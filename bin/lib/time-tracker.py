import argparse
import copy
import datetime as dt
import fnmatch
import json
import os
import re
import select
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import zoneinfo

try:
  import tomllib
except ModuleNotFoundError:
  print("Python 3.11 or newer is required for TOML config parsing.", file=sys.stderr)
  sys.exit(1)


BROWSER_APPS = {"zen", "chromium", "firefox", "google-chrome", "brave", "browser"}
WORK_APPS = {"code", "codium", "vscode", "zed", "rider", "wezterm", "terminal", "alacritty", "kitty", "ghostty"}
DEFAULT_APP_ALIASES = {
  "work": {
    "zed": ["zed", "dev.zed.zed"],
    "wezterm": ["wezterm", "org.wezfurlong.wezterm"],
    "vscode": ["code", "codium", "vscode", "visual studio code"],
    "rider": ["rider", "jetbrains-rider"],
    "terminal": ["terminal", "alacritty", "kitty", "ghostty"],
  },
  "noise": {
    "browser": sorted(BROWSER_APPS),
  },
}
DEFAULT_NOISE_STRETCH_MINUTES = 5
CONFIDENCE_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
EVIDENCE_KEYS = [
  "apps", "titles", "paths", "repositories", "worktrees", "branches",
  "urls", "commits", "descriptions", "subjects",
]
_GIT_IDENTITY_CACHE = {}


def parse_args(argv=None):
  parser = argparse.ArgumentParser(
    prog="lowr-aw-time-tracker",
    description="Summarize ActivityWatch events into daily project time records."
  )
  parser.add_argument("command", nargs="?", choices=["record", "ai-record", "list", "enable"], help="Generate/query, list versions, or enable a report version.")
  parser.add_argument("record_id", nargs="?", type=int, help="Report ID for the enable command.")
  parser.add_argument("--date", default=dt.date.today().isoformat(), help="Local date to summarize as YYYY-MM-DD.")
  parser.add_argument("--config", help="Time-tracker TOML config path.")
  parser.add_argument("--aw-url", help="ActivityWatch server URL. Overrides config.")
  parser.add_argument("--hostname", default=socket.gethostname(), help="ActivityWatch bucket hostname suffix.")
  parser.add_argument("--show-evidence", action="store_true", help="Print diagnostic evidence and attribution (may contain paths and titles).")
  parser.add_argument("--no-quality", action="store_true", help="Do not print the quality summary.")
  parser.add_argument("--describe-with", metavar="PROVIDER", help="Explicitly enable AI descriptions with pi or codex.")
  parser.add_argument("--no-ai", action="store_true", help="Disable AI descriptions even if enabled in config.")
  parser.add_argument("--ai-dry-run", action="store_true", help="Print the exact redacted AI payload without invoking a provider.")
  parser.add_argument("--no-learn", action="store_true", help="Do not persist validated AI project aliases to time-tracker memory.")
  parser.add_argument("--new", action="store_true", help="Generate and enable a new report version instead of using stored data.")
  parser.add_argument("--improve", metavar="PROMPT", help="Create and enable a refined AI report version.")
  parser.add_argument("--prompt", help="Additional guidance for AI report generation.")
  parser.add_argument("--format", choices=["table", "yaml"], default="table", help="Report output format. Defaults to an ERP-friendly chronological table.")
  parser.add_argument("--id", dest="option_record_id", type=int, help="Report ID for the enable command.")
  return parser.parse_args(argv)


def tracker_home():
  return expand_path(os.environ.get("LOWR_TIME_TRACKER_HOME", "~/.config/time-tracker"))


def run_quiet(command):
  return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0


def initialize_tracker_home(default_config, legacy_config):
  home = tracker_home()
  config_path = os.path.join(home, "config.toml")
  memory_path = os.path.join(home, "memory.json")
  database_path = os.path.join(home, "records.sqlite")
  os.makedirs(home, exist_ok=True)
  created = not os.path.exists(config_path)
  if created:
    source = legacy_config if os.path.exists(legacy_config) else default_config
    if os.path.exists(source):
      shutil.copy2(source, config_path)
      with open(config_path, encoding="utf-8") as config_file:
        content = config_file.read()
      content = content.replace("~/.config/lowr/time-tracker-memory.json", "~/.config/time-tracker/memory.json")
      with open(config_path, "w", encoding="utf-8") as config_file:
        config_file.write(content)
  if not os.path.exists(memory_path):
    legacy_memory = os.path.expanduser("~/.config/lowr/time-tracker-memory.json")
    if os.path.exists(legacy_memory):
      shutil.copy2(legacy_memory, memory_path)
    else:
      with open(memory_path, "w", encoding="utf-8") as memory_file:
        json.dump({"version": 1, "project_aliases": {}}, memory_file, indent=2)
        memory_file.write("\n")
  initialize_database(database_path)
  attributes_path = os.path.join(home, ".gitattributes")
  diff_script = os.path.join(home, "sqlite-diff")
  if not os.path.exists(attributes_path):
    with open(attributes_path, "w", encoding="utf-8") as attributes_file:
      attributes_file.write("records.sqlite diff=sqlite\n")
  diff_script_content = """#!/bin/bash

if (( $(sqlite3 -readonly "$1" "SELECT COUNT(*) FROM pragma_table_info('reports') WHERE name = 'id';") )); then
  sqlite3 -readonly -header -separator ' | ' "$1" <<'SQL'
SELECT 'REPORTS';
SELECT id, day, revision, created_at, source, parent_id, enabled, ai_provider, prompt FROM reports ORDER BY day, revision;
SELECT 'RECORDS';
SELECT report_id, position, project, subject, description, confidence, minutes FROM records ORDER BY report_id, position;
SELECT 'PERIODS';
SELECT report_id, record_position, position, start, end FROM periods ORDER BY report_id, record_position, position;
SQL
else
  sqlite3 -readonly -header -separator ' | ' "$1" <<'SQL'
SELECT 'REPORTS';
SELECT day, generated_at, updated_at, ai_provider, prompt FROM reports ORDER BY day;
SELECT 'RECORDS';
SELECT report_day, position, project, subject, description, confidence, minutes FROM records ORDER BY report_day, position;
SELECT 'PERIODS';
SELECT report_day, record_position, position, start, end FROM periods ORDER BY report_day, record_position, position;
SQL
fi
"""
  current_diff_script = ""
  if os.path.exists(diff_script):
    with open(diff_script, encoding="utf-8") as script_file:
      current_diff_script = script_file.read()
  if current_diff_script != diff_script_content:
    with open(diff_script, "w", encoding="utf-8") as script_file:
      script_file.write(diff_script_content)
    os.chmod(diff_script, 0o755)
  new_repository = not os.path.isdir(os.path.join(home, ".git"))
  if new_repository:
    run_quiet(["git", "init", "-q", home])
  run_quiet(["git", "-C", home, "config", "diff.sqlite.textconv", diff_script])
  run_quiet(["git", "-C", home, "config", "diff.sqlite.binary", "false"])
  if new_repository:
    run_quiet(["git", "-C", home, "add", "config.toml", "memory.json", "records.sqlite", ".gitattributes", "sqlite-diff"])
    run_quiet([
      "git", "-C", home, "-c", "user.name=Lowr Time Tracker",
      "-c", "user.email=time-tracker@localhost", "commit", "-qm",
      "Initialize time-tracker configuration",
    ])
  return config_path


def load_config(path):
  lowr_path = os.environ.get("LOWR_PATH", os.path.expanduser("~/.local/share/lowr"))
  default_path = os.path.join(lowr_path, "config", "lowr", "time-tracker.toml")
  legacy_path = os.path.expanduser("~/.config/lowr/time-tracker.toml")
  config_path = os.path.expanduser(path) if path else initialize_tracker_home(default_path, legacy_path)

  if not os.path.exists(config_path):
    print(f"Config not found: {config_path}", file=sys.stderr)
    sys.exit(1)

  try:
    with open(config_path, "rb") as config_file:
      config = tomllib.load(config_file)
  except tomllib.TOMLDecodeError as error:
    print(f"Invalid config {config_path}: {error}", file=sys.stderr)
    sys.exit(1)

  validate_config(config)
  load_tracker_memory(config)
  return config, config_path


def validate_config(config):
  projects = config.get("projects", [])
  if projects and not isinstance(projects, list):
    raise_config("projects", "must be an array of tables ([[projects]])")
  for index, project in enumerate(projects):
    if not isinstance(project, dict):
      raise_config(f"projects[{index}]", "must be a table")
    if not str(project.get("name", "")).strip():
      raise_config(f"projects[{index}].name", "must not be empty")
    for key in ["path_prefixes", "title_patterns", "url_patterns"]:
      if key in project and not isinstance(project[key], list):
        raise_config(f"projects[{index}].{key}", "must be a list")

  apps = config.get("apps", {})
  if not isinstance(apps, dict):
    raise_config("apps", "must be a table")
  for kind in ["work", "noise"]:
    aliases = apps.get(kind, {})
    if not isinstance(aliases, dict):
      raise_config(f"apps.{kind}", "must be a table")
    for canonical, values in aliases.items():
      if not isinstance(values, list):
        raise_config(f"apps.{kind}.{canonical}", "must be a list")

  for section in ["activitywatch", "day", "rounding", "breaks", "buckets", "noise", "work_apps", "terminal", "git", "ai", "storage", "project_aliases"]:
    if section in config and not isinstance(config[section], dict):
      raise_config(section, "must be a table")

  numeric_keys = {
    "rounding": [("minutes", 15, 1)],
    "noise": [("stretch_minutes", 5, 0)],
    "breaks": [("coffee_minutes", 15, 1), ("coffee_window_minutes", 60, 0)],
    "terminal": [("nearby_minutes", 5, 0), ("max_context_age_minutes", 120, 0)],
    "git": [("query_margin_minutes", 30, 0), ("correlation_margin_minutes", 15, 0), ("timeout_seconds", 5, 1)],
    "ai": [("timeout_seconds", 60, 1), ("minimum_minutes", 15, 0)],
  }
  for section, values in numeric_keys.items():
    for key, default, minimum in values:
      value = config.get(section, {}).get(key, default)
      try:
        parsed = int(value)
      except (TypeError, ValueError):
        raise_config(f"{section}.{key}", "must be an integer")
      if parsed < minimum:
        raise_config(f"{section}.{key}", f"must be at least {minimum}")

  for alias, project in config.get("project_aliases", {}).items():
    if not isinstance(project, str) or not project.strip():
      raise_config(f"project_aliases.{alias}", "must be a non-empty project name")

  web_buckets = config.get("buckets", {}).get("web", [])
  if not isinstance(web_buckets, (str, list)):
    raise_config("buckets.web", "must be a string or list")


def raise_config(key, message):
  print(f"Invalid config: {key} {message}", file=sys.stderr)
  raise SystemExit(1)


def tracker_memory_path(config):
  configured = config.get("ai", {}).get("memory_path", "~/.config/time-tracker/memory.json")
  return expand_path(configured)


def tracker_database_path(config):
  configured = config.get("storage", {}).get("database_path", "~/.config/time-tracker/records.sqlite")
  return expand_path(configured)


def load_tracker_memory(config):
  path = tracker_memory_path(config)
  config["_memory_path"] = path
  config["_learned_project_aliases"] = {}
  if not os.path.exists(path):
    return
  try:
    with open(path, encoding="utf-8") as memory_file:
      memory = json.load(memory_file)
  except (OSError, json.JSONDecodeError) as error:
    print(f"Ignoring invalid time-tracker memory {path}: {error}", file=sys.stderr)
    return
  aliases = memory.get("project_aliases", {}) if isinstance(memory, dict) else {}
  if not isinstance(aliases, dict):
    print(f"Ignoring invalid time-tracker memory {path}: project_aliases must be an object", file=sys.stderr)
    return
  for alias, item in aliases.items():
    if isinstance(item, str):
      project = item
    elif isinstance(item, dict):
      project = item.get("project", "")
    else:
      continue
    if str(alias).strip() and str(project).strip():
      config["_learned_project_aliases"][str(alias)] = str(project)


def configured_project_aliases(config):
  aliases = {}
  for source in [config.get("project_aliases", {}), config.get("_learned_project_aliases", {})]:
    if not isinstance(source, dict):
      continue
    for alias, project in source.items():
      alias_text = str(alias).strip()
      project_text = str(project).strip()
      if alias_text and project_text:
        aliases[alias_text.casefold()] = {"alias": alias_text, "project": project_text}
  return aliases


def resolve_project_alias(value, config):
  text = str(value or "").strip()
  item = configured_project_aliases(config).get(text.casefold())
  return item["project"] if item else text


def match_learned_title_alias(title, config):
  for item in configured_project_aliases(config).values():
    if pattern_matches(title, item["alias"]):
      return item
  return None


def local_timezone():
  candidates = []
  if os.environ.get("TZ"):
    candidates.append(os.environ["TZ"].lstrip(":"))
  try:
    localtime = os.path.realpath("/etc/localtime")
    marker = "/zoneinfo/"
    if marker in localtime:
      candidates.append(localtime.split(marker, 1)[1])
  except OSError:
    pass
  try:
    with open("/etc/timezone", encoding="utf-8") as timezone_file:
      candidates.append(timezone_file.read().strip())
  except OSError:
    pass
  for candidate in candidates:
    try:
      return zoneinfo.ZoneInfo(candidate)
    except (ValueError, zoneinfo.ZoneInfoNotFoundError):
      continue
  return dt.datetime.now().astimezone().tzinfo


def local_day_bounds(day, start_time):
  local_zone = local_timezone()
  start = dt.datetime.combine(day, start_time, tzinfo=local_zone)
  end = dt.datetime.combine(day + dt.timedelta(days=1), start_time, tzinfo=local_zone)
  return start, end


def parse_aw_time(value):
  if value.endswith("Z"):
    value = value[:-1] + "+00:00"
  parsed = dt.datetime.fromisoformat(value)
  if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=local_timezone())
  return parsed.astimezone(local_timezone())


def _events_url(aw_url, bucket, start, end):
  params = urllib.parse.urlencode({
    "start": start.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    "end": end.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
  })
  return f"{aw_url.rstrip('/')}/api/0/buckets/{urllib.parse.quote(bucket, safe='')}/events?{params}"


def query_events(aw_url, bucket, start, end, required=True):
  try:
    with urllib.request.urlopen(_events_url(aw_url, bucket, start, end), timeout=5) as response:
      return json.loads(response.read().decode("utf-8"))
  except urllib.error.HTTPError as error:
    if error.code == 404:
      return []
    if not required:
      return []
    raise
  except (urllib.error.URLError, TimeoutError) as error:
    if not required:
      return []
    reason = getattr(error, "reason", error)
    print(f"Could not connect to ActivityWatch at {aw_url}: {reason}", file=sys.stderr)
    raise SystemExit(1)


def query_buckets(aw_url):
  try:
    with urllib.request.urlopen(f"{aw_url.rstrip('/')}/api/0/buckets", timeout=5) as response:
      value = json.loads(response.read().decode("utf-8"))
      return value if isinstance(value, dict) else {}
  except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
    return {}


def normalize_event(event, day_start, day_end, allow_point=False):
  try:
    start = parse_aw_time(event["timestamp"])
    duration = float(event.get("duration", 0) or 0)
  except (KeyError, TypeError, ValueError):
    return None
  end = start + dt.timedelta(seconds=max(duration, 0))

  if duration <= 0:
    if not allow_point or start < day_start or start >= day_end:
      return None
    end = start
  elif end <= day_start or start >= day_end:
    return None

  return {
    "start": max(start, day_start),
    "end": min(end, day_end),
    "data": event.get("data", {}) or {},
  }


def normalize_events(events, day_start, day_end, allow_points=False):
  normalized = []
  for event in events:
    item = normalize_event(event, day_start, day_end, allow_points)
    if item:
      normalized.append(item)
  return sorted(normalized, key=lambda item: item["start"])


def lower_values(values):
  return [str(value).strip().lower() for value in values if str(value).strip()]


def get_config_list(config, section, key, fallback):
  value = config.get(section, {}).get(key, fallback)
  return set(lower_values(value))


def first_value(*values):
  for value in values:
    text = str(value or "").strip()
    if text:
      return text
  return ""


def empty_evidence():
  return {key: [] for key in EVIDENCE_KEYS}


def new_record(start, end):
  return {
    "project": "unassigned",
    "subject": "",
    "description": "",
    "confidence": "unknown",
    "start": start,
    "end": end,
    "evidence": empty_evidence(),
    "attribution": [],
  }


def evidence_identity(value):
  if isinstance(value, dict):
    return json.dumps(value, sort_keys=True, default=str)
  return str(value)


def add_evidence(target, key, value):
  if value is None or value == "":
    return
  evidence = target.setdefault("evidence", empty_evidence())
  values = evidence.setdefault(key, [])
  identity = evidence_identity(value)
  if not any(evidence_identity(existing) == identity for existing in values):
    values.append(copy.deepcopy(value))


def merge_evidence(target, source):
  for key, values in source.get("evidence", {}).items():
    for value in values:
      add_evidence(target, key, value)
  for attribution in source.get("attribution", []):
    if attribution not in target.setdefault("attribution", []):
      target["attribution"].append(copy.deepcopy(attribution))
  if CONFIDENCE_RANK.get(source.get("confidence", "unknown"), 0) > CONFIDENCE_RANK.get(target.get("confidence", "unknown"), 0):
    target["confidence"] = source["confidence"]


def add_attribution(record, field, source, value, confidence):
  item = {"field": field, "source": source, "value": value, "confidence": confidence}
  if item not in record.setdefault("attribution", []):
    record["attribution"].append(item)


def set_project(record, value, source, confidence, force=False):
  value = str(value or "").strip()
  if not value:
    return False
  current = record.get("project", "unassigned")
  current_rank = CONFIDENCE_RANK.get(record.get("confidence", "unknown"), 0)
  rank = CONFIDENCE_RANK.get(confidence, 0)
  if current != "unassigned" and current != value and not force and rank <= current_rank:
    add_attribution(record, "project_conflict", source, value, confidence)
    return False
  if force or current == "unassigned" or rank > current_rank or current == value:
    record["project"] = value
    record["confidence"] = confidence if rank >= current_rank else record["confidence"]
    add_attribution(record, "project", source, value, confidence)
    return True
  return False


def app_aliases(config):
  aliases = {"work": {}, "noise": {}}
  for kind, defaults in DEFAULT_APP_ALIASES.items():
    for canonical, values in defaults.items():
      aliases[kind][canonical] = set(lower_values(values + [canonical]))

  configured = config.get("apps", {})
  for kind in ["work", "noise"]:
    for canonical, values in configured.get(kind, {}).items():
      if not isinstance(values, list):
        raise_config(f"apps.{kind}.{canonical}", "must be a list")
      aliases[kind].setdefault(str(canonical).strip().lower(), set()).update(lower_values(values + [canonical]))

  for value in get_config_list(config, "work_apps", "apps", WORK_APPS):
    aliases["work"].setdefault(value, set()).add(value)
  for value in get_config_list(config, "noise", "apps", BROWSER_APPS):
    aliases["noise"].setdefault(value, set()).add(value)
  return aliases


def resolve_application(value, config):
  raw = str(value or "").strip().lower()
  if not raw:
    return "", ""
  aliases = app_aliases(config)
  for kind in ["work", "noise"]:
    for canonical, values in aliases[kind].items():
      if raw in values:
        return canonical, kind
  return raw, ""


def expand_path(value):
  return os.path.abspath(os.path.expandvars(os.path.expanduser(str(value))))


def project_rules(config):
  rules = []
  for item in config.get("projects", []):
    rule = dict(item)
    rule["name"] = str(item["name"]).strip()
    rule["path_prefixes"] = [expand_path(value) for value in item.get("path_prefixes", [])]
    rule["title_patterns"] = [str(value).strip() for value in item.get("title_patterns", []) if str(value).strip()]
    rule["url_patterns"] = [str(value).strip() for value in item.get("url_patterns", []) if str(value).strip()]
    rules.append(rule)
  return rules


def path_matches(path, prefix):
  path = os.path.normpath(expand_path(path))
  prefix = os.path.normpath(prefix)
  return path == prefix or path.startswith(prefix + os.sep)


def match_project_path(path, rules):
  matches = []
  for rule in rules:
    for prefix in rule["path_prefixes"]:
      if path_matches(path, prefix):
        matches.append((len(prefix), rule, prefix))
  return max(matches, key=lambda item: item[0])[1:] if matches else (None, None)


def pattern_matches(value, pattern, literal_contains=True):
  value = str(value).casefold()
  pattern = str(pattern).casefold()
  if any(character in pattern for character in "*?["):
    return fnmatch.fnmatch(value, pattern)
  return pattern in value if literal_contains else value == pattern


def match_project_title(title, rules):
  for rule in rules:
    for pattern in rule["title_patterns"]:
      if pattern_matches(title, pattern):
        return rule, pattern
  return None, None


def match_project_remote(remote, rules):
  remote = sanitize_remote(remote)
  if not remote:
    return None, None
  for rule in rules:
    for path in rule["path_prefixes"]:
      identity = git_identity(path)
      if identity and identity.get("remote") == remote:
        return rule, remote
  return None, None


def sanitize_remote(value):
  remote = str(value or "").strip()
  if not remote:
    return ""
  if "://" in remote:
    parsed = urllib.parse.urlsplit(remote)
    host = (parsed.hostname or "").lower()
    path = parsed.path
  elif re.match(r"^[^/@]+@[^:]+:", remote):
    host_path = remote.split("@", 1)[1]
    host, path = host_path.split(":", 1)
    path = "/" + path
  else:
    parsed = urllib.parse.urlsplit("//" + remote)
    host = (parsed.hostname or "").lower()
    path = parsed.path
  path = re.sub(r"\.git$", "", path).strip("/")
  return f"{host}/{path}" if host and path else host


def sanitize_url(value, include_path=True):
  try:
    parsed = urllib.parse.urlsplit(str(value or ""))
  except ValueError:
    return ""
  if not parsed.hostname:
    return ""
  host = parsed.hostname.lower()
  port = f":{parsed.port}" if parsed.port else ""
  path = parsed.path if include_path else ""
  return urllib.parse.urlunsplit((parsed.scheme.lower() or "https", host + port, path, "", ""))


def match_project_url(url, rules):
  sanitized = sanitize_url(url)
  if not sanitized:
    return None, None
  parsed = urllib.parse.urlsplit(sanitized)
  host_path = parsed.hostname + parsed.path
  for rule in rules:
    for pattern in rule["url_patterns"]:
      candidate = pattern.split("://", 1)[-1]
      if pattern_matches(host_path, candidate, literal_contains=False):
        return rule, pattern
    for web_rule in rule.get("web", []):
      host = str(web_rule.get("host", "")).casefold()
      if host and parsed.hostname.casefold() != host:
        continue
      for pattern in web_rule.get("path_patterns", []):
        if pattern_matches(parsed.path, pattern, literal_contains=False):
          return rule, pattern
  return None, None


def run_git(path, args, timeout=3):
  try:
    result = subprocess.run(
      ["git", "-C", path, *args], capture_output=True, text=True,
      timeout=timeout, check=False,
    )
  except (OSError, subprocess.TimeoutExpired):
    return ""
  return result.stdout.strip() if result.returncode == 0 else ""


def git_identity(path):
  if not path:
    return None
  candidate = expand_path(path)
  if os.path.isfile(candidate):
    candidate = os.path.dirname(candidate)
  cached = _GIT_IDENTITY_CACHE.get(candidate)
  if cached is not None:
    return copy.deepcopy(cached) if cached else None
  if not os.path.exists(candidate):
    _GIT_IDENTITY_CACHE[candidate] = False
    return None

  worktree = run_git(candidate, ["rev-parse", "--show-toplevel"])
  common = run_git(candidate, ["rev-parse", "--path-format=absolute", "--git-common-dir"])
  if not worktree:
    _GIT_IDENTITY_CACHE[candidate] = False
    return None
  repository = os.path.dirname(common) if os.path.basename(common) == ".git" else worktree
  identity = {
    "repository": os.path.realpath(repository),
    "worktree": os.path.realpath(worktree),
    "branch": run_git(candidate, ["branch", "--show-current"]),
    "remote": sanitize_remote(run_git(candidate, ["config", "--get", "remote.origin.url"])),
  }
  _GIT_IDENTITY_CACHE[candidate] = identity
  return copy.deepcopy(identity)


def add_git_identity(record, identity):
  if not identity:
    return
  add_evidence(record, "repositories", identity.get("repository"))
  add_evidence(record, "worktrees", identity.get("worktree"))
  add_evidence(record, "branches", identity.get("branch"))
  if identity.get("remote"):
    record.setdefault("repository_remotes", {})[identity["repository"]] = identity["remote"]


def terminal_context(event):
  if not event:
    return {}
  data = dict(event.get("data", event))
  identity = None
  for path in [data.get("worktree"), data.get("repository"), data.get("path"), data.get("file")]:
    if path:
      identity = git_identity(path)
      if identity:
        break
  if identity:
    data.setdefault("repository", identity["repository"])
    data.setdefault("worktree", identity["worktree"])
    data.setdefault("branch", identity["branch"])
    data.setdefault("remote", identity["remote"])
  if data.get("remote"):
    data["remote"] = sanitize_remote(data["remote"])
  return data


def _terminal_agrees(data, title, rules):
  terminal_project = first_value(data.get("project"), data.get("category"))
  terminal_repository = first_value(data.get("repository"), data.get("worktree"), data.get("path"))
  title_rule, _ = match_project_title(title, rules)
  path_rule, _ = match_project_path(terminal_repository, rules) if terminal_repository else (None, None)
  if title_rule and path_rule:
    return title_rule["name"] == path_rule["name"]
  if title_rule and terminal_project:
    return title_rule["name"].casefold() == terminal_project.casefold()
  names = [terminal_project, os.path.basename(terminal_repository.rstrip(os.sep)) if terminal_repository else ""]
  return any(name and pattern_matches(title, name) for name in names)


def find_terminal_event(start, end, terminal_events, title="", config=None):
  config = config or {}
  rules = project_rules(config)
  nearby_seconds = int(config.get("terminal", {}).get("nearby_minutes", 5)) * 60
  max_seconds = int(config.get("terminal", {}).get("max_context_age_minutes", 120)) * 60
  best = None
  best_score = None

  for event in terminal_events:
    overlap = (min(end, event["end"]) - max(start, event["start"])).total_seconds()
    data = terminal_context(event)
    if overlap > 0:
      score = (3, overlap, event["start"])
    elif event["start"] <= start:
      age = (start - event["end"]).total_seconds()
      limit = max_seconds if _terminal_agrees(data, title, rules) else nearby_seconds
      if age < 0 or age > limit:
        continue
      score = (2 if limit == max_seconds else 1, -age, event["start"])
    else:
      distance = (event["start"] - end).total_seconds()
      if distance < 0 or distance > nearby_seconds:
        continue
      score = (1, -distance, event["start"])
    if best_score is None or score > best_score:
      best = dict(event)
      best["data"] = data
      best_score = score
  return best


def find_terminal_hint(start, end, terminal_events):
  event = find_terminal_event(start, end, terminal_events)
  return event["data"] if event else None


def classify_activity(data, terminal_hint):
  project = first_value(data.get("project"), data.get("category"), (terminal_hint or {}).get("project"), (terminal_hint or {}).get("category"))
  if not project:
    return None
  return {
    "project": project,
    "subject": first_value(data.get("subject"), (terminal_hint or {}).get("subject")),
    "description": first_value(data.get("description"), (terminal_hint or {}).get("description"), "review needed"),
  }


def round_down(value, minutes):
  minute = (value.minute // minutes) * minutes
  return value.replace(minute=minute, second=0, microsecond=0)


def round_up(value, minutes):
  rounded = round_down(value, minutes)
  if rounded == value.replace(second=0, microsecond=0):
    return rounded
  return rounded + dt.timedelta(minutes=minutes)


def parse_time(value):
  if not value:
    return None
  return dt.time.fromisoformat(value)


def configured_start_time(config):
  value = config.get("day", {}).get("start_time", "00:00")
  try:
    return dt.time.fromisoformat(value)
  except (TypeError, ValueError):
    raise_config("day.start_time", "must be formatted as HH:MM")


def time_on_day(day, zone, value):
  return dt.datetime.combine(day, value, tzinfo=zone)


def afk_break_records(afk_events, config):
  breaks = config.get("breaks", {})
  coffee_minutes = int(breaks.get("coffee_minutes", 15))
  window_minutes = int(breaks.get("coffee_window_minutes", 60))
  slots = [
    ("morning", parse_time(breaks.get("coffee_morning_time", "09:30"))),
    ("afternoon", parse_time(breaks.get("coffee_afternoon_time", "15:00"))),
  ]
  records = []

  for subject, slot_time in slots:
    if not slot_time:
      continue
    best = None
    best_distance = None
    for event in afk_events:
      if event["data"].get("status") != "afk":
        continue
      if (event["end"] - event["start"]).total_seconds() / 60 < coffee_minutes:
        continue
      target = time_on_day(event["start"].date(), event["start"].tzinfo, slot_time)
      if event["start"] >= target + dt.timedelta(minutes=window_minutes) or event["end"] <= target - dt.timedelta(minutes=window_minutes):
        continue
      earliest = event["start"]
      latest = event["end"] - dt.timedelta(minutes=coffee_minutes)
      if latest < earliest:
        continue
      # Prefer the configured quarter-hour slot, but clamp it into the AFK
      # interval instead of discarding a valid break with non-aligned seconds.
      record_start = max(earliest, min(round_down(target, coffee_minutes), latest))
      distance = abs((record_start - target).total_seconds())
      if best_distance is None or distance < best_distance:
        best = (record_start, record_start + dt.timedelta(minutes=coffee_minutes))
        best_distance = distance
    if best:
      record = new_record(*best)
      record.update({
        "project": "internal", "subject": f"coffee-{subject}",
        "description": "coffee break", "confidence": "high",
        "description_source": "configured_break", "description_confidence": "high",
      })
      add_attribution(record, "project", "configured_break", "internal", "high")
      records.append(record)
  return records


def subtract_intervals(record, intervals):
  parts = [copy.deepcopy(record)]
  for interval in intervals:
    next_parts = []
    for part in parts:
      if interval["end"] <= part["start"] or interval["start"] >= part["end"]:
        next_parts.append(part)
        continue
      if part["start"] < interval["start"]:
        before = copy.deepcopy(part)
        before["end"] = interval["start"]
        next_parts.append(before)
      if part["end"] > interval["end"]:
        after = copy.deepcopy(part)
        after["start"] = interval["end"]
        next_parts.append(after)
    parts = next_parts
  return parts


def remove_afk_from_work(records, afk_events, preserve_breaks=False):
  intervals = [event for event in afk_events if event["data"].get("status") == "afk"]
  cleaned = []
  for record in records:
    if preserve_breaks and record.get("description_source") == "configured_break":
      cleaned.append(copy.deepcopy(record))
    else:
      cleaned.extend(subtract_intervals(record, intervals))
  return cleaned


def overlaps_intervals(start, end, intervals):
  return any(interval["start"] < end and interval["end"] > start for interval in intervals)


def subject_is_reliable(record):
  return CONFIDENCE_RANK.get(record.get("subject_confidence", "unknown"), 0) >= CONFIDENCE_RANK["medium"]


def same_work(left, right):
  if left.get("project", "unassigned") != right.get("project", "unassigned"):
    return False
  left_subject = left.get("subject", "")
  right_subject = right.get("subject", "")
  if left_subject and right_subject and left_subject != right_subject and subject_is_reliable(left) and subject_is_reliable(right):
    return False
  return True


def stretch_records_over_noise(records, noise_events, afk_events, minutes):
  if not records or not noise_events or minutes <= 0:
    return records
  limit = dt.timedelta(minutes=minutes)
  afk_intervals = [event for event in afk_events if event["data"].get("status") == "afk"]
  stretched = [copy.deepcopy(record) for record in sorted(records, key=lambda item: item["start"])]

  for noise in noise_events:
    if noise["end"] <= noise["start"] or noise["end"] - noise["start"] > limit:
      continue
    if overlaps_intervals(noise["start"], noise["end"], afk_intervals):
      continue
    previous = None
    next_record = None
    for record in stretched:
      if record["end"] <= noise["start"]:
        previous = record
        continue
      if record["start"] >= noise["end"]:
        next_record = record
        break
    if previous and noise["end"] - previous["end"] <= limit and not overlaps_intervals(previous["end"], noise["end"], afk_intervals):
      previous["end"] = noise["end"]
    if next_record and next_record["start"] - noise["start"] <= limit and not overlaps_intervals(noise["start"], next_record["start"], afk_intervals):
      next_record["start"] = noise["start"]
    if previous and next_record and same_work(previous, next_record):
      gap = next_record["start"] - previous["end"]
      if dt.timedelta(0) < gap <= limit and not overlaps_intervals(previous["end"], next_record["start"], afk_intervals):
        previous["end"] = next_record["start"]
  return stretched


def best_overlapping_event(start, end, events):
  best = None
  best_overlap = 0
  for event in events:
    overlap = (min(end, event["end"]) - max(start, event["start"])).total_seconds()
    if overlap > best_overlap:
      best = event
      best_overlap = overlap
  return best


def _add_terminal_evidence(record, data):
  for key in ["file", "path"]:
    add_evidence(record, "paths", data.get(key))
  add_evidence(record, "repositories", data.get("repository"))
  add_evidence(record, "worktrees", data.get("worktree"))
  add_evidence(record, "branches", data.get("branch"))
  if data.get("remote") and data.get("repository"):
    record.setdefault("repository_remotes", {})[data["repository"]] = sanitize_remote(data["remote"])


def resolve_record_project(record, window_data, terminal_data, web_data, config):
  rules = project_rules(config)
  paths = record["evidence"]["repositories"] + record["evidence"]["worktrees"] + record["evidence"]["paths"]
  for path in paths:
    rule, prefix = match_project_path(path, rules)
    if rule:
      set_project(record, rule["name"], "path_mapping", "high")
      add_attribution(record, "project_path", "path_mapping", prefix, "high")
      break

  if record["project"] == "unassigned":
    remote = first_value(window_data.get("remote"), terminal_data.get("remote"))
    rule, normalized_remote = match_project_remote(remote, rules)
    if rule:
      set_project(record, rule["name"], "remote_identity", "high")
      add_attribution(record, "project_remote", "remote_identity", normalized_remote, "high")

  if record["project"] == "unassigned":
    for title in record["evidence"]["titles"]:
      rule, pattern = match_project_title(title, rules)
      if rule:
        set_project(record, rule["name"], "title_mapping", "medium")
        add_attribution(record, "project_title", "title_mapping", pattern, "medium")
        break

  if record["project"] == "unassigned":
    for title in record["evidence"]["titles"]:
      alias = match_learned_title_alias(title, config)
      if alias:
        set_project(record, alias["project"], "project_alias_memory", "medium")
        add_attribution(record, "project_title", "project_alias_memory", alias["alias"], "medium")
        break

  if record["project"] == "unassigned":
    for url in record["evidence"]["urls"]:
      rule, pattern = match_project_url(url, rules)
      if rule:
        set_project(record, rule["name"], "url_mapping", "high" if "/pull/" in url or "/issues/" in url else "medium")
        add_attribution(record, "project_url", "url_mapping", pattern, record["confidence"])
        break

  if record["project"] == "unassigned" and record["evidence"]["repositories"]:
    repository_project = os.path.basename(record["evidence"]["repositories"][0].rstrip(os.sep))
    set_project(record, resolve_project_alias(repository_project, config), "repository_identity", "high")

  supplied = first_value(window_data.get("project"), window_data.get("category"), terminal_data.get("project"), terminal_data.get("category"))
  if record["project"] == "unassigned" and supplied:
    canonical = resolve_project_alias(supplied, config)
    source = "project_alias" if canonical != supplied else "activitywatch_project"
    set_project(record, canonical, source, "medium")
    if canonical != supplied:
      add_attribution(record, "project_alias", source, supplied, "medium")

  subject = first_value(window_data.get("subject"), terminal_data.get("subject"))
  if subject:
    record["subject"] = subject
    record["subject_confidence"] = "high"
    add_attribution(record, "subject", "activitywatch_subject", subject, "high")
  description = first_value(window_data.get("description"), terminal_data.get("description"))
  if description and description != "review needed":
    add_evidence(record, "descriptions", description)


def build_records(window_events, terminal_events, afk_events, config, web_events=None):
  web_events = web_events or []
  noise_stretch_minutes = int(config.get("noise", {}).get("stretch_minutes", DEFAULT_NOISE_STRETCH_MINUTES))
  records = []
  noise_events = []

  for event in window_events:
    data = event["data"]
    raw_app = str(data.get("app", "")).strip()
    canonical_app, app_kind = resolve_application(raw_app, config)
    title = first_value(data.get("title"), data.get("name"))
    terminal_event = find_terminal_event(event["start"], event["end"], terminal_events, title, config)
    terminal_data = terminal_event["data"] if terminal_event else {}
    web_event = best_overlapping_event(event["start"], event["end"], web_events) if app_kind == "noise" else None
    web_data = web_event["data"] if web_event else {}

    record = new_record(event["start"], event["end"])
    add_evidence(record, "apps", raw_app)
    if canonical_app and canonical_app != raw_app.casefold():
      add_evidence(record, "apps", canonical_app)
    add_evidence(record, "titles", title)
    for key in ["file", "path"]:
      path = data.get(key)
      add_evidence(record, "paths", path)
      add_git_identity(record, git_identity(path))
    if terminal_event:
      _add_terminal_evidence(record, terminal_data)
    if web_event:
      url = sanitize_url(web_data.get("url", ""))
      add_evidence(record, "urls", url)
      add_evidence(record, "titles", first_value(web_data.get("title"), web_data.get("name")))

    resolve_record_project(record, data, terminal_data, web_data, config)
    derive_subject(record)
    has_project = record["project"] != "unassigned"
    if app_kind == "noise" and not has_project:
      noise_events.append(event)
      continue
    if not has_project and app_kind != "work":
      continue
    records.append(record)

  work_records = remove_afk_from_work(records, afk_events)
  work_records = stretch_records_over_noise(work_records, noise_events, afk_events, noise_stretch_minutes)
  work_records.extend(afk_break_records(afk_events, config))
  return work_records


def round_records(records, minutes):
  rounded = []
  for record in records:
    if record.get("description_source") == "configured_break":
      rounded.append(copy.deepcopy(record))
      continue
    start = round_down(record["start"], minutes)
    end = round_up(record["end"], minutes)
    if end <= start:
      continue
    item = copy.deepcopy(record)
    item["start"] = start
    item["end"] = end
    rounded.append(item)
  return sorted(rounded, key=lambda item: item["start"])


def merge_records(records):
  merged = []
  for source in sorted(records, key=lambda item: item["start"]):
    record = copy.deepcopy(source)
    if not merged:
      merged.append(record)
      continue
    previous = merged[-1]
    if same_work(previous, record) and record["start"] <= previous["end"]:
      previous["end"] = max(previous["end"], record["end"])
      merge_evidence(previous, record)
      if not previous.get("subject") and record.get("subject"):
        previous["subject"] = record["subject"]
        previous["subject_confidence"] = record.get("subject_confidence", "unknown")
    else:
      merged.append(record)
  return merged


def remove_overlaps(records):
  cleaned = []
  for source in sorted(records, key=lambda item: item["start"]):
    record = copy.deepcopy(source)
    if not cleaned:
      cleaned.append(record)
      continue
    previous = cleaned[-1]
    if record["start"] < previous["end"]:
      if same_work(previous, record):
        previous["end"] = max(previous["end"], record["end"])
        merge_evidence(previous, record)
        continue
      record["start"] = previous["end"]
    if record["end"] > record["start"]:
      cleaned.append(record)
  return cleaned


def configured_web_buckets(config, aw_url, hostname):
  explicit = config.get("buckets", {}).get("web", [])
  if isinstance(explicit, str):
    explicit = [explicit]
  result = list(explicit)
  for bucket, metadata in query_buckets(aw_url).items():
    bucket_type = str(metadata.get("type", "")).lower()
    client = str(metadata.get("client", "")).lower()
    if ("web" in bucket_type or "web" in client or bucket.startswith("aw-watcher-web-")) and bucket not in result:
      result.append(bucket)
  return result


def query_web_events(config, aw_url, hostname, start, end):
  events = []
  for bucket in configured_web_buckets(config, aw_url, hostname):
    events.extend(query_events(aw_url, bucket, start, end, required=False))
  return normalize_events(events, start, end)


def record_periods(record):
  periods = record.get("periods")
  if periods:
    return periods
  return [{"start": record["start"], "end": record["end"]}]


def record_minutes(record):
  return round(sum((period["end"] - period["start"]).total_seconds() for period in record_periods(record)) / 60)


def create_database_schema(database):
  database.executescript("""
    CREATE TABLE IF NOT EXISTS reports (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      day TEXT NOT NULL,
      revision INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      config_path TEXT NOT NULL,
      ai_provider TEXT,
      prompt TEXT,
      source TEXT NOT NULL,
      parent_id INTEGER REFERENCES reports(id),
      enabled INTEGER NOT NULL DEFAULT 0,
      UNIQUE(day, revision)
    );
    CREATE INDEX IF NOT EXISTS reports_day_idx ON reports(day, enabled, id);
    CREATE TABLE IF NOT EXISTS records (
      report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
      position INTEGER NOT NULL,
      project TEXT NOT NULL,
      subject TEXT NOT NULL,
      description TEXT NOT NULL,
      confidence TEXT NOT NULL,
      minutes INTEGER NOT NULL,
      payload_json TEXT NOT NULL,
      PRIMARY KEY (report_id, position)
    );
    CREATE INDEX IF NOT EXISTS records_project_idx ON records(project, report_id);
    CREATE TABLE IF NOT EXISTS periods (
      report_id INTEGER NOT NULL,
      record_position INTEGER NOT NULL,
      position INTEGER NOT NULL,
      start TEXT NOT NULL,
      end TEXT NOT NULL,
      PRIMARY KEY (report_id, record_position, position),
      FOREIGN KEY (report_id, record_position) REFERENCES records(report_id, position) ON DELETE CASCADE
    );
    PRAGMA user_version = 2;
  """)


def migrate_legacy_database(database):
  columns = {row[1] for row in database.execute("PRAGMA table_info(reports)")}
  if not columns or "id" in columns:
    return
  database.execute("PRAGMA foreign_keys = OFF")
  database.executescript("""
    ALTER TABLE reports RENAME TO legacy_reports;
    ALTER TABLE records RENAME TO legacy_records;
    ALTER TABLE periods RENAME TO legacy_periods;
    DROP INDEX IF EXISTS records_project_idx;
  """)
  create_database_schema(database)
  report_ids = {}
  legacy_reports = database.execute(
    "SELECT day, generated_at, updated_at, config_path, ai_provider, prompt FROM legacy_reports ORDER BY day"
  ).fetchall()
  for day, generated_at, updated_at, config_path, provider, prompt in legacy_reports:
    created_at = updated_at or generated_at
    source = "ai" if provider else "deterministic"
    cursor = database.execute(
      "INSERT INTO reports(day, revision, created_at, config_path, ai_provider, prompt, source, enabled) VALUES (?, 1, ?, ?, ?, ?, ?, 1)",
      (day, created_at, config_path, provider, prompt, source),
    )
    report_ids[day] = cursor.lastrowid
  for row in database.execute(
    "SELECT report_day, position, project, subject, description, confidence, minutes, payload_json FROM legacy_records"
  ).fetchall():
    database.execute(
      "INSERT INTO records(report_id, position, project, subject, description, confidence, minutes, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
      (report_ids[row[0]], *row[1:]),
    )
  for row in database.execute(
    "SELECT report_day, record_position, position, start, end FROM legacy_periods"
  ).fetchall():
    database.execute(
      "INSERT INTO periods(report_id, record_position, position, start, end) VALUES (?, ?, ?, ?, ?)",
      (report_ids[row[0]], *row[1:]),
    )
  database.executescript("""
    DROP TABLE legacy_periods;
    DROP TABLE legacy_records;
    DROP TABLE legacy_reports;
  """)
  database.execute("PRAGMA foreign_keys = ON")


def initialize_database(path):
  path = expand_path(path)
  os.makedirs(os.path.dirname(path), exist_ok=True)
  with sqlite3.connect(path) as database:
    table_exists = database.execute(
      "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'reports'"
    ).fetchone()
    if table_exists:
      migrate_legacy_database(database)
    create_database_schema(database)


def serialize_record(record):
  value = copy.deepcopy(record)
  value["start"] = record["start"].isoformat()
  value["end"] = record["end"].isoformat()
  value["periods"] = [
    {"start": period["start"].isoformat(), "end": period["end"].isoformat()}
    for period in record_periods(record)
  ]
  return json.dumps(value, ensure_ascii=False, default=str)


def deserialize_record(payload):
  record = json.loads(payload)
  record["start"] = parse_aw_time(record["start"])
  record["end"] = parse_aw_time(record["end"])
  record["periods"] = [
    {"start": parse_aw_time(period["start"]), "end": parse_aw_time(period["end"])}
    for period in record.get("periods", [])
  ]
  return record


def save_report(path, day, records, config_path, provider="", prompt="", source="generated", parent_id=None):
  path = expand_path(path)
  initialize_database(path)
  now = dt.datetime.now(dt.timezone.utc).isoformat()
  with sqlite3.connect(path) as database:
    revision = database.execute(
      "SELECT COALESCE(MAX(revision), 0) + 1 FROM reports WHERE day = ?", (day.isoformat(),)
    ).fetchone()[0]
    database.execute("UPDATE reports SET enabled = 0 WHERE day = ?", (day.isoformat(),))
    cursor = database.execute(
      "INSERT INTO reports(day, revision, created_at, config_path, ai_provider, prompt, source, parent_id, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
      (day.isoformat(), revision, now, config_path, provider or None, prompt or None, source, parent_id),
    )
    report_id = cursor.lastrowid
    for position, record in enumerate(records):
      database.execute(
        "INSERT INTO records(report_id, position, project, subject, description, confidence, minutes, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
          report_id, position, record.get("project", "unassigned"), record.get("subject", ""),
          record.get("description", "review needed"), record.get("confidence", "unknown"),
          record_minutes(record), serialize_record(record),
        ),
      )
      for period_position, period in enumerate(record_periods(record)):
        database.execute(
          "INSERT INTO periods(report_id, record_position, position, start, end) VALUES (?, ?, ?, ?, ?)",
          (report_id, position, period_position, period["start"].isoformat(), period["end"].isoformat()),
        )
  return report_id


def load_report(path, day=None, report_id=None):
  path = expand_path(path)
  if not os.path.exists(path):
    return None
  initialize_database(path)
  with sqlite3.connect(path) as database:
    if report_id is not None:
      report = database.execute(
        "SELECT id, day, revision, created_at, config_path, ai_provider, prompt, source, parent_id, enabled FROM reports WHERE id = ?",
        (report_id,),
      ).fetchone()
    else:
      report = database.execute(
        "SELECT id, day, revision, created_at, config_path, ai_provider, prompt, source, parent_id, enabled FROM reports WHERE day = ? ORDER BY id DESC LIMIT 1",
        (day.isoformat(),),
      ).fetchone()
    if not report:
      return None
    rows = database.execute(
      "SELECT payload_json FROM records WHERE report_id = ? ORDER BY position", (report[0],)
    ).fetchall()
  return {
    "id": report[0],
    "day": report[1],
    "revision": report[2],
    "created_at": report[3],
    "config_path": report[4],
    "provider": report[5] or "",
    "prompt": report[6] or "",
    "source": report[7],
    "parent_id": report[8],
    "enabled": bool(report[9]),
    "records": [deserialize_record(row[0]) for row in rows],
  }


def list_reports(path, day):
  path = expand_path(path)
  initialize_database(path)
  with sqlite3.connect(path) as database:
    rows = database.execute("""
      SELECT reports.id, reports.revision, reports.created_at, reports.source,
             reports.ai_provider, reports.prompt, reports.enabled,
             COUNT(records.position), COALESCE(SUM(records.minutes), 0)
      FROM reports
      LEFT JOIN records ON records.report_id = reports.id
      WHERE reports.day = ?
      GROUP BY reports.id
      ORDER BY reports.id DESC
    """, (day.isoformat(),)).fetchall()
  return [
    {
      "id": row[0], "revision": row[1], "created_at": row[2], "source": row[3],
      "provider": row[4] or "", "prompt": row[5] or "", "enabled": bool(row[6]),
      "entries": row[7], "minutes": row[8],
    }
    for row in rows
  ]


def enable_report(path, report_id):
  path = expand_path(path)
  initialize_database(path)
  with sqlite3.connect(path) as database:
    report = database.execute("SELECT day FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not report:
      return None
    database.execute("UPDATE reports SET enabled = 0 WHERE day = ?", (report[0],))
    database.execute("UPDATE reports SET enabled = 1 WHERE id = ?", (report_id,))
  return report[0]


def merge_periods(periods):
  merged = []
  for source in sorted(periods, key=lambda item: item["start"]):
    period = copy.deepcopy(source)
    if merged and period["start"] <= merged[-1]["end"]:
      merged[-1]["end"] = max(merged[-1]["end"], period["end"])
    else:
      merged.append(period)
  return merged


def summarize_day_records(records):
  """Collapse a day's intervals into one summary per project and record kind.

  Exact periods remain attached so gaps and project totals are not inflated by the
  first-to-last envelope.
  """
  grouped = {}
  order = []
  for index, source in enumerate(sorted(records, key=lambda item: item["start"])):
    kind = "break" if source.get("description_source") == "configured_break" else "work"
    project = source.get("project", "unassigned")
    key = (project, kind, index if project == "unassigned" else None)
    if key not in grouped:
      target = copy.deepcopy(source)
      target["periods"] = []
      target["subject"] = ""
      target["subject_confidence"] = "unknown"
      if kind == "work":
        target["description"] = ""
        target.pop("description_source", None)
        target.pop("description_confidence", None)
      grouped[key] = target
      order.append(key)
    target = grouped[key]
    target["periods"].extend(copy.deepcopy(record_periods(source)))
    merge_evidence(target, source)
    add_evidence(target, "subjects", source.get("subject"))

  summaries = []
  for key in order:
    record = grouped[key]
    record["periods"] = merge_periods(record["periods"])
    record["start"] = record["periods"][0]["start"]
    record["end"] = record["periods"][-1]["end"]
    subjects = record["evidence"].get("subjects", [])
    if key[1] == "break":
      record["subject"] = "coffee breaks" if len(subjects) > 1 else first_value(*subjects)
      record["description"] = "coffee break"
      record["description_source"] = "configured_break"
      record["description_confidence"] = "high"
    elif subjects:
      record["subject"] = "; ".join(subjects[:3])
      record["subject_confidence"] = "medium"
    summaries.append(record)
  return sorted(summaries, key=lambda item: item["start"])


def repository_key(value):
  return os.path.realpath(value) if value and os.path.isabs(value) else str(value or "")


def discovered_repositories(records, config):
  identities = {}
  for record in records:
    for path in record.get("evidence", {}).get("repositories", []) + record.get("evidence", {}).get("worktrees", []):
      identity = git_identity(path)
      if identity:
        identities[repository_key(identity["repository"])] = identity
  for rule in project_rules(config):
    for path in rule["path_prefixes"]:
      identity = git_identity(path)
      if identity:
        identity["project"] = rule["name"]
        identities[repository_key(identity["repository"])] = identity
  return list(identities.values())


def _configured_authors(config, repository):
  authors = set(lower_values(config.get("git", {}).get("authors", [])))
  for key in ["user.email", "user.name"]:
    value = run_git(repository, ["config", "--get", key])
    if value:
      authors.add(value.casefold())
  return authors


def query_git_commits(identity, start, end, config):
  margin = int(config.get("git", {}).get("query_margin_minutes", 30))
  since = (start - dt.timedelta(minutes=margin)).astimezone(dt.timezone.utc).isoformat()
  until = (end + dt.timedelta(minutes=margin)).astimezone(dt.timezone.utc).isoformat()
  repository = identity["repository"]
  output = run_git(repository, [
    "log", "--all", f"--since={since}", f"--until={until}",
    "--format=%H%x1f%s%x1f%P%x1f%an%x1f%ae%x1f%aI%x1f%cI",
  ], timeout=int(config.get("git", {}).get("timeout_seconds", 5)))
  reflog = set(run_git(repository, ["reflog", f"--since={since}", f"--until={until}", "--format=%H"]).splitlines())
  authors = _configured_authors(config, repository)
  commits = []
  for line in output.splitlines():
    fields = line.split("\x1f")
    if len(fields) != 7:
      continue
    commit_hash, subject, parents, author_name, author_email, authored, committed = fields
    local = commit_hash in reflog or author_name.casefold() in authors or author_email.casefold() in authors
    try:
      timestamp = parse_aw_time(committed)
    except ValueError:
      continue
    commits.append({
      "hash": commit_hash,
      "subject": subject,
      "parents": parents.split() if parents else [],
      "author_timestamp": authored,
      "committer_timestamp": committed,
      "timestamp": timestamp,
      "repository": repository,
      "worktree": identity.get("worktree", ""),
      "branch": "",
      "worktree_branch_context": identity.get("branch", ""),
      "remote": identity.get("remote", ""),
      "local": local,
      "sources": ["git_log"],
    })
  return commits


def commits_from_aw(events):
  commits = []
  for event in events:
    data = event["data"]
    if data.get("kind") != "commit" or not data.get("hash"):
      continue
    commits.append({
      "hash": str(data["hash"]),
      "subject": str(data.get("subject", "")),
      "parents": list(data.get("parents", [])),
      "timestamp": event["start"],
      "repository": str(data.get("repository", "")),
      "worktree": str(data.get("worktree", "")),
      "branch": str(data.get("branch", "")),
      "remote": sanitize_remote(data.get("remote", "")),
      "local": True,
      "sources": ["activitywatch"],
    })
  return commits


def deduplicate_commits(commits):
  merged = {}
  for commit in commits:
    repository = repository_key(commit.get("repository")) or sanitize_remote(commit.get("remote"))
    key = (repository, commit.get("hash"))
    if key not in merged:
      merged[key] = copy.deepcopy(commit)
      continue
    existing = merged[key]
    for source in commit.get("sources", []):
      if source not in existing["sources"]:
        existing["sources"].append(source)
    for field in ["subject", "parents", "branch", "worktree", "remote"]:
      if not existing.get(field) and commit.get(field):
        existing[field] = copy.deepcopy(commit[field])
    existing["local"] = existing.get("local", False) or commit.get("local", False)
  for commit in merged.values():
    commit["found_in_current_history"] = "git_log" in commit.get("sources", [])
  return list(merged.values())


def _record_repository_matches(record, commit, project_repositories):
  commit_repository = repository_key(commit.get("repository"))
  repositories = {repository_key(value) for value in record["evidence"].get("repositories", [])}
  if commit_repository in repositories:
    return True
  project_candidates = project_repositories.get(record.get("project"), set())
  if len(project_candidates) == 1 and commit_repository in project_candidates:
    add_evidence(record, "repositories", commit["repository"])
    return True
  return False


def correlate_commits(records, commits, identities, config):
  margin = dt.timedelta(minutes=int(config.get("git", {}).get("correlation_margin_minutes", 15)))
  project_repositories = {}
  for identity in identities:
    if identity.get("project"):
      project_repositories.setdefault(identity["project"], set()).add(repository_key(identity["repository"]))
  for commit in commits:
    if not commit.get("local"):
      continue
    timestamp = commit["timestamp"]
    candidates = []
    for record in records:
      if not _record_repository_matches(record, commit, project_repositories):
        continue
      period_scores = []
      for period in record_periods(record):
        if timestamp < period["start"] - margin or timestamp > period["end"] + margin:
          continue
        inside = period["start"] <= timestamp <= period["end"]
        distance = 0 if inside else min(abs((timestamp - period["start"]).total_seconds()), abs((timestamp - period["end"]).total_seconds()))
        period_scores.append((1 if inside else 0, -distance))
      if not period_scores:
        continue
      branches = record["evidence"].get("branches", [])
      if branches and commit.get("branch") and commit["branch"] not in branches:
        continue
      candidates.append((max(period_scores), record))
    if not candidates:
      continue
    record = max(candidates, key=lambda item: item[0])[1]
    evidence = {key: value for key, value in commit.items() if key != "timestamp"}
    evidence["timestamp"] = timestamp.isoformat()
    add_evidence(record, "commits", evidence)


def enrich_with_git(records, aw_git_events, start, end, config):
  identities = discovered_repositories(records, config)
  commits = commits_from_aw(aw_git_events)
  for identity in identities:
    commits.extend(query_git_commits(identity, start, end, config))
  commits = deduplicate_commits(commits)
  correlate_commits(records, commits, identities, config)
  return commits


def friendly_text(value):
  text = re.sub(r"\.(md|txt|py|js|ts|tsx|cs|toml|json|yaml|yml)$", "", value, flags=re.I)
  text = text.replace("--", " ").replace("_", " ").replace("-", " ").strip()
  text = re.sub(r"\s+", " ", text)
  text = re.sub(r"\baw\b", "ActivityWatch", text, flags=re.I)
  return text


def branch_subject(branch):
  branch = str(branch or "").strip()
  match = re.match(r"^(feature|feat|fix|bugfix|hotfix|chore|docs|refactor)/(.+)$", branch, re.I)
  kind = match.group(1).lower() if match else ""
  value = match.group(2) if match else branch
  return value, kind


def derive_subject(record):
  if record.get("subject"):
    return
  branches = record["evidence"].get("branches", [])
  if branches:
    value, _ = branch_subject(branches[0])
    record["subject"] = value
    record["subject_confidence"] = "medium"
    add_attribution(record, "subject", "git_branch", value, "medium")
    return
  repositories = {os.path.basename(path.rstrip(os.sep)) for path in record["evidence"].get("repositories", [])}
  for worktree in record["evidence"].get("worktrees", []):
    name = os.path.basename(worktree.rstrip(os.sep))
    for repository in repositories:
      prefix = repository + "."
      if name.startswith(prefix) and len(name) > len(prefix):
        value = name[len(prefix):]
        record["subject"] = value
        record["subject_confidence"] = "medium"
        add_attribution(record, "subject", "worktree_suffix", value, "medium")
        return


def _commit_description(commits):
  subjects = []
  for commit in commits:
    subject = str(commit.get("subject", "")).strip()
    if subject and subject not in subjects:
      subjects.append(subject)
  if not subjects:
    return ""
  if len(subjects) == 1:
    return subjects[0]
  implementation = None
  tested = None
  for subject in subjects:
    implementation_match = re.match(r"^(?:add|implement|create|build)\s+(.+)$", subject, re.I)
    test_match = re.match(r"^(?:add|write|update)\s+(?:tests?|testing)\s+(?:for\s+)?(.+)$", subject, re.I)
    if implementation_match:
      implementation = implementation_match.group(1)
    if test_match:
      tested = test_match.group(1)
  if implementation and tested and (implementation.casefold() in tested.casefold() or tested.casefold() in implementation.casefold()):
    subject = implementation if len(implementation) <= len(tested) else tested
    return f"Implement and test {subject}"
  return "; ".join(subjects[:3])


def _strong_title_description(record):
  project = record.get("project", "")
  ignored = set(app_aliases({})["work"]) | set(app_aliases({})["noise"]) | {project.casefold()}
  for title in record["evidence"].get("titles", []):
    pieces = [piece.strip() for piece in re.split(r"\s+[—–|-]\s+", title) if piece.strip()]
    for piece in pieces:
      if piece.casefold() in ignored or piece.casefold() == project.casefold():
        continue
      basename = os.path.basename(piece)
      pitch = re.match(r"pitch--(.+)\.md$", basename, re.I)
      if pitch:
        return f"Review {friendly_text(pitch.group(1))} pitch"
      if re.search(r"\.(md|txt)$", basename, re.I):
        return f"Review {friendly_text(basename)}"
  return ""


def generate_descriptions(records):
  for record in records:
    if record.get("description_source") == "configured_break":
      continue
    derive_subject(record)
    commits = record["evidence"].get("commits", [])
    description = _commit_description(commits)
    if description:
      source, confidence = "git_commit", "high"
    elif record["evidence"].get("descriptions"):
      description = record["evidence"]["descriptions"][0]
      source, confidence = "activitywatch_description", "high"
    elif any("/pull/" in url for url in record["evidence"].get("urls", [])) and record["evidence"].get("titles"):
      description = f"Review pull request: {record['evidence']['titles'][-1]}"
      source, confidence = "web_pull_request", "high"
    else:
      description = _strong_title_description(record)
      source, confidence = ("window_title", "medium") if description else ("", "")
    if not description and record.get("subject"):
      branch = record["evidence"].get("branches", [""])[0] if record["evidence"].get("branches") else ""
      _, kind = branch_subject(branch)
      subject_parts = [friendly_text(value) for value in record["evidence"].get("subjects", [])]
      if not subject_parts:
        subject_parts = [friendly_text(record["subject"])]
      if len(subject_parts) == 1:
        subject = subject_parts[0]
      else:
        subject = ", ".join(subject_parts[:-1]) + " and " + subject_parts[-1]
      suffix = " feature" if len(subject_parts) == 1 and kind in {"feature", "feat"} else " fix" if len(subject_parts) == 1 and kind in {"fix", "bugfix", "hotfix"} else ""
      description = f"Work on {subject}{suffix}"
      source, confidence = "branch_or_worktree", "medium"
    if not description and record.get("project") != "unassigned":
      description = f"Development in {record['project']}"
      source, confidence = "canonical_project", "medium"
    if not description:
      description, source, confidence = "review needed", "insufficient_evidence", "low"
    record["description"] = description
    record["description_source"] = source
    record["description_confidence"] = confidence
    add_attribution(record, "description", source, description, confidence)


def quality_metrics(records):
  metrics = {"total": 0, "assigned": 0, "unassigned": 0, "described": 0, "review": 0, "high": 0, "medium": 0, "low": 0, "projects": {}}
  for record in records:
    minutes = record_minutes(record)
    metrics["total"] += minutes
    project = record.get("project", "unassigned")
    metrics["projects"][project] = metrics["projects"].get(project, 0) + minutes
    metrics["assigned" if record.get("project") != "unassigned" else "unassigned"] += minutes
    metrics["review" if record.get("description") == "review needed" else "described"] += minutes
    confidence = record.get("confidence", "low")
    metrics[confidence if confidence in {"high", "medium", "low"} else "low"] += minutes
  return metrics


def _redacted_ai_evidence(record, config, prefix=""):
  include_paths = bool(config.get("include_paths", True))
  include_urls = bool(config.get("include_urls", False))
  include_titles = bool(config.get("include_titles", True))
  include_commits = bool(config.get("include_commit_subjects", True))
  supplied = []
  counter = 1
  for key, values in record.get("evidence", {}).items():
    if key in {"paths", "repositories", "worktrees"} and not include_paths:
      continue
    if key == "urls" and not include_urls:
      continue
    if key == "titles" and not include_titles:
      continue
    if key == "commits" and not include_commits:
      continue
    for value in values:
      if key == "commits" and isinstance(value, dict):
        value = {field: value.get(field) for field in ["hash", "subject", "branch", "sources"] if value.get(field)}
      if key == "urls":
        value = sanitize_url(value)
      supplied.append({"id": f"{prefix}e{counter}", "type": key, "value": value})
      counter += 1
  return supplied


def build_ai_payload(records, ai_config, config=None, force_candidates=False):
  minimum = int(ai_config.get("minimum_minutes", 15))
  payload_records = []
  canonical_projects = set()
  for index, record in enumerate(records):
    if record.get("description_source") == "configured_break":
      continue
    minutes = record_minutes(record)
    weak = record.get("description") == "review needed" or record.get("description_confidence") == "low"
    complex_evidence = len(record.get("evidence", {}).get("commits", [])) > 1
    project_is_weak = CONFIDENCE_RANK.get(record.get("confidence", "unknown"), 0) < CONFIDENCE_RANK["high"]
    candidate = minutes >= minimum and (force_candidates or weak or complex_evidence or project_is_weak)
    if record.get("project") != "unassigned" and record.get("confidence") == "high":
      canonical_projects.add(record["project"])
    payload_records.append({
      "index": index,
      "candidate": candidate,
      "project": record.get("project"),
      "project_confidence": record.get("confidence"),
      "subject": record.get("subject"),
      "description": record.get("description"),
      "minutes": minutes,
      "periods": [
        {"start": period["start"].strftime("%H:%M"), "end": period["end"].strftime("%H:%M")}
        for period in record_periods(record)
      ],
      "evidence": _redacted_ai_evidence(record, ai_config, f"r{index}"),
    })
  aliases = configured_project_aliases(config or {})
  return {
    "canonical_projects": sorted(canonical_projects),
    "known_project_aliases": {item["alias"]: item["project"] for item in aliases.values()},
    "records": payload_records,
  }


def _ai_prompt(payload, custom_prompt=""):
  refinement = f"\nUser refinement request:\n{custom_prompt.strip()}\n" if custom_prompt.strip() else ""
  return """Canonicalize related projects and improve daily time-record descriptions using only supplied evidence.
Recognize product/repository aliases such as a solution or application name referring to an existing canonical project. Prefer a supplied canonical project over inventing a new project. Records marked candidate=false are context: do not suggest changes for them.
Return strict JSON only with this shape:
{\"suggestions\":[{\"index\":0,\"subject\":\"\",\"description\":\"\",\"project\":\"\",\"confidence\":\"low|medium|high\",\"evidence_ids\":[\"r0e1\"]}],\"project_aliases\":[{\"alias\":\"Wydler.Crm\",\"project\":\"wam-crm\",\"confidence\":\"high\",\"evidence_ids\":[\"r0e1\"]}],\"project_summaries\":[{\"project\":\"wam-crm\",\"subject\":\"\",\"description\":\"\",\"confidence\":\"high\",\"evidence_ids\":[\"r0e1\"]}]}.
Do not alter, merge, or suggest times. Cite supplied evidence IDs for every item. Only propose a reusable alias when the evidence explicitly contains the alias and strongly supports the canonical project. Be conservative and action-oriented.
""" + refinement + "\nPayload:\n" + json.dumps(payload, ensure_ascii=False)


def run_streaming(command, timeout, capture_output=True):
  print(f"AI: starting {command[0]}...", file=sys.stderr)
  process = subprocess.Popen(
    command, stdout=subprocess.PIPE, stderr=None, bufsize=0,
  )
  output = []
  started = dt.datetime.now()
  try:
    while True:
      if (dt.datetime.now() - started).total_seconds() > timeout:
        process.kill()
        raise subprocess.TimeoutExpired(command, timeout)
      readable, _, _ = select.select([process.stdout], [], [], 0.2)
      if readable:
        chunk = os.read(process.stdout.fileno(), 4096)
        if chunk:
          output.append(chunk)
          print(chunk.decode("utf-8", errors="replace"), end="", file=sys.stderr, flush=True)
          continue
      if process.poll() is not None:
        break
    process.wait(timeout=1)
  finally:
    if process.poll() is None:
      process.kill()
    process.stdout.close()
  print(file=sys.stderr)
  if process.returncode != 0:
    raise RuntimeError(f"{command[0]} exited with status {process.returncode}")
  return b"".join(output).decode("utf-8") if capture_output else ""


def run_pi_json_stream(command, timeout):
  print("AI: starting pi...", file=sys.stderr, flush=True)
  print("Pi: analyzing time-tracking evidence...", file=sys.stderr, flush=True)
  process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=None, bufsize=0)
  started = dt.datetime.now()
  last_progress = started
  buffer = b""
  response_parts = []
  channel = ""

  def handle_line(raw_line):
    nonlocal channel
    try:
      event = json.loads(raw_line)
    except json.JSONDecodeError:
      return
    update = event.get("assistantMessageEvent", {})
    event_type = update.get("type", "")
    delta = update.get("delta", "")
    if not delta:
      return
    if event_type == "thinking_delta":
      if channel != "thinking":
        print("\nPi reasoning:", file=sys.stderr, flush=True)
        channel = "thinking"
      print(delta, end="", file=sys.stderr, flush=True)
    elif event_type == "text_delta":
      if channel != "response":
        print("\nPi response:", file=sys.stderr, flush=True)
        channel = "response"
      response_parts.append(delta)
      print(delta, end="", file=sys.stderr, flush=True)

  try:
    while True:
      now = dt.datetime.now()
      if (now - started).total_seconds() > timeout:
        process.kill()
        raise subprocess.TimeoutExpired(command, timeout)
      if (now - last_progress).total_seconds() >= 5 and not response_parts and not channel:
        print(f"Pi: still working ({int((now - started).total_seconds())}s)...", file=sys.stderr, flush=True)
        last_progress = now
      readable, _, _ = select.select([process.stdout], [], [], 0.2)
      if readable:
        chunk = os.read(process.stdout.fileno(), 65536)
        if chunk:
          buffer += chunk
          while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            if line:
              handle_line(line.decode("utf-8", errors="replace"))
          continue
      if process.poll() is not None:
        if buffer.strip():
          handle_line(buffer.decode("utf-8", errors="replace"))
        break
    process.wait(timeout=1)
  finally:
    if process.poll() is None:
      process.kill()
    process.stdout.close()
  print("\nPi: finished. Applying validated suggestions...", file=sys.stderr, flush=True)
  if process.returncode != 0:
    raise RuntimeError(f"pi exited with status {process.returncode}")
  response = "".join(response_parts).strip()
  if not response:
    raise RuntimeError("pi returned no final response")
  return response


def invoke_ai(provider, payload, timeout, custom_prompt="", thinking_level="medium"):
  prompt = _ai_prompt(payload, custom_prompt)
  if provider == "pi":
    command = [
      "pi", "--mode", "json", "--no-session", "--no-tools", "--no-extensions",
      "--no-skills", "--no-context-files", "--thinking", thinking_level, prompt,
    ]
    return json.loads(run_pi_json_stream(command, timeout))
  if provider == "codex":
    with tempfile.TemporaryDirectory(prefix="lowr-time-tracker-") as temp_dir:
      output_path = os.path.join(temp_dir, "response.json")
      command = ["codex", "exec", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check", "--output-last-message", output_path, prompt]
      run_streaming(command, timeout, capture_output=False)
      with open(output_path, encoding="utf-8") as response_file:
        return json.load(response_file)
  raise ValueError(f"Unsupported AI provider: {provider}")


def _payload_evidence(payload):
  return {
    item["id"]: item["value"]
    for record in payload.get("records", [])
    for item in record.get("evidence", [])
  }


def apply_ai_suggestions(records, payload, response, ai_config):
  payload_by_index = {item["index"]: item for item in payload["records"]}
  canonical_projects = set(payload.get("canonical_projects", []))
  canonical_projects.update(item.get("project") for item in payload["records"] if item.get("project") != "unassigned")
  suggestions = response.get("suggestions", []) if isinstance(response, dict) else []
  changes = []
  for suggestion in suggestions:
    if not isinstance(suggestion, dict) or suggestion.get("index") not in payload_by_index:
      continue
    index = suggestion["index"]
    payload_record = payload_by_index[index]
    if not payload_record.get("candidate"):
      continue
    allowed_ids = {item["id"] for item in payload_record["evidence"]}
    cited_ids = set(suggestion.get("evidence_ids", []))
    confidence = suggestion.get("confidence")
    if not cited_ids or not cited_ids <= allowed_ids or confidence not in {"low", "medium", "high"}:
      continue
    record = records[index]
    description = str(suggestion.get("description", "")).strip()
    subject = str(suggestion.get("subject", "")).strip()
    project = str(suggestion.get("project", "")).strip()
    if description and description != record.get("description"):
      record["description"] = description
      record["description_source"] = "ai"
      record["_ai_updated"] = True
      record["description_confidence"] = confidence
      add_attribution(record, "description", "ai", description, confidence)
    if subject and subject != record.get("subject"):
      record["subject"] = subject
      record["_ai_updated"] = True
      add_attribution(record, "subject", "ai", subject, confidence)
    if not project or not ai_config.get("allow_project_suggestion", True) or project == record["project"]:
      continue
    current = record["project"]
    current_rank = CONFIDENCE_RANK.get(record.get("confidence", "unknown"), 0)
    can_assign = current == "unassigned" and confidence in {"medium", "high"}
    can_alias = current != "unassigned" and current_rank < CONFIDENCE_RANK["high"] and confidence == "high" and project in canonical_projects
    if can_assign or can_alias:
      record["project"] = project
      record["confidence"] = confidence
      record["_ai_updated"] = True
      add_attribution(record, "project", "ai_suggestion", project, confidence)
      changes.append({"alias": current if current != "unassigned" else "", "project": project, "confidence": confidence, "evidence_ids": sorted(cited_ids)})
  return changes


def validated_ai_aliases(payload, response, changes):
  evidence = _payload_evidence(payload)
  known_projects = {item.get("project") for item in payload.get("records", []) if item.get("project") != "unassigned"}
  known_projects.update(change["project"] for change in changes)
  candidates = list(changes)
  if isinstance(response, dict):
    candidates.extend(response.get("project_aliases", []))
  aliases = []
  for candidate in candidates:
    if not isinstance(candidate, dict):
      continue
    alias = str(candidate.get("alias", "")).strip()
    project = str(candidate.get("project", "")).strip()
    cited_ids = set(candidate.get("evidence_ids", []))
    if not alias or alias == "unassigned" or not project or project not in known_projects:
      continue
    if candidate.get("confidence") != "high" or not cited_ids or not cited_ids <= set(evidence):
      continue
    supplied_text = "\n".join(json.dumps(evidence[item], ensure_ascii=False) for item in cited_ids).casefold()
    if alias.casefold() not in supplied_text and not any(change.get("alias", "").casefold() == alias.casefold() for change in changes):
      continue
    aliases.append({"alias": alias, "project": project, "confidence": "high", "evidence_ids": sorted(cited_ids)})
  unique = {}
  for item in aliases:
    unique[item["alias"].casefold()] = item
  return list(unique.values())


def persist_project_aliases(config, aliases):
  if not aliases:
    return
  path = config.get("_memory_path") or tracker_memory_path(config)
  memory = {"version": 1, "project_aliases": {}}
  if os.path.exists(path):
    try:
      with open(path, encoding="utf-8") as memory_file:
        loaded = json.load(memory_file)
      if isinstance(loaded, dict):
        memory.update(loaded)
    except (OSError, json.JSONDecodeError):
      pass
  stored = memory.setdefault("project_aliases", {})
  configured = configured_project_aliases(config)
  explicit_aliases = {str(alias).casefold() for alias in config.get("project_aliases", {})}
  for item in aliases:
    key = item["alias"]
    existing = configured.get(key.casefold())
    if key.casefold() in explicit_aliases:
      continue
    if existing and existing["project"] != item["project"]:
      continue
    stored_item = next((value for alias, value in stored.items() if alias.casefold() == key.casefold()), None)
    if isinstance(stored_item, dict) and stored_item.get("project") == item["project"]:
      continue
    stored[key] = {
      "project": item["project"],
      "confidence": "high",
      "learned_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    config.setdefault("_learned_project_aliases", {})[key] = item["project"]
  os.makedirs(os.path.dirname(path), exist_ok=True)
  descriptor, temporary = tempfile.mkstemp(prefix=".time-tracker-memory-", dir=os.path.dirname(path), text=True)
  try:
    with os.fdopen(descriptor, "w", encoding="utf-8") as memory_file:
      json.dump(memory, memory_file, indent=2, ensure_ascii=False, sort_keys=True)
      memory_file.write("\n")
    os.replace(temporary, path)
  finally:
    if os.path.exists(temporary):
      os.unlink(temporary)


def apply_ai_project_summaries(records, payload, response):
  evidence_ids = set(_payload_evidence(payload))
  summaries = response.get("project_summaries", []) if isinstance(response, dict) else []
  for summary in summaries:
    if not isinstance(summary, dict):
      continue
    project = str(summary.get("project", "")).strip()
    confidence = summary.get("confidence")
    cited_ids = set(summary.get("evidence_ids", []))
    if confidence not in {"medium", "high"} or not cited_ids or not cited_ids <= evidence_ids:
      continue
    record = next((item for item in records if item.get("project") == project and item.get("description_source") != "configured_break"), None)
    if not record:
      continue
    subject = str(summary.get("subject", "")).strip()
    description = str(summary.get("description", "")).strip()
    if subject and subject != record.get("subject"):
      record["subject"] = subject
      record["_ai_updated"] = True
      add_attribution(record, "subject", "ai_project_summary", subject, confidence)
    if description and description != record.get("description"):
      record["description"] = description
      record["_ai_updated"] = True
      record["description_source"] = "ai_project_summary"
      record["description_confidence"] = confidence
      add_attribution(record, "description", "ai_project_summary", description, confidence)


def process_ai(records, args, config, custom_prompt="", force_candidates=False):
  ai_config = config.get("ai", {})
  provider = args.describe_with or ai_config.get("provider", "pi")
  enabled = (bool(args.describe_with) or bool(ai_config.get("enabled", False)) or force_candidates) and not args.no_ai
  payload = build_ai_payload(records, ai_config, config, force_candidates)
  if args.ai_dry_run:
    print("ai_payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return records
  if not enabled or not any(item.get("candidate") for item in payload["records"]):
    return records
  if provider not in {"pi", "codex"}:
    print(f"AI descriptions skipped: unsupported provider {provider}", file=sys.stderr)
    return records
  if shutil.which(provider) is None:
    print(f"AI descriptions skipped: {provider} is not installed", file=sys.stderr)
    return records
  try:
    response = invoke_ai(
      provider, payload, int(ai_config.get("timeout_seconds", 60)), custom_prompt,
      str(ai_config.get("thinking_level", "medium")),
    )
    changes = apply_ai_suggestions(records, payload, response, ai_config)
    updated_projects = {record["project"] for record in records if record.pop("_ai_updated", False)}
    aliases = validated_ai_aliases(payload, response, changes)
    if aliases and not args.no_learn and ai_config.get("learn_project_aliases", True):
      persist_project_aliases(config, aliases)
    if changes:
      ai_descriptions = {}
      for record in records:
        if record.get("description_source") == "ai":
          ai_descriptions.setdefault(record["project"], []).append(record["description"])
      records = summarize_day_records(records)
      generate_descriptions(records)
      for record in records:
        if record["project"] in updated_projects:
          record["_ai_updated"] = True
        descriptions = list(dict.fromkeys(ai_descriptions.get(record["project"], [])))
        if descriptions:
          record["description"] = "; ".join(descriptions)
          record["description_source"] = "ai"
          record["description_confidence"] = "medium"
    else:
      for record in records:
        if record["project"] in updated_projects:
          record["_ai_updated"] = True
    apply_ai_project_summaries(records, payload, response)
    updated = sum(1 for record in records if record.pop("_ai_updated", False))
    if updated:
      print(f"Pi: updated {updated} time-tracking record(s).", file=sys.stderr, flush=True)
    else:
      print("Pi: returned no accepted record changes.", file=sys.stderr, flush=True)
    return records
  except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
    print(f"AI descriptions skipped: {error}", file=sys.stderr)
    return records


def yaml_scalar(value):
  return json.dumps(str(value), ensure_ascii=False)


def table_text(value):
  return re.sub(r"\s+", " ", str(value or "")).strip().replace("|", "\\|")


def format_duration(minutes):
  hours, remaining = divmod(int(minutes), 60)
  if hours and remaining:
    return f"{hours}h {remaining}m"
  if hours:
    return f"{hours}h"
  return f"{remaining}m"


def allocated_period_minutes(record):
  periods = record_periods(record)
  exact = [(period["end"] - period["start"]).total_seconds() / 60 for period in periods]
  allocated = [int(value) for value in exact]
  remaining = record_minutes(record) - sum(allocated)
  fractions = sorted(range(len(exact)), key=lambda index: exact[index] - allocated[index], reverse=True)
  for index in fractions[:max(remaining, 0)]:
    allocated[index] += 1
  return allocated


def chronological_rows(records):
  rows = []
  for record in records:
    minutes = allocated_period_minutes(record)
    for index, period in enumerate(record_periods(record)):
      rows.append({
        "start": period["start"],
        "end": period["end"],
        "minutes": minutes[index],
        "project": record.get("project", "unassigned"),
        "subject": record.get("subject", ""),
        "description": record.get("description", "review needed"),
      })
  return sorted(rows, key=lambda item: (item["start"], item["end"], item["project"]))


def render_aligned_table(headers, rows, widths, right_aligned=None):
  right_aligned = set(right_aligned or [])
  border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

  def render_cells(cells, header=False):
    wrapped = []
    for value, width in zip(cells, widths):
      lines = textwrap.wrap(table_text(value), width=width, break_long_words=True, break_on_hyphens=False) or [""]
      wrapped.append(lines)
    for line_index in range(max(len(lines) for lines in wrapped)):
      values = []
      for column, (lines, width) in enumerate(zip(wrapped, widths)):
        value = lines[line_index] if line_index < len(lines) else ""
        if header:
          values.append(value.center(width))
        elif column in right_aligned:
          values.append(value.rjust(width))
        else:
          values.append(value.ljust(width))
      print("| " + " | ".join(values) + " |")

  print(border)
  render_cells(headers, header=True)
  print(border)
  for row in rows:
    render_cells(row)
  print(border)


def print_table(day, records, config_path, show_quality=True, report_info=None):
  print(f"Time records for {day.isoformat()}")
  if report_info:
    status = "enabled" if report_info["enabled"] else "not enabled"
    print(f"Report: #{report_info['id']} (revision {report_info['revision']}, {report_info['source']}, {status})")
  print(f"Config: {config_path}")
  print()

  terminal_width = max(120, min(shutil.get_terminal_size(fallback=(160, 24)).columns, 200))
  fixed_width = 5 + 5 + 8 + 28 + 28
  table_overhead = 19
  description_width = max(30, terminal_width - fixed_width - table_overhead)
  rows = [
    [
      row["start"].strftime("%H:%M"),
      row["end"].strftime("%H:%M"),
      format_duration(row["minutes"]),
      row["project"],
      row["subject"],
      row["description"],
    ]
    for row in chronological_rows(records)
  ]
  render_aligned_table(
    ["Start", "End", "Duration", "Project", "Subject", "Description"],
    rows,
    [5, 5, 8, 28, 28, description_width],
    right_aligned={0, 1, 2},
  )

  metrics = quality_metrics(records)
  print()
  print("Project totals")
  print()
  first_seen = []
  for row in chronological_rows(records):
    if row["project"] not in first_seen:
      first_seen.append(row["project"])
  total_rows = []
  for project in first_seen:
    minutes = metrics["projects"].get(project, 0)
    total_rows.append([project, format_duration(minutes), minutes])
  total_rows.append(["OVERALL", format_duration(metrics["total"]), metrics["total"]])
  render_aligned_table(["Project", "Duration", "Minutes"], total_rows, [30, 10, 8], right_aligned={1, 2})

  if show_quality:
    print()
    print(
      f"Assigned: {metrics['assigned']}m | Unassigned: {metrics['unassigned']}m | "
      f"Review needed: {metrics['review']}m"
    )


def print_report_versions(day, versions):
  print(f"Stored reports for {day.isoformat()}")
  print()
  if not versions:
    print("No stored reports.")
    return
  rows = []
  for version in versions:
    created = parse_aw_time(version["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
    rows.append([
      version["id"],
      "yes" if version["enabled"] else "",
      version["revision"],
      created,
      version["source"],
      version["provider"],
      version["entries"],
      format_duration(version["minutes"]),
      version["prompt"],
    ])
  render_aligned_table(
    ["ID", "Enabled", "Rev", "Created", "Source", "AI", "Rows", "Duration", "Prompt"],
    rows,
    [6, 7, 4, 19, 18, 8, 5, 10, 35],
    right_aligned={0, 2, 6, 7},
  )


def print_records(day, records, config_path, show_evidence=False, show_quality=True, report_info=None):
  print(f"date: {day.isoformat()}")
  if report_info:
    print(f"report_id: {report_info['id']}")
    print(f"revision: {report_info['revision']}")
    print(f"enabled: {str(report_info['enabled']).lower()}")
  print(f"config: {yaml_scalar(config_path)}")
  print("records:")
  if not records:
    print("  []")
  for record in records:
    print(f"  - project: {yaml_scalar(record['project'])}")
    print(f"    subject: {yaml_scalar(record.get('subject', ''))}")
    print(f"    description: {yaml_scalar(record.get('description', 'review needed'))}")
    print(f"    minutes: {record_minutes(record)}")
    print("    periods:")
    for period in record_periods(record):
      print(f"      - start: \"{period['start'].strftime('%H:%M')}\"")
      print(f"        end: \"{period['end'].strftime('%H:%M')}\"")
    if show_evidence:
      print("    diagnostic:")
      print("      confidence: " + yaml_scalar(record.get("confidence", "unknown")))
      print("      evidence_json: " + yaml_scalar(json.dumps(record.get("evidence", {}), ensure_ascii=False, default=str)))
      print("      attribution_json: " + yaml_scalar(json.dumps(record.get("attribution", []), ensure_ascii=False, default=str)))
  if show_quality:
    metrics = quality_metrics(records)
    print("quality:")
    print(f"  tracked_minutes: {metrics['total']}")
    print(f"  working_minutes: {metrics['total']}")
    print("  project_minutes: " + json.dumps(metrics["projects"], sort_keys=True, ensure_ascii=False))
    print(f"  assigned_minutes: {metrics['assigned']}")
    print(f"  unassigned_minutes: {metrics['unassigned']}")
    print(f"  described_minutes: {metrics['described']}")
    print(f"  review_needed_minutes: {metrics['review']}")
    print(f"  confidence_minutes: {{high: {metrics['high']}, medium: {metrics['medium']}, low: {metrics['low']}}}")


def print_report(day, records, config_path, args, report_info=None):
  if args.format == "yaml" or args.show_evidence:
    print_records(day, records, config_path, args.show_evidence, not args.no_quality, report_info)
  else:
    print_table(day, records, config_path, not args.no_quality, report_info)


def main(argv=None):
  args = parse_args(argv)
  if args.command == "record":
    args.no_ai = True
  elif args.command == "ai-record" and not args.describe_with:
    args.describe_with = os.environ.get("LOWR_TIME_TRACKER_AI_PROVIDER", "pi")
  config, config_path = load_config(args.config)
  aw_url = args.aw_url or config.get("activitywatch", {}).get("url", "http://127.0.0.1:5600")
  try:
    day = dt.date.fromisoformat(args.date)
  except ValueError:
    print("--date must be formatted as YYYY-MM-DD", file=sys.stderr)
    raise SystemExit(1)

  if args.new and args.improve:
    print("--new and --improve cannot be used together", file=sys.stderr)
    raise SystemExit(1)
  if args.improve and args.no_ai:
    print("--improve requires AI; use lowr-aw-time-tracker-ai-record", file=sys.stderr)
    raise SystemExit(1)

  database_path = tracker_database_path(config)
  if args.command == "list":
    print_report_versions(day, list_reports(database_path, day))
    return
  if args.command == "enable":
    report_id = args.option_record_id or args.record_id
    if not report_id:
      print("enable requires a report ID: lowr-aw-time-tracker enable ID", file=sys.stderr)
      raise SystemExit(1)
    enabled_day = enable_report(database_path, report_id)
    if not enabled_day:
      print(f"Stored report ID {report_id} was not found", file=sys.stderr)
      raise SystemExit(1)
    print(f"Enabled report #{report_id} for {enabled_day}")
    return

  cached = None if args.new else load_report(database_path, day)
  if cached:
    records = cached["records"]
    ai_requested = args.command == "ai-record" or bool(args.describe_with)
    should_improve = ai_requested or bool(args.improve or args.ai_dry_run) or bool(args.prompt and config.get("ai", {}).get("enabled", False))
    if should_improve:
      prompt = args.improve or args.prompt or ""
      records = process_ai(records, args, config, prompt, force_candidates=True)
      if not args.ai_dry_run:
        source = "improved" if args.improve else "ai-refined"
        report_id = save_report(
          database_path, day, records, config_path,
          args.describe_with or config.get("ai", {}).get("provider", "pi"),
          prompt, source=source, parent_id=cached["id"],
        )
        cached = load_report(database_path, report_id=report_id)
        print(f"Saved and enabled report #{report_id} for {day.isoformat()}", file=sys.stderr)
    else:
      print(f"Loaded latest report #{cached['id']} for {day.isoformat()} from {database_path}", file=sys.stderr)
    print_report(day, records, config_path, args, cached)
    return
  if args.improve:
    print(f"No stored report exists for {day.isoformat()}; generate it first with --new", file=sys.stderr)
    raise SystemExit(1)

  day_start, day_end = local_day_bounds(day, configured_start_time(config))
  buckets = config.get("buckets", {})
  window_bucket = buckets.get("window", f"aw-watcher-window_{args.hostname}")
  terminal_bucket = buckets.get("terminal", f"aw-watcher-terminal_{args.hostname}")
  afk_bucket = buckets.get("afk", f"aw-watcher-afk_{args.hostname}")
  git_bucket = buckets.get("git", f"aw-watcher-git_{args.hostname}")

  window_events = normalize_events(query_events(aw_url, window_bucket, day_start, day_end), day_start, day_end)
  terminal_events = normalize_events(query_events(aw_url, terminal_bucket, day_start, day_end, required=False), day_start, day_end)
  afk_events = normalize_events(query_events(aw_url, afk_bucket, day_start, day_end, required=False), day_start, day_end)
  git_events = normalize_events(query_events(aw_url, git_bucket, day_start, day_end, required=False), day_start, day_end, allow_points=True)
  web_events = query_web_events(config, aw_url, args.hostname, day_start, day_end)

  records = build_records(window_events, terminal_events, afk_events, config, web_events)
  records = merge_records(remove_overlaps(records))
  rounding_minutes = int(config.get("rounding", {}).get("minutes", 15))
  if rounding_minutes <= 0:
    raise_config("rounding.minutes", "must be greater than zero")
  records = round_records(records, rounding_minutes)
  # Rounding outwards must never add AFK minutes back into work records. Subtract
  # AFK before resolving rounded overlaps so configured coffee records survive.
  records = remove_afk_from_work(records, afk_events, preserve_breaks=True)
  records = merge_records(remove_overlaps(records))
  records = summarize_day_records(records)
  enrich_with_git(records, git_events, day_start, day_end, config)
  generate_descriptions(records)
  records = process_ai(records, args, config, args.prompt or "", force_candidates=bool(args.prompt))
  ai_enabled = bool(args.describe_with) or bool(config.get("ai", {}).get("enabled", False))
  provider = (args.describe_with or config.get("ai", {}).get("provider", "")) if ai_enabled and not args.no_ai else ""
  if args.ai_dry_run:
    print_report(day, records, config_path, args)
    return
  source = "ai-new" if provider else "deterministic-new"
  report_id = save_report(database_path, day, records, config_path, provider, args.prompt or "", source=source)
  saved = load_report(database_path, report_id=report_id)
  print(f"Saved and enabled report #{report_id} for {day.isoformat()}", file=sys.stderr)
  print_report(day, records, config_path, args, saved)


if __name__ == "__main__":
  main()

import argparse
import datetime as dt
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
  import tomllib
except ModuleNotFoundError:
  print("Python 3.11 or newer is required for TOML config parsing.", file=sys.stderr)
  sys.exit(1)


BROWSER_APPS = {"zen", "chromium", "firefox", "google-chrome", "brave", "browser"}
WORK_APPS = {"code", "codium", "vscode", "zed", "rider", "wezterm", "terminal", "alacritty", "kitty", "ghostty"}
DEFAULT_NOISE_STRETCH_MINUTES = 5


def parse_args():
  parser = argparse.ArgumentParser(
    prog="lowr-aw-time-tracker",
    description="Summarize ActivityWatch events into daily project time records."
  )
  parser.add_argument(
    "--date",
    default=dt.date.today().isoformat(),
    help="Local date to summarize, formatted as YYYY-MM-DD. Defaults to today.",
  )
  parser.add_argument(
    "--config",
    help="Path to a time-tracker TOML config. Defaults to ~/.config/lowr/time-tracker.toml if present, otherwise the Lowr default config.",
  )
  parser.add_argument(
    "--aw-url",
    help="ActivityWatch server URL. Overrides the config value.",
  )
  parser.add_argument(
    "--hostname",
    default=socket.gethostname(),
    help="Hostname suffix used for ActivityWatch buckets. Defaults to this machine hostname.",
  )
  return parser.parse_args()


def load_config(path):
  lowr_path = os.environ.get("LOWR_PATH", os.path.expanduser("~/.local/share/lowr"))
  default_path = os.path.join(lowr_path, "config", "lowr", "time-tracker.toml")
  user_path = os.path.expanduser("~/.config/lowr/time-tracker.toml")
  config_path = path or (user_path if os.path.exists(user_path) else default_path)

  if not os.path.exists(config_path):
    print(f"Config not found: {config_path}", file=sys.stderr)
    sys.exit(1)

  with open(config_path, "rb") as config_file:
    return tomllib.load(config_file), config_path


def local_day_bounds(day, start_time):
  local_zone = dt.datetime.now().astimezone().tzinfo
  start = dt.datetime.combine(day, start_time, tzinfo=local_zone)
  end = start + dt.timedelta(days=1)
  return start, end


def parse_aw_time(value):
  if value.endswith("Z"):
    value = value[:-1] + "+00:00"
  return dt.datetime.fromisoformat(value).astimezone()


def query_events(aw_url, bucket, start, end):
  base = aw_url.rstrip("/")
  params = urllib.parse.urlencode({
    "start": start.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    "end": end.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
  })
  url = f"{base}/api/0/buckets/{urllib.parse.quote(bucket)}/events?{params}"

  try:
    with urllib.request.urlopen(url, timeout=5) as response:
      return json.loads(response.read().decode("utf-8"))
  except urllib.error.HTTPError as error:
    if error.code == 404:
      return []
    raise
  except urllib.error.URLError as error:
    print(f"Could not connect to ActivityWatch at {aw_url}: {error.reason}", file=sys.stderr)
    sys.exit(1)


def normalize_event(event, day_start, day_end):
  start = parse_aw_time(event["timestamp"])
  duration = float(event.get("duration", 0) or 0)
  end = start + dt.timedelta(seconds=duration)

  if duration <= 0:
    return None
  if end <= day_start or start >= day_end:
    return None

  return {
    "start": max(start, day_start),
    "end": min(end, day_end),
    "data": event.get("data", {}) or {},
  }


def normalize_events(events, day_start, day_end):
  normalized = []
  for event in events:
    normalized_event = normalize_event(event, day_start, day_end)
    if normalized_event:
      normalized.append(normalized_event)
  return sorted(normalized, key=lambda item: item["start"])


def lower_values(values):
  return [str(value).lower() for value in values if value]


def get_config_list(config, section, key, fallback):
  value = config.get(section, {}).get(key, fallback)
  return set(lower_values(value))


def first_value(*values):
  for value in values:
    text = str(value or "").strip()
    if text:
      return text
  return ""


def classify_activity(data, terminal_hint):
  project = first_value(
    data.get("project"),
    data.get("category"),
    (terminal_hint or {}).get("project"),
    (terminal_hint or {}).get("category"),
  )

  if project:
    return {
      "project": project,
      "subject": first_value(data.get("subject"), (terminal_hint or {}).get("subject")),
      "description": first_value(data.get("description"), (terminal_hint or {}).get("description"), "review needed"),
    }

  return None


def find_terminal_hint(start, end, terminal_events):
  best = None
  best_overlap = 0

  for event in terminal_events:
    overlap_start = max(start, event["start"])
    overlap_end = min(end, event["end"])
    overlap = (overlap_end - overlap_start).total_seconds()

    if overlap <= 0:
      # Prompt heartbeats can be short; allow nearby events to annotate a window block.
      distance = min(abs((start - event["end"]).total_seconds()), abs((event["start"] - end).total_seconds()))
      if distance > 300:
        continue
      overlap = 1

    if overlap > best_overlap:
      best = event["data"]
      best_overlap = overlap

  return best


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
  except ValueError:
    print("day.start_time must be formatted as HH:MM", file=sys.stderr)
    sys.exit(1)


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

      minutes = (event["end"] - event["start"]).total_seconds() / 60
      if minutes < coffee_minutes:
        continue

      target = time_on_day(event["start"].date(), event["start"].tzinfo, slot_time)
      window_start = target - dt.timedelta(minutes=window_minutes)
      window_end = target + dt.timedelta(minutes=window_minutes)
      if event["start"] >= window_end or event["end"] <= window_start:
        continue

      earliest = round_up(event["start"], coffee_minutes)
      latest = round_down(event["end"] - dt.timedelta(minutes=coffee_minutes), coffee_minutes)
      if latest < earliest:
        continue

      record_start = max(earliest, min(round_down(target, coffee_minutes), latest))
      record_end = record_start + dt.timedelta(minutes=coffee_minutes)
      distance = abs((record_start - target).total_seconds())

      if best_distance is None or distance < best_distance:
        best = (record_start, record_end)
        best_distance = distance

    if not best:
      continue

    record_start, record_end = best
    records.append({
      "project": "internal",
      "subject": f"coffee-{subject}",
      "description": "coffee break",
      "start": record_start,
      "end": record_end,
    })

  return records


def subtract_intervals(record, intervals):
  parts = [record]

  for interval in intervals:
    next_parts = []
    for part in parts:
      if interval["end"] <= part["start"] or interval["start"] >= part["end"]:
        next_parts.append(part)
        continue

      if part["start"] < interval["start"]:
        before = dict(part)
        before["end"] = interval["start"]
        next_parts.append(before)
      if part["end"] > interval["end"]:
        after = dict(part)
        after["start"] = interval["end"]
        next_parts.append(after)

    parts = next_parts

  return parts


def remove_afk_from_work(records, afk_events):
  afk_intervals = [event for event in afk_events if event["data"].get("status") == "afk"]
  cleaned = []

  for record in records:
    cleaned.extend(subtract_intervals(record, afk_intervals))

  return cleaned


def overlaps_intervals(start, end, intervals):
  for interval in intervals:
    if interval["start"] < end and interval["end"] > start:
      return True
  return False


def same_work(left, right):
  return all(left.get(key) == right.get(key) for key in ["project", "subject", "description"])


def stretch_records_over_noise(records, noise_events, afk_events, minutes):
  if not records or not noise_events or minutes <= 0:
    return records

  limit = dt.timedelta(minutes=minutes)
  afk_intervals = [event for event in afk_events if event["data"].get("status") == "afk"]
  stretched = [dict(record) for record in sorted(records, key=lambda item: item["start"])]

  for noise in noise_events:
    if noise["end"] <= noise["start"]:
      continue
    if noise["end"] - noise["start"] > limit:
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

    if previous and previous["end"] <= noise["start"]:
      gap = noise["end"] - previous["end"]
      if gap <= limit and not overlaps_intervals(previous["end"], noise["end"], afk_intervals):
        previous["end"] = noise["end"]

    if next_record and noise["end"] <= next_record["start"]:
      gap = next_record["start"] - noise["start"]
      if gap <= limit and not overlaps_intervals(noise["start"], next_record["start"], afk_intervals):
        next_record["start"] = noise["start"]

    if previous and next_record and same_work(previous, next_record):
      gap = next_record["start"] - previous["end"]
      if gap <= limit and not overlaps_intervals(previous["end"], next_record["start"], afk_intervals):
        previous["end"] = next_record["start"]

  return stretched


def build_records(window_events, terminal_events, afk_events, config):
  noise_apps = get_config_list(config, "noise", "apps", BROWSER_APPS)
  work_apps = get_config_list(config, "work_apps", "apps", WORK_APPS)
  noise_stretch_minutes = int(config.get("noise", {}).get("stretch_minutes", DEFAULT_NOISE_STRETCH_MINUTES))
  records = []
  noise_events = []

  for event in window_events:
    data = event["data"]
    app = str(data.get("app", "")).lower()
    terminal_hint = find_terminal_hint(event["start"], event["end"], terminal_events)
    project = classify_activity(data, terminal_hint)

    if not project and app in noise_apps:
      noise_events.append(event)
      continue
    if not project and app not in work_apps:
      continue

    record = {
      "project": (project or {}).get("project", "unassigned"),
      "subject": (project or {}).get("subject", ""),
      "description": (project or {}).get("description", "review needed"),
      "start": event["start"],
      "end": event["end"],
    }
    records.append(record)

  work_records = remove_afk_from_work(records, afk_events)
  work_records = stretch_records_over_noise(work_records, noise_events, afk_events, noise_stretch_minutes)
  work_records.extend(afk_break_records(afk_events, config))
  return work_records


def round_records(records, minutes):
  rounded = []
  for record in records:
    start = round_down(record["start"], minutes)
    end = round_up(record["end"], minutes)
    if end <= start:
      continue
    rounded_record = dict(record)
    rounded_record["start"] = start
    rounded_record["end"] = end
    rounded.append(rounded_record)
  return sorted(rounded, key=lambda item: item["start"])


def merge_records(records):
  merged = []
  for record in records:
    if not merged:
      merged.append(record)
      continue

    previous = merged[-1]
    same_work_match = same_work(previous, record)
    touches = record["start"] <= previous["end"]

    if same_work_match and touches:
      previous["end"] = max(previous["end"], record["end"])
    else:
      merged.append(record)
  return merged


def remove_overlaps(records):
  cleaned = []
  for record in sorted(records, key=lambda item: item["start"]):
    if not cleaned:
      cleaned.append(record)
      continue

    previous = cleaned[-1]
    same_work_match = same_work(previous, record)

    if record["start"] < previous["end"]:
      if same_work_match:
        previous["end"] = max(previous["end"], record["end"])
        continue

      record = dict(record)
      record["start"] = previous["end"]

    if record["end"] > record["start"]:
      cleaned.append(record)

  return cleaned


def print_records(day, records, config_path):
  print(f"date: {day.isoformat()}")
  print(f"config: {config_path}")
  print("records:")

  if not records:
    print("  []")
    return

  for record in records:
    print(f"  - project: {record['project']}")
    print(f"    subject: {record['subject']}")
    print(f"    description: {record['description']}")
    print(f"    start: \"{record['start'].strftime('%H:%M')}\"")
    print(f"    end: \"{record['end'].strftime('%H:%M')}\"")


def main():
  args = parse_args()
  config, config_path = load_config(args.config)
  aw_url = args.aw_url or config.get("activitywatch", {}).get("url", "http://127.0.0.1:5600")

  try:
    day = dt.date.fromisoformat(args.date)
  except ValueError:
    print("--date must be formatted as YYYY-MM-DD", file=sys.stderr)
    sys.exit(1)

  day_start, day_end = local_day_bounds(day, configured_start_time(config))
  buckets = config.get("buckets", {})
  window_bucket = buckets.get("window", f"aw-watcher-window_{args.hostname}")
  terminal_bucket = buckets.get("terminal", f"aw-watcher-terminal_{args.hostname}")
  afk_bucket = buckets.get("afk", f"aw-watcher-afk_{args.hostname}")

  window_events = normalize_events(query_events(aw_url, window_bucket, day_start, day_end), day_start, day_end)
  terminal_events = normalize_events(query_events(aw_url, terminal_bucket, day_start, day_end), day_start, day_end)
  afk_events = normalize_events(query_events(aw_url, afk_bucket, day_start, day_end), day_start, day_end)

  records = build_records(window_events, terminal_events, afk_events, config)
  rounding_minutes = int(config.get("rounding", {}).get("minutes", 15))
  records = merge_records(remove_overlaps(records))
  records = merge_records(remove_overlaps(round_records(records, rounding_minutes)))
  print_records(day, records, config_path)


if __name__ == "__main__":
  main()

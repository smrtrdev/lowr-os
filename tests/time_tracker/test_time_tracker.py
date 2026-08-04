import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import pathlib
import sqlite3
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("time_tracker", ROOT / "bin/lib/time-tracker.py")
TRACKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACKER)
UTC = dt.timezone.utc


def at(hour, minute=0):
  return dt.datetime(2026, 1, 12, hour, minute, tzinfo=UTC)


def event(start, end, data=None):
  return {"start": start, "end": end, "data": data or {}}


class NormalizationTests(unittest.TestCase):
  def test_event_is_clipped_to_day_boundary(self):
    value = {
      "timestamp": "2026-01-12T03:30:00Z",
      "duration": 7200,
      "data": {"app": "Zed"},
    }
    normalized = TRACKER.normalize_event(value, at(4), at(4) + dt.timedelta(days=1))
    self.assertEqual(at(4), normalized["start"])
    self.assertEqual(at(5, 30), normalized["end"])

  def test_point_events_are_optional(self):
    value = {"timestamp": "2026-01-12T08:00:00Z", "duration": 0, "data": {"kind": "commit"}}
    self.assertIsNone(TRACKER.normalize_event(value, at(4), at(4) + dt.timedelta(days=1)))
    self.assertEqual(at(8), TRACKER.normalize_event(value, at(4), at(4) + dt.timedelta(days=1), True)["start"])


class TimelineTests(unittest.TestCase):
  def make_record(self, start, end, project="acme", subject=""):
    value = TRACKER.new_record(start, end)
    value.update({"project": project, "subject": subject, "description": "review needed", "confidence": "medium"})
    return value

  def test_afk_subtraction_keeps_evidence_on_both_sides(self):
    record = self.make_record(at(8), at(10))
    TRACKER.add_evidence(record, "titles", "api.py — acme")
    parts = TRACKER.remove_afk_from_work([record], [event(at(8, 45), at(9, 15), {"status": "afk"})])
    self.assertEqual([(at(8), at(8, 45)), (at(9, 15), at(10))], [(part["start"], part["end"]) for part in parts])
    self.assertEqual(["api.py — acme"], parts[1]["evidence"]["titles"])

  def test_noise_stretch_does_not_cross_afk(self):
    records = [self.make_record(at(8), at(8, 2)), self.make_record(at(8, 5), at(8, 10))]
    noise = [event(at(8, 2), at(8, 5))]
    stretched = TRACKER.stretch_records_over_noise(records, noise, [], 5)
    self.assertEqual(at(8, 5), stretched[0]["end"])
    blocked = TRACKER.stretch_records_over_noise(records, noise, [event(at(8, 3), at(8, 4), {"status": "afk"})], 5)
    self.assertEqual(at(8, 2), blocked[0]["end"])

  def test_merge_ignores_placeholder_description_and_unions_evidence(self):
    left = self.make_record(at(8), at(9))
    right = self.make_record(at(9), at(10))
    left["description"] = "review needed"
    right["description"] = "Development in acme"
    TRACKER.add_evidence(left, "titles", "one")
    TRACKER.add_evidence(right, "titles", "one")
    TRACKER.add_evidence(right, "titles", "two")
    merged = TRACKER.merge_records([left, right])
    self.assertEqual(1, len(merged))
    self.assertEqual(["one", "two"], merged[0]["evidence"]["titles"])

  def test_daily_summary_groups_projects_without_counting_gaps(self):
    records = [
      self.make_record(at(8), at(9), "acme", "reporting"),
      self.make_record(at(9), at(9, 30), "other", "support"),
      self.make_record(at(10), at(10, 15), "acme", "testing"),
    ]
    summaries = TRACKER.summarize_day_records(records)
    acme = next(record for record in summaries if record["project"] == "acme")
    self.assertEqual(2, len(acme["periods"]))
    self.assertEqual(75, TRACKER.record_minutes(acme))
    metrics = TRACKER.quality_metrics(summaries)
    self.assertEqual(105, metrics["total"])
    self.assertEqual({"acme": 75, "other": 30}, metrics["projects"])

  def test_table_rows_are_chronological_and_totals_match(self):
    later = self.make_record(at(10), at(11), "acme", "later")
    earlier = self.make_record(at(8), at(9, 30), "other", "earlier")
    for record in [later, earlier]:
      record["description"] = f"Work on {record['subject']}"
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
      TRACKER.print_table(dt.date(2026, 1, 12), [later, earlier], "config.toml")
    text = output.getvalue()
    self.assertLess(text.index("| 08:00 |"), text.index("| 10:00 |"))
    self.assertIn("other", text)
    self.assertIn("1h 30m", text)
    self.assertIn("OVERALL", text)
    self.assertIn("2h 30m", text)

  def test_unassigned_periods_are_not_combined(self):
    records = [
      self.make_record(at(8), at(9), "unassigned"),
      self.make_record(at(10), at(11), "unassigned"),
    ]
    self.assertEqual(2, len(TRACKER.summarize_day_records(records)))

  def test_overlap_and_quarter_hour_rounding(self):
    first = self.make_record(at(8, 7), at(8, 31), "one")
    second = self.make_record(at(8, 29), at(8, 50), "two")
    rounded = TRACKER.round_records([first, second], 15)
    cleaned = TRACKER.remove_overlaps(rounded)
    self.assertEqual((at(8), at(8, 45)), (cleaned[0]["start"], cleaned[0]["end"]))
    self.assertEqual((at(8, 45), at(9)), (cleaned[1]["start"], cleaned[1]["end"]))

  def test_rounding_does_not_reintroduce_afk_time(self):
    record = self.make_record(at(15), at(16))
    afk = [event(at(15, 8), at(15, 29), {"status": "afk"})]
    rounded = TRACKER.round_records(TRACKER.remove_afk_from_work([record], afk), 15)
    cleaned = TRACKER.remove_afk_from_work(rounded, afk, preserve_breaks=True)
    self.assertFalse(any(TRACKER.overlaps_intervals(part["start"], part["end"], afk) for part in cleaned))
    self.assertEqual(39, sum(TRACKER.record_minutes(part) for part in cleaned))

  def test_coffee_break_and_lunch_behavior(self):
    config = {"breaks": {"coffee_morning_time": "09:30", "coffee_afternoon_time": "15:00"}}
    afk = [event(at(9, 20), at(9, 50), {"status": "afk"}), event(at(12), at(13), {"status": "afk"})]
    breaks = TRACKER.afk_break_records(afk, config)
    self.assertEqual(1, len(breaks))
    self.assertEqual("coffee-morning", breaks[0]["subject"])
    self.assertEqual(15, (breaks[0]["end"] - breaks[0]["start"]).total_seconds() / 60)


class AttributionTests(unittest.TestCase):
  def setUp(self):
    self.config = {
      "apps": {
        "work": {"zed": ["zed", "dev.zed.zed"], "wezterm": ["wezterm", "org.wezfurlong.wezterm"]},
        "noise": {"browser": ["zen", "firefox"]},
      },
      "projects": [
        {
          "name": "acme",
          "path_prefixes": ["/work/acme"],
          "title_patterns": ["acme"],
          "url_patterns": ["github.com/*/acme/pull/*"],
        }
      ],
      "terminal": {"nearby_minutes": 5, "max_context_age_minutes": 120},
    }

  def test_desktop_identifiers_resolve_exactly(self):
    self.assertEqual(("zed", "work"), TRACKER.resolve_application("dev.zed.Zed", self.config))
    self.assertEqual(("wezterm", "work"), TRACKER.resolve_application("org.wezfurlong.wezterm", self.config))
    self.assertEqual(("not-zed", ""), TRACKER.resolve_application("not-zed", self.config))

  def test_explicit_path_mapping_wins_over_title(self):
    config = dict(self.config)
    config["projects"] = self.config["projects"] + [{"name": "other", "path_prefixes": [], "title_patterns": ["other"], "url_patterns": []}]
    record = TRACKER.new_record(at(8), at(9))
    TRACKER.add_evidence(record, "paths", "/work/acme/src")
    TRACKER.add_evidence(record, "titles", "other — Zed")
    TRACKER.resolve_record_project(record, {}, {}, {}, config)
    self.assertEqual("acme", record["project"])
    self.assertEqual("high", record["confidence"])

  def test_sparse_terminal_context_requires_agreement(self):
    terminal = [event(at(8), at(8, 0) + dt.timedelta(seconds=30), {"project": "acme", "repository": "/work/acme"})]
    self.assertIsNotNone(TRACKER.find_terminal_event(at(9), at(10), terminal, "acme — Zed", self.config))
    self.assertIsNone(TRACKER.find_terminal_event(at(9), at(10), terminal, "other — Zed", self.config))

  def test_remote_urls_normalize_without_credentials(self):
    self.assertEqual("github.com/example/acme", TRACKER.sanitize_remote("git@github.com:example/acme.git"))
    self.assertEqual("github.com/example/acme", TRACKER.sanitize_remote("https://user:secret@github.com/example/acme.git?token=x"))

  def test_web_url_is_sanitized_and_only_active_overlap_is_used(self):
    web = [event(at(8), at(8, 30), {"url": "https://user:secret@github.com/example/acme/pull/7?token=x#fragment", "title": "Improve reports"})]
    windows = [event(at(8), at(8, 15), {"app": "Zen", "title": "Browser"})]
    records = TRACKER.build_records(windows, [], [], self.config, web)
    self.assertEqual(1, len(records))
    self.assertEqual("acme", records[0]["project"])
    self.assertEqual(["https://github.com/example/acme/pull/7"], records[0]["evidence"]["urls"])

  def test_project_alias_maps_solution_title_to_canonical_project(self):
    config = dict(self.config)
    config["project_aliases"] = {"Wydler.Crm": "wam-crm", "CRM": "wam-crm"}
    windows = [event(at(8), at(9), {"app": "dev.zed.Zed", "title": "PortfolioMappings.cs — Wydler.Crm"})]
    records = TRACKER.build_records(windows, [], [], config)
    self.assertEqual("wam-crm", records[0]["project"])

  def test_unknown_editor_period_remains_unassigned(self):
    windows = [event(at(8), at(9), {"app": "dev.zed.Zed", "title": "unknown"})]
    records = TRACKER.build_records(windows, [], [], self.config)
    TRACKER.generate_descriptions(records)
    self.assertEqual("unassigned", records[0]["project"])
    self.assertEqual("review needed", records[0]["description"])


class GitAndDescriptionTests(unittest.TestCase):
  def test_temporary_repository_commit_and_git_query(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      repository = pathlib.Path(temp_dir) / "repository"
      tools = pathlib.Path(temp_dir) / "tools"
      repository.mkdir()
      tools.mkdir()
      subprocess.run(["git", "init", "-q", str(repository)], check=True)
      subprocess.run(["git", "-C", str(repository), "config", "user.name", "Sanitized User"], check=True)
      subprocess.run(["git", "-C", str(repository), "config", "user.email", "user@example.test"], check=True)
      (repository / "file.txt").write_text("evidence\n")
      subprocess.run(["git", "-C", str(repository), "add", "file.txt"], check=True)
      for name, body in [("curl", "#!/bin/bash\nexit 1\n"), ("jq", "#!/bin/bash\necho '{}'\n")]:
        tool = tools / name
        tool.write_text(body)
        tool.chmod(0o755)
      hook = repository / ".git/hooks/post-commit"
      hook.symlink_to(ROOT / "bin/lowr-aw-git-heartbeat")
      environment = dict(os.environ)
      environment["PATH"] = f"{tools}:{environment['PATH']}"
      environment["GIT_AUTHOR_DATE"] = "2026-01-12T08:15:00+00:00"
      environment["GIT_COMMITTER_DATE"] = "2026-01-12T08:15:00+00:00"
      result = subprocess.run(["git", "-C", str(repository), "commit", "-qm", "Add sanitized evidence"], env=environment)
      self.assertEqual(0, result.returncode)
      identity = TRACKER.git_identity(str(repository))
      commits = TRACKER.query_git_commits(identity, at(4), at(4) + dt.timedelta(days=1), {})
      self.assertEqual(["Add sanitized evidence"], [commit["subject"] for commit in commits])
      self.assertTrue(commits[0]["local"])

  def test_git_and_activitywatch_commit_are_deduplicated(self):
    base = {
      "hash": "a" * 40,
      "subject": "Add report view",
      "repository": "/work/acme",
      "timestamp": at(8),
      "local": True,
      "sources": ["git_log"],
    }
    duplicate = dict(base, sources=["activitywatch"])
    commits = TRACKER.deduplicate_commits([base, duplicate])
    self.assertEqual(1, len(commits))
    self.assertEqual(["git_log", "activitywatch"], commits[0]["sources"])

  def test_commit_in_gap_does_not_attach_to_daily_project_summary(self):
    first = TRACKER.new_record(at(8), at(9))
    first.update({"project": "acme", "confidence": "high"})
    second = TRACKER.new_record(at(11), at(12))
    second.update({"project": "acme", "confidence": "high"})
    for record in [first, second]:
      TRACKER.add_evidence(record, "repositories", "/work/acme")
    summary = TRACKER.summarize_day_records([first, second])[0]
    commit = {"hash": "a" * 40, "subject": "Fetched work", "repository": "/work/acme", "timestamp": at(10), "local": True, "sources": ["git_log"]}
    TRACKER.correlate_commits([summary], [commit], [], {"git": {"correlation_margin_minutes": 15}})
    self.assertEqual([], summary["evidence"]["commits"])

  def test_commit_and_branch_descriptions_are_deterministic(self):
    commit_record = TRACKER.new_record(at(8), at(9))
    commit_record.update({"project": "acme", "confidence": "high"})
    TRACKER.add_evidence(commit_record, "commits", {"subject": "Add bug report detail view", "hash": "a" * 40})
    branch_record = TRACKER.new_record(at(9), at(10))
    branch_record.update({"project": "acme", "confidence": "medium"})
    TRACKER.add_evidence(branch_record, "branches", "feature/bug-reporting")
    TRACKER.generate_descriptions([commit_record, branch_record])
    self.assertEqual("Add bug report detail view", commit_record["description"])
    self.assertEqual("Work on bug reporting feature", branch_record["description"])
    self.assertEqual("bug-reporting", branch_record["subject"])

  def test_ai_aliases_lower_confidence_project_and_persists_memory(self):
    canonical = TRACKER.new_record(at(8), at(9))
    canonical.update({"project": "wam-crm", "confidence": "high", "description": "Development in wam-crm", "description_confidence": "medium"})
    alias = TRACKER.new_record(at(10), at(11))
    alias.update({"project": "Wydler.Crm", "confidence": "medium", "description": "review needed", "description_confidence": "low"})
    TRACKER.add_evidence(alias, "titles", "PortfolioMappings.cs — Wydler.Crm")
    payload = TRACKER.build_ai_payload([canonical, alias], {"minimum_minutes": 15}, {})
    evidence_id = payload["records"][1]["evidence"][0]["id"]
    response = {"suggestions": [{"index": 1, "description": "Review portfolio mappings", "subject": "portfolio mappings", "project": "wam-crm", "confidence": "high", "evidence_ids": [evidence_id]}]}
    changes = TRACKER.apply_ai_suggestions([canonical, alias], payload, response, {"allow_project_suggestion": True})
    self.assertEqual("wam-crm", alias["project"])
    self.assertEqual(1, len(TRACKER.summarize_day_records([canonical, alias])))
    aliases = TRACKER.validated_ai_aliases(payload, response, changes)
    with tempfile.TemporaryDirectory() as temp_dir:
      path = pathlib.Path(temp_dir) / "memory.json"
      config = {"_memory_path": str(path), "_learned_project_aliases": {}}
      TRACKER.persist_project_aliases(config, aliases)
      memory = json.loads(path.read_text())
      self.assertEqual("wam-crm", memory["project_aliases"]["Wydler.Crm"]["project"])

  def test_ai_payload_is_redacted_and_suggestion_cannot_change_time(self):
    record = TRACKER.new_record(at(8), at(9))
    record["description"] = "review needed"
    record["description_confidence"] = "low"
    TRACKER.add_evidence(record, "urls", "https://example.com/work?token=secret#x")
    TRACKER.add_evidence(record, "titles", "Work item 7")
    payload = TRACKER.build_ai_payload([record], {"minimum_minutes": 15, "include_urls": False})
    self.assertNotIn("token", json.dumps(payload))
    evidence_id = payload["records"][0]["evidence"][0]["id"]
    response = {"suggestions": [{"index": 0, "description": "Investigate work item 7", "subject": "work item 7", "project": "acme", "confidence": "medium", "evidence_ids": [evidence_id], "start": "00:00"}]}
    TRACKER.apply_ai_suggestions([record], payload, response, {"allow_project_suggestion": True})
    self.assertEqual((at(8), at(9)), (record["start"], record["end"]))
    self.assertEqual("acme", record["project"])


class StorageTests(unittest.TestCase):
  def test_pi_json_stream_shows_reasoning_and_collects_response(self):
    events = [
      {"assistantMessageEvent": {"type": "thinking_delta", "delta": "checking evidence"}},
      {"assistantMessageEvent": {"type": "text_delta", "delta": "{\"ok\":"}},
      {"assistantMessageEvent": {"type": "text_delta", "delta": "true}"}},
    ]
    script = "import json,time; events=" + repr(events) + ";\nfor event in events:\n print(json.dumps(event), flush=True); time.sleep(.01)"
    output = io.StringIO()
    with contextlib.redirect_stderr(output):
      response = TRACKER.run_pi_json_stream(["python3", "-c", script], 2)
    self.assertEqual('{"ok":true}', response)
    self.assertIn("Pi reasoning:", output.getvalue())
    self.assertIn("checking evidence", output.getvalue())
    self.assertIn("Pi response:", output.getvalue())

  def test_tracker_home_is_initialized_as_git_repository(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      home = pathlib.Path(temp_dir) / "time-tracker"
      default = pathlib.Path(temp_dir) / "default.toml"
      default.write_text("[activitywatch]\nurl = \"http://localhost:5600\"\n")
      previous = os.environ.get("LOWR_TIME_TRACKER_HOME")
      os.environ["LOWR_TIME_TRACKER_HOME"] = str(home)
      try:
        config_path = TRACKER.initialize_tracker_home(str(default), str(pathlib.Path(temp_dir) / "missing.toml"))
      finally:
        if previous is None:
          os.environ.pop("LOWR_TIME_TRACKER_HOME", None)
        else:
          os.environ["LOWR_TIME_TRACKER_HOME"] = previous
      self.assertEqual(home / "config.toml", pathlib.Path(config_path))
      self.assertTrue((home / ".git").is_dir())
      self.assertTrue((home / "memory.json").is_file())
      self.assertTrue((home / "records.sqlite").is_file())
      self.assertTrue((home / "sqlite-diff").is_file())
      self.assertEqual("", subprocess.run(["git", "-C", str(home), "status", "--short"], capture_output=True, text=True, check=True).stdout)

  def test_report_versions_are_created_and_can_be_enabled(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      database = pathlib.Path(temp_dir) / "records.sqlite"
      record = TRACKER.new_record(at(8), at(9))
      record.update({"project": "acme", "subject": "reporting", "description": "Build report", "confidence": "high"})
      day = dt.date(2026, 1, 12)
      first_id = TRACKER.save_report(str(database), day, [record], "config.toml", source="deterministic-new")
      loaded = TRACKER.load_report(str(database), day)
      self.assertEqual(first_id, loaded["id"])
      self.assertEqual("acme", loaded["records"][0]["project"])
      self.assertEqual(60, TRACKER.record_minutes(loaded["records"][0]))
      record["description"] = "Improve report"
      second_id = TRACKER.save_report(
        str(database), day, [record], "config.toml", "pi", "make it concise",
        source="improved", parent_id=first_id,
      )
      loaded = TRACKER.load_report(str(database), day)
      self.assertEqual(second_id, loaded["id"])
      self.assertEqual("Improve report", loaded["records"][0]["description"])
      self.assertEqual("make it concise", loaded["prompt"])
      versions = TRACKER.list_reports(str(database), day)
      self.assertEqual([second_id, first_id], [version["id"] for version in versions])
      self.assertTrue(versions[0]["enabled"])
      TRACKER.enable_report(str(database), first_id)
      latest = TRACKER.load_report(str(database), day)
      self.assertEqual(second_id, latest["id"])
      enabled_versions = TRACKER.list_reports(str(database), day)
      self.assertFalse(enabled_versions[0]["enabled"])
      self.assertTrue(enabled_versions[1]["enabled"])
      enabled = TRACKER.load_report(str(database), report_id=first_id)
      self.assertEqual("Build report", enabled["records"][0]["description"])
      with sqlite3.connect(database) as connection:
        self.assertEqual(2, connection.execute("SELECT count(*) FROM reports").fetchone()[0])
        self.assertEqual(2, connection.execute("SELECT count(*) FROM records").fetchone()[0])

  def test_streaming_runner_returns_complete_output(self):
    command = ["python3", "-c", "import sys,time; print('{\\\"ok\\\":', end='', flush=True); time.sleep(.02); print('true}', flush=True)"]
    self.assertEqual({"ok": True}, json.loads(TRACKER.run_streaming(command, 2)))


class FixtureReportTests(unittest.TestCase):
  def test_sanitized_day_covers_aliases_web_afk_and_unassigned(self):
    fixture_path = pathlib.Path(__file__).parent / "fixtures/sanitized-day.json"
    fixture = json.loads(fixture_path.read_text())
    start, end = at(4), at(4) + dt.timedelta(days=1)
    normalized = {key: TRACKER.normalize_events(value, start, end, key == "git") for key, value in fixture.items()}
    config = {
      "projects": [
        {"name": "acme", "path_prefixes": ["/work/acme"], "title_patterns": ["acme"], "url_patterns": ["github.com/*/acme/pull/*"]},
        {"name": "lowr", "path_prefixes": ["/work/lowr"], "title_patterns": ["lowr"], "url_patterns": []},
      ],
      "apps": {"work": {"zed": ["dev.zed.zed"], "wezterm": ["org.wezfurlong.wezterm"]}, "noise": {"browser": ["zen"]}},
    }
    records = TRACKER.build_records(normalized["window"], normalized["terminal"], normalized["afk"], config, normalized["web"])
    records = TRACKER.merge_records(TRACKER.remove_overlaps(records))
    records = TRACKER.summarize_day_records(records)
    aw_commits = TRACKER.commits_from_aw(normalized["git"])
    TRACKER.correlate_commits(records, aw_commits, [], config)
    TRACKER.generate_descriptions(records)
    self.assertEqual(1, sum(record["project"] == "acme" for record in records))
    self.assertEqual(1, sum(record["project"] == "lowr" for record in records))
    self.assertTrue(any(record["project"] == "unassigned" for record in records))
    self.assertTrue(any(record["description"] == "Add reporting view" for record in records))
    self.assertTrue(any(record["subject"] == "coffee-morning" for record in records))


if __name__ == "__main__":
  unittest.main()

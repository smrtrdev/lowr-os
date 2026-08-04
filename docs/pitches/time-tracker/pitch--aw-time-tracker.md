# PITCH: ActivityWatch Time Tracker

## Problem

I need a reliable way to summarize my working day into project, customer, and internal time records without manually reconstructing the day from memory.

ActivityWatch already captures useful raw signals: active windows, terminal paths, visited websites, and AFK periods. But the raw data is too noisy and too granular to use directly for time tracking. The useful output should be a clean daily summary with quarter-hour accuracy, grouped into meaningful project records.

Today the missing step is attribution: turning "I was active in this window, path, or website at this time" into "I worked on this project or subject from 10:45 to 14:30." This matters because time records need to be good enough for customer billing, internal product tracking, and personal review, without requiring constant manual timers.

## Appetite

4 weeks.

This is enough time to build a useful local-first prototype that can generate daily summaries from ActivityWatch data, apply simple project-mapping rules, detect breaks, and allow manual correction before the records are used.

## Solution

Build a local summarizer that queries ActivityWatch buckets for a selected day and produces a daily time report.

Implement the first version as a Python CLI exposed through the Lowr command `bin/lowr-aw-time-tracker`. Python is a good fit because this work is mostly timeline processing, merging, rounding, and heuristic classification, and it allows quick iteration while the attribution rules are still being shaped.

The core input sources are:

- `aw-watcher-window_<hostname>`: primary source for active work context.
- `aw-watcher-terminal_<hostname>`: supporting source for project, repository, worktree, and branch attribution.
- `aw-watcher-afk_<hostname>`: source for active/away periods and break detection.
- Compatible ActivityWatch web-watcher buckets: supporting evidence correlated only with active browser windows.
- Local Git history and `aw-watcher-git_<hostname>`: commit evidence that annotates activity without creating tracked time.

The summarizer should:

- Read the ActivityWatch timeline for a day.
- Filter out noisy windows such as general browsing unless they are useful for project attribution.
- Treat IDEs, terminals, and development tools as strong signals for project work.
- Merge short terminal/path events into nearby window activity.
- Round or summarize time into quarter-hour blocks.
- Detect at most two coffee breaks per day from AFK periods: one 15-minute break around 09:30 and one 15-minute break around 15:00.
- If a coffee-related AFK period is longer than 15 minutes, track only the 15-minute coffee break and leave the remaining AFK time untracked.
- Treat lunch and other AFK breaks like untracked away time: subtract them from project work but do not create records for them.
- Subtract AFK again after rounding so rounded work periods can never reclaim away time; configured coffee records remain the explicit exception.
- Collapse assigned work into one daily summary per project, retaining exact disjoint start/end periods and total minutes so gaps are never counted as work.
- Keep unrelated `unassigned` periods separate for review instead of combining unclear activity.
- Retain structured evidence and attribution diagnostics through merging and rounding.
- Generate conservative deterministic descriptions from commits, pull requests, titles, branches, and worktrees.
- Report exact rounded minutes per project and overall, plus assigned, described, and confidence-weighted minutes.
- Optionally postprocess weak descriptions through an explicitly enabled, redacted AI CLI; AI cannot alter record times or high-confidence project mappings.
- Let AI connect lower-confidence solution/application aliases to an existing canonical project, regroup the report afterward, and retain only validated high-confidence aliases in global time-tracker memory.
- Stream Pi JSON-mode reasoning and response deltas to stderr as they arrive, then print the final report on stdout.
- Store immutable report versions in SQLite: deterministic `record` returns the latest version, `ai-record` creates a refined child version, and both `--new` and `--improve "prompt"` insert and enable a new version instead of overwriting history.
- List a day's report IDs with `list --date YYYY-MM-DD` and mark the version that counts with `enable ID`; normal day queries still show the latest version.
- Produce an ERP-friendly chronological table by default, with one row per exact work period plus project and overall totals.
- Keep the editable YAML representation available through `--format yaml` before anything is exported or finalized.

Project attribution should start with explicit local rules, for example:

- Repository path maps to project.
- Window title containing project or repository name maps to project.
- Known IDE workspace maps to project.
- Known customer or product keywords map to project.
- Unclear periods are marked as `unassigned` instead of guessed silently.

Additional information sources can be added later to improve summaries:

- Authenticated GitHub API activity beyond active web pages and local Git history.
- MS Graph calendar events for meetings.
- Outlook sent mails.
- Teams calls.

These should not be required for the first version. The first version should work from ActivityWatch alone.

Repository placement:

- Core user-facing command: `bin/lowr-aw-time-tracker`.
- Deterministic convenience command: `bin/lowr-aw-time-tracker-record`.
- AI convenience command: `bin/lowr-aw-time-tracker-ai-record`, with `--prompt` for generation guidance.
- Existing installer remains responsible for ActivityWatch setup: `bin/lowr-install-time-tracker`.
- Default project mapping rules: `config/lowr/time-tracker.toml`.
- User configuration, learned memory, and records: `~/.config/time-tracker/{config.toml,memory.json,records.sqlite}` in a dedicated Git repository.
- Pitch and planning notes: `docs/pitches/time-tracker/`.

If the implementation grows beyond a single script, move reusable internals into a dedicated implementation directory later. Do not introduce that structure before it is needed.

## Rabbit Holes

- Perfect attribution is not realistic from ActivityWatch alone.
- Browser activity can be noisy and misleading.
- Window titles may contain sensitive data or inconsistent naming.
- Terminal events are short and need careful merging with surrounding context.
- AFK detection may confuse coffee breaks, interruptions, phone calls, and lunch; only the configured morning and afternoon coffee windows should produce break records.
- Calendar, Outlook, Teams, and GitHub integrations can easily expand the scope because of API permissions, authentication, pagination, and inconsistent metadata.
- Automatic descriptions may become too speculative unless based on strong signals like repository names, branch names, commits, or calendar titles.
- Quarter-hour rounding needs clear rules to avoid accidentally over-reporting or under-reporting time.

## No-Gos

- No real-time timer UI in the first version.
- No mobile tracking.
- No team or company-wide time tracking system.
- No automatic billing submission.
- No cloud sync.
- No requirement to classify every minute perfectly.
- No background-tab or deep browser-history analysis; only ActivityWatch web events overlapping an active browser window can support a record.
- No AI processing by default, and no AI authority over tracked time or high-confidence deterministic attribution.
- No Microsoft Graph, GitHub, Outlook, or Teams integration in the first slice.
- No silent guessing for unclear time blocks; unclear blocks must remain reviewable.
- No larger internal package layout until the first script becomes too large to maintain comfortably.

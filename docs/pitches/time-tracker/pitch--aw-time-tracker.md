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

- `aw-watcher-window_lowrarch01`: primary source for active work context.
- `aw-watcher-terminal_lowrarch01`: supporting source for project attribution through active paths.
- `aw-watcher-afk_lowrarch01`: source for active/away periods and break detection.

The summarizer should:

- Read the ActivityWatch timeline for a day.
- Filter out noisy windows such as general browsing unless they are useful for project attribution.
- Treat IDEs, terminals, and development tools as strong signals for project work.
- Merge short terminal/path events into nearby window activity.
- Round or summarize time into quarter-hour blocks.
- Detect at most two coffee breaks per day from AFK periods: one 15-minute break around 09:30 and one 15-minute break around 15:00.
- If a coffee-related AFK period is longer than 15 minutes, track only the 15-minute coffee break and leave the remaining AFK time untracked.
- Treat lunch and other AFK breaks like untracked away time: subtract them from project work but do not create records for them.
- Group adjacent or related blocks into clean records with project, subject, description, start, and end.
- Produce an editable daily summary before anything is exported or finalized.

Project attribution should start with explicit local rules, for example:

- Repository path maps to project.
- Window title containing project or repository name maps to project.
- Known IDE workspace maps to project.
- Known customer or product keywords map to project.
- Unclear periods are marked as `unassigned` instead of guessed silently.

Additional information sources can be added later to improve summaries:

- GitHub activity for commits, issues, and pull requests.
- MS Graph calendar events for meetings.
- Outlook sent mails.
- Teams calls.

These should not be required for the first version. The first version should work from ActivityWatch alone.

Repository placement:

- User-facing command: `bin/lowr-aw-time-tracker`.
- Existing installer remains responsible for ActivityWatch setup: `bin/lowr-install-time-tracker`.
- Default project mapping rules: `config/lowr/time-tracker.toml`.
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
- No deep browser-history analysis beyond what ActivityWatch already records.
- No Microsoft Graph, GitHub, Outlook, or Teams integration in the first slice.
- No silent guessing for unclear time blocks; unclear blocks must remain reviewable.
- No larger internal package layout until the first script becomes too large to maintain comfortably.

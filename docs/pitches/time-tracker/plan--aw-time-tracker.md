# IMPLEMENTATION PLAN: ActivityWatch Time Tracker Quality

## Goal

Improve `lowr-aw-time-tracker` from a timeline that mostly contains worktree names and `review needed` descriptions into an evidence-backed daily report with reliable project attribution, useful deterministic descriptions, and optional AI assistance.

The implementation must remain local-first and conservative:

- Preserve unclear periods as reviewable instead of inventing billable work.
- Keep timestamps and high-confidence project assignments deterministic.
- Treat Git commits and browser activity as evidence, not as time intervals.
- Do not record arbitrary shell commands or command arguments.
- Do not make commits fail when ActivityWatch is unavailable.
- Make remote AI processing explicit and opt-in.

## Target Pipeline

Process a day in this order:

1. Query and normalize ActivityWatch events.
2. Collect evidence from windows, terminal heartbeats, AFK events, Git events, and active browser tabs.
3. Resolve canonical applications, repositories, projects, worktrees, and branches.
4. Build activity records while retaining their evidence.
5. Remove AFK time and bridge only short, safe noise periods.
6. Merge and round records while combining evidence.
7. Query local Git repositories and correlate commits.
8. Generate deterministic subjects and descriptions.
9. Optionally ask an AI CLI to improve unresolved or weak descriptions.
10. Print an editable report and quality summary.

Descriptions must be generated near the end. Generating them before records are merged would fragment otherwise related work and discard useful context.

## Expected Files

Modify the existing files where possible:

- `bin/lib/time-tracker.py`
- `bin/lowr-aw-terminal-heartbeat`
- `bin/lowr-install-time-tracker`
- `config/lowr/time-tracker.toml`
- `docs/pitches/time-tracker/pitch--aw-time-tracker.md`, if the delivered behavior changes the pitch assumptions

Add narrowly scoped files when their responsibility is distinct:

- `bin/lowr-aw-git-heartbeat` — collect one structured Git event after a commit
- `config/git/hooks/post-commit` or an installer-generated equivalent — lightweight Git hook dispatcher
- Time-tracker tests and sanitized fixtures in the repository's established test location

Keep the Python implementation in `bin/lib/time-tracker.py` during the early slices. Extract modules only when evidence handling, Git querying, web correlation, and AI integration make the single file materially harder to test or maintain.

## Slice 0: Baseline, Fixtures, and Quality Metrics

### Purpose

Protect existing timeline, AFK, coffee-break, merging, and rounding behavior before attribution changes are introduced.

### Work

1. Capture sanitized fixtures representing:
   - VS Code window activity.
   - Zed window activity with `dev.zed.Zed`.
   - WezTerm activity with `org.wezfurlong.wezterm`.
   - Terminal activity in a normal repository.
   - Terminal activity in a Git worktree.
   - A long editor period with sparse terminal prompt heartbeats.
   - Browser window and web-watcher activity.
   - AFK, lunch, and configured coffee-break periods.
   - A Git commit found in both Git and ActivityWatch.
   - An unassignable period.
2. Add tests for:
   - Day-boundary normalization.
   - AFK subtraction.
   - Noise stretching.
   - Merge and overlap behavior.
   - Quarter-hour rounding.
   - Existing output fields.
3. Add report metrics calculated before rendering:
   - Total tracked minutes.
   - Assigned versus unassigned minutes.
   - Described versus `review needed` minutes.
   - High-, medium-, and low-confidence minutes.
4. Keep quality metrics concise in normal output or place them behind a flag if they make the editable report harder to consume.

### Acceptance criteria

- Existing coffee-break and AFK behavior is covered by tests.
- A fixture reproduces the current alias problem and current `review needed` fallback.
- Subsequent slices can demonstrate an improvement in assigned and described minutes.

## Slice 1: Evidence-Aware Records

### Purpose

Stop flattening source events into `project`, `subject`, and `description` before enough context has been collected.

### Internal model

Extend each internal record with structured evidence:

```python
{
  "project": "",
  "subject": "",
  "description": "",
  "confidence": "unknown",
  "start": start,
  "end": end,
  "evidence": {
    "apps": [],
    "titles": [],
    "paths": [],
    "repositories": [],
    "worktrees": [],
    "branches": [],
    "urls": [],
    "commits": [],
  },
  "attribution": [],
}
```

Use helper functions to append unique evidence rather than scattering list/set handling through timeline code.

Each attribution entry should identify why a field was chosen:

```python
{
  "field": "project",
  "source": "path_mapping",
  "value": "wam-crm",
  "confidence": "high",
}
```

### Merge behavior

1. Merge evidence whenever records merge.
2. Do not use generated descriptions to decide whether records represent the same work.
3. Compare canonical project and sufficiently reliable subject instead.
4. Keep conflicting evidence rather than silently replacing it.
5. Generate user-facing descriptions only after final timeline merging and rounding.

### Output behavior

Keep normal output compatible:

```yaml
project: wam-crm
subject: bug reporting
description: Add bug report detail view
start: "13:30"
end: "14:30"
```

Add an optional diagnostic mode such as `--show-evidence` for troubleshooting attribution. Do not expose sensitive paths or URLs in normal output unless they are already part of the selected description.

### Acceptance criteria

- Window titles and terminal paths survive merge, overlap removal, and rounding.
- Merged records contain the union of their evidence without duplicate values.
- Different placeholder descriptions no longer prevent otherwise identical work from merging.

## Slice 2: Canonical Application Aliases

### Purpose

Recognize actual desktop application identifiers instead of relying on exact short names.

### Configuration

Replace or supplement flat work/noise lists with explicit aliases:

```toml
[apps.work]
zed = ["zed", "dev.zed.zed"]
wezterm = ["wezterm", "org.wezfurlong.wezterm"]
vscode = ["code", "codium", "vscode", "visual studio code"]
rider = ["rider", "jetbrains-rider"]

[apps.noise]
browser = ["zen", "chromium", "firefox", "google-chrome", "brave", "browser"]
```

Retain backward compatibility with the existing `[work_apps].apps` and `[noise].apps` lists during migration.

### Work

1. Lowercase and trim watcher application identifiers once.
2. Resolve them to a canonical application through exact configured aliases.
3. Avoid unrestricted substring matching.
4. Store both the raw and canonical application in diagnostic evidence where useful.

### Acceptance criteria

- `dev.zed.Zed` resolves to `zed`.
- `org.wezfurlong.wezterm` resolves to `wezterm`.
- Existing short application names continue to work.
- Previously discarded Zed and WezTerm records reach the attribution pipeline.

## Slice 3: Project Mapping Rules

### Purpose

Implement the path-, title-, and URL-based project mappings described in the pitch.

### Configuration

Support repeated project sections:

```toml
[[projects]]
name = "wam-crm"
customer = "iseag"
path_prefixes = [
  "/home/smrtr/repos/iseag/wam-crm",
  "/home/smrtr/repos/iseag/wam-crm-worktrees/",
]
title_patterns = ["wam-crm"]
url_patterns = ["github.com/*/wam-crm/*"]

[[projects]]
name = "lowr"
customer = "internal"
path_prefixes = ["~/.local/share/lowr"]
title_patterns = ["lowr"]
url_patterns = []
```

Expand `~` and environment variables in configured paths before matching. Document whether title and URL patterns are literal, glob, or regular-expression patterns; prefer literal and glob matching for the first version.

### Matching precedence

Use a deterministic order:

1. Explicit repository/path mapping.
2. Exact or configured title mapping.
3. Configured URL mapping.
4. Terminal-provided repository/project.
5. Derived worktree/title identity.
6. `unassigned`.

Higher-confidence evidence must not be overwritten by lower-confidence evidence. Conflicts should remain visible in diagnostic evidence.

### Acceptance criteria

- Known repository paths map to canonical projects.
- Known IDE titles map to canonical projects when no path is available.
- An explicit path mapping wins over an ambiguous title.
- Unmatched periods remain `unassigned`.

## Slice 4: Repository and Worktree Normalization

### Purpose

Treat worktree suffixes and branches as subject evidence instead of separate projects.

### Git identity

For discovered Git paths, collect where available:

```text
git rev-parse --show-toplevel
git rev-parse --git-common-dir
git branch --show-current
git config --get remote.origin.url
```

Normalize remote URLs so SSH and HTTPS forms can identify the same repository without retaining credentials or query parameters.

Represent identity separately:

```python
{
  "project": "wam-crm",
  "repository": "/home/smrtr/repos/iseag/wam-crm",
  "worktree": "/home/smrtr/repos/iseag/wam-crm-worktrees/wam-crm.feature-bug-reporting",
  "branch": "feature/bug-reporting",
}
```

### Resolution order

1. Explicit configured project mapping.
2. Normalized remote identity.
3. Git common-directory identity.
4. Recognized worktree directory convention.
5. Name splitting only as a conservative fallback.

Do not assume every dot separates a repository from a worktree subject; repository names can legitimately contain dots.

### Subject derivation

Prefer, in order:

1. Configured subject mapping.
2. Branch name stripped of prefixes such as `feature/`, `fix/`, or `chore/`.
3. Recognized worktree suffix.
4. Strong task text from window titles.

Keep the raw branch in evidence even when a friendlier subject is derived.

### Acceptance criteria

- `wam-crm.feature-bug-reporting` maps to project `wam-crm` and subject `feature-bug-reporting` when supported by mapping or Git identity.
- Two worktrees from the same repository share one canonical project.
- Repository names containing dots are not split incorrectly.

## Slice 5: Better Terminal Evidence

### Purpose

Make terminal heartbeats useful beyond a five-minute window around a prompt.

### Heartbeat payload

Extend `bin/lowr-aw-terminal-heartbeat` to emit structured metadata when available:

```json
{
  "file": "/current/path",
  "project": "wam-crm",
  "repository": "/canonical/repository",
  "worktree": "/active/worktree",
  "branch": "feature/bug-reporting",
  "remote": "github.com/org/wam-crm"
}
```

Do not include the command line, environment variables, remotes containing credentials, diffs, or file contents.

### Correlation

1. Continue preferring true overlap.
2. Allow the most recent compatible terminal context to annotate a later IDE event.
3. Increase the permitted age only when supporting evidence agrees, for example when the editor title names the same repository.
4. Stop carrying context forward when a contradictory repository signal appears.
5. Make the maximum age configurable.

### Acceptance criteria

- A long IDE session can retain repository context despite sparse prompt heartbeats when its title agrees.
- Switching to another repository prevents stale context from leaking into later records.
- Heartbeats remain harmless when outside a Git repository.

## Slice 6: Query Git During Summarization

### Purpose

Use local Git history as the primary source of commit evidence, including for historical reports created before the ActivityWatch Git hook exists.

### Discovery

Build a unique list of repositories and worktrees from:

- Terminal evidence.
- Project path mappings.
- Window-title mappings that resolve to a configured local repository.
- Git ActivityWatch events, once available.

Do not recursively scan the user's home directory for repositories.

### Query

For each discovered repository or worktree:

1. Query commits within the configured day plus a small correlation margin.
2. Record full hash, subject, parent hashes, author/committer timestamps, and repository identity.
3. Prefer locally relevant commits by configured Git author identities and reachable worktree context.
4. Consider local reflog evidence when it helps distinguish a locally created commit from a fetched commit.
5. Do not read commit bodies or diffs in the first version.
6. Bound subprocess runtime and treat repository/query failures as non-fatal.

A commit does not intrinsically retain a branch name. Use branch/worktree evidence conservatively rather than claiming a historical branch without support.

### Correlation

Attach a commit to a record when:

- Canonical repository matches.
- Commit time falls inside the record or within a configured nearby margin.
- Branch/worktree/title evidence does not conflict.

A commit annotates existing activity; it must not create tracked time by itself.

### Acceptance criteria

- Historical reports gain commit evidence without requiring prior hook installation.
- A nearby commit attaches only to activity for the same repository.
- A fetched or unrelated commit is not presented as high-confidence local work.
- Missing or broken repositories do not prevent report generation.

## Slice 7: Record Git Commits in ActivityWatch

### Purpose

Capture precise local commit milestones at creation time, including commits later amended, rebased, or deleted.

### Bucket

Use a dedicated bucket:

```text
aw-watcher-git_<hostname>
```

Use a structured event type distinct from editor activity.

### Event payload

The `post-commit` collector should send:

```json
{
  "kind": "commit",
  "hash": "full commit hash",
  "subject": "Add bug report detail view",
  "repository": "/canonical/repository",
  "worktree": "/active/worktree",
  "branch": "feature/bug-reporting",
  "remote": "github.com/org/wam-crm",
  "parents": ["full parent hash"]
}
```

Sanitize remote URLs and never include credentials. Do not include diffs, commit bodies, arbitrary commands, environment values, or file contents.

### Hook installation

Update `bin/lowr-install-time-tracker` to:

1. Inspect system, global, and repository `core.hooksPath` behavior.
2. Detect an existing global hooks path and existing `post-commit` hook.
3. Never overwrite an existing hook silently.
4. Offer or install a Lowr-managed hook only when integration is safe.
5. Ensure worktrees use the same integration.
6. make the hook executable.
7. Explain that GUI clients must be restarted if their environment or PATH changes.

The installed hook should be a minimal dispatcher. It should invoke a stable Lowr path such as `~/.local/share/lowr/bin/lowr-aw-git-heartbeat` rather than depending on a GUI application's PATH.

### Runtime requirements

- Work from CLI, VS Code, Zed, and JetBrains when those clients invoke normal Git hooks.
- Use a short ActivityWatch timeout.
- Always exit successfully.
- Never delay or reject a commit because ActivityWatch, `curl`, `jq`, or Lowr is unavailable.
- Avoid duplicate hook output in editor UIs.

### Deduplication

Deduplicate Git-log and ActivityWatch evidence by:

```text
canonical repository identity + full commit hash
```

Preserve both sources on the merged evidence. An event found only in ActivityWatch can remain as historical evidence but should be marked as no longer found in current Git history.

### Acceptance criteria

- Commits from CLI, VS Code, and Zed produce equivalent structured events in a test repository.
- Committing succeeds while ActivityWatch is stopped.
- Existing hook configuration is not overwritten.
- One commit found through both sources appears once in the report evidence.

## Slice 8: Web Watcher Correlation

### Purpose

Use active browser context for pull requests, issues, work items, documentation, meetings, and known customer applications.

### Bucket configuration and discovery

Support explicit web buckets and safe discovery:

```toml
[buckets]
web = [
  "aw-watcher-web-chrome_lowrarch01",
  "aw-watcher-web-firefox_lowrarch01",
]
```

When discovering buckets, select compatible web-watcher bucket types rather than assuming one fixed browser name.

### Correlation

1. Query web events for the reporting period.
2. Correlate them with active browser window events.
3. Ignore background tabs that cannot be tied to active browser time.
4. Store the page title, hostname, and sanitized path as evidence.
5. Do not count web watcher heartbeats as additional time.

### Privacy

Strip by default:

- Query strings.
- URL fragments.
- Credentials.
- Tokens and signed parameters.

Provide config controls for retaining or redacting paths and titles before AI processing.

### Mapping

Allow repository/customer-specific URL patterns:

```toml
[[projects.web]]
project = "wam-crm"
host = "github.com"
path_patterns = ["*/wam-crm/issues/*", "*/wam-crm/pull/*"]
```

Use confidence levels:

- Repository-specific issue or pull-request page: high.
- Known customer application: medium or high according to config.
- Documentation matching surrounding repository work: supporting evidence.
- Generic search or unrelated browsing: no automatic assignment.

### Acceptance criteria

- An active repository pull-request page can annotate the matching project record.
- A background tab does not create or claim work time.
- Printed and AI-bound URLs exclude query strings and fragments by default.

## Slice 9: Deterministic Subjects and Descriptions

### Purpose

Produce useful descriptions without requiring AI.

### Description priority

Use evidence in this order:

1. One or more nearby Git commit subjects.
2. Pull-request, issue, or work-item title.
3. Strong task text from window titles.
4. Branch or worktree-derived subject.
5. Generic canonical-project development description.
6. `review needed`.

Examples:

| Evidence | Result |
| --- | --- |
| Commit `Add bug report detail view` | `Add bug report detail view` |
| Related implementation and test commits | `Implement and test bug report detail view` |
| Active PR titled `Add bug reporting workflow` | `Review pull request: Add bug reporting workflow` |
| `pitch--aw-time-tracker.md` in `lowr` | `Review ActivityWatch time-tracker pitch` |
| Branch `feature/bug-reporting` | `Work on bug reporting feature` |
| Canonical project only | `Development in wam-crm` |
| Insufficient evidence | `review needed` |

### Rules

1. Prefer concise action-oriented text suitable for a time record.
2. Do not claim completion merely because a related file was open.
3. Avoid listing every touched file or window title.
4. Preserve source and confidence internally:

```python
{
  "description_source": "git_commit",
  "description_confidence": "high",
}
```

5. Keep `review needed` for genuinely weak evidence.

### Acceptance criteria

- Commit-backed records receive concise descriptions.
- Branch-only records receive conservative descriptions.
- File names are not overstated as completed work.
- Descriptions are stable and testable for identical evidence.

## Slice 10: Opt-In AI Postprocessor

### Purpose

Summarize rich evidence for unresolved or weak records without giving AI control over the timeline.

### Invocation

Add an explicit option and configuration:

```toml
[ai]
enabled = false
provider = "pi"
timeout_seconds = 60
minimum_minutes = 15
include_urls = false
include_paths = true
allow_project_suggestion = true
```

Support a command-line override such as:

```text
lowr-aw-time-tracker --describe-with pi
lowr-aw-time-tracker --describe-with codex
lowr-aw-time-tracker --no-ai
lowr-aw-time-tracker --ai-dry-run
```

Verify the noninteractive invocation and output mode for each supported installed CLI version. Execute argument arrays without a shell, enforce a timeout, and parse strict JSON.

### Scope

Send only records that have:

- `review needed` descriptions;
- low-confidence deterministic descriptions; or
- several related evidence items that need concise consolidation.

Make one batched request per report where practical instead of invoking an agent for every ActivityWatch event.

### Authority boundaries

AI may propose:

- Subject.
- Description.
- A project for an currently unassigned record, with confidence and supporting evidence.

AI must not change:

- Start or end time.
- AFK handling.
- High-confidence canonical project assignments.
- Git hashes or source evidence.
- Deterministic facts.

Require output containing confidence and cited supplied evidence. Reject or ignore output that:

- Is not valid JSON.
- References evidence that was not supplied.
- Contradicts a high-confidence mapping.
- Changes record boundaries.
- Times out or exits unsuccessfully.

Fall back to deterministic output without failing the report.

### Privacy

1. Keep AI disabled by default.
2. Explain that a local CLI may still send prompts to a remote model.
3. Redact URL query strings, fragments, credentials, and secrets before invocation.
4. Allow users to exclude paths, URLs, titles, or commit subjects.
5. Provide `--ai-dry-run` to show the exact redacted payload without invoking AI.

### Acceptance criteria

- AI improves weak descriptions while preserving times and deterministic projects.
- Invalid, unavailable, or timed-out AI providers do not prevent report generation.
- No AI process is started unless enabled explicitly by config or CLI.
- Dry-run output matches the payload that would be sent.

## Configuration Migration

Evolve `config/lowr/time-tracker.toml` without breaking an existing user copy immediately.

1. Continue reading current `[noise].apps` and `[work_apps].apps` values.
2. Prefer the new alias and project sections when present.
3. Print actionable warnings only for invalid configuration, not merely older configuration.
4. Add a Lowr migration when a user config must be updated or refreshed.
5. Do not overwrite user mappings during refresh; use the existing Lowr config backup pattern.
6. Document new settings in the default config with minimal examples.

## Error Handling

All optional evidence sources must degrade gracefully:

- Missing web bucket: continue without web evidence.
- Missing Git repository: retain ActivityWatch evidence.
- Git command failure: warn in diagnostic mode and continue.
- ActivityWatch Git bucket missing: use Git query results.
- ActivityWatch unavailable: retain the existing clear connection error for the required primary source.
- AI unavailable or invalid: retain deterministic descriptions.
- Invalid required config: report the exact section and key.

Avoid swallowing programming errors that should fail tests. Graceful degradation applies to absent external evidence, not malformed internal state.

## Validation Strategy

Validate each slice from narrow to broad:

1. Unit tests for normalization, mappings, evidence merging, Git deduplication, URL sanitization, and description generation.
2. Fixture-driven report tests covering a complete day.
3. Shell checks for terminal and Git heartbeat scripts.
4. A temporary Git repository test for CLI commits.
5. Manual commit tests from VS Code and Zed.
6. A live ActivityWatch report comparison for at least one representative day.
7. AI dry-run tests that never contact a provider.
8. Optional provider contract tests when credentials and network access are intentionally available.

For live comparisons, record:

- Assigned-minute percentage before and after.
- Described-minute percentage before and after.
- Number of incorrect assignments.
- Number of records requiring manual correction.
- Duplicate or overlapping minutes.

Do not accept a higher assignment percentage if it comes from more incorrect guesses.

## Completion Criteria

The quality work is complete when:

- Zed, WezTerm, VS Code, and configured work applications are recognized reliably.
- Known repository paths, worktrees, titles, and URLs resolve to canonical projects.
- Worktree and branch names become subject evidence rather than duplicate project names.
- Evidence survives timeline merging and rounding.
- Git commits are available from both local Git queries and ActivityWatch hooks and are deduplicated.
- Browser evidence is correlated only with active browser time.
- Most strongly evidenced records receive deterministic descriptions.
- Weak records remain visibly reviewable.
- AI can improve unresolved descriptions but is optional, bounded, redacted, and unable to alter tracked time.
- Existing AFK, coffee-break, overlap, and rounding behavior remains covered and correct.

## Delivery Order Summary

Implement and validate the slices in this order:

1. Baseline fixtures and quality metrics.
2. Evidence-aware internal records.
3. Canonical application aliases.
4. Project mapping rules.
5. Repository and worktree normalization.
6. Better terminal evidence.
7. Query Git during summarization.
8. Record Git commits in ActivityWatch.
9. Correlate web watcher activity.
10. Generate deterministic descriptions.
11. Add the opt-in AI postprocessor.

This ordering first prevents evidence loss, then improves deterministic attribution, then adds stronger evidence sources, and only finally introduces probabilistic summarization.
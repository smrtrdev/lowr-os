# PITCH: worklife--shutdown

## Problem

Users want a hard boundary between work and personal time by automatically shutting down the computer during configured off-hours, for example between `22:00` and `04:30`.

A simple scheduled shutdown is not enough because the user may turn the computer back on during the blocked window. The system must recognize that it is still within the shutdown window, notify the user again, wait 5 minutes, and shut down again.

The service also needs a reliable audit trail of when shutdown warnings were issued. This should be stored in a SQLite database so future behavior can be inspected, debugged, or extended.

## Appetite

Small project: 1-2 days.

The goal is a focused local service, not a full productivity platform. It should be reliable, understandable, and easy to configure. The first version should support one or more fixed daily shutdown windows and a fixed warning delay of 5 minutes.

## Solution

Create a service named `work-life--shut-down`.

The service runs at startup and periodically checks whether the current local time falls inside a configured shutdown window, such as:

```text
22:00-04:30
```

When the computer is inside a shutdown window:

1. The service records a notification event in SQLite.
2. The user receives a desktop notification: `System will shut down in 5 minutes.`
3. The service waits 5 minutes.
4. If the current time is still inside the shutdown window, the service shuts down the machine.
5. If the user powers the computer back on and it is still inside the shutdown window, the same flow repeats.

SQLite stores notification events, for example:

```sql
CREATE TABLE shutdown_notifications (
  id INTEGER PRIMARY KEY,
  notified_at TEXT NOT NULL,
  shutdown_window_start TEXT NOT NULL,
  shutdown_window_end TEXT NOT NULL,
  shutdown_scheduled_for TEXT NOT NULL
);
```

Configuration can be kept simple:

```ini
SHUTDOWN_WINDOWS=22:00-04:30
WARNING_MINUTES=5
```

The service should treat overnight windows correctly, where the end time is earlier than the start time.

## Rabbit Holes

Avoid building a calendar system, rules engine, or complex recurrence format in the first version.

Avoid trying to detect user intent after reboot. If the current time is inside the configured blocked window, the service should notify and shut down again.

Avoid overengineering the database. The first version only needs to record when warnings were issued and which window caused them.

Avoid relying only on one-shot timers. The service needs to handle booting directly into an active shutdown window.

## No-Gos

No snooze button in the first version.

No GUI configuration panel.

No cloud sync or remote policy management.

No per-application blocking.

No automatic override based on active downloads, meetings, or unsaved work.

No silent shutdown. The user must always receive the 5-minute warning before shutdown.

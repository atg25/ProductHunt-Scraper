# Sprint 2 — Scheduler via Cron

## Sprint Goal

Automate scraper execution using a repeatable cron schedule.

## Backlog / Tasks

- Build a single-run pipeline command (scrape + persist) for scheduler reuse.
- Add cron configuration file and startup script for foreground execution.
- Add configurable schedule through environment variable (`CRON_SCHEDULE`).
- Add timezone support (`TZ`) and structured log output.
- Add tests for scheduler command path and basic schedule config validation.

## Acceptance Criteria

- Cron triggers scraper runs at the configured interval.
- Each scheduled run writes data to SQLite using the same code path as manual run.
- Scheduler logs clearly show run start, completion, and errors.
- Manual execution command remains available for ad hoc runs.

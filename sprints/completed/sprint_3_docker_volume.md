# Sprint 3 — Docker Containerization and Persistent Volume

## Sprint Goal

Containerize the scraper and scheduler, with SQLite persisted on a Docker volume.

## Backlog / Tasks

- Create Dockerfile for scraper/scheduler runtime.
- Create `docker-compose.yml` with scheduler service and volume mapping for DB file.
- Externalize runtime config (`DB_PATH`, `CRON_SCHEDULE`, `TZ`, optional token values).
- Validate container startup and cron execution inside container.
- Validate persistence across container restarts and rebuilds.
- Add smoke tests and runbook commands for container lifecycle.

## Acceptance Criteria

- `docker compose up` starts scheduled scraper pipeline successfully.
- SQLite file is written to a named volume and survives container restarts.
- Re-deploying containers does not lose historical records.
- Container logs show scheduled execution and persistence activity.

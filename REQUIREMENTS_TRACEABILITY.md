# Requirements Traceability Matrix

This matrix maps assignment requirements to implementation artifacts and verification steps.

| Assignment Requirement                     | Implementation                                                                                                                                                                                                                                                           | Verification                                                                                                                            |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| Save scraper output to SQLite database     | `SQLiteStore` in [src/ph_ai_tracker/storage.py](src/ph_ai_tracker/storage.py); default persistence in [src/ph_ai_tracker/**main**.py](src/ph_ai_tracker/__main__.py); one-shot scheduler persistence in [src/ph_ai_tracker/scheduler.py](src/ph_ai_tracker/scheduler.py) | `poetry run ph-ai-tracker-runner --strategy scraper --db-path ./data/ph_ai_tracker.db` then `sqlite3 ./data/ph_ai_tracker.db ".tables"` |
| Run scraper on repeating schedule via cron | Cron entrypoint and generated crontab in [scripts/cron/entrypoint.sh](scripts/cron/entrypoint.sh); schedule via `CRON_SCHEDULE`                                                                                                                                          | `docker compose logs -f scheduler` shows repeated scheduler runs                                                                        |
| Containerize scraper + cron scheduler      | Runtime image in [Dockerfile](Dockerfile); scheduler service in [docker-compose.yml](docker-compose.yml)                                                                                                                                                                 | `docker compose up -d --build` and verify `scheduler` container is running                                                              |
| SQLite persisted on Docker volume          | Named volume `ph_ai_tracker_data` mapped to `/data` in [docker-compose.yml](docker-compose.yml); DB path `/data/ph_ai_tracker.db`                                                                                                                                        | Restart containers (`docker compose down && docker compose up -d`) and verify run counts continue increasing                            |
| Exclude API service from scope             | No API server framework/routes added; only scraper + scheduler + persistence components                                                                                                                                                                                  | Repository has no API service entrypoint or web framework service                                                                       |

## Test Evidence

- Unit + integration + e2e suite: `poetry run pytest`
- Current expected status: all tests passing

## Demo Entry Point

- Demo script: [scripts/demo_pipeline.sh](scripts/demo_pipeline.sh)
- Runbook: [RUNBOOK.md](RUNBOOK.md)

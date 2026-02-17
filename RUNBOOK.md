# ph_ai_tracker Runbook

This runbook covers local execution, scheduler execution, Docker deployment, and SQLite verification.

## 1) Prerequisites

- Python 3.10+
- Poetry installed
- Docker + Docker Compose (for container workflow)
- Optional: Product Hunt token for API strategy (`PRODUCTHUNT_TOKEN`)

## 2) Local Setup

```bash
poetry install
```

Optional env vars:

```bash
export PH_AI_DB_PATH=./data/ph_ai_tracker.db
export PH_AI_TRACKER_STRATEGY=scraper
export PH_AI_TRACKER_SEARCH=AI
export PH_AI_TRACKER_LIMIT=20
```

## 3) Local One-Off Run (scrape + persist)

```bash
poetry run ph-ai-tracker-runner \
  --strategy scraper \
  --search AI \
  --limit 20 \
  --db-path ./data/ph_ai_tracker.db
```

Expected outcome:

- JSON result printed to stdout
- SQLite DB created at `./data/ph_ai_tracker.db`
- New row in `runs` and related rows in `products` + `product_snapshots`

## 4) CLI Run with Persistence

```bash
poetry run ph-ai-tracker --strategy scraper --search AI --limit 10
```

Default persistence path: `./data/ph_ai_tracker.db`

Disable persistence for one-off testing:

```bash
poetry run ph-ai-tracker --strategy scraper --no-persist
```

## 5) Scheduler Runtime (single cycle)

```bash
poetry run ph-ai-tracker-runner --strategy scraper --db-path ./data/ph_ai_tracker.db
```

Retry controls:

```bash
poetry run ph-ai-tracker-runner \
  --retry-attempts 3 \
  --retry-backoff-seconds 2
```

## 6) Docker Deployment (cron scheduler)

Build and start:

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f scheduler
```

Stop (retain data volume):

```bash
docker compose down
```

## 7) Persistence Verification

The database lives in Docker volume `ph_ai_tracker_data` at `/data/ph_ai_tracker.db`.

Verify volume exists:

```bash
docker volume ls | grep ph_ai_tracker_data
```

Run DB checks locally (if DB is local path):

```bash
sqlite3 ./data/ph_ai_tracker.db ".tables"
sqlite3 ./data/ph_ai_tracker.db "SELECT COUNT(*) FROM runs;"
```

Run DB checks inside scheduler container:

```bash
docker compose exec scheduler sh -lc "python - <<'PY'
import sqlite3
conn = sqlite3.connect('/data/ph_ai_tracker.db')
for table in ('runs','products','product_snapshots'):
    count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(table, count)
conn.close()
PY"
```

## 8) Troubleshooting

### Problem: `python: command not found`

Use `poetry run python ...` inside this project (Poetry-managed env).

### Problem: `Missing api_token`

Set token or use scraper strategy:

```bash
export PRODUCTHUNT_TOKEN=<token>
poetry run ph-ai-tracker-runner --strategy api
```

### Problem: DB file not written

- Check `PH_AI_DB_PATH` or `--db-path`
- Ensure parent directory is writable
- Check stderr for `failed to persist run`

### Problem: Cron appears idle in Docker

- Confirm schedule env: `CRON_SCHEDULE`
- Check container logs: `docker compose logs -f scheduler`
- Use aggressive test schedule: `*/2 * * * *`

### Problem: Data missing after restart

- Ensure you used `docker compose down` (without `-v`)
- `docker compose down -v` deletes named volumes

## 9) Validation Checklist

- [ ] `poetry run pytest` passes
- [ ] one local run writes DB rows
- [ ] docker scheduler starts and logs cycles
- [ ] DB persists across container restart
- [ ] run counts increase over time

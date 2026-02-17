# ph_ai_tracker

A small Python library that finds trending AI products on Product Hunt.

- Primary: Product Hunt GraphQL API v2
- Secondary: Web scraping fallback (BeautifulSoup) for when the API is unavailable / rate-limited

## Install (dev)

```bash
poetry install
```

## Install (PyPI)

```bash
pip install ph-ai-tracker
```

Optional (faster HTML parsing with lxml):

```bash
pip install "ph-ai-tracker[lxml]"
```

## Quickstart

```python
from ph_ai_tracker import AIProductTracker

tracker = AIProductTracker(
    api_token="YOUR_PRODUCTHUNT_TOKEN",  # optional
    strategy="auto",                    # api | scraper | auto
)

result = tracker.get_products(search_term="AI", limit=20)
print(result.to_pretty_json())
```

Or from the terminal (prints pretty JSON):

```bash
poetry run python -m ph_ai_tracker --strategy scraper --search AI --limit 10
```

By default, each run is also persisted to SQLite at `./data/ph_ai_tracker.db`.

```bash
poetry run python -m ph_ai_tracker --strategy scraper --db-path ./data/ph_ai_tracker.db
```

Use `--no-persist` to skip DB writes for one-off runs.

## Scheduler (Sprint 2)

Run one scheduled cycle (scrape + persist) via the scheduler command:

```bash
poetry run ph-ai-tracker-runner --strategy scraper --search AI --limit 20 --db-path ./data/ph_ai_tracker.db
```

Environment variables supported by scheduler runtime:

- `CRON_SCHEDULE` (default: `0 */6 * * *`)
- `TZ` (default: `UTC`)
- `PH_AI_TRACKER_STRATEGY` (default: `scraper`)
- `PH_AI_TRACKER_SEARCH` (default: `AI`)
- `PH_AI_TRACKER_LIMIT` (default: `20`)
- `PH_AI_DB_PATH` (default: `./data/ph_ai_tracker.db`)
- `PRODUCTHUNT_TOKEN` (required for API strategy)
- `PH_AI_RETRY_ATTEMPTS` (default: `2`)
- `PH_AI_RETRY_BACKOFF_SECONDS` (default: `2`)

Cron helper files are available in `scripts/cron/`.

## Docker + Persistent Volume (Sprint 3)

Build and start the scheduler container:

```bash
docker compose up -d --build
```

Watch scheduler logs:

```bash
docker compose logs -f scheduler
```

The SQLite database is stored on the named Docker volume `ph_ai_tracker_data`
at `/data/ph_ai_tracker.db` in the container.

Stop without deleting data:

```bash
docker compose down
```

If you remove containers and start again, data persists because the named volume
is reused.

After installing from PyPI, you can also run:

```bash
ph-ai-tracker --strategy scraper --search AI --limit 10
```

## Trending behavior

- `--strategy api` defaults to Product Hunt's `RANKING` order.
- The API client first attempts the `artificial-intelligence` topic; if the schema/topic query fails, it falls back to global posts and applies a client-side filter.

## Product Hunt API token

Do **not** hardcode tokens in code or commit them to git.

Set your token as an environment variable:

```bash
export PRODUCTHUNT_TOKEN="<your_token>"
poetry run python -m ph_ai_tracker --strategy api --search AI --limit 10
```

## Notes

- This project is intended to run well on PyPy 3.
- All tests are offline and use mocks/fixtures (no real network).
- Supported Python versions: 3.10–3.14
- Operational guide: see `RUNBOOK.md`
- Convenience commands: `make test`, `make runner`, `make docker-up`, `make docker-logs`
- Demo script: `scripts/demo_pipeline.sh`
- Requirements mapping: `REQUIREMENTS_TRACEABILITY.md`
- Final handoff checklist: `SUBMISSION_CHECKLIST.md`

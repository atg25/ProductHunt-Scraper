# ph_ai_tracker

**Fetch trending AI products from Product Hunt — via API or web scraping — and store every run in a local SQLite database.**

Works as a one-shot CLI command, a Python library, a scheduled background service, or a Docker container.

---

## Table of Contents

1. [What it does](#what-it-does)
2. [Installation](#installation)
3. [CLI usage](#cli-usage)
4. [Python library usage](#python-library-usage)
5. [Output format](#output-format)
6. [Data strategies](#data-strategies)
7. [SQLite persistence](#sqlite-persistence)
8. [Scheduler (recurring runs)](#scheduler-recurring-runs)
9. [Docker deployment](#docker-deployment)
10. [Environment variables](#environment-variables)
11. [Make shortcuts](#make-shortcuts)
12. [Project layout](#project-layout)

---

## What it does

`ph_ai_tracker` searches Product Hunt for products related to a keyword (default: `"AI"`) and returns a structured list with names, taglines, descriptions, vote counts, URLs, and topics.

Every run can be automatically saved to a SQLite database so you can track which products appeared over time, how their vote counts changed, and when each run succeeded or failed.

Key capabilities at a glance:

| Feature        | Details                                              |
| -------------- | ---------------------------------------------------- |
| Data sources   | Product Hunt GraphQL API v2 + HTML scraping fallback |
| Output         | Pretty-printed JSON to stdout                        |
| Persistence    | SQLite — full audit history across runs              |
| Scheduling     | Built-in cron-style scheduler with retry logic       |
| Deployment     | Docker container with a named persistent volume      |
| Python support | 3.10 – 3.14, including PyPy 3                        |

---

## Installation

**For development (all extras):**

```bash
poetry install
```

**From PyPI:**

```bash
pip install ph-ai-tracker
```

**Optional — faster HTML parsing:**

```bash
pip install "ph-ai-tracker[lxml]"
```

---

## CLI usage

Run a one-shot fetch and print results as JSON:

```bash
# Scraper strategy (no API token needed)
python -m ph_ai_tracker --strategy scraper --search AI --limit 10

# API strategy (requires PRODUCTHUNT_TOKEN)
python -m ph_ai_tracker --strategy api --search AI --limit 20

# Auto strategy — tries API first, falls back to scraper
python -m ph_ai_tracker --strategy auto --search "machine learning" --limit 15

# Custom database path
python -m ph_ai_tracker --strategy scraper --db-path ./data/mydb.db

# Skip database write (one-off query)
python -m ph_ai_tracker --strategy scraper --no-persist
```

If installed as a package entry point, the `ph-ai-tracker` command is also available:

```bash
ph-ai-tracker --strategy scraper --search AI --limit 10
```

### CLI flags

| Flag           | Default                   | Description                          |
| -------------- | ------------------------- | ------------------------------------ |
| `--strategy`   | `scraper`                 | `api`, `scraper`, or `auto`          |
| `--search`     | `AI`                      | Keyword filter applied to results    |
| `--limit`      | `20`                      | Maximum number of products to return |
| `--db-path`    | `./data/ph_ai_tracker.db` | SQLite file location                 |
| `--token`      | _(env)_                   | Product Hunt API token               |
| `--no-persist` | off                       | Skip writing to the database         |

### Exit codes

| Code | Meaning                                                    |
| ---- | ---------------------------------------------------------- |
| `0`  | Success                                                    |
| `2`  | Fetch completed but returned an error (data still printed) |
| `3`  | Database write failed                                      |

---

## Python library usage

```python
from ph_ai_tracker.bootstrap import build_provider
from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.storage import SQLiteStore

# Build a provider for your chosen strategy
provider = build_provider(strategy="auto", api_token="YOUR_TOKEN")

# Fetch products
tracker = AIProductTracker(provider=provider)
result = tracker.get_products(search_term="AI", limit=20)

# Inspect the result
print(result.to_pretty_json())
print(result.error)        # None on success, error message on failure
print(result.is_transient) # True if the error is retry-safe (rate limit, timeout)
print(result.search_term)  # "AI"
print(result.limit)        # 20

# Iterate over products
for product in result.products:
    print(product.name, product.votes_count, product.url)

# Persist to SQLite
store = SQLiteStore("./data/ph_ai_tracker.db")
store.init_db()
run_id = store.save_result(result)
print(f"Saved as run #{run_id}")
```

### `Product` fields

| Field         | Type              | Description                         |
| ------------- | ----------------- | ----------------------------------- |
| `name`        | `str`             | Product title (required, non-empty) |
| `tagline`     | `str or None`     | Short one-line description          |
| `description` | `str or None`     | Full description                    |
| `votes_count` | `int`             | Upvote count at time of fetch       |
| `url`         | `str or None`     | Product Hunt listing URL            |
| `topics`      | `tuple[str, ...]` | Category tags                       |

`product.searchable_text` returns a lowercase string combining all text fields — useful for filtering.

### `TrackerResult` fields

| Field          | Type                  | Description                             |
| -------------- | --------------------- | --------------------------------------- |
| `products`     | `tuple[Product, ...]` | The fetched products (empty on failure) |
| `source`       | `str`                 | Which strategy produced the data        |
| `fetched_at`   | `datetime`            | UTC timestamp of the fetch              |
| `error`        | `str or None`         | Error message, or `None` on success     |
| `is_transient` | `bool`                | `True` if the error is retry-safe       |
| `search_term`  | `str`                 | The keyword used for this run           |
| `limit`        | `int`                 | The limit used for this run             |

`result.to_pretty_json()` serializes the full result (including all products) to an indented JSON string.

---

## Output format

Every run prints a JSON object to stdout. Example:

```json
{
  "source": "producthunt_scraper",
  "fetched_at": "2026-02-20T14:00:00+00:00",
  "search_term": "AI",
  "limit": 10,
  "error": null,
  "products": [
    {
      "name": "Example AI Tool",
      "tagline": "Do things faster with AI",
      "description": "A longer description...",
      "votes_count": 342,
      "url": "https://www.producthunt.com/posts/example-ai-tool",
      "topics": ["Artificial Intelligence", "Productivity"]
    }
  ]
}
```

On error, `"products"` is an empty array and `"error"` contains the message.

---

## Data strategies

**`scraper`** — Fetches the Product Hunt website directly using HTTP + BeautifulSoup. No API token required. Falls back gracefully when individual product pages fail enrichment.

**`api`** — Uses the official Product Hunt GraphQL API v2. Returns richer data. Requires a `PRODUCTHUNT_TOKEN` (see below). First queries the `artificial-intelligence` topic; if that shape is unavailable, falls back to global posts with a client-side keyword filter. Results are returned in `RANKING` order.

**`auto`** — Tries the API first; if it fails (rate limit, missing token, network error), automatically falls back to the scraper. Best for production use when uptime matters.

---

## SQLite persistence

Every run writes three tables:

| Table               | Contents                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------- |
| `runs`              | One row per `get_products()` call — source, timestamp, search term, limit, status, error    |
| `products`          | One row per unique product, deduplicated by URL or name                                     |
| `product_snapshots` | One row per (run, product) — records votes, tagline, and description at that moment in time |

Product identity is decided by the database: the `canonical_key` column (URL preferred, name as fallback) has a `UNIQUE` constraint. Duplicate products are upserted, not duplicated.

Run status values: `success`, `partial`, `failure`.

You can pass an explicit status override when saving:

```python
store.save_result(result, status="partial")
```

> **Note:** call `store.init_db()` once before the first call to `save_result()`. This creates the schema if it does not already exist.

---

## Scheduler (recurring runs)

The `ph-ai-tracker-runner` command runs one full fetch-and-persist cycle with automatic retry on transient errors:

```bash
ph-ai-tracker-runner \
  --strategy scraper \
  --search AI \
  --limit 20 \
  --db-path ./data/ph_ai_tracker.db
```

Or with `poetry run`:

```bash
poetry run ph-ai-tracker-runner --strategy auto --search AI --limit 20
```

The scheduler retries failed fetches up to `PH_AI_RETRY_ATTEMPTS` times with exponential backoff before writing a `failure` run to the database. This makes it safe to run on a cron interval without manual intervention.

Cron helper scripts are in `scripts/cron/`.

---

## Docker deployment

Build and start the container (runs the scheduler on the configured cron schedule):

```bash
docker compose up -d --build
```

Stream logs:

```bash
docker compose logs -f scheduler
```

Stop (data is preserved):

```bash
docker compose down
```

The SQLite database lives on the named Docker volume `ph_ai_tracker_data` at `/data/ph_ai_tracker.db` inside the container. The volume persists across container restarts and re-builds.

---

## Environment variables

All flags can be set via environment variables. CLI flags take precedence.

| Variable                      | CLI equivalent     | Default                   | Description                             |
| ----------------------------- | ------------------ | ------------------------- | --------------------------------------- |
| `PH_AI_TRACKER_STRATEGY`      | `--strategy`       | `scraper`                 | Data strategy                           |
| `PH_AI_TRACKER_SEARCH`        | `--search`         | `AI`                      | Keyword filter                          |
| `PH_AI_TRACKER_LIMIT`         | `--limit`          | `20`                      | Max products                            |
| `PH_AI_DB_PATH`               | `--db-path`        | `./data/ph_ai_tracker.db` | SQLite path                             |
| `PRODUCTHUNT_TOKEN`           | `--token`          | _(none)_                  | API token (required for `api` strategy) |
| `CRON_SCHEDULE`               | _(scheduler only)_ | `0 */6 * * *`             | Cron expression for Docker              |
| `TZ`                          | _(scheduler only)_ | `UTC`                     | Timezone for cron                       |
| `PH_AI_RETRY_ATTEMPTS`        | _(scheduler only)_ | `2`                       | Retry count on transient errors         |
| `PH_AI_RETRY_BACKOFF_SECONDS` | _(scheduler only)_ | `2`                       | Base backoff delay in seconds           |

**Never hardcode your API token.** Set it as an environment variable:

```bash
export PRODUCTHUNT_TOKEN="your_token_here"
python -m ph_ai_tracker --strategy api --search AI --limit 10
```

---

## Make shortcuts

```bash
make test          # Run the full test suite
make bundle        # Generate codebase_review_bundle.txt
make runner        # Start the scheduler (foreground)
make docker-up     # Build and start the Docker container
make docker-logs   # Stream Docker container logs
```

---

## Project layout

```
src/ph_ai_tracker/
├── __main__.py      # CLI entry point
├── tracker.py       # AIProductTracker — core use-case facade
├── models.py        # Product and TrackerResult dataclasses
├── api_client.py    # Product Hunt GraphQL API client
├── scraper.py       # BeautifulSoup HTML scraper
├── bootstrap.py     # Provider factory (builds correct strategy)
├── storage.py       # SQLiteStore — persistence layer
├── scheduler.py     # Recurring run scheduler with retry logic
├── cli.py           # Shared CLI argument definitions
├── constants.py     # Default values
├── exceptions.py    # Domain exceptions
└── protocols.py     # ProductProvider interface

scripts/
├── demo_pipeline.sh           # End-to-end demo script
└── cron/                      # Cron entrypoint helpers for Docker

tests/
├── unit/                      # Pure unit tests (no network, no disk)
├── integration/               # Integration tests against real SQLite
└── e2e/                       # End-to-end smoke tests
```

Additional documentation:

- [RUNBOOK.md](RUNBOOK.md) — operational guide (start, stop, backup, recover)
- [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) — requirement-to-code mapping
- [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) — final handoff checklist

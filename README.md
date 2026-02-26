# ph_ai_tracker

**Fetch trending AI products from Product Hunt — via API or web scraping — and store every run in a local SQLite database.**

Works as a one-shot CLI command, a Python library, a scheduled background service, or a Docker container.

---

## Table of Contents

1. [What it does](#what-it-does)
2. [Installation](#installation)
3. [CLI usage](#cli-usage)
4. [HTTP API](#http-api)
5. [Python library usage](#python-library-usage)
6. [Output format](#output-format)
7. [Data strategies](#data-strategies)
8. [AI Tagging](#ai-tagging)
9. [SQLite persistence](#sqlite-persistence)
10. [Scheduler (recurring runs)](#scheduler-recurring-runs)
11. [Docker deployment](#docker-deployment)
12. [Environment variables](#environment-variables)
13. [Make shortcuts](#make-shortcuts)
14. [Project layout](#project-layout)

---

## What it does

`ph_ai_tracker` searches Product Hunt for products related to a keyword (default: `"AI"`) and returns a structured list with names, taglines, descriptions, vote counts, URLs, topics, and post timestamps.

By default, results are constrained to products posted in the last 7 days (when Product Hunt provides post timestamps), then sorted by trending votes and truncated to your limit (default 10).

Every run can be automatically saved to a SQLite database so you can track which products appeared over time, how their vote counts changed, and when each run succeeded or failed.

Key capabilities at a glance:

| Feature        | Details                                              |
| -------------- | ---------------------------------------------------- |
| Data sources   | Product Hunt GraphQL API v2 + HTML scraping fallback |
| AI Tagging     | Optional OpenAI-powered product categorization       |
| Output         | Newsletter-style JSON with tag analytics to stdout   |
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

## HTTP API

Start the API server:

```bash
make serve
```

This runs:

```bash
poetry run uvicorn ph_ai_tracker.api:app --host 0.0.0.0 --port 8000 --reload
```

When the API module starts, it auto-loads key/value pairs from `.env` in the project root (without overriding already-exported environment variables), so `OPENAI_API_KEY` in `.env` is picked up for tagging.

Endpoints:

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/health` | Liveness check; returns `{"status": "ok"}` |
| `GET` | `/products/search` | Live scrape and persist, returns newsletter JSON (recent 7-day window when timestamps are available) |
| `GET` | `/products/history` | Read persisted product observations |

`/products/search` query parameters:

| Parameter | Default | Rules |
| --------- | ------- | ----- |
| `q` | `AI` | 1-100 chars |
| `limit` | `10` | 1-50 |
| `strategy` | `auto` | `api` / `scraper` / `auto` |

`/products/history` query parameters:

| Parameter | Default | Rules |
| --------- | ------- | ----- |
| `limit` | `50` | 1-500 |

Example:

```bash
curl "http://127.0.0.1:8000/products/search?q=AI&limit=10&strategy=auto"
curl "http://127.0.0.1:8000/products/history?limit=25"
```

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

| Field         | Type              | Description                                        |
| ------------- | ----------------- | -------------------------------------------------- |
| `name`        | `str`             | Product title (required, non-empty)                |
| `tagline`     | `str or None`     | Short one-line description                         |
| `description` | `str or None`     | Full description                                   |
| `votes_count` | `int`             | Upvote count at time of fetch                      |
| `url`         | `str or None`     | Product Hunt listing URL                           |
| `topics`      | `tuple[str, ...]` | Category tags from Product Hunt                    |
| `tags`        | `tuple[str, ...]` | AI-assigned categories (requires `OPENAI_API_KEY`) |
| `posted_at`   | `datetime or None`| Product Hunt post/release timestamp (if available) |

`product.searchable_text` returns a lowercase string combining all text fields — useful for filtering.

`product.tags` is populated by the optional AI tagging service (see [AI Tagging](#ai-tagging) below).

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

Every run prints a JSON object to stdout in newsletter format. Products are sorted by vote count (descending), and the output includes analytics on top tags across the result set.

Example:

```json
{
  "generated_at": "2026-02-20T14:00:00+00:00",
  "total_products": 3,
  "top_tags": [
    { "tag": "ai", "count": 3 },
    { "tag": "productivity", "count": 2 },
    { "tag": "machine-learning", "count": 1 }
  ],
  "products": [
    {
      "name": "Example AI Tool",
      "tagline": "Do things faster with AI",
      "description": "A longer description...",
      "url": "https://www.producthunt.com/posts/example-ai-tool",
      "votes": 342,
      "topics": ["Artificial Intelligence", "Productivity"],
      "tags": ["ai", "productivity"],
      "posted_at": "2026-02-25T12:00:00+00:00"
    }
  ]
}
```

Fields:

- **`generated_at`** – ISO 8601 timestamp of when the output was created (UTC).
- **`total_products`** – Count of products in the result set.
- **`top_tags`** – List of the most common AI-assigned tags with their frequency (sorted by count, then alphabetically).
- **`products`** – Array of products, sorted by vote count (highest first), then by name.
  - **`tags`** – AI-assigned categories from the tagging service (empty if tagging is disabled).
  - **`posted_at`** – Product Hunt post/release timestamp when available from upstream data.

---

## Data strategies

**`scraper`** — Fetches the Product Hunt homepage directly using HTTP + BeautifulSoup (Top Products Launching Today section). No API token required. Falls back gracefully when individual product pages fail enrichment.

**`api`** — Uses the official Product Hunt GraphQL API v2. Returns richer data. Requires a `PRODUCTHUNT_TOKEN` (see below). First queries the `artificial-intelligence` topic; if that shape is unavailable, falls back to global posts with a client-side keyword filter. Results are returned in `RANKING` order.

**`auto`** — Tries the API first; if it fails (rate limit, missing token, network error), automatically falls back to the scraper. Best for production use when uptime matters.

---

## AI Tagging

Products can be automatically categorized using an OpenAI-compatible LLM service. This is **optional** and controlled by the `OPENAI_API_KEY` environment variable.

### How it works

1. Each product is sent to an OpenAI-compatible API (default: OpenAI, configurable via `OPENAI_BASE_URL`).
2. The LLM generates 1–3 category tags based on the product's name, tagline, and description.
3. Tags are validated, deduplicated, and stored in the `tags` field of each product.
4. If no API key is configured, the tagging service is a no-op and all products have empty tags.
5. If the API call fails for any reason, the product is still returned with empty tags (graceful degradation).

### Configuration

| Environment Variable | Default                     | Description                              |
| -------------------- | --------------------------- | ---------------------------------------- |
| `OPENAI_API_KEY`     | _(required for tagging)_    | API key for OpenAI or compatible service |
| `OPENAI_BASE_URL`    | `https://api.openai.com/v1` | Base URL for the LLM service             |

Example:

```bash
export OPENAI_API_KEY="sk-..."
python -m ph_ai_tracker --strategy scraper --search AI --limit 10
```

Now each product in the output will have a `tags` field with AI-generated categories.

### In the codebase

- **Implementation:** [`src/ph_ai_tracker/tagging.py`](src/ph_ai_tracker/tagging.py) — `NoOpTaggingService` (disabled) and `UniversalLLMTaggingService` (OpenAI-compatible).
- **Protocol:** [`src/ph_ai_tracker/protocols.py`](src/ph_ai_tracker/protocols.py) — `TaggingService` interface.
- **Bootstrap:** [`src/ph_ai_tracker/bootstrap.py`](src/ph_ai_tracker/bootstrap.py) — `build_tagging_service()` factory function.

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

All CLI flags can be set via environment variables. CLI flags take precedence.

**Fetch & storage:**

| Variable                 | CLI equivalent | Default                   | Description                             |
| ------------------------ | -------------- | ------------------------- | --------------------------------------- |
| `PH_AI_TRACKER_STRATEGY` | `--strategy`   | `scraper`                 | Data strategy                           |
| `PH_AI_TRACKER_SEARCH`   | `--search`     | `AI`                      | Keyword filter                          |
| `PH_AI_TRACKER_LIMIT`    | `--limit`      | `20`                      | Max products                            |
| `PH_AI_DB_PATH`          | `--db-path`    | `./data/ph_ai_tracker.db` | SQLite path                             |
| `PRODUCTHUNT_TOKEN`      | `--token`      | _(none)_                  | API token (required for `api` strategy) |

**AI Tagging (optional):**

| Variable          | Default                     | Description                                      |
| ----------------- | --------------------------- | ------------------------------------------------ |
| `OPENAI_API_KEY`  | _(none; tagging disabled)_  | API key for OpenAI or compatible provider        |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Base URL for the LLM service (OpenAI-compatible) |

**Scheduler & retry logic (Docker/background runners):**

| Variable                      | _(scheduler only)_ | Default       | Description                     |
| ----------------------------- | ------------------ | ------------- | ------------------------------- |
| `CRON_SCHEDULE`               | _(scheduler only)_ | `0 */6 * * *` | Cron expression for Docker      |
| `TZ`                          | _(scheduler only)_ | `UTC`         | Timezone for cron               |
| `PH_AI_RETRY_ATTEMPTS`        | _(scheduler only)_ | `2`           | Retry count on transient errors |
| `PH_AI_RETRY_BACKOFF_SECONDS` | _(scheduler only)_ | `2`           | Base backoff delay in seconds   |

**Never hardcode your API tokens.** Set them as environment variables:

```bash
export PRODUCTHUNT_TOKEN="your_token_here"
export OPENAI_API_KEY="sk_..."
python -m ph_ai_tracker --strategy api --search AI --limit 10
```

---

## Make shortcuts

```bash
make test          # Run the full test suite
make bundle        # Generate codebase_review_bundle.txt
make runner        # Start the scheduler (foreground)
make serve         # Start the HTTP API (FastAPI + uvicorn)
make docker-up     # Build and start the Docker container
make docker-logs   # Stream Docker container logs
```

---

## Project layout

```
src/ph_ai_tracker/
├── __main__.py          # CLI entry point
├── tracker.py           # AIProductTracker — core use-case facade
├── models.py            # Product and TrackerResult dataclasses
├── api_client.py        # Product Hunt GraphQL API client
├── scraper.py           # BeautifulSoup HTML scraper
├── tagging.py           # AI product categorization service
├── formatters.py        # Output formatters (NewsletterFormatter)
├── bootstrap.py         # Provider & tagging service factories
├── api.py               # FastAPI HTTP endpoints
├── storage.py           # SQLiteStore — persistence layer
├── scheduler.py         # Recurring run scheduler with retry logic
├── cli.py               # Shared CLI argument definitions
├── constants.py         # Default values
├── exceptions.py        # Domain exceptions
└── protocols.py         # ProductProvider & TaggingService interfaces

scripts/
├── demo_pipeline.sh           # End-to-end demo script
├── build_bundle.py            # Generates codebase_review_bundle.txt
└── cron/                      # Cron entrypoint helpers for Docker
    ├── entrypoint.sh          # Scheduler entrypoint
    └── crontab.example        # Example cron configuration

tests/
├── unit/                      # Pure unit tests (no network, no disk)
├── integration/               # Integration tests against real SQLite
└── e2e/                       # End-to-end smoke tests
```

Additional documentation:

- [RUNBOOK.md](RUNBOOK.md) — operational guide (start, stop, backup, recover)
- [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) — requirement-to-code mapping
- [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) — final handoff checklist

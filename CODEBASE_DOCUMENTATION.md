# ph_ai_tracker: Complete Codebase Documentation

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Data Models](#data-models)
5. [Data Flow](#data-flow)
6. [Operational Modes](#operational-modes)
7. [Key Design Patterns](#key-design-patterns)
8. [Configuration & Defaults](#configuration--defaults)
9. [Error Handling](#error-handling)
10. [Extension Points](#extension-points)

---

## Project Overview

**ph_ai_tracker** is a production-grade Python library and CLI tool that fetches trending AI products from Product Hunt and persists them in a local SQLite database. It works as a standalone CLI command, a Python library, a scheduled background service, an HTTP API, or a Docker container.

### Core Capabilities

| Capability         | Implementation                                       |
| ------------------ | ---------------------------------------------------- |
| **Data Sources**   | Product Hunt GraphQL API v2 + HTML scraping fallback |
| **Search**         | Keyword-based search (default: "AI")                 |
| **Filtering**      | Optional temporal filtering (last 7 days by default) |
| **Enrichment**     | OpenAI-powered product categorization (optional)     |
| **Persistence**    | SQLite database with full audit history              |
| **Scheduling**     | Built-in cron-style scheduler with retry logic       |
| **Deployment**     | Docker container with persistent volumes             |
| **Python Support** | 3.10+ (including PyPy 3)                             |

---

## Architecture

### High-Level Design

The codebase follows **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────┐
│  Entry Points (CLI, HTTP API, Scheduler)        │
├─────────────────────────────────────────────────┤
│  Use-Case Layer (AIProductTracker)              │
│  - Business logic facade                        │
├─────────────────────────────────────────────────┤
│  Data Layer (Providers & Storage)               │
│  - ProductProvider (API/Scraper)                │
│  - SQLiteStore                                  │
│  - TaggingService                               │
├─────────────────────────────────────────────────┤
│  Domain Layer (Models & Protocols)              │
│  - Product, TrackerResult (immutable)           │
│  - Protocol-based abstractions                  │
├─────────────────────────────────────────────────┤
│  External Services                              │
│  - Product Hunt API (GraphQL)                   │
│  - Product Hunt Website (HTML scraping)         │
│  - OpenAI API (optional tagging)                │
└─────────────────────────────────────────────────┘
```

### Architectural Principles

1. **Immutability**: Core domain models (`Product`, `TrackerResult`) are frozen dataclasses to prevent accidental mutation.
2. **Protocol-Based Abstraction**: `ProductProvider` and `TaggingService` are protocols (structural typing) allowing flexible implementations.
3. **Separation of Concerns**: Each module has a single, well-defined responsibility.
4. **Composition Over Inheritance**: Providers are composed with fallback strategies rather than class hierarchies.
5. **Never Raises on Known Domain Errors**: `AIProductTracker.get_products()` captures known errors in the result object, never raising.

---

## Core Components

### 1. Entry Points

#### \***\*main**.py\*\* — CLI Execution

Implements the primary command-line interface. When users run `python -m ph_ai_tracker`, this module:

- Parses command-line arguments
- Builds the provider stack via bootstrap
- Executes the tracker
- Optionally persists results to SQLite
- Formats output as JSON

**Key Functions:**

- `main()`: Orchestrates the CLI flow
- `_fetch_result()`: Builds provider and executes tracker
- `_write_newsletter()`: Formats output as JSON
- `_try_persist()`: Handles database write with error recovery

**Exit Codes:**

- `0`: Success
- `3`: Storage error (database write failed)

#### **api.py** — HTTP API

FastAPI-based REST service exposing tracker functionality via HTTP. Provides:

- Health check endpoint
- Product fetch endpoints with strategy parameter
- Database history query endpoint
- Environment variable loading from `.env`

**Key Endpoints:**

- `GET /health`: Health status
- `GET /fetch`: Fetch products with strategy/search/limit parameters
- `GET /history`: Query SQLite history

#### **scheduler.py** — Background Scheduler

CLI entry point for recurring execution (via cron or container orchestration). Features:

- Cron expression parsing
- Transient error retry logic
- Result classification (success/partial/failure)
- JSON-serialized status output

**Key Classes:**

- `ScheduleConfig`: Immutable schedule configuration
- `RunConfig`: Immutable runtime configuration

### 2. Use-Case Layer

#### **tracker.py** — AIProductTracker (Facade)

The central use-case orchestrator. Acts as a facade that:

- Injects a provider to fetch products
- Injects a tagging service for enrichment
- Maps domain exceptions to result objects
- Never raises on known errors

**Key Method:**

```python
def get_products(
    *,
    search_term: str = DEFAULT_SEARCH_TERM,
    limit: int = DEFAULT_LIMIT
) -> TrackerResult:
```

**Invariant:** `get_products()` captures `RateLimitError`, `ScraperError`, and `APIError` as failures in `TrackerResult`. Unknown exceptions may propagate.

### 3. Data Layer — Providers

#### **Abstraction: ProductProvider (Protocol)**

Any object that implements:

```python
class ProductProvider(Protocol):
    source_name: str
    def fetch_products(*, search_term: str, limit: int) -> list[Product]: ...
    def close() -> None: ...
```

#### **api_client.py — ProductHuntAPI**

GraphQL API client for official Product Hunt integration.

**Features:**

- Connects to `https://api.producthunt.com/v2/api/graphql`
- Fetches from the `artificial-intelligence` topic by default
- Falls back to global `posts` topic if schema changes
- Oversamples results (requests 5x the limit) for client-side filtering
- Parses rate-limit headers into `RateLimitInfo` object
- Handles bearer token authentication

**Rate Limit Handling:**
Extracts and reports:

- `X-Rate-Limit-Limit`: Total quota
- `X-Rate-Limit-Remaining`: Requests left
- `X-Rate-Limit-Reset`: Unix timestamp of reset
- `Retry-After`: Suggested backoff in seconds

#### **scraper.py — ProductHuntScraper**

HTML-based fallback when API is unavailable. Uses two extraction paths:

**Primary Path:**

- Extracts `__NEXT_DATA__` JSON blob from Next.js embedded data
- Walks nested structure to find product records
- Validates product page URLs (must be `/products/<slug>` with exactly 2 path segments)

**Fallback Path:**

- Falls back to DOM parsing if `__NEXT_DATA__` yields no results
- Uses BeautifulSoup with lxml preference (falls back to html.parser)
- Logs warnings when layout changes prevent extraction

**Features:**

- Filters posts by recency (configurable, default 7 days)
- Extracts: name, tagline, description, votes, URL, topics, posted_at
- Configuration object for timeout control

#### **protocols.py — FallbackProvider**

Strategy pattern implementation that:

- Attempts API first (if token provided)
- Falls back to scraper on any exception
- Emits diagnostic warning when token is missing
- Transparently handles strategy switching

**Key Behavior:**

```
Try API → Success: return results
        → Failure: Try Scraper → Success: return results
                              → Failure: raise
```

### 4. Storage Layer

#### **storage.py — SQLiteStore**

Persistence layer managing database lifecycle:

**Schema:**

```sql
CREATE TABLE products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    tagline     TEXT,
    votes       INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    url         TEXT,
    tags        TEXT,
    posted_at   TEXT,
    observed_at TEXT NOT NULL
);

CREATE INDEX idx_products_observed_at ON products(observed_at DESC);
```

**Key Methods:**

- `init_db()`: Idempotent schema initialization with backward-compatibility migrations
- `save_result()`: Inserts one row per product in a TrackerResult; returns row count
- `_ensure_*_column()`: Adds missing columns for backward compatibility

**Design:**

- No deduplication: each run is a complete snapshot
- Full audit trail: enables tracking vote count changes over time
- Idempotent initialization: safe to call repeatedly

### 5. Enrichment Layer

#### **tagging.py — Tagging Services**

Optional product categorization layer.

**NoOpTaggingService:**
Returns empty tuple for all products (used by default).

**UniversalLLMTaggingService:**
OpenAI-compatible HTTP client that:

- Accepts custom `base_url` (allows local LLM routing like ollama)
- Uses `gpt-4o-mini` by default (configurable)
- Sends product searchable text to LLM
- Parses JSON response with `{"tags": [...]}` schema
- **Never raises**: catches all exceptions and returns empty tuple
- Validates tags (lowercase, non-empty, max 20 chars, no duplicates)

### 6. Domain Layer

#### **models.py — Core Data Models**

**Product** (Frozen Dataclass)

```python
@dataclass(frozen=True)
class Product:
    name: str                    # Required, non-empty invariant
    tagline: str | None = None   # Optional
    description: str | None = None
    votes: int = 0
    url: str | None = None
    topics: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()   # Enrichment tags (from LLM)
    posted_at: datetime | None = None
    searchable_text: str = field(init=False)  # Computed concatenation
```

**TrackerResult** (Frozen Dataclass)
Represents the outcome of a fetch operation:

```python
@dataclass(frozen=True)
class TrackerResult:
    # Success fields
    products: tuple[Product, ...]

    # Error fields
    error: str | None = None

    # Metadata
    source: str                  # "api" or "scraper"
    search_term: str
    limit: int
    fetched_at: datetime
    is_transient: bool = False   # Retry-safe?
```

**Canonical Keys:**
`canonical_key(product: Product)` returns:

- `url:<normalized_url>` if URL exists and is valid
- `name:<normalized_name>` otherwise (for deduplication/matching)

#### **protocols.py — Protocol Abstractions**

Type-safe interfaces via Python's structural typing:

```python
@runtime_checkable
class ProductProvider(Protocol):
    source_name: str
    def fetch_products(...) -> list[Product]: ...
    def close() -> None: ...

@runtime_checkable
class TaggingService(Protocol):
    def categorize(product: Product) -> tuple[str, ...]: ...
```

### 7. Bootstrap & Configuration

#### **bootstrap.py — Composition Root**

Factory functions that assemble provider stacks:

```python
def build_provider(*, strategy: str, api_token: str | None) -> ProductProvider:
    # strategy: "api", "scraper", or "auto"
    # Returns correct provider based on strategy and token availability

def build_tagging_service(env: dict[str, str] | None = None) -> TaggingService:
    # Reads OPENAI_API_KEY and optional OPENAI_BASE_URL
    # Returns UniversalLLMTaggingService or NoOpTaggingService
```

**Strategy Behavior:**

- `"scraper"`: Always use scraper (no network dependency on API)
- `"api"`: Use API only; warn if token missing
- `"auto"`: Try API, fall back to scraper (recommended for reliability)

#### **cli.py — CLI Argument Parsing**

Shared argument definitions:

```python
@dataclass
class CommonArgs:
    strategy: str
    search_term: str
    limit: int
    db_path: str
    api_token: str | None
```

Provides `add_common_arguments(parser)` for consistent CLI interfaces across `__main__` and `scheduler`.

#### **constants.py — Default Values**

```python
DEFAULT_SEARCH_TERM = "AI"
DEFAULT_LIMIT = 10
DEFAULT_DB_PATH = "./data/ph_ai_tracker.db"
DEFAULT_RECENT_DAYS = 7
```

### 8. Formatting & Utilities

#### **formatters.py — NewsletterFormatter**

Transforms Product list into newsletter-style JSON:

```python
def format(products: list[Product], timestamp: datetime) -> dict:
    # Returns: {
    #   "generated_at": ISO timestamp,
    #   "product_count": int,
    #   "products": [...],
    #   "tag_analytics": {
    #     "tag_name": frequency_count,
    #     ...
    #   }
    # }
```

#### **exceptions.py — Domain Errors**

```python
APIError          # GraphQL/HTTP errors from API
RateLimitError    # Rate limit exceeded (transient)
ScraperError      # HTML parsing failures (transient)
StorageError      # Database operation failures
```

---

## Data Flow

### Flow 1: CLI Execution (One-Shot Fetch)

```
┌─ User runs: python -m ph_ai_tracker --strategy auto --search AI
│
├─ __main__.main() parses arguments
│
├─ bootstrap.build_provider("auto", api_token)
│  └─ Creates FallbackProvider(api=ProductHuntAPI(), scraper=ProductHuntScraper())
│
├─ bootstrap.build_tagging_service()
│  └─ Creates UniversalLLMTaggingService() or NoOpTaggingService()
│
├─ AIProductTracker(provider, tagging_service).get_products(search_term, limit)
│  ├─ provider.fetch_products() [tries API → falls back to scraper]
│  ├─ _enrich_product() [calls tagging_service.categorize() for each]
│  └─ Returns TrackerResult(success or failure)
│
├─ _write_newsletter()
│  └─ Outputs formatted JSON to stdout
│
└─ _try_persist() [if not --no-persist]
   └─ SQLiteStore.save_result()
   └─ Exit code 0 or 3
```

### Flow 2: API Fetch (HTTP Request)

```
┌─ User makes: GET /fetch?strategy=auto&search=AI&limit=10
│
├─ api.py loads .env if exists
│
├─ _fetch_result(strategy, search_term, limit)
│  └─ Same as Flow 1, returns TrackerResult
│
├─ Optionally: _persist_result() saves to SQLite
│
└─ Returns JSON response with product list and status
```

### Flow 3: Scheduled Execution (Background)

```
┌─ Cron triggers: ph-ai-tracker-runner
│
├─ scheduler.main() parses environment variables for config
│
├─ scheduler.run_once(config)
│  ├─ Creates AIProductTracker with configured provider
│  ├─ Retries on transient errors (up to retry_attempts)
│  ├─ Classifies result as success/partial/failure
│  └─ Persists result via SQLiteStore
│
└─ Outputs JSON status to stdout or logs
```

### Fetch Strategy Behavior

#### Strategy: "API"

1. Queries Product Hunt GraphQL endpoint
2. Uses bearer token from environment
3. Requests `artificial-intelligence` topic (oversampled)
4. Falls back to global `posts` topic if schema changed
5. Raises `APIError` or `RateLimitError` on failure

#### Strategy: "Scraper"

1. Fetches Product Hunt HTML homepage
2. Extracts `__NEXT_DATA__` JSON blob from page
3. Walks nested structure to find products
4. Falls back to DOM parsing if extraction fails
5. Filters by recency (default: last 7 days)
6. Raises `ScraperError` on total failure

#### Strategy: "Auto"

1. Attempts API first (if token available, else warns)
2. On any exception (API or network), falls back to scraper
3. Returns scraper result on success
4. Raises `ScraperError` only if both fail

---

## Operational Modes

### 1. One-Shot CLI

```bash
# Scraper strategy (no auth needed)
python -m ph_ai_tracker --strategy scraper --search AI --limit 10

# API strategy (requires token)
python -m ph_ai_tracker --strategy api --search AI

# Auto strategy (fallback enabled)
python -m ph_ai_tracker --strategy auto --search "machine learning"

# Skip database persistence
python -m ph_ai_tracker --strategy scraper --no-persist

# Custom database path
python -m ph_ai_tracker --db-path ./custom.db
```

### 2. Python Library Import

```python
from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.api_client import ProductHuntAPI

api = ProductHuntAPI(api_token="your_token")
tracker = AIProductTracker(provider=api)
result = tracker.get_products(search_term="AI", limit=10)

if result.error:
    print(f"Failed: {result.error}, transient={result.is_transient}")
else:
    for product in result.products:
        print(f"{product.name}: {product.votes} votes")
```

### 3. HTTP API Server

```bash
# Start server
python -m ph_ai_tracker.api

# Fetch via HTTP
curl "http://localhost:8000/fetch?strategy=auto&search=AI&limit=10"

# Check health
curl http://localhost:8000/health
```

### 4. Scheduled Runner (Cron)

```bash
# In crontab
0 9 * * * /usr/local/bin/ph-ai-tracker-runner \
  --strategy auto \
  --search AI \
  --limit 10 \
  --cron "0 */6 * * *" \
  --retry-attempts 3

# Or in Docker with environment variables:
# SCHEDULE="0 9 * * *"
# STRATEGY="auto"
# PH_AI_SEARCH_TERM="AI"
```

### 5. Docker Deployment

```dockerfile
# Dockerfile handles:
# - Per-run execution or scheduled service
# - Volume mount for persistent SQLite
# - Environment variable configuration
```

```bash
# Run Docker container
docker run \
  -e PRODUCTHUNT_TOKEN="your_token" \
  -e OPENAI_API_KEY="your_key" \
  -v /data:/app/data \
  ph-ai-tracker:latest
```

---

## Key Design Patterns

### 1. Strategy Pattern (Provider Selection)

**Problem:** Multiple data sources (API vs. scraper) with different trade-offs.

**Solution:** `ProductProvider` protocol allows runtime selection and composition.

```python
# At runtime, choose strategy
if api_token:
    provider = ProductHuntAPI(api_token)
else:
    provider = ProductHuntScraper()

tracker = AIProductTracker(provider=provider)
```

### 2. Fallback Pattern (Resilience)

**Problem:** API outages or network issues cause complete failure.

**Solution:** `FallbackProvider` transparently tries API first, falls back to scraper.

```python
provider = FallbackProvider(
    api_provider=ProductHuntAPI(token),
    scraper_provider=ProductHuntScraper()
)
# Caller doesn't know about fallback; it "just works"
```

### 3. Facade Pattern (Use-Case Orchestration)

**Problem:** Complex interactions between provider, tagging, and error handling.

**Solution:** `AIProductTracker` presents a single, simple method.

```python
tracker.get_products(search_term, limit)  # Hide all complexity
```

### 4. Immutability & Value Objects

**Problem:** Mutable state leads to bugs and makes testing/reasoning hard.

**Solution:** `Product` and `TrackerResult` are frozen dataclasses.

```python
@dataclass(frozen=True)
class Product:
    name: str
    votes: int = 0
    # Can't be modified after creation
```

### 5. Never-Raises Pattern (Error as Data)

**Problem:** Callers must handle exceptions from multiple layers.

**Solution:** `AIProductTracker.get_products()` never raises known domain errors; captures them in result.

```python
# Always returns TrackerResult, never raises APIError/ScraperError
result = tracker.get_products(...)
if result.error:
    # Handle error; is_transient tells you if retry is safe
    handle_error(result.error, retry_safe=result.is_transient)
else:
    # Process products
    for product in result.products:
        ...
```

### 6. Protocol-Based Abstraction

**Problem:** Tight coupling to specific implementations prevents testing/extension.

**Solution:** `ProductProvider` and `TaggingService` are protocols, not abstract base classes.

```python
@runtime_checkable
class ProductProvider(Protocol):
    source_name: str
    def fetch_products(...) -> list[Product]: ...
    def close() -> None: ...

# Any object with these members satisfies the protocol (structural typing)
```

---

## Configuration & Defaults

### Environment Variables

| Variable            | Default                     | Purpose                            |
| ------------------- | --------------------------- | ---------------------------------- |
| `PRODUCTHUNT_TOKEN` | (none)                      | GraphQL API bearer token           |
| `OPENAI_API_KEY`    | (none)                      | OpenAI API key for tagging         |
| `OPENAI_BASE_URL`   | `https://api.openai.com/v1` | LLM endpoint (supports local LLMs) |
| `PH_AI_DB_PATH`     | `./data/ph_ai_tracker.db`   | SQLite database path               |
| `PH_AI_SEARCH_TERM` | `AI`                        | Default search keyword             |
| `PH_AI_LIMIT`       | `10`                        | Default result limit               |
| `SCHEDULE`          | (none)                      | Cron expression for scheduler      |

### CLI Arguments

```
--strategy {api,scraper,auto}     Data source strategy (required)
--search TERM                     Search keyword (default: AI)
--limit N                         Number of results (default: 10)
--db-path PATH                    SQLite database path
--api-token TOKEN                 Product Hunt API token (override env)
--no-persist                      Skip database write
```

### Hard-Coded Defaults (constants.py)

```python
DEFAULT_SEARCH_TERM = "AI"
DEFAULT_LIMIT = 10
DEFAULT_DB_PATH = "./data/ph_ai_tracker.db"
DEFAULT_RECENT_DAYS = 7  # Temporal filter for scraper
```

### API Configuration (api_client.py)

```python
# GraphQL endpoint
DEFAULT_GRAPHQL_ENDPOINT = "https://api.producthunt.com/v2/api/graphql"

# Oversampling factor (request 5x limit to account for filtering)
request_first = min(limit * 5, 50)

# HTTP timeout
timeout_seconds = 10.0
```

---

## Error Handling

### Exception Hierarchy

```
Exception
├── StorageError          # SQLite/disk errors (not transient)
├── APIError              # GraphQL errors, malformed responses
│   └── RateLimitError    # Rate limited (transient, retry-safe)
└── ScraperError          # HTML parsing, validation failures (transient)
```

### Error Classification in TrackerResult

```python
@dataclass(frozen=True)
class TrackerResult:
    error: str | None           # Human-readable error message
    is_transient: bool = False  # Safe to retry?

    # Examples:
    # error="Rate limited: 429", is_transient=True    → Retry after delay
    # error="Scraper failed: ...", is_transient=True → Retry, maybe with API
    # error="Storage error: ...", is_transient=False → Log, investigate
```

### Resilience Strategies

1. **API Rate Limiting:**
   - Parsed from response headers: `X-Rate-Limit-Limit`, `X-Rate-Limit-Remaining`, `X-Rate-Limit-Reset`
   - Raises `RateLimitError` with backoff info
   - Marked as transient (retry after delay)

2. **Network Failures:**
   - Handled by httpx timeout
   - Scraper falls back if API unreachable
   - Scheduler retries on transient errors

3. **HTML Layout Changes:**
   - Logs WARNING if `__NEXT_DATA__` extraction fails
   - Falls back to DOM parsing
   - Enables operator detection without alert fatigue

4. **Database Errors:**
   - Caught in `_try_persist()`
   - Returns exit code 3
   - CLI continues even if database unavailable (print output to stdout)

---

## Extension Points

### 1. Custom Provider Implementation

Create a new data source by implementing the `ProductProvider` protocol:

```python
class CustomNewsProvider:
    source_name = "custom"

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        # Fetch from your source
        products = my_api.search(search_term)
        return [
            Product(
                name=p["title"],
                url=p["link"],
                votes=p["views"],
                ...
            )
            for p in products[:limit]
        ]

    def close(self) -> None:
        pass  # Cleanup (close connection, etc.)

# Use it
tracker = AIProductTracker(provider=CustomNewsProvider())
result = tracker.get_products(search_term="AI")
```

### 2. Custom Tagging Service

Implement a different categorization strategy:

```python
class RuleBasedTaggingService:
    """Tags products based on keyword matching."""

    def categorize(self, product: Product) -> tuple[str, ...]:
        text = product.searchable_text.lower()
        tags = []
        if "nlp" in text or "language" in text:
            tags.append("nlp")
        if "vision" in text or "image" in text:
            tags.append("vision")
        return tuple(tags)

# Use it
tracker = AIProductTracker(
    provider=provider,
    tagging_service=RuleBasedTaggingService()
)
```

### 3. Custom Storage Backend

Extend or replace SQLiteStore:

```python
class PostgresStore:
    """Persist products to PostgreSQL."""

    def __init__(self, connection_string: str):
        self._conn_str = connection_string

    def init_db(self) -> None:
        # Create schema if needed
        ...

    def save_result(self, result: TrackerResult) -> int:
        # Insert rows
        ...

# Use it in CLI or API by replacing SQLiteStore
store = PostgresStore(os.environ["DATABASE_URL"])
store.init_db()
store.save_result(result)
```

### 4. Custom Entry Points

Add new CLI commands or workflows:

```python
# new_command.py
from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.bootstrap import build_provider

def my_custom_workflow():
    provider = build_provider(strategy="auto", api_token=None)
    tracker = AIProductTracker(provider=provider)
    result = tracker.get_products(search_term="machine learning", limit=20)

    # Custom processing
    for product in result.products:
        if product.votes > 100:
            send_notification(product)

if __name__ == "__main__":
    my_custom_workflow()
```

---

## Testing Architecture

The codebase is designed for testability:

1. **Protocol-based abstraction**: Mock any provider or tagging service
2. **Immutable models**: No setup/teardown mutation issues
3. **Composition root (bootstrap.py)**: Easy to inject test doubles
4. **Never-raises pattern**: No deep try-catch chains in tests

**Example test:**

```python
class MockProvider:
    source_name = "mock"

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        return [
            Product(name="Test Product", votes=100),
        ]

    def close(self) -> None:
        pass

def test_tracker_enriches_products():
    tracker = AIProductTracker(provider=MockProvider())
    result = tracker.get_products()
    assert len(result.products) == 1
    assert result.products[0].name == "Test Product"
```

---

## Summary

**ph_ai_tracker** is a well-architected production system demonstrating:

- **Clean separation of concerns** across CLI, use-case, data, and domain layers
- **Protocol-based design** enabling flexible implementations and testing
- **Error handling as data** (never-raises pattern)
- **Immutability** for correctness and safe concurrency
- **Fallback resilience** for real-world network conditions
- **Multiple deployment modes** (CLI, library, API, scheduler, Docker)

The codebase prioritizes **simplicity, reliability, and extensibility**, making it suitable for production deployment while remaining easy to understand and modify.

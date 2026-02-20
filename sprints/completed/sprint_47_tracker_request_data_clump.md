# Sprint 47 — Data Clump: Absorb `search_term` + `limit` into `TrackerResult`

**Uncle Bob Letter 11, Issue #2**
**Depends on:** Sprint 43 (`TrackerResult.is_transient` established the pattern of enriching the result object with context that travels alongside it)

---

## Problem Statement

`result`, `search_term`, and `limit` are a **data clump** — a group of primitives that travel together everywhere they go:

```python
# storage.py
def save_result(self, result: TrackerResult, *, search_term: str, limit: int, status: str | None = None) -> int:
def _commit_run(self, conn, result, search_term, limit, status) -> int:
def _insert_run_record(self, conn, result, search_term, limit, status) -> int:

# __main__.py
SQLiteStore(common.db_path).save_result(result, search_term=common.search_term, limit=common.limit)

# scheduler.py
store.save_result(result, search_term=config.search_term, limit=config.limit, status=status)
```

`search_term` and `limit` are not separate from the result.  They are the request context that *produced* the result.  They belong inside `TrackerResult`, which already records `source` and `fetched_at` for the same reason.

---

## Goal

Add `search_term: str` and `limit: int` fields to `TrackerResult`.  Update `tracker.py` to populate them from the `get_products` call parameters.  Simplify every `save_result` call site to pass only the result.  Eliminate the clumped parameter group.

---

## Files to Change

| File | Change |
|------|--------|
| `src/ph_ai_tracker/models.py` | Add `search_term: str = ""` and `limit: int = 0` to `TrackerResult`; add them as kwargs to `success()` and `failure()` |
| `src/ph_ai_tracker/tracker.py` | Pass `search_term=search_term, limit=limit` to both `TrackerResult.success()` and `TrackerResult.failure()` |
| `src/ph_ai_tracker/scheduler.py` | Update `_fetch_with_retries` sentinel failure to carry `search_term`/`limit`; simplify `run_once` call to `store.save_result(result, status=status)` |
| `src/ph_ai_tracker/storage.py` | Remove `search_term` and `limit` params from `save_result`, `_commit_run`, `_insert_run_record`; read from `result.search_term` / `result.limit` |
| `src/ph_ai_tracker/__main__.py` | Simplify `_try_persist` to call `store.save_result(result)` |
| `tests/unit/test_storage.py` | Build `TrackerResult` with `search_term` + `limit` set; remove those kwargs from `save_result` calls |
| `tests/unit/test_models.py` | Add tests for new fields on `TrackerResult` |
| `tests/unit/test_scheduler.py` | Update `_fetch_with_retries` sentinel result expectation; update `save_result` mock expectations |

---

## Exact Code Changes

### `src/ph_ai_tracker/models.py` — `TrackerResult`

Add two new fields with defaults (so all existing construction code remains backward-compatible):

```python
@dataclass(frozen=True, slots=True)
class TrackerResult:
    """The outcome of a single ``AIProductTracker.get_products()`` call.

    ``error is None`` is the canonical success signal.  ``products`` is always
    a tuple; on failure it is empty unless a partial result was recorded.

    ``is_transient`` is a scheduler hint: ``True`` means retrying this
    failure is safe and potentially useful (e.g. timeout/rate-limit).

    ``search_term`` and ``limit`` record the request context that produced
    this result, eliminating the data clump that otherwise travels beside
    the result object through every persistence call.
    """

    products: tuple[Product, ...]
    source: str
    fetched_at: datetime
    error: str | None = None
    is_transient: bool = False
    search_term: str = ""
    limit: int = 0
```

Update `success()`:

```python
@classmethod
def success(
    cls,
    products: Iterable[Product],
    source: str,
    *,
    search_term: str = "",
    limit: int = 0,
) -> "TrackerResult":
    return cls(
        products=tuple(products),
        source=source,
        fetched_at=datetime.now(timezone.utc),
        error=None,
        search_term=search_term,
        limit=limit,
    )
```

Update `failure()`:

```python
@classmethod
def failure(
    cls,
    source: str,
    error: str,
    *,
    is_transient: bool = False,
    search_term: str = "",
    limit: int = 0,
) -> "TrackerResult":
    return cls(
        products=(),
        source=source,
        fetched_at=datetime.now(timezone.utc),
        error=error,
        is_transient=is_transient,
        search_term=search_term,
        limit=limit,
    )
```

---

### `src/ph_ai_tracker/tracker.py` — `get_products`

Pass `search_term` and `limit` into every `TrackerResult` factory call:

```python
def get_products(
    self, *, search_term: str = DEFAULT_SEARCH_TERM, limit: int = DEFAULT_LIMIT
) -> TrackerResult:
    """Delegate to provider; map known domain exceptions to TrackerResult failures."""
    try:
        products = self._provider.fetch_products(search_term=search_term, limit=limit)
        return TrackerResult.success(
            products, source=self._provider.source_name,
            search_term=search_term, limit=limit,
        )
    except RateLimitError as exc:
        return TrackerResult.failure(
            source=self._provider.source_name,
            error=f"Rate limited: {exc}",
            is_transient=True,
            search_term=search_term,
            limit=limit,
        )
    except ScraperError as exc:
        return TrackerResult.failure(
            source=self._provider.source_name,
            error=str(exc),
            is_transient=True,
            search_term=search_term,
            limit=limit,
        )
    except APIError as exc:
        return TrackerResult.failure(
            source=self._provider.source_name,
            error=str(exc),
            is_transient=False,
            search_term=search_term,
            limit=limit,
        )
    finally:
        self._provider.close()
```

---

### `src/ph_ai_tracker/storage.py` — Remove clumped parameters

**`save_result`** — drop `search_term` and `limit`; forward to `_commit_run` without them:

```python
def save_result(
    self,
    result: TrackerResult,
    *,
    status: str | None = None,
) -> int:
    """Persist a tracker result; return the newly created run ID."""
    self.init_db()
    status_value = _derive_run_status(result, status_override=status)
    try:
        with self._connect() as conn:
            run_id = self._commit_run(conn, result, status_value)
        return run_id
    except sqlite3.IntegrityError as exc:
        raise StorageError(f"integrity violation during save: {exc}") from exc
    except sqlite3.Error as exc:
        raise StorageError(f"failed to save tracker result: {exc}") from exc
```

**`_commit_run`** — drop `search_term` and `limit`:

```python
def _commit_run(
    self, conn: sqlite3.Connection, result: TrackerResult, status: str,
) -> int:
    """Insert the run record and all snapshots, then commit; return run ID."""
    run_id = self._insert_run_record(conn, result, status)
    if result.error is None:
        self._insert_all_snapshots(conn, run_id, result.products, result.fetched_at.isoformat())
    conn.commit()
    return run_id
```

**`_insert_run_record`** — drop `search_term` and `limit`; read from `result`:

```python
def _insert_run_record(
    self,
    conn: sqlite3.Connection,
    result: TrackerResult,
    status: str,
) -> int:
    """Insert a row into ``runs`` and return the new ``id``."""
    cursor = conn.execute(
        """
        INSERT INTO runs (source, fetched_at, search_term, limit_value, status, error)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            result.source,
            result.fetched_at.isoformat(),
            str(result.search_term),
            int(result.limit),
            status,
            result.error,
        ),
    )
    return int(cursor.lastrowid)
```

---

### `src/ph_ai_tracker/scheduler.py` — Update `_fetch_with_retries` and `run_once`

In `_fetch_with_retries`, the sentinel `TrackerResult.failure` should carry request context:

```python
# Before:
result = TrackerResult.failure(source=config.strategy, error="run not started")
# After:
result = TrackerResult.failure(
    source=config.strategy,
    error="run not started",
    search_term=config.search_term,
    limit=config.limit,
)
```

In `run_once`, simplify `save_result` call:

```python
# Before:
run_id = store.save_result(result, search_term=config.search_term, limit=config.limit, status=status)
# After:
run_id = store.save_result(result, status=status)
```

---

### `src/ph_ai_tracker/__main__.py` — Simplify `_try_persist`

```python
# Before:
SQLiteStore(common.db_path).save_result(result, search_term=common.search_term, limit=common.limit)
# After:
SQLiteStore(common.db_path).save_result(result)
```

---

### `tests/unit/test_storage.py` — Thread `search_term`/`limit` through results

Every test that calls `store.save_result(result, search_term=..., limit=...)` must instead build the result with those fields, then call `store.save_result(result)`.

**Pattern:**

```python
# Before:
result = TrackerResult.success([p1, p2], source="scraper")
run_id = store.save_result(result, search_term="AI", limit=20)

# After:
result = TrackerResult.success([p1, p2], source="scraper", search_term="AI", limit=20)
run_id = store.save_result(result)
```

Apply this pattern to all of the following tests:
- `test_save_success_persists_run_products_and_snapshots`
- `test_save_failure_persists_run_without_product_rows`
- `test_upsert_dedupes_products_across_runs`
- `test_upsert_updates_updated_at_but_not_created_at`
- `test_save_result_rejects_invalid_status`

---

## New Tests for `tests/unit/test_models.py`

Add focused verification that the new fields are populated correctly:

```python
def test_tracker_result_success_carries_search_term_and_limit() -> None:
    r = TrackerResult.success([], source="scraper", search_term="AI", limit=5)
    assert r.search_term == "AI"
    assert r.limit == 5

def test_tracker_result_failure_carries_search_term_and_limit() -> None:
    r = TrackerResult.failure(source="api", error="oops", search_term="ml", limit=10)
    assert r.search_term == "ml"
    assert r.limit == 10

def test_tracker_result_defaults_search_term_and_limit_to_empty() -> None:
    r = TrackerResult.success([], source="api")
    assert r.search_term == ""
    assert r.limit == 0
```

---

## Function Size Constraint

All modified methods must remain ≤ 20 lines.  `get_products` will grow by ~8 lines — verify with `make bundle`.

> **Note:** If `get_products` exceeds 20 lines after this change, extract the four exception handlers into a `_make_failure` helper that accepts `exc`, `source`, `is_transient`, `search_term`, `limit`.

---

## Acceptance Criteria

- [ ] `TrackerResult` has `search_term: str = ""` and `limit: int = 0` fields.
- [ ] `TrackerResult.success()` and `TrackerResult.failure()` accept and store `search_term` and `limit`.
- [ ] `SQLiteStore.save_result` signature is `(self, result, *, status=None)` — no `search_term` or `limit` params.
- [ ] `_commit_run` and `_insert_run_record` signatures contain no `search_term` or `limit` params.
- [ ] `run_id = store.save_result(result, status=status)` in `scheduler.py` — no extra kwargs.
- [ ] `SQLiteStore(common.db_path).save_result(result)` in `__main__.py` — no extra kwargs.
- [ ] All 3 new model tests pass.
- [ ] Full pytest suite passes (no regressions).
- [ ] `make bundle` reports ✓ all functions ≤ 20 lines.
- [ ] `grep -rn "search_term=config\." src/ph_ai_tracker/scheduler.py` → 0 matches (in `save_result` call).
- [ ] `grep -rn "search_term=common\." src/ph_ai_tracker/__main__.py` → 0 matches.

# Sprint 49 — Temporal Coupling: Move `init_db()` to the Framework Layer

**Uncle Bob Letter 11, Issue #4**
**Depends on:** Sprint 47 (`save_result` signature change lands first to avoid touching the same methods twice); Sprint 48 is independent but should be run before this sprint to avoid editing the same test file twice.

---

## Problem Statement

The very first line of `SQLiteStore.save_result` is:

```python
def save_result(self, result: TrackerResult, *, status: str | None = None) -> int:
    """Persist a tracker result; return the newly created run ID."""
    self.init_db()   # ← executed on EVERY write
    ...
```

This is **Temporal Coupling**.  `SQLiteStore` is silently taking on schema-initialisation responsibility inside a domain write operation.  Every call to `save_result` — even the hundredth one in a long-running scheduler — executes `CREATE TABLE IF NOT EXISTS ...` SQL against the database.  That is:

1. **An I/O tax**: an unnecessary round-trip on every write.
2. **A responsibility violation**: schema init is a bootstrapping concern, not a domain write concern.
3. **A hidden lie in the API contract**: the method is named `save_result`, not `init_and_save_result`.

The caller (the framework layer: `__main__.py` and `scheduler.py`) is the right place to call `init_db()` — once, explicitly, at startup, before any domain logic is invoked.

---

## Goal

Remove `self.init_db()` from `save_result`.  Explicitly call `store.init_db()` in `__main__.py` and `scheduler.py` at startup.  Update all storage tests that relied on `save_result` auto-initialising the database.

---

## Files to Change

| File | Change |
|------|--------|
| `src/ph_ai_tracker/storage.py` | Delete `self.init_db()` from the top of `save_result` |
| `src/ph_ai_tracker/__main__.py` | Call `store.init_db()` in `_try_persist` before `save_result` |
| `src/ph_ai_tracker/scheduler.py` | Call `store.init_db()` in `run_once` immediately after creating the `SQLiteStore` |
| `tests/unit/test_storage.py` | Add `store.init_db()` before every `save_result` call in tests that omitted it |

---

## Exact Code Changes

### `src/ph_ai_tracker/storage.py` — Remove `self.init_db()`

```python
def save_result(
    self,
    result: TrackerResult,
    *,
    status: str | None = None,
) -> int:
    """Persist a tracker result; return the newly created run ID.

    The database schema must already be initialised (via ``init_db()``) before
    this method is called.  Schema initialisation is the caller's responsibility
    and should happen once at application startup.
    """
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

The only change is removing `self.init_db()` from line 1 of the body and updating the docstring to reflect the new contract.

---

### `src/ph_ai_tracker/__main__.py` — Explicit `init_db` in `_try_persist`

```python
def _try_persist(result, common: CommonArgs) -> int | None:
    """Initialise the database schema and persist result; return 3 on error, else None."""
    try:
        store = SQLiteStore(common.db_path)
        store.init_db()
        store.save_result(result)
        return None
    except StorageError as exc:
        sys.stderr.write(f"failed to persist run: {exc}\n")
        return 3
```

> **Note:** Before this sprint, `_try_persist` constructed `SQLiteStore` inline in the `save_result` call.  After Sprint 49 it names the store so `init_db()` can be called on it first.  The function remains well within 20 lines.

---

### `src/ph_ai_tracker/scheduler.py` — Explicit `init_db` in `run_once`

```python
def run_once(config: SchedulerConfig) -> SchedulerRunResult:
    """Execute one full fetch-and-persist cycle and return the run outcome."""
    provider = build_provider(strategy=config.strategy, api_token=config.api_token)
    tracker = AIProductTracker(provider=provider)
    result, attempts_used = _fetch_with_retries(tracker, config)
    store = SQLiteStore(config.db_path)
    store.init_db()
    status = _classify_run_status(result)
    run_id = store.save_result(result, status=status)
    return SchedulerRunResult(
        run_id=run_id, tracker_result=result, status=status, attempts_used=attempts_used,
    )
```

The single added line is `store.init_db()` between creating the store and calling `save_result`.

---

### `tests/unit/test_storage.py` — Add `init_db()` before `save_result` in affected tests

Every test that calls `save_result` without first calling `init_db()` will now raise `sqlite3.OperationalError: no such table: runs`.  Add `store.init_db()` immediately after `store = SQLiteStore(...)` in each of:

- `test_save_success_persists_run_products_and_snapshots`
- `test_save_failure_persists_run_without_product_rows`
- `test_upsert_dedupes_products_across_runs`
- `test_upsert_updates_updated_at_but_not_created_at`
- `test_save_result_rejects_invalid_status`

**Pattern:**

```python
# Before:
store = SQLiteStore(db_path)
result = TrackerResult.success([...], source="scraper", search_term="AI", limit=20)
run_id = store.save_result(result)

# After:
store = SQLiteStore(db_path)
store.init_db()
result = TrackerResult.success([...], source="scraper", search_term="AI", limit=20)
run_id = store.save_result(result)
```

The following tests already call `init_db()` explicitly and are **unaffected**:
- `test_init_db_creates_tables`
- `test_init_db_is_idempotent`
- `test_foreign_key_pragma_is_active`
- `test_canonical_key_unique_constraint_enforced_at_db_level`
- `test_product_snapshot_unique_run_product_constraint`
- `test_db_path_parent_dir_created_automatically`

---

## No New Tests Required

`test_init_db_creates_tables` and `test_init_db_is_idempotent` already verify `init_db`'s contract in isolation.  The changes to the five affected storage tests confirm the schema must be initialised before `save_result` works.

---

## Acceptance Criteria

- [ ] `grep "self.init_db" src/ph_ai_tracker/storage.py` → 1 match only (inside `init_db` itself — or 0 if `init_db` doesn't call itself; the point is `save_result` must not call it).
- [ ] `grep "save_result" src/ph_ai_tracker/storage.py` shows **no** `self.init_db()` call on the line before or inside `save_result`.
- [ ] `scheduler.py`'s `run_once` calls `store.init_db()` before `store.save_result(...)`.
- [ ] `__main__.py`'s `_try_persist` calls `store.init_db()` before `store.save_result(...)`.
- [ ] All five previously-implicit tests now have an explicit `store.init_db()` call before `store.save_result(...)`.
- [ ] Full pytest suite passes (no regressions).
- [ ] `make bundle` reports ✓ all functions ≤ 20 lines.

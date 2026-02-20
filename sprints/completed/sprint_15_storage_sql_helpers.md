# Sprint 15 — Storage: Extract SQL Helpers from `save_result`

## Uncle Bob Concern Addressed

> "Your `SQLiteStore.save_result` method (72 lines) is mixing raw SQL string
> execution with domain status mapping. The SQL strings should be extracted
> into well-named private methods (`_insert_run_record`, `_insert_product_snapshot`).
> Keep the transaction boundaries clear and the SQL out of the high-level
> orchestration flow."
> — Issue #5

---

## Sprint Goal

`save_result` becomes a ≤ 20 line transaction coordinator that reads like a
narrative. Every SQL string and every per-row write lives in a private helper
with a name that explains exactly what it does. No SQL string touches the
public method body.

---

## Acceptance Criteria

1. `save_result` body **≤ 20 lines** after refactoring.
2. **`_insert_run_record(conn, result, search_term, limit, status) -> int`** —
   executes the `INSERT INTO runs …` statement and returns `cursor.lastrowid`.
   Contains exactly one `conn.execute(...)` call.
3. **`_insert_product_snapshot(conn, run_id, product_id, product, fetched_at) -> None`** —
   executes the `INSERT OR REPLACE INTO product_snapshots …` statement.
   Contains exactly one `conn.execute(...)` call.
4. **`_insert_all_snapshots(conn, run_id, products, fetched_at) -> None`** —
   iterates over products, calls `_upsert_product` then `_insert_product_snapshot`
   for each. Replaces the `for product in result.products` loop currently
   embedded in `save_result`.
5. `_derive_run_status(result, status_override) -> str` — tiny pure function
   (already partially present as an inline expression) extracts the status
   resolution rule so it can be tested in isolation.
6. No SQL string literal appears in `save_result`.
7. All existing storage tests continue to pass.
8. All new tests listed below pass.

---

## TDD Approach — Red → Green → Refactor

### Step 1 — Write failing tests first

#### Unit Tests — `tests/unit/test_storage.py` (extend existing file)

```
──────────────────────────────────────────────────────
_derive_run_status (pure function, no DB)
──────────────────────────────────────────────────────
POSITIVE
test_derive_run_status_returns_success_when_no_error_and_no_override
    - result = TrackerResult(products=[...], error=None, ...)
    - assert _derive_run_status(result, status_override=None) == "success"

test_derive_run_status_returns_failure_when_error_and_no_products
    - result = TrackerResult(products=[], error="boom", ...)
    - assert _derive_run_status(result, status_override=None) == "failure"

test_derive_run_status_honours_explicit_override
    - result = TrackerResult(products=[...], error="partial", ...)
    - assert _derive_run_status(result, status_override="partial") == "partial"

NEGATIVE
test_derive_run_status_raises_on_invalid_override
    - with pytest.raises(StorageError):
    -     _derive_run_status(result, status_override="unknown_value")

──────────────────────────────────────────────────────
_insert_run_record
──────────────────────────────────────────────────────
POSITIVE
test_insert_run_record_returns_integer_id
    - Open an in-memory SQLite conn and apply _SCHEMA
    - run_id = SQLiteStore._insert_run_record(conn, result, "AI", 20, "success")
    - assert isinstance(run_id, int) and run_id > 0

test_insert_run_record_stores_correct_source
    - After insert, SELECT source FROM runs WHERE id=run_id
    - assert row["source"] == result.source

test_insert_run_record_stores_correct_status
    - assert row["status"] == "success"

NEGATIVE
test_insert_run_record_raises_storage_error_on_invalid_conn
    - Pass a closed/invalid connection
    - with pytest.raises(StorageError)

──────────────────────────────────────────────────────
_insert_product_snapshot
──────────────────────────────────────────────────────
POSITIVE
test_insert_product_snapshot_creates_row
    - Open in-memory DB; insert a run row and a product row first
    - Call SQLiteStore._insert_product_snapshot(conn, run_id, product_id, product, fetched_at)
    - SELECT COUNT(*) FROM product_snapshots WHERE run_id=run_id
    - assert count == 1

test_insert_product_snapshot_stores_votes_count
    - product = Product(name="Foo", votes_count=42, ...)
    - row = SELECT votes_count FROM product_snapshots WHERE run_id=...
    - assert row["votes_count"] == 42

NEGATIVE
test_insert_product_snapshot_raises_on_missing_run_id
    - Foreign key violations when run_id=9999 does not exist
    - with pytest.raises(StorageError)

──────────────────────────────────────────────────────
save_result orchestration (existing behaviour must be preserved)
──────────────────────────────────────────────────────
POSITIVE
test_save_result_returns_run_id (existing — must still pass)
test_save_result_persists_products (existing — must still pass)
test_save_result_partial_status_with_error (existing — must still pass)

NEGATIVE
test_save_result_body_is_under_20_lines
    - import inspect; src = inspect.getsource(SQLiteStore.save_result)
    - count non-blank non-comment lines; assert <= 20

test_no_sql_string_in_save_result_body
    - src = inspect.getsource(SQLiteStore.save_result)
    - assert "INSERT" not in src
    - assert "SELECT" not in src
    - assert "UPDATE" not in src
```

#### Integration Tests — `tests/integration/test_storage_integrity.py` (extend)

```
POSITIVE
test_save_result_is_atomic_on_integrity_error
    - Init DB; create a run row manually with run_id=1
    - Attempt save_result with a product that triggers a FK violation
    - Verify the runs table still has the pre-existing row (no orphan run inserted)

test_multiple_save_results_accumulate_correctly
    - Call save_result twice with different products
    - Assert runs table has 2 rows, product_snapshots has 2 rows
    - Assert products table has deduplicated entries (same URL → same product_id)

test_insert_run_record_and_insert_product_snapshot_are_importable
    # These are private but we verify they exist via hasattr
    - store = SQLiteStore(":memory:")
    - assert hasattr(store, "_insert_run_record")
    - assert hasattr(store, "_insert_product_snapshot")
```

#### E2E Tests — `tests/e2e/test_e2e_negative.py` (extend)

```
NEGATIVE
test_e2e_storage_integrity_constraint_raises_storage_error
    - Use a mock tracker that returns a valid TrackerResult
    - Tamper with the DB to create an FK violation scenario
    - assert save_result raises StorageError (not sqlite3.IntegrityError leaking)
```

---

## Implementation Notes

### Target shape for `save_result`

```python
def save_result(self, result, *, search_term, limit, status=None) -> int:
    self.init_db()
    status_value = _derive_run_status(result, status_override=status)
    try:
        with self._connect() as conn:
            run_id = self._insert_run_record(conn, result, search_term, limit, status_value)
            if result.error is None:
                self._insert_all_snapshots(conn, run_id, result.products, result.fetched_at)
            conn.commit()
            return run_id
    except sqlite3.IntegrityError as exc:
        raise StorageError(f"integrity violation during save: {exc}") from exc
    except sqlite3.Error as exc:
        raise StorageError(f"failed to save tracker result: {exc}") from exc
```

### `_derive_run_status` — pure module-level function

```python
def _derive_run_status(result: TrackerResult, *, status_override: str | None) -> str:
    if status_override is not None:
        if status_override not in {"success", "partial", "failure"}:
            raise StorageError(f"invalid run status: {status_override}")
        return status_override
    return "success" if result.error is None else "failure"
```

Making it a **module-level** pure function (not a method) means it has zero
coupling to `SQLiteStore` and can be tested with zero setup.

### `_insert_all_snapshots` — replaces the embedded loop

```python
def _insert_all_snapshots(
    self,
    conn: sqlite3.Connection,
    run_id: int,
    products: list[Product],
    fetched_at: datetime.datetime,
) -> None:
    for product in products:
        product_id = self._upsert_product(conn, product)
        self._insert_product_snapshot(conn, run_id, product_id, product, fetched_at)
```

Clean, readable, ≤ 5 lines.

---

## Definition of Done

- [ ] `save_result` is ≤ 20 non-blank lines and contains no SQL strings
- [ ] `_insert_run_record`, `_insert_product_snapshot`, `_insert_all_snapshots` exist as private methods
- [ ] `_derive_run_status` exists as a module-level pure function
- [ ] All NEW tests listed above pass (Red → Green)
- [ ] All EXISTING tests still pass (no regression)
- [ ] `make bundle` regenerates cleanly
- [ ] Function-size inventory shows `save_result` ≤ 20

# Sprint 10 — Database Schema Integrity & Referential Enforcement

## Knuth Concern Addressed

> "Ensure that your database schema enforces uniqueness via primary keys or
> constraints rather than relying solely on application-level logic. The
> database should be the ultimate arbiter of truth, maintaining referential
> integrity without algorithmic contortions in Python."
> — Issue #4

---

## Sprint Goal

Make SQLite the single source of truth for product uniqueness and referential
integrity. Every constraint that currently lives in Python (`canonical_key`
generation, duplicate guards) must have a corresponding database-level
enforcement mechanism so that a buggy Python caller cannot corrupt the schema.

---

## Acceptance Criteria

1. `PRAGMA foreign_keys = ON` is set on every connection; orphan inserts into
   `product_snapshots` raise `sqlite3.IntegrityError`.
2. Direct SQL `INSERT` of a duplicate `canonical_key` into `products` raises
   `IntegrityError` _without_ any Python guard in the path.
3. Direct SQL `INSERT` of a duplicate `(run_id, product_id)` into
   `product_snapshots` raises `IntegrityError`.
4. `StorageError` wraps all `sqlite3.IntegrityError` so callers receive a
   typed exception (not raw sqlite3).
5. Schema migration: if the database already exists from an older version
   (missing FK pragma), `init_db` is idempotent and the pragma still applies
   (pragma is per-connection, not stored in file — so it is always set in
   `_connect()`).
6. All three test layers pass.

---

## TDD Approach — Red → Green → Refactor

### Step 1 — Write failing tests first

#### Unit Tests `tests/unit/test_storage.py` (extend existing file)

```
POSITIVE
test_foreign_key_pragma_is_active
    - After init_db(), open a raw connection via SQLiteStore._connect()
    - Execute PRAGMA foreign_keys; assert the result row value == 1

test_canonical_key_unique_constraint_enforced_at_db_level
    - init_db(); open raw connection
    - INSERT two rows with the same canonical_key into products
    - Assert sqlite3.IntegrityError is raised on the second insert

test_product_snapshot_unique_run_product_constraint_enforced
    - init_db(); insert a run and a product via raw SQL
    - INSERT two identical (run_id, product_id) rows into product_snapshots
    - Assert sqlite3.IntegrityError is raised

test_product_snapshot_fk_rejects_orphan_run_id
    - init_db(); insert a valid product
    - Try to insert a snapshot with run_id=9999 (non-existent run)
    - Assert sqlite3.IntegrityError is raised

test_product_snapshot_fk_rejects_orphan_product_id
    - init_db(); insert a valid run
    - Try to insert a snapshot with product_id=9999 (non-existent product)
    - Assert sqlite3.IntegrityError is raised

test_save_result_wraps_integrity_error_as_storage_error
    - Manually corrupt the DB (insert duplicate canonical_key before save);
      call store.save_result() with the same product
    - Assert StorageError is raised, not sqlite3.IntegrityError

test_upsert_product_updates_updated_at_but_not_created_at
    - Save the same product twice; query DB
    - Assert created_at unchanged, updated_at ≥ created_at on second write

test_save_result_full_commit_occurs_atomically
    - Inject a product that will succeed and one whose canonical_key will
      trigger an IntegrityError (pre-inserted duplicate)
    - Assert the entire transaction rolls back (products count unchanged)

NEGATIVE
test_init_db_is_idempotent
    - Call init_db() three times on same path; assert no exceptions and
      table count remains the same (CREATE TABLE IF NOT EXISTS)

test_save_result_rejects_invalid_status_string
    - store.save_result(result, search_term="AI", limit=10, status="invalid")
    - Assert StorageError("invalid run status") is raised before any DB write

test_db_path_parent_dir_created_automatically
    - Use a tmp_path / "nested" / "dir" / "tracker.db"
    - Assert init_db() creates the directory and file without error
```

#### Integration Tests `tests/integration/test_storage_integrity.py`

```
POSITIVE
test_two_runs_share_one_product_row
    - Save two different TrackerResults containing the same canonical URL
    - SELECT COUNT(*) FROM products == 1
    - SELECT COUNT(*) FROM product_snapshots == 2

test_product_name_updated_on_subsequent_run
    - Save product with name="OldName", then same URL with name="NewName"
    - SELECT name FROM products; assert "NewName"

test_votes_count_tracked_per_snapshot_not_per_product
    - Save votes=10 then votes=99 for same product
    - SELECT votes_count FROM product_snapshots ORDER BY id;
      assert rows are [10, 99] (history preserved)

test_run_status_failure_stores_error_message
    - Save a TrackerResult.failure(source="api", error="Token expired")
    - SELECT error FROM runs; assert "Token expired"

NEGATIVE
test_raw_insert_without_fk_pragma_would_succeed_but_connection_enforces_it
    - Open a SQLite connection WITHOUT setting FK pragma
    - INSERT orphan snapshot row — assert this succeeds (documents the SQLite
      default OFF behaviour)
    - Demonstrates WHY we must always call PRAGMA foreign_keys = ON
    - Note: this negative test intentionally shows the unsafe path to justify
      the enforcement in _connect()

test_concurrent_save_does_not_corrupt_product_count  (if threading is feasible)
    - Spawn 4 threads each saving the same product
    - Assert products table still has exactly 1 row after all threads complete
```

#### E2E Tests `tests/e2e/test_e2e_positive.py` and `test_e2e_negative.py` (extend)

```
POSITIVE
test_e2e_full_pipeline_stores_and_dedupes
    - Use mock scraper transport returning 2 products
    - Run tracker twice with same search_term
    - Save both results via SQLiteStore
    - Assert runs == 2, products == 2 (unique by URL), snapshots == 4

test_e2e_db_survives_empty_run
    - Run tracker returning 0 products (empty page mock); save to DB
    - Assert runs == 1, products == 0, snapshots == 0, status == "success"

NEGATIVE
test_e2e_failure_result_does_not_write_products
    - No token; strategy="api"; save result
    - Assert products == 0, snapshots == 0, runs == 1 with status "failure"

test_e2e_storage_error_propagates_to_caller
    - Set db_path to a read-only location (chmod 444 on tmp_path)
    - Assert StorageError is raised (not sqlite3.Error or generic Exception)
```

---

## Implementation Tasks (after tests are written and red)

### `storage.py`

1. **`_connect()`** — enable FK enforcement on every connection:

   ```python
   def _connect(self) -> sqlite3.Connection:
       conn = sqlite3.connect(self._db_path)
       conn.execute("PRAGMA foreign_keys = ON")
       conn.row_factory = sqlite3.Row
       return conn
   ```

2. **`_SCHEMA`** — verify all three `FOREIGN KEY` declarations are present and
   that `ON DELETE RESTRICT` is explicit (makes intent clear to readers):

   ```sql
   FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE RESTRICT,
   FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE RESTRICT,
   ```

3. **`save_result`** — catch `sqlite3.IntegrityError` specifically before the
   generic `sqlite3.Error` catch:

   ```python
   except sqlite3.IntegrityError as exc:
       raise StorageError(f"integrity violation during save: {exc}") from exc
   except sqlite3.Error as exc:
       raise StorageError(f"failed to save tracker result: {exc}") from exc
   ```

4. **`_upsert_product`** — add comment explaining that the `ON CONFLICT` clause
   is the _database-level_ deduplication; the Python `_canonical_key` function
   only determines _which_ key to use — the DB decides uniqueness.

5. **`init_db()`** — document that FK pragma is per-connection (set in
   `_connect()`), not stored in the database file.

---

## Definition of Done

- [ ] All 16 storage/integrity tests pass (existing + new).
- [ ] `PRAGMA foreign_keys = ON` verified programmatically by a unit test.
- [ ] Orphan FK inserts raise `IntegrityError` (caught, re-raised as
      `StorageError`).
- [ ] The "unsafe path" negative test documenting SQLite's default-OFF FK
      behaviour is present and passes.
- [ ] `_connect()` sets `PRAGMA foreign_keys = ON` on every connection.

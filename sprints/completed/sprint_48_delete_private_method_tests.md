# Sprint 48 — Inappropriate Intimacy: Delete Private-Method Tests

**Uncle Bob Letter 11, Issue #3**
**Depends on:** Sprint 47 (`TrackerResult` absorbs `search_term`/`limit`; `_insert_run_record` signature changes, making it temporarily simpler after 47 lands first) — **run this sprint immediately after Sprint 47**

---

## Problem Statement

Tests that call private methods bind the test suite to internal implementation, making refactoring painful without adding any coverage that does not already exist through the public API.

### `tests/unit/test_storage.py` — two offenders

```python
def test_insert_run_record_returns_integer_id(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    result = TrackerResult.success([], source="scraper")
    with store._connect() as conn:
        run_id = store._insert_run_record(conn, result, "AI", 10, "success")
        conn.commit()
    assert isinstance(run_id, int) and run_id > 0


def test_insert_all_snapshots_writes_expected_rows(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    products = [Product(name="P1"), Product(name="P2", url="https://example.com/p2")]
    result = TrackerResult.success(products, source="scraper")
    with store._connect() as conn:
        run_id = store._insert_run_record(conn, result, "AI", 20, "success")
        store._insert_all_snapshots(conn, run_id, products, result.fetched_at.isoformat())
        conn.commit()
        row = conn.execute(
            "SELECT COUNT(*) FROM product_snapshots WHERE run_id=?", (run_id,)
        ).fetchone()
    assert row[0] == 2
```

`test_save_success_persists_run_products_and_snapshots` already verifies that `save_result` creates one run row, two product rows, and two snapshot rows — the same behavioural contract these private tests try to prove.  These tests add zero coverage beyond what the public test provides.

### `tests/unit/test_api_client.py` — one offender

```python
def test_build_query_returns_clean_payload_and_local_filter() -> None:
    from ph_ai_tracker.api_client import QueryContext

    context = ProductHuntAPI._build_query(
        first=10, order="RANKING", topic_slug=None, search_term=" AI "
    )

    assert isinstance(context, QueryContext)
    assert set(context.payload.keys()) == {"query", "variables"}
    assert context.local_filter == "ai"
```

`_build_query` is a private helper (`_` prefix).  The behaviour it tests — specifically that `search_term` whitespace is stripped and lowercased into the local filter — must be observable through `fetch_ai_products`.

---

## Goal

Delete the three private-method tests.  Replace the `_build_query` test with a public-contract test that verifies the strip/lowercase normalisation through `fetch_ai_products`.  The two storage private tests are fully superseded by the existing public test; no replacement is needed.

---

## Files to Change

| File | Change |
|------|--------|
| `tests/unit/test_storage.py` | Delete `test_insert_run_record_returns_integer_id` and `test_insert_all_snapshots_writes_expected_rows` |
| `tests/unit/test_api_client.py` | Delete `test_build_query_returns_clean_payload_and_local_filter`; add `test_fetch_strips_and_lowercases_search_term` |

---

## Exact Code Changes

### `tests/unit/test_storage.py`

**Delete** these two test functions entirely (no replacement):

- `test_insert_run_record_returns_integer_id`
- `test_insert_all_snapshots_writes_expected_rows`

The existing `test_save_success_persists_run_products_and_snapshots` provides complete public-contract coverage for the same behaviour:

```python
def test_save_success_persists_run_products_and_snapshots(tmp_path: Path) -> None:
    # ... verifies run count, product count, AND snapshot count via save_result(result)
```

### `tests/unit/test_api_client.py`

**Delete** `test_build_query_returns_clean_payload_and_local_filter`.

**Add** the following replacement that verifies the same normalisation through the public API:

```python
def test_fetch_strips_and_lowercases_search_term(api_success_payload: dict) -> None:
    """``fetch_ai_products`` normalises ``search_term`` whitespace/case: ' AI ' == 'AI'."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=api_success_payload)

    api = ProductHuntAPI("token", transport=httpx.MockTransport(handler))
    try:
        results_clean  = api.fetch_ai_products(search_term="AI",  limit=10)
        results_padded = api.fetch_ai_products(search_term=" AI ", limit=10)
    finally:
        api.close()
    assert results_clean == results_padded
```

This test exercises `fetch_ai_products → _build_query → StrictAIFilter` end-to-end through the public interface.  If whitespace stripping is ever broken, this test will catch it.

---

## Acceptance Criteria

- [ ] `grep "test_insert_run_record_returns_integer_id\|test_insert_all_snapshots_writes_expected_rows" tests/unit/test_storage.py` → 0 matches.
- [ ] `grep "test_build_query_returns_clean_payload_and_local_filter" tests/unit/test_api_client.py` → 0 matches.
- [ ] `grep "_insert_run_record\|_insert_all_snapshots\|_build_query" tests/unit/test_storage.py tests/unit/test_api_client.py` → 0 matches.
- [ ] `test_fetch_strips_and_lowercases_search_term` passes.
- [ ] Full pytest suite passes (no regressions — the public-contract tests still cover the deleted behaviours).
- [ ] `make bundle` reports ✓ all functions ≤ 20 lines.

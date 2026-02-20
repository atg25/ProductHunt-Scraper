# Sprint 31 — Remove Lingering Banner Comments

## Uncle Bob's Verdict

> "In our last review, I asked you to remove the massive ASCII banner comments from the codebase. While you removed them from some files, they are still cluttering up others. In `api_client.py`... And in `cli.py`... Fix it: Delete them. Your file structure and method names (like `build_provider`) are clear enough. If a file feels like it needs distinct visual 'zones,' it usually means those zones belong in separate modules."

## Problem

Despite Sprint 28 cleaning up `scraper.py`, ASCII banner comments (`# ---`) still exist in `api_client.py` and `cli.py`. These banners are visual clutter and a code smell indicating that a file might be trying to do too much.

## Goal

Remove all remaining ASCII banner comments from the codebase.

## Implementation

### `src/ph_ai_tracker/api_client.py`

Delete the banner block:

```python
# ---------------------------------------------------------------------------
# GraphQL query templates — {order} is replaced at call time with RANKING|NEWEST
# ---------------------------------------------------------------------------
```

### `src/ph_ai_tracker/cli.py`

Delete the banner block:

```python
# ---------------------------------------------------------------------------
# Provider factory — single place where concrete adapters are constructed
# ---------------------------------------------------------------------------
```

## Acceptance Criteria

- [ ] `grep -c "# ---" src/ph_ai_tracker/*.py` returns `0`.
- [ ] Full test suite remains green.
- [ ] `make bundle` exits 0.

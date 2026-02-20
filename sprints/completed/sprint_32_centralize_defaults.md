# Sprint 32 — Centralize Domain Default Constants

## Uncle Bob's Verdict

> "You have scattered your default business logic values across multiple modules... In `cli.py`, you define `_DEFAULT_SEARCH   = "AI"` and `_DEFAULT_LIMIT    = 20`. In `api_client.py`, `fetch_ai_products` hardcodes the defaults `search_term: str = "AI"` and `limit: int = 20`. In `scheduler.py`, `SchedulerConfig` hardcodes `search_term: str = "AI"` and `limit: int = 20`. This is a subtle violation of the DRY (Don't Repeat Yourself) principle... Fix it: Create a single source of truth for your domain's default values (perhaps a `constants.py` file in your domain layer) and import them wherever defaults are assigned."

## Problem

The default search term `"AI"` and default limit `20` are hardcoded in multiple places:

- `cli.py` (`_DEFAULT_SEARCH`, `_DEFAULT_LIMIT`)
- `api_client.py` (`fetch_ai_products` signature)
- `scheduler.py` (`SchedulerConfig` signature)
- `tracker.py` (`get_products` signature)

If the business decides the default search term should be "Machine Learning", a developer would have to track down and update this string in four separate files.

## Goal

Extract these domain defaults into a single `constants.py` file and import them across the codebase.

## Implementation

### 1. Create `src/ph_ai_tracker/constants.py`

```python
"""Domain-wide constants and default values."""

DEFAULT_SEARCH_TERM = "AI"
DEFAULT_LIMIT = 20
```

### 2. Update `src/ph_ai_tracker/cli.py`

- Import `DEFAULT_SEARCH_TERM`, `DEFAULT_LIMIT` from `.constants`.
- Replace `_DEFAULT_SEARCH` and `_DEFAULT_LIMIT` with the imported constants.

### 3. Update `src/ph_ai_tracker/api_client.py`

- Import constants.
- Update signature: `def fetch_ai_products(..., search_term: str = DEFAULT_SEARCH_TERM, limit: int = DEFAULT_LIMIT)`

### 4. Update `src/ph_ai_tracker/scheduler.py`

- Import constants.
- Update `SchedulerConfig` fields to use `default=DEFAULT_SEARCH_TERM` and `default=DEFAULT_LIMIT`.

### 5. Update `src/ph_ai_tracker/tracker.py`

- Import constants.
- Update `get_products` signature to use the constants.

### 6. Update `scripts/build_bundle.py`

- Add `SRC / "constants.py"` to `SECTION_3_PRODUCTION` so it appears in the review bundle.

## Acceptance Criteria

- [ ] `constants.py` exists and contains `DEFAULT_SEARCH_TERM` and `DEFAULT_LIMIT`.
- [ ] `"AI"` and `20` (as defaults) no longer appear as magic literals in `cli.py`, `api_client.py`, `scheduler.py`, or `tracker.py`.
- [ ] `constants.py` is included in the `make bundle` output.
- [ ] Full test suite remains green.

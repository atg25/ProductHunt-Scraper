# Sprint 24 — Extract Pagination Magic Numbers as Named Constants

## Uncle Bob's Complaint

> In `fetch_ai_products`, the expression `min(max(limit_int * 5, 20), 50)` buries
> three magic numbers with no explanation. A developer reading this a year from
> now will have to guess why `5`, `20`, and `50`.
> Fix: extract `_PAGINATION_MULTIPLIER`, `_MIN_FETCH_SIZE`, and `_MAX_FETCH_SIZE`.

---

## Root Cause

`api_client.py` line 201:

```python
first=min(max(limit_int * 5, 20), 50),
```

**Why these values?**

- `* 5` — over-fetch by 5× so that client-side keyword filtering has enough
  candidates to return `limit` results after culling.
- `20` — minimum batch size; fetching fewer than 20 is wasteful given API
  overhead.
- `50` — maximum batch size; the Product Hunt API returns at most 50 posts in
  one query; requesting more is silently clamped or rejected.

Without names, these constraints are invisible. The module docstring even
describes the `* 5` rule ("over-fetches … `request_first = min(limit * 5, 50)`")
but the code doesn't reflect it.

---

## TDD Plan

### Step 1 — Write the failing tests (RED)

File: `tests/unit/test_api_client.py` — add tests that assert the constants
exist and that `fetch_ai_products` respects them.

| Test                                                 | Assertion                                                                                                          | Colour before fix                                       |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| `test_pagination_multiplier_constant_exists`         | `from ph_ai_tracker.api_client import _PAGINATION_MULTIPLIER; assert _PAGINATION_MULTIPLIER == 5`                  | 🔴 FAIL                                                 |
| `test_min_fetch_size_constant_exists`                | `_MIN_FETCH_SIZE == 20`                                                                                            | 🔴 FAIL                                                 |
| `test_max_fetch_size_constant_exists`                | `_MAX_FETCH_SIZE == 50`                                                                                            | 🔴 FAIL                                                 |
| `test_fetch_never_requests_more_than_max_fetch_size` | Mock the API; call with `limit=100`; assert the `"variables"."first"` in the POSTed payload is ≤ `_MAX_FETCH_SIZE` | 🔴 FAIL (constant doesn't exist to compare against yet) |
| `test_fetch_never_requests_less_than_min_fetch_size` | Call with `limit=1`; assert `"variables"."first"` is ≥ `_MIN_FETCH_SIZE`                                           | 🔴 FAIL                                                 |

### Step 2 — Add the constants and use them (GREEN)

In `src/ph_ai_tracker/api_client.py`, add three module-level constants near
the other module-level constants (after `_STRICT_TERMS`, before the class
definitions):

```python
# Pagination — the API is queried for more results than the caller requested
# so that client-side keyword filtering has enough candidates.
_PAGINATION_MULTIPLIER: int = 5   # over-fetch factor applied to caller's limit
_MIN_FETCH_SIZE: int       = 20   # minimum batch size (avoids tiny API round-trips)
_MAX_FETCH_SIZE: int       = 50   # hard cap: Product Hunt API max per request
```

Update `fetch_ai_products`:

```python
# Before
first=min(max(limit_int * 5, 20), 50),

# After
first=min(max(limit_int * _PAGINATION_MULTIPLIER, _MIN_FETCH_SIZE), _MAX_FETCH_SIZE),
```

No other logic changes — purely a naming improvement.

### Step 3 — Regression check

All existing `fetch_ai_products` tests must pass unchanged (the runtime
behaviour is identical — only the source-level names change).

---

## Acceptance Criteria

1. `_PAGINATION_MULTIPLIER = 5`, `_MIN_FETCH_SIZE = 20`, `_MAX_FETCH_SIZE = 50`
   are importable module-level constants in `api_client.py`.
2. The literal numbers `5`, `20`, `50` no longer appear inside
   `fetch_ai_products` (or any other method body — they live only in the
   constant definitions).
3. New unit tests asserting constant values and boundary behaviour pass.
4. Full test suite remains green; function sizes remain ≤ 20 lines.

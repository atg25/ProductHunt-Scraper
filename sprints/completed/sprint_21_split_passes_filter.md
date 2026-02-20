# Sprint 21 — Eliminate the Boolean Flag from `_passes_filter` (SRP)

## Uncle Bob's Complaint

> `def _passes_filter(p, local_filter, strict, ai_filter) -> bool` passes a boolean
> `strict` into the function — a loud signal that the function does two different
> things. Split it into `_passes_strict_filter` and `_passes_loose_filter`. Let the
> caller decide which to invoke.

---

## Root Cause

`api_client.py` lines 316-324:

```python
@staticmethod
def _passes_filter(
    p: Product, local_filter: str, strict: bool, ai_filter: StrictAIFilter
) -> bool:
    """Return True if p satisfies local_filter."""
    haystack = " ".join([p.name or "", p.tagline or "", ...])
    if strict:
        return ai_filter.is_match(haystack, p.topics)
    return local_filter in haystack.lower()
```

The `if strict:` branch is the flag-argument smell: two distinct behaviours live in one
function, selected by a bool.

Caller (`_build_products_from_edges`):

```python
ai_filter = StrictAIFilter()
strict    = StrictAIFilter.is_strict_term(local_filter)
...
if not local_filter or self._passes_filter(p, local_filter, strict, ai_filter):
```

---

## TDD Plan

### Step 1 — Write the failing tests (RED)

File: `tests/unit/test_api_client.py` — add tests that target the _new_ API.

| Test                                           | Assertion                                                                        | Expected colour before fix           |
| ---------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------ |
| `test_passes_strict_filter_matches_ai_product` | `_passes_strict_filter(ai_product, ai_filter)` returns `True`                    | 🔴 FAIL (function doesn't exist yet) |
| `test_passes_strict_filter_rejects_non_ai`     | `_passes_strict_filter(non_ai_product, ai_filter)` returns `False`               | 🔴 FAIL                              |
| `test_passes_loose_filter_matches_substring`   | `_passes_loose_filter(product, "tracker")` returns `True` when "tracker" in name | 🔴 FAIL                              |
| `test_passes_loose_filter_rejects_mismatch`    | `_passes_loose_filter(product, "zzz")` returns `False`                           | 🔴 FAIL                              |
| `test_passes_filter_no_longer_exists`          | `assert not hasattr(ProductHuntAPI, "_passes_filter")`                           | 🔴 FAIL                              |

### Step 2 — Fix the source (GREEN)

In `src/ph_ai_tracker/api_client.py`, replace the single function with two:

```python
@staticmethod
def _passes_strict_filter(p: Product, ai_filter: StrictAIFilter) -> bool:
    """Return True if p satisfies the strict AI keyword/topic filter."""
    haystack = " ".join([p.name or "", p.tagline or "", p.description or "", " ".join(p.topics)])
    return ai_filter.is_match(haystack, p.topics)

@staticmethod
def _passes_loose_filter(p: Product, local_filter: str) -> bool:
    """Return True if local_filter appears anywhere in p's text fields."""
    haystack = " ".join([p.name or "", p.tagline or "", p.description or "", " ".join(p.topics)])
    return local_filter in haystack.lower()
```

Update `_build_products_from_edges` to call the correct function directly:

```python
ai_filter = StrictAIFilter()
strict    = StrictAIFilter.is_strict_term(local_filter)
...
if not local_filter:
    products.append(p)
elif strict and self._passes_strict_filter(p, ai_filter):
    products.append(p)
elif not strict and self._passes_loose_filter(p, local_filter):
    products.append(p)
```

### Step 3 — Regression check

- `_passes_filter` is fully removed (no dead code).
- All prior `_build_products_from_edges` integration tests still pass.
- `haystack` construction is not duplicated: if both helpers share logic, extract a
  `_product_haystack(p)` module-level helper to keep DRY (apply only if both helpers
  would otherwise contain identical lines).

---

## Acceptance Criteria

1. `_passes_filter` is deleted; `_passes_strict_filter` and `_passes_loose_filter`
   exist as separate `@staticmethod` methods on `ProductHuntAPI`.
2. Neither new function accepts a `bool` parameter.
3. `_build_products_from_edges` calls the correct function without passing a boolean.
4. New unit tests for both filter functions pass.
5. Full test suite remains green.

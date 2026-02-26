# Sprint 61 — Trust the Contract: Remove Exception Muzzle in _enrich_product

## Problem Statement
`AIProductTracker._enrich_product` wraps `self._tagger.categorize()` in a bare
`except Exception` block:

```python
def _enrich_product(self, product: Product) -> Product:
    try:
        tags = self._tagger.categorize(product)
    except Exception:
        tags = ()
    return replace(product, tags=tags)
```

This violates two principles:
1. **Trust your contracts.** Every concrete `TaggingService` implementation (`NoOpTaggingService`,
   `UniversalLLMTaggingService`) is specified to be failure-safe and never raise. Swallowing
   `Exception` here hides bugs in the Use Case layer itself (typos, `AttributeError`, etc.) and
   makes the system appear to succeed when it is broken.
2. **The Acyclic Dependencies Principle.** The original sprint plan tried to solve the default by
   importing `NoOpTaggingService` into the Use Case; that was correctly rejected in Sprint 55. The
   exception muzzle is the lingering ghost of that defensive paranoia.

The fix: delete the try/except. Let exceptions propagate to the caller.

## Acceptance Criteria
1. `_enrich_product` contains no `try`/`except` block.
2. If a `TaggingService` implementation raises `RuntimeError`, `_enrich_product` propagates it.
3. Existing tests that **expected** the exception to be swallowed are deleted or updated to
   instead assert that exceptions propagate.
4. `NoOpTaggingService` and `UniversalLLMTaggingService` tests still confirm those concrete
   implementations never raise (their own failure-safety is unchanged).
5. `make bundle` passes; all functions within 20-line limit.

## TDD Plan

### RED phase — write tests that expose the muzzle

**Unit — `tests/unit/test_tracker.py`** (extend):
- `test_enrich_product_propagates_tagger_exception` — create a tagger that raises `RuntimeError`;
  assert that calling `_enrich_product` propagates `RuntimeError` (currently fails because it was
  swallowed).

**Unit — `tests/unit/test_tracker.py`**:
- `test_get_products_propagates_tagger_exception` — full `get_products` call with a raising tagger;
  assert `RuntimeError` bubbles through (currently fails).

**E2E negative — `tests/e2e/test_e2e_negative.py`**:
- `test_e2e_broken_tagger_raises_at_runtime` — wire a tagger that raises into
  `AIProductTracker` and call `get_products`; assert the exception propagates rather than
  producing a silent empty-tag result.

### GREEN phase — remove the try/except
```python
def _enrich_product(self, product: Product) -> Product:
    tags = self._tagger.categorize(product)
    return replace(product, tags=tags)
```

### REFACTOR phase
- Delete or rewrite any existing test that asserted exception swallowing (e.g.
  `test_enrich_falls_back_on_tagger_exception` if it exists).
- Run full suite; confirm all pass.
- Run `make bundle`.

## Definition of Done
- [x] `_enrich_product` has no try/except
- [x] `test_enrich_product_propagates_tagger_exception` passes
- [x] `test_get_products_propagates_tagger_exception` passes
- [x] `test_e2e_broken_tagger_raises_at_runtime` passes
- [x] No test in the suite asserts that tagger exceptions are silently swallowed
- [x] `make bundle` exits 0
- [x] Full `pytest -q` passes

## Dependencies
Sprint 60 (bundle must include tracker.py — already in list; no additional dependency).

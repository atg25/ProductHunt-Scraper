# Sprint 55 — Use-Case Enrichment (Tagging in `AIProductTracker`)

## Objective

Extend the `AIProductTracker` use case to accept a `TaggingService` and
enrich each fetched product with tags before returning the result. The use
case must remain failure-safe: a tagging error must not degrade the result.

## Why (Clean Architecture)

`AIProductTracker` is **Application Layer Policy**. It orchestrates steps:
fetch → enrich → return. It depends only on the `TaggingService` abstraction,
not on any concrete LLM or NoOp class. Dependency is injected at
construction time.

## Scope

**In:** `src/ph_ai_tracker/tracker.py`,
`tests/unit/test_tracker.py`  
**Out:** No bootstrap wiring yet (Sprint 56). No CLI changes.

---

## TDD Cycle

### Red — write failing tests first

File: `tests/unit/test_tracker.py`

```
test_get_products_enriches_products_with_tags
    Inject a stub TaggingService that returns ("ai",) for any product.
    Call get_products() → each product in result.products has tags == ("ai",).

test_get_products_uses_noop_when_no_tagging_service_provided
    Construct AIProductTracker without tagging_service kwarg.
    Products in result have tags == () (default NoOp).

test_tagging_failure_does_not_fail_the_result
    Inject a TaggingService whose categorize() raises RuntimeError.
    get_products() returns a success TrackerResult with products present
    (tags == () for each product that failed enrichment).

test_tagging_is_not_called_on_fetch_failure
    Inject a provider that raises APIError and a spy TaggingService.
    result.error is not None → TaggingService.categorize was never called.

test_enrichment_produces_new_product_instances
    Products in result are new frozen instances with tags set;
    the original products from the provider have tags == ().

test_enrichment_preserves_all_other_product_fields
    After enrichment, name/tagline/description/votes/url/topics unchanged.
```

### Green

1. Change `AIProductTracker.__init__` signature:

   ```python
   def __init__(self, *, provider: ProductProvider,
                tagging_service: TaggingService | None = None) -> None:
   ```

   Store `self._tagger = tagging_service or NoOpTaggingService()`.

2. Add `_enrich_product(product: Product) -> Product` method:

   ```python
   def _enrich_product(self, p: Product) -> Product:
       try:
           tags = self._tagger.categorize(p)
       except Exception:
           tags = ()
       return dataclasses.replace(p, tags=tags)
   ```

3. In `get_products`, after fetching, map `_enrich_product` over the product
   list before passing to `TrackerResult.success`.

### Refactor

`_enrich_product` and the enrichment map must each be ≤ 20 lines.
The `get_products` method must remain ≤ 20 lines.

---

## Definition of Done

- [x] All new tracker tests green.
- [x] Tagging failure does NOT propagate to caller.
- [x] Tagging is skipped entirely on fetch failure.
- [x] `AIProductTracker` with no `tagging_service` kwarg works identically to
    before this sprint (backward compatible).
- [x] `make bundle` passes.
- [x] All pre-existing tests still green.

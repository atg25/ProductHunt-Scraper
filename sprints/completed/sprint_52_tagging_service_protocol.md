# Sprint 52 — `TaggingService` Protocol (Application Boundary)

## Objective

Define the `TaggingService` abstract interface in the application boundary
layer so the use case can depend on an abstraction rather than a concrete
implementation.

## Why (Clean Architecture)

A `Protocol` in `protocols.py` (application layer) is the **dependency
inversion plug**. The use case (`tracker.py`) points inward to this
interface. The outer-layer implementations (NoOp, LLM) point inward toward
it. Nothing in the inner layers knows how tags are produced.

## Scope

**In:** `src/ph_ai_tracker/protocols.py`, `tests/unit/test_protocols.py`  
**Out:** No new implementations yet (Sprint 53–54). No tracker change yet
(Sprint 55).

---

## TDD Cycle

### Red — write failing tests first

File: `tests/unit/test_protocols.py`

```
test_tagging_service_protocol_is_runtime_checkable
    assert isinstance(obj, TaggingService) can be checked at runtime.

test_class_with_categorize_satisfies_protocol
    A bare class that implements categorize(product) -> tuple[str,...]
    passes isinstance check.

test_class_without_categorize_does_not_satisfy_protocol
    A class missing categorize does NOT pass isinstance check.

test_categorize_return_type_annotation_is_tuple_of_str
    Inspect TaggingService.categorize return annotation == tuple[str, ...].

test_categorize_accepts_product_argument
    Inspect TaggingService.categorize parameter named "product".
```

### Green

In `protocols.py`, add:

```python
@runtime_checkable
class TaggingService(Protocol):
    """Categorise a product into a tuple of lowercase string tags."""

    def categorize(self, product: Product) -> tuple[str, ...]:
        ...
```

Import `Product` inside `TYPE_CHECKING` guard (already present) so there is
no circular import.

### Refactor

Ensure `protocols.py` still exports only what is needed; add `TaggingService`
to any `__all__` if one exists.

---

## Definition of Done

- [x] Protocol is `@runtime_checkable`.
- [x] All new protocol tests green.
- [x] No existing test broken.
- [x] `make bundle` passes.
- [x] `TaggingService` is importable from `ph_ai_tracker.protocols`.

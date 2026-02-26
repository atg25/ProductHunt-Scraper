# Sprint 53 — `NoOpTaggingService` (Outer Layer)

## Objective

Implement the null-object tagging service that always returns an empty tuple.
This is the safe default when no LLM key is configured and the mechanism used
in all tests that do not exercise tagging.

## Why (Clean Architecture)

`NoOpTaggingService` is an **outer-layer mechanism** — a Frameworks & Drivers
detail. It satisfies the `TaggingService` protocol without leaking any
mechanism concern into the application or entity layers. It also embodies the
Null Object pattern: callers never need to branch on `tagging_service is None`.

## Scope

**In:** `src/ph_ai_tracker/tagging.py` (new file),
`tests/unit/test_tagging.py` (new file)  
**Out:** No use-case wiring yet (Sprint 55). No bootstrap wiring yet (Sprint 56).

---

## TDD Cycle

### Red — write failing tests first

File: `tests/unit/test_tagging.py`

```
test_noop_satisfies_tagging_service_protocol
    isinstance(NoOpTaggingService(), TaggingService) is True

test_noop_categorize_returns_empty_tuple
    NoOpTaggingService().categorize(Product("X")) == ()

test_noop_categorize_returns_tuple_not_list
    isinstance(NoOpTaggingService().categorize(Product("X")), tuple)

test_noop_categorize_returns_empty_for_any_product
    Parametrize: several different products → always ()

test_noop_categorize_never_raises
    Call with Product("X") inside try/except → no exception raised.
```

### Green

Create `src/ph_ai_tracker/tagging.py`:

```python
class NoOpTaggingService:
    """Tagging service that always returns no tags.

    Used when no LLM key is available. Satisfies TaggingService protocol.
    """

    def categorize(self, product: Product) -> tuple[str, ...]:
        return ()
```

### Refactor

Confirm the module is ≤ 20 lines per function and has a module docstring
explaining its outer-layer role.

---

## Definition of Done

- [x] `NoOpTaggingService` lives in `tagging.py` (outer layer, not `models.py`
    or `protocols.py`).
- [x] All new tests green.
- [x] `isinstance(NoOpTaggingService(), TaggingService)` is `True`.
- [x] `make bundle` passes.

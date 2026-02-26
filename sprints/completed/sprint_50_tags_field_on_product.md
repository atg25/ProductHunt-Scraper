# Sprint 50 — Add `tags` Field to `Product` Entity

## Objective

Extend the `Product` entity with an immutable `tags` field so the domain
model can carry enrichment data produced by the tagging layer.

## Why (Clean Architecture)

`Product` is an **Enterprise Rule** (innermost ring). It must be able to
represent tags without knowing who produced them. Adding the field here
means every outer layer gains the ability to read and write tags through the
same clean, typed interface.

## Scope

**In:** `src/ph_ai_tracker/models.py`, `tests/unit/test_models.py`  
**Out:** No storage schema change, no tagging logic, no serialization change
beyond `to_dict` / `from_dict`.

---

## TDD Cycle

### Red — write failing tests first

File: `tests/unit/test_models.py`

```
test_product_tags_defaults_to_empty_tuple
    Product("X") → tags == ()

test_product_tags_accepts_tuple_of_strings
    Product("X", tags=("ai", "tool")) → tags == ("ai", "tool")

test_product_from_dict_populates_tags
    from_dict({"name":"X","tags":["ai","tool"]}) → tags == ("ai","tool")

test_product_from_dict_missing_tags_key_defaults_to_empty
    from_dict({"name":"X"}) → tags == ()

test_product_from_dict_null_tags_defaults_to_empty
    from_dict({"name":"X","tags":null}) → tags == ()

test_product_to_dict_includes_tags
    Product("X", tags=("ai",)).to_dict()["tags"] == ["ai"]

test_product_to_dict_tags_is_list_not_tuple
    isinstance(Product("X").to_dict()["tags"], list)
```

### Green — make the tests pass

1. Add `tags: tuple[str, ...] = ()` field to `Product` (after `topics`).
2. Extend `__post_init__` to strip, lowercase, and deduplicate tags via a
   helper `_coerce_tags(raw)` — same signature pattern as `_coerce_topics`.
3. Update `to_dict` to include `"tags": list(self.tags)`.
4. Update `from_dict` to pass `tags=_coerce_tags(data.get("tags"))`.

### Refactor

Extract `_coerce_tags` so it mirrors `_coerce_topics` exactly.
Both helpers must be ≤ 20 lines.

---

## Definition of Done

- [x] All new tests green.
- [x] All pre-existing tests still green.
- [x] `make bundle` passes (`✓ All functions within 20-line guideline`).
- [x] `Product` remains a frozen dataclass with `slots=True`.
- [x] `tags` field is a `tuple[str, ...]`, never a list.

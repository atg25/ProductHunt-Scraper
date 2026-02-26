# Sprint 57 — `NewsletterFormatter` Presenter

## Objective

Implement a pure presenter that transforms a list of `Product` objects into a
structured newsletter dictionary. It knows nothing about storage, LLMs, or
HTTP. It formats data only.

## Why (Clean Architecture)

This is an **Interface Adapter** — it converts domain data into a presentation
format. It depends on entities inward (reads `Product`) but is never imported
by entities or use cases. Presentation detail stays at the boundary, not inside
the core.

## Scope

**In:** `src/ph_ai_tracker/formatters.py` (new file),
`tests/unit/test_formatters.py` (new file)  
**Out:** No CLI wiring yet. No storage interaction.

---

## TDD Cycle

### Red — write failing tests first

File: `tests/unit/test_formatters.py`

**Sorting:**

```
test_products_sorted_by_votes_desc
    [Product("A", votes_count=5), Product("B", votes_count=10)]
    → output["products"][0]["name"] == "B"

test_products_with_equal_votes_sorted_by_name_asc
    [Product("Zebra", votes_count=5), Product("Alpha", votes_count=5)]
    → output["products"][0]["name"] == "Alpha"

test_empty_product_list_returns_empty_products
    format([], generated_at) → output["products"] == []
```

**Tag frequencies:**

```
test_top_tags_counts_tag_occurrences
    Two products: one with tags=("ai","tool"), one with tags=("ai",)
    → top_tags contains {"tag":"ai","count":2} and {"tag":"tool","count":1}

test_top_tags_sorted_by_count_desc
    Most frequent tag appears first in top_tags list.

test_top_tags_empty_when_no_tags
    All products have tags=() → output["top_tags"] == []
```

**Field completeness:**

```
test_output_contains_generated_at_iso8601
    output["generated_at"] matches ISO8601 pattern.

test_output_contains_total_products
    output["total_products"] == len(products)

test_each_product_dict_has_all_required_fields
    Every dict in output["products"] has keys:
    name, tagline, description, url, votes, topics, tags

test_missing_optional_fields_use_defaults
    Product with only name set → tagline is None (or ""), description is None,
    url is None, votes is 0, topics is [], tags is [].

test_votes_field_name_is_votes_not_votes_count
    output["products"][0]["votes"] — key is "votes", not "votes_count".
```

**Determinism:**

```
test_format_is_deterministic
    Calling format() twice with same inputs → identical output dicts.
```

### Green

Create `src/ph_ai_tracker/formatters.py`:

```python
class NewsletterFormatter:
    def format(self, products: list[Product], generated_at: datetime) -> dict:
        sorted_products = self._sort(products)
        return {
            "generated_at": generated_at.isoformat(),
            "total_products": len(products),
            "top_tags": self._top_tags(products),
            "products": [self._product_dict(p) for p in sorted_products],
        }

    def _sort(self, products: list[Product]) -> list[Product]: ...
    def _top_tags(self, products: list[Product]) -> list[dict]: ...
    def _product_dict(self, product: Product) -> dict: ...
```

Each private helper ≤ 20 lines.

### Refactor

Ensure `_sort` uses a stable key `(-votes_count, name)`. Ensure `_top_tags`
uses `collections.Counter` and returns sorted by `(-count, tag)` for
determinism within ties.

---

## Definition of Done

- [x] All new formatter tests green.
- [x] Sort is deterministic (votes DESC, name ASC).
- [x] Tag frequencies are correct.
- [x] Every product dict contains all 7 required keys.
- [x] `NewsletterFormatter` has zero imports from `storage`, `tracker`,
  `scheduler`, or any LLM module.
- [x] `make bundle` passes.

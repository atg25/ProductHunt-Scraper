# Sprint 22 — Add `Product.searchable_text` Property (Feature Envy / DRY)

## Uncle Bob's Complaint

> The same string-concatenation logic is repeated in three places:
> `api_client._product_haystack`, `api_client._passes_loose_filter`, and
> `scraper._apply_filter`. The `Product` dataclass should be the absolute
> authority on its own textual representation.
> Fix: add `@property searchable_text` to `Product`; have all three sites call it.

---

## Root Cause

The identical pattern appears in three locations:

| File            | Line                   | Expression                                                                                                                                              |
| --------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `api_client.py` | `_product_haystack`    | `" ".join([p.name or "", p.tagline or "", p.description or "", " ".join(p.topics)]).lower()`                                                            |
| `api_client.py` | `_passes_loose_filter` | `" ".join([p.name or "", p.tagline or "", p.description or "", " ".join(p.topics)])` (`.lower()` applied after)                                         |
| `scraper.py`    | `_apply_filter`        | `" ".join([p.name, p.tagline or "", p.description or "", " ".join(p.topics)]).lower()` (note: `p.name` has no `or ""` guard here — a subtle latent bug) |

All three are envious of data that lives inside `Product`. `Product` itself
is the right owner of this logic.

---

## TDD Plan

### Step 1 — Write the failing tests (RED)

File: `tests/unit/test_models.py` — add tests for the new property.

| Test                                                | Assertion                                                                                    | Colour before fix |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------- | ----------------- |
| `test_product_searchable_text_includes_name`        | `"alphaai" in Product(name="AlphaAI").searchable_text`                                       | 🔴 FAIL           |
| `test_product_searchable_text_includes_tagline`     | `"copilot" in Product(name="X", tagline="AI copilot").searchable_text`                       | 🔴 FAIL           |
| `test_product_searchable_text_includes_description` | `"powerful" in Product(name="X", description="powerful tool").searchable_text`               | 🔴 FAIL           |
| `test_product_searchable_text_includes_topics`      | `"machine learning" in Product(name="X", topics=("Machine Learning",)).searchable_text`      | 🔴 FAIL           |
| `test_product_searchable_text_is_lowercase`         | `Product(name="AlphaAI").searchable_text == Product(name="AlphaAI").searchable_text.lower()` | 🔴 FAIL           |
| `test_product_searchable_text_handles_none_fields`  | `Product(name="X").searchable_text` does not raise                                           | 🔴 FAIL           |

### Step 2 — Add the property to `Product` (GREEN)

In `src/ph_ai_tracker/models.py`, add inside the `Product` dataclass body
(after `topics`, before `to_dict`):

```python
@property
def searchable_text(self) -> str:
    """Lowercase concatenation of all human-readable text fields."""
    return " ".join([
        self.name or "",
        self.tagline or "",
        self.description or "",
        " ".join(self.topics),
    ]).lower()
```

> **Note:** `Product` uses `slots=True`, which is compatible with `@property`
> in Python ≥ 3.10 frozen dataclasses. No structural change to the dataclass
> definition is needed.

### Step 3 — Remove duplication at all three call sites

**`api_client.py`**

- `_product_haystack`: replace body with `return p.searchable_text`.
- `_passes_loose_filter`: replace the inline `" ".join(...)` expression with
  `p.searchable_text` (drop the separate `.lower()` call — already lowercased).

**`scraper.py`**

- `_apply_filter`: replace the inline `" ".join([p.name, p.tagline or "", ...]).lower()`
  with `p.searchable_text` — this also fixes the latent `p.name` missing `or ""`
  guard for free.

### Step 4 — Regression check

Existing tests for `StrictAIFilter.is_match`, `_passes_strict_filter`,
`_passes_loose_filter`, and the scraper filter tests must all remain green.

---

## Acceptance Criteria

1. `Product.searchable_text` property exists, returns a lowercase string,
   includes all four fields, and handles `None` gracefully.
2. `_product_haystack` in `api_client.py` delegates entirely to
   `p.searchable_text`.
3. `_passes_loose_filter` uses `p.searchable_text` (no inline `" ".join`).
4. `scraper._apply_filter` uses `p.searchable_text` (no inline `" ".join`).
5. All haystack-construction duplication is eliminated.
6. Full test suite remains green; function sizes remain ≤ 20 lines.

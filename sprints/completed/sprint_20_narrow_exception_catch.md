# Sprint 20 — Narrow the Broad `except Exception` in `scraper.py`

## Uncle Bob's Complaint

> In `scraper.py`, `_extract_products` wraps both extractors in a dangerously wide
> `except Exception`. Catching `Exception` hides bugs, suppresses unexpected
> failures, and makes root-cause analysis impossible.
> Fix: catch only the specific exceptions the extractors are known to raise.

---

## Root Cause

`scraper.py` lines 321-328 (`_extract_products`):

```python
def _extract_products(self, html: str) -> list[Product]:
    try:
        products = self._next_data.extract(html)
        if not products:
            products = self._dom_fallback.extract(html)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Unexpected extraction failure: %s", exc, exc_info=True)
        products = []
    return products
```

### Which exceptions can the extractors actually raise?

Tracing the call chain:

| Source                                 | Exception              | Why                                                                                              |
| -------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------ |
| `json.loads` inside `_load_next_data`  | `json.JSONDecodeError` | malformed `__NEXT_DATA__` script (note: already caught inside `_load_next_data`, returns `None`) |
| BS4 tag navigation (`.get`, iteration) | `AttributeError`       | unexpected `None` in the DOM tree                                                                |
| Integer / slice coercion               | `ValueError`           | e.g. `_coerce_votes` on a non-numeric string                                                     |
| Dict key access on unexpected shapes   | `KeyError`             | malformed node structures                                                                        |

`ScraperError` (network failures) is raised _before_ this method in `_fetch_page` /
`_fetch_product_page` and should propagate **unchanged** — callers rely on it.

Any exception that isn't one of the four above signals a programming error and should
**not** be swallowed.

---

## TDD Plan

### Step 1 — Write the failing tests (RED)

File: `tests/unit/test_scraper.py` — add tests verifying propagation.

| Test                                                  | Setup                                                       | Assertion                                          | Expected colour               |
| ----------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------- | ----------------------------- |
| `test_extract_products_propagates_runtime_error`      | Mock `_next_data.extract` to raise `RuntimeError("bug")`    | `_extract_products(html)` re-raises `RuntimeError` | 🔴 FAIL (currently swallowed) |
| `test_extract_products_propagates_type_error`         | Mock `_next_data.extract` to raise `TypeError("bug")`       | re-raises `TypeError`                              | 🔴 FAIL                       |
| `test_extract_products_recovers_from_value_error`     | Mock `_next_data.extract` to raise `ValueError("parse")`    | returns `[]`                                       | 🟢 PASS after fix             |
| `test_extract_products_recovers_from_attribute_error` | Mock `_next_data.extract` to raise `AttributeError("attr")` | returns `[]`                                       | 🟢 PASS after fix             |
| `test_extract_products_recovers_from_key_error`       | Mock `_next_data.extract` to raise `KeyError("k")`          | returns `[]`                                       | 🟢 PASS after fix             |

### Step 2 — Fix the source (GREEN)

In `src/ph_ai_tracker/scraper.py`:

```python
# Before
except Exception as exc:  # noqa: BLE001

# After
except (ValueError, AttributeError, KeyError) as exc:
```

Remove the `# noqa: BLE001` comment — it's no longer needed once the broad catch is
gone.

### Step 3 — Regression check

Verify that `ScraperError`, `RuntimeError`, `TypeError`, and similar unexpected
exceptions are **not** caught (they propagate to the caller of `_extract_products`).

---

## Acceptance Criteria

1. `_extract_products` catches exactly `(ValueError, AttributeError, KeyError)`.
2. `RuntimeError` and `TypeError` raised by an extractor propagate out of
   `_extract_products` unchanged.
3. The `# noqa: BLE001` suppression comment is removed.
4. All existing scraper unit tests remain green.
5. Full test suite remains green.

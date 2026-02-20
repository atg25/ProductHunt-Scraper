# Sprint 35 — Delete `_product_haystack` Pointless Indirection

## Uncle Bob's Verdict

> "In `api_client.py`, you have a static method called `_product_haystack`. The entirety of this function is: `return p.searchable_text`. This is useless indirection. It adds a layer of abstraction that does nothing but waste vertical space and cognitive load. Fix it: Delete `_product_haystack` entirely. Update `_passes_strict_filter` to simply call `p.searchable_text` directly."

## Problem

`_product_haystack` is a one-line wrapper that delegates identically to `Product.searchable_text`:

```python
@staticmethod
def _product_haystack(p: Product) -> str:
    """Return lowercase searchable text for *p*."""
    return p.searchable_text
```

Its sole caller is `_passes_strict_filter`:

```python
@staticmethod
def _passes_strict_filter(p: Product, ai_filter: StrictAIFilter) -> bool:
    haystack = ProductHuntAPI._product_haystack(p)
    return ai_filter.is_match(haystack, p.topics)
```

The indirection adds a name, a docstring, and a class-qualified call (`ProductHuntAPI._product_haystack`) to express exactly `p.searchable_text`. A reader inspecting `_passes_strict_filter` must jump to `_product_haystack` only to discover it does nothing. A method that is its own explanation-demanding abstraction where none is needed violates the principle that names should reveal intent — not obscure something simple.

The `Product.searchable_text` property is itself a well-named, well-tested property that already serves as its own clean abstraction. Wrapping it once more adds noise.

## Goal

Delete `_product_haystack`. Inline `p.searchable_text` directly in `_passes_strict_filter`. The result is one fewer method, one fewer cognitive indirection jump, and no loss of clarity.

## Implementation

### 1. Delete `_product_haystack` from `src/ph_ai_tracker/api_client.py`

Remove the entire method:

```python
# DELETE this:
@staticmethod
def _product_haystack(p: Product) -> str:
    """Return lowercase searchable text for *p*."""
    return p.searchable_text
```

### 2. Update `_passes_strict_filter`

```python
# BEFORE:
@staticmethod
def _passes_strict_filter(p: Product, ai_filter: StrictAIFilter) -> bool:
    """Return ``True`` if *p* satisfies strict AI filtering."""
    haystack = ProductHuntAPI._product_haystack(p)
    return ai_filter.is_match(haystack, p.topics)

# AFTER:
@staticmethod
def _passes_strict_filter(p: Product, ai_filter: StrictAIFilter) -> bool:
    """Return ``True`` if *p* satisfies strict AI filtering."""
    return ai_filter.is_match(p.searchable_text, p.topics)
```

### 3. Remove any test targeting `_product_haystack` in `tests/unit/test_api_client.py`

Search for and delete any test function that calls `_product_haystack` directly. The behavior it tested is already covered by `test_searchable_text_*` tests in `test_models.py` and by the `StrictAIFilter` / integration tests in `test_api_client.py`.

## Acceptance Criteria

- [ ] `_product_haystack` is deleted; zero references remain in the codebase.
- [ ] `_passes_strict_filter` calls `p.searchable_text` directly.
- [ ] No tests reference `_product_haystack`.
- [ ] Full test suite remains green.

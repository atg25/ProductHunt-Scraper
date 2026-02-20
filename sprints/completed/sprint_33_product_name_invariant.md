# Sprint 33 — Enforce Product Name Invariant via `__post_init__`

## Uncle Bob's Verdict

> "Your `Product` dataclass has a docstring that states: 'Invariant: name is non-empty.' However, the very next sentence reads: 'direct dataclass construction bypassing that guard is the caller's responsibility to avoid.' Nonsense. An object is absolutely responsible for its own state. It is not the caller's job to keep your object valid; it is the object's job to refuse to be created in an invalid state. Fix it: Add a `__post_init__` method to the `Product` dataclass to assert that name is present and non-empty."

## Problem

`Product` is a frozen dataclass that documents a `name` invariant in plain English but does not enforce it in code. Any caller — including future contributors — can silently construct a `Product(name="")` or `Product(name="   ")` without any error:

```python
# This should raise — but it currently does not.
bad = Product(name="")
```

The docstring shifts responsibility onto the caller:

> "direct dataclass construction bypassing that guard is the caller's responsibility to avoid."

This is a broken contract. The invariant is stated but unguarded. The object cannot be trusted to be in a valid state after construction.

## Goal

Add a `__post_init__` method to `Product` that raises `ValueError` if `name` is empty or whitespace-only. Delete the dishonest clause from the docstring that offloads responsibility to the caller. Add tests that confirm the guard fires.

## Implementation

### 1. Update `src/ph_ai_tracker/models.py`

Add a `__post_init__` method to `Product`:

```python
def __post_init__(self) -> None:
    """Enforce the name invariant: name must be a non-empty string."""
    if not self.name or not self.name.strip():
        raise ValueError("Product.name must be a non-empty string")
```

Update the class docstring to remove the sentence that puts responsibility on the caller:

**Before:**
```
Invariant: ``name`` is non-empty.  A ``Product`` with an empty ``name``
cannot be constructed via ``from_dict``; direct dataclass construction
bypassing that guard is the caller's responsibility to avoid.
```

**After:**
```
Invariant: ``name`` is non-empty.  Attempting to construct a ``Product``
with a blank or whitespace-only ``name`` raises ``ValueError``.
```

### 2. Update `tests/unit/test_models.py`

Add tests for the new guard:

```python
def test_product_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Product(name="")

def test_product_rejects_whitespace_name() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Product(name="   ")

def test_product_accepts_valid_name() -> None:
    p = Product(name="ValidProduct")
    assert p.name == "ValidProduct"
```

## Acceptance Criteria

- [ ] `Product(name="")` raises `ValueError`.
- [ ] `Product(name="   ")` raises `ValueError`.
- [ ] `Product(name="ValidProduct")` constructs successfully.
- [ ] The docstring no longer blames the caller for empty-name construction.
- [ ] Full test suite remains green.

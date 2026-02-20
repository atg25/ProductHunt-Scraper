# Sprint 39 — DRY `from_dict`: Trust `__post_init__` as the Single Invariant Gatekeeper

**Source:** Uncle Bob Letter 8, Issue #3  
**Depends on:** Sprint 33 (which added `__post_init__` to `Product`)

---

## Problem Statement

`models.py` currently enforces the `Product.name` invariant in **two separate places**,
with **two different error messages**:

### Guard 1 — `Product.__post_init__` (added in Sprint 33)

```python
def __post_init__(self) -> None:
    if not self.name or not self.name.strip():
        raise ValueError("Product.name must be a non-empty string")
```

This is the **correct, authoritative** gatekeeper.  It runs on every code path that
constructs a `Product`, regardless of how it was invoked.

### Guard 2 — `Product.from_dict` (manual, pre-dates Sprint 33)

```python
@classmethod
def from_dict(cls, data: dict[str, Any]) -> "Product":
    """Build a ``Product`` from a plain dict (e.g. parsed JSON)."""
    if "name" not in data or not data["name"]:          # ← duplicate guard
        raise ValueError("Product.name is required")    # ← different message
    ...
    return cls(
        name=str(data["name"]),
        ...
    )
```

This guard was added before Sprint 33 existed.  After Sprint 33, it is **redundant**: if
`from_dict` ever constructs a `Product` with an empty name, `__post_init__` will reject it
*anyway*.  The manual pre-check just gets there first, with a slightly different message.
That inconsistency is the DRY violation Uncle Bob flagged.

---

## The Fix

Remove the pre-check entirely.  Let `__post_init__` do its job.

The only mechanical change required inside `from_dict` is how `name` is extracted.
Currently it uses:

```python
name=str(data["name"]),   # KeyError risk if guard above is absent
```

After removing the guard, use a safe default that routes through `__post_init__`:

```python
name=str(data.get("name") or ""),
```

**Why `data.get("name") or ""`?**

| Input | `data.get("name")` | `… or ""` | `str(…)` | `__post_init__` result |
|-------|--------------------|-----------|----------|------------------------|
| key absent | `None` | `""` | `""` | `ValueError` — correct |
| `"name": None` | `None` | `""` | `""` | `ValueError` — correct |
| `"name": ""` | `""` | `""` | `""` | `ValueError` — correct |
| `"name": "  "` | `"  "` | `"  "` | `"  "` | `ValueError` (whitespace) — correct |
| `"name": "Foo"` | `"Foo"` | `"Foo"` | `"Foo"` | passes — correct |

The pattern `str(data.get("name") or "")` is a single, readable expression that correctly
maps every falsy-name input to the empty string, which `__post_init__` then rejects with the
canonical error message: `"Product.name must be a non-empty string"`.

---

## Scope

- **File modified:** `src/ph_ai_tracker/models.py` only
- **Lines removed:** The two-line `if "name" not in data or not data["name"]:` /
  `raise ValueError("Product.name is required")` block — delete both lines in full.
- **Line changed:** `name=str(data["name"]),` → `name=str(data.get("name") or ""),`
- **No other logic is modified.**

### What stays the same

- `votes_count` validation (the `try/except (TypeError, ValueError)` block) is **not** a
  duplicate — `Product.__post_init__` does not validate votes.  Keep it.
- The `_coerce_topics` helper is unchanged.
- `__post_init__` is unchanged.

---

## Test Impact

The existing test suite already covers the invariant correctly:

| Test | Current behaviour | After sprint |
|------|-------------------|--------------|
| `test_product_from_dict_missing_name_raises` | `ValueError` from `from_dict` guard | `ValueError` from `__post_init__` — test still passes (no `match=` assertion) |
| `test_product_rejects_empty_name_direct_construction` | `ValueError` from `__post_init__` | unchanged |
| `test_product_rejects_whitespace_name_direct_construction` | `ValueError` from `__post_init__` | unchanged |

No new tests are required.  The existing coverage proves both the direct-construction path
and the `from_dict` path now share one gatekeeper.

---

## Acceptance Criteria

1. The two-line manual guard (`if "name" not in data or not data["name"]:` / `raise ValueError(…)`)
   is absent from `from_dict`.
2. `from_dict` uses `name=str(data.get("name") or ""),` instead of `name=str(data["name"]),`.
3. `grep -n "Product.name is required" src/ph_ai_tracker/models.py` returns **zero matches**.
4. `pytest --tb=short -q` passes with the **same count** as before this sprint
   (no tests added or removed).
5. `make bundle` completes successfully.

---

## Definition of Done

- [ ] Two-line duplicate guard deleted from `from_dict`
- [ ] `name=` line updated to use `str(data.get("name") or "")`
- [ ] `grep "Product.name is required" src/` returns zero matches
- [ ] Full test suite green (same count as before)
- [ ] Bundle regenerated
- [ ] This sprint moved to `sprints/completed/`

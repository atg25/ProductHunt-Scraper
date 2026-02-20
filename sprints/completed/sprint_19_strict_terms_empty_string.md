# Sprint 19 — Remove Empty-String Logical Bug from `_STRICT_TERMS`

## Uncle Bob's Complaint

> `_STRICT_TERMS = frozenset({"ai", "artificial intelligence", ""})` — why is an
> empty string a strict AI term? An empty search term should bypass filtering
> altogether, not trigger the strictest possible filter.
> Fix: remove `""` from `_STRICT_TERMS`.

---

## Root Cause

`api_client.py` line 77 defines:

```python
_STRICT_TERMS = frozenset({"ai", "artificial intelligence", ""})
```

`StrictAIFilter.is_strict_term` checks membership in that set:

```python
return term.strip().lower() in _STRICT_TERMS
```

An empty `search_term` (or whitespace-only) strips to `""`, matches, and activates
strict mode — silently over-filtering every result. Worse, a unit test at
`tests/unit/test_api_client.py:163` explicitly _asserts_ this broken behaviour:

```python
assert StrictAIFilter.is_strict_term("")
```

---

## TDD Plan

### Step 1 — Write the failing tests (RED)

File: `tests/unit/test_api_client.py` — add / modify tests.

| Test                                                                                                                                        | Assertion                                         | Expected colour before fix                              |
| ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------- |
| `test_strict_term_empty_string_is_false`                                                                                                    | `assert not StrictAIFilter.is_strict_term("")`    | 🔴 FAIL                                                 |
| `test_strict_term_whitespace_is_false`                                                                                                      | `assert not StrictAIFilter.is_strict_term("   ")` | 🔴 FAIL                                                 |
| Remove/invert the line `assert StrictAIFilter.is_strict_term("")` in the existing `test_strict_ai_filter_is_strict_term_recognises_ai` test | —                                                 | currently passes; must be updated to not codify the bug |

### Step 2 — Fix the source (GREEN)

In `src/ph_ai_tracker/api_client.py`:

```python
# Before
_STRICT_TERMS = frozenset({"ai", "artificial intelligence", ""})

# After
_STRICT_TERMS = frozenset({"ai", "artificial intelligence"})
```

No other changes needed — `is_strict_term` already strips/lowercases, so whitespace
strings correctly evaluate to `""` which is no longer in the set.

### Step 3 — Regression check

Verify `StrictAIFilter.is_strict_term("ai")` and `is_strict_term("AI")` still return
`True` (existing tests must stay green).

Verify that an empty `local_filter` still short-circuits the whole filter path (the
guard `if not local_filter or self._passes_filter(...)` in `_build_products_from_edges`
ensures an empty term bypasses filtering entirely, independent of this fix).

---

## Acceptance Criteria

1. `_STRICT_TERMS` contains exactly `{"ai", "artificial intelligence"}`.
2. `StrictAIFilter.is_strict_term("")` returns `False`.
3. `StrictAIFilter.is_strict_term("   ")` returns `False`.
4. All existing `StrictAIFilter` tests continue to pass.
5. Full test suite remains green.

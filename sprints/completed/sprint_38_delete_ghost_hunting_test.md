# Sprint 38 — Delete the Ghost-Hunting Test

**Source:** Uncle Bob Letter 8, Issue #2  
**Depends on:** Sprint 21 (which deleted `_passes_filter` and was the event being "commemorated")

---

## Problem Statement

`tests/unit/test_api_client.py` contains the following test:

```python
def test_passes_filter_no_longer_exists() -> None:
    assert not hasattr(ProductHuntAPI, "_passes_filter")
```

This test does not specify behaviour of the system.  It specifies the *absence of a historical
artefact* — a method that was deleted in Sprint 21.  Uncle Bob names this anti-pattern
**"Ghost Hunting"**: writing a test to prove that you deleted something three weeks ago.

---

## Why Ghost-Hunting Tests Are Harmful

### 1. Tests Must Describe Present Behaviour, Not Past Deletions

The test suite is a living specification.  Every assertion should answer the question
*"What does this system do right now?"*  An assertion of the form
`assert not hasattr(cls, "old_name")` answers a different question:
*"Did someone clean up my old code?"*  That is not a specification — it is a historical
footnote.

### 2. They Couple Tests to Implementation Vocabulary

If `ProductHuntAPI` is ever renamed or reorganised, this test fails for the wrong reason.
Similarly, if a future developer legitimately adds a method that happens to be called
`_passes_filter` with a completely different purpose, this test blocks them with a
misleading failure message.

### 3. They Add Noise to the Failure Log

If the system breaks and 20 tests fail, `test_passes_filter_no_longer_exists` appearing in
the output provides zero diagnostic value.  It pulls attention away from tests that actually
describe the current contract.

### 4. The Behaviour They Guard Is Already Proven Indirectly

Sprint 21 is complete.  The refactored predicate-composition logic is covered by the tests
that exercise `_passes_strict_filter`, `_passes_loose_filter`, and `fetch_ai_products`
directly.  Those tests would fail immediately if someone accidentally re-introduced an
incompatible `_passes_filter`.  A dedicated absence-assertion adds nothing.

---

## Scope

- **File modified:** `tests/unit/test_api_client.py` only
- **Change:** Delete the full function body of `test_passes_filter_no_longer_exists` —
  exactly two lines (the `def` line and the single `assert` statement)
- **Do NOT** delete any other test or modify any source file

---

## Acceptance Criteria

1. `test_passes_filter_no_longer_exists` no longer appears anywhere in the test suite.
2. `grep -rn "no_longer_exists\|Ghost\|hasattr.*_passes_filter" tests/` returns zero matches.
3. `pytest --tb=short -q` passes with a count **one lower** than before this sprint
   (exactly one test removed).
4. No other test is modified, added, or removed.
5. `make bundle` completes successfully.

---

## Definition of Done

- [ ] `test_passes_filter_no_longer_exists` deleted from `tests/unit/test_api_client.py`
- [ ] Test count drops by exactly 1
- [ ] Full test suite green
- [ ] Bundle regenerated
- [ ] This sprint moved to `sprints/completed/`

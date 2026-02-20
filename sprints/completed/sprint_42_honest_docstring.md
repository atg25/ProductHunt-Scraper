# Sprint 42 — Fix the Dishonest Docstring in `AIProductTracker`

**Status:** Active  
**Source:** Uncle Bob Letter 9, Issue #3 — The Dishonest Contract  
**Depends on:** Sprint 30 (narrowed exception catches to `APIError`, `ScraperError`,
`RateLimitError`; established the exact guarantee `get_products` can actually make)

---

## Problem Statement

`AIProductTracker` makes an absolute promise it cannot keep.

**Class docstring (current):**

```
Invariant: ``get_products`` *never raises*; every outcome is captured in
the returned ``TrackerResult``.
```

**Method docstring (current):**

```
"""Delegate to provider; map exceptions to TrackerResult failures; never raises."""
```

**The implementation:**

```python
    except RateLimitError as exc:
        return TrackerResult.failure(...)
    except (APIError, ScraperError) as exc:
        return TrackerResult.failure(...)
```

The implementation catches only three known domain exceptions. Any other exception
propagated by the provider — `ValueError`, `TypeError`, `httpx.ConnectError`,
`RuntimeError`, an unhandled `AttributeError` — will escape `get_products` and crash
the caller.

Uncle Bob's ruling from Letter 9:

> A contract that makes a promise it cannot keep is worse than no contract at all.

The fix is **not** to add a bare `except Exception` catch (Sprint 20 already
eliminated that pattern and for good reason: a generic muzzle hides programming bugs).
The fix is to update the docstrings to state precisely what is guaranteed: that the
three known domain exception types (`RateLimitError`, `APIError`, `ScraperError`) are
always mapped to `TrackerResult.failure` and will never propagate to the caller.
Unknown failures may still raise — and the docstring must say so.

---

## Acceptance Criteria

1. The class docstring for `AIProductTracker` no longer contains the phrase
   `never raises` in an unqualified form.
2. The docstring accurately describes the actual guarantee: known domain exceptions
   (`RateLimitError`, `APIError`, `ScraperError`) are captured; unknown failures may
   still raise.
3. The `get_products` method docstring is updated to match the same qualified statement.
4. The production logic in `tracker.py` is **unchanged** — no new `except` clauses,
   no code deletions.
5. `pytest` exits 0 with no regressions.
6. `make bundle` reports all functions ≤ 20 lines.

---

## Exact Changes Required

### `src/ph_ai_tracker/tracker.py` — docstrings only

**Class docstring — replace the `Invariant` sentence:**

Before:

```python
class AIProductTracker:
    """Use-case facade: fetch AI products from a single injected provider.

    The caller selects a strategy by constructing the correct ``ProductProvider``
    (a plain adapter, ``FallbackProvider``, or ``_NoTokenProvider``) and passing
    it here.  ``AIProductTracker`` itself knows nothing about strategy names,
    tokens, or fallback sequences.

    Invariant: ``get_products`` *never raises*; every outcome is captured in
    the returned ``TrackerResult``.
    """
```

After:

```python
class AIProductTracker:
    """Use-case facade: fetch AI products from a single injected provider.

    The caller selects a strategy by constructing the correct ``ProductProvider``
    (a plain adapter, ``FallbackProvider``, or ``_NoTokenProvider``) and passing
    it here.  ``AIProductTracker`` itself knows nothing about strategy names,
    tokens, or fallback sequences.

    Invariant: ``get_products`` never raises *known domain exceptions*
    (``RateLimitError``, ``APIError``, ``ScraperError``); these outcomes are
    captured in the returned ``TrackerResult``.  Unexpected failures may still
    propagate.
    """
```

**Method docstring — replace the unqualified `never raises` clause:**

Before:

```python
    def get_products(self, ...) -> TrackerResult:
        """Delegate to provider; map exceptions to TrackerResult failures; never raises."""
```

After:

```python
    def get_products(self, ...) -> TrackerResult:
        """Delegate to provider; map known domain exceptions to TrackerResult failures."""
```

No other line in `tracker.py` changes.

---

## Verification

```bash
# Unqualified "never raises" is gone
grep -n "never raises" src/ph_ai_tracker/tracker.py

# Qualified invariant is present
grep -n "known domain exceptions" src/ph_ai_tracker/tracker.py

# Full test suite passes (no logic changed; all tests must pass unchanged)
.venv/bin/python -m pytest --tb=short -q

# Bundle still clean
make bundle
```

Expected: first grep returns 0 lines; second grep returns 2 lines (class docstring +
confirmation in method docstring area); pytest exits 0; bundle reports all functions
≤ 20 lines.

---

## Definition of Done

- [ ] Class docstring `Invariant` sentence updated to qualified form in `tracker.py`
- [ ] `get_products` method docstring updated to qualified form in `tracker.py`
- [ ] Production logic (the `except` clauses) is **unchanged**
- [ ] `grep "never raises" src/ph_ai_tracker/tracker.py` → 0 matches
- [ ] `grep "known domain exceptions" src/ph_ai_tracker/tracker.py` → 2 matches
- [ ] `pytest` exits 0, no regressions
- [ ] `make bundle` all functions ≤ 20 lines
- [ ] Sprint doc moved to `sprints/completed/`

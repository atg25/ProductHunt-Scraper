# Sprint 43 — Restore Type Safety: `TrackerResult.is_transient`

**Status:** Active  
**Source:** Uncle Bob Letter 10, Issue #1 — Primitive Obsession and Type Erasure  
**Depends on:** Sprint 32 (established `DEFAULT_*` constants), Sprint 39 (from_dict DRY — models.py is the current stable baseline)

---

## Problem Statement

`AIProductTracker.get_products` catches three distinct typed exceptions and converts
all of them into raw strings:

```python
except RateLimitError as exc:
    return TrackerResult.failure(source=..., error=f"Rate limited: {exc}")
except (APIError, ScraperError) as exc:
    return TrackerResult.failure(source=..., error=str(exc))
```

At the Application layer, the code **knows** which exception type fired.  It
immediately discards that knowledge by squashing it into a primitive string.

`scheduler.py` must then perform string archaeology to recover the domain meaning:

```python
_TRANSIENT_TOKENS = frozenset({
    "timed out", "request failed", "network", "rate limited",
    "status=429", "status=500", "status=502", "status=503",
    "status=504", "temporarily unavailable",
})
def _is_transient_error(message: str | None) -> bool:
    if not message:
        return False
    text = message.lower()
    return any(token in text for token in _TRANSIENT_TOKENS)
```

This is Primitive Obsession: a framework-layer function guessing at domain meaning by
reading tea leaves from a string, meaning that could have been carried as a typed flag
from the beginning.

---

## Semantic Decision — Which exceptions are transient?

| Exception | `is_transient` | Rationale |
|---|---|---|
| `RateLimitError` | `True` | Temporary quota exhaustion — retrying after backoff is correct |
| `ScraperError` | `True` | Network-layer errors (timeout, HTTP 5xx on the scraper path) — transient by nature |
| `APIError` | `False` | API-level failures (auth refused, malformed payload, 4xx) — retrying wastes quota |

This changes one prior behaviour: `APIError` messages containing `"status=500"`, etc.,
were previously matched by `_TRANSIENT_TOKENS` and retried.  After this sprint they
will not be.  The tradeoff is accepted: the architectural benefit (eliminating string
parsing) outweighs the rare case of a 5xx from the GraphQL API, which should be
modelled as a separate `TransientAPIError` subclass in a future sprint if the need
arises.

---

## Acceptance Criteria

1. `TrackerResult` has a new `is_transient: bool = False` field.
2. `TrackerResult.failure()` accepts an `is_transient: bool = False` parameter and
   stores it.
3. `tracker.py` sets `is_transient=True` for `RateLimitError` and `ScraperError`,
   and leaves `is_transient=False` (default) for `APIError`.
4. `scheduler.py` uses `result.is_transient` in `_fetch_with_retries`; `_TRANSIENT_TOKENS`
   and `_is_transient_error` are **deleted entirely**.
5. `grep -n "_is_transient_error\|_TRANSIENT_TOKENS" src/ph_ai_tracker/scheduler.py` → 0 matches.
6. All existing `TrackerResult.success(...)` call sites are **unchanged** (the new
   field defaults to `False` on success; callers of `success` do not need updating).
7. `to_dict` and `to_pretty_json` are **not required** to expose `is_transient` — it
   is an operational field for the scheduler, not a persistence field.
8. `pytest` exits 0 with no regressions.
9. `make bundle` reports all functions ≤ 20 lines.

---

## Exact Changes Required

### A — `src/ph_ai_tracker/models.py`

**Step 1:** Add `is_transient: bool = False` as the last field of `TrackerResult`:

```python
@dataclass(frozen=True, slots=True)
class TrackerResult:
    """..."""

    products: tuple[Product, ...]
    source: str
    fetched_at: datetime
    error: str | None = None
    is_transient: bool = False
```

**Step 2:** Add `is_transient: bool = False` to `TrackerResult.failure()`:

Before:
```python
    @classmethod
    def failure(cls, source: str, error: str) -> "TrackerResult":
        return cls(products=(), source=source, fetched_at=datetime.now(timezone.utc), error=error)
```

After:
```python
    @classmethod
    def failure(cls, source: str, error: str, *, is_transient: bool = False) -> "TrackerResult":
        return cls(
            products=(), source=source, fetched_at=datetime.now(timezone.utc),
            error=error, is_transient=is_transient,
        )
```

### B — `src/ph_ai_tracker/tracker.py`

Separate the `(APIError, ScraperError)` catch into two distinct handlers so each can
be tagged correctly:

Before:
```python
        except RateLimitError as exc:
            return TrackerResult.failure(
                source=self._provider.source_name, error=f"Rate limited: {exc}"
            )
        except (APIError, ScraperError) as exc:
            return TrackerResult.failure(source=self._provider.source_name, error=str(exc))
```

After:
```python
        except RateLimitError as exc:
            return TrackerResult.failure(
                source=self._provider.source_name,
                error=f"Rate limited: {exc}",
                is_transient=True,
            )
        except ScraperError as exc:
            return TrackerResult.failure(
                source=self._provider.source_name,
                error=str(exc),
                is_transient=True,
            )
        except APIError as exc:
            return TrackerResult.failure(
                source=self._provider.source_name,
                error=str(exc),
                is_transient=False,
            )
```

Update the class docstring `Invariant` sentence to name the three exceptions in
their now-explicit order:

```
    Invariant: ``get_products`` never raises known domain exceptions
    (``RateLimitError``, ``ScraperError``, ``APIError``); these outcomes are
    captured in the returned ``TrackerResult``.  ``TrackerResult.is_transient``
    is ``True`` when the failure is safe to retry.  Unexpected failures may
    still propagate.
```

### C — `src/ph_ai_tracker/scheduler.py`

**Step 1:** Delete the two module-level constants:

```python
_TRANSIENT_TOKENS = frozenset({
    "timed out", "request failed", "network", "rate limited",
    "status=429", "status=500", "status=502", "status=503",
    "status=504", "temporarily unavailable",
})
```

and the `import re` line that is no longer needed if `re` is only used for the cron
validator — **check** whether `_CRON_ALLOWED_RE` still needs `re`; if it does, leave
the import.

**Step 2:** Delete the `_is_transient_error` function entirely (four lines).

**Step 3:** In `_fetch_with_retries`, replace the string-check line:

Before:
```python
        if not _is_transient_error(result.error) or attempt >= max_attempts:
```

After:
```python
        if not result.is_transient or attempt >= max_attempts:
```

### D — Tests

Update relevant tests in `tests/unit/test_scheduler.py` that test transient-retry
behaviour — any test that previously relied on `_is_transient_error` string matching
to gate retry should now be written to use `TrackerResult.failure(…, is_transient=True/False)`.

If explicit unit tests for `_is_transient_error` exist, delete them.

Add two new tests (or update existing ones) in `tests/unit/test_scheduler.py`:

**New test 1 — verifies transient result triggers retry:**
```python
def test_fetch_with_retries_retries_on_transient_result() -> None:
    from ph_ai_tracker.models import TrackerResult
    ...
    # provider returns a transient failure on first call, success on second
```

**New test 2 — verifies fatal result does NOT trigger retry:**
```python
def test_fetch_with_retries_does_not_retry_on_fatal_result() -> None:
    from ph_ai_tracker.models import TrackerResult
    ...
    # provider returns a non-transient failure; assert only one attempt made
```

Add to `tests/unit/test_tracker.py` (or create the file if absent):

**New test 3 — RateLimitError produces is_transient=True:**
```python
def test_get_products_rate_limit_is_transient() -> None:
    ...
    assert result.is_transient is True
```

**New test 4 — ScraperError produces is_transient=True:**
```python
def test_get_products_scraper_error_is_transient() -> None:
    ...
    assert result.is_transient is True
```

**New test 5 — APIError produces is_transient=False:**
```python
def test_get_products_api_error_is_not_transient() -> None:
    ...
    assert result.is_transient is False
```

---

## Verification

```bash
# _is_transient_error and _TRANSIENT_TOKENS deleted from scheduler
grep -n "_is_transient_error\|_TRANSIENT_TOKENS" src/ph_ai_tracker/scheduler.py

# is_transient field present in models
grep -n "is_transient" src/ph_ai_tracker/models.py

# tracker.py tags the three exception types
grep -n "is_transient" src/ph_ai_tracker/tracker.py

# full suite
.venv/bin/python -m pytest --tb=short -q
make bundle
```

Expected: first grep → 0 matches; second/third → present; pytest exits 0; bundle all functions ≤ 20 lines.

---

## Definition of Done

- [ ] `TrackerResult.is_transient: bool = False` field added to `models.py`
- [ ] `TrackerResult.failure()` accepts `is_transient` parameter
- [ ] `tracker.py` catches `RateLimitError`, `ScraperError`, `APIError` in separate handlers; first two tagged `is_transient=True`, last tagged `is_transient=False`
- [ ] `_TRANSIENT_TOKENS` and `_is_transient_error` deleted from `scheduler.py`
- [ ] `_fetch_with_retries` uses `result.is_transient` directly
- [ ] New tests for all three tagging paths + retry behaviour added
- [ ] `pytest` exits 0, no regressions
- [ ] `make bundle` all functions ≤ 20 lines
- [ ] Sprint doc moved to `sprints/completed/`

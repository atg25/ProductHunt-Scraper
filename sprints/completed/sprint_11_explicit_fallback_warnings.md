# Sprint 11 — Explicit Fallback Warnings & Configuration Clarity

## Knuth Concern Addressed

> "Be wary of silent fallbacks masking configuration errors. If an API token is
> expected but missing, a loud initialization warning is often preferable to
> silently shifting to a slower, less reliable scraping heuristic. Clarity is
> superior to cleverness."
> — Issue #5

---

## Sprint Goal

`AIProductTracker` in `auto` mode must **loudly announce** when it falls back
from the API path due to a missing or blank token — this is a _configuration_
error dressed up as a graceful degradation. Operators running under the
scheduler need to see the warning in their log stream so they can fix their
environment before the next run.

The existing behaviour (silently try API → silently fall back) is preserved
so no caller is broken. What changes is _visibility_: a `WARNING`-level log
and an optional `warnings.warn` at `RuntimeWarning` severity fire any time the
auto-strategy detects a missing token.

---

## Acceptance Criteria

1. When `strategy="auto"` and `api_token` is `None` or blank, and the API
   path is entered (even just to check), a `WARNING` log entry is emitted
   **before** switching to the scraper. The message must contain the string
   `"api_token"` so operators can grep for it.
2. The same condition also triggers `warnings.warn(…, RuntimeWarning,
stacklevel=2)` so that test suites and library users see it via Python's
   standard warnings machinery.
3. When `strategy="api"` and `api_token` is missing, the existing
   `TrackerResult.failure(source="api", error="Missing api_token")` is
   returned _unchanged_, but a `WARNING` log is additionally emitted (the
   failure message already reports the issue; the log makes it visible in the
   operator console without needing to inspect the returned object).
4. When a valid token is supplied, no warning of any kind is emitted.
5. The scheduler's `run_once` / `start` log output surface includes the
   fallback warning in structured form so log aggregators can alert on it.
6. All three test layers pass.

---

## TDD Approach — Red → Green → Refactor

### Step 1 — Write failing tests first

#### Unit Tests `tests/unit/test_tracker.py` (extend existing file)

```
POSITIVE
test_auto_strategy_with_no_token_logs_warning
    - caplog at WARNING; AIProductTracker(strategy="auto").get_products()
    - (Scraper will raise ScraperError because no real network)
    - Assert any caplog.record has "api_token" in the message
    - Assert record.levelname == "WARNING"

test_auto_strategy_with_no_token_emits_runtime_warning
    - with pytest.warns(RuntimeWarning, match="api_token"):
          AIProductTracker(strategy="auto").get_products()

test_api_strategy_with_no_token_logs_warning
    - caplog at WARNING; AIProductTracker(strategy="api").get_products()
    - Assert caplog contains a WARNING with "api_token" or "Missing api_token"

test_auto_strategy_with_valid_token_no_warning_emitted
    - Mock API to return success; AIProductTracker(strategy="auto",
      api_token="valid-token").get_products()
    - Assert no WARNING in caplog AND no RuntimeWarning via recwarn

test_scraper_strategy_no_warning_emitted
    - AIProductTracker(strategy="scraper") — no token needed
    - Monkeypatch scraper to return products
    - Assert no WARNING in caplog related to api_token

test_auto_strategy_blank_whitespace_token_logs_warning
    - AIProductTracker(strategy="auto", api_token="   ").get_products()
    - Assert WARNING emitted (blank token is effectively missing)

NEGATIVE
test_warning_message_contains_actionable_guidance
    - Capture the RuntimeWarning message text
    - Assert it contains "api_token" AND at least one of:
      "PRODUCTHUNT_TOKEN", "set", "configure", "missing", "strategy"
    - Prevents unhelpful generic messages like "Warning: fallback"

test_warning_does_not_fire_twice_in_one_get_products_call
    - Use recwarn; call get_products() once
    - Assert len([w for w in recwarn if issubclass(w.category, RuntimeWarning)]) == 1
    - Prevents warning spam in high-frequency scheduler loops

test_auto_strategy_scraper_failure_after_token_missing_still_returns_failure_result
    - No token; scraper raises ScraperError; assert r.error is not None
      (warning fires but result still faithfully reports failure)
```

#### Integration Tests `tests/integration/test_tracker_integration.py` (extend)

```
POSITIVE
test_scheduler_run_propagates_warning_to_log_stream
    - Create a SchedulerConfig(strategy="auto", api_token=None)
    - Call run_once() with a mock tracker that records log output
    - Assert "api_token" appears in the captured logs at WARNING or above

test_auto_fallback_warning_does_not_prevent_scraper_success
    - No token; mock scraper returns [Product(name="X")];
      AIProductTracker(strategy="auto").get_products()
    - Assert r.error is None (warning issued but scraper succeeds)
    - Assert WARNING was logged

NEGATIVE
test_empty_string_token_treated_same_as_none
    - AIProductTracker(strategy="auto", api_token="")
    - Assert RuntimeWarning emitted (consistent behaviour with None)

test_warning_respects_python_warnings_filter
    - import warnings; warnings.filterwarnings("error", category=RuntimeWarning)
    - AIProductTracker(strategy="auto").get_products()  in a try/except
    - Assert RuntimeWarning is raised (proves it uses warnings.warn not logging only)
    - warnings.resetwarnings() in teardown
```

#### E2E Tests `tests/e2e/test_e2e_negative.py` (extend)

```
POSITIVE
test_e2e_auto_no_token_warning_logged_before_scraper_called
    - caplog; mock scraper returns empty list; run auto strategy
    - Assert WARNING about api_token appears BEFORE any scraper log entries
      (ordering check — prove detection happens at API-path entry, not after)

test_e2e_auto_with_token_no_spurious_warnings
    - Mock API transport returns valid GraphQL response
    - Run auto strategy with api_token="valid"
    - Assert no RuntimeWarning and no "api_token" WARNING in caplog

NEGATIVE
test_e2e_missing_token_warning_is_distinct_from_network_failure_warning
    - No token + mock transport raises TimeoutException on API call
    - Capture ALL warnings
    - Assert one RuntimeWarning about missing token
    - Assert separate log about network failure
    - Ensures the two failure modes produce *distinct*, diagnosable messages
```

---

## Implementation Tasks (after tests are written and red)

### `tracker.py`

1. **Add logger and import**

   ```python
   import logging
   import warnings

   _log = logging.getLogger(__name__)

   _MISSING_TOKEN_MSG = (
       "AIProductTracker: api_token is missing or blank. "
       "The 'auto' strategy will fall back to the scraper, which is slower and "
       "less reliable. Set the PRODUCTHUNT_TOKEN environment variable or pass "
       "api_token= explicitly to silence this warning."
   )
   ```

2. **`_from_api()`** — emit warning at the top of the method:

   ```python
   def _from_api(self, *, search_term: str, limit: int) -> TrackerResult:
       if not self._api_token or not self._api_token.strip():
           _log.warning(_MISSING_TOKEN_MSG)
           warnings.warn(_MISSING_TOKEN_MSG, RuntimeWarning, stacklevel=4)
           return TrackerResult.failure(source="api", error="Missing api_token")
       ...
   ```

   _`stacklevel=4` walks the call stack back through `_from_api → get_products
→ caller`, placing the warning at the user's call site._

3. **Keep the existing `TrackerResult.failure(source="api", …)` return path
   unchanged** — only add the warn/log lines before it.

4. **`scheduler.py` — log the warning in `run_once()`** (if it exists; otherwise
   in the run loop):
   ```python
   if result.error and "api_token" in (result.error or "").lower():
       _log.warning(
           "Run %d: API token configuration error detected. "
           "Consider setting PRODUCTHUNT_TOKEN.", run_id
       )
   ```

---

## Definition of Done

- [ ] All 14 fallback-warning tests pass (existing + new).
- [ ] `pytest -W error::RuntimeWarning` passes across the full test suite (no
      _unexpected_ runtime warnings from our own code).
- [ ] WARNING appears in `caplog` whenever `api_token` is absent and `auto` or
      `api` strategy is used.
- [ ] `warnings.warn(…, RuntimeWarning)` fires exactly once per `get_products()`
      call — no double-warning.
- [ ] When a valid token is provided, zero warnings are emitted.

# Sprint 4 — Tracker Facade & E2E Tests

**Goal:** Build the orchestrator that ties API + Scraper together with auto-fallback,
and validate the entire pipeline end-to-end.

## TDD Cycle

### Red Phase — Write failing tests FIRST

```
tests/unit/test_tracker.py
    ✗ test_tracker_init_default_config
    ✗ test_tracker_init_custom_config
    ✗ test_get_products_api_strategy
    ✗ test_get_products_scraper_strategy

tests/integration/test_tracker_integration.py
    ✗ test_fallback_on_api_rate_limit
    ✗ test_fallback_on_api_auth_error
    ✗ test_auto_tries_api_first_on_success
    ✗ test_auto_falls_back_to_scraper_on_failure
    ✗ test_both_strategies_fail_raises_comprehensive_error

tests/e2e/test_e2e_positive.py
    ✗ test_e2e_api_happy_path_returns_products
    ✗ test_e2e_scraper_happy_path_returns_products
    ✗ test_e2e_auto_fallback_api_to_scraper

tests/e2e/test_e2e_negative.py
    ✗ test_e2e_no_network_both_fail
    ✗ test_e2e_invalid_token_triggers_fallback
    ✗ test_e2e_both_sources_return_empty_results
```

### Green Phase — Implement

- `AIProductTracker.__init__(api_token=None, strategy="auto")`
- `AIProductTracker.get_products() -> TrackerResult`
  - strategy="api" → API only
  - strategy="scraper" → Scraper only
  - strategy="auto" → API first, fallback to scraper
- Capture errors and return in `TrackerResult.error`

### Refactor Phase

- Add strategy pattern (pluggable data sources)
- Add caching layer stub
- Polish error messages

## Exit Criteria

```bash
$ poetry run pytest tests/ -v
~43 passed
```

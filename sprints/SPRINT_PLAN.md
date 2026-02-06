# ph_ai_tracker — Sprint Plan (TDD Approach)

> **Methodology:** Test-Driven Development (Red → Green → Refactor)
> **Testing Pyramid:** Unit → Integration → E2E (positive + negative cases)
> **Runtime:** PyPy 3 · **Packaging:** Poetry (src/ layout)

---

## Sprint 0 — Project Scaffolding & Tooling (Foundation)

| #   | Task                                                        | Acceptance Criteria                                              |
| --- | ----------------------------------------------------------- | ---------------------------------------------------------------- |
| 0.1 | Initialize Poetry project with `src/` layout                | `pyproject.toml` exists, `src/ph_ai_tracker/__init__.py` created |
| 0.2 | Pin interpreter to PyPy 3                                   | `poetry env use <pypy3-path>` succeeds                           |
| 0.3 | Add dev dependencies (pytest, pytest-cov, responses, vcrpy) | `poetry install` passes                                          |
| 0.4 | Add prod dependencies (httpx, beautifulsoup4, lxml)         | All imports resolve                                              |
| 0.5 | Configure `pyproject.toml` with full PEP 621 metadata       | `poetry check` passes                                            |
| 0.6 | Create `.gitignore`, `README.md`, `LICENSE`                 | Files present in repo root                                       |
| 0.7 | Create `conftest.py` with shared fixtures                   | Pytest discovers fixtures                                        |
| 0.8 | Verify `pytest` runs (0 tests collected, 0 errors)          | Exit code 0                                                      |

**Definition of Done:** `poetry install && poetry run pytest` exits cleanly.

---

## Sprint 1 — Domain Models & Data Contracts (Unit Tests)

| #   | Task                                                                              | Test Type | Tests                                                                 |
| --- | --------------------------------------------------------------------------------- | --------- | --------------------------------------------------------------------- |
| 1.1 | Define `Product` dataclass (name, tagline, description, votes_count, url, topics) | Unit ✅   | `test_product_creation_valid`, `test_product_creation_missing_fields` |
| 1.2 | Define `TrackerResult` dataclass (products, source, fetched_at, error)            | Unit ✅   | `test_tracker_result_success`, `test_tracker_result_with_error`       |
| 1.3 | Define custom exceptions: `APIError`, `ScraperError`, `RateLimitError`            | Unit ✅   | `test_exceptions_inherit_base`, `test_exception_messages`             |
| 1.4 | Add `Product.to_dict()` / `from_dict()` serialization                             | Unit ✅   | `test_product_roundtrip_serialization`, `test_from_dict_invalid_data` |

**TDD Cycle:** Write failing tests first → implement models → green bar → refactor.

---

## Sprint 2 — GraphQL API Client (Unit + Integration Tests)

| #   | Task                                                     | Test Type        | Tests                                                                                   |
| --- | -------------------------------------------------------- | ---------------- | --------------------------------------------------------------------------------------- |
| 2.1 | Create `ProductHuntAPI` class with `__init__(api_token)` | Unit ✅          | `test_client_init_with_token`, `test_client_init_missing_token_raises`                  |
| 2.2 | Implement `_build_query()` for GraphQL payload           | Unit ✅          | `test_build_query_contains_fields`, `test_build_query_with_topic_filter`                |
| 2.3 | Implement `fetch_ai_products()` with httpx               | Unit ✅ (mocked) | `test_fetch_returns_products`, `test_fetch_empty_response`, `test_fetch_malformed_json` |
| 2.4 | Implement rate-limit detection (HTTP 429 handling)       | Unit ✅ (mocked) | `test_rate_limit_raises_error`, `test_rate_limit_error_contains_retry_after`            |
| 2.5 | Implement auth failure detection (HTTP 401/403)          | Unit ✅ (mocked) | `test_auth_failure_raises_api_error`                                                    |
| 2.6 | Integration test against mocked HTTP (responses lib)     | Integration ✅   | `test_full_api_flow_mocked`, `test_api_network_timeout`                                 |

**TDD Cycle:** Mock all HTTP calls. No real network hits in CI.

---

## Sprint 3 — Web Scraper Fallback (Unit + Integration Tests)

| #   | Task                                          | Test Type        | Tests                                                                                  |
| --- | --------------------------------------------- | ---------------- | -------------------------------------------------------------------------------------- |
| 3.1 | Create `ProductHuntScraper` class             | Unit ✅          | `test_scraper_init`, `test_scraper_default_url`                                        |
| 3.2 | Implement `_parse_product_card(html_element)` | Unit ✅          | `test_parse_valid_card`, `test_parse_card_missing_votes`, `test_parse_card_empty_name` |
| 3.3 | Implement `scrape_ai_products()`              | Unit ✅ (mocked) | `test_scrape_returns_products`, `test_scrape_empty_page`, `test_scrape_malformed_html` |
| 3.4 | Implement HTTP error handling for scraper     | Unit ✅ (mocked) | `test_scrape_404_raises`, `test_scrape_500_raises`, `test_scrape_timeout`              |
| 3.5 | Integration test with fixture HTML file       | Integration ✅   | `test_scraper_parses_fixture_html`, `test_scraper_handles_changed_markup`              |

**TDD Cycle:** Use saved HTML fixtures, never hit the real site in tests.

---

## Sprint 4 — Tracker Facade / Orchestrator (Integration + E2E Tests)

| #   | Task                                             | Test Type      | Tests                                                                  |
| --- | ------------------------------------------------ | -------------- | ---------------------------------------------------------------------- |
| 4.1 | Create `AIProductTracker` facade class           | Unit ✅        | `test_tracker_init_default_config`, `test_tracker_init_custom_config`  |
| 4.2 | Implement `get_products(strategy="api")` routing | Unit ✅        | `test_get_products_api_strategy`, `test_get_products_scraper_strategy` |
| 4.3 | Implement auto-fallback (API fails → Scraper)    | Integration ✅ | `test_fallback_on_api_rate_limit`, `test_fallback_on_api_auth_error`   |
| 4.4 | Implement `get_products(strategy="auto")`        | Integration ✅ | `test_auto_tries_api_first`, `test_auto_falls_back_to_scraper`         |
| 4.5 | Negative: both strategies fail                   | Integration ✅ | `test_both_fail_raises_comprehensive_error`                            |
| 4.6 | E2E: Full pipeline mock (API → Product list)     | E2E ✅         | `test_e2e_api_happy_path`, `test_e2e_api_to_scraper_fallback`          |
| 4.7 | E2E: Negative full pipeline                      | E2E ✅         | `test_e2e_no_network_both_fail`, `test_e2e_invalid_token_fallback`     |

---

## Sprint 5 — Public API, Packaging & Distribution

| #   | Task                                           | Test Type | Tests                                                                |
| --- | ---------------------------------------------- | --------- | -------------------------------------------------------------------- |
| 5.1 | Define public `__init__.py` exports            | Unit ✅   | `test_public_api_exports_tracker`, `test_public_api_exports_product` |
| 5.2 | Add `py.typed` marker for type checkers        | Unit ✅   | `test_py_typed_exists`                                               |
| 5.3 | Validate `poetry build` produces wheel + sdist | E2E ✅    | `test_package_builds_successfully`                                   |
| 5.4 | Validate installable in fresh venv             | E2E ✅    | `test_package_installs_and_imports`                                  |
| 5.5 | Write usage example script                     | —         | Manual verification                                                  |
| 5.6 | Final `README.md` with badges, install, usage  | —         | Manual review                                                        |

---

## Sprint Velocity & Estimates

| Sprint    | Focus        | Estimated Effort | Tests Count    |
| --------- | ------------ | ---------------- | -------------- |
| 0         | Scaffolding  | 1 hour           | 0 (setup only) |
| 1         | Models       | 1 hour           | ~8 tests       |
| 2         | API Client   | 2 hours          | ~10 tests      |
| 3         | Scraper      | 2 hours          | ~10 tests      |
| 4         | Facade + E2E | 2 hours          | ~11 tests      |
| 5         | Packaging    | 1 hour           | ~4 tests       |
| **Total** |              | **~9 hours**     | **~43 tests**  |

---

## Test Organization

```
tests/
├── conftest.py                  # Shared fixtures (mock responses, HTML fixtures)
├── fixtures/
│   ├── api_response_success.json
│   ├── api_response_empty.json
│   ├── api_response_malformed.json
│   ├── scraper_page.html
│   └── scraper_page_empty.html
├── unit/
│   ├── test_models.py           # Sprint 1
│   ├── test_api_client.py       # Sprint 2
│   ├── test_scraper.py          # Sprint 3
│   └── test_tracker.py          # Sprint 4 (unit-level)
├── integration/
│   ├── test_api_integration.py  # Sprint 2
│   ├── test_scraper_integration.py  # Sprint 3
│   └── test_tracker_integration.py  # Sprint 4
└── e2e/
    ├── test_e2e_positive.py     # Sprint 4
    ├── test_e2e_negative.py     # Sprint 4
    └── test_packaging.py        # Sprint 5
```

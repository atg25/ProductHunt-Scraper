# Sprint 3 — Web Scraper Fallback

**Goal:** Implement the BeautifulSoup4 scraper as a fallback data source.

## TDD Cycle

### Red Phase — Write failing tests FIRST

```
tests/unit/test_scraper.py
    ✗ test_scraper_init_default_url
    ✗ test_scraper_init_custom_url
    ✗ test_parse_valid_product_card
    ✗ test_parse_card_missing_votes_defaults_zero
    ✗ test_parse_card_empty_name_skipped
    ✗ test_scrape_returns_products
    ✗ test_scrape_empty_page_returns_empty_list
    ✗ test_scrape_malformed_html_raises
    ✗ test_scrape_404_raises_scraper_error
    ✗ test_scrape_500_raises_scraper_error
    ✗ test_scrape_connection_timeout_raises

tests/integration/test_scraper_integration.py
    ✗ test_scraper_parses_fixture_html_full_page
    ✗ test_scraper_handles_changed_markup_gracefully
```

### Green Phase — Implement

- `ProductHuntScraper.__init__(base_url: str = "https://www.producthunt.com")`
- `ProductHuntScraper._parse_product_card(element) -> Product | None`
- `ProductHuntScraper.scrape_ai_products() -> list[Product]`
- Save realistic HTML fixture files under `tests/fixtures/`
- HTTP errors → `ScraperError`

### Refactor Phase

- Add user-agent rotation
- Add configurable CSS selectors for resilience
- Add logging

## Exit Criteria

```bash
$ poetry run pytest tests/unit/test_scraper.py tests/integration/test_scraper_integration.py -v
13 passed
```

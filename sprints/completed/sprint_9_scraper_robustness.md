# Sprint 9 — Scraper Robustness & Graceful DOM Degradation

## Knuth Concern Addressed

> "Web scraping is a notoriously brittle endeavor. A minor change in the
> typographic layout of the target website will shatter your parser. You must
> ensure that your ProductHuntScraper employs robust error handling … so that
> when (not if) they fail, the system degrades gracefully and logs the precise anomaly."
> — Issue #3

---

## Sprint Goal

Isolate every DOM interaction behind a thin extraction layer so that a layout
change produces a _logged warning_ and an empty-but-valid list — never an
unhandled exception. Each extraction stage must be individually unit-testable
with a minimal HTML fixture. Unknown DOM shapes are logged at `WARNING` level
with the HTML fragment that caused the surprise.

---

## Acceptance Criteria

1. `ProductHuntScraper.scrape_ai_products` **never raises** `ScraperError` due
   to a malformed or empty page; it returns `[]` and logs a `WARNING`.
2. A `ScraperError` is raised **only** for network-layer failures (timeout, HTTP
   4xx/5xx) — these remain the caller's problem.
3. `_extract_next_data_products` and `_extract_dom_products` each log a warning
   (via the module-level `logging.getLogger(__name__)`) when no products are
   found, including the first 200 chars of the HTML they received.
4. The `walk()` helper inside `_extract_next_data_products` catches
   `json.JSONDecodeError` gracefully (already partially done) and logs the
   malformed fragment before returning `[]`.
5. DOM path-depth guard uses a named constant `_MIN_PATH_DEPTH = 2` for
   readability.
6. All three test layers pass.

---

## TDD Approach — Red → Green → Refactor

### Fixtures needed (add to `tests/fixtures/`)

| Fixture file                       | Description                                                                          |
| ---------------------------------- | ------------------------------------------------------------------------------------ |
| `scraper_page_empty.html`          | Minimal HTML with no `__NEXT_DATA__` and no `/products/` links — already exists      |
| `scraper_page_dom.html`            | HTML with only anchor-based product links, no JSON script — already exists           |
| `scraper_next_data_malformed.html` | Page with `__NEXT_DATA__` whose JSON is truncated/invalid                            |
| `scraper_next_data_no_posts.html`  | Valid JSON in `__NEXT_DATA__` but no node matches the product heuristic              |
| `scraper_dom_nav_only.html`        | Page filled with `/products/` anchors that are navigation/category links (depth ≠ 2) |

### Step 1 — Write failing tests first

#### Unit Tests `tests/unit/test_scraper.py` (extend existing file)

```
POSITIVE
test_extract_next_data_returns_empty_on_missing_script_tag
    - Pass HTML with no <script id="__NEXT_DATA__">; assert result == []

test_extract_next_data_returns_empty_on_malformed_json
    - Pass fixture scraper_next_data_malformed.html; assert result == []
    - Assert a WARNING log was emitted containing "Failed to parse"

test_extract_next_data_returns_empty_on_no_matching_nodes
    - Pass fixture scraper_next_data_no_posts.html; assert result == []

test_extract_dom_products_ignores_nav_only_anchors
    - Pass fixture scraper_dom_nav_only.html; assert result == []

test_extract_dom_products_ignores_mailto_and_tel_links
    - Construct HTML with href="mailto:..." containing "/products/"; assert == []

test_extract_dom_products_dedupes_by_name_and_url
    - Build HTML with two anchors pointing to the same /products/slug; assert len == 1

test_enrich_from_product_page_returns_original_on_http_error
    - Mock transport returns 404; assert returned product == original (no mutation)

test_enrich_from_product_page_returns_original_on_network_exception
    - Mock transport raises httpx.TimeoutException; assert returned product == original

test_scrape_ai_products_returns_empty_list_on_empty_page
    - Provide scraper_page_empty.html; assert result == [] and no exception raised

test_scrape_ai_products_falls_through_to_dom_when_no_next_data
    - Provide scraper_page_dom.html (has anchors, no JSON blob);
      assert result is a list (may be empty)

NEGATIVE
test_scrape_ai_products_raises_scraper_error_on_timeout
    - Mock transport raises httpx.TimeoutException; assert raises ScraperError

test_scrape_ai_products_raises_scraper_error_on_http_500
    - Mock transport returns 500; assert raises ScraperError("Scraper HTTP error")

test_scrape_ai_products_raises_scraper_error_on_connection_error
    - Mock transport raises httpx.ConnectError; assert raises ScraperError

test_extract_next_data_logs_warning_on_empty_result
    - Use caplog at WARNING level; assert at least one warning logged when page
      has script tag but zero product nodes

test_extract_dom_products_logs_warning_when_nothing_found
    - Use caplog at WARNING level; assert warning logged when page has anchors
      but none pass path-depth guard
```

#### Integration Tests `tests/integration/test_scraper_integration.py` (extend)

```
POSITIVE
test_scraper_gracefully_handles_layout_change
    - Provide HTML that looks like PH but has been restructured (no known CSS
      classes, different JSON shape); assert scrape_ai_products returns [] without
      raising

test_scraper_dom_fallback_activates_when_next_data_absent
    - Provide HTML containing only classic anchor-based product links; assert
      scrape_ai_products produces ≥ 0 products without raising

test_scraper_enrichment_skipped_when_enrich_products_is_false
    - ScraperConfig(enrich_products=False); verify _enrich_from_product_page is
      never called (mock it to raise; assert no exception)

NEGATIVE
test_scraper_partial_json_in_next_data_does_not_propagate_exception
    - Feed truncated JSON string (`{"props": {`); assert returns [] not raises

test_scraper_empty_page_does_not_propagate_exception
    - Feed completely empty string ""; assert returns [] not raises
```

#### E2E Tests `tests/e2e/test_e2e_negative.py` (extend existing file)

```
POSITIVE
test_e2e_scraper_empty_page_returns_empty_result
    - Set up mock transport returning 200 with empty HTML; invoke tracker
      with strategy="scraper"; assert r.error is None and r.products == ()

test_e2e_scraper_layout_change_returns_empty_not_exception
    - Mock transport returns 200 with scrambled HTML (no product data);
      assert r.error is None, r.products == ()

NEGATIVE
test_e2e_scraper_timeout_produces_failure_result
    - Mock transport raises TimeoutException; assert r.error is not None
      and "timed out" in r.error.lower()

test_e2e_scraper_500_produces_failure_result
    - Mock returns 500; assert r.error is not None and "500" in r.error

test_e2e_auto_strategy_degrades_to_scraper_on_api_error
    - No API token set; mock scraper transport returns 200 with empty HTML;
      assert overall r.error is None and r.source == "scraper"
      (auto degraded cleanly to scraper which returned [])
      NOTE: this verifies graceful silent degradation at the data level,
      while Sprint 11 adds the loud warning at the *configuration* level.
```

---

## Implementation Tasks (after tests are written and red)

### `scraper.py`

1. **Add module-level logger**

   ```python
   import logging
   _log = logging.getLogger(__name__)
   ```

2. **Add constant**

   ```python
   _MIN_PATH_DEPTH = 2
   ```

3. **`_extract_next_data_products`** — add guard:

   ```python
   if not found:
       _log.warning(
           "No products found in __NEXT_DATA__. "
           "Possible layout change. HTML snippet: %.200s", html
       )
   ```

4. **`_extract_next_data_products`** — wrap `json.JSONDecodeError`:

   ```python
   except json.JSONDecodeError as exc:
       _log.warning("Failed to parse __NEXT_DATA__ JSON: %s. Snippet: %.200s", exc, html)
       return []
   # NOTE: drop the re-raise — return [] keeps the contract "never raises on bad data"
   ```

5. **`_extract_dom_products`** — add warning when `products` is empty after the loop:

   ```python
   if not products:
       _log.warning(
           "DOM fallback found no product anchors. "
           "Possible layout change. HTML snippet: %.200s", html
       )
   ```

6. **`_extract_dom_products`** — replace magic `2` with `_MIN_PATH_DEPTH`.

7. **`_enrich_from_product_page`** — add explicit logging for network errors:

   ```python
   except httpx.HTTPError as exc:
       _log.warning("Enrichment request failed for %s: %s", product.url, exc)
       return product
   ```

8. **`scrape_ai_products`** — wrap the extraction block so that an unexpected
   exception during extraction returns `[]` + warning rather than propagating:
   ```python
   try:
       products = self._extract_next_data_products(html)
       if not products:
           products = self._extract_dom_products(html)
   except Exception as exc:   # pylint: disable=broad-except
       _log.warning("Unexpected extraction failure: %s", exc, exc_info=True)
       products = []
   ```

---

## Definition of Done

- [ ] All 22 scraper tests pass (existing + new).
- [ ] `scrape_ai_products` returns `[]` for every malformed / empty fixture; no
      unhandled exception.
- [ ] `ScraperError` is raised only on network-layer failures (verified by
      negative tests).
- [ ] WARNING logs are emitted and verifiable via `caplog` fixture in pytest.
- [ ] `_MIN_PATH_DEPTH` constant is used in `_extract_dom_products`.

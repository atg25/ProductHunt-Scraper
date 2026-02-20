# Sprint 13 — Scraper: Decompose the God Object

## Uncle Bob Concern Addressed

> "Your `ProductHuntScraper` class knows entirely too much. It knows how to
> instantiate an HTTP client, it knows how to parse Next.js JSON blobs via
> recursive walking, it knows how to traverse DOM anchor tags for fallbacks,
> and it knows how to fetch and parse OpenGraph meta tags for enrichment.
> Extract `NextDataExtractor`, `DOMFallbackExtractor`, and `ProductEnricher`.
> `scrape_ai_products` (53 lines) should act only as a high-level coordinator."
> — Issue #2

---

## Sprint Goal

Break `ProductHuntScraper` into a cluster of small, focused collaborators.
Each new class has exactly one reason to change. `scrape_ai_products` becomes
a ≤ 20 line orchestrator that delegates every substantive step by name.

---

## Acceptance Criteria

1. **`NextDataExtractor`** — standalone class, no dependency on `httpx`.
   Single public method: `extract(html: str) -> list[Product]`.
   Contains the recursive `_walk` helper as a private static method.
   `_extract_next_data_products` on `ProductHuntScraper` becomes a one-line
   delegation: `return self._next_extractor.extract(html)`.

2. **`DOMFallbackExtractor`** — standalone class, no dependency on `httpx`.
   Single public method: `extract(html: str) -> list[Product]`.
   Requires the `base_url` string at construction so it can canonicalise
   relative anchors.
   `_extract_dom_products` on `ProductHuntScraper` becomes a one-line
   delegation.

3. **`ProductEnricher`** — class that owns an `httpx.Client` (or accepts one).
   Single public method: `enrich(product: Product) -> Product`.
   All OpenGraph parsing, `votesCount` regex, and `_soup` helper live here.
   `_enrich_from_product_page` on `ProductHuntScraper` becomes a one-line
   delegation.

4. `scrape_ai_products` body **≤ 20 lines** after refactoring.
5. `_extract_next_data_products.walk` (36 lines) is no longer a function
   defined inside another function — it lives as `NextDataExtractor._walk`.
6. All existing unit, integration, and e2e tests continue to pass.
7. All new tests listed below pass.

---

## New Entities to Create

```
src/ph_ai_tracker/scraper.py
  ├── NextDataExtractor   (class)  — extract(html) -> list[Product]
  │     └── _walk(obj, found)      — recursive JSON traversal (private static)
  ├── DOMFallbackExtractor (class) — extract(html) -> list[Product]
  ├── ProductEnricher      (class) — enrich(product) -> Product
  │     └── _meta_content(soup, **attrs) -> str | None  (private static)
  └── ProductHuntScraper   (thin coordinator)
        ├── scrape_ai_products  ≤ 20 lines
        ├── _extract_next_data_products  — delegates to NextDataExtractor
        ├── _extract_dom_products        — delegates to DOMFallbackExtractor
        └── _enrich_from_product_page    — delegates to ProductEnricher
```

The three extractor/enricher classes are **exported from the module** so tests
can import and exercise them independently without going through the scraper.

---

## TDD Approach — Red → Green → Refactor

### Step 1 — Write failing tests first

#### Unit Tests — `tests/unit/test_scraper.py` (extend existing file)

```
──────────────────────────────────────────────────────
NextDataExtractor (direct, no HTTP)
──────────────────────────────────────────────────────
POSITIVE
test_next_data_extractor_returns_products_from_valid_html
    - Pass scraper_page.html fixture (existing)
    - from ph_ai_tracker.scraper import NextDataExtractor
    - extractor = NextDataExtractor()
    - result = extractor.extract(html)
    - assert len(result) >= 1

test_next_data_extractor_deduplicates_by_name_url
    - Construct HTML with __NEXT_DATA__ containing two identical product nodes
    - assert len(extractor.extract(html)) == 1

test_next_data_extractor_returns_empty_on_missing_script
    - Pass plain HTML with no <script id="__NEXT_DATA__">
    - assert extractor.extract(html) == []

test_next_data_extractor_returns_empty_on_malformed_json
    - Use scraper_next_data_malformed.html fixture
    - assert extractor.extract(html) == []  (no exception raised)

test_next_data_extractor_returns_empty_when_no_posts_match_heuristic
    - Use scraper_next_data_no_posts.html fixture
    - assert extractor.extract(html) == []

NEGATIVE
test_next_data_extractor_does_not_import_httpx
    - import inspect, ph_ai_tracker.scraper as m
    - assert "httpx" not in [name for name, _ in inspect.getmembers(
          sys.modules["ph_ai_tracker.scraper.NextDataExtractor"].__module__
      ) if isinstance(_, types.ModuleType)]
    # Simpler: ensure NextDataExtractor.__module__ source has no httpx client init

test_next_data_extractor_logs_warning_on_malformed_json
    - Use caplog fixture; parse scraper_next_data_malformed.html
    - assert any("Failed to parse" in r.message for r in caplog.records)

test_next_data_extractor_logs_warning_when_no_products_found
    - Use scraper_next_data_no_posts.html; check caplog for WARNING

──────────────────────────────────────────────────────
DOMFallbackExtractor (direct, no HTTP)
──────────────────────────────────────────────────────
POSITIVE
test_dom_extractor_returns_products_from_anchor_html
    - Use scraper_page_dom.html fixture
    - from ph_ai_tracker.scraper import DOMFallbackExtractor
    - extractor = DOMFallbackExtractor(base_url="https://www.producthunt.com")
    - assert len(extractor.extract(html)) >= 1

test_dom_extractor_canonicalises_relative_urls
    - HTML with <a href="/products/foo">Foo</a>
    - result[0].url == "https://www.producthunt.com/products/foo"

NEGATIVE
test_dom_extractor_rejects_deep_paths
    - Use scraper_dom_nav_only.html (all anchors are deep navigation paths)
    - assert extractor.extract(html) == []

test_dom_extractor_logs_warning_when_no_products_found
    - Use scraper_page_empty.html; check caplog for WARNING

──────────────────────────────────────────────────────
ProductEnricher (mock HTTP client)
──────────────────────────────────────────────────────
POSITIVE
test_enricher_fills_description_from_og_meta
    - Mock transport returns HTML with <meta property="og:description" content="Great AI tool">
    - product = Product(name="Foo", url="https://ph.com/products/foo")
    - enriched = ProductEnricher(transport=mock).enrich(product)
    - assert enriched.description == "Great AI tool"

test_enricher_fills_votes_from_embedded_json
    - Mock transport returns HTML with "votesCount":42 in a <script> tag
    - assert enriched.votes_count == 42

test_enricher_returns_original_on_http_error
    - Mock transport raises httpx.ConnectError
    - enriched = ProductEnricher(transport=mock).enrich(product)
    - assert enriched is product  (unchanged reference)

NEGATIVE
test_enricher_returns_original_when_url_is_none
    - product = Product(name="NoURL")
    - assert ProductEnricher().enrich(product) is product

test_enricher_returns_original_on_4xx_response
    - Mock transport returns HTTP 404
    - assert enriched.description is None  (unchanged)

──────────────────────────────────────────────────────
scrape_ai_products (thin orchestrator)
──────────────────────────────────────────────────────
POSITIVE
test_scrape_ai_products_delegates_to_next_extractor_first
    - Patch NextDataExtractor.extract to return [Product(name="MockProduct")]
    - Call scraper.scrape_ai_products()
    - assert result[0].name == "MockProduct"
    - assert DOMFallbackExtractor.extract was NOT called

test_scrape_ai_products_falls_back_to_dom_when_next_data_empty
    - Patch NextDataExtractor.extract to return []
    - Patch DOMFallbackExtractor.extract to return [Product(name="DOMProduct")]
    - assert result[0].name == "DOMProduct"
```

#### Integration Tests — `tests/integration/test_scraper_integration.py` (extend)

```
POSITIVE
test_next_data_extractor_importable_at_package_level
    - from ph_ai_tracker.scraper import NextDataExtractor, DOMFallbackExtractor, ProductEnricher
    - assert all three are classes

test_scraper_full_pipeline_with_real_html_fixture
    - Build a ProductHuntScraper with a mock transport that returns scraper_page.html
    - result = scraper.scrape_ai_products(search_term="AI", limit=5)
    - assert isinstance(result, list)
    - assert all(isinstance(p, Product) for p in result)

NEGATIVE
test_scrape_ai_products_body_is_under_20_lines
    - Use inspect.getsource(ProductHuntScraper.scrape_ai_products)
    - Count non-blank, non-comment source lines; assert <= 20
```

#### E2E Tests — `tests/e2e/test_e2e_negative.py` (extend)

```
NEGATIVE
test_e2e_scraper_gracefully_handles_empty_page
    - Build Tracker with scraper strategy and mock transport returning scraper_page_empty.html
    - result = tracker.get_products(search_term="AI", limit=5)
    - assert result.products == []
    - assert result.error is None  (empty page is NOT an error)

test_e2e_scraper_gracefully_handles_malformed_next_data
    - Mock transport returns scraper_next_data_malformed.html
    - result = tracker.get_products(search_term="AI", limit=5)
    - assert isinstance(result.products, list)  (no exception bubbles up)
```

---

## Implementation Notes

### Construction — dependency injection

`ProductHuntScraper.__init__` should construct its three collaborators and
expose them as instance attributes so tests can swap them:

```python
class ProductHuntScraper:
    def __init__(self, *, config=None, transport=None):
        self._config   = config or ScraperConfig()
        self._client   = httpx.Client(...)
        self._next_ext = NextDataExtractor()
        self._dom_ext  = DOMFallbackExtractor(base_url=self._config.base_url)
        self._enricher = ProductEnricher(client=self._client)
```

### `scrape_ai_products` target shape

```python
def scrape_ai_products(self, *, search_term="AI", limit=20) -> list[Product]:
    html     = self._fetch_html()                   # raises ScraperError on network failure
    products = self._next_ext.extract(html)
    if not products:
        products = self._dom_ext.extract(html)
    products = self._apply_filter(products, search_term, limit)
    products = self._maybe_enrich(products)
    return self._sort_by_votes(products)
```

Each delegated method is a ≤ 10-line private method on `ProductHuntScraper`.

### `NextDataExtractor._walk` — no more closures

Move the recursive `walk()` function that currently lives inside
`_extract_next_data_products` to a `@staticmethod _walk(obj, found)` on
`NextDataExtractor`. This makes it directly unit-testable and eliminates the
closure over `found`.

---

## Definition of Done

- [ ] `NextDataExtractor`, `DOMFallbackExtractor`, `ProductEnricher` exist in `scraper.py` and are importable
- [ ] `scrape_ai_products` is ≤ 20 non-blank lines
- [ ] `walk()` is no longer a closure — it is `NextDataExtractor._walk`
- [ ] All NEW tests listed above pass (Red → Green)
- [ ] All EXISTING tests still pass (no regression)
- [ ] `make bundle` regenerates cleanly
- [ ] Function-size inventory shows `scrape_ai_products` ≤ 20

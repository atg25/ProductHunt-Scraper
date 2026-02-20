# Sprint 40 — Delete Dead Shims from `ProductHuntScraper`

**Status:** Active  
**Source:** Uncle Bob Letter 9, Issue #1 — Test-Induced Design Damage  
**Depends on:** Sprint 13 (introduced the extractor classes that replaced this code)

---

## Problem Statement

`ProductHuntScraper` carries three methods that do nothing except forward a call
one-for-one to an underlying extractor object:

```python
def _extract_next_data_products(self, html: str) -> list[Product]:
    """Delegate to :class:`NextDataExtractor` to parse the ``__NEXT_DATA__`` JSON."""
    return self._next_data.extract(html)

def _extract_dom_products(self, html: str) -> list[Product]:
    """Delegate to :class:`DOMFallbackExtractor` to scrape anchor tags."""
    return self._dom_fallback.extract(html)

def _enrich_from_product_page(self, product: Product) -> Product:
    """Delegate to :class:`ProductEnricher` to fill missing fields from the product page."""
    return self._enricher.enrich(product)
```

`_extract_products` (the real production caller) bypasses all three shims completely
and calls the extractors directly:

```python
def _extract_products(self, html: str) -> list[Product]:
    products = self._next_data.extract(html)          # ← direct
    if not products:
        products = self._dom_fallback.extract(html)   # ← direct
    ...
```

`_maybe_enrich` calls `self._enricher.enrich(p)` directly as well.

These three methods exist **only** because eight tests in `tests/unit/test_scraper.py`
(lines 65–141) still call them via `s._extract_next_data_products(…)`,
`s._extract_dom_products(…)`, and `s._enrich_from_product_page(…)`. The shims are
dead weight kept alive purely to satisfy stale tests — the textbook definition of
**Test-Induced Design Damage**.

---

## Acceptance Criteria

1. `ProductHuntScraper` contains **zero** occurrences of `_extract_next_data_products`,
   `_extract_dom_products`, and `_enrich_from_product_page`.
2. No test in the suite calls any of those three names.  
   `grep -rn "_extract_next_data_products\|_extract_dom_products\|_enrich_from_product_page" tests/` → 0 matches.
3. Every behaviour that was previously exercised through the shims is now exercised by
   calling `NextDataExtractor`, `DOMFallbackExtractor`, or `ProductEnricher` directly.
4. Test count after the sprint is `(previous count) - 8 shim tests + N new direct tests`,
   where N ≥ 5 (the five cases not yet covered by any existing direct extractor test).
5. `pytest` exits 0 with no regressions.
6. `make bundle` reports all functions ≤ 20 lines.

---

## Exact Changes Required

### A — `src/ph_ai_tracker/scraper.py`

Delete the following three method definitions from `ProductHuntScraper` entirely
(the nine lines from the first `def` to the last `return`):

```python
def _extract_next_data_products(self, html: str) -> list[Product]:
    """Delegate to :class:`NextDataExtractor` to parse the ``__NEXT_DATA__`` JSON."""
    return self._next_data.extract(html)

def _extract_dom_products(self, html: str) -> list[Product]:
    """Delegate to :class:`DOMFallbackExtractor` to scrape anchor tags."""
    return self._dom_fallback.extract(html)

def _enrich_from_product_page(self, product: Product) -> Product:
    """Delegate to :class:`ProductEnricher` to fill missing fields from the product page."""
    return self._enricher.enrich(product)
```

Nothing else in `scraper.py` needs to change; `_extract_products` and `_maybe_enrich`
already call the extractors directly.

### B — `tests/unit/test_scraper.py` — Delete all eight shim-calling tests

Delete the following test functions **in their entirety** (including any blank lines
that separate them from adjacent tests):

| Function name                                                | Current lines (approx) | Calls shim                         |
| ------------------------------------------------------------ | ---------------------- | ---------------------------------- |
| `test_extract_next_data_returns_empty_on_missing_script_tag` | 65–68                  | `s._extract_next_data_products(…)` |
| `test_extract_next_data_returns_empty_on_malformed_json`     | 71–79                  | `s._extract_next_data_products(…)` |
| `test_extract_next_data_returns_empty_on_no_matching_nodes`  | 83–88                  | `s._extract_next_data_products(…)` |
| `test_extract_dom_products_ignores_nav_only_anchors`         | 91–96                  | `s._extract_dom_products(…)`       |
| `test_extract_dom_products_ignores_mailto_links`             | 99–103                 | `s._extract_dom_products(…)`       |
| `test_extract_dom_products_dedupes_by_name_and_url`          | 106–115                | `s._extract_dom_products(…)`       |
| `test_enrich_returns_original_on_http_404`                   | 118–128                | `s._enrich_from_product_page(…)`   |
| `test_enrich_returns_original_on_timeout`                    | 131–141                | `s._enrich_from_product_page(…)`   |

### C — `tests/unit/test_scraper.py` — Add direct extractor tests

After the existing block of direct extractor tests (currently ending near line 330),
add the following five new functions. These cover the five behavioural edges that the
deleted shim tests owned and that are **not** already covered by any existing direct
extractor test.

Three of the eight deleted shim tests are already redundant — their behaviour is fully
covered by existing direct tests added earlier (Sprint 13 follow-up):

| Deleted shim test                                           | Already covered by                             |
| ----------------------------------------------------------- | ---------------------------------------------- |
| `test_extract_next_data_returns_empty_on_malformed_json`    | `test_next_data_extractor_empty_on_malformed`  |
| `test_extract_next_data_returns_empty_on_no_matching_nodes` | `test_next_data_extractor_empty_on_no_posts`   |
| `test_extract_dom_products_ignores_nav_only_anchors`        | `test_dom_fallback_extractor_rejects_nav_only` |

The five remaining edges need new tests:

**New test 1 — `NextDataExtractor` returns empty on missing `<script>` tag:**

```python
def test_next_data_extractor_empty_on_missing_script_tag() -> None:
    from ph_ai_tracker.scraper import NextDataExtractor

    assert NextDataExtractor().extract("<html><body></body></html>") == []
```

**New test 2 — `DOMFallbackExtractor` ignores `mailto:` links:**

```python
def test_dom_fallback_extractor_ignores_mailto_links() -> None:
    from ph_ai_tracker.scraper import DOMFallbackExtractor

    html = '<html><body><a href="mailto:hello@example.com/products/fake">Product</a></body></html>'
    assert DOMFallbackExtractor("https://www.producthunt.com").extract(html) == []
```

**New test 3 — `DOMFallbackExtractor` deduplicates by name and URL:**

```python
def test_dom_fallback_extractor_dedupes_by_name_and_url() -> None:
    from ph_ai_tracker.scraper import DOMFallbackExtractor

    html = """
    <html><body>
      <a href="/products/alphaai">AlphaAI</a>
      <a href="/products/alphaai">AlphaAI</a>
    </body></html>
    """
    result = DOMFallbackExtractor("https://www.producthunt.com").extract(html)
    assert len(result) == 1
```

**New test 4 — `ProductEnricher` returns original product unchanged on HTTP 404:**

```python
def test_product_enricher_returns_original_on_http_404() -> None:
    import httpx
    from ph_ai_tracker.scraper import ProductEnricher
    from ph_ai_tracker.models import Product

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    enricher = ProductEnricher(client=client)
    try:
        p = Product(name="X", url="https://www.producthunt.com/products/x")
        assert enricher.enrich(p) == p
    finally:
        enricher.close()
```

**New test 5 — `ProductEnricher` returns original product unchanged on timeout:**

```python
def test_product_enricher_returns_original_on_timeout() -> None:
    import httpx
    from ph_ai_tracker.scraper import ProductEnricher
    from ph_ai_tracker.models import Product

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    enricher = ProductEnricher(client=client)
    try:
        p = Product(name="X", url="https://www.producthunt.com/products/x")
        assert enricher.enrich(p) == p
    finally:
        enricher.close()
```

---

## Verification

```bash
# No shim names survive anywhere in the codebase
grep -rn "_extract_next_data_products\|_extract_dom_products\|_enrich_from_product_page" \
    src/ tests/

# Full test suite passes
.venv/bin/python -m pytest --tb=short -q

# Bundle still clean
make bundle
```

Expected: all three grep commands return zero lines; pytest exits 0; bundle reports
all functions ≤ 20 lines.

---

## Definition of Done

- [ ] Three shim methods deleted from `ProductHuntScraper`
- [ ] Eight shim-calling test functions deleted from `test_scraper.py`
- [ ] Five new direct-extractor test functions added to `test_scraper.py`
- [ ] `grep` shim search → 0 matches in `src/` and `tests/`
- [ ] `pytest` exits 0, no regressions
- [ ] `make bundle` all functions ≤ 20 lines
- [ ] Sprint doc moved to `sprints/completed/`

import httpx
import pytest
from datetime import datetime, timedelta, timezone

from ph_ai_tracker.scraper import ProductHuntScraper, ScraperConfig
from ph_ai_tracker.exceptions import ScraperError


def test_scrape_parses_next_data(scraper_html: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    transport = httpx.MockTransport(handler)
    s = ProductHuntScraper(transport=transport)
    try:
        products = s.scrape_ai_products(search_term="AI", limit=10)
        assert len(products) == 1
        assert products[0].name == "AlphaAI"
        assert products[0].votes_count == 123
        assert products[0].posted_at is not None
    finally:
        s.close()


def test_scrape_filters_out_products_older_than_week() -> None:
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    html = f"""
    <html><body>
      <script id="__NEXT_DATA__" type="application/json">{{
        "props": {{"pageProps": {{"seed": {{"posts": [
          {{"name": "OldAI", "tagline": "old", "createdAt": "{old}", "votesCount": 200, "url": "https://www.producthunt.com/posts/oldai"}},
          {{"name": "RecentAI", "tagline": "recent", "createdAt": "{recent}", "votesCount": 100, "url": "https://www.producthunt.com/posts/recentai"}}
        ]}}}}}}
      }}</script>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    s = ProductHuntScraper(transport=httpx.MockTransport(handler))
    try:
        products = s.scrape_ai_products(search_term="AI", limit=10)
        assert [product.name for product in products] == ["RecentAI"]
    finally:
        s.close()


def test_scrape_http_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oops")

    transport = httpx.MockTransport(handler)
    s = ProductHuntScraper(transport=transport)
    try:
        with pytest.raises(ScraperError):
            s.scrape_ai_products(limit=1)
    finally:
        s.close()


def test_scrape_enriches_description_from_product_page() -> None:
    topic_html = """
    <html><body>
      <a href=\"/products/alphaai\">AlphaAI</a>
    </body></html>
    """
    product_html = """
    <html><head>
      <meta name=\"description\" content=\"AlphaAI is an AI copilot.\" />
    </head><body></body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text=topic_html)
        if request.url.path == "/products/alphaai":
            return httpx.Response(200, text=product_html)
        return httpx.Response(404, text="no")

    transport = httpx.MockTransport(handler)
    s = ProductHuntScraper(transport=transport)
    try:
        products = s.scrape_ai_products(search_term="AI", limit=5)
        assert products
        assert products[0].description == "AlphaAI is an AI copilot."
    finally:
        s.close()


def test_scrape_ai_products_returns_empty_on_empty_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body></body></html>")

    s = ProductHuntScraper(transport=httpx.MockTransport(handler))
    try:
        result = s.scrape_ai_products(limit=5)
        assert result == []
    finally:
        s.close()


def test_scrape_ai_products_raises_scraper_error_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    s = ProductHuntScraper(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ScraperError, match="timed out"):
            s.scrape_ai_products(limit=1)
    finally:
        s.close()


def test_scrape_ai_products_raises_scraper_error_on_http_500() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    s = ProductHuntScraper(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ScraperError, match="500"):
            s.scrape_ai_products(limit=1)
    finally:
        s.close()


def test_extract_next_data_logs_warning_on_empty_result(
    scraper_next_data_no_posts_html: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging
    from ph_ai_tracker.scraper import NextDataExtractor

    with caplog.at_level(logging.WARNING, logger="ph_ai_tracker.scraper"):
        NextDataExtractor().extract(scraper_next_data_no_posts_html)
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_scrape_ai_products_enrichment_skipped_when_disabled() -> None:
    """ScraperConfig(enrich_products=False) must never perform product-page enrichment."""
    dom_html = """
    <html><body>
      <a href="/products/alphaai">AlphaAI</a>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text=dom_html)
        # Any product page hit means enrichment ran — fail immediately.
        raise AssertionError("Product-page enrichment should not have been called")

    s = ProductHuntScraper(
        config=ScraperConfig(enrich_products=False),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = s.scrape_ai_products(limit=5)
        # Result may be empty or have products; no exception means enrichment didn't run.
    finally:
        s.close()


def test_next_data_extractor_returns_products(scraper_html: str) -> None:
    from ph_ai_tracker.scraper import NextDataExtractor

    products = NextDataExtractor().extract(scraper_html)
    assert len(products) == 1
    assert products[0].name == "AlphaAI"
    assert products[0].votes_count == 123


def test_next_data_extractor_empty_on_malformed(scraper_next_data_malformed_html: str) -> None:
    from ph_ai_tracker.scraper import NextDataExtractor

    assert NextDataExtractor().extract(scraper_next_data_malformed_html) == []


def test_next_data_extractor_empty_on_no_posts(scraper_next_data_no_posts_html: str) -> None:
    from ph_ai_tracker.scraper import NextDataExtractor

    assert NextDataExtractor().extract(scraper_next_data_no_posts_html) == []


def test_next_data_extractor_empty_on_missing_script_tag() -> None:
    from ph_ai_tracker.scraper import NextDataExtractor

    assert NextDataExtractor().extract("<html><body></body></html>") == []


def test_dom_fallback_extractor_returns_products(scraper_dom_html: str) -> None:
    from ph_ai_tracker.scraper import DOMFallbackExtractor

    products = DOMFallbackExtractor("https://www.producthunt.com").extract(scraper_dom_html)
    assert len(products) == 2
    names = {p.name for p in products}
    assert "DomAI One" in names
    assert "DomAI Two" in names


def test_dom_fallback_extractor_rejects_nav_only(scraper_dom_nav_only_html: str) -> None:
    from ph_ai_tracker.scraper import DOMFallbackExtractor

    assert DOMFallbackExtractor("https://www.producthunt.com").extract(scraper_dom_nav_only_html) == []


def test_dom_fallback_extractor_ignores_mailto_links() -> None:
    from ph_ai_tracker.scraper import DOMFallbackExtractor

    html = '<html><body><a href="mailto:hello@example.com/products/fake">Product</a></body></html>'
    assert DOMFallbackExtractor("https://www.producthunt.com").extract(html) == []


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


def test_product_enricher_returns_unchanged_when_no_url() -> None:
    from ph_ai_tracker.scraper import ProductEnricher
    from ph_ai_tracker.models import Product

    enricher = ProductEnricher()
    try:
        product = Product(name="ToolX")
        assert enricher.enrich(product) is product
    finally:
        enricher.close()


def test_product_enricher_fills_description_from_og() -> None:
    from ph_ai_tracker.scraper import ProductEnricher
    from ph_ai_tracker.models import Product

    product_html = (
        '<html><head>'
        '<meta property="og:description" content="Great AI tool" />'
        '</head><body></body></html>'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=product_html)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    enricher = ProductEnricher(client=client)
    try:
        product = Product(name="ToolX", url="https://www.producthunt.com/posts/toolx")
        enriched = enricher.enrich(product)
        assert enriched.description == "Great AI tool"
    finally:
        enricher.close()


def test_product_enricher_returns_original_on_http_404() -> None:
    from ph_ai_tracker.scraper import ProductEnricher
    from ph_ai_tracker.models import Product

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    enricher = ProductEnricher(client=client)
    try:
        product = Product(name="X", url="https://www.producthunt.com/products/x")
        assert enricher.enrich(product) == product
    finally:
        enricher.close()


def test_product_enricher_returns_original_on_timeout() -> None:
    from ph_ai_tracker.scraper import ProductEnricher
    from ph_ai_tracker.models import Product

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    enricher = ProductEnricher(client=client)
    try:
        product = Product(name="X", url="https://www.producthunt.com/products/x")
        assert enricher.enrich(product) == product
    finally:
        enricher.close()


def test_extract_products_propagates_runtime_error() -> None:
    class BadExtractor:
        def extract(self, html: str) -> list:
            raise RuntimeError("bug")

    s = ProductHuntScraper(next_data_extractor=BadExtractor())
    try:
        with pytest.raises(RuntimeError, match="bug"):
            s._extract_products("<html></html>")
    finally:
        s.close()


def test_extract_products_propagates_type_error() -> None:
    class BadExtractor:
        def extract(self, html: str) -> list:
            raise TypeError("bug")

    s = ProductHuntScraper(next_data_extractor=BadExtractor())
    try:
        with pytest.raises(TypeError, match="bug"):
            s._extract_products("<html></html>")
    finally:
        s.close()


@pytest.mark.parametrize("exc", [ValueError("parse"), AttributeError("attr"), KeyError("k")])
def test_extract_products_recovers_from_known_parse_exceptions(exc: Exception) -> None:
    class BadExtractor:
        def __init__(self, err: Exception) -> None:
            self._err = err

        def extract(self, html: str) -> list:
            raise self._err

    s = ProductHuntScraper(next_data_extractor=BadExtractor(exc))
    try:
        assert s._extract_products("<html></html>") == []
    finally:
        s.close()

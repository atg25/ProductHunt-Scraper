import httpx
import pytest

from ph_ai_tracker.scraper import ProductHuntScraper
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
        if request.url.path.startswith("/topics/"):
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

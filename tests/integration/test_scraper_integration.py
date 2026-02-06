import httpx

from ph_ai_tracker.scraper import ProductHuntScraper


def test_scraper_parses_fixture_html_full_page(scraper_html: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    transport = httpx.MockTransport(handler)
    s = ProductHuntScraper(transport=transport)
    try:
        products = s.scrape_ai_products(search_term="AI", limit=10)
        assert len(products) == 1
        assert products[0].name == "AlphaAI"
    finally:
        s.close()


def test_scraper_dom_fallback_parses_posts(scraper_dom_html: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_dom_html)

    transport = httpx.MockTransport(handler)
    s = ProductHuntScraper(transport=transport)
    try:
        products = s.scrape_ai_products(search_term="", limit=10)
        assert products
        assert any(("/products/" in (p.url or "")) or ("/posts/" in (p.url or "")) for p in products)
    finally:
        s.close()

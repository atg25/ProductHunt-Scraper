import httpx
import pytest

from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.scraper import ProductHuntScraper


def test_e2e_scraper_happy_path(scraper_html: str) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    t = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
    )
    r = t.get_products(search_term="AI", limit=10)
    assert r.error is None
    assert r.products


def test_result_pretty_json(scraper_html: str) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    r = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
    ).get_products(limit=1)
    s = r.to_pretty_json()
    assert "products" in s
    assert "source" in s

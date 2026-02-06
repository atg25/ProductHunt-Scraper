import httpx
import pytest

from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.scraper import ProductHuntScraper


def test_e2e_scraper_happy_path(scraper_html: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    mock_transport = httpx.MockTransport(scraper_handler)

    original_scraper_init = ProductHuntScraper.__init__

    def patched_scraper_init(self, *, config=None, transport=None):
        return original_scraper_init(self, config=config, transport=mock_transport)

    monkeypatch.setattr(ProductHuntScraper, "__init__", patched_scraper_init)

    t = AIProductTracker(strategy="scraper")
    r = t.get_products(search_term="AI", limit=10)
    assert r.error is None
    assert r.products


def test_result_pretty_json(scraper_html: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    mock_transport = httpx.MockTransport(scraper_handler)
    original_scraper_init = ProductHuntScraper.__init__

    def patched_scraper_init(self, *, config=None, transport=None):
        return original_scraper_init(self, config=config, transport=mock_transport)

    monkeypatch.setattr(ProductHuntScraper, "__init__", patched_scraper_init)

    r = AIProductTracker(strategy="scraper").get_products(limit=1)
    s = r.to_pretty_json()
    assert "products" in s
    assert "source" in s

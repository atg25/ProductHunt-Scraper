import httpx
import pytest

from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.api_client import APIConfig
from ph_ai_tracker.scraper import ScraperConfig, ProductHuntScraper
from ph_ai_tracker.api_client import ProductHuntAPI


def test_auto_fallback_on_api_error(api_success_payload: dict, scraper_html: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force API to fail, scraper to succeed.

    def api_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "no"})

    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    api_transport = httpx.MockTransport(api_handler)
    scraper_transport = httpx.MockTransport(scraper_handler)

    # Monkeypatch constructors to inject transports.
    original_api_init = ProductHuntAPI.__init__
    original_scraper_init = ProductHuntScraper.__init__

    def patched_api_init(self, api_token: str, *, config=None, transport=None):
        return original_api_init(self, api_token, config=config, transport=api_transport)

    def patched_scraper_init(self, *, config=None, transport=None):
        return original_scraper_init(self, config=config, transport=scraper_transport)

    monkeypatch.setattr(ProductHuntAPI, "__init__", patched_api_init)
    monkeypatch.setattr(ProductHuntScraper, "__init__", patched_scraper_init)

    t = AIProductTracker(api_token="token", strategy="auto", api_config=APIConfig(), scraper_config=ScraperConfig())
    r = t.get_products(search_term="AI", limit=10)

    assert r.error is None
    assert r.source == "scraper"
    assert len(r.products) == 1

import httpx
import pytest

from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.scraper import ProductHuntScraper


def test_e2e_both_sources_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    def api_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"errors": []})

    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oops")

    api_transport = httpx.MockTransport(api_handler)
    scraper_transport = httpx.MockTransport(scraper_handler)

    original_api_init = ProductHuntAPI.__init__
    original_scraper_init = ProductHuntScraper.__init__

    def patched_api_init(self, api_token: str, *, config=None, transport=None):
        return original_api_init(self, api_token, config=config, transport=api_transport)

    def patched_scraper_init(self, *, config=None, transport=None):
        return original_scraper_init(self, config=config, transport=scraper_transport)

    monkeypatch.setattr(ProductHuntAPI, "__init__", patched_api_init)
    monkeypatch.setattr(ProductHuntScraper, "__init__", patched_scraper_init)

    t = AIProductTracker(api_token="token", strategy="auto")
    r = t.get_products(limit=5)
    assert r.error is not None
    assert r.source == "auto"

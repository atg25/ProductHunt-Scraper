import httpx

from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.protocols import FallbackProvider
from ph_ai_tracker.scraper import ProductHuntScraper


def test_auto_fallback_on_api_error(api_success_payload: dict, scraper_html: str) -> None:
    # Force API to fail, scraper to succeed.

    def api_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "no"})

    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    provider = FallbackProvider(
        api_provider=ProductHuntAPI("token", transport=httpx.MockTransport(api_handler)),
        scraper_provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
    )
    r = AIProductTracker(provider=provider).get_products(search_term="AI", limit=10)

    assert r.error is None
    assert r.source == "auto"
    assert len(r.products) == 1


def test_auto_fallback_warning_does_not_prevent_scraper_success(
    scraper_html: str,
    caplog,
) -> None:
    """When no token is set, a warning fires but the scraper still succeeds."""
    import logging

    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    scraper = ProductHuntScraper(transport=httpx.MockTransport(scraper_handler))
    with caplog.at_level(logging.WARNING, logger="ph_ai_tracker.protocols"):
        provider = FallbackProvider(api_provider=None, scraper_provider=scraper)
        r = AIProductTracker(provider=provider).get_products(search_term="AI", limit=5)

    assert r.error is None
    assert r.source == "auto"
    assert any("api_token" in rec.message for rec in caplog.records if rec.levelno >= logging.WARNING)


def test_empty_string_token_triggers_warning() -> None:
    """Empty-string token must behave identically to None."""
    import pytest as _pytest
    from ph_ai_tracker.exceptions import ScraperError

    class _FailingScraper:
        source_name = "scraper"

        def fetch_products(self, *, search_term: str, limit: int) -> list:
            raise ScraperError("offline")

        def close(self) -> None:
            return None

    with _pytest.warns(RuntimeWarning, match="api_token"):
        provider = FallbackProvider(api_provider=None, scraper_provider=_FailingScraper())
        AIProductTracker(provider=provider).get_products(limit=1)

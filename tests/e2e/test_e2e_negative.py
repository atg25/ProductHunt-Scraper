import httpx
import pytest

from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.protocols import FallbackProvider
from ph_ai_tracker.scraper import ProductHuntScraper


def test_e2e_both_sources_fail() -> None:
    def api_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"errors": []})

    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oops")

    provider = FallbackProvider(
        api_provider=ProductHuntAPI("token", transport=httpx.MockTransport(api_handler)),
        scraper_provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
    )
    r = AIProductTracker(provider=provider).get_products(limit=5)
    assert r.error is not None
    assert r.source == "auto"


def test_e2e_scraper_empty_page_returns_empty_result() -> None:
    """An empty 200 page must yield r.error is None + empty products (no exception)."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body></body></html>")

    r = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(handler)),
    ).get_products(limit=5)
    assert r.error is None
    assert r.products == ()


def test_e2e_scraper_timeout_produces_failure_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    r = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(handler)),
    ).get_products(limit=5)
    assert r.error is not None
    assert "timed out" in r.error.lower()


def test_e2e_scraper_500_produces_failure_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    r = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(handler)),
    ).get_products(limit=5)
    assert r.error is not None
    assert "500" in r.error


def test_e2e_auto_no_token_warning_logged(
    caplog,
) -> None:
    import logging

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body></body></html>")

    scraper = ProductHuntScraper(transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.WARNING, logger="ph_ai_tracker.protocols"):
        AIProductTracker(
            provider=FallbackProvider(api_provider=None, scraper_provider=scraper),
        ).get_products(limit=1)

    assert any("api_token" in r.message for r in caplog.records if r.levelno >= logging.WARNING)


def test_e2e_missing_token_and_network_failure_produce_distinct_messages(
) -> None:
    """Missing token warning and network failure are separate, diagnosable messages."""
    import pytest as _pytest

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    scraper = ProductHuntScraper(transport=httpx.MockTransport(handler))
    with _pytest.warns(RuntimeWarning) as record:
        provider = FallbackProvider(api_provider=None, scraper_provider=scraper)
        r = AIProductTracker(provider=provider).get_products(limit=1)

    # One RuntimeWarning about missing token
    token_warns = [w for w in record if "api_token" in str(w.message)]
    assert len(token_warns) >= 1

    # The result error must describe the network failure, not the token issue
    assert r.error is not None
    assert "timed out" in r.error.lower() or "scraper" in r.error.lower()

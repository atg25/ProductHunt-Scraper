from __future__ import annotations

import logging

import pytest

from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.exceptions import ScraperError
from ph_ai_tracker.models import Product
from ph_ai_tracker.protocols import FallbackProvider, ProductProvider, TaggingService, _NoTokenProvider
from ph_ai_tracker.scraper import ProductHuntScraper


class _StubScraper:
    """Minimal scraper stub; never raises."""

    source_name = "scraper"

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        return []

    def close(self) -> None:
        pass


class _FailingScraper(_StubScraper):
    """Always raises ScraperError."""

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        raise ScraperError("offline")


# isinstance conformance

def test_product_hunt_api_satisfies_protocol() -> None:
    assert isinstance(ProductHuntAPI("fake-token"), ProductProvider)


def test_product_hunt_scraper_satisfies_protocol() -> None:
    assert isinstance(ProductHuntScraper(), ProductProvider)


def test_fallback_provider_satisfies_protocol() -> None:
    fp = FallbackProvider(api_provider=None, scraper_provider=_StubScraper())
    assert isinstance(fp, ProductProvider)


def test_no_token_provider_satisfies_protocol() -> None:
    assert isinstance(_NoTokenProvider(), ProductProvider)


def test_arbitrary_object_does_not_satisfy_protocol() -> None:
    assert not isinstance(object(), ProductProvider)


def test_tagging_service_protocol_runtime_checkable() -> None:
    class _StubTagger:
        def categorize(self, product: Product) -> tuple[str, ...]:
            return ()

    assert isinstance(_StubTagger(), TaggingService)


def test_tagging_service_protocol_rejects_missing_method() -> None:
    class _NoCategorize:
        pass

    assert not isinstance(_NoCategorize(), TaggingService)


# source_name labels

def test_api_source_name() -> None:
    assert ProductHuntAPI("token").source_name == "api"


def test_scraper_source_name() -> None:
    assert ProductHuntScraper().source_name == "scraper"


def test_fallback_source_name() -> None:
    fp = FallbackProvider(api_provider=None, scraper_provider=_StubScraper())
    assert fp.source_name == "auto"


def test_no_token_provider_source_name() -> None:
    assert _NoTokenProvider().source_name == "api"


# FallbackProvider — missing-token warnings

def test_fallback_provider_logs_warning_when_api_is_none(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="ph_ai_tracker.protocols"):
        FallbackProvider(api_provider=None, scraper_provider=_StubScraper())
    assert any("api_token" in r.message for r in caplog.records if r.levelno >= logging.WARNING)


def test_fallback_provider_emits_runtime_warning_when_api_is_none() -> None:
    with pytest.warns(RuntimeWarning, match="api_token"):
        FallbackProvider(api_provider=None, scraper_provider=_StubScraper())


def test_fallback_provider_warning_message_is_actionable() -> None:
    with pytest.warns(RuntimeWarning) as rec:
        FallbackProvider(api_provider=None, scraper_provider=_StubScraper())
    msg = str(rec[0].message).lower()
    assert "api_token" in msg
    assert any(kw in msg for kw in ("producthunt_token", "set", "configure", "missing", "strategy"))


def test_fallback_provider_no_warning_when_api_is_present() -> None:
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        class _StubAPI(_StubScraper):
            source_name = "api"

        FallbackProvider(api_provider=_StubAPI(), scraper_provider=_StubScraper())
    api_warns = [x for x in w if issubclass(x.category, RuntimeWarning) and "api_token" in str(x.message)]
    assert api_warns == []


def test_fallback_provider_propagates_unexpected_exceptions() -> None:
    class _BuggyAPI(_StubScraper):
        source_name = "api"

        def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
            raise RuntimeError("Unexpected bug in API client")

    provider = FallbackProvider(api_provider=_BuggyAPI(), scraper_provider=_StubScraper())
    with pytest.raises(RuntimeError, match="Unexpected bug"):
        provider.fetch_products(search_term="AI", limit=10)

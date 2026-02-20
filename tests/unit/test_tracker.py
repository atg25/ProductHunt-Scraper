from __future__ import annotations

import ast
from pathlib import Path

from ph_ai_tracker.exceptions import APIError, RateLimitError, ScraperError
from ph_ai_tracker.models import Product
from ph_ai_tracker.protocols import FallbackProvider, _NoTokenProvider
from ph_ai_tracker.tracker import AIProductTracker


class _FakeProvider:
    def __init__(
        self,
        *,
        products: list[Product] | None = None,
        raises: Exception | None = None,
        source_name: str = "fake",
    ) -> None:
        self._products = products or []
        self._raises = raises
        self.source_name = source_name
        self.closed = False

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        if self._raises is not None:
            raise self._raises
        return self._products

    def close(self) -> None:
        self.closed = True


# Core delegation tests — tracker should delegate entirely to provider

def test_tracker_success_returns_products() -> None:
    t = AIProductTracker(provider=_FakeProvider(products=[Product(name="AlphaAI")], source_name="api"))
    r = t.get_products()
    assert r.error is None
    assert r.source == "api"
    assert len(r.products) == 1


def test_tracker_uses_provider_source_name() -> None:
    t = AIProductTracker(provider=_FakeProvider(products=[], source_name="scraper"))
    r = t.get_products()
    assert r.source == "scraper"


def test_tracker_rate_limit_maps_failure() -> None:
    t = AIProductTracker(provider=_FakeProvider(raises=RateLimitError("boom")))
    r = t.get_products(limit=1)
    assert r.error is not None
    assert "Rate limited" in r.error
    assert r.is_transient is True


def test_tracker_api_error_maps_failure() -> None:
    t = AIProductTracker(provider=_FakeProvider(raises=APIError("bad"), source_name="api"))
    r = t.get_products(limit=1)
    assert r.source == "api"
    assert r.error == "bad"
    assert r.is_transient is False


def test_tracker_scraper_error_maps_failure() -> None:
    t = AIProductTracker(provider=_FakeProvider(raises=ScraperError("down"), source_name="scraper"))
    r = t.get_products(limit=1)
    assert r.source == "scraper"
    assert r.error is not None
    assert r.is_transient is True


def test_tracker_calls_close_after_success() -> None:
    p = _FakeProvider(products=[Product(name="X")])
    AIProductTracker(provider=p).get_products()
    assert p.closed


def test_tracker_calls_close_after_exception() -> None:
    p = _FakeProvider(raises=ScraperError("err"))
    AIProductTracker(provider=p).get_products()
    assert p.closed


# _NoTokenProvider — sentinel for api strategy without a token

def test_no_token_provider_returns_api_failure() -> None:
    t = AIProductTracker(provider=_NoTokenProvider())
    r = t.get_products(limit=1)
    assert r.error == "Missing api_token"
    assert r.source == "api"


# FallbackProvider — auto-strategy combinator

def test_fallback_provider_succeeds_via_scraper_when_api_none() -> None:
    fp = FallbackProvider(
        api_provider=None,
        scraper_provider=_FakeProvider(products=[Product(name="B")]),
    )
    t = AIProductTracker(provider=fp)
    r = t.get_products(limit=1)
    assert r.error is None
    assert r.source == "auto"


def test_fallback_provider_both_fail_returns_failure() -> None:
    fp = FallbackProvider(
        api_provider=_FakeProvider(raises=APIError("api err")),
        scraper_provider=_FakeProvider(raises=ScraperError("scraper err")),
    )
    t = AIProductTracker(provider=fp)
    r = t.get_products(limit=1)
    assert r.source == "auto"
    assert r.error is not None


def test_tracker_does_not_import_adapters() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src" / "ph_ai_tracker" / "tracker.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "api_client" not in node.module
            assert "scraper" not in node.module

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


class _Tagger:
    def __init__(self, *, tags: tuple[str, ...] = ("ai",), raises: Exception | None = None) -> None:
        self._tags = tags
        self._raises = raises
        self.calls = 0

    def categorize(self, product: Product) -> tuple[str, ...]:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._tags


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


def test_get_products_enriches_products_with_tags() -> None:
    provider = _FakeProvider(products=[Product(name="Alpha")])
    tracker = AIProductTracker(provider=provider, tagging_service=_Tagger(tags=("ai", "tool")))
    result = tracker.get_products()
    assert result.products[0].tags == ("ai", "tool")


def test_get_products_uses_default_no_tags_without_tagger() -> None:
    provider = _FakeProvider(products=[Product(name="Alpha")])
    result = AIProductTracker(provider=provider).get_products()
    assert result.products[0].tags == ()


def test_enrich_product_propagates_tagger_exception() -> None:
    """If a TaggingService raises, the exception must propagate — not be swallowed."""
    import pytest as _pytest
    provider = _FakeProvider(products=[Product(name="Alpha")])
    tracker = AIProductTracker(provider=provider, tagging_service=_Tagger(raises=RuntimeError("boom")))
    with _pytest.raises(RuntimeError, match="boom"):
        tracker._enrich_product(Product(name="Alpha"))


def test_get_products_propagates_tagger_exception() -> None:
    """A raising TaggingService must bubble through get_products."""
    import pytest as _pytest
    provider = _FakeProvider(products=[Product(name="Alpha")])
    tracker = AIProductTracker(provider=provider, tagging_service=_Tagger(raises=RuntimeError("boom")))
    with _pytest.raises(RuntimeError, match="boom"):
        tracker.get_products()


def test_tagging_not_called_on_fetch_failure() -> None:
    tagger = _Tagger(tags=("ai",))
    tracker = AIProductTracker(provider=_FakeProvider(raises=APIError("bad")), tagging_service=tagger)
    result = tracker.get_products()
    assert result.error is not None
    assert tagger.calls == 0


def test_enrichment_produces_new_product_instances() -> None:
    original = Product(name="Alpha", tagline="tag", description="desc", votes_count=1, url="https://x", topics=("AI",))
    result = AIProductTracker(provider=_FakeProvider(products=[original]), tagging_service=_Tagger(tags=("ai",))).get_products()
    assert result.products[0] is not original
    assert original.tags == ()
    assert result.products[0].tags == ("ai",)


def test_enrichment_preserves_non_tag_fields() -> None:
    original = Product(name="Alpha", tagline="tag", description="desc", votes_count=7, url="https://x", topics=("AI", "ML"))
    enriched = AIProductTracker(provider=_FakeProvider(products=[original]), tagging_service=_Tagger(tags=("ai",))).get_products().products[0]
    assert enriched.name == original.name
    assert enriched.tagline == original.tagline
    assert enriched.description == original.description
    assert enriched.votes_count == original.votes_count
    assert enriched.url == original.url
    assert enriched.topics == original.topics

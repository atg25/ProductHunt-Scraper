from __future__ import annotations

import pytest
from datetime import datetime, timezone

from ph_ai_tracker.formatters import NewsletterFormatter
from ph_ai_tracker.models import Product
from ph_ai_tracker.tagging import NoOpTaggingService
from ph_ai_tracker.tracker import AIProductTracker


class _Provider:
    source_name = "fake"

    def __init__(self, products: list[Product]) -> None:
        self._products = products

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        return self._products

    def close(self) -> None:
        pass


class _Tagger:
    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises

    def categorize(self, product: Product) -> tuple[str, ...]:
        if self._raises and product.name.startswith("A"):
            raise RuntimeError("boom")
        return ("ai",)


def test_pipeline_tracks_tags_and_formats_newsletter() -> None:
    provider = _Provider([Product(name="Alpha", votes_count=5), Product(name="Beta", votes_count=10)])
    result = AIProductTracker(provider=provider, tagging_service=_Tagger()).get_products()
    out = NewsletterFormatter().format(list(result.products), generated_at=datetime.now(timezone.utc))
    assert result.error is None
    assert out["total_products"] == 2
    assert out["products"][0]["name"] == "Beta"
    assert out["top_tags"] == [{"tag": "ai", "count": 2}]


def test_pipeline_tagging_exception_propagates() -> None:
    """Sprint 61: a raising TaggingService must propagate — not silently produce empty tags."""
    provider = _Provider([Product(name="Alpha"), Product(name="Beta")])
    tracker = AIProductTracker(provider=provider, tagging_service=_Tagger(raises=True))
    with pytest.raises(RuntimeError, match="boom"):
        tracker.get_products()


def test_pipeline_noop_tagging_produces_empty_tags_in_newsletter() -> None:
    provider = _Provider([Product(name="A", votes_count=2), Product(name="B", votes_count=1)])
    result = AIProductTracker(provider=provider, tagging_service=NoOpTaggingService()).get_products()
    out = NewsletterFormatter().format(list(result.products), generated_at=datetime.now(timezone.utc))
    assert all(item["tags"] == [] for item in out["products"])


def test_pipeline_total_products_matches_provider_output() -> None:
    provider = _Provider([Product(name="A"), Product(name="B"), Product(name="C")])
    result = AIProductTracker(provider=provider, tagging_service=_Tagger()).get_products()
    out = NewsletterFormatter().format(list(result.products), generated_at=datetime.now(timezone.utc))
    assert out["total_products"] == 3


def test_pipeline_empty_provider_returns_valid_newsletter_structure() -> None:
    provider = _Provider([])
    result = AIProductTracker(provider=provider, tagging_service=_Tagger()).get_products()
    out = NewsletterFormatter().format(list(result.products), generated_at=datetime.now(timezone.utc))
    assert set(out.keys()) == {"generated_at", "total_products", "top_tags", "products"}
    assert out["total_products"] == 0
    assert out["products"] == []
    assert out["top_tags"] == []

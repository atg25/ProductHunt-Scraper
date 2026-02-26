from __future__ import annotations

from datetime import datetime, timezone

from ph_ai_tracker.formatters import NewsletterFormatter
from ph_ai_tracker.models import Product


def test_newsletter_sorts_by_votes_desc_then_name_asc() -> None:
    products = [
        Product(name="Zebra", votes_count=5),
        Product(name="Alpha", votes_count=5),
        Product(name="Beta", votes_count=10),
    ]
    out = NewsletterFormatter().format(products, generated_at=datetime.now(timezone.utc))
    assert [item["name"] for item in out["products"]] == ["Beta", "Alpha", "Zebra"]


def test_newsletter_top_tags_counts_and_sorts() -> None:
    products = [
        Product(name="A", tags=("ai", "tool")),
        Product(name="B", tags=("ai",)),
    ]
    out = NewsletterFormatter().format(products, generated_at=datetime.now(timezone.utc))
    assert out["top_tags"] == [{"tag": "ai", "count": 2}, {"tag": "tool", "count": 1}]


def test_newsletter_has_required_fields_for_each_product() -> None:
    out = NewsletterFormatter().format([Product(name="A")], generated_at=datetime.now(timezone.utc))
    product = out["products"][0]
    assert set(product.keys()) == {"name", "tagline", "description", "url", "votes", "topics", "tags", "posted_at"}


def test_newsletter_empty_products_is_valid_shape() -> None:
    out = NewsletterFormatter().format([], generated_at=datetime.now(timezone.utc))
    assert out["total_products"] == 0
    assert out["products"] == []
    assert out["top_tags"] == []


def test_newsletter_format_is_deterministic() -> None:
    products = [Product(name="B", votes_count=1), Product(name="A", votes_count=1)]
    generated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    formatter = NewsletterFormatter()
    assert formatter.format(products, generated_at) == formatter.format(products, generated_at)

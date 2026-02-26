"""Presentation formatters for ph_ai_tracker outputs."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from .models import Product


class NewsletterFormatter:
    """Build deterministic newsletter-friendly product output."""

    def format(self, products: list[Product], generated_at: datetime) -> dict:
        sorted_products = self._sorted_products(products)
        return {
            "generated_at": generated_at.isoformat(),
            "total_products": len(products),
            "top_tags": self._top_tags(products),
            "products": [self._product_item(product) for product in sorted_products],
        }

    @staticmethod
    def _sorted_products(products: list[Product]) -> list[Product]:
        return sorted(products, key=lambda product: (-int(product.votes_count), product.name))

    @staticmethod
    def _top_tags(products: list[Product]) -> list[dict[str, int | str]]:
        counts = Counter(tag for product in products for tag in product.tags)
        sorted_tags = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return [{"tag": tag, "count": count} for tag, count in sorted_tags]

    @staticmethod
    def _product_item(product: Product) -> dict:
        return {
            "name": product.name,
            "tagline": product.tagline,
            "description": product.description,
            "url": product.url,
            "votes": int(product.votes_count),
            "topics": list(product.topics),
            "tags": list(product.tags),
            "posted_at": product.posted_at.isoformat() if product.posted_at else None,
        }

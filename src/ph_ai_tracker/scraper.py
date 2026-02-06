from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, FeatureNotFound

from .exceptions import ScraperError
from .models import Product


@dataclass(frozen=True, slots=True)
class ScraperConfig:
    base_url: str = "https://www.producthunt.com"
    timeout_seconds: float = 10.0
    # A stable-ish entry point for AI products.
    # Product Hunt is a React app; this path may change, so we keep it configurable.
    ai_path: str = "/topics/artificial-intelligence"
    enrich_products: bool = True
    max_enrich: int = 10


class ProductHuntScraper:
    def __init__(
        self,
        *,
        config: ScraperConfig | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config or ScraperConfig()
        self._client = httpx.Client(timeout=self._config.timeout_seconds, transport=transport, headers={
            "User-Agent": "ph_ai_tracker/0.1.0 (+https://github.com/)"
        })

    def close(self) -> None:
        self._client.close()

    def _url(self) -> str:
        return self._config.base_url.rstrip("/") + self._config.ai_path

    def _soup(self, html: str) -> BeautifulSoup:
        # Prefer lxml if installed; fall back to the stdlib parser.
        try:
            return BeautifulSoup(html, "lxml")
        except FeatureNotFound:
            return BeautifulSoup(html, "html.parser")

    def _extract_next_data_products(self, html: str) -> list[Product]:
        soup = self._soup(html)
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return []

        try:
            payload = json.loads(script.string)
        except json.JSONDecodeError as exc:
            raise ScraperError("Failed to parse __NEXT_DATA__ JSON") from exc

        # Heuristic: walk the JSON and pick objects that look like posts.
        found: list[Product] = []

        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                maybe_name = obj.get("name")
                if isinstance(maybe_name, str) and maybe_name.strip():
                    votes = obj.get("votesCount")
                    tagline = obj.get("tagline")
                    description = obj.get("description")
                    url = obj.get("url") or obj.get("website")

                    if tagline is not None or description is not None or votes is not None:
                        try:
                            votes_int = int(votes or 0)
                        except (TypeError, ValueError):
                            votes_int = 0

                        topics: tuple[str, ...] = ()
                        # Try a few shapes
                        if isinstance(obj.get("topics"), list):
                            topics = tuple(
                                t.get("name") for t in obj.get("topics") if isinstance(t, dict) and t.get("name")
                            )

                        found.append(Product(
                            name=maybe_name.strip(),
                            tagline=tagline if isinstance(tagline, str) else None,
                            description=description if isinstance(description, str) else None,
                            votes_count=votes_int,
                            url=url if isinstance(url, str) else None,
                            topics=topics,
                        ))

                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(payload)

        # De-dupe by (name, url)
        unique: dict[tuple[str, str | None], Product] = {}
        for p in found:
            key = (p.name, p.url)
            unique[key] = p
        return list(unique.values())

    def _extract_dom_products(self, html: str) -> list[Product]:
        # Very soft fallback: attempt to find product-like anchors.
        soup = self._soup(html)
        products: list[Product] = []

        for a in soup.find_all("a"):
            href = a.get("href")
            text = (a.get_text(" ", strip=True) or "").strip()
            if not href or not text:
                continue
            if ("/products/" not in href) and ("/posts/" not in href):
                continue

            # Avoid obvious non-product URLs that happen to include the substring.
            if href.startswith("mailto:") or href.startswith("tel:"):
                continue

            url = href
            if url.startswith("/"):
                url = self._config.base_url.rstrip("/") + url

            parsed = urlparse(url)
            path_parts = [p for p in (parsed.path or "").split("/") if p]
            # Keep only canonical product pages: /products/<slug> or legacy /posts/<slug>
            if len(path_parts) < 2:
                continue
            if path_parts[0] in {"products", "posts"} and len(path_parts) != 2:
                continue

            products.append(Product(name=text, url=url))

        # De-dupe by name/url
        unique: dict[tuple[str, str | None], Product] = {}
        for p in products:
            unique[(p.name, p.url)] = p
        return list(unique.values())

    def _enrich_from_product_page(self, product: Product) -> Product:
        if not product.url:
            return product

        try:
            resp = self._client.get(product.url, follow_redirects=True)
        except httpx.HTTPError:
            return product

        if resp.status_code >= 400:
            return product

        html = resp.text
        soup = self._soup(html)

        def meta_content(**attrs: Any) -> str | None:
            tag = soup.find("meta", attrs=attrs)
            if not tag:
                return None
            content = tag.get("content")
            return content.strip() if isinstance(content, str) and content.strip() else None

        description = product.description
        tagline = product.tagline
        votes_count = product.votes_count

        # Prefer OG description, then standard description.
        if not description:
            description = meta_content(property="og:description") or meta_content(name="description")

        # Try to recover a short tagline from OG title patterns.
        if not tagline:
            og_title = meta_content(property="og:title")
            if og_title and og_title != product.name:
                tagline = None

        # Best-effort votesCount extraction from embedded JSON blobs.
        if not votes_count:
            matches = re.findall(r'"votesCount"\s*:\s*(\d+)', html)
            if matches:
                try:
                    votes_count = max(int(m) for m in matches)
                except ValueError:
                    votes_count = product.votes_count

        if description == product.description and tagline == product.tagline and votes_count == product.votes_count:
            return product

        return Product(
            name=product.name,
            tagline=tagline,
            description=description,
            votes_count=votes_count,
            url=product.url,
            topics=product.topics,
        )

    def scrape_ai_products(self, *, search_term: str = "AI", limit: int = 20) -> list[Product]:
        try:
            resp = self._client.get(self._url())
        except httpx.TimeoutException as exc:
            raise ScraperError("Scraper request timed out") from exc
        except httpx.HTTPError as exc:
            raise ScraperError("Scraper request failed") from exc

        if resp.status_code >= 400:
            raise ScraperError(f"Scraper HTTP error (status={resp.status_code})")

        html = resp.text
        products = self._extract_next_data_products(html)
        if not products:
            products = self._extract_dom_products(html)

        st = (search_term or "").strip().lower()
        has_rich_fields = any((p.tagline or p.description or p.topics) for p in products)
        if st and has_rich_fields:
            products = [
                p for p in products
                if st in (" ".join([p.name, p.tagline or "", p.description or "", " ".join(p.topics)]).lower())
            ]

        products = products[: max(int(limit), 1)]

        if self._config.enrich_products:
            needs_enrich = any((p.description is None or p.votes_count == 0) and p.url for p in products)
            if needs_enrich:
                enriched: list[Product] = []
                for idx, p in enumerate(products):
                    if idx < max(int(self._config.max_enrich), 0):
                        enriched.append(self._enrich_from_product_page(p))
                    else:
                        enriched.append(p)
                products = enriched

        # If we managed to extract votes, order by most votes first.
        if any(p.votes_count for p in products):
            products = sorted(products, key=lambda p: (p.votes_count, p.name), reverse=True)

        return products

"""HTML scraper for Product Hunt AI product listings.

Product Hunt is a React single-page application.  The primary data-extraction
strategy relies on the ``__NEXT_DATA__`` JSON blob that Next.js embeds in a
``<script>`` tag on every page-load.  This blob mirrors the GraphQL response
shape and is stable enough to parse with a recursive walk heuristic.

Dom invariants
--------------
* ``__NEXT_DATA__`` is a ``<script id="__NEXT_DATA__" type="application/json">``
  element.  Its ``string`` attribute contains the full JSON payload.
* Product anchors on canonical pages follow the path pattern
  ``/products/<slug>`` or (legacy) ``/posts/<slug>`` with exactly two path
  segments.  Navigation / category links that happen to contain ``/products/``
  as a substring will have more segments and are discarded.

When the primary extraction path yields no results (layout change, A/B test,
or CDN-cached variant), the DOM fallback activates.  Both paths log a WARNING
if they find nothing, so operators can detect layout changes in their log
stream without waiting for an alert on missing data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace as _dc_replace
from typing import Any
import json
import logging
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, FeatureNotFound

from .exceptions import ScraperError
from .models import Product

_log = logging.getLogger(__name__)

# Minimum URL path depth for a canonical product page, e.g. /products/<slug>
_MIN_PATH_DEPTH = 2


def _make_soup(html: str) -> BeautifulSoup:
    """Parse *html*, preferring lxml and falling back to the stdlib parser."""
    try:
        return BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        return BeautifulSoup(html, "html.parser")


def _coerce_votes(raw: Any) -> int:
    """Return *raw* as int, or ``0`` on any type/value error."""
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _extract_next_topics(raw: Any) -> tuple[str, ...]:
    """Convert a raw ``topics`` list from the JSON blob to a string tuple."""
    if not isinstance(raw, list):
        return ()
    return tuple(t.get("name") for t in raw if isinstance(t, dict) and t.get("name"))


@dataclass(frozen=True, slots=True)
class ScraperConfig:
    """Immutable configuration for ``ProductHuntScraper``."""

    base_url: str = "https://www.producthunt.com"
    timeout_seconds: float = 10.0
    ai_path: str = "/topics/artificial-intelligence"
    enrich_products: bool = True
    max_enrich: int = 10


class NextDataExtractor:
    """Extracts ``Product`` objects from the ``__NEXT_DATA__`` JSON blob.

    Walks the parsed JSON tree recursively via the ``_walk`` static method.
    A node is a product candidate when it has a non-empty ``name`` and at
    least one of ``tagline``, ``description``, or ``votesCount``.
    Results are de-duplicated by ``(name, url)``.
    """

    def extract(self, html: str) -> list[Product]:
        """Return products found in the ``__NEXT_DATA__`` script tag in *html*."""
        payload = self._load_next_data(_make_soup(html), html)
        if payload is None:
            return []
        found: list[Product] = []
        self._walk(payload, found)
        return self._dedup(found, html)

    @staticmethod
    def _load_next_data(soup: BeautifulSoup, html: str) -> Any | None:
        """Parse the ``__NEXT_DATA__`` JSON payload; return ``None`` on failure."""
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return None
        try:
            return json.loads(script.string)
        except json.JSONDecodeError as exc:
            _log.warning("Failed to parse __NEXT_DATA__ JSON: %s. Snippet: %.200s", exc, html)
            return None

    @staticmethod
    def _dedup(found: list[Product], html: str) -> list[Product]:
        """Deduplicate *found* by ``(name, url)``; log a WARNING if empty."""
        unique = {(p.name, p.url): p for p in found}
        if not unique:
            _log.warning("No products found in __NEXT_DATA__. Possible layout change. HTML snippet: %.200s", html)
        return list(unique.values())

    @staticmethod
    def _product_from_node(obj: dict[str, Any]) -> Product | None:
        """Build a ``Product`` from a JSON dict node, or return ``None``."""
        name = obj.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        tagline, description, votes = obj.get("tagline"), obj.get("description"), obj.get("votesCount")
        if tagline is None and description is None and votes is None:
            return None
        raw_url = obj.get("url") or obj.get("website")
        return Product(
            name=name.strip(),
            tagline=tagline if isinstance(tagline, str) else None,
            description=description if isinstance(description, str) else None,
            votes_count=_coerce_votes(votes),
            url=raw_url if isinstance(raw_url, str) else None,
            topics=_extract_next_topics(obj.get("topics")),
        )

    @staticmethod
    def _walk(obj: Any, found: list[Product]) -> None:
        """Recursively walk *obj*, appending product candidates to *found*."""
        if isinstance(obj, dict):
            product = NextDataExtractor._product_from_node(obj)
            if product is not None:
                found.append(product)
            for v in obj.values():
                NextDataExtractor._walk(v, found)
        elif isinstance(obj, list):
            for item in obj:
                NextDataExtractor._walk(item, found)


class DOMFallbackExtractor:
    """Extracts ``Product`` objects from anchor tags as a fallback.

    Only anchors matching ``/products/<slug>`` or ``/posts/<slug>``
    (exactly ``_MIN_PATH_DEPTH`` = 2 path segments) are accepted.
    Deeper navigation / category links are discarded.
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    def extract(self, html: str) -> list[Product]:
        """Return products found via anchor-tag parsing of *html*."""
        soup     = _make_soup(html)
        products = [
            p for a in soup.find_all("a")
            if (p := self._anchor_to_product(a)) is not None
        ]
        unique = {(p.name, p.url): p for p in products}
        if not unique:
            _log.warning(
                "DOM fallback found no product anchors. Possible layout change. "
                "HTML snippet: %.200s",
                html,
            )
        return list(unique.values())

    def _anchor_to_product(self, a: Any) -> Product | None:
        """Return a ``Product`` for anchor *a* if it is a canonical product link."""
        href = a.get("href")
        text = (a.get_text(" ", strip=True) or "").strip()
        if not href or not text:
            return None
        if ("/products/" not in href) and ("/posts/" not in href):
            return None
        if href.startswith(("mailto:", "tel:")):
            return None
        url    = href if not href.startswith("/") else self._base_url.rstrip("/") + href
        parsed = urlparse(url)
        parts  = [p for p in (parsed.path or "").split("/") if p]
        if len(parts) < _MIN_PATH_DEPTH:
            return None
        if parts[0] in {"products", "posts"} and len(parts) != _MIN_PATH_DEPTH:
            return None
        return Product(name=text, url=url)


class ProductEnricher:
    """Fills in missing fields on a ``Product`` by fetching its own page.

    OpenGraph meta tags are preferred because they are server-set and stable
    across layout changes.  If the request fails the original product is
    returned unchanged.
    """

    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self._client      = client
        self._owns_client = client is None
        if self._owns_client:
            self._client = httpx.Client()

    def close(self) -> None:
        if self._owns_client and self._client:
            self._client.close()

    def enrich(self, product: Product) -> Product:
        """Return *product* enriched with description and votes from its page."""
        if not product.url:
            return product
        resp = self._fetch_product_page(product.url)
        if resp is None or resp.status_code >= 400:
            return product
        description = product.description or self._og_description(_make_soup(resp.text))
        votes_count = product.votes_count or self._extract_votes(resp.text)
        if description == product.description and votes_count == product.votes_count:
            return product
        return _dc_replace(product, description=description, votes_count=votes_count)

    def _fetch_product_page(self, url: str) -> httpx.Response | None:
        """GET *url* and return the response; return ``None`` on network error."""
        try:
            return self._client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            _log.warning("Enrichment request failed for %s: %s", url, exc)
            return None

    @staticmethod
    def _og_description(soup: BeautifulSoup) -> str | None:
        """Return the first non-empty OG or standard description meta content."""
        for attrs in ({"property": "og:description"}, {"name": "description"}):
            tag = soup.find("meta", attrs=attrs)
            if tag:
                content = tag.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
        return None

    @staticmethod
    def _extract_votes(html: str) -> int:
        """Return the maximum votesCount value found embedded in *html*."""
        matches = re.findall(r'"votesCount"\s*:\s*(\d+)', html)
        if not matches:
            return 0
        try:
            return max(int(m) for m in matches)
        except ValueError:
            return 0


class ProductHuntScraper:
    """Thin coordinator that delegates to :class:`NextDataExtractor`,
    :class:`DOMFallbackExtractor`, and :class:`ProductEnricher`.

    Network failures (timeout, HTTP 4xx/5xx) are raised as :exc:`ScraperError`
    and propagate to the caller.  Parse errors and empty pages degrade
    gracefully and return ``[]``.
    """

    source_name = "scraper"

    def __init__(
        self,
        *,
        config: ScraperConfig | None = None,
        transport: httpx.BaseTransport | None = None,
        next_data_extractor: NextDataExtractor | None = None,
        dom_fallback_extractor: DOMFallbackExtractor | None = None,
        enricher: ProductEnricher | None = None,
    ) -> None:
        self._config      = config or ScraperConfig()
        self._client      = httpx.Client(
            timeout=self._config.timeout_seconds,
            transport=transport,
            headers={"User-Agent": "ph_ai_tracker/0.1.0 (+https://github.com/)"},
        )
        self._next_data    = next_data_extractor or NextDataExtractor()
        self._dom_fallback = dom_fallback_extractor or DOMFallbackExtractor(self._config.base_url)
        self._enricher     = enricher or ProductEnricher(client=self._client)

    def close(self) -> None:
        self._enricher.close()
        self._client.close()

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        """Protocol shim for tracker-layer ``ProductProvider`` usage."""
        return self.scrape_ai_products(search_term=search_term, limit=limit)

    def _url(self) -> str:
        return self._config.base_url.rstrip("/") + self._config.ai_path

    def _fetch_html(self) -> str:
        try:
            resp = self._client.get(self._url())
        except httpx.TimeoutException as exc:
            raise ScraperError("Scraper request timed out") from exc
        except httpx.HTTPError as exc:
            raise ScraperError("Scraper request failed") from exc
        if resp.status_code >= 400:
            raise ScraperError(f"Scraper HTTP error (status={resp.status_code})")
        return resp.text

    def _extract_products(self, html: str) -> list[Product]:
        try:
            products = self._next_data.extract(html)
            if not products:
                products = self._dom_fallback.extract(html)
        except (ValueError, AttributeError, KeyError) as exc:
            _log.warning("Unexpected extraction failure: %s", exc, exc_info=True)
            products = []
        return products

    def _apply_filter(
        self, products: list[Product], search_term: str, limit: int
    ) -> list[Product]:
        st = (search_term or "").strip().lower()
        has_rich = any((p.tagline or p.description or p.topics) for p in products)
        if st and has_rich:
            products = [p for p in products if st in p.searchable_text]
        return products[: max(int(limit), 1)]

    def _maybe_enrich(self, products: list[Product]) -> list[Product]:
        if not self._config.enrich_products:
            return products
        needs = any((p.description is None or p.votes_count == 0) and p.url for p in products)
        if not needs:
            return products
        cap = max(int(self._config.max_enrich), 0)
        return [
            self._enricher.enrich(p) if idx < cap else p
            for idx, p in enumerate(products)
        ]

    @staticmethod
    def _sort_by_votes(products: list[Product]) -> list[Product]:
        if any(p.votes_count for p in products):
            return sorted(products, key=lambda p: (p.votes_count, p.name), reverse=True)
        return products

    def scrape_ai_products(self, *, search_term: str = "AI", limit: int = 20) -> list[Product]:
        """Fetch and return a list of AI-related products from Product Hunt.

        Raises:
            ScraperError: On any network-layer failure (timeout, HTTP 4xx/5xx).
        """
        html     = self._fetch_html()
        products = self._extract_products(html)
        products = self._apply_filter(products, search_term, limit)
        products = self._maybe_enrich(products)
        return self._sort_by_votes(products)



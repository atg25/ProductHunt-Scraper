"""Product Hunt GraphQL API client.

Authentication is via a Developer Token (Bearer token).  The client queries the
``artificial-intelligence`` topic by default, fetching more records than
requested (``request_first = min(limit * 5, 50)``) so that client-side keyword
filtering still returns a full page even when some results are off-topic.

If the server returns GraphQL errors for the topic-scoped query (indicating
that the schema shape has changed), the client automatically retries with the
global ``posts`` query shape before surfacing the error to the caller.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any

import httpx

from .constants import DEFAULT_LIMIT, DEFAULT_RECENT_DAYS, DEFAULT_SEARCH_TERM
from .exceptions import APIError, RateLimitError
from .models import Product


DEFAULT_GRAPHQL_ENDPOINT = "https://api.producthunt.com/v2/api/graphql"


@dataclass(frozen=True, slots=True)
class APIConfig:
    """Immutable API client configuration."""

    endpoint: str = DEFAULT_GRAPHQL_ENDPOINT
    timeout_seconds: float = 10.0


@dataclass(frozen=True, slots=True)
class RateLimitInfo:
    """Parsed values from Product Hunt rate-limit response headers."""

    limit:         int | None  # X-Rate-Limit-Limit
    remaining:     int | None  # X-Rate-Limit-Remaining
    reset_seconds: int | None  # X-Rate-Limit-Reset (epoch seconds)
    retry_after:   int | None  # effective back-off to use


@dataclass(frozen=True, slots=True)
class QueryContext:
    """A clean GraphQL payload plus the local filter term."""

    payload: dict[str, Any]
    local_filter: str


def _header_int(headers: Mapping[str, str], key: str) -> int | None:
    """Return *key* from *headers* parsed as ``int``, or ``None``."""
    val = headers.get(key)
    if val is None:
        return None
    try:
        return int(str(val).strip())
    except ValueError:
        return None


class RateLimitParser:
    """Parses Product Hunt rate-limit response headers into a ``RateLimitInfo``."""

    @staticmethod
    def parse(headers: Mapping[str, str]) -> RateLimitInfo:
        """Return a ``RateLimitInfo`` from *headers*.

        ``X-Rate-Limit-Reset`` takes precedence over ``Retry-After``.
        """
        reset = _header_int(headers, "X-Rate-Limit-Reset")
        retry = _header_int(headers, "Retry-After")
        return RateLimitInfo(
            limit=_header_int(headers, "X-Rate-Limit-Limit"),
            remaining=_header_int(headers, "X-Rate-Limit-Remaining"),
            reset_seconds=reset,
            retry_after=reset if reset is not None else retry,
        )


_STRICT_TERMS = frozenset({"ai", "artificial intelligence"})
_PAGINATION_MULTIPLIER = 5
_MIN_FETCH_SIZE = 20
_MAX_FETCH_SIZE = 50
_AI_PATTERN   = re.compile(
    r"\bartificial\s+intelligence\b|\b(ai|ml|llm|gpt)\b",
    flags=re.IGNORECASE,
)


class StrictAIFilter:
    """Filters products for genuine AI relevance.

    Prevents false-positive substring matches — e.g. ``"paid"`` contains
    ``"ai"`` as a substring but is not an AI product.  Use
    ``is_strict_term`` to decide whether strict mode applies, then
    ``is_match`` to evaluate a product's combined text.
    """

    @staticmethod
    def is_strict_term(term: str) -> bool:
        """Return ``True`` if *term* warrants strict AI-only filtering."""
        return term.strip().lower() in _STRICT_TERMS

    def is_match(self, haystack: str, topics: tuple[str, ...]) -> bool:
        """Return ``True`` if *haystack* or *topics* contain a genuine AI signal."""
        if "artificial intelligence" in {t.lower() for t in topics}:
            return True
        return bool(_AI_PATTERN.search(haystack))

_GQL_POST_FIELDS = """
          name
          tagline
          description
                    createdAt
          votesCount
          url
          topics(first: 10) {{
            edges {{ node {{ name }} }}
          }}"""

_GQL_TOPIC_POSTS_TMPL = (
    "query TopicPosts($slug: String!, $first: Int!) {{\n"
    "  topic(slug: $slug) {{\n"
    "    posts(first: $first, order: {order}) {{\n"
    "      edges {{\n        node {{" + _GQL_POST_FIELDS + "\n        }}\n      }}\n    }}\n  }}\n}}"
)

_GQL_GLOBAL_POSTS_TMPL = (
    "query Posts($first: Int!) {{\n"
    "  posts(first: $first, order: {order}) {{\n"
    "    edges {{\n      node {{" + _GQL_POST_FIELDS + "\n      }}\n    }}\n  }}\n}}"
)


class ProductHuntAPI:
    """Low-level GraphQL client for the Product Hunt v2 API.

    Instantiation validates that ``api_token`` is non-empty — an empty token
    would produce a ``401`` on the first request and is caught early to give a
    clearer error message.
    """

    source_name = "api"

    def __init__(
        self,
        api_token: str,
        *,
        config: APIConfig | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_token or not api_token.strip():
            raise ValueError("api_token is required")
        self._token = api_token.strip()
        self._config = config or APIConfig()
        self._client = httpx.Client(timeout=self._config.timeout_seconds, transport=transport)

    def close(self) -> None:
        self._client.close()

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        """Protocol shim for tracker-layer ``ProductProvider`` usage."""
        return self.fetch_ai_products(search_term=search_term, limit=limit)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _build_query(
        *, first: int, order: str, topic_slug: str | None, search_term: str
    ) -> QueryContext:
        """Assemble a GraphQL payload and local filter context."""
        order_enum = (order or "RANKING").strip().upper()
        if order_enum not in {"RANKING", "NEWEST"}:
            order_enum = "RANKING"
        if topic_slug:
            tmpl = _GQL_TOPIC_POSTS_TMPL
            variables: dict[str, Any] = {"slug": str(topic_slug), "first": int(first)}
        else:
            tmpl = _GQL_GLOBAL_POSTS_TMPL
            variables = {"first": int(first)}
        return QueryContext(
            payload={
            "query": tmpl.format(order=order_enum),
            "variables": variables,
            },
            local_filter=search_term.strip().lower(),
        )

    def _extract_edges(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Return edges from ``data.topic.posts`` (topic shape) or ``data.posts`` (global)."""
        data = payload.get("data") or {}
        topic_edges = self._parse_topic_edges(data)
        if topic_edges is not None:
            return topic_edges
        return self._parse_global_edges(data)

    @staticmethod
    def _parse_topic_edges(data: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Return edges from ``data["topic"]["posts"]``, or ``None`` when absent."""
        topic = data.get("topic")
        if not isinstance(topic, dict):
            return None
        posts = topic.get("posts")
        if not isinstance(posts, dict):
            return None
        edges = posts.get("edges")
        return edges if isinstance(edges, list) else None

    @staticmethod
    def _parse_global_edges(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Return edges from ``data["posts"]``, or ``[]`` when absent."""
        posts = data.get("posts")
        if not isinstance(posts, dict):
            return []
        edges = posts.get("edges")
        return edges if isinstance(edges, list) else []

    def fetch_ai_products(
        self,
        *,
        search_term: str = DEFAULT_SEARCH_TERM,
        limit: int = DEFAULT_LIMIT,
        topic_slug: str | None = "artificial-intelligence",
        order: str = "RANKING",
    ) -> list[Product]:
        """Fetch AI products; over-fetches then sorts + truncates to ``limit``."""
        limit_int = max(int(limit), 1)
        query_context = self._build_query(
            first=min(max(limit_int * _PAGINATION_MULTIPLIER, _MIN_FETCH_SIZE), _MAX_FETCH_SIZE), order=order,
            topic_slug=topic_slug, search_term=search_term,
        )
        products = self._fetch_and_build(
            query_context.payload, topic_slug, limit_int, order, query_context.local_filter
        )
        products = self._filter_recent_products(products, days=DEFAULT_RECENT_DAYS)
        products.sort(key=lambda p: p.votes_count, reverse=True)
        return products[:limit_int]

    @staticmethod
    def _filter_recent_products(products: list[Product], *, days: int) -> list[Product]:
        if not products or not any(p.posted_at is not None for p in products):
            return products
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=max(int(days), 1))
        return [
            product
            for product in products
            if product.posted_at is not None and product.posted_at >= cutoff
        ]

    @staticmethod
    def _parse_posted_at(raw: Any) -> datetime | None:
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    def _execute_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST *payload*; return parsed JSON. Raises RateLimitError/APIError."""
        try:
            response = self._client.post(
                self._config.endpoint, headers=self._headers(), json=payload
            )
        except httpx.TimeoutException as exc:
            raise APIError("API request timed out") from exc
        except httpx.HTTPError as exc:
            raise APIError("API request failed") from exc
        self._raise_for_rate_limit(response)
        if response.status_code in (401, 403):
            raise APIError(f"API auth failed (status={response.status_code})")
        if response.status_code >= 400:
            raise APIError(f"API error (status={response.status_code})")
        return self._parse_json(response)

    def _raise_for_rate_limit(self, response: httpx.Response) -> None:
        """Raise ``RateLimitError`` if *response* is HTTP 429."""
        if response.status_code != 429:
            return
        rl = RateLimitParser.parse(response.headers)
        raise RateLimitError(
            "Product Hunt API rate limit hit",
            retry_after_seconds=rl.retry_after,
            rate_limit_limit=rl.limit,
            rate_limit_remaining=rl.remaining,
            rate_limit_reset_seconds=rl.reset_seconds,
        )

    @staticmethod
    def _parse_json(response: httpx.Response) -> dict[str, Any]:
        """Unpack JSON from *response* or raise ``APIError``."""
        try:
            return response.json()
        except ValueError as exc:
            raise APIError("API returned non-JSON response") from exc

    def _fetch_and_build(
        self, payload: dict[str, Any], topic_slug: str | None,
        limit_int: int, order: str, raw_filter: str,
    ) -> list[Product]:
        """Execute the request (with optional global-query retry) and build products."""
        data = self._execute_request(payload)
        if data.get("errors") and topic_slug:
            data = self._retry_with_global_query(limit_int, order, raw_filter)
        if data.get("errors"):
            raise APIError("GraphQL errors returned")
        return self._build_products_from_edges(self._extract_edges(data), raw_filter)

    def _retry_with_global_query(
        self, limit_int: int, order: str, local_filter: str
    ) -> dict[str, Any]:
        """Re-issue the query without a topic slug when the topic-scoped query
        returns GraphQL errors (schema divergence between API versions).
        """
        fallback = self._build_query(
            first=limit_int, order=order, topic_slug=None, search_term=local_filter,
        )
        return self._execute_request(fallback.payload)

    def _build_products_from_edges(
        self, edges: list[dict[str, Any]], local_filter: str
    ) -> list[Product]:
        """Construct ``Product`` objects from *edges* and apply *local_filter*."""
        ai_filter = StrictAIFilter()
        strict    = StrictAIFilter.is_strict_term(local_filter)
        products: list[Product] = []
        for edge in edges or []:
            node = (edge or {}).get("node") or {}
            if not node.get("name"):
                continue
            p = self._node_to_product(node)
            if not local_filter:
                products.append(p)
                continue
            if strict and self._passes_strict_filter(p, ai_filter):
                products.append(p)
            if (not strict) and self._passes_loose_filter(p, local_filter):
                products.append(p)
        return products

    @staticmethod
    def _node_to_product(node: dict[str, Any]) -> Product:
        """Build a ``Product`` from a GraphQL node dict."""
        topics_edges = ProductHuntAPI._parse_topic_edges_from_node(node)
        topics = tuple(
            (te.get("node") or {}).get("name")
            for te in topics_edges
            if (te.get("node") or {}).get("name")
        )
        return Product(
            name=str(node.get("name")),
            tagline=node.get("tagline"),
            description=node.get("description"),
            votes_count=int(node.get("votesCount") or 0),
            url=node.get("url"),
            topics=topics,
            posted_at=ProductHuntAPI._parse_posted_at(node.get("createdAt")),
        )

    @staticmethod
    def _parse_topic_edges_from_node(node: dict[str, Any]) -> list[dict[str, Any]]:
        """Return topic edges from a GraphQL post node, or ``[]``."""
        topics = node.get("topics")
        if not isinstance(topics, dict):
            return []
        edges = topics.get("edges")
        return edges if isinstance(edges, list) else []

    @staticmethod
    def _passes_strict_filter(p: Product, ai_filter: StrictAIFilter) -> bool:
        """Return ``True`` if *p* satisfies strict AI filtering."""
        return ai_filter.is_match(p.searchable_text, p.topics)

    @staticmethod
    def _passes_loose_filter(p: Product, local_filter: str) -> bool:
        """Return ``True`` if *local_filter* appears in *p* text fields."""
        return local_filter in p.searchable_text

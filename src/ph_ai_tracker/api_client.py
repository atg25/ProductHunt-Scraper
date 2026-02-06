from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import httpx

from .exceptions import APIError, RateLimitError
from .models import Product


DEFAULT_GRAPHQL_ENDPOINT = "https://api.producthunt.com/v2/api/graphql"


@dataclass(frozen=True, slots=True)
class APIConfig:
    endpoint: str = DEFAULT_GRAPHQL_ENDPOINT
    timeout_seconds: float = 10.0


class ProductHuntAPI:
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

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _build_query(
        self,
        *,
        first: int,
        order: str,
        topic_slug: str | None,
        search_term: str,
    ) -> dict[str, Any]:
        # Prefer topic-scoped trending posts (AI topic). Fallback to global posts if needed.
        # We still do a client-side text filter for robustness.
        order_enum = (order or "RANKING").strip().upper()
        if order_enum not in {"RANKING", "NEWEST"}:
            order_enum = "RANKING"

        if topic_slug:
            query = f"""
            query TopicPosts($slug: String!, $first: Int!) {{
              topic(slug: $slug) {{
                posts(first: $first, order: {order_enum}) {{
                  edges {{
                    node {{
                      name
                      tagline
                      description
                      votesCount
                      url
                      topics(first: 10) {{
                        edges {{ node {{ name }} }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            """
            variables = {"slug": str(topic_slug), "first": int(first)}
        else:
            query = f"""
            query Posts($first: Int!) {{
              posts(first: $first, order: {order_enum}) {{
                edges {{
                  node {{
                    name
                    tagline
                    description
                    votesCount
                    url
                    topics(first: 10) {{
                      edges {{ node {{ name }} }}
                    }}
                  }}
                }}
              }}
            }}
            """
            variables = {"first": int(first)}

        return {
            "query": query,
            "variables": variables,
            "_local_filter": search_term,
            "_order": order_enum,
            "_topic_slug": topic_slug,
        }

    def _extract_edges(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data") or {}

        # Topic shape: data.topic.posts.edges
        topic = data.get("topic") or {}
        posts_in_topic = topic.get("posts") or {}
        edges = posts_in_topic.get("edges")
        if isinstance(edges, list):
            return edges

        # Global shape: data.posts.edges
        posts = data.get("posts") or {}
        edges = posts.get("edges")
        if isinstance(edges, list):
            return edges

        return []

    def fetch_ai_products(
        self,
        *,
        search_term: str = "AI",
        limit: int = 20,
        topic_slug: str | None = "artificial-intelligence",
        order: str = "RANKING",
    ) -> list[Product]:
        # "Top trending" by default = RANKING.
        limit_int = max(int(limit), 1)
        # Fetch a larger page so filtering doesn't leave us empty.
        request_first = min(max(limit_int * 5, 20), 50)
        payload = self._build_query(
            first=request_first,
            order=order,
            topic_slug=topic_slug,
            search_term=search_term,
        )
        raw_filter = (payload.pop("_local_filter") or "").strip()
        local_filter = raw_filter.lower()
        payload.pop("_order", None)
        payload.pop("_topic_slug", None)

        # "AI" as a substring matches lots of unrelated words (e.g., "paid").
        # Treat the default/generic "AI" query as a stricter AI-only filter.
        strict_ai = local_filter in {"", "ai", "artificial intelligence"}

        try:
            response = self._client.post(self._config.endpoint, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise APIError("API request timed out") from exc
        except httpx.HTTPError as exc:
            raise APIError("API request failed") from exc

        if response.status_code == 429:
            def to_int(value: str | None) -> int | None:
                if value is None:
                    return None
                try:
                    return int(str(value).strip())
                except ValueError:
                    return None

            # Per PH docs: X-Rate-Limit-Limit / Remaining / Reset
            rl_limit = to_int(response.headers.get("X-Rate-Limit-Limit"))
            rl_remaining = to_int(response.headers.get("X-Rate-Limit-Remaining"))
            rl_reset = to_int(response.headers.get("X-Rate-Limit-Reset"))

            # Keep Retry-After support, but prefer PH reset when present.
            retry_after_int = to_int(response.headers.get("Retry-After"))
            if retry_after_int is None:
                retry_after_int = rl_reset

            raise RateLimitError(
                "Product Hunt API rate limit hit",
                retry_after_seconds=retry_after_int,
                rate_limit_limit=rl_limit,
                rate_limit_remaining=rl_remaining,
                rate_limit_reset_seconds=rl_reset,
            )

        if response.status_code in (401, 403):
            raise APIError(f"API auth failed (status={response.status_code})")

        if response.status_code >= 400:
            raise APIError(f"API error (status={response.status_code})")

        try:
            data = response.json()
        except ValueError as exc:
            raise APIError("API returned non-JSON response") from exc

        # If the topic field isn't supported (schema differences), retry once with global posts.
        if "errors" in data and data["errors"] and topic_slug:
            fallback = self._build_query(
                first=max(int(limit), 1),
                order=order,
                topic_slug=None,
                search_term=local_filter,
            )
            local_filter = (fallback.pop("_local_filter") or "").strip().lower()
            fallback.pop("_order", None)
            fallback.pop("_topic_slug", None)

            response = self._client.post(self._config.endpoint, headers=self._headers(), json=fallback)
            if response.status_code >= 400:
                raise APIError(f"API error (status={response.status_code})")
            try:
                data = response.json()
            except ValueError as exc:
                raise APIError("API returned non-JSON response") from exc

        # Still errors after fallback -> surface
        if "errors" in data and data["errors"]:
            raise APIError("GraphQL errors returned")

        edges = self._extract_edges(data)

        products: list[Product] = []
        for edge in edges or []:
            node = (edge or {}).get("node") or {}
            name = node.get("name")
            if not name:
                continue

            topics_edges = (((node.get("topics") or {}).get("edges")) or [])
            topics = tuple(
                (te.get("node") or {}).get("name")
                for te in topics_edges
                if (te.get("node") or {}).get("name")
            )

            p = Product(
                name=str(name),
                tagline=node.get("tagline"),
                description=node.get("description"),
                votes_count=int(node.get("votesCount") or 0),
                url=node.get("url"),
                topics=topics,
            )

            if not local_filter:
                products.append(p)
                continue

            haystack = " ".join(
                [
                    p.name or "",
                    p.tagline or "",
                    p.description or "",
                    " ".join(p.topics),
                ]
            )

            if strict_ai:
                topics_lc = {t.lower() for t in p.topics}
                topic_match = "artificial intelligence" in topics_lc

                # Accept common AI signals while avoiding broad substring matches.
                text_match = bool(
                    re.search(r"\bartificial\s+intelligence\b", haystack, flags=re.IGNORECASE)
                    or re.search(r"\b(ai|ml|llm|gpt)\b", haystack, flags=re.IGNORECASE)
                )

                if topic_match or text_match:
                    products.append(p)
                continue

            if local_filter in haystack.lower():
                products.append(p)

        products.sort(key=lambda pr: pr.votes_count, reverse=True)
        return products[:limit_int]

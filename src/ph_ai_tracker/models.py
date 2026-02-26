"""Core domain models for ph_ai_tracker.

Both ``Product`` and ``TrackerResult`` are immutable frozen dataclasses.
Immutability is intentional: once data has been fetched and returned to the
caller (or persisted to storage), it must not change under the caller's feet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any, Iterable
import json
import re
import string


def _coerce_topics(raw: Any) -> tuple[str, ...]:
    """Convert a raw topics value from ``from_dict`` into a tuple of strings."""
    if not raw:
        return ()
    if isinstance(raw, str):
        raw = [raw]
    return tuple(str(t) for t in raw)


def _coerce_tags(raw: Any) -> tuple[str, ...]:
    if not raw:
        return ()
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list | tuple):
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for value in raw:
        if not isinstance(value, str):
            continue
        tag = value.strip().lower()
        if not tag or len(tag) > 20 or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return tuple(out)


def _normalized_url(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    parsed = urlparse(url.strip().lower())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path.rstrip("/")
    cleaned = parsed._replace(path=path, query="", fragment="")
    return cleaned.geturl()


def _normalized_name(name: str) -> str:
    collapsed = re.sub(r"\s+", " ", name.strip().lower())
    return collapsed.strip(string.punctuation)


def canonical_key(product: "Product") -> str:
    normalized_url = _normalized_url(product.url)
    if normalized_url is not None:
        return f"url:{normalized_url}"
    return f"name:{_normalized_name(product.name)}"


def _coerce_datetime(raw: Any) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=timezone.utc)
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class Product:
    """A single Product Hunt listing captured during one tracker run.

    ``name`` is the only required field — it is the human-readable title of
    the product.  All other fields are optional enrichment that may be
    populated by the API path, the scraper path, or the per-product enrichment
    step in ``ProductHuntScraper._enrich_from_product_page``.

    Invariant: ``name`` is non-empty.  Attempting to construct a ``Product``
    with a blank or whitespace-only ``name`` raises ``ValueError``.
    """

    name: str
    tagline: str | None = None
    description: str | None = None
    votes_count: int = 0
    url: str | None = None
    topics: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    posted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Product.name must be a non-empty string")

    @property
    def searchable_text(self) -> str:
        """Lowercase concatenation of all human-readable text fields."""
        return " ".join([self.name or "", self.tagline or "", self.description or "", " ".join(self.topics)]).lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tagline": self.tagline,
            "description": self.description,
            "votes_count": self.votes_count,
            "url": self.url,
            "topics": list(self.topics),
            "tags": list(self.tags),
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Product":
        """Build a ``Product`` from a plain dict (e.g. parsed JSON)."""
        votes = data.get("votes_count", 0)
        try:
            votes_int = int(votes)
        except (TypeError, ValueError) as exc:
            raise ValueError("votes_count must be an int") from exc
        return cls(
            name=str(data.get("name") or ""),
            tagline=data.get("tagline"),
            description=data.get("description"),
            votes_count=votes_int,
            url=data.get("url"),
            topics=_coerce_topics(data.get("topics")),
            tags=_coerce_tags(data.get("tags")),
            posted_at=_coerce_datetime(data.get("posted_at")),
        )


@dataclass(frozen=True, slots=True)
class TrackerResult:
    """The outcome of a single ``AIProductTracker.get_products()`` call.

    ``error is None`` is the canonical success signal.  ``products`` is always
    a tuple; on failure it is empty unless a partial result was recorded.

    Note: ``products`` *may* be non-empty even when ``error`` is set — this
    represents a *partial* result where some data was recovered before the
    failure occurred (the scheduler records these with ``status='partial'``).

    ``is_transient`` is a scheduler hint: ``True`` means retrying this
    failure is safe and potentially useful (e.g. timeout/rate-limit).

    ``search_term`` and ``limit`` capture the request context that produced
    the result.
    """

    products: tuple[Product, ...]
    source: str
    fetched_at: datetime
    error: str | None = None
    is_transient: bool = False
    search_term: str = ""
    limit: int = 0

    @classmethod
    def success(
        cls,
        products: Iterable[Product],
        source: str,
        *,
        search_term: str = "",
        limit: int = 0,
    ) -> "TrackerResult":
        return cls(
            products=tuple(products),
            source=source,
            fetched_at=datetime.now(timezone.utc),
            error=None,
            search_term=search_term,
            limit=limit,
        )

    @classmethod
    def failure(
        cls,
        source: str,
        error: str,
        *,
        is_transient: bool = False,
        search_term: str = "",
        limit: int = 0,
    ) -> "TrackerResult":
        return cls(
            products=(),
            source=source,
            fetched_at=datetime.now(timezone.utc),
            error=error,
            is_transient=is_transient,
            search_term=search_term,
            limit=limit,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "fetched_at": self.fetched_at.isoformat(),
            "error": self.error,
            "products": [p.to_dict() for p in self.products],
        }

    def to_pretty_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)

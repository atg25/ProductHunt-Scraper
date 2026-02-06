from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
import json


@dataclass(frozen=True, slots=True)
class Product:
    name: str
    tagline: str | None = None
    description: str | None = None
    votes_count: int = 0
    url: str | None = None
    topics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tagline": self.tagline,
            "description": self.description,
            "votes_count": self.votes_count,
            "url": self.url,
            "topics": list(self.topics),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Product":
        if "name" not in data or not data["name"]:
            raise ValueError("Product.name is required")
        votes = data.get("votes_count", 0)
        try:
            votes_int = int(votes)
        except (TypeError, ValueError) as exc:
            raise ValueError("votes_count must be an int") from exc

        topics = data.get("topics") or []
        if isinstance(topics, str):
            topics = [topics]

        return cls(
            name=str(data["name"]),
            tagline=data.get("tagline"),
            description=data.get("description"),
            votes_count=votes_int,
            url=data.get("url"),
            topics=tuple(str(t) for t in topics),
        )


@dataclass(frozen=True, slots=True)
class TrackerResult:
    products: tuple[Product, ...]
    source: str
    fetched_at: datetime
    error: str | None = None

    @classmethod
    def success(cls, products: Iterable[Product], source: str) -> "TrackerResult":
        return cls(products=tuple(products), source=source, fetched_at=datetime.now(timezone.utc), error=None)

    @classmethod
    def failure(cls, source: str, error: str) -> "TrackerResult":
        return cls(products=(), source=source, fetched_at=datetime.now(timezone.utc), error=error)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "fetched_at": self.fetched_at.isoformat(),
            "error": self.error,
            "products": [p.to_dict() for p in self.products],
        }

    def to_pretty_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)

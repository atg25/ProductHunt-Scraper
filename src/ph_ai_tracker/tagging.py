"""Outer-layer tagging service implementations."""

from __future__ import annotations

from typing import Any
import json

import httpx

from .models import Product


def _clean_tags(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for value in raw:
        if not isinstance(value, str):
            return ()
        tag = value.strip().lower()
        if not tag or len(tag) > 20 or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return tuple(out)


class NoOpTaggingService:
    """Tagging service that intentionally returns no tags."""

    def categorize(self, product: Product) -> tuple[str, ...]:
        return ()


class UniversalLLMTaggingService:
    """OpenAI-compatible HTTP tagging service.

    Never raises: any failure returns an empty tuple.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "gpt-4o-mini",
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._transport = transport

    def categorize(self, product: Product) -> tuple[str, ...]:
        try:
            return self._call(product)
        except Exception:
            return ()

    def _call(self, product: Product) -> tuple[str, ...]:
        payload = self._payload(product)
        body = self._post(payload)
        return self._validate_response(body)

    def _payload(self, product: Product) -> dict[str, Any]:
        prompt = (
            "Return JSON exactly in this schema: {\"tags\": [string, ...]}. "
            "Use concise lowercase category tags for this product text: "
            f"{product.searchable_text}"
        )
        return {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _post(self, payload: dict[str, Any]) -> Any:
        with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def _validate_response(self, body: Any) -> tuple[str, ...]:
        message = self._extract_content(body)
        if message is None:
            return ()
        if isinstance(message, str):
            data = json.loads(message)
        elif isinstance(message, dict):
            data = message
        else:
            return ()
        if not isinstance(data, dict) or set(data.keys()) != {"tags"}:
            return ()
        return _clean_tags(data.get("tags"))

    @staticmethod
    def _extract_content(body: Any) -> Any | None:
        if not isinstance(body, dict):
            return None
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            return None
        return message.get("content")

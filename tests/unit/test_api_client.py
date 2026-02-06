import httpx
import pytest

from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.exceptions import APIError, RateLimitError


def test_client_init_missing_token_raises() -> None:
    with pytest.raises(ValueError):
        ProductHuntAPI(" ")


def test_fetch_returns_products(api_success_payload: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers.get("Authorization", "").startswith("Bearer ")
        return httpx.Response(200, json=api_success_payload)

    transport = httpx.MockTransport(handler)
    api = ProductHuntAPI("token", transport=transport)
    try:
        products = api.fetch_ai_products(search_term="AI", limit=10)
        assert len(products) >= 1
        assert products[0].name
    finally:
        api.close()


def test_rate_limit_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={
                "X-Rate-Limit-Limit": "6250",
                "X-Rate-Limit-Remaining": "0",
                "X-Rate-Limit-Reset": "850",
            },
            json={"errors": []},
        )

    transport = httpx.MockTransport(handler)
    api = ProductHuntAPI("token", transport=transport)
    try:
        with pytest.raises(RateLimitError) as exc:
            api.fetch_ai_products(limit=1)
        assert exc.value.rate_limit_limit == 6250
        assert exc.value.rate_limit_remaining == 0
        assert exc.value.rate_limit_reset_seconds == 850
        assert exc.value.retry_after_seconds == 850
    finally:
        api.close()


def test_auth_failure_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "no"})

    transport = httpx.MockTransport(handler)
    api = ProductHuntAPI("token", transport=transport)
    try:
        with pytest.raises(APIError):
            api.fetch_ai_products(limit=1)
    finally:
        api.close()


def test_non_json_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    transport = httpx.MockTransport(handler)
    api = ProductHuntAPI("token", transport=transport)
    try:
        with pytest.raises(APIError):
            api.fetch_ai_products(limit=1)
    finally:
        api.close()

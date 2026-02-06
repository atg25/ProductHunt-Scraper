import httpx

from ph_ai_tracker.api_client import ProductHuntAPI


def test_full_api_flow_mocked_success(api_success_payload: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=api_success_payload)

    transport = httpx.MockTransport(handler)
    api = ProductHuntAPI("token", transport=transport)
    try:
        products = api.fetch_ai_products(search_term="AI", limit=5)
        assert products
        assert products[0].votes_count == 123
    finally:
        api.close()


def test_api_network_timeout_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("boom")

    transport = httpx.MockTransport(handler)
    api = ProductHuntAPI("token", transport=transport)
    try:
        try:
            api.fetch_ai_products(limit=1)
            assert False, "Expected exception"
        except Exception as exc:
            assert "timed out" in str(exc).lower() or "failed" in str(exc).lower()
    finally:
        api.close()

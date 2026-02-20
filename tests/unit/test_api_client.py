import httpx
import pytest

from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.exceptions import APIError, RateLimitError
from ph_ai_tracker.models import Product


def test_pagination_multiplier_constant_exists() -> None:
    from ph_ai_tracker.api_client import _PAGINATION_MULTIPLIER

    assert _PAGINATION_MULTIPLIER == 5


def test_min_fetch_size_constant_exists() -> None:
    from ph_ai_tracker.api_client import _MIN_FETCH_SIZE

    assert _MIN_FETCH_SIZE == 20


def test_max_fetch_size_constant_exists() -> None:
    from ph_ai_tracker.api_client import _MAX_FETCH_SIZE

    assert _MAX_FETCH_SIZE == 50


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


def test_fetch_never_requests_more_than_max_fetch_size() -> None:
    from ph_ai_tracker.api_client import _MAX_FETCH_SIZE

    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode("utf-8")
        assert '"first":' in payload
        marker = '"first":'
        idx = payload.index(marker) + len(marker)
        num = ""
        while idx < len(payload) and payload[idx] in " \t":
            idx += 1
        while idx < len(payload) and payload[idx].isdigit():
            num += payload[idx]
            idx += 1
        seen.append(int(num))
        return httpx.Response(200, json={"data": {"topic": {"posts": {"edges": []}}}})

    api = ProductHuntAPI("token", transport=httpx.MockTransport(handler))
    try:
        api.fetch_ai_products(limit=100)
    finally:
        api.close()
    assert seen and seen[0] <= _MAX_FETCH_SIZE


def test_fetch_never_requests_less_than_min_fetch_size() -> None:
    from ph_ai_tracker.api_client import _MIN_FETCH_SIZE

    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode("utf-8")
        marker = '"first":'
        idx = payload.index(marker) + len(marker)
        num = ""
        while idx < len(payload) and payload[idx] in " \t":
            idx += 1
        while idx < len(payload) and payload[idx].isdigit():
            num += payload[idx]
            idx += 1
        seen.append(int(num))
        return httpx.Response(200, json={"data": {"topic": {"posts": {"edges": []}}}})

    api = ProductHuntAPI("token", transport=httpx.MockTransport(handler))
    try:
        api.fetch_ai_products(limit=1)
    finally:
        api.close()
    assert seen and seen[0] >= _MIN_FETCH_SIZE


def test_parse_topic_edges_returns_list_when_present() -> None:
    data = {"topic": {"posts": {"edges": [{"node": {"name": "X"}}]}}}
    edges = ProductHuntAPI._parse_topic_edges(data)
    assert edges == [{"node": {"name": "X"}}]


def test_parse_topic_edges_returns_none_when_topic_missing() -> None:
    assert ProductHuntAPI._parse_topic_edges({}) is None


def test_parse_topic_edges_returns_none_when_posts_missing() -> None:
    assert ProductHuntAPI._parse_topic_edges({"topic": {"other": 1}}) is None


def test_parse_global_edges_returns_list_when_present() -> None:
    data = {"posts": {"edges": [{"node": {"name": "Y"}}]}}
    edges = ProductHuntAPI._parse_global_edges(data)
    assert edges == [{"node": {"name": "Y"}}]


def test_parse_global_edges_returns_empty_when_absent() -> None:
    assert ProductHuntAPI._parse_global_edges({}) == []


def test_parse_topic_edges_from_node_returns_list_when_present() -> None:
    node = {"topics": {"edges": [{"node": {"name": "AI"}}]}}
    assert ProductHuntAPI._parse_topic_edges_from_node(node) == [{"node": {"name": "AI"}}]


def test_parse_topic_edges_from_node_returns_empty_when_absent() -> None:
    assert ProductHuntAPI._parse_topic_edges_from_node({}) == []


def test_fetch_strips_and_lowercases_search_term(api_success_payload: dict) -> None:
    """``fetch_ai_products`` normalises ``search_term`` whitespace/case."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=api_success_payload)

    api = ProductHuntAPI("token", transport=httpx.MockTransport(handler))
    try:
        results_clean = api.fetch_ai_products(search_term="AI", limit=10)
        results_padded = api.fetch_ai_products(search_term=" AI ", limit=10)
    finally:
        api.close()
    assert results_clean == results_padded


def test_rate_limit_parser_parses_full_headers() -> None:
    from ph_ai_tracker.api_client import RateLimitParser

    info = RateLimitParser.parse({
        "X-Rate-Limit-Limit": "100",
        "X-Rate-Limit-Remaining": "42",
        "X-Rate-Limit-Reset": "30",
        "Retry-After": "60",
    })
    assert info.limit == 100
    assert info.remaining == 42
    assert info.reset_seconds == 30
    # reset takes precedence over Retry-After
    assert info.retry_after == 30


def test_rate_limit_parser_fallback_to_retry_after() -> None:
    from ph_ai_tracker.api_client import RateLimitParser

    info = RateLimitParser.parse({"Retry-After": "15"})
    assert info.retry_after == 15
    assert info.limit is None


def test_rate_limit_parser_handles_empty_headers() -> None:
    from ph_ai_tracker.api_client import RateLimitParser

    info = RateLimitParser.parse({})
    assert info.limit is None
    assert info.remaining is None
    assert info.reset_seconds is None
    assert info.retry_after is None


def test_rate_limit_parser_ignores_non_integer_values() -> None:
    from ph_ai_tracker.api_client import RateLimitParser

    info = RateLimitParser.parse({"X-Rate-Limit-Limit": "not-a-number"})
    assert info.limit is None


def test_strict_ai_filter_matches_word_boundary_ai() -> None:
    from ph_ai_tracker.api_client import StrictAIFilter

    f = StrictAIFilter()
    assert f.is_match("AI Assistant", ())


def test_strict_ai_filter_rejects_paid_substring() -> None:
    """'paid' contains 'ai' as substring but not at word boundary."""
    from ph_ai_tracker.api_client import StrictAIFilter

    f = StrictAIFilter()
    assert not f.is_match("paid service", ())


def test_strict_ai_filter_matches_llm_abbreviation() -> None:
    from ph_ai_tracker.api_client import StrictAIFilter

    f = StrictAIFilter()
    assert f.is_match("LLM-powered product", ())


def test_strict_ai_filter_matches_via_topic() -> None:
    from ph_ai_tracker.api_client import StrictAIFilter

    f = StrictAIFilter()
    assert f.is_match("Random Name", ("artificial intelligence",))


def test_strict_ai_filter_is_strict_term_recognises_ai() -> None:
    from ph_ai_tracker.api_client import StrictAIFilter

    assert StrictAIFilter.is_strict_term("ai")
    assert StrictAIFilter.is_strict_term("AI")


def test_strict_ai_filter_is_strict_term_rejects_empty() -> None:
    from ph_ai_tracker.api_client import StrictAIFilter

    assert not StrictAIFilter.is_strict_term("")
    assert not StrictAIFilter.is_strict_term("   ")


def test_strict_ai_filter_is_strict_term_rejects_other() -> None:
    from ph_ai_tracker.api_client import StrictAIFilter

    assert not StrictAIFilter.is_strict_term("machine learning")


def test_passes_strict_filter_matches_ai_product() -> None:
    from ph_ai_tracker.api_client import ProductHuntAPI, StrictAIFilter

    p = Product(name="Alpha", tagline="AI copilot")
    assert ProductHuntAPI._passes_strict_filter(p, StrictAIFilter())


def test_passes_strict_filter_rejects_non_ai_product() -> None:
    from ph_ai_tracker.api_client import ProductHuntAPI, StrictAIFilter

    p = Product(name="Budget Planner", tagline="Personal finance tracker")
    assert not ProductHuntAPI._passes_strict_filter(p, StrictAIFilter())


def test_passes_loose_filter_matches_substring() -> None:
    from ph_ai_tracker.api_client import ProductHuntAPI

    p = Product(name="Tracker Pro", tagline="Insights")
    assert ProductHuntAPI._passes_loose_filter(p, "tracker")


def test_passes_loose_filter_rejects_mismatch() -> None:
    from ph_ai_tracker.api_client import ProductHuntAPI

    p = Product(name="Tracker Pro", tagline="Insights")
    assert not ProductHuntAPI._passes_loose_filter(p, "zzz")

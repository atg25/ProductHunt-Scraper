from __future__ import annotations

import json

import httpx

from ph_ai_tracker.models import Product
from ph_ai_tracker.protocols import TaggingService
from ph_ai_tracker.tagging import NoOpTaggingService, UniversalLLMTaggingService


def _json_response(payload: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


def test_noop_satisfies_tagging_service_protocol() -> None:
    assert isinstance(NoOpTaggingService(), TaggingService)


def test_noop_categorize_returns_empty_tuple() -> None:
    assert NoOpTaggingService().categorize(Product(name="X")) == ()


def test_noop_categorize_returns_tuple_type() -> None:
    assert isinstance(NoOpTaggingService().categorize(Product(name="X")), tuple)


def test_noop_categorize_never_raises() -> None:
    service = NoOpTaggingService()
    service.categorize(Product(name="A"))
    service.categorize(Product(name="B", url="https://example.com"))


def test_llm_satisfies_tagging_service_protocol() -> None:
    service = UniversalLLMTaggingService(api_key="k", base_url="https://example.test/v1")
    assert isinstance(service, TaggingService)


def test_llm_returns_parsed_tags_on_valid_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps({"tags": ["AI", "tool", "ai", "this-tag-is-way-too-long-for-us"]})
        return _json_response({"choices": [{"message": {"content": content}}]})

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="X")) == ("ai", "tool")


def test_llm_temperature_is_zero() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": '{"tags":["ai"]}'}}]})

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    service.categorize(Product(name="X"))
    assert seen.get("temperature") == 0


def test_llm_returns_empty_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"error": "bad"}, status_code=500)

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="X")) == ()


def test_llm_returns_empty_on_timeout_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="X")) == ()


def test_llm_returns_empty_on_wrong_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"choices": [{"message": {"content": '{"result":"ok"}'}}]})

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="X")) == ()


def test_llm_returns_empty_on_malformed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"choices": [{"message": {"content": "not json"}}]})

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="X")) == ()


def test_llm_returns_empty_when_tags_not_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"choices": [{"message": {"content": '{"tags":"ai"}'}}]})

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="X")) == ()


def test_llm_timeout_is_finite() -> None:
    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        timeout=12.0,
    )
    assert service.timeout == 12.0


def test_llm_returns_empty_when_tag_is_non_string() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"choices": [{"message": {"content": '{"tags":[1]}'}}]})

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="X")) == ()

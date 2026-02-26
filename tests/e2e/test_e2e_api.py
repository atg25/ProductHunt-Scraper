from __future__ import annotations

import httpx

from fastapi.testclient import TestClient
import pytest

from ph_ai_tracker.scraper import ProductHuntScraper
import ph_ai_tracker.api as api


def _client() -> TestClient:
    return TestClient(api.app)


def test_e2e_api_health_is_ok() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_e2e_api_search_with_scraper_fixture_returns_newsletter(
    tmp_path, monkeypatch: pytest.MonkeyPatch, scraper_html: str,
) -> None:
    db_path = tmp_path / "e2e.db"

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    monkeypatch.setenv("PH_AI_DB_PATH", str(db_path))
    monkeypatch.setattr(api, "build_provider", lambda **_kw: ProductHuntScraper(transport=httpx.MockTransport(_handler)))
    monkeypatch.setattr(api, "build_tagging_service", lambda: api.NoOpTaggingService())

    response = _client().get("/products/search", params={"strategy": "scraper", "q": "AI", "limit": 3})
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) >= {"generated_at", "total_products", "top_tags", "products"}
    assert body["total_products"] >= 1


def test_e2e_api_history_non_empty_after_search(
    tmp_path, monkeypatch: pytest.MonkeyPatch, scraper_html: str,
) -> None:
    db_path = tmp_path / "history.db"

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    monkeypatch.setenv("PH_AI_DB_PATH", str(db_path))
    monkeypatch.setattr(api, "build_provider", lambda **_kw: ProductHuntScraper(transport=httpx.MockTransport(_handler)))
    monkeypatch.setattr(api, "build_tagging_service", lambda: api.NoOpTaggingService())

    search = _client().get("/products/search", params={"strategy": "scraper", "q": "AI", "limit": 2})
    assert search.status_code == 200
    history = _client().get("/products/history", params={"limit": 10})
    assert history.status_code == 200
    assert history.json()["total"] >= 1


def test_e2e_api_bad_strategy_returns_422() -> None:
    response = _client().get("/products/search", params={"strategy": "bad"})
    assert response.status_code == 422


def test_e2e_api_network_failure_returns_503(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "netfail.db"

    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    monkeypatch.setenv("PH_AI_DB_PATH", str(db_path))
    monkeypatch.setattr(api, "build_provider", lambda **_kw: ProductHuntScraper(transport=httpx.MockTransport(_handler)))
    monkeypatch.setattr(api, "build_tagging_service", lambda: api.NoOpTaggingService())

    response = _client().get("/products/search", params={"strategy": "scraper", "q": "AI", "limit": 3})
    assert response.status_code == 503


def test_e2e_api_repeated_history_reads_are_consistent(
    tmp_path, monkeypatch: pytest.MonkeyPatch, scraper_html: str,
) -> None:
    db_path = tmp_path / "consistent.db"

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    monkeypatch.setenv("PH_AI_DB_PATH", str(db_path))
    monkeypatch.setattr(api, "build_provider", lambda **_kw: ProductHuntScraper(transport=httpx.MockTransport(_handler)))
    monkeypatch.setattr(api, "build_tagging_service", lambda: api.NoOpTaggingService())

    assert _client().get("/products/search", params={"strategy": "scraper", "q": "AI", "limit": 2}).status_code == 200

    totals = [_client().get("/products/history", params={"limit": 50}).json()["total"] for _ in range(3)]
    assert totals[0] == totals[1] == totals[2]

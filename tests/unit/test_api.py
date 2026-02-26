from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from ph_ai_tracker.models import Product, TrackerResult
import ph_ai_tracker.api as api


class _FakeProvider:
    source_name = "scraper"

    def __init__(self, result: TrackerResult) -> None:
        self._result = result
        self.calls: list[tuple[str, int]] = []

    def fetch_products(self, *, search_term: str, limit: int):
        self.calls.append((search_term, limit))
        return list(self._result.products)

    def close(self) -> None:
        return None


def _client() -> TestClient:
    return TestClient(api.app)


def _ok_result(count: int = 2) -> TrackerResult:
    products = [Product(name=f"Tool {i}", votes_count=count - i) for i in range(count)]
    return TrackerResult.success(products, source="scraper")


def test_health_returns_ok() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_returns_newsletter_json(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _ok_result(3)
    fake = _FakeProvider(result)
    monkeypatch.setattr(api, "build_provider", lambda **_kw: fake)
    monkeypatch.setattr(api, "build_tagging_service", lambda: api.NoOpTaggingService())
    response = _client().get("/products/search", params={"q": "AI", "limit": 3})
    body = response.json()
    assert response.status_code == 200
    assert set(body.keys()) >= {"generated_at", "total_products", "top_tags", "products"}
    assert body["total_products"] == 3
    assert fake.calls == [("AI", 3)]


def test_search_rejects_out_of_range_limit() -> None:
    response = _client().get("/products/search", params={"limit": 0})
    assert response.status_code == 422


def test_search_rejects_unknown_strategy() -> None:
    response = _client().get("/products/search", params={"strategy": "badbot"})
    assert response.status_code == 422


def test_search_rejects_empty_query() -> None:
    response = _client().get("/products/search", params={"q": ""})
    assert response.status_code == 422


def test_search_tracker_error_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    failed = TrackerResult.failure(source="scraper", error="upstream down")
    monkeypatch.setattr(api, "_fetch_result", lambda **_kw: failed)
    response = _client().get("/products/search", params={"q": "AI", "limit": 10})
    assert response.status_code == 503
    assert "upstream down" in response.json()["detail"]


def test_search_edge_limits_accept_1_and_50(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _ok_result(1)
    monkeypatch.setattr(api, "build_provider", lambda **_kw: _FakeProvider(result))
    monkeypatch.setattr(api, "build_tagging_service", lambda: api.NoOpTaggingService())
    assert _client().get("/products/search", params={"q": "AI", "limit": 1}).status_code == 200
    assert _client().get("/products/search", params={"q": "AI", "limit": 50}).status_code == 200


def test_history_returns_total_and_rows(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "history.db"
    _seed_products_db(db_path, rows=2)
    monkeypatch.setenv("PH_AI_DB_PATH", str(db_path))
    response = _client().get("/products/history")
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 2
    assert len(body["products"]) == 2
    assert set(body["products"][0].keys()) == {"id", "name", "tagline", "votes", "description", "url", "tags", "posted_at", "observed_at"}


def test_history_rejects_out_of_range_limit() -> None:
    assert _client().get("/products/history", params={"limit": 0}).status_code == 422
    assert _client().get("/products/history", params={"limit": 501}).status_code == 422


def test_history_empty_db_returns_zero(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "empty.db"
    _seed_products_db(db_path, rows=0)
    monkeypatch.setenv("PH_AI_DB_PATH", str(db_path))
    response = _client().get("/products/history")
    assert response.status_code == 200
    assert response.json() == {"total": 0, "products": []}


def test_history_db_error_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def _explode(*_args, **_kwargs):
        raise sqlite3.OperationalError("db unavailable")

    monkeypatch.setattr(api, "_read_history_rows", _explode)
    response = _client().get("/products/history")
    assert response.status_code == 503
    assert "db unavailable" in response.json()["detail"]


def test_load_env_file_sets_missing_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=test-key\nCRON_SCHEDULE=\"0 8 * * *\"\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CRON_SCHEDULE", raising=False)
    api._load_env_file(str(env_file))
    assert api.os.environ.get("OPENAI_API_KEY") == "test-key"
    assert api.os.environ.get("CRON_SCHEDULE") == "0 8 * * *"


def test_load_env_file_does_not_override_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    api._load_env_file(str(env_file))
    assert api.os.environ.get("OPENAI_API_KEY") == "from-env"


def _seed_products_db(db_path, *, rows: int) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                tagline     TEXT,
                votes       INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                url         TEXT,
                tags        TEXT,
                posted_at   TEXT,
                observed_at TEXT NOT NULL
            );
            """
        )
        for i in range(rows):
            conn.execute(
                "INSERT INTO products (name, tagline, votes, description, url, tags, posted_at, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"Tool {i}",
                    None,
                    10 + i,
                    f"Desc {i}",
                    f"https://example.com/{i}",
                    '["ai"]',
                    "2026-02-25T12:00:00+00:00",
                    "2026-02-26T08:00:00+00:00",
                ),
            )

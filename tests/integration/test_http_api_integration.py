from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient
import pytest

from ph_ai_tracker.models import Product
import ph_ai_tracker.api as api


class _Provider:
    source_name = "scraper"

    def __init__(self, names: list[str]) -> None:
        self._names = names

    def fetch_products(self, *, search_term: str, limit: int):
        products = [Product(name=name, votes_count=100 - i, url=f"https://example.com/{i}") for i, name in enumerate(self._names)]
        return products[:limit]

    def close(self) -> None:
        return None


def _client() -> TestClient:
    return TestClient(api.app)


def test_search_then_history_round_trip(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "roundtrip.db"
    monkeypatch.setenv("PH_AI_DB_PATH", str(db_path))
    monkeypatch.setattr(api, "build_provider", lambda **_kw: _Provider(["Alpha", "Beta", "Gamma"]))
    monkeypatch.setattr(api, "build_tagging_service", lambda: api.NoOpTaggingService())

    search = _client().get("/products/search", params={"q": "AI", "limit": 3})
    assert search.status_code == 200
    history = _client().get("/products/history", params={"limit": 10})
    assert history.status_code == 200
    body = history.json()
    assert body["total"] == 3
    assert {row["name"] for row in body["products"]} == {"Alpha", "Beta", "Gamma"}


def test_multiple_searches_accumulate_history(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "accumulate.db"
    monkeypatch.setenv("PH_AI_DB_PATH", str(db_path))
    monkeypatch.setattr(api, "build_provider", lambda **_kw: _Provider(["One", "Two", "Three"]))
    monkeypatch.setattr(api, "build_tagging_service", lambda: api.NoOpTaggingService())

    assert _client().get("/products/search", params={"q": "AI", "limit": 2}).status_code == 200
    assert _client().get("/products/search", params={"q": "AI", "limit": 2}).status_code == 200

    history = _client().get("/products/history", params={"limit": 10}).json()
    assert history["total"] == 4


def test_search_error_does_not_write_to_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _ErrorProvider:
        source_name = "scraper"

        def fetch_products(self, *, search_term: str, limit: int):
            raise RuntimeError("boom")

        def close(self) -> None:
            return None

    db_path = tmp_path / "error.db"
    monkeypatch.setenv("PH_AI_DB_PATH", str(db_path))
    monkeypatch.setattr(api, "build_provider", lambda **_kw: _ErrorProvider())
    monkeypatch.setattr(api, "build_tagging_service", lambda: api.NoOpTaggingService())

    response = _client().get("/products/search", params={"q": "AI", "limit": 3})
    assert response.status_code == 503

    history = _client().get("/products/history", params={"limit": 10}).json()
    assert history["total"] == 0


def test_history_reads_real_sqlite_rows(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "seeded.db"
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
        conn.execute(
            "INSERT INTO products (name, tagline, votes, description, url, tags, posted_at, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "Manual",
                "Tag",
                77,
                "Desc",
                "https://example.com/manual",
                '["ai"]',
                "2026-02-25T12:00:00+00:00",
                "2026-02-26T08:00:00+00:00",
            ),
        )

    monkeypatch.setenv("PH_AI_DB_PATH", str(db_path))
    response = _client().get("/products/history", params={"limit": 10})
    assert response.status_code == 200
    row = response.json()["products"][0]
    assert row["name"] == "Manual"
    assert row["votes"] == 77

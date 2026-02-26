"""Unit tests for the simplified SQLiteStore."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import unittest.mock as mock

import pytest

from ph_ai_tracker.models import Product, TrackerResult
from ph_ai_tracker.storage import SQLiteStore
from ph_ai_tracker.exceptions import StorageError


def test_init_db_creates_products_table(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "products" in tables
    assert "runs" not in tables
    assert "product_snapshots" not in tables


def test_save_success_inserts_product_rows(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()
    result = TrackerResult.success(
        [
            Product(name="AlphaAI", url="https://example.com/a", votes_count=10),
            Product(name="BetaAI", url="https://example.com/b", votes_count=5),
        ],
        source="scraper",
        search_term="AI",
        limit=10,
    )
    n = store.save_result(result)

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert n == 2
    assert count == 2


def test_save_failure_inserts_no_rows(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()
    result = TrackerResult.failure(
        source="api", error="Missing api_token", search_term="AI", limit=10
    )
    n = store.save_result(result)

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert n == 0
    assert count == 0


def test_each_run_appends_new_rows(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()
    p = Product(name="AlphaAI", url="https://example.com/a", votes_count=1)
    store.save_result(TrackerResult.success([p], source="scraper", search_term="AI", limit=10))
    p2 = Product(name="AlphaAI", url="https://example.com/a", votes_count=99)
    store.save_result(TrackerResult.success([p2], source="scraper", search_term="AI", limit=10))

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert count == 2, "No deduplication -- every observation is its own row"


def test_correct_columns_persisted(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()
    p = Product(
        name="Tool",
        tagline="Tagline here",
        description="Full description",
        url="https://example.com/tool",
        tags=("ai", "developer-tools"),
        votes_count=77,
        posted_at=datetime(2026, 2, 25, 12, 0, 0, tzinfo=timezone.utc),
    )
    store.save_result(TrackerResult.success([p], source="api", search_term="AI", limit=10))

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        row = conn.execute(
            "SELECT name, tagline, votes, description, url, tags, posted_at FROM products"
        ).fetchone()
    assert row == (
        "Tool",
        "Tagline here",
        77,
        "Full description",
        "https://example.com/tool",
        '["ai", "developer-tools"]',
        "2026-02-25T12:00:00+00:00",
    )


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    store.init_db()
    store.init_db()
    with sqlite3.connect(tmp_path / "t.db") as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "products" in tables


def test_db_path_parent_dir_created_automatically(tmp_path: Path) -> None:
    deep_path = tmp_path / "nested" / "dir" / "tracker.db"
    store = SQLiteStore(deep_path)
    store.init_db()
    assert deep_path.exists()


def test_save_result_raises_storage_error_on_db_failure(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()
    with mock.patch.object(store, "_connect", side_effect=sqlite3.Error("boom")):
        with pytest.raises(StorageError):
            store.save_result(
                TrackerResult.success(
                    [Product(name="X")], source="scraper", search_term="AI", limit=10
                )
            )

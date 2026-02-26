"""Integration tests for the simplified SQLiteStore — single products table."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from ph_ai_tracker.models import Product, TrackerResult
from ph_ai_tracker.storage import SQLiteStore


def test_schema_has_only_products_table(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    user_tables = tables - {"sqlite_sequence"}  # sqlite_sequence is an internal SQLite table
    assert user_tables == {"products"}, f"unexpected tables: {user_tables - {'products'}}"


def test_products_table_columns(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(products)").fetchall()
        }

    assert {"id", "name", "tagline", "votes", "description", "url", "tags", "posted_at", "observed_at"} <= cols


def test_save_result_inserts_all_products(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()

    products = [
        Product(name=f"Prod{i}", url=f"https://example.com/{i}", votes_count=i * 10)
        for i in range(1, 6)
    ]
    result = TrackerResult.success(products, source="scraper", search_term="AI", limit=10)
    n = store.save_result(result)

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    assert n == 5
    assert count == 5


def test_observed_at_is_iso_timestamp(tmp_path: Path) -> None:
    import re

    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()
    p = Product(name="Alpha", url="https://example.com/a", votes_count=3)
    store.save_result(TrackerResult.success([p], source="scraper", search_term="AI", limit=10))

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        ts = conn.execute("SELECT observed_at FROM products").fetchone()[0]

    iso_re = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
    assert iso_re.match(ts), f"observed_at is not ISO format: {ts!r}"


def test_multiple_runs_accumulate_rows(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()

    p = Product(name="Alpha", url="https://example.com/a", votes_count=1)
    for _ in range(3):
        store.save_result(TrackerResult.success([p], source="scraper", search_term="AI", limit=10))

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    assert count == 3


def test_failure_result_writes_zero_rows(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "tracker.db")
    store.init_db()
    result = TrackerResult.failure(source="api", error="timeout", search_term="AI", limit=10)
    n = store.save_result(result)

    with sqlite3.connect(tmp_path / "tracker.db") as conn:
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    assert n == 0
    assert count == 0

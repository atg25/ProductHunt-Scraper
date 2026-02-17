from __future__ import annotations

from pathlib import Path
import sqlite3

from ph_ai_tracker.models import Product, TrackerResult
from ph_ai_tracker.storage import SQLiteStore


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])


def test_init_db_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "tracker.db"
    store = SQLiteStore(db_path)

    store.init_db()

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert "runs" in tables
    assert "products" in tables
    assert "product_snapshots" in tables


def test_save_success_persists_run_products_and_snapshots(tmp_path: Path) -> None:
    db_path = tmp_path / "tracker.db"
    store = SQLiteStore(db_path)

    result = TrackerResult.success(
        [
            Product(name="AlphaAI", url="https://example.com/a", votes_count=10, topics=("AI",)),
            Product(name="BetaAI", url="https://example.com/b", votes_count=5, topics=("ML",)),
        ],
        source="scraper",
    )

    run_id = store.save_result(result, search_term="AI", limit=20)

    with sqlite3.connect(db_path) as conn:
        assert run_id > 0
        assert _count(conn, "runs") == 1
        assert _count(conn, "products") == 2
        assert _count(conn, "product_snapshots") == 2

        run_row = conn.execute("SELECT status, error, source FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert run_row == ("success", None, "scraper")


def test_save_failure_persists_run_without_product_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "tracker.db"
    store = SQLiteStore(db_path)

    result = TrackerResult.failure(source="api", error="Missing api_token")
    run_id = store.save_result(result, search_term="AI", limit=10)

    with sqlite3.connect(db_path) as conn:
        assert run_id > 0
        assert _count(conn, "runs") == 1
        assert _count(conn, "products") == 0
        assert _count(conn, "product_snapshots") == 0

        run_row = conn.execute("SELECT status, error FROM runs WHERE id = ?", (run_id,)).fetchone()
        assert run_row == ("failure", "Missing api_token")


def test_upsert_dedupes_products_across_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "tracker.db"
    store = SQLiteStore(db_path)

    first = TrackerResult.success(
        [Product(name="AlphaAI", url="https://example.com/a", votes_count=1)],
        source="scraper",
    )
    second = TrackerResult.success(
        [Product(name="AlphaAI Updated", url="https://example.com/a", votes_count=99)],
        source="scraper",
    )

    store.save_result(first, search_term="AI", limit=10)
    store.save_result(second, search_term="AI", limit=10)

    with sqlite3.connect(db_path) as conn:
        assert _count(conn, "runs") == 2
        assert _count(conn, "products") == 1
        assert _count(conn, "product_snapshots") == 2

        name_row = conn.execute("SELECT name FROM products").fetchone()
        assert name_row is not None
        assert name_row[0] == "AlphaAI Updated"

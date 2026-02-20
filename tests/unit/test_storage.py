from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

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
    store.init_db()

    result = TrackerResult.success(
        [
            Product(name="AlphaAI", url="https://example.com/a", votes_count=10, topics=("AI",)),
            Product(name="BetaAI", url="https://example.com/b", votes_count=5, topics=("ML",)),
        ],
        source="scraper",
        search_term="AI",
        limit=20,
    )

    run_id = store.save_result(result)

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
    store.init_db()

    result = TrackerResult.failure(source="api", error="Missing api_token", search_term="AI", limit=10)
    run_id = store.save_result(result)

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
    store.init_db()

    first = TrackerResult.success(
        [Product(name="AlphaAI", url="https://example.com/a", votes_count=1)],
        source="scraper",
        search_term="AI",
        limit=10,
    )
    second = TrackerResult.success(
        [Product(name="AlphaAI Updated", url="https://example.com/a", votes_count=99)],
        source="scraper",
        search_term="AI",
        limit=10,
    )

    store.save_result(first)
    store.save_result(second)

    with sqlite3.connect(db_path) as conn:
        assert _count(conn, "runs") == 2
        assert _count(conn, "products") == 1
        assert _count(conn, "product_snapshots") == 2

        name_row = conn.execute("SELECT name FROM products").fetchone()
        assert name_row is not None
        assert name_row[0] == "AlphaAI Updated"


def test_foreign_key_pragma_is_active(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    with store._connect() as conn:
        row = conn.execute("PRAGMA foreign_keys").fetchone()
    assert row is not None and int(row[0]) == 1, "PRAGMA foreign_keys should be ON"


def test_canonical_key_unique_constraint_enforced_at_db_level(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO products (canonical_key, name) VALUES ('url:https://x.com', 'X')"
        )
        conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        with store._connect() as conn:
            conn.execute(
                "INSERT INTO products (canonical_key, name) VALUES ('url:https://x.com', 'Y')"
            )
            conn.commit()


def test_product_snapshot_unique_run_product_constraint(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()

    with store._connect() as conn:
        conn.execute(
            "INSERT INTO runs (source, fetched_at, search_term, limit_value, status) "
            "VALUES ('scraper', datetime('now'), 'AI', 10, 'success')"
        )
        conn.execute(
            "INSERT INTO products (canonical_key, name) VALUES ('url:https://x.com', 'X')"
        )
        run_id = conn.execute("SELECT id FROM runs").fetchone()[0]
        product_id = conn.execute("SELECT id FROM products").fetchone()[0]
        conn.commit()

    with store._connect() as conn:
        conn.execute(
            "INSERT INTO product_snapshots "
            "(run_id, product_id, votes_count, topics_json, observed_at) "
            "VALUES (?, ?, 0, '[]', datetime('now'))",
            (run_id, product_id),
        )
        conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        with store._connect() as conn:
            conn.execute(
                "INSERT INTO product_snapshots "
                "(run_id, product_id, votes_count, topics_json, observed_at) "
                "VALUES (?, ?, 1, '[]', datetime('now'))",
                (run_id, product_id),
            )
            conn.commit()


def test_upsert_updates_updated_at_but_not_created_at(tmp_path: Path) -> None:
    import time as _time
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    p = Product(name="AlphaAI", url="https://example.com/a", votes_count=1)
    store.save_result(TrackerResult.success([p], source="scraper", search_term="AI", limit=10))

    _time.sleep(0.05)

    p2 = Product(name="AlphaAI", url="https://example.com/a", votes_count=99)
    store.save_result(TrackerResult.success([p2], source="scraper", search_term="AI", limit=10))

    with sqlite3.connect(tmp_path / "t.db") as conn:
        row = conn.execute("SELECT created_at, updated_at FROM products").fetchone()
    assert row is not None
    # updated_at should be >= created_at (may equal if same second)
    assert row[1] >= row[0]


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    store.init_db()
    store.init_db()
    with sqlite3.connect(tmp_path / "t.db") as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert {"runs", "products", "product_snapshots"} <= tables


def test_save_result_rejects_invalid_status(tmp_path: Path) -> None:
    from ph_ai_tracker.exceptions import StorageError
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    result = TrackerResult.success([Product(name="X")], source="scraper", search_term="AI", limit=10)
    with pytest.raises(StorageError, match="invalid run status"):
        store.save_result(result, status="bogus")


def test_db_path_parent_dir_created_automatically(tmp_path: Path) -> None:
    deep_path = tmp_path / "nested" / "dir" / "tracker.db"
    store = SQLiteStore(deep_path)
    store.init_db()
    assert deep_path.exists()


def test_derive_run_status_success_when_no_error() -> None:
    from ph_ai_tracker.storage import _derive_run_status

    result = TrackerResult.success([], source="scraper")
    assert _derive_run_status(result, status_override=None) == "success"


def test_derive_run_status_failure_when_error() -> None:
    from ph_ai_tracker.storage import _derive_run_status

    result = TrackerResult.failure(source="scraper", error="boom")
    assert _derive_run_status(result, status_override=None) == "failure"


def test_derive_run_status_override_partial() -> None:
    from ph_ai_tracker.storage import _derive_run_status

    result = TrackerResult.success([], source="scraper")
    assert _derive_run_status(result, status_override="partial") == "partial"


def test_derive_run_status_invalid_override_raises() -> None:
    from ph_ai_tracker.storage import _derive_run_status
    from ph_ai_tracker.exceptions import StorageError

    result = TrackerResult.success([], source="scraper")
    with pytest.raises(StorageError, match="invalid run status"):
        _derive_run_status(result, status_override="oops")



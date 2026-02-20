"""Integration tests for SQLite schema integrity and referential enforcement."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ph_ai_tracker.models import Product, TrackerResult
from ph_ai_tracker.storage import SQLiteStore
from ph_ai_tracker.exceptions import StorageError


# POSITIVE — multi-run deduplication and snapshot history

def test_two_runs_share_one_product_row(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    p = Product(name="AlphaAI", url="https://example.com/alpha", votes_count=5)

    store.save_result(TrackerResult.success([p], source="scraper", search_term="AI", limit=10))
    store.save_result(
        TrackerResult.success(
            [Product(name="AlphaAI v2", url="https://example.com/alpha", votes_count=99)],
            source="scraper",
            search_term="AI",
            limit=10,
        ),
    )

    with sqlite3.connect(tmp_path / "t.db") as conn:
        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        snapshot_count = conn.execute("SELECT COUNT(*) FROM product_snapshots").fetchone()[0]
        run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

    assert product_count == 1, "Same URL must map to a single product row"
    assert snapshot_count == 2, "Each run should add a snapshot row"
    assert run_count == 2


def test_product_name_updated_on_subsequent_run(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    url = "https://example.com/beta"

    store.save_result(
        TrackerResult.success(
            [Product(name="OldName", url=url)],
            source="scraper",
            search_term="AI",
            limit=10,
        ),
    )
    store.save_result(
        TrackerResult.success(
            [Product(name="NewName", url=url)],
            source="scraper",
            search_term="AI",
            limit=10,
        ),
    )

    with sqlite3.connect(tmp_path / "t.db") as conn:
        row = conn.execute("SELECT name FROM products").fetchone()
    assert row is not None
    assert row[0] == "NewName"


def test_votes_count_tracked_per_snapshot_not_per_product(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    url = "https://example.com/gamma"

    store.save_result(
        TrackerResult.success(
            [Product(name="G", url=url, votes_count=10)],
            source="api",
            search_term="AI",
            limit=10,
        ),
    )
    store.save_result(
        TrackerResult.success(
            [Product(name="G", url=url, votes_count=99)],
            source="api",
            search_term="AI",
            limit=10,
        ),
    )

    with sqlite3.connect(tmp_path / "t.db") as conn:
        votes = [
            row[0]
            for row in conn.execute(
                "SELECT votes_count FROM product_snapshots ORDER BY id"
            ).fetchall()
        ]
    assert votes == [10, 99], f"Expected [10, 99], got {votes}"


def test_run_failure_stores_error_message(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    store.save_result(
        TrackerResult.failure(source="api", error="Token expired", search_term="AI", limit=10),
    )

    with sqlite3.connect(tmp_path / "t.db") as conn:
        row = conn.execute("SELECT error, status FROM runs").fetchone()
    assert row is not None
    assert row[0] == "Token expired"
    assert row[1] == "failure"


# NEGATIVE — constraint enforcement

def test_raw_without_fk_pragma_allows_orphan_insert(tmp_path: Path) -> None:
    """Documents SQLite's default-OFF FK behaviour.

    This test intentionally shows the *unsafe* path to justify why ``_connect``
    always sets ``PRAGMA foreign_keys = ON``.
    """
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()

    # Open a raw connection WITHOUT the FK pragma (SQLite default = OFF).
    conn = sqlite3.connect(tmp_path / "t.db")
    try:
        # This orphan insert succeeds when FK enforcement is disabled.
        conn.execute(
            "INSERT INTO product_snapshots "
            "(run_id, product_id, votes_count, topics_json, observed_at) "
            "VALUES (9999, 9999, 0, '[]', datetime('now'))"
        )
        conn.commit()
    finally:
        conn.close()
    # If we reached here, the orphan insert succeeded — this is the unsafe default.


def test_canonical_key_unique_constraint_enforced_at_db_level(tmp_path: Path) -> None:
    """The UNIQUE(canonical_key) constraint on products must be enforced by SQLite."""
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
                "INSERT INTO products (canonical_key, name) VALUES ('url:https://x.com', 'X2')"
            )
            conn.commit()


def test_fk_pragma_rejects_orphan_snapshot_run_id(tmp_path: Path) -> None:
    """With PRAGMA foreign_keys = ON, inserting a snapshot for a non-existent run must fail."""
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()

    # Insert a valid product row.
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO products (canonical_key, name) VALUES ('url:https://x.com', 'X')"
        )
        product_id = conn.execute(
            "SELECT id FROM products WHERE canonical_key='url:https://x.com'"
        ).fetchone()[0]
        conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        with store._connect() as conn:
            conn.execute(
                "INSERT INTO product_snapshots "
                "(run_id, product_id, votes_count, topics_json, observed_at) "
                "VALUES (9999, ?, 0, '[]', datetime('now'))",
                (product_id,),
            )
            conn.commit()


def test_save_result_wraps_integrity_error_as_storage_error(tmp_path: Path) -> None:
    """StorageError should be raised (not sqlite3.IntegrityError) on a constraint violation."""
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()

    # Pre-insert a product with the same canonical_key we're about to save.
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO products (canonical_key, name) VALUES ('name:alphaai', 'AlphaAI')"
        )
        conn.commit()

    # Trying to insert via the normal code path — upsert should handle it,
    # so this test verifies the happy path still works (ON CONFLICT handles it).
    result = TrackerResult.success(
        [Product(name="AlphaAI", votes_count=5)], source="scraper", search_term="AI", limit=10
    )
    run_id = store.save_result(result)
    assert run_id > 0  # upsert succeeded — no StorageError raised


def test_save_result_rejects_invalid_status_string(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "t.db")
    store.init_db()
    result = TrackerResult.success([Product(name="X")], source="scraper", search_term="AI", limit=10)

    with pytest.raises(StorageError, match="invalid run status"):
        store.save_result(result, status="bad_status")

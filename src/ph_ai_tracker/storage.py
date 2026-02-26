"""SQLite-backed persistence layer for ph_ai_tracker.

Simple single-table schema: one row per product observed per run.
Every call to ``save_result`` inserts one row per product with the
name, tagline, votes, description, url, and observed_at timestamp.
There is no deduplication — each scrape is an independent snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from .exceptions import StorageError
from .models import TrackerResult


_SCHEMA = """
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

CREATE INDEX IF NOT EXISTS idx_products_observed_at ON products(observed_at DESC);
"""


class SQLiteStore:
    """Persists product observations to a local SQLite database.

    Each call to ``save_result`` inserts one row per product fetched.
    Every row is an independent observation — there is no deduplication.
    To see how a product's vote count changed over time, query all rows
    with the same url ordered by observed_at.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def init_db(self) -> None:
        """Create the database schema if it does not already exist.

        Idempotent: safe to call multiple times. All ``CREATE`` statements use
        ``IF NOT EXISTS`` so repeated calls have no effect on an already
        initialised database.
        """
        self._ensure_parent_dir()
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
                self._ensure_posted_at_column(conn)
                self._ensure_tags_column(conn)
        except sqlite3.Error as exc:
            raise StorageError(f"failed to initialize database: {exc}") from exc

    def save_result(self, result: TrackerResult) -> int:
        """Insert one row per product in result; return the number of rows inserted.

        Returns 0 without writing anything when result.error is not None.
        """
        if result.error is not None:
            return 0
        observed_at = result.fetched_at.isoformat()
        try:
            with self._connect() as conn:
                count = self._insert_products(conn, result.products, observed_at)
                conn.commit()
            return count
        except sqlite3.Error as exc:
            raise StorageError(f"failed to save tracker result: {exc}") from exc

    def _insert_products(self, conn: sqlite3.Connection, products, observed_at: str) -> int:
        """Insert all products and return the row count."""
        for product in products:
            conn.execute(
                """
                INSERT INTO products (name, tagline, votes, description, url, tags, posted_at, observed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (product.name, product.tagline, int(product.votes_count),
                 product.description, product.url,
                 json.dumps(list(product.tags)),
                 product.posted_at.isoformat() if product.posted_at else None,
                 observed_at),
            )
        return len(products)

    @staticmethod
    def _ensure_posted_at_column(conn: sqlite3.Connection) -> None:
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(products)").fetchall()
        }
        if "posted_at" not in cols:
            conn.execute("ALTER TABLE products ADD COLUMN posted_at TEXT")

    @staticmethod
    def _ensure_tags_column(conn: sqlite3.Connection) -> None:
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(products)").fetchall()
        }
        if "tags" not in cols:
            conn.execute("ALTER TABLE products ADD COLUMN tags TEXT")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_parent_dir(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

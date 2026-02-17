from __future__ import annotations

from pathlib import Path
import json
import sqlite3

from .exceptions import StorageError
from .models import Product, TrackerResult


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    search_term TEXT NOT NULL,
    limit_value INTEGER NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS product_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    tagline TEXT,
    description TEXT,
    votes_count INTEGER NOT NULL,
    topics_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id),
    FOREIGN KEY(product_id) REFERENCES products(id),
    UNIQUE(run_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_fetched_at ON runs(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_run ON product_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_product ON product_snapshots(product_id);
"""


class SQLiteStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def init_db(self) -> None:
        self._ensure_parent_dir()
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise StorageError(f"failed to initialize database: {exc}") from exc

    def save_result(
        self,
        result: TrackerResult,
        *,
        search_term: str,
        limit: int,
        status: str | None = None,
    ) -> int:
        self.init_db()
        status_value = status or ("success" if result.error is None else "failure")
        if status_value not in {"success", "partial", "failure"}:
            raise StorageError(f"invalid run status: {status_value}")

        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO runs (source, fetched_at, search_term, limit_value, status, error)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.source,
                        result.fetched_at.isoformat(),
                        str(search_term),
                        int(limit),
                        status_value,
                        result.error,
                    ),
                )
                run_id = int(cursor.lastrowid)

                if result.error is None:
                    for product in result.products:
                        product_id = self._upsert_product(conn, product)
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO product_snapshots
                            (run_id, product_id, tagline, description, votes_count, topics_json, observed_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                run_id,
                                product_id,
                                product.tagline,
                                product.description,
                                int(product.votes_count),
                                self._topics_json(product),
                                result.fetched_at.isoformat(),
                            ),
                        )

                conn.commit()
                return run_id
        except sqlite3.Error as exc:
            raise StorageError(f"failed to save tracker result: {exc}") from exc

    def _upsert_product(self, conn: sqlite3.Connection, product: Product) -> int:
        key = self._canonical_key(product)
        conn.execute(
            """
            INSERT INTO products (canonical_key, name, url)
            VALUES (?, ?, ?)
            ON CONFLICT(canonical_key) DO UPDATE SET
                name=excluded.name,
                url=excluded.url,
                updated_at=datetime('now')
            """,
            (key, product.name, product.url),
        )

        row = conn.execute("SELECT id FROM products WHERE canonical_key = ?", (key,)).fetchone()
        if row is None:
            raise StorageError("failed to resolve product id after upsert")
        return int(row[0])

    @staticmethod
    def _canonical_key(product: Product) -> str:
        if product.url and product.url.strip():
            return f"url:{product.url.strip().lower()}"
        return f"name:{product.name.strip().lower()}"

    @staticmethod
    def _topics_json(product: Product) -> str:
        return json.dumps(list(product.topics), ensure_ascii=False)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _ensure_parent_dir(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

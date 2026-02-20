"""SQLite-backed persistence layer for ph_ai_tracker.

The schema is intentionally simple: three tables that capture the full
audit history of every tracker run.

* ``runs``             — one row per ``get_products()`` call.
* ``products``         — one row per *unique* product (canonical key = URL or name).
* ``product_snapshots`` — one row per (run, product) pair; records the
  observed votes/tagline/description at that point in time.

The database is the **ultimate arbiter of product uniqueness**.  The
``UNIQUE(canonical_key)`` constraint on ``products`` and the ``ON CONFLICT``
clause in every upsert mean that Python code never decides whether two
products are the same — the database does.
"""

from __future__ import annotations

from pathlib import Path
import json
import sqlite3

from .exceptions import StorageError
from .models import Product, TrackerResult


_SQL_UPSERT_PRODUCT = (
    "INSERT INTO products (canonical_key, name, url) VALUES (?, ?, ?) "
    "ON CONFLICT(canonical_key) DO UPDATE SET "
    "name=excluded.name, url=excluded.url, updated_at=datetime('now')"
)
_SQL_SELECT_PRODUCT = "SELECT id FROM products WHERE canonical_key = ?"


def _derive_run_status(result: TrackerResult, *, status_override: str | None) -> str:
    """Return the canonical run status string for *result*.

    Uses *status_override* when explicitly provided; otherwise ``'success'``
    when there is no error and ``'failure'`` otherwise.

    Raises:
        StorageError: If *status_override* is not one of the three allowed
            values (``'success'``, ``'partial'``, ``'failure'``).
    """
    if status_override is not None:
        if status_override not in {"success", "partial", "failure"}:
            raise StorageError(f"invalid run status: {status_override}")
        return status_override
    return "success" if result.error is None else "failure"


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
    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE RESTRICT,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE RESTRICT,
    UNIQUE(run_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_fetched_at ON runs(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_run ON product_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_product ON product_snapshots(product_id);
"""


class SQLiteStore:
    """Persists tracker run results to a local SQLite database.

    The ``canonical_key`` column on the ``products`` table is the single
    source of truth for product identity.  A key is derived from the
    product URL (preferred) or its name (fallback).  Two products with the
    same canonical key are the *same* product across runs — only a new
    snapshot row is added, the ``products`` row is updated in-place.

    ``PRAGMA foreign_keys = ON`` is set on every connection, so::

        INSERT INTO product_snapshots (run_id=9999, …)   ← 9999 doesn't exist

    will raise ``sqlite3.IntegrityError``, which is caught and re-raised as
    ``StorageError``.
    """
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def init_db(self) -> None:
        """Create the database schema if it does not already exist.

        Idempotent: safe to call multiple times.  All ``CREATE`` statements use
        ``IF NOT EXISTS`` so repeated calls have no effect on an already
        initialised database.
        """
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
        status: str | None = None,
    ) -> int:
        """Persist a tracker result; return the newly created run ID."""
        status_value = _derive_run_status(result, status_override=status)
        try:
            with self._connect() as conn:
                run_id = self._commit_run(conn, result, status_value)
            return run_id
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"integrity violation during save: {exc}") from exc
        except sqlite3.Error as exc:
            raise StorageError(f"failed to save tracker result: {exc}") from exc

    def _commit_run(
        self, conn: sqlite3.Connection, result: TrackerResult,
        status: str,
    ) -> int:
        """Insert the run record and all snapshots, then commit; return run ID."""
        run_id = self._insert_run_record(conn, result, status)
        if result.error is None:
            self._insert_all_snapshots(conn, run_id, result.products, result.fetched_at.isoformat())
        conn.commit()
        return run_id

    def _insert_run_record(
        self,
        conn: sqlite3.Connection,
        result: TrackerResult,
        status: str,
    ) -> int:
        """Insert a row into ``runs`` and return the new ``id``."""
        values = (result.source, result.fetched_at.isoformat(), str(result.search_term), int(result.limit), status, result.error)
        cursor = conn.execute(
            """
            INSERT INTO runs (source, fetched_at, search_term, limit_value, status, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        return int(cursor.lastrowid)

    def _insert_product_snapshot(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        product_id: int,
        product: Product,
        fetched_at: str,
    ) -> None:
        """Insert a single ``product_snapshots`` row."""
        conn.execute(
            """
            INSERT OR REPLACE INTO product_snapshots
            (run_id, product_id, tagline, description, votes_count, topics_json, observed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, product_id, product.tagline, product.description,
             int(product.votes_count), self._topics_json(product), fetched_at),
        )

    def _insert_all_snapshots(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        products: list[Product],
        fetched_at: str,
    ) -> None:
        """Upsert every product in *products* and record a snapshot row."""
        for product in products:
            product_id = self._upsert_product(conn, product)
            self._insert_product_snapshot(conn, run_id, product_id, product, fetched_at)

    def _upsert_product(self, conn: sqlite3.Connection, product: Product) -> int:
        """ON CONFLICT upsert *product* and return its database ``id``."""
        key = self._canonical_key(product)
        conn.execute(_SQL_UPSERT_PRODUCT, (key, product.name, product.url))
        row = conn.execute(_SQL_SELECT_PRODUCT, (key,)).fetchone()
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

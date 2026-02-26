from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query

from .bootstrap import build_provider, build_tagging_service
from .constants import DEFAULT_DB_PATH, DEFAULT_LIMIT, DEFAULT_SEARCH_TERM
from .formatters import NewsletterFormatter
from .storage import SQLiteStore
from .tagging import NoOpTaggingService
from .tracker import AIProductTracker

app = FastAPI(title="ph_ai_tracker API", version="1.0.0")


def _load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists() or not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        cleaned = value.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"\"", "'"}:
            cleaned = cleaned[1:-1]
        os.environ[key] = cleaned


_load_env_file()


def _db_path() -> str:
    return os.environ.get("PH_AI_DB_PATH", DEFAULT_DB_PATH)


def _api_token() -> str | None:
    token = os.environ.get("PRODUCTHUNT_TOKEN")
    return token if token and token.strip() else None


def _fetch_result(*, strategy: str, search_term: str, limit: int):
    provider = build_provider(strategy=strategy, api_token=_api_token())
    tagger = build_tagging_service() or NoOpTaggingService()
    tracker = AIProductTracker(provider=provider, tagging_service=tagger)
    return tracker.get_products(search_term=search_term, limit=limit)


def _persist_result(result) -> None:
    store = SQLiteStore(_db_path())
    store.init_db()
    store.save_result(result)


def _read_history_rows(*, db_path: str, limit: int) -> list[dict[str, object]]:
    store = SQLiteStore(db_path)
    store.init_db()
    with store._connect() as conn:
        cursor = conn.execute(
            "SELECT id, name, tagline, votes, description, url, tags, posted_at, observed_at "
            "FROM products ORDER BY observed_at DESC, id DESC LIMIT ?",
            (limit,),
        )
        columns = [col[0] for col in (cursor.description or ())]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/products/search")
def products_search(
    q: Annotated[str, Query(min_length=1, max_length=100)] = DEFAULT_SEARCH_TERM,
    limit: Annotated[int, Query(ge=1, le=50)] = DEFAULT_LIMIT,
    strategy: Annotated[Literal["auto", "scraper", "api"], Query()] = "auto",
) -> dict[str, object]:
    try:
        result = _fetch_result(strategy=strategy, search_term=q, limit=limit)
        if result.error is not None:
            raise HTTPException(status_code=503, detail=result.error)
        _persist_result(result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return NewsletterFormatter().format(list(result.products), datetime.now(timezone.utc))


@app.get("/products/history")
def products_history(limit: Annotated[int, Query(ge=1, le=500)] = 50) -> dict[str, object]:
    try:
        rows = _read_history_rows(db_path=_db_path(), limit=limit)
    except (sqlite3.Error, OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"total": len(rows), "products": rows}

"""Shared CLI argument definitions for ph_ai_tracker.

Both ``__main__.py`` and ``scheduler.py`` expose the same five common
arguments (``--strategy``, ``--search``, ``--limit``, ``--db-path``,
``--token``).  This module is the single source of truth for those argument
names, their corresponding environment variables, and their defaults.

Provider construction is handled by ``bootstrap.build_provider``.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from .constants import DEFAULT_LIMIT, DEFAULT_SEARCH_TERM

# Environment variable names — ONE place, never repeated
_ENV_STRATEGY = "PH_AI_TRACKER_STRATEGY"
_ENV_SEARCH   = "PH_AI_TRACKER_SEARCH"
_ENV_LIMIT    = "PH_AI_TRACKER_LIMIT"
_ENV_DB_PATH  = "PH_AI_DB_PATH"
_ENV_TOKEN    = "PRODUCTHUNT_TOKEN"

_DEFAULT_STRATEGY = "scraper"
_DEFAULT_DB_PATH  = "./data/ph_ai_tracker.db"


def _add_strategy_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--strategy",
        choices=["api", "scraper", "auto"],
        default=os.environ.get(_ENV_STRATEGY, _DEFAULT_STRATEGY),
        help="Data-retrieval strategy (default: scraper or PH_AI_TRACKER_STRATEGY)",
    )


def _add_search_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--search",
        default=os.environ.get(_ENV_SEARCH, DEFAULT_SEARCH_TERM),
        help="Client-side keyword filter (default: AI or PH_AI_TRACKER_SEARCH)",
    )


def _add_limit_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get(_ENV_LIMIT, str(DEFAULT_LIMIT))),
        help="Max products to return (default: 20 or PH_AI_TRACKER_LIMIT)",
    )


def _add_db_path_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db-path",
        default=os.environ.get(_ENV_DB_PATH, _DEFAULT_DB_PATH),
        help="SQLite database path (default: ./data/ph_ai_tracker.db or PH_AI_DB_PATH)",
    )


def _add_token_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--token",
        default=os.environ.get(_ENV_TOKEN),
        help="Product Hunt API token (or set PRODUCTHUNT_TOKEN)",
    )


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the five shared tracker arguments to *parser*.

    Defaults are resolved from environment variables at call time, so tests
    can monkeypatch env before calling this to control behaviour.
    """
    _add_strategy_argument(parser)
    _add_search_argument(parser)
    _add_limit_argument(parser)
    _add_db_path_argument(parser)
    _add_token_argument(parser)


@dataclass(frozen=True, slots=True)
class CommonArgs:
    """Typed, validated view of the five common CLI arguments."""

    strategy:    str
    search_term: str
    limit:       int
    db_path:     str
    api_token:   str | None

    @staticmethod
    def from_namespace(ns: argparse.Namespace) -> "CommonArgs":
        """Build a ``CommonArgs`` from a parsed ``argparse.Namespace``."""
        return CommonArgs(
            strategy=ns.strategy,
            search_term=ns.search,
            limit=max(int(ns.limit), 1),
            db_path=ns.db_path,
            api_token=ns.token or None,
        )

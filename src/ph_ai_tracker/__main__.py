from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from .bootstrap import build_provider, build_tagging_service
from .cli import add_common_arguments, CommonArgs
from .exceptions import StorageError
from .formatters import NewsletterFormatter
from .storage import SQLiteStore
from .tracker import AIProductTracker


def _try_persist(result, common: CommonArgs) -> int | None:
    """Persist result to SQLite; return 3 on StorageError, else None."""
    try:
        store = SQLiteStore(common.db_path)
        store.init_db()
        store.save_result(result)
        return None
    except StorageError as exc:
        sys.stderr.write(f"failed to persist run: {exc}\n")
        return 3


def _fetch_result(common: CommonArgs):
    """Build provider and fetch products; never raises."""
    provider = build_provider(strategy=common.strategy, api_token=common.api_token)
    tagging_service = build_tagging_service()
    return AIProductTracker(provider=provider, tagging_service=tagging_service).get_products(
        search_term=common.search_term, limit=common.limit
    )


def _write_newsletter(result) -> None:
    """Serialise result as newsletter JSON and write to stdout."""
    newsletter = NewsletterFormatter().format(list(result.products), datetime.now(timezone.utc))
    sys.stdout.write(json.dumps(newsletter) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Fetch AI products and optionally persist the result."""
    parser = argparse.ArgumentParser(prog="ph_ai_tracker", description="Fetch AI products from Product Hunt.")
    add_common_arguments(parser)
    parser.add_argument("--no-persist", action="store_true", help="Skip writing run results to SQLite")
    args = parser.parse_args(argv)
    common = CommonArgs.from_namespace(args)
    result = _fetch_result(common)
    if not args.no_persist:
        code = _try_persist(result, common)
        if code is not None:
            _write_newsletter(result)
            return code
    _write_newsletter(result)
    return 0 if result.error is None else 2


if __name__ == "__main__":
    raise SystemExit(main())

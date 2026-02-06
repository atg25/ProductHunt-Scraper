from __future__ import annotations

import argparse
import os
import sys

from .tracker import AIProductTracker


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ph_ai_tracker", description="Fetch AI products from Product Hunt.")
    parser.add_argument("--strategy", default="scraper", choices=["api", "scraper", "auto"], help="Data source")
    parser.add_argument("--search", default="AI", help="Search term (client-side filter)")
    parser.add_argument("--limit", type=int, default=20, help="Max number of products")
    parser.add_argument(
        "--token",
        default=os.environ.get("PRODUCTHUNT_TOKEN"),
        help="Product Hunt API token (or set PRODUCTHUNT_TOKEN)",
    )

    args = parser.parse_args(argv)

    tracker = AIProductTracker(api_token=args.token, strategy=args.strategy)
    result = tracker.get_products(search_term=args.search, limit=args.limit)
    sys.stdout.write(result.to_pretty_json() + "\n")

    return 0 if result.error is None else 2


if __name__ == "__main__":
    raise SystemExit(main())

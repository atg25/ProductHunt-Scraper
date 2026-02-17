from __future__ import annotations

from dataclasses import dataclass
import argparse
import os
import re
import sys
import time

from .exceptions import StorageError
from .models import TrackerResult
from .storage import SQLiteStore
from .tracker import AIProductTracker


_ALLOWED_STRATEGIES = {"api", "scraper", "auto"}
_CRON_ALLOWED_RE = re.compile(r"^[\d\*/,\-\s]+$")


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    cron_schedule: str = "0 */6 * * *"
    timezone: str = "UTC"
    strategy: str = "scraper"
    search_term: str = "AI"
    limit: int = 20
    db_path: str = "./data/ph_ai_tracker.db"
    api_token: str | None = None
    retry_attempts: int = 2
    retry_backoff_seconds: float = 2.0


@dataclass(frozen=True, slots=True)
class SchedulerRunResult:
    run_id: int
    tracker_result: TrackerResult
    status: str
    attempts_used: int


def validate_cron_schedule(schedule: str) -> bool:
    if not schedule or not schedule.strip():
        return False

    normalized = " ".join(schedule.strip().split())
    fields = normalized.split(" ")
    if len(fields) != 5:
        return False

    return all(bool(field) and _CRON_ALLOWED_RE.match(field) for field in fields)


def _is_transient_error(message: str | None) -> bool:
    if not message:
        return False

    text = message.lower()
    transient_tokens = (
        "timed out",
        "request failed",
        "network",
        "rate limited",
        "status=429",
        "status=500",
        "status=502",
        "status=503",
        "status=504",
        "temporarily unavailable",
    )
    return any(token in text for token in transient_tokens)


def _classify_run_status(result: TrackerResult) -> str:
    if result.error is None:
        return "success"
    if result.products:
        return "partial"
    return "failure"


def scheduler_config_from_env() -> SchedulerConfig:
    schedule = os.environ.get("CRON_SCHEDULE", "0 */6 * * *")
    if not validate_cron_schedule(schedule):
        raise ValueError(f"Invalid CRON_SCHEDULE: {schedule}")

    strategy = (os.environ.get("PH_AI_TRACKER_STRATEGY", "scraper") or "scraper").strip().lower()
    if strategy not in _ALLOWED_STRATEGIES:
        raise ValueError(f"Invalid PH_AI_TRACKER_STRATEGY: {strategy}")

    limit_raw = os.environ.get("PH_AI_TRACKER_LIMIT", "20")
    try:
        limit = int(limit_raw)
    except ValueError as exc:
        raise ValueError(f"Invalid PH_AI_TRACKER_LIMIT: {limit_raw}") from exc

    retry_attempts_raw = os.environ.get("PH_AI_RETRY_ATTEMPTS", "2")
    try:
        retry_attempts = int(retry_attempts_raw)
    except ValueError as exc:
        raise ValueError(f"Invalid PH_AI_RETRY_ATTEMPTS: {retry_attempts_raw}") from exc

    retry_backoff_raw = os.environ.get("PH_AI_RETRY_BACKOFF_SECONDS", "2")
    try:
        retry_backoff = float(retry_backoff_raw)
    except ValueError as exc:
        raise ValueError(f"Invalid PH_AI_RETRY_BACKOFF_SECONDS: {retry_backoff_raw}") from exc

    return SchedulerConfig(
        cron_schedule=schedule,
        timezone=os.environ.get("TZ", "UTC"),
        strategy=strategy,
        search_term=os.environ.get("PH_AI_TRACKER_SEARCH", "AI"),
        limit=max(limit, 1),
        db_path=os.environ.get("PH_AI_DB_PATH", "./data/ph_ai_tracker.db"),
        api_token=os.environ.get("PRODUCTHUNT_TOKEN"),
        retry_attempts=max(retry_attempts, 1),
        retry_backoff_seconds=max(retry_backoff, 0.0),
    )


def run_once(config: SchedulerConfig) -> SchedulerRunResult:
    tracker = AIProductTracker(api_token=config.api_token, strategy=config.strategy)
    max_attempts = max(int(config.retry_attempts), 1)
    attempts_used = 0
    result = TrackerResult.failure(source=config.strategy, error="run not started")

    for attempt in range(1, max_attempts + 1):
        attempts_used = attempt
        result = tracker.get_products(search_term=config.search_term, limit=config.limit)

        if result.error is None:
            break

        if not _is_transient_error(result.error) or attempt >= max_attempts:
            break

        time.sleep(float(config.retry_backoff_seconds))

    store = SQLiteStore(config.db_path)
    status = _classify_run_status(result)
    run_id = store.save_result(result, search_term=config.search_term, limit=config.limit, status=status)

    return SchedulerRunResult(
        run_id=run_id,
        tracker_result=result,
        status=status,
        attempts_used=attempts_used,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ph_ai_tracker_scheduler",
        description="Run one scheduled scrape-and-persist cycle.",
    )
    parser.add_argument("--strategy", default=os.environ.get("PH_AI_TRACKER_STRATEGY", "scraper"))
    parser.add_argument("--search", default=os.environ.get("PH_AI_TRACKER_SEARCH", "AI"))
    parser.add_argument("--limit", type=int, default=int(os.environ.get("PH_AI_TRACKER_LIMIT", "20")))
    parser.add_argument("--db-path", default=os.environ.get("PH_AI_DB_PATH", "./data/ph_ai_tracker.db"))
    parser.add_argument("--token", default=os.environ.get("PRODUCTHUNT_TOKEN"))
    parser.add_argument("--retry-attempts", type=int, default=int(os.environ.get("PH_AI_RETRY_ATTEMPTS", "2")))
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=float(os.environ.get("PH_AI_RETRY_BACKOFF_SECONDS", "2")),
    )

    args = parser.parse_args(argv)

    strategy = (args.strategy or "scraper").strip().lower()
    if strategy not in _ALLOWED_STRATEGIES:
        sys.stderr.write(f"Invalid strategy: {strategy}\n")
        return 2

    config = SchedulerConfig(
        strategy=strategy,
        search_term=args.search,
        limit=max(int(args.limit), 1),
        db_path=args.db_path,
        api_token=args.token,
        retry_attempts=max(int(args.retry_attempts), 1),
        retry_backoff_seconds=max(float(args.retry_backoff_seconds), 0.0),
    )

    try:
        run_result = run_once(config)
    except StorageError as exc:
        sys.stderr.write(f"failed to persist run: {exc}\n")
        return 3

    fetched_count = len(run_result.tracker_result.products)
    sys.stderr.write(
        "[scheduler] "
        f"run_id={run_result.run_id} "
        f"status={run_result.status} "
        f"source={run_result.tracker_result.source} "
        f"attempts={run_result.attempts_used} "
        f"fetched={fetched_count} "
        f"error={run_result.tracker_result.error!r}\n"
    )

    sys.stdout.write(run_result.tracker_result.to_pretty_json() + "\n")
    return 0 if run_result.tracker_result.error is None else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Scheduler entry-point for periodic ph_ai_tracker runs.

One ``run_once()`` call executes a full fetch-and-persist cycle:

1. Instantiate ``AIProductTracker`` with the configured strategy.
2. Call ``get_products()`` with up to ``retry_attempts`` retries on transient
   errors (network timeouts, 5xx responses).
3. Classify the run as ``success``, ``partial``, or ``failure``.
4. Persist the result via ``SQLiteStore.save_result()``.

The ``main()`` function is the CLI entry-point registered as
``ph-ai-tracker-runner`` in ``pyproject.toml``.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import os
import re
import sys
import time
from typing import Callable, TypeVar

from .bootstrap import build_provider
from .cli import add_common_arguments, CommonArgs
from .constants import DEFAULT_LIMIT, DEFAULT_SEARCH_TERM
from .exceptions import StorageError
from .models import TrackerResult
from .storage import SQLiteStore
from .tracker import AIProductTracker


_ALLOWED_STRATEGIES = {"api", "scraper", "auto"}
_CRON_ALLOWED_RE = re.compile(r"^[\d\*/,\-\s]+$")

_T = TypeVar("_T")


def _parse_env_var(key: str, default: _T, cast: Callable[[str], _T]) -> _T:
    """Return env var *key* cast with *cast*; raise ValueError on cast failure."""
    raw = os.environ.get(key, str(default))
    try:
        return cast(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid {key}: {raw}") from exc


def _parse_int_env(key: str, default: int) -> int:
    """Return env var *key* as int; raise ValueError with key name on failure."""
    return _parse_env_var(key, default, int)


def _parse_float_env(key: str, default: float) -> float:
    """Return env var *key* as float; raise ValueError with key name on failure."""
    return _parse_env_var(key, default, float)


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    """Complete configuration for a single scheduler run.

    Fields
    ------
    cron_schedule:
        Five-field cron expression for the container entrypoint (e.g.
        ``"0 */6 * * *"`` = every 6 hours).  Validated by
        ``validate_cron_schedule`` on startup.
    timezone:
        POSIX timezone string passed to the cron daemon (default: ``UTC``).
    strategy:
        Data-retrieval strategy for ``AIProductTracker``.  One of
        ``"api"``, ``"scraper"``, or ``"auto"``.
    search_term:
        Keyword forwarded to ``get_products(search_term=...)``.  Defaults
        to ``"AI"``.
    limit:
        Maximum products per run.  Forwarded to ``get_products(limit=...)``.
    db_path:
        File-system path to the SQLite database.
    api_token:
        Product Hunt API Developer Token.  ``None`` forces the scraper path
        (or emits a warning if ``strategy="auto"``).
    retry_attempts:
        Number of fetch attempts before giving up on a transient error.
    retry_backoff_seconds:
        Seconds to sleep between retry attempts.
    """
    cron_schedule: str = "0 */6 * * *"
    timezone: str = "UTC"
    strategy: str = "scraper"
    search_term: str = DEFAULT_SEARCH_TERM
    limit: int = DEFAULT_LIMIT
    db_path: str = "./data/ph_ai_tracker.db"
    api_token: str | None = None
    retry_attempts: int = 2
    retry_backoff_seconds: float = 2.0


@dataclass(frozen=True, slots=True)
class SchedulerRunResult:
    """The outcome of a single ``run_once()`` call."""

    run_id: int
    tracker_result: TrackerResult
    status: str
    attempts_used: int


def validate_cron_schedule(schedule: str) -> bool:
    """Return ``True`` if *schedule* is a valid five-field cron expression."""
    if not schedule or not schedule.strip():
        return False

    normalized = " ".join(schedule.strip().split())
    fields = normalized.split(" ")
    if len(fields) != 5:
        return False

    return all(bool(field) and _CRON_ALLOWED_RE.match(field) for field in fields)


def _classify_run_status(result: TrackerResult) -> str:
    """Map a ``TrackerResult`` to one of ``'success'``, ``'partial'``, or ``'failure'``.

    A result with products *and* an error is ``'partial'`` — some data was
    recovered before the failure, which is more useful than recording nothing.
    """
    if result.error is None:
        return "success"
    if result.products:
        return "partial"
    return "failure"


def scheduler_config_from_env() -> SchedulerConfig:
    """Build a SchedulerConfig from env vars; raise ValueError on invalid input."""
    schedule = os.environ.get("CRON_SCHEDULE", "0 */6 * * *")
    if not validate_cron_schedule(schedule):
        raise ValueError(f"Invalid CRON_SCHEDULE: {schedule}")
    strategy = (os.environ.get("PH_AI_TRACKER_STRATEGY", "scraper") or "scraper").strip().lower()
    if strategy not in _ALLOWED_STRATEGIES:
        raise ValueError(f"Invalid PH_AI_TRACKER_STRATEGY: {strategy}")
    return SchedulerConfig(
        cron_schedule=schedule, timezone=os.environ.get("TZ", "UTC"),
        strategy=strategy, search_term=os.environ.get("PH_AI_TRACKER_SEARCH", DEFAULT_SEARCH_TERM),
        limit=max(_parse_int_env("PH_AI_TRACKER_LIMIT", DEFAULT_LIMIT), 1),
        db_path=os.environ.get("PH_AI_DB_PATH", "./data/ph_ai_tracker.db"),
        api_token=os.environ.get("PRODUCTHUNT_TOKEN"),
        retry_attempts=max(_parse_int_env("PH_AI_RETRY_ATTEMPTS", 2), 1),
        retry_backoff_seconds=max(_parse_float_env("PH_AI_RETRY_BACKOFF_SECONDS", 2.0), 0.0),
    )


def _fetch_with_retries(tracker: AIProductTracker, config: SchedulerConfig) -> tuple[TrackerResult, int]:
    """Retry fetch up to config.retry_attempts times on transient errors."""
    max_attempts = max(int(config.retry_attempts), 1)
    result = TrackerResult.failure(
        source=config.strategy,
        error="run not started",
        search_term=config.search_term,
        limit=config.limit,
    )
    for attempt in range(1, max_attempts + 1):
        result = tracker.get_products(search_term=config.search_term, limit=config.limit)
        if result.error is None:
            return result, attempt
        if not result.is_transient or attempt >= max_attempts:
            return result, attempt
        time.sleep(float(config.retry_backoff_seconds))
    return result, max_attempts


def _format_run_summary(run_result: SchedulerRunResult) -> str:
    """Return a one-line stderr summary for the completed run."""
    r = run_result.tracker_result
    return (
        f"[scheduler] run_id={run_result.run_id} status={run_result.status} "
        f"source={r.source} attempts={run_result.attempts_used} "
        f"fetched={len(r.products)} error={r.error!r}"
    )


def _build_config_from_args(args: argparse.Namespace, common: CommonArgs) -> SchedulerConfig:
    """Build SchedulerConfig from parsed CLI arguments."""
    return SchedulerConfig(
        strategy=common.strategy, search_term=common.search_term,
        limit=common.limit, db_path=common.db_path, api_token=common.api_token,
        retry_attempts=max(int(args.retry_attempts), 1),
        retry_backoff_seconds=max(float(args.retry_backoff_seconds), 0.0),
    )


def _make_scheduler_parser() -> argparse.ArgumentParser:
    """Build and return the scheduler CLI argument parser."""
    p = argparse.ArgumentParser(prog="ph_ai_tracker_scheduler", description="Run one scheduled scrape-and-persist cycle.")
    add_common_arguments(p)
    p.add_argument("--retry-attempts", type=int, default=_parse_int_env("PH_AI_RETRY_ATTEMPTS", 2))
    p.add_argument("--retry-backoff-seconds", type=float, default=_parse_float_env("PH_AI_RETRY_BACKOFF_SECONDS", 2.0))
    return p


def run_once(config: SchedulerConfig) -> SchedulerRunResult:
    """Execute one full fetch-and-persist cycle and return the run outcome."""
    provider = build_provider(strategy=config.strategy, api_token=config.api_token)
    tracker = AIProductTracker(provider=provider)
    result, attempts_used = _fetch_with_retries(tracker, config)
    store = SQLiteStore(config.db_path)
    store.init_db()
    status = _classify_run_status(result)
    run_id = store.save_result(result, status=status)
    return SchedulerRunResult(
        run_id=run_id, tracker_result=result, status=status, attempts_used=attempts_used,
    )


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, run one cycle, and return an exit code."""
    args = _make_scheduler_parser().parse_args(argv)
    common = CommonArgs.from_namespace(args)
    if common.strategy not in _ALLOWED_STRATEGIES:
        sys.stderr.write(f"Invalid strategy: {common.strategy}\n")
        return 2
    config = _build_config_from_args(args, common)
    try:
        run_result = run_once(config)
    except StorageError as exc:
        sys.stderr.write(f"failed to persist run: {exc}\n")
        return 3
    sys.stderr.write(_format_run_summary(run_result) + "\n")
    sys.stdout.write(run_result.tracker_result.to_pretty_json() + "\n")
    return 0 if run_result.tracker_result.error is None else 2


if __name__ == "__main__":
    raise SystemExit(main())

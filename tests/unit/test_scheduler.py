from __future__ import annotations

from pathlib import Path
import sqlite3
import time

import pytest

from ph_ai_tracker.models import Product, TrackerResult
from ph_ai_tracker.scheduler import SchedulerConfig, run_once, scheduler_config_from_env, validate_cron_schedule
from ph_ai_tracker.tracker import AIProductTracker
import ph_ai_tracker.scheduler as scheduler


def test_validate_cron_schedule_valid_cases() -> None:
    assert validate_cron_schedule("0 */6 * * *")
    assert validate_cron_schedule("*/15 * * * *")


def test_validate_cron_schedule_invalid_cases() -> None:
    assert not validate_cron_schedule("")
    assert not validate_cron_schedule("not-a-cron")
    assert not validate_cron_schedule("0 */6 * * * *")


def test_scheduler_config_from_env_invalid_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRON_SCHEDULE", "bad schedule")
    with pytest.raises(ValueError):
        scheduler_config_from_env()


def test_scheduler_config_from_env_invalid_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRON_SCHEDULE", "0 */6 * * *")
    monkeypatch.setenv("PH_AI_TRACKER_STRATEGY", "invalid")
    with pytest.raises(ValueError):
        scheduler_config_from_env()


def test_scheduler_config_from_env_invalid_retry_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRON_SCHEDULE", "0 */6 * * *")
    monkeypatch.setenv("PH_AI_RETRY_ATTEMPTS", "oops")
    with pytest.raises(ValueError):
        scheduler_config_from_env()


def test_parse_env_var_returns_cast_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PH_TEST_INT", "42")
    assert scheduler._parse_env_var("PH_TEST_INT", 5, int) == 42


def test_parse_env_var_uses_default_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PH_MISSING_INT", raising=False)
    assert scheduler._parse_env_var("PH_MISSING_INT", 7, int) == 7


def test_parse_env_var_raises_on_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PH_BAD_INT", "not-an-int")
    with pytest.raises(ValueError, match="PH_BAD_INT"):
        scheduler._parse_env_var("PH_BAD_INT", 0, int)


def test_parse_int_env_still_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PH_STILL_INT", "9")
    assert scheduler._parse_int_env("PH_STILL_INT", 3) == 9


def test_parse_float_env_still_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PH_STILL_FLOAT", "3.14")
    assert scheduler._parse_float_env("PH_STILL_FLOAT", 1.0) == 3.14


def test_run_once_persists_to_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "scheduler.db"

    def fake_get_products(self, *, search_term: str = "AI", limit: int = 20) -> TrackerResult:
        return TrackerResult.success(
            [Product(name="AlphaAI", url="https://example.com/alpha", votes_count=42)],
            source="scraper",
        )

    monkeypatch.setattr(AIProductTracker, "get_products", fake_get_products)

    config = SchedulerConfig(
        strategy="scraper",
        search_term="AI",
        limit=5,
        db_path=str(db_path),
    )

    result = run_once(config)
    assert result.run_id > 0
    assert result.tracker_result.error is None
    assert result.status == "success"
    assert result.attempts_used == 1

    with sqlite3.connect(db_path) as conn:
        run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()
        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()
        assert run_count is not None and int(run_count[0]) == 1
        assert product_count is not None and int(product_count[0]) == 1


def test_run_once_retries_transient_error_then_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "scheduler.db"
    calls: list[int] = []

    def fake_get_products(self, *, search_term: str = "AI", limit: int = 20) -> TrackerResult:
        calls.append(1)
        if len(calls) == 1:
            return TrackerResult.failure(source="scraper", error="Scraper request timed out", is_transient=True)
        return TrackerResult.success([Product(name="AlphaAI", votes_count=1)], source="scraper")

    monkeypatch.setattr(AIProductTracker, "get_products", fake_get_products)
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)

    config = SchedulerConfig(
        strategy="scraper",
        search_term="AI",
        limit=5,
        db_path=str(db_path),
        retry_attempts=3,
        retry_backoff_seconds=0.0,
    )

    result = run_once(config)
    assert len(calls) == 2
    assert result.status == "success"
    assert result.attempts_used == 2


def test_run_once_does_not_retry_non_transient_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "scheduler.db"
    calls: list[int] = []

    def fake_get_products(self, *, search_term: str = "AI", limit: int = 20) -> TrackerResult:
        calls.append(1)
        return TrackerResult.failure(source="api", error="Missing api_token", is_transient=False)

    monkeypatch.setattr(AIProductTracker, "get_products", fake_get_products)
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)

    config = SchedulerConfig(
        strategy="api",
        search_term="AI",
        limit=5,
        db_path=str(db_path),
        retry_attempts=5,
        retry_backoff_seconds=0.0,
    )

    result = run_once(config)
    assert len(calls) == 1
    assert result.status == "failure"
    assert result.attempts_used == 1

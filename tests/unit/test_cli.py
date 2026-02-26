"""Unit tests for ph_ai_tracker.cli."""
from __future__ import annotations

import argparse

import pytest

from ph_ai_tracker.cli import CommonArgs, add_common_arguments


# add_common_arguments

def test_add_common_arguments_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """All five defaults are applied when no env vars or CLI flags are set."""
    for var in (
        "PH_AI_TRACKER_STRATEGY",
        "PH_AI_TRACKER_SEARCH",
        "PH_AI_TRACKER_LIMIT",
        "PH_AI_DB_PATH",
        "PRODUCTHUNT_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)

    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    args = parser.parse_args([])

    assert args.strategy == "scraper"
    assert args.search == "AI"
    assert args.limit == 10
    assert args.db_path == "./data/ph_ai_tracker.db"
    assert args.token is None


def test_add_common_arguments_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables override the built-in defaults."""
    monkeypatch.setenv("PH_AI_TRACKER_STRATEGY", "api")
    monkeypatch.setenv("PH_AI_TRACKER_SEARCH", "ML")
    monkeypatch.setenv("PH_AI_TRACKER_LIMIT", "5")
    monkeypatch.setenv("PH_AI_DB_PATH", "/tmp/test.db")
    monkeypatch.setenv("PRODUCTHUNT_TOKEN", "tok")

    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    args = parser.parse_args([])

    assert args.strategy == "api"
    assert args.search == "ML"
    assert args.limit == 5
    assert args.db_path == "/tmp/test.db"
    assert args.token == "tok"


def test_add_common_arguments_cli_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit CLI flags take precedence over environment variables."""
    monkeypatch.setenv("PH_AI_TRACKER_STRATEGY", "api")

    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    args = parser.parse_args(["--strategy", "scraper"])

    assert args.strategy == "scraper"


# CommonArgs

def _ns(**kwargs: object) -> argparse.Namespace:
    defaults = dict(strategy="scraper", search="AI", limit=10, db_path="./data/x.db", token=None)
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_common_args_from_namespace_maps_fields() -> None:
    ns = _ns(strategy="api", search="ML", limit=10, db_path="/tmp/t.db", token="tok123")
    common = CommonArgs.from_namespace(ns)

    assert common.strategy   == "api"
    assert common.search_term == "ML"
    assert common.limit       == 10
    assert common.db_path     == "/tmp/t.db"
    assert common.api_token   == "tok123"


def test_common_args_limit_floored_to_one() -> None:
    """A non-positive limit is clamped to 1."""
    common = CommonArgs.from_namespace(_ns(limit=0))
    assert common.limit == 1


def test_common_args_none_token_stays_none() -> None:
    common = CommonArgs.from_namespace(_ns(token=None))
    assert common.api_token is None


def test_common_args_empty_token_becomes_none() -> None:
    common = CommonArgs.from_namespace(_ns(token=""))
    assert common.api_token is None


def test_common_args_is_frozen() -> None:
    common = CommonArgs.from_namespace(_ns())
    with pytest.raises((AttributeError, TypeError)):
        common.strategy = "api"  # type: ignore[misc]

"""Unit tests for ph_ai_tracker.bootstrap (provider factory)."""

from __future__ import annotations

import pytest

from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.bootstrap import build_provider
from ph_ai_tracker.protocols import FallbackProvider, _NoTokenProvider
from ph_ai_tracker.scraper import ProductHuntScraper


def test_build_provider_scraper() -> None:
    p = build_provider(strategy="scraper", api_token=None)
    assert isinstance(p, ProductHuntScraper)


def test_build_provider_api_with_token() -> None:
    p = build_provider(strategy="api", api_token="my-token")
    assert isinstance(p, ProductHuntAPI)


def test_build_provider_api_no_token_returns_no_token_provider() -> None:
    with pytest.warns(RuntimeWarning, match="api_token"):
        p = build_provider(strategy="api", api_token=None)
    assert isinstance(p, _NoTokenProvider)


def test_build_provider_auto_with_token() -> None:
    p = build_provider(strategy="auto", api_token="my-token")
    assert isinstance(p, FallbackProvider)
    assert p.source_name == "auto"


def test_build_provider_auto_no_token_emits_warning() -> None:
    with pytest.warns(RuntimeWarning, match="api_token"):
        p = build_provider(strategy="auto", api_token=None)
    assert isinstance(p, FallbackProvider)


def test_build_provider_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError, match="Unknown strategy"):
        build_provider(strategy="rss_feed", api_token=None)

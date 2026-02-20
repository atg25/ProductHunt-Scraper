"""Integration-level docstring and narrative documentation checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ph_ai_tracker.models import TrackerResult
from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.scraper import ProductHuntScraper, NextDataExtractor
from ph_ai_tracker.storage import SQLiteStore
from ph_ai_tracker.protocols import FallbackProvider

REPO_ROOT = Path(__file__).resolve().parents[2]


# POSITIVE — critical "why" keywords in method docstrings

def test_fallback_docstring_contains_strategy_or_fallback_keyword() -> None:
    doc = (FallbackProvider.__doc__ or "").lower()
    assert any(kw in doc for kw in ("fallback", "strategy", "invariant", "configuration", "token"))


def test_scraper_docstring_mentions_next_data_or_dom() -> None:
    """The scraper extraction method must reference the DOM structure it parses."""
    doc = (NextDataExtractor.extract.__doc__ or "").lower()
    assert "__next_data__" in doc or "walk" in doc or "json" in doc


def test_storage_upsert_docstring_mentions_on_conflict() -> None:
    doc = (SQLiteStore._upsert_product.__doc__ or "").lower()
    assert "on conflict" in doc or "upsert" in doc or "dedup" in doc


def test_tracker_result_docstring_mentions_transient() -> None:
    doc = (TrackerResult.__doc__ or "").lower()
    assert "transient" in doc or "retry" in doc


# NEGATIVE — subprocess checks for tooling

def test_no_module_level_syntax_errors() -> None:
    """All source modules import cleanly — a basic sanity check for docstring syntax."""
    result = subprocess.run(
        [sys.executable, "-c",
         "import ph_ai_tracker.tracker, ph_ai_tracker.scraper, "
         "ph_ai_tracker.storage, ph_ai_tracker.api_client, "
         "ph_ai_tracker.models, ph_ai_tracker.exceptions, "
         "ph_ai_tracker.scheduler; print('ok')"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Import failed:\n{result.stderr}"
    assert "ok" in result.stdout

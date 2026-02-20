"""E2E validation that the bundle contains the correct first-party source.

Runs ``make bundle`` then inspects content for first-party classes and the
absence of third-party/generated content.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = REPO_ROOT / "codebase_review_bundle.txt"


@pytest.fixture(scope="module", autouse=True)
def regenerate_bundle() -> None:
    """Always regenerate before these E2E checks so content is fresh."""
    subprocess.run(["make", "bundle"], cwd=REPO_ROOT, check=True, capture_output=True)


@pytest.fixture(scope="module")
def bundle_text() -> str:
    return BUNDLE_PATH.read_text(encoding="utf-8", errors="replace")


# POSITIVE — essential first-party symbols must appear

def test_e2e_bundle_contains_tracker_source(bundle_text: str) -> None:
    assert "class AIProductTracker" in bundle_text


def test_e2e_bundle_contains_scraper_source(bundle_text: str) -> None:
    assert "class ProductHuntScraper" in bundle_text


def test_e2e_bundle_contains_storage_source(bundle_text: str) -> None:
    assert "class SQLiteStore" in bundle_text


# NEGATIVE — third-party / generated artefacts must be absent

def _file_paths(bundle_text: str) -> list[str]:
    """Extract path strings from all FILE: marker lines."""
    paths = []
    for line in bundle_text.splitlines():
        s = line.strip()
        if s.startswith("FILE:") and not s.startswith("FILE: PATH"):
            paths.append(s[len("FILE:"):].strip())
    return paths


def test_e2e_bundle_has_no_site_packages(bundle_text: str) -> None:
    """No FILE: marker in the bundle should point into site-packages."""
    bad = [p for p in _file_paths(bundle_text) if "site-packages" in p]
    assert bad == [], f"site-packages FILE markers found: {bad[:3]}"


def test_e2e_bundle_has_no_venv_content(bundle_text: str) -> None:
    """No FILE: marker should point into the .venv directory."""
    bad = [p for p in _file_paths(bundle_text) if ".venv" in p]
    assert bad == [], f".venv FILE markers found: {bad[:3]}"


def test_e2e_bundle_has_no_pycache(bundle_text: str) -> None:
    """No FILE: marker should point into a __pycache__ directory."""
    bad = [p for p in _file_paths(bundle_text) if "__pycache__" in p]
    assert bad == [], f"__pycache__ FILE markers found: {bad[:3]}"

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


# Sprint 60 — newly added production files must appear in the regenerated bundle

def test_e2e_bundle_contains_tagging_source(bundle_text: str) -> None:
    """tagging.py must be present in the bundle after Sprint 60."""
    assert "class NoOpTaggingService" in bundle_text, (
        "NoOpTaggingService missing — tagging.py not in bundle"
    )
    assert "class UniversalLLMTaggingService" in bundle_text, (
        "UniversalLLMTaggingService missing — tagging.py not in bundle"
    )


def test_e2e_bundle_contains_formatter_source(bundle_text: str) -> None:
    """formatters.py must be present in the bundle after Sprint 60."""
    assert "class NewsletterFormatter" in bundle_text, (
        "NewsletterFormatter missing — formatters.py not in bundle"
    )


def test_e2e_bundle_all_production_files_exist() -> None:
    """Every file listed in SECTION_3_PRODUCTION must physically exist on disk."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_bundle  # type: ignore[import]
    missing = [str(p) for p in build_bundle.SECTION_3_PRODUCTION if not p.exists()]
    assert missing == [], f"Listed production files not found on disk: {missing}"


def test_e2e_bundle_all_test_files_exist() -> None:
    """Every file listed in SECTION_4_TESTS must physically exist on disk."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_bundle  # type: ignore[import]
    missing = [str(p) for p in build_bundle.SECTION_4_TESTS if not p.exists()]
    assert missing == [], f"Listed test files not found on disk: {missing}"

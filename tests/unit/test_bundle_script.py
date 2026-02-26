"""Verify properties of the codebase review bundle file.

These tests assume ``make bundle`` has been run and the bundle file exists.
They are skipped if the bundle is absent (run ``make bundle`` first).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BUNDLE_PATH = Path(__file__).resolve().parents[2] / "codebase_review_bundle.txt"

pytestmark = pytest.mark.skipif(
    not BUNDLE_PATH.exists(),
    reason="codebase_review_bundle.txt not found — run `make bundle` first",
)


def _file_markers(bundle: str) -> list[str]:
    """Return all 'FILE: …' marker lines from the bundle, path only."""
    results = []
    for line in bundle.splitlines():
        stripped = line.strip()
        if stripped.startswith("FILE:") and not stripped.startswith("FILE: PATH"):
            # Extract just the path: 'FILE: src/ph_ai_tracker/foo.py' -> 'src/ph_ai_tracker/foo.py'
            results.append(stripped[len("FILE:"):].strip())
    return results


@pytest.fixture(scope="module")
def bundle_text() -> str:
    return BUNDLE_PATH.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def file_markers(bundle_text: str) -> list[str]:
    return _file_markers(bundle_text)


# POSITIVE — the bundle must contain only first-party source

def test_bundle_excludes_venv_paths(file_markers: list[str]) -> None:
    venv_markers = [m for m in file_markers if re.search(r"\.venv[/\\]", m)]
    assert venv_markers == [], f"Bundle contains .venv paths: {venv_markers[:5]}"


def test_bundle_excludes_pycache_paths(file_markers: list[str]) -> None:
    pycache_markers = [m for m in file_markers if "__pycache__" in m]
    assert pycache_markers == [], f"Bundle contains __pycache__ paths: {pycache_markers[:5]}"


def test_bundle_excludes_pyc_files(file_markers: list[str]) -> None:
    pyc_markers = [m for m in file_markers if m.endswith(".pyc")]
    assert pyc_markers == [], f"Bundle contains .pyc files: {pyc_markers[:5]}"


def test_bundle_excludes_egg_info(file_markers: list[str]) -> None:
    egg_markers = [m for m in file_markers if ".egg-info" in m]
    assert egg_markers == [], f"Bundle contains .egg-info paths: {egg_markers[:5]}"


def test_bundle_file_markers_contain_source_files(file_markers: list[str]) -> None:
    """At least some first-party source files should be present."""
    src_markers = [m for m in file_markers if m.startswith("src/") or m.startswith("tests/")]
    assert len(src_markers) > 5, "Expected to find src/ and tests/ files in bundle"


# NEGATIVE — the bundle must NOT contain generated / external artefacts

def test_bundle_file_is_non_empty(bundle_text: str) -> None:
    assert len(bundle_text) > 0, "Bundle file is empty"


def test_bundle_does_not_include_site_packages(file_markers: list[str]) -> None:
    """No FILE: marker should point to a path containing 'site-packages'."""
    bad = [m for m in file_markers if "site-packages" in m]
    assert bad == [], f"Bundle FILE markers contain site-packages paths: {bad[:5]}"


def test_bundle_does_not_include_pytest_cache(file_markers: list[str]) -> None:
    cache_markers = [m for m in file_markers if ".pytest_cache" in m]
    assert cache_markers == [], f"Bundle contains .pytest_cache paths: {cache_markers[:5]}"


# Sprint 60 — tagging.py and formatters.py must appear in build_bundle.py lists

def test_tagging_in_production_list() -> None:
    from scripts import build_bundle
    paths = [str(p) for p in build_bundle.SECTION_3_PRODUCTION]
    assert any("tagging.py" in p for p in paths), "tagging.py missing from SECTION_3_PRODUCTION"


def test_formatters_in_production_list() -> None:
    from scripts import build_bundle
    paths = [str(p) for p in build_bundle.SECTION_3_PRODUCTION]
    assert any("formatters.py" in p for p in paths), "formatters.py missing from SECTION_3_PRODUCTION"


def test_tagging_tests_in_test_list() -> None:
    from scripts import build_bundle
    paths = [str(p) for p in build_bundle.SECTION_4_TESTS]
    assert any("test_tagging.py" in p for p in paths), "test_tagging.py missing from SECTION_4_TESTS"


def test_formatters_tests_in_test_list() -> None:
    from scripts import build_bundle
    paths = [str(p) for p in build_bundle.SECTION_4_TESTS]
    assert any("test_formatters.py" in p for p in paths), "test_formatters.py missing from SECTION_4_TESTS"


def test_pipeline_tests_in_test_list() -> None:
    from scripts import build_bundle
    paths = [str(p) for p in build_bundle.SECTION_4_TESTS]
    assert any("test_tagging_formatter_pipeline.py" in p for p in paths), (
        "test_tagging_formatter_pipeline.py missing from SECTION_4_TESTS"
    )

"""Integration tests for the ``make bundle`` target.

These tests actually invoke ``make bundle`` so they require ``make`` to be
present on the PATH.  They are slower than unit tests and should run in CI.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = REPO_ROOT / "codebase_review_bundle.txt"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# POSITIVE

def test_make_bundle_target_exits_zero() -> None:
    result = subprocess.run(
        ["make", "bundle"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"make bundle failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_bundle_line_count_is_reasonable() -> None:
    """Bundle should have real source (> 100 lines) but no venv junk (< 50 000 lines)."""
    subprocess.run(["make", "bundle"], cwd=REPO_ROOT, check=True, capture_output=True)
    line_count = len(BUNDLE_PATH.read_text(encoding="utf-8", errors="replace").splitlines())
    assert line_count > 100, f"Bundle too small ({line_count} lines); possibly empty"
    assert line_count < 50_000, f"Bundle too large ({line_count} lines); possibly includes .venv"


def test_cli_module_in_bundle() -> None:
    subprocess.run(["make", "bundle"], cwd=REPO_ROOT, check=True, capture_output=True)
    bundle_text = BUNDLE_PATH.read_text(encoding="utf-8", errors="replace")
    assert "FILE: src/ph_ai_tracker/cli.py" in bundle_text
    assert "def add_common_arguments" in bundle_text
    assert "class CommonArgs" in bundle_text


# NEGATIVE

def test_bundle_regeneration_is_idempotent() -> None:
    """Running make bundle twice should produce the same file content."""
    subprocess.run(["make", "bundle"], cwd=REPO_ROOT, check=True, capture_output=True)
    sha1 = _sha256(BUNDLE_PATH)

    subprocess.run(["make", "bundle"], cwd=REPO_ROOT, check=True, capture_output=True)
    sha2 = _sha256(BUNDLE_PATH)

    assert sha1 == sha2, "Bundle regeneration is not idempotent (content differs between runs)"

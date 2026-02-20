# Sprint 25 — Broken Bundle Manifest: Add `cli.py` to Production File List

## Context

Uncle Bob Letter #5 reports that he cannot find `cli.py` in the
`codebase_review_bundle.txt` that is submitted for review. His conclusion is
that the module does not exist — but the opposite is true. `cli.py` **exists,
is fully implemented, and its imports are confirmed clean**.

The root cause is a pure omission in `scripts/build_bundle.py`. When `cli.py`
was extracted from `__main__.py` (Sprint 14, DRY CLI), the `SECTION_3_PRODUCTION`
list that controls which source files appear in the bundle was **never updated**.
Uncle Bob receives a bundle with 9 production files; the correct number is 10.

This sprint fixes in **one targeted line** and verifies the fix with a
regression-safe integration test.

---

## Problem Statement

### Root cause

`scripts/build_bundle.py`, lines 37–47 (`SECTION_3_PRODUCTION`):

```python
SECTION_3_PRODUCTION: list[Path] = [
    SRC / "exceptions.py",
    SRC / "models.py",
    SRC / "api_client.py",
    SRC / "scraper.py",
    SRC / "storage.py",
    SRC / "tracker.py",
    SRC / "scheduler.py",      # <-- cli.py must appear BEFORE this line
    SRC / "__init__.py",
    SRC / "__main__.py",
]
```

`SRC / "cli.py"` is absent. All other 9 modules are present.

### Why `cli.py` must appear before `scheduler.py`

`cli.py` exports `CommonArgs` and `add_common_arguments()`. Both
`scheduler.py` and `__main__.py` import from `cli.py`. Presenting it earlier
in the bundle preserves the dependency-order convention already established for
all other modules.

### Proof that the file itself is correct

```
$ python -c "from ph_ai_tracker.cli import add_common_arguments, CommonArgs; print('cli OK')"
cli OK
```

---

## Acceptance Criteria

1. `codebase_review_bundle.txt` (Section 3) contains the full source of
   `cli.py` after running `make bundle`.
2. The bundle header line **"Production files: 10"** is reported (was 9).
3. `cli.py` appears in Section 3 **before** `scheduler.py` and
   `__main__.py`.
4. All 212+ existing tests remain green.
5. `test_cli_module_in_bundle` passes with no modifications allowed to the
   production source files it reads.

---

## Test Plan (TDD — Red → Green → Refactor)

### RED phase

Add one test to `tests/integration/test_bundle_integrity.py` **before**
touching `build_bundle.py`:

```python
def test_cli_module_in_bundle() -> None:
    """cli.py must appear in the production section of the bundle."""
    import subprocess
    from pathlib import Path

    REPO_ROOT = Path(__file__).resolve().parents[2]
    BUNDLE_PATH = REPO_ROOT / "codebase_review_bundle.txt"

    subprocess.run(["make", "bundle"], cwd=REPO_ROOT, check=True,
                   capture_output=True)
    bundle_text = BUNDLE_PATH.read_text(encoding="utf-8")

    # The bundle must contain the canonical cli.py source marker
    assert "def add_common_arguments" in bundle_text, (
        "cli.py is missing from the bundle — add SRC / 'cli.py' to "
        "SECTION_3_PRODUCTION in scripts/build_bundle.py"
    )
    assert "class CommonArgs" in bundle_text, (
        "CommonArgs dataclass not found in bundle; cli.py may be truncated"
    )
```

Run `pytest tests/integration/test_bundle_integrity.py::test_cli_module_in_bundle`
— it **must FAIL** (confirming the red state).

### GREEN phase

Apply the single-line fix to `scripts/build_bundle.py`:

```python
SECTION_3_PRODUCTION: list[Path] = [
    SRC / "exceptions.py",
    SRC / "models.py",
    SRC / "api_client.py",
    SRC / "scraper.py",
    SRC / "storage.py",
    SRC / "tracker.py",
    SRC / "cli.py",           # <-- ADDED
    SRC / "scheduler.py",
    SRC / "__init__.py",
    SRC / "__main__.py",
]
```

Run the new test — it **must PASS**.

### REFACTOR / Regression phase

```bash
make bundle
pytest --tb=short -q
```

Both must exit zero. Confirm the bundle header output includes:

```
Production files: 10
```

---

## Files Changed

| File                                         | Change                                                  |
| -------------------------------------------- | ------------------------------------------------------- |
| `scripts/build_bundle.py`                    | Add `SRC / "cli.py"` to `SECTION_3_PRODUCTION` (1 line) |
| `tests/integration/test_bundle_integrity.py` | Add `test_cli_module_in_bundle`                         |

---

## Definition of Done

- [ ] `test_cli_module_in_bundle` passes
- [ ] `make bundle` exits zero and reports "Production files: 10"
- [ ] Full `pytest` run: 213+ tests, 0 failures
- [ ] Bundle text contains `def add_common_arguments` and `class CommonArgs`
- [ ] No production source files were modified

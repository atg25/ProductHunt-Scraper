# Sprint 5 — Packaging, Distribution & Repo Finalization

**Goal:** Ensure the package builds, installs cleanly, and the GitHub repo is publish-ready.

## Tasks

### Public API Surface

- [ ] `__init__.py` exports: `AIProductTracker`, `Product`, `TrackerResult`
- [ ] `py.typed` marker present for PEP 561 compliance

### Build Validation

- [ ] `poetry build` produces `.whl` and `.tar.gz`
- [ ] Install wheel in a fresh venv → `from ph_ai_tracker import AIProductTracker` works

### Repo Polish

- [ ] `README.md` — Overview, installation, usage example, API reference
- [ ] `LICENSE` — MIT
- [ ] `.gitignore` — comprehensive Python/Poetry ignores
- [ ] `CHANGELOG.md` — Initial release notes

### Tests

```
tests/e2e/test_packaging.py
    ✗ test_public_api_exports_tracker_class
    ✗ test_public_api_exports_product_class
    ✗ test_public_api_exports_tracker_result_class
    ✗ test_py_typed_marker_exists
```

## Terminal Checklist (Zero → Published Repo)

See `TERMINAL_CHECKLIST.md` in project root.

## Exit Criteria

```bash
$ poetry build
Building ph_ai_tracker (0.1.0)
  - Building sdist
  - Built ph_ai_tracker-0.1.0.tar.gz
  - Building wheel
  - Built ph_ai_tracker-0.1.0-py3-none-any.whl

$ poetry run pytest tests/ -v --tb=short
~43 passed
```

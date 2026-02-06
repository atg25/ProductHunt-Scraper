# Sprint 0 — Project Scaffolding & Tooling

**Goal:** Establish the project skeleton so that `poetry install && poetry run pytest`
exits cleanly with zero errors.

## Checklist

- [ ] `poetry init` with src/ layout → `pyproject.toml` created
- [ ] `poetry env use $(which pypy3)` → virtualenv pinned to PyPy 3
- [ ] Add production deps: `httpx`, `beautifulsoup4`, `lxml`
- [ ] Add dev deps: `pytest`, `pytest-cov`, `responses`, `pytest-mock`
- [ ] Create directory tree:
  ```
  src/ph_ai_tracker/
      __init__.py
      models.py
      api_client.py
      scraper.py
      tracker.py
      exceptions.py
      py.typed
  ```
- [ ] Create `tests/` tree with `conftest.py` and fixture dirs
- [ ] Create `.gitignore`, `README.md`, `LICENSE`
- [ ] Run `poetry check` — must pass
- [ ] Run `poetry run pytest` — 0 collected, 0 errors

## Exit Criteria

```bash
$ poetry check
All set!

$ poetry run pytest
========================= no tests ran ==========================
```

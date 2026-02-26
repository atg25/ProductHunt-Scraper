# Sprint 64 — Expose an HTTP API: FastAPI Endpoints for Live Scrape and History

## Objective

Add a production-ready HTTP interface so external clients can consume
`ph_ai_tracker` without invoking CLI commands directly.

## Why (Clean Architecture)

The API layer is an outer adapter. It should orchestrate request/response
translation only, while delegating domain work to existing use-case and
storage components (`AIProductTracker`, `SQLiteStore`, `NewsletterFormatter`).

## Scope

**In:**

- `src/ph_ai_tracker/api.py`
- `tests/unit/test_api.py`
- `tests/integration/test_http_api_integration.py`
- `tests/e2e/test_e2e_api.py`
- `pyproject.toml`, `poetry.lock`, `Makefile`, `README.md`

**Out:**

- No changes to Product Hunt adapter contracts
- No schema redesign (reuses single `products` table)

---

## Delivered Endpoints

| Method | Path                | Behavior                                                |
| ------ | ------------------- | ------------------------------------------------------- |
| `GET`  | `/health`           | Returns `{"status": "ok"}`                              |
| `GET`  | `/products/search`  | Runs live fetch, returns newsletter JSON, persists rows |
| `GET`  | `/products/history` | Returns persisted observations from SQLite              |

### Validation Contract

- `/products/search`
  - `q`: 1–100 chars
  - `limit`: 1–50
  - `strategy`: `auto | scraper | api`
- `/products/history`
  - `limit`: 1–500
- Invalid inputs return `422` via FastAPI validation.

### Error Contract

- Tracker/runtime failures in `/products/search` return `503` with `detail`.
- DB read failures in `/products/history` return `503` with `detail`.

---

## TDD Coverage Implemented

### Unit

- `tests/unit/test_api.py`
  - Health success
  - Search success/validation/error behavior
  - History success/validation/error behavior
  - Edge limits and empty-history behavior

### Integration

- `tests/integration/test_http_api_integration.py`
  - Search → history round-trip
  - Multi-search accumulation
  - Error path does not persist
  - Real SQLite row read verification

### E2E

- `tests/e2e/test_e2e_api.py`
  - Health route
  - Scraper fixture search flow
  - History after search
  - Bad strategy validation
  - Network failure behavior
  - Repeated history consistency

---

## Definition of Done

- [x] `src/ph_ai_tracker/api.py` provides `app`, `/health`, `/products/search`, `/products/history`
- [x] Search endpoint returns newsletter JSON and persists successful runs
- [x] History endpoint reads single-table storage shape (`products`)
- [x] FastAPI query validation enforces bounds and allowed strategy values
- [x] API unit/integration/e2e tests added and passing
- [x] `make serve` runs `uvicorn ph_ai_tracker.api:app`
- [x] README includes API section and usage examples
- [x] `make bundle` passes with all function-size checks green
- [x] Full `pytest -q` passes

---

## Final Verification

- Full test suite: passed
- Bundle generation: passed (`✓ All functions within 20-line guideline`)
- Dependencies synced: `fastapi`, `uvicorn` added and lockfile refreshed

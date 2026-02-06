# Sprint 1 — Domain Models & Data Contracts

**Goal:** Define all data models and custom exceptions with full test coverage.

## TDD Cycle

### Red Phase — Write failing tests FIRST

```
tests/unit/test_models.py
    ✗ test_product_creation_valid
    ✗ test_product_creation_defaults
    ✗ test_product_to_dict
    ✗ test_product_from_dict_valid
    ✗ test_product_from_dict_missing_key_raises
    ✗ test_tracker_result_success
    ✗ test_tracker_result_with_error
    ✗ test_exceptions_hierarchy
    ✗ test_exception_messages
```

### Green Phase — Implement models

- `Product` dataclass with fields: name, tagline, description, votes_count, url, topics
- `TrackerResult` dataclass with fields: products, source, fetched_at, error
- `APIError`, `ScraperError`, `RateLimitError` exceptions
- `Product.to_dict()` and `Product.from_dict()` class method

### Refactor Phase

- Add `__repr__` to models
- Ensure immutability where appropriate
- Add type hints to everything

## Exit Criteria

```bash
$ poetry run pytest tests/unit/test_models.py -v
8 passed
```

# Sprint 2 — GraphQL API Client

**Goal:** Implement the ProductHunt GraphQL v2 API client with full mocked test coverage.

## TDD Cycle

### Red Phase — Write failing tests FIRST

```
tests/unit/test_api_client.py
    ✗ test_client_init_with_token
    ✗ test_client_init_missing_token_raises
    ✗ test_build_query_contains_required_fields
    ✗ test_build_query_search_term
    ✗ test_fetch_returns_product_list
    ✗ test_fetch_empty_response_returns_empty_list
    ✗ test_fetch_malformed_json_raises
    ✗ test_rate_limit_429_raises_rate_limit_error
    ✗ test_auth_failure_401_raises_api_error
    ✗ test_auth_failure_403_raises_api_error

tests/integration/test_api_integration.py
    ✗ test_full_api_flow_mocked_success
    ✗ test_api_network_timeout_raises
```

### Green Phase — Implement

- `ProductHuntAPI.__init__(api_token: str)`
- `ProductHuntAPI._build_query(search_term: str, first: int) -> dict`
- `ProductHuntAPI.fetch_ai_products(search_term: str = "AI") -> list[Product]`
- HTTP 429 → `RateLimitError`
- HTTP 401/403 → `APIError`
- JSON decode error → `APIError`

### Refactor Phase

- Extract header construction to helper
- Add configurable timeout parameter
- Add logging

## Exit Criteria

```bash
$ poetry run pytest tests/unit/test_api_client.py tests/integration/test_api_integration.py -v
12 passed
```

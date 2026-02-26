# Sprint 54 — `UniversalLLMTaggingService` (Outer Layer)

## Objective

Implement a failure-safe HTTP-based tagging service that calls an
OpenAI-compatible chat completions endpoint, validates the JSON response, and
enforces tag quality constraints. It **never raises**.

## Why (Clean Architecture)

This is a pure **Frameworks & Drivers** class. It knows about HTTP, JSON, and
LLM API conventions — all mechanism details that must not leak inward. The
`TaggingService` protocol isolates the use case from this complexity entirely.

## Scope

**In:** `src/ph_ai_tracker/tagging.py`,
`tests/unit/test_tagging.py`  
**Out:** No use-case wiring yet (Sprint 55). No real HTTP calls in tests.

---

## TDD Cycle

### Red — write failing tests first

File: `tests/unit/test_tagging.py`

Use `unittest.mock.patch` or `pytest-httpx` to intercept HTTP.

**Happy path:**

```
test_llm_returns_parsed_tags_on_valid_response
    Mock HTTP 200, body {"choices":[{"message":{"content":"{"tags":["ai","tool"]}"}}]}
    → categorize returns ("ai", "tool")

test_llm_tags_are_lowercased
    Mock returns {"tags":["AI","TOOL"]} → ("ai","tool")

test_llm_duplicate_tags_are_deduplicated
    Mock returns {"tags":["ai","ai","tool"]} → ("ai","tool") (length 2)

test_llm_tags_over_20_chars_are_dropped
    Mock returns {"tags":["ai","this-tag-is-way-too-long-for-us"]}
    → ("ai",)

test_llm_temperature_is_zero
    Capture outbound request body; assert "temperature": 0

test_llm_timeout_is_enforced
    Assert the httpx client is constructed with a finite timeout (e.g. ≤ 30s).
```

**Failure safety:**

```
test_llm_returns_empty_on_http_error
    Mock HTTP 500 → ()

test_llm_returns_empty_on_network_timeout
    Mock raises httpx.TimeoutException → ()

test_llm_returns_empty_on_malformed_json
    Mock returns body "not json" → ()

test_llm_returns_empty_when_tags_key_missing
    Mock returns {"result":"ok"} → ()

test_llm_returns_empty_when_tags_not_a_list
    Mock returns {"tags": "ai"} → ()

test_llm_returns_empty_when_tag_is_not_a_string
    Mock returns {"tags": [1, 2]} → ()

test_llm_never_raises_on_any_exception
    Patch httpx to raise an arbitrary Exception → no exception propagates,
    return value is ().
```

**Protocol conformance:**

```
test_llm_satisfies_tagging_service_protocol
    isinstance(UniversalLLMTaggingService(api_key="k", base_url="u"), TaggingService)
```

### Green

Extend `src/ph_ai_tracker/tagging.py`:

```python
class UniversalLLMTaggingService:
    def __init__(self, *, api_key: str, base_url: str, model: str = "gpt-4o-mini",
                 timeout: float = 20.0) -> None: ...

    def categorize(self, product: Product) -> tuple[str, ...]:
        try:
            return self._call(product)
        except Exception:
            return ()

    def _call(self, product: Product) -> tuple[str, ...]: ...
    def _validate(self, data: object) -> tuple[str, ...]: ...
```

`_call` builds the prompt from `product.searchable_text`, sends via `httpx`,
parses JSON, delegates to `_validate`. `_validate` enforces schema and
quality rules. Each helper ≤ 20 lines.

### Refactor

Move shared tag-cleaning logic (lowercase, max-20-char filter, dedup) into a
module-level `_clean_tags(raw: list) -> tuple[str, ...]` helper reused by
both `_validate` and the `Product._coerce_tags` in models.

---

## Definition of Done

- [x] All new tests green (no live HTTP).
- [x] `categorize` returns `tuple[str, ...]` in all paths.
- [x] `categorize` never raises under any injected failure.
- [x] Temperature is always 0.
- [x] Tags are lowercase, unique, ≤ 20 characters.
- [x] `make bundle` passes.

# Sprint 56 — Bootstrap Tagging Service Injection

## Objective

Wire the outermost layer (bootstrap / CLI entry point) to read the
`OPENAI_API_KEY` environment variable (or equivalent) and inject either a
`UniversalLLMTaggingService` or a `NoOpTaggingService` into the use case.

## Why (Clean Architecture)

Environment variable reading and object construction are **Frameworks &
Drivers** concerns. They belong in the outermost ring. The application and
entity layers must remain completely unaware of how the tagging service is
selected.

## Scope

**In:** `src/ph_ai_tracker/bootstrap.py`,
`src/ph_ai_tracker/__main__.py`,
`tests/unit/test_bootstrap.py`  
**Out:** No new protocol or entity changes.

---

## TDD Cycle

### Red — write failing tests first

File: `tests/unit/test_bootstrap.py`

```
test_build_tagging_service_returns_noop_when_no_key
    monkeypatch removes OPENAI_API_KEY from env.
    build_tagging_service(env={}) → isinstance(result, NoOpTaggingService)

test_build_tagging_service_returns_llm_when_key_present
    env has OPENAI_API_KEY="sk-test".
    build_tagging_service(env={"OPENAI_API_KEY":"sk-test"})
    → isinstance(result, UniversalLLMTaggingService)

test_build_tagging_service_returns_noop_for_blank_key
    env has OPENAI_API_KEY="   ".
    → isinstance(result, NoOpTaggingService)

test_build_tagging_service_base_url_configurable
    env has OPENAI_API_KEY="k", OPENAI_BASE_URL="https://custom/v1".
    Returned LLM service uses that base_url (inspect attribute).

test_build_tagging_service_default_base_url
    env has OPENAI_API_KEY="k", no OPENAI_BASE_URL.
    service.base_url == "https://api.openai.com/v1"

test_existing_build_provider_unchanged
    build_provider(strategy="scraper", api_token=None) still returns
    ProductHuntScraper (regression guard).
```

### Green

Add to `bootstrap.py`:

```python
_DEFAULT_BASE_URL = "https://api.openai.com/v1"

def build_tagging_service(
    env: dict[str, str] | None = None,
) -> TaggingService:
    """Return the appropriate TaggingService based on env config."""
    if env is None:
        env = dict(os.environ)
    key = env.get("OPENAI_API_KEY", "").strip()
    if not key:
        return NoOpTaggingService()
    base_url = env.get("OPENAI_BASE_URL", _DEFAULT_BASE_URL)
    return UniversalLLMTaggingService(api_key=key, base_url=base_url)
```

Update `__main__.py` (`_run` or `main`) to call `build_tagging_service()` and
pass the result to `AIProductTracker(provider=..., tagging_service=...)`.

### Refactor

`build_tagging_service` must be ≤ 20 lines. No logic duplicated between
bootstrap and any other module.

---

## Definition of Done

- [x] All new bootstrap tests green.
- [x] `__main__` passes `tagging_service` to `AIProductTracker`.
- [x] No existing CLI behavior changed (backward compatible).
- [x] `make bundle` passes.
- [x] All pre-existing tests still green.

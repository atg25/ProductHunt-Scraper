# Sprint 59 — E2E Tests: Positive and Negative Scenarios

## Objective

Write end-to-end tests that exercise the full CLI / programmatic entry point
with real bootstrap logic, mocked HTTP (both Product Hunt and LLM), and a
real in-memory SQLite database.

The positive scenario confirms the happy path works top to bottom.
The negative scenarios confirm the system degrades gracefully under every
expected failure mode.

## Why (Clean Architecture)

E2E tests are the **acceptance gate** for the entire architecture. They live
at the outermost ring — they are the "main component" of tests. They confirm
that the Dependency Rule has been respected: the system runs, all layers
cooperate, and no inner layer has been corrupted by outer concerns.

## Scope

**In:** `tests/e2e/test_e2e_positive.py` (extend existing),
`tests/e2e/test_e2e_negative.py` (extend existing)  
**Out:** No real network calls. Docker not required.

---

## TDD Cycle

### Positive E2E Tests

File: `tests/e2e/test_e2e_positive.py`

```
test_e2e_scraper_with_noop_tagging_returns_products
    Mock ProductHunt HTML response.
    Run with strategy="scraper", no OPENAI_API_KEY.
    result.products non-empty.
    Each product.tags == ().

test_e2e_scraper_with_llm_tagging_returns_tagged_products
    Mock ProductHunt HTML response.
    Mock LLM HTTP 200 → {"tags":["productivity","ai"]}.
    Set OPENAI_API_KEY="sk-test" in env.
    result.products non-empty.
    Each product.tags is a non-empty tuple.

test_e2e_newsletter_from_live_tracker_run
    Mock ProductHunt scraper returns 5 products (varied votes).
    Mock LLM returns tags.
    Run tracker → format with NewsletterFormatter.
    newsletter["products"] has 5 entries.
    newsletter["products"][0]["votes"] >= newsletter["products"][-1]["votes"].
    newsletter["top_tags"] is a list.

test_e2e_persisted_products_have_tags_in_output_json
    Run full pipeline with DB persistence.
    Reload products from DB via storage layer.
    Product loaded from DB carries correct tags.
```

### Negative E2E Tests

File: `tests/e2e/test_e2e_negative.py`

```
test_e2e_llm_down_does_not_break_pipeline
    Mock ProductHunt scraper returns 3 products.
    Mock LLM HTTP raises ConnectionError.
    Pipeline completes → result.error is None, result.products non-empty.
    Each product.tags == () (graceful degradation).

test_e2e_missing_api_key_uses_noop_tagging
    Remove OPENAI_API_KEY from env.
    Run pipeline → completes without error.
    Tags are () for all products.

test_e2e_llm_returns_malformed_json_gracefully
    Mock LLM returns 200 with body "oops not json".
    Pipeline completes → tags are () for all products.
    result.error is None.

test_e2e_llm_returns_wrong_schema_gracefully
    Mock LLM returns {"result":"ok"} (missing "tags" key).
    Pipeline completes → tags are ().

test_e2e_llm_returns_oversized_tags_are_filtered
    Mock LLM returns {"tags":["ok","this-is-way-too-long-indeed-over-twenty-chars"]}.
    Pipeline completes → only ("ok",) in tags.
    No exception raised.

test_e2e_scraper_failure_produces_failure_result_not_exception
    Mock ProductHunt scraper raises ScraperError.
    result.error is not None.
    result.products == ().
    No exception propagates to caller.

test_e2e_newsletter_from_failed_tracker_run_handles_empty_gracefully
    Use failure TrackerResult (products=()), format with NewsletterFormatter.
    newsletter["total_products"] == 0.
    newsletter["products"] == [].
    No exception.
```

### Green

If any test fails after the previous sprints, diagnose and fix the
appropriate layer (do not patch tests to hide bugs).

### Refactor

Ensure fixtures shared between positive and negative suites live in
`tests/conftest.py` or a `tests/e2e/conftest.py`.

---

## Definition of Done

- [x] All positive E2E tests green.
- [x] All negative E2E tests green.
- [x] No real HTTP or real disk I/O (except in-memory SQLite).
- [x] CLI `--no-persist` flag still works in E2E context.
- [x] `make bundle` passes.
- [x] Full suite (`pytest -q`) shows 0 failures, 0 errors.

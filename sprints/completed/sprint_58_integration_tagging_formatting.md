# Sprint 58 — Integration Tests: Tagging + Formatting Pipeline

## Objective

Write integration tests that exercise the full chain:
`AIProductTracker.get_products` (with a real injected `NoOpTaggingService` or
stubbed `TaggingService`) → `NewsletterFormatter.format`.

These tests verify that the layers cooperate correctly through their contracts,
without any real network I/O.

## Why (Clean Architecture)

Unit tests verify layers in isolation. Integration tests at the seam between
application layer (tracker), outer mechanisms (tagging), and interface adapters
(formatter) confirm that the wiring is correct without coupling to specific
implementations.

## Scope

**In:** `tests/integration/test_tagging_formatter_pipeline.py` (new file)  
**Out:** No real HTTP. No SQLite. No CLI.

---

## TDD Cycle

### Red — write failing tests first

File: `tests/integration/test_tagging_formatter_pipeline.py`

```
test_pipeline_noop_tagging_produces_empty_tags_in_newsletter
    Provider returns two products.
    Tracker uses NoOpTaggingService.
    Newsletter["products"] each have tags == [].

test_pipeline_stub_tagging_tags_appear_in_newsletter
    Provider returns Product("AI Tool A", votes_count=10),
                     Product("Data Widget", votes_count=5).
    StubTagger returns ("ai",) for any product.
    Newsletter top_tags == [{"tag":"ai","count":2}].

test_pipeline_sorting_votes_desc_preserved_in_newsletter
    Products with votes 5, 10, 1 → newsletter products[0].votes == 10.

test_pipeline_total_products_matches_provider_output
    Provider returns 3 products → newsletter["total_products"] == 3.

test_pipeline_tagging_failure_does_not_break_newsletter
    Stub tagger raises on first product, returns ("tool",) on second.
    Newsletter produced (not raised); first product tags == [],
    second product tags == ["tool"].
    total_products == 2.

test_pipeline_generated_at_is_recent
    newsletter["generated_at"] parses to datetime within 5 seconds of now.

test_pipeline_empty_provider_returns_valid_newsletter_structure
    Provider returns [].
    Newsletter has keys: generated_at, total_products, top_tags, products.
    total_products == 0, products == [], top_tags == [].
```

### Green

No new source code required — these tests exercise existing code.
If any test fails, diagnose and fix the appropriate source module.

### Refactor

Ensure a `StubProvider` and `StubTaggingService` fixture is defined in or
imported from a shared conftest so it can be reused in e2e tests.

---

## Definition of Done

- [x] All integration tests green.
- [x] Tests use no real HTTP, no real SQLite.
- [x] Tests import only from `ph_ai_tracker.*` — no reaching into test internals.
- [x] `make bundle` passes.
- [x] All pre-existing tests still green.

# ph_ai_tracker — Data Pipeline Sprint Plan

## Scope

This sprint plan replaces the earlier package/scaffolding plan and targets the current class assignment architecture:

1. Save scraper output to SQLite.
2. Run scraper on a repeating cron schedule.
3. Containerize scraper + cron scheduler with Docker.
4. Persist SQLite data on a Docker volume.

Originally out of scope: API service layer. Now included via Sprint 64.

---

## Sprint Sequence Overview

1. Sprint 1 — SQLite persistence foundation
2. Sprint 2 — Scheduled execution via cron
3. Sprint 3 — Docker containerization + persistent volume
4. Sprint 4 — Reliability, failure handling, and observability
5. Sprint 5 — Delivery documentation and runbook
6. Sprint 6 — Final demo hardening and submission packaging
7. Sprint 7 — Bundle discipline & repository hygiene _(Knuth #1)_
8. Sprint 8 — Literate programming & narrative documentation _(Knuth #2)_
9. Sprint 9 — Scraper robustness & graceful DOM degradation _(Knuth #3)_
10. Sprint 10 — Database schema integrity & referential enforcement _(Knuth #4)_
11. Sprint 11 — Explicit fallback warnings & configuration clarity _(Knuth #5)_
12. Sprint 12 — API client SRP: extract `RateLimitParser`, `StrictAIFilter` _(Uncle Bob Letter 1, issues #1 & #3)_
13. Sprint 13 — Scraper decomposition: `NextDataExtractor`, `DOMFallbackExtractor`, `ProductEnricher` _(Uncle Bob Letter 1, issue #2)_
14. Sprint 14 — DRY CLI: shared `add_common_arguments` + `CommonArgs` _(Uncle Bob Letter 1, issue #4)_
15. Sprint 15 — Storage SQL helpers: extract `_insert_run_record`, `_insert_product_snapshot` _(Uncle Bob Letter 1, issue #5)_
16. Sprint 16 — _(Uncle Bob Letter 2 — superseded; see Sprints 27–29)_
17. Sprint 17 — _(Uncle Bob Letter 2 — superseded; see Sprints 27–29)_
18. Sprint 18 — _(Uncle Bob Letter 2 — superseded; see Sprints 27–29)_
19. Sprint 19 — Strict empty-string search term enforcement _(Uncle Bob Letter 3, issue #1)_
20. Sprint 20 — Narrow broad `Exception` catches to precise exception types _(Uncle Bob Letter 3, issue #2)_
21. Sprint 21 — Split `_passes_filter` into leaf predicates _(Uncle Bob Letter 3, issue #3)_
22. Sprint 22 — `Product.searchable_text` property: eliminate haystack duplication _(Uncle Bob Letter 4, issue #1)_
23. Sprint 23 — Generic `_parse_env_var`: eliminate int/float cast duplication _(Uncle Bob Letter 4, issue #2)_
24. Sprint 24 — Pagination constants: name magic numbers `_PAGINATION_MULTIPLIER`, `_MIN_FETCH_SIZE`, `_MAX_FETCH_SIZE` _(Uncle Bob Letter 4, issue #3)_
25. Sprint 25 — Fix broken bundle manifest: add `cli.py` to `SECTION_3_PRODUCTION` _(Uncle Bob Letter 5, issue #1)_
26. Sprint 26 — Dependency Inversion Principle: `ProductProvider` Protocol + injected composition root _(Uncle Bob Letter 5, issue #2)_
27. Sprint 27 — OCP: Eliminate strategy switch statement → polymorphic `FallbackProvider` / `_NoTokenProvider` _(Uncle Bob Letter 2, issue #1)_
28. Sprint 28 — Remove ASCII banner comments from `scraper.py` _(Uncle Bob Letter 2, issue #2)_
29. Sprint 29 — ProviderFactory: DRY CLI layer with `build_provider()` _(Uncle Bob Letter 2, issue #3)_
30. Sprint 30 — Narrow Exception Catch in `FallbackProvider` _(Uncle Bob Letter 6, issue #1)_
31. Sprint 31 — Remove Lingering Banner Comments _(Uncle Bob Letter 6, issue #2)_
32. Sprint 32 — Centralize Domain Default Constants _(Uncle Bob Letter 6, issue #3)_
33. Sprint 33 — Enforce `Product.name` Invariant via `__post_init__` _(Uncle Bob Letter 7, issue #1)_
34. Sprint 34 — Introduce `QueryContext` to Eliminate Payload Pollution _(Uncle Bob Letter 7, issue #2)_
35. Sprint 35 — Delete `_product_haystack` Pointless Indirection _(Uncle Bob Letter 7, issue #3)_
36. Sprint 36 — Remove Banner Comments from the Test Suite _(Uncle Bob Letter 7, issue #4)_
37. Sprint 37 — Purge All Sprint-Reference Labels from the Test Suite _(Uncle Bob Letter 8, issue #1)_
38. Sprint 38 — Delete the Ghost-Hunting Test _(Uncle Bob Letter 8, issue #2)_
39. Sprint 39 — DRY `from_dict`: Trust `__post_init__` as the Single Invariant Gatekeeper _(Uncle Bob Letter 8, issue #3)_
40. Sprint 40 — Delete Dead Shims from `ProductHuntScraper`; redirect tests to extractor classes _(Uncle Bob Letter 9, issue #1)_
41. Sprint 41 — Promote `_build_query` to `@staticmethod`; eliminate `__new__` hack _(Uncle Bob Letter 9, issue #2)_
42. Sprint 42 — Fix the dishonest docstring in `AIProductTracker` _(Uncle Bob Letter 9, issue #3)_
43. Sprint 43 — `TrackerResult.is_transient`: restore type safety; delete `_is_transient_error` string parsing _(Uncle Bob Letter 10, issue #1)_
44. Sprint 44 — Constructor injection for extractors; fix encapsulation violation in scraper tests _(Uncle Bob Letter 10, issue #2)_
45. Sprint 45 — Split `cli.py`: extract `build_provider` to `bootstrap.py`; eliminate `noqa: E402` suppressions _(Uncle Bob Letter 10, issue #3)_
46. Sprint 46 — Law of Demeter: extract `_parse_topic_edges` / `_parse_global_edges`; eliminate chained `.get()` train wreck in `_extract_edges` _(Uncle Bob Letter 11, issue #1)_
47. Sprint 47 — Data Clump: absorb `search_term` + `limit` into `TrackerResult`; remove those params from `SQLiteStore.save_result` _(Uncle Bob Letter 11, issue #2)_
48. Sprint 48 — Inappropriate Intimacy: delete private-method tests for `_insert_run_record`, `_insert_all_snapshots`, and `_build_query`; replace `_build_query` test with public-contract test _(Uncle Bob Letter 11, issue #3)_
49. Sprint 49 — Temporal Coupling: remove `self.init_db()` from `save_result`; call `init_db()` explicitly in `__main__.py` and `scheduler.py` at startup _(Uncle Bob Letter 11, issue #4)_
50. Sprint 50 — Add `tags` field to `Product` entity; `_coerce_tags` helper; `to_dict` / `from_dict` updates _(Uncle Bob Letter 12, issue #1)_
51. Sprint 51 — Pure `canonical_key(product)` function: URL-first normalization with name fallback; extract from storage _(Uncle Bob Letter 12, issue #2)_
52. Sprint 52 — `TaggingService` Protocol in application boundary (`protocols.py`) _(Uncle Bob Letter 12, issue #3)_
53. Sprint 53 — `NoOpTaggingService`: null-object outer-layer implementation in `tagging.py` _(Uncle Bob Letter 12, issue #4)_
54. Sprint 54 — `UniversalLLMTaggingService`: failure-safe HTTP tagging, JSON schema validation, quality constraints _(Uncle Bob Letter 12, issue #5)_
55. Sprint 55 — Use-case enrichment: `AIProductTracker` accepts `TaggingService`, enriches products, failure-safe _(Uncle Bob Letter 12, issue #6)_
56. Sprint 56 — Bootstrap injection: env-var-driven tagging service selection in `bootstrap.py` and `__main__.py` _(Uncle Bob Letter 12, issue #7)_
57. Sprint 57 — `NewsletterFormatter` presenter: sort by votes DESC / name ASC, tag frequencies, full field contract _(Uncle Bob Letter 12, issue #8)_
58. Sprint 58 — Integration tests: tagging + formatting pipeline through public contracts, no real I/O _(Uncle Bob Letter 12, issue #9)_
59. Sprint 59 — E2E tests: positive (full pipeline with mock LLM) and negative (LLM down, bad JSON, missing key, scraper failure) _(Uncle Bob Letter 12, issue #10)_
60. Sprint 60 — Bundle audit: register `tagging.py` and `formatters.py` in review bundle manifests _(Uncle Bob Letter 13, issue #1)_
61. Sprint 61 — Remove exception muzzle in tracker enrichment path; trust service contract _(Uncle Bob Letter 13, issue #2)_
62. Sprint 62 — Wire `NewsletterFormatter` into CLI stdout path _(Uncle Bob Letter 13, issue #3)_
63. Sprint 63 — Wire `NewsletterFormatter` into scheduler stdout path _(Uncle Bob Letter 13, issue #4)_
64. Sprint 64 — Expose FastAPI HTTP endpoints for health, search, and history

---

## Sprint Dependencies

- Sprint 2 depends on Sprint 1 (scheduler needs write path).
- Sprint 3 depends on Sprint 2 (containerized schedule path).
- Sprint 4 depends on Sprints 1–3 (hardening full pipeline).
- Sprint 5 depends on Sprints 1–4 (document final behavior).
- Sprint 6 depends on all prior sprints.
- Sprint 7 is independent; run immediately (housekeeping).
- Sprint 8 depends on Sprint 7 (clean bundle makes docs review meaningful).
- Sprint 9 depends on Sprint 6 (builds on existing scraper test suite).
- Sprint 10 depends on Sprint 1 (extends storage layer).
- Sprint 11 depends on Sprint 9 (tracker warning relies on solid fallback path).
- Sprint 12 is independent of 9–11; targets `api_client.py` only.
- Sprint 13 depends on Sprint 9 (extends existing scraper extraction layer).
- Sprint 14 is independent; targets CLI modules only.
- Sprint 15 depends on Sprint 10 (extends storage integrity work).
- Sprints 19–21 depend on Sprints 12–15 (refine the refactored adapter layer).
- Sprints 22–24 are independent of each other; each targets a single module.
- Sprint 25 is independent; targets `scripts/build_bundle.py` only.
- Sprint 26 depends on Sprints 12–14 (Protocol sits above refactored adapters); must run after Sprint 25 so `protocols.py` appears in the bundle.
- Sprint 27 depends on Sprint 26 (OCP polymorphism builds on the injected `ProductProvider` foundation).
- Sprint 28 is independent; purely cosmetic change to `scraper.py`.
- Sprint 29 depends on Sprint 27 (factory constructs the new `FallbackProvider` / `_NoTokenProvider` types).
- Sprint 30 depends on Sprint 27 (modifies the `FallbackProvider` created in Sprint 27).
- Sprint 31 is independent; purely cosmetic change to `api_client.py` and `cli.py`.
- Sprint 32 is independent; extracts constants and updates signatures across multiple files.
- Sprint 33 is independent; adds `__post_init__` guard to `models.py` only.
- Sprint 34 depends on Sprints 12 and 32 (refines the refactored `api_client.py` built across those sprints).
- Sprint 35 depends on Sprint 22 (`_product_haystack` delegates to `searchable_text`, introduced in Sprint 22) and Sprint 34 (Sprint 34 should run first to stabilise `api_client.py` before this further trims it).
- Sprint 36 is independent; purely cosmetic changes to test files only.
- Sprint 37 depends on Sprint 36 (finishes the work Sprint 36 left incomplete; same set of test files).
- Sprint 38 is independent; deletes a single test function from `tests/unit/test_api_client.py`.
- Sprint 39 depends on Sprint 33 (`__post_init__` guard must already exist before the `from_dict` pre-check can be safely removed).
- Sprint 40 depends on Sprint 13 (the extractor classes `NextDataExtractor`, `DOMFallbackExtractor`, `ProductEnricher` were introduced there; the shims are a residue of that sprint's test-writing).
- Sprint 41 depends on Sprint 34 (`_build_query` received its current signature returning `QueryContext` in that sprint).
- Sprint 42 depends on Sprint 30 (Sprint 30 narrowed the exception catches that define the exact guarantee `get_products` can actually make).
- Sprint 43 depends on Sprint 32 (centralised constants in `constants.py`) and Sprint 42 (truthful docstring establishes the contract that `is_transient` formalises).
- Sprint 44 depends on Sprint 13 (the three extractor classes being injected were introduced there) and Sprint 40 (shim methods removed, confirming extractors are the right seam).
- Sprint 45 depends on Sprint 29 (`build_provider` was created in `cli.py` in Sprint 29; this sprint moves it to its own module) and Sprint 14 (`CommonArgs` / `add_common_arguments` — the argument-parsing half that stays in `cli.py`).
- Sprint 46 depends on Sprint 34 (`_extract_edges` received its current form — returning from the topic or global shape — in that sprint) and Sprint 41 (`@staticmethod` promotion pattern is established).
- Sprint 47 depends on Sprint 43 (`TrackerResult` was enriched with `is_transient` in Sprint 43; absorbing `search_term`/`limit` follows the same pattern) and Sprint 15 (the private `_insert_run_record` helpers introduced there are the ones whose signatures change here).
- Sprint 48 depends on Sprint 47 (`_insert_run_record` signature changes in Sprint 47 first, so Sprint 48 deletes the tests that reference the old signature) and Sprint 41 (`_build_query` is the static method tested in isolation here).
- Sprint 49 depends on Sprint 47 (`save_result` signature is stabilised in Sprint 47 before the `init_db` side-effect is removed here).
- Sprint 50 is independent; adds a new field to `Product` only.
- Sprint 51 depends on Sprint 50 (`Product` must have its final field set before the pure `canonical_key` function is extracted from storage).
- Sprint 52 depends on Sprint 50 (`TaggingService.categorize` signature references `Product`; the `tags` field must already exist).
- Sprint 53 depends on Sprint 52 (`NoOpTaggingService` must satisfy the `TaggingService` protocol defined in Sprint 52).
- Sprint 54 depends on Sprints 52 and 53 (`UniversalLLMTaggingService` implements the same protocol; `NoOpTaggingService` is the regression baseline for tests).
- Sprint 55 depends on Sprints 52, 53, and 54 (use case wires the tagging services from all three previous sprints).
- Sprint 56 depends on Sprints 53, 54, and 55 (bootstrap selects between the two implementations and injects into the wired use case).
- Sprint 57 depends on Sprint 50 (`NewsletterFormatter` reads `product.tags`; field must exist).
- Sprint 58 depends on Sprints 55 and 57 (exercises the full tracker → formatter pipeline end-to-end).
- Sprint 59 depends on Sprints 56, 57, and 58 (requires bootstrap injection, formatter, and integration seam all confirmed green).
- Sprint 60 depends on Sprint 57 and Sprint 58 (bundle must include formatter/tagging code and associated tests).
- Sprint 61 depends on Sprint 55 (removes broad exception handling from enrichment path introduced there).
- Sprint 62 depends on Sprint 57 and Sprint 56 (CLI output wiring requires formatter and bootstrap tagging injection).
- Sprint 63 depends on Sprint 62 and Sprint 57 (scheduler output made consistent with CLI newsletter output).
- Sprint 64 depends on Sprint 63 and storage simplification (HTTP API reuses tracker/scheduler output model and single-table history contract).

---

## Definition of Done (Project-Level)

- Scraper writes structured data to SQLite consistently.
- Cron runs scraper repeatedly without manual intervention.
- Dockerized deployment persists SQLite data across restarts using a named volume.
- Tests cover positive and negative pipeline behavior.
- A new user can run the full pipeline from docs only.

---

## Knuth Review Resolution Summary (Sprints 7–11)

| #   | Knuth Concern                                     | Sprint | Key Change                                                                                           |
| --- | ------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------- |
| 1   | Bundle ships `.venv` / cache artefacts            | 7      | `make bundle` exclusion list; `.gitignore` / `.dockerignore` updated                                 |
| 2   | No narrative "why" in code                        | 8      | Docstrings + `--doctest-modules` CI check on all public APIs                                         |
| 3   | Brittle DOM parser, no graceful degradation       | 9      | Isolated extraction layers; `_log.warning` on layout change; `ScraperError` only on network failures |
| 4   | App-level deduplication instead of DB constraints | 10     | `PRAGMA foreign_keys = ON` on every connection; `IntegrityError` → `StorageError`; FK tests          |
| 5   | Silent auto-fallback masks token misconfiguration | 11     | `warnings.warn(RuntimeWarning)` + `_log.warning` on every missing-token fallback                     |

---

## Uncle Bob Review Resolution Summary (Sprints 12–15)

| #   | Uncle Bob Concern                                             | Sprint | Key Change                                                                                              |
| --- | ------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------- |
| 1   | `fetch_ai_products` is 173 lines; violates SRP                | 12     | Extract `RateLimitParser`, `StrictAIFilter`; `fetch_ai_products` ≤ 20 lines                             |
| 2   | `ProductHuntScraper` is a God Object                          | 13     | Extract `NextDataExtractor`, `DOMFallbackExtractor`, `ProductEnricher`; scraper becomes coordinator     |
| 3   | Comment explains regex instead of code expressing intent      | 12     | `StrictAIFilter.is_match()` replaces inline regex block + comment                                       |
| 4   | Duplicated `argparse` / `os.environ` reads in two CLI modules | 14     | New `cli.py` with `add_common_arguments(parser)` and `CommonArgs` dataclass                             |
| 5   | `save_result` (72 lines) mixes SQL strings with domain logic  | 15     | Extract `_insert_run_record`, `_insert_product_snapshot`, `_insert_all_snapshots`, `_derive_run_status` |

---

## Uncle Bob Letter 3 Resolution Summary (Sprints 19–21)

| #   | Uncle Bob Concern                                           | Sprint | Key Change                                                                          |
| --- | ----------------------------------------------------------- | ------ | ----------------------------------------------------------------------------------- |
| 1   | Empty-string search term passes silently into network calls | 19     | `ValueError` raised on blank `search_term`; tests for empty-string edge cases       |
| 2   | Bare `except Exception` swallows unknown failures silently  | 20     | Replace broad catches with precise `APIError`, `ScraperError`, `StorageError` types |
| 3   | `_passes_filter` is one compound predicate, hard to extend  | 21     | Split into leaf predicates; compose with `all(pred(p) for pred in _PREDICATES)`     |

---

## Uncle Bob Letter 4 Resolution Summary (Sprints 22–24)

| #   | Uncle Bob Concern                                                        | Sprint | Key Change                                                                             |
| --- | ------------------------------------------------------------------------ | ------ | -------------------------------------------------------------------------------------- |
| 1   | Feature Envy: `_product_haystack` duplicated in 3 places                 | 22     | `Product.searchable_text` property on the model; all three sites replaced with it      |
| 2   | DRY violation: `_parse_int_env` / `_parse_float_env` differ only in cast | 23     | Extract `_parse_env_var(key, default, cast)`; wrappers become one-liners               |
| 3   | Magic numbers in `min(max(limit * 5, 20), 50)` have no names             | 24     | `_PAGINATION_MULTIPLIER = 5`, `_MIN_FETCH_SIZE = 20`, `_MAX_FETCH_SIZE = 50` constants |

---

## Uncle Bob Letter 2 Resolution Summary (Sprints 27–29)

| #   | Uncle Bob Concern                                                      | Sprint | Key Change                                                                                                                        |
| --- | ---------------------------------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `get_products` contains an `if strategy ==` switch — violates OCP      | 27     | `FallbackProvider` + `_NoTokenProvider` in `protocols.py`; `tracker.py` reduced to a single `provider: ProductProvider` injection |
| 2   | ASCII banner comment blocks in `scraper.py` clutter the file           | 28     | Three banner blocks removed; code reads as a flat, cohesive module                                                                |
| 3   | Provider-building logic duplicated in `__main__.py` and `scheduler.py` | 29     | `build_provider(*, strategy, api_token)` factory extracted to `cli.py`; both composition roots delegate to the single factory     |

---

## Uncle Bob Letter 5 Resolution Summary (Sprints 25–26)

| #   | Uncle Bob Concern                                                       | Sprint | Key Change                                                                                                                                  |
| --- | ----------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `cli.py` absent from bundle; Uncle Bob thinks the module does not exist | 25     | Add `SRC / "cli.py"` to `SECTION_3_PRODUCTION` in `build_bundle.py`; bundle reports 10 prod files                                           |
| 2   | `tracker.py` (Use-Case) directly imports + instantiates adapter classes | 26     | `ProductProvider` Protocol in `protocols.py`; tracker accepts injected providers; `scheduler.py` and `__main__.py` become Composition Roots |

---

## Uncle Bob Letter 6 Resolution Summary (Sprints 30–32)

| #   | Uncle Bob Concern                                               | Sprint | Key Change                                                                                                     |
| --- | --------------------------------------------------------------- | ------ | -------------------------------------------------------------------------------------------------------------- |
| 1   | Blanket `Exception` catch in `FallbackProvider` swallows bugs   | 30     | Change `except Exception:` to `except APIError:` in `protocols.py`; remove `# noqa: BLE001`                    |
| 2   | Lingering ASCII banner comments in `api_client.py` and `cli.py` | 31     | Delete the remaining `# ---` banner blocks                                                                     |
| 3   | Scattered default values (`"AI"`, `20`) violate DRY             | 32     | Extract `DEFAULT_SEARCH_TERM` and `DEFAULT_LIMIT` into `constants.py`; import and use them across the codebase |

---

## Uncle Bob Letter 7 Resolution Summary (Sprints 33–36)

| #   | Uncle Bob Concern                                                                                  | Sprint | Key Change                                                                                                                                                 |
| --- | -------------------------------------------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `Product` documents a name invariant but does not enforce it; blames the caller                    | 33     | Add `__post_init__` to `Product` raising `ValueError` on empty/whitespace name; fix docstring; add targeted tests                                          |
| 2   | `_build_query` injects private context into the network payload dict; `_pop_meta` removes it again | 34     | Introduce `QueryContext` dataclass with `payload` and `local_filter` fields; `_build_query` returns it; `_pop_meta` deleted; retry path uses `ctx.payload` |
| 3   | `_product_haystack` is a one-line wrapper that just returns `p.searchable_text`                    | 35     | Delete `_product_haystack`; inline `p.searchable_text` in `_passes_strict_filter`                                                                          |
| 4   | `# ---` banner comment blocks remain throughout the test suite                                     | 36     | Delete all `# ---` / label / `# ---` three-line banner patterns from all 14 affected test files; module docstrings are preserved                           |

---

## Uncle Bob Letter 10 Resolution Summary (Sprints 43–45)

| #   | Uncle Bob Concern                                                                                              | Sprint | Key Change                                                                                                                                                                                      |
| --- | -------------------------------------------------------------------------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `TrackerResult.error` is a string; scheduler does substring matching to infer transience — Primitive Obsession | 43     | Add `is_transient: bool = False` to `TrackerResult`; `tracker.py` tags failure based on exception type; delete `_TRANSIENT_TOKENS` + `_is_transient_error` from `scheduler.py`                  |
| 2   | Tests mutate `s._next_data` directly after construction — Encapsulation Violation                              | 44     | Add `next_data_extractor`, `dom_fallback_extractor`, `enricher` kwargs to `ProductHuntScraper.__init__`; rewrite three tests to inject through the constructor                                  |
| 3   | `build_provider` lives in `cli.py` causing mid-file `# noqa: E402` imports; `cli.py` has two responsibilities  | 45     | Create `bootstrap.py` with `build_provider`; `cli.py` retains only argument-parsing; `__main__.py` + `scheduler.py` import from `bootstrap`; `test_bootstrap.py` created; all `noqa: E402` gone |

---

## Uncle Bob Letter 11 Resolution Summary (Sprints 46–49)

| #   | Uncle Bob Concern                                                                                                                                        | Sprint | Key Change                                                                                                                                                                                               |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Train wreck: `((data.get("topic") or {}).get("posts") or {}).get("edges")` — three-level chained `.get()` in `_extract_edges`                            | 46     | Extract `_parse_topic_edges` and `_parse_global_edges` `@staticmethod` helpers; `_extract_edges` calls them by name; `_node_to_product` gains `_parse_topic_edges_from_node`; 7 new targeted tests added |
| 2   | `result`, `search_term`, and `limit` form a data clump: travelling together through every `save_result` / `_commit_run` / `_insert_run_record` signature | 47     | Add `search_term: str = ""` and `limit: int = 0` to `TrackerResult`; `tracker.py` populates them; `SQLiteStore.save_result` drops those params; `__main__.py` + `scheduler.py` call sites simplified     |
| 3   | Tests call private `_insert_run_record`, `_insert_all_snapshots`, and `_build_query` directly — inappropriate intimacy                                   | 48     | Delete 2 private-storage tests and 1 private-API test; replace `_build_query` test with `test_fetch_strips_and_lowercases_search_term` through the public interface                                      |
| 4   | `save_result` calls `self.init_db()` on every write — temporal coupling; schema init hidden inside a domain write operation                              | 49     | Remove `self.init_db()` from `save_result`; call `store.init_db()` explicitly in `_try_persist` (`__main__.py`) and `run_once` (`scheduler.py`); update 5 storage tests to call `init_db()` upfront      |

---

## Uncle Bob Letter 9 Resolution Summary (Sprints 40–42)

| #   | Uncle Bob Concern                                                                                                        | Sprint | Key Change                                                                                                                                                              |
| --- | ------------------------------------------------------------------------------------------------------------------------ | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Three shim methods in `ProductHuntScraper` exist solely to satisfy stale tests — Test-Induced Design Damage              | 40     | Delete `_extract_next_data_products`, `_extract_dom_products`, `_enrich_from_product_page`; delete 8 shim-calling tests; add 5 new direct extractor tests               |
| 2   | `_build_query` never references `self` but is an instance method; test bypasses constructor with `__new__` to call it    | 41     | Add `@staticmethod`; remove `self` from signature; test calls `ProductHuntAPI._build_query(…)` directly; `__new__` hack eliminated                                      |
| 3   | Class and method docstrings promise `get_products` _never raises_ — a lie; only three known domain exceptions are caught | 42     | Update both docstrings to the qualified truth: known domain exceptions are captured; unexpected failures may still propagate; production `except` clauses are unchanged |

---

## Uncle Bob Letter 8 Resolution Summary (Sprints 37–39)

| #   | Uncle Bob Concern                                                                                                                       | Sprint | Key Change                                                                                                                                                         |
| --- | --------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Sprint 36 removed dashes but left floating `# Label — Sprint N` and `Sprint N:` module docstring prefixes intact — malicious compliance | 37     | Delete all 15 remaining standalone `# … Sprint …` comment lines; strip sprint-number prefix/suffix from 7 module docstrings; `grep "Sprint [0-9]" tests/` → 0 hits |
| 2   | `test_passes_filter_no_longer_exists` is a ghost-hunting test proving a historical deletion, not current behaviour                      | 38     | Delete the test entirely; test count drops by exactly 1                                                                                                            |
| 3   | `from_dict` validates `name` manually before calling `cls(…)`, duplicating `__post_init__` with a different error message               | 39     | Remove the two-line pre-check from `from_dict`; use `name=str(data.get("name") or "")` so `__post_init__` is the single authoritative gatekeeper                   |

---

## Uncle Bob Letter 12 Resolution Plan (Sprints 50–59)

| #   | Uncle Bob Concern                                                                             | Sprint | Planned Change                                                                                                                                       |
| --- | --------------------------------------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `Product` has no `tags` field; enrichment data has nowhere to live in the entity layer        | 50     | Add `tags: tuple[str, ...]` to `Product`; `_coerce_tags` helper; `to_dict` and `from_dict` updated; full unit-test coverage                          |
| 2   | Canonical key logic is buried inside a SQL helper; entities cannot be deduplicated without DB | 51     | Extract `canonical_key(product) -> str` pure function into `models.py`; full URL-normalization and name-fallback rules; idempotence tests            |
| 3   | No `TaggingService` abstraction; tagging cannot be injected → Dependency Rule violation       | 52     | Define `@runtime_checkable TaggingService(Protocol)` in `protocols.py`; unit tests for protocol conformance                                          |
| 4   | System has no safe default when LLM key is absent; null check required at every call site     | 53     | `NoOpTaggingService` in `tagging.py`; null object patterns means callers never branch on `None`; parametrised unit tests                             |
| 5   | No LLM tagging mechanism exists; tags always empty                                            | 54     | `UniversalLLMTaggingService` in `tagging.py`; never raises; validates JSON schema and quality constraints; all tests use mocked HTTP                 |
| 6   | `AIProductTracker.get_products` does not enrich products; enrichment must be a use-case step  | 55     | Accept `tagging_service` kwarg; `_enrich_product` helper; tagging failure-safe; tagging skipped on fetch failure; backward-compatible default (NoOp) |
| 7   | Bootstrap does not read env vars for LLM; no injection path from outer ring to use case       | 56     | `build_tagging_service(env)` in `bootstrap.py`; reads `OPENAI_API_KEY` / `OPENAI_BASE_URL`; `__main__.py` injects result into `AIProductTracker`     |
| 8   | No newsletter presenter; sorting and aggregation duplicated or absent across call sites       | 57     | `NewsletterFormatter` in `formatters.py`; votes DESC / name ASC sort; tag frequency counter; full 7-field product dict; zero storage/LLM imports     |
| 9   | No integration test exercises the tracker → tagging → formatter chain together                | 58     | `tests/integration/test_tagging_formatter_pipeline.py`; 7 tests; no real HTTP/SQLite; shared fixtures in conftest                                    |
| 10  | No E2E tests cover tagging or newsletter; degradation paths (LLM down, bad JSON) untested     | 59     | `tests/e2e/` extended: 4 positive + 7 negative scenarios; mock HTTP for both PH and LLM; real in-memory SQLite; all failure modes confirmed graceful |

---

## Uncle Bob Letter 13 Resolution Plan (Sprints 60–63)

| #   | Uncle Bob Concern                                                                                            | Sprint | Planned Change                                                                                                                                                                   |
| --- | ------------------------------------------------------------------------------------------------------------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `tagging.py` and `formatters.py` absent from `build_bundle.py`; Uncle Bob cannot review them                 | 60     | Add both files to `SECTION_3_PRODUCTION`; add `test_tagging.py`, `test_formatters.py`, `test_tagging_formatter_pipeline.py` to `SECTION_4_TESTS`; bundle shows 15 prod / 24 test |
| 2   | `_enrich_product` swallows `Exception`; hides Use Case bugs; violates trust-the-contract principle           | 61     | Remove try/except from `_enrich_product`; rely on `TaggingService` to guarantee failure-safety; new tests assert exceptions propagate; old swallowing tests deleted              |
| 3   | `NewsletterFormatter` built but not wired into CLI (`__main__.py`); `to_pretty_json` still emitted on stdout | 62     | Replace both `to_pretty_json` stdout writes in `__main__.py` with `json.dumps(NewsletterFormatter().format(...)))`; 6 new tests (unit + integration + e2e positive + negative)   |
| 4   | `NewsletterFormatter` not wired into scheduler (`scheduler.py`); `to_pretty_json` still emitted on stdout    | 63     | Replace `to_pretty_json` stdout write in `scheduler.main` with newsletter JSON; 8 new tests covering stdout shape, stderr preservation, error exit codes                         |

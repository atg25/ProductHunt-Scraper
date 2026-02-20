# Sprint 8 — Literate Programming & Narrative Documentation

## Knuth Concern Addressed

> "The code itself lacks the narrative structure of Literate Programming. …
> I encourage you to weave in documentation that explains the 'why'."
> — Issue #2: Every public class, method, and non-obvious heuristic must carry a
> docstring that tells the _story_ of the data — invariants, fallback reasons,
> and DOM constraints.

---

## Sprint Goal

Transform each module from a sequence of mechanical instructions into a
_chapter of a well-reasoned book_. Every public API surface must explain
**why** decisions were made, not merely **what** happens. Tests verify that
the narrative documentation exists, is structurally correct, and does not lie
(docstring examples are runnable via `doctest`).

---

## Acceptance Criteria

1. `AIProductTracker`, `ProductHuntScraper`, `SQLiteStore`, `ProductHuntAPI`,
   `SchedulerConfig`, and every one of their public methods carry a multi-line
   docstring.
2. Docstrings for fallback-related methods explicitly name the invariant being
   preserved and the failure mode being guarded against.
3. All `doctest` examples in the module docstrings pass under `pytest --doctest-modules`.
4. `pydocstyle` (or `ruff D` rule) CI check passes with zero violations against
   the `src/ph_ai_tracker/` tree.
5. All three test layers pass.

---

## TDD Approach — Red → Green → Refactor

### Step 1 — Write failing tests first

#### Unit Tests `tests/unit/test_docstrings.py`

```
POSITIVE
test_AIProductTracker_has_class_docstring
    - assert AIProductTracker.__doc__ is not None
    - assert len(AIProductTracker.__doc__.strip()) > 40

test_AIProductTracker_get_products_has_docstring
    - assert AIProductTracker.get_products.__doc__ is not None

test_AIProductTracker_from_api_has_docstring
    - inspect the private method; assert docstring mentions "api_token"

test_AIProductTracker_from_scraper_has_docstring
    - assert "_from_scraper" method docstring present

test_ProductHuntScraper_class_docstring_mentions_invariants
    - assert "invariant" in ProductHuntScraper.__doc__.lower()
      OR "dom" in ProductHuntScraper.__doc__.lower()

test_ProductHuntScraper_extract_next_data_has_docstring
    - assert ProductHuntScraper._extract_next_data_products.__doc__ is not None

test_ProductHuntScraper_extract_dom_has_docstring
    - assert ProductHuntScraper._extract_dom_products.__doc__ is not None

test_SQLiteStore_class_docstring_mentions_canonical_key
    - assert "canonical" in SQLiteStore.__doc__.lower()

test_SQLiteStore_save_result_has_docstring
    - assert SQLiteStore.save_result.__doc__ is not None

test_ProductHuntAPI_fetch_ai_products_has_docstring
    - assert ProductHuntAPI.fetch_ai_products.__doc__ is not None

test_TrackerResult_docstring_describes_error_field
    - assert "error" in (TrackerResult.__doc__ or "").lower()

test_SchedulerConfig_docstring_describes_fields
    - assert SchedulerConfig.__doc__ is not None

NEGATIVE
test_docstring_examples_are_doctests
    - Use doctest.testmod() on each module; assert no failures
    - If a module has no examples, assert its docstring does not claim to show
      a usage example (i.e., no dangling ">>>" without a result)

test_no_module_is_docstring_free
    - Iterate over all public names exported by ph_ai_tracker.__init__; assert
      getattr(obj, "__doc__") is not None for every class and function
```

#### Integration Tests `tests/integration/test_narrative_docs.py`

```
POSITIVE
test_fallback_docstring_contains_why_keyword
    - Import AIProductTracker; search _from_api and _from_scraper docstrings
      for at least one of: "fallback", "strategy", "invariant", "reason"

test_scraper_docstring_mentions_dom_constraint
    - Import ProductHuntScraper; assert any docstring in its methods references
      "__NEXT_DATA__" or "React" or "DOM"

test_storage_docstring_mentions_upsert_semantics
    - Import SQLiteStore._upsert_product; assert docstring explains the
      ON CONFLICT behaviour

NEGATIVE
test_pydocstyle_passes_on_src_tree  (or ruff D rule)
    - subprocess.run(["ruff", "check", "--select", "D", "src/"]) → returncode == 0

test_doctest_passes_on_all_modules
    - subprocess.run(["pytest", "--doctest-modules", "src/"]) → returncode == 0
```

#### E2E Tests `tests/e2e/test_docs_e2e.py`

```
POSITIVE
test_e2e_tracker_result_to_dict_is_self_documenting
    - TrackerResult.success([...], source="api").to_dict() produces a dict
      where every key matches a documented field in the class docstring

test_e2e_product_from_dict_roundtrip_is_described
    - Product.from_dict(p.to_dict()) == p  (docstring example should cover this)

NEGATIVE
test_e2e_no_public_function_is_undocumented
    - Walk the public API surface of ph_ai_tracker (via pkgutil + inspect);
      assert 0 public callables have __doc__ == None
```

---

## Implementation Tasks (after tests are written and red)

### `tracker.py`

- Add module docstring explaining the strategy pattern and its three modes.
- `AIProductTracker`: explain why `auto` exists (offline/quota resilience) and
  what the invariant is (always returns a `TrackerResult`, never raises).
- `_from_api`: explain that a missing token is a _configuration_ error, not a
  transient network failure — deliberately returned as `TrackerResult.failure`
  so callers can distinguish it from network errors.
- `_from_scraper`: explain that scraping is the lower-fidelity fallback; calls
  `close()` in `finally` to prevent socket exhaustion under high-frequency
  scheduler runs.

### `scraper.py`

- Module docstring: explain Product Hunt is a React SPA; `__NEXT_DATA__` is the
  stable JSON payload; DOM fallback is a best-effort heuristic for when the
  script tag is absent.
- `_extract_next_data_products`: explain the walk heuristic and the de-dupe
  strategy (URL takes precedence over name).
- `_extract_dom_products`: explain path-depth guard (`len(path_parts) != 2`)
  prevents matching category and nav links.
- `_enrich_from_product_page`: explain why OG tags are preferred over inline
  text scraping.

### `storage.py`

- `SQLiteStore`: explain that `canonical_key` is the database arbiter of
  product uniqueness — Python logic never decides whether two products are the
  same; the UNIQUE constraint does.
- `save_result`: explain the three-table write sequence and why it is wrapped in
  a single connection context (`with self._connect()`).
- `_upsert_product`: explain `ON CONFLICT … DO UPDATE` semantics and why
  `updated_at` is refreshed but `created_at` is immutable.

### `api_client.py`

- `fetch_ai_products`: explain `request_first = min(max(limit * 5, 20), 50)` —
  over-fetch to survive local filtering without a second round-trip.
- `_build_query`: explain `topic_slug` vs global posts shape and why both
  shapes are retried.

### `models.py`

- `Product`: add invariant note — `name` is the only required field; all others
  are optional enrichment.
- `TrackerResult`: explain that `error is None` is the canonical success signal
  and that `products` may be non-empty even when `error` is set (partial results).

### `exceptions.py`

- Add module docstring with hierarchy diagram (ASCII is fine).

### `scheduler.py`

- `SchedulerConfig`: document each field.
- `_is_transient_error`: explain why certain status codes (502/503/504) are
  deemed transient while 401/403 are not.

---

## Definition of Done

- [ ] All 16 docstring tests pass.
- [ ] `pytest --doctest-modules src/` exits 0.
- [ ] `ruff check --select D src/` exits 0 (or `pydocstyle` equivalent).
- [ ] Every class in `src/ph_ai_tracker/` has a class-level docstring ≥ 2 sentences.

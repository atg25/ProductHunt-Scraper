# Sprint 60 — Bundle Audit: Register tagging.py and formatters.py

## Problem Statement
`tagging.py` and `formatters.py` were created in Sprints 53/57 but were never added to
`scripts/build_bundle.py`. This means they are absent from:
- Section 2 (Function-Size Inventory) — their functions are not checked against the 20-line limit
- Section 3 (Production Code) — Uncle Bob cannot review them
- Section 4 (Test Suite) — `test_tagging.py`, `test_formatters.py`, and
  `test_tagging_formatter_pipeline.py` are invisible to the reviewer

Additionally, `test_function_sizes.py` exercises the bundle script itself; it must be updated
to assert the new file count expectations.

## Acceptance Criteria
1. `SECTION_3_PRODUCTION` in `build_bundle.py` lists `tagging.py` and `formatters.py` in
   Clean Architecture order (outer layers after inner layers: `tagging.py` after `bootstrap.py`,
   `formatters.py` after `protocols.py`/before `api_client.py`).
2. `SECTION_4_TESTS` in `build_bundle.py` lists:
   - `tests/unit/test_tagging.py`
   - `tests/unit/test_formatters.py`
   - `tests/integration/test_tagging_formatter_pipeline.py`
3. `make bundle` succeeds and the bundle output shows 15 production files and 24 test files.
4. All functions in `tagging.py` and `formatters.py` are within the 20-line limit (already true;
   this sprint just makes the checker enforce it).
5. A new integration test `test_bundle_integrity.py::test_tagging_and_formatter_in_bundle` passes.

## TDD Plan

### RED phase — write failing tests first

**Unit — `tests/unit/test_bundle_script.py`** (already exists; extend it):
- `test_tagging_in_production_list` — assert `tagging.py` path is in `SECTION_3_PRODUCTION`
- `test_formatters_in_production_list` — assert `formatters.py` path is in `SECTION_3_PRODUCTION`
- `test_tagging_tests_in_test_list` — assert `test_tagging.py` path is in `SECTION_4_TESTS`
- `test_formatters_tests_in_test_list` — assert `test_formatters.py` path is in `SECTION_4_TESTS`
- `test_pipeline_tests_in_test_list` — assert `test_tagging_formatter_pipeline.py` path is
  in `SECTION_4_TESTS`

**Integration — `tests/integration/test_bundle_integrity.py`** (already exists; extend it):
- `test_tagging_and_formatter_in_bundle` — run `build_bundle.py` output and assert it contains
  the string `"# tagging.py"` and `"# formatters.py"`

**E2E positive — `tests/e2e/test_bundle_e2e.py`** (already exists; extend it):
- `test_bundle_production_file_count_is_fifteen` — assert production file count reported in
  bundle header is 15
- `test_bundle_test_file_count_is_twenty_four` — assert test file count reported in header is 24

**E2E negative — `tests/e2e/test_bundle_e2e.py`**:
- `test_bundle_no_missing_files` — assert every file listed in `SECTION_3_PRODUCTION` and
  `SECTION_4_TESTS` physically exists on disk (already exists as `test_all_production_files_exist`;
  verify it still passes after addition)

### GREEN phase — fix `build_bundle.py`
Add `tagging.py` and `formatters.py` to `SECTION_3_PRODUCTION`.
Add the three new test files to `SECTION_4_TESTS`.

### REFACTOR phase
- Run `make bundle` and confirm header reads "15 production files, 24 test files".
- Run full test suite; all pass.

## Definition of Done
- [x] `test_tagging_in_production_list` passes
- [x] `test_formatters_in_production_list` passes
- [x] `test_tagging_tests_in_test_list` passes
- [x] `test_formatters_tests_in_test_list` passes
- [x] `test_pipeline_tests_in_test_list` passes
- [x] `test_tagging_and_formatter_in_bundle` passes
- [x] `test_bundle_production_file_count_is_fifteen` passes (bundle shows 15)
- [x] `test_bundle_test_file_count_is_twenty_four` passes (bundle shows 24)
- [x] `make bundle` exits 0; all functions within 20-line guideline
- [x] Full `pytest -q` passes

## Dependencies
None (self-contained script change).

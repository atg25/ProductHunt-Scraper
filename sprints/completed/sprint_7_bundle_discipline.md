# Sprint 7 — Bundle Discipline & Repository Hygiene

## Knuth Concern Addressed

> "A craftsman does not ship his workbench along with the finished cabinet."
> — Issue #1: `.venv` and `.pytest_cache` must be excluded from every code-review
> bundle, `.gitignore`, `.dockerignore`, and any tooling script.

---

## Sprint Goal

Ensure that no third-party library code, cache artefact, or generated file is
ever included in the review bundle, committed to version control, or copied into
a Docker image. The bundle script must be hermetically repeatable: running it
twice always produces a file that contains **only** first-party source.

---

## Acceptance Criteria

1. `codebase_review_bundle.txt` contains zero lines from `.venv/`, `.pytest_cache/`,
   `__pycache__/`, `*.pyc`, `*.egg-info/`, `dist/`, `build/`, or `output.json`.
2. `.gitignore` explicitly lists all generated/virtual-env paths.
3. `.dockerignore` mirrors `.gitignore` for build-context hygiene.
4. `Makefile` has a `bundle` target that enforces the exclusion list.
5. All three test layers pass with the new exclusion logic exercised.

---

## TDD Approach — Red → Green → Refactor

### Step 1 — Write failing tests first

#### Unit Tests `tests/unit/test_bundle_script.py`

```
POSITIVE
test_bundle_excludes_venv_paths
    - Parse the generated bundle file; assert no line matches r"^===== FILE: \./\.venv/"

test_bundle_excludes_pycache_paths
    - Assert no line matches r"^===== FILE: .*__pycache__"

test_bundle_excludes_pyc_files
    - Assert no line matches r"\.pyc ====="

test_bundle_excludes_egg_info
    - Assert no line matches r"\.egg-info"

test_bundle_file_markers_are_only_source_files
    - Collect every "===== FILE:" line; assert all start with known first-party roots
      (./src/, ./tests/, ./sprints/, ./scripts/, ./Makefile, ./pyproject.toml,
       ./README.md, ./docker-compose.yml, ./Dockerfile, ./.github/, ./.env.example,
       ./.gitignore, ./.dockerignore, ./RUNBOOK.md, ./REQUIREMENTS_TRACEABILITY.md,
       ./SUBMISSION_CHECKLIST.md, ./TERMINAL_CHECKLIST.md)

NEGATIVE
test_bundle_file_is_non_empty
    - Assert the bundle file exists and has > 0 bytes

test_bundle_does_not_include_output_json
    - output.json is a generated artefact; assert it is absent from bundle markers
```

#### Integration Tests `tests/integration/test_bundle_integrity.py`

```
POSITIVE
test_make_bundle_target_exits_zero
    - subprocess.run(["make", "bundle"]) → returncode == 0

test_bundle_line_count_is_reasonable
    - Line count > 100 (has real source) and < 50_000 (no venv junk)

NEGATIVE
test_bundle_regeneration_is_idempotent
    - Run make bundle twice; assert identical SHA-256 of the resulting file
      (content-stable, same order every time)
```

#### E2E Tests `tests/e2e/test_bundle_e2e.py`

```
POSITIVE
test_e2e_bundle_contains_tracker_source
    - Search bundle for "class AIProductTracker"; assert found

test_e2e_bundle_contains_scraper_source
    - Search bundle for "class ProductHuntScraper"; assert found

test_e2e_bundle_contains_storage_source
    - Search bundle for "class SQLiteStore"; assert found

NEGATIVE
test_e2e_bundle_has_no_site_packages
    - Search bundle for "site-packages"; assert NOT found

test_e2e_bundle_has_no_installed_package_metadata
    - Search bundle for "METADATA" and "WHEEL" file markers; assert NOT found
```

---

## Implementation Tasks (after tests are written and red)

1. **Update `.gitignore`**
   Add explicit entries for:

   ```
   .venv/
   venv/
   .pytest_cache/
   __pycache__/
   *.pyc
   *.pyo
   *.egg-info/
   dist/
   build/
   output.json
   codebase_review_bundle.txt
   data/*.db
   ```

2. **Update `.dockerignore`**
   Mirror `.gitignore` plus add `.git/` and `sprints/`.

3. **Update `Makefile` — add `bundle` target**

   ```makefile
   BUNDLE_FILE := codebase_review_bundle.txt

   .PHONY: bundle
   bundle:
       @echo "Building review bundle (first-party source only)…"
       @: > $(BUNDLE_FILE)
       @find . -type f \
           ! -path './.git/*' \
           ! -path './.venv/*' \
           ! -path './venv/*' \
           ! -path '*/__pycache__/*' \
           ! -name '*.pyc' \
           ! -name '*.pyo' \
           ! -path './.pytest_cache/*' \
           ! -path './dist/*' \
           ! -path './build/*' \
           ! -path './*.egg-info/*' \
           ! -name 'output.json' \
           ! -name '$(BUNDLE_FILE)' \
           | LC_ALL=C sort \
           | awk '{printf "\n\n===== FILE: %s =====\n\n", $$0; system("cat " $$0)}' \
           >> $(BUNDLE_FILE)
       @echo "Bundle written: $$(wc -l < $(BUNDLE_FILE)) lines"
   ```

4. **Verify tests go green** — `pytest tests/unit/test_bundle_script.py tests/integration/test_bundle_integrity.py tests/e2e/test_bundle_e2e.py -v`

---

## Definition of Done

- [ ] All 12 bundle tests pass.
- [ ] `make bundle` produces a file with only first-party source.
- [ ] `codebase_review_bundle.txt` and all generated paths are in `.gitignore`.
- [ ] Docker build context is clean (`docker build --no-cache .` still succeeds).

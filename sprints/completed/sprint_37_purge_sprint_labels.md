# Sprint 37 — Purge All Sprint-Reference Labels from the Test Suite

**Source:** Uncle Bob Letter 8, Issue #1  
**Depends on:** Sprint 36 (which removed the `# ---` dashed borders, but left the text labels standing)

---

## Problem Statement

Sprint 36 removed the decorative ASCII dashes (`# ---`) that framed each section-header comment
in the test suite.  It did **not** remove the label lines themselves.  Fifteen location markers
remain, split across two forms:

### Form A — Standalone `#` section-header comments

These are pure noise: a `#` comment whose sole content is a class or method name followed by
a sprint number.  They add no information that the test function names don't already provide,
and they tie the codebase to a project-management artifact that no longer exists.

| File | Line | Comment |
|------|------|---------|
| `tests/unit/test_api_client.py` | 163 | `# RateLimitParser — Sprint 12` |
| `tests/unit/test_api_client.py` | 206 | `# StrictAIFilter — Sprint 12` |
| `tests/unit/test_scraper.py` | 65 | `# Sprint 9 — scraper robustness` |
| `tests/unit/test_scraper.py` | 218 | `# NextDataExtractor — Sprint 13` |
| `tests/unit/test_scraper.py` | 241 | `# DOMFallbackExtractor — Sprint 13` |
| `tests/unit/test_scraper.py` | 259 | `# ProductEnricher — Sprint 13` |
| `tests/unit/test_scraper.py` | 296 | `# Sprint 20 — narrow exception catch in ProductHuntScraper._extract_products` |
| `tests/unit/test_storage.py` | 104 | `# Sprint 10 — database schema integrity` |
| `tests/unit/test_storage.py` | 212 | `# _derive_run_status — Sprint 15` |
| `tests/unit/test_storage.py` | 244 | `# _insert_run_record — Sprint 15` |
| `tests/unit/test_storage.py` | 256 | `# _insert_all_snapshots — Sprint 15` |
| `tests/unit/test_cli.py` | 106 | `# build_provider factory — Sprint 29` |
| `tests/e2e/test_e2e_negative.py` | 26 | `# Sprint 9 — scraper robustness E2E` |
| `tests/e2e/test_e2e_negative.py` | 62 | `# Sprint 11 — missing-token warning E2E` |
| `tests/integration/test_tracker_integration.py` | 29 | `# Sprint 11 — explicit fallback warnings (integration)` |

**Action:** Delete every line in the table above in full.  Do not replace them with anything.
The test functions that follow each label are self-documenting through their own names.

### Form B — Module docstrings that lead with a sprint number

Seven test modules open with a module-level docstring whose first sentence begins with
`"Sprint N:"` or ends with `"— Sprint N …"`.  A sprint number in a module docstring violates
the same principle: the file is a snapshot of present behaviour, not a changelog entry.

| File | Current first line | Required first line |
|------|--------------------|---------------------|
| `tests/unit/test_cli.py` | `"""Unit tests for ph_ai_tracker.cli — Sprint 14 DRY CLI."""` | `"""Unit tests for ph_ai_tracker.cli."""` |
| `tests/e2e/test_bundle_e2e.py` | `"""Sprint 7: E2E validation that the bundle contains the correct first-party source."""` | `"""E2E validation that the bundle contains the correct first-party source."""` |
| `tests/integration/test_bundle_integrity.py` | `"""Sprint 7: Integration tests for the ``make bundle`` target."""` | `"""Integration tests for the ``make bundle`` target."""` |
| `tests/integration/test_narrative_docs.py` | `"""Sprint 8: Integration-level docstring and narrative documentation checks."""` | `"""Integration-level docstring and narrative documentation checks."""` |
| `tests/integration/test_storage_integrity.py` | `"""Sprint 10: Integration tests for SQLite schema integrity and referential enforcement."""` | `"""Integration tests for SQLite schema integrity and referential enforcement."""` |
| `tests/unit/test_bundle_script.py` | `"""Sprint 7: Verify properties of the codebase review bundle file."""` | `"""Verify properties of the codebase review bundle file."""` |
| `tests/unit/test_docstrings.py` | `"""Sprint 8: Verify that all public classes and methods carry docstrings."""` | `"""Verify that all public classes and methods carry docstrings."""` |

**Action:** For each file, strip the leading `"Sprint N: "` prefix **or** the trailing
`" — Sprint N …"` suffix from the docstring's first sentence.  Preserve the rest of the
docstring verbatim.

---

## Why This Matters

Uncle Bob's direct quote: *"Comments should describe intent, not the Jira ticket or sprint number
that authored them.  Source control is for history; code is for the present."*

A test file is read by future maintainers who want to understand what behaviour the suite
currently verifies.  Sprint numbers are irreversible clutter:

- They force the reader to look up an external context (the sprint log) to understand why
  the comment exists.
- They imply the code might be temporary or incomplete.
- They silently rot as the sprint numbering scheme is abandoned or re-ordered.

The test function names, fixture names, and module names already provide the correct context.

---

## Scope

- **Files modified:** 9 test files  
  (7 module-docstring edits + 15 inline comment deletions spread across 7 of the same files)
- **Files NOT modified:** `conftest.py`, any source file under `src/`, `SPRINT_PLAN.md`,
  and any file in `sprints/` (those *are* sprint history and belong there)

---

## Acceptance Criteria

1. `grep -rn "Sprint [0-9]" tests/` returns **zero matches** in `.py` source files
   (`.pyc` cache files may still match and are acceptable to ignore).
2. All 15 inline `# … Sprint …` comment lines are deleted without replacement.
3. All 7 module docstrings no longer begin with `"Sprint N:"` or end with `"— Sprint N …"`;
   the rest of the docstring content is intact and grammatically correct.
4. `pytest --tb=short -q` continues to pass with the same count as before this sprint.
5. `make bundle` completes successfully and the bundle size changes by no more than a few
   hundred bytes (comment deletions only).

---

## Definition of Done

- [ ] 15 inline sprint-label comments deleted across 7 test files
- [ ] 7 module docstrings stripped of their sprint-number prefix/suffix
- [ ] `grep -rn "Sprint [0-9]" tests/*.py tests/**/*.py` → 0 results
- [ ] Full test suite green
- [ ] Bundle regenerated
- [ ] This sprint moved to `sprints/completed/`

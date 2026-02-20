# Sprint 36 — Remove Banner Comments from the Test Suite

## Uncle Bob's Verdict

> "In the last review, I asked you to delete the massive ASCII banner comments. You successfully removed them from the production code, but you left them littered throughout the test suite (e.g., `# RateLimitParser — Sprint 12` and `# NextDataExtractor — Sprint 13`). Clean code applies to your tests just as strictly as it applies to your production code. Your tests are a living specification of the system. Fix it: Delete these artificial visual boundaries from the test files. Let the test modules and fixture names organize the code naturally."

## Problem

Sprint 28 and Sprint 31 eliminated banner comment blocks from the production source files. The same `# ---` / label / `# ---` three-line pattern was never cleaned from the test suite. These banners now appear in **14 test files** across the `unit/`, `integration/`, and `e2e/` directories.

The pattern to remove looks like:
```python
# ---------------------------------------------------------------------------
# RateLimitParser — Sprint 12
# ---------------------------------------------------------------------------
```

Banner comments in tests are harmful for the same reason they are harmful in production code:

- They create visual noise that distracts from the test's own names and docstrings.
- They tie test organization to implementation sprint numbers — archaeology, not specification.
- They suggest the module's structure needs visual crutches, which usually means the structure itself could be cleaner.

## Goal

Delete every `# ---` banner block from every test file. Module docstrings (the `"""Sprint N: ..."""` triple-quoted strings at the very top of files) are **not** banners and are **not** changed by this sprint. Only the `# -----------` / `# Label` / `# -----------` three-line patterns are removed.

## Affected Files

Every file listed below contains one or more three-line banner blocks to remove:

**Unit tests:**
- `tests/unit/test_api_client.py` — `RateLimitParser — Sprint 12`, `StrictAIFilter — Sprint 12`
- `tests/unit/test_scraper.py` — Sprint 9 robustness, `NextDataExtractor — Sprint 13`, `DOMFallbackExtractor — Sprint 13`, `ProductEnricher — Sprint 13`, Sprint 20 narrow exception
- `tests/unit/test_storage.py` — Sprint 10 schema integrity, `_derive_run_status — Sprint 15`, `_insert_run_record — Sprint 15`, `_insert_all_snapshots — Sprint 15`
- `tests/unit/test_tracker.py` — three unlabelled `# ---` separator blocks
- `tests/unit/test_cli.py` — two unlabelled blocks, `build_provider factory — Sprint 29`
- `tests/unit/test_bundle_script.py` — two unlabelled separator blocks
- `tests/unit/test_docstrings.py` — four unlabelled separator blocks
- `tests/unit/test_function_sizes.py` — six or more unlabelled separator blocks

**Integration tests:**
- `tests/integration/test_bundle_integrity.py` — two unlabelled separator blocks
- `tests/integration/test_narrative_docs.py` — two unlabelled separator blocks
- `tests/integration/test_storage_integrity.py` — two unlabelled separator blocks
- `tests/integration/test_tracker_integration.py` — `Sprint 11 — explicit fallback warnings`

**End-to-end tests:**
- `tests/e2e/test_bundle_e2e.py` — two unlabelled separator blocks
- `tests/e2e/test_e2e_negative.py` — `Sprint 9 — scraper robustness E2E`, `Sprint 11 — missing-token warning E2E`

## Implementation

For each file in the list above:

1. Find every occurrence of the three-line pattern:
   ```
   # ---------------------------------------------------------------------------
   # <optional label text>
   # ---------------------------------------------------------------------------
   ```
   as well as bare two-line `# ---` pairs (unlabelled separators with no text on the middle line, or where the label and both `# ---` lines form a visual block).

2. Delete all three lines (or both lines for two-line variants) and any trailing blank line that immediately follows them and was visually paired with the banner.

3. Do **not** alter module-level docstrings, inline comments within function bodies, or any comment that conveys genuine information about test intent.

## Acceptance Criteria

- [ ] Zero `# ---` banner separator lines remain in any file under `tests/`.
- [ ] Module docstrings are unchanged.
- [ ] No test functions are removed or renamed.
- [ ] All test assertions remain identical.
- [ ] Full test suite remains green with all tests passing.

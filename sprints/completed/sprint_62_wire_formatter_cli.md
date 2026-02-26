# Sprint 62 — Plug the Presenter: Wire NewsletterFormatter into CLI (__main__.py)

## Problem Statement
`__main__.py` still emits raw `TrackerResult.to_pretty_json()` in every code path:

```python
sys.stdout.write(result.to_pretty_json() + "\n")
```

`NewsletterFormatter` was built and fully tested in Sprints 57-59 but was never connected to the
delivery mechanism. A feature complete in the core but disconnected from the entry point is dead
code. The user never receives the newsletter output.

## Acceptance Criteria
1. Both stdout writes in `__main__.py` are replaced with output produced by
   `NewsletterFormatter().format(result.products, datetime.now(timezone.utc))`.
2. The output written to stdout is valid JSON (use `json.dumps(newsletter_dict)`).
3. On a successful fetch the stdout JSON contains the keys:
   `generated_at`, `total_products`, `top_tags`, `products`.
4. On a storage-failure path (`--no-persist` bypassed, `StorageError` raised) the same
   newsletter keys are present.
5. `result.to_pretty_json()` is no longer called anywhere in `__main__.py`.
6. `make bundle` passes; all functions within 20-line limit.

## TDD Plan

### RED phase

**Unit — `tests/unit/test_function_sizes.py`** — already validates 20-line limit; will
automatically cover any new helper extracted during refactoring.

**Unit — new helper extracted: `_format_output`** (if refactored out):
- `test_format_output_contains_newsletter_keys` — `_format_output(result)` returns a JSON
  string with keys `generated_at`, `total_products`, `top_tags`, `products`.

**Integration — `tests/integration/test_tracker_integration.py`** (extend):
- `test_cli_stdout_is_newsletter_json` — call `main(["--no-persist", ...])` with captured stdout;
  parse JSON; assert newsletter keys present.
- `test_cli_stdout_newsletter_total_products_matches_provider` — assert
  `output["total_products"]` equals the number of products the stub provider returned.

**E2E positive — `tests/e2e/test_e2e_positive.py`** (extend):
- `test_e2e_cli_stdout_is_newsletter_format` — run `main(["--no-persist", ...])` end-to-end
  with scraper HTML fixture; capture stdout; parse JSON; assert all four newsletter keys.
- `test_e2e_cli_newsletter_products_sorted_by_votes` — assert first product has highest
  `votes` value in the parsed output list.

**E2E negative — `tests/e2e/test_e2e_negative.py`** (extend):
- `test_e2e_cli_storage_error_still_outputs_newsletter` — force `StorageError` in `_try_persist`;
  assert stdout is still valid newsletter JSON (not raw tracker JSON) and exit code is 3.
- `test_e2e_cli_no_persist_outputs_newsletter` — run with `--no-persist`; assert stdout is
  newsletter format.

### GREEN phase — wire formatter in `__main__.py`
```python
import json
from datetime import datetime, timezone
from .formatters import NewsletterFormatter

def _write_newsletter(result) -> None:
    newsletter = NewsletterFormatter().format(list(result.products), datetime.now(timezone.utc))
    sys.stdout.write(json.dumps(newsletter) + "\n")
```
Replace both `sys.stdout.write(result.to_pretty_json() + "\n")` calls with
`_write_newsletter(result)`.

### REFACTOR phase
- Remove unused `to_pretty_json` call; keep `to_pretty_json` on the model (it may be used in
  tests or scheduler; do not delete the method itself).
- Run full suite; confirm all pass.
- Run `make bundle`.

## Definition of Done
- [x] `__main__.py` contains no call to `to_pretty_json`
- [x] stdout output is newsletter-format JSON
- [x] `test_cli_stdout_is_newsletter_json` passes
- [x] `test_cli_stdout_newsletter_total_products_matches_provider` passes
- [x] `test_e2e_cli_stdout_is_newsletter_format` passes
- [x] `test_e2e_cli_newsletter_products_sorted_by_votes` passes
- [x] `test_e2e_cli_storage_error_still_outputs_newsletter` passes
- [x] `test_e2e_cli_no_persist_outputs_newsletter` passes
- [x] `make bundle` exits 0
- [x] Full `pytest -q` passes

## Dependencies
Sprint 60 (formatters.py visible in bundle).
Sprint 61 (propagation behaviour tested; no interaction but logical ordering).

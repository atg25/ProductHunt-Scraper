# Sprint 63 — Plug the Presenter: Wire NewsletterFormatter into Scheduler (scheduler.py)

## Problem Statement
`scheduler.py` still emits raw `TrackerResult.to_pretty_json()` to stdout:

```python
sys.stdout.write(run_result.tracker_result.to_pretty_json() + "\n")
```

The scheduler is the long-running daemon entry point used in Docker / cron. It should emit the
same newsletter-format JSON that the CLI now emits (after Sprint 62), so consumers of the
scheduler output (log aggregators, dashboards) receive a consistent structured payload.

## Acceptance Criteria
1. The stdout write in `scheduler.main()` is replaced with output produced by
   `NewsletterFormatter().format(result.products, datetime.now(timezone.utc))`.
2. Output is valid JSON via `json.dumps(newsletter_dict)`.
3. The scheduler's stderr summary line (`_format_run_summary`) is preserved unchanged.
4. `run_result.tracker_result.to_pretty_json()` is no longer called anywhere in `scheduler.py`.
5. `make bundle` passes; all functions within 20-line limit.

## TDD Plan

### RED phase

**Unit — `tests/unit/test_scheduler.py`** (extend):
- `test_scheduler_stdout_is_newsletter_json` — mock `run_once`, capture stdout from `main()`;
  parse JSON; assert keys `generated_at`, `total_products`, `top_tags`, `products`.
- `test_scheduler_stdout_total_products_matches_tracker_result` — assert
  `output["total_products"]` equals `len(run_result.tracker_result.products)`.
- `test_scheduler_stderr_still_contains_summary` — assert captured stderr contains the run
  summary text (i.e. `_format_run_summary` output is untouched).

**Integration — `tests/integration/test_tracker_integration.py`** (extend):
- `test_scheduler_run_once_stdout_is_newsletter` — run `scheduler.main(["--strategy",
  "scraper", ...])` with patched `run_once`; assert stdout is newsletter JSON.

**E2E positive — `tests/e2e/test_e2e_positive.py`** (extend):
- `test_e2e_scheduler_stdout_is_newsletter_format` — run `scheduler.main` end-to-end with
  scraper HTML fixture; capture stdout; parse JSON; assert all four newsletter keys present.
- `test_e2e_scheduler_newsletter_products_sorted_by_votes` — assert first product in parsed
  output has highest votes value.

**E2E negative — `tests/e2e/test_e2e_negative.py`** (extend):
- `test_e2e_scheduler_storage_error_returns_exit_3` — force `StorageError` inside `run_once`;
  assert exit code is 3 and stderr contains the error message.
- `test_e2e_scheduler_invalid_strategy_returns_exit_2` — pass an unknown strategy string;
  assert exit code is 2 and no newsletter is written to stdout.

### GREEN phase — wire formatter in `scheduler.py`
```python
import json
from datetime import datetime, timezone
from .formatters import NewsletterFormatter

# Inside main(), replace:
#   sys.stdout.write(run_result.tracker_result.to_pretty_json() + "\n")
# with:
newsletter = NewsletterFormatter().format(
    list(run_result.tracker_result.products),
    datetime.now(timezone.utc),
)
sys.stdout.write(json.dumps(newsletter) + "\n")
```

Extract a `_write_newsletter(result)` helper if the 20-line limit requires it.

### REFACTOR phase
- Confirm `to_pretty_json` is no longer called in `scheduler.py`.
- Run full suite; confirm all pass.
- Run `make bundle`.

## Definition of Done
- [x] `scheduler.py` contains no call to `to_pretty_json`
- [x] stdout output from scheduler is newsletter-format JSON
- [x] `test_scheduler_stdout_is_newsletter_json` passes
- [x] `test_scheduler_stdout_total_products_matches_tracker_result` passes
- [x] `test_scheduler_stderr_still_contains_summary` passes
- [x] `test_scheduler_run_once_stdout_is_newsletter` passes
- [x] `test_e2e_scheduler_stdout_is_newsletter_format` passes
- [x] `test_e2e_scheduler_newsletter_products_sorted_by_votes` passes
- [x] `test_e2e_scheduler_storage_error_returns_exit_3` passes
- [x] `test_e2e_scheduler_invalid_strategy_returns_exit_2` passes
- [x] `make bundle` exits 0
- [x] Full `pytest -q` passes

## Dependencies
Sprint 62 (CLI formatter wired; consistent output format established).
Sprint 60 (formatters.py visible in bundle).

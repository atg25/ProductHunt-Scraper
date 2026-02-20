# Sprint 29 — ProviderFactory: DRY up the Framework Layer

## Uncle Bob's Verdict

> "In `__main__.py`, you have a dedicated `_build_providers` method that checks the token and
> instantiates `ProductHuntAPI` and `ProductHuntScraper`. In `scheduler.py`, inside the
> `run_once` function, you are manually repeating the exact same logic. Fix it: You need a
> Factory. Create an `AppContainer` or a `ProviderFactory` in your CLI module that takes the
> `CommonArgs` and returns the fully configured `ProductProvider`."

## Problem

After Sprint 27, both composition roots still contain _duplicated, parallel_ provider-building
logic:

**`__main__.py` — `_build_provider(common)`**

```python
has_token = bool(common.api_token and common.api_token.strip())
api = ProductHuntAPI(common.api_token) if has_token else None
...
```

**`scheduler.py` — `run_once(config)`**

```python
api_provider = None
if config.api_token and config.api_token.strip():
    api_provider = ProductHuntAPI(config.api_token)
...
```

Two callers, two copies of the same four-step decision:

1. Does the token exist and is it non-blank?
2. Build `ProductHuntAPI` (or None).
3. Build `ProductHuntScraper`.
4. Pick `ProductHuntAPI` / `ProductHuntScraper` / `FallbackProvider` based on strategy.

This is a DRY violation. Adding a new strategy or changing provider construction would
require updating both files.

## Goal

Extract a single `build_provider(*, strategy: str, api_token: str | None) -> ProductProvider`
factory function into `cli.py` (the framework-layer shared module already imported by both
callers). Both `__main__.py` and `scheduler.py` call `build_provider` and nothing else.

## Changes

### `src/ph_ai_tracker/cli.py`

**Add imports** at the top: `ProductHuntAPI`, `ProductHuntScraper`, `ProductProvider`,
`FallbackProvider`, `_NoTokenProvider`, `_warn_missing_token` from the appropriate modules.

**Add** private helper:

```python
def _warn_missing_token() -> None:
    """Emit the standard missing-token log warning and RuntimeWarning."""
    _log.warning(_MISSING_TOKEN_MSG)
    warnings.warn(_MISSING_TOKEN_MSG, RuntimeWarning, stacklevel=3)
```

**Add** public factory:

```python
def build_provider(*, strategy: str, api_token: str | None) -> ProductProvider:
    """Build the correct ProductProvider for *strategy* and *api_token*.

    Raises ValueError for unrecognised strategy names so callers can surface
    a clean error without catching generic exceptions.
    """
    has_token = bool(api_token and api_token.strip())
    api  = ProductHuntAPI(api_token) if has_token else None
    scraper = ProductHuntScraper()
    if strategy == "scraper":
        return scraper
    if strategy == "api":
        if api is None:
            _warn_missing_token()
            return _NoTokenProvider()
        return api
    if strategy == "auto":
        return FallbackProvider(api_provider=api, scraper_provider=scraper)
    raise ValueError(f"Unknown strategy: {strategy!r}")
```

`_MISSING_TOKEN_MSG` constant is imported from `protocols` (where it lives after Sprint 27).

### `src/ph_ai_tracker/__main__.py`

Remove `_build_provider`. `_fetch_result` calls `build_provider` from `.cli`:

```python
from .cli import add_common_arguments, CommonArgs, build_provider

def _fetch_result(common: CommonArgs) -> TrackerResult:
    provider = build_provider(strategy=common.strategy, api_token=common.api_token)
    return AIProductTracker(provider=provider).get_products(
        search_term=common.search_term, limit=common.limit
    )
```

Remove imports of `ProductHuntAPI`, `ProductHuntScraper`, `FallbackProvider`, `_NoTokenProvider`
since they are now only needed inside `cli.py`.

### `src/ph_ai_tracker/scheduler.py`

Remove inline provider building from `run_once()`. Call `build_provider`:

```python
from .cli import add_common_arguments, CommonArgs, build_provider

def run_once(config: SchedulerConfig) -> SchedulerRunResult:
    """Execute one full fetch-and-persist cycle and return the run outcome."""
    provider = build_provider(strategy=config.strategy, api_token=config.api_token)
    tracker  = AIProductTracker(provider=provider)
    result, attempts_used = _fetch_with_retries(tracker, config)
    ...
```

Remove imports of `ProductHuntAPI`, `ProductHuntScraper`, `FallbackProvider`, `_NoTokenProvider`
from `scheduler.py` since they are no longer referenced there.

### Tests

**`tests/unit/test_cli.py`** — Add `build_provider` tests:

| Test                                                         | Assertion                                                                |
| ------------------------------------------------------------ | ------------------------------------------------------------------------ |
| `test_build_provider_scraper`                                | Returns `ProductHuntScraper` instance for strategy `"scraper"`.          |
| `test_build_provider_api_with_token`                         | Returns `ProductHuntAPI` instance when token present.                    |
| `test_build_provider_api_no_token_returns_no_token_provider` | Returns `_NoTokenProvider` when token absent; emits RuntimeWarning.      |
| `test_build_provider_auto_with_token`                        | Returns `FallbackProvider` with non-None api_provider.                   |
| `test_build_provider_auto_no_token`                          | Returns `FallbackProvider` with api_provider=None; emits RuntimeWarning. |
| `test_build_provider_unknown_raises`                         | Raises `ValueError` for unrecognised strategy.                           |

**`tests/unit/test_tracker.py`** — Remove any remaining warning tests that belong in
`test_cli.py`. The tracker unit tests are now purely about provider delegation.

## Acceptance Criteria

- [ ] `build_provider` exists in `cli.py` and is the single place that instantiates
      `ProductHuntAPI`, `ProductHuntScraper`, `FallbackProvider`, or `_NoTokenProvider`.
- [ ] `__main__.py` does not import `ProductHuntAPI`, `ProductHuntScraper`,
      `FallbackProvider`, or `_NoTokenProvider`.
- [ ] `scheduler.py` does not import `ProductHuntAPI`, `ProductHuntScraper`,
      `FallbackProvider`, or `_NoTokenProvider`.
- [ ] All 216+ tests green.
- [ ] `make bundle` exits 0; all functions ≤ 20 lines.
- [ ] `grep -c "_build_provider\|api_provider =\|ProductHuntScraper()" src/ph_ai_tracker/__main__.py`
      returns `0` (no inline provider construction).

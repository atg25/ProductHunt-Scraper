# Sprint 27 — OCP: Eliminate the Strategy Switch Statement

## Uncle Bob's Verdict

> "Look closely at `AIProductTracker.get_products` in the Use-Case layer. You have a routing
> mechanism built entirely on a string flag. This violates the Open/Closed Principle. A class
> should be open for extension but closed for modification. The `AIProductTracker` should not
> know what a 'scraper' or an 'api' or an 'auto' fallback is. It should simply receive a single
> `ProductProvider` instance through its constructor and call `fetch_products()` on it."

## Problem

`tracker.py` contains a four-branch `if/elif` chain in `get_products()` routing on the `strategy`
string. Adding a new strategy (e.g. `"rss_feed"`) requires opening `tracker.py` and adding
a new branch — a direct OCP violation. The class also holds _two_ provider slots
(`api_provider`, `scraper_provider`) and three private routing methods (`_from_api`,
`_from_scraper`, `_auto_strategy`), all of which encode framework-layer decisions that have no
place in the use-case layer.

## Goal

- `AIProductTracker` knows nothing about strategy names, tokens, or fallback sequences.
- It accepts exactly **one** `provider: ProductProvider` and delegates to it.
- The "auto fallback" compositional logic lives in a `FallbackProvider` combinator
  (use-case layer — it depends only on the `ProductProvider` abstraction, not on any
  concrete HTTP adapter).
- The "api + no token → immediate failure" case is handled by a `_NoTokenProvider`
  sentinel (private, use-case layer).
- Composition roots (`__main__.py`, `scheduler.py`) remain the only places that instantiate
  concrete adapters and select between them.

## Changes

### `src/ph_ai_tracker/protocols.py`

**Add** `source_name: str` to the `ProductProvider` protocol so every provider can
self-report its observability label.

**Add** the constant `_MISSING_TOKEN_MSG` (moved from `tracker.py`).

**Add** `FallbackProvider` — a pure combinator that tries the API first and falls back
to the scraper. If `api_provider` is `None`, it emits the standard missing-token warning
at init time, before any network call.

**Add** `_NoTokenProvider` — a private sentinel that raises `APIError("Missing api_token")`
from `fetch_products()`. Used by composition roots when `strategy="api"` but no token
is present; the tracker's normal exception handler maps it to a `TrackerResult.failure`.

### `src/ph_ai_tracker/api_client.py`

Add `source_name = "api"` class attribute to `ProductHuntAPI`.

### `src/ph_ai_tracker/scraper.py`

Add `source_name = "scraper"` class attribute to `ProductHuntScraper`.

### `src/ph_ai_tracker/tracker.py`

Strip `AIProductTracker` to its minimal form:

```
__init__(self, *, provider: ProductProvider) -> None
get_products(self, *, search_term="AI", limit=20) -> TrackerResult
```

Remove: `TrackerConfig`, `_config`, `_api_provider`, `_scraper_provider`,
`_from_api`, `_from_scraper`, `_auto_strategy`, `_MISSING_TOKEN_MSG`.

`get_products()` body:

```python
try:
    products = self._provider.fetch_products(search_term=search_term, limit=limit)
    return TrackerResult.success(products, source=self._provider.source_name)
except RateLimitError as exc:
    return TrackerResult.failure(source=self._provider.source_name, error=f"Rate limited: {exc}")
except (APIError, ScraperError) as exc:
    return TrackerResult.failure(source=self._provider.source_name, error=str(exc))
finally:
    self._provider.close()
```

### `src/ph_ai_tracker/__main__.py`

Replace `_build_providers` (returns a tuple) with `_build_provider` (returns a single
`ProductProvider`). Import `FallbackProvider`, `_NoTokenProvider` from `.protocols`.

Strategy → provider mapping:

- `"api"` + token → `ProductHuntAPI(token)`
- `"api"` + no token → warn + `_NoTokenProvider()`
- `"scraper"` → `ProductHuntScraper()`
- `"auto"` → `FallbackProvider(api_provider=api_or_none, scraper_provider=ProductHuntScraper())`

`_fetch_result` updated to call `_build_provider(common)` directly.

### `src/ph_ai_tracker/scheduler.py`

`run_once()` mirrors the same provider-building logic as `__main__._build_provider`.
`AIProductTracker` receives the single provider.

### Tests

| File                                            | Change                                                                                                                                                |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/unit/test_tracker.py`                    | Rewrite: pass `_FakeProvider` directly to `AIProductTracker(provider=...)`. Remove all `strategy=` kwargs. Move warning tests to `test_protocols.py`. |
| `tests/unit/test_protocols.py`                  | Add: `FallbackProvider` success via API; fallback to scraper; both-fail; missing-token warning at init; `_NoTokenProvider` raises APIError.           |
| `tests/integration/test_tracker_integration.py` | Wrap with `FallbackProvider`. Update `r.source == "scraper"` assertions to `r.source == "auto"`.                                                      |
| `tests/e2e/test_e2e_positive.py`                | Pass `FallbackProvider` as provider.                                                                                                                  |
| `tests/e2e/test_e2e_negative.py`                | Pass `FallbackProvider` or direct scraper provider.                                                                                                   |

## Acceptance Criteria

- [ ] `tracker.py` imports only `exceptions`, `models`, `protocols` — no `api_client`, no `scraper`.
- [ ] `tracker.py` has no `if strategy` branch.
- [ ] `AIProductTracker.__init__` signature is `(self, *, provider: ProductProvider)`.
- [ ] `FallbackProvider` lives in `protocols.py` and has `source_name = "auto"`.
- [ ] `_NoTokenProvider` raises `APIError("Missing api_token")` from `fetch_products()`.
- [ ] All 216+ tests green with no regressions.
- [ ] `make bundle` exits 0; all functions ≤ 20 lines.

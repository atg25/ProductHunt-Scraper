# Sprint 26 — Dependency Inversion: `ProductProvider` Protocol

## Context

Uncle Bob Letter #5 identifies a Dependency Inversion Principle (DIP) violation
in `tracker.py`. The **Use-Case layer** directly reaches into the **Interface
Adapters layer**:

```python
# tracker.py — Use-Case layer (BAD)
from .api_client import APIConfig, ProductHuntAPI       # ← Interface Adapter
from .scraper import ProductHuntScraper, ScraperConfig  # ← Interface Adapter
```

`AIProductTracker` then **instantiates** those concrete adapters on lines 98 and
117, making the use-case layer's compile-time dependency point in the wrong
direction.

Clean Architecture rule:

> _"Source code dependencies must point inward — toward higher-level policy.
> The use-case layer must never depend on concrete infrastructure."_

The fix: define a `ProductProvider` **Protocol** in the use-case layer, make
`AIProductTracker` depend only on that abstraction, and move concrete
instantiation to the **Composition Root** (the framework/entry-point layer:
`scheduler.py` and `__main__.py`).

---

## Architecture Before and After

### Before (broken arrows)

```
tracker.py  →  api_client.py     (Use-Case imports Adapter)
tracker.py  →  scraper.py        (Use-Case imports Adapter)
```

### After (correct arrows)

```
api_client.py  (satisfies)  →  ProductProvider Protocol  ←  tracker.py
scraper.py     (satisfies)  →  ProductProvider Protocol  ←  tracker.py

scheduler.py   (creates)    →  ProductHuntAPI            (Composition Root)
scheduler.py   (creates)    →  ProductHuntScraper        (Composition Root)
scheduler.py   (injects)    →  AIProductTracker          (Composition Root)
```

`tracker.py` imports nothing from `api_client.py` or `scraper.py` after this
sprint.

---

## Design Decisions

### D1 — Unified `fetch_products` interface

Both `ProductHuntAPI` and `ProductHuntScraper` expose differently-named
methods today (`fetch_ai_products` vs `scrape_ai_products`). Adding a
**thin `fetch_products` forwarding method** to each adapter lets the Protocol
use a single, stable name without renaming existing public methods (which would
break existing callers and tests).

### D2 — `ProductProvider` lives in `protocols.py`

A new top-level module `src/ph_ai_tracker/protocols.py` holds the Protocol.
This keeps `models.py` as pure data and gives the Protocol a home that can be
discovered without reading tracker.py.

### D3 — `@runtime_checkable` for dev-time safety

`@runtime_checkable` allows `isinstance(obj, ProductProvider)` checks in tests
and defensive assertions, without requiring adapters to inherit from anything.

### D4 — Missing provider warning stays in `tracker.py`

The business rule _"if no API provider is configured for an API strategy, warn
the operator"_ is use-case logic, not infrastructure logic. `tracker.py` keeps
the `RuntimeWarning` / `logging.WARNING` emission — it now fires when
`self._api_provider is None`, the same semantic as before.

### D5 — `strategy` parameter preserved on `AIProductTracker`

The routing choice (api / scraper / auto) is use-case policy. It stays in
`AIProductTracker.__init__`. The composition root picks a strategy based on
CLI arguments OR environment variables; the tracker honours that choice.

### D6 — Composition Roots are `scheduler.py` and `__main__.py`

These are the framework-layer entry points. They already hold `config.api_token`
and `SchedulerConfig` / `CommonArgs`. They are the correct place to decide
_which concrete adapter_ to build and inject.

---

## New File: `src/ph_ai_tracker/protocols.py`

```python
"""Protocols for the ph_ai_tracker use-case layer.

Defining these abstractions here keeps tracker.py free of any concrete
adapter imports.  Adapters (api_client.py, scraper.py) satisfy the protocols
structurally — no explicit subclassing required.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .models import Product


@runtime_checkable
class ProductProvider(Protocol):
    """A source that can return a list of AI products.

    Implemented structurally by ``ProductHuntAPI`` and ``ProductHuntScraper``.
    Any object that provides matching ``fetch_products`` and ``close``
    signatures satisfies this protocol without explicit registration.
    """

    def fetch_products(
        self, *, search_term: str, limit: int
    ) -> list[Product]:
        """Return up to *limit* products matching *search_term*.

        Must raise ``APIError`` / ``ScraperError`` (or subclasses) on failure.
        Must never return ``None``.
        """
        ...

    def close(self) -> None:
        """Release any held network connections or file handles."""
        ...
```

---

## Changes to `src/ph_ai_tracker/api_client.py`

Add one forwarding method to `ProductHuntAPI`:

```python
def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
    """Satisfy ``ProductProvider`` protocol; delegates to ``fetch_ai_products``."""
    return self.fetch_ai_products(search_term=search_term, limit=limit)
```

No existing method is renamed. All existing tests continue to work unchanged.

---

## Changes to `src/ph_ai_tracker/scraper.py`

Add one forwarding method to `ProductHuntScraper`:

```python
def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
    """Satisfy ``ProductProvider`` protocol; delegates to ``scrape_ai_products``."""
    return self.scrape_ai_products(search_term=search_term, limit=limit)
```

---

## Changes to `src/ph_ai_tracker/tracker.py`

### Remove all adapter imports

```python
# REMOVE these two lines:
from .api_client import APIConfig, ProductHuntAPI
from .scraper import ProductHuntScraper, ScraperConfig
```

### Add protocol import

```python
from .protocols import ProductProvider
```

### New `__init__` signature

```python
def __init__(
    self,
    *,
    strategy: str = "auto",
    api_provider: ProductProvider | None = None,
    scraper_provider: ProductProvider | None = None,
) -> None:
    self._config = TrackerConfig(strategy=strategy)
    self._api_provider = api_provider
    self._scraper_provider = scraper_provider
```

`api_token`, `api_config`, and `scraper_config` parameters are **removed**.
The caller is responsible for building configured provider objects.

### `_from_api` — use injected provider

```python
def _from_api(self, *, search_term: str, limit: int) -> TrackerResult:
    """Fetch via the API provider; warn and fail immediately if none configured."""
    if self._api_provider is None:
        _log.warning(_MISSING_TOKEN_MSG)
        warnings.warn(_MISSING_TOKEN_MSG, RuntimeWarning, stacklevel=4)
        return TrackerResult.failure(source="api", error="Missing api_token")
    try:
        products = self._api_provider.fetch_products(
            search_term=search_term, limit=limit
        )
        return TrackerResult.success(products, source="api")
    except RateLimitError as exc:
        return TrackerResult.failure(source="api", error=f"Rate limited: {exc}")
    except APIError as exc:
        return TrackerResult.failure(source="api", error=str(exc))
    finally:
        self._api_provider.close()
```

### `_from_scraper` — use injected provider

```python
def _from_scraper(self, *, search_term: str, limit: int) -> TrackerResult:
    """Fetch via the scraper provider; fail if none configured."""
    if self._scraper_provider is None:
        return TrackerResult.failure(
            source="scraper", error="No scraper provider configured"
        )
    try:
        products = self._scraper_provider.fetch_products(
            search_term=search_term, limit=limit
        )
        return TrackerResult.success(products, source="scraper")
    except ScraperError as exc:
        return TrackerResult.failure(source="scraper", error=str(exc))
    finally:
        self._scraper_provider.close()
```

### Forbidden imports check (enforced by test)

`tracker.py` must import **zero** symbols from `api_client` or `scraper`.

---

## Changes to `src/ph_ai_tracker/__main__.py`

The `main()` function becomes the Composition Root for the CLI entry-point:

```python
from .api_client import ProductHuntAPI
from .scraper import ProductHuntScraper

def main(argv: list[str] | None = None) -> int:
    ...
    common = CommonArgs.from_namespace(args)

    api_provider = (
        ProductHuntAPI(common.api_token)
        if common.api_token and common.api_token.strip()
        else None
    )
    scraper_provider = ProductHuntScraper()

    result = AIProductTracker(
        strategy=common.strategy,
        api_provider=api_provider,
        scraper_provider=scraper_provider,
    ).get_products(search_term=common.search_term, limit=common.limit)
    ...
```

---

## Changes to `src/ph_ai_tracker/scheduler.py`

The `run_once(config)` function becomes the Composition Root for the scheduled
entry-point:

```python
from .api_client import APIConfig, ProductHuntAPI
from .scraper import ProductHuntScraper, ScraperConfig

def run_once(config: SchedulerConfig, ...) -> SchedulerRunResult:
    ...
    api_provider = (
        ProductHuntAPI(config.api_token, config=APIConfig())
        if config.api_token and config.api_token.strip()
        else None
    )
    scraper_provider = ProductHuntScraper(config=ScraperConfig())

    tracker = AIProductTracker(
        strategy=config.strategy,
        api_provider=api_provider,
        scraper_provider=scraper_provider,
    )
    ...
```

---

## Test Plan (TDD — Red → Green → Refactor)

### New file: `tests/unit/test_protocols.py`

Write these tests **before** creating `protocols.py`:

```python
"""Sprint 26: Protocol conformance tests."""
from ph_ai_tracker.protocols import ProductProvider
from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.scraper import ProductHuntScraper


def test_product_hunt_api_satisfies_protocol() -> None:
    """ProductHuntAPI must satisfy ProductProvider structurally."""
    assert isinstance(ProductHuntAPI("fake-token"), ProductProvider)


def test_product_hunt_scraper_satisfies_protocol() -> None:
    """ProductHuntScraper must satisfy ProductProvider structurally."""
    assert isinstance(ProductHuntScraper(), ProductProvider)


def test_arbitrary_object_does_not_satisfy_protocol() -> None:
    """A plain object without requisite methods must NOT satisfy ProductProvider."""
    assert not isinstance(object(), ProductProvider)


def test_protocol_is_runtime_checkable() -> None:
    """ProductProvider must support isinstance checks at runtime."""
    import typing
    assert typing.runtime_checkable in type(ProductProvider).__mro__ or \
           getattr(ProductProvider, "_is_runtime_protocol", False)
```

Run → all four **must FAIL** (red).

### Migrate `tests/unit/test_tracker.py`

The following changes restore green after the tracker refactor.

#### Helper in conftest or top of test file

```python
from __future__ import annotations
from ph_ai_tracker.models import Product
from ph_ai_tracker.exceptions import ScraperError, APIError


class _FakeProvider:
    """Minimal ProductProvider — used in place of monkeypatching real adapters."""

    def __init__(
        self,
        products: list[Product] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._products = products or []
        self._raises = raises
        self.closed = False

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        if self._raises is not None:
            raise self._raises
        return self._products

    def close(self) -> None:
        self.closed = True
```

#### Rewrite per-test migrations

| Old test                                                                  | Migration                                                                                                   |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `AIProductTracker(strategy="nope")`                                       | unchanged — still valid signature                                                                           |
| `AIProductTracker(strategy="api")`                                        | unchanged — `api_provider` defaults to `None`, still returns "Missing api_token"                            |
| `AIProductTracker(strategy="scraper")` + monkeypatch `ProductHuntScraper` | Replace with `AIProductTracker(strategy="scraper", scraper_provider=_FakeProvider([...]))`                  |
| Auto-fallback + monkeypatch scraper to raise                              | `scraper_provider=_FakeProvider(raises=ScraperError("offline"))` — no monkeypatching needed                 |
| Warning tests (`RuntimeWarning`, `caplog`)                                | Keep identical — warnings fire when `api_provider is None` for api/auto strategy, same observable behaviour |
| `test_auto_strategy_with_valid_token_no_warning`                          | Replace `ProductHuntAPI` mock with `_FakeProvider([Product(...)])` as `api_provider=`                       |

### Migrate `tests/integration/test_tracker_integration.py`

The integration tests currently monkeypatch `ProductHuntAPI.__init__` and
`ProductHuntScraper.__init__` to inject mock transports. Under DIP, the
composition root constructs providers, so integration tests do the same:

```python
def test_auto_fallback_on_api_error(api_success_payload, scraper_html, monkeypatch):
    ...
    # Build providers with injected transports — no monkeypatching constructors
    api_provider = ProductHuntAPI("token", config=APIConfig(),
                                  transport=api_transport)
    scraper_provider = ProductHuntScraper(config=ScraperConfig(),
                                          transport=scraper_transport)

    t = AIProductTracker(
        strategy="auto",
        api_provider=api_provider,
        scraper_provider=scraper_provider,
    )
    ...
```

This is _strictly cleaner_ than the old approach: no `monkeypatch.setattr` on
constructors, so tests are faster and more deterministic.

### Forbidden-imports regression test

Add to `tests/unit/test_tracker.py`:

```python
def test_tracker_does_not_import_adapters() -> None:
    """tracker.py must not reference api_client or scraper at import time."""
    import ast
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / "src" / "ph_ai_tracker" / "tracker.py"
    ).read_text()
    tree = ast.parse(source)

    forbidden = {"api_client", "scraper"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            assert not any(f in module for f in forbidden), (
                f"tracker.py imports from forbidden module: {module}"
            )
```

---

## Files Changed Summary

| File                                            | Type   | Change                                                              |
| ----------------------------------------------- | ------ | ------------------------------------------------------------------- |
| `src/ph_ai_tracker/protocols.py`                | NEW    | `ProductProvider` Protocol                                          |
| `src/ph_ai_tracker/tracker.py`                  | MODIFY | Remove adapter imports; accept injected providers                   |
| `src/ph_ai_tracker/api_client.py`               | MODIFY | Add `fetch_products` forwarding method                              |
| `src/ph_ai_tracker/scraper.py`                  | MODIFY | Add `fetch_products` forwarding method                              |
| `src/ph_ai_tracker/__main__.py`                 | MODIFY | Composition Root: build + inject providers                          |
| `src/ph_ai_tracker/scheduler.py`                | MODIFY | Composition Root: build + inject providers                          |
| `tests/unit/test_protocols.py`                  | NEW    | Protocol conformance + isinstance checks                            |
| `tests/unit/test_tracker.py`                    | MODIFY | Replace monkeypatched scraper with `_FakeProvider`                  |
| `tests/integration/test_tracker_integration.py` | MODIFY | Inject providers via constructor; remove constructor monkeypatching |

---

## Invariants That Must Not Break

1. `get_products()` never raises — invariant preserved (providers error out to
   `TrackerResult.failure`).
2. `strategy="auto"` with `api_provider=None` still emits `RuntimeWarning` and
   `logging.WARNING` containing `"api_token"`.
3. `strategy="api"` with `api_provider=None` returns
   `TrackerResult(error="Missing api_token")`.
4. All 213+ tests from Sprint 25 remain green after migration.
5. `tracker.py` zero adapter imports — enforced by AST regression test.
6. Bundle regenerates successfully with 10 production files (Sprint 25 fix
   already applied).

---

## Definition of Done

- [ ] `src/ph_ai_tracker/protocols.py` exists and exports `ProductProvider`
- [ ] `ProductHuntAPI` and `ProductHuntScraper` each have `fetch_products`
- [ ] `tracker.py` imports nothing from `api_client` or `scraper`
- [ ] `tracker.py` zero instances of `ProductHuntAPI(` or `ProductHuntScraper(`
- [ ] `test_tracker_does_not_import_adapters` passes
- [ ] `test_product_hunt_api_satisfies_protocol` passes
- [ ] `test_product_hunt_scraper_satisfies_protocol` passes
- [ ] Full `pytest` run: 220+ tests, 0 failures
- [ ] `make bundle` exits zero; bundle contains `protocols.py` in production section
- [ ] 0 flagged functions (all functions remain ≤ 20 lines)

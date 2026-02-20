# Sprint 45 — Split `cli.py`: Extract `build_provider` to `bootstrap.py`

**Status:** Active  
**Source:** Uncle Bob Letter 10, Issue #3 — Mid-File Import Smell / Masked Circular Dependencies  
**Depends on:** Sprint 29 (created `build_provider` in `cli.py`); Sprint 14 (created `CommonArgs` / `add_common_arguments`)

---

## Problem Statement

`cli.py` currently has two responsibilities:

1. **Argument parsing** — `CommonArgs`, `add_common_arguments`, and the five private
   `_add_*` helpers.
2. **Provider construction** — `build_provider` factory that instantiates concrete
   adapters (`ProductHuntAPI`, `ProductHuntScraper`, `FallbackProvider`, `_NoTokenProvider`).

Because `build_provider` must import the concrete adapter classes, and those classes
import from modules that already import from `cli.py` (the classic circular dependency
loop), the import had to be deferred to the **middle of the file**:

```python
# ... 100 lines of argument-parsing code ...

from .api_client import ProductHuntAPI  # noqa: E402
from .protocols import FallbackProvider, ProductProvider, _MISSING_TOKEN_MSG, _NoTokenProvider  # noqa: E402
from .scraper import ProductHuntScraper  # noqa: E402
```

Each `# noqa: E402` comment is an admission: "I know this is wrong, but the tool
complains if I put these at the top."

The same smell echoes into the test file.  `test_cli.py` also carries mid-file
`noqa` imports to test `build_provider`:

```python
from ph_ai_tracker.api_client import ProductHuntAPI  # noqa: E402
from ph_ai_tracker.cli import build_provider  # noqa: E402
from ph_ai_tracker.protocols import FallbackProvider, _NoTokenProvider  # noqa: E402
from ph_ai_tracker.scraper import ProductHuntScraper  # noqa: E402
```

The fix is separation of concerns: the argument-parsing vocabulary belongs in `cli.py`;
the provider-construction factory belongs in a new Framework-layer module `bootstrap.py`.

---

## Acceptance Criteria

1. `src/ph_ai_tracker/bootstrap.py` exists and contains:
   - `build_provider` function (moved verbatim from `cli.py`)
   - `_warn_missing_token` helper (moved from `cli.py`)
   - `_log` logger (moved from `cli.py`)
   - All three adapter imports at the **top** of the file (no `noqa` suppression).
2. `cli.py` contains:
   - `CommonArgs`, `add_common_arguments`, and the five `_add_*` helpers — unchanged.
   - `_ENV_*`, `_DEFAULT_*` constants — unchanged.
   - **No** mid-file imports; **No** `noqa: E402` comments; **No** `build_provider`.
   - All `cli.py` imports remain at the top of the file.
3. `__main__.py` imports `build_provider` from `.bootstrap`.
4. `scheduler.py` imports `build_provider` from `.bootstrap`.
5. `tests/unit/test_bootstrap.py` (new file) tests all `build_provider` cases.
6. `tests/unit/test_cli.py`: the mid-file `noqa` import block and all `test_build_provider_*`
   tests are **deleted**; `test_cli.py` tests only argument-parsing behaviour.
7. `grep -rn "noqa: E402" src/ tests/` → 0 matches.
8. `pytest` exits 0 with no regressions.
9. `make bundle` reports all functions ≤ 20 lines.

---

## Exact Changes Required

### A — Create `src/ph_ai_tracker/bootstrap.py` (new file)

```python
"""Provider factory for ph_ai_tracker.

This module is the single composition root for constructing a ``ProductProvider``
from a strategy name and optional API token.  It imports the concrete adapter
classes (``ProductHuntAPI``, ``ProductHuntScraper``) and the protocol helpers
(``FallbackProvider``, ``_NoTokenProvider``) and wires them together based on
the requested strategy.

Composition roots (``__main__.py``, ``scheduler.py``) call ``build_provider``
once per run; ``AIProductTracker`` receives the result and knows nothing about
how providers are constructed.
"""

from __future__ import annotations

import logging
import warnings

from .api_client import ProductHuntAPI
from .protocols import FallbackProvider, ProductProvider, _MISSING_TOKEN_MSG, _NoTokenProvider
from .scraper import ProductHuntScraper

_log = logging.getLogger(__name__)


def _warn_missing_token() -> None:
    """Emit log WARNING and RuntimeWarning for a missing API token."""
    _log.warning(_MISSING_TOKEN_MSG)
    warnings.warn(_MISSING_TOKEN_MSG, RuntimeWarning, stacklevel=3)


def build_provider(*, strategy: str, api_token: str | None) -> ProductProvider:
    """Construct the correct ``ProductProvider`` for *strategy* and *api_token*.

    Composition roots call this once; ``AIProductTracker`` receives the result.
    Raises ``ValueError`` for unrecognised strategy names so callers can
    surface a clean diagnostic without catching generic exceptions.
    """
    has_token = bool(api_token and api_token.strip())
    api = ProductHuntAPI(api_token) if has_token else None
    if strategy == "scraper":
        return ProductHuntScraper()
    if strategy == "api":
        if api is None:
            _warn_missing_token()
            return _NoTokenProvider()
        return api
    if strategy == "auto":
        return FallbackProvider(api_provider=api, scraper_provider=ProductHuntScraper())
    raise ValueError(f"Unknown strategy: {strategy!r}")
```

### B — `src/ph_ai_tracker/cli.py`

Remove:
- The three mid-file adapter imports (lines 110–112) and their `# noqa: E402` comments
- The `import logging` statement (no longer needed — `_log` moves to `bootstrap.py`)
- The `import warnings` statement (no longer needed)
- The `_log = logging.getLogger(__name__)` module-level assignment
- The `_warn_missing_token` function definition
- The `build_provider` function definition

The resulting file contains only:
- Module docstring (update to remove the `build_provider` sentence)
- `from __future__ import annotations`
- `import argparse`, `import os`, `from dataclasses import dataclass`
- `from .constants import DEFAULT_LIMIT, DEFAULT_SEARCH_TERM`
- `_ENV_*` constants, `_DEFAULT_*` constants
- `_add_strategy_argument`, `_add_search_argument`, `_add_limit_argument`,
  `_add_db_path_argument`, `_add_token_argument`
- `add_common_arguments`
- `CommonArgs`

All imports are at the **top** of the file.  No `noqa` comments.

**Updated module docstring:**

```python
"""Shared CLI argument definitions for ph_ai_tracker.

Both ``__main__.py`` and ``scheduler.py`` expose the same five common
arguments (``--strategy``, ``--search``, ``--limit``, ``--db-path``,
``--token``).  This module is the single source of truth for those argument
names, their corresponding environment variables, and their defaults.

Provider construction is handled by ``bootstrap.build_provider``.
"""
```

### C — `src/ph_ai_tracker/__main__.py`

Update import line:

Before:
```python
from .cli import add_common_arguments, CommonArgs, build_provider
```

After:
```python
from .bootstrap import build_provider
from .cli import add_common_arguments, CommonArgs
```

### D — `src/ph_ai_tracker/scheduler.py`

Update import line:

Before:
```python
from .cli import add_common_arguments, CommonArgs, build_provider
```

After:
```python
from .bootstrap import build_provider
from .cli import add_common_arguments, CommonArgs
```

### E — Create `tests/unit/test_bootstrap.py` (new file)

Move all `test_build_provider_*` tests out of `test_cli.py` and into this new file.
All imports go at the top of the file with no `noqa` suppressions.

```python
"""Unit tests for ph_ai_tracker.bootstrap (provider factory)."""

from __future__ import annotations

import pytest

from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.bootstrap import build_provider
from ph_ai_tracker.protocols import FallbackProvider, _NoTokenProvider
from ph_ai_tracker.scraper import ProductHuntScraper


def test_build_provider_scraper() -> None:
    p = build_provider(strategy="scraper", api_token=None)
    assert isinstance(p, ProductHuntScraper)


def test_build_provider_api_with_token() -> None:
    p = build_provider(strategy="api", api_token="my-token")
    assert isinstance(p, ProductHuntAPI)


def test_build_provider_api_no_token_returns_no_token_provider() -> None:
    with pytest.warns(RuntimeWarning):
        p = build_provider(strategy="api", api_token=None)
    assert isinstance(p, _NoTokenProvider)


def test_build_provider_auto_with_token() -> None:
    p = build_provider(strategy="auto", api_token="my-token")
    assert isinstance(p, FallbackProvider)


def test_build_provider_auto_no_token_emits_warning() -> None:
    with pytest.warns(RuntimeWarning):
        p = build_provider(strategy="auto", api_token=None)
    assert isinstance(p, FallbackProvider)


def test_build_provider_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError, match="rss_feed"):
        build_provider(strategy="rss_feed", api_token=None)
```

### F — `tests/unit/test_cli.py`

Delete:
- The mid-file import block (four `noqa: E402` lines around line 106–109)
- All six `test_build_provider_*` test functions (lines 112–142)

The remaining contents of `test_cli.py` (argument-parsing tests only) are unchanged.

---

## Verification

```bash
# No noqa: E402 suppressions survive anywhere
grep -rn "noqa: E402" src/ tests/

# bootstrap.py exists and contains build_provider
grep -n "def build_provider" src/ph_ai_tracker/bootstrap.py

# cli.py no longer contains build_provider
grep -n "def build_provider\|_warn_missing_token" src/ph_ai_tracker/cli.py

# __main__.py and scheduler.py import from bootstrap
grep -n "from .bootstrap" src/ph_ai_tracker/__main__.py src/ph_ai_tracker/scheduler.py

# Full suite
.venv/bin/python -m pytest --tb=short -q
make bundle
```

Expected: first grep → 0; second → present; third → 0; fourth → present in both files; pytest exits 0; bundle all functions ≤ 20 lines.

---

## Definition of Done

- [ ] `src/ph_ai_tracker/bootstrap.py` created with `build_provider` and `_warn_missing_token`
- [ ] `cli.py` contains only argument-parsing code; all imports at the top; no `noqa`
- [ ] `__main__.py` imports `build_provider` from `.bootstrap`
- [ ] `scheduler.py` imports `build_provider` from `.bootstrap`
- [ ] `tests/unit/test_bootstrap.py` created with all six `build_provider` tests
- [ ] `test_cli.py` mid-file import block and `build_provider` tests deleted
- [ ] `grep -rn "noqa: E402" src/ tests/` → 0 matches
- [ ] `pytest` exits 0, no regressions
- [ ] `make bundle` all functions ≤ 20 lines (check `bootstrap.py` is included)
- [ ] Sprint doc moved to `sprints/completed/`

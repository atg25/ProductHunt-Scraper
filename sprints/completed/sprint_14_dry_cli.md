# Sprint 14 — DRY CLI: Extract Shared Argument Parser

## Uncle Bob Concern Addressed

> "You are repeating yourself. Look at the CLI argument parsing in `__main__.py`
> and `scheduler.py`. Both modules manually read from `os.environ` and set up
> standard `argparse` definitions for `--strategy`, `--search`, `--limit`, and
> `--db-path`. This is duplicated knowledge. Create a centralized
> `CLIBuilder` that handles these shared arguments."
> — Issue #4

---

## Sprint Goal

Identify every `argparse` argument definition and `os.environ` read that
appears in both `__main__.py` and `scheduler.py`, then move the shared logic
to a single `cli.py` module. Both entry-points become thin wrappers that call
`add_common_arguments(parser)` and are no longer responsible for knowing the
environment variable names or default values.

---

## Duplicated Knowledge to Eliminate

| Argument     | Env var                  | Default                     |
| ------------ | ------------------------ | --------------------------- |
| `--strategy` | `PH_AI_TRACKER_STRATEGY` | `"scraper"`                 |
| `--search`   | `PH_AI_TRACKER_SEARCH`   | `"AI"`                      |
| `--limit`    | `PH_AI_TRACKER_LIMIT`    | `20`                        |
| `--db-path`  | `PH_AI_DB_PATH`          | `"./data/ph_ai_tracker.db"` |
| `--token`    | `PRODUCTHUNT_TOKEN`      | `None`                      |

`scheduler.py` additionally defines `--retry-attempts` and
`--retry-backoff-seconds` which are scheduler-specific and remain local.
`__main__.py` additionally defines `--no-persist` which is also local.

---

## New Entity to Create

```
src/ph_ai_tracker/cli.py
  ├── _ENV               (module-level dict mapping arg-name -> env-var name)
  ├── _DEFAULTS          (module-level dict of canonical default values)
  ├── add_common_arguments(parser: argparse.ArgumentParser) -> None
  │     Adds the five shared arguments to an existing parser.
  │     Reads current environment once at call time — allows test isolation.
  └── CommonArgs         (frozen dataclass)
        strategy: str
        search_term: str
        limit: int
        db_path: str
        api_token: str | None
        @staticmethod from_namespace(ns: argparse.Namespace) -> CommonArgs
```

The module is intentionally small (target: ≤ 60 total lines).

---

## TDD Approach — Red → Green → Refactor

### Fixtures needed

Add to `tests/conftest.py`:

```python
@pytest.fixture(autouse=False)
def clean_ph_env(monkeypatch):
    """Remove all PH_AI_* and PRODUCTHUNT_TOKEN env vars for CLI tests."""
    for key in list(os.environ):
        if key.startswith(("PH_AI_", "PRODUCTHUNT_")):
            monkeypatch.delenv(key, raising=False)
```

### Step 1 — Write failing tests first

#### Unit Tests — `tests/unit/test_cli.py` (new file)

```
──────────────────────────────────────────────────────
add_common_arguments
──────────────────────────────────────────────────────
POSITIVE
test_add_common_arguments_registers_strategy
    - parser = argparse.ArgumentParser()
    - add_common_arguments(parser)
    - args = parser.parse_args(["--strategy", "api"])
    - assert args.strategy == "api"

test_add_common_arguments_registers_search
    - args = parser.parse_args(["--search", "chatbot"])
    - assert args.search == "chatbot"

test_add_common_arguments_registers_limit
    - args = parser.parse_args(["--limit", "5"])
    - assert args.limit == 5

test_add_common_arguments_registers_db_path
    - args = parser.parse_args(["--db-path", "/tmp/test.db"])
    - assert args.db_path == "/tmp/test.db"

test_add_common_arguments_registers_token
    - args = parser.parse_args(["--token", "abc123"])
    - assert args.token == "abc123"

test_add_common_arguments_defaults_come_from_env
    - monkeypatch.setenv("PH_AI_TRACKER_STRATEGY", "api")
    - monkeypatch.setenv("PH_AI_TRACKER_LIMIT", "7")
    - args = parser.parse_args([])
    - assert args.strategy == "api"
    - assert args.limit == 7

test_add_common_arguments_uses_hardcoded_defaults_when_env_absent
    - clean_ph_env fixture active
    - args = parser.parse_args([])
    - assert args.strategy == "scraper"
    - assert args.limit == 20
    - assert args.token is None

──────────────────────────────────────────────────────
CommonArgs
──────────────────────────────────────────────────────
POSITIVE
test_common_args_from_namespace_maps_fields
    - ns = argparse.Namespace(strategy="scraper", search="AI",
                              limit=10, db_path="./data/x.db", token=None)
    - ca = CommonArgs.from_namespace(ns)
    - assert ca.strategy == "scraper"
    - assert ca.search_term == "AI"
    - assert ca.limit == 10

test_common_args_is_frozen
    - ca = CommonArgs(strategy="scraper", search_term="AI",
                      limit=20, db_path="./data/x.db", api_token=None)
    - with pytest.raises(Exception): ca.strategy = "api"

NEGATIVE
test_no_env_var_name_is_hardcoded_in_main_module
    - src = inspect.getsource(ph_ai_tracker.__main__)
    - for var in ("PH_AI_TRACKER_STRATEGY", "PH_AI_TRACKER_SEARCH",
                  "PH_AI_TRACKER_LIMIT", "PRODUCTHUNT_TOKEN"):
    -     assert var not in src, f"{var} should live in cli.py only"

test_no_env_var_name_is_hardcoded_in_scheduler_common_args
    - src = inspect.getsource(ph_ai_tracker.scheduler.main)
    - for var in ("PH_AI_TRACKER_STRATEGY", "PH_AI_TRACKER_SEARCH",
                  "PH_AI_TRACKER_LIMIT"):
    -     assert var not in src
```

#### Integration Tests — `tests/integration/test_cli_integration.py` (new file)

```
POSITIVE
test_main_module_cli_accepts_strategy_arg
    - result = subprocess.run([sys.executable, "-m", "ph_ai_tracker",
                               "--strategy", "scraper", "--no-persist",
                               "--search", "AI", "--limit", "1"],
                              capture_output=True, text=True, cwd=REPO_ROOT)
    - assert result.returncode in (0, 2)  # 2 = scraper returned no results, still ran

test_scheduler_cli_accepts_strategy_arg
    - result = subprocess.run([sys.executable, "-m", "ph_ai_tracker.scheduler",
                               "--strategy", "scraper", "--search", "AI",
                               "--limit", "1", "--db-path", str(tmp_path / "t.db")],
                              capture_output=True, text=True, cwd=REPO_ROOT)
    - assert result.returncode in (0, 2)

NEGATIVE
test_cli_module_is_importable
    - from ph_ai_tracker.cli import add_common_arguments, CommonArgs
    - assert callable(add_common_arguments)
```

#### E2E Tests — `tests/e2e/test_e2e_negative.py` (extend)

```
NEGATIVE
test_e2e_env_var_strategy_propagates_to_both_entrypoints
    - env = {**os.environ, "PH_AI_TRACKER_STRATEGY": "scraper",
             "PH_AI_TRACKER_LIMIT": "1"}
    - For each of the two entry-points, assert it parses `strategy == "scraper"`
      and `limit == 1` when invoked with no explicit CLI flags
    - (Use subprocess.run with modified env and --no-persist / mock transport)
```

---

## Implementation Notes

### `cli.py` sketch

```python
"""Shared CLI argument definitions for ph_ai_tracker entry-points."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

_DEFAULTS = {
    "strategy": "scraper",
    "search":   "AI",
    "limit":    20,
    "db_path":  "./data/ph_ai_tracker.db",
    "token":    None,
}

def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the five shared arguments to *parser*, reading env-var defaults at call time."""
    parser.add_argument("--strategy",
        choices=["api", "scraper", "auto"],
        default=os.environ.get("PH_AI_TRACKER_STRATEGY", _DEFAULTS["strategy"]))
    parser.add_argument("--search",
        default=os.environ.get("PH_AI_TRACKER_SEARCH", _DEFAULTS["search"]))
    parser.add_argument("--limit", type=int,
        default=int(os.environ.get("PH_AI_TRACKER_LIMIT", str(_DEFAULTS["limit"]))))
    parser.add_argument("--db-path",
        default=os.environ.get("PH_AI_DB_PATH", _DEFAULTS["db_path"]))
    parser.add_argument("--token",
        default=os.environ.get("PRODUCTHUNT_TOKEN", _DEFAULTS["token"]))


@dataclass(frozen=True, slots=True)
class CommonArgs:
    strategy:  str
    search_term: str
    limit:     int
    db_path:   str
    api_token: str | None

    @staticmethod
    def from_namespace(ns: argparse.Namespace) -> "CommonArgs":
        return CommonArgs(
            strategy=ns.strategy,
            search_term=ns.search,
            limit=max(int(ns.limit), 1),
            db_path=ns.db_path,
            api_token=ns.token or None,
        )
```

### Changes to `__main__.py`

```python
# Before (6 lines of duplication)
parser.add_argument("--strategy", default="scraper", choices=["api", "scraper", "auto"])
parser.add_argument("--search", default="AI")
parser.add_argument("--limit", type=int, default=20)
parser.add_argument("--db-path", default=os.environ.get("PH_AI_DB_PATH", "..."))
parser.add_argument("--token", default=os.environ.get("PRODUCTHUNT_TOKEN"))

# After (2 lines)
from .cli import add_common_arguments, CommonArgs
add_common_arguments(parser)
```

Apply the equivalent transformation to `scheduler.py`'s `main()`.

---

## Definition of Done

- [ ] `src/ph_ai_tracker/cli.py` exists with `add_common_arguments` and `CommonArgs`
- [ ] `__main__.py` uses `add_common_arguments`; none of `PH_AI_TRACKER_STRATEGY`, `PH_AI_TRACKER_SEARCH`, `PH_AI_TRACKER_LIMIT`, `PRODUCTHUNT_TOKEN` are referenced directly
- [ ] `scheduler.py` uses `add_common_arguments` for the five shared args; its scheduler-specific args (`--retry-attempts`, `--retry-backoff-seconds`) remain local
- [ ] All NEW tests listed above pass (Red → Green)
- [ ] All EXISTING tests still pass (no regression)
- [ ] `make bundle` regenerates cleanly

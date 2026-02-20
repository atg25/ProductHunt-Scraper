# Sprint 23 — Generic `_parse_env_var` Helper (DRY)

## Uncle Bob's Complaint

> `_parse_int_env` and `_parse_float_env` in `scheduler.py` are line-for-line
> identical except for the cast callable (`int` vs `float`). If the error
> message or logging logic ever changes, it must be updated in two places.
> Fix: extract a single `_parse_env_var(key, default, cast_callable)` and
> implement both helpers in terms of it.

---

## Root Cause

`scheduler.py` lines 40–57:

```python
def _parse_int_env(key: str, default: int) -> int:
    """Return env var *key* as int; raise ValueError with key name on failure."""
    raw = os.environ.get(key, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid {key}: {raw}") from exc


def _parse_float_env(key: str, default: float) -> float:
    """Return env var *key* as float; raise ValueError with key name on failure."""
    raw = os.environ.get(key, str(default))
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid {key}: {raw}") from exc
```

The only difference is `int(raw)` vs `float(raw)`. Every line of error
handling, the `os.environ.get` call, and the `raise ValueError(...)` message
are duplicated.

---

## TDD Plan

### Step 1 — Write the failing tests (RED)

File: `tests/unit/test_scheduler.py` — add tests for the new private helper
and the refactored wrappers.

| Test                                        | Assertion                                                                              | Colour before fix                        |
| ------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------- |
| `test_parse_env_var_returns_cast_value`     | `_parse_env_var("K", 5, int)` with env `K=42` returns `42`                             | 🔴 FAIL (`_parse_env_var` doesn't exist) |
| `test_parse_env_var_uses_default`           | `_parse_env_var("MISSING_KEY_XYZ", 7, int)` returns `7`                                | 🔴 FAIL                                  |
| `test_parse_env_var_raises_on_invalid`      | `_parse_env_var("K", 0, int)` with env `K=bad` raises `ValueError` mentioning key name | 🔴 FAIL                                  |
| `test_parse_int_env_delegates_to_generic`   | `_parse_int_env("K", 3)` with env `K=9` returns `9` (existing behaviour preserved)     | 🟢 already passes — must stay green      |
| `test_parse_float_env_delegates_to_generic` | `_parse_float_env("K", 1.0)` with env `K=3.14` returns `3.14`                          | 🟢 already passes — must stay green      |

### Step 2 — Add the generic helper and rewrite the wrappers (GREEN)

In `src/ph_ai_tracker/scheduler.py`, add above `_parse_int_env`:

```python
from typing import Callable, TypeVar
_T = TypeVar("_T")

def _parse_env_var(key: str, default: _T, cast: Callable[[str], _T]) -> _T:
    """Return env var *key* cast with *cast*; raise ValueError if cast fails."""
    raw = os.environ.get(key, str(default))
    try:
        return cast(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid {key}: {raw}") from exc
```

Replace `_parse_int_env` and `_parse_float_env` with thin wrappers:

```python
def _parse_int_env(key: str, default: int) -> int:
    """Return env var *key* as int; raise ValueError with key name on failure."""
    return _parse_env_var(key, default, int)

def _parse_float_env(key: str, default: float) -> float:
    """Return env var *key* as float; raise ValueError with key name on failure."""
    return _parse_env_var(key, default, float)
```

All existing call sites (`scheduler_config_from_env`, `_make_scheduler_parser`)
remain identical — they continue calling `_parse_int_env` / `_parse_float_env`.

### Step 3 — Regression check

All existing scheduler tests that exercise `scheduler_config_from_env` and
`_make_scheduler_parser` must pass unchanged.

---

## Acceptance Criteria

1. `_parse_env_var(key, default, cast)` exists as a module-level function in
   `scheduler.py`.
2. `_parse_int_env` and `_parse_float_env` are one-liners that delegate to it.
3. No call site outside `scheduler.py` is changed.
4. New unit tests for `_parse_env_var` pass (correct value, default, error
   message).
5. Full test suite remains green; function sizes remain ≤ 20 lines.

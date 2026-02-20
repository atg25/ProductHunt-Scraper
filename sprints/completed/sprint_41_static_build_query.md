# Sprint 41 — Promote `_build_query` to `@staticmethod`; Eliminate `__new__` Hack

**Status:** Active  
**Source:** Uncle Bob Letter 9, Issue #2 — Static Method Envy  
**Depends on:** Sprint 34 (introduced `QueryContext`; `_build_query` has had its current
signature since that sprint)

---

## Problem Statement

`ProductHuntAPI._build_query` is declared as an instance method but **never references
`self`**. Its entire input comes from its explicit arguments and module-level constants:

```python
def _build_query(
    self, *, first: int, order: str, topic_slug: str | None, search_term: str
) -> QueryContext:
    """Assemble a GraphQL payload and local filter context."""
    order_enum = (order or "RANKING").strip().upper()
    ...
    return QueryContext(payload={...}, local_filter=search_term.strip().lower())
```

The presence of `self` is an accident of history, not a design decision. It signals to
every reader that state is involved when none is.

The test that exercises this method confirms the problem: to call `_build_query` in
isolation the author was forced to bypass the constructor with `__new__`, because the
real constructor requires an `api_token` the test does not need:

```python
def test_build_query_returns_clean_payload_and_local_filter() -> None:
    from ph_ai_tracker.api_client import QueryContext

    api = ProductHuntAPI.__new__(ProductHuntAPI)           # ← bypass constructor
    context = api._build_query(first=10, order="RANKING", topic_slug=None, search_term=" AI ")
    ...
```

The `__new__` hack is the smell made visible. When you need to sneak past the
constructor to test a method, the method does not belong to the instance.

---

## Acceptance Criteria

1. `_build_query` in `api_client.py` is decorated with `@staticmethod`.
2. `self` is removed from `_build_query`'s parameter list.
3. Both internal call sites (`fetch_ai_products` and the retry/pagination path) call
   `_build_query` without relying on instance state — `self._build_query(…)` is still
   valid Python for static methods and may remain, or the calls may be changed to
   `ProductHuntAPI._build_query(…)` for clarity; either is acceptable.
4. The test `test_build_query_returns_clean_payload_and_local_filter` calls
   `ProductHuntAPI._build_query(…)` **directly** with no `__new__` preamble.
5. `grep -n "__new__" tests/unit/test_api_client.py` → 0 matches.
6. `pytest` exits 0 with no regressions.
7. `make bundle` reports all functions ≤ 20 lines.

---

## Exact Changes Required

### A — `src/ph_ai_tracker/api_client.py`

**Step 1:** Add `@staticmethod` decorator immediately above the `def _build_query` line.

**Step 2:** Remove `self` from the parameter list.

Before:

```python
    def _build_query(
        self, *, first: int, order: str, topic_slug: str | None, search_term: str
    ) -> QueryContext:
```

After:

```python
    @staticmethod
    def _build_query(
        *, first: int, order: str, topic_slug: str | None, search_term: str
    ) -> QueryContext:
```

The body of the method is **unchanged** — it never referenced `self`.

**Step 3 (call sites):** The two internal call sites that invoke `self._build_query(…)`
remain syntactically valid after the `@staticmethod` change because Python resolves
static methods through both the class and instance. No change is required to those
lines. However, if the implementer prefers explicit clarity, both call sites may
optionally be updated to `ProductHuntAPI._build_query(…)`. Either form satisfies this
sprint.

### B — `tests/unit/test_api_client.py`

Replace the entire body of `test_build_query_returns_clean_payload_and_local_filter`
to remove the `__new__` hack:

Before:

```python
def test_build_query_returns_clean_payload_and_local_filter() -> None:
    from ph_ai_tracker.api_client import QueryContext

    api = ProductHuntAPI.__new__(ProductHuntAPI)
    context = api._build_query(first=10, order="RANKING", topic_slug=None, search_term=" AI ")

    assert isinstance(context, QueryContext)
    assert set(context.payload.keys()) == {"query", "variables"}
    assert context.local_filter == "ai"
```

After:

```python
def test_build_query_returns_clean_payload_and_local_filter() -> None:
    from ph_ai_tracker.api_client import QueryContext

    context = ProductHuntAPI._build_query(
        first=10, order="RANKING", topic_slug=None, search_term=" AI "
    )

    assert isinstance(context, QueryContext)
    assert set(context.payload.keys()) == {"query", "variables"}
    assert context.local_filter == "ai"
```

The three assertions are preserved exactly. Only the setup lines change.

---

## Verification

```bash
# No __new__ hack remains in the test
grep -n "__new__" tests/unit/test_api_client.py

# _build_query is decorated as @staticmethod
grep -n "@staticmethod" src/ph_ai_tracker/api_client.py

# Full test suite passes
.venv/bin/python -m pytest --tb=short -q

# Bundle still clean
make bundle
```

Expected: first grep returns 0 lines; second grep shows `@staticmethod` before
`_build_query`; pytest exits 0; bundle reports all functions ≤ 20 lines.

---

## Definition of Done

- [ ] `@staticmethod` added to `_build_query` in `api_client.py`
- [ ] `self` removed from `_build_query` parameter list
- [ ] `test_build_query_returns_clean_payload_and_local_filter` calls
      `ProductHuntAPI._build_query(…)` directly with no `__new__`
- [ ] `grep "__new__" tests/unit/test_api_client.py` → 0 matches
- [ ] `pytest` exits 0, no regressions
- [ ] `make bundle` all functions ≤ 20 lines
- [ ] Sprint doc moved to `sprints/completed/`

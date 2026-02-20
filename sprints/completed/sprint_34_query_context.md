# Sprint 34 — Introduce `QueryContext` to Eliminate Payload Pollution

## Uncle Bob's Verdict

> "Look at `_build_query` and `_pop_meta` in `api_client.py`. You are injecting internal application state (`_local_filter`, `_order`, `_topic_slug`) directly into the GraphQL dictionary payload. Then, you pass this polluted dictionary around, only to pop those keys back out right before the HTTP request is made. A data structure destined for the network should not be used as a temporary backpack for internal context. Fix it: Create a dedicated context object (e.g., a `QueryContext` named tuple or dataclass) that holds the clean GraphQL payload and the local filter state, rather than mutating the dictionary twice."

## Problem

`_build_query` returns a single `dict` that bundles two conceptually separate things:

1. The clean network payload (`query`, `variables`) that will be sent to the GraphQL API.
2. Internal application state (`_local_filter`, `_order`, `_topic_slug`) that belongs to the Python layer only.

This forces `fetch_ai_products` to call `_pop_meta` to surgically remove the private keys before the dict reaches `_execute_request`. The retry path in `_retry_with_global_query` repeats the same manual `.pop()` dance a second time:

```python
fallback.pop("_local_filter", None)
fallback.pop("_order", None)
fallback.pop("_topic_slug", None)
```

If a developer adds a new context key to `_build_query` and forgets to add it to `_pop_meta`, a private key silently leaks into the HTTP request body. The dictionary is mutated twice — once to add context and once to remove it — a pattern that is fragile and hard to follow.

## Goal

Introduce a `QueryContext` dataclass that holds the clean GraphQL `payload` dict alongside the `local_filter` string as separate, named fields. `_build_query` returns `QueryContext` directly. `_pop_meta` is deleted; there is nothing left to pop because the payload was never polluted to begin with.

## Implementation

### 1. Add `QueryContext` to `src/ph_ai_tracker/api_client.py`

Define this near `APIConfig` and `RateLimitInfo` at the top of the module:

```python
@dataclass(frozen=True, slots=True)
class QueryContext:
    """A clean GraphQL payload paired with its local post-filter term.

    ``payload`` is safe to send directly over the network — it contains only
    ``query`` and ``variables`` keys.  ``local_filter`` is the lowercased
    search term used for client-side filtering after the response arrives.
    """

    payload: dict[str, Any]
    local_filter: str
```

### 2. Rewrite `_build_query` to return `QueryContext`

```python
def _build_query(
    self, *, first: int, order: str, topic_slug: str | None, search_term: str
) -> QueryContext:
    """Assemble a GraphQL payload and return it bundled with its local filter."""
    order_enum = (order or "RANKING").strip().upper()
    if order_enum not in {"RANKING", "NEWEST"}:
        order_enum = "RANKING"
    if topic_slug:
        tmpl = _GQL_TOPIC_POSTS_TMPL
        variables: dict[str, Any] = {"slug": str(topic_slug), "first": int(first)}
    else:
        tmpl = _GQL_GLOBAL_POSTS_TMPL
        variables = {"first": int(first)}
    payload = {"query": tmpl.format(order=order_enum), "variables": variables}
    return QueryContext(payload=payload, local_filter=search_term.strip().lower())
```

### 3. Update `fetch_ai_products` to use `QueryContext`

```python
def fetch_ai_products(self, *, search_term: str = DEFAULT_SEARCH_TERM,
                      limit: int = DEFAULT_LIMIT, topic_slug: str | None = "artificial-intelligence",
                      order: str = "RANKING") -> list[Product]:
    """Fetch AI products; over-fetches then sorts + truncates to ``limit``."""
    limit_int = max(int(limit), 1)
    ctx = self._build_query(
        first=min(max(limit_int * _PAGINATION_MULTIPLIER, _MIN_FETCH_SIZE), _MAX_FETCH_SIZE),
        order=order, topic_slug=topic_slug, search_term=search_term,
    )
    products = self._fetch_and_build(ctx.payload, topic_slug, limit_int, order, ctx.local_filter)
    products.sort(key=lambda p: p.votes_count, reverse=True)
    return products[:limit_int]
```

### 4. Update `_retry_with_global_query` to use `QueryContext`

```python
def _retry_with_global_query(
    self, limit_int: int, order: str, local_filter: str
) -> dict[str, Any]:
    """Re-issue the query without a topic slug when the topic-scoped query
    returns GraphQL errors (schema divergence between API versions).
    """
    ctx = self._build_query(
        first=limit_int, order=order, topic_slug=None, search_term=local_filter,
    )
    return self._execute_request(ctx.payload)
```

### 5. Delete `_pop_meta`

Remove the `_pop_meta` static method entirely. There are no remaining callers.

### 6. Update `tests/unit/test_api_client.py`

- Remove any test that directly exercises `_pop_meta`.
- Add a test asserting that `_build_query` returns a `QueryContext` whose `payload` dict contains only `"query"` and `"variables"` keys (no private `_`-prefixed keys):

```python
def test_build_query_payload_contains_no_private_keys() -> None:
    api = ProductHuntAPI.__new__(ProductHuntAPI)
    ctx = api._build_query(first=10, order="RANKING", topic_slug=None, search_term="AI")
    assert isinstance(ctx, QueryContext)
    assert set(ctx.payload.keys()) == {"query", "variables"}
    assert ctx.local_filter == "ai"
```

## Acceptance Criteria

- [ ] `QueryContext` dataclass exists in `api_client.py` with `payload` and `local_filter` fields.
- [ ] `_build_query` returns `QueryContext` with a clean `payload` dict (no `_`-prefixed keys).
- [ ] `_pop_meta` is deleted; zero references to it remain in the codebase.
- [ ] The `_retry_with_global_query` path uses `ctx.payload` directly.
- [ ] Test coverage confirms no private keys leak into the network payload.
- [ ] Full test suite remains green.

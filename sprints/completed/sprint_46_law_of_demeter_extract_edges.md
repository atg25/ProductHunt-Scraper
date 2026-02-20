# Sprint 46 — Law of Demeter: Eliminate Train Wreck in `_extract_edges`

**Uncle Bob Letter 11, Issue #1**
**Depends on:** Sprint 34 (`QueryContext` / `_extract_edges` has its final form) and Sprint 41 (`@staticmethod` promotion pattern is already established)

---

## Problem Statement

`ProductHuntAPI._extract_edges` violates the Law of Demeter (Principle of Least Knowledge) via a chained `or`/`.get()` cascade:

```python
topic_edges = ((data.get("topic") or {}).get("posts") or {}).get("edges")
```

This single expression digs three levels deep through the response dict — `data → topic → posts → edges` — using mixed `or {}` and `.get()` fallbacks at each hop.  The reader must mentally parse the entire chain to understand the intent.  It also hides bugs: if the API returns `{"topic": None}`, the silent `or {}` swallows that and produces the same result as a completely missing `topic` key.

The same but slightly smaller smell exists in `_node_to_product`:

```python
topics_edges = (((node.get("topics") or {}).get("edges")) or [])
```

---

## Goal

Split the navigation into named, one-level-at-a-time `@staticmethod` helpers that reveal intent and validate shape explicitly.

---

## Files to Change

| File | Change |
|------|--------|
| `src/ph_ai_tracker/api_client.py` | Extract `_parse_topic_edges`, `_parse_global_edges`; simplify `_extract_edges`; extract `_parse_topic_edges_from_node` for `_node_to_product` |
| `tests/unit/test_api_client.py` | Add focused unit tests for each new parser helper |

---

## Exact Code Changes

### `src/ph_ai_tracker/api_client.py`

**Delete** the current `_extract_edges` method body and **replace** with three small `@staticmethod` helpers plus a simplified coordinator:

```python
@staticmethod
def _parse_topic_edges(data: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Return edges from ``data["topic"]["posts"]``, or ``None`` if that shape is absent.

    Returns ``None`` (not an empty list) so the caller can distinguish
    "topic shape is present but empty" from "topic shape is not present at all".
    """
    topic = data.get("topic")
    if not isinstance(topic, dict):
        return None
    posts = topic.get("posts")
    if not isinstance(posts, dict):
        return None
    edges = posts.get("edges")
    return edges if isinstance(edges, list) else None

@staticmethod
def _parse_global_edges(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return edges from ``data["posts"]``, or ``[]`` if that shape is absent."""
    posts = data.get("posts")
    if not isinstance(posts, dict):
        return []
    edges = posts.get("edges")
    return edges if isinstance(edges, list) else []

def _extract_edges(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return edges from ``data.topic.posts`` (topic shape) or ``data.posts`` (global)."""
    data = payload.get("data") or {}
    topic_edges = self._parse_topic_edges(data)
    if topic_edges is not None:
        return topic_edges
    return self._parse_global_edges(data)
```

**Also update** `_node_to_product` to avoid its own two-level chain.  Extract a `@staticmethod`:

```python
@staticmethod
def _parse_topic_edges_from_node(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the topic-edge list from a GraphQL post node, or ``[]``."""
    topics = node.get("topics")
    if not isinstance(topics, dict):
        return []
    edges = topics.get("edges")
    return edges if isinstance(edges, list) else []
```

And inside `_node_to_product`:

```python
# Before:
topics_edges = (((node.get("topics") or {}).get("edges")) or [])
# After:
topics_edges = ProductHuntAPI._parse_topic_edges_from_node(node)
```

---

## New Tests to Add in `tests/unit/test_api_client.py`

Add the following four tests (use `from ph_ai_tracker.api_client import ProductHuntAPI`):

```python
def test_parse_topic_edges_returns_list_when_present() -> None:
    data = {"topic": {"posts": {"edges": [{"node": {"name": "X"}}]}}}
    edges = ProductHuntAPI._parse_topic_edges(data)
    assert edges == [{"node": {"name": "X"}}]

def test_parse_topic_edges_returns_none_when_topic_missing() -> None:
    assert ProductHuntAPI._parse_topic_edges({}) is None

def test_parse_topic_edges_returns_none_when_posts_missing() -> None:
    assert ProductHuntAPI._parse_topic_edges({"topic": {"other": 1}}) is None

def test_parse_global_edges_returns_list_when_present() -> None:
    data = {"posts": {"edges": [{"node": {"name": "Y"}}]}}
    edges = ProductHuntAPI._parse_global_edges(data)
    assert edges == [{"node": {"name": "Y"}}]

def test_parse_global_edges_returns_empty_when_absent() -> None:
    assert ProductHuntAPI._parse_global_edges({}) == []

def test_parse_topic_edges_from_node_returns_list_when_present() -> None:
    node = {"topics": {"edges": [{"node": {"name": "AI"}}]}}
    assert ProductHuntAPI._parse_topic_edges_from_node(node) == [{"node": {"name": "AI"}}]

def test_parse_topic_edges_from_node_returns_empty_when_absent() -> None:
    assert ProductHuntAPI._parse_topic_edges_from_node({}) == []
```

---

## Function Size Constraint

All new helpers must be ≤ 20 lines each.  Run `make bundle` to confirm after implementation.

---

## Acceptance Criteria

- [ ] `_extract_edges` body contains **no** chained `.get()` — it calls `_parse_topic_edges` and `_parse_global_edges` only.
- [ ] `_node_to_product` body contains **no** chained `or {}`/`.get()` — it calls `_parse_topic_edges_from_node`.
- [ ] `_parse_topic_edges`, `_parse_global_edges`, `_parse_topic_edges_from_node` are all `@staticmethod`.
- [ ] All 7 new tests pass.
- [ ] Full pytest suite passes (no regressions).
- [ ] `make bundle` reports ✓ all functions ≤ 20 lines.
- [ ] `grep -r "or {}).get" src/ph_ai_tracker/api_client.py` → 0 matches.

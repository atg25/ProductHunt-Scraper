# Sprint 30 — Narrow Exception Catch in FallbackProvider

## Uncle Bob's Verdict

> "Adding a `# noqa` linter bypass does not make the code smell go away; it just hides the warning. Catching `Exception` here is too broad. If the API client has a syntax error or a bug, this block will silently swallow it and fall back to the scraper, masking the root cause. Fix it: You have a beautifully defined exception hierarchy where all API failures fall under `APIError`. Change this block to explicitly catch `APIError`. Let unexpected runtime bugs crash loudly so they can be fixed."

## Problem

In `src/ph_ai_tracker/protocols.py`, the `FallbackProvider.fetch_products` method uses a blanket `except Exception:` block to trigger the fallback to the scraper. This violates best practices by swallowing unexpected runtime errors (like `TypeError`, `NameError`, or `RuntimeError`), making debugging difficult and masking true system failures.

## Goal

Change the `except` block to catch only `APIError`. Unexpected exceptions must crash loudly and propagate up the call stack.

## TDD Plan

### RED Phase

In `tests/unit/test_protocols.py`, add a new test to verify that unexpected exceptions are not swallowed:

```python
def test_fallback_provider_propagates_unexpected_exceptions() -> None:
    class _BuggyAPI(_StubScraper):
        source_name = "api"
        def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
            raise RuntimeError("Unexpected bug in API client")

    provider = FallbackProvider(api_provider=_BuggyAPI(), scraper_provider=_StubScraper())

    with pytest.raises(RuntimeError, match="Unexpected bug"):
        provider.fetch_products(search_term="AI", limit=10)
```

Run the test. It will **FAIL** because the current `except Exception:` block will swallow the `RuntimeError` and return the scraper's empty list.

### GREEN Phase

In `src/ph_ai_tracker/protocols.py`:

1. Import `APIError` from `.exceptions`.
2. Change `except Exception:` to `except APIError:`.
3. Remove the `# noqa: BLE001` comment.

```python
    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        """Try API; on APIError fall through to scraper."""
        from .exceptions import APIError  # local import to avoid circular dependency if needed, or top-level if safe

        if self._api is not None:
            try:
                return self._api.fetch_products(search_term=search_term, limit=limit)
            except APIError:
                pass
        return self._scraper.fetch_products(search_term=search_term, limit=limit)
```

## Acceptance Criteria

- [ ] `FallbackProvider.fetch_products` catches `APIError` instead of `Exception`.
- [ ] `# noqa: BLE001` is removed from `protocols.py`.
- [ ] New test `test_fallback_provider_propagates_unexpected_exceptions` passes.
- [ ] Full test suite remains green.

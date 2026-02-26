# Sprint 51 — Pure `canonical_key` Function

## Objective

Extract and strengthen the canonical key logic from the storage layer into a
pure, fully-tested function that lives in `models.py`.

## Why (Clean Architecture)

Canonical key generation is **Enterprise Policy**: it defines what makes two
products "the same". That concept belongs in the entity layer, not inside a
SQL helper. Extracting it makes the rule visible, testable in isolation, and
reusable without touching the database.

## Scope

**In:** `src/ph_ai_tracker/models.py`,
`src/ph_ai_tracker/storage.py`,
`tests/unit/test_models.py`  
**Out:** No schema change. The SQLite `UNIQUE(canonical_key)` constraint is
unchanged.

---

## TDD Cycle

### Red — write failing tests first

File: `tests/unit/test_models.py`

**URL-based key:**

```
test_canonical_key_url_lowercases
    Product("X", url="HTTPS://Example.COM/p/foo") → "url:https://example.com/p/foo"

test_canonical_key_url_strips_query
    Product("X", url="https://example.com/p?ref=1") → "url:https://example.com/p"

test_canonical_key_url_strips_fragment
    Product("X", url="https://example.com/p#top") → "url:https://example.com/p"

test_canonical_key_url_removes_trailing_slash
    Product("X", url="https://example.com/p/") → "url:https://example.com/p"

test_canonical_key_url_strips_whitespace
    Product("X", url="  https://example.com/p  ") → "url:https://example.com/p"

test_canonical_key_url_preserves_scheme_host_path
    Product("X", url="https://ph.co/p/myapp?x=1#y") → "url:https://ph.co/p/myapp"
```

**Name-based fallback (URL absent or invalid):**

```
test_canonical_key_no_url_uses_name
    Product("My App") → "name:my app"

test_canonical_key_name_lowercased
    Product("MY APP") → "name:my app"

test_canonical_key_name_strips_whitespace
    Product("  my app  ") → "name:my app"

test_canonical_key_name_collapses_internal_whitespace
    Product("my   app") → "name:my app"

test_canonical_key_name_removes_surrounding_punctuation
    Product("...my app!!!") → "name:my app"

test_canonical_key_invalid_url_falls_back_to_name
    Product("my app", url="not a url") → "name:my app"

test_canonical_key_empty_url_falls_back_to_name
    Product("my app", url="") → "name:my app"
```

**Idempotence:**

```
test_canonical_key_idempotent_url
    Applying canonical_key twice to a key already in canonical form is stable
    (verify the output does not change if re-processed as a URL).

test_canonical_key_idempotent_name
    canonical_key(Product(canonical_key(Product("My App"))[5:])) == canonical_key(Product("My App"))
```

**Format contract:**

```
test_canonical_key_always_starts_with_url_or_name_prefix
    All outputs match ^(url:|name:).+
```

### Green

1. Add `canonical_key(product: Product) -> str` module-level function in `models.py`.
2. Implement URL branch: `urllib.parse.urlparse` → validate by checking
   `parsed.scheme in {"http","https"}` and `parsed.netloc != ""`; if invalid
   treat URL as absent.
3. Strip query (`_replace(query="", fragment="")`) and trailing slash from path.
4. Name branch: `re.sub(r'\s+', ' ', name.strip()).strip(string.punctuation)`.
5. Return `f"url:{...}"` or `f"name:{...}"`.

### Refactor

Update `storage._upsert_product` (or whichever helper computes the key) to
call `models.canonical_key(product)` instead of the inline logic.

---

## Definition of Done

- [x] All new canonicalization tests green.
- [x] Idempotence tests green.
- [x] `canonical_key` is a pure function: no I/O, no mutation, no side effects.
- [x] `make bundle` passes.
- [x] Storage layer tests still green (storage now delegates to `canonical_key`).

# Sprint 28 — Remove Banner Comments from scraper.py

## Uncle Bob's Verdict

> "You have included these massive visual ASCII banners. I call these 'banners' or 'posies.'
> They are clutter. A banner is usually a sign that a class is getting too large and the
> developer is trying to create artificial boundaries within it. If a class is cohesive and
> well-organized, it does not need a billboard to tell the reader what they are looking at.
> Delete the banners. Let the code's structure and method names speak for themselves."

## Problem

`ProductHuntScraper` in `scraper.py` contains three ASCII banner blocks that serve no semantic
purpose. Each banner is a three-line `# ---- #` / label / `# ---- #` clutter pattern:

1. **Lines ~294–296** — `# Delegation shims — preserve backwards compatibility for tests #`
2. **Lines ~310–312** — `# Private pipeline steps #`
3. **Lines ~362–364** — `# Public API #`

The presence of these banners is a code smell. They signal that someone felt the class needed
roadmaps to navigate it — implying the class is too wide or poorly cohesive. The delegation
shim methods, private pipeline methods, and public API method are already clearly separated by
naming conventions (`_extract_*`, `_fetch_*`, `scrape_*`, `fetch_*`).

## Goal

Delete all three banner blocks from `ProductHuntScraper`. Method names and docstrings carry
sufficient documentation weight without visual noise.

## Changes

### `src/ph_ai_tracker/scraper.py`

Remove three banner blocks (nine lines total):

```python
# ------------------------------------------------------------------ #
# Delegation shims — preserve backwards compatibility for tests        #
# ------------------------------------------------------------------ #
```

```python
# ------------------------------------------------------------------ #
# Private pipeline steps                                               #
# ------------------------------------------------------------------ #
```

```python
# ------------------------------------------------------------------ #
# Public API                                                           #
# ------------------------------------------------------------------ #
```

No logic changes. No other files modified.

## Tests

No test changes required. Remove any test that asserts the banner strings are present
in the source file, should any such test exist.

## Acceptance Criteria

- [ ] `grep -c "# ---" src/ph_ai_tracker/scraper.py` returns `0` (ignoring the module-level
      docstring section separator on line 9, which is a reStructuredText underline, not a banner).
- [ ] Full test suite remains green.
- [ ] `make bundle` exits 0.

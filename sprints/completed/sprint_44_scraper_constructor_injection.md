# Sprint 44 — Constructor Injection for Extractors; Fix Encapsulation Violation

**Status:** Active  
**Source:** Uncle Bob Letter 10, Issue #2 — Encapsulation Violation (Prying Open the Object)  
**Depends on:** Sprint 13 (introduced `NextDataExtractor`, `DOMFallbackExtractor`, `ProductEnricher`); Sprint 40 (removed shim methods and redirected tests to use extractors directly)

---

## Problem Statement

Three tests in `tests/unit/test_scraper.py` need to inject a broken extractor to
verify the error-handling path inside `_extract_products`.  Instead of injecting
through the constructor, they directly overwrite the private attribute after
instantiation:

```python
def test_extract_products_propagates_runtime_error() -> None:
    class BadExtractor:
        def extract(self, html: str) -> list:
            raise RuntimeError("bug")

    s = ProductHuntScraper()
    try:
        s._next_data = BadExtractor()     # ← private attribute overwrite
        with pytest.raises(RuntimeError, match="bug"):
            s._extract_products("<html></html>")
    finally:
        s.close()
```

All three tests (`…runtime_error`, `…type_error`, `…recovers_from_known_parse_exceptions`)
follow the same open-heart-surgery pattern.  Private attributes are private; a test
that pokes at them is coupled to the implementation's field names and risks masking
real bugs when those fields are renamed.

The fix is **Dependency Injection**: expose the extractors as optional constructor
parameters so tests can supply a fake through the documented public interface.

---

## Acceptance Criteria

1. `ProductHuntScraper.__init__` accepts three new keyword-only parameters:
   - `next_data_extractor: NextDataExtractor | None = None`
   - `dom_fallback_extractor: DOMFallbackExtractor | None = None`
   - `enricher: ProductEnricher | None = None`
2. When non-`None`, each injected value is used instead of the default construction.
3. All existing call-sites that pass **none** of the three new kwargs are unaffected —
   the defaults reproduce the pre-sprint behaviour exactly.
4. The three tests that mutate `s._next_data`, `s._dom_fallback`, or `s._enricher`
   are rewritten to use constructor injection instead.
5. `grep -n "_next_data\s*=" tests/unit/test_scraper.py` → 0 matches (no post-construction
   mutation).
6. `pytest` exits 0 with no regressions.
7. `make bundle` reports all functions ≤ 20 lines.

---

## Exact Changes Required

### A — `src/ph_ai_tracker/scraper.py`

**`ProductHuntScraper.__init__`** — add three optional injection parameters and use
them:

Before:
```python
    def __init__(
        self,
        *,
        config: ScraperConfig | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config      = config or ScraperConfig()
        self._client      = httpx.Client(
            timeout=self._config.timeout_seconds,
            transport=transport,
            headers={"User-Agent": "ph_ai_tracker/0.1.0 (+https://github.com/)"},
        )
        self._next_data   = NextDataExtractor()
        self._dom_fallback = DOMFallbackExtractor(self._config.base_url)
        self._enricher    = ProductEnricher(client=self._client)
```

After:
```python
    def __init__(
        self,
        *,
        config: ScraperConfig | None = None,
        transport: httpx.BaseTransport | None = None,
        next_data_extractor: NextDataExtractor | None = None,
        dom_fallback_extractor: DOMFallbackExtractor | None = None,
        enricher: ProductEnricher | None = None,
    ) -> None:
        self._config      = config or ScraperConfig()
        self._client      = httpx.Client(
            timeout=self._config.timeout_seconds,
            transport=transport,
            headers={"User-Agent": "ph_ai_tracker/0.1.0 (+https://github.com/)"},
        )
        self._next_data    = next_data_extractor or NextDataExtractor()
        self._dom_fallback = dom_fallback_extractor or DOMFallbackExtractor(self._config.base_url)
        self._enricher     = enricher or ProductEnricher(client=self._client)
```

No other line in `scraper.py` changes.

### B — `tests/unit/test_scraper.py` — rewrite three tests

**`test_extract_products_propagates_runtime_error`:**

Before:
```python
def test_extract_products_propagates_runtime_error() -> None:
    class BadExtractor:
        def extract(self, html: str) -> list:
            raise RuntimeError("bug")

    s = ProductHuntScraper()
    try:
        s._next_data = BadExtractor()
        with pytest.raises(RuntimeError, match="bug"):
            s._extract_products("<html></html>")
    finally:
        s.close()
```

After:
```python
def test_extract_products_propagates_runtime_error() -> None:
    class BadExtractor:
        def extract(self, html: str) -> list:
            raise RuntimeError("bug")

    s = ProductHuntScraper(next_data_extractor=BadExtractor())
    try:
        with pytest.raises(RuntimeError, match="bug"):
            s._extract_products("<html></html>")
    finally:
        s.close()
```

**`test_extract_products_propagates_type_error`:**

Before:
```python
def test_extract_products_propagates_type_error() -> None:
    class BadExtractor:
        def extract(self, html: str) -> list:
            raise TypeError("bug")

    s = ProductHuntScraper()
    try:
        s._next_data = BadExtractor()
        with pytest.raises(TypeError, match="bug"):
            s._extract_products("<html></html>")
    finally:
        s.close()
```

After:
```python
def test_extract_products_propagates_type_error() -> None:
    class BadExtractor:
        def extract(self, html: str) -> list:
            raise TypeError("bug")

    s = ProductHuntScraper(next_data_extractor=BadExtractor())
    try:
        with pytest.raises(TypeError, match="bug"):
            s._extract_products("<html></html>")
    finally:
        s.close()
```

**`test_extract_products_recovers_from_known_parse_exceptions`:**

Before:
```python
@pytest.mark.parametrize("exc", [ValueError("parse"), AttributeError("attr"), KeyError("k")])
def test_extract_products_recovers_from_known_parse_exceptions(exc: Exception) -> None:
    class BadExtractor:
        def __init__(self, err: Exception) -> None:
            self._err = err

        def extract(self, html: str) -> list:
            raise self._err

    s = ProductHuntScraper()
    try:
        s._next_data = BadExtractor(exc)
        assert s._extract_products("<html></html>") == []
    finally:
        s.close()
```

After:
```python
@pytest.mark.parametrize("exc", [ValueError("parse"), AttributeError("attr"), KeyError("k")])
def test_extract_products_recovers_from_known_parse_exceptions(exc: Exception) -> None:
    class BadExtractor:
        def __init__(self, err: Exception) -> None:
            self._err = err

        def extract(self, html: str) -> list:
            raise self._err

    s = ProductHuntScraper(next_data_extractor=BadExtractor(exc))
    try:
        assert s._extract_products("<html></html>") == []
    finally:
        s.close()
```

---

## Verification

```bash
# No post-construction private attribute mutation in tests
grep -n "\._next_data\s*=\|\._dom_fallback\s*=\|\._enricher\s*=" tests/unit/test_scraper.py

# Constructor signature updated in production code
grep -n "next_data_extractor\|dom_fallback_extractor" src/ph_ai_tracker/scraper.py

# Full test suite
.venv/bin/python -m pytest --tb=short -q
make bundle
```

Expected: first grep → 0 matches (no private mutation); second → present in `__init__`; pytest exits 0; bundle all functions ≤ 20 lines.

---

## Definition of Done

- [ ] `ProductHuntScraper.__init__` accepts `next_data_extractor`, `dom_fallback_extractor`, `enricher` optional kwargs
- [ ] Default behaviour (no kwargs) is identical to pre-sprint
- [ ] Three tests rewritten to inject through the constructor
- [ ] `grep "s\._next_data\s*=" tests/unit/test_scraper.py` → 0 matches
- [ ] `pytest` exits 0, no regressions
- [ ] `make bundle` all functions ≤ 20 lines
- [ ] Sprint doc moved to `sprints/completed/`

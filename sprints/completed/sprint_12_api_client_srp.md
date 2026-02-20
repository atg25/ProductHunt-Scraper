# Sprint 12 — API Client: Single Responsibility & Comment Deodorant

## Uncle Bob Concerns Addressed

> "The most egregious offender is `api_client.ProductHuntAPI.fetch_ai_products`,
> clocking in at 173 lines. This function is a sprawling monolith … A function
> should do one thing, do it well, and do it only."
> — Issue #1

> "If you need a block comment to explain a complex chunk of regex and boolean
> logic, the code is not expressive enough. Extract that regex logic into a
> class named `StrictAIFilter` with a method `is_match(text: str) -> bool`."
> — Issue #3

---

## Sprint Goal

Decompose `fetch_ai_products` (173 lines) into a set of small, named, single-
purpose helpers. Every extracted class must be independently unit-testable.
The method itself becomes a ≤20 line orchestrator that reads like a sentence.

---

## Acceptance Criteria

1. `fetch_ai_products` body **≤ 20 lines** after refactoring.
2. A `RateLimitParser` class with a `parse(headers) -> RateLimitInfo` method
   encapsulates all `X-Rate-Limit-*` header parsing (currently 12 inline lines).
3. A `StrictAIFilter` class with an `is_match(text: str) -> bool` method
   replaces the inline regex block and its explanatory comment.
4. A `GraphQLResponseParser` (or `_parse_api_response` private method) handles
   JSON decode → error checking → `_extract_edges` → `Product` construction.
5. The retry-on-schema-error path is extracted to `_retry_with_global_query`.
6. The comment beginning `# "AI" as a substring matches lots of unrelated words`
   is **deleted** — the `StrictAIFilter` name explains itself.
7. All existing unit, integration, and e2e tests continue to pass without
   change (behavior is identical; only structure changes).
8. All new tests listed below pass.

---

## New Entities to Create

```
src/ph_ai_tracker/api_client.py
  ├── RateLimitInfo        (frozen dataclass)  — parsed rate-limit header values
  ├── RateLimitParser      (class)             — parse(headers) -> RateLimitInfo
  ├── StrictAIFilter       (class)             — is_match(text, topics) -> bool
  │                                              is_strict_term(term) -> bool
  └── ProductHuntAPI
        ├── fetch_ai_products   ≤ 20 lines (orchestrator)
        ├── _execute_request    — POST + HTTP error handling
        ├── _retry_with_global_query  — schema-change retry path
        └── _build_products_from_edges  — edge list → list[Product]
```

---

## TDD Approach — Red → Green → Refactor

### Step 1 — Write failing tests first

#### Unit Tests — `tests/unit/test_api_client.py` (extend existing file)

```
──────────────────────────────────────────────────────
RateLimitParser
──────────────────────────────────────────────────────
POSITIVE
test_rate_limit_parser_extracts_all_headers
    - Headers with X-Rate-Limit-Limit=100, Remaining=0, Reset=60, Retry-After=30
    - assert result.limit == 100, result.remaining == 0, result.reset_seconds == 60
    - assert result.retry_after == 30

test_rate_limit_parser_prefers_reset_over_retry_after_when_both_present
    - Headers with Reset=90 and Retry-After=30
    - assert result.retry_after == 90  (Reset takes precedence per PH docs)

test_rate_limit_parser_returns_none_for_missing_headers
    - Empty headers dict
    - assert all fields are None

NEGATIVE
test_rate_limit_parser_handles_non_integer_values_gracefully
    - Headers with X-Rate-Limit-Limit="not-a-number"
    - assert result.limit is None (no exception raised)

──────────────────────────────────────────────────────
StrictAIFilter
──────────────────────────────────────────────────────
POSITIVE
test_strict_ai_filter_matches_word_boundary_ai
    - text="Build AI tools faster", topics=()
    - assert StrictAIFilter().is_match(text, topics) is True

test_strict_ai_filter_matches_llm_word_boundary
    - text="LLM-powered assistant", topics=()
    - assert result is True

test_strict_ai_filter_matches_ml_word_boundary
    - text="ML model training", topics=()
    - assert result is True

test_strict_ai_filter_matches_artificial_intelligence_phrase
    - text="artificial intelligence platform", topics=()
    - assert result is True

test_strict_ai_filter_matches_artificial_intelligence_topic
    - text="random", topics=("artificial intelligence",)
    - assert result is True

NEGATIVE
test_strict_ai_filter_rejects_paid_as_false_positive
    - text="get paid faster", topics=()
    - assert StrictAIFilter().is_match(text, topics) is False

test_strict_ai_filter_rejects_email_as_false_positive
    - text="send email notifications", topics=()
    - assert result is False

test_strict_ai_filter_rejects_trail_as_false_positive
    - text="audit trail viewer", topics=()
    - assert result is False

test_is_strict_term_returns_true_for_empty_search
    - assert StrictAIFilter.is_strict_term("") is True

test_is_strict_term_returns_true_for_bare_ai
    - assert StrictAIFilter.is_strict_term("ai") is True

test_is_strict_term_returns_false_for_specific_term
    - assert StrictAIFilter.is_strict_term("chatbot") is False

──────────────────────────────────────────────────────
RateLimitInfo dataclass
──────────────────────────────────────────────────────
POSITIVE
test_rate_limit_info_is_frozen
    - rl = RateLimitInfo(limit=100, remaining=0, reset_seconds=60, retry_after=60)
    - with pytest.raises(Exception): rl.limit = 99  # frozen dataclass

──────────────────────────────────────────────────────
fetch_ai_products orchestration (mock transport, existing shape)
──────────────────────────────────────────────────────
POSITIVE
test_fetch_ai_products_strict_filter_excludes_paid_product
    - Mock response includes a product named "GetPaid Invoicing" with no AI signals
    - assert "GetPaid Invoicing" NOT in [p.name for p in result]

test_fetch_ai_products_strict_filter_includes_llm_product
    - Mock response includes a product taglined "LLM-powered code review"
    - assert that product IS in result

NEGATIVE
test_fetch_ai_products_raises_rate_limit_error_on_429
    - Already exists; confirm it still passes after refactor
```

#### Integration Tests — `tests/integration/test_api_integration.py` (extend)

```
POSITIVE
test_strict_ai_filter_class_importable_from_api_client
    - from ph_ai_tracker.api_client import StrictAIFilter
    - assert callable(StrictAIFilter)

test_rate_limit_parser_class_importable_from_api_client
    - from ph_ai_tracker.api_client import RateLimitParser
    - assert callable(RateLimitParser)

NEGATIVE
test_fetch_ai_products_body_is_under_20_lines
    - Use inspect.getsource(ProductHuntAPI.fetch_ai_products)
    - Count non-blank, non-comment lines; assert <= 20
```

#### E2E Tests — `tests/e2e/test_e2e_negative.py` (extend)

```
NEGATIVE
test_e2e_strict_filter_rejects_false_positives_end_to_end
    - Construct a mock transport that returns products named
      "PaidUp", "EmailTrail", "Portraiture" alongside "GPT Wrapper"
    - Call tracker.get_products(strategy="api", search_term="AI", limit=10)
    - assert no false-positive products in result
    - assert "GPT Wrapper" IS in result
```

---

## Implementation Notes

### `RateLimitInfo` & `RateLimitParser`

```python
@dataclass(frozen=True, slots=True)
class RateLimitInfo:
    limit: int | None
    remaining: int | None
    reset_seconds: int | None
    retry_after: int | None  # effective value to use for back-off


class RateLimitParser:
    @staticmethod
    def parse(headers: Mapping[str, str]) -> RateLimitInfo:
        def _int(key: str) -> int | None: ...
        reset   = _int("X-Rate-Limit-Reset")
        retry   = _int("Retry-After")
        return RateLimitInfo(
            limit=_int("X-Rate-Limit-Limit"),
            remaining=_int("X-Rate-Limit-Remaining"),
            reset_seconds=reset,
            retry_after=reset if reset is not None else retry,
        )
```

### `StrictAIFilter`

```python
_STRICT_TERMS = frozenset({"", "ai", "artificial intelligence"})
_AI_PATTERN   = re.compile(
    r"\bartificial\s+intelligence\b|\b(ai|ml|llm|gpt)\b",
    flags=re.IGNORECASE,
)

class StrictAIFilter:
    @staticmethod
    def is_strict_term(term: str) -> bool:
        return term.strip().lower() in _STRICT_TERMS

    def is_match(self, haystack: str, topics: tuple[str, ...]) -> bool:
        if "artificial intelligence" in {t.lower() for t in topics}:
            return True
        return bool(_AI_PATTERN.search(haystack))
```

### `fetch_ai_products` after refactor (target shape)

```python
def fetch_ai_products(self, *, search_term="AI", limit=20,
                      topic_slug="artificial-intelligence", order="RANKING") -> list[Product]:
    limit_int      = max(int(limit), 1)
    request_first  = min(max(limit_int * 5, 20), 50)
    payload        = self._build_query(first=request_first, order=order,
                                       topic_slug=topic_slug, search_term=search_term)
    raw_filter     = (payload.pop("_local_filter") or "").strip().lower()
    payload.pop("_order", None); payload.pop("_topic_slug", None)

    data = self._execute_request(payload)
    if "errors" in (data.get("errors") or []) and topic_slug:
        data = self._retry_with_global_query(limit_int, order, raw_filter)

    if data.get("errors"):
        raise APIError("GraphQL errors returned")

    products = self._build_products_from_edges(self._extract_edges(data), raw_filter)
    products.sort(key=lambda p: p.votes_count, reverse=True)
    return products[:limit_int]
```

---

## Definition of Done

- [ ] `fetch_ai_products` is ≤ 20 non-blank lines
- [ ] `RateLimitParser`, `StrictAIFilter` exist and are importable
- [ ] The inline comment about "paid" is gone
- [ ] All NEW tests listed above pass (Red → Green)
- [ ] All EXISTING tests still pass (no regression)
- [ ] `make bundle` regenerates cleanly
- [ ] Function-size inventory in Section 2 shows `fetch_ai_products` ≤ 20

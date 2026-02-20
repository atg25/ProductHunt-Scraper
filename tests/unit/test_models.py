import pytest

from ph_ai_tracker.models import Product, TrackerResult
from ph_ai_tracker.exceptions import APIError, PhAITrackerError, RateLimitError, ScraperError


def test_product_creation_valid() -> None:
    p = Product(name="Foo", votes_count=12, description="desc")
    assert p.name == "Foo"
    assert p.votes_count == 12


def test_product_to_dict_roundtrip() -> None:
    p = Product(name="Foo", tagline="t", description="d", votes_count=3, url="u", topics=("AI",))
    assert Product.from_dict(p.to_dict()) == p


def test_product_from_dict_missing_name_raises() -> None:
    with pytest.raises(ValueError):
        Product.from_dict({"votes_count": 1})


def test_product_from_dict_votes_must_be_int() -> None:
    with pytest.raises(ValueError):
        Product.from_dict({"name": "Foo", "votes_count": "nope"})


def test_product_rejects_empty_name_direct_construction() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Product(name="")


def test_product_rejects_whitespace_name_direct_construction() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Product(name="   ")


def test_product_searchable_text_includes_name() -> None:
    p = Product(name="AlphaAI")
    assert "alphaai" in p.searchable_text


def test_product_searchable_text_includes_tagline() -> None:
    p = Product(name="X", tagline="AI copilot")
    assert "copilot" in p.searchable_text


def test_product_searchable_text_includes_description() -> None:
    p = Product(name="X", description="Powerful tool")
    assert "powerful" in p.searchable_text


def test_product_searchable_text_includes_topics() -> None:
    p = Product(name="X", topics=("Machine Learning",))
    assert "machine learning" in p.searchable_text


def test_product_searchable_text_is_lowercase() -> None:
    p = Product(name="AlphaAI", tagline="LLM App")
    assert p.searchable_text == p.searchable_text.lower()


def test_product_searchable_text_handles_none_fields() -> None:
    p = Product(name="X")
    assert isinstance(p.searchable_text, str)
    assert p.searchable_text


def test_tracker_result_success() -> None:
    p = Product(name="Foo")
    r = TrackerResult.success([p], source="api")
    assert r.error is None
    assert r.products == (p,)


def test_tracker_result_failure() -> None:
    r = TrackerResult.failure(source="api", error="boom")
    assert r.error == "boom"
    assert r.products == ()


def test_tracker_result_success_carries_search_term_and_limit() -> None:
    r = TrackerResult.success([], source="scraper", search_term="AI", limit=5)
    assert r.search_term == "AI"
    assert r.limit == 5


def test_tracker_result_failure_carries_search_term_and_limit() -> None:
    r = TrackerResult.failure(source="api", error="oops", search_term="ml", limit=10)
    assert r.search_term == "ml"
    assert r.limit == 10


def test_tracker_result_defaults_search_term_and_limit_to_empty() -> None:
    r = TrackerResult.success([], source="api")
    assert r.search_term == ""
    assert r.limit == 0


def test_exceptions_hierarchy() -> None:
    assert issubclass(APIError, PhAITrackerError)
    assert issubclass(ScraperError, PhAITrackerError)
    assert issubclass(RateLimitError, APIError)

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


def test_tracker_result_success() -> None:
    p = Product(name="Foo")
    r = TrackerResult.success([p], source="api")
    assert r.error is None
    assert r.products == (p,)


def test_tracker_result_failure() -> None:
    r = TrackerResult.failure(source="api", error="boom")
    assert r.error == "boom"
    assert r.products == ()


def test_exceptions_hierarchy() -> None:
    assert issubclass(APIError, PhAITrackerError)
    assert issubclass(ScraperError, PhAITrackerError)
    assert issubclass(RateLimitError, APIError)

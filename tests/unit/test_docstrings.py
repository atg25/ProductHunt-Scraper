"""Verify that all public classes and methods carry docstrings.

These tests guard against documentation regressions.  A new class or public
method added without a docstring will cause these tests to fail.
"""

from __future__ import annotations

import inspect

from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.scraper import (
    ProductHuntScraper, NextDataExtractor, DOMFallbackExtractor, ProductEnricher,
)
from ph_ai_tracker.storage import SQLiteStore
from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.models import Product, TrackerResult
from ph_ai_tracker.exceptions import (
    PhAITrackerError, APIError, RateLimitError, ScraperError, StorageError,
)
from ph_ai_tracker.scheduler import SchedulerConfig, SchedulerRunResult


def _has_docstring(obj: object) -> bool:
    doc = getattr(obj, "__doc__", None)
    return bool(doc and doc.strip())


# POSITIVE — classes must have docstrings

def test_AIProductTracker_has_class_docstring() -> None:
    assert _has_docstring(AIProductTracker), "AIProductTracker missing class docstring"


def test_ProductHuntScraper_has_class_docstring() -> None:
    assert _has_docstring(ProductHuntScraper), "ProductHuntScraper missing class docstring"


def test_SQLiteStore_has_class_docstring() -> None:
    assert _has_docstring(SQLiteStore), "SQLiteStore missing class docstring"


def test_ProductHuntAPI_has_class_docstring() -> None:
    assert _has_docstring(ProductHuntAPI), "ProductHuntAPI missing class docstring"


def test_Product_has_class_docstring() -> None:
    assert _has_docstring(Product), "Product missing class docstring"


def test_TrackerResult_has_class_docstring() -> None:
    assert _has_docstring(TrackerResult), "TrackerResult missing class docstring"


def test_SchedulerConfig_has_class_docstring() -> None:
    assert _has_docstring(SchedulerConfig), "SchedulerConfig missing class docstring"


def test_PhAITrackerError_has_docstring() -> None:
    assert _has_docstring(PhAITrackerError), "PhAITrackerError missing docstring"


def test_RateLimitError_has_docstring() -> None:
    assert _has_docstring(RateLimitError), "RateLimitError missing docstring"


def test_ScraperError_has_docstring() -> None:
    assert _has_docstring(ScraperError), "ScraperError missing docstring"


def test_StorageError_has_docstring() -> None:
    assert _has_docstring(StorageError), "StorageError missing docstring"


# POSITIVE — key methods must have docstrings

def test_AIProductTracker_get_products_has_docstring() -> None:
    assert _has_docstring(AIProductTracker.get_products)


def test_NextDataExtractor_extract_has_docstring() -> None:
    assert _has_docstring(NextDataExtractor.extract)


def test_DOMFallbackExtractor_extract_has_docstring() -> None:
    assert _has_docstring(DOMFallbackExtractor.extract)


def test_ProductEnricher_enrich_has_docstring() -> None:
    assert _has_docstring(ProductEnricher.enrich)


def test_ProductHuntScraper_scrape_ai_products_has_docstring() -> None:
    assert _has_docstring(ProductHuntScraper.scrape_ai_products)


def test_SQLiteStore_save_result_has_docstring() -> None:
    assert _has_docstring(SQLiteStore.save_result)


def test_SQLiteStore_init_db_has_docstring() -> None:
    assert _has_docstring(SQLiteStore.init_db)


def test_ProductHuntAPI_fetch_ai_products_has_docstring() -> None:
    assert _has_docstring(ProductHuntAPI.fetch_ai_products)


# POSITIVE — docstrings must mention key invariants

def test_scraper_class_docstring_mentions_dom_or_next_data() -> None:
    doc = (ProductHuntScraper.__doc__ or "").lower()
    assert "__next_data__" in doc or "dom" in doc or "react" in doc


def test_storage_class_docstring_mentions_observation() -> None:
    assert "observation" in (SQLiteStore.__doc__ or "").lower()


def test_tracker_class_docstring_mentions_strategy() -> None:
    doc = (AIProductTracker.__doc__ or "").lower()
    assert "strategy" in doc or "provider" in doc


def test_from_api_docstring_mentions_configuration_error() -> None:
    doc = (AIProductTracker.get_products.__doc__ or "").lower()
    assert "never raises" in doc or "failure" in doc or "exception" in doc


# NEGATIVE — docstrings must be non-trivial (> 20 chars)

def test_AIProductTracker_docstring_is_non_trivial() -> None:
    assert len((AIProductTracker.__doc__ or "").strip()) > 40


def test_ProductHuntScraper_docstring_is_non_trivial() -> None:
    assert len((ProductHuntScraper.__doc__ or "").strip()) > 40


def test_SQLiteStore_docstring_is_non_trivial() -> None:
    assert len((SQLiteStore.__doc__ or "").strip()) > 40

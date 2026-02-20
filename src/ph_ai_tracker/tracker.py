from __future__ import annotations

import logging

from .constants import DEFAULT_LIMIT, DEFAULT_SEARCH_TERM
from .exceptions import APIError, RateLimitError, ScraperError
from .models import TrackerResult
from .protocols import ProductProvider

_log = logging.getLogger(__name__)


class AIProductTracker:
    """Use-case facade: fetch AI products from a single injected provider.

    The caller selects a strategy by constructing the correct ``ProductProvider``
    (a plain adapter, ``FallbackProvider``, or ``_NoTokenProvider``) and passing
    it here.  ``AIProductTracker`` itself knows nothing about strategy names,
    tokens, or fallback sequences.

    Invariant: ``get_products`` never raises known domain exceptions
    (``RateLimitError``, ``ScraperError``, ``APIError``); these outcomes are
    captured in the returned ``TrackerResult``. ``TrackerResult.is_transient``
    marks retry-safe failures. Unexpected failures may still propagate.
    """

    def __init__(self, *, provider: ProductProvider) -> None:
        self._provider = provider

    def _failure_result(self, exc: Exception, *, search_term: str, limit: int) -> TrackerResult:
        if isinstance(exc, RateLimitError):
            error_text = f"Rate limited: {exc}"
            is_transient = True
        elif isinstance(exc, ScraperError):
            error_text = str(exc)
            is_transient = True
        else:
            error_text = str(exc)
            is_transient = False
        return TrackerResult.failure(
            source=self._provider.source_name,
            error=error_text,
            is_transient=is_transient,
            search_term=search_term,
            limit=limit,
        )

    def get_products(self, *, search_term: str = DEFAULT_SEARCH_TERM, limit: int = DEFAULT_LIMIT) -> TrackerResult:
        """Delegate to provider; map known domain exceptions to TrackerResult failures."""
        try:
            products = self._provider.fetch_products(search_term=search_term, limit=limit)
            return TrackerResult.success(
                products,
                source=self._provider.source_name,
                search_term=search_term,
                limit=limit,
            )
        except (RateLimitError, ScraperError, APIError) as exc:
            return self._failure_result(exc, search_term=search_term, limit=limit)
        finally:
            self._provider.close()

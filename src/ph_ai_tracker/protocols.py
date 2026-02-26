from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .exceptions import APIError

if TYPE_CHECKING:
    from .models import Product

_log = logging.getLogger(__name__)

# Emitted whenever the auto or api strategy is chosen but no API token is present.
# Both a logging.WARNING (operator logs) and RuntimeWarning (test suites / library code).
_MISSING_TOKEN_MSG = (
    "AIProductTracker: api_token is missing or blank. "
    "The 'auto' strategy will fall back to the scraper, which is slower and "
    "less reliable. Set the PRODUCTHUNT_TOKEN environment variable or pass "
    "api_token= explicitly to silence this warning."
)


@runtime_checkable
class ProductProvider(Protocol):
    """Abstraction for a data source that can fetch Product Hunt products."""

    source_name: str

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        ...

    def close(self) -> None:
        ...


@runtime_checkable
class TaggingService(Protocol):
    """Abstraction for product tag enrichment."""

    def categorize(self, product: Product) -> tuple[str, ...]:
        ...


class FallbackProvider:
    """Try *api_provider* first; fall back to *scraper_provider* on any exception.

    Emits the standard missing-token warning at construction time when
    *api_provider* is ``None``, so operators see the diagnostic before the
    first network call is made.
    """

    source_name = "auto"

    def __init__(
        self,
        *,
        api_provider: ProductProvider | None,
        scraper_provider: ProductProvider,
    ) -> None:
        self._api = api_provider
        self._scraper = scraper_provider
        if api_provider is None:
            _log.warning(_MISSING_TOKEN_MSG)
            warnings.warn(_MISSING_TOKEN_MSG, RuntimeWarning, stacklevel=3)

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        """Try API; on APIError fall through to scraper."""
        if self._api is not None:
            try:
                return self._api.fetch_products(search_term=search_term, limit=limit)
            except APIError:
                pass
        return self._scraper.fetch_products(search_term=search_term, limit=limit)

    def close(self) -> None:
        """Release both underlying providers."""
        if self._api is not None:
            self._api.close()
        self._scraper.close()


class _NoTokenProvider:
    """Sentinel returned when 'api' strategy is requested but no token is present.

    ``fetch_products`` always raises ``APIError``, which ``AIProductTracker``
    maps cleanly to a ``TrackerResult.failure``.
    """

    source_name = "api"

    def fetch_products(self, *, search_term: str, limit: int) -> list[Product]:
        """Immediately raise APIError to signal the missing token."""
        from .exceptions import APIError  # local import avoids circular dep
        raise APIError("Missing api_token")

    def close(self) -> None:
        pass

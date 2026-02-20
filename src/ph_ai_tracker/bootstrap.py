"""Provider factory for ph_ai_tracker.

This module is the composition root for constructing a ``ProductProvider``
from a strategy name and optional API token.
"""

from __future__ import annotations

import logging
import warnings

from .api_client import ProductHuntAPI
from .protocols import FallbackProvider, ProductProvider, _MISSING_TOKEN_MSG, _NoTokenProvider
from .scraper import ProductHuntScraper

_log = logging.getLogger(__name__)


def _warn_missing_token() -> None:
    """Emit log WARNING and RuntimeWarning for a missing API token."""
    _log.warning(_MISSING_TOKEN_MSG)
    warnings.warn(_MISSING_TOKEN_MSG, RuntimeWarning, stacklevel=3)


def build_provider(*, strategy: str, api_token: str | None) -> ProductProvider:
    """Construct the correct ``ProductProvider`` for *strategy* and *api_token*."""
    has_token = bool(api_token and api_token.strip())
    api = ProductHuntAPI(api_token) if has_token else None
    if strategy == "scraper":
        return ProductHuntScraper()
    if strategy == "api":
        if api is None:
            _warn_missing_token()
            return _NoTokenProvider()
        return api
    if strategy == "auto":
        return FallbackProvider(api_provider=api, scraper_provider=ProductHuntScraper())
    raise ValueError(f"Unknown strategy: {strategy!r}")

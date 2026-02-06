from __future__ import annotations

from dataclasses import dataclass

from .api_client import APIConfig, ProductHuntAPI
from .exceptions import APIError, RateLimitError, ScraperError
from .models import TrackerResult
from .scraper import ProductHuntScraper, ScraperConfig


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    strategy: str = "auto"  # api | scraper | auto


class AIProductTracker:
    def __init__(
        self,
        *,
        api_token: str | None = None,
        strategy: str = "auto",
        api_config: APIConfig | None = None,
        scraper_config: ScraperConfig | None = None,
    ) -> None:
        self._api_token = api_token
        self._config = TrackerConfig(strategy=strategy)
        self._api_config = api_config
        self._scraper_config = scraper_config

    def get_products(self, *, search_term: str = "AI", limit: int = 20) -> TrackerResult:
        strategy = (self._config.strategy or "auto").lower()

        if strategy not in {"api", "scraper", "auto"}:
            return TrackerResult.failure(source=strategy, error=f"Unknown strategy: {strategy}")

        if strategy == "api":
            return self._from_api(search_term=search_term, limit=limit)

        if strategy == "scraper":
            return self._from_scraper(search_term=search_term, limit=limit)

        # auto
        api_result = self._from_api(search_term=search_term, limit=limit)
        if api_result.error is None:
            return api_result

        scraper_result = self._from_scraper(search_term=search_term, limit=limit)
        if scraper_result.error is None:
            return scraper_result

        return TrackerResult.failure(
            source="auto",
            error=f"API failed: {api_result.error}; Scraper failed: {scraper_result.error}",
        )

    def _from_api(self, *, search_term: str, limit: int) -> TrackerResult:
        if not self._api_token:
            return TrackerResult.failure(source="api", error="Missing api_token")

        api = ProductHuntAPI(self._api_token, config=self._api_config)
        try:
            products = api.fetch_ai_products(search_term=search_term, limit=limit)
            return TrackerResult.success(products, source="api")
        except RateLimitError as exc:
            return TrackerResult.failure(source="api", error=f"Rate limited: {exc}")
        except APIError as exc:
            return TrackerResult.failure(source="api", error=str(exc))
        finally:
            api.close()

    def _from_scraper(self, *, search_term: str, limit: int) -> TrackerResult:
        scraper = ProductHuntScraper(config=self._scraper_config)
        try:
            products = scraper.scrape_ai_products(search_term=search_term, limit=limit)
            return TrackerResult.success(products, source="scraper")
        except ScraperError as exc:
            return TrackerResult.failure(source="scraper", error=str(exc))
        finally:
            scraper.close()

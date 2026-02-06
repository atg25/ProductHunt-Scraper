from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.scraper import ProductHuntScraper


def test_tracker_unknown_strategy_returns_failure() -> None:
    t = AIProductTracker(strategy="nope")
    r = t.get_products()
    assert r.error is not None


def test_tracker_missing_token_api_failure() -> None:
    t = AIProductTracker(strategy="api")
    r = t.get_products()
    assert r.error == "Missing api_token"


def test_tracker_scraper_success(scraper_html: str, monkeypatch) -> None:
    # Ensure no network by forcing the scraper to return deterministic products.
    def fake_scrape(self, *, search_term: str = "AI", limit: int = 20):
        from ph_ai_tracker.models import Product

        return [Product(name="AlphaAI", votes_count=123)]

    monkeypatch.setattr(ProductHuntScraper, "scrape_ai_products", fake_scrape)

    t = AIProductTracker(strategy="scraper")
    r = t.get_products(limit=1)
    assert r.error is None
    assert r.source == "scraper"
    assert len(r.products) == 1


def test_tracker_auto_falls_back_when_no_token(monkeypatch) -> None:
    from ph_ai_tracker.exceptions import ScraperError

    def fake_scrape(self, *, search_term: str = "AI", limit: int = 20):
        raise ScraperError("offline")

    monkeypatch.setattr(ProductHuntScraper, "scrape_ai_products", fake_scrape)

    t = AIProductTracker(strategy="auto")
    r = t.get_products(limit=1)
    assert r.source == "auto"
    assert r.error is not None

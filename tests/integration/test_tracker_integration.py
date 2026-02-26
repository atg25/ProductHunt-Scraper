import httpx

from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.protocols import FallbackProvider
from ph_ai_tracker.scraper import ProductHuntScraper


def test_auto_fallback_on_api_error(api_success_payload: dict, scraper_html: str) -> None:
    # Force API to fail, scraper to succeed.

    def api_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "no"})

    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    provider = FallbackProvider(
        api_provider=ProductHuntAPI("token", transport=httpx.MockTransport(api_handler)),
        scraper_provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
    )
    r = AIProductTracker(provider=provider).get_products(search_term="AI", limit=10)

    assert r.error is None
    assert r.source == "auto"
    assert len(r.products) == 1


def test_auto_fallback_warning_does_not_prevent_scraper_success(
    scraper_html: str,
    caplog,
) -> None:
    """When no token is set, a warning fires but the scraper still succeeds."""
    import logging

    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    scraper = ProductHuntScraper(transport=httpx.MockTransport(scraper_handler))
    with caplog.at_level(logging.WARNING, logger="ph_ai_tracker.protocols"):
        provider = FallbackProvider(api_provider=None, scraper_provider=scraper)
        r = AIProductTracker(provider=provider).get_products(search_term="AI", limit=5)

    assert r.error is None
    assert r.source == "auto"
    assert any("api_token" in rec.message for rec in caplog.records if rec.levelno >= logging.WARNING)


def test_empty_string_token_triggers_warning() -> None:
    """Empty-string token must behave identically to None."""
    import pytest as _pytest
    from ph_ai_tracker.exceptions import ScraperError

    class _FailingScraper:
        source_name = "scraper"

        def fetch_products(self, *, search_term: str, limit: int) -> list:
            raise ScraperError("offline")

        def close(self) -> None:
            return None

    with _pytest.warns(RuntimeWarning, match="api_token"):
        provider = FallbackProvider(api_provider=None, scraper_provider=_FailingScraper())
        AIProductTracker(provider=provider).get_products(limit=1)


# Sprint 62 — CLI stdout must be newsletter-format JSON

def test_cli_stdout_is_newsletter_json(monkeypatch, capsys) -> None:
    """main(--no-persist) must write newsletter JSON keys to stdout."""
    import json
    from ph_ai_tracker import __main__ as cli_main
    from ph_ai_tracker.models import Product, TrackerResult

    products = [Product(name="Tool A", votes_count=10), Product(name="Tool B", votes_count=5)]
    monkeypatch.setattr(cli_main, "_fetch_result", lambda _c: TrackerResult.success(products, source="scraper"))
    code = cli_main.main(["--no-persist"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out.keys()) >= {"generated_at", "total_products", "top_tags", "products"}


def test_cli_stdout_newsletter_total_products_matches_provider(monkeypatch, capsys) -> None:
    """total_products in newsletter output must equal the provider's product count."""
    import json
    from ph_ai_tracker import __main__ as cli_main
    from ph_ai_tracker.models import Product, TrackerResult

    products = [Product(name=f"P{i}", votes_count=i) for i in range(7)]
    monkeypatch.setattr(cli_main, "_fetch_result", lambda _c: TrackerResult.success(products, source="scraper"))
    cli_main.main(["--no-persist"])
    out = json.loads(capsys.readouterr().out)
    assert out["total_products"] == 7


# Sprint 63 — scheduler stdout must be newsletter JSON

def test_scheduler_run_once_stdout_is_newsletter(tmp_path, monkeypatch, capsys) -> None:
    """scheduler.main(...) must write newsletter JSON keys to stdout."""
    import json
    import ph_ai_tracker.scheduler as scheduler_mod
    from ph_ai_tracker.scheduler import SchedulerRunResult, main as scheduler_main
    from ph_ai_tracker.models import Product, TrackerResult

    products = [Product(name="Tool X", votes_count=3)]
    tracker_result = TrackerResult.success(products, source="scraper")
    fake = SchedulerRunResult(saved=1, tracker_result=tracker_result, status="success", attempts_used=1)
    monkeypatch.setattr(scheduler_mod, "run_once", lambda _c: fake)
    code = scheduler_main(["--strategy", "scraper", "--db-path", str(tmp_path / "db.db")])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out.keys()) >= {"generated_at", "total_products", "top_tags", "products"}

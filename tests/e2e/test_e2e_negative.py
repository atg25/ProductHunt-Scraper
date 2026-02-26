import httpx
import pytest

from ph_ai_tracker.formatters import NewsletterFormatter
from ph_ai_tracker.models import Product
from ph_ai_tracker.bootstrap import build_tagging_service
from ph_ai_tracker.models import TrackerResult
from ph_ai_tracker.tagging import UniversalLLMTaggingService
from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.api_client import ProductHuntAPI
from ph_ai_tracker.protocols import FallbackProvider
from ph_ai_tracker.scraper import ProductHuntScraper


def test_e2e_both_sources_fail() -> None:
    def api_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"errors": []})

    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oops")

    provider = FallbackProvider(
        api_provider=ProductHuntAPI("token", transport=httpx.MockTransport(api_handler)),
        scraper_provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
    )
    r = AIProductTracker(provider=provider).get_products(limit=5)
    assert r.error is not None
    assert r.source == "auto"


def test_e2e_scraper_empty_page_returns_empty_result() -> None:
    """An empty 200 page must yield r.error is None + empty products (no exception)."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body></body></html>")

    r = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(handler)),
    ).get_products(limit=5)
    assert r.error is None
    assert r.products == ()


def test_e2e_scraper_timeout_produces_failure_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    r = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(handler)),
    ).get_products(limit=5)
    assert r.error is not None
    assert "timed out" in r.error.lower()


def test_e2e_scraper_500_produces_failure_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    r = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(handler)),
    ).get_products(limit=5)
    assert r.error is not None
    assert "500" in r.error


def test_e2e_auto_no_token_warning_logged(
    caplog,
) -> None:
    import logging

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body></body></html>")

    scraper = ProductHuntScraper(transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.WARNING, logger="ph_ai_tracker.protocols"):
        AIProductTracker(
            provider=FallbackProvider(api_provider=None, scraper_provider=scraper),
        ).get_products(limit=1)

    assert any("api_token" in r.message for r in caplog.records if r.levelno >= logging.WARNING)


def test_e2e_missing_token_and_network_failure_produce_distinct_messages(
) -> None:
    """Missing token warning and network failure are separate, diagnosable messages."""
    import pytest as _pytest

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    scraper = ProductHuntScraper(transport=httpx.MockTransport(handler))
    with _pytest.warns(RuntimeWarning) as record:
        provider = FallbackProvider(api_provider=None, scraper_provider=scraper)
        r = AIProductTracker(provider=provider).get_products(limit=1)

    # One RuntimeWarning about missing token
    token_warns = [w for w in record if "api_token" in str(w.message)]
    assert len(token_warns) >= 1

    # The result error must describe the network failure, not the token issue
    assert r.error is not None
    assert "timed out" in r.error.lower() or "scraper" in r.error.lower()


def test_e2e_llm_down_returns_empty_tags_without_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="Alpha")) == ()


def test_e2e_llm_malformed_json_returns_empty_tags() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "oops"}}]})

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="Alpha")) == ()


def test_e2e_missing_api_key_uses_noop_tagging(scraper_html: str) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    tracker = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
        tagging_service=build_tagging_service({}),
    )
    result = tracker.get_products(limit=3)
    assert result.error is None
    assert all(product.tags == () for product in result.products)


def test_e2e_llm_returns_wrong_schema_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"result":"ok"}'}}]})

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="Alpha")) == ()


def test_e2e_llm_filters_oversized_tags() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = '{"tags":["ok","this-is-way-too-long-indeed-over-twenty-chars"]}'
        return httpx.Response(200, json={"choices": [{"message": {"content": payload}}]})

    service = UniversalLLMTaggingService(
        api_key="k",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    assert service.categorize(Product(name="Alpha")) == ("ok",)


def test_e2e_newsletter_from_failed_tracker_run_handles_empty_gracefully() -> None:
    failed = TrackerResult.failure(source="scraper", error="boom")
    newsletter = NewsletterFormatter().format(list(failed.products), generated_at=failed.fetched_at)
    assert newsletter["total_products"] == 0
    assert newsletter["products"] == []


# Sprint 61 — broken tagger must NOT be silently swallowed by the Use Case

def test_e2e_broken_tagger_raises_at_runtime(scraper_html: str) -> None:
    """A tagger that raises must propagate through get_products \u2014 not be muzzled."""
    class _BrokenTagger:
        def categorize(self, product: Product) -> tuple[str, ...]:
            raise RuntimeError("intentional failure in tagger")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    provider = ProductHuntScraper(transport=httpx.MockTransport(handler))
    tracker = AIProductTracker(provider=provider, tagging_service=_BrokenTagger())
    with pytest.raises(RuntimeError, match="intentional failure in tagger"):
        tracker.get_products(limit=1)


# Sprint 62 — CLI stdout must be newsletter JSON even on storage failure

def test_e2e_cli_storage_error_still_outputs_newsletter(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """StorageError path must still write newsletter JSON to stdout (exit 3)."""
    import json
    from ph_ai_tracker import __main__ as cli_main

    products = [Product(name="Alpha", votes_count=5)]
    monkeypatch.setattr(cli_main, "_fetch_result", lambda _c: TrackerResult.success(products, source="scraper"))
    monkeypatch.setattr(cli_main, "_try_persist", lambda *_a, **_kw: 3)
    code = cli_main.main([])
    assert code == 3
    out = json.loads(capsys.readouterr().out)
    assert "generated_at" in out
    assert out["total_products"] == 1


def test_e2e_cli_no_persist_outputs_newsletter(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """--no-persist must write newsletter JSON (not raw tracker JSON) to stdout."""
    import json
    from ph_ai_tracker import __main__ as cli_main

    products = [Product(name="Beta", votes_count=20)]
    monkeypatch.setattr(cli_main, "_fetch_result", lambda _c: TrackerResult.success(products, source="scraper"))
    code = cli_main.main(["--no-persist"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out.keys()) >= {"generated_at", "total_products", "top_tags", "products"}


# Sprint 63 — scheduler e2e negative coverage

def test_e2e_scheduler_storage_error_returns_exit_3(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """StorageError in run_once must yield exit code 3 and an error message on stderr."""
    import ph_ai_tracker.scheduler as scheduler_mod
    from ph_ai_tracker.scheduler import main as scheduler_main
    from ph_ai_tracker.exceptions import StorageError

    def _fail(_config):
        raise StorageError("disk full")

    monkeypatch.setattr(scheduler_mod, "run_once", _fail)
    code = scheduler_main(["--strategy", "scraper", "--db-path", "/tmp/fake.db"])
    assert code == 3
    assert "disk full" in capsys.readouterr().err


def test_e2e_scheduler_invalid_strategy_returns_exit_2(
    capsys: pytest.CaptureFixture,
) -> None:
    """An unrecognised --strategy value must yield exit code 2 with no stdout."""
    from ph_ai_tracker.scheduler import main as scheduler_main

    with pytest.raises(SystemExit) as exc_info:
        scheduler_main(["--strategy", "unknown_strategy_xyz"])
    assert exc_info.value.code == 2
    assert capsys.readouterr().out == ""

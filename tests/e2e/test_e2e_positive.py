import httpx
import pytest

from ph_ai_tracker import __main__ as cli_main
from ph_ai_tracker.formatters import NewsletterFormatter
from ph_ai_tracker.models import Product, TrackerResult
from ph_ai_tracker.tagging import NoOpTaggingService
from ph_ai_tracker.tagging import UniversalLLMTaggingService
from ph_ai_tracker.tracker import AIProductTracker
from ph_ai_tracker.scraper import ProductHuntScraper


def test_e2e_scraper_happy_path(scraper_html: str) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    t = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
    )
    r = t.get_products(search_term="AI", limit=10)
    assert r.error is None
    assert r.products


def test_result_pretty_json(scraper_html: str) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    r = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
    ).get_products(limit=1)
    s = r.to_pretty_json()
    assert "products" in s
    assert "source" in s


def test_e2e_noop_tagging_keeps_pipeline_successful(scraper_html: str) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    result = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
        tagging_service=NoOpTaggingService(),
    ).get_products(search_term="AI", limit=3)
    assert result.error is None
    assert result.products
    assert all(product.tags == () for product in result.products)


def test_e2e_newsletter_formatter_output(scraper_html: str) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    result = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
    ).get_products(limit=5)
    newsletter = NewsletterFormatter().format(list(result.products), generated_at=result.fetched_at)
    assert newsletter["total_products"] == len(result.products)
    assert "generated_at" in newsletter
    assert isinstance(newsletter["products"], list)


def test_e2e_scraper_with_llm_tagging_returns_tagged_products(scraper_html: str) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"tags":["productivity","ai"]}'}}]})

    result = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
        tagging_service=UniversalLLMTaggingService(
            api_key="sk-test",
            base_url="https://example.test/v1",
            transport=httpx.MockTransport(llm_handler),
        ),
    ).get_products(search_term="AI", limit=5)
    assert result.error is None
    assert result.products
    assert all(product.tags for product in result.products)


def test_e2e_newsletter_from_tagged_tracker_run_sorted(scraper_html: str) -> None:
    def scraper_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=scraper_html)

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"tags":["ai"]}'}}]})

    result = AIProductTracker(
        provider=ProductHuntScraper(transport=httpx.MockTransport(scraper_handler)),
        tagging_service=UniversalLLMTaggingService(
            api_key="sk-test",
            base_url="https://example.test/v1",
            transport=httpx.MockTransport(llm_handler),
        ),
    ).get_products(limit=5)
    newsletter = NewsletterFormatter().format(list(result.products), generated_at=result.fetched_at)
    assert len(newsletter["products"]) == len(result.products)
    assert newsletter["products"][0]["votes"] >= newsletter["products"][-1]["votes"]
    assert isinstance(newsletter["top_tags"], list)


def test_e2e_cli_no_persist_skips_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_main,
        "_fetch_result",
        lambda _common: TrackerResult.success([Product(name="X")], source="scraper"),
    )
    called: list[bool] = []
    monkeypatch.setattr(cli_main, "_try_persist", lambda *_args, **_kwargs: called.append(True) or None)
    code = cli_main.main(["--no-persist"])
    assert code == 0
    assert called == []


# Sprint 62 — CLI stdout must be newsletter-format JSON

def test_e2e_cli_stdout_is_newsletter_format(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """main() must write newsletter JSON (not raw tracker JSON) to stdout."""
    import json
    products = [Product(name="Alpha", votes_count=5), Product(name="Beta", votes_count=10)]
    monkeypatch.setattr(cli_main, "_fetch_result", lambda _c: TrackerResult.success(products, source="scraper"))
    code = cli_main.main(["--no-persist"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert "generated_at" in out
    assert "total_products" in out
    assert "top_tags" in out
    assert "products" in out


def test_e2e_cli_newsletter_products_sorted_by_votes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Products in newsletter stdout must be sorted votes-descending."""
    import json
    products = [
        Product(name="Low", votes_count=1),
        Product(name="High", votes_count=99),
        Product(name="Mid", votes_count=50),
    ]
    monkeypatch.setattr(cli_main, "_fetch_result", lambda _c: TrackerResult.success(products, source="scraper"))
    cli_main.main(["--no-persist"])
    out = json.loads(capsys.readouterr().out)
    votes = [p["votes"] for p in out["products"]]
    assert votes == sorted(votes, reverse=True)


# Sprint 63 — scheduler stdout must be newsletter-format JSON

def test_e2e_scheduler_stdout_is_newsletter_format(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """scheduler.main() must write newsletter JSON (not raw tracker JSON) to stdout."""
    import json
    import ph_ai_tracker.scheduler as scheduler_mod
    from ph_ai_tracker.scheduler import SchedulerRunResult, main as scheduler_main

    products = [Product(name="Alpha", votes_count=5), Product(name="Beta", votes_count=10)]
    tracker_result = TrackerResult.success(products, source="scraper")
    fake = SchedulerRunResult(saved=1, tracker_result=tracker_result, status="success", attempts_used=1)
    monkeypatch.setattr(scheduler_mod, "run_once", lambda _c: fake)
    code = scheduler_main(["--strategy", "scraper", "--db-path", str(tmp_path / "db.db")])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out.keys()) >= {"generated_at", "total_products", "top_tags", "products"}


def test_e2e_scheduler_newsletter_products_sorted_by_votes(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """Scheduler newsletter products must be sorted votes-descending."""
    import json
    import ph_ai_tracker.scheduler as scheduler_mod
    from ph_ai_tracker.scheduler import SchedulerRunResult, main as scheduler_main

    products = [Product(name="Low", votes_count=1), Product(name="High", votes_count=99), Product(name="Mid", votes_count=50)]
    tracker_result = TrackerResult.success(products, source="scraper")
    fake = SchedulerRunResult(saved=1, tracker_result=tracker_result, status="success", attempts_used=1)
    monkeypatch.setattr(scheduler_mod, "run_once", lambda _c: fake)
    scheduler_main(["--strategy", "scraper", "--db-path", str(tmp_path / "db.db")])
    out = json.loads(capsys.readouterr().out)
    votes = [p["votes"] for p in out["products"]]
    assert votes == sorted(votes, reverse=True)

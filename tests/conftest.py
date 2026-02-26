import json
import sys
from pathlib import Path

import pytest


# Allow running tests without an installed wheel by adding src/ to sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def api_success_payload(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "api_response_success.json").read_text(encoding="utf-8"))


@pytest.fixture
def scraper_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "scraper_page.html").read_text(encoding="utf-8")


@pytest.fixture
def scraper_dom_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "scraper_page_dom.html").read_text(encoding="utf-8")


@pytest.fixture
def scraper_next_data_malformed_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "scraper_next_data_malformed.html").read_text(encoding="utf-8")


@pytest.fixture
def scraper_next_data_no_posts_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "scraper_next_data_no_posts.html").read_text(encoding="utf-8")


@pytest.fixture
def scraper_dom_nav_only_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "scraper_dom_nav_only.html").read_text(encoding="utf-8")

from pathlib import Path

from ph_ai_tracker import AIProductTracker, Product, TrackerResult


def test_public_api_exports() -> None:
    assert AIProductTracker is not None
    assert Product is not None
    assert TrackerResult is not None


def test_py_typed_marker_exists() -> None:
    # PEP 561 marker
    marker = Path(__file__).parents[2] / "src" / "ph_ai_tracker" / "py.typed"
    assert marker.exists()

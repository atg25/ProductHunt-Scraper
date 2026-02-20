"""TDD guard: every production function must be ≤ 20 source lines.

These tests use the same AST measurement as build_bundle.py:
  size = end_lineno - def_lineno + 1

A failing test here means a function needs extraction.  After refactoring,
all tests here must be green before ``make bundle`` is re-run for Uncle Bob.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "ph_ai_tracker"
LIMIT = 20


class _Func(NamedTuple):
    module: str
    cls: str
    name: str
    size: int


def _collect(module_stem: str) -> list[_Func]:
    path = SRC / f"{module_stem}.py"
    tree = ast.parse(path.read_text())

    class V(ast.NodeVisitor):
        def __init__(self) -> None:
            self._cls: str = ""
            self.funcs: list[_Func] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            old, self._cls = self._cls, node.name
            self.generic_visit(node)
            self._cls = old

        def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            size = getattr(node, "end_lineno", node.lineno) - node.lineno + 1
            self.funcs.append(_Func(module_stem, self._cls, node.name, size))

        visit_FunctionDef = _visit_func
        visit_AsyncFunctionDef = _visit_func

    v = V()
    v.visit(tree)
    return v.funcs


def _assert_under_limit(module: str, cls: str, fn: str) -> None:
    funcs = {(f.cls, f.name): f for f in _collect(module)}
    key = (cls, fn)
    assert key in funcs, f"{module}.{cls}.{fn} not found"
    f = funcs[key]
    assert f.size <= LIMIT, (
        f"{module}.{cls or '<module>'}.{fn} is {f.size} lines — must be ≤ {LIMIT}"
    )


# models.py

def test_models_product_from_dict_size() -> None:
    _assert_under_limit("models", "Product", "from_dict")


# api_client.py

def test_api_client_rate_limit_parser_parse_size() -> None:
    _assert_under_limit("api_client", "RateLimitParser", "parse")


def test_api_client_build_query_size() -> None:
    _assert_under_limit("api_client", "ProductHuntAPI", "_build_query")


def test_api_client_extract_edges_size() -> None:
    _assert_under_limit("api_client", "ProductHuntAPI", "_extract_edges")


def test_api_client_fetch_ai_products_size() -> None:
    _assert_under_limit("api_client", "ProductHuntAPI", "fetch_ai_products")


def test_api_client_execute_request_size() -> None:
    _assert_under_limit("api_client", "ProductHuntAPI", "_execute_request")


def test_api_client_build_products_from_edges_size() -> None:
    _assert_under_limit("api_client", "ProductHuntAPI", "_build_products_from_edges")


# scraper.py

def test_scraper_next_data_extractor_extract_size() -> None:
    _assert_under_limit("scraper", "NextDataExtractor", "extract")


def test_scraper_next_data_extractor_product_from_node_size() -> None:
    _assert_under_limit("scraper", "NextDataExtractor", "_product_from_node")


def test_scraper_product_enricher_enrich_size() -> None:
    _assert_under_limit("scraper", "ProductEnricher", "enrich")


# storage.py

def test_storage_save_result_size() -> None:
    _assert_under_limit("storage", "SQLiteStore", "save_result")


def test_storage_upsert_product_size() -> None:
    _assert_under_limit("storage", "SQLiteStore", "_upsert_product")


# tracker.py

def test_tracker_get_products_size() -> None:
    _assert_under_limit("tracker", "AIProductTracker", "get_products")


# scheduler.py

def test_scheduler_fetch_with_retries_size() -> None:
    _assert_under_limit("scheduler", "", "_fetch_with_retries")


def test_scheduler_config_from_env_size() -> None:
    _assert_under_limit("scheduler", "", "scheduler_config_from_env")


def test_scheduler_run_once_size() -> None:
    _assert_under_limit("scheduler", "", "run_once")


def test_scheduler_main_size() -> None:
    _assert_under_limit("scheduler", "", "main")


# __main__.py

def test_main_main_size() -> None:
    _assert_under_limit("__main__", "", "main")

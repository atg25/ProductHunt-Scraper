#!/usr/bin/env python3
"""build_bundle.py — Generate a structured code-review bundle for ph_ai_tracker.

Produces a single text file with:
  0. Cover page & table of contents
  1. Architecture overview (intra-package dependency graph)
  2. Function-size inventory (AST-based, flags functions > 20 lines)
  3. Production code  — logically ordered
  4. Test suite       — unit / integration / e2e
  5. Configuration & build artefacts

Usage:
    python scripts/build_bundle.py [--out codebase_review_bundle.txt]
"""

from __future__ import annotations

import ast
import datetime
import importlib.metadata
import re
import sys
import textwrap
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
SRC  = ROOT / "src" / "ph_ai_tracker"

# ---------------------------------------------------------------------------
# Files to include, ordered within each section
# ---------------------------------------------------------------------------

SECTION_3_PRODUCTION: list[Path] = [
    SRC / "exceptions.py",
    SRC / "models.py",
    SRC / "constants.py",
    SRC / "protocols.py",
    SRC / "api_client.py",
    SRC / "scraper.py",
    SRC / "storage.py",
    SRC / "tracker.py",
    SRC / "cli.py",
    SRC / "bootstrap.py",
    SRC / "scheduler.py",
    SRC / "__init__.py",
    SRC / "__main__.py",
]

SECTION_4_TESTS: list[Path] = [
    ROOT / "tests" / "conftest.py",
    # unit
    ROOT / "tests" / "unit" / "test_models.py",
    ROOT / "tests" / "unit" / "test_api_client.py",
    ROOT / "tests" / "unit" / "test_scraper.py",
    ROOT / "tests" / "unit" / "test_storage.py",
    ROOT / "tests" / "unit" / "test_tracker.py",
    ROOT / "tests" / "unit" / "test_scheduler.py",
    ROOT / "tests" / "unit" / "test_bootstrap.py",
    ROOT / "tests" / "unit" / "test_protocols.py",
    ROOT / "tests" / "unit" / "test_docstrings.py",
    ROOT / "tests" / "unit" / "test_bundle_script.py",
    # integration
    ROOT / "tests" / "integration" / "test_api_integration.py",
    ROOT / "tests" / "integration" / "test_scraper_integration.py",
    ROOT / "tests" / "integration" / "test_storage_integrity.py",
    ROOT / "tests" / "integration" / "test_tracker_integration.py",
    ROOT / "tests" / "integration" / "test_bundle_integrity.py",
    ROOT / "tests" / "integration" / "test_narrative_docs.py",
    # e2e
    ROOT / "tests" / "e2e" / "test_e2e_positive.py",
    ROOT / "tests" / "e2e" / "test_e2e_negative.py",
    ROOT / "tests" / "e2e" / "test_packaging.py",
    ROOT / "tests" / "e2e" / "test_bundle_e2e.py",
]

SECTION_5_CONFIG: list[Path] = [
    ROOT / "pyproject.toml",
    ROOT / "Makefile",
    ROOT / "README.md",
    ROOT / "RUNBOOK.md",
]

# ---------------------------------------------------------------------------
# Internal module names for dependency analysis
# ---------------------------------------------------------------------------

INTERNAL_MODULES = [p.stem for p in SECTION_3_PRODUCTION]


# ===========================================================================
# Helpers
# ===========================================================================

def _box(title: str, width: int = 78) -> str:
    """Return a double-line ASCII box containing *title*, centred."""
    inner = width - 2
    bar   = "═" * inner
    pad   = title.center(inner)
    return f"╔{bar}╗\n║{pad}║\n╚{bar}╝"


def _section_header(num: int | str, title: str, width: int = 78) -> str:
    bar = "─" * width
    label = f"  SECTION {num}: {title}  "
    return f"\n\n{'━' * width}\n{label}\n{'━' * width}\n"


def _subsection_header(title: str, width: int = 78) -> str:
    return f"\n{'─' * width}\n  {title}\n{'─' * width}\n"


def _file_header(rel: str, width: int = 78) -> str:
    label = f"  FILE: {rel}  "
    bar   = "─" * width
    return f"\n\n{'─' * width}\n{label}\n{bar}\n"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return f"[ERROR: could not read {path}]\n"


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ===========================================================================
# Section 0 — Cover page & TOC
# ===========================================================================

def _cover_and_toc(pkg_version: str, file_counts: dict[str, int]) -> str:
    date = datetime.date.today().isoformat()
    py   = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    toc = textwrap.dedent(f"""\
        TABLE OF CONTENTS
        ─────────────────────────────────────────────────────────────────────────────
        Section 0 · Cover page & table of contents       (this page)
        Section 1 · Architecture overview & dependency graph
        Section 2 · Function-size inventory  (Uncle Bob's first stop)
        Section 3 · Production code          ({file_counts['prod']} files, ordered by dependency)
        Section 4 · Test suite               ({file_counts['tests']} files — unit / integration / e2e)
        Section 5 · Configuration & build    ({file_counts['config']} files)
        ─────────────────────────────────────────────────────────────────────────────

        Clean Code review checklist (Robert C. Martin):
          □  Single Responsibility Principle — each class/function does ONE thing
          □  Open/Closed Principle          — open for extension, closed for modification
          □  Dependency Inversion           — high-level modules do NOT import low-level ones
          □  Small functions                — every function fits on a screen (≤20 lines)
          □  Descriptive names              — no abbreviations, no comments needed
          □  No dead code                   — no commented-out lines, no unused imports
          □  Tests as specification         — test names describe intent, not mechanism
          □  Zero duplication               — DRY applied ruthlessly
    """)

    meta = textwrap.dedent(f"""\
        Package   : ph_ai_tracker  v{pkg_version}
        Generated : {date}
        Python    : {py}
        Reviewer  : Robert C. Martin (Uncle Bob) — Clean Code / Clean Architecture
    """)

    return "\n".join([
        _box("CODE REVIEW BUNDLE"),
        _box("ph_ai_tracker"),
        "",
        meta,
        "",
        toc,
    ])


# ===========================================================================
# Section 1 — Architecture & dependency graph
# ===========================================================================

def _parse_internal_imports(path: Path) -> list[str]:
    """Return the internal module names imported by *path*."""
    try:
        tree = ast.parse(_read(path), filename=str(path))
    except SyntaxError:
        return []
    deps: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # from .models import … OR from ph_ai_tracker.models import …
            mod = node.module or ""
            for part in mod.split("."):
                if part in INTERNAL_MODULES:
                    deps.append(part)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for part in alias.name.split("."):
                    if part in INTERNAL_MODULES:
                        deps.append(part)
    return sorted(set(deps))


def _dependency_graph() -> str:
    lines: list[str] = []
    lines.append(_subsection_header("Intra-package import graph"))
    lines.append("  Format:  module  ──▶  [dependencies it imports]\n")

    max_name = max(len(p.stem) for p in SECTION_3_PRODUCTION)
    arrow    = "──▶"

    for path in SECTION_3_PRODUCTION:
        deps = _parse_internal_imports(path)
        name = path.stem.ljust(max_name)
        dep_str = "  ".join(deps) if deps else "(no internal deps)"
        lines.append(f"  {name}  {arrow}  {dep_str}")

    lines.append("")
    lines.append(_subsection_header("Architectural layers (Clean Architecture)"))
    layers = textwrap.dedent("""\
        ┌─────────────────────────────────────────────────────────────┐
        │  FRAMEWORK / CLI LAYER                                      │
        │    scheduler.py  __main__.py                                │
        ├─────────────────────────────────────────────────────────────┤
        │  USE-CASE / APPLICATION LAYER                               │
        │    tracker.py                                               │
        ├─────────────────────────────────────────────────────────────┤
        │  INTERFACE ADAPTERS                                         │
        │    api_client.py   scraper.py   storage.py                  │
        ├─────────────────────────────────────────────────────────────┤
        │  ENTITIES / DOMAIN                                          │
        │    models.py   exceptions.py                                │
        └─────────────────────────────────────────────────────────────┘

        Dependency Rule: arrows must ONLY point inward (toward entities).
        Any outward import is a Clean Architecture violation.
    """)
    lines.append(layers)
    return "\n".join(lines)


# ===========================================================================
# Section 2 — Function-size inventory
# ===========================================================================

class FuncInfo(NamedTuple):
    module: str
    cls: str          # empty string if top-level
    name: str
    first_line: int
    size: int         # lines
    flag: bool        # True if > 20 lines


def _collect_functions(path: Path) -> list[FuncInfo]:
    src = _read(path)
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return []

    module_name = path.stem
    results: list[FuncInfo] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._class: str = ""

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            old = self._class
            self._class = node.name
            self.generic_visit(node)
            self._class = old

        def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            start = node.lineno
            end   = getattr(node, "end_lineno", node.lineno)
            size  = end - start + 1
            results.append(FuncInfo(
                module=module_name,
                cls=self._class,
                name=node.name,
                first_line=start,
                size=size,
                flag=size > 20,
            ))
            # do NOT recurse — nested functions counted separately
            old = self._class
            self._class = self._class  # keep class context for nested defs
            self.generic_visit(node)
            self._class = old

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._handle_func(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._handle_func(node)

    Visitor().visit(tree)
    return results


def _function_size_table(all_funcs: list[FuncInfo]) -> str:
    lines: list[str] = []

    lines.append(_subsection_header("Function-size inventory (flag = lines > 20)"))
    lines.append(
        "  Uncle Bob's rule: every function should fit on one screen.\n"
        "  Anything over 20 lines is a candidate for extraction.\n"
    )

    # Column widths
    W_MOD  = max(len(f.module) for f in all_funcs) + 1
    W_CLS  = max((len(f.cls) for f in all_funcs), default=0) + 1
    W_NAME = max(len(f.name) for f in all_funcs) + 1
    W_LINE = 6
    W_SIZE = 6

    header = (
        f"  {'Module':<{W_MOD}} {'Class':<{W_CLS}} {'Function':<{W_NAME}} "
        f"{'Line':>{W_LINE}} {'Size':>{W_SIZE}}  Flag"
    )
    sep = "  " + "─" * (W_MOD + W_CLS + W_NAME + W_LINE + W_SIZE + 14)
    lines.append(header)
    lines.append(sep)

    flagged: list[FuncInfo] = []
    for f in all_funcs:
        flag_str = "  ◀ TOO LONG" if f.flag else ""
        lines.append(
            f"  {f.module:<{W_MOD}} {f.cls:<{W_CLS}} {f.name:<{W_NAME}} "
            f"{f.first_line:>{W_LINE}} {f.size:>{W_SIZE}}{flag_str}"
        )
        if f.flag:
            flagged.append(f)

    lines.append(sep)
    lines.append(f"\n  Total functions : {len(all_funcs)}")
    lines.append(f"  Flagged (> 20 ln): {len(flagged)}")

    if flagged:
        lines.append("\n" + _subsection_header("Summary of flagged functions"))
        for f in flagged:
            qual = f"{f.module}.{f.cls}.{f.name}" if f.cls else f"{f.module}.{f.name}"
            lines.append(f"  ✗  {qual:<55}  {f.size} lines  (line {f.first_line})")
    else:
        lines.append("\n  ✓  All functions are within the 20-line guideline.\n")

    return "\n".join(lines)


# ===========================================================================
# Sections 3–5 — source files
# ===========================================================================

def _include_files(section_num: int, title: str, paths: list[Path],
                   subsections: dict[str, str] | None = None) -> str:
    """Render a full section with optional subsection labels.

    *subsections* maps a filename stem prefix → subsection title.
    """
    parts: list[str] = [_section_header(section_num, title)]
    current_sub: str | None = None

    for path in paths:
        if not path.exists():
            continue

        # optionally emit a subsection header when the group changes
        if subsections:
            rel = _rel(path)
            for prefix, sub_title in subsections.items():
                if prefix in rel and sub_title != current_sub:
                    parts.append(_subsection_header(sub_title))
                    current_sub = sub_title
                    break

        parts.append(_file_header(_rel(path)))
        parts.append(_read(path))

    return "\n".join(parts)


# ===========================================================================
# Main
# ===========================================================================

def build(out_path: Path) -> None:
    # Determine package version
    try:
        pkg_version = importlib.metadata.version("ph_ai_tracker")
    except importlib.metadata.PackageNotFoundError:
        pkg_version = "?.?.?"

    # Collect all functions from production code (for the inventory)
    all_funcs: list[FuncInfo] = []
    for path in SECTION_3_PRODUCTION:
        if path.exists():
            all_funcs.extend(_collect_functions(path))

    file_counts = {
        "prod":   sum(1 for p in SECTION_3_PRODUCTION if p.exists()),
        "tests":  sum(1 for p in SECTION_4_TESTS      if p.exists()),
        "config": sum(1 for p in SECTION_5_CONFIG      if p.exists()),
    }

    chunks: list[str] = []

    # ── Section 0 ─────────────────────────────────────────────────────────
    chunks.append(_section_header(0, "COVER PAGE & TABLE OF CONTENTS"))
    chunks.append(_cover_and_toc(pkg_version, file_counts))

    # ── Section 1 ─────────────────────────────────────────────────────────
    chunks.append(_section_header(1, "ARCHITECTURE OVERVIEW"))
    chunks.append(_dependency_graph())

    # ── Section 2 ─────────────────────────────────────────────────────────
    chunks.append(_section_header(2, "FUNCTION-SIZE INVENTORY"))
    chunks.append(_function_size_table(all_funcs))

    # ── Section 3 ─────────────────────────────────────────────────────────
    chunks.append(_include_files(3, "PRODUCTION CODE (ordered by dependency layer)", SECTION_3_PRODUCTION))

    # ── Section 4 ─────────────────────────────────────────────────────────
    chunks.append(_include_files(
        4,
        "TEST SUITE",
        SECTION_4_TESTS,
        subsections={
            "tests/unit":        "Unit Tests",
            "tests/integration": "Integration Tests",
            "tests/e2e":         "End-to-End Tests",
            "tests/conftest":    "Shared Fixtures (conftest)",
        },
    ))

    # ── Section 5 ─────────────────────────────────────────────────────────
    chunks.append(_include_files(5, "CONFIGURATION & BUILD", SECTION_5_CONFIG))

    # Write
    out_path.write_text("\n".join(chunks), encoding="utf-8")
    lines = out_path.read_text(encoding="utf-8").count("\n")
    print(f"Bundle written to : {out_path.relative_to(ROOT)}")
    print(f"Lines             : {lines:,}")
    print(f"Size              : {out_path.stat().st_size / 1024:.1f} KB")
    print(f"Production files  : {file_counts['prod']}")
    print(f"Test files        : {file_counts['tests']}")
    print(f"Config files      : {file_counts['config']}")
    print(f"Functions tracked : {len(all_funcs)}")
    flagged = sum(1 for f in all_funcs if f.flag)
    if flagged:
        print(f"⚠  Flagged (> 20 ln): {flagged}")
    else:
        print("✓  All functions within 20-line guideline")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build the Uncle Bob review bundle.")
    parser.add_argument("--out", default="codebase_review_bundle.txt",
                        help="Output file path (default: codebase_review_bundle.txt)")
    args = parser.parse_args()
    build(ROOT / args.out)

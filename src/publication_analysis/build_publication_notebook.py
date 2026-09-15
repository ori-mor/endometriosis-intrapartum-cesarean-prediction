#!/usr/bin/env python3
"""Assemble the publication / inferential-analysis notebook from its 10 part files.

Usage (from project root):
    python analysis/publication_analysis/build_publication_notebook.py [--dry-run]

--dry-run prints cell counts and IDs without writing a notebook.
Output: notebooks/publication/01_publication_statistical_analysis.ipynb

This builder only assembles and validates static notebook-cell JSON — it
never executes any cell, never imports analysis.modeling.final_modeling, and
never reads or writes patient-level data itself.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BUILD_DIR.parent.parent
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "publication" / "01_publication_statistical_analysis.ipynb"
PARTS_DIR = BUILD_DIR / "notebook_parts"

# Part files must be loadable both as plain files (via spec_from_file_location,
# used below) and via absolute package import (``from
# publication_analysis...``, used inside several part files to reach
# the shared cell-construction helpers) — so the project root must be on
# sys.path before any part file is executed.
# Submission package: publication_analysis lives under src/, not analysis/.
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

PART_FILES = [
    (PARTS_DIR / "part1_intro_and_contract.py", "PART1_CELLS"),
    (PARTS_DIR / "part2_variable_audit.py", "PART2_CELLS"),
    (PARTS_DIR / "part3_table1.py", "PART3_CELLS"),
    (PARTS_DIR / "part4_univariable_and_fdr.py", "PART4_CELLS"),
    (PARTS_DIR / "part5_endometriosis_findings.py", "PART5_CELLS"),
    (PARTS_DIR / "part6_adjusted_analysis.py", "PART6_CELLS"),
    (PARTS_DIR / "part7_research_signal.py", "PART7_CELLS"),
    (PARTS_DIR / "part8_predictive_context.py", "PART8_CELLS"),
    (PARTS_DIR / "part9_figures.py", "PART9_CELLS"),
    (PARTS_DIR / "part10_limitations.py", "PART10_CELLS"),
]


def load_part(path: Path, attr: str) -> list:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, attr)


def build_notebook(cells: list) -> dict:
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.12.10"},
        },
        "cells": cells,
    }


def validate_cells(cells: list) -> bool:
    ok = True
    ids = [cell["id"] for cell in cells]
    duplicates = sorted({cid for cid in ids if ids.count(cid) > 1})
    if duplicates:
        print(f"  WARNING: duplicate cell IDs: {duplicates}")
        ok = False

    bad_outputs = [
        cell["id"]
        for cell in cells
        if cell["cell_type"] == "code"
        and (cell.get("outputs") != [] or cell.get("execution_count") is not None)
    ]
    if bad_outputs:
        print(f"  WARNING: uncleared code cells: {bad_outputs}")
        ok = False

    for cell in cells:
        source = "".join(cell.get("source", []))
        for identifier in ("subject_number", "delivery_id"):
            if re.search(rf"\bprint\s*\([^)]*\b{identifier}\b", source):
                print(f"  WARNING: cell {cell['id']} may print {identifier}")
                ok = False

    forbidden_import_tokens = ("import analysis.modeling.final_modeling", "from analysis.modeling.final_modeling")
    for cell in cells:
        source = "".join(cell.get("source", []))
        for token in forbidden_import_tokens:
            if token in source:
                print(f"  WARNING: cell {cell['id']} references a forbidden final_modeling import")
                ok = False

    return ok


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    all_cells = []
    print("Assembling publication / inferential-analysis notebook...")

    for path, attr in PART_FILES:
        if not path.exists():
            print(f"ERROR: {path.name} not found.")
            sys.exit(1)
        cells = load_part(path, attr)
        n_code = sum(cell["cell_type"] == "code" for cell in cells)
        n_markdown = sum(cell["cell_type"] == "markdown" for cell in cells)
        print(f"  {path.name}: {len(cells)} cells ({n_code} code, {n_markdown} markdown)")
        all_cells.extend(cells)

    print(f"\nTotal cells: {len(all_cells)}")
    print("\nValidating...")
    valid = validate_cells(all_cells)
    print("  OK" if valid else "  Validation issues found.")

    if dry_run:
        print("\n[DRY RUN] Notebook NOT written.")
        for cell in all_cells:
            print(f"  [{cell['cell_type'][:4]}] {cell['id']}")
        return

    if not valid:
        print("\nRefusing to write notebook: validation issues found (see warnings above).")
        sys.exit(1)

    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTEBOOK_PATH.open("w", encoding="utf-8") as handle:
        json.dump(build_notebook(all_cells), handle, indent=1, ensure_ascii=False)
    print(f"\nNotebook written: {NOTEBOOK_PATH}")
    print(f"Size: {NOTEBOOK_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()

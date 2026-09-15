#!/usr/bin/env python3
"""Assemble the EDA C notebook from its 5 part files.

Usage (from project root):
    python analysis/eda/notebook_build/eda_c/build_eda_c_notebook.py [--dry-run]

--dry-run prints cell counts and IDs without writing a notebook.
Output: notebooks/eda/04_eda_c_modeling_handoff.ipynb
"""

import importlib.util
import json
import re
import sys
from pathlib import Path


BUILD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BUILD_DIR.parent.parent.parent.parent
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "eda" / "04_eda_c_modeling_handoff.ipynb"

PART_FILES = [
    (BUILD_DIR / "eda_c_part1_setup_gate.py", "EDA_C_PART1_CELLS"),
    (BUILD_DIR / "eda_c_part2_recheck.py", "EDA_C_PART2_CELLS"),
    (BUILD_DIR / "eda_c_part3_feature_engineering.py", "EDA_C_PART3_CELLS"),
    (BUILD_DIR / "eda_c_part4_screening.py", "EDA_C_PART4_CELLS"),
    (BUILD_DIR / "eda_c_part5_handoff.py", "EDA_C_PART5_CELLS"),
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
    return ok


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    all_cells = []
    print("Assembling EDA C notebook...")

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

    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTEBOOK_PATH.open("w", encoding="utf-8") as handle:
        json.dump(build_notebook(all_cells), handle, indent=1, ensure_ascii=False)
    print(f"\nNotebook written: {NOTEBOOK_PATH}")
    print(f"Size: {NOTEBOOK_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()

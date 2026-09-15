#!/usr/bin/env python3
"""Assemble the Data Cleaning B notebook from its 6 part files.

Usage (from project root):
    python analysis/data_cleaning/notebook_build/data_cleaning_b/build_data_cleaning_b_notebook.py [--dry-run]

--dry-run prints cell counts and IDs without writing a notebook.
Output: notebooks/eda/03_data_cleaning_b_after_initial_eda.ipynb

Decision 92 (2026-08-29): PART_FILES below is assembled in EXECUTION order,
which is now:
    Part 1 (setup B1/B1c)
    -> Part 3 (outlier review B2/B2b, formerly numbered B4/B4b)
    -> Part 3b (pure continuous transformation review B3 -- new)
    -> Part 2 (missingness assessment B4/B4b/B4c/B4d, formerly numbered
       B2/B2c/B2b/B3)
    -> Part 4 (final derived/model-facing representations B5, imputation
       plan B6)
    -> Part 5 (export/validation B7)
This reorder was proven, by a prior read-only dependency audit, not to
change any patient-level value, derived column, or audit-CSV content --
Part 3 (outlier) and Part 3b (transformation review) read only objects
already established by Part 1/B1c and do not depend on Part 2's
(missingness) output; Part 2 does not depend on Part 3/3b's output either.
Filenames were intentionally NOT renamed to match the new execution order
(historical filenames remain acceptable -- the assembly order below is
authoritative, not the filenames). See
docs/clinical_decisions/manual_decisions_log.md Decision 92 for the full
rationale.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path


BUILD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BUILD_DIR.parent.parent.parent.parent
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "eda" / "03_data_cleaning_b_after_initial_eda.ipynb"

PART_FILES = [
    (BUILD_DIR / "cleaning_b_part1_setup_inputs.py", "CLEANING_B_PART1_CELLS"),
    (BUILD_DIR / "cleaning_b_part3_outlier_handling.py", "CLEANING_B_PART3_CELLS"),
    (BUILD_DIR / "cleaning_b_part3b_transformation_review.py", "CLEANING_B_PART3B_CELLS"),
    (BUILD_DIR / "cleaning_b_part2_missingness_handling.py", "CLEANING_B_PART2_CELLS"),
    (BUILD_DIR / "cleaning_b_part4_transformations_imputation_plan.py", "CLEANING_B_PART4_CELLS"),
    (BUILD_DIR / "cleaning_b_part5_export_cleaned_dataset.py", "CLEANING_B_PART5_CELLS"),
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
            "language_info": {"name": "python", "version": "3.10.0"},
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
    print("Assembling Data Cleaning B notebook...")

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
    print("  OK" if validate_cells(all_cells) else "  Validation issues found.")

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

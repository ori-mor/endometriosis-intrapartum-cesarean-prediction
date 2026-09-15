#!/usr/bin/env python3
"""Assemble the initial predictor-readiness EDA notebook (stage A2) from its part files.

NOTE (methodology): This builder produces a SECTION 1 (Initial EDA) notebook.
This folder was renamed from `eda_b` to `a2_predictor_readiness` on
2026-08-24 (the A2 namespace refactor) once the A2 freeze gate passed;
internal `EDA_B_*`/`SB<n>_*` Python symbol names and `eda-b-*` cell IDs are
deliberately kept unchanged for execution stability only -- they do not mean
"Data Cleaning B." This is the A2 initial predictor-readiness stage — it
performs NO data cleaning. The methodological Section 2 (Data Cleaning, "B")
lives in `analysis/data_cleaning/notebook_build/data_cleaning_b/`.

Usage (from project root):
    python analysis/eda/notebook_build/a2_predictor_readiness/build_a2_notebook.py [--dry-run]

--dry-run prints cell counts and IDs without writing a notebook.
Output: notebooks/eda/02b_eda_a_initial_predictor_readiness.ipynb
"""

import importlib.util
import json
import re
import sys
from pathlib import Path


BUILD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BUILD_DIR.parent.parent.parent.parent
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "eda" / "02b_eda_a_initial_predictor_readiness.ipynb"

# Assembly order (2026-08-08 reorg) is intentionally NOT part1/part2/part3/.../
# part5 file-name order: each part file's *internal* section order was kept
# stable, so producing the methodological A2.0-A2.15 sequence only requires
# reordering which file gets concatenated when -- part3 (numeric/binary/
# categorical/domain distributions, now A2.3-A2.6) must render before part2
# (missingness deep-dive/sparsity, now A2.7-A2.8), which must render before part4
# (associations/redundancy/outliers, now A2.9-A2.11), which must render before
# part5 (now holds the relocated former-B5 comprehensive table as A2.12, plus
# the original A2.13-A2.15).
PART_FILES = [
    (BUILD_DIR / "a2_part1_setup_scope.py", "EDA_B_PART1_CELLS"),
    (BUILD_DIR / "a2_part3_distributions.py", "EDA_B_PART3_CELLS"),
    (BUILD_DIR / "a2_part2_missingness.py", "EDA_B_PART2_CELLS"),
    (BUILD_DIR / "a2_part4_associations.py", "EDA_B_PART4_CELLS"),
    (BUILD_DIR / "a2_part5_readiness.py", "EDA_B_PART5_CELLS"),
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
    duplicates = sorted({cell_id for cell_id in ids if ids.count(cell_id) > 1})
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
    print("Assembling A2 notebook...")

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


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Assemble the EDA A notebook from its part files.

Usage (from project root):
    python analysis/eda/notebook_build/eda_a/build_eda_a_notebook.py [--dry-run]

--dry-run  Print cell counts and IDs but do NOT write the notebook.

Output: notebooks/eda/02_eda_a_initial_cohort_overview.ipynb
"""

import sys, json, importlib.util
from pathlib import Path

BUILD_DIR     = Path(__file__).resolve().parent
PROJECT_ROOT  = BUILD_DIR.parent.parent.parent.parent  # project root
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "eda" / "02_eda_a_initial_cohort_overview.ipynb"

PART_FILES = [
    (BUILD_DIR / "eda_a_part1_setup_cohort.py", "EDA_A_PART1_CELLS"),
    (BUILD_DIR / "eda_a_part2_summaries.py",    "EDA_A_PART2_CELLS"),
]


def load_part(path: Path, attr: str) -> list:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, attr)


def build_notebook(cells: list) -> dict:
    return {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.0"},
        },
        "cells": cells,
    }


def validate_cells(cells: list) -> bool:
    ok = True
    ids = [c["id"] for c in cells]
    seen, dupes = set(), set()
    for cid in ids:
        if cid in seen:
            dupes.add(cid)
        seen.add(cid)
    if dupes:
        print(f"  WARNING: duplicate cell IDs: {sorted(dupes)}")
        ok = False
    bad = [c["id"] for c in cells if c["cell_type"] == "code" and c.get("outputs") != []]
    if bad:
        print(f"  WARNING: code cells with non-empty outputs: {bad}")
        ok = False
    import re
    for c in cells:
        src_text = "".join(c.get("source", []))
        for tok in ("subject_number", "delivery_id"):
            if re.search(rf'\bprint\s*\([^)]*\b{tok}\b', src_text):
                print(f"  WARNING: cell {c['id']} may print {tok}")
                ok = False
        # Regression guard: raw ID-value extraction (.values.tolist(),
        # .to_dict()) from a subject_number/delivery_id-derived slice is the
        # pattern that previously let duplicate-key values leak into a raised
        # ValueError (and thus into notebook/HTML output). No legitimate use
        # of this notebook's aggregate-only design should do this.
        if re.search(
            r'\b(?:subject_number|delivery_id|_KEY_COLS)\b[^\n]{0,80}'
            r'\.(?:values\.tolist|to_dict)\(\)',
            src_text,
        ):
            print(f"  WARNING: cell {c['id']} may extract raw subject_number/delivery_id values")
            ok = False
    return ok


def main():
    dry_run = "--dry-run" in sys.argv
    print("Assembling EDA A notebook...")
    all_cells = []
    for path, attr in PART_FILES:
        if not path.exists():
            print(f"ERROR: {path.name} not found.")
            sys.exit(1)
        cells = load_part(path, attr)
        n_code = sum(1 for c in cells if c["cell_type"] == "code")
        n_md   = sum(1 for c in cells if c["cell_type"] == "markdown")
        print(f"  {path.name}: {len(cells)} cells ({n_code} code, {n_md} markdown)")
        all_cells.extend(cells)

    print(f"\nTotal cells: {len(all_cells)}")
    print("\nValidating...")
    valid = validate_cells(all_cells)
    if not valid:
        print("  Validation issues found — continuing anyway.")
    else:
        print("  OK")

    if dry_run:
        print("\n[DRY RUN] Notebook NOT written.")
        return

    nb = build_notebook(all_cells)
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
    print(f"\nNotebook written: {NOTEBOOK_PATH}")
    print(f"Size: {NOTEBOOK_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()

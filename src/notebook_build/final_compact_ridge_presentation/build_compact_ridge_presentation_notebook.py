#!/usr/bin/env python3
"""Assemble the Compact Ridge presentation notebook from its 5 part files.

SUBMISSION-ONLY BUILDER. This is a curated adaptation of the canonical
builder for the curated submission package layout
(`src/notebook_build/final_compact_ridge_presentation/`, 3 levels below the
submission root, vs. the canonical repository's
`analysis/modeling/notebook_build/final_compact_ridge_presentation/`, 4
levels below its root). Do not copy this file back into the canonical
repository -- its PROJECT_ROOT depth and generated cell paths are specific
to this package's directory layout.

Usage (from the submission root):
    python src/notebook_build/final_compact_ridge_presentation/build_compact_ridge_presentation_notebook.py [--dry-run]

Output: notebooks/05_final_compact_ridge_model.ipynb

This notebook PRESENTS the already-locked Decision 99 Compact Ridge final
model. It reads only already-generated, curated aggregate artifacts under
results/tables/reproducibility/, results/tables/compact_ridge_final/, and
results/figures/compact_ridge_final/ -- no new fitting, no new
cross-validation, no hold-out access, no new scientific decision, no
patient-level input.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BUILD_DIR.parent.parent.parent
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "05_final_compact_ridge_model.ipynb"

PART_FILES = [
    (BUILD_DIR / "part1_intro_and_contract.py", "PART1_CELLS"),
    (BUILD_DIR / "part2_locked_validation_results.py", "PART2_CELLS"),
    (BUILD_DIR / "part3_full_refit_coefficients_ors.py", "PART3_CELLS"),
    (BUILD_DIR / "part4_calibration_and_diagnostics.py", "PART4_CELLS"),
    (BUILD_DIR / "part5_limitations_and_provenance.py", "PART5_CELLS"),
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
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12.10"},
        },
        "cells": cells,
    }


_FORBIDDEN_TOKENS = (
    "HOLDOUT_IDX", "TRAIN_IDX", "train_test_split",
    "evaluate_locked_holdout_candidates", "phase4b_endo_search_runner",
    "derive_provisional_endo_aware_coefficients",
)


def validate_cells(cells: list) -> bool:
    ok = True
    ids = [c["id"] for c in cells]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups:
        print(f"  WARNING: duplicate cell IDs: {dups}")
        ok = False
    bad = [c["id"] for c in cells if c["cell_type"] == "code"
           and (c.get("outputs") != [] or c.get("execution_count") is not None)]
    if bad:
        print(f"  WARNING: uncleared code cells: {bad}")
        ok = False
    for c in cells:
        source = "".join(c.get("source", []))
        for ident in ("subject_number", "delivery_id"):
            if re.search(rf"\bprint\s*\([^)]*\b{ident}\b", source):
                print(f"  WARNING: cell {c['id']} may print {ident}")
                ok = False
        for token in _FORBIDDEN_TOKENS:
            if token in source:
                print(f"  WARNING: cell {c['id']} references forbidden token {token!r} (hold-out / superseded entrypoint)")
                ok = False
    return ok


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    all_cells = []
    print("Assembling Compact Ridge presentation notebook...")
    for path, attr in PART_FILES:
        if not path.exists():
            print(f"ERROR: {path.name} not found.")
            sys.exit(1)
        cells = load_part(path, attr)
        n_code = sum(c["cell_type"] == "code" for c in cells)
        n_md = sum(c["cell_type"] == "markdown" for c in cells)
        print(f"  {path.name}: {len(cells)} cells ({n_code} code, {n_md} markdown)")
        all_cells.extend(cells)
    print(f"\nTotal cells: {len(all_cells)}")
    print("Validating...")
    ok = validate_cells(all_cells)
    print("  OK" if ok else "  Validation issues found.")
    if dry_run:
        print("\n[DRY RUN] Notebook NOT written.")
        for c in all_cells:
            print(f"  [{c['cell_type'][:4]}] {c['id']}")
        return
    if not ok:
        print("\nRefusing to write notebook: validation issues found (see warnings above).")
        sys.exit(1)
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTEBOOK_PATH.open("w", encoding="utf-8") as fh:
        json.dump(build_notebook(all_cells), fh, indent=1, ensure_ascii=False)
    print(f"\nNotebook written: {NOTEBOOK_PATH}")
    print(f"Size: {NOTEBOOK_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()

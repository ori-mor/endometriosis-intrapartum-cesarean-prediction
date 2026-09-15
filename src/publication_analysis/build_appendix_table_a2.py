#!/usr/bin/env python3
"""Build Appendix Table A2 from already-generated publication-analysis artifacts.

This script is intentionally a display/export layer only. It reads canonical
publication-analysis CSVs and writes Appendix A2 CSV/XLSX/Markdown outputs;
it never reruns univariable models, applies BH-FDR, or touches predictive
modeling artifacts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Submission package: publication_analysis lives under src/, not analysis/.
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from publication_analysis import appendix_tables
from publication_analysis import publication_display_labels
from publication_analysis import publication_exports as exports


def _read_canonical_table(filename: str) -> pd.DataFrame:
    return pd.read_csv(
        exports.TABLES_DIR / filename,
        dtype=str,
        keep_default_na=False,
    )


def main() -> None:
    univariable_master = _read_canonical_table(exports.UNIVARIABLE_MASTER_CSV)
    hypothesis_fdr = _read_canonical_table(
        exports.PREDICTOR_LEVEL_HYPOTHESIS_FDR_CSV
    )
    categorical_level_detail = _read_canonical_table(
        exports.UNIVARIABLE_PREDICTOR_LEVEL_TESTS_CSV
    )
    representation_contract = _read_canonical_table(
        exports.PUBLICATION_REPRESENTATION_CONTRACT_CSV
    )
    compact_table2_saved = _read_canonical_table(
        exports.TABLE_2_COMPACT_FINAL_PREDICTORS_UNIVARIABLE_CSV
    )

    appendix_table_a2 = appendix_tables.build_appendix_table_a2(
        univariable_master=univariable_master,
        hypothesis_fdr=hypothesis_fdr,
        categorical_level_detail=categorical_level_detail,
        representation_contract=representation_contract,
        predictor_display_labels=publication_display_labels.DISPLAY_LABELS,
    )
    paths = appendix_tables.save_appendix_table_a2_exports(appendix_table_a2)

    # Side-effect guard: the compact Table 2 export is loaded read-only above
    # and compared after A2 writing so accidental mutation is caught here too.
    compact_table2_after = _read_canonical_table(
        exports.TABLE_2_COMPACT_FINAL_PREDICTORS_UNIVARIABLE_CSV
    )
    pd.testing.assert_frame_equal(
        compact_table2_saved,
        compact_table2_after,
        check_dtype=False,
    )

    source_rows = int((appendix_table_a2["Row type"] == "source").sum())
    category_rows = int((appendix_table_a2["Row type"] == "category_subrow").sum())
    print(f"Appendix Table A2 source rows: {source_rows}")
    print(f"Appendix Table A2 category subrows: {category_rows}")
    print(f"Appendix Table A2 total display rows: {len(appendix_table_a2)}")
    for kind, path in paths.items():
        print(f"{kind}: {path}")


if __name__ == "__main__":
    main()

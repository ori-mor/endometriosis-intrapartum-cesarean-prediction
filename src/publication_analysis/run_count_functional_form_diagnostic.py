#!/usr/bin/env python
"""Rerun ONLY the 5 count functional-form diagnostics (P, G, CS, LIVE_BIRTH,
AB) using the corrected predefined-quadratic method (Count Functional-Form
Low-DF Correction task).

Does NOT touch the 6 continuous predictors' diagnostic in any way -- their
rows are read UNCHANGED from the existing
``outputs/publication_analysis/audit/functional_form_review.csv`` (already
produced by the prior, methodologically-corrected continuous run) and
carried forward verbatim into the updated combined CSV.

This is the ONLY real-patient-level model fitting authorized by this task:
the 5 count predictors' linear-vs-quadratic diagnostic, nothing else. Does
NOT touch Final-D, does NOT create a holdout or threshold, writes only
under ``outputs/publication_analysis/``.

Usage (from project root):
    .venv312\\Scripts\\python.exe analysis/publication_analysis/run_count_functional_form_diagnostic.py
"""
from __future__ import annotations

import pandas as pd

from publication_analysis import analysis_matrix as amx
from publication_analysis import publication_exports as exports
from publication_analysis import subject_grouping
from publication_analysis.functional_form_diagnostic import (
    COUNT_PREDICTORS,
    FUNCTIONAL_FORM_REVIEW_COLUMNS,
    build_functional_form_review_table,
    count_level_prediction_diagnostic_table,
    run_count_diagnostic,
)
from publication_analysis.verify_subject_group_parity import verify_live_subject_group_parity

TARGET_COL = "target_intrapartum_cs"


def main() -> None:
    print("Count functional-form diagnostic rerun -- ONLY P/G/CS/LIVE_BIRTH/AB.")
    print("The six CONTINUOUS predictors are NOT rerun; their existing rows are")
    print("carried forward unchanged from the current functional_form_review.csv.")

    review_path = exports.AUDIT_DIR / exports.FUNCTIONAL_FORM_REVIEW_CSV
    if not review_path.exists():
        raise FileNotFoundError(
            f"{review_path} not found -- run the continuous diagnostic first "
            "(analysis/publication_analysis/run_functional_form_diagnostic.py); "
            "this script only ever refreshes the 5 count rows within an existing review table."
        )
    existing_review = pd.read_csv(review_path)
    continuous_rows = existing_review[existing_review["physical_type"] == "continuous"].copy()
    print(f"\nLoaded {len(continuous_rows)} existing CONTINUOUS rows unchanged from {review_path}:")
    print(continuous_rows["predictor"].tolist())
    if len(continuous_rows) != 6:
        raise AssertionError(
            f"expected exactly 6 continuous rows in the existing review table, found {len(continuous_rows)} "
            "-- refusing to proceed with a possibly-stale/corrupt file."
        )

    print("\nLoading the canonical Checkpoint-A analytical matrix + subject grouping...")
    matrix_df, row_key_df = amx.load_aligned_analysis_inputs()
    matrix_report = amx.validate_analysis_matrix(matrix_df, strict=True)
    print(f"  analytical matrix: {matrix_df.shape[0]} rows x {matrix_df.shape[1]} cols "
          f"(target + {matrix_report.n_predictors} predictors); contract OK: {matrix_report.ok}")

    batch18_df = subject_grouping.load_batch18()
    subject_groups = subject_grouping.build_subject_groups(matrix_df, row_key_df, batch18_df)

    parity_result = verify_live_subject_group_parity(strict=True)
    print(f"  subject-group parity gate: PASS "
          f"(rows={parity_result.n_rows}, row_label_equal={parity_result.row_label_equal}, "
          f"partition_equivalent={parity_result.partition_equivalent})")

    exports.ensure_output_dirs()

    print("\n--- COUNT predictors (corrected quadratic diagnostic) ---")
    count_results = []
    count_support_frames = []
    count_prediction_frames = []
    for predictor in COUNT_PREDICTORS:
        result = run_count_diagnostic(matrix_df, TARGET_COL, predictor, subject_groups)
        count_results.append(result)
        print(f"  {predictor}: N={result['analysis_N']} events={result['events']} "
              f"unique_values={result['n_unique_values']} "
              f"linear={result['linear_fit_status']} flexible={result['flexible_fit_status']} "
              f"robust_wald_stat={result['robust_wald_stat']} robust_wald_df={result['robust_wald_df']} "
              f"robust_wald_p={result['robust_wald_p']} "
              f"sparse_tail_present={result['sparse_tail_present']} "
              f"any_level_zero_events={result['any_level_zero_events']} "
              f"any_level_zero_non_events={result['any_level_zero_non_events']} "
              f"-> {result['functional_form_status']}")
        support = result["_support_table"]
        count_support_frames.append(support)
        print(support.to_string(index=False))

        pred_table = count_level_prediction_diagnostic_table(
            support, result["_linear"], result["_flexible"], predictor,
        )
        count_prediction_frames.append(pred_table)
        print(pred_table.to_string(index=False))

    count_rows = build_functional_form_review_table(count_results)

    # Reindex the untouched continuous rows onto the CURRENT schema (which now
    # additionally carries sparse_tail_present / any_level_zero_events /
    # any_level_zero_non_events -- NOT applicable to continuous predictors,
    # so they become NaN there, never a fabricated value).
    continuous_rows_reindexed = continuous_rows.reindex(columns=FUNCTIONAL_FORM_REVIEW_COLUMNS)

    combined = pd.concat([continuous_rows_reindexed, count_rows], ignore_index=True)
    # restore the canonical 11-predictor order (6 continuous, then 5 count)
    from publication_analysis.functional_form_diagnostic import CONTINUOUS_PREDICTORS
    canonical_order = CONTINUOUS_PREDICTORS + COUNT_PREDICTORS
    combined["_order"] = combined["predictor"].map({p: i for i, p in enumerate(canonical_order)})
    combined = combined.sort_values("_order").drop(columns="_order").reset_index(drop=True)

    review_out_path = exports.save_table_csv(combined, exports.FUNCTIONAL_FORM_REVIEW_CSV, subdir=exports.AUDIT_DIR)
    print(f"\nWrote {review_out_path} ({len(combined)} rows: 6 continuous UNCHANGED + 5 count CORRECTED)")

    support_df = pd.concat(count_support_frames, ignore_index=True)
    support_path = exports.save_table_csv(
        support_df, exports.FUNCTIONAL_FORM_COUNT_SUPPORT_CSV, subdir=exports.AUDIT_DIR,
    )
    print(f"Wrote {support_path} ({len(support_df)} rows)")

    predictions_df = pd.concat(count_prediction_frames, ignore_index=True)
    predictions_path = exports.save_table_csv(
        predictions_df, exports.FUNCTIONAL_FORM_COUNT_LEVEL_PREDICTIONS_CSV, subdir=exports.AUDIT_DIR,
    )
    print(f"Wrote {predictions_path} ({len(predictions_df)} rows)")

    print("\nfunctional_form_status distribution for the 5 CORRECTED count rows "
          "(diagnostic RECOMMENDATION, not a contract update):")
    print(count_rows["functional_form_status"].value_counts().to_string())
    print("\nNOTE: the representation contract's own functional_form_status field is NOT "
          "modified by this run -- it remains PENDING_FUNCTIONAL_FORM_REVIEW for all 11 "
          "predictors pending a future, separate, manual review step.")
    print("NOTE: the 6 continuous rows above are byte-for-byte the same values as before this "
          "run -- only re-serialized alongside the corrected count rows into the same combined CSV.")


if __name__ == "__main__":
    main()

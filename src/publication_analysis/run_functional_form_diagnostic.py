#!/usr/bin/env python
"""Run the functional-form diagnostic for the 11 CONTINUOUS/COUNT predictors
(Representation Sign-off + Functional-Form Gate task, Sections 10-13;
CORRECTED per the Functional-Form Methodological Correction pass -- cluster-
robust Wald evidence, not an LR/p<0.05 automated classifier).

This is the ONLY real-patient-level model fitting authorized by that task:
just these 11 predictors' linear-vs-flexible diagnostic, nothing else. It
does NOT run the full 81-predictor univariable analysis, does NOT touch
Final-D, does NOT create a holdout or threshold, and writes only under
``outputs/publication_analysis/``.

The representation contract's own `functional_form_status` field is NOT
modified by this run -- every one of these 11 predictors stays
PENDING_FUNCTIONAL_FORM_REVIEW pending a future, separate, MANUAL review
step that weighs this diagnostic's evidence (robust Wald p-value, curve
shape, descriptive curve-difference metrics, data support, clinical
plausibility, parsimony) rather than a mechanical p-value rule.

Usage (from project root):
    .venv312\\Scripts\\python.exe analysis/publication_analysis/run_functional_form_diagnostic.py
"""
from __future__ import annotations

from publication_analysis import analysis_matrix as amx
from publication_analysis import publication_exports as exports
from publication_analysis import subject_grouping
from publication_analysis.functional_form_diagnostic import (
    COUNT_PREDICTORS,
    CONTINUOUS_PREDICTORS,
    build_functional_form_review_table,
    count_value_support_table,
    plot_functional_form_diagnostic,
    run_continuous_diagnostic,
    run_count_diagnostic,
)
from publication_analysis.verify_subject_group_parity import verify_live_subject_group_parity

TARGET_COL = "target_intrapartum_cs"


def main() -> None:
    print("Functional-form diagnostic -- the ONE authorized real-data run in this task.")
    print("Loading the canonical Checkpoint-A analytical matrix + subject grouping...")

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
    exports.FUNCTIONAL_FORM_FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    print("\n--- CONTINUOUS predictors ---")
    for predictor in CONTINUOUS_PREDICTORS:
        result = run_continuous_diagnostic(matrix_df, TARGET_COL, predictor, subject_groups)
        results.append(result)
        print(f"  {predictor}: N={result['analysis_N']} events={result['events']} "
              f"unique_values={result['n_unique_values']} "
              f"linear={result['linear_fit_status']} flexible={result['flexible_fit_status']} "
              f"robust_wald_p={result['robust_wald_p']} "
              f"-> {result['functional_form_status']}")

        fig = plot_functional_form_diagnostic(
            matrix_df, TARGET_COL, predictor, result["_linear"], result["_flexible"],
            result["reporting_unit"], result["_desc"],
        )
        fig_path = exports.save_figure(
            fig, f"functional_form_{predictor}.png", subdir=exports.FUNCTIONAL_FORM_FIGURES_DIR,
        )
        print(f"    figure: {fig_path}")

    print("\n--- COUNT predictors ---")
    count_support_frames = []
    for predictor in COUNT_PREDICTORS:
        result = run_count_diagnostic(matrix_df, TARGET_COL, predictor, subject_groups)
        results.append(result)
        print(f"  {predictor}: N={result['analysis_N']} events={result['events']} "
              f"unique_values={result['n_unique_values']} "
              f"linear={result['linear_fit_status']} flexible={result['flexible_fit_status']} "
              f"robust_wald_p={result['robust_wald_p']} "
              f"-> {result['functional_form_status']}")
        support = result["_support_table"]
        count_support_frames.append(support)
        print(support.to_string(index=False))

    review_table = build_functional_form_review_table(results)
    review_path = exports.save_table_csv(review_table, exports.FUNCTIONAL_FORM_REVIEW_CSV, subdir=exports.AUDIT_DIR)
    print(f"\nWrote {review_path} ({len(review_table)} rows)")

    import pandas as pd
    support_df = pd.concat(count_support_frames, ignore_index=True)
    support_path = exports.save_table_csv(
        support_df, exports.FUNCTIONAL_FORM_COUNT_SUPPORT_CSV, subdir=exports.AUDIT_DIR,
    )
    print(f"Wrote {support_path} ({len(support_df)} rows)")

    print("\nfunctional_form_status distribution in the review table (diagnostic RECOMMENDATION, "
          "not a contract update):")
    print(review_table["functional_form_status"].value_counts().to_string())
    print("\nNOTE: the representation contract's own functional_form_status field is NOT "
          "modified by this run -- it remains PENDING_FUNCTIONAL_FORM_REVIEW for all 11 "
          "predictors pending a future, separate, manual review step.")


if __name__ == "__main__":
    main()

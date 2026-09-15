"""Publication notebook — Part 6: adjusted endometriosis-specific association
analysis and missingness handling for inferential models (both Section F)."""
from publication_analysis.notebook_parts._cell_helpers import code, md

PART6_CELLS = [
    md(
        "pub-s14-header",
        """
---
## Section F — Adjusted Endometriosis Association Analysis

**One endometriosis-specific predictor at a time**, each with the same
small, pre-specified conventional-covariate adjustment set — never one
model containing all 35 endometriosis predictors together.

Two adjustment cores are **locked** (`adjusted_endometriosis_analysis.py` —
Adjusted Association Design Lock, Checkpoint C, APPROVED; not tunable, not
swappable per-exposure, not chosen by any statistical criterion):

- `PRIMARY_ADJUSTMENT_SET = AGE + nulliparity + S_P_CS` — the manuscript-facing
  main adjusted result.
- `SENSITIVITY_ADJUSTMENT_SET = PRIMARY_ADJUSTMENT_SET + mode_of_conception_ivf_vs_all`
  — a separate, explicitly secondary sensitivity analysis.

Only Class A (`STANDARD_ADJUSTED_MODEL_FEASIBLE`) and Class B
(`STANDARD_ADJUSTED_MODEL_HIGH_CAUTION`) exposures are fit with ordinary
logistic regression. Class C (`STANDARD_ADJUSTED_MODEL_NOT_DEFENSIBLE`)
exposures are represented as `NOT_FITTED` and are never rescued with Firth,
continuity correction, ad-hoc collapsing, or penalized OR estimates.

### Missingness in inferential models
Each adjusted model uses complete-case rows only (no fold-wise or MICE
imputation at this stage). `missingness_loss_n` / `missingness_loss_pct`
below are a presentational derived view (`N=431` minus each row's complete-case
`n`) — not a new statistic computed by `adjusted_endometriosis_analysis.py` —
so a reviewer can flag any adjusted analysis where the loss may warrant a
later multiple-imputation sensitivity check.
""",
    ),
    code(
        "pub-s14-imports",
        """
from publication_analysis import adjusted_endometriosis_analysis as adjusted
from publication_analysis.adjusted_association_reporting import (
    build_primary_bh_table,
    build_primary_vs_sensitivity_comparison,
    merge_bh_into_master,
)
""",
    ),
    code(
        "pub-s14-run-adjusted",
        """
# Derived from the validated analysis matrix (Section A), never a bare
# literal (targeted correction #7C) -- the assertion below still fails loud
# if the live cohort ever diverges from the locked canonical N=431.
FULL_COHORT_N = len(df)
assert FULL_COHORT_N == 431, (
    f"full cohort N derived from the validated analysis matrix is {FULL_COHORT_N}, expected "
    "the locked canonical N=431 -- STOP, do not silently proceed on a mismatched cohort."
)

adjusted_master = adjusted.run_adjusted_analysis_for_family(
    df,
    outcome_col=TARGET_COL,
    endometriosis_predictors=sorted(endo_family_names),
    subject_groups=subject_groups,
)

adjusted_primary_bh = build_primary_bh_table(adjusted_master)
adjusted_master = merge_bh_into_master(adjusted_master, adjusted_primary_bh)
adjusted_primary_vs_sensitivity = build_primary_vs_sensitivity_comparison(adjusted_master)

# Three DISTINCT counts (final micro-correction #1) -- `build_primary_bh_table`
# already excludes Class C, so its own row/exposure count is NOT the number of
# all 35 endometriosis-family source exposures. Counted separately here so
# Limitations (Section "Limitations") never needs to hardcode or conflate them.
n_primary_source_exposures_total = int(
    adjusted_master.loc[
        (adjusted_master["model_variant"] == adjusted.MODEL_VARIANT_PRIMARY)
        & (adjusted_master["row_type"] == adjusted.ROW_TYPE_SOURCE),
        "exposure",
    ].nunique()
)
n_primary_bh_eligible_class_ab = int(adjusted_primary_bh["exposure"].nunique())
n_primary_bh_estimable = int(adjusted_primary_bh["in_bh_family"].sum())
print(f"(A) total PRIMARY source exposures represented (Class A+B+C): {n_primary_source_exposures_total} "
      "(expected 35 -- one per endometriosis-family member)")
print(f"(B) Class A/B PRIMARY source exposures eligible for the BH procedure: {n_primary_bh_eligible_class_ab}")
print(f"(C) estimable p-values actually entering the BH denominator: {n_primary_bh_estimable}")
assert n_primary_source_exposures_total == 35

adjusted_master["missingness_loss_n"] = FULL_COHORT_N - adjusted_master["n"]
adjusted_master["missingness_loss_pct"] = (
    100.0 * adjusted_master["missingness_loss_n"] / FULL_COHORT_N
)
high_loss = adjusted_master[adjusted_master["missingness_loss_pct"] > 10]
if len(high_loss):
    print("COMPLETE_CASE_RETENTION_WARNING for:", sorted(set(high_loss["exposure"])))

exports.save_table_csv(adjusted_master, exports.ADJUSTED_ENDOMETRIOSIS_ANALYSIS_CSV)
adjusted_master.head(20)
""",
    ),
    md(
        "pub-s14b-bh-header",
        """
### PRIMARY BH-FDR family (Class A/B source-level p-values only)

A separate exploratory multiplicity family from the global 81-predictor
family in Section D — this one is scoped to the 35 endometriosis-family
exposures' PRIMARY adjusted source-level p-values (Class C excluded). This is
the ONLY BH family computed for the adjusted analysis; it is never
recomputed per-subset elsewhere in this notebook.
""",
    ),
    code(
        "pub-s14b-bh-table",
        """
adjusted_primary_bh.sort_values("raw_p", na_position="last")
""",
    ),
    md(
        "pub-s14c-sensitivity-header",
        """
### PRIMARY vs SENSITIVITY_IVF — descriptive comparison

Purely descriptive, one row per Class A/B exposure — no automatic
"robust"/"not robust" threshold is assigned by code. Saved as its own
canonical table (`exports.ADJUSTED_PRIMARY_VS_SENSITIVITY_CSV`) — the exact
dataframe `build_primary_vs_sensitivity_comparison(...)` already produced
above, never recomputed independently.
""",
    ),
    code(
        "pub-s14c-sensitivity-table",
        """
exports.save_table_csv(adjusted_primary_vs_sensitivity, exports.ADJUSTED_PRIMARY_VS_SENSITIVITY_CSV)
adjusted_primary_vs_sensitivity
""",
    ),
]

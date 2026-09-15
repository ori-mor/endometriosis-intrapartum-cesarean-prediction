#!/usr/bin/env python3
"""Data Cleaning B -- Part 3b cell definitions (Section B3).

B3 -- PURE CONTINUOUS TRANSFORMATION REVIEW. DESCRIPTIVE ONLY. TARGET-BLIND.

Decision 92 (2026-08-29): the notebook's execution order was restructured to
    Setup (B1/B1c) -> Outlier review (B2/B2b) -> Transformation review (B3)
    -> Missingness (B4/B4b/B4c/B4d) -> Representations (B5) -> Plan (B6)
    -> Export (B7)
This is section B3 in the new order. See
docs/clinical_decisions/manual_decisions_log.md Decision 92 for the full
rationale and the read-only dependency audit that proved this reorder does
not change any patient-level value, derived column, or audit-CSV content.

This section is deliberately narrow. It answers exactly one question for each
retained continuous, model-facing numeric variable: does the current primary
predictive architecture (logistic regression, compared like-for-like against
other model families through the same shared preprocessing pipeline) require
a fixed distribution-normalizing power transform (log / log1p / sqrt /
Box-Cox / Yeo-Johnson) of the raw clinical-unit value before scaling?

The answer for every currently-reviewed variable is NO -- `raw_no_fixed_power_
transform`. This section documents that the question WAS reviewed, not that
it was skipped. See the code cell below for the per-variable reasons; all of
them are variants of the same target-blind rationale:
  * logistic regression does not require normally distributed predictors --
    only a linear relationship between the predictor and the log-odds of the
    outcome, which a power transform does not, by itself, establish or
    refute;
  * skewness alone (a `descriptive_skew_flag`) is not sufficient justification
    for transformation;
  * clinically implausible/erroneous values are a data-quality question,
    already adjudicated separately and target-blind in Section B2 (Decision
    90) -- this section does not re-litigate that adjudication;
  * the raw clinical unit (years, kg, cm, g/dL, days) remains directly
    interpretable to a clinical reader, which a log/Box-Cox-transformed value
    would not be;
  * any future nonlinear functional-form sensitivity analysis (e.g. splines,
    a data-driven Box-Cox lambda) must be fitted fold-safely inside modeling
    cross-validation, never by mutating Batch19 globally here.

This decision is explicitly TARGET-BLIND: `target_intrapartum_cs`, event
rates, target correlations, model coefficients, and model performance are
never read anywhere in this section, and never appear in
`decision_reason` below (`target_used_for_decision` is always `False`).

### Which variables are reviewed here
The reviewed pool is derived, not hardcoded: every `CLEANING_SCOPE` column
that `infer_var_type` classifies as `"numeric"` (i.e. not binary, not a
low-cardinality discrete count, not string/categorical), MINUS the columns
already excluded because a different, already-approved model-facing
representation supersedes the raw continuous value for modeling purposes
(`CONTINUOUS_TRANSFORM_REVIEW_EXCLUDE_COLS` below -- `weight_in_pregnancy`,
`BMI_after` [documented fold-safe tertile categoricals, Decision 91, Section
B5b] and `endometrioma_size_clean` [superseded by `endometrioma_size_status`,
Section B5c]). Live-verified against the current 431-row/73-column post-B1c
cohort: this yields exactly six variables -- `AGE`, `weight_before_pregnancy`,
`height`, `BMI_before`, `Hb_before_delivery`,
`gestational_age_at_delivery_days` -- unchanged from the pool identified in
the prior read-only dependency audit. `gestational_age_at_PPROM_days` is not
in this pool at all: with only ~16 observed values it is classified
`"categorical"` by `infer_var_type` (its `nunique()` on observed data is below
the numeric threshold), not `"numeric"`.

The five discrete obstetric-history counts (`G`, `P`, `LIVE_BIRTH`, `AB`,
`CS`) are reported separately, explicitly marked
`not_applicable_discrete_count` -- they are already excluded from an
automatic log/sqrt rule for the same reason Section B2b gives: they are
small-integer counts, not continuous physiological measurements, and
`infer_var_type` itself already classifies them as `"categorical"`
(`nunique() <= 20`), so they were never in the continuous pool in the first
place. This section states that explicitly rather than silently.

### Output
`transformation_review_log` (initialised in Part 1) is exported by Section B7
as `outputs/data_cleaning/audit/cleaning_b_final_numeric_transformation_review.csv`.
"""


def src(text):
    lines = text.lstrip("\n").splitlines(keepends=True)
    if lines and lines[-1].endswith("\n"):
        lines[-1] = lines[-1][:-1]
    return lines


def md(cid, text):
    return {"id": cid, "cell_type": "markdown", "metadata": {}, "source": src(text)}


def code(cid, text):
    return {
        "id": cid,
        "cell_type": "code",
        "metadata": {},
        "source": src(text),
        "outputs": [],
        "execution_count": None,
    }


# ── Section B3 ────────────────────────────────────────────────────────────────
SB3T_HEADER = md("clean-b-s03-header", """
## Section B3 — Pure Continuous Transformation Review (Descriptive, Target-Blind)

Runs immediately after the outlier / extreme-value review (Section B2/B2b) and
before the missingness assessment (Section B4). Outliers are screened on the
original numeric scale first; this transformation review is deliberately
separate from, and does not depend on, that outlier adjudication or the
missingness assessment that follows it — it reads only `df_clean` /
`CLEANING_SCOPE` as established after Section B1/B1c.

**This is a review, not a skip.** For every reviewed continuous variable the
question "does this variable need a fixed power transform?" was explicitly
asked and answered. The answer is uniformly `raw_no_fixed_power_transform` —
no `log`, `log1p`, `sqrt`, `Box-Cox`, or `Yeo-Johnson` transform is applied to
any variable in Data Cleaning B, and none is planned as a future default. A
descriptive skewness figure is recorded for audit visibility only; it never
triggers, names, or pre-selects a transform family.

**Target-blind by construction:** `target_intrapartum_cs`, event rates,
per-variable target correlations, coefficients, and model performance are
never read in this section and never appear in any decision reason recorded
here.

**Binary type normalization is not part of this review.** Casting an
already-clean 0/1 column to a nullable `Int64` dtype (Section B5a) is a
deterministic type-conversion step, not a continuous-distribution decision.

### Downstream scaling contract (verification only, not enacted here)
Every retained continuous variable in this review — and the discrete counts,
which use the identical shared numeric preprocessing branch — is scaled
downstream by `sklearn.preprocessing.StandardScaler`, fit only on each
cross-validation training fold and applied transform-only to validation/test
folds (`analysis/modeling/final_modeling/modeling_core.py`,
`build_preprocessor()`). Data Cleaning B performs no scaling of any kind —
`StandardScaler` does not appear anywhere in this notebook.
""")

SB3T_REVIEW = code("clean-b-s03-review", '''
# -- B3 pure continuous transformation review (target-blind, non-mutating) ---
# Reviews whether a fixed power transform (log/log1p/sqrt/Box-Cox/Yeo-Johnson)
# should be applied to the raw clinical-unit value of each retained continuous
# model-facing variable. This cell reads no outcome/target column and creates
# no new dataframe column -- it only records a documentation-only decision per
# variable in transformation_review_log (initialised in Part 1).
SKEW_REVIEW_DESCRIPTIVE_THRESHOLD = 1.5  # |skew| above this is descriptively "high" -- documentation only, never a transform trigger

# -- Variables excluded because a different, already-approved model-facing ----
# representation supersedes the raw continuous value -- these are not
# power-transform questions at all, regardless of their raw numeric dtype.
CONTINUOUS_TRANSFORM_REVIEW_EXCLUDE_COLS = {
    "weight_in_pregnancy",      # modeling representation is the fold-safe weight_in_pregnancy_cat (Section B5b)
    "BMI_after",                # modeling representation is the fold-safe BMI_after_cat (Section B5b)
    "endometrioma_size_clean",  # superseded by endometrioma_size_status (Section B5c)
}

CONTINUOUS_TRANSFORM_REVIEW_COLS = [
    c for c in CLEANING_SCOPE
    if infer_var_type(df_clean[c]) == "numeric"
    and c not in CONTINUOUS_TRANSFORM_REVIEW_EXCLUDE_COLS
]

# Discrete obstetric-history counts, reported separately, never subject to an
# automatic continuous log/sqrt rule (same rationale as Section B2b). Listed
# explicitly here for completeness -- infer_var_type already classifies each
# as "categorical" (nunique <= 20), so none of these was ever in
# CONTINUOUS_TRANSFORM_REVIEW_COLS above.
DISCRETE_COUNT_REVIEW_COLS = [c for c in ["G", "P", "LIVE_BIRTH", "AB", "CS"] if c in CLEANING_SCOPE]

_TARGET_BLIND_REASON = (
    "Logistic regression requires a linear relationship between the predictor "
    "and the log-odds of the outcome, not a normally distributed predictor -- "
    "skewness alone is not sufficient justification for transformation. "
    "Clinically implausible/erroneous values were already adjudicated "
    "separately and target-blind in Section B2; this section does not "
    "re-litigate that adjudication. The raw clinical unit remains directly "
    "interpretable to a clinical reader. Any future nonlinear functional-form "
    "sensitivity analysis (e.g. splines, a data-driven Box-Cox lambda) must be "
    "fitted fold-safely inside modeling cross-validation, never by mutating "
    "Batch19 globally here. This decision does not read target_intrapartum_cs, "
    "event rates, target correlations, coefficients, or model performance."
)

for col in CONTINUOUS_TRANSFORM_REVIEW_COLS:
    _s = df_clean[col].dropna()
    _skew = float(_s.skew()) if len(_s) >= 10 else None
    _high_skew = bool(_skew is not None and abs(_skew) > SKEW_REVIEW_DESCRIPTIVE_THRESHOLD)
    _stage_1 = col in PREDICTOR_ALLOWED_COLS
    _stage_2 = _stage_1 or col in SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS
    _stage_3 = _stage_2 or col in INTRAPARTUM_PREDICTOR_EXCLUDE_COLS

    transformation_review_log.append({
        "variable": col,
        "stage_1": _stage_1,
        "stage_2": _stage_2,
        "stage_3": _stage_3,
        "continuous_or_discrete": "continuous",
        "skewness": round(_skew, 3) if _skew is not None else None,
        "descriptive_skew_flag": _high_skew,
        "power_transform_reviewed": True,
        "primary_power_transform_decision": "raw_no_fixed_power_transform",
        "decision_reason": _TARGET_BLIND_REASON,
        "target_used_for_decision": False,
        "downstream_scaling": "fold_safe_standard_scaler",
    })
    column_actions_log.append({
        "column": col, "stage": "B3_transformation_review",
        "action": "raw_no_fixed_power_transform",
        "detail": (
            f"skew={round(_skew, 2) if _skew is not None else 'n/a'} -- reviewed, "
            "target-blind; no log/log1p/sqrt/Box-Cox/Yeo-Johnson applied; "
            "downstream scaling is StandardScaler, fit training-fold-only in modeling"
        ),
    })

for col in DISCRETE_COUNT_REVIEW_COLS:
    _stage_1 = col in PREDICTOR_ALLOWED_COLS
    _stage_2 = _stage_1 or col in SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS
    _stage_3 = _stage_2 or col in INTRAPARTUM_PREDICTOR_EXCLUDE_COLS
    transformation_review_log.append({
        "variable": col,
        "stage_1": _stage_1,
        "stage_2": _stage_2,
        "stage_3": _stage_3,
        "continuous_or_discrete": "discrete_count",
        "skewness": None,
        "descriptive_skew_flag": False,
        "power_transform_reviewed": True,
        "primary_power_transform_decision": "not_applicable_discrete_count",
        "decision_reason": (
            f"{col} is a small-integer obstetric-history count (non-negativity + "
            "integerness validated in Section B2b), not a continuous physiological "
            "measurement -- a fixed continuous power transform is not applicable. "
            "Ordinary upper-tail counts are not treated as skew requiring "
            "transformation. This decision does not read target_intrapartum_cs, "
            "event rates, target correlations, coefficients, or model performance."
        ),
        "target_used_for_decision": False,
        "downstream_scaling": "fold_safe_standard_scaler",
    })

transformation_review_df = pd.DataFrame(transformation_review_log)
print(f"B3 pure continuous transformation review: {len(CONTINUOUS_TRANSFORM_REVIEW_COLS)} continuous "
      f"variable(s) + {len(DISCRETE_COUNT_REVIEW_COLS)} discrete count(s) reviewed.")
# Compact reader-facing view (variable, skewness, decision). The full review
# table with the per-variable rationale and stage eligibility is written to
# outputs/data_cleaning/audit/cleaning_b_final_numeric_transformation_review.csv.
print(transformation_review_df[
    ["variable", "continuous_or_discrete", "skewness",
     "descriptive_skew_flag", "primary_power_transform_decision"]
].to_string(index=False))
print()
print("Decision for every reviewed continuous variable: raw_no_fixed_power_transform "
      "(no log/log1p/sqrt/Box-Cox/Yeo-Johnson applied or planned).")
print("Decision for every reviewed discrete count: not_applicable_discrete_count.")
print("target_used_for_decision: False for every row (target-blind by construction).")
print("  Full review table: outputs/data_cleaning/audit/cleaning_b_final_numeric_transformation_review.csv")
assert not any(row["target_used_for_decision"] for row in transformation_review_log), (
    "TARGET-BLINDNESS POSTCONDITION FAILED: B3 must never use the target to justify "
    "a transformation decision."
)
_allowed_decisions = {"raw_no_fixed_power_transform", "not_applicable_discrete_count"}
_bad_decisions = sorted({
    row["primary_power_transform_decision"] for row in transformation_review_log
} - _allowed_decisions)
assert not _bad_decisions, (
    f"UNEXPECTED TRANSFORMATION DECISION(S) FOUND: {_bad_decisions} -- only "
    f"{sorted(_allowed_decisions)} are currently approved."
)
print("Postconditions PASSED: target-blind, no unexpected decision label.")
''')


CLEANING_B_PART3B_CELLS = [
    SB3T_HEADER,
    SB3T_REVIEW,
]


if __name__ == "__main__":
    print(f"Data Cleaning B Part 3b cells defined: {len(CLEANING_B_PART3B_CELLS)}")

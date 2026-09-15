#!/usr/bin/env python3
"""Data Cleaning B -- Part 3 cell definitions (Section B2).

Decision 92 (2026-08-29): this section was renumbered from B4 to B2 when the
notebook's execution order was restructured to
    Setup (B1/B1c) -> Outlier review (B2/B2b) -> Transformation review (B3)
    -> Missingness (B4/B4b/B4c/B4d) -> Representations (B5) -> Plan (B6)
    -> Export (B7)
so that the outlier/extreme-value review -- proven by the prior read-only
dependency audit to have no dependency on missingness (B4-family) or
transformation-review (B3) output -- now runs immediately after Section
B1/B1c. See docs/clinical_decisions/manual_decisions_log.md Decision 92. No
patient-level value, derived column, or audit-CSV content changed as a
result of this renumbering -- only cell position and section labels.

B2 (formerly B4) -- EXTREME-VALUE / DISTRIBUTION AUDIT. DESCRIPTIVE ONLY. TARGET-BLIND.

Final target-blind extreme-value / outlier adjudication and retention policy
(docs/clinical_decisions/manual_decisions_log.md Decision 90, 2026-08-27;
docs/finalization/outlier_extreme_value_handling_closure.md):

  * A value is NEVER removed, set to missing, clipped, capped, winsorized, or
    otherwise modified merely because it is an IQR outlier, statistically
    extreme, highly skewed, or influential. STATISTICALLY EXTREME != INVALID.
  * IQR (1.5x) is a DESCRIPTIVE SCREEN ONLY. It does not establish clinical
    plausibility or data error.
  * Skewness is a DESCRIPTIVE DISTRIBUTION PROPERTY ONLY. It never changes a
    review / plausibility status and is never used (via any
    ``abs(skewness) > threshold`` rule) to declare a value plausible or
    unclear.
  * B2 creates zero new NaNs, performs zero row deletions, and performs zero
    clipping / winsorization / capping.
  * Data-quality validity rules -- deterministic unit normalization,
    malformed/unparseable source tokens, approved source-data corrections,
    documented placeholder meaning, logical/definitional impossibility, and
    subgroup structural-missingness -- are owned by PREPROCESSING
    (``analysis/preprocessing/run_preprocessing.py``), not by B2. Those are
    not "outlier removal".
  * Outcome / target information (``target_intrapartum_cs``, cesarean/vaginal
    event rates, target-rate change with/without an outlier, correlation with
    target, p-values against target, model coefficients, feature importance,
    model performance) is NOT read or used anywhere in this section.

Retired 2026-08-27 (Decision 90):
  * Sections B4c / B4d (section numbers as they existed at that time, before
    the Decision 92 renumbering below) -- the with-vs-without-IQR-outlier
    target-event-rate comparison and the point-biserial-with-target
    diagnostics -- were removed from the Data Cleaning B notebook assembly
    entirely. They read the outcome and therefore did not belong in the
    target-blind cleaning adjudication path (even though they never mutated
    data). Outcome-based outlier-influence / sensitivity analysis, if
    desired, belongs downstream (after cleaning decisions are frozen) and
    must never determine preprocessing eligibility.
  * The B4 (as this section was then numbered) ``PLAUSIBILITY_AUDIT_RANGES``
    / ``IMPOSSIBLE_VALUE_RULES`` mechanism (AGE / BMI_before / height /
    gestational-age broad bounds, none with cited clinical provenance) was
    removed. Preprocessing owns source/data-quality sanity-review gates; this
    section does not maintain a second, independent plausibility-threshold
    system and introduces no replacement cutoffs.

The final per-variable adjudications are static, target-blind KEEP decisions
recorded in ``OUTLIER_FINAL_ADJUDICATION`` below.
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


# ── Section B2 ────────────────────────────────────────────────────────────────
SB4_HEADER = md("clean-b-s02-header", """
## Section B2 — Extreme-Value / Distribution Audit (Descriptive, Target-Blind)

Continuous numeric scope variables are screened descriptively with the 1.5×
IQR rule. **A statistical extreme is not treated as an error.** No value is
removed, set to missing, clipped, winsorized, or capped by this section, and
no row is deleted — regardless of IQR or skewness. Skewness is recorded only
as a descriptive distribution property (`descriptive_skew_flag`); it never
changes a review decision.

Data-quality validity (unit normalization, malformed-token handling, approved
source corrections, definitional/logical impossibility, subgroup
structural-missingness) is owned by **preprocessing**
(`analysis/preprocessing/run_preprocessing.py`), not by this section.

Discrete obstetric counts (`G`, `P`, `LIVE_BIRTH`, `AB`, `CS`) are handled in
Section B2b with logical validation (non-negativity, integerness) rather than
continuous-variable outlier logic. IQR is **not** used as a validity or
removal criterion for them.

Outcome / target information is not read or used anywhere in this section.
Outcome-based outlier-influence or sensitivity analysis, if performed, belongs
downstream after cleaning decisions are frozen — it must never determine
preprocessing eligibility.

This section runs immediately after Section B1/B1c and before the continuous
transformation review (Section B3) and the missingness assessment (Section B4);
none of the three depends on the others' output.

### Final adjudication
Every flagged extreme in the current 431-row cohort was reviewed **target-blind**
for source consistency, mathematical / internal consistency, and physiological
plausibility, and **retained unchanged**. See
`docs/finalization/outlier_extreme_value_handling_closure.md` for the full
per-variable table and evidence. There is **no open outlier-related clinical
dependency**.

| Column | value_mutated | row_removed | created_missingness | target_used_for_decision |
|--------|---------------|-------------|---------------------|--------------------------|
| every column screened here | False | False | False | False |
""")

SB4_SCREEN = code("clean-b-s02-screen", """
# ── B2 descriptive extreme-value screen (target-blind, non-mutating) ─────────
# IQR (1.5x) is a DESCRIPTIVE screen only. Skewness is recorded independently
# as `descriptive_skew_flag` and NEVER changes a decision. This section keeps
# no plausibility-range / impossible-value cutoff system -- preprocessing owns
# data-quality sanity gates. This cell reads no outcome/target column.
SKEW_DESCRIPTIVE_THRESHOLD = 1.5   # |skew| above this -> descriptive_skew_flag only

# Inert constant, frozen at 0 for backward-compatible manifest schema
# (cleaning_b_part5 still emits `values_outside_plausibility_range_flagged_for_review`).
# This section maintains no plausibility range, so nothing can be flagged by one.
n_outside_plausibility_range = 0

# Discrete obstetric-history counts -- screened for descriptive distribution
# summary + logical validation (Section B2b), never continuous-IQR removal.
COUNT_TYPE_SUPPLEMENTARY_OUTLIER_COLS = ["G", "P", "LIVE_BIRTH", "AB", "CS"]

# ── Final target-blind adjudication ─────────────────────────────────────────
# Every entry is a KEEP -- no value modified, no row removed, no missingness
# created. `clinical_dependency_status` is `closed_no_consultation_required`
# for all: reviewed target-blind for source consistency, mathematical
# consistency, and physiological plausibility, with no evidence of data error.
OUTLIER_FINAL_ADJUDICATION = {
    "AGE": (
        "keep_plausible",
        "Valid maternal ages (18 and 46 yr). IQR status reflects this cohort's "
        "age distribution, not a data-quality problem. No Keren question required."
    ),
    "height": (
        "keep_plausible",
        "187 cm is tall but physiologically ordinary. The separate 1.65 -> 165 cm "
        "conversion is a deterministic preprocessing unit normalization, not an "
        "outlier correction. No Keren question required."
    ),
    "weight_before_pregnancy": (
        "keep_internally_consistent",
        "~95-135 kg. BMI_before is reproduced to floating-point precision by "
        "weight_before_pregnancy / (height/100)**2 for every flagged row -- no "
        "kg/lb, decimal-point, or arithmetic error. No Keren question required."
    ),
    "BMI_before": (
        "keep_internally_consistent",
        "~34.9-47.0. Every flagged BMI is mathematically consistent with its own "
        "observed height and pre-pregnancy weight. The observed minimum (~14.2) "
        "is not an IQR outlier. No Keren question required."
    ),
    "weight_in_pregnancy": (
        "keep_internally_consistent",
        "119 kg (1 row). Weight, height, BMI_before, BMI_after and the ~6 kg "
        "gestational weight difference are mutually coherent. No Keren question required."
    ),
    "BMI_after": (
        "keep_internally_consistent",
        "~40.6-41.2. Mathematically consistent with observed pregnancy weight and "
        "height. No BMI_after plausibility cutoff is introduced by this section."
    ),
    "Hb_before_delivery": (
        "keep_plausible",
        "8.77 / 8.96 / 16.07 g/dL -- clinically possible anemia / high-Hb "
        "observations with no evidence of malformed source values or unit error. "
        "The preprocessing <5 / >20 g/dL check is a broad sanity-review threshold, "
        "not proof of physical impossibility."
    ),
    "gestational_age_at_delivery_days": (
        "keep_available_source_consistency_verified",
        "Preterm tail (162-245 days). All raw 'W+D' values parse correctly (W+0 "
        "is valid, e.g. 35+0 -> 245 days). The most extreme preterm record "
        "(23+1 weeks) is internally coherent in the currently available "
        "canonical source (PPROM=1 at 23+1, trial_of_labor_corrected=1). "
        "Additional source-chart "
        "verification could be performed if the original clinical record is later "
        "available, but the current canonical dataset contains no internal "
        "evidence of transcription or parsing error and the record is not "
        "excluded. No open preprocessing blocker; no Keren question required."
    ),
    "endometrioma_size_clean": (
        "keep_parser_source_notation_consistent",
        "IQR extremes 210 / 100 / 100 mm. The parser applies the documented "
        "literal unit interpretation of the source unit marker consistently (the "
        "same notation occurs throughout the dataset, not only in these rows). "
        "Extreme lesion size is not by itself evidence of a source error, and the "
        "values are not reinterpreted merely because they are statistically "
        "extreme. endometrioma_size_clean and the derived endometrioma_size_status "
        "are unchanged. An original ultrasound/chart could provide additional "
        "external confirmation if ever reviewed; this is not an open preprocessing "
        "blocker and not a pending Keren dependency."
    ),
}

_DEFAULT_ADJ = (
    "keep_no_specific_adjudication_needed",
    "Retained unchanged. B2 never mutates a value, removes a row, or creates "
    "missingness, regardless of IQR or skewness."
)


def _b4_row(col, values, screen_type, screening_method, extra=None):
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    n_iqr_outliers = int(((df_clean[col] < lower) | (df_clean[col] > upper)).sum())
    skewness = float(values.skew())
    descriptive_skew_flag = bool(abs(skewness) > SKEW_DESCRIPTIVE_THRESHOLD)  # descriptive ONLY

    if n_iqr_outliers == 0:
        decision, reason = (
            "keep_no_iqr_outlier",
            "No IQR outlier flagged; retained unchanged."
        )
    else:
        decision, reason = OUTLIER_FINAL_ADJUDICATION.get(col, _DEFAULT_ADJ)
    if extra:
        decision, reason = extra(decision, reason, lower, upper, n_iqr_outliers)

    return {
        "column": col,
        "N": int(len(values)),
        "Q1": round(float(q1), 3),
        "Q3": round(float(q3), 3),
        "IQR": round(float(iqr), 3),
        "min": round(float(values.min()), 3),
        "max": round(float(values.max()), 3),
        "iqr_lower": round(float(lower), 3),
        "iqr_upper": round(float(upper), 3),
        "n_iqr_outliers": n_iqr_outliers,
        "iqr_outlier_%": round(n_iqr_outliers / max(len(values), 1) * 100, 1),
        "skewness": round(skewness, 3),
        "descriptive_skew_flag": descriptive_skew_flag,
        "screening_method": screening_method,
        "final_decision": decision,
        "final_reason": reason,
        "clinical_dependency_status": "closed_no_consultation_required",
        "value_mutated": False,
        "row_removed": False,
        "created_missingness": False,
        "target_used_for_decision": False,
        "screen_type": screen_type,
    }


# 1. Continuous numeric scope variables (IQR descriptive screen).
for col in CLEANING_SCOPE:
    if col not in df_clean.columns or infer_var_type(df_clean[col]) != "numeric":
        continue
    values = df_clean[col].dropna()
    if values.empty:
        continue
    outlier_log.append(_b4_row(col, values, "numeric_iqr", "iqr_1p5_descriptive"))

_n_numeric_screened = len(outlier_log)

# 2. Discrete obstetric-history counts. `infer_var_type` classifies these as
# categorical (nunique <= 20), so they fall outside loop 1 -- included here for
# distribution-summary completeness. IQR is reported but is NOT a validity or
# removal criterion for a discrete count (Section B2b applies the logical
# checks). `CS` is zero-inflated: Q1 = median = Q3 = 0, so its IQR bounds
# collapse to a single point and the IQR method is not meaningful.
for col in COUNT_TYPE_SUPPLEMENTARY_OUTLIER_COLS:
    if col not in df_clean.columns or col not in CLEANING_SCOPE:
        continue
    if any(row["column"] == col for row in outlier_log):
        continue
    values = df_clean[col].dropna()
    if values.empty:
        continue

    def _count_extra(decision, reason, lower, upper, n_iqr, _col=col):
        degenerate = bool(lower == upper)
        if degenerate:
            return (
                "keep_count_iqr_not_meaningful_zero_inflated",
                f"{_col}: zero-inflated discrete count (Q1 = median = Q3 = 0). IQR "
                "bounds collapse to a single value, so the IQR method is not "
                "meaningful here; values of 1 or 2 are ordinary, not statistical "
                "outliers. Retained unchanged. Logical validation (non-negativity, "
                "integerness) is in Section B2b."
            )
        return (
            "keep_count_logical_checks_only",
            f"{_col}: discrete obstetric-history count. IQR is descriptive only and "
            "is not used as a validity or removal criterion; ordinary upper-tail "
            "counts are not errors. Retained unchanged. Logical validation "
            "(non-negativity, integerness) is in Section B2b."
        )

    outlier_log.append(
        _b4_row(col, values, "count_supplementary_iqr",
                "count_distribution_descriptive", extra=_count_extra)
    )

outlier_df = pd.DataFrame(outlier_log) if outlier_log else pd.DataFrame()
if len(outlier_df):
    outlier_df = outlier_df.sort_values("iqr_outlier_%", ascending=False)

print(f"B2 descriptive extreme-value screen: {len(outlier_log)} scope columns "
      f"({_n_numeric_screened} continuous numeric + "
      f"{len(outlier_log) - _n_numeric_screened} discrete count).")
print()
print("Values modified / set missing / clipped / winsorized by B2: 0 (always).")
print("Rows removed by B2: 0 (always).  Target column read by B2: never.")
print(f"Descriptive high-skew flags (audit-only, no decision effect): "
      f"{[r['column'] for r in outlier_log if r['descriptive_skew_flag']]}")
# Compact reader-facing view: only columns that carry an IQR-flagged extreme,
# with their target-blind KEEP adjudication. The full per-column screen (Q1/Q3/
# IQR bounds, min/max, skewness for every scope numeric) is written unchanged
# to outputs/data_cleaning/audit/cleaning_b_outlier_handling.csv.
_flagged = outlier_df[outlier_df["n_iqr_outliers"] > 0] if len(outlier_df) else outlier_df
print()
if len(_flagged):
    print(f"Columns with an IQR-flagged extreme ({len(_flagged)} of {len(outlier_log)}); "
          "all retained unchanged:")
    print(_flagged[["column", "n_iqr_outliers", "final_decision"]].to_string(index=False))
else:
    print("No column carries an IQR-flagged extreme.")
print("  Full per-column screen: outputs/data_cleaning/audit/cleaning_b_outlier_handling.csv")
print("All flagged extremes: KEEP (target-blind). See "
      "docs/finalization/outlier_extreme_value_handling_closure.md.")
""")


SB4B_HEADER = md("clean-b-s02b-header", """
## Section B2b — Discrete Count Variables: Logical Validation

`G`, `P`, `LIVE_BIRTH`, `AB`, `CS` are discrete obstetric-history **counts**,
not continuous physiological measurements. IQR is reported for them in
Section B2 for distribution-summary completeness only; **it is not used as a
plausibility, validity, or removal criterion**. Observed upper values such as
`G = 10`, `P = 5`, `LIVE_BIRTH = 5`, `AB = 4`, `CS = 2` are ordinary
distribution-tail values, not data errors.

- `G`, `P`, `LIVE_BIRTH`, `AB`: right-skewed small-integer counts with a large
  zero/one mass. IQR flags the clinically ordinary upper tail, not an error.
- `CS`: zero-inflated (Q1 = median = Q3 = 0). IQR bounds collapse to a single
  value, so the IQR method is not meaningful; `CS = 1` or `2` (prior
  cesareans) are not statistical outliers. `S_P_CS` (binary prior-CS status)
  is a separate variable and is not merged with `CS`.

**Zero is valid** for every one of these five variables (nulliparous, no prior
CS, etc.) — never treated as missing or as an error.

Only the two constraints that are **universally true for a count by
definition** are validated: non-negativity and integerness. No stronger
cross-variable ordering (e.g. `LIVE_BIRTH <= P`, or `P + AB <= G`) is applied:
no authoritative project source (preprocessing decision, clinical-decision
log, or data dictionary) defines such an identity for this dataset's coding
scheme, and inventing one is out of scope. Rows where `LIVE_BIRTH > P` appear
are **not** labelled errors here; if a formal coding definition is received
later it can be evaluated then. This section changes no value.
""")

SB4B_COUNT_VALIDATION = code("clean-b-s02b-count-validation", """
# Logical (non-statistical) validation for discrete count scope variables.
# Two universally-true-by-definition constraints only: non-negativity and
# integerness (every non-null value is a whole number 0, 1, 2, ... -- not -1,
# not 1.5). Neither is an "outlier" rule. A stronger cross-variable ordering
# constraint is NOT applied (see the B2b markdown for why). Violations are
# asserted for review only -- values are never auto-corrected here.
_count_cols_for_validation = [c for c in COUNT_TYPE_SUPPLEMENTARY_OUTLIER_COLS
                              if c in df_clean.columns]
_negative_value_rows = {}
_non_integer_value_rows = {}
for col in _count_cols_for_validation:
    _observed = df_clean[col].dropna()
    _n_neg = int((df_clean[col] < 0).sum())
    if _n_neg > 0:
        _negative_value_rows[col] = _n_neg
    _n_non_int = int((_observed != _observed.round()).sum())
    if _n_non_int > 0:
        _non_integer_value_rows[col] = _n_non_int

print("Discrete count logical validation (non-negativity + integerness only; "
      "IQR is not a validity/removal criterion for these variables):")
for col in _count_cols_for_validation:
    _n_neg = _negative_value_rows.get(col, 0)
    _n_non_int = _non_integer_value_rows.get(col, 0)
    print(f"  {col}: negative = {_n_neg} ({'FAIL' if _n_neg else 'pass'}); "
          f"non-integer = {_n_non_int} ({'FAIL' if _n_non_int else 'pass'})")

assert not _negative_value_rows, (
    f"COUNT VALIDATION FAILED: negative value(s): {_negative_value_rows}"
)
assert not _non_integer_value_rows, (
    f"COUNT VALIDATION FAILED: non-integer value(s): {_non_integer_value_rows}"
)
print()
print("All discrete count scope variables are non-negative and integer-valued. "
      "No logical violation; no value changed.")
""")


CLEANING_B_PART3_CELLS = [
    SB4_HEADER,
    SB4_SCREEN,
    SB4B_HEADER,
    SB4B_COUNT_VALIDATION,
]


if __name__ == "__main__":
    print(f"Data Cleaning B Part 3 cells defined: {len(CLEANING_B_PART3_CELLS)}")

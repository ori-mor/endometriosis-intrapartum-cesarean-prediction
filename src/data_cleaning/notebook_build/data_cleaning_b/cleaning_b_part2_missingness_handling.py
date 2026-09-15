#!/usr/bin/env python3
"""Data Cleaning B — Part 2 cell definitions (sections B4–B4d).

Decision 92 (2026-08-29): this file's sections were renumbered when the
notebook's execution order was restructured to
    Setup (B1/B1c) -> Outlier review (B2/B2b) -> Transformation review (B3)
    -> Missingness (B4/B4b/B4c/B4d) -> Representations (B5) -> Plan (B6)
    -> Export (B7)
so that missingness assessment now runs after the outlier review and the
pure continuous transformation review, both of which were proven by the
prior read-only dependency audit to have no dependency on this section's
output. This file's own historical section names were B2 (missingness
handling), B2c (row-specific applicability breakdown), B2b (broad
missingness heatmap review), and B3 (missingness-mechanism screen) -- now
renumbered B4, B4b, B4c, and B4d respectively. See
docs/clinical_decisions/manual_decisions_log.md Decision 92. No patient-level
value, derived column, or audit-CSV content changed as a result of this
renumbering -- only cell position and section labels. The Python variable
names in this file (SB2_*, SB2C_*, SB2B_*, SB3_*) intentionally keep their
historical names for stability (existing tests reference them by name); only
each cell's visible `id` string and markdown section-label text changed.

B4 (formerly B2) — Missingness handling: row-level flags, column-level
    decisions, indicators.
B4d (formerly B3) — Missingness-mechanism screen: KS/chi-square/Fisher
    against a defensible reference set of observed variables, BH-FDR
    corrected, for manual review.

All work is applied to df_clean (a copy). df remains read-only. Row-exclusion
capability was removed entirely (2026-08-25) -- no row is ever deleted here,
regardless of the retired/inert APPLY_ROW_EXCLUSIONS flag's value; row-level
missingness is flag/audit only, unconditionally. B-created columns are
recorded in feature_dictionary for downstream controlled validation in EDA C.
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


# ── Section B4 ─────────────────────────────────────────────────────────────────
SB2_HEADER = md("clean-b-s04-header", """
## Section B4 — Missingness Handling

### Row-level
Rows with more than `ROW_MISSING_FLAG_FRACTION` (50%) missing **within the
cleaning scope** are flagged. This is **flag / audit only** — Data Cleaning B
has no code path that deletes a row. The cleaning scope mixes Stage 1/2/3
variables, so a row-drop keyed off this mixed-horizon denominator could let
later-horizon missingness silently alter the cohort used for an earlier-horizon
model; the descriptive flag is kept, the deletion capability is not.
Patient-level row flags are written to
`cleaning_b_row_actions_patient_level.csv` (gitignored) — never printed at
patient level here.

### Column-level

| Missingness | Recommendation |
|-------------|----------------|
| ≥ 70% | flag / document for audit only; the source column is **retained** in the cleaned analytical export; no automatic derived predictor |
| 40–70% | audit tier only — flagged for variable-specific representation review; no automatic categorical / unknown conversion or missingness indicator is created solely for crossing this band |
| < 40% | assess missingness mechanism (Section B4d) where feasible |

Crossing a missingness threshold is never, by itself, a reason to delete a
column from the export or to create a categorical / derived predictor. Model
eligibility and the representation of a high-missingness variable are decided
explicitly, downstream (EDA C / modeling).

**Three treatments of NaN, kept distinct:**

1. **Confirmed structural NaN** — a documented, code-enforced subgroup gate
   exists in preprocessing (e.g. the `endo_resection_*` family, gated on
   `endometriosis_surgery`). NaN is expected by design and is not ordinary
   random missingness.
2. **Row-specific applicability gated** — `gestational_age_at_PPROM_days`,
   `indication_for_induction_clean`, and `adenomyosis_sonographic_features_clean`
   (`ROW_APPLICABILITY_GATES`, Section B1). No code-enforced preprocessing gate
   exists, but each variable's row-level applicability is empirically confirmed
   against the current cohort — zero rows are inconsistent with the registered
   gate column (`PPROM`, `induction_any_bin`, `adenomyosis` respectively; see
   Section B4b). Rows where the gate condition fails are excluded from the
   missingness denominator entirely; rows where it holds are assessed for
   genuine missingness on their own.
3. **Ordinary missingness** — assessed against the whole-cohort denominator.

**Genuine missing within the applicable subset (variable-specific):**
- `adenomyosis_sonographic_features_clean`: `adenomyosis == 1` (applicable) =
  169, `adenomyosis == 0` (structural) = 262; of the 169 applicable rows, 130
  have an observed sonographic feature and 39 are genuinely missing
  (whole-cohort 69.8%, applicable-subset 23.1%). Those 39 rows are represented
  explicitly by the derived multi-hot family — `adenomyosis_feature_1` …
  `adenomyosis_feature_11` plus `adenomyosis_features_unknown` (Section B5f).
- `gestational_age_at_PPROM_days` (1 genuinely missing of 17 applicable) and
  `indication_for_induction_clean` (4 of 194) are preserved as true missing and
  handled by their own downstream rules (Section B6).

For rows with `endometriosis_surgery == 0`, missing `endo_resection_*` values
are consistent with "not applicable — no prior endometriosis surgery."
`endo_surgery_adhesiolysis` alone should not be used to infer prior
endometriosis surgery or resection history; any future conditional recoding
requires clinical / statistical approval.

### Indicators
A binary missingness indicator `<col>__missing_ind` is **never** created
automatically for falling in a missingness band, or for being
confirmed-structural with genuine missingness. Every indicator must trace to an
explicit, variable-specific allowlist:
`APPROVED_VARIABLE_SPECIFIC_INDICATOR_COLS` (ordinary columns) or
`APPROVED_STRUCTURAL_INDICATOR_COLS` (confirmed-structural columns). **Both are
currently empty** — every current structural column with genuine missingness
already carries that information in an explicit derived status instead (e.g.
`endometrioma_size_status`), and `weight_in_pregnancy`'s missingness is carried
by the `not_documented` bucket of its fold-safe `weight_in_pregnancy_cat`
representation. A postcondition after the missingness loop enforces that every
created indicator is a member of one of the two allowlists; each created
indicator is recorded in `feature_dictionary` with full metadata.
""")

SB2_ROW = code("clean-b-s04-row", """
# ── Row-level missingness within cleaning scope (fully applicability-aware) ──
# The missingness denominator is built PER ROW. A variable that is not
# applicable to a given row (e.g. gestational_age_at_PPROM_days when PPROM==0)
# does not count in that row's denominator at all -- it does not apply. When
# the variable IS applicable to a row and still NaN, that genuinely is missing
# and counts. This applies uniformly across BOTH applicability tiers -- a
# single whole-column include/exclude decision cannot express per-row
# applicability, and would otherwise discard genuine within-applicable-subgroup
# missingness (e.g. endometrioma==1 rows with genuinely undocumented size):
#   - ROW_APPLICABILITY_GATES (Part 1) for the 3 registered row-specific-gated
#     variables (gestational_age_at_PPROM_days, indication_for_induction_clean,
#     adenomyosis_sonographic_features_clean)
#   - the confirmed-structural variables active at this point
#     (STRUCTURAL_NAN_COLS, after the Section B1c recode has removed the 10
#     endo_resection_* columns), gated via the public
#     structural_missingness_registry.structural_subgroup_gates() API -- the
#     same shared registry A1/A2 use.
# Every other scope column is "always applicable" (ordinary variables).
_structural_gates_public = structural_missingness_registry.structural_subgroup_gates()
_structural_row_gates = {
    _c: {"gate_column": _gc, "applicable_value": _gv}
    for _c, (_gc, _gv) in _structural_gates_public.items()
    if _c in STRUCTURAL_NAN_COLS
}
_all_row_applicability_gates = {**ROW_APPLICABILITY_GATES, **_structural_row_gates}


def _full_row_applicability_mask(df_source, col):
    _gate = _all_row_applicability_gates.get(col)
    if _gate is None:
        return pd.Series(True, index=df_source.index)
    return df_source[_gate["gate_column"]] == _gate["applicable_value"]


_scope_for_rows = list(CLEANING_SCOPE)
_applicability_mask = pd.DataFrame(
    {c: _full_row_applicability_mask(df_clean, c) for c in _scope_for_rows},
    index=df_clean.index,
)
_is_missing = df_clean[_scope_for_rows].isna()
_applicable_and_missing = _is_missing & _applicability_mask
_n_applicable_per_row = _applicability_mask.sum(axis=1)
_row_missing_frac = _applicable_and_missing.sum(axis=1) / _n_applicable_per_row
_row_flag = _row_missing_frac > ROW_MISSING_FLAG_FRACTION

for idx in df_clean.index:
    row_actions.append({
        "row_index": int(idx),
        "n_applicable_cols": int(_n_applicable_per_row.loc[idx]),
        "scope_missing_fraction": round(float(_row_missing_frac.loc[idx]), 4),
        "flagged_high_missing": bool(_row_flag.loc[idx]),
        # Always "flag_only": Data Cleaning B has no code path that deletes a
        # row, so a conditional label here would be misleading.
        "action": "flag_only",
    })

_n_flagged = int(_row_flag.sum())
print(f"Row-level missingness (scope: {len(_scope_for_rows)} cols, "
      "fully applicability-aware denominator -- structural and row-gated "
      "columns are gated per row, not blanket-excluded)")
print(f"  Rows flagged >{int(ROW_MISSING_FLAG_FRACTION*100)}% missing: {_n_flagged} "
      f"({round(_n_flagged / len(df_clean) * 100, 1)}%)")
for thr in [0.10, 0.25, 0.50]:
    _n = int((_row_missing_frac > thr).sum())
    print(f"  Rows > {int(thr*100)}% missing: {_n}")

# ── Row-level missingness is flag / audit only ─────────────────────────────
# Data Cleaning B has no code path that deletes a row. CLEANING_SCOPE mixes
# Stage 1/2/3 variables, so a row-drop keyed off this mixed-horizon
# denominator could let later-horizon missingness silently alter the cohort
# used for an earlier-horizon model. The descriptive row-level audit above is
# kept as a useful diagnostic.
print("  No rows dropped -- row-level missingness is flag / audit only.")
ROW_EXCLUSIONS_APPLIED = False
ROWS_AFTER_CLEANING = len(df_clean)
""")

SB2_COLUMN = code("clean-b-s04-column", """
# ── Column-level missingness decisions ────────────────────────────────────────
INDICATOR_SUFFIX = "__missing_ind"
created_indicator_cols = []
SUPPRESSED_MISSING_INDICATOR_COLS = {
    # BMI_after: kept suppressed. Its missingness is carried by the
    # not_documented bucket of the fold-safe BMI_after_cat representation
    # (Section B5b), so a separate raw-column indicator would be redundant.
    # Listed explicitly (rather than relying on the 40-70% tier default) so a
    # future tier-default change cannot silently start indicating it.
    "BMI_after",
    # endometrioma_size_status already represents structural no-endometrioma
    # and endometrioma-present-unknown-size directly.
    "endometrioma_size_clean",
    # endometrioma_presence_laterality already represents genuinely unresolved
    # endometrioma==1 laterality as the explicit `laterality_unknown` category
    # (0 missing), so a standalone __missing_ind for the raw detail columns has
    # nothing left to describe.
    "endometrioma_place_clean",
    "endometrioma_laterality",
    # gestational_age_at_PPROM_days is row-specific applicability gated on PPROM
    # (ROW_APPLICABILITY_GATES); a raw indicator would mostly re-encode
    # "PPROM==0", not genuine documentation gaps.
    "gestational_age_at_PPROM_days",
    # endo_surgery_adhesiolysis missingness is structural when there was no
    # prior endometriosis surgery; represented by
    # derived_endo_surgery_adhesion_status (Section B5g). Raw column dropped
    # from the export.
    "endo_surgery_adhesiolysis",
    # indication_for_induction_clean is row-specific applicability gated on
    # induction_any_bin; a raw indicator would mostly re-encode
    # "induction_any_bin==0". Represented by indication_for_induction_status
    # (Section B5h); raw column dropped from the export.
    "indication_for_induction_clean",
}

# ── Explicit, variable-specific approved missingness indicators ──────────────
# Crossing the 40-70% missingness band never creates an indicator
# automatically -- a column must be named in this allowlist to receive one.
# Currently empty. (weight_in_pregnancy's missingness is carried by the
# not_documented bucket of its fold-safe weight_in_pregnancy_cat
# representation, so it needs no standalone indicator.) The allowlist mechanism
# remains available for a future explicitly-approved column.
APPROVED_VARIABLE_SPECIFIC_INDICATOR_COLS = set()

# ── Closed variable-specific missingness-treatment contracts ─────────────────
# These five variables' Data Cleaning B treatment is already finally decided
# (docs/clinical_decisions/manual_decisions_log.md; CLAUDE.md) -- the generic
# tier-based `recommendation` computed below is a fallback for columns
# without a closed contract, not a description of what actually happens to
# these five. Overriding `recommendation` text only (never `tier` or
# `make_indicator`) is audit-metadata/wording alignment only -- it changes no
# imputation method, no indicator, and no patient-level value.
CLOSED_VARIABLE_SPECIFIC_MISSINGNESS_RECOMMENDATIONS = {
    "weight_before_pregnancy": (
        "direct numeric — approved median imputation, fitted within the "
        "training fold only"
    ),
    "height": (
        "direct numeric — approved median imputation, fitted within the "
        "training fold only"
    ),
    "Hb_before_delivery": (
        "direct numeric — approved median imputation, fitted within the "
        "training fold only"
    ),
    "weight_in_pregnancy": (
        "CLOSED representation — fold-safe observed-value tertiles "
        "(weight_in_pregnancy_cat: low_observed/mid_observed/high_observed) "
        "plus not_documented, cutpoints fitted training-fold-only; no "
        "imputation is performed in Data Cleaning B"
    ),
    "BMI_after": (
        "CLOSED representation — fold-safe observed-value tertiles "
        "(BMI_after_cat: low_observed/mid_observed/high_observed) plus "
        "not_documented, cutpoints fitted training-fold-only; no imputation "
        "is performed in Data Cleaning B"
    ),
}

# ── Explicit, variable-specific approved STRUCTURAL indicators ───────────────
# A confirmed-structural column's genuine missingness never automatically
# receives an indicator merely for being structural-and-missing -- a column
# must be named here. Currently empty: every current structural column with
# genuine missingness already carries that information in an explicit derived
# status (see SUPPRESSED_MISSING_INDICATOR_COLS above).
APPROVED_STRUCTURAL_INDICATOR_COLS = set()

# ── Applicability-aware reporting fields ────────────────────────────────────
# Raw whole-cohort missing_% alone does not distinguish structural
# non-applicability from genuine documentation gaps. These fields expose both
# concepts side by side for every scope column, without replacing the raw
# missing_% / tier / indicator logic below. Uses the same unified gate lookup
# as the row-level cell (public
# structural_missingness_registry.structural_subgroup_gates() API), so both
# cells agree on which columns are gated. Structural non-applicability is not a
# data-quality failure; genuine missingness is evaluated only among applicable
# records. No missingness mechanism is labeled MNAR here -- these are observed
# counts, not a claim
# about mechanism.
_structural_gates_public_report = structural_missingness_registry.structural_subgroup_gates()
_structural_applicability_gates_report = {
    _c: {"gate_column": _gc, "applicable_value": _gv}
    for _c, (_gc, _gv) in _structural_gates_public_report.items()
    if _c in STRUCTURAL_NAN_COLS
}


def _applicability_breakdown(col):
    _raw_n = int(df_clean[col].isna().sum())
    _raw_pct = round(float(df_clean[col].isna().mean() * 100), 1)
    _gate = ROW_APPLICABILITY_GATES.get(col) or _structural_applicability_gates_report.get(col)
    if _gate is not None:
        _app_mask = df_clean[_gate["gate_column"]] == _gate["applicable_value"]
        _applicable_n = int(_app_mask.sum())
        _genuine_missing_n = int((_app_mask & df_clean[col].isna()).sum())
    else:
        _applicable_n = len(df_clean)
        _genuine_missing_n = _raw_n
    _genuine_missing_pct = (
        round(_genuine_missing_n / _applicable_n * 100, 1) if _applicable_n else None
    )
    return _raw_n, _raw_pct, _applicable_n, _genuine_missing_n, _genuine_missing_pct


for col in CLEANING_SCOPE:
    if col not in df_clean.columns:
        continue
    raw_miss_pct = float(df_clean[col].isna().mean() * 100)
    miss_pct = raw_miss_pct
    is_structural = col in STRUCTURAL_NAN_COLS
    is_row_gated = col in ROW_APPLICABILITY_GATES
    var_type = infer_var_type(df_clean[col])
    row_gated_applicable_pct = None
    (
        _raw_full_cohort_missing_n, _raw_full_cohort_missing_pct,
        _applicable_n_report, _genuine_missing_within_applicable_n,
        _genuine_missing_within_applicable_pct,
    ) = _applicability_breakdown(col)

    if is_row_gated and not is_structural:
        # Row-specific applicability gate: tier/recommendation must be driven
        # by the applicable-subset missingness %, never the raw whole-cohort
        # % (the raw % is dominated by rows where the variable simply does
        # not apply). Both are still recorded below for transparency.
        _gate = ROW_APPLICABILITY_GATES[col]
        _applicable_mask_col = df_clean[_gate["gate_column"]] == _gate["applicable_value"]
        _n_applicable = int(_applicable_mask_col.sum())
        _n_applicable_missing = int((_applicable_mask_col & df_clean[col].isna()).sum())
        row_gated_applicable_pct = round(
            _n_applicable_missing / _n_applicable * 100, 1
        ) if _n_applicable else 0.0
        miss_pct = row_gated_applicable_pct
        tier = (
            ">=70%" if miss_pct >= COL_MISSING_HIGH * 100
            else "40-70%" if miss_pct >= COL_MISSING_MID * 100
            else "<40%" if miss_pct > 0
            else "0%"
        )
        # Generic wording shared by every registered row-applicability-gated
        # column: each variable's specific residual-missingness treatment is
        # documented on its own terms in Section B4's header and Section B6.
        recommendation = (
            f"row_specific_applicability_gate(gate={_gate['gate_column']}=="
            f"{_gate['applicable_value']}): not applicable when gate condition "
            "fails (excluded from the missingness denominator entirely, never "
            "indicated or imputed); genuine missingness is assessed only among "
            "applicable rows; no automatic indicator or CV imputation is created "
            "here -- this variable's specific representation/handling is "
            "documented separately (see Section B6)"
        )
        make_indicator = False
    elif is_structural:
        tier = "structural"
        # Gated on the explicit APPROVED_STRUCTURAL_INDICATOR_COLS allowlist
        # (currently empty), not on "structural AND missing".
        make_indicator = miss_pct > 0 and col in APPROVED_STRUCTURAL_INDICATOR_COLS
        if make_indicator:
            recommendation = "subgroup-aware; keep NaN meaningful; explicit variable-specific approved indicator"
        elif miss_pct == 0:
            recommendation = "subgroup-aware; no missing values in current cohort; indicator skipped"
        elif col in SUPPRESSED_MISSING_INDICATOR_COLS:
            recommendation = "subgroup-aware; missingness represented by explicit derived status; indicator retired"
        else:
            recommendation = "subgroup-aware; no approved variable-specific indicator for this column"
    elif miss_pct >= COL_MISSING_HIGH * 100:
        tier = ">=70%"
        # High-missingness policy: an ordinary non-structural variable with
        # >=70% missingness is flagged / documented for audit only. It is
        # never automatically removed from the export, and no indicator /
        # not_documented category / derived predictor is created for it
        # automatically -- each requires an explicit variable-specific decision.
        recommendation = "flag_for_audit_high_missingness_source_retained_no_automatic_derived_representation"
        make_indicator = False
    elif col in SUPPRESSED_MISSING_INDICATOR_COLS and miss_pct > 0:
        tier = "40-70%" if miss_pct >= COL_MISSING_MID * 100 else "<40%"
        recommendation = "missingness represented by linked/family indicator; indicator retired"
        make_indicator = False
    elif col in APPROVED_VARIABLE_SPECIFIC_INDICATOR_COLS and miss_pct > 0:
        # Explicit, variable-specific approved indicator (not a side effect of
        # the generic 40-70% band). The allowlist is currently empty, so this
        # branch does not fire for any column; the mechanism remains available
        # for a future explicitly-approved column.
        tier = "40-70%" if miss_pct >= COL_MISSING_MID * 100 else "<40%"
        recommendation = "approved_variable_specific_missingness_indicator"
        make_indicator = True
    elif miss_pct >= COL_MISSING_MID * 100:
        # 40-70% is an audit tier only, not an automatic feature-engineering
        # rule -- crossing this band alone creates no indicator and no
        # categorical / unknown conversion. Any representation for a specific
        # variable requires its own explicit decision.
        tier = "40-70%"
        recommendation = "variable_specific_representation_review"
        make_indicator = False
    elif miss_pct > 0:
        tier = "<40%"
        recommendation = "assess_mechanism_then_impute_in_cv"
        make_indicator = False
    else:
        tier = "0%"
        recommendation = "none"
        make_indicator = False

    # Closed-contract override: wording only -- never changes tier or
    # make_indicator (already correctly False for all five closed variables
    # under the generic logic above).
    if col in CLOSED_VARIABLE_SPECIFIC_MISSINGNESS_RECOMMENDATIONS:
        recommendation = CLOSED_VARIABLE_SPECIFIC_MISSINGNESS_RECOMMENDATIONS[col]

    indicator_name = ""
    if make_indicator:
        indicator_name = f"{col}{INDICATOR_SUFFIX}"
        df_clean[indicator_name] = df_clean[col].isna().astype(int)
        created_indicator_cols.append(indicator_name)
        feature_dictionary.append(new_feature_dictionary_entry(
            new_column=indicator_name,
            source_column=col,
            creation_rule="binary indicator: 1 if source is NaN else 0",
            timing="same_as_source",
            leakage_status="no",
            intended_use="review" if tier == "structural" else "secondary",
            creation_section="B4",
        ))

    missingness_log.append({
        "column": col,
        "type": var_type,
        "missing_%": round(miss_pct, 1),
        "raw_missing_pct_whole_cohort": round(raw_miss_pct, 1) if is_row_gated else None,
        "structural_nan": is_structural,
        "row_specific_applicability_gated": is_row_gated,
        "tier": tier,
        "recommendation": recommendation,
        "indicator_created": indicator_name if indicator_name else "",
        # Applicability-aware breakdown: raw whole-cohort vs.
        # genuine within-applicable-subgroup missingness, side by side, for
        # every scope column -- see _applicability_breakdown() above.
        "raw_full_cohort_missing_n": _raw_full_cohort_missing_n,
        "raw_full_cohort_missing_pct": _raw_full_cohort_missing_pct,
        "applicable_n": _applicable_n_report,
        "genuine_missing_within_applicable_n": _genuine_missing_within_applicable_n,
        "genuine_missing_within_applicable_pct": _genuine_missing_within_applicable_pct,
    })
    column_actions_log.append({
        "column": col,
        "stage": "B4_missingness",
        "action": recommendation,
        "detail": (
            f"applicable_subset_missing={round(miss_pct,1)}% "
            f"(raw_whole_cohort={round(raw_miss_pct,1)}%) tier={tier}"
            if is_row_gated else f"missing={round(miss_pct,1)}% tier={tier}"
        ) + (f"; +{indicator_name}" if indicator_name else ""),
    })

# ── Postcondition: every created indicator must trace to an allowlist ────────
# Every created indicator must be a member of one of the two explicit
# allowlists above -- no percentage tier or structural classification may
# create one on its own. This is a subset check (created ⊆ approved): a
# partial/synthetic CLEANING_SCOPE (e.g. in isolated tests) need not contain
# every approved column; only an indicator NOT on either allowlist is a
# failure. In the full-scope run both allowlists are currently empty, so no
# indicator column is created by this section.
_approved_indicator_cols = {
    f"{c}{INDICATOR_SUFFIX}" for c in
    (APPROVED_VARIABLE_SPECIFIC_INDICATOR_COLS | APPROVED_STRUCTURAL_INDICATOR_COLS)
}
_actual_indicator_cols = sorted(created_indicator_cols)
_unapproved_indicator_cols = sorted(set(_actual_indicator_cols) - _approved_indicator_cols)
if _unapproved_indicator_cols:
    raise AssertionError(
        "MISSINGNESS-INDICATOR ALLOWLIST POSTCONDITION FAILED: indicator(s) "
        f"{_unapproved_indicator_cols} were created without explicit "
        f"variable-specific approval (approved allowlist: "
        f"{sorted(_approved_indicator_cols)}); re-audit before proceeding."
    )
print(f"Missingness-indicator allowlist postcondition PASSED: "
      f"created_indicator_cols == {_actual_indicator_cols} "
      "(every indicator traces to an explicit variable-specific approval).")

missingness_df = pd.DataFrame(missingness_log).sort_values(
    ["structural_nan", "missing_%"], ascending=[False, False])
print(f"Column-level missingness decisions ({len(missingness_log)} scope columns):")
print("  Tier distribution:", missingness_df["tier"].value_counts().to_dict())
# Compact reader-facing view: only columns that carry any NaN, with their tier
# and recommendation. The full per-column log (raw whole-cohort vs. genuine
# applicable-subgroup missingness for every scope column) is written to
# outputs/data_cleaning/audit/cleaning_b_missingness_handling.csv.
_missing_rows = missingness_df[missingness_df["missing_%"] > 0]
print(f"\\n  Columns with missingness ({len(_missing_rows)} of {len(missingness_log)}):")
if len(_missing_rows):
    print(_missing_rows[["column", "structural_nan", "row_specific_applicability_gated",
                         "missing_%", "tier", "indicator_created"]].to_string(index=False))
else:
    print("    (none)")
print("  Full per-column missingness log: "
      "outputs/data_cleaning/audit/cleaning_b_missingness_handling.csv")
print(f"\\nMissingness indicators created: {len(created_indicator_cols)}")

# ── Explicit raw-vs-genuine callout for gated columns ─────────────────────────
# The wide table above already carries both figures for every column; this
# callout exists so a reader does not have to infer the distinction from the
# raw missing_% alone. Structural non-applicability is not a data-quality
# failure -- it means the variable does not apply to that patient (e.g. no
# endometrioma, no prior endometriosis surgery). Genuine missingness is
# evaluated only among applicable records.
_gated_cols_report = [
    r for r in missingness_log
    if r["structural_nan"] or r["row_specific_applicability_gated"]
]
if _gated_cols_report:
    print("\\nRaw whole-cohort vs. genuine applicable-subgroup missingness "
          "(structural + row-specific-gated columns):")
    for _r in _gated_cols_report:
        print(f"  {_r['column']}: raw_full_cohort={_r['raw_full_cohort_missing_n']}/"
              f"{len(df_clean)} ({_r['raw_full_cohort_missing_pct']}%) | "
              f"genuine_within_applicable={_r['genuine_missing_within_applicable_n']}/"
              f"{_r['applicable_n']} ({_r['genuine_missing_within_applicable_pct']}%)")
""")


# ── Section B4b ────────────────────────────────────────────────────────────────
SB2C_HEADER = md("clean-b-s04b-header", """
## Section B4b — Row-Specific Applicability Breakdown

Every registered row-applicability-gated variable (`ROW_APPLICABILITY_GATES`,
Section B1 -- currently 3: `gestational_age_at_PPROM_days`,
`indication_for_induction_clean`, `adenomyosis_sonographic_features_clean`)
is neither whole-column structural nor whole-column ordinary missingness.
Applicability is determined **per row** from an explicit event-status
variable already in the dataset (`PPROM`, `induction_any_bin`, `adenomyosis`
respectively), verified directly against the current cohort before
implementation: zero rows are inconsistent with any registered gate (no
`PPROM==0` row has an observed gestational-age value; no
`induction_any_bin==0` row has a documented indication; no `adenomyosis==0`
row has an observed sonographic-feature value). This section reports the
three-way row-level breakdown for each registered variable -- structural/
not-applicable, applicable-and-observed, applicable-and-genuinely-missing --
instead of a single raw missingness percentage, which is what Sections
B4d/B6 below act on.
""")

SB2C_APPLICABILITY = code("clean-b-s04b-applicability", """
_applicability_rows = []
for col, gate in ROW_APPLICABILITY_GATES.items():
    if col not in df_clean.columns:
        continue
    gate_col = gate["gate_column"]
    applicable = df_clean[gate_col] == gate["applicable_value"]
    not_applicable = ~applicable
    is_missing = df_clean[col].isna()

    n_not_applicable = int(not_applicable.sum())
    n_not_applicable_but_observed = int((not_applicable & df_clean[col].notna()).sum())
    n_applicable = int(applicable.sum())
    n_applicable_observed = int((applicable & df_clean[col].notna()).sum())
    n_applicable_missing = int((applicable & is_missing).sum())

    if n_not_applicable_but_observed != 0:
        raise AssertionError(
            f"{col} APPLICABILITY POSTCONDITION FAILED: {n_not_applicable_but_observed} "
            f"row(s) have {gate_col} != {gate['applicable_value']} (not applicable) but "
            f"an observed {col} value -- gate is not clean; re-audit before proceeding."
        )

    raw_missing_pct = round(float(is_missing.mean() * 100), 1)
    applicable_missing_pct = (
        round(n_applicable_missing / n_applicable * 100, 1) if n_applicable else None
    )

    _applicability_rows.append({
        "column": col,
        "gate_column": gate_col,
        "structural_not_applicable_n": n_not_applicable,
        "applicable_n": n_applicable,
        "applicable_observed_n": n_applicable_observed,
        "applicable_missing_n": n_applicable_missing,
        "raw_missing_pct_whole_cohort": raw_missing_pct,
        "applicable_missing_pct": applicable_missing_pct,
    })

applicability_df = pd.DataFrame(_applicability_rows)
print("Row-specific applicability breakdown (verified against the current data, not assumed):")
print(applicability_df.to_string(index=False))
print()
print("None of the registered gated variables is whole-column structural or")
print("whole-column ordinary missingness: the raw whole-cohort missingness % is")
print("driven almost entirely by rows where the variable simply does not apply, not")
print("by genuine undocumented values within the applicable subgroup. Postcondition")
print("passed for all registered gates: zero rows are inconsistent with their gate")
print("(not-applicable rows never carry an observed value).")
""")


# ── Section B4c ────────────────────────────────────────────────────────────────
SB2B_HEADER = md("clean-b-s04c-header", """
## Section B4c — Broad Missingness Review (Matrix / Heatmap)

Audit-output only — no data is modified. Adds a broad visual missingness
review (matrix/heatmap across all cleaning-scope columns, plus row- and
column-level missingness summaries, including missingness by classification
group) alongside the tabular missingness log above. This is a diagnostic
visualization added to Data Cleaning B's own audit trail; it does not change
any decision already made in Section B4.

**Raw vs. genuine missingness (read before the heatmap below):** the matrix
and per-column bar chart show **raw NaN presence**, which necessarily includes
confirmed structural non-applicability (Section B4's `STRUCTURAL_NAN_COLS`) —
it is **not** a genuine missingness burden and must not be read as one. Every
reader-facing scientific row-level statistic below reuses the exact same
applicability-aware denominator already established in Section B4/B4b
(the row-level missingness cell `clean-b-s04-row` and the column-level
missingness log `clean-b-s04-column`); see those cells for the full
structural/applicability breakdown per column.
""")

SB2B_VISUAL = code("clean-b-s04c-visual", """
# ── Broad missingness review: matrix/heatmap + row/column summaries ───────────
# The heatmap and per-column bar chart below are a RAW NaN visualization only:
# they include confirmed structural non-applicability (STRUCTURAL_NAN_COLS),
# which is not genuine data-quality missingness and must not be read as a
# missingness burden. Every scientific row-level statistic in this cell reuses
# the same applicability-aware _row_missing_frac computed in the Section B4
# row-level cell (clean-b-s04-row); a raw figure, where kept for audit
# curiosity, is explicitly labeled RAW and never substituted for the genuine
# metric.
_miss_matrix = df_clean[CLEANING_SCOPE].isna()

_fig, _axes = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [3, 1]})

sns.heatmap(_miss_matrix, cbar=False, yticklabels=False, xticklabels=False,
            cmap=["#dddddd", "#c0392b"], ax=_axes[0])
_axes[0].set_title(
    f"RAW NaN pattern (NOT genuine missingness) -- {len(CLEANING_SCOPE)} cleaning-scope "
    f"columns x {len(df_clean)} rows\\nIncludes confirmed structural non-applicability -- "
    "see the applicability-aware summary below"
)
_axes[0].set_xlabel("columns (order = CLEANING_SCOPE)")
_axes[0].set_ylabel("rows")

_col_miss_pct = (_miss_matrix.mean() * 100).sort_values(ascending=True)
_colors = ["#2ecc71" if v == 0 else ("#f39c12" if v < 40 else ("#e67e22" if v < 70 else "#c0392b"))
           for v in _col_miss_pct.values]
_axes[1].barh(range(len(_col_miss_pct)), _col_miss_pct.values, color=_colors)
_axes[1].set_yticks([])
_axes[1].set_xlabel("% missing (RAW whole-cohort)")
_axes[1].set_title("Column RAW NaN %\\n(sorted; not applicability-aware)")
_axes[1].axvline(40, color="black", linewidth=0.5, linestyle="--")
_axes[1].axvline(70, color="black", linewidth=0.5, linestyle="--")

plt.tight_layout()
plt.show()

print("RAW NaN visualization (cleaning scope, at this point in the pipeline) -- raw whole-")
print("cohort NaN presence, NOT genuine missingness: includes confirmed structural non-")
print("applicability (e.g. endometrioma_size_clean NaN for endometrioma==0). See the")
print("Section B4 column-level missingness log (clean-b-s04-column) for the genuine-vs-raw")
print("split per column, and the Section B4 row-level cell (clean-b-s04-row) for the genuine")
print("row-level denominator used below.")
print(f"  Columns with 0% RAW missing    : {int((_col_miss_pct==0).sum())}")
print(f"  Columns with <40% RAW missing  : {int(((_col_miss_pct>0)&(_col_miss_pct<40)).sum())}")
print(f"  Columns with 40-70% RAW missing: {int(((_col_miss_pct>=40)&(_col_miss_pct<70)).sum())}")
print(f"  Columns with >=70% RAW missing : {int((_col_miss_pct>=70).sum())}")

# ── Scientific row-level missingness summary: SAME applicability-aware ───────
# metric as the Section B4 row-level cell (clean-b-s04-row, _row_missing_frac) -- never an independently recomputed
# blanket _miss_matrix.mean(axis=1) figure used as the scientific decision
# metric.
print(f"\\n  Max row missingness (applicability-aware, matches Section B4 row-level cell): "
      f"{round(float(_row_missing_frac.max())*100, 1)}%")
for _thr in [0.10, 0.25, 0.50]:
    _n_thr = int((_row_missing_frac > _thr).sum())
    print(f"  Rows > {int(_thr*100)}% missing (applicability-aware, matches Section B4 row-level cell): {_n_thr}")

# RAW row-missingness figure retained ONLY as a labeled audit-curiosity
# diagnostic -- never used in any recommendation.
_row_miss_pct_RAW_DIAGNOSTIC_ONLY = _miss_matrix.mean(axis=1) * 100
print(f"\\n  [RAW diagnostic only, not used in any recommendation] Max row RAW NaN %: "
      f"{round(float(_row_miss_pct_RAW_DIAGNOSTIC_ONLY.max()),1)}%")
print(f"  [RAW diagnostic only, not used in any recommendation] Rows >50% RAW NaN: "
      f"{int((_row_miss_pct_RAW_DIAGNOSTIC_ONLY>50).sum())}")

# Missingness by classification group. The group mean below is RAW
# whole-cohort NaN prevalence (it includes structural non-applicability); an
# applicability-aware GENUINE-missingness-by-group summary follows immediately,
# reusing genuine_missing_within_applicable_pct from the Section B4 column-level
# log.
_group_of = {
    _c: (
        "predictor_allowed" if _c in PREDICTOR_ALLOWED_COLS
        else "secondary_near_delivery_predictor" if _c in SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS
        else "intrapartum_predictor_exclude_from_prelabor_model" if _c in INTRAPARTUM_PREDICTOR_EXCLUDE_COLS
        else "intrapartum_candidate_pending_timing_confirmation"
    )
    for _c in CLEANING_SCOPE
}
_group_series = pd.Series(_group_of)
_by_group_raw = pd.DataFrame({
    "raw_missing_%": _col_miss_pct,
    "group": _group_series.reindex(_col_miss_pct.index),
})
print("\\n  Mean column RAW NaN % by classification group (whole-cohort prevalence; includes "
      "structural non-applicability -- see genuine-missingness table below):")
print(_by_group_raw.groupby("group")["raw_missing_%"].mean().round(1).to_string())

_genuine_pct_by_col = {r["column"]: r["genuine_missing_within_applicable_pct"] for r in missingness_log}
_by_group_genuine = pd.DataFrame({
    "genuine_missing_within_applicable_%": pd.Series(_genuine_pct_by_col).reindex(_col_miss_pct.index),
    "group": _group_series.reindex(_col_miss_pct.index),
})
print("\\n  Mean GENUINE within-applicable missingness % by classification group "
      "(applicability-aware; preferred for data-quality interpretation, from the Section B4 column-level log):")
print(_by_group_genuine.groupby("group")["genuine_missing_within_applicable_%"].mean().round(1).to_string())

# ── Subgroup applicability report ──────────────────────────────────────────
# adhesions, surgical_site_infection, etc. are outside CLEANING_SCOPE and are
# never touched by the missingness handling above. Reported here separately,
# using SUBGROUP_APPLICABLE_COLS (Section B1), with each entry's own subgroup
# denominator (not the full-cohort denominator, and not as ordinary
# missingness). Most entries use the cesarean subgroup; age_at_neonatal_death
# uses the neonatal_death==1 subgroup -- the mask is looked up per entry by
# subgroup_label.
#
# Small-cell disclosure protection: a subgroup with a protected small
# denominator (e.g. neonatal_death==1, n=1) never has its raw within-subgroup
# value distribution printed. Reuses the shared small-cell convention
# (analysis/eda/notebook_build/eda_shared/share_safe.py,
# DEFAULT_DISCLOSURE_THRESHOLD=5). The internal null-check on non-applicable
# rows is unaffected -- only the raw value distribution is suppressed.
_ss_spec = importlib.util.spec_from_file_location(
    "share_safe", _root / "analysis" / "eda" / "notebook_build" / "eda_shared" / "share_safe.py",
)
share_safe = importlib.util.module_from_spec(_ss_spec)
_ss_spec.loader.exec_module(share_safe)
_SMALL_CELL_THRESHOLD = share_safe.DEFAULT_DISCLOSURE_THRESHOLD

print("\\n  Subgroup applicability report (not part of CLEANING_SCOPE):")
_subgroup_masks_report = {
    "intrapartum_cesarean": df["type_of_CS"].isin([2, 3]),
    "neonatal_death": df["neonatal_death"] == 1,
}
for _sg_col, _sg_meta in SUBGROUP_APPLICABLE_COLS.items():
    _sg_label_report = _sg_meta["subgroup_label"]
    _sg_mask_report = _subgroup_masks_report[_sg_label_report]
    _n_sg_report = int(_sg_mask_report.sum())
    _sg_n_outside_non_null = int(df.loc[~_sg_mask_report, _sg_col].notna().sum())
    if 0 < _n_sg_report < _SMALL_CELL_THRESHOLD:
        _sg_display = (
            f"protected small subgroup (n={_n_sg_report}<{_SMALL_CELL_THRESHOLD}); raw value "
            "distribution suppressed for disclosure protection"
        )
    else:
        _sg_display = df.loc[_sg_mask_report, _sg_col].value_counts(dropna=False).to_dict()
    print(f"    {_sg_col}: subgroup={_sg_label_report} "
          f"(denominator n={_n_sg_report}, expected {_sg_meta['expected_applicable_denominator']}) "
          f"-> within-subgroup counts={_sg_display} | "
          f"non-subgroup non-null (expected 0, structural not ordinary missing)={_sg_n_outside_non_null}")
""")


# ── Section B4d ─────────────────────────────────────────────────────────────────
SB3_HEADER = md("clean-b-s04d-header", """
## Section B4d — Missingness-Mechanism Screen

For each scope column with missingness, its missingness indicator is tested for
association against a small, defensible reference-variable set chosen by a
**deterministic, per-variable, horizon-tiered selection rule** — near-complete
(< 5% missing) `CLEANING_SCOPE` variables only, capped per type, in
`CLEANING_SCOPE` order. This is a rule that selects among eligible variables
each run, not a hardcoded list of names.

**Horizon tiering.** The reference-eligible pool is not one fixed set shared by
every screened column. A screened column's own predictor-classification stage
bounds which reference variables may explain *its* missingness, matching the
cumulative modeling-horizon contract: a Stage-1 (`predictor_allowed`) column's
screen uses Stage-1 references only; a Stage-2
(`secondary_near_delivery_predictor`) column's screen uses Stage 1+2
references; a Stage-3 (`intrapartum_predictor_exclude_from_prelabor_model`)
column's screen uses Stage 1+2+3 references. A column that is never a predictor
at any stage (e.g. `leakage_exclude`, `intrapartum_or_post_delivery_exclude`,
`source_or_text_audit_exclude`) has no earlier-stage model to protect and draws
from the full pool for its descriptive screen. `intrapartum_or_post_delivery_exclude`
columns and the target are never reference-eligible at any tier. Tiering — not a
name-specific ban — is what prevents a later-horizon variable from leaking into
an earlier-horizon screen. The mechanism labels are **descriptive screening
labels only**:

- **no strong evidence of association with the tested observed variables**
- **missingness associated with observed variables; MCAR unlikely / compatible with MAR**
- **structural / subgroup missingness (confirmed code-enforced gate); MCAR/MAR
  mechanism inference not applicable; variable-specific handling documented
  separately** — this label does **not** by itself mean the variable has an
  open clinical-review decision; each variable's specific status is documented
  in its own Section B5-family paragraph.

### Tests
- Indicator vs. each **continuous** reference variable: **Kolmogorov–Smirnov** (two-sample)
- Indicator vs. each **categorical/binary** reference variable: **chi-square**, or
  **Fisher exact** for sparse 2×2 tables (any expected cell count <5)
- For a categorical/binary reference variable with more than 2 levels (a
  contingency table larger than 2×2), sparse expected counts can still make
  the asymptotic chi-square test unreliable even though Fisher's exact test is
  not used for tables of that shape here. A conservative, documented rule
  (more than 20% of cells with expected count <5, or any cell with expected
  count <1) is applied: if materially violated, that specific test is
  **skipped** (`skipped_sparse_contingency_table`) rather than reporting an
  unsupported asymptotic p-value. No category collapsing or Monte-Carlo/exact
  test is introduced to force a result. Skipped tests are excluded from that
  column's BH-FDR family.
- Where a missing variable is tested against more than one reference variable,
  **Benjamini–Hochberg FDR** correction is applied across that variable's own
  *valid* test family (never including skipped tests) before deciding
  significance (q<0.05), so a large number of raw p-values is not misread as
  independent evidence.

### Confirmed-structural and row-specific applicability gated variables
`gestational_age_at_PPROM_days` and `indication_for_induction_clean` (row-
specific applicability gated) and the confirmed-structural columns in
`STRUCTURAL_NAN_COLS` (`endometrioma_size_clean`, `endometrioma_place_clean`,
`endometrioma_laterality`, `endo_surgery_adhesiolysis`) are all tested within
their own applicable subset only (e.g. `PPROM==1`, `induction_any_bin==1`,
`endometrioma==1`, `endometriosis_surgery==1`) — not-applicable rows are
excluded from the test entirely, never counted as "present" or "missing".
Below 5 applicable-missing cases, no test is run; the result is reported as
`"insufficient applicable missing cases for a meaningful mechanism test"`
rather than an unstable p-value. `endo_surgery_adhesiolysis` currently has
zero genuinely missing applicable cases and therefore receives no mechanism
test.

### No target / outcome diagnostic is computed here
This section does **not** compute, report, or store any missingness-vs-target
association. Data Cleaning B is a target-blind cleaning stage: `TARGET_COL` is
never read in Section B2 (extreme-value audit) or Section B4/B4d (missingness
assessment). The mechanism label depends **only** on KS / chi-square / Fisher
tests against safe observed reference variables from the screened column's own
horizon-stage pool, BH-FDR corrected per column. Any outcome-aware sensitivity
analysis, if ever wanted, belongs downstream in modeling.

### Critical interpretation rule
These tests do **not** prove MCAR, MAR, or MNAR. A significant association after
FDR correction means missingness is associated with the observed variables
tested here — evidence against MCAR, potentially compatible with MAR — **never**
evidence of MNAR. MNAR concerns dependence on values that are themselves
unobserved and cannot be established from observed-data association tests
alone. Results here are intended to guide manual review and later modeling
decisions; any actual missing-value handling decision requires clinical/
statistical approval before implementation.
""")


SB3_MECHANISM = code("clean-b-s04d-mechanism", """
# ── Sparse contingency-table rule ───────────────────────────────────────────
# Conventional (Cochran's) rule for asymptotic chi-square reliability: no more
# than 20% of cells may have expected count <5, and no cell may have expected
# count <1. Documented here explicitly rather than left implicit -- applies
# only to tables LARGER than 2x2 (2x2 tables already fall back to Fisher's
# exact test below whenever any expected cell count is <5, so they never reach
# this rule).
_SPARSE_MAX_FRACTION_LOW_EXPECTED = 0.20
_SPARSE_MIN_EXPECTED_ABSOLUTE = 1.0
_SPARSE_LOW_EXPECTED_THRESHOLD = 5.0


def _expected_counts_acceptable(table):
    expected = stats.chi2_contingency(table, correction=False)[3]
    n_cells = expected.size
    n_low = int((expected < _SPARSE_LOW_EXPECTED_THRESHOLD).sum())
    n_below_min = int((expected < _SPARSE_MIN_EXPECTED_ABSOLUTE).sum())
    return (n_low / n_cells) <= _SPARSE_MAX_FRACTION_LOW_EXPECTED and n_below_min == 0


def _chi2_or_fisher(indicator, categorical_var):
    # Returns (p_value_or_None, status). status is one of:
    #   'chi2'    -- valid chi-square test performed
    #   'fisher'  -- valid Fisher exact test performed (sparse 2x2 only)
    #   'skipped_sparse_contingency_table' -- table >2x2 with materially
    #        violated expected-count assumptions; NOT reported as an
    #        unsupported asymptotic p-value, and excluded from BH-FDR
    #   'not_testable' -- fewer than 2 observed levels in the indicator or the
    #        reference variable after pairwise-complete dropna; not a sparse
    #        table, simply not enough variation to test at all
    pair = pd.DataFrame({"ind": indicator, "v": categorical_var}).dropna()
    if pair["ind"].nunique() < 2 or pair["v"].nunique() < 2:
        return None, "not_testable"
    table = pd.crosstab(pair["ind"], pair["v"])
    if table.shape == (2, 2):
        if (stats.chi2_contingency(table, correction=False)[3] < 5).any():
            _, p = stats.fisher_exact(table)
            return float(p), "fisher"
        _, p, _, _ = stats.chi2_contingency(table, correction=False)
        return float(p), "chi2"
    # Larger than 2x2: do not silently accept an unreliable asymptotic
    # chi-square result. No category collapsing and no Monte-Carlo/exact-test
    # dependency is introduced here -- the test is skipped and the reason is
    # recorded instead.
    if not _expected_counts_acceptable(table):
        return None, "skipped_sparse_contingency_table"
    _, p, _, _ = stats.chi2_contingency(table, correction=False)
    return float(p), "chi2"


def _ks_test(indicator, continuous_var):
    grp_missing = continuous_var[indicator == 1].dropna()
    grp_present = continuous_var[indicator == 0].dropna()
    if len(grp_missing) < 5 or len(grp_present) < 5:
        return None, "not_testable"
    _, p = stats.ks_2samp(grp_missing, grp_present)
    return float(p), "ks"


def _bh_fdr(pvals):
    # Standard Benjamini-Hochberg FDR correction (step-up), returned in the
    # same order as the input p-values. No extra dependency required.
    m = len(pvals)
    if m == 0:
        return []
    ranked = sorted(range(m), key=lambda i: pvals[i])  # ascending p-value order
    q = [0.0] * m
    running_min = 1.0
    for rank in range(m, 0, -1):
        idx = ranked[rank - 1]
        adj = pvals[idx] * m / rank
        running_min = min(running_min, adj)
        q[idx] = running_min
    return q


# ── Defensible reference-variable SELECTION RULE (not a literal fixed list) ───
# Near-complete (<5% missing themselves) clinical/predictor variables, in
# deterministic (CLEANING_SCOPE) order, capped to keep each missing-variable's
# own test family small and interpretable rather than testing against dozens
# of columns. This is a RULE that selects among currently-eligible
# CLEANING_SCOPE variables each run -- not a single hardcoded named list.
_MAX_REFERENCE_VARS_PER_TYPE = 3
_MECHANISM_REF_MAX_MISSING = 0.05

# ── Per-variable horizon tiers ─────────────────────────────────────────────
# Mirrors modeling_core.py's HORIZON_ALLOWED_CLASSIFICATIONS cumulative
# contract exactly: Stage 1 = predictor_allowed; Stage 2 = Stage 1 +
# secondary_near_delivery_predictor; Stage 3 = Stage 2 +
# intrapartum_predictor_exclude_from_prelabor_model. intrapartum_or_post_delivery_exclude
# columns and the target are never reference-eligible at any tier.
HORIZON_STAGE1_COLS = set(PREDICTOR_ALLOWED_COLS)
HORIZON_STAGE2_COLS = HORIZON_STAGE1_COLS | set(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)
HORIZON_STAGE3_COLS = HORIZON_STAGE2_COLS | set(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)


def _reference_eligible_cols_for(col):
    # A screened column's OWN stage bounds which reference variables may be
    # used to explain its missingness -- a Stage-1 variable's screen must
    # never be informed by a Stage-2/Stage-3 reference. A column with no
    # horizon-tier classification at all (never a predictor at any stage) has
    # no earlier-stage predictor model to protect, so it gets the full
    # Stage-1+2+3 pool for its descriptive/audit screen.
    if col in PREDICTOR_ALLOWED_COLS:
        return HORIZON_STAGE1_COLS
    if col in SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS:
        return HORIZON_STAGE2_COLS
    if col in INTRAPARTUM_PREDICTOR_EXCLUDE_COLS:
        return HORIZON_STAGE3_COLS
    return HORIZON_STAGE3_COLS


# Near-complete numeric/categorical CLEANING_SCOPE columns, in deterministic
# order, WITHOUT any stage filtering yet -- stage filtering is applied
# per-screened-column below via _reference_eligible_cols_for, not once
# globally, so the same candidate list can serve every horizon tier correctly.
_ALL_CONTINUOUS_REF_CANDIDATES = [
    c for c in CLEANING_SCOPE
    if infer_var_type(df_clean[c]) == "numeric"
    and df_clean[c].isna().mean() < _MECHANISM_REF_MAX_MISSING
]
_ALL_CATEGORICAL_REF_CANDIDATES = [
    c for c in CLEANING_SCOPE
    if infer_var_type(df_clean[c]) in ("binary", "categorical")
    and df_clean[c].isna().mean() < _MECHANISM_REF_MAX_MISSING
]


def _reference_vars_for(col):
    _eligible = _reference_eligible_cols_for(col)
    _cont = [c for c in _ALL_CONTINUOUS_REF_CANDIDATES if c in _eligible and c != col][:_MAX_REFERENCE_VARS_PER_TYPE]
    _cat = [c for c in _ALL_CATEGORICAL_REF_CANDIDATES if c in _eligible and c != col][:_MAX_REFERENCE_VARS_PER_TYPE]
    return _cont, _cat

# Row-specific applicability gated variables (gestational_age_at_PPROM_days,
# indication_for_induction_clean) AND confirmed-structural variables
# (STRUCTURAL_NAN_COLS: endometrioma_size_clean/place_clean/laterality,
# endo_surgery_adhesiolysis) are tested against this reference set only within
# their own applicable subset -- never the whole cohort, and never with
# not-applicable rows counted as either "missing" or "present". Both tiers
# share the SAME unified gate lookup already built in the Section B4 row-level cell (clean-b-s04-row; Section B4's
# row-level cell, `_all_row_applicability_gates`) instead of a second,
# independently-maintained applicability calculation. Below this many
# applicable-missing cases, an inferential test would be unstable and
# misleading, so testing is skipped and reported explicitly instead.
_MIN_APPLICABLE_MISSING_FOR_TESTING = 5

print("Reference-variable pools are per-screened-column and horizon-tiered "
      "-- see _reference_vars_for(col); the pool differs by the screened "
      f"column's own stage. Stage-1 pool size={len(HORIZON_STAGE1_COLS)}, "
      f"Stage-2 pool size={len(HORIZON_STAGE2_COLS)}, Stage-3 pool size={len(HORIZON_STAGE3_COLS)}.")

# ── Honest test-count tally ──────────────────────────────────────────────────
_test_tally = {
    "attempted": 0, "valid_chi2_or_ks": 0,
    "skipped_sparse_contingency_table": 0, "skipped_not_testable": 0,
}

mechanism_rows = []
mechanism_detail_rows = []  # audit-only: every individual test performed, kept for the CSV export
for col in CLEANING_SCOPE:
    if col not in df_clean.columns:
        continue

    # Unified applicability gate lookup: reuses the same
    # _all_row_applicability_gates built in the Section B4 row-level cell
    # (clean-b-s04-row) -- ROW_APPLICABILITY_GATES (PPROM/induction) unioned
    # with the confirmed-structural columns' gates from the shared
    # structural_missingness_registry. This is the one consistent applicability
    # mechanism used for both the row-specific-gated and the
    # confirmed-structural tiers.
    _is_gated = col in _all_row_applicability_gates
    if _is_gated:
        # Applicability gate (row-specific OR confirmed-structural): mechanism
        # testing concerns ONLY the applicable subset (gate condition holds)
        # and the genuinely missing applicable cases -- not-applicable rows
        # are excluded entirely, not counted as "present" or "missing".
        _gate = _all_row_applicability_gates[col]
        _applicable_mask_col = df_clean[_gate["gate_column"]] == _gate["applicable_value"]
        _test_df = df_clean.loc[_applicable_mask_col]
        _n_applicable = int(_applicable_mask_col.sum())
        _n_applicable_missing = int(_test_df[col].isna().sum())
        miss_pct = round(_n_applicable_missing / _n_applicable * 100, 1) if _n_applicable else 0.0
        if _n_applicable_missing < _MIN_APPLICABLE_MISSING_FOR_TESTING:
            mechanism_rows.append({
                "column": col,
                "missing_%": miss_pct,
                "n_observed_variable_tests": 0,
                "n_significant_after_fdr": 0,
                "mechanism_heuristic": (
                    "insufficient applicable missing cases for a meaningful mechanism test "
                    f"(applicable_missing_n={_n_applicable_missing}, applicable_n={_n_applicable}, "
                    f"gate={_gate['gate_column']}=={_gate['applicable_value']})"
                ),
                "reference_vars_used": "(not computed - insufficient applicable cases)",
            })
            continue
        indicator = _test_df[col].isna().astype(int)
    else:
        miss_pct = float(df_clean[col].isna().mean() * 100)
        if miss_pct == 0:
            continue
        indicator = df_clean[col].isna().astype(int)
        _test_df = df_clean

    # No target / outcome diagnostic is computed here -- Data Cleaning B never
    # reads TARGET_COL in this section. The mechanism label below depends only
    # on the safe observed reference variables selected next.

    # Per-column, horizon-tiered reference pool: computed fresh for THIS
    # screened column's own stage, not a single global pool shared by every
    # column. The horizon-stage pools (HORIZON_STAGE1/2/3_COLS) are
    # classification-derived predictor sets and structurally never contain the
    # outcome column.
    _col_continuous_refs, _col_categorical_refs = _reference_vars_for(col)
    assert not (set(_col_continuous_refs) | set(_col_categorical_refs)) & set(INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS), (
        f"Horizon-safety violation: an intrapartum_or_post_delivery_exclude column was "
        f"selected as a reference for {col!r}."
    )
    if col in PREDICTOR_ALLOWED_COLS:
        assert not (set(_col_continuous_refs) | set(_col_categorical_refs)) - HORIZON_STAGE1_COLS, (
            f"Horizon-safety violation: Stage-1 column {col!r}'s screen selected a "
            "later-horizon reference variable."
        )
    elif col in SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS:
        assert not (set(_col_continuous_refs) | set(_col_categorical_refs)) - HORIZON_STAGE2_COLS, (
            f"Horizon-safety violation: Stage-2 column {col!r}'s screen selected a "
            "Stage-3 reference variable."
        )

    _test_pvals, _test_labels = [], []
    for _ref in _col_continuous_refs:
        if _ref == col:
            continue
        _test_tally["attempted"] += 1
        p, _status = _ks_test(indicator, _test_df[_ref])
        if _status == "ks":
            _test_tally["valid_chi2_or_ks"] += 1
            _test_pvals.append(p); _test_labels.append(f"KS_vs_{_ref}")
            mechanism_detail_rows.append({
                "column": col, "test": f"KS_vs_{_ref}", "status": _status, "p_value": round(p, 4),
            })
        else:
            _test_tally["skipped_not_testable"] += 1
            mechanism_detail_rows.append({
                "column": col, "test": f"KS_vs_{_ref}", "status": _status, "p_value": None,
            })
    for _ref in _col_categorical_refs:
        if _ref == col:
            continue
        _test_tally["attempted"] += 1
        p, _status = _chi2_or_fisher(indicator, _test_df[_ref])
        if _status in ("chi2", "fisher"):
            _test_tally["valid_chi2_or_ks"] += 1
            _test_pvals.append(p); _test_labels.append(f"{_status}_vs_{_ref}")
            mechanism_detail_rows.append({
                "column": col, "test": f"chi2_or_fisher_vs_{_ref}", "status": _status, "p_value": round(p, 4),
            })
        elif _status == "skipped_sparse_contingency_table":
            _test_tally["skipped_sparse_contingency_table"] += 1
            mechanism_detail_rows.append({
                "column": col, "test": f"chi2_or_fisher_vs_{_ref}", "status": _status, "p_value": None,
            })
        else:  # not_testable
            _test_tally["skipped_not_testable"] += 1
            mechanism_detail_rows.append({
                "column": col, "test": f"chi2_or_fisher_vs_{_ref}", "status": _status, "p_value": None,
            })

    if not _test_pvals:
        mechanism = "review (not testable against the reference variable set)"
        n_sig_fdr = 0
    else:
        _qvals = _bh_fdr(_test_pvals)
        n_sig_fdr = sum(q < 0.05 for q in _qvals)
        mechanism = (
            "missingness associated with observed variables; MCAR unlikely / compatible with MAR"
            if n_sig_fdr > 0
            else "no strong evidence of association with the tested observed variables"
        )

    # Structural override applies to CONFIRMED structural columns only, never
    # the pending tier. APPLICABILITY_LINKED_NO_PREPROCESSING_MASK columns get their real
    # computed mechanism label above and are annotated (not relabeled) as
    # row-applicability gated -- a provenance annotation meaning no
    # code-enforced preprocessing gate exists, not a statement about whether
    # the variable's handling is resolved (each variable's own status is in its
    # Section B5-family paragraph).
    if col in STRUCTURAL_NAN_COLS:
        # A confirmed code-enforced gate means MCAR/MAR mechanism inference is
        # not applicable (the gate, not chance, explains the NaN pattern). It
        # says nothing about whether that variable's handling is resolved --
        # see its Section B5-family paragraph.
        mechanism = (
            "structural/subgroup missingness (confirmed code-enforced gate); "
            "MCAR/MAR mechanism inference not applicable; variable-specific "
            "handling documented separately"
        )
    elif col in APPLICABILITY_LINKED_NO_PREPROCESSING_MASK_COLS:
        mechanism = mechanism + (
            " (empirically row-applicability gated; no preprocessing-enforced "
            "mask -- see Section B4 header for this variable's specific "
            "applicability/handling status)"
        )

    mechanism_rows.append({
        "column": col,
        "missing_%": round(miss_pct, 1),
        "n_observed_variable_tests": len(_test_pvals),
        "n_significant_after_fdr": n_sig_fdr,
        "mechanism_heuristic": mechanism,
        "reference_vars_used": ", ".join(_col_continuous_refs + _col_categorical_refs) or "(none)",
    })

mechanism_df = pd.DataFrame(mechanism_rows).sort_values("missing_%", ascending=False) \\
    if mechanism_rows else pd.DataFrame()
mechanism_detail_df = pd.DataFrame(mechanism_detail_rows) if mechanism_detail_rows else pd.DataFrame()
print("\\nMissingness mechanism assessment (per-column horizon-tiered reference pools, "
      "up to 3 continuous + 3 categorical reference variable(s) each, BH-FDR corrected per column):")
if len(mechanism_df):
    print(mechanism_df.to_string(index=False))
    # attach mechanism back into the missingness log for export
    _mech_map = dict(zip(mechanism_df["column"], mechanism_df["mechanism_heuristic"]))
    for row in missingness_log:
        row["mechanism_heuristic"] = _mech_map.get(row["column"], "n/a (no missing)")
else:
    print("  No columns with missingness in scope.")
print("\\nCRITICAL: a significant association after FDR correction means missingness is")
print("associated with observed variables (MCAR unlikely / compatible with MAR) -- it does NOT")
print("establish MNAR, which concerns dependence on unobserved values and cannot be shown by")
print("these tests. No target/outcome association is computed in this target-blind cleaning")
print("stage. Heuristic only -- no imputation performed in this section.")

# ── Honest test-count reporting ──────────────────────────────────────────────
# attempted = every KS/chi2-or-fisher call made; valid = a usable p-value was
# produced; the two skip reasons are mutually exclusive and both excluded from
# every column's BH-FDR family above (only _test_pvals entries -- 'valid'
# tests -- ever reach _bh_fdr()).
print(f"\\nTest-count summary (all reference-variable tests across all tested columns):")
print(f"  attempted                       : {_test_tally['attempted']}")
print(f"  valid/completed (chi2/fisher/KS) : {_test_tally['valid_chi2_or_ks']}")
print(f"  skipped_sparse_contingency_table : {_test_tally['skipped_sparse_contingency_table']}")
print(f"  skipped_not_testable (<2 levels or insufficient group size) : {_test_tally['skipped_not_testable']}")
assert (
    _test_tally["valid_chi2_or_ks"]
    + _test_tally["skipped_sparse_contingency_table"]
    + _test_tally["skipped_not_testable"]
    == _test_tally["attempted"]
), "Test-count tally does not reconcile -- attempted must equal valid + both skip reasons."
""")


SB3_DRY_RUN_DECISION = code("clean-b-s04d-dry-run-decision", """
# ── Dry-run missingness decision table (documentation only) ──────────────────
# This table records review candidates and allowed actions. It does not apply
# row deletion, column deletion, imputation, new indicators, Unknown levels,
# transformations, target changes, preprocessing changes, or EDA C changes.
# The scientific predictor-scope row-missingness metric reuses the same
# applicability-aware _row_missing_frac from the Section B4 row-level cell
# (clean-b-s04-row) -- not an independently recomputed blanket
# df_clean[...].isna().mean(axis=1) figure.
row_missingness_gt_50_predictor_scope_n = int((_row_missing_frac > 0.50).sum())

# RAW diagnostic only (every df_clean column, including TARGET_COL,
# _row_key_delivery_id, and BMI_after where present) -- retained purely as an
# audit-curiosity figure, explicitly labeled, and NEVER used in
# row_deletion_recommended or any other recommendation field below.
_all_col_missing_frac_RAW_DIAGNOSTIC_ONLY = df_clean.isna().mean(axis=1)
row_missingness_gt_50_all_columns_n_RAW_DIAGNOSTIC_ONLY = int(
    (_all_col_missing_frac_RAW_DIAGNOSTIC_ONLY > 0.50).sum()
)

row_deletion_recommended = False
row_deletion_applied = False

print("Dry-run row-level missingness summary:")
print(f"  row_missingness_gt_50_predictor_scope_n (applicability-aware, matches Section B4 row-level cell) "
      f"= {row_missingness_gt_50_predictor_scope_n}")
print("  [RAW diagnostic only, not used in row_deletion_recommended or any other "
      f"recommendation] row_missingness_gt_50_all_columns_n_RAW = "
      f"{row_missingness_gt_50_all_columns_n_RAW_DIAGNOSTIC_ONLY}")
print(f"  row_deletion_recommended = {row_deletion_recommended}")
print(f"  row_deletion_applied = {row_deletion_applied}")


def _scope_or_role(col):
    if col in STRUCTURAL_NAN_COLS:
        return "structural/subgroup documented (confirmed gate)"
    if col in ROW_APPLICABILITY_GATES:
        return "row-specific applicability gated (empirically confirmed, no code-enforced gate)"
    if col in classification_df.index:
        return str(classification_df.loc[col, "classification"])
    return "cleaning_scope"


def _missingness_band(missing_pct):
    if missing_pct >= 70:
        return ">=70%"
    if missing_pct >= 40:
        return "40%-70%"
    if missing_pct > 0:
        return "<40%"
    return "0%"


def _structural_status(col):
    if col in STRUCTURAL_NAN_COLS:
        return "structural/subgroup documented (confirmed gate)"
    if col in ROW_APPLICABILITY_GATES:
        return "row-specific applicability gated (empirically confirmed, no code-enforced gate)"
    return "not structural based on available metadata"


def _proposed_status(row):
    col = row["column"]
    tier = row["tier"]
    if tier == "structural":
        # A confirmed code-enforced gate is not itself an open clinical decision.
        return (
            "structural/subgroup missingness (confirmed code-enforced gate); "
            "variable-specific handling documented separately"
        )
    if col in ROW_APPLICABILITY_GATES:
        # Each registered gated variable's residual applicable-missing rows have
        # an approved deterministic representation -- variable-specific, not a
        # single generic "pending clinical review".
        if col == "adenomyosis_sonographic_features_clean":
            return (
                "not-applicable rows excluded from the denominator by design; "
                "genuinely missing applicable rows are represented explicitly "
                "by the adenomyosis multi-hot family (adenomyosis_feature_1..11 "
                "+ adenomyosis_features_unknown, Section B5f) -- resolved, not pending"
            )
        if col == "gestational_age_at_PPROM_days":
            return (
                "not-applicable rows excluded from the denominator by design; "
                "genuinely missing applicable rows are represented explicitly by "
                "the fold-safe gestational_age_at_PPROM_days_timing_status "
                "(PPROM_timing_unknown category, Section B5b) -- resolved, not "
                "pending; only the category-cutpoint fitting location is deferred "
                "to modeling"
            )
        if col == "indication_for_induction_clean":
            return (
                "not-applicable rows excluded from the denominator by design; "
                "genuinely missing applicable rows are represented explicitly by "
                "indication_for_induction_status (induction_indication_unknown "
                "category, Section B5h) -- resolved, not pending"
            )
        return (
            "not-applicable rows excluded from the denominator by design; residual "
            "applicable-missing cases pending clinical/partner review before any imputation"
        )
    if tier in [">=70%", "40-70%"]:
        return "manual review before any exclusion/imputation"
    if tier == "<40%":
        return "candidate for later modeling-pipeline handling only after approval"
    return "no missingness action needed"


def _decision_notes(row):
    col = row["column"]
    tier = row["tier"]
    if col in ROW_APPLICABILITY_GATES:
        return (
            "row-specific applicability gate confirmed empirically against the current "
            "cohort (zero rows inconsistent with the gate); tier/missing_% above reflect "
            "the applicable subset only, not the raw whole-cohort % -- counting "
            "not-applicable rows in the denominator would misrepresent this variable; "
            "see Section B4b for the full breakdown"
        )
    if tier == "structural":
        return "structural or subgroup-specific missingness (confirmed gate); keep meaningful NaN unless approved otherwise"
    if tier == "40-70%":
        return "high-intermediate missingness; do not exclude, recode, or impute without manual approval"
    if tier == "<40%":
        return "lower missingness; later modeling-pipeline handling only after approved mechanism review"
    return "no missingness detected"


missingness_decision_rows = []
for _, row in missingness_df.sort_values("missing_%", ascending=False).iterrows():
    tier = row["tier"]
    requires_decision = bool(tier != "0%")
    # Logical classification uses the boolean membership test directly
    # (col in STRUCTURAL_NAN_COLS), never the display-only status string.
    _is_confirmed_structural = bool(row["column"] in STRUCTURAL_NAN_COLS)
    missingness_decision_rows.append({
        "variable": row["column"],
        "missing_n": int(df_clean[row["column"]].isna().sum()) if row["column"] in df_clean.columns else None,
        "missing_pct": row["missing_%"],
        "missingness_band": _missingness_band(row["missing_%"]),
        "variable_scope_or_role": _scope_or_role(row["column"]),
        "structural_or_subgroup_missingness_status": _structural_status(row["column"]),
        "is_confirmed_structural": _is_confirmed_structural,
        "existing_handling": row["recommendation"],
        "proposed_status": _proposed_status(row),
        "action_allowed_now": "documentation only",
        "requires_manual_decision": requires_decision,
        "notes": _decision_notes(row),
    })

missingness_decision_df = pd.DataFrame(missingness_decision_rows)
_decision_view = missingness_decision_df[missingness_decision_df["requires_manual_decision"]]
print("\\nDry-run missingness decision table (documentation only):")
if len(_decision_view):
    _n_structural = int(_decision_view["is_confirmed_structural"].sum())
    _gated_cols_present = [c for c in ROW_APPLICABILITY_GATES if c in _decision_view["variable"].values]
    print(f"  {len(_decision_view)} scope column(s) have any missingness (missing_% > 0): "
          f"{_n_structural} confirmed structural/subgroup, {len(_gated_cols_present)} "
          "row-applicability-gated with an approved deterministic representation, "
          f"{len(_decision_view) - _n_structural - len(_gated_cols_present)} other.")
    print(
        "  Variable-specific final treatments are documented in Sections B5-B6. The "
        "decision-support table above is retained in memory (missingness_decision_df) "
        "for auditability; no unresolved Data Cleaning B treatment decision is implied "
        "by this display."
    )
    if _gated_cols_present:
        _final_location = {
            "adenomyosis_sonographic_features_clean":
                "adenomyosis_feature_1..11 + adenomyosis_features_unknown (Section B5f)",
            "gestational_age_at_PPROM_days":
                "gestational_age_at_PPROM_days_timing_status (Section B5b)",
            "indication_for_induction_clean":
                "indication_for_induction_status (Section B5h)",
        }
        _gated_table = pd.DataFrame({
            "variable": _gated_cols_present,
            "applicable_missingness_status": ["row-applicability gated (confirmed)"] * len(_gated_cols_present),
            "final_B_representation": [_final_location.get(c, "documented in Sections B5-B6") for c in _gated_cols_present],
        })
        print("\\n  Row-applicability-gated variables -- final representation:")
        print(_gated_table.to_string(index=False))
else:
    print("  (none -- every scope column is 0% missing or already resolved)")

_structural_summary_df = (
    missingness_decision_df
    .groupby("missingness_band", dropna=False)
    .agg(
        number_of_columns=("variable", "count"),
        number_structural_or_subgroup_documented=("is_confirmed_structural", "sum"),
        column_names=("variable", lambda s: ", ".join(s)),
    )
    .reset_index()
)
_structural_summary_df["number_not_structural_or_unclear"] = (
    _structural_summary_df["number_of_columns"]
    - _structural_summary_df["number_structural_or_subgroup_documented"]
)
_structural_summary_df["percentage_structural_or_subgroup_among_band"] = (
    _structural_summary_df["number_structural_or_subgroup_documented"]
    / _structural_summary_df["number_of_columns"] * 100
).round(1)
print("\\nDry-run structural/subgroup missingness summary by band:")
print(_structural_summary_df.to_string(index=False))

missingness_documentation_audit_entry = {
    "issue_type": "missingness_documentation_review",
    "action_taken": "documentation_only",
    "reason": "safer missingness mechanism wording and dry-run decision table; no data changes",
    "rows_removed": 0,
    "columns_removed": 0,
    "values_set_to_na": 0,
    "values_imputed": 0,
    "indicators_created": 0,
    "row_count_changed": False,
    "target_distribution_changed": False,
    "requires_manual_decision_before_data_change": True,
}
print("\\nDocumentation-only missingness audit entry:")
print(missingness_documentation_audit_entry)

print("\\nNot performed in this task/section:")
print("  no rows were removed")
print("  no columns were removed")
print("  no imputation was performed")
print("  no learned imputation or kNN imputation was performed")
print("  no new missing indicators were created")
print("  no Unknown category was created")
print("  no transformations were applied")
print("  target definition was unchanged")
print("  preprocessing was not modified")
print("  EDA C was not modified")
""")


CLEANING_B_PART2_CELLS = [
    SB2_HEADER,
    SB2_ROW,
    SB2_COLUMN,
    SB2C_HEADER,
    SB2C_APPLICABILITY,
    SB2B_HEADER,
    SB2B_VISUAL,
    SB3_HEADER,
    SB3_MECHANISM,
    SB3_DRY_RUN_DECISION,
]


if __name__ == "__main__":
    print(f"Data Cleaning B Part 2 cells defined: {len(CLEANING_B_PART2_CELLS)}")

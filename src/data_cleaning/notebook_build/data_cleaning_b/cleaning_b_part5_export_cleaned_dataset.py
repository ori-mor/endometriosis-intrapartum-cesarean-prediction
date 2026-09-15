#!/usr/bin/env python3
"""Data Cleaning B - Part 5 cell definitions (section B7).

B7 - Cleaned-column summary, consistency checks, and export of the cleaned
     dataset and audit logs required by EDA C, in that order.

When EXPORT_FOR_EDA_C = True, writes the cleaned dataset and audit logs to
outputs/data_cleaning/. NEVER overwrites work_df_batch18.xlsx. The feature
dictionary and manifest are the audit contract consumed by EDA C's controlled
validation.
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


# Section B7
SB8_HEADER = md("clean-b-s07-header", """
## Section B7 — Cleaned-Dataset Summary, Consistency Checks, and Export

This section runs in three steps, in this order: (1) assemble the final
cleaned-column list and print a summary, (2) run read-only consistency checks
against that column list (below), and only if every check passes, (3) export
the cleaned dataset and audit logs.

### Default: export for EDA C
`EXPORT_FOR_EDA_C = True` writes the cleaned B dataset and the audit contract that
EDA C validates before continuing.

### When enabled
This section owns **13 artifacts** — 1 patient-level workbook, 1 patient-level
audit CSV, 1 ID-only row-alignment sidecar, and 10 aggregate audit files (no
patient rows):

| File | Location | Patient rows? |
|------|----------|---------------|
| `work_df_batch19_after_data_cleaning_b.xlsx` | `outputs/data_cleaning/processed/` | **Yes — patient-level, gitignored** |
| `cleaning_b_row_actions_patient_level.csv` | `outputs/data_cleaning/audit/` | **Yes — patient-level, gitignored** |
| `cleaning_b_output_delivery_id_key.csv` | audit | **ID-only row-alignment sidecar — gitignored** |
| `cleaning_b_manifest.json` | audit | No |
| `cleaning_b_column_actions.csv` | audit | No |
| `cleaning_b_missingness_handling.csv` | audit | No |
| `cleaning_b_outlier_handling.csv` | audit | No |
| `outlier_extreme_value_final_adjudication.csv` | audit | No |
| `cleaning_b_imputation_plan.csv` | audit | No |
| `cleaning_b_feature_dictionary.csv` | audit | No |
| `cleaning_b_final_numeric_transformation_review.csv` | audit | No |
| `cleaning_b_variable_classification_snapshot.csv` | audit | No |
| `cleaning_b_variable_type_schema_snapshot.csv` | audit | No |

### Hard safety guarantees
- Output goes only under `outputs/data_cleaning/`.
- The code refuses to write anywhere inside `outputs/preprocessing/` or `analysis/preprocessing/`.
- `work_df_batch18.xlsx` is never overwritten.

### Feature dictionary = contract for EDA C
`cleaning_b_feature_dictionary.csv` documents every B-created column with:
`new_column, source_column, creation_rule, timing, leakage_status, intended_use`,
plus centralized-registry metadata columns: `creation_section, upstream_lineage,
predictor_classification, stage, clinical_timing, domain, redundancy_group`
(unresolved values stored as the literal string `"UNSET"`, never guessed).
Row order is deterministic (sorted by `new_column`).
EDA C uses it to allow B-created columns through its controlled validation; any
cleaned-dataset column that is neither in the classification CSV nor in this
dictionary causes EDA C to error.

### Row-specific applicability gated variables: `gestational_age_at_PPROM_days` and `indication_for_induction_clean` are handled DIFFERENTLY
Both have high raw whole-cohort NaN rates because each is applicable only to a
subset of rows, not because most of the cohort is undocumented (see Section
B4b). Their export treatment differs and is documented separately below:
`gestational_age_at_PPROM_days`'s raw column is retained;
`indication_for_induction_clean`'s is not.

**`gestational_age_at_PPROM_days`** — applicable only when `PPROM == 1`; rows
with `PPROM == 0` are not applicable (not "missing," not "documented as
absent"). Among the 17 `PPROM == 1` rows, 16 are observed and 1 is genuinely
missing.

- **The raw source column IS retained** in the cleaned/audit export, with its
  original NaNs preserved (not imputed); `model_entry_mode=transform_source_only`.
- Its retired derived representations `gestational_age_at_PPROM_days__missing_ind`
  and `gestational_age_at_PPROM_days__cat` are excluded from export.
- The documented-only fold-safe four-state timing representation
  (`no_PPROM` / `PPROM_earlier` / `PPROM_later` / `PPROM_timing_unknown`) is
  computed in modeling (Section B5b) -- it is not a physical Batch19 column.
- Classified `secondary_near_delivery_predictor`.
  `eda_c_part1_setup_gate.py`'s `MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS`
  is empty -- the raw column is admitted to EDA C's `ANALYSIS_VARS`. Its
  PRIMARY (raw whole-cohort) missingness is ~96.3%; the
  structural-applicability-aware figure (~5.9% genuine-missing-within-applicable)
  is a sensitivity/diagnostic view only and does not replace the PRIMARY
  figure or itself determine eligibility -- EDA C's generic high-missingness
  rule has been removed, and high missingness is now a soft diagnostic, not a
  hard-exclusion screen. `model_entry_mode=transform_source_only` means it may
  feed the fold-safe timing transformer internally but must never
  independently enter a design matrix as a plain numeric predictor -- a
  restricted-entry-mode disclosure, not a hard screening exclusion.

**`indication_for_induction_clean`** — applicable only when
`induction_any_bin == 1`; rows with `induction_any_bin == 0` are not
applicable. Among the 194 `induction_any_bin == 1` rows, 190 are observed and
4 are genuinely missing; 237 rows are `induction_any_bin == 0` (no induction /
not applicable).

- **The raw source column is NOT retained** in Batch19. It is represented in
  Batch19 by `indication_for_induction_status` (created in Section B5h), which the export
  drops the raw column in favour of (`INDICATION_FOR_INDUCTION_EXCLUDE_FROM_EXPORT`).
- `indication_for_induction_status` is materialized in B5h with **0 missing**:
  `no_induction` (237), `induction_indication_unknown` (4), or the observed
  indication string preserved verbatim (190).
- Because the raw column is absent from Batch19, it cannot reach EDA C at all
  -- the derived `indication_for_induction_status` is the only EDA C-facing
  representation of this information.
- `indication_for_induction_status` is classified
  `intrapartum_predictor_exclude_from_prelabor_model` (Stage 3 / intrapartum
  horizon only): it enters EDA C's unified Stage 1/2/3 screening universe
  (`ANALYSIS_VARS`) like any other Stage-3-eligible variable, and its
  classification restricts it to the Stage 3 horizon at the modeling boundary,
  not at EDA-C screening. It is **hard-redundant with `induction_any_bin`**
  (`no_induction` ⇔ `induction_any_bin == 0`), registered as a redundancy pair
  so the two are never automatically co-selected as independent predictors at
  modeling entry.

See `docs/clinical_decisions/manual_decisions_log.md` for the decision record.

No rows are removed, no imputation is performed, the target definition is
unchanged, preprocessing is not modified.
""")

SB8_SUMMARY = code("clean-b-s07-summary", """
# Build the cleaned-dataset column manifest
_original_cols = [TARGET_COL] + [c for c in CLEANING_SCOPE if c in df_clean.columns]
_created_cols = [d["new_column"] for d in feature_dictionary if d["new_column"] in df_clean.columns]
CLEANED_COLUMNS = [c for c in dict.fromkeys(_original_cols + _created_cols)
                   if c in df_clean.columns]

# ── >=70% ordinary missingness: flag / audit only ──────────────────────────
# An ordinary-missingness source column is never automatically deleted from
# the export for crossing the 70% threshold, and no category / derived
# predictor is created for it automatically (Section B4's
# "flag_for_audit_high_missingness_..." recommendation). This descriptive
# audit list feeds the summary print below and has no effect on
# CLEANED_COLUMNS.
_high_missing_ordinary_flagged_for_audit = [
    r["column"] for r in missingness_log
    if r["tier"] == ">=70%" and r["column"] in df_clean.columns
]
for _hm_col in _high_missing_ordinary_flagged_for_audit:
    _hm_miss_pct = round(float(df_clean[_hm_col].isna().mean() * 100), 1)
    column_actions_log.append({
        "column": _hm_col,
        "stage": "B7_export",
        "action": "flagged_for_audit_retained_in_export",
        "detail": (
            f"{_hm_col} has {_hm_miss_pct}% ordinary non-structural missingness (>=70%); "
            "flagged/documented for audit only -- retained in the cleaned analytical "
            "export, not automatically excluded. No missingness indicator, "
            "categorical/not_documented copy, or other derived predictor representation "
            "is created automatically."
        ),
        "issue_type": "ordinary_high_missingness_ge70_flagged_only",
        "action_taken": "flagged_for_audit_retained_in_export",
        "base_variable": _hm_col,
        "related_columns_excluded": "",
        "reason": (
            f"{_hm_col} has {_hm_miss_pct}% ordinary non-structural missingness (>=70%). "
            "The source variable is retained in the cleaned analytical dataset; any "
            "representation decision for this variable is made downstream (EDA C / "
            "modeling), not automatically here."
        ),
        "rows_removed": 0,
        "row_count_changed": False,
        "target_distribution_changed": False,
        "imputation_performed": False,
        "new_indicators_created": 0,
        "unknown_categories_created": 0,
        "requires_manual_decision_before_reversal": True,
    })

# gestational_age_at_PPROM_days: the raw column stays in the cleaned/audit
# export with its original NaNs; only its derived __missing_ind / __cat
# representations are excluded (replaced in Batch19 by the documented-only
# gestational_age_at_PPROM_days_timing_status). The raw column is admitted to
# EDA C's ANALYSIS_VARS, disclosed as model_entry_mode=transform_source_only.
PPROM_TIMING_DERIVED_FAMILY_TO_EXCLUDE = [
    "gestational_age_at_PPROM_days__missing_ind",
    "gestational_age_at_PPROM_days__cat",
]
_pprom_exclusion_requested = list(PPROM_TIMING_DERIVED_FAMILY_TO_EXCLUDE)
_pprom_exclusion_present_before = [
    c for c in _pprom_exclusion_requested if c in df_clean.columns
]
_pprom_exclusion_absent = [
    c for c in _pprom_exclusion_requested if c not in df_clean.columns
]
_pprom_exclusion_removed_from_export = [
    c for c in _pprom_exclusion_requested if c in CLEANED_COLUMNS
]
CLEANED_COLUMNS = [
    c for c in CLEANED_COLUMNS if c not in set(_pprom_exclusion_requested)
]
if "gestational_age_at_PPROM_days" in df_clean.columns and "gestational_age_at_PPROM_days" not in CLEANED_COLUMNS:
    CLEANED_COLUMNS = CLEANED_COLUMNS + ["gestational_age_at_PPROM_days"]

_n_pprom_missing = int(df_clean["gestational_age_at_PPROM_days"].isna().sum()) if "gestational_age_at_PPROM_days" in df_clean.columns else None
column_actions_log.append({
    "column": "gestational_age_at_PPROM_days",
    "stage": "B7_export",
    "action": "retained_in_export_transform_source_only",
    "detail": (
        "Raw column retained in cleaned/audit export with original NaNs (not "
        "imputed); its retired __missing_ind/__cat representations remain "
        "excluded, superseded by the documented-representation-only "
        "gestational_age_at_PPROM_days_timing_status (Section B5b). "
        "The raw column is NOT hard-"
        "excluded from EDA C's model-candidate pool -- "
        "MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS is empty; EDA C's "
        "generic high-missingness hard-exclusion rule has been removed, so no "
        "missingness threshold gates this column's eligibility. Its PRIMARY "
        "(raw whole-cohort) missingness is 96.3%; the "
        "structural-applicability-aware effective missingness (5.9% "
        "genuine-missing-within-applicable) is a sensitivity/diagnostic figure "
        "only and does not replace the PRIMARY figure. It IS admitted to "
        "ANALYSIS_VARS, tagged "
        "model_entry_mode=transform_source_only -- it may feed the fold-safe "
        "timing transformer internally but must never independently enter a "
        "design matrix as a plain numeric predictor. This is a "
        "restricted-entry-mode disclosure, not a hard exclusion."
    ),
    "issue_type": "structural_applicability_gated_secondary_timing_feature",
    "action_taken": "retained_for_audit_transform_source_only_in_modeling",
    "base_variable": "gestational_age_at_PPROM_days",
    "related_columns_excluded": ", ".join(_pprom_exclusion_removed_from_export),
    "reason": (
        f"gestational_age_at_PPROM_days has {_n_pprom_missing} missing values "
        f"({round(_n_pprom_missing/len(df_clean)*100,1) if _n_pprom_missing is not None else '?'}%) "
        "whole-cohort, structurally explained by PPROM==0 for all but one row "
        "(see docs/clinical_decisions/manual_decisions_log.md and "
        "analysis/eda/notebook_build/eda_shared/structural_missingness_registry.py "
        "for the exact structural-vs-undocumented breakdown: 17 applicable "
        "PPROM==1 rows, 1 genuinely missing -- 5.9% applicability-aware "
        "sensitivity/diagnostic missingness, distinct from and not replacing "
        "the 96.3% PRIMARY raw whole-cohort figure). Retained for audit/PPROM-subgroup analysis; its APPROVED "
        "modeling representation is the four-state fold-safe timing status "
        "(no_PPROM / PPROM_earlier / PPROM_later / PPROM_timing_unknown, "
        "Section B5b) -- the raw column feeds that transformer internally but "
        "must never independently enter a design matrix as a plain numeric "
        "predictor (model_entry_mode=transform_source_only)."
    ),
    "rows_removed": 0,
    "row_count_changed": False,
    "target_distribution_changed": False,
    "imputation_performed": False,
    "new_indicators_created": 0,
    "unknown_categories_created": 0,
    "requires_manual_decision_before_reversal": True,
})

# ── weight_in_pregnancy / BMI_after ────────────────────────────────────────
# Both remain continuous, NaNs preserved, no missingness indicator. Their
# modeling representations are the fold-safe weight_in_pregnancy_cat /
# BMI_after_cat (low_observed/mid_observed/high_observed/not_documented), with
# q33/q67 cutpoints fitted training-fold-only in modeling -- see the Section B7
# export-consistency checks below.

# ── adenomyosis sonographic-features detail: represented by the B5f multi-hot
# family (adenomyosis_feature_1..11 + adenomyosis_features_unknown) ──────────
_adeno_detail_exclusion_requested = list(ADENOMYOSIS_SONOGRAPHIC_EXCLUDE_FROM_EXPORT)
_adeno_detail_exclusion_present_before = [c for c in _adeno_detail_exclusion_requested if c in df_clean.columns]
_adeno_detail_exclusion_removed_from_export = [c for c in _adeno_detail_exclusion_requested if c in CLEANED_COLUMNS]
CLEANED_COLUMNS = [c for c in CLEANED_COLUMNS if c not in set(_adeno_detail_exclusion_requested)]

for _adeno_col in ADENOMYOSIS_SONOGRAPHIC_EXCLUDE_FROM_EXPORT:
    if _adeno_col not in df_clean.columns:
        continue
    column_actions_log.append({
        "column": _adeno_col,
        "stage": "B7_export",
        "action": "column_exclusion",
        "detail": (
            f"Excluded {_adeno_col} from final cleaned/modeling-ready output; "
            "superseded by the adenomyosis multi-hot representation (Section B5f, "
            "adenomyosis_feature_1..11 + adenomyosis_features_unknown)."
        ),
        "issue_type": "structural_missingness_correction_superseded_by_derived_variable",
        "action_taken": "column_exclusion",
        "base_variable": _adeno_col,
        "related_columns_excluded": _adeno_col,
        "reason": (
            "Replaced by the deterministic, lossless multi-hot representation "
            "(adenomyosis_feature_1..11 + adenomyosis_features_unknown) in place of a single "
            "combination-level adenomyosis_sonographic_features_status "
            "categorical, which distinguishes structural no-adenomyosis, genuinely unknown "
            "feature detail, and every documented feature code independently, without "
            "imputation. See docs/clinical_decisions/manual_decisions_log.md."
        ),
        "rows_removed": 0,
        "row_count_changed": False,
        "target_distribution_changed": False,
        "imputation_performed": False,
        "new_indicators_created": 0,
        "unknown_categories_created": 0,
        "requires_manual_decision_before_reversal": True,
    })

# ── endo_surgery_adhesiolysis: represented by derived_endo_surgery_adhesion_status (B5g) ──
_adhesiolysis_exclusion_requested = list(ENDO_SURGERY_ADHESIOLYSIS_EXCLUDE_FROM_EXPORT)
_adhesiolysis_exclusion_present_before = [c for c in _adhesiolysis_exclusion_requested if c in df_clean.columns]
_adhesiolysis_exclusion_removed_from_export = [c for c in _adhesiolysis_exclusion_requested if c in CLEANED_COLUMNS]
CLEANED_COLUMNS = [c for c in CLEANED_COLUMNS if c not in set(_adhesiolysis_exclusion_requested)]

for _adhesiolysis_col in ENDO_SURGERY_ADHESIOLYSIS_EXCLUDE_FROM_EXPORT:
    if _adhesiolysis_col not in df_clean.columns:
        continue
    column_actions_log.append({
        "column": _adhesiolysis_col,
        "stage": "B7_export",
        "action": "column_exclusion",
        "detail": (
            f"Excluded {_adhesiolysis_col} from final cleaned/modeling-ready output; "
            "superseded by derived_endo_surgery_adhesion_status (Section B5g)."
        ),
        "issue_type": "deterministic_replacement_supersedes_raw_source",
        "action_taken": "column_exclusion",
        "base_variable": _adhesiolysis_col,
        "related_columns_excluded": _adhesiolysis_col,
        "reason": (
            "Replaced by derived_endo_surgery_adhesion_status (Section B5g). See "
            "docs/clinical_decisions/manual_decisions_log.md."
        ),
        "rows_removed": 0,
        "row_count_changed": False,
        "target_distribution_changed": False,
        "imputation_performed": False,
        "new_indicators_created": 0,
        "unknown_categories_created": 0,
        "requires_manual_decision_before_reversal": True,
    })

# ── indication_for_induction_clean: represented by indication_for_induction_status (B5h) ──
_induction_exclusion_requested = list(INDICATION_FOR_INDUCTION_EXCLUDE_FROM_EXPORT)
_induction_exclusion_present_before = [c for c in _induction_exclusion_requested if c in df_clean.columns]
_induction_exclusion_removed_from_export = [c for c in _induction_exclusion_requested if c in CLEANED_COLUMNS]
CLEANED_COLUMNS = [c for c in CLEANED_COLUMNS if c not in set(_induction_exclusion_requested)]

for _induction_col in INDICATION_FOR_INDUCTION_EXCLUDE_FROM_EXPORT:
    if _induction_col not in df_clean.columns:
        continue
    column_actions_log.append({
        "column": _induction_col,
        "stage": "B7_export",
        "action": "column_exclusion",
        "detail": (
            f"Excluded {_induction_col} from final cleaned/modeling-ready output; "
            "superseded by indication_for_induction_status (Section B5h)."
        ),
        "issue_type": "deterministic_replacement_supersedes_raw_source",
        "action_taken": "column_exclusion",
        "base_variable": _induction_col,
        "related_columns_excluded": _induction_col,
        "reason": (
            "Replaced by indication_for_induction_status (Section B5h). See "
            "docs/clinical_decisions/manual_decisions_log.md."
        ),
        "rows_removed": 0,
        "row_count_changed": False,
        "target_distribution_changed": False,
        "imputation_performed": False,
        "new_indicators_created": 0,
        "unknown_categories_created": 0,
        "requires_manual_decision_before_reversal": True,
    })

# ── endometrioma detail columns: represented in Batch19 by B5c derived variables ──
# endometrioma_size_clean / endometrioma_place_clean / endometrioma_laterality and
# their __missing_ind indicators are excluded from the final export; endometrioma
# itself, endometrioma_size_status, and endometrioma_presence_laterality (created in
# B5c) are the modeling-bound representation going forward. df_clean itself is
# untouched here.
_endo_detail_exclusion_requested = list(ENDOMETRIOMA_DETAIL_EXCLUDE_FROM_EXPORT)
_endo_detail_exclusion_present_before = [c for c in _endo_detail_exclusion_requested if c in df_clean.columns]
_endo_detail_exclusion_removed_from_export = [c for c in _endo_detail_exclusion_requested if c in CLEANED_COLUMNS]
CLEANED_COLUMNS = [c for c in CLEANED_COLUMNS if c not in set(_endo_detail_exclusion_requested)]

for _endo_col in ("endometrioma_size_clean", "endometrioma_place_clean", "endometrioma_laterality"):
    if _endo_col not in df_clean.columns:
        continue
    column_actions_log.append({
        "column": _endo_col,
        "stage": "B7_export",
        "action": "column_exclusion",
        "detail": (
            f"Excluded {_endo_col} and {_endo_col}__missing_ind from final cleaned/"
            "modeling-ready output; superseded by endometrioma_size_status / "
            "endometrioma_presence_laterality (Section B5c)."
        ),
        "issue_type": "superseded_by_derived_variable",
        "action_taken": "column_exclusion",
        "base_variable": _endo_col,
        "related_columns_excluded": f"{_endo_col}, {_endo_col}__missing_ind",
        "reason": (
            "Replaced by deterministic derived variables endometrioma_size_status "
            "and endometrioma_presence_laterality. No imputation was performed. "
            "See docs/clinical_decisions/manual_decisions_log.md Decision 22."
        ),
        "rows_removed": 0,
        "row_count_changed": False,
        "target_distribution_changed": False,
        "imputation_performed": False,
        "new_indicators_created": 0,
        "unknown_categories_created": 0,
        "requires_manual_decision_before_reversal": True,
    })

# ── severe_PET / any_PET: represented by the _cat versions (B5e) ────────────
# diagnosis_year is NOT part of CAT_UNKNOWN_EXCLUDE_FROM_EXPORT (never was --
# see cleaning_b_part4_transformations_imputation_plan.py's
# CAT_UNKNOWN_EXCLUDE_FROM_EXPORT = list(PET_CAT_SOURCE_COLS)); it is excluded
# from df_clean entirely upstream, at the CLEANING_SCOPE stage
# (source_or_text_audit_exclude).
_catunk_exclusion_requested = list(CAT_UNKNOWN_EXCLUDE_FROM_EXPORT)
_catunk_exclusion_present_before = [c for c in _catunk_exclusion_requested if c in df_clean.columns]
_catunk_exclusion_removed_from_export = [c for c in _catunk_exclusion_requested if c in CLEANED_COLUMNS]
CLEANED_COLUMNS = [c for c in CLEANED_COLUMNS if c not in set(_catunk_exclusion_requested)]

for _catunk_col in CAT_UNKNOWN_EXCLUDE_FROM_EXPORT:
    if _catunk_col not in df_clean.columns:
        continue
    column_actions_log.append({
        "column": _catunk_col,
        "stage": "B7_export",
        "action": "column_exclusion",
        "detail": f"Excluded {_catunk_col} from final export; superseded by {_catunk_col}_cat (Section B5e).",
        "issue_type": "superseded_by_derived_variable",
        "action_taken": "column_exclusion",
        "base_variable": _catunk_col,
        "related_columns_excluded": _catunk_col,
        "reason": (
            f"Replaced by categorical + not_documented derived variable {_catunk_col}_cat. No "
            "ordinary numeric/binary imputation was performed for this column. "
            "See docs/clinical_decisions/manual_decisions_log.md Decision 27."
        ),
        "rows_removed": 0,
        "row_count_changed": False,
        "target_distribution_changed": False,
        "imputation_performed": False,
        "new_indicators_created": 0,
        "unknown_categories_created": 1,
        "requires_manual_decision_before_reversal": True,
    })

# Deterministic order (sorted by new_column) -- registry entries are appended
# throughout this notebook in code-execution order, which is not guaranteed
# stable across future edits; sorting here makes the exported CSV's row
# order deterministic regardless.
feature_dictionary_df = pd.DataFrame(feature_dictionary) if feature_dictionary else pd.DataFrame(
    columns=["new_column", "source_column", "creation_rule", "timing",
             "leakage_status", "intended_use", "creation_section", "upstream_lineage",
             "predictor_classification", "stage", "clinical_timing", "domain", "redundancy_group"])
if len(feature_dictionary_df):
    feature_dictionary_df = feature_dictionary_df.sort_values("new_column").reset_index(drop=True)

print("Cleaning summary")
print(f"  Input rows                : {len(df)}")
print(f"  Cleaned rows              : {len(df_clean)} "
      f"(row exclusions applied: {ROW_EXCLUSIONS_APPLIED})")
print(f"  Scope original columns    : {len(_original_cols)}")
print(f"  B-created columns         : {len(_created_cols)}")
print(f"  Cleaned dataset columns   : {len(CLEANED_COLUMNS)}")
print(f"  B2 extreme-value screen -- values mutated / rows removed / missingness "
      f"created: 0 / 0 / 0 (always)")
print(f"  >=70% ordinary-missing columns flagged for audit (retained in export): "
      f"{_high_missing_ordinary_flagged_for_audit if _high_missing_ordinary_flagged_for_audit else '(none)'}")

# Raw/source columns physically removed from Batch19, each replaced by a
# deterministic B representation. The retired __missing_ind/__cat derived
# representations are a separate exclusion class, not counted here.
_all_removed_raw_source = sorted({
    c for c in (
        _adeno_detail_exclusion_removed_from_export
        + _endo_detail_exclusion_removed_from_export
        + _catunk_exclusion_removed_from_export
        + _adhesiolysis_exclusion_removed_from_export
        + _induction_exclusion_removed_from_export
    )
    if not c.endswith(("__missing_ind", "__cat"))
})
print(f"  Raw/source columns removed from Batch19 (replaced by B "
      f"representations): {len(_all_removed_raw_source)}")
for _rc, _repl in [
    ("adenomyosis_sonographic_features_clean", "adenomyosis_feature_1..11 + adenomyosis_features_unknown (B5f)"),
    ("endometrioma_size_clean / _place_clean / _laterality", "endometrioma_size_status, endometrioma_presence_laterality (B5c)"),
    ("severe_PET / any_PET", "severe_PET_cat, any_PET_cat (B5e)"),
    ("endo_surgery_adhesiolysis", "derived_endo_surgery_adhesion_status (B5g)"),
    ("indication_for_induction_clean", "indication_for_induction_status (B5h)"),
]:
    print(f"    {_rc}  ->  {_repl}")
print(f"    (also excluded: retired PPROM __missing_ind/__cat "
      f"representations: {_pprom_exclusion_removed_from_export or '(none)'})")

print("  weight_before_pregnancy / height / Hb_before_delivery: NaN preserved, "
      "not imputed here; BMI_before deterministically recomputed only where "
      "weight + height are observed (see Section B5d).")
print()

print("Feature dictionary -- B-created columns "
      f"(full 17-column dictionary -> outputs/data_cleaning/audit/cleaning_b_feature_dictionary.csv):")
if len(feature_dictionary_df):
    _fd_cols = [c for c in ["new_column", "creation_section", "predictor_classification",
                            "stage", "materialized_in_B", "model_entry_mode", "leakage_status"]
                if c in feature_dictionary_df.columns]
    print(feature_dictionary_df[_fd_cols].to_string(index=False))
else:
    print("  (none created)")
""")


# ── Section B7 (subsection, no separate number) ─────────────────────────────
SB7_HEADER = md("clean-b-s07b-header", """
### Consistency Checks (Before Export)

Audit-output only — read-only checks against the about-to-be-exported column
set (`CLEANED_COLUMNS`). No data is modified here. Every check either passes
silently (printed as PASS) or raises `AssertionError` with the exact violation
-- this section never auto-corrects a failure.
""")

SB7_CHECKS = code("clean-b-s07b-checks", """
_consistency_errors = []


def _check(label, condition_ok, detail=""):
    status = "PASS" if condition_ok else "FAIL"
    print(f"  [{status}] {label}" + (f" -- {detail}" if detail and not condition_ok else ""))
    if not condition_ok:
        _consistency_errors.append(f"{label}: {detail}")


print("Final consistency checks (before export):")

# -- row-key uniqueness / alignment --
_check("_row_key_delivery_id column exists", "_row_key_delivery_id" in df_clean.columns)
if "_row_key_delivery_id" in df_clean.columns:
    _row_key = df_clean["_row_key_delivery_id"]
    _check("_row_key_delivery_id: no missing delivery_id", int(pd.isna(_row_key).sum()) == 0,
           f"{int(pd.isna(_row_key).sum())} missing")
    _check("_row_key_delivery_id: unique per row (1:1 with the canonical source)",
           _row_key.nunique(dropna=False) == len(_row_key),
           f"{len(_row_key)} rows, {_row_key.nunique(dropna=False)} unique values")
_check(f"row count: {EXPECTED_ROWS}", len(df_clean) == EXPECTED_ROWS,
       f"got {len(df_clean)}")

# -- endo_resection_* family --
_endo_res_cols = [c for c in CLEANED_COLUMNS if c.startswith("endo_resection_")
                  and not c.endswith("__missing_ind")]
if _endo_res_cols:
    _check("endo_resection_*: 10 base indicators present", len(_endo_res_cols) == 10,
           f"found {len(_endo_res_cols)}")
    _check("endo_resection_*: zero missingness", int(df_clean[_endo_res_cols].isna().sum().sum()) == 0,
           f"{int(df_clean[_endo_res_cols].isna().sum().sum())} missing cells")
    _endo_res_ind_present = [c for c in CLEANED_COLUMNS if c.startswith("endo_resection_")
                              and c.endswith("__missing_ind")]
    _check("endo_resection_*: no __missing_ind columns in export", len(_endo_res_ind_present) == 0,
           f"found {_endo_res_ind_present}")
    if "endo_resection_no_resection" in df_clean.columns:
        _other_sites = [c for c in _endo_res_cols if c != "endo_resection_no_resection"]
        _viol = int(((df_clean["endo_resection_no_resection"] == 1) &
                      (df_clean[_other_sites] == 1).any(axis=1)).sum())
        _check("endo_resection_*: no_resection mutually exclusive with other sites", _viol == 0,
               f"{_viol} violating rows")
    if "endometriosis_surgery" in df_clean.columns and _endo_res_cols:
        _es = df_clean["endometriosis_surgery"]
        _any_pos = (df_clean[_endo_res_cols] == 1).any(axis=1)
        _v1 = int(((_es == 0) & _any_pos).sum())
        _v2 = int(((_es == 1) & (~_any_pos)).sum())
        _check("endo_resection_*: endometriosis_surgery gate holds both directions",
               _v1 == 0 and _v2 == 0, f"{_v1} surgery=0-but-positive, {_v2} surgery=1-but-all-zero")

# -- endometrioma family --
if "endometrioma_size_status" in df_clean.columns:
    _size_status = df_clean["endometrioma_size_status"]
    _allowed_size_status = {
        "no_endometrioma",
        "endometrioma_less_than_30mm",
        "endometrioma_30mm_or_more",
        "endometrioma_size_unknown",
    }
    _check("endometrioma_size_status: valid categories, no missing",
           set(_size_status.dropna().unique()).issubset(_allowed_size_status)
           and int(_size_status.isna().sum()) == 0,
           f"values={sorted(_size_status.dropna().unique().tolist())} missing={int(_size_status.isna().sum())}")
if "endometrioma_presence_laterality" in df_clean.columns:
    _presence_lat = df_clean["endometrioma_presence_laterality"]
    _check("endometrioma_presence_laterality: valid categories, exactly 5 laterality_unknown, 0 missing "
           "(unresolved applicable rows are the explicit laterality_unknown category)",
           set(_presence_lat.dropna().unique()).issubset({"none", "unilateral", "bilateral", "laterality_unknown"})
           and int(_presence_lat.isna().sum()) == 0
           and int((_presence_lat == "laterality_unknown").sum()) == 5,
           f"values={sorted(_presence_lat.dropna().unique().tolist())} missing={int(_presence_lat.isna().sum())} "
           f"laterality_unknown={int((_presence_lat == 'laterality_unknown').sum())}")
if "endometrioma" in df_clean.columns and "endometrioma_size_status" in df_clean.columns:
    _endo = df_clean["endometrioma"]
    _size_status = df_clean["endometrioma_size_status"]
    _presence_lat = df_clean["endometrioma_presence_laterality"]
    _check("endometrioma==0 implies size_status==no_endometrioma and presence_laterality==none",
           int((((_endo == 0) & (_size_status != "no_endometrioma")) | ((_endo == 0) & (_presence_lat != "none"))).sum()) == 0)
_raw_endo_detail = ["endometrioma_size_clean", "endometrioma_place_clean", "endometrioma_laterality",
                    "endometrioma_size_clean__missing_ind", "endometrioma_place_clean__missing_ind",
                    "endometrioma_laterality__missing_ind"]
_present_raw_endo = [c for c in _raw_endo_detail if c in CLEANED_COLUMNS]
_check("endometrioma raw/detail columns absent from export", len(_present_raw_endo) == 0,
       f"found {_present_raw_endo}")

# -- weight/BMI pregnancy family --
_check("weight_in_pregnancy retained as numeric secondary source",
       "weight_in_pregnancy" in CLEANED_COLUMNS and pd.api.types.is_numeric_dtype(df_clean["weight_in_pregnancy"]))
_check("weight_in_pregnancy values pass through unchanged from raw preprocessing output (NaNs preserved)",
       int((df_clean["weight_in_pregnancy"].fillna(-1) != df["weight_in_pregnancy"].fillna(-1)).sum()) == 0)
_check("weight_in_pregnancy__missing_ind absent from export (no separate indicator -- the "
       "fold-safe weight_in_pregnancy_cat representation's not_documented category carries the "
       "missingness information at modeling time)",
       "weight_in_pregnancy__missing_ind" not in CLEANED_COLUMNS)
_check("weight_in_pregnancy_cat absent from export (documented-representation-only -- "
       "fold-safe cutpoints fitted at modeling time, not materialized in B)",
       "weight_in_pregnancy_cat" not in CLEANED_COLUMNS)
# BMI_after is a secondary_near_delivery_predictor carved into df_clean and
# exported like weight_in_pregnancy above -- passed through unchanged (no
# categorical conversion, no missingness indicator). Its not_documented
# information is carried by the fold-safe BMI_after_cat representation (see
# SUPPRESSED_MISSING_INDICATOR_COLS in Section B4).
_check("BMI_after retained as a numeric secondary transform source",
       "BMI_after" in CLEANED_COLUMNS and pd.api.types.is_numeric_dtype(df_clean["BMI_after"]))
_check("BMI_after values pass through unchanged from raw preprocessing output",
       int((df_clean["BMI_after"].fillna(-1) != df["BMI_after"].fillna(-1)).sum()) == 0)
_check("BMI_after__missing_ind absent from export (no separate indicator -- the fold-safe "
       "BMI_after_cat representation's not_documented category carries the missingness "
       "information at modeling time)",
       "BMI_after__missing_ind" not in CLEANED_COLUMNS)
# BMI_after_cat is a documented representation only: B decides it, the
# fold-safe transformer at modeling time computes the actual column.
_check("BMI_after_cat absent from export (documented-representation-only -- fold-safe "
       "cutpoints fitted at modeling time, not materialized in B)",
       "BMI_after_cat" not in CLEANED_COLUMNS)
# PPROM timing status: documented representation only.
_check("gestational_age_at_PPROM_days_timing_status absent from export "
       "(documented-representation-only -- fold-safe median split fitted at modeling "
       "time, not materialized in B)",
       "gestational_age_at_PPROM_days_timing_status" not in CLEANED_COLUMNS)

# -- adenomyosis multi-hot family (Section B5f) --
_ADENO_MULTIHOT_CHECK_COLS = [f"adenomyosis_feature_{c}" for c in range(1, 12)]
if all(c in df_clean.columns for c in _ADENO_MULTIHOT_CHECK_COLS) and "adenomyosis_features_unknown" in df_clean.columns:
    _adeno_multihot_check = df_clean[_ADENO_MULTIHOT_CHECK_COLS]
    _adeno_unknown_check = df_clean["adenomyosis_features_unknown"]
    _check("adenomyosis multi-hot indicators: values in {0,1} only, no missing",
           bool(_adeno_multihot_check.isin([0, 1]).all().all())
           and int(_adeno_multihot_check.isna().sum().sum()) == 0
           and set(_adeno_unknown_check.dropna().unique()).issubset({0, 1})
           and int(_adeno_unknown_check.isna().sum()) == 0)
    if "adenomyosis" in df_clean.columns:
        _adeno_check = df_clean["adenomyosis"]
        _row_sum_check = _adeno_multihot_check.sum(axis=1)
        _check("adenomyosis==0 implies all adenomyosis_feature_* indicators and "
               "adenomyosis_features_unknown are 0",
               int((((_adeno_check == 0) & ((_row_sum_check != 0) | (_adeno_unknown_check != 0)))).sum()) == 0)
        _check("adenomyosis==1 & adenomyosis_features_unknown==0 implies at least one "
               "adenomyosis_feature_* indicator is 1",
               int((((_adeno_check == 1) & (_adeno_unknown_check == 0) & (_row_sum_check == 0))).sum()) == 0)
_check("adenomyosis_sonographic_features_clean absent from export "
       "(represented in Batch19 by the adenomyosis multi-hot representation, Section B5f)",
       "adenomyosis_sonographic_features_clean" not in CLEANED_COLUMNS)
_check("adenomyosis_sonographic_features_status absent from export "
       "(the combination-level categorical is not created; multi-hot is the representation)",
       "adenomyosis_sonographic_features_status" not in CLEANED_COLUMNS)
_check("adenomyosis_sonographic_features_clean__missing_ind absent from export "
       "(row-applicability gated -- never created)",
       "adenomyosis_sonographic_features_clean__missing_ind" not in CLEANED_COLUMNS)

# -- diagnosis_year family: none of the three may be predictor-eligible.
# diagnosis_year is source_or_text_audit_exclude, outside CLEANING_SCOPE, so
# neither it nor its missingness indicator is created in the cleaned export.
_check("diagnosis_year absent from cleaned export (source_or_text_audit_exclude)",
       "diagnosis_year" not in CLEANED_COLUMNS)
_check("diagnosis_year__missing_ind absent from cleaned export",
       "diagnosis_year__missing_ind" not in CLEANED_COLUMNS)
_check("diagnosis_year_cat absent from export", "diagnosis_year_cat" not in CLEANED_COLUMNS)

# -- induction family --
if "induction_any_bin" in df_clean.columns and "indication_for_induction_clean" in df_clean.columns:
    _anybin = df_clean["induction_any_bin"]
    _ind = df_clean["indication_for_induction_clean"]
    _v = int(((_anybin == 0) & _ind.notna()).sum())
    _check("induction_any_bin==0 with non-missing indication: none remain", _v == 0, f"{_v} rows")

# -- indication_for_induction_status (Section B5h) --
if "indication_for_induction_status" in df_clean.columns:
    _induction_status_check = df_clean["indication_for_induction_status"]
    _check("indication_for_induction_status: no missing", int(_induction_status_check.isna().sum()) == 0,
           f"missing={int(_induction_status_check.isna().sum())}")
    _check("indication_for_induction_status present in export", "indication_for_induction_status" in CLEANED_COLUMNS)
    if "induction_any_bin" in df_clean.columns:
        _anybin_check = df_clean["induction_any_bin"]
        _check("indication_for_induction_status==no_induction iff induction_any_bin==0",
               int(((_anybin_check == 0) != (_induction_status_check == "no_induction")).sum()) == 0)
_check("indication_for_induction_clean absent from export "
       "(represented in Batch19 by indication_for_induction_status, Section B5h)",
       "indication_for_induction_clean" not in CLEANED_COLUMNS)

# -- derived_endo_surgery_adhesion_status (Section B5g) --
if "derived_endo_surgery_adhesion_status" in df_clean.columns:
    _adhesion_status_check = df_clean["derived_endo_surgery_adhesion_status"]
    _allowed_adhesion_status = {
        "no_prior_endo_surgery",
        "prior_surgery_with_documented_adhesions",
        "prior_surgery_without_documented_adhesions",
    }
    _check("derived_endo_surgery_adhesion_status: valid categories, no missing",
           set(_adhesion_status_check.dropna().unique()).issubset(_allowed_adhesion_status)
           and int(_adhesion_status_check.isna().sum()) == 0,
           f"values={sorted(_adhesion_status_check.dropna().unique().tolist())} "
           f"missing={int(_adhesion_status_check.isna().sum())}")
    _check("derived_endo_surgery_adhesion_status present in export", "derived_endo_surgery_adhesion_status" in CLEANED_COLUMNS)
    if "endometriosis_surgery" in df_clean.columns:
        _surg_check = df_clean["endometriosis_surgery"]
        _check("endometriosis_surgery==0 implies derived_endo_surgery_adhesion_status==no_prior_endo_surgery",
               int(((_surg_check == 0) & (_adhesion_status_check != "no_prior_endo_surgery")).sum()) == 0)
_check("endo_surgery_adhesiolysis absent from export "
       "(represented in Batch19 by derived_endo_surgery_adhesion_status, Section B5g)",
       "endo_surgery_adhesiolysis" not in CLEANED_COLUMNS)

# -- nulliparity / P canonical-parity consistency --
# nulliparity is the canonical parity indicator, corrected directly from P in
# preprocessing and consumed as-is here -- Data Cleaning B does not re-derive,
# invert, or rename it, and does not create parity_binary_0_vs_1plus.
_check("nulliparity present in export", "nulliparity" in df_clean.columns)
_check("P present in export", "P" in df_clean.columns)
_check("parity_binary_0_vs_1plus absent from export",
       "parity_binary_0_vs_1plus" not in df_clean.columns)
if "nulliparity" in df_clean.columns:
    _null = df_clean["nulliparity"]
    _check("nulliparity: values in {0, 1, missing}",
           set(_null.dropna().unique()).issubset({0, 1, 0.0, 1.0}),
           f"values={sorted(_null.dropna().unique().tolist())}")
    if "P" in df_clean.columns:
        _p_num = pd.to_numeric(df_clean["P"], errors="coerce")
        _valid_p = _p_num.notna() & (_p_num >= 0) & (_p_num == _p_num.round())
        _mismatch_p0 = int((_valid_p & (_p_num == 0) & (_null != 1)).sum())
        _mismatch_p1 = int((_valid_p & (_p_num >= 1) & (_null != 0)).sum())
        _check("nulliparity consistent with P (valid P==0 -> nulliparity==1)",
               _mismatch_p0 == 0, f"{_mismatch_p0} row(s)")
        _check("nulliparity consistent with P (valid P>=1 -> nulliparity==0)",
               _mismatch_p1 == 0, f"{_mismatch_p1} row(s)")
_check(f"target distribution: 0={EXPECTED_N0}/1={EXPECTED_N1}",
       int((df_clean[TARGET_COL] == 0).sum()) == EXPECTED_N0
       and int((df_clean[TARGET_COL] == 1).sum()) == EXPECTED_N1,
       f"got 0={int((df_clean[TARGET_COL]==0).sum())}/1={int((df_clean[TARGET_COL]==1).sum())}")

# -- general binary-variable validity sweep across the final export column set --
_bad_binary = []
for _c in CLEANED_COLUMNS:
    if _c == TARGET_COL or _c not in df_clean.columns:
        continue
    _s = df_clean[_c].dropna()
    if _s.empty:
        continue
    if _s.nunique() <= 3 and set(_s.unique()).issubset({0, 1, 0.0, 1.0, True, False}) and _s.nunique() <= 2:
        pass  # genuinely binary, already valid by construction of this branch
    elif _s.nunique() <= 2 and not set(_s.unique()).issubset({0, 1, 0.0, 1.0}):
        # looks binary-cardinality but uses non-0/1 codes -- flag for manual review, not auto-failed
        _bad_binary.append((_c, sorted(_s.unique().tolist())))
_check("no unexpected non-0/1 binary-cardinality columns found", len(_bad_binary) == 0, f"{_bad_binary}")

# -- Section B3 transformation-review audit --
_transform_review_target_used = [
    r["variable"] for r in transformation_review_log if r.get("target_used_for_decision")
]
_check("transformation-review audit is target-blind for every reviewed variable",
       len(_transform_review_target_used) == 0, f"{_transform_review_target_used}")
_ALLOWED_TRANSFORM_DECISIONS = {"raw_no_fixed_power_transform", "not_applicable_discrete_count"}
_unexpected_transform_decisions = sorted({
    r["primary_power_transform_decision"] for r in transformation_review_log
} - _ALLOWED_TRANSFORM_DECISIONS)
_check("transformation-review audit contains only approved decision labels",
       len(_unexpected_transform_decisions) == 0, f"{_unexpected_transform_decisions}")
_check("transformation-review audit reviewed at least the 6-variable continuous pool "
       "(AGE, weight_before_pregnancy, height, BMI_before, Hb_before_delivery, "
       "gestational_age_at_delivery_days)",
       {"AGE", "weight_before_pregnancy", "height", "BMI_before", "Hb_before_delivery",
        "gestational_age_at_delivery_days"}.issubset(
           {r["variable"] for r in transformation_review_log
            if r["continuous_or_discrete"] == "continuous"}))
_check("no log/log1p/sqrt/Box-Cox/Yeo-Johnson transform column exists in the export",
       not any(_c.endswith(("_log", "_log1p", "_sqrt", "_boxcox", "_yeojohnson"))
               for _c in CLEANED_COLUMNS))

# -- fail-loud export-contract invariants ------------------------------------
# A. The exported column list must have no duplicate entries.
_check("CLEANED_COLUMNS has no duplicate entries",
       len(CLEANED_COLUMNS) == len(set(CLEANED_COLUMNS)),
       f"{len(CLEANED_COLUMNS)} entries, {len(set(CLEANED_COLUMNS))} unique")

# B. The target column appears exactly once in the exported column list.
_check("target column appears exactly once in CLEANED_COLUMNS",
       CLEANED_COLUMNS.count(TARGET_COL) == 1,
       f"count={CLEANED_COLUMNS.count(TARGET_COL)}")

# C. No patient/technical identifier leaks into the analytical export columns.
# _row_key_delivery_id MUST still exist on df_clean (checked above) -- this is
# strictly an analytical-export-column check, not a df_clean check.
_id_like_in_export = [c for c in ("_row_key_delivery_id", "delivery_id", "subject_number")
                      if c in CLEANED_COLUMNS]
_check("no patient/technical identifier column in the analytical export "
       "(_row_key_delivery_id/delivery_id/subject_number)",
       len(_id_like_in_export) == 0, f"found {_id_like_in_export}")
_check("_row_key_delivery_id still present internally on df_clean "
       "(export-column check above must not have removed it)",
       "_row_key_delivery_id" in df_clean.columns)

# D. The feature dictionary must not register the same new_column twice.
if len(feature_dictionary_df):
    _fd_dupes = int(feature_dictionary_df["new_column"].duplicated().sum())
    _check("feature_dictionary_df has no duplicate new_column entries",
           _fd_dupes == 0, f"{_fd_dupes} duplicate new_column value(s)")

# E. Frozen current Batch19 schema-count regression gate. 82 is the current
# approved Batch19 schema count (431 rows x 82 columns, target 370/61). A
# future approved schema revision may deliberately update this value -- it is
# a frozen-cohort regression gate, not a permanent architectural invariant.
_FROZEN_BATCH19_COLUMN_COUNT = 82
_check(f"CLEANED_COLUMNS matches the frozen Batch19 schema count "
       f"({_FROZEN_BATCH19_COLUMN_COUNT})",
       len(CLEANED_COLUMNS) == _FROZEN_BATCH19_COLUMN_COUNT,
       f"got {len(CLEANED_COLUMNS)}")

print()
if _consistency_errors:
    raise AssertionError(
        "FINAL CONSISTENCY CHECKS FAILED:\\n" + "\\n".join(f"  - {e}" for e in _consistency_errors)
    )
print(f"All final consistency checks PASSED ({len(CLEANED_COLUMNS)} columns about to be exported).")
""")


SB8_EXPORT = code("clean-b-s07-export", """
# Output paths (only under outputs/data_cleaning/)
_OUT_BASE = (_root / "outputs" / "data_cleaning") if _root \\
    else Path("outputs/data_cleaning")
_OUT_PROCESSED = _OUT_BASE / "processed"
_OUT_AUDIT = _OUT_BASE / "audit"
CLEANED_DATASET_NAME = "work_df_batch19_after_data_cleaning_b.xlsx"
_cleaned_path = _OUT_PROCESSED / CLEANED_DATASET_NAME
_feature_dictionary_path = _OUT_AUDIT / "cleaning_b_feature_dictionary.csv"
_manifest_path = _OUT_AUDIT / "cleaning_b_manifest.json"

# Hard guard: never write inside the preprocessing tree.
_resolved = str(_OUT_BASE.resolve())
if "preprocessing" in _resolved.replace("\\\\", "/").lower():
    raise RuntimeError(f"SAFETY ABORT: output base resolves into preprocessing tree: {_resolved}")

if not EXPORT_FOR_EDA_C:
    print("EXPORT_FOR_EDA_C = False -> nothing written.")
    # This dry-run inventory lists the complete 13-artifact contract, matching
    # the B7 "When enabled" markdown table above: 1 patient-level workbook, 1
    # patient-level audit CSV, 1 ID-only row-alignment sidecar, and 10
    # aggregate audit files.
    print("Would write (when enabled) -- 13 B-owned artifacts:")
    print(f"  {_rel(_cleaned_path)}  [patient-level, gitignored]")
    print(f"  {_rel(_OUT_AUDIT)}/cleaning_b_row_actions_patient_level.csv  [patient-level, gitignored]")
    print(f"  {_rel(_OUT_AUDIT)}/cleaning_b_output_delivery_id_key.csv  [ID-only row-alignment sidecar, gitignored]")
    print(f"  {_rel(_manifest_path)}")
    print(f"  {_rel(_OUT_AUDIT)}/cleaning_b_column_actions.csv")
    print(f"  {_rel(_OUT_AUDIT)}/cleaning_b_missingness_handling.csv")
    print(f"  {_rel(_OUT_AUDIT)}/cleaning_b_outlier_handling.csv")
    print(f"  {_rel(_OUT_AUDIT)}/outlier_extreme_value_final_adjudication.csv")
    print(f"  {_rel(_OUT_AUDIT)}/cleaning_b_imputation_plan.csv")
    print(f"  {_rel(_feature_dictionary_path)}")
    print(f"  {_rel(_OUT_AUDIT)}/cleaning_b_final_numeric_transformation_review.csv")
    print(f"  {_rel(_OUT_AUDIT)}/cleaning_b_variable_classification_snapshot.csv")
    print(f"  {_rel(_OUT_AUDIT)}/cleaning_b_variable_type_schema_snapshot.csv")
else:
    _OUT_PROCESSED.mkdir(parents=True, exist_ok=True)
    _OUT_AUDIT.mkdir(parents=True, exist_ok=True)

    # Never overwrite the preprocessing source.
    if _cleaned_path.name == SOURCE_BATCH_NAME:
        raise RuntimeError("SAFETY ABORT: cleaned dataset name collides with source batch18.")

    # The row-order sidecar is constructed and its row-count / row-order
    # alignment assertions run BEFORE writing any canonical file, so a broken
    # invariant is caught before either on-disk file is produced.
    #
    # Row-order delivery_id sidecar -- delivery_id is NEVER included in
    # CLEANED_COLUMNS/the cleaned dataset itself (C0 safety rule); this is a
    # separate, id-only file. Built from this SAME df_clean object, in the
    # SAME row order as the cleaned file written below (df_clean[[...]] is a
    # column-only selection either way, so both come from identical rows in
    # identical order). This makes the sidecar's row i correspond to
    # _cleaned_path's row i by construction, regardless of any
    # filter/reorder/merge that may have happened to df_clean anywhere
    # between load (part 1) and here -- delivery_id was attached as a real
    # column at load time and has traveled with each row ever since.
    # EDA C reads this to continue the same guarantee; see
    # eda_c_part1_setup_gate.py.
    _row_key_path = _OUT_AUDIT / "cleaning_b_output_delivery_id_key.csv"
    _row_key_sidecar_df = pd.DataFrame({
        "row_index": range(len(df_clean)),
        "delivery_id": df_clean["_row_key_delivery_id"].to_numpy(),
    })

    # Sidecar row-count / ordering alignment assertions. The sidecar is built
    # from this exact df_clean object, in this exact row order, at this exact
    # point -- but assert it explicitly rather than relying only on that
    # construction guarantee, so any future refactor that breaks the invariant
    # fails loudly here, before a single canonical file is written.
    if len(_row_key_sidecar_df) != len(df_clean):
        raise AssertionError(
            f"ROW-KEY SIDECAR POSTCONDITION FAILED: sidecar has "
            f"{len(_row_key_sidecar_df)} rows, cleaned output has {len(df_clean)} rows."
        )
    if not (_row_key_sidecar_df["delivery_id"].to_numpy() == df_clean["_row_key_delivery_id"].to_numpy()).all():
        raise AssertionError(
            "ROW-KEY SIDECAR POSTCONDITION FAILED: sidecar delivery_id order does not "
            "exactly match df_clean's row order."
        )

    # Assertions passed -- now write the canonical Batch19 workbook, then the
    # sidecar.
    df_clean[CLEANED_COLUMNS].to_excel(_cleaned_path, index=False, engine="openpyxl")
    _row_key_sidecar_df.to_csv(_row_key_path, index=False)
    print(f"  Row-order ID key written: {_rel(_row_key_path)}  [id-only, gitignored] "
          f"({len(_row_key_sidecar_df)} rows, order-verified against df_clean)")

    # Output provenance hash.
    _ho = hashlib.sha256()
    with open(_cleaned_path, "rb") as _fh:
        for _block in iter(lambda: _fh.read(1 << 20), b""):
            _ho.update(_block)
    _output_sha = _ho.hexdigest()

    _n0c = int((df_clean[TARGET_COL] == 0).sum())
    _n1c = int((df_clean[TARGET_COL] == 1).sum())
    manifest = {
        "stage": "data_cleaning_b",
        "created_utc": _dt.now(_tz.utc).isoformat(timespec="seconds"),
        "input_file": SOURCE_BATCH_NAME,
        "input_sha256": INPUT_SHA256,
        "output_file": CLEANED_DATASET_NAME,
        "output_sha256": _output_sha,
        "input_rows": int(len(df)),
        "cleaned_rows": int(len(df_clean)),
        "row_exclusions_applied": bool(ROW_EXCLUSIONS_APPLIED),
        "target_0": _n0c,
        "target_1": _n1c,
        "scope_original_columns": len(_original_cols),
        "b_created_columns": len(_created_cols),
        "cleaned_columns_total": len(CLEANED_COLUMNS),
        # Only the retired derived __missing_ind/__cat representations are
        # excluded from export; the raw gestational_age_at_PPROM_days column is
        # retained for audit and admitted to EDA C's model-candidate pool
        # (ANALYSIS_VARS) tagged model_entry_mode=transform_source_only, so it
        # feeds the fold-safe timing transformer but never enters a design
        # matrix as a plain numeric predictor.
        "pprom_timing_derived_family_excluded_from_export": True,
        "pprom_timing_raw_column_retained_in_export": "gestational_age_at_PPROM_days" in CLEANED_COLUMNS,
        "pprom_timing_feature_family_requested": _pprom_exclusion_requested,
        "pprom_timing_feature_family_present_before_exclusion": _pprom_exclusion_present_before,
        "pprom_timing_feature_family_excluded_from_output": _pprom_exclusion_removed_from_export,
        "pprom_timing_feature_family_absent_before_exclusion": _pprom_exclusion_absent,
        "pprom_timing_feature_family_exclusion_reason": (
            f"gestational_age_at_PPROM_days has {_n_pprom_missing} missing values "
            f"({round(_n_pprom_missing/len(df_clean)*100,1) if _n_pprom_missing is not None else '?'}%) "
            "whole-cohort (PRIMARY figure; structural-applicability-aware "
            "sensitivity/diagnostic missingness is 5.9%: 1/17 applicable "
            "PPROM==1 rows genuinely missing -- diagnostic only, does not "
            "replace the PRIMARY whole-cohort figure). Raw column retained in the cleaned/audit "
            "export and admitted to EDA C's model-candidate pool (ANALYSIS_VARS), "
            "tagged model_entry_mode=transform_source_only -- it may feed the fold-safe "
            "timing transformer internally but must never independently enter a "
            "design matrix as a plain numeric predictor. Retired derived "
            "missingness/Unknown encodings (__missing_ind/__cat) remain excluded "
            "from export, superseded by the documented-only "
            "gestational_age_at_PPROM_days_timing_status. See "
            "structural_missingness_registry.py APPLICABILITY_LINKED_NO_PREPROCESSING_MASK "
            "for the structural-vs-undocumented missingness breakdown."
        ),
        "endo_resection_structural_recode_applied": True,
        "endo_resection_recode_cols": list(ENDO_RESECTION_RECODE_COLS),
        # weight_in_pregnancy is a numeric secondary-family variable: NaNs
        # preserved, no categorical representation materialized in B, and no
        # standalone missingness indicator (the fold-safe weight_in_pregnancy_cat
        # not_documented bucket carries the missingness information).
        # BMI_after_cat is not computed as a df_clean column: its q33/q67
        # cutpoints are fitted training-fold-only by a fold-safe transformer at
        # modeling time, so there is no single full-cohort value to report here.
        "BMI_after_cat_materialized_in_B": False,
        "BMI_after_cat_cutpoint_source": "fold_safe_training_only",
        "weight_in_pregnancy_cat_materialized_in_B": False,
        "weight_in_pregnancy_cat_cutpoint_source": "fold_safe_training_only",
        "gestational_age_at_PPROM_days_timing_status_materialized_in_B": False,
        "gestational_age_at_PPROM_days_timing_status_cutpoint_source": "fold_safe_training_only",
        "gestational_age_at_PPROM_days_timing_status_applicable_n": _n_pprom_applicable,
        "gestational_age_at_PPROM_days_timing_status_genuine_missing_applicable_n": _n_pprom_timing_missing_applicable,
        # Adenomyosis sonographic features are represented as the multi-hot
        # indicator family (below); there is no combination-level categorical
        # and no imputation.
        "adenomyosis_multihot_imputation_method": "none",
        "adenomyosis_multihot_per_code_counts": {
            str(k): v for k, v in _adeno_multihot_counts.items()
        } if "_adeno_multihot_counts" in dir() else {},
        "adenomyosis_features_unknown_count": int(_n_unknown) if "_n_unknown" in dir() else None,
        "adenomyosis_detail_excluded_from_output": _adeno_detail_exclusion_removed_from_export,
        "adenomyosis_detail_exclusion_reason": (
            "adenomyosis_sonographic_features_clean is row-applicability gated "
            "(adenomyosis==1) and replaced in the export by the deterministic, lossless "
            "multi-hot representation (adenomyosis_feature_1..11 + adenomyosis_features_unknown), "
            "in place of a combination-level adenomyosis_sonographic_features_status categorical."
        ),
        "endometrioma_size_status_cutoff_mm": SIZE_STATUS_CUTOFF_MM,
        "endometrioma_size_status_imputation_method": "none",
        "endometrioma_size_status_counts": {
            str(k): v for k, v in df_clean["endometrioma_size_status"].value_counts(dropna=False).to_dict().items()
        },
        "endometrioma_presence_laterality_imputation_method": (
            "none; unresolved laterality is the explicit laterality_unknown category, "
            "not imputed and not true missing"
        ),
        "endometrioma_presence_laterality_counts": {
            str(k): v for k, v in df_clean["endometrioma_presence_laterality"].value_counts(dropna=False).to_dict().items()
        },
        "endometrioma_detail_excluded_from_output": _endo_detail_exclusion_removed_from_export,
        "endometrioma_detail_exclusion_reason": (
            "endometrioma_size_clean, endometrioma_place_clean, and endometrioma_laterality "
            "(and their __missing_ind indicators) are replaced by deterministic derived "
            "variables endometrioma_size_status and endometrioma_presence_laterality. "
            "endometrioma_size_status distinguishes no endometrioma, known <30mm, known >=30mm, "
            "and endometrioma present with genuinely unknown size, without upstream size imputation. "
            "endometrioma_presence_laterality represents genuinely unresolved endometrioma==1 "
            "laterality as the explicit laterality_unknown category "
            "(0 missing) rather than full-cohort mode-imputing it or leaving it as true NaN."
        ),
        "pending_timing_confirmation_classification": "intrapartum_candidate_pending_timing_confirmation",
        "pending_timing_confirmation_columns": list(PENDING_TIMING_CONFIRMATION_COLS),
        "pending_timing_confirmation_exclusion_reason": (
            "Variables known or potentially known during labor whose availability before "
            "the intrapartum cesarean decision has not yet been clinically confirmed. "
            "Data Cleaning B preserves its existing cleaning/audit handling for these "
            "columns, but downstream EDA/modeling must exclude them from primary and "
            "secondary predictor pools pending clinical timing confirmation."
        ),
        # Always 0. Preprocessing owns data-quality sanity gates; the Section B2
        # outlier review is a target-blind descriptive screen that mutates
        # nothing. Retained as a manifest key for backward-compatible schema.
        "values_outside_plausibility_range_flagged_for_review": int(n_outside_plausibility_range),
        # Section B2 outlier-review extreme-value closure invariants -- always
        # these exact values; this section never removes a row, sets a value
        # missing, clips, or winsorizes, and never reads the target column.
        # JSON keys keep a "b4_" prefix for backward-compatible manifest schema.
        "b4_extreme_value_values_mutated": 0,
        "b4_extreme_value_rows_removed": 0,
        "b4_extreme_value_missingness_created": 0,
        "b4_extreme_value_target_used": False,
        # weight_before_pregnancy / height / Hb_before_delivery are not imputed
        # in Data Cleaning B; NaN is preserved and median imputation is fitted
        # training-fold-only in modeling.
        "anthropometry_hb_missing_data_handling": {
            "weight_before_pregnancy": WEIGHT_BEFORE_IMPUTATION_METHOD,
            "height": HEIGHT_IMPUTATION_METHOD,
            "BMI_before": "deterministic recompute from observed weight/height only (formula-exact); NaN preserved otherwise",
            "Hb_before_delivery": HB_IMPUTATION_METHOD,
        },
        "pet_categorical_conversion": {
            "severe_PET_cat": (
                "not imputed; categorical + not_documented (Decision 27); mechanism screen found "
                "significant association with AGE -- evidence against MCAR, compatible with MAR, "
                "not by itself proof of MNAR or that imputation is impossible"
            ),
            "any_PET_cat": (
                "not imputed; categorical + not_documented (Decision 27); mechanism screen found "
                "significant association with AGE -- evidence against MCAR, compatible with MAR, "
                "not by itself proof of MNAR or that imputation is impossible"
            ),
        },
        "diagnosis_year_family_status": (
            "diagnosis_year is classified source_or_text_audit_exclude (a "
            "calendar-time-of-diagnosis field; not predictor-eligible). It is outside "
            "CLEANING_SCOPE and absent from this cleaned export entirely -- "
            "diagnosis_year__missing_ind is not created (its source is out of scope), and "
            "diagnosis_year_cat is not created. None of the three enter this or any "
            "downstream candidate/modeling pool."
        ),
        "execute_learned_imputation": bool(EXECUTE_LEARNED_IMPUTATION),
        "execute_learned_imputation_meaning": (
            "Retired flag, kept only for backward-compatible manifest schema; it has no "
            "operational effect. Data Cleaning B performs no learned imputation in any form. "
            "weight_before_pregnancy, height, and Hb_before_delivery are not imputed here "
            "(NaN preserved); BMI_before is deterministically recomputed only from observed "
            "weight+height. endometrioma_size_status/endometrioma_presence_laterality are not "
            "imputed (Section B5c). The adenomyosis multi-hot representation "
            "(adenomyosis_feature_1..11 + adenomyosis_features_unknown) is not imputed "
            "(Section B5f). severe_PET/any_PET are not imputed -- see "
            "pet_categorical_conversion above; diagnosis_year is not part of this cleaned "
            "export at all (see diagnosis_year_family_status). Any learned imputation "
            "belongs in the modeling pipeline, fitted only within each grouped "
            "(subject_number) training fold."
        ),
        "export_for_eda_c": bool(EXPORT_FOR_EDA_C),
    }
    with open(_manifest_path, "w", encoding="utf-8") as _f:
        json.dump(manifest, _f, indent=2, ensure_ascii=False)

    pd.DataFrame(column_actions_log).to_csv(_OUT_AUDIT / "cleaning_b_column_actions.csv", index=False)
    pd.DataFrame(missingness_log).to_csv(_OUT_AUDIT / "cleaning_b_missingness_handling.csv", index=False)
    pd.DataFrame(outlier_log).to_csv(_OUT_AUDIT / "cleaning_b_outlier_handling.csv", index=False)

    # Compact final target-blind extreme-value adjudication table.
    # Derived deterministically from outlier_log -- every row is a KEEP; the
    # four invariant columns are constant by construction. Human-readable
    # record: docs/finalization/outlier_extreme_value_handling_closure.md
    _adj_rows = []
    for _r in outlier_log:
        _n_ex = _r.get("n_iqr_outliers", 0)
        _adj_rows.append({
            "variable": _r["column"],
            "observed_extreme_summary": (
                f"{_n_ex} value(s) beyond 1.5xIQR fence "
                f"[{_r.get('iqr_lower')}, {_r.get('iqr_upper')}]; "
                f"observed range [{_r.get('min')}, {_r.get('max')}]"
                if _n_ex else "no IQR-flagged value"
            ),
            "screening_method": _r.get("screening_method", "iqr_1p5_descriptive"),
            "source_or_consistency_evidence": _r.get("final_reason", ""),
            "final_decision": _r.get("final_decision", "keep"),
            "final_reason": _r.get("final_reason", ""),
            "data_mutated": False,
            "row_removed": False,
            "created_missingness": False,
            "clinical_dependency_status": _r.get(
                "clinical_dependency_status", "closed_no_consultation_required"),
            "target_used_for_decision": False,
        })
    pd.DataFrame(_adj_rows).to_csv(
        _OUT_AUDIT / "outlier_extreme_value_final_adjudication.csv", index=False)
    pd.DataFrame(imputation_plan).to_csv(_OUT_AUDIT / "cleaning_b_imputation_plan.csv", index=False)
    feature_dictionary_df.to_csv(_feature_dictionary_path, index=False)
    pd.DataFrame(row_actions).to_csv(_OUT_AUDIT / "cleaning_b_row_actions_patient_level.csv", index=False)

    # Section B3 pure continuous transformation-review audit. Every row is
    # target-blind by construction (target_used_for_decision is always
    # False -- asserted in Section B3 itself).
    _transformation_review_path = _OUT_AUDIT / "cleaning_b_final_numeric_transformation_review.csv"
    pd.DataFrame(transformation_review_log).to_csv(_transformation_review_path, index=False)

    # Classification-lineage: save the Data Cleaning B snapshot (fresh copy of
    # the immutable preprocessing files plus exactly the approved DCB
    # registrations above). Never touches the preprocessing files themselves.
    _dcb_cls_snapshot_path, _dcb_schema_snapshot_path = classification_lineage.save_data_cleaning_b_snapshot(
        dcb_classification_snapshot, dcb_type_schema_snapshot, root=_root,
    )
    print(f"Classification-lineage snapshot saved: {_rel(_dcb_cls_snapshot_path)}")
    print(f"                                       {_rel(_dcb_schema_snapshot_path)}")

    print(f"Cleaned dataset written: {_rel(_cleaned_path)}")
    print(f"  SHA-256: {_output_sha[:24]}...  | rows={len(df_clean)} cols={len(CLEANED_COLUMNS)}")
    print(f"Audit logs written to: {_rel(_OUT_AUDIT)}")
    print(f"  Transformation-review audit: {_rel(_transformation_review_path)} "
          f"({len(transformation_review_log)} rows)")
    print("Reminder: patient-level files are gitignored and must never be committed.")

print()
print("=" * 70)
print("B FINAL VERIFICATION (Colab/local, run last)")
print("=" * 70)
_required_files = {
    "work_df_batch19_after_data_cleaning_b.xlsx": _cleaned_path,
    "cleaning_b_feature_dictionary.csv": _feature_dictionary_path,
    "cleaning_b_manifest.json": _manifest_path,
    "variable_classification_minimal.csv (source, not a B output)": Path(CLASSIFICATION_PATH),
}
for _label, _path in _required_files.items():
    print(f"  [{'PASS' if _path.is_file() else 'FAIL'}] {_label} exists ({_rel(_path)})")

print()
# Frozen-cohort baseline centralization: EXPECTED_ROWS/N0/N1 are
# Part 1's own globals (set from preprocessing_config.py's
# CURRENT_APPROVED_COHORT_ROWS/TARGET_N0/TARGET_N1, the single authoritative
# source), reused here rather than independently re-declaring the same
# literal a second time within Data Cleaning B -- same pattern already used
# for CLASSIFICATION_PATH above. This is a CURRENT FROZEN-COHORT REGRESSION
# GATE, not a permanent architectural invariant.
print(f"  Row count       : {len(df_clean)} (expected {EXPECTED_ROWS})")
print(f"  Target 0        : {int((df_clean[TARGET_COL] == 0).sum())} (expected {EXPECTED_N0})")
print(f"  Target 1        : {int((df_clean[TARGET_COL] == 1).sum())} (expected {EXPECTED_N1})")
print()
print("  B output paths:")
print(f"    {_rel(_cleaned_path)}")
print(f"    {_rel(_feature_dictionary_path)}")
print(f"    {_rel(_manifest_path)}")

B_VERIFICATION_PASSED = (
    all(_p.is_file() for _p in [_cleaned_path, _feature_dictionary_path, _manifest_path])
    and len(df_clean) == EXPECTED_ROWS
    and int((df_clean[TARGET_COL] == 0).sum()) == EXPECTED_N0
    and int((df_clean[TARGET_COL] == 1).sum()) == EXPECTED_N1
)
print()
print(f"B_VERIFICATION_PASSED = {B_VERIFICATION_PASSED}")
print("=" * 70)
""")

SB8_CLOSE = md("clean-b-s07-close", """
### End of Data Cleaning B

Data Cleaning B took the preprocessing output and produced a derived cleaned
dataset, Batch19, together with a full audit trail. The cohort and the target
are unchanged from preprocessing:

- **431 deliveries retained** — no analytical row was removed, deduplicated, or
  reordered.
- **Target distribution unchanged: 370 vaginal / 61 intrapartum cesarean.**
- Deterministic derived representations were created only where clinically and
  methodologically justified (endometrioma size / laterality status, the
  adenomyosis multi-hot family, PET categoricals, prior-surgery adhesion status,
  induction-indication status).
- Original NaNs were preserved for every variable whose treatment requires
  downstream fold-safe processing.
- **No learned or data-dependent preprocessing parameter was fitted on the full
  cohort.** Learned medians and quantile / timing cutpoints are fitted
  training-fold-only during modeling cross-validation.
- The final Batch19 contains **82 analytical columns**.
- All final consistency checks passed.

Batch19 is the **canonical input to EDA C**
(`04_eda_c_modeling_handoff.ipynb`), which validates every column against the
classification CSV, the feature dictionary, and the manifest written here.
""")


CLEANING_B_PART5_CELLS = [
    SB8_HEADER,
    SB8_SUMMARY,
    SB7_HEADER,
    SB7_CHECKS,
    SB8_EXPORT,
    SB8_CLOSE,
]


if __name__ == "__main__":
    print(f"Data Cleaning B Part 5 cells defined: {len(CLEANING_B_PART5_CELLS)}")

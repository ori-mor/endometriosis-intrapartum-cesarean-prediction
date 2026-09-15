#!/usr/bin/env python3
"""Data Cleaning B — Part 4 cell definitions (sections B5–B6).

Decision 92 (2026-08-29): the former Section B5's binary-dtype-normalization
step and its descriptive-skewness/continuous-transformation-review step were
two conceptually different activities that used to share one cell
(`SB5_TRANSFORM`). They are now split: the skewness/transformation-decision
review moved to the new, standalone Section B3 (see
cleaning_b_part3b_transformation_review.py), which now runs immediately
after the outlier review and before missingness assessment. Binary-dtype
normalization is NOT part of a continuous-transformation decision -- it
remains here, downstream (after missingness assessment, alongside the other
final derived/model-facing representation sections), renamed Section B5a for
clarity now that it no longer shares a cell with the transformation review.
`SB5_HEADER`/`SB5_TRANSFORM` keep their historical Python variable names for
stability (existing tests reference them by name); only the cell `id`
strings and markdown section-label text changed. See
docs/clinical_decisions/manual_decisions_log.md Decision 92.

B5a — Binary type normalization (deterministic, rule-based only; formerly
      part of Section B5, "Transformations and Type Conversions").
B5b — weight_in_pregnancy, BMI_after, gestational_age_at_PPROM_days timing:
      Data Cleaning B CLOSES the representation/METHOD decision (fold-safe
      observed-value tertile categories for the first two; a four-state
      structural/applicability-gated timing split for the third -- Decision
      91, 2026-08-27) and materializes NOTHING as a df_clean column for any
      of the three (retired full-cohort tertile machinery deleted
      2026-08-25/2026-08-27). Cutpoint/split-point FITTING is deferred to
      modeling training folds only (see modeling_core.py's
      FoldSafeQuantileCategoryTransformer) -- this is a fitting-location
      deferral, not an open methodological question. BMI_after was excluded
      from Data Cleaning B entirely 2026-08-25 to 2026-08-27; restored
      2026-08-27 (Decision 86, supersedes Decision 69) as a plain numeric
      secondary predictor, passed through unchanged like weight_in_pregnancy
      -- both are tagged transform_source_only and must never independently
      enter a design matrix as a plain numeric predictor.
B5c — Endometrioma derived variables: structural not-applicable coding.
      endometrioma_presence_laterality's genuinely unresolved laterality
      rows are the explicit `laterality_unknown` category (Decision 91,
      2026-08-27, supersedes the true-NaN representation approved by
      Decisions 24/25) -- the final column has 0 missing; no downstream
      categorical imputation is needed or performed for these 5 rows.
B5d — weight_before_pregnancy, height, Hb_before_delivery: Decision 71
      (2026-08-16, missing-data architecture correction) removed Decision
      27's global KNN for these three as an imputation-leakage risk, left
      Data Cleaning B preserving NaN with no imputation performed there, and
      deferred final imputation to a training-fold-only modeling-stage
      method WITHOUT selecting that method. The Decision-91 targeted
      missingness closure (2026-08-28 addendum) now records the APPROVED
      final method as ordinary median imputation, fitted training-fold-only
      in modeling (SimpleImputer inside modeling_core.py's shared
      ColumnTransformer) -- a fitting-location deferral, not an
      unspecified/undecided downstream strategy. BMI_before
      is deterministically recomputed only from observed weight+height in
      Data Cleaning B; when BMI_before is selected for modeling and either
      input is missing for a row, modeling_core.py's
      FoldSafeRecomputedBMITransformer fold-safe-medians height/
      weight_before_pregnancy internally (training-fold-only) and recomputes
      BMI_before from those -- BMI_before itself is never independently
      imputed. BMI_after's representation/method is likewise CLOSED (see
      B5b above: fold-safe observed-value tertile + not_documented,
      deferred fitting only) -- not an open question.
B5e — severe_PET/any_PET: categorical + not_documented (Decision 27).
B5f — adenomyosis_sonographic_features_clean: row-applicability-gated
      (adenomyosis==1) structural-missingness correction (2026-08-25).
      Current representation (2026-08-27 correction, supersedes the
      combination-level categorical below): a lossless multi-hot family --
      adenomyosis_feature_1 .. adenomyosis_feature_11 (one binary indicator
      per documented sonographic-feature code) plus
      adenomyosis_features_unknown (adenomyosis==1 with no specific feature
      documented). The single ~22-level adenomyosis_sonographic_features_status
      combination categorical this section originally created is retired and
      no longer materialized in the export.
B6 — Imputation plan for everything else, learned imputation deferred
     entirely to the modeling CV. No opt-in/preview learned imputation of
     any kind is performed in Data Cleaning B (the former optional-kNN
     preview cell was removed, not just left off-by-default).

No outcome / post-delivery / leakage variable is ever used as an imputation
feature anywhere in this file, including in Section B5c.
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


# ── Section B5a ────────────────────────────────────────────────────────────────
SB5_HEADER = md("clean-b-s05a-header", """
## Section B5a — Binary Type Normalization

Sections B5a–B5h build the final derived / model-facing representations. This
first step applies only **deterministic, value-preserving** type conversion:
a column whose observed values are already a subset of `{0, 1}` is cast to a
clean nullable `Int64` 0/1 dtype.

### Rules
- Only deterministic, safe conversions here — no distribution decision, no
  imputation.
- Missingness-percentage decisions belong to Section B4 alone; this section
  does not recompute or act on a column's missingness percentage.
- Outcome / post-delivery / leakage variables are outside the cleaning scope
  and never touched.
- Skewness and continuous power-transform review are done target-blind in
  Section B3, not here.

Every derived `<col>_cat` / status column created in B5c/B5e/B5f is recorded in
`feature_dictionary`.
""")

SB5_TRANSFORM = code("clean-b-s05a-binary-normalize", """
# B5a: deterministic binary-dtype normalization only. A column whose observed
# values are already a subset of {0, 1} is cast to a nullable Int64 0/1 dtype
# -- a value-preserving type conversion, not a distribution or transformation
# decision.
binary_normalised = []

for col in list(CLEANING_SCOPE):
    if col not in df_clean.columns:
        continue
    var_type = infer_var_type(df_clean[col])

    # Normalise clean binaries to Int 0/1 (deterministic, safe)
    if var_type == "binary":
        observed = set(df_clean[col].dropna().unique())
        if observed.issubset({0, 1, 0.0, 1.0}):
            df_clean[col] = df_clean[col].astype("Float64").astype("Int64")
            binary_normalised.append(col)
            column_actions_log.append({
                "column": col, "stage": "B5a_type",
                "action": "normalise_binary_int", "detail": "cast to nullable Int64 0/1",
            })

print(f"Binary columns normalised to Int 0/1: {len(binary_normalised)}")
print("Descriptive skew / continuous power-transform review: see Section B3.")
""")


# ── Section B5b ────────────────────────────────────────────────────────────────
SB5B_HEADER = md("clean-b-s05b-header", """
## Section B5b — Fold-Safe-Deferred Categorical Representations
### (`weight_in_pregnancy`, `BMI_after`, `gestational_age_at_PPROM_days` timing)

For these three variables the modeling representation's category boundaries
are learned from the observed-data distribution (an observed-value tertile
split, or an observed-timing median split). Data Cleaning B closes the
**representation decision** — the category vocabulary, the split concept, and
which raw column it applies to — but does **not** fit the numeric cutpoint.
The `q33` / `q67` / median values are fitted **training-fold-only** by a
fold-safe transformer at modeling time
(`analysis/modeling/final_modeling/modeling_core.py`), never from the full
431-row cohort and never here. (This differs from `endometrioma_size_status`'s
fixed 30 mm clinical cutoff and the adenomyosis structural / lossless
categories, which involve no data-derived cutpoint and are fully materialized
in B — Sections B5c / B5f.)

This section therefore creates **no dataframe columns** for `BMI_after_cat`,
`weight_in_pregnancy_cat`, or the PPROM-timing status. It records a
documented-representation-only `feature_dictionary` entry for each
(`materialized_in_B=False`, `cutpoint_source="fold_safe_training_only"`), and
tags each of the three raw source columns
`model_entry_mode="transform_source_only"` — a raw column may feed its
fold-safe transformer internally but may never independently enter a design
matrix as a plain predictor. EDA C and modeling both enforce this tag.

- **`weight_in_pregnancy`** — kept as a continuous
  `secondary_near_delivery_predictor` in the export, passed through unchanged:
  original NaNs preserved, no median / kNN imputation, no missingness
  indicator. Its missingness is carried by the `not_documented` bucket of the
  fold-safe `weight_in_pregnancy_cat` representation, constructed at modeling
  time, so a standalone binary indicator would be redundant.
- **`BMI_after`** — `secondary_near_delivery_predictor`, carved into `df_clean`
  like any other secondary predictor, passed through unchanged (NaNs
  preserved, no imputation, no indicator).
- **`BMI_after_cat`** (documented representation only) — four nominal
  categories: `low_observed` / `mid_observed` / `high_observed`
  (observed-value tertiles) plus `not_documented`. `BMI_after` is never
  imputed; `not_documented` carries the missingness. One-hot encoded at
  modeling time (never an ordinal integer). Raw `BMI_after` and `BMI_after_cat`
  never co-enter a model because `build_preprocessor()` routes a
  `transform_source_only` column only through its fold-safe transformer.
- **`gestational_age_at_PPROM_days` timing status** (documented representation
  only) — `no_PPROM` (structural, `PPROM==0`), `PPROM_earlier` / `PPROM_later`
  (observed-timing median split within the `PPROM==1` applicable subgroup),
  `PPROM_timing_unknown` (the 1 genuinely missing applicable case). The raw
  binary `PPROM` column stays independently selectable
  (`model_entry_mode="direct"`) but is registered `redundant_with` the timing
  status, so the two are never simultaneously co-selected.
  `gestational_age_at_PPROM_days` itself is `transform_source_only`.
""")

SB5B_STATCAT = code("clean-b-s05b-statcat", """
# weight_in_pregnancy_cat, BMI_after_cat, and the PPROM-timing status are
# DOCUMENTED REPRESENTATION ONLY in this section: B decides the category
# vocabulary and which raw column each applies to, but computes no dataframe
# column and no numeric cutpoint. The q33/q67/median values are fitted
# training-fold-only by a fold-safe transformer at modeling time. (Fixed
# clinical thresholds such as endometrioma's 30 mm cutoff, and
# structural/lossless categories such as the adenomyosis multi-hot family,
# involve no cutpoint-fitting question and are fully materialized in B.)
print("B5b: weight_in_pregnancy -- approved representation is fold-safe "
      "observed-value tertiles (low/mid/high_observed + not_documented), "
      "not materialized as a df_clean column here; cutpoints fitted "
      "training-fold-only in modeling. weight_in_pregnancy itself stays "
      "continuous with its original NaNs and gets no standalone missingness "
      "indicator -- the fold-safe categorical's own not_documented bucket "
      "carries that information.")

feature_dictionary.append(new_feature_dictionary_entry(
    new_column="weight_in_pregnancy",
    source_column="weight_in_pregnancy",
    creation_rule=(
        "raw source column, passed through unchanged (no imputation, no formula "
        "completion). May feed the modeling-stage fold-safe weight_in_pregnancy_cat "
        "transformer internally as a transform dependency; must never independently "
        "enter a design matrix as a plain numeric predictor."
    ),
    timing="same_as_source", leakage_status="no", intended_use="review",
    creation_section="B5b", domain="anthropometric", clinical_timing="pregnancy",
    predictor_classification="secondary_near_delivery_predictor", stage="2",
    redundancy_group="weight_in_pregnancy_representation",
    materialized_in_B=True, model_entry_mode="transform_source_only",
))
feature_dictionary.append(new_feature_dictionary_entry(
    new_column="weight_in_pregnancy_cat",
    source_column="weight_in_pregnancy",
    creation_rule=(
        "DOCUMENTED REPRESENTATION ONLY -- not computed as a df_clean column in Data "
        "Cleaning B. B decides: four nominal categories low_observed/mid_observed/"
        "high_observed (observed-value tertiles of weight_in_pregnancy) plus "
        "not_documented for missing rows. The actual q33/q67 cutpoints are fitted "
        "training-fold-only by a fold-safe transformer at modeling time -- never from "
        "the full cohort, never here in B."
    ),
    timing="same_as_source", leakage_status="no", intended_use="review",
    creation_section="B5b", domain="anthropometric", clinical_timing="pregnancy",
    predictor_classification="secondary_near_delivery_predictor", stage="2",
    redundancy_group="weight_in_pregnancy_representation",
    materialized_in_B=False, model_entry_mode="direct",
    cutpoint_source="fold_safe_training_only",
))

# ── BMI_after: NaN preserved, no formula completion ─────────────────────────
# BMI_after is a secondary_near_delivery_predictor carved into df_clean
# (Section B1). This section does not complete it via weight_in_pregnancy /
# height -- that would put derived backfilled values into a raw-named column.
# Logged below for audit-trail parity with the not-imputed entries for
# weight_before_pregnancy / height / Hb_before_delivery in Section B5d.
_n_bmi_after_missing = int(df_clean["BMI_after"].isna().sum())
column_actions_log.append({
    "column": "BMI_after", "stage": "B5b_no_imputation_raw_source",
    "action": "no_imputation_nan_preserved",
    "detail": f"{_n_bmi_after_missing} rows left as NaN (not imputed, not formula-completed)",
    "issue_type": "n/a", "action_taken": "none", "base_variable": "BMI_after",
    "reason": (
        f"BMI_after had {_n_bmi_after_missing} missing "
        f"({round(_n_bmi_after_missing/len(df_clean)*100,1)}%). BMI_after is in "
        "CLEANING_SCOPE as a secondary near-delivery predictor. No "
        "weight_in_pregnancy/height-based deterministic completion is performed. "
        "NaN preserved on the raw "
        "source column; the missingness question is answered for MODELING purposes "
        "by the documented (not materialized) BMI_after_cat representation below, "
        "computed by a fold-safe transformer at modeling time -- the raw column "
        "itself is never imputed and never independently enters a model "
        "(model_entry_mode=transform_source_only). "
        "See docs/clinical_decisions/manual_decisions_log.md."
    ),
    "rows_removed": 0, "row_count_changed": False, "target_distribution_changed": False,
    "imputation_performed": False, "new_indicators_created": 0,
    "unknown_categories_created": 0, "requires_manual_decision_before_reversal": True,
})
feature_dictionary.append(new_feature_dictionary_entry(
    new_column="BMI_after",
    source_column="BMI_after",
    creation_rule=(
        "raw source column, passed through unchanged (no imputation). May feed the "
        "modeling-stage fold-safe BMI_after_cat transformer internally as a transform "
        "dependency; must never independently enter a design matrix as a plain "
        "numeric predictor, nor alongside its mathematical source family "
        "(height, weight_in_pregnancy)."
    ),
    timing="same_as_source", leakage_status="no", intended_use="review",
    creation_section="B5b", domain="anthropometric", clinical_timing="pregnancy",
    predictor_classification="secondary_near_delivery_predictor", stage="2",
    redundancy_group="BMI_after_representation",
    materialized_in_B=True, model_entry_mode="transform_source_only",
))
feature_dictionary.append(new_feature_dictionary_entry(
    new_column="BMI_after_cat",
    source_column="BMI_after",
    creation_rule=(
        "DOCUMENTED REPRESENTATION ONLY -- not computed as a df_clean column in Data "
        "Cleaning B. B decides: four nominal categories low_observed/mid_observed/"
        "high_observed (observed-value tertiles of BMI_after) plus not_documented for "
        "missing rows. The actual q33/q67 cutpoints are fitted training-fold-only by a "
        "fold-safe transformer at modeling time -- never from the full cohort, never "
        "here in B. No imputation of BMI_after is performed anywhere."
    ),
    timing="same_as_source", leakage_status="no", intended_use="review",
    creation_section="B5b", domain="anthropometric", clinical_timing="pregnancy",
    # predictor_classification inherits BMI_after's secondary_near_delivery_
    # predictor timing horizon (Stage 1 ineligible, Stage 2/3 eligible), like
    # the raw source column.
    predictor_classification="secondary_near_delivery_predictor", stage="2",
    redundancy_group="BMI_after_representation",
    materialized_in_B=False, model_entry_mode="direct",
    cutpoint_source="fold_safe_training_only",
))

# ── PPROM timing: documented representation only ────────────────────────────
# gestational_age_at_PPROM_days is applicability-gated (PPROM==1) in Section
# B4/B4d; this entry documents its deferred categorical representation without
# materializing it.
_n_pprom_applicable = int((df_clean["PPROM"] == 1).sum())
_n_pprom_timing_missing_applicable = int(
    df_clean.loc[df_clean["PPROM"] == 1, "gestational_age_at_PPROM_days"].isna().sum()
)
feature_dictionary.append(new_feature_dictionary_entry(
    new_column="gestational_age_at_PPROM_days",
    source_column="gestational_age_at_PPROM_days",
    creation_rule=(
        "raw source column, passed through unchanged (no imputation). May feed the "
        "modeling-stage fold-safe PPROM-timing transformer internally as a transform "
        "dependency (together with the raw binary PPROM gate column); must never "
        "independently enter a design matrix as a plain numeric predictor."
    ),
    timing="same_as_source", leakage_status="no", intended_use="review",
    creation_section="B5b", domain="obstetric", clinical_timing="antepartum",
    predictor_classification="secondary_near_delivery_predictor", stage="2",
    redundancy_group="pprom_timing_representation",
    materialized_in_B=True, model_entry_mode="transform_source_only",
))
feature_dictionary.append(new_feature_dictionary_entry(
    new_column="PPROM",
    source_column="PPROM",
    creation_rule=(
        "raw binary source column, passed through unchanged. Remains independently "
        "selectable as an ordinary predictor on its own clinical merits "
        "(model_entry_mode=direct) -- it is NOT a transform-source-only column. It also "
        "acts as the applicability gate the fold-safe PPROM-timing transformer needs "
        "internally (no_PPROM vs. applicable-subgroup timing) as a dependency, "
        "independent of whether PPROM is itself selected as a feature. Because it is "
        "exactly redundant with the timing representation it gates (no_PPROM already "
        "encodes PPROM==0/1), the two must never be SIMULTANEOUSLY selected together -- "
        "enforced via the pprom_timing_representation redundancy group, not by "
        "forbidding PPROM's independent use altogether."
    ),
    timing="same_as_source", leakage_status="no", intended_use="review",
    creation_section="B5b", domain="obstetric", clinical_timing="antepartum",
    predictor_classification="secondary_near_delivery_predictor", stage="2",
    redundancy_group="pprom_timing_representation",
    materialized_in_B=True, model_entry_mode="direct",
    redundant_with="gestational_age_at_PPROM_days_timing_status",
))
feature_dictionary.append(new_feature_dictionary_entry(
    new_column="gestational_age_at_PPROM_days_timing_status",
    source_column="gestational_age_at_PPROM_days, PPROM",
    creation_rule=(
        "DOCUMENTED REPRESENTATION ONLY -- not computed as a df_clean column in Data "
        "Cleaning B. B decides: four nominal categories -- no_PPROM (structural, "
        "PPROM==0), PPROM_earlier / PPROM_later (observed-timing median split within "
        f"the PPROM==1 applicable subgroup, n_applicable={_n_pprom_applicable}), "
        "PPROM_timing_unknown (genuinely missing applicable timing, "
        f"n={_n_pprom_timing_missing_applicable}). The actual median cutpoint is "
        "fitted training-fold-only by a fold-safe transformer at modeling time -- "
        "never from the full cohort, never here in B, and never derived from "
        "gestational_age_at_delivery_days (Stage-3-only; would leak into this "
        "Stage-2 representation)."
    ),
    timing="same_as_source", leakage_status="no", intended_use="review",
    creation_section="B5b", domain="obstetric", clinical_timing="antepartum",
    predictor_classification="secondary_near_delivery_predictor", stage="2",
    redundancy_group="pprom_timing_representation",
    materialized_in_B=False, model_entry_mode="direct",
    cutpoint_source="fold_safe_training_only",
))
print(f"\\nPPROM timing (documented representation only): applicable_n={_n_pprom_applicable}, "
      f"genuinely_missing_applicable_n={_n_pprom_timing_missing_applicable}. "
      "No dataframe column created here; fold-safe transformer computes it at modeling time.")
print("\\nB5b complete: weight_in_pregnancy_cat, BMI_after_cat, and "
      "gestational_age_at_PPROM_days_timing_status are all documented-representation-"
      "only entries (materialized_in_B=False) -- no dataframe columns created for any "
      "of them in this notebook.")
""")


# ── Section B5c ────────────────────────────────────────────────────────────────
SB5C_HEADER = md("clean-b-s05c-header", """
## Section B5c — Endometrioma Size Status + Presence / Laterality

Two deterministic full-cohort categorical phenotype variables are built.
Structural not-applicable coding is applied first (`endometrioma == 0`); within
the `endometrioma == 1` applicable subgroup, genuinely unresolved size or
laterality is kept as an explicit unknown category, **not** full-cohort
imputed — this keeps "not applicable" distinct from "documented endometrioma
with unknown detail". No imputation is performed for either variable.

### endometrioma_size_status
- `no_endometrioma` (structural, `endometrioma == 0`),
  `endometrioma_less_than_30mm`, `endometrioma_30mm_or_more`,
  `endometrioma_size_unknown`.
- Among `endometrioma == 1` rows, documented size is split at the
  clinically-sourced 30 mm cutoff; genuinely unknown / unusable size is the
  explicit `endometrioma_size_unknown` state.

### endometrioma_presence_laterality
- `none`, `unilateral`, `bilateral`, `laterality_unknown`.
- Derived from `endometrioma_laterality`, cross-checked against
  `endometrioma_place_clean` wherever both are present (raises an error on
  disagreement).
- The 5 `endometrioma == 1` rows with genuinely unresolved laterality are the
  explicit `laterality_unknown` category. **The final column has 0 missing
  values** — `laterality_unknown` is a disclosed unknown state, not a guessed
  or imputed value; no full-cohort mode imputation is performed.
- Right vs. left is intentionally collapsed to `unilateral`: no clinical
  hypothesis in this project supports a side-specific effect on intrapartum
  CS risk, and `endometrioma_place_clean` / `endometrioma_laterality` are
  ≈ 0.997 Cramér's V redundant (laterality is a deterministic function of
  place).

### Export
`endometrioma_size_clean`, `endometrioma_place_clean`,
`endometrioma_laterality`, and their `__missing_ind` columns are excluded from
the Batch19 export (Section B7) — superseded by the two derived variables
above. `endometrioma` itself is retained unchanged; the raw detail columns
remain in the preprocessing output.
""")

SB5C_ENDOMETRIOMA = code("clean-b-s05c-endometrioma", """
# -- endometrioma_size_status: structural status + explicit unknown-size state --
_endo = df_clean["endometrioma"]
_size = df_clean["endometrioma_size_clean"]
_place = df_clean["endometrioma_place_clean"]
_lat = df_clean["endometrioma_laterality"]

_n0 = int((_endo == 0).sum())
_n1 = int((_endo == 1).sum())
_size_missing_n1 = int(_size[_endo == 1].isna().sum())
_size_present_n1 = int(_size[_endo == 1].notna().sum())
print("Endometrioma size -- structural status representation:")
print(f"  endometrioma == 0 (structural / not applicable): {_n0}")
print(f"  endometrioma == 1 (applicable subgroup)       : {_n1}")
print(f"  within applicable subgroup, size missing: {_size_missing_n1} "
      f"({round(_size_missing_n1/_n1*100,1)}%)")
print(f"  within applicable subgroup, size present: {_size_present_n1}")
print(f"  explicit unknown-size category: "
      f"{_size_missing_n1}/{len(df_clean)} = {round(_size_missing_n1/len(df_clean)*100,1)}%; "
      "no size imputation is performed.")

SIZE_STATUS_CUTOFF_MM = 30.0
endometrioma_size_status = pd.Series(pd.NA, index=df_clean.index, dtype="string")
endometrioma_size_status[_endo == 0] = "no_endometrioma"
_e1_mask = _endo == 1
endometrioma_size_status[_e1_mask & _size.notna() & (_size < SIZE_STATUS_CUTOFF_MM)] = "endometrioma_less_than_30mm"
endometrioma_size_status[_e1_mask & _size.notna() & (_size >= SIZE_STATUS_CUTOFF_MM)] = "endometrioma_30mm_or_more"
endometrioma_size_status[_e1_mask & _size.isna()] = "endometrioma_size_unknown"
df_clean["endometrioma_size_status"] = endometrioma_size_status

_size_status_allowed = {
    "no_endometrioma",
    "endometrioma_less_than_30mm",
    "endometrioma_30mm_or_more",
    "endometrioma_size_unknown",
}
_counts = df_clean["endometrioma_size_status"].value_counts(dropna=False).to_dict()
_n_missing_status = int(df_clean["endometrioma_size_status"].isna().sum())
if _n_missing_status != 0:
    raise AssertionError(
        f"endometrioma_size_status POSTCONDITION FAILED: expected 0 missing after "
        f"deterministic status construction, got {_n_missing_status}"
    )
if not set(df_clean["endometrioma_size_status"].dropna().unique()).issubset(_size_status_allowed):
    raise AssertionError("endometrioma_size_status POSTCONDITION FAILED: unexpected category label.")
_contradict_no_endo = int(((_endo == 0) & (df_clean["endometrioma_size_status"] != "no_endometrioma")).sum())
if _contradict_no_endo != 0:
    raise AssertionError(
        f"endometrioma_size_status POSTCONDITION FAILED: {_contradict_no_endo} no-endometrioma "
        "row(s) received a known/unknown endometrioma-size category."
    )
print("\\nendometrioma_size_status finalized "
      "(no_endometrioma, endometrioma_less_than_30mm, endometrioma_30mm_or_more, "
      f"endometrioma_size_unknown; no size imputation). Counts: {_counts}")

feature_dictionary.append(new_feature_dictionary_entry(
    new_column="endometrioma_size_status",
    source_column="endometrioma, endometrioma_size_clean",
    creation_rule=(
        "categorical full-cohort status: no_endometrioma when endometrioma==0; "
        "endometrioma_less_than_30mm when endometrioma==1 and documented size <30mm; "
        "endometrioma_30mm_or_more when endometrioma==1 and documented size >=30mm; "
        "endometrioma_size_unknown when endometrioma==1 and size is genuinely missing/unusable. "
        "No size imputation is performed; structural not-applicable and genuine unknown are distinguished."
    ),
    timing="same_as_source",
    leakage_status="no",
    intended_use="review",
    creation_section="B5c",
    domain="endometriosis_phenotype",
    # clinical_timing is "pre_pregnancy": both direct sources (endometrioma,
    # endometrioma_size_clean) are diagnostic/history characteristics from
    # imaging/surgical findings, the same kind of information that feeds the
    # sibling endometrioma_presence_laterality.
    clinical_timing="pre_pregnancy",
    # Approved pre-labor predictor. Source-faithful representation of
    # endometrioma size/presence status, reusing the clinically-sourced 30 mm
    # cutoff.
    predictor_classification="predictor_allowed",
    stage="1",
    redundancy_group="endometrioma_size_status_representation",
))
column_actions_log.append({
    "column": "endometrioma_size_status",
    "stage": "B5c_endometrioma_derived",
    "action": "deterministic_categorical_status_no_imputation",
    "detail": f"counts={_counts}; cutoff={SIZE_STATUS_CUTOFF_MM}mm; imputation=none",
    "issue_type": "n/a",
    "action_taken": "deterministic_categorical_status_no_imputation",
    "base_variable": "endometrioma",
    "reason": (
        "endometrioma==0 is structurally no_endometrioma. Within endometrioma==1, documented size is "
        "classified using the 30mm clinical cutoff and genuinely missing/unusable size is represented as "
        "endometrioma_size_unknown rather than being imputed into a known size category. No size "
        "imputation is performed."
    ),
    "rows_removed": 0,
    "row_count_changed": False,
    "target_distribution_changed": False,
    "imputation_performed": False,
    "new_indicators_created": 0,
    "unknown_categories_created": int(_size_missing_n1 > 0),
    "requires_manual_decision_before_reversal": True,
})

# Classification-lineage: register endometrioma_size_status (approved
# pre-labor predictor). This snapshot feeds EDA C's screening/eligibility.
dcb_classification_snapshot, dcb_type_schema_snapshot = classification_lineage.register_feature(
    "endometrioma_size_status", "categorical", "predictor_allowed",
    "Approved pre-labor predictor representation for endometrioma size/presence "
    "status (Decision 84) -- source-faithful replacement for the retired, "
    "KNN-imputed endometrioma_size_severity; no size imputation, genuinely "
    "unknown size kept as an explicit endometrioma_size_unknown category.",
    df=df_clean, classification_df=dcb_classification_snapshot, type_schema_df=dcb_type_schema_snapshot,
)

# ── endometrioma_presence_laterality: categorical presence/laterality handling ──
_both_present = _lat.notna() & _place.notna()
_place_says_bilateral = _place == 3
_lat_says_bilateral = _lat == 2
_inconsistent_bilateral = int((_both_present & (_place_says_bilateral != _lat_says_bilateral)).sum())
if _inconsistent_bilateral != 0:
    raise ValueError(
        f"STRUCTURAL DERIVATION ABORTED -- {_inconsistent_bilateral} row(s) have "
        "endometrioma_laterality and endometrioma_place_clean disagreeing on bilateral "
        "status. Cannot safely derive endometrioma_presence_laterality -- re-audit before implementing."
    )
print(f"\\nendometrioma_presence_laterality precondition check: 0 laterality/place bilateral "
      f"disagreements found among {int(_both_present.sum())} rows with both present.")

_lat_missing_flag = (_lat.isna() & (_endo == 1)).astype(int)
_n_lat_missing = int(_lat_missing_flag.sum())
print(f"\\n{_n_lat_missing} unresolved applicable rows (endometrioma==1 laterality/place "
      "genuinely missing) -- represented as the explicit laterality_unknown category. "
      "No upstream imputation is performed. See Section B4d for the applicability-aware "
      "mechanism testing.")

MECHANISM_LABEL_BILATERAL = (
    f"{_n_lat_missing} unresolved applicable rows represented as the explicit "
    "laterality_unknown category (no upstream imputation). See Section B4d for the "
    "canonical mechanism screen."
)

# Unresolved applicable rows are the explicit laterality_unknown category (the
# final column has 0 missing). No upstream imputation: laterality_unknown is a
# disclosed unknown state, not a guessed/imputed value.
endometrioma_presence_laterality = pd.Series(pd.NA, index=df_clean.index, dtype="string")
endometrioma_presence_laterality[_endo == 0] = "none"
endometrioma_presence_laterality[(_endo == 1) & (_lat == 1)] = "unilateral"
endometrioma_presence_laterality[(_endo == 1) & (_lat == 2)] = "bilateral"
endometrioma_presence_laterality[(_endo == 1) & _lat.isna()] = "laterality_unknown"
df_clean["endometrioma_presence_laterality"] = endometrioma_presence_laterality

_presence_counts = df_clean["endometrioma_presence_laterality"].value_counts(dropna=False).to_dict()
_n_missing_presence_laterality = int(df_clean["endometrioma_presence_laterality"].isna().sum())
if _n_missing_presence_laterality != 0:
    raise AssertionError(
        "endometrioma_presence_laterality POSTCONDITION FAILED: expected 0 missing "
        f"(unresolved rows must be the laterality_unknown category), got "
        f"{_n_missing_presence_laterality}"
    )
_n_laterality_unknown = int((df_clean["endometrioma_presence_laterality"] == "laterality_unknown").sum())
if _n_laterality_unknown != _n_lat_missing:
    raise AssertionError(
        "endometrioma_presence_laterality POSTCONDITION FAILED: expected "
        f"{_n_lat_missing} laterality_unknown rows, got {_n_laterality_unknown}"
    )
_allowed_presence_laterality = {"none", "unilateral", "bilateral", "laterality_unknown"}
_invalid_presence_laterality = sorted(
    set(df_clean["endometrioma_presence_laterality"].dropna().unique()) - _allowed_presence_laterality
)
if _invalid_presence_laterality:
    raise AssertionError(
        "endometrioma_presence_laterality POSTCONDITION FAILED: invalid categories "
        f"{_invalid_presence_laterality}"
    )
print(f"\\nendometrioma_presence_laterality finalized (categorical, 0 missing, "
      f"no upstream imputation). Counts: {_presence_counts}")
print("Right vs. left intentionally collapsed to unilateral: no current clinical "
      "hypothesis supports a side-specific effect on intrapartum CS risk, and "
      "place_clean/laterality are highly redundant (Cramer's V ~ 0.997; laterality is in fact "
      "a deterministic function of place_clean).")

# source_column names the columns the derivation reads directly (endometrioma,
# endometrioma_laterality); endometrioma_place_clean is upstream lineage only
# (endometrioma_laterality was derived from it in preprocessing).
feature_dictionary.append(new_feature_dictionary_entry(
    new_column="endometrioma_presence_laterality",
    source_column="endometrioma, endometrioma_laterality",
    upstream_lineage="endometrioma_place_clean (endometrioma_laterality was derived from it in preprocessing)",
    creation_rule=(
        "Categorical representation: none if endometrioma==0; unilateral if "
        "endometrioma==1 and laterality/location indicates right/left/unilateral; "
        "bilateral if endometrioma==1 and laterality/location indicates bilateral; "
        "laterality_unknown if endometrioma==1 and laterality/location is genuinely "
        "unresolved (explicit category, not true NaN -- final column has 0 missing). "
        "No upstream mode imputation is performed."
    ),
    timing="same_as_source",
    leakage_status="no",
    intended_use="review",
    creation_section="B5c",
    predictor_classification="predictor_allowed",
    stage="1",
    clinical_timing="pre_pregnancy",
    domain="endometriosis_phenotype",
    redundancy_group="endometrioma_presence_laterality_representation",
))
column_actions_log.append({
    "column": "endometrioma_presence_laterality",
    "stage": "B5c_endometrioma_derived",
    "action": "categorical_presence_laterality_no_upstream_imputation",
    "detail": f"counts={_presence_counts}; unresolved_missing={_n_missing_presence_laterality}",
    "issue_type": "n/a",
    "action_taken": "categorical_presence_laterality_no_upstream_imputation",
    "base_variable": "endometrioma",
    "reason": (
        "Canonical categorical representation of endometrioma presence plus laterality: "
        "none/unilateral/bilateral/laterality_unknown. Genuinely unresolved "
        "endometrioma==1 laterality rows are the explicit laterality_unknown category, "
        "not true missing -- the final column has 0 missing; no downstream categorical "
        "imputation is needed or performed for these rows. It replaces the "
        "full-cohort mode-imputed binary alias endometrioma_bilateral_any."
    ),
    "rows_removed": 0,
    "row_count_changed": False,
    "target_distribution_changed": False,
    "imputation_performed": False,
    "new_indicators_created": 0,
    "unknown_categories_created": 0,
    "requires_manual_decision_before_reversal": True,
})

# Classification-lineage: register endometrioma_presence_laterality (approved).
dcb_classification_snapshot, dcb_type_schema_snapshot = classification_lineage.register_feature(
    "endometrioma_presence_laterality", "categorical", "predictor_allowed",
    "Approved pre-labor predictor representation combining endometrioma presence and laterality.",
    df=df_clean, classification_df=dcb_classification_snapshot, type_schema_df=dcb_type_schema_snapshot,
)

ENDOMETRIOMA_DETAIL_EXCLUDE_FROM_EXPORT = [
    "endometrioma_size_clean", "endometrioma_place_clean", "endometrioma_laterality",
    "endometrioma_size_clean__missing_ind", "endometrioma_place_clean__missing_ind",
    "endometrioma_laterality__missing_ind",
]
print(f"\\nColumns to exclude from final batch19 export (superseded by endometrioma "
      f"derived variables): {ENDOMETRIOMA_DETAIL_EXCLUDE_FROM_EXPORT}")
""")


# ── Section B5d ────────────────────────────────────────────────────────────────
SB5D_HEADER = md("clean-b-s05d-header", """
## Section B5d — Anthropometry Family and Hb_before_delivery: NaN Preserved

### No global imputation
`weight_before_pregnancy`, `height`, and `Hb_before_delivery` are **not
imputed** anywhere in Data Cleaning B. A global, full-cohort imputation fit
once before any train/CV split is an imputation-leakage risk — a held-out
fold's rows could influence the values imputed into training rows once these
columns are used in a cross-validated model. Original NaNs are preserved
unchanged in the export; the approved method (ordinary median imputation) is
fitted only within each modeling training fold, respecting each variable's
Stage 1/2/3 horizon eligibility.

### BMI_before — deterministic formula recompute (observed inputs only)
`BMI_before == weight_before_pregnancy / (height/100)**2` to within ordinary
floating-point precision (preprocessing treats `BMI_before` as an
independently-sourced raw field, with no formula derivation). `BMI_before` is
missing if and only if `weight_before_pregnancy` and/or `height` is missing —
zero rows have BMI present with weight or height missing, and zero rows have
both inputs present with BMI missing; its missingness is fully explained by
the anthropometry pair. The code cell below verifies this formula agreement
**dynamically, every run** against the loaded cohort (floating-point
tolerance, not bit-exact equality).

`BMI_before` is then deterministically **recomputed only for rows where both
`weight_before_pregnancy` and `height` are observed** — never from an imputed
input. Rows where either input is missing keep `BMI_before` as NaN; an
already-observed `BMI_before` is never overwritten. This resolves only the
subset recoverable from already-observed data — a deterministic formula rule,
not structural-zero handling, and it never assigns 0 for a genuinely missing
value. Downstream, when `BMI_before` is selected for modeling with an input
still missing, `modeling_core.py`'s `FoldSafeRecomputedBMITransformer`
fold-safe-medians `height` / `weight_before_pregnancy` internally
(training-fold-only) and recomputes `BMI_before`; `BMI_before` itself is never
independently imputed.

### BMI_after
`secondary_near_delivery_predictor`, carved into `df_clean` (Section B1). This
section does **not** complete it from `weight_in_pregnancy` / `height` (that
would put derived backfilled values into a raw-named column). `BMI_after` is
exported with its original NaNs preserved; its modeling representation is the
fold-safe `BMI_after_cat` (Section B5b).

`target_intrapartum_cs` and all leakage / delivery-outcome variables are never
read in this section — enforced by an explicit code-level guard.
""")

SB5D_ANTHROPOMETRY = code("clean-b-s05d-anthropometry", """
# ── weight_before_pregnancy, height, Hb_before_delivery: NaN preserved ────────
# No imputation of any kind is performed here (no KNN, no scaling, no median
# fallback). Original missingness is measured for audit and left unchanged;
# median imputation is fitted inside each grouped (subject_number) training
# fold in modeling -- never here, never in EDA C.
_n_weight_missing_before = int(df_clean["weight_before_pregnancy"].isna().sum())
_n_height_missing_before = int(df_clean["height"].isna().sum())
_n_hb_missing_before = int(df_clean["Hb_before_delivery"].isna().sum())
_n_bmi_missing_before = int(df_clean["BMI_before"].isna().sum())
print("weight_before_pregnancy / height / Hb_before_delivery -- missingness "
      "(NOT imputed here, NaN preserved):")
print(f"  weight_before_pregnancy: {_n_weight_missing_before} missing "
      f"({round(_n_weight_missing_before/len(df_clean)*100,1)}%)")
print(f"  height                 : {_n_height_missing_before} missing "
      f"({round(_n_height_missing_before/len(df_clean)*100,1)}%)")
print(f"  Hb_before_delivery     : {_n_hb_missing_before} missing "
      f"({round(_n_hb_missing_before/len(df_clean)*100,1)}%)")
print(f"  BMI_before (pre-recompute): {_n_bmi_missing_before} missing "
      f"({round(_n_bmi_missing_before/len(df_clean)*100,1)}%)")

WEIGHT_BEFORE_IMPUTATION_METHOD = (
    "none -- NaN preserved; median imputation fitted training-fold-only in modeling"
)
HEIGHT_IMPUTATION_METHOD = WEIGHT_BEFORE_IMPUTATION_METHOD
HB_IMPUTATION_METHOD = WEIGHT_BEFORE_IMPUTATION_METHOD

_n_weight_missing_after = int(df_clean["weight_before_pregnancy"].isna().sum())
_n_height_missing_after = int(df_clean["height"].isna().sum())
_n_hb_missing_after = int(df_clean["Hb_before_delivery"].isna().sum())
if (_n_weight_missing_after != _n_weight_missing_before
        or _n_height_missing_after != _n_height_missing_before
        or _n_hb_missing_after != _n_hb_missing_before):
    raise AssertionError(
        "NaN-PRESERVATION POSTCONDITION FAILED: weight_before_pregnancy/height/"
        "Hb_before_delivery missingness must be exactly unchanged by this "
        f"section -- before={_n_weight_missing_before}/{_n_height_missing_before}/"
        f"{_n_hb_missing_before}, after={_n_weight_missing_after}/"
        f"{_n_height_missing_after}/{_n_hb_missing_after}"
    )
print("weight_before_pregnancy / height / Hb_before_delivery: missingness "
      "unchanged -- no imputation performed.")

# ── BMI_before formula-exact relationship: dynamic verification ─────────────
# Computes the current complete-case count and the formula agreement every
# run, against whatever cohort is loaded -- audit only, no value is read from
# or written to df_clean here.
_bmi_verify_mask = (
    df_clean["weight_before_pregnancy"].notna()
    & df_clean["height"].notna()
    & df_clean["BMI_before"].notna()
)
_bmi_verify_n = int(_bmi_verify_mask.sum())
_bmi_verify_formula = (
    df_clean.loc[_bmi_verify_mask, "weight_before_pregnancy"]
    / ((df_clean.loc[_bmi_verify_mask, "height"] / 100) ** 2)
)
_bmi_verify_diff = (_bmi_verify_formula - df_clean.loc[_bmi_verify_mask, "BMI_before"]).abs()
_bmi_verify_max_diff = float(_bmi_verify_diff.max()) if _bmi_verify_n else float("nan")
_bmi_verify_mean_diff = float(_bmi_verify_diff.mean()) if _bmi_verify_n else float("nan")
_BMI_VERIFY_ATOL = 1e-6
_bmi_verify_consistent = bool(
    _bmi_verify_n == 0
    or np.allclose(_bmi_verify_formula, df_clean.loc[_bmi_verify_mask, "BMI_before"], atol=_BMI_VERIFY_ATOL)
)
if not _bmi_verify_consistent:
    raise AssertionError(
        f"BMI_before FORMULA-CONSISTENCY CHECK FAILED: max absolute difference "
        f"{_bmi_verify_max_diff} exceeds tolerance {_BMI_VERIFY_ATOL} across "
        f"{_bmi_verify_n} complete-case rows -- re-audit before proceeding."
    )
print(f"BMI_before formula-exact relationship -- LIVE verification against the "
      f"current cohort ({_bmi_verify_n} rows with weight_before_pregnancy, height, "
      f"and BMI_before all observed):")
print(f"  max absolute difference: {_bmi_verify_max_diff:.3e}")
print(f"  mean absolute difference: {_bmi_verify_mean_diff:.3e}")
print(f"  numerically consistent within floating-point tolerance "
      f"(atol={_BMI_VERIFY_ATOL}): {_bmi_verify_consistent}")
_bmi_verify_bmi_present_but_wh_missing = int(
    (df_clean["BMI_before"].notna()
     & (df_clean["weight_before_pregnancy"].isna() | df_clean["height"].isna())).sum()
)
_bmi_verify_wh_present_but_bmi_missing = int(
    (df_clean["weight_before_pregnancy"].notna() & df_clean["height"].notna()
     & df_clean["BMI_before"].isna()).sum()
)
print(f"  rows with BMI_before present but weight/height missing (expected 0): "
      f"{_bmi_verify_bmi_present_but_wh_missing}")
print(f"  rows with weight+height present but BMI_before missing (expected 0, "
      f"before this section's recompute below): {_bmi_verify_wh_present_but_bmi_missing}")

# ── BMI_before: deterministic recompute, only from OBSERVED weight+height ─────
# Not structural-zero handling -- never assigns 0 for a genuinely missing
# value. Rows where weight or height remain missing keep BMI_before as NaN in
# the exported Batch19; this step resolves only what is recoverable from
# already-observed data. When BMI_before is selected for modeling with an
# input still missing, modeling_core.py's FoldSafeRecomputedBMITransformer
# fold-safe-medians weight_before_pregnancy / height internally
# (training-fold-only) and recomputes BMI_before from those.
_bmi_recompute_mask = (
    df_clean["BMI_before"].isna()
    & df_clean["weight_before_pregnancy"].notna()
    & df_clean["height"].notna()
)
_n_bmi_recomputed = int(_bmi_recompute_mask.sum())
_bmi_recomputed_vals = df_clean["weight_before_pregnancy"] / ((df_clean["height"] / 100) ** 2)
df_clean.loc[_bmi_recompute_mask, "BMI_before"] = _bmi_recomputed_vals.loc[_bmi_recompute_mask]

_n_bmi_missing_after = int(df_clean["BMI_before"].isna().sum())
_expected_bmi_missing_after = int(
    (df_clean["weight_before_pregnancy"].isna() | df_clean["height"].isna()).sum()
)
if _n_bmi_missing_after > _expected_bmi_missing_after:
    raise AssertionError(
        f"BMI_before POSTCONDITION FAILED: {_n_bmi_missing_after} missing after "
        f"recompute, expected at most {_expected_bmi_missing_after} (rows where "
        "weight and/or height is still missing)."
    )
print(f"BMI_before: {_n_bmi_recomputed} row(s) recomputed via "
      "weight_before_pregnancy/(height/100)^2 from observed inputs only "
      f"(formula-exact, live-verified above against {_bmi_verify_n} observed rows). "
      f"{_n_bmi_missing_after} still missing (weight and/or height not observed).")
# BMI_after is not processed in this cell (this section is BMI_before-only) --
# see Section B5b for its not-imputed audit-log entry.

# ── Audit log: not-imputed (NaN preserved) vs. deterministic formula recompute ──
for _col, _n_before in [
    ("weight_before_pregnancy", _n_weight_missing_before),
    ("height", _n_height_missing_before),
    ("Hb_before_delivery", _n_hb_missing_before),
]:
    column_actions_log.append({
        "column": _col, "stage": "B5d_missing_data_architecture_correction",
        "action": "no_imputation_nan_preserved", "detail": f"{_n_before} rows left as NaN (not imputed)",
        "issue_type": "n/a", "action_taken": "none", "base_variable": _col,
        "reason": (
            f"{_col} had {_n_before} missing ({round(_n_before/len(df_clean)*100,1)}%). Data "
            "Cleaning B preserves the original NaN and performs no learned imputation "
            "itself. A full-cohort imputer fit before any train/CV split would be an "
            "imputation-leakage risk. The approved method is ordinary median imputation, "
            "with the median statistic fitted training-fold-only in modeling, within each "
            "grouped (subject_number) training fold (SimpleImputer, "
            "analysis/modeling/final_modeling/modeling_core.py). This is an APPROVED, "
            "closed treatment, not an open or if-any downstream decision. See "
            "docs/clinical_decisions/manual_decisions_log.md."
        ),
        "rows_removed": 0, "row_count_changed": False, "target_distribution_changed": False,
        "imputation_performed": False, "new_indicators_created": 0,
        "unknown_categories_created": 0, "requires_manual_decision_before_reversal": True,
    })

for _col, _n_recomputed, _n_before in [
    ("BMI_before", _n_bmi_recomputed, _n_bmi_missing_before),
]:
    column_actions_log.append({
        "column": _col, "stage": "B5d_missing_data_architecture_correction",
        "action": "formula_recompute", "detail": f"{_n_recomputed} of {_n_before} originally-missing rows resolved via deterministic formula (observed inputs only)",
        "issue_type": "n/a", "action_taken": "formula_recompute", "base_variable": _col,
        "reason": (
            f"{_col} recomputed via weight_before_pregnancy/(height/100)^2 (formula-exact) "
            "only for rows where both formula inputs are observed -- never from an imputed "
            "input, since neither weight_before_pregnancy nor height is imputed in Data "
            "Cleaning B. Deterministic formula rule, not structural-zero handling and not "
            "learned imputation; remaining missingness (weight and/or height still missing) "
            "is left as NaN in the exported Batch19. When BMI_before is selected downstream, "
            "modeling_core.py's FoldSafeRecomputedBMITransformer fits training-fold-only "
            "medians for height and weight_before_pregnancy and recomputes BMI_before from "
            "those -- confirmed-implemented, not hypothetical. BMI_before itself is never "
            "independently median-imputed."
        ),
        "rows_removed": 0, "row_count_changed": False, "target_distribution_changed": False,
        "imputation_performed": False, "new_indicators_created": 0,
        "unknown_categories_created": 0, "requires_manual_decision_before_reversal": True,
    })
""")


# ── Section B5e ────────────────────────────────────────────────────────────────
SB5E_HEADER = md("clean-b-s05e-header", """
## Section B5e — PET Family: Categorical + not_documented

`severe_PET` and `any_PET` are **not** imputed. Each is converted to a
categorical representation with string labels `"absent"` / `"present"` /
`"not_documented"` — deliberately not `0/1/2` numeric codes, so no downstream
tool mistakes it for an ordinal variable. `not_documented` is a separate,
undocumented state, **not** equivalent to "PET absent". The categorical
variables replace their raw counterparts in the export.

The missingness-mechanism screen (Section B4d) finds a significant association
with `AGE` for both — evidence against MCAR and compatible with MAR, but not by
itself proof of MNAR or that ordinary imputation is impossible. The explicit
`not_documented` representation is a labeling choice for high-missingness
categorical data, with the mechanism screen as supporting evidence rather than
its sole justification.

`diagnosis_year` is not processed in this section: it is
`source_or_text_audit_exclude` (a calendar-time-of-diagnosis field, never
predictor-eligible), so it is outside the cleaning scope entirely and remains
only in the preprocessing output for audit purposes.

**Classification (Decision 94, 2026-09-01):** `severe_PET_cat` / `any_PET_cat`
are approved standalone `predictor_allowed` / Stage 1 predictors, inherited
from their raw sources' own classification and clinical timing -- retiring
the prior `manual_review_pending`/`UNSET` state (Decision 71). This is a
classification/eligibility change only; the representation above (string
labels, `not_documented` as a valid non-imputed category) is unchanged.
""")

SB5E_CATEGORICAL_UNKNOWN = code("clean-b-s05e-categorical-unknown", """
NOT_DOCUMENTED_LABEL = "not_documented"

# diagnosis_year is not processed here: it is source_or_text_audit_exclude, so
# it is outside CLEANING_SCOPE and not present in df_clean (like diagnosis_date).
# No diagnosis_year__missing_ind or diagnosis_year_cat is created.

# ── severe_PET / any_PET -> _cat (categorical, not imputed) ───────────────────
PET_CAT_SOURCE_COLS = ["severe_PET", "any_PET"]
_PET_APPROVED_BINARY_DOMAIN = {0, 1, 0.0, 1.0}
pet_cat_created = []
for _pet_col in PET_CAT_SOURCE_COLS:
    _n_pet_missing = int(df_clean[_pet_col].isna().sum())
    _cat_name = f"{_pet_col}_cat"
    # Fail loud on any unexpected observed value BEFORE the absent/present
    # mapping. The mapping below sends any non-1, non-NaN value to "absent";
    # without this guard a stray 2, a negative, or a text token would be
    # silently absorbed as "absent". A future data revision that violates the
    # approved binary domain must surface here explicitly.
    _pet_observed = set(df_clean[_pet_col].dropna().unique())
    _pet_unexpected = _pet_observed - _PET_APPROVED_BINARY_DOMAIN
    if _pet_unexpected:
        raise ValueError(
            f"{_pet_col} -> {_cat_name} ABORTED -- observed value(s) outside the approved "
            f"binary domain {{0, 1}}: {sorted(_pet_unexpected, key=str)}. Data Cleaning B does "
            "not silently coerce an unexpected PET value to 'absent'; re-audit preprocessing "
            "before this categorical can be built."
        )
    df_clean[_cat_name] = df_clean[_pet_col].apply(
        lambda v: NOT_DOCUMENTED_LABEL if pd.isna(v) else ("present" if v == 1 else "absent")
    ).astype("object")
    pet_cat_created.append(_cat_name)
    _pet_counts = df_clean[_cat_name].value_counts(dropna=False).to_dict()
    print(f"{_pet_col} -> {_cat_name}: {_n_pet_missing} missing rows -> '{NOT_DOCUMENTED_LABEL}'. "
          f"Counts: {_pet_counts}")

    feature_dictionary.append(new_feature_dictionary_entry(
        new_column=_cat_name,
        source_column=_pet_col,
        creation_rule=(
            "'absent'/'present'/'not_documented' string labels -- NOT 0/1/2 numeric codes, so this "
            "is never mistaken for an ordinal/numeric variable downstream. 'not_documented' is a "
            f"distinct state, not equivalent to 'absent'. Mechanism screen found missingness "
            "associated with observed data (MCAR unlikely) -- not silently imputed."
        ),
        timing="same_as_source", leakage_status="no", intended_use="review",
        creation_section="B5e",
        # Approved standalone predictors (Decision 94):
        # severe_PET_cat / any_PET_cat are deterministic categorical
        # relabelings of their raw source columns (severe_PET / any_PET),
        # which are themselves classified predictor_allowed / Stage 1 in
        # outputs/preprocessing/audit/variable_classification_minimal.csv
        # ("Available before labor begins"). Domain/clinical_timing mirror
        # the raw sources' own analysis/model_variable_readiness/config.py
        # DOMAIN_MAP/TIMING_MAP entries ("pregnancy_complication"/
        # "pregnancy") -- the categorical relabeling changes representation
        # only, never availability timing. See
        # docs/clinical_decisions/manual_decisions_log.md Decision 94.
        predictor_classification="predictor_allowed",
        stage="1",
        domain="pregnancy_complication",
        clinical_timing="pregnancy",
        redundancy_group="hypertension_pet_family",
    ))
    column_actions_log.append({
        "column": _pet_col, "stage": "B5e_categorical_unknown",
        "action": "categorical_not_documented_conversion",
        "detail": f"+{_cat_name}; {_n_pet_missing} rows -> not_documented; counts={_pet_counts}",
        "issue_type": "n/a", "action_taken": "categorical_not_documented_conversion",
        "base_variable": _pet_col,
        "reason": (
            f"{_pet_col} had {_n_pet_missing} missing ({round(_n_pet_missing/len(df_clean)*100,1)}%), "
            "<40%, mechanism screen found a significant association with AGE -- evidence against "
            "MCAR, compatible with MAR (not, by itself, proof of MNAR or proof that ordinary "
            "imputation is impossible). Per the project's approved Decision 27 handling, converted "
            "to categorical (absent/present/not_documented) instead of ordinary binary imputation, "
            "with the mechanism screen as supporting/descriptive evidence for that decision. "
            "not_documented is explicitly NOT coded as PET-absent. Raw column excluded from final "
            "export. See docs/clinical_decisions/manual_decisions_log.md Decision 27."
        ),
        "rows_removed": 0, "row_count_changed": False, "target_distribution_changed": False,
        "imputation_performed": False, "new_indicators_created": 0, "unknown_categories_created": 1,
        "requires_manual_decision_before_reversal": True,
    })

    # Classification-lineage: register severe_PET_cat / any_PET_cat as
    # predictor_allowed (Decision 94) -- approved standalone
    # predictors, retiring the prior manual_review_pending/UNSET state
    # (Decision 71). This snapshot feeds EDA C's screening/eligibility (the
    # active downstream consumer of the classification-lineage chain).
    dcb_classification_snapshot, dcb_type_schema_snapshot = classification_lineage.register_feature(
        _cat_name, "categorical", "predictor_allowed",
        "Approved standalone pre-labor predictor (Decision 94) -- deterministic "
        "categorical relabeling of the raw source column, itself predictor_allowed/"
        "Stage 1; values/representation unchanged (present/absent/not_documented).",
        df=df_clean, classification_df=dcb_classification_snapshot, type_schema_df=dcb_type_schema_snapshot,
    )

CAT_UNKNOWN_EXCLUDE_FROM_EXPORT = list(PET_CAT_SOURCE_COLS)
print(f"\\nColumns excluded from the Batch19 export (represented by the "
      f"categorical + not_documented versions): {CAT_UNKNOWN_EXCLUDE_FROM_EXPORT}")
""")


# ── Section B5f ────────────────────────────────────────────────────────────────
SB5F_HEADER = md("clean-b-s05f-header", """
## Section B5f — Adenomyosis Sonographic Features: Multi-Hot Representation

### Why multi-hot rather than a combination categorical
A single categorical that treats every observed code combination as its own
level (e.g. `"1,3,4"` as one opaque label) cannot express partial overlap
between combinations — a model could never learn "code 3 matters" independently
of exactly which other codes co-occurred with it in this cohort — and produces
a high-cardinality, sparse category space. The representation used here is
**direct multi-hot**: one binary indicator per approved sonographic-feature
code (1–11), plus a separate explicit unknown-state indicator.

### Structural vs. genuine missingness
`adenomyosis_sonographic_features_clean`'s raw whole-cohort missingness
(301 of 431 = 69.8%) conflates structural non-applicability (`adenomyosis == 0`,
262 rows — the field cannot describe a sonographic feature of a disease the
patient does not have) with genuine undocumented detail within the applicable
`adenomyosis == 1` subgroup (169 rows: 130 observed, 39 genuinely missing =
23.1% applicable-subset missingness). Prior manual clinical review had already
confirmed that some adenomyosis-positive free text supports adenomyosis
generally without describing a sufficiently specific sonographic feature to
code — consistent with genuine (not structural) missingness within the
applicable subgroup.

### `adenomyosis_feature_1` … `adenomyosis_feature_11`
One binary indicator per approved sonographic-feature code (codes 1-11 only
— code 0 is not a feature, codes 12/13 do not exist):
- `1` = the specific feature is **documented as present** for this row.
- `0` = the specific feature is **not documented as present** — this is not
  asserted as guaranteed clinical absence, only that it was not among the
  codes recorded.
- `adenomyosis == 0` rows: all 11 indicators are `0` (no redundant
  `no_adenomyosis` category is created here — the existing binary
  `adenomyosis` variable already represents disease absence).
- `adenomyosis == 1` and the source feature is genuinely missing: all 11
  indicators are `0` (nothing documented present) — distinguished from
  disease absence only via `adenomyosis` itself and `adenomyosis_features_unknown`
  below, never conflated with it.
- `adenomyosis == 1` and the source feature is observed: each documented code
  in the comma-separated source string sets its corresponding indicator to
  `1`; this is **lossless** — a source value of `"1,3,4"` sets
  `adenomyosis_feature_1`, `adenomyosis_feature_3`, and `adenomyosis_feature_4`
  to `1`, all other indicators to `0`.

### `adenomyosis_features_unknown`
Binary indicator: `1` when `adenomyosis == 1` and no specific positive
sonographic feature is documented (source genuinely missing); `0` otherwise
(including all `adenomyosis == 0` rows). No feature imputation, no assignment
to a common combination, no patient-specific guessing.

### Parser safety
The upstream preprocessing parser (`normalize_multi_code_string`) rejects a
non-integer-valued token (e.g. `"3.4"`) rather than silently truncating it.
This section's own token-to-code parsing is a second, defensive layer over the
already-cleaned string: any token outside the approved 1–11 range triggers a
loud `ValueError` rather than being silently dropped or coerced.

### Export
`adenomyosis_sonographic_features_clean` (the raw source column) is excluded
from the Batch19 export — superseded by the multi-hot indicators. It remains
available in the preprocessing output.
""")

SB5F_ADENOMYOSIS = code("clean-b-s05f-adenomyosis", """
# -- adenomyosis multi-hot representation -----------------------------------
ADENOMYOSIS_FEATURE_CODES = list(range(1, 12))  # codes 1-11 only

_adeno = df_clean["adenomyosis"]
_adeno_src = df_clean["adenomyosis_sonographic_features_clean"]

_n_adeno0 = int((_adeno == 0).sum())
_n_adeno1 = int((_adeno == 1).sum())
_adeno_src_missing_a1 = int(_adeno_src[_adeno == 1].isna().sum())
_adeno_src_observed_a1 = int(_adeno_src[_adeno == 1].notna().sum())
print("Adenomyosis sonographic features -- multi-hot representation:")
print(f"  adenomyosis == 0 (structural / not applicable): {_n_adeno0}")
print(f"  adenomyosis == 1 (applicable subgroup)        : {_n_adeno1}")
print(f"  within applicable subgroup, feature observed  : {_adeno_src_observed_a1}")
print(f"  within applicable subgroup, feature missing   : {_adeno_src_missing_a1} "
      f"({round(_adeno_src_missing_a1/_n_adeno1*100,1) if _n_adeno1 else 0}%)")

# Precondition: adenomyosis==0 rows must never carry an observed feature
# value. Abort (do not silently overwrite) if violated.
_adeno0_observed = int(((_adeno == 0) & _adeno_src.notna()).sum())
if _adeno0_observed != 0:
    raise ValueError(
        f"STRUCTURAL DERIVATION ABORTED -- {_adeno0_observed} row(s) have adenomyosis==0 "
        "but an observed adenomyosis_sonographic_features_clean value. Cannot safely derive "
        "the adenomyosis multi-hot representation -- re-audit before implementing."
    )
print("\\nPrecondition check PASSED: 0 adenomyosis==0 rows have an observed feature value.")

_a1_mask = _adeno == 1
_observed_mask = _a1_mask & _adeno_src.notna()


def _parse_adenomyosis_codes(raw_value):
    # Defensive second layer over the already-cleaned, comma-separated
    # sorted-integer-code string (e.g. "1,3,4") produced upstream in
    # preprocessing. Any token that is not an exact integer in 1-11 fails
    # loud here -- never silently dropped or coerced (mirrors the upstream
    # normalize_multi_code_string contract).
    codes = set()
    for token in str(raw_value).split(","):
        token = token.strip()
        if token == "":
            continue
        if not token.lstrip("-").isdigit():
            raise ValueError(
                f"Adenomyosis multi-hot parsing ABORTED -- non-integer token {token!r} found in "
                f"adenomyosis_sonographic_features_clean value {raw_value!r}. The upstream parser "
                "should already reject this; re-audit preprocessing before proceeding."
            )
        code = int(token)
        if code not in ADENOMYOSIS_FEATURE_CODES:
            raise ValueError(
                f"Adenomyosis multi-hot parsing ABORTED -- code {code} outside the approved 1-11 "
                f"range found in adenomyosis_sonographic_features_clean value {raw_value!r}."
            )
        codes.add(code)
    return codes


_adeno_parsed_codes = _adeno_src.loc[_observed_mask].apply(_parse_adenomyosis_codes)

# Defensive non-empty-observed-code invariant. This section relies on the
# upstream contract that any non-missing adenomyosis_sonographic_features_clean
# value contains at least one approved 1-11 code (an empty parsed code list is
# mapped to NaN in preprocessing). If that contract is ever violated, an
# observed row parsing to the EMPTY set would silently become "all 11 feature
# indicators = 0 AND adenomyosis_features_unknown = 0" -- indistinguishable
# from a documented row with no positive features. Fail loud instead.
_adeno_empty_observed = int((_adeno_parsed_codes.map(len) == 0).sum())
if _adeno_empty_observed != 0:
    raise ValueError(
        f"Adenomyosis multi-hot ABORTED -- {_adeno_empty_observed} row(s) have "
        "adenomyosis==1 and a NON-MISSING adenomyosis_sonographic_features_clean value "
        "that parses to zero approved 1-11 codes. The upstream parser should have mapped "
        "such a value to NaN (genuinely-missing), routing it to adenomyosis_features_unknown; "
        "re-audit preprocessing before proceeding rather than silently producing an "
        "all-zero row that is neither a documented feature set nor the explicit unknown state."
    )

ADENOMYOSIS_MULTIHOT_COLS = []
for _code in ADENOMYOSIS_FEATURE_CODES:
    _col_name = f"adenomyosis_feature_{_code}"
    _col = pd.Series(0, index=df_clean.index, dtype="int64")
    _has_code_mask = pd.Series(False, index=df_clean.index)
    _has_code_mask.loc[_observed_mask] = _adeno_parsed_codes.apply(lambda codes, c=_code: c in codes)
    _col[_has_code_mask] = 1
    df_clean[_col_name] = _col
    ADENOMYOSIS_MULTIHOT_COLS.append(_col_name)

adenomyosis_features_unknown = pd.Series(0, index=df_clean.index, dtype="int64")
adenomyosis_features_unknown[_a1_mask & _adeno_src.isna()] = 1
df_clean["adenomyosis_features_unknown"] = adenomyosis_features_unknown

# ── Postconditions ─────────────────────────────────────────────────────────
_multihot_frame = df_clean[ADENOMYOSIS_MULTIHOT_COLS]
_row_sum = _multihot_frame.sum(axis=1)

# adenomyosis==0 rows: all 11 indicators 0, unknown 0.
_contradict_no_adeno = int(((_adeno == 0) & ((_row_sum != 0) | (df_clean["adenomyosis_features_unknown"] != 0))).sum())
if _contradict_no_adeno != 0:
    raise AssertionError(
        f"Adenomyosis multi-hot POSTCONDITION FAILED: {_contradict_no_adeno} adenomyosis==0 "
        "row(s) have a non-zero feature indicator or unknown flag."
    )
# adenomyosis==1 & feature missing: all 11 indicators 0, unknown 1.
_missing_a1_mask = _a1_mask & _adeno_src.isna()
_contradict_unknown = int(((_missing_a1_mask) & ((_row_sum != 0) | (df_clean["adenomyosis_features_unknown"] != 1))).sum())
if _contradict_unknown != 0:
    raise AssertionError(
        f"Adenomyosis multi-hot POSTCONDITION FAILED: {_contradict_unknown} adenomyosis==1/"
        "feature-missing row(s) do not have unknown=1 with all feature indicators 0."
    )
# adenomyosis==1 & feature observed: unknown 0, and at least 1 indicator set
# (every parsed code set is non-empty by construction upstream), and the
# indicator set exactly matches the parsed codes (lossless round-trip check).
_contradict_observed_unknown = int((_observed_mask & (df_clean["adenomyosis_features_unknown"] != 0)).sum())
if _contradict_observed_unknown != 0:
    raise AssertionError(
        f"Adenomyosis multi-hot POSTCONDITION FAILED: {_contradict_observed_unknown} "
        "feature-observed row(s) incorrectly have adenomyosis_features_unknown=1."
    )
_roundtrip_mismatches = 0
for _idx in df_clean.index[_observed_mask]:
    _expected_codes = _adeno_parsed_codes.loc[_idx]
    _actual_codes = {c for c in ADENOMYOSIS_FEATURE_CODES if df_clean.at[_idx, f"adenomyosis_feature_{c}"] == 1}
    if _expected_codes != _actual_codes:
        _roundtrip_mismatches += 1
if _roundtrip_mismatches != 0:
    raise AssertionError(
        f"Adenomyosis multi-hot POSTCONDITION FAILED: {_roundtrip_mismatches} row(s) failed the "
        "lossless round-trip check (parsed source codes != set indicators)."
    )
# No indicator column may contain a value outside {0, 1}.
for _col_name in ADENOMYOSIS_MULTIHOT_COLS + ["adenomyosis_features_unknown"]:
    _bad_values = sorted(set(df_clean[_col_name].unique()) - {0, 1})
    if _bad_values:
        raise AssertionError(f"{_col_name} POSTCONDITION FAILED: unexpected values {_bad_values}")

_adeno_multihot_counts = {c: int(df_clean[f"adenomyosis_feature_{c}"].sum()) for c in ADENOMYOSIS_FEATURE_CODES}
_n_unknown = int(df_clean["adenomyosis_features_unknown"].sum())
print("\\nPostcondition checks PASSED (adenomyosis==0 -> all indicators 0; adenomyosis==1 & "
      "feature missing -> unknown=1, all indicators 0; adenomyosis==1 & feature observed -> "
      "unknown=0, indicators exactly match parsed source codes -- lossless round-trip verified).")
print(f"Per-code counts (adenomyosis_feature_1..11): {_adeno_multihot_counts}")
print(f"adenomyosis_features_unknown count: {_n_unknown}")

for _code in ADENOMYOSIS_FEATURE_CODES:
    feature_dictionary.append(new_feature_dictionary_entry(
        new_column=f"adenomyosis_feature_{_code}",
        source_column="adenomyosis, adenomyosis_sonographic_features_clean",
        creation_rule=(
            f"binary indicator: 1 when adenomyosis==1 and code {_code} is documented present in "
            "adenomyosis_sonographic_features_clean's comma-separated code string; 0 otherwise "
            "(including all adenomyosis==0 rows and adenomyosis==1 rows where the feature is "
            "genuinely undocumented). 0 is not asserted as guaranteed clinical absence, only "
            "that the code was not documented as present. Lossless multi-hot replacement for the "
            "retired adenomyosis_sonographic_features_status combination-level categorical."
        ),
        timing="same_as_source",
        leakage_status="no",
        intended_use="review",
        creation_section="B5f",
        domain="endometriosis_phenotype",
        clinical_timing="pre_pregnancy",
        predictor_classification="predictor_allowed",
        stage="1",
        # No redundancy_group: a positive-disease binary flag and its
        # granular sub-feature multi-hot indicators are not mutually
        # exclusive, so these 11 code indicators must not be grouped with the
        # plain adenomyosis binary (EDA C's redundancy-group scoring would
        # otherwise demote them). Matches the endo_resection_* precedent,
        # which is unregistered for the same reason.
    ))
feature_dictionary.append(new_feature_dictionary_entry(
    new_column="adenomyosis_features_unknown",
    source_column="adenomyosis, adenomyosis_sonographic_features_clean",
    creation_rule=(
        "binary indicator: 1 when adenomyosis==1 and no specific positive sonographic feature "
        "is documented (source genuinely missing); 0 otherwise. No feature imputation, no "
        "assignment to a common combination."
    ),
    timing="same_as_source",
    leakage_status="no",
    intended_use="review",
    creation_section="B5f",
    domain="endometriosis_phenotype",
    clinical_timing="pre_pregnancy",
    predictor_classification="predictor_allowed",
    stage="1",
    # No redundancy_group -- see the matching comment above the code-indicator
    # loop for why (endo_resection_* precedent, not disclosure-only).
))
column_actions_log.append({
    "column": "adenomyosis_feature_1..11, adenomyosis_features_unknown",
    "stage": "B5f_adenomyosis_multihot",
    "action": "deterministic_multihot_no_imputation",
    "detail": f"per_code_counts={_adeno_multihot_counts}; unknown_count={_n_unknown}; imputation=none",
    "issue_type": "n/a",
    "action_taken": "deterministic_multihot_no_imputation",
    "base_variable": "adenomyosis",
    "reason": (
        "Multi-hot representation of the documented sonographic features, so a model can learn "
        "each documented feature's association independently rather than only whole opaque "
        "combinations. adenomyosis==0 is structurally all-zero. Within adenomyosis==1, each "
        "documented code sets its own indicator losslessly; genuinely missing feature detail is "
        "represented by adenomyosis_features_unknown rather than imputed. See "
        "docs/clinical_decisions/manual_decisions_log.md."
    ),
    "rows_removed": 0,
    "row_count_changed": False,
    "target_distribution_changed": False,
    "imputation_performed": False,
    "new_indicators_created": 12,
    "unknown_categories_created": int(_adeno_src_missing_a1 > 0),
    "requires_manual_decision_before_reversal": True,
})

for _code in ADENOMYOSIS_FEATURE_CODES:
    dcb_classification_snapshot, dcb_type_schema_snapshot = classification_lineage.register_feature(
        f"adenomyosis_feature_{_code}", "binary", "predictor_allowed",
        f"Approved pre-labor predictor: binary indicator for documented adenomyosis sonographic "
        f"feature code {_code}. Lossless multi-hot replacement for the retired "
        "adenomyosis_sonographic_features_status combination-level categorical.",
        df=df_clean, classification_df=dcb_classification_snapshot, type_schema_df=dcb_type_schema_snapshot,
    )
dcb_classification_snapshot, dcb_type_schema_snapshot = classification_lineage.register_feature(
    "adenomyosis_features_unknown", "binary", "predictor_allowed",
    "Approved pre-labor predictor: binary indicator for adenomyosis==1 rows with no specific "
    "positive sonographic feature documented. No feature imputation.",
    df=df_clean, classification_df=dcb_classification_snapshot, type_schema_df=dcb_type_schema_snapshot,
)

# Only the real raw source column needs an export-exclusion entry. The
# combination-level `adenomyosis_sonographic_features_status` categorical is
# never created as a df_clean column by this pipeline; the future-safety guard
# for that name lives in EDA C's `SUPERSEDED_RAW_VARS` check.
ADENOMYOSIS_SONOGRAPHIC_EXCLUDE_FROM_EXPORT = [
    "adenomyosis_sonographic_features_clean",
]
print(f"\\nColumns to exclude from final batch19 export (superseded by the adenomyosis "
      f"multi-hot representation): {ADENOMYOSIS_SONOGRAPHIC_EXCLUDE_FROM_EXPORT}")
""")


# ── Section B5g ────────────────────────────────────────────────────────────────
SB5G_HEADER = md("clean-b-s05g-header", """
## Section B5g — endo_surgery_adhesiolysis: Adhesion Status

Deterministic semantic replacements are created in Data Cleaning B (the same
pattern as `endometrioma_size_status`, `endometrioma_presence_laterality`, and
the adenomyosis multi-hot family). `derived_endo_surgery_adhesion_status` is
one of them; EDA C consumes it through the ordinary `B_CREATED_ANALYSIS_VARS`
pathway.

### Structural / applicable-subgroup split
`endo_surgery_adhesiolysis` is applicable only when `endometriosis_surgery == 1`
(prior endometriosis surgery). Within that applicable subgroup, this field
records whether adhesions were **documented** during that prior surgery — it
does not indicate whether adhesiolysis was **performed**;
`endo_resection_adhesiolysis` is the separate performed-procedure variable.

### derived_endo_surgery_adhesion_status
Three active categories only, because the current cohort has **zero**
genuinely missing rows within the applicable (`endometriosis_surgery == 1`)
subgroup:
- `no_prior_endo_surgery` (`endometriosis_surgery == 0`, structural).
- `prior_surgery_with_documented_adhesions` (`endometriosis_surgery == 1` and
  `endo_surgery_adhesiolysis == 1`).
- `prior_surgery_without_documented_adhesions` (`endometriosis_surgery == 1`
  and `endo_surgery_adhesiolysis == 0`).

No fourth "unknown" category is invented for a case that does not currently
exist in the data — a genuinely missing applicable row would fail loud
(`ValueError`) rather than being silently absorbed into one of the three
categories above, so a future data update that violates this invariant
surfaces explicitly instead of being masked.

### Export
Raw `endo_surgery_adhesiolysis` is excluded from the final export (source
retained upstream in preprocessing for provenance).
""")

SB5G_ADHESION_STATUS = code("clean-b-s05g-adhesion-status", """
# -- derived_endo_surgery_adhesion_status -----------------------------------
_adhesiolysis_status_srcs = ["endometriosis_surgery", "endo_surgery_adhesiolysis"]
_adhesiolysis_status_missing_cols = [c for c in _adhesiolysis_status_srcs if c not in df_clean.columns]
if _adhesiolysis_status_missing_cols:
    raise ValueError(
        "derived_endo_surgery_adhesion_status requires endometriosis_surgery and "
        f"endo_surgery_adhesiolysis; missing: {_adhesiolysis_status_missing_cols}"
    )

_no_endo_surgery = df_clean["endometriosis_surgery"] == 0
_has_endo_surgery = df_clean["endometriosis_surgery"] == 1
_adhesiolysis_src = df_clean["endo_surgery_adhesiolysis"]

# Invariant check FIRST: this notebook only ever creates the 3 active
# categories below. If the current cohort ever has a genuinely missing
# applicable row (endometriosis_surgery==1 & endo_surgery_adhesiolysis NaN),
# fail loud rather than silently inventing/omitting a 4th category.
_n_genuine_missing_applicable = int((_has_endo_surgery & _adhesiolysis_src.isna()).sum())
if _n_genuine_missing_applicable != 0:
    raise ValueError(
        f"derived_endo_surgery_adhesion_status: {_n_genuine_missing_applicable} row(s) have "
        "endometriosis_surgery==1 and genuinely missing endo_surgery_adhesiolysis -- this "
        "invariant (0 genuine missing in the applicable subgroup) no longer holds for the "
        "current cohort. A 4th active category is required before this construction can "
        "proceed; re-audit and update this section rather than silently absorbing these rows "
        "into one of the 3 existing categories."
    )

derived_endo_surgery_adhesion_status = pd.Series(pd.NA, index=df_clean.index, dtype="string")
derived_endo_surgery_adhesion_status[_no_endo_surgery] = "no_prior_endo_surgery"
derived_endo_surgery_adhesion_status[_has_endo_surgery & (_adhesiolysis_src == 0)] = "prior_surgery_without_documented_adhesions"
derived_endo_surgery_adhesion_status[_has_endo_surgery & (_adhesiolysis_src == 1)] = "prior_surgery_with_documented_adhesions"
df_clean["derived_endo_surgery_adhesion_status"] = derived_endo_surgery_adhesion_status

_adhesion_status_allowed = {
    "no_prior_endo_surgery",
    "prior_surgery_with_documented_adhesions",
    "prior_surgery_without_documented_adhesions",
}
_n_missing_adhesion_status = int(df_clean["derived_endo_surgery_adhesion_status"].isna().sum())
if _n_missing_adhesion_status != 0:
    raise AssertionError(
        f"derived_endo_surgery_adhesion_status POSTCONDITION FAILED: expected 0 missing, "
        f"got {_n_missing_adhesion_status}"
    )
if not set(df_clean["derived_endo_surgery_adhesion_status"].dropna().unique()).issubset(_adhesion_status_allowed):
    raise AssertionError("derived_endo_surgery_adhesion_status POSTCONDITION FAILED: unexpected category label.")
_adhesion_status_counts = df_clean["derived_endo_surgery_adhesion_status"].value_counts(dropna=False).to_dict()
print(f"\\nderived_endo_surgery_adhesion_status finalized (relocated from EDA C). "
      f"Counts: {_adhesion_status_counts}")

feature_dictionary.append(new_feature_dictionary_entry(
    new_column="derived_endo_surgery_adhesion_status",
    source_column="endometriosis_surgery, endo_surgery_adhesiolysis",
    creation_rule=(
        "categorical full-cohort status: no_prior_endo_surgery when endometriosis_surgery==0 "
        "(structural); prior_surgery_with_documented_adhesions when endometriosis_surgery==1 "
        "and endo_surgery_adhesiolysis==1; prior_surgery_without_documented_adhesions when "
        "endometriosis_surgery==1 and endo_surgery_adhesiolysis==0. Documents adhesion FINDING, "
        "not whether adhesiolysis was performed (see endo_resection_adhesiolysis for the "
        "performed-procedure variable). No 4th 'unknown' category exists because the current "
        "cohort has 0 genuinely missing applicable rows; construction fails loud if that "
        "invariant is ever violated by future data."
    ),
    timing="same_as_source",
    leakage_status="no",
    intended_use="review",
    creation_section="B5g",
    domain="prior_endo_surgery",
    clinical_timing="pre_pregnancy",
    predictor_classification="predictor_allowed",
    stage="1",
    redundancy_group="endo_surgery_adhesion_status_representation",
    # Disclose the deterministic redundancy: this status reconstructs the
    # endometriosis_surgery binary (no_prior_endo_surgery -> 0, else -> 1),
    # exactly as indication_for_induction_status reconstructs induction_any_bin.
    # Both may remain in Batch19; the canonical EDA C hard co-entry contract
    # (contracts/model_coentry_constraints.yaml) registers
    # derived_endo_surgery_adhesion_status <-> endometriosis_surgery as a hard
    # pair, preventing simultaneous independent model entry (resolved pre-fit
    # in final modeling).
    redundant_with="endometriosis_surgery",
))
column_actions_log.append({
    "column": "derived_endo_surgery_adhesion_status",
    "stage": "B5g_endo_surgery_adhesion_status_relocated_from_eda_c",
    "action": "deterministic_categorical_status_no_imputation",
    "detail": f"counts={_adhesion_status_counts}; imputation=none",
    "issue_type": "n/a",
    "action_taken": "deterministic_categorical_status_no_imputation",
    "base_variable": "endo_surgery_adhesiolysis",
    "reason": (
        "Deterministic semantic replacement built in Data Cleaning B (Section B5g). "
        "Only 3 active categories "
        "(0 genuinely missing applicable rows in the current cohort); construction "
        "fails loud if that invariant is ever violated. See "
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

# Classification-lineage: register derived_endo_surgery_adhesion_status (approved).
dcb_classification_snapshot, dcb_type_schema_snapshot = classification_lineage.register_feature(
    "derived_endo_surgery_adhesion_status", "categorical", "predictor_allowed",
    "Approved pre-labor predictor representation of documented adhesion status during "
    "prior endometriosis surgery; relocated from EDA C to Data Cleaning B (2026-08-27). "
    "Does not represent whether adhesiolysis was performed.",
    df=df_clean, classification_df=dcb_classification_snapshot, type_schema_df=dcb_type_schema_snapshot,
)

ENDO_SURGERY_ADHESIOLYSIS_EXCLUDE_FROM_EXPORT = ["endo_surgery_adhesiolysis"]
print(f"\\nColumns to exclude from final batch19 export (superseded by "
      f"derived_endo_surgery_adhesion_status): {ENDO_SURGERY_ADHESIOLYSIS_EXCLUDE_FROM_EXPORT}")
""")


# ── Section B5h ────────────────────────────────────────────────────────────────
SB5H_HEADER = md("clean-b-s05h-header", """
## Section B5h — indication_for_induction_status

### Structural / applicable-subgroup split
`indication_for_induction_clean` is applicable only when `induction_any_bin == 1`.
Within `induction_any_bin == 0` rows the field is structurally not-applicable
(no induction occurred).

### indication_for_induction_status
Three active category types:
- `no_induction` (`induction_any_bin == 0`, structural — 237 rows in the
  current cohort).
- `induction_indication_unknown` (`induction_any_bin == 1` and the indication
  is genuinely missing — 4 rows in the current cohort).
- Otherwise, the observed indication string is preserved **verbatim**,
  including multi-indication combinations (190 rows in the current cohort) —
  not split, grouped, or altered.

### Redundancy with induction_any_bin
`induction_any_bin` is reconstructable from this status
(`no_induction` → 0, anything else → 1) — registered as a redundancy pair so
EDA C/modeling do not automatically co-select both as independent predictors.

### Export
Raw `indication_for_induction_clean` is excluded from the final export
(source retained upstream in preprocessing for provenance).
""")

SB5H_INDICATION_STATUS = code("clean-b-s05h-indication-status", """
# -- indication_for_induction_status --------------------------------------
_induction_status_srcs = ["induction_any_bin", "indication_for_induction_clean"]
_induction_status_missing_cols = [c for c in _induction_status_srcs if c not in df_clean.columns]
if _induction_status_missing_cols:
    raise ValueError(
        f"indication_for_induction_status requires {_induction_status_srcs}; "
        f"missing: {_induction_status_missing_cols}"
    )

_no_induction_mask = df_clean["induction_any_bin"] == 0
_has_induction_mask = df_clean["induction_any_bin"] == 1
_indication_src = df_clean["indication_for_induction_clean"]

# Applicability invariant: an indication is only meaningful when an induction
# actually occurred (induction_any_bin==1). A row with induction_any_bin==0 AND
# a non-missing indication_for_induction_clean is a contradiction (0 remain in
# the current cohort). Fail loud rather than silently labelling it
# "no_induction" and discarding the contradictory observed indication.
_contradictory_indication_n = int((_no_induction_mask & _indication_src.notna()).sum())
if _contradictory_indication_n != 0:
    raise ValueError(
        f"indication_for_induction_status ABORTED -- {_contradictory_indication_n} row(s) have "
        "induction_any_bin==0 (no induction) but a non-missing indication_for_induction_clean. "
        "This contradiction must be resolved upstream (as Decision 26 did) before this "
        "categorical can be built; it is not silently absorbed into 'no_induction'."
    )

indication_for_induction_status = pd.Series(pd.NA, index=df_clean.index, dtype="object")
indication_for_induction_status[_no_induction_mask] = "no_induction"
indication_for_induction_status[_has_induction_mask & _indication_src.isna()] = "induction_indication_unknown"
_observed_induction_mask = _has_induction_mask & _indication_src.notna()
indication_for_induction_status.loc[_observed_induction_mask] = _indication_src.loc[_observed_induction_mask]
df_clean["indication_for_induction_status"] = indication_for_induction_status.astype("object")

_n_missing_induction_status = int(df_clean["indication_for_induction_status"].isna().sum())
if _n_missing_induction_status != 0:
    raise AssertionError(
        f"indication_for_induction_status POSTCONDITION FAILED: expected 0 missing, "
        f"got {_n_missing_induction_status}"
    )
_n_no_induction = int((df_clean["indication_for_induction_status"] == "no_induction").sum())
_n_unknown_induction = int((df_clean["indication_for_induction_status"] == "induction_indication_unknown").sum())
_n_observed_induction = int(_observed_induction_mask.sum())
if _n_no_induction != int(_no_induction_mask.sum()):
    raise AssertionError("indication_for_induction_status POSTCONDITION FAILED: no_induction count mismatch.")
if _n_unknown_induction != int((_has_induction_mask & _indication_src.isna()).sum()):
    raise AssertionError("indication_for_induction_status POSTCONDITION FAILED: unknown count mismatch.")
_contradict_observed_preserved = int(
    (df_clean.loc[_observed_induction_mask, "indication_for_induction_status"] != _indication_src.loc[_observed_induction_mask]).sum()
)
if _contradict_observed_preserved != 0:
    raise AssertionError(
        f"indication_for_induction_status POSTCONDITION FAILED: {_contradict_observed_preserved} "
        "observed-indication row(s) were not preserved verbatim."
    )
print(f"\\nindication_for_induction_status finalized: no_induction={_n_no_induction}, "
      f"induction_indication_unknown={_n_unknown_induction}, observed_preserved={_n_observed_induction}, "
      f"missing=0")

feature_dictionary.append(new_feature_dictionary_entry(
    new_column="indication_for_induction_status",
    source_column="induction_any_bin, indication_for_induction_clean",
    creation_rule=(
        "categorical full-cohort status: no_induction when induction_any_bin==0 (structural); "
        "induction_indication_unknown when induction_any_bin==1 and indication_for_induction_clean "
        "is genuinely missing; otherwise the observed indication string preserved verbatim "
        "(including multi-indication combinations, unmodified). induction_any_bin is "
        "reconstructable from this status (no_induction -> 0, else -> 1) -- registered as a "
        "redundancy pair, not independently selectable alongside this status."
    ),
    timing="same_as_source",
    leakage_status="no",
    intended_use="review",
    creation_section="B5h",
    domain="labor_induction",
    # "admission_labor" (not "intrapartum") -- matches EDA C's recognized
    # clinical_timing vocabulary (normalize_timing_label() in
    # eda_c_part4_screening.py maps "admission_labor" -> "admission_or_pre_delivery";
    # any unrecognized string silently degrades to "timing_unknown").
    clinical_timing="admission_labor",
    predictor_classification="intrapartum_predictor_exclude_from_prelabor_model",
    stage="3",
    redundancy_group="indication_for_induction_status_representation",
    redundant_with="induction_any_bin",
))
column_actions_log.append({
    "column": "indication_for_induction_status",
    "stage": "B5h_indication_for_induction_status_new",
    "action": "deterministic_categorical_status_no_imputation",
    "detail": (
        f"no_induction={_n_no_induction}, induction_indication_unknown={_n_unknown_induction}, "
        f"observed_preserved={_n_observed_induction}; imputation=none"
    ),
    "issue_type": "n/a",
    "action_taken": "deterministic_categorical_status_no_imputation",
    "base_variable": "indication_for_induction_clean",
    "reason": (
        "Deterministic Stage-3-only categorical representation for "
        "indication_for_induction_clean, following the same applicability-aware "
        "structural/genuine-unknown pattern as adenomyosis/endometrioma/PPROM. "
        "See docs/clinical_decisions/manual_decisions_log.md."
    ),
    "rows_removed": 0,
    "row_count_changed": False,
    "target_distribution_changed": False,
    "imputation_performed": False,
    "new_indicators_created": 0,
    "unknown_categories_created": int(_n_unknown_induction > 0),
    "requires_manual_decision_before_reversal": True,
})

# Classification-lineage: register indication_for_induction_status (approved).
dcb_classification_snapshot, dcb_type_schema_snapshot = classification_lineage.register_feature(
    "indication_for_induction_status", "categorical", "intrapartum_predictor_exclude_from_prelabor_model",
    "New (2026-08-27): Stage-3-only categorical representation of the induction "
    "indication -- structural no_induction, genuine induction_indication_unknown, or "
    "the observed indication preserved verbatim. Redundant with induction_any_bin.",
    df=df_clean, classification_df=dcb_classification_snapshot, type_schema_df=dcb_type_schema_snapshot,
)

INDICATION_FOR_INDUCTION_EXCLUDE_FROM_EXPORT = ["indication_for_induction_clean"]
print(f"\\nColumns to exclude from final batch19 export (superseded by "
      f"indication_for_induction_status): {INDICATION_FOR_INDUCTION_EXCLUDE_FROM_EXPORT}")
""")


# ── Section B6 ─────────────────────────────────────────────────────────────────
SB6_HEADER = md("clean-b-s06-header", """
## Section B6 — Imputation Plan

### Modeling-safety rule
Learned imputations (kNN, iterative, model-based) must be **fitted inside the
modeling pipeline / cross-validation training folds**, never globally before
evaluation. Doing it globally leaks information across the train/test boundary.

Therefore this section **only produces an imputation plan**. No learned
imputation, opt-in or otherwise, is performed anywhere in Data Cleaning B --
there is no opt-in kNN preview path of any kind.

### Scope of this plan
This section is **not** silent about downstream treatment. Four distinct
concepts apply, and every row of the plan falls under exactly one of them:

**A. Data Cleaning B itself performs no learned imputation.** No kNN, no
iterative/model-based imputer, no median fit — nothing data-dependent is
fitted here, opt-in or otherwise.

**B. Where an imputation / representation METHOD has already been approved,
this section documents that method explicitly** (via `_EXPLICIT_PLAN_OVERRIDES`
below), rather than deferring it as an unspecified downstream choice. The
approved methods are:
- `height` — median imputation.
- `weight_before_pregnancy` — median imputation.
- `Hb_before_delivery` — median imputation.
- `BMI_after` — fold-safe observed-value tertile categorical representation
  (`low_observed` / `mid_observed` / `high_observed` + `not_documented`).
- `weight_in_pregnancy` — fold-safe observed-value tertile categorical
  representation (same architecture as `BMI_after`).
- `gestational_age_at_PPROM_days` — fold-safe applicability-gated four-state
  timing representation (`no_PPROM` / `PPROM_earlier` / `PPROM_later` /
  `PPROM_timing_unknown`).

**C. For every method in (B), only the learned PARAMETER is fitted downstream,
inside the modeling cross-validation training folds** — a median, the
`q33`/`q67` tertile cutpoints, the PPROM-timing median split. That is a
fitting-LOCATION deferral for leakage safety, never a sign that the method
itself is undecided or "finalized downstream."

**D. For a generic fallback variable with no approved variable-specific
treatment, this section correctly states only that the downstream strategy, if
any, is finalized in modeling** — it does not invent one, and it does not
promise that a missing-indicator column is created anywhere. A source column
having NaN values does **not** by itself guarantee any downstream
missing-indicator column.
""")

SB6_PLAN = code("clean-b-s06-plan", """
# Variables with an explicit, non-generic plan (checked before the generic
# numeric/binary/categorical fallback below). Data Cleaning B closes the
# method/representation decision for every entry; only learned PARAMETER
# FITTING (a median, a quantile cutpoint) is deferred to modeling training
# folds -- a fitting-location detail, not an undecided treatment.
_EXPLICIT_PLAN_OVERRIDES = {
    # height, weight_before_pregnancy, Hb_before_delivery: no global KNN (an
    # imputation-leakage risk); NaN is preserved here and ordinary median
    # imputation is fitted training-fold-only in modeling (SimpleImputer inside
    # modeling_core.py's shared ColumnTransformer).
    "height": (
        "APPROVED: median imputation. Data Cleaning B preserves NaN and "
        "performs no imputation itself -- the median is fitted "
        "training-fold-only in modeling (SimpleImputer, modeling_core.py). "
        "Only the fitting location is deferred.",
        "approved_median_fold_safe_modeling_core",
    ),
    "weight_before_pregnancy": (
        "APPROVED: median imputation. Data Cleaning B preserves NaN and "
        "performs no imputation itself -- the median is fitted "
        "training-fold-only in modeling (SimpleImputer, modeling_core.py). "
        "Only the fitting location is deferred.",
        "approved_median_fold_safe_modeling_core",
    ),
    "Hb_before_delivery": (
        "APPROVED: median imputation. Data Cleaning B preserves NaN and "
        "performs no imputation itself -- the median is fitted "
        "training-fold-only in modeling (SimpleImputer, modeling_core.py). "
        "Only the fitting location is deferred.",
        "approved_median_fold_safe_modeling_core",
    ),
    # BMI_after / weight_in_pregnancy (40-70% missing band): the approved
    # representation is a fold-safe observed-value tertile categorical; an
    # explicit override entry names it here rather than letting these fall
    # through to the vague generic numeric fallback below.
    "BMI_after": (
        "APPROVED: fold-safe observed-value tertile categories "
        "(low_observed/mid_observed/high_observed) plus not_documented for "
        "missing rows -- q33/q67 cutpoints fitted training-fold-only in "
        "modeling (FoldSafeQuantileCategoryTransformer, modeling_core.py). "
        "Data Cleaning B materializes no dataframe column for this "
        "representation (Section B5b); the continuous source value and its "
        "original NaNs are preserved as-is. No numerical imputation of the raw "
        "continuous value is approved -- only the categorical representation. "
        "Only the cutpoint fitting location is deferred.",
        "approved_fold_safe_tertile_deferred_fitting",
    ),
    "weight_in_pregnancy": (
        "APPROVED: fold-safe observed-value tertile categories "
        "(low_observed/mid_observed/high_observed) plus not_documented for "
        "missing rows -- q33/q67 cutpoints fitted training-fold-only in "
        "modeling (FoldSafeQuantileCategoryTransformer, modeling_core.py). "
        "Data Cleaning B materializes no dataframe column for this "
        "representation (Section B5b); the continuous source value and its "
        "original NaNs are preserved as-is. "
        "No separate missingness indicator is created -- the fold-safe "
        "categorical's not_documented bucket carries the missingness "
        "information. No numerical imputation of the raw continuous value is "
        "approved -- only the categorical representation. Only the cutpoint "
        "fitting location is deferred.",
        "approved_fold_safe_tertile_deferred_fitting",
    ),
    # endo_surgery_adhesiolysis (40-70% missing band): the deterministic
    # subgroup-aware representation is created in Data Cleaning B itself
    # (Section B5g).
    "endo_surgery_adhesiolysis": (
        "none for the raw field -- do not apply ordinary most-frequent "
        "imputation. Section B5g creates the deterministic, final "
        "derived_endo_surgery_adhesion_status representation (3 categories: "
        "no_prior_endo_surgery / prior_surgery_without_documented_adhesions / "
        "prior_surgery_with_documented_adhesions) from the "
        "endometriosis_surgery / endo_surgery_adhesiolysis subgroup context. "
        "The raw column is dropped from the final B export (Section B7).",
        "not_applicable_use_derived_subgroup_aware_representation",
    ),
    "gestational_age_at_PPROM_days": (
        "APPROVED: four-state structural/applicability-gated timing "
        "representation -- no_PPROM (PPROM==0, structural), PPROM_earlier / "
        "PPROM_later (PPROM==1, observed timing vs. a training-fold-only "
        "median split of the applicable subgroup), PPROM_timing_unknown "
        "(PPROM==1, genuinely missing timing -- currently 1/17 applicable "
        "rows). Split-point fitted training-fold-only in modeling "
        "(FoldSafeQuantileCategoryTransformer, modeling_core.py); never "
        "derived from gestational_age_at_delivery_days. Data Cleaning B "
        "materializes no dataframe column for this representation "
        "(Section B5b). Only the split-point fitting location is deferred; "
        "the applicable-subgroup denominator (17) and its genuinely-missing "
        "count (1) are structural facts established here (Section B4b).",
        "approved_fold_safe_applicability_gated_split_deferred_fitting",
    ),
    "indication_for_induction_clean": (
        "none for the raw field -- classified "
        "intrapartum_predictor_exclude_from_prelabor_model (Stage 3 / "
        "intrapartum horizon only). Section B5h creates the deterministic, "
        "final indication_for_induction_status representation (no_induction / "
        "induction_indication_unknown / the observed indication string "
        "verbatim); the 4 applicable-missing rows are resolved as "
        "induction_indication_unknown by that representation. The raw column "
        "is dropped from the final B export (Section B7).",
        "not_applicable_use_derived_subgroup_aware_representation",
    ),
}

for col in CLEANING_SCOPE:
    if col not in df_clean.columns:
        continue
    var_type = infer_var_type(df_clean[col])
    miss_pct = float(df_clean[col].isna().mean() * 100)
    is_structural = col in STRUCTURAL_NAN_COLS
    is_pending_structural_unconfirmed = col in APPLICABILITY_LINKED_NO_PREPROCESSING_MASK_COLS
    is_row_gated = col in ROW_APPLICABILITY_GATES
    applicable_missing_pct_if_row_gated = None
    if is_row_gated:
        # missing_% below stays the raw whole-cohort % like every other row in
        # this table; the applicable-subset % is reported separately here so
        # neither number is silently dropped (Section B4b has the full breakdown).
        _rg_gate = ROW_APPLICABILITY_GATES[col]
        _rg_mask = df_clean[_rg_gate["gate_column"]] == _rg_gate["applicable_value"]
        _rg_n_applicable = int(_rg_mask.sum())
        _rg_n_missing = int((_rg_mask & df_clean[col].isna()).sum())
        applicable_missing_pct_if_row_gated = (
            round(_rg_n_missing / _rg_n_applicable * 100, 1) if _rg_n_applicable else None
        )
    is_endometrioma_detail_source = col in (
        "endometrioma_size_clean", "endometrioma_place_clean", "endometrioma_laterality"
    )
    is_adenomyosis_detail_source = col == "adenomyosis_sonographic_features_clean"
    is_cat_unknown_source = col in CAT_UNKNOWN_EXCLUDE_FROM_EXPORT
    # weight_before_pregnancy, height, Hb_before_delivery have an approved
    # method (median imputation, fitted training-fold-only in modeling), so all
    # three are caught by _EXPLICIT_PLAN_OVERRIDES above and do NOT fall through
    # to the generic numeric branch. BMI_before is handled inline here: a
    # deterministic formula recompute (observed inputs only), not imputation.
    is_bmi_before_partial_formula = col == "BMI_before"

    if col in _EXPLICIT_PLAN_OVERRIDES:
        plan, fit_location = _EXPLICIT_PLAN_OVERRIDES[col]
    elif is_endometrioma_detail_source:
        plan = (
        "none -- replaced by endometrioma_size_status / endometrioma_presence_laterality "
            "(Section B5c); no imputation performed; excluded from final export"
        )
        # Raw source column: not imputed, replaced by a deterministic B
        # representation, and excluded from Batch19 -- no learned parameter is
        # ever fitted for it, so a "fitted in modeling CV" location would be a
        # false promise.
        fit_location = "not_applicable_replaced_by_deterministic_representation"
    elif is_adenomyosis_detail_source:
        plan = (
            "none -- row-specific applicability gate (adenomyosis==1), confirmed empirically; "
            "not-applicable rows (adenomyosis==0) are structural and never imputed or "
            "indicated; replaced by the adenomyosis multi-hot representation "
            "(adenomyosis_feature_1..11 + adenomyosis_features_unknown, Section B5f), "
            "which represents genuinely unresolved applicable rows via the explicit "
            "adenomyosis_features_unknown indicator rather than imputing them; "
            "no imputation performed; raw source excluded from final export"
        )
        fit_location = "not_applicable_row_specific_applicability_gate"
    elif is_cat_unknown_source:
        plan = (
            f"none -- replaced by {col}_cat (categorical + not_documented, Section B5e); "
            "no imputation performed; excluded from final export"
        )
        # severe_PET / any_PET raw source columns: not imputed, replaced by the
        # deterministic {col}_cat representation and excluded from Batch19; no
        # learned parameter is fitted anywhere.
        fit_location = "not_applicable_replaced_by_deterministic_representation"
    elif is_bmi_before_partial_formula:
        plan = (
            "Data Cleaning B deterministically recomputes BMI_before = "
            "weight_before_pregnancy/(height/100)^2 only for rows where both "
            "inputs are observed (Section B5d); not a learned imputation. "
            "Rows where either input remains missing keep BMI_before as NaN in "
            "the exported Batch19. At modeling time, if BMI_before is selected, "
            "modeling_core.py's FoldSafeRecomputedBMITransformer fold-safe-medians "
            "height/weight_before_pregnancy (training-fold-only) and recomputes "
            "BMI_before from those -- BMI_before itself is never directly "
            "median-imputed."
        )
        fit_location = "data_cleaning_b_partial_formula_recompute_observed_inputs_only"
    elif miss_pct == 0:
        plan = "none"
        # 0% missing in the current cohort and no learned fit required --
        # nothing is fitted for this column in any training fold.
        fit_location = "not_applicable_no_imputation_needed"
    elif is_structural:
        plan = "not imputed in Data Cleaning B; subgroup-aware NaN is preserved (no standalone missingness indicator retained for this variable -- see Section B4's SUPPRESSED_MISSING_INDICATOR_COLS). Downstream imputation strategy, if any, is finalized in modeling."
        fit_location = "modeling_cv_train_fold_only"
    elif is_pending_structural_unconfirmed:
        plan = (
            "none -- empirically row-applicability gated but not "
            "code-enforced in preprocessing "
            f"(see APPLICABILITY_LINKED_NO_PREPROCESSING_MASK_REASONS['{col}']); raw NaNs "
            "preserved as ordinary missingness; no automatic imputation-plan "
            "approval and no invented indicator/representation in this task; "
            "requires explicit clinical/source confirmation before any handling "
            "decision"
        )
        fit_location = "not_applicable_pending_structural_confirmation"
    elif var_type == "numeric":
        # Generic fallback: NaN preserved as-is. Whether a downstream
        # missing-indicator column is created is a modeling-pipeline detail,
        # not guaranteed or described by this plan.
        plan = "not imputed in Data Cleaning B; NaN preserved as-is. Downstream imputation strategy (if any) is finalized in modeling, fitted only within training folds."
        fit_location = "modeling_cv_train_fold_only"
    elif var_type == "binary":
        plan = "not imputed in Data Cleaning B; NaN preserved as-is. Downstream imputation strategy (if any) is finalized in modeling, fitted only within training folds."
        fit_location = "modeling_cv_train_fold_only"
    else:
        plan = "not imputed in Data Cleaning B; NaN preserved as-is. Downstream categorical encoding/imputation strategy (if any) is finalized in modeling, fitted only within training folds."
        fit_location = "modeling_cv_train_fold_only"

    imputation_plan.append({
        "column": col,
        "type": var_type,
        "missing_%": round(miss_pct, 1),
        "applicable_subset_missing_%": applicable_missing_pct_if_row_gated,
        "structural_nan": is_structural,
        # applicability_linked_no_preprocessing_mask: True means only that no
        # code-enforced preprocessing subgroup gate (set_outside_subgroup_to_na
        # or equivalent) exists for this column -- a statement about
        # preprocessing-gate provenance, not about whether this column's
        # Data Cleaning B handling is unresolved. Each variable's actual status
        # is stated in its own `imputation_plan` text above.
        "applicability_linked_no_preprocessing_mask": is_pending_structural_unconfirmed,
        "imputation_plan": plan,
        "fit_location": fit_location,
    })

# severe_PET_cat / any_PET_cat: not_documented is a valid category, so no
# imputation plan is needed for either.
for col in pet_cat_created:
    imputation_plan.append({
        "column": col,
        "type": "categorical",
        "missing_%": round(float(df_clean[col].isna().mean() * 100), 1),
        "structural_nan": False,
        "imputation_plan": "none -- not_documented is a valid category label, not a missing value",
        # Materialized deterministic representation, 0% missing by
        # construction, no learned parameter fitted anywhere.
        "fit_location": "not_applicable_deterministic_no_fit",
    })

# Derived endometrioma variables: deterministic categorical full-cohort
# representations. Unknown size / laterality states are explicit categories,
# not imputed.
imputation_plan.append({
    "column": "endometrioma_size_status",
    "type": "categorical",
    "missing_%": round(float(df_clean["endometrioma_size_status"].isna().mean() * 100), 1),
    "structural_nan": False,
    "imputation_plan": (
        "not imputed in Data Cleaning B; structural no-endometrioma and genuinely "
        "unknown endometrioma size are represented as explicit categorical states"
    ),
    "fit_location": "not_applicable_deterministic_no_fit",
})
imputation_plan.append({
    "column": "endometrioma_presence_laterality",
    "type": "categorical",
    "missing_%": round(float(df_clean["endometrioma_presence_laterality"].isna().mean() * 100), 1),
    "structural_nan": False,
    "imputation_plan": (
        "not imputed in Data Cleaning B; genuinely unresolved endometrioma==1 laterality "
        "is the explicit laterality_unknown category (0 missing), not true missing and "
        "not imputed"
    ),
    "fit_location": "not_applicable_deterministic_no_fit",
})

# Adenomyosis multi-hot family: one entry per code indicator plus the unknown
# indicator, all 0% missing by construction (binary 0/1, never NaN).
for _adeno_col in ADENOMYOSIS_MULTIHOT_COLS + ["adenomyosis_features_unknown"]:
    imputation_plan.append({
        "column": _adeno_col,
        "type": "binary",
        "missing_%": round(float(df_clean[_adeno_col].isna().mean() * 100), 1),
        "structural_nan": False,
        "imputation_plan": (
            "not imputed in Data Cleaning B; structural no-adenomyosis and genuinely unknown "
            "sonographic-feature detail are represented as explicit 0/1 indicator states"
        ),
        "fit_location": "not_applicable_deterministic_no_fit",
    })

imputation_plan_df = pd.DataFrame(imputation_plan).sort_values("missing_%", ascending=False)
print("Imputation / treatment plan (planning only -- any learned parameter is "
      "fitted inside modeling cross-validation training folds):")
print("  fit_location distribution:", imputation_plan_df["fit_location"].value_counts().to_dict())
# Compact reader-facing view: the variable-specific approved plans (anything
# not routed through a generic fallback). The full 87-row plan for every scope
# column is written to outputs/data_cleaning/audit/cleaning_b_imputation_plan.csv.
_special_plan = imputation_plan_df[
    ~imputation_plan_df["fit_location"].isin(
        ["not_applicable_no_imputation_needed", "not_applicable_deterministic_no_fit"])
]
print(f"\\n  Variable-specific plans ({len(_special_plan)} of {len(imputation_plan_df)}):")
print(_special_plan[["column", "type", "missing_%", "fit_location"]].to_string(index=False))
print("  Full plan: outputs/data_cleaning/audit/cleaning_b_imputation_plan.csv")
""")

SB6_OPTIONAL_KNN = code("clean-b-s06-optional-knn", """
# Data Cleaning B and EDA C implement no learned imputation in any form -- not
# even an opt-in / off-by-default preview. All learned imputation is deferred
# to the modeling pipeline, fitted within each subject-grouped training fold.
print("Learned imputation is not performed in Data Cleaning B. Deferred "
      "entirely to the modeling pipeline, fitted within each subject-grouped "
      "training fold only.")
""")


CLEANING_B_PART4_CELLS = [
    SB5_HEADER,
    SB5_TRANSFORM,
    SB5B_HEADER,
    SB5B_STATCAT,
    SB5C_HEADER,
    SB5C_ENDOMETRIOMA,
    SB5D_HEADER,
    SB5D_ANTHROPOMETRY,
    SB5E_HEADER,
    SB5E_CATEGORICAL_UNKNOWN,
    SB5F_HEADER,
    SB5F_ADENOMYOSIS,
    SB5G_HEADER,
    SB5G_ADHESION_STATUS,
    SB5H_HEADER,
    SB5H_INDICATION_STATUS,
    SB6_HEADER,
    SB6_PLAN,
    SB6_OPTIONAL_KNN,
]


if __name__ == "__main__":
    print(f"Data Cleaning B Part 4 cells defined: {len(CLEANING_B_PART4_CELLS)}")

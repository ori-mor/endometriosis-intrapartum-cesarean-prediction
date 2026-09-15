# Data Cleaning B — Section 2 (After Initial EDA)

> **Canonical-repository README — read in submission context.** This file
> was copied from the private canonical research repository. Internal paths
> (`outputs/...`, `analysis/...`, `docs/...`, and the canonical
> `notebooks/eda/02_...`/`02b_...`/`03_...`/`04_...` naming — this
> submission's own notebooks are flatter, e.g.
> `notebooks/03_data_cleaning.ipynb`, see the root `README.md`), Git commit
> policy, and `.gitignore` references below describe *that* repository, not
> this curated submission. This submission intentionally tracks a different, narrower set
> of files — approved *executed* notebooks and privacy-safe aggregate
> `.csv`/`.xlsx` artifacts alongside source, most of which the canonical
> policy below would gitignore. Submission-specific inclusion/exclusion and
> Git policy is defined by the root `README.md` and `SUBMISSION_MANIFEST.md`,
> not by the paths or commit/gitignore rules below.

**Purpose:** the methodological **Section 2 — Data Cleaning**. Runs after the
initial EDA (A1 + A2) and produces a derived cleaned dataset
(`work_df_batch19_after_data_cleaning_b.xlsx`) that becomes the input for EDA C.

This is the *real* "B" of the data-science methodology. The notebook under
`analysis/eda/notebook_build/a2_predictor_readiness/` (folder renamed from
`eda_b/` to remove exactly this confusion) is **initial EDA (A2)**, not data
cleaning.

**Status:** FINAL CLOSED / VERIFIED / SUBMISSION-READY. Git-closed at commit
`a421037597f6344389be191221843bdcd51ba397`.

**Development history:** `docs/clinical_decisions/manual_decisions_log.md` is
the authoritative chronology of every clinical/methodological decision that
shaped this stage. This README documents the **final architecture**, not how
it was reached.

---

## Workflow position

| Stage | Notebook | Role |
|-------|----------|------|
| A1 (Section 1) | `notebooks/eda/02_eda_a_initial_cohort_overview.ipynb` | Cohort & inventory |
| A2 (Section 1) | `notebooks/eda/02b_eda_a_initial_predictor_readiness.ipynb` | Predictor-readiness EDA |
| **B (Section 2)** | **`notebooks/eda/03_data_cleaning_b_after_initial_eda.ipynb`** | **This — data cleaning** |
| C (Sections 3–5) | `notebooks/eda/04_eda_c_modeling_handoff.ipynb` | Repeated EDA + FE + screening + modeling handoff |

A1 and A2 both read the preprocessing output directly and produce no artifact
that Data Cleaning B consumes. Only EDA C has a real data-flow dependency on
this stage's output.

---

## Current state

| Property | Value |
|---|---|
| Input | `outputs/preprocessing/processed/work_df_batch18.xlsx` (431 × 156) + `variable_classification_minimal.csv` |
| Output | `outputs/data_cleaning/processed/work_df_batch19_after_data_cleaning_b.xlsx` — **431 × 82**, target **370 / 61** |
| Notebook | 51 cells (29 code, 22 markdown); `B_VERIFICATION_PASSED = True` |
| Rows removed by B | **none** (`row_exclusions_applied: false`) |
| Learned/full-cohort fitting in B | **none** — fold-safe learned parameters are fitted downstream in modeling training folds only |

---

## Section architecture

The notebook is assembled by `build_data_cleaning_b_notebook.py` from six
source fragments. `PART_FILES` order is authoritative; fragment filenames do
**not** all match their section numbers.

| Section | Part file | Role |
|---------|-----------|------|
| B0–B1 | `cleaning_b_part1_setup_inputs.py` | Purpose/safety; load inputs; validate target/cohort; define the explicit `CLEANING_SCOPE` |
| B1c | `cleaning_b_part1_setup_inputs.py` | `endo_resection_*` structural not-applicable recode (`NaN → 0` where `endometriosis_surgery == 0`) |
| B2 | `cleaning_b_part3_outlier_handling.py` | Extreme-value / distribution audit — **descriptive and target-blind only**. 1.5× IQR is a descriptive screen; skewness is a descriptive property. B2 never removes a row, sets a value missing, clips, winsorizes, or reads the target. Final per-variable adjudication (all KEEP): `docs/finalization/outlier_extreme_value_handling_closure.md` |
| B2b | `cleaning_b_part3_outlier_handling.py` | Discrete obstetric-count logical validation (non-negativity / integerness only — not a continuous-IQR removal criterion) |
| B3 | `cleaning_b_part3b_transformation_review.py` | Pure continuous transformation review — target-blind, descriptive only. Records an explicit `raw_no_fixed_power_transform` decision (no `log`/`log1p`/`sqrt`/`Box-Cox`/`Yeo-Johnson`) for the 6-variable continuous model-facing pool (`AGE`, `weight_before_pregnancy`, `height`, `BMI_before`, `Hb_before_delivery`, `gestational_age_at_delivery_days`); discrete counts get `not_applicable_discrete_count`. Exports `cleaning_b_final_numeric_transformation_review.csv` |
| B4 | `cleaning_b_part2_missingness_handling.py` | Row/column missingness handling and indicators, computed **within `CLEANING_SCOPE` only** |
| B4b | `cleaning_b_part2_missingness_handling.py` | Row-specific applicability breakdown (structural non-applicability vs. genuine missingness) |
| B4c | `cleaning_b_part2_missingness_handling.py` | Missingness matrix / heatmap + row/column/group summaries (audit output only) |
| B4d | `cleaning_b_part2_missingness_handling.py` | Missingness-mechanism screen (KS / chi-square / Fisher, BH-FDR) + dry-run decision table. Association with an observed variable is evidence against MCAR — it is **not** proof of MAR or MNAR, and not proof that imputation is impossible |
| B5a | `cleaning_b_part4_transformations_imputation_plan.py` | Binary type normalization only (deterministic `Int64` cast) |
| B5b | `cleaning_b_part4_transformations_imputation_plan.py` | `weight_in_pregnancy`, `BMI_after`, PPROM timing: representation/method documented, **not materialized** as `df_clean` columns. `weight_in_pregnancy_cat` / `BMI_after_cat` are documented-representation-only feature-dictionary entries (`materialized_in_B=False`, `cutpoint_source="fold_safe_training_only"`); cutpoints are fitted training-fold-only in modeling (`FoldSafeQuantileCategoryTransformer`). Raw source columns are retained, unimputed, tagged `model_entry_mode=transform_source_only` |
| B5c | `cleaning_b_part4_transformations_imputation_plan.py` | Endometrioma derived variables: `endometrioma_size_status` (`no_endometrioma` / `endometrioma_less_than_30mm` / `endometrioma_30mm_or_more` / `endometrioma_size_unknown`, clinically-sourced 30 mm cutoff, no size imputation) and `endometrioma_presence_laterality` (`none` / `unilateral` / `bilateral` / `laterality_unknown`). Both **0 missing** — genuinely unresolved values are the explicit unknown category, not NaN |
| B5d | `cleaning_b_part4_transformations_imputation_plan.py` | `weight_before_pregnancy` / `height` / `Hb_before_delivery`: NaN **preserved** — no imputation in B; approved median imputation is fitted training-fold-only in modeling (`SimpleImputer`). `BMI_before` is deterministically recomputed in B **only from observed** weight + height; when a modeling fold needs it with an input missing, `FoldSafeRecomputedBMITransformer` fold-safe-medians the inputs and recomputes |
| B5e | `cleaning_b_part4_transformations_imputation_plan.py` | `severe_PET` / `any_PET` → categorical + `not_documented` (`severe_PET_cat` / `any_PET_cat`). `diagnosis_year` is **not** processed here — it is a calendar-time-of-diagnosis field, classified `source_or_text_audit_exclude`, outside `CLEANING_SCOPE` |
| B5f | `cleaning_b_part4_transformations_imputation_plan.py` | Adenomyosis sonographic features: row-applicability-gated (`adenomyosis == 1`) deterministic **12-column multi-hot** representation — `adenomyosis_feature_1`..`adenomyosis_feature_11` (one binary indicator per documented feature code) + `adenomyosis_features_unknown`. No combination categorical; no imputation |
| B5g | `cleaning_b_part4_transformations_imputation_plan.py` | `derived_endo_surgery_adhesion_status` (3 categories). Raw `endo_surgery_adhesiolysis` is dropped from the export (retained upstream in preprocessing only) |
| B5h | `cleaning_b_part4_transformations_imputation_plan.py` | `indication_for_induction_status` (`no_induction` / `induction_indication_unknown` / observed string; 0 missing). Raw `indication_for_induction_clean` is dropped from the export |
| B6 | `cleaning_b_part4_transformations_imputation_plan.py` | Imputation plan for everything not resolved above. Reads B5-created columns by name, so B5c/B5e/B5f precede it. Any learned imputation is deferred to modeling, fitted only within each grouped (`subject_number`) training fold |
| B7 | `cleaning_b_part5_export_cleaned_dataset.py` | Final automated consistency checks (endo_resection, endometrioma, weight/BMI, induction, general binary validity, transformation-review target-blindness) **and** export of the cleaned dataset + audit logs for EDA C. One combined section — there is no separate B8 stage |
| — | `build_data_cleaning_b_notebook.py` | Assembles the notebook — order-authoritative |

### Section B3 does not promote or reclassify anything

**Transformation review does not alter predictor eligibility, timing
classification, model inclusion, or representation-family/co-selection
constraints.** Section B3 (`cleaning_b_part3b_transformation_review.py`) is
target-blind and representation-only: it records a
`raw_no_fixed_power_transform` decision for each reviewed continuous variable
and reads (never writes) `PREDICTOR_ALLOWED_COLS` /
`SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS` / `INTRAPARTUM_PREDICTOR_EXCLUDE_COLS`
only to report each variable's existing `stage_1` / `stage_2` / `stage_3`
eligibility for audit visibility — it never assigns, changes, or overrides any
of those classifications. In particular, `gestational_age_at_delivery_days`
appearing in Section B3's reviewed pool does **not** promote it into a
pre-labor or near-delivery model: its canonical classification remains
`intrapartum_predictor_exclude_from_prelabor_model` (Stage 1: excluded,
Stage 2: excluded, Stage 3 / intrapartum horizon: eligible), set upstream in
`variable_classification_minimal.csv` / `run_preprocessing.py` and unrelated to
Section B3.

---

## Durable methodological invariants

- **Outlier / extreme-value review is descriptive and target-blind.** It
  mutates nothing: no IQR outlier, statistically extreme value, or skewed
  value is ever converted to missing, clipped, winsorized, or capped, and no
  `<col>__missing_ind` is recomputed because of it. See
  `docs/finalization/outlier_extreme_value_handling_closure.md`.
- **Structural non-applicability is not genuine missingness.** A value that
  is not applicable to a row (e.g. endometrioma size when `endometrioma == 0`,
  a sonographic feature when `adenomyosis == 0`) is represented as an explicit
  structural category, never imputed and never counted as missing in a
  denominator.
- **No target-informed feature selection in B.** No variable's
  representation, eligibility, or inclusion is decided by association with
  `target_intrapartum_cs`.
- **No learned / data-dependent preprocessing is fitted on the full cohort.**
  Data Cleaning B performs no KNN, no median fitting, no learned categorical
  cutpoints, no scaling. Where a treatment *method* is approved, B documents
  it; the learned *parameters* are estimated downstream, inside modeling
  training folds only (approved median imputation, `BMI_after` /
  `weight_in_pregnancy` quantile-category cutpoints, PPROM timing split,
  `BMI_before` fold-safe reconstruction).
- **Representation does not imply predictor eligibility.** Creating a
  categorical or derived variable in B is a data-representation act; whether
  it may enter a model, and at which horizon, is a separate upstream
  classification decision.

### What actually happens to each partially-observed variable

Data Cleaning B performs **no learned or statistical imputation of any
variable**. An older draft of this README previously claimed joint KNN for
these variables; that approach was an imputation-leakage risk and is not part
of the pipeline. What happens instead:

- **`weight_before_pregnancy`, `height`, `Hb_before_delivery`:** NaN is
  preserved in Data Cleaning B. No KNN, scaling, or learned imputation is
  fitted in B. The approved downstream treatment is **ordinary median
  imputation, fitted training-fold-only inside modeling** (`SimpleImputer`).
  The method is fixed — the reader-facing contract is complete, not deferred.
- **`BMI_before`:** deterministic formula recompute in B
  (`weight_before_pregnancy / (height/100)^2`) applied **only to rows where
  both inputs are observed**; rows with either input missing keep `BMI_before`
  as NaN in the exported Batch19. When a modeling fold needs `BMI_before` with
  an input missing, `FoldSafeRecomputedBMITransformer` performs a fold-safe
  reconstruction.
- **`endometrioma_size_status`, `endometrioma_presence_laterality`, the
  adenomyosis multi-hot family:** deterministic, source-faithful semantic
  representations — genuinely unresolved values are kept as an explicit
  unknown category, never filled in or guessed.
- **`severe_PET` / `any_PET`:** converted to an explicit categorical
  (`absent` / `present` / `not_documented`) — a labeling decision, not a
  value estimate.
- **`weight_in_pregnancy`, `BMI_after`:** raw columns retained with original
  NaNs, **no standalone missingness indicator** — the fold-safe
  `weight_in_pregnancy_cat` / `BMI_after_cat` categoricals' own
  `not_documented` bucket carries that information, fitted training-fold-only
  at modeling time.

Any future learned/data-dependent imputation belongs downstream in modeling,
fitted only within training folds. This is not a precedent for adding more
rules here; any extension requires its own documented decision.

### High-missingness policy

`≥ 70%` ordinary (non-structural) missingness is **flag/document for audit
only** — the source variable is **retained** in the cleaned analytical
export and is never automatically removed for crossing this threshold, and no
missingness indicator, `not_documented` category, categorical replacement, or
other derived predictor is automatically created for it. Any representation
decision for a high-missingness variable is made downstream (EDA C /
modeling).

---

## Control flags (defaults)

| Flag | Default | Effect |
|------|---------|--------|
| `APPLY_ROW_EXCLUSIONS` | `False` | Retired/inert — row-exclusion capability has been removed entirely; rows > 50% missing in scope are always flagged only, regardless of this flag's value |
| `EXECUTE_LEARNED_IMPUTATION` | `False` | Retired/inert — no code path reads this flag; kept only for backward-compatible manifest schema. Data Cleaning B performs no learned imputation of any kind |
| `EXPORT_FOR_EDA_C` | `True` | Writes the cleaned B dataset and audit contract required by EDA C |

---

## Inputs

- `outputs/preprocessing/processed/work_df_batch18.xlsx` (read-only source)
- `variable_classification_minimal.csv` (single source of truth for classification)

## Outputs (when `EXPORT_FOR_EDA_C = True`)

- `outputs/data_cleaning/processed/work_df_batch19_after_data_cleaning_b.xlsx` — **patient-level, gitignored**
- `outputs/data_cleaning/audit/`:
  - `cleaning_b_manifest.json`
  - `cleaning_b_column_actions.csv`
  - `cleaning_b_missingness_handling.csv`
  - `cleaning_b_outlier_handling.csv` — per-variable B2 descriptive screen (target-blind; every `final_decision` is a `keep_*`)
  - `outlier_extreme_value_final_adjudication.csv` — compact final target-blind extreme-value adjudication table; human-readable record: `docs/finalization/outlier_extreme_value_handling_closure.md`
  - `cleaning_b_final_numeric_transformation_review.csv` — Section B3's target-blind continuous-transformation-review audit
  - `cleaning_b_imputation_plan.csv`
  - `cleaning_b_feature_dictionary.csv` — **contract consumed by EDA C controlled validation**
  - `cleaning_b_variable_classification_snapshot.csv` / `cleaning_b_variable_type_schema_snapshot.csv` — authoritative classification/type inputs for EDA C
  - `cleaning_b_row_actions_patient_level.csv` — **patient-level, gitignored**
  - `cleaning_b_output_delivery_id_key.csv` — **patient-level (id-only), gitignored** — the canonical downstream row-order sidecar, written in the exact same row order as the cleaned Batch19 file

## Hard safety guarantees

- Never overwrites `work_df_batch18.xlsx`.
- Refuses to write anywhere inside `outputs/preprocessing/` or `analysis/preprocessing/`.
- `df` is never modified; cleaning is applied to a copy `df_clean`.
- No learned or statistical imputation runs in B at all.
- No variable's formula/representation logic ever reads `target_intrapartum_cs`
  or any leakage / post-delivery / intrapartum-outcome variable.
- No patient-level identifier (`subject_number`, `delivery_id`) is ever printed
  in notebook output.

## Feature dictionary = contract for EDA C

Every B-created column is documented in `cleaning_b_feature_dictionary.csv`
with `new_column, source_column, creation_rule, timing, leakage_status,
intended_use`. EDA C admits a B-created column through validation only if it
appears here; any undocumented cleaned-dataset column makes EDA C error.

## Commit policy

Commit `.py` and `.md` files only. Never commit `.ipynb`, `.xlsx`, `.csv`,
`.json` outputs, or any patient-level file. `outputs/data_cleaning/` is
gitignored.

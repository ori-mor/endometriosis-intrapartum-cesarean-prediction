# FIGURE_TABLE_INDEX — index of this submission's `results/`

This is the index of what is **actually included in this curated submission
package**, organized by the four result groups under `results/`. All paths
below are relative to the submission's `results/` directory. For the full canonical-repository
figure/table index (including the historical Stage 3/LASSO Tables A–I /
Figures 1–10 layer, not included in this package), see
`documentation/reference/FIGURE_TABLE_INDEX_CANONICAL.md`.

Every table/figure below is aggregate-only (cohort-level statistics,
variable-level metadata, or model-level results) — no patient-level row
appears in any of them. See the root `README.md` for this submission's
reproducibility tiers.

## 1. `compact_ridge_final/` — the current, locked final model (Decision 99)

Generated (in the canonical repository) by
`analysis/reports/compact_ridge_final_outputs.py`, reading only the locked
Compact Ridge validation/refit artifacts. Notebook 5
(`notebooks/05_final_compact_ridge_model.ipynb`) surfaces this same content
and is genuinely rerunnable from these files — see item 2 below and the root
`README.md`.

| Path | Contents |
|---|---|
| `tables/compact_ridge_final/table_final_model_performance.{csv,md}` | Compact Ridge vs. historical Stage 3/LASSO baseline (PR-AUC, AUROC, Brier, calibration) |
| `tables/compact_ridge_final/table_final_ridge_coefficients.{csv,md}` | Full-data-refit Ridge coefficients (standardized/encoded scale) + outer-fold stability — **not** adjusted odds ratios |
| `tables/compact_ridge_final/adjusted_or/table_adjusted_odds_ratios.{csv,md}` | Secondary descriptive adjusted-OR analysis (primary MLE, all 6 predictors) |
| `tables/compact_ridge_final/adjusted_or/table_adjusted_odds_ratios_firth_sensitivity.{csv,md}` | Firth sensitivity table (subordinate to the MLE table; sparse-cell robustness check) |
| `tables/compact_ridge_final/README.md` | Full generating-method documentation for this model's tables |
| `tables/compact_ridge_final/adjusted_or/README.md` | Full generating-method documentation for the adjusted-OR analysis |
| `figures/compact_ridge_final/figure_compact_ridge_roc.{png,svg}` | ROC curve |
| `figures/compact_ridge_final/figure_compact_ridge_precision_recall.{png,svg}` | Precision-recall curve |
| `figures/compact_ridge_final/figure_compact_ridge_calibration.{png,svg}` | Reliability (calibration) diagram |
| `figures/compact_ridge_final/adjusted_or/figure_adjusted_odds_ratios.{png,svg}` | Adjusted-OR forest plot (primary MLE only) |
| `figures/compact_ridge_final/figures_metadata.md` | Exact aggregation method behind each figure |

## 2. `reproducibility/` — repeat/fold-level detail behind the model tables

Aggregate cross-validation manifests and per-fold/per-repeat metrics that
`table_final_model_performance.md` and the coefficient table summarize.
Deliberately **excludes** any out-of-fold prediction file
(`locked_validation_oof_predictions.csv` is a row-level artifact and is not
part of this submission — see the root `README.md`).

| Path | Contents |
|---|---|
| `tables/reproducibility/locked_validation_manifest.json` | Locked internal-validation run manifest (repeat-level summary, both current and historical architectures) |
| `tables/reproducibility/final_refit_manifest.json` | Full-431-row final refit manifest (chosen C, intercept, convergence, provenance hashes) |
| `tables/reproducibility/repeat_level_metrics.csv` | Per-repeat (10) performance metrics |
| `tables/reproducibility/fold_level_metrics.csv` | Per-outer-fold (50) status |
| `tables/reproducibility/coefficient_stability.csv` | Sign consistency / coefficient spread per predictor across the 50 outer folds |
| `tables/reproducibility/coefficients_encoded.csv`, `coefficients_source_level.csv` | Full-refit coefficients, encoded and source-variable level |
| `tables/reproducibility/frozen_set_contract.csv` | The frozen 6-predictor contract |
| `tables/reproducibility/preprocessing_spec.json` | Fold-safe preprocessing contract (imputation/encoding rules) used by the final refit |

## 3. `publication_analysis/` — descriptive/univariable statistical analysis

Table 1/Table 2, FDR-corrected univariable associations, endometriosis-
specific findings, and forest/functional-form diagnostic figures. Produced
by the publication-analysis pipeline (`src/publication_analysis/`), shown
executed in `notebooks/06_publication_statistical_analysis.ipynb`.

| Path | Contents |
|---|---|
| `tables/publication_analysis/table_1_full_descriptive.{csv,xlsx}`, `table_1_compact_descriptive.{csv,xlsx}` | Table 1 — cohort descriptive statistics (full and compact) |
| `tables/publication_analysis/table_2_compact_final_predictors_univariable.{csv,xlsx}` | Table 2 — univariable associations for the final predictor set |
| `tables/publication_analysis/appendix_table_a2_full_univariable.{csv,md,xlsx}` | Appendix — full univariable association table |
| `tables/publication_analysis/univariable_master.csv`, `univariable_predictor_level_tests.csv`, `predictor_level_hypothesis_fdr.csv` | Univariable test statistics and FDR correction detail |
| `tables/publication_analysis/endometriosis_findings.csv`, `adjusted_endometriosis_analysis.csv`, `adjusted_primary_vs_sensitivity.csv` | Endometriosis-specific association findings (crude, adjusted, sensitivity) |
| `tables/publication_analysis/research_signal_evidence.csv` | Consolidated research-signal summary |
| `tables/publication_analysis/missingness_support_audit.csv` | Variable-level missingness/support audit for the analyses above |
| `tables/publication_analysis/publication_representation_contract.csv`, `representation_signoff_review.csv` | Display-representation contract and sign-off review (formatting/labeling rules, not analytical results) |
| `tables/publication_analysis/diagnostics/functional_form_review.csv`, `functional_form_count_level_predictions.csv`, `functional_form_count_value_support.csv` | Functional-form diagnostic detail behind the figures below |
| `figures/publication_analysis/forest_endometriosis_crude.png`, `forest_endometriosis_adjusted.png` | Endometriosis crude/adjusted forest plots |
| `figures/publication_analysis/forest_univariable_group_*.png` | Univariable forest plots by predictor group (groups 4 and 9 are not shown — see the generating script's grouping logic for why) |
| `figures/publication_analysis/functional_form/functional_form_*.png` | Functional-form diagnostics for 6 continuous predictors |

## 4. `modeling_handoff/` and `data_cleaning_b_audit/` — current supporting variable-level artifacts

Added to this submission beyond what appeared in the original project book,
because they are current, aggregate/variable-level only, and privacy-safe
(see `SUBMISSION_MANIFEST.md`'s "Major deliberate exclusions, and why" and
"Supporting modeling-handoff / data-cleaning result locations" sections).
Source: the canonical
repository's EDA C candidate-pool handoff and Data Cleaning B audit layer,
current as of the same commit this package is curated from. Every file here
is one row per **variable** (or variable pair), never one row per patient —
verified by content, not by filename, before inclusion.

| Path | Contents |
|---|---|
| `tables/modeling_handoff/candidate_feature_manifest.json` | EDA C run manifest — screening counts, stage-eligibility pools, validation-check results (personal filesystem paths present in the canonical source were redacted for this copy; see the file's own `_submission_redaction_note`) |
| `tables/modeling_handoff/candidate_feature_review_full.csv` | Full per-variable screening review (85 variables) |
| `tables/modeling_handoff/candidate_model_features.csv` | Model-facing candidate registry (81 variables) |
| `tables/modeling_handoff/excluded_features_log.csv` | Hard-excluded variables and reasons (4 variables) |
| `tables/modeling_handoff/model_coentry_constraints.csv` | Hard co-entry variable-pair constraints (8 pairs) |
| `tables/modeling_handoff/model_relationship_groups.csv` | Review-only relationship groupings (65 rows, 13 relationship groups) |
| `tables/modeling_handoff/predictor_relationship_diagnostics.csv` | Pairwise predictor relationship diagnostics (75 pairs) |
| `tables/modeling_handoff/feature_dictionary.csv` | Derived/engineered feature definitions (5 features) |
| `tables/modeling_handoff/variable_classification_snapshot.csv`, `variable_type_schema_snapshot.csv` | Variable-level classification and type schema snapshots (178 variables each) |
| `figures/modeling_handoff/domain_*_distributions.png` | Aggregate per-domain distribution figures (12 clinical domains) |
| `tables/data_cleaning_b_audit/cleaning_b_column_actions.csv` | Per-column cleaning action log (157 columns) |
| `tables/data_cleaning_b_audit/cleaning_b_feature_dictionary.csv` | Data Cleaning B feature dictionary (25 features) |
| `tables/data_cleaning_b_audit/cleaning_b_imputation_plan.csv` | Variable-level imputation plan (87 variables) |
| `tables/data_cleaning_b_audit/cleaning_b_missingness_handling.csv` | Variable-level missingness-handling plan (71 variables) |
| `tables/data_cleaning_b_audit/cleaning_b_outlier_handling.csv` | Variable-level outlier-handling plan (14 variables) |
| `tables/data_cleaning_b_audit/cleaning_b_final_numeric_transformation_review.csv` | Numeric transformation review (11 variables) |
| `tables/data_cleaning_b_audit/outlier_extreme_value_final_adjudication.csv` | Per-variable extreme-value adjudication (aggregate ranges/counts only, 14 variables) |
| `tables/data_cleaning_b_audit/cleaning_b_variable_classification_snapshot.csv`, `cleaning_b_variable_type_schema_snapshot.csv` | Data Cleaning B classification/type snapshots (174 variables each) |
| `tables/data_cleaning_b_audit/cleaning_b_manifest.json` | Data Cleaning B run manifest (row/column counts, feature-family decisions) |

**Explicitly excluded** from these two folders (patient-level, never
copied): the EDA C modeling-dataset `.xlsx` matrices, the EDA C row/
delivery-id key sidecar, the Data Cleaning B output delivery-id key
sidecar, and the Data Cleaning B row-actions "patient-level" file.

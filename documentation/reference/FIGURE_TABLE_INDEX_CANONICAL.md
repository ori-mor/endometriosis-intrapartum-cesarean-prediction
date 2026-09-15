# FIGURE_TABLE_INDEX — every final submission figure and table

> **HISTORICAL / CANONICAL-REFERENCE.** This is the full canonical-repository
> figure/table index, retained here for provenance and historical context
> only. It is **not** an index of this curated submission package — most
> artifacts it lists (the Stage 3/LASSO Tables A–I / Figures 1–10 layer, and
> canonical `outputs/...` paths) are deliberately not included in this
> submission. **For the actual index of what is included in this submission,
> see `documentation/FIGURE_TABLE_INDEX.md`.**
>
> **Provenance note (submission package):** copied verbatim, without
> scientific content changes, from the canonical research repository at
> commit `e7676be3167c706950ce1a564fc454223f0d265d` (tag `final-project-2026`).
> Internal repository paths mentioned below refer to that canonical
> repository, not this submission package.


**Not a prose chapter.** For each artifact: exact path, purpose, the canonical
underlying run artifact, the major value(s) it represents, and readiness.

## Current — Compact Ridge (Decision 99) manuscript-facing artifacts

**Point current manuscript-facing model tables/figures here**, not at the
historical Tables A–I / Figures 1–10 below (those remain the historical
Stage 3 / LASSO Final-D package — kept, and still appropriate as internal/
supplementary/robustness material, but not the current model's own results).

| Path (`outputs/results/compact_ridge_final/…`) | Purpose | Readiness |
|---|---|---|
| `tables/table_final_model_performance.md` | Compact Ridge vs. historical Stage 3/LASSO, side by side (PR-AUC 0.348 vs. 0.272, AUROC 0.798 vs. 0.715, Brier, Brier skill, log-loss, calibration) | READY |
| `tables/table_final_ridge_coefficients.md` | Final full-data-refit coefficients (encoded/standardized scale) — explicitly **not** adjusted odds ratios | READY |
| `figures/figure_compact_ridge_roc.{png,svg}` | Compact Ridge ROC curve | READY |
| `figures/figure_compact_ridge_precision_recall.{png,svg}` | Compact Ridge precision-recall curve | READY |
| `figures/figure_compact_ridge_calibration.{png,svg}` | Compact Ridge reliability diagram | READY |
| `adjusted_or/table_adjusted_odds_ratios.md` + `figure_adjusted_odds_ratios.{png,svg}` | Secondary six-predictor adjusted-OR forest plot/table (primary MLE) | READY |
| `adjusted_or/table_adjusted_odds_ratios_firth_sensitivity.md` | Firth sensitivity table (subordinate to the MLE table above, never substituted into the primary forest plot) | READY |

Canonical source for every value above: `docs/finalization/COMPACT_RIDGE_FINAL_LOCK.md`
§6–§7. Directory map: `outputs/results/README.md`.

## HISTORICAL — Stage 3 / LASSO Final-D submission package (superseded architecture)

Everything below (Tables A–I, Figures 1–10) describes the **historical**
Final-D run and remains an accurate historical record, still useful as the
robustness/sensitivity/predictor-stability supplement — but it is not the
current model's own results (see the current section above).

Readiness legend: **READY** = final, submission-quality, reconciled ·
**PARTIAL** = exists but not yet finalized · **HISTORICAL** = superseded, kept
for provenance.

Generators (read-only consumers of the frozen run — no fitting, no CV, no
threshold, no holdout):
`analysis/modeling/final_modeling/results/results_data.py` (data) and
`results_figures.py` (figures); notebook builder
`analysis/modeling/notebook_build/results/build_results_notebook.py`.
Consistency test: `analysis/modeling/final_modeling/tests/test_results_data.py`.

All paths below are under `outputs/results/final_submission/`. Tables are
committed as `.md` (the `.csv` twins are gitignored); figures are committed as
`.png` + `.svg`.

**2026-09-03 revision (Decision 98):** Tables C/D and Figures 6/7 were
regenerated to carry **two independent rarity dimensions** — `rarity_class`
(target-independent unique-carrier-subject band: SINGLE_CASE 1 / EXTREME_RARITY
2–4 / VERY_RARE 5–9 / RARE 10–19 / NOT_RARE ≥ 20) and `target_cell_flag`
(target-dependent carrier × outcome cell sparsity/separation) — plus a
corrected `stability_interpretation` (selection frequency alone no longer
implies robustness at low support). The two dimensions are never combined into
one threshold. Table I was added for the post-hoc extreme-rarity robustness
sensitivity. No canonical primary performance number changed; Figures 1–5 and
8–10 are unchanged. See
`docs/finalization/EXTREME_RARITY_SENSITIVITY_SUMMARY.md` and
`docs/finalization/FINAL_MODELING_DECISIONS.md`.

---

## Tables

| ID | Path (`tables/…`) | Purpose | Underlying artifact | Major values | Readiness |
|---|---|---|---|---|---|
| **A** | `table_a_all_9_pathways.md` | Compare all 9 prespecified pathways | `selection/pathway_comparison.csv`, `post_run_bootstrap/primary_pathway_bootstrap.csv` | 9 rows; winner = Stage 3 / lasso_logistic, mean PR-AUC 0.272 [0.212, 0.352]; all-9 PR-AUC range 0.222–0.272 | READY |
| **B** | `table_b_winner_repeat_level.md` | Winner performance per outer repeat (10) + summary | `selection/pathway_repeat_metrics.csv` | mean PR-AUC 0.2720 (sd 0.0176, se 0.0056); mean AUROC 0.7150; mean Brier 0.1270 | READY |
| **C** | `table_c_winner_predictor_stability.md` | Source-predictor selection frequency across 50 winner outer models, **+ two separate rarity columns (`rarity_class` = SINGLE_CASE 1 / EXTREME_RARITY 2–4 / VERY_RARE 5–9 / RARE 10–19 / NOT_RARE ≥20; `target_cell_flag` = complete_separation / sparse_target_cell / ok) + corrected `stability_interpretation`** (revised 2026-09-03) | `fold_results/source_predictor_activity.csv` + `sensitivity/stage3_extreme_rarity_unique_subject_support.csv` | stable core AGE/nulliparity/indication_for_induction_status/height (≥96%); adenomyosis_feature_7/_11 (78/76%) = SINGLE_CASE + complete separation → `single_case_driven_exploratory` | READY |
| **D** | `table_d_endometriosis_predictor_stability.md` | Endometriosis-family predictor stability + `rarity_class` + `target_cell_flag` + **corrected `stability_interpretation`** (revised 2026-09-03 — replaced the frequency-only `highly_stable`/`moderately_stable` tier) | `fold_results/source_predictor_activity.csv`, `coefficients/transformed_feature_coefficients.csv`, extreme-rarity support | cs_scar_endometriosis 98%, RARE (12 subjects) → `consistently_selected_with_limited_support`; feature_7/_11 = SINGLE_CASE (1 subject each) → single-case-driven exploratory; feature_4 = NOT_RARE by subjects but sparse target cell → `sparse_target_cell_exploratory`; no endometriosis predictor is `highly_stable` | READY |
| **I** | `table_i_extreme_rarity_sensitivity.md` | **POST-HOC ROBUSTNESS SENSITIVITY** — Stage-3/LASSO OOF with 10 ≤ 4-unique-subject predictors removed (81→71) vs canonical primary, paired subject-aware bootstrap (2000/2000) | `sensitivity/stage3_extreme_rarity_{summary.json,paired_bootstrap.csv}` | paired Δ PR-AUC +0.016 [−0.007, +0.043] (crosses 0); AUROC +0.002 [−0.017, +0.023]; Brier +0.044 [+0.030, +0.058]; calibration intercept −0.80 [−1.06, −0.55]. Discrimination robust; calibration/tuning sensitive. NOT a primary model. | READY |
| **E** | `table_e_constrained_vs_unconstrained.md` | Constrained winner vs matched unconstrained benchmark (paired) | `predictions/matched_unconstrained_outer_oof_predictions.csv`, `post_run_bootstrap/matched_benchmark_paired_bootstrap.csv` | paired PR-AUC delta −0.0017, 95% CI [−0.0048, 0.0015] (crosses zero) | READY |
| **F** | `table_f_stage3a_vs_stage3b.md` | Stage 3A (with gestational age) vs 3B (without), paired | `sensitivity/stage3_gestational_age_paired_fold_metrics.csv`, `post_run_bootstrap/stage3_paired_bootstrap_reconstructed.csv` | gestational_age active 46% of Stage-3B; all primary paired-delta CIs cross zero except calibration intercept | READY |
| **G** | `table_g_calibration_summary.md` | Winner calibration + Brier-vs-null | `post_run_bootstrap/winner_calibration_bootstrap.csv` | intercept −0.6807 [−1.1217, −0.2681]; slope 0.6713 [0.4847, 0.8743]; null Brier 0.1215, winner worse than null | READY |
| **H** | `table_h_run_integrity_summary.md` | Run integrity / provenance one-pager | `run_manifest.json` | COMPLETE; 450/450; 50/50; 50/50; bootstrap B_valid 2000; refit NOT_RUN; threshold BLOCKED; holdout NOT_ACCESSED | READY |

## Figures

| ID | Path (`figures/…`, `.png` + `.svg`) | Purpose | Underlying artifact | Major values | Readiness |
|---|---|---|---|---|---|
| **1** | `figure1_all9_pathways_pr_auc` | All 9 pathways — PR-AUC with bootstrap CIs | `selection/pathway_comparison.csv` + primary pathway bootstrap | winner clears its own one-SE band; all CIs overlap | READY |
| **2** | `figure2_winner_pr_curve` | Winner precision-recall curve | `predictions/primary_outer_oof_predictions.csv` (Stage 3 / lasso) | PR-AUC 0.272 vs no-skill 0.1415 | READY |
| **3** | `figure3_winner_roc_curve` | Winner ROC curve | same OOF | AUROC 0.715 | READY |
| **4** | `figure4_winner_calibration` | Winner reliability diagram | winner OOF probabilities | slope 0.67, intercept −0.68; overconfident | READY |
| **5** | `figure5_predicted_risk_distribution` | Predicted risk by observed outcome | winner OOF | partial separation of the two outcome groups | READY |
| **6** | `figure6_predictor_stability` | Winner source-predictor selection frequency (≥ 25% shown); **colour = unique-carrier-subject band (SINGLE_CASE / EXTREME_RARITY / VERY_RARE / RARE / NOT_RARE); hatch = target-dependent carrier×outcome cell empty/sparse — two SEPARATE dimensions** (revised 2026-09-03) | `fold_results/source_predictor_activity.csv` + extreme-rarity support | obstetric core dark-blue; adenomyosis_feature_7/_11 dark-red + `xx` (single case + complete separation); placental_abruption amber (extreme rarity) | READY (revised) |
| **7** | `figure7_endometriosis_predictor_stability` | Endometriosis-specific predictor stability; **colour = unique-carrier-subject band, hatch = sparse/empty outcome cell — two separate dimensions** (revised 2026-09-03) | same | cs_scar_endometriosis = RARE (mid-blue); feature_7/_11 = SINGLE_CASE (dark-red + `xx`); feature_4 = NOT_RARE colour but `//` hatch (sparse cell); no highly-stable bar | READY (revised) |
| **8** | `figure8_hyperparameter_stability` | Selected `C` and `class_weight` distribution across 50 folds | `predictions/primary_outer_oof_predictions.csv` (selected hyperparams) | dominant C = 0.1274 in 25/50; class_weight none in 41/50 | READY |
| **9** | `figure9_constrained_vs_unconstrained` | Paired constrained vs unconstrained by metric | matched benchmark paired bootstrap | PR-AUC delta CI crosses zero | READY |
| **10** | `figure10_stage3ab_sensitivity` | Stage 3A vs 3B paired deltas by metric | `sensitivity/` + reconstructed paired bootstrap | all primary deltas' CIs cross zero except calibration intercept | READY |

## Table 1 / Table 2 — cohort characteristics and univariable associations

- **Status: READY.** Not part of the Final-D artifact layer
  (`RESULT_ARTIFACT_SCHEMA.md` "Out of scope") — produced by the separate
  publication-analysis pipeline.
- Generator: `analysis/publication_analysis/notebook_parts/part3_table1.py`
  (Table 1: full + compact descriptive) and `part4_univariable_and_fdr.py`
  (Table 2: compact final-predictor univariable associations), assembled by
  `analysis/publication_analysis/build_publication_notebook.py`.
- Notebook: `notebooks/publication/01_publication_statistical_analysis.ipynb`
  (gitignored; executed, 0 errors).
- Output: `outputs/publication_analysis/tables/table_1_full_descriptive.{csv,xlsx}`,
  `table_1_compact_descriptive.{csv,xlsx}`,
  `table_2_compact_final_predictors_univariable.{csv,xlsx}` (gitignored,
  local-only).

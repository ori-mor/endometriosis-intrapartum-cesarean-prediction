# METHODS_FACTS — exact final methods facts for the project book

> **Provenance note (submission package):** copied verbatim, without
> scientific content changes, from the canonical research repository at
> commit `e7676be3167c706950ce1a564fc454223f0d265d` (tag `final-project-2026`).
> Internal repository paths mentioned below refer to that canonical
> repository, not this submission package.


**Not a prose chapter.** A fact reference. Most of this document (from
"## Predictors and stages" onward) is from the completed, now-**historical**
Final-D scientific run and its locked methodology contract
(`analysis/modeling/final_modeling/RESULT_ARTIFACT_SCHEMA.md`,
`run_manifest.json`). Re-verify regenerable hashes / counts against the live
manifest before quoting.

## Current final architecture (Decision 99, 2026-09-04) — methods

**Compact Ridge (L2-penalized) logistic regression** supersedes Stage 3 /
LASSO as the final predictive-model architecture. Source of truth:
`docs/finalization/COMPACT_RIDGE_FINAL_LOCK.md`.

- **Six source predictors:** `AGE`, `nulliparity`, `S_P_CS`, `BMI_before`,
  `derived_hypertension_pih_pet_spectrum`, `induction_any_bin`. No
  endometriosis-specific predictor forced in (see the "Endometriosis" facts
  below). No predictor-selection step — all 6 are always retained (Ridge
  never zeros a coefficient exactly).
- **Estimator:** L2-penalized (Ridge) logistic regression, 15-point
  `logspace(-2, 1.5)` C grid, selection rule = PR-AUC one-SE band → lowest
  inner Brier → smallest C.
- **Validation:** repeated **subject-grouped nested cross-validation** —
  outer **10 repeats × 5 folds = 50 outer models**; inner **grouped 5-fold**,
  training-fold only. Identical cohort, target, and subject-grouping
  definition as the historical run below (§Cohort, §Grouping unchanged).
  50/50 outer folds converged, 0 failures.
- **Fold-safe preprocessing:** median imputation (numeric) / most-frequent
  imputation (categorical) + standardization, fit training-fold-only in the
  locked-validation run and full-cohort for the one-time final refit;
  full-dummy one-hot for `derived_hypertension_pih_pet_spectrum`.
  `BMI_before` is **not** itself imputed — it is fold-safe-recomputed from
  its `height` + `weight_before_pregnancy` source components via
  `FoldSafeRecomputedBMITransformer` (component medians fitted
  training-fold-only in Ridge's nested CV, full-cohort for the final refit),
  never median-imputed directly as a standalone column.
- **Division of responsibility on missing data:** **Data Cleaning B** is the
  canonical decision-making stage — it defines the treatment policy
  (structural non-applicability vs. genuine missingness vs.
  not-documented, and the component-level BMI reconstruction strategy) and
  performs no learned/data-dependent imputation on the full cohort.
  **Modeling** implements the data-derived parameters (medians, the BMI
  component recompute) fold-safely inside training folds. **EDA C** does not
  independently choose the missing-data strategy — it consumes Data Cleaning
  B's classification/type-schema snapshot as its authority.
- **Validation scope:** **internal** repeated subject-grouped nested CV,
  performed **after** exploratory model development on the same dataset
  (`exploratory/overnight-model-improvement`). **No external validation**
  exists for this architecture, same as the historical run.
- **Historical baseline:** Stage 3 / LASSO logistic (below) is retained as
  the historical baseline architecture — everything from "## Predictors and
  stages" through "## Post-hoc extreme-rarity robustness sensitivity" below
  describes that historical run's own methodology and does not describe
  Compact Ridge.

---

## Cohort

- **431 deliveries** after all upstream filtering: exclusion of elective /
  pre-labor cesarean, exclusion of non-trial-of-labor rows, and
  clinically-approved eligibility corrections (Decisions 32, 67; see
  `docs/clinical_decisions/manual_decisions_log.md`).
- The dataset was **already restricted to singleton pregnancies upstream by
  Sheba Medical Center** before delivery to the student team. No reliable
  singleton variable exists in the analytical workbook, so the pipeline does
  not (and cannot) re-apply a singleton filter.
- Cohort filtering is done in **preprocessing**, not by the model.

## Target

- `target_intrapartum_cs` — binary: `0` = vaginal delivery, `1` = intrapartum
  cesarean section.
- Distribution: **370 vaginal / 61 intrapartum CS**; prevalence **0.1415**.

## HISTORICAL — Stage 3 / LASSO Final-D run methodology (superseded architecture, see Decision 99 above)

`## Cohort` and `## Target` above are shared facts that still apply to the
current Compact Ridge architecture unchanged. Everything from here through
"## Post-hoc extreme-rarity robustness sensitivity" describes the
**historical, superseded** Stage 3 / LASSO Final-D run's own predictor pool,
model-family search, and winner-selection methodology only.

## Predictors and stages

- Predictor eligibility and the model-facing pool come from **EDA C**
  (`outputs/eda_c/candidate_feature_manifest.json`): 85 screened, 4
  hard-excluded (all zero-variance: `alcohol`, `HELLP`, `eclampsia`, `IUFD`),
  **81 eligible**.
- Three **strictly nested cumulative stages** by prediction horizon
  (`run_manifest.json` `stage_pool_counts`):
  - **Stage 1 — pre-labor: 70 predictors** (`predictor_allowed`).
  - **Stage 2 — + near-delivery: 76** (+6 `secondary_near_delivery_predictor`).
  - **Stage 3 — + intrapartum horizon: 81** (+5
    `intrapartum_predictor_exclude_from_prelabor_model`); equals the full
    eligible pool.
- 8 deterministic, target-independent **hard co-entry pairs** (never co-enter
  any model, LASSO/EN included), resolved pre-fit in the training fold.
- 13 review-only relationship groups (never affect eligibility).
- No post-delivery / neonatal / maternal-outcome / CS-indication variable is
  ever a predictor (leakage list in `CLAUDE.md`).

## Model families (9 pathways = 3 stages × 3 families)

- **Top-N logistic** — unpenalized logistic regression (`C = np.inf`), fixed
  number of predictors selected by training-fold ranking, drop-one reference
  categorical coding.
- **LASSO logistic** — L1-penalized.
- **Elastic-Net logistic** — L1 + L2.
- All 9 pathways are **endometriosis-constrained**: every fitted model must
  retain ≥ 1 active endometriosis-specific source predictor (enforced pre-fit).

## Nested cross-validation

- **Repeated nested CV.** Outer: **5 folds × 10 repeats** = 50 outer models
  per pathway. Inner: **5 folds**, training-fold only, for candidate /
  hyperparameter / predictor selection.
- **Primary metric: PR-AUC** (area under the precision-recall curve), chosen
  for the ~14% event prevalence.
- Also computed OOF: AUROC, Brier score, calibration intercept + slope.
- **450 primary outer units** (9 × 5 × 10); **38,790 primary OOF prediction
  rows** (9 × 10 × 431).
- Seeds and configuration are fingerprinted in `run_manifest.json`
  (`search_config_fingerprint`, `resume_gating_fingerprints`); a resume fails
  loud on any fingerprint or input-hash mismatch.
- `completion_status = COMPLETE` is **validated** by
  `assert_overall_run_complete()` (every intended fold key present + every
  serialized-model checksum matches), never caller-declared.

## Grouping

- **Subject-grouped** everywhere (`subject_groups.load_group_labels`).
  Grouping unit = subject; a missing `subject_number` gets its own unique
  singleton group. 430 groups over 431 rows.
- The same subject never appears in both training and validation of any fold
  (inner or outer), and bootstrap resampling is over subjects, never rows.

## Preprocessing inside CV

- All learned preprocessing is **fit on the training fold only**: median
  imputation; `BMI_after` / `weight_in_pregnancy` quantile-category cutpoints;
  PPROM timing split; `BMI_before` deterministic recomputation from observed
  weight + height; one-hot / ordinal encoding.
- **Nothing is fit on the full cohort.** Data Cleaning B performs no learned
  imputation and removes no analytical row.

## Winner-selection rule

- Pre-specified, locked (`canonical_across_pathway_rule_v1`), computed on the
  **primary outer OOF only**:
  1. one pooled PR-AUC per `stage × family × repeat`;
  2. one-SE band: `best_mean − SD/√R`;
  3. deterministic parsimony tie-break (fewer active source predictors →
     earlier stage → lower Brier → lower calibration deviation → higher AUROC
     → family order).
- A real `--scale full` run refuses an injected winner; the decision is
  recomputed and checksum-verified on resume.

## Bootstrap method

- **Post-run, read-only.** `post_run_bootstrap.py` consumes the persisted OOF
  predictions; it never reruns CV, refits, reselects a winner, or computes a
  threshold. It refuses to run unless the source run is `COMPLETE` and its
  fingerprints still match.
- **Subject-level resampling**, `B = 2000` valid replicates, dedicated seed
  `20260901`, deterministic safety cap. Invalid (single-class) replicates
  discarded, never imputed. Per-replicate: each repeat's pooled metric first,
  then averaged across repeats. Percentile 2.5 / 97.5 CIs.
- Stage-3A/3B paired bootstrap uses a **prediction-only reconstruction** of
  row-level OOF predictions (already-fitted preprocessor + estimator, `.transform`
  / `.predict_proba` only), reconciled to ≤ 1e-8 against the canonical
  fold-level metrics before bootstrapping (`reconciliation_status = PASS`).

## Matched unconstrained benchmark

- One matched benchmark for the winning stage/family (Stage 3 / LASSO), same
  50 outer folds, **without** the endometriosis constraint. 50/50 COMPLETE.
- Paired constrained-vs-unconstrained bootstrap uses the identical sampled
  subject multiset for both arms.

## Stage 3 sensitivity (gestational age)

- Stage 3A (with `gestational_age_at_delivery_days`) vs Stage 3B (without),
  paired by `family × repeat × outer_fold`. 50/50 pairs COMPLETE. A
  transparency safeguard (Decision 79 addendum), not an eligibility gate.

## Post-hoc extreme-rarity robustness sensitivity (Decision 98, 2026-09-03)

- **Type:** POST-HOC, TARGET-INDEPENDENT EXTREME-RARITY ROBUSTNESS ANALYSIS.
  Not a primary pathway, not a winner reselection, not a methodology change.
- **Why:** the pipeline deliberately treats **target-dependent**
  sparsity/separation as a disclosed soft warning (never a hard global
  exclusion) to avoid target-informed eligibility decisions outside training
  folds. A later audit found that **target-independent** subject-level rarity
  was a separate, unassessed issue: high outer-model selection frequency was
  discovered to be misleading for predictors supported by very few unique
  subjects — `adenomyosis_feature_7` / `_11` (78% / 76% selection) are each
  carried by **one** unique subject and sit in ~40/50 outer training folds by
  construction.
- **Rule:** remove every Stage-3 source predictor with **≤ 4 unique carrier
  subjects** (target-independent, re-verified live from cohort + subject
  grouping). 10 predictors: `adenomyosis_feature_6/7/8/9/11`, `SIPET`,
  `endo_resection_epiploica`, `endo_resection_appendix`, `VBAC`,
  `placental_abruption`.
- **Design:** refit **only** Stage 3 / lasso_logistic on the reduced pool
  (81 → 71), everything else identical to the canonical run (cohort, target,
  subject grouping, exact canonical 10×5 folds, preprocessing, inner CV,
  hyperparameter grid, one-SE rule, hard pairs, convergence gating,
  ≥ 1-active-endometriosis constraint, metric definitions). 50/50 folds
  converged; 4,310 OOF rows; fold-reproduction check PASS; paired
  subject-aware bootstrap 2000/2000.
- **Why it did NOT replace the primary methodology:** the primary analysis was
  prespecified and frozen (Decisions 79, 94, 95, 96). Making the ≤ 4-subject
  rule a global predictor-eligibility rule would be a post-hoc methodology
  change that would require re-deriving all 9 pathways and a new winner
  selection. The sensitivity produced no evidence that a wholesale primary
  rerun is warranted.
- **Result:** discrimination robust (paired Δ PR-AUC +0.016 [−0.007, +0.043];
  AUROC +0.002 [−0.017, +0.023]); calibration/tuning materially altered
  (Brier Δ +0.044 [+0.030, +0.058]; calibration intercept Δ −0.80
  [−1.06, −0.55]; `class_weight` `none` 41/50 → `balanced` 38/50). Impact
  MATERIAL, not CRITICAL.
- **Artifacts:** `analysis/modeling/final_modeling/stage3_extreme_rarity_sensitivity.py`;
  `outputs/final_modeling/final_run/sensitivity/stage3_extreme_rarity_*`
  (gitignored); tracked summary
  `docs/finalization/EXTREME_RARITY_SENSITIVITY_SUMMARY.md`; submission
  Table I; rationale `docs/finalization/FINAL_MODELING_DECISIONS.md`.

## Threshold-free policy (LOCKED 2026-09-01)

- The primary run selects **no decision threshold** (not 0.5, Youden J,
  F1/accuracy/balanced-accuracy, cost-based, or prevalence-derived).
- `sensitivity` / `specificity` / `PPV` / `NPV` are `null` everywhere,
  `threshold_dependent_metrics_blocked = true`.
- Primary evaluation is threshold-independent only: PR-AUC, AUROC, Brier,
  calibration, and the corresponding curves.

## No holdout (LOCKED 2026-09-01)

- The historical sealed holdout's row-level membership is **unrecoverable**
  after the 447→431 cohort transition (no persisted membership artifact).
- **Locked decision:** it must never be reconstructed and a replacement
  holdout must never be created.
- Internal validation = the repeated subject-grouped nested CV. There is **no
  independent external / test-set / replacement-holdout validation**.
- `run_manifest.json` `holdout_status = "NOT_ACCESSED / NOT_CREATED"`; every
  final-modeling module is test-pinned against importing the holdout code
  (`test_holdout_sealed_never_accessed.py`).

## Software

- Python **3.12.10**, scikit-learn **1.9.0**, run in `.venv312`.
- Execution commit `8a06438`, `git_dirty = False`, run id
  `final_run_20260901T221447+0000`.

## Out of scope for the modeling run (separate work)

- Table 1 / cohort characteristics.
- The final adjusted odds-ratio / coefficient presentation table. When it is
  prepared: `adenomyosis_feature_7` / `_11` must not receive a conventional
  inferential OR (single carrier subject each → complete separation); OR
  suitability for other rare predictors is judged case-by-case on support,
  separation, and sparse-cell structure.
- Any threshold-dependent or decision-curve analysis.
- The final full-data deployment refit and any recalibration.
- Turning the post-hoc ≤ 4-unique-subject rule into a prespecified primary
  eligibility rule (would require reconsidering all 9 pathways).

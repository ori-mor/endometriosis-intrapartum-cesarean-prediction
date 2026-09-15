# RESULTS_FACTS — exact final numbers for the project book

> **Provenance note (submission package):** copied verbatim, without
> scientific content changes, from the canonical research repository at
> commit `e7676be3167c706950ce1a564fc454223f0d265d` (tag `final-project-2026`).
> Internal repository paths mentioned below refer to that canonical
> repository, not this submission package.


**Not a prose chapter.** A fact reference to prevent writing errors.

## Current final predictive model (Decision 99, Compact Ridge) — results

Source: `docs/finalization/COMPACT_RIDGE_FINAL_LOCK.md` §6–§7 (locked
internal-validation run + full-data refit). These are the **current**
numbers; everything from "## 1. Winner identity" onward below describes the
**historical, superseded** Stage 3 / LASSO Final-D run and its own numbers,
kept distinct and never substituted for these.

- **FACT — predictive performance** (repeated grouped-CV, 50/50 outer folds,
  0 failures; mean over 10 repeats): PR-AUC **0.348** (SD 0.015); AUROC
  **0.798** (SD 0.011); Brier **0.106** (SD 0.001); Brier skill (vs.
  constant-prevalence null) **+0.130** (SD 0.012); log-loss **0.337**
  (SD 0.005); calibration intercept **+0.162** (SD 0.096, ideal 0);
  calibration slope **1.115** (SD 0.066, ideal 1).
- **FACT — final full-data refit** (the model going forward, fit once on all
  431 rows): `C = 0.3162`, intercept `= −2.0476`, converged = True (lbfgs, 15
  iterations). This refit's own training-set fit statistics are never
  reported as performance — performance is exclusively the bullet above.
- **FACT — secondary adjusted OR** (six predictors, ordinary unpenalized MLE,
  n=431, 61 events; `outputs/results/compact_ridge_final/adjusted_or/`):
  clinically interpretable adjusted odds ratios for descriptive association
  only — e.g. nulliparity adjusted OR 8.37, prior CS 14.62, induction 6.01
  (see `table_adjusted_odds_ratios.md` for the full table with CIs). **Not**
  the source of any predictive-performance figure above, and **not**
  interchangeable with the Ridge coefficients (different estimator,
  different encoding, different purpose — see `COMPACT_RIDGE_FINAL_LOCK.md`
  §7 and the adjusted-OR README's "Relationship to the locked Ridge
  coefficients" section).
- **FACT — Firth sensitivity** (bias-reduced logistic regression, identical
  six-predictor design, fit because two hypertension categories are sparse):
  overall verdict `ROBUST — NO MATERIAL INTERPRETIVE CHANGE`. Sensitivity
  only — MLE remains the primary adjusted-OR model; Firth is never
  substituted into the primary forest plot.
- **DO NOT CLAIM:** that the Ridge coefficients in `COMPACT_RIDGE_FINAL_LOCK.md`
  §7 are adjusted odds ratios (they are penalized, standardized-scale
  predictive-model coefficients); that the adjusted-OR/Firth analysis is the
  predictive model or the source of PR-AUC/AUROC/Brier/calibration; that this
  architecture has external, independent, or test-set validation (internal
  repeated grouped CV only, performed after exploratory model development on
  the same dataset).

## HISTORICAL — Stage 3 / LASSO Final-D run results (superseded architecture)

Every number from here to the end of this document is from the completed,
now-**historical** Final-D scientific run
(`run_id = final_run_20260901T221447+0000`, execution commit `8a06438`,
`completion_status = COMPLETE`) and its Results-closure artifacts
(`outputs/results/final_submission/`, closure commit `4c11f36`). Cross-checked
against `docs/results/results_interpretation.md` and
`docs/finalization/FINAL_SCIENTIFIC_FREEZE.md`. These numbers remain an
accurate historical record and are not the current model's performance (see
the current section above).

Format per item: **FACT** · **INTERPRETATION** · **ALLOWED CLAIM** · **DO NOT
CLAIM**.

---

## 1. Winner identity

- **FACT:** The winning pathway is **Stage 3 / LASSO logistic**, selected by the
  pre-specified across-pathway one-SE rule (`rule_id =
  canonical_across_pathway_rule_v1`). Source of truth: `run_manifest.json`
  `winning_strategy`, `selection/winner_selection.json`,
  `outputs/results/final_submission/tables/table_a_all_9_pathways.md`
  (`winner = True` on exactly that row).
- **INTERPRETATION:** Among 9 prespecified pathways it had the highest mean
  repeat-level PR-AUC and was the only pathway in its own one-SE near-tie band.
- **ALLOWED CLAIM:** "Stage 3 / LASSO logistic was the pre-specified-rule
  winner among the nine candidate pathways."
- **DO NOT CLAIM:** that Top-N or elastic-net won; that the winner was chosen
  post-hoc or by eyeballing; that winning implies clinical readiness.

## 2. PR-AUC (primary metric)

- **FACT:** Winner mean repeat-level **PR-AUC = 0.272** (SD 0.018, SE 0.0056;
  10-repeat range 0.254–0.318). One-SE threshold = 0.2664. Next pathway
  (Stage 3 / elastic-net) = 0.2559. All-9 range 0.222–0.272 (Table A).
  Subject-grouped bootstrap 95% CI (B = 2000/2000) = **[0.212, 0.352]**.
  No-skill PR baseline = prevalence = **0.1415**.
- **INTERPRETATION:** Real signal well above the no-skill line; wide interval
  driven by only 61 events.
- **ALLOWED CLAIM:** "internal nested-CV PR-AUC 0.272 (95% CI 0.212–0.352),
  materially above the 0.14 event-prevalence baseline."
- **DO NOT CLAIM:** PR-AUC 0.307 or any other value as the winner's PR-AUC;
  that the CI represents external-validation uncertainty.

## 3. AUROC

- **FACT:** Winner mean **AUROC = 0.715** (repeat range 0.674–0.764).
  Bootstrap 95% CI = **[0.664, 0.762]**. All-9 range 0.654–0.715.
- **INTERPRETATION:** Moderate discrimination.
- **ALLOWED CLAIM:** "moderate discrimination, AUROC ≈ 0.71 (95% CI 0.66–0.76)."
- **DO NOT CLAIM:** "good"/"strong"/"excellent" discrimination; that AUROC
  alone means the model is usable.

## 4. Brier score

- **FACT:** Winner mean **Brier = 0.127** (bootstrap 95% CI [0.107, 0.147]).
  Constant-prevalence null Brier `p(1−p)` at `p = 61/431` = **0.1215**.
  Winner Brier (0.127) is **worse than the null** (Table G,
  `winner_brier_worse_than_null = True`).
- **INTERPRETATION:** Overall probability accuracy is poor because
  probabilities are miscalibrated, even though ranking (AUROC/PR-AUC) is
  informative.
- **ALLOWED CLAIM:** "the winner's Brier score (0.127) was slightly worse than
  a no-information constant-prevalence prediction (0.1215), reflecting
  inadequate calibration."
- **DO NOT CLAIM:** that Brier ≈ null means the model has no discrimination
  (it does — AUROC 0.71); hide or omit this comparison.

## 5. Calibration

- **FACT:** Bootstrap calibration **intercept = −0.681, 95% CI [−1.122, −0.268]**
  (ideal 0; CI excludes 0). Bootstrap calibration **slope = 0.671, 95% CI
  [0.485, 0.874]** (ideal 1; CI excludes 1). Table G / Figure 4.
- **INTERPRETATION:** Predicted probabilities are systematically too extreme
  (slope < 1) and biased (intercept < 0). Calibration is inadequate.
- **ALLOWED CLAIM:** "probability calibration was inadequate (calibration
  slope 0.67, intercept −0.68; both 95% CIs excluded their ideal values)."
- **DO NOT CLAIM:** calibration is adequate / acceptable / "reasonable";
  that recalibration was done (it was not); that predicted probabilities can
  be communicated to patients as-is.

## 6. Bootstrap CIs (winner, subject-grouped, B = 2000/2000 valid)

- **FACT:** PR-AUC [0.212, 0.352] · AUROC [0.664, 0.762] · Brier [0.107, 0.147]
  · calibration intercept [−1.122, −0.268] · calibration slope [0.485, 0.874].
  Seed 20260901; `post_run_bootstrap.py`; 0 invalid replicates.
- **INTERPRETATION:** Sampling uncertainty **conditional on the saved repeated
  nested-CV OOF architecture**.
- **ALLOWED CLAIM:** "subject-level bootstrap 95% CIs".
- **DO NOT CLAIM:** that the bootstrap is external validation; a full
  model-development-procedure bootstrap; a winner-selection optimism
  correction; or proof overfitting was eliminated.

## 7. No-skill / null baselines

- **FACT:** PR no-skill baseline = event prevalence = **0.1415**. Null Brier =
  `p(1−p)` = **0.1215**.
- **ALLOWED CLAIM:** both, verbatim, as reference lines.
- **DO NOT CLAIM:** a different prevalence; that beating the PR baseline means
  beating the Brier baseline (it does not here).

## 8. Consistently selected predictors (winner, 50 outer models — Table C / Figure 6)

- **FACT:** `AGE` 100% · `nulliparity` 100% (`NOT_RARE`) ·
  `indication_for_induction_status` 98% · `height` 96%. 72 source predictors
  active in ≥ 1 fold; most < 50%. Table C carries two separate columns —
  `rarity_class` (`SINGLE_CASE` 1 / `EXTREME_RARITY` 2–4 / `VERY_RARE` 5–9 /
  `RARE` 10–19 / `NOT_RARE` ≥ 20) and `target_cell_flag` — plus
  `stability_interpretation`. `adenomyosis_feature_7` (78%) / `_11` (76%) are
  each `SINGLE_CASE` (1 unique subject) + complete separation, labelled
  `single_case_driven_exploratory`, not part of the stable core.
- **INTERPRETATION:** A stable 4-predictor obstetric backbone; the rest
  fold-dependent. High selection frequency for a ≤ 4-subject predictor is
  fold exposure, not stability.
- **ALLOWED CLAIM:** "the obstetric predictors AGE, nulliparity, induction
  indication status and height were consistently selected across resampling
  (≥ 96% of outer models)."
- **DO NOT CLAIM:** these four "are the model"; a specific adjusted OR for any
  of them; that selection frequency = effect size or significance; that
  `adenomyosis_feature_7` / `_11` belong in the stable set.

## 9. Endometriosis-family predictor stability (Table D / Figure 7)

- **FACT:** `cs_scar_endometriosis` — 98% (49/50) canonical winner outer
  models + 50/50 extreme-rarity sensitivity outer fits, median coef +0.145,
  consistent positive; subject support `RARE` (**12 unique carrier subjects**,
  events in both outcome groups, `target_cell_flag = ok`) →
  `consistently_selected_with_limited_support`. `adenomyosis_feature_7` 78%
  and `_11` 76% — `SINGLE_CASE` (one unique subject each, different subjects,
  both `target = 1`) + complete separation → `single_case_driven_exploratory`.
  `adenomyosis_feature_4` 70% (−) — subject support `NOT_RARE` (**39 carrier
  subjects**, classified from actual count) **but** `sparse_target_cell` (2
  events among carriers) → `sparse_target_cell_exploratory`. `placental_abruption`
  72% — `EXTREME_RARITY` (4 subjects) → exploratory. All 50 canonical winner
  outer models contained ≥ 2 active endometriosis predictors.
- **INTERPRETATION:** No endometriosis-family predictor is robustly stable.
  `cs_scar_endometriosis` is consistently selected but on limited support; the
  adenomyosis feature codes are exploratory (single-case or sparse-cell).
- **ALLOWED CLAIM:** "`cs_scar_endometriosis` was consistently selected across
  resampling (consistent positive direction) but is supported by a limited
  number of subjects and needs independent validation."
- **DO NOT CLAIM:** `cs_scar_endometriosis` as a confirmed independent /
  robust population-level / causal / externally validated risk factor;
  `adenomyosis_feature_7` / `_11` / `_4` as stable, robust, or validated;
  an inferential OR for any of them (`_7` / `_11` are complete-separation
  single-case predictors — OR undefined/misleading).

## 10. Constrained vs unconstrained (Table E / Figure 9)

- **FACT:** Matched Stage 3 / LASSO benchmark, 50/50 folds. Unconstrained
  LASSO selected ≥ 1 endometriosis predictor in **49/50** folds on its own;
  the constraint changed exactly **1/50** folds. Paired delta
  (unconstrained − constrained): PR-AUC −0.0017, 95% CI **[−0.0048, 0.0015]
  (crosses zero)**; AUROC −0.0041, CI [−0.0081, −0.0002]; Brier +0.0025, CI
  [0.0013, 0.0035].
- **INTERPRETATION:** The endometriosis constraint costs essentially nothing
  and mostly formalizes what the unconstrained model already does.
- **ALLOWED CLAIM:** "requiring ≥ 1 endometriosis-specific predictor did not
  materially change performance (paired PR-AUC difference 95% CI included
  zero) and was almost always satisfied naturally."
- **DO NOT CLAIM:** the constrained model is statistically **superior** on
  PR-AUC; that the tiny AUROC/Brier CI exclusions are clinically meaningful.

## 11. Stage 3A vs Stage 3B (Table F / Figure 10)

- **FACT:** 50/50 pairs. `gestational_age_at_delivery_days` active in **46%**
  of Stage-3B outer models. Paired-delta (B − A) bootstrap 95% CIs (B =
  2000/2000, prediction-only reconstruction reconciled to ≤ 1e-8): PR-AUC
  [−0.0193, 0.0082] · AUROC [−0.0134, 0.0004] · Brier [−0.0018, 0.0025] ·
  calibration slope [−0.0625, 0.0036] — **all cross zero**. Calibration
  intercept [−0.1149, −0.0083] — excludes zero (small, secondary).
- **INTERPRETATION:** Gestational age at delivery is not the main driver of
  the Stage-3 result.
- **ALLOWED CLAIM:** "excluding `gestational_age_at_delivery_days` did not
  materially change Stage-3 discrimination (all primary paired 95% CIs
  included zero)."
- **DO NOT CLAIM:** Stage 3A and 3B are formally "equivalent"; that
  gestational age is irrelevant.

## 12. Run integrity (Table H)

- **FACT:** `completion_status = COMPLETE`; `primary_search 450/450`;
  `matched_unconstrained_benchmark 50/50`; `stage3_gestational_age_sensitivity
  50/50`; `post_run_bootstrap B_valid = 2000`; Stage-3A/B reconstructed +
  bootstrapped (2000/2000); primary OOF rows = **38,790** (9 × 10 × 431);
  `final_model_refit = NOT_RUN`; `threshold_dependent_analysis =
  BLOCKED_PENDING_APPROVED_RULE`; `holdout_status = NOT_ACCESSED / NOT_CREATED`.
- **ALLOWED CLAIM:** all of the above verbatim.
- **DO NOT CLAIM:** a final model was fit; a threshold exists; a holdout was
  used.

## 13. Extreme-rarity robustness sensitivity (Table I)

Full reference: `docs/finalization/EXTREME_RARITY_SENSITIVITY_SUMMARY.md`.

- **FACT:** Post-hoc; Stage 3 / lasso_logistic only; canonical 10×5 folds;
  10 predictors with ≤ 4 unique carrier subjects removed (Stage-3 pool
  **81 → 71**); 50/50 folds converged; 4,310 OOF rows; fold-reproduction
  check PASS; paired subject-aware bootstrap 2000/2000. Paired Δ
  (reduced − primary): PR-AUC **+0.016 [−0.007, +0.043]** (CI crosses 0),
  AUROC **+0.002 [−0.017, +0.023]**, Brier **+0.044 [+0.030, +0.058]**,
  calibration intercept **−0.80 [−1.06, −0.55]**. Selected `class_weight`
  `none` 41/50 → `balanced` 38/50.
- **INTERPRETATION:** Discrimination is robust to removing the extreme-rarity
  predictors; absolute calibration and hyperparameter tuning are sensitive to
  predictor-pool composition. Impact MATERIAL, not CRITICAL.
- **ALLOWED CLAIM:** "removing predictors supported by ≤ 4 unique subjects did
  not materially degrade discrimination (paired PR-AUC and AUROC 95% CIs
  included zero); calibration and tuning changed materially and are sensitive
  to which predictors are in the pool."
- **DO NOT CLAIM:** that the reduced-pool run replaced the primary model; that
  the ≤ 4-subject rule was prespecified; that all 9 pathways were rerun; that
  the calibration change proves the removed predictors "improve calibration"
  (removal changed the entire penalized fitting/tuning pathway — no causal
  attribution).

### feature_7 / feature_11 — FACT / INTERPRETATION / ALLOWED / DO NOT

- **FACT:** `adenomyosis_feature_7` and `adenomyosis_feature_11` each have
  **1** unique carrier subject (`rarity_class = SINGLE_CASE`; different
  subjects, both `target = 1` → `target_cell_flag = complete_separation`).
  Active in 39/50 and 38/50 canonical winner outer models; the carrier is in
  outer training in ~40/50 folds by construction; active in ~39/40 (`_7`) and
  ~38/40 (`_11`) when the carrier is in training, 0/10 when absent.
- **INTERPRETATION:** Single-case quasi-separation artifact. Selection
  frequency reflects fold exposure.
- **ALLOWED CLAIM:** "flagged `SINGLE_CASE_DRIVEN_EXPLORATORY`; not
  interpretable as a stable predictor."
- **DO NOT CLAIM:** stable / highly stable / robust / sign-consistent
  evidence / independently supported / an odds ratio.

### cs_scar_endometriosis — FACT / INTERPRETATION / ALLOWED / DO NOT

- **FACT:** ~12 unique carrier subjects (`rarity_class = RARE`), events in
  both outcome groups (`target_cell_flag = ok`); selected 49/50 canonical
  winner outer fits and 50/50 extreme-rarity sensitivity outer fits;
  consistent positive direction.
- **INTERPRETATION:** `CONSISTENTLY_SELECTED_WITH_LIMITED_SUPPORT` — strongest
  current endometriosis-specific candidate signal.
- **ALLOWED CLAIM:** "consistently selected with limited support; needs
  independent validation."
- **DO NOT CLAIM:** confirmed independent risk factor / robust population-level
  predictor / causal / externally validated.

### adenomyosis_feature_4 — FACT / INTERPRETATION / ALLOWED / DO NOT

- **FACT:** subject support `rarity_class = NOT_RARE` (39 unique carrier
  subjects, classified from its actual count); `target_cell_flag =
  sparse_target_cell` (**2 events among carriers**); 70% selection, consistent
  negative.
- **INTERPRETATION:** Sparse target cell — exploratory. Not single-case-driven
  (distinct from `_7` / `_11`). Subject-support rarity and target-cell
  sparsity are separate dimensions.
- **ALLOWED CLAIM:** "sparse / exploratory (`sparse_target_cell_exploratory`)."
- **DO NOT CLAIM:** robust / stable / validated; group it with the single-case
  predictors.

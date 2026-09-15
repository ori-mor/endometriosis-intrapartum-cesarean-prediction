# LIMITATIONS_FACTS — the limitation list, stated precisely

> **Provenance note (submission package):** copied verbatim, without
> scientific content changes, from the canonical research repository at
> commit `e7676be3167c706950ce1a564fc454223f0d265d` (tag `final-project-2026`).
> Internal repository paths mentioned below refer to that canonical
> repository, not this submission package.


**Not a prose chapter.** Each limitation is stated so it can be transcribed
into the project book without overstating or understating it.

## Current final predictive model (Decision 99, Compact Ridge) — limitations

Source: `docs/finalization/COMPACT_RIDGE_FINAL_LOCK.md` §6, §9. These apply to
the **current** model; the numbered list below (from "1. Only 61 events."
onward) is the **historical** Stage 3 / LASSO limitation list and is not
reused verbatim for Compact Ridge — several of those historical items
(notably calibration adequacy and selection optimism from a 9-pathway
comparison) do not carry over unchanged and are addressed separately here.

1. **Only 61 events**, same cohort as the historical run — all uncertainty
   is wide at 61 events; rare/unstable categorical levels remain a concern.
2. **Internal validation only.** Reported performance (§6 of the lock
   document) is repeated subject-grouped nested cross-validation on the same
   431-delivery Sheba cohort.
3. **No external validation** and no independent holdout — same locked,
   never-reconstruct decision as the historical run
   (`holdout_status = NOT_ACCESSED / NOT_CREATED`).
4. **Selection optimism from exploratory model development on the same
   dataset.** This is a *different* selection-optimism source than the
   historical run's 9-pathway comparison: this architecture (6 predictors,
   Ridge, no `gestational_age_at_delivery_days`, no endometriosis predictor)
   was itself chosen by comparing cross-validated performance during the
   `exploratory/overnight-model-improvement` process, on the same
   development data used for the reported internal-validation numbers. The
   internal-validation figures in §6 of the lock document therefore carry
   some optimism from that selection, exactly as the historical run's
   9-pathway selection did — this limitation is **not resolved**, only
   differently sourced.
5. **Calibration is materially improved but not validated as
   deployment-adequate.** Brier skill **+0.130** (beats the
   constant-prevalence null, unlike the historical run's **−0.045**);
   calibration intercept **+0.162** / slope **1.115** (both much closer to
   ideal than the historical run's **−0.689** / **0.660**). This is a real,
   disclosed improvement — it must **not** be read as "the historical
   Stage-3 calibration defect persists in Compact Ridge" — but it is also
   **not** validated external/deployment-grade calibration: no
   recalibration, no threshold policy, and no decision-analytic evaluation
   exists for this architecture.
6. **No threshold validation, no deployment model, no clinical calculator** —
   same as the historical run.
7. **`BMI_before`'s individual contribution is weak and directionally
   unstable** (54% sign consistency across the 50 outer folds, near-zero
   median coefficient) — disclosed, not smoothed over; it is retained
   because it is part of the frozen architecture, not because its individual
   effect is stable.
8. **No endometriosis-specific predictor is in the final model.** Four
   completed exploratory analyses (`COMPACT_RIDGE_FINAL_LOCK.md` §4) found no
   stable incremental predictive value from any measured endometriosis
   phenotype/severity/surgical-history representation, individually or
   aggregated. This is a negative predictive-modeling result in a small
   retrospective cohort — **not** a causal or clinical-relevance claim about
   endometriosis.
9. **Associations are not causal** — same as the historical run; this is a
   predictive, not causal, design.
10. **The secondary six-predictor adjusted-OR/Firth association analysis is
    descriptive, non-causal, and uses conventional (non-cluster-robust)
    covariance**, unlike other cluster-robust association analyses in this
    project — disclosed as very likely immaterial at this cohort's cluster
    structure (1 of 430 subject groups contributes 2 of 431 rows), but a
    genuine methodological inconsistency a careful reader should know about.
    It is not the predictive model and its coefficients/ORs are not
    interchangeable with the Ridge coefficients.

## HISTORICAL — Stage 3 / LASSO Final-D run limitations (superseded architecture)

Everything from here to the end of this document is the limitation list for
the **historical, superseded** Stage 3 / LASSO Final-D run. It remains an
accurate historical record. Sources:
`docs/results/results_interpretation.md` §I,
`analysis/modeling/final_modeling/RESULT_ARTIFACT_SCHEMA.md`,
`run_manifest.json`.

---

1. **Only 61 events.** The modeling cohort has 431 deliveries but only **61
   intrapartum cesarean sections**. All uncertainty is wide at 61 events, as
   reflected in the bootstrap CI widths (e.g. winner PR-AUC 95% CI
   [0.212, 0.352]). Rare predictor categories are especially unstable.

2. **Internal validation only.** Reported performance is from **repeated
   subject-grouped nested cross-validation** on the single 431-delivery Sheba
   cohort. It is an internal, resampling-based estimate.

3. **No independent external validation.** No cohort external to Sheba, and no
   independent post-selection test partition, was used. The project must never
   be described as externally, independently, or test-set validated
   (`holdout_status = NOT_ACCESSED / NOT_CREATED`; the historical holdout's
   membership is unrecoverable and is a locked never-reconstruct decision).

4. **Selection optimism from comparing 9 pathways.** The winning pathway was
   chosen from 9 prespecified strategies using the **same outer-resampling
   comparison that is then reported**. Reported performance therefore carries
   some selection optimism and is not equivalent to a fully independent
   post-selection estimate. The bootstrap does **not** remove this — it
   quantifies sampling uncertainty conditional on the saved OOF architecture
   only.

5. **Calibration is inadequate and sensitive to predictor-pool composition.**
   Bootstrap calibration slope 0.67 (95% CI [0.485, 0.874]) and intercept
   −0.68 (95% CI [−1.122, −0.268]); both CIs exclude their ideal values. The
   winner's Brier (0.127) is slightly worse than a constant-prevalence null
   (0.1215). Predicted probabilities are overconfident and must not be
   communicated as calibrated risks. No recalibration was performed. The
   post-hoc extreme-rarity sensitivity (removing 10 predictors) materially
   worsened Brier (Δ +0.044) and calibration intercept (Δ −0.80) and changed
   the LASSO's `class_weight` tuning — so absolute calibration depends on
   which predictors are in the pool. This change **cannot** be attributed
   causally to the removed predictors (removal alters the whole penalized
   fitting/tuning pathway).

6. **No threshold validation.** No decision threshold was selected; no
   sensitivity / specificity / PPV / NPV / confusion matrix / decision-curve
   analysis exists (`threshold_dependent_analysis =
   BLOCKED_PENDING_APPROVED_RULE`). Any such analysis would require a
   separate, approved, leakage-safe, training-only threshold policy.

7. **No final deployment model.** No full-data refit was performed
   (`final_model_refit = NOT_RUN`; `final_model/` is empty). There is no
   clinical calculator. A future refit is scoped but not authorized
   (`docs/results/final_full_data_refit_proposal.md`).

8. **Rare-category coefficient instability + ultra-rare predictor support.**
   Several categorical predictor levels are rare and numerically unstable
   across resampling. No individual coefficient may be reported as a robust,
   conventional adjusted odds ratio (see Table C / Table D stability columns).
   Some predictors are supported by only a handful — in two cases, **one** —
   unique subjects. `adenomyosis_feature_7` and `adenomyosis_feature_11` each
   have a single carrier subject; their high outer-model selection frequency
   (78% / 76%) is fold exposure, not stability, and they must not receive a
   conventional inferential odds ratio (complete separation).

8a. **Selection frequency can exaggerate apparent stability.** When very few
    unique subjects support a predictor, a single carrier lands in ~40/50
    outer training folds by construction, so a high active-fraction there is
    not evidence of a population-level effect. Some predictor-level
    interpretations therefore remain **exploratory** (Table C / Table D
    `stability_interpretation`; Figures 6/7 distinguish extreme-rarity
    predictors).

9. **Associations are not causal.** The design is predictive
   (regularized logistic regression under nested CV). No causal
   interpretation of any predictor — endometriosis-specific or otherwise,
   including `gestational_age_at_delivery_days` — is supported.

10. **No endometriosis-family predictor is robustly stable.**
    `cs_scar_endometriosis` is consistently selected (98% canonical + 50/50
    sensitivity outer fits) but supported by only ~12 unique subjects —
    "consistently selected with limited support", the strongest current
    endometriosis-specific candidate signal, not a confirmed risk factor.
    `adenomyosis_feature_7` / `_11` (78% / 76%) are single-case-driven
    (1 subject each) — exploratory. `adenomyosis_feature_4` (70%) is
    sparse-cell (39 subjects, 2 events) — exploratory. The remaining
    endometriosis-family predictors are fold-dependent and must not be
    presented as individually robust findings.

10a. **The extreme-rarity sensitivity was for robustness evaluation, not
     redefinition.** The post-hoc ≤ 4-unique-subject removal + Stage-3-LASSO
     refit was used to test whether the discrimination finding depends on
     ultra-rare predictors (it does not). It is not a new primary model and
     the ≤ 4-subject threshold is not a prespecified eligibility rule. See
     `docs/finalization/FINAL_MODELING_DECISIONS.md`.

11. **The endometriosis constraint is a design choice, not a proven benefit.**
    The matched unconstrained benchmark shows the constraint neither
    materially helps nor harms performance (paired PR-AUC delta 95% CI crosses
    zero) and is almost always satisfied naturally (49/50 folds). It should be
    framed as preserving clinical interpretability, not as improving the
    model.

12. **Stage 3A vs 3B is a sensitivity check, not an equivalence proof.**
    All primary paired deltas' 95% CIs cross zero, but "not distinguishable at
    this sample size" is not the same as formal equivalence.

13. **Singleton restriction is inherited, not verified locally.** The
    singleton-only cohort is an upstream condition from Sheba; the supplied
    workbook contains no variable to re-verify it. A future dataset version
    must have this re-confirmed with the data owner.

14. **Raw run artifacts are local-only.** The `outputs/final_modeling/final_run/`
    tree (including `run_manifest.json` and all serialized models) is
    gitignored and exists only on the analysis machine. The committed,
    shareable evidence is the 8 summary tables, 10 figures,
    `results_interpretation.md`, and `RESULT_ARTIFACT_SCHEMA.md`. Full
    regeneration requires the local raw data and an explicit, authorized
    rerun.

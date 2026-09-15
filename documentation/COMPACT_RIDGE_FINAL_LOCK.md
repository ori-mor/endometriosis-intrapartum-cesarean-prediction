# COMPACT RIDGE FINAL LOCK — Endometriosis & Intrapartum Cesarean Section

> **Provenance note (submission package):** copied verbatim, without
> scientific content changes, from the canonical research repository at
> commit `e7676be3167c706950ce1a564fc454223f0d265d` (tag `final-project-2026`).
> Internal repository paths mentioned below refer to that canonical
> repository, not this submission package.


**Status: CANONICAL. This is the current final predictive-model architecture
decision, superseding the Stage 3 / LASSO logistic winner recorded in
`docs/finalization/FINAL_SCIENTIFIC_FREEZE.md` for the purpose of what model
is final.** `FINAL_SCIENTIFIC_FREEZE.md` remains the accurate historical
record of the original Final-D 9-pathway run and is not rewritten; it now
carries a pointer to this document. This document does **not** replace
`FINAL_SCIENTIFIC_FREEZE.md`'s cohort, CV-structure, or general methodology
sections (§C, §D unchanged) — only the architecture, predictor set, and
final winner sections are superseded.

Freeze date: **2026-09-04**. Prepared as part of the model-development
closure that followed the overnight model-improvement exploratory process.

Companion documents:
- Historical original freeze (Stage 3 / LASSO): `docs/finalization/FINAL_SCIENTIFIC_FREEZE.md`
- Exploratory process record: `analysis/modeling_experiments/overnight_model_improvement/FINDINGS.md`
  (branch `exploratory/overnight-model-improvement`)
- Endometriosis incremental-value record:
  `analysis/modeling_experiments/overnight_model_improvement/ENDO_ADDON_FINDINGS.md`,
  `ENDO_SIGNAL_RECOVERY_FINDINGS.md`, `ENDO_FEATURE_PROFILING_FINDINGS.md`,
  `ENDO_PHENOTYPE_AGGREGATION_FINDINGS.md` (all on `exploratory/overnight-model-improvement`)

  **Note on the paths above:** `analysis/modeling_experiments/` is
  intentionally gitignored on `main` (and every branch derived from it,
  including this one) and holds no tracked source here — these five files
  exist only as committed history on the `exploratory/overnight-model-improvement`
  branch itself (`git show exploratory/overnight-model-improvement:analysis/modeling_experiments/overnight_model_improvement/FINDINGS.md`,
  or check out that branch directly). Their absence from this branch's working
  tree is expected, not a missing-file defect, and the locked architecture
  and metrics below do not require checking out or executing that branch to
  reproduce — see §6/§7 for the self-contained, read-only reproduction
  commands.
- Lock implementation + artifacts:
  `analysis/modeling/final_modeling/final_compact_ridge_lock.py`,
  `outputs/final_modeling/compact_ridge_lock/` (gitignored, regenerable)
- Full decision chronology: `docs/clinical_decisions/manual_decisions_log.md` (Decision 99)

---

## 1. Why this supersedes the Stage 3 / LASSO winner

`FINAL_SCIENTIFIC_FREEZE.md` §H/§J/§O already disclosed that the original
winner's absolute calibration was inadequate (bootstrap calibration
intercept/slope CIs excluded the ideal values; mean Brier numerically worse
than the constant-prevalence null). An exploratory model-improvement process
(branch `exploratory/overnight-model-improvement`, never merged, canonical
run never modified during the process) subsequently tested alternative
estimator families, penalty policies, and compact prespecified predictor
sets against the same cohort, target, subject grouping, and canonical
10×5/inner-5 CV structure. Its headline finding (`.../FINDINGS.md`): **a
compact, prespecified ~7–8-predictor architecture is a clear, robust
improvement over the full-pool 81-predictor penalized search on every
metric** (PR-AUC, AUROC, Brier, calibration), regardless of estimator
(LASSO / ridge / Firth all converge on the same conclusion). A focused
follow-up then evaluated the well-supported endometriosis representations
individually, with additional sparse-sensitivity, block, interaction,
differential-penalty, and clinically prespecified phenotype-aggregation
analyses; the full canonical endometriosis family was reviewed for support
and representation, and found **no stable incremental predictive value**
from any of them (§4 below). The architecture locked here is the
non-endometriosis compact core that survived that entire process.

**No further model search, predictor search, or estimator comparison was
performed to produce this lock.** This document freezes and internally
validates one specific, already-selected candidate.

## 2. Research question (unchanged from §A of the original freeze)

Unchanged from `FINAL_SCIENTIFIC_FREEZE.md` §A. Design remains predictive
(nested cross-validation, regularized logistic regression), not causal.

## 3. Target and cohort (unchanged from §B/§C)

Identical to `FINAL_SCIENTIFIC_FREEZE.md` §B/§C: `target_intrapartum_cs`,
431 deliveries, 370 vaginal / 61 intrapartum cesarean, prevalence 0.1415.
Modeling input matrix SHA-256 reproduced exactly:
`12733c8548cdda2e3c19ae563b0750ba0f41173fc93eaed730f35f2c1f8a8c69` — **the
same byte-identical `outputs/eda_c/modeling_dataset_candidate_features.xlsx`
input as the original Final-D run.** No cohort, target, or data change of
any kind is associated with this architecture lock.

## 4. The completed endometriosis exploratory analyses — negative
   incremental-value conclusion (retained, not hidden)

Four focused analyses on `exploratory/overnight-model-improvement`, all
using the canonical cohort/CV/preprocessing:

1. **Endometriosis Add-On Experiment** (`ENDO_ADDON_FINDINGS.md`) — fixed
   the non-endometriosis compact core, tested every well-supported
   endometriosis representation (single terms, 2–3-term blocks, a burden
   count) as an add-on. Result: no representation showed a convincing
   incremental PR-AUC/AUROC gain (every ΔPR-AUC 95% CI included 0); forcing
   2–3 endo terms into an all-retained ridge consistently *degraded*
   log-loss and, in one block, PR-AUC (CI excluded 0, unfavorably).
2. **Endometriosis Signal Recovery / Incremental-Value Audit**
   (`ENDO_SIGNAL_RECOVERY_FINDINGS.md`) — tested standalone signal, earlier
   entry into the timeline, absorption by late Stage-3 variables, and a
   jointly-shrunk block. Result: standalone AUROC 0.40–0.47 (at/below
   chance); adding the block degrades the core by the *same* magnitude at
   every stage (no early window where it helps); no absorption by
   `induction_any_bin` or `gestational_age_at_delivery_days`; a
   differentially-penalized block is driven to near-zero by inner CV.
3. **Endometriosis Feature Profiling / Relative Signal Analysis**
   (`ENDO_FEATURE_PROFILING_FINDINGS.md`) — ranked the individual
   endometriosis variables themselves (association, standalone prediction,
   stability, leave-one-out contribution within an endo-only block).
   Result: `adenomyosis` is the relatively most internally consistent
   (92% sign-stable, non-negative leave-one-out contribution) but remains
   weak/non-significant in absolute terms (crude OR 1.18 [0.68, 2.04],
   standalone AUROC 0.478); `endometriosis_surgery`, `deep_endometriosis`,
   and `peritoneal_endometriosis` show a reproducibly *inverse*
   (protective-direction) signal across three independent lines of evidence;
   `cs_scar_endometriosis` (12 carriers / 5 events) shows the only nominal
   crude association (Firth OR 4.72 [1.45, 15.34]) but is explicitly a
   labelled sparse sensitivity, not adoptable.
4. **Endometriosis Phenotype Aggregation Audit**
   (`ENDO_PHENOTYPE_AGGREGATION_FINDINGS.md`) — tested whether aggregating
   the individual variables into 7 clinically motivated composite
   phenotypes recovers a signal the individual variables lack. Result: no
   composite survives Holm or BH-FDR correction; none improves prediction
   beyond a 6-variable obstetric core (one significantly worsens it);
   aggregation stabilizes coefficient *sign* for several composites but
   consistently toward a small, non-significant, protective direction.

**Conclusion, stated plainly and retained as a scientific finding:**
measured endometriosis phenotype, severity, and surgical-history variables
did **not** demonstrate stable incremental predictive value beyond the
maternal/obstetric core, individually or in any tested combination or
aggregation, in this cohort. This is a negative result about *prediction* in
a small retrospective cohort — it is not evidence against endometriosis
having clinical relevance to these patients' care, and it is not a causal
claim. **No endometriosis-specific predictor was forced into the final
predictive model** to avoid hiding this negative result behind a
face-validity inclusion.

## 5. Final locked architecture

**Compact Ridge (L2-penalized) logistic regression.**

| | |
|---|---|
| Predictors (6) | `AGE`, `nulliparity`, `S_P_CS`, `BMI_before`, `derived_hypertension_pih_pet_spectrum`, `induction_any_bin` |
| Removed vs. the compact-core exploratory candidate | `gestational_age_at_delivery_days` |
| Endometriosis-specific predictor forced in | **none** |
| Penalty | L2 (Ridge), no predictor-selection step (all 6 always retained) |
| Hyperparameter grid | 15-point `logspace(-2, 1.5)` — identical to the "compact_ridge_brier" / Arm F1_brier procedure used throughout the exploratory work |
| Selection rule | PR-AUC one-SE band → lowest inner Brier → smallest C (tiebreak) — **probability-aware**, chosen because absolute calibration was the original winner's weakest property (§O of the original freeze) |
| Preprocessing | Fold-safe median imputation (numeric) / most-frequent imputation (categorical) + standardization; `BMI_before` fold-safe-recomputed from `height` + `weight_before_pregnancy`; full-dummy one-hot for `derived_hypertension_pih_pet_spectrum` (penalized model, not reference coding) |
| Structural constraints | None of the endometriosis-family hard co-entry pairs apply (no endometriosis predictor present); `induction_any_bin`'s only hard partner, `indication_for_induction_status`, is not in the frozen set, so no training-fold hard-pair resolution step is needed |
| Intended prediction moment | **Beginning of labor / start of trial of labor** — `induction_any_bin` and, implicitly, the decision to attempt a trial of labor are known at this moment; no post-labor-onset or intrapartum variable is present |

### Why `gestational_age_at_delivery_days` was removed

The overnight exploratory work found removing it from the compact ridge core
*improved* its cross-validated performance (side finding in
`endo_signal_recovery`: PR-AUC 0.335→0.348 on the compact ridge when GA was
dropped), while `induction_any_bin` carried essentially all of the Stage-3
timing lift. Clinical clarification from Keren establishes that
`gestational_age_at_delivery_days` was considered available at the Stage-3
prediction horizon, corresponding to the onset of labor / beginning of the
trial of labor, and was therefore eligible for the later-stage modeling
framework. It is nevertheless excluded from the final Compact Ridge
architecture because exploratory comparison showed improved cross-validated
predictive performance after its removal. The earlier leakage-adjacency
chronology remains preserved in the decision log as superseded history and
should not be used as the current final-model rationale.

### Why `induction_any_bin` is retained

`induction_any_bin` is Stage-3-eligible per Decision 28 and was found,
repeatedly across the exploratory work, to carry the great majority of the
compact core's discriminative advantage over a pre-labor-only core. It is
known at the intended prediction moment (start of trial of labor / decision
to induce).

## 6. Locked internal-validation run (final reported performance)

**Because this architecture was selected using exploratory analyses on the
same development dataset used here, this is INTERNAL repeated grouped
cross-validation performed after exploratory model development — it is
NOT an independent test set and NOT external validation.** The same caveat
that already applied to the original Stage 3 / LASSO winner (§G/§P/§S of
the original freeze: no external validation exists anywhere in this
project) applies here, with the additional, explicit acknowledgment that
this specific architecture was itself chosen by looking at cross-validated
performance during the exploratory phase — so even the internal-validation
numbers below carry some optimism from that selection process, exactly as
the original 9-pathway selection did (§G of the original freeze).

- Cohort / target / grouping: identical to §3 above.
- Outer CV: canonical **10 repeats × 5 grouped folds = 50 outer models**
  (`modeling_core.make_outer_splits`, unchanged seeds).
- Inner CV: canonical grouped 5-fold, training-fold only, unchanged seeds.
- Estimator/procedure: exactly as locked in §5, run identically in every
  outer fold (no comparison, no reselection across folds).
- Completeness: **50/50 outer folds converged and scorable, 0 failures.**
- Artifacts: `outputs/final_modeling/compact_ridge_lock/report/{fold_level_metrics,repeat_level_metrics,coefficient_stability}.csv`,
  `locked_validation_oof_predictions.csv` (complete OOF, all 431 rows × 10
  repeats), `locked_validation_manifest.json` (gitignored, regenerable;
  re-run with `python -m analysis.modeling.final_modeling.final_compact_ridge_lock --validate`).

### Final locked metrics (repeat-level, mean over 10 repeats)

| Metric | Compact Ridge (this lock) | Historical Stage 3 / LASSO (original freeze) |
|---|---:|---:|
| PR-AUC | **0.348** (SD 0.015) | 0.272 (SD 0.018) |
| AUROC | **0.798** (SD 0.011) | 0.715 (SD 0.029) |
| Brier | **0.106** (SD 0.001) | 0.127 (SD 0.014) |
| Brier skill (vs. constant-prevalence null) | **+0.130** (SD 0.012) | −0.045 (SD 0.114) |
| log-loss | **0.337** (SD 0.005) | 0.421 (SD 0.070) |
| Calibration intercept (ideal 0) | **+0.162** (SD 0.096) | −0.689 (SD 0.667) |
| Calibration slope (ideal 1) | **1.115** (SD 0.066) | 0.660 (SD 0.347) |

Every metric improves, most substantially calibration: the constant-
prevalence-null-beating Brier skill (+0.130 vs. −0.045) and the
calibration intercept/slope both landing much closer to their ideal values
directly addresses the inadequate-calibration finding that was the original
freeze's principal limitation (§J/§O of `FINAL_SCIENTIFIC_FREEZE.md`).
Discrimination (AUROC 0.798 vs. 0.715) also improves materially. These
deltas are descriptive, repeat-level comparisons on the same canonical OOF
convention used throughout the project; no formal paired significance test
against the historical winner was computed as part of this lock (that
question was already answered by the compact-vs-full-pool comparisons in
the exploratory `FINDINGS.md`, which used a proper paired subject bootstrap
and found the compact architecture's advantage's CIs excluded 0).

### Chosen penalty (C) across the 50 outer folds

| C | Folds selected |
|---:|---:|
| 0.100 | 11 |
| 0.178 | 29 |
| 0.316 | 9 |
| 0.562 | 1 |

Stable: 40/50 folds (80%) select one of the two adjacent grid points
0.100/0.178.

### Coefficient sign stability across the 50 outer folds

| Predictor | Median coef. (standardized) | IQR | Sign consistency |
|---|---:|---:|---:|
| `AGE` | +0.479 | 0.085 | 100% |
| `nulliparity` | +0.739 | 0.142 | 100% |
| `S_P_CS` | +0.344 | 0.139 | 100% |
| `induction_any_bin` | +0.708 | 0.091 | 100% |
| `BMI_before` | −0.015 | 0.098 | 54% (≈ coin-flip) |

`derived_hypertension_pih_pet_spectrum` is a 3-level full-dummy categorical
and is not reducible to one sign; see the source-level table in §7 for its
per-level coefficients. **`BMI_before` is retained (it is part of the frozen
architecture and never removed by Ridge), but its individual contribution is
weak and directionally unstable** (54% sign consistency, near-zero median
coefficient) — this is disclosed here as a limitation, not smoothed over.

## 7. Final full-data refit (the model going forward)

Fit **once** on all **431** deliveries, using the identical frozen
architecture and tuning procedure. The penalty `C` was selected by one
canonical grouped-5-fold inner CV split of the full cohort
(`repeat=1, fold=1`, deterministic seed `42101` —
`modeling_core.inner_seed(1, 1)`, the same seed convention used inside
every outer fold in §6; there is no outer holdout left once refitting on
all data). **This refit's own training-set fit statistics are never
reported as model performance** — performance is exclusively §6 above.

Artifacts: `outputs/final_modeling/compact_ridge_lock/final_refit/{coefficients_encoded,coefficients_source_level}.csv`,
`preprocessing_spec.json`, `final_refit_manifest.json` (gitignored,
regenerable; re-run with
`python -m analysis.modeling.final_modeling.final_compact_ridge_lock --refit`).

| | |
|---|---|
| Rows used | **431 / 431** |
| Chosen penalty `C` | **0.3162** (`10^0.5`, the grid's 7th of 15 points) |
| Intercept | **−2.0476** |
| Converged | Yes (lbfgs, 15 iterations, no convergence warning) |
| Active source predictors | 6 / 6 (Ridge never zeros a coefficient exactly) |
| L2 coefficient norm | 1.4408 |

### Final coefficients (standardized-feature scale; source-predictor level)

| Source predictor | Coefficient | Direction |
|---|---:|---|
| `AGE` | +0.5414 | higher age → higher odds |
| `nulliparity` | +0.8896 | nulliparous → higher odds |
| `S_P_CS` | +0.4422 | prior cesarean → higher odds |
| `induction_any_bin` | +0.7931 | induced labor → higher odds |
| `derived_hypertension_pih_pet_spectrum = no_hypertensive_disorder` | −0.3320 | (full-dummy level; interpret jointly with the other two levels, not vs. an omitted reference) |
| `derived_hypertension_pih_pet_spectrum = pih_gestational_htn` | +0.1352 | |
| `derived_hypertension_pih_pet_spectrum = preeclampsia_spectrum` | +0.1936 | hypertensive-disease levels push toward higher odds relative to no disorder |
| `BMI_before` | −0.0282 | weak, near-null, directionally unstable across folds (§6) |

Coefficients are on the fold-safe-standardized feature scale (mean-0,
unit-variance for continuous predictors; one-hot for the categorical); they
are **not** directly interpretable as unstandardized log-odds-per-unit and
must not be exponentiated as a conventional adjusted odds ratio without
first un-standardizing, consistent with the same caution the original
freeze applies to its own coefficients (§U of `FINAL_SCIENTIFIC_FREEZE.md`).

### Reproducibility

| | |
|---|---|
| Modeling input matrix SHA-256 | `12733c8548cdda2e3c19ae563b0750ba0f41173fc93eaed730f35f2c1f8a8c69` (identical to the original freeze) |
| Candidate registry SHA-256 | `3ca23c0f9f11e340a962630c00ffa73447000e0a497975ddd79304861d1759e7` |
| Development git SHA (base) | `bb75851cf76db157a8dea3ba47878bd74958a7b6` (isolated worktree `final-model/compact-ridge-lock`, based on `origin/main`) |
| Exploratory-process branch | `exploratory/overnight-model-improvement` (commits through `cb11ed9`, pushed) |

## 8. What may be claimed

- The compact Ridge architecture (6 predictors, no `gestational_age_at_delivery_days`,
  no endometriosis-specific predictor) improves internal repeated
  grouped-CV PR-AUC, AUROC, Brier, Brier skill, log-loss, and calibration
  over the original Stage 3 / LASSO winner, on the identical cohort and CV
  structure.
- Discrimination is real and stronger than the original winner's (AUROC
  0.798 vs. 0.715).
- Calibration is materially improved and, unlike the original winner, beats
  the constant-prevalence-null Brier (Brier skill +0.130 vs. −0.045).
- Four endometriosis-focused analyses (add-on combinations, standalone
  signal recovery, standalone/stability/leave-one-out ranking of the
  well-supported representations, and clinically motivated phenotype
  aggregation over the full canonical endometriosis family) were performed
  and found no stable incremental predictive value; that negative finding is
  part of the reported science, not suppressed.
- All statements are **internal-validation-based, after exploratory model
  development on the same dataset.**

## 9. What must NOT be claimed

- ❌ externally validated / independently validated / test-set validated —
  none exists (unchanged from the original freeze; §P/§S there).
- ❌ that the internal-validation numbers in §6 are free of selection
  optimism — this architecture was itself chosen by comparing
  cross-validated performance during the exploratory phase.
- ❌ deployment-ready / a finished clinical calculator — no threshold
  policy, no decision-analytic evaluation, no sensitivity/specificity/PPV/NPV
  exists for this architecture (unchanged from §Q of the original freeze).
- ❌ that `BMI_before`'s coefficient is a stable, individually meaningful
  effect (54% sign consistency across outer folds).
- ❌ any causal interpretation of any predictor.
- ❌ that this architecture was prespecified from study inception — it was
  selected through the documented exploratory process on
  `exploratory/overnight-model-improvement`, after and using the same
  development data as the original Final-D run.
- ❌ that the endometriosis negative-incremental-value finding means
  endometriosis has no clinical relevance to this patient population —
  it is a statement about predictive modeling in this cohort, not a causal
  or clinical-significance claim.
- ❌ old numbers from the original Stage 3 / LASSO run (PR-AUC 0.272,
  AUROC 0.715, etc.) as this architecture's performance, or vice versa —
  both are reported, kept distinct, in §6's comparison table.

## 10. Relationship to `FINAL_SCIENTIFIC_FREEZE.md`

`FINAL_SCIENTIFIC_FREEZE.md` is **retained in full, unedited below its new
pointer banner**, as the accurate historical record of the original,
once-only 9-pathway Final-D scientific run (execution commit `8a06438`,
Results-closure commit `4c11f36`). Its cohort definition (§C), grouped-CV
methodology (§D), 9-pathway design (§E), winner-selection rule (§F), holdout
status (§P), and threshold status (§Q) all remain accurate and unchanged —
this document does not reopen any of them. Only the **final architecture and
winner** (§G onward of the original freeze, describing Stage 3 / LASSO) are
superseded, by this document, for the purpose of "what is the final
predictive model."

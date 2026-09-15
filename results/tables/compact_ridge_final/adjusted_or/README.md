# Adjusted Odds Ratio Analysis (Secondary, Descriptive) -- Compact Ridge Six Predictors

> **Provenance note (submission package):** retained from the canonical
> research repository's results documentation with submission-context
> annotations; scientific content unchanged. Internal
> repository paths below (`outputs/...`, `analysis/...`) refer to the
> canonical repository; the generating script and its raw-data inputs are
> not included in this submission (they require the excluded patient-level
> dataset — see the root `README.md`'s reproducibility tiers). All counts
> and tables quoted below are aggregate-level only (contingency-cell
> counts, coefficients, ORs) — no patient-level row is shown anywhere in
> this file.

## What this analysis is

A **secondary descriptive multivariable association analysis** using the
same six predictors as the final Decision 99 Compact Ridge predictive
architecture (`AGE`, `nulliparity`, `S_P_CS`, `BMI_before`,
`derived_hypertension_pih_pet_spectrum`, `induction_any_bin`), fit as one
prespecified ordinary (unpenalized) maximum-likelihood logistic regression
against `target_intrapartum_cs`, to provide clinically interpretable adjusted odds
ratios (ORs) with 95% confidence intervals. A prespecified **Firth
sensitivity analysis** (Section "Firth sensitivity analysis" below) is also
fit on the identical design, because the hypertension categories contain
genuinely sparse cells.

## What this is not

- **Not** the final predictive model. The predictive model remains the
  locked Decision 99 Compact Ridge (L2-penalized) logistic regression under
  `outputs/final_modeling/compact_ridge_lock/` -- entirely unchanged by this
  analysis.
- **Not** the source of any reported predictive performance (PR-AUC, AUROC,
  Brier, calibration) -- those figures come exclusively from the locked
  Ridge validation artifacts and are untouched here.
- **Not** a causal model.
- **Not** a replacement for Ridge, and not a re-estimate of its coefficients.
- **Not** a new variable-selection exercise -- no backward/stepwise/LASSO/
  Ridge selection was performed; all six predictors entered together in one
  prespecified model (both the MLE and the Firth sensitivity fit).
- The Firth fit is **not** a replacement for the primary MLE model, and is
  never substituted into the primary forest plot.

## Interpretation

Each adjusted OR represents the conditional association of that predictor
with intrapartum cesarean delivery, after mutual adjustment for the other
five predictor domains, within this cohort. Do not infer causality.
Wording throughout this analysis (and its outputs) is deliberately cautious:
"was associated with higher/lower odds," not "caused" / "increased the
risk" / "protective factor"; statistical significance (p < 0.05) is
reported as a diagnostic only, never as a model-selection rule.

## Data source and verification

- Canonical data source: `outputs/data_cleaning/processed/work_df_batch19_after_data_cleaning_b.xlsx`
  (sha256 `e9cd7a9a88b05c4fa135f9b74fc40ce04dfdeee822ab7473951cda5e7b68d08c`, verified against `cleaning_b_manifest.json`)
- Cohort: **431** deliveries (matches the canonical 431-row cohort;
  zero row exclusions -- Data Cleaning B's `row_exclusions_applied: false`
  invariant holds).
- Target: `target_intrapartum_cs`, distribution **370 / 61** (vaginal / intrapartum
  cesarean), verified before any analysis-specific step.
- `derived_hypertension_pih_pet_spectrum` is reconstructed here using the
  exact, already-approved EDA C formula (not re-derived/reinterpreted):
  `preeclampsia_spectrum` if `any_PET_cat=='present'` OR `SIPET==1` OR
  `HELLP==1` OR `eclampsia==1`; otherwise, when resolved, `pih_gestational_htn`
  if `PIH==1`, `no_hypertensive_disorder` if `PIH==0`; NaN when
  `any_PET_cat=='not_documented'` and none of SIPET/HELLP/eclampsia is
  positive (unresolved spectrum status) -- never guessed as level 0. Full
  value distribution: no_hypertensive_disorder=397, NaN (unresolved)=15, preeclampsia_spectrum=11, pih_gestational_htn=8. **Provenance note:** Data Cleaning B made the canonical
  treatment/representation decision for this variable family (source
  values, category definitions, "not_documented" handling); this
  reconstruction and EDA C's own feature-engineering script are both
  downstream implementations of that already-approved representation, not
  an independent missing-data-policy choice made at this stage or at EDA C.
- `BMI_before` reconstruction verified: recomputing
  `weight_before_pregnancy / (height/100)**2` independently reproduces the
  canonical `BMI_before` column exactly (max abs diff over 317
  rows with both inputs observed: 4.97e-09) with an identical
  missingness pattern -- confirming this is already the approved
  Data Cleaning B reconstruction, not a new one.
- **`BMI VECTOR MATCH: 431/431`** -- `height` and
  `weight_before_pregnancy` in this script's canonical Data Cleaning B
  source are row-identical to the same two columns in the EDA C modeling
  matrix (`outputs/eda_c/modeling_dataset_candidate_features.xlsx`) that
  actually feeds the locked Ridge final refit. Because this script
  reconstructs `BMI_before` from those columns using the literal
  `FoldSafeRecomputedBMITransformer` class the final refit uses (imported
  directly from `analysis/modeling/final_modeling/modeling_core.py`, not
  reimplemented), this confirms the reconstructed BMI vector used below is
  identical, before scaling, to the one entering the locked final refit.

## BMI_before: corrected reconstruction (was: direct median imputation)

**Prior version of this analysis incorrectly median-imputed `BMI_before`
directly.** That is NOT identical to the locked Compact Ridge full-data
final-refit preprocessing contract, which never touches `BMI_before` as a
standalone numeric column. The corrected procedure reproduces the locked
final refit exactly:

1. `height` missing values are median-imputed, with the median fit on the
   full 431-row cohort (`height` median used = **163.0000 cm**,
   68 missing values before imputation).
2. `weight_before_pregnancy` missing values are median-imputed, with the
   median fit on the full 431-row cohort (median used =
   **60.0000 kg**, 89 missing values before
   imputation).
3. `BMI_before` is recomputed from those (possibly-imputed) components:
   `weight_before_pregnancy / (height/100)**2`.
4. `BMI_before` itself is never independently median-imputed.

This is implemented by importing and reusing the literal
`FoldSafeRecomputedBMITransformer` class from
`analysis/modeling/final_modeling/modeling_core.py` -- the same class named
in `outputs/final_modeling/compact_ridge_lock/final_refit/preprocessing_spec.json`
(`"bmi_before_note"`) -- fit on the full cohort exactly as the final refit
does (`"scaling"` note: "fit on the full 431-row cohort for this final
refit"), not reimplemented from scratch. Row-by-row self-consistency was
verified: wherever `BMI_before` was originally observed (317 of 431 rows),
the reconstruction reproduces it exactly (max abs diff
4.97e-09); it differs only on the
114 rows where `BMI_before` was originally missing,
which is exactly where component-level imputation applies. `BMI_before` is
reported in original clinical units (kg/m²), not standardized -- OR is per
1 kg/m² increase.

## Variable coding and references (verified, not assumed)

| Predictor | Stored coding (verified) | Reference level used here |
|---|---|---|
| `AGE` | continuous, years, 0 missing | n/a (continuous, per 1-year OR) |
| `nulliparity` | binary; 1 = nulliparous (first delivery), 0 = prior birth; 0 missing | 0 = non-nulliparous / prior birth |
| `S_P_CS` | binary prior-cesarean indicator; 1 = prior CS, 0 = none; 0 missing | 0 = no prior cesarean |
| `BMI_before` | continuous, kg/m², reconstructed from `height`/`weight_before_pregnancy` (see above); 114 of 431 rows relied on component-level imputation | n/a (continuous, per 1 kg/m² OR) |
| `derived_hypertension_pih_pet_spectrum` | categorical, 3 levels, 15 missing (3.48%) pre-imputation | `no_hypertensive_disorder` |
| `induction_any_bin` | binary; 1 = induction, 0 = no induction; 0 missing | 0 = no induction |

## Missingness (pre-imputation), all six predictors

| Predictor | N missing | % missing |
|---|---|---|
| AGE | 0 | 0.00% |
| nulliparity | 0 | 0.00% |
| S_P_CS | 0 | 0.00% |
| BMI_before | 114 | 26.45% |
| derived_hypertension_pih_pet_spectrum | 15 | 3.48% |
| induction_any_bin | 0 | 0.00% |

`height`: 68 missing (15.78%).
`weight_before_pregnancy`: 89 missing
(20.65%). (These are `BMI_before`'s
component inputs, shown for transparency -- they are not themselves model
predictors.)

## Missing-data handling actually applied

No new missing-data policy was invented.

- `BMI_before`: see "BMI_before: corrected reconstruction" above -- the
  identical component-level strategy already used by the locked Ridge
  model's own full-data final refit, reused via the literal transformer
  class, not reimplemented or approximated.
- `derived_hypertension_pih_pet_spectrum`: 15 missing values
  (3.48%) imputed with the full-cohort mode =
  **`no_hypertensive_disorder`** -- identical to the locked Ridge final refit's own
  documented contract (`final_refit/preprocessing_spec.json`: "most-frequent
  impute (categorical) fit on the full cohort").
- No observation was excluded. Final N used in the adjusted model =
  **431** (all 431 cohort rows retained via imputation/
  reconstruction, not complete-case deletion).

### Single-imputation caveat

Predictor values reconstructed or imputed for this full-cohort secondary
analysis are treated as fixed in the ordinary MLE standard errors and
confidence intervals; therefore, the reported intervals do not propagate
uncertainty introduced by single imputation/reconstruction and should be
interpreted cautiously. This is not described as a literal mathematical
lower bound on uncertainty -- it is a known limitation of single
imputation/reconstruction treated as fixed at estimation time, common to
both the MLE and Firth fits below.

## Model specification

Ordinary (unpenalized) maximum-likelihood multivariable logistic regression
(`statsmodels` `Logit`), all six predictors entered simultaneously, no
backward/stepwise/LASSO/Ridge selection, no outcome-driven predictor
removal. Formula:

```
target_intrapartum_cs ~ AGE + nulliparity + S_P_CS + BMI_before_reconstructed
             + C(derived_hypertension_pih_pet_spectrum_imputed,
                 Treatment(reference="no_hypertensive_disorder"))
             + induction_any_bin
```

## Diagnostics / sparsity audit

- Converged: **True** (8 iterations).
- Slope parameters (excludes intercept): **7**; total
  parameters including intercept: **8**.
- Events: **61**.
- Events per parameter (excl. intercept, standard convention): **8.71**
  -- reported as a descriptive diagnostic only. EPP = 10 is not applied as a
  hard threshold; no predictor was removed because of it, per this
  analysis's prespecification.
- Events per parameter (incl. intercept): **7.62**.
- Max |coefficient| among slope terms: **2.6822**.
- Max |standard error| among slope terms: **0.8817**.
- Intercept: coefficient = -8.4314, SE =
  1.4348 (not reported as an OR / not plotted -- an
  intercept is a baseline-odds term, not a predictor association).
- Contingency zero-cell check: **none found**.
- Minimum contingency cell count across all binary/categorical predictors:
  **3** (< 5 → prespecified sparse-cell criterion
  MET -- this is what triggers the
  mandatory Firth sensitivity analysis below, independent of the zero-cell/
  large-SE separation heuristic).
- No convergence warning, no perfect/quasi-separation warning raised by the
  MLE fit.

### Contingency counts (predictor level x outcome)

**nulliparity** (rows = predictor level, cols = outcome 0/1):

```
target_intrapartum_cs    0   1
nulliparity                   
0                      184  10
1                      186  51
```

**S_P_CS** (rows = predictor level, cols = outcome 0/1):

```
target_intrapartum_cs    0   1
S_P_CS                        
0                      356  57
1                       14   4
```

**induction_any_bin** (rows = predictor level, cols = outcome 0/1):

```
target_intrapartum_cs    0   1
induction_any_bin             
0                      223  14
1                      147  47
```

**derived_hypertension_pih_pet_spectrum_imputed** (rows = predictor level, cols = outcome 0/1):

```
target_intrapartum_cs                            0   1
derived_hypertension_pih_pet_spectrum_imputed         
no_hypertensive_disorder                       358  54
pih_gestational_htn                              5   3
preeclampsia_spectrum                            7   4
```

## Firth sensitivity policy

**Firth sensitivity analysis is REQUIRED by the prespecified sparse-cell criterion (minimum contingency cell count = 3 < 5: pih_gestational_htn and preeclampsia_spectrum are both genuinely sparse) and is fit in Section 8b below. The ordinary MLE converged cleanly with no zero contingency cell and no pathologically large slope SE, so it remains the PRIMARY descriptive adjusted-association model; Firth is a sensitivity analysis only.**

## Firth sensitivity analysis

Firth (1993) bias-reduced penalized-likelihood logistic regression, fit on
the identical 431-row cohort, corrected `BMI_before` reconstruction,
seven slope parameters, and treatment/reference coding as the primary MLE
model above. No third-party Firth package (e.g. `firthlogist`) is
installable in this environment's Python version, so the standard
modified-score formulation of Firth bias-reduced logistic regression
(Heinze & Schemper 2002) is implemented directly in this script. This
implementation is numerically validated using independent general-purpose
optimization, analytic gradient checks, and deterministic synthetic tests --
not against any external Firth package (e.g. R's `logistf`/`brglm2`,
Python's `firthlogist`), none of which is installable in this environment.
That validation is version-controlled at
`analysis/reports/tests/test_firth_numerical_validation.py` (independent
scipy BFGS/Nelder-Mead refits of the identical penalized objective,
analytic-vs-finite-difference gradient agreement, and deterministic
synthetic complete-separation / null-predictor calibration checks) -- it
does not compare against, and does not claim to compare against, any
external Firth package.
Converged: **True**
(11 iterations). 95% CIs are Wald-type confidence
intervals based on the inverse expected Fisher information evaluated at the
converged Firth estimate. p-values are penalized likelihood-ratio (PLR) tests per parameter (that
parameter held at 0 within the same full-dimensional design, the rest
re-optimized, chi-square(1) reference; never a column-dropped refit, which
would change the Jeffreys-prior penalty's own dimensionality -- verified
against a null-predictor calibration check before use) -- not Wald tests on
the Firth estimate, which are known unreliable in exactly this sparse-cell
regime.

See `table_adjusted_odds_ratios_firth_sensitivity.csv` /
`table_adjusted_odds_ratios_firth_sensitivity.md` in this directory for the
complete table. No separate Firth forest plot is produced (see
"MLE vs. Firth comparison" below for why).

## MLE vs. Firth comparison

| Predictor | MLE adjusted OR | Firth adjusted OR | Direction stable? | Magnitude change (>50% relative OR)? | CI-vs-1 conclusion flip? | Verdict |
|---|---|---|---|---|---|---|
| Age (per 1-year increase) | 1.137 | 1.131 | yes | no | no | ROBUST |
| Nulliparous vs. non-nulliparous (prior birth) | 8.367 | 7.566 | yes | no | no | ROBUST |
| Prior cesarean vs. no prior cesarean | 14.617 | 13.942 | yes | no | no | ROBUST |
| Pre-pregnancy BMI (per 1 kg/m² increase) | 0.989 | 0.991 | yes | no | no | ROBUST |
| PIH / gestational hypertension vs. no hypertensive disorder | 2.151 | 2.161 | yes | no | no | ROBUST |
| Preeclampsia spectrum vs. no hypertensive disorder | 2.248 | 2.291 | yes | no | no | ROBUST |
| Labor induction vs. no induction | 6.006 | 5.665 | yes | no | no | ROBUST |

Particular attention was paid to `S_P_CS`, `pih_gestational_htn`, and
`preeclampsia_spectrum` (the two sparse hypertension categories that
triggered this sensitivity analysis). "Material" is judged from direction,
relative magnitude change, and whether the 95% CI's position relative to
OR = 1 flips -- not from p < 0.05 alone.

**Overall sensitivity verdict: `ROBUST — NO MATERIAL INTERPRETIVE CHANGE`**

## Adjusted odds ratio table (primary, MLE)

See `table_adjusted_odds_ratios.csv` / `table_adjusted_odds_ratios.md` in
this directory.

### OLD -> NEW: effect of the BMI_before correction on the primary MLE table

| Predictor | OLD adjusted OR (direct BMI median imputation) | NEW adjusted OR (corrected BMI reconstruction) | Change |
|---|---|---|---|
| Age (per 1-year increase) | 1.137 | 1.137 | -0.001 |
| Nulliparous vs. non-nulliparous (prior birth) | 8.452 | 8.367 | -0.085 |
| Prior cesarean vs. no prior cesarean | 14.514 | 14.617 | +0.102 |
| Pre-pregnancy BMI (per 1 kg/m² increase) | 0.978 | 0.989 | +0.011 |
| PIH / gestational hypertension vs. no hypertensive disorder | 2.144 | 2.151 | +0.007 |
| Preeclampsia spectrum vs. no hypertensive disorder | 2.255 | 2.248 | -0.008 |
| Labor induction vs. no induction | 6.128 | 6.006 | -0.122 |

## Forest plot

See `figure_adjusted_odds_ratios.png` / `.svg` in the sibling
`results/figures/compact_ridge_final/adjusted_or/` directory (not this
`results/tables/...` directory — see `documentation/FIGURE_TABLE_INDEX.md`
for the exact submission-relative paths). Log-scale
x-axis, vertical reference line at OR = 1, point estimates with 95% CIs,
reference categories shown explicitly, intercept excluded, no significance
stars, no causal wording. Shows the **primary MLE estimates only** -- Firth
estimates are never substituted into this plot.

## Relationship to the locked Ridge coefficients (conceptual, not statistical)

| Predictor | Ridge full-refit sign | Adjusted-OR sign | Signs agree? | Note |
|---|---|---|---|---|
| AGE | positive | positive | yes |  |
| nulliparity | positive | positive | yes |  |
| S_P_CS | positive | positive | yes |  |
| BMI_before | negative | negative | yes | Ridge outer-fold sign consistency = 0.54 (near chance); a single-fit sign match here does NOT resolve that instability. |
| induction_any_bin | positive | positive | yes |  |

Numerical equivalence with the Ridge coefficients is **not expected**:
Ridge is L2-penalized, its features are standardized and (for the
categorical predictor) full-dummy encoded with no omitted reference level,
and its coefficients were tuned via nested cross-validation for predictive
performance -- not for unbiased conditional-association estimation. This
unpenalized OR model instead uses original clinical units and explicit
reference-level (treatment) coding for exactly that estimation purpose.
`BMI_before` is specifically flagged: its Ridge full-refit coefficient sign
matches this OR model's sign in this single full-cohort fit, but Ridge's own
outer-fold sign consistency was only 0.54 (near a coin flip across the 50
locked-validation folds) -- that instability is a property of the
resampled Ridge fits and is **not resolved** by a single-fit sign match here.
This OR model's own `BMI_before` estimate is also imprecise (wide CI,
p = 0.7272),
consistent with genuine uncertainty about this predictor's association
rather than a stable effect in either direction. Disagreement between the
two models, were it to occur, would not be a reason to modify the locked
predictive architecture.

## Subject clustering

The 431 deliveries in this cohort correspond to 430 subject groups under the
canonical CV grouping definition used by the locked Compact Ridge internal
validation (`analysis/modeling/final_modeling/subject_groups.py`) -- only one
subject group contributes two delivery records; every other group
contributes exactly one. This model uses conventional independent-observation
MLE (and Firth) covariance; any impact of the single repeated subject group
is expected to be negligible in a cohort this size, and no cluster-robust
variant was fit. The primary model was not modified for clustering, per this
analysis's prespecification.

## Reproducibility

**Canonical-repository regeneration command** (not runnable from this
curated submission — the script and its raw-data inputs, including the
excluded patient-level clinical workbook, are canonical-repository inputs
not included in this package; see the root `README.md` reproducibility
tiers):

```
python analysis/reports/final_adjusted_or_analysis.py
```

This script performs no model fitting, refitting, or selection against the
predictive Compact Ridge architecture; Decision 99 and
`outputs/final_modeling/compact_ridge_lock/` are read-only inputs (for the
`FoldSafeRecomputedBMITransformer` class and the direction-comparison
section only) and are not modified.

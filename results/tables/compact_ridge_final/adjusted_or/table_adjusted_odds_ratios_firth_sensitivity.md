# Firth Logistic Regression Sensitivity Analysis

**Prespecified sparse-cell sensitivity analysis for the six Compact Ridge predictors. Not the primary adjusted-OR model (see `table_adjusted_odds_ratios.md`) and not the predictive Compact Ridge model.**

| Predictor | Comparison | Firth adjusted OR | 95% CI (Wald) | Firth coefficient | SE | p-value (PLR) | Reference |
|---|---|---|---|---|---|---|---|
| Age (per 1-year increase) | per 1-year increase | 1.131 | 1.061–1.205 | 0.1228 | 0.0323 | 0.0001 | n/a (continuous) |
| Nulliparous vs. non-nulliparous (prior birth) | nulliparous (1) vs. prior birth (0) | 7.566 | 3.131–18.284 | 2.0236 | 0.4502 | <0.0001 | 0 = non-nulliparous / prior birth |
| Prior cesarean vs. no prior cesarean | prior cesarean (1) vs. none (0) | 13.942 | 3.299–58.929 | 2.6349 | 0.7354 | 0.0008 | 0 = no prior cesarean |
| Pre-pregnancy BMI (per 1 kg/m² increase) | per 1 kg/m² increase | 0.991 | 0.932–1.054 | -0.0090 | 0.0315 | 0.7717 | n/a (continuous) |
| PIH / gestational hypertension vs. no hypertensive disorder | pih_gestational_htn vs. no_hypertensive_disorder | 2.161 | 0.389–11.991 | 0.7704 | 0.8744 | 0.3602 | no_hypertensive_disorder |
| Preeclampsia spectrum vs. no hypertensive disorder | preeclampsia_spectrum vs. no_hypertensive_disorder | 2.291 | 0.576–9.122 | 0.8291 | 0.7049 | 0.2343 | no_hypertensive_disorder |
| Labor induction vs. no induction | induction (1) vs. none (0) | 5.665 | 2.762–11.619 | 1.7343 | 0.3665 | <0.0001 | 0 = no induction |

Firth (1993) bias-reduced penalized-likelihood logistic regression; same 431-row cohort, same 61-event outcome, same seven slope parameters, same treatment/reference coding as the primary MLE model. 95% CI = Wald-type confidence interval based on the inverse expected Fisher information evaluated at the converged Firth estimate. p-value = penalized likelihood-ratio (PLR) test (2x log-likelihood difference vs. the model refit with that parameter fixed at 0, chi-square(1)) -- not a Wald test on the Firth estimate, which is unreliable in exactly this sparse-cell regime.

> This is a prespecified SENSITIVITY analysis, triggered by genuine small-cell sparsity in the hypertension categories (pih_gestational_htn: n=8, 3 events; preeclampsia_spectrum: n=11, 4 events). It does not replace the ordinary MLE as the primary adjusted-association model. Do not infer causality from these odds ratios.

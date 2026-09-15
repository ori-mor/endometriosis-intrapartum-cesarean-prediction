# Adjusted Odds Ratios: Six Compact Ridge Predictors

**Primary adjusted-association analysis, secondary to the predictive Compact Ridge model.** See `table_adjusted_odds_ratios_firth_sensitivity.md` for the prespecified Firth sparse-cell sensitivity analysis.

| Predictor | Comparison | Adjusted OR | 95% CI | Coefficient | SE | p-value | Reference |
|---|---|---|---|---|---|---|---|
| Age (per 1-year increase) | per 1-year increase | 1.137 | 1.065–1.212 | 0.1279 | 0.0329 | 0.0001 | n/a (continuous) |
| Nulliparous vs. non-nulliparous (prior birth) | nulliparous (1) vs. prior birth (0) | 8.367 | 3.331–21.017 | 2.1244 | 0.4699 | <0.0001 | 0 = non-nulliparous / prior birth |
| Prior cesarean vs. no prior cesarean | prior cesarean (1) vs. none (0) | 14.617 | 3.296–64.812 | 2.6822 | 0.7599 | 0.0004 | 0 = no prior cesarean |
| Pre-pregnancy BMI (per 1 kg/m² increase) | per 1 kg/m² increase | 0.989 | 0.929–1.053 | -0.0111 | 0.0320 | 0.7272 | n/a (continuous) |
| PIH / gestational hypertension vs. no hypertensive disorder | pih_gestational_htn vs. no_hypertensive_disorder | 2.151 | 0.382–12.108 | 0.7658 | 0.8817 | 0.3851 | no_hypertensive_disorder |
| Preeclampsia spectrum vs. no hypertensive disorder | preeclampsia_spectrum vs. no_hypertensive_disorder | 2.248 | 0.557–9.072 | 0.8099 | 0.7119 | 0.2553 | no_hypertensive_disorder |
| Labor induction vs. no induction | induction (1) vs. none (0) | 6.006 | 2.873–12.557 | 1.7928 | 0.3763 | <0.0001 | 0 = no induction |

Source variable names (source-level, matching the locked Ridge frozen-predictor list): AGE, BMI_before, S_P_CS, derived_hypertension_pih_pet_spectrum, induction_any_bin, nulliparity.

Ordinary (unpenalized) maximum-likelihood multivariable logistic regression; all six predictors entered together (n = 431, 61 events). AOR = exp(coefficient); 95% CI = exp(Wald confidence interval on the coefficient). `BMI_before` uses the corrected component-level reconstruction (see README) -- not direct median imputation.

> This is a secondary, prespecified descriptive association analysis. It is not the predictive Compact Ridge model, not a causal model, and not a variable-selection exercise. Do not infer causality from these odds ratios.

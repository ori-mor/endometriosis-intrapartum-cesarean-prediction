# Final Compact Ridge Coefficients (Full 431-Row Data Refit)

| Predictor | Level | Ridge coefficient (standardized scale) | Direction | Outer-fold median | Outer-fold IQR | Sign consistency (50 folds) | Stability |
|---|---|---|---|---|---|---|---|
| AGE | (continuous/binary) | 0.5414 | positive | 0.4790 | 0.0854 | 1.00 | stable |
| nulliparity | (continuous/binary) | 0.8896 | positive | 0.7391 | 0.1425 | 1.00 | stable |
| S_P_CS | (continuous/binary) | 0.4422 | positive | 0.3439 | 0.1386 | 1.00 | stable |
| induction_any_bin | (continuous/binary) | 0.7931 | positive | 0.7075 | 0.0914 | 1.00 | stable |
| derived_hypertension_pih_pet_spectrum | no_hypertensive_disorder | -0.3320 | negative | n/a | n/a | n/a | not available (categorical level; stability tracked at the source-predictor level only) |
| derived_hypertension_pih_pet_spectrum | pih_gestational_htn | 0.1352 | positive | n/a | n/a | n/a | not available (categorical level; stability tracked at the source-predictor level only) |
| derived_hypertension_pih_pet_spectrum | preeclampsia_spectrum | 0.1936 | positive | n/a | n/a | n/a | not available (categorical level; stability tracked at the source-predictor level only) |
| BMI_before | (continuous/binary) | -0.0282 | negative | -0.0152 | 0.0981 | 0.54 | UNSTABLE (directional sign flips across outer folds) |

Source: `outputs/final_modeling/compact_ridge_lock/final_refit/coefficients_source_level.csv` and `coefficients_encoded.csv` (full 431-row final refit, C=0.3162, intercept=-2.0476), cross-referenced with `outputs/final_modeling/compact_ridge_lock/report/coefficient_stability.csv` (sign/magnitude stability across the 50 locked-validation outer folds).

`derived_hypertension_pih_pet_spectrum` uses full-dummy (non-reference) one-hot encoding for this penalized model, per `final_refit/preprocessing_spec.json` (`"categorical_encoding": "OneHotEncoder(handle_unknown='ignore') ... full-dummy, penalized model -- not reference/drop-first coding"`); each level's coefficient is not relative to an omitted reference category. Coefficient-stability tracking (`coefficient_stability.csv`) is reported at the source-predictor level only and does not include per-level stability for this categorical predictor.

**`BMI_before` is flagged as directionally unstable**: its sign consistency across the 50 outer validation folds is 0.54 (i.e., close to a coin flip), versus 1.00 for every other continuous/binary predictor in the frozen set. Its full-refit coefficient sign should not be over-interpreted.

> Ridge coefficients are penalized coefficients on the standardized/encoded modeling scale and are not conventional adjusted odds ratios.

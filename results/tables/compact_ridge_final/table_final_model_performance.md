# Final Compact Ridge Model Performance Under Repeated Subject-Grouped Internal Validation

| Metric | Compact Ridge (current, locked) | Historical Stage 3 / LASSO baseline |
|---|---|---|
| PR-AUC | 0.348 (SD 0.015) | 0.272 (SD 0.018) |
| AUROC | 0.798 (SD 0.011) | 0.715 (SD 0.029) |
| Brier score | 0.106 (SD 0.001) | 0.127 (SD 0.014) |
| Brier skill score | 0.130 (SD 0.012) | -0.045 (SD 0.114) |
| Log-loss | 0.337 (SD 0.005) | 0.421 (SD 0.070) |
| Calibration intercept | 0.162 (SD 0.096) | -0.689 (SD 0.667) |
| Calibration slope | 1.115 (SD 0.066) | 0.660 (SD 0.347) |

Values are locked repeat-level means (10 repeats x 5 outer folds = 50/50 successful folds, 0 failures) from `outputs/final_modeling/compact_ridge_lock/report/locked_validation_manifest.json`. SD = standard deviation across the 10 outer-CV repeats.

**Historical Stage 3 / LASSO baseline** is the previously locked, now-superseded architecture (Decision 99 superseded it). It is shown here only as a contextual historical comparator and is **not** a current candidate model.

> Performance represents internal repeated subject-grouped cross-validation after exploratory model development on the same dataset; it is not independent or external validation.

# Figure generation metadata (Compact Ridge locked results)

> **Provenance note (submission package):** the source path below
> (`outputs/final_modeling/compact_ridge_lock/...`) is a canonical-repository
> path. The row-level file it names,
> `locked_validation_oof_predictions.csv`, is a deliberately excluded,
> patient-level artifact and is **not** part of this submission — see the
> root `README.md` reproducibility tiers and `SUBMISSION_MANIFEST.md`. This
> document describes how the three figures in this submission's
> `results/figures/compact_ridge_final/` were originally generated; it is
> not a claim that the source file is included here.
>
> **Rendering-metadata note:** the PNG/SVG files for these three figures
> embed `Matplotlib 3.10.9` (Matplotlib's own auto-generated file metadata),
> while `documentation/environment/ENVIRONMENT_FREEZE.md`'s frozen
> environment table lists `matplotlib 3.10.0`. This reflects which
> Matplotlib patch version rendered the file, not the environment that
> computed the underlying statistics — the plotted curves and annotated
> values are the already-locked `repeat_level`/`locked_validation_manifest.json`
> numbers described below, not something Matplotlib itself calculates.
> Disclosed rather than silently reconciled; the figures were not
> regenerated to force metadata agreement.

Source data: `outputs/final_modeling/compact_ridge_lock/report/locked_validation_oof_predictions.csv`
(4,310 rows = 431 deliveries x 10 repeated-CV repeats; 50/50 outer folds, 0 failures).

Repeated-CV handling philosophy: each delivery contributes one out-of-fold prediction
per repeat (10 total), so the 4,310 rows are NOT 4,310 independent patients. All three
figures below compute a curve/summary **separately within each of the 10 repeats**
(431 predictions each), display those 10 repeat-level curves lightly (alpha=0.16),
and overlay one bold **aggregate curve** obtained by simple, unweighted averaging across
repeats on a common grid. No new confidence intervals were computed; only the locked
repeat-level mean/SD already present in `locked_validation_manifest.json` are annotated.

## Precision-Recall (figure_compact_ridge_precision_recall)
- Per repeat: `sklearn.metrics.precision_recall_curve(y_true, predicted_probability)`.
- Aggregate curve: each repeat's precision is linearly interpolated onto a common
  201-point recall grid (0 to 1); the aggregate curve is the pointwise mean across
  the 10 repeats ("vertical averaging").
- No-skill reference line = empirical prevalence = 61/431 = 0.1415.
- Annotated mean PR-AUC is the locked `repeat_level.mean_pr_auc` value (fold-level PR-AUC
  averaged per repeat, then averaged across repeats) — not recomputed from the plotted curve.

## ROC (figure_compact_ridge_roc)
- Per repeat: `sklearn.metrics.roc_curve(y_true, predicted_probability)`.
- Aggregate curve: each repeat's TPR is linearly interpolated onto a common 201-point
  FPR grid (0 to 1); the aggregate curve is the pointwise mean across the 10 repeats
  (the standard repeated/cross-validated mean-ROC recipe).
- Annotated mean AUROC is the locked `repeat_level.mean_auroc` value.

## Calibration (figure_compact_ridge_calibration)
- Per repeat: predictions sorted and split into 8 equal-frequency (quantile) bins
  (~53 deliveries/bin/repeat); bin points are
  (mean predicted probability, observed event frequency).
- 8 bins were chosen (not deciles) specifically to avoid very-low-event bins,
  given only 61 events per repeat (14.2% prevalence).
- Aggregate curve: bin-index-wise mean of (mean predicted, mean observed) across the
  10 repeats.
- Annotated intercept/slope/Brier/Brier-skill are the locked `repeat_level` values
  (each repeat's calibration intercept/slope was fit via logistic recalibration on
  that repeat's 431 OOF predictions in the original locked run; those 10 per-repeat
  values were then averaged) — not refit here.

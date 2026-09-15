#!/usr/bin/env python3
"""Compact Ridge presentation notebook -- Part 5: limitations, provenance,
and an explicit restatement of this notebook's scope boundaries.
"""


def _src(text):
    lines = text.lstrip("\n").splitlines(keepends=True)
    if lines and lines[-1].endswith("\n"):
        lines[-1] = lines[-1][:-1]
    return lines


def md(cid, text):
    return {"id": cid, "cell_type": "markdown", "metadata": {}, "source": _src(text)}


def code(cid, text):
    return {"id": cid, "cell_type": "code", "metadata": {}, "source": _src(text),
            "outputs": [], "execution_count": None}


PART5_CELLS = [
    md("crp-p16-limitations", """
---
## D6 -- Limitations

* **Internal validation only.** Reported performance is repeated
  subject-grouped cross-validation performed *after* exploratory model
  development on this same development dataset -- not an independent test
  set, not external validation.
* **No hold-out.** The historical EDA D hold-out's row-level membership is
  unrecoverable after the 447 -> 431 cohort transition and is, by locked
  policy, never reconstructed or accessed. This model was never evaluated
  against any hold-out.
* **No endometriosis-specific predictor.** The completed exploratory
  endometriosis analyses (add-on, signal-recovery, feature-profiling,
  phenotype-aggregation, all on `exploratory/overnight-model-improvement`)
  found no stable incremental predictive value from any measured
  endometriosis phenotype/severity/surgical-history variable beyond the
  frozen obstetric core. That negative finding is retained as part of the
  scientific record, not overridden.
* **`BMI_before` coefficient instability.** Sign consistency 0.54 across the
  50 outer validation folds (vs. 1.00 for every other continuous/binary
  predictor) -- its full-refit coefficient direction should not be
  over-interpreted.
* **Ridge coefficients are not odds ratios.** D4's Ridge coefficient table
  reports penalized coefficients on the standardized/encoded scale; the
  separate adjusted-OR table is a secondary, prespecified descriptive
  association analysis, not a causal model.
"""),
    code("crp-p17-provenance", """
reproducibility = final_refit_manifest.get("reproducibility", {})
print("Reproducibility manifest (from final_refit_manifest.json):")
for key, value in reproducibility.items():
    print(f"  {key}: {value}")
"""),
    md("crp-p18-provenance-sources", """
## D7 -- Provenance

Sources marked *(canonical only)* are not included in this submission
package; see the root `README.md` and `SUBMISSION_MANIFEST.md` for the
reproducibility tier this implies.

| | |
|---|---|
| Frozen architecture + validation + refit | `analysis/modeling/final_modeling/final_compact_ridge_lock.py` *(canonical only)* |
| Publication tables/figures generator | `analysis/reports/compact_ridge_final_outputs.py` *(canonical only)* |
| Scientific summary (current final architecture) | `documentation/COMPACT_RIDGE_FINAL_LOCK.md` (included in this submission) |
| Decision record | Decision 99, `docs/clinical_decisions/manual_decisions_log.md` *(canonical only)* |
| Repository index entry | `docs/finalization/FINAL_PROJECT_INDEX.md` §6b/§7b *(canonical only)* |
| Historical superseded winner (Stage 3 / LASSO) | `docs/finalization/FINAL_SCIENTIFIC_FREEZE.md` *(canonical only)* |

## D8 -- What this notebook does NOT do

* No new model selection, predictor search, or estimator comparison.
* No change to predictors, preprocessing, hyperparameters, or CV design.
* No new cross-validation, refit, or bootstrap.
* No hold-out access of any kind.
* No new scientific or clinical decision.

Every table and figure above is a read-only view of artifacts already
produced by the canonical scripts in D7.
"""),
]

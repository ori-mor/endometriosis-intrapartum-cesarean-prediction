#!/usr/bin/env python3
"""Compact Ridge presentation notebook -- Part 1: purpose, contract, and
locked-artifact integrity check.

This notebook DOCUMENTS and SURFACES the already-locked Decision 99 Compact
Ridge final model. It performs no model fitting, no predictor search, no
hyperparameter search, no new cross-validation, and never accesses any
hold-out.
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


PART1_CELLS = [
    md("crp-p1-title", """
# Final Compact Ridge Model -- Presentation (Decision 99, LOCKED)

**Status: CURRENT final architecture, LOCKED.** This notebook is a
**presentation / reproducibility layer only** for the already-locked Compact
Ridge model. It surfaces existing canonical outputs -- it does not produce
any new scientific result.

This notebook does **not**:

* perform new model selection, predictor search, or estimator comparison,
* change predictors, preprocessing, hyperparameters, or CV design,
* run any new cross-validation or refit,
* read, create, or evaluate any hold-out,
* generate any new scientific decision.

Every number, table, and figure below is read directly from artifacts
already produced and verified by the canonical scripts listed in D2.
"""),
    md("crp-p2-frozen-architecture", """
## D1 -- Frozen architecture (Decision 99)

| | |
|---|---|
| Predictors (6) | `AGE`, `nulliparity`, `S_P_CS`, `BMI_before`, `derived_hypertension_pih_pet_spectrum`, `induction_any_bin` |
| Estimator | L2 (Ridge) logistic regression |
| Selection rule | PR-AUC one-SE band -> lowest inner Brier -> smallest C |
| Endometriosis predictor | None -- the completed exploratory endometriosis analyses found no stable incremental value; that negative result is retained, not overridden |
| `gestational_age_at_delivery_days` | Not included |

## D2 -- Canonical sources (this notebook reads curated outputs of these only)

This curated submission does not include the executable source of the lock
script or the publication-outputs generator below -- only their already-
generated aggregate result artifacts, under `results/` in this package. The
canonical sources are listed for provenance; they are not present in this
submission.

| Layer | Canonical source (canonical repository only -- not included here) |
|---|---|
| Lock / validation / refit | `analysis/modeling/final_modeling/final_compact_ridge_lock.py` |
| Publication tables/figures | `analysis/reports/compact_ridge_final_outputs.py` |
| Scientific summary | `docs/finalization/COMPACT_RIDGE_FINAL_LOCK.md` (curated copy included in this submission at `documentation/COMPACT_RIDGE_FINAL_LOCK.md`) |
| Decision record | Decision 99, `docs/clinical_decisions/manual_decisions_log.md` |

**Caveat carried through every section below:** these results are internal
repeated subject-grouped cross-validation performed *after* exploratory
model development on the same dataset -- not independent or external
validation.
"""),
    code("crp-p3-load-manifests", """
import json
from pathlib import Path

import pandas as pd

# Submission-relative root resolution: walk upward from the notebook's
# working directory until a directory containing both results/ and
# notebooks/ subdirectories is found. This package has no CLAUDE.md (that
# is a canonical-repository-only marker), so root detection uses the
# submission's own known top-level structure instead.
PROJECT_ROOT = Path.cwd()
while not ((PROJECT_ROOT / "results").is_dir() and (PROJECT_ROOT / "notebooks").is_dir()) and PROJECT_ROOT.parent != PROJECT_ROOT:
    PROJECT_ROOT = PROJECT_ROOT.parent

REPORT_DIR = PROJECT_ROOT / "results" / "tables" / "reproducibility"
REFIT_DIR = REPORT_DIR
RESULTS_DIR = PROJECT_ROOT / "results" / "tables" / "compact_ridge_final"
FIGURES_DIR = PROJECT_ROOT / "results" / "figures" / "compact_ridge_final"

locked_validation_manifest = json.loads((REPORT_DIR / "locked_validation_manifest.json").read_text(encoding="utf-8"))
final_refit_manifest = json.loads((REFIT_DIR / "final_refit_manifest.json").read_text(encoding="utf-8"))

# Read-only integrity check against the already-locked artifacts -- no new
# computation, only confirming the frozen numbers this notebook will display.
assert locked_validation_manifest["n_folds_ok"] == 50
assert locked_validation_manifest["n_folds_total"] == 50
assert locked_validation_manifest["n_rows"] == 431
assert final_refit_manifest["n_rows_used"] == 431
assert final_refit_manifest["converged"] is True
assert tuple(final_refit_manifest["frozen_predictors"]) == (
    "AGE", "nulliparity", "S_P_CS", "BMI_before",
    "derived_hypertension_pih_pet_spectrum", "induction_any_bin",
)

print("Locked internal-validation run: "
      f"{locked_validation_manifest['n_folds_ok']}/{locked_validation_manifest['n_folds_total']} outer folds OK, "
      f"n_rows={locked_validation_manifest['n_rows']}")
print("Final full-data refit: "
      f"n_rows_used={final_refit_manifest['n_rows_used']}, "
      f"chosen_C={final_refit_manifest['chosen_C']:.4f}, "
      f"intercept={final_refit_manifest['intercept']:.4f}, "
      f"converged={final_refit_manifest['converged']}")
"""),
]

#!/usr/bin/env python3
"""Compact Ridge presentation notebook -- Part 4: calibration/discrimination
figures and outer-fold coefficient-stability diagnostics.

Displays only already-generated figures and diagnostic tables -- no new
plotting logic, no new statistics.
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


PART4_CELLS = [
    md("crp-p12-header", """
---
## D5 -- Calibration, discrimination, and coefficient stability

The three figures below are already-generated read-only artifacts,
originally produced by `analysis/reports/compact_ridge_final_outputs.py`
in the canonical repository (not included in this submission) and included
here as curated files at `results/figures/compact_ridge_final/`, aggregated
exactly per `figures_metadata.md` in that directory. They are displayed
here, not regenerated.
"""),
    code("crp-p13-figures", """
from IPython.display import Image, display

for fig_name in (
    "figure_compact_ridge_roc.png",
    "figure_compact_ridge_precision_recall.png",
    "figure_compact_ridge_calibration.png",
):
    display(Image(filename=str(FIGURES_DIR / fig_name)))
"""),
    md("crp-p14-stability-header", """
### Outer-fold coefficient stability (50 outer refits)

Sign consistency and coefficient spread for each frozen predictor across the
50 locked-validation outer folds --
`results/tables/reproducibility/coefficient_stability.csv`.
`BMI_before`'s sign consistency of 0.54 (vs. 1.00 for every other
continuous/binary predictor) is the basis for its "unstable" flag in D4.
"""),
    code("crp-p15-stability-table", """
coefficient_stability = pd.read_csv(REPORT_DIR / "coefficient_stability.csv")
coefficient_stability
"""),
]

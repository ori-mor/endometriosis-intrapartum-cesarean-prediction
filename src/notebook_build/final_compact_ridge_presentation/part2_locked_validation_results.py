#!/usr/bin/env python3
"""Compact Ridge presentation notebook -- Part 2: locked internal-validation
performance (repeated subject-grouped nested CV).

Reads only the already-locked/aggregated performance tables -- no new
cross-validation, no new metric computation.
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


PART2_CELLS = [
    md("crp-p4-header", """
---
## D3 -- Locked internal-validation performance

Repeated 10x5 subject-grouped outer CV (50 outer folds, 0 failures). These
are the FINAL reported model-performance numbers -- read directly from
`results/tables/compact_ridge_final/table_final_model_performance.csv`
(itself built read-only from `locked_validation_manifest.json`).

The historical Stage 3 / LASSO row is the previously locked, now-superseded
architecture (Decision 99 superseded it) -- shown only as a contextual
historical comparator, not a current candidate model.
"""),
    code("crp-p5-performance-table", """
performance_table = pd.read_csv(RESULTS_DIR / "table_final_model_performance.csv")
performance_table
"""),
    md("crp-p6-repeat-level-header", """
### Repeat-level detail (10 outer-CV repeats)

The table above reports the mean/SD across the 10 repeats shown here in
full, straight from the locked manifest's per-repeat aggregation --
`results/tables/reproducibility/repeat_level_metrics.csv`.
"""),
    code("crp-p7-repeat-level-table", """
repeat_level_metrics = pd.read_csv(REPORT_DIR / "repeat_level_metrics.csv")
repeat_level_metrics
"""),
]

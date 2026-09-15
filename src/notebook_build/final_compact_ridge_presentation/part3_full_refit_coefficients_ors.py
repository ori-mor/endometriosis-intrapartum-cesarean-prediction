#!/usr/bin/env python3
"""Compact Ridge presentation notebook -- Part 3: full-data refit
coefficients and the secondary adjusted-odds-ratio association analysis.

Reads only already-generated coefficient/OR tables -- no new fitting.
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


PART3_CELLS = [
    md("crp-p8-header", """
---
## D4 -- Full-data refit: coefficients and adjusted odds ratios

The frozen architecture is refit ONCE on all 431 deliveries (same tuning
procedure, one canonical grouped inner split). Its own training-set fit
statistics are never reported as model performance -- only Part D3's
repeated-CV numbers are. These are penalized Ridge coefficients on the
standardized/encoded modeling scale, **not** conventional adjusted odds
ratios.

`BMI_before` is flagged as directionally unstable (sign consistency 0.54
across the 50 outer validation folds, vs. 1.00 for every other
continuous/binary predictor) -- its full-refit coefficient sign should not
be over-interpreted.
"""),
    code("crp-p9-coefficients-table", """
ridge_coefficients_table = pd.read_csv(RESULTS_DIR / "table_final_ridge_coefficients.csv")
ridge_coefficients_table
"""),
    md("crp-p10-or-header", """
### Secondary analysis: adjusted odds ratios

A separate, prespecified descriptive association analysis -- ordinary
(unpenalized) multivariable logistic regression on the same six frozen
predictors, entered together. **This is not the predictive Compact Ridge
model, not a causal model, and not a variable-selection exercise.** Source:
`results/tables/compact_ridge_final/adjusted_or/table_adjusted_odds_ratios.csv`.
"""),
    code("crp-p11-or-table", """
adjusted_or_table = pd.read_csv(RESULTS_DIR / "adjusted_or" / "table_adjusted_odds_ratios.csv")
adjusted_or_table
"""),
]

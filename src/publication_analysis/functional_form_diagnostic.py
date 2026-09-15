"""Functional-form diagnostic for the 11 CONTINUOUS/COUNT predictors whose
reporting unit is approved but whose LINEAR log-odds functional form is a
separate, still-pending decision (Representation Sign-off + Functional-Form
Gate task, Sections 8-13; corrected per the Functional-Form Methodological
Correction pass).

APPROVING A REPORTING UNIT IS NOT THE SAME AS PROVING THAT THE CONTINUOUS
PREDICTOR HAS A LINEAR LOG-ODDS RELATIONSHIP. This module produces evidence
for MANUAL/independent review -- it never automatically decides a final
functional form, never chooses cutpoints from outcome p-values, never
alters the predictive pipeline, and never writes outside
``outputs/publication_analysis/``.

This is the ONLY module in the publication-analysis package authorized to
fit real-patient-level models, and only for these 11 predictors' functional
form (never a full 81-predictor real-data run, never adjusted models).

DATA-INFORMED DIAGNOSTIC -- NOT PROSPECTIVELY PRESPECIFIED
------------------------------------------------------------
The approved reporting UNITS (Section 3 of the Representation Sign-off
task) were selected on clinical/methodological grounds -- native/
conventional clinical units and conventional scaling factors -- independent
of any outcome association. The functional-FORM diagnostic below, by
contrast, necessarily uses the study outcome (it fits ``target_intrapartum_
cs`` against each predictor) and is therefore a POST-HOC, DATA-INFORMED
EXPLORATORY diagnostic, not a prospectively prespecified test. Its result
must never be described as confirmatory. No outcome-derived cutpoint is
ever created by this module. The final functional-form decision for each
predictor is made MANUALLY, weighing: the robust Wald evidence below, the
plotted curve shape, the amount of data support at each part of the range,
clinical plausibility, and parsimony -- not a mechanical p-value rule. Any
inferential p-value eventually reported for these predictors in Table 2
remains exploratory and must be interpreted in light of this data-informed
functional-form review process, not as an independent confirmatory result.

Methodological correction from the prior version of this module
------------------------------------------------------------------
The previous version compared linear vs. flexible fits using
``2 * (flexible_llf - linear_llf)`` referred to a chi-square distribution
(a "likelihood-ratio" style diagnostic), then applied an automated
``p < 0.05`` decision rule. Both are now REMOVED:

1. ``.llf`` (and the fitted coefficients) in a statsmodels ``Logit`` fit are
   determined by ordinary maximum likelihood and are UNCHANGED by
   ``cov_type`` -- verified empirically (see the correction-pass audit and
   ``tests/test_functional_form_diagnostic.py``). The former LR-style
   p-value therefore silently ignored the Checkpoint-A subject-cluster
   structure entirely, even though the same fitted objects also carried
   cluster-robust standard errors for other purposes.
2. An automated ``p < 0.05`` -> flag / else -> supports-linear split is
   exactly the kind of mechanical functional-form gate the task brief
   explicitly warns against.

The corrected diagnostic instead performs a genuine CLUSTER-ROBUST WALD
TEST of the null hypothesis that the flexible model's fitted function lies
in the ordinary linear subspace (intercept + beta*x), using the flexible
model's own cluster-robust covariance matrix -- see
``_nested_restriction_matrix`` / ``_cluster_robust_wald_linearity_test``.
The test's p-value is reported as ONE piece of evidence among several
(alongside descriptive curve-difference metrics and the plotted shape) and
is never, by itself, mapped to an automated linear/nonlinear verdict: every
estimable predictor is instead assigned the neutral
``AWAITING_MANUAL_FUNCTIONAL_FORM_DECISION`` status.

Diagnostic method
------------------
- LINEAR: a dedicated cluster-robust logistic fit on the raw (native-unit)
  predictor, keeping the actual fitted statsmodels result object so that
  plotted/reported predictions come directly from ``result.predict(...)``-
  equivalent computation -- never a manually reconstructed intercept.
- FLEXIBLE (continuous predictors): a low-complexity natural/restricted
  cubic spline (``patsy.cr(x, df=SPLINE_DF, constraints="center")``), fit
  with the same subject-cluster-robust covariance. Knot placement is
  patsy's own deterministic quantile algorithm for ``cr()`` -- never
  data-mined, never outcome-informed. ``SPLINE_DF`` is a small fixed
  constant, not tuned per variable. NONLINEARITY EVIDENCE for these is a
  cluster-robust Wald test of the linear restriction, obtained by
  (a) verifying numerically that the linear design ``Z = [1, x]`` is nested
  inside the flexible design's column space (least-squares reconstruction,
  fail-loud above a strict tolerance), (b) constructing a restriction matrix
  ``R`` spanning the orthogonal complement of that nested subspace
  (``scipy.linalg.null_space``), and (c) calling the flexible model's own
  ``wald_test(R)`` (df=2: intercept+slope).
- FLEXIBLE (count predictors) -- CORRECTED (Count Functional-Form Low-DF
  Correction pass): a single PREDEFINED low-df quadratic,
  ``outcome ~ x + x_squared`` (``x_squared = x ** 2`` on the native count),
  NOT a saturated one-dummy-coefficient-per-observed-value categorical
  model. The prior categorical version produced unreliable, wildly inflated
  Wald evidence for G and LIVE_BIRTH: their sparse/singleton high-count
  levels (e.g. G=9, G=10, LIVE_BIRTH=5, each n=1 with zero events) drove
  individual dummy coefficients to quasi-complete-separation magnitudes
  (~-48 on the log-odds scale) that the shared large-SE separation
  heuristic did not reliably flag (the reported standard errors stayed
  numerically small even though the coefficients were clearly at a
  separation boundary), so the resulting omnibus/nested-subspace Wald
  statistics for G/LIVE_BIRTH were themselves numerical artifacts, not
  genuine nonlinearity evidence. A fixed 1-extra-parameter quadratic cannot
  exhibit that failure mode the same way. NONLINEARITY EVIDENCE for count
  predictors is a cluster-robust Wald test of exactly ONE restriction,
  H0: beta_x_squared = 0 (df=1 always), via
  ``cluster_robust_wald_quadratic_term``.
- Both continuous and count NONLINEARITY EVIDENCE are reported alongside
  purely DESCRIPTIVE curve-difference metrics (max/mean absolute predicted-
  probability difference between the linear and flexible curves, evaluated
  over the observed central range for continuous predictors and at every
  OBSERVED count value -- never extrapolated -- for count predictors) --
  descriptive evidence only, never converted into a clinical "meaningful
  curvature" threshold.
- SPARSITY DISCLOSURE (count predictors only): ``sparse_tail_present`` is a
  TARGET-INDEPENDENT flag (based only on row counts, via
  ``SPARSE_TAIL_MIN_ROWS`` -- never on outcome/event rate) alongside
  separate ``any_level_zero_events`` / ``any_level_zero_non_events`` flags.
  This is descriptive separation-risk disclosure only -- it is never used to
  merge, drop, or collapse an observed count value; every value keeps its
  own row in ``count_value_support_table`` regardless.
"""
from __future__ import annotations

from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")  # headless-safe; publication_exports.py controls actual file writes
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from patsy import dmatrix
from scipy.linalg import null_space

from publication_analysis.univariable_analysis import (
    FIT_OK,
    _fit_logit,  # reuse the same separation/convergence detection as the rest of the package
)

# --- scope: the exact 11 predictors this diagnostic covers, never more -----
CONTINUOUS_PREDICTORS = [
    "AGE", "BMI_before", "height", "weight_before_pregnancy", "Hb_before_delivery",
    "gestational_age_at_delivery_days",
]
COUNT_PREDICTORS = ["P", "G", "CS", "LIVE_BIRTH", "AB"]

# Reporting-unit label, matching the representation contract exactly
# (Representation Sign-off task Section 3) -- duplicated here as a plain
# constant so this diagnostic module has no import-time dependency on the
# representation-contract module's real-registry read. NOTE: the robust-
# Wald/plotting machinery below operates on the RAW native-unit predictor
# throughout (a linear reparametrization by unit_scale does not change
# whether a function lies in the linear subspace, so the Wald test is scale-
# invariant); reporting_unit is display metadata only here.
REPORTING_UNIT = {
    "AGE": "1 year",
    "BMI_before": "1 kg/m^2",
    "height": "5 cm",
    "weight_before_pregnancy": "5 kg",
    "Hb_before_delivery": "1 g/dL",
    "gestational_age_at_delivery_days": "1 week (7 days)",
}

# Low, fixed spline complexity -- deliberately NOT tuned per variable, and
# never chosen from an outcome p-value. df=3 (natural cubic spline via
# patsy's cr()) gives 3 spline coefficients + intercept = 4 parameters,
# conservative relative to 61 total target events across the whole cohort.
SPLINE_DF = 3

# Strict numerical tolerance for verifying the linear design Z is nested
# inside the flexible design's column space (relative Frobenius-norm
# reconstruction error). Fails loud (raises) above this, rather than
# silently proceeding with an invalid restriction matrix.
NESTED_SUBSPACE_RELATIVE_TOLERANCE = 1e-6

# --- neutral, non-automated status vocabulary for the diagnostic CSV -------
# No REVIEW_SUPPORTS_LINEAR / REVIEW_FLAGS_NONLINEARITY: the corrected
# diagnostic never maps its evidence to an automated linear/nonlinear
# verdict. This vocabulary is intentionally distinct from (and never
# auto-written back into) the representation contract's own
# functional_form_status field, which stays PENDING_FUNCTIONAL_FORM_REVIEW.
AWAITING_MANUAL_DECISION = "AWAITING_MANUAL_FUNCTIONAL_FORM_DECISION"
REVIEW_INSUFFICIENT_INFO = "INSUFFICIENT_INFORMATION_FOR_FORM_REVIEW"

FUNCTIONAL_FORM_REVIEW_COLUMNS = [
    "predictor",
    "physical_type",
    "reporting_unit",
    "analysis_N",
    "events",
    "non_events",
    "unique_subjects",
    "n_unique_values",
    "diagnostic_method",
    "linear_fit_status",
    "flexible_fit_status",
    "robust_wald_stat",
    "robust_wald_df",
    "robust_wald_p",
    "curve_max_abs_probability_difference",
    "curve_mean_abs_probability_difference",
    "central_range_q05",
    "central_range_q95",
    "sparse_tail_present",
    "any_level_zero_events",
    "any_level_zero_non_events",
    "functional_form_status",
    "review_note",
]

# Target-independent sparsity rule (Count Functional-Form Low-DF Correction
# task, Section 8): a count value is flagged as part of the "sparse tail" if
# it has fewer than this many ROWS -- never based on outcome/event rate.
# This is descriptive disclosure evidence only, never a merging/collapsing
# rule; every observed value still gets its own row in the support table
# regardless of this flag.
SPARSE_TAIL_MIN_ROWS = 5


@dataclass
class DescriptiveSummary:
    predictor: str
    n_nonmissing: int
    events: int
    non_events: int
    unique_subjects: int
    n_unique_values: int
    minimum: float
    q05: float
    q25: float
    median: float
    q75: float
    q95: float
    maximum: float


def descriptive_stats_continuous(
    df: pd.DataFrame, outcome_col: str, predictor_col: str, subject_groups: pd.Series | None = None,
) -> DescriptiveSummary:
    data = df[[outcome_col, predictor_col]].dropna()
    groups = subject_groups.loc[data.index] if subject_groups is not None else None
    values = data[predictor_col].astype(float)
    q = values.quantile([0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0])
    return DescriptiveSummary(
        predictor=predictor_col,
        n_nonmissing=len(data),
        events=int((data[outcome_col] == 1).sum()),
        non_events=int((data[outcome_col] == 0).sum()),
        unique_subjects=int(groups.nunique()) if groups is not None else -1,
        n_unique_values=int(values.nunique()),
        minimum=float(q.loc[0.0]), q05=float(q.loc[0.05]), q25=float(q.loc[0.25]),
        median=float(q.loc[0.5]), q75=float(q.loc[0.75]), q95=float(q.loc[0.95]),
        maximum=float(q.loc[1.0]),
    )


def count_value_support_table(
    df: pd.DataFrame, outcome_col: str, predictor_col: str, subject_groups: pd.Series | None = None,
) -> pd.DataFrame:
    """Every observed non-missing count value: rows, unique subjects, events, non-events.
    No value is ever collapsed, merged, or dropped here -- sparse tails are
    reported individually."""
    data = df[[outcome_col, predictor_col]].dropna()
    groups = subject_groups.loc[data.index] if subject_groups is not None else None
    rows = []
    for value in sorted(data[predictor_col].unique()):
        mask = data[predictor_col] == value
        rows.append({
            "predictor": predictor_col,
            "value": value,
            "rows": int(mask.sum()),
            "unique_subjects": int(groups.loc[mask].nunique()) if groups is not None else None,
            "events": int((data.loc[mask, outcome_col] == 1).sum()),
            "non_events": int((data.loc[mask, outcome_col] == 0).sum()),
        })
    return pd.DataFrame(rows)


# ==========================================================================
# Fitted-model wrappers (each keeps the REAL fitted statsmodels result, so
# every predicted-probability curve is computed directly from the exact
# fitted coefficients via patsy's own design_info -- never a manual
# intercept/slope reconstruction).
# ==========================================================================
@dataclass
class DiagnosticFitResult:
    fit_status: str
    result: object | None  # fitted statsmodels LogitResults, or None if not reliable
    design_matrix: np.ndarray | None  # the exact design matrix (values) used to fit `result`
    predict_fn: object | None  # callable: array-like grid -> predicted probability, from `result` directly
    note: str = ""


def _predict_fn_from_design_info(result, predictor_col: str) -> object:
    """Build a predict callable directly from the fitted result's own patsy
    design_info + fitted coefficients (never a manually reconstructed
    intercept/slope). `predictor_col` is passed explicitly by the caller --
    NOT auto-detected from patsy's factor naming -- because a spline design's
    factor expression is the whole `cr(AGE, df=3, ...)` string, not the bare
    variable name; the caller already knows the real column name to bind."""
    design_info = result.model.data.design_info

    def _predict(x_grid: np.ndarray) -> np.ndarray:
        grid_design = dmatrix(design_info, {predictor_col: np.asarray(x_grid)}, return_type="dataframe")
        linpred = grid_design.values @ result.params.values
        return 1.0 / (1.0 + np.exp(-linpred))

    return _predict


def fit_linear_diagnostic(
    df: pd.DataFrame, outcome_col: str, predictor_col: str, subject_groups: pd.Series | None = None,
) -> DiagnosticFitResult:
    """Cluster-robust logistic fit of outcome ~ predictor on the RAW native-
    unit predictor, keeping the actual fitted result object (never a
    reconstructed intercept)."""
    data = df[[outcome_col, predictor_col]].dropna()
    groups = subject_groups.loc[data.index] if subject_groups is not None else None
    formula = f"{outcome_col} ~ {predictor_col}"
    result, separation_status, fit_status = _fit_logit(formula, data, groups)
    if fit_status != FIT_OK or result is None:
        return DiagnosticFitResult(
            fit_status=fit_status, result=None, design_matrix=None, predict_fn=None,
            note=f"linear diagnostic fit not reliable (separation_status={separation_status})",
        )
    design_matrix = np.asarray(result.model.exog)
    return DiagnosticFitResult(
        fit_status=FIT_OK, result=result, design_matrix=design_matrix,
        predict_fn=_predict_fn_from_design_info(result, predictor_col),
    )


def _fit_flexible_spline(
    df: pd.DataFrame, outcome_col: str, predictor_col: str, subject_groups: pd.Series | None = None,
    spline_df: int = SPLINE_DF,
) -> DiagnosticFitResult:
    data = df[[outcome_col, predictor_col]].dropna().copy()
    groups = subject_groups.loc[data.index] if subject_groups is not None else None
    # constraints="center" avoids near-exact collinearity between the spline
    # basis and the formula's own intercept term (a well-known patsy cr()
    # gotcha -- without it the design matrix can be numerically singular,
    # producing NaN standard errors that look like separation but are really
    # a basis-parameterization artifact, not evidence about the data).
    formula = f'{outcome_col} ~ cr({predictor_col}, df={spline_df}, constraints="center")'
    result, separation_status, fit_status = _fit_logit(formula, data, groups)
    if fit_status != FIT_OK or result is None:
        return DiagnosticFitResult(
            fit_status=fit_status, result=None, design_matrix=None, predict_fn=None,
            note=f"flexible spline fit not reliable (separation_status={separation_status})",
        )
    design_matrix = np.asarray(result.model.exog)
    return DiagnosticFitResult(
        fit_status=FIT_OK, result=result, design_matrix=design_matrix,
        predict_fn=_predict_fn_from_design_info(result, predictor_col),
    )


def fit_quadratic_count_diagnostic(
    df: pd.DataFrame, outcome_col: str, predictor_col: str, subject_groups: pd.Series | None = None,
) -> DiagnosticFitResult:
    """PRIMARY flexible model for count predictors (Count Functional-Form
    Low-DF Correction task): a single predefined low-df quadratic,
    ``outcome ~ x + x_squared`` where ``x_squared = x ** 2`` on the native
    numeric count -- NOT one dummy coefficient per observed count value.

    This replaces the prior saturated-categorical flexible model, which
    produced unreliable, wildly inflated Wald evidence for sparse/singleton
    high-count levels (e.g. G=9/G=10, LIVE_BIRTH=5) via quasi-complete
    separation that the shared large-SE heuristic did not reliably catch.
    A fixed 1-extra-parameter quadratic cannot exhibit that failure mode the
    same way, and its single restriction (H0: beta_x_squared = 0) is exactly
    testable with a simple, unambiguous robust Wald test (see
    ``cluster_robust_wald_quadratic_term``).

    No centering/transform depends on the outcome; the squared term is a
    pure, deterministic function of the observed predictor values only.
    """
    data = df[[outcome_col, predictor_col]].dropna().copy()
    groups = subject_groups.loc[data.index] if subject_groups is not None else None
    squared_col = f"{predictor_col}_squared"
    data[squared_col] = data[predictor_col].astype(float) ** 2
    formula = f"{outcome_col} ~ {predictor_col} + {squared_col}"
    result, separation_status, fit_status = _fit_logit(formula, data, groups)
    if fit_status != FIT_OK or result is None:
        return DiagnosticFitResult(
            fit_status=fit_status, result=None, design_matrix=None, predict_fn=None,
            note=f"quadratic count diagnostic fit not reliable (separation_status={separation_status})",
        )
    design_matrix = np.asarray(result.model.exog)
    return DiagnosticFitResult(
        fit_status=FIT_OK, result=result, design_matrix=design_matrix,
        predict_fn=_quadratic_predict_fn(result, predictor_col, squared_col),
    )


def _quadratic_predict_fn(result, predictor_col: str, squared_col: str) -> object:
    """Predict callable for the quadratic count model, built directly from
    the fitted result's own design_info + coefficients (never a manual
    reconstruction)."""
    design_info = result.model.data.design_info

    def _predict(x_grid: np.ndarray) -> np.ndarray:
        x_grid = np.asarray(x_grid, dtype=float)
        grid_design = dmatrix(
            design_info, {predictor_col: x_grid, squared_col: x_grid ** 2}, return_type="dataframe",
        )
        linpred = grid_design.values @ result.params.values
        return 1.0 / (1.0 + np.exp(-linpred))

    return _predict


def _single_coefficient_restriction(result, param_name: str) -> np.ndarray:
    """Restriction matrix R (shape (1, n_params)) picking out exactly ONE
    fitted coefficient by NAME (never by an assumed position), so that
    ``result.wald_test(R)`` tests H0: that one coefficient = 0."""
    names = list(result.model.exog_names)
    if param_name not in names:
        raise ValueError(f"parameter {param_name!r} not found among fitted parameters {names}")
    idx = names.index(param_name)
    R = np.zeros((1, len(names)))
    R[0, idx] = 1.0
    return R


def cluster_robust_wald_quadratic_term(quadratic: DiagnosticFitResult, squared_col: str) -> "RobustWaldResult":
    """H0: beta_x_squared = 0, using the quadratic model's OWN stored
    cluster-robust covariance (fit with cov_type='cluster' upstream).
    df is always exactly 1 -- a single-coefficient restriction."""
    if quadratic.fit_status != FIT_OK or quadratic.result is None:
        return RobustWaldResult(None, None, None, note="quadratic fit not reliable; Wald test not attempted")
    try:
        R = _single_coefficient_restriction(quadratic.result, squared_col)
    except ValueError as exc:
        return RobustWaldResult(None, None, None, note=f"restriction construction failed: {exc}")
    wald = quadratic.result.wald_test(R, scalar=True)
    return RobustWaldResult(
        stat=float(wald.statistic), df=1, p_value=float(wald.pvalue),
        note="cluster-robust Wald test of H0: beta_x_squared=0 in the predefined quadratic "
             "outcome ~ x + x_squared model (uses the quadratic model's cov_type='cluster' "
             "covariance via wald_test's default cov_params())",
    )


# ==========================================================================
# Cluster-robust Wald test of "flexible model lies in the linear subspace"
# ==========================================================================
def _nested_restriction_matrix(
    X_full: np.ndarray, Z: np.ndarray, tol: float = NESTED_SUBSPACE_RELATIVE_TOLERANCE,
) -> np.ndarray:
    """Verify Z's column space is nested inside X_full's column space (i.e.
    every linear function of the raw predictor is exactly representable as
    a linear combination of the flexible design's columns), then return a
    restriction matrix R (shape (n_full - n_z, n_full_params)) whose rows
    span the orthogonal complement of that nested subspace -- so that
    ``R @ beta_full = 0`` is exactly the null hypothesis "beta_full lies in
    the linear subspace".

    FAILS LOUD (raises ValueError) if the reconstruction error exceeds
    `tol`, rather than silently proceeding with an invalid restriction.
    """
    A, _residuals, rank, _sv = np.linalg.lstsq(X_full, Z, rcond=None)
    reconstruction = X_full @ A
    denom = max(np.linalg.norm(Z), 1e-12)
    relative_error = float(np.linalg.norm(reconstruction - Z) / denom)
    if relative_error > tol:
        raise ValueError(
            f"linear design Z (shape {Z.shape}) is not nested within the flexible "
            f"design X_full's column space (shape {X_full.shape}): relative "
            f"reconstruction error {relative_error:.3e} exceeds tolerance {tol:.3e} "
            f"(lstsq rank={rank}). Refusing to build a Wald restriction from an "
            "invalid subspace assumption."
        )
    R_full = null_space(A.T)
    if R_full.shape[1] == 0:
        raise ValueError(
            "could not construct a nonzero restriction matrix: the flexible design "
            "has no dimensions beyond the linear subspace (null space is empty)."
        )
    return R_full.T  # shape (n_restrictions, n_full_params)


@dataclass
class RobustWaldResult:
    stat: float | None
    df: int | None
    p_value: float | None
    note: str = ""


def cluster_robust_wald_linearity_test(
    flexible: DiagnosticFitResult, Z: np.ndarray, tol: float = NESTED_SUBSPACE_RELATIVE_TOLERANCE,
) -> RobustWaldResult:
    """H0: the flexible model's fitted function lies in the ordinary linear
    subspace (intercept + beta*x). Uses the flexible model's OWN stored
    cluster-robust covariance (the model was fit with
    cov_type='cluster' upstream) -- statsmodels' wald_test uses
    self.cov_params() by default, which for a cluster-fit result IS the
    cluster-robust sandwich covariance, never a plain/naive one."""
    if flexible.fit_status != FIT_OK or flexible.result is None or flexible.design_matrix is None:
        return RobustWaldResult(None, None, None, note="flexible fit not reliable; Wald test not attempted")
    try:
        R = _nested_restriction_matrix(flexible.design_matrix, Z, tol=tol)
    except ValueError as exc:
        return RobustWaldResult(None, None, None, note=f"nested-subspace verification failed: {exc}")
    wald = flexible.result.wald_test(R, scalar=True)
    return RobustWaldResult(
        stat=float(wald.statistic), df=int(R.shape[0]), p_value=float(wald.pvalue),
        note="cluster-robust Wald test of H0: flexible fit lies in the linear subspace "
             "(uses the flexible model's cov_type='cluster' covariance via wald_test's default cov_params())",
    )


def _curve_probability_differences(
    linear_predict_fn, flexible_predict_fn, grid: np.ndarray,
) -> tuple[float, float]:
    """Purely DESCRIPTIVE evidence -- max/mean absolute predicted-probability
    difference between the linear and flexible curves over `grid`. Never
    converted into a clinical 'meaningful difference' threshold here."""
    p_lin = linear_predict_fn(grid)
    p_flex = flexible_predict_fn(grid)
    diff = np.abs(p_lin - p_flex)
    return float(diff.max()), float(diff.mean())


# ==========================================================================
# Per-predictor diagnostic drivers
# ==========================================================================
def run_continuous_diagnostic(
    df: pd.DataFrame, outcome_col: str, predictor_col: str, subject_groups: pd.Series | None,
) -> dict:
    reporting_unit = REPORTING_UNIT[predictor_col]
    desc = descriptive_stats_continuous(df, outcome_col, predictor_col, subject_groups)

    linear = fit_linear_diagnostic(df, outcome_col, predictor_col, subject_groups)
    flexible = _fit_flexible_spline(df, outcome_col, predictor_col, subject_groups, spline_df=SPLINE_DF)

    wald = RobustWaldResult(None, None, None, note="not attempted")
    curve_max_diff, curve_mean_diff = None, None
    if desc.n_unique_values > 2 and linear.fit_status == FIT_OK and flexible.fit_status == FIT_OK:
        data = df[[outcome_col, predictor_col]].dropna()
        Z = np.column_stack([np.ones(len(data)), data[predictor_col].to_numpy(dtype=float)])
        wald = cluster_robust_wald_linearity_test(flexible, Z)
        grid = np.linspace(desc.q05, desc.q95, 200)
        curve_max_diff, curve_mean_diff = _curve_probability_differences(
            linear.predict_fn, flexible.predict_fn, grid,
        )

    status, note = _classify_availability_status(desc, linear.fit_status, flexible.fit_status, wald)

    return {
        "predictor": predictor_col, "physical_type": "continuous", "reporting_unit": reporting_unit,
        "analysis_N": desc.n_nonmissing, "events": desc.events, "non_events": desc.non_events,
        "unique_subjects": desc.unique_subjects, "n_unique_values": desc.n_unique_values,
        "diagnostic_method": f"linear (raw native unit) vs natural cubic spline (cr, df={SPLINE_DF}); "
                              "cluster-robust Wald test of the linear restriction",
        "linear_fit_status": linear.fit_status, "flexible_fit_status": flexible.fit_status,
        "robust_wald_stat": wald.stat, "robust_wald_df": wald.df, "robust_wald_p": wald.p_value,
        "curve_max_abs_probability_difference": curve_max_diff,
        "curve_mean_abs_probability_difference": curve_mean_diff,
        "central_range_q05": desc.q05, "central_range_q95": desc.q95,
        "functional_form_status": status, "review_note": note,
        "_desc": desc, "_linear": linear, "_flexible": flexible, "_wald": wald,
    }


def _sparsity_flags(support_table: pd.DataFrame) -> tuple[bool, bool, bool]:
    """Target-independent sparsity/separation-risk disclosure (Count
    Functional-Form Low-DF Correction task, Section 8). `sparse_tail_present`
    is based ONLY on row counts (never outcome/event rate). Descriptive
    disclosure only -- never used to merge or drop a count value."""
    sparse_tail_present = bool((support_table["rows"] < SPARSE_TAIL_MIN_ROWS).any())
    any_level_zero_events = bool((support_table["events"] == 0).any())
    any_level_zero_non_events = bool((support_table["non_events"] == 0).any())
    return sparse_tail_present, any_level_zero_events, any_level_zero_non_events


def count_level_prediction_diagnostic_table(
    support_table: pd.DataFrame, linear: DiagnosticFitResult, quadratic: DiagnosticFitResult,
    predictor_col: str,
) -> pd.DataFrame:
    """One row per OBSERVED count value (never extrapolated to unobserved
    counts): predicted probability from the actual fitted linear and
    quadratic models, and their absolute difference. Descriptive evidence
    only -- no 'meaningful curvature' threshold is applied here."""
    values = support_table["value"].to_numpy(dtype=float)
    linear_p = linear.predict_fn(values) if linear.fit_status == FIT_OK and linear.predict_fn else None
    quad_p = quadratic.predict_fn(values) if quadratic.fit_status == FIT_OK and quadratic.predict_fn else None

    rows = []
    for i, (_, support_row) in enumerate(support_table.iterrows()):
        lp = float(linear_p[i]) if linear_p is not None else None
        qp = float(quad_p[i]) if quad_p is not None else None
        diff = abs(lp - qp) if (lp is not None and qp is not None) else None
        rows.append({
            "predictor": predictor_col,
            "value": support_row["value"],
            "observed_rows": int(support_row["rows"]),
            "observed_events": int(support_row["events"]),
            "linear_predicted_probability": lp,
            "quadratic_predicted_probability": qp,
            "absolute_probability_difference": diff,
        })
    return pd.DataFrame(
        rows,
        columns=["predictor", "value", "observed_rows", "observed_events",
                 "linear_predicted_probability", "quadratic_predicted_probability",
                 "absolute_probability_difference"],
    )


def run_count_diagnostic(
    df: pd.DataFrame, outcome_col: str, predictor_col: str, subject_groups: pd.Series | None,
) -> dict:
    """PRIMARY count functional-form diagnostic: linear vs. a predefined
    low-df quadratic (x + x_squared), tested via a cluster-robust Wald test
    of H0: beta_x_squared=0 (df=1) -- NOT a saturated one-dummy-per-value
    categorical comparison (see fit_quadratic_count_diagnostic's docstring
    for why that was replaced)."""
    reporting_unit = "1 unit (count)"
    desc = descriptive_stats_continuous(df, outcome_col, predictor_col, subject_groups)
    support_table = count_value_support_table(df, outcome_col, predictor_col, subject_groups)
    sparse_tail_present, any_level_zero_events, any_level_zero_non_events = _sparsity_flags(support_table)

    linear = fit_linear_diagnostic(df, outcome_col, predictor_col, subject_groups)

    wald = RobustWaldResult(None, None, None, note="not attempted")
    curve_max_diff, curve_mean_diff = None, None

    if desc.n_unique_values <= 2:
        quadratic = DiagnosticFitResult(fit_status="NOT_ATTEMPTED", result=None, design_matrix=None,
                                         predict_fn=None, note="fewer than 3 distinct values")
        method = "linear (per 1 unit) only (insufficient distinct values for a quadratic comparison)"
    else:
        quadratic = fit_quadratic_count_diagnostic(df, outcome_col, predictor_col, subject_groups)
        method = "linear (per 1 unit) vs predefined low-df quadratic (x + x^2); cluster-robust Wald " \
                 "test of H0: beta_x_squared=0"

    if desc.n_unique_values > 2 and linear.fit_status == FIT_OK and quadratic.fit_status == FIT_OK:
        squared_col = f"{predictor_col}_squared"
        wald = cluster_robust_wald_quadratic_term(quadratic, squared_col)
        observed_values = support_table["value"].to_numpy(dtype=float)
        curve_max_diff, curve_mean_diff = _curve_probability_differences(
            linear.predict_fn, quadratic.predict_fn, observed_values,
        )

    status, note = _classify_availability_status(desc, linear.fit_status, quadratic.fit_status, wald)

    return {
        "predictor": predictor_col, "physical_type": "count", "reporting_unit": reporting_unit,
        "analysis_N": desc.n_nonmissing, "events": desc.events, "non_events": desc.non_events,
        "unique_subjects": desc.unique_subjects, "n_unique_values": desc.n_unique_values,
        "diagnostic_method": method,
        "linear_fit_status": linear.fit_status, "flexible_fit_status": quadratic.fit_status,
        "robust_wald_stat": wald.stat, "robust_wald_df": wald.df, "robust_wald_p": wald.p_value,
        "curve_max_abs_probability_difference": curve_max_diff,
        "curve_mean_abs_probability_difference": curve_mean_diff,
        "central_range_q05": desc.q05, "central_range_q95": desc.q95,
        "sparse_tail_present": sparse_tail_present,
        "any_level_zero_events": any_level_zero_events,
        "any_level_zero_non_events": any_level_zero_non_events,
        "functional_form_status": status, "review_note": note,
        "_desc": desc, "_linear": linear, "_flexible": quadratic, "_wald": wald,
        "_support_table": support_table,
    }


def _classify_availability_status(
    desc: DescriptiveSummary, linear_status: str, flexible_status: str, wald: RobustWaldResult,
) -> tuple[str, str]:
    """Neutral status only -- NEVER an automated linear/nonlinear verdict
    (Functional-Form Methodological Correction pass, Section 4). Every
    predictor for which the diagnostic evidence was successfully computed
    is AWAITING_MANUAL_FUNCTIONAL_FORM_DECISION; only estimability failures
    produce INSUFFICIENT_INFORMATION_FOR_FORM_REVIEW."""
    if desc.n_unique_values <= 2:
        return (
            REVIEW_INSUFFICIENT_INFO,
            "Fewer than 3 distinct observed values -- a 'linear vs. flexible' shape "
            "comparison is not meaningful with only 1-2 points.",
        )
    if linear_status != FIT_OK:
        return (
            REVIEW_INSUFFICIENT_INFO,
            f"Linear diagnostic fit was not reliably estimable (fit_status={linear_status}); "
            "no functional-form evidence can be computed.",
        )
    if flexible_status != FIT_OK:
        return (
            REVIEW_INSUFFICIENT_INFO,
            f"Flexible diagnostic fit was not reliably estimable (fit_status={flexible_status}), "
            "even though the linear fit succeeded; the data may be too sparse to assess "
            "nonlinearity, not necessarily evidence FOR linearity.",
        )
    if wald.p_value is None:
        return (
            REVIEW_INSUFFICIENT_INFO,
            f"Cluster-robust Wald test of linearity could not be computed ({wald.note}).",
        )
    return (
        AWAITING_MANUAL_DECISION,
        "Diagnostic evidence computed (cluster-robust Wald test of the linear restriction, "
        "plus descriptive curve-difference metrics and the plotted shape over the observed "
        "central range). This is exploratory, data-informed evidence for MANUAL review -- "
        f"no automated linear/nonlinear verdict is assigned. robust_wald_p={wald.p_value:.4f} "
        f"(df={wald.df}) is ONE input among several (curve shape, data support at each part "
        "of the range, clinical plausibility, parsimony), never a standalone p<0.05 rule.",
    )


def build_functional_form_review_table(results: list[dict]) -> pd.DataFrame:
    rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    return pd.DataFrame(rows, columns=FUNCTIONAL_FORM_REVIEW_COLUMNS)


def plot_functional_form_diagnostic(
    df: pd.DataFrame, outcome_col: str, predictor_col: str, linear: DiagnosticFitResult,
    flexible: DiagnosticFitResult, reporting_unit: str, desc: DescriptiveSummary,
):
    """Diagnostic audit figure: observed-data rug, linear predicted-probability
    curve, flexible predicted-probability curve -- BOTH curves computed
    directly from their fitted statsmodels result objects via patsy's own
    design_info (never a manually reconstructed intercept) -- restricted to
    the observed central range (Q05-Q95), never extrapolated far beyond
    observed data. NOT a final manuscript figure."""
    data = df[[outcome_col, predictor_col]].dropna()
    x_grid = np.linspace(desc.q05, desc.q95, 200)

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.plot(data[predictor_col], data[outcome_col] * 0.0 - 0.03, "|", color="#666666", alpha=0.4, markersize=8)

    if linear.fit_status == FIT_OK and linear.predict_fn is not None:
        ax.plot(x_grid, linear.predict_fn(x_grid), label="linear diagnostic (exact fitted MLE)",
                 color="#1f77b4", linewidth=2)

    if flexible.fit_status == FIT_OK and flexible.predict_fn is not None:
        ax.plot(x_grid, flexible.predict_fn(x_grid), label=f"flexible diagnostic (spline, df={SPLINE_DF})",
                 color="#d62728", linewidth=2, linestyle="--")

    ax.set_xlabel(f"{predictor_col} (native unit; reporting unit: {reporting_unit})")
    ax.set_ylabel("predicted P(intrapartum CS) -- diagnostic only")
    ax.set_title(f"Functional-form diagnostic: {predictor_col}\n"
                 "(audit figure -- NOT a final manuscript figure; data-informed exploratory evidence)")
    ax.legend(fontsize=8)
    ax.set_xlim(desc.q05, desc.q95)
    fig.tight_layout()
    return fig

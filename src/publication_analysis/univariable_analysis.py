"""Univariable association analysis (Section D) and exploratory BH-FDR (Section 10).

For every predictor's publication representation, fits a univariable
logistic regression of ``target_intrapartum_cs`` on that predictor, using
subject-cluster-robust standard errors where a grouping key is supplied
(see ``subject_grouping.py``).

This module never decides model eligibility from a p-value, never removes a
predictor for p > 0.05, and never silently reports an unreliable MLE under
complete/quasi separation — such rows are kept with an explicit
``STANDARD_OR_NOT_RELIABLY_ESTIMABLE`` status and a stated reason instead.
Firth-type penalized logistic regression is explicitly out of scope for this
implementation phase.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.tools.sm_exceptions import ConvergenceWarning, PerfectSeparationWarning

from publication_analysis.publication_representations import (
    APPROVED,
    FF_LINEAR_APPROVED,
    FF_NONLINEAR_APPROVED,
    FF_PENDING_REVIEW,
    PENDING_CLINICAL_SIGNOFF,
    PublicationLabelMappingError,
    ROLE_BINARY,
    ROLE_CATEGORICAL,
    ROLE_CONTINUOUS,
    ROLE_COUNT,
    ROLE_DESCRIPTIVE_ONLY,
    ROLE_PENDING,
    prepare_predictor_for_publication_inference,
)

try:  # statsmodels versions differ in whether this is a hard exception
    from statsmodels.tools.sm_exceptions import PerfectSeparationError
except ImportError:  # pragma: no cover
    PerfectSeparationError = None  # type: ignore[assignment,misc]

FIT_OK = "OK"
FIT_NOT_RELIABLE = "STANDARD_OR_NOT_RELIABLY_ESTIMABLE"

SEPARATION_NONE = "none"
SEPARATION_COMPLETE = "complete_separation"
SEPARATION_SINGLE_CASE = "single_case_support"
SEPARATION_NON_CONVERGENCE = "non_convergence"
SEPARATION_OTHER = "other"

SUPPORT_OK = "OK"
SUPPORT_SPARSE = "SPARSE_EXPLORATORY"
SUPPORT_INSUFFICIENT = "INSUFFICIENT_SUPPORT"
# A categorical SOURCE row spans multiple levels with potentially very
# different support; it must never unconditionally claim SUPPORT_OK without
# examining level-level support (Checkpoint-B targeted-correction #7). This
# status is reporting-only and is never used as an eligibility filter -- the
# per-level rows retain their own real support_status from _support_status().
SUPPORT_SEE_LEVEL_SUPPORT = "SEE_LEVEL_SUPPORT"
# A CONTINUOUS/COUNT predictor has no exposed-vs-unexposed carrier cell --
# min(outcome events, outcome non-events) describes OUTCOME balance, not
# predictor/exposure support, and must never be classified OK / SPARSE_
# EXPLORATORY / INSUFFICIENT_SUPPORT on that basis (Checkpoint-B targeted-
# correction #2). model_analysis_N / model_events / model_non_events /
# model_unique_subjects already carry the real sample/outcome-adequacy
# information for these predictors.
SUPPORT_NOT_APPLICABLE_CONTINUOUS_COUNT = "NOT_APPLICABLE_CONTINUOUS_COUNT"

MIN_EVENTS_SPARSE_THRESHOLD = 5
MIN_EVENTS_INSUFFICIENT_THRESHOLD = 1

LARGE_SE_THRESHOLD = 10.0  # on the log-odds scale; a proxy for quasi-separation


@dataclass
class UnivariableResult:
    predictor: str
    level: str | None
    unit: str
    reference: str
    analysis_n: int
    events: int
    non_events: int
    unique_subject_groups: int | None
    odds_ratio: float | None
    ci_low: float | None
    ci_high: float | None
    p_value: float | None
    fit_status: str
    separation_status: str
    support_status: str
    notes: str = ""


def _support_status(min_cell_events: int) -> str:
    if min_cell_events < MIN_EVENTS_INSUFFICIENT_THRESHOLD:
        return SUPPORT_INSUFFICIENT
    if min_cell_events < MIN_EVENTS_SPARSE_THRESHOLD:
        return SUPPORT_SPARSE
    return SUPPORT_OK


def _fit_logit(formula: str, data: pd.DataFrame, groups: pd.Series | None):
    """Fit a logistic regression, returning (result, separation_status, fit_status)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            model = smf.logit(formula, data=data)
            if groups is not None:
                result = model.fit(disp=0, cov_type="cluster", cov_kwds={"groups": groups})
            else:
                result = model.fit(disp=0)
        except Exception as exc:  # noqa: BLE001 - statsmodels raises several distinct types
            if PerfectSeparationError is not None and isinstance(exc, PerfectSeparationError):
                return None, SEPARATION_COMPLETE, FIT_NOT_RELIABLE
            return None, SEPARATION_OTHER, FIT_NOT_RELIABLE

        separation_status = SEPARATION_NONE
        fit_status = FIT_OK

        for warning in caught:
            if issubclass(warning.category, PerfectSeparationWarning):
                separation_status = SEPARATION_COMPLETE
                fit_status = FIT_NOT_RELIABLE
            elif issubclass(warning.category, ConvergenceWarning) and fit_status == FIT_OK:
                separation_status = SEPARATION_NON_CONVERGENCE
                fit_status = FIT_NOT_RELIABLE

        converged = result.mle_retvals.get("converged", True)
        if not converged and fit_status == FIT_OK:
            separation_status = SEPARATION_NON_CONVERGENCE
            fit_status = FIT_NOT_RELIABLE

        if fit_status == FIT_OK:
            bse = np.asarray(result.bse)
            if np.any(~np.isfinite(bse)) or np.any(bse > LARGE_SE_THRESHOLD):
                separation_status = SEPARATION_COMPLETE
                fit_status = FIT_NOT_RELIABLE

        return result, separation_status, fit_status


def fit_univariable_binary(
    df: pd.DataFrame,
    outcome_col: str,
    predictor_col: str,
    subject_groups: pd.Series | None = None,
    unit: str = "binary",
    reference: str = "value 0",
) -> UnivariableResult:
    data = df[[outcome_col, predictor_col]].dropna()
    groups = subject_groups.loc[data.index] if subject_groups is not None else None

    events = int(data[outcome_col].sum())
    non_events = int((data[outcome_col] == 0).sum())
    n = len(data)

    crosstab = pd.crosstab(data[predictor_col], data[outcome_col])
    min_cell = int(crosstab.values.min()) if crosstab.size else 0
    support_status = _support_status(min_cell)

    if crosstab.shape[0] < 2 or (crosstab.values == 0).any():
        return UnivariableResult(
            predictor=predictor_col,
            level=None,
            unit=unit,
            reference=reference,
            analysis_n=n,
            events=events,
            non_events=non_events,
            unique_subject_groups=int(groups.nunique()) if groups is not None else None,
            odds_ratio=None,
            ci_low=None,
            ci_high=None,
            p_value=None,
            fit_status=FIT_NOT_RELIABLE,
            separation_status=SEPARATION_COMPLETE if crosstab.shape[0] >= 2 else SEPARATION_SINGLE_CASE,
            support_status=support_status,
            notes="Zero-count cell in the 2x2 outcome table (complete separation) or single predictor level.",
        )

    formula = f"{outcome_col} ~ {predictor_col}"
    result, separation_status, fit_status = _fit_logit(formula, data, groups)

    if fit_status != FIT_OK or result is None:
        return UnivariableResult(
            predictor=predictor_col,
            level=None,
            unit=unit,
            reference=reference,
            analysis_n=n,
            events=events,
            non_events=non_events,
            unique_subject_groups=int(groups.nunique()) if groups is not None else None,
            odds_ratio=None,
            ci_low=None,
            ci_high=None,
            p_value=None,
            fit_status=fit_status,
            separation_status=separation_status,
            support_status=support_status,
            notes="Logistic fit did not converge or was flagged unstable.",
        )

    coef = result.params[predictor_col]
    ci_low, ci_high = result.conf_int().loc[predictor_col]
    p_value = result.pvalues[predictor_col]

    return UnivariableResult(
        predictor=predictor_col,
        level=None,
        unit=unit,
        reference=reference,
        analysis_n=n,
        events=events,
        non_events=non_events,
        unique_subject_groups=int(groups.nunique()) if groups is not None else None,
        odds_ratio=float(np.exp(coef)),
        ci_low=float(np.exp(ci_low)),
        ci_high=float(np.exp(ci_high)),
        p_value=float(p_value),
        fit_status=FIT_OK,
        separation_status=SEPARATION_NONE,
        support_status=support_status,
    )


def fit_univariable_continuous(
    df: pd.DataFrame,
    outcome_col: str,
    predictor_col: str,
    subject_groups: pd.Series | None = None,
    unit_scale: float = 1.0,
    unit_label: str = "per unit",
) -> UnivariableResult:
    """Fit OR per ``unit_scale`` of the predictor (e.g. per 5 years, per 1 kg/m^2)."""
    data = df[[outcome_col, predictor_col]].dropna()
    groups = subject_groups.loc[data.index] if subject_groups is not None else None

    events = int(data[outcome_col].sum())
    non_events = int((data[outcome_col] == 0).sum())
    n = len(data)
    # NOT a carrier-cell / exposure-support status: a continuous/count
    # predictor has no exposed-vs-unexposed cell to be sparse or insufficient
    # in. model_analysis_N / model_events / model_non_events (reported
    # separately by the caller) already describe sample/outcome adequacy.
    support_status = SUPPORT_NOT_APPLICABLE_CONTINUOUS_COUNT

    scaled_col = f"{predictor_col}__scaled"
    scaled_data = data.copy()
    scaled_data[scaled_col] = scaled_data[predictor_col] / unit_scale

    formula = f"{outcome_col} ~ {scaled_col}"
    result, separation_status, fit_status = _fit_logit(formula, scaled_data, groups)

    if fit_status != FIT_OK or result is None:
        return UnivariableResult(
            predictor=predictor_col,
            level=None,
            unit=unit_label,
            reference="n/a (continuous)",
            analysis_n=n,
            events=events,
            non_events=non_events,
            unique_subject_groups=int(groups.nunique()) if groups is not None else None,
            odds_ratio=None,
            ci_low=None,
            ci_high=None,
            p_value=None,
            fit_status=fit_status,
            separation_status=separation_status,
            support_status=support_status,
            notes="Logistic fit did not converge or was flagged unstable.",
        )

    coef = result.params[scaled_col]
    ci_low, ci_high = result.conf_int().loc[scaled_col]
    p_value = result.pvalues[scaled_col]

    return UnivariableResult(
        predictor=predictor_col,
        level=None,
        unit=unit_label,
        reference="n/a (continuous)",
        analysis_n=n,
        events=events,
        non_events=non_events,
        unique_subject_groups=int(groups.nunique()) if groups is not None else None,
        odds_ratio=float(np.exp(coef)),
        ci_low=float(np.exp(ci_low)),
        ci_high=float(np.exp(ci_high)),
        p_value=float(p_value),
        fit_status=FIT_OK,
        separation_status=SEPARATION_NONE,
        support_status=support_status,
    )


SPLINE_DF = 3

EFFECT_REPRESENTATION_LINEAR = "linear_one_slope"
EFFECT_REPRESENTATION_NONLINEAR_SPLINE = "nonlinear_spline"


def fit_univariable_nonlinear_spline(
    df: pd.DataFrame,
    outcome_col: str,
    predictor_col: str,
    subject_groups: pd.Series | None = None,
    spline_df: int = SPLINE_DF,
) -> UnivariableResult:
    """FINAL FUNCTIONAL-FORM LOCK: fixed natural cubic spline representation
    (``patsy cr(x, df=3, constraints="center")``), fit with subject-cluster-
    robust covariance (same ``cov_type='cluster'`` machinery as every other
    univariable fit in this module).

    This function deliberately returns NO single odds ratio / CI — a
    nonlinear spline has no single per-unit log-odds slope to report. The
    ``p_value`` field instead carries the source-level cluster-robust Wald
    OMNIBUS test of H0: all non-intercept spline coefficients = 0. No
    individual spline-basis coefficient is ever surfaced as a clinically
    interpretable effect estimate.
    """
    data = df[[outcome_col, predictor_col]].dropna()
    groups = subject_groups.loc[data.index] if subject_groups is not None else None

    events = int(data[outcome_col].sum())
    non_events = int((data[outcome_col] == 0).sum())
    n = len(data)
    unit_label = f"Nonlinear spline (df={spline_df})"
    reference_label = "n/a (nonlinear spline)"

    # constraints="center" avoids near-exact collinearity between the spline
    # basis and the formula's own intercept term (see functional_form_diagnostic.py).
    formula = f'{outcome_col} ~ cr({predictor_col}, df={spline_df}, constraints="center")'
    result, separation_status, fit_status = _fit_logit(formula, data, groups)

    if fit_status != FIT_OK or result is None:
        return UnivariableResult(
            predictor=predictor_col,
            level=None,
            unit=unit_label,
            reference=reference_label,
            analysis_n=n,
            events=events,
            non_events=non_events,
            unique_subject_groups=int(groups.nunique()) if groups is not None else None,
            odds_ratio=None,
            ci_low=None,
            ci_high=None,
            p_value=None,
            fit_status=fit_status,
            separation_status=separation_status,
            support_status=SUPPORT_NOT_APPLICABLE_CONTINUOUS_COUNT,
            notes="Nonlinear spline fit did not converge or was flagged unstable.",
        )

    param_names = list(result.model.exog_names)
    non_intercept_idx = [i for i, name in enumerate(param_names) if name != "Intercept"]
    R = np.zeros((len(non_intercept_idx), len(param_names)))
    for restriction_row, col_idx in enumerate(non_intercept_idx):
        R[restriction_row, col_idx] = 1.0
    # wald_test uses the fitted result's own cov_params() by default -- for a
    # result fit with cov_type='cluster' upstream (see _fit_logit), that IS
    # the subject-cluster-robust sandwich covariance, never a naive one.
    wald = result.wald_test(R, scalar=True)
    omnibus_p = float(wald.pvalue)

    return UnivariableResult(
        predictor=predictor_col,
        level=None,
        unit=unit_label,
        reference=reference_label,
        analysis_n=n,
        events=events,
        non_events=non_events,
        unique_subject_groups=int(groups.nunique()) if groups is not None else None,
        odds_ratio=None,
        ci_low=None,
        ci_high=None,
        p_value=omnibus_p,
        fit_status=FIT_OK,
        separation_status=SEPARATION_NONE,
        support_status=SUPPORT_NOT_APPLICABLE_CONTINUOUS_COUNT,
        notes=(
            "Cluster-robust Wald omnibus test of H0: all non-intercept spline coefficients "
            "= 0. No single OR is reported for a nonlinear spline representation; no "
            "individual spline-basis coefficient is clinically interpreted."
        ),
    )


@dataclass
class CategoricalUnivariableResult:
    predictor: str
    reference: str
    level_results: list[UnivariableResult]
    omnibus_p_value: float | None
    omnibus_status: str
    separation_status: str = SEPARATION_NONE
    omnibus_reason: str = ""


def _ordered_non_reference_levels(
    observed: list[str], reference_level: str, category_order: list[str] | None,
) -> list[str]:
    """Deterministic display order for the non-reference level-detail rows.

    ``category_order`` is used purely as a display sequence (item 7): the
    observed non-reference levels are returned in the order given by
    ``category_order`` with the reference level removed. It is NEVER treated
    as an ordinal numeric encoding and drives no statistical calculation. Any
    observed level not present in ``category_order`` (should not happen for an
    approved contract) is appended in stable sorted order so nothing is
    silently dropped.
    """
    observed_non_ref = [lvl for lvl in observed if lvl != reference_level]
    if not isinstance(category_order, list) or not category_order:
        return sorted(observed_non_ref)
    seq = [lvl for lvl in category_order if lvl != reference_level and lvl in observed_non_ref]
    seq += sorted(lvl for lvl in observed_non_ref if lvl not in category_order)
    return seq


def _categorical_descriptive_level_row(
    data: pd.DataFrame,
    outcome_col: str,
    predictor_col: str,
    reference_level: str,
    level_label: str,
    groups: pd.Series | None,
    separation_status: str,
    notes: str,
) -> UnivariableResult:
    """Descriptive-only level-detail row (no OR/CI/p) used when the standard
    categorical MLE is blocked by the deterministic zero-cell gate."""
    level_mask = data[predictor_col].astype(str) == level_label
    n_level = int(level_mask.sum())
    events_level = int(data.loc[level_mask, outcome_col].sum())
    non_events_level = n_level - events_level
    level_groups = groups.loc[data.index[level_mask]] if groups is not None else None
    return UnivariableResult(
        predictor=predictor_col,
        level=level_label,
        unit="categorical",
        reference=reference_level,
        analysis_n=n_level,
        events=events_level,
        non_events=non_events_level,
        unique_subject_groups=int(level_groups.nunique()) if level_groups is not None else None,
        odds_ratio=None,
        ci_low=None,
        ci_high=None,
        p_value=None,
        fit_status=FIT_NOT_RELIABLE,
        separation_status=separation_status,
        support_status=_support_status(min(events_level, non_events_level)),
        notes=notes,
    )


def fit_univariable_categorical(
    df: pd.DataFrame,
    outcome_col: str,
    predictor_col: str,
    reference_level: str,
    subject_groups: pd.Series | None = None,
    category_order: list[str] | None = None,
) -> CategoricalUnivariableResult:
    data = df[[outcome_col, predictor_col]].dropna()
    groups = subject_groups.loc[data.index] if subject_groups is not None else None

    observed_levels = sorted(data[predictor_col].astype(str).unique())
    if reference_level not in observed_levels:
        return CategoricalUnivariableResult(
            predictor=predictor_col,
            reference=reference_level,
            level_results=[],
            omnibus_p_value=None,
            omnibus_status=FIT_NOT_RELIABLE,
            separation_status=SEPARATION_OTHER,
            omnibus_reason=(
                f"reference level {reference_level!r} is not observed in the "
                "complete-case data for this predictor"
            ),
        )

    events = int(data[outcome_col].sum())
    non_events = int((data[outcome_col] == 0).sum())

    # ---- deterministic pre-fit categorical estimability / separation gate ----
    # (CHECKPOINT C categorical-separation correction §2/§4). Cross EVERY
    # observed category (the reference category INCLUDED) with the complete-case
    # outcome. A standard unpenalized categorical logistic model is NOT reliably
    # estimable when fewer than two categories are observed, OR when ANY observed
    # category has zero events or zero non-events (complete separation within a
    # category). This is a deterministic structural check on the contingency
    # table -- not a p-value rule, independent of any chosen effect direction --
    # and the offending category is NEVER collapsed or dropped. Ordinary sparse
    # but non-zero cells (e.g. 1 event / 14 non-events) do NOT trip this gate and
    # keep their existing SPARSE_EXPLORATORY handling (§5).
    contingency = pd.crosstab(data[predictor_col].astype(str), data[outcome_col])
    for outcome_value in (0, 1):
        if outcome_value not in contingency.columns:
            contingency[outcome_value] = 0
    zero_cell_levels = sorted(
        str(lvl)
        for lvl in contingency.index
        if int(contingency.loc[lvl, 0]) == 0 or int(contingency.loc[lvl, 1]) == 0
    )
    if len(observed_levels) < 2 or zero_cell_levels:
        if len(observed_levels) < 2:
            omnibus_reason = (
                f"Standard categorical logistic MLE not reliably estimable: fewer than two "
                f"categories of {predictor_col!r} are observed in the complete-case data."
            )
            gate_separation = SEPARATION_SINGLE_CASE
        else:
            omnibus_reason = (
                f"Standard categorical logistic MLE not reliably estimable: category(ies) "
                f"{zero_cell_levels} have a zero outcome cell (0 events or 0 non-events) -> "
                f"complete separation within a category. The affected category is retained "
                f"(not collapsed); no OR/CI/coefficient p is reported from the full model."
            )
            gate_separation = SEPARATION_COMPLETE
        level_notes = (
            "Standard categorical MLE not reliably estimable (at least one category has a "
            "zero outcome cell); descriptive counts only, no OR/CI/coefficient p."
        )
        level_results = [
            _categorical_descriptive_level_row(
                data, outcome_col, predictor_col, reference_level, lvl, groups,
                SEPARATION_COMPLETE if lvl in zero_cell_levels else SEPARATION_NONE,
                level_notes,
            )
            for lvl in _ordered_non_reference_levels(
                observed_levels, reference_level, category_order
            )
        ]
        return CategoricalUnivariableResult(
            predictor=predictor_col,
            reference=reference_level,
            level_results=level_results,
            omnibus_p_value=None,
            omnibus_status=FIT_NOT_RELIABLE,
            separation_status=gate_separation,
            omnibus_reason=omnibus_reason,
        )
    # ---- end deterministic gate ----

    formula = f"{outcome_col} ~ C({predictor_col}, Treatment(reference='{reference_level}'))"
    result, separation_status, fit_status = _fit_logit(formula, data, groups)

    if fit_status != FIT_OK or result is None:
        return CategoricalUnivariableResult(
            predictor=predictor_col,
            reference=reference_level,
            level_results=[
                UnivariableResult(
                    predictor=predictor_col,
                    level="ALL_LEVELS",
                    unit="categorical",
                    reference=reference_level,
                    analysis_n=len(data),
                    events=events,
                    non_events=non_events,
                    unique_subject_groups=int(groups.nunique()) if groups is not None else None,
                    odds_ratio=None,
                    ci_low=None,
                    ci_high=None,
                    p_value=None,
                    fit_status=fit_status,
                    separation_status=separation_status,
                    support_status=SUPPORT_INSUFFICIENT,
                    notes="Logistic fit did not converge or was flagged unstable.",
                )
            ],
            omnibus_p_value=None,
            omnibus_status=fit_status,
            separation_status=separation_status,
            omnibus_reason="categorical logistic fit did not converge or was flagged unstable",
        )

    levels_by_label: dict[str, UnivariableResult] = {}
    for term in result.params.index:
        if term == "Intercept":
            continue
        level_label = term.split("T.", 1)[-1].rstrip("]")
        coef = result.params[term]
        ci_low, ci_high = result.conf_int().loc[term]
        p_value = result.pvalues[term]
        level_mask = data[predictor_col].astype(str) == level_label
        n_level = int(level_mask.sum())
        events_level = int(data.loc[level_mask, outcome_col].sum())
        non_events_level = n_level - events_level
        # LEVEL-specific unique-subject count (Checkpoint-B targeted-correction
        # #1): must be computed only among rows belonging to THIS level, never
        # copied from the whole model's grouping vector. `groups` is already
        # aligned to `data.index` (see the `groups = subject_groups.loc[...]`
        # assignment above), so `data.index[level_mask]` selects exactly this
        # level's rows and `groups.loc[...]` restricts the grouping vector to
        # them before counting unique subjects.
        level_groups = groups.loc[data.index[level_mask]] if groups is not None else None
        levels_by_label[level_label] = UnivariableResult(
            predictor=predictor_col,
            level=level_label,
            unit="categorical",
            reference=reference_level,
            analysis_n=n_level,
            events=events_level,
            non_events=non_events_level,
            unique_subject_groups=int(level_groups.nunique()) if level_groups is not None else None,
            odds_ratio=float(np.exp(coef)),
            ci_low=float(np.exp(ci_low)),
            ci_high=float(np.exp(ci_high)),
            p_value=float(p_value),
            fit_status=FIT_OK,
            separation_status=SEPARATION_NONE,
            support_status=_support_status(min(events_level, non_events_level)),
        )

    # Publication display order (item 7): emit the non-reference level-detail
    # rows in the approved category_order (reference removed). Ordering only --
    # no estimate changes.
    ordered_labels = _ordered_non_reference_levels(
        list(levels_by_label.keys()), reference_level, category_order
    )
    level_results = [levels_by_label[lbl] for lbl in ordered_labels if lbl in levels_by_label]
    level_results += [
        lr for lbl, lr in levels_by_label.items() if lbl not in ordered_labels
    ]

    omnibus_p_value = None
    omnibus_status = FIT_OK
    try:
        wald = result.wald_test_terms(skip_single=False)
        term_name = [t for t in wald.table.index if predictor_col in t]
        if term_name:
            omnibus_p_value = float(wald.table.loc[term_name[0], "pvalue"])
    except Exception:  # noqa: BLE001
        omnibus_status = FIT_NOT_RELIABLE

    return CategoricalUnivariableResult(
        predictor=predictor_col,
        reference=reference_level,
        level_results=level_results,
        omnibus_p_value=omnibus_p_value,
        omnibus_status=omnibus_status,
        separation_status=SEPARATION_NONE,
        omnibus_reason="" if omnibus_status == FIT_OK else "categorical omnibus Wald test not computable",
    )


# ===========================================================================
# Checkpoint B — full 81-predictor univariable master dispatcher
# ===========================================================================
FIT_NOT_FITTED = "NOT_FITTED"

MASTER_COLUMNS = [
    "predictor",
    "inferential_role",
    "row_type",              # 'source' (one per predictor) | 'level' (categorical detail)
    "level",
    "reference_level",
    "reporting_unit",
    "continuous_unit_scale",
    "fit_status",
    "separation_status",
    "support_status",
    "model_analysis_N",
    "model_events",
    "model_non_events",
    "model_unique_subjects",
    "value_1_n",              # binary only -- rows where the stored value == 1 (numeric, not a clinical claim)
    "value_0_n",              # binary only -- rows where the stored value == 0
    "value_1_events",         # binary only -- value==1 rows with outcome==1
    "value_0_events",         # binary only -- value==0 rows with outcome==1
    "level_n",               # categorical level rows only
    "level_events",
    "level_non_events",
    "level_unique_subjects",
    "odds_ratio",
    "ci_low",
    "ci_high",
    "coef_p_value",          # binary/continuous/count coefficient p
    "omnibus_p_value",       # categorical source-level omnibus p, OR nonlinear-spline omnibus p
    "effect_representation", # 'linear_one_slope' | 'nonlinear_spline' (CONTINUOUS/COUNT source rows only)
    "spline_df",             # fixed spline df (3) for nonlinear_spline rows only, else None
    "reason",
]

HYPOTHESIS_BINARY = "binary_coefficient"
HYPOTHESIS_CONTINUOUS = "continuous_coefficient"
HYPOTHESIS_COUNT = "count_coefficient"
HYPOTHESIS_CATEGORICAL_OMNIBUS = "categorical_omnibus"
HYPOTHESIS_NONLINEAR_SPLINE_OMNIBUS = "nonlinear_spline_omnibus"
HYPOTHESIS_NOT_ESTIMABLE = "not_estimable"


def _blank_master_row(predictor: str, role: str, row_type: str) -> dict:
    row = {col: None for col in MASTER_COLUMNS}
    row["predictor"] = predictor
    row["inferential_role"] = role
    row["row_type"] = row_type
    return row


def _binary_support(data: pd.DataFrame, outcome_col: str, predictor_col: str) -> dict:
    """Numeric value==1 / value==0 row and event counts.

    Field names are numerically neutral ("value_1"/"value_0"), never
    "exposed"/"unexposed" (Checkpoint-B targeted-correction #3): for a
    GENERIC_1_VS_0 binary predictor, "exposed" would assert an unsupported
    clinical present/absent meaning that no repository source establishes.
    """
    pred = data[predictor_col]
    out = data[outcome_col]
    is_value_1 = pred == 1
    is_value_0 = pred == 0
    return {
        "value_1_n": int(is_value_1.sum()),
        "value_0_n": int(is_value_0.sum()),
        "value_1_events": int((is_value_1 & (out == 1)).sum()),
        "value_0_events": int((is_value_0 & (out == 1)).sum()),
    }


def run_univariable_master(
    matrix_df: pd.DataFrame,
    contract_df: pd.DataFrame,
    outcome_col: str,
    subject_groups: pd.Series | None = None,
) -> pd.DataFrame:
    """Dispatch every one of the 81 source predictors to its univariable
    analysis according to its ``inferential_role`` in the publication
    representation contract.

    * BINARY / CONTINUOUS / COUNT  -> one ``row_type='source'`` row with the
      coefficient p-value (``coef_p_value``).
    * CATEGORICAL -> one ``row_type='source'`` row carrying the source-level
      omnibus p-value, plus one ``row_type='level'`` row per non-reference
      level with the level-specific OR / CI / p.
    * DESCRIPTIVE_ONLY / PENDING_REPRESENTATION_REVIEW -> retained as a
      ``row_type='source'`` row with ``fit_status = NOT_FITTED`` and a stated
      reason. No predictor is ever dropped.

    A representation whose ``publication_status`` is not ``APPROVED`` — in
    particular ``PENDING_CLINICAL_SIGNOFF`` (a concrete, repository-grounded
    proposal that has not yet been signed off by a clinician) — is NEVER
    dispatched to the low-level fitting functions by this default master
    dispatcher, regardless of its ``inferential_role``. This is a hard gate
    on ``publication_status``, checked independently of ``inferential_role``,
    so a future real-data run cannot silently fit a not-yet-approved
    CATEGORICAL/CONTINUOUS/COUNT proposal just because its role looks
    fittable. There is no override flag: the only way a predictor becomes
    fittable here is for the representation contract itself to record
    ``publication_status = APPROVED`` (i.e. clinical sign-off updates the
    contract, not a bypass parameter on this function).

    No real-data fitting decision is made here about model eligibility, and a
    non-estimable MLE (separation / numerical failure / zero cells) is kept
    with a transparent ``fit_status`` — never dropped, never given a
    fabricated OR.
    """
    contract_by_pred = contract_df.set_index("predictor")
    rows: list[dict] = []

    for predictor in contract_df["predictor"]:
        spec = contract_by_pred.loc[predictor]
        role = spec["inferential_role"]
        ref_level = spec["reference_level"]
        reporting_unit = spec["reporting_unit"]
        scale = spec["continuous_unit_scale"]
        pub_status = spec.get("publication_status")

        if role in (ROLE_DESCRIPTIVE_ONLY, ROLE_PENDING):
            row = _blank_master_row(predictor, role, "source")
            row["fit_status"] = FIT_NOT_FITTED
            row["reason"] = (
                "DESCRIPTIVE_ONLY — retained for description, not fitted in the primary "
                "whole-cohort univariable analysis."
                if role == ROLE_DESCRIPTIVE_ONLY
                else "PENDING_REPRESENTATION_REVIEW — no approved publication representation; "
                "not fitted in Checkpoint B."
            )
            rows.append(row)
            continue

        # Hard gate on publication_status, independent of inferential_role:
        # only an explicitly APPROVED representation may reach the low-level
        # fitting functions below. A representation contract row with no
        # publication_status at all is treated the same as "not approved"
        # (fail safe -- never silently fit an unmarked row).
        if pub_status != APPROVED:
            row = _blank_master_row(predictor, role, "source")
            row["fit_status"] = FIT_NOT_FITTED
            row["reason"] = (
                "PENDING_CLINICAL_SIGNOFF — representation proposed but not yet clinically "
                "approved for real-data inferential execution."
                if pub_status == PENDING_CLINICAL_SIGNOFF
                else f"publication_status={pub_status!r} is not APPROVED; not fitted by the "
                "default master dispatcher."
            )
            rows.append(row)
            continue

        # Second, independent hard gate -- the functional-form gate (Representation
        # Sign-off + Functional-Form Gate task, now FINAL FUNCTIONAL-FORM LOCK): an
        # APPROVED reporting unit for a CONTINUOUS/COUNT predictor is NOT the same
        # as an approved functional form. Only CONTINUOUS/COUNT roles carry a
        # functional_form_status at all (every other role is NOT_APPLICABLE and
        # never blocked here). A predictor whose functional_form_status is
        # anything other than LINEAR_FORM_APPROVED or NONLINEAR_FORM_APPROVED is
        # never dispatched to a low-level fitting function by this default master
        # dispatcher -- there is no executable path that silently fits an
        # unresolved functional form.
        ff_status = spec.get("functional_form_status")
        if role in (ROLE_CONTINUOUS, ROLE_COUNT) and ff_status not in (
            FF_LINEAR_APPROVED, FF_NONLINEAR_APPROVED,
        ):
            row = _blank_master_row(predictor, role, "source")
            row["fit_status"] = FIT_NOT_FITTED
            row["reason"] = (
                "PENDING_FUNCTIONAL_FORM_REVIEW — reporting unit is approved, but the "
                "functional form has not yet been reviewed/approved; a final per-unit OR / "
                "nonlinear spline result is not produced by the default master dispatcher "
                "until functional_form_status becomes LINEAR_FORM_APPROVED or "
                "NONLINEAR_FORM_APPROVED."
                if ff_status == FF_PENDING_REVIEW
                else f"functional_form_status={ff_status!r} is not LINEAR_FORM_APPROVED or "
                "NONLINEAR_FORM_APPROVED; not fitted by the default master dispatcher."
            )
            rows.append(row)
            continue

        if predictor not in matrix_df.columns:
            row = _blank_master_row(predictor, role, "source")
            row["fit_status"] = FIT_NOT_FITTED
            row["reason"] = f"predictor column {predictor!r} not present in the analysis matrix"
            rows.append(row)
            continue

        data = matrix_df[[outcome_col, predictor]].dropna()
        groups = subject_groups.loc[data.index] if subject_groups is not None else None
        n_subjects = int(groups.nunique()) if groups is not None else None
        model_n = len(data)
        model_events = int((data[outcome_col] == 1).sum())
        model_non_events = int((data[outcome_col] == 0).sum())

        if role == ROLE_BINARY:
            result = fit_univariable_binary(
                matrix_df, outcome_col, predictor, subject_groups=subject_groups,
                reference=str(ref_level),
            )
            row = _blank_master_row(predictor, role, "source")
            support = _binary_support(data, outcome_col, predictor)
            row.update(
                reference_level=ref_level,
                reporting_unit=reporting_unit,
                fit_status=result.fit_status,
                separation_status=result.separation_status,
                support_status=result.support_status,
                model_analysis_N=model_n,
                model_events=model_events,
                model_non_events=model_non_events,
                model_unique_subjects=n_subjects,
                odds_ratio=result.odds_ratio,
                ci_low=result.ci_low,
                ci_high=result.ci_high,
                coef_p_value=result.p_value,
                reason=result.notes or "",
                **support,
            )
            rows.append(row)

        elif role in (ROLE_CONTINUOUS, ROLE_COUNT) and ff_status == FF_LINEAR_APPROVED:
            unit_scale = float(scale) if scale is not None and not pd.isna(scale) else 1.0
            result = fit_univariable_continuous(
                matrix_df, outcome_col, predictor, subject_groups=subject_groups,
                unit_scale=unit_scale, unit_label=str(reporting_unit),
            )
            row = _blank_master_row(predictor, role, "source")
            row.update(
                reporting_unit=reporting_unit,
                continuous_unit_scale=unit_scale,
                fit_status=result.fit_status,
                separation_status=result.separation_status,
                support_status=result.support_status,
                model_analysis_N=model_n,
                model_events=model_events,
                model_non_events=model_non_events,
                model_unique_subjects=n_subjects,
                odds_ratio=result.odds_ratio,
                ci_low=result.ci_low,
                ci_high=result.ci_high,
                coef_p_value=result.p_value,
                effect_representation=EFFECT_REPRESENTATION_LINEAR,
                spline_df=None,
                reason=(
                    result.notes
                    or "model_analysis_N / model_events / model_non_events describe sample "
                    "and fit adequacy only (a per-unit continuous/count effect has no "
                    "exposed-vs-unexposed contrast cells)"
                ),
            )
            rows.append(row)

        elif role in (ROLE_CONTINUOUS, ROLE_COUNT) and ff_status == FF_NONLINEAR_APPROVED:
            # FINAL FUNCTIONAL-FORM LOCK: fixed natural cubic spline (df=3), no
            # single OR -- the source row carries a spline omnibus cluster-
            # robust Wald p-value in omnibus_p_value, never coef_p_value /
            # odds_ratio / ci_low / ci_high (those stay None/NaN by design).
            result = fit_univariable_nonlinear_spline(
                matrix_df, outcome_col, predictor, subject_groups=subject_groups,
                spline_df=SPLINE_DF,
            )
            row = _blank_master_row(predictor, role, "source")
            row.update(
                reporting_unit=reporting_unit,
                continuous_unit_scale=None,
                fit_status=result.fit_status,
                separation_status=result.separation_status,
                support_status=result.support_status,
                model_analysis_N=model_n,
                model_events=model_events,
                model_non_events=model_non_events,
                model_unique_subjects=n_subjects,
                odds_ratio=None,
                ci_low=None,
                ci_high=None,
                coef_p_value=None,
                omnibus_p_value=result.p_value,
                effect_representation=EFFECT_REPRESENTATION_NONLINEAR_SPLINE,
                spline_df=SPLINE_DF,
                reason=(
                    result.notes
                    or "nonlinear spline representation (df=3); no single OR is reported -- "
                    "see omnibus_p_value for the source-level spline omnibus cluster-robust "
                    "Wald association"
                ),
            )
            rows.append(row)

        elif role == ROLE_CATEGORICAL:
            # Centralized publication-label preparation layer (Functional-
            # Form Methodological Correction pass §7): the representation
            # contract is the sole source of truth for whether a predictor's
            # stored analysis-matrix values need mapping to publication
            # labels (e.g. smoking/mode_of_conception's raw integer codes)
            # or already ARE the publication labels (the derived_* /
            # PIH-spectrum categoricals) -- never special-cased by name here.
            try:
                prepared_series = prepare_predictor_for_publication_inference(matrix_df, predictor, spec)
            except PublicationLabelMappingError as exc:
                row = _blank_master_row(predictor, role, "source")
                row["fit_status"] = FIT_NOT_FITTED
                row["reason"] = f"publication-label preparation failed: {exc}"
                rows.append(row)
                continue
            prepared_df = matrix_df[[outcome_col]].copy()
            prepared_df[predictor] = prepared_series
            cat = fit_univariable_categorical(
                prepared_df, outcome_col, predictor, reference_level=str(ref_level),
                subject_groups=subject_groups,
                category_order=spec.get("category_order"),
            )
            source_row = _blank_master_row(predictor, role, "source")
            source_fit = (
                FIT_OK if cat.omnibus_status == FIT_OK and cat.omnibus_p_value is not None
                else FIT_NOT_RELIABLE
            )
            source_row.update(
                reference_level=ref_level,
                fit_status=source_fit,
                # Never claim SUPPORT_OK for the whole categorical source: support
                # is inherently level-specific (some levels can be sparse while
                # others are not). This is reporting only, never an eligibility
                # filter -- the per-level rows below carry their own real
                # support_status from _support_status().
                support_status=SUPPORT_SEE_LEVEL_SUPPORT,
                separation_status=cat.separation_status,
                model_analysis_N=model_n,
                model_events=model_events,
                model_non_events=model_non_events,
                model_unique_subjects=n_subjects,
                omnibus_p_value=cat.omnibus_p_value,
                reason=(
                    "categorical source-level omnibus test (one p-value per source predictor); "
                    "see the per-level rows below for level-specific support_status "
                    "(support_status here is SEE_LEVEL_SUPPORT, not an eligibility filter)"
                    if source_fit == FIT_OK
                    else (
                        cat.omnibus_reason
                        or "categorical omnibus not reliably estimable; see per-level rows for support"
                    )
                ),
            )
            rows.append(source_row)

            for lvl in cat.level_results:
                lvl_row = _blank_master_row(predictor, role, "level")
                lvl_row.update(
                    level=lvl.level,
                    reference_level=ref_level,
                    fit_status=lvl.fit_status,
                    separation_status=lvl.separation_status,
                    support_status=lvl.support_status,
                    model_analysis_N=model_n,
                    model_events=model_events,
                    model_non_events=model_non_events,
                    model_unique_subjects=n_subjects,
                    level_n=lvl.analysis_n,
                    level_events=lvl.events,
                    level_non_events=lvl.non_events,
                    level_unique_subjects=lvl.unique_subject_groups,
                    odds_ratio=lvl.odds_ratio,
                    ci_low=lvl.ci_low,
                    ci_high=lvl.ci_high,
                    coef_p_value=lvl.p_value,
                    reason=lvl.notes or "categorical level-specific contrast vs reference",
                )
                rows.append(lvl_row)
        else:  # pragma: no cover - guarded by contract validation
            raise ValueError(f"unexpected inferential_role {role!r} for {predictor!r}")

    master_df = pd.DataFrame(rows, columns=MASTER_COLUMNS)

    n_source = int((master_df["row_type"] == "source").sum())
    if n_source != len(contract_df):
        raise ValueError(
            f"univariable master has {n_source} source rows, expected {len(contract_df)} "
            "(one per source predictor)"
        )
    if list(master_df.loc[master_df["row_type"] == "source", "predictor"]) != list(
        contract_df["predictor"]
    ):
        raise ValueError("univariable master source rows are not in canonical registry order")

    return master_df


def build_predictor_level_hypothesis_table(master_df: pd.DataFrame) -> pd.DataFrame:
    """Exactly one source-level hypothesis row per source predictor.

    Categorical predictors contribute their single source-level OMNIBUS
    p-value — never one row per level. DESCRIPTIVE_ONLY / PENDING / failed
    fits contribute a ``not_estimable`` row with ``raw_p = None``.
    """
    source = master_df[master_df["row_type"] == "source"].copy()

    records: list[dict] = []
    for _, r in source.iterrows():
        role = r["inferential_role"]
        fit_status = r["fit_status"]
        raw_p = None
        hypothesis_type = HYPOTHESIS_NOT_ESTIMABLE

        estimable = fit_status == FIT_OK
        is_nonlinear_spline = r.get("effect_representation") == EFFECT_REPRESENTATION_NONLINEAR_SPLINE
        if role in (ROLE_CONTINUOUS, ROLE_COUNT) and is_nonlinear_spline and estimable and r["omnibus_p_value"] is not None:
            # FINAL FUNCTIONAL-FORM LOCK: the nonlinear spline's ONE source-level
            # hypothesis is its omnibus p-value -- individual spline-basis
            # coefficient p-values never enter the BH family.
            hypothesis_type, raw_p = HYPOTHESIS_NONLINEAR_SPLINE_OMNIBUS, r["omnibus_p_value"]
        elif role == ROLE_BINARY and estimable and r["coef_p_value"] is not None:
            hypothesis_type, raw_p = HYPOTHESIS_BINARY, r["coef_p_value"]
        elif role == ROLE_CONTINUOUS and estimable and r["coef_p_value"] is not None:
            hypothesis_type, raw_p = HYPOTHESIS_CONTINUOUS, r["coef_p_value"]
        elif role == ROLE_COUNT and estimable and r["coef_p_value"] is not None:
            hypothesis_type, raw_p = HYPOTHESIS_COUNT, r["coef_p_value"]
        elif role == ROLE_CATEGORICAL and estimable and r["omnibus_p_value"] is not None:
            hypothesis_type, raw_p = HYPOTHESIS_CATEGORICAL_OMNIBUS, r["omnibus_p_value"]

        if raw_p is not None and pd.isna(raw_p):
            raw_p, hypothesis_type = None, HYPOTHESIS_NOT_ESTIMABLE

        records.append(
            {
                "predictor": r["predictor"],
                "inferential_role": role,
                "hypothesis_type": hypothesis_type,
                "raw_p": raw_p,
                "fit_status": fit_status,
            }
        )

    hypothesis_df = pd.DataFrame(
        records,
        columns=["predictor", "inferential_role", "hypothesis_type", "raw_p", "fit_status"],
    )

    if hypothesis_df["predictor"].duplicated().any():
        raise ValueError("hypothesis table has more than one row for a source predictor")
    if list(hypothesis_df["predictor"]) != list(source["predictor"]):
        raise ValueError("hypothesis table lost canonical predictor order")

    return hypothesis_df


def apply_global_bh(hypothesis_df: pd.DataFrame) -> pd.DataFrame:
    """One exploratory predictor-level Benjamini-Hochberg family.

    The family is every estimable source-level raw p-value among the source
    predictors — binary / continuous / count coefficient p-values and
    categorical OMNIBUS p-values, combined into a single BH pass. Categorical
    level-specific p-values never enter this family. Non-estimable / PENDING /
    DESCRIPTIVE_ONLY predictors stay in the table with ``bh_q = None``.
    """
    out = hypothesis_df.copy()
    raw_p = list(out["raw_p"])
    out["bh_q"] = benjamini_hochberg(raw_p)
    out["in_bh_family"] = [p is not None and not pd.isna(p) for p in raw_p]
    return out[
        ["predictor", "hypothesis_type", "raw_p", "bh_q", "in_bh_family", "fit_status"]
    ]


def benjamini_hochberg(p_values: list[float | None]) -> list[float | None]:
    """Exploratory BH-FDR q-values. None entries (non-estimable p-values) pass through as None.

    Per the task brief, q-values here are a research aid only — never used to
    decide predictive-model eligibility or to delete predictors from tables.
    """
    indexed = [(i, p) for i, p in enumerate(p_values) if p is not None and not pd.isna(p)]
    if not indexed:
        return [None] * len(p_values)

    indexed.sort(key=lambda x: x[1])
    m = len(indexed)
    q_values: dict[int, float] = {}
    prev_q = 1.0
    for rank, (i, p) in reversed(list(enumerate(indexed, start=1))):
        q = min(prev_q, p * m / rank)
        q_values[i] = q
        prev_q = q

    return [q_values.get(i) for i in range(len(p_values))]

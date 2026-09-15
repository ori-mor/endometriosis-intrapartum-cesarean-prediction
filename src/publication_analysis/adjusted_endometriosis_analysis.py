"""Adjusted endometriosis-specific association analysis (Adjusted Association
Design Lock, Checkpoint C -- APPROVED).

Fits ONE endometriosis-specific predictor at a time, each alongside a small,
pre-specified conventional-covariate adjustment set -- never one giant model
with all 35 endometriosis predictors together (that would be badly
underpowered at 61 events and would conflate co-linear endometriosis
sub-phenotypes).

Two adjustment cores are locked (methodological/clinical sign-off already
given -- these are NOT tunable, NOT swappable per-exposure, and NOT chosen by
any statistical criterion):

    PRIMARY_ADJUSTMENT_SET     = AGE + nulliparity + S_P_CS
    SENSITIVITY_ADJUSTMENT_SET = PRIMARY_ADJUSTMENT_SET + mode_of_conception_ivf_vs_all

Purpose: adjusted ASSOCIATION estimation, not causal-effect estimation, not
prediction-model development.

Only Class A (``STANDARD_ADJUSTED_MODEL_FEASIBLE``) and Class B
(``STANDARD_ADJUSTED_MODEL_HIGH_CAUTION``) exposures
(``endometriosis_adjusted_feasibility.py``) are fit here. Class C
(``STANDARD_ADJUSTED_MODEL_NOT_DEFENSIBLE``) exposures are never fit with
ordinary logistic regression -- they are represented with an explicit
``NOT_FITTED`` status and a name-keyed structural reason.

Before trusting any ordinary logistic estimate, a deterministic structural
estimability gate is applied (zero exposure-by-outcome cell for binary; any
zero-event/zero-non-event categorical level) -- consistent with Checkpoint C.
No rescue via Firth, category collapsing, continuity correction, or ad-hoc
penalization is performed; a non-estimable model is marked
``STANDARD_OR_NOT_RELIABLY_ESTIMABLE`` with descriptive support retained.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from publication_analysis.endometriosis_adjusted_feasibility import (
    CATEGORICAL_EXPOSURES,
    CLASS_C,
    caution_reason,
    classify,
)
from publication_analysis.publication_representations import (
    _BINARY_EXPLICIT_SEMANTICS,
    _CATEGORICAL_APPROVED,
)
from publication_analysis.univariable_analysis import (
    FIT_NOT_FITTED,
    FIT_NOT_RELIABLE,
    FIT_OK,
    SEPARATION_COMPLETE,
    SEPARATION_NONE,
    SEPARATION_OTHER,
    SEPARATION_SINGLE_CASE,
    SUPPORT_INSUFFICIENT,
    SUPPORT_SEE_LEVEL_SUPPORT,
    _categorical_descriptive_level_row,
    _fit_logit,
    _ordered_non_reference_levels,
    _support_status,
)

# ---------------------------------------------------------------------------
# LOCKED adjustment cores -- see module docstring. Never altered based on a
# univariable p-value, a LASSO selection result, or an exposure's observed OR.
# ---------------------------------------------------------------------------
PRIMARY_ADJUSTMENT_SET: list[str] = ["AGE", "nulliparity", "S_P_CS"]
SENSITIVITY_ADJUSTMENT_SET: list[str] = PRIMARY_ADJUSTMENT_SET + ["mode_of_conception_ivf_vs_all"]

MODEL_VARIANT_PRIMARY = "PRIMARY"
MODEL_VARIANT_SENSITIVITY_IVF = "SENSITIVITY_IVF"

ADJUSTMENT_SETS_BY_VARIANT: dict[str, list[str]] = {
    MODEL_VARIANT_PRIMARY: PRIMARY_ADJUSTMENT_SET,
    MODEL_VARIANT_SENSITIVITY_IVF: SENSITIVITY_ADJUSTMENT_SET,
}

ROW_TYPE_SOURCE = "source"
ROW_TYPE_LEVEL = "level"


@dataclass
class AdjustedResult:
    exposure: str
    exposure_class: str
    row_type: str
    level: str | None
    reference_level: str | None
    model_variant: str
    comparison: str
    n: int
    events: int
    non_events: int
    unique_subject_groups: int | None
    adjusted_or: float | None
    adjusted_ci_low: float | None
    adjusted_ci_high: float | None
    adjusted_p: float | None
    fit_status: str
    separation_status: str
    support_status: str
    caution_flag: bool
    caution_reason: str
    notes: str = ""


def build_adjusted_formula(outcome_col: str, exposure_term: str, adjustment_cols: list[str]) -> str:
    """Build the patsy formula ``outcome ~ exposure_term + adjustment_set`` (additive, no interactions)."""
    terms = [exposure_term] + list(adjustment_cols)
    return f"{outcome_col} ~ " + " + ".join(terms)


def _complete_case(df: pd.DataFrame, required_cols: list[str]) -> pd.DataFrame:
    missing_required = [c for c in required_cols if c not in df.columns]
    if missing_required:
        raise KeyError(f"Missing required columns for adjusted analysis: {missing_required}")
    return df[required_cols].dropna()


def binary_exposure_comparison_label(exposure_col: str) -> str:
    """Publication-safe label for the coded binary contrast.

    Explicit clinical wording is used only when the representation contract has
    a predictor-specific 0/1 semantic source. Otherwise the adjusted OR remains
    correctly labeled as the numeric coded contrast.
    """
    semantics = _BINARY_EXPLICIT_SEMANTICS.get(exposure_col)
    if semantics is None:
        return "value 1 vs value 0"
    return f"{semantics['comparison_label']} vs {semantics['reference_label']}"


def fit_adjusted_binary_exposure(
    df: pd.DataFrame,
    outcome_col: str,
    exposure_col: str,
    adjustment_cols: list[str],
    model_variant: str,
    subject_groups: pd.Series | None = None,
) -> AdjustedResult:
    """Fit one adjusted model for a binary endometriosis exposure."""
    exposure_class = classify(exposure_col)
    reason = caution_reason(exposure_col)
    required_cols = [outcome_col, exposure_col] + list(adjustment_cols)
    data = _complete_case(df, required_cols)
    n = len(data)
    events = int(data[outcome_col].sum())
    non_events = n - events
    groups = subject_groups.loc[data.index] if subject_groups is not None else None
    unique_groups = int(groups.nunique()) if groups is not None else None

    crosstab = pd.crosstab(data[exposure_col], data[outcome_col])
    min_cell = int(crosstab.values.min()) if crosstab.size else 0
    support_status = _support_status(min_cell)

    if crosstab.shape[0] < 2 or (crosstab.values == 0).any():
        return AdjustedResult(
            exposure=exposure_col,
            exposure_class=exposure_class,
            row_type=ROW_TYPE_SOURCE,
            level=None,
            reference_level=None,
            model_variant=model_variant,
            comparison=binary_exposure_comparison_label(exposure_col),
            n=n,
            events=events,
            non_events=non_events,
            unique_subject_groups=unique_groups,
            adjusted_or=None,
            adjusted_ci_low=None,
            adjusted_ci_high=None,
            adjusted_p=None,
            fit_status=FIT_NOT_RELIABLE,
            separation_status=SEPARATION_COMPLETE if crosstab.shape[0] >= 2 else SEPARATION_SINGLE_CASE,
            support_status=support_status,
            caution_flag=exposure_class != "STANDARD_ADJUSTED_MODEL_FEASIBLE",
            caution_reason=reason,
            notes="Zero-count cell in the exposure-by-outcome table (complete separation) or single exposure level.",
        )

    formula = build_adjusted_formula(outcome_col, exposure_col, adjustment_cols)
    result, separation_status, fit_status = _fit_logit(formula, data, groups)

    if fit_status != FIT_OK or result is None:
        return AdjustedResult(
            exposure=exposure_col,
            exposure_class=exposure_class,
            row_type=ROW_TYPE_SOURCE,
            level=None,
            reference_level=None,
            model_variant=model_variant,
            comparison=binary_exposure_comparison_label(exposure_col),
            n=n,
            events=events,
            non_events=non_events,
            unique_subject_groups=unique_groups,
            adjusted_or=None,
            adjusted_ci_low=None,
            adjusted_ci_high=None,
            adjusted_p=None,
            fit_status=fit_status,
            separation_status=separation_status,
            support_status=support_status,
            caution_flag=exposure_class != "STANDARD_ADJUSTED_MODEL_FEASIBLE",
            caution_reason=reason,
            notes="Adjusted logistic fit did not converge or was flagged unstable.",
        )

    coef = result.params[exposure_col]
    ci_low, ci_high = result.conf_int().loc[exposure_col]
    p_value = result.pvalues[exposure_col]

    return AdjustedResult(
        exposure=exposure_col,
        exposure_class=exposure_class,
        row_type=ROW_TYPE_SOURCE,
        level=None,
        reference_level=None,
        model_variant=model_variant,
        comparison=binary_exposure_comparison_label(exposure_col),
        n=n,
        events=events,
        non_events=non_events,
        unique_subject_groups=unique_groups,
        adjusted_or=float(np.exp(coef)),
        adjusted_ci_low=float(np.exp(ci_low)),
        adjusted_ci_high=float(np.exp(ci_high)),
        adjusted_p=float(p_value),
        fit_status=FIT_OK,
        separation_status=SEPARATION_NONE,
        support_status=support_status,
        caution_flag=exposure_class != "STANDARD_ADJUSTED_MODEL_FEASIBLE",
        caution_reason=reason,
    )


def fit_adjusted_categorical_exposure(
    df: pd.DataFrame,
    outcome_col: str,
    exposure_col: str,
    adjustment_cols: list[str],
    model_variant: str,
    subject_groups: pd.Series | None = None,
) -> list[AdjustedResult]:
    """Fit one adjusted model for a categorical endometriosis exposure.

    Returns one source-level omnibus row (``row_type='source'``) plus one
    level-detail row per non-reference level (``row_type='level'``). Uses
    treatment/dummy coding against the approved reference level; never an
    ordinal numeric slope.
    """
    exposure_class = classify(exposure_col)
    reason = caution_reason(exposure_col)
    spec = _CATEGORICAL_APPROVED[exposure_col]
    reference_level = spec["reference_level"]
    category_order = spec["category_order"]

    required_cols = [outcome_col, exposure_col] + list(adjustment_cols)
    data = _complete_case(df, required_cols)
    n = len(data)
    events = int(data[outcome_col].sum())
    non_events = n - events
    groups = subject_groups.loc[data.index] if subject_groups is not None else None
    unique_groups = int(groups.nunique()) if groups is not None else None

    observed_levels = sorted(data[exposure_col].astype(str).unique())

    def _source_row(
        fit_status: str,
        separation_status: str,
        support_status: str,
        omnibus_p: float | None = None,
        notes: str = "",
    ) -> AdjustedResult:
        return AdjustedResult(
            exposure=exposure_col,
            exposure_class=exposure_class,
            row_type=ROW_TYPE_SOURCE,
            level=None,
            reference_level=reference_level,
            model_variant=model_variant,
            comparison="categorical source-level omnibus (cluster-robust Wald)",
            n=n,
            events=events,
            non_events=non_events,
            unique_subject_groups=unique_groups,
            adjusted_or=None,
            adjusted_ci_low=None,
            adjusted_ci_high=None,
            adjusted_p=omnibus_p,
            fit_status=fit_status,
            separation_status=separation_status,
            support_status=support_status,
            caution_flag=exposure_class != "STANDARD_ADJUSTED_MODEL_FEASIBLE",
            caution_reason=reason,
            notes=notes,
        )

    if reference_level not in observed_levels:
        return [
            _source_row(
                FIT_NOT_RELIABLE,
                SEPARATION_OTHER,
                SUPPORT_INSUFFICIENT,
                notes=f"reference level {reference_level!r} is not observed in the complete-case data.",
            )
        ]

    contingency = pd.crosstab(data[exposure_col].astype(str), data[outcome_col])
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
            gate_separation = SEPARATION_SINGLE_CASE
            omnibus_notes = (
                f"Standard categorical adjusted logistic MLE not reliably estimable: fewer than "
                f"two categories of {exposure_col!r} are observed in the complete-case data."
            )
        else:
            gate_separation = SEPARATION_COMPLETE
            omnibus_notes = (
                f"Standard categorical adjusted logistic MLE not reliably estimable: category(ies) "
                f"{zero_cell_levels} have a zero outcome cell (0 events or 0 non-events) -> complete "
                f"separation within a category. The affected category is retained (not collapsed); "
                f"no OR/CI/coefficient p is reported from the full model."
            )
        level_notes = (
            "Standard categorical adjusted MLE not reliably estimable (at least one category has a "
            "zero outcome cell); descriptive counts only, no OR/CI/coefficient p."
        )
        level_rows = [
            _to_adjusted_level_row(
                _categorical_descriptive_level_row(
                    data, outcome_col, exposure_col, reference_level, lvl, groups,
                    SEPARATION_COMPLETE if lvl in zero_cell_levels else SEPARATION_NONE,
                    level_notes,
                ),
                exposure_class, model_variant, reason,
            )
            for lvl in _ordered_non_reference_levels(observed_levels, reference_level, category_order)
        ]
        return [_source_row(FIT_NOT_RELIABLE, gate_separation, SUPPORT_SEE_LEVEL_SUPPORT, notes=omnibus_notes)] + level_rows

    formula = build_adjusted_formula(
        outcome_col,
        f"C({exposure_col}, Treatment(reference='{reference_level}'))",
        adjustment_cols,
    )
    result, separation_status, fit_status = _fit_logit(formula, data, groups)

    if fit_status != FIT_OK or result is None:
        level_notes = "Adjusted categorical logistic fit did not converge or was flagged unstable."
        level_rows = [
            _to_adjusted_level_row(
                _categorical_descriptive_level_row(
                    data, outcome_col, exposure_col, reference_level, lvl, groups,
                    separation_status, level_notes,
                ),
                exposure_class, model_variant, reason,
            )
            for lvl in _ordered_non_reference_levels(observed_levels, reference_level, category_order)
        ]
        return [
            _source_row(fit_status, separation_status, SUPPORT_SEE_LEVEL_SUPPORT, notes=level_notes)
        ] + level_rows

    levels_by_label: dict[str, AdjustedResult] = {}
    for term in result.params.index:
        if not term.startswith(f"C({exposure_col}"):
            continue
        level_label = term.split("T.", 1)[-1].rstrip("]")
        coef = result.params[term]
        ci_low, ci_high = result.conf_int().loc[term]
        p_value = result.pvalues[term]
        level_mask = data[exposure_col].astype(str) == level_label
        n_level = int(level_mask.sum())
        events_level = int(data.loc[level_mask, outcome_col].sum())
        non_events_level = n_level - events_level
        level_groups = groups.loc[data.index[level_mask]] if groups is not None else None
        levels_by_label[level_label] = AdjustedResult(
            exposure=exposure_col,
            exposure_class=exposure_class,
            row_type=ROW_TYPE_LEVEL,
            level=level_label,
            reference_level=reference_level,
            model_variant=model_variant,
            comparison=f"{level_label} vs. {reference_level}",
            n=n_level,
            events=events_level,
            non_events=non_events_level,
            unique_subject_groups=int(level_groups.nunique()) if level_groups is not None else None,
            adjusted_or=float(np.exp(coef)),
            adjusted_ci_low=float(np.exp(ci_low)),
            adjusted_ci_high=float(np.exp(ci_high)),
            adjusted_p=float(p_value),
            fit_status=FIT_OK,
            separation_status=SEPARATION_NONE,
            support_status=_support_status(min(events_level, non_events_level)),
            caution_flag=exposure_class != "STANDARD_ADJUSTED_MODEL_FEASIBLE",
            caution_reason=reason,
        )

    ordered_labels = _ordered_non_reference_levels(list(levels_by_label.keys()), reference_level, category_order)
    level_rows = [levels_by_label[lbl] for lbl in ordered_labels if lbl in levels_by_label]
    level_rows += [lr for lbl, lr in levels_by_label.items() if lbl not in ordered_labels]

    omnibus_p_value = None
    omnibus_status = FIT_OK
    omnibus_notes = ""
    try:
        wald = result.wald_test_terms(skip_single=False)
        term_name = [t for t in wald.table.index if exposure_col in t]
        if term_name:
            omnibus_p_value = float(wald.table.loc[term_name[0], "pvalue"])
        else:
            omnibus_status = FIT_NOT_RELIABLE
            omnibus_notes = "categorical omnibus Wald term not found"
    except Exception:  # noqa: BLE001
        omnibus_status = FIT_NOT_RELIABLE
        omnibus_notes = "categorical omnibus Wald test not computable"

    return [
        _source_row(omnibus_status, SEPARATION_NONE, SUPPORT_SEE_LEVEL_SUPPORT, omnibus_p_value, omnibus_notes)
    ] + level_rows


def _to_adjusted_level_row(univariable_level_row, exposure_class: str, model_variant: str, reason: str) -> AdjustedResult:
    """Adapt a univariable_analysis descriptive ``UnivariableResult`` level row
    (counts-only, no OR/CI/p) into the adjusted-analysis ``AdjustedResult`` shape."""
    r = univariable_level_row
    return AdjustedResult(
        exposure=r.predictor,
        exposure_class=exposure_class,
        row_type=ROW_TYPE_LEVEL,
        level=r.level,
        reference_level=r.reference,
        model_variant=model_variant,
        comparison=f"{r.level} vs. {r.reference}",
        n=r.analysis_n,
        events=r.events,
        non_events=r.non_events,
        unique_subject_groups=r.unique_subject_groups,
        adjusted_or=None,
        adjusted_ci_low=None,
        adjusted_ci_high=None,
        adjusted_p=None,
        fit_status=r.fit_status,
        separation_status=r.separation_status,
        support_status=r.support_status,
        caution_flag=exposure_class != "STANDARD_ADJUSTED_MODEL_FEASIBLE",
        caution_reason=reason,
        notes=r.notes,
    )


def _not_fitted_row(
    df: pd.DataFrame,
    outcome_col: str,
    exposure_col: str,
    model_variant: str,
    subject_groups: pd.Series | None = None,
) -> AdjustedResult:
    """Class-C descriptive-only row: never fit with ordinary adjusted logistic regression."""
    exposure_class = classify(exposure_col)
    reason = caution_reason(exposure_col)
    data = df[[outcome_col, exposure_col]].dropna()
    n = len(data)
    events = int(data[outcome_col].sum())
    non_events = n - events
    groups = subject_groups.loc[data.index] if subject_groups is not None else None
    unique_groups = int(groups.nunique()) if groups is not None else None
    is_categorical = exposure_col in CATEGORICAL_EXPOSURES
    reference_level = _CATEGORICAL_APPROVED[exposure_col]["reference_level"] if is_categorical else None
    return AdjustedResult(
        exposure=exposure_col,
        exposure_class=exposure_class,
        row_type=ROW_TYPE_SOURCE,
        level=None,
        reference_level=reference_level,
        model_variant=model_variant,
        comparison="not fitted (class C -- STANDARD_ADJUSTED_MODEL_NOT_DEFENSIBLE)",
        n=n,
        events=events,
        non_events=non_events,
        unique_subject_groups=unique_groups,
        adjusted_or=None,
        adjusted_ci_low=None,
        adjusted_ci_high=None,
        adjusted_p=None,
        fit_status=FIT_NOT_FITTED,
        separation_status=SEPARATION_OTHER,
        support_status=SUPPORT_INSUFFICIENT,
        caution_flag=True,
        caution_reason=reason,
        notes="Class C exposure: never fit with ordinary adjusted logistic regression per the approved design lock.",
    )


def fit_adjusted_exposure(
    df: pd.DataFrame,
    outcome_col: str,
    exposure_col: str,
    model_variant: str,
    subject_groups: pd.Series | None = None,
) -> list[AdjustedResult]:
    """Dispatch one exposure/variant combination to the correct fitter.

    Class C exposures return a single ``NOT_FITTED`` row. Categorical
    exposures (class A/B only) return one source omnibus row plus level rows.
    Binary exposures return a single source row.
    """
    exposure_class = classify(exposure_col)
    if exposure_class == CLASS_C:
        return [_not_fitted_row(df, outcome_col, exposure_col, model_variant, subject_groups)]

    adjustment_cols = ADJUSTMENT_SETS_BY_VARIANT[model_variant]
    if exposure_col in CATEGORICAL_EXPOSURES:
        return fit_adjusted_categorical_exposure(
            df, outcome_col, exposure_col, adjustment_cols, model_variant, subject_groups
        )
    return [
        fit_adjusted_binary_exposure(
            df, outcome_col, exposure_col, adjustment_cols, model_variant, subject_groups
        )
    ]


def run_adjusted_analysis_for_family(
    df: pd.DataFrame,
    outcome_col: str,
    endometriosis_predictors: list[str],
    subject_groups: pd.Series | None = None,
) -> pd.DataFrame:
    """Run PRIMARY and SENSITIVITY_IVF adjusted models across the endometriosis
    family. Every predictor gets a row for both model variants; class C
    predictors get a ``NOT_FITTED`` row for both variants (never an ordinary fit).
    """
    rows: list[AdjustedResult] = []
    for exposure in endometriosis_predictors:
        for model_variant in (MODEL_VARIANT_PRIMARY, MODEL_VARIANT_SENSITIVITY_IVF):
            rows.extend(
                fit_adjusted_exposure(df, outcome_col, exposure, model_variant, subject_groups)
            )
    return pd.DataFrame([r.__dict__ for r in rows])

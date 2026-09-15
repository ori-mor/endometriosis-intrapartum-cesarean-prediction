"""Table 1 — full descriptive cohort table (Section C).

Table 1 is DESCRIPTIVE only: Overall / Vaginal delivery / Intrapartum CS /
Missing n (%) for every eligible predictor, ordered by earliest entry stage.
No inferential p-values belong in this table (see ``univariable_analysis.py``
for a separate, optional supplementary group-comparison table).

Every function here is a pure function of a dataframe + column metadata, so
it is fully testable against synthetic data without touching the real
patient-level processed dataset.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from publication_analysis.publication_representations import (
    prepare_predictor_for_publication_inference,
)

MEAN_SD = "mean_sd"
MEDIAN_IQR = "median_iqr"

BINARY = "binary"
CATEGORICAL = "categorical"
CONTINUOUS = "continuous"
COUNT = "count"

DEFAULT_SKEW_THRESHOLD = 1.0


def variable_types_from_candidate_features(features_df: pd.DataFrame) -> dict[str, str]:
    """Map predictor -> {binary, categorical, continuous, count} from EDA C metadata."""
    return dict(zip(features_df["variable"], features_df["physical_variable_type"]))


def stage_map_from_candidate_features(features_df: pd.DataFrame) -> dict[str, int]:
    """Map predictor -> earliest_entry_stage (1/2/3) from EDA C metadata."""
    return dict(zip(features_df["variable"], features_df["earliest_entry_stage"]))


def default_distribution_rule(series: pd.Series, skew_threshold: float = DEFAULT_SKEW_THRESHOLD) -> str:
    """Transparent default rule: |skewness| > threshold -> median [IQR], else mean +/- SD.

    This is a default, not a formal normality test, and not the sole
    decision rule per the task brief — callers may pass a manual override
    per variable to ``summarize_continuous``/``build_table1``.
    """
    values = series.dropna().astype(float)
    if len(values) < 3:
        return MEAN_SD
    skew = values.skew()
    if pd.isna(skew):
        return MEAN_SD
    return MEDIAN_IQR if abs(skew) > skew_threshold else MEAN_SD


def summarize_continuous(series: pd.Series, rule: str | None = None) -> str:
    values = series.dropna().astype(float)
    if len(values) == 0:
        return "n/a"
    if rule is None:
        rule = default_distribution_rule(series)
    if rule == MEAN_SD:
        return f"{values.mean():.1f} ± {values.std():.1f}"
    if rule == MEDIAN_IQR:
        q1, median, q3 = values.quantile([0.25, 0.5, 0.75])
        return f"{median:.1f} [{q1:.1f}–{q3:.1f}]"
    raise ValueError(f"Unknown distribution rule: {rule!r}")


def summarize_binary(series: pd.Series) -> str:
    non_missing = series.dropna()
    n_non_missing = len(non_missing)
    if n_non_missing == 0:
        return "n/a"
    n_present = int((non_missing == 1).sum())
    pct = 100.0 * n_present / n_non_missing
    return f"{n_present} ({pct:.1f}%)"


def summarize_categorical(series: pd.Series) -> dict[str, str]:
    non_missing = series.dropna()
    n_non_missing = len(non_missing)
    counts = non_missing.value_counts()
    result = {}
    for level, n in counts.items():
        pct = 100.0 * n / n_non_missing if n_non_missing else 0.0
        result[str(level)] = f"{n} ({pct:.1f}%)"
    return result


# Tokens marking an explicit "not observed / not documented / unknown" category.
# These are always placed last, regardless of the neutral ordering of the rest.
_UNKNOWN_LIKE_TOKENS = (
    "unknown",
    "not_documented",
    "not documented",
    "not_performed",
    "not performed",
    "missing",
    "undocumented",
    "unspecified",
    "not_applicable",
    "not applicable",
)


def _is_unknown_like(level: str) -> bool:
    low = str(level).strip().lower()
    return any(token in low for token in _UNKNOWN_LIKE_TOKENS)


class UnexpectedCategoryLevelError(ValueError):
    """Raised when an observed categorical level is not covered by an
    explicit ``category_order`` supplied for that predictor.

    An explicit order is treated as a CLOSED set of allowed levels: every
    observed non-missing level must be represented in it. Silently appending
    an unlisted level (or silently dropping it) would let an unreviewed
    category slip into a publication table without anyone noticing.
    """


def order_categorical_levels(
    observed_levels, explicit_order: list | None = None, predictor: str | None = None,
) -> list[str]:
    """Deterministic display order for a categorical variable's levels.

    * With ``explicit_order``: treated as a CLOSED set. Every observed
      non-missing level must appear in ``explicit_order`` — if any observed
      level is missing from it, this raises ``UnexpectedCategoryLevelError``
      (fail loud: never silently append, never silently drop). Levels present
      in ``explicit_order`` are emitted in that order; unknown/not-documented
      -style levels among them are still forced last. ``explicit_order`` MAY
      contain levels that are not observed in this particular data slice —
      those are simply not emitted (this is intentional: the same explicit
      order is reused across Overall / subgroup columns that may not each
      observe every level).
    * Without ``explicit_order``: a neutral, deterministic order —
      case-insensitive lexical sort — never a frequency (``value_counts``)
      order and never outcome-driven, with unknown/not-documented-style
      categories forced last. This neutral path is unaffected by the
      fail-loud check above and remains available for
      PENDING_REPRESENTATION_REVIEW categoricals that have no explicit order.

    Parameters
    ----------
    predictor: optional predictor name, included in the raised exception
        message only (for a clearer error when called from ``build_table1``).
    """
    observed = [str(x) for x in observed_levels]

    if explicit_order:
        explicit_order = [str(x) for x in explicit_order]
        unexpected = sorted(
            (l for l in set(observed) if l not in explicit_order), key=lambda s: s.lower()
        )
        if unexpected:
            pred_txt = f"predictor {predictor!r}: " if predictor else ""
            raise UnexpectedCategoryLevelError(
                f"{pred_txt}observed categorical level(s) {unexpected} are not covered by "
                f"the supplied explicit category_order {explicit_order}. An explicit "
                "category_order must account for every observed level — extend the "
                "representation contract's category_order (or leave the predictor "
                "PENDING_REPRESENTATION_REVIEW) rather than silently appending or "
                "dropping an unexpected level."
            )

        seen: set[str] = set()
        ordered: list[str] = []
        for level in explicit_order:
            if level in observed and level not in seen and not _is_unknown_like(level):
                ordered.append(level)
                seen.add(level)
        # Unknown-like levels that ARE part of the explicit order (e.g. an
        # explicitly enumerated "not_documented" level) still go last.
        unknown_like_in_order = [
            l for l in explicit_order if l in observed and l not in seen and _is_unknown_like(l)
        ]
        ordered.extend(unknown_like_in_order)
        return ordered

    # --- no explicit order: neutral deterministic ordering (unchanged) ------
    seen: set[str] = set()
    remaining_known = sorted(
        (l for l in observed if not _is_unknown_like(l)), key=lambda s: s.lower()
    )
    ordered = list(remaining_known)
    seen.update(remaining_known)

    unknown_like = sorted(
        (l for l in observed if l not in seen), key=lambda s: s.lower()
    )
    ordered.extend(unknown_like)
    return ordered


def summarize_missing(series: pd.Series) -> str:
    n_missing = int(series.isna().sum())
    pct = 100.0 * n_missing / len(series) if len(series) else 0.0
    return f"{n_missing} ({pct:.1f}%)"


@dataclass
class Table1Row:
    variable: str
    level: str | None
    overall: str
    group_0: str
    group_1: str
    missing: str
    stage: int


def resolve_distribution_rule(
    full_cohort_series: pd.Series,
    override: str | None = None,
    skew_threshold: float = DEFAULT_SKEW_THRESHOLD,
) -> str:
    """The single display rule for one continuous/count variable.

    Determined ONCE — from an explicit override if given, otherwise from the
    FULL-COHORT distribution — and then applied unchanged to the Overall,
    Vaginal-delivery and Intrapartum-CS columns. A variable is never shown as
    mean ± SD in one column and median [IQR] in another just because a
    subgroup distribution differs.
    """
    if override is not None:
        if override not in (MEAN_SD, MEDIAN_IQR):
            raise ValueError(f"Unknown distribution override: {override!r}")
        return override
    return default_distribution_rule(full_cohort_series, skew_threshold=skew_threshold)


def build_table1(
    df: pd.DataFrame,
    variables: list[str],
    variable_types: dict[str, str],
    stage_map: dict[str, int],
    outcome_col: str,
    distribution_overrides: dict[str, str] | None = None,
    category_order_map: dict[str, list] | None = None,
    representation_contract: pd.DataFrame | None = None,
    predictor_display_labels: dict[str, str] | None = None,
    group_0_label: str = "Vaginal delivery",
    group_1_label: str = "Intrapartum CS",
) -> pd.DataFrame:
    """Build the full descriptive Table 1, ordered by earliest entry stage.

    Parameters
    ----------
    df: analysis dataframe containing ``outcome_col`` and every entry in
        ``variables``.
    variables: predictor names to summarize (already restricted to the
        eligible 81-predictor pool by the caller).
    variable_types: predictor -> one of {binary, categorical, continuous, count}.
    stage_map: predictor -> earliest_entry_stage (1, 2, or 3), used for ordering only.
    outcome_col: binary 0/1 outcome column name.
    distribution_overrides: optional predictor -> {mean_sd, median_iqr} override
        for continuous/count variables. When absent, ONE rule is resolved from
        the full-cohort distribution and applied to all three columns.
    category_order_map: optional predictor -> explicit level display order.
        When a variable has no entry, a deterministic neutral order is used
        (lexical, never frequency-driven; explicit unknown-style levels last).
        A PENDING inferential representation is still described here — PENDING
        means "do not fit inferentially yet", not "hide from Table 1".
    representation_contract: optional publication representation contract
        (``publication_representations.build_publication_representation_contract()``
        output, one row per predictor, indexed by column ``predictor``). When
        given, every variable present in the contract is routed through
        ``prepare_predictor_for_publication_inference`` BEFORE summarization —
        this is the single shared publication-value preparation path also used
        by the inferential pipeline (``univariable_analysis.py``), so a
        raw-coded categorical (e.g. ``smoking``, ``mode_of_conception``) is
        mapped to its approved clinical label before ``category_order_map`` is
        applied against it. A predictor absent from the contract is passed
        through unchanged. Preparation failures (an unmapped raw code, a
        missing reference level, an observed level outside an approved
        ``category_order``) raise ``PublicationLabelMappingError`` — this
        table never silently guesses a label. When omitted (default), ``df``
        is used as-is, unchanged from prior behavior (covers synthetic tests
        that already supply publication-ready values directly).
    predictor_display_labels: optional predictor -> approved clinical display
        label (see ``publication_display_labels.py``). When given, an
        additional ``"Clinical Label"`` column is inserted after
        ``"Variable"`` — the technical ``"Variable"`` column is always kept
        unchanged alongside it for traceability. A predictor absent from the
        mapping keeps its bare technical name as the display label (never a
        fabricated clinical meaning). When omitted (default, unchanged from
        prior behavior), no such column is added.
    """
    distribution_overrides = distribution_overrides or {}
    category_order_map = category_order_map or {}
    if outcome_col not in df.columns:
        raise KeyError(f"Outcome column {outcome_col!r} not in dataframe")

    if representation_contract is not None:
        contract_by_pred = representation_contract.set_index("predictor")
        prepared_df = df.copy()
        for variable in variables:
            if variable in contract_by_pred.index:
                prepared_df[variable] = prepare_predictor_for_publication_inference(
                    df, variable, contract_by_pred.loc[variable]
                )
        df = prepared_df

    group_0 = df[df[outcome_col] == 0]
    group_1 = df[df[outcome_col] == 1]

    ordered_variables = sorted(variables, key=lambda v: (stage_map.get(v, 99), v))

    rows: list[Table1Row] = []
    for variable in ordered_variables:
        if variable not in df.columns:
            raise KeyError(f"Predictor {variable!r} not found in dataframe columns")
        var_type = variable_types.get(variable, CONTINUOUS)
        stage = stage_map.get(variable, 99)
        series = df[variable]

        if var_type == BINARY:
            rows.append(
                Table1Row(
                    variable=variable,
                    level=None,
                    overall=summarize_binary(series),
                    group_0=summarize_binary(group_0[variable]),
                    group_1=summarize_binary(group_1[variable]),
                    missing=summarize_missing(series),
                    stage=stage,
                )
            )
        elif var_type == CATEGORICAL:
            overall_levels = summarize_categorical(series)
            group_0_levels = summarize_categorical(group_0[variable])
            group_1_levels = summarize_categorical(group_1[variable])
            missing_str = summarize_missing(series)
            display_order = order_categorical_levels(
                overall_levels.keys(), category_order_map.get(variable), predictor=variable,
            )
            for idx, level in enumerate(display_order):
                rows.append(
                    Table1Row(
                        variable=variable,
                        level=level,
                        overall=overall_levels.get(level, "0 (0.0%)"),
                        group_0=group_0_levels.get(level, "0 (0.0%)"),
                        group_1=group_1_levels.get(level, "0 (0.0%)"),
                        missing=missing_str if idx == 0 else "",
                        stage=stage,
                    )
                )
        else:
            # ONE rule per variable: resolved from the full cohort (or an
            # explicit override) and applied to all three columns.
            rule = resolve_distribution_rule(
                series, distribution_overrides.get(variable)
            )
            rows.append(
                Table1Row(
                    variable=variable,
                    level=None,
                    overall=summarize_continuous(series, rule),
                    group_0=summarize_continuous(group_0[variable], rule),
                    group_1=summarize_continuous(group_1[variable], rule),
                    missing=summarize_missing(series),
                    stage=stage,
                )
            )

    table = pd.DataFrame(
        [
            {
                "Variable": r.variable if r.level is None else f"{r.variable}: {r.level}",
                **(
                    {"Clinical Label": predictor_display_labels.get(r.variable, r.variable)}
                    if predictor_display_labels is not None
                    else {}
                ),
                "Stage": r.stage,
                "Overall": r.overall,
                group_0_label: r.group_0,
                group_1_label: r.group_1,
                "Missing n (%)": r.missing,
            }
            for r in rows
        ]
    )
    return table

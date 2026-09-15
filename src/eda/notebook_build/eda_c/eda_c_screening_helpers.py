"""Small, independently-testable helpers used by eda_c_part4_screening.py.

Extracted so the exact logic exercised by the notebook can also be exercised
directly by unit tests, with no risk of the two silently drifting apart.
"""


def resolve_observed_series(variable, primary_df, fallback_df=None):
    """Return the actual observed-data Series for `variable`, or None.

    `primary_df` is checked first (e.g. the restricted analysis frame used for
    statistical screening); `fallback_df` (e.g. the full loaded dataset) is
    used only when `variable` is not a column of `primary_df`. This matters
    because some variables (e.g. those pending timing confirmation, or
    confirmed-intrapartum variables excluded from the pre-labor pool) are
    deliberately excluded from the restricted screening frame -- excluded
    from *statistical screening*, not absent from the *dataset*. Their real
    observed data still lives in `fallback_df` and must be used, never a
    placeholder.

    Single source of truth for this fallback preference -- every caller that
    needs the variable's real data (whether for a summary statistic or for
    type inference) must resolve it through this function, not reimplement
    the same primary/fallback lookup independently.
    """
    if variable in primary_df.columns:
        return primary_df[variable]
    if fallback_df is not None and variable in fallback_df.columns:
        return fallback_df[variable]
    return None


def compute_observed_variance_summary(variable, primary_df, fallback_df=None):
    """Return (non_missing_count, n_unique, zero_variance_flag) for `variable`,
    computed from its actual observed data (via `resolve_observed_series`).

    Bug fixed 2026-07-30 (Decision 37 / oligohydramnios): the previous
    behavior returned a hardcoded (0, 0) whenever a variable was absent from
    the restricted screening frame, which downstream code then read as "zero
    variance" -- an unrelated fact this function must never fabricate. "Not
    statistically screened" carries no information about non-missing count,
    unique-value count, or variance; only real observed data may answer those
    questions.

    Returns (0, 0, False) if `variable` is absent from both frames (no
    observed data available at all).
    """
    series = resolve_observed_series(variable, primary_df, fallback_df)

    if series is None:
        return 0, 0, False

    non_missing_count = int(series.notna().sum())
    n_unique = int(series.dropna().nunique())
    # Zero-variance policy: constant status may be audited across all variables,
    # but automatic zero-variance exclusion applies only within the relevant
    # analytical predictor scope. A true zero-variance exclusion has no missing
    # values and exactly one observed unique value; all-missing and partially
    # missing single-value variables are handled by missingness logic. Cohort
    # controls and other already-excluded variables retain their role reason.
    missing_count = int(series.isna().sum())
    zero_variance_flag = missing_count == 0 and n_unique == 1
    return non_missing_count, n_unique, zero_variance_flag


def compute_structural_applicability_aware_missing_pct(variable, df, gate):
    """Structural-applicability-aware missingness (Part B3, 2026-08-27
    correction): for a variable with a known not-applicable subgroup, the
    genuine-missingness percentage must be computed as
    `genuine_missing_applicable_n / applicable_n`, never as
    `df[variable].isna().mean()` over the whole cohort (which folds
    structural non-applicability into "missing" and can badly overstate the
    genuine rate -- e.g. PPROM: 96.3% whole-cohort NaN vs. 5.9%
    genuine-missing-within-applicable).

    `gate` is a resolved applicability-gate dict as returned by
    `structural_missingness_registry.applicability_gate_for(variable)`:
    {"gate_column", "gate_values", ...}. This function is deliberately
    generic (mask/rule-driven from whatever gate dict is passed in) -- it
    contains no PPROM-specific or any other single-variable special case.

    Returns None if `variable` is not a column of `df`, or if `gate` is None
    (no registered applicability gate -- caller should fall back to the
    ordinary whole-cohort `isna().mean()` computation in that case).

    Returns a dict: {"applicable_n", "structural_n", "observed_applicable_n",
    "genuine_missing_applicable_n", "genuine_missing_pct"}. All counts are
    computed LIVE from `df` -- never from a stored/expected denominator.
    """
    if variable not in df.columns or gate is None:
        return None
    gate_column = gate["gate_column"]
    if gate_column not in df.columns:
        return None
    applicable_mask = df[gate_column].isin(gate["gate_values"])
    applicable_n = int(applicable_mask.sum())
    structural_n = int((~applicable_mask).sum())
    applicable_series = df.loc[applicable_mask, variable]
    observed_applicable_n = int(applicable_series.notna().sum())
    genuine_missing_applicable_n = int(applicable_series.isna().sum())
    genuine_missing_pct = (
        round(genuine_missing_applicable_n / applicable_n * 100, 1) if applicable_n else 0.0
    )
    return {
        "applicable_n": applicable_n,
        "structural_n": structural_n,
        "observed_applicable_n": observed_applicable_n,
        "genuine_missing_applicable_n": genuine_missing_applicable_n,
        "genuine_missing_pct": genuine_missing_pct,
    }

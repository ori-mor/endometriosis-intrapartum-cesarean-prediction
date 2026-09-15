#!/usr/bin/env python3
"""Source-predictor-level activity resolution for the final-modeling pipeline.

A single fitted linear model works on the *encoded* design matrix: one
categorical or fold-safe-transformed source predictor expands into several
model-matrix columns (one-hot dummies, fold-safe quantile-category dummies).
Every downstream structural check in this pipeline -- endometriosis-family
activity, hard-pair violations, set-level violations, selection-stability
frequency -- must reason about the SOURCE predictors, not the encoded
columns. This module is the one place that mapping is built and applied, so
all consumers agree.

Contract
--------
`build_column_to_source_map(preprocessor, source_predictors)` returns a
``dict[str, str]`` from every model-matrix output column name (as produced by
``preprocessor.get_feature_names_out()``) to exactly one source predictor
name. The map is exhaustive: if any output column cannot be resolved to a
source predictor, it raises ``RuntimeError`` (fail loud -- a dangling column
means the preprocessor and the declared predictor list disagree).

`active_source_predictors(coefficients, column_names, column_to_source_map,
tolerance)` returns the ``set[str]`` of source predictors that have at least
one mapped coefficient with ``abs(coef) > tolerance``.

The mapping relies only on the naming convention that
``build_preprocessor()`` (modeling_core) uses: with
``verbose_feature_names_out=True`` every output column is
``"<block>__<remainder>"`` and ``<remainder>`` begins with the source
predictor name (numeric passthrough: exactly the name; one-hot / fold-safe:
``"<name>_<level>"``). The special fold-safe transformers each declare
``get_feature_names_out() -> [source_col]`` / ``["BMI_before"]``, so their
remainders start with the source predictor too. Longest-name-first matching
disambiguates nested names (e.g. ``endometrioma`` vs
``endometrioma_size_status``).
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import numpy as np

# Canonical, centralized numerical-zero threshold for "is this source
# predictor genuinely active in the fitted model". 1e-6 (not 1e-8): penalized
# (LASSO / Elastic-Net, saga) optimization leaves tiny residual coefficients
# that are numerically indistinguishable from zero; 1e-6 is comfortably above
# that residual band yet far below any coefficient of genuine clinical or
# statistical magnitude on a standardized design matrix. This SAME threshold
# is used for every source-level activity decision in the pipeline:
#   - endometriosis-family activity (the >=1 endo constraint),
#   - hard-pair co-entry activity,
#   - set-level max-active activity,
#   - stability-selection frequency counting,
#   - coefficient-sign-stability eligibility (a predictor must first be
#     active at this threshold before its sign is counted).
# search_config.py re-exports this as the single public name.
#
# BOUNDARY CONVENTION (explicit, tested): activity is a STRICT inequality --
#   abs(coef) >  tolerance  -> ACTIVE
#   abs(coef) == tolerance  -> INACTIVE  (treated as numerical zero)
#   abs(coef) <  tolerance  -> INACTIVE
COEFFICIENT_ACTIVITY_TOLERANCE = 1e-6


def _strip_block_prefix(name: str) -> str:
    return name.split("__", 1)[1] if "__" in name else name


def build_column_to_source_map(
    preprocessor,
    source_predictors: Iterable[str],
) -> dict[str, str]:
    """Map every fitted-preprocessor output column to exactly one source
    predictor. Raises RuntimeError if any output column is unresolvable."""
    try:
        out_names = [str(n) for n in preprocessor.get_feature_names_out()]
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            "source_predictor_activity: preprocessor.get_feature_names_out() "
            f"failed -- the preprocessor must be fitted first ({exc!r})."
        ) from exc

    srcs = sorted({str(s) for s in source_predictors}, key=len, reverse=True)
    if not srcs:
        raise RuntimeError("source_predictor_activity: empty source_predictors list.")

    mapping: dict[str, str] = {}
    unresolved: list[str] = []
    for col in out_names:
        remainder = _strip_block_prefix(col)
        hit = None
        for sp in srcs:
            if remainder == sp or remainder.startswith(sp + "_"):
                hit = sp
                break
        if hit is None:
            unresolved.append(col)
        else:
            mapping[col] = hit

    if unresolved:
        raise RuntimeError(
            "source_predictor_activity: "
            f"{len(unresolved)} model-matrix column(s) could not be resolved "
            f"to any source predictor (first: {unresolved[:10]}). The "
            "column->source map must be exhaustive; a dangling column means "
            "build_preprocessor() and the declared predictor list disagree."
        )
    return mapping


def source_level_coefficients(
    coefficients: Sequence[float] | np.ndarray,
    column_names: Sequence[str],
    column_to_source_map: Mapping[str, str],
) -> dict[str, dict[str, float]]:
    """Per-source, per-ENCODED-COLUMN coefficient breakdown:
    ``{source: {encoded_column: coefficient}}``. This is the level-specific
    detail that source-level sign-stability semantics must be built from --
    a multi-level categorical source's coefficients are never collapsed by
    summation (Correction 8/33): see :func:`source_sign`."""
    coefs = np.ravel(np.asarray(coefficients, dtype=float))
    cols = [str(c) for c in column_names]
    if coefs.shape[0] != len(cols):
        raise RuntimeError(
            "source_predictor_activity.source_level_coefficients: coefficient "
            f"count ({coefs.shape[0]}) != column count ({len(cols)})."
        )
    out: dict[str, dict[str, float]] = {}
    for coef, col in zip(coefs, cols):
        if col not in column_to_source_map:
            raise RuntimeError(
                f"source_predictor_activity: column {col!r} is absent from "
                "column_to_source_map -- rebuild the map from the same fitted "
                "preprocessor that produced these coefficients."
            )
        out.setdefault(column_to_source_map[col], {})[col] = float(coef)
    return out


def source_sign(per_source_level_coefficients: Mapping[str, float]) -> float | None:
    """A single source-level SIGN is a statistically meaningful summary only
    when the source is represented by exactly ONE encoded column (an
    ordinary numeric/binary predictor, or a fold-safe-transformed source
    whose fitted encoder happens to produce a single modelled dummy). For a
    genuinely multi-coefficient (multi-level categorical) source, summing the
    dummy coefficients conflates unrelated category contrasts against a
    reference level that -- for the Top-N drop-one encoding -- can itself
    vary by training fold; that sum is NOT a meaningful single sign.

    Returns the lone coefficient for a single-column source (its sign IS
    meaningful), or ``None`` ("not applicable") for a multi-column source --
    callers must treat ``None`` as not-applicable, never as zero/no-effect.
    """
    if len(per_source_level_coefficients) == 1:
        return next(iter(per_source_level_coefficients.values()))
    return None


def active_source_predictors(
    coefficients: Sequence[float] | np.ndarray,
    column_names: Sequence[str],
    column_to_source_map: Mapping[str, str],
    tolerance: float = COEFFICIENT_ACTIVITY_TOLERANCE,
) -> set[str]:
    """Return the set of source predictors with >= 1 mapped coefficient whose
    absolute value STRICTLY exceeds `tolerance` (abs(coef) == tolerance is
    inactive -- see COEFFICIENT_ACTIVITY_TOLERANCE boundary convention).

    Encoded categorical / fold-safe columns roll up to their single source
    predictor via `column_to_source_map`: the source is active if ANY of its
    mapped columns clears the threshold."""
    coefs = np.ravel(np.asarray(coefficients, dtype=float))
    cols = [str(c) for c in column_names]
    if coefs.shape[0] != len(cols):
        raise RuntimeError(
            "source_predictor_activity.active_source_predictors: coefficient "
            f"count ({coefs.shape[0]}) != column count ({len(cols)})."
        )
    if tolerance <= 0:
        raise ValueError("tolerance must be strictly positive.")
    active: set[str] = set()
    for coef, col in zip(coefs, cols):
        if col not in column_to_source_map:
            raise RuntimeError(
                f"source_predictor_activity: column {col!r} is absent from "
                "column_to_source_map -- rebuild the map from the same fitted "
                "preprocessor that produced these coefficients."
            )
        if abs(float(coef)) > tolerance:
            active.add(column_to_source_map[col])
    return active

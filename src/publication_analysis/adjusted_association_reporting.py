"""Multiplicity (BH-FDR) and primary-vs-sensitivity reporting for the adjusted
endometriosis-specific association analysis (Adjusted Association Design Lock).

Both functions here operate purely on the ``adjusted_master`` DataFrame
produced by ``adjusted_endometriosis_analysis.run_adjusted_analysis_for_family``
-- no model fitting happens in this module.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from publication_analysis.adjusted_endometriosis_analysis import (
    MODEL_VARIANT_PRIMARY,
    MODEL_VARIANT_SENSITIVITY_IVF,
    ROW_TYPE_SOURCE,
)
from publication_analysis.endometriosis_adjusted_feasibility import CLASS_C
from publication_analysis.univariable_analysis import FIT_OK, benjamini_hochberg

BH_COLUMNS = ["exposure", "exposure_class", "raw_p", "bh_q", "in_bh_family", "fit_status"]


def build_primary_bh_table(master_df: pd.DataFrame) -> pd.DataFrame:
    """ONE exploratory BH-FDR family: valid PRIMARY source-level p-values from
    class A + B exposures only.

    - binary exposure: the coefficient p is the source-level p.
    - categorical exposure: the omnibus Wald p (already the source row's
      ``adjusted_p`` for a categorical source row) is the source-level p.
    - class C: never included.
    - a non-estimable A/B model: raw_p=None, bh_q=None, in_bh_family=False.

    Sensitivity (``SENSITIVITY_IVF``) rows never enter this family.
    """
    eligible = master_df[
        (master_df["model_variant"] == MODEL_VARIANT_PRIMARY)
        & (master_df["row_type"] == ROW_TYPE_SOURCE)
        & (master_df["exposure_class"] != CLASS_C)
    ].copy()

    raw_p = [
        float(p) if (fit_status == FIT_OK and p is not None and not pd.isna(p)) else None
        for p, fit_status in zip(eligible["adjusted_p"], eligible["fit_status"])
    ]
    bh_q = benjamini_hochberg(raw_p)
    in_bh_family = [p is not None for p in raw_p]

    # dtype=object preserves the exact Python None / bool values through
    # DataFrame storage. A float64/bool column would silently coerce
    # None -> NaN and True/False -> numpy bool scalars on read-back, which
    # breaks the documented `is None` / `is False` contract above.
    eligible["raw_p"] = pd.Series(raw_p, index=eligible.index, dtype=object)
    eligible["bh_q"] = pd.Series(bh_q, index=eligible.index, dtype=object)
    eligible["in_bh_family"] = pd.Series(in_bh_family, index=eligible.index, dtype=object)

    return eligible[BH_COLUMNS].reset_index(drop=True)


def merge_bh_into_master(master_df: pd.DataFrame, bh_df: pd.DataFrame) -> pd.DataFrame:
    """Left-join ``bh_q`` / ``in_bh_family`` back onto the full master table.

    Every row not in the BH family (level rows, class C, SENSITIVITY_IVF rows)
    gets ``bh_q=None`` / ``in_bh_family=False``.
    """
    out = master_df.copy()
    out["bh_q"] = pd.Series([None] * len(out), index=out.index, dtype=object)
    out["in_bh_family"] = pd.Series([False] * len(out), index=out.index, dtype=object)
    bh_by_exposure = bh_df.set_index("exposure")
    is_primary_source = (out["model_variant"] == MODEL_VARIANT_PRIMARY) & (out["row_type"] == ROW_TYPE_SOURCE)
    for idx in out.index[is_primary_source]:
        exposure = out.at[idx, "exposure"]
        if exposure in bh_by_exposure.index:
            out.at[idx, "bh_q"] = bh_by_exposure.at[exposure, "bh_q"]
            out.at[idx, "in_bh_family"] = bool(bh_by_exposure.at[exposure, "in_bh_family"])
    return out


def build_primary_vs_sensitivity_comparison(master_df: pd.DataFrame) -> pd.DataFrame:
    """Paired PRIMARY vs SENSITIVITY_IVF descriptive comparison, one row per
    A/B source exposure. Purely descriptive -- no automatic "robust" threshold.
    """
    source_rows = master_df[
        (master_df["row_type"] == ROW_TYPE_SOURCE) & (master_df["exposure_class"] != CLASS_C)
    ]
    records = []
    for exposure, group in source_rows.groupby("exposure", sort=True):
        primary = group[group["model_variant"] == MODEL_VARIANT_PRIMARY]
        sensitivity = group[group["model_variant"] == MODEL_VARIANT_SENSITIVITY_IVF]
        if primary.empty or sensitivity.empty:
            continue
        p = primary.iloc[0]
        s = sensitivity.iloc[0]

        primary_ok = p["fit_status"] == FIT_OK
        sensitivity_ok = s["fit_status"] == FIT_OK

        def _or_present(row) -> bool:
            val = row["adjusted_or"]
            return val is not None and not pd.isna(val)

        primary_or_present = primary_ok and _or_present(p)
        sensitivity_or_present = sensitivity_ok and _or_present(s)
        # A source row that fit OK but carries no single OR is a categorical
        # multi-level omnibus row (no per-source-row OR by construction) --
        # detected structurally, never by exposure name.
        is_categorical = (primary_ok and not primary_or_present) or (sensitivity_ok and not sensitivity_or_present)

        log_or_diff = None
        direction_consistent = None
        if primary_or_present and sensitivity_or_present:
            log_or_diff = float(np.log(s["adjusted_or"]) - np.log(p["adjusted_or"]))
            direction_consistent = bool(
                np.sign(np.log(p["adjusted_or"])) == np.sign(np.log(s["adjusted_or"]))
            )

        notes = (
            "categorical multi-level source: log-OR difference not applicable; compare omnibus p only."
            if is_categorical
            else ""
        )

        records.append(
            {
                "exposure": exposure,
                "exposure_class": p["exposure_class"],
                "primary_fit_status": p["fit_status"],
                "primary_or": p["adjusted_or"],
                "primary_ci_low": p["adjusted_ci_low"],
                "primary_ci_high": p["adjusted_ci_high"],
                "primary_p": p["adjusted_p"],
                "sensitivity_fit_status": s["fit_status"],
                "sensitivity_or": s["adjusted_or"],
                "sensitivity_ci_low": s["adjusted_ci_low"],
                "sensitivity_ci_high": s["adjusted_ci_high"],
                "sensitivity_p": s["adjusted_p"],
                "log_or_diff": log_or_diff,
                "direction_consistent": direction_consistent,
                "estimability_changed": bool(primary_ok != sensitivity_ok),
                "notes": notes,
            }
        )
    df = pd.DataFrame(records)
    if not df.empty:
        # Same object-dtype rationale as build_primary_bh_table /
        # merge_bh_into_master above: these columns mix None with float/bool
        # values across rows, which a typed column would silently coerce.
        for col in ("log_or_diff", "direction_consistent", "estimability_changed"):
            df[col] = pd.Series([r[col] for r in records], index=df.index, dtype=object)
    return df

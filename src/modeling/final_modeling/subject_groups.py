#!/usr/bin/env python3
"""Subject-level CV grouping keys for the final-modeling pipeline.

Provides `load_group_labels(matrix)`: an array of group labels, row-aligned
1:1 by position with `matrix` (the modeling matrix loaded by
`modeling_core.load_inputs()`), so that a repeated `subject_number` (the same
woman with multiple delivery records) is always kept together on one side of
every train/validation split and every CV fold -- never split across them.

`subject_number`/`delivery_id` are dropped before the EDA C candidate matrix
is built (C0 safety rule -- see eda_c_part1_setup_gate.py) and are not
present in the Data Cleaning B output either, so `delivery_id` cannot be
joined against `matrix` directly. Instead it is propagated end-to-end as a
sidecar, never a feature:

- Data Cleaning B attaches `delivery_id` as a real (export-excluded) column
  the instant its working dataframe is carved from the loaded
  `work_df_batch18.xlsx` (`cleaning_b_part1_setup_inputs.py`), so it travels
  with each row through every subsequent cleaning operation. At save time it
  exports that column's final row order as `cleaning_b_output_delivery_id_key.csv`
  (`cleaning_b_part5_export_cleaned_dataset.py`) -- aligned with the cleaned
  dataset by construction (same in-memory object, same save operation), not
  by an assumption that nothing in between reordered rows.
- EDA C loads that sidecar at read time and re-attaches it the same way
  (`eda_c_part1_setup_gate.py`), then exports its own final sidecar,
  `modeling_dataset_row_delivery_id_key.csv`, at the exact moment the
  modeling matrix itself is saved (`eda_c_part5_handoff.py`) -- again aligned
  by construction, not by trusting that nothing in EDA C's own processing
  reordered rows.

`load_group_labels` reads that final sidecar and performs a genuine
content-based join on `delivery_id` against `work_df_batch18.xlsx` (the
source of truth for `subject_number`) -- not a positional assumption. Every
`delivery_id` in the sidecar must resolve to exactly one row in
`work_df_batch18.xlsx`; any that doesn't raises loudly. `delivery_id` itself
is never treated as a model feature anywhere in this module or written into
the modeling matrix -- it is read from, and exists only in, id-only sidecar
files.

`TARGET_COL`/`AGE` value comparisons (present from an earlier iteration of
this alignment check, back when it was position-based) are retained as
cheap, OPTIONAL sanity checks only -- secondary corroboration, not the
alignment proof itself, since the delivery_id join above already proves
alignment independent of row position or count.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = ROOT / "outputs" / "preprocessing" / "processed" / "work_df_batch18.xlsx"
MATRIX_ROW_KEY_PATH = ROOT / "outputs" / "eda_c" / "modeling_dataset_row_delivery_id_key.csv"
TARGET_COL = "target_intrapartum_cs"
# Optional/secondary sanity checks only (see module docstring) -- not the
# primary alignment mechanism. Skipped gracefully if a column isn't present.
_OPTIONAL_SANITY_CHECK_COLS = [TARGET_COL, "AGE"]


def _values_equal(a: pd.Series, b: pd.Series) -> bool:
    return a.reset_index(drop=True).equals(b.reset_index(drop=True))


def _run_optional_sanity_checks(matrix: pd.DataFrame, row_key: pd.DataFrame) -> None:
    """Cheap, non-load-bearing corroboration only. The delivery_id join in
    load_group_labels() is the actual alignment proof; if these disagree
    with it, something is unexpected enough to warrant a loud failure, but
    their absence/skip is never itself a problem."""
    check_cols = [c for c in _OPTIONAL_SANITY_CHECK_COLS if c in matrix.columns]
    if not check_cols or not SOURCE_PATH.is_file():
        return
    if len(row_key) != len(matrix):
        return  # the primary row-count check below will already fail loudly
    try:
        source_checked = pd.read_excel(SOURCE_PATH, usecols=["delivery_id"] + check_cols)
    except ValueError:
        return  # one of the optional columns isn't in work_df_batch18.xlsx -- skip, non-fatal
    source_checked = source_checked.set_index("delivery_id")
    try:
        aligned = source_checked.loc[row_key["delivery_id"].to_numpy()].reset_index(drop=True)
    except KeyError:
        return  # covered by the primary delivery_id-join check; don't double-report here
    for col in check_cols:
        if not _values_equal(aligned[col], matrix[col]):
            mismatch = (aligned[col].reset_index(drop=True) != matrix[col].reset_index(drop=True)).to_numpy()
            _idx = np.flatnonzero(mismatch)
            raise RuntimeError(
                f"Optional sanity check FAILED for {col!r}: {len(_idx)} of {len(matrix)} row(s) "
                f"differ between work_df_batch18.xlsx (joined by delivery_id) and the modeling "
                f"matrix, first mismatch at matrix row {int(_idx[0])}. This does not match the "
                "delivery_id-based alignment proof and needs investigation before trusting CV "
                "group labels, even though the primary join-based check passed."
            )


def load_group_labels(matrix: pd.DataFrame) -> np.ndarray:
    """Return an array of length `len(matrix)` of CV group labels, one per
    row of `matrix`, row-aligned with it.

    Group label = ``"subject_<subject_number>"`` when `subject_number` is
    non-missing, so every delivery record belonging to the same woman shares
    one group. Rows with a missing `subject_number` (8 documented/accepted
    cases -- see CLAUDE.md) each become their own singleton group, keyed by
    the always-unique `delivery_id`, per the approved rule: treated as
    independent groups, never merged with each other or with any
    non-missing-subject group.
    """
    n_rows = len(matrix)

    if not MATRIX_ROW_KEY_PATH.is_file():
        raise FileNotFoundError(
            f"Row-order delivery_id key not found: {MATRIX_ROW_KEY_PATH}. This sidecar is "
            "written by EDA C (eda_c_part5_handoff.py) at the exact moment it saves the "
            "modeling matrix, and is required here to join CV group labels onto the matrix by "
            "delivery_id rather than by row position alone. Rerun EDA C's handoff step (with "
            "SAVE_SELECTED_MODELING_DATASET=True) to generate it."
        )
    row_key = pd.read_csv(MATRIX_ROW_KEY_PATH).sort_values("row_index").reset_index(drop=True)
    if len(row_key) != n_rows:
        raise RuntimeError(
            f"Row count mismatch between {MATRIX_ROW_KEY_PATH.name} ({len(row_key)} rows) and "
            f"the modeling matrix ({n_rows} rows) -- the sidecar is stale relative to the "
            "current matrix. Rerun EDA C's handoff step before trusting CV group labels."
        )
    if row_key["delivery_id"].isna().any():
        raise RuntimeError(f"{MATRIX_ROW_KEY_PATH.name} contains missing delivery_id value(s); "
                            "delivery_id must always be present (it is assigned sequentially and "
                            "complete by construction in preprocessing).")
    if row_key["delivery_id"].duplicated().any():
        _dupes = row_key.loc[row_key["delivery_id"].duplicated(keep=False), "delivery_id"].unique().tolist()
        raise RuntimeError(f"{MATRIX_ROW_KEY_PATH.name} contains duplicate delivery_id value(s): "
                            f"{_dupes[:10]} -- delivery_id must be unique per row.")

    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(
            f"Canonical source for subject_number not found: {SOURCE_PATH}. This file is "
            "required to build CV group labels that keep each woman's delivery records "
            "together across train/validation splits and CV folds."
        )
    source = pd.read_excel(SOURCE_PATH, usecols=["subject_number", "delivery_id"])
    if source["delivery_id"].isna().any():
        raise RuntimeError(
            "delivery_id must never be missing (it is the documented always-complete "
            "identifier); found missing value(s) in the source file."
        )
    if source["delivery_id"].duplicated().any():
        raise RuntimeError(f"{SOURCE_PATH.name} contains duplicate delivery_id value(s); "
                            "delivery_id must be unique per row.")

    # ── The alignment proof: a genuine content-based join on delivery_id --
    # not a positional assumption. Every matrix row (via row_key) must
    # resolve to exactly one work_df_batch18.xlsx row by delivery_id;
    # anything else means row alignment cannot be trusted.
    merged = row_key.merge(source, on="delivery_id", how="left", indicator=True, validate="one_to_one")
    _unmatched = merged.loc[merged["_merge"] == "left_only", "delivery_id"].tolist()
    if _unmatched:
        raise RuntimeError(
            f"Row alignment check FAILED: {len(_unmatched)} modeling-matrix row(s) have a "
            f"delivery_id not found in {SOURCE_PATH.name}: {_unmatched[:10]}. "
            f"{MATRIX_ROW_KEY_PATH.name} is stale relative to the current "
            f"{SOURCE_PATH.name} -- refusing to build CV group labels against an unverified "
            "alignment. Rerun Data Cleaning B and EDA C before trusting the modeling matrix's "
            "row-to-subject correspondence again."
        )
    merged = merged.drop(columns="_merge")

    _run_optional_sanity_checks(matrix, row_key)

    subject_number = merged["subject_number"]
    delivery_id = merged["delivery_id"]
    groups = np.where(
        subject_number.notna(),
        "subject_" + subject_number.astype("Int64").astype(str),
        "delivery_only_" + delivery_id.astype("Int64").astype(str),
    )
    return groups

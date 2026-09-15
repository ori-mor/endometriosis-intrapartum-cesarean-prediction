"""Canonical delivery -> subject grouping key for the publication analysis.

The analytical matrix (``analysis_matrix.load_analysis_matrix``) carries no
``delivery_id`` / ``subject_number``. This module reconstructs the grouping
key by reproducing — **without importing the modeling namespace** — the exact
contract of
``analysis/modeling/final_modeling/subject_groups.py::load_group_labels``:

1. validate the row-alignment sidecar (0..430 complete map,
   ``analysis_matrix.validate_row_key``);
2. take the matrix row-for-row in that order (positional alignment, never an
   arbitrary pandas index);
3. content-join ``delivery_id`` against
   ``outputs/preprocessing/processed/work_df_batch18.xlsx`` for
   ``subject_number`` (loud on any unmatched / duplicated / reordered row);
4. label: ``subject_<subject_number>`` (nullable-Int64, never ``subject_1.0``)
   when ``subject_number`` is present, else ``delivery_only_<delivery_id>``
   for the 8 documented missing-subject rows — each its own singleton group,
   never merged with another.

The live read-only parity check against the canonical implementation lives in
``verify_subject_group_parity.py`` and is a Checkpoint-A deliverable now that
the extreme-rarity sensitivity run has finished.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from publication_analysis.analysis_matrix import (
    DELIVERY_ID_COL,
    REPO_ROOT,
    RowKeyContractError,
    load_aligned_analysis_inputs,
    validate_row_key,
)

SUBJECT_COL = "subject_number"
GROUP_COL = "subject_group"

BATCH18_XLSX = (
    REPO_ROOT / "outputs" / "preprocessing" / "processed" / "work_df_batch18.xlsx"
)

# HISTORICAL DOCUMENTATION ONLY — carries no control/status semantics and is
# read by no code. The authoritative parity check is the runtime function
# verify_subject_group_parity.verify_live_subject_group_parity(), invoked as a
# gate in notebook Section A and by the CLI. This date is just a note of when
# that live check last passed against the canonical implementation.
LAST_DOCUMENTED_PARITY_CHECK_DATE = "2026-09-03"


class Batch18ContractError(RuntimeError):
    """Raised when work_df_batch18.xlsx cannot support subject grouping."""


class SubjectGroupParityError(RuntimeError):
    """Raised when the publication grouping no longer matches the canonical one."""


@dataclass
class SubjectGroupingSummary:
    n_rows: int
    n_unique_groups: int
    n_rows_missing_subject_number: int
    n_repeated_subject_groups: int
    n_rows_in_repeated_subject_groups: int
    max_deliveries_per_subject: int


@dataclass
class ParityResult:
    n_rows: int
    row_label_equal: bool
    partition_equivalent: bool
    n_label_mismatches: int
    n_partition_mismatches: int
    label_mismatch_positions: list[int] = field(default_factory=list)
    partition_mismatch_positions: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def load_batch18(path: Path = BATCH18_XLSX) -> pd.DataFrame:
    if not path.exists():
        raise Batch18ContractError(
            f"Canonical subject_number source not found: {path}"
        )
    return pd.read_excel(path)


def validate_batch18_for_grouping(batch18_df: pd.DataFrame) -> None:
    """Fail loud unless batch18 can supply a clean delivery_id -> subject_number map."""
    problems: list[str] = []
    if DELIVERY_ID_COL not in batch18_df.columns:
        problems.append(f"missing {DELIVERY_ID_COL!r} column")
    if SUBJECT_COL not in batch18_df.columns:
        problems.append(f"missing {SUBJECT_COL!r} column")
    if not problems:
        did = batch18_df[DELIVERY_ID_COL]
        if did.isna().any():
            problems.append(f"{DELIVERY_ID_COL} has {int(did.isna().sum())} missing value(s)")
        if did.duplicated().any():
            dupes = did[did.duplicated(keep=False)].unique().tolist()
            problems.append(f"{DELIVERY_ID_COL} has duplicate value(s): {dupes[:10]}")
    if problems:
        raise Batch18ContractError(
            "work_df_batch18 grouping contract violated:\n- " + "\n- ".join(problems)
        )


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------
def _subject_label_series(
    subject_number: pd.Series, delivery_id: pd.Series
) -> pd.Series:
    """Label formatting identical to final_modeling/subject_groups.py:
    subject_number and delivery_id both coerced through nullable Int64 so a
    float like 123.0 becomes ``subject_123``, never ``subject_123.0``.
    """
    subj = pd.Series(
        pd.array(subject_number.to_numpy(), dtype="Int64"), index=subject_number.index
    )
    did = pd.Series(
        pd.array(delivery_id.to_numpy(), dtype="Int64"), index=delivery_id.index
    )
    labels = np.where(
        subj.notna().to_numpy(),
        "subject_" + subj.astype("string"),
        "delivery_only_" + did.astype("string"),
    )
    return pd.Series(labels, index=subject_number.index, name=GROUP_COL).astype("object")


def build_subject_groups(
    matrix_df: pd.DataFrame,
    row_key_df: pd.DataFrame,
    batch18_df: pd.DataFrame,
) -> pd.Series:
    """Return a per-row grouping-key Series positionally aligned to ``matrix_df``.

    ``matrix_df`` row *i* corresponds to sidecar ``row_index`` *i* corresponds
    to a ``delivery_id`` corresponds to one ``subject_number`` in batch18.
    """
    row_key_sorted = validate_row_key(row_key_df, expected_n_rows=len(matrix_df))
    validate_batch18_for_grouping(batch18_df)

    if len(matrix_df) != len(row_key_sorted):
        raise RowKeyContractError(
            f"matrix has {len(matrix_df)} rows but the validated row key has "
            f"{len(row_key_sorted)}"
        )

    b18 = batch18_df[[DELIVERY_ID_COL, SUBJECT_COL]].copy()
    try:
        merged = row_key_sorted[[DELIVERY_ID_COL]].merge(
            b18,
            on=DELIVERY_ID_COL,
            how="left",
            validate="one_to_one",
            indicator=True,
        )
    except pd.errors.MergeError as exc:  # duplicate keys on either side
        raise RowKeyContractError(
            f"delivery_id join is not one-to-one: {exc}"
        ) from exc

    if len(merged) != len(row_key_sorted):
        raise RowKeyContractError(
            f"delivery_id join changed the row count: {len(merged)} vs "
            f"{len(row_key_sorted)}"
        )
    unmatched = merged.loc[merged["_merge"] == "left_only", DELIVERY_ID_COL].tolist()
    if unmatched:
        raise RowKeyContractError(
            f"{len(unmatched)} row-key delivery_id(s) not found in work_df_batch18: "
            f"{unmatched[:10]}"
        )
    if merged[DELIVERY_ID_COL].duplicated().any():
        raise RowKeyContractError("delivery_id join produced duplicate rows")
    if merged[DELIVERY_ID_COL].tolist() != row_key_sorted[DELIVERY_ID_COL].tolist():
        raise RowKeyContractError(
            "the delivery_id join reordered rows relative to the sorted row key"
        )
    merged = merged.drop(columns="_merge").reset_index(drop=True)

    labels = _subject_label_series(merged[SUBJECT_COL], merged[DELIVERY_ID_COL])
    labels.index = matrix_df.index  # positional: matrix row i <-> row_index i
    return labels


def summarize_subject_groups(
    matrix_df: pd.DataFrame,
    row_key_df: pd.DataFrame,
    batch18_df: pd.DataFrame,
) -> SubjectGroupingSummary:
    groups = build_subject_groups(matrix_df, row_key_df, batch18_df)
    n_missing = int(groups.astype(str).str.startswith("delivery_only_").sum())
    sizes = groups.value_counts()
    repeated = sizes[sizes > 1]
    return SubjectGroupingSummary(
        n_rows=len(groups),
        n_unique_groups=int(groups.nunique()),
        n_rows_missing_subject_number=n_missing,
        n_repeated_subject_groups=int(len(repeated)),
        n_rows_in_repeated_subject_groups=int(repeated.sum()),
        max_deliveries_per_subject=int(sizes.max()) if len(sizes) else 0,
    )


def load_subject_groups_for_analysis() -> pd.Series:
    """Convenience: read the three canonical files and return the grouping key."""
    matrix_df, row_key_df = load_aligned_analysis_inputs()
    return build_subject_groups(matrix_df, row_key_df, load_batch18())


# ---------------------------------------------------------------------------
# Parity verification (pure logic; the live run is in verify_subject_group_parity.py)
# ---------------------------------------------------------------------------
def verify_grouping_parity(publication_groups, canonical_labels) -> ParityResult:
    """Compare the publication grouping to the canonical final-modeling grouping.

    Reports two things separately:
      (A) ``row_label_equal`` — exact element-wise label equality across all
          rows (an implementation-integrity check);
      (B) ``partition_equivalent`` — the two labelings induce the *same
          partition* of the rows (same rows grouped together / apart),
          singletons included. This is the scientific requirement for
          subject-cluster-robust standard errors, and is invariant to a
          consistent relabeling of the groups.
    """
    pub = pd.Series(list(publication_groups), dtype="object").astype(str).reset_index(
        drop=True
    )
    canon = pd.Series(list(canonical_labels), dtype="object").astype(str).reset_index(
        drop=True
    )
    if len(pub) != len(canon):
        raise ValueError(
            f"parity length mismatch: publication={len(pub)} canonical={len(canon)}"
        )
    n = len(pub)

    label_eq = pub.to_numpy() == canon.to_numpy()
    label_mismatch_pos = [int(i) for i in np.flatnonzero(~label_eq)]

    # First-occurrence factor codes depend only on the partition, so equal code
    # arrays  <=>  identical partition.
    code_pub = pd.factorize(pub, sort=False)[0]
    code_canon = pd.factorize(canon, sort=False)[0]
    part_eq = code_pub == code_canon
    part_mismatch_pos = [int(i) for i in np.flatnonzero(~part_eq)]

    return ParityResult(
        n_rows=n,
        row_label_equal=bool(label_eq.all()),
        partition_equivalent=bool(part_eq.all()),
        n_label_mismatches=len(label_mismatch_pos),
        n_partition_mismatches=len(part_mismatch_pos),
        label_mismatch_positions=label_mismatch_pos[:50],
        partition_mismatch_positions=part_mismatch_pos[:50],
    )


def parity_gate_passed(result: ParityResult) -> bool:
    """The parity gate requires BOTH exact row-label equality AND partition
    equivalence — a consistently-relabeled grouping (partition-equivalent but
    not label-equal) does NOT pass this gate.
    """
    return bool(result.row_label_equal and result.partition_equivalent)

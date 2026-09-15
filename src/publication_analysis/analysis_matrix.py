"""Canonical analytical-matrix input contract for the publication / inferential analysis.

The publication analysis must be run on the **same 81-predictor modeling
handoff matrix** the predictive pipeline uses — not on the wider Data
Cleaning B dataframe. That matrix is:

    outputs/eda_c/modeling_dataset_candidate_features.xlsx   (431 x 82)
        = target_intrapartum_cs + the 81 eligible predictors, in the exact
          order of outputs/eda_c/candidate_model_features.csv (the registry).

It carries **no** ``delivery_id`` / ``subject_number`` (those are dropped
before the EDA C candidate matrix is built). Row identity is recovered
separately, positionally, through the canonical row-alignment sidecar:

    outputs/eda_c/modeling_dataset_row_delivery_id_key.csv   (row_index, delivery_id)

This module only *reads*; it never writes. It provides fail-loud validation
of both the matrix and the sidecar so a stale or reshaped input is caught
before any real-data inference runs.

Verified manifest schema (``outputs/eda_c/candidate_feature_manifest.json``,
inspected 2026-09-03 — exact keys, no fallback search):
``n_rows`` = 431, ``n_events`` = 61, ``n_eligible_pool`` = 81,
``target_distribution["target_intrapartum_cs"]["n0"|"n1"]`` = 370 / 61.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

ANALYSIS_MATRIX_XLSX = (
    REPO_ROOT / "outputs" / "eda_c" / "modeling_dataset_candidate_features.xlsx"
)
ROW_DELIVERY_ID_KEY_CSV = (
    REPO_ROOT / "outputs" / "eda_c" / "modeling_dataset_row_delivery_id_key.csv"
)

TARGET_COL = "target_intrapartum_cs"
ROW_INDEX_COL = "row_index"
DELIVERY_ID_COL = "delivery_id"

EXPECTED_N_ROWS = 431
EXPECTED_TARGET_0 = 370
EXPECTED_TARGET_1 = 61
EXPECTED_N_PREDICTORS = 81


class RowKeyContractError(RuntimeError):
    """Raised when modeling_dataset_row_delivery_id_key.csv violates its contract."""


class AnalysisMatrixError(RuntimeError):
    """Raised when the loaded analytical matrix does not match the canonical contract."""


@dataclass
class AnalysisMatrixReport:
    ok: bool
    n_rows: int | None = None
    n_predictors: int | None = None
    target_0: int | None = None
    target_1: int | None = None
    problems: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Row-alignment sidecar
# ---------------------------------------------------------------------------
def load_row_delivery_id_key(path: Path = ROW_DELIVERY_ID_KEY_CSV) -> pd.DataFrame:
    if not path.exists():
        raise RowKeyContractError(f"Row-alignment sidecar not found: {path}")
    return pd.read_csv(path)


def validate_row_key(
    row_key_df: pd.DataFrame, expected_n_rows: int = EXPECTED_N_ROWS
) -> pd.DataFrame:
    """Fail loud unless the sidecar is a complete ``0..expected_n_rows-1``
    row-index map with unique, complete delivery ids. Returns the sidecar
    sorted by ``row_index`` with a fresh RangeIndex — the canonical positional
    order.

    ``expected_n_rows`` defaults to the canonical cohort size (431); callers
    aligning against a specific matrix pass ``len(matrix_df)``.
    """
    problems: list[str] = []

    for col in (ROW_INDEX_COL, DELIVERY_ID_COL):
        if col not in row_key_df.columns:
            problems.append(f"missing required column {col!r}")
    if problems:
        raise RowKeyContractError(
            "Row-key contract violated:\n- " + "\n- ".join(problems)
        )

    n = len(row_key_df)
    if n != expected_n_rows:
        problems.append(f"row key has {n} rows, expected {expected_n_rows}")

    ri = row_key_df[ROW_INDEX_COL]
    if ri.isna().any():
        problems.append(f"{ROW_INDEX_COL} has {int(ri.isna().sum())} missing value(s)")
    ri_nonnull = ri.dropna()
    ri_is_integer = True
    try:
        ri_int = ri_nonnull.astype("int64")
    except (ValueError, TypeError):
        ri_is_integer = False
        problems.append(f"{ROW_INDEX_COL} is not integer-valued")
    else:
        if not (ri_nonnull.to_numpy() == ri_int.to_numpy()).all():
            ri_is_integer = False
            problems.append(f"{ROW_INDEX_COL} has non-integer value(s)")
    if ri.duplicated().any():
        problems.append(f"{ROW_INDEX_COL} has duplicate value(s)")
    if ri_is_integer and not ri.isna().any() and not ri.duplicated().any():
        sorted_ri = sorted(int(x) for x in ri_nonnull)
        if sorted_ri != list(range(expected_n_rows)):
            problems.append(
                f"{ROW_INDEX_COL} sorted is not 0..{expected_n_rows - 1} contiguous "
                f"(min={sorted_ri[0]}, max={sorted_ri[-1]}, n={len(sorted_ri)})"
            )

    did = row_key_df[DELIVERY_ID_COL]
    if did.isna().any():
        problems.append(f"{DELIVERY_ID_COL} has {int(did.isna().sum())} missing value(s)")
    if did.duplicated().any():
        dupes = did[did.duplicated(keep=False)].unique().tolist()
        problems.append(f"{DELIVERY_ID_COL} has duplicate value(s): {dupes[:10]}")

    if problems:
        raise RowKeyContractError(
            "Row-key contract violated:\n- " + "\n- ".join(problems)
        )

    return row_key_df.sort_values(ROW_INDEX_COL).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Analytical matrix
# ---------------------------------------------------------------------------
def load_analysis_matrix(path: Path = ANALYSIS_MATRIX_XLSX) -> pd.DataFrame:
    if not path.exists():
        raise AnalysisMatrixError(f"Analytical matrix not found: {path}")
    return pd.read_excel(path)


def predictor_columns(matrix_df: pd.DataFrame) -> list[str]:
    """Non-target columns, in the matrix's own column order."""
    return [c for c in matrix_df.columns if c != TARGET_COL]


def load_registry_predictor_names() -> list[str]:
    """The 81 predictor names in canonical order, from candidate_model_features.csv."""
    from publication_analysis import publication_contract as _pc

    return list(_pc.load_candidate_features()["variable"])


def load_aligned_analysis_inputs(
    matrix_path: Path = ANALYSIS_MATRIX_XLSX,
    row_key_path: Path = ROW_DELIVERY_ID_KEY_CSV,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the matrix and the validated sidecar, positionally aligned.

    The sidecar is validated first (0..430 complete map); only then is the
    matrix taken row-for-row in that order, with a fresh RangeIndex — never
    an arbitrary pandas index.
    """
    row_key_df = validate_row_key(load_row_delivery_id_key(row_key_path))
    matrix_df = load_analysis_matrix(matrix_path).reset_index(drop=True)
    if len(matrix_df) != len(row_key_df):
        raise AnalysisMatrixError(
            f"matrix has {len(matrix_df)} rows but the row-key sidecar has "
            f"{len(row_key_df)} — the sidecar is stale relative to the matrix."
        )
    return matrix_df, row_key_df


def validate_analysis_matrix_from_data(
    matrix_df: pd.DataFrame,
    registry_names: list[str],
    manifest: dict,
    cleaning_b_manifest: dict,
    strict: bool = True,
) -> AnalysisMatrixReport:
    """Pure validation logic (no file I/O) — used directly by synthetic tests
    and by ``validate_analysis_matrix`` against the real files.
    """
    problems: list[str] = []

    # --- registry integrity -------------------------------------------------
    if len(registry_names) != len(set(registry_names)):
        seen: set[str] = set()
        dupes = sorted({n for n in registry_names if n in seen or seen.add(n)})
        problems.append(f"registry predictor names contain duplicates: {dupes}")
    if len(registry_names) != EXPECTED_N_PREDICTORS:
        problems.append(
            f"registry has {len(registry_names)} predictors, expected {EXPECTED_N_PREDICTORS}"
        )
    man_pool = manifest.get("n_eligible_pool")
    if man_pool != EXPECTED_N_PREDICTORS:
        problems.append(f"manifest n_eligible_pool={man_pool}, expected {EXPECTED_N_PREDICTORS}")
    if man_pool != len(registry_names):
        problems.append(
            f"manifest n_eligible_pool={man_pool} != len(registry_names)={len(registry_names)}"
        )

    # --- matrix column integrity -----------------------------------------
    if matrix_df.columns.duplicated().any():
        dupes = sorted(set(matrix_df.columns[matrix_df.columns.duplicated()].tolist()))
        problems.append(f"analysis matrix has duplicate column name(s): {dupes}")

    has_target = TARGET_COL in matrix_df.columns
    if not has_target:
        problems.append(f"analysis matrix is missing the target column {TARGET_COL!r}")

    pred_cols = predictor_columns(matrix_df)
    if len(pred_cols) != EXPECTED_N_PREDICTORS:
        problems.append(
            f"analysis matrix has {len(pred_cols)} non-target column(s), "
            f"expected {EXPECTED_N_PREDICTORS}"
        )
    if pred_cols != list(registry_names):
        only_matrix = sorted(set(pred_cols) - set(registry_names))
        only_registry = sorted(set(registry_names) - set(pred_cols))
        if only_matrix or only_registry:
            problems.append(
                "predictor SET mismatch vs registry — "
                f"only_in_matrix={only_matrix}, only_in_registry={only_registry}"
            )
        elif len(pred_cols) != len(registry_names):
            problems.append(
                f"predictor column count {len(pred_cols)} != registry "
                f"{len(registry_names)} despite an identical name set "
                "(duplicate predictor column names)"
            )
        else:
            first_diff = next(
                (i for i, (a, b) in enumerate(zip(pred_cols, registry_names)) if a != b),
                0,
            )
            problems.append(
                "predictor ORDER mismatch vs registry (same set, different order) — "
                f"first differs at position {first_diff}: "
                f"matrix={pred_cols[first_diff]!r} registry={registry_names[first_diff]!r}"
            )

    # --- row count --------------------------------------------------------
    n_rows = len(matrix_df)
    man_rows = manifest.get("n_rows")
    if n_rows != EXPECTED_N_ROWS:
        problems.append(f"analysis matrix has {n_rows} rows, expected {EXPECTED_N_ROWS}")
    if man_rows != EXPECTED_N_ROWS:
        problems.append(f"manifest n_rows={man_rows}, expected {EXPECTED_N_ROWS}")
    if n_rows != man_rows:
        problems.append(f"analysis matrix rows={n_rows} != manifest n_rows={man_rows}")
    cb_rows = cleaning_b_manifest.get("cleaned_rows")
    if cb_rows != EXPECTED_N_ROWS:
        problems.append(
            f"cleaning_b_manifest cleaned_rows={cb_rows}, expected {EXPECTED_N_ROWS}"
        )

    # --- target column ---------------------------------------------------
    target_0 = target_1 = None
    if has_target:
        target = matrix_df[TARGET_COL]
        if target.isna().any():
            problems.append(
                f"{TARGET_COL} has {int(target.isna().sum())} missing value(s)"
            )
        non_null = target.dropna()
        observed = {v for v in non_null.unique().tolist()}
        if not observed <= {0, 1}:
            problems.append(
                f"{TARGET_COL} has value(s) outside {{0, 1}}: {sorted(observed - {0, 1})}"
            )
        else:
            counts = non_null.astype("int64").value_counts().to_dict()
            target_0 = int(counts.get(0, 0))
            target_1 = int(counts.get(1, 0))
            if (target_0, target_1) != (EXPECTED_TARGET_0, EXPECTED_TARGET_1):
                problems.append(
                    f"target counts 0/1 = {target_0}/{target_1}, "
                    f"expected {EXPECTED_TARGET_0}/{EXPECTED_TARGET_1}"
                )
        man_dist = manifest.get("target_distribution", {}).get(TARGET_COL, {})
        man_n0, man_n1 = man_dist.get("n0"), man_dist.get("n1")
        if (man_n0, man_n1) != (EXPECTED_TARGET_0, EXPECTED_TARGET_1):
            problems.append(
                f"manifest target_distribution n0/n1={man_n0}/{man_n1}, "
                f"expected {EXPECTED_TARGET_0}/{EXPECTED_TARGET_1}"
            )
        if target_1 is not None and (target_0, target_1) != (man_n0, man_n1):
            problems.append(
                f"matrix target counts {target_0}/{target_1} != manifest {man_n0}/{man_n1}"
            )
        man_events = manifest.get("n_events")
        if man_events != EXPECTED_TARGET_1:
            problems.append(f"manifest n_events={man_events}, expected {EXPECTED_TARGET_1}")
        if target_1 is not None and target_1 != man_events:
            problems.append(
                f"matrix events={target_1} != manifest n_events={man_events}"
            )

    report = AnalysisMatrixReport(
        ok=not problems,
        n_rows=n_rows,
        n_predictors=len(pred_cols),
        target_0=target_0,
        target_1=target_1,
        problems=problems,
    )
    if strict and problems:
        raise AnalysisMatrixError(
            "Analysis-matrix contract violated:\n- " + "\n- ".join(problems)
        )
    return report


def validate_analysis_matrix(
    matrix_df: pd.DataFrame | None = None, strict: bool = True
) -> AnalysisMatrixReport:
    """File-loading wrapper: validate the real matrix against the real
    registry + manifests. Reads only the EDA-C xlsx and small metadata files.
    """
    from publication_analysis import publication_contract as _pc

    if matrix_df is None:
        matrix_df = load_analysis_matrix()
    registry_names = load_registry_predictor_names()
    manifest = _pc.load_candidate_feature_manifest()
    cleaning_b_manifest = _pc.load_cleaning_b_manifest()
    return validate_analysis_matrix_from_data(
        matrix_df, registry_names, manifest, cleaning_b_manifest, strict=strict
    )


if __name__ == "__main__":
    import sys

    # Submission package: publication_analysis lives under src/, not analysis/
    # (see REPO_ROOT above) -- src/ must be on sys.path, not REPO_ROOT itself.
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))

    _matrix, _row_key = load_aligned_analysis_inputs()
    _report = validate_analysis_matrix(_matrix, strict=False)
    print(f"analysis matrix: {_matrix.shape[0]} x {_matrix.shape[1]}")
    print(f"row-key sidecar rows: {len(_row_key)}")
    print(f"contract OK: {_report.ok}")
    print(f"n_predictors: {_report.n_predictors}  target 0/1: {_report.target_0}/{_report.target_1}")
    for _p in _report.problems:
        print(f"  - {_p}")

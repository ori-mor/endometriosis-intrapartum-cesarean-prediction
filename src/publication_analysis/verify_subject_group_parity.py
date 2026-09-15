#!/usr/bin/env python3
"""Live READ-ONLY parity gate: publication subject grouping vs the canonical
final-modeling grouping.

The single source of truth is the callable ``verify_live_subject_group_parity``
— invoked both as a gate in notebook Section A and by this module's CLI
``main()``. There is no cached/dated verdict: every call re-loads the current
EDA-C matrix + row-alignment sidecar + ``work_df_batch18.xlsx``, rebuilds the
publication grouping, and re-runs the canonical
``analysis/modeling/final_modeling/subject_groups.py::load_group_labels``
(loaded read-only by file path — never a package import; that module imports
only ``pathlib`` / ``numpy`` / ``pandas`` and nothing else from
``final_modeling``, and is never modified). No model is fit.

Gate: ``verify_live_subject_group_parity`` raises ``SubjectGroupParityError``
unless BOTH ``row_label_equal`` and ``partition_equivalent`` are True across
every row. Run (canonical env):

    .venv312\\Scripts\\python.exe analysis/publication_analysis/verify_subject_group_parity.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SUBJECT_GROUPS_PATH = (
    REPO_ROOT / "analysis" / "modeling" / "final_modeling" / "subject_groups.py"
)

# Submission package: publication_analysis lives under src/, not analysis/.
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from publication_analysis.analysis_matrix import (
    ANALYSIS_MATRIX_XLSX,
    ROW_DELIVERY_ID_KEY_CSV,
    load_aligned_analysis_inputs,
)
from publication_analysis.subject_grouping import (
    BATCH18_XLSX,
    ParityResult,
    SubjectGroupParityError,
    build_subject_groups,
    load_batch18,
    parity_gate_passed,
    verify_grouping_parity,
)


def _load_canonical_subject_groups_module():
    if not CANONICAL_SUBJECT_GROUPS_PATH.exists():
        raise FileNotFoundError(
            f"canonical subject_groups.py not found: {CANONICAL_SUBJECT_GROUPS_PATH}"
        )
    spec = importlib.util.spec_from_file_location(
        "publication_analysis._canonical_subject_groups_readonly",
        CANONICAL_SUBJECT_GROUPS_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot build an import spec for {CANONICAL_SUBJECT_GROUPS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_live_subject_group_parity(
    matrix_path: Path = ANALYSIS_MATRIX_XLSX,
    row_key_path: Path = ROW_DELIVERY_ID_KEY_CSV,
    batch18_path: Path = BATCH18_XLSX,
    strict: bool = True,
) -> ParityResult:
    """Run the live parity check against the current canonical files.

    Loads the current EDA-C matrix + sidecar, builds the publication grouping,
    runs the canonical ``load_group_labels`` read-only, and compares every
    row. With ``strict=True`` (the default and the notebook-gate behavior),
    raises ``SubjectGroupParityError`` unless BOTH ``row_label_equal`` and
    ``partition_equivalent`` are True. Returns the ``ParityResult`` either way
    when it does not raise.
    """
    matrix_df, row_key_df = load_aligned_analysis_inputs(matrix_path, row_key_path)
    publication_groups = build_subject_groups(
        matrix_df, row_key_df, load_batch18(batch18_path)
    )

    canonical_module = _load_canonical_subject_groups_module()
    canonical_labels = canonical_module.load_group_labels(matrix_df)

    result = verify_grouping_parity(publication_groups, canonical_labels)

    if strict and not parity_gate_passed(result):
        raise SubjectGroupParityError(
            "Live subject-group parity FAILED — refusing to proceed with inferential "
            "analysis.\n"
            f"  rows compared:            {result.n_rows}\n"
            f"  (A) row_label_equal:      {result.row_label_equal} "
            f"(mismatches: {result.n_label_mismatches}; "
            f"first: {result.label_mismatch_positions})\n"
            f"  (B) partition_equivalent: {result.partition_equivalent} "
            f"(mismatches: {result.n_partition_mismatches}; "
            f"first: {result.partition_mismatch_positions})\n"
            "The publication grouping no longer matches "
            "final_modeling.subject_groups.load_group_labels(). Re-check the EDA-C "
            "matrix, the row-alignment sidecar, and work_df_batch18.xlsx."
        )
    return result


def _print_result(result: ParityResult) -> None:
    print("=== Subject-group parity: publication vs "
          "final_modeling.subject_groups.load_group_labels ===")
    print(f"rows compared:                {result.n_rows}")
    print(f"(A) exact row-label equality: {result.row_label_equal}  "
          f"(mismatches: {result.n_label_mismatches})")
    print(f"(B) partition equivalence:    {result.partition_equivalent}  "
          f"(mismatches: {result.n_partition_mismatches})")
    if not result.row_label_equal:
        print(f"    first row-label-mismatch positions: {result.label_mismatch_positions}")
    if not result.partition_equivalent:
        print(f"    first partition-mismatch positions: {result.partition_mismatch_positions}")


def main() -> int:
    try:
        result = verify_live_subject_group_parity(strict=False)
    except Exception as exc:  # noqa: BLE001 - CLI: report and exit non-zero
        print(f"parity check could not run: {exc}")
        return 2

    _print_result(result)
    gate_ok = parity_gate_passed(result)
    print(f"\nPARITY {'PASS' if gate_ok else 'FAIL'} "
          "(gate requires BOTH exact row-label equality AND partition equivalence)")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Canonical read-only input contract for the publication / inferential analysis.

This module NEVER writes anything. It only reads small, aggregate,
variable-level metadata files (candidate-feature CSV/JSON manifests, the
Data Cleaning B manifest) and one hand-authored Python registry file. None
of the files it reads contain patient-level rows.

Read-only exception, explicitly permitted by the task brief: this module
loads ``ENDOMETRIOSIS_FAMILY_RATIONALE`` from
``analysis/modeling/final_modeling/endometriosis_family.py`` via
``importlib.util.spec_from_file_location`` against the file's own path —
never via a package import (``import analysis.modeling.final_modeling...``)
and never via the package's ``__init__``. This makes the read narrowly
scoped to that one file's module-level constants and avoids executing any
other code in ``analysis/modeling/final_modeling/``.

If any canonical count below does not match what is currently on disk, the
strict validators here raise ``PublicationContractError`` loudly rather than
silently continuing — per the task brief: "The notebook must fail loudly if
canonical counts do not match expectations."
"""
from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

CANDIDATE_FEATURES_CSV = REPO_ROOT / "outputs" / "eda_c" / "candidate_model_features.csv"
CANDIDATE_FEATURE_MANIFEST_JSON = REPO_ROOT / "outputs" / "eda_c" / "candidate_feature_manifest.json"
CLEANING_B_MANIFEST_JSON = REPO_ROOT / "outputs" / "data_cleaning" / "audit" / "cleaning_b_manifest.json"

# NOTE: the publication analytical matrix is exclusively
# outputs/eda_c/modeling_dataset_candidate_features.xlsx (see analysis_matrix.py).
# The Data Cleaning B output xlsx is never read by this package — the only
# Data-Cleaning-B cross-check uses cleaning_b_manifest.json (cleaned_rows)
# above — so no path constant for that xlsx is defined here.
ENDOMETRIOSIS_FAMILY_MODULE_PATH = (
    REPO_ROOT / "analysis" / "modeling" / "final_modeling" / "endometriosis_family.py"
)

EXPECTED_N_ROWS = 431
EXPECTED_TARGET_0 = 370
EXPECTED_TARGET_1 = 61
EXPECTED_STAGE_CUMULATIVE = {1: 70, 2: 76, 3: 81}
EXPECTED_N_ELIGIBLE_POOL = 81
EXPECTED_ENDOMETRIOSIS_FAMILY_SIZE = 35
TARGET_COL = "target_intrapartum_cs"
STAGE_COL = "earliest_entry_stage"


class PublicationContractError(RuntimeError):
    """Raised when a canonical count on disk does not match the expected contract."""


@dataclass
class ContractReport:
    ok: bool
    n_eligible_pool: int | None = None
    stage_cumulative: dict[int, int] = field(default_factory=dict)
    target_0: int | None = None
    target_1: int | None = None
    endometriosis_family_size: int | None = None
    endometriosis_family_matches_domain_subset: bool | None = None
    cleaning_b_n_rows: int | None = None
    cleaning_b_n_cols: int | None = None
    problems: list[str] = field(default_factory=list)


def _load_endometriosis_family_names() -> set[str]:
    """Load the 35-member hand-authored family registry by direct file path.

    Uses ``importlib.util.spec_from_file_location`` against the file itself,
    never a package-style import, so no other code under
    ``analysis/modeling/final_modeling/`` (including its ``__init__``) runs.
    """
    if not ENDOMETRIOSIS_FAMILY_MODULE_PATH.exists():
        raise PublicationContractError(
            f"Endometriosis family registry not found: {ENDOMETRIOSIS_FAMILY_MODULE_PATH}"
        )
    spec = importlib.util.spec_from_file_location(
        "publication_analysis._endometriosis_family_readonly",
        ENDOMETRIOSIS_FAMILY_MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise PublicationContractError(
            f"Could not create an import spec for {ENDOMETRIOSIS_FAMILY_MODULE_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rationale = getattr(module, "ENDOMETRIOSIS_FAMILY_RATIONALE", None)
    if rationale is None:
        raise PublicationContractError(
            "ENDOMETRIOSIS_FAMILY_RATIONALE not found in endometriosis_family.py"
        )
    return set(rationale.keys())


def load_candidate_features() -> pd.DataFrame:
    """Load the 81-row EDA C candidate-feature metadata CSV (no patient rows)."""
    if not CANDIDATE_FEATURES_CSV.exists():
        raise PublicationContractError(f"Missing candidate features CSV: {CANDIDATE_FEATURES_CSV}")
    return pd.read_csv(CANDIDATE_FEATURES_CSV)


def load_candidate_feature_manifest() -> dict:
    if not CANDIDATE_FEATURE_MANIFEST_JSON.exists():
        raise PublicationContractError(
            f"Missing candidate feature manifest: {CANDIDATE_FEATURE_MANIFEST_JSON}"
        )
    return json.loads(CANDIDATE_FEATURE_MANIFEST_JSON.read_text(encoding="utf-8"))


def load_cleaning_b_manifest() -> dict:
    if not CLEANING_B_MANIFEST_JSON.exists():
        raise PublicationContractError(f"Missing Data Cleaning B manifest: {CLEANING_B_MANIFEST_JSON}")
    return json.loads(CLEANING_B_MANIFEST_JSON.read_text(encoding="utf-8"))


def endometriosis_family_names() -> set[str]:
    """Public accessor for the 35-member canonical endometriosis family name set."""
    return _load_endometriosis_family_names()


def validate_contract_from_data(
    features_df: pd.DataFrame,
    manifest: dict,
    cleaning_b_manifest: dict,
    family_names: set[str],
    strict: bool = True,
) -> ContractReport:
    """Pure validation logic, independent of file I/O — used directly by tests
    against synthetic fixtures, and by ``validate_contract`` against real data.
    """
    problems: list[str] = []

    n_eligible_pool = len(features_df)
    if n_eligible_pool != EXPECTED_N_ELIGIBLE_POOL:
        problems.append(
            f"n_eligible_pool={n_eligible_pool}, expected {EXPECTED_N_ELIGIBLE_POOL}"
        )

    stage_cumulative: dict[int, int] = {}
    if STAGE_COL in features_df.columns:
        for stage in (1, 2, 3):
            stage_cumulative[stage] = int((features_df[STAGE_COL] <= stage).sum())
    else:
        problems.append(f"Column {STAGE_COL!r} not found in candidate features CSV")

    for stage, expected in EXPECTED_STAGE_CUMULATIVE.items():
        actual = stage_cumulative.get(stage)
        if actual != expected:
            problems.append(f"Stage {stage} cumulative count={actual}, expected {expected}")

    manifest_target = manifest.get("target_distribution", {}).get(TARGET_COL, {})
    target_0 = manifest_target.get("n0")
    target_1 = manifest_target.get("n1")
    if target_0 != EXPECTED_TARGET_0 or target_1 != EXPECTED_TARGET_1:
        problems.append(
            f"target_distribution n0/n1={target_0}/{target_1}, "
            f"expected {EXPECTED_TARGET_0}/{EXPECTED_TARGET_1}"
        )

    endo_family_size = len(family_names)
    if endo_family_size != EXPECTED_ENDOMETRIOSIS_FAMILY_SIZE:
        problems.append(
            f"endometriosis family size={endo_family_size}, "
            f"expected {EXPECTED_ENDOMETRIOSIS_FAMILY_SIZE}"
        )

    domain_subset_matches = None
    if "domain" in features_df.columns and "variable" in features_df.columns:
        domain_subset = set(
            features_df.loc[
                features_df["domain"].isin(["endometriosis_phenotype", "prior_endo_surgery"]),
                "variable",
            ]
        )
        domain_subset_matches = domain_subset == family_names
        if not domain_subset_matches:
            only_in_family = family_names - domain_subset
            only_in_domain = domain_subset - family_names
            problems.append(
                "endometriosis family registry does not match the domain-derived "
                f"subset — only_in_family={sorted(only_in_family)}, "
                f"only_in_domain={sorted(only_in_domain)}"
            )

    cleaning_b_n_rows = cleaning_b_manifest.get("cleaned_rows")
    cleaning_b_n_cols = cleaning_b_manifest.get("cleaned_columns_total")
    if cleaning_b_n_rows != EXPECTED_N_ROWS:
        problems.append(f"Data Cleaning B n_rows={cleaning_b_n_rows}, expected {EXPECTED_N_ROWS}")

    report = ContractReport(
        ok=not problems,
        n_eligible_pool=n_eligible_pool,
        stage_cumulative=stage_cumulative,
        target_0=target_0,
        target_1=target_1,
        endometriosis_family_size=endo_family_size,
        endometriosis_family_matches_domain_subset=domain_subset_matches,
        cleaning_b_n_rows=cleaning_b_n_rows,
        cleaning_b_n_cols=cleaning_b_n_cols,
        problems=problems,
    )

    if strict and problems:
        raise PublicationContractError(
            "Publication analysis input contract violated:\n- " + "\n- ".join(problems)
        )

    return report


def validate_contract(strict: bool = True) -> ContractReport:
    """Validate cohort/stage/family counts against the metadata artifacts on disk.

    Reads only variable-level metadata (CSV/JSON manifests) and the
    hand-authored family registry's module-level constant — never the
    patient-level processed dataframe. This is "static validation" of the
    input contract, not real-data inferential analysis.

    Parameters
    ----------
    strict:
        If True (default), raise ``PublicationContractError`` on any
        mismatch. If False, return a ``ContractReport`` with ``ok=False``
        and the list of problems, without raising.
    """
    features_df = load_candidate_features()
    manifest = load_candidate_feature_manifest()
    cleaning_b_manifest = load_cleaning_b_manifest()
    family_names = _load_endometriosis_family_names()
    return validate_contract_from_data(
        features_df, manifest, cleaning_b_manifest, family_names, strict=strict
    )


if __name__ == "__main__":
    result = validate_contract(strict=False)
    print(f"Contract OK: {result.ok}")
    print(f"n_eligible_pool: {result.n_eligible_pool}")
    print(f"stage_cumulative: {result.stage_cumulative}")
    print(f"target_0/target_1: {result.target_0}/{result.target_1}")
    print(f"endometriosis_family_size: {result.endometriosis_family_size}")
    print(
        "endometriosis_family_matches_domain_subset: "
        f"{result.endometriosis_family_matches_domain_subset}"
    )
    print(f"cleaning_b_n_rows/n_cols: {result.cleaning_b_n_rows}/{result.cleaning_b_n_cols}")
    if result.problems:
        print("Problems:")
        for problem in result.problems:
            print(f"  - {problem}")

#!/usr/bin/env python3
"""Core utilities for the constrained final-modeling smoke test."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.feature_selection import mutual_info_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

try:
    from .forced_endo_logistic import (
        ForcedEndoLogisticRegression,
        logistic_elastic_net_objective,
        resolve_sample_weight,
        sigmoid,
        smooth_gradient,
    )
except ImportError:  # pragma: no cover - supports direct script execution.
    from forced_endo_logistic import (
        ForcedEndoLogisticRegression,
        logistic_elastic_net_objective,
        resolve_sample_weight,
        sigmoid,
        smooth_gradient,
    )

try:
    from .subject_groups import load_group_labels
except ImportError:  # pragma: no cover - supports direct script execution.
    from subject_groups import load_group_labels


ROOT = Path(__file__).resolve().parents[3]
TARGET = "target_intrapartum_cs"
SEED_BASE = 42
OUTER_FOLDS = 5
OUTER_REPEATS = 10
INNER_FOLDS = 5

EDA_C_DIR = ROOT / "outputs" / "eda_c"
FINAL_DIR = ROOT / "outputs" / "final_modeling"
SMOKE_DIR = FINAL_DIR / "smoke"
CORRECTED_PENALIZED_SMOKE_DIR = FINAL_DIR / "smoke_corrected_penalized"

MATRIX_PATH = EDA_C_DIR / "modeling_dataset_candidate_features.xlsx"
CANDIDATE_REGISTRY_PATH = EDA_C_DIR / "candidate_model_features.csv"
EDA_C_MANIFEST_PATH = EDA_C_DIR / "candidate_feature_manifest.json"

ENDOMETRIOSIS_TERMS = ("endo", "adenomyosis")
CLINICAL_FIXED_TERMS = {
    "AGE",
    "BMI_before",
    "nulliparity",
    "CS",
    "gestational_diabetes",
    "mode_of_conception_ivf_vs_all",
    "adenomyosis",
    "endometriosis_surgery",
}

VALIDATION_TOLERANCES = {
    "sklearn_max_abs_coef_diff": 1e-4,
    "sklearn_max_abs_probability_diff": 1e-5,
    "relative_gradient_error": 1e-5,
    "direct_objective_abs_diff": 1e-10,
    "direct_gradient_max_abs_diff": 1e-10,
    "reproducibility_max_abs_diff": 0.0,
}
MAX_SELECTED_ACTIVE_PREDICTORS = 20
MAX_SELECTED_ACTIVE_COUNT_RANGE = 12
ACTIVE_COUNT_GUARDRAIL_INVALID_REASON = "no_inner_candidate_passed_active_count_guardrails"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_blank(value: Any) -> str | None:
    # "ג€”," / "ג€”" are legacy encoding-compatibility guards (a known em-dash
    # mis-decode pattern -- UTF-8 bytes for "—" read back as Windows-1255).
    # They do not occur anywhere in the current canonical registry/data
    # (verified 2026-09-09 across every current and historical tracked
    # data file) and are retained unchanged, not "corrected" to "—", so
    # normalization behavior does not shift during final scientific
    # closure. See test_modeling_core_normalize_blank.py for the pinned
    # contract.
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text in {"-", "—", "ג€”,", "ג€”", "nan", "NaN"}:
        return None
    return text


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, np.bool_):
        return bool(value)
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def is_endometriosis_predictor(variable: str, domain: Any) -> bool:
    haystack = f"{variable} {domain}".lower()
    return any(term in haystack for term in ENDOMETRIOSIS_TERMS)


def registry_predictors(registry: pd.DataFrame) -> list[str]:
    if "variable" not in registry.columns:
        raise RuntimeError("Candidate registry is missing required 'variable' column.")
    predictors = registry["variable"].astype(str).tolist()
    if not predictors:
        raise RuntimeError("Candidate registry contains no predictors.")
    duplicates = sorted(registry.loc[registry["variable"].astype(str).duplicated(), "variable"].astype(str).unique())
    if duplicates:
        raise RuntimeError(f"Candidate registry contains duplicate predictor names: {duplicates}.")
    return predictors


def validate_modeling_input_contract(matrix: pd.DataFrame, registry: pd.DataFrame, manifest: dict[str, Any]) -> list[str]:
    """Validate the current EDA C modeling handoff without a historical count.

    The contract is registry-driven: matrix predictor columns must exactly match
    candidate_model_features.csv in the same order, and the manifest counts must
    describe that same handoff. This keeps the fail-loud guardrail while avoiding
    stale magic numbers from older 43-predictor runs.
    """
    target_count = list(matrix.columns).count(TARGET)
    if target_count != 1:
        raise RuntimeError(f"Modeling matrix must contain target column {TARGET!r} exactly once; found {target_count}.")
    duplicate_matrix_cols = sorted({col for col in matrix.columns if list(matrix.columns).count(col) > 1})
    if duplicate_matrix_cols:
        raise RuntimeError(f"Modeling matrix contains duplicate columns: {duplicate_matrix_cols}.")

    matrix_predictors = [col for col in matrix.columns if col != TARGET]
    registry_vars = registry_predictors(registry)
    if matrix_predictors != registry_vars:
        missing_from_matrix = sorted(set(registry_vars) - set(matrix_predictors))
        extra_in_matrix = sorted(set(matrix_predictors) - set(registry_vars))
        raise RuntimeError(
            "Candidate registry and modeling matrix are not synchronized. "
            f"missing_from_matrix={missing_from_matrix}; extra_in_matrix={extra_in_matrix}; "
            "order_match=False."
        )

    manifest_pool = manifest.get("n_eligible_pool")
    if manifest_pool != len(registry_vars):
        raise RuntimeError(
            "Candidate manifest n_eligible_pool does not match candidate registry count: "
            f"manifest={manifest_pool}; registry={len(registry_vars)}."
        )
    manifest_rows = manifest.get("n_rows")
    if manifest_rows != len(matrix):
        raise RuntimeError(
            f"Candidate manifest n_rows does not match modeling matrix rows: manifest={manifest_rows}; matrix={len(matrix)}."
        )
    target_events = int(matrix[TARGET].astype(int).sum())
    manifest_events = manifest.get("n_events")
    if manifest_events != target_events:
        raise RuntimeError(
            "Candidate manifest n_events does not match observed target events: "
            f"manifest={manifest_events}; matrix={target_events}."
        )
    if str(manifest.get("conclusion", "")).strip().upper() != "PASS":
        raise RuntimeError(f"Candidate manifest conclusion is not PASS: {manifest.get('conclusion')!r}.")
    return registry_vars


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    matrix = pd.read_excel(MATRIX_PATH)
    registry = pd.read_csv(CANDIDATE_REGISTRY_PATH)
    manifest = json.loads(EDA_C_MANIFEST_PATH.read_text(encoding="utf-8"))
    validate_modeling_input_contract(matrix, registry, manifest)
    return matrix, registry, manifest


def load_groups(matrix: pd.DataFrame) -> np.ndarray:
    """CV group labels (subject_number, or a singleton per missing-subject
    delivery record), row-aligned with `matrix` (as returned by
    load_inputs()). Passing the same subject's rows to both sides of a
    split/fold is a train/validation leakage bug; grouping on this array
    prevents it. Validates row-by-row alignment (not just row count) before
    returning -- see subject_groups.py for the full contract and proof."""
    return load_group_labels(matrix)


def build_stage_predictor_metadata(registry: pd.DataFrame) -> pd.DataFrame:
    """Canonical, non-selection modeling metadata table for the Final-D
    stage-based runner (stage_nested_cv_search.py, matched_unconstrained_
    benchmark.py). Preserves every current EDA C eligible registry row
    exactly once and in order -- no filtering, no gate -- and carries ONLY
    the metadata build_preprocessor() genuinely needs to dispatch a
    predictor to its preprocessing block: predictor identity, data type,
    model_preprocessing_contract_id, model_representation_type,
    model_entry_mode, earliest_entry_stage, and eligibility_status (for
    audit only).

    This table deliberately does NOT compute primary_model_eligible,
    meets_quality_bar, priority_score, or any substring/domain
    endometriosis-heuristic flag -- those are historical fields computed by
    the LEGACY build_modeling_eligibility_table() below (kept only for its
    other, pre-Final-D consumers: bootstrap_optimism/, expedited_corrected_
    model.py, corrected_penalized_smoke_test.py, smoke_test_final_search.py)
    and must never gate or filter the canonical stage runner. The canonical
    stage runner's candidate universe is defined ELSEWHERE and only there:
    stage_pools.load_stage_pools() (earliest_entry_stage-keyed, cumulative
    Stage 1/2/3) for which predictors are in scope, and endometriosis_family.
    ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY (the explicit, hand-reviewed,
    per-member-justified 35-member list) for the >= 1 endometriosis
    requirement -- never a field computed here.
    """
    canonical_predictors = registry_predictors(registry)
    rows: list[dict[str, Any]] = []
    for _, row in registry.iterrows():
        variable = str(row["variable"])
        rows.append(
            {
                "predictor": variable,
                "data_type": row.get("data_type"),
                "model_preprocessing_contract_id": normalize_blank(row.get("model_preprocessing_contract_id")),
                "model_representation_type": normalize_blank(row.get("model_representation_type")),
                "model_entry_mode": normalize_blank(row.get("model_entry_mode")),
                "earliest_entry_stage": row.get("earliest_entry_stage"),
                "eligibility_status": str(row.get("eligibility_status", "")).strip().lower(),
            }
        )
    table = pd.DataFrame(rows)
    validate_eligibility_table_contract(table, canonical_predictors)
    return table


def build_modeling_eligibility_table(registry: pd.DataFrame) -> pd.DataFrame:
    """LEGACY eligibility table (primary_model_eligible / meets_quality_bar /
    a substring-based endometriosis_domain heuristic + the fail-loud
    "no approved primary endometriosis-domain predictors" gate below). This
    predates the Final-D stage-keyed architecture and is kept ONLY for its
    other pre-Final-D consumers (bootstrap_optimism/, expedited_corrected_
    model.py, corrected_penalized_smoke_test.py, smoke_test_final_search.py).

    The canonical Final-D stage runner (stage_nested_cv_search.py,
    matched_unconstrained_benchmark.py) must NOT call this function -- it
    uses build_stage_predictor_metadata() above instead, so a historical
    quality-bar/eligibility-registry-field change here can never silently
    alter or block the canonical 70/76/81 stage pathway. Do not route any
    new canonical-path code through this function or its gate.
    """
    canonical_predictors = registry_predictors(registry)
    rows: list[dict[str, Any]] = []
    for _, row in registry.iterrows():
        variable = str(row["variable"])
        timing_uncertain = bool_value(row.get("timing_uncertain", False))
        quality_ok = bool_value(row.get("meets_quality_bar", False))
        eligible_status = str(row.get("eligibility_status", "")).strip().lower() == "eligible"
        primary_raw = str(row.get("primary_model_eligible", "")).strip().lower()
        primary_model_eligible = primary_raw == "yes" and quality_ok and not timing_uncertain and eligible_status
        sensitivity_analysis_eligible = eligible_status and primary_raw in {"yes", "review"} and not timing_uncertain
        endo_domain = is_endometriosis_predictor(variable, row.get("domain"))
        clinical_fixed = variable in CLINICAL_FIXED_TERMS
        statistically_selectable = primary_model_eligible and not clinical_fixed

        reasons = []
        if primary_raw != "yes":
            reasons.append(f"primary_model_eligible_registry={primary_raw or 'missing'}")
        if not quality_ok:
            reasons.append("below_quality_bar")
        if timing_uncertain:
            reasons.append("timing_uncertain")
        if not eligible_status:
            reasons.append("eda_c_status_not_eligible")
        if not reasons:
            reasons.append("approved_primary_model_candidate")

        rows.append(
            {
                "predictor": variable,
                "primary_model_eligible": bool(primary_model_eligible),
                "sensitivity_analysis_eligible": bool(sensitivity_analysis_eligible),
                "endometriosis_domain": bool(endo_domain),
                "timing_status": row.get("timing"),
                "timing_uncertain": timing_uncertain,
                "redundancy_group": normalize_blank(row.get("redundancy_group")),
                "clinical_fixed": bool(clinical_fixed),
                "statistically_selectable": bool(statistically_selectable),
                "eligibility_reason": "; ".join(reasons),
                "data_type": row.get("data_type"),
                "priority_score": row.get("priority_score"),
                "meets_quality_bar": quality_ok,
                "registry_primary_model_eligible": row.get("primary_model_eligible"),
                # eda_c_eligible: the QC-pass/fail gate alone (leakage,
                # separation, sparsity, missingness, zero-variance, etc.),
                # independent of timing. predictor_classification: the
                # authoritative original classification preserved by EDA C
                # (Decision 65, 2026-08-12) -- predictor_allowed,
                # secondary_near_delivery_predictor, or
                # intrapartum_predictor_exclude_from_prelabor_model. Both are
                # consumed by horizon_eligible_predictors() below; neither
                # replaces primary_model_eligible above, which remains the
                # existing (timing-derived) pre-labor-oriented signal used
                # elsewhere in this module.
                "eda_c_eligible": bool(eligible_status),
                "predictor_classification": normalize_blank(row.get("predictor_classification")),
                # Final D rebuild (2026-09-01): the registry's model-facing
                # preprocessing contract, surfaced here so build_preprocessor()
                # can dispatch on it (falls back to data_type when absent, e.g.
                # for synthetic hand-built eligibility tables in unit tests).
                "model_preprocessing_contract_id": normalize_blank(row.get("model_preprocessing_contract_id")),
                "model_entry_mode": normalize_blank(row.get("model_entry_mode")),
                "earliest_entry_stage": row.get("earliest_entry_stage"),
            }
        )
    table = pd.DataFrame(rows)
    validate_eligibility_table_contract(table, canonical_predictors)
    if table.loc[table["primary_model_eligible"] & table["endometriosis_domain"]].empty:
        raise RuntimeError("No approved primary endometriosis-domain predictors are available.")
    return table


def validate_eligibility_table_contract(table: pd.DataFrame, canonical_predictors: list[str]) -> None:
    if "predictor" not in table.columns:
        raise RuntimeError("Eligibility table is missing required 'predictor' column.")
    table_predictors = table["predictor"].astype(str).tolist()
    duplicates = sorted(table.loc[table["predictor"].astype(str).duplicated(), "predictor"].astype(str).unique())
    if table_predictors != canonical_predictors or duplicates:
        missing = sorted(set(canonical_predictors) - set(table_predictors))
        extra = sorted(set(table_predictors) - set(canonical_predictors))
        raise RuntimeError(
            "Eligibility table does not preserve the canonical candidate registry exactly once and in order. "
            f"missing={missing}; extra={extra}; duplicates={duplicates}."
        )


def primary_predictors(eligibility: pd.DataFrame) -> list[str]:
    return eligibility.loc[eligibility["primary_model_eligible"], "predictor"].astype(str).tolist()


def approved_endometriosis_predictors(eligibility: pd.DataFrame) -> list[str]:
    mask = eligibility["primary_model_eligible"] & eligibility["endometriosis_domain"]
    return eligibility.loc[mask, "predictor"].astype(str).tolist()


# ---------------------------------------------------------------------------
# Multi-horizon modeling boundary (Decision 65, clinical review with
# Dr. Keren and Dr. Shai, 2026-08-12; source-only implementation 2026-08-13,
# multi-horizon plan Batch 6).
#
# EDA C hands off ONE unified master candidate pool (predictor_allowed +
# secondary_near_delivery_predictor + intrapartum_predictor_exclude_from_
# prelabor_model, each variable's original classification preserved as
# predictor_classification -- see eda_c_part4_screening.py /
# eda_c_part1_setup_gate.py). The three prediction horizons are introduced
# ONLY here, at the modeling boundary, by filtering that one pool on
# predictor_classification -- never inside EDA C. This is the single
# reusable mechanism every model-fitting script should use to derive its
# horizon-specific predictor list; it does not alter estimator, CV, or
# bootstrap logic, and it does not create three separate pipelines -- the
# same Top-N / forced-endo-penalized (LASSO/Elastic Net) fitting code in this
# module is simply invoked with a different `selected`/predictor list per
# horizon.
#
# intrapartum_candidate_pending_timing_confirmation is intentionally absent
# from every horizon below (currently 0 members; excluded by definition until
# its timing is clinically resolved -- unaffected by this architecture).
HORIZON_PRE_LABOR = "pre_labor"
HORIZON_NEAR_DELIVERY = "near_delivery"
HORIZON_INTRAPARTUM = "intrapartum"

HORIZON_ALLOWED_CLASSIFICATIONS: dict[str, set[str]] = {
    HORIZON_PRE_LABOR: {"predictor_allowed"},
    HORIZON_NEAR_DELIVERY: {"predictor_allowed", "secondary_near_delivery_predictor"},
    HORIZON_INTRAPARTUM: {
        "predictor_allowed",
        "secondary_near_delivery_predictor",
        "intrapartum_predictor_exclude_from_prelabor_model",
    },
}


def horizon_eligible_predictors(eligibility: pd.DataFrame, horizon: str) -> list[str]:
    """The eligible predictor list for one modeling horizon, derived from the
    SAME EDA C master eligibility table `build_modeling_eligibility_table()`
    already produces -- no separate horizon-specific registry/file exists or
    is needed.

    A predictor is eligible for `horizon` iff:
      1. EDA C's QC screening did not hard-exclude it (`eda_c_eligible`,
         independent of timing -- leakage/separation/sparsity/missingness/
         zero-variance/etc.), AND
      2. its preserved original classification (`predictor_classification`)
         is one of the classes approved for that horizon
         (HORIZON_ALLOWED_CLASSIFICATIONS).

    Raises ValueError for an unknown horizon name, and RuntimeError if
    `eligibility` lacks the required columns (i.e. was built before EDA C's
    Decision 65 predictor_classification metadata existed upstream --
    requires a fresh EDA C rerun, not a code change here).
    """
    if horizon not in HORIZON_ALLOWED_CLASSIFICATIONS:
        raise ValueError(
            f"Unknown modeling horizon {horizon!r}; expected one of {sorted(HORIZON_ALLOWED_CLASSIFICATIONS)}."
        )
    required_cols = {"predictor", "eda_c_eligible", "predictor_classification"}
    missing_cols = required_cols - set(eligibility.columns)
    if missing_cols:
        raise RuntimeError(
            f"Eligibility table is missing required column(s) {sorted(missing_cols)} -- "
            "build_modeling_eligibility_table() must be run against an EDA C candidate "
            "registry that includes predictor_classification (Decision 65). Rerun EDA C "
            "before using horizon_eligible_predictors()."
        )
    allowed = HORIZON_ALLOWED_CLASSIFICATIONS[horizon]
    mask = eligibility["eda_c_eligible"] & eligibility["predictor_classification"].isin(allowed)
    return eligibility.loc[mask, "predictor"].astype(str).tolist()


# 2026-08-28 targeted-closure addendum (Delta 2, Part 3, corrected same day
# after independent re-review against the live candidate_model_features.csv):
# the ACTIVE runner (full_nested_cv_search.py) previously derived every
# selection path's candidate universe through primary_predictors()
# unconditionally, never horizon_eligible_predictors() -- that existed but
# nothing active actually called it with anything but its own internal test.
# candidate_universe_for_horizon()/endometriosis_candidate_universe_for_horizon()
# are the ONE shared dispatch every active selection path (Top-N, single-
# forced-penalized, Random Forest, and the module-level forced-endometriosis-
# candidate resolver in full_nested_cv_search.py) now routes through, so a
# requested horizon can never silently fall back to Stage 1 only, and no
# predictor outside the requested horizon can enter via any path -- without
# creating three independent modeling pipelines.
#
# CORRECTION: an earlier version of this dispatch special-cased
# horizon=HORIZON_PRE_LABOR to return primary_predictors()/
# approved_endometriosis_predictors() verbatim, reasoning that the
# equivalence between that legacy registry-field-driven gate and the
# canonical eda_c_eligible/predictor_classification=="predictor_allowed" gate
# was unverified. Verified against the live candidate_model_features.csv:
# they are NOT equivalent -- primary_predictors() yields 44 predictors vs.
# the canonical Stage-1 pool's 67 (canonical Stage 2 is 73, Stage 3 is 78);
# the legacy gate also omits several EDA-C-eligible endometriosis-domain
# candidates the canonical pool includes. primary_predictors() was silently
# UNDER-including the approved Stage-1 contract, not a safe subset of it.
# This is an intentional architecture correction, not an accidental
# widening: EVERY horizon, including the pre_labor default, now routes
# through horizon_eligible_predictors() uniformly -- there is no longer a
# special case here. primary_predictors()/approved_endometriosis_predictors()
# remain defined above for their other existing legacy consumers
# (bootstrap_optimism/, expedited_corrected_model.py,
# corrected_penalized_smoke_test.py, smoke_test_final_search.py -- none of
# which are the active horizon-aware full-search runner) but they no longer
# define the candidate universe for any horizon here.
def candidate_universe_for_horizon(eligibility: pd.DataFrame, horizon: str) -> list[str]:
    return horizon_eligible_predictors(eligibility, horizon)


def endometriosis_candidate_universe_for_horizon(eligibility: pd.DataFrame, horizon: str) -> list[str]:
    """The approved endometriosis-domain subset of
    candidate_universe_for_horizon(horizon) -- used to reserve/force an
    endometriosis predictor without that predictor ever being able to fall
    outside the requested horizon (Part 3B). Derived from the SAME canonical
    horizon_eligible_predictors() universe for every horizon, including
    pre_labor -- never falls back to the legacy approved_endometriosis_predictors()."""
    universe = set(horizon_eligible_predictors(eligibility, horizon))
    mask = eligibility["endometriosis_domain"] & eligibility["predictor"].astype(str).isin(universe)
    return eligibility.loc[mask, "predictor"].astype(str).tolist()


# 2026-08-27 correction (Part A9/A11/A13/A20/A22, supersedes only Decision
# 89's materialize-in-B mechanism -- Decisions 86/87 unaffected): B closes
# the representation decision for BMI_after, weight_in_pregnancy, and PPROM
# timing (category vocabulary, split concept, applicability gate), but the
# actual numeric cutpoints must be fitted training-fold-only, inside modeling
# CV -- never from the full cohort, never in B. FoldSafeQuantileCategoryTransformer
# below generalizes the removed Decision-88 FoldSafeTertileMissingCategoryTransformer
# to all three variables (tertile split for BMI_after/weight_in_pregnancy,
# gated median split for PPROM timing) instead of duplicating near-identical
# code three times.
class FoldSafeQuantileCategoryTransformer(BaseEstimator, TransformerMixin):
    """Fold-safe categorical representation for a genuinely data-derived-
    cutpoint variable. `fit()` computes the cutpoint(s) from TRAINING-FOLD,
    non-missing (and, if gated, applicable-subgroup) values only; `transform()`
    applies those SAME fitted cutpoint(s) unchanged to any other fold's data
    (train or validation) -- never refit, never computed from the full
    cohort. Output is a single column of nominal string labels, always fed
    into a OneHotEncoder afterward (never consumed as ordinal/numeric).

    split="tertile": labels=(low, mid, high); missing (or, if gated,
    genuinely-missing-within-applicable) rows get `missing_label`.
    split="median": labels=(earlier, later); requires gate_col/gate_value
    (e.g. PPROM==1) -- rows failing the gate get `gate_label`, rows passing
    the gate but missing the source value get `missing_label`.
    """

    def __init__(self, source_col, split, labels, missing_label,
                 gate_col=None, gate_value=None, gate_label=None):
        self.source_col = source_col
        self.split = split
        self.labels = labels
        self.missing_label = missing_label
        self.gate_col = gate_col
        self.gate_value = gate_value
        self.gate_label = gate_label

    def _applicable_mask(self, X):
        if self.gate_col is None:
            return pd.Series(True, index=X.index)
        return X[self.gate_col] == self.gate_value

    def fit(self, X, y=None):
        applicable_mask = self._applicable_mask(X)
        observed = X.loc[applicable_mask, self.source_col].dropna()
        if observed.empty:
            raise RuntimeError(
                f"FoldSafeQuantileCategoryTransformer({self.source_col!r}): no observed "
                "applicable values in this training fold to fit cutpoint(s) from."
            )
        if self.split == "tertile":
            self.cutpoints_ = (float(observed.quantile(1 / 3)), float(observed.quantile(2 / 3)))
        elif self.split == "median":
            self.cutpoints_ = (float(observed.median()),)
        else:
            raise ValueError(f"Unknown split type {self.split!r} (expected 'tertile' or 'median').")
        return self

    def transform(self, X):
        if not hasattr(self, "cutpoints_"):
            raise RuntimeError("FoldSafeQuantileCategoryTransformer.transform() called before fit().")
        applicable_mask = self._applicable_mask(X)
        out = pd.Series(pd.NA, index=X.index, dtype="object")
        if self.gate_col is not None:
            out.loc[~applicable_mask] = self.gate_label
        vals = X[self.source_col]
        observed_mask = applicable_mask & vals.notna()
        if self.split == "tertile":
            q33, q67 = self.cutpoints_
            low, mid, high = self.labels
            out.loc[observed_mask & (vals <= q33)] = low
            out.loc[observed_mask & (vals > q33) & (vals <= q67)] = mid
            out.loc[observed_mask & (vals > q67)] = high
        else:  # median
            (median_,) = self.cutpoints_
            earlier, later = self.labels
            out.loc[observed_mask & (vals < median_)] = earlier
            out.loc[observed_mask & (vals >= median_)] = later
        missing_mask = applicable_mask & vals.isna()
        out.loc[missing_mask] = self.missing_label
        if out.isna().any():
            raise RuntimeError(
                f"FoldSafeQuantileCategoryTransformer({self.source_col!r}): {int(out.isna().sum())} "
                "row(s) received no category label -- every row must be structurally-gated, "
                "genuinely-missing, or fall into a split bucket."
            )
        return out.to_numpy().reshape(-1, 1)

    def get_feature_names_out(self, input_features=None):
        return np.asarray([self.source_col])


class FoldSafeRecomputedBMITransformer(BaseEstimator, TransformerMixin):
    """BMI_before recompute-after-fold-safe-impute (Part A7). height and
    weight_before_pregnancy are read as internal transform DEPENDENCIES from
    the wider input X (present whenever BMI_before is selected, per
    build_preprocessor's column routing below) even when neither is
    independently present in `selected_columns` -- this is a dependency-
    access path, not a feature-selection path. `fit()` computes their
    training-fold-only medians; `transform()` fold-safe-imputes both with
    those fitted medians and recomputes BMI_before from the (possibly-
    imputed) values -- BMI_before itself is never independently median-
    imputed."""

    def fit(self, X, y=None):
        height_observed = X["height"].dropna()
        weight_observed = X["weight_before_pregnancy"].dropna()
        if height_observed.empty or weight_observed.empty:
            raise RuntimeError(
                "FoldSafeRecomputedBMITransformer: no observed height/weight_before_pregnancy "
                "in this training fold to fit medians from."
            )
        self.height_median_ = float(height_observed.median())
        self.weight_median_ = float(weight_observed.median())
        return self

    def transform(self, X):
        if not hasattr(self, "height_median_"):
            raise RuntimeError("FoldSafeRecomputedBMITransformer.transform() called before fit().")
        height = X["height"].fillna(self.height_median_)
        weight = X["weight_before_pregnancy"].fillna(self.weight_median_)
        bmi = weight / (height / 100) ** 2
        return bmi.to_numpy(dtype=float).reshape(-1, 1)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(["BMI_before"])


# Transform-source-only registry (Part A9/A11/A13): these raw columns may
# feed their fold-safe transformer internally as a dependency, but must never
# be routed through the generic numeric (median-impute) branch as a plain
# predictor. Keyed by the column build_preprocessor special-cases; each value
# describes the FoldSafeQuantileCategoryTransformer configuration used.
_FOLD_SAFE_QUANTILE_SPECS: dict[str, dict[str, Any]] = {
    "BMI_after": dict(
        source_col="BMI_after", split="tertile",
        labels=("low_observed", "mid_observed", "high_observed"), missing_label="not_documented",
    ),
    "weight_in_pregnancy": dict(
        source_col="weight_in_pregnancy", split="tertile",
        labels=("low_observed", "mid_observed", "high_observed"), missing_label="not_documented",
    ),
    "gestational_age_at_PPROM_days": dict(
        source_col="gestational_age_at_PPROM_days", split="median",
        labels=("PPROM_earlier", "PPROM_later"), missing_label="PPROM_timing_unknown",
        gate_col="PPROM", gate_value=1, gate_label="no_PPROM",
    ),
}
# Extra input columns each fold-safe-quantile spec needs beyond its own
# source_col (i.e. its gate column, when present).
_FOLD_SAFE_QUANTILE_EXTRA_COLS: dict[str, list[str]] = {
    "gestational_age_at_PPROM_days": ["PPROM"],
}
TRANSFORM_SOURCE_ONLY_COLS = frozenset(_FOLD_SAFE_QUANTILE_SPECS)

# Final D rebuild (2026-09-01): build_preprocessor() dispatches on the EDA C
# model-facing preprocessing contract id (candidate_model_features.csv,
# column model_preprocessing_contract_id) rather than on data_type + a
# hard-coded special-column set. The route names below feed the SAME
# transformer blocks / block names as before ("num", "cat", "fold_safe_<col>",
# "bmi_before_recompute"), so this is a dispatch-source change, not a
# behaviour change. A column with no contract id (synthetic unit-test
# eligibility tables) falls back to the legacy data_type dispatch.
_CONTRACT_ID_ROUTE: dict[str, str] = {
    "BIN_PASSTHROUGH_V1": "numeric",
    "NUM_PASSTHROUGH_FOLD_SCALE_V1": "numeric",
    "CAT_ONEHOT_FOLD_V1": "categorical",
    "FS_QUANTILE_CAT_V1": "fold_safe_quantile",
    "FS_PPROM_TIMING_CAT_V1": "fold_safe_quantile",
    "FS_RECOMPUTED_BMI_V1": "bmi_before_recompute",
}

# BMI_before's internal transform dependencies (Part A7) -- read from the
# wider input X even when neither is independently selected.
_BMI_BEFORE_DEPENDENCY_COLS = ["height", "weight_before_pregnancy"]

# ===========================================================================
# LEGACY / NON-CANONICAL -- DO NOT USE FOR THE FINAL D REBUILD.
# ===========================================================================
# `_REDUNDANT_CO_SELECTION_PAIRS` + `assert_no_redundant_co_selection()` are
# the OLD horizon-era co-entry guard. They have DRIFTED from the canonical
# EDA C contract: the list below still carries superseded pairwise BMI bans,
# the adenomyosis parent-vs-each-feature bans and the old PET bans, none of
# which are in the canonical 8-pair EDA C YAML.
#
# The Final D rebuild does NOT use any of this. Hard co-entry enforcement for
# the 9 primary constrained pathways is:
#   * the canonical 8-pair YAML (analysis/eda/notebook_build/eda_c/contracts/
#     model_coentry_constraints.yaml), loaded by constraint_contracts.py, and
#   * RESOLVED PRE-FIT by
#     constrained_selection.resolve_hard_coentry_pairs_training_only()
#     (global greedy training-fold rank-order).
# build_preprocessor() no longer calls assert_no_redundant_co_selection().
#
# This object is still imported ONLY by legacy functions in this module that
# are reachable exclusively from the retirement-guarded legacy runners
# (full_nested_cv_search.py etc., each `raise SystemExit(...)` on run) and by
# one legacy regression test. It is kept, unmodified, purely so those guarded
# paths still import; it must never be reintroduced onto a live path.
# ===========================================================================
_REDUNDANT_CO_SELECTION_PAIRS: list[tuple[str, str, str]] = [
    ("BMI_before", "height", "anthropometry (BMI_before vs. height)"),
    ("BMI_before", "weight_before_pregnancy", "anthropometry (BMI_before vs. weight_before_pregnancy)"),
    ("BMI_after", "height", "BMI_after mathematical source family (BMI_after vs. height)"),
    ("BMI_after", "weight_in_pregnancy", "BMI_after mathematical source family (BMI_after vs. weight_in_pregnancy)"),
    ("gestational_age_at_PPROM_days", "PPROM", "PPROM timing representation vs. raw binary PPROM"),
    # weight_in_pregnancy vs. weight_in_pregnancy__missing_ind: REMOVED
    # 2026-08-29 -- weight_in_pregnancy__missing_ind has been retired
    # entirely (Data Cleaning B no longer creates it; its former redundancy
    # with weight_in_pregnancy_cat's not_documented bucket is now moot since
    # the indicator can never exist to co-select with anything).
    ("indication_for_induction_status", "induction_any_bin", "indication_for_induction_status vs. induction_any_bin"),
    # 2026-08-29 (Urgent Fixset 01, Fix 1): derived_endo_surgery_adhesion_status
    # deterministically encodes the endometriosis_surgery binary state
    # (no_prior_endo_surgery maps to endometriosis_surgery zero; both
    # prior_surgery_with_documented_adhesions and
    # prior_surgery_without_documented_adhesions map to endometriosis_surgery
    # one). Structurally identical to the indication_for_induction_status /
    # induction_any_bin pair above (a derived status that reconstructs a raw
    # binary): both are Stage-one predictor-allowed and must never enter one
    # model as independent predictors. Dataset-level co-existence in Batch19
    # is fine -- only simultaneous independent MODEL ENTRY is prohibited.
    ("derived_endo_surgery_adhesion_status", "endometriosis_surgery", "endo surgery adhesion status vs. raw endometriosis_surgery binary"),
    # 2026-08-28 targeted correction (missingness/representation follow-up):
    # adenomyosis binary vs. its 12-column detailed multi-hot family
    # (adenomyosis_feature_1..11, adenomyosis_features_unknown). Only the
    # binary-vs-detailed relationship is prohibited -- the 12 detailed
    # members remain free to coexist with EACH OTHER (that is the intended
    # multi-label representation), since no pair among them is listed here.
    # Expressed as 12 explicit pairwise entries (not a new family-aware
    # guard type) to reuse assert_no_redundant_co_selection()'s existing
    # pairwise iteration unchanged -- consistent with this list's existing
    # architecture.
    ("adenomyosis", "adenomyosis_feature_1", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_feature_2", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_feature_3", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_feature_4", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_feature_5", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_feature_6", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_feature_7", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_feature_8", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_feature_9", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_feature_10", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_feature_11", "adenomyosis representation (binary vs. detailed multi-hot)"),
    ("adenomyosis", "adenomyosis_features_unknown", "adenomyosis representation (binary vs. detailed multi-hot)"),
    # 2026-08-28 targeted correction: future-safe PET representation
    # dependency guard. severe_PET_cat/any_PET_cat are currently UNSET
    # (not in the EDA C candidate pool) -- this entry is dormant in
    # practice until/unless that classification is ever resolved to
    # predictor_allowed, but the guard exists now so the two prohibited
    # pairs can never silently co-enter a fit once it is. mild_PET +
    # severe_PET_cat together remains explicitly ALLOWED (not listed here).
    ("any_PET_cat", "mild_PET", "PET representation (any_PET_cat vs. mild_PET)"),
    ("any_PET_cat", "severe_PET_cat", "PET representation (any_PET_cat vs. severe_PET_cat)"),
]


def assert_no_redundant_co_selection(selected_columns: list[str]) -> None:
    """Raises RuntimeError if `selected_columns` simultaneously contains both
    members of any registered redundant pair (Part A8/A10/A12/A13). This
    guard is about simultaneous MODEL ENTRY (independent selection) only --
    it says nothing about a transformer's internal dependency access (see
    FoldSafeRecomputedBMITransformer / _BMI_BEFORE_DEPENDENCY_COLS above,
    which read height/weight_before_pregnancy from the wider input X
    regardless of whether either is independently selected)."""
    selected_set = set(selected_columns)
    for col_a, col_b, family in _REDUNDANT_CO_SELECTION_PAIRS:
        if col_a in selected_set and col_b in selected_set:
            raise RuntimeError(
                f"Redundant co-selection: {col_a!r} and {col_b!r} cannot both be selected "
                f"as independent predictors ({family})."
            )


# 2026-08-28 targeted-closure addendum (Delta 2, Blocker 1): the horizon
# ELIGIBILITY universes (candidate_universe_for_horizon()) legitimately
# contain BOTH members of one or more _REDUNDANT_CO_SELECTION_PAIRS at once
# (e.g. Stage 1 already contains both BMI_before and height) -- each member
# individually remains an approved horizon candidate, but no single fitted
# model may contain both. Passing a full horizon universe straight into
# build_preprocessor() therefore always raises assert_no_redundant_co_
# selection()'s guard before fitting even begins. hard_conflict_partners_in_
# set() is the ONE shared primitive both resolution strategies below build
# on: select_top_n_with_reserved_endometriosis()'s skip-based greedy fill
# (never evicts an already-selected predictor, just declines to add a
# conflicting one), and resolve_hard_co_selection_conflicts_training_only()'s
# forced-predictor-aware resolution (may evict an already-resolved predictor
# to make room for a reserved forced predictor). Both ultimately still pass
# through assert_no_redundant_co_selection() as final defense-in-depth --
# this addendum does not weaken or remove that guard.
def hard_conflict_partners_in_set(predictor: str, already_selected: set[str] | list[str]) -> list[str]:
    """The subset of `already_selected` that would form a prohibited
    Decision-91 simultaneous-entry pair with `predictor` if both were
    selected together."""
    selected_set = set(already_selected)
    partners: list[str] = []
    for col_a, col_b, _family in _REDUNDANT_CO_SELECTION_PAIRS:
        if predictor == col_a and col_b in selected_set:
            partners.append(col_b)
        elif predictor == col_b and col_a in selected_set:
            partners.append(col_a)
    return partners


def _preprocessing_route(col: str, meta: pd.DataFrame) -> str:
    """Route `col` to a transformer block, dispatching on its EDA C
    model_preprocessing_contract_id when available and falling back to the
    legacy data_type + special-column dispatch when it is not (synthetic
    unit-test eligibility tables)."""
    cid = None
    if "model_preprocessing_contract_id" in meta.columns:
        raw = meta.loc[col, "model_preprocessing_contract_id"]
        cid = None if (raw is None or (isinstance(raw, float) and pd.isna(raw))) else str(raw)
    if cid and cid in _CONTRACT_ID_ROUTE:
        route = _CONTRACT_ID_ROUTE[cid]
    elif col in _FOLD_SAFE_QUANTILE_SPECS:
        route = "fold_safe_quantile"
    elif col == "BMI_before":
        route = "bmi_before_recompute"
    elif "data_type" in meta.columns and str(meta.loc[col, "data_type"]) == "categorical":
        route = "categorical"
    else:
        route = "numeric"

    if route == "fold_safe_quantile" and col not in _FOLD_SAFE_QUANTILE_SPECS:
        raise RuntimeError(
            f"build_preprocessor: {col!r} routes to a fold-safe quantile block but has no "
            f"_FOLD_SAFE_QUANTILE_SPECS entry (contract_id={cid!r})."
        )
    if route == "bmi_before_recompute" and col != "BMI_before":
        raise RuntimeError(f"build_preprocessor: only BMI_before uses the recompute block; got {col!r}.")
    if "model_entry_mode" in meta.columns:
        em = meta.loc[col, "model_entry_mode"]
        em = "" if (em is None or (isinstance(em, float) and pd.isna(em))) else str(em)
        if em == "transform_source_only" and route != "fold_safe_quantile":
            raise RuntimeError(
                f"build_preprocessor: {col!r} is model_entry_mode=transform_source_only "
                f"but routed to {route!r} -- it may only enter via its fold-safe transformer."
            )
    return route


def _one_hot_encoder(*, drop_first: bool):
    """OneHotEncoder for the constrained pathways.

    drop_first=False (default, penalized families): full K-column one-hot,
      handle_unknown='ignore' -> unseen category is all-zeros.
    drop_first=True (Correction 18, Top-N unpenalized only): deterministic
      reference-level / drop-one coding -- K observed training levels produce
      K-1 modelled columns so an intercept + all-K dummies design is never
      passed to an UNPENALIZED logistic regression. handle_unknown='ignore'
      still handles an unseen validation category without refitting: an
      unseen category is encoded as an all-zero vector, which has the SAME
      MODELED CONTRIBUTION as the dropped reference category under the
      fitted encoder, but it is NOT semantically the reference category --
      it is a genuinely unseen category that happens to share the reference
      level's all-zero encoding. The reference level itself is recoverable
      from the fitted encoder (categories_ / drop_idx_) -- see
      reference_levels()."""
    kwargs: dict[str, Any] = {"handle_unknown": "ignore"}
    if drop_first:
        kwargs["drop"] = "first"
    try:
        return OneHotEncoder(sparse_output=False, **kwargs)
    except TypeError:  # pragma: no cover - older sklearn compatibility.
        return OneHotEncoder(sparse=False, **kwargs)


def reference_levels(preprocessor: ColumnTransformer) -> dict[str, Any]:
    """Correction 18: for every drop-one (drop='first') OneHotEncoder in a
    fitted Top-N preprocessor, report {input_column: reference_level} so a
    coefficient table / calculator can reconstruct the dropped level later.
    Empty for a penalized (full-dummy) preprocessor."""
    out: dict[str, Any] = {}
    for name, trans, cols in preprocessor.transformers_:
        enc = None
        if hasattr(trans, "named_steps") and "encoder" in getattr(trans, "named_steps", {}):
            enc = trans.named_steps["encoder"]
        elif isinstance(trans, OneHotEncoder):
            enc = trans
        if enc is None or getattr(enc, "drop_idx_", None) is None:
            continue
        # 'cat' block: encoder.categories_ is parallel to `cols` (the source
        # categorical columns). 'fold_safe_<col>' block: the cutter emits one
        # derived label column, so categories_ has length 1 and the source
        # column (cols[0]) is the natural key.
        keys = list(cols)
        cat_lists = getattr(enc, "categories_", [])
        drop_idx = enc.drop_idx_
        for i, cats in enumerate(cat_lists):
            key = keys[i] if i < len(keys) else f"{name}[{i}]"
            di = drop_idx[i] if drop_idx is not None and i < len(drop_idx) else None
            out[str(key)] = None if di is None else cats[int(di)]
    return out


def build_preprocessor(
    selected_columns: list[str],
    eligibility: pd.DataFrame,
    scaling: bool = True,
    *,
    identifiable: bool = False,
) -> ColumnTransformer:
    # NOTE (Final D rebuild, 2026-09-01): co-entry / set-level constraint
    # enforcement is NO LONGER done here. It moved to the caller
    # (constrained_selection.py + constraint_contracts.py). Hard co-entry pairs
    # (canonical EDA C YAML, 8 pairs) are RESOLVED BEFORE this function is
    # called (constrained_selection.resolve_hard_coentry_pairs_training_only,
    # training-fold ranking only) so both members of a hard pair never reach a
    # single penalized preprocessor/estimator; a post-fit active-source check
    # (constraint_contracts.hard_pair_violations) stays as defence-in-depth.
    # The retired, drifted _REDUNDANT_CO_SELECTION_PAIRS guard is not applied
    # to this rebuild's pathways.
    #
    # identifiable=True (Correction 18): Top-N unpenalized logistic only --
    # every OneHotEncoder uses deterministic drop-one reference-level coding
    # (K training levels -> K-1 columns) so an intercept + full-dummy block is
    # never handed to an unpenalized fit. Penalized families keep full-dummy
    # coding (identifiable=False, the default) unchanged.
    meta = eligibility.set_index("predictor") if eligibility.index.name != "predictor" else eligibility
    routes = {col: _preprocessing_route(col, meta) for col in selected_columns}
    categorical_cols = [c for c in selected_columns if routes[c] == "categorical"]
    numeric_cols = [c for c in selected_columns if routes[c] == "numeric"]

    numeric_steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median"))]
    if scaling:
        numeric_steps.append(("scaler", StandardScaler()))

    encoder = _one_hot_encoder(drop_first=identifiable)

    transformers: list[tuple[str, Any, list[str]]] = []
    if numeric_cols:
        transformers.append(("num", Pipeline(numeric_steps), numeric_cols))
    if categorical_cols:
        transformers.append(
            (
                "cat",
                Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("encoder", encoder)]),
                categorical_cols,
            )
        )
    if any(routes[c] == "bmi_before_recompute" for c in selected_columns):
        # Only height/weight_before_pregnancy are read (dependencies) -- the
        # transformer always recomputes BMI_before fresh from them, uniformly
        # for every row, never consuming B's own partial pre-recompute.
        bmi_steps: list[tuple[str, Any]] = [("recompute", FoldSafeRecomputedBMITransformer())]
        if scaling:
            bmi_steps.append(("scaler", StandardScaler()))
        transformers.append(("bmi_before_recompute", Pipeline(bmi_steps), _BMI_BEFORE_DEPENDENCY_COLS))
    for col in selected_columns:
        if routes[col] != "fold_safe_quantile":
            continue
        spec = _FOLD_SAFE_QUANTILE_SPECS[col]
        input_cols = [spec["source_col"]] + _FOLD_SAFE_QUANTILE_EXTRA_COLS.get(col, [])
        fold_safe_encoder = _one_hot_encoder(drop_first=identifiable)
        quantile_pipe = Pipeline([
            ("cutter", FoldSafeQuantileCategoryTransformer(**spec)),
            ("encoder", fold_safe_encoder),
        ])
        transformers.append((f"fold_safe_{col}", quantile_pipe, input_cols))
    return ColumnTransformer(transformers=transformers, remainder="drop", verbose_feature_names_out=True)


def raw_predictor_from_transformed_name(name: str, raw_columns: list[str]) -> str:
    suffix = name.split("__", 1)[1] if "__" in name else name
    for column in sorted(raw_columns, key=len, reverse=True):
        if suffix == column or suffix.startswith(f"{column}_"):
            return column
    return suffix


def transformed_feature_mapping(preprocessor: ColumnTransformer, raw_columns: list[str]) -> pd.DataFrame:
    names = list(preprocessor.get_feature_names_out())
    rows = []
    for idx, transformed in enumerate(names):
        raw = raw_predictor_from_transformed_name(transformed, raw_columns)
        rows.append(
            {
                "transformed_feature_index": idx,
                "transformed_feature": transformed,
                "raw_predictor": raw,
                "transformer": transformed.split("__", 1)[0] if "__" in transformed else "raw",
            }
        )
    return pd.DataFrame(rows)


def make_outer_splits(y: pd.Series, groups: np.ndarray) -> list[dict[str, Any]]:
    """Repeated, group-aware, stratified outer splits. `groups` must be
    row-aligned with `y` (see load_groups()) so that no subject's delivery
    records ever appear on both sides of a split. Reimplements
    RepeatedStratifiedKFold's repeat/shuffle/seed structure on top of
    StratifiedGroupKFold, since sklearn has no built-in repeated variant of
    the group-aware splitter."""
    if len(groups) != len(y):
        raise RuntimeError(f"groups length ({len(groups)}) must match y length ({len(y)}).")
    groups_arr = np.asarray(groups)
    repeat_seeds = np.random.RandomState(SEED_BASE).randint(0, np.iinfo(np.int32).max, size=OUTER_REPEATS)
    splits = []
    for repeat, seed in enumerate(repeat_seeds, start=1):
        splitter = StratifiedGroupKFold(n_splits=OUTER_FOLDS, shuffle=True, random_state=int(seed))
        for fold, (train_idx, val_idx) in enumerate(
            splitter.split(np.zeros(len(y)), y.to_numpy(), groups_arr), start=1
        ):
            splits.append({"repeat": repeat, "fold": fold, "train_idx": train_idx, "val_idx": val_idx})
    return splits


def smoke_outer_splits(y: pd.Series, groups: np.ndarray) -> list[dict[str, Any]]:
    return [split for split in make_outer_splits(y, groups) if split["repeat"] == 1 and split["fold"] in {1, 2}]


def inner_seed(repeat: int, fold: int) -> int:
    return SEED_BASE * 1000 + repeat * 100 + fold


def make_inner_splits(
    y_train: pd.Series, groups_train: np.ndarray, repeat: int, fold: int
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Group-aware inner splits. `groups_train` must be row-aligned with
    `y_train` (i.e. sliced by the same outer train_idx, in the same order)
    so that no subject's delivery records ever appear on both sides of an
    inner fold."""
    if len(groups_train) != len(y_train):
        raise RuntimeError(f"groups_train length ({len(groups_train)}) must match y_train length ({len(y_train)}).")
    splitter = StratifiedGroupKFold(n_splits=INNER_FOLDS, shuffle=True, random_state=inner_seed(repeat, fold))
    return list(splitter.split(np.zeros(len(y_train)), y_train.to_numpy(), np.asarray(groups_train)))


def temporary_encoded_training_matrix(
    X_train: pd.DataFrame, candidate_registry: pd.DataFrame, candidate_columns: list[str]
) -> tuple[np.ndarray, list[str], list[bool]]:
    """Training-only encoded matrix for mutual-information ranking. Mirrors
    build_preprocessor()'s special-case routing (Part A9/A11/A13/A20/A22, this
    correction pass) so a candidate's RANKING representation never diverges
    from its final-fit representation:

      - BMI_before is never direct-median-imputed here -- it is recomputed
        from fold-safe (training-fold-only) medians of height/
        weight_before_pregnancy via the SAME FoldSafeRecomputedBMITransformer
        build_preprocessor() uses, read as internal dependencies exactly as
        in the real fit (present even when neither dependency is itself a
        ranking candidate).
      - BMI_after / weight_in_pregnancy / gestational_age_at_PPROM_days
        (TRANSFORM_SOURCE_ONLY_COLS) never reach the generic numeric
        median-impute branch either -- each is passed through the SAME
        FoldSafeQuantileCategoryTransformer spec used at fit time (training-
        fold-only cutpoints; PPROM read as an internal gate dependency for
        the PPROM-timing spec even when PPROM is not itself a candidate).
        Its nominal (one-hot-at-fit-time) category label is here given a
        technical OrdinalEncoder encoding -- fit on training data only --
        purely so mutual_info_classif has a single discrete column to score;
        this does not make the fitted model's own representation ordinal
        (build_preprocessor still one-hot-encodes it for every real fit).

    Every other candidate keeps the prior generic numeric (median-impute) or
    categorical (most-frequent-impute + OrdinalEncoder) branch unchanged.
    Exactly one ranking column -- and therefore one mutual-information score
    -- is produced per raw candidate predictor, preserving the existing
    one-score-per-raw-predictor ranking contract; no candidate is expanded
    into multiple one-hot ranking columns.
    """
    meta = candidate_registry.set_index("variable")
    special_cols = set(_FOLD_SAFE_QUANTILE_SPECS) | {"BMI_before"}
    categorical_cols = [
        col for col in candidate_columns
        if col not in special_cols and str(meta.loc[col, "data_type"]) == "categorical"
    ]
    numeric_cols = [
        col for col in candidate_columns
        if col not in special_cols and col not in categorical_cols
    ]
    special_ranking_cols = [col for col in candidate_columns if col in special_cols]

    parts = []
    ordered_columns: list[str] = []
    discrete_flags: list[bool] = []
    if numeric_cols:
        numeric = SimpleImputer(strategy="median").fit_transform(X_train[numeric_cols])
        parts.append(numeric)
        ordered_columns.extend(numeric_cols)
        discrete_flags.extend([str(meta.loc[col, "data_type"]) == "binary" for col in numeric_cols])
    if categorical_cols:
        cat_pipe = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
            ]
        )
        categorical = cat_pipe.fit_transform(X_train[categorical_cols])
        parts.append(categorical)
        ordered_columns.extend(categorical_cols)
        discrete_flags.extend([True] * len(categorical_cols))
    for col in special_ranking_cols:
        if col == "BMI_before":
            recomputed = FoldSafeRecomputedBMITransformer().fit_transform(X_train[_BMI_BEFORE_DEPENDENCY_COLS])
            parts.append(recomputed)
            ordered_columns.append(col)
            discrete_flags.append(False)
        else:
            spec = _FOLD_SAFE_QUANTILE_SPECS[col]
            input_cols = [spec["source_col"]] + _FOLD_SAFE_QUANTILE_EXTRA_COLS.get(col, [])
            labels = FoldSafeQuantileCategoryTransformer(**spec).fit_transform(X_train[input_cols])
            encoded = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1).fit_transform(labels)
            parts.append(encoded)
            ordered_columns.append(col)
            discrete_flags.append(True)
    if not parts:
        raise RuntimeError("No candidate columns available for ranking.")
    return np.concatenate(parts, axis=1), ordered_columns, discrete_flags


def rank_predictors_training_only(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    candidate_registry: pd.DataFrame,
    candidate_columns: list[str],
    seed: int,
) -> list[dict[str, Any]]:
    encoded, ordered_columns, discrete_flags = temporary_encoded_training_matrix(X_train, candidate_registry, candidate_columns)
    scores = mutual_info_classif(encoded, y_train.to_numpy(), discrete_features=discrete_flags, random_state=seed)
    meta = candidate_registry.set_index("variable")
    ranking = []
    for variable, score in zip(ordered_columns, scores):
        ranking.append(
            {
                "predictor": variable,
                "training_only_score": float(score),
                "redundancy_group": normalize_blank(meta.loc[variable, "redundancy_group"]),
                # priority_score is retained here for AUDIT/DESCRIPTION only
                # (2026-08-28 correction) -- it is EDA C's full-dataset
                # association-effect-size + FDR-significance-bonus score, not
                # training-fold-only, so it must never influence ordering or
                # selection. It used to be the sort tie-break below; a
                # training-fold MI tie (common for score=0) could then be
                # broken by full-cohort target-derived information, violating
                # the training-only feature-selection contract. The
                # deterministic tie-break is now the predictor name alone.
                "priority_score": float(meta.loc[variable, "priority_score"]),
                "endometriosis_domain": is_endometriosis_predictor(variable, meta.loc[variable, "domain"]),
            }
        )
    return sorted(ranking, key=lambda item: (-item["training_only_score"], item["predictor"]))


# 2026-08-28 backward-compatibility correction (Part 6, following the same-
# day multi-horizon correction above): select_top_n_with_reserved_
# endometriosis(), pooled_inner_topn_tuning(), and pooled_inner_single_
# forced_penalized_tuning() below default to horizon=None, NOT
# HORIZON_PRE_LABOR. candidate_universe_for_horizon()/endometriosis_
# candidate_universe_for_horizon() are now pure canonical dispatchers with no
# legacy special case (correct for the ACTIVE multi-horizon-aware runner,
# which always passes an explicit horizon string) -- but several OTHER,
# non-horizon-aware callers of these same shared functions
# (expedited_corrected_model.py, bootstrap_optimism/, corrected_penalized_
# smoke_test.py, smoke_test_final_search.py) never pass `horizon` at all,
# and would otherwise silently receive the canonical Stage-1 universe (67
# live predictors) in place of the legacy primary_model_eligible-based set
# (44 live predictors) they were built and validated against -- an
# unintended, undisclosed behavior change for code this pass never
# reviewed or re-validated. horizon=None now means explicit LEGACY mode:
# primary_predictors()/approved_endometriosis_predictors() exactly as
# before this whole horizon-aware correction began. Only an explicit
# horizon in {pre_labor, near_delivery, intrapartum} (as
# full_nested_cv_search.py's CLI default and every internal call always
# supplies) requests the canonical dispatch.
def select_top_n_with_reserved_endometriosis(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    candidate_registry: pd.DataFrame,
    eligibility: pd.DataFrame,
    n: int,
    seed: int,
    horizon: str | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    if horizon is None:
        candidates = primary_predictors(eligibility)
        endo_candidates = set(approved_endometriosis_predictors(eligibility))
    else:
        candidates = candidate_universe_for_horizon(eligibility, horizon)
        endo_candidates = set(endometriosis_candidate_universe_for_horizon(eligibility, horizon))
    if n < 1:
        raise ValueError("Top-N selection requires n >= 1.")
    ranking = rank_predictors_training_only(X_train, y_train, candidate_registry, candidates, seed)
    endo_ranked = [item for item in ranking if item["predictor"] in endo_candidates]
    if not endo_ranked:
        raise RuntimeError("Top-N selector found no approved endometriosis-domain candidate.")

    selected: list[str] = [endo_ranked[0]["predictor"]]
    used_groups = {endo_ranked[0]["redundancy_group"]} if endo_ranked[0]["redundancy_group"] else set()
    log_rows = []
    for rank, item in enumerate(ranking, start=1):
        selected_reason = None
        skip_reason = None
        if item["predictor"] == selected[0]:
            selected_reason = "reserved_highest_ranked_endometriosis_predictor"
        elif len(selected) < n:
            group = item["redundancy_group"]
            # 2026-08-28 correction (Blocker 1C): a hard Decision-91
            # simultaneous-entry conflict (hard_conflict_partners_in_set(),
            # the same shared primitive resolve_hard_co_selection_conflicts_
            # training_only() below uses) is checked in addition to the
            # pre-existing soft redundancy_group check -- the two mechanisms
            # are not uniformly represented by the same groups, so a hard
            # pair could previously survive this greedy fill and only fail
            # later, inside build_preprocessor(). Top-N never evicts an
            # already-selected predictor here; it simply declines to add a
            # conflicting one and continues to the next-ranked candidate.
            conflicting = hard_conflict_partners_in_set(item["predictor"], selected)
            if group and group in used_groups:
                skip_reason = "redundancy_group_already_selected"
            elif conflicting:
                skip_reason = "hard_co_selection_conflict"
            else:
                selected.append(item["predictor"])
                if group:
                    used_groups.add(group)
                selected_reason = "top_ranked_training_only_fill"
        elif item["predictor"] not in selected:
            skip_reason = "top_n_already_filled"

        log_rows.append(
            {
                "rank": rank,
                "predictor": item["predictor"],
                "training_only_score": item["training_only_score"],
                "redundancy_group": item["redundancy_group"],
                "endometriosis_domain": item["endometriosis_domain"],
                "selected": item["predictor"] in selected,
                "selected_reason": selected_reason,
                "skip_reason": skip_reason,
            }
        )
    if len(selected) != n:
        raise RuntimeError(f"Unable to select top {n} predictors; selected {len(selected)}.")
    if not any(p in endo_candidates for p in selected):
        raise RuntimeError("Top-N selection did not retain an approved endometriosis-domain predictor.")
    # Final defense-in-depth (Blocker 1C) -- must hold by construction given
    # the per-candidate check above; asserted explicitly before returning to
    # the caller (and therefore before model fitting) rather than relying
    # solely on build_preprocessor()'s own downstream guard.
    assert_no_redundant_co_selection(selected)
    return selected, log_rows


# 2026-08-28 targeted-closure addendum (Delta 2, Blocker 1D): the shared
# training-only resolver for forced-penalized and Random Forest, which
# (unlike Top-N's bounded greedy fill above) must accept the ENTIRE horizon
# eligibility universe as candidates and therefore cannot just skip
# conflicts -- a forced predictor must always win its own conflict rather
# than potentially being skipped. This is NOT a new global eligibility
# exclusion: a losing alternative here remains a full member of
# candidate_universe_for_horizon() and may win in a different training fold
# or under a different forced-predictor candidate -- only the transient,
# per-fit resolved list is affected.
def resolve_hard_co_selection_conflicts_training_only(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    candidate_registry: pd.DataFrame,
    candidate_universe: list[str],
    seed: int,
    forced_predictors: list[str] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    forced_list = list(forced_predictors or [])
    forced_set = set(forced_list)
    missing_forced = forced_set - set(candidate_universe)
    if missing_forced:
        raise RuntimeError(
            f"Forced predictor(s) {sorted(missing_forced)} are not in the supplied candidate universe."
        )
    for a in forced_list:
        if hard_conflict_partners_in_set(a, forced_set - {a}):
            raise RuntimeError(
                f"Forced predictors {forced_list} contain a pair that hard-conflicts with each other; "
                "at most one side of any Decision-91 conflict pair may be forced simultaneously."
            )

    # Training-only ranking (Blocker 2: predictor name is the sole
    # deterministic tie-break -- never priority_score) determines both the
    # fill order for non-forced candidates and, when a forced predictor
    # conflicts with an already-resolved candidate, which one a NON-forced
    # vs. NON-forced conflict would have favored (used only for the log/
    # audit trail below, not for any forced-vs-non-forced decision, which is
    # always won by the forced predictor).
    ranking = rank_predictors_training_only(X_train, y_train, candidate_registry, candidate_universe, seed)
    rank_order = [item["predictor"] for item in ranking]
    ordered = forced_list + [p for p in rank_order if p not in forced_set]

    resolved: set[str] = set()
    log_rows: list[dict[str, Any]] = []
    for predictor in ordered:
        is_forced = predictor in forced_set
        conflicting_resolved = hard_conflict_partners_in_set(predictor, resolved)
        if not conflicting_resolved:
            resolved.add(predictor)
            log_rows.append(
                {"predictor": predictor, "decision": "retained_forced_predictor" if is_forced else "retained", "conflicts_with": []}
            )
            continue
        if is_forced:
            # In practice unreachable given forced predictors are processed
            # first (above) and are pre-checked for mutual conflicts, so
            # `resolved` is always empty of conflicts when a forced
            # predictor is reached -- guarded defensively regardless: a
            # forced predictor always wins, evicting any already-resolved
            # conflicting predictor(s) rather than being skipped.
            for other in conflicting_resolved:
                resolved.discard(other)
                log_rows.append(
                    {
                        "predictor": other,
                        "decision": "excluded_hard_conflict_with_forced_predictor",
                        "conflicts_with": [predictor],
                    }
                )
            resolved.add(predictor)
            log_rows.append(
                {"predictor": predictor, "decision": "retained_forced_predictor", "conflicts_with": conflicting_resolved}
            )
        else:
            conflicts_with_forced = [c for c in conflicting_resolved if c in forced_set]
            decision = (
                "excluded_hard_conflict_with_forced_predictor" if conflicts_with_forced else "excluded_hard_conflict_lower_rank"
            )
            log_rows.append({"predictor": predictor, "decision": decision, "conflicts_with": conflicting_resolved})

    resolved_list = [p for p in rank_order if p in resolved]
    # Final defense-in-depth (Blocker 1B) -- must hold by construction; also
    # proves the resolver, not just Top-N, satisfies the same contract
    # assert_no_redundant_co_selection() enforces inside build_preprocessor().
    assert_no_redundant_co_selection(resolved_list)
    for forced in forced_list:
        if forced not in resolved:
            raise RuntimeError(f"Forced predictor {forced!r} was not retained by conflict resolution.")
    return resolved_list, log_rows


@dataclass(frozen=True)
class SmokeSpec:
    model_id: str
    family: str
    class_weight: str | None
    selection: str
    top_n_grid: tuple[int, ...] = ()
    C_grid: tuple[float, ...] = ()
    l1_ratio_grid: tuple[float, ...] = ()


def smoke_specs() -> list[SmokeSpec]:
    return [
        SmokeSpec(
            model_id="smoke_topn_logistic_unweighted",
            family="reserved_endometriosis_topn_logistic",
            class_weight=None,
            selection="topn",
            top_n_grid=(3, 5),
        ),
        SmokeSpec(
            model_id="smoke_topn_logistic_weighted",
            family="reserved_endometriosis_topn_logistic",
            class_weight="balanced",
            selection="topn",
            top_n_grid=(3, 5),
        ),
        SmokeSpec(
            model_id="smoke_forced_endo_lasso_weighted",
            family="forced_endometriosis_lasso_logistic",
            class_weight="balanced",
            selection="forced_penalized",
            C_grid=(0.1, 1.0),
            l1_ratio_grid=(1.0,),
        ),
        SmokeSpec(
            model_id="smoke_forced_endo_elastic_net_unweighted",
            family="forced_endometriosis_elastic_net_logistic",
            class_weight=None,
            selection="forced_penalized",
            C_grid=(0.1,),
            l1_ratio_grid=(0.3, 0.7),
        ),
    ]


def corrected_penalized_smoke_specs() -> list[SmokeSpec]:
    return [
        SmokeSpec(
            model_id="corrected_forced_endo_lasso_weighted",
            family="single_forced_endometriosis_lasso_logistic",
            class_weight="balanced",
            selection="single_forced_penalized",
            C_grid=(0.1, 1.0),
            l1_ratio_grid=(1.0,),
        ),
        SmokeSpec(
            model_id="corrected_forced_endo_lasso_unweighted",
            family="single_forced_endometriosis_lasso_logistic",
            class_weight=None,
            selection="single_forced_penalized",
            C_grid=(0.1, 1.0),
            l1_ratio_grid=(1.0,),
        ),
        SmokeSpec(
            model_id="corrected_forced_endo_elastic_net_weighted",
            family="single_forced_endometriosis_elastic_net_logistic",
            class_weight="balanced",
            selection="single_forced_penalized",
            C_grid=(0.1,),
            l1_ratio_grid=(0.3, 0.7),
        ),
        SmokeSpec(
            model_id="corrected_forced_endo_elastic_net_unweighted",
            family="single_forced_endometriosis_elastic_net_logistic",
            class_weight=None,
            selection="single_forced_penalized",
            C_grid=(0.1,),
            l1_ratio_grid=(0.3, 0.7),
        ),
    ]


def build_corrected_penalized_smoke_registry(eligible_forced_predictors: list[str]) -> dict[str, Any]:
    specs = []
    for spec in corrected_penalized_smoke_specs():
        specs.append(
            {
                "model_id": spec.model_id,
                "family": spec.family,
                "class_weight": spec.class_weight,
                "selection": spec.selection,
                "C_grid": list(spec.C_grid),
                "l1_ratio_grid": list(spec.l1_ratio_grid),
                "eligible_forced_endometriosis_predictors": eligible_forced_predictors,
                "outer_scope": "repeat_1_folds_1_2_only",
                "inner_cv": f"{INNER_FOLDS}-fold stratified, training fold only",
                "primary_scoring_metric": "pooled_inner_oof_average_precision",
                "selection_hierarchy": [
                    "PR-AUC primary",
                    "one-standard-error parsimony",
                    "Brier and calibration as guardrails",
                    "stability and convergence checks",
                ],
                "default_forced_predictor_count": 1,
                "maximum_two_forced_predictor_sensitivity": "registered_as_future_sensitivity_only_not_run",
                "active_count_stop_threshold": MAX_SELECTED_ACTIVE_PREDICTORS,
                "active_count_range_stop_threshold": MAX_SELECTED_ACTIVE_COUNT_RANGE,
            }
        )
    return {"created_utc": utc_now(), "specifications": specs}


def build_smoke_registry() -> dict[str, Any]:
    specs = []
    for spec in smoke_specs():
        specs.append(
            {
                "model_id": spec.model_id,
                "family": spec.family,
                "class_weight": spec.class_weight,
                "selection": spec.selection,
                "top_n_grid": list(spec.top_n_grid),
                "C_grid": list(spec.C_grid),
                "l1_ratio_grid": list(spec.l1_ratio_grid),
                "outer_scope": "repeat_1_folds_1_2_only",
                "inner_cv": f"{INNER_FOLDS}-fold stratified, training fold only",
                "primary_scoring_metric": "pooled_inner_oof_average_precision",
                "acceptance_rule": "at least one active approved endometriosis-domain predictor in every fitted/evaluated smoke fold",
            }
        )
    return {"created_utc": utc_now(), "specifications": specs}


def fit_predict_logistic(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    selected: list[str],
    eligibility: pd.DataFrame,
    class_weight: str | None,
) -> tuple[np.ndarray, LogisticRegression, pd.DataFrame]:
    preprocessor = build_preprocessor(selected, eligibility, scaling=True)
    # Pass the FULL X_train/X_val (not X_train[selected]) -- special
    # transformers (FoldSafeRecomputedBMITransformer, FoldSafeQuantileCategoryTransformer)
    # need dependency columns (e.g. height, weight_before_pregnancy, PPROM)
    # that may not be in `selected` itself (Part A7/A13 dependency-access,
    # not feature-selection). The ColumnTransformer's own named column
    # selectors + remainder="drop" ensure only the referenced columns are
    # ever actually used.
    X_train_t = preprocessor.fit_transform(X_train)
    X_val_t = preprocessor.transform(X_val)
    if not np.isfinite(X_train_t).all() or not np.isfinite(X_val_t).all():
        raise RuntimeError("Non-finite transformed values detected in Top-N logistic preprocessing.")
    model = LogisticRegression(
        C=np.inf,
        l1_ratio=0,
        solver="lbfgs",
        fit_intercept=True,
        class_weight=class_weight,
        max_iter=5000,
        tol=1e-10,
    )
    model.fit(X_train_t, y_train.to_numpy())
    probs = model.predict_proba(X_val_t)[:, 1]
    return probs, model, transformed_feature_mapping(preprocessor, selected)


def single_forced_penalty_factors(mapping: pd.DataFrame, forced_predictor: str) -> np.ndarray:
    factors = np.asarray([0.0 if raw == forced_predictor else 1.0 for raw in mapping["raw_predictor"]], dtype=float)
    zero_raw = sorted(set(mapping.loc[factors == 0.0, "raw_predictor"].astype(str)))
    if zero_raw != [forced_predictor]:
        raise RuntimeError(
            f"Default forced-endometriosis penalty assignment must zero exactly {forced_predictor!r}; got {zero_raw}."
        )
    return factors


# 2026-08-28 targeted-closure addendum (Delta 2, Part 5 -- horizon-aware
# endometriosis labeling/validation): validate_single_forced_penalty_
# assignment(), coefficient_table(), and fit_predict_forced_penalized()
# (below) each gained an optional `approved_endometriosis_candidates`
# parameter. When omitted (None, the default), behavior is UNCHANGED for
# every existing non-horizon-aware caller (legacy smoke scripts,
# expedited_corrected_model.py, bootstrap_optimism/, this module's own
# run_custom_estimator_validations self-test) -- they keep deriving the
# approved set from the legacy approved_endometriosis_predictors(eligibility)
# (a primary_model_eligible-based, pre-labor-only gate). Only the ACTIVE
# horizon-aware callers (pooled_inner_single_forced_penalized_tuning below,
# and full_nested_cv_search.py's run_one_model_fold()/fit_random_forest())
# pass this explicitly, derived once from
# endometriosis_candidate_universe_for_horizon(eligibility, horizon) --
# the SAME horizon-aware set candidate selection itself already uses -- so a
# Stage-2/3 endometriosis predictor that was correctly selected and fitted
# can no longer be mislabeled approved_endometriosis_domain=False, or make
# validate_active_endometriosis()'s "no active approved endometriosis
# predictor" guard fire incorrectly, purely because it falls outside the
# legacy primary_model_eligible gate.
def validate_single_forced_penalty_assignment(
    mapping: pd.DataFrame,
    penalty_factors: np.ndarray,
    forced_predictor: str,
    eligibility: pd.DataFrame,
    approved_endometriosis_candidates: list[str] | set[str] | None = None,
) -> None:
    approved_endo = (
        set(approved_endometriosis_candidates)
        if approved_endometriosis_candidates is not None
        else set(approved_endometriosis_predictors(eligibility))
    )
    zero_rows = mapping.loc[np.asarray(penalty_factors) == 0.0]
    zero_raw = sorted(set(zero_rows["raw_predictor"].astype(str)))
    if zero_raw != [forced_predictor]:
        raise RuntimeError(f"More than one raw predictor received zero penalty, or wrong raw predictor was zeroed: {zero_raw}.")
    if forced_predictor not in approved_endo:
        raise RuntimeError(f"Forced predictor {forced_predictor!r} is not an approved endometriosis-domain predictor.")
    other_endo = mapping["raw_predictor"].isin(approved_endo - {forced_predictor})
    if other_endo.any() and not np.all(np.asarray(penalty_factors)[other_endo.to_numpy()] == 1.0):
        raise RuntimeError("A non-forced endometriosis predictor inherited zero penalty.")
    non_forced = mapping["raw_predictor"].astype(str) != forced_predictor
    if non_forced.any() and not np.all(np.asarray(penalty_factors)[non_forced.to_numpy()] == 1.0):
        raise RuntimeError("A transformed column from another raw predictor inherited nonstandard penalty.")


def fit_predict_forced_penalized(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    selected: list[str],
    eligibility: pd.DataFrame,
    C: float,
    l1_ratio: float,
    class_weight: str | None,
    forced_predictor: str,
    approved_endometriosis_candidates: list[str] | set[str] | None = None,
) -> tuple[np.ndarray, ForcedEndoLogisticRegression, pd.DataFrame]:
    preprocessor = build_preprocessor(selected, eligibility, scaling=True)
    # See fit_predict_logistic's identical comment above -- full X_train/X_val
    # are passed so dependency columns are available to special transformers.
    X_train_t = preprocessor.fit_transform(X_train)
    X_val_t = preprocessor.transform(X_val)
    if not np.isfinite(X_train_t).all() or not np.isfinite(X_val_t).all():
        raise RuntimeError("Non-finite transformed values detected in forced penalized preprocessing.")
    mapping = transformed_feature_mapping(preprocessor, selected)
    factors = single_forced_penalty_factors(mapping, forced_predictor)
    validate_single_forced_penalty_assignment(
        mapping, factors, forced_predictor, eligibility,
        approved_endometriosis_candidates=approved_endometriosis_candidates,
    )
    model = ForcedEndoLogisticRegression(
        C=C,
        l1_ratio=l1_ratio,
        penalty_factors=factors,
        fit_intercept=True,
        class_weight=class_weight,
        max_iter=10000,
        tol=1e-8,
    )
    model.fit(np.asarray(X_train_t, dtype=float), y_train.to_numpy(dtype=int))
    if not model.converged_:
        raise RuntimeError(f"Forced estimator failed to converge: {model.failure_reason_}")
    forced_mask = mapping["raw_predictor"].astype(str) == forced_predictor
    forced_coefs = model.coef_[0][forced_mask.to_numpy()]
    if len(forced_coefs) == 0 or not np.isfinite(forced_coefs).all() or not (np.abs(forced_coefs) > 1e-8).any():
        raise RuntimeError(f"Forced predictor {forced_predictor!r} does not have a finite active coefficient.")
    probs = model.predict_proba(np.asarray(X_val_t, dtype=float))[:, 1]
    return probs, model, mapping


def metric_record(model_id: str, repeat: int, fold: int, y_true: pd.Series, probs: np.ndarray) -> dict[str, Any]:
    if not np.isfinite(probs).all():
        raise RuntimeError(f"Non-finite predictions for {model_id}, repeat={repeat}, fold={fold}.")
    y_arr = y_true.to_numpy(dtype=int)
    prevalence = float(np.mean(y_arr))
    predicted_label = (probs >= 0.5).astype(int)
    tp = int(((predicted_label == 1) & (y_arr == 1)).sum())
    tn = int(((predicted_label == 0) & (y_arr == 0)).sum())
    fp = int(((predicted_label == 1) & (y_arr == 0)).sum())
    fn = int(((predicted_label == 0) & (y_arr == 1)).sum())
    sensitivity = float(tp / (tp + fn)) if (tp + fn) else None
    specificity = float(tn / (tn + fp)) if (tn + fp) else None
    cal_intercept, cal_slope = calibration_intercept_slope(y_arr, probs)
    return {
        "model_id": model_id,
        "repeat": repeat,
        "fold": fold,
        "validation_n": int(len(y_true)),
        "validation_positive": int(y_arr.sum()),
        "validation_negative": int((1 - y_arr).sum()),
        "observed_prevalence": prevalence,
        "mean_predicted_probability": float(np.mean(probs)),
        "pr_auc": float(average_precision_score(y_arr, probs)),
        "roc_auc": float(roc_auc_score(y_arr, probs)) if len(np.unique(y_arr)) == 2 else None,
        "brier_score": float(brier_score_loss(y_arr, probs)),
        "calibration_intercept": cal_intercept,
        "calibration_slope": cal_slope,
        "sensitivity_at_0_5": sensitivity,
        "specificity_at_0_5": specificity,
    }


def calibration_intercept_slope(y_true: np.ndarray, probs: np.ndarray) -> tuple[float | None, float | None]:
    if len(np.unique(y_true)) != 2:
        return None, None
    clipped = np.clip(probs, 1e-6, 1.0 - 1e-6)
    logits = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
    if np.std(logits) <= 1e-12:
        return None, None
    try:
        model = LogisticRegression(C=np.inf, l1_ratio=0, solver="lbfgs", fit_intercept=True, max_iter=2000, tol=1e-10)
        model.fit(logits, y_true)
        return float(model.intercept_[0]), float(model.coef_[0, 0])
    except Exception:
        return None, None


def baseline_record(repeat: int, fold: int, y_train: pd.Series, y_val: pd.Series) -> dict[str, Any]:
    p = float(y_train.mean())
    y_arr = y_val.to_numpy(dtype=int)
    return {
        "baseline_id": "outer_train_prevalence_constant",
        "repeat": repeat,
        "fold": fold,
        "train_event_prevalence": p,
        "validation_observed_prevalence": float(y_arr.mean()),
        "baseline_pr_auc": float(y_arr.mean()),
        "baseline_brier_score": float(np.mean((y_arr - p) ** 2)),
        "constant_predicted_probability": p,
    }


def active_predictors_from_coefficients(
    coef: np.ndarray,
    mapping: pd.DataFrame,
    eligibility: pd.DataFrame,
    threshold: float = 1e-8,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    active_rows = []
    approved_endo = set(approved_endometriosis_predictors(eligibility))
    for coef_value, (_, row) in zip(coef, mapping.iterrows()):
        raw = str(row["raw_predictor"])
        is_active = abs(float(coef_value)) > threshold
        active_rows.append(
            {
                "transformed_feature": row["transformed_feature"],
                "raw_predictor": raw,
                "coefficient": float(coef_value),
                "active": bool(is_active),
                "approved_endometriosis_domain": raw in approved_endo,
            }
        )
    active_predictors = sorted({row["raw_predictor"] for row in active_rows if row["active"]})
    active_endo = sorted({row["raw_predictor"] for row in active_rows if row["active"] and row["approved_endometriosis_domain"]})
    return active_predictors, active_endo, active_rows


def coefficient_table(
    coef: np.ndarray,
    mapping: pd.DataFrame,
    eligibility: pd.DataFrame,
    penalty_factors: np.ndarray | None = None,
    threshold: float = 1e-8,
    approved_endometriosis_candidates: list[str] | set[str] | None = None,
) -> list[dict[str, Any]]:
    approved_endo = (
        set(approved_endometriosis_candidates)
        if approved_endometriosis_candidates is not None
        else set(approved_endometriosis_predictors(eligibility))
    )
    rows = []
    for idx, (coef_value, (_, row)) in enumerate(zip(coef, mapping.iterrows())):
        raw = str(row["raw_predictor"])
        rows.append(
            {
                "transformed_feature": row["transformed_feature"],
                "raw_predictor": raw,
                "coefficient": float(coef_value),
                "active": bool(abs(float(coef_value)) > threshold),
                "approved_endometriosis_domain": raw in approved_endo,
                "penalty_factor": None if penalty_factors is None else float(penalty_factors[idx]),
            }
        )
    return rows


def active_summary_from_coefficient_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    active = [row for row in rows if row["active"]]
    active_endo = sorted({row["raw_predictor"] for row in active if row["approved_endometriosis_domain"]})
    active_non_endo = sorted({row["raw_predictor"] for row in active if not row["approved_endometriosis_domain"]})
    return {
        "active_endometriosis_predictors": active_endo,
        "active_non_endometriosis_predictors": active_non_endo,
        "total_active_predictor_count": len(set(active_endo).union(active_non_endo)),
        "active_transformed_feature_count": len(active),
    }


def annotate_active_count_guardrails(candidate_rows: list[dict[str, Any]]) -> float:
    valid = [row for row in candidate_rows if row["valid_fit"]]
    if not valid:
        raise RuntimeError("No valid corrected penalized tuning candidates were available.")
    best = sorted(valid, key=lambda row: (-row["pooled_inner_oof_pr_auc"], row["pooled_inner_oof_brier"]))[0]
    threshold = best["pooled_inner_oof_pr_auc"] - best["inner_pr_auc_standard_error"]
    for row in candidate_rows:
        one_se = bool(row["valid_fit"] and row["pooled_inner_oof_pr_auc"] >= threshold)
        mean_pass = bool(
            row["valid_fit"]
            and row["total_active_predictor_count_mean"] is not None
            and row["total_active_predictor_count_mean"] <= MAX_SELECTED_ACTIVE_PREDICTORS
        )
        range_pass = bool(
            row["valid_fit"]
            and row["total_active_predictor_count_range"] is not None
            and row["total_active_predictor_count_range"] <= MAX_SELECTED_ACTIVE_COUNT_RANGE
        )
        row["one_standard_error_eligible"] = one_se
        row["active_count_mean_guardrail_pass"] = mean_pass
        row["active_count_range_guardrail_pass"] = range_pass
        row["active_count_guardrails_pass"] = bool(mean_pass and range_pass)
    return float(threshold)


def one_standard_error_parsimony_choice(candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in candidate_rows if row["valid_fit"]]
    if not valid:
        raise RuntimeError("No valid corrected penalized tuning candidates were available.")
    annotate_active_count_guardrails(candidate_rows)
    eligible = [row for row in valid if row["one_standard_error_eligible"] and row["active_count_guardrails_pass"]]
    if not eligible:
        return {
            "status": "completed_invalid",
            "invalid_fit_reason": ACTIVE_COUNT_GUARDRAIL_INVALID_REASON,
            "selection_reason": "no_one_standard_error_candidate_passed_active_count_guardrails",
        }
    return sorted(
        eligible,
        key=lambda row: (
            row["total_active_predictor_count_mean"],
            row["active_transformed_feature_count_mean"],
            row["pooled_inner_oof_brier"],
            abs(row["calibration_slope"] - 1.0) if row["calibration_slope"] is not None else 999.0,
            -row["pooled_inner_oof_pr_auc"],
            row["forced_endometriosis_predictor"],
            row["param_C"],
            row["param_l1_ratio"],
        ),
    )[0]


def pooled_inner_topn_tuning(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    groups_train: np.ndarray,
    candidate_registry: pd.DataFrame,
    eligibility: pd.DataFrame,
    repeat: int,
    fold: int,
    spec: SmokeSpec,
    horizon: str | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    rows = []
    for n in spec.top_n_grid:
        oof = np.zeros(len(y_train), dtype=float)
        selected_by_inner = []
        for inner_i, (inner_tr_idx, inner_val_idx) in enumerate(
            make_inner_splits(y_train.reset_index(drop=True), groups_train, repeat, fold), start=1
        ):
            X_inner_tr = X_train.iloc[inner_tr_idx].reset_index(drop=True)
            y_inner_tr = y_train.iloc[inner_tr_idx].reset_index(drop=True)
            X_inner_val = X_train.iloc[inner_val_idx].reset_index(drop=True)
            selected, _ = select_top_n_with_reserved_endometriosis(
                X_inner_tr, y_inner_tr, candidate_registry, eligibility, n=n,
                seed=inner_seed(repeat, fold) + inner_i, horizon=horizon,
            )
            probs, _, _ = fit_predict_logistic(X_inner_tr, y_inner_tr, X_inner_val, selected, eligibility, spec.class_weight)
            oof[inner_val_idx] = probs
            selected_by_inner.append(selected)
        score = float(average_precision_score(y_train.to_numpy(dtype=int), oof))
        rows.append(
            {
                "model_id": spec.model_id,
                "repeat": repeat,
                "fold": fold,
                "param_top_n": n,
                "param_C": None,
                "param_l1_ratio": None,
                "pooled_inner_oof_pr_auc": score,
                "pooled_inner_oof_brier": float(brier_score_loss(y_train.to_numpy(dtype=int), oof)),
                "selected_predictors_by_inner_fold": json.dumps(selected_by_inner, ensure_ascii=False),
                "selected_for_outer_refit": False,
            }
        )
    best = sorted(rows, key=lambda row: (-row["pooled_inner_oof_pr_auc"], row["param_top_n"]))[0]
    for row in rows:
        row["selected_for_outer_refit"] = row["param_top_n"] == best["param_top_n"]
    return int(best["param_top_n"]), rows


def pooled_inner_penalized_tuning(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    groups_train: np.ndarray,
    eligibility: pd.DataFrame,
    repeat: int,
    fold: int,
    spec: SmokeSpec,
) -> tuple[dict[str, float], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    failures = []
    selected = primary_predictors(eligibility)
    for C in spec.C_grid:
        for l1_ratio in spec.l1_ratio_grid:
            oof = np.zeros(len(y_train), dtype=float)
            diagnostics_by_inner = []
            for inner_i, (inner_tr_idx, inner_val_idx) in enumerate(
                make_inner_splits(y_train.reset_index(drop=True), groups_train, repeat, fold), start=1
            ):
                X_inner_tr = X_train.iloc[inner_tr_idx].reset_index(drop=True)
                y_inner_tr = y_train.iloc[inner_tr_idx].reset_index(drop=True)
                X_inner_val = X_train.iloc[inner_val_idx].reset_index(drop=True)
                try:
                    probs, model, _ = fit_predict_forced_penalized(
                        X_inner_tr, y_inner_tr, X_inner_val, selected, eligibility, C, l1_ratio, spec.class_weight
                    )
                except Exception as exc:
                    failures.append(
                        {
                            "model_id": spec.model_id,
                            "repeat": repeat,
                            "fold": fold,
                            "inner_fold": inner_i,
                            "param_C": C,
                            "param_l1_ratio": l1_ratio,
                            "failure_reason": str(exc),
                        }
                    )
                    raise
                oof[inner_val_idx] = probs
                diagnostics_by_inner.append(model.diagnostics())
            score = float(average_precision_score(y_train.to_numpy(dtype=int), oof))
            rows.append(
                {
                    "model_id": spec.model_id,
                    "repeat": repeat,
                    "fold": fold,
                    "param_top_n": None,
                    "param_C": C,
                    "param_l1_ratio": l1_ratio,
                    "pooled_inner_oof_pr_auc": score,
                    "pooled_inner_oof_brier": float(brier_score_loss(y_train.to_numpy(dtype=int), oof)),
                    "selected_predictors_by_inner_fold": None,
                    "estimator_diagnostics_by_inner_fold": json.dumps(clean_json(diagnostics_by_inner), ensure_ascii=False),
                    "selected_for_outer_refit": False,
                }
            )
    best = sorted(rows, key=lambda row: (-row["pooled_inner_oof_pr_auc"], row["param_C"], row["param_l1_ratio"]))[0]
    for row in rows:
        row["selected_for_outer_refit"] = row["param_C"] == best["param_C"] and row["param_l1_ratio"] == best["param_l1_ratio"]
    return {"C": float(best["param_C"]), "l1_ratio": float(best["param_l1_ratio"])}, rows, failures


def pooled_inner_single_forced_penalized_tuning(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    groups_train: np.ndarray,
    eligibility: pd.DataFrame,
    repeat: int,
    fold: int,
    spec: SmokeSpec,
    forced_candidates: list[str],
    guardrail_failure_as_invalid: bool = False,
    horizon: str | None = None,
    candidate_registry: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    # 2026-08-28 correction (Blocker 1D/1E, then Part 6 backward-compat
    # follow-up same day): candidate_universe_for_horizon() is the horizon
    # ELIGIBILITY universe, which legitimately contains BOTH members of one
    # or more _REDUNDANT_CO_SELECTION_PAIRS at once -- it must never be
    # passed directly to fit_predict_forced_penalized() as the model-entry
    # set (that would always raise assert_no_redundant_co_selection() before
    # fitting), so an explicit horizon triggers hard-conflict resolution
    # below. horizon=None (the default) is explicit LEGACY mode instead --
    # non-horizon-aware callers of this shared function
    # (expedited_corrected_model.py, bootstrap_optimism/,
    # corrected_penalized_smoke_test.py, smoke_test_final_search.py) keep
    # getting exactly primary_predictors()/approved_endometriosis_
    # predictors() with NO resolution machinery applied, preserving their
    # pre-existing behavior byte-for-byte (including, if the legacy set
    # itself contains a hard conflict, the pre-existing fail-loud
    # build_preprocessor() guard -- never silently resolved out from under
    # them). The active horizon-aware runner always supplies an explicit
    # horizon (see full_nested_cv_search.py) and therefore always uses the
    # canonical dispatch + resolver path.
    if horizon is None:
        candidate_universe = primary_predictors(eligibility)
        approved_endometriosis_candidates = approved_endometriosis_predictors(eligibility)
    else:
        if candidate_registry is None:
            candidate_registry = pd.read_csv(CANDIDATE_REGISTRY_PATH)
        candidate_universe = candidate_universe_for_horizon(eligibility, horizon)
        # Derived once from the SAME horizon-aware set candidate selection
        # above already used, and threaded explicitly through every
        # downstream labeling/validation call below -- never re-derived via
        # the legacy primary_model_eligible-based
        # approved_endometriosis_predictors().
        approved_endometriosis_candidates = endometriosis_candidate_universe_for_horizon(eligibility, horizon)
    y_train_array = y_train.to_numpy(dtype=int)
    for forced_predictor in forced_candidates:
        # Hard Decision-91 conflicts are resolved once per (forced_predictor,
        # inner fold) -- training-fold-only, independent of C/l1_ratio -- and
        # reused across the C x l1_ratio grid for this forced predictor
        # (Blocker 1D/1E: never fit on the full 431-row cohort, never uses
        # inner-validation values to choose the representation; the forced
        # predictor is reserved during resolution). LEGACY mode (horizon is
        # None) skips this machinery entirely -- every inner fit uses the
        # unresolved candidate_universe directly, exactly as before this
        # whole horizon-aware correction began.
        if horizon is None:
            inner_resolution = None
        else:
            inner_resolution: dict[int, tuple[list[str], list[dict[str, Any]]]] = {}
            for inner_i, (inner_tr_idx, _inner_val_idx) in enumerate(
                make_inner_splits(y_train.reset_index(drop=True), groups_train, repeat, fold), start=1
            ):
                X_inner_tr_resolve = X_train.iloc[inner_tr_idx].reset_index(drop=True)
                y_inner_tr_resolve = y_train.iloc[inner_tr_idx].reset_index(drop=True)
                inner_resolution[inner_i] = resolve_hard_co_selection_conflicts_training_only(
                    X_inner_tr_resolve,
                    y_inner_tr_resolve,
                    candidate_registry,
                    candidate_universe,
                    seed=inner_seed(repeat, fold) + inner_i,
                    forced_predictors=[forced_predictor],
                )
        for C in spec.C_grid:
            for l1_ratio in spec.l1_ratio_grid:
                oof = np.zeros(len(y_train), dtype=float)
                inner_details: list[dict[str, Any]] = []
                valid_fit = True
                invalid_reason = None
                for inner_i, (inner_tr_idx, inner_val_idx) in enumerate(
                    make_inner_splits(y_train.reset_index(drop=True), groups_train, repeat, fold), start=1
                ):
                    X_inner_tr = X_train.iloc[inner_tr_idx].reset_index(drop=True)
                    y_inner_tr = y_train.iloc[inner_tr_idx].reset_index(drop=True)
                    X_inner_val = X_train.iloc[inner_val_idx].reset_index(drop=True)
                    y_inner_val = y_train.iloc[inner_val_idx].reset_index(drop=True)
                    if inner_resolution is None:
                        resolved_predictors, resolution_log = candidate_universe, []
                    else:
                        resolved_predictors, resolution_log = inner_resolution[inner_i]
                    try:
                        probs, model, mapping = fit_predict_forced_penalized(
                            X_inner_tr,
                            y_inner_tr,
                            X_inner_val,
                            resolved_predictors,
                            eligibility,
                            C,
                            l1_ratio,
                            spec.class_weight,
                            forced_predictor,
                            approved_endometriosis_candidates=approved_endometriosis_candidates,
                        )
                        oof[inner_val_idx] = probs
                        coef_rows = coefficient_table(
                            model.coef_[0], mapping, eligibility, model.penalty_factors_,
                            approved_endometriosis_candidates=approved_endometriosis_candidates,
                        )
                        summary = active_summary_from_coefficient_rows(coef_rows)
                        forced_rows = [row for row in coef_rows if row["raw_predictor"] == forced_predictor]
                        forced_active = any(row["active"] and np.isfinite(row["coefficient"]) for row in forced_rows)
                        if not forced_active:
                            raise RuntimeError(f"Forced predictor {forced_predictor!r} was not active in inner fold {inner_i}.")
                        diagnostics = model.diagnostics()
                        inner_details.append(
                            {
                                "inner_fold": inner_i,
                                "forced_endometriosis_predictor": forced_predictor,
                                "valid_fit": True,
                                "inner_pr_auc": float(average_precision_score(y_inner_val.to_numpy(dtype=int), probs)),
                                "inner_brier": float(brier_score_loss(y_inner_val.to_numpy(dtype=int), probs)),
                                "convergence": diagnostics,
                                "active_endometriosis_predictors": summary["active_endometriosis_predictors"],
                                "active_non_endometriosis_predictors": summary["active_non_endometriosis_predictors"],
                                "total_active_predictor_count": summary["total_active_predictor_count"],
                                "active_transformed_feature_count": summary["active_transformed_feature_count"],
                                "coefficients": coef_rows,
                                "resolved_predictors": resolved_predictors,
                                "hard_conflict_resolution_log": resolution_log,
                            }
                        )
                    except Exception as exc:
                        valid_fit = False
                        invalid_reason = str(exc)
                        inner_details.append(
                            {
                                "inner_fold": inner_i,
                                "forced_endometriosis_predictor": forced_predictor,
                                "valid_fit": False,
                                "invalid_fit_reason": invalid_reason,
                            }
                        )
                        break

                if valid_fit:
                    cal_intercept, cal_slope = calibration_intercept_slope(y_train_array, oof)
                    inner_pr = [item["inner_pr_auc"] for item in inner_details]
                    active_counts = [item["total_active_predictor_count"] for item in inner_details]
                    active_counts_array = np.asarray(active_counts, dtype=float)
                    transformed_counts = [item["active_transformed_feature_count"] for item in inner_details]
                    all_active_endo = sorted(
                        {
                            predictor
                            for item in inner_details
                            for predictor in item["active_endometriosis_predictors"]
                            if predictor != forced_predictor
                        }
                    )
                    all_active_non_endo = sorted(
                        {
                            predictor
                            for item in inner_details
                            for predictor in item["active_non_endometriosis_predictors"]
                        }
                    )
                    row = {
                        "model_id": spec.model_id,
                        "repeat": repeat,
                        "fold": fold,
                        "forced_endometriosis_predictor": forced_predictor,
                        "param_C": C,
                        "param_l1_ratio": l1_ratio,
                        "valid_fit": True,
                        "invalid_fit_reason": None,
                        "pooled_inner_oof_pr_auc": float(average_precision_score(y_train_array, oof)),
                        "inner_pr_auc_mean": float(np.mean(inner_pr)),
                        "inner_pr_auc_standard_error": float(np.std(inner_pr, ddof=1) / np.sqrt(len(inner_pr))),
                        "pooled_inner_oof_brier": float(brier_score_loss(y_train_array, oof)),
                        "calibration_intercept": cal_intercept,
                        "calibration_slope": cal_slope,
                        "other_active_endometriosis_predictors": json.dumps(all_active_endo, ensure_ascii=False),
                        "active_non_endometriosis_predictors": json.dumps(all_active_non_endo, ensure_ascii=False),
                        "total_active_predictor_count_mean": float(np.mean(active_counts)),
                        "total_active_predictor_count_min": int(np.min(active_counts)),
                        "total_active_predictor_count_max": int(np.max(active_counts)),
                        "total_active_predictor_count_range": int(np.max(active_counts) - np.min(active_counts)),
                        "total_active_predictor_count_std": float(np.std(active_counts_array, ddof=1)),
                        "total_active_predictor_count_iqr": float(
                            np.percentile(active_counts_array, 75) - np.percentile(active_counts_array, 25)
                        ),
                        "active_transformed_feature_count_mean": float(np.mean(transformed_counts)),
                        "all_inner_converged": bool(all(item["convergence"]["converged"] for item in inner_details)),
                        "inner_fold_details": json.dumps(clean_json(inner_details), ensure_ascii=False),
                        "selected_for_outer_refit": False,
                    }
                else:
                    row = {
                        "model_id": spec.model_id,
                        "repeat": repeat,
                        "fold": fold,
                        "forced_endometriosis_predictor": forced_predictor,
                        "param_C": C,
                        "param_l1_ratio": l1_ratio,
                        "valid_fit": False,
                        "invalid_fit_reason": invalid_reason,
                        "pooled_inner_oof_pr_auc": None,
                        "inner_pr_auc_mean": None,
                        "inner_pr_auc_standard_error": None,
                        "pooled_inner_oof_brier": None,
                        "calibration_intercept": None,
                        "calibration_slope": None,
                        "other_active_endometriosis_predictors": None,
                        "active_non_endometriosis_predictors": None,
                        "total_active_predictor_count_mean": None,
                        "total_active_predictor_count_min": None,
                        "total_active_predictor_count_max": None,
                        "total_active_predictor_count_range": None,
                        "total_active_predictor_count_std": None,
                        "total_active_predictor_count_iqr": None,
                        "active_transformed_feature_count_mean": None,
                        "all_inner_converged": False,
                        "inner_fold_details": json.dumps(clean_json(inner_details), ensure_ascii=False),
                        "selected_for_outer_refit": False,
                    }
                rows.append(row)

    best = one_standard_error_parsimony_choice(rows)
    if best.get("status") == "completed_invalid":
        if not guardrail_failure_as_invalid:
            raise RuntimeError("Corrected penalized candidates failed active-count stability guardrails.")
        return best, rows
    for row in rows:
        row["selected_for_outer_refit"] = bool(
            row["valid_fit"]
            and row["forced_endometriosis_predictor"] == best["forced_endometriosis_predictor"]
            and row["param_C"] == best["param_C"]
            and row["param_l1_ratio"] == best["param_l1_ratio"]
        )
    return {
        "forced_endometriosis_predictor": best["forced_endometriosis_predictor"],
        "C": float(best["param_C"]),
        "l1_ratio": float(best["param_l1_ratio"]),
        "selection_reason": "one_standard_error_parsimony_after_pooled_inner_oof_pr_auc",
    }, rows


def validate_no_outer_leakage(train_idx: np.ndarray, val_idx: np.ndarray, repeat: int, fold: int) -> None:
    if set(train_idx).intersection(set(val_idx)):
        raise RuntimeError(f"Outer train/validation overlap detected for repeat={repeat}, fold={fold}.")


def validate_active_endometriosis(model_id: str, repeat: int, fold: int, active_endo: list[str]) -> None:
    if not active_endo:
        raise RuntimeError(f"No active approved endometriosis-domain predictor for {model_id}, repeat={repeat}, fold={fold}.")


def direct_weighted_objective(
    theta: np.ndarray,
    X: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    C: float,
    l1_ratio: float,
    penalty_factors: np.ndarray,
) -> float:
    intercept = theta[0]
    beta = theta[1:]
    weight_sum = float(weights.sum())
    alpha = 1.0 / (C * weight_sum)
    linear = intercept + X @ beta
    y_signed = 2.0 * y - 1.0
    loss = np.sum(weights * np.logaddexp(0.0, -y_signed * linear)) / weight_sum
    l2 = 0.5 * alpha * (1.0 - l1_ratio) * np.sum(penalty_factors * beta * beta)
    l1 = alpha * l1_ratio * np.sum(penalty_factors * np.abs(beta))
    return float(loss + l2 + l1)


def direct_weighted_smooth_gradient(
    theta: np.ndarray,
    X: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    C: float,
    l1_ratio: float,
    penalty_factors: np.ndarray,
) -> np.ndarray:
    intercept = theta[0]
    beta = theta[1:]
    weight_sum = float(weights.sum())
    alpha = 1.0 / (C * weight_sum)
    residual = (sigmoid(intercept + X @ beta) - y) * weights / weight_sum
    return np.concatenate([[float(residual.sum())], X.T @ residual + alpha * (1.0 - l1_ratio) * penalty_factors * beta])


def run_custom_estimator_validations() -> dict[str, Any]:
    report: dict[str, Any] = {
        "created_utc": utc_now(),
        "tolerances": VALIDATION_TOLERANCES,
        "conventions": {
            "loss_normalization": "weighted mean logistic loss divided by sum(sample_weight)",
            "sample_weight_normalization": "sample weights are used as supplied; class_weight='balanced' is computed from the training fold only and then multiplied into sample_weight",
            "intercept_handling": "intercept is a separate unpenalized coefficient with penalty factor 0",
            "sklearn_C_mapping": "custom alpha = 1 / (C * sum(sample_weight)); objective = weighted_mean_loss + alpha * penalty, matching sklearn lbfgs L2 after common division by sum(sample_weight)",
            "l1_handling": "exact soft-thresholding proximal step for penalized coefficients; no smooth L1 approximation",
            "step_strategy": "initial step = inverse logistic/L2 Lipschitz bound; deterministic backtracking halves step until smooth upper-bound condition passes; next iteration may expand up to the Lipschitz step",
            "convergence": "stop when proximal residual <= tol; smoke uses tol=1e-8 and max_iter=10000",
        },
        "checks": {},
        "blocking_passed": False,
    }

    rng = np.random.default_rng(20260722)
    X = rng.normal(size=(80, 6))
    logits = -0.3 + X @ np.array([0.8, -0.4, 0.0, 0.5, -0.2, 0.3])
    y = (rng.random(80) < sigmoid(logits)).astype(int)
    if len(np.unique(y)) < 2:
        y[0], y[1] = 0, 1

    C = 0.7
    sklearn_model = LogisticRegression(
        C=C,
        l1_ratio=0,
        solver="lbfgs",
        fit_intercept=True,
        class_weight="balanced",
        max_iter=10000,
        tol=1e-12,
    )
    sklearn_model.fit(X, y)
    custom_model = ForcedEndoLogisticRegression(
        C=C,
        l1_ratio=0.0,
        penalty_factors=np.ones(X.shape[1]),
        fit_intercept=True,
        class_weight="balanced",
        max_iter=30000,
        tol=1e-11,
    )
    custom_model.fit(X, y)
    coef_diff = float(
        np.max(
            np.abs(
                np.concatenate([custom_model.intercept_, custom_model.coef_[0]])
                - np.concatenate([sklearn_model.intercept_, sklearn_model.coef_[0]])
            )
        )
    )
    prob_diff = float(np.max(np.abs(custom_model.predict_proba(X)[:, 1] - sklearn_model.predict_proba(X)[:, 1])))
    report["checks"]["sklearn_l2_equivalence"] = {
        "passed": bool(
            custom_model.converged_
            and coef_diff <= VALIDATION_TOLERANCES["sklearn_max_abs_coef_diff"]
            and prob_diff <= VALIDATION_TOLERANCES["sklearn_max_abs_probability_diff"]
        ),
        "max_abs_coef_diff": coef_diff,
        "max_abs_probability_diff": prob_diff,
        "custom_diagnostics": custom_model.diagnostics(),
    }

    theta = rng.normal(size=X.shape[1] + 1)
    factors = np.array([0.0, 1.0, 0.5, 1.0, 0.0, 1.0])
    weights = resolve_sample_weight(y, None, "balanced")
    direct_obj = direct_weighted_objective(theta, X, y, weights, C=1.3, l1_ratio=0.4, penalty_factors=factors)
    estimator_obj = logistic_elastic_net_objective(theta, X, y, weights, 1.3, 0.4, factors, True)
    direct_grad = direct_weighted_smooth_gradient(theta, X, y, weights, C=1.3, l1_ratio=0.4, penalty_factors=factors)
    estimator_grad = smooth_gradient(theta, X, y, weights, 1.3, 0.4, factors, True)
    report["checks"]["weighted_objective_and_gradient_formula"] = {
        "passed": bool(
            abs(direct_obj - estimator_obj) <= VALIDATION_TOLERANCES["direct_objective_abs_diff"]
            and float(np.max(np.abs(direct_grad - estimator_grad)))
            <= VALIDATION_TOLERANCES["direct_gradient_max_abs_diff"]
        ),
        "objective_abs_diff": float(abs(direct_obj - estimator_obj)),
        "gradient_max_abs_diff": float(np.max(np.abs(direct_grad - estimator_grad))),
        "sample_weight_sum": float(weights.sum()),
    }

    theta_fd = rng.normal(size=X.shape[1] + 1)
    grad = smooth_gradient(theta_fd, X, y, weights, 1.1, 0.0, np.ones(X.shape[1]), True)
    eps = 1e-6
    approx = np.zeros_like(theta_fd)
    for idx in range(len(theta_fd)):
        step = np.zeros_like(theta_fd)
        step[idx] = eps
        plus = logistic_elastic_net_objective(theta_fd + step, X, y, weights, 1.1, 0.0, np.ones(X.shape[1]), True)
        minus = logistic_elastic_net_objective(theta_fd - step, X, y, weights, 1.1, 0.0, np.ones(X.shape[1]), True)
        approx[idx] = (plus - minus) / (2.0 * eps)
    rel_error = float(np.linalg.norm(grad - approx) / max(1.0, np.linalg.norm(grad), np.linalg.norm(approx)))
    report["checks"]["finite_difference_smooth_gradient"] = {
        "passed": bool(rel_error <= VALIDATION_TOLERANCES["relative_gradient_error"]),
        "relative_gradient_error": rel_error,
    }

    penalty_mapping = pd.DataFrame(
        {
            "transformed_feature": [
                "num__adenomyosis",
                "num__AGE",
                "cat__endometrioma_size_status_no_endometrioma",
                "cat__endometrioma_size_status_endometrioma_less_than_30mm",
            ],
            "raw_predictor": ["adenomyosis", "AGE", "endometrioma_size_status", "endometrioma_size_status"],
        }
    )
    synthetic_eligibility = pd.DataFrame(
        {
            "predictor": ["adenomyosis", "AGE", "endometrioma_size_status"],
            "primary_model_eligible": [True, True, True],
            "endometriosis_domain": [True, False, True],
        }
    )
    penalty = single_forced_penalty_factors(penalty_mapping, "endometrioma_size_status")
    validate_single_forced_penalty_assignment(penalty_mapping, penalty, "endometrioma_size_status", synthetic_eligibility)
    report["checks"]["single_forced_penalty_factors"] = {
        "passed": bool(np.array_equal(penalty, np.array([1.0, 1.0, 0.0, 0.0]))),
        "intercept_penalty_factor": 0.0,
        "computed_non_intercept_penalty_factors": penalty.tolist(),
        "zero_penalty_raw_predictors": sorted(set(penalty_mapping.loc[penalty == 0.0, "raw_predictor"])),
        "normal_penalty_endometriosis_predictors": sorted(
            set(penalty_mapping.loc[(penalty == 1.0) & (penalty_mapping["raw_predictor"] == "adenomyosis"), "raw_predictor"])
        ),
    }

    synthetic = pd.DataFrame(
        {
            "AGE": [30.0, np.nan, 37.0, 29.0],
            "adenomyosis": [1, 0, 1, 0],
            "endometrioma_size_status": [
                "no_endometrioma",
                "endometrioma_less_than_30mm",
                "endometrioma_30mm_or_more",
                "endometrioma_size_unknown",
            ],
        }
    )
    feature_eligibility = pd.DataFrame(
        {
            "predictor": ["AGE", "adenomyosis", "endometrioma_size_status"],
            "data_type": ["numeric", "binary", "categorical"],
            "primary_model_eligible": [True, True, True],
            "endometriosis_domain": [False, True, True],
        }
    )
    preprocessor = build_preprocessor(list(synthetic.columns), feature_eligibility, scaling=True)
    transformed = preprocessor.fit_transform(synthetic)
    mapping = transformed_feature_mapping(preprocessor, list(synthetic.columns))
    expected_raw = {"AGE", "adenomyosis", "endometrioma_size_status"}
    report["checks"]["feature_mapping"] = {
        "passed": bool(np.isfinite(transformed).all() and set(mapping["raw_predictor"]) == expected_raw),
        "transformed_features": mapping["transformed_feature"].tolist(),
        "raw_predictors": mapping["raw_predictor"].tolist(),
    }

    forced_active_model = ForcedEndoLogisticRegression(
        C=0.2,
        l1_ratio=1.0,
        penalty_factors=np.array([0.0, 1.0, 1.0, 1.0]),
        class_weight=None,
        max_iter=20000,
        tol=1e-10,
    )
    X_forced = rng.normal(size=(120, 4))
    y_forced = (rng.random(120) < sigmoid(0.2 + 1.4 * X_forced[:, 0] + 0.1 * X_forced[:, 1])).astype(int)
    if len(np.unique(y_forced)) < 2:
        y_forced[0], y_forced[1] = 0, 1
    forced_active_model.fit(X_forced, y_forced)
    forced_coef = float(forced_active_model.coef_[0, 0])
    report["checks"]["forced_predictor_active_coefficient"] = {
        "passed": bool(forced_active_model.converged_ and np.isfinite(forced_coef) and abs(forced_coef) > 1e-8),
        "forced_coefficient": forced_coef,
        "diagnostics": forced_active_model.diagnostics(),
    }

    repro_a = ForcedEndoLogisticRegression(
        C=0.5,
        l1_ratio=0.7,
        penalty_factors=np.array([0.0, 1.0, 1.0, 0.0, 1.0, 1.0]),
        class_weight="balanced",
        max_iter=20000,
        tol=1e-10,
    ).fit(X, y)
    repro_b = ForcedEndoLogisticRegression(
        C=0.5,
        l1_ratio=0.7,
        penalty_factors=np.array([0.0, 1.0, 1.0, 0.0, 1.0, 1.0]),
        class_weight="balanced",
        max_iter=20000,
        tol=1e-10,
    ).fit(X, y)
    repro_coef_diff = float(np.max(np.abs(repro_a.coef_ - repro_b.coef_)))
    repro_prob_diff = float(np.max(np.abs(repro_a.predict_proba(X)[:, 1] - repro_b.predict_proba(X)[:, 1])))
    report["checks"]["reproducibility"] = {
        "passed": bool(
            repro_a.converged_
            and repro_b.converged_
            and repro_coef_diff <= VALIDATION_TOLERANCES["reproducibility_max_abs_diff"]
            and repro_prob_diff <= VALIDATION_TOLERANCES["reproducibility_max_abs_diff"]
        ),
        "max_abs_coef_diff": repro_coef_diff,
        "max_abs_probability_diff": repro_prob_diff,
        "diagnostics_a": repro_a.diagnostics(),
        "diagnostics_b": repro_b.diagnostics(),
    }

    report["blocking_passed"] = all(check["passed"] for check in report["checks"].values())
    if not report["blocking_passed"]:
        failed = [name for name, check in report["checks"].items() if not check["passed"]]
        report["failure_reason"] = f"Blocking custom-estimator validation failed: {failed}"
    else:
        report["failure_reason"] = None
    return report


def reproducibility_hash(*frames: pd.DataFrame, registry: dict[str, Any] | None = None) -> str:
    text = ""
    for frame in frames:
        text += frame.to_csv(index=False, float_format="%.12g")
    if registry is not None:
        text += json.dumps(clean_json(registry), sort_keys=True, ensure_ascii=False)
    return sha256_text(text)


def smoke_manifest(
    prediction_hash_1: str,
    prediction_hash_2: str,
    manifest_hash_1: str,
    manifest_hash_2: str,
    validation_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "created_utc": utc_now(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
        "sklearn_version": sklearn.__version__,
        "seed_base": SEED_BASE,
        "outer_repeat": 1,
        "outer_folds": [1, 2],
        "inner_folds": INNER_FOLDS,
        "input_hashes": {
            "modeling_dataset_candidate_features": sha256_file(MATRIX_PATH),
            "candidate_model_features": sha256_file(CANDIDATE_REGISTRY_PATH),
            "candidate_feature_manifest": sha256_file(EDA_C_MANIFEST_PATH),
        },
        "custom_estimator_validation_passed": bool(validation_report["blocking_passed"]),
        "prediction_hash_first": prediction_hash_1,
        "prediction_hash_second": prediction_hash_2,
        "prediction_hash_match": prediction_hash_1 == prediction_hash_2,
        "full_manifest_hash_first": manifest_hash_1,
        "full_manifest_hash_second": manifest_hash_2,
        "full_manifest_hash_match": manifest_hash_1 == manifest_hash_2,
        "holdout_accessed": False,
        "full_search_run": False,
        "commit_made": False,
    }

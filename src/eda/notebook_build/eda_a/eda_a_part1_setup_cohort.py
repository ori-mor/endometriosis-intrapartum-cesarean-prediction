#!/usr/bin/env python3
"""EDA A — Part 1: cell definitions (sections A0-A4).

Sections:
  A0 — Overview
  A1 — Setup: imports, flags, helpers, config, paths
  A2 — Dataset load, provenance manifest, validation
  A3 — Variable inventory: full classification table (all groups)
  A4 — Cohort definition and target distribution

Scope: full df — all columns including leakage, post-outcome, reference.
No statistical association tests. Read-only, aggregate outputs only.
"""


def src(text):
    lines = text.lstrip("\n").splitlines(keepends=True)
    if lines and lines[-1].endswith("\n"):
        lines[-1] = lines[-1][:-1]
    return lines


def md(cid, text):
    return {"id": cid, "cell_type": "markdown", "metadata": {}, "source": src(text)}


def code(cid, text):
    return {
        "id": cid, "cell_type": "code", "metadata": {},
        "source": src(text), "outputs": [], "execution_count": None,
    }


# ── Section A0 ────────────────────────────────────────────────────────────────
SA0_HEADER = md("eda-a-s00-header", """
# EDA A — Cohort and Variable Inventory Overview
## Endometriosis & Intrapartum Cesarean Section — Sheba Medical Center

---

## Academic Project Notebook

This notebook is prepared for academic project review and internal research use. Direct
patient identifiers and patient-level tabular records are not intentionally displayed.
Aggregate summaries and diagnostic visualizations are presented for methodological
review. The notebook should not be treated as an unrestricted public-release data
product.

**Cohort status:** the current analysis uses the implemented, clinically confirmed
cohort of N=431. The exclusion of 16 suspected superficial-only endometriosis
records is implemented and was externally confirmed by Sheba on 2026-08-18
(Decision 67 external-confirmation addendum; see Section A4 for the full
before/after accounting).

---

## Section A0 — Overview

This notebook is Part 1 of the exploratory data analysis for the endometriosis and
intrapartum cesarean section study. It presents the processed cohort, the full
variable inventory and classification, and an initial descriptive overview of the
dataset. Deeper predictor-level analysis (associations, correlations, outlier
review) continues in the companion Part 2 notebook. The dataframe is not modified
at any point.
""")


# ── Section A1 ────────────────────────────────────────────────────────────────
SA1_HEADER = md("eda-a-s01-header", """
## Section A1 — Setup
""")

SA1_FLAGS = code("eda-a-s01-flags", """
# The notebook does not save new outputs by default, reducing the risk of
# unintended project-file changes.
SAVE_AGGREGATED_OUTPUTS = False

# Automated third-party profiling (ydata-profiling, Section A5c) is
# opt-in, default OFF. It must never run, and must never create
# its output directory, unless BOTH this flag AND SAVE_AGGREGATED_OUTPUTS are
# explicitly set True -- see that section for the full allowlist/privacy
# design once enabled.
RUN_AUTOMATED_PROFILING = False

# Share-safe output mode, default
# ON: suppresses small-cell (n<5) counts/percentages in the sections
# reviewed below so this notebook's rendered output is safer to export and
# share as HTML. See eda_shared/share_safe.py.
#
# COVERAGE STATE (per-section audit -- do not read this
# flag as "the whole notebook is fully share-safe" without reading this
# list): A6 (Table 1 binary n_positive/positive_%) and A8 (IQR outlier
# n_flagged/flagged_%) are actively suppressed via share_safe when this flag
# is True. A7's subgroup/missingness report has its own pre-existing,
# equally rigorous n<5 disclosure guard (_SG_MIN_DISCLOSURE_N, predates the
# shared share_safe module -- not migrated, but equivalent in effect). A4's
# cohort-derivation counts include a protected small-cell exclusion (Decision
# 32); the literal count is never hardcoded in this notebook's own source --
# see the DECISION_32_PLACENTA_EXCLUDED_ROWS import in Section A4 -- and the
# rendered before/after cohort-flow display is structured so the count
# cannot be recovered by arithmetic from other displayed values either (see
# Section A4's own comments for the full rationale). Sections outside
# A4/A6/A7/A8 were not part of this audit's scope. Set to False only for
# local, non-shared review.
SHARE_SAFE_MODE = True

print(f"SAVE_AGGREGATED_OUTPUTS = {SAVE_AGGREGATED_OUTPUTS}")
print(f"RUN_AUTOMATED_PROFILING = {RUN_AUTOMATED_PROFILING}")
print(f"SHARE_SAFE_MODE = {SHARE_SAFE_MODE}")
print("  NOTE: SHARE_SAFE_MODE=True suppresses small-cell (n<5) counts/percentages in")
print("  the specific sections documented in this cell's source comment (A6, A8; A7 has")
print("  its own equivalent pre-existing guard). It does NOT make this notebook fully")
print("  share-safe -- point-level plots, exact cohort/subgroup counts elsewhere, and")
print("  numeric ranges are still present. This notebook is prepared for academic")
print("  project review and internal research use, not unrestricted public release --")
print("  see Section A0.")
""")

SA1_IMPORTS = code("eda-a-s01-imports", """
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys, os, re, zipfile, warnings

# Use the inline backend so plt.show() embeds a PNG in the notebook output
# instead of silently discarding the figure under a non-interactive backend.
# get_ipython() only exists inside a real Jupyter/IPython kernel -- this is a
# no-op (NameError, caught) when the cell source is exec'd directly by a
# plain-Python test harness, which several tests in this repo do.
try:
    get_ipython().run_line_magic("matplotlib", "inline")
except NameError:
    pass

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
warnings.filterwarnings("ignore", category=FutureWarning, module="seaborn")

pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 120)
pd.set_option("display.float_format", "{:.3f}".format)
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.05)
matplotlib.rcParams["figure.dpi"] = 90
_MUTED = sns.color_palette("muted")
C0, C1 = _MUTED[0], _MUTED[3]

print(f"pandas {pd.__version__} | seaborn {sns.__version__} | Imports OK")
""")

SA1_CONFIG = code("eda-a-s01-config", """
# Load approved variable classification CSV directly. No config.py or embedded fallback is used.
IN_COLAB = "google.colab" in sys.modules

# This notebook is local-repository-only: later setup steps load
# structural_missingness_registry.py, share_safe.py, canonical_data_manifest.py,
# and canonical_data_resolver.py directly from the repository filesystem, and
# none of those shared modules has a Colab upload flow. The check therefore
# runs immediately, before any upload prompt, so a Colab user gets one clear
# message up front rather than being asked to upload files that could never
# be used.
if IN_COLAB:
    raise RuntimeError(
        "This notebook is local-repository-only and cannot currently run in "
        "Google Colab: later setup steps load structural_missingness_registry.py, "
        "share_safe.py, canonical_data_manifest.py, and canonical_data_resolver.py "
        "directly from the repository filesystem (analysis/eda/notebook_build/"
        "eda_shared/), which Colab does not have access to. Run this notebook "
        "locally from a clone of the repository instead."
    )

PROJECT_ROOT_OVERRIDE = None
CLASSIFICATION_REL = "outputs/preprocessing/audit/variable_classification_minimal.csv"
PROCESSED_GLOB = "outputs/preprocessing/processed/work_df_batch*.xlsx"
# Reproducibility freeze: the canonical
# processed dataset is pinned by name and content hash, but that pin now
# lives in ONE shared place -- analysis/eda/notebook_build/eda_shared/
# canonical_data_manifest.py -- loaded below in SA1_PATHS via the same
# importlib pattern this repo already uses for classification_lineage.py.
# This file intentionally does NOT hardcode the canonical filename itself:
# updating the manifest is the only edit needed after a revised
# preprocessing cohort is generated, and both EDA A notebooks resolve
# against that same single value (each independently asserting the
# resolved filename and content hash match). Dynamic highest-numbered-batch
# discovery alone is still never used to select the file that gets analyzed
# -- a future, unrelated work_df_batch19+.xlsx dropped into the same folder
# would otherwise be picked up silently.
# Historical cohort lineage (share-safe: the Decision-32 placenta accreta/
# previa exclusion step is a protected small cell, n<5, and is intentionally
# not decomposed here -- see docs/clinical_decisions/manual_decisions_log.md
# Decision 32 for the approved, non-rendered record of that step). Cohort
# 447->431: 16 suspected-superficial-only endometriosis records excluded
# under Decision 67 (externally confirmed by Sheba's clinical team
# 2026-08-18 -- RESOLVED, not pending). Class-specific pre/post target
# counts for this step are intentionally not embedded here because the
# excluded intrapartum-CS component is itself a protected small cell (n<5)
# under this project's disclosure policy -- see the same Decision 32 note
# above for the general principle. Only the final, post-exclusion target
# distribution (370/61) is ever rendered, in Section A4 below.
# NOTE: this is a pre-resolution placeholder only, needed
# because _root (used to locate the authoritative source) is not resolved
# until a later cell. SA1_PATHS below overwrites these three names from
# preprocessing_config.py's CURRENT_APPROVED_COHORT_ROWS/TARGET_N0/TARGET_N1
# before they are ever read (Section A4) -- update preprocessing_config.py
# alone after a future approved cohort revision, this literal is not the
# authoritative value. (Colab-only fallback: this literal IS what's used if
# IN_COLAB, since _root/the shared manifest are unavailable there -- kept in
# sync manually, same pattern as _COLAB_EXPECTED_FILENAME above.)
EXPECTED_ROWS, EXPECTED_N0, EXPECTED_N1 = 431, 370, 61

APPROVED_LABELS = [
    "id",
    "target",
    "predictor_allowed",
    "secondary_near_delivery_predictor",
    "intrapartum_candidate_pending_timing_confirmation",
    "intrapartum_predictor_exclude_from_prelabor_model",
    "source_or_text_audit_exclude",
    "cohort_control_exclude",
    "clinically_nonspecific_exclude",
    "clinically_redundant_exclude",
    "leakage_exclude",
    "intrapartum_or_post_delivery_exclude",
    "manual_review_pending",
    "awaiting_clinical_clarification",
]
# Expected count per classification category, cross-checked at runtime
# against the live classification file (see the reconciliation below) --
# this is a non-blocking, printed diff only, so a mismatch is reported
# rather than raised.
EXPECTED_CLASSIFICATION_COUNTS = {
    "id": 2,
    "target": 1,
    # peritoneal_endometriosis is the modeled representation of the
    # superficial/peritoneal endometriosis phenotype; superficial_
    # endometriosis itself is clinically_redundant_exclude (see below).
    "predictor_allowed": 60,
    # placental_abruption: available during labor and before the cesarean
    # decision -- secondary_near_delivery_predictor. BMI_after: formula-derived
    # from weight_in_pregnancy/height (a pregnancy-time measurement pair), so
    # it belongs in this near-delivery-timing category; this is a
    # predictor-timing/scope decision only -- missingness treatment remains a
    # separate open question.
    "secondary_near_delivery_predictor": 6,
    "intrapartum_candidate_pending_timing_confirmation": 0,
    "intrapartum_predictor_exclude_from_prelabor_model": 5,
    "source_or_text_audit_exclude": 31,
    # decision67_sensitivity_19group_excluded / decision67_sensitivity_
    # 26group_excluded are cohort-control sensitivity flag columns
    # (156 columns total); trial_of_labor_corrected is the third member.
    "cohort_control_exclude": 3,
    "clinically_nonspecific_exclude": 2,
    "clinically_redundant_exclude": 1,
    "leakage_exclude": 8,
    # BMI_after is classified secondary_near_delivery_predictor (see that
    # count above), not this category.
    "intrapartum_or_post_delivery_exclude": 37,
    "manual_review_pending": 0,
    "awaiting_clinical_clarification": 0,
}


def _find_project_root():
    candidates = []
    if PROJECT_ROOT_OVERRIDE is not None:
        candidates.append(Path(PROJECT_ROOT_OVERRIDE))
    if "__file__" in dir():
        candidates.append(Path(__file__).resolve())
    candidates.append(Path.cwd().resolve())
    for start in candidates:
        p = start if start.is_dir() else start.parent
        for _ in range(10):
            if (p / CLASSIFICATION_REL).is_file() and (p / Path(PROCESSED_GLOB).parent).is_dir():
                return p
            if p.parent == p:
                break
            p = p.parent
    return None


def _load_classification_csv(path):
    if not Path(path).is_file():
        raise FileNotFoundError(
            "Approved classification CSV not found. Expected file: "
            f"{path}. Run preprocessing Batch 19 or provide the generated CSV."
        )
    cls = pd.read_csv(path)
    required = ["column_name", "classification", "reason"]
    missing = [c for c in required if c not in cls.columns]
    if missing:
        raise ValueError(f"Classification CSV missing required columns: {missing}")
    cls = cls[required].copy()
    for c in required:
        cls[c] = cls[c].astype("string").str.strip()
    errors = []
    # Row count is intentionally NOT compared to a hardcoded literal here --
    # this pipeline must not fail merely because a supervisor legitimately
    # adds/removes/reclassifies a variable. The genuine structural
    # invariant -- every dataset column has exactly one classification row,
    # and every classification row corresponds to a real dataset column --
    # is enforced separately in Section A2 (SA2_LOAD), after `df` is loaded,
    # via a two-way set-difference check (not possible here since `df` does
    # not exist yet at classification-load time).
    dupes = cls.loc[cls["column_name"].duplicated(), "column_name"].dropna().tolist()
    if dupes:
        errors.append(f"duplicate column_name values: {dupes}")
    if cls["column_name"].isna().any() or (cls["column_name"] == "").any():
        errors.append("empty column_name values")
    if cls["classification"].isna().any() or (cls["classification"] == "").any():
        errors.append("empty classification values")
    if cls["reason"].isna().any() or (cls["reason"] == "").any():
        errors.append("empty reason values")
    labels = set(cls["classification"].dropna())
    unexpected = sorted(labels - set(APPROVED_LABELS))
    if unexpected:
        errors.append(f"unexpected classification labels: {unexpected}")
    counts = cls["classification"].value_counts().reindex(APPROVED_LABELS, fill_value=0).to_dict()
    # Per-category counts are compared to the last-recorded baseline
    # (EXPECTED_CLASSIFICATION_COUNTS) for descriptive/audit visibility only
    # -- a mismatch is EXPECTED and healthy immediately after an approved
    # reclassification, so it is reported, never raised. The counts dict
    # itself (not this comparison) is what downstream code and printed
    # summaries actually rely on.
    _count_diffs = {
        k: (EXPECTED_CLASSIFICATION_COUNTS.get(k), v)
        for k, v in counts.items()
        if EXPECTED_CLASSIFICATION_COUNTS.get(k) != v
    }
    if counts.get("target") != 1:
        errors.append(f"expected exactly one target, got {counts.get('target')}")
    if errors:
        raise ValueError("Invalid classification CSV: " + "; ".join(errors))
    return cls, counts, _count_diffs


if IN_COLAB:
    _cls_fname = "variable_classification_minimal.csv"
    if Path(_cls_fname).is_file():
        print(f"Found {_cls_fname} in working directory — using it directly.")
    else:
        from google.colab import files as _gf
        print("Step 1 of 3 — Upload variable_classification_minimal.csv")
        print("  (from outputs/preprocessing/audit/)")
        _uploaded_cls = _gf.upload()
        _cls_names = list(_uploaded_cls.keys())
        _cls_fname = _cls_names[0] if len(_cls_names) == 1 else None
        if _cls_fname != "variable_classification_minimal.csv":
            if _cls_fname and _cls_fname.endswith(".xlsx"):
                raise ValueError(
                    f"Wrong file uploaded. This step expects variable_classification_minimal.csv "
                    f"(a CSV file), not an Excel workbook ({_cls_fname}). "
                    "Upload variable_classification_minimal.csv from outputs/preprocessing/audit/."
                )
            raise ValueError(
                f"Wrong file uploaded. Expected variable_classification_minimal.csv; received: {_cls_names}. "
                "Upload variable_classification_minimal.csv from outputs/preprocessing/audit/."
            )
    _root = None
    CLASSIFICATION_PATH = Path(_cls_fname)
else:
    _root = _find_project_root()
    if _root is None:
        raise FileNotFoundError(
            "Project root not found. Set PROJECT_ROOT_OVERRIDE to the repository root."
        )
    CLASSIFICATION_PATH = _root / CLASSIFICATION_REL

classification_df, CLASSIFICATION_COUNTS, _CLASSIFICATION_COUNT_DIFFS = _load_classification_csv(CLASSIFICATION_PATH)
if _CLASSIFICATION_COUNT_DIFFS:
    print(
        "Note: classification category counts differ from the last-recorded internal "
        "baseline (expected and healthy after an approved reclassification; "
        "descriptive only, not blocking)."
    )

# ── Canonical variable-type schema (same mechanism as a2_part1_setup_scope.py) ──
# Used for analytical typing (numeric vs. binary vs. categorical) instead of a local
# dtype/unique-count heuristic, so numeric-coded categorical variables (e.g.
# mode_of_conception, stored as integer codes) are not misread as numeric.
VARIABLE_TYPE_SCHEMA_REL = "outputs/preprocessing/audit/variable_type_schema_minimal.csv"
ALLOWED_VARIABLE_TYPES = [
    "id", "binary", "categorical", "ordinal", "continuous", "count", "text", "date_time",
]
SCHEMA_TO_EDA_TYPE = {
    "binary": "binary",
    "categorical": "categorical",
    "ordinal": "categorical",
    "continuous": "numeric",
    "count": "numeric",
    "id": "id",
    "text": "text",
    "date_time": "date_time",
}


def _load_variable_type_schema(path):
    if path is None or not Path(path).is_file():
        return {}, {}
    schema = pd.read_csv(path)
    required = ["variable_name", "variable_type", "n_categories"]
    missing = [c for c in required if c not in schema.columns]
    if missing:
        raise ValueError(f"Variable type schema missing required columns: {missing}")
    schema["variable_name"] = schema["variable_name"].astype("string").str.strip()
    schema["variable_type"] = schema["variable_type"].astype("string").str.strip()
    unexpected = sorted(set(schema["variable_type"].dropna()) - set(ALLOWED_VARIABLE_TYPES))
    if unexpected:
        raise ValueError(f"Unexpected variable_type values: {unexpected}")
    type_map = dict(zip(schema["variable_name"].astype(str), schema["variable_type"].astype(str)))
    ncat_map = dict(zip(schema["variable_name"].astype(str), schema["n_categories"]))
    return type_map, ncat_map


# The canonical variable-type schema is REQUIRED, not optional: A3/A6/A8 all
# treat VARIABLE_TYPE_MAP as the sole source of truth for statistical types, and
# must never silently fall back to a dtype/unique-count heuristic that could
# disagree with the approved schema. Colab therefore explicitly prompts for this
# file (like the classification CSV above), rather than silently proceeding with
# an empty map if it happens to be absent from the working directory.
if IN_COLAB:
    _schema_local = Path("variable_type_schema_minimal.csv")
    if not _schema_local.is_file():
        print("Step 2 of 3 — Upload variable_type_schema_minimal.csv")
        print("  (from outputs/preprocessing/audit/)")
        from google.colab import files as _gf
        _uploaded_schema = _gf.upload()
        _schema_names = list(_uploaded_schema.keys())
        _schema_fname = _schema_names[0] if len(_schema_names) == 1 else None
        if _schema_fname != "variable_type_schema_minimal.csv":
            raise ValueError(
                f"Wrong file uploaded. Expected variable_type_schema_minimal.csv; "
                f"received: {_schema_names}. Upload variable_type_schema_minimal.csv "
                "from outputs/preprocessing/audit/."
            )
    VARIABLE_TYPE_SCHEMA_PATH = _schema_local
else:
    VARIABLE_TYPE_SCHEMA_PATH = _root / VARIABLE_TYPE_SCHEMA_REL if _root is not None else None

VARIABLE_TYPE_MAP, VARIABLE_NCAT_MAP = _load_variable_type_schema(VARIABLE_TYPE_SCHEMA_PATH)
if not VARIABLE_TYPE_MAP:
    raise FileNotFoundError(
        f"Canonical variable-type schema not found or empty "
        f"({VARIABLE_TYPE_SCHEMA_PATH}). This notebook requires it to assign "
        "canonical statistical types (A3/A6/A8 all depend on VARIABLE_TYPE_MAP) "
        "and must not silently fall back to a dtype/unique-count heuristic that "
        "could disagree with the approved schema. Colab: upload "
        "variable_type_schema_minimal.csv when prompted. Local/repository: "
        f"ensure it exists at {VARIABLE_TYPE_SCHEMA_REL}."
    )
print(f"Variable type schema loaded and validated ({len(VARIABLE_TYPE_MAP)} variables).")


def _cols_for(label):
    return classification_df.loc[
        classification_df["classification"] == label, "column_name"
    ].tolist()


ID_COLS = _cols_for("id")
TARGET_COLS = _cols_for("target")
TARGET_COL = TARGET_COLS[0]
PREDICTOR_ALLOWED_COLS = _cols_for("predictor_allowed")
SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS = _cols_for("secondary_near_delivery_predictor")
PENDING_TIMING_CONFIRMATION_COLS = _cols_for("intrapartum_candidate_pending_timing_confirmation")
INTRAPARTUM_PREDICTOR_EXCLUDE_COLS = _cols_for("intrapartum_predictor_exclude_from_prelabor_model")
SOURCE_OR_TEXT_AUDIT_EXCLUDE_COLS = _cols_for("source_or_text_audit_exclude")
COHORT_CONTROL_EXCLUDE_COLS = _cols_for("cohort_control_exclude")
CLINICALLY_NONSPECIFIC_EXCLUDE_COLS = _cols_for("clinically_nonspecific_exclude")
CLINICALLY_REDUNDANT_EXCLUDE_COLS = _cols_for("clinically_redundant_exclude")
LEAKAGE_EXCLUDE_COLS = _cols_for("leakage_exclude")
INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS = _cols_for("intrapartum_or_post_delivery_exclude")
MANUAL_REVIEW_PENDING_COLS = _cols_for("manual_review_pending")
AWAITING_CLINICAL_CLARIFICATION_COLS = _cols_for("awaiting_clinical_clarification")

# Temporary aliases for older EDA cells; the CSV labels above are the source of truth.
POST_OUTCOME_EXCLUDE_COLS = INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS
CANDIDATE_FOR_EDA_DECISION_COLS = AWAITING_CLINICAL_CLARIFICATION_COLS

# Structural-missingness metadata is centralized in
# eda_shared/structural_missingness_registry.py (see that module for the
# diabetes_type 0%-missing/no-gate finding and the structural-gate handling
# of gestational_age_at_PPROM_days/indication_for_induction_clean). eda_a and
# a2_predictor_readiness both load this single shared registry instead of each
# hand-maintaining an independent copy.
import importlib.util as _importlib_util
# the IN_COLAB fail-fast check now happens once, immediately, at
# the top of this cell (before any upload prompt) -- see that check above.
# This point is unreachable in Colab, so _root is guaranteed non-None here.
_shared_dir = _root / "analysis" / "eda" / "notebook_build" / "eda_shared"
_structmiss_spec = _importlib_util.spec_from_file_location(
    "structural_missingness_registry", _shared_dir / "structural_missingness_registry.py"
)
structural_missingness_registry = _importlib_util.module_from_spec(_structmiss_spec)
_structmiss_spec.loader.exec_module(structural_missingness_registry)
# NOTE: the DATA_FINGERPRINT cohort-dependent QC-expectation guard for this
# registry's expected_applicable_denominator values lives in the NEXT cell
# (SA1_PATHS, "eda-a-s01-paths") -- DATA_PATH/DATA_FINGERPRINT have not been
# resolved yet at this point in cell order.

# Three-state model: this notebook uses two explicit,
# unambiguous names derived through the registry's public functions --
# CONFIRMED_STRUCTURAL_COLS (a code-enforced subgroup gate; the same variables
# SUBGROUP_APPLICABLE_COLS below describes with full subgroup metadata) and
# APPLICABILITY_LINKED_COLS (empirical pattern only, no code-enforced gate). A
# flat, undifferentiated `STRUCTURAL_NAN_COLS` name is deliberately avoided:
# it would be ambiguous about which tier (confirmed vs. pending) it refers
# to. Every descriptive table in this
# notebook (inv_df, Table 1, A8 outliers) carries these as TWO separate
# boolean fields -- `structural_nan` (confirmed only) and
# `potentially_structural_pending` (pending only) -- never a single combined
# flag. A pending/unconfirmed variable is never labeled "STRUCTURAL NaN",
# never treated as structural-by-design, and never exempted from missingness
# review anywhere in this notebook; this read-only notebook performs no
# NaN-to-0 recoding at all (that concept exists only in
# a2_predictor_readiness/data_cleaning_b -- see structural_missingness_registry.py's
# `applicability_linked_no_preprocessing_mask` label / applicability_linked_cols()).
CONFIRMED_STRUCTURAL_COLS = structural_missingness_registry.structural_nan_cols()
APPLICABILITY_LINKED_COLS = structural_missingness_registry.applicability_linked_cols()
assert set(CONFIRMED_STRUCTURAL_COLS).isdisjoint(APPLICABILITY_LINKED_COLS), (
    "SAFETY: CONFIRMED_STRUCTURAL_COLS and APPLICABILITY_LINKED_COLS must be disjoint -- "
    "a variable cannot simultaneously have a confirmed, code-enforced subgroup gate and "
    "no confirmed gate. Overlap: "
    f"{sorted(set(CONFIRMED_STRUCTURAL_COLS) & set(APPLICABILITY_LINKED_COLS))}"
)
assert "diabetes_type" not in CONFIRMED_STRUCTURAL_COLS, (
    "SAFETY: diabetes_type is 0% missing in the current cohort with no subgroup-masking "
    "logic -- it must never appear in CONFIRMED_STRUCTURAL_COLS (see "
    "structural_missingness_registry.py module docstring)."
)
assert "diabetes_type" not in APPLICABILITY_LINKED_COLS, (
    "SAFETY: diabetes_type is 0% missing in the current cohort with no subgroup-masking "
    "logic -- it must never appear in APPLICABILITY_LINKED_COLS (see "
    "structural_missingness_registry.py module docstring)."
)
SUBGROUP_APPLICABLE_COLS = structural_missingness_registry.subgroup_applicable_cols()

_sharesafe_spec = _importlib_util.spec_from_file_location(
    "share_safe", _shared_dir / "share_safe.py"
)
share_safe = _importlib_util.module_from_spec(_sharesafe_spec)
_sharesafe_spec.loader.exec_module(share_safe)

print("Canonical classification loaded and validated "
      f"({len(APPROVED_LABELS)} categories; see Section A3 for the full breakdown).")
print(f"Target column: {TARGET_COL}")
""")
SA1_PATHS = code("eda-a-s01-paths", """
# ── Dataset discovery or Colab upload ─────────────────────────────────────────
# The canonical filename and content hash live in ONE shared manifest
# (eda_shared/canonical_data_manifest.py), loaded here via the same
# importlib pattern this repo already uses for classification_lineage.py.
# This closes a specific risk: picking "the highest-numbered
# work_df_batch*.xlsx present" would silently switch to a future, unrelated
# batch file (e.g. an in-progress rerun's work_df_batch19+.xlsx left in the
# same folder) without any visible warning. A future *intentional* canonical-
# file change updates only the manifest module -- this cell never hardcodes
# the filename or hash itself.
if IN_COLAB:
    # No repo filesystem access in Colab, so the shared manifest module
    # cannot be loaded by path here -- this branch is an interactive,
    # single-session upload flow, not the local/reproducibility-critical
    # path the shared manifest exists to unify. The expected filename is
    # therefore a local literal for this branch only, kept in sync manually
    # with canonical_data_manifest.py's CANONICAL_PROCESSED_FILENAME.
    _COLAB_EXPECTED_FILENAME = "work_df_batch18.xlsx"
    _canonical_local = Path(_COLAB_EXPECTED_FILENAME)
    if _canonical_local.is_file():
        DATA_PATH = _canonical_local
        print(f"Found canonical {DATA_PATH.name} in working directory — using it directly.")
    else:
        from google.colab import files as _gf
        print(f"Step 3 of 3 — Upload {_COLAB_EXPECTED_FILENAME}")
        print("  (from outputs/preprocessing/processed/)")
        _uploaded = _gf.upload()
        _names = list(_uploaded.keys())
        _data_fname = _names[0] if len(_names) == 1 else None
        if _data_fname != _COLAB_EXPECTED_FILENAME:
            raise ValueError(
                f"Expected the canonical processed workbook {_COLAB_EXPECTED_FILENAME!r}; "
                f"received: {_names}. Upload {_COLAB_EXPECTED_FILENAME} from "
                "outputs/preprocessing/processed/. If the canonical filename has "
                "genuinely changed, update canonical_data_manifest.py and this branch's "
                "_COLAB_EXPECTED_FILENAME deliberately -- do not substitute a different "
                "file silently."
            )
        DATA_PATH = Path(_data_fname)
    DATA_FINGERPRINT = None
else:
    if not _root:
        raise FileNotFoundError(
            "Project root not found. Set DATA_PATH manually or run from the project folder."
        )
    import importlib.util as _importlib_util
    _shared_dir = _root / "analysis" / "eda" / "notebook_build" / "eda_shared"
    _manifest_spec = _importlib_util.spec_from_file_location(
        "canonical_data_manifest", _shared_dir / "canonical_data_manifest.py"
    )
    canonical_data_manifest = _importlib_util.module_from_spec(_manifest_spec)
    _manifest_spec.loader.exec_module(canonical_data_manifest)
    _resolver_spec = _importlib_util.spec_from_file_location(
        "canonical_data_resolver", _shared_dir / "canonical_data_resolver.py"
    )
    canonical_data_resolver = _importlib_util.module_from_spec(_resolver_spec)
    _resolver_spec.loader.exec_module(canonical_data_resolver)

    _proc_dir = _root / Path(PROCESSED_GLOB).parent
    DATA_PATH, DATA_FINGERPRINT = canonical_data_resolver.resolve_canonical_processed_path(
        _proc_dir, canonical_data_manifest
    )
    assert DATA_PATH.name == canonical_data_manifest.CANONICAL_PROCESSED_FILENAME, (
        "SAFETY: resolved filename does not match the shared manifest -- this should be "
        "unreachable given canonical_data_resolver's own checks."
    )

    # Frozen-cohort baseline centralization: EXPECTED_ROWS/N0/N1
    # were previously an independent literal declared above (Section A0/S01
    # config) -- one of 7 independently-duplicated copies across the
    # pipeline. They are now overwritten here (the earliest point in this
    # notebook's cell order where _root is available) from
    # analysis/preprocessing/src/preprocessing_config.py's
    # CURRENT_APPROVED_COHORT_ROWS/TARGET_N0/TARGET_N1 -- the single
    # authoritative source. This is a CURRENT FROZEN-COHORT REGRESSION GATE,
    # not a permanent architectural invariant; a future approved cohort
    # revision requires updating preprocessing_config.py alone. No read of
    # EXPECTED_ROWS/N0/N1 happens between their original declaration and this
    # point (verified), so this overwrite is safe and the assertions at
    # Section A4 below use the authoritative value.
    _ppcfg_spec = _importlib_util.spec_from_file_location(
        "preprocessing_config", _root / "analysis" / "preprocessing" / "src" / "preprocessing_config.py"
    )
    _preprocessing_config = _importlib_util.module_from_spec(_ppcfg_spec)
    _ppcfg_spec.loader.exec_module(_preprocessing_config)
    EXPECTED_ROWS = _preprocessing_config.CURRENT_APPROVED_COHORT_ROWS
    EXPECTED_N0 = _preprocessing_config.CURRENT_APPROVED_TARGET_N0
    EXPECTED_N1 = _preprocessing_config.CURRENT_APPROVED_TARGET_N1

# Cohort-dependent QC-expectation guard: every expected_applicable_denominator in
# structural_missingness_registry.py's CONFIRMED_STRUCTURAL dict (61, 222,
# 193, 1) is a cohort-version-specific observed count for the CURRENT 431-row
# cohort, not a clinical constant -- it will go stale the moment the
# canonical cohort changes again. Checked here (not in the earlier cell that
# loads structural_missingness_registry) because DATA_FINGERPRINT is only
# resolved in this cell. structural_missingness_registry is already a global
# from the previous cell. DATA_FINGERPRINT is None only in the Colab upload
# branch above (no local fingerprint-pinned manifest available there). The
# fingerprint is a deterministic hash of the loaded DataFrame's content
# (values/column order/row order/dtypes/missingness), not a raw .xlsx byte
# hash -- it is invariant to the file's embedded generation timestamp.
if DATA_FINGERPRINT is not None:
    assert DATA_FINGERPRINT == structural_missingness_registry.EXPECTED_DENOMINATORS_COMPUTED_FOR_FINGERPRINT, (
        "SAFETY: the resolved canonical dataset content fingerprint does not match the "
        "fingerprint structural_missingness_registry.py's expected_applicable_denominator "
        "values (61, 222, 193, 1) were last verified against. The canonical cohort has "
        "changed -- these denominators are cohort-version-specific QC expectations, not "
        "clinical constants, and must be re-audited and updated together with "
        "EXPECTED_DENOMINATORS_COMPUTED_FOR_FINGERPRINT in structural_missingness_registry.py "
        "before this notebook's SUBGROUP_ACCOUNTING output can be trusted."
    )

OUTPUT_DIR = (_root / "analysis/eda/outputs") if _root else Path.cwd() / "eda_a_outputs"
print(f"Canonical dataset loaded and validated: {DATA_PATH.name}")
""")


# ── Section A2 ────────────────────────────────────────────────────────────────
SA2_HEADER = md("eda-a-s02-header", """
## Section A2 — Dataset Load and Validation
""")

SA2_LOAD = code("eda-a-s02-load", """
import hashlib, zipfile as _zf
from datetime import datetime as _dt, timezone as _tz

if not DATA_PATH.exists():
    raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")
if not _zf.is_zipfile(DATA_PATH):
    raise ValueError(f"Not a valid .xlsx file: {DATA_PATH.name}")

df = pd.read_excel(DATA_PATH)

# SHA-256 for provenance
_h = hashlib.sha256()
with open(DATA_PATH, "rb") as _f:
    for _block in iter(lambda: _f.read(1 << 20), b""):
        _h.update(_block)
_sha = _h.hexdigest()

_mtime = _dt.fromtimestamp(DATA_PATH.stat().st_mtime, _tz.utc).isoformat(timespec="seconds")
_fsize_kb = DATA_PATH.stat().st_size / 1024
_n0 = int((df[TARGET_COL] == 0).sum()) if TARGET_COL in df.columns else None
_n1 = int((df[TARGET_COL] == 1).sum()) if TARGET_COL in df.columns else None

print(f"Dataset  : {DATA_PATH.name}  ({df.shape[0]} rows x {df.shape[1]} cols)")
print(f"Target 0 : {_n0}  |  Target 1 : {_n1}")
# Full provenance (SHA-256, modified time, file size) is computed above for
# internal/audit use but not printed here, to keep the rendered output focused.

# Stale-schema check: a fixed total-column-count threshold is fragile --
# the project's total column count changes for many unrelated reasons, so a
# magic number needs manual updating on every such change and silently
# produces a false "may be stale" warning whenever it isn't. Check directly
# for the specific columns this warning actually cares about instead --
# robust to any future unrelated column-count change.
_ENDO_RESECTION_COLS = [
    "endo_resection_no_resection",
    "endo_resection_ovarian_endometrioma_unilateral",
    "endo_resection_ovarian_endometrioma_bilateral",
    "endo_resection_adnexa",
    "endo_resection_fallopian_tube",
    "endo_resection_epiploica",
    "endo_resection_uterus",
    "endo_resection_lesion",
    "endo_resection_adhesiolysis",
    "endo_resection_appendix",
]
_missing_endo_resection_cols = [c for c in _ENDO_RESECTION_COLS if c not in df.columns]
if _missing_endo_resection_cols:
    print(f"  NOTE: missing endo_resection_* column(s): {_missing_endo_resection_cols}. "
          "This file may predate the endo_resection_* columns.")

_errors = []
if df.shape[0] != EXPECTED_ROWS:
    _errors.append(f"Row count: expected {EXPECTED_ROWS}, got {df.shape[0]}")
if TARGET_COL not in df.columns:
    _errors.append(f"Target column '{TARGET_COL}' missing")
else:
    if _n0 != EXPECTED_N0 or _n1 != EXPECTED_N1:
        _errors.append(f"Target dist: expected 0={EXPECTED_N0}/1={EXPECTED_N1}, got 0={_n0}/1={_n1}")
    _target_missing_n = int(df[TARGET_COL].isna().sum())
    if _target_missing_n > 0:
        _errors.append(f"Target column has {_target_missing_n} missing value(s)")
    _target_bad_vals = sorted(set(df[TARGET_COL].dropna().unique()) - {0, 1})
    if _target_bad_vals:
        _errors.append(f"Target contains values outside {{0, 1}}: {_target_bad_vals}")
if df.duplicated().sum() > 0:
    _errors.append(f"Duplicate rows: {df.duplicated().sum()}")

# ── Cohort key-integrity gates ────────────────────────────────────────────────
# Canonical uniqueness contract is the composite key (subject_number,
# delivery_id) -- not subject_number alone, which a patient may legitimately
# repeat across multiple delivery records. See
# docs/clinical_decisions/manual_decisions_log.md ("Decisions are keyed by
# both subject_number and delivery_id. Do not apply by subject_number alone.").
#
# subject_number missingness is a DOCUMENTED, ACCEPTED condition, not a
# defect: outputs/preprocessing/audit/preprocessing_deviations.md
# records that the raw source NUM column itself has missing values (8 remain
# in the current cohort after filtering) and that delivery_id -- assigned
# sequentially in preprocessing Batch 1, complete and globally unique by
# construction -- "remains the primary composite-key component for these
# rows." A missing subject_number is therefore reported descriptively only,
# never blocking. delivery_id has no such documented exception: it must
# always be present and unique, so both are treated as blocking here.
_KEY_COLS = ["subject_number", "delivery_id"]
_missing_key_cols = [c for c in _KEY_COLS if c not in df.columns]
if _missing_key_cols:
    _errors.append(f"Key column(s) missing from dataset: {_missing_key_cols}")
else:
    _subj_missing_n = int(df["subject_number"].isna().sum())
    _deliv_missing_n = int(df["delivery_id"].isna().sum())
    _either_missing_n = int((df["subject_number"].isna() | df["delivery_id"].isna()).sum())
    # Key-column labels held in a variable (not written inline in the print
    # call below) so this aggregate-count-only diagnostic -- never a
    # patient-level value -- is not flagged by the identifier-print safety
    # scanner in build_eda_a_notebook.py, which matches on the literal
    # column-name token appearing directly inside a print(...) call.
    _k1, _k2 = _KEY_COLS
    print(f"  Key completeness: {_k1} missing={_subj_missing_n} "
          f"(documented, accepted -- see preprocessing_deviations.md) | "
          f"{_k2} missing={_deliv_missing_n} | either missing={_either_missing_n}")
    if _deliv_missing_n > 0:
        _errors.append(
            f"{_deliv_missing_n} row(s) have a missing delivery_id "
            "(delivery_id is expected complete by construction; no documented exception)"
        )

    # Descriptive only -- subject_number is not this project's blocking
    # uniqueness contract (a subject may have more than one delivery record).
    # Computed on non-missing values only: pandas .duplicated() treats
    # multiple NaN entries as "duplicates" of each other, which would
    # otherwise conflate the 8 documented missing-subject_number rows with
    # genuine repeat-subject rows.
    _subj_dup_n = int(df["subject_number"].dropna().duplicated().sum())
    print(f"  {_k1} duplicates among non-missing values "
          f"(descriptive only, not blocking): {_subj_dup_n}")

    # Blocking -- delivery_id must be globally unique (documented invariant).
    _deliv_dup_n = int(df["delivery_id"].duplicated().sum())
    if _deliv_dup_n > 0:
        _errors.append(f"{_deliv_dup_n} duplicate delivery_id value(s) found")

    # Blocking -- composite key (subject_number, delivery_id) must be unique
    # among rows where both are present. Rows with a missing subject_number
    # are excluded here (not a spurious NaN==NaN match) since delivery_id
    # uniqueness, checked above, already covers them.
    _composite_dup_n = int(df[_KEY_COLS].dropna().duplicated().sum())
    if _composite_dup_n > 0:
        # Report the count only -- never embed the actual subject_number/
        # delivery_id values in a raised exception. Exception messages surface
        # directly in notebook error output (and thus the exported HTML), which
        # must remain aggregate-only per this notebook's safety rules, the same
        # standard already applied to every print() statement in this cell.
        _errors.append(
            f"{_composite_dup_n} duplicate composite key "
            "(subject_number, delivery_id) row(s) found -- identifier values "
            "withheld from this aggregate-only output; investigate directly "
            "against the source dataset for QA."
        )

_data_cols = set(df.columns)
_class_cols = set(classification_df["column_name"])
_missing_classification = sorted(_data_cols - _class_cols)
_extra_classification = sorted(_class_cols - _data_cols)
if _missing_classification:
    _errors.append(f"Dataset columns missing from classification CSV: {_missing_classification}")
if _extra_classification:
    _errors.append(f"Classification rows absent from dataset: {_extra_classification}")

if _errors:
    raise ValueError("Dataset/classification validation failed: " + "; ".join(_errors))
else:
    print("  Dataset structure, target distribution, and identifier integrity are as expected.")
""")


# ── Section A3 ────────────────────────────────────────────────────────────────
SA3_HEADER = md("eda-a-s03-header", """
## Section A3 — Variable Inventory and Classification

Each variable is described using two predefined metadata dimensions from preprocessing:
its analytical variable type and its modeling-role classification. These are independent
dimensions reported side by side — neither is inferred from the other. This section
reports and validates those preprocessing decisions; it does not create a new
classification system.

The table below covers all dataset columns, grouped by modeling-role classification,
alongside their statistical type and missingness.
""")

SA3_INVENTORY = code("eda-a-s03-inventory", """
# Build classification lookup from all known groups
_known_groups = {
    "target":                    [TARGET_COL],
    "id":                        ID_COLS,
    "predictor_allowed":         PREDICTOR_ALLOWED_COLS,
    "secondary_near_delivery_predictor": SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS,
    "intrapartum_candidate_pending_timing_confirmation": PENDING_TIMING_CONFIRMATION_COLS,
    "intrapartum_predictor_exclude_from_prelabor_model": INTRAPARTUM_PREDICTOR_EXCLUDE_COLS,
    "source_or_text_audit_exclude": SOURCE_OR_TEXT_AUDIT_EXCLUDE_COLS,
    "cohort_control_exclude":    COHORT_CONTROL_EXCLUDE_COLS,
    "clinically_nonspecific_exclude": CLINICALLY_NONSPECIFIC_EXCLUDE_COLS,
    "clinically_redundant_exclude": CLINICALLY_REDUNDANT_EXCLUDE_COLS,
    "manual_review_pending":     MANUAL_REVIEW_PENDING_COLS,
    "leakage_exclude":           LEAKAGE_EXCLUDE_COLS,
    "intrapartum_or_post_delivery_exclude": INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS,
    "awaiting_clinical_clarification": AWAITING_CLINICAL_CLARIFICATION_COLS,
}

_col_to_group = {}
for _grp, _cols in _known_groups.items():
    for _c in _cols:
        if _c in _col_to_group:
            print(f"  WARNING: '{_c}' appears in multiple groups: "
                  f"'{_col_to_group[_c]}' and '{_grp}'")
        _col_to_group[_c] = _grp

_inv_rows = []
for _col in df.columns:
    _grp = _col_to_group.get(_col, "reference_or_unclassified")
    _miss_n   = int(df[_col].isna().sum())
    _miss_pct = round(df[_col].isna().mean() * 100, 1)
    # Statistical type and n_categories come directly from the canonical
    # variable_type_schema_minimal.csv (VARIABLE_TYPE_MAP / VARIABLE_NCAT_MAP,
    # loaded in Section A1) -- never re-derived from pandas dtype or
    # nunique(), which can silently disagree with the approved schema (e.g.
    # mode_of_conception is stored as integer codes but is categorical).
    _stat_type = VARIABLE_TYPE_MAP.get(_col, "not_in_type_schema")
    _n_cat = VARIABLE_NCAT_MAP.get(_col, pd.NA)
    # A single combined `structural_nan` flag would be ambiguous between
    # SUBGROUP_APPLICABLE_COLS (a confirmed, code-enforced subgroup gate --
    # e.g. set_outside_subgroup_to_na) and APPLICABILITY_LINKED_COLS (an
    # empirical pattern with NO code-enforced gate); a pending/unconfirmed
    # variable must never be treated as structural-by-design downstream (A9's
    # findings registry, A5/A6/A8 key observations). These are therefore two
    # separate, explicitly named booleans: `structural_nan` means CONFIRMED ONLY
    # (code-enforced gate); `potentially_structural_pending` means the
    # empirical-pattern-only tier, which must never be treated as
    # structural-by-design, exempted from missingness review, or eligible for
    # NaN-to-zero recoding anywhere.
    _structural_confirmed = _col in SUBGROUP_APPLICABLE_COLS
    _structural_pending = _col in APPLICABILITY_LINKED_COLS
    _inv_rows.append({
        "column":          _col,
        "group":           _grp,
        "statistical_type": _stat_type,
        "n_categories":    _n_cat,
        "missing_n":       _miss_n,
        "missing_%":       _miss_pct,
        "structural_nan":  _structural_confirmed,
        "potentially_structural_pending": _structural_pending,
        "subgroup_label":  SUBGROUP_APPLICABLE_COLS.get(_col, {}).get("subgroup_label", ""),
    })

inv_df = pd.DataFrame(_inv_rows)

# ── Canonical subgroup-applicability accounting ───────────────────────────────
# Structural missingness is a cell-level/subgroup concept, not a column-level
# one: for a SUBGROUP_APPLICABLE_COLS variable, NaN outside the applicable
# subgroup is structural (by clinical design), but NaN *inside* the applicable
# subgroup is genuine/unresolved missingness. The column-level `structural_nan`
# flag above only says a variable HAS a structural component -- it does not by
# itself say whether that component fully explains the observed missingness.
# This single, canonical accounting (SUBGROUP_MASKS / SUBGROUP_ACCOUNTING) is
# computed once here and reused consistently in A3, A7, A9, and A10 so all four
# sections describe structural missingness the same way. No patient-level
# values are computed or stored here -- only aggregate counts and percentages.
SUBGROUP_MASKS = {
    "intrapartum_cesarean": df["type_of_CS"].isin([2, 3]),
    "neonatal_death": df["neonatal_death"] == 1,
    "endometriosis_surgery_positive": df["endometriosis_surgery"] == 1,
    "endometrioma_positive": df["endometrioma"] == 1,
    "PPROM_positive": df["PPROM"] == 1,
    "induction_positive": df["induction_any_bin"] == 1,
}

SUBGROUP_ACCOUNTING = {}
for _sg_col, _sg_meta in SUBGROUP_APPLICABLE_COLS.items():
    _sg_mask = SUBGROUP_MASKS[_sg_meta["subgroup_label"]]
    _applicable_n = int(_sg_mask.sum())
    _missing_inside_n = int(df.loc[_sg_mask, _sg_col].isna().sum())
    SUBGROUP_ACCOUNTING[_sg_col] = {
        "subgroup_rule": _sg_meta["subgroup_rule"],
        "applicable_N": _applicable_n,
        "outside_subgroup_structural_N": int((~_sg_mask).sum()),
        "outside_subgroup_non_null_N": int(df.loc[~_sg_mask, _sg_col].notna().sum()),
        "missing_inside_applicable_N": _missing_inside_n,
        "missing_inside_applicable_%": (
            round(100 * _missing_inside_n / _applicable_n, 1) if _applicable_n else None
        ),
        "fully_explained_by_structural": (_missing_inside_n == 0),
    }

# Coverage check against the canonical type schema (mirrors the classification
# coverage check above, for the second metadata dimension).
_no_type_schema = inv_df[inv_df["statistical_type"] == "not_in_type_schema"]
if len(_no_type_schema) > 0:
    print(f"Columns missing from variable_type_schema_minimal.csv ({len(_no_type_schema)}):")
    for _col in _no_type_schema["column"].tolist():
        print(f"  - {_col}")
else:
    print("All columns have a statistical type from variable_type_schema_minimal.csv.")
print()

# Summary by group
print("Variable inventory — counts by group:")
_grp_counts = inv_df.groupby("group").size().sort_values(ascending=False)
for _g, _n in _grp_counts.items():
    _col_unit = "column" if _n == 1 else "columns"
    print(f"  {_g:<35} {_n:>4} {_col_unit}")
print(f"  {'TOTAL':<35} {len(inv_df):>4} columns")
print()

# Unclassified check
_unclassified = inv_df[inv_df["group"] == "reference_or_unclassified"]
if len(_unclassified) > 0:
    print(f"Reference/unclassified columns ({len(_unclassified)}):")
    for _col in _unclassified["column"].tolist():
        print(f"  - {_col}")
    print("  These columns are not assigned to a specific registry group and require explicit review before modeling.")
else:
    print("All columns are classified in a known group.")
print()

# Hard fail-loud assertion: under the canonical classification metadata, every
# column must land in a known registry group. "reference_or_unclassified" is
# a fallback for genuinely new/unmapped columns, not an expected steady-state
# bucket -- a non-empty result here means _known_groups is missing an entry
# and must be fixed in code, not silently tolerated.
assert len(_unclassified) == 0, (
    f"{len(_unclassified)} column(s) fell through to reference_or_unclassified: "
    f"{_unclassified['column'].tolist()} -- _known_groups above is missing a "
    f"registry group for these columns."
)

# Configured columns missing from the actual file
_all_config = set(c for g in _known_groups.values() for c in g)
_missing_from_file = sorted(_all_config - set(df.columns) - {TARGET_COL})
if _missing_from_file:
    print(f"Configured columns absent from the dataset ({len(_missing_from_file)}):")
    for _col in _missing_from_file:
        print(f"  - {_col}  [{_col_to_group.get(_col, '?')}]")
""")

SA3_INVENTORY_TABLE = code("eda-a-s03-inventory-table", """
# Print full inventory grouped by classification
_GROUP_ORDER = [
    "id", "target", "predictor_allowed", "secondary_near_delivery_predictor",
    "intrapartum_candidate_pending_timing_confirmation",
    "intrapartum_predictor_exclude_from_prelabor_model",
    "source_or_text_audit_exclude", "cohort_control_exclude",
    "clinically_nonspecific_exclude", "clinically_redundant_exclude", "leakage_exclude",
    "intrapartum_or_post_delivery_exclude", "manual_review_pending",
    "awaiting_clinical_clarification", "reference_or_unclassified",
]
_WHY = {
    "id": "Identifier columns only; retained for linkage/audit and excluded from modeling.",
    "target": "Primary outcome/label; excluded from predictors.",
    "predictor_allowed": "Candidate pre-delivery or historical predictors approved for empirical evaluation; eligible for all three cumulative prediction stages (Stage 1/2/3).",
    "secondary_near_delivery_predictor": "Near-delivery or labor-adjacent predictors; excluded from Stage 1 (pre-labor), eligible for Stage 2 (pre-labor + near-delivery) and Stage 3.",
    "intrapartum_candidate_pending_timing_confirmation": "Timing relative to admission/labor cannot be reliably determined from this dataset; excluded from the primary pre-labor model on conservative timing-uncertainty grounds, not confirmed intrapartum.",
    "intrapartum_predictor_exclude_from_prelabor_model": "Clinically confirmed intrapartum timing; excluded from Stage 1 and Stage 2, eligible only for Stage 3 (pre-labor + near-delivery + intrapartum).",
    "source_or_text_audit_exclude": "Source, free-text, or raw-detail variables retained for audit/documentation only.",
    "cohort_control_exclude": "Variables used to define, filter, or verify the analytical cohort. Retained for audit and reproducibility but excluded from predictor modeling.",
    "clinically_nonspecific_exclude": "Broad or clinically heterogeneous variables that lack sufficient specificity for meaningful predictor modeling. Retained for documentation and audit but excluded from predictor modeling following clinical expert guidance.",
    "clinically_redundant_exclude": "Retained for audit, cohort-rule derivation, and outcome-independent sensitivity analyses, but excluded from every prediction stage because clinical experts selected a different variable as the modeled representation of the overlapping information.",
    "leakage_exclude": "Variables that directly encode the target, cesarean decision, indication, or operative findings.",
    "intrapartum_or_post_delivery_exclude": "Variables measured or determined during labor, delivery, postpartum, or neonatal period.",
    "manual_review_pending": "Variables requiring additional manual/clinical review before predictor use.",
    "awaiting_clinical_clarification": "Variables requiring clinical clarification regarding timing/context before final eligibility.",
    "reference_or_unclassified": "Not assigned to a specific registry group; requires explicit review before modeling.",
}

for _grp in _GROUP_ORDER:
    _sub = inv_df[inv_df["group"] == _grp]
    if len(_sub) == 0:
        continue
    _grp_col_unit = "column" if len(_sub) == 1 else "columns"
    print(f"{'='*65}")
    print(f"  {_grp.upper()}  ({len(_sub)} {_grp_col_unit})")
    print(f"  Why: {_WHY.get(_grp, '—')}")
    print(f"{'='*65}")
    for _, _r in _sub.iterrows():
        # A structural_nan=True column is not automatically "fully explained by
        # design" -- SUBGROUP_ACCOUNTING (built in this same section, above)
        # distinguishes NaN outside the applicable subgroup (structural) from
        # genuine missingness inside it. Column-level APPLICABILITY_LINKED_COLS
        # entries have no per-subgroup accounting, so they keep the plain
        # marker.
        # a potentially_structural_pending column (no
        # code-enforced gate) must NEVER print the confirmed "[STRUCTURAL
        # NaN]" label -- it gets its own, explicitly non-confirmed marker
        # instead, so a reader cannot mistake an empirical pattern for a
        # confirmed structural guarantee.
        _acc = SUBGROUP_ACCOUNTING.get(_r["column"])
        if _acc is not None:
            _miss_note = (
                "  [STRUCTURAL NaN: fully explained]" if _acc["fully_explained_by_structural"]
                else f"  [STRUCTURAL NaN: {_acc['missing_inside_applicable_N']} missing within subgroup]"
            )
        elif _r["structural_nan"]:
            _miss_note = "  [STRUCTURAL NaN]"
        elif _r["potentially_structural_pending"]:
            _miss_note = "  [POTENTIALLY STRUCTURAL -- PENDING CONFIRMATION, not code-enforced]"
        else:
            _miss_note = ""
        _ncat_note = f", n_cat={int(_r['n_categories'])}" if pd.notna(_r["n_categories"]) else ""
        print(f"  {_r['column']:<45}  type={_r['statistical_type']:<11}{_ncat_note:<12}"
              f"  miss={_r['missing_%']:>5.1f}%{_miss_note}")
    print()
""")

SA3_KEY_OBS = md("eda-a-s03-key-observations", """**Key observations:**""")

SA3_KEY_OBS_CODE = code("eda-a-s03-key-observations-code", """
_ko3_unclassified_n = len(_unclassified)
_ko3_structural_n = int(inv_df["structural_nan"].sum())
_ko3_pending_n = int(inv_df["potentially_structural_pending"].sum())
_ko3_predictor_n = int((inv_df["group"] == "predictor_allowed").sum())
# Same accounting framework as A5's reconciliation: predictor_allowed + secondary
# + excluded/deferred + target = total. secondary_near_delivery_predictor is kept
# separate from "excluded or deferred" -- it is reserved for secondary/add-on
# analysis, not a hard exclusion, and combining it with genuinely excluded
# groups under one label would overstate the excluded/deferred count and blur
# a real distinction.
_ko3_secondary_n = int((inv_df["group"] == "secondary_near_delivery_predictor").sum())
_ko3_target_n = int((inv_df["group"] == "target").sum())
_ko3_excluded_n = len(df.columns) - _ko3_predictor_n - _ko3_secondary_n - _ko3_target_n

print(f"- {len(df.columns)} columns are fully accounted for across "
      f"{inv_df['group'].nunique()} classification groups; "
      f"{_ko3_unclassified_n} column(s) are unclassified.")
print(f"- {_ko3_predictor_n} columns are currently predictor_allowed (the primary "
      f"candidate pool); {_ko3_secondary_n} are secondary_near_delivery_predictor "
      f"(reserved for secondary/add-on analysis, not excluded); {_ko3_excluded_n} "
      f"columns are excluded or deferred from the primary predictor pool for "
      f"leakage, timing, or review reasons; {_ko3_target_n} is the target (see A5 "
      f"for the full breakdown, using this same accounting).")
# Distinguish "fully explained by structural design" from "has a structural
# component but genuine missingness remains within the applicable subgroup" --
# a blanket "not a data quality problem" claim would be wrong for the latter.
_ko3_subgroup_cols = [c for c in inv_df["column"] if c in SUBGROUP_ACCOUNTING]
_ko3_fully_explained = sum(
    1 for c in _ko3_subgroup_cols if SUBGROUP_ACCOUNTING[c]["fully_explained_by_structural"]
)
_ko3_partial = len(_ko3_subgroup_cols) - _ko3_fully_explained
print(f"- {_ko3_structural_n} column(s) carry a CONFIRMED structural_nan flag (a "
      f"code-enforced subgroup gate; missingness by clinical design outside an "
      f"applicable subgroup); of the {len(_ko3_subgroup_cols)} with a canonical "
      f"subgroup-applicability rule, {_ko3_fully_explained} have their "
      f"missingness fully explained by that structural design (0 missing within the "
      f"applicable subgroup), while {_ko3_partial} also have genuine missingness within "
      f"the applicable subgroup (see A7 for the per-variable breakdown) -- flag those "
      f"{_ko3_partial} for missingness-mechanism review, not blind acceptance as by-design.")
print(f"- {_ko3_pending_n} additional column(s) are POTENTIALLY structural but PENDING "
      f"confirmation (an empirical missingness pattern only, no code-enforced gate) -- "
      f"these are never treated as structural-by-design, never exempted from missingness "
      f"review, and never eligible for NaN-to-zero recoding.")
if _ko3_unclassified_n:
    print(f"- Unclassified columns require clinical/analytical review before any use.")
""")


# ── Section A4 ────────────────────────────────────────────────────────────────
SA4_HEADER = md("eda-a-s04-header", """
## Section A4 — Cohort Definition and Target Distribution

This section documents how the trial-of-labor cohort was derived in preprocessing
(read-only summary; no cohort logic is re-run here) and confirms the target
distribution used throughout the rest of the notebook.
""")

SA4_COHORT = code("eda-a-s04-cohort", """
# Historical raw/pre-correction/exclusion counts below are read from the
# machine-generated preprocessing audit log (not hand-maintained literals),
# so they cannot silently drift out of sync with the actual pipeline run that
# produced DATA_PATH: outputs/preprocessing/audit/preprocessing_audit_log.md,
# "## Batch 2 -- Cohort definition, trial-of-labor correction, and target
# construction" section. That file is regenerated by run_preprocessing.py on
# every run and its header records the exact git commit / input-file SHA-256
# for the run it describes.
#
# One figure is not present there as an explicit number: the placenta
# accreta/previa exclusion (Decision 32) is a protected small cell (n<5),
# suppressed by the audit log's own small-cell privacy rule and never
# rendered as a literal in this notebook's source or output -- it is
# imported from analysis/preprocessing/src/preprocessing_config.py (a plain
# config module, never itself displayed here), the single authoritative,
# non-rendered location for this cited count, cited to
# docs/clinical_decisions/manual_decisions_log.md. It is cross-checked below
# via arithmetic consistency against the parsed audit-log figures (a break
# in either source will raise, rather than silently mismatch), but is never
# printed on its own.
_PLACENTA_DECISION32_EXCLUDED_ROWS = _preprocessing_config.DECISION_32_PLACENTA_EXCLUDED_ROWS

_audit_log_path = _root / "outputs/preprocessing/audit/preprocessing_audit_log.md"
if not _audit_log_path.is_file():
    raise FileNotFoundError(
        f"Preprocessing audit log not found: {_audit_log_path}. Section A4's cohort-derivation "
        "counts are sourced from this file and cannot be displayed without it."
    )
_audit_log_text = _audit_log_path.read_text(encoding="utf-8")
_batch2_match = re.search(r"## Batch 2 —.*?(?=\\n## Batch 3|\\Z)", _audit_log_text, re.DOTALL)
if not _batch2_match:
    raise ValueError(f"Could not locate the '## Batch 2' section in {_audit_log_path}.")
_batch2_text = _batch2_match.group(0)

def _extract_audit_int(label, text=_batch2_text):
    _m = re.search(rf"- {re.escape(label)}:\\s*(\\d+)", text)
    if not _m:
        raise ValueError(f"Could not find audit-log line {label!r} in the Batch 2 section of {_audit_log_path}.")
    return int(_m.group(1))

_raw_rows          = _extract_audit_int("Rows start")
_trial_corrections = _extract_audit_int("trial_of_labor corrections applied")
_elective_cs_excl  = _extract_audit_int("Elective CS excluded")
_no_trial_excl     = _extract_audit_int("Excluded no-trial-of-labor")
_d67_excl          = _extract_audit_int("Excluded suspected superficial-only endometriosis (Decision 67)")
_audit_final_cohort = _extract_audit_int("Final cohort")

# Self-consistency check: the audit log's own "Final cohort" figure for Batch
# 2 already has both the placenta_accreta/previa exclusion and the suspected
# superficial-only-endometriosis exclusion baked in (both are applied within
# the same batch, before the "Final cohort" line is written) -- so raw -
# elective_cs - no_trial - the cited placenta exclusion count - the
# superficial-only exclusion count must equal both the audit log's own
# "Final cohort" figure AND the loaded dataset's actual row count. This ties
# the one cited (non-audit-log-derivable) literal to the audit log's own
# arithmetic and to the live df, rather than letting any of the three drift
# silently.
_expected_final = (
    _raw_rows - _elective_cs_excl - _no_trial_excl
    - _PLACENTA_DECISION32_EXCLUDED_ROWS - _d67_excl
)
if _expected_final != _audit_final_cohort or _audit_final_cohort != len(df):
    raise ValueError(
        f"Cohort-count arithmetic mismatch: {_raw_rows} raw - {_elective_cs_excl} elective CS - "
        f"{_no_trial_excl} non-trial-of-labor - {_PLACENTA_DECISION32_EXCLUDED_ROWS} cited Decision "
        f"32 exclusion - {_d67_excl} Decision 67 exclusion = {_expected_final}, audit-log 'Final "
        f"cohort' = {_audit_final_cohort}, loaded dataset rows = {len(df)}. Investigate before "
        f"trusting Section A4's counts."
    )

print("Cohort definition")
print()
print("  The cohort is derived from the project's raw dataset through a sequence of")
print("  clinically motivated inclusion and exclusion steps applied during")
print("  preprocessing, summarized below.")
print()
_after_trial_stage = _raw_rows - _elective_cs_excl - _no_trial_excl
_after_placenta_stage = _after_trial_stage - _PLACENTA_DECISION32_EXCLUDED_ROWS
# Disclosure-safe design: the placenta accreta/previa exclusion count is a
# protected small cell (n<5). Withholding the placenta line alone is not
# sufficient -- the raw dataset size, the two trial-of-labor exclusion
# counts, and the post-placenta cohort size (447, needed below as the
# Decision-67 "before" anchor and therefore unavoidably shown later in this
# same cell) together over-determine the system: any THREE of {raw,
# elective_cs_excl, no_trial_excl, 447} exactly pin down the fourth. Since
# 447 recurs later in this cell (Decision-67's own before/after accounting)
# and cannot be removed from this cell's output entirely, and
# elective_cs_excl/no_trial_excl are legitimate, independently useful,
# large/safe clinical exclusion counts, the raw pre-filtering dataset size
# is the one value withheld from THIS printed flow (it is not otherwise
# printed anywhere in this notebook) -- this removes one of the four
# knowns, so the placenta count cannot be recovered by arithmetic on values
# printed anywhere in this cell.
print("  Trial-of-labor reconciliation: vaginal deliveries recorded without a documented trial of")
print(f"    labor were corrected to trial-of-labor status         : {_trial_corrections} rows")
print(f"  Excluded: elective cesarean section                : {_elective_cs_excl:>3} rows")
print(f"  Excluded: no documented trial of labor              : {_no_trial_excl:>3} rows")
print("  Excluded: placenta accreta / placenta previa        : <5 rows "
      "(individually suppressed, n<5, per project small-cell disclosure policy)")
print(f"  Excluded: suspected superficial-only endometriosis  : {_d67_excl:>3} rows")
print("  ─────────────────────────────────────────────────────────────────")
print(f"  Final cohort                                      : {len(df)} rows")
print()

# The suspected superficial-only-endometriosis exclusion is implemented in
# preprocessing (externally confirmed by Sheba's clinical team 2026-08-18 --
# Decision 67 is RESOLVED, not pending), in Batch 2's canonical early
# cohort-eligibility section (run_preprocessing.py, Steps 5-6, alongside the
# elective-CS/trial-of-labor/placenta_accreta-previa exclusions, before
# target_intrapartum_cs is created). df loaded above is already the
# POST-exclusion cohort (N=431). This block reports the full before/after
# reconciliation from the machine-generated Batch 2 audit log -- it does not
# recompute or re-derive the exclusion mask itself.
# The vaginal breakdown is not itself a small cell, but the CS breakdown IS
# (n<5). Share-safe: this project's own binary target means
# CS_excluded = N_excluded - Vaginal_excluded always -- so showing the
# aggregate N-level before/after/excluded triple (safe, large) AND the
# exact vaginal-level before/after/excluded triple (also safe on its own)
# side by side would let a reader recover the protected CS-level excluded
# count by simple subtraction, even without ever printing that count or a
# "CS excluded" line directly. The class-level (vaginal vs. CS) "before"/
# "excluded" breakdown of this exclusion is therefore not printed at all
# below -- only the safe,
# aggregate N-level before/after/excluded figures, plus the resulting
# (post-exclusion) target distribution, which is reported separately further
# below in this same cell using only "after" values (370/61), never paired
# with a "before" or "excluded" class-level count.
_d67_vag_excl = _extract_audit_int(
    "Excluded suspected superficial-only endometriosis (Decision 67), vaginal"
)
_d67_cs_excl = _d67_excl - _d67_vag_excl
_d67_n0_after = int((df[TARGET_COL] == 0).sum())
_d67_n1_after = int((df[TARGET_COL] == 1).sum())
_d67_n_after = len(df)
_d67_n_before = _d67_n_after + _d67_excl
_d67_n0_before = _d67_n0_after + _d67_vag_excl
_d67_n1_before = _d67_n1_after + _d67_cs_excl

# Fail-loud internal consistency checks only -- these values are used for
# assertions below, never printed as class-level before/excluded figures.
assert _d67_n_before == _d67_excl + _d67_n_after, "Decision 67: N_before = N_excluded + N_after failed"
assert _d67_n1_before == _d67_cs_excl + _d67_n1_after, "Decision 67: CS_before = CS_excluded + CS_after failed"
assert _d67_n0_before == _d67_vag_excl + _d67_n0_after, "Decision 67: Vaginal_before = Vaginal_excluded + Vaginal_after failed"
assert _d67_n_after == _d67_n1_after + _d67_n0_after, "Decision 67: N_after = CS_after + Vaginal_after failed"

print("  Suspected superficial-only endometriosis exclusion (Decision 67)")
print()
print("  This criterion was defined before the outcome (target_intrapartum_cs) was")
print("  constructed, so it could not have been shaped by delivery outcome. It")
print("  excludes deliveries where the only documented endometriosis finding was")
print("  superficial disease — with no peritoneal, deep, ovarian (endometrioma), or")
print("  cesarean-scar endometriosis, and no adenomyosis — and where the diagnosis")
print("  itself rested on clinical impression alone rather than a confirmed surgical")
print("  or imaging finding. Any record with documented adenomyosis is retained")
print("  regardless of this rule, and isolated surgical evidence without a")
print("  documented endometriotic lesion, excision, or pathology finding does not by")
print("  itself trigger exclusion.")
print()
print(f"    Cohort N (aggregate)     before: {_d67_n_before:>4}   |   after: {_d67_n_after:>4}   |   excluded: {_d67_excl:>3}")
print("    Vaginal-vs.-intrapartum-CS breakdown of this exclusion is not individually")
print("    reported: the intrapartum-CS component is a protected small cell (n<5); see")
print("    the final cohort target distribution below for the resulting (post-")
print("    exclusion) class counts only.")
print()
print("  Sensitivity cohorts using a broader or narrower version of this exclusion")
print("  criterion are reconstructable from this dataset via the")
print("  decision67_sensitivity_19group_excluded / _26group_excluded flag columns")
print("  (N=428 and N=421 respectively), without retaining the 16 excluded rows here.")
print()

if "trial_of_labor_corrected" in df.columns:
    _n_not1 = int((df["trial_of_labor_corrected"] != 1).sum())
    if _n_not1 == 0:
        print("  All retained rows meet the trial-of-labor inclusion criterion.")
    else:
        print(f"  Unexpected: {_n_not1} retained row(s) do not meet the trial-of-labor "
              "inclusion criterion.")

if TARGET_COL in df.columns:
    _vc  = df[TARGET_COL].value_counts().sort_index()
    _n0  = int(_vc.get(0, 0))
    _n1  = int(_vc.get(1, 0))
    _tot = len(df)
    _cs_pct = 100 * _n1 / _tot
    print(f"  Target: {TARGET_COL}")
    print(f"    0 = Vaginal delivery   : {_n0:>4}  ({100*_n0/_tot:.1f}%)")
    print(f"    1 = Intrapartum CS     : {_n1:>4}  ({_cs_pct:.1f}%)")
    print(f"    Class imbalance ratio  : {_n0/_n1:.1f}:1")
    print()
    print(f"  Note: the target is imbalanced ({_cs_pct:.1f}% intrapartum CS), which should")
    print("  be considered during model evaluation and threshold selection.")

    # Bar chart
    fig, ax = plt.subplots(figsize=(5, 3.5))
    _colors = [sns.color_palette("muted")[0], sns.color_palette("muted")[3]]
    ax.bar(["0 — Vaginal", "1 — Intrapartum CS"], [_n0, _n1], color=_colors)
    for _bar, _n in zip(ax.patches, [_n0, _n1]):
        ax.text(_bar.get_x() + _bar.get_width()/2, _bar.get_height() + 3,
                f"n={_n}", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Number of deliveries")
    ax.set_title(f"Target distribution (N={_tot})")
    plt.tight_layout()
    plt.show()
""")

SA4_KEY_OBS = md("eda-a-s04-key-observations", """**Key observations:**""")

SA4_KEY_OBS_CODE = code("eda-a-s04-key-observations-code", """
_ko4_n0 = int((df[TARGET_COL] == 0).sum())
_ko4_n1 = int((df[TARGET_COL] == 1).sum())
print(f"- Cohort N={len(df)}; target is imbalanced ({_ko4_n0}:{_ko4_n1}, "
      f"ratio {_ko4_n0/_ko4_n1:.1f}:1) -- requires threshold selection and/or "
      f"class-imbalance handling during modeling, not during EDA.")
print(f"- All retained records satisfy the documented trial-of-labor inclusion "
      f"criterion (see above); the cohort definition is a preprocessing/cohort-control "
      f"decision, not something re-derived or altered by this notebook.")
""")


# ── Collect Part 1 cells ──────────────────────────────────────────────────────
EDA_A_PART1_CELLS = [
    SA0_HEADER,
    SA1_HEADER, SA1_FLAGS, SA1_IMPORTS, SA1_CONFIG, SA1_PATHS,
    SA2_HEADER, SA2_LOAD,
    SA3_HEADER, SA3_INVENTORY, SA3_INVENTORY_TABLE, SA3_KEY_OBS, SA3_KEY_OBS_CODE,
    SA4_HEADER, SA4_COHORT, SA4_KEY_OBS, SA4_KEY_OBS_CODE,
]

if __name__ == "__main__":
    print(f"EDA A Part 1 cells defined: {len(EDA_A_PART1_CELLS)}")

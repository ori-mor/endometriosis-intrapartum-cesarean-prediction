#!/usr/bin/env python3
"""EDA A2 — Part 1: cell definitions (sections A2.0–A2.2).

Sections:
  A2.0 — Purpose, scope, safety rules
  A2.1 — Setup: imports, flags, config, helper functions
  A2.2 — Load + build df_primary (main baseline predictors)
       and document secondary near-delivery/labor-adjacent variables separately

Primary scope: predictor_allowed rows from variable_classification_minimal.csv
Secondary near-delivery variables: documented but excluded from main baseline deep-dive
Timing/context-unclear variables: in clinical decision registry only (A2.14)
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


# ── Section A2.0 ────────────────────────────────────────────────────────────────
SB0_HEADER = md("eda-b-s00-header", """
# EDA A2 — Initial Predictor-Readiness EDA (Section 1)
## Endometriosis & Intrapartum Cesarean Section — Sheba Medical Center

---

## Academic analytical notebook — privacy and use note

This notebook is intended for approved academic/project review and is not a
clinical decision-support tool. Patient identifiers and tabular patient-level
records are not intentionally displayed, and rare-cell outputs are suppressed
where applicable, but the notebook may still contain observation-level
visualizations, exact ranges, and rare-value frequencies; sharing should
therefore follow the project's approved data-governance procedures.

**Cohort status:** the current analysis uses the working cohort of
N=431 (vaginal=370, intrapartum CS=61). 16 records with suspected
superficial-only endometriosis are excluded from this cohort (see EDA A
Part 1, Section A4, and Section A2.15 here for the full accounting). Any
variable marked `pending_timing_confirmation` in the current
`modeling_clearance` status is not cleared for modeling (Sections
A2.2/A2.12/A2.13).

---

> **Scope note.** This notebook performs predictor-readiness EDA only: it is the
> second initial-EDA notebook after A1 (cohort overview) and performs no data
> cleaning — it never modifies `df`, never imputes, and never removes rows. It is
> distinct from the separate data-cleaning notebook; this folder was renamed
> from `eda_b` to `a2_predictor_readiness` on 2026-08-24, and internal
> `EDA_B_*` symbol names / `eda-b-*` cell IDs are retained unchanged for
> execution stability only.

---

## Section A2.0 — Purpose, Scope, and Methodology

### Study population and target
The cohort comprises women who underwent a trial of vaginal labor (elective cesarean
and non-trial-of-labor deliveries are excluded upstream, in preprocessing). The
outcome, `target_intrapartum_cs`, is binary: 0 = vaginal delivery, 1 = intrapartum
cesarean section. The classes are imbalanced (approximately 6:1 vaginal-to-CS), which
is handled explicitly during modeling, not in this EDA.

### Research question
Can endometriosis characteristics, obstetric risk factors, and pregnancy data predict
the risk of intrapartum cesarean section after a trial of vaginal labor?

### Purpose of the primary model
The primary model is intended to estimate intrapartum-CS risk from information
available *before* labor begins, so that any resulting risk estimate could plausibly
inform pre-labor counselling or planning rather than merely describing labor's
outcome after the fact.

### Timing principle for predictor eligibility
A variable is eligible for the pre-labor (Stage 1) model only if it reflects
information available before admission to the labor unit; later stages (Stage 2:
pre-labor + near-delivery; Stage 3: pre-labor + near-delivery + intrapartum) add
progressively richer, later-available information without discarding earlier stages.
This notebook consumes that eligibility directly from the current preprocessing
classification: `predictor_allowed` is Stage 1; `secondary_near_delivery_predictor`
is near-delivery/labor-adjacent and enters at Stage 2; `intrapartum_predictor_
exclude_from_prelabor_model` enters only at Stage 3. All three groups are analysed
together throughout this notebook (`PRIMARY_COLS` is their cumulative union) — this
is descriptive/readiness coverage only, not a model-training decision;
horizon-specific model eligibility is decided downstream, at the modeling boundary.

Two variables worth naming explicitly, since their eligibility is not obvious from
the name alone: `oligohydramnios` is assessed by ultrasound during pregnancy and is
classified `predictor_allowed` (Stage 1 eligible); `placental_abruption` is
classified `secondary_near_delivery_predictor` (Stage 2 eligible; near-delivery
horizon and modeling clearance confirmed by Keren) and is analysed throughout this
notebook alongside every other Stage 1-3 variable.

### Analytical principles
1. This notebook never modifies `df`.
2. Outputs avoid printing patient-level rows.
3. `dropna()` is never used blindly — N analyzed is always reported alongside N missing.
4. Leakage, post-outcome, and manual-review-pending variables are excluded from
   predictor-readiness statistical analyses and modeling-candidate summaries.
5. FDR-corrected p-values are screening signals only — not feature selection rules.
6. Clinically important variables may remain candidates even with non-significant p-values.
""")


# ── Section A2.1 ────────────────────────────────────────────────────────────────
SB1_HEADER = md("eda-b-s01-header", """
## Section A2.1 — Setup: Imports, Flags, Config, Helper Functions
""")

SB1_FLAGS = code("eda-b-s01-flags", """
SAVE_AGGREGATED_OUTPUTS = False
# Share-safe output mode, default ON: suppresses small-cell (n<5)
# counts/percentages in the sections reviewed below so this notebook's
# rendered output is safer to export and share as HTML. See
# eda_shared/share_safe.py.
#
# COVERAGE (do not read this flag as "the whole notebook is fully
# share-safe" without reading this list). Actively suppressed via
# share_safe/safe_pct_disclosure when this flag is True:
#   A2.4  -- binary rate table (cs_events/vaginal_events + their %, and
#          abs_diff_% when either is suppressed), categorical level table
#          (per-level total/vaginal/CS counts, including the per-level
#          vaginal/CS split, not just the total)
#   A2.5  -- endometriosis-domain binary table (vaginal_%/CS%)
#   A2.6  -- obstetric/mode-of-conception/complications domain binary tables
#   A2.7  -- missingness table (see structural_missingness_registry.py for the
#          separate three-state model; not a share-safe-mode item)
#   A2.8  -- sparsity table (cs_events label, min_vaginal_cell, min_any_cell);
#          the boolean flags (separation_risk/too_sparse/rare_flag) are
#          always shown regardless of this setting, since flagging small
#          cells for clinical review is this section's purpose
#   A2.9  -- association table (cs_summ/vaginal_summ percentages)
#   A2.10 -- numcat screening (group_Ns_str per-category counts), catcat
#          screening (already had no raw-count gap), A2.10d worked example
#          (mode_of_conception contingency table cells)
#   A2.11 -- outlier table (n_outliers/outlier_%) and the outcome-sensitivity
#          table (outcome_rate_outliers -- suppressed whenever it would
#          disclose a small outlier subgroup's raw target-event count, the
#          most severe reconstruction risk found in this audit)
#   A2.12 -- comprehensive diagnostic table (cs_events/min_any_cell, reused
#          from A2.8)
#   A2.15 -- handoff summary's "too sparse" per-variable listing
# Not part of this audit's scope: A2.3 (unstratified numeric summaries, no
# raw small-cell counts by construction), A2.13/A2.14 (already display booleans/
# effect sizes only, no raw counts printed), A2.10a (numeric-numeric scatter
# plots -- a different kind of disclosure risk, individual point visibility,
# not addressed by share_safe's count/percentage suppression design; treated
# as out of scope for this pass, consistent with every other scatter/
# heatmap plot in both notebooks). Set to False only for local, non-shared
# review.
SHARE_SAFE_MODE = True
print(f"SAVE_AGGREGATED_OUTPUTS = {SAVE_AGGREGATED_OUTPUTS}")
print(f"SHARE_SAFE_MODE = {SHARE_SAFE_MODE}")
print("  NOTE: SHARE_SAFE_MODE=True suppresses small-cell (n<5) counts/percentages in")
print("  the specific sections documented in this cell's source comment (A2.4-A2.12, A2.15).")
print("  It does NOT make this notebook fully share-safe -- A2.10a's numeric-numeric")
print("  scatterplots, other point-level plots, and numeric ranges are still present.")
print("  This notebook is INTERNAL ANALYTICAL REVIEW ONLY -- see Section A2.0.")
""")

SB1_IMPORTS = code("eda-b-s01-imports", """
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path
import sys, os, re, zipfile, warnings, importlib.util

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
pd.set_option("display.max_rows", 150)
pd.set_option("display.float_format", "{:.3f}".format)
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.05)
matplotlib.rcParams["figure.dpi"] = 90
_MUTED = sns.color_palette("muted")
C0, C1 = _MUTED[0], _MUTED[3]
PALETTE = [C0, C1]

IN_COLAB = "google.colab" in sys.modules
print(f"Environment: {'Google Colab' if IN_COLAB else 'Local'}")
print(f"pandas {pd.__version__} | seaborn {sns.__version__}")

# This notebook is local-repository-only. The check runs here, immediately
# after determining IN_COLAB and before the next cell's classification-CSV/
# variable-type-schema upload prompts even begin, because later setup steps
# load structural_missingness_registry.py / share_safe.py directly from the
# repository filesystem and neither has a Colab upload flow -- checking now
# avoids asking a Colab user to complete uploads that could never be used.
if IN_COLAB:
    raise RuntimeError(
        "This notebook is local-repository-only and cannot currently run in "
        "Google Colab: later setup steps load structural_missingness_registry.py, "
        "share_safe.py, canonical_data_manifest.py, and canonical_data_resolver.py "
        "directly from the repository filesystem (analysis/eda/notebook_build/"
        "eda_shared/), which Colab does not have access to. Run this notebook "
        "locally from a clone of the repository instead."
    )
""")

SB1_CONFIG = code("eda-b-s01-config", r"""
# Load approved variable classification CSV directly. No config.py or embedded classification fallback is used.
PROJECT_ROOT_OVERRIDE = None
CLASSIFICATION_REL = "outputs/preprocessing/audit/variable_classification_minimal.csv"
VARIABLE_TYPE_SCHEMA_REL = "outputs/preprocessing/audit/variable_type_schema_minimal.csv"
PROCESSED_GLOB = "outputs/preprocessing/processed/work_df_batch*.xlsx"
# Cohort/target counts reflecting the current working cohort (16 suspected
# superficial-only endometriosis records excluded).
# This is a pre-resolution placeholder only, needed because _root is not
# resolved until a later cell. The SA1_PATHS-equivalent cell below overwrites
# these three names from preprocessing_config.py's CURRENT_APPROVED_COHORT_
# ROWS/TARGET_N0/TARGET_N1 before they are ever read -- update
# preprocessing_config.py alone after a future approved cohort revision;
# this literal is not the authoritative value.
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
# Expected per-category counts for the current classification
# (outputs/preprocessing/audit/variable_classification_minimal.csv).
# This is a validation checksum only -- actual group membership is always
# derived directly from the loaded CSV (see _cols_for() below), never from a
# fixed per-variable list. If preprocessing classification changes, this
# dict must be updated to match; a mismatch is reported/described (see
# _CLASSIFICATION_COUNT_DIFFS below) rather than raised -- it is EXPECTED and
# healthy immediately after an approved reclassification, so the loader does
# NOT fail loudly on a mismatch; it never blocks execution.
EXPECTED_CLASSIFICATION_COUNTS = {
    "id": 2,
    "target": 1,
    # peritoneal_endometriosis is the modeled representation of the
    # superficial/peritoneal endometriosis phenotype; superficial_
    # endometriosis itself is clinically_redundant_exclude (see below).
    "predictor_allowed": 60,
    # placental_abruption's category membership reflects its confirmed
    # measurement timing (available during labor and before the cesarean
    # decision). BMI_after is also a member of this category -- it is
    # formula-derived from weight_in_pregnancy/height, not an
    # independently-sourced postpartum value. Predictor-timing/scope only;
    # its missingness treatment remains a separate open question.
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
    "intrapartum_or_post_delivery_exclude": 37,
    "manual_review_pending": 0,
    "awaiting_clinical_clarification": 0,
}
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


def _collect_roots():
    seen = set()
    roots = []

    def _add(p):
        try:
            rp = Path(str(p)).resolve()
        except Exception:
            return
        if rp not in seen:
            seen.add(rp)
            roots.append(rp)

    if PROJECT_ROOT_OVERRIDE is not None:
        _add(PROJECT_ROOT_OVERRIDE)
    if "__file__" in dir():
        p = Path(__file__).resolve().parent
        for _ in range(10):
            _add(p)
            if p.parent == p:
                break
            p = p.parent
    p = Path.cwd().resolve()
    for _ in range(10):
        _add(p)
        if p.parent == p:
            break
        p = p.parent
    return roots


def _find_project_root():
    for root in _collect_roots():
        if (root / CLASSIFICATION_REL).is_file() and (root / Path(PROCESSED_GLOB).parent).is_dir():
            return root
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
    # is enforced separately, after `df` is loaded, via a two-way
    # set-difference check (not possible here since `df` does not exist yet
    # at classification-load time).
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


def _load_variable_type_schema(path):
    if not Path(path).is_file():
        return pd.DataFrame(columns=["variable_name", "variable_type", "n_categories"]), {}, []
    schema = pd.read_csv(path)
    required = ["variable_name", "variable_type", "n_categories"]
    missing = [c for c in required if c not in schema.columns]
    if missing:
        raise ValueError(f"Variable type schema missing required columns: {missing}")
    schema = schema[required].copy()
    schema["variable_name"] = schema["variable_name"].astype("string").str.strip()
    schema["variable_type"] = schema["variable_type"].astype("string").str.strip()
    errors = []
    dupes = schema.loc[schema["variable_name"].duplicated(), "variable_name"].dropna().tolist()
    if dupes:
        errors.append(f"duplicate variable_name values: {dupes}")
    if schema["variable_name"].isna().any() or (schema["variable_name"] == "").any():
        errors.append("empty variable_name values")
    unexpected = sorted(set(schema["variable_type"].dropna()) - set(ALLOWED_VARIABLE_TYPES))
    if unexpected:
        errors.append(f"unexpected variable_type values: {unexpected}")
    if errors:
        raise ValueError("Invalid variable type schema: " + "; ".join(errors))
    type_map = dict(zip(schema["variable_name"].astype(str), schema["variable_type"].astype(str)))
    return schema, type_map, errors


if IN_COLAB:
    _cls_fname = "variable_classification_minimal.csv"
    if Path(_cls_fname).is_file():
        print(f"Found {_cls_fname} in working directory — using it directly.")
    else:
        from google.colab import files as _gf
        print("Step 1 of 2 — Upload variable_classification_minimal.csv")
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
        "Classification category counts differ from the last-recorded baseline "
        "(expected, healthy after an approved reclassification -- descriptive "
        f"only, not blocking): {_CLASSIFICATION_COUNT_DIFFS}"
    )

# The canonical variable-type schema is REQUIRED, not optional -- every
# statistical/type decision in this notebook (infer_var_type()) treats
# VARIABLE_TYPE_MAP as the sole source of truth and must never silently fall
# back to a dtype/unique-count heuristic that could disagree with the
# approved schema. Colab therefore explicitly prompts for this file (like the
# classification CSV above) rather than silently proceeding with an empty map
# if it happens to be absent from the working directory.
if IN_COLAB:
    _schema_local = Path("variable_type_schema_minimal.csv")
    if not _schema_local.is_file():
        print("Step 2 of 2 — Upload variable_type_schema_minimal.csv")
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

variable_type_schema_df, VARIABLE_TYPE_MAP, _schema_errors = _load_variable_type_schema(VARIABLE_TYPE_SCHEMA_PATH)
if not VARIABLE_TYPE_MAP:
    raise FileNotFoundError(
        f"Canonical variable-type schema not found or empty ({VARIABLE_TYPE_SCHEMA_PATH}). "
        "This notebook requires it to assign canonical statistical types and must not "
        "silently fall back to a dtype/unique-count heuristic that could disagree with the "
        "approved schema. Colab: upload variable_type_schema_minimal.csv when prompted. "
        f"Local/repository: ensure it exists at {VARIABLE_TYPE_SCHEMA_REL}."
    )

# Coverage verification: every classified dataset column must have a
# canonical type entry -- a gap here would otherwise be invisible until (and
# unless) infer_var_type() happened to be called on that specific column.
_schema_covered = set(VARIABLE_TYPE_MAP.keys())
_classified_cols = set(classification_df["column_name"])
_TYPE_SCHEMA_MISSING_COLS = sorted(_classified_cols - _schema_covered)
_TYPE_SCHEMA_UNEXPECTED_COLS = sorted(_schema_covered - _classified_cols)
if _TYPE_SCHEMA_MISSING_COLS:
    raise ValueError(
        f"{len(_TYPE_SCHEMA_MISSING_COLS)} classified dataset column(s) have no canonical "
        f"variable-type entry: {_TYPE_SCHEMA_MISSING_COLS}. Every column in "
        f"{CLASSIFICATION_REL} must also appear in {VARIABLE_TYPE_SCHEMA_REL}."
    )


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
LEAKAGE_EXCLUDE_COLS = _cols_for("leakage_exclude")
INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS = _cols_for("intrapartum_or_post_delivery_exclude")
MANUAL_REVIEW_PENDING_COLS = _cols_for("manual_review_pending")
AWAITING_CLINICAL_CLARIFICATION_COLS = _cols_for("awaiting_clinical_clarification")

# Temporary aliases for older EDA cells; the CSV labels above are the source of truth.
POST_OUTCOME_EXCLUDE_COLS = INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS
CANDIDATE_FOR_EDA_DECISION_COLS = AWAITING_CLINICAL_CLARIFICATION_COLS
ADMISSION_LABOR_COLS = SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS

# Structural-missingness metadata is centralized in
# eda_shared/structural_missingness_registry.py (see that module for the
# confirmed-gate methodology). eda_a and a2_predictor_readiness both load
# this single shared registry instead of each hand-maintaining an independent copy.
import importlib.util as _importlib_util
# the IN_COLAB fail-fast check now happens once, immediately, at
# the end of Section A2.1's imports cell (before any upload prompt) -- see that
# check there. This point is unreachable in Colab, so _root is guaranteed
# non-None here.
_shared_dir = _root / "analysis" / "eda" / "notebook_build" / "eda_shared"
_structmiss_spec = _importlib_util.spec_from_file_location(
    "structural_missingness_registry", _shared_dir / "structural_missingness_registry.py"
)
structural_missingness_registry = _importlib_util.module_from_spec(_structmiss_spec)
_structmiss_spec.loader.exec_module(structural_missingness_registry)

STRUCTURAL_NAN_COLS = structural_missingness_registry.structural_nan_cols()
STRUCTURAL_SUBGROUP_GATES = structural_missingness_registry.structural_subgroup_gates()
# Separate third tier: empirically subgroup-patterned
# missingness with NO code-enforced gate. Must never be merged into
# STRUCTURAL_NAN_COLS -- see structural_missingness_registry.py docstring.
# These columns get their own "applicability_linked_no_preprocessing_mask"
# category in A2.7, NOT "structural_by_design", and no missingness-penalty
# exemption in A2.13.
APPLICABILITY_LINKED_COLS = structural_missingness_registry.applicability_linked_cols()
APPLICABILITY_LINKED_NO_PREPROCESSING_MASK_LABEL = (
    structural_missingness_registry.APPLICABILITY_LINKED_NO_PREPROCESSING_MASK_LABEL
)

_sharesafe_spec = _importlib_util.spec_from_file_location(
    "share_safe", _shared_dir / "share_safe.py"
)
share_safe = _importlib_util.module_from_spec(_sharesafe_spec)
_sharesafe_spec.loader.exec_module(share_safe)
# TIMING_MAP describes ONLY when a value is typically recorded relative to
# labor/delivery (its measurement horizon), labeled "intrapartum" for
# INTRAPARTUM_PREDICTOR_EXCLUDE_COLS variables (a measurement-timing fact,
# not a clearance claim) -- separately, TIMING_REVIEW_STATUS/
# TIMING_REVIEW_REASON below mark some of those same variables OPEN (timing
# not yet clinically confirmed). Whether a variable is actually cleared for
# modeling is the separate, orthogonal MODELING_CLEARANCE_MAP defined after
# TIMING_REVIEW_REASON below, derived from the single canonical
# TIMING_REVIEW_STATUS registry -- never inferred from the horizon label
# itself.
TIMING_MAP = {c: "baseline" for c in PREDICTOR_ALLOWED_COLS}
TIMING_MAP.update({c: "near_delivery" for c in SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS})
TIMING_MAP.update({c: "pending_timing_confirmation" for c in PENDING_TIMING_CONFIRMATION_COLS})
TIMING_MAP.update({c: "intrapartum" for c in INTRAPARTUM_PREDICTOR_EXCLUDE_COLS})
TIMING_MAP.update({c: "unclear" for c in AWAITING_CLINICAL_CLARIFICATION_COLS})
# previously initialized for PREDICTOR_ALLOWED_COLS
# (Stage 1) only, so every Stage 2/3 addition silently fell back to A2.13's
# `CLINICAL_TIER.get(col, 0)` default of 0 -- an unintended structural bonus
# for every Stage-1 variable over every later-stage variable, regardless of
# actual clinical importance. Default tier now covers the FULL Stage-3
# candidate universe (Stage 1 + Stage 2 additions + Stage 3 additions) so no
# variable is penalized purely for its stage of entry; the bump-to-2 list
# below is unaffected and still marks a higher-priority subset within that
# same baseline.
CLINICAL_TIER = {
    c: 1 for c in (
        PREDICTOR_ALLOWED_COLS
        + SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS
        + INTRAPARTUM_PREDICTOR_EXCLUDE_COLS
    )
}
for _c in [
    "AGE", "nulliparity", "S_P_CS", "VBAC", "BMI_before", "endometrioma",
    "deep_endometriosis", "adenomyosis", "endometriosis_surgery",
    "gestational_diabetes", "pregnancy_related_hypertensive_disorder", "IUGR",
    "mode_of_conception_ivf_vs_all", "aspirin_during_pregnancy",
]:
    if _c in CLINICAL_TIER:
        CLINICAL_TIER[_c] = 2

# Single canonical clinical-review registry, keyed by actual PRIMARY_COLS
# column name: `review_type` explicitly distinguishes timing/sparsity/
# redundancy questions, and `blocks_modeling` is an explicit boolean set
# only for genuinely modeling-blocking OPEN timing questions -- never
# inferred from the wording, punctuation, or capitalization of a
# human-readable reason string. TIMING_REVIEW_STATUS/TIMING_REVIEW_REASON
# below are DERIVED compatibility views (not independently maintained) for
# downstream cells/tests that still read those two names directly.
#
# Status/blocks_modeling here must always match the corresponding
# CLINICAL_DECISIONS entry's current_status in a2_part5_readiness.py --
# update both together.
CLINICAL_REVIEW_REGISTRY = {
    "S_P_CS": {
        "status": "RESOLVED", "review_type": "sparsity", "blocks_modeling": False,
        "reason": "Retained as a predictive candidate. Prior-CS patients rarely have an intrapartum CS in a trial of labor, so the intrapartum-CS event count is small and near complete separation; sparse-event / near-separation handling (penalized or bias-reduced estimation, CV-based stability assessment) is a modeling-stage concern, not a reason for pre-model exclusion. Final retention is determined during modeling.",
    },
    "cs_scar_endometriosis": {
        "status": "RESOLVED", "review_type": "sparsity", "blocks_modeling": False,
        "reason": "Retained as a predictive candidate. Clinically specific to endometriosis and available before the outcome; the small intrapartum-CS event count is a modeling-stage concern (sparse-event-aware handling, CV-based stability assessment), not a pre-model exclusion reason. Final retention is determined during modeling.",
    },
    "placental_abruption": {
        "status": "RESOLVED", "review_type": "timing", "blocks_modeling": False,
        "reason": "Near-delivery horizon (secondary_near_delivery_predictor) is correct; eligible from Stage 2 (pre-labor + near-delivery) onward.",
    },
    "intrapartum_fever_or_chorioamnionitis_bin": {
        "status": "RESOLVED", "review_type": "timing", "blocks_modeling": False,
        "reason": "Available during labor and before the cesarean decision -- intrapartum timing. Eligible for Stage 3 only (an intrapartum risk-update model, not an early/prelabor model), excluded from Stage 1 and Stage 2.",
    },
    "meconium_stained_amniotic_fluid": {
        "status": "RESOLVED", "review_type": "timing", "blocks_modeling": False,
        "reason": "Available during labor and before the cesarean decision -- intrapartum timing. Eligible for Stage 3 only (an intrapartum risk-update model, not an early/prelabor model), excluded from Stage 1 and Stage 2.",
    },
    "oligohydramnios": {
        "status": "RESOLVED", "review_type": "timing", "blocks_modeling": False,
        "reason": "consistently documented from antepartum ultrasound (pre-labor), consistently with polyhydramnios; not an intrapartum finding here. Classified predictor_allowed.",
    },
    "Hb_before_delivery": {
        "status": "RESOLVED", "review_type": "timing", "blocks_modeling": False,
        "reason": "not taken during labor; timing is heterogeneous across the pregnancy/admission window but always available before intrapartum events. Classified secondary_near_delivery_predictor and analyzed separately from the primary pool for that reason.",
    },
    "pregnancy_related_hypertensive_disorder": {
        "status": "RESOLVED", "review_type": "redundancy", "blocks_modeling": False,
        "reason": "derived_hypertension_pih_pet_spectrum is the 3-level grouped/composite representation; the individual subtype variables are retained ungrouped as well (DERIVED_REDUNDANCY_GROUPS entry 'hypertension_pih_pet_spectrum_representation', representative=None) because they carry independent clinical value the 3-level grouping intentionally coarsens. Final retention is determined during modeling.",
    },
    "any_PET": {
        "status": "RESOLVED", "review_type": "redundancy", "blocks_modeling": False,
        "reason": "See pregnancy_related_hypertensive_disorder. The small intrapartum-CS event count (below the n<5 disclosure threshold) is a modeling-stage sparsity concern, not a pre-model exclusion reason.",
    },
    "PIH": {
        "status": "RESOLVED", "review_type": "redundancy", "blocks_modeling": False,
        "reason": "See pregnancy_related_hypertensive_disorder.",
    },
    "mild_PET": {
        "status": "RESOLVED", "review_type": "redundancy", "blocks_modeling": False,
        "reason": "See pregnancy_related_hypertensive_disorder.",
    },
    "severe_PET": {
        "status": "RESOLVED", "review_type": "redundancy", "blocks_modeling": False,
        "reason": "See pregnancy_related_hypertensive_disorder.",
    },
    "SIPET": {
        "status": "RESOLVED", "review_type": "redundancy", "blocks_modeling": False,
        "reason": "See pregnancy_related_hypertensive_disorder.",
    },
}

# Approved review_type vocabulary -- fail loudly if a future entry uses an
# unrecognized category instead of silently accepting a typo.
_APPROVED_REVIEW_TYPES = {"timing", "sparsity", "redundancy"}
_bad_review_types = {
    v: info["review_type"] for v, info in CLINICAL_REVIEW_REGISTRY.items()
    if info["review_type"] not in _APPROVED_REVIEW_TYPES
}
assert not _bad_review_types, (
    f"SAFETY: CLINICAL_REVIEW_REGISTRY contains unapproved review_type value(s): "
    f"{_bad_review_types}. Approved vocabulary: {_APPROVED_REVIEW_TYPES}."
)
assert all(info["status"] in ("OPEN", "RESOLVED") for info in CLINICAL_REVIEW_REGISTRY.values()), (
    "SAFETY: CLINICAL_REVIEW_REGISTRY 'status' must be exactly 'OPEN' or 'RESOLVED'."
)
# blocks_modeling may only be True for a genuinely unresolved timing question
# -- never for sparsity/redundancy questions (which are display/warning-only
# context, not a modeling-eligibility gate) and never for a RESOLVED entry.
_bad_blocks_modeling = {
    v for v, info in CLINICAL_REVIEW_REGISTRY.items()
    if info["blocks_modeling"] and (info["review_type"] != "timing" or info["status"] != "OPEN")
}
assert not _bad_blocks_modeling, (
    f"SAFETY: blocks_modeling=True is only valid for an OPEN, review_type='timing' entry: "
    f"{_bad_blocks_modeling}"
)

# Derived compatibility views, not independently maintained -- recomputed
# from CLINICAL_REVIEW_REGISTRY every run, so they stay consistent with it.
TIMING_REVIEW_STATUS = {v: info["status"] for v, info in CLINICAL_REVIEW_REGISTRY.items()}
TIMING_REVIEW_REASON = {v: info["reason"] for v, info in CLINICAL_REVIEW_REGISTRY.items()}

# ── modeling_clearance ──────────────────────────────────────────────────────
# Orthogonal to TIMING_MAP's measurement_horizon: a variable's horizon
# (baseline/near_delivery/intrapartum/etc.) says WHEN it is typically
# recorded; clearance says whether it may actually enter a model yet.
# Derived only from CLINICAL_REVIEW_REGISTRY's structured `blocks_modeling`
# boolean -- never from reason text or wording.
TIMING_OPEN_VARS = {
    v for v, info in CLINICAL_REVIEW_REGISTRY.items() if info["blocks_modeling"]
}
# Every variable in the full Stage-3 candidate universe (TIMING_MAP's own
# keys) gets an explicit clearance: "cleared" unless it is one of the
# timing-open variables above, in which case it is
# "pending_timing_confirmation" and must remain blocked from every model
# until per-delivery pre-CS-decision availability is clinically confirmed
# (see A2.14/A2.15), regardless of what any descriptive EDA panel shows.
MODELING_CLEARANCE_MAP = {
    c: ("pending_timing_confirmation" if c in TIMING_OPEN_VARS else "cleared")
    for c in TIMING_MAP
}

# ── Fail-loud coverage assertions ───────────────────────────────────────────
# Every Stage 1-3 candidate (TIMING_MAP's own key set) must have EXACTLY one
# clearance value, and MODELING_CLEARANCE_MAP must define no unexpected extra
# keys -- an omitted or extra key here would mean a consumer using safe .get()
# fallback logic could silently treat an unmapped variable as cleared, which
# is exactly the fail-open risk this coverage check exists to catch upstream
# of every consumer (all consumers now use direct MODELING_CLEARANCE_MAP[col]
# indexing instead of .get(col, "cleared") -- see A2.12/A2.13).
_clearance_universe = set(TIMING_MAP)
_clearance_keys = set(MODELING_CLEARANCE_MAP)
assert _clearance_keys == _clearance_universe, (
    "SAFETY: MODELING_CLEARANCE_MAP key set does not exactly match the Stage 1-3 "
    f"candidate universe (TIMING_MAP keys). Missing: {sorted(_clearance_universe - _clearance_keys)}; "
    f"unexpected: {sorted(_clearance_keys - _clearance_universe)}."
)
_APPROVED_CLEARANCE_VALUES = {"cleared", "pending_timing_confirmation"}
_bad_clearance_values = {
    c: v for c, v in MODELING_CLEARANCE_MAP.items() if v not in _APPROVED_CLEARANCE_VALUES
}
assert not _bad_clearance_values, (
    f"SAFETY: MODELING_CLEARANCE_MAP contains value(s) outside the approved vocabulary "
    f"{_APPROVED_CLEARANCE_VALUES}: {_bad_clearance_values}"
)

# Fail-loud validation checksum ONLY (not a second operational source of
# truth) -- the actual modeling-blocked set is always derived from
# CLINICAL_REVIEW_REGISTRY above. This just catches an unintended silent
# change (e.g. a future registry edit that widens or narrows the blocked set
# without an explicit clinical decision) as early and loudly as possible.
# placental_abruption, meconium_stained_amniotic_
# fluid, and intrapartum_fever_or_chorioamnionitis_bin all RESOLVED -- Keren
# confirmed clinically confirmed intrapartum timing for all three. The
# modeling-blocked set is now empty; kept as an explicit empty set (not
# removed) so a future accidental block is still caught by this checksum.
_MODELING_BLOCKED_EXPECTED_CHECKSUM = set()
_modeling_blocked_actual = {
    c for c, v in MODELING_CLEARANCE_MAP.items() if v == "pending_timing_confirmation"
}
assert _modeling_blocked_actual == _MODELING_BLOCKED_EXPECTED_CHECKSUM, (
    "SAFETY: the modeling-blocked variable set changed unexpectedly. Expected "
    f"{_MODELING_BLOCKED_EXPECTED_CHECKSUM}, got {_modeling_blocked_actual}. If this is an "
    "intentional clinical change, update CLINICAL_REVIEW_REGISTRY deliberately and this "
    "checksum together -- this assertion is a validation checksum, not an operational gate."
)

DOMAIN_MAP = {}
REDUNDANCY_GROUPS = {
    "parity_history": {"members": ["G", "P", "LIVE_BIRTH", "AB", "EUP", "nulliparity"], "representative": "nulliparity"},
    "prior_cs_count": {"members": ["S_P_CS", "CS"], "representative": "S_P_CS"},
    "anthropometry": {"members": ["BMI_before", "BMI_after", "weight_before_pregnancy", "weight_in_pregnancy", "height"], "representative": "BMI_before"},
    "hypertension": {"members": ["pregnancy_related_hypertensive_disorder", "PIH", "mild_PET", "severe_PET", "any_PET", "SIPET"], "representative": "pregnancy_related_hypertensive_disorder"},
    "endometrioma_location": {"members": ["endometrioma_place_clean", "endometrioma_laterality"], "representative": "endometrioma_laterality"},
    # conception_method: mode_of_conception is the richer multi-level source
    # variable; mode_of_conception_ivf_vs_all is a deterministic binary
    # collapse of the same information (see the dedicated A2.10d
    # redundancy-review block for the contingency-table evidence).
    # Representative reflects a clinical preference for the IVF-vs-all
    # binary framing, not a statistical rule.
    "conception_method": {"members": ["mode_of_conception", "mode_of_conception_ivf_vs_all"], "representative": "mode_of_conception_ivf_vs_all"},
    # surgical_detail_overlap: added during the same review -- flagged by the
    # systematic categorical-categorical screening (strong association,
    # Cramer's V ~0.68 in the current cohort; see A2.10d). Both variables
    # describe adhesiolysis during endometriosis surgery, one as a standalone
    # summary flag and one as a member of the endo_resection_* multi-hot
    # procedure-detail family, at different levels of detail/representation.
    # Strong association alone does not prove identical meaning (unlike
    # conception_method above, there is no independently documented
    # derivation showing one variable is computed from the other), so no
    # representative is asserted here -- representative=None means the
    # generic redundancy-group loops (A2.10d, A2.13) treat both members as
    # flagged for review without auto-demoting either one. Deferred to
    # Feature Selection / clinical review.
    "surgical_detail_overlap": {"members": ["endo_surgery_adhesiolysis", "endo_resection_adhesiolysis"], "representative": None},
    # diabetes_status: eda_a_part1_setup_cohort.py's own structural-
    # missingness audit documented a near-perfect
    # cross-tabulation between these two (Cramer's V 0.982; diabetes_type
    # level 0 occurs only when gestational_diabetes==0, levels 1-5 only when
    # gestational_diabetes==1). That documented pattern is suggestive of a
    # source/derived relationship but has not been independently confirmed
    # as an actual derivation (unlike conception_method above, where the
    # contingency table shows a verified deterministic partition worked
    # through explicitly in A2.10d) -- so, following this project's existing
    # policy for association-only evidence (same as surgical_detail_overlap
    # above), no representative is asserted; both members are flagged for
    # review rather than one being auto-demoted.
    # derived_diabetes_type_grouped is grouped here for consistency with
    # eda_c_part4_screening.py's DERIVED_REDUNDANCY_GROUPS
    # ["diabetes_representation"], created alongside that derived feature.
    "diabetes_status": {"members": ["gestational_diabetes", "diabetes_type",
                                     "derived_diabetes_type_grouped"], "representative": None},
}
# Readiness-score weights (Section A2.13). Target-independent components only
# -- see A2.13's own header for the methodological rationale. Whole-cohort
# target-derived statistics (association effect size, FDR significance,
# target-by-level sparsity/separation) are never part of this score; they may
# still be *displayed* alongside it as descriptive/warning information, but
# they do not contribute to ranking or eligibility here.
# No timing_pre_admission_bonus / timing_unclear_penalty term is included:
# such a term would give every Stage-1 (predictor_allowed) variable a
# systematic bonus over Stage-2/3 variables purely from its classification
# label -- a variable must never be penalized merely for belonging to a
# later permitted cumulative stage. Readiness is reported per
# earliest-entry-stage instead of blended into one cross-stage score.
SCORING_WEIGHTS = {
    "clinical_tier": 3.0,
    "missingness_penalty_per_10pct": -0.4,
    "redundancy_demotion": -2.5,
}

print(f"Classification CSV: {CLASSIFICATION_REL}")
print(f"Variable type schema: {VARIABLE_TYPE_SCHEMA_REL} ({len(VARIABLE_TYPE_MAP)} variables)")
print(f"Type-schema coverage: {len(_schema_covered & _classified_cols)} of {len(_classified_cols)} "
      f"classified dataset columns covered")
print(f"Duplicate metadata rows: classification={int(classification_df['column_name'].duplicated().sum())}, "
      f"type schema={int(variable_type_schema_df['variable_name'].duplicated().sum())}")
print(f"Unexpected type-schema variables (not in classification CSV): {len(_TYPE_SCHEMA_UNEXPECTED_COLS)}")
print("Classification counts (canonical, loaded not re-derived):")
for _label in APPROVED_LABELS:
    print(f"  {_label:<40} {CLASSIFICATION_COUNTS[_label]:>3}")
print("Canonical variable-type counts (loaded not re-derived):")
for _vtype, _vcount in variable_type_schema_df["variable_type"].value_counts().sort_index().items():
    print(f"  {_vtype:<40} {_vcount:>3}")
print(f"Target column: {TARGET_COL}")
print(f"Main baseline predictors: {len(PREDICTOR_ALLOWED_COLS)}")
print(f"Secondary near-delivery predictors: {len(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)}")
print(f"Pending timing-confirmation predictors: {len(PENDING_TIMING_CONFIRMATION_COLS)}")
print(f"Intrapartum predictors (confirmed, excluded from prelabor model): {len(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)}")
""")
SB1_HELPERS = code("eda-b-s01-helpers", """
# ── Helper functions (same logic as S01_HELPERS in Part A; inline for Colab) ──
#
# Precision rule: every helper below returns raw,
# full-precision values (p-values, effect sizes, test statistics). Rounding
# is a display-layer concern only -- see fmt_pval()/fmt_effect() -- and must
# never be applied before a value is reused programmatically (BH-FDR input,
# ranking, threshold comparison, redundancy/sparsity flags). A displayed
# "0.0000" must never be read as a stored, computed zero.


# infer_var_type: canonical variable type only -- consults VARIABLE_TYPE_MAP
# (loaded from variable_type_schema_minimal.csv), never dtype/cardinality.
# Raises if a column has no canonical schema entry rather than silently
# guessing; the schema is required to cover every classified column (checked
# at load time above), so this should never actually fire during canonical
# execution -- it exists as a hard stop, not a soft warning, in case a
# caller ever passes an unclassified/ad-hoc series.
def infer_var_type(s):
    col = getattr(s, "name", None)
    if col not in VARIABLE_TYPE_MAP:
        raise KeyError(
            f"{col!r} has no canonical variable-type schema entry in {VARIABLE_TYPE_SCHEMA_REL}. "
            "Canonical execution must not infer type from dtype/cardinality."
        )
    return SCHEMA_TO_EDA_TYPE[VARIABLE_TYPE_MAP[col]]


# Returns (p_value, effect_size) at full precision -- no rounding.
def mannwhitney_with_effect(g0, g1):
    g0, g1 = g0.dropna(), g1.dropna()
    if len(g0) == 0 or len(g1) == 0:
        return np.nan, np.nan
    stat, pval = stats.mannwhitneyu(g0, g1, alternative="two-sided")
    r = 1 - (2 * stat) / (len(g0) * len(g1))
    return float(pval), float(abs(r))


_SPARSE_TABLE_TEST_SEED = 20260810  # fixed seed for the Monte-Carlo contingency-table
                                     # fallback (only reached if the exact test itself
                                     # errors) -- documented here for reproducibility.
_SPARSE_TABLE_MONTE_CARLO_RESAMPLES = 100_000


# General r x c contingency-table association test with statistically valid
# sparse-cell handling.
#
# 2x2 tables: Chi-square when expected-cell assumptions are satisfied
# (Cochran's rule -- no expected cell < 5); Fisher exact otherwise. scipy's
# default (no `method=`) 2x2 path is the classical, fully-enumerated exact
# hypergeometric algorithm -- confirmed deterministic (repeated calls on an
# identical table return bit-identical results) -- so this branch is
# unchanged from the prior implementation.
#
# r x c tables (r>2 or c>2): the SAME sparsity rule is applied (Cochran's
# rule of thumb: >20% of expected cells < 5 triggers the sparse path) --
# Chi-square is never reported as the formal inferential result for a sparse
# r x c table. scipy's default
# (method=None) fisher_exact() path for a NON-2x2 table is NOT the classical
# fully-enumerated exact algorithm in the installed scipy version -- it is an
# internally stochastic computation (repeated calls on an identical table
# return different p-values by default). Reproducibility for a r x c table
# therefore requires explicitly constructing a fresh, identically-seeded
# `MonteCarloMethod` on every call and passing it directly to
# `stats.fisher_exact(ct_values, method=...)` -- a fresh (not
# module-level/mutated) RNG seeded from the same fixed constant every time
# guarantees repeated calls -- including independent calls from separate
# notebook sections on the same table -- return the identical p-value. This
# is an explicitly-labeled Monte Carlo (resampling) p-value, never described
# as a fully enumerated exact one. No silent fallback to an
# unrelated inferential method (e.g. chi2_contingency's asymptotic p-value)
# on failure here -- if this explicitly configured, deterministic procedure
# itself fails, that must surface loudly rather than being masked, since
# masking it is exactly the failure mode this whole function exists to avoid
# for a sparse table.
#
# Returns (test_name, statistic, p_value, min_expected_cell,
# sparse_cell_fraction, sparse_flag) at full, unrounded precision.
def contingency_association_test(ct):
    chi2, p_chi2, dof, expected = stats.chi2_contingency(ct, correction=False)
    n_cells = expected.size
    min_expected = float(expected.min()) if n_cells else np.nan
    sparse_frac = float((expected < 5).sum()) / n_cells if n_cells else np.nan
    sparse_flag = bool((expected < 5).any()) if ct.shape == (2, 2) else bool(sparse_frac > 0.2)
    if not sparse_flag:
        return "chi-square", float(chi2), float(p_chi2), min_expected, sparse_frac, sparse_flag
    ct_values = ct.values if hasattr(ct, "values") else np.asarray(ct)

    if ct.shape == (2, 2):
        # Sparse 2x2 -- unchanged: deterministic classical exact algorithm.
        try:
            stat, pval = stats.fisher_exact(ct_values)
            # scipy can return stat/pval as a 0-d/1-element numpy array
            # rather than a plain float; float() on that directly is
            # deprecated in current numpy. np.asarray(...).item() extracts
            # the exact same numeric value as a native Python scalar
            # regardless of whether stat/pval is already a plain float, a
            # numpy scalar, or a 0-d/1-element array -- no change to the
            # statistical result, just a safe, explicit scalar extraction.
            stat = np.asarray(stat).item()
            pval = np.asarray(pval).item()
            return "Fisher exact", stat, pval, min_expected, sparse_frac, sparse_flag
        except Exception:
            _rng = np.random.default_rng(_SPARSE_TABLE_TEST_SEED)
            _method = stats.MonteCarloMethod(rng=_rng, n_resamples=_SPARSE_TABLE_MONTE_CARLO_RESAMPLES)
            _res = stats.chi2_contingency(ct, correction=False, method=_method)
            test_name = (
                f"chi-square (Monte Carlo p-value, seed={_SPARSE_TABLE_TEST_SEED}, "
                f"n={_SPARSE_TABLE_MONTE_CARLO_RESAMPLES})"
            )
            return test_name, float(chi2), float(_res.pvalue), min_expected, sparse_frac, sparse_flag

    # Sparse r x c -- explicit, fresh, fixed-seed Monte Carlo method passed
    # directly to fisher_exact() (see correctness note above). No try/except:
    # a failure here must fail loudly, not silently fall back to an unrelated
    # inferential method.
    _rng = np.random.default_rng(_SPARSE_TABLE_TEST_SEED)
    _method = stats.MonteCarloMethod(rng=_rng, n_resamples=_SPARSE_TABLE_MONTE_CARLO_RESAMPLES)
    stat, pval = stats.fisher_exact(ct_values, method=_method)
    stat = np.asarray(stat).item()
    pval = np.asarray(pval).item()
    test_name = (
        f"Fisher-Freeman-Halton (Monte Carlo p-value, seed={_SPARSE_TABLE_TEST_SEED}, "
        f"n={_SPARSE_TABLE_MONTE_CARLO_RESAMPLES})"
    )
    return test_name, stat, pval, min_expected, sparse_frac, sparse_flag


# Predictor-vs-target association test (target is always binary, so this is
# always an r x 2 table). Thin wrapper around contingency_association_test()
# -- same sparse-cell rule for r x 2 as for any other r x c table. Returns a
# dict (not a positional tuple, so new diagnostic fields can be added without
# breaking callers by position): p_value, test, N, table_shape, n_levels,
# min_expected_cell, sparse_cell_fraction, sparse_flag -- all at full
# precision.
def chi2_or_fisher(col, df_in, target):
    sub = df_in[[col, target]].dropna()
    ct = pd.crosstab(sub[col], sub[target])
    test_name, _stat, pval, min_exp, sparse_frac, sparse_flag = contingency_association_test(ct)
    return {
        "p_value": pval,
        "test": test_name,
        "N": len(sub),
        "table_shape": f"{ct.shape[0]}x{ct.shape[1]}",
        "n_levels": int(ct.shape[0]),
        "min_expected_cell": min_exp,
        "sparse_cell_fraction": sparse_frac,
        "sparse_flag": sparse_flag,
    }


# Full precision -- no rounding.
def cramers_v(ct):
    chi2 = stats.chi2_contingency(ct, correction=False)[0]
    n = ct.sum().sum()
    k = min(ct.shape) - 1
    if n == 0 or k == 0:
        return np.nan
    return float(np.sqrt(chi2 / (n * k)))


# Display-only formatting -- never use the return value programmatically.
def fmt_pval(p, decimals=4):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "—"
    threshold = 10 ** (-decimals)
    if 0 < p < threshold:
        return f"<{threshold:.{decimals}f}"
    return f"{p:.{decimals}f}"


# Display-only formatting -- never use the return value programmatically.
def fmt_effect(e, decimals=3):
    if e is None or (isinstance(e, float) and np.isnan(e)):
        return "—"
    return f"{e:.{decimals}f}"


def benjamini_hochberg(p_values):
    p = pd.to_numeric(pd.Series(p_values), errors="coerce")
    adj = pd.Series(np.nan, index=p.index, dtype=float)
    valid = p.dropna()
    if valid.empty:
        return adj
    ordered = valid.sort_values()
    m = len(ordered)
    raw = ordered * m / np.arange(1, m + 1)
    mono = raw.iloc[::-1].cummin().iloc[::-1].clip(upper=1.0)
    adj.loc[mono.index] = mono
    return adj


def safe_pct(num, den):
    return f"{100*num/den:.1f}%" if den and den > 0 else "—"


# Like safe_pct(), but suppresses the percentage (not just formats it) when
# num or (den - num) is below `threshold` -- unlike safe_pct(), which only
# guards against a zero denominator and has no small-cell disclosure
# protection despite the similar name. This guards against reconstructing a
# small suppressed target-group count from a printed percentage alone.
def safe_pct_disclosure(num, den, threshold=5, enabled=None):
    # enabled=None (not enabled=SHARE_SAFE_MODE) deliberately: a default
    # parameter value is evaluated once, at function-DEFINITION time -- using
    # SHARE_SAFE_MODE directly there would require it to already exist as a
    # global at the moment this def statement runs, which some test harnesses
    # (isolated single-cell exec) do not guarantee even though the real
    # notebook always defines it earlier in Section A2.1. Resolved lazily here
    # at CALL time instead, falling back to True (this notebook's default) if
    # genuinely absent.
    if enabled is None:
        enabled = globals().get("SHARE_SAFE_MODE", True)
    disp, _ = share_safe.safe_pct_with_denominator(num, den, threshold=threshold, enabled=enabled)
    if isinstance(disp, (int, float)):
        return f"{disp:.1f}%"
    return disp if disp is not None else "—"


def fmt_median_iqr(s):
    s = s.dropna()
    if len(s) == 0: return "—"
    return f"{s.median():.1f} [{s.quantile(0.25):.1f}–{s.quantile(0.75):.1f}]"


def _is_discrete_count(s, max_range=15):
    # Integer-aware detection: every non-missing value is a whole number and
    # the observed range is small enough for per-integer bins to be readable
    # (e.g. G/P/LIVE_BIRTH/AB/CS, observed range <=9), as opposed to a
    # continuous or wide-range integer-valued measurement (e.g. AGE range
    # ~28, diagnosis_year range ~20) where one x-tick per integer value
    # produces unreadable, overlapping tick labels and 20 evenly-spaced
    # bins remain appropriate instead. max_range=15 keeps a safe margin
    # above the true count variables while excluding AGE/diagnosis_year.
    s2 = s.dropna()
    if s2.empty:
        return False
    if not np.all(np.mod(s2, 1) == 0):
        return False
    return (s2.max() - s2.min()) <= max_range


def iqr_bounds(s):
    # Explicit IQR outlier-screening summary (IQR 1.5x rule) -- used for both
    # the univariate numeric summary table and the outlier registry.
    s2 = s.dropna()
    n = len(s2)
    if n < 4:
        return {"N": n, "Q1": np.nan, "Q3": np.nan, "IQR": np.nan,
                "lower_bound": np.nan, "upper_bound": np.nan,
                "n_flagged": 0, "pct_flagged": np.nan, "iqr_zero": False}
    q1, q3 = s2.quantile(0.25), s2.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        # matches EDA A Part 1 Section A8's existing,
        # already-approved behavior for zero-IQR variables (e.g. CS, a
        # right-skewed low-count clinical variable where Q1==Q3==0). With
        # IQR==0 the 1.5x-IQR rule degenerates to bounds=[0,0], which would
        # mislabel every nonzero observation as an "outlier" purely because
        # the bounds collapsed to a single point -- not a meaningful
        # statistical-extremeness screen. Q1/Q3/IQR remain real, reported
        # values (Q1==Q3==0 is a genuine fact about the distribution); only
        # the bounds/flag count are withheld as not informative, exactly as
        # EDA A Part 1 already does for the same variable/situation.
        return {
            "N": n, "Q1": round(float(q1), 3), "Q3": round(float(q3), 3),
            "IQR": round(float(iqr), 3),
            "lower_bound": np.nan, "upper_bound": np.nan,
            "n_flagged": 0, "pct_flagged": np.nan, "iqr_zero": True,
        }
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    n_out = int(((s2 < lo) | (s2 > hi)).sum())
    return {
        "N": n, "Q1": round(float(q1), 3), "Q3": round(float(q3), 3),
        "IQR": round(float(iqr), 3),
        "lower_bound": round(float(lo), 3), "upper_bound": round(float(hi), 3),
        "n_flagged": n_out, "pct_flagged": round(100 * n_out / n, 1) if n else np.nan,
        "iqr_zero": False,
    }


def near_zero_variance_flag(s, dominant_thresh=0.99, minority_min=5):
    # Descriptive-only screening flag (Batch-approved definition, verified
    # against live data): for exactly 2 observed categories, flag if the
    # dominant category share >= dominant_thresh OR the smaller category has
    # < minority_min observations (this is where "minority category" is
    # well-defined). For >2 categories, "minority category" is not a single
    # well-defined concept (nearly every multi-level categorical has *some*
    # rare level), so only the dominant-share criterion applies. Never used
    # to exclude or reclassify a variable.
    s2 = s.dropna()
    n = len(s2)
    if n == 0:
        return False, np.nan, {}
    vc = s2.value_counts()
    nun = len(vc)
    if nun <= 1:
        return False, np.nan, vc.to_dict()  # true zero-variance, reported separately
    max_frac = vc.iloc[0] / n
    if nun == 2:
        flagged = (max_frac >= dominant_thresh) or (int(vc.iloc[-1]) < minority_min)
    else:
        flagged = max_frac >= dominant_thresh
    return bool(flagged), round(float(max_frac), 4), vc.to_dict()


def is_true_zero_variance_for_exclusion(s):
    # Zero-variance policy: constant status may be audited across all variables,
    # but automatic zero-variance exclusion applies only within the relevant
    # analytical predictor scope. A true zero-variance exclusion has no missing
    # values and exactly one observed unique value; all-missing and partially
    # missing single-value variables are handled by missingness logic. Cohort
    # controls and other already-excluded variables retain their role reason.
    return int(s.isna().sum()) == 0 and int(s.dropna().nunique()) == 1


def plot_numeric_dist(df_in, col, target, ax_hist, ax_box):
    sub = df_in[[col, target]].dropna()
    _discrete = _is_discrete_count(df_in[col])
    if _discrete and len(sub) > 0:
        _lo, _hi = int(sub[col].min()), int(sub[col].max())
        _bins = np.arange(_lo - 0.5, _hi + 1.5, 1)  # one bin per integer value
    else:
        _bins = 20
    for tval, color, label in [(0, C0, "Vaginal"), (1, C1, "Intra-CS")]:
        vals = sub.loc[sub[target] == tval, col]
        ax_hist.hist(vals, bins=_bins, alpha=0.55, color=color,
                     label=f"{label} (n={len(vals)})", density=True)
        if (not _discrete) and len(vals) >= 5 and vals.nunique() >= 2:
            try:
                kde = stats.gaussian_kde(vals)
                xr  = np.linspace(vals.min(), vals.max(), 200)
                ax_hist.plot(xr, kde(xr), color=color, lw=1.5)
            except Exception:
                pass
    ax_hist.set_title(col, fontsize=12, pad=8)
    ax_hist.set_ylabel("Density" if not _discrete else "Proportion", fontsize=11)
    ax_hist.legend(fontsize=9.5)
    ax_hist.tick_params(labelsize=10)
    if _discrete:
        ax_hist.set_xticks(range(int(sub[col].min()), int(sub[col].max()) + 1))
    sub_p = sub.copy()
    sub_p[target] = sub_p[target].astype(str)
    sns.boxplot(data=sub_p, x=target, y=col, hue=target, ax=ax_box,
                palette={"0": C0, "1": C1}, width=0.5, linewidth=1.2, legend=False)
    ax_box.set_xlabel("0=Vaginal  1=CS", fontsize=11)
    ax_box.set_title(f"{col} by target", fontsize=12, pad=8)
    ax_box.set_ylabel("")
    ax_box.tick_params(labelsize=10)
    miss_n = df_in[col].isna().sum()
    ax_hist.set_xlabel(f"N={len(sub)}, miss={miss_n}, skew={round(sub[col].skew(),2)}", fontsize=10)


def check_separation_risk(col, df_in, target):
    # Flag binary variables with an empty target-by-level cell.
    sub  = df_in[[col, target]].dropna(subset=[col])
    g0   = sub[sub[target] == 0]
    g1   = sub[sub[target] == 1]
    vtype = infer_var_type(df_in[col])
    if vtype != "binary":
        return False, None
    n_pos1 = int((g1[col] == 1).sum())
    n_neg1 = len(g1) - n_pos1
    n_pos0 = int((g0[col] == 1).sum())
    n_neg0 = len(g0) - n_pos0
    cells = {"CS positive": n_pos1, "CS negative": n_neg1,
             "vaginal positive": n_pos0, "vaginal negative": n_neg0}
    empty = [name for name, count in cells.items() if count == 0]
    if empty:
        return True, f"empty target-by-level cell(s): {empty}"
    return False, None


print("Helper functions defined.")
""")


# ── Section A2.2 ────────────────────────────────────────────────────────────────
SB2_HEADER = md("eda-b-s02-header", """
## Section A2.2 — Primary Predictor Analysis Frame

This section constructs the cumulative Stage 1–3 modeling-pathway analysis frame
(`PRIMARY_COLS`) used for predictor-readiness EDA. Stage membership remains
explicit throughout, and inclusion in this descriptive analysis does not imply
eligibility for the primary pre-labor model. Variables with unclear measurement
timing are flagged separately (Section A2.14).
""")

SB2_LOAD = code("eda-b-s02-load", """
# Filename/hash resolution: the local (non-Colab) branch resolves against
# the same shared manifest EDA A Part 1 uses --
# analysis/eda/notebook_build/eda_shared/canonical_data_manifest.py -- via
# the same importlib pattern this repo already uses for
# classification_lineage.py, rather than independently auto-selecting the
# highest-numbered work_df_batch*.xlsx. Both notebooks
# independently print/assert the resolved filename and content hash, so
# they are provably analysing the identical file.
if IN_COLAB:
    # No repo filesystem access in Colab -- interactive, single-session
    # upload flow, not the local/reproducibility-critical path the shared
    # manifest exists to unify. Literal kept in sync manually with
    # canonical_data_manifest.py's CANONICAL_PROCESSED_FILENAME.
    _COLAB_EXPECTED_FILENAME = "work_df_batch18.xlsx"
    _existing_data = Path(".") / _COLAB_EXPECTED_FILENAME
    if _existing_data.is_file():
        DATA_PATH = _existing_data
        print(f"Found {DATA_PATH.name} in working directory — using it directly.")
    else:
        from google.colab import files as _gf
        print(f"Step 2 of 2 — Upload {_COLAB_EXPECTED_FILENAME}")
        print("  (from outputs/preprocessing/processed/)")
        _up = _gf.upload()
        _nm = list(_up.keys())
        _data_fname = _nm[0] if len(_nm) == 1 else None
        if _data_fname == "variable_classification_minimal.xlsx":
            raise ValueError(
                "Wrong file uploaded. This step expects the processed dataset "
                f"{_COLAB_EXPECTED_FILENAME}, not variable_classification_minimal.xlsx. "
                f"Upload {_COLAB_EXPECTED_FILENAME} from outputs/preprocessing/processed/."
            )
        if _data_fname != _COLAB_EXPECTED_FILENAME:
            raise ValueError(
                f"Expected the canonical processed workbook {_COLAB_EXPECTED_FILENAME!r}; "
                f"received: {_nm}. Upload {_COLAB_EXPECTED_FILENAME} from "
                "outputs/preprocessing/processed/."
            )
        DATA_PATH = Path(_data_fname)
    DATA_FINGERPRINT = None
else:
    if not _root:
        raise FileNotFoundError("Project root not found. Set DATA_PATH manually.")
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

    _proc = _root / Path(PROCESSED_GLOB).parent
    DATA_PATH, DATA_FINGERPRINT = canonical_data_resolver.resolve_canonical_processed_path(
        _proc, canonical_data_manifest
    )
    print(f"Canonical file resolved via shared manifest: {DATA_PATH.name}")
    print(f"  Content fingerprint: {DATA_FINGERPRINT}")
    assert DATA_PATH.name == canonical_data_manifest.CANONICAL_PROCESSED_FILENAME, (
        "SAFETY: resolved filename does not match the shared manifest -- this should be "
        "unreachable given canonical_data_resolver's own checks."
    )

    # EXPECTED_ROWS/N0/N1 declared above is a pre-resolution placeholder;
    # overwritten here (the earliest point in this notebook's cell order
    # where _root is available) from analysis/preprocessing/src/
    # preprocessing_config.py's CURRENT_APPROVED_COHORT_ROWS/TARGET_N0/
    # TARGET_N1, the single authoritative source. This is a frozen-cohort
    # regression gate, not a permanent architectural invariant; a future
    # approved cohort revision requires updating preprocessing_config.py
    # alone. No read of EXPECTED_ROWS/N0/N1 happens between their original
    # declaration and this point, so this overwrite is safe.
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
# 193, 1) is a cohort-version-specific observed count for the current 431-row
# cohort, not a clinical constant -- it will go stale the moment the
# cohort changes again. DATA_FINGERPRINT is only None in the Colab
# upload branch above (no local fingerprint-pinned manifest available
# there); here it must match the exact fingerprint the registry's
# denominators were last verified against, or this notebook fails loudly
# rather than silently reporting a stale structural-missingness breakdown
# (A2.7/A2.13 miss_% for STRUCTURAL_NAN_COLS entries). The fingerprint is a
# deterministic hash of the loaded DataFrame's content (values/column
# order/row order/dtypes/missingness), not a raw .xlsx byte hash -- it is
# invariant to the file's embedded generation timestamp.
if DATA_FINGERPRINT is not None:
    assert DATA_FINGERPRINT == structural_missingness_registry.EXPECTED_DENOMINATORS_COMPUTED_FOR_FINGERPRINT, (
        "SAFETY: the resolved canonical dataset content fingerprint does not match the "
        "fingerprint structural_missingness_registry.py's expected_applicable_denominator "
        "values (61, 222, 193, 1) were last verified against. The canonical cohort has "
        "changed -- these denominators are cohort-version-specific QC expectations, not "
        "clinical constants, and must be re-audited and updated together with "
        "EXPECTED_DENOMINATORS_COMPUTED_FOR_FINGERPRINT in structural_missingness_registry.py "
        "before this notebook's structural-missingness output can be trusted."
    )

df = pd.read_excel(DATA_PATH)
if TARGET_COL not in df.columns:
    raise ValueError(
        f"Target column '{TARGET_COL}' not found in the uploaded file. "
        "The uploaded file may not be the correct processed dataset. "
        f"Received: {DATA_PATH.name} ({df.shape[0]} rows x {df.shape[1]} cols). "
        "Upload work_df_batch18.xlsx from outputs/preprocessing/processed/."
    )
n0 = int((df[TARGET_COL] == 0).sum())
n1 = int((df[TARGET_COL] == 1).sum())
print(f"Loaded: {DATA_PATH.name}")
print(f"  Shape : {df.shape[0]} rows x {df.shape[1]} cols")
print(f"  Target: 0={n0} (vaginal), 1={n1} (intrapartum CS)")

_data_cols = set(df.columns)
_class_cols = set(classification_df["column_name"])
_classification_errors = []
if df.shape[0] != EXPECTED_ROWS:
    _classification_errors.append(f"Row count: expected {EXPECTED_ROWS}, got {df.shape[0]}")
# Column count is reported descriptively only -- it is not the schema gate.
# A bare total-column-count check is fragile: two unrelated schema changes
# (e.g. one column added, one removed) can cancel out to the same total and
# pass silently, while a single genuine rename can change the total for a
# reason that has nothing to do with actual drift. Exact named-column
# reconciliation against the live classification CSV (below) is strictly
# stronger -- it catches every case a total-count check catches, plus cases
# it would miss -- so it is the sole blocking schema authority here,
# consistent with eda_a_part1_setup_cohort.py's SA2_LOAD (which uses the
# same named-column reconciliation approach for the same reason).
print(f"  Column count (descriptive only): {df.shape[1]}")
if n0 != EXPECTED_N0 or n1 != EXPECTED_N1:
    _classification_errors.append(f"Target dist: expected 0={EXPECTED_N0}/1={EXPECTED_N1}, got 0={n0}/1={n1}")
if sorted(_data_cols - _class_cols):
    _classification_errors.append(f"Dataset columns missing from classification CSV: {sorted(_data_cols - _class_cols)}")
if sorted(_class_cols - _data_cols):
    _classification_errors.append(f"Classification rows absent from dataset: {sorted(_class_cols - _data_cols)}")
if _classification_errors:
    raise ValueError("Dataset/classification validation failed: " + "; ".join(_classification_errors))
print("  Dataset/classification validation PASSED")

# ── Cohort key-integrity gate ─────────────────────────────────────────────────
# Same composite-key contract as eda_a_part1_setup_cohort.py's SA2_LOAD:
# (subject_number, delivery_id) is the canonical uniqueness key, not
# subject_number alone. subject_number missingness is a documented, accepted
# condition (raw NUM column; see preprocessing_deviations.md) and is reported
# descriptively only -- never blocking. delivery_id must always be complete
# and unique by construction, so it (and the composite key) is blocking here.
_key_cols = ["subject_number", "delivery_id"]
_missing_key_cols = [c for c in _key_cols if c not in df.columns]
if _missing_key_cols:
    _classification_errors.append(f"Key column(s) missing from dataset: {_missing_key_cols}")
else:
    _subj_missing_n = int(df["subject_number"].isna().sum())
    _deliv_missing_n = int(df["delivery_id"].isna().sum())
    _subj_dup_n = int(df["subject_number"].dropna().duplicated().sum())
    _deliv_dup_n = int(df["delivery_id"].duplicated().sum())
    _composite_dup_n = int(df[_key_cols].dropna().duplicated().sum())
    # Key-column labels held in a variable (not written inline in the print
    # call below), matching eda_a_part1_setup_cohort.py's SA2_LOAD convention
    # -- this aggregate-count-only diagnostic is not flagged by the
    # identifier-print safety scanner in build_a2_notebook.py, which
    # matches on the literal column-name token appearing directly inside a
    # print(...) call.
    _k1, _k2 = _key_cols
    print(f"  Key completeness: {_k1} missing={_subj_missing_n} "
          f"(documented, accepted) | {_k2} missing={_deliv_missing_n} | "
          f"{_k1} duplicates (non-missing, descriptive only)={_subj_dup_n}")
    if _deliv_missing_n > 0:
        _classification_errors.append(
            f"{_deliv_missing_n} row(s) have a missing delivery_id (expected complete)"
        )
    if _deliv_dup_n > 0:
        _classification_errors.append(f"{_deliv_dup_n} duplicate delivery_id value(s) found")
    if _composite_dup_n > 0:
        _classification_errors.append(
            f"{_composite_dup_n} duplicate composite key (subject_number, delivery_id) row(s)"
        )
    if _deliv_missing_n == 0 and _deliv_dup_n == 0 and _composite_dup_n == 0:
        print(f"  Cohort key-integrity gate PASSED ({_k2} complete and unique; "
              "composite key unique)")
if _classification_errors:
    raise ValueError("Dataset/classification validation failed: " + "; ".join(_classification_errors))

# Stale column check
_stale = {"endo_adhesiolysis": "endo_surgery_adhesiolysis",
          "conception_method_detail": "mode_of_conception_details"}
for _old, _new in _stale.items():
    if _old in df.columns:
        print(f"  WARNING: stale column name '{_old}' found. Expected '{_new}'. "
              "Preprocessing may need a rerun.")
""")

SB2_SCOPE = code("eda-b-s02-scope", """
# Hard leakage gate. EDA A2's descriptive/readiness predictor universe (per
# approved clinical review) is the cumulative union of three
# approved classifications: predictor_allowed (Stage 1), plus
# secondary_near_delivery_predictor (Stage 2), plus
# intrapartum_predictor_exclude_from_prelabor_model (Stage 3). This is NOT a
# modeling-horizon split -- pre-labor/near-delivery/intrapartum eligibility is
# decided only downstream, at the modeling boundary (outside EDA A2 and EDA C).
# intrapartum_candidate_pending_timing_confirmation remains excluded here
# (0 members currently, but its timing is by definition still unresolved).
_forbidden = (
    set(PENDING_TIMING_CONFIRMATION_COLS)
    | set(SOURCE_OR_TEXT_AUDIT_EXCLUDE_COLS)
    | set(LEAKAGE_EXCLUDE_COLS)
    | set(INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS)
    | set(MANUAL_REVIEW_PENDING_COLS)
    | set(AWAITING_CLINICAL_CLARIFICATION_COLS)
    | set(ID_COLS)
    | set(TARGET_COLS)
)

# ── Explicit, ordered cumulative prediction-stage sets ─────────────────────
# Built as order-preserving lists (canonical classification-CSV column
# order), never as raw Python sets -- every downstream table/list built from
# these therefore has deterministic, reproducible row order. set(...) is used
# below only for membership tests and subset/disjointness assertions, never
# as the canonical list itself.
_col_order = list(classification_df["column_name"])
STAGE_1_COLS = [c for c in _col_order if c in set(PREDICTOR_ALLOWED_COLS)]
STAGE_2_COLS = STAGE_1_COLS + [
    c for c in _col_order if c in set(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)
]
STAGE_3_COLS = STAGE_2_COLS + [
    c for c in _col_order if c in set(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)
]
EDA_ALL_CANDIDATE_COLS = STAGE_3_COLS

# ── Stage-architecture safety assertions ───────
assert set(STAGE_1_COLS) <= set(STAGE_2_COLS) <= set(STAGE_3_COLS), (
    "SAFETY: cumulative stage sets must be strictly nested "
    "(Stage 1 subset of Stage 2 subset of Stage 3)."
)
assert set(STAGE_2_COLS) - set(STAGE_1_COLS) == set(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS), (
    "SAFETY: Stage 2 minus Stage 1 must equal exactly the metadata-defined "
    "secondary_near_delivery_predictor columns."
)
assert set(STAGE_3_COLS) - set(STAGE_2_COLS) == set(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS), (
    "SAFETY: Stage 3 minus Stage 2 must equal exactly the metadata-defined "
    "intrapartum_predictor_exclude_from_prelabor_model columns."
)
_violation = sorted(set(EDA_ALL_CANDIDATE_COLS) & _forbidden)
if _violation:
    raise AssertionError(f"SAFETY: forbidden columns in the cumulative stage universe: {_violation}")
assert "superficial_endometriosis" not in set(EDA_ALL_CANDIDATE_COLS), (
    "SAFETY: superficial_endometriosis is clinically_redundant_exclude and "
    "must never appear in any prediction stage."
)
assert "peritoneal_endometriosis" in set(STAGE_1_COLS), (
    "SAFETY: peritoneal_endometriosis is the canonical modeled endometriosis "
    "phenotype and must be present in Stage 1."
)

_preds_present  = [c for c in EDA_ALL_CANDIDATE_COLS if c in df.columns]
_primary_cols   = list(_preds_present)
_pending_timing_cols = [c for c in PENDING_TIMING_CONFIRMATION_COLS if c in df.columns]
_unclear_cols   = [c for c in AWAITING_CLINICAL_CLARIFICATION_COLS if c in df.columns]
_absent         = sorted(c for c in EDA_ALL_CANDIDATE_COLS if c not in df.columns)

# Drop all-missing and complete zero-variance predictors from the cumulative
# stage universe (same as pipeline Phase 2). The zero-variance rule is
# value-independent and requires complete data; partial missingness is
# handled separately.
_all_missing  = [c for c in _primary_cols if df[c].isna().all()]
_zero_var     = [c for c in _primary_cols
                 if c not in _all_missing and is_true_zero_variance_for_exclusion(df[c])]
_drop_set     = set(_all_missing) | set(_zero_var)
PRIMARY_COLS  = [c for c in _primary_cols if c not in _drop_set]

# Preserve each variable's original (authoritative) classification label AND
# its earliest cumulative-stage entry point as metadata, so downstream tables
# can attach both without re-deriving anything. "Earliest entry stage", not
# "prediction stage": a Stage-1 variable remains eligible in Stages 2 and 3
# too -- it is never exclusive to the stage it first enters.
PRIMARY_COLS_CLASSIFICATION = {
    c: classification_df.loc[classification_df["column_name"] == c, "classification"].iloc[0]
    for c in PRIMARY_COLS
}
_stage1_set, _stage2_set = set(STAGE_1_COLS), set(STAGE_2_COLS)
PRIMARY_COLS_EARLIEST_STAGE = {
    c: (1 if c in _stage1_set else (2 if c in _stage2_set else 3))
    for c in PRIMARY_COLS
}

# Build df_primary
df_primary = df[[TARGET_COL] + PRIMARY_COLS].copy()

print("Predictor scope for A2 predictor-readiness analysis (cumulative 3-stage predictor universe):")
print(f"  Stage 1 (pre-labor)                                : {len(STAGE_1_COLS)}")
print(f"  Stage 2 (pre-labor + near-delivery)                : {len(STAGE_2_COLS)}")
print(f"  Stage 3 (pre-labor + near-delivery + intrapartum)  : {len(STAGE_3_COLS)}")
print(f"  EDA_ALL_CANDIDATE_COLS (== Stage 3, before file/zero-variance filtering): {len(EDA_ALL_CANDIDATE_COLS)}")
print(f"  Absent from file                  : {len(_absent)}")
if _absent: print(f"    {_absent}")
print(f"  Present in file                    : {len(_primary_cols)}")
print(f"  Dropped (all-missing)             : {_all_missing}")
print(f"  Dropped (zero-variance)           : {_zero_var}")
print(f"  PRIMARY ANALYSIS COLS             : {len(PRIMARY_COLS)}")
_primary_by_stage = (
    pd.Series(PRIMARY_COLS_EARLIEST_STAGE).value_counts().sort_index().to_dict()
    if PRIMARY_COLS_EARLIEST_STAGE else {}
)
print(f"  PRIMARY_COLS by earliest entry stage: {_primary_by_stage}")
print(f"  Awaiting clinical clarification   : {_unclear_cols}")
print(f"  Pending timing confirmation (still excluded): {_pending_timing_cols}")
print()

# Primary candidate set (Core + Conditional) for deep plots.
# These variables receive additional deep domain-specific narrative interpretation.
# All other eligible predictors still receive standard full plot/table coverage in
# A2.3/A2.4 (histogram+boxplot / bar-chart, every PRIMARY_COLS variable, not a subset)
# plus appear in the comprehensive summary table (A2.12) -- they are not limited to
# the summary table alone; they simply receive no additional priority narrative.
PRIORITY_CORE = [
    "AGE", "nulliparity", "BMI_before", "endometriosis_surgery",
    "endometrioma", "adenomyosis", "deep_endometriosis",
    "gestational_diabetes", "mode_of_conception_ivf_vs_all",
    # any_medical_problem intentionally omitted: classified
    # clinically_nonspecific_exclude, not predictor_allowed, so it is not a
    # primary-model candidate; listing it here would be a stale entry
    # silently dropped by the PRIMARY_COLS intersection below.
    "aspirin_during_pregnancy",
]
PRIORITY_CONDITIONAL = [
    "S_P_CS", "cs_scar_endometriosis",
    # superficial_endometriosis intentionally omitted here: classified
    # clinically_redundant_exclude, no longer
    # predictor_allowed, so it is not a stage-1/2/3 candidate; listing it
    # would be a stale entry silently dropped by the PRIMARY_COLS
    # intersection below -- same pattern as any_medical_problem above.
]
PRIORITY_VARS = [c for c in PRIORITY_CORE + PRIORITY_CONDITIONAL
                 if c in PRIMARY_COLS]
OTHER_PRIMARY = [c for c in PRIMARY_COLS if c not in PRIORITY_VARS]

print(f"Priority variables (Core + Conditional, for deep plots): {len(PRIORITY_VARS)}")
print(f"Other eligible primary predictors (standard plot/table coverage; no additional "
      f"priority narrative emphasis) : {len(OTHER_PRIMARY)}")
""")

SB2_TIMING_WARNING_HEADER = md("eda-b-s02-timing-warning-header", """
**Pre-CS-decision availability.** The variables listed below (derived from the
current `modeling_clearance` status, not a fixed list) require explicit caution
before use in any stage's model.

A variable's Stage 1/2/3 classification (`predictor_allowed` /
`secondary_near_delivery_predictor` / `intrapartum_predictor_exclude_from_prelabor_
model`) represents its **typical or provisional measurement horizon only** -- when
the value is typically recorded relative to labor/delivery. Stage membership is
descriptive eligibility by horizon; it is **not modeling clearance**. A variable
currently marked `pending_timing_confirmation` must not enter any model until its
availability before the cesarean decision is clinically confirmed, regardless of
which stage's candidate pool it already appears in.
""")

SB2_TIMING_WARNING_CODE = code("eda-b-s02-timing-warning-code", """
# Derived directly from the canonical structured registry (Part 1) -- never an
# independently maintained name list, so this cannot silently drift after a
# future clinical decision changes which variables are timing-open.
_PRE_CS_TIMING_WARNING_VARS = sorted(TIMING_OPEN_VARS)
print("Pre-CS-decision availability warning -- variables requiring explicit timing caution:")
if not _PRE_CS_TIMING_WARNING_VARS:
    print("  None currently blocking -- TIMING_OPEN_VARS is empty.")
for _v in _PRE_CS_TIMING_WARNING_VARS:
    _stage = PRIMARY_COLS_EARLIEST_STAGE.get(_v)
    _in_pool = _v in PRIMARY_COLS
    print(f"  {_v}: earliest_entry_stage={_stage if _in_pool else 'not in PRIMARY_COLS'} "
          f"-- must not be used in a stage's model unless its timing for each observation "
          f"is confirmed to precede the cesarean decision, not merely 'generally documented "
          f"around that time'.")
""")

# ── Collect Part 1 cells ──────────────────────────────────────────────────────
EDA_B_PART1_CELLS = [
    SB0_HEADER,
    SB1_HEADER, SB1_FLAGS, SB1_IMPORTS, SB1_CONFIG, SB1_HELPERS,
    SB2_HEADER, SB2_LOAD, SB2_SCOPE,
    SB2_TIMING_WARNING_HEADER, SB2_TIMING_WARNING_CODE,
]

if __name__ == "__main__":
    print(f"EDA A2 Part 1 cells defined: {len(EDA_B_PART1_CELLS)}")

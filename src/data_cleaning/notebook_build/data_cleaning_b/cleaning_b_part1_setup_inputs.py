#!/usr/bin/env python3
"""Data Cleaning B — Part 1 cell definitions (sections B0–B1).

B0 — Purpose, safety rules, and methodology placement (Section 2: Data Cleaning).
B1 — Load inputs (work_df_batch18.xlsx + classification CSV), validate target/cohort,
     define the explicit cleaning scope, and initialise the cleaning logs.

This notebook is Section 2 of the data-science methodology. It runs AFTER the
initial EDA (A1 + A2) and produces a derived cleaned dataset. It never overwrites
the preprocessing output work_df_batch18.xlsx.
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
        "id": cid,
        "cell_type": "code",
        "metadata": {},
        "source": src(text),
        "outputs": [],
        "execution_count": None,
    }


# ── Section B0 ─────────────────────────────────────────────────────────────────
SB0_HEADER = md("clean-b-s00-header", """
# Data Cleaning B — Section 2 (After Initial EDA)
## Endometriosis & Intrapartum Cesarean Section — Sheba Medical Center

---

## Section B0 — Purpose and Safety Rules

### Methodology placement
This is **Section 2 — Data Cleaning**. It runs after the initial EDA stages:
- **A1** — `02_eda_a_initial_cohort_overview.ipynb` (cohort & inventory)
- **A2** — `02b_eda_a_initial_predictor_readiness.ipynb` (predictor-readiness EDA)

It produces a **derived cleaned dataset** that becomes the input for:
- **C** (Sections 3–5) — `04_eda_c_modeling_handoff.ipynb`

### What this notebook does
1. Loads the preprocessing output and the variable classification.
2. Defines an explicit **cleaning scope** (no blind processing of all 156 columns).
3. Handles missingness (row-level flags, column-level decisions, indicators).
4. Screens missingness associations with observed variables for manual review.
5. Runs a **descriptive, target-blind** extreme-value / distribution audit
   (Section B2 — 1.5×IQR screening + skewness, for detection only; discrete
   counts get logical non-negativity / integerness validation). No value is
   set to NaN, clipped, winsorized, capped, or otherwise mutated; no row is
   removed; the target column is not read. Data-quality sanity gates are owned
   by preprocessing, not by this audit.
6. Runs a **descriptive, target-blind** continuous transformation review
   (Section B3).
7. Plans transformations and type conversions (deterministic, rule-based only).
8. Produces an **imputation / treatment plan**. Data Cleaning B fits no
   learned parameter itself; approved methods are documented, and every
   learned / data-dependent parameter (a median, a quantile cutpoint) is
   fitted downstream inside modeling cross-validation training folds only.
9. Exports the cleaned dataset required by EDA C plus its full audit contract
   when `EXPORT_FOR_EDA_C = True`.

### What this notebook NEVER does
- **Never overwrites** `outputs/preprocessing/processed/work_df_batch18.xlsx`.
- Never trains a model or selects final features.
- Never runs global learned imputation. No learned imputer, median, or
  quantile cutpoint is fitted here; a global fit before the train/test split
  would leak held-out information into training rows.
- **Never deletes rows.** Row-level missingness is flag/audit only,
  unconditionally.
- **Never sets a value to NaN, clips, winsorizes, caps, or otherwise mutates a
  value based on an IQR / skewness / extreme-value screen, and never removes a
  row for statistical extremeness** — Section B2 is a descriptive, target-blind
  audit only; see
  `docs/finalization/outlier_extreme_value_handling_closure.md`.
- Never modifies the source `df` — all cleaning is applied to a copy `df_clean`.
- Never uses outcome / post-delivery / leakage variables as cleaning inputs.
- Never prints patient-level identifiers (`subject_number`, `delivery_id`).

*The chronology of architecture and classification changes over the project
is recorded in `docs/clinical_decisions/manual_decisions_log.md`; this
notebook describes only the final method.*

### Output safety
- `EXPORT_FOR_EDA_C = True` by default writes the derived B output required by EDA C.
- Cleaned dataset and patient-level logs are gitignored and never committed.
""")


# ── Section B1 ─────────────────────────────────────────────────────────────────
SB1_HEADER = md("clean-b-s01-header", """
## Section B1 — Load Inputs, Validate, and Define Cleaning Scope

### Inputs
- `work_df_batch18.xlsx` — preprocessing output (read-only source)
- `variable_classification_minimal.csv` — single source of truth for classification

### Cleaning scope (explicit, documented)
`CLEANING_SCOPE` is the union of four classification categories:
- `predictor_allowed` — primary pre-delivery predictor candidates
- `secondary_near_delivery_predictor` — allowed secondary pre-delivery variables
- `intrapartum_candidate_pending_timing_confirmation` — pending-timing candidates
  (currently 0 members)
- `intrapartum_predictor_exclude_from_prelabor_model` — Stage-3/intrapartum-only
  variables, retained here for cleaning/audit only. **Being retained/cleaned in
  Data Cleaning B does not make a Stage-3 or intrapartum-only variable eligible
  for an earlier prediction horizon** — horizon eligibility is a separate,
  downstream decision.

The target column is carried **separately** alongside `CLEANING_SCOPE` — it is
never itself a predictor and is never cleaned as a feature.

Explicitly **excluded** from cleaning scope:
- `leakage_exclude`, `intrapartum_or_post_delivery_exclude`
- `source_or_text_audit_exclude`, `cohort_control_exclude`
- `clinically_nonspecific_exclude`, `clinically_redundant_exclude`
- `manual_review_pending`, `awaiting_clinical_clarification`, `id`

Row/column missingness rules are computed **within scope only** — not blindly over
all 156 columns (many of which are structurally not-applicable).
""")

SB1_FLAGS = code("clean-b-s01-flags", """
# ── Cleaning control flags ─────────────────────────────────────────────────────
# APPLY_ROW_EXCLUSIONS / EXECUTE_LEARNED_IMPUTATION: inert. Data Cleaning B
# never deletes a row and never fits a learned imputer; no code path reads
# either flag. Both are retained only for backward-compatible manifest schema
# (ROW_EXCLUSIONS_APPLIED is always False). Section B4 (cell clean-b-s04-row)
# holds the audit-only row-flagging that replaced row exclusion.
APPLY_ROW_EXCLUSIONS = False        # inert -- no operational effect
EXECUTE_LEARNED_IMPUTATION = False  # inert -- no learned imputation runs in Data Cleaning B
EXPORT_FOR_EDA_C = True             # if True, write the cleaned B dataset + audit contract for EDA C

# ── Missingness thresholds (within cleaning scope) ────────────────────────────
ROW_MISSING_FLAG_FRACTION = 0.50    # row flagged if >50% of scope cols missing
# COL_MISSING_HIGH (>=70%) and COL_MISSING_MID (40-70%) are audit/review tiers
# only. Crossing either band never automatically deletes a source column from
# the cleaned export and never automatically creates a categorical / unknown
# conversion or missingness indicator for it -- every representation and every
# model-eligibility decision is made explicitly, per variable, downstream. See
# Section B4 (cells clean-b-s04-column, clean-b-s04d-*).
COL_MISSING_HIGH = 0.70            # >=70% -> flag/document for audit only
COL_MISSING_MID = 0.40            # 40-70% -> audit/review tier only

print(f"APPLY_ROW_EXCLUSIONS       = {APPLY_ROW_EXCLUSIONS} (inert)")
print(f"EXECUTE_LEARNED_IMPUTATION = {EXECUTE_LEARNED_IMPUTATION} (inert)")
print(f"EXPORT_FOR_EDA_C           = {EXPORT_FOR_EDA_C}")
""")

SB1_IMPORTS = code("clean-b-s01-imports", """
import pandas as pd
import numpy as np
import matplotlib
if "google.colab" not in dir() and "get_ipython" not in dir():
    # Non-interactive backend outside Jupyter/Colab -- prevents plt.show() from
    # blocking on a GUI event loop when this notebook's cells are executed as a
    # plain script (e.g. via nbconvert --execute or an exec-based runner).
    # Jupyter/Colab both provide get_ipython(), so this leaves the normal inline
    # backend untouched when actually run as a notebook.
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path
import sys, os, re, hashlib, zipfile, warnings, json, importlib.util
from datetime import datetime as _dt, timezone as _tz

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
warnings.filterwarnings("ignore", category=FutureWarning)

pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 200)
pd.set_option("display.float_format", "{:.3f}".format)
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.05)
matplotlib.rcParams["figure.dpi"] = 90
_MUTED = sns.color_palette("muted")
_C0, _C1 = _MUTED[0], _MUTED[3]

IN_COLAB = "google.colab" in sys.modules
""")

SB1_LOAD_CLASSIFICATION = code("clean-b-s01-load-classification", """
# ── Locate and parse the variable classification CSV ──────────────────────────
CLASSIFICATION_REL = "outputs/preprocessing/audit/variable_classification_minimal.csv"
APPROVED_LABELS = [
    "id", "target", "predictor_allowed", "secondary_near_delivery_predictor",
    "intrapartum_candidate_pending_timing_confirmation",
    "intrapartum_predictor_exclude_from_prelabor_model",
    "source_or_text_audit_exclude", "cohort_control_exclude",
    "clinically_nonspecific_exclude", "clinically_redundant_exclude",
    "leakage_exclude",
    "intrapartum_or_post_delivery_exclude", "manual_review_pending",
    "awaiting_clinical_clarification",
]
# EXPECTED_CLASSIFICATION_COUNTS is a regression gate: the classification CSV
# must contain exactly these per-label counts (156 variables total). The
# classification of individual variables evolved through the project as
# clinical timing was confirmed with the data owner; that per-variable
# chronology is in docs/clinical_decisions/manual_decisions_log.md and is not
# reproduced here. A future approved classification change updates the CSV and
# these expected counts together.
EXPECTED_CLASSIFICATION_COUNTS = {
    "id": 2, "target": 1, "predictor_allowed": 60,
    "secondary_near_delivery_predictor": 6,
    "intrapartum_candidate_pending_timing_confirmation": 0,
    "intrapartum_predictor_exclude_from_prelabor_model": 5,
    "source_or_text_audit_exclude": 31,
    "cohort_control_exclude": 3,
    "clinically_nonspecific_exclude": 2,
    "clinically_redundant_exclude": 1,
    "leakage_exclude": 8, "intrapartum_or_post_delivery_exclude": 37,
    "manual_review_pending": 0, "awaiting_clinical_clarification": 0,
}
# The pending-timing-confirmation category is formally defined but currently
# has zero members (all its variables' clinical timing has been confirmed).
EXPECTED_PENDING_TIMING_CONFIRMATION_COLS = []

# Stage-3 / intrapartum-horizon variables. Retained in the cleaning scope for
# cleaning and audit, but eligible only for the dynamic intrapartum prediction
# horizon downstream, never for a pre-labor model.
# gestational_age_at_delivery_days: its value is the completed gestational age
# at the actual delivery, so it is not knowable at Stage 1/2 -- Stage-3 only.
EXPECTED_INTRAPARTUM_PREDICTOR_EXCLUDE_COLS = [
    "meconium_stained_amniotic_fluid",
    "induction_any_bin",
    "indication_for_induction_clean",
    "intrapartum_fever_or_chorioamnionitis_bin",
    "gestational_age_at_delivery_days",
]

# Secondary near-delivery variables: genuinely available before or at
# admission for labor, but reserved for secondary near-delivery analyses
# rather than the primary pre-labor predictor model. They remain in the
# cleaning scope (cleaned and imputation-eligible), just not primary-model
# eligible.
#   - weight_in_pregnancy: non-standardized, generally self-reported
#     measurement timing (not confirmed leakage).
#   - BMI_after: formula-derived from weight_in_pregnancy and height, a
#     pregnancy-time measurement pair. Passed through unchanged here (no
#     categorization, no imputation, no missingness indicator); its
#     modeling representation is BMI_after_cat (Section B5b).
EXPECTED_SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS = [
    "PPROM",
    "gestational_age_at_PPROM_days",
    "placental_abruption",
    "Hb_before_delivery",
    "weight_in_pregnancy",
    "BMI_after",
]


def _find_project_root():
    starts = []
    if "__file__" in dir():
        starts.append(Path(__file__).resolve().parent)
    starts.append(Path.cwd().resolve())
    for start in starts:
        p = start if start.is_dir() else start.parent
        for _ in range(10):
            if (p / CLASSIFICATION_REL).is_file() or (p / "CLAUDE.md").is_file():
                return p
            if p.parent == p:
                break
            p = p.parent
    return None


_root = _find_project_root()

# Repository-root-anchored canonical path only. A CWD-local
# `variable_classification_minimal.csv` does not take precedence: this cell's
# classification_df and the lineage snapshot
# (classification_lineage.start_data_cleaning_b_snapshot) must resolve to the
# same file, so both read only the root-anchored canonical path. Fails loudly
# rather than silently falling back to a local file.
if _root is None:
    raise FileNotFoundError(
        "Could not resolve the repository root (no CLASSIFICATION_REL or "
        "CLAUDE.md found in any parent directory). Run this notebook from "
        "within the project repository."
    )
CLASSIFICATION_PATH = _root / CLASSIFICATION_REL
if not CLASSIFICATION_PATH.is_file():
    raise FileNotFoundError(f"Classification CSV not found: {CLASSIFICATION_PATH}")


def _rel(path):
    # Display-only helper: render a path as a repository-relative POSIX string
    # for reader-facing output, instead of an absolute local machine path.
    # Never used for file I/O -- the real Path objects are unchanged.
    try:
        return Path(path).resolve().relative_to(_root.resolve()).as_posix()
    except (ValueError, AttributeError):
        return str(path)


def _parse_classification_csv(path):
    cls = pd.read_csv(path)
    required = ["column_name", "classification", "reason"]
    missing_cols = [c for c in required if c not in cls.columns]
    if missing_cols:
        raise ValueError(f"Classification CSV missing required columns: {missing_cols}")
    cls = cls[required].copy()
    for c in required:
        cls[c] = cls[c].astype("string").str.strip()
    errors = []
    if len(cls) != 156:
        errors.append(f"expected 156 rows, got {len(cls)}")
    dupes = cls.loc[cls["column_name"].duplicated(), "column_name"].dropna().tolist()
    if dupes:
        errors.append(f"duplicate column_name values: {dupes}")
    unexpected = sorted(set(cls["classification"].dropna()) - set(APPROVED_LABELS))
    if unexpected:
        errors.append(f"unexpected classification labels: {unexpected}")
    counts = cls["classification"].value_counts().reindex(APPROVED_LABELS, fill_value=0).to_dict()
    if counts != EXPECTED_CLASSIFICATION_COUNTS:
        errors.append(f"classification count mismatch: expected {EXPECTED_CLASSIFICATION_COUNTS}, got {counts}")
    pending_cols = cls.loc[
        cls["classification"] == "intrapartum_candidate_pending_timing_confirmation",
        "column_name",
    ].tolist()
    if len(pending_cols) != len(EXPECTED_PENDING_TIMING_CONFIRMATION_COLS) or set(pending_cols) != set(EXPECTED_PENDING_TIMING_CONFIRMATION_COLS):
        errors.append(
            "pending timing confirmation columns mismatch: "
            f"expected {EXPECTED_PENDING_TIMING_CONFIRMATION_COLS}, got {pending_cols}"
        )
    intrapartum_predictor_cols = cls.loc[
        cls["classification"] == "intrapartum_predictor_exclude_from_prelabor_model",
        "column_name",
    ].tolist()
    if (
        len(intrapartum_predictor_cols) != len(EXPECTED_INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)
        or set(intrapartum_predictor_cols) != set(EXPECTED_INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)
    ):
        errors.append(
            "intrapartum_predictor_exclude_from_prelabor_model columns mismatch: "
            f"expected {EXPECTED_INTRAPARTUM_PREDICTOR_EXCLUDE_COLS}, got {intrapartum_predictor_cols}"
        )
    secondary_cols = cls.loc[
        cls["classification"] == "secondary_near_delivery_predictor",
        "column_name",
    ].tolist()
    if (
        len(secondary_cols) != len(EXPECTED_SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)
        or set(secondary_cols) != set(EXPECTED_SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)
    ):
        errors.append(
            "secondary_near_delivery_predictor columns mismatch: "
            f"expected {EXPECTED_SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS}, got {secondary_cols}"
        )
    if errors:
        raise ValueError("Invalid classification CSV: " + "; ".join(errors))
    return cls


classification_df = _parse_classification_csv(CLASSIFICATION_PATH)


def _cols_for(label):
    return classification_df.loc[
        classification_df["classification"] == label, "column_name"
    ].tolist()


ID_COLS = _cols_for("id")
TARGET_COL = _cols_for("target")[0]
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

# Structural-NaN columns: NaN is expected by design (do not impute blindly).
#
# Project/clinical decision: all endo_resection_* base variables represent
# endometriosis surgery/resection subgroup fields. Their missingness is
# considered structural/subgroup missingness and should not be treated as
# ordinary random missingness.
ENDO_RESECTION_STRUCTURAL_COLS = sorted([
    c for c in (PREDICTOR_ALLOWED_COLS + SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)
    if c.startswith("endo_resection_") and not c.endswith("__missing_ind")
])
# diabetes_type is NOT included here: it is 0% missing in the cohort and has
# no subgroup-masking logic in preprocessing, so there is no missingness for a
# structural flag to explain.
#
# ── CONFIRMED vs. PENDING structural missingness ─────────────────────────────
# Two tiers are kept distinct:
#   CONFIRMED_STRUCTURAL -- endometrioma_size_clean/place_clean/laterality,
#     ENDO_RESECTION_STRUCTURAL_COLS, endo_surgery_adhesiolysis: each has a
#     documented, code-enforced subgroup gate in preprocessing.
#   APPLICABILITY_LINKED_NO_PREPROCESSING_MASK -- gestational_age_at_PPROM_days,
#     indication_for_induction_clean: empirically gated in the current cohort
#     but with NO code-enforced subgroup gate.
# Only CONFIRMED columns receive whole-column structural privileges (exemption
# from the row-level >50%-missingness denominator, structural_nan=True, a
# "structural" tier, a "structural/subgroup missingness" mechanism label).
# Both tiers are read from the shared registry
# (analysis/eda/notebook_build/eda_shared/structural_missingness_registry.py),
# which A1/A2 also use, so all three notebooks agree.
#
# The NaN->0 recode below (Section B1c) only ever targets
# ENDO_RESECTION_RECODE_COLS -- it never touches either pending column.
_smr_spec = importlib.util.spec_from_file_location(
    "structural_missingness_registry",
    _root / "analysis" / "eda" / "notebook_build" / "eda_shared" / "structural_missingness_registry.py",
)
structural_missingness_registry = importlib.util.module_from_spec(_smr_spec)
_smr_spec.loader.exec_module(structural_missingness_registry)

# Source of truth: the public shared registry (structural_nan_cols()),
# filtered to columns relevant to Data Cleaning B's cleaning scope (the same
# four classification categories CLEANING_SCOPE unions in Section B1;
# CLEANING_SCOPE is not yet built at this point, so the equivalent column set
# is reconstructed here from the *_COLS lists loaded above). The same public
# function is used below for APPLICABILITY_LINKED_NO_PREPROCESSING_MASK_COLS, so both tiers
# come from one shared source.
_dcb_in_scope_cols = (
    set(PREDICTOR_ALLOWED_COLS) | set(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)
    | set(PENDING_TIMING_CONFIRMATION_COLS) | set(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)
)
CONFIRMED_STRUCTURAL_NAN_COLS = [
    c for c in structural_missingness_registry.structural_nan_cols()
    if c in _dcb_in_scope_cols
]

# gestational_age_at_PPROM_days, indication_for_induction_clean,
# adenomyosis_sonographic_features_clean: no preprocessing-enforced subgroup
# gate exists for any of the three, so none qualifies for
# CONFIRMED_STRUCTURAL_NAN_COLS. See ROW_APPLICABILITY_GATES below for the
# row-level treatment Data Cleaning B applies to them instead.
APPLICABILITY_LINKED_NO_PREPROCESSING_MASK_COLS = list(structural_missingness_registry.applicability_linked_cols())
APPLICABILITY_LINKED_NO_PREPROCESSING_MASK_REASONS = dict(structural_missingness_registry.APPLICABILITY_LINKED_NO_PREPROCESSING_MASK)

# STRUCTURAL_NAN_COLS now means CONFIRMED-only (never the pending tier). This
# is the one name consumed throughout Sections B2/B3/B6 for every WHOLE-COLUMN
# structural privilege (denominator exemption, tier, mechanism-label override)
# -- the registered row-applicability-gated variables below are deliberately
# NOT included, so they can no longer receive a whole-column privilege by
# accident.
STRUCTURAL_NAN_COLS = list(CONFIRMED_STRUCTURAL_NAN_COLS)

# ── Row-specific applicability gates (verified directly against the current ──
# 431-row dataset, not assumed from variable names).
# None of the registered variables is whole-column structural nor whole-column
# ordinary missingness: applicability is known PER ROW from an explicit
# event-status variable in the dataset, with zero inconsistent rows for any of
# them (0 rows with PPROM==0 and an observed gestational_age_at_PPROM_days
# value; 0 rows with induction_any_bin==0 and a documented
# indication_for_induction_clean value; 0 rows with adenomyosis==0 and an
# observed adenomyosis_sonographic_features_clean value).
#   - gestational_age_at_PPROM_days: applicable iff PPROM == 1 (of the 17
#     PPROM==1 rows, 16 observed / 1 missing).
#   - indication_for_induction_clean: applicable iff induction_any_bin == 1
#     (of the 194 induction_any_bin==1 rows, 190 observed / 4 missing).
#     induction_any_bin (not the raw induction_of_labor/start_of_labor
#     columns) is this project's canonical derived applicability flag.
#   - adenomyosis_sonographic_features_clean: applicable iff adenomyosis == 1
#     (of the 169 adenomyosis==1 rows, 130 observed / 39 genuinely missing =
#     23.1% within the applicable subgroup). The raw whole-cohort rate (69.8%)
#     conflates structural not-applicability with genuine documentation gaps.
#     Feeds the multi-hot representation in Section B5f
#     (adenomyosis_feature_1..11 + adenomyosis_features_unknown).
ROW_APPLICABILITY_GATES = {
    "gestational_age_at_PPROM_days": {"gate_column": "PPROM", "applicable_value": 1},
    "indication_for_induction_clean": {"gate_column": "induction_any_bin", "applicable_value": 1},
    "adenomyosis_sonographic_features_clean": {"gate_column": "adenomyosis", "applicable_value": 1},
}


def row_applicability_mask(df_source, col):
    # True for rows where `col` is applicable (per ROW_APPLICABILITY_GATES),
    # else False. Columns without a registered gate are applicable to every
    # row (ordinary variables).
    gate = ROW_APPLICABILITY_GATES.get(col)
    if gate is None:
        import pandas as _pd
        return _pd.Series(True, index=df_source.index)
    return df_source[gate["gate_column"]] == gate["applicable_value"]


print(f"CONFIRMED_STRUCTURAL_NAN_COLS: {len(CONFIRMED_STRUCTURAL_NAN_COLS)} columns")
print(f"ROW_APPLICABILITY_GATES: {ROW_APPLICABILITY_GATES} -- applicability is "
      "determined per row from these gate columns, not from a whole-column "
      "label; see Sections B2/B3/B6 for how this is used.")

# ── Cesarean-subgroup applicability registry ────────────────────────────────
# A small registry, separate from STRUCTURAL_NAN_COLS above, for a few
# variables that are applicable only to the cesarean subgroup and are outside
# CLEANING_SCOPE -- just enough metadata to report them correctly, using the
# set_outside_subgroup_to_na masking already applied in preprocessing. The
# intrapartum_cesarean entries have expected_applicable_denominator 61
# (target_intrapartum_cs==1 count for the current 431-row cohort); the
# age_at_neonatal_death entry uses the neonatal_death==1 subgroup (denominator 1).
SUBGROUP_APPLICABLE_COLS = {
    "adhesions": {
        "subgroup_rule": "type_of_CS.isin([2, 3])",
        "subgroup_label": "intrapartum_cesarean",
        "expected_applicable_denominator": 61,
        "structural_missing_interpretation": (
            "NaN outside the cesarean subgroup is structural (not applicable "
            "to vaginal deliveries), not ordinary missing data."
        ),
    },
    "surgical_site_infection": {
        "subgroup_rule": "type_of_CS.isin([2, 3])",
        "subgroup_label": "intrapartum_cesarean",
        "expected_applicable_denominator": 61,
        "structural_missing_interpretation": (
            "NaN outside the cesarean subgroup is structural (not applicable "
            "to vaginal deliveries) -- NOT confirmed absence of infection, "
            "not ordinary missing data."
        ),
    },
    # suspected_endo_lesions_during_CS_clean, abdominal_cavity_findings,
    # other_surgery_complications: outside CLEANING_SCOPE (leakage_exclude),
    # never touched by the missingness handling. This registry only drives the
    # separate cesarean-subgroup applicability report (Section B4), read before
    # CLEANING_SCOPE restricts the exported columns.
    # suspected_endo_lesions_during_CS_clean is the subgroup-masked
    # (leakage_exclude) canonical variable, guaranteed NaN outside the cesarean
    # subgroup by construction (set_outside_subgroup_to_na in preprocessing),
    # unlike the untouched raw suspected_endo_lesions_during_CS.
    "suspected_endo_lesions_during_CS_clean": {
        "subgroup_rule": "type_of_CS.isin([2, 3])",
        "subgroup_label": "intrapartum_cesarean",
        "expected_applicable_denominator": 61,
        "structural_missing_interpretation": (
            "NaN outside the cesarean subgroup is structural (not applicable "
            "to vaginal deliveries), not ordinary missing data."
        ),
    },
    "abdominal_cavity_findings": {
        "subgroup_rule": "type_of_CS.isin([2, 3])",
        "subgroup_label": "intrapartum_cesarean",
        "expected_applicable_denominator": 61,
        "structural_missing_interpretation": (
            "NaN outside the cesarean subgroup is structural (not applicable "
            "to vaginal deliveries), not ordinary missing data."
        ),
    },
    "other_surgery_complications": {
        "subgroup_rule": "type_of_CS.isin([2, 3])",
        "subgroup_label": "intrapartum_cesarean",
        "expected_applicable_denominator": 61,
        "structural_missing_interpretation": (
            "NaN outside the cesarean subgroup is structural (not applicable "
            "to vaginal deliveries), not ordinary missing data."
        ),
    },
    # blood_loss_during_surgery: outside CLEANING_SCOPE (leakage_exclude); this
    # registry only drives the separate cesarean-subgroup applicability report
    # (Section B4).
    "blood_loss_during_surgery": {
        "subgroup_rule": "type_of_CS.isin([2, 3])",
        "subgroup_label": "intrapartum_cesarean",
        "expected_applicable_denominator": 61,
        "structural_missing_interpretation": (
            "NaN outside the cesarean subgroup is structural (not applicable "
            "to vaginal deliveries), not ordinary missing data."
        ),
    },
    # age_at_neonatal_death: applicable only when neonatal_death == 1 (n=1 in
    # the current cohort) -- a different subgroup rule from the cesarean-subgroup
    # entries above, same registry mechanism. Outside CLEANING_SCOPE
    # (intrapartum_or_post_delivery_exclude); drives the separate applicability
    # report (Section B4) only.
    "age_at_neonatal_death": {
        "subgroup_rule": "neonatal_death == 1",
        "subgroup_label": "neonatal_death",
        "expected_applicable_denominator": 1,
        "structural_missing_interpretation": (
            "NaN outside the neonatal_death==1 subgroup is structural (not "
            "applicable when there was no neonatal death), not ordinary "
            "missing data. Within the applicable subgroup, a still-missing "
            "value would be genuine missingness, distinct from the "
            "structural NaN outside it."
        ),
    },
}

print(f"Classification CSV: {CLASSIFICATION_PATH.name}")
print(f"  Loaded from: {_rel(CLASSIFICATION_PATH)}")
print(f"Target column: {TARGET_COL}")
print(f"predictor_allowed: {len(PREDICTOR_ALLOWED_COLS)} | "
      f"secondary_near_delivery: {len(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)} | "
      f"pending_timing_confirmation: {len(PENDING_TIMING_CONFIRMATION_COLS)} | "
      f"intrapartum_predictor_exclude_from_prelabor_model: {len(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)}")
print("endo_resection structural/subgroup columns: "
      f"{len(ENDO_RESECTION_STRUCTURAL_COLS)}")
""")

SB1_CLASSIFICATION_LINEAGE_INIT = code("clean-b-s01-classification-lineage-init", """
# ── Classification-lineage: fresh Data Cleaning B working snapshot ────────────
# Starts from the immutable preprocessing classification files, never from a
# Data-Cleaning-B-saved snapshot -- see
# analysis/classification_lineage/classification_lineage.py for the shared
# fresh-copy + register_feature() infrastructure EDA C also uses.
_cl_module_path = _root / "analysis" / "classification_lineage" / "classification_lineage.py"
_cl_spec = importlib.util.spec_from_file_location("classification_lineage", _cl_module_path)
classification_lineage = importlib.util.module_from_spec(_cl_spec)
_cl_spec.loader.exec_module(classification_lineage)

dcb_classification_snapshot, dcb_type_schema_snapshot = classification_lineage.start_data_cleaning_b_snapshot(root=_root)
print("Classification-lineage snapshot initialised from the immutable preprocessing "
      f"files: {len(dcb_classification_snapshot)} classification rows, "
      f"{len(dcb_type_schema_snapshot)} type-schema rows.")
""")

SB1_LOAD_DATA = code("clean-b-s01-load-data", """
# ── Load the preprocessing output (read-only source) ──────────────────────────
# The frozen-cohort baseline (expected row / target counts) is loaded from the
# single authoritative source,
# analysis/preprocessing/src/preprocessing_config.py's
# CURRENT_APPROVED_COHORT_ROWS / TARGET_N0 / TARGET_N1 -- a frozen-cohort
# regression gate; a future approved cohort revision updates that file alone.
_ppcfg_spec = importlib.util.spec_from_file_location(
    "preprocessing_config", _root / "analysis" / "preprocessing" / "src" / "preprocessing_config.py"
)
_preprocessing_config = importlib.util.module_from_spec(_ppcfg_spec)
_ppcfg_spec.loader.exec_module(_preprocessing_config)
EXPECTED_ROWS = _preprocessing_config.CURRENT_APPROVED_COHORT_ROWS
EXPECTED_N0 = _preprocessing_config.CURRENT_APPROVED_TARGET_N0
EXPECTED_N1 = _preprocessing_config.CURRENT_APPROVED_TARGET_N1
SOURCE_BATCH_NAME = "work_df_batch18.xlsx"
PROCESSED_SUBPATH = "outputs/preprocessing/processed"

# This notebook reads batch18 and must NEVER write to PROCESSED_SUBPATH.
# Repository-root-anchored canonical path only: a CWD-local work_df_batch18.xlsx
# does not take precedence over the canonical preprocessing output. Fails
# loudly rather than silently selecting a same-named local workbook.
if _root is None:
    raise FileNotFoundError(
        "Could not resolve the repository root. Run this notebook from "
        "within the project repository."
    )
DATA_PATH = _root / PROCESSED_SUBPATH / SOURCE_BATCH_NAME
if not DATA_PATH.is_file():
    raise FileNotFoundError(
        f"Source dataset '{SOURCE_BATCH_NAME}' not found at the canonical path: {DATA_PATH}"
    )
if not zipfile.is_zipfile(DATA_PATH):
    raise ValueError(f"Not a valid .xlsx file: {DATA_PATH.name}")

df = pd.read_excel(DATA_PATH)
if "Unnamed: 0" in df.columns:
    df = df.drop(columns=["Unnamed: 0"])

# ── Provenance manifest (input) ───────────────────────────────────────────────
_h = hashlib.sha256()
with open(DATA_PATH, "rb") as _fh:
    for _block in iter(lambda: _fh.read(1 << 20), b""):
        _h.update(_block)
INPUT_SHA256 = _h.hexdigest()
_mtime = _dt.fromtimestamp(DATA_PATH.stat().st_mtime, _tz.utc).isoformat(timespec="seconds")

print("Input provenance manifest")
print(f"  File    : {DATA_PATH.name}")
print(f"  Loaded from: {_rel(DATA_PATH)}")
print(f"  SHA-256 : {INPUT_SHA256[:24]}...")
print(f"  Modified: {_mtime} UTC")
print(f"  Shape   : {df.shape[0]} rows x {df.shape[1]} cols")

# ── Validate target & cohort ──────────────────────────────────────────────────
_errors = []
if TARGET_COL not in df.columns:
    _errors.append(f"Target column '{TARGET_COL}' missing")
else:
    _n0 = int((df[TARGET_COL] == 0).sum())
    _n1 = int((df[TARGET_COL] == 1).sum())
    if df.shape[0] != EXPECTED_ROWS:
        _errors.append(f"Row count: expected {EXPECTED_ROWS}, got {df.shape[0]}")
    if _n0 != EXPECTED_N0 or _n1 != EXPECTED_N1:
        _errors.append(f"Target dist: expected 0={EXPECTED_N0}/1={EXPECTED_N1}, got 0={_n0}/1={_n1}")
if _errors:
    raise ValueError("Input validation FAILED:\\n" + "\\n".join(f"  - {e}" for e in _errors))
print(f"  Target  : 0={_n0} | 1={_n1}  (validation PASSED)")

# ── Validate input schema (column-level integrity, not feature selection) ─────
# The row/target checks above cannot detect a missing, renamed, duplicated, or
# unexpected column -- CLEANING_SCOPE's `c in df.columns` filters would just
# silently shrink instead of failing loudly. This gate checks df's column set
# against the classification CSV's own column_name set (the single source of
# truth already loaded above) -- no second hard-coded name list is created.
# Column order is intentionally not enforced (no canonical contract requires
# it).
_schema_errors = []
if df.shape[1] != 156:
    _schema_errors.append(f"Column count: expected 156, got {df.shape[1]}")
_dup_df_cols = df.columns[df.columns.duplicated()].unique().tolist()
if _dup_df_cols:
    _schema_errors.append(f"Duplicate dataframe column names: {_dup_df_cols}")
_expected_col_set = set(classification_df["column_name"])
_actual_col_set = set(df.columns)
_missing_from_input = sorted(_expected_col_set - _actual_col_set)
_unexpected_in_input = sorted(_actual_col_set - _expected_col_set)
if _missing_from_input:
    _schema_errors.append(
        f"Columns expected by the classification CSV but missing from input: {_missing_from_input}"
    )
if _unexpected_in_input:
    _schema_errors.append(
        f"Columns present in input but not in the classification CSV: {_unexpected_in_input}"
    )
if _schema_errors:
    raise ValueError("Input schema validation FAILED:\\n" + "\\n".join(f"  - {e}" for e in _schema_errors))
print(f"  Schema  : {df.shape[1]} columns, no duplicates, exactly matches the "
      "classification CSV column set (validation PASSED)")
""")

SB1_SCOPE = code("clean-b-s01-scope", """
# ── Define the explicit cleaning scope ────────────────────────────────────────
_scope_labels = (
    set(PREDICTOR_ALLOWED_COLS)
    | set(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)
    | set(PENDING_TIMING_CONFIRMATION_COLS)
    # intrapartum_predictor_exclude_from_prelabor_model variables remain in the
    # cleaning scope (retained in the cleaned dataset for Stage-3 / descriptive
    # use); omitting this from the union would silently drop them.
    | set(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)
)
CLEANING_SCOPE = [c for c in classification_df["column_name"]
                  if c in _scope_labels and c in df.columns]

_excluded_from_scope = {
    "leakage_exclude": [c for c in LEAKAGE_EXCLUDE_COLS if c in df.columns],
    "intrapartum_or_post_delivery_exclude": [c for c in INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS if c in df.columns],
    "source_or_text_audit_exclude": [c for c in SOURCE_OR_TEXT_AUDIT_EXCLUDE_COLS if c in df.columns],
    "cohort_control_exclude": [c for c in COHORT_CONTROL_EXCLUDE_COLS if c in df.columns],
    "clinically_nonspecific_exclude": [c for c in CLINICALLY_NONSPECIFIC_EXCLUDE_COLS if c in df.columns],
    "clinically_redundant_exclude": [c for c in CLINICALLY_REDUNDANT_EXCLUDE_COLS if c in df.columns],
    "manual_review_pending": [c for c in MANUAL_REVIEW_PENDING_COLS if c in df.columns],
    "awaiting_clinical_clarification": [c for c in AWAITING_CLINICAL_CLARIFICATION_COLS if c in df.columns],
    "id": [c for c in ID_COLS if c in df.columns],
}

# df_clean is the working copy that cleaning is applied to. df stays read-only.
df_clean = df[[TARGET_COL] + CLEANING_SCOPE].copy()

# BMI_after is classified secondary_near_delivery_predictor, one of the
# categories inside CLEANING_SCOPE, so it is carved into df_clean here like any
# other secondary predictor. Its raw column is passed through unchanged: no
# completion/imputation from weight_in_pregnancy/height (that would put derived
# backfilled values into a raw-named column), and no standalone missingness
# indicator (see SUPPRESSED_MISSING_INDICATOR_COLS in Section B4).
# For modeling, BMI_after's representation is the documented-only BMI_after_cat
# (Section B5b): four nominal categories -- low_observed / mid_observed /
# high_observed (observed-value tertiles) + not_documented -- with the q33/q67
# cutpoints fitted training-fold-only by FoldSafeQuantileCategoryTransformer in
# modeling, not materialized as a df_clean column here. Raw BMI_after is tagged
# model_entry_mode=transform_source_only: never imputed, never an independent
# plain predictor.

# _row_key_delivery_id: an internal-only row-alignment key, NOT a research
# variable and NEVER a model feature. Attached here, the exact instant
# df_clean is carved from df by column selection (so the two are still
# trivially row-position-identical), so that delivery_id -- the one true
# unique row key -- travels WITH each row through every subsequent operation
# in this notebook. If a row is ever dropped, filtered, or reordered
# downstream, its _row_key_delivery_id value goes with it automatically, the
# same way any other column would -- this is a construction guarantee, not
# an assumption that no such operation exists. Exported as a sidecar file at
# the exact moment the cleaned dataset itself is saved (SB8_EXPORT, part 5);
# EDA C reads that sidecar and continues the same guarantee through to the
# modeling matrix (see eda_c_part1_setup_gate.py /
# eda_c_part5_handoff.py). Never added to CLEANING_SCOPE, CLEANED_COLUMNS,
# or feature_dictionary, so it can never enter the cleaned dataset export or
# any research-variable list (C0 safety rule).
df_clean["_row_key_delivery_id"] = df["delivery_id"].to_numpy()

# ── Initialise cleaning logs (populated by later sections) ─────────────────────
column_actions_log = []        # one row per scope column: action + reason
missingness_log = []           # missingness handling per column
outlier_log = []               # outlier handling per numeric column
imputation_plan = []           # imputation plan per column
row_actions = []               # patient-level row missingness (gitignored output)
feature_dictionary = []        # metadata for every B-created column
transformation_review_log = [] # pure continuous transformation-review (Section B3)

# ── Centralized DCB-created-variable metadata registry ─────────────────────────
# Single source of truth for every Data Cleaning B-created variable's metadata,
# colocated with the variable-creation logic (every feature_dictionary.append(...)
# call site uses the helper below instead of a raw dict literal, so no creation
# site can silently omit a field). Exported through
# cleaning_b_feature_dictionary.csv (Section B7) in deterministic order (sorted
# by new_column); EDA C consumes it directly. Unresolved metadata is stored as
# the literal string "UNSET", never guessed -- a variable with a required field
# still UNSET is ineligible for model-candidate promotion (enforced in
# eda_c_part1_setup_gate.py).
DCB_FEATURE_DICTIONARY_REQUIRED_METADATA_FIELDS = [
    "predictor_classification", "stage", "clinical_timing", "domain", "redundancy_group",
]
UNSET = "UNSET"


# Build one feature_dictionary entry with the full, deterministic key set.
# Every feature_dictionary.append(...) call site in this notebook must use
# this helper (never a raw dict literal) so no B-created column can be
# exported with a partial/inconsistent schema. upstream_lineage is for
# lineage one or more levels removed from source_column itself (e.g. a
# column that source_column was, in turn, derived from upstream in
# preprocessing) -- leave '' when there is none.
# NOTE: no triple-double-quoted docstring here on purpose -- this function
# body is embedded inside an outer triple-double-quoted cell-source string,
# and a nested nested set of 3 double quotes would terminate it early.
def new_feature_dictionary_entry(
    new_column, source_column, creation_rule, timing, leakage_status, intended_use,
    *, creation_section, upstream_lineage="",
    predictor_classification=UNSET, stage=UNSET, clinical_timing=UNSET,
    domain=UNSET, redundancy_group=UNSET,
    materialized_in_B=True, model_entry_mode="direct", redundant_with=UNSET,
    cutpoint_source=UNSET,
):
    # cutpoint_source: for a representation whose category boundaries are
    # learned from the observed-data distribution (e.g. tertile/median
    # splits), "fold_safe_training_only" documents that those specific
    # numbers are fitted inside modeling CV training folds only, never from
    # the full cohort. UNSET for representations with no data-derived
    # numeric cutpoint (e.g. a fixed clinical threshold, or a plain
    # structural/lossless category).
    # materialized_in_B: False for a representation that B has DECIDED (name,
    # categories, split concept) but does not itself compute into a real
    # df_clean column -- the actual values are produced later by a fold-safe
    # transformer at modeling time. Default True for ordinary columns that ARE
    # materialized directly in df_clean by this notebook.
    # model_entry_mode: "transform_source_only" marks a raw/source column that
    # may feed a fold-safe transformer internally but must never independently
    # enter a design matrix as a plain predictor (enforced in EDA C/modeling).
    # Default "direct" for ordinary predictors.
    # redundant_with: names another registered column this one is exactly
    # redundant with (e.g. a missingness indicator superseded by a categorical
    # representation's own "not_documented"/equivalent bucket) -- disclosure
    # metadata that EDA C/modeling co-entry guards key off of. UNSET when N/A.
    return {
        "new_column": new_column,
        "source_column": source_column,
        "creation_rule": creation_rule,
        "timing": timing,
        "leakage_status": leakage_status,
        "intended_use": intended_use,
        "creation_section": creation_section,
        "upstream_lineage": upstream_lineage,
        "predictor_classification": predictor_classification,
        "stage": stage,
        "clinical_timing": clinical_timing,
        "domain": domain,
        "redundancy_group": redundancy_group,
        "materialized_in_B": materialized_in_B,
        "model_entry_mode": model_entry_mode,
        "redundant_with": redundant_with,
        "cutpoint_source": cutpoint_source,
    }

print(f"Cleaning scope: {len(CLEANING_SCOPE)} columns "
      f"({len(PREDICTOR_ALLOWED_COLS)} predictor_allowed + "
      f"{len(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)} secondary + "
      f"{len(PENDING_TIMING_CONFIRMATION_COLS)} pending timing + "
      f"{len(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)} intrapartum_predictor_exclude_from_prelabor_model, "
      f"present in dataset)")
print(f"Excluded from cleaning scope:")
for label, cols in _excluded_from_scope.items():
    print(f"  {label}: {len(cols)} columns")
print(f"df_clean (working copy): {df_clean.shape[0]} rows x {df_clean.shape[1]} cols")


def infer_var_type(series, binary_threshold=3, category_threshold=20):
    observed = series.dropna()
    if observed.empty:
        return "empty"
    values = set(observed.unique())
    if observed.nunique() <= binary_threshold and values.issubset({0, 1, 0.0, 1.0}):
        return "binary"
    if pd.api.types.is_numeric_dtype(series) and observed.nunique() > category_threshold:
        return "numeric"
    return "categorical"
""")


# ── Section B1c ────────────────────────────────────────────────────────────────
SB1C_HEADER = md("clean-b-s01c-header", """
## Section B1c — Structural Not-Applicable Recode: endo_resection_* Family

### Decision (Data Cleaning B, approved)
The 10 structured `endo_resection_*` multi-hot indicators have missingness that
is fully and exclusively explained by `endometriosis_surgery == 0` (no prior
endometriosis-related surgery -> resection-site fields are not applicable).
Verified by a dedicated read-only audit before implementation: zero rows with
partial missingness across the family, zero `endometriosis_surgery == 1` rows
with any missing site, zero `endometriosis_surgery == 0` rows with any positive
site value, and `endo_resection_no_resection` always mutually exclusive with
every other site.

> **Naming note:** `endo_resection_adhesiolysis` (one of the 10 fields below)
> and `endo_surgery_adhesiolysis` (a separate historical-surgery summary
> variable, gated the same way but **not** part of this 10-column recode) are
> similarly named but distinct columns — do not confuse them.

### What this step does
- Recodes `NaN -> 0` in the 10 `endo_resection_*` columns, only for rows where
  `endometriosis_surgery == 0`.
- Leaves every `endometriosis_surgery == 1` row completely untouched.
- Is **not** imputation — no value is estimated or learned. It is a
  deterministic structural fill based on an already-approved predictor
  (`endometriosis_surgery`) that perfectly and exclusively explains the
  missingness pattern.
- Removes the 10 columns from `STRUCTURAL_NAN_COLS` afterward, since they no
  longer carry meaningful NaN. Section B4 (missingness handling) then classifies
  them as 0% missing and does **not** create `__missing_ind` indicators for
  them (they would be redundant / zero-variance duplicates of
  `endometriosis_surgery`).
- Validates preconditions before recoding and postconditions after. If any
  assumption does not hold on a future data rerun, this step raises an error
  instead of silently recoding.
- The raw/free-text fields (`endo_resection_sites`, `endo_resection_sites_clean`)
  are **not** touched by this step and remain excluded from the modeling scope
  exactly as before.
""")

SB1C_RECODE = code("clean-b-s01c-recode", """
# ── Structural not-applicable recode: endo_resection_* family ─────────────────
ENDO_RESECTION_RECODE_COLS = [c for c in ENDO_RESECTION_STRUCTURAL_COLS if c in df_clean.columns]
_es = df_clean["endometriosis_surgery"]
_sub_before = df_clean[ENDO_RESECTION_RECODE_COLS].copy()

_all_missing_before = _sub_before.isna().all(axis=1)
_all_complete_before = _sub_before.notna().all(axis=1)
_partial_before = (~_all_missing_before) & (~_all_complete_before)
_n_es0 = int((_es == 0).sum())
_n_es1 = int((_es == 1).sum())

print("Structural recode precondition check (endo_resection_* family):")
print(f"  endometriosis_surgery == 0 : {_n_es0} rows")
print(f"  endometriosis_surgery == 1 : {_n_es1} rows")
print(f"  all-missing across family  : {int(_all_missing_before.sum())} rows")
print(f"  all-complete across family : {int(_all_complete_before.sum())} rows")
print(f"  partial missingness        : {int(_partial_before.sum())} rows")

_precondition_errors = []
if int(_partial_before.sum()) != 0:
    _precondition_errors.append(
        f"{int(_partial_before.sum())} rows have partial endo_resection_* missingness (expected 0)")
_bad_es0 = int(((_es == 0) & (~_all_missing_before)).sum())
if _bad_es0 != 0:
    _precondition_errors.append(
        f"{_bad_es0} rows have endometriosis_surgery==0 but are not all-missing in endo_resection_*")
_bad_es1 = int(((_es == 1) & (~_all_complete_before)).sum())
if _bad_es1 != 0:
    _precondition_errors.append(
        f"{_bad_es1} rows have endometriosis_surgery==1 but are not fully complete in endo_resection_*")
_es0_positive = int(((_es == 0).to_numpy()[:, None] & (_sub_before == 1).to_numpy()).sum())
if _es0_positive != 0:
    _precondition_errors.append(
        f"{_es0_positive} positive endo_resection_* cell(s) found among endometriosis_surgery==0 rows")

if _precondition_errors:
    raise ValueError(
        "STRUCTURAL RECODE ABORTED -- precondition check failed:\\n"
        + "\\n".join(f"  - {e}" for e in _precondition_errors)
        + "\\nNo values were changed. Re-audit before retrying."
    )
print("  Precondition check PASSED -- missingness is fully and exclusively explained "
      "by endometriosis_surgery==0. Proceeding with structural recode.")

_n_recoded_cells = 0
for col in ENDO_RESECTION_RECODE_COLS:
    _n_before_na = int(df_clean.loc[_es == 0, col].isna().sum())
    df_clean.loc[_es == 0, col] = df_clean.loc[_es == 0, col].fillna(0)
    _n_recoded_cells += _n_before_na
    column_actions_log.append({
        "column": col,
        "stage": "B1c_structural_recode",
        "action": "structural_not_applicable_recode",
        "detail": f"NaN -> 0 where endometriosis_surgery==0 ({_n_before_na} cells recoded)",
        "issue_type": "structural_subgroup_missingness",
        "action_taken": "structural_not_applicable_recode",
        "base_variable": "endometriosis_surgery",
        "reason": (
            "Missingness in this column is fully and exclusively explained by "
            "endometriosis_surgery==0 (no prior endometriosis surgery -> resection "
            "site not applicable), verified by a dedicated read-only audit with zero "
            "partial-missingness and zero inconsistent rows. Deterministic structural "
            "fill, not statistical/learned imputation."
        ),
        "rows_removed": 0,
        "row_count_changed": False,
        "target_distribution_changed": False,
        "imputation_performed": False,
        "new_indicators_created": 0,
        "unknown_categories_created": 0,
        "requires_manual_decision_before_reversal": True,
    })

print(f"Structural recode applied: {_n_recoded_cells} NaN cells -> 0 across "
      f"{len(ENDO_RESECTION_RECODE_COLS)} endo_resection_* columns "
      f"(endometriosis_surgery==0 rows only).")

# ── Postcondition validation ───────────────────────────────────────────────────
_sub_after = df_clean[ENDO_RESECTION_RECODE_COLS]
_remaining_missing = int(_sub_after.isna().sum().sum())
_es1_unchanged = df_clean.loc[_es == 1, ENDO_RESECTION_RECODE_COLS].equals(
    _sub_before.loc[_es == 1])
_es0_all_zero = bool((_sub_after.loc[_es == 0] == 0).all(axis=None))
_no_res_col = "endo_resection_no_resection"
_other_site_cols = [c for c in ENDO_RESECTION_RECODE_COLS if c != _no_res_col]
_mutual_excl_violations = int(
    ((df_clean[_no_res_col] == 1) & (df_clean[_other_site_cols] == 1).any(axis=1)).sum()
)

_postcondition_errors = []
if _remaining_missing != 0:
    _postcondition_errors.append(f"{_remaining_missing} missing cells remain after recode (expected 0)")
if not _es1_unchanged:
    _postcondition_errors.append("endometriosis_surgery==1 rows changed by the recode (expected unchanged)")
if not _es0_all_zero:
    _postcondition_errors.append("a non-zero value exists among endometriosis_surgery==0 rows after recode (expected all 0)")
if _mutual_excl_violations != 0:
    _postcondition_errors.append(
        f"{_mutual_excl_violations} row(s) have endo_resection_no_resection==1 with another site also ==1")

if _postcondition_errors:
    raise AssertionError(
        "STRUCTURAL RECODE POSTCONDITION FAILED:\\n" + "\\n".join(f"  - {e}" for e in _postcondition_errors)
    )

print("Postcondition check PASSED:")
print(f"  remaining missing cells across family      : {_remaining_missing}")
print(f"  endometriosis_surgery==1 rows unchanged     : {_es1_unchanged}")
print(f"  endometriosis_surgery==0 rows all zero      : {_es0_all_zero}")
print(f"  no_resection mutual-exclusivity violations  : {_mutual_excl_violations}")

# ── Remove from STRUCTURAL_NAN_COLS: missingness is resolved, not preserved ───
STRUCTURAL_NAN_COLS = [c for c in STRUCTURAL_NAN_COLS if c not in ENDO_RESECTION_RECODE_COLS]
CONFIRMED_STRUCTURAL_NAN_COLS = [c for c in CONFIRMED_STRUCTURAL_NAN_COLS if c not in ENDO_RESECTION_RECODE_COLS]
print(f"\\nSTRUCTURAL_NAN_COLS updated: {len(ENDO_RESECTION_RECODE_COLS)} endo_resection_* columns removed.")
print("Downstream sections (B4 missingness, B6 imputation plan) will now correctly "
      "treat these as 0% missing, ordinary columns -- no __missing_ind will be created for them.")
""")


CLEANING_B_PART1_CELLS = [
    SB0_HEADER,
    SB1_HEADER,
    SB1_FLAGS,
    SB1_IMPORTS,
    SB1_LOAD_CLASSIFICATION,
    SB1_CLASSIFICATION_LINEAGE_INIT,
    SB1_LOAD_DATA,
    SB1_SCOPE,
    SB1C_HEADER,
    SB1C_RECODE,
]


if __name__ == "__main__":
    print(f"Data Cleaning B Part 1 cells defined: {len(CLEANING_B_PART1_CELLS)}")

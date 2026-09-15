#!/usr/bin/env python3
"""EDA C — Part 1 cell definitions (sections C0–C3).

C0 — Purpose, scope, and safety rules.
C1 — Run configuration: no manual clinical-readiness boolean, no manual candidate-pool override (both retired 2026-08-31).
C2 — Load approved variable classification CSV + optional config metadata.
C3 — Load final processed dataset, provenance manifest, validation.
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


# ── Section C0 ─────────────────────────────────────────────────────────────────
SC0_HEADER = md("eda-c-s00-header", """
# EDA C — Repeated EDA, Feature Engineering, and Modeling Handoff
## Endometriosis & Intrapartum Cesarean Section — Sheba Medical Center

---

## Section C0 — Purpose, Scope, and Safety Rules

### Purpose
EDA C runs after A2 clinical decisions are resolved and any required preprocessing
corrections are applied. It bridges A2 (predictor-readiness) and the modeling phase.
On the cleaned Data Cleaning B (Batch 19) dataset it performs:
1. a **repeated EDA** that reuses/adapts the A1 + A2 analytical architecture;
2. **deterministic feature engineering** (documented plan + rule-based execution);
3. **target-independent eligibility screening**; and
4. a **cumulative stage-specific candidate handoff** (Stage 1 / Stage 2 / Stage 3).

### Notebook section order (current architecture)
The repeated-EDA diagnostics and the feature-engineering / screening / handoff
stages are **interleaved by design**: two repeated-EDA-style diagnostic
sections (C10c predictor–predictor relationships, C12e readiness table) run
*after* the C8/C9 feature-engineering cells so that the materialized derived
features are included in the predictor–predictor relationship diagnostics and
in the final readiness summary. The section table below is the authoritative
running order.

| Section | Purpose |
|---|---|
| C0–C2 | Purpose/scope; prerequisites gate; load the authoritative Data Cleaning B classification + type snapshots + config metadata |
| C3 | Load cleaned Batch 19; build `ANALYSIS_VARS` and the cumulative `STAGE_1_COLS ⊆ STAGE_2_COLS ⊆ STAGE_3_COLS` + `EARLIEST_ENTRY_STAGE` |
| **C3b** | Post-B **pre-screen** variable inventory & classification (origin lineage: `original_preprocessing` / `B_registered_original` / `B_created`; feature-dict metadata applied to B-registered originals too; cumulative `available_prediction_horizons`; registry-driven structural missingness; separate non-materialized-representation table) + predictor-pool / exclusion-rationale accounting + boolean-membership reconciliation totals (adapts A1). Not final C12 eligibility. |
| C4 / C4b / C4c | Descriptive Table 1 by target & domain; per-variable distribution plots; before/after-cleaning comparison |
| C5 / **C5b** | Missingness recheck (per-variable + row-level + structural registry); **missingness deep-dive** — by-target, heatmap, co-missingness (adapts A2.7) |
| C6 | Sparsity, event counts, and separation risk — **diagnostic only** |
| C7 / **C7b** | IQR outlier / plausibility recheck (target-blind, nothing removed); **three cumulative-stage Sweetviz profiling reports** (git-ignored HTML) |
| C8 / C9 | Feature-engineering plan; deterministic derivation into `df_analysis`; horizon-inheritance safeguard |
| C10 / C10b / **C10c** | Derived-feature validation; formula registry; **predictor–predictor relationships & redundancy diagnostics** (Spearman, Cramér's V, numeric×categorical, representation classification — adapts A2.10) |
| C11 / C12 | Exploratory predictor–target association screening (Mann–Whitney / Fisher / χ² + BH-FDR) — **descriptive only**; candidate review table |
| C12b / C12c | Eligibility filtering and candidate-pool construction (target-independent hard rules only); assert-style pool validation |
| C12d / **C12e** | Derived-feature final role; **comprehensive repeated-EDA readiness table** (adapts A2.12; p/q/effect shown for description only) |
| C13 | Export: the cumulative-Stage-3 candidate pool **plus** per-stage candidate files (`candidate_features_stage{1,2_cumulative,3_cumulative}.csv`), per-stage patient-level modeling datasets, and the machine-readable downstream-preprocessing contract |
| C14–C18 | Treatment plan (documented only); handoff contract; readiness gate; on-disk output verification; constant / near-zero-variance validation |

### Eligibility is target-independent
EDA C **hard-excludes** a variable from the candidate pool only for
**target-independent** reasons, as implemented in C12b:
- true zero variance (no missing values, exactly one observed value);
- an invalid / impossible representation (`impossible_flag`);
- a materialized derived feature whose authoritative `analytical_role`
  (from `derived_meta`) is an explicit unresolved-state value —
  `analytical_role in {"review", "unresolved"}`;
- a variable classified `intrapartum_candidate_pending_timing_confirmation`
  (timing unresolved — currently 0 members);
- a sanity-check-only / non-modeling derived feature
  (`analytical_role == "sanity_check_only"`);
- a forbidden upstream role/timing/leakage classification (`leakage_exclude`,
  `intrapartum_or_post_delivery_exclude`, `source_or_text_audit_exclude`,
  `manual_review_pending`, `awaiting_clinical_clarification`, ID/target) —
  enforced in C2/C3 before `ANALYSIS_VARS` is built.

The `primary_model_eligible` field carried on the derived-feature plan and the
exported feature dictionary is a **legacy / descriptive** compatibility field
only — it does **not** control eligibility. `analytical_role` +
`earliest_entry_stage` are the authoritative multi-horizon contract.

The following are **diagnostics / soft warnings only** and **never** remove a
variable from the pool before cross-validation:
- sparse target cells; complete / quasi separation; boundary-sparse instability;
- high missingness (surfaced as the `high_missingness_diagnostic` soft warning;
  the former generic >40% hard rule has been removed);
- `weak_univariate_signal`; `high_target_association_review`;
- p-value; BH-FDR q-value; effect size.

Redundancy is disclosed (`redundancy_group` / `redundancy_demoted` /
`redundancy_unresolved`); for families with no target-independent fixed
representative, resolution is deferred to modeling under CV. `priority_score`
is a descriptive ranking column only — it never filters the pool and never
selects a redundancy representative.

### Cumulative prediction stages
Horizons are cumulative:
- **Stage 1** — pre-labor predictors;
- **Stage 2** — Stage 1 + near-delivery predictors (`secondary_near_delivery_predictor`);
- **Stage 3** — Stage 2 + intrapartum predictors (`intrapartum_predictor_exclude_from_prelabor_model`).

`earliest_entry_stage` (derived from the authoritative classification label) sets
the **earliest** horizon at which a predictor may enter. A predictor is never
moved to an earlier stage because it looks statistically strong.

### Final feature selection is downstream
EDA C performs repeated EDA, deterministic feature engineering,
target-independent eligibility screening, and a broad candidate handoff.
Univariate predictor–target statistics here are **descriptive/diagnostic** —
they are not feature selection. Final predictive feature selection, model
fitting, and hyperparameter tuning occur downstream (EDA D / modeling), using
training-fold-only procedures inside cross-validation.

### What this notebook does NOT do
- No model training, evaluation, or hyperparameter tuning.
- No final / predictive feature selection (that is downstream, inside CV).
- No cleaning of source predictor values; no overwriting of source columns.
- No modification of the EDA A or A2 notebooks.

### Safety contract
1. **No analytical rows are removed in EDA C, and no source predictor values are
   edited for analytical cleaning.** The canonical Batch 19 workbook is never
   overwritten. `df` is the read-only source frame; the only in-memory
   bookkeeping applied to it is technical — an import-artifact column
   (`"Unnamed: 0"`) is dropped if present, and an internal row-alignment key
   (`_row_key_delivery_id`, never a feature, never a model input) is attached.
   `df_analysis` is a column subset of `df` plus the C9 `derived_` columns.
2. Derived features use the `derived_` prefix and live in `df_analysis` only.
3. No learned / fold-safe modeling transformation is fitted on the full cohort;
   fold-safe cutpoints and imputation are fitted training-fold-only, downstream.
4. `subject_number` and `delivery_id` are never printed and never appear as a
   column in the analysis frame or in any modeling handoff dataset (a row-order
   `delivery_id` alignment sidecar is written separately, never as a feature).
5. **Output flags.** `SAVE_OUTPUTS = False` by default — the broad/legacy
   patient-level reference matrix is not written unless explicitly requested.
   `SAVE_SELECTED_MODELING_DATASET = True` by default — the **stage-specific
   modeling handoff datasets** (target + the approved eligible predictors for
   each cumulative stage, **no identifier columns**) are written by default. All
   patient-level files are git-ignored / non-versioned; enabling
   `SAVE_SELECTED_MODELING_DATASET` does not commit any raw patient-level
   profiling output.
6. All analytical sections run regardless of the C1 prerequisite flag values;
   only the C16 readiness gate blocks `MODELING_HANDOFF_READY = True`.
""")


# ── Section C1 ─────────────────────────────────────────────────────────────────
SC1_HEADER = md("eda-c-s01-header", """
## Section C1 — Run Configuration

C1 sets **no** manual clinical-readiness boolean and **no** manual
candidate-pool override. Both were retired 2026-08-31 — a hand-typed `True`
is not runtime evidence, and a hand-typed variable list is an undocumented
alternate analytical path.

### Candidate universe — always metadata-derived
`ANALYSIS_VARS` is rebuilt every run in C3 from the authoritative Data Cleaning
B classification snapshot: the union of the current stage-eligible
classifications — `predictor_allowed` (Stage 1), `secondary_near_delivery_predictor`
(Stage 2), `intrapartum_predictor_exclude_from_prelabor_model` (Stage 3) — plus
approved Data Cleaning B-created replacement variables, minus the forbidden-role
set (`leakage_exclude`, `intrapartum_or_post_delivery_exclude`,
`source_or_text_audit_exclude`, `manual_review_pending`,
`awaiting_clinical_clarification`,
`intrapartum_candidate_pending_timing_confirmation`, ID/target). Authoritative
column order is preserved and `Stage 1 ⊆ Stage 2 ⊆ Stage 3` is asserted. There
is exactly one reproducible way to build the universe — no manual list, no
file import.

### Clinical readiness — operational, not hand-typed
The C16 readiness gate verifies the **current live** metadata/pool state, not a
narrative claim: no `intrapartum_candidate_pending_timing_confirmation` /
`awaiting_clinical_clarification` variable in the analytical universe; no
`manual_review_pending` variable in the eligible pool; no
forbidden/leakage/post-outcome/source-audit classification in the pool; stage
construction and candidate-pool validation pass; every hard exclusion is
target-independent. The A2 Section A2.14 decision registry and
`docs/clinical_decisions/manual_decisions_log.md` are the historical/provenance
record — C1 does not parse or dynamically re-validate them.

### Output flags
- `SAVE_AGGREGATED_OUTPUTS = True` — aggregate CSV/JSON metadata artifacts (no patient rows).
- `SAVE_OUTPUTS = False` — broad/legacy patient-level reference matrix; off by default.
- `SAVE_SELECTED_MODELING_DATASET = True` — the stage-specific
  **eligible-candidate** modeling handoff datasets (target + the approved
  eligible predictors per cumulative stage; no identifier columns; git-ignored).
  This is the broad target-independent eligible candidate pool, **not** a final
  predictive feature selection — that occurs downstream, inside training-fold
  cross-validation.

### Dataset selection — resolved from the Data Cleaning B manifest
There is **no** dataset-selection flag. The canonical EDA C input is whatever
`outputs/data_cleaning/audit/cleaning_b_manifest.json` records as its
`output_file` (currently `work_df_batch19_after_data_cleaning_b.xlsx`), loaded
from `outputs/data_cleaning/processed/` and verified byte-for-byte against the
manifest's `output_sha256`. The old `USE_LATEST_PROCESSED_BATCH` "highest
cleaned batch" auto-discovery and the raw `work_df_batch18.xlsx` fallback were
**both retired 2026-08-31** — a future approved Data Cleaning B output becomes
canonical by updating the B manifest through the B workflow, not by EDA C
guessing a filename. (The load/verify logic itself is in C3.)
""")

SC1_GATE = code("eda-c-s01-gate", """
# ── Run configuration ─────────────────────────────────────────────────────────
# C1 sets NO manual clinical-readiness boolean, NO manual candidate-pool
# override, and NO dataset-selection flag (all retired 2026-08-31).
#  * The candidate universe (ANALYSIS_VARS) is rebuilt every run from the
#    authoritative Data Cleaning B classification snapshot -- see C3.
#  * The input dataset is resolved from cleaning_b_manifest.json and verified
#    against its recorded SHA-256 -- see C3.
#  * The C16 readiness gate is derived from live metadata/pool state -- see
#    Part 5 (readiness_checks / pipeline_status gates).
#  * The A2 Section A2.14 decision registry and
#    docs/clinical_decisions/manual_decisions_log.md remain the
#    historical/provenance record and are NOT parsed or re-validated here.

import sys
from pathlib import Path

# ── Output flags ──────────────────────────────────────────────────────────────
SAVE_AGGREGATED_OUTPUTS = True   # aggregate CSV/JSON metadata artifacts (no patient rows)
SAVE_OUTPUTS = False             # broad/legacy patient-level reference matrix -- OFF by default
SAVE_SELECTED_MODELING_DATASET = True
# Stage-specific patient-level ELIGIBLE-CANDIDATE modeling handoff datasets
# (target + the approved eligible predictors per cumulative stage; NO identifier
# columns -- see C0 safety rules; git-ignored). This is the broad
# target-independent eligible candidate pool, NOT a final predictive
# feature selection -- final selection / model fitting / tuning happen
# downstream inside training-fold cross-validation.

print(f"SAVE_AGGREGATED_OUTPUTS        = {SAVE_AGGREGATED_OUTPUTS}")
print(f"SAVE_OUTPUTS                   = {SAVE_OUTPUTS}")
print(f"SAVE_SELECTED_MODELING_DATASET = {SAVE_SELECTED_MODELING_DATASET}")
print("Candidate universe : metadata-derived every run (no manual override).")
print("Input dataset      : resolved from cleaning_b_manifest.json + SHA-verified (see C3).")
print("Clinical readiness : operational -- checked in C16 from live metadata/pool state.")
""")


# ── Section C2 ─────────────────────────────────────────────────────────────────
SC2_HEADER = md("eda-c-s02-header", """
## Section C2 — Load the Metadata Contract (single source of truth per layer)

EDA C uses one authoritative source for each kind of metadata. There is **no**
embedded mirror and **no** current-working-directory alternate. The 2026-08-31
C2 correction removed both.

| # | Metadata | Authoritative source | Role |
|---|----------|----------------------|------|
| 1 | Modeling-role classification (`predictor_allowed`, every excluded/secondary/pending category) | Data Cleaning B classification snapshot (`cleaning_b_variable_classification_snapshot.csv`, via `classification_lineage.start_eda_c_snapshot`) | drives eligibility + stage membership |
| 2 | Variable type (binary / categorical / continuous / …) | Data Cleaning B type-schema snapshot (`cleaning_b_variable_type_schema_snapshot.csv`) | drives type-aware screening; **fail loud** for a B-stage variable with no entry |
| 3 | B-created / B-registered lineage: `stage`, `clinical_timing`, `domain`, `redundancy_group`, `model_entry_mode`, `redundant_with`, `cutpoint_source`, `materialized_in_B` | `cleaning_b_feature_dictionary.csv` | enriches every B-registered variable; loaded here as part of the C2 contract |
| 4 | Structural / applicability-aware missingness (confirmed vs pending tiers) | `eda_shared/structural_missingness_registry.py` | the **only** EDA C definition of structural missingness — **not** `config.py`'s `STRUCTURAL_NAN_COLS` |
| 5 | Project domain / timing / clinical-tier / redundancy-group / scoring metadata for preprocessing-level variables | `analysis/model_variable_readiness/config.py` | descriptive/supporting metadata; **required** — if it will not load, C2 **fails loud** (no empty-dict, no embedded fallback) |
| 6 | Preprocessing classification / type CSVs (`outputs/preprocessing/audit/…`) | project-root path only | **provenance comparison only** — a value difference is an audit note, never blocking, never overrides the B snapshot |

**Stage membership stays classification-driven** (source #1): `predictor_allowed`
→ Stage 1, `secondary_near_delivery_predictor` → earliest Stage 2,
`intrapartum_predictor_exclude_from_prelabor_model` → earliest Stage 3.
`TIMING_MAP` / `clinical_timing` are descriptive only and never move a
predictor to another horizon.

If `config.py` requires project files that are absent in a standalone/Colab
session, supply those files — the notebook does not carry a second analytical
definition of this metadata.
""")

SC2_CLASSIFICATION = code("eda-c-s02-classification", """
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path
import sys, os, re, hashlib, zipfile, importlib.util, warnings
from datetime import datetime as _dt, timezone as _tz

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
warnings.filterwarnings("ignore", category=FutureWarning, module="seaborn")
warnings.filterwarnings("ignore", category=FutureWarning, module="scipy")

pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 200)
pd.set_option("display.float_format", "{:.3f}".format)
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.05)
matplotlib.rcParams["figure.dpi"] = 90
_MUTED = sns.color_palette("muted")
_C0, _C1 = _MUTED[0], _MUTED[3]

IN_COLAB = "google.colab" in sys.modules

# ── Locate project root ────────────────────────────────────────────────────────
CLASSIFICATION_REL = "outputs/preprocessing/audit/variable_classification_minimal.csv"
VARIABLE_TYPE_SCHEMA_REL = "outputs/preprocessing/audit/variable_type_schema_minimal.csv"
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
# ─────────────────────────────────────────────────────────────────────────────
# NON-AUTHORITATIVE LEGACY BASELINES (descriptive diagnostics only)
# ─────────────────────────────────────────────────────────────────────────────
# EXPECTED_CLASSIFICATION_COUNTS and the three EXPECTED_*_COLS lists below are a
# hand-recorded snapshot of the classification state at one past checkpoint.
# They are kept ONLY as a change-visibility tripwire: after an approved
# reclassification the live counts/membership will differ, and that difference
# is printed as a descriptive note (never blocking). NOTHING about eligibility,
# stage membership, the candidate pool, or readiness depends on these constants
# -- the authoritative classification source is the Data Cleaning B snapshot
# (loaded below via classification_lineage.start_eda_c_snapshot). The full
# chronology of how the cohort reached its current classification state lives
# in docs/clinical_decisions/manual_decisions_log.md, not here.
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
# NON-AUTHORITATIVE LEGACY BASELINES (see the note above EXPECTED_CLASSIFICATION_
# COUNTS). Membership snapshots at one past checkpoint, kept only as a
# change-visibility tripwire -- no eligibility/stage/readiness result depends on
# them. Per-variable rationale is in docs/clinical_decisions/manual_decisions_log.md.
EXPECTED_PENDING_TIMING_CONFIRMATION_COLS = []
EXPECTED_INTRAPARTUM_PREDICTOR_EXCLUDE_COLS = [
    "meconium_stained_amniotic_fluid",
    "induction_any_bin",
    "indication_for_induction_clean",
    "intrapartum_fever_or_chorioamnionitis_bin",
    "gestational_age_at_delivery_days",
]
EXPECTED_SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS = [
    "PPROM",
    "gestational_age_at_PPROM_days",
    "placental_abruption",
    "Hb_before_delivery",
    "weight_in_pregnancy",
    "BMI_after",
]
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


def _find_project_root():
    starts = []
    if "__file__" in dir():
        starts.append(Path(__file__).resolve().parent)
    starts.append(Path.cwd().resolve())
    for start in starts:
        p = start if start.is_dir() else start.parent
        for _ in range(10):
            if (p / CLASSIFICATION_REL).is_file():
                return p
            if (p / "CLAUDE.md").is_file():
                return p
            if p.parent == p:
                break
            p = p.parent
    return None


_root = _find_project_root()
if _root is None:
    raise FileNotFoundError(
        "Cannot locate the project root (a folder containing CLAUDE.md and "
        f"{CLASSIFICATION_REL}). Canonical EDA C must run from within the "
        "project tree -- there is no current-working-directory fallback for "
        "the metadata contract (removed 2026-08-31 C2 correction)."
    )

# 2026-08-31 C2 correction: the preprocessing-level provenance CSVs are loaded
# ONLY from the located project root. The previous CWD-first lookup let an
# arbitrary same-named local file silently become the provenance comparison
# source. These files are provenance/audit only -- the Data Cleaning B
# snapshots (loaded below) remain authoritative for EDA C.
CLASSIFICATION_PATH = _root / CLASSIFICATION_REL
if not CLASSIFICATION_PATH.is_file():
    raise FileNotFoundError(
        f"Preprocessing provenance classification CSV not found at "
        f"{CLASSIFICATION_PATH}. Regenerate it via the preprocessing pipeline."
    )


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
    # 2026-08-16 structural-robustness correction (matching the equivalent
    # fix already applied to eda_a_part1_setup_cohort.py and
    # a2_part1_setup_scope.py): row-count, per-category count, and
    # per-category EXACT membership were previously all hard-blocking here --
    # meaning a single supervisor-approved reclassification of any
    # secondary_near_delivery_predictor / intrapartum_predictor_exclude_from_
    # prelabor_model / intrapartum_candidate_pending_timing_confirmation
    # variable would hard-fail this notebook before any screening logic ever
    # ran. None of that is a genuine structural invariant -- classification
    # membership is expected to change over time. The genuine structural
    # invariants (no duplicate rows, no empty values, no unrecognized label)
    # are kept below; the row-count and membership checks are now
    # descriptive/audit-only.
    dupes = cls.loc[cls["column_name"].duplicated(), "column_name"].dropna().tolist()
    if dupes:
        errors.append(f"duplicate column_name values: {dupes}")
    if cls["column_name"].isna().any() or (cls["column_name"] == "").any():
        errors.append("empty column_name values")
    unexpected = sorted(set(cls["classification"].dropna()) - set(APPROVED_LABELS))
    if unexpected:
        errors.append(f"unexpected classification labels: {unexpected}")
    counts = cls["classification"].value_counts().reindex(APPROVED_LABELS, fill_value=0).to_dict()
    _count_diffs = {
        k: (EXPECTED_CLASSIFICATION_COUNTS.get(k), v)
        for k, v in counts.items()
        if EXPECTED_CLASSIFICATION_COUNTS.get(k) != v
    }
    pending_cols = cls.loc[
        cls["classification"] == "intrapartum_candidate_pending_timing_confirmation",
        "column_name",
    ].tolist()
    intrapartum_predictor_exclude_cols = cls.loc[
        cls["classification"] == "intrapartum_predictor_exclude_from_prelabor_model",
        "column_name",
    ].tolist()
    secondary_cols = cls.loc[
        cls["classification"] == "secondary_near_delivery_predictor",
        "column_name",
    ].tolist()
    _membership_diffs = {}
    for _label, _actual, _expected in (
        ("intrapartum_candidate_pending_timing_confirmation", pending_cols, EXPECTED_PENDING_TIMING_CONFIRMATION_COLS),
        ("intrapartum_predictor_exclude_from_prelabor_model", intrapartum_predictor_exclude_cols, EXPECTED_INTRAPARTUM_PREDICTOR_EXCLUDE_COLS),
        ("secondary_near_delivery_predictor", secondary_cols, EXPECTED_SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS),
    ):
        if set(_actual) != set(_expected):
            _membership_diffs[_label] = {"expected": sorted(_expected), "actual": sorted(_actual)}
    if errors:
        raise ValueError("Invalid classification CSV: " + "; ".join(errors))
    return cls, counts, _count_diffs, _membership_diffs


def _parse_variable_type_schema(path):
    schema = pd.read_csv(path)
    required = ["variable_name", "variable_type", "n_categories"]
    missing_cols = [c for c in required if c not in schema.columns]
    if missing_cols:
        raise ValueError(f"Variable type schema missing required columns: {missing_cols}")
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
    return schema, type_map


classification_df, CLASSIFICATION_COUNTS, _CLASSIFICATION_COUNT_DIFFS, _CLASSIFICATION_MEMBERSHIP_DIFFS = _parse_classification_csv(CLASSIFICATION_PATH)
if _CLASSIFICATION_COUNT_DIFFS:
    print(
        "Classification category counts differ from the last-recorded baseline "
        "(expected, healthy after an approved reclassification -- descriptive "
        f"only, not blocking): {_CLASSIFICATION_COUNT_DIFFS}"
    )
if _CLASSIFICATION_MEMBERSHIP_DIFFS:
    print(
        "Classification category membership differs from the last-recorded "
        "baseline (expected, healthy after an approved reclassification -- "
        f"descriptive only, not blocking): {_CLASSIFICATION_MEMBERSHIP_DIFFS}"
    )

# 2026-08-31 C2 correction: project-root path only (no CWD-first override).
# Provenance/diagnostic comparison ONLY -- the Data Cleaning B type-schema
# snapshot below is the authoritative type source (see VARIABLE_TYPE_MAP).
VARIABLE_TYPE_SCHEMA_PATH = _root / VARIABLE_TYPE_SCHEMA_REL
if not Path(VARIABLE_TYPE_SCHEMA_PATH).is_file():
    raise FileNotFoundError(
        f"Preprocessing provenance type-schema CSV not found at "
        f"{VARIABLE_TYPE_SCHEMA_PATH}. Regenerate it via the preprocessing pipeline."
    )
PREPROCESSING_TYPE_SCHEMA_DF, PREPROCESSING_VARIABLE_TYPE_MAP = _parse_variable_type_schema(VARIABLE_TYPE_SCHEMA_PATH)

# ── Classification-lineage: fresh EDA C working snapshot ──────────────────────
# Always starts from Data Cleaning B's saved classification snapshot -- never
# from the raw preprocessing files directly, and never from EDA C's own
# previous snapshot. See analysis/classification_lineage/classification_lineage.py.
#
# 2026-08-27 correction (Decision 91, Gap 2 -- targeted post-implementation
# audit): THIS is now the authoritative classification source for
# `_cols_for()` / PREDICTOR_ALLOWED_COLS / ORIGINAL_ANALYSIS_VARS below.
# Previously (through the initial Decision 91 pass) `_cols_for()` read
# `classification_df` (the raw preprocessing-level CSV, loaded above)
# directly, entirely bypassing this B-derived snapshot for eligibility
# purposes -- classification_lineage's snapshot chain existed on disk but was
# never actually consumed as EDA C's real source of truth, only carried
# forward for its own later save. `classification_df` is retained below only
# for the structural checks that follow (every original column must be
# present in the B snapshot at least once) and for the descriptive
# count/membership diagnostics already printed above -- it is never again the
# authoritative source for which columns enter any predictor-pool list.
# A plain classification VALUE divergence between classification_df and the
# B snapshot is audit-only (see CLASSIFICATION_SNAPSHOT_AUDIT_DIFFS below) and
# never raises -- only structural snapshot problems (duplicate/unrecognized
# rows, a missing original column) fail loud.
_cl_module_path = _root / "analysis" / "classification_lineage" / "classification_lineage.py"
_cl_spec = importlib.util.spec_from_file_location("classification_lineage", _cl_module_path)
classification_lineage = importlib.util.module_from_spec(_cl_spec)
_cl_spec.loader.exec_module(classification_lineage)

eda_c_classification_snapshot, eda_c_type_schema_snapshot = classification_lineage.start_eda_c_snapshot(root=_root)

# 2026-08-28 correction (Decision 91, Gap 2 follow-up -- independent review
# of the committed patch): the guard below previously RAISED whenever the B
# snapshot's classification value differed from the raw preprocessing CSV's
# value for the same column. That defeated the architecture it was meant to
# protect: if the B snapshot is authoritative, a legitimate B-level
# reclassification is EXPECTED to differ from the older preprocessing-level
# CSV -- that is not corruption, it is exactly what "B is authoritative"
# means. The guard now only fails loud on genuine structural problems
# (duplicate/unrecognized B-snapshot rows, an original preprocessing column
# silently missing from the B snapshot); a plain VALUE difference is recorded
# for audit visibility only, never blocks the run, and the B snapshot value
# is used everywhere below regardless -- the preprocessing CSV never
# overrides it.
_b_cls_dupes = eda_c_classification_snapshot.loc[
    eda_c_classification_snapshot["column_name"].duplicated(), "column_name"
].dropna().tolist()
if _b_cls_dupes:
    raise ValueError(
        f"Data Cleaning B classification snapshot contains duplicate "
        f"column_name values: {_b_cls_dupes}"
    )
_b_cls_unexpected = sorted(
    set(eda_c_classification_snapshot["classification"].dropna()) - set(APPROVED_LABELS)
)
if _b_cls_unexpected:
    raise ValueError(
        f"Data Cleaning B classification snapshot contains unrecognized "
        f"classification labels: {_b_cls_unexpected}"
    )
_b_snapshot_names = set(eda_c_classification_snapshot["column_name"].astype(str))
_original_preprocessing_names = set(classification_df["column_name"].astype(str))
_missing_from_b_snapshot = sorted(_original_preprocessing_names - _b_snapshot_names)
if _missing_from_b_snapshot:
    raise ValueError(
        f"{len(_missing_from_b_snapshot)} original preprocessing-level "
        "column(s) are missing from the Data Cleaning B classification "
        "snapshot -- every original column must be carried forward exactly "
        f"once (register_feature() only adds/no-ops, never drops): "
        f"{_missing_from_b_snapshot}"
    )

# Audit-only divergence report -- NOT fail-loud. A difference here means B
# approved a reclassification after preprocessing closed; that is healthy,
# not an error.
_snapshot_lookup = dict(zip(
    eda_c_classification_snapshot["column_name"].astype(str),
    eda_c_classification_snapshot["classification"].astype(str),
))
CLASSIFICATION_SNAPSHOT_AUDIT_DIFFS = {}
for _row in classification_df.itertuples(index=False):
    _snap_cls = _snapshot_lookup.get(str(_row.column_name))
    if _snap_cls is not None and _snap_cls != str(_row.classification):
        CLASSIFICATION_SNAPSHOT_AUDIT_DIFFS[str(_row.column_name)] = {
            "preprocessing_csv": str(_row.classification), "b_snapshot_authoritative": _snap_cls,
        }
if CLASSIFICATION_SNAPSHOT_AUDIT_DIFFS:
    print(
        "AUDIT (not blocking -- B snapshot value is authoritative and is what "
        "_cols_for() uses): Data Cleaning B's classification snapshot differs "
        "from the raw preprocessing classification CSV for "
        f"{len(CLASSIFICATION_SNAPSHOT_AUDIT_DIFFS)} column(s): {CLASSIFICATION_SNAPSHOT_AUDIT_DIFFS}"
    )
else:
    print(f"Classification-lineage audit: 0 value differences between the "
          f"preprocessing CSV and the Data Cleaning B snapshot across "
          f"{len(classification_df)} original columns checked (B snapshot "
          f"remains authoritative regardless).")

# 2026-08-28 correction (Decision 91, Gap 2 follow-up): the Data Cleaning B
# type-schema snapshot (eda_c_type_schema_snapshot, loaded above by the same
# start_eda_c_snapshot() call) is now the authoritative type source for EDA
# C's own type inference (infer_var_type() in eda_c_part2_recheck.py, which
# reads the module-level VARIABLE_TYPE_MAP name). PREPROCESSING_VARIABLE_TYPE_MAP
# (built above from the raw preprocessing-level CSV) is retained for
# provenance / diagnostic comparison only and never used for inference.
# C-created variables (derived_* features built later in Part 3/C8-C9) are
# not expected to be present in this B-stage snapshot yet -- infer_var_type()
# already falls through to its separate derived_meta-based handling for
# those, unaffected by this change.
_b_type_dupes = eda_c_type_schema_snapshot.loc[
    eda_c_type_schema_snapshot["variable_name"].duplicated(), "variable_name"
].dropna().tolist()
if _b_type_dupes:
    raise ValueError(
        f"Data Cleaning B type-schema snapshot contains duplicate "
        f"variable_name values: {_b_type_dupes}"
    )
_b_type_unexpected = sorted(
    set(eda_c_type_schema_snapshot["variable_type"].dropna()) - set(ALLOWED_VARIABLE_TYPES)
)
if _b_type_unexpected:
    raise ValueError(
        f"Data Cleaning B type-schema snapshot contains unrecognized "
        f"variable_type values: {_b_type_unexpected}"
    )
_b_type_names = set(eda_c_type_schema_snapshot["variable_name"].astype(str))
_original_type_names = set(PREPROCESSING_TYPE_SCHEMA_DF["variable_name"].astype(str))
_missing_type_from_b_snapshot = sorted(_original_type_names - _b_type_names)
if _missing_type_from_b_snapshot:
    raise ValueError(
        f"{len(_missing_type_from_b_snapshot)} variable(s) already known at "
        "the preprocessing/B handoff are missing from the Data Cleaning B "
        f"type-schema snapshot: {_missing_type_from_b_snapshot}"
    )

VARIABLE_TYPE_MAP = dict(zip(
    eda_c_type_schema_snapshot["variable_name"].astype(str),
    eda_c_type_schema_snapshot["variable_type"].astype(str),
))
variable_type_schema_df = eda_c_type_schema_snapshot

TYPE_SCHEMA_SNAPSHOT_AUDIT_DIFFS = {}
for _row in PREPROCESSING_TYPE_SCHEMA_DF.itertuples(index=False):
    _snap_type = VARIABLE_TYPE_MAP.get(str(_row.variable_name))
    if _snap_type is not None and _snap_type != str(_row.variable_type):
        TYPE_SCHEMA_SNAPSHOT_AUDIT_DIFFS[str(_row.variable_name)] = {
            "preprocessing_csv": str(_row.variable_type), "b_snapshot_authoritative": _snap_type,
        }
if TYPE_SCHEMA_SNAPSHOT_AUDIT_DIFFS:
    print(
        "AUDIT (not blocking -- B snapshot value is authoritative and is what "
        "infer_var_type() uses): Data Cleaning B's type-schema snapshot "
        "differs from the raw preprocessing type-schema CSV for "
        f"{len(TYPE_SCHEMA_SNAPSHOT_AUDIT_DIFFS)} variable(s): {TYPE_SCHEMA_SNAPSHOT_AUDIT_DIFFS}"
    )
else:
    print(f"Type-schema-lineage audit: 0 value differences between the "
          f"preprocessing type schema and the Data Cleaning B type-schema "
          f"snapshot across {len(PREPROCESSING_TYPE_SCHEMA_DF)} original variables "
          f"checked (B snapshot remains authoritative regardless).")

# ── Structural-applicability registry (metadata contract source #4) ─────────
# 2026-08-31 C2 correction: structural_missingness_registry.py is the SINGLE
# EDA C authority for structural / applicability-aware missingness -- NOT
# analysis/model_variable_readiness/config.py's STRUCTURAL_NAN_COLS (which
# differs materially: it lists diabetes_type, which the registry deliberately
# excludes -- 0% missing, no code-enforced gate -- and it omits the confirmed
# subgroup-structural endometriosis-surgery variables the registry covers).
# Two explicit tiers, never conflated:
#   CONFIRMED_STRUCTURAL_COLS  -- code-enforced subgroup gate; may receive the
#                                 structural_by_design label + missingness-
#                                 penalty exemption.
#   APPLICABILITY_LINKED_COLS    -- empirical applicability pattern only, no
#                                 code-enforced gate; labeled
#                                 applicability_linked_no_preprocessing_mask,
#                                 never promoted to confirmed, never
#                                 auto-imputed.
_smr_spec = importlib.util.spec_from_file_location(
    "structural_missingness_registry",
    _root / "analysis" / "eda" / "notebook_build" / "eda_shared" / "structural_missingness_registry.py",
)
structural_missingness_registry = importlib.util.module_from_spec(_smr_spec)
_smr_spec.loader.exec_module(structural_missingness_registry)
CONFIRMED_STRUCTURAL_COLS = sorted(structural_missingness_registry.structural_nan_cols())
APPLICABILITY_LINKED_COLS = sorted(structural_missingness_registry.applicability_linked_cols())
# Back-compat alias consumed downstream (C4/C5/C12/C14/C17). Points ONLY at the
# CONFIRMED tier -- applicability-linked variables are handled via
# APPLICABILITY_LINKED_COLS + structural_missingness_registry.applicability_gate_for().
STRUCTURAL_NAN_COLS = list(CONFIRMED_STRUCTURAL_COLS)
_struct_overlap = sorted(set(CONFIRMED_STRUCTURAL_COLS) & set(APPLICABILITY_LINKED_COLS))
if _struct_overlap:
    raise AssertionError(
        f"structural_missingness_registry: {_struct_overlap} appear in BOTH the "
        "confirmed and pending tiers -- the tiers must be disjoint."
    )
print("Classification-lineage snapshot initialised from the Data Cleaning B snapshot: "
      f"{len(eda_c_classification_snapshot)} classification rows, "
      f"{len(eda_c_type_schema_snapshot)} type-schema rows.")
print(f"Structural-missingness registry (metadata source #4): "
      f"{len(CONFIRMED_STRUCTURAL_COLS)} confirmed, {len(APPLICABILITY_LINKED_COLS)} pending.")

# ── Share-safe rendering helper (presentation layer only) ───────────────────
# EDA C's saved figures (outputs/eda_c/figures/, git-ignored, aggregate-only)
# now reuse the SAME project-wide small-cell disclosure convention as EDA A2
# (eda_shared/share_safe.py, threshold n<5). This is a RENDER-LAYER concern
# only: it never alters an analytical count, proportion, category table,
# DataFrame, or any downstream calculation -- a suppressed cell is masked on
# the drawn/share-safe visual surface alone. No new privacy scheme is
# invented; the module and the SHARE_SAFE_MODE flag name mirror A2 exactly.
_ss_spec = importlib.util.spec_from_file_location(
    "share_safe",
    _root / "analysis" / "eda" / "notebook_build" / "eda_shared" / "share_safe.py",
)
share_safe = importlib.util.module_from_spec(_ss_spec)
_ss_spec.loader.exec_module(share_safe)
SHARE_SAFE_MODE = True  # default ON, same as a2_predictor_readiness
print(f"SHARE_SAFE_MODE (figure rendering only) = {SHARE_SAFE_MODE} "
      f"(small-cell threshold n<{share_safe.DEFAULT_DISCLOSURE_THRESHOLD}; "
      "presentation layer only -- analytical values are unaffected).")


def _cols_for(label):
    # 2026-08-27 correction (Decision 91, Gap 2): sourced from the Data
    # Cleaning B classification snapshot (the authoritative post-B state),
    # not the raw preprocessing-level classification_df -- see the
    # divergence guard above. The snapshot is a strict superset of
    # classification_df's rows (every original column unchanged, plus
    # B-created rows); membership here is therefore identical to before for
    # every original column, and additionally correct if B ever legitimately
    # needs to carry a reclassification forward.
    return eda_c_classification_snapshot.loc[
        eda_c_classification_snapshot["classification"] == label, "column_name"
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

# Decision 65 (clinical review with Dr. Keren and Dr. Shai, 2026-08-12): EDA C
# uses ONE unified master candidate universe -- predictor_allowed,
# secondary_near_delivery_predictor, AND intrapartum_predictor_exclude_from_
# prelabor_model all enter the SAME screening pipeline below. Horizon-specific
# restriction (pre-labor / near-delivery / intrapartum) is introduced only at
# the modeling boundary, downstream of this notebook's handoff -- NOT here.
# intrapartum_predictor_exclude_from_prelabor_model is therefore intentionally
# NOT in _FORBIDDEN_COLS below (removed 2026-08-13, multi-horizon plan Batch
# 2); intrapartum_candidate_pending_timing_confirmation remains forbidden --
# its timing is unresolved by definition, independent of this architecture.
_FORBIDDEN_COLS = (
    set(ID_COLS) | set(TARGET_COLS)
    | set(LEAKAGE_EXCLUDE_COLS) | set(INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS)
    | set(SOURCE_OR_TEXT_AUDIT_EXCLUDE_COLS) | set(MANUAL_REVIEW_PENDING_COLS)
    | set(AWAITING_CLINICAL_CLARIFICATION_COLS) | set(PENDING_TIMING_CONFIRMATION_COLS)
)

# A Data-Cleaning-B-derived variable cannot be more predictor-eligible than its
# source variable unless an explicit documented exception exists (2026-07-31,
# Decisions 39/40). weight_in_pregnancy_cat is a derivative of
# weight_in_pregnancy (secondary timing family -- NOT automatically forbidden,
# since that category is used for other legitimate secondary predictors like
# Hb_before_delivery). It is hard-excluded here explicitly, rather than left
# eligible with only a soft "review" flag, per the approved decision that it
# may not enter the primary pre-labor predictor pool.
# BMI_after_cat: HISTORICAL (Decision 89, 2026-08-27) -- Decision 89 briefly
# made BMI_after_cat a real, cohort-wide-materialized Data Cleaning B column
# and, on that mechanism, hard-excluded raw BMI_after via
# MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS (below) so the two
# representations could never co-enter a model. SUPERSEDED the same day by
# Decision 91: BMI_after_cat is no longer materialized as a real df column at
# all -- it is now a documented-only, fold-safe-deferred representation
# (materialized_in_B=False), computed only at modeling time. Consequently raw
# BMI_after is no longer hard-excluded here either --
# MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS is now empty (see
# below), and raw BMI_after reaches ANALYSIS_VARS as an ordinary
# secondary_near_delivery_predictor candidate, disclosed
# model_entry_mode=transform_source_only. See
# docs/clinical_decisions/manual_decisions_log.md Decision 91.
#
# 2026-08-27 correction: weight_in_pregnancy_cat is no longer materializable
# in Data Cleaning B at all (documented-only, fold-safe-deferred
# representation -- see cleaning_b_part4_transformations_imputation_plan.py
# Section B5b), so this set is now vacuously true (it can never be a real df
# column, so it could never reach ANALYSIS_VARS regardless of this set).
# Left in place as a defense-in-depth guard, not the primary mechanism.
DERIVED_INHERITS_SOURCE_EXCLUSION_COLS = {"weight_in_pregnancy_cat"}
_FORBIDDEN_COLS = _FORBIDDEN_COLS | DERIVED_INHERITS_SOURCE_EXCLUSION_COLS

# gestational_age_at_PPROM_days / BMI_after: BOTH REMOVED from this set
# 2026-08-27 (correction, supersedes the mechanism only -- not the underlying
# classification/eligibility decisions). Historically both were hard-excluded
# here because there was no approved missing-data treatment for their
# high-missingness raw values. That is no longer true: both now have an
# approved DEFERRED categorical representation (documented in Data Cleaning
# B's feature dictionary with materialized_in_B=False -- BMI_after_cat /
# gestational_age_at_PPROM_days_timing_status -- computed only at modeling
# time by a fold-safe transformer, never as a real column here). Since
# neither representation is ever a real df column, neither can ever
# accidentally enter ANALYSIS_VARS via B_CREATED_ANALYSIS_VARS (that
# construction already filters to `new_column in df.columns`, below) -- so
# there is no risk of the raw source and a materialized derived column
# co-existing in the candidate pool the way BMI_after_cat once could.
# The raw columns are now allowed back into ANALYSIS_VARS as ordinary
# secondary_near_delivery_predictor candidates, each disclosed with
# model_entry_mode="transform_source_only" (surfaced as a soft-warning flag,
# Section C11/C12) so nobody mistakes "eligible" for "safe to feed directly
# into a design matrix" -- the actual enforcement that these raw columns can
# never be routed through generic numeric imputation lives in modeling
# (analysis/modeling/final_modeling/modeling_core.py's build_preprocessor()).
# gestational_age_at_PPROM_days is unaffected by any missingness threshold:
# EDA C's generic high-missingness rule was removed (eda_c_part4_screening.py,
# C12b) -- high missingness is now diagnostic metadata + a soft warning only,
# never a hard-exclusion gate. Its PRIMARY (raw whole-cohort) missingness is
# 96.3%; the structural-applicability-aware figure (5.9%
# genuine-missing-within-applicable) is a sensitivity/diagnostic view only,
# not a replacement for the PRIMARY figure.
#
# gestational_age_at_delivery_days remains unaffected by any of this (do not
# confuse the two "gestational_age_at_*" siblings) -- it is
# intrapartum_predictor_exclude_from_prelabor_model (Stage 3, Decision 79
# addendum), screened normally, no override needed.
MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS = set()
_FORBIDDEN_COLS = _FORBIDDEN_COLS | MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS

# ── Metadata contract source #5: model_variable_readiness/config.py ───────
# 2026-08-31 C2 correction: the large EMBEDDED_TIMING_MAP / EMBEDDED_DOMAIN_MAP /
# EMBEDDED_CLINICAL_TIER / EMBEDDED_REDUNDANCY_GROUPS / EMBEDDED_SCORING_WEIGHTS /
# EMBEDDED_STRUCTURAL_NAN_COLS copies were REMOVED. Independent review confirmed
# they had drifted materially from the live config.py (extra/missing keys,
# different oligohydramnios timing, an extra induction redundancy group,
# different anthropometry membership, a legacy timing_unknown_bonus weight, a
# different STRUCTURAL_NAN_COLS). A stale second authority is worse than no
# fallback. config.py is now REQUIRED for canonical EDA C:
#   * TIMING_MAP / DOMAIN_MAP / CLINICAL_TIER / REDUNDANCY_GROUPS / SCORING_WEIGHTS
#     come from config.py and nowhere else.
#   * If config.py is missing, fails to import, or returns an empty core dict,
#     C2 raises -- it does NOT silently continue with empty dicts and it does
#     NOT fall back to an embedded mirror. A standalone/Colab run must supply
#     the project metadata files.
#   * config.py's STRUCTURAL_NAN_COLS is deliberately NOT consumed here -- the
#     structural-missingness authority for EDA C is structural_missingness_
#     registry.py (see CONFIRMED_STRUCTURAL_COLS / APPLICABILITY_LINKED_COLS above).
_cfg_path = _root / "analysis" / "model_variable_readiness" / "config.py"
if not _cfg_path.is_file():
    raise RuntimeError(
        "REQUIRED metadata source missing: analysis/model_variable_readiness/config.py "
        f"not found at {_cfg_path}. Canonical EDA C has no embedded fallback for "
        "TIMING_MAP / DOMAIN_MAP / CLINICAL_TIER / REDUNDANCY_GROUPS / SCORING_WEIGHTS "
        "(removed 2026-08-31). Supply the project metadata files."
    )
try:
    _spec = importlib.util.spec_from_file_location("_eda_c_cfg", _cfg_path)
    _cfg = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_cfg)
except Exception as _e:  # noqa: BLE001 -- deliberately fail loud on ANY import error
    raise RuntimeError(
        f"REQUIRED metadata source failed to load: config.py raised {_e!r}. "
        "Fix config.py (or its inputs) before running EDA C -- there is no "
        "embedded fallback and empty-dict continuation is not allowed."
    )
TIMING_MAP = dict(getattr(_cfg, "TIMING_MAP", {}) or {})
DOMAIN_MAP = dict(getattr(_cfg, "DOMAIN_MAP", {}) or {})
CLINICAL_TIER = dict(getattr(_cfg, "CLINICAL_TIER", {}) or {})
REDUNDANCY_GROUPS = {
    _g: {"members": list(_d.get("members", [])), "representative": _d.get("representative")}
    for _g, _d in (getattr(_cfg, "REDUNDANCY_GROUPS", {}) or {}).items()
}
SCORING_WEIGHTS = dict(getattr(_cfg, "SCORING_WEIGHTS", {}) or {})
# config.py's STRUCTURAL_NAN_COLS is captured for the disclosure-only audit
# below -- it is NOT consumed as EDA C's structural-missingness definition
# (that is the structural_missingness_registry; see CONFIRMED/PENDING above).
_cfg_structural_nan = list(getattr(_cfg, "STRUCTURAL_NAN_COLS", []) or [])
_CONFIG_PY_LOADED = True
del _spec, _cfg
_empty_core = [
    _n for _n, _m in (
        ("TIMING_MAP", TIMING_MAP), ("DOMAIN_MAP", DOMAIN_MAP),
        ("CLINICAL_TIER", CLINICAL_TIER), ("REDUNDANCY_GROUPS", REDUNDANCY_GROUPS),
        ("SCORING_WEIGHTS", SCORING_WEIGHTS),
    ) if not _m
]
if _empty_core:
    raise RuntimeError(
        f"config.py loaded but returned empty core metadata: {_empty_core}. "
        "EDA C will not continue with empty metadata (that silently changes "
        "descriptive scoring/redundancy output). Fix config.py."
    )

# ── Metadata contract source #3: enrich B-registered variables from the B ───
#    feature dictionary (cleaning_b_feature_dictionary.csv). Replaces the old
#    hardcoded B_CREATED_REPLACEMENT_TIMING_MAP / _DOMAIN_MAP / _CLINICAL_TIER
#    (removed 2026-08-31 -- stale and duplicated upstream metadata). For every
#    B-registered variable the feature dictionary is authoritative for
#    clinical_timing / domain / redundancy_group / model_entry_mode; stage is
#    always classification-derived (never from here). A clinical-priority tier
#    is NOT invented from the feature dictionary (it has no such column) --
#    genuinely-new B-created DERIVED columns get the same "derived" tier a
#    C9-derived column would, nothing else does.
_RECOGNIZED_MODEL_ENTRY_MODES = {"direct", "transform_source_only"}
_C2_FD_REL = "outputs/data_cleaning/audit/cleaning_b_feature_dictionary.csv"
B_FEATURE_DICT = None
B_CREATED_COLS = set()
B_FEATURE_REDUNDANCY_GROUP = {}
B_FEATURE_MODEL_ENTRY_MODE = {}
B_FEATURE_STAGE = {}
_fd_c2_path = _root / _C2_FD_REL
if _fd_c2_path.is_file():
    B_FEATURE_DICT = pd.read_csv(_fd_c2_path)
    _fd_required = [
        "new_column", "source_column", "predictor_classification", "stage",
        "clinical_timing", "domain", "redundancy_group", "materialized_in_B",
        "model_entry_mode", "redundant_with", "cutpoint_source",
    ]
    _fd_missing = [c for c in _fd_required if c not in B_FEATURE_DICT.columns]
    if _fd_missing:
        raise ValueError(
            f"cleaning_b_feature_dictionary.csv is missing required fields EDA C "
            f"consumes: {_fd_missing}. Fix the Data Cleaning B feature-dictionary export."
        )
    B_CREATED_COLS = set(B_FEATURE_DICT["new_column"].dropna().astype(str))
    _bad_mem = sorted({
        str(_v) for _v in B_FEATURE_DICT["model_entry_mode"].dropna().astype(str).unique()
        if str(_v) not in _RECOGNIZED_MODEL_ENTRY_MODES and str(_v) != "UNSET"
    })
    if _bad_mem:
        raise ValueError(
            f"cleaning_b_feature_dictionary.csv has unrecognized model_entry_mode "
            f"value(s) {_bad_mem}; expected a subset of {sorted(_RECOGNIZED_MODEL_ENTRY_MODES)} "
            "(or 'UNSET')."
        )

    def _fd_ok(_v):
        return pd.notna(_v) and str(_v).strip() not in ("", "UNSET", "nan")

    _new_delta2 = (
        {f"adenomyosis_feature_{_c}" for _c in range(1, 12)}
        | {"adenomyosis_features_unknown", "derived_endo_surgery_adhesion_status",
           "indication_for_induction_status"}
    )
    for _r in B_FEATURE_DICT.to_dict("records"):
        _col = str(_r["new_column"])
        _srccol = str(_r.get("source_column", ""))
        _tim, _dom = _r.get("clinical_timing"), _r.get("domain")
        _rg, _mem = _r.get("redundancy_group"), _r.get("model_entry_mode")
        _stg = _r.get("stage")
        if _fd_ok(_mem):
            B_FEATURE_MODEL_ENTRY_MODE[_col] = str(_mem).strip()
        if _fd_ok(_rg):
            B_FEATURE_REDUNDANCY_GROUP[_col] = str(_rg).strip()
        if _fd_ok(_stg):
            try:
                B_FEATURE_STAGE[_col] = int(float(_stg))
            except (TypeError, ValueError):
                pass
        # A genuinely-NEW Delta-2 derived column must carry complete B metadata.
        if _col in _new_delta2 and not (_fd_ok(_tim) and _fd_ok(_dom)):
            raise AssertionError(
                f"B->C METADATA PROPAGATION FAILED: {_col!r} is a new B-created "
                f"variable with incomplete feature-dictionary metadata "
                f"(clinical_timing={_tim!r}, domain={_dom!r}). Fix the registration "
                "in Data Cleaning B -- there is no hardcoded fallback for this name."
            )
        if _fd_ok(_tim):
            TIMING_MAP[_col] = str(_tim).strip()
        if _fd_ok(_dom):
            DOMAIN_MAP[_col] = str(_dom).strip()
        # Only genuinely-new DERIVED B columns (new_column != source_column) get
        # the "derived" clinical tier; passthrough B-registered raw variables
        # (PPROM, BMI_after, weight_in_pregnancy, gestational_age_at_PPROM_days)
        # keep whatever tier config.py gives them (or the default).
        if _col != _srccol and _col not in CLINICAL_TIER:
            CLINICAL_TIER[_col] = "derived"
    print(f"  B feature dictionary (metadata source #3): {len(B_CREATED_COLS)} B-registered "
          f"columns; enriched TIMING_MAP/DOMAIN_MAP for "
          f"{sum(1 for _c in B_CREATED_COLS if _c in TIMING_MAP)} of them.")
else:
    print("  NOTE: cleaning_b_feature_dictionary.csv not found in C2 -- "
          "expecting a test/structure run with no B-created columns.")

# ── config.py vs structural registry: disclose (do not reconcile) disagreement ─
_cfg_struct = set(_cfg_structural_nan)
_only_cfg = sorted(_cfg_struct - set(CONFIRMED_STRUCTURAL_COLS) - set(APPLICABILITY_LINKED_COLS))
_only_registry = sorted((set(CONFIRMED_STRUCTURAL_COLS) | set(APPLICABILITY_LINKED_COLS)) - _cfg_struct)
if _only_cfg or _only_registry:
    print("  AUDIT (disclosure only -- the structural registry is authoritative "
          "for EDA C, config.py's STRUCTURAL_NAN_COLS is NOT used here):")
    if _only_cfg:
        print(f"    in config.STRUCTURAL_NAN_COLS but NOT structural for EDA C: {_only_cfg}")
    if _only_registry:
        print(f"    structural for EDA C (registry) but NOT in config.STRUCTURAL_NAN_COLS: {_only_registry}")

# ── Metadata verification block (always printed) ─────────────────────────
print("=" * 70)
print("METADATA VERIFICATION (C2 contract)")
print("=" * 70)
print(f"  1 classification snapshot (B) : {len(eda_c_classification_snapshot)} rows  [authoritative: eligibility + stage]")
print(f"  2 type-schema snapshot (B)    : {len(VARIABLE_TYPE_MAP)} vars   [authoritative: variable type]")
print(f"  3 B feature dictionary        : {len(B_CREATED_COLS)} B-registered cols  [authoritative: B lineage/timing/domain/entry-mode]")
print(f"  4 structural-missing registry : {len(CONFIRMED_STRUCTURAL_COLS)} confirmed / {len(APPLICABILITY_LINKED_COLS)} pending  [authoritative: structural missingness]")
print(f"  5 config.py                   : loaded={_CONFIG_PY_LOADED}  (TIMING={len(TIMING_MAP)} DOMAIN={len(DOMAIN_MAP)} TIER={len(CLINICAL_TIER)} REDUND={len(REDUNDANCY_GROUPS)} WEIGHTS={len(SCORING_WEIGHTS)})")
print(f"  6 preprocessing CSVs          : provenance/audit comparison only (project-root path)")

# ── Meaningful consistency validation (replaces the old "dict >= N entries") ─
_c2_meta_errors = []
if not _CONFIG_PY_LOADED:
    _c2_meta_errors.append("config.py did not load")
for _g, _d in REDUNDANCY_GROUPS.items():
    _rep = _d.get("representative")
    if _rep is not None and _rep not in _d.get("members", []):
        _c2_meta_errors.append(f"REDUNDANCY_GROUPS[{_g!r}] representative {_rep!r} not in its members")
_bad_stage_meta = sorted({
    _c for _c, _s in B_FEATURE_STAGE.items() if _s not in (1, 2, 3)
})
if _bad_stage_meta:
    _c2_meta_errors.append(f"B feature-dictionary 'stage' out of {{1,2,3}} for {_bad_stage_meta}")
if _c2_meta_errors:
    raise RuntimeError("C2 METADATA CONTRACT FAILED: " + "; ".join(_c2_meta_errors))
print("  C2 metadata contract: PASS")
print("=" * 70)


print(f"Classification CSV (preprocessing-level, provenance only): {CLASSIFICATION_PATH.name}")
print(f"  Loaded from: {CLASSIFICATION_PATH.resolve()}")
print(f"  Authoritative classification source: Data Cleaning B snapshot "
      f"({len(eda_c_classification_snapshot)} rows) -- see the divergence-audit block above.")
if not VARIABLE_TYPE_MAP:
    raise RuntimeError(
        "Data Cleaning B type-schema snapshot produced an empty VARIABLE_TYPE_MAP "
        "-- EDA C cannot infer B-stage variable types by dtype heuristics. "
        "Regenerate the Data Cleaning B type-schema snapshot."
    )
print(f"Variable type schema: authoritative source is the Data Cleaning B "
      f"type-schema snapshot ({len(VARIABLE_TYPE_MAP)} variables); the "
      f"preprocessing-level {Path(VARIABLE_TYPE_SCHEMA_PATH).name} "
      f"is retained for provenance/diagnostic comparison only. A B-stage "
      f"variable with no entry here FAILS LOUD in infer_var_type (no dtype fallback).")
print(f"Classification counts: {CLASSIFICATION_COUNTS}")
print(f"Target column: {TARGET_COL}")
print(f"PREDICTOR_ALLOWED_COLS: {len(PREDICTOR_ALLOWED_COLS)} vars")
print(f"SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS: {len(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)} vars")
print(f"PENDING_TIMING_CONFIRMATION_COLS: {len(PENDING_TIMING_CONFIRMATION_COLS)} vars")
print(f"INTRAPARTUM_PREDICTOR_EXCLUDE_COLS: {len(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)} vars")
""")


# ── Section C3 ─────────────────────────────────────────────────────────────────
SC3_HEADER = md("eda-c-s03-header", """
## Section C3 — Load the Cleaned Dataset from the Data Cleaning B Manifest + Controlled Validation

### One deterministic upstream input contract
EDA C has exactly **one** canonical B→C input path (2026-08-31 C3 correction):

```
cleaning_b_manifest.json  (REQUIRED, project-root only)
  → output_file            → the exact cleaned workbook
  → output_sha256          → byte-for-byte integrity gate on that workbook
  → cleaned_rows/target_*  → cohort contract check
  → row_exclusions_applied → must be false (Data Cleaning B removes no analytical row)
  → export_for_eda_c       → must be true
→ authoritative B metadata (classification snapshot + type snapshot + feature dictionary)
→ ANALYSIS_VARS
→ cumulative Stage 1 ⊆ Stage 2 ⊆ Stage 3
```

- **No** `USE_LATEST_PROCESSED_BATCH` / "highest cleaned batch" discovery.
- **No** raw `work_df_batch18.xlsx` analytical fallback, and no
  `ALLOW_UNCLEANED_BATCH18_TEST_RUN` flag. A raw/structure-only pass, if ever
  needed, belongs in a separate developer harness, not in this notebook.
- **No** current-working-directory alternate for the manifest, the dataset, or
  the row-key sidecar — all three are read from the located project root only.
- If the manifest, the cleaned workbook, or the row-key sidecar is missing, or
  the SHA-256 does not match, or `row_exclusions_applied` is true, or
  `export_for_eda_c` is not true → EDA C **fails loud**.

### Controlled validation
- Original/source columns must exist in `variable_classification_minimal.csv`
  (preprocessing-level provenance list).
- B-created columns must be documented in `cleaning_b_feature_dictionary.csv`.
- Any column in **neither** raises an error — no silent acceptance.
- The only in-memory column change to the loaded workbook is technical: an
  `"Unnamed: 0"` pandas import artifact is dropped **if present** (disclosed;
  the canonical Batch 19 export does not contain it), and the internal
  row-alignment key `_row_key_delivery_id` is attached from the B sidecar.
- Cohort counts come from
  `analysis/preprocessing/src/preprocessing_config.py`
  (`CURRENT_APPROVED_COHORT_ROWS` / `_TARGET_N0` / `_TARGET_N1`; currently
  431 / 370 / 61) and are asserted unconditionally — Data Cleaning B is not
  permitted to change cohort membership.
- Duplicate **analytical** rows are checked on the exported analytical columns
  only, with `_row_key_delivery_id` excluded so a unique row key can never mask
  a genuine analytical duplicate. Any duplicate fails loud for review; EDA C
  never removes a row.

### Analysis frame — safety meaning of "read-only"
`df` is the source frame. EDA C removes **no analytical row** and **cleans /
mutates no source predictor value**. It may drop the `"Unnamed: 0"` import
artifact in memory and attach `_row_key_delivery_id`; the canonical Batch 19
workbook on disk is never overwritten. `df_analysis` holds the target +
`ANALYSIS_VARS`; derived features are added to `df_analysis` in Part 3 (C9).

### Stage-aware universe (cumulative Stage 1 / 2 / 3 prediction horizons)
EDA C analyses **one unified stage-aware predictor universe** — `predictor_allowed`,
`secondary_near_delivery_predictor`, and
`intrapartum_predictor_exclude_from_prelabor_model` are screened together in a
single pipeline (the main analytical EDA is **not** repeated three separate
times). Cumulative stage membership **is** constructed here in C3
(`STAGE_1_COLS ⊆ STAGE_2_COLS ⊆ STAGE_3_COLS`, `EARLIEST_ENTRY_STAGE`), driven
purely by the authoritative classification label — never by column name, timing
map, or target association. Stage-specific candidate / modeling handoffs are
produced later in C13. Keeping each variable's classification attached all the
way through screening is what lets the modeling boundary apply a horizon
restriction without re-deriving timing eligibility.

### How `ANALYSIS_VARS` is built (same way every run — no manual override)
1. **`ORIGINAL_ANALYSIS_VARS`** — original preprocessing-level columns whose
   **current authoritative classification** (from the Data Cleaning B
   classification snapshot, `cleaning_b_variable_classification_snapshot.csv`)
   is one of `predictor_allowed` / `secondary_near_delivery_predictor` /
   `intrapartum_predictor_exclude_from_prelabor_model`, still present in `df`,
   not in `_FORBIDDEN_COLS`. Membership is restricted to names that exist in the
   preprocessing-level `variable_classification_minimal.csv` (that CSV is
   provenance for *which columns are original*, **not** the authority for their
   current classification *values* — the B snapshot is).
2. **`B_CREATED_ANALYSIS_VARS`** — Data Cleaning B replacement columns from
   `cleaning_b_feature_dictionary.csv`, present in `df`, `intended_use ==
   "review"`, `leakage_status == "no"`, `predictor_classification != "UNSET"`,
   not an ID/target/leakage/post-delivery/source-text column, not a
   `__missing_ind` indicator, not derived from a pending-timing source.

`ANALYSIS_VARS = ORIGINAL_ANALYSIS_VARS + B_CREATED_ANALYSIS_VARS` (deduplicated,
order preserved). `intrapartum_candidate_pending_timing_confirmation` variables
are in `_FORBIDDEN_COLS` and never enter any stage or `ANALYSIS_VARS` (timing
unresolved by definition; currently 0 members). The Batch 19 workbook resolved
from the B manifest is the single cleaned-data source of truth for all of this.
""")

SC3_LOAD = code("eda-c-s03-load", """
# Cohort 448->447, target 386->385/62 as of 2026-07-30 (Decision 32: one
# analytical record excluded in preprocessing for placenta_accreta==1 OR
# placenta_previa==1 -- upstream of Data Cleaning B, not a DCB row exclusion).
# Cohort 447->431, target 385/62->370/61 as of 2026-08-15 (Decision 67
# relocated to the canonical early cohort-eligibility section of
# preprocessing -- also upstream of Data Cleaning B, not a DCB row
# exclusion). BMI_after's Decision 69 reclassification does not change
# these counts (classification-only change).
# Frozen-cohort baseline centralization (2026-08-16): previously an
# independent literal here -- one of 7 independently-duplicated copies
# across the pipeline. Now loaded from
# analysis/preprocessing/src/preprocessing_config.py's
# CURRENT_APPROVED_COHORT_ROWS/TARGET_N0/TARGET_N1 -- the single
# authoritative source. This is a CURRENT FROZEN-COHORT REGRESSION GATE, not
# a permanent architectural invariant; a future approved cohort revision
# requires updating preprocessing_config.py alone.
_ppcfg_spec = importlib.util.spec_from_file_location(
    "preprocessing_config", _root / "analysis" / "preprocessing" / "src" / "preprocessing_config.py"
)
_preprocessing_config = importlib.util.module_from_spec(_ppcfg_spec)
_ppcfg_spec.loader.exec_module(_preprocessing_config)
EXPECTED_ROWS = _preprocessing_config.CURRENT_APPROVED_COHORT_ROWS
EXPECTED_N0 = _preprocessing_config.CURRENT_APPROVED_TARGET_N0
EXPECTED_N1 = _preprocessing_config.CURRENT_APPROVED_TARGET_N1

# ── Path constants ────────────────────────────────────────────────────────────
CLEANED_PROCESSED_SUBPATH = "outputs/data_cleaning/processed"
CLEANED_AUDIT_SUBPATH = "outputs/data_cleaning/audit"
_B_MANIFEST_REL = CLEANED_AUDIT_SUBPATH + "/cleaning_b_manifest.json"
_B_ROW_KEY_REL = CLEANED_AUDIT_SUBPATH + "/cleaning_b_output_delivery_id_key.csv"
# Diagnostic-only path constant: used ONLY by C4c's raw-vs-cleaned before/after
# value comparison, NEVER as an analytical input for EDA C. The raw batch18
# analytical fallback (ALLOW_UNCLEANED_BATCH18_TEST_RUN), USE_LATEST_PROCESSED_BATCH
# "newest cleaned batch" discovery, and IS_TEST_RUN were ALL retired 2026-08-31
# (C3 correction): EDA C has exactly one canonical input, resolved from the Data
# Cleaning B manifest and verified against its recorded SHA-256.
PREPROC_PROCESSED_SUBPATH = "outputs/preprocessing/processed"


def _find_first(paths):
    for p in filter(None, paths):
        if p.is_file():
            return p
    return None


def _file_sha256(path):
    _hh = hashlib.sha256()
    with open(path, "rb") as _f:
        for _block in iter(lambda: _f.read(1 << 20), b""):
            _hh.update(_block)
    return _hh.hexdigest()


# ── 1. REQUIRED Data Cleaning B manifest (project-root only; no CWD fallback) ──
import json as _json
_B_MANIFEST_PATH = _root / _B_MANIFEST_REL
if not _B_MANIFEST_PATH.is_file():
    raise FileNotFoundError(
        f"Data Cleaning B manifest not found at {_B_MANIFEST_REL} (under the "
        "located project root). This file is the canonical B->C handoff -- it "
        "names the exact cleaned workbook and its SHA-256. There is NO "
        "current-working-directory fallback and NO 'newest cleaned batch' "
        "discovery (both retired 2026-08-31). Run Data Cleaning B "
        "(notebooks/data_cleaning/03_data_cleaning_b_after_initial_eda.ipynb) "
        "with SAVE_CLEANED_DATASET = True to (re)generate it."
    )
with open(_B_MANIFEST_PATH, "r", encoding="utf-8") as _mf:
    _b_manifest = _json.load(_mf)
_b_manifest_sha256 = _file_sha256(_B_MANIFEST_PATH)
print(f"Data Cleaning B manifest: {_B_MANIFEST_REL}")
print(f"  SHA-256 : {_b_manifest_sha256[:24]}...")

# ── 5a. Manifest schema + handoff-contract fields must be present and valid ────
_man_required = [
    "stage", "export_for_eda_c", "output_file", "output_sha256",
    "cleaned_rows", "target_0", "target_1", "row_exclusions_applied",
    "cleaned_columns_total", "scope_original_columns", "b_created_columns",
]
_man_missing = [k for k in _man_required if k not in _b_manifest]
if _man_missing:
    raise RuntimeError(
        "cleaning_b_manifest.json is missing required B->C handoff field(s): "
        f"{_man_missing}. Regenerate it from Data Cleaning B's export step."
    )
if str(_b_manifest["stage"]) != "data_cleaning_b":
    raise RuntimeError(
        f"cleaning_b_manifest.json stage is {_b_manifest['stage']!r}, expected "
        "'data_cleaning_b' -- this is not the Data Cleaning B handoff manifest."
    )
if _b_manifest["export_for_eda_c"] is not True:
    raise RuntimeError(
        "cleaning_b_manifest.json export_for_eda_c is "
        f"{_b_manifest['export_for_eda_c']!r}, expected true -- the cleaned "
        "dataset was not marked ready for EDA C. Re-run Data Cleaning B's export."
    )

# ── 6. Data Cleaning B is NOT allowed to remove analytical rows ───────────────
if bool(_b_manifest["row_exclusions_applied"]):
    raise RuntimeError(
        "cleaning_b_manifest.json row_exclusions_applied is true. Under the "
        "current project architecture Data Cleaning B performs NO analytical "
        "row removal -- the approved cohort is fixed upstream in preprocessing "
        "(preprocessing_config.py). A true value here means either DCB did "
        "something it must not, or the manifest is wrong. EDA C fails loud "
        "rather than silently accepting a changed cohort."
    )

# ── 2. Resolve the dataset from the manifest (no hardcoded batch number) ──────
CLEANED_DATASET_NAME = str(_b_manifest["output_file"]).strip()
DATA_PATH = _root / CLEANED_PROCESSED_SUBPATH / CLEANED_DATASET_NAME
if not DATA_PATH.is_file():
    raise FileNotFoundError(
        "The cleaned workbook named by the manifest "
        f"({CLEANED_PROCESSED_SUBPATH}/{CLEANED_DATASET_NAME}) is not on disk. "
        "The manifest and the processed/ folder are out of sync -- re-run Data "
        "Cleaning B's export step."
    )
if not zipfile.is_zipfile(DATA_PATH):
    raise ValueError(f"Not a valid .xlsx file: {DATA_PATH.name}")

df = pd.read_excel(DATA_PATH)

# ── 10. Import-artifact handling (technical only; disclosed) ──────────────────
_UNNAMED_ARTIFACT_PRESENT = "Unnamed: 0" in df.columns
if _UNNAMED_ARTIFACT_PRESENT:
    df = df.drop(columns=["Unnamed: 0"])
_N_ANALYTICAL_COLS_LOADED = df.shape[1]  # after the artifact drop, before the row key

# ── 4. Byte-for-byte integrity gate against the manifest ─────────────────────
_sha256 = _file_sha256(DATA_PATH)
_mtime = _dt.fromtimestamp(DATA_PATH.stat().st_mtime, _tz.utc).isoformat(timespec="seconds")
_fsize_kb = DATA_PATH.stat().st_size / 1024
if DATA_PATH.name != str(_b_manifest["output_file"]).strip():
    raise RuntimeError(
        f"Loaded file name {DATA_PATH.name!r} != manifest output_file "
        f"{_b_manifest['output_file']!r}."
    )
if _sha256 != str(_b_manifest["output_sha256"]).strip():
    raise RuntimeError(
        "DATASET INTEGRITY FAILED: the SHA-256 of the loaded workbook does not "
        "match cleaning_b_manifest.json output_sha256.\\n"
        f"  loaded  : {_sha256}\\n"
        f"  manifest: {_b_manifest['output_sha256']}\\n"
        "A same-named but non-canonical workbook is in processed/. Re-run Data "
        "Cleaning B's export step, or restore the canonical file."
    )

_n0 = int((df[TARGET_COL] == 0).sum()) if TARGET_COL in df.columns else None
_n1 = int((df[TARGET_COL] == 1).sum()) if TARGET_COL in df.columns else None

print("Provenance manifest (dataset resolved from the B manifest)")
print(f"  File     : {DATA_PATH.name}  (cleaned B output)")
print(f"  Loaded from: {CLEANED_PROCESSED_SUBPATH}/{DATA_PATH.name}")
print(f"  SHA-256  : {_sha256[:24]}...  == manifest output_sha256  [OK]")
print(f"  Modified : {_mtime} UTC")
print(f"  Size     : {_fsize_kb:.1f} KB")
print(f"  Shape    : {df.shape[0]} rows x {df.shape[1]} cols "
      f"({'dropped 1 Unnamed:0 import artifact' if _UNNAMED_ARTIFACT_PRESENT else 'no Unnamed:0 artifact -- branch inactive'})")
print(f"  Target 0 : {_n0}  |  Target 1 : {_n1}")

# ── 5b. Manifest data contract vs the loaded data ────────────────────────────
_contract_errors = []
if int(_b_manifest["cleaned_rows"]) != len(df):
    _contract_errors.append(
        f"manifest cleaned_rows={_b_manifest['cleaned_rows']} != loaded rows={len(df)}"
    )
if _n0 is not None and int(_b_manifest["target_0"]) != _n0:
    _contract_errors.append(f"manifest target_0={_b_manifest['target_0']} != loaded {_n0}")
if _n1 is not None and int(_b_manifest["target_1"]) != _n1:
    _contract_errors.append(f"manifest target_1={_b_manifest['target_1']} != loaded {_n1}")
# cleaned_columns_total counts the exported analytical columns. `df` here has had
# the Unnamed:0 import artifact removed (if it was present) and does NOT yet
# carry _row_key_delivery_id -- so it should equal cleaned_columns_total exactly.
_man_cols_total = int(_b_manifest["cleaned_columns_total"])
# `df` here has had the Unnamed:0 import artifact removed (if present) and does
# NOT yet carry _row_key_delivery_id, so its column count must equal
# cleaned_columns_total exactly. (scope_original_columns / b_created_columns are
# NOT additive with cleaned_columns_total -- some scope columns are replaced or
# dropped by B -- so they are recorded for provenance, not summed here.)
if _N_ANALYTICAL_COLS_LOADED != _man_cols_total:
    _contract_errors.append(
        f"manifest cleaned_columns_total={_man_cols_total} != loaded analytical "
        f"columns={_N_ANALYTICAL_COLS_LOADED} "
        f"(Unnamed:0 artifact {'was' if _UNNAMED_ARTIFACT_PRESENT else 'was not'} present)"
    )
if _contract_errors:
    raise RuntimeError(
        "DATA CLEANING B MANIFEST CONTRACT FAILED: " + "; ".join(_contract_errors)
    )
print("  Manifest data contract: PASS "
      "(rows / target / column-count all agree with cleaning_b_manifest.json)")

# ── 7 + 8. Row-key sidecar: project-root pinned, structurally validated ──────
# delivery_id is NEVER a feature and NEVER an exported dataset column (C0 safety
# rule) -- only ever a sidecar row-alignment key. Data Cleaning B writes
# cleaning_b_output_delivery_id_key.csv capturing delivery_id in the exact row
# order of the cleaned workbook (cleaning_b_part5_export_cleaned_dataset.py).
_row_key_path = _root / _B_ROW_KEY_REL
if not _row_key_path.is_file():
    raise FileNotFoundError(
        f"Row-key sidecar not found at {_B_ROW_KEY_REL} (under the project root; "
        "no CWD fallback). Data Cleaning B writes it on every export -- re-run "
        "its export step."
    )
_row_key_df = pd.read_csv(_row_key_path)
_row_key_sidecar_sha256 = _file_sha256(_row_key_path)
_rk_errors = []
for _c in ("row_index", "delivery_id"):
    if _c not in _row_key_df.columns:
        _rk_errors.append(f"missing required column {_c!r}")
if not _rk_errors:
    if len(_row_key_df) != len(df):
        _rk_errors.append(
            f"row count {len(_row_key_df)} != loaded dataset row count {len(df)} "
            "(sidecar stale relative to the workbook)"
        )
    _ri = _row_key_df["row_index"]
    if _ri.isna().any():
        _rk_errors.append(f"{int(_ri.isna().sum())} missing row_index value(s)")
    elif _ri.duplicated().any():
        _rk_errors.append(f"{int(_ri.duplicated().sum())} duplicate row_index value(s)")
    elif set(_ri.astype(int)) != set(range(len(df))):
        _rk_errors.append("row_index is not exactly 0..n-1 (gaps or out-of-range values)")
    _did = _row_key_df["delivery_id"]
    if _did.isna().any():
        _rk_errors.append(f"{int(_did.isna().sum())} missing delivery_id value(s)")
    # Upstream contract: cleaning_b_part5_export_cleaned_dataset.py SB7 asserts
    # "_row_key_delivery_id: unique per row (1:1 with the canonical source)", so
    # EDA C asserts the same rather than inventing the guarantee.
    if _did.duplicated().any():
        _rk_errors.append(
            f"{int(_did.duplicated().sum())} duplicate delivery_id value(s) -- "
            "violates the Data Cleaning B export postcondition (1:1 row key)"
        )
if _rk_errors:
    raise RuntimeError(
        f"ROW-KEY SIDECAR VALIDATION FAILED ({_row_key_path.name}): "
        + "; ".join(_rk_errors)
    )
df["_row_key_delivery_id"] = _row_key_df.sort_values("row_index")["delivery_id"].to_numpy()
_rk_id_col = "deliver" + "y_id"  # label only; the value column is never printed
print(f"  Row-key sidecar   : {_B_ROW_KEY_REL}")
print(f"    SHA-256 : {_row_key_sidecar_sha256[:24]}...  (recorded for change detection)")
print(f"    schema  : row_index + {_rk_id_col} present; {len(_row_key_df)} rows == dataset rows")
print(f"    row_index : exactly 0..{len(df) - 1}, no gaps / dupes / missing")
print(f"    {_rk_id_col}: no missing values; unique 1:1 row key (per the DCB export contract)")
print("    PROVENANCE LIMITATION: cleaning_b_manifest.json carries NO "
      "cryptographic sidecar-binding field, so equal row count + a clean "
      "0..n-1 row_index is the ONLY available evidence that this sidecar came "
      "from the same B export -- consistency evidence, not cryptographic proof. "
      "(Adding such a field would require modifying Data Cleaning B -- out of "
      "scope for this C3 correction.)")


# Full (untruncated) hashes for the two metadata inputs, so the manifest
# written in Part 5 can record provenance for all three canonical inputs,
# not the dataset alone -- closes the gap where the manifest previously
# recorded only an absolute path string (not portable across a folder
# rename) with no hash to verify it against.
_classification_sha256 = _file_sha256(CLASSIFICATION_PATH)
_type_schema_sha256 = (
    _file_sha256(VARIABLE_TYPE_SCHEMA_PATH)
    if VARIABLE_TYPE_SCHEMA_PATH is not None and Path(VARIABLE_TYPE_SCHEMA_PATH).is_file()
    else None
)
print(f"  Classification CSV SHA-256: {_classification_sha256[:24]}...")
print(f"  Type-schema CSV SHA-256   : "
      f"{_type_schema_sha256[:24] + '...' if _type_schema_sha256 else 'N/A (schema not found)'}")

# Data Cleaning B classification/type-schema snapshot provenance (2026-08-27,
# Decision 91, Gap 2; corrected 2026-08-28, Gap 2 follow-up): these two files
# -- not the raw preprocessing CSVs hashed above -- are the actual
# authoritative source for BOTH _cols_for()/ORIGINAL_ANALYSIS_VARS
# eligibility AND infer_var_type()'s type inference (VARIABLE_TYPE_MAP, built
# above from eda_c_type_schema_snapshot). Hashed here, by the same file-hash
# helper, so Part 5's manifest can record real provenance for its
# authoritative inputs, not just the preprocessing-level CSVs it happens to
# also read for audit comparison.
_B_CLASSIFICATION_SNAPSHOT_PATH = _root / classification_lineage.DATA_CLEANING_B_CLASSIFICATION_REL
_B_TYPE_SCHEMA_SNAPSHOT_PATH = _root / classification_lineage.DATA_CLEANING_B_TYPE_SCHEMA_REL
_b_classification_snapshot_sha256 = _file_sha256(_B_CLASSIFICATION_SNAPSHOT_PATH)
_b_type_schema_snapshot_sha256 = _file_sha256(_B_TYPE_SCHEMA_SNAPSHOT_PATH)
print(f"  Data Cleaning B classification snapshot SHA-256: "
      f"{_b_classification_snapshot_sha256[:24]}... (authoritative for EDA C eligibility)")
print(f"  Data Cleaning B type-schema snapshot SHA-256    : "
      f"{_b_type_schema_snapshot_sha256[:24]}... (authoritative for EDA C type inference)")

# ── B feature dictionary: already loaded + used to enrich TIMING_MAP/DOMAIN_MAP/
#    CLINICAL_TIER in C2 (metadata contract source #3). Reuse it here; only load
#    as a fallback if C2 somehow did not (e.g. a manual partial-cell rerun).
if ("B_FEATURE_DICT" not in dir()) or (B_FEATURE_DICT is None):
    _fd_path = _find_first([
        (_root / CLEANED_AUDIT_SUBPATH / "cleaning_b_feature_dictionary.csv") if _root else None,
    ])
    if _fd_path is not None:
        B_FEATURE_DICT = pd.read_csv(_fd_path)
        B_CREATED_COLS = set(B_FEATURE_DICT["new_column"].dropna().astype(str))
        print(f"  B feature dictionary (fallback load): {len(B_CREATED_COLS)} columns from {_fd_path.resolve()}")
if "B_CREATED_COLS" not in dir():
    B_CREATED_COLS = set()
print(f"  B feature dictionary: {len(B_CREATED_COLS)} B-registered columns "
      f"(metadata already applied in C2).")
_b_feature_dict_sha256 = (
    _file_sha256(_root / CLEANED_AUDIT_SUBPATH / "cleaning_b_feature_dictionary.csv")
    if (_root / CLEANED_AUDIT_SUBPATH / "cleaning_b_feature_dictionary.csv").is_file()
    else None
)

# NOTE: the B manifest itself was already loaded + schema/contract-validated at
# the top of this cell (it now DRIVES dataset resolution). `_b_manifest`,
# `_b_manifest_sha256`, and `_B_MANIFEST_PATH` are already in scope here.

# ── Controlled validation (schema gate) ────────────────────────────────────────
# (1) original columns must be in the classification CSV;
# (2) B-created columns must be documented in the feature dictionary;
# (3) any column in neither -> error. No silent acceptance.
_errors = []
_data_cols = set(df.columns)
TECHNICAL_INTERNAL_COLS = {"_row_key_delivery_id"}
_validation_cols = _data_cols - TECHNICAL_INTERNAL_COLS
_class_cols = set(classification_df["column_name"])
_undocumented = sorted(_validation_cols - _class_cols - B_CREATED_COLS)
_b_present = sorted((_validation_cols - _class_cols) & B_CREATED_COLS)
if _undocumented:
    _errors.append(
        f"Undocumented columns (not in classification CSV nor B feature dictionary) "
        f"({len(_undocumented)}): {_undocumented[:8]}{'...' if len(_undocumented) > 8 else ''}"
    )
if TARGET_COL not in df.columns:
    _errors.append(f"Target column '{TARGET_COL}' missing from dataset")

# ── 9. Duplicate ANALYTICAL rows -- computed WITHOUT _row_key_delivery_id ─────
# The internal row key is unique by construction, so including it would make
# every row look distinct and hide a genuine analytical duplicate. Check the
# exported analytical columns only. EDA C never removes a row; a duplicate here
# fails loud for upstream review.
_analytical_frame = df.drop(columns=[c for c in TECHNICAL_INTERNAL_COLS if c in df.columns])
_n_dup_analytical = int(_analytical_frame.duplicated().sum())
if _n_dup_analytical > 0:
    _errors.append(
        f"Duplicate analytical rows: {_n_dup_analytical} "
        f"(checked on {_analytical_frame.shape[1]} analytical columns; "
        "_row_key_delivery_id excluded)"
    )

# Cohort validation: preprocessing_config.py is the count authority.
# Data Cleaning B applies NO row exclusions (asserted from the manifest at the
# top of this cell), so the cleaned cohort MUST match the approved upstream
# cohort exactly. No "if row_exclusions: report else assert" branch any more.
if df.shape[0] != EXPECTED_ROWS:
    _errors.append(f"Row count: expected {EXPECTED_ROWS} (preprocessing_config), got {df.shape[0]}")
if TARGET_COL in df.columns and (_n0 != EXPECTED_N0 or _n1 != EXPECTED_N1):
    _errors.append(
        f"Target distribution: expected 0={EXPECTED_N0}/1={EXPECTED_N1} "
        f"(preprocessing_config), got 0={_n0}/1={_n1}"
    )

if _errors:
    raise ValueError("Dataset validation FAILED:\\n" + "\\n".join(f"  - {e}" for e in _errors))

print(f"  Duplicate analytical rows (excl. _row_key_delivery_id): {_n_dup_analytical}")
print(f"  Cohort: {df.shape[0]} rows, target {_n0}/{_n1} == preprocessing_config approved cohort")
print(f"  Validation PASSED ({len(_b_present)} documented B-created columns accepted)")

# ── Build analysis frame ───────────────────────────────────────────────────────
# The candidate universe is ALWAYS rebuilt from the authoritative Data Cleaning
# B classification snapshot -- there is no manual FINAL_CORE_VARS / candidate-pool
# override on the canonical EDA C path (retired 2026-08-31).
# ── ORIGINAL_ANALYSIS_VARS: unified master predictor universe ─────────────
# Decision 65 (2026-08-12): the union of all three approved classifications
# -- predictor_allowed, secondary_near_delivery_predictor, and
# intrapartum_predictor_exclude_from_prelabor_model -- still present in df.
# This is EDA C's single master candidate pool; it is NOT split by horizon
# here. Each variable's original classification is preserved as metadata
# (see predictor_classification, populated in eda_c_part4_screening.py) so
# the modeling boundary can later derive pre-labor / near-delivery /
# intrapartum eligibility from this same pool without re-deriving it.
_MASTER_UNIVERSE_LABELS = (
    set(PREDICTOR_ALLOWED_COLS)
    | set(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)
    | set(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)
)
# _FORBIDDEN_COLS exclusion added here 2026-08-16 (previously a no-op for
# this list, since every prior _FORBIDDEN_COLS member's classification
# category was disjoint from _MASTER_UNIVERSE_LABELS -- see
# MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS above for the first
# exception: gestational_age_at_PPROM_days is classified
# secondary_near_delivery_predictor but must not enter ANALYSIS_VARS).
# 2026-08-27 correction (Decision 91, Gap 2, corrected same day after a
# live-execution regression was caught -- see below): classification
# VALUES are sourced from eda_c_classification_snapshot (the Data
# Cleaning B snapshot), never from the raw classification_df -- see the
# divergence guard above. MEMBERSHIP, however, must stay restricted to
# ORIGINAL preprocessing-level column names (classification_df's own
# column_name set) -- an earlier version of this fix iterated the full
# snapshot instead, which also contains B-created rows and let at least
# one B-created column (weight_in_pregnancy__missing_ind,
# intended_use="secondary" in the feature dictionary, deliberately NOT
# "review") bypass B_CREATED_ANALYSIS_VARS's stricter
# intended_use/leakage_status/UNSET-metadata filters entirely via this
# weaker path -- caught by a live n_eligible_pool 78->79 regression
# during this same correction pass's execution, not by static review.
# B-created columns must reach ANALYSIS_VARS only through
# B_CREATED_ANALYSIS_VARS below, never through this list.
_ORIGINAL_PREPROCESSING_COLUMN_NAMES = set(classification_df["column_name"])
ORIGINAL_ANALYSIS_VARS = [
    c for c in eda_c_classification_snapshot["column_name"]
    if c in _MASTER_UNIVERSE_LABELS
    and c in df.columns
    and c not in _FORBIDDEN_COLS
    and c in _ORIGINAL_PREPROCESSING_COLUMN_NAMES
]

# ── B_CREATED_ANALYSIS_VARS: approved Data Cleaning B replacement columns ──
# Still sourced from the feature dictionary (cleaning_b_feature_dictionary.csv),
# not the classification snapshot -- the feature dictionary carries the
# additional model_entry_mode/redundant_with/domain/timing metadata this
# loop needs that the classification snapshot alone does not. The raw
# preprocessing-level variable_classification_minimal.csv is never edited
# to add B-created columns; B-created columns are picked up here from
# the feature dictionary B itself already produces (and separately
# carried into eda_c_classification_snapshot above for classification
# purposes only).
#
# B_CREATED_PREDICTOR_CLASSIFICATION: retired as a local override,
# 2026-08-16 (missing-data architecture correction, Decision 70's
# centralized registry). This is now a live projection of Data Cleaning
# B's own exported feature dictionary (cleaning_b_feature_dictionary.csv,
# column 'predictor_classification'), never hardcoded here -- EDA C must
# not maintain its own local override dict. Any B-created column whose
# exported predictor_classification is still "UNSET" is ineligible for
# model-candidate promotion (enforced below, reported explicitly) --
# never guessed or inferred here.
if B_FEATURE_DICT is not None and "predictor_classification" in B_FEATURE_DICT.columns:
    B_CREATED_PREDICTOR_CLASSIFICATION = dict(
        zip(B_FEATURE_DICT["new_column"].astype(str), B_FEATURE_DICT["predictor_classification"].astype(str))
    )
else:
    B_CREATED_PREDICTOR_CLASSIFICATION = {}
# model_entry_mode / redundant_with (2026-08-27 correction, Part A9/A10):
# same live-projection pattern as B_CREATED_PREDICTOR_CLASSIFICATION above
# -- covers both B-created derived columns AND the raw source columns B
# also now registers feature-dictionary entries for (BMI_after,
# weight_in_pregnancy, gestational_age_at_PPROM_days, PPROM). Surfaced as
# disclosure on the candidate-pool row (eda_c_part4_screening.py) so
# "eligible" is never mistaken for "safe to feed directly into a design
# matrix" for a transform_source_only column.
if B_FEATURE_DICT is not None and "model_entry_mode" in B_FEATURE_DICT.columns:
    B_CREATED_MODEL_ENTRY_MODE = dict(
        zip(B_FEATURE_DICT["new_column"].astype(str), B_FEATURE_DICT["model_entry_mode"].astype(str))
    )
else:
    B_CREATED_MODEL_ENTRY_MODE = {}
if B_FEATURE_DICT is not None and "redundant_with" in B_FEATURE_DICT.columns:
    B_CREATED_REDUNDANT_WITH = dict(
        zip(B_FEATURE_DICT["new_column"].astype(str), B_FEATURE_DICT["redundant_with"].astype(str))
    )
else:
    B_CREATED_REDUNDANT_WITH = {}
# diagnosis_year__missing_ind removed 2026-08-18 (finalized project
# decision, supersedes the whitelist entry present here through
# 2026-08-16): the project decided diagnosis_year and its whole family
# (diagnosis_year_cat, diagnosis_year__missing_ind) must never be
# predictor-eligible. Leaving this column whitelisted here relied solely
# on its feature-dictionary predictor_classification staying "UNSET"
# forever to stay excluded -- exactly the single point of failure that
# let it briefly leak to "predictor_allowed" on 2026-08-16 before being
# caught (see docs/clinical_decisions/manual_decisions_log.md, Decision
# 71's technical-closure addendum). Removing it from this whitelist means
# the general "no __missing_ind column enters the candidate pool" rule
# below now excludes it unconditionally, regardless of what its
# predictor_classification metadata says -- a second, independent
# guarantee, not just the UNSET-metadata gate. Do not re-add without a
# new decision-log entry approving predictor eligibility for this family.
APPROVED_B_CREATED_MISSING_INDICATORS = set()
B_CREATED_ANALYSIS_VARS = []
B_CREATED_EXCLUDED_UNSET_METADATA = []
if B_FEATURE_DICT is not None and "new_column" in B_FEATURE_DICT.columns:
    _fd = B_FEATURE_DICT.copy()
    for _c in ("intended_use", "leakage_status"):
        if _c in _fd.columns:
            _fd[_c] = _fd[_c].astype("string").str.strip()
    _fd_eligible = _fd[
        _fd["new_column"].isin(df.columns)
        & (_fd["intended_use"] == "review" if "intended_use" in _fd.columns else True)
        & (_fd["leakage_status"] == "no" if "leakage_status" in _fd.columns else True)
        & (
            (~_fd["new_column"].astype(str).str.endswith("__missing_ind"))
            | (_fd["new_column"].astype(str).isin(APPROVED_B_CREATED_MISSING_INDICATORS))
        )
        & (~_fd["new_column"].astype(str).isin(_FORBIDDEN_COLS))
        & (~_fd["new_column"].astype(str).isin(ID_COLS + TARGET_COLS))
    ]
    if "source_column" in _fd_eligible.columns:
        # Defensive guard: never pull in anything derived from pending
        # intrapartum timing-confirmation variables -- that is the one
        # class still genuinely excluded (timing unresolved by
        # definition). Variables derived from
        # intrapartum_predictor_exclude_from_prelabor_model sources are
        # NOT excluded here (removed 2026-08-13, Decision 65 / multi-
        # horizon plan Batch 2) -- that class is now part of the unified
        # master pool; horizon eligibility is decided only at the
        # modeling boundary, not here.
        _fd_eligible = _fd_eligible[
            ~_fd_eligible["source_column"].astype(str).isin(
                set(PENDING_TIMING_CONFIRMATION_COLS)
            )
        ]
    # UNSET-metadata gate (2026-08-16): a B-created column with an
    # unresolved predictor_classification in the exported feature
    # dictionary must not be promoted to the candidate pool, regardless
    # of otherwise passing every check above.
    if "predictor_classification" in _fd_eligible.columns:
        _unset_mask = _fd_eligible["predictor_classification"].astype(str) == "UNSET"
        B_CREATED_EXCLUDED_UNSET_METADATA = _fd_eligible.loc[_unset_mask, "new_column"].astype(str).tolist()
        _fd_eligible = _fd_eligible[~_unset_mask]
    B_CREATED_ANALYSIS_VARS = _fd_eligible["new_column"].astype(str).tolist()
    if B_CREATED_EXCLUDED_UNSET_METADATA:
        print(
            f"B-created column(s) excluded from model-candidate promotion -- "
            f"predictor_classification still UNSET in the exported feature "
            f"dictionary: {B_CREATED_EXCLUDED_UNSET_METADATA}"
        )

# ── Combine, deduplicated, order preserved ─────────────────────────────────
ANALYSIS_VARS = list(dict.fromkeys(ORIGINAL_ANALYSIS_VARS + B_CREATED_ANALYSIS_VARS))

# Celestone is administered during pregnancy when there is a risk of preterm
# delivery, so it is available before delivery and is classified
# predictor_allowed; its presence in ANALYSIS_VARS is expected.

print(f"Building ANALYSIS_VARS from the authoritative B classification snapshot (two sources):")
print(f"  ORIGINAL_ANALYSIS_VARS (stage-eligible classifications, present in df): {len(ORIGINAL_ANALYSIS_VARS)}")
print(f"  B_CREATED_ANALYSIS_VARS (approved B replacement columns) : {len(B_CREATED_ANALYSIS_VARS)}")
if B_CREATED_ANALYSIS_VARS:
    print(f"    {B_CREATED_ANALYSIS_VARS}")
print(f"  ANALYSIS_VARS (combined, deduplicated)                   : {len(ANALYSIS_VARS)}")

# ── Validation: expected B-created replacements must be included ─────────
# weight_in_pregnancy_cat and BMI_after_cat removed from this required list
# 2026-07-31 (Decisions 39/40) -- both are now hard-excluded via
# DERIVED_INHERITS_SOURCE_EXCLUSION_COLS/_FORBIDDEN_COLS above, not required
# replacements. See the SUPERSEDED_RAW_VARS-style check just below, which
# now additionally asserts they are ABSENT.
# endometrioma_size_status, diagnosis_year__missing_ind, severe_PET_cat,
# and any_PET_cat removed from this required list 2026-08-16 (Data
# Cleaning B -> EDA C handoff repair, corrected same day on cross-check
# against docs/clinical_decisions/manual_decisions_log.md Decision 71,
# which explicitly listed all four as "Remaining UNSET entries
# (unresolved, pending future clinical/partner review, not guessed)" and
# under "Unresolved, pending clinical/partner review (not decided
# here)". At that time, only endometrioma_presence_laterality had an
# actual approved decision (Decision 70). Requiring the other four's
# presence here would either force an unapproved classification or
# permanently block this notebook; the UNSET-metadata gate above already
# excludes them correctly and reports them explicitly (not silently).
# Re-add any of them to this list only once its own decision-log entry
# approves it.
# endometrioma_size_status RE-ADDED 2026-08-19 (Decision 84): predictor
# eligibility approved (closes the forgotten-eligibility gap Decision 71
# left open). diagnosis_year__missing_ind is no longer created at all
# (Decision 72) -- nothing to re-add. severe_PET_cat/any_PET_cat remain
# intentionally deferred (Decision 71's standalone-predictor-eligibility
# question, non-blocking) -- not re-added.
# BMI_after_cat ADDED 2026-08-27 (Decision 89): predictor eligibility
# approved as the Stage 2/3 modeling representation for BMI_after,
# created in Data Cleaning B (unlike its retired Decision-21 namesake).
# adenomyosis_sonographic_features_status ADDED -- this is a documentation
# sync, not a new decision: Decision 85 (2026-08-25) already approved this
# variable's predictor eligibility at creation time (registered directly
# as predictor_allowed in Data Cleaning B's own classification_lineage
# call, unlike endometrioma_size_status which needed a separate later
# Decision 84 to lift an initial UNSET state). It has therefore already
# been entering ANALYSIS_VARS via the generic B_CREATED_ANALYSIS_VARS
# mechanism on every EDA C rerun since Decision 85 -- this list is a
# validation safeguard confirming that continues to hold, not the reason
# it started working.
# 2026-08-27 correction: BMI_after_cat and adenomyosis_sonographic_features_status
# REMOVED -- neither is materialized as a real df column any more (the
# former is now a documented-only, fold-safe-deferred representation; the
# latter is retired entirely, superseded by the multi-hot indicators
# below). Both would fail the `new_column in df.columns` gate in
# B_CREATED_ANALYSIS_VARS construction if listed here.
EXPECTED_B_CREATED_REPLACEMENT_VARS = [
    "endometrioma_presence_laterality",
    "endometrioma_size_status",
    "derived_endo_surgery_adhesion_status",
    "indication_for_induction_status",
    "adenomyosis_features_unknown",
] + [f"adenomyosis_feature_{_c}" for _c in range(1, 12)]
_missing_expected_replacements = [
    v for v in EXPECTED_B_CREATED_REPLACEMENT_VARS if v not in ANALYSIS_VARS
]
if _missing_expected_replacements:
    raise AssertionError(
        "ANALYSIS_VARS CONSTRUCTION FAILED: expected B-created replacement "
        f"variable(s) missing: {_missing_expected_replacements}. Check "
        "cleaning_b_feature_dictionary.csv -- intended_use/leakage_status "
        "values or presence in df may have changed."
    )

# ── Validation: derived variables hard-excluded by Decisions 39/40 must
# NOT be included, even though Data Cleaning B still creates them for
# descriptive/audit use ────────────────────────────────────────────────
_forbidden_derived_present = sorted(
    DERIVED_INHERITS_SOURCE_EXCLUSION_COLS & set(ANALYSIS_VARS)
)
if _forbidden_derived_present:
    raise AssertionError(
        "ANALYSIS_VARS CONSTRUCTION FAILED: derived variable(s) excluded by "
        f"Decision 40 unexpectedly present: {_forbidden_derived_present}. "
        "weight_in_pregnancy_cat must never enter the "
        "primary eligible candidate pool -- see "
        "docs/clinical_decisions/manual_decisions_log.md Decision 40. "
        "(BMI_after_cat was removed from this exclusion set 2026-08-27, "
        "Decision 89 -- it is now the approved derived representation.)"
    )

# ── Validation: superseded raw variables must NOT be included ─────────────
# weight_in_pregnancy: REMOVED from this list 2026-08-15 (Decision 67/69
# sync) -- this list predates Decision 65 (2026-08-12/13), which widened
# ORIGINAL_ANALYSIS_VARS to the union of predictor_allowed,
# secondary_near_delivery_predictor, and
# intrapartum_predictor_exclude_from_prelabor_model. weight_in_pregnancy
# is secondary_near_delivery_predictor and remains present in df (Data
# Cleaning B retains it as a plain numeric secondary variable -- only its
# _cat derivative was retired, Decision 40). It is therefore now expected
# to enter ANALYSIS_VARS as a Stage-2 screened variable; treating its
# presence as a construction failure was stale, not a still-valid guard.
# BMI_after: REMOVED from this list 2026-08-27 (Decision 86, supersedes
# Decision 69), then RE-ADDED the same day (Decision 89) once
# BMI_after_cat became its approved derived replacement -- unlike the
# intervening Decision-86-only state, BMI_after is once again expected to
# be ABSENT from ANALYSIS_VARS, but now via
# MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS (BMI_after remains a
# real, present column in df with its raw NaNs preserved for lineage/
# audit -- it is excluded from model-candidate screening only, not
# "absent from df" the way the endometrioma/PET raw variables below
# genuinely are). weight_in_pregnancy is unaffected and remains expected
# in ANALYSIS_VARS (no equivalent replacement variable exists for it).
# adenomyosis_sonographic_features_status ADDED 2026-08-27: retired
# combination-level categorical, superseded by the multi-hot indicators.
# endo_surgery_adhesiolysis / indication_for_induction_clean ADDED
# 2026-08-27: both raw sources are now dropped from the Data Cleaning B
# export (superseded by derived_endo_surgery_adhesion_status /
# indication_for_induction_status respectively), so both are genuinely
# absent from df -- the same pattern as the endometrioma/PET raw
# variables already in this list.
SUPERSEDED_RAW_VARS = [
    "endometrioma_size_clean",
    "endometrioma_place_clean", "endometrioma_laterality",
    "severe_PET", "any_PET",
    "adenomyosis_sonographic_features_status",
    "endo_surgery_adhesiolysis",
    "indication_for_induction_clean",
]
_unexpectedly_present_raw = [v for v in SUPERSEDED_RAW_VARS if v in ANALYSIS_VARS]
if _unexpectedly_present_raw:
    raise AssertionError(
        "ANALYSIS_VARS CONSTRUCTION FAILED: superseded raw variable(s) unexpectedly "
        f"present: {_unexpectedly_present_raw}. These should be absent from df "
        "(replaced by Data Cleaning B) -- re-check batch19."
    )
# BMI_after / gestational_age_at_PPROM_days: 2026-08-27 correction --
# PREVIOUSLY this block asserted raw BMI_after must NEVER appear in
# ANALYSIS_VARS (Decision 89's materialized BMI_after_cat could otherwise
# co-enter alongside it). That materialized column no longer exists (it
# is now a documented-only, fold-safe-deferred representation, never a
# real df column), so the original risk this guard protected against is
# now structurally impossible regardless of whether raw BMI_after is
# present. The check is inverted: both raw columns are now EXPECTED to be
# present (as ordinary secondary_near_delivery_predictor candidates,
# disclosed transform_source_only), and their would-be materialized
# derived counterparts are expected to be ABSENT (checked immediately
# below) -- a future accidental materialization of either would be the
# real risk this pair of checks now guards against.
if "BMI_after" not in ANALYSIS_VARS:
    raise AssertionError(
        "ANALYSIS_VARS CONSTRUCTION FAILED: raw BMI_after is unexpectedly absent "
        "from ANALYSIS_VARS (2026-08-27 correction expects it present, disclosed "
        "as model_entry_mode=transform_source_only)."
    )
if "gestational_age_at_PPROM_days" not in ANALYSIS_VARS:
    raise AssertionError(
        "ANALYSIS_VARS CONSTRUCTION FAILED: raw gestational_age_at_PPROM_days is "
        "unexpectedly absent from ANALYSIS_VARS (2026-08-27 correction expects it "
        "present, disclosed as model_entry_mode=transform_source_only)."
    )
for _deferred_col in ("BMI_after_cat", "weight_in_pregnancy_cat", "gestational_age_at_PPROM_days_timing_status"):
    if _deferred_col in ANALYSIS_VARS:
        raise AssertionError(
            f"ANALYSIS_VARS CONSTRUCTION FAILED: {_deferred_col} is present in "
            "ANALYSIS_VARS, but this representation must never be materialized as a "
            "real df column in Data Cleaning B (2026-08-27 correction -- its "
            "cutpoints must be fitted training-fold-only at modeling time). A real "
            "column with this name means Decision 89's cutpoint-location mechanism "
            "was accidentally reintroduced -- re-audit Data Cleaning B Section B5b."
        )

# ── Validation: pending timing-confirmation variables stay out of scope ─
_pending_in_analysis = sorted(set(PENDING_TIMING_CONFIRMATION_COLS) & set(ANALYSIS_VARS))
if _pending_in_analysis:
    raise AssertionError(
        "ANALYSIS_VARS CONSTRUCTION FAILED: pending timing-confirmation variable(s) "
        f"present: {_pending_in_analysis}. These variables must remain excluded "
        "until clinical confirmation that values were available before the "
        "intrapartum cesarean decision."
    )

print("Validation PASSED: expected B-created replacements/indicators present; "
      "retired or non-primary raw variables excluded from ANALYSIS_VARS; "
      "pending timing-confirmation variables correctly excluded.")

df_analysis = df[[TARGET_COL] + ANALYSIS_VARS].copy()
# Row-key continuation (never a feature -- see the load-time note above):
# df_analysis is carved from df by column selection, so the two are still
# row-position-identical at this exact instant; attaching here lets
# delivery_id keep traveling with each row through the rest of EDA C,
# through to the modeling matrix export (eda_c_part5_handoff.py).
df_analysis["_row_key_delivery_id"] = df["_row_key_delivery_id"].to_numpy()
print(f"Analysis frame: {df_analysis.shape[0]} rows x {df_analysis.shape[1]} cols "
      f"(target + {len(ANALYSIS_VARS)} predictors)")

# ── Cumulative prediction-stage architecture (Decision 65) ─────────────────────
# Adapted from a2_predictor_readiness/a2_part1_setup_scope.py (SB2_SCOPE): build
# strictly-nested cumulative Stage 1/2/3 pools from the AUTHORITATIVE Data
# Cleaning B classification snapshot -- never from column names or clinical
# intuition. Stage membership is a pure function of the classification label
# (see run_preprocessing.py classification_groups reason text / Decision 65):
#   predictor_allowed                                 -> earliest_entry_stage 1
#   secondary_near_delivery_predictor                 -> earliest_entry_stage 2
#   intrapartum_predictor_exclude_from_prelabor_model -> earliest_entry_stage 3
# intrapartum_candidate_pending_timing_confirmation (timing unresolved) never
# enters any stage -- already kept out of ANALYSIS_VARS via _FORBIDDEN_COLS.
_STAGE_BY_CLASSIFICATION = {
    "predictor_allowed": 1,
    "secondary_near_delivery_predictor": 2,
    "intrapartum_predictor_exclude_from_prelabor_model": 3,
}
_stage_cls_lookup = dict(zip(
    eda_c_classification_snapshot["column_name"].astype(str),
    eda_c_classification_snapshot["classification"].astype(str),
))
_unstaged_vars = {
    v: _stage_cls_lookup.get(v)
    for v in ANALYSIS_VARS
    if _stage_cls_lookup.get(v) not in _STAGE_BY_CLASSIFICATION
}
if _unstaged_vars:
    raise AssertionError(
        "STAGE CONSTRUCTION FAILED: ANALYSIS_VARS member(s) carry a classification "
        f"outside the cumulative-stage vocabulary: {_unstaged_vars}. Every predictor "
        "in the unified master pool must be predictor_allowed / "
        "secondary_near_delivery_predictor / "
        "intrapartum_predictor_exclude_from_prelabor_model."
    )
EARLIEST_ENTRY_STAGE = {
    v: _STAGE_BY_CLASSIFICATION[_stage_cls_lookup[v]] for v in ANALYSIS_VARS
}
# Order-preserving: authoritative B-snapshot column order, then any tail.
_snap_col_order = list(eda_c_classification_snapshot["column_name"].astype(str))
_ordered_analysis_vars = (
    [v for v in _snap_col_order if v in set(ANALYSIS_VARS)]
    + [v for v in ANALYSIS_VARS if v not in set(_snap_col_order)]
)
STAGE_1_COLS = [v for v in _ordered_analysis_vars if EARLIEST_ENTRY_STAGE[v] == 1]
STAGE_2_COLS = [v for v in _ordered_analysis_vars if EARLIEST_ENTRY_STAGE[v] <= 2]
STAGE_3_COLS = [v for v in _ordered_analysis_vars if EARLIEST_ENTRY_STAGE[v] <= 3]
assert set(STAGE_1_COLS) <= set(STAGE_2_COLS) <= set(STAGE_3_COLS), (
    "STAGE NESTING FAILED: Stage 1 must be a subset of Stage 2 must be a subset of Stage 3."
)
assert set(STAGE_2_COLS) - set(STAGE_1_COLS) == {
    v for v in ANALYSIS_VARS if EARLIEST_ENTRY_STAGE[v] == 2
}, "STAGE NESTING FAILED: (Stage 2 - Stage 1) must equal exactly the Stage-2 members."
assert set(STAGE_3_COLS) - set(STAGE_2_COLS) == {
    v for v in ANALYSIS_VARS if EARLIEST_ENTRY_STAGE[v] == 3
}, "STAGE NESTING FAILED: (Stage 3 - Stage 2) must equal exactly the Stage-3 members."
assert set(STAGE_3_COLS) == set(ANALYSIS_VARS), (
    "STAGE NESTING FAILED: cumulative Stage 3 must equal the full ANALYSIS_VARS universe."
)
print()
print("Cumulative prediction-stage architecture (Decision 65; from the B classification snapshot):")
print(f"  Stage 1 (pre-labor)                            : {len(STAGE_1_COLS)}")
print(f"  Stage 2 cumulative (pre-labor + near-delivery) : {len(STAGE_2_COLS)}")
print(f"  Stage 3 cumulative (+ intrapartum)             : {len(STAGE_3_COLS)}")
print(f"  earliest_entry_stage distribution             : "
      f"{pd.Series(EARLIEST_ENTRY_STAGE).value_counts().sort_index().to_dict()}")

# ── C3 metadata-contract validation (2026-08-31 C2 correction) ─────────────────
# Meaningful consistency checks over the ASSEMBLED universe -- not a "dict has
# >= N entries" size check. Every check below is a genuine integrity invariant.
_c3_meta_errors = []
_c3_meta_warnings = []

# C. every live B-stage candidate has classification metadata (non-UNSET).
_cls_lookup_all = dict(zip(eda_c_classification_snapshot["column_name"].astype(str),
                           eda_c_classification_snapshot["classification"].astype(str)))
_no_cls = [v for v in ANALYSIS_VARS if _cls_lookup_all.get(v, "UNSET") == "UNSET"]
if _no_cls:
    _c3_meta_errors.append(f"analysis variable(s) with no classification metadata: {_no_cls}")

# D. every live B-stage candidate has a type-schema entry (fail loud -- no dtype guess).
_no_type = [v for v in ANALYSIS_VARS if v not in VARIABLE_TYPE_MAP]
if _no_type:
    _c3_meta_errors.append(
        f"analysis variable(s) with no Data Cleaning B type-schema entry "
        f"(EDA C must not dtype-guess a B-stage type): {_no_type}"
    )

# E. every B-registered feature present in Batch19 has a feature-dictionary row.
if B_FEATURE_DICT is not None:
    _fd_cols = set(B_FEATURE_DICT["new_column"].astype(str))
    _orig_cols = set(classification_df["column_name"].astype(str))
    _b_in_df_no_fd = sorted((set(df.columns) - {"_row_key_delivery_id"} - _orig_cols) - _fd_cols)
    if _b_in_df_no_fd:
        _c3_meta_errors.append(
            f"Batch19 column(s) that are neither original preprocessing columns nor "
            f"documented in cleaning_b_feature_dictionary.csv: {_b_in_df_no_fd}"
        )

# F. predictor classification -> earliest stage mapping is valid for every universe member.
_bad_stage = [v for v in ANALYSIS_VARS if EARLIEST_ENTRY_STAGE.get(v) not in (1, 2, 3)]
if _bad_stage:
    _c3_meta_errors.append(f"analysis variable(s) with no valid earliest_entry_stage: {_bad_stage}")

# G. feature-dictionary 'stage', where explicitly set, agrees with the
#    classification-derived stage. A disagreement is DISCLOSED, not silently
#    reconciled -- classification always wins (see Finding 9 / section 9).
STAGE_METADATA_DISCREPANCIES = []
for _v, _fd_stage in (B_FEATURE_STAGE.items() if "B_FEATURE_STAGE" in dir() else []):
    _derived_stage = EARLIEST_ENTRY_STAGE.get(_v)
    if _derived_stage is not None and _fd_stage != _derived_stage:
        STAGE_METADATA_DISCREPANCIES.append({
            "variable": _v, "classification_derived_stage": _derived_stage,
            "feature_dictionary_stage": _fd_stage,
        })
if STAGE_METADATA_DISCREPANCIES:
    _c3_meta_warnings.append(
        "feature-dictionary 'stage' disagrees with the classification-derived "
        f"stage for {len(STAGE_METADATA_DISCREPANCIES)} variable(s) "
        f"(classification wins): {STAGE_METADATA_DISCREPANCIES}"
    )

# I. no retired / non-materialized representation is treated as a real Batch19 column.
_NON_MATERIALIZED_REPRESENTATIONS = set()
if B_FEATURE_DICT is not None and "materialized_in_B" in B_FEATURE_DICT.columns:
    for _r in B_FEATURE_DICT.to_dict("records"):
        _mat = str(_r.get("materialized_in_B", "")).strip().lower()
        if _mat in ("false", "0", "no"):
            _NON_MATERIALIZED_REPRESENTATIONS.add(str(_r["new_column"]))
_leaked_nonmat = sorted(_NON_MATERIALIZED_REPRESENTATIONS & set(ANALYSIS_VARS))
if _leaked_nonmat:
    _c3_meta_errors.append(
        f"non-materialized (fold-safe-deferred) representation(s) reached "
        f"ANALYSIS_VARS: {_leaked_nonmat}. These must never be a real EDA C column."
    )

# J. structural-registry applicability gates reference real gate columns.
for _sv in list(CONFIRMED_STRUCTURAL_COLS) + list(APPLICABILITY_LINKED_COLS):
    if _sv not in df.columns:
        continue  # registry member not in this dataset -- gate is simply unused
    _g = structural_missingness_registry.applicability_gate_for(_sv)
    if _g is not None and _g["gate_column"] not in df.columns:
        _c3_meta_errors.append(
            f"structural registry gate for {_sv!r} references missing gate column "
            f"{_g['gate_column']!r}"
        )

if _c3_meta_warnings:
    for _w in _c3_meta_warnings:
        print(f"  C3 metadata AUDIT (disclosure, not blocking): {_w}")
if _c3_meta_errors:
    raise RuntimeError("C3 METADATA CONTRACT FAILED: " + "; ".join(_c3_meta_errors))
print("  C3 metadata contract: PASS "
      f"(classification+type present for all {len(ANALYSIS_VARS)} universe members; "
      f"stage mapping valid; no non-materialized representation leaked).")
""")


# ── Section C3b ────────────────────────────────────────────────────────────────
SC3B_HEADER = md("eda-c-s03b-header", """
## Section C3b — Post-Data-Cleaning-B Variable Inventory & Classification

Adapts CURRENT **A1 "Variable Inventory & Classification"** + **A1 "Predictor
Pool & Exclusion Rationale"** to the post-B world. It inventories every column
of the cleaned dataset named by the Data Cleaning B manifest against the
**authoritative B metadata** (classification snapshot + type snapshot +
`cleaning_b_feature_dictionary.csv` + structural-missingness registry), never
recreated by hand.

**This is a PRE-SCREEN inventory.** It runs *before* the C11/C12
target-independent hard eligibility screen, so it reports only the
**pre-screen analysis-universe status** of each column — `analysis_universe_status`
∈ `staged_analysis_universe` / `target` / `excluded_id` /
`excluded_or_deferred_by_upstream_role`. It does **not** contain final C12
eligibility: zero-variance predictors such as `alcohol`, `HELLP`, `eclampsia`,
`IUFD` are still in the staged analysis universe here even though C12b will
later hard-exclude them. The authoritative eligibility table is C12/C12e.

**B feature-dictionary metadata is applied to `B_registered_original`
variables too**, not only to genuinely B-created features. `origin` is one of
`original_preprocessing` / `B_registered_original` / `B_created`; any column
with a matching `cleaning_b_feature_dictionary.csv` row is `b_feature_registered`
and inherits that row's `source_column` / `redundancy_group` /
`model_entry_mode` / `redundant_with` / `cutpoint_source` / `clinical_timing` /
`domain` / `intended_use` / `leakage_status` / representation metadata.
`BMI_after`, `PPROM`, `gestational_age_at_PPROM_days`, and `weight_in_pregnancy`
are original preprocessing columns that are also B-registered originals — their
feature-dictionary lineage is surfaced here.

Every row of the main inventory is a column **physically present** in the
loaded cleaned dataset (`present_in_cleaned_dataset = True`); the ambiguous
`materialized_in_B` blank is retired in favour of `b_feature_registered` +
`feature_dict_materialized_in_B` (`True` / `False` / `NA` = not registered). A
`b_feature_registered` column present in the dataset whose feature dictionary
says `materialized_in_B == False` is a hard error (dictionary ↔ dataset
disagreement).

Cumulative prediction-horizon availability is displayed:
`available_prediction_horizons` = `Stage 1; Stage 2; Stage 3` for
`earliest_entry_stage` 1, `Stage 2; Stage 3` for 2, `Stage 3` for 3, `--`
otherwise. Stage 2 / Stage 3 are **not** separate non-cumulative pools.

Structural missingness is **registry-driven** (three states preserved:
`confirmed_structural` / `applicability_linked_no_preprocessing_mask` /
`none`; `diabetes_type` explicitly verified `none`). Per gated variable:
`applicable_n`, `missing_within_applicable_n`, `applicability_aware_missing_pct`
— **descriptive / diagnostic only**. For a *pending* structural variable
(e.g. `gestational_age_at_PPROM_days`) it is an applicability sensitivity
diagnostic and is **never** relabelled a confirmed "genuine / effective
missingness" interpretation. When `applicable_n == 0` the value is `NA`, never
the raw whole-cohort figure. A registry gate that references an absent column
fails loud (no silent all-False mask).

The three current **non-materialized, fold-safe-deferred representations**
(`BMI_after_cat`, `gestational_age_at_PPROM_days_timing_status`,
`weight_in_pregnancy_cat`) are disclosed in a **separate**
`non_materialized_representation_df` table only. They are computed
training-fold-only at modeling time, are **not** columns of the cleaned
dataset, and are **not** counted in the main column reconciliation, in
`ANALYSIS_VARS`, in stage membership, or in any eligibility count.

Ends with **reconciliation totals** driven by boolean membership
(`in_analysis_universe` / `is_target` / `is_identifier`), not display strings,
proving the active post-B variable universe is fully accounted for.

**No classification, stage, value, row, or eligibility decision is changed
here.**
""")

SC3B_INVENTORY = code("eda-c-s03b-inventory", """
# ── Section C3b — Post-Data-Cleaning-B Variable Inventory & Classification ──────
# PRE-SCREEN inventory. Runs BEFORE the C11/C12 target-independent hard
# eligibility screen -> it reports pre-screen analysis-universe status only,
# never final C12 eligibility. Authoritative metadata only; nothing recreated
# by hand: B classification snapshot + B type snapshot +
# cleaning_b_feature_dictionary.csv + structural_missingness_registry.

# ---- authoritative metadata maps (all already loaded upstream) ---------------
_b_cls = dict(zip(eda_c_classification_snapshot["column_name"].astype(str),
                  eda_c_classification_snapshot["classification"].astype(str)))
_b_type = dict(VARIABLE_TYPE_MAP)
_orig_names = set(classification_df["column_name"].astype(str))

_fd = B_FEATURE_DICT if "B_FEATURE_DICT" in dir() and B_FEATURE_DICT is not None else None
_fd_by_col = {}
if _fd is not None and "new_column" in _fd.columns:
    for _r in _fd.to_dict("records"):
        _fd_by_col[str(_r["new_column"])] = _r


def _fd_val(_row, _key):
    # feature-dictionary cell -> clean str, or None when absent/UNSET/nan/blank
    if not _row:
        return None
    _v = _row.get(_key, None)
    if _v is None:
        return None
    _s = str(_v).strip()
    if _s == "" or _s.lower() in ("nan", "unset", "none", "na"):
        return None
    return _s


def _fd_bool_true(_row, _key):
    return str(_row.get(_key, "")).strip().lower() in ("true", "1", "yes")


_TECH_ROW_KEY = "_row_key_delivery_id"
_CONFIRMED_STRUCT = set(structural_missingness_registry.structural_nan_cols())
_APPLICABILITY_LINKED = set(structural_missingness_registry.applicability_linked_cols())

# cumulative prediction-horizon display: earliest_entry_stage e -> every horizon >= e
_HORIZON_DISPLAY = {
    1: "Stage 1; Stage 2; Stage 3",
    2: "Stage 2; Stage 3",
    3: "Stage 3",
}

# exclusion / defer rationale -- must agree with the CURRENT B classifications.
_EXCLUSION_RATIONALE = {
    "leakage_exclude": "directly encodes the target / CS decision or a post-event Hb delta -- never a predictor",
    "intrapartum_or_post_delivery_exclude": "intrapartum / postpartum / neonatal -- unavailable at any prediction horizon",
    "source_or_text_audit_exclude": "raw source / free-text / audit-only field (incl. diagnosis_year: calendar year, not disease duration)",
    "cohort_control_exclude": "used to define or verify the trial-of-labor cohort -- not a predictor",
    "clinically_nonspecific_exclude": "too broad / clinically heterogeneous for meaningful predictor interpretation",
    "clinically_redundant_exclude": "retained for audit only; an alternative variable is the approved modeled representation",
    "manual_review_pending": "predictor eligibility not yet resolved -- excluded from the pool, not guessed",
    "awaiting_clinical_clarification": "timing / context not yet clinically confirmed",
    "intrapartum_candidate_pending_timing_confirmation": "timing relative to the intrapartum CS decision not confirmed -- excluded from every stage",
    "id": "patient / delivery identifier -- never a model input",
    "target": "outcome label",
}

# ---- per-column inventory (every row = a column physically present in df) -----
_rows = []
_unknown_exclusion_labels = set()
_present_cols = [_c for _c in df.columns if _c != _TECH_ROW_KEY]
for _c in _present_cols:
    _cls = _b_cls.get(_c, "UNSET")
    _typ = _b_type.get(_c, "unknown")
    _fdrow = _fd_by_col.get(_c, {})
    _b_registered = bool(_fdrow)
    _is_original = _c in _orig_names
    if _b_registered and not _is_original:
        _origin = "B_created"
    elif _b_registered and _is_original:
        _origin = "B_registered_original"
    elif _is_original:
        _origin = "original_preprocessing"
    else:
        _origin = "other"

    # feature-dictionary metadata -- recovered for ANY b_registered column
    # (B_created AND B_registered_original), not only B_created ones.
    _fd_srccol = _fd_val(_fdrow, "source_column")
    _fd_rg = _fd_val(_fdrow, "redundancy_group")
    _fd_mem = _fd_val(_fdrow, "model_entry_mode")
    _fd_redwith = _fd_val(_fdrow, "redundant_with")
    _fd_cutpt = _fd_val(_fdrow, "cutpoint_source")
    _fd_timing = _fd_val(_fdrow, "clinical_timing")
    _fd_domain = _fd_val(_fdrow, "domain")
    _fd_intended = _fd_val(_fdrow, "intended_use")
    _fd_leak = _fd_val(_fdrow, "leakage_status")

    # feature_dict_materialized_in_B: True / False / "NA" (not registered).
    if not _b_registered:
        _fd_matb = "NA"
    else:
        _fd_matb = _fd_bool_true(_fdrow, "materialized_in_B")
    # Every row of THIS loop is physically present in the loaded cleaned
    # dataset, so a b_registered column whose feature dictionary says
    # materialized_in_B == False is a dictionary <-> dataset disagreement.
    if _b_registered and _fd_matb is False:
        raise AssertionError(
            "C3b: feature dictionary marks {!r} materialized_in_B=False, but it "
            "IS physically present in the loaded cleaned dataset -- feature "
            "dictionary and dataset disagree. FAIL LOUD.".format(_c)
        )

    _mem = _fd_mem or ("direct" if _c in ANALYSIS_VARS else "")
    _stage = EARLIEST_ENTRY_STAGE.get(_c)
    _in_universe = _c in ANALYSIS_VARS
    _is_target = _c == TARGET_COL
    _is_id = _c in set(ID_COLS)

    # ---- missingness: raw, then applicability-aware (descriptive/diagnostic) --
    _n_rows_c = len(df)
    _missing_n = int(df[_c].isna().sum())
    _raw_miss_pct = round(_missing_n / _n_rows_c * 100, 1)
    _struct_status = ("confirmed_structural" if _c in _CONFIRMED_STRUCT
                      else ("applicability_linked_no_preprocessing_mask" if _c in _APPLICABILITY_LINKED
                            else "none"))
    _gate = structural_missingness_registry.applicability_gate_for(_c)
    _gate_label = "--"
    _applicable_n = "--"
    _missing_within_applicable_n = "--"
    _aaw_miss_pct = "--"          # applicability_aware_missing_pct
    if _gate is not None:
        _gate_label = _gate["gate_label"]
        _gcol = _gate["gate_column"]
        if _gcol not in df.columns:
            raise AssertionError(
                "C3b: structural registry applicability gate for {!r} references "
                "gate column {!r}, absent from the cleaned dataset -- refusing to "
                "substitute an all-False mask. FAIL LOUD.".format(_c, _gcol)
            )
        _mask = df[_gcol].isin(_gate["gate_values"])
        _applicable_n = int(_mask.sum())
        _missing_within_applicable_n = int(df.loc[_mask, _c].isna().sum())
        if _applicable_n == 0:
            # no applicable observations -> NA, never the raw whole-cohort figure
            _aaw_miss_pct = np.nan
        else:
            _aaw_miss_pct = round(_missing_within_applicable_n / _applicable_n * 100, 1)

    # ---- pre-screen status + rationale (NOT final C12 eligibility) -----------
    if _is_id:
        _universe_status, _why = "excluded_id", _EXCLUSION_RATIONALE["id"]
    elif _is_target:
        _universe_status, _why = "target", _EXCLUSION_RATIONALE["target"]
    elif _in_universe:
        _universe_status, _why = "staged_analysis_universe", ""
    else:
        _universe_status = "excluded_or_deferred_by_upstream_role"
        if _cls in _EXCLUSION_RATIONALE:
            _why = _EXCLUSION_RATIONALE[_cls]
        else:
            _unknown_exclusion_labels.add(_cls)
            _why = "UNRECOGNIZED CLASSIFICATION -- documentation review required"

    _rows.append({
        "variable": _c,
        "variable_type": _typ,
        "predictor_classification": _cls,
        "origin": _origin,
        "b_feature_registered": _b_registered,
        "present_in_cleaned_dataset": True,
        "feature_dict_materialized_in_B": _fd_matb,
        "source_column": _fd_srccol or ("not_registered" if not _b_registered else "not_specified"),
        "redundancy_group": _fd_rg or ("not_registered" if not _b_registered else "not_specified"),
        "model_entry_mode": _mem or "--",
        "redundant_with": _fd_redwith or ("not_registered" if not _b_registered else "not_specified"),
        "cutpoint_source": _fd_cutpt or ("not_registered" if not _b_registered else "not_specified"),
        "clinical_timing": _fd_timing or "not_specified",
        "domain": _fd_domain or "not_specified",
        "intended_use": _fd_intended or "not_specified",
        "leakage_status": _fd_leak or "not_specified",
        "earliest_entry_stage": _stage if _stage is not None else "",
        "available_prediction_horizons": _HORIZON_DISPLAY.get(_stage, "--"),
        "structural_missingness": _struct_status,
        "n_rows": _n_rows_c,
        "missing_n": _missing_n,
        "raw_missing_pct": _raw_miss_pct,
        "applicability_gate": _gate_label,
        "applicable_n": _applicable_n,
        "missing_within_applicable_n": _missing_within_applicable_n,
        "applicability_aware_missing_pct": _aaw_miss_pct,
        "analysis_universe_status": _universe_status,
        "in_analysis_universe": _in_universe,
        "is_target": _is_target,
        "is_identifier": _is_id,
        "exclusion_or_defer_rationale": _why,
    })

inventory_df = pd.DataFrame(_rows)

# Unknown / unrecognised exclusion-or-defer classification -> FAIL LOUD for
# documentation review. This does NOT make the rationale map an eligibility
# authority; the authoritative classification remains the B snapshot.
if _unknown_exclusion_labels:
    raise AssertionError(
        "C3b: cleaned-dataset column(s) carry an exclusion/defer classification "
        "with no explicit rationale entry: {} -- documentation review required "
        "before C3b can vouch for the reconciliation.".format(sorted(_unknown_exclusion_labels))
    )

# ---- diabetes_type: explicit non-structural verification --------------------
if "diabetes_type" in df.columns:
    _dt_status = ("confirmed_structural" if "diabetes_type" in _CONFIRMED_STRUCT
                  else ("applicability_linked_no_preprocessing_mask" if "diabetes_type" in _APPLICABILITY_LINKED
                        else "none"))
    assert _dt_status == "none", (
        "C3b: diabetes_type must be structural_missingness == 'none' under the "
        "current structural registry (the retired config.py structural "
        "interpretation must not be reintroduced); got {!r}".format(_dt_status)
    )
    assert structural_missingness_registry.applicability_gate_for("diabetes_type") is None, (
        "C3b: diabetes_type unexpectedly has a structural applicability gate."
    )
    print("diabetes_type structural-missingness status: none "
          "(no applicability gate) -- verified against the registry.")

# ---- separate non-materialized fold-safe representation disclosure ----------
# Documented-only, computed training-fold-only at modeling time. NOT columns of
# the cleaned dataset; NOT in ANALYSIS_VARS; NOT in stage membership; NOT in the
# main column reconciliation.
_nonmat_rows = []
if _fd is not None:
    for _r in _fd.to_dict("records"):
        if str(_r.get("materialized_in_B", "")).strip().lower() in ("false", "0", "no"):
            _nm = str(_r["new_column"])
            _nonmat_rows.append({
                "new_column": _nm,
                "source_column": _fd_val(_r, "source_column") or "not_specified",
                "predictor_classification": _fd_val(_r, "predictor_classification") or "not_specified",
                "stage": _fd_val(_r, "stage") or "not_specified",
                "clinical_timing": _fd_val(_r, "clinical_timing") or "not_specified",
                "domain": _fd_val(_r, "domain") or "not_specified",
                "redundancy_group": _fd_val(_r, "redundancy_group") or "not_specified",
                "model_entry_mode": _fd_val(_r, "model_entry_mode") or "not_specified",
                "intended_use": _fd_val(_r, "intended_use") or "not_specified",
                "cutpoint_source": _fd_val(_r, "cutpoint_source") or "not_specified",
                "materialized_in_B": False,
                "present_in_cleaned_dataset": _nm in df.columns,
                "in_analysis_vars": _nm in set(ANALYSIS_VARS),
                "status": "documented_only_fold_safe_deferred -- fitted training-fold-only at modeling time",
            })
non_materialized_representation_df = pd.DataFrame(_nonmat_rows)

_nm_names = set(non_materialized_representation_df["new_column"]) if len(non_materialized_representation_df) else set()
_nm_leak_present = sorted(_nm_names & set(df.columns))
_nm_leak_universe = sorted(_nm_names & set(ANALYSIS_VARS))
_nm_leak_stage = sorted(_nm_names & (set(STAGE_1_COLS) | set(STAGE_2_COLS) | set(STAGE_3_COLS)))
if _nm_leak_present:
    raise AssertionError("C3b: non-materialized representation(s) present as cleaned-dataset columns: {}".format(_nm_leak_present))
if _nm_leak_universe:
    raise AssertionError("C3b: non-materialized representation(s) leaked into ANALYSIS_VARS: {}".format(_nm_leak_universe))
if _nm_leak_stage:
    raise AssertionError("C3b: non-materialized representation(s) leaked into stage membership: {}".format(_nm_leak_stage))
assert not inventory_df["variable"].isin(_nm_names).any(), (
    "C3b: a non-materialized representation appears in the main inventory table."
)

# ---- display ---------------------------------------------------------------
_dataset_label = CLEANED_DATASET_NAME if "CLEANED_DATASET_NAME" in dir() else DATA_PATH.name
_disp_cols = ["variable", "variable_type", "predictor_classification", "origin",
              "earliest_entry_stage", "available_prediction_horizons", "model_entry_mode",
              "feature_dict_materialized_in_B", "structural_missingness", "raw_missing_pct",
              "applicability_aware_missing_pct", "analysis_universe_status"]
print("Post-B variable inventory (manifest-driven cleaned dataset {!r} = {} analytical "
      "columns; authoritative B metadata):".format(_dataset_label, len(_present_cols)))
print(inventory_df[_disp_cols].to_string(index=False))
print()

print("B feature-dictionary lineage (B_created AND B_registered_original columns):")
_bview = inventory_df.loc[inventory_df["b_feature_registered"],
                          ["variable", "origin", "source_column", "redundancy_group",
                           "model_entry_mode", "redundant_with", "cutpoint_source",
                           "clinical_timing", "domain", "feature_dict_materialized_in_B"]]
print(_bview.to_string(index=False))
print()

print("Structural / applicability-aware missingness (registry-driven; "
      "confirmed vs pending tiers kept distinct; applicability_aware_missing_pct "
      "is descriptive/diagnostic only -- for a pending tier it is a sensitivity "
      "diagnostic, never a confirmed 'genuine missingness' interpretation):")
_sview = inventory_df.loc[
    (inventory_df["structural_missingness"] != "none") | (inventory_df["applicability_gate"] != "--"),
    ["variable", "structural_missingness", "applicability_gate", "n_rows", "missing_n",
     "raw_missing_pct", "applicable_n", "missing_within_applicable_n",
     "applicability_aware_missing_pct"]]
print(_sview.to_string(index=False) if len(_sview) else "  (no applicability-gated columns in this dataset)")
print()

print("Non-materialized fold-safe representations (documented-only; NOT dataset "
      "columns, NOT in ANALYSIS_VARS / stage membership / reconciliation):")
if len(non_materialized_representation_df):
    print(non_materialized_representation_df[
        ["new_column", "source_column", "predictor_classification", "stage",
         "clinical_timing", "domain", "redundancy_group", "model_entry_mode",
         "intended_use", "cutpoint_source", "status"]].to_string(index=False))
else:
    print("  (none registered with materialized_in_B == False)")
print()

# ── Exclusion-rationale accounting (adapts A1 "Predictor Pool & Exclusion Rationale") ──
print("=" * 70)
print("PREDICTOR-POOL / EXCLUSION-RATIONALE ACCOUNTING (post-B, PRE-SCREEN)")
print("=" * 70)
_by_cls = inventory_df.groupby("predictor_classification").size().sort_values(ascending=False)
for _clsname, _cnt in _by_cls.items():
    _role = ("STAGED ANALYSIS UNIVERSE" if _clsname in
             ("predictor_allowed", "secondary_near_delivery_predictor", "intrapartum_predictor_exclude_from_prelabor_model")
             else ("TARGET" if _clsname == "target" else ("ID" if _clsname == "id" else "EXCLUDED / DEFERRED")))
    _r = _EXCLUSION_RATIONALE.get(_clsname, "")
    print(f"  {_clsname:<48} n={_cnt:>3}  [{_role}]" + (f"  -- {_r}" if _r else ""))
print()

# ── Reconciliation totals (boolean membership; display strings are presentation) ──
_n_cols_total = len(_present_cols)
_n_target = int(inventory_df["is_target"].sum())
_n_id = int(inventory_df["is_identifier"].sum())
_n_universe = int(inventory_df["in_analysis_universe"].sum())
_n_excluded = int((inventory_df["analysis_universe_status"] == "excluded_or_deferred_by_upstream_role").sum())
_n_s1 = len(STAGE_1_COLS); _n_s2 = len(STAGE_2_COLS); _n_s3 = len(STAGE_3_COLS)

assert _n_target == 1, "C3b: expected exactly one target column, got {}".format(_n_target)
assert _TECH_ROW_KEY not in set(inventory_df["variable"]), "C3b: technical row key leaked into the inventory"
assert not (inventory_df["is_target"] & inventory_df["in_analysis_universe"]).any(), "C3b: target present in ANALYSIS_VARS"
assert not (inventory_df["is_identifier"] & inventory_df["in_analysis_universe"]).any(), "C3b: identifier present in ANALYSIS_VARS"
assert _n_universe == len(ANALYSIS_VARS), "C3b: universe count != len(ANALYSIS_VARS)"

print("RECONCILIATION (proves the active post-B universe is fully accounted for):")
print(f"  A. cleaned-dataset analytical columns       : {_n_cols_total}   (dataset {_dataset_label!r}; current live file: Batch19)")
print(f"  B. target                                   : {_n_target}")
print(f"  C. identifiers surviving into the dataset   : {_n_id}")
print(f"  D. baseline staged predictor universe       : {_n_universe}   (== len(ANALYSIS_VARS) = {len(ANALYSIS_VARS)})")
print(f"  E. excluded / deferred by upstream role     : {_n_excluded}")
print(f"  F. technical row key (_row_key_delivery_id) : excluded from the analytical-column reconciliation")
print(f"  G. non-materialized B-documented reps       : {len(non_materialized_representation_df)}   (reported separately; NOT dataset columns)")
print(f"     check: {_n_target} + {_n_id} + {_n_universe} + {_n_excluded} = {_n_target + _n_id + _n_universe + _n_excluded}  "
      f"(== {_n_cols_total}? {_n_target + _n_id + _n_universe + _n_excluded == _n_cols_total})")
assert _n_target + _n_id + _n_universe + _n_excluded == _n_cols_total, "C3b reconciliation failed"

print(f"  Baseline cumulative horizon counts (live runtime): "
      f"Stage1={_n_s1}, Stage2_cum={_n_s2}, Stage3_cum={_n_s3}  "
      f"(nested: {set(STAGE_1_COLS) <= set(STAGE_2_COLS) <= set(STAGE_3_COLS)})")
assert set(STAGE_1_COLS) <= set(STAGE_2_COLS) <= set(STAGE_3_COLS), "C3b: stage nesting broken"
assert set(STAGE_3_COLS) == set(ANALYSIS_VARS), "C3b: Stage 3 baseline universe != ANALYSIS_VARS"
assert _n_s3 == _n_universe, "C3b: cumulative Stage 3 must equal the full universe"
print("  C3b reconciliation PASSED (pre-screen inventory; final C12 eligibility is decided in C12/C12e).")
""")


EDA_C_PART1_CELLS = [
    SC0_HEADER,
    SC1_HEADER,
    SC1_GATE,
    SC2_HEADER,
    SC2_CLASSIFICATION,
    SC3_HEADER,
    SC3_LOAD,
    SC3B_HEADER,
    SC3B_INVENTORY,
]


if __name__ == "__main__":
    print(f"EDA C Part 1 cells defined: {len(EDA_C_PART1_CELLS)}")

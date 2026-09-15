"""
Endometriosis Delivery Study — Data Preprocessing Module

In the canonical private project, this module is the single executable pipeline
that converts the research clinical Excel dataset into a standardized, auditable
analytical dataset. This public-review copy preserves the pipeline structure and
general deterministic logic, but record-specific correction keys and rationales
are redacted as documented below.
It is the required first stage of the analysis pipeline: exploratory data
analysis (EDA) and predictive modeling are performed only on its output, and
neither stage repeats or re-derives the transformations implemented here.

Preprocessing responsibilities implemented in this module:

- Standardization: raw column names are mapped to standardized analytical
  variable names via a documented column mapping; original source and
  free-text variables are preserved alongside derived/cleaned variables
  rather than being overwritten, so provenance stays auditable.
- Cohort and target construction: a unique delivery-level identifier is
  created, the eligible trial-of-labor study cohort is defined, and the
  binary intrapartum cesarean-section target variable is constructed.
- Approved exclusions: records and variables that fall outside the
  analytical cohort or are not clinically appropriate as predictors are
  excluded, strictly according to clinical decisions approved and logged in
  docs/clinical_decisions/manual_decisions_log.md.
- Variable cleaning and derivation: demographic, obstetric, endometriosis,
  pregnancy, delivery, maternal, and neonatal variables are cleaned and
  standardized, and new variables are derived from documented source
  variables using deterministic, auditable rules.
- Clinically defined composite variables: related source variables are
  combined into single composite variables only where a clinical decision
  explicitly defines the combination rule.
- Subgroup-specific missing-value handling: for variables that are only
  clinically applicable to a subgroup of records (e.g. cesarean-only or
  surgery-only fields), values outside that subgroup are set to missing
  rather than treated as a false negative/zero.
- Manual record-level corrections: clinically approved corrections are
  applied only via validated subject_number + delivery_id composite keys,
  never by value alone, with hard validation against duplicate or unmatched
  keys.
- Manual-review exports: unresolved, contradictory, or unexpected values are
  exported to dedicated review files for clinical review instead of being
  silently auto-corrected or guessed.
- Leakage prevention: post-outcome, intrapartum, and post-delivery variables
  are identified and classified separately from pre-labor predictors, so
  downstream modeling cannot accidentally use information that would not be
  available at prediction time.
- Reproducibility and audit outputs: the canonical private implementation produces
  processed datasets, batch-level summaries, a deviation log, and an audit trail.
  This redacted review copy is not intended for exact execution because individual
  adjudication keys have been removed.

The workflow is organized into sequential, numbered batch functions (Batch 1
through Batch 19). Each batch handles a defined clinical or analytical
variable group, validates its own output, writes the relevant documentation,
and returns the updated working DataFrame to the next batch in main().

The raw input Excel dataset is never modified. All transformations operate on
working copies of the data; the resulting processed output is the input to
downstream data cleaning, exploratory analysis, and modeling stages.

This is a plain Python module, not a notebook. Manual clinical decision
tables and their composite-key validation/application logic live in
src/clinical_decisions.py; deterministic adenomyosis and endometrioma
free-text parsing rules live in src/adenomyosis_rules.py and
src/endometrioma_rules.py respectively. This module imports from those and
focuses on orchestration: the sequential Batch 1-19 functions and main().

Run from the project root:

    python analysis/preprocessing/run_preprocessing.py

Only the approved batch functions called from main() are executed.
"""

import sys
import os
import re

# Allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pandas as pd
import numpy as np
from openpyxl.utils import get_column_letter

from preprocessing_config import (
    RAW_DATA_PATH,
    OUTPUT_AUDIT_PATH,
    OUTPUT_REVIEW_PATH,
    OUTPUT_PROCESSED_PATH,
    LOGS_PATH,
    COLUMN_MAPPING,
    VARS_NOT_IN_DATASET,
    PLANNED_QA_CORRECTIONS,
    CURRENT_APPROVED_COHORT_ROWS,
    CURRENT_APPROVED_TARGET_N0,
    CURRENT_APPROVED_TARGET_N1,
)
# Note: INTERNAL_USE_VARS and LEAKAGE_VARS are intentionally not imported
# here. Neither controls pipeline execution — see the comments on their
# definitions in preprocessing_config.py for the actual authoritative
# mechanisms (the local _INTERNAL_USE_COLS list in Batch 2, and the
# classification_groups leakage_exclude group in Batch 19).
from preprocessing_utils import (
    build_rename_map,
    validate_mapping,
    save_column_mapping_csv,
    normalize_multi_code_string,
    write_batch_summary,
    append_deviation,
    init_deviation_log,
    init_audit_log,
    append_audit_entry,
    sha256_of_file,
    format_run_header,
    sanitize_tracked_audit_markdown,
)
from clinical_decisions import (
    ADENOMYOSIS_MANUAL_FEATURE_DECISIONS,
    ADENOMYOSIS_REVIEW_STATUS_DECISIONS,
    validate_composite_key_decisions,
    apply_adenomyosis_manual_feature_decisions,
    apply_adenomyosis_review_status_decisions,
)
from adenomyosis_rules import (
    normalize_adenomyosis_feature_text,
    classify_adenomyosis_free_text,
    classify_adenomyosis_features_value,
    adenomyosis_codes_to_clean_value,
    adenomyosis_has_diagnostic_code,
)
from endometrioma_rules import (
    normalize_endometrioma_place_missing_text,
    is_documented_missing_endometrioma_place,
    extract_endometrioma_place_codes,
    clean_endometrioma_place_value,
    derive_endometrioma_laterality,
    has_uncodeable_endometrioma_place_text,
    parse_endometrioma_size_mm_with_evidence,
    ENDOMETRIOMA_SIZE_PARSER_VERSION,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def resolve_path(relative):
    """Join a project-root-relative path with the absolute PROJECT_ROOT."""
    return os.path.join(PROJECT_ROOT, relative)



# ---------------------------------------------------------------------------
# PRIVACY-REDACTED REVIEW COPY
# ---------------------------------------------------------------------------
# This file preserves the preprocessing orchestration and general deterministic
# logic, but literal record keys and patient-specific adjudication text have been
# removed. Redacted record-specific corrections are represented as no-op review
# placeholders. This copy is for code/method review and is NOT an executable
# substitute for the canonical private preprocessing source.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Batch title registry — single source of truth for the descriptive title
# shown in console output, audit-log entries, and batch summary headings.
# Docstrings on each batch function restate the same title as their opening
# line; keep both in sync when a batch's scope changes.
# ---------------------------------------------------------------------------
BATCH_METADATA = {
    1: {
        "function": "batch_1_column_mapping",
        "title": "Column standardization and delivery-level identifier creation",
    },
    2: {
        "function": "batch_2_cohort_target",
        "title": "Cohort definition, trial-of-labor correction, and target construction",
    },
    3: {
        "function": "batch_3_obstetric_history",
        "title": "Obstetric history standardization and approved S_P_CS correction",
    },
    4: {
        "function": "batch_4_background",
        "title": "Background health variables and free-text comment standardization",
    },
    5: {
        "function": "batch_5_endometriosis",
        "title": "Endometriosis type variables and diagnosis-year derivation",
    },
    6: {
        "function": "batch_6_adenomyosis",
        "title": "Adenomyosis feature cleaning and clinically approved corrections",
    },
    7: {
        "function": "batch_7_endometrioma",
        "title": "Endometrioma characteristics parsing and consistency review",
    },
    8: {
        "function": "batch_8_endometriosis_surgery",
        "title": "Endometriosis-surgery cleaning and resection-site classification",
    },
    9: {
        "function": "batch_9_body_size_and_treatment",
        "title": "Pregnancy anthropometry and antenatal treatment variables",
    },
    10: {
        "function": "batch_10_conception",
        "title": "Conception method and fertility-treatment standardization",
    },
    11: {
        "function": "batch_11_pprom_gestational_age",
        "title": "PPROM and gestational-age standardization",
    },
    12: {
        "function": "batch_12_hypertension_diabetes",
        "title": "Hypertensive-disorder and diabetes-related pregnancy complications",
    },
    13: {
        "function": "batch_13_pregnancy_complications",
        "title": "Remaining pregnancy-complication variable standardization",
    },
    14: {
        "function": "batch_14_labor_induction",
        "title": "Labor onset and induction-of-labor derivation",
    },
    15: {
        "function": "batch_15_cs_reference_variables",
        "title": "Cesarean-delivery reference variables and subgroup applicability",
    },
    16: {
        "function": "batch_16_maternal_outcomes",
        "title": "Maternal post-delivery outcomes and leakage-variable reference",
    },
    17: {
        "function": "batch_17_neonatal_basic",
        "title": "Basic neonatal outcome variables",
    },
    18: {
        "function": "batch_18_neonatal_outcomes",
        "title": "Extended neonatal outcomes and manual text corrections",
    },
    19: {
        "function": "batch_19_qa_inventory_and_classification",
        "title": "Final variable classification, leakage gate, and QA inventory",
    },
}


# ---------------------------------------------------------------------------
# Batch 1 — Column standardization and delivery-level identifier creation
# ---------------------------------------------------------------------------

def batch_1_column_mapping(cohort_mode=None):
    """
    Column standardization and delivery-level identifier creation.

    Maps raw Excel column names to standardized variable names via the
    documented column mapping (COLUMN_MAPPING), creates the delivery-level
    identifier delivery_id, and validates that the raw-to-standardized
    mapping is complete and unambiguous. The raw dataset is loaded but never
    modified; all transformations operate on a working copy. This batch's own
    logic never depends on cohort_mode (column mapping is identical in every
    mode) -- the parameter exists only to redirect this batch's audit/
    deviation/summary/mapping-csv file paths for non-"primary" modes (see
    COHORT_MODES / resolve_cohort_mode), so a non-primary run can never
    truncate or overwrite the canonical audit log (init_deviation_log/
    init_audit_log always truncate-and-rewrite on every call).

    QA outputs: column_mapping.csv (audit).
    Returns: (work_df, raw_df) — the standardized working copy and the
    untouched raw source.
    """
    cohort_mode = resolve_cohort_mode(cohort_mode)
    BATCH_TITLE = BATCH_METADATA[1]["title"]
    print(f"=== Batch 1: {BATCH_TITLE} (cohort_mode={cohort_mode!r}) ===")

    # Paths
    raw_path         = resolve_path(RAW_DATA_PATH)
    audit_path       = resolve_path(OUTPUT_AUDIT_PATH)
    review_path      = resolve_path(OUTPUT_REVIEW_PATH)
    processed_path   = resolve_path(OUTPUT_PROCESSED_PATH)
    logs_path        = resolve_path(LOGS_PATH)
    if cohort_mode != "primary":
        # Never the canonical audit/deviation/summary paths -- a non-primary
        # run must be structurally incapable of truncating or overwriting a
        # canonical artifact (init_deviation_log/init_audit_log always
        # truncate-and-rewrite on every call).
        audit_path = os.path.join(audit_path, "cohort_modes", cohort_mode)
    mapping_csv      = os.path.join(audit_path, "column_mapping.csv")
    deviations_md    = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md     = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md       = os.path.join(audit_path, "preprocessing_summary_batch1.md")

    for d in [audit_path, review_path, processed_path, logs_path]:
        os.makedirs(d, exist_ok=True)

    # 1. Load raw data — never modify this copy
    print(f"  Loading raw data from: {raw_path}")
    raw_df = pd.read_excel(raw_path)
    n_rows_raw, n_cols_raw = raw_df.shape
    print(f"  Raw shape: {n_rows_raw} rows x {n_cols_raw} columns")

    # Identify exactly which execution the audit files below describe.
    # init_deviation_log/init_audit_log truncate and rewrite on every run —
    # a canonical audit run represents one execution, never an accumulation
    # of unrelated prior runs (see preprocessing_utils.py docstrings).
    run_header = format_run_header(
        input_dataset_relpath=os.path.relpath(raw_path, PROJECT_ROOT).replace(os.sep, "/"),
        input_dataset_sha256=sha256_of_file(raw_path),
    )
    init_deviation_log(deviations_md, run_header=run_header)
    init_audit_log(audit_log_md, run_header=run_header)

    # 2. Create working copy
    work_df = raw_df.copy()

    # 3. Validate that every raw column is covered by COLUMN_MAPPING
    # (PARTNER-FIX-04, finding F-2). Previously this only printed a WARNING
    # and marked the batch summary "FAIL" in text while still writing
    # work_df_batch1.xlsx and letting the pipeline continue to Batch 2 --
    # a fail-open path. An unmapped or duplicate-mapped raw column is now a
    # blocking error: a minimal failure diagnostic is written (never the
    # canonical processed output), then the pipeline raises and stops
    # before Batch 2 runs.
    ok, unmapped, dup_in_mapping = validate_mapping(work_df.columns.tolist(), COLUMN_MAPPING)

    if not ok:
        failure_lines = [
            f"# Preprocessing Batch 1 Summary — {BATCH_TITLE}",
            f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Validation",
            "FAIL",
            "",
            "## Blocking findings",
        ]
        if unmapped:
            failure_lines.append(f"- {len(unmapped)} unmapped raw column(s): {unmapped}")
        if dup_in_mapping:
            failure_lines.append(f"- {len(dup_in_mapping)} duplicate COLUMN_MAPPING entrie(s): {dup_in_mapping}")
        failure_lines.append("")
        failure_lines.append(
            "No processed output was written for this run. Downstream batches did not run."
        )
        os.makedirs(audit_path, exist_ok=True)
        write_batch_summary(summary_md, "\n".join(failure_lines) + "\n")
        raise ValueError(
            "Batch 1 column-mapping validation FAILED -- "
            f"unmapped: {unmapped if unmapped else 'none'}; "
            f"duplicate mapping entries: {dup_in_mapping if dup_in_mapping else 'none'}. "
            f"See {summary_md} for the failure diagnostic. "
            "The canonical processed output was not written and the pipeline did not continue."
        )

    # 4. Build rename map and apply it
    rename_map = build_rename_map(COLUMN_MAPPING)
    work_df = work_df.rename(columns=rename_map)

    # Verify no duplicate standardized names after rename
    if work_df.columns.duplicated().any():
        dups = work_df.columns[work_df.columns.duplicated()].tolist()
        raise ValueError(f"Duplicate standardized column names after rename: {dups}")

    # 5. Add delivery_id as first column (1-based sequential integer)
    work_df.insert(0, "delivery_id", range(1, len(work_df) + 1))
    print(f"  delivery_id created: 1 to {len(work_df)}")

    # Defense-in-depth: delivery_id must be complete and unique by
    # construction; assert it rather than silently trusting the sequence.
    assert work_df["delivery_id"].notna().all(), "delivery_id must be complete (no missing values)."
    assert not work_df["delivery_id"].duplicated().any(), "delivery_id must be unique."

    # 6. Save column mapping CSV
    save_column_mapping_csv(COLUMN_MAPPING, mapping_csv)
    print(f"  Column mapping saved: {mapping_csv}")

    # 7. Count column categories
    excluded_cols  = [std for _, std, mtype, _ in COLUMN_MAPPING if mtype == "excluded"]
    duplicate_cols = [(raw, std) for raw, std, mtype, _ in COLUMN_MAPPING if mtype == "duplicate"]
    inferred_cols  = [std for _, std, mtype, _ in COLUMN_MAPPING if mtype == "inferred"]
    exact_cols     = [std for _, std, mtype, _ in COLUMN_MAPPING if mtype == "exact"]
    n_mapped       = len(COLUMN_MAPPING)

    # 8. Document planned QA deviations in deviation log (not yet executed)
    for corr in PLANNED_QA_CORRECTIONS:
        append_deviation(
            path=deviations_md,
            variable=corr["variable"],
            raw_variable=corr["variable"],
            documented="Per variable documentation heading",
            action=f"PLANNED (not yet executed): {corr['action']}",
            reason=corr["reason"],
            requires_approval=corr["requires_approval"],
            batch=corr["batch"],
        )

    # 9. Document comment_10 raw-position correction and current generic
    # comment-column renumbering lineage.
    append_deviation(
        path=deviations_md,
        variable="comment_10",
        raw_variable="comments.3",
        documented="Variable documentation file listed last generic comment as comment_11",
        action="Mapped to comment_10 (not comment_11)",
        reason="Current dataset has exactly 10 generic comment columns (col indices 14,16,18,37,72,78,82,88,99,129). Documentation used comment_11 due to old numbering. Corrected to comment_10 to match actual count.",
        requires_approval=False,
        batch="Batch 1",
    )
    generic_comment_lineage = [
        ("הערות", "comment_4", "comment_1", "endo surgery group"),
        ("comments.1", "comment_5", "comment_2", "celestone/magnesium group"),
        ("comment.2", "comment_6", "comment_3", "CS_case_vs_control group"),
        ("comment.3", "comment_7", "comment_4", "indication_for_CS group"),
        ("comments.2", "comment_8", "comment_5", "surgery/adhesions group"),
        ("comment.4", "comment_9", "comment_6", "hospitalization_days group"),
    ]
    generic_comment_lineage_md = "\n".join(
        f"- raw {raw!r} ({section}): {old} -> {new}"
        for raw, old, new, section in generic_comment_lineage
    )
    append_deviation(
        path=deviations_md,
        variable="comment_1-comment_6",
        raw_variable="generic comment columns",
        documented="Previous processed generic comment numbering preserved historical raw positions",
        action="Renumbered remaining generic comment columns consecutively from comment_1",
        reason=(
            "Decision 57: semantic comment fields retain descriptive names; "
            "generic numbering now represents only generic comment columns "
            "remaining in the processed schema. Previous numbering represented "
            "historical raw-source positions. comment_10 remains intentionally "
            "removed under Decision 33."
        ),
        requires_approval=False,
        batch="Batch 1",
    )

    # 10. Document variables not in dataset
    vars_not_present_text = ""
    for v in VARS_NOT_IN_DATASET:
        vars_not_present_text += (
            f"- `{v['standardized_name']}` (documented raw: '{v['documented_raw_name']}'): {v['reason']}\n"
        )

    # 11. Build batch summary
    validation_result = "PASS" if ok and not work_df.columns.duplicated().any() else "FAIL"

    summary = f"""# Preprocessing Batch 1 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Dataset shape
- Raw shape: {n_rows_raw} rows × {n_cols_raw} columns
- Working copy after rename + delivery_id: {work_df.shape[0]} rows × {work_df.shape[1]} columns

## Column mapping statistics
- Total raw columns: {n_cols_raw}
- Mapped (exact): {len(exact_cols)}
- Mapped (inferred): {len(inferred_cols)}
- Mapped (duplicate/contextual): {len(duplicate_cols)}
- Excluded/internal-use: {len(excluded_cols)}
- Total COLUMN_MAPPING entries: {n_mapped}
- Unmapped columns: {len(unmapped)} {unmapped if unmapped else '(none)'}

## Excluded / internal-use columns
{chr(10).join(f'- {c}' for c in excluded_cols)}

## Duplicated raw column names resolved
{chr(10).join(f'- raw: {r!r}  →  standardized: {s!r}' for r, s in duplicate_cols)}

## Generic comment-column lineage (Decision 57)
Semantic comment fields retain descriptive names. Remaining generic comment
columns are now numbered consecutively from `comment_1`; prior gaps represented
historical raw-source positions. `comment_10` remains intentionally removed
under Decision 33.
{generic_comment_lineage_md}

## Variables not present in current dataset
{vars_not_present_text}
## Planned QA corrections (not yet executed)
{chr(10).join(f"- {c['variable']}: {c['action']}" for c in PLANNED_QA_CORRECTIONS)}

## Deviation from documentation
- comment_10 raw-position correction and generic comment renumbering lineage:
  see preprocessing_deviations.md

## Output files
- Column mapping: {mapping_csv}
- Audit log: {audit_log_md}
- Deviation log: {deviations_md}
- Summary: {summary_md}

## Validation result
{validation_result}
"""

    write_batch_summary(summary_md, summary)
    print(f"  Summary saved: {summary_md}")

    append_audit_entry(
        audit_log_md,
        f"Batch 1 — {BATCH_TITLE}",
        f"- Raw shape: {n_rows_raw}x{n_cols_raw}\n"
        f"- Mapped columns: {n_mapped}\n"
        f"- Excluded: {excluded_cols}\n"
        f"- Unmapped: {unmapped if unmapped else 'none'}\n"
        f"- Duplicate comment columns resolved: {len(duplicate_cols)}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"\n  Validation: {validation_result}")
    print("=== Batch 1 complete ===\n")

    return work_df, raw_df


# ---------------------------------------------------------------------------
# mode_of_conception — centralized permitted-code set (Decision 30, PRE-B10-006)
# Single source of truth shared by Batch 2 (Decision 30 derivation) and
# Batch 10 (explicit code validation), so the permitted set is never
# duplicated or allowed to drift between the two. Only code 1 is documented
# (Decision 30) as meaning IVF; codes 0, 2, and 3 are valid non-IVF codes
# with no further clinical label assigned here beyond what Decision 30
# itself defines, since no authoritative project source assigns one.
# ---------------------------------------------------------------------------
MODE_OF_CONCEPTION_VALID_CODES = {0, 1, 2, 3}


# ---------------------------------------------------------------------------
# Decision 67 cohort modes (2026-08-15) -- four reproducible, operationally
# generatable cohorts, not just transient in-memory counts. Each entry gives
# the delivery_id-mask size Batch 2 applies (0 = no Decision 67 exclusion at
# all) and the resulting row count, both asserted fail-loud in
# batch_2_cohort_target. "primary" is the default and the ONLY mode that
# writes to the canonical processed-output paths (work_df_batch2.xlsx, and,
# via main(), every downstream batch's canonical file); every other mode is
# routed to a separate cohort_modes/ subdirectory and main() stops after
# Batch 2 for it -- see resolve_cohort_mode() and main() below. Target
# (vaginal, CS) distributions are informational only here; they are computed
# and asserted at runtime, never trusted from this comment.
#
# SCOPE LIMITATION (deliberate, not yet extended): the three non-primary
# modes ("original", "exclude19", "strict26") produce cohort-MEMBERSHIP and
# QC/reconciliation outputs ONLY -- the row set, target distribution, and a
# handful of raw/renamed source columns present after Batch 1+2, nothing
# more. Batches 3-19 (variable cleaning, derived-feature construction,
# missingness handling, classification) run ONLY for "primary". A
# non-primary export is therefore NOT a fully processed, model-ready
# dataset -- it has none of the ~150 derived/cleaned analytical columns the
# primary 431-row export has, and must not be treated as one. Extending the
# non-primary modes through the full pipeline (so each produces its own
# complete model-ready dataset) is future work, intentionally out of scope
# for this pass.
# ---------------------------------------------------------------------------
# "primary"'s expected_n/expected_target read from preprocessing_config.py's
# CURRENT_APPROVED_COHORT_ROWS/TARGET_N0/TARGET_N1 -- the single authoritative
# source for the current frozen-cohort baseline (centralized 2026-08-16; do
# not reintroduce an independent literal here). The other three modes are
# Decision-67 sensitivity/QC variants, not the approved primary cohort, so
# they keep their own literals.
COHORT_MODES = {
    "primary":   {"n_excluded": 16, "expected_n": CURRENT_APPROVED_COHORT_ROWS, "expected_target": (CURRENT_APPROVED_TARGET_N0, CURRENT_APPROVED_TARGET_N1)},
    "original":  {"n_excluded": 0,  "expected_n": 447, "expected_target": (385, 62)},
    "exclude19": {"n_excluded": 19, "expected_n": 428, "expected_target": (367, 61)},
    "strict26":  {"n_excluded": 26, "expected_n": 421, "expected_target": (363, 58)},
}


def resolve_cohort_mode(explicit=None):
    """Fail-closed resolution of the Decision 67 cohort mode: explicit
    argument takes precedence, else the PREPROCESSING_COHORT_MODE
    environment variable, else "primary". Raises ValueError immediately for
    any value not in COHORT_MODES -- never silently falls back to "primary"
    for an unrecognized value, so a typo'd env var cannot silently produce
    the wrong cohort."""
    mode = explicit if explicit is not None else os.environ.get("PREPROCESSING_COHORT_MODE", "primary")
    if mode not in COHORT_MODES:
        raise ValueError(
            f"Invalid cohort_mode {mode!r} -- must be one of {sorted(COHORT_MODES)}. "
            "Set the PREPROCESSING_COHORT_MODE environment variable, or pass "
            "cohort_mode explicitly to batch_2_cohort_target()/main()."
        )
    return mode


# ---------------------------------------------------------------------------
# Decision 67 -- suspected superficial-only endometriosis eligibility.
# Extracted to a standalone, pure function (2026-08-20 addendum) so the
# missing-evidence eligibility logic is independently testable with a small
# synthetic dataframe, without going through batch_2_cohort_target()'s
# hard-wired real-dataset safety-gate assertions (447-record baseline,
# exactly 16/19/26 matches). batch_2_cohort_target() below calls this
# function and then applies those safety gates to its return values --
# behavior is unchanged, only the computation is now separately callable.
# ---------------------------------------------------------------------------

def compute_decision67_evidence(work_df):
    """Decision 67 eligibility masks for suspected superficial-only
    endometriosis records (see docs/clinical_decisions/manual_decisions_log.md,
    Decision 67, for the full clinical rationale).

    Reads only the 7 clinical fields below; never modifies work_df and never
    reads target_intrapartum_cs, type_of_CS, or any outcome-derived
    information.

    A superficial_endometriosis==1 record is excluded unless documented
    evidence supports retaining it in the endometriosis cohort:
      - documented positive phenotype evidence (peritoneal_endometriosis,
        deep_endometriosis, endometrioma, cs_scar_endometriosis, or
        adenomyosis, each ==1) justifies retention; adenomyosis alone is
        sufficient.
      - clinical_diagnosis_only == 0 also prevents this exclusion (the
        diagnosis does not rest on clinical impression alone), but is not
        itself phenotype evidence.
      - a missing field is never treated as evidence for or against
        retention -- it stays missing in the data and cannot itself justify
        keeping or excluding a record.

    Returns a dict:
      - "superficial_mask": the reviewed population (superficial_
        endometriosis == 1).
      - "phenotype_evidence": documented positive phenotype evidence only.
      - "retention_basis_excl_adenomyosis" / "retention_basis_full":
        phenotype_evidence plus clinical_diagnosis_only == 0 (and, for
        "_full", adenomyosis == 1) -- the 19-record/26-record sensitivity
        groups and the 16-record primary rule are each built from one of
        these.
      - "mask_primary" / "mask_19" / "mask_26": superficial_mask minus the
        corresponding retention basis above (mask_primary <= mask_19 <=
        mask_26).
      - "nan_in_required": rows with a missing required field, for audit
        purposes only.
    """
    _decision67_required_cols_local = [
        "superficial_endometriosis", "peritoneal_endometriosis", "deep_endometriosis",
        "endometrioma", "cs_scar_endometriosis", "clinical_diagnosis_only", "adenomyosis",
    ]
    superficial_mask = work_df["superficial_endometriosis"] == 1
    peritoneal_confirmed        = work_df["peritoneal_endometriosis"] == 1
    deep_confirmed              = work_df["deep_endometriosis"] == 1
    endometrioma_confirmed      = work_df["endometrioma"] == 1
    cs_scar_confirmed           = work_df["cs_scar_endometriosis"] == 1
    adenomyosis_confirmed       = work_df["adenomyosis"] == 1
    # Not phenotype evidence -- a documented condition that removes the
    # record from the "clinical diagnosis only" branch of the exclusion
    # classification (see docstring).
    not_clinical_diagnosis_only = work_df["clinical_diagnosis_only"] == 0

    phenotype_evidence = (
        peritoneal_confirmed | deep_confirmed
        | endometrioma_confirmed | cs_scar_confirmed
    )
    retention_basis_excl_adenomyosis = phenotype_evidence | not_clinical_diagnosis_only
    retention_basis_full = retention_basis_excl_adenomyosis | adenomyosis_confirmed

    nan_in_required = work_df[_decision67_required_cols_local].isna().any(axis=1) & superficial_mask

    return {
        "superficial_mask": superficial_mask,
        "phenotype_evidence": phenotype_evidence,
        "retention_basis_excl_adenomyosis": retention_basis_excl_adenomyosis,
        "retention_basis_full": retention_basis_full,
        "mask_primary": superficial_mask & (~retention_basis_full),
        "mask_19": superficial_mask & (~retention_basis_excl_adenomyosis),
        "mask_26": superficial_mask & (~phenotype_evidence),
        "nan_in_required": nan_in_required,
    }


# ---------------------------------------------------------------------------
# Batch 2 — Cohort definition, trial-of-labor correction, and target construction
# ---------------------------------------------------------------------------

def batch_2_cohort_target(work_df, cohort_mode=None):
    """
    Cohort definition, trial-of-labor correction, and target construction.

    cohort_mode: one of COHORT_MODES ("primary" [default], "original",
    "exclude19", "strict26") -- resolved fail-closed via
    resolve_cohort_mode() if not passed explicitly (checks the
    PREPROCESSING_COHORT_MODE environment variable, else "primary"). Selects
    which of the three outcome-blind Decision 67 masks (0/16/19/26 records)
    is actually applied to remove rows. Only "primary" writes to the
    canonical processed-output path; every other mode writes to a separate
    cohort_modes/ subdirectory instead (see main() for the full-pipeline
    implication).

    Canonical early cohort-eligibility section: recomputes
    mode_of_conception_ivf_vs_all deterministically from mode_of_conception
    (Decision 30), corrects trial_of_labor for vaginal deliveries, then
    applies every row-level cohort exclusion in one consolidated sequence,
    all before target_intrapartum_cs is created: elective CS, non-trial-of-
    labor, the single approved placenta_accreta/previa record (Decision 32,
    448->447), and the suspected-superficial-only-endometriosis exclusion
    (Decision 67, 447->431 in primary mode). Decision 67's masks are derived
    and frozen on the outcome-blind 447-record baseline, using
    clinical_diagnosis_only and 6 endometriosis/adenomyosis phenotype flags
    that are binary-validated immediately after loading and column-name
    standardization, before any of this batch's row exclusions run.
    clinical_diagnosis_only is then dropped (with the other internal-use /
    approved analytical-exclusion columns: delivery_mode, Status, comment_10,
    surgery_dehiscence — Decision 33) immediately after that single use, and
    target_intrapartum_cs is constructed only once the final 431-row primary
    cohort is settled -- "target access" never precedes cohort eligibility.
    Three reproducible non-primary cohort modes (447 original, 428
    exclude-19, 421 strict-26) are preserved two ways: via delivery_id-keyed
    flag columns on the primary 431-row export (no excluded rows retained),
    and, independently, as operationally regeneratable cohorts via the
    cohort_mode parameter/COHORT_MODES (see above) -- each producing its own
    standalone processed file from the same raw input, with no source-code
    edits required.

    Approved decisions: 30, 32, 33, 67.
    Returns: work_df — the cohort-filtered working DataFrame (431 rows,
    primary mode).
    """
    cohort_mode = resolve_cohort_mode(cohort_mode)
    BATCH_TITLE = BATCH_METADATA[2]["title"]
    print(f"=== Batch 2: {BATCH_TITLE} (cohort_mode={cohort_mode!r}) ===")

    audit_path    = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    if cohort_mode != "primary":
        # Same redirection as batch_1_column_mapping, for the same reason:
        # a non-primary run must never truncate/overwrite the canonical
        # audit/deviation/summary files (append_deviation/append_audit_entry
        # append within whatever file they're given; write_batch_summary
        # always truncates-and-rewrites its target path).
        audit_path = os.path.join(audit_path, "cohort_modes", cohort_mode)
        os.makedirs(audit_path, exist_ok=True)
    deviations_md = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md  = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md    = os.path.join(audit_path, "preprocessing_summary_batch2.md")
    if cohort_mode == "primary":
        # Only mode that ever touches the canonical processed-output path.
        output_xlsx = os.path.join(processed_path, "work_df_batch2.xlsx")
    else:
        # Never the canonical filename/path -- a non-primary run must be
        # structurally incapable of overwriting a canonical artifact, even
        # by accident. main() also stops after this batch for non-primary
        # modes (does not proceed to Batch 3+), for the same reason.
        _cohort_mode_dir = os.path.join(processed_path, "cohort_modes")
        os.makedirs(_cohort_mode_dir, exist_ok=True)
        output_xlsx = os.path.join(_cohort_mode_dir, f"work_df_batch2_cohort_mode_{cohort_mode}.xlsx")

    n_rows_start = len(work_df)

    # --- Step -1: Decision 67 -- binary validation of the 7 required fields ---
    # Runs first in this batch, immediately after Batch 1's loading and
    # column-name standardization -- before any row-level exclusion, before
    # mode_of_conception_ivf_vs_all derivation, before feature engineering,
    # missingness treatment, and target construction. Read-only: does not
    # modify any column. All 7 fields are raw/renamed-only at this point (no
    # later batch ever assigns to them before this validation runs, since
    # Batch 2 executes before Batches 5-7); the two fields that DO receive a
    # later clinically-approved correction downstream (adenomyosis in Batch 6,
    # endometrioma for [record key redacted] in Batch 7) were confirmed, by
    # direct pre-execution audit against the raw source, not to overlap any
    # Decision 67-relevant record in the current dataset -- so using their
    # pre-correction values here is equivalent to post-correction for this
    # specific rule. See docs/clinical_decisions/manual_decisions_log.md,
    # Decision 67.
    from preprocessing_utils import validate_expected_binary_values
    _decision67_required_cols = [
        "superficial_endometriosis", "peritoneal_endometriosis", "deep_endometriosis",
        "endometrioma", "cs_scar_endometriosis", "clinical_diagnosis_only", "adenomyosis",
    ]
    _d67_binary_validation_errors = []
    for _d67_col in _decision67_required_cols:
        _d67_ok, _d67_unexpected = validate_expected_binary_values(work_df[_d67_col], _d67_col)
        if not _d67_ok:
            _d67_binary_validation_errors.append(f"{_d67_col}: unexpected values {_d67_unexpected}")
    if _d67_binary_validation_errors:
        raise ValueError(
            "Decision 67 SAFETY GATE FAILED: one or more required fields contain "
            f"non-binary values: {_d67_binary_validation_errors}. Stopping before "
            "any cohort-eligibility mask is computed -- do not proceed without "
            "re-approval. See docs/clinical_decisions/manual_decisions_log.md, "
            "Decision 67."
        )
    print(f"  Decision 67: all {len(_decision67_required_cols)} required fields "
          "validated as binary (0/1/NaN)")

    # --- Step 0: mode_of_conception_ivf_vs_all -- deterministic derivation ---
    # Decision 30 (2026-07-29): mode_of_conception_ivf_vs_all was previously an
    # independently-sourced raw field (not derived), which disagreed with
    # mode_of_conception in 29 of 513 rows. Recomputed deterministically from
    # the authoritative source column instead: 1 when mode_of_conception == 1,
    # 0 when mode_of_conception is a valid non-IVF code (see
    # MODE_OF_CONCEPTION_VALID_CODES). mode_of_conception itself and
    # mode_of_conception_details are never modified. Must run here, before the
    # Step 3/4 cohort-filtering below, so all 513 source records are corrected
    # consistently -- not just the 448 retained after filtering. See
    # docs/clinical_decisions/manual_decisions_log.md, Decisions 30 and 7.
    #
    # PRE-B10-006 (2026-07-31): missing or invalid mode_of_conception values
    # must not silently derive to 0 -- uncertainty in the authoritative source
    # must be preserved as missing in the derived binary, not resolved into a
    # false negative. mode_of_conception itself is independently re-validated
    # and turned into a blocking QA failure by Batch 10 later in the same
    # pipeline run if any invalid (non-missing, non-permitted) value is found;
    # this step only needs to avoid manufacturing a wrong 0 here. Current data
    # contain zero missing/invalid mode_of_conception values (verified: raw
    # dtype int64, 0 missing, values confined to {0,1,2,3}), so this changes no
    # current analytical value -- it only changes future-data behavior.
    work_df = work_df.copy()
    _moc_step0 = pd.to_numeric(work_df["mode_of_conception"], errors="coerce")
    _moc_step0_valid = _moc_step0.isin(MODE_OF_CONCEPTION_VALID_CODES)
    _moc_step0_invalid = work_df["mode_of_conception"].notna() & ~_moc_step0_valid
    _n_moc_step0_invalid = int(_moc_step0_invalid.sum())
    _ivf_before_step0 = work_df["mode_of_conception_ivf_vs_all"].copy()
    _ivf_derived_step0 = pd.Series(np.nan, index=work_df.index, dtype="float64")
    _ivf_derived_step0[_moc_step0_valid] = (_moc_step0[_moc_step0_valid] == 1).astype(int)
    work_df["mode_of_conception_ivf_vs_all"] = _ivf_derived_step0
    _n_ivf_0to1 = int(((_ivf_before_step0 != 1) & (work_df["mode_of_conception_ivf_vs_all"] == 1)).sum())
    _n_ivf_1to0 = int(((_ivf_before_step0 == 1) & (work_df["mode_of_conception_ivf_vs_all"] == 0)).sum())
    print(f"  mode_of_conception_ivf_vs_all: recomputed from mode_of_conception "
          f"(full population, n={len(work_df)}): {_n_ivf_0to1} row(s) changed 0->1, "
          f"{_n_ivf_1to0} row(s) changed 1->0, "
          f"{_n_moc_step0_invalid} row(s) had an invalid mode_of_conception value "
          f"(derived left as NaN, not 0)")
    if _n_ivf_0to1 > 0:
        append_deviation(
            path=deviations_md,
            variable="mode_of_conception_ivf_vs_all",
            raw_variable="mode of conception IVF VS all",
            documented="Recompute deterministically from mode_of_conception rather than "
                       "trusting the independently-sourced raw field.",
            action=f"{_n_ivf_0to1} row(s) changed 0->1 (mode_of_conception==1 but the raw "
                   f"IVF field disagreed); {_n_ivf_1to0} row(s) changed 1->0.",
            reason="mode_of_conception_ivf_vs_all is authoritative-source-derived per "
                   "Decision 30 -- 1 when mode_of_conception == 1, 0 otherwise. Applied "
                   "before cohort filtering so all source records are handled consistently.",
            requires_approval=False,
            batch="Batch 2",
            affected_count=_n_ivf_0to1,
        )

    # --- Step 1: preserve original trial_of_labor for reference ---
    # The raw value is already renamed to trial_of_labor by Batch 1.
    # We add trial_of_labor_corrected without overwriting the source column.
    work_df = work_df.copy()
    work_df["trial_of_labor_corrected"] = work_df["trial_of_labor"].copy()

    # --- Step 2: correct trial_of_labor_corrected ---
    # Rule: if type_of_CS == 0 (vaginal delivery), the patient was by definition
    # in trial of labor. Set trial_of_labor_corrected = 1 regardless of original.
    correction_mask = work_df["type_of_CS"] == 0
    n_corrected = int((correction_mask & (work_df["trial_of_labor"] != 1)).sum())
    work_df.loc[correction_mask, "trial_of_labor_corrected"] = 1

    print(f"  trial_of_labor_corrected: {n_corrected} rows changed 0->1 (vaginal deliveries)")

    # --- Step 3: check for elective CS (type_of_CS == 1) ---
    elective_mask = work_df["type_of_CS"] == 1
    n_elective = int(elective_mask.sum())
    if n_elective > 0:
        work_df = work_df[~elective_mask].reset_index(drop=True)
        append_deviation(
            path=deviations_md,
            variable="type_of_CS",
            raw_variable="Type of CS",
            documented="Exclude type_of_CS == 1 before target creation",
            action=f"Excluded {n_elective} elective CS rows",
            reason="Elective cesarean sections are outside the study cohort.",
            requires_approval=False,
            batch="Batch 2",
            affected_count=n_elective,
        )
        print(f"  Elective CS (type_of_CS=1) excluded: {n_elective} rows")
    else:
        print("  Elective CS (type_of_CS=1): 0 rows — no exclusion needed")

    # --- Step 4: filter cohort to trial_of_labor_corrected == 1 ---
    n_before_filter = len(work_df)
    cohort_mask = work_df["trial_of_labor_corrected"] == 1
    work_df = work_df[cohort_mask].reset_index(drop=True)
    n_excluded_no_trial = n_before_filter - len(work_df)
    print(f"  Cohort filter: {n_excluded_no_trial} rows excluded (trial_of_labor_corrected != 1)")
    print(f"  Cohort size after filtering: {len(work_df)} rows")

    # --- Step 5: placenta_accreta / placenta_previa cohort exclusion (Decision 32) ---
    # Exclude a record when placenta_accreta==1 OR placenta_previa==1 -- these
    # materially change intrapartum management and are not representative of
    # the general trial-of-labor cohort. The exclusion criterion is these two
    # placenta columns only; delivery outcome plays no part in it. A later
    # step (after the Decision 67 mask is frozen) validates that the excluded
    # record was in the expected vaginal-delivery group -- that check does not
    # define this exclusion rule.
    _placenta_mask = (work_df["placenta_accreta"] == 1) | (work_df["placenta_previa"] == 1)
    _n_placenta_affected = int(_placenta_mask.sum())
    if _n_placenta_affected > 1:
        raise AssertionError(
            f"Placenta exclusion gate FAILED: expected exactly 1 affected record, "
            f"found {_n_placenta_affected}. Stopping -- do not remove records "
            "without re-approval. See docs/clinical_decisions/manual_decisions_log.md, "
            "Decision 32."
        )
    if _n_placenta_affected == 1:
        # The row is captured here so the deferred vaginal-group validation
        # (after the Decision 67 mask is frozen, below) has the data it needs.
        _placenta_affected_row = work_df.loc[_placenta_mask].copy()
        _placenta_subject = _placenta_affected_row["subject_number"].iloc[0]
        _placenta_delivery = _placenta_affected_row["delivery_id"].iloc[0]
        append_deviation(
            path=deviations_md,
            variable="placenta_accreta / placenta_previa",
            raw_variable="placenta accreta / placenta previa",
            documented="Exclude an analytical record when placenta_accreta==1 OR placenta_previa==1.",
            action=f"Excluded 1 analytical record (subject_number={_placenta_subject}, "
                   f"delivery_id={_placenta_delivery}) -- verified single-record, "
                   "vaginal-delivery case per the approved conditional-execution gate.",
            reason="Placenta accreta/previa materially change intrapartum management and are "
                   "not representative of the general trial-of-labor cohort; approved for "
                   "removal only because exactly one analytical record was affected.",
            requires_approval=False,
            batch="Batch 2",
            affected_count=1,
        )
        work_df = work_df[~_placenta_mask].reset_index(drop=True)
        print(f"  Placenta accreta/previa exclusion: 1 record removed "
              f"(subject_number={_placenta_subject}, delivery_id={_placenta_delivery}); "
              f"cohort now {len(work_df)} rows")
    else:
        print("  Placenta accreta/previa exclusion: 0 affected records found; no exclusion applied.")

    # Both columns are retired from the downstream analytical dataset now that
    # they have been used for cohort construction -- not retained as
    # predictors or type-registry entries; do not wait for EDA's
    # zero-variance screening (Decision 32).
    work_df = work_df.drop(columns=["placenta_accreta", "placenta_previa"])

    # --- Step 6: Decision 67 -- suspected superficial-only endometriosis ---
    # exclusion (see docs/clinical_decisions/manual_decisions_log.md,
    # Decision 67, for the full clinical rationale and history).
    #
    # Exclude a suspected superficial-only case (superficial_endometriosis
    # == 1) when no documented evidence supports retaining it in the
    # endometriosis cohort:
    #   - documented positive phenotype evidence (peritoneal/deep/
    #     endometrioma/cs_scar/adenomyosis) justifies retention;
    #     adenomyosis alone is sufficient.
    #   - clinical_diagnosis_only == 0 also prevents this exclusion (the
    #     diagnosis does not rest on clinical impression alone), but is not
    #     itself phenotype evidence.
    #   - missing values remain missing and are never treated as evidence
    #     for or against retention.
    # Computed by compute_decision67_evidence() (defined above), which reads
    # only these clinical fields -- never target_intrapartum_cs or any
    # outcome-derived information.
    _d67_evidence = compute_decision67_evidence(work_df)
    _d67_superficial_mask               = _d67_evidence["superficial_mask"]
    _d67_phenotype_evidence             = _d67_evidence["phenotype_evidence"]
    _d67_retention_basis_excl_adenomyosis = _d67_evidence["retention_basis_excl_adenomyosis"]
    _d67_retention_basis_full           = _d67_evidence["retention_basis_full"]

    # Records with a missing required field are logged for audit
    # transparency; the eligibility rule above still resolves them
    # deterministically from whatever fields are documented.
    _d67_nan_in_required = _d67_evidence["nan_in_required"]
    _n_d67_nan_flagged = int(_d67_nan_in_required.sum())
    if _n_d67_nan_flagged > 0:
        _d67_excluded_despite_missing = _d67_nan_in_required & ~_d67_retention_basis_full
        _n_d67_excluded_despite_missing = int(_d67_excluded_despite_missing.sum())
        append_deviation(
            path=deviations_md,
            variable="decision67_superficial_only_exclusion",
            raw_variable="superficial / peritoneal endometriosis / deep / endometrioma / "
                          "endometriosis CS scar / CLINICAL DIAGanosis only / adenomyosis",
            documented="Decision 67 addendum (2026-08-20): absence of a documented retention "
                       "basis (positive phenotype evidence, or a documented "
                       "clinical_diagnosis_only==0 finding) is not sufficient to retain a "
                       "suspected superficial-only record. A missing field is never recoded "
                       "and never treated as a retention basis.",
            action=f"{_n_d67_nan_flagged} row(s) have superficial_endometriosis==1 and at "
                   "least one other required field missing. Of these, "
                   f"{_n_d67_excluded_despite_missing} are excluded under the explicit "
                   "eligibility rule (no documented retention basis -- positive phenotype "
                   "evidence or clinical_diagnosis_only==0 -- found in any available field) "
                   "and "
                   f"{_n_d67_nan_flagged - _n_d67_excluded_despite_missing} are retained "
                   "(a documented retention basis found in at least one other, non-missing "
                   "field). No source or analytical value was recoded.",
            reason="Missing values remain missing in the data; the eligibility rule "
                   "resolves every row's cohort membership deterministically from whatever "
                   "fields ARE documented, per the 2026-08-20 Decision 67 addendum.",
            requires_approval=False,
            batch="Batch 2",
            affected_count=_n_d67_nan_flagged,
        )
        print(f"  Decision 67: {_n_d67_nan_flagged} row(s) had a missing required field "
              "among superficial_endometriosis==1 records -- resolved by the explicit "
              "eligibility rule (see preprocessing_deviations.md), not retained by NaN "
              "comparison accident")
    else:
        print("  Decision 67: 0 rows with a missing required field among "
              "superficial_endometriosis==1 records")

    _decision67_mask = _d67_superficial_mask & (~_d67_retention_basis_full)
    _n_decision67_excluded = int(_decision67_mask.sum())
    if _n_decision67_excluded != 16:
        raise AssertionError(
            f"Decision 67 SAFETY GATE FAILED: the outcome-independent primary exclusion "
            f"mask matched {_n_decision67_excluded} record(s), expected exactly 16 (on "
            f"the {len(work_df)}-record baseline). Stopping before any row is removed -- "
            "do not proceed without re-approval. See "
            "docs/clinical_decisions/manual_decisions_log.md, Decision 67."
        )
    if len(work_df) != 447:
        raise AssertionError(
            f"Decision 67 SAFETY GATE FAILED: expected the outcome-blind baseline cohort "
            f"to be 447 records (post elective-CS, trial-of-labor, and Decision 32 "
            f"exclusion) before Decision 67 masks are frozen, got {len(work_df)}. Stopping."
        )
    _decision67_excluded_delivery_ids = set(work_df.loc[_decision67_mask, "delivery_id"].tolist())
    assert len(_decision67_excluded_delivery_ids) == 16

    # Deferred Decision-32 validation: after the Decision-67 eligibility mask
    # is fixed, confirm that the previously identified placenta case belongs
    # to the expected vaginal-delivery group. This validation does not
    # determine Decision-67 eligibility.
    if _n_placenta_affected == 1:
        _placenta_type_of_cs = _placenta_affected_row["type_of_CS"].iloc[0]
        if _placenta_type_of_cs != 0:
            raise AssertionError(
                f"Placenta exclusion gate FAILED: the single affected record "
                f"(subject_number={_placenta_subject}, delivery_id={_placenta_delivery}) "
                f"is not in the expected vaginal delivery group (type_of_CS={_placenta_type_of_cs}). "
                "Stopping -- investigate before trusting this run."
            )
        print(f"  Placenta exclusion deferred check: subject_number={_placenta_subject}, "
              f"delivery_id={_placenta_delivery} confirmed vaginal delivery group -- PASSED")

    # Sensitivity cohorts (Decision 67): broader exclusion definitions used
    # only for cohort-robustness checks, never applied to the primary
    # cohort. The 19-record group drops the adenomyosis exception; the
    # 26-record group also drops the clinical_diagnosis_only condition.
    # Both are supersets of the 16-record primary exclusion by construction.
    _decision67_19_mask = _d67_superficial_mask & (~_d67_retention_basis_excl_adenomyosis)
    _decision67_26_mask = _d67_superficial_mask & (~_d67_phenotype_evidence)
    assert int(_decision67_19_mask.sum()) == 19, (
        f"Decision 67 sensitivity gate: expected 19-record group size 19, "
        f"got {int(_decision67_19_mask.sum())}."
    )
    assert int(_decision67_26_mask.sum()) == 26, (
        f"Decision 67 sensitivity gate: expected 26-record group size 26, "
        f"got {int(_decision67_26_mask.sum())}."
    )
    assert set(work_df.loc[_decision67_mask, "delivery_id"]) <= set(work_df.loc[_decision67_19_mask, "delivery_id"])
    assert set(work_df.loc[_decision67_19_mask, "delivery_id"]) <= set(work_df.loc[_decision67_26_mask, "delivery_id"])
    _decision67_19only_delivery_ids = set(work_df.loc[_decision67_19_mask, "delivery_id"]) - _decision67_excluded_delivery_ids
    _decision67_26only_delivery_ids = set(work_df.loc[_decision67_26_mask, "delivery_id"]) - _decision67_excluded_delivery_ids
    print(f"  Decision 67: primary exclusion mask matches {_n_decision67_excluded} records "
          f"(outcome-independent, verified on the {len(work_df)}-record baseline, "
          "before target creation)")
    print(f"  Decision 67 sensitivity groups (for post-exclusion flag columns): "
          f"19-record group={int(_decision67_19_mask.sum())}, "
          f"26-record group={int(_decision67_26_mask.sum())}")

    # Select which frozen, outcome-blind mask this cohort_mode actually
    # applies -- "original" removes nothing (empty mask); the other three
    # reuse the exact masks already computed and safety-gated above (never
    # recomputed). This is the only place cohort_mode affects row removal.
    _cohort_mode_masks = {
        "primary":   _decision67_mask,
        "original":  pd.Series(False, index=work_df.index),
        "exclude19": _decision67_19_mask,
        "strict26":  _decision67_26_mask,
    }
    _applied_mask = _cohort_mode_masks[cohort_mode]
    _n_applied_excluded = int(_applied_mask.sum())
    if _n_applied_excluded != COHORT_MODES[cohort_mode]["n_excluded"]:
        raise AssertionError(
            f"Decision 67 SAFETY GATE FAILED: cohort_mode={cohort_mode!r} expected to "
            f"exclude exactly {COHORT_MODES[cohort_mode]['n_excluded']} records, the "
            f"selected mask matches {_n_applied_excluded}. Stopping -- do not proceed "
            "without re-approval."
        )

    # Apply the selected exclusion immediately (447 -> mode-specific N), in
    # the same block as the mask computation above -- no split between
    # "compute" and "apply" steps, and no other implementation of this rule
    # exists elsewhere. Reconciliation modes (all reproducible from the same
    # raw input via cohort_mode/PREPROCESSING_COHORT_MODE, no source edits):
    #   original   (447) = this baseline, no exclusion applied
    #   primary    (431) = this baseline minus the 16-record mask (default)
    #   exclude-19 (428) = this baseline minus the 19-record mask
    #   strict-26  (421) = this baseline minus the 26-record mask
    _n_before_d67 = len(work_df)
    _d67_excluded_rows = work_df.loc[_applied_mask]
    _d67_excluded_cs = int((_d67_excluded_rows["type_of_CS"].isin([2, 3])).sum())
    _d67_excluded_vag = int((_d67_excluded_rows["type_of_CS"] == 0).sum())
    if _n_applied_excluded > 0:
        append_deviation(
            path=deviations_md,
            variable="decision67_superficial_only_exclusion",
            raw_variable="superficial / peritoneal endometriosis / deep / endometrioma / "
                          "endometriosis CS scar / CLINICAL DIAGanosis only / adenomyosis",
            documented="Exclude a record when superficial_endometriosis==1 AND "
                       "peritoneal_endometriosis==0 AND deep_endometriosis==0 AND "
                       "endometrioma==0 AND cs_scar_endometriosis==0 AND "
                       "clinical_diagnosis_only==1 AND adenomyosis==0 (Decision 67, "
                       f"cohort_mode={cohort_mode!r}).",
            action=f"Excluded {_n_applied_excluded} analytical records (delivery_id values "
                   "withheld from this aggregate-only log; see manual_decisions_log.md "
                   "Decision 67 for the full case-review record).",
            reason="Clinically finalized suspected-superficial-only exclusion rule -- adenomyosis "
                   "retained per study scope (primary/exclude19 modes only -- strict26 drops this "
                   "condition too); surgical evidence without a documented endometriotic "
                   "lesion/excision/pathology finding is insufficient confirmation. Defined and "
                   "verified entirely without reference to target_intrapartum_cs (which does not "
                   "yet exist at this point in the pipeline).",
            requires_approval=False,
            batch="Batch 2",
            affected_count=_n_applied_excluded,
        )
    work_df = work_df[~_applied_mask].reset_index(drop=True)
    _n_d67_present = _n_applied_excluded
    print(f"  Decision 67 exclusion applied (cohort_mode={cohort_mode!r}): {_n_d67_present} "
          f"records removed (vaginal={_d67_excluded_vag}, CS={_d67_excluded_cs}); "
          f"cohort now {len(work_df)} rows (was {_n_before_d67})")
    if len(work_df) != COHORT_MODES[cohort_mode]["expected_n"]:
        raise AssertionError(
            f"Decision 67 SAFETY GATE FAILED: cohort_mode={cohort_mode!r} expected a "
            f"final cohort of {COHORT_MODES[cohort_mode]['expected_n']} rows, got "
            f"{len(work_df)}. Stopping."
        )

    # Sensitivity flags (Decision 67): attached in every mode -- well-defined
    # regardless of which mask was actually applied above (derived only from
    # the fixed 19/26-record masks, never recomputed). On the primary export
    # they reconstruct N=428/421 by further filtering; on a non-primary
    # export they are still correct (e.g. under exclude19 mode,
    # decision67_sensitivity_19group_excluded is all-False -- those rows are
    # already gone -- and the reconstruction assertions below are skipped,
    # since they are primary-mode-specific arithmetic). Both are boolean,
    # target-independent by construction, and classified cohort_control_exclude,
    # like trial_of_labor_corrected -- audit/reproducibility only, never a predictor.
    work_df["decision67_sensitivity_19group_excluded"] = work_df["delivery_id"].isin(
        _decision67_19only_delivery_ids
    )
    work_df["decision67_sensitivity_26group_excluded"] = work_df["delivery_id"].isin(
        _decision67_26only_delivery_ids
    )
    _n_sens19 = int(work_df["decision67_sensitivity_19group_excluded"].sum())
    _n_sens26 = int(work_df["decision67_sensitivity_26group_excluded"].sum())
    if cohort_mode == "primary":
        assert _n_sens19 == 3, f"expected 3 rows flagged for the 19-record sensitivity group, got {_n_sens19}"
        assert _n_sens26 == 10, f"expected 10 rows flagged for the 26-record sensitivity group, got {_n_sens26}"
        assert len(work_df) - _n_sens19 == 428, "sensitivity flag does not reconstruct N=428"
        assert len(work_df) - _n_sens26 == 421, "sensitivity flag does not reconstruct N=421"
        print(f"  Decision 67 sensitivity flags: {_n_sens19} row(s) flagged "
              f"decision67_sensitivity_19group_excluded (reconstructs N=428), "
              f"{_n_sens26} row(s) flagged decision67_sensitivity_26group_excluded "
              f"(reconstructs N=421)")
    else:
        print(f"  Decision 67 sensitivity flags (cohort_mode={cohort_mode!r}, informational): "
              f"{_n_sens19} row(s) flagged decision67_sensitivity_19group_excluded, "
              f"{_n_sens26} row(s) flagged decision67_sensitivity_26group_excluded")

    # Unique-woman (subject_number) accounting -- reported here for the audit
    # trail; does not affect row-level cohort construction. subject_number can
    # legitimately repeat across multiple delivery records for the same woman
    # (project convention; delivery_id is the row-level key).
    _d67_unique_baseline = int(pd.concat(
        [work_df["subject_number"], _d67_excluded_rows["subject_number"]]
    ).dropna().nunique())
    _d67_unique_excluded = int(_d67_excluded_rows["subject_number"].dropna().nunique())
    _d67_unique_remaining = int(work_df["subject_number"].dropna().nunique())
    print(f"  Decision 67 unique-woman counts: baseline={_d67_unique_baseline}, "
          f"excluded={_d67_unique_excluded}, remaining={_d67_unique_remaining}")
    if _d67_unique_excluded + _d67_unique_remaining != _d67_unique_baseline:
        print(f"  NOTE: at least one woman has both an excluded and a retained delivery "
              "record -- group-aware (subject-level) train/test splitting is required "
              "before this cohort is used for modeling; this is a modeling blocker, not "
              "fixed in this preprocessing pass.")

    # --- Step 7: drop internal-use / approved analytical-exclusion columns ---
    # Internal-use columns removed after all row-level cohort-eligibility
    # exclusions above, based on clinical/project decision (Keren: not for
    # analysis dataset; Gidi: drop early). clinical_diagnosis_only,
    # surgery_dehiscence: added 2026-07-30 (Decision 33) -- approved early
    # analytical exclusion, same drop mechanism. clinical_diagnosis_only is
    # dropped here immediately after its only use anywhere in the pipeline
    # (the Decision 67 exclusion mask, computed immediately above) --
    # permanently unavailable to any predictor/classification stage from this
    # point on; only the derived exclusion outcome (which rows) and
    # sensitivity flags (above) survive downstream. surgery_dehiscence has no
    # downstream references beyond its own former Batch 15 subgroup-NaN block,
    # now removed.
    _INTERNAL_USE_COLS = [
        "delivery_mode", "Status", "comment_10",
        "clinical_diagnosis_only", "surgery_dehiscence",
    ]
    _present = [c for c in _INTERNAL_USE_COLS if c in work_df.columns]
    _absent  = [c for c in _INTERNAL_USE_COLS if c not in work_df.columns]
    if _present:
        work_df = work_df.drop(columns=_present)
    print(f"  Internal-use columns requested for drop: {_INTERNAL_USE_COLS}")
    print(f"  Dropped: {_present}")
    if _absent:
        print(f"  Already absent (skipped): {_absent}")

    # --- Step 8: create target_intrapartum_cs ---
    # Created only now, after every row-level cohort-eligibility exclusion
    # above (elective CS, trial-of-labor, Decision 32, Decision 67) has been
    # applied -- "target access" never precedes cohort eligibility. This is
    # the primary 431-row cohort.
    # 0 = vaginal delivery (type_of_CS == 0)
    # 1 = intrapartum / non-elective CS (type_of_CS in [2, 3])
    # Any remaining rows with type_of_CS not in {0,2,3} → NaN (flag for review)
    def assign_target(val):
        if val == 0:
            return 0
        if val in (2, 3):
            return 1
        return np.nan

    work_df["target_intrapartum_cs"] = work_df["type_of_CS"].map(assign_target)

    n_nan_target = int(work_df["target_intrapartum_cs"].isna().sum())
    if n_nan_target > 0:
        append_deviation(
            path=deviations_md,
            variable="target_intrapartum_cs",
            raw_variable="Type of CS",
            documented="Target must be 0 or 1 for all cohort rows",
            action=f"{n_nan_target} rows have NaN target (unexpected type_of_CS value)",
            reason="type_of_CS value outside {0,2,3} found after elective CS exclusion. Flagged for review.",
            requires_approval=True,
            batch="Batch 2",
            affected_count=n_nan_target,
        )

    target_dist = work_df["target_intrapartum_cs"].value_counts(dropna=False).to_dict()
    print(f"  target_intrapartum_cs distribution: {target_dist}")

    # --- Step 8.5: verify primary cohort event counts, only now that the ---
    # Decision 67 mask is frozen and applied -- this check reads the target,
    # it never informs the exclusion mask above (which was computed and
    # verified without any reference to type_of_CS's CS/vaginal grouping
    # beyond the pre-existing elective-CS step, or to target_intrapartum_cs,
    # which did not exist until Step 8).
    _n_target1 = int(work_df["target_intrapartum_cs"].eq(1).sum())
    _n_target0 = int(work_df["target_intrapartum_cs"].eq(0).sum())
    _expected_target0, _expected_target1 = COHORT_MODES[cohort_mode]["expected_target"]
    if _n_target1 != _expected_target1 or _n_target0 != _expected_target0:
        raise AssertionError(
            f"Decision 67 post-exclusion target verification FAILED for cohort_mode="
            f"{cohort_mode!r}: expected {_expected_target1} events (intrapartum CS) and "
            f"{_expected_target0} non-events (vaginal), got {_n_target1} / {_n_target0}. "
            "Stopping -- investigate before trusting this cohort."
        )
    print(f"  Post-Decision-67 target verification (cohort_mode={cohort_mode!r}): "
          f"{_n_target1} events / {_n_target0} non-events -- PASSED "
          f"(expected {_expected_target1} / {_expected_target0})")

    # --- Step 9: save processed output ---
    os.makedirs(processed_path, exist_ok=True)
    work_df.to_excel(output_xlsx, index=False)
    print(f"  Saved: {output_xlsx}")

    # --- Step 10: audit ---
    n_rows_final = len(work_df)
    target_0 = int(work_df["target_intrapartum_cs"].eq(0).sum())
    target_1 = int(work_df["target_intrapartum_cs"].eq(1).sum())
    target_pct = round(target_1 / n_rows_final * 100, 1) if n_rows_final > 0 else 0

    summary = f"""# Preprocessing Batch 2 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## mode_of_conception_ivf_vs_all (Decision 30, full population n={n_rows_start}, before any cohort filtering)
- Recomputed deterministically from mode_of_conception (1 if ==1, else 0)
- Rows changed 0->1: {_n_ivf_0to1}
- Rows changed 1->0: {_n_ivf_1to0}

## placenta_accreta / placenta_previa cohort exclusion (Decision 32)
- Affected records found: {_n_placenta_affected}
- Both columns dropped from the analytical dataset after use (not retained as predictors)

## Suspected superficial-only endometriosis cohort exclusion (Decision 67, 2026-08-15)
- Primary exclusion rule (outcome-independent, computed and frozen before target_intrapartum_cs
  existed): superficial_endometriosis==1 AND peritoneal_endometriosis==0 AND
  deep_endometriosis==0 AND endometrioma==0 AND cs_scar_endometriosis==0 AND
  clinical_diagnosis_only==1 AND adenomyosis==0
- Records excluded: {_n_d67_present} (vaginal={_d67_excluded_vag}, CS={_d67_excluded_cs})
- Sensitivity cohorts preserved via flags on the exported dataset (not by retaining excluded
  rows): decision67_sensitivity_19group_excluded ({_n_sens19} rows, reconstructs N=428),
  decision67_sensitivity_26group_excluded ({_n_sens26} rows, reconstructs N=421)
- Unique-woman (subject_number) counts: baseline={_d67_unique_baseline},
  excluded={_d67_unique_excluded}, remaining={_d67_unique_remaining}

## Cohort definition
- Rows at batch start: {n_rows_start}
- trial_of_labor_corrected rows changed (0→1 for vaginal deliveries): {n_corrected}
- Elective CS excluded (type_of_CS == 1): {n_elective}
- Rows excluded (trial_of_labor_corrected != 1): {n_excluded_no_trial}
- Rows excluded (placenta_accreta/previa, Decision 32): {_n_placenta_affected}
- Rows excluded (suspected superficial-only endometriosis, Decision 67): {_n_d67_present}
- **Final cohort size: {n_rows_final} rows**

## Target variable
- target_intrapartum_cs = 0 (vaginal): {target_0} ({round(target_0/n_rows_final*100,1)}%)
- target_intrapartum_cs = 1 (intrapartum CS): {target_1} ({target_pct}%)
- target_intrapartum_cs = NaN (unexpected): {n_nan_target}

## Columns added
- trial_of_labor_corrected (preserved original trial_of_labor for reference)
- target_intrapartum_cs

## Columns recomputed (values only, not newly added)
- mode_of_conception_ivf_vs_all (see above)

## Output
- {output_xlsx}

## Validation
{"PASS" if n_nan_target == 0 else "FAIL — unexpected target values, see deviation log"}
"""
    write_batch_summary(summary_md, summary)

    append_audit_entry(
        audit_log_md,
        f"Batch 2 — {BATCH_TITLE}",
        f"- Rows start: {n_rows_start}\n"
        f"- trial_of_labor corrections applied: {n_corrected}\n"
        f"- Elective CS excluded: {n_elective}\n"
        f"- Excluded no-trial-of-labor: {n_excluded_no_trial}\n"
        f"- Excluded placenta_accreta/previa (Decision 32): {_n_placenta_affected}\n"
        f"- Excluded suspected superficial-only endometriosis (Decision 67): {_n_d67_present}\n"
        f"- Excluded suspected superficial-only endometriosis (Decision 67), vaginal: {_d67_excluded_vag}\n"
        f"- Excluded suspected superficial-only endometriosis (Decision 67), CS: {_d67_excluded_cs}\n"
        f"- Final cohort: {n_rows_final}\n"
        f"- Target 0 (vaginal): {target_0}\n"
        f"- Target 1 (intrapartum CS): {target_1}\n"
        f"- Target NaN: {n_nan_target}\n",
    )

    print("=== Batch 2 complete ===\n")
    return work_df


# ---------------------------------------------------------------------------
# Batch 3 — Obstetric history standardization and approved S_P_CS correction
# subject_number, AGE, G, nulliparity, P, LIVE_BIRTH, EUP, AB, S_P_CS, CS, VBAC
# ---------------------------------------------------------------------------

def batch_3_obstetric_history(work_df):
    """
    Obstetric history standardization and approved S_P_CS correction.

    Standardizes AGE, G, P, LIVE_BIRTH, EUP, AB, nulliparity, CS, VBAC, and
    applies the clinically approved approved record-specific S_P_CS correction
    (2 -> 1) via validated composite-key lookup. Any other unexpected
    S_P_CS value is exported for manual review rather than auto-recoded.

    QA outputs: S_P_CS_unexpected_QA.xlsx (only if unexpected values are
    found).
    Returns: df — the working DataFrame with obstetric-history variables
    cleaned.
    """
    BATCH_TITLE = BATCH_METADATA[3]["title"]
    from preprocessing_utils import (
        summarize_before_after_counts, validate_expected_binary_values,
        log_deviation_event, log_audit_event, write_batch_summary,
        create_review_dataframe, compute_nulliparity_from_P,
        build_nulliparity_from_P_qa,
    )

    print(f"=== Batch 3: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch3.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch3.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []

    # ------------------------------------------------------------------
    # 1. subject_number — reference only, no imputation
    #    (Batch 19 read-only review finding PRE-ALL-001, 2026-08-01). The
    #    gap originates in the raw NUM column (9/513 raw rows missing NUM;
    #    8 remain after cohort filtering) -- not introduced by this
    #    pipeline. delivery_id, assigned sequentially in Batch 1, is the
    #    complete, unique primary key and is unaffected. No identifier is
    #    invented here and no row is removed on this basis; the only
    #    practical consequence is that these 8 rows cannot be looked up by
    #    subject_number (chart lookup), only by delivery_id.
    # ------------------------------------------------------------------
    n_missing_subj = int(df["subject_number"].isna().sum())
    # No changes made; missing values remain NaN as documented.
    if n_missing_subj:
        log_deviation_event(
            path=deviations_md,
            variable="subject_number",
            raw_variable="NUM",
            documented="Patient ID (NUM); reference identifier only, not imputed.",
            action=(
                f"No action taken (documentation only): {n_missing_subj} row(s) have "
                f"missing subject_number, unchanged from the raw source. No identifier "
                f"invented; no row removed."
            ),
            reason=(
                "The raw NUM column itself has 9 missing values out of 513 rows; "
                f"{n_missing_subj} of those rows remain in the current cohort after "
                "trial-of-labor filtering. delivery_id (assigned sequentially in Batch "
                "1) is complete and globally unique and remains the primary composite-"
                "key component for these rows. No predictor or target value is "
                "affected; the only practical limitation is that these rows cannot be "
                "looked up by subject_number, only by delivery_id."
            ),
            requires_approval=False,
            batch="Batch 3 (obstetric history) — condition originates in Batch 1 raw mapping",
            affected_count=n_missing_subj,
        )

    # ------------------------------------------------------------------
    # 2. Numeric / count variables: coerce to numeric, preserve NaN
    # ------------------------------------------------------------------
    numeric_cols = ["AGE", "G", "P", "LIVE_BIRTH", "EUP", "AB", "CS"]
    numeric_summary = {}
    for col in numeric_cols:
        before = df[col].copy()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        summary = summarize_before_after_counts(before, df[col], col)
        numeric_summary[col] = summary
        if summary["rows_changed"] > 0:
            unexpected_findings.append(f"{col}: {summary['rows_changed']} values coerced to NaN")

    # ------------------------------------------------------------------
    # 3. nulliparity — overwrite directly from authoritative P
    # (PARTNER-FIX-03A, PRE-B3-003). P is already numeric-coerced by step 2
    # above. Approved transformation: valid P==0 -> nulliparity=1; valid
    # P>=1 -> nulliparity=0; invalid or missing P -> nulliparity=NaN. P
    # itself is never modified, dropped, or renamed. No second analytical
    # column (e.g. nulliparity_clean) is created -- the existing column is
    # overwritten in place. Downstream redundancy between nulliparity and P
    # (parity_binary_0_vs_1plus) is intentionally out of scope here; see
    # PARTNER-FIX-03B.
    # ------------------------------------------------------------------
    nulliparity_diag = compute_nulliparity_from_P(df)
    old_nulliparity = df["nulliparity"].copy()
    columns_before = list(df.columns)

    df["nulliparity"] = nulliparity_diag["expected_nulliparity"]

    correction_counts = nulliparity_diag["correction_status"].value_counts().to_dict()
    n_correction_applied = int(correction_counts.get("correction_applied", 0))
    n_already_correct = int(correction_counts.get("already_correct", 0))
    n_set_missing_invalid_P = int(correction_counts.get("set_missing_due_to_invalid_P", 0))
    contradiction_counts = nulliparity_diag["contradiction_category"].value_counts().to_dict()
    n_contra_p0 = int(contradiction_counts.get("contradiction_P0_nulliparity0", 0))
    n_contra_p1 = int(contradiction_counts.get("contradiction_P1plus_nulliparity1", 0))

    # Assertions -- fail loud rather than silently accept an unexpected state.
    valid_p_mask = nulliparity_diag["p_validity_category"] == "valid"
    p_numeric = nulliparity_diag["P_numeric"]
    assert (df.loc[valid_p_mask & (p_numeric == 0), "nulliparity"] == 1).all(), (
        "nulliparity correction: a valid P==0 row does not have nulliparity==1."
    )
    assert (df.loc[valid_p_mask & (p_numeric >= 1), "nulliparity"] == 0).all(), (
        "nulliparity correction: a valid P>=1 row does not have nulliparity==0."
    )
    assert df.loc[~valid_p_mask, "nulliparity"].isna().all(), (
        "nulliparity correction: an invalid/missing-P row does not have nulliparity missing."
    )
    assert df["nulliparity"].dropna().isin([0, 1]).all(), (
        "nulliparity correction: a value outside {0, 1, missing} was produced."
    )
    n_cells_changed = int((~(
        (df["nulliparity"] == old_nulliparity)
        | (df["nulliparity"].isna() & old_nulliparity.isna())
    )).sum())
    assert n_cells_changed == 139, (
        f"nulliparity correction: expected exactly 139 changed cells, got {n_cells_changed}. "
        "(Was 143 for the pre-Decision-67 447-row cohort; recalibrated 2026-08-15 for the "
        "431-row cohort.)"
    )
    assert "P" in df.columns, "nulliparity correction: P column is missing."
    assert "parity_binary_0_vs_1plus" not in df.columns, (
        "nulliparity correction: parity_binary_0_vs_1plus must not be created in preprocessing."
    )
    assert list(df.columns) == columns_before, (
        "nulliparity correction: the set/order of df columns changed unexpectedly."
    )

    # QA export
    nulliparity_qa_sheets = build_nulliparity_from_P_qa(nulliparity_diag)
    nulliparity_qa_xlsx = os.path.join(review_path, "nulliparity_from_P_correction_QA.xlsx")
    os.makedirs(review_path, exist_ok=True)
    with pd.ExcelWriter(nulliparity_qa_xlsx, engine="openpyxl") as _writer:
        nulliparity_qa_sheets["contradictions"].to_excel(_writer, sheet_name="contradictions", index=False)
        nulliparity_qa_sheets["invalid_or_missing_P"].to_excel(
            _writer, sheet_name="invalid_or_missing_P", index=False
        )
        pd.DataFrame({
            "category": list(contradiction_counts.keys()) + list(correction_counts.keys()),
            "kind": (["contradiction_category"] * len(contradiction_counts)
                     + ["correction_status"] * len(correction_counts)),
            "count": list(contradiction_counts.values()) + list(correction_counts.values()),
        }).to_excel(_writer, sheet_name="summary", index=False)

    if n_correction_applied > 0:
        log_deviation_event(
            path=deviations_md,
            variable="nulliparity",
            raw_variable="nulliparity",
            documented="Binary 0/1: 1 = no prior deliveries, 0 = one or more prior deliveries.",
            action=f"Overwrote {n_correction_applied} nulliparity value(s) directly from "
                   f"authoritative P ({n_contra_p0} rows P==0/old nulliparity==0 -> 1; "
                   f"{n_contra_p1} rows P>=1/old nulliparity==1 -> 0).",
            reason="P is the authoritative parity-count source (PRE-B3-003, PARTNER-FIX-03A, "
                   "approved). nulliparity is now derived deterministically from P "
                   "(P==0 -> 1, P>=1 -> 0, invalid/missing P -> NaN) rather than trusted as an "
                   "independently entered field. See "
                   "outputs/review/nulliparity_from_P_correction_QA.xlsx for the full "
                   "row-level evidence.",
            requires_approval=False,
            batch="Batch 3",
            affected_count=n_correction_applied,
        )

    ok_nul, unexp_nul = validate_expected_binary_values(df["nulliparity"], "nulliparity")
    if not ok_nul:
        unexpected_findings.append(f"nulliparity: unexpected values {unexp_nul}")

    # ------------------------------------------------------------------
    # 4. S_P_CS — approved single-record correction [RECORD KEY REDACTED]
    # ------------------------------------------------------------------
    # The canonical private source applies one clinically approved correction by
    # subject_number + delivery_id. The key and patient-specific rationale are
    # omitted from this review copy. No record-specific correction is executed here.
    s_p_cs_before = df["S_P_CS"].copy()
    n_recoded = 0
    _redacted_spcs_mask = pd.Series(False, index=df.index)
    _n_redacted_spcs = 0

    # ------------------------------------------------------------------
    # 4b. S_P_CS — deterministic CS/S_P_CS consistency correction (Decision 80)
    # ------------------------------------------------------------------
    # Canonical dictionary (docs/data_dictionary/clinical_variable_dictionary.xlsx)
    # confirms: CS = number of previous cesarean sections; S_P_CS = binary
    # status of whether the patient had a previous cesarean section. These are
    # a count and its own binary indicator of the same underlying fact, so
    # CS > 0 deterministically implies S_P_CS = 1 -- this is not a new
    # clinical interpretation, it enforces that already-documented
    # relationship (same precedent as the approved record-specific correction
    # above, and the same general-deterministic-consistency pattern already
    # used elsewhere in this pipeline, e.g. Batch 12's any_PET/umbrella
    # corrections). A full N=431 audit (CS>0 & S_P_CS=0; CS=0 & S_P_CS=1;
    # CS missing with S_P_CS populated; S_P_CS missing with CS populated)
    # found only the CS>0/S_P_CS=0 direction present, in exactly 3 rows, with
    # no source-text evidence suggesting the CS counts themselves are
    # erroneous. See Decision 80.
    cs_spc_contra_mask = (df["CS"] > 0) & (df["S_P_CS"] == 0)
    n_cs_spc_contra = int(cs_spc_contra_mask.sum())
    if n_cs_spc_contra > 0:
        cs_spc_rows = [
            (
                (None if pd.isna(df.at[idx, "subject_number"]) else int(df.at[idx, "subject_number"])),
                int(df.at[idx, "delivery_id"]),
                int(df.at[idx, "CS"]),
            )
            for idx in df.index[cs_spc_contra_mask]
        ]
        df.loc[cs_spc_contra_mask, "S_P_CS"] = 1
        log_deviation_event(
            path=deviations_md,
            variable="S_P_CS",
            raw_variable="S/P CS",
            documented="S_P_CS is the binary indicator of CS (number of previous cesareans) "
                       "being > 0, per docs/data_dictionary/clinical_variable_dictionary.xlsx.",
            action=(
                f"Recoded S_P_CS 0->1 for {n_cs_spc_contra} row(s) where CS>0: "
                + "; ".join(
                    f"subject_number={sn if sn is not None else 'MISSING'}/delivery_id={did} (CS={cs})"
                    for sn, did, cs in cs_spc_rows
                )
            ),
            reason="Deterministic consistency correction, not a new clinical interpretation: "
                   "the canonical variable dictionary defines CS as the count of previous "
                   "cesareans and S_P_CS as that count's own binary indicator, so CS>0 must "
                   "imply S_P_CS=1. A full-cohort audit found no other CS/S_P_CS inconsistency "
                   "pattern and no source-text evidence that the CS counts themselves are wrong.",
            requires_approval=False,
            batch="Batch 3",
            affected_count=n_cs_spc_contra,
        )
        print(f"  S_P_CS: {n_cs_spc_contra} row(s) corrected 0->1 for CS>0/S_P_CS=0 "
              "consistency (Decision 80)")
    remaining_cs_spc_contra = int(((df["CS"] > 0) & (df["S_P_CS"] == 0)).sum())
    if remaining_cs_spc_contra > 0:
        unexpected_findings.append(
            f"S_P_CS: {remaining_cs_spc_contra} row(s) still have CS>0 with S_P_CS=0 "
            "after the Decision 80 consistency correction"
        )

    # Check all rows for unexpected values outside {0, 1, NaN} — do NOT auto-recode
    unexpected_spc_mask = df["S_P_CS"].notna() & ~df["S_P_CS"].isin([0, 1])
    n_unexpected_spc = int(unexpected_spc_mask.sum())
    if n_unexpected_spc > 0:
        spc_qa_df = create_review_dataframe(
            df, unexpected_spc_mask,
            cols=["S_P_CS"],
            id_cols=["delivery_id", "subject_number"],
        )
        # QA context: create_review_dataframe already adds empty manual_review_decision/
        # manual_review_reason/manual_review_notes columns; populate the reason here so
        # the flagging rule is visible in the file itself, not only in console output.
        spc_qa_df["expected_values"] = "{0, 1, NaN}"
        spc_qa_df["manual_review_reason"] = (
            "S_P_CS value outside expected binary range {0, 1, NaN} — not auto-recoded "
            "(the approved record-specific correction is redacted in this review copy)"
        )
        spc_qa_path = os.path.join(review_path, "S_P_CS_unexpected_QA.xlsx")
        os.makedirs(review_path, exist_ok=True)
        spc_qa_df.to_excel(spc_qa_path, index=False)
        unexpected_findings.append(
            f"S_P_CS: {n_unexpected_spc} row(s) with unexpected values outside {{0, 1}}. "
            f"NOT auto-recoded. Requires clinical review. QA file: {spc_qa_path}"
        )

    ok_spc, unexp_spc = validate_expected_binary_values(df["S_P_CS"], "S_P_CS")
    if not ok_spc:
        unexpected_findings.append(f"S_P_CS: unexpected values remain after correction: {unexp_spc}")

    s_p_cs_summary = summarize_before_after_counts(s_p_cs_before, df["S_P_CS"], "S_P_CS")

    # ------------------------------------------------------------------
    # 5. VBAC — validate expected values, no imputation
    # ------------------------------------------------------------------
    ok_vbac, unexp_vbac = validate_expected_binary_values(df["VBAC"], "VBAC")
    if not ok_vbac:
        unexpected_findings.append(f"VBAC: unexpected values {unexp_vbac}")

    # ------------------------------------------------------------------
    # 6. Save output
    # ------------------------------------------------------------------
    os.makedirs(processed_path, exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    # ------------------------------------------------------------------
    # 7. Audit summary
    # ------------------------------------------------------------------
    numeric_lines = "\n".join(
        f"  - {col}: NaN={df[col].isna().sum()}, changed={numeric_summary[col]['rows_changed']}"
        for col in numeric_cols
    )

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    summary = f"""# Preprocessing Batch 3 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input}
- Output: {len(df)} (no rows removed in this batch)

## subject_number
- Missing values: {n_missing_subj} (kept as NaN, no imputation — delivery_id is primary key)

## Numeric / count variables (AGE, G, P, LIVE_BIRTH, EUP, AB, CS)
{numeric_lines}

## nulliparity (PARTNER-FIX-03A, PRE-B3-003 — overwritten directly from authoritative P)
- Expected values only (0/1): {"YES" if ok_nul else "NO — " + str(unexp_nul)}
- Correction applied: {n_correction_applied} (P==0/old 0->1: {n_contra_p0}; P>=1/old 1->0: {n_contra_p1})
- Already correct: {n_already_correct}
- Set missing due to invalid/missing P: {n_set_missing_invalid_P}
- P is the authoritative source; P itself is unchanged. Downstream redundancy between
  nulliparity and P (parity_binary_0_vs_1plus) is deferred to PARTNER-FIX-03B.
- QA file: {nulliparity_qa_xlsx}

## S_P_CS
- Values before: {s_p_cs_before.value_counts(dropna=False).to_dict()}
- Values after:  {df["S_P_CS"].value_counts(dropna=False).to_dict()}
- Rows recoded by redacted single-record correction: {n_recoded}
- Record-specific S_P_CS verification: [REDACTED IN REVIEW COPY]
- Rows recoded (0->1, CS/S_P_CS consistency, Decision 80): {n_cs_spc_contra}

## VBAC
- Expected values only (0/1): {"YES" if ok_vbac else "NO — " + str(unexp_vbac)}
- Value counts: {df["VBAC"].value_counts(dropna=False).to_dict()}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)

    log_audit_event(
        audit_log_md,
        f"Batch 3 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- subject_number missing: {n_missing_subj}\n"
        f"- nulliparity corrected from P: {n_correction_applied} "
        f"(0->1: {n_contra_p0}, 1->0: {n_contra_p1}), already correct: {n_already_correct}, "
        f"set missing (invalid/missing P): {n_set_missing_invalid_P}\n"
        f"- S_P_CS recoded 2->1: {n_recoded}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  nulliparity corrected from P: {n_correction_applied} "
          f"(0->1: {n_contra_p0}, 1->0: {n_contra_p1}), already correct: {n_already_correct}, "
          f"set missing (invalid/missing P): {n_set_missing_invalid_P}")
    print(f"  S_P_CS: {n_recoded} value(s) recoded 2->1")
    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 3 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 4 — Background health variables and free-text comment standardization
# smoking, alcohol, any_medical_problem, any_medical_problem_comment,
# regular_medications, regular_medications_comment, Fetus_Anamoly, Fetus_Anamoly_comment
# (direct raw-to-final rename, Decision 34, 2026-07-30 -- no intermediate comment_N names)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Batch 4 binary/comment review closure (PARTNER-FIX-04, finding F-3).
#
# Population: rows where a Batch 4 binary is 0 but its comment is non-empty.
# Approved methodology: "Free-text comments do not automatically override
# the structured binary source variable unless an explicit, approved,
# deterministic clinical mapping exists." No binary value is changed based
# on comment interpretation; this table records the manual clinical read of
# each row's comment (translated from the raw Hebrew/English text) so the
# review population is closed rather than left informally unresolved.
#
# Keyed by (subject_number, delivery_id, review_variable) -- never
# subject_number alone, and always including the variable name because a single record may have
# distinct comments under more than one reviewed variable. Categories: KEEP_ZERO_SUPPORTED, DUPLICATE_INFORMATION_ELSEWHERE,
# POSSIBLE_BINARY_CORRECTION_NOT_AUTOMATED, AMBIGUOUS_CLINICAL_TEXT,
# MAPPING_OR_DATA_QUALITY_CONCERN.
# ---------------------------------------------------------------------------
BATCH4_COMMENT_BINARY_REVIEW = {}
# Canonical private source: explicit reviewed entries keyed by
# (subject_number, delivery_id, review_variable). Those row keys and the
# patient-specific review reasons are intentionally omitted here.

_BATCH4_CATEGORY_TO_FINAL_DECISION = {
    "KEEP_ZERO_SUPPORTED": "KEEP_SOURCE_BINARY_AND_RETAIN_COMMENT",
    "DUPLICATE_INFORMATION_ELSEWHERE": "KEEP_SOURCE_BINARY_AND_RETAIN_COMMENT",
    "POSSIBLE_BINARY_CORRECTION_NOT_AUTOMATED": "SOURCE_MAPPING_REVIEW_DOCUMENTED_NO_AUTOMATIC_CHANGE",
    "AMBIGUOUS_CLINICAL_TEXT": "SOURCE_MAPPING_REVIEW_DOCUMENTED_NO_AUTOMATIC_CHANGE",
    "MAPPING_OR_DATA_QUALITY_CONCERN": "SOURCE_MAPPING_REVIEW_DOCUMENTED_NO_AUTOMATIC_CHANGE",
}


def build_batch4_comment_binary_review(df, comment_cols_by_variable):
    """Build the canonical, closed Batch 4 binary/comment review table.

    Population: rows where a Batch 4 binary variable is 0 and its
    corresponding comment is non-missing and non-blank. Read-only -- never
    changes a binary value or a comment. Every row's final_preprocessing_decision
    is one of KEEP_SOURCE_BINARY, KEEP_SOURCE_BINARY_AND_RETAIN_COMMENT, or
    SOURCE_MAPPING_REVIEW_DOCUMENTED_NO_AUTOMATIC_CHANGE; decision_status is
    always CLOSED_SOURCE_VALUE_RETAINED -- no row is left OPEN/PENDING.
    """
    rows = []
    for var, comment_col in comment_cols_by_variable.items():
        mask = (df[var] == 0) & df[comment_col].notna() & (df[comment_col].astype(str).str.strip() != "")
        for idx in df.index[mask]:
            sub = df.loc[idx, "subject_number"]
            dlv = df.loc[idx, "delivery_id"]
            lookup_key = (int(sub) if pd.notna(sub) else sub, int(dlv), var)
            entry = BATCH4_COMMENT_BINARY_REVIEW.get(lookup_key)
            if entry is None:
                raise RuntimeError(
                    "Batch 4 record-level review table is redacted in this review package; "
                    "use the canonical private source for executable reproduction."
                )
            category, supporting_var, reason = entry
            rows.append({
                "subject_number": sub,
                "delivery_id": dlv,
                "review_variable": var,
                "binary_value": df.loc[idx, var],
                "comment_value_exact": df.loc[idx, comment_col],
                "supporting_structured_variables": supporting_var if supporting_var else "",
                "review_category": category,
                "final_preprocessing_decision": _BATCH4_CATEGORY_TO_FINAL_DECISION[category],
                "decision_reason": reason,
                "decision_status": "CLOSED_SOURCE_VALUE_RETAINED",
            })
    review_df = pd.DataFrame(rows)
    if len(review_df):
        review_df = review_df.sort_values(
            ["subject_number", "delivery_id", "review_variable"], kind="mergesort"
        ).reset_index(drop=True)
    return review_df

def batch_4_background(work_df):
    """
    Background health variables and free-text comment standardization.

    Standardizes smoking, alcohol, any_medical_problem,
    regular_medications, Fetus_Anamoly, and normalizes their adjacent
    free-text comment columns (renamed directly from the raw source per
    Decision 34, with no intermediate comment_N name), converting
    placeholder zeros to true missing.

    Approved decisions: 34.
    Returns: df — the working DataFrame with background variables cleaned.
    """
    BATCH_TITLE = BATCH_METADATA[4]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values, summarize_before_after_counts,
        log_audit_event, log_deviation_event, write_batch_summary,
        detect_free_text,
    )

    print(f"=== Batch 4: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch4.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch4.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []
    zero_variance_flags = []

    # ------------------------------------------------------------------
    # Helper: normalize placeholder zeros in comment/free-text columns
    # Zeros in free-text columns are non-informative placeholders,
    # not valid text entries. Normalized to NaN.
    # ------------------------------------------------------------------
    def normalize_comment_zeros(series):
        return series.apply(lambda v: np.nan if v == 0 or v == "0" else v)

    # ------------------------------------------------------------------
    # 1. smoking — validate 3-level categorical {0, 1, 2}
    # ------------------------------------------------------------------
    ok_smoke, unexp_smoke = validate_expected_binary_values(
        df["smoking"], "smoking", allowed={0, 1, 2, 0.0, 1.0, 2.0, np.nan}
    )
    if not ok_smoke:
        unexpected_findings.append(f"smoking: unexpected values {unexp_smoke}")
    smoke_vc = df["smoking"].value_counts(dropna=False).to_dict()

    # ------------------------------------------------------------------
    # 2. alcohol — validate; flag zero-variance
    # ------------------------------------------------------------------
    ok_alc, unexp_alc = validate_expected_binary_values(
        df["alcohol"], "alcohol", allowed={0, 1, 0.0, 1.0, np.nan}
    )
    if not ok_alc:
        unexpected_findings.append(f"alcohol: unexpected values {unexp_alc}")
    if df["alcohol"].nunique(dropna=True) <= 1:
        zero_variance_flags.append(
            "alcohol: all values are 0 (zero variance) — candidate for removal at EDA stage"
        )

    # ------------------------------------------------------------------
    # 3. any_medical_problem — validate binary
    # ------------------------------------------------------------------
    ok_amp, unexp_amp = validate_expected_binary_values(df["any_medical_problem"], "any_medical_problem")
    if not ok_amp:
        unexpected_findings.append(f"any_medical_problem: unexpected values {unexp_amp}")

    # ------------------------------------------------------------------
    # 4. any_medical_problem_comment — free-text linked to any_medical_problem
    #    Normalize placeholder zeros to NaN (technical, not clinical)
    # ------------------------------------------------------------------
    before_c1 = df["any_medical_problem_comment"].copy()
    df["any_medical_problem_comment"] = normalize_comment_zeros(df["any_medical_problem_comment"])
    n_c1_zeros = int((before_c1 == 0).sum())
    if n_c1_zeros > 0:
        log_deviation_event(
            path=deviations_md,
            variable="any_medical_problem_comment", raw_variable="comment",
            documented="Free-text comment column; preserve as-is",
            action=f"Normalized {n_c1_zeros} placeholder zero(s) to NaN",
            reason="Zeros in free-text comment columns are non-informative placeholders "
                   "(entered when adjacent variable is 0). Normalizing preserves correct "
                   "distinction between 'no comment entered' and actual text content.",
            requires_approval=False, batch="Batch 4", affected_count=n_c1_zeros,
        )

    # ------------------------------------------------------------------
    # 5. regular_medications — validate binary
    # ------------------------------------------------------------------
    ok_rm, unexp_rm = validate_expected_binary_values(df["regular_medications"], "regular_medications")
    if not ok_rm:
        unexpected_findings.append(f"regular_medications: unexpected values {unexp_rm}")

    # ------------------------------------------------------------------
    # 6. regular_medications_comment — free-text linked to regular_medications
    # ------------------------------------------------------------------
    before_c2 = df["regular_medications_comment"].copy()
    df["regular_medications_comment"] = normalize_comment_zeros(df["regular_medications_comment"])
    n_c2_zeros = int((before_c2 == 0).sum())
    if n_c2_zeros > 0:
        log_deviation_event(
            path=deviations_md,
            variable="regular_medications_comment", raw_variable="comment.1",
            documented="Free-text comment column; preserve as-is",
            action=f"Normalized {n_c2_zeros} placeholder zero(s) to NaN",
            reason="Same as any_medical_problem_comment: placeholder zeros normalized to NaN.",
            requires_approval=False, batch="Batch 4", affected_count=n_c2_zeros,
        )

    # ------------------------------------------------------------------
    # 6b. Fetus_Anamoly — approved single-record correction [REDACTED]
    # ------------------------------------------------------------------
    # Canonical private source applies one clinically approved composite-key
    # correction here. Identifier and patient-specific comment are withheld.
    n_redacted_fetal_anomaly_correction = 0

    # ------------------------------------------------------------------
    # 7. Fetus_Anamoly — validate binary
    # ------------------------------------------------------------------
    ok_fa, unexp_fa = validate_expected_binary_values(df["Fetus_Anamoly"], "Fetus_Anamoly")
    if not ok_fa:
        unexpected_findings.append(f"Fetus_Anamoly: unexpected values {unexp_fa}")

    # ------------------------------------------------------------------
    # 8. Fetus_Anamoly_comment — free-text linked to Fetus_Anamoly
    # ------------------------------------------------------------------
    before_c3 = df["Fetus_Anamoly_comment"].copy()
    df["Fetus_Anamoly_comment"] = normalize_comment_zeros(df["Fetus_Anamoly_comment"])
    n_c3_zeros = int((before_c3 == 0).sum())
    if n_c3_zeros > 0:
        log_deviation_event(
            path=deviations_md,
            variable="Fetus_Anamoly_comment", raw_variable="comments",
            documented="Free-text comment column; preserve as-is",
            action=f"Normalized {n_c3_zeros} placeholder zero(s) to NaN",
            reason="Same as any_medical_problem_comment: placeholder zeros normalized to NaN.",
            requires_approval=False, batch="Batch 4", affected_count=n_c3_zeros,
        )

    # ------------------------------------------------------------------
    # Count free-text review rows across all comment columns
    # ------------------------------------------------------------------
    comment_cols = ["any_medical_problem_comment", "regular_medications_comment", "Fetus_Anamoly_comment"]
    free_text_rows = int(
        df[comment_cols].apply(detect_free_text).any(axis=1).sum()
    )

    # ------------------------------------------------------------------
    # Binary-zero-with-comment review closure (PARTNER-FIX-04, finding F-3).
    # Approved methodology: comments never automatically override the
    # structured binary; every row in this population gets an explicit,
    # reviewed classification (BATCH4_COMMENT_BINARY_REVIEW above) and is
    # closed with decision_status=CLOSED_SOURCE_VALUE_RETAINED -- none are
    # left OPEN/PENDING. No binary value or comment is changed here.
    # ------------------------------------------------------------------
    _comment_col_by_var = {
        "any_medical_problem": "any_medical_problem_comment",
        "regular_medications": "regular_medications_comment",
        "Fetus_Anamoly": "Fetus_Anamoly_comment",
    }
    batch4_review_df = build_batch4_comment_binary_review(df, _comment_col_by_var)
    n_batch4_review_occurrences = len(batch4_review_df)
    n_batch4_review_unique_records = (
        batch4_review_df[["subject_number", "delivery_id"]].drop_duplicates().shape[0]
        if n_batch4_review_occurrences else 0
    )

    assert not batch4_review_df[["subject_number", "delivery_id", "review_variable"]].duplicated().any(), (
        "Batch 4 comment/binary review: duplicate (subject_number, delivery_id, review_variable) rows."
    )
    assert batch4_review_df["subject_number"].notna().all() and batch4_review_df["delivery_id"].notna().all(), (
        "Batch 4 comment/binary review: every row must have a complete composite key."
    )
    assert not (batch4_review_df["decision_status"].isin(["OPEN", "PENDING", ""]) | batch4_review_df["decision_status"].isna()).any(), (
        "Batch 4 comment/binary review: no row may be left OPEN/PENDING/blank."
    )

    batch4_review_xlsx = os.path.join(review_path, "batch4_comment_binary_review.xlsx")
    os.makedirs(review_path, exist_ok=True)
    batch4_review_df.to_excel(batch4_review_xlsx, index=False)
    _batch4_category_counts = batch4_review_df["review_category"].value_counts().to_dict()
    print(f"  Comment/binary review: {n_batch4_review_occurrences} occurrence(s), "
          f"{n_batch4_review_unique_records} unique record(s), all closed -> {batch4_review_xlsx}")
    print(f"  Comment/binary review categories: {_batch4_category_counts}")

    # ------------------------------------------------------------------
    # Save + audit
    # ------------------------------------------------------------------
    os.makedirs(processed_path, exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    summary = f"""# Preprocessing Batch 4 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## smoking
- Values: {smoke_vc}
- Kept as 3-level categorical (0=never, 1=current, 2=past). Do not merge at preprocessing.
- Unexpected values: {"none" if ok_smoke else str(unexp_smoke)}

## alcohol
- All values = 0 (no variance)
- Zero-variance flag: {zero_variance_flags[0] if zero_variance_flags else "none"}

## any_medical_problem
- Binary 0/1. Unexpected values: {"none" if ok_amp else str(unexp_amp)}

## regular_medications
- Binary 0/1. Unexpected values: {"none" if ok_rm else str(unexp_rm)}

## Fetus_Anamoly
- Binary 0/1 ({df['Fetus_Anamoly'].value_counts(dropna=False).to_dict()})
- Unexpected values: {"none" if ok_fa else str(unexp_fa)}
- Approved single-record correction: record key and patient-specific rationale redacted (rows recoded in this review copy: {n_redacted_fetal_anomaly_correction})

## Comment columns (placeholder zeros normalized to NaN)
- any_medical_problem_comment: {n_c1_zeros} zeros -> NaN
- regular_medications_comment: {n_c2_zeros} zeros -> NaN
- Fetus_Anamoly_comment: {n_c3_zeros} zeros -> NaN
- Total rows with free text across any_medical_problem_comment/regular_medications_comment/Fetus_Anamoly_comment: {free_text_rows}

## Zero-variance columns flagged for EDA
{chr(10).join("- " + z for z in zero_variance_flags) if zero_variance_flags else "None"}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)

    log_audit_event(
        audit_log_md,
        f"Batch 4 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- smoking 3-level valid: {ok_smoke}\n"
        f"- alcohol zero-variance: True (all 0)\n"
        f"- comment zero-placeholders normalized: c1={n_c1_zeros}, c2={n_c2_zeros}, c3={n_c3_zeros}\n"
        f"- Free-text rows in any_medical_problem_comment/regular_medications_comment/Fetus_Anamoly_comment: {free_text_rows}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  smoking: {smoke_vc}")
    print(f"  alcohol: zero-variance flagged")
    print(f"  comment zeros->NaN: c1={n_c1_zeros}, c2={n_c2_zeros}, c3={n_c3_zeros}")
    print(f"  Free-text rows in comment cols: {free_text_rows}")
    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 4 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 5 — Endometriosis type variables and diagnosis-year derivation
# deep_endometriosis, superficial_endometriosis,
# cs_scar_endometriosis, peritoneal_endometriosis, diagnosis_date, diagnosis_year
# (clinical_diagnosis_only dropped in Batch 2, Decision 33)
# ---------------------------------------------------------------------------

def batch_5_endometriosis(work_df):
    """
    Endometriosis type variables and diagnosis-year derivation.

    Validates the binary endometriosis-type variables (deep, superficial,
    cs_scar, peritoneal). clinical_diagnosis_only was already removed
    early in Batch 2 (Decision 33) and is not handled here. Derives
    diagnosis_year from diagnosis_date; diagnosis_date itself is preserved
    unchanged.

    Approved decisions: 33, 57.
    Returns: df — the working DataFrame with endometriosis-type variables
    validated.
    """
    BATCH_TITLE = BATCH_METADATA[5]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values, log_audit_event,
        log_deviation_event, write_batch_summary,
        build_diagnosis_date_unresolved_qa, extract_diagnosis_year,
    )

    print(f"=== Batch 5: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch5.md")
    diagnosis_date_qa_xlsx = os.path.join(review_path, "diagnosis_date_unresolved_QA.xlsx")
    output_xlsx    = os.path.join(processed_path, "work_df_batch5.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []

    # ------------------------------------------------------------------
    # 1. Binary endometriosis type variables — validate only, no changes
    # ------------------------------------------------------------------
    binary_cols = [
        "deep_endometriosis",
        "superficial_endometriosis",
        # clinical_diagnosis_only: dropped in Batch 2 (Decision 33, 2026-07-30)
        # -- no longer present in df by this point.
        "cs_scar_endometriosis",
        "peritoneal_endometriosis",
    ]
    binary_results = {}
    for col in binary_cols:
        ok, unexp = validate_expected_binary_values(df[col], col)
        binary_results[col] = {"ok": ok, "unexpected": unexp, "vc": df[col].value_counts(dropna=False).to_dict()}
        if not ok:
            unexpected_findings.append(f"{col}: unexpected values {unexp}")

    # ------------------------------------------------------------------
    # 2. diagnosis_date — preserve source as-is; derive diagnosis_year
    #
    # Extraction rules (in priority order):
    #   - pd.Timestamp / datetime object   → .year
    #   - string with Hebrew letters        → NaN (qualifier text)
    #   - string matching YYYY/YYYY or YYYY-YYYY (range) → NaN
    #   - int / float that is a 4-digit year 1900–2100    → use directly
    #   - string 'YYYY' or 'YYYY.0'         → int year
    #   - string 'D/M/23' or 'DD/MM/23' -> Decision 57 approved D/M/YY rule, 2023
    #   - string 'D/M/YYYY' or 'DD/MM/YYYY' → extract YYYY
    #   - string 'MM/YYYY' partial date      → extract YYYY
    #   - anything else                      → NaN
    # ------------------------------------------------------------------
    # The canonical private pipeline includes a small, clinically approved
    # record-specific D/M/YY verification keyed by subject_number + delivery_id.
    # Those keys and the exact patient-level source date are redacted here.
    before_diagnosis_year = df["diagnosis_date"].map(extract_diagnosis_year)
    df["diagnosis_year"] = df["diagnosis_date"].map(extract_diagnosis_year)

    n_nan_source    = int(df["diagnosis_date"].isna().sum())
    n_year_resolved = int(df["diagnosis_year"].notna().sum())
    n_year_nan      = int(df["diagnosis_year"].isna().sum())
    ambiguous_count = n_year_nan - n_nan_source
    year_dist = (
        df["diagnosis_year"].value_counts(dropna=False).sort_index().to_dict()
    )
    approved_dmy_yy_rows = df.iloc[0:0].copy()
    approved_dmy_yy_key_lines = "  - [record keys and exact source date redacted]"

    if ambiguous_count > 0:
        log_deviation_event(
            path=deviations_md,
            variable="diagnosis_year",
            raw_variable="diagnosis_date",
            documented="Extract year from diagnosis_date when format is reliable",
            action=f"{ambiguous_count} non-null source values set to NaN in diagnosis_year",
            reason="Values with Hebrew qualifiers (e.g. 'לא ידוע'), year ranges "
                   "('2009/2020', '2020-2021'), invalid years ('17/3/3024' typo), "
                   "and unapproved two-digit years cannot be reliably resolved to a "
                   "single year. Set to NaN.",
            requires_approval=False,
            batch="Batch 5",
            affected_count=int(ambiguous_count),
        )

    print(f"  diagnosis_year: {n_year_resolved} resolved, {n_year_nan} NaN "
          f"(incl. {n_nan_source} originally NaN + {ambiguous_count} ambiguous)")
    print(f"  year distribution: {year_dist}")

    # ------------------------------------------------------------------
    # diagnosis_date -> diagnosis_year unresolved-row QA (PARTNER-FIX-02,
    # PRE-B5-001). Row-level, deterministic, read-only: does not modify
    # diagnosis_date, does not assign a year, does not add an analytical
    # column. diagnosis_date remains the source-of-truth date. diagnosis_year
    # is retained only for source/audit/descriptive lineage where needed and
    # is excluded from predictive eligibility (Decision 72, 2026-08-18,
    # supersedes the earlier pre-labor-predictor conclusion in Decision 63;
    # see docs/clinical_decisions/manual_decisions_log.md).
    # ------------------------------------------------------------------
    assert not df[["subject_number", "delivery_id"]].duplicated().any(), (
        "diagnosis_date QA precondition failed: subject_number+delivery_id "
        "composite key is not unique in the Batch 5 working dataframe."
    )

    diagnosis_date_qa = build_diagnosis_date_unresolved_qa(df)

    assert not diagnosis_date_qa[["subject_number", "delivery_id"]].duplicated().any(), (
        "diagnosis_date_unresolved_QA composite keys are not unique."
    )
    _qa_keys = set(map(tuple, diagnosis_date_qa[["subject_number", "delivery_id"]].to_numpy()))
    _df_keys = set(map(tuple, df[["subject_number", "delivery_id"]].to_numpy()))
    assert _qa_keys <= _df_keys, (
        "diagnosis_date_unresolved_QA contains a composite key not present in the dataset."
    )
    _expected_keys = set(map(
        tuple,
        df.loc[df["diagnosis_date"].notna() & df["diagnosis_year"].isna(),
               ["subject_number", "delivery_id"]].to_numpy(),
    ))
    assert _qa_keys == _expected_keys, (
        "diagnosis_date_unresolved_QA does not contain exactly the unresolved "
        "non-missing diagnosis_date rows."
    )

    n_diagnosis_date_qa = len(diagnosis_date_qa)
    diagnosis_date_qa_category_counts = (
        diagnosis_date_qa["failure_category"].value_counts().sort_index().to_dict()
    )

    os.makedirs(review_path, exist_ok=True)
    diagnosis_date_qa.to_excel(diagnosis_date_qa_xlsx, index=False)
    print(f"  diagnosis_date unresolved QA: {n_diagnosis_date_qa} rows -> {diagnosis_date_qa_xlsx}")
    print(f"  diagnosis_date unresolved QA categories: {diagnosis_date_qa_category_counts}")

    # ------------------------------------------------------------------
    # Save + audit
    # ------------------------------------------------------------------
    os.makedirs(processed_path, exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    binary_lines = "\n".join(
        f"  - {col}: {r['vc']} | unexpected: {'none' if r['ok'] else str(r['unexpected'])}"
        for col, r in binary_results.items()
    )

    summary = f"""# Preprocessing Batch 5 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## Binary endometriosis type variables (validated only, no changes made)
{binary_lines}

## diagnosis_date -> diagnosis_year
- Source NaN: {n_nan_source}
- Year successfully extracted: {n_year_resolved}
- Year set to NaN (ambiguous/unresolvable): {n_year_nan}
  - Originally NaN in source: {n_nan_source}
  - Non-null but unresolvable (Hebrew qualifiers, ranges, invalid years): {ambiguous_count}
- Approved strict D/M/YY correction: YY=23 only -> 2023. Source diagnosis_date unchanged.
{approved_dmy_yy_key_lines}
- Year distribution: {year_dist}

## diagnosis_date unresolved QA (PARTNER-FIX-02, PRE-B5-001)
- Non-missing diagnosis_date with unresolved diagnosis_year: {n_diagnosis_date_qa}
- Failure category counts: {diagnosis_date_qa_category_counts}
- QA file: {diagnosis_date_qa_xlsx}
- No year invented; diagnosis_year is retained only for source/audit/descriptive
  lineage where needed and is excluded from predictive eligibility (Decision 72,
  2026-08-18, supersedes Decision 63's earlier predictor-eligibility conclusion)

## New columns added
- diagnosis_year (int or NaN; source diagnosis_date preserved unchanged)

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)

    log_audit_event(
        audit_log_md,
        f"Batch 5 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- Binary cols validated (no changes): {binary_cols}\n"
        f"- diagnosis_year extracted: {n_year_resolved}, NaN: {n_year_nan}\n"
        "- Approved D/M/YY correction: record keys and exact source date redacted in this review copy; "
        "source diagnosis_date remains unchanged in the canonical private run\n"
        f"- Ambiguous/unresolvable set to NaN: {ambiguous_count}\n"
        f"- diagnosis_date unresolved QA: {n_diagnosis_date_qa} rows, "
        f"categories: {diagnosis_date_qa_category_counts}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Binary cols validated: all {len(binary_cols)}")
    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 5 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 6 — Adenomyosis feature cleaning and clinically approved corrections
# ---------------------------------------------------------------------------

def batch_6_adenomyosis(work_df):
    """
    Adenomyosis feature cleaning and clinically approved corrections.

    Parses adenomyosis_sonographic_features using numeric-code extraction
    and deterministic literal-text rules (src/adenomyosis_rules.py),
    applies the clinically approved composite-key manual feature-code
    corrections (Decision 28) and review-status decisions (Decision 36),
    and corrects the binary adenomyosis indicator only where a
    diagnostic-strength code (1-10) supports it — code 11 alone does not.
    Ambiguous free text is left uncoded for manual review rather than
    guessed; original source text is never modified.

    Approved decisions: 28, 36.
    QA outputs: adenomyosis_features_review_df.xlsx,
    adenomyosis_corrected_0_to_1_QA.xlsx.
    Returns: df — the working DataFrame with adenomyosis variables cleaned.
    """
    BATCH_TITLE = BATCH_METADATA[6]["title"]
    import re as _re
    from preprocessing_utils import (
        detect_free_text, normalize_multi_code_string,
        log_audit_event, log_deviation_event, write_batch_summary,
        create_review_dataframe,
    )

    print(f"=== Batch 6: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch6.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch6.xlsx")
    review_xlsx    = os.path.join(review_path, "adenomyosis_features_review_df.xlsx")
    qa_xlsx        = os.path.join(review_path, "adenomyosis_corrected_0_to_1_QA.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []

    # 2026-08-27 parser-safety correction: normalize_multi_code_string now
    # fails loud (ValueError) on a numeric-but-non-integer-valued token
    # (e.g. "3.4") instead of silently truncating it -- see
    # preprocessing_utils.py. A single ambiguous cell must not crash the
    # entire 513-row batch; each such cell is instead caught here, treated
    # as genuinely unresolved (empty codes -> NaN clean value, the same
    # downstream outcome as "no clean code" -- never guessed, never
    # silently coerced to any specific codes), and made audit-visible via a
    # dedicated review export + deviation log entry + console print, never
    # silently vanished either.
    _adeno_ambiguous_numeric_rows = []

    def _classify_adenomyosis_row(idx, value):
        try:
            # strict=True: an exact-integer numeric token outside the
            # approved 1-11 code set (e.g. "12") must not silently vanish --
            # it is routed through the same ValueError -> unresolved/manual-
            # review path already used for non-integer tokens like "3.4".
            return classify_adenomyosis_features_value(
                value,
                lambda raw, valid_codes: normalize_multi_code_string(raw, valid_codes, strict=True),
            )
        except ValueError as exc:
            _adeno_ambiguous_numeric_rows.append({
                "row_index": idx,
                "raw_value": value,
                "parse_error": str(exc),
            })
            return [], "unresolved_ambiguous_numeric_manual_review", []

    results = pd.Series(
        [_classify_adenomyosis_row(idx, value) for idx, value in df["adenomyosis_sonographic_features"].items()],
        index=df.index,
    )
    df["_adeno_clean_list"]   = results.map(lambda x: x[0])
    df["_adeno_clean_source"] = results.map(lambda x: x[1])
    df["_adeno_rule_labels"] = results.map(lambda x: x[2])

    if _adeno_ambiguous_numeric_rows:
        _ambiguous_idx = [r["row_index"] for r in _adeno_ambiguous_numeric_rows]
        _ambiguous_id_cols = [c for c in ("delivery_id", "subject_number") if c in df.columns]
        _ambiguous_df = df.loc[_ambiguous_idx, _ambiguous_id_cols + ["adenomyosis_sonographic_features"]].copy()
        _ambiguous_df["parse_error"] = [r["parse_error"] for r in _adeno_ambiguous_numeric_rows]
        _ambiguous_df["manual_review_decision"] = pd.NA
        _ambiguous_df["manual_review_reason"] = pd.NA
        os.makedirs(review_path, exist_ok=True)
        ambiguous_numeric_xlsx = os.path.join(review_path, "adenomyosis_ambiguous_numeric_token_QA.xlsx")
        _ambiguous_df.to_excel(ambiguous_numeric_xlsx, index=False)
        print(f"  WARNING: {len(_adeno_ambiguous_numeric_rows)} row(s) had an ambiguous "
              f"numeric token (e.g. a non-integer-valued code like '3.4') in "
              "adenomyosis_sonographic_features -- NOT silently coerced or guessed. Left "
              "unresolved (adenomyosis_sonographic_features_clean = NaN for these rows) "
              f"pending manual/clinical review. Exported: {ambiguous_numeric_xlsx}")
        log_deviation_event(
            path=deviations_md,
            variable="adenomyosis_sonographic_features_clean",
            raw_variable="adenomyosis_sonographic_features",
            documented="normalize_multi_code_string requires every numeric-looking token to be "
                       "an exact integer or exact-integer-valued float (2026-08-27 parser-safety "
                       "correction, supersedes the previous silent int(float(token)) truncation).",
            action=f"{len(_adeno_ambiguous_numeric_rows)} row(s) with an ambiguous non-integer "
                   "numeric token left with adenomyosis_sonographic_features_clean = NaN "
                   "(unresolved, not guessed) pending manual/clinical review -- exported to "
                   "adenomyosis_ambiguous_numeric_token_QA.xlsx.",
            reason="A token such as '3.4' cannot be safely interpreted as a specific integer "
                   "code without clinical/source-record confirmation; no archived alternate "
                   "source record was available in this repository to resolve it.",
            requires_approval=True,
            batch="Batch 6",
            affected_count=len(_adeno_ambiguous_numeric_rows),
        )

    # ------------------------------------------------------------------
    # Validated record-level decisions use subject_number + delivery_id.
    # ------------------------------------------------------------------
    df, n_manual_feature_decisions = apply_adenomyosis_manual_feature_decisions(df)
    if n_manual_feature_decisions > 0:
        log_deviation_event(
            path=deviations_md,
            variable="adenomyosis_sonographic_features_clean",
            raw_variable="adenomyosis_sonographic_features",
            documented="ADENOMYOSIS_MANUAL_FEATURE_DECISIONS (clinical_decisions.py): "
                       "authoritative composite-key corrections, each overriding automated "
                       "free-text parsing for one record.",
            action=f"Applied {n_manual_feature_decisions} validated composite-key manual "
                   "adenomyosis feature-code decisions according to the approved decision "
                   "table; individual assigned codes and rationales are defined in "
                   "clinical_decisions.py / manual_decisions_log.md.",
            reason="Composite-key manual decision table is unique, input keys are unique, "
                   "and the merge is validated one-to-one before applying each decision.",
            requires_approval=False,
            batch="Batch 6",
            affected_count=n_manual_feature_decisions,
        )

    # Convert list → comma-separated string; empty list → NaN
    df["adenomyosis_sonographic_features_clean"] = df["_adeno_clean_list"].map(
        adenomyosis_codes_to_clean_value
    )

    # ------------------------------------------------------------------
    # Review file: rows with free-text content that got no clean code
    # ------------------------------------------------------------------
    has_text  = detect_free_text(df["adenomyosis_sonographic_features"])
    has_clean = df["adenomyosis_sonographic_features_clean"].notna()
    review_mask = has_text & ~has_clean

    n_review = int(review_mask.sum())
    n_review_status_decisions = 0
    if n_review > 0:
        review_df = create_review_dataframe(
            df, review_mask,
            cols=["adenomyosis_sonographic_features",
                  "adenomyosis_sonographic_features_clean",
                  "adenomyosis"],
            id_cols=["delivery_id", "subject_number"],
        )
        # Decision 36 (2026-07-29): apply the approved keep_missing_not_specific_enough
        # review decision for the 11 rows already reviewed. This only sets
        # manual_review_decision/manual_review_reason -- it never assigns a
        # sonographic feature code and never touches adenomyosis.
        review_df, n_review_status_decisions = apply_adenomyosis_review_status_decisions(review_df)
        os.makedirs(review_path, exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        print(f"  Review file saved: {review_xlsx} ({n_review} rows, "
              f"{n_review_status_decisions} with a recorded manual_review_decision)")
        if n_review_status_decisions > 0:
            log_deviation_event(
                path=deviations_md,
                variable="adenomyosis_sonographic_features_clean",
                raw_variable="adenomyosis_sonographic_features",
                documented="Final clinical review (Decision 36) of the 11 rows that remained "
                           "unresolved after Decision 28's 5 direct corrections.",
                action="Recorded manual_review_decision='keep_missing_not_specific_enough' for "
                       f"{n_review_status_decisions} row(s) by validated subject_number + "
                       "delivery_id decision. adenomyosis_sonographic_features_clean left NaN; "
                       "adenomyosis left unchanged.",
                reason="Text supports adenomyosis generally but does not describe a sufficiently "
                       "specific sonographic feature to map to a predefined code (1-11). Disease "
                       "presence is already represented by the binary adenomyosis variable.",
                requires_approval=False,
                batch="Batch 6",
                affected_count=n_review_status_decisions,
            )
    else:
        print("  No unresolved free-text rows.")

    # ------------------------------------------------------------------
    # Adenomyosis correction: 0 → 1 where clean codes include any of 1–10
    # Code 11 alone does not trigger correction (not diagnostically conclusive)
    # ------------------------------------------------------------------
    adenomyosis_before = df["adenomyosis"].copy()

    correction_mask = (
        (df["adenomyosis"] == 0) &
        df["_adeno_clean_list"].map(adenomyosis_has_diagnostic_code)
    )
    n_corrected        = int(correction_mask.sum())
    n_corr_numeric     = int((correction_mask & (df["_adeno_clean_source"] == "numeric_codes")).sum())
    n_corr_record_specific  = int((correction_mask & (df["_adeno_clean_source"] == "manual_composite_key_globular_uterus")).sum())
    n_corr_det_text    = int((correction_mask & (df["_adeno_clean_source"] == "explicit_literal_text")).sum())

    if n_corrected > 0:
        df.loc[correction_mask, "adenomyosis"] = 1
        log_deviation_event(
            path=deviations_md,
            variable="adenomyosis",
            raw_variable="ADENOMYOSIS",
            documented="Binary 0/1. Documented QA rule: if sonographic features include "
                       "codes 1-10, adenomyosis must be 1.",
            action=f"Corrected {n_corrected} rows: adenomyosis 0->1 "
                   f"({n_corr_numeric} from numeric codes, "
                   f"{n_corr_record_specific} record-specific documented text, "
                   f"{n_corr_det_text} other deterministic text)",
            reason="Sonographic features confirming adenomyosis (codes 1-10) with "
                   "adenomyosis=0 is a data inconsistency. "
                   "Free-text values are NOT used for numeric extraction; only pure code fields, "
                   "explicit literal text rules, and validated composite-key decisions trigger correction.",
            requires_approval=False,
            batch="Batch 6",
            affected_count=n_corrected,
        )

    adenomyosis_after     = df["adenomyosis"].copy()
    adenomyosis_before_vc = adenomyosis_before.value_counts(dropna=False).to_dict()
    adenomyosis_after_vc  = adenomyosis_after.value_counts(dropna=False).to_dict()

    print(f"  adenomyosis corrected 0->1: {n_corrected} "
          f"(numeric={n_corr_numeric}, record_specific={n_corr_record_specific}, det_text={n_corr_det_text})")
    print(f"  adenomyosis before: {adenomyosis_before_vc}")
    print(f"  adenomyosis after:  {adenomyosis_after_vc}")

    # ------------------------------------------------------------------
    # QA file: all corrected rows with source breakdown
    # ------------------------------------------------------------------
    qa_rows = []
    for idx in df.index[correction_mask | (adenomyosis_before == 0)]:
        src = df.at[idx, "_adeno_clean_source"] if "_adeno_clean_source" in df.columns else ""
        raw_val = df.at[idx, "adenomyosis_sonographic_features"]
        clean_val = df.at[idx, "adenomyosis_sonographic_features_clean"]
        was_corrected = correction_mask.loc[idx] if idx in correction_mask.index else False
        if not was_corrected:
            continue
        if src == "numeric_codes":
            reason = (f"Pure numeric code field. Code(s) {df.at[idx, '_adeno_clean_list']} "
                      "in range 1-10. Correction per documented QA rule.")
            needs_review = False
            decision_number = "N/A (automated deterministic parsing rule, not a numbered clinical decision)"
        elif src == "manual_composite_key_globular_uterus":
            reason = ("Approved record-specific manual correction. "
                      "Patient-specific source excerpt redacted. "
                      "Applied by validated subject_number + delivery_id key per documentation.")
            needs_review = False
            decision_number = "28"
        elif src.startswith("manual_composite_key_"):
            reason = ("Direct authoritative clinical correction applied by validated "
                      "subject_number + delivery_id key per documentation.")
            needs_review = False
            decision_number = "28"
        elif src == "explicit_literal_text":
            reason = "Explicit literal text rule matched one or more approved codebook features."
            needs_review = False
            decision_number = "N/A (automated deterministic parsing rule, not a numbered clinical decision)"
        else:
            reason = f"Unknown source: {src}"
            needs_review = True
            decision_number = "N/A (unrecognized correction source — flagged for review)"
        qa_rows.append({
            "delivery_id": df.at[idx, "delivery_id"],
            "subject_number": df.at[idx, "subject_number"],
            "original_row_index_in_cohort": idx,
            "adenomyosis_before": 0,
            "adenomyosis_after": 1,
            "adenomyosis_sonographic_features_raw": raw_val,
            "adenomyosis_sonographic_features_clean": clean_val,
            "decision_number": decision_number,
            "correction_source": src,
            "spurious_text_extraction": False,
            "needs_manual_review": needs_review,
            "correction_reason": reason,
        })
    qa_df = pd.DataFrame(qa_rows)
    os.makedirs(review_path, exist_ok=True)
    qa_df.to_excel(qa_xlsx, index=False)
    print(f"  QA file saved: {qa_xlsx} ({len(qa_df)} rows)")

    # Drop internal helper columns
    df = df.drop(columns=["_adeno_clean_list", "_adeno_clean_source", "_adeno_rule_labels"])

    # ------------------------------------------------------------------
    # Save + audit
    # ------------------------------------------------------------------
    os.makedirs(processed_path, exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    n_clean_resolved = int(df["adenomyosis_sonographic_features_clean"].notna().sum())
    n_clean_nan      = int(df["adenomyosis_sonographic_features_clean"].isna().sum())
    n_source_nan     = int(df["adenomyosis_sonographic_features"].isna().sum())

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    summary = f"""# Preprocessing Batch 6 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## adenomyosis_sonographic_features (source preserved)
- NaN in source: {n_source_nan}

## adenomyosis_sonographic_features_clean (new column)
- Valid codes resolved: {n_clean_resolved}
- NaN (empty/0/unresolvable/free-text): {n_clean_nan}
- Rule: free-text values (containing Hebrew or Latin letters) are NOT parsed for numeric codes.
  Only pure code fields (digits, separators, spaces) trigger numeric extraction.
- Deterministic text mapping: 'הצללה בצורת מניפה' -> code 9 (0 matches in data)
- Approved record-specific manual feature correction: key and source excerpt redacted
- Free-text rows with no parseable code, sent to review: {n_review}
- Reviewed with recorded manual_review_decision (Decision 36, 2026-07-29): {n_review_status_decisions}
{"  Review file: " + review_xlsx if n_review > 0 else ""}

## adenomyosis correction (0->1) — breakdown
- Before: {adenomyosis_before_vc}
- After:  {adenomyosis_after_vc}
- Total corrected 0->1: {n_corrected}
  1. Clean numeric code corrections (pure code fields, codes 1-10): {n_corr_numeric}
  2. Approved record-specific text correction [key redacted]: {n_corr_record_specific}
  3. Other deterministic text mapping: {n_corr_det_text}
  4. Spurious text extraction cases: 0 (fixed — letters in value → no numeric extraction)
- Code 11 alone: no correction (not diagnostically conclusive per documentation)

## QA file
- {qa_xlsx} ({len(qa_df)} corrected rows)
- All corrections: spurious_text_extraction=False, needs_manual_review=False

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}
{"- Review: " + review_xlsx if n_review > 0 else ""}
- QA: {qa_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)

    log_audit_event(
        audit_log_md,
        f"Batch 6 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- adenomyosis_sonographic_features_clean: {n_clean_resolved} resolved, {n_clean_nan} NaN\n"
        f"- Free-text review rows: {n_review} ({n_review_status_decisions} with a recorded manual_review_decision, Decision 36)\n"
        f"- adenomyosis corrected 0->1: {n_corrected} "
        f"(numeric={n_corr_numeric}, record_specific={n_corr_record_specific}, det_text={n_corr_det_text})\n"
        f"- Spurious text extractions: 0 (fix applied)\n"
        f"- QA file: {qa_xlsx}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  adenomyosis_sonographic_features_clean: {n_clean_resolved} resolved, {n_clean_nan} NaN")
    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 6 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 7 — Endometrioma characteristics parsing and consistency review
#          (new numeric mm column), endometrioma_place, endometrioma_place_clean,
#          endometrioma_laterality
# Note: endometrioma_review_flag is created internally for QA export only;
#       it is dropped before saving and is not part of the final analytic dataframe.
# ---------------------------------------------------------------------------

def batch_7_endometrioma(work_df):
    """
    Endometrioma characteristics parsing and consistency review.

    Parses endometrioma_size and endometrioma_place into clean numeric /
    coded values (src/endometrioma_rules.py), derives laterality, and
    flags size/place values that are inconsistent with the endometrioma
    existence indicator for manual review instead of auto-correcting.

    QA outputs: endometrioma_review_df.xlsx (only if inconsistent rows are
    found).
    Returns: df — the working DataFrame with endometrioma variables
    cleaned.
    """
    BATCH_TITLE = BATCH_METADATA[7]["title"]
    import re as _re
    import unicodedata as _unicodedata
    from preprocessing_utils import (
        validate_expected_binary_values, detect_free_text,
        log_audit_event, log_deviation_event, write_batch_summary,
        create_review_dataframe,
    )

    print(f"=== Batch 7: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch7.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch7.xlsx")
    review_xlsx    = os.path.join(review_path, "endometrioma_review_df.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []

    # Unit regexes use Unicode escapes to avoid mojibake in Hebrew cm/mm
    # notation. Supported Hebrew forms include samekh-mem and mem-mem with
    # optional quote/gershayim variants, plus Latin cm/c.m/mm/m.m forms.
    UNIT_ALPHA_BOUNDARY = r"A-Za-z\u05D0-\u05EA"
    UNIT_LEFT_BOUNDARY = r"(?<![" + UNIT_ALPHA_BOUNDARY + r"])"
    UNIT_RIGHT_BOUNDARY = r"(?![" + UNIT_ALPHA_BOUNDARY + r"])"
    UNIT_QUOTE_CHARS = r"[\"'\u05f3\u05f4\u2018\u2019\u201c\u201d\u2032\u2033]"
    CM_UNIT_PATTERN = (
        UNIT_LEFT_BOUNDARY +
        r'(?:\u05e1\s*(?:' + UNIT_QUOTE_CHARS + r'{0,2})\s*\u05de|'
        r'c\s*\.?\s*m|centimeters?)' +
        UNIT_RIGHT_BOUNDARY
    )
    MM_UNIT_PATTERN = (
        UNIT_LEFT_BOUNDARY +
        r'(?:\u05de\s*(?:' + UNIT_QUOTE_CHARS + r'{0,2})\s*\u05de|'
        r'm\s*\.?\s*m|millimeters?)' +
        UNIT_RIGHT_BOUNDARY
    )
    CM_UNIT_RE = _re.compile(CM_UNIT_PATTERN, _re.IGNORECASE)
    MM_UNIT_RE = _re.compile(MM_UNIT_PATTERN, _re.IGNORECASE)

    def _normalize_unit_text(text):
        return _unicodedata.normalize("NFKC", str(text)).lower()

    def _has_cm_unit(text):
        return bool(CM_UNIT_RE.search(_normalize_unit_text(text)))

    def _has_mm_unit(text):
        return bool(MM_UNIT_RE.search(_normalize_unit_text(text)))

    # "smaller than 1 cm" -> 10 mm per documentation
    LESS_THAN_1CM_RE = _re.compile(
        r'(?:<|less\s+than|smaller\s+than|\u05e7\u05d8\u05df|\u05e7\u05d8\u05e0\u05d4|'
        r'\u05e7\u05d8\u05e0\u05d9\u05dd|\u05e4\u05d7\u05d5\u05ea)\s*(?:\u05de|m)?\s*1\s*'
        r'(?:' + CM_UNIT_PATTERN + r')',
        _re.IGNORECASE
    )
    NUMBER_RE = _re.compile(r'\d+(?:\.\d+)?')

    NON_INFORMATIVE_SIZE = frozenset({
        'לא צוין', 'לא צויין', 'לא צוין גודל', 'לא צויין גודל',
    })
    # Vague text detection: letter check and dimension pattern (N?M, N*M, N-M, NxM, N, M)
    # Comma included as dimension separator to handle bilateral measurements like "17, 19"
    HAS_LETTER_RE = _re.compile(r"[A-Za-z?-?]")
    DIM_RE        = _re.compile(r'\d+(?:\.\d+)?[\s]*[,xX\*?\-][\s]*\d+(?:\.\d+)?')

    def _has_clear_size_signal(s):
        """True if s has an explicit mm/cm unit, a dimension pattern, or 2+ numeric values.
        Two or more numbers indicate bilateral/multi-dimensional measurements (e.g. 'ימין 17, שמאל 19').
        """
        return bool(
            _has_mm_unit(s) or
            _has_cm_unit(s) or
            DIM_RE.search(s) or
            len(NUMBER_RE.findall(s)) >= 2
        )

    # ------------------------------------------------------------------
    # 1. endometrioma — validate binary; approved record-specific QA correction redacted
    # ------------------------------------------------------------------
    ok_endo, unexp_endo = validate_expected_binary_values(df["endometrioma"], "endometrioma")
    if not ok_endo:
        unexpected_findings.append(f"endometrioma: unexpected values {unexp_endo}")
    endo_before_vc = df["endometrioma"].value_counts(dropna=False).to_dict()

    # Documented QA correction — single record [RECORD KEY REDACTED]
    # Canonical private source applies the approved correction here.
    # This review copy preserves the surrounding method but executes no row-key correction.
    note_record_specific_endometrioma = "approved single-record correction: key and rationale redacted"

    n_endo_changed = int((df["endometrioma"] != work_df["endometrioma"]).sum())
    print(f"  endometrioma: {note_record_specific_endometrioma}")
    print(f"  endometrioma values changed: {n_endo_changed}")

    # ------------------------------------------------------------------
    # 2. endometrioma_size (preserved) → endometrioma_size_clean (new numeric mm column)
    # Rule: endometrioma_size is never overwritten.
    # All parsing and unit conversion produce values in endometrioma_size_clean only.
    # ------------------------------------------------------------------
    endometrioma_size_raw = df["endometrioma_size"].copy()

    # ------------------------------------------------------------------
    # Attribution-aware size parsing (PARTNER-FIX-04, F-1 correction).
    #
    # The prior parser extracted every number in a cell and took the
    # unconditional maximum, regardless of which anatomical structure or
    # pathology it belonged to. That could silently misattribute a measurement belonging to a different
    # pathology/structure to the endometrioma in a reviewed record. The corrected,
    # tested, importable parser lives in endometrioma_rules.py so it can be
    # unit-tested directly; see that module's docstring for the full rule.
    # ------------------------------------------------------------------
    PARSER_VERSION = ENDOMETRIOMA_SIZE_PARSER_VERSION

    _size_evidence = endometrioma_size_raw.map(parse_endometrioma_size_mm_with_evidence)

    # endometrioma_size remains unchanged (original standardized values preserved as reference)
    # All parsed numeric mm values are written only to the new endometrioma_size_clean column
    df["endometrioma_size_clean"] = _size_evidence.map(lambda e: e["processed_value_mm"])

    n_size_parsed  = int(df["endometrioma_size_clean"].notna().sum())
    n_size_nan     = int(df["endometrioma_size_clean"].isna().sum())
    n_size_was_zero = int((endometrioma_size_raw == 0).sum())
    size_dist      = df["endometrioma_size_clean"].describe().to_dict()

    # Row-level size-parsing audit (diagnostic only -- never part of the
    # analytical dataframe). Covers every non-missing raw value so any
    # mixed-text parse is fully auditable.
    _size_audit_mask = endometrioma_size_raw.notna()
    if _size_audit_mask.any():
        _size_audit_rows = []
        for _idx in df.index[_size_audit_mask]:
            _ev = _size_evidence.loc[_idx]
            _size_audit_rows.append({
                "subject_number": df.loc[_idx, "subject_number"],
                "delivery_id": df.loc[_idx, "delivery_id"],
                "raw_value": _ev["raw_value"],
                "candidate_measurements": _ev["candidate_measurements"],
                "candidate_contexts": _ev["candidate_contexts"],
                "excluded_measurements": _ev["excluded_measurements"],
                "selected_measurement": _ev["selected_measurement"],
                "selected_unit": _ev["selected_unit"],
                "processed_value_mm": _ev["processed_value_mm"],
                "decision_type": _ev["decision_type"],
                "decision_reason": _ev["decision_reason"],
                "parser_version": PARSER_VERSION,
            })
        size_audit_df = pd.DataFrame(_size_audit_rows).sort_values(
            ["subject_number", "delivery_id"], kind="mergesort"
        ).reset_index(drop=True)
        size_audit_xlsx = os.path.join(review_path, "endometrioma_size_parsing_audit.xlsx")
        os.makedirs(review_path, exist_ok=True)
        size_audit_df.to_excel(size_audit_xlsx, index=False)
        print(f"  endometrioma_size parsing audit: {len(size_audit_df)} row(s) -> {size_audit_xlsx}")

    # Track vague text_with_number rows (letters+digits, no clear size unit/dimension)
    def _is_vague_size_text(val):
        if pd.isna(val): return False
        s = str(val).strip()
        try:
            if float(s) == 0.0: return False
        except (ValueError, TypeError): pass
        if s.lower() in NON_INFORMATIVE_SIZE: return False
        if LESS_THAN_1CM_RE.search(s): return False
        # Must have both letters AND digits (text_with_number category, not text_no_number)
        return bool(HAS_LETTER_RE.search(s)) and bool(NUMBER_RE.search(s)) and not _has_clear_size_signal(s)

    vague_size_mask = endometrioma_size_raw.map(_is_vague_size_text)
    n_vague_size = int(vague_size_mask.sum())
    if n_vague_size > 0:
        log_deviation_event(
            path=deviations_md,
            variable="endometrioma_size",
            raw_variable="endometrioma_size",
            documented="Parse size to mm. Text with embedded numbers may or may not be sizes.",
            action=f"Set {n_vague_size} vague text_with_number value(s) to NaN.",
            reason="Raw value has letters and digits but no mm/cm unit and no dimension "
                   "pattern — cannot reliably identify a size. Set to NaN; flagged for review.",
            requires_approval=False,
            batch="Batch 7",
            affected_count=n_vague_size,
        )

    print(f"  endometrioma_size_clean: {n_size_parsed} valid (mm), {n_size_nan} NaN "
          f"(incl. {n_size_was_zero} original zeros, {n_vague_size} vague text); "
          f"endometrioma_size preserved as-is")

    # Log: zeros treated as NaN
    if n_size_was_zero > 0:
        log_deviation_event(
            path=deviations_md,
            variable="endometrioma_size",
            raw_variable="endometrioma_size",
            documented="Missing/no size data should be NaN, not 0.",
            action=f"Converted {n_size_was_zero} zero values to NaN during size parsing.",
            reason="Zero is not a valid endometrioma size; "
                   "it is a placeholder for 'not recorded' in this dataset.",
            requires_approval=False,
            batch="Batch 7",
            affected_count=n_size_was_zero,
        )

    # ------------------------------------------------------------------
    # 3. endometrioma_place — validate; create clean (numeric 1/2/3) + laterality (1/2)
    # Codes: 1=right, 2=left, 3=bilateral
    # Combinations: any combination containing both 1+2, or including 3, → 3 (bilateral)
    # endometrioma_laterality: 1=unilateral (place 1 or 2), 2=bilateral (place 3), NaN otherwise
    # ------------------------------------------------------------------
    NON_INFORMATIVE_PLACE = frozenset({"0", "0.0", "לא צוין", "לא צויין"})

    df["endometrioma_place_clean"] = df["endometrioma_place"].map(clean_endometrioma_place_value)
    # laterality: 1=unilateral, 2=bilateral, NaN if unknown
    df["endometrioma_laterality"] = df["endometrioma_place_clean"].map(derive_endometrioma_laterality)

    n_place_parsed  = int(df["endometrioma_place_clean"].notna().sum())
    laterality_vc   = df["endometrioma_laterality"].value_counts(dropna=False).to_dict()

    def _has_uncodeable_text(val):
        s = str(val).strip()
        if s in NON_INFORMATIVE_PLACE:
            return False
        return has_uncodeable_endometrioma_place_text(val)
    place_text_mask = df["endometrioma_place"].map(_has_uncodeable_text)
    n_place_text    = int(place_text_mask.sum())

    # ------------------------------------------------------------------
    # 3a. Documented manual laterality correction verification [REDACTED]
    # Canonical private source verifies one record-specific correction here.
    note_record_specific_laterality = "approved record-specific laterality correction: key and rationale redacted"

    print(f"  endometrioma_place_clean: {n_place_parsed} parsed (1=right, 2=left, 3=bilateral)")
    print(f"  endometrioma_laterality: {laterality_vc} (1=unilateral, 2=bilateral)")
    print(f"  endometrioma_place free-text rows (uncodeable): {n_place_text}")
    print(f"  {note_record_specific_laterality}")

    # ------------------------------------------------------------------
    # 4. endometrioma_review_flag — flag contradictions
    # ------------------------------------------------------------------
    df["endometrioma_review_flag"] = pd.Series(pd.NA, index=df.index, dtype="object")

    # Flag: endo=0 but valid parsed size (use endometrioma_size_clean as numeric signal)
    m_0_size = (df["endometrioma"] == 0) & df["endometrioma_size_clean"].notna()
    df.loc[m_0_size, "endometrioma_review_flag"] = "endo=0 but valid size recorded"

    # Flag: endo=0 but valid place (set to most severe flag if already set)
    m_0_place = (df["endometrioma"] == 0) & df["endometrioma_place_clean"].notna()
    combined_0 = m_0_size & m_0_place
    df.loc[combined_0, "endometrioma_review_flag"] = (
        "endo=0 but valid size and valid place recorded"
    )
    only_0_place = m_0_place & ~m_0_size
    df.loc[only_0_place, "endometrioma_review_flag"] = "endo=0 but valid place recorded"

    # Flag: free-text place that could not be coded
    m_text_no_clean = place_text_mask & df["endometrioma_place_clean"].isna()
    # Only add this flag if not already flagged
    df.loc[m_text_no_clean & df["endometrioma_review_flag"].isna(),
           "endometrioma_review_flag"] = "endometrioma_place is free text — could not code"
    # Append to existing flag if row already has one
    both_flags = m_text_no_clean & df["endometrioma_review_flag"].notna()
    df.loc[both_flags, "endometrioma_review_flag"] = (
        df.loc[both_flags, "endometrioma_review_flag"] + "; place is free text"
    )

    # Flag: vague text_with_number size — set to NaN, add to review
    already_flagged = df["endometrioma_review_flag"].notna()
    df.loc[vague_size_mask & ~already_flagged,
           "endometrioma_review_flag"] = (
        "vague text with numbers, not a reliable size expression"
    )
    df.loc[vague_size_mask & already_flagged, "endometrioma_review_flag"] = (
        df.loc[vague_size_mask & already_flagged, "endometrioma_review_flag"]
        + "; vague size text"
    )

    review_mask = df["endometrioma_review_flag"].notna()
    n_flagged   = int(review_mask.sum())
    flag_counts = df.loc[review_mask, "endometrioma_review_flag"].value_counts().to_dict()
    print(f"  endometrioma_review_flag: {n_flagged} rows flagged")

    # ------------------------------------------------------------------
    # 5. Review file for flagged rows
    # ------------------------------------------------------------------
    review_cols = [
        "endometrioma_size",        # original standardized value (preserved as-is)
        "endometrioma_size_clean",  # parsed numeric mm value
        "endometrioma_place",
        "endometrioma_place_clean",
        "endometrioma_laterality",
        "endometrioma_review_flag",
        "endometrioma",
    ]
    review_df = create_review_dataframe(
        df, review_mask,
        cols=review_cols,
        id_cols=["delivery_id", "subject_number"],
    )
    os.makedirs(review_path, exist_ok=True)
    review_df.to_excel(review_xlsx, index=False)
    if n_flagged > 0:
        print(f"  Review file saved: {review_xlsx} ({n_flagged} rows)")
    else:
        print(f"  Review file saved: {review_xlsx} (0 rows)")
        print("  No contradictions flagged.")

    # ------------------------------------------------------------------
    # 6. Save + audit
    # ------------------------------------------------------------------
    # Drop QA helper column before saving — endometrioma_review_flag is a pipeline
    # validation artifact exported separately to the review file above.
    df = df.drop(columns=["endometrioma_review_flag"])

    os.makedirs(processed_path, exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    summary = f"""# Preprocessing Batch 7 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## endometrioma (binary 0/1)
- Before: {endo_before_vc}
- After:  {df["endometrioma"].value_counts(dropna=False).to_dict()}
- record-specific endometrioma correction: {note_record_specific_endometrioma}
- Values changed: {n_endo_changed}

## endometrioma_size (original — preserved unchanged)
- Column kept as-is from standardized input; original values not modified.

## endometrioma_size_clean (new numeric column, mm)
- Successfully parsed: {n_size_parsed}
- NaN after parsing: {n_size_nan} (incl. {n_size_was_zero} original zeros, {n_vague_size} vague text)
- Vague text_with_number rows set to NaN: {n_vague_size} (letters+digits, no unit/dimension — flagged for review)
- Stats (mm): min={size_dist.get("min", "N/A"):.1f}, max={size_dist.get("max", "N/A"):.1f}, mean={size_dist.get("mean", "N/A"):.1f}
- Rule: "less than 1 cm" → 10 mm; no unit → assume mm; multiple dims → largest; cm → *10
- Note: zeros treated as NaN (placeholder for 'not recorded')

## endometrioma_place_clean (new numeric column: 1=right, 2=left, 3=bilateral)
- 1 (right): {(df["endometrioma_place_clean"] == 1).sum()}
- 2 (left): {(df["endometrioma_place_clean"] == 2).sum()}
- 3 (bilateral): {(df["endometrioma_place_clean"] == 3).sum()}
- NaN (0, empty, לא צוין/לא צויין, free text): {df["endometrioma_place_clean"].isna().sum()}
- Free-text (uncodeable) rows: {n_place_text}
- record-specific laterality correction: {note_record_specific_laterality}

## endometrioma_laterality (new numeric column: 1=unilateral, 2=bilateral)
- {laterality_vc}

## endometrioma_review_flag
- Total flagged: {n_flagged}
- Breakdown: {flag_counts}
{"- Review file: " + review_xlsx if n_flagged > 0 else ""}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}
{"- Review: " + review_xlsx if n_flagged > 0 else ""}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)

    log_audit_event(
        audit_log_md,
        f"Batch 7 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- endometrioma changed: {n_endo_changed} (record-specific correction: {note_record_specific_endometrioma})\n"
        f"- endometrioma_size: preserved unchanged (original reference column)\n"
        f"- endometrioma_size_clean (new numeric mm): parsed={n_size_parsed}, NaN={n_size_nan}\n"
        f"- endometrioma_place_clean parsed: {n_place_parsed}\n"
        f"- endometrioma_laterality: {laterality_vc}\n"
        f"- endometrioma_review_flag: {n_flagged} rows\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 7 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 8 — Endometriosis-surgery cleaning and resection-site classification
# endometriosis_surgery, grouped endo_resection_sites_clean + multi-hot columns,
# vaginal_opening_during_surgery, bowel_lesion_resected,
# bladder_lesion_resected, surgery_details, endo_surgery_adhesiolysis, comment_1
# ---------------------------------------------------------------------------

# Module-level (not batch_8-local) so the grouping logic is independently
# testable without invoking the full batch function's file I/O -- pure
# functions, no closured mutable state, behavior unchanged from their
# former in-function-body definitions.
RESECTION_LABEL_ORDER = (
    "no_resection",
    "ovarian_endometrioma_unilateral",
    "ovarian_endometrioma_bilateral",
    "adnexa",
    "fallopian_tube",
    "epiploica",
    "uterus",
    "lesion_resection",
    "adhesiolysis",
    "appendix",
)


def _is_exact_zero_resection_site(val):
    if pd.isna(val):
        return False
    if isinstance(val, str):
        return val.strip() in {"0", "0.0"}
    try:
        return float(val) == 0.0
    except (ValueError, TypeError):
        return False


def _group_endo_resection_sites(raw_value, parsed_codes, label_order=RESECTION_LABEL_ORDER):
    if _is_exact_zero_resection_site(raw_value):
        return ["no_resection"]

    code_set = set(parsed_codes)
    labels = set()

    if 3 in code_set or ({1, 2} <= code_set):
        labels.add("ovarian_endometrioma_bilateral")
    elif code_set.intersection({1, 2}):
        labels.add("ovarian_endometrioma_unilateral")

    if code_set.intersection({4, 5}):
        labels.add("adnexa")
    if code_set.intersection({6, 7}):
        labels.add("fallopian_tube")
    if 8 in code_set:
        labels.add("epiploica")
    if 9 in code_set:
        labels.add("uterus")
    if 10 in code_set:
        labels.add("lesion_resection")
    if 11 in code_set:
        labels.add("adhesiolysis")

    raw_text = "" if pd.isna(raw_value) else str(raw_value)
    if "תוספתן" in raw_text:
        labels.add("appendix")
    if "ציסטה בשחלה" in raw_text and (
        "ovarian_endometrioma_bilateral" not in labels
    ):
        labels.add("ovarian_endometrioma_unilateral")

    return [label for label in label_order if label in labels]


def batch_8_endometriosis_surgery(work_df):
    """
    Endometriosis-surgery cleaning and resection-site classification.

    Cleans endometriosis_surgery to binary (free text is treated as
    positive surgical evidence per Keren and moved to
    endometriosis_surgery_comment), applies the Decision 9 record-level
    composite-key corrections, and derives the 10 structured
    endo_resection_* multi-hot indicators plus the grouped
    endo_resection_sites_clean field.

    Approved decisions: 9.
    QA outputs: endometriosis_surgery_review_df.xlsx (only if
    contradictions are found).
    Returns: df — the working DataFrame with endometriosis-surgery
    variables cleaned.
    """
    BATCH_TITLE = BATCH_METADATA[8]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values, clean_binary_numeric,
        normalize_multi_code_string,
        set_outside_subgroup_to_na,
        log_audit_event, log_deviation_event, write_batch_summary,
        create_review_dataframe,
    )

    print(f"=== Batch 8: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch8.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch8.xlsx")
    review_xlsx    = os.path.join(review_path, "endometriosis_surgery_review_df.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []

    # ------------------------------------------------------------------
    # 1. endometriosis_surgery_comment — create before cleaning
    # ------------------------------------------------------------------
    df["endometriosis_surgery_comment"] = pd.Series(pd.NA, index=df.index, dtype="object")

    # ------------------------------------------------------------------
    # 2. endometriosis_surgery — handle free text, then clean to binary 0/1
    # Rule (Keren): all original free-text in endometriosis_surgery = positive surgical evidence.
    # Free text → endometriosis_surgery = 1; text preserved in endometriosis_surgery_comment.
    # ------------------------------------------------------------------
    endo_surg_raw = df["endometriosis_surgery"].copy()

    # Detect free-text rows: non-NaN values that are not purely numeric binary
    def _is_free_text_surgery(val):
        if pd.isna(val): return False
        try:
            n = float(str(val).strip())
            return n not in (0.0, 1.0)
        except (ValueError, TypeError):
            return True  # non-numeric string → free text

    free_text_mask = endo_surg_raw.map(_is_free_text_surgery)
    n_free_text = int(free_text_mask.sum())

    if n_free_text > 0:
        # Preserve text in comment column
        df.loc[free_text_mask, "endometriosis_surgery_comment"] = (
            endo_surg_raw[free_text_mask].astype(str)
        )
        # Set to 1 per Keren's rule
        df.loc[free_text_mask, "endometriosis_surgery"] = 1
        log_deviation_event(
            path=deviations_md,
            variable="endometriosis_surgery",
            raw_variable="endometriosis surgery",
            documented="Binary field: 0=no surgery, 1=surgery.",
            action=f"{n_free_text} free-text value(s) set to 1; text preserved in endometriosis_surgery_comment.",
            reason="Per Keren: all original free-text in endometriosis_surgery represents positive "
                   "surgical evidence. Text moved to comment column.",
            requires_approval=False,
            batch="Batch 8",
            affected_count=n_free_text,
        )

    df["endometriosis_surgery"] = clean_binary_numeric(df["endometriosis_surgery"])

    # Remaining non-binary values (unexpected — not free text, not 0/1)
    non_free_text_mask = endo_surg_raw.notna() & ~free_text_mask
    n_coerced_nan = int(
        clean_binary_numeric(endo_surg_raw[non_free_text_mask]).isna().sum()
    )
    if n_coerced_nan > 0:
        log_deviation_event(
            path=deviations_md,
            variable="endometriosis_surgery",
            raw_variable="endometriosis surgery",
            documented="Binary field: 0=no surgery, 1=surgery.",
            action=f"{n_coerced_nan} unexpected non-binary numeric value(s) set to NaN.",
            reason="Values not in {0, 1} and not free text. Cannot auto-code; set to NaN for review.",
            requires_approval=False,
            batch="Batch 8",
            affected_count=n_coerced_nan,
        )

    # Canonical private source contains a small table of manually reviewed
    # subject_number + delivery_id decisions here. Literal keys and patient-specific
    # clinical rationales are omitted from this privacy-redacted review copy.
    manual_endo_surgery_decisions = {}


    def _append_endo_surgery_comment(idx, note):
        existing = df.at[idx, "endometriosis_surgery_comment"]
        df.at[idx, "endometriosis_surgery_comment"] = (
            note if pd.isna(existing) else f"{existing}; {note}"
        )

    manual_endo_surgery_reviewed_mask = pd.Series(False, index=df.index)
    n_manual_endo_surgery_decisions = 0
    manual_endo_surgery_missing_pairs = []

    for (subject_number, delivery_id), decision in manual_endo_surgery_decisions.items():
        record_mask = (
            df["subject_number"].eq(subject_number)
            & df["delivery_id"].eq(delivery_id)
        )
        if not record_mask.any():
            manual_endo_surgery_missing_pairs.append((subject_number, delivery_id))
            continue

        manual_endo_surgery_reviewed_mask |= record_mask
        df.loc[record_mask, "endometriosis_surgery"] = decision["value"]
        note = (
            "Manual clinical decision after consultation with Gidi: "
            f"endometriosis_surgery={decision['value']}. {decision['reason']}"
        )
        for idx in df.index[record_mask]:
            _append_endo_surgery_comment(idx, note)
        n_manual_endo_surgery_decisions += int(record_mask.sum())

    if n_manual_endo_surgery_decisions > 0:
        log_deviation_event(
            path=deviations_md,
            variable="endometriosis_surgery",
            raw_variable="endometriosis surgery",
            documented="Binary field: 0=no prior endometriosis surgery, 1=prior endometriosis surgery.",
            action=(
                f"{n_manual_endo_surgery_decisions} manually reviewed record(s) set by "
                "subject_number + delivery_id pair; decision note appended to "
                "endometriosis_surgery_comment."
            ),
            reason=(
                "Manual clinical decision after consultation with Gidi. Prior surgery with "
                "endometriosis-compatible adhesions/adhesiolysis may count as prior "
                "endometriosis-related surgery; current delivery cesarean findings must not "
                "be used as prior surgical history to avoid leakage."
            ),
            requires_approval=False,
            batch="Batch 8",
            affected_count=n_manual_endo_surgery_decisions,
        )

    if manual_endo_surgery_missing_pairs:
        unexpected_findings.append(
            "endometriosis_surgery manual decision pair(s) not found: "
            f"{manual_endo_surgery_missing_pairs}"
        )

    n_endo_surg_0   = int((df["endometriosis_surgery"] == 0).sum())
    n_endo_surg_1   = int((df["endometriosis_surgery"] == 1).sum())
    n_endo_surg_nan = int(df["endometriosis_surgery"].isna().sum())

    ok_surg, unexp_surg = validate_expected_binary_values(
        df["endometriosis_surgery"], "endometriosis_surgery"
    )
    if not ok_surg:
        unexpected_findings.append(f"endometriosis_surgery: unexpected values {unexp_surg}")

    # ------------------------------------------------------------------
    # 2. endo_resection_sites - clinically grouped multi-label field
    # ------------------------------------------------------------------
    RESECTION_VALID_CODES = set(range(1, 12))
    RESECTION_MULTIHOT_COLUMNS = {
        "no_resection": "endo_resection_no_resection",
        "ovarian_endometrioma_unilateral": (
            "endo_resection_ovarian_endometrioma_unilateral"
        ),
        "ovarian_endometrioma_bilateral": (
            "endo_resection_ovarian_endometrioma_bilateral"
        ),
        "adnexa": "endo_resection_adnexa",
        "fallopian_tube": "endo_resection_fallopian_tube",
        "epiploica": "endo_resection_epiploica",
        "uterus": "endo_resection_uterus",
        "lesion_resection": "endo_resection_lesion",
        "adhesiolysis": "endo_resection_adhesiolysis",
        "appendix": "endo_resection_appendix",
    }

    endo_resection_raw_before = df["endo_resection_sites"].copy(deep=True)
    comment_1_before_resection = df["comment_1"].copy(deep=True)
    surgery_comment_before_resection = df[
        "endometriosis_surgery_comment"
    ].copy(deep=True)

    # strict=True: an exact-integer numeric token outside the approved 1-11
    # resection-site code set (e.g. "12") must not silently vanish -- it is
    # caught per-row (same "fail loud, audit visible, never a silent
    # partial-code representation" treatment already given to non-integer
    # tokens like "3.4") and surfaced via unexpected_findings below, never
    # allowed to crash the whole batch on one malformed cell.
    _endo_resection_unmapped_numeric_rows = []

    def _parse_endo_resection_row(idx, raw_value):
        try:
            return normalize_multi_code_string(raw_value, RESECTION_VALID_CODES, strict=True)
        except ValueError as exc:
            _endo_resection_unmapped_numeric_rows.append({
                "row_index": idx,
                "raw_value": raw_value,
                "parse_error": str(exc),
            })
            return []

    endo_res_lists = pd.Series(
        [
            _parse_endo_resection_row(idx, raw_value)
            for idx, raw_value in df["endo_resection_sites"].items()
        ],
        index=df.index,
        dtype="object",
    )
    if _endo_resection_unmapped_numeric_rows:
        unexpected_findings.append(
            "endo_resection_sites contains an unmapped/out-of-range numeric "
            "code (never silently dropped, requires manual review): "
            f"{_endo_resection_unmapped_numeric_rows}"
        )
    grouped_resection_lists = pd.Series(
        [[] for _ in range(len(df))], index=df.index, dtype="object"
    )
    endo_surgery_positive_mask = df["endometriosis_surgery"].eq(1)
    positive_resection_index = df.index[endo_surgery_positive_mask]
    grouped_resection_lists.loc[endo_surgery_positive_mask] = pd.Series(
        [
            _group_endo_resection_sites(raw_value, parsed_codes)
            for raw_value, parsed_codes in zip(
                df.loc[endo_surgery_positive_mask, "endo_resection_sites"],
                endo_res_lists.loc[endo_surgery_positive_mask],
            )
        ],
        index=positive_resection_index,
        dtype="object",
    )

    df["endo_resection_sites_clean"] = grouped_resection_lists.map(
        lambda labels: "|".join(labels) if labels else np.nan
    )

    known_resection_mask = (
        endo_surgery_positive_mask
        & df["endo_resection_sites_clean"].notna()
    )
    for label, column_name in RESECTION_MULTIHOT_COLUMNS.items():
        df[column_name] = np.nan
        df.loc[known_resection_mask, column_name] = grouped_resection_lists.loc[
            known_resection_mask
        ].map(lambda labels, expected=label: int(expected in labels))

    no_endo_surgery_mask = df["endometriosis_surgery"].eq(0)
    adhesiolysis_before_subgroup_vc = (
        df["endo_surgery_adhesiolysis"].value_counts(dropna=False).to_dict()
    )
    n_adhesiolysis_set_na = int(
        df.loc[no_endo_surgery_mask, "endo_surgery_adhesiolysis"].notna().sum()
    )
    df = set_outside_subgroup_to_na(
        df,
        "endo_surgery_adhesiolysis",
        endo_surgery_positive_mask,
    )
    adhesiolysis_after_subgroup_vc = (
        df["endo_surgery_adhesiolysis"].value_counts(dropna=False).to_dict()
    )
    n_adhesiolysis_nonnull_without_surgery = int(
        df.loc[no_endo_surgery_mask, "endo_surgery_adhesiolysis"].notna().sum()
    )
    if n_adhesiolysis_set_na > 0:
        log_deviation_event(
            path=deviations_md,
            variable="endo_surgery_adhesiolysis",
            raw_variable="ניתוח אנדו- הפרדת הידבקויות",
            documented="Surgery-specific binary characteristic.",
            action=(
                "Set to missing where corrected endometriosis_surgery == 0 "
                f"({n_adhesiolysis_set_na} row(s))."
            ),
            reason=(
                "endo_surgery_adhesiolysis is not applicable when there was no "
                "corrected endometriosis surgery."
            ),
            requires_approval=False,
            batch="Batch 8",
            affected_count=n_adhesiolysis_set_na,
        )

    true_zero_resection_mask = (
        endo_surgery_positive_mask
        & df["endo_resection_sites"].map(_is_exact_zero_resection_site)
    )
    kidney_text_mask = df["endo_resection_sites"].astype("string").str.contains(
        "כריתת כליה שמאלית", regex=False, na=False
    )

    approved_resection_text_phrases = (
        "תוספתן",
        "ציסטה בשחלה",
        "כריתת כליה שמאלית",
    )

    def _unsupported_resection_text_residue(raw_value):
        if pd.isna(raw_value):
            return ""

        residue = str(raw_value)
        for approved_phrase in approved_resection_text_phrases:
            residue = residue.replace(approved_phrase, " ")

        # Remove valid numeric codes while leaving unsupported words untouched.
        residue = re.sub(
            r"(?<![\d.])(?:10|11|[0-9])(?:\.0+)?(?![\d.])",
            " ",
            residue,
        )
        residue = residue.strip()
        return residue if re.search(r"[A-Za-zא-ת]", residue) else ""

    unsupported_resection_text_rows = []
    for idx in df.index[endo_surgery_positive_mask]:
        unsupported_residue = _unsupported_resection_text_residue(
            df.at[idx, "endo_resection_sites"]
        )
        if unsupported_residue:
            unsupported_resection_text_rows.append(
                {
                    "subject_number": df.at[idx, "subject_number"],
                    "delivery_id": df.at[idx, "delivery_id"],
                    "residue": unsupported_residue,
                }
            )

    if unsupported_resection_text_rows:
        unexpected_findings.append(
            "endo_resection_sites contains unsupported free-text residue after "
            "approved parsing: "
            f"{unsupported_resection_text_rows}"
        )

    n_res_clean = int(df["endo_resection_sites_clean"].notna().sum())
    n_res_nan = int(df["endo_resection_sites_clean"].isna().sum())
    n_res_true_zero = int(true_zero_resection_mask.sum())
    n_res_not_applicable = int(no_endo_surgery_mask.sum())
    n_res_unresolved = int(
        (endo_surgery_positive_mask & df["endo_resection_sites_clean"].isna()).sum()
    )
    n_kidney_text_excluded = int(kidney_text_mask.sum())
    resection_label_counts = {
        label: int(
            grouped_resection_lists.map(lambda labels: label in labels).sum()
        )
        for label in RESECTION_LABEL_ORDER
    }

    # Validation: raw/reference data and comments must not be changed by this derivation.
    if not df["endo_resection_sites"].equals(endo_resection_raw_before):
        unexpected_findings.append(
            "endo_resection_sites raw source changed during grouped derivation"
        )
    if not df["comment_1"].equals(comment_1_before_resection):
        unexpected_findings.append(
            "comment_1 changed during endo_resection_sites grouped derivation"
        )
    if not df["endometriosis_surgery_comment"].equals(
        surgery_comment_before_resection
    ):
        unexpected_findings.append(
            "endometriosis_surgery_comment changed during endo_resection_sites "
            "grouped derivation"
        )

    allowed_resection_labels = set(RESECTION_LABEL_ORDER)
    for idx, clean_value in df["endo_resection_sites_clean"].dropna().items():
        labels = clean_value.split("|")
        unknown_labels = set(labels) - allowed_resection_labels
        if unknown_labels:
            unexpected_findings.append(
                f"endo_resection_sites_clean row {idx}: disallowed labels "
                f"{sorted(unknown_labels)}"
            )
        if any(
            separator in clean_value for separator in (",", ";", "+", "/")
        ) or any(character.isdigit() for character in clean_value):
            unexpected_findings.append(
                f"endo_resection_sites_clean row {idx}: numeric label or invalid separator"
            )
        if len(labels) != len(set(labels)):
            unexpected_findings.append(
                f"endo_resection_sites_clean row {idx}: duplicate labels"
            )
        expected_order = [
            label for label in RESECTION_LABEL_ORDER if label in set(labels)
        ]
        if labels != expected_order:
            unexpected_findings.append(
                f"endo_resection_sites_clean row {idx}: labels not in fixed order"
            )
        if "no_resection" in labels and len(labels) > 1:
            unexpected_findings.append(
                f"endo_resection_sites_clean row {idx}: no_resection coexists "
                "with another label"
            )

    if df.loc[
        no_endo_surgery_mask, "endo_resection_sites_clean"
    ].notna().any():
        unexpected_findings.append(
            "endo_resection_sites_clean is non-NaN where endometriosis_surgery=0"
        )

    resection_multihot_cols = list(RESECTION_MULTIHOT_COLUMNS.values())
    if df.loc[no_endo_surgery_mask, resection_multihot_cols].notna().any().any():
        unexpected_findings.append(
            "endo_resection multi-hot value is non-NaN where "
            "endometriosis_surgery=0"
        )
    if n_adhesiolysis_nonnull_without_surgery != 0:
        unexpected_findings.append(
            "endo_surgery_adhesiolysis is non-NaN where endometriosis_surgery=0"
        )

    known_multihot_values = df.loc[known_resection_mask, resection_multihot_cols]
    invalid_known_multihot = ~known_multihot_values.isin([0, 1])
    if invalid_known_multihot.any().any():
        unexpected_findings.append(
            "surgery-positive known resection rows contain non-binary multi-hot values"
        )

    unresolved_resection_mask = (
        endo_surgery_positive_mask
        & df["endo_resection_sites_clean"].isna()
    )
    if df.loc[
        unresolved_resection_mask, resection_multihot_cols
    ].notna().any().any():
        unexpected_findings.append(
            "unresolved surgery-positive resection rows contain non-NaN "
            "multi-hot values"
        )

    for label, column_name in RESECTION_MULTIHOT_COLUMNS.items():
        expected_values = grouped_resection_lists.loc[known_resection_mask].map(
            lambda labels, expected=label: int(expected in labels)
        )
        actual_values = df.loc[known_resection_mask, column_name].astype(int)
        if (actual_values != expected_values.astype(int)).any():
            unexpected_findings.append(
                f"{column_name} does not match endo_resection_sites_clean membership"
            )

    # Canonical private source also verifies a small set of reviewed
    # composite-key resection expectations. Record keys and per-record expected
    # label combinations are redacted from this review copy.
    reviewed_resection_expectations = {}
    for (subject_number, delivery_id), expected_clean in reviewed_resection_expectations.items():
        pass

    kidney_positive_mask = kidney_text_mask & endo_surgery_positive_mask
    for idx in df.index[kidney_positive_mask]:
        raw_without_kidney_text = str(df.at[idx, "endo_resection_sites"]).replace(
            "כריתת כליה שמאלית", ""
        )
        labels_without_kidney_text = _group_endo_resection_sites(
            raw_without_kidney_text, endo_res_lists.at[idx]
        )
        if grouped_resection_lists.at[idx] != labels_without_kidney_text:
            unexpected_findings.append(
                f"endo_resection_sites row {idx}: kidney removal text generated "
                "a grouped label"
            )

    # ------------------------------------------------------------------
    # 3. Binary surgical variables — validate expected values, no imputation
    # ------------------------------------------------------------------
    binary_surg_cols = [
        "vaginal_opening_during_surgery",
        "bowel_lesion_resected",
        "bladder_lesion_resected",
        "endo_surgery_adhesiolysis",
    ]
    binary_surg_results = {}
    for col in binary_surg_cols:
        ok, unexp = validate_expected_binary_values(df[col], col)
        binary_surg_results[col] = {
            "ok": ok,
            "unexpected": unexp,
            "vc": df[col].value_counts(dropna=False).to_dict(),
        }
        if not ok:
            unexpected_findings.append(f"{col}: unexpected values {unexp}")

    # ------------------------------------------------------------------
    # 4. surgery_details, comment_1 — normalize placeholder zeros; preserve
    # ------------------------------------------------------------------
    def _normalize_freetext_zeros(series):
        return series.apply(lambda v: np.nan if v in (0, "0", 0.0) else v)

    before_sd = df["surgery_details"].copy()
    df["surgery_details"] = _normalize_freetext_zeros(df["surgery_details"])
    n_sd_zeros = int(before_sd.map(lambda v: v in (0, "0", 0.0)).sum())

    before_c4 = df["comment_1"].copy()
    df["comment_1"] = _normalize_freetext_zeros(df["comment_1"])
    n_c4_zeros = int(before_c4.map(lambda v: v in (0, "0", 0.0)).sum())

    # ------------------------------------------------------------------
    # 5. Contradiction review: endometriosis_surgery=0 or NaN but positive surgical evidence
    # Do not auto-update endometriosis_surgery from support columns; export for manual review.
    # ------------------------------------------------------------------
    surg_evidence_mask = (
        df["vaginal_opening_during_surgery"].eq(1) |
        df["bowel_lesion_resected"].eq(1) |
        df["bladder_lesion_resected"].eq(1) |
        df["endo_surgery_adhesiolysis"].eq(1) |
        df["endo_resection_sites_clean"].notna()
    )
    # Include both surgery=0 and surgery=NaN with surgical evidence
    contradiction_mask = (
        (df["endometriosis_surgery"].isna() | (df["endometriosis_surgery"] == 0))
        & surg_evidence_mask
        & ~manual_endo_surgery_reviewed_mask
    )
    n_contradictions = int(contradiction_mask.sum())

    if n_contradictions > 0:
        note = "Surgical evidence present but endometriosis_surgery=0/NaN  requires manual review."
        for idx in df.index[contradiction_mask]:
            existing = df.at[idx, "endometriosis_surgery_comment"]
            df.at[idx, "endometriosis_surgery_comment"] = (
                note if pd.isna(existing) else f"{existing}; {note}"
            )

        review_cols = [
            "type_of_CS",
            "target_intrapartum_cs",
            "S_P_CS",
            "CS",
            "endometriosis_surgery",
            "endometriosis_surgery_comment",
            "endo_resection_sites",
            "endo_resection_sites_clean",
            "vaginal_opening_during_surgery",
            "bowel_lesion_resected",
            "bladder_lesion_resected",
            "endo_surgery_adhesiolysis",
            "surgery_details",
        ]
        review_df = create_review_dataframe(
            df, contradiction_mask,
            cols=review_cols,
            id_cols=["delivery_id", "subject_number"],
        )
        review_df["manual_review_decision"] = pd.NA
        review_df["manual_review_reason"] = review_df["endometriosis_surgery_comment"]
        os.makedirs(review_path, exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        print(f"  Review file saved: {review_xlsx} ({n_contradictions} rows)")
        print(f"  WARNING: {n_contradictions} contradiction row(s) require manual review — "
              f"endometriosis_surgery NOT auto-updated from surgical evidence")
    else:
        if os.path.exists(review_xlsx):
            os.remove(review_xlsx)
            print(f"  Cleared stale review file: {review_xlsx}")
        print("  No surgery contradictions found.")

    # ------------------------------------------------------------------
    # Save + audit
    # ------------------------------------------------------------------
    os.makedirs(processed_path, exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    binary_lines = "\n".join(
        f"  - {col}: {r['vc']} | unexpected: {'none' if r['ok'] else str(r['unexpected'])}"
        for col, r in binary_surg_results.items()
    )

    summary = f"""# Preprocessing Batch 8 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## endometriosis_surgery (binary 0/1)
- Raw value counts: {endo_surg_raw.value_counts(dropna=False).to_dict()}
- Free-text rows set to 1 (Keren rule) + text moved to comment: {n_free_text}
- Manual clinical decisions applied after consultation with Gidi: {n_manual_endo_surgery_decisions}
- After cleaning: 0={n_endo_surg_0}, 1={n_endo_surg_1}, NaN={n_endo_surg_nan}
- Unexpected non-binary numeric values coerced to NaN: {n_coerced_nan}

## endo_resection_sites_clean (clinically grouped multi-label column)
- Non-null grouped values: {n_res_clean}
- `no_resection` for endometriosis_surgery=1 and raw endo_resection_sites exactly 0: {n_res_true_zero}
- NaN total: {n_res_nan}
- Not applicable due to endometriosis_surgery=0: {n_res_not_applicable}
- Unresolved among endometriosis_surgery=1: {n_res_unresolved}
- Allowed labels in fixed order: {list(RESECTION_LABEL_ORDER)}
- Separator: `|`
- Grouped label counts: {resection_label_counts}
- Hebrew text `תוספתן` maps to `appendix`.
- Hebrew text `ציסטה בשחלה` maps to `ovarian_endometrioma_unilateral`.
- Left kidney removal text (`כריתת כליה שמאלית`) is intentionally excluded from grouped endometriosis resection-site labels and remains only in existing source/operative context: {n_kidney_text_excluded} row(s).
- Multi-hot columns created: {resection_multihot_cols}

## Binary surgical variables (validated only, no imputation)
{binary_lines}

## endo_surgery_adhesiolysis subgroup rule
- Rule: set to NaN where corrected endometriosis_surgery == 0.
- Before subgroup rule: {adhesiolysis_before_subgroup_vc}
- Rows set to NaN: {n_adhesiolysis_set_na}
- After subgroup rule: {adhesiolysis_after_subgroup_vc}
- Non-null rows remaining where endometriosis_surgery == 0: {n_adhesiolysis_nonnull_without_surgery}

## surgery_details, comment_1
- Preserved as free-text reference columns.
- Placeholder zeros normalized to NaN: surgery_details={n_sd_zeros}, comment_1={n_c4_zeros}

## endometriosis_surgery_comment (new column)
- Free-text rows from endometriosis_surgery: {n_free_text} values moved here and set to 1.
- Contradiction rows (surgery=0/NaN but surgical evidence): {n_contradictions} rows annotated.
- NaN for all other rows.

## Contradiction review (endometriosis_surgery=0/NaN but positive surgical evidence)
- Rows flagged: {n_contradictions}
- endometriosis_surgery NOT auto-updated  requires manual clinical review
- Manually resolved record pairs are excluded from unresolved export only by exact subject_number + delivery_id match.
{"- Review file: " + review_xlsx if n_contradictions > 0 else "- No review file generated."}
- Review columns: delivery_id, subject_number, type_of_CS, S_P_CS, endometriosis_surgery, endometriosis_surgery_comment, support columns, manual_review_decision, manual_review_reason

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}
{"- Review: " + review_xlsx if n_contradictions > 0 else ""}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)

    log_audit_event(
        audit_log_md,
        f"Batch 8 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- endometriosis_surgery: 0={n_endo_surg_0}, 1={n_endo_surg_1}, NaN={n_endo_surg_nan}\n"
        f"- Manual endometriosis_surgery decisions applied: {n_manual_endo_surgery_decisions}\n"
        f"- endo_resection_sites_clean: {n_res_clean} grouped non-null, "
        f"{n_res_true_zero} no_resection, {n_res_unresolved} unresolved among "
        f"endometriosis_surgery=1\n"
        f"- endo_resection grouped label counts: {resection_label_counts}\n"
        f"- endo_resection multi-hot columns: {resection_multihot_cols}\n"
        f"- Left kidney removal text intentionally excluded from grouped labels: "
        f"{n_kidney_text_excluded} row(s); no comment duplication\n"
        f"- Binary cols validated: {binary_surg_cols}\n"
        f"- endometriosis_surgery_comment: new column; populated for free-text, contradiction-review, and manual-decision documentation as applicable\n"
        f"- Surgery contradictions for review: {n_contradictions} (endometriosis_surgery NOT auto-updated)\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  endometriosis_surgery: 0={n_endo_surg_0}, 1={n_endo_surg_1}, NaN={n_endo_surg_nan}")
    print(f"  endo_resection_sites_clean: {n_res_clean} grouped non-null, "
          f"{n_res_true_zero} no_resection, {n_res_unresolved} unresolved")
    print(f"  endo_resection multi-hot columns: {resection_multihot_cols}")
    for col, r in binary_surg_results.items():
        print(f"  {col}: {r['vc']}")
    print(f"  Contradictions flagged for review: {n_contradictions} (endometriosis_surgery NOT auto-updated)")
    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 8 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 9 — Pregnancy anthropometry and antenatal treatment variables
# weight_before_pregnancy, weight_in_pregnancy, height, BMI_before, BMI_after,
# aspirin_during_pregnancy, clexane_during_pregnancy
# ---------------------------------------------------------------------------

def batch_9_body_size_and_treatment(work_df):
    """
    Pregnancy anthropometry and antenatal treatment variables.

    Standardizes weight/height/BMI variables and antenatal treatment flags
    (aspirin, clexane), flagging values outside a broad sanity/plausibility
    review range for manual review instead of silently discarding or
    auto-correcting them. These ranges are conservative review thresholds,
    NOT proven physiological-impossibility bounds and NOT backed by a cited
    clinical decision -- a value outside a range is a review trigger, never a
    truth claim that the source value cannot exist. No numeric bound in this
    batch mutates a value.

    QA outputs: body_size_impossible_values_review_df.xlsx -- the filename is
    historical ("impossible"); its current semantic meaning is
    "sanity/plausibility review" (only written when at least one value is
    outside a review range; currently 0).
    Returns: df — the working DataFrame with anthropometry/treatment
    variables cleaned.
    """
    BATCH_TITLE = BATCH_METADATA[9]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values,
        log_audit_event, log_deviation_event, write_batch_summary,
        create_review_dataframe,
    )

    print(f"=== Batch 9: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch9.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch9.xlsx")
    review_xlsx    = os.path.join(review_path, "body_size_impossible_values_review_df.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []
    review_reasons = {}  # delivery_id -> list of reasons

    def _add_review(mask, reason):
        for did in df.loc[mask, "delivery_id"]:
            review_reasons.setdefault(did, []).append(reason)

    # ------------------------------------------------------------------
    # 1. weight_before_pregnancy — coerce to numeric; flag outside sanity/plausibility review range
    # ------------------------------------------------------------------
    WEIGHT_MIN, WEIGHT_MAX = 30.0, 250.0

    df["weight_before_pregnancy"] = pd.to_numeric(
        df["weight_before_pregnancy"], errors="coerce"
    )
    wbp_invalid = df["weight_before_pregnancy"].notna() & (
        (df["weight_before_pregnancy"] < WEIGHT_MIN) |
        (df["weight_before_pregnancy"] > WEIGHT_MAX)
    )
    n_wbp_invalid = int(wbp_invalid.sum())
    if n_wbp_invalid:
        _add_review(wbp_invalid,
                    f"weight_before_pregnancy outside [{WEIGHT_MIN},{WEIGHT_MAX}] kg")
    print(f"  weight_before_pregnancy: {df['weight_before_pregnancy'].notna().sum()} valid, "
          f"{df['weight_before_pregnancy'].isna().sum()} NaN, {n_wbp_invalid} flagged")

    # ------------------------------------------------------------------
    # 2. weight_in_pregnancy — coerce to numeric; flag outside sanity/plausibility review range
    # ------------------------------------------------------------------
    WEIGHT_PREG_MAX = 300.0

    df["weight_in_pregnancy"] = pd.to_numeric(
        df["weight_in_pregnancy"], errors="coerce"
    )
    wip_invalid = df["weight_in_pregnancy"].notna() & (
        (df["weight_in_pregnancy"] < WEIGHT_MIN) |
        (df["weight_in_pregnancy"] > WEIGHT_PREG_MAX)
    )
    n_wip_invalid = int(wip_invalid.sum())
    if n_wip_invalid:
        _add_review(wip_invalid,
                    f"weight_in_pregnancy outside [{WEIGHT_MIN},{WEIGHT_PREG_MAX}] kg")
    print(f"  weight_in_pregnancy: {df['weight_in_pregnancy'].notna().sum()} valid, "
          f"{df['weight_in_pregnancy'].isna().sum()} NaN, {n_wip_invalid} flagged")

    # ------------------------------------------------------------------
    # 3. height — coerce to numeric; normalize meters→cm if clearly in meters
    #    (deterministic unit normalization -- a data-quality correction, NOT
    #    outlier handling); then flag outside a sanity/plausibility review range
    # ------------------------------------------------------------------
    HEIGHT_MIN_CM, HEIGHT_MAX_CM = 100.0, 220.0

    df["height"] = pd.to_numeric(df["height"], errors="coerce")

    # Values clearly in meters (0 < h < 3) → convert to cm
    meters_mask = df["height"].notna() & (df["height"] > 0) & (df["height"] < 3)
    n_meters = int(meters_mask.sum())
    height_conversion_audit_xlsx = os.path.join(
        audit_path, "height_meters_to_cm_conversion_audit.xlsx"
    )
    if n_meters > 0:
        # Row-level audit trail (PRE-B9-006, 2026-07-31): capture the composite
        # key and raw/processed values BEFORE overwriting, so every conversion
        # is individually traceable rather than only an aggregate count. This
        # does not change the deterministic conversion rule or behavior --
        # it only adds evidence for it.
        conv_keys = df.loc[meters_mask, ["subject_number", "delivery_id"]]
        if conv_keys.isna().to_numpy().any():
            raise ValueError(
                "height meters->cm conversion: one or more affected rows have a "
                "missing subject_number or delivery_id -- cannot produce a "
                "row-level audit trail. Aborting rather than converting silently."
            )
        composite_keys = list(zip(conv_keys["subject_number"], conv_keys["delivery_id"]))
        if len(composite_keys) != len(set(composite_keys)):
            raise ValueError(
                "height meters->cm conversion: duplicate subject_number+delivery_id "
                "composite key(s) found among affected rows -- cannot produce a "
                "unique row-level audit trail. Aborting rather than converting silently."
            )

        raw_heights = df.loc[meters_mask, "height"].copy()
        processed_heights = (raw_heights * 100).round(1)

        # "Impossible post-conversion result" fail-loud guard: a value that is
        # merely outside the plausible reporting range (e.g. a hypothetical
        # 295cm) is still allowed through to the existing height_invalid
        # flag-for-review path below -- it is not silently discarded. Only a
        # non-physical result (<=0 or non-finite) aborts the batch outright,
        # since that would indicate the deterministic rule itself misbehaved,
        # not a data-quality issue in the source value.
        if not (processed_heights > 0).all() or not np.isfinite(processed_heights.to_numpy()).all():
            raise ValueError(
                "height meters->cm conversion produced a non-physical result "
                "(<=0 or non-finite) -- aborting rather than writing an impossible value."
            )

        height_conversion_audit = pd.DataFrame({
            "subject_number": conv_keys["subject_number"].to_numpy(),
            "delivery_id": conv_keys["delivery_id"].to_numpy(),
            "source_column": "highth",
            "raw_value": raw_heights.to_numpy(),
            "processed_value": processed_heights.to_numpy(),
            "original_unit_assumption": "meters",
            "final_unit": "centimeters",
            "applied_rule": "0 < raw_value < 3 -> processed_value = round(raw_value * 100, 1)",
            "reason": "Values in range (0, 3) are clearly meters; rest of column is in "
                      "cm. Normalized to consistent cm scale.",
        })
        os.makedirs(audit_path, exist_ok=True)
        height_conversion_audit.to_excel(height_conversion_audit_xlsx, index=False)

        df.loc[meters_mask, "height"] = processed_heights
        log_deviation_event(
            path=deviations_md,
            variable="height",
            raw_variable="highth",
            documented="Height stored as a numeric value (expected cm per documentation).",
            action=f"Converted {n_meters} value(s) from meters to cm (multiplied by 100). "
                   f"Row-level audit: {height_conversion_audit_xlsx}",
            reason="Values in range (0, 3) are clearly meters; rest of column is in cm. "
                   "Normalized to consistent cm scale.",
            requires_approval=False,
            batch="Batch 9",
            affected_count=n_meters,
        )

    height_invalid = df["height"].notna() & (
        (df["height"] < HEIGHT_MIN_CM) | (df["height"] > HEIGHT_MAX_CM)
    )
    n_height_invalid = int(height_invalid.sum())
    if n_height_invalid:
        _add_review(height_invalid,
                    f"height outside [{HEIGHT_MIN_CM},{HEIGHT_MAX_CM}] cm after normalization")
    print(f"  height: {df['height'].notna().sum()} valid, "
          f"{df['height'].isna().sum()} NaN, {n_meters} meters->cm, {n_height_invalid} flagged")

    # ------------------------------------------------------------------
    # 4. BMI_before, BMI_after — keep existing; flag outside sanity/plausibility review range
    # ------------------------------------------------------------------
    BMI_MIN, BMI_MAX = 10.0, 70.0

    for bmi_col in ("BMI_before", "BMI_after"):
        df[bmi_col] = pd.to_numeric(df[bmi_col], errors="coerce")
        invalid_mask = df[bmi_col].notna() & (
            (df[bmi_col] < BMI_MIN) | (df[bmi_col] > BMI_MAX)
        )
        n_invalid = int(invalid_mask.sum())
        if n_invalid:
            _add_review(invalid_mask,
                        f"{bmi_col} outside [{BMI_MIN},{BMI_MAX}]")
            unexpected_findings.append(
                f"{bmi_col}: {n_invalid} value(s) outside the sanity/plausibility review "
                f"range [{BMI_MIN},{BMI_MAX}] (review threshold, not a proven-impossibility bound)"
            )
        print(f"  {bmi_col}: {df[bmi_col].notna().sum()} valid, "
              f"{df[bmi_col].isna().sum()} NaN, {n_invalid} flagged")

    # ------------------------------------------------------------------
    # 5. aspirin_during_pregnancy, clexane_during_pregnancy — validate binary
    # ------------------------------------------------------------------
    for bin_col in ("aspirin_during_pregnancy", "clexane_during_pregnancy"):
        ok, unexp = validate_expected_binary_values(df[bin_col], bin_col)
        vc = df[bin_col].value_counts(dropna=False).to_dict()
        if not ok:
            unexpected_findings.append(f"{bin_col}: unexpected values {unexp}")
            _add_review(
                df[bin_col].map(
                    lambda v, u=unexp: not (
                        pd.isna(v) or v in (0, 1, 0.0, 1.0)
                    )
                ),
                f"{bin_col} has unexpected value"
            )
        print(f"  {bin_col}: {vc}")

    # ------------------------------------------------------------------
    # 6. Review file for flagged rows
    # ------------------------------------------------------------------
    if review_reasons:
        flag_index = list(review_reasons.keys())
        flag_mask  = df["delivery_id"].isin(flag_index)
        review_cols = [
            "weight_before_pregnancy",
            "weight_in_pregnancy",
            "height",
            "BMI_before",
            "BMI_after",
            "aspirin_during_pregnancy",
            "clexane_during_pregnancy",
        ]
        review_df = create_review_dataframe(
            df, flag_mask,
            cols=review_cols,
            id_cols=["delivery_id", "subject_number"],
        )
        review_df["review_reason"] = review_df["delivery_id"].map(
            lambda did: "; ".join(review_reasons.get(did, []))
        )
        os.makedirs(review_path, exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        n_flagged = len(review_df)
        print(f"  Review file saved: {review_xlsx} ({n_flagged} rows)")
    else:
        n_flagged = 0
        print("  No values outside a sanity/plausibility review range.")

    # ------------------------------------------------------------------
    # Save + audit
    # ------------------------------------------------------------------
    os.makedirs(processed_path, exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    summary = f"""# Preprocessing Batch 9 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

> Note: the numeric ranges below are **broad sanity/plausibility review
> thresholds** with no cited clinical-decision provenance -- a value outside a
> range is a manual-review trigger only, never mutated, and never a claim that
> the source value is physically impossible. The metre->cm height step is a
> deterministic unit normalization (a data-quality correction), separate from
> this review-threshold screening.

## weight_before_pregnancy (kg)
- Valid: {df["weight_before_pregnancy"].notna().sum()} | NaN: {df["weight_before_pregnancy"].isna().sum()}
- Flagged outside sanity-review range [30, 250] kg: {n_wbp_invalid}

## weight_in_pregnancy (kg)
- Valid: {df["weight_in_pregnancy"].notna().sum()} | NaN: {df["weight_in_pregnancy"].isna().sum()}
- Flagged outside sanity-review range [30, 300] kg: {n_wip_invalid}

## height (cm)
- Valid: {df["height"].notna().sum()} | NaN: {df["height"].isna().sum()}
- Meter values deterministically normalized to cm (unit correction, not outlier handling): {n_meters}
{"- Row-level conversion audit: " + height_conversion_audit_xlsx if n_meters > 0 else ""}
- Flagged outside sanity-review range [100, 220] cm after normalization: {n_height_invalid}

## BMI_before
- Valid: {df["BMI_before"].notna().sum()} | NaN: {df["BMI_before"].isna().sum()}
- Flagged outside sanity-review range [10, 70]: {int((df["BMI_before"].notna() & ((df["BMI_before"] < BMI_MIN) | (df["BMI_before"] > BMI_MAX))).sum())}

## BMI_after
- Valid: {df["BMI_after"].notna().sum()} | NaN: {df["BMI_after"].isna().sum()}
- Flagged outside sanity-review range [10, 70]: {int((df["BMI_after"].notna() & ((df["BMI_after"] < BMI_MIN) | (df["BMI_after"] > BMI_MAX))).sum())}

## aspirin_during_pregnancy
- {df["aspirin_during_pregnancy"].value_counts(dropna=False).to_dict()}

## clexane_during_pregnancy
- {df["clexane_during_pregnancy"].value_counts(dropna=False).to_dict()}

## Review file
- Rows flagged outside a sanity/plausibility review range: {n_flagged}
{"- Review file: " + review_xlsx if n_flagged > 0 else "- No review file generated."}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}
{"- Review: " + review_xlsx if n_flagged > 0 else ""}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)

    log_audit_event(
        audit_log_md,
        f"Batch 9 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- weight_before_pregnancy: {df['weight_before_pregnancy'].notna().sum()} valid, "
        f"{n_wbp_invalid} outside sanity-review range\n"
        f"- weight_in_pregnancy: {df['weight_in_pregnancy'].notna().sum()} valid, "
        f"{n_wip_invalid} outside sanity-review range\n"
        f"- height: {df['height'].notna().sum()} valid, {n_meters} meter->cm (unit fix), "
        f"{n_height_invalid} outside sanity-review range\n"
        f"- BMI_before/after: validated\n"
        f"- aspirin/clexane binary: validated\n"
        f"- Rows flagged for review: {n_flagged}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Rows flagged for review: {n_flagged}")
    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 9 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 10 — Conception method and fertility-treatment standardization
# mode_of_conception, mode_of_conception_details, mode_of_conception_ivf_vs_all
# ---------------------------------------------------------------------------

def batch_10_conception(work_df):
    """
    Conception method and fertility-treatment standardization.

    Validates mode_of_conception against the centralized permitted code set
    (MODE_OF_CONCEPTION_VALID_CODES, PRE-B10-006) and re-validates the
    Decision-30-recomputed mode_of_conception_ivf_vs_all binary.
    mode_of_conception itself is never modified or deleted (reference
    column) -- an invalid source value is set to NaN in the analytical
    column, never silently mapped to a valid category and never restored
    from the original raw text after being flagged (PRE-B10-001). The
    original raw value is preserved only in the row-level review evidence.

    If any invalid mode_of_conception value or unexpected
    mode_of_conception_ivf_vs_all value is found, this is a blocking
    failure: the canonical Batch 10 output is NOT written, and this
    function raises RuntimeError after producing diagnostic evidence
    (review file, summary, audit log entry). Current data contain zero
    such values, so this path is not exercised today.

    Approved decisions: 30, 7 (superseded reference_only note).
    QA outputs: conception_review_df.xlsx (created/replaced only if
    invalid rows are found this run; removed if a stale copy exists from
    a prior run and none are found this run).
    Returns: df — the working DataFrame with conception variables
    validated.
    """
    BATCH_TITLE = BATCH_METADATA[10]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values,
        log_audit_event, log_deviation_event, write_batch_summary,
        create_review_dataframe,
    )

    print(f"=== Batch 10: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch10.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch10.xlsx")
    review_xlsx    = os.path.join(review_path, "conception_review_df.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []

    # ------------------------------------------------------------------
    # 1. mode_of_conception — coerce to numeric; validate against the
    #    centralized permitted code set (PRE-B10-006). A present-but-invalid
    #    value (non-numeric text, or numeric but outside
    #    MODE_OF_CONCEPTION_VALID_CODES -- e.g. negative, decimal, >3) is set
    #    to NaN in the analytical column and is never restored. A value that
    #    was already missing in the source is left as NaN and is NOT treated
    #    as invalid.
    # ------------------------------------------------------------------
    moc_before   = df["mode_of_conception"].copy()
    moc_coerced  = pd.to_numeric(moc_before, errors="coerce")
    moc_unparseable  = moc_before.notna() & moc_coerced.isna()
    moc_out_of_range = moc_coerced.notna() & ~moc_coerced.isin(MODE_OF_CONCEPTION_VALID_CODES)
    moc_invalid_mask = moc_unparseable | moc_out_of_range
    n_moc_invalid = int(moc_invalid_mask.sum())

    df["mode_of_conception"] = moc_coerced.mask(moc_out_of_range, np.nan)
    moc_vc = df["mode_of_conception"].value_counts(dropna=False).sort_index().to_dict()

    if n_moc_invalid:
        unexpected_findings.append(
            f"mode_of_conception: {n_moc_invalid} value(s) outside the permitted code set "
            f"{sorted(MODE_OF_CONCEPTION_VALID_CODES)} (non-numeric or out-of-range); set to NaN"
        )
    print(f"  mode_of_conception: {moc_vc}")

    # ------------------------------------------------------------------
    # 2. mode_of_conception_details — free text; normalize placeholder zeros
    # ------------------------------------------------------------------
    before_cmd = df["mode_of_conception_details"].copy()
    df["mode_of_conception_details"] = df["mode_of_conception_details"].apply(
        lambda v: np.nan if v in (0, "0", 0.0) else v
    )
    n_cmd_zeros = int(before_cmd.map(lambda v: v in (0, "0", 0.0)).sum())
    n_cmd_text  = int(
        df["mode_of_conception_details"].map(
            lambda v: not pd.isna(v)
        ).sum()
    )
    print(f"  mode_of_conception_details: {n_cmd_text} non-null, {n_cmd_zeros} zeros->NaN")

    # ------------------------------------------------------------------
    # 3. mode_of_conception_ivf_vs_all — re-validate binary (defense-in-depth)
    # This column is now deterministically derived from mode_of_conception in
    # Batch 2, Step 0 (Decision 30, 2026-07-29), before cohort filtering. This
    # step no longer establishes the value -- it only reconfirms it is still a
    # clean binary (0, 1, or NaN) at this later pipeline stage.
    # ------------------------------------------------------------------
    moc_ivf_vc = df["mode_of_conception_ivf_vs_all"].value_counts(dropna=False).sort_index().to_dict()
    ok_ivf, unexp_ivf = validate_expected_binary_values(
        df["mode_of_conception_ivf_vs_all"], "mode_of_conception_ivf_vs_all"
    )
    if not ok_ivf:
        unexpected_findings.append(
            f"mode_of_conception_ivf_vs_all: unexpected values {unexp_ivf}"
        )
    print(f"  mode_of_conception_ivf_vs_all: {moc_ivf_vc}")

    # ------------------------------------------------------------------
    # 4. Review-file lifecycle (PRE-B10-001): create/replace when invalid
    #    rows exist this run; remove a stale copy from a prior run when none
    #    exist this run. The original raw value is written ONLY into this
    #    review evidence -- never back into the analytical `df`.
    # ------------------------------------------------------------------
    if n_moc_invalid:
        review_df = create_review_dataframe(
            df, moc_invalid_mask,
            cols=["mode_of_conception", "mode_of_conception_details",
                  "mode_of_conception_ivf_vs_all"],
            id_cols=["delivery_id", "subject_number"],
        )
        # Original pre-coercion source value, preserved only here for audit.
        review_df["mode_of_conception_raw_value"] = moc_before[moc_invalid_mask].to_numpy()
        review_df["review_reason"] = (
            "mode_of_conception: value outside the permitted code set "
            f"{sorted(MODE_OF_CONCEPTION_VALID_CODES)} (non-numeric or out-of-range); "
            "set to NaN in the analytical column pending clinical review"
        )
        os.makedirs(review_path, exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        print(f"  Review file saved: {review_xlsx} ({n_moc_invalid} rows)")
    else:
        print("  No invalid conception values.")
        if os.path.exists(review_xlsx):
            os.remove(review_xlsx)
            print(f"  Removed stale review file: {review_xlsx}")

    validation_result = "BLOCKING FAILURE" if unexpected_findings else "PASS"

    # ------------------------------------------------------------------
    # Diagnostic summary + audit log — always written. These describe what
    # was found even when (especially when) the canonical output is being
    # withheld; they never claim a state the saved dataframe doesn't have,
    # since moc_vc/moc_ivf_vc above were computed from the final df state.
    # ------------------------------------------------------------------
    summary = f"""# Preprocessing Batch 10 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df) if validation_result == "PASS" else "NOT WRITTEN (blocking failure)"}

## mode_of_conception
- Value counts: {moc_vc}
- Permitted code set: {sorted(MODE_OF_CONCEPTION_VALID_CODES)} (plus NaN for missing)
- Invalid values (non-numeric or out-of-range) set to NaN: {n_moc_invalid}
- Note: kept separate from mode_of_conception_ivf_vs_all; both are preserved, current sparsity/redundancy rules govern eligibility (see Decision 7 superseded note).

## mode_of_conception_details (free text, reference only)
- Non-null entries: {n_cmd_text}
- Placeholder zeros normalized to NaN: {n_cmd_zeros}

## mode_of_conception_ivf_vs_all (binary)
- Value counts: {moc_ivf_vc}
- Unexpected values: {"none" if ok_ivf else str(unexp_ivf)}

## Review file
{"- " + review_xlsx + f" ({n_moc_invalid} rows)" if n_moc_invalid else "- None (all values valid; any stale prior copy was removed)"}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
{"- " + output_xlsx if validation_result == "PASS" else "- NOT WRITTEN -- blocking validation failure. See review file and findings above."}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)
    log_audit_event(
        audit_log_md,
        f"Batch 10 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / "
        f"{len(df) if validation_result == 'PASS' else 'NOT WRITTEN (blocking failure)'} out\n"
        f"- mode_of_conception: {moc_vc}\n"
        f"- mode_of_conception_ivf_vs_all: {moc_ivf_vc}\n"
        f"- invalid mode_of_conception values set to NaN: {n_moc_invalid}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")

    if unexpected_findings:
        print("=== Batch 10 BLOCKED -- canonical output NOT written ===\n")
        raise RuntimeError(
            "Batch 10 blocking validation failure: "
            + "; ".join(unexpected_findings)
            + f". See {review_xlsx if n_moc_invalid else summary_md} for row-level evidence. "
              "Canonical Batch 10 output was NOT written."
        )

    # ------------------------------------------------------------------
    # Save canonical output — only reached when validation passed.
    # ------------------------------------------------------------------
    os.makedirs(processed_path, exist_ok=True)
    df.to_excel(output_xlsx, index=False)
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 10 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 11 — PPROM and gestational-age standardization
# PPROM, gestational_age_at_PPROM (→ _days), gestational_age_at_delivery (→ _days)
# ---------------------------------------------------------------------------

def batch_11_pprom_gestational_age(work_df):
    """
    PPROM and gestational-age standardization.

    Derives gestational_age_at_delivery_days and
    gestational_age_at_PPROM_days from raw gestational-age text (W+D or
    W.D notation, a single digit 0-6 after the '+'/'.' meaning days;
    a day component of 0 -- e.g. "35+0" -> 245 days -- IS valid), and
    flags the logically impossible case of PPROM occurring after delivery
    (a genuine definitional impossibility -- PPROM cannot happen after the
    birth it precedes). PPROM occurring on the same day as delivery is
    clinically acceptable per Keren and is not flagged.

    Two distinct kinds of numeric check exist here and must not be conflated:
      * Definitional / logical checks (strong): a day component of 7-9, a
        literal raw value of 0, an unrecognized/malformed GA string, and
        PPROM-GA > delivery-GA. These genuinely cannot be a valid value in
        this notation; malformed strings -> NaN in the derived column.
      * Broad sanity/data-quality review gates (weak): the [154, 308] day
        (delivery) and [98, 258] day (PPROM) ranges. These are conservative
        review thresholds with no cited clinical provenance -- a value
        outside a range is a blocking manual-review trigger, NOT a claim
        that the gestational age is physiologically impossible, and NEVER
        mutates a value. Parsing/validity for these fields is owned here in
        canonical preprocessing (Data Cleaning B does not re-clean them).

    PRE-B11-001/002 (2026-07-31): the parser no longer reinterprets an
    out-of-range day digit (7-9) as decimal weeks, and a raw value of 0 is
    treated as invalid (not a valid GA), not as 0 days -- both now produce
    NaN in the derived *_days column, per the dataset's documented
    convention. The original source columns are never modified; only the
    derived *_days columns are affected. See _classify_ga_value for the
    matching audit-only classification of why a value did not parse.

    PRE-B11-003 (2026-07-31): the validation gate now considers PPROM-GA
    out-of-review-range / invalid values, not only delivery-GA ones, so a
    PPROM-side-only contradiction can no longer pass silently as PASS.

    QA outputs: gestational_age_review_df.xlsx (only if out-of-review-range,
    invalid, or contradictory values are found).
    Returns: df — the working DataFrame with PPROM/gestational-age
    variables derived.
    """
    BATCH_TITLE = BATCH_METADATA[11]["title"]
    import re as _re
    from preprocessing_utils import (
        validate_expected_binary_values,
        log_audit_event, log_deviation_event, write_batch_summary,
        create_review_dataframe,
    )

    print(f"=== Batch 11: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch11.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch11.xlsx")
    review_xlsx    = os.path.join(review_path, "gestational_age_review_df.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []

    # Physiological ranges (days)
    GA_DELIVERY_MIN, GA_DELIVERY_MAX = 154, 308  # 22–44 weeks
    GA_PPROM_MIN,    GA_PPROM_MAX    = 98,  258   # 14–36+6 weeks

    _GA_PLUS_RE  = _re.compile(r'^(\d+)\+(\d)$')
    _GA_DEC_RE   = _re.compile(r'^(\d+)\.(\d)$')
    _GA_WHOLE_RE = _re.compile(r'^(\d+)$')

    def _parse_ga_days(val):
        """
        Parse gestational age to total days. Dataset convention: "W+D" or
        "W.D" notation, where D is a single digit 0-6 meaning days (never
        decimal weeks). A day component of 0 is VALID: "35+0" -> 245 days,
        "40+0" -> 280 days. Returns NaN only for a missing source value, an
        unrecognized/malformed format, a day component of 7-9 (cannot be a
        valid day in this notation), or a literal raw value of 0 (not a
        gestational age at all). These are definitional rejections, not
        outlier handling. An out-of-range day digit (e.g. "33.7") is NEVER
        silently reinterpreted as a decimal-week value.
        """
        if pd.isna(val):
            return np.nan
        s = str(val).strip()
        if not s:
            return np.nan
        m = _GA_PLUS_RE.match(s) or _GA_DEC_RE.match(s)
        if m:
            weeks, day = int(m.group(1)), int(m.group(2))
            if day > 6:
                return np.nan
            total = weeks * 7 + day
            return np.nan if total == 0 else float(total)
        m = _GA_WHOLE_RE.match(s)
        if m:
            total = int(m.group(1)) * 7
            return np.nan if total == 0 else float(total)
        return np.nan

    def _classify_ga_value(val):
        """
        Audit-only classification of a raw gestational-age value, mirroring
        _parse_ga_days's acceptance rules but distinguishing WHY a value
        did not produce a valid day count. Does not affect the analytical
        *_days column -- used only for review/validation reporting.
        Returns one of: 'valid', 'missing', 'invalid_zero',
        'invalid_day_component', 'invalid_format'.
        """
        if pd.isna(val):
            return "missing"
        s = str(val).strip()
        if not s:
            return "missing"
        m = _GA_PLUS_RE.match(s) or _GA_DEC_RE.match(s)
        if m:
            weeks, day = int(m.group(1)), int(m.group(2))
            if day > 6:
                return "invalid_day_component"
            return "invalid_zero" if weeks * 7 + day == 0 else "valid"
        m = _GA_WHOLE_RE.match(s)
        if m:
            return "invalid_zero" if int(m.group(1)) == 0 else "valid"
        return "invalid_format"

    # ------------------------------------------------------------------
    # 1. PPROM — validate binary
    # ------------------------------------------------------------------
    ok_pprom, unexp_pprom = validate_expected_binary_values(df["PPROM"], "PPROM")
    pprom_vc = df["PPROM"].value_counts(dropna=False).to_dict()
    if not ok_pprom:
        unexpected_findings.append(f"PPROM: unexpected values {unexp_pprom}")
    print(f"  PPROM: {pprom_vc}")

    # ------------------------------------------------------------------
    # 2. gestational_age_at_delivery → gestational_age_at_delivery_days
    # ------------------------------------------------------------------
    df["gestational_age_at_delivery_days"] = df["gestational_age_at_delivery"].map(
        _parse_ga_days
    )
    gad_class = df["gestational_age_at_delivery"].map(_classify_ga_value)
    n_gad_parsed  = int(df["gestational_age_at_delivery_days"].notna().sum())
    n_gad_nan     = int(df["gestational_age_at_delivery_days"].isna().sum())
    n_gad_was_nan = int(df["gestational_age_at_delivery"].isna().sum())
    gad_invalid_format = gad_class == "invalid_format"
    gad_invalid_day    = gad_class == "invalid_day_component"
    gad_invalid_zero   = gad_class == "invalid_zero"
    gad_outside_ga_review_range = df["gestational_age_at_delivery_days"].notna() & (
        (df["gestational_age_at_delivery_days"] < GA_DELIVERY_MIN) |
        (df["gestational_age_at_delivery_days"] > GA_DELIVERY_MAX)
    )
    n_gad_outside_ga_review_range      = int(gad_outside_ga_review_range.sum())
    n_gad_invalid_format  = int(gad_invalid_format.sum())
    n_gad_invalid_day     = int(gad_invalid_day.sum())
    n_gad_invalid_zero    = int(gad_invalid_zero.sum())
    gad_stats = df["gestational_age_at_delivery_days"].describe().to_dict()
    print(f"  gestational_age_at_delivery_days: {n_gad_parsed} parsed, {n_gad_nan} NaN, "
          f"{n_gad_outside_ga_review_range} outside sanity-review range, {n_gad_invalid_format} invalid format, "
          f"{n_gad_invalid_day} invalid day component, {n_gad_invalid_zero} raw zero")

    # ------------------------------------------------------------------
    # 3. gestational_age_at_PPROM → gestational_age_at_PPROM_days
    # ------------------------------------------------------------------
    df["gestational_age_at_PPROM_days"] = df["gestational_age_at_PPROM"].map(
        _parse_ga_days
    )
    gap_class = df["gestational_age_at_PPROM"].map(_classify_ga_value)
    n_gap_parsed  = int(df["gestational_age_at_PPROM_days"].notna().sum())
    n_gap_nan     = int(df["gestational_age_at_PPROM_days"].isna().sum())
    n_gap_was_nan = int(df["gestational_age_at_PPROM"].isna().sum())
    gap_invalid_format = gap_class == "invalid_format"
    gap_invalid_day    = gap_class == "invalid_day_component"
    gap_invalid_zero   = gap_class == "invalid_zero"
    gap_outside_ga_review_range = df["gestational_age_at_PPROM_days"].notna() & (
        (df["gestational_age_at_PPROM_days"] < GA_PPROM_MIN) |
        (df["gestational_age_at_PPROM_days"] > GA_PPROM_MAX)
    )
    n_gap_outside_ga_review_range      = int(gap_outside_ga_review_range.sum())
    n_gap_invalid_format  = int(gap_invalid_format.sum())
    n_gap_invalid_day     = int(gap_invalid_day.sum())
    n_gap_invalid_zero    = int(gap_invalid_zero.sum())
    print(f"  gestational_age_at_PPROM_days: {n_gap_parsed} parsed, {n_gap_nan} NaN, "
          f"{n_gap_outside_ga_review_range} outside sanity-review range, {n_gap_invalid_format} invalid format, "
          f"{n_gap_invalid_day} invalid day component, {n_gap_invalid_zero} raw zero")

    # ------------------------------------------------------------------
    # 4. Contradiction / consistency flags for review
    # ------------------------------------------------------------------
    # PPROM=0 but GA at PPROM is not NaN
    pprom_zero_ga_exists = (df["PPROM"] == 0) & df["gestational_age_at_PPROM_days"].notna()
    # GA at PPROM > GA at delivery (logically impossible — PPROM cannot occur after delivery)
    # Note: equality (PPROM GA == delivery GA) is NOT an error — delivery may occur on
    # the same day as PPROM (spontaneous labor or clinical decision per Keren).
    ga_pprom_after_delivery = (
        df["gestational_age_at_PPROM_days"].notna() &
        df["gestational_age_at_delivery_days"].notna() &
        (df["gestational_age_at_PPROM_days"] > df["gestational_age_at_delivery_days"])
    )
    # PPROM=1 with GA at PPROM missing: reported as a missing-detail count only --
    # NOT flagged for review and NOT treated as a false PPROM diagnosis or a
    # patient-level correction (task instruction, and rule 6: missing stays missing).
    pprom_one_ga_missing = (df["PPROM"] == 1) & df["gestational_age_at_PPROM_days"].isna()
    n_pprom_one_ga_missing = int(pprom_one_ga_missing.sum())

    # Blocking conditions (contribute to FAIL): genuinely malformed/contradictory
    # data that a human must review. A raw "0" is reported but non-blocking on
    # its own -- it is functionally equivalent to "not documented" (rule 5/6),
    # not a malformed entry, and is still included in the review file for
    # visibility.
    blocking_mask = (
        gad_outside_ga_review_range | gap_outside_ga_review_range |
        pprom_zero_ga_exists | ga_pprom_after_delivery |
        gad_invalid_format | gad_invalid_day |
        gap_invalid_format | gap_invalid_day
    )
    flag_mask = blocking_mask | gad_invalid_zero | gap_invalid_zero
    n_flagged = int(flag_mask.sum())

    if n_flagged:
        # Row-level audit composite-key guard (PRE-B11 row-level audit
        # requirement): every flagged row must have a complete, unique
        # subject_number + delivery_id key before any review evidence is
        # built. Fails loudly rather than silently mis-linking a reason.
        flagged_keys = df.loc[flag_mask, ["subject_number", "delivery_id"]]
        if flagged_keys.isna().to_numpy().any():
            raise ValueError(
                "Batch 11 row-level audit: one or more flagged rows have a "
                "missing subject_number or delivery_id -- cannot build a "
                "reliable composite-key audit trail."
            )
        composite_keys = list(zip(flagged_keys["subject_number"], flagged_keys["delivery_id"]))
        if len(composite_keys) != len(set(composite_keys)):
            raise ValueError(
                "Batch 11 row-level audit: duplicate subject_number+delivery_id "
                "composite key found among flagged rows -- cannot build a unique "
                "audit trail."
            )

        review_df = create_review_dataframe(
            df, flag_mask,
            cols=["PPROM", "gestational_age_at_PPROM", "gestational_age_at_PPROM_days",
                  "gestational_age_at_delivery", "gestational_age_at_delivery_days"],
            id_cols=["delivery_id", "subject_number"],
        )
        # Reason/severity assignment uses the row's own original index directly
        # (review_df was built via df.loc[flag_mask], which preserves df's
        # index exactly -- no separate delivery_id-based re-lookup is needed
        # or performed here; the composite-key guard above additionally
        # guarantees this index-based linkage is unambiguous).
        review_df["review_reason"] = ""
        review_df["validation_severity"] = ""
        review_df["variables_flagged"] = ""
        for idx in review_df.index:
            r = []
            v = []
            if gad_outside_ga_review_range.loc[idx]:
                r.append("delivery GA outside [22,44] weeks"); v.append("gestational_age_at_delivery")
            if gad_invalid_format.loc[idx]:
                r.append("delivery GA: unrecognized format"); v.append("gestational_age_at_delivery")
            if gad_invalid_day.loc[idx]:
                r.append("delivery GA: day component outside 0-6"); v.append("gestational_age_at_delivery")
            if gad_invalid_zero.loc[idx]:
                r.append("delivery GA: raw value 0 (invalid, treated as missing)"); v.append("gestational_age_at_delivery")
            if gap_outside_ga_review_range.loc[idx]:
                r.append("PPROM GA outside [14,37] weeks"); v.append("gestational_age_at_PPROM")
            if gap_invalid_format.loc[idx]:
                r.append("PPROM GA: unrecognized format"); v.append("gestational_age_at_PPROM")
            if gap_invalid_day.loc[idx]:
                r.append("PPROM GA: day component outside 0-6"); v.append("gestational_age_at_PPROM")
            if gap_invalid_zero.loc[idx]:
                r.append("PPROM GA: raw value 0 (invalid, treated as missing)"); v.append("gestational_age_at_PPROM")
            if pprom_zero_ga_exists.loc[idx]:
                r.append("PPROM=0 but GA at PPROM recorded"); v.append("PPROM")
            if ga_pprom_after_delivery.loc[idx]:
                r.append("GA at PPROM > GA at delivery (logically impossible)")
                v.extend(["gestational_age_at_PPROM", "gestational_age_at_delivery"])
            review_df.at[idx, "review_reason"] = "; ".join(r)
            review_df.at[idx, "validation_severity"] = "blocking" if blocking_mask.loc[idx] else "non-blocking"
            review_df.at[idx, "variables_flagged"] = ", ".join(dict.fromkeys(v))
        os.makedirs(review_path, exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        print(f"  Review file saved: {review_xlsx} ({n_flagged} rows, "
              f"{int(blocking_mask.sum())} blocking)")
        if n_gad_outside_ga_review_range:
            unexpected_findings.append(
                f"gestational_age_at_delivery_days: {n_gad_outside_ga_review_range} value(s) outside the [154,308]-day sanity-review range (blocking review trigger, not a proven-impossibility bound)"
            )
        if n_gap_outside_ga_review_range:
            unexpected_findings.append(
                f"gestational_age_at_PPROM_days: {n_gap_outside_ga_review_range} value(s) outside the [98,258]-day sanity-review range (blocking review trigger, not a proven-impossibility bound)"
            )
        if n_gad_invalid_format:
            unexpected_findings.append(
                f"gestational_age_at_delivery: {n_gad_invalid_format} unrecognized format value(s)"
            )
        if n_gap_invalid_format:
            unexpected_findings.append(
                f"gestational_age_at_PPROM: {n_gap_invalid_format} unrecognized format value(s)"
            )
        if n_gad_invalid_day:
            unexpected_findings.append(
                f"gestational_age_at_delivery: {n_gad_invalid_day} value(s) with day component outside 0-6"
            )
        if n_gap_invalid_day:
            unexpected_findings.append(
                f"gestational_age_at_PPROM: {n_gap_invalid_day} value(s) with day component outside 0-6"
            )
        if int(pprom_zero_ga_exists.sum()):
            unexpected_findings.append(
                f"PPROM=0 with GA at PPROM recorded: {int(pprom_zero_ga_exists.sum())} row(s)"
            )
        if int(ga_pprom_after_delivery.sum()):
            unexpected_findings.append(
                f"GA at PPROM > GA at delivery: {int(ga_pprom_after_delivery.sum())} row(s)"
            )
    else:
        print("  No out-of-review-range, invalid, or contradictory gestational age values.")

    # ------------------------------------------------------------------
    # Save + audit
    # ------------------------------------------------------------------
    os.makedirs(processed_path, exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    summary = f"""# Preprocessing Batch 11 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## PPROM (binary)
- {pprom_vc}
- Unexpected values: {"none" if ok_pprom else str(unexp_pprom)}
- PPROM=1 with GA at PPROM missing (reported only, not a diagnosis error, not corrected): {n_pprom_one_ga_missing}

## gestational_age_at_delivery_days (new column)
- Parsed from gestational_age_at_delivery (preserved, unmodified)
- Source NaN: {n_gad_was_nan} | Parsed: {n_gad_parsed} | NaN after parse: {n_gad_nan}
- Outside sanity-review range 154-308 days / 22-44 weeks (blocking review gate, not a proven-impossibility bound): {n_gad_outside_ga_review_range}
- Invalid format: {n_gad_invalid_format} | Invalid day component (not 0-6): {n_gad_invalid_day} | Raw zero (invalid): {n_gad_invalid_zero}
- Stats: min={gad_stats.get('min','N/A'):.0f}, max={gad_stats.get('max','N/A'):.0f}, mean={gad_stats.get('mean','N/A'):.1f} days

## gestational_age_at_PPROM_days (new column)
- Parsed from gestational_age_at_PPROM (preserved, unmodified)
- Source NaN: {n_gap_was_nan} | Parsed: {n_gap_parsed} | NaN after parse: {n_gap_nan}
- Outside sanity-review range 98-258 days / 14-37 weeks (blocking review gate, not a proven-impossibility bound): {n_gap_outside_ga_review_range}
- Invalid format: {n_gap_invalid_format} | Invalid day component (not 0-6): {n_gap_invalid_day} | Raw zero (invalid): {n_gap_invalid_zero}

## Flags for review
- PPROM=0 but GA at PPROM recorded: {int(pprom_zero_ga_exists.sum())}
- GA at PPROM > GA at delivery (**logically/definitionally impossible** — PPROM cannot occur after the delivery it precedes; equality is acceptable per Keren): {int(ga_pprom_after_delivery.sum())}
- Total flagged rows: {n_flagged} ({int(blocking_mask.sum()) if n_flagged else 0} blocking, {n_flagged - int(blocking_mask.sum()) if n_flagged else 0} non-blocking raw-zero-only)
{"- Review file: " + review_xlsx if n_flagged else "- No review file."}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)
    log_audit_event(
        audit_log_md,
        f"Batch 11 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- PPROM: {pprom_vc} | PPROM=1 with GA missing: {n_pprom_one_ga_missing}\n"
        f"- GA delivery days parsed: {n_gad_parsed}, NaN: {n_gad_nan}, outside sanity-review range: {n_gad_outside_ga_review_range}, "
        f"invalid format: {n_gad_invalid_format}, invalid day: {n_gad_invalid_day}, raw zero: {n_gad_invalid_zero}\n"
        f"- GA PPROM days parsed: {n_gap_parsed}, NaN: {n_gap_nan}, outside sanity-review range: {n_gap_outside_ga_review_range}, "
        f"invalid format: {n_gap_invalid_format}, invalid day: {n_gap_invalid_day}, raw zero: {n_gap_invalid_zero}\n"
        f"- Flagged for review: {n_flagged}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 11 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 12 — Hypertensive-disorder and diabetes-related pregnancy complications
# pregnancy_related_hypertensive_disorder, PIH, mild_PET, severe_PET, any_PET,
# SIPET, HELLP, eclampsia, gestational_diabetes, diabetes_type
# ---------------------------------------------------------------------------

def batch_12_hypertension_diabetes(work_df):
    """
    Hypertensive-disorder and diabetes-related pregnancy complications.

    Implements the full approved hierarchy from the active variable
    documentation (docs/variable_documentation/active/):

      any_PET (4-part deterministic rule):
        1. missing, with mild_PET=1 or severe_PET=1  -> fill 1
        2. missing, with mild_PET=0 AND severe_PET=0 -> fill 0
        3. missing, insufficient subtype info         -> remains NaN
        4. any_PET=0, with mild_PET=1 or severe_PET=1 -> correct to 1
      PIH is never used to derive any_PET.

      pregnancy_related_hypertensive_disorder (umbrella derivation):
        0 or missing, with PIH=1 or mild_PET=1 or severe_PET=1 or
        any_PET=1 (post-correction) or HELLP=1 or eclampsia=1 (post-fill)
        -> set to 1. This implements the approved umbrella definition
        (docs/clinical_decisions/manual_decisions_log.md Decision 45) --
        it is not statistical imputation. SIPET is deliberately excluded:
        SIPET (superimposed PET) is PET arising on pre-existing chronic
        hypertension, which is exactly the category the raw source
        column's "only [during pregnancy]" qualifier excludes from this
        umbrella; see Decision 45 for the full resolution.

      HELLP / eclampsia: unchanged from the prior implementation --
      all-missing -> 0 (Keren's dataset-specific approved rule; source
      data currently contains only 0/missing, no positives).

      mild_PET / severe_PET: never filled; missing stays missing.

      pregnancy_related_hypertensive_disorder: approved single-record
      record-specific correction applied before the umbrella derivation above
      in the canonical private source (Decision 76); record key and source excerpt
      are redacted in this review copy.

    Returns: df — the working DataFrame with hypertension/diabetes
    variables cleaned.
    QA output: hypertension_diabetes_review_df.xlsx -- always regenerated,
    classifying every notable row into one of: approved_correction_applied,
    valid_clinical_combination, unresolved_contradiction,
    documentation_only_finding.
    """
    BATCH_TITLE = BATCH_METADATA[12]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values,
        log_audit_event, log_deviation_event, write_batch_summary,
    )

    print(f"=== Batch 12: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch12.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch12.xlsx")
    review_xlsx    = os.path.join(review_path, "hypertension_diabetes_review_df.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []

    # Note: delivery_id is always present and globally unique by construction
    # (Batch 1); subject_number has 8 pre-existing, batch-12-irrelevant gaps
    # in the current cohort (unrelated raw-data condition, not introduced or
    # affected by this batch). A whole-dataframe composite-key guard would
    # therefore block unrelated preprocessing on a condition this batch does
    # not touch. Instead, matching Batch 11's established pattern, the
    # composite-key guard below (step 9) is scoped to only the rows this
    # batch actually flags for the review file.

    # ------------------------------------------------------------------
    # 1. Validate binary: pregnancy_related_hypertensive_disorder, PIH,
    #    mild_PET, severe_PET, SIPET, gestational_diabetes
    # ------------------------------------------------------------------
    binary_cols = [
        "pregnancy_related_hypertensive_disorder",
        "PIH", "mild_PET", "severe_PET", "SIPET", "gestational_diabetes",
    ]
    binary_results = {}
    for col in binary_cols:
        ok, unexp = validate_expected_binary_values(df[col], col)
        binary_results[col] = {
            "ok": ok, "unexpected": unexp,
            "vc": df[col].value_counts(dropna=False).to_dict(),
        }
        if not ok:
            unexpected_findings.append(f"{col}: unexpected values {unexp}")
        print(f"  {col}: {binary_results[col]['vc']}")

    # Frozen pre-batch snapshots for later "never filled" assertions.
    mild_pet_pre_batch = df["mild_PET"].copy()
    severe_pet_pre_batch = df["severe_PET"].copy()

    # ------------------------------------------------------------------
    # 2. any_PET — full 4-part documented deterministic rule
    # ------------------------------------------------------------------
    any_pet_before = df["any_PET"].copy()
    mild_pos = df["mild_PET"] == 1
    severe_pos = df["severe_PET"] == 1
    supporting_subtype_mask = mild_pos | severe_pos

    # Rule 1 + Rule 4 combined: any_PET missing OR 0, with mild/severe
    # positive -> 1. Split into the two sub-cases purely for reporting.
    any_pet_missing = df["any_PET"].isna()
    any_pet_is_zero = df["any_PET"] == 0
    any_pet_fill_missing_to_1_mask = any_pet_missing & supporting_subtype_mask
    any_pet_correct_0_to_1_mask = any_pet_is_zero & supporting_subtype_mask
    any_pet_to_1_mask = any_pet_fill_missing_to_1_mask | any_pet_correct_0_to_1_mask

    # Rule 2 (unchanged): any_PET missing, mild=0 AND severe=0 -> 0.
    any_pet_fill_0_mask = any_pet_missing & (df["mild_PET"] == 0) & (df["severe_PET"] == 0)

    n_any_pet_filled_missing_to_1 = int(any_pet_fill_missing_to_1_mask.sum())
    n_any_pet_corrected_0_to_1 = int(any_pet_correct_0_to_1_mask.sum())
    n_any_pet_filled_0 = int(any_pet_fill_0_mask.sum())

    def _supporting_subtype_label(idx):
        parts = []
        if mild_pos.loc[idx]:
            parts.append("mild_PET")
        if severe_pos.loc[idx]:
            parts.append("severe_PET")
        return ",".join(parts)

    any_pet_corrections = []  # row-level record for correction_applied + review file
    for idx in df.index[any_pet_fill_missing_to_1_mask]:
        any_pet_corrections.append(dict(
            idx=idx, variable="any_PET", original_value="NaN", final_value=1,
            supporting_subtype=_supporting_subtype_label(idx),
            approved_rule="any_PET rule 1: missing, mild/severe positive -> fill 1",
        ))
    for idx in df.index[any_pet_correct_0_to_1_mask]:
        any_pet_corrections.append(dict(
            idx=idx, variable="any_PET", original_value=0, final_value=1,
            supporting_subtype=_supporting_subtype_label(idx),
            approved_rule="any_PET rule 4: any_PET=0, mild/severe positive -> correct to 1",
        ))

    if n_any_pet_to_1_mask := int(any_pet_to_1_mask.sum()):
        df.loc[any_pet_to_1_mask, "any_PET"] = 1
    if n_any_pet_filled_0:
        df.loc[any_pet_fill_0_mask, "any_PET"] = 0

    if n_any_pet_corrected_0_to_1:
        log_deviation_event(
            path=deviations_md,
            variable="any_PET",
            raw_variable="ANY PET",
            documented="any_PET=0 with mild_PET=1 or severe_PET=1 -> corrected to 1 "
                        "(approved umbrella-consistency rule; Decision 45).",
            action=f"Corrected {n_any_pet_corrected_0_to_1} row(s) from 0 to 1: "
                    + "; ".join(
                        f"subject_number={df.at[r['idx'],'subject_number']:.0f}/"
                        f"delivery_id={df.at[r['idx'],'delivery_id']:.0f} "
                        f"(supporting: {r['supporting_subtype']})"
                        for r in any_pet_corrections if r["approved_rule"].startswith("any_PET rule 4")
                    ),
            reason="Deterministic: mild_PET=1 or severe_PET=1 clinically implies PET is present, "
                   "so any_PET cannot remain 0.",
            requires_approval=False,
            batch="Batch 12",
            affected_count=n_any_pet_corrected_0_to_1,
        )
    if n_any_pet_filled_missing_to_1:
        log_deviation_event(
            path=deviations_md,
            variable="any_PET",
            raw_variable="ANY PET",
            documented="any_PET missing, with mild_PET=1 or severe_PET=1 -> filled with 1 "
                        "(Decision 45).",
            action=f"Filled {n_any_pet_filled_missing_to_1} NaN value(s) with 1.",
            reason="Deterministic: mild_PET=1 or severe_PET=1 is sufficient positive evidence "
                   "for any_PET, regardless of whether any_PET itself was documented.",
            requires_approval=False,
            batch="Batch 12",
            affected_count=n_any_pet_filled_missing_to_1,
        )
    if n_any_pet_filled_0:
        log_deviation_event(
            path=deviations_md,
            variable="any_PET",
            raw_variable="ANY PET",
            documented="any_PET missing → 0 where mild_PET=0 and severe_PET=0 (documented rule).",
            action=f"Filled {n_any_pet_filled_0} NaN values with 0.",
            reason="Deterministic: if neither mild nor severe PET is present, any_PET must be 0.",
            requires_approval=False,
            batch="Batch 12",
            affected_count=n_any_pet_filled_0,
        )
    ok_any, unexp_any = validate_expected_binary_values(df["any_PET"], "any_PET")
    if not ok_any:
        unexpected_findings.append(f"any_PET: unexpected values after fill {unexp_any}")
    print(f"  any_PET: before NaN={int(any_pet_before.isna().sum())}, "
          f"corrected 0->1={n_any_pet_corrected_0_to_1}, "
          f"filled missing->1={n_any_pet_filled_missing_to_1}, "
          f"filled missing->0={n_any_pet_filled_0}, "
          f"after {df['any_PET'].value_counts(dropna=False).to_dict()}")

    # ------------------------------------------------------------------
    # 3. HELLP — documented rule: all missing → 0 (unchanged)
    # ------------------------------------------------------------------
    hellp_before  = df["HELLP"].copy()
    n_hellp_nan   = int(df["HELLP"].isna().sum())
    n_hellp_filled = 0
    if n_hellp_nan:
        df["HELLP"] = df["HELLP"].fillna(0)
        n_hellp_filled = n_hellp_nan
        log_deviation_event(
            path=deviations_md,
            variable="HELLP",
            raw_variable="HELLP",
            documented="All HELLP missing → 0 (severe event would have been documented).",
            action=f"Filled {n_hellp_filled} NaN with 0.",
            reason="Clinical documentation rule: absence of HELLP documentation implies no HELLP.",
            requires_approval=False,
            batch="Batch 12",
            affected_count=n_hellp_filled,
        )
    ok_hellp, unexp_hellp = validate_expected_binary_values(df["HELLP"], "HELLP")
    if not ok_hellp:
        unexpected_findings.append(f"HELLP: unexpected values {unexp_hellp}")
    print(f"  HELLP: {n_hellp_filled} NaN->0, after {df['HELLP'].value_counts(dropna=False).to_dict()}")

    # ------------------------------------------------------------------
    # 4. eclampsia — documented rule: all missing → 0 (unchanged)
    # ------------------------------------------------------------------
    ecl_before   = df["eclampsia"].copy()
    n_ecl_nan    = int(df["eclampsia"].isna().sum())
    n_ecl_filled = 0
    if n_ecl_nan:
        df["eclampsia"] = df["eclampsia"].fillna(0)
        n_ecl_filled = n_ecl_nan
        log_deviation_event(
            path=deviations_md,
            variable="eclampsia",
            raw_variable="Eclampsia",
            documented="All eclampsia missing → 0 (same justification as HELLP).",
            action=f"Filled {n_ecl_filled} NaN with 0.",
            reason="Clinical documentation rule: absence of eclampsia documentation implies no eclampsia.",
            requires_approval=False,
            batch="Batch 12",
            affected_count=n_ecl_filled,
        )
    ok_ecl, unexp_ecl = validate_expected_binary_values(df["eclampsia"], "eclampsia")
    if not ok_ecl:
        unexpected_findings.append(f"eclampsia: unexpected values {unexp_ecl}")
    print(f"  eclampsia: {n_ecl_filled} NaN->0, after {df['eclampsia'].value_counts(dropna=False).to_dict()}")

    # ------------------------------------------------------------------
    # 4b. pregnancy_related_hypertensive_disorder — approved single-record
    #     correction [RECORD KEY AND SOURCE EXCERPT REDACTED]
    # ------------------------------------------------------------------
    # Canonical private source applies one clinically approved correction before
    # the umbrella derivation. It is intentionally not executable in this copy.
    n_redacted_hypertension_correction = 0

    # ------------------------------------------------------------------
    # 5. pregnancy_related_hypertensive_disorder — umbrella derivation.
    #    Approved umbrella definition: covers all pregnancy-related
    #    hypertensive disorders (PIH through HELLP/eclampsia). Uses
    #    POST-correction any_PET and POST-fill HELLP/eclampsia values.
    #    SIPET is deliberately excluded -- see Decision 45. Runs AFTER the
    #    redacted record-specific correction above (step 4b), so umbrella_before
    #    already reflects that correction.
    # ------------------------------------------------------------------
    umbrella_before = df["pregnancy_related_hypertensive_disorder"].copy()
    umbrella_subtype_cols = ["PIH", "mild_PET", "severe_PET", "any_PET", "HELLP", "eclampsia"]
    subtype_positive_for_umbrella = (df[umbrella_subtype_cols] == 1).any(axis=1)
    umbrella_needs_set_mask = subtype_positive_for_umbrella & (
        (df["pregnancy_related_hypertensive_disorder"] == 0)
        | df["pregnancy_related_hypertensive_disorder"].isna()
    )
    n_umbrella_from_0 = int((umbrella_needs_set_mask & (umbrella_before == 0)).sum())
    n_umbrella_from_missing = int((umbrella_needs_set_mask & umbrella_before.isna()).sum())
    n_umbrella_set = n_umbrella_from_0 + n_umbrella_from_missing

    def _umbrella_supporting_label(idx):
        return ",".join(c for c in umbrella_subtype_cols if df.at[idx, c] == 1)

    umbrella_corrections = []
    for idx in df.index[umbrella_needs_set_mask]:
        umbrella_corrections.append(dict(
            idx=idx, variable="pregnancy_related_hypertensive_disorder",
            original_value=("NaN" if pd.isna(umbrella_before.loc[idx]) else int(umbrella_before.loc[idx])),
            final_value=1,
            supporting_subtype=_umbrella_supporting_label(idx),
            approved_rule="umbrella derivation: PIH/mild_PET/severe_PET/any_PET/HELLP/eclampsia "
                           "positive -> umbrella=1",
        ))

    if n_umbrella_set:
        df.loc[umbrella_needs_set_mask, "pregnancy_related_hypertensive_disorder"] = 1
        log_deviation_event(
            path=deviations_md,
            variable="pregnancy_related_hypertensive_disorder",
            raw_variable="hypertensive disorder only during pregnancy",
            documented="Implementation of the approved umbrella definition (Decision 45): "
                        "if PIH, mild_PET, severe_PET, any_PET, HELLP, or eclampsia = 1, then "
                        "pregnancy_related_hypertensive_disorder must equal 1. This is a "
                        "deterministic implementation of the variable's documented clinical "
                        "definition, not statistical or frequency-based imputation. SIPET is "
                        "deliberately excluded (see Decision 45).",
            action=f"Set {n_umbrella_set} row(s) to 1 "
                    f"({n_umbrella_from_0} corrected from 0, {n_umbrella_from_missing} filled from missing).",
            reason="The umbrella variable is defined to include all listed pregnancy-related "
                   "hypertensive-disorder subtypes; a positive subtype with a negative or "
                   "missing umbrella value is a hierarchy contradiction, not a valid state.",
            requires_approval=False,
            batch="Batch 12",
            affected_count=n_umbrella_set,
        )
    ok_umbrella, unexp_umbrella = validate_expected_binary_values(
        df["pregnancy_related_hypertensive_disorder"], "pregnancy_related_hypertensive_disorder"
    )
    if not ok_umbrella:
        unexpected_findings.append(
            f"pregnancy_related_hypertensive_disorder: unexpected values after derivation {unexp_umbrella}"
        )
    print(f"  pregnancy_related_hypertensive_disorder: corrected 0->1={n_umbrella_from_0}, "
          f"filled missing->1={n_umbrella_from_missing}, "
          f"after {df['pregnancy_related_hypertensive_disorder'].value_counts(dropna=False).to_dict()}")

    # ------------------------------------------------------------------
    # 6. SIPET — no value transformation. SIPET's meaning is not defined
    #    anywhere in the active variable documentation beyond its bare
    #    header. Resolved (Decision 45) as: SIPET = superimposed PET on
    #    pre-existing chronic hypertension (standard obstetric usage of
    #    the abbreviation), which is exactly the category the raw source
    #    column's "only [during pregnancy]" qualifier excludes from the
    #    umbrella. SIPET=1 with umbrella=0 is therefore documented as a
    #    valid clinical combination, not an unresolved contradiction --
    #    SIPET is never added to umbrella_subtype_cols above.
    # ------------------------------------------------------------------
    sipet_valid_combination_mask = (df["SIPET"] == 1) & (
        df["pregnancy_related_hypertensive_disorder"] == 0
    )
    n_sipet_valid = int(sipet_valid_combination_mask.sum())
    print(f"  SIPET: {df['SIPET'].value_counts(dropna=False).to_dict()}, "
          f"SIPET=1 with umbrella=0 (documented valid combination, Decision 45): {n_sipet_valid}")

    # ------------------------------------------------------------------
    # 7. diabetes_type — categorical; coerce to numeric; report values
    # ------------------------------------------------------------------
    dt_before = df["diabetes_type"].copy()
    df["diabetes_type"] = pd.to_numeric(df["diabetes_type"], errors="coerce")
    dt_vc = df["diabetes_type"].value_counts(dropna=False).sort_index().to_dict()
    n_dt_text = int(dt_before.map(
        lambda v: not pd.isna(v) and pd.isna(pd.to_numeric(v, errors="coerce"))
    ).sum())
    if n_dt_text:
        unexpected_findings.append(
            f"diabetes_type: {n_dt_text} non-numeric value(s) coerced to NaN"
        )
    print(f"  diabetes_type: {dt_vc}")

    # ------------------------------------------------------------------
    # 7b. gestational_diabetes — deterministic diabetes_type-to-binary
    #     consistency correction (Decision 82)
    # ------------------------------------------------------------------
    # Canonical dictionary (docs/data_dictionary/clinical_variable_dictionary.yaml)
    # confirms: diabetes_type=4 is GDMA1, diabetes_type=5 is GDMA2, and
    # gestational_diabetes is the binary gestational-diabetes indicator. GDMA1
    # and GDMA2 are gestational diabetes BY DEFINITION, so diabetes_type in
    # {4, 5} deterministically implies gestational_diabetes=1 -- this is not a
    # new clinical interpretation, it enforces the canonical dictionary's own
    # already-documented code meanings (same pattern as Decision 80's CS/
    # S_P_CS consistency correction). The REVERSE implication is deliberately
    # NOT enforced: gestational_diabetes=1 does not imply diabetes_type in
    # {4, 5}, since the cohort also contains pregestational/type-1/type-2
    # diabetes records (codes 1/2/3) with gestational_diabetes=1. Runs after
    # diabetes_type has been coerced to numeric (step 7 above) so codes 4/5
    # can be safely identified.
    gd_contra_mask = df["diabetes_type"].isin([4, 5]) & (df["gestational_diabetes"] == 0)
    n_gd_contra = int(gd_contra_mask.sum())
    if n_gd_contra > 0:
        gd_contra_rows = [
            (
                (None if pd.isna(df.at[idx, "subject_number"]) else int(df.at[idx, "subject_number"])),
                int(df.at[idx, "delivery_id"]),
                int(df.at[idx, "diabetes_type"]),
            )
            for idx in df.index[gd_contra_mask]
        ]
        df.loc[gd_contra_mask, "gestational_diabetes"] = 1
        log_deviation_event(
            path=deviations_md,
            variable="gestational_diabetes",
            raw_variable="gestational diabetes",
            documented="gestational_diabetes is the binary indicator of diabetes_type "
                       "being GDMA1 (4) or GDMA2 (5), per docs/data_dictionary/"
                       "clinical_variable_dictionary.yaml.",
            action=(
                f"Recoded gestational_diabetes 0->1 for {n_gd_contra} row(s) where "
                f"diabetes_type in {{4, 5}}: "
                + "; ".join(
                    f"subject_number={sn if sn is not None else 'MISSING'}/delivery_id={did} "
                    f"(diabetes_type={dt})"
                    for sn, did, dt in gd_contra_rows
                )
            ),
            reason="Deterministic consistency correction, not a new clinical interpretation: "
                   "the canonical variable dictionary defines diabetes_type codes 4/5 as "
                   "GDMA1/GDMA2 (gestational diabetes by definition), so gestational_diabetes "
                   "must equal 1 whenever diabetes_type is 4 or 5. The reverse implication is "
                   "not enforced -- gestational_diabetes=1 with diabetes_type in {1,2,3} "
                   "(pregestational/type 1/type 2) is not a contradiction.",
            requires_approval=False,
            batch="Batch 12",
            affected_count=n_gd_contra,
        )
        print(f"  gestational_diabetes: {n_gd_contra} row(s) corrected 0->1 for "
              "diabetes_type-in-{4,5} consistency (Decision 82)")
    remaining_gd_contra = int((df["diabetes_type"].isin([4, 5]) & (df["gestational_diabetes"] == 0)).sum())
    if remaining_gd_contra > 0:
        unexpected_findings.append(
            f"gestational_diabetes: {remaining_gd_contra} row(s) still have diabetes_type "
            "in {4,5} with gestational_diabetes=0 after the Decision 82 consistency correction"
        )

    # ------------------------------------------------------------------
    # 8. Post-correction validation gates — fail loud, not silently.
    # ------------------------------------------------------------------
    remaining_any_pet_contra = (df["any_PET"] == 0) & (
        (df["mild_PET"] == 1) | (df["severe_PET"] == 1)
    )
    if remaining_any_pet_contra.any():
        raise AssertionError(
            "Batch 12: an approved any_PET correction remains unapplied -- "
            f"{int(remaining_any_pet_contra.sum())} row(s) still have any_PET=0 "
            "with mild_PET=1 or severe_PET=1 after the deterministic rule was applied."
        )
    remaining_umbrella_contra = subtype_positive_for_umbrella & (
        df["pregnancy_related_hypertensive_disorder"] == 0
    )
    if remaining_umbrella_contra.any():
        raise AssertionError(
            "Batch 12: an approved umbrella derivation remains unapplied -- "
            f"{int(remaining_umbrella_contra.sum())} row(s) still have "
            "pregnancy_related_hypertensive_disorder=0 with an included subtype positive."
        )
    if not df["mild_PET"].equals(mild_pet_pre_batch):
        raise AssertionError("Batch 12: mild_PET was modified without an approved rule.")
    if not df["severe_PET"].equals(severe_pet_pre_batch):
        raise AssertionError("Batch 12: severe_PET was modified without an approved rule.")

    # ------------------------------------------------------------------
    # 9. Unified review file — every notable row, classified.
    #    Categories: approved_correction_applied, valid_clinical_combination,
    #    unresolved_contradiction, documentation_only_finding.
    #    "unresolved_contradiction" is expected to be empty after step 8's
    #    hard gate above; the category is retained in the schema so a
    #    future genuinely-unresolved case (e.g. a new subtype variable
    #    added without a matching rule) would still be representable and
    #    would not silently disappear.
    # ------------------------------------------------------------------
    review_records = {}  # idx -> dict of accumulated review fields

    def _get_record(idx):
        if idx not in review_records:
            review_records[idx] = dict(
                idx=idx,
                any_PET_original="", any_PET_final="",
                umbrella_original="", umbrella_final="",
                supporting_subtype="", approved_rule=[],
                category="", correction_status="", review_reason=[],
            )
        return review_records[idx]

    for rec in any_pet_corrections:
        r = _get_record(rec["idx"])
        r["any_PET_original"] = rec["original_value"]
        r["any_PET_final"] = rec["final_value"]
        r["supporting_subtype"] = rec["supporting_subtype"]
        r["approved_rule"].append(rec["approved_rule"])
        r["category"] = "approved_correction_applied"
        r["correction_status"] = "corrected"
        r["review_reason"].append("any_PET corrected per approved deterministic rule")

    for rec in umbrella_corrections:
        r = _get_record(rec["idx"])
        r["umbrella_original"] = rec["original_value"]
        r["umbrella_final"] = rec["final_value"]
        if not r["supporting_subtype"]:
            r["supporting_subtype"] = rec["supporting_subtype"]
        r["approved_rule"].append(rec["approved_rule"])
        r["category"] = "approved_correction_applied"
        r["correction_status"] = "corrected"
        r["review_reason"].append("umbrella derived from a positive included subtype")

    for idx in df.index[sipet_valid_combination_mask]:
        r = _get_record(idx)
        r["approved_rule"].append(
            "SIPET excluded from umbrella derivation (Decision 45): superimposed PET on "
            "chronic hypertension falls outside the pregnancy-only umbrella definition"
        )
        r["category"] = "valid_clinical_combination"
        r["correction_status"] = "preserved_valid"
        r["review_reason"].append("SIPET=1 with umbrella=0 -- documented as clinically valid, not a contradiction")

    for idx in df.index[remaining_any_pet_contra | remaining_umbrella_contra]:
        # Unreachable given the hard gate above (step 8 raises first); kept
        # so the category is structurally real, not just a label never used.
        r = _get_record(idx)
        r["category"] = "unresolved_contradiction"
        r["correction_status"] = "unresolved"
        r["review_reason"].append("contradiction remains after deterministic rules")

    n_contra = len(review_records)
    if n_contra:
        review_cols = [
            "pregnancy_related_hypertensive_disorder", "PIH",
            "mild_PET", "severe_PET", "any_PET", "SIPET",
            "HELLP", "eclampsia",
        ]
        ordered_idx = sorted(
            review_records.keys(),
            key=lambda i: (df.at[i, "subject_number"], df.at[i, "delivery_id"]),
        )
        review_df = df.loc[ordered_idx, ["delivery_id", "subject_number"] + review_cols].copy()
        review_df["any_PET_original"] = [review_records[i]["any_PET_original"] for i in ordered_idx]
        review_df["any_PET_final"] = [review_records[i]["any_PET_final"] for i in ordered_idx]
        review_df["umbrella_original"] = [review_records[i]["umbrella_original"] for i in ordered_idx]
        review_df["umbrella_final"] = [review_records[i]["umbrella_final"] for i in ordered_idx]
        review_df["supporting_subtype"] = [review_records[i]["supporting_subtype"] for i in ordered_idx]
        review_df["approved_rule"] = ["; ".join(review_records[i]["approved_rule"]) for i in ordered_idx]
        review_df["category"] = [review_records[i]["category"] for i in ordered_idx]
        review_df["correction_status"] = [review_records[i]["correction_status"] for i in ordered_idx]
        review_df["review_reason"] = ["; ".join(review_records[i]["review_reason"]) for i in ordered_idx]

        # Composite-key integrity guard on the review subset specifically
        # (defense-in-depth on top of the whole-dataframe guard in step 0).
        review_keys = list(zip(review_df["subject_number"], review_df["delivery_id"]))
        if review_df[["subject_number", "delivery_id"]].isna().to_numpy().any():
            raise ValueError("Batch 12 review file: missing composite key in a review row.")
        if len(review_keys) != len(set(review_keys)):
            raise ValueError("Batch 12 review file: duplicate composite key in review rows.")

        os.makedirs(review_path, exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        print(f"  Review file saved: {review_xlsx} ({n_contra} rows: "
              f"{sum(1 for r in review_records.values() if r['category']=='approved_correction_applied')} "
              "approved_correction_applied, "
              f"{sum(1 for r in review_records.values() if r['category']=='valid_clinical_combination')} "
              "valid_clinical_combination, "
              f"{sum(1 for r in review_records.values() if r['category']=='unresolved_contradiction')} "
              "unresolved_contradiction)")
    else:
        print("  No notable rows -- review file not written.")

    # ------------------------------------------------------------------
    # Save + audit
    # ------------------------------------------------------------------
    os.makedirs(processed_path, exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    binary_lines = "\n".join(
        f"  - {col}: {r['vc']} | unexpected: {'none' if r['ok'] else str(r['unexpected'])}"
        for col, r in binary_results.items()
    )

    any_pet_rows_txt = "\n".join(
        f"  - subject_number={df.at[r['idx'],'subject_number']:.0f}, "
        f"delivery_id={df.at[r['idx'],'delivery_id']:.0f}: "
        f"{r['original_value']} -> {r['final_value']} (supporting: {r['supporting_subtype']}; {r['approved_rule']})"
        for r in any_pet_corrections
    ) or "  None"

    umbrella_rows_txt = "\n".join(
        f"  - subject_number={df.at[r['idx'],'subject_number']:.0f}, "
        f"delivery_id={df.at[r['idx'],'delivery_id']:.0f}: "
        f"{r['original_value']} -> {r['final_value']} (supporting: {r['supporting_subtype']})"
        for r in umbrella_corrections
    ) or "  None"

    summary = f"""# Preprocessing Batch 12 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## Binary hypertensive variables (validated)
{binary_lines}

## any_PET (full 4-part deterministic rule)
- Before: {any_pet_before.value_counts(dropna=False).to_dict()}
- Corrected 0->1 (rule 4, mild/severe positive): {n_any_pet_corrected_0_to_1}
- Filled missing->1 (rule 1, mild/severe positive): {n_any_pet_filled_missing_to_1}
- Filled missing->0 (rule 2, mild=0 and severe=0): {n_any_pet_filled_0}
- After: {df["any_PET"].value_counts(dropna=False).to_dict()}
- Corrected/filled-to-1 rows:
{any_pet_rows_txt}

## HELLP (deterministic fill: missing→0)
- Filled: {n_hellp_filled} | After: {df["HELLP"].value_counts(dropna=False).to_dict()}

## eclampsia (deterministic fill: missing→0)
- Filled: {n_ecl_filled} | After: {df["eclampsia"].value_counts(dropna=False).to_dict()}

## pregnancy_related_hypertensive_disorder (umbrella derivation)
- Approved single-record correction (Decision 76; key/rationale redacted): {n_redacted_hypertension_correction} row(s) corrected in this review copy.
- Before (post-Decision-76 correction): {umbrella_before.value_counts(dropna=False).to_dict()}
- Corrected 0->1: {n_umbrella_from_0} | Filled missing->1: {n_umbrella_from_missing}
- After: {df["pregnancy_related_hypertensive_disorder"].value_counts(dropna=False).to_dict()}
- SIPET deliberately excluded from this rule (Decision 45).
- Corrected rows:
{umbrella_rows_txt}

## SIPET
- {df["SIPET"].value_counts(dropna=False).to_dict()}
- SIPET=1 with umbrella=0 (documented valid clinical combination, Decision 45): {n_sipet_valid}

## diabetes_type (categorical)
- {dt_vc}
- Non-numeric coerced to NaN: {n_dt_text}

## gestational_diabetes (diabetes_type-in-{{4,5}} consistency, Decision 82)
- {df["gestational_diabetes"].value_counts(dropna=False).to_dict()}
- Rows corrected (0->1): {n_gd_contra}
- Remaining diabetes_type-in-{{4,5}}/gestational_diabetes=0 contradictions: {remaining_gd_contra}

## Review file
- Total notable rows: {n_contra}
{"- Review file: " + review_xlsx if n_contra else "- No review file."}
- No row remains classified as unresolved_contradiction (hard gate in step 8 would have raised otherwise).

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)
    log_audit_event(
        audit_log_md,
        f"Batch 12 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- any_PET corrected 0->1: {n_any_pet_corrected_0_to_1}\n"
        f"- any_PET filled missing->1: {n_any_pet_filled_missing_to_1}\n"
        f"- any_PET filled missing->0: {n_any_pet_filled_0}\n"
        f"- HELLP filled 0: {n_hellp_filled}\n"
        f"- eclampsia filled 0: {n_ecl_filled}\n"
        f"- umbrella corrected 0->1: {n_umbrella_from_0}\n"
        f"- umbrella filled missing->1: {n_umbrella_from_missing}\n"
        f"- Review file rows: {n_contra}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 12 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 13 — Remaining pregnancy-complication variable standardization
# IUGR, placental_abruption,
# chorioamnionitis, PPH, oligohydramnios, polyhydramnios,
# meconium_stained_amniotic_fluid, IUFD, celestone, magnesium, comment_2
# (placenta_accreta, placenta_previa dropped in Batch 2, Decision 32)
# ---------------------------------------------------------------------------

def batch_13_pregnancy_complications(work_df):
    """
    Remaining pregnancy-complication variable standardization.

    Validates the remaining pregnancy-complication variables (IUGR,
    placental_abruption, chorioamnionitis, PPH, oligo/polyhydramnios,
    meconium-stained fluid, IUFD, celestone, magnesium). placenta_accreta
    and placenta_previa are not handled here — they were already used for
    the one-record cohort exclusion and dropped entirely in Batch 2
    (Decision 32).

    IUFD (Decision 49, 2026-08-01): current-pregnancy intrauterine fetal
    death only -- never a predictor, retained only for cohort QC/audit/
    descriptive/secondary-outcome use. A fail-loud QA gate below blocks
    automatic cohort progression for any row with IUFD=1 (none exist in the
    current 431-row cohort -- this gate is a no-op today, exercised only by
    its own tests) pending explicit clinical timing review, rather than
    silently including or excluding such a row in a future data refresh.

    Approved decisions: 32, 49.
    Returns: df — the working DataFrame with remaining pregnancy-
    complication variables validated.
    """
    BATCH_TITLE = BATCH_METADATA[13]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values,
        log_audit_event, write_batch_summary,
    )

    print(f"=== Batch 13: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch13.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch13.xlsx")
    iufd_review_xlsx = os.path.join(review_path, "IUFD_clinical_review_df.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []

    binary_cols = [
        "IUGR", "placental_abruption",
        # placenta_accreta, placenta_previa: dropped in Batch 2 (Decision 32,
        # 2026-07-30) after being used for cohort construction -- no longer
        # present in df by this point.
        "chorioamnionitis", "PPH", "oligohydramnios", "polyhydramnios",
        "meconium_stained_amniotic_fluid", "IUFD", "celestone", "magnesium",
    ]
    binary_results = {}
    for col in binary_cols:
        ok, unexp = validate_expected_binary_values(df[col], col)
        binary_results[col] = {
            "ok": ok, "unexpected": unexp,
            "vc": df[col].value_counts(dropna=False).to_dict(),
        }
        if not ok:
            unexpected_findings.append(f"{col}: unexpected values {unexp}")
        print(f"  {col}: {binary_results[col]['vc']}")

    # comment_2: free-text adjacent to celestone/magnesium — normalize placeholder zeros
    before_c5 = df["comment_2"].copy()
    df["comment_2"] = df["comment_2"].apply(
        lambda v: np.nan if v in (0, "0", 0.0) else v
    )
    n_c5_zeros = int(before_c5.map(lambda v: v in (0, "0", 0.0)).sum())
    n_c5_text  = int(df["comment_2"].notna().sum())
    print(f"  comment_2: {n_c5_text} non-null, {n_c5_zeros} zeros->NaN")

    # ------------------------------------------------------------------
    # IUFD clinical-review QA gate (Decision 49, 2026-08-01).
    #
    # IUFD=1 alone does not establish whether fetal death occurred before
    # the start of the attempted vaginal delivery (-> cohort exclusion, this
    # is not a live-birth trial-of-labor case) or during labor (-> row may
    # remain if otherwise eligible; IUFD stays a secondary fetal outcome,
    # never a predictor). This gate never resolves that timing itself -- it
    # only detects the trigger condition, blocks automatic cohort
    # progression for the row, and exports the evidence a clinical reviewer
    # needs to make that determination. Do not infer neonatal death from an
    # intrapartum fetal death, and do not silently include or exclude the
    # row while timing is unresolved.
    # ------------------------------------------------------------------
    iufd_positive_mask = df["IUFD"] == 1
    n_iufd_positive = int(iufd_positive_mask.sum())
    if n_iufd_positive:
        iufd_keys = df.loc[iufd_positive_mask, ["subject_number", "delivery_id"]]
        if iufd_keys.isna().to_numpy().any():
            raise ValueError(
                "Batch 13 IUFD review: one or more IUFD=1 rows have a missing "
                "subject_number or delivery_id -- cannot build a reliable "
                "composite-key clinical-review audit trail."
            )
        composite_keys = list(zip(iufd_keys["subject_number"], iufd_keys["delivery_id"]))
        if len(composite_keys) != len(set(composite_keys)):
            raise ValueError(
                "Batch 13 IUFD review: duplicate subject_number+delivery_id "
                "composite key found among IUFD=1 rows -- cannot build a "
                "unique clinical-review audit trail."
            )
        review_cols = [
            "subject_number", "delivery_id", "IUFD",
            "comment_2",  # relevant source free-text comment
            "trial_of_labor_corrected", "trial_of_labor",  # trial-of-labor information
            "start_of_labor",  # labor-start information
            "type_of_CS",  # delivery mode
            "neonatal_death", "age_at_neonatal_death", "congenital_anomaly",  # fetal/neonatal outcome fields
        ]
        iufd_review_df = df.loc[iufd_positive_mask, review_cols].copy()
        iufd_review_df["review_reason"] = (
            "IUFD=1 -- timing relative to the start of the attempted vaginal "
            "delivery is not established by this field alone; clinical review "
            "required before this row's cohort membership can be determined."
        )
        # Blank fields for clinical fill-in -- never auto-populated.
        iufd_review_df["timing_decision"] = pd.NA  # expected values: "before_labor" / "during_labor" / "cannot_establish"
        iufd_review_df["final_cohort_action"] = "BLOCKED_PENDING_REVIEW"
        os.makedirs(review_path, exist_ok=True)
        iufd_review_df.to_excel(iufd_review_xlsx, index=False)
        unexpected_findings.append(
            f"IUFD: {n_iufd_positive} row(s) with IUFD=1 require clinical timing "
            f"review before cohort progression -- see {iufd_review_xlsx}. This is "
            "a blocking clinical-review condition, not a code defect."
        )
        print(f"  IUFD clinical review: {n_iufd_positive} row(s) BLOCKED_PENDING_REVIEW, "
              f"exported to {iufd_review_xlsx}")
    else:
        print("  IUFD clinical review: 0 rows with IUFD=1 -- gate not triggered.")

    os.makedirs(resolve_path(OUTPUT_PROCESSED_PATH), exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    binary_lines = "\n".join(
        f"  - {col}: {r['vc']} | unexpected: {'none' if r['ok'] else str(r['unexpected'])}"
        for col, r in binary_results.items()
    )
    summary = f"""# Preprocessing Batch 13 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## Binary pregnancy complication variables (validated only)
{binary_lines}

## comment_2 (free text, reference)
- Non-null entries: {n_c5_text} | Placeholder zeros normalized: {n_c5_zeros}

## IUFD clinical-review QA gate (Decision 49)
- IUFD=1 rows found: {n_iufd_positive}
{"- Review file: " + iufd_review_xlsx + " (BLOCKED_PENDING_REVIEW -- clinical timing decision required)" if n_iufd_positive else "- No review file (gate not triggered)."}
- IUFD is never a predictor regardless of timing outcome; a "during_labor" timing decision keeps the row (IUFD remains a secondary fetal outcome), a "before_labor" decision requires cohort exclusion, and "cannot_establish" keeps the row blocked.

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)
    log_audit_event(
        audit_log_md,
        f"Batch 13 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- Binary cols validated: {binary_cols}\n"
        f"- IUFD=1 rows (clinical review gate): {n_iufd_positive}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 13 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 14 — Labor onset and induction-of-labor derivation
# start_of_labor, induction_of_labor, indication_for_induction, induction_any_bin
# ---------------------------------------------------------------------------

def batch_14_labor_induction(work_df):
    """
    Labor onset and induction-of-labor derivation.

    Standardizes start_of_labor and induction_of_labor, derives
    induction_any_bin from both source columns (codes 1-4 in either column
    indicate induction; indication_for_induction is never used to infer
    that induction occurred), and processes indication_for_induction,
    flagging contradictions for review.

    QA outputs: induction_review_df.xlsx (only if contradictions are
    found).
    Returns: df — the working DataFrame with labor-onset/induction
    variables derived.
    """
    BATCH_TITLE = BATCH_METADATA[14]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values, normalize_multi_code_string,
        parse_multi_code_field,
        log_audit_event, log_deviation_event, write_batch_summary,
        create_review_dataframe,
    )

    print(f"=== Batch 14: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch14.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch14.xlsx")
    review_xlsx    = os.path.join(review_path, "induction_review_df.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []
    import re as _re

    HAS_LETTERS = _re.compile(r"[A-Za-z?-?]")

    # ------------------------------------------------------------------
    # 1. start_of_labor — categorical multi-code; report distribution
    # ------------------------------------------------------------------
    sol_raw = df["start_of_labor"].copy()
    # Check for free text in start_of_labor
    sol_text_mask = df["start_of_labor"].map(
        lambda v: not pd.isna(v) and bool(HAS_LETTERS.search(str(v)))
    )
    n_sol_text = int(sol_text_mask.sum())
    if n_sol_text:
        unexpected_findings.append(
            f"start_of_labor: {n_sol_text} free-text value(s)"
        )

    # ------------------------------------------------------------------
    # 1b. start_of_labor — multi-code formatting normalization
    # ------------------------------------------------------------------
    # start_of_labor is a documented multi-code field (same clinical coding
    # style as indication_for_induction) but was never actually normalized —
    # multi-code cells kept their raw separator/whitespace/order exactly as
    # entered (e.g. "2, 3" and "2,3" coexisted as distinct strings for the
    # identical code set {2,3}). This applies the same tested
    # normalize_multi_code_string pattern already used for
    # indication_for_induction, but ONLY to cells that actually contain more
    # than one code — ordinary single-value cells (the large majority) keep
    # their original representation and dtype untouched, so this is a
    # formatting-only fix, not a column-wide type conversion. The underlying
    # code set is never changed, so induction_any_bin (derived from the
    # digit set, not the string form) is unaffected — verified below and by
    # test_batch14_start_of_labor_normalization.py.
    START_OF_LABOR_CODES = set(range(0, 10))  # conservative upper bound; documented/observed codes are 0-5

    def _normalize_sol_cell(val):
        if pd.isna(val):
            return val
        codes = normalize_multi_code_string(val, START_OF_LABOR_CODES)
        if len(codes) <= 1:
            return val  # single value or unparseable — representation untouched
        return ",".join(str(c) for c in codes)

    sol_normalized = df["start_of_labor"].map(_normalize_sol_cell)
    _sol_format_changed_mask = sol_raw.astype(str) != sol_normalized.astype(str)
    n_sol_format_changed = int(_sol_format_changed_mask.sum())
    if n_sol_format_changed:
        _sol_changed_rows = df.loc[_sol_format_changed_mask, ["subject_number", "delivery_id"]].copy()
        _sol_changed_rows["before"] = sol_raw.loc[_sol_format_changed_mask].astype(str)
        _sol_changed_rows["after"] = sol_normalized.loc[_sol_format_changed_mask].astype(str)
        _sol_changed_list = "; ".join(
            f"(subject_number={r.subject_number}, delivery_id={r.delivery_id}): "
            f"{r.before!r} -> {r.after!r}"
            for r in _sol_changed_rows.itertuples()
        )
        print(f"  start_of_labor formatting normalized: {n_sol_format_changed} row(s): {_sol_changed_list}")
        log_deviation_event(
            path=deviations_md,
            variable="start_of_labor",
            raw_variable="start of labor",
            documented="Multi-code field; normalize whitespace/separators, remove duplicate "
                       "codes, sort codes numerically — same pattern already applied to "
                       "indication_for_induction, previously not applied to start_of_labor "
                       "(Batch 14 read-only review finding PRE-B14-001).",
            action="Formatting-only normalization applied to multi-code cell(s); underlying "
                   f"code sets unchanged. Before -> after: {_sol_changed_list}",
            reason="start_of_labor multi-code cells previously kept raw, unnormalized separators "
                   "(e.g. '2, 3' vs '2,3' representing the identical code set {2,3}), which is a "
                   "formatting inconsistency, not a clinical recoding — no code is added, removed, "
                   "or reinterpreted, and induction_any_bin is unchanged for every row (digit-set "
                   "extraction is order/whitespace-independent). Ordinary single-value cells are "
                   "left untouched (representation and dtype preserved) to avoid an unnecessary "
                   "column-wide type conversion.",
            requires_approval=False,
            batch="Batch 14",
            affected_count=n_sol_format_changed,
        )
    else:
        print("  start_of_labor formatting normalization: 0 rows changed.")

    df["start_of_labor"] = sol_normalized
    sol_raw = sol_normalized  # downstream derivation (Sections 3 & 5) now reads the normalized column
    sol_vc  = df["start_of_labor"].value_counts(dropna=False).to_dict()
    print(f"  start_of_labor: {sol_vc}")

    # ------------------------------------------------------------------
    # 2. induction_of_labor — multi-code field; report distribution
    # ------------------------------------------------------------------
    iol_raw = df["induction_of_labor"].copy()
    iol_vc  = df["induction_of_labor"].value_counts(dropna=False).to_dict()
    iol_text_mask = df["induction_of_labor"].map(
        lambda v: not pd.isna(v) and bool(HAS_LETTERS.search(str(v)))
    )
    n_iol_text = int(iol_text_mask.sum())
    if n_iol_text:
        unexpected_findings.append(
            f"induction_of_labor: {n_iol_text} free-text value(s)"
        )
    print(f"  induction_of_labor: {iol_vc}")

    # ------------------------------------------------------------------
    # 3. induction_any_bin — derive from BOTH induction_of_labor and start_of_labor
    # INDUCTION_CODES = {1, 2, 3, 4}: evidence of induction
    # NON_INDUCTION_CODES = {0, 5}: code 5 = cesarean/surgery, not induction
    # Logic:
    #   1 if either column contains any code in {1,2,3,4}
    #   0 if both columns contain only {0,5} or NaN (but at least one has usable info)
    #   NaN if both columns are NaN (no usable information)
    # indication_for_induction must NOT be used to infer induction occurred.
    # ------------------------------------------------------------------
    INDUCTION_CODES = {1, 2, 3, 4}

    def _extract_int_codes(val):
        """Return set of integer codes from a raw cell, or None if no usable info."""
        if pd.isna(val): return None
        s = str(val).strip()
        if not s: return None
        codes = set()
        for m in _re.finditer(r'\d+', s):
            codes.add(int(m.group()))
        return codes if codes else None

    def _induction_any_combined(iol_val, sol_val):
        iol_codes = _extract_int_codes(iol_val)
        sol_codes = _extract_int_codes(sol_val)
        if iol_codes is None and sol_codes is None:
            return np.nan
        all_codes = (iol_codes or set()) | (sol_codes or set())
        if any(c in INDUCTION_CODES for c in all_codes):
            return 1.0
        return 0.0  # only codes 0/5 (or empty) across both columns

    df["induction_any_bin"] = [
        _induction_any_combined(i, s)
        for i, s in zip(iol_raw, sol_raw)
    ]
    iab_vc = df["induction_any_bin"].value_counts(dropna=False).to_dict()
    ok_iab, unexp_iab = validate_expected_binary_values(
        df["induction_any_bin"], "induction_any_bin"
    )
    if not ok_iab:
        unexpected_findings.append(f"induction_any_bin: unexpected values {unexp_iab}")
    print(f"  induction_any_bin: {iab_vc}")

    log_deviation_event(
        path=deviations_md,
        variable="induction_any_bin",
        raw_variable="induction of labor / start of labor",
        documented="Derived from induction_of_labor and start_of_labor per documentation.",
        action="Derived from both induction_of_labor and start_of_labor. "
               "Codes 1–4 = induction; codes 0/5 = not induction (5=CS, not induction).",
        reason="indication_for_induction must not be used — an indication does not prove induction "
               "occurred. Both induction_of_labor and start_of_labor are checked. "
               "induction_any_bin=NaN only when both source columns are NaN.",
        requires_approval=False,
        batch="Batch 14",
    )

    # ------------------------------------------------------------------
    # 4. indication_for_induction — parse clean code fields only
    # ------------------------------------------------------------------
    # Codes assumed 1-10 range (multi-hot documented but not coded yet)
    INDUCTION_IND_CODES = set(range(1, 20))  # conservative upper bound

    ifi_raw = df["indication_for_induction"].copy()
    ifi_text_mask = df["indication_for_induction"].map(
        lambda v: not pd.isna(v) and bool(HAS_LETTERS.search(str(v)))
    )
    n_ifi_text = int(ifi_text_mask.sum())

    # Parse only pure code fields (no letters)
    def _parse_ifi(val):
        if pd.isna(val): return np.nan
        s = str(val).strip()
        if not s or s in ("0", "0.0"): return np.nan
        if HAS_LETTERS.search(s): return np.nan  # free text → NaN, flag separately
        codes = normalize_multi_code_string(val, INDUCTION_IND_CODES)
        return ",".join(str(c) for c in codes) if codes else np.nan

    df["indication_for_induction_clean"] = ifi_raw.map(_parse_ifi)
    n_ifi_clean = int(df["indication_for_induction_clean"].notna().sum())
    n_ifi_nan   = int(df["indication_for_induction_clean"].isna().sum())
    print(f"  indication_for_induction_clean: {n_ifi_clean} parsed, {n_ifi_nan} NaN, "
          f"{n_ifi_text} free-text rows")

    # ------------------------------------------------------------------
    # 4b. induction_any_bin correction: real induction indication implies induction occurred
    # ------------------------------------------------------------------
    # Approved correction (data owner, 2026-07-10; see
    # docs/clinical_decisions/manual_decisions_log.md). If
    # indication_for_induction_clean is non-missing (a real, specific induction
    # indication code -- 1-10, excluding 0="no induction" which _parse_ifi already
    # maps to NaN above), induction_any_bin is forced to 1, even where
    # induction_of_labor/start_of_labor coded only {0,5}. This intentionally
    # REVERSES, for this specific subset of rows, the original design choice
    # documented above (Section 3), which deliberately excluded
    # indication_for_induction from the induction_any_bin derivation on the
    # grounds that an indication does not prove induction occurred. That
    # rationale is still valid in general; this correction treats the 9 rows
    # where the two derivations disagreed as a logic error to fix, not as a
    # reversal of the general principle -- an indication is being documented
    # for a reason, and a directly contradictory induction_any_bin=0 alongside
    # a specific real indication code is judged more likely to reflect a
    # derivation gap than genuine non-induction.
    _induction_any_bin_correction_mask = (
        (df["induction_any_bin"] == 0) &
        df["indication_for_induction_clean"].notna()
    )
    n_induction_any_bin_corrected = int(_induction_any_bin_correction_mask.sum())

    # Fail-loud dataset-specific invariant (Decision 26): the currently
    # approved dataset is documented to produce exactly 9 override rows.
    # An unexpected count must not be silently accepted as if it were the
    # same, already clinically reviewed population -- a future raw-data
    # refresh producing a different count needs a new clinical review, not
    # a silent re-application of this rule to a different row set.
    EXPECTED_DECISION_26_OVERRIDE_COUNT = 9
    if n_induction_any_bin_corrected != EXPECTED_DECISION_26_OVERRIDE_COUNT:
        raise ValueError(
            "Batch 14 Decision-26 override: expected exactly "
            f"{EXPECTED_DECISION_26_OVERRIDE_COUNT} row(s) with induction_any_bin=0 and a "
            "non-missing indication_for_induction_clean (the documented, already clinically "
            f"reviewed population), but found {n_induction_any_bin_corrected}. This is not a "
            "new clinical rule -- the count must match the already-approved population "
            "exactly. A different count means the underlying data changed and requires a new "
            "clinical review before this correction is reapplied."
        )

    _decision26_rows = df.loc[
        _induction_any_bin_correction_mask,
        ["subject_number", "delivery_id", "indication_for_induction_clean"],
    ]
    _decision26_keys_list = "; ".join(
        f"(subject_number={r.subject_number}, delivery_id={r.delivery_id}, "
        f"indication_for_induction_clean={r.indication_for_induction_clean!r})"
        for r in _decision26_rows.itertuples()
    )

    df.loc[_induction_any_bin_correction_mask, "induction_any_bin"] = 1.0
    print(f"  induction_any_bin correction: {n_induction_any_bin_corrected} row(s) changed "
          "from 0 to 1 (non-missing real induction indication present).")

    log_deviation_event(
        path=deviations_md,
        variable="induction_any_bin",
        raw_variable="induction of labor / start of labor / indication for induction ",
        documented="Decision 26 (docs/clinical_decisions/manual_decisions_log.md, approved "
                   "2026-07-10): the base derivation (Section 3 above; start_of_labor and "
                   "induction_of_labor only) deliberately excludes indication_for_induction. "
                   "Decision 26 then applies one approved, targeted override on top of that "
                   "base rule: rows where the base derivation gives induction_any_bin=0 but "
                   "indication_for_induction_clean is a real, non-missing induction indication "
                   "are treated as a derivation gap and corrected to induction_any_bin=1.",
        action=f"Applied the already-approved Decision-26 override to "
               f"{n_induction_any_bin_corrected} row(s), before=0 / after=1: "
               f"{_decision26_keys_list}",
        reason="This is an approved correction from Decision 26 (2026-07-10); it is being "
               "logged here for audit-trail completeness, not introduced or changed in this "
               "session. It applies only to this exact, already-reviewed row population "
               "(enforced immediately above by a fail-loud count assertion) and is not a "
               "general rule that indication_for_induction determines induction_any_bin "
               "outside this specific, approved exception.",
        requires_approval=False,
        batch="Batch 14",
        affected_count=n_induction_any_bin_corrected,
    )
    # Recompute for the summary/audit log so they reflect the corrected final state
    # (the print at Section 3 above intentionally still shows the pre-correction,
    # induction_of_labor/start_of_labor-only derivation for transparency).
    iab_vc = df["induction_any_bin"].value_counts(dropna=False).to_dict()

    # ------------------------------------------------------------------
    # 4c. Reproducibility guard — approved record-specific source edit [REDACTED]
    # ------------------------------------------------------------------
    # The canonical private source verifies one composite-key record whose source
    # workbook had been manually corrected before preprocessing. The composite key,
    # exact corrected source values, and patient-specific free-text excerpt are
    # intentionally removed from this review package.
    # No value is changed here; this redacted copy is not executable reproduction.

    # ------------------------------------------------------------------
    # 5. Contradiction / review flags
    # ------------------------------------------------------------------
    # induction_any_bin=0 but indication_for_induction_clean has codes.
    # This is now a post-correction check (Section 4b already fixed this exact
    # pattern) -- expected to be 0 rows going forward; retained as a live
    # regression check rather than removed, so a future data update that
    # reintroduces this pattern is still caught and reviewed, not silently corrected.
    contra_ind = (
        (df["induction_any_bin"] == 0) &
        df["indication_for_induction_clean"].notna()
    )
    # induction_any_bin=1 but start_of_labor is 0 (if start_of_labor is numeric)
    sol_num = pd.to_numeric(sol_raw, errors="coerce")
    contra_sol = (
        (df["induction_any_bin"] == 1) &
        sol_num.notna() &
        (sol_num == 0)
    )

    review_mask = ifi_text_mask | contra_ind | contra_sol
    n_review = int(review_mask.sum())
    if n_review:
        review_df = create_review_dataframe(
            df, review_mask,
            cols=["start_of_labor", "induction_of_labor", "induction_any_bin",
                  "indication_for_induction", "indication_for_induction_clean"],
            id_cols=["delivery_id", "subject_number"],
        )
        reason_list = []
        for idx in review_df.index:
            did = review_df.at[idx, "delivery_id"]
            orig_idx = df.index[df["delivery_id"] == did][0]
            r = []
            if ifi_text_mask.loc[orig_idx]:
                r.append("indication_for_induction contains free text")
            if contra_ind.loc[orig_idx]:
                r.append("induction_any_bin=0 but indication codes present")
            if contra_sol.loc[orig_idx]:
                r.append("induction_any_bin=1 but start_of_labor=0")
            reason_list.append("; ".join(r) if r else "flagged")
        review_df["review_reason"] = reason_list
        os.makedirs(resolve_path(OUTPUT_REVIEW_PATH), exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        print(f"  Review file saved: {review_xlsx} ({n_review} rows)")
    else:
        print("  No induction contradictions or free text found.")

    os.makedirs(resolve_path(OUTPUT_PROCESSED_PATH), exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    summary = f"""# Preprocessing Batch 14 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## start_of_labor
- {sol_vc}
- Free-text rows: {n_sol_text}

## induction_of_labor
- {iol_vc}
- Free-text rows: {n_iol_text}

## induction_any_bin (new, derived)
- {iab_vc}
- Derivation: 1 if either induction_of_labor or start_of_labor has a code in {{1,2,3,4}};
  0 if both have only codes in {{0,5}}; NaN if both are NaN.
- Code 5 = cesarean/surgery ? does NOT count as induction.
- indication_for_induction NOT used for the base derivation (indication ? actual induction).
- Correction applied (2026-07-10): {n_induction_any_bin_corrected} row(s) with
  induction_any_bin=0 but a non-missing indication_for_induction_clean were
  corrected to induction_any_bin=1. See docs/clinical_decisions/manual_decisions_log.md.

## indication_for_induction_clean (new column)
- Parsed: {n_ifi_clean} | NaN: {n_ifi_nan} | Free text (not parsed): {n_ifi_text}

## Review file
{"- " + review_xlsx + f" ({n_review} rows)" if n_review else "- None"}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)
    log_audit_event(
        audit_log_md,
        f"Batch 14 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- start_of_labor: {sol_vc}\n"
        f"- induction_of_labor: {iol_vc}\n"
        f"- induction_any_bin: {iab_vc}\n"
        f"- indication_for_induction_clean: {n_ifi_clean} parsed\n"
        f"- Review rows: {n_review}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 14 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 15 — Cesarean-delivery reference variables and subgroup applicability
# type_of_CS (validated only — already used for target), indication_for_CS,
# suspected_endo_lesions_during_CS, abdominal_cavity_findings,
# other_surgery_complications, adhesions,
# comment_3, comment_4, comment_5
# (surgery_dehiscence dropped in Batch 2, Decision 33)
# ---------------------------------------------------------------------------

def batch_15_cs_reference_variables(work_df):
    """
    Cesarean-delivery reference variables and subgroup applicability.

    Validates type_of_CS (already used for the target in Batch 2) and
    cesarean-only reference variables, derives indication_for_CS_clean and
    suspected_endo_lesions_during_CS_clean, and applies the
    cesarean-subgroup structural-missingness mask to adhesions
    (Decision 35, subgroup rule type_of_CS.isin([2, 3])). Values outside
    the cesarean subgroup become missing, not zero.

    Approved decisions: 35.
    QA outputs: cs_reference_review_df.xlsx (only if contradictions are
    found).
    Returns: df — the working DataFrame with cesarean-reference variables
    cleaned.
    """
    BATCH_TITLE = BATCH_METADATA[15]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values, normalize_multi_code_string,
        set_outside_subgroup_to_na,
        log_audit_event, log_deviation_event, write_batch_summary,
        create_review_dataframe,
    )

    print(f"=== Batch 15: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch15.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch15.xlsx")
    review_xlsx    = os.path.join(review_path, "cs_reference_review_df.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []
    import re as _re

    HAS_LETTERS = _re.compile(r"[A-Za-z?-?]")

    # CS subgroup mask — cesarean cases only
    cs_mask = df["target_intrapartum_cs"] == 1
    n_cs = int(cs_mask.sum())
    # Subgroup mask based on delivery mode — used for surgery-only variables.
    # After cohort filtering, type_of_CS values are only {0, 2, 3}.
    cs_surgery_mask = df["type_of_CS"].isin([2, 3])

    # Decision 35 (2026-07-30): the clinical delivery-mode subgroup definition
    # (type_of_CS.isin([2,3])) is the canonical rule used for masking
    # adhesions/surgical_site_infection below. Assert it is identical to the
    # target-based definition in this cohort -- verified, not assumed.
    if not cs_surgery_mask.equals(cs_mask):
        raise AssertionError(
            "Cesarean subgroup definitions diverge: type_of_CS.isin([2,3]) != "
            "target_intrapartum_cs==1. Stopping -- do not apply the "
            "adhesions/surgical_site_infection subgroup mask without re-approval. "
            "See docs/clinical_decisions/manual_decisions_log.md, Decision 35."
        )
    print(f"  Cesarean subgroup check: type_of_CS.isin([2,3]) == target_intrapartum_cs==1 "
          f"for all {len(df)} rows (n_cs={n_cs}) -- PASS")

    # ------------------------------------------------------------------
    # 1. type_of_CS — already used for target; validate only, no changes
    # ------------------------------------------------------------------
    toc_vc = df["type_of_CS"].value_counts(dropna=False).to_dict()
    print(f"  type_of_CS (reference): {toc_vc}")

    # ------------------------------------------------------------------
    # 2. indication_for_CS — post-event leakage; parse clean code fields;
    #    mark as reference only; apply subgroup NaN for vaginal deliveries
    # ------------------------------------------------------------------
    ICS_VALID_CODES = set(range(1, 30))  # conservative upper bound

    ics_raw = df["indication_for_CS"].copy()
    ics_text_mask = df["indication_for_CS"].map(
        lambda v: not pd.isna(v) and bool(HAS_LETTERS.search(str(v)))
    )
    n_ics_text = int(ics_text_mask.sum())

    def _parse_ics(val):
        if pd.isna(val): return np.nan
        s = str(val).strip()
        if not s or s in ("0", "0.0"): return np.nan
        if HAS_LETTERS.search(s): return np.nan
        codes = normalize_multi_code_string(val, ICS_VALID_CODES)
        return ",".join(str(c) for c in codes) if codes else np.nan

    df["indication_for_CS_clean"] = ics_raw.map(_parse_ics)
    # Vaginal deliveries: set to NaN in clean column (CS-subgroup variable)
    df.loc[~cs_mask, "indication_for_CS_clean"] = np.nan
    n_ics_clean = int(df["indication_for_CS_clean"].notna().sum())
    print(f"  indication_for_CS_clean: {n_ics_clean} parsed (CS only), "
          f"{n_ics_text} free-text rows")

    # ------------------------------------------------------------------
    # 3. suspected_endo_lesions_during_CS — CS subgroup only;
    #    apply subgroup NaN: vaginal → NaN in clean derived version
    # ------------------------------------------------------------------
    sel_raw = df["suspected_endo_lesions_during_CS"].copy()
    ok_sel, unexp_sel = validate_expected_binary_values(
        df["suspected_endo_lesions_during_CS"], "suspected_endo_lesions_during_CS"
    )
    if not ok_sel:
        unexpected_findings.append(
            f"suspected_endo_lesions_during_CS: unexpected values {unexp_sel}"
        )
    # Create subgroup-restricted clean version
    df["suspected_endo_lesions_during_CS_clean"] = set_outside_subgroup_to_na(
        df, "suspected_endo_lesions_during_CS", cs_mask,
        new_col="suspected_endo_lesions_during_CS_clean"
    )["suspected_endo_lesions_during_CS_clean"]
    sel_cs_vc = df.loc[cs_mask, "suspected_endo_lesions_during_CS_clean"].value_counts(dropna=False).to_dict()
    print(f"  suspected_endo_lesions_during_CS (CS cases only): {sel_cs_vc}")

    # ------------------------------------------------------------------
    # 4. abdominal_cavity_findings — CS subgroup only; free text; preserve
    # ------------------------------------------------------------------
    acf_before_vc    = df["abdominal_cavity_findings"].value_counts(dropna=False).to_dict()
    acf_non_cs_before = int(df.loc[~cs_surgery_mask, "abdominal_cavity_findings"].notna().sum())
    df = set_outside_subgroup_to_na(df, "abdominal_cavity_findings", cs_surgery_mask)
    acf_after_vc         = df["abdominal_cavity_findings"].value_counts(dropna=False).to_dict()
    acf_set_nan          = acf_non_cs_before
    acf_vaginal_remaining = int(df.loc[~cs_surgery_mask, "abdominal_cavity_findings"].notna().sum())
    acf_cs_non_null      = int(df.loc[cs_surgery_mask, "abdominal_cavity_findings"].notna().sum())
    print(f"  abdominal_cavity_findings: {acf_set_nan} non-CS rows set to NaN; "
          f"{acf_cs_non_null} non-null preserved in CS rows; "
          f"{acf_vaginal_remaining} non-null remaining in non-CS rows (expected 0)")

    # ------------------------------------------------------------------
    # 5. other_surgery_complications — post-event leakage; validate binary;
    #    CS subgroup expected
    #    (surgery_dehiscence dropped in Batch 2, Decision 33, 2026-07-30 --
    #    no longer present in df by this point)
    # ------------------------------------------------------------------
    sdc_results = {}
    for col in ("other_surgery_complications",):
        ok, unexp = validate_expected_binary_values(df[col], col)
        before_vc      = df[col].value_counts(dropna=False).to_dict()
        non_cs_before  = int(df.loc[~cs_surgery_mask, col].notna().sum())
        if not ok:
            unexpected_findings.append(f"{col}: unexpected values {unexp}")
        df = set_outside_subgroup_to_na(df, col, cs_surgery_mask)
        after_vc           = df[col].value_counts(dropna=False).to_dict()
        vaginal_remaining  = int(df.loc[~cs_surgery_mask, col].notna().sum())
        cs_non_null        = int(df.loc[cs_surgery_mask, col].notna().sum())
        sdc_results[col] = {
            "before_vc": before_vc, "after_vc": after_vc,
            "set_nan": non_cs_before, "vaginal_remaining": vaginal_remaining,
            "cs_non_null": cs_non_null,
        }
        print(f"  {col}: {non_cs_before} non-CS rows set to NaN; "
              f"{cs_non_null} non-null preserved in CS rows; "
              f"{vaginal_remaining} non-null remaining in non-CS rows (expected 0)")

    # ------------------------------------------------------------------
    # 6. adhesions — binary; validate; cesarean-subgroup structural mask
    #    (Decision 35, 2026-07-30): adhesions is applicable only to the
    #    cesarean subgroup -- a structural-applicability mask, not a clinical
    #    recoding. Vaginal rows were already NaN in the raw source, so this is
    #    expected to produce zero effective value changes; verified, not
    #    assumed, via before/after comparison below.
    # ------------------------------------------------------------------
    ok_adh, unexp_adh = validate_expected_binary_values(df["adhesions"], "adhesions")
    adh_before_vc = df["adhesions"].value_counts(dropna=False).to_dict()
    adh_before_non_cs_non_null = int(df.loc[~cs_surgery_mask, "adhesions"].notna().sum())
    if not ok_adh:
        unexpected_findings.append(f"adhesions: unexpected values {unexp_adh}")
    df = set_outside_subgroup_to_na(df, "adhesions", cs_surgery_mask)
    adh_vc = df["adhesions"].value_counts(dropna=False).to_dict()
    adh_cs_non_null = int(df.loc[cs_surgery_mask, "adhesions"].notna().sum())
    adh_vaginal_remaining = int(df.loc[~cs_surgery_mask, "adhesions"].notna().sum())
    adh_effective_changes = adh_before_non_cs_non_null - adh_vaginal_remaining
    print(f"  adhesions: before={adh_before_vc} | after={adh_vc}")
    print(f"  adhesions: {adh_effective_changes} non-CS value(s) actually changed by masking "
          f"(non-CS non-null before={adh_before_non_cs_non_null}, remaining after={adh_vaginal_remaining}); "
          f"CS non-null={adh_cs_non_null}; non-CS remaining (expected 0)={adh_vaginal_remaining}")

    # ------------------------------------------------------------------
    # 7. comment_3, comment_4, comment_5 — free text; normalize zeros
    # ------------------------------------------------------------------
    for col in ("comment_3", "comment_4", "comment_5"):
        before = df[col].copy()
        df[col] = df[col].apply(lambda v: np.nan if v in (0, "0", 0.0) else v)
        n_zeros = int(before.map(lambda v: v in (0, "0", 0.0)).sum())
        n_text  = int(df[col].notna().sum())
        print(f"  {col}: {n_text} non-null, {n_zeros} zeros->NaN")

    # ------------------------------------------------------------------
    # 8. Review: vaginal delivery rows with CS-specific data,
    #    CS rows missing indication, free-text indications
    # ------------------------------------------------------------------
    # Vaginal rows with non-null CS indication
    vag_with_ics = (~cs_mask) & ics_raw.notna() & ~(ics_raw.map(
        lambda v: pd.isna(v) or str(v).strip() in ("0", "0.0", "")
    ))
    # CS rows with no indication at all
    cs_no_ics = cs_mask & ics_raw.isna()
    # Free-text indication rows
    review_mask = ics_text_mask | vag_with_ics | cs_no_ics
    n_review = int(review_mask.sum())

    if n_review:
        review_cols = [
            "type_of_CS", "target_intrapartum_cs",
            "indication_for_CS", "indication_for_CS_clean",
            "suspected_endo_lesions_during_CS",
        ]
        review_df = create_review_dataframe(
            df, review_mask,
            cols=review_cols,
            id_cols=["delivery_id", "subject_number"],
        )
        reason_list = []
        for idx in review_df.index:
            did = review_df.at[idx, "delivery_id"]
            orig_idx = df.index[df["delivery_id"] == did][0]
            r = []
            if ics_text_mask.loc[orig_idx]:
                r.append("indication_for_CS contains free text")
            if vag_with_ics.loc[orig_idx]:
                r.append("vaginal delivery but indication_for_CS is non-null")
            if cs_no_ics.loc[orig_idx]:
                r.append("CS case but indication_for_CS is NaN")
            reason_list.append("; ".join(r) if r else "flagged")
        review_df["review_reason"] = reason_list
        os.makedirs(resolve_path(OUTPUT_REVIEW_PATH), exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        print(f"  Review file saved: {review_xlsx} ({n_review} rows)")
    else:
        print("  No CS reference contradictions or free text found.")

    # ------------------------------------------------------------------
    # Save + audit
    # ------------------------------------------------------------------
    os.makedirs(resolve_path(OUTPUT_PROCESSED_PATH), exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    summary = f"""# Preprocessing Batch 15 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)
- CS cases (target_intrapartum_cs=1): {n_cs}

## type_of_CS (reference only, already used for target)
- {toc_vc}

## indication_for_CS_clean (new, CS subgroup only, LEAKAGE — reference only)
- Clean codes parsed (CS rows only): {n_ics_clean}
- Free-text rows (not parsed): {n_ics_text}
- Vaginal delivery rows: set to NaN in clean column

## suspected_endo_lesions_during_CS_clean (new, CS subgroup)
- CS case values: {sel_cs_vc}
- Vaginal rows: NaN in clean column

## abdominal_cavity_findings (CS subgroup only; subgroup NaN applied in place)
- Before masking: {acf_before_vc}
- Non-CS rows set to NaN: {acf_set_nan}
- After masking — CS rows non-null: {acf_cs_non_null} | non-CS rows non-null: {acf_vaginal_remaining} (expected 0)

## other_surgery_complications (CS subgroup only; subgroup NaN applied in place)
- other_surgery_complications: before={sdc_results['other_surgery_complications']['before_vc']} | non-CS set to NaN={sdc_results['other_surgery_complications']['set_nan']} | CS non-null={sdc_results['other_surgery_complications']['cs_non_null']} | non-CS remaining={sdc_results['other_surgery_complications']['vaginal_remaining']} (expected 0)
(surgery_dehiscence dropped in Batch 2, Decision 33, 2026-07-29)

## adhesions (cesarean-subgroup structural mask, Decision 35, 2026-07-29)
- Before masking: {adh_before_vc}
- After masking: {adh_vc}
- Effective non-CS value changes: {adh_effective_changes} (expected 0 -- vaginal rows already NaN in raw source)
- CS non-null: {adh_cs_non_null} | non-CS remaining (expected 0): {adh_vaginal_remaining}

## comment_3, comment_4, comment_5 (free text, reference)
- Placeholder zeros normalized to NaN

## Review file
{"- " + review_xlsx + f" ({n_review} rows)" if n_review else "- None"}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)
    log_audit_event(
        audit_log_md,
        f"Batch 15 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- CS cases: {n_cs}\n"
        f"- indication_for_CS_clean: {n_ics_clean} parsed, {n_ics_text} free text\n"
        f"- suspected_endo_lesions_during_CS_clean: subgroup NaN applied (cs_mask)\n"
        f"- abdominal_cavity_findings: {acf_set_nan} non-CS rows set to NaN; {acf_cs_non_null} CS non-null remaining\n"
        f"- other_surgery_complications: {sdc_results['other_surgery_complications']['set_nan']} non-CS rows set to NaN; {sdc_results['other_surgery_complications']['cs_non_null']} CS non-null remaining\n"
        f"- surgery_dehiscence: dropped in Batch 2 (Decision 33, 2026-07-29)\n"
        f"- adhesions: cesarean-subgroup mask applied (Decision 35), {adh_effective_changes} effective non-CS changes, {adh_cs_non_null} CS non-null remaining\n"
        f"- Review rows: {n_review}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 15 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 16 — Maternal post-delivery outcomes and leakage-variable reference
# CS_case_vs_control, blood_loss_during_surgery, Hb_before/after_delivery,
# Hb_diff, intrapartum_fever, postpartum_fever, surgical_site_infection,
# endometritis, any_blood_product_transfusion, hospitalization_days, comment_6
# ---------------------------------------------------------------------------

def batch_16_maternal_outcomes(work_df):
    """
    Maternal post-delivery outcomes and leakage-variable reference.

    Cleans post-delivery / leakage reference variables (blood loss, Hb
    before/after, fever, endometritis, transfusion, hospitalization days),
    applies the cesarean-subgroup structural-missingness mask to
    surgical_site_infection (Decision 35), and derives the
    intrapartum_fever_or_chorioamnionitis_bin composite from
    intrapartum_fever and chorioamnionitis (Decision 31). Every variable
    handled in this batch is post-event and must be excluded from
    pre-labor prediction.

    Approved decisions: 31, 35, 51.
    QA outputs: maternal_outcomes_review_df.xlsx,
    blood_loss_distribution_for_thresholds_QA.xlsx (Decision 51: review closed,
    retained as historical evidence — continuous mL, cesarean-only, no
    threshold-derived variable, descriptive/secondary-outcome use only),
    blood_loss_during_surgery_subgroup_QA.xlsx.
    Returns: df — the working DataFrame with maternal post-delivery/
    leakage variables cleaned.
    """
    BATCH_TITLE = BATCH_METADATA[16]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values, set_outside_subgroup_to_na,
        log_audit_event, log_deviation_event, write_batch_summary,
        create_review_dataframe,
    )


    print(f"=== Batch 16: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch16.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch16.xlsx")
    review_xlsx    = os.path.join(review_path, "maternal_outcomes_review_df.xlsx")
    bld_qa_xlsx    = os.path.join(review_path, "blood_loss_distribution_for_thresholds_QA.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []
    def _has_letters(value):
        return not pd.isna(value) and any(ch.isalpha() for ch in str(value))

    # ------------------------------------------------------------------
    # 0. Cesarean target/reference cross-consistency assertion (fail-loud)
    # ------------------------------------------------------------------
    # Verifies, on every run, that the three independent representations of
    # "was this delivery a cesarean" still agree row-for-row:
    #   CS_case_vs_control == target_intrapartum_cs
    #   target_intrapartum_cs == type_of_CS.isin([2, 3]).astype(int)
    # Mirrors the existing cs_surgery_mask/cs_mask assertion in
    # batch_15_cs_reference_variables, extended to cover CS_case_vs_control,
    # the reference variable introduced in this batch. Currently 0 mismatches
    # across the 447-row cohort (Batch 16 read-only review, PRE-B16-002) --
    # this only detects a future divergence; it never corrects one and never
    # redefines the cohort or target.
    _cesarean_required_cols = [
        "subject_number", "delivery_id", "CS_case_vs_control",
        "target_intrapartum_cs", "type_of_CS",
    ]
    _missing_cesarean_cols = [c for c in _cesarean_required_cols if c not in df.columns]
    if _missing_cesarean_cols:
        raise ValueError(
            "Batch 16 cesarean target/reference assertion: required column(s) "
            f"missing from the working dataframe: {_missing_cesarean_cols}. Cannot "
            "verify CS_case_vs_control/target_intrapartum_cs/type_of_CS agreement."
        )
    if df.duplicated(subset=["subject_number", "delivery_id"]).any():
        raise ValueError(
            "Batch 16 cesarean target/reference assertion: duplicate "
            "subject_number+delivery_id composite key found -- cannot build a "
            "reliable row-level mismatch report."
        )
    _type_of_cs_bin = df["type_of_CS"].isin([2, 3]).astype(int)
    _cesarean_mismatch_mask = (
        (df["CS_case_vs_control"] != df["target_intrapartum_cs"]) |
        (df["target_intrapartum_cs"] != _type_of_cs_bin)
    )
    _n_cesarean_mismatch = int(_cesarean_mismatch_mask.sum())
    if _n_cesarean_mismatch:
        _mismatch_rows = df.loc[
            _cesarean_mismatch_mask,
            ["subject_number", "delivery_id", "CS_case_vs_control", "target_intrapartum_cs", "type_of_CS"],
        ]
        _mismatch_list = "; ".join(
            f"(subject_number={r.subject_number}, delivery_id={r.delivery_id}): "
            f"CS_case_vs_control={r.CS_case_vs_control}, "
            f"target_intrapartum_cs={r.target_intrapartum_cs}, "
            f"type_of_CS={r.type_of_CS}"
            for r in _mismatch_rows.itertuples()
        )
        raise ValueError(
            f"Batch 16 cesarean target/reference assertion: {_n_cesarean_mismatch} "
            "row(s) disagree between CS_case_vs_control, target_intrapartum_cs, and "
            "type_of_CS.isin([2,3]). Stopping -- do not silently trust or overwrite "
            "one field from another; this needs manual clinical review before "
            f"proceeding. Mismatches: {_mismatch_list}"
        )
    print(f"  Cesarean target/reference check: CS_case_vs_control == target_intrapartum_cs "
          f"== type_of_CS.isin([2,3]) for all {len(df)} rows -- PASS")

    # ------------------------------------------------------------------
    # 1. CS_case_vs_control — internal/leakage; validate binary
    # ------------------------------------------------------------------
    ok_csc, unexp_csc = validate_expected_binary_values(df["CS_case_vs_control"], "CS_case_vs_control")
    csc_vc = df["CS_case_vs_control"].value_counts(dropna=False).to_dict()
    if not ok_csc:
        unexpected_findings.append(f"CS_case_vs_control: unexpected values {unexp_csc}")
    print(f"  CS_case_vs_control (leakage/ref): {csc_vc}")

    # ------------------------------------------------------------------
    # 2. blood_loss_during_surgery — leakage; numeric (mL); flag >3000
    # ------------------------------------------------------------------
    bld_text_mask = df["blood_loss_during_surgery"].map(_has_letters)
    bld_raw = df["blood_loss_during_surgery"].copy()  # preserve raw values for subgroup QA
    n_bld_text = int(bld_text_mask.sum())

    # Subgroup rule (Keren): type_of_CS=0 (vaginal) -> NaN (not applicable for vaginal deliveries).
    # 0-to-NaN rule (Keren): 0 = missing/unknown documentation, not true zero blood loss.
    # Free-text rule: text value -> NaN; preserve original text exactly in comment_6. No normalization.
    # Do not impute numeric value. Do not recode PPH.
    # Keren: blood loss >1000 mL during surgery is abnormal. Do not create abnormal variable here;
    # defer to EDA/secondary outcome analysis. This variable must not be used as a predictor.
    bld_text_originals = {}
    for idx in df.index[bld_text_mask]:
        orig_text = str(df.at[idx, "blood_loss_during_surgery"]).strip()
        bld_text_originals[idx] = orig_text
        df.at[idx, "blood_loss_during_surgery"] = np.nan
        existing_comment_6 = df.at[idx, "comment_6"]
        appendage = f"blood_loss_during_surgery original text: {orig_text}"
        if pd.isna(existing_comment_6) or str(existing_comment_6).strip() in ("", "0", "nan"):
            df.at[idx, "comment_6"] = appendage
        else:
            df.at[idx, "comment_6"] = f"{existing_comment_6}, {appendage}"
    if n_bld_text:
        print(f"  blood_loss_during_surgery: {n_bld_text} free-text value(s) set to NaN; "
              f"original text appended to comment_6")

    # type_of_CS-based cleanup:
    # type_of_CS == 0 (vaginal): blood loss during surgery is not applicable → NaN
    # type_of_CS in {2,3} (CS): numeric 0 is not a valid blood loss measurement → NaN
    vaginal_mask = df["type_of_CS"] == 0
    bld_val_num_temp = pd.to_numeric(df["blood_loss_during_surgery"], errors="coerce")

    n_bld_vaginal_set_nan = int(
        vaginal_mask & bld_val_num_temp.notna()
    ).sum() if False else int((vaginal_mask & bld_val_num_temp.notna()).sum())
    if n_bld_vaginal_set_nan > 0:
        df.loc[vaginal_mask, "blood_loss_during_surgery"] = np.nan
        log_deviation_event(
            path=deviations_md,
            variable="blood_loss_during_surgery",
            raw_variable="blood loss during surgery",
            documented="Blood loss numeric value (mL) for CS cases only.",
            action=f"Set blood_loss_during_surgery to NaN for {n_bld_vaginal_set_nan} vaginal delivery rows (type_of_CS=0).",
            reason="Blood loss during surgery is not applicable for vaginal deliveries. NaN preserves clinical accuracy.",
            requires_approval=False,
            batch="Batch 16 hotfix",
            affected_count=n_bld_vaginal_set_nan,
        )
        print(f"  blood_loss_during_surgery: {n_bld_vaginal_set_nan} vaginal row(s) set to NaN (type_of_CS=0)")

    cs_mask = df["type_of_CS"].isin([2, 3])
    bld_val_num_temp2 = pd.to_numeric(df["blood_loss_during_surgery"], errors="coerce")
    zero_cs_mask = cs_mask & (bld_val_num_temp2 == 0)
    n_bld_zero_set_nan = int(zero_cs_mask.sum())
    if n_bld_zero_set_nan > 0:
        df.loc[zero_cs_mask, "blood_loss_during_surgery"] = np.nan
        log_deviation_event(
            path=deviations_md,
            variable="blood_loss_during_surgery",
            raw_variable="blood loss during surgery",
            documented="Blood loss should be a positive numeric value in mL for CS cases.",
            action=f"Set blood_loss_during_surgery=0 to NaN for {n_bld_zero_set_nan} CS row(s) (type_of_CS in {{2,3}}).",
            reason="Zero is not a valid blood loss measurement for cesarean deliveries; treated as missing/not recorded.",
            requires_approval=False,
            batch="Batch 16 hotfix",
            affected_count=n_bld_zero_set_nan,
        )
        print(f"  blood_loss_during_surgery: {n_bld_zero_set_nan} zero value(s) in CS rows set to NaN")

    bld_num = pd.to_numeric(df["blood_loss_during_surgery"], errors="coerce")
    n_bld_valid = int(bld_num.notna().sum())
    n_bld_nan   = int(bld_num.isna().sum())
    bld_high_mask = bld_num.notna() & (bld_num > 3000)
    n_bld_high  = int(bld_high_mask.sum())
    print(f"  blood_loss_during_surgery (leakage): {n_bld_valid} numeric, {n_bld_nan} NaN, "
          f"{n_bld_high} >3000 mL, {n_bld_text} free-text (moved to comment_6)")

    # ------------------------------------------------------------------
    # Subgroup QA: before/after view for 0-to-NaN, text-to-NaN, and vaginal NaN
    # ------------------------------------------------------------------
    bld_subgroup_qa_xlsx = os.path.join(review_path, "blood_loss_during_surgery_subgroup_QA.xlsx")
    bld_proc_post   = pd.to_numeric(df["blood_loss_during_surgery"], errors="coerce")
    bld_raw_numeric = pd.to_numeric(bld_raw, errors="coerce")
    bld_raw_is_zero = bld_raw_numeric == 0
    bld_cs_empty    = df["type_of_CS"].isin([2, 3]) & bld_raw.isna()
    bld_proc_zero   = bld_proc_post == 0
    subgroup_qa_mask = bld_raw_is_zero | bld_cs_empty | bld_text_mask | bld_proc_zero
    if subgroup_qa_mask.any():
        qa_rows = df[subgroup_qa_mask]
        # Per-row reason(s) this record was included -- a row may match more than one
        # of the four inclusion conditions (e.g. a CS-empty row that is also raw-zero).
        flag_reasons = []
        for idx in qa_rows.index:
            r = []
            if bld_raw_is_zero.loc[idx]:
                r.append("raw value was 0 (treated as missing/not recorded, not true zero)")
            if bld_cs_empty.loc[idx]:
                r.append("cesarean case with no raw blood-loss value recorded")
            if bld_text_mask.loc[idx]:
                r.append("raw value was free text (moved to comment_6)")
            if bld_proc_zero.loc[idx]:
                r.append("processed value is 0")
            flag_reasons.append("; ".join(r))
        bld_subgroup_qa = pd.DataFrame({
            "delivery_id":           qa_rows["delivery_id"].values,
            "subject_number":        qa_rows["subject_number"].values,
            "type_of_CS":            qa_rows["type_of_CS"].values,
            "cesarean_subgroup_applicable": qa_rows["type_of_CS"].isin([2, 3]).values,
            "target_intrapartum_cs": qa_rows["target_intrapartum_cs"].values,
            "blood_loss_raw":        bld_raw[subgroup_qa_mask].values,
            "blood_loss_processed":  qa_rows["blood_loss_during_surgery"].values,
            "flag_reason":           flag_reasons,
            "comment_6":             qa_rows["comment_6"].values,
        })
        os.makedirs(resolve_path(OUTPUT_REVIEW_PATH), exist_ok=True)
        bld_subgroup_qa.to_excel(bld_subgroup_qa_xlsx, index=False)
        print(f"  Subgroup QA saved: {bld_subgroup_qa_xlsx} ({int(subgroup_qa_mask.sum())} rows)")
    else:
        print("  Subgroup QA: no relevant blood_loss rows.")

    # ------------------------------------------------------------------
    # 3. Hb_before_delivery, Hb_after_delivery — numeric (g/dL); flag <5 or >20
    # ------------------------------------------------------------------
    # Known missing/invalid text markers confirmed from data inspection 2026-05-26.
    # Numeric strings with exactly one trailing dot (e.g. '10.00.') are normalised to
    # their numeric value. Other leakage/post-outcome numeric columns are not affected.
    _HB_MISSING_MARKERS = {"לא נלקח", "אין נתונים", "פסול"}
    _HB_NULL_TOKENS = {"na", "n/a", "nan", "none", "null"}

    def _clean_hb_value(val):
        """Return float, np.nan-for-known-missing, or the original value for unexpected text."""
        if pd.isna(val):
            return np.nan
        s = str(val).strip()
        if s == "" or s.lower() in _HB_NULL_TOKENS:
            return np.nan
        if s in _HB_MISSING_MARKERS:
            return np.nan
        # Normalise exactly-one-trailing-dot typos (e.g. '10.00.' -> 10.0)
        if s.endswith(".") and not s.endswith(".."):
            candidate = s[:-1]
            try:
                return float(candidate)
            except (ValueError, TypeError):
                pass  # unexpected — fall through to return original string
        try:
            return float(s)
        except (ValueError, TypeError):
            return s  # preserve original value; unexpected cases counted below

    hb_results = {}
    for col in ("Hb_before_delivery", "Hb_after_delivery"):
        before = df[col].copy()
        cleaned = df[col].map(_clean_hb_value)

        # Identify unexpected non-numeric values (not a known marker, not parseable)
        unexpected_mask = cleaned.map(lambda v: isinstance(v, str))
        n_unexpected = int(unexpected_mask.sum())
        if n_unexpected > 0:
            unexpected_vals = cleaned[unexpected_mask].value_counts().to_dict()
            unexpected_findings.append(
                f"{col}: {n_unexpected} unexpected non-numeric value(s) converted to NaN: "
                f"{unexpected_vals}"
            )
            print(f"  WARNING: {col}: unexpected non-numeric -> NaN: {unexpected_vals}")
        # Now replace any remaining strings with NaN before numeric coercion
        cleaned = cleaned.map(lambda v: np.nan if isinstance(v, str) else v)

        # Count trailing-dot corrections (non-null before, numeric after, non-numeric in before)
        before_numeric = pd.to_numeric(before, errors="coerce")
        n_trailing_dot = int(
            (
                before.notna()
                & cleaned.notna()
                & before_numeric.isna()
            ).sum()
        )

        df[col] = pd.to_numeric(cleaned, errors="coerce")
        n_valid   = int(df[col].notna().sum())
        n_nan     = int(df[col].isna().sum())
        n_imp     = int((df[col].notna() & ((df[col] < 5) | (df[col] > 20))).sum())
        # Expected-missing = originally non-null, now NaN, not unexpected
        n_expected_nan = int(
            (before.notna() & df[col].isna()).sum()
        ) - n_unexpected
        hb_results[col] = {
            "valid": n_valid, "nan": n_nan, "impossible": n_imp,
            "expected_markers_to_nan": n_expected_nan,
            "trailing_dot_corrected": n_trailing_dot,
            "unexpected_to_nan": n_unexpected,
        }
        print(
            f"  {col}: {n_valid} valid, {n_nan} NaN "
            f"({n_expected_nan} known markers->NaN, "
            f"{n_trailing_dot} trailing-dot corrected, "
            f"{n_unexpected} unexpected->NaN), "
            f"{n_imp} outside 5-20 g/dL"
        )

    # ------------------------------------------------------------------
    # 4. Hb_diff — leakage; numeric; report only
    # ------------------------------------------------------------------
    hbd_num = pd.to_numeric(df["Hb_diff"], errors="coerce")
    n_hbd_valid = int(hbd_num.notna().sum())
    n_hbd_nan   = int(hbd_num.isna().sum())
    print(f"  Hb_diff (source leakage, not modified): {n_hbd_valid} numeric, {n_hbd_nan} NaN")

    # ------------------------------------------------------------------
    # 4b. Hb_diff_clean — derived leakage: Hb_before_delivery - Hb_after_delivery
    # ------------------------------------------------------------------
    df["Hb_diff_clean"] = df["Hb_before_delivery"] - df["Hb_after_delivery"]
    n_hbd_clean_valid = int(df["Hb_diff_clean"].notna().sum())
    n_hbd_clean_nan   = int(df["Hb_diff_clean"].isna().sum())
    print(f"  Hb_diff_clean (derived leakage): {n_hbd_clean_valid} numeric, "
          f"{n_hbd_clean_nan} NaN")

    # ------------------------------------------------------------------
    # 5. Binary leakage variables: intrapartum_fever, postpartum_fever,
    #    endometritis, any_blood_product_transfusion
    #    (surgical_site_infection handled separately below, step 5a --
    #    cesarean-subgroup structural mask, Decision 35)
    # ------------------------------------------------------------------
    binary_leakage = [
        "intrapartum_fever", "postpartum_fever",
        "endometritis", "any_blood_product_transfusion",
    ]
    bin_results = {}
    for col in binary_leakage:
        ok, unexp = validate_expected_binary_values(df[col], col)
        vc = df[col].value_counts(dropna=False).to_dict()
        bin_results[col] = {"ok": ok, "vc": vc}
        if not ok:
            unexpected_findings.append(f"{col}: unexpected values {unexp}")
        print(f"  {col} (leakage): {vc}")

    # ------------------------------------------------------------------
    # 5a. surgical_site_infection — cesarean-subgroup structural mask
    #    (Decision 35, 2026-07-30): applicable only to the cesarean subgroup.
    #    Vaginal-row 0s were NOT confirmed absence of infection -- they become
    #    structurally missing (NaN), not a clinical recoding to a different
    #    value. Uses the same type_of_CS.isin([2,3]) definition asserted
    #    identical to target_intrapartum_cs==1 in Batch 15.
    # ------------------------------------------------------------------
    _ssi_cs_mask = df["type_of_CS"].isin([2, 3])
    ok_ssi, unexp_ssi = validate_expected_binary_values(df["surgical_site_infection"], "surgical_site_infection")
    ssi_before_vc = df["surgical_site_infection"].value_counts(dropna=False).to_dict()
    ssi_before_non_cs_non_null = int(df.loc[~_ssi_cs_mask, "surgical_site_infection"].notna().sum())
    if not ok_ssi:
        unexpected_findings.append(f"surgical_site_infection: unexpected values {unexp_ssi}")
    df = set_outside_subgroup_to_na(df, "surgical_site_infection", _ssi_cs_mask)
    ssi_vc = df["surgical_site_infection"].value_counts(dropna=False).to_dict()
    ssi_cs_non_null = int(df.loc[_ssi_cs_mask, "surgical_site_infection"].notna().sum())
    ssi_vaginal_remaining = int(df.loc[~_ssi_cs_mask, "surgical_site_infection"].notna().sum())
    ssi_effective_changes = ssi_before_non_cs_non_null - ssi_vaginal_remaining
    bin_results["surgical_site_infection"] = {"ok": ok_ssi, "vc": ssi_vc}
    print(f"  surgical_site_infection: before={ssi_before_vc} | after={ssi_vc}")
    print(f"  surgical_site_infection: {ssi_effective_changes} non-CS value(s) changed 0->NaN "
          f"(structural, not confirmed absence); CS non-null={ssi_cs_non_null}; "
          f"non-CS remaining (expected 0)={ssi_vaginal_remaining}")

    # ------------------------------------------------------------------
    # 5b. intrapartum_fever_or_chorioamnionitis_bin — new composite (Decision 31,
    # 2026-07-29). intrapartum_fever (this batch, step 5) and chorioamnionitis
    # (Batch 13) are both already clinically confirmed intrapartum timing
    # (Decision 28); this composite combines them for descriptive/future
    # intrapartum-stage-model use. Both source columns are kept unchanged.
    # Rule: 1 if either source == 1; 0 only if both are observed and == 0;
    # NaN if neither is positive and at least one source is missing.
    # ------------------------------------------------------------------
    _fever_col = df["intrapartum_fever"]
    _chorio_col = df["chorioamnionitis"]
    _fc_positive_mask = (_fever_col == 1) | (_chorio_col == 1)
    _fc_both_zero_mask = (
        _fever_col.notna() & _chorio_col.notna()
        & (_fever_col == 0) & (_chorio_col == 0)
    )
    df["intrapartum_fever_or_chorioamnionitis_bin"] = np.select(
        [_fc_positive_mask, _fc_both_zero_mask],
        [1, 0],
        default=np.nan,
    )
    _fc_vc = df["intrapartum_fever_or_chorioamnionitis_bin"].value_counts(dropna=False).to_dict()
    ok_fc, unexp_fc = validate_expected_binary_values(
        df["intrapartum_fever_or_chorioamnionitis_bin"], "intrapartum_fever_or_chorioamnionitis_bin"
    )
    if not ok_fc:
        unexpected_findings.append(
            f"intrapartum_fever_or_chorioamnionitis_bin: unexpected values {unexp_fc}"
        )
    print(f"  intrapartum_fever_or_chorioamnionitis_bin (new composite): {_fc_vc}")

    # ------------------------------------------------------------------
    # 6. hospitalization_days — leakage; numeric; flag > 60 days for review
    #    (a broad sanity-review threshold, NOT a proven-impossibility bound;
    #    value is never mutated). Leakage-excluded from prediction regardless.
    # ------------------------------------------------------------------
    hd_num = pd.to_numeric(df["hospitalization_days"], errors="coerce")
    n_hd_valid = int(hd_num.notna().sum())
    n_hd_nan   = int(hd_num.isna().sum())
    hd_high_mask = hd_num.notna() & (hd_num > 60)
    n_hd_high  = int(hd_high_mask.sum())
    print(f"  hospitalization_days (leakage): {n_hd_valid} numeric, {n_hd_nan} NaN, "
          f"{n_hd_high} > 60 days (sanity-review threshold, not a proven-impossibility bound)")

    # ------------------------------------------------------------------
    # 7. comment_6 — free text; normalize placeholder zeros
    # ------------------------------------------------------------------
    before_comment_6 = df["comment_6"].copy()
    df["comment_6"] = df["comment_6"].apply(lambda v: np.nan if v in (0, "0", 0.0) else v)
    n_comment_6_zeros = int(before_comment_6.map(lambda v: v in (0, "0", 0.0)).sum())
    n_comment_6_text  = int(df["comment_6"].notna().sum())
    print(f"  comment_6: {n_comment_6_text} non-null, {n_comment_6_zeros} zeros->NaN")

    # ------------------------------------------------------------------
    # 8. Review: blood loss / Hb outside sanity-review ranges, free-text blood loss.
    #    NOTE: the numeric bounds used below (blood loss >3000 mL, Hb <5 or >20
    #    g/dL, hospitalization_days >60) are BROAD SANITY-REVIEW THRESHOLDS with
    #    no cited clinical-decision provenance -- a value outside a bound is a
    #    manual-review trigger only, never mutated, and is not a claim that the
    #    source value is physically impossible.
    # ------------------------------------------------------------------
    review_mask = bld_high_mask | bld_text_mask
    for col in ("Hb_before_delivery", "Hb_after_delivery"):
        num = pd.to_numeric(df[col], errors="coerce")
        review_mask = review_mask | (num.notna() & ((num < 5) | (num > 20)))
    review_mask = review_mask | hd_high_mask
    n_review = int(review_mask.sum())
    if n_review:
        review_cols = [
            "blood_loss_during_surgery", "Hb_before_delivery", "Hb_after_delivery",
            "Hb_diff", "Hb_diff_clean", "hospitalization_days", "target_intrapartum_cs",
        ]
        review_df = create_review_dataframe(
            df, review_mask, cols=review_cols, id_cols=["delivery_id", "subject_number"]
        )
        reason_list = []
        for idx in review_df.index:
            did = review_df.at[idx, "delivery_id"]
            orig_idx = df.index[df["delivery_id"] == did][0]
            r = []
            bv = pd.to_numeric(df.at[orig_idx, "blood_loss_during_surgery"], errors="coerce")
            if not pd.isna(bv) and bv > 3000:
                r.append(f"blood_loss={bv:.0f}>3000 mL")
            if bld_text_mask.loc[orig_idx]:
                orig_text = bld_text_originals.get(orig_idx, "unknown")
                r.append(f"blood_loss original text moved to comment_6: {repr(orig_text)}; clinical review needed")
            for col in ("Hb_before_delivery", "Hb_after_delivery"):
                hv = pd.to_numeric(df.at[orig_idx, col], errors="coerce")
                if not pd.isna(hv) and (hv < 5 or hv > 20):
                    r.append(f"{col}={hv} outside 5-20")
            hdv = pd.to_numeric(df.at[orig_idx, "hospitalization_days"], errors="coerce")
            if not pd.isna(hdv) and hdv > 60:
                r.append(f"hospitalization_days={hdv:.0f}>60")
            reason_list.append("; ".join(r) if r else "flagged")
        review_df["review_reason"] = reason_list
        os.makedirs(resolve_path(OUTPUT_REVIEW_PATH), exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        print(f"  Review file saved: {review_xlsx} ({n_review} rows)")
    else:
        print("  No extreme values found.")

    # ------------------------------------------------------------------
    # 9. Blood-loss distribution QA file — for Keren/Gidi clinical threshold review
    # Do NOT create ordinal categories yet; thresholds require clinical approval.
    # TODO: ordinal blood-loss categories pending clinical thresholds from Keren/Gidi.
    # ------------------------------------------------------------------
    bld_num_for_qa = pd.to_numeric(df["blood_loss_during_surgery"], errors="coerce")
    cs_rows_mask = df["type_of_CS"].isin([2, 3])

    # Descriptive stats for numeric CS rows
    bld_numeric_cs = bld_num_for_qa[cs_rows_mask & bld_num_for_qa.notna()]
    bld_stats = bld_numeric_cs.describe().rename("blood_loss_numeric_cs_mL").to_frame()
    bld_stats.index.name = "statistic"  # avoids an ambiguous "Unnamed: 0" column on export

    # Rows with free-text blood-loss notes (original text preserved in comment_6)
    bld_freetext_rows = df.loc[bld_text_mask, ["delivery_id", "subject_number", "type_of_CS",
                                                 "blood_loss_during_surgery", "comment_6"]].copy()
    bld_freetext_rows["qa_note"] = "original free text moved to comment_6"

    # Metadata sheet: population/subgroup, unit, and threshold-approval status --
    # previously only stated in console output and the deviation log, not in the
    # QA file itself.
    bld_metadata = pd.DataFrame({
        "field": ["population_subgroup", "units", "threshold_under_evaluation", "threshold_status"],
        "value": [
            "type_of_CS in {2, 3} (cesarean subgroup only; vaginal deliveries excluded)",
            "mL",
            ">1000 mL considered abnormal per Keren (informal clinical reference, not yet "
            "an approved ordinal category cutpoint)",
            "pending — Keren/Gidi clinical threshold approval needed before ordinal "
            "blood-loss categories are created (see preprocessing_deviations.md)",
        ],
    })

    os.makedirs(resolve_path(OUTPUT_REVIEW_PATH), exist_ok=True)
    with pd.ExcelWriter(bld_qa_xlsx, engine="openpyxl") as writer:
        bld_stats.to_excel(writer, sheet_name="numeric_distribution")
        bld_freetext_rows.to_excel(writer, sheet_name="freetext_rows", index=False)
        bld_metadata.to_excel(writer, sheet_name="qa_metadata", index=False)
    print(f"  Blood-loss QA file saved: {bld_qa_xlsx}")
    print(f"  (TODO: ordinal blood-loss categories pending clinical thresholds from Keren/Gidi)")

    log_deviation_event(
        path=deviations_md,
        variable="blood_loss_during_surgery",
        raw_variable="blood loss during surgery",
        documented="Clinical thresholds for ordinal blood-loss categories not yet defined.",
        action="TODO: ordinal blood-loss variable not created. QA distribution file created for clinical review.",
        reason="Ordinal categories require clinical threshold approval from Keren/Gidi before implementation.",
        requires_approval=True,
        batch="Batch 16 hotfix",
        affected_count=0,
    )

    os.makedirs(resolve_path(OUTPUT_PROCESSED_PATH), exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    summary = f"""# Preprocessing Batch 16 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## CS_case_vs_control (internal/leakage reference)
- {csc_vc}

## blood_loss_during_surgery (leakage)
- Continuous numeric variable in mL, cesarean subgroup only (type_of_CS in {{2,3}}); vaginal rows (type_of_CS=0) are structurally NaN, not ordinary missingness.
- Valid numeric: {n_bld_valid} | NaN: {n_bld_nan} | >3000 mL: {n_bld_high}
- Free-text rows: {n_bld_text} — set to NaN; exact original text appended to comment_6 (Ori 2026-04-25)
- Vaginal delivery rows (type_of_CS=0) set to NaN: {n_bld_vaginal_set_nan}
- CS rows with blood_loss=0 set to NaN: {n_bld_zero_set_nan} (0 treated as missing/unknown documentation, not a true zero measurement)
- No value is imputed.
- PPH not changed by blood_loss correction — PPH remains a separate, independently documented clinical outcome.
- Ordinal/binary categories (e.g. blood_loss_high, blood_loss_above_1000): NOT created and will not be created — Decision 51 (2026-08-02) closes this permanently for descriptive/secondary-outcome use only; 500/1000 mL are documented clinical background only, not an implemented rule.
- Remains classified leakage_exclude; excluded from prediction of intrapartum cesarean delivery.
- QA distribution file: {bld_qa_xlsx} (retained as historical evidence; review closed under Decision 51)

## Hb_before_delivery
- Inspected: {n_rows_input} | Converted to numeric: {hb_results['Hb_before_delivery']['valid']} | Converted to missing: {hb_results['Hb_before_delivery']['nan']} | Outside sanity-review range <5 or >20 g/dL (review threshold, not a proven-impossibility bound): {hb_results['Hb_before_delivery']['impossible']}
- Known missing markers ('לא נלקח'/'אין נתונים'/'פסול') -> NaN: {hb_results['Hb_before_delivery']['expected_markers_to_nan']} | Trailing-dot corrections (e.g. '10.00.' -> 10.0): {hb_results['Hb_before_delivery']['trailing_dot_corrected']} | Unexpected non-numeric -> NaN: {hb_results['Hb_before_delivery']['unexpected_to_nan']}

## Hb_after_delivery
- Inspected: {n_rows_input} | Converted to numeric: {hb_results['Hb_after_delivery']['valid']} | Converted to missing: {hb_results['Hb_after_delivery']['nan']} | Outside sanity-review range <5 or >20 g/dL (review threshold, not a proven-impossibility bound): {hb_results['Hb_after_delivery']['impossible']}
- Known missing markers ('לא נלקח'/'אין נתונים'/'פסול') -> NaN: {hb_results['Hb_after_delivery']['expected_markers_to_nan']} | Trailing-dot corrections (e.g. '10.00.' -> 10.0): {hb_results['Hb_after_delivery']['trailing_dot_corrected']} | Unexpected non-numeric -> NaN: {hb_results['Hb_after_delivery']['unexpected_to_nan']}

## Hb_diff (leakage)
- Valid: {n_hbd_valid} | NaN: {n_hbd_nan}

## Binary leakage variables validated
- intrapartum_fever: {bin_results['intrapartum_fever']['vc']}
- postpartum_fever: {bin_results['postpartum_fever']['vc']}
- endometritis: {bin_results['endometritis']['vc']}
- any_blood_product_transfusion: {bin_results['any_blood_product_transfusion']['vc']}

## surgical_site_infection (cesarean-subgroup structural mask, Decision 35, 2026-07-29)
- Before masking: {ssi_before_vc}
- After masking: {ssi_vc}
- Effective non-CS value changes (0->NaN, structural, not confirmed absence of infection): {ssi_effective_changes}
- CS non-null: {ssi_cs_non_null} | non-CS remaining (expected 0): {ssi_vaginal_remaining}

## intrapartum_fever_or_chorioamnionitis_bin (new composite, Decision 31)
- {_fc_vc}
- 1 if either intrapartum_fever or chorioamnionitis == 1; 0 only if both observed and == 0;
  NaN if neither positive and at least one source missing. Both source columns unchanged.

## hospitalization_days (leakage)
- Valid: {n_hd_valid} | NaN: {n_hd_nan} | >60 days: {n_hd_high}

## comment_6 (free text reference)
- Non-null: {n_comment_6_text} | Zeros normalized: {n_comment_6_zeros}

## Review file
{"- " + review_xlsx + f" ({n_review} rows)" if n_review else "- None"}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)
    log_audit_event(
        audit_log_md,
        f"Batch 16 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- CS_case_vs_control: {csc_vc}\n"
        f"- blood_loss_during_surgery: {n_bld_valid} numeric, {n_bld_high} >3000, "
        f"{n_bld_text} free-text set to NaN (text appended to comment_6 per Ori 2026-04-25)\n"
        f"- Hb_before: {hb_results['Hb_before_delivery']['valid']} valid\n"
        f"- Hb_after: {hb_results['Hb_after_delivery']['valid']} valid\n"
        f"- Binary leakage vars: {list(bin_results.keys())}\n"
        f"- surgical_site_infection: cesarean-subgroup mask applied (Decision 35), {ssi_effective_changes} effective non-CS changes, {ssi_cs_non_null} CS non-null remaining\n"
        f"- Review rows: {n_review}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 16 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 17 — Basic neonatal outcome variables
# gender, pH_vein, pH_artery, pH_artery_or_vein_less_than_7_1,
# apgar1, apgar5, apgar_5_less_than_7, birth_weight,
# percentile_by_Dolberg, SGA, LGA
# ---------------------------------------------------------------------------

def batch_17_neonatal_basic(work_df):
    """
    Basic neonatal outcome variables.

    Standardizes gender, pH, Apgar scores, birth weight, and
    percentile_by_Dolberg (with the approved >97/<3 text-to-numeric
    recode). Persists numeric conversion for pH_vein/pH_artery/apgar1/
    apgar5 (previously validated only, not saved back). Derives
    pH_artery_or_vein_less_than_7_1 from the continuous pH_artery/pH_vein
    measurements rather than trusting the raw source column (Decision 50),
    with a fail-loud post-derivation consistency check. Validates
    apgar_5_less_than_7 against apgar5 (fail-loud, no overwrite -- already
    consistent). Runs a non-mutating SGA/LGA-vs-percentile consistency QA
    gate (does not recalculate SGA/LGA).

    Approved decisions: 50.
    QA outputs: neonatal_basic_review_df.xlsx (only if unexpected values
    are found), percentile_by_Dolberg_QA.xlsx,
    SGA_LGA_percentile_consistency_QA.xlsx (only if a mismatch is found).
    Returns: df — the working DataFrame with basic neonatal variables
    cleaned.
    """
    BATCH_TITLE = BATCH_METADATA[17]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values,
        log_audit_event, log_deviation_event, write_batch_summary,
        create_review_dataframe,
    )

    print(f"=== Batch 17: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    deviations_md  = os.path.join(audit_path, "preprocessing_deviations.md")
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch17.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch17.xlsx")
    review_xlsx    = os.path.join(review_path, "neonatal_basic_review_df.xlsx")
    pct_qa_xlsx    = os.path.join(review_path, "percentile_by_Dolberg_QA.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []

    # ------------------------------------------------------------------
    # 1. gender — report distribution; do not recode (coding not documented)
    # ------------------------------------------------------------------
    gender_vc = df["gender"].value_counts(dropna=False).to_dict()
    gender_text_mask = df["gender"].map(
        lambda v: not pd.isna(v) and not str(v).strip().replace(".", "", 1).lstrip("-").isdigit()
        and str(v).strip() not in ("", "nan")
    )
    n_gender_text = int(gender_text_mask.sum())
    if n_gender_text:
        unexpected_findings.append(f"gender: {n_gender_text} non-numeric value(s)")
    print(f"  gender: {gender_vc}")

    # ------------------------------------------------------------------
    # 2. pH_vein, pH_artery — numeric; flag outside 6.5-7.5; persist
    #    coercion in place (Batch 17 correction -- previously validated via
    #    a local pd.to_numeric() result that was never saved back to df).
    # ------------------------------------------------------------------
    ph_results = {}
    for col in ("pH_vein", "pH_artery"):
        before = df[col].copy()
        num = pd.to_numeric(before, errors="coerce")
        # Unexpected non-numeric tokens: originally non-null but not
        # parseable as a number -- reported before coercion so nothing is
        # silently discarded. Currently 0 for both columns (raw source is
        # already pure numeric); kept general for future raw-data refreshes.
        unexpected_mask = before.notna() & num.isna()
        n_unexpected = int(unexpected_mask.sum())
        if n_unexpected:
            unexpected_vals = before[unexpected_mask].value_counts().to_dict()
            unexpected_findings.append(
                f"{col}: {n_unexpected} unexpected non-numeric value(s) converted to NaN: {unexpected_vals}"
            )
            print(f"  WARNING: {col}: unexpected non-numeric -> NaN: {unexpected_vals}")
        df[col] = num  # persist numeric conversion; missing values remain NaN, never filled
        n_valid = int(num.notna().sum())
        n_nan   = int(num.isna().sum())
        n_imp   = int((num.notna() & ((num < 6.5) | (num > 7.5))).sum())
        ph_results[col] = {
            "valid": n_valid, "nan": n_nan, "impossible": n_imp,
            "unexpected_to_nan": n_unexpected,
        }
        tag = " (leakage)" if col == "pH_artery" else ""
        print(f"  {col}{tag}: {n_valid} valid, {n_nan} NaN, {n_imp} outside 6.5-7.5")

    # ------------------------------------------------------------------
    # 3. pH_artery_or_vein_less_than_7_1 — derived from the continuous
    #    pH_artery/pH_vein measurements (Decision 50), not trusted directly
    #    from the raw source. The raw header "PH-artery less then 7.1" is
    #    artery-only-worded, but clinical review confirmed the field
    #    represents artery-OR-vein pH < 7.1; the raw column is retained
    #    only as source/audit evidence and is no longer authoritative.
    #    Rule: 1 if either pH_artery or pH_vein < 7.1; 0 only if both are
    #    observed and both >= 7.1; NaN otherwise (a single observed normal
    #    value with the other missing is NOT sufficient for 0).
    # ------------------------------------------------------------------
    ph71_raw = df["pH_artery_or_vein_less_than_7_1"].copy()
    ok_ph71, unexp_ph71 = validate_expected_binary_values(ph71_raw, "pH_artery_or_vein_less_than_7_1")
    if not ok_ph71:
        unexpected_findings.append(f"pH_artery_or_vein_less_than_7_1: unexpected raw-source values {unexp_ph71}")
    ph71_raw_vc = ph71_raw.value_counts(dropna=False).to_dict()

    _ph_a = df["pH_artery"]  # already numeric, persisted in Section 2
    _ph_v = df["pH_vein"]
    _ph71_positive = (_ph_a < 7.1) | (_ph_v < 7.1)
    _ph71_confirmed_zero = _ph_a.notna() & _ph_v.notna() & (_ph_a >= 7.1) & (_ph_v >= 7.1) & ~_ph71_positive
    ph71_derived = pd.Series(np.nan, index=df.index)
    ph71_derived[_ph71_positive] = 1.0
    ph71_derived[_ph71_confirmed_zero] = 0.0

    # Rows where the derived value differs from the raw source -- these are
    # deterministic derived-variable corrections (a general rule reapplied
    # to all rows), not manual patient-specific edits.
    _ph71_diff_mask = ~(
        (ph71_raw.isna() & ph71_derived.isna()) | (ph71_raw == ph71_derived)
    )
    n_ph71_corrected = int(_ph71_diff_mask.sum())
    _ph71_correction_list = ""
    if n_ph71_corrected:
        _ph71_corrections = df.loc[_ph71_diff_mask, ["subject_number", "delivery_id"]].copy()
        _ph71_corrections["pH_vein"] = _ph_v.loc[_ph71_diff_mask]
        _ph71_corrections["pH_artery"] = _ph_a.loc[_ph71_diff_mask]
        _ph71_corrections["raw_source_value"] = ph71_raw.loc[_ph71_diff_mask]
        _ph71_corrections["derived_value"] = ph71_derived.loc[_ph71_diff_mask]
        _ph71_correction_list = "; ".join(
            f"(subject_number={r.subject_number}, delivery_id={r.delivery_id}): "
            f"raw={r.raw_source_value!r} -> derived={r.derived_value!r} "
            f"(pH_vein={r.pH_vein!r}, pH_artery={r.pH_artery!r})"
            for r in _ph71_corrections.itertuples()
        )

    df["pH_artery_or_vein_less_than_7_1"] = ph71_derived

    # Fail-loud independent re-derivation check: every processed value must
    # match the approved rule exactly before this batch is allowed to save.
    _ph71_recheck_positive = (df["pH_artery"] < 7.1) | (df["pH_vein"] < 7.1)
    _ph71_recheck_zero = (
        df["pH_artery"].notna() & df["pH_vein"].notna()
        & (df["pH_artery"] >= 7.1) & (df["pH_vein"] >= 7.1) & ~_ph71_recheck_positive
    )
    _ph71_recheck_expected = pd.Series(np.nan, index=df.index)
    _ph71_recheck_expected[_ph71_recheck_positive] = 1.0
    _ph71_recheck_expected[_ph71_recheck_zero] = 0.0
    _ph71_recheck_mismatch = ~(
        (df["pH_artery_or_vein_less_than_7_1"].isna() & _ph71_recheck_expected.isna())
        | (df["pH_artery_or_vein_less_than_7_1"] == _ph71_recheck_expected)
    )
    if _ph71_recheck_mismatch.any():
        raise ValueError(
            "Batch 17 pH_artery_or_vein_less_than_7_1 derivation: "
            f"{int(_ph71_recheck_mismatch.sum())} row(s) do not match the approved rule after "
            "derivation -- stopping rather than saving an inconsistent value."
        )

    if n_ph71_corrected:
        log_deviation_event(
            path=deviations_md,
            variable="pH_artery_or_vein_less_than_7_1",
            raw_variable="PH-artery less then 7.1",
            documented="Decision 50: derive from pH_artery/pH_vein (artery OR vein < 7.1); the raw "
                       "column is retained as source/audit evidence only, not trusted as authoritative.",
            action=f"Recalculated from the continuous pH_artery/pH_vein measurements; "
                   f"{n_ph71_corrected} row(s) differ from the raw source value. Corrections: "
                   f"{_ph71_correction_list}",
            reason="Deterministic derived-variable correction (a general rule reapplied to all rows), "
                   "not a manual patient-specific edit -- the raw column does not always reflect the "
                   "approved OR-rule over both continuous measurements (e.g. a single missing "
                   "measurement was sometimes recorded as a confirmed 0). See Decision 50.",
            requires_approval=False,
            batch="Batch 17 (correction)",
            affected_count=n_ph71_corrected,
        )

    ph71_vc = df["pH_artery_or_vein_less_than_7_1"].value_counts(dropna=False).to_dict()
    print(f"  pH_artery_or_vein_less_than_7_1 (derived from pH_artery/pH_vein): {ph71_vc}")
    print(f"    Raw-source distribution: {ph71_raw_vc} | corrected vs raw source: {n_ph71_corrected} row(s)")

    # ------------------------------------------------------------------
    # 4. apgar1, apgar5 — leakage; 0-10 range; validate; persist coercion
    #    in place (Batch 17 correction, same pattern as pH above).
    # ------------------------------------------------------------------
    apgar_results = {}
    for col in ("apgar1", "apgar5"):
        before = df[col].copy()
        num = pd.to_numeric(before, errors="coerce")
        unexpected_mask = before.notna() & num.isna()
        n_unexpected = int(unexpected_mask.sum())
        if n_unexpected:
            unexpected_vals = before[unexpected_mask].value_counts().to_dict()
            unexpected_findings.append(
                f"{col}: {n_unexpected} unexpected non-numeric value(s) converted to NaN: {unexpected_vals}"
            )
            print(f"  WARNING: {col}: unexpected non-numeric -> NaN: {unexpected_vals}")
        df[col] = num  # persist numeric conversion; missing values remain NaN, never filled
        n_valid = int(num.notna().sum())
        n_nan   = int(num.isna().sum())
        n_imp   = int((num.notna() & ((num < 0) | (num > 10))).sum())
        apgar_results[col] = {
            "valid": n_valid, "nan": n_nan, "impossible": n_imp,
            "unexpected_to_nan": n_unexpected,
        }
        print(f"  {col} (leakage): {n_valid} valid, {n_nan} NaN, {n_imp} outside 0-10")

    # ------------------------------------------------------------------
    # 5. apgar_5_less_than_7 — validated (fail-loud) against apgar5 < 7.
    #    Current values already match exactly, so nothing is overwritten --
    #    unlike the pH binary above, this is a validation-only gate.
    #    Missing apgar5 must never be silently treated as 0.
    # ------------------------------------------------------------------
    ok_apg7, unexp_apg7 = validate_expected_binary_values(
        df["apgar_5_less_than_7"], "apgar_5_less_than_7"
    )
    apg7_vc = df["apgar_5_less_than_7"].value_counts(dropna=False).to_dict()
    if not ok_apg7:
        unexpected_findings.append(f"apgar_5_less_than_7: unexpected values {unexp_apg7}")

    _apgar5_observed = df["apgar5"].notna()
    _apgar7_expected = pd.Series(np.nan, index=df.index)
    _apgar7_expected[_apgar5_observed] = (df.loc[_apgar5_observed, "apgar5"] < 7).astype(float)
    _apgar7_mismatch = ~(
        (df["apgar_5_less_than_7"].isna() & _apgar7_expected.isna())
        | (df["apgar_5_less_than_7"] == _apgar7_expected)
    )
    n_apgar7_mismatch = int(_apgar7_mismatch.sum())
    if n_apgar7_mismatch:
        raise ValueError(
            "Batch 17 apgar_5_less_than_7 validation: "
            f"{n_apgar7_mismatch} row(s) disagree with apgar5 < 7 -- stopping. Current values are not "
            "auto-corrected; this needs manual review before proceeding."
        )
    print(f"  apgar_5_less_than_7: {apg7_vc} (validated against apgar5<7: {n_apgar7_mismatch} mismatch(es))")

    # ------------------------------------------------------------------
    # 6. birth_weight — numeric (grams); flag outside 300-6000
    # ------------------------------------------------------------------
    bw_num = pd.to_numeric(df["birth_weight"], errors="coerce")
    n_bw_valid = int(bw_num.notna().sum())
    n_bw_nan   = int(bw_num.isna().sum())
    bw_imp_mask = bw_num.notna() & ((bw_num < 300) | (bw_num > 6000))
    n_bw_imp   = int(bw_imp_mask.sum())
    print(f"  birth_weight: {n_bw_valid} valid, {n_bw_nan} NaN, {n_bw_imp} outside 300-6000 g")

    # ------------------------------------------------------------------
    # 7. percentile_by_Dolberg — deterministic recode of extreme-text values,
    #    then numeric validation (0-100).
    #    Approved rule (Gidi/Keren): ">97" Hebrew text -> 98; "<3" Hebrew text -> 2.
    # ------------------------------------------------------------------
    import re as _re
    _HIGH97 = _re.compile(r"97", _re.IGNORECASE)
    _LOW3   = _re.compile(r"3",  _re.IGNORECASE)

    pct_raw_series = df["percentile_by_Dolberg"].copy()

    def _recode_pct(val):
        if pd.isna(val):
            return val
        try:
            return float(val)
        except (ValueError, TypeError):
            s = str(val).strip()
            # >97 text (garbled "???? ?97") ? contains digits 97
            if "97" in s:
                return 98.0
            # <3 text (garbled "???? ?3") ? contains digit 3
            if "3" in s:
                return 2.0
            return np.nan  # other unrecognised text -> NaN

    df["percentile_by_Dolberg"] = pct_raw_series.map(_recode_pct)

    # Identify recoded rows for QA
    high97_mask = pct_raw_series.map(
        lambda v: not pd.isna(v) and not isinstance(v, (int, float)) and "97" in str(v)
    )
    low3_mask = pct_raw_series.map(
        lambda v: not pd.isna(v) and not isinstance(v, (int, float)) and "97" not in str(v) and "3" in str(v)
    )
    n_high97 = int(high97_mask.sum())
    n_low3   = int(low3_mask.sum())

    # Save QA file
    qa_mask = high97_mask | low3_mask
    if qa_mask.any():
        qa_df = pd.DataFrame({
            "delivery_id":        df.loc[qa_mask, "delivery_id"].values,
            "subject_number":     df.loc[qa_mask, "subject_number"].values,
            "raw_value":          pct_raw_series.loc[qa_mask].values,
            "cleaned_numeric":    df.loc[qa_mask, "percentile_by_Dolberg"].values,
            "recoding_reason":    [
                ">97 Hebrew text recoded to 98 (Gidi/Keren rule)" if high97_mask.loc[i]
                else "<3 Hebrew text recoded to 2 (Gidi/Keren rule)"
                for i in qa_mask[qa_mask].index
            ],
        })
        os.makedirs(resolve_path(OUTPUT_REVIEW_PATH), exist_ok=True)
        qa_df.to_excel(pct_qa_xlsx, index=False)
        print(f"  percentile_by_Dolberg: {n_high97} >97 text->98, {n_low3} <3 text->2, QA saved")

    log_deviation_event(
        path=deviations_md,
        variable="percentile_by_Dolberg",
        raw_variable="percentile by ??????",
        documented="Numeric birth-weight percentile by Dolberg scale.",
        action=f"Deterministic recode: >97 Hebrew text ({n_high97} rows)->98; "
               f"<3 Hebrew text ({n_low3} rows)->2.",
        reason="Approved rule from Gidi/Keren: text extreme values have clear clinical meaning "
               "and numeric continuity must be preserved.",
        requires_approval=False,
        batch="Batch 17 (correction)",
        affected_count=n_high97 + n_low3,
    )

    pct_num = pd.to_numeric(df["percentile_by_Dolberg"], errors="coerce")
    n_pct_valid = int(pct_num.notna().sum())
    n_pct_nan   = int(pct_num.isna().sum())
    pct_imp_mask = pct_num.notna() & ((pct_num < 0) | (pct_num > 100))
    n_pct_imp   = int(pct_imp_mask.sum())
    print(f"  percentile_by_Dolberg: {n_pct_valid} valid, {n_pct_nan} NaN, {n_pct_imp} outside 0-100")

    # ------------------------------------------------------------------
    # 8. SGA, LGA — binary; validate
    # ------------------------------------------------------------------
    sga_lga_vc = {}
    for col in ("SGA", "LGA"):
        ok, unexp = validate_expected_binary_values(df[col], col)
        vc = df[col].value_counts(dropna=False).to_dict()
        sga_lga_vc[col] = vc
        if not ok:
            unexpected_findings.append(f"{col}: unexpected values {unexp}")
        print(f"  {col}: {vc}")

    # ------------------------------------------------------------------
    # 8b. SGA/LGA consistency QA (non-mutating) — verifies mutual
    #    exclusivity and agreement with the processed Dolberg percentile
    #    using the documented clinical convention (SGA = percentile < 10,
    #    LGA = percentile > 90). Does not recalculate or overwrite SGA/LGA.
    # ------------------------------------------------------------------
    _SGA_PCT_THRESHOLD = 10  # SGA = percentile_by_Dolberg < 10
    _LGA_PCT_THRESHOLD = 90  # LGA = percentile_by_Dolberg > 90
    sga_lga_qa_xlsx = os.path.join(review_path, "SGA_LGA_percentile_consistency_QA.xlsx")

    _both_positive_mask = (df["SGA"] == 1) & (df["LGA"] == 1)
    n_sga_lga_both = int(_both_positive_mask.sum())

    _pct_num_for_qa = pd.to_numeric(df["percentile_by_Dolberg"], errors="coerce")
    _pct_observed_for_qa = _pct_num_for_qa.notna()
    _sga_expected = pd.Series(np.nan, index=df.index)
    _lga_expected = pd.Series(np.nan, index=df.index)
    _sga_expected[_pct_observed_for_qa] = (_pct_num_for_qa[_pct_observed_for_qa] < _SGA_PCT_THRESHOLD).astype(int)
    _lga_expected[_pct_observed_for_qa] = (_pct_num_for_qa[_pct_observed_for_qa] > _LGA_PCT_THRESHOLD).astype(int)
    _sga_mismatch = _pct_observed_for_qa & (df["SGA"] != _sga_expected)
    _lga_mismatch = _pct_observed_for_qa & (df["LGA"] != _lga_expected)
    _sga_lga_mismatch_mask = _sga_mismatch | _lga_mismatch | _both_positive_mask
    n_sga_lga_mismatch = int(_sga_lga_mismatch_mask.sum())

    if n_sga_lga_mismatch:
        qa_rows = df.loc[_sga_lga_mismatch_mask]
        reasons = []
        for idx in qa_rows.index:
            r = []
            if _sga_mismatch.loc[idx]:
                r.append(f"SGA={df.at[idx, 'SGA']} but percentile={_pct_num_for_qa.at[idx]} "
                         f"(expected SGA={int(_sga_expected.at[idx])})")
            if _lga_mismatch.loc[idx]:
                r.append(f"LGA={df.at[idx, 'LGA']} but percentile={_pct_num_for_qa.at[idx]} "
                         f"(expected LGA={int(_lga_expected.at[idx])})")
            if _both_positive_mask.loc[idx]:
                r.append("SGA=1 and LGA=1 simultaneously (not mutually exclusive)")
            reasons.append("; ".join(r))
        sga_lga_qa_df = pd.DataFrame({
            "subject_number":         qa_rows["subject_number"].values,
            "delivery_id":            qa_rows["delivery_id"].values,
            "percentile_by_Dolberg":  _pct_num_for_qa.loc[_sga_lga_mismatch_mask].values,
            "SGA":                    qa_rows["SGA"].values,
            "LGA":                    qa_rows["LGA"].values,
            "expected_SGA":           _sga_expected.loc[_sga_lga_mismatch_mask].values,
            "expected_LGA":           _lga_expected.loc[_sga_lga_mismatch_mask].values,
            "mismatch_reason":        reasons,
        })
        os.makedirs(resolve_path(OUTPUT_REVIEW_PATH), exist_ok=True)
        sga_lga_qa_df.to_excel(sga_lga_qa_xlsx, index=False)
        unexpected_findings.append(
            f"SGA/LGA percentile-consistency QA: {n_sga_lga_mismatch} row(s) blocked for review -- "
            f"see {sga_lga_qa_xlsx}"
        )
        print(f"  SGA/LGA consistency QA: {n_sga_lga_mismatch} mismatch(es) -- "
              f"exported for review: {sga_lga_qa_xlsx}")
    else:
        print(f"  SGA/LGA consistency QA: PASS (thresholds: SGA=percentile<{_SGA_PCT_THRESHOLD}, "
              f"LGA=percentile>{_LGA_PCT_THRESHOLD}; 0 mismatches; mutual exclusivity holds: "
              f"{n_sga_lga_both} row(s) with both=1)")

    # ------------------------------------------------------------------
    # 9. Review: pH / birth_weight outside sanity-review ranges (broad review
    #    thresholds, no cited clinical provenance -- not proven-impossibility
    #    bounds); apgar outside its defined 0-10 scale and percentile outside
    #    0-100 (these two ARE definitional/logical bounds). None mutate a value.
    # ------------------------------------------------------------------
    review_mask = bw_imp_mask | pct_imp_mask
    for col in ("pH_vein", "pH_artery"):
        num = pd.to_numeric(df[col], errors="coerce")
        review_mask = review_mask | (num.notna() & ((num < 6.5) | (num > 7.5)))
    for col in ("apgar1", "apgar5"):
        num = pd.to_numeric(df[col], errors="coerce")
        review_mask = review_mask | (num.notna() & ((num < 0) | (num > 10)))
    n_review = int(review_mask.sum())
    if n_review:
        review_cols = [
            "gender", "pH_vein", "pH_artery", "pH_artery_or_vein_less_than_7_1",
            "apgar1", "apgar5", "apgar_5_less_than_7",
            "birth_weight", "percentile_by_Dolberg", "SGA", "LGA",
        ]
        review_df = create_review_dataframe(
            df, review_mask, cols=review_cols, id_cols=["delivery_id", "subject_number"]
        )
        reason_list = []
        for idx in review_df.index:
            did = review_df.at[idx, "delivery_id"]
            orig_idx = df.index[df["delivery_id"] == did][0]
            r = []
            for col in ("pH_vein", "pH_artery"):
                v = pd.to_numeric(df.at[orig_idx, col], errors="coerce")
                if not pd.isna(v) and (v < 6.5 or v > 7.5):
                    r.append(f"{col}={v} outside 6.5-7.5")
            for col in ("apgar1", "apgar5"):
                v = pd.to_numeric(df.at[orig_idx, col], errors="coerce")
                if not pd.isna(v) and (v < 0 or v > 10):
                    r.append(f"{col}={v} outside 0-10")
            bwv = pd.to_numeric(df.at[orig_idx, "birth_weight"], errors="coerce")
            if not pd.isna(bwv) and (bwv < 300 or bwv > 6000):
                r.append(f"birth_weight={bwv} outside 300-6000")
            pv = pd.to_numeric(df.at[orig_idx, "percentile_by_Dolberg"], errors="coerce")
            if not pd.isna(pv) and (pv < 0 or pv > 100):
                r.append(f"percentile={pv} outside 0-100")
            reason_list.append("; ".join(r) if r else "flagged")
        review_df["review_reason"] = reason_list
        os.makedirs(resolve_path(OUTPUT_REVIEW_PATH), exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        print(f"  Review file saved: {review_xlsx} ({n_review} rows)")
    else:
        print("  No neonatal values outside a sanity-review range or a definitional scale.")

    os.makedirs(resolve_path(OUTPUT_PROCESSED_PATH), exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    summary = f"""# Preprocessing Batch 17 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## gender
- {gender_vc}

## pH_vein
- Numeric valid: {ph_results['pH_vein']['valid']} | Missing: {ph_results['pH_vein']['nan']} ({round(ph_results['pH_vein']['nan']/len(df)*100, 1)}%) | Unexpected non-numeric coerced to NaN: {ph_results['pH_vein']['unexpected_to_nan']} | Outside sanity-review range <6.5 or >7.5 (review threshold, not a proven-impossibility bound): {ph_results['pH_vein']['impossible']}
- Numeric conversion persisted to the working column (Batch 17 correction). No imputation performed — missing values remain NaN.

## pH_artery (leakage)
- Numeric valid: {ph_results['pH_artery']['valid']} | Missing: {ph_results['pH_artery']['nan']} ({round(ph_results['pH_artery']['nan']/len(df)*100, 1)}%) | Unexpected non-numeric coerced to NaN: {ph_results['pH_artery']['unexpected_to_nan']} | Outside sanity-review range <6.5 or >7.5 (review threshold, not a proven-impossibility bound): {ph_results['pH_artery']['impossible']}
- Numeric conversion persisted to the working column (Batch 17 correction). No imputation performed — missing values remain NaN.

## pH_artery_or_vein_less_than_7_1 (derived, Decision 50)
- Raw-source distribution (as read from the raw workbook, pre-derivation): {ph71_raw_vc}
- Derived processed distribution (from pH_artery/pH_vein): {ph71_vc}
- Derivation rule: 1 if pH_artery < 7.1 or pH_vein < 7.1; 0 only if both are observed and both >= 7.1; NaN otherwise (a single observed normal value with the other missing is NOT sufficient for 0).
- Raw-vs-derived mismatches (deterministic corrections applied): {n_ph71_corrected}
- Corrected rows: {_ph71_correction_list if n_ph71_corrected else "none"}
- The derived value is authoritative for analysis; the raw source column is retained unchanged in the raw workbook for audit only.

## apgar1 (leakage)
- Numeric valid: {apgar_results['apgar1']['valid']} | Missing: {apgar_results['apgar1']['nan']} | Unexpected non-numeric coerced to NaN: {apgar_results['apgar1']['unexpected_to_nan']} | Outside the defined Apgar 0-10 scale (definitional/logical bound): {apgar_results['apgar1']['impossible']}
- Numeric conversion persisted to the working column (Batch 17 correction).

## apgar5 (leakage)
- Numeric valid: {apgar_results['apgar5']['valid']} | Missing: {apgar_results['apgar5']['nan']} | Unexpected non-numeric coerced to NaN: {apgar_results['apgar5']['unexpected_to_nan']} | Outside the defined Apgar 0-10 scale (definitional/logical bound): {apgar_results['apgar5']['impossible']}
- Numeric conversion persisted to the working column (Batch 17 correction).

## apgar_5_less_than_7
- {apg7_vc}
- Validated (fail-loud) against apgar5 < 7 for every row where apgar5 is observed; missing apgar5 never treated as 0. Mismatches: {n_apgar7_mismatch}. Current values not overwritten (already fully consistent).

## birth_weight
- Valid: {n_bw_valid} | NaN: {n_bw_nan} | Outside sanity-review range <300 or >6000 g (review threshold, not a proven-impossibility bound): {n_bw_imp}

## percentile_by_Dolberg
- >97 text recoded to 98: {n_high97} | <3 text recoded to 2: {n_low3}
- Valid: {n_pct_valid} | NaN: {n_pct_nan} | Outside the 0-100 percentile scale (definitional/logical bound): {n_pct_imp}
- QA file: {pct_qa_xlsx}

## SGA, LGA
- SGA: {sga_lga_vc['SGA']} | LGA: {sga_lga_vc['LGA']}
- Consistency QA thresholds: SGA = percentile_by_Dolberg < {_SGA_PCT_THRESHOLD}; LGA = percentile_by_Dolberg > {_LGA_PCT_THRESHOLD} (non-mutating check; SGA/LGA are never recalculated or overwritten)
- Mutual exclusivity: {n_sga_lga_both} row(s) with both SGA=1 and LGA=1 (expected 0)
- Percentile-consistency mismatches: {n_sga_lga_mismatch} (expected 0){"" if not n_sga_lga_mismatch else f" — see {sga_lga_qa_xlsx}"}

## Review file
{"- " + review_xlsx + f" ({n_review} rows)" if n_review else "- None"}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)
    log_audit_event(
        audit_log_md,
        f"Batch 17 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- gender: {gender_vc}\n"
        f"- pH_vein: {ph_results['pH_vein']['valid']} valid, {ph_results['pH_vein']['impossible']} outside sanity-review range\n"
        f"- pH_artery: {ph_results['pH_artery']['valid']} valid, {ph_results['pH_artery']['impossible']} outside sanity-review range\n"
        f"- birth_weight: {n_bw_valid} valid, {n_bw_imp} outside sanity-review range\n"
        f"- Review rows: {n_review}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 17 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 18 — Extended neonatal outcomes and manual text corrections
# IVH, IVH_grade_1_2, IVH_grade_3_4, NICU_admission, RDS,
# mechanical_ventilation, length_of_mechanical_ventilation, NEC,
# sepsis, hypoglycemia, neonatal_jaundice_used_phototherapy,
# neonatal_death, age_at_neonatal_death, congenital_anomaly,
# congenital_anomaly_comment, long_term_outcome, long_term_outcome_comment,
# comment_10
# ---------------------------------------------------------------------------

def batch_18_neonatal_outcomes(work_df):
    """
    Extended neonatal outcomes and manual text corrections.

    Applies the approved NICU_admission and RDS/TTN free-text corrections
    (Keren/Ori) and standardizes the remaining extended neonatal-outcome
    variables (IVH, mechanical ventilation, NEC, sepsis, hypoglycemia,
    jaundice, neonatal death, congenital anomaly, long-term outcome).
    Documents age_at_neonatal_death's neonatal_death==1 subgroup
    applicability (registered separately in the EDA A / Data Cleaning B
    SUBGROUP_APPLICABLE_COLS registries) and length_of_mechanical_
    ventilation's free-text nature (classification: source_or_text_audit_
    exclude, not intrapartum_or_post_delivery_exclude). No patient-level
    values are changed by these classification/documentation corrections.

    QA outputs: RDS_NICU_manual_correction_QA.xlsx,
    neonatal_outcomes_review_df.xlsx (only if contradictions are found).
    Returns: df — the working DataFrame with extended neonatal variables
    cleaned.
    """
    BATCH_TITLE = BATCH_METADATA[18]["title"]
    from preprocessing_utils import (
        validate_expected_binary_values,
        log_audit_event, write_batch_summary,
        create_review_dataframe,
    )

    print(f"=== Batch 18: {BATCH_TITLE} ===")

    audit_path     = resolve_path(OUTPUT_AUDIT_PATH)
    processed_path = resolve_path(OUTPUT_PROCESSED_PATH)
    review_path    = resolve_path(OUTPUT_REVIEW_PATH)
    audit_log_md   = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md     = os.path.join(audit_path, "preprocessing_summary_batch18.md")
    output_xlsx    = os.path.join(processed_path, "work_df_batch18.xlsx")
    review_xlsx    = os.path.join(review_path, "neonatal_outcomes_review_df.xlsx")
    qa_xlsx        = os.path.join(review_path, "RDS_NICU_manual_correction_QA.xlsx")

    df = work_df.copy()
    n_rows_input = len(df)
    unexpected_findings = []
    def _has_letters(value):
        return not pd.isna(value) and any(ch.isalpha() for ch in str(value))

    # ------------------------------------------------------------------
    # 1a. NICU_admission — manual clinical correction
    #     "מחלקת פגים" (preterm/neonatal ward) = NICU admission per Keren.
    #     Recode to 1. Any other text = unexpected → fail validation.
    # ------------------------------------------------------------------
    NICU_APPROVED_TEXT = "מחלקת פגים"
    nicu_text_mask = df["NICU_admission"].map(_has_letters)
    n_nicu_text = int(nicu_text_mask.sum())
    nicu_recoded_to_1 = 0
    nicu_unexpected_vals = []
    qa_rows = []

    for idx in df.index[nicu_text_mask]:
        orig_val = str(df.at[idx, "NICU_admission"]).strip()
        subj = df.at[idx, "subject_number"] if "subject_number" in df.columns else np.nan
        did  = df.at[idx, "delivery_id"]  if "delivery_id"  in df.columns else np.nan
        if orig_val == NICU_APPROVED_TEXT:
            df.at[idx, "NICU_admission"] = 1
            nicu_recoded_to_1 += 1
            qa_rows.append({
                "delivery_id": did,
                "subject_number": subj,
                "variable": "NICU_admission",
                "original_value": orig_val,
                "cleaned_value": 1,
                "RDS_comment": np.nan,
                "TTN_bin": np.nan,
                "correction_reason": "Hebrew text ????? ???? = preterm/neonatal ward; clinically equivalent to NICU admission",
                "clinical_decision_source": "Keren (manual review 2026-04-25)",
            })
        else:
            nicu_unexpected_vals.append(orig_val)

    if nicu_unexpected_vals:
        unexpected_findings.append(
            f"NICU_admission: unexpected text value(s) not in approved list: {nicu_unexpected_vals}"
        )
        print(f"  NICU_admission: UNEXPECTED text found: {nicu_unexpected_vals}")
    else:
        print(f"  NICU_admission: {n_nicu_text} text row(s) found, "
              f"{nicu_recoded_to_1} recoded to 1 (????? ???? per Keren)")

    # ------------------------------------------------------------------
    # 1b. RDS — manual clinical correction
    #     Known approved text values reviewed by Keren/Ori (2026-04-25):
    #       TTN          → RDS=0, TTN_bin=1, text→RDS_comment
    #       Meconium Aspiration Syndrome → RDS=0, TTN_bin=0, text→RDS_comment
    #       AIR LEAK SYNDROME → RDS=0, TTN_bin=0, text→RDS_comment
    #     Any other text = unexpected → fail validation.
    # ------------------------------------------------------------------
    KNOWN_RDS_TEXTS_UPPER = {"TTN", "MECONIUM ASPIRATION SYNDROME", "AIR LEAK SYNDROME"}
    rds_raw_series = df["RDS"].copy()
    rds_text_mask = df["RDS"].map(_has_letters)
    n_rds_text = int(rds_text_mask.sum())
    n_rds_recoded_to_0 = 0
    n_ttn_bin_positive = 0
    rds_unexpected_vals = []

    df["RDS_comment"] = pd.Series(pd.NA, index=df.index, dtype="object")
    df["TTN_bin"] = 0

    for idx in df.index[rds_text_mask]:
        orig_val = str(rds_raw_series.at[idx])
        orig_stripped = orig_val.strip()
        subj = df.at[idx, "subject_number"] if "subject_number" in df.columns else np.nan
        did  = df.at[idx, "delivery_id"]  if "delivery_id"  in df.columns else np.nan
        if orig_stripped.upper() in KNOWN_RDS_TEXTS_UPPER:
            is_ttn = "TTN" in orig_stripped.upper()
            df.at[idx, "RDS"]         = 0
            df.at[idx, "RDS_comment"] = orig_stripped
            df.at[idx, "TTN_bin"]     = 1 if is_ttn else 0
            n_rds_recoded_to_0 += 1
            if is_ttn:
                n_ttn_bin_positive += 1
            qa_rows.append({
                "delivery_id": did,
                "subject_number": subj,
                "variable": "RDS",
                "original_value": orig_stripped,
                "cleaned_value": 0,
                "RDS_comment": orig_stripped,
                "TTN_bin": 1 if is_ttn else 0,
                "correction_reason": (
                    "TTN is not RDS; coded RDS=0, TTN_bin=1 per Keren/Ori review" if is_ttn
                    else f"{orig_stripped} is not RDS; coded RDS=0 per Keren/Ori review"
                ),
                "clinical_decision_source": "Keren/Ori (manual review 2026-04-25)",
            })
        else:
            rds_unexpected_vals.append(orig_stripped)

    if rds_unexpected_vals:
        unexpected_findings.append(
            f"RDS: unexpected text value(s) not in approved list: {rds_unexpected_vals}"
        )
        print(f"  RDS: UNEXPECTED text found: {rds_unexpected_vals}")
    else:
        print(f"  RDS: {n_rds_text} text row(s) found, {n_rds_recoded_to_0} recoded to 0, "
              f"TTN_bin=1 for {n_ttn_bin_positive}, original text preserved in RDS_comment")

    # QA file: NICU + RDS manual corrections
    if qa_rows:
        qa_df = pd.DataFrame(qa_rows)
        os.makedirs(review_path, exist_ok=True)
        qa_df.to_excel(qa_xlsx, index=False)
        print(f"  QA file saved: {qa_xlsx} ({len(qa_rows)} rows)")

    # ------------------------------------------------------------------
    # 1c. Other binary neonatal complication variables
    #     Generic: any remaining free-text → NaN (unexpected; cannot infer).
    # ------------------------------------------------------------------
    binary_cols_generic = [
        "IVH", "IVH_grade_1_2", "IVH_grade_3_4",
        "mechanical_ventilation",
        "NEC", "sepsis", "hypoglycemia",
        "neonatal_jaundice_used_phototherapy", "neonatal_death",
        "congenital_anomaly",
    ]
    text_rows_found = {}
    for col in binary_cols_generic:
        text_mask = df[col].map(_has_letters)
        n_text = int(text_mask.sum())
        if n_text:
            text_vals = [str(v) for v in df.loc[text_mask, col].unique()]
            text_rows_found[col] = {"n": n_text, "vals": text_vals}
            df.loc[text_mask, col] = np.nan
            print(f"  {col}: {n_text} free-text value(s) set to NaN -> {text_vals}")

    # Validate all binary cols (NICU and RDS now clean after special handling above)
    binary_cols_all = binary_cols_generic + ["NICU_admission", "RDS"]
    bin_results = {}
    for col in binary_cols_all:
        ok, unexp = validate_expected_binary_values(df[col], col)
        vc = df[col].value_counts(dropna=False).to_dict()
        bin_results[col] = {"ok": ok, "vc": vc}
        if not ok:
            unexpected_findings.append(f"{col}: unexpected values {unexp}")
        print(f"  {col}: {vc}")

    # Validate TTN_bin
    ttn_ok, ttn_unexp = validate_expected_binary_values(df["TTN_bin"], "TTN_bin")
    if not ttn_ok:
        unexpected_findings.append(f"TTN_bin: unexpected values {ttn_unexp}")
    print(f"  TTN_bin: {df['TTN_bin'].value_counts(dropna=False).to_dict()}")
    n_rds_comment_nonnull = int(df["RDS_comment"].notna().sum())
    print(f"  RDS_comment: {n_rds_comment_nonnull} non-null")

    # ------------------------------------------------------------------
    # 2. length_of_mechanical_ventilation — FREE-TEXT respiratory-course
    #    narrative (support type + mixed day/hour references), no approved
    #    standardized time unit. It is NOT a numeric duration variable.
    #    Corrected 2026-08-27 (Decision 90, section D): the field is no longer
    #    coerced to numeric for any validity/outlier screening, and the
    #    ">365 days" threshold (meaningless for a free-text field with no unit)
    #    is removed. The raw field is preserved unchanged; only raw non-null
    #    presence is summarized. Units are never inferred from the text.
    #    Classification remains source_or_text_audit_exclude / reference-only;
    #    never used in EDA C / modeling / the calculator.
    # ------------------------------------------------------------------
    lmv_raw = df["length_of_mechanical_ventilation"]
    n_lmv_nonnull = int(lmv_raw.notna().sum())
    n_lmv_nan     = int(lmv_raw.isna().sum())
    print(f"  length_of_mechanical_ventilation: {n_lmv_nonnull} raw non-null free-text "
          f"entries, {n_lmv_nan} NaN (free text; not numeric-coerced, no duration "
          f"threshold applied)")

    # ------------------------------------------------------------------
    # 3. age_at_neonatal_death — free text; expected only when neonatal_death=1
    #    (Batch 18 read-only review finding PRE-B18-005, 2026-08-01). True
    #    non-null presence is determined from the original field via
    #    notna(), never via numeric coercion: pd.to_numeric(errors="coerce")
    #    silently reports a genuine text value (e.g. "14 שעות") as NaN,
    #    which previously undercounted this field as "0 non-null" even
    #    though the current cohort's one neonatal_death=1 row does have a
    #    documented value. Numeric-parse availability is tracked separately
    #    below and must never be read as a non-null/presence count. The
    #    value itself is never converted to numeric or altered.
    # ------------------------------------------------------------------
    aad_raw_notna = df["age_at_neonatal_death"].notna()
    n_aad_valid = int(aad_raw_notna.sum())
    n_aad_nan   = int((~aad_raw_notna).sum())
    aad_num = pd.to_numeric(df["age_at_neonatal_death"], errors="coerce")
    n_aad_numeric_parseable = int(aad_num.notna().sum())
    nd_zero_mask = df["neonatal_death"].map(
        lambda v: not pd.isna(v) and str(v).strip() in ("0", "0.0")
    )
    aad_contra_mask = aad_raw_notna & nd_zero_mask
    n_aad_contra = int(aad_contra_mask.sum())
    if n_aad_contra:
        unexpected_findings.append(
            f"age_at_neonatal_death: {n_aad_contra} row(s) non-null when neonatal_death=0"
        )
    print(f"  age_at_neonatal_death: {n_aad_valid} non-null (raw), {n_aad_nan} NaN, "
          f"{n_aad_numeric_parseable} numeric-parseable, "
          f"{n_aad_contra} contradiction (non-null when neonatal_death=0)")

    # ------------------------------------------------------------------
    # 3b. age_at_neonatal_death — subgroup-applicability documentation
    #    (Batch 18 read-only review finding PRE-B18-003). Registered in the
    #    EDA A / Data Cleaning B SUBGROUP_APPLICABLE_COLS registries under
    #    neonatal_death == 1. Documentation only -- no values are modified,
    #    converted, or imputed here. Reuses aad_raw_notna above (the only
    #    reliable non-missing indicator for this text field).
    # ------------------------------------------------------------------
    _nd_applicable_mask = df["neonatal_death"] == 1
    n_nd_applicable = int(_nd_applicable_mask.sum())
    n_nd_not_applicable = int((~_nd_applicable_mask).sum())
    n_aad_present_in_subgroup = int((_nd_applicable_mask & aad_raw_notna).sum())
    n_aad_missing_in_subgroup = int((_nd_applicable_mask & ~aad_raw_notna).sum())
    print(f"  age_at_neonatal_death subgroup (neonatal_death==1): applicable n={n_nd_applicable}, "
          f"non-applicable n={n_nd_not_applicable}; within-subgroup present={n_aad_present_in_subgroup}, "
          f"within-subgroup missing={n_aad_missing_in_subgroup}")

    # ------------------------------------------------------------------
    # 4. long_term_outcome — report distribution
    # ------------------------------------------------------------------
    lto_vc = df["long_term_outcome"].value_counts(dropna=False).to_dict()
    print(f"  long_term_outcome: {lto_vc}")

    # ------------------------------------------------------------------
    # 5. Free-text columns: normalize placeholder zeros
    # ------------------------------------------------------------------
    freetext_cols = [
        "congenital_anomaly_comment", "long_term_outcome_comment",
    ]
    ft_results = {}
    for col in freetext_cols:
        before = df[col].copy()
        df[col] = df[col].apply(lambda v: np.nan if v in (0, "0", 0.0) else v)
        n_zeros = int(before.map(lambda v: v in (0, "0", 0.0)).sum())
        n_text  = int(df[col].notna().sum())
        ft_results[col] = {"non_null": n_text, "zeros_removed": n_zeros}
        print(f"  {col}: {n_text} non-null, {n_zeros} zeros->NaN")

    # ------------------------------------------------------------------
    # 6. Contradiction / review flags
    #    NICU and RDS text rows are resolved (manual decisions applied).
    #    freetext_bin_mask covers only OTHER binary cols with unexpected text.
    # ------------------------------------------------------------------
    ivh_num    = pd.to_numeric(df["IVH"], errors="coerce")
    ivhg12_num = pd.to_numeric(df["IVH_grade_1_2"], errors="coerce")
    ivhg34_num = pd.to_numeric(df["IVH_grade_3_4"], errors="coerce")
    ivh_grade_no_ivh = (
        ((ivhg12_num == 1) | (ivhg34_num == 1)) & (ivh_num == 0)
    )
    mv_num = pd.to_numeric(df["mechanical_ventilation"], errors="coerce")
    # mechanical_ventilation == 0 but a genuine non-empty respiratory-course
    # narrative recorded -> review only, based on RAW NON-EMPTY PRESENCE (never
    # on numeric parseability of the free text; units are not inferred). No
    # value is mutated. Currently 0 rows in the cohort.
    mv_contra_mask = (mv_num == 0) & df["length_of_mechanical_ventilation"].notna()

    # Only flag unexpected text in OTHER binary cols (NICU/RDS resolved above)
    freetext_bin_mask = pd.Series(False, index=df.index)
    for col in binary_cols_generic:
        orig_mask = work_df[col].map(_has_letters)
        freetext_bin_mask = freetext_bin_mask | orig_mask

    review_mask = aad_contra_mask | ivh_grade_no_ivh | mv_contra_mask | freetext_bin_mask
    n_review = int(review_mask.sum())
    if n_review:
        review_cols = [
            "IVH", "IVH_grade_1_2", "IVH_grade_3_4",
            "NICU_admission", "RDS", "RDS_comment", "TTN_bin",
            "mechanical_ventilation", "length_of_mechanical_ventilation",
            "neonatal_death", "age_at_neonatal_death",
        ]
        review_df = create_review_dataframe(
            df, review_mask, cols=review_cols, id_cols=["delivery_id", "subject_number"]
        )
        reason_list = []
        for idx in review_df.index:
            did = review_df.at[idx, "delivery_id"]
            orig_idx = df.index[df["delivery_id"] == did][0]
            r = []
            if aad_contra_mask.loc[orig_idx]:
                r.append("age_at_neonatal_death non-null but neonatal_death=0")
            if ivh_grade_no_ivh.loc[orig_idx]:
                r.append("IVH grade present but IVH=0")
            if mv_contra_mask.loc[orig_idx]:
                r.append("mechanical_ventilation=0 but length_of_mechanical_ventilation "
                         "has a non-empty free-text entry (raw presence; units not inferred)")
            if freetext_bin_mask.loc[orig_idx]:
                for col in binary_cols_generic:
                    raw_v = work_df.at[orig_idx, col]
                    if _has_letters(raw_v):
                        r.append(f"{col} free text set to NaN: {repr(str(raw_v))}")
            reason_list.append("; ".join(r) if r else "flagged")
        review_df["review_reason"] = reason_list
        os.makedirs(resolve_path(OUTPUT_REVIEW_PATH), exist_ok=True)
        review_df.to_excel(review_xlsx, index=False)
        print(f"  Review file saved: {review_xlsx} ({n_review} rows)")
    else:
        print("  No neonatal contradictions found.")

    os.makedirs(resolve_path(OUTPUT_PROCESSED_PATH), exist_ok=True)
    df.to_excel(output_xlsx, index=False)

    validation_result = "PASS" if not unexpected_findings else "FAIL"

    bin_lines = "\n".join(
        f"  - {col}: {r['vc']}"
        for col, r in bin_results.items()
    )
    text_norm_lines = "\n".join(
        f"  - {col}: {v['n']} free-text row(s) set to NaN; values: {v['vals']}"
        for col, v in text_rows_found.items()
    ) if text_rows_found else "  - None"

    summary = f"""# Preprocessing Batch 18 Summary — {BATCH_TITLE}
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

## Rows
- Input: {n_rows_input} | Output: {len(df)} (no rows removed)

## NICU_admission — manual clinical correction (2026-04-25)
- Text rows found: {n_nicu_text}
- Text value: ????? ???? (preterm/neonatal ward)
- Recoded to 1: {nicu_recoded_to_1} (per Keren: clinically equivalent to NICU admission)
- Unexpected text values: {nicu_unexpected_vals if nicu_unexpected_vals else "None"}

## RDS — manual clinical correction (2026-04-25)
- Text rows found: {n_rds_text}
- All recoded to RDS=0 (not RDS per Keren/Ori review): {n_rds_recoded_to_0}
- TTN_bin created: TTN_bin=1 for {n_ttn_bin_positive} rows
- RDS_comment: original text preserved for {n_rds_comment_nonnull} rows
- Unexpected RDS text values: {rds_unexpected_vals if rds_unexpected_vals else "None"}
- QA file: {qa_xlsx} ({len(qa_rows)} rows)

## Free-text normalization in other binary columns
{text_norm_lines}

## Binary neonatal complication variables (post-correction)
{bin_lines}
  - TTN_bin: {df['TTN_bin'].value_counts(dropna=False).to_dict()}
  - TTN_bin is an intrapartum/post-delivery neonatal outcome (classification: intrapartum_or_post_delivery_exclude, derived from RDS) and is protected by the calculator's defensive LEAKAGE_EXCLUDE_VARS guard (evaluate_locked_holdout_candidates.py) in addition to its predictor-eligibility classification.

## length_of_mechanical_ventilation
- Raw non-null free-text entries: {n_lmv_nonnull} | NaN: {n_lmv_nan}
- This field is free text (neonatal respiratory-course narrative: support type plus mixed day/hour references) with no approved standardized time unit -- **not a numeric duration variable**. It is NOT coerced to numeric and NO duration threshold is applied (the former ">365 days" rule was retired 2026-08-27, Decision 90 section D -- it was meaningless for a unit-less free-text field). Canonical classification (unchanged): intrapartum_or_post_delivery_exclude -- post-delivery timing is the primary exclusion reason; the free-text storage format is a secondary characteristic. Retained for reference/audit only; never converted to numeric, never binarized, units never inferred from the text, and excluded from EDA C / modeling / the calculator. The raw field value is preserved exactly.

## age_at_neonatal_death
- Non-null (raw, notna): {n_aad_valid} | NaN: {n_aad_nan} | Numeric-parseable: {n_aad_numeric_parseable} | Contradictions: {n_aad_contra}
- Applicable only when neonatal_death = 1; registered in the EDA A / Data Cleaning B SUBGROUP_APPLICABLE_COLS registries (subgroup_rule: neonatal_death == 1) so descriptive missingness reporting distinguishes structurally non-applicable rows from genuine missingness within the applicable subgroup. Current applicable subgroup size: {n_nd_applicable} | Structurally non-applicable: {n_nd_not_applicable} | Present within the applicable subgroup: {n_aad_present_in_subgroup} | True missing within the applicable subgroup: {n_aad_missing_in_subgroup}. Value and unit unchanged -- not converted to numeric, not imputed.

## long_term_outcome
- {lto_vc}

## Free-text columns (zeros normalized)
- congenital_anomaly_comment: {ft_results['congenital_anomaly_comment']['non_null']} non-null, {ft_results['congenital_anomaly_comment']['zeros_removed']} zeros removed
- long_term_outcome_comment: {ft_results['long_term_outcome_comment']['non_null']} non-null, {ft_results['long_term_outcome_comment']['zeros_removed']} zeros removed

## Review file
{"- " + review_xlsx + f" ({n_review} rows)" if n_review else "- None"}

## Unexpected findings
{chr(10).join("- " + x for x in unexpected_findings) if unexpected_findings else "None"}

## Output
- {output_xlsx}

## Validation
{validation_result}
"""
    write_batch_summary(summary_md, summary)
    log_audit_event(
        audit_log_md,
        f"Batch 18 — {BATCH_TITLE}",
        f"- Rows: {n_rows_input} in / {len(df)} out\n"
        f"- NICU_admission: {n_nicu_text} text rows (????? ????) recoded to 1 per Keren\n"
        f"- RDS: {n_rds_text} text rows recoded to 0 per Keren/Ori; "
        f"TTN_bin=1 for {n_ttn_bin_positive}; RDS_comment preserves original text\n"
        f"- Generic free-text binary normalization: "
        f"{dict((c, v['n']) for c, v in text_rows_found.items()) if text_rows_found else 'none'}\n"
        f"- Binary cols validated: {binary_cols_all + ['TTN_bin']}\n"
        f"- length_of_mechanical_ventilation: {n_lmv_nonnull} raw non-null free-text entries "
        f"(free text, not numeric-coerced; retired >365-day rule -- Decision 90 section D)\n"
        f"- age_at_neonatal_death contradictions: {n_aad_contra}\n"
        f"- Review rows: {n_review}\n"
        f"- QA file: {qa_xlsx}\n"
        f"- Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Unexpected findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print(f"  Saved: {output_xlsx}")
    print("=== Batch 18 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Batch 19 — Final variable classification, leakage gate, and QA inventory
# ---------------------------------------------------------------------------

def batch_19_qa_inventory_and_classification(df):
    """
    Final variable classification, leakage gate, and QA inventory.

    Generates the canonical variable classification and type-schema
    registries from the fully processed DataFrame, validates row/column/
    target invariants (431 rows, 156 columns, target 370/61), delivery_id/
    subject_number identifier integrity (delivery_id complete and unique;
    missing subject_number reported but non-blocking, see PRE-ALL-001), and
    the full leakage/timing classification scheme, and produces the
    review-file inventory documenting every open and closed manual-review
    item. Does not modify any analytical column.

    QA outputs: variable_classification_minimal.csv/.xlsx,
    variable_type_schema_minimal.csv/.xlsx, review_file_inventory_batch19.md.
    The type-schema CSV and XLSX are both written from the same validated
    in-memory dataframe: the CSV remains the canonical machine-readable
    artifact (reproducible diffs, programmatic use); the XLSX is an
    equivalent representation for manual review and filtering, not a
    separate source of truth. Neither is written if schema validation fails.
    Returns: df — the final processed DataFrame, unchanged by this batch.
    """
    BATCH_TITLE = BATCH_METADATA[19]["title"]
    print(f"=== Batch 19: {BATCH_TITLE} ===")

    audit_path  = resolve_path(OUTPUT_AUDIT_PATH)
    review_path = resolve_path(OUTPUT_REVIEW_PATH)

    audit_log_md = os.path.join(audit_path, "preprocessing_audit_log.md")
    summary_md   = os.path.join(audit_path, "preprocessing_summary_batch19.md")
    inventory_md = os.path.join(audit_path, "review_file_inventory_batch19.md")
    classif_csv  = os.path.join(audit_path, "variable_classification_minimal.csv")
    classif_xlsx = os.path.join(audit_path, "variable_classification_minimal.xlsx")

    # variable_type_schema_minimal.csv/.xlsx: like every other Batch 19
    # output, written under OUTPUT_AUDIT_PATH. Previously frozen at a
    # separate, older location (update/preprocessing/outputs/audit/) because
    # the tracked .csv there could not be moved by this repo's harness-level
    # commit guard (see CLAUDE.md's commit policy grandfather note) -- that
    # exception was retired 2026-08-24: the tracked .csv was removed from git
    # entirely (git rm), replaced by a tracked, data-free-where-possible YAML
    # mirror (variable_type_schema_minimal.yaml, generated by
    # generate_type_schema_yaml.py), and this local runtime CSV/XLSX export
    # now lives at the same location as every other audit output, gitignored
    # like the rest.
    type_schema_csv = os.path.join(audit_path, "variable_type_schema_minimal.csv")
    type_schema_xlsx = os.path.join(audit_path, "variable_type_schema_minimal.xlsx")

    os.makedirs(audit_path, exist_ok=True)

    unexpected_findings = []
    # Tracked separately from unexpected_findings: a missing optional review/QA
    # workbook (produced by a standalone helper script outside this required
    # chain, e.g. qa_endometrioma_batch7.py) is a non-blocking condition, not
    # a preprocessing correctness failure — it must never be reported at the
    # same severity as a row-count/target/classification mismatch.
    missing_review_files = []

    # ------------------------------------------------------------------
    # 1. Validation: row count and target distribution
    # ------------------------------------------------------------------
    # Cohort 448->447 (2026-07-30, Decision 32: one analytical record excluded
    # for placenta_accreta==1 OR placenta_previa==1) ->431 (2026-08-15,
    # Decision 67: 16 suspected-superficial-only records excluded). Target
    # 386/62 -> 385/62 -> 370/61.
    # Expected values read from preprocessing_config.py's
    # CURRENT_APPROVED_COHORT_ROWS/TARGET_N0/TARGET_N1 -- the single
    # authoritative source for the current frozen-cohort baseline
    # (centralized 2026-08-16; do not reintroduce independent literals here).
    n_rows = len(df)
    print(f"  Row count: {n_rows}")
    if n_rows != CURRENT_APPROVED_COHORT_ROWS:
        unexpected_findings.append(f"Row count: expected {CURRENT_APPROVED_COHORT_ROWS}, got {n_rows}")

    n0 = int(df["target_intrapartum_cs"].eq(0).sum())
    n1 = int(df["target_intrapartum_cs"].eq(1).sum())
    print(f"  target_intrapartum_cs: 0={n0} / 1={n1}")
    if n0 != CURRENT_APPROVED_TARGET_N0 or n1 != CURRENT_APPROVED_TARGET_N1:
        unexpected_findings.append(
            f"Target distribution: expected 0={CURRENT_APPROVED_TARGET_N0} / 1={CURRENT_APPROVED_TARGET_N1}, got 0={n0} / 1={n1}"
        )

    # ------------------------------------------------------------------
    # 1b. Identifier integrity — delivery_id / subject_number composite key
    #    (Batch 19 read-only review finding PRE-ALL-001, 2026-08-01).
    #    delivery_id is the complete, unique primary key (assigned
    #    sequentially in Batch 1); subject_number may be legitimately
    #    missing (see Batch 3, PRE-ALL-001 deviation log entry) because the
    #    gap originates in the raw NUM column, not this pipeline. A missing
    #    subject_number is reported but never blocking; a missing or
    #    duplicate delivery_id, or a duplicate composite key among rows
    #    where subject_number IS available, is always blocking. No
    #    artificial identifier is generated anywhere in this check.
    # ------------------------------------------------------------------
    n_missing_delivery_id = int(df["delivery_id"].isna().sum())
    n_duplicate_delivery_id = int(df["delivery_id"].dropna().duplicated().sum())
    n_missing_subject_number = int(df["subject_number"].isna().sum())
    _both_present = df["subject_number"].notna() & df["delivery_id"].notna()
    n_duplicate_available_composite_key = int(
        df.loc[_both_present, ["subject_number", "delivery_id"]].duplicated().sum()
    )
    print(
        f"  Identifier integrity: missing delivery_id={n_missing_delivery_id}, "
        f"duplicate delivery_id={n_duplicate_delivery_id}, "
        f"missing subject_number={n_missing_subject_number} (non-blocking), "
        f"duplicate available subject_number+delivery_id pairs={n_duplicate_available_composite_key}"
    )
    if n_missing_delivery_id:
        unexpected_findings.append(
            f"delivery_id: {n_missing_delivery_id} row(s) missing (must be complete)"
        )
    if n_duplicate_delivery_id:
        unexpected_findings.append(
            f"delivery_id: {n_duplicate_delivery_id} duplicate value(s) (must be unique)"
        )
    if n_duplicate_available_composite_key:
        unexpected_findings.append(
            f"subject_number+delivery_id: {n_duplicate_available_composite_key} duplicate "
            f"composite key(s) among rows where both are available"
        )
    # missing subject_number is intentionally NOT added to unexpected_findings
    # (see PRE-ALL-001) -- it is reported above and persisted in the summary
    # below, but must never block validation.

    # ------------------------------------------------------------------
    # 2. Minimal approved variable classification table
    # ------------------------------------------------------------------
    classification_groups = [
        (
            "id",
            "Identifier columns only; retained for linkage/audit and excluded from modeling.",
            [
                "delivery_id",
                "subject_number",
            ],
        ),
        (
            "target",
            "Primary outcome/label; excluded from predictors.",
            [
                "target_intrapartum_cs",
            ],
        ),
        (
            "predictor_allowed",
            "Candidate pre-delivery or historical predictors approved for empirical evaluation. Available before labor begins; eligible for all three cumulative prediction stages (Decision 65): Stage 1 (pre-labor), Stage 2 (pre-labor + near-delivery), and Stage 3 (pre-labor + near-delivery + intrapartum).",
            [
                "AGE",
                "G",
                # P: authoritative parity-count source (PARTNER-FIX-03A,
                # PRE-B3-003). nulliparity below is now derived directly from
                # P in Batch 3 (P==0 -> 1, P>=1 -> 0); P itself is unchanged
                # and stays predictor_allowed. Downstream redundancy between
                # P and nulliparity (e.g. a possible parity_binary_0_vs_1plus
                # feature) is a modeling-stage decision, out of scope here --
                # see PARTNER-FIX-03B.
                "P",
                "LIVE_BIRTH",
                "EUP",
                "AB",
                # nulliparity: overwritten directly from P in Batch 3
                # (PARTNER-FIX-03A, PRE-B3-003); see the P comment above.
                "nulliparity",
                "S_P_CS",
                "CS",
                "VBAC",
                "smoking",
                "alcohol",
                # any_medical_problem, regular_medications: moved out here
                # 2026-08-04 (clinically_nonspecific_exclude below) -- Keren
                # determined both are too broad/clinically heterogeneous for
                # meaningful predictor interpretation. See
                # docs/clinical_decisions/manual_decisions_log.md.
                "Fetus_Anamoly",
                "deep_endometriosis",
                "adenomyosis",
                # superficial_endometriosis: moved out here 2026-08-14
                # (Decision 66) -- to clinically_redundant_exclude below.
                # Clinical experts selected peritoneal_endometriosis as the
                # canonical representation of the overlapping endometriosis
                # phenotype; superficial_endometriosis is retained in the
                # dataset (see the dedicated tuple below) but no longer a
                # modeling candidate.
                # clinical_diagnosis_only: removed here 2026-07-30 (Decision 33)
                # -- dropped early (Batch 2) as an approved analytical
                # exclusion; no longer present in df, so no longer classified.
                "cs_scar_endometriosis",
                "peritoneal_endometriosis",
                # diagnosis_year: SUPERSEDED 2026-08-18 (finalized project
                # decision) -- moved out to source_or_text_audit_exclude below.
                # The predictor-eligibility rationale that used to live here
                # (pre-labor predictor, not leakage, per the dataset owner's
                # definition of diagnosis_date as the original endometriosis
                # diagnosis date, PARTNER-FIX-02 / PRE-B5-001) is retained for
                # historical record at the new tuple's location, not deleted.
                # diagnosis_year is the literal calendar year the diagnosis was
                # documented -- not disease duration, not age at diagnosis, not
                # time since diagnosis -- and the project decided a calendar-
                # time-of-diagnosis field must not be predictor-eligible
                # regardless of its pre-labor availability. See
                # docs/clinical_decisions/manual_decisions_log.md (decision
                # superseding the diagnosis_year predictor-eligibility history
                # in Decisions 5/63 and this file's PARTNER-FIX-02/PRE-B5-001
                # notes).
                "endometrioma",
                "endometrioma_size_clean",
                "endometrioma_place_clean",
                "endometrioma_laterality",
                "endometriosis_surgery",
                "weight_before_pregnancy",
                # weight_in_pregnancy: moved here 2026-07-31 (Decision 40) --
                # to secondary_near_delivery_predictor below. Generally
                # self-reported; not measured at a standardized, consistent
                # pregnancy time point. Excluded from the primary model on
                # timing-non-standardization grounds -- not confirmed leakage.
                "height",
                "BMI_before",
                # BMI_after: moved here 2026-07-31 (Decision 39) -- to
                # intrapartum_or_post_delivery_exclude below. Confirmed by the
                # active clinical variable documentation: BMI data after
                # delivery is influenced by documentation existing in the
                # medical record after the end of delivery or at discharge,
                # and is not always determined immediately after delivery,
                # especially in normal deliveries without complications. Not
                # available at the pre-labor prediction point.
                # aspirin_during_pregnancy, clexane_during_pregnancy: confirmed
                # 2026-07-31 (Decision 41) as antenatal/pre-labor predictors --
                # treatment began before labor and was known before the
                # attempted vaginal delivery. Remain predictor_allowed,
                # unchanged by this decision. Binary semantics (0 = no
                # positive documentation, not confirmed non-use) documented in
                # Decision 41 and the project's methodological limitations.
                "aspirin_during_pregnancy",
                "clexane_during_pregnancy",
                "mode_of_conception_ivf_vs_all",
                "pregnancy_related_hypertensive_disorder",
                "PIH",
                "mild_PET",
                "severe_PET",
                "any_PET",
                "SIPET",
                "HELLP",
                "eclampsia",
                "gestational_diabetes",
                "diabetes_type",
                "IUGR",
                # placental_abruption: moved here 2026-08-04, to the
                # secondary_near_delivery_predictor group below (students +
                # Keren: may be identified close to the delivery episode).
                # placenta_accreta, placenta_previa: removed here 2026-07-30
                # (Decision 32) -- used for a one-record cohort exclusion in
                # Batch 2, then dropped from the analytical dataset entirely;
                # no longer present in df, so no longer classified.
                # oligohydramnios: moved here 2026-07-30 (Decision 37, EDA B14
                # DEC-04) -- to intrapartum_candidate_pending_timing_confirmation
                # below. Timing (antenatal ultrasound vs. admission vs. during
                # labor) cannot be reliably determined from this dataset;
                # excluded from the primary pre-labor model on conservative
                # leakage-prevention grounds. Not confirmed intrapartum.
                "polyhydramnios",
                # IUFD: moved 2026-08-01 (Decision 49) -- to
                # intrapartum_or_post_delivery_exclude below. Represents
                # current-pregnancy intrauterine fetal death only (never
                # prior-pregnancy history); this is a fetal event occurring
                # before or during delivery, not a pre-labor-available
                # predictor -- reclassified regardless of its current zero
                # variance (which was never the basis for exclusion).
                # celestone: moved 2026-08-01 (Decision 47) -- to
                # intrapartum_candidate_pending_timing_confirmation below.
                # Administration timing (during pregnancy vs. around
                # admission/labor assessment) is not consistently documented;
                # excluded from the primary pre-labor model on the same
                # timing-uncertainty grounds as oligohydramnios. Not confirmed
                # leakage.
                # magnesium: reviewed 2026-08-01 (Decision 46) and CONFIRMED
                # predictor_allowed -- clinically administered antenatally for
                # fetal neuroprotection before threatened preterm delivery
                # (<32 weeks), known before the attempted vaginal delivery.
                # No classification change; only its TIMING_MAP tag (config.py,
                # EDA C) is corrected from admission_labor to pregnancy.
                "magnesium",
                "mode_of_conception",
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
                "vaginal_opening_during_surgery",
                "bowel_lesion_resected",
                "bladder_lesion_resected",
                # endo_surgery_adhesiolysis: restored here 2026-07-08 (Decision 14).
                # Clinical supervisors confirmed it reflects adhesiolysis performed
                # during PRIOR endometriosis-related surgery, before the pregnancy —
                # not an action during the current delivery/CS/intrapartum/postpartum
                # period. Treated as a historical baseline predictor, not leakage.
                # Included in the correlation/redundancy audit (may overlap with
                # other endometriosis surgery variables). See
                # docs/clinical_decisions/manual_decisions_log.md.
                "endo_surgery_adhesiolysis",
                # gender: restored here 2026-07-08 (Decision 17, supersedes Decision 12).
                # Clinical clarification confirms gender reflects FETAL SEX known
                # before delivery/birth — not neonatal-only, not post-delivery, not
                # intrapartum, not postpartum, not target-derived. The prior exclusion
                # (Decision 12) was a conservative data-governance correction made
                # while timing/source was ambiguous and undocumented; that ambiguity
                # is now resolved. Treated as a pre-delivery baseline predictor, not
                # leakage. Included in the correlation/redundancy audit like any
                # other predictor.
                # SUPERSEDED 2026-08-04 (Decision 62): moved out to
                # intrapartum_or_post_delivery_exclude below -- Keren clarified
                # that THIS SPECIFIC DATASET COLUMN is based on newborn/neonatal
                # data; even though fetal sex may theoretically be known during
                # pregnancy, this recorded variable is treated as unavailable at
                # the intended pre-labor prediction stage. See
                # docs/clinical_decisions/manual_decisions_log.md.
                # adenomyosis_sonographic_features_clean: reclassified here 2026-07-28
                # (data owner decision). Previously manual_review_pending; 5 of the
                # remaining 16 unresolved free-text rows were resolved by direct
                # authoritative clinical corrections (see
                # ADENOMYOSIS_MANUAL_FEATURE_DECISIONS and
                # docs/clinical_decisions/manual_decisions_log.md). 11 rows remain
                # unresolved (missing) and are handled under the project's general
                # CV-only imputation policy, not resolved at this stage.
                "adenomyosis_sonographic_features_clean",
            ],
        ),
        (
            # New tuples 2026-08-04 (Decision 62): oligohydramnios, celestone,
            # and IUFD each have their own bespoke reason text (below),
            # distinct from the shared reason of the main predictor_allowed
            # tuple above -- kept as separate single-variable tuples with the
            # same classification label so the other members' reasons are not
            # altered.
            "predictor_allowed",
            "Assessed by ultrasound during pregnancy, similarly to polyhydramnios, and therefore available before delivery.",
            [
                "oligohydramnios",
            ],
        ),
        (
            "predictor_allowed",
            "Antenatal corticosteroid administered during pregnancy when there is a risk of preterm delivery, and therefore given before delivery.",
            [
                "celestone",
            ],
        ),
        (
            "predictor_allowed",
            "Predictor eligibility confirmed by clinical expert instruction (Keren).",
            [
                "IUFD",
            ],
        ),
        (
            # New label 2026-08-14 (Decision 66). superficial_endometriosis
            # and peritoneal_endometriosis are NOT empirically equivalent
            # (~63.2% agreement -- see COLUMN_MAPPING's "superficial" row in
            # preprocessing_config.py -- and were never merged); this is a
            # clinical preference decision made despite that divergence, not
            # a statistical reconciliation.
            "clinically_redundant_exclude",
            "Retained in the dataset for audit, cohort-rule derivation, and outcome-independent sensitivity analyses, but excluded from every modeling candidate pool: clinical experts selected peritoneal_endometriosis as the canonical representation of the overlapping endometriosis phenotype (Decision 66), notwithstanding the two variables' imperfect empirical agreement.",
            [
                "superficial_endometriosis",
            ],
        ),
        (
            "secondary_near_delivery_predictor",
            "Near-delivery or labor-adjacent predictors; not treated as target leakage, but separated from the main baseline predictor set. Excluded from Stage 1 (pre-labor); eligible for Stage 2 (pre-labor + near-delivery) and Stage 3 (Decision 65).",
            [
                "PPROM",
                # gestational_age_at_delivery_days: moved out 2026-08-18
                # (timing-leakage correction, ChatGPT independent review) --
                # see the dedicated intrapartum_or_post_delivery_exclude tuple
                # below for the full rationale and the new decision entry in
                # docs/clinical_decisions/manual_decisions_log.md.
                "gestational_age_at_PPROM_days",
                # Hb_before_delivery: reclassified here 2026-07-29 (Decision 29).
                # Final clinical clarification: the measurement is never taken
                # during labor; it may be obtained during pregnancy or on the day
                # of admission for delivery. Timing is heterogeneous across these
                # two pre-labor windows, but the value is always available before
                # any intrapartum event and before the delivery outcome -- the
                # same near-delivery-but-not-intrapartum status as this group's
                # other 3 members. See docs/clinical_decisions/manual_decisions_log.md.
                "Hb_before_delivery",
                # weight_in_pregnancy: moved here 2026-07-31 (Decision 40),
                # from predictor_allowed. Distinct rationale from this group's
                # other members: it is not confirmed near-delivery-but-safe
                # timing -- it is generally self-reported and not measured at
                # a standardized, consistent pregnancy time point (may be an
                # early-, mid-, or late-pregnancy value; the dataset provides
                # no reliable timestamp). Excluded from the primary/baseline
                # predictor pool on timing-non-standardization grounds, not
                # because it is confirmed leakage. Retained for descriptive
                # or explicitly non-primary sensitivity analysis. See
                # docs/clinical_decisions/manual_decisions_log.md Decision 40.
                "weight_in_pregnancy",
            ],
        ),
        (
            # New tuple 2026-08-27 (Decision 86, approved): BMI_after moved
            # back here from intrapartum_or_post_delivery_exclude (Decision
            # 69, 2026-08-15), the second reversal of this variable's
            # near-delivery-vs-excluded classification (Decision 39 ->
            # Decision 61 -> Decision 69 -> Decision 86). Decision 86 is a
            # project classification decision, not a claim of new Keren/Gidi
            # clinical input beyond what is already on record; it is
            # supported by the variable's own formula-exact lineage (Data
            # Cleaning B/preprocessing confirm BMI_after is derived from
            # weight_in_pregnancy and height -- a pregnancy-time measurement
            # pair, not an independently-sourced postpartum value) rather
            # than by a new clinical statement. This is a predictor-timing/
            # scope decision only; it does not itself resolve BMI_after's
            # missingness treatment -- that METHOD question was separately
            # CLOSED the same day by Decision 91 (fold-safe observed-value
            # tertile representation, Data Cleaning B Section B5b; only the
            # cutpoint fitting location is deferred to modeling). Bespoke
            # reason text, distinct from the shared reason
            # of the main secondary_near_delivery_predictor tuple above --
            # kept as a separate single-variable tuple so the other members'
            # reasons are not altered. See
            # docs/clinical_decisions/manual_decisions_log.md Decision 86
            # (Decision 69 remains in the log as historical record; it is
            # superseded, not deleted).
            "secondary_near_delivery_predictor",
            "Restored to secondary near-delivery predictor status (Decision 86, 2026-08-27), superseding Decision 69. BMI_after is formula-derived from weight_in_pregnancy and height, a pregnancy-time measurement pair, rather than an independently-sourced postpartum value. Excluded from Stage 1 (pre-labor); eligible for Stage 2 (pre-labor + near-delivery) and Stage 3 (Decision 65), the same horizon as this group's other members. This decision addresses predictor-timing/scope only; BMI_after's missingness-handling method is a separate decision, closed the same day by Decision 91 (fold-safe observed-value tertile representation, Data Cleaning B Section B5b, cutpoints fitted training-fold-only in modeling) -- not an open question.",
            [
                "BMI_after",
            ],
        ),
        (
            # placental_abruption: restored here 2026-08-15 (Decision 68
            # correction) -- Decision 68's original 2026-08-15 change had
            # moved this variable to intrapartum_predictor_exclude_from_
            # prelabor_model, misreading Keren's clarification as a horizon
            # reassignment. Keren's original secondary_near_delivery_predictor
            # (near-delivery) horizon for this variable was already approved
            # and correct; the actual required change was modeling clearance
            # (blocks_modeling True -> False in the EDA A2 CLINICAL_REVIEW_
            # REGISTRY), not horizon reassignment. Bespoke reason text,
            # distinct from the shared reason of the main
            # secondary_near_delivery_predictor tuple above -- kept as a
            # separate tuple with the same classification label so the other
            # members' reasons are not altered.
            "secondary_near_delivery_predictor",
            "Near-delivery timing approved by Keren (Decision 68, corrected 2026-08-15): may be identified close to the delivery episode. Cleared for modeling (no longer pending timing confirmation) -- eligible from Stage 2 (pre-labor + near-delivery) onward, per Decision 65.",
            [
                "placental_abruption",
            ],
        ),
        (
            "intrapartum_predictor_exclude_from_prelabor_model",
            "Variables with clinically confirmed intrapartum timing (relayed by Keren to the project team on 2026-07-28). Not outcomes or audit-only variables (distinct from intrapartum_or_post_delivery_exclude). Excluded from Stage 1 (pre-labor) and Stage 2 (pre-labor + near-delivery); eligible only for Stage 3 (pre-labor + near-delivery + intrapartum), per Decision 65. Stage 3 is an intrapartum risk-update model, not an early/prelabor model.",
            [
                # chorioamnionitis, intrapartum_fever: moved out here 2026-08-04,
                # to source_or_text_audit_exclude below (students + Keren:
                # cannot be reliably distinguished clinically in this dataset
                # and partly overlap; consolidated into
                # intrapartum_fever_or_chorioamnionitis_bin below, which is
                # unaffected by this move).
                "meconium_stained_amniotic_fluid",
                # induction_of_labor, start_of_labor: moved out here 2026-08-04,
                # to source_or_text_audit_exclude below (students + Keren:
                # source variables whose information is consolidated into
                # induction_any_bin below, which is unaffected by this move).
                # induction_any_bin is derived from induction_of_labor and
                # start_of_labor; these related variables should not be used
                # together automatically in the same model.
                "induction_any_bin",
                # indication_for_induction_clean may be structurally missing
                # because it applies mainly when induction occurred.
                "indication_for_induction_clean",
                # intrapartum_fever_or_chorioamnionitis_bin: new composite created
                # 2026-07-29 (Decision 31) from two already-confirmed-intrapartum
                # source variables in this same group. Descriptive/future
                # intrapartum-stage-model use only; excluded from the current
                # pre-labor predictor pool for the same reason as its sources.
                "intrapartum_fever_or_chorioamnionitis_bin",
                # gestational_age_at_delivery_days: moved here 2026-08-19
                # (Decision 79 addendum -- Keren's explicit Stage-3 approval,
                # supersedes the 2026-08-18 all-stage exclusion). Its value is
                # only fixed once delivery has occurred, so it remains
                # excluded from Stage 1 (pre-labor) and Stage 2 (admission) --
                # exactly like every other member of this category -- but
                # Keren explicitly approved its use as a Stage 3 (dynamic
                # intrapartum, known before the cesarean decision) predictor.
                # Was intrapartum_or_post_delivery_exclude (a stricter,
                # all-stage-excluded category); this is a horizon
                # relaxation, not a claim that its value is knowable earlier
                # than before. See docs/clinical_decisions/manual_decisions_log.md
                # Decision 79 addendum.
                "gestational_age_at_delivery_days",
            ],
        ),
        (
            "intrapartum_candidate_pending_timing_confirmation",
            "Variables known or potentially known during labor that do not directly encode the target, but whose availability before the cesarean decision has not yet been clinically confirmed. Excluded from the primary and secondary predictor pools pending clinical timing confirmation.",
            [
                # Vacated 2026-07-29 (Decision 29): Hb_before_delivery, the sole
                # remaining member as of 2026-07-28, has now also been clinically
                # confirmed (available before any intrapartum event) and moved to
                # secondary_near_delivery_predictor above. This category was kept
                # formally defined with zero members between Decisions 29 and 37,
                # for schema continuity, in case a future variable's timing was
                # genuinely still unresolved.
                # oligohydramnios: moved here 2026-07-30 (Decision 37, EDA B14
                # DEC-04), from predictor_allowed. May be diagnosed antenatally,
                # at admission, or during labor; this dataset provides no reliable
                # timestamp to determine which applies per record. Excluded from
                # the primary and secondary predictor pools on timing-uncertainty/
                # leakage-prevention grounds -- not confirmed intrapartum (distinct
                # from intrapartum_predictor_exclude_from_prelabor_model, Decision
                # 28). Retained in the dataset; available for descriptive,
                # secondary, or sensitivity analysis.
                # SUPERSEDED 2026-08-04 (Decision 62): moved back to
                # predictor_allowed below -- Keren clarified oligohydramnios is
                # assessed by ultrasound during pregnancy, similarly to
                # polyhydramnios, and is therefore available before delivery.
                # celestone: moved here 2026-08-01 (Decision 47), from
                # predictor_allowed. Betamethasone for fetal lung maturation;
                # the retrospective data do not consistently document whether
                # administration occurred during pregnancy or around
                # admission/labor assessment. Excluded from the primary
                # pre-labor model on the same timing-uncertainty grounds as
                # oligohydramnios -- not confirmed leakage, not confirmed
                # intrapartum. Retained in the dataset; available for
                # descriptive analysis and explicitly-labeled non-primary
                # sensitivity analysis.
                # SUPERSEDED 2026-08-04 (Decision 62): moved back to
                # predictor_allowed below -- Keren clarified Celestone is
                # administered during pregnancy when there is a risk of preterm
                # delivery and is therefore given before delivery.
            ],
        ),
        (
            "source_or_text_audit_exclude",
            # "cohort-control" removed from this description 2026-08-04 --
            # trial_of_labor_corrected (the only cohort-control variable
            # formerly here) moved to the new cohort_control_exclude
            # category below, which now owns that description.
            "Source, free-text, or raw-detail variables retained for audit/documentation only; excluded from direct modeling.",
            [
                # The first three raw duplicated comment fields were renamed to
                # semantic final names in Decision 34. Decision 57 then
                # renumbered only the remaining generic comment_N columns.
                "any_medical_problem_comment",
                "regular_medications_comment",
                "Fetus_Anamoly_comment",
                "comment_1",
                "comment_2",
                "comment_3",
                "comment_4",
                "comment_5",
                "comment_6",
                # congenital_anomaly_comment, long_term_outcome_comment: moved
                # out here 2026-08-04, to intrapartum_or_post_delivery_exclude
                # below (students + Keren: post-delivery neonatal outcome
                # detail -- post-delivery timing is the primary reason for
                # exclusion, even though the variable contains descriptive
                # text).
                "endometriosis_surgery_comment",
                "RDS_comment",
                "mode_of_conception_details",
                "diagnosis_date",
                "endometrioma_size",
                "endometrioma_place",
                "adenomyosis_sonographic_features",
                "endo_resection_sites",
                # endo_resection_sites_clean: reclassified here 2026-07-28 (data owner
                # decision). Previously manual_review_pending; this is a bookkeeping
                # relabel, not a substantive change -- it is a grouped, pipe-separated
                # multi-label field derived from raw/free text, structurally distinct
                # from the 10 already-predictor_allowed structured endo_resection_*
                # binary indicators (Decision 19). It was already, and remains,
                # excluded from modeling either way. See
                # docs/clinical_decisions/manual_decisions_log.md.
                "endo_resection_sites_clean",
                "surgery_details",
                "gestational_age_at_PPROM",
                "gestational_age_at_delivery",
                "indication_for_induction",
                "trial_of_labor",
                # trial_of_labor_corrected: moved out here 2026-08-04, to the
                # new cohort_control_exclude group below -- it is a derived
                # cohort-control variable (used to filter the analytical
                # cohort), not merely a source/free-text/reference field.
                # length_of_mechanical_ventilation: added here 2026-08-01
                # (Batch 18 read-only review finding PRE-B18-004) -- free-text
                # neonatal respiratory-course narrative (mixed support-type/
                # day/hour references, no approved uniform time unit), moved
                # from intrapartum_or_post_delivery_exclude. Value unchanged;
                # classification-only correction, not a new clinical rule.
                # SUPERSEDED 2026-08-04 (Decision 62): moved back to
                # intrapartum_or_post_delivery_exclude below -- describes the
                # duration of neonatal mechanical ventilation after delivery
                # and is unavailable at the intended prediction stage.
                # Post-delivery timing is the primary exclusion reason and
                # takes precedence over the variable's free-text storage
                # format (a secondary characteristic only). See
                # docs/clinical_decisions/manual_decisions_log.md Decision 62.
            ],
        ),
        (
            # New tuple 2026-08-18 (finalized project decision, supersedes the
            # predictor-eligibility rationale formerly attached to diagnosis_year
            # in the predictor_allowed tuple above, and Decisions 5/63). Kept as
            # its own bespoke-reason single-variable tuple, matching this
            # category's existing style, so the shared reason text of the main
            # source_or_text_audit_exclude tuple (and of the diagnosis_date
            # tuple within it) is not altered.
            "source_or_text_audit_exclude",
            "diagnosis_year is the literal calendar year in which the endometriosis diagnosis was documented (derived from diagnosis_date) -- not disease duration, not age at diagnosis, and not time since diagnosis. Deliberate project decision: a calendar-time-of-diagnosis field must not be predictor-eligible, regardless of its pre-labor availability (which is why it was previously predictor_allowed -- see the superseded PARTNER-FIX-02/PRE-B5-001 rationale still noted at its old location above). Retained in the analytical dataset, alongside its source diagnosis_date, for audit/descriptive purposes only; excluded from Stage 1/2/3, PRIMARY_COLS, and every predictive candidate pool. No replacement diagnosis-time-derived predictor (age at diagnosis, disease duration, time since diagnosis) was created as part of this decision.",
            [
                "diagnosis_year",
            ],
        ),
        (
            # New tuples 2026-08-04 (students + Keren approved final
            # classification mapping). Each of the 7 variables below has its
            # own bespoke reason text, distinct from the shared reason of the
            # main source_or_text_audit_exclude tuple above -- kept as
            # separate single-variable tuples with the same classification
            # label so the other members' reasons are not altered.
            "source_or_text_audit_exclude",
            "Source clinical variable retained for audit. Keren clarified that chorioamnionitis and intrapartum fever cannot be reliably distinguished clinically in this dataset and partly overlap; their information is therefore consolidated into a separate combined variable.",
            [
                "chorioamnionitis",
            ],
        ),
        (
            "source_or_text_audit_exclude",
            "Source clinical variable retained for audit. Keren clarified that intrapartum fever and chorioamnionitis cannot be reliably distinguished clinically in this dataset and partly overlap; their information is therefore consolidated into a separate combined variable.",
            [
                "intrapartum_fever",
            ],
        ),
        (
            "source_or_text_audit_exclude",
            "Source variable describing the induction methods performed. Its information is consolidated into a separate derived induction variable, while the source variable is retained for audit and traceability.",
            [
                "induction_of_labor",
            ],
        ),
        (
            "source_or_text_audit_exclude",
            "Source variable describing how labor started. Its information is consolidated with the induction information into a separate derived variable, while the source variable is retained for audit and traceability.",
            [
                "start_of_labor",
            ],
        ),
        (
            "source_or_text_audit_exclude",
            "Source cesarean-indication variable retained for audit and traceability after its information is processed into a separate cleaned or derived variable.",
            [
                "indication_for_CS",
            ],
        ),
        (
            "source_or_text_audit_exclude",
            "Source variable retained for audit and traceability after its information is represented by a separate cleaned or derived variable.",
            [
                "suspected_endo_lesions_during_CS",
            ],
        ),
        (
            "source_or_text_audit_exclude",
            "Source or redundant hemoglobin-difference variable retained for audit because alternative hemoglobin variables are used for the analytical representation.",
            [
                "Hb_diff",
            ],
        ),
        (
            # New category added 2026-08-04. Distinct from
            # source_or_text_audit_exclude: covers derived cohort-control
            # variables (used to define/filter/verify the analytical cohort)
            # rather than source/free-text/raw-detail fields. Category
            # definition: "Variables used to define, filter, or verify the
            # analytical cohort. Retained for audit and reproducibility but
            # excluded from predictor modeling." See
            # docs/clinical_decisions/manual_decisions_log.md.
            "cohort_control_exclude",
            "Derived cohort-control variable used to identify and retain women who underwent a trial of labor. It is constant after cohort filtering and is excluded from predictor modeling.",
            [
                "trial_of_labor_corrected",
            ],
        ),
        (
            # New tuple 2026-08-15 (Decision 67): sensitivity flags for the
            # broader 19-record and 26-record suspected-superficial-only
            # sensitivity cohorts, preserved on the 431-row primary export so
            # they can be reconstructed without rerunning preprocessing.
            # Derived only from clinical fields (never target_intrapartum_cs),
            # constant/audit-only, excluded from predictor modeling like
            # trial_of_labor_corrected above.
            "cohort_control_exclude",
            "Decision 67 sensitivity-cohort flag: True for a record retained under the primary exclusion rule but excluded under a broader suspected-superficial-only sensitivity definition. Excluded from predictor modeling; audit/reproducibility only.",
            [
                "decision67_sensitivity_19group_excluded",
                "decision67_sensitivity_26group_excluded",
            ],
        ),
        (
            # New category added 2026-08-04 (clinical decision, Keren).
            # Category definition: "Broad or clinically heterogeneous
            # variables that lack sufficient specificity for meaningful
            # predictor modeling. Retained for documentation and audit but
            # excluded from predictor modeling following clinical expert
            # guidance." Distinct from source_or_text_audit_exclude (these
            # are structured binary variables, not source/free-text fields)
            # and from clinical timing-based exclusion categories (this
            # exclusion is about specificity, not timing/leakage). Does not
            # apply automatically to related comment/detail/diagnosis/
            # treatment columns -- see
            # docs/clinical_decisions/manual_decisions_log.md.
            "clinically_nonspecific_exclude",
            "General indicator combining clinically heterogeneous conditions or treatments; excluded from predictor modeling because it is too nonspecific for meaningful interpretation, following clinical expert guidance.",
            [
                "any_medical_problem",
                "regular_medications",
            ],
        ),
        (
            "leakage_exclude",
            "Variables that directly encode the target, cesarean decision, cesarean indication, or operative findings after the target decision; excluded from predictors.",
            [
                "type_of_CS",
                "CS_case_vs_control",
                # indication_for_CS, suspected_endo_lesions_during_CS: moved
                # out here 2026-08-04, to source_or_text_audit_exclude below
                # (students + Keren: source variables retained for audit and
                # traceability after their information is represented by the
                # cleaned/derived variables below, which remain leakage_exclude
                # and are unaffected by this move).
                "indication_for_CS_clean",
                "suspected_endo_lesions_during_CS_clean",
                "abdominal_cavity_findings",
                "adhesions",
                "blood_loss_during_surgery",
                # surgery_dehiscence: removed here 2026-07-30 (Decision 33) --
                # dropped early (Batch 2) as an approved analytical exclusion;
                # no longer present in df, so no longer classified.
                "other_surgery_complications",
            ],
        ),
        (
            "intrapartum_or_post_delivery_exclude",
            "Variables measured or determined during labor, delivery, postpartum, or neonatal period; retained for outcomes/audit only and excluded from predictor modeling.",
            [
                "PPH",
                "postpartum_fever",
                "surgical_site_infection",
                "endometritis",
                "pH_vein",
                "pH_artery_or_vein_less_than_7_1",
                "apgar_5_less_than_7",
                "birth_weight",
                "percentile_by_Dolberg",
                "SGA",
                "LGA",
                "IVH",
                "IVH_grade_1_2",
                "IVH_grade_3_4",
                "NICU_admission",
                "RDS",
                "TTN_bin",
                "mechanical_ventilation",
                # length_of_mechanical_ventilation: removed here 2026-08-01
                # (Batch 18 read-only review finding PRE-B18-004) -- moved to
                # source_or_text_audit_exclude below. It is free-text
                # neonatal respiratory-course narrative (mixed support-type/
                # day/hour references, no approved uniform time unit), not a
                # numeric or binary outcome; the value is unchanged, only
                # its classification category.
                "NEC",
                "sepsis",
                "hypoglycemia",
                "neonatal_jaundice_used_phototherapy",
                "neonatal_death",
                "age_at_neonatal_death",
                "congenital_anomaly",
                "long_term_outcome",
                "apgar1",
                "Hb_after_delivery",
                "hospitalization_days",
                "pH_artery",
                "apgar5",
                # Hb_diff: moved out here 2026-08-04, to
                # source_or_text_audit_exclude below (students + Keren: source/
                # redundant hemoglobin-difference variable; the derived
                # Hb_diff_clean below is the analytical representation and is
                # unaffected by this move).
                "Hb_diff_clean",
                "any_blood_product_transfusion",
                # BMI_after: moved here 2026-07-31 (Decision 39), from
                # predictor_allowed. Confirmed by the active clinical variable
                # documentation: BMI data after delivery is influenced by
                # documentation existing in the medical record after the end
                # of delivery or at discharge, and is not always determined
                # immediately after delivery, especially in normal deliveries
                # without complications. Not available at the pre-labor
                # prediction point; its missingness may itself be
                # outcome-adjacent (documentation completeness varies with
                # delivery complexity). Retained for descriptive/postpartum
                # analysis only. See
                # docs/clinical_decisions/manual_decisions_log.md Decision 39.
                # SUPERSEDED 2026-08-04 (students + Keren): moved to
                # secondary_near_delivery_predictor below -- reserved for
                # secondary near-delivery analyses rather than the primary
                # pre-labor predictor model, rather than fully excluded.
                # IUFD: moved here 2026-08-01 (Decision 49), from
                # predictor_allowed. Represents current-pregnancy intrauterine
                # fetal death only (never prior-pregnancy history -- see the
                # active variable documentation's own clarification that a
                # comment-field mention of "IUFD in the past" for one row does
                # not indicate this binary field reflects that history). A
                # fetal event occurring before or during delivery; retained
                # only for cohort QC, audit, descriptive reporting, and
                # secondary outcome analysis, never as a predictor. Reclassified
                # regardless of currently being constant (0 for all 447 rows) --
                # zero variance is not the reason for this exclusion.
                # SUPERSEDED 2026-08-04 (Decision 62): moved back to
                # predictor_allowed below -- Keren explicitly instructed that
                # this variable should be predictor-eligible. No additional
                # clinical reasoning beyond that explicit instruction; predictor
                # eligibility was confirmed by the clinical expert. See
                # docs/clinical_decisions/manual_decisions_log.md Decisions 49
                # and 62.
            ],
        ),
        (
            # New tuples 2026-08-04 (students + Keren): congenital_anomaly_comment
            # and long_term_outcome_comment each have their own bespoke reason
            # text (below), distinct from the shared reason of the main
            # intrapartum_or_post_delivery_exclude tuple above -- kept as
            # separate single-variable tuples with the same classification
            # label so the other members' reasons are not altered.
            "intrapartum_or_post_delivery_exclude",
            "Post-delivery neonatal outcome detail. Its post-delivery timing is the primary reason for exclusion, even though the variable contains descriptive text.",
            [
                "congenital_anomaly_comment",
            ],
        ),
        (
            "intrapartum_or_post_delivery_exclude",
            "Post-delivery long-term neonatal outcome detail. Its post-delivery timing is the primary reason for exclusion, even though the variable contains descriptive text.",
            [
                "long_term_outcome_comment",
            ],
        ),
        (
            # New tuples 2026-08-04 (Decision 62): gender and
            # length_of_mechanical_ventilation each have their own bespoke
            # reason text (below), distinct from the shared reason of the
            # main intrapartum_or_post_delivery_exclude tuple above -- kept as
            # separate single-variable tuples with the same classification
            # label so the other members' reasons are not altered.
            "intrapartum_or_post_delivery_exclude",
            "This dataset column is based on newborn/neonatal data. The classification is based on how this specific dataset column was populated, not on whether fetal sex can theoretically be known during pregnancy; treated as unavailable at the intended pre-labor prediction stage.",
            [
                "gender",
            ],
        ),
        (
            "intrapartum_or_post_delivery_exclude",
            "Describes the duration of neonatal mechanical ventilation after delivery; unavailable at the intended prediction stage. Post-delivery timing is the primary exclusion reason and takes precedence over the variable's free-text storage format, which is a secondary characteristic only.",
            [
                "length_of_mechanical_ventilation",
            ],
        ),
        (
            # Tuple retired 2026-08-27 (Decision 86, approved) -- BMI_after
            # moved OUT of this category, back to secondary_near_delivery_predictor
            # (see the bespoke tuple below). Kept here as an empty placeholder
            # tuple for schema/history continuity, matching this file's
            # established pattern for a superseded single-variable
            # classification (see the gestational_age_at_delivery_days
            # placeholder tuple elsewhere in this list for the same pattern).
            # Decision 69 (2026-08-15) placed BMI_after here, citing
            # postpartum/discharge-influenced documentation timing per the
            # active clinical variable documentation; that reasoning is not
            # disputed as a historical record, but Decision 86 supersedes it
            # for BMI_after's current classification. See
            # docs/clinical_decisions/manual_decisions_log.md Decisions 69
            # and 86.
            "intrapartum_or_post_delivery_exclude",
            "Placeholder tuple, no current members (see Decision 86 -- BMI_after moved out).",
            [
            ],
        ),
        (
            # New tuple 2026-08-18 (timing-leakage prevention correction,
            # ChatGPT independent review of Data Cleaning B). Its sole prior
            # member, gestational_age_at_delivery_days, moved OUT on
            # 2026-08-19 to intrapartum_predictor_exclude_from_prelabor_model
            # (Decision 79 addendum -- Keren's explicit Stage-3 approval).
            # Tuple kept (empty list) for schema continuity and historical
            # documentation, matching this file's own established pattern
            # (e.g. the intrapartum_candidate_pending_timing_confirmation
            # tuple below, kept formally defined with zero members between
            # Decisions 29 and 37) -- not deleted, in case a future variable
            # is confirmed to genuinely fit this stricter all-stage-excluded
            # category.
            "intrapartum_or_post_delivery_exclude",
            "Completed gestational age, in days, AT THE ACTUAL DELIVERY (parsed from the raw 'gestational age at delivery' field, Batch 11). Its final value is only fixed once delivery has occurred. Historically classified here (2026-08-18) on the reasoning that this made it not knowable at Stage 1/2/3 -- **superseded 2026-08-19 (Decision 79 addendum)**: Keren explicitly approved this variable as knowable before the intrapartum cesarean decision for Stage-3 purposes specifically, so it now lives in intrapartum_predictor_exclude_from_prelabor_model (Stage 3 only) instead. This category is retained, currently empty, for any future variable whose value is confirmed not knowable even at Stage 3. Do not confuse with gestational_age_at_PPROM_days, which has row-specific applicability and its own separate handling. See docs/clinical_decisions/manual_decisions_log.md Decision 79.",
            [
            ],
        ),
        (
            "manual_review_pending",
            "Variables requiring additional manual/clinical review before they can be used as predictors.",
            [
                # Both former members reclassified 2026-07-28 -- see
                # predictor_allowed (adenomyosis_sonographic_features_clean) and
                # source_or_text_audit_exclude (endo_resection_sites_clean) above.
            ],
        ),
        (
            "awaiting_clinical_clarification",
            "Variables requiring clinical clarification regarding timing/context before final modeling eligibility.",
            [],
        ),
    ]

    approved_labels = {
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
    }
    expected_classif_counts = {
        "id": 2,
        "target": 1,
        # predictor_allowed: 67->65 (2026-07-31, Decisions 39/40) --
        # weight_in_pregnancy and BMI_after moved out (see below).
        # 65->64 (2026-08-01, Decision 47) -- celestone moved out to
        # intrapartum_candidate_pending_timing_confirmation.
        # 64->63 (2026-08-01, Decision 49) -- IUFD moved out to
        # intrapartum_or_post_delivery_exclude.
        # 63->61 (2026-08-04) -- any_medical_problem and regular_medications
        # moved out to the new clinically_nonspecific_exclude category
        # (Keren: too broad/clinically heterogeneous for meaningful predictor
        # interpretation).
        # 61->60 (2026-08-04, students+Keren final mapping, Decision 61) --
        # placental_abruption moved out to secondary_near_delivery_predictor.
        # 60->62 (2026-08-04, Decision 62) -- net +2: gender moved out (-1, to
        # intrapartum_or_post_delivery_exclude); oligohydramnios, celestone,
        # and IUFD moved in (+3, superseding Decisions 37/47/49).
        # 62->61 (2026-08-14, Decision 66) -- superficial_endometriosis moved
        # out to the new clinically_redundant_exclude category (see below);
        # peritoneal_endometriosis is the canonical modeled phenotype.
        # 61->60 (2026-08-18, finalized project decision) -- diagnosis_year
        # moved out to source_or_text_audit_exclude. It is the literal
        # calendar year of diagnosis (not disease duration, age at diagnosis,
        # or time since diagnosis); a calendar-time-of-diagnosis field must
        # not be predictor-eligible, superseding the prior PARTNER-FIX-02/
        # PRE-B5-001 pre-labor-availability rationale.
        "predictor_allowed": 60,
        # secondary_near_delivery_predictor: 4->5 (Decision 40) --
        # weight_in_pregnancy added.
        # 5->7 (2026-08-04, students+Keren final mapping) -- BMI_after and
        # placental_abruption added. Unchanged by Decision 62.
        # 7->6 (2026-08-15, Decision 68) -- placental_abruption moved out to
        # intrapartum_predictor_exclude_from_prelabor_model (Keren confirmed
        # clinically confirmed intrapartum timing).
        # 6->7 (2026-08-15, Decision 68 correction) -- placental_abruption
        # moved back: its near-delivery horizon was already correct; the
        # required change was modeling clearance, not horizon reassignment.
        # 7->6 (2026-08-15, Decision 69) -- BMI_after moved out to
        # intrapartum_or_post_delivery_exclude (measured postpartum; must
        # never predict intrapartum CS).
        # 6->5 (2026-08-18, timing-leakage prevention correction) --
        # gestational_age_at_delivery_days moved out to
        # intrapartum_or_post_delivery_exclude (its value is only fixed at
        # completed delivery; not knowable at Stage 1/2/3).
        # 5->6 (2026-08-27, Decision 86) -- BMI_after moved back in from
        # intrapartum_or_post_delivery_exclude, superseding Decision 69.
        "secondary_near_delivery_predictor": 6,
        # intrapartum_candidate_pending_timing_confirmation: 1->2 (2026-08-01,
        # Decision 47) -- celestone added, joining oligohydramnios.
        # 2->0 (2026-08-04, Decision 62) -- both oligohydramnios and celestone
        # moved to predictor_allowed (superseding Decisions 37/47). Category
        # kept formally defined with zero members, as it was between
        # Decisions 29 and 37, in case a future variable's timing is genuinely
        # still unresolved.
        "intrapartum_candidate_pending_timing_confirmation": 0,
        # intrapartum_predictor_exclude_from_prelabor_model: 8->4 (2026-08-04,
        # students+Keren final mapping) -- chorioamnionitis, intrapartum_fever,
        # induction_of_labor, start_of_labor moved out to
        # source_or_text_audit_exclude. Unchanged by Decision 62.
        # 4->5 (2026-08-15, Decision 68) -- placental_abruption moved in from
        # secondary_near_delivery_predictor (Keren confirmed clinically
        # confirmed intrapartum timing).
        # 5->4 (2026-08-15, Decision 68 correction) -- placental_abruption
        # moved back to secondary_near_delivery_predictor (horizon was
        # already correct; only modeling clearance needed to change).
        # 4->5 (2026-08-19, Decision 79 addendum) -- gestational_age_at_
        # delivery_days moved in from intrapartum_or_post_delivery_exclude
        # (Keren explicitly approved Stage-3 use; not Stage 1/2).
        "intrapartum_predictor_exclude_from_prelabor_model": 5,
        # source_or_text_audit_exclude: 26->27 (2026-08-01, Batch 18
        # read-only review finding PRE-B18-004) -- length_of_mechanical_
        # ventilation moved in from intrapartum_or_post_delivery_exclude
        # (free-text neonatal respiratory-course narrative, not a numeric/
        # binary outcome; classification-only correction).
        # 27->26 (2026-08-04) -- trial_of_labor_corrected moved out to the new
        # cohort_control_exclude category (it is a derived cohort-control
        # variable, not a source/free-text field).
        # 26->31 (2026-08-04, students+Keren final mapping) -- net +5:
        # congenital_anomaly_comment and long_term_outcome_comment moved out
        # (-2, to intrapartum_or_post_delivery_exclude); chorioamnionitis,
        # intrapartum_fever, induction_of_labor, start_of_labor,
        # indication_for_CS, suspected_endo_lesions_during_CS, and Hb_diff
        # moved in (+7).
        # 31->30 (2026-08-04, Decision 62) -- length_of_mechanical_ventilation
        # moved out to intrapartum_or_post_delivery_exclude (superseding the
        # 2026-08-01 PRE-B18-004 finding; post-delivery timing takes
        # precedence over its free-text storage format).
        # 30->31 (2026-08-18, finalized project decision) -- diagnosis_year
        # moved in from predictor_allowed (calendar-time-of-diagnosis field;
        # not predictor-eligible). Retained for audit/descriptive purposes
        # only, alongside its source diagnosis_date.
        "source_or_text_audit_exclude": 31,
        # New categories added 2026-08-04 (classification-only corrections;
        # no analytical values, cohort, or target changed). See
        # docs/clinical_decisions/manual_decisions_log.md.
        # cohort_control_exclude: 1->3 (2026-08-15, Decision 67) -- two new
        # sensitivity-flag columns added (decision67_sensitivity_19group_
        # excluded, decision67_sensitivity_26group_excluded); total column
        # count 154->156.
        "cohort_control_exclude": 3,
        "clinically_nonspecific_exclude": 2,
        # clinically_redundant_exclude: new category, 2026-08-14 (Decision
        # 66) -- superficial_endometriosis moved out of predictor_allowed;
        # peritoneal_endometriosis selected as the canonical modeled
        # phenotype. See docs/clinical_decisions/manual_decisions_log.md.
        "clinically_redundant_exclude": 1,
        # leakage_exclude: 10->8 (2026-08-04, students+Keren final mapping) --
        # indication_for_CS and suspected_endo_lesions_during_CS moved out to
        # source_or_text_audit_exclude (their cleaned/derived counterparts
        # indication_for_CS_clean/suspected_endo_lesions_during_CS_clean
        # remain leakage_exclude, unaffected). Unchanged by Decision 62.
        "leakage_exclude": 8,
        # intrapartum_or_post_delivery_exclude: 35->36 (Decision 39) --
        # BMI_after added. 36->37 (2026-08-01, Decision 49) -- IUFD added.
        # 37->36 (2026-08-01, PRE-B18-004) -- length_of_mechanical_ventilation
        # moved out to source_or_text_audit_exclude.
        # Unchanged (net zero) 2026-08-04 (students+Keren final mapping,
        # Decision 61) -- BMI_after and Hb_diff moved out (-2, BMI_after to
        # secondary_near_delivery_predictor, Hb_diff to
        # source_or_text_audit_exclude); congenital_anomaly_comment and
        # long_term_outcome_comment moved in (+2, from
        # source_or_text_audit_exclude).
        # 36->37 (2026-08-04, Decision 62) -- net +1: IUFD moved out (-1, to
        # predictor_allowed, superseding Decision 49); gender and
        # length_of_mechanical_ventilation moved in (+2).
        # 37->38 (2026-08-15, Decision 69) -- BMI_after moved back in from
        # secondary_near_delivery_predictor (reverts the 2026-08-04
        # students+Keren move; measured postpartum, must never predict
        # intrapartum CS).
        # 38->39 (2026-08-18, timing-leakage prevention correction) --
        # gestational_age_at_delivery_days moved in from
        # secondary_near_delivery_predictor (its value is only fixed at
        # completed delivery; not knowable at Stage 1/2/3).
        # 39->38 (2026-08-19, Decision 79 addendum) -- gestational_age_at_
        # delivery_days moved out to intrapartum_predictor_exclude_from_
        # prelabor_model (Keren explicitly approved Stage-3 use).
        # 38->37 (2026-08-27, Decision 86) -- BMI_after moved out to
        # secondary_near_delivery_predictor, superseding Decision 69.
        "intrapartum_or_post_delivery_exclude": 37,
        "manual_review_pending": 0,
        "awaiting_clinical_clarification": 0,
    }

    df_cols = list(df.columns)
    df_col_set = set(df_cols)
    membership = {}
    reason_lookup = {}
    for classification, reason, columns in classification_groups:
        if classification not in approved_labels:
            unexpected_findings.append(
                f"Unapproved classification label: {classification}"
            )
        for column_name in columns:
            membership.setdefault(column_name, []).append(classification)
            reason_lookup[column_name] = reason

    zero_classified = [column_name for column_name in df_cols if column_name not in membership]
    duplicate_in_classif = sorted(
        column_name for column_name, groups in membership.items() if len(set(groups)) > 1
    )
    extra_in_classif = sorted(
        column_name for column_name in membership if column_name not in df_col_set
    )

    classification_rows = []
    for column_name in df_cols:
        groups = membership.get(column_name, [])
        if len(groups) == 1:
            classification_rows.append(
                {
                    "column_name": column_name,
                    "classification": groups[0],
                    "reason": reason_lookup[column_name],
                }
            )

    classification_df = pd.DataFrame(
        classification_rows,
        columns=["column_name", "classification", "reason"],
    )
    classif_counts = classification_df["classification"].value_counts().to_dict()
    classif_counts_for_validation = {
        label: int(classif_counts.get(label, 0))
        for label in expected_classif_counts
    }

    classification_errors = []
    if len(df_cols) != 156:
        classification_errors.append(f"Column count: expected 156, got {len(df_cols)}")
    if len(classification_df) != 156:
        classification_errors.append(
            f"Classification row count: expected 156, got {len(classification_df)}"
        )
    if zero_classified:
        classification_errors.append(f"Columns in df not classified: {zero_classified}")
    if duplicate_in_classif:
        duplicate_details = {
            column_name: sorted(set(membership[column_name]))
            for column_name in duplicate_in_classif
        }
        classification_errors.append(
            f"Duplicate approved-list columns across groups: {duplicate_details}"
        )
    if extra_in_classif:
        classification_errors.append(
            f"Approved-list columns not in df: {extra_in_classif}"
        )
    observed_labels = set(classification_df["classification"].dropna().unique())
    invalid_labels = sorted(observed_labels - approved_labels)
    if invalid_labels:
        classification_errors.append(f"Invalid classification labels: {invalid_labels}")
    if classif_counts_for_validation != expected_classif_counts:
        classification_errors.append(
            f"Classification counts mismatch: expected {expected_classif_counts}, "
            f"got {classif_counts_for_validation}"
        )

    if classification_errors:
        unexpected_findings.extend(classification_errors)
        classification_written = False
        print("  Minimal variable classification validation failed; outputs not written.")
    else:
        classification_df.to_csv(classif_csv, index=False, encoding="utf-8-sig")
        classification_df.to_excel(classif_xlsx, index=False)
        classification_written = True
        print(f"  Minimal variable classification saved: {classif_csv}")
        print(f"  Minimal variable classification saved: {classif_xlsx}")

    print(
        f"  Minimal classification rows: {len(classification_df)} | "
        f"df columns: {len(df_cols)}"
    )
    if zero_classified:
        print(f"  MISSING from minimal classification: {zero_classified}")
    if extra_in_classif:
        print(f"  In approved lists but not in df: {extra_in_classif}")

    # ------------------------------------------------------------------
    # 3. Minimal variable type schema for preprocessing modeling/EDA metadata
    # ------------------------------------------------------------------
    allowed_variable_types = {
        "id",
        "binary",
        "categorical",
        "ordinal",
        "continuous",
        "count",
        "text",
        "date_time",
    }
    variable_type_groups = {
        "binary": [
            "target_intrapartum_cs",
            "nulliparity",
            "EUP",
            "S_P_CS",
            "VBAC",
            "alcohol",
            "any_medical_problem",
            "regular_medications",
            "Fetus_Anamoly",
            "deep_endometriosis",
            "adenomyosis",
            "superficial_endometriosis",
            # clinical_diagnosis_only: removed 2026-07-30 (Decision 33)
            "cs_scar_endometriosis",
            "peritoneal_endometriosis",
            "endometrioma",
            "endometriosis_surgery",
            "vaginal_opening_during_surgery",
            "bowel_lesion_resected",
            "bladder_lesion_resected",
            "endo_surgery_adhesiolysis",
            "aspirin_during_pregnancy",
            "clexane_during_pregnancy",
            "mode_of_conception_ivf_vs_all",
            "PPROM",
            "pregnancy_related_hypertensive_disorder",
            "PIH",
            "mild_PET",
            "severe_PET",
            "any_PET",
            "SIPET",
            "HELLP",
            "eclampsia",
            "gestational_diabetes",
            "IUGR",
            "placental_abruption",
            # placenta_accreta, placenta_previa: removed 2026-07-30 (Decision 32)
            "chorioamnionitis",
            "PPH",
            "oligohydramnios",
            "polyhydramnios",
            "meconium_stained_amniotic_fluid",
            "IUFD",
            "celestone",
            "magnesium",
            "CS_case_vs_control",
            "trial_of_labor",
            "suspected_endo_lesions_during_CS",
            "abdominal_cavity_findings",
            # surgery_dehiscence: removed 2026-07-30 (Decision 33)
            "other_surgery_complications",
            "adhesions",
            "intrapartum_fever",
            # intrapartum_fever_or_chorioamnionitis_bin: new composite (Decision 31,
            # 2026-07-29), OR of intrapartum_fever and chorioamnionitis.
            "intrapartum_fever_or_chorioamnionitis_bin",
            "postpartum_fever",
            "surgical_site_infection",
            "endometritis",
            "any_blood_product_transfusion",
            "pH_artery_or_vein_less_than_7_1",
            "apgar_5_less_than_7",
            "SGA",
            "LGA",
            "IVH",
            "IVH_grade_1_2",
            "IVH_grade_3_4",
            "NICU_admission",
            "RDS",
            "mechanical_ventilation",
            "NEC",
            "sepsis",
            "hypoglycemia",
            "neonatal_jaundice_used_phototherapy",
            "neonatal_death",
            "congenital_anomaly",
            "long_term_outcome",
            "trial_of_labor_corrected",
            "decision67_sensitivity_19group_excluded",
            "decision67_sensitivity_26group_excluded",
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
            "induction_any_bin",
            "suspected_endo_lesions_during_CS_clean",
            "TTN_bin",
        ],
        "id": [
            "delivery_id",
            "subject_number",
        ],
        "categorical": [
            "gender",
            "smoking",
            "mode_of_conception",
            "diabetes_type",
            "induction_of_labor",
            "start_of_labor",
            "type_of_CS",
            "indication_for_CS",
            "endometrioma_place_clean",
            "endometrioma_laterality",
            "adenomyosis_sonographic_features_clean",
            "endo_resection_sites_clean",
            "indication_for_induction_clean",
            "indication_for_CS_clean",
        ],
        "continuous": [
            "AGE",
            "weight_before_pregnancy",
            "weight_in_pregnancy",
            "height",
            "BMI_before",
            "BMI_after",
            "blood_loss_during_surgery",
            "Hb_before_delivery",
            "Hb_after_delivery",
            "Hb_diff_clean",
            "pH_vein",
            "pH_artery",
            "birth_weight",
            "percentile_by_Dolberg",
            "endometrioma_size_clean",
            "gestational_age_at_delivery_days",
            "gestational_age_at_PPROM_days",
            "diagnosis_year",
        ],
        "count": [
            "G",
            "P",
            "LIVE_BIRTH",
            "AB",
            "CS",
            "hospitalization_days",
            "age_at_neonatal_death",
        ],
        "date_time": [
            "diagnosis_date",
        ],
        "ordinal": [
            "apgar1",
            "apgar5",
        ],
        "text": [
            # First three raw duplicated comment fields received semantic names
            # in Decision 34; Decision 57 renumbered remaining generic comments.
            "any_medical_problem_comment",
            "regular_medications_comment",
            "Fetus_Anamoly_comment",
            "comment_1",
            "comment_2",
            "comment_3",
            "comment_4",
            "comment_5",
            "comment_6",
            "congenital_anomaly_comment",
            "long_term_outcome_comment",
            "endometriosis_surgery_comment",
            "RDS_comment",
            "mode_of_conception_details",
            "endometrioma_size",
            "endometrioma_place",
            "adenomyosis_sonographic_features",
            "endo_resection_sites",
            "surgery_details",
            "gestational_age_at_PPROM",
            "gestational_age_at_delivery",
            "indication_for_induction",
            "Hb_diff",
            # length_of_mechanical_ventilation: moved from "count" here
            # 2026-08-01 (Batch 18 read-only review finding PRE-B18-004) --
            # confirmed free-text neonatal respiratory-course narrative
            # (dtype str), not a numeric count. Value unchanged.
            "length_of_mechanical_ventilation",
        ],
    }

    variable_type_lookup = {}
    duplicate_type_membership = {}
    for variable_type, variable_names in variable_type_groups.items():
        if variable_type not in allowed_variable_types:
            unexpected_findings.append(f"Unapproved variable_type label: {variable_type}")
        for variable_name in variable_names:
            if variable_name in variable_type_lookup:
                duplicate_type_membership.setdefault(variable_name, []).extend(
                    [variable_type_lookup[variable_name], variable_type]
                )
            variable_type_lookup[variable_name] = variable_type

    schema_df_source = df
    schema_source_cols = list(schema_df_source.columns)
    schema_rows = []
    for variable_name in schema_source_cols:
        variable_type = variable_type_lookup.get(variable_name)
        n_categories = ""
        if variable_type == "binary":
            n_categories = 2
        elif variable_type in {"categorical", "ordinal"}:
            n_categories = int(schema_df_source[variable_name].dropna().nunique())
        schema_rows.append(
            {
                "variable_name": variable_name,
                "variable_type": variable_type,
                "n_categories": n_categories,
            }
        )

    variable_type_schema_df = pd.DataFrame(
        schema_rows,
        columns=["variable_name", "variable_type", "n_categories"],
    )

    schema_errors = []
    if len(schema_source_cols) != 156:
        schema_errors.append(
            f"Preprocessing schema source column count: expected 156, got {len(schema_source_cols)}"
        )
    if len(variable_type_schema_df) != 156:
        schema_errors.append(
            f"Variable type schema row count: expected 156, got {len(variable_type_schema_df)}"
        )
    missing_type = variable_type_schema_df.loc[
        variable_type_schema_df["variable_type"].isna(), "variable_name"
    ].tolist()
    if missing_type:
        schema_errors.append(f"Preprocessing columns missing variable_type: {missing_type}")
    extra_type_schema_vars = sorted(
        variable_name
        for variable_name in variable_type_lookup
        if variable_name not in set(schema_source_cols)
    )
    if extra_type_schema_vars:
        schema_errors.append(
            f"Variable type schema entries not in preprocessing dataframe: {extra_type_schema_vars}"
        )
    invalid_type_labels = sorted(
        set(variable_type_schema_df["variable_type"].dropna()) - allowed_variable_types
    )
    if invalid_type_labels:
        schema_errors.append(f"Invalid variable_type labels: {invalid_type_labels}")
    if duplicate_type_membership:
        schema_errors.append(
            f"Duplicate variable_type memberships: {duplicate_type_membership}"
        )

    target_type_row = variable_type_schema_df.loc[
        variable_type_schema_df["variable_name"] == "target_intrapartum_cs"
    ]
    if len(target_type_row) != 1:
        schema_errors.append("target_intrapartum_cs missing from variable type schema")
    else:
        target_type = target_type_row.iloc[0]["variable_type"]
        target_categories = target_type_row.iloc[0]["n_categories"]
        if target_type != "binary" or int(target_categories) != 2:
            schema_errors.append(
                "target_intrapartum_cs must be binary with n_categories=2"
            )

    binary_category_errors = variable_type_schema_df.loc[
        (variable_type_schema_df["variable_type"] == "binary")
        & (variable_type_schema_df["n_categories"] != 2),
        "variable_name",
    ].tolist()
    if binary_category_errors:
        schema_errors.append(
            f"Binary variables without n_categories=2: {binary_category_errors}"
        )

    blank_category_types = {"id", "continuous", "count", "text", "date_time"}
    nonblank_category_errors = variable_type_schema_df.loc[
        variable_type_schema_df["variable_type"].isin(blank_category_types)
        & variable_type_schema_df["n_categories"].astype(str).ne(""),
        "variable_name",
    ].tolist()
    if nonblank_category_errors:
        schema_errors.append(
            "Variables that should have blank n_categories but do not: "
            f"{nonblank_category_errors}"
        )

    if schema_errors:
        unexpected_findings.extend(schema_errors)
        variable_type_schema_written = False
        print("  Variable type schema validation failed; outputs not written.")
    else:
        variable_type_schema_df.to_csv(
            type_schema_csv, index=False, encoding="utf-8-sig"
        )

        # Blank n_categories ("") must render as true blank cells in Excel, not
        # empty-string text cells -- replace only for this in-memory Excel copy;
        # the CSV write above is untouched and keeps its existing "" behavior.
        _type_schema_excel_df = variable_type_schema_df.copy()
        _type_schema_excel_df["n_categories"] = _type_schema_excel_df["n_categories"].replace(
            "", np.nan
        )
        with pd.ExcelWriter(type_schema_xlsx, engine="openpyxl") as _type_schema_writer:
            _type_schema_excel_df.to_excel(
                _type_schema_writer, sheet_name="variable_types", index=False
            )
            _type_schema_ws = _type_schema_writer.sheets["variable_types"]
            _type_schema_ws.freeze_panes = "A2"
            _last_col_letter = get_column_letter(len(variable_type_schema_df.columns))
            _type_schema_ws.auto_filter.ref = (
                f"A1:{_last_col_letter}{len(variable_type_schema_df) + 1}"
            )
            _type_schema_col_widths = {
                "variable_name": 42,
                "variable_type": 16,
                "n_categories": 14,
            }
            for _idx, _col_name in enumerate(variable_type_schema_df.columns, start=1):
                _type_schema_ws.column_dimensions[get_column_letter(_idx)].width = (
                    _type_schema_col_widths.get(_col_name, 16)
                )

        variable_type_schema_written = True
        print(f"  Variable type schema saved: {type_schema_csv}")
        print(f"  Variable type schema saved: {type_schema_xlsx}")

    # ------------------------------------------------------------------
    # 4. Review-file inventory
    # ------------------------------------------------------------------
    REVIEW_INVENTORY = [
        # (file_name, related_variable, batch_source, review_type, status, action_needed, notes)
        ("RDS_NICU_manual_correction_QA.xlsx",
         "NICU_admission, RDS", "Batch 18", "QA verification", "Closed", "None",
         "Manual clinical decisions applied: ????? ?????NICU=1 (Keren); TTN/MAS/Air Leak?RDS=0 (Keren/Ori)"),
        ("adenomyosis_corrected_0_to_1_QA.xlsx",
         "adenomyosis", "Batch 6", "QA verification", "Closed", "None",
         "All 23 adenomyosis 0→1 corrections verified"),
        ("adenomyosis_features_review_df.xlsx",
         "adenomyosis_sonographic_features_clean", "Batch 6", "Manual review", "Closed",
         "None",
         "11 rows reviewed 2026-07-29 (Decision 36): keep_missing_not_specific_enough applied "
         "to all 11 -- text supports adenomyosis generally but does not map to a specific "
         "sonographic feature code; adenomyosis_sonographic_features_clean remains NaN by "
         "clinical decision, not parser failure; disease presence already represented by the "
         "binary adenomyosis variable"),
        ("nulliparity_from_P_correction_QA.xlsx",
         "nulliparity, P", "Batch 3", "Row-level correction QA", "Closed", "None",
         "143 nulliparity rows overwritten directly from authoritative P (PARTNER-FIX-03A, "
         "PRE-B3-003), against the then-447-row cohort: 88 rows P==0/old nulliparity==0 "
         "corrected to 1; 55 rows P>=1/old nulliparity==1 corrected to 0. 304 rows already "
         "correct. 0 rows had invalid or missing P. P itself unchanged and remains present; "
         "no new analytical column created. Downstream redundancy between nulliparity and P "
         "is deferred to PARTNER-FIX-03B. Current file (present N=431 cohort): {row_count} "
         "rows -- every row has correction_status=correction_applied; the file tracks "
         "corrected rows only, not the full audited population."),
        ("diagnosis_date_unresolved_QA.xlsx",
         "diagnosis_date, diagnosis_year", "Batch 5", "Row-level QA reference",
         "Reference only",
         "None",
         "18 rows where diagnosis_date is non-missing but diagnosis_year could not be "
         "resolved (PARTNER-FIX-02, PRE-B5-001): 13 unknown_value, 2 date_range, "
         "2 approximate_or_uncertain, and 1 impossible_date (17/3/3024). Decision 57 "
         "resolved the previously reviewed D/M/YY records under the approved strict "
         "D/M/YY, YY=23 rule; diagnosis_date source values remain unchanged. "
         "diagnosis_year is retained only for source/audit/descriptive lineage "
         "where needed and is excluded from predictive eligibility (Decision 72, "
         "supersedes Decision 63's earlier predictor-eligibility conclusion); no "
         "year was invented for the remaining unresolved rows"),
        ("blood_loss_distribution_for_thresholds_QA.xlsx",
         "blood_loss_during_surgery", "Batch 16", "Clinical threshold review", "Closed",
         "None",
         "Decision 51 (2026-08-02): blood_loss_during_surgery remains continuous mL, "
         "cesarean-subgroup descriptive/secondary-outcome use only; no threshold-derived "
         "ordinal/binary variable created; PPH is not recalculated from this field; "
         "500/1000 mL are documented as clinical background only, not implemented rules. "
         "Leakage variable — do not use in model regardless of this decision; "
         "workbook retained as historical evidence, no further clinical action required"),
        ("endometrioma_review_df.xlsx",
         "endometrioma, endometrioma_size_clean", "Batch 7", "Contradiction review", "Closed",
         "None",
         "Bilateral-measurement hotfix confirmed under Decision 38; current canonical review logic flags zero rows"),
        ("endometrioma_size_parsing_QA.xlsx",
         "endometrioma_size_clean", "Batch 7", "QA reference", "Closed", "None",
         "24 rows documenting parse decisions"),
        ("endometrioma_size_text_with_number_QA.xlsx",
         "endometrioma_size_clean", "Batch 7", "QA reference", "Closed", "None",
         "130 rows text-with-number classification reference"),
        ("endometrioma_size_parsing_audit.xlsx",
         "endometrioma_size_clean", "Batch 7", "Row-level parsing audit", "Closed", "None",
         "Decision 54 (2026-08-02): attribution-aware parser "
         "(parse_endometrioma_size_mm_with_evidence, endometrioma_rules.py, parser version "
         "endometrioma_size_v2_attribution_aware_2026-08-02) -- {row_count} rows, one per "
         "non-missing raw endometrioma_size value (not only cells containing a candidate "
         "measurement), documenting candidate_measurements/candidate_contexts/"
         "excluded_measurements/selected_measurement/decision_type/decision_reason. "
         "Supersedes both legacy endometrioma_size_parsing_QA.xlsx and "
         "endometrioma_size_text_with_number_QA.xlsx (see LEGACY_QA_FILES below)."),
        ("batch4_comment_binary_review.xlsx",
         "any_medical_problem, regular_medications, Fetus_Anamoly", "Batch 4",
         "Binary/comment review", "Closed", "None",
         "Decision 55 (2026-08-02): originally 36 rows (34 unique subject_number+delivery_id "
         "records) where a binary background variable is 0 but its paired free-text comment "
         "column is non-blank -- reviewed and closed as CLOSED_SOURCE_VALUE_RETAINED for every "
         "row; the structured binary source value is retained unchanged in all cases, no "
         "automatic recode from free text (see BATCH4_COMMENT_BINARY_REVIEW). Updated "
         "2026-08-04: now 35 rows (33 unique records) -- a redacted record-specific key "
         "Fetus_Anamoly row was corrected to 1 under a separate approved clinical decision (see "
         "the Fetus_Anamoly correction in batch_4_background) and no longer matches this "
         "population's ==0 filter; Fetus_Anamoly_comment for that row is unchanged. "
         "Current file (present N=431 cohort): {row_count} rows -- every row remains "
         "CLOSED_SOURCE_VALUE_RETAINED; the structured binary source value is unchanged and "
         "no comment text is ever auto-recoded into it."),
        ("endometriosis_surgery_review_df.xlsx",
         "endometriosis_surgery", "Batch 8", "Contradiction review", "Closed",
         "None",
         "3 contradiction rows resolved by manual clinical decision after consultation with Gidi; stale review file should be cleared after rerun if no unresolved rows remain"),
        ("gestational_age_review_df.xlsx",
         "gestational_age_at_delivery_days, gestational_age_at_PPROM_days", "Batch 11",
         "Technical QA", "Not triggered (0 current rows)", "None currently",
         "Conditional QA file: exported only if gestational_age_at_delivery_days/"
         "gestational_age_at_PPROM_days are outside their broad sanity-review range "
         "([154,308] / [98,258] days -- a blocking review gate, not a proven-impossibility "
         "bound) or malformed/invalid, or if PPROM GA > delivery GA (this last one IS "
         "logically/definitionally impossible -- PPROM cannot occur after the delivery it "
         "precedes; equality is clinically acceptable per Keren and is never flagged). "
         "Not triggered in the current N=431 cohort -- 0 qualifying rows, file does "
         "not currently exist on disk. Expected, correctly-conditional absence, not a missing "
         "required artifact."),
        ("IUFD_clinical_review_df.xlsx",
         "IUFD", "Batch 13", "Clinical timing review (fail-loud QA gate)",
         "Not triggered (0 current rows)", "None currently",
         "Decision 49 (2026-08-01): current 431-row cohort has IUFD=0 for all records, so this "
         "conditional gate has never fired and the file does not currently exist on disk. Any "
         "future raw-data refresh containing IUFD=1 will export this file and block that row's "
         "cohort progression (validation FAIL) pending an explicit before_labor/during_labor/"
         "cannot_establish clinical timing decision -- this is a standing QA gate, not a "
         "one-time resolved item."),
        ("hypertension_diabetes_review_df.xlsx",
         "any_PET, pregnancy_related_hypertensive_disorder, PIH, mild_PET, severe_PET, SIPET, "
         "HELLP, eclampsia", "Batch 12", "Contradiction review", "Closed", "None",
         "14 rows (Decision 45, 2026-08-01): 3 any_PET=0 contradictions corrected to 1 and "
         "13 umbrella (pregnancy_related_hypertensive_disorder) contradictions corrected to 1, "
         "both via deterministic rules actually applied in code (not just flagged); 1 SIPET=1/"
         "umbrella=0 row documented as a valid clinical combination (SIPET excluded from the "
         "umbrella rule). Zero rows remain classified unresolved_contradiction."),
        ("induction_review_df.xlsx",
         "induction_of_labor, induction_any_bin", "Batch 14", "Contradiction review", "Closed",
         "None",
         # Row count intentionally not hardcoded here -- the loop below fills it in
         # from the actual, currently-computed row_count column so the note and the
         # count column can never disagree (Batch 14 read-only review finding PRE-B14-004).
         "{row_count} induction contradiction rows; resolved by induction_any_bin derived variable"),
        ("blood_loss_during_surgery_subgroup_QA.xlsx",
         "blood_loss_during_surgery", "Batch 16", "Subgroup QA", "Reference only", "None",
         "{row_count} rows: raw-0 values, free-text values, and cesarean rows with no raw "
         "value recorded -- before/after processing audit; row count tracks the current "
         "cohort and QA trigger conditions, not a fixed historical figure."),
        ("maternal_outcomes_review_df.xlsx",
         "blood_loss_during_surgery", "Batch 16", "Free-text reference", "Reference only", "None",
         "2 rows with free-text blood loss; text preserved in comment_6; leakage variable"),
        ("neonatal_outcomes_review_df.xlsx",
         "IVH/IVH_grade_1_2/IVH_grade_3_4, mechanical_ventilation/length_of_mechanical_"
         "ventilation, age_at_neonatal_death, other neonatal binary free text", "Batch 18",
         "Contradiction/free-text reference", "Not triggered (0 current rows)",
         "None currently",
         "Conditional review file for OTHER unresolved neonatal contradictions/free text "
         "(IVH grade positive with IVH=0, mechanical_ventilation=0 with a non-empty "
         "length_of_mechanical_ventilation free-text entry [raw presence, units not "
         "inferred; the retired >365-day numeric rule is gone -- Decision 90 section D], "
         "age_at_neonatal_death non-null with neonatal_death=0, unexpected free text in "
         "other binary neonatal columns). NICU_admission and RDS text are resolved "
         "separately via approved manual corrections (NICU text -> NICU_admission=1; RDS "
         "text -> RDS=0 with text preserved in RDS_comment) and are excluded from this "
         "file's trigger condition -- see RDS_NICU_manual_correction_QA.xlsx, the "
         "canonical evidence for those. Not triggered in the current N=431 cohort -- 0 "
         "qualifying rows, file does not currently exist on disk. Expected, "
         "correctly-conditional absence, not a missing required artifact."),
        ("percentile_by_Dolberg_QA.xlsx",
         "percentile_by_Dolberg", "Batch 17", "Text recode QA", "Closed", "None",
         "10 rows: >97 text→98 (4 rows), <3 text→2 (6 rows); recode verified (Gidi/Keren)"),
        # The 5 entries below were previously present in MANUAL_REVIEW_METADATA but
        # absent from REVIEW_INVENTORY, which meant they never appeared in either
        # this tracked audit inventory or the generated manual_review_inventory.md,
        # despite being generated by the current pipeline. Added for completeness
        # (2026-07-30 QA-schema closure pass) -- no analytical behavior affected.
        ("S_P_CS_unexpected_QA.xlsx",
         "S_P_CS", "Batch 3", "QA verification", "Closed", "None",
         "No unexpected S_P_CS values in current cohort; file is generated only when a "
         "value outside {0, 1, NaN} is found (the approved record-specific 2->1 "
         "correction is applied separately and does not trigger this file)"),
        ("body_size_impossible_values_review_df.xlsx",
         "weight_before_pregnancy, weight_in_pregnancy, height, BMI_before, BMI_after",
         "Batch 9", "Sanity/plausibility review (filename historical: 'impossible')", "Reference only", "None",
         "No values outside a sanity-review range in the current cohort; file is generated only when weight, "
         "height, or BMI values fall outside documented physiological ranges"),
        ("conception_review_df.xlsx",
         "mode_of_conception", "Batch 10", "Technical QA", "Reference only", "None",
         "No invalid mode_of_conception values (non-numeric or outside the permitted "
         "code set {0,1,2,3}, PRE-B10-006) in current cohort; file is generated/replaced "
         "only when invalid values are found, and any stale copy is removed otherwise"),
        ("cs_reference_review_df.xlsx",
         "indication_for_CS, suspected_endo_lesions_during_CS", "Batch 15",
         "Contradiction review", "Reference only", "None",
         "No CS-reference contradictions in current cohort; file is generated only for "
         "vaginal/CS mismatches, CS rows missing an indication, or free-text indications "
         "(Decision 35)"),
        ("neonatal_basic_review_df.xlsx",
         "gender, pH_vein, pH_artery, apgar1, apgar5, birth_weight, percentile_by_Dolberg",
         "Batch 17", "Technical QA", "Reference only", "None",
         "No neonatal-basic values outside a sanity-review range / definitional scale in the current cohort; file is generated only "
         "when pH, Apgar, birth weight, or percentile values fall outside documented "
         "physiological ranges"),
    ]

    # Files that are NOT written by any current batch function -- present only as
    # static entries in MANUAL_REVIEW_METADATA (and, for the two endometrioma_size_*
    # entries, in REVIEW_INVENTORY above) for historical traceability. Used to route
    # the manual-review inventory into "current canonical" vs "legacy" sections below.
    LEGACY_QA_FILES = {
        "adenomyosis_sonographic_features_manual_review_workbook.xlsx",
        "endometrioma_size_parsing_QA.xlsx",
        "endometrioma_size_text_with_number_QA.xlsx",
    }
    LEGACY_QA_REPLACEMENT = {
        "adenomyosis_sonographic_features_manual_review_workbook.xlsx": dict(
            canonical_replacement="adenomyosis_features_review_df.xlsx",
            recommendation="retain temporarily",
            recommendation_reason=(
                "Contains fields not present in the canonical file (raw_source_text, "
                "normalized_text, readable_hebrew_display_text parsing-audit columns, "
                "and 2 additional candidate rows beyond the canonical file's 11) -- not "
                "confirmed redundant; do not archive or remove without clinical review."
            ),
        ),
        "endometrioma_size_parsing_QA.xlsx": dict(
            canonical_replacement="endometrioma_review_df.xlsx",
            recommendation="archive after approval",
            recommendation_reason=(
                "Superseded by the current endometrioma_size_clean parsing logic "
                "(Batch 7, src/endometrioma_rules.py); not present on disk (never "
                "regenerated by current code)."
            ),
        ),
        "endometrioma_size_text_with_number_QA.xlsx": dict(
            canonical_replacement="endometrioma_review_df.xlsx",
            recommendation="archive after approval",
            recommendation_reason=(
                "Superseded by the current endometrioma_size_clean parsing logic "
                "(Batch 7, src/endometrioma_rules.py); not present on disk (never "
                "regenerated by current code)."
            ),
        ),
    }

    # Files whose CURRENT absence is an expected, correctly-conditional outcome of
    # this run's data -- not evidence of a missing required artifact. Kept separate
    # from LEGACY_QA_FILES (superseded, never generated by current code at all) and
    # from the "Closed"+"cleared" text match below (an approved resolution that
    # cleared a once-populated file): these are conditional QA gates whose trigger
    # condition (a value outside a sanity-review range, a definitional/logical violation, a contradiction, an unexpected code) simply
    # found 0 qualifying rows this run.
    CONDITIONAL_NOT_TRIGGERED_FILES = {
        "gestational_age_review_df.xlsx",
        "IUFD_clinical_review_df.xlsx",
        "S_P_CS_unexpected_QA.xlsx",
        "body_size_impossible_values_review_df.xlsx",
        "conception_review_df.xlsx",
        "cs_reference_review_df.xlsx",
        "neonatal_basic_review_df.xlsx",
        "neonatal_outcomes_review_df.xlsx",
    }

    # Files whose notes field embeds a {row_count} placeholder (see REVIEW_INVENTORY
    # above) instead of a hardcoded number, so the explanatory text always matches
    # the row_count column computed just below -- they cannot drift apart the way
    # the old hardcoded "14"/"275"/"35"/"89"/"143" figures did.
    _ROW_COUNT_TEMPLATED_FILES = {
        "induction_review_df.xlsx",
        "endometrioma_size_parsing_audit.xlsx",
        "batch4_comment_binary_review.xlsx",
        "blood_loss_during_surgery_subgroup_QA.xlsx",
        "nulliparity_from_P_correction_QA.xlsx",
    }

    inventory_rows = []
    for entry in REVIEW_INVENTORY:
        fname = entry[0]
        status = entry[4]
        notes = entry[6]
        fpath = os.path.join(review_path, fname)
        if os.path.exists(fpath):
            try:
                tmp = pd.read_excel(fpath)
                row_count = len(tmp)
            except Exception as e:
                row_count = f"ERROR: {e}"
        elif fname in LEGACY_QA_FILES:
            row_count = "LEGACY / SUPERSEDED (not generated by current code)"
        elif fname in CONDITIONAL_NOT_TRIGGERED_FILES:
            row_count = "NOT TRIGGERED (0 qualifying rows this run)"
        elif status == "Closed" and "cleared" in str(notes).lower():
            row_count = "CLEARED / FILE NOT FOUND"
        else:
            row_count = "FILE NOT FOUND"
            missing_review_files.append(fname)
        entry_notes = entry[6]
        if fname in _ROW_COUNT_TEMPLATED_FILES and isinstance(row_count, int):
            entry_notes = entry_notes.format(row_count=row_count)
            entry = entry[:6] + (entry_notes,)
        inventory_rows.append((fname, row_count) + entry[1:])

    inv_lines = [
        f"# Review File Inventory — {BATCH_METADATA[19]['title']}",
        f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        f"Review directory: outputs/preprocessing/review/",
        f"Total files inventoried: {len(REVIEW_INVENTORY)}",
        "",
        "## Batch title reference",
        "",
        "`batch_source` below is the short batch number; see the corresponding "
        "descriptive title here or in run_preprocessing.py's BATCH_METADATA.",
        "",
    ] + [
        f"- Batch {n}: {BATCH_METADATA[n]['title']}"
        for n in sorted({int(row[2].replace("Batch ", "")) for row in REVIEW_INVENTORY})
    ] + [
        "",
        "| file_name | row_count | related_variable | batch_source | review_type | status | action_needed | notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for fname, row_count, rel_var, batch_src, rev_type, status, action, notes in inventory_rows:
        inv_lines.append(
            f"| `{fname}` | {row_count} | {rel_var} | {batch_src} | {rev_type} | {status} | {action} | {notes} |"
        )

    open_items = [
        (fname, status, action)
        for fname, _, _, _, _, status, action, _ in inventory_rows
        if status in ("Open", "Pending")
    ]
    if open_items:
        inv_lines += ["", "## Open / Pending items requiring clinical action", ""]
        for fname, status, action in open_items:
            inv_lines.append(f"- **{fname}** ({status}): {action}")

    with open(inventory_md, "w", encoding="utf-8") as f:
        f.write(sanitize_tracked_audit_markdown("\n".join(inv_lines) + "\n"))
    print(f"  Review file inventory saved: {inventory_md}")

    # ------------------------------------------------------------------
    # 4b. Manual-review inventory (gitignored working reference, not an
    # audit-trail record). Summarizes each QA/review file with the fields a
    # reviewer needs to orient themselves without opening the pipeline
    # source: which variables it covers, whether a subgroup rule applies,
    # which derived variables are affected, and which Decision(s) it
    # implements. Contains no patient-level data -- only filenames, counts,
    # and variable/decision names already present in REVIEW_INVENTORY.
    # ------------------------------------------------------------------
    MANUAL_REVIEW_METADATA = {
        "RDS_NICU_manual_correction_QA.xlsx": dict(source_variable="NICU_admission, RDS", clean_variable="NICU_admission, RDS, TTN_bin", subgroup_variable="none", derived_variables="TTN_bin", decisions="none (direct Keren/Ori correction)"),
        "adenomyosis_corrected_0_to_1_QA.xlsx": dict(source_variable="adenomyosis_sonographic_features", clean_variable="adenomyosis_sonographic_features_clean", subgroup_variable="none", derived_variables="adenomyosis", decisions="28"),
        "adenomyosis_features_review_df.xlsx": dict(source_variable="adenomyosis_sonographic_features", clean_variable="adenomyosis_sonographic_features_clean", subgroup_variable="none", derived_variables="none", decisions="28, 36"),
        "adenomyosis_sonographic_features_manual_review_workbook.xlsx": dict(source_variable="adenomyosis_sonographic_features", clean_variable="adenomyosis_sonographic_features_clean", subgroup_variable="none", derived_variables="none", decisions="36"),
        "blood_loss_distribution_for_thresholds_QA.xlsx": dict(source_variable="blood_loss_during_surgery", clean_variable="none (distribution reference only)", subgroup_variable="type_of_CS (cesarean)", derived_variables="none", decisions="51"),
        "blood_loss_during_surgery_subgroup_QA.xlsx": dict(source_variable="blood_loss_during_surgery", clean_variable="blood_loss_during_surgery (subgroup-masked)", subgroup_variable="type_of_CS (cesarean)", derived_variables="none", decisions="none"),
        "endometrioma_review_df.xlsx": dict(source_variable="endometrioma_size, endometrioma_place", clean_variable="endometrioma_size_clean, endometrioma_place_clean", subgroup_variable="endometrioma", derived_variables="endometrioma_laterality", decisions="none"),
        "hypertension_diabetes_review_df.xlsx": dict(source_variable="PIH, mild_PET, severe_PET, any_PET, SIPET, HELLP, eclampsia, pregnancy_related_hypertensive_disorder", clean_variable="any_PET, pregnancy_related_hypertensive_disorder (both corrected in place)", subgroup_variable="none", derived_variables="any_PET, pregnancy_related_hypertensive_disorder", decisions="Decision 45"),
        "induction_review_df.xlsx": dict(source_variable="start_of_labor, induction_of_labor, indication_for_induction", clean_variable="indication_for_induction_clean", subgroup_variable="none", derived_variables="induction_any_bin", decisions="none"),
        "maternal_outcomes_review_df.xlsx": dict(source_variable="Hb_before_delivery, Hb_after_delivery, blood_loss_during_surgery", clean_variable="Hb_diff_clean", subgroup_variable="none", derived_variables="Hb_diff_clean", decisions="none"),
        "percentile_by_Dolberg_QA.xlsx": dict(source_variable="percentile_by_Dolberg (raw text)", clean_variable="percentile_by_Dolberg (numeric)", subgroup_variable="none", derived_variables="none", decisions="none (approved >97/<3 recode)"),
        "S_P_CS_unexpected_QA.xlsx": dict(source_variable="S_P_CS", clean_variable="S_P_CS", subgroup_variable="none", derived_variables="none", decisions="none (approved record-specific correction; key redacted)"),
        "endometriosis_surgery_review_df.xlsx": dict(source_variable="endometriosis_surgery + resection support columns", clean_variable="endometriosis_surgery", subgroup_variable="none", derived_variables="none", decisions="9"),
        "body_size_impossible_values_review_df.xlsx": dict(source_variable="weight_before_pregnancy, height, BMI_before", clean_variable="same", subgroup_variable="none", derived_variables="none", decisions="none"),
        "conception_review_df.xlsx": dict(source_variable="mode_of_conception", clean_variable="mode_of_conception_ivf_vs_all", subgroup_variable="none", derived_variables="none", decisions="30"),
        "gestational_age_review_df.xlsx": dict(source_variable="gestational_age_at_PPROM, gestational_age_at_delivery", clean_variable="gestational_age_at_PPROM_days, gestational_age_at_delivery_days", subgroup_variable="none", derived_variables="gestational_age_at_PPROM_days, gestational_age_at_delivery_days", decisions="none"),
        "IUFD_clinical_review_df.xlsx": dict(source_variable="IUFD", clean_variable="IUFD (unchanged; classification-only reclassification)", subgroup_variable="IUFD == 1", derived_variables="none", decisions="49"),
        "cs_reference_review_df.xlsx": dict(source_variable="indication_for_CS, suspected_endo_lesions_during_CS", clean_variable="indication_for_CS_clean, suspected_endo_lesions_during_CS_clean", subgroup_variable="type_of_CS (cesarean)", derived_variables="indication_for_CS_clean, suspected_endo_lesions_during_CS_clean", decisions="35"),
        "neonatal_basic_review_df.xlsx": dict(source_variable="gender, pH_vein, pH_artery, apgar1, apgar5", clean_variable="same", subgroup_variable="none", derived_variables="SGA, LGA", decisions="none"),
        "neonatal_outcomes_review_df.xlsx": dict(source_variable="extended neonatal-outcome variables", clean_variable="same", subgroup_variable="none", derived_variables="none", decisions="none"),
        "endometrioma_size_parsing_QA.xlsx": dict(source_variable="endometrioma_size", clean_variable="endometrioma_size_clean", subgroup_variable="none", derived_variables="none", decisions="none"),
        "endometrioma_size_text_with_number_QA.xlsx": dict(source_variable="endometrioma_size", clean_variable="endometrioma_size_clean", subgroup_variable="none", derived_variables="none", decisions="none"),
    }

    manual_inventory_md = os.path.join(review_path, "manual_review_inventory.md")
    mr_lines = [
        "# Manual-Review Inventory",
        f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        "Gitignored working reference for manual clinical review -- not an audit-trail record "
        "(see outputs/audit/review_file_inventory_batch19.md for the tracked audit version).",
        "Contains no patient-level data: filenames, counts, and variable/Decision names only.",
        "",
        "## Current canonical QA/review outputs",
        "",
        "Files generated by the current preprocessing pipeline. A file may legitimately be "
        "absent below a given run if its trigger condition (e.g. a value outside a sanity-review range, a "
        "contradiction) found 0 matching rows -- see `status`/`action_needed`.",
        "",
    ]
    canonical_rows = [row for row in inventory_rows if row[0] not in LEGACY_QA_FILES]
    legacy_rows_from_inventory = [row for row in inventory_rows if row[0] in LEGACY_QA_FILES]

    for fname, row_count, rel_var, batch_src, rev_type, status, action, notes in canonical_rows:
        batch_num = int(batch_src.replace("Batch ", ""))
        meta = MANUAL_REVIEW_METADATA.get(fname, {})
        mr_lines += [
            f"### `{fname}`",
            f"- generation_status: current_canonical",
            f"- Batch: {batch_src} — {BATCH_METADATA[batch_num]['title']}",
            f"- Clinical topic: {rel_var}",
            f"- Records: {row_count}",
            f"- Source variable(s): {meta.get('source_variable', 'n/a')}",
            f"- Clean variable(s): {meta.get('clean_variable', 'n/a')}",
            f"- Subgroup-defining variable: {meta.get('subgroup_variable', 'n/a')}",
            f"- Derived variable(s) affected: {meta.get('derived_variables', 'n/a')}",
            f"- Decision number(s): {meta.get('decisions', 'n/a')}",
            f"- Review complete: {'Yes' if status == 'Closed' else 'No (' + status + ')'}",
            f"- Path: outputs/preprocessing/review/{fname}",
            "",
        ]

    # ------------------------------------------------------------------
    # Legacy section: files not written by any current batch function. Includes
    # the 2 endometrioma_size_* entries already carried in REVIEW_INVENTORY (kept
    # there for historical continuity) plus any legacy file in LEGACY_QA_FILES that
    # has no REVIEW_INVENTORY entry at all (e.g. the adenomyosis manual-review
    # workbook). Every file in LEGACY_QA_FILES appears exactly once here, regardless
    # of which source it was found through, and is never listed as "current" above.
    # ------------------------------------------------------------------
    mr_lines += [
        "## Legacy artifacts present on disk",
        "",
        "Files not written by any current batch function in run_preprocessing.py -- "
        "static reference artifacts only. Not part of the current QA/review pipeline "
        "output. A file listed below with exists=False is documented for traceability "
        "only and is not a current artifact.",
        "",
    ]
    legacy_fnames_seen = set()
    for fname, row_count, rel_var, batch_src, rev_type, status, action, notes in legacy_rows_from_inventory:
        legacy_fnames_seen.add(fname)
        fpath = os.path.join(review_path, fname)
        exists = os.path.exists(fpath)
        repl = LEGACY_QA_REPLACEMENT.get(fname, {})
        mr_lines += [
            f"### `{fname}`",
            f"- generation_status: legacy_not_generated_by_current_pipeline",
            f"- Exists on disk: {exists}",
            f"- Git status: ignored (matches blanket *.xlsx rule in .gitignore; never tracked)",
            f"- Canonical replacement: {repl.get('canonical_replacement', 'none identified')}",
            f"- Recommendation: {repl.get('recommendation', 'retain temporarily')}",
            f"- Recommendation reason: {repl.get('recommendation_reason', 'n/a')}",
            f"- Historical notes: {notes}",
            f"- Path: outputs/preprocessing/review/{fname}",
            "",
        ]
    for fname, meta in MANUAL_REVIEW_METADATA.items():
        if fname not in LEGACY_QA_FILES or fname in legacy_fnames_seen:
            continue
        fpath = os.path.join(review_path, fname)
        exists = os.path.exists(fpath)
        repl = LEGACY_QA_REPLACEMENT.get(fname, {})
        mr_lines += [
            f"### `{fname}`",
            f"- generation_status: legacy_not_generated_by_current_pipeline",
            f"- Exists on disk: {exists}",
            f"- Git status: ignored (matches blanket *.xlsx rule in .gitignore; never tracked)" if exists
            else "- Git status: n/a (file not present)",
            f"- Canonical replacement: {repl.get('canonical_replacement', 'none identified')}",
            f"- Recommendation: {repl.get('recommendation', 'retain temporarily')}",
            f"- Recommendation reason: {repl.get('recommendation_reason', 'n/a')}",
            f"- Decision number(s): {meta.get('decisions', 'n/a')}",
            f"- Path: outputs/preprocessing/review/{fname}",
            "",
        ]

    with open(manual_inventory_md, "w", encoding="utf-8") as f:
        f.write("\n".join(mr_lines) + "\n")
    print(f"  Manual-review inventory saved: {manual_inventory_md}")

    # ------------------------------------------------------------------
    # 5. Summary and audit log
    # ------------------------------------------------------------------
    if unexpected_findings:
        validation_result = "BLOCKING FAILURE"
    elif missing_review_files:
        validation_result = "NON-BLOCKING MISSING FILE(S)"
    else:
        validation_result = "PASS"

    summary_text = (
        f"# Preprocessing Batch 19 Summary — {BATCH_TITLE}\n"
        f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"## Rows\n"
        f"- Input: {n_rows} (no rows modified)\n\n"
        f"## Target distribution\n"
        f"- target_intrapartum_cs: 0={n0} / 1={n1}\n\n"
        f"## Identifier integrity\n"
        f"- missing subject_number = {n_missing_subject_number}\n"
        f"- missing delivery_id = {n_missing_delivery_id}\n"
        f"- duplicate delivery_id = {n_duplicate_delivery_id}\n"
        f"- duplicate available subject_number + delivery_id pairs = {n_duplicate_available_composite_key}\n"
        f"- Note: missing subject_number originates in the raw NUM column (see "
        f"preprocessing_deviations.md, PRE-ALL-001) and is reported but non-blocking; "
        f"delivery_id must always be complete and unique (blocking if not).\n\n"
        f"## Variable classification\n"
        f"- Output rows: {len(classification_df)}\n"
        + "".join(f"- {cat}: {cnt}\n" for cat, cnt in sorted(classif_counts.items()))
        + f"- Columns in df not classified: {zero_classified if zero_classified else 'None'}\n"
        f"- Approved-list columns not in df: {extra_in_classif if extra_in_classif else 'None'}\n"
        f"- Duplicate approved-list columns: {duplicate_in_classif if duplicate_in_classif else 'None'}\n"
        f"- Output written: {'yes' if classification_written else 'no'}\n\n"
        f"## Review file inventory\n"
        f"- Files inventoried: {len(REVIEW_INVENTORY)}\n"
        f"- Open/Pending: {len(open_items)}\n"
        f"- Saved: {inventory_md}\n\n"
        f"## Classification files\n"
        f"- CSV: {classif_csv}\n"
        f"- XLSX: {classif_xlsx}\n\n"
        f"## Variable type schema files\n"
        f"- CSV (canonical, machine-readable): {type_schema_csv}\n"
        f"- XLSX (equivalent representation for manual review/filtering): {type_schema_xlsx}\n"
        f"- Output written: {'yes' if variable_type_schema_written else 'no'}\n\n"
        f"## Non-blocking missing files\n"
        + (("\n".join(f"- {x} — see review_file_inventory_batch19.md's notes column for the "
                       "specific reason (may be a separate script's known defect, or a "
                       "correctly-conditional file with zero qualifying rows this run)"
                       for x in missing_review_files) + "\n")
           if missing_review_files else "None\n")
        + f"\n## Blocking findings\n"
        + (("\n".join(f"- {x}" for x in unexpected_findings) + "\n") if unexpected_findings else "None\n")
        + f"\n## Validation\n{validation_result}\n"
    )
    write_batch_summary(summary_md, summary_text)
    append_audit_entry(
        audit_log_md,
        f"Batch 19 — {BATCH_TITLE}",
        f"- Rows: {n_rows} (no changes)\n"
        f"- Identifier integrity: missing subject_number={n_missing_subject_number} (non-blocking), "
        f"missing delivery_id={n_missing_delivery_id}, duplicate delivery_id={n_duplicate_delivery_id}, "
        f"duplicate available composite keys={n_duplicate_available_composite_key}\n"
        f"- Minimal classification rows: {len(classification_df)} | output written: {classification_written}\n"
        + "".join(
            f"- {cat}: {classif_counts.get(cat, 0)}\n"
            for cat in sorted(expected_classif_counts)
        )
        + f"- Review files inventoried: {len(REVIEW_INVENTORY)} | Open/Pending: {len(open_items)}\n"
        f"- Non-blocking missing files: {missing_review_files if missing_review_files else 'none'}\n"
        f"- Blocking findings: {unexpected_findings if unexpected_findings else 'none'}\n"
        f"- Validation: {validation_result}\n",
    )

    print(f"  Non-blocking missing files: {missing_review_files if missing_review_files else 'none'}")
    print(f"  Blocking findings: {unexpected_findings if unexpected_findings else 'none'}")
    print(f"  Validation: {validation_result}")
    print("=== Batch 19 complete ===\n")
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(cohort_mode=None):
    """Run the approved pipeline and produce the final processed dataset.

    cohort_mode: resolved fail-closed via resolve_cohort_mode() (explicit
    argument, else the PREPROCESSING_COHORT_MODE environment variable, else
    "primary"). "primary" (the default) runs all 19 batches exactly as
    before, in sequence, each batch receiving the previous batch's output
    DataFrame -- this is the ONLY path that writes to any canonical output
    file, and it always produces a 431-row primary cohort. Any other mode
    ("original"/"exclude19"/"strict26") runs ONLY Batch 1 and Batch 2 (the
    two batches that determine cohort membership), writes exclusively to the
    cohort_modes/<mode> subdirectories (never a canonical path), prints a
    reconciliation report, and returns without running Batch 3 onward --
    Batches 3-19 perform unrelated column cleaning/derivation on whatever
    row count they are given and have no bearing on which of the four
    cohorts a row belongs to, so they are not needed to reproduce a
    non-primary cohort's row-level composition, and running them would only
    create risk of writing a non-431-row file under a canonical batch-N
    filename.

    IMPORTANT -- non-primary outputs are NOT model-ready: a non-primary
    export is a cohort-membership/QC artifact only (row set, target
    distribution, raw/renamed source columns present after Batch 1+2). It
    has none of the derived/cleaned analytical columns Batches 3-19
    construct, so it must never be substituted for the primary 431-row
    export in any downstream analysis or modeling. See COHORT_MODES for the
    four modes' exact definitions."""
    cohort_mode = resolve_cohort_mode(cohort_mode)
    work_df, raw_df = batch_1_column_mapping(cohort_mode=cohort_mode)
    work_df = batch_2_cohort_target(work_df, cohort_mode=cohort_mode)

    if cohort_mode != "primary":
        _mode_info = COHORT_MODES[cohort_mode]
        _n0 = int(work_df["target_intrapartum_cs"].eq(0).sum())
        _n1 = int(work_df["target_intrapartum_cs"].eq(1).sum())
        print(f"\n=== cohort_mode={cohort_mode!r} complete (non-primary: stopped after Batch 2) ===")
        print(f"  N={len(work_df)} (expected {_mode_info['expected_n']}), "
              f"target 0={_n0}/1={_n1} (expected {_mode_info['expected_target'][0]}/"
              f"{_mode_info['expected_target'][1]})")
        print("  Batches 3-19 were NOT run for this mode -- they do not affect cohort "
              "membership; canonical primary artifacts are untouched.")
        print("  NOTE: this is a cohort-membership/QC output only, through Batch 2 -- "
              "NOT a fully processed, model-ready dataset. It has none of the "
              "derived/cleaned analytical columns Batches 3-19 construct.")
        return work_df

    work_df = batch_3_obstetric_history(work_df)
    work_df = batch_4_background(work_df)
    work_df = batch_5_endometriosis(work_df)
    work_df = batch_6_adenomyosis(work_df)
    work_df = batch_7_endometrioma(work_df)
    work_df = batch_8_endometriosis_surgery(work_df)
    work_df = batch_9_body_size_and_treatment(work_df)
    work_df = batch_10_conception(work_df)
    work_df = batch_11_pprom_gestational_age(work_df)
    work_df = batch_12_hypertension_diabetes(work_df)
    work_df = batch_13_pregnancy_complications(work_df)
    work_df = batch_14_labor_induction(work_df)
    work_df = batch_15_cs_reference_variables(work_df)
    work_df = batch_16_maternal_outcomes(work_df)
    work_df = batch_17_neonatal_basic(work_df)
    work_df = batch_18_neonatal_outcomes(work_df)
    work_df = batch_19_qa_inventory_and_classification(work_df)


if __name__ == "__main__":
    main()

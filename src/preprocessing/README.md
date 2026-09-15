# Preprocessing source — what is included, what was redacted, and why

This folder contains the raw-data preprocessing implementation: the
orchestrator, its supporting rule/config modules, and the reusable utility
module. See `REDACTION_NOTICE.md` in this folder for the precise privacy
scope, and `PREPROCESSING_DECISIONS_SUMMARY.md` for an examiner-facing
summary of the methodological outcomes without record-level detail.

## What is included

- **`run_preprocessing.py`** — the pipeline orchestrator (Batches 1-19) that
  converts the raw Sheba clinical workbook into the canonical
  `work_df_batch18.xlsx` (431 rows x 156 columns). Privacy-redacted: see
  below.
- **`src/preprocessing_config.py`** — column mapping and QA-correction
  reference. Privacy-redacted: literal record-specific identifiers and the
  patient-specific source excerpts used only to justify individual
  corrections have been removed or replaced with generic placeholders;
  protected small-cell counts are withheld per this project's disclosure
  policy. The general schema, thresholds, and correction *logic* are
  unchanged.
- **`src/clinical_decisions.py`** — the composite-key (`subject_number` +
  `delivery_id`) manual clinical decision tables and the validation/merge
  logic that applies them. Privacy-redacted: the literal record-level
  decision rows (real subject/delivery identifiers and their per-record
  clinical rationale) have been removed and replaced with empty,
  schema-only tables. The validation and application logic — including the
  hard-error behavior on duplicate or unmatched keys — is unchanged and
  fully intact.
- **`src/adenomyosis_rules.py`**, **`src/endometrioma_rules.py`** — the
  free-text/multi-code parsing rules for these two variable families.
  Unredacted: these contain only generic, deterministic parsing logic, not
  record-specific content (one previously-present comment describing a
  single record's raw-text wording was generalized to describe the rule
  category instead).
- **`src/preprocessing_utils.py`** — the full reusable utility module,
  unmodified. Every function in it is a generic, clinically neutral
  data-mechanics helper (missing-value normalization, binary coercion,
  multi-code text parsing, subgroup NA logic, deterministic QA-table
  construction, and a defense-in-depth Markdown sanitizer that actively
  strips patient identifiers, record-level value changes, and small-cell
  (n<5) breakdowns from any tracked audit text before it is written to
  disk). No function in this file contains a literal patient identifier, a
  literal clinical decision, or any record-specific value.

## What was redacted, and why

Two kinds of record-level content have been removed from the files above:

1. **Literal `subject_number` / `delivery_id` values** used as composite-key
   filters for individually reviewed records, together with the
   per-record clinical rationale text attached to them (e.g. a specific
   sonographic finding transcribed for one record's QA entry).
2. **Protected small-cell counts** — a small number of exclusion counts
   that this project's disclosure policy treats as protected and does not
   print as a literal, even in an examiner-facing summary.

The general algorithm, validation logic, thresholds, and schema are
retained in full — nothing about *how* the pipeline works was removed,
only the specific record identifiers and per-record adjudication text.

## Consequence for reproducibility

Because the record-level adjudication content is redacted, this public
copy is **not** an exact executable reproduction of the confidential
raw-data pipeline: re-running it against the raw workbook would not
reproduce the handful of individually-adjudicated records identically,
since the composite-key decision tables that would re-apply those specific
corrections are now empty. Everything else in the pipeline — cohort
construction, deterministic cleaning/recoding, feature construction, and
QA — is unchanged and traces exactly to what actually produced
`work_df_batch18.xlsx`. Full raw-to-final reproduction in any case also
requires the confidential source workbook, which is not part of this
repository (see the root `README.md`, reproducibility tier 5).

A few other builder scripts elsewhere in this repository
(`src/eda/notebook_build/`, `src/data_cleaning/notebook_build/`) reference
`preprocessing_config.py` at runtime (e.g. to import the approved cohort
row/target counts for a validation gate); that import now resolves, since
the file is present, but those scripts still cannot be independently rerun
end to end without the confidential source workbook.

### What "zero patient-level information" means here

No file anywhere in this repository — code, notebook source, notebook
output, results table, or documentation — contains a literal
patient/delivery identifier value, a composite subject+delivery key,
patient-specific free text, or a row-level model prediction. Aggregate
counts derived from such keys (e.g. "missing subject_number = 8") are
retained where they already appeared, since a count is not an identifier.

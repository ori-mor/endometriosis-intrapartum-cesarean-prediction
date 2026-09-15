"""Publication notebook — Part 1: intro, scientific framing, and Section A analysis contract."""
from publication_analysis.notebook_parts._cell_helpers import code, md

PART1_CELLS = [
    md(
        "pub-s00-header",
        """
# Publication / Inferential Analysis — Endometriosis & Intrapartum Cesarean Section
## Sheba Medical Center

---

## Scientific question

This notebook is the association / descriptive companion to the canonical
predictive modeling pipeline. It asks a different question than the
predictive pipeline does:

- **Predictive pipeline (elsewhere):** how well can `target_intrapartum_cs`
  be predicted out-of-sample from the available predictor pool?
- **This notebook:** which predictors — and in particular, which
  endometriosis-specific phenotype/surgical-history features — are
  **associated** with intrapartum cesarean delivery, in the whole cohort,
  described in clinically interpretable units, with and without adjustment
  for a small pre-specified conventional covariate set?

**This is not a causal analysis.** Throughout, results are described as
*association*, *adjusted association*, *predictive contribution*,
*incremental predictive value*, or *exploratory finding* — never as
*causes*, *effect of*, or *independent causal effect*.

**How the two halves of this notebook are computed, in one sentence each:**
the association/descriptive analyses (Sections A–G, I — Table 1, univariable
associations, BH-FDR, endometriosis-specific findings, adjusted associations,
research-signal evidence, figures) are **computed live, in this notebook**, every time
it is run end-to-end from a clean kernel against the real patient-level
cohort; the Compact Ridge predictive results (Section H) are **consumed
read-only** from already-persisted locked/final publication artifacts and are
never re-fit, tuned, or rerun here.

### Prediction vs. association — why both exist and why they can disagree
A predictor can be strongly *associated* with the outcome in a univariable
or adjusted regression while contributing little *incremental predictive
value* on top of everything else already in a multivariable model (because
it is redundant with other predictors) — and vice versa. Sections below keep
these two kinds of evidence in clearly separate tables and never substitute
one for the other.

### Strict separation from the predictive modeling pipeline
This notebook and its supporting code (`analysis/publication_analysis/`)
never import from, write to, or execute the predictive-modeling package or
its outputs. Where this notebook shows predictive-model context (Section H)
it is a **read-only consumer** of already-persisted result artifacts — it
never re-fits, tunes, or reruns the predictive model. The one exception is a
read-only, file-path load of the canonical subject-grouping helper for the
parity check at the end of Section A (that helper is never modified and no
model is run).
""",
    ),
    md(
        "pub-s00b-status-note",
        """
### Status note

All sections (A–I) implement, and are cross-checked for internal consistency
against, the current predictor pool, the locked `PRIMARY_ADJUSTMENT_SET` /
`SENSITIVITY_ADJUSTMENT_SET`, the single-source-of-truth univariable/BH-FDR
join used by every downstream section, and the current Compact Ridge
(Decision 99) predictive context.

Sections A–G — and the Section I figures generated from this notebook's own
live association analyses (the univariable and endometriosis-specific forest
plots) — are computed live from the real patient-level cohort each time the
notebook is run end-to-end from a clean kernel; nothing in those sections is
a cached or pre-computed number. Re-running the notebook is how a result
reported in Sections A–G/I is produced and reproduced; the fail-loud contract
checks in Section A below (and the runtime subject-grouping parity gate) halt
the run before any inferential section if the live cohort ever diverges from
what this notebook expects.

Section H is different by design: it consumes the already-accepted, locked
Compact Ridge, six-predictor adjusted-OR, and Firth-sensitivity artifacts
**read-only** and never refits, tunes, or reruns them (see Section H's own
header for the full read-only contract) — its performance-table/figure/
coefficient content is reproduced from the locked artifact files on disk each
run, not recomputed live in this notebook.

Section A (this part) is the canonical input contract: the analysis runs
exclusively on the 81-predictor EDA-C modeling matrix
(`outputs/eda_c/modeling_dataset_candidate_features.xlsx`), never the Data
Cleaning B dataframe. The subject-grouping key is checked **at runtime** (not
by a stored verdict) against the canonical predictive-pipeline implementation
— the parity cell in Section A raises and halts the notebook if they ever
diverge.
""",
    ),
    md(
        "pub-s01-header",
        """
---
## Section A — Analysis Contract

Two layers of validation, both **fail-loud**:

1. **Metadata contract** — canonical cohort / stage / endometriosis-family
   counts against the live variable-level manifests (no patient row read).
2. **Analytical-matrix contract** — the real 81-predictor matrix: N = 431,
   target 370 / 61 with no missing and values in {0, 1}, exactly 81
   predictor columns in the exact order of `candidate_model_features.csv`,
   no duplicate columns or registry names, and agreement with the manifest's
   `n_rows` / `n_events` / `n_eligible_pool`.

Row identity (for subject-cluster-robust SEs) is recovered separately through
the canonical row-alignment sidecar and `work_df_batch18.xlsx`.
""",
    ),
    code(
        "pub-s01-metadata-contract",
        """
from publication_analysis import publication_contract as contract

report = contract.validate_contract(strict=True)  # raises PublicationContractError on any mismatch

print(f"Eligible predictor pool: {report.n_eligible_pool}")
print(f"Cumulative stage sizes (1/2/3): {report.stage_cumulative}")
print(f"Target distribution (0/1): {report.target_0}/{report.target_1}")
print(f"Endometriosis-specific family size: {report.endometriosis_family_size}")
print(
    "Endometriosis family matches EDA-C domain-derived subset: "
    f"{report.endometriosis_family_matches_domain_subset}"
)
print(f"Data Cleaning B shape: {report.cleaning_b_n_rows} x {report.cleaning_b_n_cols}")
""",
    ),
    code(
        "pub-s01-analysis-matrix",
        """
from publication_analysis import analysis_matrix as amx

# Positionally align the analytical matrix to the validated 0..430 sidecar.
matrix_df, row_key_df = amx.load_aligned_analysis_inputs()

# Fail loud unless the real matrix matches the canonical 81-predictor contract.
matrix_report = amx.validate_analysis_matrix(matrix_df, strict=True)

predictor_names = amx.predictor_columns(matrix_df)   # 81 names, canonical order
df = matrix_df                                       # analytical matrix used by later sections

# Registry metadata reused by later sections (types / stage / family membership).
features_df = contract.load_candidate_features()
endo_family_names = contract.endometriosis_family_names()

print(
    f"Analytical matrix: {matrix_df.shape[0]} rows x {matrix_df.shape[1]} cols "
    f"(target + {matrix_report.n_predictors} predictors)"
)
print(f"Row-alignment sidecar rows: {len(row_key_df)}")
print(f"Target 0/1 in matrix: {matrix_report.target_0}/{matrix_report.target_1}")
print(f"Analytical-matrix contract OK: {matrix_report.ok}")
""",
    ),
    code(
        "pub-s01-subject-groups",
        """
from publication_analysis import subject_grouping

batch18_df = subject_grouping.load_batch18()
subject_groups = subject_grouping.build_subject_groups(matrix_df, row_key_df, batch18_df)
group_summary = subject_grouping.summarize_subject_groups(matrix_df, row_key_df, batch18_df)

print(f"rows: {group_summary.n_rows}")
print(f"unique subject clusters: {group_summary.n_unique_groups}")
print(f"rows without a linked subject id: {group_summary.n_rows_missing_subject_number}")
print(f"clusters with more than one delivery: {group_summary.n_repeated_subject_groups}")
print(f"rows in multi-delivery clusters: {group_summary.n_rows_in_repeated_subject_groups}")
print(f"max deliveries per subject: {group_summary.max_deliveries_per_subject}")
""",
    ),
    md(
        "pub-s01-parity-header",
        """
### Subject-grouping parity gate (runtime)

The cell below is the **authoritative** parity check. It re-runs, every time
this notebook executes, a read-only comparison of the publication grouping
against the canonical predictive-pipeline implementation
`analysis/modeling/final_modeling/subject_groups.py::load_group_labels`
(loaded by file path; that module is never modified and no model is run). It
**raises `SubjectGroupParityError` and halts the notebook** unless BOTH hold
for all 431 rows:

- (A) exact row-wise label equality (implementation-integrity check);
- (B) partition equivalence — same rows grouped together / apart (the
  requirement for subject-cluster-robust standard errors).

No dated/stored "PASS" is trusted. The same check is available on the command
line: `.venv312\\Scripts\\python.exe analysis/publication_analysis/verify_subject_group_parity.py`
""",
    ),
    code(
        "pub-s01-parity-gate",
        """
from publication_analysis.verify_subject_group_parity import (
    verify_live_subject_group_parity,
)

# RUNTIME GATE: raises SubjectGroupParityError (halting the notebook before any
# inferential section) unless exact row-label equality AND partition
# equivalence both hold for every row, checked live against the canonical
# final_modeling grouping.
parity_result = verify_live_subject_group_parity(strict=True)

print(f"rows compared:                {parity_result.n_rows}")
print(f"(A) exact row-label equality: {parity_result.row_label_equal}")
print(f"(B) partition equivalence:    {parity_result.partition_equivalent}")
print("subject-group parity gate: PASS")
""",
    ),
]

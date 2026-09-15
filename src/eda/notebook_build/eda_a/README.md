# EDA A1 — Initial Cohort and Variable Inventory Overview (Section 1)

> **Canonical-repository README — read in submission context.** This file
> was copied from the private canonical research repository. Internal paths
> (including the canonical `notebooks/eda/02_...`/`02b_...`/`03_...`/`04_...`
> naming below — this submission's own notebooks are flatter, e.g.
> `notebooks/01_cohort_overview.ipynb`, see the root `README.md`) and the
> Git commit policy below describe *that* repository, not this curated
> submission. This submission intentionally tracks a different,
> narrower set of files — approved *executed* notebooks and privacy-safe
> aggregate `.csv`/`.xlsx` artifacts alongside source, most of which the
> canonical policy below would gitignore. Submission-specific
> inclusion/exclusion and Git policy is defined by the root `README.md` and
> `SUBMISSION_MANIFEST.md`, not by the paths or commit/gitignore rules below.

**Purpose:** All-variables overview of the full processed dataset.
Not an analytical EDA — no statistical association tests.
Answers: "What do we have, and how is it classified?"

**Scope:** Full `df` (all columns, not just approved predictors).

**Workflow position (data-science methodology):**
- **This notebook — A1 (Section 1, `02_eda_a_initial_cohort_overview.ipynb`):**
  Inventory and basic descriptives — all variable groups.
- **A2 (Section 1, `02b_eda_a_initial_predictor_readiness.ipynb`):** Deep
  predictor-readiness EDA for the pre-delivery candidate set (builder folder `a2_predictor_readiness/`, renamed 2026-08-24 from `eda_b/`).
- **B (Section 2, `notebooks/eda/03_data_cleaning_b_after_initial_eda.ipynb`):**
  Data cleaning → cleaned dataset.
- **C (Sections 3–5, `04_eda_c_modeling_handoff.ipynb`):** Repeated EDA + feature
  engineering + screening + modeling handoff on the cleaned dataset.

**Data-dependency clarification (added 2026-08-16):** the table above is a
*chronological/methodological reading order*, not a strict data-flow chain.
A1 and A2 both read `work_df_batch18.xlsx` (this stage's own preprocessing
output) directly and independently — neither depends on the other's output.
Data Cleaning B (Stage B) also reads `work_df_batch18.xlsx` directly; it is a
second, independent consumer, not a stage that consumes A2's output. Only
EDA C depends on Data Cleaning B's output. The true dependency graph is:
`Preprocessing → work_df_batch18.xlsx → {A1, A2, Data Cleaning B}` (three
parallel consumers), then `Data Cleaning B → EDA C`.

**Does not perform:**
- Statistical association tests
- Outlier analysis
- Redundancy/correlation analysis
- Feature selection or scoring
- Any data modification

---

## Files

| File | Role |
|------|------|
| `eda_a_part1_setup_cohort.py` | Sections A0–A4: setup, load, validation, variable inventory, cohort definition & target distribution |
| `eda_a_part2_summaries.py` | Sections A5–A10: predictor pool & exclusion rationale, descriptive overview (Table 1), missingness overview, outlier screening, findings registry, summary/handoff (reordered 2026-08-08 — see the file's own docstring for the old→new section map) |
| `build_eda_a_notebook.py` | Assembles the A1 notebook from the part files above |

## Generated notebook
`notebooks/eda/02_eda_a_initial_cohort_overview.ipynb` (gitignored)

## Commit policy
Commit `.py` and `.md` files. Never commit `.ipynb`, `.xlsx`, `.csv`.

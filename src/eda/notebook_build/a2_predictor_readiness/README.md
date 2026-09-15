# EDA A2 — Initial Predictor-Readiness EDA (Section 1)

> **Canonical-repository README — read in submission context.** This file
> was copied from the private canonical research repository. Internal paths
> (including the canonical `notebooks/eda/02_...`/`02b_...`/`03_...`/`04_...`
> naming below — this submission's own notebooks are flatter, e.g.
> `notebooks/02_predictor_readiness.ipynb`, see the root `README.md`) and
> the Git commit policy below describe *that* repository, not this curated
> submission. This submission intentionally tracks a different,
> narrower set of files — approved *executed* notebooks and privacy-safe
> aggregate `.csv`/`.xlsx` artifacts alongside source, most of which the
> canonical policy below would gitignore. Submission-specific
> inclusion/exclusion and Git policy is defined by the root `README.md` and
> `SUBMISSION_MANIFEST.md`, not by the paths or commit/gitignore rules below.

> ## ⚠ A2 INITIAL PREDICTOR-READINESS — NOT DATA CLEANING B
> This folder builds **A2** (`notebooks/eda/02b_eda_a_initial_predictor_readiness.ipynb`),
> the second initial-EDA notebook, run after A1 (cohort overview). It performs
> **NO data cleaning**. This folder was renamed from `eda_b` to
> `a2_predictor_readiness` on 2026-08-24, once the A2 freeze gate passed, to
> stop inviting exactly this confusion. Internal `EDA_B_*`/`SB*` Python symbol
> names and `eda-b-*` cell IDs are **deliberately kept unchanged, for
> path/execution stability only** — they do not mean "Data Cleaning B."
> The actual methodological **Data Cleaning B (Section 2)** is a completely
> separate folder and notebook:
> `analysis/data_cleaning/notebook_build/data_cleaning_b/`
> → `notebooks/eda/03_data_cleaning_b_after_initial_eda.ipynb`

**Purpose:** Rigorous, structured initial EDA on the pre-delivery candidate predictors
for the primary intrapartum-CS prediction model. Diagnostics only — no data is modified.

**Primary scope:** the cumulative Stage 1+2+3 candidate universe (`PRIMARY_COLS`) —
Stage 1 (pre-labor), Stage 2 (near-delivery), and Stage 3 (intrapartum) predictors
together, after target-independent zero-variance removal. Every predictor in this
universe receives the same main diagnostic coverage (distribution, association,
missingness, readiness tables/plots); `earliest_entry_stage` is tracked and shown
per variable throughout, but does not gate which sections cover it. This is
readiness/descriptive coverage only — it is not a claim that Stage 2/3 variables
are usable in an earlier-stage (pre-labor) model; horizon-specific modeling
eligibility is decided downstream, at the modeling boundary.

**Zero-variance policy:** Constant status may be audited across all variables,
but automatic `zero_variance` exclusion applies only within the analytical
predictor scope. A true zero-variance exclusion requires no missing values and
exactly one observed unique value; all-missing and partially missing single-value
variables remain missingness issues, and cohort-control variables retain their
original role.

**Workflow position (data-science methodology):**

| Stage | Notebook | Role |
|-------|----------|------|
| A1 (Section 1) | `notebooks/eda/02_eda_a_initial_cohort_overview.ipynb` | Full-dataset inventory & cohort overview (run first) |
| **A2 (Section 1)** | **`notebooks/eda/02b_eda_a_initial_predictor_readiness.ipynb`** | **This notebook — predictor-readiness EDA** |
| B (Section 2) | `notebooks/eda/03_data_cleaning_b_after_initial_eda.ipynb` | Data cleaning → cleaned dataset |
| C (Sections 3–5) | `notebooks/eda/04_eda_c_modeling_handoff.ipynb` | Repeated EDA + feature engineering + screening + handoff |

**Data-dependency clarification (added 2026-08-16):** the table above is a
*chronological/methodological reading order*, not a strict data-flow chain.
This notebook (A2/EDA A2) reads `work_df_batch18.xlsx` — the preprocessing
output — directly (see `a2_part1_setup_scope.py`'s data-load cell). It
does **not** read Data Cleaning B's cleaned output, and Data Cleaning B does
**not** depend on this notebook running first or on any of its outputs. Both
are independent, parallel consumers of `work_df_batch18.xlsx`. Only EDA C
depends on Data Cleaning B's output.

**Does not perform:**
- Data modification or imputation
- Model training
- Final feature selection (plans and rankings only)

---

## Files

**Note (2026-08-08 reorg):** the notebook's displayed section order is now
methodological (A2.0–A2.15 as listed below), which no longer matches file-name order.
`build_a2_notebook.py`'s `PART_FILES` list controls assembly order
(`part1, part3, part2, part4, part5`); each file's own cell-ID prefixes (e.g.
`eda-b-s06-*` in `a2_part3_distributions.py`) still reflect the pre-reorg
numbering for execution stability — only the markdown section numbers shown to
the reader changed. See each file's own docstring for its old→new section map.

| File | Role |
|------|------|
| `a2_part1_setup_scope.py` | A2.0–A2.2: setup, config, scope definition, df_primary build |
| `a2_part2_missingness.py` | A2.7–A2.8 (displayed): missingness deep-dive, sparsity/separation |
| `a2_part3_distributions.py` | A2.3–A2.6 (displayed): numeric distributions, binary/categorical distributions, domain EDA |
| `a2_part4_associations.py` | A2.9–A2.11 (displayed): association+FDR, predictor-predictor relationships & redundancy (A2.10a–d), outlier screening |
| `a2_part5_readiness.py` | A2.12–A2.15 (displayed): comprehensive predictor screening summary (relocated from part2), variable-readiness scoring, clinical decision registry, action log |
| `build_a2_notebook.py` | Assembles the A2 notebook |

## Generated notebook
`notebooks/eda/02b_eda_a_initial_predictor_readiness.ipynb` (gitignored)

## Commit policy
Commit `.py` and `.md` files. Never commit `.ipynb`, `.xlsx`, `.csv`.

## Important notes for the data-cleaning B and EDA C
- The clinical decision registry (Section A2.14) feeds both the data-cleaning B
  scope decisions and EDA C. As of the current A2 source, all clinical-review
  registry entries are resolved and there are zero blocking timing variables
  (`TIMING_OPEN_VARS` is empty) -- do not treat any specific resolved/open count
  as fixed here; `docs/clinical_decisions/manual_decisions_log.md` is the
  canonical, currently-authoritative source for decision status.
- Before running EDA C: data cleaning B must produce the cleaned dataset.
  **Stale note, corrected:** an earlier version of this file described a
  `FINAL_CORE_VARS` manual candidate-pool override as an optional EDA C
  Section C1 setting. That override was **retired on 2026-08-31** — there is
  no manual override any more. `ANALYSIS_VARS` is now always built
  automatically from the authoritative Data Cleaning B classification
  metadata (the unified Stage 1/2/3 master candidate universe —
  `predictor_allowed` + `secondary_near_delivery_predictor` +
  `intrapartum_predictor_exclude_from_prelabor_model`, plus approved Data
  Cleaning B-created replacement variables — not just the `predictor_allowed`
  pool alone). See `src/eda/notebook_build/eda_c/README.md`'s "No manual
  candidate-pool override" note for the current, authoritative description.
- Clinical decisions must be recorded in `docs/clinical_decisions/manual_decisions_log.md`.

# SUBMISSION_MANIFEST

A concise map of this package. See the root `README.md` for the full
scientific summary and reproducibility tiers; this file is navigation only.

## Canonical source

Curated from the canonical research repository at commit
`e7676be3167c706950ce1a564fc454223f0d265d` (tag `final-project-2026`) — the
canonical scientific freeze/base.

One later **visual-only** canonical patch is also included:
`ea9280011ae6fabeacc67852ec104f23ad44e61b` (`fix: improve adjusted OR
forest plot tick labels`) — adjusted-OR forest-plot tick-label rendering
only. No scientific value, coefficient, cohort, predictor, preprocessing
step, model, metric, p-value, or conclusion is changed by it. The
adjusted-OR PNG/SVG under
`results/figures/compact_ridge_final/adjusted_or/` are the post-patch
versions (byte-identical to canonical `ea92800`).

**This submission's Git history (once initialized) is independent of the
canonical research repository's Git history.** It is a fresh, standalone
history for this curated package — not a clone, fork, filtered branch, or
subtree of the canonical repository's history. The canonical repository
itself is not modified by, and does not depend on, this submission.

## Major included sections

| Section | Contents |
|---|---|
| `notebooks/` | The six executed notebooks (reading order below). |
| `src/` | Curated source: preprocessing (including the privacy-redacted orchestrator and supporting modules — see `src/preprocessing/README.md`), EDA/data-cleaning notebook builders, the final Compact Ridge modeling source, the notebook-05 builder, and the publication-analysis pipeline. |
| `results/` | All current, aggregate-only tables/figures — final-model results, reproducibility detail, publication-analysis output, and modeling-handoff/Data-Cleaning-B supporting artifacts (see below). |
| `documentation/` | Current scientific-facts summaries, the model-lock decision record, the clinical variable dictionary, the environment specification, and a figure/table index — see `documentation/README.md` for current-vs-reference navigation. |
| `data/` | No patient-level data (see `data/README.md`). |
| `requirements.txt` | Submission-wide dependency specification. |

## Notebook reading order

| # | Notebook | Covers |
|---|---|---|
| 1 | `notebooks/01_cohort_overview.ipynb` | Full-dataset inventory and cohort overview |
| 2 | `notebooks/02_predictor_readiness.ipynb` | Predictor-readiness diagnostics (distributions, missingness, associations) |
| 3 | `notebooks/03_data_cleaning.ipynb` | Data cleaning and construction of the cleaned analytical dataset |
| 4 | `notebooks/04_modeling_handoff.ipynb` | Feature engineering, screening, and the candidate-predictor handoff to modeling |
| 5 | `notebooks/05_final_compact_ridge_model.ipynb` | The locked final model: performance, coefficients, adjusted odds ratios, calibration — the one notebook in this package that is genuinely rerunnable from included aggregate outputs alone |
| 6 | `notebooks/06_publication_statistical_analysis.ipynb` | Descriptive Table 1, univariable Table 2, FDR-corrected associations, endometriosis-specific findings |

## Current final-model result locations

- `results/tables/compact_ridge_final/`, `results/figures/compact_ridge_final/` — locked Compact Ridge (Decision 99) performance, coefficients, adjusted odds ratios, calibration.
- `results/tables/reproducibility/` — repeat/fold-level detail behind those results (manifests, per-fold metrics, coefficient stability).
- `documentation/COMPACT_RIDGE_FINAL_LOCK.md` — the scientific lock record.

## Supporting modeling-handoff / data-cleaning result locations

Added beyond what appeared in the original project book, because they are
current, variable-level-only, and privacy-safe:

- `results/tables/modeling_handoff/`, `results/figures/modeling_handoff/` — EDA-C candidate-feature screening/handoff registry and domain distribution figures.
- `results/tables/data_cleaning_b_audit/` — Data Cleaning B variable-level cleaning/imputation/outlier audit.
- `results/tables/publication_analysis/`, `results/figures/publication_analysis/` — descriptive and univariable statistical analysis.

See `documentation/FIGURE_TABLE_INDEX.md` for the complete, itemized index
of every table and figure above.

## Major deliberate exclusions, and why

| Excluded | Why |
|---|---|
| Any raw or processed patient-level dataset (`.xlsx`/`.csv` with one row per patient/delivery) | The source clinical data is governed by Sheba Medical Center's data-sharing agreement and is never committed to any Git repository, canonical or submission. See `data/README.md`. |
Literal record-level content in the preprocessing source | `src/preprocessing/run_preprocessing.py`, `src/preprocessing/src/preprocessing_config.py`, and `src/preprocessing/src/clinical_decisions.py` are included, but with literal `subject_number`/`delivery_id` composite-key filters, patient-specific free-text clinical excerpts, and protected small-cell counts redacted. The general algorithm, validation logic, and schema are retained in full. See `src/preprocessing/README.md` and `src/preprocessing/REDACTION_NOTICE.md`. |
| `locked_validation_oof_predictions.csv` | Row-level out-of-fold model predictions (one row per delivery per CV repeat). |
| The EDA-C patient-level modeling-matrix `.xlsx` files and their row/delivery-id key sidecars | One row per patient; only the variable-level screening/handoff registry derived from them is included. |
| The Data Cleaning B patient-level row-actions file and its delivery-id key sidecar | Same reason — only the variable-level audit artifacts derived from them are included. |
| The historical Stage 3/LASSO Tables A–I / Figures 1–10 submission layer | Superseded architecture; retained in full only in `documentation/reference/FIGURE_TABLE_INDEX_CANONICAL.md` for provenance. |

## Privacy statement

No file in this submission — code, notebook source, notebook output,
results table, or documentation — contains a literal patient/delivery
identifier value, a composite subject+delivery key, patient-specific free
text, a row-level model prediction, or a personal filesystem path/username.
This includes the preprocessing source under `src/preprocessing/`: literal
record-specific keys and patient-specific adjudication excerpts have been
removed from it (see `src/preprocessing/REDACTION_NOTICE.md`). Generic
schema column names such as `subject_number` and `delivery_id` remain
throughout, since they describe the data structure rather than identify a
record. Aggregate counts derived from such keys (e.g. "missing
subject_number = 8") are retained where they already appeared, since a
count is not an identifier.

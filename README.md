# Endometriosis & Intrapartum Cesarean Section — Final Submission

See `SUBMISSION_MANIFEST.md` for a concise navigation map of this package
(included sections, notebook reading order, result locations, and
deliberate exclusions with reasons).

## Purpose

This package presents the final analysis of whether the risk of
intrapartum cesarean section, following a trial of vaginal labor, can be
predicted from endometriosis characteristics, obstetric risk factors, and
pregnancy/delivery data.

## Research question

Can we predict the risk of intrapartum cesarean section after trial of
vaginal labor, based on endometriosis characteristics, obstetric risk
factors, and pregnancy/delivery data?

## Cohort (high level)

- 431 deliveries at Sheba Medical Center, restricted to trial-of-vaginal-labor
  cases (elective cesarean sections and non-trial-of-labor deliveries
  excluded upstream).
- Singleton pregnancies only — the dataset received from the data provider
  was already restricted to singletons before this analysis began.
- Target variable: intrapartum cesarean section during trial of labor
  (370 vaginal deliveries, 61 intrapartum cesarean sections).

## Final modeling approach

**Locked, current final model: Compact Ridge (L2-penalized) logistic
regression** on 6 predictors — `AGE`, `nulliparity`, `S_P_CS` (prior
cesarean section), `BMI_before` (pre-pregnancy BMI), a hypertensive-disorder
spectrum variable, and induction of labor. No endometriosis-specific
predictor is included: a completed exploratory analysis (summarized in
`documentation/COMPACT_RIDGE_FINAL_LOCK.md`) found no stable incremental
predictive value from any measured endometriosis phenotype, severity, or
surgical-history variable beyond this obstetric core. That negative result
is retained as a scientific finding, not overridden.

Reported performance (internal repeated subject-grouped 10×5
cross-validation, evaluated after model development — not an independent
test set or external validation):

| Metric | Compact Ridge (current, final) |
|---|---|
| PR-AUC | 0.348 (SD 0.015) |
| AUROC | 0.798 (SD 0.011) |
| Brier score | 0.106 (SD 0.001) |

Full detail, including the superseded-model comparison, is in
`results/tables/compact_ridge_final/table_final_model_performance.md`.

## Notebooks and reading order

All six notebooks are supplied **already executed**, with their outputs
(tables, statistics, figures) embedded — they can be opened and read in
Jupyter, nbviewer, or any `.ipynb`-capable tool without running any code or
having access to the underlying clinical data.

| # | Notebook | Covers |
|---|---|---|
| 1 | `notebooks/01_cohort_overview.ipynb` | Full-dataset inventory and cohort overview |
| 2 | `notebooks/02_predictor_readiness.ipynb` | Predictor-readiness diagnostics (distributions, missingness, associations) |
| 3 | `notebooks/03_data_cleaning.ipynb` | Data cleaning and construction of the cleaned analytical dataset |
| 4 | `notebooks/04_modeling_handoff.ipynb` | Feature engineering, screening, and the candidate-predictor handoff to modeling |
| 5 | `notebooks/05_final_compact_ridge_model.ipynb` | The locked final model: performance, coefficients, adjusted odds ratios, calibration |
| 6 | `notebooks/06_publication_statistical_analysis.ipynb` | Descriptive Table 1, univariable Table 2, FDR-corrected associations, endometriosis-specific findings |

(Notebooks 1–4 correspond to earlier pipeline stages named `02`, `02b`, `03`,
and `04` respectively in the source repository; a small number of embedded
cross-references between them use those original names.)

## Package contents

| Folder | Contents |
|---|---|
| `notebooks/` | The six executed notebooks above. |
| `src/` | Curated source code for the workflow shown in the notebooks: preprocessing (including the privacy-redacted orchestrator and its supporting modules — see `src/preprocessing/README.md`), EDA/data-cleaning notebook builders, the locked Compact Ridge model implementation, and the publication-analysis pipeline. This is a curated subset of the full research codebase, reorganized for readability — not a verbatim copy of the original repository layout. |
| `results/figures/`, `results/tables/` | All current, aggregate-only figures and tables: the final model's performance, coefficients, and calibration; the adjusted odds-ratio secondary analysis; and the full publication-analysis output set (descriptive Table 1, univariable Table 2, appendix tables, forest plots, functional-form diagnostics). Nothing here is superseded or patient-level. |
| `documentation/` | Current scientific-facts summaries (methods, results, limitations, figure/table index), the Compact Ridge model-lock decision record, the clinical variable dictionary, and the pinned Python environment for the most sensitive pipeline stage (Data Cleaning B). |
| `data/` | No patient-level data. See `data/README.md`. |

## Privacy-redacted preprocessing implementation

This repository includes the raw-data preprocessing implementation under
`src/preprocessing/` — the orchestrator (`run_preprocessing.py`) and its
supporting rule/config modules, in privacy-redacted form:

- No patient-level datasets are included anywhere in this repository.
- Literal `subject_number`/`delivery_id` record identifiers and the
  per-record clinical adjudication text tied to them have been redacted
  from the preprocessing source.
- The preprocessing source is provided for methodological and code
  inspection — to let a reader see exactly how the raw clinical workbook is
  turned into the analytical dataset.
- Because the record-specific adjudications were redacted, this public
  preprocessing copy is **not** an exact executable reproduction of the
  confidential raw-data pipeline.

See `src/preprocessing/README.md` for the file-by-file scope of what was
redacted, `src/preprocessing/REDACTION_NOTICE.md` for the privacy summary,
and `src/preprocessing/PREPROCESSING_DECISIONS_SUMMARY.md` for an
examiner-facing description of the preprocessing outcomes without
record-level detail.

## What is and isn't reproducible from this package

Reproducibility is not one claim — it is five tiers, each requiring
progressively more than what is included here. Do not assume a tier below
the one you need just because a tier above it works.

1. **Readable from included executed notebooks and frozen aggregate
   outputs (no code execution needed).** All six notebooks are supplied
   already executed, with every statistic, table, and figure baked into
   the notebook itself, alongside the same aggregate tables/figures under
   `results/`. This is the primary, always-available way to review the
   analysis, and requires nothing beyond a notebook viewer.
2. **Notebook 05 is genuinely rerunnable from the included aggregate
   outputs.** `notebooks/05_final_compact_ridge_model.ipynb` reads only
   already-frozen files under `results/tables/reproducibility/`,
   `results/tables/compact_ridge_final/`, and
   `results/figures/compact_ridge_final/`. It can be regenerated from its
   builder (`src/notebook_build/final_compact_ridge_presentation/`) and
   re-executed end to end with zero model fitting, zero new
   cross-validation, zero OOF data, zero hold-out access, and zero
   patient-level input — see that folder's module docstrings. This is the
   one notebook in this package independently verified rerunnable from the
   curated package alone.
3. **Full regeneration of the final model's own figures/tables and any
   new model validation is NOT possible from this package.** The
   generator behind those artifacts, `src/reports/compact_ridge_final_outputs.py`,
   requires `locked_validation_manifest.json`'s companion row-level file
   (`locked_validation_oof_predictions.csv`), which is deliberately excluded
   from this package because it contains row-level out-of-fold predictions.
   Notebook 05 (tier 2) displays the *already-generated* results of this
   generator; it does not, and cannot, rerun it.
4. **Full publication-analysis regeneration is NOT possible from this
   package.** `notebooks/06_publication_statistical_analysis.ipynb`'s
   `src/publication_analysis/` pipeline requires the patient-level EDA-C
   modeling matrix as input, which is deliberately excluded. Independently
   of that, the notebook's own executed source cells import their helper
   modules via the canonical repository's package path
   (`analysis.publication_analysis...`), not this repository's
   `src/publication_analysis` layout — the included `src/` copy is
   provided for source-code transparency and provenance, not as a
   drop-in-and-run package for this notebook.
5. **Full raw-data pipeline reproduction is NOT possible from this
   package.** Preprocessing, data cleaning, EDA, and model
   training/cross-validation from scratch require the original
   confidential clinical workbook from Sheba Medical Center (see
   `data/README.md`), which is never included. The preprocessing
   orchestrator source is now included in privacy-redacted form (see
   `src/preprocessing/README.md`), but the redacted composite-key decision
   tables cannot exactly reproduce the handful of individually-adjudicated
   records even if the raw workbook were supplied. Notebooks 1–4 assume
   the raw dataset is present; without it, they remain fully readable
   (tier 1) but cannot be re-executed.

## Environment

Root **`requirements.txt`** is the submission-wide dependency spec: every
direct third-party import found across all included `src/` files and all
six notebooks, pinned to versions verified against the actual final project
virtual environment (Python 3.12.10). It supersedes nothing — the
stage-specific `documentation/environment/data-cleaning-b-py31210-lock.txt`
(`data-cleaning-b.in` for direct requirements) remains as-is, as a fully
resolved provenance lock for Data Cleaning B specifically. `requirements.txt`
itself documents one verified discrepancy between that stage lock's pinned
versions and the environment actually used, rather than silently picking
one.

## Provenance

Curated from the canonical research repository at commit
`e7676be3167c706950ce1a564fc454223f0d265d` (tag `final-project-2026`) — the
canonical **scientific freeze/base** for this package. That repository is
the authoritative, version-controlled source of the full research history;
this package is a supervisor-facing extract of its current, non-superseded,
privacy-safe scientific content.

One later **visual-only** canonical patch is also incorporated:
`ea9280011ae6fabeacc67852ec104f23ad44e61b` (*"fix: improve adjusted OR
forest plot tick labels"*). It changes only the tick-label rendering of the
adjusted odds-ratio forest plot. It does **not** change any scientific
value, coefficient, cohort, predictor set, preprocessing step, model logic,
metric, p-value, conclusion, or interpretation. The
`results/figures/compact_ridge_final/adjusted_or/figure_adjusted_odds_ratios.{png,svg}`
files in this package are the post-patch versions (byte-identical to
canonical `ea92800`); all other content remains that of the `e7676be`
scientific freeze.

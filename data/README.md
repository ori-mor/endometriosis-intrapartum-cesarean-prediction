# data/

**No patient-level clinical data are included in this submission package.**
This directory is intentionally empty except for this file. No synthetic,
example, or placeholder patient data have been created to make the package
appear runnable — none exists here, by design.

## Why

The source dataset is private clinical research data from Sheba Medical
Center, governed by the institution's data-sharing agreement. It is
excluded from this package for privacy and data-governance reasons, and is
never committed to any Git repository (canonical or submission).

## What the original pipeline expects

The canonical preprocessing pipeline expects a single clinical workbook
(`.xlsx`), one row per delivery, with columns corresponding to the
variables described in `../documentation/clinical_variable_dictionary.yaml`.
That workbook is not part of this repository. The pipeline's orchestrator
source (`run_preprocessing.py`) is included, in privacy-redacted form, under
`../src/preprocessing/` — see `../src/preprocessing/README.md` for exactly
what was redacted and why. The redacted copy does not include, and cannot
regenerate, any patient-level data; it exists for methodological and
code inspection only.

## You do not need this data to review the analysis

The six notebooks under `../notebooks/` are supplied **already executed**,
with every statistic, table, and figure embedded in the notebook itself.
They can be opened and read in full — including the final model's
performance, coefficients, and the publication statistical analysis —
without access to the underlying clinical data. The complete aggregate
results are also available directly under `../results/`.

## What does require this data

Re-running the pipeline from raw data — preprocessing, data cleaning, the
exploratory analyses, and the model training/cross-validation itself —
requires the original workbook and is restricted to researchers with
authorized access under the relevant data-use agreement. No file needs to
be placed in this `data/` folder for any other part of this package to be
reviewed.

# Clinical Variable Dictionary — What's in this submission

This note explains `clinical_variable_dictionary.yaml` (in this same
folder) for a reader of this submission package. For the full canonical-
repository documentation of this file (which references internal paths,
policies, and decision logs that don't exist in this package), see
`documentation/reference/DATA_DICTIONARY_README_CANONICAL.md`.

## What the file contains

`clinical_variable_dictionary.yaml` documents the **128 original source
variables** as they arrive in the raw clinical workbook from Sheba Medical
Center, before any preprocessing. For each variable it records:

- `name` — the standardized variable name used throughout this project,
- `description_he` — the clinical meaning, in Hebrew (the source
  documentation's own language),
- `codes_he` — the Hebrew code/category mapping for categorical variables
  (`null` where the source workbook had no code list for that variable).

It contains **metadata and semantics only** — variable names, descriptions,
and code meanings. It does not, and has never, contained any patient value,
row, or identifier. It is generated programmatically from a local
authoring workbook (not itself part of this submission, and never
committed to any Git repository, canonical or submission) so that the
generation is reproducible and auditable, not hand-transcribed.

## What it does not cover

The processed/analytical dataset has many more columns than these 128 —
preprocessing, data cleaning, and feature engineering create additional
derived, cleaned, categorical, and engineered variables (for example
`derived_hypertension_pih_pet_spectrum`, `endometrioma_size_status`,
`BMI_before`). This dictionary does not enumerate those derived variables;
their definitions live instead in:

- the six notebooks in this submission (each derived variable is
  introduced and explained where it is first constructed or used), and
- `results/tables/modeling_handoff/feature_dictionary.csv` and
  `results/tables/data_cleaning_b_audit/cleaning_b_feature_dictionary.csv`
  (technical construction detail for the derived/engineered feature set).

This dictionary is also not the source for modeling-eligibility decisions
(which variables are usable as predictors, and in which modeling stage) —
that is documented in
`results/tables/modeling_handoff/candidate_model_features.csv` and
`results/tables/modeling_handoff/excluded_features_log.csv`.

## Row-level manual corrections are not part of this file, or this submission

A small number of individual data-entry corrections were applied during
preprocessing (e.g. recoding one out-of-range value in a binary field).
Those are **record-level clinical decisions**, distinct from this
dictionary's variable-level semantics, and are intentionally not part of
this submission for privacy reasons — see `src/preprocessing/README.md`
for why, and what is included in its place.

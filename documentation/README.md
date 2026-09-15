# documentation/ — what's current vs. retained reference

This folder mixes two kinds of document. This file exists so a reader can
tell them apart at a glance.

## Current — describes this submission / the current Compact Ridge model

| Document | What it's for |
|---|---|
| `COMPACT_RIDGE_FINAL_LOCK.md` | The scientific lock record for the current final model (Decision 99): frozen architecture, locked performance, full-refit coefficients. The primary scientific-facts source for the current model. |
| `RESULTS_FACTS.md` | Exact current final numbers (model performance, coefficients, publication-analysis results) — a fact-checking reference, not prose. |
| `METHODS_FACTS.md` | Exact current methods facts (cohort definition, CV design, predictor set) — a fact-checking reference. |
| `LIMITATIONS_FACTS.md` | Exact current limitations facts — a fact-checking reference. |
| `FIGURE_TABLE_INDEX.md` | Index of every figure/table actually included in this submission's `results/`, organized by result group. |
| `DATA_DICTIONARY_README.md` | Supervisor-facing explanation of `clinical_variable_dictionary.yaml` (this submission's variable-metadata reference) and what it does/doesn't cover. |
| `clinical_variable_dictionary.yaml` | The 128-source-variable metadata/semantics dictionary itself. |
| `requirements.txt` (submission root, one level up from `documentation/`) | This submission's full dependency specification. |
| `environment/data-cleaning-b.in`, `environment/data-cleaning-b-py31210-lock.txt` | Stage-specific dependency lock for the Data Cleaning B pipeline stage — narrower than the root `requirements.txt`, kept for provenance. |
| `environment/ENVIRONMENT_FREEZE.md` | Canonical-repository environment snapshot (Python version, key package versions), verified current and consistent with the actual environment used — but see its own provenance note for one disclosed inconsistency with the co-located Data-Cleaning-B lock file's pinned versions. |

`RESULTS_FACTS.md`, `METHODS_FACTS.md`, and `LIMITATIONS_FACTS.md` each
carry a provenance banner marking them as copied verbatim from the
canonical repository — that's expected; they are still the **current**
scientific-facts record, not historical material, and any internal path
they mention refers to the canonical repository rather than this package.

## Retained reference — historical / canonical-repository-internal context

| Document | Why it's kept, and why it's not primary |
|---|---|
| `reference/FIGURE_TABLE_INDEX_CANONICAL.md` | The full canonical-repository figure/table index, including the historical Stage 3/LASSO Tables A–I / Figures 1–10 layer (superseded architecture, largely not included in this submission). Kept for provenance; superseded as the submission's own index by `FIGURE_TABLE_INDEX.md`. |
| `reference/DATA_DICTIONARY_README_CANONICAL.md` | The full canonical-repository documentation of the variable dictionary, written for collaborators inside that repository (references internal paths/policies not present here). Kept for provenance; superseded as the submission's own explanation by `DATA_DICTIONARY_README.md`. |

## Where else to look

- `SUBMISSION_MANIFEST.md` (submission root) — the top-level map of this
  entire package, including deliberate exclusions and why.
- `src/preprocessing/README.md` — explains what preprocessing source is
  and isn't included, and why (the privacy-motivated exclusion of the
  record-level orchestrator).
- `data/README.md` — explains why no patient-level data is included and
  what that means for reproducibility.

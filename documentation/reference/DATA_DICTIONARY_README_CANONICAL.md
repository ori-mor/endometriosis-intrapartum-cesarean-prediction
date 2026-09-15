# Clinical Variable Dictionary — Scope and Precedence

> **HISTORICAL / CANONICAL-REFERENCE.** This is the full canonical-repository
> documentation for `clinical_variable_dictionary.yaml`, written for
> collaborators working inside that repository. It references internal
> paths (`docs/...`, `analysis/...`, `CLAUDE.md`, `manual_decisions_log.md`)
> that do not exist in this curated submission, and describes canonical-
> repository policy (commit guards, local authoring files) not relevant
> here. Retained for provenance only. **For a concise, supervisor-facing
> explanation of the dictionary as included in this submission, see
> `documentation/DATA_DICTIONARY_README.md`.**
>
> **Provenance note (submission package):** copied verbatim, without
> content changes, from the canonical research repository at commit
> `e7676be3167c706950ce1a564fc454223f0d265d` (tag `final-project-2026`).

## Canonical version-controlled source of truth

**`docs/data_dictionary/clinical_variable_dictionary.yaml`** — this is the
canonical, version-controlled file. It is generated programmatically (not
retyped by hand) from the local `.xlsx` workbook described below, and is
committed to the repository so every collaborator receives the same
dictionary on clone/pull.

Structure: `metadata` (source workbook name, scope, generation date, row
count) plus a `variables` list, one entry per source variable, each with
`name`, `description_he` (Hebrew description, from the workbook's
`variable_meaning` column), and `codes_he` (Hebrew code/category mapping,
from `value_or_category_interpretation`, `null` where the workbook cell was
empty). 128 variables total.

## Local authoring copy (NOT version-controlled)

`docs/data_dictionary/clinical_variable_dictionary.xlsx` — supplied by the
project owner, 2026-08-19 (originally `קובץ פירושים סופי.xlsx` at the repo
root; moved, not copied -- no duplicate remains at the repo root). This is
the **source** the YAML above is generated from, kept locally for editing
convenience, but it is **not committed**: this repository's safety policy
(`CLAUDE.md`'s Commit policy) prohibits committing `.xlsx` files without
exception, and the harness-level commit guard enforces this unconditionally
by file extension regardless of content or any documented policy exception
-- confirmed directly (a narrowly-scoped, path-specific `CLAUDE.md`
exception for this exact file was added and the guard still blocked the
commit on extension alone, 2026-08-19). The `.gitignore` `*.xlsx` rule
therefore applies to this file with no exception; it remains local-only,
present on disk, gitignored like every other Excel file in this repository.
**When the workbook is edited, regenerate the YAML from it** (see
"Regenerating the YAML" below) rather than editing the YAML by hand, so the
two never silently diverge.

## Regenerating the YAML

Regenerate with a small script that reads the workbook's three columns
(`variable_name`, `variable_meaning`, `value_or_category_interpretation`)
via `openpyxl` and writes them to the three YAML fields (`name`,
`description_he`, `codes_he`) using `yaml.dump(..., allow_unicode=True,
sort_keys=False)`, preserving the workbook's own row order for a stable
diff. Do not invent or infer fields the workbook does not contain. After
regenerating, verify: row count (128) unchanged unless the workbook's own
variable count changed; variable-name set equality; no duplicate names; and
every non-null description/code cell preserved exactly.

## Coverage — original/source variables only

This dictionary enumerates **128 original/source variables** — the raw
columns as they arrive from Sheba before preprocessing. It is the source of
truth for **their** semantics and code meanings only.

The current processed dataset (`work_df_batch18.xlsx`) has **156 columns** —
more than 128 — because preprocessing creates additional derived,
cleaned-suffix (`_clean`), categorical (`_cat`), and structural-missingness-
indicator (`__missing_ind`) columns, and Data Cleaning B / EDA C create
further derived/composite features on top of that (e.g.
`derived_hypertension_pih_pet_spectrum`, `derived_diabetes_type_grouped`).
**This workbook does not, and is not intended to, enumerate every one of
those 156+ columns or any later derived/modeling variable.** Do not treat an
absence from this dictionary as evidence that a derived variable is
undocumented — derived variables are documented in the relevant
decision/configuration architecture instead (see the precedence hierarchy
below): `docs/clinical_decisions/manual_decisions_log.md` for the clinical
rationale of each derived feature, and
`analysis/eda/notebook_build/eda_c/eda_c_part3_feature_engineering.py` /
`analysis/data_cleaning/notebook_build/data_cleaning_b/
cleaning_b_part1_setup_inputs.py`'s feature-dictionary mechanism for their
technical construction.

## What this dictionary IS authoritative for

- The clinical **meaning** of original/source variables (the raw columns
  produced by `analysis/preprocessing/run_preprocessing.py`'s `COLUMN_MAPPING`).
- **Categorical code mappings** for source variables (e.g. `diabetes_type`
  codes 0-5, `endo_resection_sites` codes 1-11).
- Distinguishing similarly-named source variables (e.g. `neonatal_death` vs.
  `IUFD`; `CS` vs. `S_P_CS`).

## What this dictionary is NOT authoritative for

- **Modeling horizon eligibility** (Stage 1/2/3, `predictor_allowed` vs.
  excluded) — governed by `outputs/preprocessing/audit/
  variable_classification_minimal.csv` and `analysis/model_variable_readiness/
  config.py`.
- **Leakage decisions** — governed by the "Data Leakage" section of
  `CLAUDE.md` and the classification categories above.
- **Feature-selection decisions** — governed by EDA C's screening outputs
  (`outputs/eda_c/`) and, eventually, Modeling D.
- **Derived-feature definitions** — governed by
  `analysis/eda/notebook_build/eda_c/eda_c_part3_feature_engineering.py` and
  the manual decisions that approved each one.
- **Row-level manual corrections** — governed by
  `docs/clinical_decisions/manual_decisions_log.md`.

## Precedence hierarchy

1. **`clinical_variable_dictionary.yaml`** (this file's canonical companion,
   generated from the local `.xlsx`) — canonical semantics/codes for
   *original* variables, as documented by the data owner.
2. **`docs/clinical_decisions/manual_decisions_log.md`** — approved
   clarifications/corrections that refine or supersede a source value or
   interpretation for this specific cohort (e.g. a documented data-entry
   error, a row-level free-text interpretation, a timing clarification).
3. **Classification/timing/model-readiness configuration**
   (`variable_classification_minimal.csv`, `analysis/model_variable_readiness/
   config.py`, A2/EDA C setup-gate files) — predictor eligibility and modeling
   horizons.

A later layer never contradicts an earlier layer's *semantic meaning* of a
variable; it only adds scope-specific decisions on top (timing eligibility,
row corrections, feature engineering) that this dictionary alone does not
decide. Example: `gestational_age_at_delivery`'s meaning ("gestational age at
the moment of delivery, in weeks+days") comes from this dictionary; its
approved Stage-3-only modeling eligibility comes from a separate, later
Keren/manual decision (Decision 79, `manual_decisions_log.md`) and is not
re-derived from the dictionary's semantic description alone.

## Semantic drift

If an approved manual decision changes a variable's *general* semantic
meaning (not just a row-level correction or a modeling-eligibility change),
this dictionary should be synchronized in the same pass so the two documents
do not silently diverge. See `manual_decisions_log.md` for the log of when
this dictionary was last synchronized with an approved decision.

## Relationship to `docs/variable_documentation/active/`

`docs/variable_documentation/active/` holds a separate `.docx` file that is
the source of truth for **preprocessing implementation** — the raw-to-
standardized column mapping and parsing rules the pipeline is built from (see
`CLAUDE.md`'s "Source of truth" section). This dictionary is a narrower,
purpose-built semantic/code reference layer for documentation and analysis
use; it does not replace or duplicate that file's role, and the two are not
required to be kept in a specific sync relationship beyond both reflecting
the same underlying clinical reality. If the two are ever found to
contradict each other on a variable's meaning, treat it as a documentation
inconsistency to flag and resolve via a manual decision, not as this
dictionary silently overriding the `.docx` (or vice versa).

## 2026-08-19 synchronized corrections

Three wording corrections were applied to this workbook when it was
installed as canonical (approved same-day, see
`docs/clinical_decisions/manual_decisions_log.md` for the corresponding
Decision entry):

- `diabetes_type`: description corrected from "binary" to a categorical
  description ("סוג הסוכרת" — type of diabetes); the 0-5 code list was
  already correct and is unchanged.
- `neonatal_death` / `age_at_neonatal_death`: description corrected from
  "death/age of the fetus" (עובר) to "death/age of the newborn/neonate"
  (היילוד), and distinguished explicitly from `IUFD` (intrauterine fetal
  death, a separate variable).
- `AB`: description corrected to "number of abortions/pregnancy losses,"
  removing the prior "or premature births" framing and any implied specific
  gestational-week cutoff.

No other cells were modified. Row count (128 variables) and all other
variable descriptions and code mappings are unchanged from the supplied
file. These corrections are reflected in both the local `.xlsx` workbook and
the canonical, committed `clinical_variable_dictionary.yaml` (generated from
the corrected workbook, verified field-for-field identical to it).

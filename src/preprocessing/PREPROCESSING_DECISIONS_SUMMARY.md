# Preprocessing Decisions Summary

Examiner-facing summary of the **final** decisions embodied in the raw-data
preprocessing stage (`src/preprocessing/run_preprocessing.py`, Batches
1-19), which converts the raw Sheba workbook into
`outputs/preprocessing/processed/work_df_batch18.xlsx` (431 rows x 156
columns). This is a summary of *outcomes*, not a chronology — it describes
only the rules and classifications currently in force. It is not a
substitute for the executable code, which is the actual source of truth and
is now included in this package (see "Where to look" at the end).

This document is new to this repository (added alongside the privacy-redacted
preprocessing source — see the root `README.md`).

## 1. Cohort construction and exclusions

Starting population: every row in the single raw workbook in
`data/raw/active/` (`data_endo_sheba_active 5.5.26 1547.xlsx`).

Row-level exclusions are applied in this order, all **before**
`target_intrapartum_cs` is created ("target access never precedes cohort
eligibility"):

1. **Elective cesarean section** (`type_of_CS == 1`) — excluded; not a trial
   of labor.
2. **Not in trial of labor** — a woman is in the analytical cohort only if
   `trial_of_labor_corrected == 1`. `trial_of_labor_corrected` starts as a
   copy of the raw `trial_of_labor` field, then is force-corrected to 1 for
   every vaginal delivery (`type_of_CS == 0`), since a vaginal delivery is
   by definition a trial of labor regardless of what the raw field says.
3. **Decision 32** (a protected small number of records): excluded when
   `placenta_accreta == 1` OR `placenta_previa == 1` — placenta accreta/previa
   materially changes intrapartum management and is not representative of
   the general trial-of-labor cohort. Both source columns are dropped from
   the dataset immediately after this one use. The exact count is a
   protected small cell under this project's disclosure policy and is
   deliberately not printed as a literal in this examiner-facing summary.
4. **Decision 67** (16 records, the current, primary cohort definition):
   excluded when `superficial_endometriosis==1 AND peritoneal_endometriosis==0
   AND deep_endometriosis==0 AND endometrioma==0 AND cs_scar_endometriosis==0
   AND clinical_diagnosis_only==1 AND adenomyosis==0` — i.e. records whose
   only endometriosis evidence is an isolated, clinically-unconfirmed
   "superficial" flag with no corroborating phenotype and no formal
   diagnosis. This mask is computed and safety-gated (binary-validated) on
   the outcome-blind 447-record baseline, strictly before
   `target_intrapartum_cs` exists, so the exclusion cannot be influenced by
   the delivery outcome. Two broader sensitivity variants (19-record and
   26-record supersets of the same 16) are also computed and preserved as
   `delivery_id`-keyed flag columns on the final export, for cohort-
   robustness checks only — they are never applied to the primary cohort.
   `clinical_diagnosis_only` is dropped immediately after this single use.

**Final primary cohort: 431 rows.** (447 after Decisions 1-3, minus the
16-record Decision 67 mask.) The pipeline hard-asserts the exact row count
and target split at each checkpoint and raises rather than silently
continuing if a future raw-data change shifts these numbers — see
`CURRENT_APPROVED_COHORT_ROWS`/`_N0`/`_N1` in
`src/preprocessing/src/preprocessing_config.py`.

Three alternative, reproducible cohort definitions (447 "original"/no
exclusion, 428 "exclude19", 421 "strict26") exist purely as sensitivity
checks, selectable via a `cohort_mode` parameter/environment variable; none
of them ever writes to the canonical output path, and none was used to
produce `work_df_batch18.xlsx`.

## 2. Identifier / delivery handling

- **`delivery_id`**: a simple 1-based sequential integer assigned to every
  raw row at load time (Batch 1), before any cohort exclusion — so it is a
  stable per-raw-row key, not necessarily contiguous after filtering.
  Asserted complete and unique by construction.
- **`subject_number`**: mapped from the raw `NUM` column (patient ID). Not
  itself the primary key (a woman can have more than one delivery record);
  `subject_number` + `delivery_id` together are the composite key used for
  every record-level manual clinical decision (Section 4). A small number of
  rows (8 in the current cohort) have a missing `subject_number`; this is
  logged as non-blocking, since `delivery_id` alone remains a complete,
  unique row key.
- Manual clinical corrections are **never** applied by raw value alone —
  only by validated `subject_number` + `delivery_id` composite key, with
  hard validation that rejects duplicate or unmatched keys before any
  correction is applied (`clinical_decisions.py`,
  `validate_composite_key_decisions`).

## 3. Target construction

`target_intrapartum_cs` is derived from `type_of_CS` only after every
row-level cohort exclusion above has already been applied:

- `type_of_CS == 0` (vaginal delivery) -> **0**
- `type_of_CS in {2, 3}` (non-elective/intrapartum CS) -> **1**
- any other value -> `NaN` (would block the run; none occur in the current
  data)

Current distribution: **370 vaginal (0) / 61 intrapartum CS (1)**, verified
by a hard assertion against the approved baseline
(`CURRENT_APPROVED_TARGET_N0`/`_N1`) immediately after construction.

## 4. Manual clinical adjudications / corrections

A small number of individual records received an explicit, clinically
authorized correction, applied strictly by composite key
(`subject_number` + `delivery_id`), never by value pattern alone:

- **`S_P_CS`** (status-post-CS): one record's binary field had a raw value
  of 2 (undefined for a binary field); recoded to 1 (positive) as a
  documented data-entry correction. After this, `S_P_CS` is validated to
  contain only {0, 1, NaN} — any future unexpected value is exported to a
  QA review file rather than silently recoded.
- **`endometrioma`**: one record recoded 0 -> 1, where `endometrioma_size`/
  `endometrioma_place` supporting evidence existed but the binary existence
  flag had not been set — a documented clinical-review correction.
- **`adenomyosis` sonographic feature coding**: a small table of
  authoritative record-level overrides
  (`ADENOMYOSIS_MANUAL_FEATURE_DECISIONS` in `clinical_decisions.py`)
  assigns a specific sonographic feature code to named records — either
  because free-text parsing correctly identified adenomyosis-supportive
  language but could not resolve it to one of the 11 predefined feature
  codes, or because the clinical supervisor supplied a direct correction.
  A companion table (`ADENOMYOSIS_REVIEW_STATUS_DECISIONS`) records the
  final review outcome for records that remain genuinely unresolved after
  this pass — these stay `NaN` **by clinical decision**, not by parser
  failure, and never populate an analytical column.
- All such decision tables are re-validated against the live dataframe on
  every run (duplicate-key and unmatched-key conditions are hard errors),
  so a corrected/re-keyed future dataset cannot silently apply a stale
  decision.

## 5. Free-text-derived rules

Several raw free-text or multi-code fields are parsed into deterministic,
auditable derived columns rather than modeled as free text directly. The
detailed parsing logic lives in `preprocessing_utils.py`,
`adenomyosis_rules.py`, and `endometrioma_rules.py`, and is exercised
batch-by-batch in `run_preprocessing.py`; the notable rules are:

- **`endometrioma_place_clean` / `endometrioma_laterality`**: numeric codes
  are authoritative when present (1=right, 2=left, 3=bilateral, with any
  combination of codes 1-3 collapsing to bilateral); free text is used only
  when no numeric code exists and clearly indicates right/left/bilateral.
  Non-informative text -> `NaN`. `endometrioma==1` with an unknown location
  is preserved as "existence known, location unknown" (`NaN`), never
  silently converted to 0 or flagged as a bug.
- **`endometrioma_size_clean`**: numeric millimeter extraction with an
  approved unit-conversion/ambiguity policy (bare numbers interpreted as mm;
  explicit cm x10; multiple dimensions -> largest; "less than 1 cm" -> 10mm;
  vague non-numeric text -> `NaN`). No ordinal size grouping is created in
  preprocessing — any such grouping is deferred to EDA/modeling.
- **`endometriosis_surgery`**: all free text in the raw field is treated as
  positive surgical evidence (recoded to 1); the original text is moved to
  `endometriosis_surgery_comment` before the binary cleaning step, so
  provenance is preserved. Any remaining 0/`NaN` row with independent
  surgical evidence elsewhere is exported to a review file rather than
  auto-corrected.
- **`endo_resection_sites_clean`** + 10 grouped multi-hot
  `endo_resection_*` columns: deterministic clinical grouping of the raw
  pipe-separated free-text surgical-site field into a lossless, auditable
  multi-hot representation.
- **`percentile_by_Dolberg`**: two recognized Hebrew free-text tokens for
  ">97" and "<3" are recoded to 98 and 2 respectively (directional clinical
  meaning preserved); every other case is left as-is.
- **`NICU_admission` / `RDS`**: a small number of recognized free-text
  values are recoded per clinical rule (`NICU_admission` text -> 1;
  TTN/Meconium-Aspiration/Air-Leak text under the raw `RDS` field -> `RDS=0`
  plus a new `TTN_bin=1`, since these are clinically distinct from RDS).
  Any unrecognized future text is a blocking validation failure, not a
  silent guess.
- **`induction_any_bin`**: derived from `induction_of_labor` /
  `start_of_labor` multi-code fields only (codes 1-4 -> induced, codes
  {0,5} only -> not induced, both missing -> `NaN`); `indication_for_induction`
  is never used to derive this, since an indication does not prove the
  intervention occurred.

## 6. Missingness / structural-missingness handling

- General rule: `NaN` represents true missing/not-relevant; values are never
  filled with 0 unless a specific, documented clinical rule exists.
- **Subgroup-specific ("structural") missingness**: variables that are only
  clinically observable for a subgroup (e.g. cesarean-only fields such as
  `abdominal_cavity_findings`, `other_surgery_complications`,
  `suspected_endo_lesions_during_CS`; surgery-only blood-loss) are set to
  `NaN` outside that subgroup via a single reusable helper,
  `set_outside_subgroup_to_na` (`preprocessing_utils.py`) — never coerced to
  0, since 0 inside the applicable subgroup and "not applicable" outside it
  are different clinical facts.
- **Deterministic 0-fill with clinical justification** (the narrow
  exception to the no-auto-fill rule): `HELLP` and `eclampsia` missing
  values are filled with 0 — a severe, acute event of this kind would have
  been documented if it occurred, so missing is treated as evidence of
  absence, not uncertainty. `any_PET` missing values are filled with 0 only
  where both `mild_PET` and `severe_PET` are already 0.
- Hemoglobin fields (`Hb_before_delivery`, `Hb_after_delivery`) have known
  non-informative text tokens (e.g. "לא נלקח") normalized to true `NaN`
  before numeric conversion; a small number of numeric strings with one
  trailing dot are normalized to their numeric value.
- Structural NaN-to-0 recodes for the `endo_resection_*` family
  (conditioned on `endometriosis_surgery == 0`) and the fold-safe
  categorical/quantile representations referenced in
  `documentation/COMPACT_RIDGE_FINAL_LOCK.md` are Data-Cleaning-B-stage
  decisions, not preprocessing — they are listed here only for orientation;
  preprocessing itself performs no full-cohort learned imputation.

## 7. Variable typing / classification

Batch 19 (the final batch) inventories every one of the 156 analytical
columns and assigns exactly one classification and one type. Current
classification counts (also machine-verified against
`outputs/preprocessing/audit/variable_classification_minimal.csv`):

| Classification | Count |
|---|---|
| `predictor_allowed` | 60 |
| `secondary_near_delivery_predictor` | 6 |
| `intrapartum_predictor_exclude_from_prelabor_model` | 5 |
| `source_or_text_audit_exclude` | 31 |
| `intrapartum_or_post_delivery_exclude` | 37 |
| `leakage_exclude` | 8 |
| `cohort_control_exclude` | 3 |
| `clinically_nonspecific_exclude` | 2 |
| `clinically_redundant_exclude` | 1 |
| `id` | 2 |
| `target` | 1 |
| `manual_review_pending` / `awaiting_clinical_clarification` / `intrapartum_candidate_pending_timing_confirmation` | 0 (none open) |

Type-schema counts: `binary`=88, `text`=24, `continuous`=18,
`categorical`=14, `count`=7, `id`=2, `ordinal`=2, `date_time`=1.

Both registries are produced entirely by rule-based inspection of the
processed dataframe (column dtype, value set, and a static per-column
classification table inside `run_preprocessing.py`) — no manual per-run
editing.

## 8. Leakage prevention

Any variable only knowable during or after the cesarean decision/delivery
itself, or that is a post-outcome/neonatal-outcome measurement, is
classified `leakage_exclude`, `intrapartum_or_post_delivery_exclude`, or
`intrapartum_predictor_exclude_from_prelabor_model` and is never treated as
a pre-labor predictor downstream (the classification registry, not ad hoc
per-analysis judgement, is the single enforcement point). Examples include
`indication_for_CS`, `blood_loss_during_surgery`, `Hb_diff`/`Hb_diff_clean`,
`surgical_site_infection`, `intrapartum_fever`, `postpartum_fever`,
`apgar1`/`apgar5`, `hospitalization_days`, `CS_case_vs_control`,
`other_surgery_complications`, `endometritis`,
`any_blood_product_transfusion`, and every neonatal outcome (birth weight,
Apgar, NICU/RDS/IVH/sepsis/etc.). `gender` is excluded as
newborn-derived/unavailable at prediction time. The full, current,
authoritative, machine-checked list is
`outputs/preprocessing/audit/variable_classification_minimal.csv` (every
row classified `leakage_exclude`,
`intrapartum_or_post_delivery_exclude`, or
`intrapartum_predictor_exclude_from_prelabor_model`), together with the
classification logic itself in the included executable code
(`run_preprocessing.py`, Batch 19).

## 9. Major endometriosis-specific transformations

- **`adenomyosis`**: binary existence, corrected in one record from free-text
  sonographic evidence (Section 4); `adenomyosis_sonographic_features_clean`
  is a deterministic free-text-to-11-code parse, with manual overrides
  (Section 4) for records the parser cannot resolve confidently.
- **`endometrioma`**: binary existence (with the one Section-4 correction);
  location (`endometrioma_place_clean`/`_laterality`) and size
  (`endometrioma_size_clean`) are separately, deterministically derived
  (Section 5), never combined into an ordinal severity scale in
  preprocessing.
- **`endometriosis_surgery`**: cleaned to strict binary with free text
  preserved in a comment column (Section 5); the 10-column
  `endo_resection_*` multi-hot family is the structured representation of
  which anatomical sites/procedures were involved.
- **`superficial_endometriosis`**, **`peritoneal_endometriosis`**,
  **`deep_endometriosis`**, **`cs_scar_endometriosis`**: kept as independent
  binary phenotype flags (agreement between `superficial_endometriosis` and
  `peritoneal_endometriosis` is only ~63%), never merged into a single
  severity variable in preprocessing — that decision, if ever made, belongs
  to EDA/modeling, not this stage. These same flags are also the inputs to
  the Decision 67 cohort-exclusion rule (Section 1).

## 10. Final transition to `work_df_batch18.xlsx`

Batch 18 is the last batch that adds/derives analytical columns (extended
neonatal outcomes and two remaining manual free-text corrections,
`NICU_admission`/`RDS`); its output is saved as the canonical
`work_df_batch18.xlsx` — **431 rows x 156 columns**. Batch 19 runs
immediately afterward and performs read-only QA/classification only: it
does not add, remove, or modify any analytical column or row, and does not
rewrite `work_df_batch18.xlsx`. It writes the classification and
type-schema registries (Section 7) and a small number of QA/audit files.
`work_df_batch18.xlsx` — not any Batch-19 output — is the single frozen
input every downstream stage (Data Cleaning B, EDA A/A2/C, and this
package's own EDA-C-onward outputs) actually consumes.

## Where to look for more detail

- **Record-level decisions and the exact rule implementation**: this
  summary intentionally omits per-record detail. The authoritative,
  executable source is now included in this repository —
  `src/preprocessing/run_preprocessing.py` and
  `src/preprocessing/src/{preprocessing_config,preprocessing_utils,
  clinical_decisions,adenomyosis_rules,endometrioma_rules}.py`. Every rule
  described above traces to a specific, commented block there.
- **Full chronological decision log** (thousands of lines; how each rule
  above was arrived at, superseded drafts, and the clinical discussion
  behind it): `docs/clinical_decisions/` is **not** included in this
  repository (see "Historical documentation" below) — it exists only in the
  canonical research workspace. This summary was written directly from the
  executable code plus that log's already-condensed current-state sections,
  and only current, final decisions are reported here.
- **Machine-checked current counts**: the variable classification / type-schema
  snapshot tables under `results/tables/` (e.g.
  `results/tables/modeling_handoff/variable_classification_snapshot.csv`,
  `results/tables/modeling_handoff/variable_type_schema_snapshot.csv`, and the
  corresponding `results/tables/data_cleaning_b_audit/cleaning_b_variable_*_snapshot.csv`
  pair for the earlier stage).

## Historical documentation — deliberately not included

The canonical research workspace's `docs/clinical_decisions/
manual_decisions_log.md` (~4,500 lines: the full chronological record of
every clinical/methodological decision, including superseded drafts) and
`docs/finalization/` audit trail were **not** copied into this package. They
are historical/process documentation, not required to execute or verify the
preprocessing stage, and reproducing them here would risk presenting
superseded intermediate decisions alongside the current ones with no
narrative to distinguish them. This summary (Sections 1-10 above) reports
only the **final, currently-in-force** rules; where a rule was revised more
than once historically, only its current form is described. If a future
examiner needs the full chronology, it remains available in the canonical
research workspace under the project's existing data-governance process.

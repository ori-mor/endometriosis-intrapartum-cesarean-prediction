# EDA C — Repeated EDA, Feature Engineering, and Modeling Handoff (Sections 3–5)

> **Canonical-repository README — read in submission context.** This file
> was copied from the private canonical research repository. Internal paths
> (`outputs/...`, `analysis/...`, and the canonical
> `notebooks/eda/04_eda_c_modeling_handoff.ipynb` naming — this submission's
> own notebook is `notebooks/04_modeling_handoff.ipynb`, see the root
> `README.md`), Git commit policy, and `.gitignore` references below
> describe *that* repository, not this curated submission.
> This submission intentionally tracks a different, narrower set of files —
> approved *executed* notebooks and privacy-safe aggregate `.csv`/`.xlsx`
> artifacts alongside source, most of which the canonical policy below would
> gitignore. Submission-specific inclusion/exclusion and Git policy is
> defined by the root `README.md` and `SUBMISSION_MANIFEST.md`, not by the
> paths or commit/gitignore rules below.

> ## CURRENT AUTHORITATIVE STATE (this submission)
>
> - Screened = 85, hard-excluded = 4, eligible pool = 81
> - Cumulative Stage 1 / 2 / 3 pools = 70 / 76 / 81
> - Hard co-entry pairs = 8; relationship groups = 13
> - Source of truth: `results/tables/modeling_handoff/candidate_feature_manifest.json`
>   (`n_screened`, `n_eligible_pool`, `stage_architecture.*`,
>   `hard_coentry_pair_count`, `relationship_group_count`) and the row counts of
>   `candidate_feature_review_full.csv` / `candidate_model_features.csv` /
>   `excluded_features_log.csv` / `model_coentry_constraints.csv` /
>   `model_relationship_groups.csv` themselves.
>
> Every other count below (67/73/78, 61/63/67, etc.) is a **historical
> development snapshot** from an earlier point in this file's own change log,
> superseded by Decision 94 (2026-09-01, PET final approval) to the numbers
> above. Where a passage below still calls an old snapshot "current"/"live",
> that label describes what was true *at the time that passage was written*,
> not the state of this submission — always defer to the manifest counts
> above, not to a hardcoded number in prose.

> ## 2026-09-01 completion / correction pass — what changed
>
> Completes the repeated-EDA A1/A2 merge and corrects several naming/redundancy
> issues. The 2026-08-31 stage architecture below is **preserved as of this
> pass** (67 / 73 / 78 cumulative eligible pool — itself superseded shortly
> after by Decision 94 to 70 / 76 / 81, see the CURRENT AUTHORITATIVE STATE
> banner above), `earliest_entry_stage`, target-independent hard
> eligibility, no generic >40% missingness rule, three stage exports + datasets,
> machine-readable downstream contract, no target-informed redundancy winner
> selection).
>
> 1. **C3b — Post-B Variable Inventory & Classification** (`eda_c_part1_setup_gate.py`):
>    adapts CURRENT A1's "Variable Inventory & Classification" + "Predictor Pool
>    & Exclusion Rationale" onto the manifest-driven cleaned dataset +
>    authoritative B metadata, with reconciliation totals (target + id + unified
>    Stage 1/2/3 universe + excluded/deferred == all analytical columns).
>    **C3b accuracy correction (2026-09-01):** it is a **pre-screen** inventory
>    (`analysis_universe_status`, not "eligibility" — final C12 eligibility is
>    decided in C12/C12e); `origin` is `original_preprocessing` /
>    `B_registered_original` / `B_created`, and `cleaning_b_feature_dictionary.csv`
>    metadata (`source_column` / `redundancy_group` / `model_entry_mode` /
>    `redundant_with` / `cutpoint_source` / `clinical_timing` / `domain` /
>    `intended_use` / `leakage_status`) is recovered for **B-registered
>    original** variables (`BMI_after`, `PPROM`, `gestational_age_at_PPROM_days`,
>    `weight_in_pregnancy`) too, not only genuinely B-created ones;
>    `feature_dict_materialized_in_B` (`True` / `False` / `NA`) replaces the
>    ambiguous blank and a present-but-`materialized_in_B==False` registered
>    column fails loud; `available_prediction_horizons` shows cumulative
>    horizon availability (`1`→"Stage 1; Stage 2; Stage 3", `2`→"Stage 2;
>    Stage 3", `3`→"Stage 3"); structural missingness stays three-state
>    registry-driven with `applicability_aware_missing_pct` explicitly
>    descriptive/diagnostic (`NA` when `applicable_n == 0`, never the raw
>    whole-cohort figure; pending tier never relabelled confirmed), an absent
>    gate column fails loud, and `diabetes_type` is verified non-structural;
>    the three non-materialized fold-safe representations (`BMI_after_cat`,
>    `gestational_age_at_PPROM_days_timing_status`, `weight_in_pregnancy_cat`)
>    are disclosed in a **separate** `non_materialized_representation_df` and
>    never enter the reconciliation, `ANALYSIS_VARS`, stage membership, or any
>    eligibility count; reconciliation now uses boolean membership
>    (`in_analysis_universe` / `is_target` / `is_identifier`), not display
>    strings. No classification, stage, value, row, or eligibility decision
>    changes.
> 2. **C5b — Missingness Deep-Dive** (`eda_c_part2_recheck.py`): adapts A2.7 —
>    missingness-by-target (descriptive; **no MAR/MNAR inference**), missingness
>    heatmap (structural columns annotated), co-missingness (Jaccard/lift).
>    Keeps C5's whole-cohort + row-level + registry + applicability-aware view.
> 3. **C10c — Predictor–Predictor Relationships & Redundancy** (`eda_c_part4_screening.py`):
>    adapts A2.10 — Spearman matrix + heatmap + high-|ρ| pairs + scatterplots;
>    numeric×categorical (Kruskal–Wallis on **retained groups** only, with
>    `epsilon_squared` computed on `n_analyzed` = Σ retained-group sizes — the
>    same observations passed to `stats.kruskal`, not `len(complete_pair)` — and
>    `n_complete_pair` / `n_analyzed` / `n_excluded_small_groups` /
>    `n_groups_analyzed` all reconciled and exposed); Cramér's V matrix + heatmap
>    + high-V pairs; a target-independent **representation-relationship
>    classification** for **every** high-association pair from all three blocks —
>    numeric-numeric, categorical-categorical **and numeric-categorical**
>    (exact/superseded / deterministic re-expression / clinically overlapping /
>    clinically distinct but correlated), each row carrying its own
>    `strength_measure` (`spearman_rho` / `cramers_v` / `epsilon_squared` — not
>    interchangeable). B-lineage matching uses **exact source-variable tokens**,
>    not substring containment. The known deterministic pairs `P ↔ nulliparity`
>    and `CS ↔ S_P_CS` are additionally audited in
>    `deterministic_lineage_audit_df` so a known relationship is never lost to a
>    descriptive threshold. Removes no variable; changes no eligibility.
>    Both `P ↔ nulliparity` and `CS ↔ S_P_CS` are **review-only** relationship
>    pairs, not hard co-entry pairs (`model_coentry_constraints.yaml` holds
>    eight hard pairs, none of them parity/prior-CS).
> 4. **C12e — Comprehensive Repeated-EDA Readiness Table** (`eda_c_part4_screening.py`):
>    adapts A2.12 — one master row per screened variable; p/q/effect size shown
>    for **description only**, never eligibility. Marks the end of the
>    repeated-EDA portion.
> 6. **Five fixed-representative redundancy families audited.** `config.py` is
>    **not** modified (shared with other stages); EDA C applies an
>    `EDA_C_FIXED_REPRESENTATIVE_FAMILIES` override:
>
>    | config family | members | audit class | evidence | EDA C behaviour |
>    |---|---|---|---|---|
>    | `parity_history` | G, P, LIVE_BIRTH, AB, EUP, nulliparity | **B** | `nulliparity` is a deterministic binarisation of `P` (corrected upstream directly from `P`); G/LIVE_BIRTH/AB/EUP are distinct obstetric counts | no fixed demotion — all `redundancy_unresolved`, kept |
>    | `prior_cs_count` | S_P_CS, CS | **C** | `S_P_CS = (CS>0)` but `CS` carries the prior-CS **count**, clinically distinct for TOLAC risk (CLAUDE.md `S_P_CS` rule) | no fixed demotion — both `redundancy_unresolved`, kept |
>    | `anthropometry` | BMI_before, weight_before_pregnancy, height | **B** | `BMI_before` is the index; the other two are its own components (Decision 27 imputes all three; no supersession) | no fixed demotion — all `redundancy_unresolved`, kept |
>    | `hypertension` | pregnancy_related_hypertensive_disorder, PIH, mild_PET, severe_PET, any_PET, SIPET | **C** | PIH / mild_PET / SIPET carry distinct severity information; Decision 77 explicitly retained them ungrouped for independent clinical value | no fixed demotion — all `redundancy_unresolved`, kept |
>    | `endometrioma_location` | endometrioma_place_clean, endometrioma_laterality | **A** (superseded by `endometrioma_presence_laterality`, Decision 24/25/70) — but **INERT** | neither raw member is in Batch 19 (< 2 present members) | the one Category-A family EDA C honours; demotes nothing because it has no present members |
>
>    Net effect: `redundancy_demoted` count = **0**; `redundancy_unresolved` = 31;
>    pool size unchanged. Co-entry resolution is deferred entirely to EDA D / CV.
> 7. **Neutral soft-warning names.** `below_quality_bar` → **`weak_univariate_signal`**
>    (a weak univariate association is not low data quality; interactions may
>    still help); `target_correlation_leakage_risk` → **`high_target_association_review`**
>    (high target association is not by itself leakage — real leakage is
>    timing/provenance/classification-based, enforced upstream in C2/C3).
>    Neither flag ever affects eligibility. Renamed in source, exports,
>    manifest, README, tests.
> 8. **Sweetviz stage scope** = the **pre-hard-exclusion** cumulative stage
>    pools (`STAGE_1/2/3_COLS`, 68 / 74 / 79 predictors + target): the repeated
>    EDA profiles — and thereby reveals — zero-variance / sparse / extreme
>    issues rather than silently dropping them. A true constant that Sweetviz
>    cannot render is omitted from the **HTML only**, retained in the analytical
>    universe, and reported; a profiling omission never changes eligibility.
> 9. **Sweetviz dependency.** The EDA stages have **no** requirements file by
>    design (runbook: "any interpreter with pandas/numpy/openpyxl + …");
>    optional notebook profiling follows the same convention as A1's
>    `ydata_profiling` — undeclared, opt-in, guarded. C7b defaults
>    `RUN_STAGE_SWEETVIZ = True` and degrades gracefully with a clear message if
>    `sweetviz` is absent (**no** silent substitution). To enable it locally:
>    `pip install sweetviz==2.3.3`.
> 10. **`pipeline_status` is validation-gated** (`eda_c_part5_handoff.py`):
>     `"CANONICAL"` / `conclusion "PASS"` only when every gate in
>     `pipeline_status_gates` passes (pool validation, 431 rows, target 370/61,
>     strict stage nesting, cumulative Stage 3 == pool, no hard-excluded var in
>     pool, every hard exclusion target-independent); otherwise `"BLOCKED"` /
>     `"FAIL"`. The hardcoded string is gone.

> ## 2026-08-31 methodological rebuild — what changed
>
> EDA C now consumes the current metadata lineage (B classification/type
> snapshots + `cleaning_b_feature_dictionary.csv`) and produces an explicit
> **cumulative Stage 1 / Stage 2 / Stage 3** handoff. The following
> methodological corrections were made for the project's predictive/CV
> architecture:
>
> 1. **Cumulative prediction stages** (`eda_c_part1_setup_gate.py`, C3): builds
>    strictly-nested `STAGE_1_COLS ⊆ STAGE_2_COLS ⊆ STAGE_3_COLS` and
>    `EARLIEST_ENTRY_STAGE` from the **authoritative B classification snapshot**
>    (label → stage: `predictor_allowed`=1, `secondary_near_delivery_predictor`=2,
>    `intrapartum_predictor_exclude_from_prelabor_model`=3). Fails loud on any
>    classification outside that vocabulary or any nesting violation. Adapted
>    from `a2_predictor_readiness/a2_part1_setup_scope.py` (`SB2_SCOPE`).
> 2. **Generic `>40%` missingness HARD-exclusion rule REMOVED**
>    (`eda_c_part4_screening.py`, C12b). High missingness is now diagnostic
>    metadata + a soft warning (`high_missingness_diagnostic`), and a downstream
>    fold-safe-preprocessing requirement — never pre-CV deletion. The ad-hoc
>    `HIGH_MISSINGNESS_EXCLUDE_OVERRIDE = {"BMI_after", "weight_in_pregnancy"}`
>    escape hatch is retired (empty set) — those variables are now ordinary
>    eligible `secondary_near_delivery_predictor` candidates.
> 3. **Target-informed redundancy-representative selection REMOVED** (C12b). The
>    old code, for a `representative=None` family, picked the surviving member by
>    `priority_score` (which contains target effect size + FDR) and marked the
>    others `redundancy_demoted` (a hard co-entry guard downstream). Now: a
>    fixed-representative demotion is honoured **only** for a family listed in
>    `EDA_C_FIXED_REPRESENTATIVE_FAMILIES` — currently just `endometrioma_location`
>    (and even that is inert: neither raw member is in Batch19). Every other
>    family, whatever `config.py` says, is treated as `representative=None` and
>    demotes **nobody** — every member stays eligible, flagged
>    `redundancy_unresolved`, review-only, with the co-entry choice resolved
>    within modeling / CV. Live EDA C therefore has `redundancy_demoted = 0`.
>    `priority_score` remains a descriptive export column only.
> 4. **Three cumulative Sweetviz reports** (`eda_c_part2_recheck.py`, C7b):
>    `outputs/manual_review/eda_c_sweetviz/eda_c_stage{1,2_cumulative,3_cumulative}_sweetviz.html`
>    (git-ignored). Guarded import; no silent substitution. Descriptive only.
> 5. **Stage-specific handoff exports** (`eda_c_part5_handoff.py`, C13):
>    `candidate_features_stage{1,2_cumulative,3_cumulative}.csv` +
>    `modeling_dataset_stage{1,2_cumulative,3_cumulative}.xlsx` (patient-level,
>    git-ignored). Strict nesting + target 370/61 asserted on every slice.
> 6. **Machine-readable downstream contract**: `downstream_preprocessing_requirement`
>    and `fold_safe_requirement` columns on every candidate row, reusing existing
>    `model_entry_mode` / `cutpoint_source` / structural-applicability vocabulary.
> 7. Manifest gains `eda_c_architecture_version`, `stage_architecture`,
>    per-stage before/after counts, and explicit `no_*` / `*_removed` flags.
> 8. **Manual C1 readiness booleans RETIRED** (`eda_c_part1_setup_gate.py` C1;
>    `eda_c_part5_handoff.py` C16). `CLINICAL_DECISIONS_COMPLETE` /
>    `CLINICAL_DECISIONS_LOG_UPDATED` (hand-typed `True`, not runtime evidence)
>    are replaced by **operational** checks derived from the live classification
>    metadata + the C12b pool: no `intrapartum_candidate_pending_timing_confirmation`
>    / `awaiting_clinical_clarification` variable in the analytical universe, no
>    `manual_review_pending` variable in the eligible pool, no
>    forbidden/leakage/post-outcome/source-audit classification in the pool,
>    strict cumulative stage nesting + Stage 3 == full universe, C12c pool
>    validation passed, every hard exclusion target-independent. These also
>    became `pipeline_status` gates, so a blocked/unresolved upstream role
>    reaching a stage or the pool forces `BLOCKED` / `FAIL` — it can no longer be
>    asserted away. The A2 Section A2.14 decision registry and
>    `docs/clinical_decisions/manual_decisions_log.md` remain the
>    historical/provenance record; EDA C does not parse them.
> 9. **Manual candidate-pool override RETIRED** (`eda_c_part1_setup_gate.py` C1/C3).
>    `FINAL_CORE_VARS = []` and its `if FINAL_CORE_VARS:` substitution branch are
>    gone. `ANALYSIS_VARS` is always metadata-derived (union of stage-eligible
>    classification groups + approved B-created variables, forbidden-role
>    protections applied, authoritative order preserved, `Stage 1 ⊆ Stage 2 ⊆
>    Stage 3`). No `MANUAL_CANDIDATE_VARS` / `OVERRIDE_FEATURES` / `CUSTOM_POOL`
>    replacement. Live eligible counts were 67 / 73 / 78 at the time of this
>    correction (2026-08-31) — since superseded to 70 / 76 / 81 by Decision 94
>    (2026-09-01, PET final approval); always re-verify against the live
>    `candidate_feature_manifest.json`.
>
> The hard-exclusion rules that remain are all target-independent: impossible
> values, true zero variance, hard-clinical-unresolved (a materialized derived
> feature whose authoritative `analytical_role` is `"review"` or `"unresolved"`),
> pending-timing-confirmation, and sanity-check-only
> (`analytical_role == "sanity_check_only"`). The legacy `primary_model_eligible`
> field does **not** control eligibility. Current live zero-variance exclusions:
> `alcohol`, `HELLP`, `eclampsia`, `IUFD`.

**Purpose:** Runs on the **cleaned dataset produced by Data Cleaning B (Section 2)**.
Performs a repeated EDA (reusing the A1/A2 analytical architecture), executes
conservative deterministic feature engineering, runs **exploratory** statistical
screening (diagnostic only — never eligibility), and produces a cumulative
Stage 1/2/3 modeling handoff contract.

**Input — one deterministic contract (2026-08-31 C3 correction):** the dataset is
resolved from `outputs/data_cleaning/audit/cleaning_b_manifest.json` (REQUIRED,
project-root only). EDA C loads the exact workbook named by `output_file`
(currently `work_df_batch19_after_data_cleaning_b.xlsx`) from
`outputs/data_cleaning/processed/` and verifies it **byte-for-byte** against the
manifest's `output_sha256`. It also asserts `stage == "data_cleaning_b"`,
`export_for_eda_c == true`, `row_exclusions_applied == false`, and that
`cleaned_rows` / `target_0` / `target_1` / `cleaned_columns_total` match the
loaded data. `USE_LATEST_PROCESSED_BATCH`, `ALLOW_UNCLEANED_BATCH18_TEST_RUN`,
`IS_TEST_RUN`, the "newest cleaned batch" auto-discovery, and every
current-working-directory fallback were **all retired** — any of those inputs
missing or mismatched now fails loud. A future approved Data Cleaning B output
becomes canonical by updating the B manifest through the B workflow, not by EDA C
guessing a filename.

**Run only after:**
1. Data Cleaning B has produced the cleaned dataset (`SAVE_CLEANED_DATASET = True`).
2. The A2 Section A2.14 clinical decisions are resolved and documented in
   `docs/clinical_decisions/manual_decisions_log.md`. EDA C does **not** parse
   that log — instead C16 verifies the equivalent **operational** state from the
   live classification metadata + the C12b pool (no
   `intrapartum_candidate_pending_timing_confirmation` /
   `awaiting_clinical_clarification` variable in the analytical universe, no
   `manual_review_pending` variable in the eligible pool, no
   forbidden/leakage/post-outcome/source-audit classification in the pool, stage
   construction and pool validation pass, every hard exclusion target-independent).

**Candidate universe (C3):** `ANALYSIS_VARS` is rebuilt every run from the
authoritative Data Cleaning B classification snapshot — the union of the
stage-eligible classifications (`predictor_allowed` +
`secondary_near_delivery_predictor` +
`intrapartum_predictor_exclude_from_prelabor_model`) plus approved Data
Cleaning B-created replacement variables, minus the forbidden-role set. There is
**no manual `FINAL_CORE_VARS` / candidate-pool override** on the canonical EDA C
path (retired 2026-08-31); the only reproducible way to build the universe is
from the metadata.

**No test/structure fallback:** if the B manifest, the cleaned workbook, or the
row-key sidecar is missing (or the SHA does not match), EDA C fails loud. A
raw/structure-only pass, if ever needed, belongs in a separate developer harness.

**Controlled validation (C3):** original columns must be in
`variable_classification_minimal.csv` (provenance list of *which columns are
original* — **not** the authority for their current classification *values*,
which is the B classification snapshot); B-created columns must be documented in
`cleaning_b_feature_dictionary.csv`; any undocumented column raises an error.
The row-key sidecar (`cleaning_b_output_delivery_id_key.csv`) is structurally
validated — `row_index` exactly `0..n-1` (no gaps / dupes / missing),
`delivery_id` present and unique (1:1, per the Data Cleaning B export
postcondition) — and its SHA-256 recorded. Duplicate **analytical** rows are
checked on the exported analytical columns with `_row_key_delivery_id` excluded,
so a unique row key can never mask a real duplicate; any duplicate fails loud.
Cohort counts come from `preprocessing_config.py` and are asserted
unconditionally (Data Cleaning B removes no analytical row). Only one in-memory
change is made to the loaded workbook: an `"Unnamed: 0"` pandas import artifact
is dropped if present (disclosed; the canonical export does not contain it).
**Provenance limitation:** `cleaning_b_manifest.json` has no cryptographic
sidecar-binding field, so equal row count + a clean `0..n-1` `row_index` is
consistency evidence, not cryptographic proof, that the sidecar came from the
same B export.

**Does not perform:**
- Model training, tuning, or evaluation
- Final feature/model selection — EDA C performs eligibility filtering only. It
  exports a broad, hard-exclusion-filtered candidate pool, not a capped final list.
  Final selection happens later, in EDA D, under cross-validation.
- Preprocessing or imputation (treatment plan is documented only, not executed)
- Patient-level exports unless `SAVE_SELECTED_MODELING_DATASET = True` is set (default `True`)

---

## Active builder files

| File | Sections | Role |
|------|----------|------|
| `eda_c_part1_setup_gate.py` | C0–C3 | Purpose/safety rules; prerequisites gate; classification CSV load; dataset load + validation |
| `eda_c_part2_recheck.py` | C4–C7 (+ C4b) | Descriptive summary table; distribution plots (C4b); missingness recheck (C5) + deep-dive (C5b); sparsity/separation **diagnostic** (C6, soft-warning only); outlier **statistical IQR** recheck (C7) |
| `eda_c_part3_feature_engineering.py` | C8–C9 | Feature engineering plan (documented table; every row carries a `runtime_availability` that reconciles 1:1 with C9 — `executable_now` / `conditional_skipped_unresolved_source` / `review_only` / `relocated_to_data_cleaning_b` / `not_implementable`; `analytical_role` + `earliest_entry_stage` are the multi-horizon stage contract, `primary_model_eligible` is legacy/compat); deterministic derivation execution with source-contract safety (`diabetes_type` ∈ {0..5}, `any_PET_cat` ∈ {present,absent,not_documented} — unexpected value fails loud, genuine NaN stays unresolved) + the shared narrowly-scoped `DERIVED_FEATURE_CONTRACTS` (formula inputs / rule / allowed output values / NaN propagation only) + `APPROVED_UPSTREAM_ONLY_SOURCES` allowlist for the horizon-inheritance safeguard + a five-way plan↔materialization reconciliation |
| `eda_c_part4_screening.py` | C10–C12c | Derived feature validation; exploratory statistical screening (BH-FDR); candidate review table; eligibility filtering + candidate pool construction; candidate pool validation checks |
| `eda_c_part5_handoff.py` | C13–C17 | Export artifacts (canonical candidate-pool files + additional versioned deliverables); treatment plan; modeling handoff contract; final readiness checklist; output verification |
| `build_eda_c_notebook.py` | — | Assembles all 5 parts into the EDA C notebook |

## Section map (C0–C18)

> Rebuilt-notebook order (2026-09-01, 60 cells). **Repeated-EDA portion:**
> C0, C1, C2, C3 *(load + cumulative `STAGE_1/2/3_COLS` + `EARLIEST_ENTRY_STAGE`)*,
> **C3b** *(post-B **pre-screen** variable inventory & classification —
> origin lineage, feature-dict metadata for B-registered originals, cumulative
> `available_prediction_horizons`, registry-driven structural missingness,
> separate non-materialized-representation table — + exclusion-rationale
> accounting + boolean-membership reconciliation — A1; not final C12
> eligibility)*, C4 *(descriptive Table 1)*, C4b
> *(distribution plots by domain — discrete-count vs continuous, share-safe
> small-cell suppression on the saved figures, stage-aware labels, fail-loud
> plot-coverage reconciliation)*, C4c *(before/after-cleaning column summary /
> cleaning-effect comparison — canonical root-pinned inputs, not a row-level
> value diff)*, C5 *(missingness recheck — applicability-aware row-level:
> `row_missing_count_primary` conservative + labelled pending-structural
> sensitivity)*, **C5b** *(missingness deep-dive — by-target RAW + C5-PRIMARY
> analytical view, PRIMARY-semantics heatmap, PRIMARY-mask co-missingness;
> A2.7)*, C6 *(sparsity / separation **soft diagnostic** — `sparsity_warning_vars`,
> share-safe printed table, not an eligibility gate; zero variance is a
> separate C12 concern)*, C7 *(**statistical IQR** outlier recheck — target-blind;
> `outlier_pct_of_nonmissing` denominator; no clinical plausibility
> classification)*, **C7b** *(three cumulative-stage
> Sweetviz reports, pre-hard-exclusion universe)*, C8/C9 *(feature engineering
> plan + execution — `runtime_availability` reconciles 1:1 with C9; source-contract
> safety fails loud)*, C10 *(derived-feature validation — type-correct target
> association, `high_target_association_review`, deterministic valid-value
> contract fails loud)*, C10b *(formula registry — FAIL-LOUD on missing coverage
> of a materialized feature; deterministic parts from the shared
> `DERIVED_FEATURE_CONTRACTS`)*, **C10c** *(predictor–predictor: Spearman /
> Cramér's V / numeric×categorical Kruskal–Wallis with corrected `n_analyzed`
> ε² denominator / representation-relationship classification over all three
> pair types with exact B-lineage tokens — A2.10)*,
> C11 *(exploratory associations + BH-FDR — diagnostic only)*, C12 *(candidate
> review table)*. **Then:** C12b *(eligibility filtering)*, C12c *(pool
> validation)*, C12d *(derived-feature final role)*, **C12e** *(comprehensive
> repeated-EDA readiness table — A2.12; end of repeated EDA)*, C13 *(export +
> three per-stage candidate CSVs + three per-stage modeling datasets +
> machine-readable downstream contract)*, C14 *(treatment plan)*, C15 *(handoff
> contract)*, C16 *(readiness gate)*, C17 *(output verification)*, C18
> *(constant / near-zero-variance validation)*.
>
> **Methodological order:** Repeated EDA (C3b–C12e / C4b–C11) → Feature
> Engineering (C8/C9) → Post-feature quality check (C10/C10c) → Feature
> Screening / Eligibility (C12b) → Stage-Specific Modeling Handoff (C13).
> No learned/fold-safe transformation is materialised on the full cohort;
> `BMI_after_cat` / `weight_in_pregnancy_cat` /
> `gestational_age_at_PPROM_days_timing_status` are documented-only.

| Section | Part | Description |
|---------|------|-------------|
| C0 | 1 | Purpose, scope, and safety rules |
| C1 | 1 | Prerequisites gate: clinical/metadata readiness checks |
| C2 | 1 | Load approved variable classification CSV |
| C3 | 1 | Resolve + SHA-verify the cleaned B dataset from `cleaning_b_manifest.json`; manifest data contract; row-key sidecar validation; duplicate-analytical-row check; cohort assert; build `ANALYSIS_VARS` + cumulative `STAGE_1/2/3_COLS` |
| C4 | 2 | Descriptive summary table (Table 1 style, by target and domain) |
| C4b | 2 | Distribution plots for the 81-member **baseline staged analysis universe (pre-screen)** (`ANALYSIS_VARS`; live-verified, Decision 94 -- was 79 pre-Decision-94, 69 pre-Decision-91), grouped by domain, saved to `outputs/eda_c/figures/`. Numeric: continuous → histogram + KDE; discrete integer counts → integer-aligned bins, **no KDE** (reuses A2's `_is_discrete_count`). Binary/categorical: aggregate level-count + target-stratified rate bars with **share-safe small-cell suppression on the rendered figure only** (`eda_shared/share_safe.py`, `SHARE_SAFE_MODE`; a suppressed cell is an absent bar + "Suppressed" annotation, never a zero-height bar — analytical values untouched). Panel titles carry `earliest_entry_stage` + cumulative horizons. `c4b_plot_coverage_df` reconciles every variable and **fails loud** on an unresolved plotting failure. Diagnostic only — closes the visual-parity gap with EDA A2 (`a2_predictor_readiness`, renamed 2026-08-24 from `eda_b`; Sections A2.3–A2.6, renumbered from B6–B9 in the 2026-08-08 EDA A/A2 reorg); no cleaning, imputation, row/column, classification, stage, or eligibility change |
| C5 | 2 | Missingness recheck — per variable (raw + registry-driven applicability-aware) + **applicability-aware row-level**: `row_missing_count_primary` (conservative — confirmed structural counts NaN *within* the applicable subgroup only, applicability-linked (no preprocessing mask) keeps **raw** NaN, ordinary keeps raw NaN) and a separately-labelled `row_missing_count_applicability_linked_sensitivity` diagnostic. Reported in **observations (deliveries/rows)**, not "patients". Treatment recommendations respect `model_entry_mode` / `transform_source_only` / structural status — no generic missing-indicator or "unknown"-category proposal. Missingness-burden diagnostic only; does **not** establish complete-case analysis and does **not** affect eligibility |
| C5b | 2 | Missingness deep-dive (adapts A2.7), aligned with C5's contract: (A) RAW whole-column missingness by target **and** a C5-PRIMARY analytical view with `applicable_n` / `missing_within_applicable_n` / `applicability_aware_missing_pct` per target (applicability-linked values labelled sensitivity-only, never replacing raw); (B) heatmap on **PRIMARY analytical missingness** (structural non-applicability not drawn as missingness), secondary RAW heatmap only if it differs; (C) co-missingness on the **PRIMARY masks** (`jaccard` / `lift_vs_independence` descriptive only — not MAR/MNAR/causal/redundancy/exclusion). Observations (deliveries/rows), not "patients". `missingness_by_target_df` / `comissingness_df` are empty-safe with stable columns |
| C6 | 2 | Sparsity and separation **diagnostic** (binary/categorical) — **soft warnings only, not an eligibility gate**. `separation_risk` (unregularized dummy-coded logistic coefficient may diverge; not "every model cannot fit") / `too_sparse` (`min_cell_count < 5`, a **heuristic** review threshold, not an exclusion rule) / `min_cell_count` are carried forward as disclosed soft-warning flags in C12. `blocking_sparsity_vars` → **`sparsity_warning_vars`**. Printed `sparsity_display_df` is share-safe (protected small counts suppressed, never shown as 0); analytical `sparsity_df` keeps exact values for C10/C12. Zero variance is a **separate** target-independent C12 hard exclusion |
| C7 | 2 | Outlier recheck — **statistical IQR 1.5× extreme-value flags** for numeric variables (target-blind); no value removed/capped/transformed. Rate = `n_outliers / N_nonmissing × 100` (`outlier_pct_of_nonmissing`, the ranking key) — **non-missing denominator** (2026-09-01 correction; the old `outlier_mask.mean()` used the full cohort). Asserts `N_nonmissing + missing_n == cohort N` and `0 ≤ n_outliers ≤ N_nonmissing`. `N_nonmissing == 0` → `all_missing / not_evaluable` (not excluded). **No clinical plausible-range classification** — none exists in EDA C and none is invented; the known extreme records were already reviewed upstream, target-blind, so C7 performs descriptive target-blind IQR / skewness diagnostics only and does not re-adjudicate them. `review_transform` → **`transformation_review_flag`** (`|skewness| > 1.5`, diagnostic only) |
| C8 | 3 | Feature engineering plan — documented table of **all** proposed derived features; `runtime_availability` reconciles 1:1 with C9; multi-horizon `analytical_role` + `earliest_entry_stage` (legacy `primary_model_eligible` retained for compatibility) |
| C9 | 3 | Feature engineering execution (deterministic derivations; timing checks; sanity checks). Source-contract safety fails loud on an unexpected `diabetes_type` / `any_PET_cat` value (never silently missing, never silently "absent"); shared `DERIVED_FEATURE_CONTRACTS`; `APPROVED_UPSTREAM_ONLY_SOURCES` allowlist (currently empty — 2026-09-01, Decision 94 retired its sole prior members `any_PET_cat`/`severe_PET_cat`, now approved standalone predictors); five-way plan↔materialization reconciliation. `derived_placental_dysfunction_proxy` **now materializes** (`runtime_availability = executable_now`, `earliest_entry_stage = 1`) since `any_PET_cat` is staged (Decision 94) — no longer conditionally skipped |
| C10 | 4 | Derived feature validation — `derived_missingness_review` (descriptive heuristic, no eligibility); **type-correct** target association (`abs_spearman` / `abs_point_biserial` / `cramers_v`, named per row) surfaced as `high_target_association_review` at a documented descriptive `DERIVED_TARGET_ASSOC_REVIEW_THRESHOLD = 0.7` threshold (**no eligibility effect**; the legacy `leakage_flag` column name is fully retired 2026-09-01 — `high_target_association_review` is the sole stored column); redundancy; **deterministic valid-value contract for every materialized derived feature** (from the shared `DERIVED_FEATURE_CONTRACTS` — an out-of-domain value fails loud); share-safe printed small cells (exact values retained); explicit denominator (`P(target=1 | level)`) on the categorical target panel |
| C11 | 4 | Exploratory statistical screening (**exploratory only**; corrected 2026-09-01 -- see "C11 statistical screening correction" below): signed Mann-Whitney U rank-biserial r (numeric); 2x2 Fisher exact/chi-square with an explicit odds-ratio contrast and zero-cell disclosure (binary/2-level categorical); assumption-aware multi-level Rx2 testing (asymptotic chi-square when adequate, else reproducible Monte Carlo, else `descriptive_only_sparse_multilevel` with Cramér's V still reported) + BH-FDR restricted to `included_in_bh` rows (`bh_family_n` reconciled) |
| C12 | 4 | Candidate feature review table (`candidate_role_for_modeling_review`; **not feature selection**; corrected 2026-09-01 -- see "C12-C12e candidate contract correction" below -- now a **neutral, non-selective review taxonomy**: `association_signal_review` / `clinical_priority_review` / `horizon_specific_review` / `general_review` / `soft_risk_review` / `hard_exclusion_review`); also assigns `domain` from `derived_meta` for a materialized derived feature (fail loud if absent) and the three-tier missingness fields (`raw_missing_pct` / `primary_missing_pct_for_modeling` / `structural_applicability_status` / `applicability_aware_missing_pct_sensitivity`) |
| C12b | 4 | **Eligibility filtering and candidate pool construction.** EDA C performs eligibility filtering only — it does not choose final modeling variables. Target-independent hard-exclusion rules (2026-08-31 rebuild; hard-clinical-unresolved corrected 2026-09-01): impossible values, true zero variance, hard-clinical-unresolved (derived `analytical_role` explicitly `"review"`/`"unresolved"` -- the legacy `primary_model_eligible` field is no longer read for this), pending-timing-confirmation, sanity-check-only (structurally inert -- the sanity feature never reaches `candidate_df`, excluded from `SCREEN_VARS` upstream in C11). **The generic `>40%` missingness rule and its `HIGH_MISSINGNESS_EXCLUDE_OVERRIDE` are removed** — high missingness is now a soft warning (`high_missingness_diagnostic`, evaluated against the PRIMARY missingness value). Complete/quasi separation, boundary-sparse instability, too-sparse, and target-correlation leakage stay soft warnings (2026-08-19/20). **Redundancy** (prose corrected 2026-09-01 to match the live five-family-audit code -- `parity_history`/PPROM-timing/induction-status groups do NOT demote anyone): fixed-representative families (`EDA_C_FIXED_REPRESENTATIVE_FAMILIES`, currently just `endometrioma_location`, and currently inert) demote the others (target-independent); every other `representative=None` family demotes nobody and is flagged `redundancy_unresolved` (choice deferred to CV) -- `redundancy_demoted` is 0 on the live cohort. `priority_score` is descriptive only, never picks a representative, and its missingness term now uses the same three-tier PRIMARY semantics as C5/C12 (no blanket zero-penalty for a `STRUCTURAL_NAN_COLS` variable with genuine within-subgroup missingness). Produces `eligibility_status`, `hard_exclusion_reason`, `soft_warning_flags`, `review_reason` (2026-09-01: now populated for every eligible non-`association_signal_review` role, not only the old `review_candidate`), `redundancy_demoted`, `redundancy_unresolved`, `redundancy_unresolved_group` on `candidate_df`, plus `candidate_pool_df`, `excluded_features_df`, and the share-safe `candidate_display_df`/`candidate_pool_display_df`/`excluded_features_display_df` (2026-09-01). |
| C12c | 4 | Assert-style validation checks on the C12b candidate pool (`pool_validation_passed`) — every hard exclusion is target-independent (strengthened 2026-09-01: exact approved vocabulary, no target-informed metric token); high-missingness pool members disclose the soft diagnostic (against the PRIMARY value); separation/high-target-association/sparse-event variables remain eligible; the three-tier missingness contract holds per status; SCREEN_VARS completeness/uniqueness in `candidate_df`; every materialized derived predictor has a non-unknown `domain`; `candidate_display_df` never alters analytical p/q/effect-size values; zero-variance hard exclusions are exactly the four expected live variables; runs independent of the `SAVE_*` flags |
| C12d | 4 | Derived-feature final role in the candidate pipeline (eligible / hard-excluded / not screened -- the sanity-check-only feature gets an explicit "not part of the screening universe" label, 2026-09-01) |
| C13 | 5 | Export artifacts: the cumulative-Stage-3 candidate pool **plus** `candidate_features_stage{1,2_cumulative,3_cumulative}.csv`, `modeling_dataset_stage{1,2_cumulative,3_cumulative}.xlsx` (patient-level, gitignored), and the machine-readable `downstream_preprocessing_requirement` / `fold_safe_requirement` contract |
| C14 | 5 | Imputation, encoding, and scaling treatment plan (planning only; not executed). **Power-transform contract aligned with Data Cleaning B Section B3 (2026-09-01):** `skewness` is retained as descriptive audit information only and never triggers, names, or pre-selects a transform — there is no `\|skewness\| > 1.5` transformation rule in C14. `transformation_plan` is driven by the authoritative C13 `physical_variable_type`: continuous numeric predictors get `raw_no_fixed_power_transform`; discrete obstetric-history counts (`physical_variable_type == "count"`) get `not_applicable_discrete_count`. Scaling (fold-safe `StandardScaler` when the estimator requires it) is a separate downstream decision, never a response to skewness. Any future nonlinear functional-form alternative is a separate, explicit modeling-stage decision (fold-safe if data-dependent), not an EDA C recommendation |
| C15 | 5 | Modeling handoff contract — candidate pool handoff to EDA D (target, cohort, timing boundary, safeguards) |
| C16 | 5 | Final readiness checklist — `MODELING_HANDOFF_READY = True` only when all **blocking** checks pass. **Operational clinical-readiness checks (2026-08-31)** replace the retired hand-typed `CLINICAL_DECISIONS_COMPLETE` / `CLINICAL_DECISIONS_LOG_UPDATED` booleans: derived from the live classification metadata + the C12b pool — no `intrapartum_candidate_pending_timing_confirmation` / `awaiting_clinical_clarification` variable in the analytical universe, no `manual_review_pending` variable in the eligible pool, no forbidden/leakage/post-outcome/source-audit classification in the pool, cumulative stage construction strictly nested + Stage 3 == full universe, C12c pool validation passed, every hard exclusion target-independent. Other blocking checks apply to the exported candidate pool (zero variance, severe sparsity, separation, hard-exclusion-reason/eligibility-status population, export-matrix column/ID integrity). Whether the full approved `ANALYSIS_VARS` set contains zero-variance/separation-risk variables is reported as an **informational note only** (corrected 2026-07-05) — those variables are expected to exist and simply need to be correctly hard-excluded, not absent from the approved set entirely |
| C17 | 5 | Output verification — reads `outputs/eda_c/` from disk (incl. the three per-stage candidate CSVs and modeling datasets; nesting + target 370/61 checks) |
| C18 | 5 | Constant / near-zero-variance / cohort-invariant validation (descriptive amendment) |

**Zero-variance policy:** Constant status may be audited across all variables,
but automatic `zero_variance` exclusion applies only within the analytical
predictor scope. A true zero-variance exclusion requires no missing values and
exactly one observed unique value; all-missing and partially missing single-value
variables remain missingness issues, and cohort-control variables retain their
original role.

**Value + missingness representation update:** Data Cleaning B no longer exports
`weight_in_pregnancy_cat` or `diagnosis_year_cat` as current analytical
representations. `weight_in_pregnancy` remains a secondary numeric variable,
original NaNs preserved, with **no missingness indicator** (2026-08-29
correction: `weight_in_pregnancy__missing_ind` has been retired entirely — the
approved fold-safe `weight_in_pregnancy_cat` categorical's own
`not_documented` bucket, fitted training-fold-only at modeling time, already
carries the same information).

**`diagnosis_year` (superseded 2026-08-18, Decision 72):** `diagnosis_year` was
reclassified from `predictor_allowed` to `source_or_text_audit_exclude` — it is
the literal calendar year of diagnosis, not disease duration/age-at-diagnosis/
time-since-diagnosis, and must never be predictor-eligible. `diagnosis_year_cat`
remains retired. `diagnosis_year__missing_ind` is no longer created at all by
Data Cleaning B (its source is out of `CLEANING_SCOPE`, so there is nothing left
for it to describe the missingness of) — stronger than the earlier
`manual_review_pending` treatment. None of the three enter EDA C's screened
pool, eligible pool, or any candidate/model-input file. Decision 72 supersedes
Decision 63's predictor-eligibility conclusion. This does not alter EDA C's
scientific logic — the exclusion is enforced upstream, by classification.

**Anthropometric representation — CURRENT state (Decision 91, 2026-08-27,
supersedes Decision 89's materialize-in-B mechanism entirely; unaffected by
Decision 92, 2026-08-29):** `BMI_after_cat` is **retired again as a
Data-Cleaning-B-materialized column** — Decision 89's direct-in-B
construction described in the paragraph this replaces is no longer how the
pipeline works. Neither `BMI_after_cat` nor `weight_in_pregnancy_cat` is
computed as a `df_clean` column at all; both are documented-representation-only
feature-dictionary entries (`materialized_in_B=False`,
`cutpoint_source="fold_safe_training_only"`) — the actual `q33`/`q67`
tertile cutpoints are fitted **training-fold-only**, inside modeling CV, by
`FoldSafeQuantileCategoryTransformer` (`analysis/modeling/final_modeling/
modeling_core.py`), never once from the full 431-row cohort. **Neither
`BMI_after_cat` nor `weight_in_pregnancy_cat` appears in
`candidate_model_features.csv`** — do not describe either as present/eligible
in the current live EDA C pool.

Raw `BMI_after` and `weight_in_pregnancy` **are** present and eligible in the
current pool, both `model_entry_mode=transform_source_only` (they may feed
their respective fold-safe transformers internally in modeling but must
never independently enter a design matrix as a plain numeric predictor).
**There is no generic `>40%` missingness hard-exclusion rule in EDA C** — it
was removed in the 2026-08-31 methodological rebuild. High missingness is
diagnostic metadata + a soft warning (`high_missingness_diagnostic`) only, and
downstream handling is fold-safe (fitted inside training folds).
`HIGH_MISSINGNESS_EXCLUDE_OVERRIDE` (`eda_c_part4_screening.py`) is **retired
and empty** — `HIGH_MISSINGNESS_EXCLUDE_OVERRIDE = set()`. It does **not**
contain `BMI_after` / `weight_in_pregnancy` or any other variable; there is no
generic missingness exclusion left for anything to be "exempted" from, and the
name survives only for backward-compatible references.
`MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS` (`eda_c_part1_setup_gate.py`)
is currently **empty** — neither `BMI_after` nor `gestational_age_at_PPROM_days`
is hard-excluded from `ANALYSIS_VARS` by that mechanism any more; both reach
`ANALYSIS_VARS` disclosed as `transform_source_only` instead.
`DERIVED_INHERITS_SOURCE_EXCLUSION_COLS` currently contains only
`weight_in_pregnancy_cat` (a documentation-only entry now, since that column
is never materialized to begin with). See
`docs/clinical_decisions/manual_decisions_log.md` Decision 91 for full detail.

The pre-pregnancy anthropometric family remains `BMI_before`,
`weight_before_pregnancy`, and `height` (representative
`derived_bmi_before_category`, derived from `BMI_before`) — unaffected.

**Endometrioma representation — CURRENT state:** `endometrioma_size_status`
replaces the retired `endometrioma_size_severity` representation. It is a
nominal categorical full-cohort phenotype variable with states
`no_endometrioma`, `endometrioma_less_than_30mm`, `endometrioma_30mm_or_more`,
and `endometrioma_size_unknown`; unknown size is represented explicitly
rather than imputed into a known-size category — unaffected by Decision 91.
`endometrioma_presence_laterality`'s genuinely unresolved rows are the
explicit `laterality_unknown` category (5 rows, Decision 91 — supersedes the
earlier true-NaN representation approved by Decisions 24/25) — **0 missing**,
not true NaN; do not describe this variable as still carrying missing/NaN
values for unresolved laterality. `endometrioma`,
`endometrioma_presence_laterality`, `endometrioma_size_clean`, and
`endometrioma_size_status` are overlapping endometrioma phenotype
representations. Global family-selection/redundancy enforcement is deferred
to the consolidated final modeling pass.

**Adenomyosis sonographic-feature representation — CURRENT state (Decision
91, 2026-08-27, supersedes Decision 85's single-categorical representation
entirely):** `adenomyosis_sonographic_features_status` (the single ~22-level
combination categorical described in the paragraph this replaces) **is
retired and no longer exists anywhere in the pipeline.** It is superseded by
a lossless, deterministic **12-column multi-hot family**:
`adenomyosis_feature_1`..`adenomyosis_feature_11` (one binary indicator per
approved sonographic-feature code 1-11 — `1` if that code is documented
present, `0` otherwise, including all `adenomyosis==0` rows) plus
`adenomyosis_features_unknown` (`1` when `adenomyosis==1` and no specific
feature is documented, `0` otherwise). All 12 columns are `predictor_allowed`
(Stage 1), `model_entry_mode=direct`, and are **deliberately not registered**
in `DERIVED_REDUNDANCY_GROUPS` — a model can learn each documented feature's
association independently, the same architectural precedent already used for
`endo_resection_*` (a positive-disease binary flag and its granular
sub-feature multi-hot indicators are not mutually exclusive). All 12 are
currently present and eligible in `candidate_model_features.csv`
(live-verified). Do not describe `adenomyosis_sonographic_features_status` as
present, active, or registered in any redundancy group — it does not exist.

## Generated notebook

`notebooks/eda/04_eda_c_modeling_handoff.ipynb` (gitignored)

---

## Legacy files (unreferenced)

The following files are present in this directory but are **not part of the active builder**
and are not referenced by `build_eda_c_notebook.py`:

| File | Status |
|------|--------|
| `eda_c_part1_setup_final.py` | Legacy — superseded by `eda_c_part1_setup_gate.py` |
| `eda_c_part3_handoff.py` | Legacy — superseded by `eda_c_part5_handoff.py` |

These files are kept for reference only. Do not add them back to `PART_FILES`.

---

## `parity_binary_0_vs_1plus` — retired (historical note)

An earlier version of this pipeline (2026-07-02 → 2026-08-02) derived
`parity_binary_0_vs_1plus` in C9 as `(P >= 1)`, and briefly made it the fixed
representative of the `parity_history` redundancy family, because the raw
`nulliparity` column disagreed with `P` and `P` was confirmed authoritative
for prior-parity status (`docs/clinical_decisions/manual_decisions_log.md`
Decision 11). That is no longer how the pipeline works.

**Current state:**

- `parity_binary_0_vs_1plus` is **retired** — EDA C does not create it. It is
  absent from `DERIVED_VARS`, the feature-engineering plan, and every exported
  candidate / model-facing file.
- `nulliparity` is corrected **upstream, in preprocessing**, directly from the
  authoritative parity count `P` (`nulliparity == 1` iff `P == 0`;
  `P >= 1` → `0`; invalid/missing `P` → NaN). It is therefore itself the
  canonical, P-derived binary parity predictor — no second, opposite-polarity
  derived column is needed.
- `nulliparity`, `G`, `P`, `LIVE_BIRTH`, `AB`, and `EUP` **all remain eligible**
  predictors in the exported candidate pool.
- The parity family is a **review-only** modeling relationship group. There is
  **no** current fixed parity representative and **no** parity-family
  `redundancy_demoted` winner architecture — live EDA C has
  `redundancy_demoted = 0` (for this family and overall).
- Final handling of the review-only parity relationship (all members `G` /
  `AB` / `EUP` / `LIVE_BIRTH` / `P` / `nulliparity`) occurs within modeling / CV.
  `P ↔ nulliparity` is a **deterministic derivation** (`nulliparity == I(P == 0)`)
  but is **not** one of the eight hard co-entry pairs in
  `model_coentry_constraints.yaml`: `nulliparity` is a *nonlinear* basis
  function of `P` (a threshold at parity zero), not a linear re-expression, so
  `P` and `nulliparity` may jointly enter a model and their joint entry is a
  modeling-review / coefficient-stability matter, not a global ban. (An interim
  Final-D decision that briefly promoted this pair to hard was superseded and
  reverted on 2026-09-01.) No parity-family member is demoted or removed
  (`redundancy_demoted = 0` still holds).

---

## Key constraints

### Core architectural contracts (canonical explanation — added 2026-08-16)

- **UNSET / `manual_review_pending` safety contract.** A Data-Cleaning-B-created
  column's `predictor_classification` (in `cleaning_b_feature_dictionary.csv`)
  defaults to the literal string `UNSET` until a clinical decision explicitly
  approves a value — `UNSET` never means `predictor_allowed` by default, and is
  never inferred from target association, effect size, or model performance.
  Columns with `intended_use != "review"` (e.g. `"secondary"`) are excluded
  from `B_CREATED_ANALYSIS_VARS` before `predictor_classification` is even
  inspected — they are never modeling candidates, by design, regardless of
  classification. Columns with `intended_use == "review"` and an unresolved
  `UNSET` classification reach an explicit gate (`eda_c_part1_setup_gate.py`,
  `B_CREATED_ANALYSIS_VARS` construction) that excludes them from the pool and
  reports them by name (`B_CREATED_EXCLUDED_UNSET_METADATA`) — excluded, not
  crashed, and never silently promoted. Regression-tested in
  `tests/test_unset_metadata_safety_contract.py` against the real filter code.
  As of 2026-09-01 (Decision 94) there are **zero** current
  `manual_review_pending`/`UNSET` B-created variables — Decision 71's former
  two (`severe_PET_cat`, `any_PET_cat`) are resolved to `predictor_allowed`.
  See `docs/clinical_decisions/manual_decisions_log.md` Decisions 71/94.
- **Derived-feature horizon inheritance.** A derived feature (`eda_c_part3_feature_engineering.py`,
  C9) may never be labeled with an earlier/less-restrictive prediction horizon
  than the latest horizon among its own source columns (Stage 1 + Stage 1 may
  stay Stage 1; any Stage-2 or Stage-3 source forces the derived feature to at
  least that stage). Enforced by an explicit structural safeguard at the end
  of C9 that checks each derived feature's declared `analytical_role` against
  its sources' live classification and fails loudly on a mismatch. A source
  column that is itself conditionally unavailable (e.g. a pending-review
  B-created column) causes a graceful, explicitly-logged skip of the
  dependent derived feature — not a silent construction with a wrong horizon
  — while a source unexpectedly missing for any other reason still fails
  loudly, so a real upstream bug is never hidden behind the same skip path.
  A source that cannot be stage-ranked at all (outside all three stage sets)
  now **fails the safeguard loud** unless it is explicitly registered in
  `APPROVED_UPSTREAM_ONLY_SOURCES` — currently **empty** (2026-09-01,
  Decision 94 retired its sole prior members, the PET `_cat` recodes, now
  approved standalone `predictor_allowed` predictors properly stage-ranked
  via the ordinary path) — a non-rankable source is never silently assumed to
  be an earlier stage.
- **Unified EDA C screening vs. modeling horizons.** Per Decision 65, EDA C
  screens the union of Stage 1 (`predictor_allowed`), Stage 2 additions
  (`secondary_near_delivery_predictor`), and Stage 3 additions
  (`intrapartum_predictor_exclude_from_prelabor_model`) together in one
  candidate pool — it does not itself gate by prediction horizon. Each
  variable's original classification is preserved as metadata
  (`predictor_classification` in the exported candidate files) precisely so
  that horizon-specific filtering can be applied later, at the modeling
  boundary (EDA D), without re-deriving timing information. "Stage 2
  additions" and "Stage 3 additions" (currently **6 and 5** raw
  classification members — `secondary_near_delivery_predictor`=6,
  `intrapartum_predictor_exclude_from_prelabor_model`=5, live-verified in
  `outputs/preprocessing/audit/variable_classification_minimal.csv`; the
  live EDA C *pool* decomposes as 70/6/5=81 predictor_allowed/Stage-2/Stage-3
  members respectively (70 = the raw 67 plus `severe_PET_cat`/`any_PET_cat`/
  `derived_placental_dysfunction_proxy`, Decision 94), which differs from
  these raw classification counts because the pool also includes B-created
  Stage-1 representations such as the 12 adenomyosis multi-hot indicators)
  are incremental counts on top of
  Stage 1, not cumulative totals — do not read them as the full size of
  Stage 2 or Stage 3.

- **Input dataset — resolved from `cleaning_b_manifest.json` (2026-08-31 C3
  correction).** There is no dataset-selection flag. The workbook loaded is
  whatever the B manifest's `output_file` names, from
  `outputs/data_cleaning/processed/`, verified byte-for-byte against
  `output_sha256`. `USE_LATEST_PROCESSED_BATCH`, `ALLOW_UNCLEANED_BATCH18_TEST_RUN`,
  `IS_TEST_RUN`, "newest cleaned batch" discovery, and every CWD fallback are
  retired — the raw `work_df_batch18.xlsx` is never an analytical input.
- **PPROM gestational-age timing family — CURRENT state (Decision 91,
  2026-08-27, supersedes the hard-exclusion described in the paragraph this
  replaces):** the retired derived encodings
  (`gestational_age_at_PPROM_days__missing_ind`,
  `gestational_age_at_PPROM_days__cat`) remain excluded from export and must
  not be reintroduced — superseded by the documented-representation-only
  `gestational_age_at_PPROM_days_timing_status` (four states: `no_PPROM`,
  `PPROM_earlier`/`PPROM_later`, `PPROM_timing_unknown`; not materialized as
  a `df_clean` column, fitted training-fold-only in modeling). The **raw**
  `gestational_age_at_PPROM_days` field, however, is **no longer
  hard-excluded** — `MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS` is
  currently empty, so it **is** admitted to `ANALYSIS_VARS` and is currently
  present and eligible in `candidate_model_features.csv`, disclosed as
  `model_entry_mode=transform_source_only` (it may feed the fold-safe timing
  transformer internally in modeling but must never independently enter a
  design matrix as a plain numeric predictor). **Corrected — this passage
  previously said the applicability-aware ~5.9% figure is "what lets it pass
  the generic high-missingness screen"; that is stale, for two reasons.**
  First, there is no generic `>40%` hard missingness-exclusion rule any more
  — it was removed in the 2026-08-31 rebuild, so there is no such screen to
  "pass." Second, per the restored three-tier PRIMARY-missingness contract
  (see "C12-C12e candidate contract correction" below), this variable is
  **pending-structural, not confirmed-structural**, so its PRIMARY
  missingness value is the raw whole-cohort figure (**~96.3%**), not the
  applicability-aware one; the **~5.9%**
  genuine-missing-within-the-PPROM==1-subgroup figure is exported only as a
  separate sensitivity/diagnostic value, never as PRIMARY. `high_missingness_diagnostic`
  is a soft warning only and never excludes a variable.
- **Output flag defaults (changed 2026-07-02 for Colab/handoff convenience):**
  `SAVE_AGGREGATED_OUTPUTS = True` and `SAVE_SELECTED_MODELING_DATASET = True`
  by default — running the notebook top to bottom writes the candidate-pool
  handoff files (`candidate_model_features.csv`,
  `modeling_dataset_candidate_features.xlsx`, `candidate_feature_manifest.json`,
  `excluded_features_log.csv`, `candidate_feature_review_full.csv`,
  `feature_dictionary.csv`, `eda_c_action_log.csv`) without any manual flag
  edits. `SAVE_OUTPUTS` (from C1) is **no longer used** by C13 — the old "broad
  reference matrix, target + ALL screened features regardless of eligibility"
  concept is superseded by the candidate pool itself, which is now the intended
  broad export.
- **No manual candidate-pool override (retired 2026-08-31).** `ANALYSIS_VARS`
  is **always** the unified Stage 1/2/3 master candidate universe (Decision 65 —
  `predictor_allowed` + `secondary_near_delivery_predictor` +
  `intrapartum_predictor_exclude_from_prelabor_model`, plus approved Data
  Cleaning B-created replacement variables — NOT just `PREDICTOR_ALLOWED_COLS`
  alone), rebuilt every run from the authoritative Data Cleaning B classification
  snapshot. The old `FINAL_CORE_VARS = []` manual list and its
  `if FINAL_CORE_VARS:` substitution branch were removed — a hand-typed variable
  list is an undocumented alternate analytical path. There is no
  `MANUAL_CANDIDATE_VARS` / `OVERRIDE_FEATURES` / `CUSTOM_POOL` replacement.
  Always verify the live `n_eligible_pool` in
  `outputs/eda_c/candidate_feature_manifest.json` rather than trusting a
  hardcoded pool-size number in this note — historical `predictor_allowed`
  checkpoints (61 variables as of Decision 66, 2026-08-15; 63 as of
  2026-08-01; 67 as of 2026-07-30) describe only the `predictor_allowed`
  component alone, not the full unified `ANALYSIS_VARS` universe this bullet
  describes. An automatic file-based import from a prior A2 export
  (`outputs/eda_b/eda_b_candidate_predictors.csv`, silently restricting
  `ANALYSIS_VARS` to whatever that file contained, with no visible error) was
  removed 2026-08-24 — investigated and confirmed it had no producer anywhere
  in the pipeline and was never enabled by default.
- **Downstream co-entry contract (for EDA D / modeling).** Global pairwise
  co-entry bans are defined **only** by the canonical hard co-entry contract
  (`hard_forbidden_with` in `candidate_model_features.csv`, sourced from
  `contracts/model_coentry_constraints.yaml`). `relationship_groups` (from
  `contracts/model_relationship_groups.yaml`) is review-within-modeling
  metadata only — it never removes a variable and never forbids a
  combination on its own. The legacy/descriptive columns `redundant_with`,
  `redundancy_group`, and `redundancy_unresolved_group` are retained for
  backward compatibility and must **not** be interpreted as independent
  global co-entry prohibitions.
### C3 canonical input contract — one deterministic B→C path (2026-08-31 correction)

```
cleaning_b_manifest.json  (REQUIRED, outputs/data_cleaning/audit/, project-root only)
  → output_file            → the exact cleaned workbook loaded from processed/
  → output_sha256          → byte-for-byte integrity gate on that workbook (fail loud)
  → stage / export_for_eda_c → must be "data_cleaning_b" / true
  → row_exclusions_applied → must be false (DCB removes no analytical row → fail loud)
  → cleaned_rows / target_0 / target_1 / cleaned_columns_total → checked vs loaded data
cleaning_b_output_delivery_id_key.csv  (REQUIRED, project-root only)
  → row_index exactly 0..n-1 (no gaps / dupes / missing); delivery_id present + unique 1:1
  → SHA-256 recorded; NOT cryptographically bound to the workbook (disclosed limitation)
→ ANALYSIS_VARS  (metadata-derived; unchanged) → cumulative Stage 1 ⊆ Stage 2 ⊆ Stage 3
```

Retired: `USE_LATEST_PROCESSED_BATCH`, `ALLOW_UNCLEANED_BATCH18_TEST_RUN`,
`IS_TEST_RUN`, the "newest cleaned batch" auto-discovery, the hardcoded
`work_df_batch19_…` filename, and every current-working-directory fallback for
the manifest / dataset / sidecar. Cohort counts (431 / 370 / 61) come from
`preprocessing_config.py` and are asserted unconditionally. Duplicate
**analytical** rows are checked with `_row_key_delivery_id` excluded. The
`"Unnamed: 0"` import artifact is dropped in memory if present (disclosed;
canonical Batch 19 does not contain it) — no other in-memory change; the
workbook on disk is never rewritten. The candidate manifest records
`b_manifest_relpath` / `b_manifest_sha256` / `b_manifest_output_sha256` /
`input_dataset_loaded_sha256` / `input_dataset_sha256_matches_b_manifest` /
`row_key_sidecar_relpath` / `row_key_sidecar_sha256` /
`b_feature_dictionary_sha256` (repository-relative paths).

### C2 metadata contract — one authority per layer (2026-08-31 correction)

EDA C uses exactly one authoritative source for each kind of metadata. There is
**no embedded metadata mirror** and **no current-working-directory alternate**
(both removed 2026-08-31 after an independent review found the embedded copy had
drifted materially from the live `config.py`).

| # | Metadata | Authoritative source | Role |
|---|----------|----------------------|------|
| 1 | Modeling-role classification | Data Cleaning B classification snapshot (`cleaning_b_variable_classification_snapshot.csv`, via `classification_lineage.start_eda_c_snapshot`) | eligibility + stage membership |
| 2 | Variable type | Data Cleaning B type-schema snapshot (`cleaning_b_variable_type_schema_snapshot.csv`) | type-aware screening; **fail loud** for a B-stage variable with no entry (no dtype guess) |
| 3 | B-created / B-registered lineage (`stage`, `clinical_timing`, `domain`, `redundancy_group`, `model_entry_mode`, `redundant_with`, `cutpoint_source`, `materialized_in_B`) | `cleaning_b_feature_dictionary.csv` (loaded in C2) | enriches every B-registered variable's timing/domain; replaces the removed hardcoded `B_CREATED_REPLACEMENT_*` maps |
| 4 | Structural / applicability-aware missingness | `eda_shared/structural_missingness_registry.py` (two disjoint tiers: `CONFIRMED_STRUCTURAL_COLS` / `APPLICABILITY_LINKED_COLS`) | the **only** EDA C structural-missingness definition — **not** `config.py`'s `STRUCTURAL_NAN_COLS`; `diabetes_type` is deliberately not structural |
| 5 | Project domain / timing / clinical-tier / redundancy-group / scoring metadata | `analysis/model_variable_readiness/config.py` | **required** — if it is missing, fails to import, or returns an empty core dict, C2 **raises** (no empty-dict, no embedded fallback) |
| 6 | Preprocessing classification / type CSVs (`outputs/preprocessing/audit/…`) | project-root path **only** | **provenance comparison only** — a value difference is an audit note, never blocking, never overrides the B snapshot |

`config.py` still loads `variable_classification_minimal.csv` as *its* canonical
classification source and still owns `TIMING_MAP` / `DOMAIN_MAP` / `CLINICAL_TIER`
/ `REDUNDANCY_GROUPS` / `SCORING_WEIGHTS` for preprocessing-level variables;
EDA C consumes those directly and never re-hardcodes them. `config.py`'s
`STRUCTURAL_NAN_COLS` is disclosed against the registry for audit visibility but
is not used. The old `_MIN_EXPECTED` "dict has ≥ N entries" check is replaced by
meaningful C2/C3 consistency validation (config loaded; every live universe
member has classification + type metadata; every B-registered Batch19 column has
a feature-dictionary row; classification→stage mapping valid; feature-dictionary
`stage` disagreements disclosed, classification wins; no non-materialized
representation leaked into `ANALYSIS_VARS`; registry gates reference real
columns).

- Classification source of truth: the Data Cleaning B classification snapshot
  (`variable_classification_minimal.csv` is provenance only; `config.py` is not
  the classification source).
- Statistical screening in C11–C12 is **exploratory / descriptive only**. C12b
  performs **eligibility filtering only**, and every C12b hard-exclusion rule is
  **target-independent**: true zero variance, invalid/impossible representation,
  hard-clinical-unresolved (a materialized derived feature whose authoritative
  `analytical_role` is `"review"` or `"unresolved"` — the legacy
  `primary_model_eligible` field is not read for this), pending-timing-confirmation,
  sanity-check-only (`analytical_role == "sanity_check_only"`). Forbidden upstream
  role/timing/leakage classifications (`leakage_exclude`,
  `intrapartum_or_post_delivery_exclude`, `source_or_text_audit_exclude`,
  `manual_review_pending`, …) are enforced in C2/C3, before `ANALYSIS_VARS` is
  built. Separation, quasi/boundary-sparse instability, too-sparse, high
  missingness (the generic >40% hard rule is removed), `weak_univariate_signal`,
  `high_target_association_review`, p / BH-FDR q / effect size are **diagnostics
  / soft warnings only** and never remove a variable before CV. No cap, no
  greedy pick. It is not feature selection — final feature/model selection
  occurs in EDA D, inside cross-validation, not here.
- `mode_of_conception_ivf_vs_all` is the canonical binary IVF-conception
  predictor. The former EDA C-derived `derived_ivf_conception_binary` was an
  exact alias of this source field and is no longer generated or exported.
- `endometrioma_presence_laterality` is the canonical categorical
  representation of endometrioma presence and laterality (`none`, `unilateral`,
  `bilateral`, `laterality_unknown`). **Corrected — this passage previously
  said genuinely unresolved laterality "remains missing"; that is stale.**
  Genuinely unresolved laterality is represented as the explicit
  `laterality_unknown` category, not as NaN — current missing count is
  **0** (see the "Endometrioma representation — CURRENT state" section
  above, Decision 91). The previous binary `endometrioma_bilateral_any`
  representation is retired.
- Timing labels (`pre_pregnancy`, `pregnancy`, `admission_or_pre_delivery`,
  `timing_unknown`, `postpartum_or_outcome`) are informational.
  `timing_unknown` (renamed 2026-08-18 from `unknown_but_likely_pre_delivery` —
  the old name wrongly asserted a pre-delivery presumption for genuinely
  unresolved timing) is never treated as a reason to exclude a variable, and no
  longer earns the old implicit "presumed pre-delivery" scoring bonus either.
  Variables reaching C11/C12 are `ANALYSIS_VARS` (Decision 65: the union of
  `predictor_allowed`, `secondary_near_delivery_predictor`, and
  `intrapartum_predictor_exclude_from_prelabor_model`) — not only
  `predictor_allowed` — so `timing_unknown` can legitimately appear on a
  secondary/intrapartum-horizon variable whose exact timing was never
  clinically pinned down to a `TIMING_MAP` entry; it is not a claim that the
  variable is pre-delivery-available. Hard timing exclusion
  (post-event/intrapartum/post-delivery/neonatal) is enforced upstream in
  C2/C3 (those columns never reach `ANALYSIS_VARS`/`SCREEN_VARS` at all), not
  in C12b.
- ID columns (`subject_number`, `delivery_id`) are never included in any export,
  including `modeling_dataset_candidate_features.xlsx` — see C0 safety rules.

### C11 statistical screening correction (2026-09-01)

Fixed a methodological blocker: multi-level categorical predictors were
always given an asymptotic chi-square p-value, even for a sparse contingency
table where that approximation is unreliable — and that p-value fed BH-FDR
and C12's descriptive scoring. Every `SCREEN_VARS` member now gets exactly
one explicit screening record (`screening_df`); no variable silently
disappears.

- **Test selection is now assumption-aware.** A 2x2 table keeps the existing
  Fisher-exact-vs-chi-square threshold (minimum expected cell `< 5`). A
  multi-level (Rx2) table is checked against a conventional adequacy rule (no
  expected cell `< 1`, `<= 20%` of expected cells `< 5`); an adequate table
  gets ordinary asymptotic chi-square, a sparse table gets a reproducible
  Monte Carlo p-value (`scipy.stats.chi2_contingency(...,
  method=scipy.stats.MonteCarloMethod(...))`, fixed seed `20260901`, 9999
  resamples — feature-detected via `hasattr`, not a hardcoded SciPy version),
  and only if Monte Carlo support is unavailable does the row become
  `test_status = "descriptive_only_sparse_multilevel"` (`p_value = NaN`,
  `included_in_bh = False`, Cramér's V still reported).
- **Numeric rank-biserial r is now signed correctly.** Positive means the
  predictor tends to be higher in `target_intrapartum_cs = 1` than in
  `target_intrapartum_cs = 0` (`effect_contrast = "target1_vs_target0"`). The
  previous formula computed the Mann-Whitney U statistic with the target=0
  sample first, which silently produced the opposite sign; the two-sided
  p-value itself is unaffected.
- **2x2 odds ratios now carry an explicit contrast.** Canonical binary 0/1
  predictors: `"predictor1_vs_predictor0 (target1 odds)"`. Any other
  two-level categorical predictor: the exact two observed levels, e.g.
  `"2_vs_1 (target1 odds)"`. A zero cell in the 2x2 table (real cases exist in
  this cohort, e.g. rare `adenomyosis_feature_*` / `endo_resection_*` /
  `VBAC` / `SIPET` levels) leaves `effect_size = NaN` with
  `effect_estimate_status = "zero_cell_unstable_or_undefined"` rather than
  inventing a continuity correction; the Fisher p-value is retained.
- **`SCREEN_VARS` is the screening universe, not automatically the BH
  family.** The family is every row with `included_in_bh = True` (a finite,
  valid p-value); `bh_family_n` is attached to every row and reconciled
  against the actual finite-p count (fails loud on mismatch, on a
  `SCREEN_VARS` duplicate, or on a variable receiving zero/multiple rows).
  `benjamini_hochberg()` now also rejects a finite p-value outside `[0, 1]`.
- **Binary group-rate wording corrected.** The two by-target percentages are
  `predictor_prevalence_target1_pct` / `predictor_prevalence_target0_pct`
  (predictor prevalence *within* each target group), never "CS risk/rate" or
  "vaginal rate" — that would be the reverse conditional.
- **`screening_display_df`** is a presentation-only, share-safe-suppressed
  copy of `screening_df` (small `N` / `N_missing` / `target0_n` / `target1_n`
  / sparse-expected-cell counts) used for the printed table only; `p_value` /
  `q_value_bh` / `effect_size` are never suppressed, and `screening_df` itself
  always keeps exact analytical values.
- **No change to eligibility, stage membership, hard exclusion, or the
  redundancy/priority-score architecture** — `_hard_exclusion_reasons` never
  reads any C11 statistic, and this was already true before the correction.
  Descriptive fields that DO read C11 output (`candidate_role_for_modeling_review`,
  `priority_score`, `weak_univariate_signal`) can shift in value for a small
  number of multi-level categorical variables now that their p-value is a
  valid Monte Carlo estimate instead of an unreliable asymptotic one — this is
  the intended effect of the fix and remains descriptive-only.
- Field names consumed downstream (`p_value`, `q_value_bh` /
  `fdr_q_value`, `fdr_sig`, `effect_size`, `effect_size_type`) are unchanged;
  new fields (`test_status`, `included_in_bh`, `bh_family_n`,
  `effect_contrast`, `effect_level`, `reference_level`,
  `effect_estimate_status`, `target0_n`, `target1_n`, `n_levels`,
  `table_shape`, `min_expected_count`, `n_expected_cells_lt5`,
  `pct_expected_cells_lt5`, `any_expected_lt1`,
  `predictor_prevalence_target1_pct`, `predictor_prevalence_target0_pct`,
  `target0_median`, `target1_median`) are additive.
- Verified against the 431-row / 79-`ANALYSIS_VARS` / 82-`SCREEN_VARS`
  cohort **as it stood at this 2026-09-01 correction pass** (historical
  execution snapshot — since superseded by Decision 94 to
  81-`ANALYSIS_VARS`-equivalent eligible pool / cumulative stages 70/76/81,
  see the CURRENT AUTHORITATIVE STATE banner above): 78 hypotheses tested
  (71 asymptotic + 7 sparse-multilevel Monte Carlo), 4
  `skipped_insufficient_data_or_zero_variance` (`alcohol`, `HELLP`,
  `eclampsia`, `IUFD` — each effectively zero-variance in this cohort),
  `bh_family_n = 78`, 7 FDR-significant at q<0.05. Batch19 SHA-256, cohort
  431/370/61, and the 67/73/78 cumulative stage-eligible counts (historical,
  pre-Decision-94) were unchanged by this pass (verified via a clean-kernel
  full notebook re-execution).
- **Recorded technical debts (not addressed in this pass, per its explicit
  scope) — items 1 and 2 below are now RESOLVED/SUPERSEDED by Decision 94
  (2026-09-01, PET final approval); retained here only as the historical
  record of what was open at the time this pass was written:**
  1. ~~`derived_placental_dysfunction_proxy`'s C8 plan row states
     `earliest_entry_stage = 2` while it is currently conditionally skipped
     (not materialized) — mark for explicit horizon review before this
     feature is ever re-enabled; not a live stage-count issue today.~~
     **RESOLVED (Decision 94):** `derived_placental_dysfunction_proxy` now
     materializes (`runtime_availability = executable_now`,
     `earliest_entry_stage = 1`, not 2) since `any_PET_cat` is staged — see
     the C9 section above.
  2. ~~`APPROVED_UPSTREAM_ONLY_SOURCES` (C9 horizon-inheritance allowlist) still
     includes `severe_PET_cat` even though the current hypertension formula no
     longer reads it — candidate for later tightening / feature-specific
     authorization review.~~
     **RESOLVED (Decision 94):** `APPROVED_UPSTREAM_ONLY_SOURCES` is now
     **empty** — its sole prior members (`any_PET_cat`/`severe_PET_cat`) are
     retired from the allowlist, now approved standalone `predictor_allowed`
     predictors properly stage-ranked via the ordinary path (see the C9
     section above).
  3. C10's share-safe categorical plots omit suppressed bars rather than
     visibly annotating a suppressed category — presentation cleanup only.
     (Still open; unaffected by Decision 94.)

### C12-C12e candidate contract correction (2026-09-01)

Independent review round covering C12/C12b/C12c/C12e (C12d only where
directly dependent). Three methodological blockers fixed, plus stale
documentation reconciled against already-correct code:

- **Neutral review-role taxonomy (Part A).** `candidate_role_for_modeling_review`
  labelled separation / high-target-association (`leakage_flag`) / sparse
  cells `exclude_candidate` -- directly contradicting C12b's own architecture,
  which treats all three as soft, target-informed, descriptive warnings that
  never remove a variable from the pool before CV. A repo-wide trace (`.py`
  and `.md`) found **no functional consumer** of the field's specific values
  anywhere outside `eda_c_part4_screening.py` itself, so the taxonomy was
  replaced outright (field name kept for continuity): `association_signal_review`
  (FDR-significant -- a signal worth investigating, never automatic
  inclusion), `clinical_priority_review`, `horizon_specific_review`
  (secondary/intrapartum-horizon or ambiguous timing), `general_review`
  (redundancy or no particular signal), `soft_risk_review` (separation /
  high target-association / sparse cells -- never an exclusion recommendation),
  `hard_exclusion_review` (only a genuinely target-independent hard issue:
  impossible values, or explicit pending timing confirmation). `review_reason`
  now carries forward for every eligible role except `association_signal_review`
  (previously only for the old `review_candidate`, so an eligible
  separation/leakage-flagged variable silently lost its explicit reason).
- **Three-tier structural-missingness PRIMARY contract restored (Part C) --
  the pre-C13 blocker.** C12 had collapsed CONFIRMED-structural and
  PENDING-structural into one applicability-aware figure, silently replacing
  a pending-structural variable's PRIMARY missingness with its unconfirmed
  sensitivity figure. Restored the exact three-tier distinction C5 already
  makes: ordinary and pending-structural variables both use RAW as PRIMARY;
  only a CONFIRMED-structural variable (a documented, code-enforced subgroup
  gate) uses genuine-missing-within-applicable-subgroup as PRIMARY. New
  explicit fields: `raw_missing_pct`, `primary_missing_pct_for_modeling`,
  `structural_applicability_status`, `applicability_aware_missing_pct_sensitivity`.
  `effective_missing_pct_for_exclusion` is retained ONLY as a documented
  compatibility alias of `primary_missing_pct_for_modeling` (its old name is
  stale -- no generic missingness exclusion rule exists any more) and never
  carries a pending-structural sensitivity value. Live example --
  `gestational_age_at_PPROM_days` (pending-structural, no code-enforced gate):
  PRIMARY is now the raw ~96.3% (was incorrectly ~5.9%); the ~5.9%
  genuine-within-the-PPROM==1-subgroup figure is exported only as the
  separate sensitivity diagnostic. `priority_score`'s missingness term uses
  the same corrected semantics, with the previous blanket
  "0-penalty-for-every-`STRUCTURAL_NAN_COLS`-variable" rule removed (a
  confirmed-structural variable with genuine within-subgroup missingness must
  not have that information erased) -- live effect: PPROM's `priority_score`
  drops from ≈1.23 to ≈-2.38 (the corrected, much larger raw-missingness
  penalty); the 10 live `endo_resection_*` confirmed-structural variables are
  unaffected (already 0% genuine missingness post-Data-Cleaning-B, so both
  the old and new formulas already gave a 0.0 penalty for them).
- **`primary_model_eligible` retired as a hard-exclusion driver (Part E).**
  C8 explicitly documents this field as legacy/compatibility only; C12b's
  `_hard_excl_pending_review` nonetheless read it as an all-horizon
  hard-exclusion driver. Now reads the authoritative
  `derived_meta[dv]["analytical_role"]` instead -- hard-excluded only for an
  explicit unresolved-state value (`"review"`/`"unresolved"`), never inferred
  from the legacy field; a materialized derived predictor with no
  `analytical_role` at all fails loud. Only iterates `SCREEN_VARS` members
  (never the sanity-check-only feature). Live count unchanged (0 -- every
  currently-materialized derived predictor has `analytical_role="predictor_allowed"`).
- **Derived-feature domain (Part B).** The local `DERIVED_DOMAIN_MAP` registry
  (stale -- missing `derived_hypertension_pih_pet_spectrum`/
  `derived_diabetes_type_grouped`, and largely dead code since
  `derived_endo_surgery_adhesion_status` is no longer `is_derived`) is
  retired; a materialized derived feature's `domain` now comes solely from
  its own `derived_meta[dv]["domain"]` entry (C9's single source of truth),
  failing loud if absent rather than silently exporting `"unknown"`. Live
  domains verified: `derived_prior_endo_surgery_procedure_status` ->
  `prior_endo_surgery`, `derived_hypertension_pih_pet_spectrum` ->
  `hypertension`, `derived_diabetes_type_grouped` -> `diabetes`.
- **Sanity-check-only feature (Part F).** `derived_nulliparity_with_prior_cs`'s
  C12b hard-exclusion rule is confirmed **structurally inert, not merely
  inactive**: the feature is excluded from `SCREEN_VARS` before `candidate_df`
  is even built (C11), so it can never become a `candidate_df` row for this
  rule to evaluate -- documentation corrected to say so explicitly rather than
  implying an active exclusion mechanism; `_is_sanity_check_only` now checks
  `analytical_role=="sanity_check_only"` (matching the feature's own C8 plan
  entry -- added to its runtime `derived_meta` for consistency) instead of the
  legacy field. C12d reports it with an explicit "not part of the screening
  universe" label.
- **C11 metadata propagated into `candidate_df` (Part G).** `test_status`,
  `test`, `included_in_bh`, `bh_family_n`, `effect_contrast`,
  `effect_estimate_status`, `target0_n`, `target1_n` added (additive; `p_value`
  / `q_value_bh` (`fdr_q_value`) / `effect_size` / `effect_size_type` field
  names unchanged). A pending-timing row gets explicit
  `test_status="not_screened"` / `included_in_bh=False`.
- **Share-safe candidate presentation (Part H).** `candidate_display_df` (+
  `candidate_pool_display_df` / `excluded_features_display_df`) suppresses
  `min_cell_count`, `target0_n`/`target1_n`, the structural-applicability `_n`
  fields, and any `event_count_info` text embedding a protected small count,
  under `SHARE_SAFE_MODE`, for the printed previews only --
  `candidate_df`/`candidate_pool_df`/`excluded_features_df` and every
  p-value/q-value/effect-size stay exact and unmasked.
- **Redundancy documentation reconciled with the live five-family-audit code
  (Part I) -- no algorithm change.** Several `DERIVED_REDUNDANCY_GROUPS`
  comments and the old "`parity_history` redundancy family" header
  subsection described a superseded score-based auto-demotion mechanism
  (`representative=None` "score-resolved at runtime", PPROM-timing/
  induction-status groups "correctly demot[ing]" one member, `parity_history`
  demoting `G`/`P`/`LIVE_BIRTH`/`AB`/`EUP` in favor of `nulliparity`) that
  directly contradicted the already-correct 2026-08-31/2026-09-01
  five-family-audit code (`EDA_C_FIXED_REPRESENTATIVE_FAMILIES = {"endometrioma_location"}`
  only; every other family, `parity_history` included, is Category B/C --
  `representative=None`, all live members kept eligible, flagged
  `redundancy_unresolved`, choice deferred to EDA D under CV). Comments
  rewritten to match; live `redundancy_demoted = 0`, confirmed by execution.
- **Stale `>40%` missingness-rule provenance marked historical (Part J).**
  The `HIGH_MISSINGNESS_EXCLUDE_OVERRIDE` historical decision trail
  (Decisions 86-89) is retained (it explains real BMI_after/weight_in_pregnancy
  decisions) but now explicitly labelled as provenance for a permanently
  inert name, not a currently-active exemption mechanism -- there is no
  current generic missingness exclusion rule for anything to be "exempted"
  from. A stale `MANUAL_KNOWN_LIMITATIONS` note referencing
  "`hard_exclusion_reason` if excluded on missingness grounds" corrected to
  state missingness is diagnostic/soft-warning only.
- **C12c strengthened (Part K/L).** New checks: every `SCREEN_VARS` variable
  appears exactly once in `candidate_df`; no duplicate rows; every
  materialized derived predictor has a non-unknown `domain`;
  separation/high-target-association/sparse-event variables remain eligible;
  `hard_exclusion_reason` never contains a target-informed metric token and
  only ever uses the exact approved target-independent vocabulary
  (`invalid_or_impossible_values`, `zero_variance`,
  `hard_clinical_unresolved_pending_review`,
  `pending_timing_confirmation_before_intrapartum_cs_decision`,
  `sanity_check_only_not_a_modeling_candidate`); the three-tier missingness
  contract holds per status; `high_missingness_diagnostic` is evaluated
  against the PRIMARY value; `candidate_display_df` never alters analytical
  p/q/effect-size values; every `SCREEN_VARS` member has C11 `test_status`
  populated; zero-variance hard exclusions are exactly the four expected live
  variables (`alcohol`, `eclampsia`, `HELLP`, `IUFD`). All checks pass
  (`pool_validation_passed = True`), verified by a clean-kernel full notebook
  re-execution.
- **Invariants unchanged by this pass, verified by execution (historical
  execution snapshot at this 2026-09-01 correction — eligible-pool /
  cumulative-stage counts since superseded by Decision 94, see the CURRENT
  AUTHORITATIVE STATE banner above):** cohort 431, target 370/61,
  `ANALYSIS_VARS` 79, `SCREEN_VARS` 82, cumulative stages 67/73/78, eligible
  pool 78, hard-excluded 4 (the same 4 zero-variance variables),
  `redundancy_demoted` 0, Batch19 SHA-256 unchanged, `pipeline_status=CANONICAL`
  / `conclusion=PASS`. No cohort/value/classification/stage/hard-eligibility
  change from this pass.

### Submission-freeze documentation sync

A final documentation/presentation pass brought this README and the C0/C7/C8/
C10c reader-facing notebook prose fully into line with the live code: the
hard-clinical-unresolved driver is described everywhere as
`analytical_role in {"review", "unresolved"}` (not the legacy
`primary_model_eligible`); `HIGH_MISSINGNESS_EXCLUDE_OVERRIDE` is stated as
retired/empty (`= set()`); the `parity_binary_0_vs_1plus` section is a concise
historical note with no current fixed parity representative and no
parity-family `redundancy_demoted` winner; C7 states the extreme-value review
fact directly instead of citing an internal decision number and removes the
false "Data Cleaning B performs KNN imputation" statement; the sole authored
canonical co-entry source is named as `contracts/model_coentry_constraints.yaml`;
and the `mode_of_conception ↔ mode_of_conception_ivf_vs_all` pair is described
as one of the **eight** hard co-entry pairs (never "choice deferred"). No
analytical result changed. (An interim Final-D rebuild step briefly added a
ninth pair, `P ↔ nulliparity`; that was superseded and reverted on 2026-09-01 —
`P ↔ nulliparity` is review-only, see the `parity_binary_0_vs_1plus` section
above. The hard co-entry registry holds exactly eight pairs.)

## Output files (when export flags are enabled)

### Canonical EDA D handoff files — do not rename, remove, or repurpose

These 4 files are `eda_d/`'s sole, hard-coded input contract
(`eda_d_part1_setup_and_contract.py`, `phase4b_endo_search_runner.py` read
these exact filenames and rely on specific columns —
`variable`/`data_type`/`redundancy_group`/`redundancy_demoted`/
`clinical_priority_tier` on `candidate_model_features.csv`, and
`n_eligible_pool` in `candidate_feature_manifest.json`). Any future change to
these must be coordinated with an `eda_d/` update in the same session — not
done silently here.

| File | Flag | Patient rows? | Content |
|------|------|----------------|---------|
| `outputs/eda_c/candidate_model_features.csv` | `SAVE_AGGREGATED_OUTPUTS` | No | Eligible candidate pool only (C12b) — full per-variable metadata, no cap |
| `outputs/eda_c/candidate_feature_manifest.json` | `SAVE_AGGREGATED_OUTPUTS` | No | Run metadata, thresholds, screened/excluded/eligible counts, pass/fail conclusion |
| `outputs/eda_c/candidate_feature_review_full.csv` | `SAVE_AGGREGATED_OUTPUTS` | No | Full review table — eligible + hard-excluded rows (C12/C12b) |
| `outputs/eda_c/modeling_dataset_candidate_features.xlsx` | `SAVE_SELECTED_MODELING_DATASET` | **Yes — gitignored** | Target + ONLY the eligible candidate-pool columns — intended EDA D handoff |

### Other reference/audit files (unchanged)

| File | Flag | Patient rows? | Content |
|------|------|----------------|---------|
| `outputs/eda_c/excluded_features_log.csv` | `SAVE_AGGREGATED_OUTPUTS` | No | Hard-excluded variables + exact `hard_exclusion_reason` |
| `outputs/eda_c/feature_dictionary.csv` | `SAVE_AGGREGATED_OUTPUTS` | No | Derived feature metadata |
| `outputs/eda_c/eda_c_action_log.csv` | `SAVE_AGGREGATED_OUTPUTS` | No | Provenance + run metadata |
| `outputs/eda_c/figures/domain_<domain>_distributions.png` | (written unconditionally by C4b, not gated by `SAVE_*`) | No | Distribution plots, one PNG per clinical-domain group |

### Additional requested deliverables — parallel exports, not a second contract

Added because this session's requested deliverable filenames don't match the
canonical `candidate_*` names above. Each is derived *from* a canonical file
in the same run — never the reverse — so they cannot drift from it. **None
of these are read by `eda_d/`.**

| File | Flag | Patient rows? | Content | Relationship to canonical file |
|------|------|----------------|---------|----------------------------------|
| `outputs/eda_c/final_candidate_features.csv` | `SAVE_AGGREGATED_OUTPUTS` | No | Same content as `candidate_feature_review_full.csv` | Convenience re-export — not a second source of truth |
| `outputs/eda_c/modeling_dataset_all_clean_features.xlsx` | `SAVE_SELECTED_MODELING_DATASET` | **Yes — gitignored** | Target + all 81 baseline `ANALYSIS_VARS` (live-verified, Decision 94 -- was 79 pre-Decision-94, 69 pre-Decision-91) + implementable derived features (`SCREEN_VARS`), **before** eligibility filtering | **Distinct content**, not a mirror — broader than `modeling_dataset_candidate_features.xlsx` (post-hard-exclusion, narrower) |
| `outputs/eda_c/selected_model_features.csv` | `SAVE_AGGREGATED_OUTPUTS` | No | Same variable rows as `candidate_model_features.csv`, plus `variable_name`/`selection_status`/`handoff_role`/`contract_version`/`reason`/`test_used`/`p_value`/`q_value`/`effect_size`/`redundancy_flag`/`timing_leakage_notes` | Versioned re-export — explicitly **not** the old capped-10 Model V1 "conservative primary set" (see Design note below) |
| `outputs/eda_c/feature_selection_manifest.json` | `SAVE_AGGREGATED_OUTPUTS` | No | New contract manifest: `current_contract`, `canonical_d_handoff_files`, legacy-contract disclaimers | **Not** a copy of `candidate_feature_manifest.json` — declares the contract rather than duplicating run statistics |

### Design note — why the distinction matters

EDA C used to export a capped 10-feature "conservative primary set" under
these exact 3 names (`selected_model_features.csv`,
`feature_selection_manifest.json`, `final_candidate_features.csv`, plus
`modeling_dataset_selected_features.xlsx`) before the 2026-07-02→07-05
redesign to the current broad, no-cap candidate-pool design (see C0/C12b).
`analysis/modeling/` (Model V1, untouched, out of scope) still expects that
old contract and is already known-broken independent of this work — see
`eda_d/PHASE_4_HANDOFF.md`. This session's requested deliverables reuse
three of those exact filenames, but their *content* is the current
broad-pool design, not a revival of the capped selection —
`contract_version`/`handoff_role`/`current_contract` fields make that
explicit everywhere it could otherwise be ambiguous. `analysis/modeling/`
was not modified and this does not fix its incompatibility with the current
design; that remains a known, separate, out-of-scope gap.

`outputs/eda_c/` (including `outputs/eda_c/figures/`) is covered by
`.gitignore`. `SAVE_OUTPUTS` (from C1) is no longer used by C13 — see the
"Output flag defaults" note above.

## Commit policy

Commit `.py` and `.md` files. Never commit `.ipynb`, `.xlsx`, or `.csv`.

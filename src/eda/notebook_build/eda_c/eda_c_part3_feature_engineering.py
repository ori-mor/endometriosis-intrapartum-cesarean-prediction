#!/usr/bin/env python3
"""EDA C — Part 3 cell definitions (sections C8–C9).

C8 — Feature engineering plan: documented table of all proposed derived features.
C9 — Feature engineering execution: deterministic derivations with leakage checks.

All derived features use the prefix 'derived_'. Source columns are never overwritten.
Only features marked 'implementable = yes' are executed.
"""


def src(text):
    lines = text.lstrip("\n").splitlines(keepends=True)
    if lines and lines[-1].endswith("\n"):
        lines[-1] = lines[-1][:-1]
    return lines


def md(cid, text):
    return {"id": cid, "cell_type": "markdown", "metadata": {}, "source": src(text)}


def code(cid, text):
    return {
        "id": cid,
        "cell_type": "code",
        "metadata": {},
        "source": src(text),
        "outputs": [],
        "execution_count": None,
    }


# ── Section C8 ─────────────────────────────────────────────────────────────────
SC8_HEADER = md("eda-c-s08-header", """
## Section C8 — Feature Engineering Plan

This table documents **every proposed derived feature before any is executed**,
and — via `runtime_availability` — must reconcile exactly, feature-for-feature,
with what C9 actually materializes. Features whose `runtime_availability` is
`executable_now` are derived in C9. `derived_nulliparity_with_prior_cs` is
`review_only` but is still computed in C9 as a sanity-check-only variable (never
a modeling candidate) — see its dedicated block below for why.

### Documentation fields
- **source_columns**: exact column names the derivation formula actually reads
  — no invented names, and (for a feature whose clinical redundancy family is
  wider than its formula inputs) not padded with non-read family members
- **redundancy_family_columns**: broader clinically/representationally
  overlapping variables that are *not* direct formula inputs and that require
  **explicit modeling co-entry review** with the derived feature (informational;
  separate from `source_columns`). Whether co-entry is actually **HARD-forbidden**
  is determined **only** by the sole authored canonical C13 hard co-entry
  registry, the tracked YAML
  `analysis/eda/notebook_build/eda_c/contracts/model_coentry_constraints.yaml`
  (`outputs/eda_c/model_coentry_constraints.csv` and any local `contracts/*.csv`
  are generated inspection/runtime mirrors of that YAML, never the source);
  everything else here is `review_within_modeling`, not a global prohibition.
- **clinical_rationale**: why this feature is clinically meaningful
- **timing**: the latest time window any source column belongs to
- **leakage_risk**: `no` or `review` (never `yes` for an implementable feature)
- **missingness_risk / missingness_behavior**: expected missing rate relative to
  source columns, and the deterministic rule for when the output is left NaN
- **expected_type**: the derived variable's type (binary / categorical / …)
- **implementable**: `yes` = the formula is fully specified and implementable
  **when its approved upstream source columns are available**; `review` =
  clinically ambiguous source; `no` = source unusable; `relocated` = now
  created upstream in Data Cleaning B
- **runtime_availability** (the authoritative materialization status — see below)
- **analytical_role**: the derived feature's own classification if materialized
  (`predictor_allowed` / `sanity_check_only` / `not_a_candidate`); mirrors the
  C9 `derived_meta` value, checked by C9's horizon-inheritance safeguard
- **earliest_entry_stage**: earliest cumulative prediction horizon the derived
  feature could enter (1 / 2 / 3 / `n/a`), inherited from its latest source
- **primary_model_eligible**: **legacy/compatibility field only.** Retained for
  downstream objects that still read it. This project is multi-horizon
  (cumulative Stage 1/2/3) — there is no single "primary
  pre-admission model", so `analytical_role` + `earliest_entry_stage` +
  the horizon-availability wording are the real stage contract, not this field.

### `runtime_availability` — the plan ↔ C9 reconciliation key
Every plan row carries exactly one of:
- `executable_now` — materialized in C9 this run, added to `DERIVED_VARS`.
- `conditional_skipped_unresolved_source` — formula is fully implementable, but
  a required upstream source is not in the staged analysis universe this run
  (e.g. a variable registered only in `APPROVED_UPSTREAM_ONLY_SOURCES`, not a
  standalone candidate). **Gracefully skipped — this is NOT a C9 failure** and
  is re-enabled automatically whenever the upstream source is present. No
  current plan row uses this bucket as of 2026-09-01 (Decision 94 resolved
  the last one, `derived_placental_dysfunction_proxy`, to `executable_now`);
  the bucket remains available for a future genuinely-unresolved source.
- `review_only` — computed for data-quality purposes only, never a modeling
  candidate (the nulliparity/prior-CS contradiction sanity check).
- `relocated_to_data_cleaning_b` — no longer created here; consumed through the
  ordinary `B_CREATED_ANALYSIS_VARS` pathway.
- `not_implementable` — source column cannot support a modeling feature.

C9 prints a five-way reconciliation (planned / formula-implementable /
conditionally-skipped / relocated / actually-materialized `DERIVED_VARS`) and
fails loud only on a genuine mismatch (an `executable_now` row that did not
materialize, or a materialized column with no plan row).

### Conservative principles
1. Derived features are candidate representations — not guaranteed model inputs.
2. No feature is marked as a "validated clinical score" unless it comes from a
   published and validated instrument.
3. Features with clinically ambiguous source columns are marked `review`.
4. Retired representations are not created or exported from the active EDA C
   handoff. Historical audit outputs may still mention them.

### Warning
`derived_nulliparity_with_prior_cs` is a **sanity-check feature only**.
Nulliparity = 1 AND prior CS = 1 is logically inconsistent. If this feature
has a non-zero count, it signals a potential data-coding error and must be
reviewed before modeling.

### Retired count/composite representations
The prior count/composite representations retired by the final decision freeze
are no longer created here. Their source variables remain available under the
current screening rules where appropriate.
""")

SC8_PLAN = code("eda-c-s08-plan", """
# ── Feature engineering plan table ─────────────────────────────────────────────
# This table is printed and reviewed BEFORE any feature is executed.
# Changes to implementable status or source columns require explicit approval.

_FEATURE_PLAN = [
{
        "new_feature_name": "derived_prior_endo_surgery_procedure_status",
        "source_columns": (
            "endometriosis_surgery, "
            "endo_resection_ovarian_endometrioma_unilateral, "
            "endo_resection_lesion, endo_resection_adhesiolysis"
        ),
        "redundancy_family_columns": "endometriosis_surgery, endo_resection_* family",
        "clinical_rationale": (
            "Exploratory prior-endometriosis-surgery representation with a coarse "
            "documentation-status distinction for a selected subset of reliably "
            "coded structured procedure variables. This is NOT a validated "
            "surgical severity score and NOT a burden score."
        ),
        "timing": "pre_pregnancy",
        "leakage_risk": "no",
        "missingness_behavior": (
            "low in the current cleaned cohort; a surgery-positive row is left "
            "NaN when any selected-procedure source is missing (status "
            "unresolvable); endometriosis_surgery missing -> NaN"
        ),
        "expected_type": "categorical (3 states)",
        "implementable": "yes",
        "runtime_availability": "executable_now",
        "analytical_role": "predictor_allowed",
        "earliest_entry_stage": 1,
        "primary_model_eligible": "yes (legacy field)",
        "notes": (
            "States: no_prior_endo_surgery; "
            "prior_surgery_no_selected_procedure_documented; "
            "prior_surgery_with_selected_procedure_documented. The selected "
            "procedures are only a subset of reliably coded structured surgical "
            "variables. 'No selected procedure documented' must not be interpreted "
            "as no procedure or no resection occurred. Its co-entry with the "
            "structured endo_resection_* family is review_within_modeling (the "
            "prior_endometriosis_surgery relationship group); its HARD pair is "
            "with endometriosis_surgery only (C13 registry, deterministic status "
            "encoding)."
        ),
    },
    {
        "new_feature_name": "derived_endo_surgery_adhesion_status",
        "source_columns": "endometriosis_surgery, endo_surgery_adhesiolysis",
        "redundancy_family_columns": "endometriosis_surgery, endo_resection_adhesiolysis",
        "clinical_rationale": (
            "Exploratory prior-endometriosis-surgery adhesion finding/status "
            "representation: whether adhesions were documented during prior "
            "endometriosis surgery. This does not indicate whether adhesiolysis "
            "was performed."
        ),
        "timing": "pre_pregnancy",
        "leakage_risk": "no",
        "missingness_behavior": "low in the current cleaned cohort",
        "expected_type": "categorical (3 states)",
        "implementable": "relocated",
        "runtime_availability": "relocated_to_data_cleaning_b",
        "analytical_role": "predictor_allowed",
        "earliest_entry_stage": 1,
        "primary_model_eligible": "yes (legacy field)",
        "notes": (
            "Created upstream in Data Cleaning B -- "
            "no longer created here; consumed via the ordinary B_CREATED_ANALYSIS_VARS "
            "pathway (its formula/valid-value contract is the B feature dictionary's). "
            "Current architecture has 3 active states only: "
            "no_prior_endo_surgery; prior_surgery_without_documented_adhesions; "
            "prior_surgery_with_documented_adhesions -- the current cohort has 0 "
            "genuinely-missing-applicable rows, so a 4th 'unknown' state is not "
            "invented; a future genuinely missing applicable row fails loud instead "
            "of silently reintroducing an unused category. "
            "endo_resection_adhesiolysis remains the separate performed-procedure "
            "variable for adhesiolysis."
        ),
    },
{
        "new_feature_name": "derived_placental_dysfunction_proxy",
        "source_columns": "any_PET_cat, IUGR",
        "redundancy_family_columns": (
            "any_PET_cat, severe_PET_cat, IUGR, derived_hypertension_pih_pet_spectrum"
        ),
        "clinical_rationale": (
            "Exploratory placenta-mediated complication phenotype: PET present "
            "or IUGR present. This is a clinically motivated proxy only, not a "
            "validated clinical score, not a severity score, and not a "
            "missingness indicator."
        ),
        "timing": "pregnancy",
        "leakage_risk": "no",
        "missingness_behavior": (
            "inherits genuine PET unknown status: an unresolved PET state "
            "(not 'present'/'absent') with IUGR != 1 remains NaN; no fillna(0)"
        ),
        "expected_type": "binary",
        "implementable": "yes",
        "runtime_availability": "executable_now",
        "analytical_role": "predictor_allowed",
        "earliest_entry_stage": 1,
        "primary_model_eligible": "yes (legacy field)",
        "notes": (
            "1 if any_PET_cat == 'present' OR IUGR == 1; 0 only if "
            "any_PET_cat == 'absent' AND IUGR == 0; NaN otherwise. "
            "any_PET_cat is now an approved predictor_allowed/Stage 1 standalone "
            "predictor in its own right (Decision 94, 2026-09-01, retiring its "
            "prior manual_review_pending state) and IUGR is predictor_allowed/ "
            "Stage 1 -- both sources are present in df_analysis, so this feature "
            "now materializes (previously CONDITIONALLY SKIPPED while any_PET_cat "
            "was unavailable; see docs/clinical_decisions/manual_decisions_log.md "
            "Decision 94). earliest_entry_stage recomputed from its actual source "
            "stages (both Stage 1) -- not the prior placeholder Stage 2. "
            "Alternative representation to any_PET_cat and IUGR."
        ),
    },
{
        "new_feature_name": "derived_hypertension_pih_pet_spectrum",
        "source_columns": "PIH, any_PET_cat, SIPET, HELLP, eclampsia",
        "redundancy_family_columns": (
            "pregnancy_related_hypertensive_disorder, PIH, mild_PET, severe_PET_cat, "
            "any_PET_cat, SIPET, HELLP, eclampsia"
        ),
        "clinical_rationale": (
            "Predefined 3-level grouped clinical representation of the hypertension "
            "family: no_hypertensive_disorder / pih_gestational_htn / "
            "preeclampsia_spectrum. Defined purely from clinical/source semantics, "
            "NOT from target association. SIPET/HELLP/eclampsia are "
            "each, by their own established clinical definition, preeclampsia "
            "diagnoses and fall in the spectrum level."
        ),
        "timing": "pregnancy",
        "leakage_risk": "no",
        "missingness_behavior": (
            "NaN when any_PET_cat == 'not_documented' and none of SIPET/HELLP/"
            "eclampsia is positive (spectrum genuinely unresolved -- not guessed "
            "as level 0); NaN when spectrum-negative but PIH is missing. No fillna."
        ),
        "expected_type": "categorical (3 states)",
        "implementable": "yes",
        "runtime_availability": "executable_now",
        "analytical_role": "predictor_allowed",
        "earliest_entry_stage": 1,
        "primary_model_eligible": "yes (legacy field)",
        "notes": (
            "Formula reads PIH (df_analysis) and any_PET_cat/SIPET/HELLP/eclampsia. "
            "any_PET_cat is an approved standalone predictor_allowed/Stage 1 "
            "predictor in its own right (Decision 94, 2026-09-01, retiring its "
            "prior manual_review_pending state) and is present in df_analysis via "
            "the ordinary staged-analysis path -- it is also a "
            "direct formula input to this derived feature. Its categorical representation "
            "remains present/absent/not_documented -- an unambiguous "
            "deterministic recode of any_PET (1/0/NaN); not_documented is "
            "genuinely unresolved PET documentation status and is never silently "
            "treated as absent. mild_PET and severe_PET_cat are clinical-"
            "redundancy-family members (severe_PET_cat is itself an approved "
            "standalone predictor_allowed/Stage 1 predictor too) but are NOT "
            "formula inputs to this feature. Co-entry with the individual "
            "hypertension source variables is review_within_modeling (the "
            "hypertension_spectrum relationship group) -- NOT an automatic HARD "
            "pair against each PIH/PET subtype. It has NO HARD co-entry pair in "
            "the C13 registry. See "
            "DERIVED_REDUNDANCY_GROUPS['hypertension_pih_pet_spectrum_representation']."
        ),
    },
{
        "new_feature_name": "derived_diabetes_type_grouped",
        "source_columns": "diabetes_type",
        "redundancy_family_columns": "gestational_diabetes, diabetes_type",
        "clinical_rationale": (
            "Deterministic 4-level clinical grouping of diabetes_type's confirmed "
            "code dictionary (0=no diabetes, 1=pregestational unspecified, 2=type 1, "
            "3=type 2, 4=GDMA1, 5=GDMA2): no_diabetes / pregestational (1,2,3) / "
            "GDMA1 (4) / GDMA2 (5). Grouped on category-size and clinical-"
            "interpretability grounds only (each of codes 1/2/3 is individually too "
            "sparse; the combined pregestational category stays clinically "
            "coherent), NOT on target association."
        ),
        "timing": "pregnancy",
        "leakage_risk": "no",
        "missingness_behavior": (
            "NaN iff diabetes_type is missing. An unexpected non-missing code "
            "outside {0,1,2,3,4,5} FAILS LOUD in C9 -- it is never silently mapped "
            "to NaN."
        ),
        "expected_type": "categorical (4 states)",
        "implementable": "yes",
        "runtime_availability": "executable_now",
        "analytical_role": "predictor_allowed",
        "earliest_entry_stage": 1,
        "primary_model_eligible": "yes (legacy field)",
        "notes": (
            "HARD co-entry pair with diabetes_type ONLY (C13 registry: deterministic "
            "coarsening -- the grouped variable is a function of diabetes_type). "
            "gestational_diabetes is review_within_modeling (diabetes_representation "
            "relationship group), NOT a HARD pair: current executable lineage does "
            "not prove deterministic recoverability from it. See "
            "DERIVED_REDUNDANCY_GROUPS['diabetes_representation']."
        ),
    },
{
        "new_feature_name": "derived_nulliparity_with_prior_cs",
        "source_columns": "nulliparity, S_P_CS",
        "redundancy_family_columns": "n/a (data-quality check, not a candidate)",
        "clinical_rationale": (
            "Interaction flag: nulliparity = 1 AND prior CS = 1. "
            "This combination is clinically inconsistent - a nulliparous patient "
            "cannot have had a prior delivery by any mode. "
            "SANITY-CHECK ONLY: non-zero count indicates a data-coding error."
        ),
        "timing": "pre_pregnancy",
        "leakage_risk": "no",
        "missingness_behavior": (
            "1 iff nulliparity == 1 AND S_P_CS == 1; 0 when both sources are "
            "observed and not both == 1; NaN when either source is missing"
        ),
        "expected_type": "binary",
        "implementable": "review",
        "runtime_availability": "review_only",
        "analytical_role": "sanity_check_only",
        "earliest_entry_stage": "n/a",
        "primary_model_eligible": "no",
        "notes": (
            "NOT a modeling candidate. Computed in C9 for a data-quality sanity "
            "check only. If count > 0, flag for data review before modeling."
        ),
    },
{
        "new_feature_name": "derived_conception_mode_detail",
        "source_columns": "mode_of_conception_details",
        "redundancy_family_columns": "mode_of_conception, mode_of_conception_ivf_vs_all",
        "clinical_rationale": "Detailed conception mode grouping.",
        "timing": "pre_pregnancy",
        "leakage_risk": "no",
        "missingness_behavior": "high missingness; source is free-text / audit-only",
        "expected_type": "categorical",
        "implementable": "no",
        "runtime_availability": "not_implementable",
        "analytical_role": "not_a_candidate",
        "earliest_entry_stage": "n/a",
        "primary_model_eligible": "no",
        "notes": (
            "Source column is in source_or_text_audit_exclude - "
            "free-text or audit-only; not suitable for modeling."
        ),
    }
]

feature_plan_df = pd.DataFrame(_FEATURE_PLAN)

# ── runtime_availability buckets (the plan <-> C9 reconciliation key) ─────────
_RUNTIME_BUCKETS = [
    ("executable_now", "executable now (materialized in C9)"),
    ("conditional_skipped_unresolved_source",
     "conditionally available / skipped (approved upstream source unresolved this run)"),
    ("review_only", "review-only sanity check (computed, never a modeling candidate)"),
    ("relocated_to_data_cleaning_b", "relocated to Data Cleaning B"),
    ("not_implementable", "not implementable"),
]
_bucket_members = {
    key: feature_plan_df.loc[feature_plan_df["runtime_availability"] == key,
                             "new_feature_name"].tolist()
    for key, _ in _RUNTIME_BUCKETS
}
_unbucketed = feature_plan_df.loc[
    ~feature_plan_df["runtime_availability"].isin([k for k, _ in _RUNTIME_BUCKETS]),
    "new_feature_name",
].tolist()
if _unbucketed:
    raise ValueError(
        "C8 feature plan: every row must carry a recognised runtime_availability "
        f"value; unrecognised for {_unbucketed}"
    )

print(f"Feature engineering plan: {len(_FEATURE_PLAN)} proposed features")
print()
for _key, _label in _RUNTIME_BUCKETS:
    _m = _bucket_members[_key]
    print(f"  {_label}: {len(_m)}")
    for _name in _m:
        print(f"      - {_name}")
print()
print("NOTE: a 'conditionally available / skipped' feature is NOT a C9 failure -- "
      "its formula is fully specified; only an approved upstream source is "
      "temporarily unavailable to the staged analysis universe. C9 prints the "
      "authoritative five-way plan<->materialization reconciliation.")
print()
_C8_DISPLAY_COLS = [
    "new_feature_name", "source_columns", "timing", "expected_type",
    "implementable", "runtime_availability", "analytical_role",
    "earliest_entry_stage", "primary_model_eligible",
]
print(feature_plan_df[_C8_DISPLAY_COLS].to_string(index=False))
""")


# ── Section C9 ─────────────────────────────────────────────────────────────────
SC9_HEADER = md("eda-c-s09-header", """
## Section C9 — Feature Engineering Execution

Executes the C8 plan. A `runtime_availability = executable_now` feature is
materialized and added to `DERIVED_VARS`; `conditional_skipped_unresolved_source`
is gracefully skipped (approved upstream source not in the staged universe —
**not a failure**); `review_only` (`derived_nulliparity_with_prior_cs`) is
computed for a data-quality check only and never becomes a modeling candidate;
`relocated_to_data_cleaning_b` / `not_implementable` are not created here.

### Rules
1. All derived features use the prefix `derived_`.
2. Source columns are never overwritten or modified.
3. Derived features are added to `df_analysis` (not to `df`).
4. TIMING_MAP is checked for each source column. Any source with
   `admission_labor` timing causes the derived feature to be flagged
   as ineligible for the pre-admission (Stage 1) horizon.
5. `derived_nulliparity_with_prior_cs`: a non-zero contradiction count
   triggers a data-quality warning.
6. **Source-contract safety.** Before it is used, every coded source is
   validated against its approved dictionary: `diabetes_type` ∈ {0,1,2,3,4,5},
   `any_PET_cat` ∈ {present, absent, not_documented}.
   An unexpected observed code/state **fails loud** — it is
   never silently treated as missing or as absence. A genuine NaN in a
   PET/`any_PET_cat` source leaves the derived result unresolved (NaN), never
   PET-negative.
7. **`DERIVED_FEATURE_CONTRACTS`** — one shared, narrowly-scoped object
   (formula inputs, rule, allowed non-missing output values, NaN-propagation
   semantics) consumed by C9, C10 validation, C10b documentation, and the
   tests. It carries no redundancy-family membership, no classification/stage,
   and no invented clinical plausibility bounds — those are separate metadata
   layers.
8. **Approved upstream-only sources.** The horizon-inheritance safeguard
   fails loud on any source column outside all three stage sets unless it is
   in `APPROVED_UPSTREAM_ONLY_SOURCES` — a source that merely cannot be
   stage-ranked is never silently assumed to be an earlier stage. Currently
   empty (2026-09-01, Decision 94): the PET `_cat` recodes are no longer
   upstream-only inputs — both are now approved `predictor_allowed`/
   Stage 1 standalone predictors and are properly stage-ranked via the
   ordinary `PREDICTOR_ALLOWED_COLS` path instead.
9. C9 prints a five-way reconciliation: planned / formula-implementable /
   conditionally-skipped / relocated / actually-materialized `DERIVED_VARS`.
""")

SC9_EXECUTE = code("eda-c-s09-execute", """
# ── TIMING_MAP safety check helper ────────────────────────────────────────────
def _check_timing(source_cols_str):
    cols = [c.strip() for c in source_cols_str.split(",") if c.strip()]
    timings = {c: TIMING_MAP.get(c, "unknown") for c in cols}
    has_admission = any(t == "admission_labor" for t in timings.values())
    return timings, has_admission


DERIVED_VARS = []     # populated below — only successfully derived columns
derived_meta = {}     # name -> {source_columns, timing, primary_model_eligible, ...}

_TIMING_WARNING = (
    "WARNING: one or more source columns have 'admission_labor' timing — "
    "this derived feature CANNOT be in the pre-admission (Stage 1) horizon."
)

# ── Approved coded-source dictionaries (source-contract safety, C9 rule 6) ────
# These validate the SOURCE columns before use; they are deliberately kept
# out of DERIVED_FEATURE_CONTRACTS (which is the derived-OUTPUT contract only).
_DIABETES_TYPE_APPROVED_CODES = {0, 1, 2, 3, 4, 5}          # confirmed diabetes_type code dictionary
_ANY_PET_CAT_APPROVED_STATES = {"present", "absent", "not_documented"}  # confirmed any_PET_cat state dictionary


def _validate_coded_source(series, approved, source_name, decision):
    # Fail loud if any non-missing observed value is outside `approved`.
    # Missing values are left untouched (allowed by the current contract).
    _obs = series.dropna()
    if _obs.dtype.kind in "biufc":
        _seen = set(int(v) if float(v).is_integer() else float(v) for v in _obs.unique())
    else:
        _seen = set(_obs.astype(str).unique())
    _unexpected = sorted(v for v in _seen if v not in approved)
    if _unexpected:
        raise ValueError(
            f"{source_name}: observed value(s) {_unexpected} are outside the approved "
            f"dictionary {sorted(approved)} ({decision}). An unrecognised code/state "
            "must NOT be silently treated as missing or as absence -- resolve the "
            "upstream data/contract before deriving features from this column."
        )


# ── DERIVED_FEATURE_CONTRACTS — single shared derived-OUTPUT contract ─────────
# Narrowly scoped by design: formula inputs; formula/rule; allowed non-missing
# output values; NaN-propagation semantics. NO redundancy-family membership, NO
# predictor classification/stage, NO invented clinical plausibility ranges --
# those live in separate authoritative metadata layers (derived_meta, the C8
# plan's redundancy_family_columns, DERIVED_REDUNDANCY_GROUPS, the classification
# snapshot). Consumed by C10 valid-value validation, C10b printed documentation,
# and the correction tests so all three agree on one expected output domain.
DERIVED_FEATURE_CONTRACTS = {
    "derived_prior_endo_surgery_procedure_status": {
        "formula_inputs": [
            "endometriosis_surgery",
            "endo_resection_ovarian_endometrioma_unilateral",
            "endo_resection_lesion",
            "endo_resection_adhesiolysis",
        ],
        "rule": (
            "no_prior_endo_surgery if endometriosis_surgery==0; "
            "prior_surgery_no_selected_procedure_documented if endometriosis_surgery==1 "
            "and all 3 selected procedure vars are observed and ==0; "
            "prior_surgery_with_selected_procedure_documented if endometriosis_surgery==1 "
            "and all 3 selected procedure vars are observed and any ==1"
        ),
        "allowed_values": {
            "no_prior_endo_surgery",
            "prior_surgery_no_selected_procedure_documented",
            "prior_surgery_with_selected_procedure_documented",
        },
        "nan_propagation": (
            "NaN when endometriosis_surgery is missing, or when endometriosis_surgery==1 "
            "and any selected-procedure source is missing (status unresolvable)"
        ),
        "runtime_status": "executable_now",
    },
    "derived_placental_dysfunction_proxy": {
        "formula_inputs": ["any_PET_cat", "IUGR"],
        "rule": (
            "1 if any_PET_cat=='present' OR IUGR==1; "
            "0 if any_PET_cat=='absent' AND IUGR==0; NaN otherwise"
        ),
        "allowed_values": {0.0, 1.0},
        "nan_propagation": (
            "NaN whenever PET status is not resolved to 'present'/'absent' and IUGR!=1; "
            "no fillna(0); a genuine any_PET_cat NaN never counts as PET-negative"
        ),
        "runtime_status": "conditional_skipped_unresolved_source",
    },
    "derived_nulliparity_with_prior_cs": {
        "formula_inputs": ["nulliparity", "S_P_CS"],
        "rule": (
            "1 if nulliparity==1 AND S_P_CS==1; 0 when both sources are observed and "
            "not both ==1"
        ),
        "allowed_values": {0.0, 1.0},
        "nan_propagation": "NaN when either nulliparity or S_P_CS is missing",
        "runtime_status": "review_only",
    },
    "derived_hypertension_pih_pet_spectrum": {
        "formula_inputs": ["PIH", "any_PET_cat", "SIPET", "HELLP", "eclampsia"],
        "rule": (
            "preeclampsia_spectrum if any_PET_cat=='present' OR SIPET==1 OR HELLP==1 "
            "OR eclampsia==1; otherwise, when PET spectrum status is resolved: "
            "pih_gestational_htn if PIH==1, no_hypertensive_disorder if PIH==0"
        ),
        "allowed_values": {
            "no_hypertensive_disorder",
            "pih_gestational_htn",
            "preeclampsia_spectrum",
        },
        "nan_propagation": (
            "NaN when any_PET_cat=='not_documented' and none of SIPET/HELLP/eclampsia "
            "is positive (spectrum unresolved); NaN when spectrum-negative but PIH is "
            "missing; a genuine any_PET_cat NaN never counts as spectrum-negative"
        ),
        "runtime_status": "executable_now",
    },
    "derived_diabetes_type_grouped": {
        "formula_inputs": ["diabetes_type"],
        "rule": "map {0->no_diabetes, 1/2/3->pregestational, 4->GDMA1, 5->GDMA2}",
        "allowed_values": {"no_diabetes", "pregestational", "GDMA1", "GDMA2"},
        "nan_propagation": (
            "NaN iff diabetes_type is missing; an unexpected non-missing code fails "
            "loud (never mapped to NaN)"
        ),
        "runtime_status": "executable_now",
    },
}

# ── APPROVED_UPSTREAM_ONLY_SOURCES (horizon-inheritance safeguard, C9 rule 8) ─
# A derived feature may read one of these as an input even though the column is
# intentionally not a standalone predictor -- it is used only as an upstream
# derivation input. Any OTHER source column that cannot be stage-ranked against
# the three stage sets fails the safeguard loud.
# Currently empty (2026-09-01, Decision 94): `any_PET_cat`/`severe_PET_cat`
# were the sole members while manual_review_pending, which put them outside
# all three stage sets (PREDICTOR_ALLOWED_COLS/SECONDARY_NEAR_DELIVERY_
# PREDICTOR_COLS/INTRAPARTUM_PREDICTOR_EXCLUDE_COLS) and required this
# explicit upstream-only exemption to avoid a false horizon-inheritance
# failure. Now approved predictor_allowed/Stage 1 standalone predictors in
# their own right, they are properly stage-ranked via PREDICTOR_ALLOWED_COLS
# like any other Stage-1 source -- they are no longer upstream-only sources
# and must not remain in this allowlist merely for historical reasons. The
# mechanism itself remains available for a future genuinely upstream-only
# source.
APPROVED_UPSTREAM_ONLY_SOURCES = set()

# Retired derived modeling representations are intentionally not created here:
# advanced-age binary, BMI category, endometriosis burden/resection counts,
# complex phenotype composite, broad surgical-history composite, and pregnancy
# complication count. Their source variables remain available where approved.

# ── 1. derived_prior_endo_surgery_procedure_status ───────────────────────────
_prior_endo_status_srcs = [
    "endometriosis_surgery",
    "endo_resection_ovarian_endometrioma_unilateral",
    "endo_resection_lesion",
    "endo_resection_adhesiolysis",
]
_prior_endo_status_missing = [c for c in _prior_endo_status_srcs if c not in df_analysis.columns]
if _prior_endo_status_missing:
    raise ValueError(
        "derived_prior_endo_surgery_procedure_status requires all source columns "
        f"to be present; missing: {_prior_endo_status_missing}"
    )

_prior_endo_proc_srcs = _prior_endo_status_srcs[1:]
_prior_endo_status = pd.Series(np.nan, index=df_analysis.index, dtype="object")
_no_prior_endo_surgery = df_analysis["endometriosis_surgery"] == 0
_prior_endo_surgery = df_analysis["endometriosis_surgery"] == 1
_selected_proc = df_analysis[_prior_endo_proc_srcs]
_selected_proc_complete = _selected_proc.notna().all(axis=1)
_selected_proc_all_zero = _selected_proc.eq(0).all(axis=1)
_selected_proc_any_positive = _selected_proc.eq(1).any(axis=1)

_prior_endo_status.loc[_no_prior_endo_surgery] = "no_prior_endo_surgery"
_prior_endo_status.loc[
    _prior_endo_surgery & _selected_proc_complete & _selected_proc_all_zero
] = "prior_surgery_no_selected_procedure_documented"
_prior_endo_status.loc[
    _prior_endo_surgery & _selected_proc_complete & _selected_proc_any_positive
] = "prior_surgery_with_selected_procedure_documented"

df_analysis["derived_prior_endo_surgery_procedure_status"] = _prior_endo_status
_t, _adm = _check_timing(", ".join(_prior_endo_status_srcs))
DERIVED_VARS.append("derived_prior_endo_surgery_procedure_status")
derived_meta["derived_prior_endo_surgery_procedure_status"] = {
    "source_columns": ", ".join(_prior_endo_status_srcs), "timing": "pre_pregnancy",
    "admission_labor_source": _adm, "primary_model_eligible": "yes" if not _adm else "review",
    "expected_type": "categorical", "leakage_risk": "no",
    "domain": "prior_endo_surgery",
    "analytical_role": "predictor_allowed",
    "note": (
        "Exploratory prior-endometriosis-surgery procedure-status representation "
        "using only a selected subset of reliably coded structured procedure "
        "variables; not a severity score, not a burden score, and not a claim "
        "that no selected procedure documented means no procedure occurred."
    ),
}
print("derived_prior_endo_surgery_procedure_status: "
      f"{df_analysis['derived_prior_endo_surgery_procedure_status'].value_counts(dropna=False).to_dict()}")
if _adm:
    print(_TIMING_WARNING)

# Classification-lineage: register derived_prior_endo_surgery_procedure_status (approved).
eda_c_classification_snapshot, eda_c_type_schema_snapshot = classification_lineage.register_feature(
    "derived_prior_endo_surgery_procedure_status", "categorical", "predictor_allowed",
    "Approved exploratory categorical alternative representation of prior endometriosis "
    "surgery and documentation of selected procedures; not a surgical severity or burden score.",
    df=df_analysis, classification_df=eda_c_classification_snapshot, type_schema_df=eda_c_type_schema_snapshot,
)

# ── 2. derived_endo_surgery_adhesion_status ──────────────────────────────
# Created upstream in Data Cleaning B (Section B5g,
# cleaning_b_part4_transformations_imputation_plan.py) -- deterministic
# semantic replacements are created in B, not EDA C. This column now reaches
# EDA C through the ordinary B_CREATED_ANALYSIS_VARS pathway (its
# classification/timing/domain/redundancy metadata come from B's feature
# dictionary / classification-lineage snapshot), like every other B-created
# replacement. No derivation code remains here.

# ── 3. derived_placental_dysfunction_proxy ───────────────────────────────────
_placental_proxy_srcs = ["any_PET_cat", "IUGR"]
_placental_proxy_missing = [c for c in _placental_proxy_srcs if c not in df_analysis.columns]
# any_PET_cat is now an approved predictor_allowed/Stage 1 standalone
# predictor (Decision 94, 2026-09-01) and is expected to always be present in
# ANALYSIS_VARS, the same as IUGR -- both sources are ordinary predictor_
# allowed columns now. Before Decision 94, any_PET_cat was a B-created column
# used only as an upstream derivation input (manual_review_pending, not yet
# a standalone candidate), so its absence was a known/expected/documented
# state handled by the graceful-skip branch below; that branch is retained
# defensively (any future reclassification back out of ANALYSIS_VARS would
# still be handled gracefully rather than crashing this cell), but is not
# expected to trigger under the current classification. Any OTHER missing
# source (e.g. IUGR, a raw predictor_allowed column that should always be
# present when ANALYSIS_VARS is built correctly) is NOT expected to ever be
# absent -- if it is, that signals a real upstream problem (unexpected
# reclassification, preprocessing regression, a typo in this source list,
# etc.) and must fail loudly rather than being silently folded into the same
# graceful skip as the known-pending case.
_placental_proxy_conditionally_available = {"any_PET_cat"}
_placental_proxy_unexpected_missing = [
    c for c in _placental_proxy_missing if c not in _placental_proxy_conditionally_available
]
if _placental_proxy_unexpected_missing:
    raise ValueError(
        "derived_placental_dysfunction_proxy: unexpected missing source column(s) "
        f"{_placental_proxy_unexpected_missing} -- these are not known "
        "conditionally-available B-created columns (only any_PET_cat is), so this "
        "likely indicates a genuine upstream bug (e.g. a raw predictor_allowed "
        "column was unexpectedly reclassified or dropped, or this source list is "
        "out of date). Investigate before proceeding; do not silently skip."
    )
if not _placental_proxy_missing:
    # B2 source-contract safety: any_PET_cat observed states must be within the
    # approved recode set. An unexpected string/state fails loud; a genuine NaN
    # is allowed and simply leaves the proxy unresolved (never PET-negative).
    _validate_coded_source(
        df_analysis["any_PET_cat"], _ANY_PET_CAT_APPROVED_STATES,
        "any_PET_cat (derived_placental_dysfunction_proxy input)", "approved any_PET_cat state dictionary",
    )
    _pet_present = df_analysis["any_PET_cat"].astype("string") == "present"
    _pet_absent = df_analysis["any_PET_cat"].astype("string") == "absent"
    _iugr_present = df_analysis["IUGR"] == 1
    _iugr_absent = df_analysis["IUGR"] == 0

    df_analysis["derived_placental_dysfunction_proxy"] = np.nan
    df_analysis.loc[_pet_present | _iugr_present, "derived_placental_dysfunction_proxy"] = 1.0
    df_analysis.loc[_pet_absent & _iugr_absent, "derived_placental_dysfunction_proxy"] = 0.0
    _t, _adm = _check_timing(", ".join(_placental_proxy_srcs))
    DERIVED_VARS.append("derived_placental_dysfunction_proxy")
    derived_meta["derived_placental_dysfunction_proxy"] = {
        "source_columns": ", ".join(_placental_proxy_srcs), "timing": "pregnancy",
        "redundancy_family_columns": "any_PET_cat, severe_PET_cat, IUGR, derived_hypertension_pih_pet_spectrum",
        "admission_labor_source": _adm, "primary_model_eligible": "yes" if not _adm else "review",
        "expected_type": "binary", "leakage_risk": "no",
        "domain": "placental_dysfunction",
        "analytical_role": "predictor_allowed",
        "note": (
            "Exploratory placenta-mediated complication proxy from PET status and IUGR; "
            "not a validated score, not a severity score, and not a missingness indicator. "
            "PET not_documented with IUGR=0 remains missing; no fillna(0)."
        ),
    }
    print("derived_placental_dysfunction_proxy: "
          f"{df_analysis['derived_placental_dysfunction_proxy'].value_counts(dropna=False).sort_index().to_dict()}")
    if _adm:
        print(_TIMING_WARNING)

    # Classification-lineage: register derived_placental_dysfunction_proxy (approved).
    # variable_type=binary -> n_categories is hardcoded to 2 by convention
    # regardless of missing values (missing is not a third category).
    eda_c_classification_snapshot, eda_c_type_schema_snapshot = classification_lineage.register_feature(
        "derived_placental_dysfunction_proxy", "binary", "predictor_allowed",
        "Exploratory pre-labor binary alternative representation of placental "
        "dysfunction using PET and IUGR; unresolved source status remains missing.",
        df=df_analysis, classification_df=eda_c_classification_snapshot, type_schema_df=eda_c_type_schema_snapshot,
    )
else:
    # 2026-08-16 correction: this used to hard-raise ValueError whenever
    # any_PET_cat was absent from df_analysis, killing the entire C9 cell
    # (including the unrelated derived_nulliparity_with_prior_cs sanity
    # check and the horizon-inheritance safeguard below, which never even
    # ran as a result). Since Decision 94 (2026-09-01), any_PET_cat is an
    # approved predictor_allowed/Stage 1 standalone predictor and is
    # expected to always be present, so this branch is not expected to
    # trigger under the current classification -- it is retained
    # defensively (a derived feature can never be more resolved than its
    # least-resolved source) rather than removed, matching the existing
    # derived_nulliparity_with_prior_cs pattern below. Not added to
    # DERIVED_VARS -- never silently treated as a modeling candidate.
    print(
        f"SKIP derived_placental_dysfunction_proxy: need {_placental_proxy_srcs}, "
        f"missing {_placental_proxy_missing}."
    )

# ── 9. parity_binary_0_vs_1plus — RETIRED ─────────────────────────────────────
# An earlier version of this pipeline derived it here as (P >= 1) because
# preprocessing's own nulliparity column disagreed with P and P was confirmed
# authoritative (Decision 11). That discordance is now resolved at the source:
# preprocessing derives nulliparity directly from P -- P==0 -> nulliparity=1,
# P>=1 -> nulliparity=0, invalid/missing P -> NaN. nulliparity is therefore now
# the exact complement of the old parity_binary_0_vs_1plus and IS the canonical,
# P-derived, authoritative binary parity predictor -- it already flows into
# df_analysis as a normal predictor_allowed column, so no derived variable is
# created for it here.
# Deriving a second, opposite-polarity column would just reintroduce the
# redundancy this migration removes. See eda_c/README.md for the retirement
# note and eda_c_part4_screening.py for the corresponding redundancy-family
# update (nulliparity is now the parity_history representative, not overridden
# to parity_binary_0_vs_1plus).

# ── 10. derived_nulliparity_with_prior_cs (sanity-check only) ────────────────
_sanity_srcs = ["nulliparity", "S_P_CS"]
_sanity_avail = [c for c in _sanity_srcs if c in df_analysis.columns]
if len(_sanity_avail) == 2:
    _contradiction_mask = (
        (df_analysis["nulliparity"] == 1) & (df_analysis["S_P_CS"] == 1)
    )
    _contradiction_n = int(_contradiction_mask.sum())
    df_analysis["derived_nulliparity_with_prior_cs"] = _contradiction_mask.astype(float)
    df_analysis.loc[
        df_analysis[_sanity_avail].isna().any(axis=1), "derived_nulliparity_with_prior_cs"
    ] = float("nan")
    DERIVED_VARS.append("derived_nulliparity_with_prior_cs")
    derived_meta["derived_nulliparity_with_prior_cs"] = {
        "source_columns": "nulliparity, S_P_CS", "timing": "pre_pregnancy",
        "admission_labor_source": False, "primary_model_eligible": "no",
        # analytical_role added 2026-09-01 (EDA C C12 correction, Part F) to
        # match this feature's own C8 plan entry -- lets any downstream
        # analytical_role-based check (e.g. eda_c_part4_screening.py's
        # _is_sanity_check_only) identify it correctly without relying on the
        # legacy primary_model_eligible field. Never reaches SCREEN_VARS or
        # candidate_df (excluded explicitly in C11), so this is defense-in-depth,
        # not a live behavior change.
        "analytical_role": "sanity_check_only",
        "expected_type": "binary",
        "note": "SANITY-CHECK ONLY — not a modeling candidate. Non-zero count = data error.",
    }
    print()
    print("derived_nulliparity_with_prior_cs (SANITY-CHECK ONLY):")
    print(f"  Contradiction count (nulliparity=1 AND S_P_CS=1): {_contradiction_n} "
          "observations (deliveries / rows)")
    if _contradiction_n > 0:
        print(f"  DATA QUALITY WARNING: {_contradiction_n} observations (deliveries / "
              "rows) are coded as nulliparous AND with a prior CS -- this is "
              "logically inconsistent. Flag for data review before modeling. "
              "(Count of rows, not inferred unique women.)")
    else:
        print("  OK: no logical contradictions detected.")
else:
    print(f"SKIP derived_nulliparity_with_prior_cs: need both {_sanity_srcs}, have {_sanity_avail}")

# ── 11. derived_hypertension_pih_pet_spectrum ────────────────────────────────
# 3-level grouped clinical representation of the
# hypertension family, defined from predefined clinical/source semantics
# -- NOT from target association. SIPET is included in the
# preeclampsia-spectrum level here (unlike the pregnancy_related_
# hypertensive_disorder umbrella, which deliberately excludes SIPET) because
# superimposed PET is, by its own established clinical definition, still a
# preeclampsia diagnosis. Rows where PET status is undocumented and not
# already confirmed positive via SIPET/HELLP/eclampsia are left missing, not
# guessed as level 0.
#
# Raw severe_PET/any_PET are not in Data Cleaning B's export (represented
# there by severe_PET_cat/any_PET_cat). This feature reads any_PET_cat from
# `df` (the full Data Cleaning B output, still in scope from Part 1 -- see
# eda_c_part1_setup_gate.py's `df = pd.read_excel(DATA_PATH)`), a pattern
# originally adopted because any_PET_cat was manual_review_pending and thus
# absent from the ANALYSIS_VARS-restricted `df_analysis`. Since Decision 94
# (2026-09-01), any_PET_cat is an approved predictor_allowed/Stage 1
# standalone predictor and IS present in `df_analysis` too (via the ordinary
# B_CREATED_ANALYSIS_VARS pathway) -- reading it from `df` here is no longer
# strictly necessary but yields identical values (df_analysis is a column
# subset of df) and is left unchanged to avoid an unnecessary code-path
# change alongside the classification correction. severe_PET_cat/any_PET_cat's
# values are a pure, already-implemented, unambiguous deterministic recode of
# severe_PET/any_PET ("present"/"absent"/"not_documented" for 1/0/NaN) -- no
# clinical interpretation is required to read them this way.
# B3: source_columns must be the columns the FORMULA actually reads, not padded
# with broader clinical-redundancy-family members. The assignment rule below
# reads PIH (df_analysis) and any_PET_cat / SIPET / HELLP / eclampsia only.
# mild_PET and severe_PET_cat are redundancy-family members (co-entry is
# review_within_modeling, not a HARD pair), NOT formula inputs -- recorded
# separately in redundancy_family_columns.
_htn_srcs = ["PIH", "any_PET_cat", "SIPET", "HELLP", "eclampsia"]
_htn_redundancy_family = [
    "pregnancy_related_hypertensive_disorder", "PIH", "mild_PET", "severe_PET_cat",
    "any_PET_cat", "SIPET", "HELLP", "eclampsia",
]
_htn_missing = (
    [c for c in ["PIH", "SIPET", "HELLP", "eclampsia"] if c not in df_analysis.columns]
    + [c for c in ["any_PET_cat"] if c not in df.columns]
)
if not _htn_missing:
    _any_pet_cat = df.loc[df_analysis.index, "any_PET_cat"]
    # B2 source-contract safety: any_PET_cat observed states must be within the
    # approved recode set. An unexpected state fails loud; a
    # genuine NaN is allowed and leaves the spectrum unresolved (-> NaN), never
    # silently treated as spectrum-negative.
    _validate_coded_source(
        _any_pet_cat, _ANY_PET_CAT_APPROVED_STATES,
        "any_PET_cat (derived_hypertension_pih_pet_spectrum input)", "approved any_PET_cat state dictionary",
    )
    _pet_spectrum_pos = (
        (_any_pet_cat == "present") | (df_analysis["SIPET"] == 1)
        | (df_analysis["HELLP"] == 1) | (df_analysis["eclampsia"] == 1)
    )
    _pet_spectrum_unresolved = (_any_pet_cat == "not_documented") & (~_pet_spectrum_pos)
    _htn_resolved = (~_pet_spectrum_pos) & (~_pet_spectrum_unresolved)
    _htn_grp = pd.Series(np.nan, index=df_analysis.index, dtype="object")
    _htn_grp.loc[_pet_spectrum_pos] = "preeclampsia_spectrum"
    _htn_grp.loc[_htn_resolved & (df_analysis["PIH"] == 1)] = "pih_gestational_htn"
    _htn_grp.loc[_htn_resolved & (df_analysis["PIH"] == 0)] = "no_hypertensive_disorder"
    df_analysis["derived_hypertension_pih_pet_spectrum"] = _htn_grp
    _t, _adm = _check_timing(", ".join(_htn_srcs))
    DERIVED_VARS.append("derived_hypertension_pih_pet_spectrum")
    derived_meta["derived_hypertension_pih_pet_spectrum"] = {
        "source_columns": ", ".join(_htn_srcs), "timing": "pregnancy",
        "redundancy_family_columns": ", ".join(_htn_redundancy_family),
        "admission_labor_source": _adm, "primary_model_eligible": "yes" if not _adm else "review",
        "expected_type": "categorical (3 states)", "leakage_risk": "no",
        "domain": "hypertension",
        "analytical_role": "predictor_allowed",
        "note": (
            "Predefined 3-level clinical grouping: no_hypertensive_disorder / "
            "pih_gestational_htn / preeclampsia_spectrum (any_PET_cat=='present', SIPET, "
            "HELLP, or eclampsia). Defined from predefined clinical/source semantics, "
            "not target association. FORMULA INPUTS: PIH, any_PET_cat, SIPET, HELLP, "
            "eclampsia. any_PET_cat is read from the full Data Cleaning B output "
            "(equivalent to df_analysis for this column since Decision 94, "
            "2026-09-01, approved it as a standalone predictor_allowed/Stage 1 "
            "predictor in its own right). mild_PET / severe_PET_cat / "
            "pregnancy_related_hypertensive_disorder are clinical-redundancy-family "
            "members only (see redundancy_family_columns), NOT formula inputs. Rows "
            "with any_PET_cat=='not_documented' and no other confirmed-positive subtype "
            "are left missing, not guessed. Co-entry with the individual hypertension "
            "source variables is review_within_modeling (hypertension_spectrum "
            "relationship group) -- NOT a HARD pair; this feature has no HARD "
            "co-entry pair in the C13 registry. See "
            "DERIVED_REDUNDANCY_GROUPS['hypertension_pih_pet_spectrum_representation']."
        ),
    }
    print("derived_hypertension_pih_pet_spectrum: "
          f"{df_analysis['derived_hypertension_pih_pet_spectrum'].value_counts(dropna=False).to_dict()}")
    if _adm:
        print(_TIMING_WARNING)

    eda_c_classification_snapshot, eda_c_type_schema_snapshot = classification_lineage.register_feature(
        "derived_hypertension_pih_pet_spectrum", "categorical", "predictor_allowed",
        "Approved 3-level grouped representation of the hypertension family "
        "(none / PIH-gestational-hypertension / preeclampsia-spectrum), defined "
        "from predefined clinical semantics, not target association. "
        "Formula inputs: PIH, any_PET_cat, SIPET, HELLP, eclampsia; any_PET_cat "
        "is an approved standalone predictor_allowed/Stage 1 predictor "
        "(Decision 94) and a direct formula input here, not merely an "
        "upstream-only source; rows with unresolved (not_documented) PET status "
        "are left missing, never silently treated as absent.",
        df=df_analysis, classification_df=eda_c_classification_snapshot, type_schema_df=eda_c_type_schema_snapshot,
    )
else:
    print(f"SKIP derived_hypertension_pih_pet_spectrum: need {_htn_srcs}, missing {_htn_missing}")

# ── 12. derived_diabetes_type_grouped ────────────────────────────────────────
# Confirmed code dictionary for diabetes_type --
# 0=no diabetes, 1=pregestational unspecified, 2=type 1, 3=type 2, 4=GDMA1,
# 5=GDMA2. Grouped on category-size/clinical-interpretability grounds only
# NOT target association: GDMA1 (N=39) and GDMA2 (N=18)
# are both individually adequate and clinically distinct, so kept split;
# codes 1/2/3 (pregestational diabetes) are combined -- each individually too
# sparse (N=2, N=2, N=4) to stand alone, and the combined pregestational
# category (N=8) remains clinically coherent (all represent diabetes present
# before pregnancy, as opposed to gestational-onset GDMA1/GDMA2).
_dt_srcs = ["diabetes_type"]
_dt_missing = [c for c in _dt_srcs if c not in df_analysis.columns]
if not _dt_missing:
    # B1 source-contract safety: every non-missing observed diabetes_type code
    # must be in the approved dictionary {0,1,2,3,4,5}. An
    # unexpected code FAILS LOUD -- it is never silently .map()-ed to NaN (which
    # would misrepresent an unknown code as "no grouped value / missing").
    _validate_coded_source(
        df_analysis["diabetes_type"], _DIABETES_TYPE_APPROVED_CODES,
        "diabetes_type (derived_diabetes_type_grouped input)", "confirmed diabetes_type code dictionary",
    )
    _dt_map = {0: "no_diabetes", 1: "pregestational", 2: "pregestational", 3: "pregestational",
               4: "GDMA1", 5: "GDMA2"}
    df_analysis["derived_diabetes_type_grouped"] = df_analysis["diabetes_type"].map(_dt_map)
    _t, _adm = _check_timing(", ".join(_dt_srcs))
    DERIVED_VARS.append("derived_diabetes_type_grouped")
    derived_meta["derived_diabetes_type_grouped"] = {
        "source_columns": ", ".join(_dt_srcs), "timing": "pregnancy",
        "admission_labor_source": _adm, "primary_model_eligible": "yes" if not _adm else "review",
        "expected_type": "categorical (4 states)", "leakage_risk": "no",
        "domain": "diabetes",
        "analytical_role": "predictor_allowed",
        "note": (
            "Deterministic 4-level clinical grouping of diabetes_type's confirmed code "
            "dictionary: no_diabetes (code 0) / pregestational (codes 1,2,3) / GDMA1 "
            "(code 4) / GDMA2 (code 5). Chosen on category-size and clinical-"
            "interpretability grounds, not target association. HARD co-entry pair "
            "with diabetes_type ONLY (C13 registry: deterministic coarsening). "
            "gestational_diabetes is review_within_modeling, NOT a HARD pair. See "
            "DERIVED_REDUNDANCY_GROUPS['diabetes_representation']."
        ),
    }
    print("derived_diabetes_type_grouped: "
          f"{df_analysis['derived_diabetes_type_grouped'].value_counts(dropna=False).to_dict()}")
    if _adm:
        print(_TIMING_WARNING)

    eda_c_classification_snapshot, eda_c_type_schema_snapshot = classification_lineage.register_feature(
        "derived_diabetes_type_grouped", "categorical", "predictor_allowed",
        "Approved 4-level grouped representation of diabetes_type's confirmed code "
        "dictionary (no_diabetes / pregestational / GDMA1 / GDMA2), chosen on "
        "category-size and clinical-interpretability grounds, not "
        "target association.",
        df=df_analysis, classification_df=eda_c_classification_snapshot, type_schema_df=eda_c_type_schema_snapshot,
    )
else:
    print(f"SKIP derived_diabetes_type_grouped: need {_dt_srcs}, missing {_dt_missing}")

# ── Summary ────────────────────────────────────────────────────────────────────
print()
print(f"Feature engineering complete: {len(DERIVED_VARS)} derived columns added to df_analysis")
print(f"df_analysis shape: {df_analysis.shape[0]} rows x {df_analysis.shape[1]} cols")
print()
_feat_summary = []
for _dv in DERIVED_VARS:
    _m = derived_meta[_dv]
    _n_valid = int(df_analysis[_dv].notna().sum())
    _n_miss = int(df_analysis[_dv].isna().sum())
    _miss_pct = round(_n_miss / len(df_analysis) * 100, 1)
    _feat_summary.append({
        "derived_feature": _dv,
        "source_columns": _m["source_columns"],
        "timing": _m["timing"],
        "primary_model_eligible": _m["primary_model_eligible"],
        "N_valid": _n_valid,
        "missing_%": _miss_pct,
    })
print(pd.DataFrame(_feat_summary).to_string(index=False))

# ── Five-way plan <-> materialization reconciliation ─────────────────────────
# planned / formula-implementable / conditionally-skipped / relocated /
# actually-materialized DERIVED_VARS. `derived_placental_dysfunction_proxy` is
# formula-implementable but is NOT reported as a materialized DERIVED_VARS
# member while its approved upstream source (any_PET_cat) is unavailable to the
# staged analysis universe.
_plan_by_name = {r["new_feature_name"]: r for r in _FEATURE_PLAN}
_planned = [r["new_feature_name"] for r in _FEATURE_PLAN]
_formula_implementable = [n for n, r in _plan_by_name.items() if r["implementable"] == "yes"]
_conditionally_skipped = [
    n for n, r in _plan_by_name.items()
    if r["runtime_availability"] == "conditional_skipped_unresolved_source"
    and n not in DERIVED_VARS
]
_relocated = [
    n for n, r in _plan_by_name.items()
    if r["runtime_availability"] == "relocated_to_data_cleaning_b"
]
_materialized = list(DERIVED_VARS)

print()
print("C9 five-way plan <-> materialization reconciliation:")
print(f"  planned features                  ({len(_planned)}): {_planned}")
print(f"  formula-implementable             ({len(_formula_implementable)}): {_formula_implementable}")
print(f"  conditionally skipped this run     ({len(_conditionally_skipped)}): {_conditionally_skipped}")
print(f"  relocated to Data Cleaning B       ({len(_relocated)}): {_relocated}")
print(f"  actually materialized DERIVED_VARS ({len(_materialized)}): {_materialized}")

_recon_errors = []
# every executable_now / review_only plan row must have materialized
for _n, _r in _plan_by_name.items():
    if _r["runtime_availability"] in ("executable_now", "review_only") and _n not in DERIVED_VARS:
        _recon_errors.append(
            f"plan row {_n!r} is {_r['runtime_availability']} but did not materialize in DERIVED_VARS"
        )
# every materialized column must have a plan row
for _n in DERIVED_VARS:
    if _n not in _plan_by_name:
        _recon_errors.append(f"materialized derived column {_n!r} has no C8 plan row")
# a conditionally-skipped feature that DID materialize is not an error, but must be reported
for _n, _r in _plan_by_name.items():
    if _r["runtime_availability"] == "conditional_skipped_unresolved_source" and _n in DERIVED_VARS:
        print(f"  NOTE: {_n} was planned as conditionally-skipped but its upstream source "
              "is now available and it materialized -- consider updating its C8 "
              "runtime_availability to executable_now.")
if _recon_errors:
    raise AssertionError(
        "C9 plan<->materialization reconciliation FAILED: " + "; ".join(_recon_errors)
    )
print("  reconciliation OK: a conditional skip is expected, not a failure.")

# ── Structural safeguard: horizon inheritance ─────────────────────────────────
# A derived feature must never be labeled with an earlier/less-restrictive
# prediction horizon than any of its source columns -- e.g. a feature built
# from a Stage-2 (secondary_near_delivery_predictor) or Stage-3
# (intrapartum_predictor_exclude_from_prelabor_model) source column must
# itself be at least that late, never silently mislabeled Stage 1
# (predictor_allowed). Each implementable derived feature's hardcoded
# "analytical_role" above is checked here against the actual current
# classification of its source columns, computed live from
# PREDICTOR_ALLOWED_COLS/SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS/
# INTRAPARTUM_PREDICTOR_EXCLUDE_COLS (Part 1) -- this does not change any
# label, it only fails loudly if a future source-column reclassification
# silently invalidates the hardcoded "analytical_role" above.
_STAGE_RANK = {
    "predictor_allowed": 1,
    "secondary_near_delivery_predictor": 2,
    "intrapartum_predictor_exclude_from_prelabor_model": 3,
}
_horizon_errors = []
_unranked_unapproved = []      # B5: sources that cannot be stage-ranked AND are not approved upstream-only
for _dv in DERIVED_VARS:
    _m = derived_meta[_dv]
    _declared_role = _m.get("analytical_role")
    if _declared_role is None:
        continue  # sanity-check-only features carry no analytical_role (never a modeling candidate)
    _src_cols = [c.strip() for c in _m["source_columns"].split(",") if c.strip()]
    _src_ranks = {}
    for _sc in _src_cols:
        if _sc in PREDICTOR_ALLOWED_COLS:
            _src_ranks[_sc] = _STAGE_RANK["predictor_allowed"]
        elif _sc in SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS:
            _src_ranks[_sc] = _STAGE_RANK["secondary_near_delivery_predictor"]
        elif _sc in INTRAPARTUM_PREDICTOR_EXCLUDE_COLS:
            _src_ranks[_sc] = _STAGE_RANK["intrapartum_predictor_exclude_from_prelabor_model"]
        elif _sc in APPROVED_UPSTREAM_ONLY_SOURCES:
            # B5: explicitly-registered upstream-only derivation input
            # (not a standalone candidate), so it is legitimately not
            # stage-rankable -- skip it, do NOT infer an earlier stage from
            # the fact that it cannot be ranked.
            continue
        else:
            # B5: any OTHER source outside all three stage sets is NOT silently
            # tolerated -- a future upstream-only source must be added to
            # APPROVED_UPSTREAM_ONLY_SOURCES (with a documented rationale) or the
            # derivation must be revisited. Never assume an earlier stage.
            _unranked_unapproved.append(f"{_dv} <- {_sc}")
    if not _src_ranks:
        continue
    _max_src_rank = max(_src_ranks.values())
    _declared_rank = _STAGE_RANK.get(_declared_role)
    if _declared_rank is not None and _declared_rank < _max_src_rank:
        _latest_src = [c for c, r in _src_ranks.items() if r == _max_src_rank]
        _horizon_errors.append(
            f"{_dv}: declared analytical_role={_declared_role!r} is earlier than its "
            f"latest-horizon source column(s) {_latest_src} (source rank {_max_src_rank})"
        )
if _unranked_unapproved:
    raise AssertionError(
        "Derived-feature horizon-inheritance check failed -- source column(s) are "
        "outside all three stage sets and are not registered in "
        "APPROVED_UPSTREAM_ONLY_SOURCES. Register the approved upstream-only source "
        "(with a decision reference) or revisit the derivation; a source that merely "
        "cannot be stage-ranked must never be assumed to be an earlier stage: "
        + "; ".join(_unranked_unapproved)
    )
if _horizon_errors:
    raise AssertionError(
        "Derived-feature horizon-inheritance check failed -- a derived feature's "
        "declared analytical_role must never be earlier than its latest source "
        "column's stage: " + "; ".join(_horizon_errors)
    )
print()
print("Derived-feature horizon-inheritance check passed: every derived feature's "
      "declared analytical_role is consistent with its source columns' current stage; "
      f"approved upstream-only sources used: {sorted(APPROVED_UPSTREAM_ONLY_SOURCES)}.")
""")


EDA_C_PART3_CELLS = [
    SC8_HEADER,
    SC8_PLAN,
    SC9_HEADER,
    SC9_EXECUTE,
]


if __name__ == "__main__":
    print(f"EDA C Part 3 cells defined: {len(EDA_C_PART3_CELLS)}")

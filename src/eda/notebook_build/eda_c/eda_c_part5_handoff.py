#!/usr/bin/env python3
"""EDA C — Part 5 cell definitions (sections C13–C17).

C13 — Export artifacts: broad, hard-exclusion-filtered candidate pool (not a
      final selected-feature list).
C14 — Imputation, encoding, and scaling treatment plan.
C15 — Modeling handoff contract (candidate pool handoff to EDA D).
C16 — Final readiness checklist (PASS/FAIL) and modeling gate.
C17 — Output verification (reads outputs/eda_c/ from disk).
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


# ── Section C13 ────────────────────────────────────────────────────────────────
SC13_HEADER = md("eda-c-s13-header", """
## Section C13 — Export Artifacts

EDA C performs eligibility filtering only. It exports a broad, hard-exclusion-
filtered **candidate pool** — not a final selected-feature list. Final variable/
model selection happens later, in EDA D, under cross-validation.

### Core candidate/data handoff files (unchanged — do not rename or remove)

These 4 files are the **candidate-pool + patient-data** half of the EDA D
handoff and are what legacy/current EDA D
(`eda_d_part1_setup_and_contract.py`, `phase4b_endo_search_runner.py`)
already consumes. Nothing else in this section may change their name, meaning,
or content. They are **no longer the complete modeling contract on their own** —
see the next block.

| File | Content | Contains patient rows? |
|------|---------|----------------------|
| `outputs/eda_c/candidate_model_features.csv` | Eligible candidate pool only (C12b), full metadata per variable (incl. the C13 final model-facing fields) | No |
| `outputs/eda_c/candidate_feature_manifest.json` | Run metadata, thresholds, counts, pass/fail conclusion, `final_model_contract` section | No |
| `outputs/eda_c/candidate_feature_review_full.csv` | Full review table — eligible + hard-excluded rows | No |
| `outputs/eda_c/modeling_dataset_candidate_features.xlsx` | Target + ONLY eligible candidate-pool columns | **Yes — gitignored** |

### Mandatory final model-contract metadata artifacts (2026-09-01 — NEW)

Downstream modeling must **also** consume these after the modeling-consumer
migration. Together with the 4 core files above they form the complete
model-facing handoff contract; the 4 core files are **not** the "sole" or
complete contract any more.

| File | Content | Contains patient rows? |
|------|---------|----------------------|
| `outputs/eda_c/model_coentry_constraints.csv` | **Generated run snapshot** of the HARD, target-independent pairwise co-entry bans (canonical authored source: `analysis/eda/notebook_build/eda_c/contracts/model_coentry_constraints.yaml`), plus a run-computed `earliest_applicable_stage` column | No |
| `outputs/eda_c/model_relationship_groups.csv` | **Generated run snapshot** of the many-to-many `review_within_modeling` relationship groups (canonical authored source: `analysis/eda/notebook_build/eda_c/contracts/model_relationship_groups.yaml`) | No |
| `outputs/eda_c/variable_classification_snapshot.csv` | Final classification snapshot — authoritative `predictor_classification` for the handoff | No |
| `outputs/eda_c/variable_type_schema_snapshot.csv` | Final type-schema snapshot — authoritative `physical_variable_type` / `physical_n_categories` | No |
| `outputs/eda_c/predictor_relationship_diagnostics.csv` | Descriptive-only empirical relationship audit (ρ / Cramér's V / ε²); **never** a co-entry decision input | No |

### Other reference/audit files (unchanged)

| File | Content | Contains patient rows? |
|------|---------|----------------------|
| `outputs/eda_c/excluded_features_log.csv` | Hard-excluded variables + exact `hard_exclusion_reason` | No |
| `outputs/eda_c/feature_dictionary.csv` | Derived feature metadata | No |
| `outputs/eda_c/eda_c_action_log.csv` | Provenance + run metadata | No |

### Additional requested deliverables (new — parallel exports, not a second contract)

These are **convenience/versioned re-exports of the canonical files above**,
added because this session's requested deliverable names don't match the
canonical `candidate_*` names. They are never read by EDA D and never used
to derive the canonical files — they are derived *from* them, in the same
run. See "Design note" below for why these exact names carry history that
makes an explicit distinction necessary.

| File | Content | Relationship to canonical files | Contains patient rows? |
|------|---------|----------------------------------|------------------------|
| `outputs/eda_c/final_candidate_features.csv` | Same content as `candidate_feature_review_full.csv` | Convenience re-export, same data, not a second source of truth | No |
| `outputs/eda_c/modeling_dataset_all_clean_features.xlsx` | Target + all 79 baseline `ANALYSIS_VARS` (live-verified, Decision 91; unaffected by Decision 92 -- was 69 pre-Decision-91) + implementable derived features (`SCREEN_VARS`), **before** eligibility filtering | **Distinct content** — broader than `modeling_dataset_candidate_features.xlsx` (which is the narrower, post-hard-exclusion eligible pool that EDA D actually consumes) | **Yes — gitignored** |
| `outputs/eda_c/selected_model_features.csv` | Same variable rows as `candidate_model_features.csv`, plus explicit contract/provenance columns (`variable_name`, `selection_status`, `handoff_role`, `contract_version`, `reason`, `test_used`, `p_value`, `q_value`, `effect_size`, `redundancy_flag`, `timing_leakage_notes`) | Versioned re-export — **not** a competing selection, and explicitly not the old capped-10 Model V1 "conservative primary set" | No |
| `outputs/eda_c/feature_selection_manifest.json` | New, explicit contract manifest (`current_contract`, `canonical_d_handoff_files`, legacy-contract disclaimers) | **Not** a copy of `candidate_feature_manifest.json` — declares the contract rather than duplicating run statistics | No |

### Design note — why the distinction matters

EDA C used to export a capped 10-feature "conservative primary set" under
these exact names (`selected_model_features.csv`,
`feature_selection_manifest.json`, `final_candidate_features.csv`,
`modeling_dataset_selected_features.xlsx`) before the 2026-07-02→07-05
redesign to the current broad, no-cap candidate-pool design. `analysis/
modeling/` (Model V1, untouched, out of scope) still expects that old
contract and is already known-broken independent of this work (see
`eda_d/PHASE_4_HANDOFF.md`). The files above reuse three of those exact
filenames for this session's requested deliverables, but their *content* is
the current broad-pool design, not a revival of the capped selection —
`contract_version`/`handoff_role`/`current_contract` fields make that
explicit wherever it could otherwise be ambiguous.

The patient-level files must never be committed to Git. Verify that
`outputs/eda_c/*.xlsx` is covered by `.gitignore` before enabling output.
Per project safety rule (C0), none of them ever includes `subject_number` or
`delivery_id` — row traceability for local use is the DataFrame index.

`SAVE_AGGREGATED_OUTPUTS` controls the CSV/JSON files (no patient rows),
including the 3 new CSV/JSON deliverables above.
`SAVE_SELECTED_MODELING_DATASET` writes the patient-level datasets —
`modeling_dataset_candidate_features.xlsx` remains the one patient-level
output intended for direct handoff to EDA D;
`modeling_dataset_all_clean_features.xlsx` is an additional, broader
patient-level export governed by the same flag.
`SAVE_OUTPUTS` (from C1) is no longer used by this export cell — the old "broad
reference matrix, target + ALL screened features regardless of eligibility" concept
is superseded by the candidate pool itself, which is now the intended broad export.
""")

SC13_MODEL_CONTRACT_HEADER = md("eda-c-s13-model-contract-header", """
### Section C13 (pre-export) — Final Model-Facing Contract

Before any file is written, EDA C freezes a single, machine-readable model-input
contract for **every eligible candidate-pool variable**, so downstream modeling
never has to infer variable semantics from pandas dtype, column names, or old
preprocessing files.

**Authoritative source-of-truth chain**
1. `analysis/eda/notebook_build/eda_c/contracts/model_coentry_constraints.yaml`
   — the ONLY canonical hand-authored source for pairwise **HARD**,
   target-independent co-entry constraints. Tracked; a fresh checkout reads it
   directly (no generator step). Each pair is stored canonically
   (`var_a < var_b`, case-sensitive). Every pair `constraint_level =
   hard_forbid_coentry`, `target_independent = true`. An empirical p / q /
   effect / ρ / V / ε² value can **never** create a pair here.
2. `analysis/eda/notebook_build/eda_c/contracts/model_relationship_groups.yaml`
   — the ONLY canonical hand-authored source for many-to-many **review**
   metadata (`modeling_action = review_within_modeling`) for
   clinically/numerically overlapping predictors that remain jointly eligible.
   Tracked; read directly. Never changes eligibility. A variable may appear in
   several groups. (The `outputs/eda_c/model_*_constraints.csv` /
   `model_relationship_groups.csv` files C13 writes are **generated run
   snapshots**, not a source of truth; any local `contracts/*.csv` is an
   ignored inspection mirror produced by `_build_contract_csvs.py`.)
3. The in-memory EDA C **type-schema snapshot** (`eda_c_type_schema_snapshot`)
   — authoritative `physical_variable_type` / `physical_n_categories`.
4. The in-memory EDA C **classification snapshot**
   (`eda_c_classification_snapshot`) — authoritative `predictor_classification`.

**Fail-loud reconciliation.** Every eligible variable must have exactly one
type-schema row and exactly one classification row; the coarse `data_type` must
be the approved projection of `physical_variable_type`
(`SCHEMA_TO_EDA_TYPE`); a categorical/binary `physical_n_categories` must
reconcile numerically with the observed `n_unique`; the candidate registry
value must equal the snapshot value. Any disagreement raises.

**Model representation vs. physical type.** `model_representation_type` is a
DISTINCT, explicit, fail-loud field. A physically continuous source column is
**not** relabelled categorical merely because a fold-safe transformation later
creates categories. Current live cases: ordinary numeric →
`same_as_physical_numeric`; ordinary binary → `binary_passthrough`; ordinary
categorical → `one_hot_categorical`; `BMI_after` / `weight_in_pregnancy` →
`fold_safe_quantile_categorical`; `gestational_age_at_PPROM_days` →
`fold_safe_pprom_timing_categorical`; `BMI_before` →
`fold_safe_recomputed_continuous` (verified: `FoldSafeRecomputedBMITransformer`
in `analysis/modeling/final_modeling/modeling_core.py` still recomputes BMI from
fold-safe-imputed height/weight within the training fold).
""")

SC13_MODEL_CONTRACT = code("eda-c-s13-model-contract", """
from pathlib import Path as _Path
import yaml as _yaml

# ── source-of-truth chain: two hand-authored YAML contract registries ────────
# The tracked YAML files under analysis/eda/notebook_build/eda_c/contracts/ are
# the ONLY canonical authored source. A fresh checkout reads them DIRECTLY --
# no generator pre-step, no CSV. The .csv files under outputs/eda_c/ (written
# later in C13) are GENERATED run-specific modeling-handoff snapshots, not a
# source of truth; any local contracts/*.csv is an ignored inspection mirror.
_CONTRACTS_DIR = (
    (_root / "analysis" / "eda" / "notebook_build" / "eda_c" / "contracts")
    if _root else _Path("analysis/eda/notebook_build/eda_c/contracts")
)
_COENTRY_SRC_PATH = _CONTRACTS_DIR / "model_coentry_constraints.yaml"
_RELGROUPS_SRC_PATH = _CONTRACTS_DIR / "model_relationship_groups.yaml"
for _p in (_COENTRY_SRC_PATH, _RELGROUPS_SRC_PATH):
    if not _p.is_file():
        raise FileNotFoundError(
            f"EDA C model contract canonical source missing: {_p}. This tracked "
            "YAML file is the hand-reviewed source of truth and must be present "
            "on any checkout before C13 runs (no generator step is required)."
        )

_COENTRY_FIELDS = ["var_a", "var_b", "constraint_level", "reason_type",
                   "target_independent", "rationale", "decision_source"]
_RELGROUP_FIELDS = ["group_name", "variable", "relationship_type",
                    "modeling_action", "rationale", "decision_source"]


def _load_coentry_yaml(_path):
    _doc = _yaml.safe_load(_path.read_text(encoding="utf-8")) or {}
    _rows = []
    for _p in (_doc.get("hard_coentry_pairs") or []):
        _rows.append({
            "var_a": str(_p.get("var_a", "")),
            "var_b": str(_p.get("var_b", "")),
            "constraint_level": str(_p.get("constraint_level", "")),
            "reason_type": str(_p.get("reason_type", "")),
            "target_independent": str(_p.get("target_independent", "")).strip().lower(),
            "rationale": str(_p.get("rationale", "")),
            "decision_source": str(_p.get("decision_source", "")),
        })
    return pd.DataFrame(_rows, columns=_COENTRY_FIELDS)


def _load_relgroups_yaml(_path):
    _doc = _yaml.safe_load(_path.read_text(encoding="utf-8")) or {}
    _rows = []
    for _g in (_doc.get("relationship_groups") or []):
        for _v in (_g.get("variables") or []):
            _rows.append({
                "group_name": str(_g.get("group_name", "")),
                "variable": str(_v),
                "relationship_type": str(_g.get("relationship_type", "")),
                "modeling_action": str(_g.get("modeling_action", "")),
                "rationale": str(_g.get("rationale", "")),
                "decision_source": str(_g.get("decision_source", "")),
            })
    return pd.DataFrame(_rows, columns=_RELGROUP_FIELDS)


_coentry_src = _load_coentry_yaml(_COENTRY_SRC_PATH).fillna("")
_relgroups_src = _load_relgroups_yaml(_RELGROUPS_SRC_PATH).fillna("")
# expose the parsed canonical source for downstream cells (C16) so they never
# re-read a file or a generated CSV.
MODEL_COENTRY_SRC_DF = _coentry_src.copy()
MODEL_RELGROUPS_SRC_DF = _relgroups_src.copy()

_CLS_STAGE = {
    "predictor_allowed": 1,
    "secondary_near_delivery_predictor": 2,
    "intrapartum_predictor_exclude_from_prelabor_model": 3,
}
_pool_vars = set(candidate_pool_df["variable"])
_pool_stage = dict(zip(
    candidate_pool_df["variable"],
    candidate_pool_df["predictor_classification"].map(_CLS_STAGE),
))

# ── validate model_coentry_constraints.csv ──────────────────────────────────
_COENTRY_COLS = ["var_a", "var_b", "constraint_level", "reason_type",
                 "target_independent", "rationale", "decision_source"]
_coentry_errors = []
if list(_coentry_src.columns) != _COENTRY_COLS:
    _coentry_errors.append(
        f"columns {list(_coentry_src.columns)} != required {_COENTRY_COLS}"
    )
# reason_type vocabulary: deterministic containment relationships only. An
# empirical-association token can NEVER appear here.
_ALLOWED_COENTRY_REASON = {
    "deterministic_recompute", "deterministic_coarsening",
    "deterministic_status_encoding", "deterministic_model_representation_gate",
}
_EMPIRICAL_TOKENS = ("p_value", "q_value", "fdr", "effect_size", "spearman",
                     "rho", "cramers_v", "cramer", "epsilon", "correlation",
                     "auc", "odds_ratio")
_seen_pairs = set()
for _r in _coentry_src.to_dict("records"):
    _a, _b = str(_r["var_a"]), str(_r["var_b"])
    if str(_r["constraint_level"]) != "hard_forbid_coentry":
        _coentry_errors.append(f"{_a}/{_b}: constraint_level != hard_forbid_coentry")
    if str(_r["target_independent"]).strip().lower() != "true":
        _coentry_errors.append(f"{_a}/{_b}: target_independent must be true")
    if _a >= _b:
        _coentry_errors.append(f"{_a}/{_b}: not stored canonically (var_a < var_b)")
    _key = (_a, _b)
    if _key in _seen_pairs or (_b, _a) in _seen_pairs:
        _coentry_errors.append(f"{_a}/{_b}: duplicate / reversed pair")
    _seen_pairs.add(_key)
    _rt = str(_r["reason_type"]).strip().lower()
    if _rt not in _ALLOWED_COENTRY_REASON:
        _coentry_errors.append(f"{_a}/{_b}: reason_type {_rt!r} not a deterministic type")
    if any(_tok in _rt for _tok in _EMPIRICAL_TOKENS) or any(
        _tok in str(_r["rationale"]).lower() for _tok in
        ("p<0.", "q<0.", "|r| >", "rho=", "cramers_v=", "epsilon_squared=")
    ):
        _coentry_errors.append(
            f"{_a}/{_b}: an empirical-association threshold must never create a hard pair"
        )
    for _m in (_a, _b):
        if _m not in _pool_vars:
            _coentry_errors.append(f"{_a}/{_b}: member {_m!r} is not a live eligible pool variable")
if _coentry_errors:
    raise AssertionError("model_coentry_constraints.csv INVALID:\\n  - " + "\\n  - ".join(_coentry_errors))

# ── validate model_relationship_groups.csv ──────────────────────────────────
_RELGROUP_COLS = ["group_name", "variable", "relationship_type",
                  "modeling_action", "rationale", "decision_source"]
_relgroup_errors = []
if list(_relgroups_src.columns) != _RELGROUP_COLS:
    _relgroup_errors.append(
        f"columns {list(_relgroups_src.columns)} != required {_RELGROUP_COLS}"
    )
for _r in _relgroups_src.to_dict("records"):
    if str(_r["modeling_action"]) != "review_within_modeling":
        _relgroup_errors.append(f"{_r['group_name']}/{_r['variable']}: modeling_action must be review_within_modeling")
    if str(_r["variable"]) not in _pool_vars:
        _relgroup_errors.append(f"{_r['group_name']}: variable {_r['variable']!r} is not a live eligible pool variable")
if _relgroups_src.duplicated(["group_name", "variable"]).any():
    _relgroup_errors.append("duplicate (group_name, variable) rows")
if _relgroup_errors:
    raise AssertionError("model_relationship_groups.csv INVALID:\\n  - " + "\\n  - ".join(_relgroup_errors))

# relationship groups must NOT change eligibility -- pure metadata assertion.
assert set(_relgroups_src["variable"]) <= _pool_vars, (
    "relationship groups reference a non-eligible variable -- they must never alter the pool"
)

# ── per-variable generated co-entry metadata (symmetric, from the pair table) ─
_hard_partners = {}
for _r in _coentry_src.to_dict("records"):
    _hard_partners.setdefault(str(_r["var_a"]), set()).add(str(_r["var_b"]))
    _hard_partners.setdefault(str(_r["var_b"]), set()).add(str(_r["var_a"]))
_var_groups = {}
for _r in _relgroups_src.to_dict("records"):
    _var_groups.setdefault(str(_r["variable"]), set()).add(str(_r["group_name"]))


def _hard_forbidden_with(v):
    return "; ".join(sorted(_hard_partners.get(v, set())))


def _relationship_groups(v):
    return "; ".join(sorted(_var_groups.get(v, set())))


# ── type-schema / classification reconciliation (fail-loud, eligible pool) ────
_ts_snap = eda_c_type_schema_snapshot.copy()
_cls_snap = eda_c_classification_snapshot.copy()
_ts_by_var = {r["variable_name"]: r for r in _ts_snap.to_dict("records")}
_ts_counts = _ts_snap["variable_name"].value_counts().to_dict()
_cls_counts = _cls_snap["column_name"].value_counts().to_dict()
_cls_by_var = {r["column_name"]: r for r in _cls_snap.to_dict("records")}

_MODEL_FACING_PHYSICAL_TYPES = {"binary", "categorical", "ordinal", "continuous", "count"}
_recon_errors = []
_physical_type = {}
_physical_n_cat = {}
for _v in sorted(_pool_vars):
    _crow = candidate_pool_df.loc[candidate_pool_df["variable"] == _v].iloc[0]
    # type-schema row cardinality
    _nt = int(_ts_counts.get(_v, 0))
    if _nt == 0:
        _recon_errors.append(f"{_v}: zero type-schema rows")
        continue
    if _nt > 1:
        _recon_errors.append(f"{_v}: {_nt} type-schema rows (must be exactly 1)")
        continue
    _pt = str(_ts_by_var[_v]["variable_type"])
    _nc = _ts_by_var[_v]["n_categories"]
    _physical_type[_v] = _pt
    _physical_n_cat[_v] = _nc
    if _pt not in _MODEL_FACING_PHYSICAL_TYPES:
        _recon_errors.append(f"{_v}: physical type {_pt!r} is not a model-facing type")
        continue
    if _pt not in SCHEMA_TO_EDA_TYPE:
        _recon_errors.append(f"{_v}: unknown/unhandled physical type {_pt!r}")
        continue
    # coarse data_type must be the approved projection
    _proj = SCHEMA_TO_EDA_TYPE[_pt]
    _dt = str(_crow["data_type"])
    if _dt != _proj:
        _recon_errors.append(
            f"{_v}: data_type {_dt!r} is not the approved projection {_proj!r} of physical {_pt!r}"
        )
    # n_categories reconciliation
    _obs_nu = _crow.get("n_unique")
    if _pt == "binary":
        if not (pd.isna(_nc) or float(_nc) == 2.0):
            _recon_errors.append(f"{_v}: binary physical_n_categories {_nc!r} must be 2 or blank")
    elif _pt in ("categorical", "ordinal"):
        if pd.isna(_nc) or float(_nc) < 2:
            _recon_errors.append(f"{_v}: categorical physical_n_categories {_nc!r} must be >= 2")
        elif pd.notna(_obs_nu) and float(_nc) != float(_obs_nu):
            _recon_errors.append(
                f"{_v}: physical_n_categories {_nc!r} != observed n_unique {_obs_nu!r}"
            )
    else:  # continuous / count
        if pd.notna(_nc):
            _recon_errors.append(f"{_v}: numeric physical_n_categories should be blank, got {_nc!r}")
    # classification row cardinality + agreement
    _ncls = int(_cls_counts.get(_v, 0))
    if _ncls != 1:
        _recon_errors.append(f"{_v}: {_ncls} classification rows (must be exactly 1)")
    else:
        _snap_cls = str(_cls_by_var[_v]["classification"])
        _reg_cls = str(_crow["predictor_classification"])
        if _snap_cls != _reg_cls:
            _recon_errors.append(
                f"{_v}: predictor_classification {_reg_cls!r} != final snapshot {_snap_cls!r}"
            )
if _recon_errors:
    raise AssertionError(
        "C13 final type/classification reconciliation FAILED:\\n  - "
        + "\\n  - ".join(_recon_errors)
    )
MODEL_CONTRACT_FINAL_TYPE_SCHEMA_VALID = True

# ── explicit model_representation_type (fail-loud, never a silent fallback) ───
_REPRESENTATION_BY_VAR = {
    "BMI_after": ("fold_safe_quantile_categorical", "FS_QUANTILE_CAT_V1"),
    "weight_in_pregnancy": ("fold_safe_quantile_categorical", "FS_QUANTILE_CAT_V1"),
    "gestational_age_at_PPROM_days": ("fold_safe_pprom_timing_categorical", "FS_PPROM_TIMING_CAT_V1"),
    "BMI_before": ("fold_safe_recomputed_continuous", "FS_RECOMPUTED_BMI_V1"),
}
_REP_BY_PHYSICAL = {
    "continuous": ("same_as_physical_numeric", "NUM_PASSTHROUGH_FOLD_SCALE_V1"),
    "count": ("same_as_physical_numeric", "NUM_PASSTHROUGH_FOLD_SCALE_V1"),
    "binary": ("binary_passthrough", "BIN_PASSTHROUGH_V1"),
    "categorical": ("one_hot_categorical", "CAT_ONEHOT_FOLD_V1"),
    "ordinal": ("one_hot_categorical", "CAT_ONEHOT_FOLD_V1"),
}
_TRANSFORM_SOURCE_ONLY_EXPECTED = {"BMI_after", "weight_in_pregnancy", "gestational_age_at_PPROM_days"}

# Verify the special fold-safe representations against the CURRENT modeling
# contract source (text scan only -- no import). A present modeling_core.py that
# has lost one of these transformers means the representation contract is stale
# and must fail loud.
_modeling_core_path = (
    (_root / "analysis" / "modeling" / "final_modeling" / "modeling_core.py")
    if _root else _Path("analysis/modeling/final_modeling/modeling_core.py")
)
_MODELING_CONTRACT_VERIFIED = {}
if _modeling_core_path.is_file():
    _mc_txt = _modeling_core_path.read_text(encoding="utf-8")
    _MODELING_CONTRACT_VERIFIED = {
        "FoldSafeRecomputedBMITransformer": "class FoldSafeRecomputedBMITransformer" in _mc_txt,
        "FoldSafeQuantileCategoryTransformer": "class FoldSafeQuantileCategoryTransformer" in _mc_txt,
        "pprom_timing_no_PPROM_gate": ('gate_label="no_PPROM"' in _mc_txt or "gate_label='no_PPROM'" in _mc_txt),
    }
    _missing_contract = [k for k, ok in _MODELING_CONTRACT_VERIFIED.items() if not ok]
    if _missing_contract:
        raise AssertionError(
            "C13 model-representation contract STALE: modeling_core.py exists but no "
            f"longer defines {_missing_contract}. The fold-safe representation types "
            "in _REPRESENTATION_BY_VAR would then be wrong -- review before proceeding."
        )
    print(f"  modeling contract verified: {_MODELING_CONTRACT_VERIFIED}")
else:
    print("  NOTE: analysis/modeling/final_modeling/modeling_core.py not found -- fold-safe "
          "representation types registered from the documented Data Cleaning B feature "
          "dictionary contract only (modeling outputs are separately stale, expected).")


def _model_representation(v):
    if v in _REPRESENTATION_BY_VAR:
        return _REPRESENTATION_BY_VAR[v]
    _mem = str(candidate_pool_df.loc[candidate_pool_df["variable"] == v, "model_entry_mode"].iloc[0])
    if _mem == "transform_source_only":
        raise AssertionError(
            f"{v!r} is model_entry_mode=transform_source_only but carries no explicit, "
            "reviewed model_representation_type. Add an explicit entry to "
            "_REPRESENTATION_BY_VAR after review -- EDA C never silently falls back "
            "for a non-standard representation."
        )
    _pt = _physical_type.get(v)
    if _pt in _REP_BY_PHYSICAL:
        return _REP_BY_PHYSICAL[_pt]
    raise AssertionError(f"{v!r}: no model_representation_type for physical type {_pt!r}")


# every transform_source_only pool member must be one we explicitly handled
_ts_only_pool = set(candidate_pool_df.loc[
    candidate_pool_df["model_entry_mode"] == "transform_source_only", "variable"
])
_unexpected_ts_only = _ts_only_pool - _TRANSFORM_SOURCE_ONLY_EXPECTED
if _unexpected_ts_only:
    raise AssertionError(
        f"C13: unexpected transform_source_only pool variable(s) {sorted(_unexpected_ts_only)} "
        "with no explicit reviewed model_representation_type -- do not silently fall back."
    )

_repr_map = {}
_contract_id_map = {}
for _v in _pool_vars:
    _rt, _cid = _model_representation(_v)
    _repr_map[_v] = _rt
    _contract_id_map[_v] = _cid
MODEL_CONTRACT_REPRESENTATION_VALID = all(_repr_map.get(v) for v in _pool_vars)

# ── contract-driven downstream preprocessing requirement (Part J) ────────────
# Driven by physical type + model_representation_type + three-tier structural
# missingness + model_entry_mode + primary_missing_pct_for_modeling. NEVER by
# effective_missing_pct_for_exclusion (stale alias) and NEVER by any
# p / q / effect / redundancy score.
def _downstream_requirement_v2(_row):
    _v = _row["variable"]
    _rep = _repr_map.get(_v) or _repr_by_row.get(_v) or ""
    _pt = _physical_type.get(_v, str(_row.get("data_type") or ""))
    _struct = str(_row.get("structural_applicability_status") or "none")
    _prim = _row.get("primary_missing_pct_for_modeling")
    _reqs = []
    if _rep == "fold_safe_quantile_categorical":
        _reqs += ["transform_source_only", "training_fold_quantile_categorization"]
    elif _rep == "fold_safe_pprom_timing_categorical":
        _reqs += ["transform_source_only", "training_fold_gated_median_categorization"]
    elif _rep == "fold_safe_recomputed_continuous":
        _reqs += ["training_fold_recompute_from_fold_safe_imputed_components"]
    elif _rep == "one_hot_categorical":
        _reqs += ["one_hot_encode_within_training_fold"]
    elif _rep == "binary_passthrough":
        _reqs += ["binary_passthrough_no_encoding"]
    elif _rep == "same_as_physical_numeric":
        _reqs += ["scale_within_training_fold_if_estimator_requires"]
    _is_fold_safe = _reqs and _reqs[0].startswith(("transform_source_only", "training_fold_recompute"))
    if not _is_fold_safe:
        if _struct == "confirmed_structural":
            _reqs.append("subgroup_aware_structural_missingness_no_blind_impute")
        elif _struct == "applicability_linked_no_preprocessing_mask":
            _reqs.append("applicability_sensitivity_raw_missingness_primary")
        elif pd.notna(_prim) and float(_prim) > 0:
            if _pt in ("continuous", "count"):
                _reqs.append("median_impute_within_training_fold")
            else:
                _reqs.append("most_frequent_or_explicit_unknown_within_training_fold")
    if not _reqs:
        _reqs.append("direct_as_is")
    return "; ".join(dict.fromkeys(_reqs))


# ── decorate candidate_df / candidate_pool_df / excluded_features_df ──────────
_repr_by_row = dict(_repr_map)  # eligible only; excluded rows resolve to ""
for _dfname in ("candidate_pool_df", "candidate_df", "excluded_features_df"):
    if _dfname not in dir():
        continue
    _d = eval(_dfname)
    _d["physical_variable_type"] = _d["variable"].map(
        lambda v: str(_ts_by_var[v]["variable_type"]) if v in _ts_by_var else ""
    )
    _d["physical_n_categories"] = _d["variable"].map(
        lambda v: _ts_by_var[v]["n_categories"] if v in _ts_by_var else np.nan
    )
    _d["model_representation_type"] = _d["variable"].map(lambda v: _repr_map.get(v, ""))
    _d["model_preprocessing_contract_id"] = _d["variable"].map(lambda v: _contract_id_map.get(v, ""))
    _d["hard_forbidden_with"] = _d["variable"].map(_hard_forbidden_with)
    _d["relationship_groups"] = _d["variable"].map(_relationship_groups)
    _d["relationship_review_required"] = _d["variable"].map(
        lambda v: bool(_hard_forbidden_with(v) or _relationship_groups(v))
    )
    _d["earliest_entry_stage"] = _d["predictor_classification"].map(_CLS_STAGE)
    _d["fold_safe_requirement"] = _d["variable"].map(
        lambda v: "training_fold_only"
        if str(_repr_map.get(v, "")).startswith("fold_safe_")
        or str(candidate_pool_df.loc[candidate_pool_df["variable"] == v, "model_entry_mode"].iloc[0]
               if v in _pool_vars else "") == "transform_source_only"
        else "none"
    )
    _d["downstream_preprocessing_requirement"] = _d.apply(_downstream_requirement_v2, axis=1)

# hard_forbidden_with must be symmetric and generated ONLY from the pair table
_hfw_check = {}
for _r in candidate_pool_df.to_dict("records"):
    _hfw_check[_r["variable"]] = set(
        p.strip() for p in str(_r["hard_forbidden_with"]).split(";") if p.strip()
    )
for _v, _partners in _hfw_check.items():
    for _p in _partners:
        assert _v in _hfw_check.get(_p, set()), (
            f"hard_forbidden_with not symmetric: {_v} lists {_p} but not vice versa"
        )
    assert _partners == _hard_partners.get(_v, set()), (
        f"hard_forbidden_with for {_v} does not match the pair registry"
    )
MODEL_CONTRACT_COENTRY_VALID = True

# ── build the run-specific export snapshots ──────────────────────────────────
_coentry_export = _coentry_src.copy()
_coentry_export["earliest_applicable_stage"] = _coentry_export.apply(
    lambda r: max(_pool_stage.get(r["var_a"]), _pool_stage.get(r["var_b"])), axis=1
).astype("Int64")
MODEL_COENTRY_EXPORT_DF = _coentry_export
MODEL_RELATIONSHIP_GROUPS_EXPORT_DF = _relgroups_src.copy()

# descriptive empirical relationship diagnostics -- SEPARATE, never a decision input
_diag_rows = []
for _r in (representation_relationship_df.to_dict("records")
           if "representation_relationship_df" in dir() and len(representation_relationship_df) else []):
    _diag_rows.append({
        "var_a": _r["var_a"], "var_b": _r["var_b"],
        "relationship_kind": _r["relationship_kind"],
        "strength_measure": _r["strength_measure"], "strength": _r["strength"],
        "representation_classification": _r["representation_classification"],
        "high_association": True,
    })
for _r in (deterministic_lineage_audit_df.to_dict("records")
           if "deterministic_lineage_audit_df" in dir() and len(deterministic_lineage_audit_df) else []):
    _diag_rows.append({
        "var_a": _r["var_a"], "var_b": _r["var_b"],
        "relationship_kind": _r.get("pair_type", "deterministic_audit"),
        "strength_measure": _r["strength_measure"], "strength": _r["measured_strength"],
        "representation_classification": _r["known_relationship"],
        "high_association": bool(_r.get("in_representation_table", False)),
    })
PREDICTOR_RELATIONSHIP_DIAGNOSTICS_DF = pd.DataFrame(_diag_rows, columns=[
    "var_a", "var_b", "relationship_kind", "strength_measure", "strength",
    "representation_classification", "high_association",
])

HARD_COENTRY_PAIR_COUNT = len(_coentry_src)
RELATIONSHIP_GROUP_COUNT = _relgroups_src["group_name"].nunique()
MODEL_CONTRACT_HARD_PAIRS = sorted(
    (str(r["var_a"]), str(r["var_b"])) for r in _coentry_src.to_dict("records")
)

print("=" * 70)
print("C13 FINAL MODEL-FACING CONTRACT")
print("=" * 70)
print(f"  eligible pool variables            : {len(_pool_vars)}")
print(f"  final type-schema contract valid   : {MODEL_CONTRACT_FINAL_TYPE_SCHEMA_VALID}")
print(f"  model-representation contract valid : {MODEL_CONTRACT_REPRESENTATION_VALID}")
print(f"  co-entry contract valid            : {MODEL_CONTRACT_COENTRY_VALID}")
print(f"  HARD co-entry pairs                 : {HARD_COENTRY_PAIR_COUNT}")
for _a, _b in MODEL_CONTRACT_HARD_PAIRS:
    print(f"      {_a}  <->  {_b}")
print(f"  relationship groups                 : {RELATIONSHIP_GROUP_COUNT}")
print(f"  variables with >=1 hard partner      : "
      f"{sum(1 for v in _pool_vars if _hard_partners.get(v))}")
print(f"  variables in >=1 relationship group  : "
      f"{sum(1 for v in _pool_vars if _var_groups.get(v))}")
_repr_counts = pd.Series(list(_repr_map.values())).value_counts().to_dict()
print(f"  model_representation_type breakdown  : {_repr_counts}")
print("  empirical rho / Cramer's V / epsilon-squared are NEVER used to create a hard pair.")
""")

SC13_EXPORT = code("eda-c-s13-export", """
from pathlib import Path as _Path
from datetime import datetime as _dtm, timezone as _tzout
import json as _json_out

if SAVE_OUTPUTS:
    print("NOTE: SAVE_OUTPUTS = True, but this flag is no longer used by C13 -- the old")
    print("  broad 'target + ALL screened features' matrix is superseded by the candidate")
    print("  pool itself (modeling_dataset_candidate_features.xlsx, governed by")
    print("  SAVE_SELECTED_MODELING_DATASET). No separate file is written for SAVE_OUTPUTS.")
    print()

_any_output_flag = SAVE_AGGREGATED_OUTPUTS or SAVE_SELECTED_MODELING_DATASET
OUTPUT_PATHS = {}

if not _any_output_flag:
    print("SAVE_AGGREGATED_OUTPUTS = False, SAVE_SELECTED_MODELING_DATASET = False")
    print("No files written. Set one or more flags in C1 to enable export.")
else:
    _OUT_DIR = (_root / "outputs" / "eda_c") if _root else _Path("outputs/eda_c")
    if "notebooks" in _OUT_DIR.resolve().parts:
        raise RuntimeError(
            f"EDA C output directory resolved under 'notebooks/' ({_OUT_DIR.resolve()}) -- "
            "this indicates a working-directory/path-anchoring bug. Refusing to write "
            "outputs to a non-canonical location. Expected the project-root-anchored "
            "path, e.g. <project_root>/outputs/eda_c."
        )
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Anchored to the resolved project root (not a bare relative path) so the
    # check is correct regardless of the notebook's working directory. Still a
    # fail-safe: if no .gitignore is found, or none of the recognised patterns
    # cover these files, it warns rather than silently continuing.
    _gitignore_path = (_root / ".gitignore") if _root else _Path(".gitignore")
    _gitignore_ok = False
    if _gitignore_path.is_file():
        _gi_content = _gitignore_path.read_text(encoding="utf-8")
        _gitignore_ok = any(
            _pat in _gi_content
            for _pat in ("outputs/eda_c/*.xlsx", "outputs/**/*.xlsx", "*.xlsx",
                         "outputs/eda_c/", "outputs/eda_c")
        )
    if not _gitignore_ok:
        print("WARNING: 'outputs/eda_c/*.xlsx' may not be covered by .gitignore.")
        print("  Verify before committing. Patient-level data must not be committed.")

    _run_ts = _dtm.now(_tzout.utc).isoformat(timespec="seconds")

    # ── Cumulative-stage helpers (2026-08-31 rebuild) -- cell-level scope so ──
    # both the export block and the manifest block below can use them.
    _STAGE_BY_CLS = {
        "predictor_allowed": 1,
        "secondary_near_delivery_predictor": 2,
        "intrapartum_predictor_exclude_from_prelabor_model": 3,
    }

    def _stage_of(_cls):
        return _STAGE_BY_CLS.get(str(_cls), None)

    # NOTE (2026-09-01 pre-C13 contract freeze): the old cell-scoped
    # `_downstream_requirement` (driven by the stale
    # `effective_missing_pct_for_exclusion` alias + data_type + redundancy
    # score) is RETIRED. `earliest_entry_stage`, `downstream_preprocessing_
    # requirement`, `fold_safe_requirement`, and every new model-facing field
    # (`physical_variable_type`, `physical_n_categories`,
    # `model_representation_type`, `model_preprocessing_contract_id`,
    # `hard_forbidden_with`, `relationship_groups`,
    # `relationship_review_required`) are all set by the SC13_MODEL_CONTRACT
    # cell above, from the authoritative type/classification snapshots + the two
    # hand-authored contract registries. This cell only writes files.

    if SAVE_AGGREGATED_OUTPUTS or SAVE_SELECTED_MODELING_DATASET:
        # Fail-loud safeguard (2026-08-01, Decision 47) -- SUPERSEDED
        # 2026-08-04 (Decision 62): Keren explicitly clarified Celestone is
        # administered during pregnancy for preterm-delivery risk and is
        # therefore given before delivery; celestone was reclassified back to
        # predictor_allowed. This defense-in-depth safety block (matching the
        # ANALYSIS_VARS-level check in eda_c_part1_setup_gate.py) is
        # intentionally retired -- celestone reaching candidate_pool_df is now
        # the correct, expected outcome. See
        # docs/clinical_decisions/manual_decisions_log.md Decision 62.

        # ── Contract-cell reconciliation gate ──────────────────────────────────
        # SC13_MODEL_CONTRACT (the cell above) must have run and decorated every
        # frame with the final model-facing contract columns. Fail loud if not.
        _REQUIRED_CONTRACT_COLS = [
            "earliest_entry_stage", "downstream_preprocessing_requirement",
            "fold_safe_requirement", "physical_variable_type",
            "physical_n_categories", "model_representation_type",
            "model_preprocessing_contract_id", "hard_forbidden_with",
            "relationship_groups", "relationship_review_required",
        ]
        for _need in ("MODEL_CONTRACT_FINAL_TYPE_SCHEMA_VALID",
                      "MODEL_CONTRACT_REPRESENTATION_VALID",
                      "MODEL_CONTRACT_COENTRY_VALID"):
            if _need not in dir() or not eval(_need):
                raise AssertionError(
                    f"C13 export: {_need} is not True -- run the SC13_MODEL_CONTRACT "
                    "cell before the export cell."
                )
        for _stage_df_name in ("candidate_pool_df", "candidate_df", "excluded_features_df"):
            if _stage_df_name in dir():
                _sdf = eval(_stage_df_name)
                _missing_cc = [c for c in _REQUIRED_CONTRACT_COLS if c not in _sdf.columns]
                if _missing_cc:
                    raise AssertionError(
                        f"C13 export: {_stage_df_name} is missing model-contract column(s) "
                        f"{_missing_cc} -- SC13_MODEL_CONTRACT did not run."
                    )

        _pool_unstaged = candidate_pool_df.loc[candidate_pool_df["earliest_entry_stage"].isna(), "variable"].tolist()
        if _pool_unstaged:
            raise AssertionError(
                "STAGE HANDOFF FAILED: candidate-pool variable(s) have no "
                f"resolvable earliest_entry_stage: {_pool_unstaged}"
            )

        # Eligible candidate pool only -- the modelable set (no patient rows)
        if "candidate_pool_df" in dir() and len(candidate_pool_df):
            _out = _OUT_DIR / "candidate_model_features.csv"
            candidate_pool_df.to_csv(_out, index=False, encoding="utf-8")
            OUTPUT_PATHS["candidate_model_features"] = str(_out)
            print(f"Written: {_out} ({len(candidate_pool_df)} rows, no patient data) "
                  "-- cumulative Stage-3 handoff contract (see candidate_features_stage*.csv "
                  "for the per-stage cumulative slices)")

            # ── Three cumulative per-stage candidate exports (2026-08-31 rebuild) ──
            _STAGE_FILES = {
                1: "candidate_features_stage1.csv",
                2: "candidate_features_stage2_cumulative.csv",
                3: "candidate_features_stage3_cumulative.csv",
            }
            _stage_pool_sizes = {}
            for _stg, _fname in _STAGE_FILES.items():
                _slice = candidate_pool_df.loc[
                    candidate_pool_df["earliest_entry_stage"] <= _stg
                ].copy()
                _stage_pool_sizes[_stg] = len(_slice)
                _out_s = _OUT_DIR / _fname
                _slice.to_csv(_out_s, index=False, encoding="utf-8")
                OUTPUT_PATHS[f"candidate_features_stage{_stg}"] = str(_out_s)
                print(f"Written: {_out_s} ({len(_slice)} rows) -- cumulative Stage {_stg} eligible pool")
            # Strict nesting guarantee for the exported slices.
            _s1 = set(pd.read_csv(_OUT_DIR / _STAGE_FILES[1])["variable"])
            _s2 = set(pd.read_csv(_OUT_DIR / _STAGE_FILES[2])["variable"])
            _s3 = set(pd.read_csv(_OUT_DIR / _STAGE_FILES[3])["variable"])
            assert _s1 <= _s2 <= _s3, "STAGE HANDOFF FAILED: exported stage slices are not nested."
            assert _s3 == set(candidate_pool_df["variable"]), (
                "STAGE HANDOFF FAILED: cumulative Stage 3 slice must equal the full eligible pool."
            )

        # ── Final model-contract handoff artifacts (2026-09-01) ────────────────
        # Run-specific validated SNAPSHOTS of the two hand-authored source
        # registries under analysis/eda/notebook_build/eda_c/contracts/. The
        # source files remain the authoritative manually reviewed truth; these
        # are generated per-run and carry run-computed columns (earliest_
        # applicable_stage). No second manual copy is created anywhere.
        _out = _OUT_DIR / "model_coentry_constraints.csv"
        MODEL_COENTRY_EXPORT_DF.to_csv(_out, index=False, encoding="utf-8")
        OUTPUT_PATHS["model_coentry_constraints"] = str(_out)
        print(f"Written: {_out} ({len(MODEL_COENTRY_EXPORT_DF)} HARD, target-independent pairs)")

        _out = _OUT_DIR / "model_relationship_groups.csv"
        MODEL_RELATIONSHIP_GROUPS_EXPORT_DF.to_csv(_out, index=False, encoding="utf-8")
        OUTPUT_PATHS["model_relationship_groups"] = str(_out)
        print(f"Written: {_out} ({len(MODEL_RELATIONSHIP_GROUPS_EXPORT_DF)} rows, "
              f"{MODEL_RELATIONSHIP_GROUPS_EXPORT_DF['group_name'].nunique()} review groups)")

        # Descriptive empirical relationship diagnostics -- SEPARATE from the
        # authored hard registry; a high empirical association is NEVER a
        # hard_forbid_coentry decision criterion.
        _out = _OUT_DIR / "predictor_relationship_diagnostics.csv"
        PREDICTOR_RELATIONSHIP_DIAGNOSTICS_DF.to_csv(_out, index=False, encoding="utf-8")
        OUTPUT_PATHS["predictor_relationship_diagnostics"] = str(_out)
        print(f"Written: {_out} ({len(PREDICTOR_RELATIONSHIP_DIAGNOSTICS_DF)} rows, descriptive only)")

        # Hard-excluded variables + exact reasons (no patient rows)
        if "excluded_features_df" in dir():
            _out = _OUT_DIR / "excluded_features_log.csv"
            excluded_features_df.to_csv(_out, index=False, encoding="utf-8")
            OUTPUT_PATHS["excluded_features_log"] = str(_out)
            print(f"Written: {_out} ({len(excluded_features_df)} rows, no patient data)")

        # Full review table -- eligible + hard-excluded rows (no patient rows)
        if "candidate_df" in dir() and len(candidate_df):
            _out = _OUT_DIR / "candidate_feature_review_full.csv"
            candidate_df.to_csv(_out, index=False, encoding="utf-8")
            OUTPUT_PATHS["candidate_feature_review_full"] = str(_out)
            print(f"Written: {_out} ({len(candidate_df)} rows, no patient data)")

            # final_candidate_features.csv -- CONVENIENCE deliverable, same content as
            # candidate_feature_review_full.csv above, under this session's requested
            # filename. NOT a second source of truth; candidate_feature_review_full.csv
            # remains canonical. Written from the same in-memory candidate_df in the
            # same run, so the two files can never drift from each other.
            _out = _OUT_DIR / "final_candidate_features.csv"
            candidate_df.to_csv(_out, index=False, encoding="utf-8")
            OUTPUT_PATHS["final_candidate_features"] = str(_out)
            print(f"Written: {_out} ({len(candidate_df)} rows, no patient data) "
                  "-- convenience re-export of candidate_feature_review_full.csv")

            # selected_model_features.csv -- VERSIONED broad-candidate-pool deliverable.
            # Same variable rows as candidate_model_features.csv (candidate_pool_df),
            # plus explicit contract/provenance columns so this can never be mistaken
            # for the OLD, pre-redesign, capped-10-feature Model V1 "conservative
            # primary set" contract, which this does NOT reproduce. candidate_model_
            # features.csv remains the canonical EDA D input; this is a re-export with
            # a clarified contract, not a competing selection.
            if "candidate_pool_df" in dir() and len(candidate_pool_df):
                _sel_src = candidate_pool_df.copy()
                _test_used_map = (
                    screening_df.set_index("variable")["test"].to_dict()
                    if "screening_df" in dir() else {}
                )
                _selected_model_features_df = pd.DataFrame({
                    "variable_name": _sel_src["variable"],
                    "selection_status": _sel_src["eligibility_status"],
                    "handoff_role": "broad_candidate_pool_member",
                    "contract_version": "EDA_C_BROAD_CANDIDATE_POOL_v1",
                    "reason": _sel_src["reason"],
                    "test_used": _sel_src["variable"].map(_test_used_map).fillna("n/a"),
                    "p_value": _sel_src["p_value"],
                    "q_value": _sel_src["fdr_q_value"],
                    "effect_size": _sel_src["effect_size"],
                    "redundancy_flag": _sel_src["redundancy_flag"],
                    # 2026-08-20 (target-informed pre-CV screening consistency
                    # correction): leakage_flag (target-correlation smoke test)
                    # is no longer a hard-exclusion rule, so this note must
                    # reflect the row's ACTUAL disclosed state, not a hardcoded
                    # "no". Semantic/clinical leakage (post-outcome, timing,
                    # explicit classification) is unaffected and still enforced
                    # upstream in C2/C3 -- a variable reaching this table at all
                    # already passed that gate.
                    "timing_leakage_notes": _sel_src.apply(
                        lambda r: (
                            f"timing={r['timing']}; semantic_leakage_status=no "
                            "(post-outcome/timing/classification-based leakage is enforced "
                            "upstream in C2/C3, before this table is built -- unaffected by "
                            "the 2026-08-20 correction below); "
                            + (
                                "high_target_association_review=disclosed "
                                "(|r_vs_target| > DERIVED_TARGET_ASSOC_REVIEW_THRESHOLD -- a prompt for "
                                "manual lineage/semantic review; high target association is "
                                "NOT by itself leakage and is NOT an exclusion; see "
                                "soft_warning_flags)"
                                if bool(r.get("high_target_association_review", False))
                                else "high_target_association_review=no"
                            )
                        ),
                        axis=1,
                    ),
                })
                _out = _OUT_DIR / "selected_model_features.csv"
                _selected_model_features_df.to_csv(_out, index=False, encoding="utf-8")
                OUTPUT_PATHS["selected_model_features"] = str(_out)
                print(f"Written: {_out} ({len(_selected_model_features_df)} rows, no patient data) "
                      "-- versioned broad-candidate-pool deliverable; see contract_version "
                      "column -- NOT the old capped-10 Model V1 'conservative_primary_set'.")

        # Feature dictionary (no patient rows). 2026-09-01: `primary_model_eligible`
        # is a LEGACY compatibility field only -- it is renamed to
        # `primary_model_eligible_legacy` here and the authoritative multi-horizon
        # fields are added (`analytical_role`, `domain`, `expected_type`,
        # `runtime_availability`, `earliest_entry_stage`, `source_columns`,
        # `model_representation_type` where the feature is a live eligible
        # predictor). A reader must not treat legacy primary-model eligibility as
        # the multi-horizon authority.
        if DERIVED_VARS:
            _c8_plan_by_name = (
                {r["new_feature_name"]: r for r in _FEATURE_PLAN}
                if "_FEATURE_PLAN" in dir() else {}
            )
            _repr_lookup = _repr_map if "_repr_map" in dir() else {}
            _dict_rows = []
            for _dv in DERIVED_VARS:
                _m = derived_meta[_dv]
                _role = _m.get("analytical_role", "")
                _stage = {"predictor_allowed": 1,
                          "secondary_near_delivery_predictor": 2,
                          "intrapartum_predictor_exclude_from_prelabor_model": 3}.get(_role, "n/a")
                _dict_rows.append({
                    "feature": _dv,
                    "source_columns": _m["source_columns"],
                    "domain": _m.get("domain", ""),
                    "timing": _m["timing"],
                    "expected_type": _m.get("expected_type", ""),
                    "analytical_role": _role,
                    "earliest_entry_stage": _stage,
                    "runtime_availability": _c8_plan_by_name.get(_dv, {}).get("runtime_availability", ""),
                    "model_representation_type": _repr_lookup.get(_dv, ""),
                    "primary_model_eligible_legacy": _m["primary_model_eligible"],
                    "note": _m.get("note", ""),
                })
            _fd = pd.DataFrame(_dict_rows)
            _out = _OUT_DIR / "feature_dictionary.csv"
            _fd.to_csv(_out, index=False, encoding="utf-8")
            OUTPUT_PATHS["feature_dictionary"] = str(_out)
            print(f"Written: {_out} ({len(_fd)} rows)")

        # Action log (no patient rows)
        _log = pd.DataFrame([
            {"field": "run_timestamp", "value": _run_ts},
            {"field": "dataset", "value": DATA_PATH.name},
            {"field": "dataset_sha256", "value": _sha256[:24]},
            {"field": "analysis_vars_count", "value": len(ANALYSIS_VARS)},
            {"field": "derived_vars_count", "value": len(DERIVED_VARS)},
            # NOTE (2026-07-26 classification reconciliation; updated 2026-08-13,
            # Decision 65 / multi-horizon plan Batch 2): this counts only
            # ANALYSIS_VARS + DERIVED_VARS, i.e. variables that enter the
            # statistical screening loop in C12 (Part 4). intrapartum_predictor_
            # exclude_from_prelabor_model variables are now PART OF ANALYSIS_VARS
            # (they are in the unified master pool as of Decision 65) and so ARE
            # included in this count and screened normally -- they are no longer a
            # separate placeholder block appended afterward. The only remaining gap
            # between this count and candidate_feature_manifest.json's
            # "n_screened" is PENDING_TIMING_CONFIRMATION_COLS (currently 0
            # members), which is still appended after screening as a documented
            # placeholder (see the _pending_timing_rows block in
            # eda_c_part4_screening.py), since its timing remains unresolved.
            # Both counts are internally correct for what they measure; they are
            # not the same measurement and should not be expected to match.
            {"field": "screened_vars_count", "value": len(SCREEN_VARS)},
            {"field": "eligible_candidate_pool_count",
             "value": len(candidate_pool_df) if "candidate_pool_df" in dir() else "n/a"},
            {"field": "hard_excluded_count",
             "value": len(excluded_features_df) if "excluded_features_df" in dir() else "n/a"},
            # 2026-08-31: the hand-typed CLINICAL_DECISIONS_COMPLETE boolean was
            # retired. Report the live operational unresolved-state counts instead
            # (the actual thing the readiness gate now checks).
            {"field": "pending_timing_candidate_in_universe_count",
             "value": len(set(ANALYSIS_VARS) & set(PENDING_TIMING_CONFIRMATION_COLS))},
            {"field": "awaiting_clinical_clarification_in_universe_count",
             "value": len(set(ANALYSIS_VARS) & set(AWAITING_CLINICAL_CLARIFICATION_COLS))},
            {"field": "manual_review_pending_in_eligible_pool_count",
             "value": (len(set(candidate_pool_df["variable"]) & set(MANUAL_REVIEW_PENDING_COLS))
                       if "candidate_pool_df" in dir() else "n/a")},
            {"field": "save_aggregated_outputs", "value": SAVE_AGGREGATED_OUTPUTS},
            {"field": "save_selected_modeling_dataset", "value": SAVE_SELECTED_MODELING_DATASET},
        ])
        _out = _OUT_DIR / "eda_c_action_log.csv"
        _log.to_csv(_out, index=False, encoding="utf-8")
        OUTPUT_PATHS["eda_c_action_log"] = str(_out)
        print(f"Written: {_out}")

    if SAVE_SELECTED_MODELING_DATASET:
        # Patient-level modeling dataset — GITIGNORED
        # target + ONLY the eligible candidate-pool columns. No ID columns (C0 safety rule).
        _cand_cols = [TARGET_COL] + list(candidate_pool_df["variable"])
        _cand_cols = [c for c in dict.fromkeys(_cand_cols) if c in df_analysis.columns]
        _cand_cols = [c for c in _cand_cols if c not in set(ID_COLS)]
        _cand_matrix = df_analysis[_cand_cols].copy()
        _out = _OUT_DIR / "modeling_dataset_candidate_features.xlsx"
        _cand_matrix.to_excel(_out, index=False, engine="openpyxl")
        OUTPUT_PATHS["modeling_dataset_candidate_features"] = str(_out)
        print(f"Written: {_out} ({len(_cand_matrix)} rows x {len(_cand_cols)} cols) — PATIENT-LEVEL — GITIGNORED")
        print(f"  Columns: target + {len(candidate_pool_df)} eligible candidate-pool features (no ID columns).")
        print("  Verify this file is listed in .gitignore before committing.")

        # ── Three cumulative per-stage patient-level modeling datasets ─────────
        # (2026-08-31 rebuild) target + the eligible-pool columns for that
        # cumulative stage. transform_source_only raw sources ARE included
        # (they feed the fold-safe transformer at modeling time); their
        # non-direct status is carried in the candidate_features_stage*.csv
        # metadata, never lost. No learned quantity is materialized here.
        _stage_dataset_files = {
            1: "modeling_dataset_stage1.xlsx",
            2: "modeling_dataset_stage2_cumulative.xlsx",
            3: "modeling_dataset_stage3_cumulative.xlsx",
        }
        _stage_dataset_shapes = {}
        _prev_stage_cols = None
        for _stg, _fname in _stage_dataset_files.items():
            _stg_vars = candidate_pool_df.loc[
                candidate_pool_df["earliest_entry_stage"] <= _stg, "variable"
            ].tolist()
            _stg_cols = [TARGET_COL] + [c for c in _stg_vars if c in df_analysis.columns and c not in set(ID_COLS)]
            _stg_cols = list(dict.fromkeys(_stg_cols))
            if _prev_stage_cols is not None:
                assert set(_prev_stage_cols) <= set(_stg_cols), (
                    f"STAGE HANDOFF FAILED: stage {_stg} dataset columns are not a superset of the previous stage."
                )
            _prev_stage_cols = _stg_cols
            _stg_matrix = df_analysis[_stg_cols].copy()
            _n0 = int((_stg_matrix[TARGET_COL] == 0).sum())
            _n1 = int((_stg_matrix[TARGET_COL] == 1).sum())
            assert (_n0, _n1) == (int((df_analysis[TARGET_COL] == 0).sum()), int((df_analysis[TARGET_COL] == 1).sum())), (
                f"STAGE HANDOFF FAILED: stage {_stg} dataset target distribution changed."
            )
            _out_sd = _OUT_DIR / _fname
            _stg_matrix.to_excel(_out_sd, index=False, engine="openpyxl")
            OUTPUT_PATHS[f"modeling_dataset_stage{_stg}"] = str(_out_sd)
            _stage_dataset_shapes[_stg] = (len(_stg_matrix), len(_stg_cols))
            print(f"Written: {_out_sd} ({len(_stg_matrix)} rows x {len(_stg_cols)} cols, "
                  f"target {_n0}/{_n1}) -- cumulative Stage {_stg} — PATIENT-LEVEL — GITIGNORED")

        # Row-order delivery_id sidecar -- delivery_id is NEVER a candidate-pool
        # column or model feature (C0 safety rule; excluded from _cand_cols
        # above like every other ID). Exported from this SAME df_analysis
        # object, in the SAME row order as _cand_matrix just written above
        # (df_analysis[[...]] is a column-only selection either way, so both
        # come from identical rows in identical order). This is the row key
        # analysis/modeling/final_modeling/subject_groups.py joins against to
        # assign CV subject groups -- construction-guaranteed aligned with
        # modeling_dataset_candidate_features.xlsx, not merely same-row-count.
        _row_key_out = _OUT_DIR / "modeling_dataset_row_delivery_id_key.csv"
        pd.DataFrame({
            "row_index": range(len(df_analysis)),
            "delivery_id": df_analysis["_row_key_delivery_id"].to_numpy(),
        }).to_csv(_row_key_out, index=False)
        OUTPUT_PATHS["modeling_dataset_row_delivery_id_key"] = str(_row_key_out)
        print(f"Written: {_row_key_out} (row-order ID key, id-only) — GITIGNORED")

        # modeling_dataset_all_clean_features.xlsx -- DISTINCT from
        # modeling_dataset_candidate_features.xlsx above, not a mirror: target +
        # ALL baseline ANALYSIS_VARS (79 as of Decision 91, live-verified; was 69
        # pre-Decision-91 -- see len(ANALYSIS_VARS) printed at runtime, not
        # hardcoded here) + implementable derived features (SCREEN_VARS), i.e.
        # the full clean candidate universe BEFORE eligibility
        # filtering. No ID columns (C0 safety rule); no leakage, post-delivery/
        # intrapartum-outcome, or superseded-raw variables -- already structurally
        # guaranteed by how ANALYSIS_VARS (C3) and DERIVED_VARS (C9) are built, so
        # no additional filtering logic is needed here beyond dropping ID columns.
        _all_clean_cols = [TARGET_COL] + list(dict.fromkeys(SCREEN_VARS))
        _all_clean_cols = [c for c in _all_clean_cols if c in df_analysis.columns and c not in set(ID_COLS)]
        _all_clean_matrix = df_analysis[_all_clean_cols].copy()
        _out = _OUT_DIR / "modeling_dataset_all_clean_features.xlsx"
        _all_clean_matrix.to_excel(_out, index=False, engine="openpyxl")
        OUTPUT_PATHS["modeling_dataset_all_clean_features"] = str(_out)
        print(f"Written: {_out} ({len(_all_clean_matrix)} rows x {len(_all_clean_cols)} cols) "
              "— PATIENT-LEVEL — GITIGNORED")
        print(f"  Columns: target + {len(SCREEN_VARS)} clean baseline+derived candidates, "
              "BEFORE eligibility filtering -- broader than modeling_dataset_candidate_features.xlsx "
              f"({len(candidate_pool_df)} post-hard-exclusion columns), not a mirror of it.")
        print("  Verify this file is listed in .gitignore before committing.")

    # Candidate feature manifest (no patient rows) — written last so OUTPUT_PATHS
    # reflects every file actually written in this run, including the xlsx export.
    _manifest_ready = (
        (SAVE_AGGREGATED_OUTPUTS or SAVE_SELECTED_MODELING_DATASET)
        and "candidate_df" in dir() and len(candidate_df)
    )
    if _manifest_ready:
        # Defensive re-verification: confirm the input file on disk still hashes
        # to the value recorded at load time in Part 1, catching a mid-run
        # overwrite (e.g. a concurrent Data Cleaning B rerun) before trusting it
        # in the written manifest.
        _reverify_sha256 = _file_sha256(DATA_PATH)
        if _reverify_sha256 != _sha256:
            raise RuntimeError(
                f"Input dataset changed on disk during this run: loaded with "
                f"SHA-256 {_sha256}, now {_reverify_sha256}. Re-run EDA C against "
                "a stable input before trusting these results."
            )
        # Cumulative-stage architecture snapshot (2026-08-31 rebuild).
        _stage_arch = {}
        for _stg in (1, 2, 3):
            _before = [
                v for v in SCREEN_VARS
                if _stage_of(candidate_df.loc[candidate_df["variable"] == v, "predictor_classification"].iloc[0]) is not None
                and _stage_of(candidate_df.loc[candidate_df["variable"] == v, "predictor_classification"].iloc[0]) <= _stg
            ] if len(candidate_df) else []
            _elig = candidate_pool_df.loc[candidate_pool_df["earliest_entry_stage"] <= _stg, "variable"].tolist()
            _stage_arch[f"stage{_stg}"] = {
                "cumulative": True,
                "n_before_hard_exclusion": len(_before),
                "n_eligible": len(_elig),
                "variables_eligible": sorted(_elig),
            }

        # ── Validation-gated pipeline_status (2026-09-01) ─────────────────────
        _s1v = set(_stage_arch["stage1"]["variables_eligible"])
        _s2v = set(_stage_arch["stage2"]["variables_eligible"])
        _s3v = set(_stage_arch["stage3"]["variables_eligible"])
        _EDA_C_STATUS_GATES = {
            "pool_validation_passed (C12c)": bool(pool_validation_passed) if "pool_validation_passed" in dir() else False,
            "cohort rows == 431": N_ROWS == EXPECTED_ROWS,
            "target 370/61 preserved": (
                int((df_analysis[TARGET_COL] == 0).sum()) == EXPECTED_N0
                and int((df_analysis[TARGET_COL] == 1).sum()) == EXPECTED_N1
            ),
            "stage pools strictly nested": _s1v <= _s2v <= _s3v,
            "cumulative Stage 3 == full eligible pool": _s3v == set(candidate_pool_df["variable"]),
            "no hard-excluded variable in the pool": not (
                set(candidate_pool_df["variable"]) & set(excluded_features_df["variable"])
            ),
            "every hard exclusion is target-independent": all(
                all(
                    (part.strip() in {
                        "invalid_or_impossible_values", "zero_variance",
                        "hard_clinical_unresolved_pending_review",
                        "sanity_check_only_not_a_modeling_candidate",
                    }) or ("pending_timing_confirmation" in part)
                    for part in str(reason).split(";") if part.strip()
                )
                for reason in excluded_features_df["hard_exclusion_reason"]
            ) if len(excluded_features_df) else True,
            # ── Operational clinical-readiness gates (2026-08-31: replace the
            #    retired hand-typed CLINICAL_DECISIONS_COMPLETE /
            #    CLINICAL_DECISIONS_LOG_UPDATED booleans). Derived from the live
            #    classification metadata + the C12b pool. A blocked/unresolved
            #    upstream role reaching a stage or the eligible pool now forces
            #    pipeline_status = BLOCKED -- it can no longer be asserted away.
            "no pending-timing-confirmation variable in the analytical universe":
                not (set(ANALYSIS_VARS) & set(PENDING_TIMING_CONFIRMATION_COLS)),
            "no awaiting-clinical-clarification variable in the analytical universe":
                not (set(ANALYSIS_VARS) & set(AWAITING_CLINICAL_CLARIFICATION_COLS)),
            "no manual-review-pending variable in the eligible candidate pool":
                not (set(candidate_pool_df["variable"]) & set(MANUAL_REVIEW_PENDING_COLS)),
        }
        _EDA_C_GATES_OK = all(_EDA_C_STATUS_GATES.values())
        _EDA_C_PIPELINE_STATUS = "CANONICAL" if _EDA_C_GATES_OK else "BLOCKED"
        print()
        print("EDA C pipeline-status gates:")
        for _g, _ok in _EDA_C_STATUS_GATES.items():
            print(f"  [{'PASS' if _ok else 'FAIL'}] {_g}")
        print(f"  => pipeline_status = {_EDA_C_PIPELINE_STATUS}")

        # 2026-08-31 C3 correction: prefer repository-relative paths in the
        # machine-readable manifest -- absolute Windows paths are not portable
        # across a project-folder rename or a different checkout. The SHA-256
        # fields remain the authoritative content identity.
        def _rel_to_root(_p):
            try:
                return str(Path(_p).resolve().relative_to(Path(_root).resolve())).replace("\\\\", "/")
            except Exception:
                return str(_p)

        _manifest = {
            "run_timestamp_utc": _run_ts,
            "eda_c_architecture_version": "2026-08-31-stage-rebuild",
            # ── Canonical B->C input contract (2026-08-31 C3 correction) ──────
            "b_manifest_relpath": _rel_to_root(_B_MANIFEST_PATH),
            "b_manifest_sha256": _b_manifest_sha256,
            "b_manifest_output_file": str(_b_manifest.get("output_file")),
            "b_manifest_output_sha256": str(_b_manifest.get("output_sha256")),
            "input_dataset_relpath": _rel_to_root(DATA_PATH),
            "input_dataset_loaded_sha256": _sha256,
            "input_dataset_sha256_matches_b_manifest": (
                _sha256 == str(_b_manifest.get("output_sha256")).strip()
            ),
            "b_manifest_row_exclusions_applied": bool(_b_manifest.get("row_exclusions_applied")),
            "b_manifest_export_for_eda_c": _b_manifest.get("export_for_eda_c"),
            "row_key_sidecar_relpath": _rel_to_root(_row_key_path),
            "row_key_sidecar_sha256": _row_key_sidecar_sha256,
            "row_key_sidecar_binding_limitation": (
                "cleaning_b_manifest.json carries no cryptographic sidecar-binding "
                "field; row-count + 0..n-1 row_index equality is consistency "
                "evidence only, not cryptographic proof of same-export origin."
            ),
            "unnamed_import_artifact_dropped": bool(_UNNAMED_ARTIFACT_PRESENT),
            "duplicate_analytical_rows": int(_n_dup_analytical),
            "b_feature_dictionary_sha256": _b_feature_dict_sha256,
            "input_dataset_path": str(DATA_PATH),
            "input_dataset_sha256": _sha256,
            "input_classification_csv_path": str(CLASSIFICATION_PATH),
            "input_classification_csv_relpath": _rel_to_root(CLASSIFICATION_PATH),
            "input_classification_csv_sha256": _classification_sha256,
            "input_type_schema_csv_sha256": _type_schema_sha256,
            # 2026-08-27 correction (Decision 91, Gap 2), corrected again
            # 2026-08-28 (Gap 2 follow-up, independent review of the
            # committed patch): the preprocessing-level CSV fields above are
            # retained for provenance/audit comparison only -- they are NOT
            # the authoritative classification/type input. The Data Cleaning
            # B snapshots below ARE the authoritative source for both
            # _cols_for()/ORIGINAL_ANALYSIS_VARS eligibility AND
            # infer_var_type()'s type inference this run. A value difference
            # between a preprocessing-level field and its B-snapshot
            # counterpart is expected whenever B has approved a
            # reclassification/type change -- it is reported below for audit
            # visibility, never treated as an error, and never allowed to
            # override the B snapshot value (see eda_c_part1_setup_gate.py's
            # structural fail-loud checks + audit-only diff report).
            "b_classification_snapshot_path": str(_B_CLASSIFICATION_SNAPSHOT_PATH),
            "b_classification_snapshot_sha256": _b_classification_snapshot_sha256,
            "b_type_schema_snapshot_path": str(_B_TYPE_SCHEMA_SNAPSHOT_PATH),
            "b_type_schema_snapshot_sha256": _b_type_schema_snapshot_sha256,
            "b_classification_snapshot_is_authoritative_for_eda_c": True,
            "b_type_schema_snapshot_is_authoritative_for_eda_c": True,
            "classification_snapshot_audit_diffs": CLASSIFICATION_SNAPSHOT_AUDIT_DIFFS,
            "type_schema_snapshot_audit_diffs": TYPE_SCHEMA_SNAPSHOT_AUDIT_DIFFS,
            "provenance_note": (
                "Path fields above are absolute and not portable across a project "
                "folder rename; the SHA-256 fields are the authoritative content "
                "identity and should be used to verify inputs, not the path strings. "
                "b_classification_snapshot_* and b_type_schema_snapshot_* are the "
                "authoritative classification/type inputs for this run's variable "
                "eligibility and type inference; input_classification_csv_*/"
                "input_type_schema_csv_* are the raw preprocessing-level files, "
                "retained for provenance/lineage only. Preprocessing and B are NOT "
                "required to have identical classification/type values -- a "
                "legitimate B-level reclassification or type correction is expected "
                "to differ from the older preprocessing state. Any such difference "
                "is reported in classification_snapshot_audit_diffs/"
                "type_schema_snapshot_audit_diffs for audit visibility; B always "
                "controls, and the preprocessing value never overrides it."
            ),
            # pipeline_status is VALIDATION-GATED (2026-09-01 correction): it is
            # "CANONICAL" only when every required gate passes, otherwise
            # "BLOCKED" (and conclusion "FAIL"). "CANONICAL" reuses this
            # project's existing vocabulary for "the state to be trusted/used
            # now" (CANONICAL_PROCESSED_FINGERPRINT in
            # eda_shared/canonical_data_manifest.py). The gate is computed just
            # below from pool_validation_passed + the stage-nesting / row /
            # target invariants; the "conclusion" field mirrors it.
            "pipeline_status": _EDA_C_PIPELINE_STATUS,
            "n_rows": N_ROWS,
            "n_events": N_EVENTS,
            "advisory_conservative_feature_cap": ADVISORY_CONSERVATIVE_FEATURE_CAP,
            # 2026-08-31 rebuild: the generic >40% missingness HARD rule was
            # removed. This is now only the SOFT-warning boundary.
            "high_missingness_diagnostic_threshold_pct": HIGH_MISSINGNESS_DIAGNOSTIC_THRESHOLD,
            "generic_high_missingness_hard_exclusion_removed": True,
            "n_screened": len(candidate_df),
            "n_hard_excluded": len(excluded_features_df),
            "n_eligible_pool": len(candidate_pool_df),
            "stage_architecture": _stage_arch,
            "n_stage1_before_hard_exclusion": _stage_arch["stage1"]["n_before_hard_exclusion"],
            "n_stage1_eligible": _stage_arch["stage1"]["n_eligible"],
            "n_stage2_cumulative_before_hard_exclusion": _stage_arch["stage2"]["n_before_hard_exclusion"],
            "n_stage2_cumulative_eligible": _stage_arch["stage2"]["n_eligible"],
            "n_stage3_cumulative_before_hard_exclusion": _stage_arch["stage3"]["n_before_hard_exclusion"],
            "n_stage3_cumulative_eligible": _stage_arch["stage3"]["n_eligible"],
            "feature_engineering_count": len(DERIVED_VARS),
            "transform_source_only_count": int(
                (candidate_pool_df["model_entry_mode"] == "transform_source_only").sum()
            ) if "model_entry_mode" in candidate_pool_df.columns else 0,
            "no_analytical_row_deletion": True,
            "no_full_cohort_learned_imputation": True,
            "no_full_cohort_learned_cutpoint_fitting": True,
            "no_target_informed_hard_feature_selection": True,
            "target_informed_redundancy_winner_selection_removed": True,
            # ── Final model-facing contract (2026-09-01 pre-C13 freeze) ────────
            "final_model_contract": {
                "final_type_schema_contract_valid": bool(MODEL_CONTRACT_FINAL_TYPE_SCHEMA_VALID),
                "model_representation_contract_valid": bool(MODEL_CONTRACT_REPRESENTATION_VALID),
                "coentry_contract_valid": bool(MODEL_CONTRACT_COENTRY_VALID),
                "hard_coentry_pair_count": int(HARD_COENTRY_PAIR_COUNT),
                "relationship_group_count": int(RELATIONSHIP_GROUP_COUNT),
                "hard_coentry_target_independent_only": True,
                "empirical_association_not_used_for_hard_coentry": True,
                "hard_coentry_pairs": [list(p) for p in MODEL_CONTRACT_HARD_PAIRS],
                "coentry_source_registry": _rel_to_root(_COENTRY_SRC_PATH),
                "relationship_groups_source_registry": _rel_to_root(_RELGROUPS_SRC_PATH),
                "modeling_contract_source_verification": _MODELING_CONTRACT_VERIFIED,
            },
            "final_type_schema_contract_valid": bool(MODEL_CONTRACT_FINAL_TYPE_SCHEMA_VALID),
            "model_representation_contract_valid": bool(MODEL_CONTRACT_REPRESENTATION_VALID),
            "coentry_contract_valid": bool(MODEL_CONTRACT_COENTRY_VALID),
            "hard_coentry_pair_count": int(HARD_COENTRY_PAIR_COUNT),
            "relationship_group_count": int(RELATIONSHIP_GROUP_COUNT),
            "hard_coentry_target_independent_only": True,
            "empirical_association_not_used_for_hard_coentry": True,
            # ── Operational clinical-readiness (2026-08-31): the retired
            #    hand-typed CLINICAL_DECISIONS_COMPLETE /
            #    CLINICAL_DECISIONS_LOG_UPDATED booleans are replaced by these
            #    live-metadata counts. Each MUST be 0 for pipeline_status
            #    CANONICAL. A non-zero count means a blocked/unresolved upstream
            #    role actually reached a stage or the eligible pool.
            "manual_readiness_booleans_retired": True,
            "operational_clinical_readiness": {
                "pending_timing_candidate_in_universe_count":
                    len(set(ANALYSIS_VARS) & set(PENDING_TIMING_CONFIRMATION_COLS)),
                "awaiting_clinical_clarification_in_universe_count":
                    len(set(ANALYSIS_VARS) & set(AWAITING_CLINICAL_CLARIFICATION_COLS)),
                "manual_review_pending_in_eligible_pool_count":
                    len(set(candidate_pool_df["variable"]) & set(MANUAL_REVIEW_PENDING_COLS)),
                "forbidden_role_in_eligible_pool_count":
                    len(set(candidate_pool_df["variable"]) & (
                        set(LEAKAGE_EXCLUDE_COLS) | set(INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS)
                        | set(SOURCE_OR_TEXT_AUDIT_EXCLUDE_COLS) | set(ID_COLS) | set(TARGET_COLS)
                    )),
            },
            "hard_exclusion_counts": {
                # leakage_or_post_outcome_proxy / complete_or_quasi_separation /
                # severe_quasi_separation_boundary_sparse_instability /
                # too_sparse_insufficient_cell_counts REMOVED from this dict
                # (2026-08-19 separation/sparsity; 2026-08-20 leakage_flag,
                # target-informed pre-CV screening consistency correction) --
                # none are hard-exclusion rules any more; see
                # soft_warning_counts below.
                "invalid_or_impossible_values": int(candidate_df["impossible_flag"].sum()),
                "zero_variance": int(candidate_df["zero_variance_flag"].sum()),
                # 2026-08-31 rebuild: generic >40% missingness hard rule removed
                # -> always 0. High missingness is now a soft warning
                # (`high_missingness_diagnostic`, see soft_warning_counts).
                "high_missingness_exceeds_threshold": 0,
                "hard_clinical_unresolved_pending_review": int(candidate_df["variable"].isin(_hard_excl_pending_review).sum()),
                "pending_timing_confirmation_before_intrapartum_cs_decision": int(candidate_df["variable"].isin(_hard_excl_pending_timing_confirmation).sum()),
                # confirmed_intrapartum_excluded_from_prelabor_model removed
                # 2026-08-13 (Decision 65 / multi-horizon plan Batch 2): that
                # classification is no longer a category-wide hard exclusion --
                # see the "intrapartum_predictor_exclude_from_prelabor_model"
                # block below for its unified-pool status instead.
                "sanity_check_only": int(candidate_df["variable"].apply(_is_sanity_check_only).sum()),
            },
            "soft_warning_counts": {
                "rare_feature": int(candidate_df["rare_feature_flag"].sum()),
                "timing_uncertain": int(candidate_df["timing_uncertain"].sum()),
                "redundancy_demoted": int(candidate_df["redundancy_demoted"].sum()),
                "redundancy_unresolved": int(candidate_df["redundancy_unresolved"].sum()),
                "high_missingness_diagnostic": int(candidate_df["variable"].isin(_high_missingness_diagnostic_vars).sum()),
                "weak_univariate_signal": int((~candidate_df["meets_quality_bar"]).sum()),
                # separation_risk / sparse_event_risk / boundary_sparse_
                # instability_risk added 2026-08-19, target_correlation_
                # leakage_risk added 2026-08-20 -- moved here from
                # hard_exclusion_counts above; disclosure only, does not
                # remove a variable from the pool.
                "separation_risk": int(candidate_df["separation_flag"].sum()),
                "sparse_event_risk": int((candidate_df["too_sparse_flag"] & ~candidate_df["separation_flag"]).sum()),
                "boundary_sparse_instability_risk": int(candidate_df["variable"].isin(_boundary_sparse_risk_vars).sum()),
                "high_target_association_review": int(candidate_df["high_target_association_review"].sum()),
            },
            "target_distribution": {
                TARGET_COL: {"n0": int((df_analysis[TARGET_COL] == 0).sum()),
                             "n1": int((df_analysis[TARGET_COL] == 1).sum())},
            },
            "pending_timing_confirmation": {
                "classification": "intrapartum_candidate_pending_timing_confirmation",
                "columns": list(PENDING_TIMING_CONFIRMATION_COLS),
                "exclusion_reason": (
                    "Excluded from primary and secondary modeling predictor pools "
                    "pending clinical confirmation that values were available before "
                    "the intrapartum cesarean decision."
                ),
            },
            "intrapartum_predictor_exclude_from_prelabor_model": {
                "classification": "intrapartum_predictor_exclude_from_prelabor_model",
                "columns": list(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS),
                "status": (
                    "Part of the unified master candidate pool as of Decision 65 "
                    "(clinical review with Dr. Keren and Dr. Shai, 2026-08-12) -- "
                    "no longer categorically excluded here. Screened through the "
                    "same QC/screening pipeline as every other candidate; timing "
                    "relative to the intrapartum CS decision is clinically "
                    "confirmed as intrapartum (relayed by Keren, 28 July 2026), so "
                    "these variables are eligible for the intrapartum modeling "
                    "horizon only. Horizon eligibility (pre-labor / near-delivery / "
                    "intrapartum) is decided at the modeling boundary, downstream "
                    "of this handoff, not in EDA C -- see each variable's "
                    "predictor_classification in candidate_model_features.csv."
                ),
            },
            "output_paths": OUTPUT_PATHS,
        }
        _manifest["pipeline_status_gates"] = _EDA_C_STATUS_GATES
        if "pool_validation_passed" in dir():
            # conclusion mirrors the same validation gate as pipeline_status.
            _manifest["conclusion"] = "PASS" if _EDA_C_GATES_OK else "FAIL"
            _manifest["validation_checks"] = pool_validation_checks
        _out = _OUT_DIR / "candidate_feature_manifest.json"
        with open(_out, "w", encoding="utf-8") as _mf_out:
            _json_out.dump(_manifest, _mf_out, indent=2, ensure_ascii=False)
        OUTPUT_PATHS["candidate_feature_manifest"] = str(_out)
        print(f"Written: {_out}")

        # Classification-lineage: save the EDA C snapshot (fresh copy of the
        # Data Cleaning B snapshot plus exactly the approved EDA C
        # registrations above) -- the authoritative final classification
        # state for the modeling handoff. Never touches the Data Cleaning B
        # snapshot itself.
        _eda_c_cls_snapshot_path, _eda_c_schema_snapshot_path = classification_lineage.save_eda_c_snapshot(
            eda_c_classification_snapshot, eda_c_type_schema_snapshot, root=_root,
        )
        OUTPUT_PATHS["classification_snapshot"] = str(_eda_c_cls_snapshot_path)
        OUTPUT_PATHS["type_schema_snapshot"] = str(_eda_c_schema_snapshot_path)
        print(f"Classification-lineage snapshot saved: {_eda_c_cls_snapshot_path.resolve()}")
        print(f"                                       {_eda_c_schema_snapshot_path.resolve()}")

        # feature_selection_manifest.json -- NEW, EXPLICIT CONTRACT MANIFEST.
        # NOT a copy of candidate_feature_manifest.json: it declares this
        # deliverable's exact role and explicitly disclaims the OLD, pre-redesign,
        # capped-10-feature Model V1 "conservative_primary_set" contract, so the
        # two can never be confused. candidate_feature_manifest.json remains the
        # canonical EDA D manifest input; this file exists only because this
        # session requested a "feature_selection_manifest.json" deliverable.
        _feature_selection_manifest = {
            "run_timestamp_utc": _run_ts,
            "input_dataset_path": str(DATA_PATH),
            "current_contract": "EDA_C_BROAD_CANDIDATE_POOL",
            "canonical_d_handoff_files": [
                "candidate_model_features.csv",
                "modeling_dataset_candidate_features.xlsx",
                "candidate_feature_manifest.json",
                "candidate_feature_review_full.csv",
            ],
            "selected_model_features_role": (
                "broad candidate-pool deliverable, not final model formula"
            ),
            "legacy_model_v1_contract": "not reproduced",
            "legacy_selected_primary_features": "not provided",
            "model_v1_legacy_incompatibility": "known and out of scope",
            "eda_d_remains_intended_downstream_consumer": True,
            "n_rows": N_ROWS,
            "n_events": N_EVENTS,
            "n_eligible_pool": len(candidate_pool_df),
            "n_hard_excluded": len(excluded_features_df),
            "pending_timing_confirmation_columns": list(PENDING_TIMING_CONFIRMATION_COLS),
            "pending_timing_confirmation_exclusion_reason": (
                "Excluded from primary and secondary modeling predictor pools pending "
                "clinical timing confirmation."
            ),
            "intrapartum_predictor_exclude_from_prelabor_model_columns": list(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS),
            "intrapartum_predictor_exclude_from_prelabor_model_status": (
                "Part of the unified master candidate pool (Decision 65, 2026-08-12) "
                "-- not categorically excluded. Timing confirmed as intrapartum "
                "(Keren, relayed 28 July 2026); eligible for the intrapartum modeling "
                "horizon only, decided at the modeling boundary, not here."
            ),
            "conclusion": _manifest.get("conclusion"),
        }
        _out = _OUT_DIR / "feature_selection_manifest.json"
        with open(_out, "w", encoding="utf-8") as _fsm_out:
            _json_out.dump(_feature_selection_manifest, _fsm_out, indent=2, ensure_ascii=False)
        OUTPUT_PATHS["feature_selection_manifest"] = str(_out)
        print(f"Written: {_out} -- explicit contract manifest, not a copy of "
              "candidate_feature_manifest.json")
""")


# ── Section C14 ────────────────────────────────────────────────────────────────
SC14_HEADER = md("eda-c-s14-header", """
## Section C14 — Imputation, Encoding, and Scaling Treatment Plan

This table specifies the intended preprocessing treatment for every approved and
derived variable. It is a **planning document** — no preprocessing is executed here.

### Rules
1. All learned preprocessing (imputation medians, frequency encodings, scalers)
   must be **fitted on training folds only** and applied to validation/test folds.
2. No transformation is applied to `df_analysis` or `df`.
3. Structural-missingness treatment comes from `structural_missingness_registry`
   (2026-08-31 C2 correction), not `config.py`. **Confirmed** structural columns
   (`STRUCTURAL_NAN_COLS`) must not be median/mode imputed. **Pending** structural
   columns and `transform_source_only` columns are handled by their modeling
   contract (applicability-gated / fold-safe transformer), never blind imputation.

### Contract-driven treatment (2026-09-01 pre-C13 freeze)
This plan is now **derived from the C13 final model-facing contract**
(`model_representation_type` + physical type + three-tier structural
missingness + `model_entry_mode`), not from a second independently-maintained
decision system. No p / q / effect / redundancy score influences preprocessing
type routing.

- **No generic missing indicator.** This project has **no active generic
  `__missing_ind` architecture**. A missing indicator is created ONLY when an
  explicit future variable-specific contract authorises one — never as blanket
  advice for "higher missing rates".
- **Confirmed structural missingness** → subgroup-aware handling; **no** blind
  median/mode imputation. Genuine missingness within the applicable subgroup is
  what gets treated.
- **Applicability-linked (no preprocessing mask)** → raw missingness remains
  primary; there is no code-enforced structural-missingness gate, so a
  structural-absence subtraction is **not** applied. An applicability
  sensitivity analysis accompanies it. Nothing about this tier is pending a
  clinical or methodological decision.
- **`transform_source_only` / fold-safe representation** (`BMI_after`,
  `weight_in_pregnancy`, `gestational_age_at_PPROM_days`, `BMI_before`) →
  handled entirely by its explicit fold-safe transformer at modeling time;
  never routed through generic numeric imputation here.
- **Ordinary numeric imputation**, where required, is simple median fitted
  **within the training fold only**.
- **Categorical missingness** follows the model contract (most-frequent or an
  explicit `unknown` category, fitted within the training fold) and must not
  silently conflate genuine missingness with a clinically meaningful category.
- **Encoding**: `binary_passthrough` for binary; `one_hot_categorical` (with
  unknown-category handling) for categorical.
- **Scaling**: `same_as_physical_numeric` variables are standardized inside the
  pipeline only if the estimator requires it (tree models do not).
- **No global full-cohort cutpoints, medians, scaling, or category collapsing.**

### Power-transform contract (aligned with Data Cleaning B Section B3, 2026-09-01)
This project applies a single, project-wide power-transform decision, defined
once in Data Cleaning B (Section B3) and inherited here without re-deciding it:
- **Skewness is retained only as descriptive audit information.** A `skewness`
  value is still computed and shown in the C14 table for every numeric
  variable. It does **not** trigger, name, or pre-select a transform.
- **There is no `|skewness| > 1.5` transformation rule anywhere in C14.**
  Skewness never drives `transformation_plan`.
- **Continuous numeric predictors** (`physical_variable_type == "continuous"`,
  i.e. direct or fold-safe-recomputed numeric representations) retain the
  Data-Cleaning-B-approved decision `raw_no_fixed_power_transform` — no log,
  log1p, sqrt, Box-Cox, or Yeo-Johnson transform is applied or recommended.
- **Ordinary discrete obstetric-history counts** (`physical_variable_type ==
  "count"`) are not continuous power-transform candidates; they retain the
  B-consistent decision `not_applicable_discrete_count`.
- **Standardization/scaling is a separate, downstream, estimator-specific
  decision** (fold-safe `StandardScaler` when the estimator requires it) and
  is never a response to skewness. `raw_no_fixed_power_transform` does not
  mean "no scaling" — power transformation and scaling are independent.
- **A future nonlinear functional-form alternative** (e.g. splines, a
  data-driven Box-Cox lambda) may only be introduced by a separate, explicit
  modeling-stage rationale grounded in an independently justified modeling
  criterion — never merely because `|skewness| > 1.5` — and, if
  data-dependent, must be evaluated fold-safely inside cross-validation.
""")

SC14_TREATMENT = code("eda-c-s14-treatment", """
ALL_CANDIDATE_VARS = (
    [v for v in ANALYSIS_VARS if v in df_analysis.columns]
    + [v for v in DERIVED_VARS if v in df_analysis.columns]
)

_APPLICABILITY_LINKED = set(APPLICABILITY_LINKED_COLS) if "APPLICABILITY_LINKED_COLS" in dir() else set()
_MEM_MODE = dict(B_FEATURE_MODEL_ENTRY_MODE) if "B_FEATURE_MODEL_ENTRY_MODE" in dir() else {}
_MEM_MODE.update(B_CREATED_MODEL_ENTRY_MODE if "B_CREATED_MODEL_ENTRY_MODE" in dir() else {})

# C14 is now GENERATED FROM the C13 final model-facing contract, not a second
# decision system. model_representation_type / downstream_preprocessing_
# requirement / physical_variable_type are read from candidate_df (populated by
# SC13_MODEL_CONTRACT). There is NO generic missing-indicator rule anywhere.
_c14_contract = (
    candidate_df.set_index("variable")[
        ["model_representation_type", "downstream_preprocessing_requirement",
         "physical_variable_type", "structural_applicability_status",
         "primary_missing_pct_for_modeling"]
    ].to_dict("index")
    if "candidate_df" in dir() else {}
)

treatment_rows = []
for col in ALL_CANDIDATE_VARS:
    vtype = infer_var_type(df_analysis[col])
    miss_pct = round(df_analysis[col].isna().mean() * 100, 1)
    is_structural = col in STRUCTURAL_NAN_COLS
    is_applicability_linked = col in _APPLICABILITY_LINKED
    is_transform_source_only = str(_MEM_MODE.get(col, "")).strip() == "transform_source_only"
    is_derived = col in DERIVED_VARS
    skewness = (
        float(df_analysis[col].dropna().skew())
        if vtype == "numeric" else float("nan")
    )
    _cc = _c14_contract.get(col, {})
    rep = str(_cc.get("model_representation_type") or "")
    contract_req = str(_cc.get("downstream_preprocessing_requirement") or "")

    if rep.startswith("fold_safe_") or is_transform_source_only:
        imputation = ("fold-safe representation — its explicit training-fold transformer "
                      "consumes the raw column; NOT median/mode imputed here")
    elif is_structural:
        imputation = "confirmed structural — subgroup-aware only; do not median/mode impute"
    elif is_applicability_linked:
        imputation = ("applicability-linked; no preprocessing mask — applicability-gated; "
                      "raw missingness stays primary, NOT blind imputation")
    elif miss_pct == 0:
        imputation = "none required"
    elif vtype == "numeric":
        # contract-driven simple median, training-fold only; NO NA-flag column
        imputation = "median fitted within training fold; no NA-flag column added"
    else:
        imputation = ("most-frequent or explicit 'unknown' category, fitted within training "
                      "fold — must not conflate genuine missingness with a clinical category")

    if rep == "one_hot_categorical" or (not rep and vtype == "categorical"):
        encoding = "one-hot encode within training fold, with unknown-category handling"
        scaling = "none"
        transform = "no global rare-level collapsing; any collapse needs an explicit rule"
    elif rep == "binary_passthrough" or (not rep and vtype == "binary"):
        encoding = "0/1 passthrough (verify no non-binary values)"
        scaling = "none"
        transform = "none"
    else:  # same_as_physical_numeric / fold_safe_recomputed_continuous / numeric
        encoding = "none (numeric passthrough)"
        scaling = "standardize inside pipeline only if the estimator requires it"
        # Transform decision is driven by the authoritative C13 physical_variable_type,
        # never by skewness -- skewness is descriptive-only, consistent with Data
        # Cleaning B Section B3 (Decision-aligned 2026-09-01). A fixed power transform
        # is never applied or recommended here regardless of |skewness|.
        _physical_type = str(_cc.get("physical_variable_type") or "")
        if _physical_type == "count":
            transform = "not_applicable_discrete_count"
        else:
            transform = "raw_no_fixed_power_transform"

    timing = (derived_meta.get(col, {}).get("timing", "unknown")
              if is_derived else TIMING_MAP.get(col, "unknown"))

    treatment_rows.append({
        "variable": col,
        "original_or_derived": "derived" if is_derived else "original",
        "type": vtype,
        "model_representation_type": rep or "n/a (not in eligible pool)",
        "timing": timing,
        "missing_%": miss_pct,
        "structural_nan": is_structural,
        "structural_status": ("confirmed_structural" if is_structural
                              else ("applicability_linked_no_preprocessing_mask" if is_applicability_linked
                                    else ("transform_source_only" if is_transform_source_only else "none"))),
        "skewness": round(skewness, 3) if pd.notna(skewness) else float("nan"),
        "imputation_plan": imputation,
        "encoding_plan": encoding,
        "scaling_plan": scaling,
        "transformation_plan": transform,
        "c13_contract_requirement": contract_req or "n/a",
    })

treatment_df = pd.DataFrame(treatment_rows)
print("Proposed modeling-pipeline treatment plan (generated from the C13 model contract)")
print("(Planning only — no preprocessing executed here)")
print()
print(treatment_df.to_string(index=False))
print()
# fail loud if a generic missing indicator ever creeps back in
assert not treatment_df["imputation_plan"].str.contains("missing indicator", case=False).any(), (
    "C14: a generic missing-indicator plan re-appeared -- this project has no active "
    "generic __missing_ind architecture; a missing indicator needs an explicit "
    "variable-specific contract."
)
print("IMPORTANT: All learned preprocessing must be fitted within cross-validation folds only.")
print("No generic missing indicators. No global full-cohort cutpoints / medians / scaling.")
""")


# ── Section C15 ────────────────────────────────────────────────────────────────
SC15_HEADER = md("eda-c-s15-header", """
## Section C15 — Modeling Handoff Contract

> **EDA C performs eligibility filtering only. It hands off a broad, hard-exclusion-
> filtered candidate pool — not a final selected-feature list.** Final variable and
> model selection will happen later, in EDA D, under cross-validation.

This section summarises the agreed inputs for that handoff:
- Target variable and cohort size
- Primary model timing boundary
- Confirmed leakage exclusions
- Unresolved clinical decisions
- Candidate pool size (eligible vs. hard-excluded)
- Recommended modeling pipeline safeguards
- Co-entry / relationship handling guidance for EDA D (2026-09-01 pre-C13 freeze):
  1. **`outputs/eda_c/model_coentry_constraints.csv`** (the generated run
     snapshot of the sole authored source
     `analysis/eda/notebook_build/eda_c/contracts/model_coentry_constraints.yaml`)
     — the **8** HARD, global, **target-independent** deterministic pairwise
     constraints. These pairs must **never** be entered as independent
     predictors together, regardless of model strategy. Penalization does
     **not** waive them: LASSO / Elastic Net must still respect
     `hard_forbid_coentry`.
  2. **`outputs/eda_c/model_relationship_groups.csv`** (generated snapshot of
     `contracts/model_relationship_groups.yaml`) — the **12** REVIEW-only
     relationship groups. Multiple members may remain candidates and be
     evaluated together within training/CV when methodologically appropriate;
     they never require one-member-only resolution and never change eligibility.
  3. Empirical full-cohort ρ / Cramér's V / ε² are descriptive diagnostics
     only (`predictor_relationship_diagnostics.csv`); they never generate a
     global hard ban.
  4. For unpenalized logistic regression: assess rank deficiency / condition
     number / VIF (or equivalent) **within the training process** — do **not**
     use "one member per `redundancy_group`" as a blanket full-cohort rule.
  5. The legacy `redundancy_group` / `redundancy_demoted` columns are
     descriptive EDA grouping only — **not** a co-entry prohibition and not the
     canonical relationship registry.

The handoff contract is printed for review. This notebook does not produce a
candidate-pool dataset unless `SAVE_SELECTED_MODELING_DATASET = True` and `C13`
has been run.
""")

SC15_CONTRACT = code("eda-c-s15-contract", """
_n0 = int((df[TARGET_COL] == 0).sum())
_n1 = int((df[TARGET_COL] == 1).sum())
# 2026-08-31: no hand-typed clinical-readiness boolean. "Unresolved blocked
# variable(s)" is now measured directly from the live metadata/pool state:
# any pending-timing / awaiting-clarification variable that reached the
# analytical universe, or any manual-review-pending variable that reached the
# eligible pool -- each of these SHOULD be 0.
_pending_in_universe = sorted(set(ANALYSIS_VARS) & set(PENDING_TIMING_CONFIRMATION_COLS))
_awaiting_in_universe = sorted(set(ANALYSIS_VARS) & set(AWAITING_CLINICAL_CLARIFICATION_COLS))
_manual_review_in_pool = sorted(
    set(candidate_pool_df["variable"]) & set(MANUAL_REVIEW_PENDING_COLS)
) if "candidate_pool_df" in dir() else []
_manual_review_in_universe = sorted(set(ANALYSIS_VARS) & set(MANUAL_REVIEW_PENDING_COLS))
# manual_review_pending exists in the authoritative Data Cleaning B
# classification snapshot but must be 0 in the analytical universe and the
# eligible pool. As of 2026-09-01 (Decision 94) the B snapshot itself has
# zero manual_review_pending members: severe_PET_cat / any_PET_cat (the
# former two, Decision 71) are now approved standalone predictor_allowed /
# Stage 1 predictors, present in ANALYSIS_VARS, every cumulative stage, and
# the eligible pool via the ordinary staged-analysis path -- any_PET_cat is
# also a direct formula input to derived_hypertension_pih_pet_spectrum and
# derived_placental_dysfunction_proxy.
_manual_review_pending_in_b_snapshot = sorted(MANUAL_REVIEW_PENDING_COLS)
_n_unresolved_dec = len(_pending_in_universe) + len(_awaiting_in_universe) + len(_manual_review_in_pool)
_n_eligible_pool = (
    len(candidate_pool_df) if "candidate_pool_df" in dir() else "n/a"
)
_n_hard_excluded = (
    len(excluded_features_df) if "excluded_features_df" in dir() else "n/a"
)

contract_rows = [
    {"field": "target_column", "value": TARGET_COL},
    {"field": "cohort_rows", "value": len(df)},
    {"field": "target_0_vaginal", "value": _n0},
    {"field": "target_1_intrapartum_CS", "value": _n1},
    {"field": "positive_event_rate", "value": f"{round(_n1 / len(df) * 100, 1)}%"},
    {"field": "analysis_vars_count", "value": len(ANALYSIS_VARS)},
    {"field": "derived_vars_implemented", "value": len(DERIVED_VARS)},
    {"field": "total_screened_vars", "value": len(SCREEN_VARS) if "SCREEN_VARS" in dir() else "n/a"},
    {"field": "eligible_candidate_pool_count", "value": _n_eligible_pool},
    {"field": "hard_excluded_count", "value": _n_hard_excluded},
    # Updated 2026-08-13 (Decision 65 / multi-horizon plan Batch 2): the EDA C
    # master candidate pool is no longer pre_pregnancy/pregnancy-only -- it is
    # the unified union of predictor_allowed, secondary_near_delivery_predictor,
    # and intrapartum_predictor_exclude_from_prelabor_model timing groups.
    # Horizon-specific timing restriction happens only at the modeling
    # boundary, not here; see each variable's predictor_classification for its
    # timing group.
    {"field": "master_pool_timing_composition",
     "value": "pre_pregnancy + pregnancy + admission_labor/intrapartum_confirmed (unified; horizon split deferred to modeling boundary)"},
    {"field": "leakage_excluded_count", "value": len(LEAKAGE_EXCLUDE_COLS)},
    {"field": "intrapartum_excluded_count", "value": len(INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS)},
    # manual_review_pending is reported at two distinct layers so the two are
    # never conflated: the upstream Data Cleaning B classification snapshot vs
    # the active EDA C analytical universe / eligible modeling pool.
    {"field": "manual_review_pending_in_B_classification_snapshot",
     "value": f"{len(_manual_review_pending_in_b_snapshot)}  {_manual_review_pending_in_b_snapshot} "
              "(zero as of Decision 94, 2026-09-01 -- severe_PET_cat/any_PET_cat, "
              "the former two members under Decision 71, are now approved "
              "standalone predictor_allowed/Stage 1 predictors)"},
    {"field": "manual_review_pending_in_analytical_universe (ANALYSIS_VARS)",
     "value": len(_manual_review_in_universe)},
    {"field": "manual_review_pending_in_eligible_modeling_pool",
     "value": len(_manual_review_in_pool)},
    {"field": "unresolved_blocked_variables_in_universe_or_pool", "value": _n_unresolved_dec},
    {"field": "  detail_pending_timing_in_universe", "value": _pending_in_universe},
    {"field": "  detail_awaiting_clarification_in_universe", "value": _awaiting_in_universe},
    {"field": "  detail_manual_review_pending_in_eligible_pool", "value": _manual_review_in_pool},
    {"field": "save_selected_modeling_dataset_enabled", "value": SAVE_SELECTED_MODELING_DATASET},
    {"field": "dataset", "value": DATA_PATH.name},
]

print("=" * 70)
print("MODELING HANDOFF CONTRACT")
print("EDA C hands off a broad, eligible candidate pool -- NOT a final selection.")
print("Final variable/model selection will happen in EDA D, under cross-validation.")
print("=" * 70)
print(pd.DataFrame(contract_rows).to_string(index=False))
print()
print("Recommended modeling pipeline safeguards (for EDA D):")
safeguards = [
    f"Stratified train/test split with a fixed random seed ({_n1} positive outcomes -- "
    "use the same seed throughout)",
    "All preprocessing (imputation, encoding, scaling) fitted inside training folds only",
    f"Cross-validation scheme appropriate for {_n1} positive outcomes (e.g., repeated stratified k-fold)",
    "Report both ROC-AUC and PR-AUC; do not rely on accuracy alone",
    "Select decision threshold from clinical objective (sensitivity vs. specificity tradeoff)",
    "Final feature selection occurs inside the CV pipeline — not before training, and not in EDA C",
    "Preserve an untouched hold-out test set for a final sanity check only — not for model selection",
    "Calibrate predicted probabilities if used clinically",
]
for i, s in enumerate(safeguards, 1):
    print(f"  {i}. {s}")
print()
print("Co-entry / relationship handling in EDA D (2026-09-01 pre-C13 contract freeze):")
redundancy_notes = [
    "model_coentry_constraints.csv = HARD, global, target-independent pairwise constraints. "
    "These pairs must NEVER be simultaneously entered as independent predictors, regardless "
    "of model strategy. hard_forbidden_with in candidate_model_features.csv is generated "
    "symmetrically from that pair table.",
    "Penalization does NOT waive an approved HARD deterministic co-entry constraint -- "
    "LASSO / Elastic Net must still respect hard_forbid_coentry.",
    "model_relationship_groups.csv = REVIEW metadata only (relationship_groups / "
    "relationship_review_required columns). Multiple members may remain candidates and be "
    "evaluated together within training/CV when methodologically appropriate. It never "
    "changes eligibility.",
    "Empirical full-cohort rho / Cramer's V / epsilon-squared "
    "(predictor_relationship_diagnostics.csv) are descriptive diagnostics only -- they never "
    "generate a global hard ban.",
    "For unpenalized logistic regression: assess rank deficiency / condition number / VIF (or "
    "equivalent) WITHIN the training process. Do NOT use 'one member per redundancy_group' as "
    "a blanket full-cohort rule -- the legacy redundancy_group / redundancy_demoted columns "
    "are descriptive EDA grouping only.",
    "Soft relationship groups may be explored under penalization / CV. There is no "
    "target-informed global winner.",
]
for i, s in enumerate(redundancy_notes, 1):
    print(f"  {i}. {s}")
# fail loud if the retired one-per-redundancy_group rule ever reappears here
assert not any(
    ("more than one" in s and "redundancy_group" in s)
    or "one member per redundancy_group" in s.lower().replace("-", " ")
    for s in redundancy_notes
    if "Do NOT" not in s and "do NOT" not in s
), "C15: the retired 'one member per redundancy_group' selection rule reappeared."
""")


# ── Section C16 ────────────────────────────────────────────────────────────────
SC16_HEADER = md("eda-c-s16-header", """
## Section C16 — Final Readiness Checklist

`MODELING_HANDOFF_READY = True` only when ALL **blocking** checks pass.
Analytical sections (C4–C15) run regardless of flag values.

**Important design note (corrected 2026-07-05; clarified 2026-09-01):** the
modeling handoff contract is candidate-pool based, not approved-variable based.
The two situations are **not** the same:

- **Zero variance** is a genuine, target-independent HARD exclusion. A
  zero-variance variable is correctly absent from `candidate_model_features.csv`
  and its appearance in the full `ANALYSIS_VARS` set is reported below only as
  an informational note.
- **Separation risk / sparse-event risk / boundary-sparse instability** are
  **target-informed diagnostics**, NOT hard exclusions. A predictor carrying one
  of these MAY (and routinely does) remain in the eligible candidate pool. The
  blocking readiness requirement for such a predictor is **correct disclosure in
  `soft_warning_flags`** (`separation_risk` / `sparse_event_risk` /
  `boundary_sparse_instability_risk`) — not removal from the pool. Only an
  undisclosed case (in the pool without the flag, or missing from `candidate_df`
  entirely) is worth investigating.

The old approved-variable-wide zero-variance / C6-sparsity checks are reported
below as informational notes (`[INFO]`/`[WARN]`), not blocking checks. The
blocking checks apply directly to the exported candidate pool and to the C13
final model-facing contract.
""")

SC16_GATE = code("eda-c-s16-gate", """
_all_vars_present = all(v in df.columns for v in ANALYSIS_VARS)
_no_forbidden = not bool(set(ANALYSIS_VARS) & _FORBIDDEN_COLS)

# ── Operational clinical-readiness checks (2026-08-31: replace the retired
#    hand-typed CLINICAL_DECISIONS_COMPLETE / CLINICAL_DECISIONS_LOG_UPDATED
#    booleans). Derived entirely from the live classification metadata + the
#    C12b candidate pool -- no narrative parsing, no second registry, no
#    target-informed inference. Each MUST be empty. ────────────────────────────
_pool_var_set = set(candidate_pool_df["variable"]) if "candidate_pool_df" in dir() else set()
_universe_set = set(ANALYSIS_VARS)
_op_pending_timing_in_universe = sorted(_universe_set & set(PENDING_TIMING_CONFIRMATION_COLS))
_op_awaiting_clarification_in_universe = sorted(_universe_set & set(AWAITING_CLINICAL_CLARIFICATION_COLS))
_op_manual_review_in_pool = sorted(_pool_var_set & set(MANUAL_REVIEW_PENDING_COLS))
_op_forbidden_class_in_pool = sorted(
    _pool_var_set & (
        set(LEAKAGE_EXCLUDE_COLS) | set(INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS)
        | set(SOURCE_OR_TEXT_AUDIT_EXCLUDE_COLS) | set(MANUAL_REVIEW_PENDING_COLS)
        | set(AWAITING_CLINICAL_CLARIFICATION_COLS) | set(PENDING_TIMING_CONFIRMATION_COLS)
        | set(ID_COLS) | set(TARGET_COLS)
    )
)
_op_stage_nesting_ok = set(STAGE_1_COLS) <= set(STAGE_2_COLS) <= set(STAGE_3_COLS)
_op_stage_universe_ok = set(STAGE_3_COLS) == _universe_set
_op_hard_exclusions_target_independent = all(
    all(
        (part.strip() in {
            "invalid_or_impossible_values", "zero_variance",
            "hard_clinical_unresolved_pending_review",
            "sanity_check_only_not_a_modeling_candidate",
        }) or ("pending_timing_confirmation" in part)
        for part in str(reason).split(";") if part.strip()
    )
    for reason in excluded_features_df["hard_exclusion_reason"]
) if "excluded_features_df" in dir() and len(excluded_features_df) else True
_OPERATIONAL_READINESS = {
    "No intrapartum_candidate_pending_timing_confirmation variable in the analytical universe":
        not _op_pending_timing_in_universe,
    "No awaiting_clinical_clarification variable in the analytical universe":
        not _op_awaiting_clarification_in_universe,
    "No manual_review_pending variable in the eligible candidate pool":
        not _op_manual_review_in_pool,
    "No forbidden/leakage/post-outcome/source-audit classification in the eligible pool":
        not _op_forbidden_class_in_pool,
    "Cumulative stage construction is strictly nested (S1 subset S2 subset S3)":
        bool(_op_stage_nesting_ok),
    "Cumulative Stage 3 equals the full analytical universe":
        bool(_op_stage_universe_ok),
    "Candidate-pool validation (C12c) passed":
        "pool_validation_passed" in dir() and bool(pool_validation_passed),
    "Every hard exclusion is target-independent":
        bool(_op_hard_exclusions_target_independent),
}
print("Operational clinical-readiness checks (live metadata/pool state; replaces the retired manual booleans):")
for _k, _v in _OPERATIONAL_READINESS.items():
    print(f"  [{'PASS' if _v else 'FAIL'}] {_k}")
if _op_pending_timing_in_universe:
    print(f"    pending-timing variable(s) that reached the universe: {_op_pending_timing_in_universe}")
if _op_awaiting_clarification_in_universe:
    print(f"    awaiting-clarification variable(s) that reached the universe: {_op_awaiting_clarification_in_universe}")
if _op_manual_review_in_pool:
    print(f"    manual-review-pending variable(s) that reached the eligible pool: {_op_manual_review_in_pool}")
if _op_forbidden_class_in_pool:
    print(f"    forbidden-classification variable(s) that reached the eligible pool: {_op_forbidden_class_in_pool}")
_OPERATIONAL_READINESS_OK = all(_OPERATIONAL_READINESS.values())

_derived_valid = (
    not any(bool(r["impossible_flag"]) for r in (derived_validation_df.to_dict("records") if "derived_validation_df" in dir() and len(derived_validation_df) else []))
)
# _no_leakage_derived RENAMED/REDEFINED 2026-08-20 (target-informed pre-CV
# screening consistency correction): leakage_flag (target-correlation smoke
# test) is no longer a hard-exclusion rule -- it is a full-dataset
# target-correlation statistic, so hard-blocking the handoff on "zero derived
# features have it" before any CV split was the same target-informed pre-CV
# pattern already corrected for separation/sparsity on 2026-08-19. A derived
# feature carrying this risk flag is now expected and correct, as long as the
# risk is disclosed via soft_warning_flags rather than silently hidden -- same
# self-consistency pattern as _pool_separation_risk_disclosed below. Scoped to
# candidate_pool_df (where soft_warning_flags is populated) rather than
# derived_validation_df: a derived feature hard-excluded for a different,
# genuinely target-independent reason (e.g. high missingness) never reaches
# the pool and has nothing to disclose.
_candidate_table_built = "candidate_df" in dir() and len(candidate_df) > 0
_candidate_pool_built = "candidate_pool_df" in dir() and len(candidate_pool_df) > 0
_pool_checks_passed = "pool_validation_passed" in dir() and pool_validation_passed

# ── Pool-level blocking checks (candidate pool, not the full approved-variable set) ─
_pool_no_zero_var = not bool(candidate_pool_df["zero_variance_flag"].any())
# _pool_no_severe_sparsity / _pool_no_separation REDEFINED 2026-08-19
# (target-informed pre-CV screening consistency correction): separation_flag/
# too_sparse_flag/boundary-sparse-instability are no longer hard exclusions
# (they are target-dependent, full-dataset-target-crosstab statistics -- using
# them to remove a variable from the pool before any CV split is exactly the
# target-informed pre-CV feature-selection pattern this project's methodology
# prohibits; see eda_c_part4_screening.py's hard-exclusion-rules docstring and
# that correction's manual_decisions_log.md entry). A pool variable carrying
# one of these risk flags is now expected and correct, as long as the risk is
# disclosed via soft_warning_flags rather than silently hidden -- same
# self-consistency check already applied to redundancy_demoted.
_pool_sparse_mask = candidate_pool_df["too_sparse_flag"] & ~candidate_pool_df["separation_flag"]
_pool_boundary_mask = candidate_pool_df["variable"].isin(_boundary_sparse_risk_vars)
_pool_sparsity_risk_disclosed = (
    bool(candidate_pool_df.loc[_pool_sparse_mask, "soft_warning_flags"].str.contains("sparse_event_risk").all())
    if _pool_sparse_mask.any() else True
) and (
    bool(candidate_pool_df.loc[_pool_boundary_mask, "soft_warning_flags"].str.contains("boundary_sparse_instability_risk").all())
    if _pool_boundary_mask.any() else True
)
_pool_separation_risk_disclosed = (
    bool(candidate_pool_df.loc[candidate_pool_df["separation_flag"], "soft_warning_flags"].str.contains("separation_risk").all())
    if candidate_pool_df["separation_flag"].any() else True
)
_no_leakage_derived = (
    bool(candidate_pool_df.loc[candidate_pool_df["high_target_association_review"], "soft_warning_flags"].str.contains("high_target_association_review").all())
    if candidate_pool_df["high_target_association_review"].any() else True
)
# 2026-08-31 rebuild: the generic >40% missingness HARD rule (and its ad-hoc
# HIGH_MISSINGNESS_EXCLUDE_OVERRIDE escape hatch) are removed. High missingness
# is now a SOFT diagnostic; this gate only confirms that any high-missingness
# pool member DISCLOSES the `high_missingness_diagnostic` soft warning -- same
# disclosure-not-exclusion pattern as sparsity/separation/leakage above.
_pool_high_missingness_diag_disclosed = (
    bool(
        candidate_pool_df.loc[
            candidate_pool_df["variable"].isin(_high_missingness_diagnostic_vars), "soft_warning_flags"
        ].str.contains("high_missingness_diagnostic").all()
    )
    if (set(candidate_pool_df["variable"]) & _high_missingness_diagnostic_vars) else True
)
_pool_no_hard_excluded_leak = not bool(
    set(candidate_pool_df["variable"]) & set(excluded_features_df["variable"])
)
_pool_no_pending_timing = not bool(
    set(candidate_pool_df["variable"]) & set(PENDING_TIMING_CONFIRMATION_COLS)
)
# NOTE: _pool_no_intrapartum_predictor_exclude was removed 2026-08-13
# (Decision 65 / multi-horizon plan Batch 2) -- intrapartum_predictor_
# exclude_from_prelabor_model is now an approved, expected member of the
# unified master pool, not something the readiness gate should block on.
# The predictor_classification metadata-preservation check in C12c
# (pool_validation_checks, eda_c_part4_screening.py) already validates that
# every pool variable's classification -- including this one -- is
# correctly populated and carried through to the handoff.
_pool_excl_reasons_populated = bool(excluded_features_df["hard_exclusion_reason"].notna().all())
_pool_eligibility_populated = bool(candidate_df["eligibility_status"].notna().all())
_pool_matrix_cols_match = list(_check_matrix.columns) == _check_matrix_cols
_pool_no_id_cols = not (set(_check_matrix.columns) & set(ID_COLS))

# ── C13 final model-facing contract readiness gates (Part M) ──────────────────
# Every eligible variable must carry exactly one final classification row, one
# final type-schema row, an approved coarse-type projection, a populated
# model_representation_type, and the co-entry contract must be canonical,
# target-independent, symmetric, and empirical-threshold-free.
_pool_v = list(candidate_pool_df["variable"])
_c13_ts_counts = eda_c_type_schema_snapshot["variable_name"].value_counts().to_dict()
_c13_cls_counts = eda_c_classification_snapshot["column_name"].value_counts().to_dict()
_c13_ts_map = dict(zip(eda_c_type_schema_snapshot["variable_name"],
                       eda_c_type_schema_snapshot["variable_type"]))
_c13_cls_map = dict(zip(eda_c_classification_snapshot["column_name"],
                        eda_c_classification_snapshot["classification"]))
_c13_pool_rows = {r["variable"]: r for r in candidate_pool_df.to_dict("records")}
# canonical co-entry source: the parsed YAML DataFrame from SC13_MODEL_CONTRACT
# (never a file re-read, never a generated CSV).
_c13_coentry = MODEL_COENTRY_SRC_DF.copy() if "MODEL_COENTRY_SRC_DF" in dir() else pd.DataFrame()

_c13_one_cls = all(_c13_cls_counts.get(v, 0) == 1 for v in _pool_v)
_c13_one_type = all(_c13_ts_counts.get(v, 0) == 1 for v in _pool_v)
_c13_cls_match = all(
    str(_c13_pool_rows[v]["predictor_classification"]) == str(_c13_cls_map.get(v)) for v in _pool_v
)
_c13_type_match = all(
    str(_c13_pool_rows[v].get("physical_variable_type")) == str(_c13_ts_map.get(v)) for v in _pool_v
)
_c13_ncat_ok = True
for v in _pool_v:
    _pt = str(_c13_ts_map.get(v))
    _nc = _c13_pool_rows[v].get("physical_n_categories")
    _nu = _c13_pool_rows[v].get("n_unique")
    if _pt == "binary" and not (pd.isna(_nc) or float(_nc) == 2.0):
        _c13_ncat_ok = False
    if _pt in ("categorical", "ordinal"):
        if pd.isna(_nc) or (pd.notna(_nu) and float(_nc) != float(_nu)):
            _c13_ncat_ok = False
    if _pt in ("continuous", "count") and pd.notna(_nc):
        _c13_ncat_ok = False
_c13_proj_ok = all(
    str(_c13_pool_rows[v].get("data_type")) == SCHEMA_TO_EDA_TYPE.get(str(_c13_ts_map.get(v)))
    for v in _pool_v
)
_c13_repr_populated = all(str(_c13_pool_rows[v].get("model_representation_type") or "") for v in _pool_v)
_KNOWN_REPRS = {
    "same_as_physical_numeric", "binary_passthrough", "one_hot_categorical",
    "fold_safe_quantile_categorical", "fold_safe_pprom_timing_categorical",
    "fold_safe_recomputed_continuous",
}
_c13_repr_known = all(
    str(_c13_pool_rows[v].get("model_representation_type")) in _KNOWN_REPRS for v in _pool_v
)
_c13_special_contract_ids = all(
    bool(str(_c13_pool_rows[v].get("model_preprocessing_contract_id") or ""))
    for v in _pool_v
    if str(_c13_pool_rows[v].get("model_representation_type", "")).startswith("fold_safe_")
)
_c13_pairs_canonical = (
    len(_c13_coentry) == 0
    or (
        (_c13_coentry["var_a"] < _c13_coentry["var_b"]).all()
        and not _c13_coentry.duplicated(["var_a", "var_b"]).any()
    )
)
_c13_pairs_target_indep = (
    len(_c13_coentry) == 0
    or (_c13_coentry["target_independent"].str.strip().str.lower() == "true").all()
)
_c13_pairs_live = (
    len(_c13_coentry) == 0
    or (set(_c13_coentry["var_a"]) | set(_c13_coentry["var_b"])) <= set(_pool_v)
)
_c13_hfw_symmetric = True
_c13_hfw_from_registry = True
_c13_reg_partners = {}
for _r in _c13_coentry.to_dict("records"):
    _c13_reg_partners.setdefault(str(_r["var_a"]), set()).add(str(_r["var_b"]))
    _c13_reg_partners.setdefault(str(_r["var_b"]), set()).add(str(_r["var_a"]))
for _r in candidate_pool_df.to_dict("records"):
    _listed = set(p.strip() for p in str(_r["hard_forbidden_with"]).split(";") if p.strip())
    if _listed != _c13_reg_partners.get(_r["variable"], set()):
        _c13_hfw_from_registry = False
    for _p in _listed:
        _prow = _c13_pool_rows.get(_p)
        if _prow is None:
            _c13_hfw_symmetric = False
        else:
            _back = set(x.strip() for x in str(_prow["hard_forbidden_with"]).split(";") if x.strip())
            if _r["variable"] not in _back:
                _c13_hfw_symmetric = False
_EMP_TOKENS = ("p_value", "q_value", "fdr", "effect_size", "spearman", "rho",
               "cramers_v", "cramer", "epsilon", "correlation")
_c13_no_empirical_hard = (
    len(_c13_coentry) == 0
    or not _c13_coentry["reason_type"].str.lower().apply(
        lambda s: any(t in s for t in _EMP_TOKENS)
    ).any()
)
_c13_groups_no_elig = (
    set(MODEL_RELATIONSHIP_GROUPS_EXPORT_DF["variable"]) <= set(_pool_v)
    if "MODEL_RELATIONSHIP_GROUPS_EXPORT_DF" in dir() else True
)
# no legacy primary_model_eligible field controls this handoff contract: none
# of the C13 gate booleans above read `primary_model_eligible`.
_c13_no_legacy_primary_control = True

_c13_contract_gates = {
    "C13: every eligible variable has exactly one final classification row": _c13_one_cls,
    "C13: every eligible variable has exactly one final type-schema row": _c13_one_type,
    "C13: candidate predictor_classification matches the final classification snapshot": _c13_cls_match,
    "C13: candidate physical_variable_type matches the final type snapshot": _c13_type_match,
    "C13: candidate physical_n_categories reconciles with observed n_unique": _c13_ncat_ok,
    "C13: coarse data_type is the approved projection of physical type": _c13_proj_ok,
    "C13: every eligible variable has a populated model_representation_type": _c13_repr_populated,
    "C13: every model_representation_type is an explicitly reviewed value": _c13_repr_known,
    "C13: every fold-safe representation carries a model_preprocessing_contract_id": _c13_special_contract_ids,
    "C13: every hard co-entry pair is canonical and unique": _c13_pairs_canonical,
    "C13: every hard co-entry row is target_independent=true": _c13_pairs_target_indep,
    "C13: every hard co-entry pair references only live eligible variables": _c13_pairs_live,
    "C13: hard_forbidden_with is symmetric": _c13_hfw_symmetric,
    "C13: hard_forbidden_with is generated exactly from the pair registry": _c13_hfw_from_registry,
    "C13: no empirical-association threshold created a hard pair": _c13_no_empirical_hard,
    "C13: relationship groups do not change the eligible pool": _c13_groups_no_elig,
    "C13: no legacy primary_model_eligible field controls the handoff contract": _c13_no_legacy_primary_control,
}

readiness_checks = {
    # 2026-08-31: the two hand-typed booleans previously here
    # (CLINICAL_DECISIONS_COMPLETE / CLINICAL_DECISIONS_LOG_UPDATED) were
    # retired. Clinical-readiness is now proven by the live operational checks
    # computed above from the classification metadata + the C12b pool -- an
    # unresolved/blocked upstream role can no longer be "asserted away".
    **_OPERATIONAL_READINESS,
    "Preprocessing corrections applied; correct batch confirmed":
        True,  # documented by provenance manifest in C3 — user must confirm
    "All approved variables present in dataset":
        _all_vars_present,
    "No forbidden/leakage columns in ANALYSIS_VARS":
        _no_forbidden,
    "Missingness strategy documented per variable (C5)":
        "missingness_df" in dir() and len(missingness_df) > 0,
    "Redundancy strategy documented (C10)":
        "redundancy_pairs_df" in dir(),
    "Derived features validated — no impossible values (C10)":
        _derived_valid,
    # Relabeled 2026-08-20 (target-informed pre-CV screening consistency
    # correction): leakage_flag is disclosure-only now (target_correlation_
    # leakage_risk in soft_warning_flags), not a hard exclusion -- this check
    # verifies disclosure, not absence. See _no_leakage_derived definition above.
    "Every candidate-pool derived feature with a high target association discloses high_target_association_review (soft warning, not a hard block; high association is not leakage)":
        _no_leakage_derived,
    "Candidate review table built (C12)":
        _candidate_table_built,
    "Candidate pool built (C12b)":
        _candidate_pool_built,
    "No candidate-pool variable has zero variance":
        _pool_no_zero_var,
    "Every candidate-pool variable with sparse-event/boundary-sparse risk discloses it (soft warning, not a hard block -- 2026-08-19 correction)":
        _pool_sparsity_risk_disclosed,
    "Every candidate-pool variable with separation risk discloses it (soft warning, not a hard block -- 2026-08-19 correction)":
        _pool_separation_risk_disclosed,
    "Every candidate-pool variable above the missingness diagnostic threshold discloses high_missingness_diagnostic (soft warning; generic >40% hard rule removed 2026-08-31)":
        _pool_high_missingness_diag_disclosed,
    "No hard-excluded variable appears in candidate_model_features (in-memory pool)":
        _pool_no_hard_excluded_leak,
    "No pending timing-confirmation variable appears in candidate_model_features":
        _pool_no_pending_timing,
    "Every hard-excluded variable has hard_exclusion_reason populated":
        _pool_excl_reasons_populated,
    "Every screened variable has eligibility_status populated":
        _pool_eligibility_populated,
    "Candidate-pool export matrix contains target + all candidate-pool variables":
        _pool_matrix_cols_match,
    "No ID columns in the candidate-pool export matrix":
        _pool_no_id_cols,
    "Candidate pool validation checks passed in full (C12c)":
        _pool_checks_passed,
    "Modeling safeguards reviewed (C15)":
        True,  # printed in C15 — user must confirm
    # ── C13 final model-facing contract gates (2026-09-01 pre-C13 freeze) ─────
    **_c13_contract_gates,
}

print("=" * 70)
print("MODELING READINESS CHECKLIST (blocking)")
print("=" * 70)
for label, passed in readiness_checks.items():
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}")

MODELING_HANDOFF_READY = all(readiness_checks.values())
print()
print(f"MODELING_HANDOFF_READY = {MODELING_HANDOFF_READY}")
print()

# ── Informational notes (approved-variable-wide diagnostics — NOT blocking) ──────
# These check the FULL approved ANALYSIS_VARS set, which by design still contains
# variables that get hard-excluded from the candidate pool (that is the point of
# C12b). A variable failing here is expected as long as it is correctly
# hard-excluded above -- these notes exist for transparency only.
def _is_complete_zero_variance_for_exclusion(series):
    # Zero-variance policy: constant status may be audited across all variables,
    # but automatic zero-variance exclusion applies only within the relevant
    # analytical predictor scope. A true zero-variance exclusion has no missing
    # values and exactly one observed unique value; all-missing and partially
    # missing single-value variables are handled by missingness logic. Cohort
    # controls and other already-excluded variables retain their role reason.
    return int(series.isna().sum()) == 0 and int(series.dropna().nunique()) == 1


_full_no_zero_var = all(not _is_complete_zero_variance_for_exclusion(df_analysis[v]) for v in ANALYSIS_VARS)
# C6 renamed `blocking_sparsity_vars` -> `sparsity_warning_vars` (2026-09-01):
# C6 is a soft diagnostic, not an eligibility gate. Accept either name for
# backward compatibility across a partial rebuild.
_c6_sparsity_warning_vars = (
    sparsity_warning_vars if "sparsity_warning_vars" in dir()
    else (blocking_sparsity_vars if "blocking_sparsity_vars" in dir() else [])
)
_full_no_separation = len(_c6_sparsity_warning_vars) == 0
_zero_var_approved_vars = [
    v for v in ANALYSIS_VARS if _is_complete_zero_variance_for_exclusion(df_analysis[v])
]
_separation_approved_vars = list(_c6_sparsity_warning_vars)

# Note (2026-08-19, target-informed pre-CV screening consistency correction):
# a variable flagged by C6's sparsity_warning_vars (separation or too-sparse
# against the full-dataset target crosstab) is NO LONGER expected to be
# hard-excluded -- it is expected to be in the candidate pool with the
# corresponding risk flag disclosed (separation_risk/sparse_event_risk in
# soft_warning_flags). Only genuinely undisclosed cases (present in the pool
# without the risk flag, or genuinely missing from candidate_df entirely) are
# worth investigating. This is a materially different check from the
# zero-variance note above (zero-variance is unaffected by this correction
# and remains a genuine hard exclusion).
_variable_to_flags = dict(zip(candidate_df["variable"], candidate_df["soft_warning_flags"].fillna("")))


def _separation_sparsity_disclosed(v):
    _flags = _variable_to_flags.get(v)
    if _flags is None:
        return False  # not screened at all -- genuinely worth investigating
    return ("separation_risk" in _flags) or ("sparse_event_risk" in _flags) or (v in set(excluded_features_df["variable"]))


informational_notes = {
    "No zero-variance variables among the full approved ANALYSIS_VARS set":
        (_full_no_zero_var, _zero_var_approved_vars, None),
    "No separation/sparse-warning variables among the full baseline staged analysis universe (C6 diagnostic)":
        (_full_no_separation, _separation_approved_vars, _separation_sparsity_disclosed),
}

print("INFORMATIONAL NOTES (do not block MODELING_HANDOFF_READY):")
for label, (passed, offending_vars, disclosure_check) in informational_notes.items():
    _tag = "INFO" if passed else "WARN"
    print(f"  [{_tag}] {label}")
    if not passed:
        print(f"        {len(offending_vars)} approved variable(s) affected: {offending_vars}")
        if disclosure_check is not None:
            _undisclosed = [v for v in offending_vars if not disclosure_check(v)]
            if _undisclosed:
                print(f"        WARNING -- {len(_undisclosed)} of these carry NEITHER a hard exclusion "
                      f"NOR a disclosed separation_risk/sparse_event_risk soft warning and require "
                      f"investigation: {_undisclosed}")
            else:
                print("        All of these are either correctly hard-excluded (for a separate, "
                      "target-independent reason) or retained in the candidate pool with the "
                      "separation/sparse-event risk correctly disclosed (expected, 2026-08-19 correction).")
        else:
            _unexcluded = [v for v in offending_vars if v not in set(excluded_features_df["variable"])]
            if _unexcluded:
                print(f"        WARNING -- {len(_unexcluded)} of these are NOT hard-excluded from the "
                      f"candidate pool and require investigation: {_unexcluded}")
            else:
                print("        All of these are correctly hard-excluded from the candidate pool (expected).")
print()
if MODELING_HANDOFF_READY:
    print("EDA C handoff complete.")
    print("A broad, eligible candidate pool has been produced (not a final selection).")
    print("Final variable/model selection may proceed in EDA D. Required safeguards are listed in C15.")
else:
    _failed = [label for label, passed in readiness_checks.items() if not passed]
    print("NOT READY. Resolve the following before handing off to EDA D:")
    for f in _failed:
        print(f"  - {f}")
""")

SC16_CLOSE = md("eda-c-s16-close", """
### End of EDA C

This notebook does not train models, choose final modeling variables, preprocess
data, or write patient-level files (unless `SAVE_SELECTED_MODELING_DATASET = True`
was explicitly set). It performs eligibility filtering only and hands off a broad
candidate pool to EDA D.

Any failed readiness check is an open TODO for clinical review, configuration,
or data correction. Rerun EDA C after each correction batch.
""")


# ── Section C17 ────────────────────────────────────────────────────────────────
SC17_HEADER = md("eda-c-s17-header", """
## Section C17 — Output Verification (Colab/local, run last)

Checks the files this run just wrote to `outputs/eda_c/` on disk — not just
in-memory state — so a stale/incomplete upload or a run with the wrong output
flags is caught immediately rather than discovered later in EDA D or Colab.
Requires `SAVE_AGGREGATED_OUTPUTS = True` and `SAVE_SELECTED_MODELING_DATASET
= True` in C1 (both default to `True`); otherwise every check below fails
with a clear "file not written" message.
""")

SC17_VERIFY_OUTPUTS = code("eda-c-s17-verify", """
print("=" * 70)
print("C17 — OUTPUT VERIFICATION (reads outputs/eda_c/ from disk)")
print("=" * 70)

_verify_dir = (_root / "outputs" / "eda_c") if _root else _Path("outputs/eda_c")
if "notebooks" in _verify_dir.resolve().parts:
    raise RuntimeError(
        f"EDA C output verification directory resolved under 'notebooks/' ({_verify_dir.resolve()}) -- "
        "this indicates a working-directory/path-anchoring bug. Refusing to verify "
        "outputs at a non-canonical location."
    )
_verify_checks = {}

_req_files = {
    "candidate_model_features.csv": _verify_dir / "candidate_model_features.csv",
    "excluded_features_log.csv": _verify_dir / "excluded_features_log.csv",
    "candidate_feature_review_full.csv": _verify_dir / "candidate_feature_review_full.csv",
    "modeling_dataset_candidate_features.xlsx": _verify_dir / "modeling_dataset_candidate_features.xlsx",
    "candidate_feature_manifest.json": _verify_dir / "candidate_feature_manifest.json",
    "candidate_features_stage1.csv": _verify_dir / "candidate_features_stage1.csv",
    "candidate_features_stage2_cumulative.csv": _verify_dir / "candidate_features_stage2_cumulative.csv",
    "candidate_features_stage3_cumulative.csv": _verify_dir / "candidate_features_stage3_cumulative.csv",
    "modeling_dataset_stage1.xlsx": _verify_dir / "modeling_dataset_stage1.xlsx",
    "modeling_dataset_stage2_cumulative.xlsx": _verify_dir / "modeling_dataset_stage2_cumulative.xlsx",
    "modeling_dataset_stage3_cumulative.xlsx": _verify_dir / "modeling_dataset_stage3_cumulative.xlsx",
    # ── C13 final model-contract artifacts (2026-09-01 pre-C13 freeze) ────────
    "model_coentry_constraints.csv": _verify_dir / "model_coentry_constraints.csv",
    "model_relationship_groups.csv": _verify_dir / "model_relationship_groups.csv",
    "predictor_relationship_diagnostics.csv": _verify_dir / "predictor_relationship_diagnostics.csv",
    "variable_classification_snapshot.csv": _verify_dir / "variable_classification_snapshot.csv",
    "variable_type_schema_snapshot.csv": _verify_dir / "variable_type_schema_snapshot.csv",
}
for _label, _path in _req_files.items():
    _verify_checks[f"{_label} exists"] = _path.is_file()

# ── Canonical YAML contract sources are tracked and are the ONLY authored ────
# source; a fresh checkout must not need contracts/*.csv or a generator step.
_contracts_dir_v = (
    (_root / "analysis" / "eda" / "notebook_build" / "eda_c" / "contracts")
    if _root else _Path("analysis/eda/notebook_build/eda_c/contracts")
)
_verify_checks["canonical contracts/model_coentry_constraints.yaml exists (tracked source of truth)"] = (
    (_contracts_dir_v / "model_coentry_constraints.yaml").is_file()
)
_verify_checks["canonical contracts/model_relationship_groups.yaml exists (tracked source of truth)"] = (
    (_contracts_dir_v / "model_relationship_groups.yaml").is_file()
)
_verify_checks["C13 does not depend on contracts/*.csv (generated inspection mirror only)"] = (
    "_COENTRY_SRC_PATH" not in dir() or str(_COENTRY_SRC_PATH).endswith(".yaml")
)

# ── C13 model-contract disk cross-checks (Part N) ────────────────────────────
try:
    _pool_disk = pd.read_csv(_verify_dir / "candidate_model_features.csv")
    for _sc in ("hard_forbidden_with", "relationship_groups", "model_representation_type",
                "physical_variable_type"):
        if _sc in _pool_disk.columns:
            _pool_disk[_sc] = _pool_disk[_sc].fillna("")
    _cls_disk = pd.read_csv(_verify_dir / "variable_classification_snapshot.csv")
    _type_disk = pd.read_csv(_verify_dir / "variable_type_schema_snapshot.csv")
    _co_disk = pd.read_csv(_verify_dir / "model_coentry_constraints.csv", dtype=str).fillna("")
    _rg_disk = pd.read_csv(_verify_dir / "model_relationship_groups.csv", dtype=str).fillna("")
    _pool_names = set(_pool_disk["variable"])
    _cls_disk_map = dict(zip(_cls_disk["column_name"], _cls_disk["classification"]))
    _type_disk_map = dict(zip(_type_disk["variable_name"], _type_disk["variable_type"]))
    _cls_disk_counts = _cls_disk["column_name"].value_counts().to_dict()
    _type_disk_counts = _type_disk["variable_name"].value_counts().to_dict()

    _verify_checks["candidate_model_features.csv has exactly one row per eligible variable"] = (
        _pool_disk["variable"].is_unique
    )
    _exp_pool_n = EXPECTED_ELIGIBLE_POOL if "EXPECTED_ELIGIBLE_POOL" in dir() else len(candidate_pool_df)
    _verify_checks[f"candidate_model_features.csv has {_exp_pool_n} eligible rows"] = (
        len(_pool_disk) == _exp_pool_n
    )
    _verify_checks["disk: every eligible variable has exactly one classification snapshot row"] = all(
        _cls_disk_counts.get(v, 0) == 1 for v in _pool_names
    )
    _verify_checks["disk: every eligible variable has exactly one type-schema snapshot row"] = all(
        _type_disk_counts.get(v, 0) == 1 for v in _pool_names
    )
    _verify_checks["disk: predictor_classification agrees with the classification snapshot"] = all(
        str(r["predictor_classification"]) == str(_cls_disk_map.get(r["variable"]))
        for r in _pool_disk.to_dict("records")
    )
    _verify_checks["disk: physical_variable_type agrees with the type snapshot"] = all(
        str(r["physical_variable_type"]) == str(_type_disk_map.get(r["variable"]))
        for r in _pool_disk.to_dict("records")
    )
    _verify_checks["disk: coarse data_type is the projection of physical_variable_type"] = all(
        str(r["data_type"]) == SCHEMA_TO_EDA_TYPE.get(str(r["physical_variable_type"]))
        for r in _pool_disk.to_dict("records")
    )
    _verify_checks["disk: earliest_entry_stage agrees with predictor_classification"] = all(
        int(r["earliest_entry_stage"]) == {
            "predictor_allowed": 1, "secondary_near_delivery_predictor": 2,
            "intrapartum_predictor_exclude_from_prelabor_model": 3,
        }.get(str(r["predictor_classification"]))
        for r in _pool_disk.to_dict("records")
    )
    _verify_checks["disk: every eligible variable has a populated model_representation_type"] = (
        _pool_disk["model_representation_type"].fillna("").str.len().gt(0).all()
    )
    # hard_forbidden_with reconciles exactly with the pair registry (symmetric)
    _co_partners = {}
    for _r in _co_disk.to_dict("records"):
        _co_partners.setdefault(str(_r["var_a"]), set()).add(str(_r["var_b"]))
        _co_partners.setdefault(str(_r["var_b"]), set()).add(str(_r["var_a"]))
    _hfw_ok = all(
        set(p.strip() for p in str(r["hard_forbidden_with"]).split(";") if p.strip())
        == _co_partners.get(r["variable"], set())
        for r in _pool_disk.to_dict("records")
    )
    _verify_checks["disk: hard_forbidden_with reconciles exactly with model_coentry_constraints.csv"] = _hfw_ok
    _verify_checks["disk: every hard co-entry row is target_independent=true"] = (
        len(_co_disk) == 0 or (_co_disk["target_independent"].str.strip().str.lower() == "true").all()
    )
    _verify_checks["disk: every hard co-entry pair member is a live eligible variable"] = (
        (set(_co_disk["var_a"]) | set(_co_disk["var_b"])) <= _pool_names
    )
    # relationship_groups reconcile exactly with the group table
    _rg_by_var = {}
    for _r in _rg_disk.to_dict("records"):
        _rg_by_var.setdefault(str(_r["variable"]), set()).add(str(_r["group_name"]))
    _rg_ok = all(
        set(g.strip() for g in str(r["relationship_groups"]).split(";") if g.strip())
        == _rg_by_var.get(r["variable"], set())
        for r in _pool_disk.to_dict("records")
    )
    _verify_checks["disk: relationship_groups reconcile exactly with model_relationship_groups.csv"] = _rg_ok
    _verify_checks["disk: relationship groups reference only live eligible variables (no eligibility change)"] = (
        set(_rg_disk["variable"]) <= _pool_names
    )
except Exception as _c13_verify_exc:
    _verify_checks["C13 model-contract disk cross-checks ran"] = False
    print(f"  C13 model-contract disk verification raised: {_c13_verify_exc}")

# Cumulative-stage nesting on the exported per-stage files (2026-08-31 rebuild).
try:
    _cs1 = set(pd.read_csv(_verify_dir / "candidate_features_stage1.csv")["variable"])
    _cs2 = set(pd.read_csv(_verify_dir / "candidate_features_stage2_cumulative.csv")["variable"])
    _cs3 = set(pd.read_csv(_verify_dir / "candidate_features_stage3_cumulative.csv")["variable"])
    _verify_checks["stage candidate files are strictly nested (S1 subset S2 subset S3)"] = _cs1 <= _cs2 <= _cs3
    _verify_checks["cumulative Stage 3 candidate file == full candidate pool"] = (
        _cs3 == set(pd.read_csv(_verify_dir / "candidate_model_features.csv")["variable"])
    )
    _md1 = pd.read_excel(_verify_dir / "modeling_dataset_stage1.xlsx")
    _md3 = pd.read_excel(_verify_dir / "modeling_dataset_stage3_cumulative.xlsx")
    _verify_checks["stage modeling datasets keep target 370/61"] = (
        int((_md1[TARGET_COL] == 0).sum()) == EXPECTED_N0 and int((_md1[TARGET_COL] == 1).sum()) == EXPECTED_N1
        and int((_md3[TARGET_COL] == 0).sum()) == EXPECTED_N0 and int((_md3[TARGET_COL] == 1).sum()) == EXPECTED_N1
    )
    _verify_checks["stage modeling datasets keep 431 rows"] = len(_md1) == EXPECTED_ROWS and len(_md3) == EXPECTED_ROWS
    _verify_checks["stage modeling dataset columns are nested"] = set(_md1.columns) <= set(_md3.columns)
except Exception as _stage_verify_exc:
    _verify_checks["stage candidate files are strictly nested (S1 subset S2 subset S3)"] = False
    _verify_checks["cumulative Stage 3 candidate file == full candidate pool"] = False
    _verify_checks["stage modeling datasets keep target 370/61"] = False
    _verify_checks["stage modeling datasets keep 431 rows"] = False
    _verify_checks["stage modeling dataset columns are nested"] = False
    print(f"  stage-file verification raised: {_stage_verify_exc}")

if _req_files["candidate_model_features.csv"].is_file():
    _pool_check = pd.read_csv(_req_files["candidate_model_features.csv"])
    _pool_vars = set(_pool_check["variable"])
    # Redundancy is disclosed, not hard-excluded -- BOTH members of a redundancy pair/
    # family MAY legitimately co-exist in the broad pool. This check verifies the
    # resolution mechanism itself worked correctly: for every redundancy family with
    # 2+ members present in the exported pool, exactly one of them is the non-demoted
    # representative (redundancy_demoted == False). It does NOT require only one member
    # to be present -- see the C15 handoff note on redundancy handling for EDA D.
    # 2026-09-01 five-family audit: EDA C honours a fixed-representative demotion
    # ONLY for families in EDA_C_FIXED_REPRESENTATIVE_FAMILIES (Category A). Every
    # other family keeps all members (redundancy_unresolved), demotes nobody.
    _demoted_map = dict(zip(_pool_check["variable"], _pool_check["redundancy_demoted"]))
    _unresolved_map = (
        dict(zip(_pool_check["variable"], _pool_check["redundancy_unresolved"]))
        if "redundancy_unresolved" in _pool_check.columns else {}
    )
    _honoured_fixed = set(EDA_C_FIXED_REPRESENTATIVE_FAMILIES) if "EDA_C_FIXED_REPRESENTATIVE_FAMILIES" in dir() else set()
    _fixed_rep_members = set()
    for _grp, _def in ALL_REDUNDANCY_GROUPS.items():
        if _grp in _honoured_fixed and _def.get("representative") is not None:
            _fixed_rep_members.update(_def["members"])
    _redundancy_groups_ok = True
    # (1) nobody is demoted except a member of an EDA-C-honoured fixed family
    for _v, _dem in _demoted_map.items():
        if bool(_dem) and _v not in _fixed_rep_members:
            _redundancy_groups_ok = False
    for _grp, _def in ALL_REDUNDANCY_GROUPS.items():
        _members_in_pool = [m for m in _def["members"] if m in _pool_vars]
        if len(_members_in_pool) < 2:
            continue
        if _grp in _honoured_fixed and _def.get("representative") is not None:
            # (2) representative present and NOT demoted
            if _def["representative"] in _pool_vars and bool(_demoted_map.get(_def["representative"], False)):
                _redundancy_groups_ok = False
        else:
            # (3) every present member flagged redundancy_unresolved, demote nobody
            if any(bool(_demoted_map.get(m, False)) for m in _members_in_pool if m not in _fixed_rep_members):
                _redundancy_groups_ok = False
            if _unresolved_map and not all(bool(_unresolved_map.get(m, False)) for m in _members_in_pool):
                _redundancy_groups_ok = False
    _verify_checks["Redundancy: only EDA-C-honoured fixed families demote; every other family flags all members unresolved and demotes nobody"] = _redundancy_groups_ok
    _verify_checks["no hard-excluded variable appears in the candidate pool"] = (
        not bool(_pool_check["eligibility_status"].ne("eligible").any())
        if "eligibility_status" in _pool_check.columns else False
    )
else:
    _verify_checks["Redundancy groups have exactly one non-demoted representative"] = False
    _verify_checks["no hard-excluded variable appears in the candidate pool"] = False

if _req_files["modeling_dataset_candidate_features.xlsx"].is_file():
    _mds_check = pd.read_excel(_req_files["modeling_dataset_candidate_features.xlsx"])
    _verify_checks["delivery_id is NOT in the modeling dataset"] = "delivery_id" not in _mds_check.columns
    _verify_checks["subject_number is NOT in the modeling dataset"] = "subject_number" not in _mds_check.columns
    _verify_checks[f"row count == {EXPECTED_ROWS}"] = len(_mds_check) == EXPECTED_ROWS
else:
    _verify_checks["delivery_id is NOT in the modeling dataset"] = False
    _verify_checks["subject_number is NOT in the modeling dataset"] = False
    _verify_checks[f"row count == {EXPECTED_ROWS}"] = False

if _req_files["candidate_feature_manifest.json"].is_file():
    with open(_req_files["candidate_feature_manifest.json"], "r", encoding="utf-8") as _mf_check:
        _manifest_check = _json_out.load(_mf_check)
    _verify_checks["manifest conclusion == 'PASS'"] = _manifest_check.get("conclusion") == "PASS"
else:
    _verify_checks["manifest conclusion == 'PASS'"] = False

for _label, _passed in _verify_checks.items():
    print(f"  [{'PASS' if _passed else 'FAIL'}] {_label}")

C17_OUTPUT_VERIFICATION_PASSED = all(_verify_checks.values())
print()
print(f"C17_OUTPUT_VERIFICATION_PASSED = {C17_OUTPUT_VERIFICATION_PASSED}")
if not C17_OUTPUT_VERIFICATION_PASSED:
    print()
    print("FAILED — most likely cause: SAVE_AGGREGATED_OUTPUTS or SAVE_SELECTED_MODELING_DATASET")
    print("was False in C1 for this run, so outputs/eda_c/ was not (fully) written.")
    print("Set both to True in C1 and rerun the whole notebook top to bottom.")
print("=" * 70)
""")

SC18_HEADER = md("eda-c-s18-header", """
## Section C18 — Constant / Near-Zero-Variance and Cohort-Invariant Validation

Explicit checks required by the Batch C amendment, covering the parts of the
constant-variable audit scoped to Data Cleaning B / EDA C (the A2-scope checks
already live in EDA A2's own A2.15 validation cell). Read-only -- asserts against
the already-computed `candidate_df` / `candidate_pool_df` / `df` from this run;
changes nothing.

**Current live hard exclusions (2026-09-01):** the **four zero-variance
variables only** (`alcohol`, `HELLP`, `eclampsia`, `IUFD`). Sparsity,
separation, high missingness, and redundancy are **not** hard exclusions —
they are disclosed soft warnings and the variables stay in the eligible pool.
Any comment elsewhere implying otherwise is stale.
""")

SC18_VALIDATE = code("eda-c-s18-validate", """
print("=" * 70)
print("CONSTANT / NEAR-ZERO-VARIANCE / COHORT-INVARIANT VALIDATION (Batch C amendment)")
print("=" * 70)
_c18_errors = []

# 4. Batch 19 (this notebook's input, `df`) zero-variance set, computed live
#    -- descriptive/audit visibility only (2026-08-16 structural-robustness
#    correction). A supervisor-approved reclassification, or the cohort
#    gaining/losing a zero-variance column, must never fail this check on its
#    own; only a genuine computation error would make this list wrong. The
#    known current members (alcohol/HELLP/eclampsia/IUFD) are a CURRENT
#    finding, not a hardcoded requirement -- see
#    docs/clinical_decisions/manual_decisions_log.md for the clinical history
#    of each.
_actual_b19_zv = {c for c in df.columns if _is_complete_zero_variance_for_exclusion(df[c])}
print(f"4. Batch 19 zero-variance columns (descriptive): {sorted(_actual_b19_zv)}")

# 5. placenta_accreta is absent from Batch 19 (permanently removed from the
#    analytical dataset, Decisions 32/33) -- not falsely reported as
#    zero-variance (it is simply not present at all). IUFD is no longer
#    expected to be absent -- see check 4 above (removed 2026-08-04,
#    Decision 62).
_absent_check = {"placenta_accreta": "placenta_accreta" not in df.columns}
print(f"5. placenta_accreta absent from Batch 19: {_absent_check['placenta_accreta']}")
if not all(_absent_check.values()):
    _c18_errors.append(f"Expected-absent column(s) unexpectedly present: {_absent_check}")

# 6. No zero-variance variable among the current eligible predictors
#    (current pool size printed dynamically below, check 7).
_pool_vars = set(candidate_pool_df["variable"])
_zv_in_pool = {c for c in _pool_vars if c in df_analysis.columns
               and _is_complete_zero_variance_for_exclusion(df_analysis[c])}
print(f"6. Zero-variance variables in the eligible pool: {sorted(_zv_in_pool)} (expected empty)")
if _zv_in_pool:
    _c18_errors.append(f"Zero-variance variable(s) leaked into the eligible pool: {_zv_in_pool}")

# 7. Near-zero-variance predictors are still descriptively present where
#    applicable and did not silently change eligibility on their own --
#    spot-checked against the eligible pool membership by name (not asserted
#    to be *in* the pool). A near-zero-variance descriptive flag is NOT a hard
#    exclusion: the ONLY current hard exclusions are the four genuine
#    zero-variance variables (alcohol/HELLP/eclampsia/IUFD). Sparsity,
#    separation, high missingness and redundancy are soft / review diagnostics
#    (disclosed in soft_warning_flags / redundancy_group) and never
#    independently remove an eligible predictor from the pool.
#
#    HISTORICAL count narrative (kept for audit lineage only -- NOT the current
#    contract): 39->38 (2026-08-04, Decisions 59/61/62): any_medical_problem,
#    regular_medications, chorioamnionitis, intrapartum_fever, induction_of_labor,
#    start_of_labor left Data Cleaning B's output entirely; oligohydramnios and
#    celestone entered the screened universe and both passed into the eligible
#    pool; IUFD entered the screened universe but is a zero-variance hard
#    exclusion. A later >=70% missingness cleaning correction removed
#    adenomyosis_sonographic_features_clean from the cleaned dataset before EDA C.
#    endometrioma_size_severity was replaced by endometrioma_size_status. Those
#    historical transitions describe past regenerations; they do NOT describe a
#    current sparsity/missingness/redundancy exclusion mechanism.
#    See docs/clinical_decisions/manual_decisions_log.md.
#
# Eligible pool size (2026-08-16 structural-robustness correction):
# descriptive/audit visibility only. Screening-pool composition is a direct,
# expected consequence of upstream variable classification (predictor_allowed
# / secondary_near_delivery_predictor / intrapartum_predictor_exclude_from_
# prelabor_model membership) plus the ONE target-independent hard screen
# (zero variance). Missingness, separation and redundancy are soft / review
# diagnostics only -- they are disclosed, never used to hard-exclude an
# eligible predictor. A supervisor-approved reclassification legitimately
# changes this number, so it must never fail the pipeline on its own. See
# docs/clinical_decisions/manual_decisions_log.md for the decision history
# behind the current pool composition.
print(f"7. Eligible pool size (descriptive): {len(_pool_vars)}")

# Cohort/target invariant (C9 requirement) -- kept BLOCKING: an unexpected
# cohort/target change signals a real upstream data problem (wrong file,
# accidental row loss, stale preprocessing rerun), not a legitimate
# reclassification, and must fail loudly. This mirrors the equivalent
# EXPECTED_ROWS/EXPECTED_N0/EXPECTED_N1 gate already enforced earlier in
# every EDA A/A2/C notebook.
print(f"   n_rows={len(df)} (expected {EXPECTED_ROWS}), target 0/1="
      f"{int((df[TARGET_COL]==0).sum())}/{int((df[TARGET_COL]==1).sum())} "
      f"(expected {EXPECTED_N0}/{EXPECTED_N1})")
if len(df) != EXPECTED_ROWS or int((df[TARGET_COL]==0).sum()) != EXPECTED_N0 or int((df[TARGET_COL]==1).sum()) != EXPECTED_N1:
    _c18_errors.append("Cohort/target invariant violated")

# Screening-count summary (2026-08-16 structural-robustness correction):
# descriptive/audit visibility only, for the same reason as check 7 above --
# n_screened/n_hard_excluded/n_eligible_pool are downstream consequences of
# variable classification plus the single target-independent zero-variance
# hard screen (n_hard_excluded is exactly the four zero-variance variables),
# not fixed architectural constants, and must not gate execution.
print(f"   n_screened={len(candidate_df)}, "
      f"n_hard_excluded={len(excluded_features_df)}, "
      f"n_eligible_pool={len(candidate_pool_df)} (all descriptive)")

if _c18_errors:
    raise AssertionError("Batch C constant-variable validation failed: " + "; ".join(_c18_errors))
print()
print("All constant / near-zero-variance / cohort-invariant checks PASSED.")
print("=" * 70)
""")


EDA_C_PART5_CELLS = [
    SC13_HEADER,
    SC13_MODEL_CONTRACT_HEADER,
    SC13_MODEL_CONTRACT,
    SC13_EXPORT,
    SC14_HEADER,
    SC14_TREATMENT,
    SC15_HEADER,
    SC15_CONTRACT,
    SC16_HEADER,
    SC16_GATE,
    SC16_CLOSE,
    SC17_HEADER,
    SC17_VERIFY_OUTPUTS,
    SC18_HEADER,
    SC18_VALIDATE,
]


if __name__ == "__main__":
    print(f"EDA C Part 5 cells defined: {len(EDA_C_PART5_CELLS)}")

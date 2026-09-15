#!/usr/bin/env python3
"""EDA C — Part 4 cell definitions (sections C10–C12c).

C10 — Derived feature validation (missingness, distributions, leakage, redundancy).
C11 — Exploratory statistical screening (association tests + BH-FDR).
C12 — Candidate feature review table (candidate_role_for_modeling_review).
C12b — Eligibility filtering and candidate pool construction (hard exclusions +
       soft warnings; no cap, no greedy pick).
C12c — Candidate pool validation checks.

IMPORTANT: All statistical results in C11 and C12 are EXPLORATORY SCREENING ONLY.
EDA C performs eligibility filtering only -- it does not choose the final modeling
variables. Final feature/model selection must occur in EDA D, inside cross-validation.
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


# ── Section C10 ────────────────────────────────────────────────────────────────
SC10_HEADER = md("eda-c-s10-header", """
## Section C10 — Derived Feature Validation

Validates each **materialized** derived feature against five criteria. None of
these change eligibility — EDA C performs eligibility filtering only, and no
C10/C10c association metric selects or excludes a predictor.

1. **`derived_missingness_review`** (renamed from a bare `miss_flag`): a
   *descriptive* warning when the derived feature's missing rate exceeds the
   max source missing rate + 5 pp. This is a heuristic only — a valid formula
   that needs several observed source fields legitimately produces more
   missingness than any one source. Never an eligibility decision.
2. **Distribution**: histogram/bar chart to detect unexpected values or
   near-constants. For a categorical derived feature the target panel plots an
   explicitly-denominated `P(target=1 | derived level)` (the corrected-C4b
   target-stratified convention), not an ambiguous "proportion".
3. **`high_target_association_review`** (formerly the legacy `leakage_flag`
   column, fully retired 2026-09-01): a *type-correct* descriptive association
   with the target — numeric → `|Spearman ρ|`; binary → point-biserial `|r|`
   (≡ Pearson φ); multi-level categorical → Cramér's V. Flagged at a
   documented descriptive threshold of `DERIVED_TARGET_ASSOC_REVIEW_THRESHOLD
   = 0.7`. **This is NOT proof of leakage** and has **no eligibility effect**
   — it only marks a feature for lineage/semantic review. `high_target_
   association_review` is the sole stored column; no `leakage_flag` alias
   remains anywhere in the active C contract.
4. **Redundancy with source variables**: Spearman ρ (numeric) or Cramér's V
   (binary/categorical). Disclosure for EDA D, not a drop.
5. **Deterministic valid-value contract**: every non-missing observed derived
   value must be inside the allowed output set declared in the shared
   `DERIVED_FEATURE_CONTRACTS` (C9). An unexpected value is a deterministic
   derivation-integrity failure and **fails loud** — this validates only the
   formula's own output domain, not any invented clinical plausibility range.

Also includes the original-predictor redundancy matrix (recheck since A2 was run
on a previous dataset version).

**Presentation vs. analysis.** `derived_validation_df` keeps exact analytical
counts. Any printed/rendered small derived-feature cell is suppressed with the
project `share_safe` helper under `SHARE_SAFE_MODE` — presentation only, no
analytical value changes.
""")

SC10_VALIDATE = code("eda-c-s10-validate", """
def cramers_v(table):
    chi2 = stats.chi2_contingency(table, correction=False)[0]
    n = table.to_numpy().sum()
    denom = min(table.shape) - 1
    return float(np.sqrt(chi2 / (n * denom))) if n > 0 and denom > 0 else float("nan")


def _target_association(series, target, vtype, min_n=10):
    # Type-correct, UNSIGNED descriptive association between a (derived) feature
    # and the binary target. Returns (measure_name, strength_0_to_1):
    #   numeric                 -> |Spearman rho|
    #   binary                  -> |point-biserial r| (== |Pearson phi| for 0/1 x 0/1)
    #   multi-level categorical -> Cramer's V
    # Three DIFFERENT strength measures, NOT interchangeable as a signed effect --
    # the measure name is always carried alongside the number. No eligibility
    # decision depends on this.
    _p = pd.concat([series.rename("_f"), target.rename("_t")], axis=1).dropna()
    if len(_p) < min_n:
        return "insufficient_n", float("nan")
    if vtype == "numeric":
        _rho = stats.spearmanr(_p["_f"], _p["_t"]).statistic
        return "abs_spearman", (float(abs(_rho)) if pd.notna(_rho) else float("nan"))
    if vtype == "binary":
        _fn = pd.to_numeric(_p["_f"], errors="coerce")
        if _fn.notna().all() and set(_fn.unique()) <= {0.0, 1.0}:
            if _fn.nunique() < 2:
                return "abs_point_biserial", float("nan")  # constant -> undefined
            _r = np.corrcoef(_fn.to_numpy(float), _p["_t"].to_numpy(float))[0, 1]
            return "abs_point_biserial", (float(abs(_r)) if pd.notna(_r) else float("nan"))
        # non-clean binary coding -> fall back to Cramer's V, do NOT silently
        # return NaN from a failed .corr()
        _tab = pd.crosstab(_p["_f"], _p["_t"])
        return "cramers_v", (cramers_v(_tab) if min(_tab.shape) >= 2 else float("nan"))
    # multi-level categorical
    _tab = pd.crosstab(_p["_f"], _p["_t"])
    return "cramers_v", (cramers_v(_tab) if min(_tab.shape) >= 2 else float("nan"))


# ── Derived feature validation ─────────────────────────────────────────────────
print("=" * 70)
print("DERIVED FEATURE VALIDATION")
print("=" * 70)

_SS_C10 = bool(SHARE_SAFE_MODE) if "SHARE_SAFE_MODE" in dir() else True
_SS_C10_THR = share_safe.DEFAULT_DISCLOSURE_THRESHOLD

validation_rows = []
# Descriptive review threshold ONLY. NOT an eligibility threshold. A derived
# feature above it is flagged high_target_association_review for lineage/semantic
# review -- it is never hard-excluded, reclassified, or dropped for it.
# The legacy threshold constant name and the legacy leakage_flag column it
# backed are fully retired (2026-09-01) -- high_target_association_review is
# the sole canonical name for both the threshold and the flag.
DERIVED_TARGET_ASSOC_REVIEW_THRESHOLD = 0.7

_VALIDATION_COLS = [
    "derived_feature", "type", "N_valid", "missing_%", "max_src_missing_%",
    "derived_missingness_review", "miss_flag",
    "association_measure", "association_strength", "|r|_vs_target",
    "high_target_association_review",
    "max_redundancy", "redundancy_detail",
    "impossible_flag", "impossible_note",
    "separation_flag", "too_sparse_flag", "min_cell_count", "min_cell_count_display",
]
_contract_violations = []
_missing_contracts = []

for dv in DERIVED_VARS:
    src_str = derived_meta[dv]["source_columns"]
    src_cols = [c.strip() for c in src_str.split(",") if c.strip()]
    vtype = infer_var_type(df_analysis[dv])
    n_valid = int(df_analysis[dv].notna().sum())
    n_miss = int(df_analysis[dv].isna().sum())
    miss_pct = round(n_miss / len(df_analysis) * 100, 1)

    # (C4) derived_missingness_review -- DESCRIPTIVE heuristic only, no eligibility
    src_miss_pcts = [round(df_analysis[c].isna().mean() * 100, 1)
                     for c in src_cols if c in df_analysis.columns]
    max_src_miss = max(src_miss_pcts) if src_miss_pcts else float("nan")
    derived_missingness_review = bool(pd.notna(max_src_miss) and miss_pct > max_src_miss + 5)
    _miss_context = ""
    if derived_missingness_review:
        _miss_context = (
            f"formula needs {len(src_cols)} source field(s) jointly; combined "
            "missingness legitimately exceeds any single source -- descriptive only"
        )

    # (C2) type-correct target association (renamed concept: high_target_association_review)
    association_measure, association_strength = _target_association(
        df_analysis[dv], df_analysis[TARGET_COL], vtype
    )
    high_target_association_review = bool(
        pd.notna(association_strength)
        and association_strength > DERIVED_TARGET_ASSOC_REVIEW_THRESHOLD
    )

    # Redundancy with source columns (disclosure for EDA D, not a drop)
    redundancy_max = float("nan")
    redundancy_detail = ""
    for sc in src_cols:
        if sc not in df_analysis.columns:
            continue
        _pr = df_analysis[[dv, sc]].dropna()
        if len(_pr) < 10:
            continue
        sv = infer_var_type(df_analysis[sc])
        try:
            if vtype == "numeric" and sv == "numeric":
                r = abs(float(stats.spearmanr(_pr[dv], _pr[sc]).statistic))
            else:
                _tab = pd.crosstab(_pr[dv], _pr[sc])
                if _tab.shape[0] >= 2 and _tab.shape[1] >= 2:
                    r = cramers_v(_tab)
                else:
                    r = float("nan")
            if pd.notna(r) and (pd.isna(redundancy_max) or r > redundancy_max):
                redundancy_max = r
                redundancy_detail = f"{sc}:{r:.2f}"
        except Exception:
            pass

    # (C3) deterministic valid-value contract -- ALL materialized derived features.
    # Validates ONLY the formula's own declared output domain (DERIVED_FEATURE_CONTRACTS,
    # from C9) -- not an invented clinical plausibility range.
    _contract = DERIVED_FEATURE_CONTRACTS.get(dv)
    impossible_flag = False
    impossible_note = ""
    if _contract is None:
        _missing_contracts.append(dv)
        impossible_flag = True
        impossible_note = "NO DERIVED_FEATURE_CONTRACTS entry"
    else:
        _allowed = _contract["allowed_values"]
        _obs = df_analysis[dv].dropna()
        if vtype in ("binary", "numeric"):
            _obs_norm = set(
                float(v) for v in pd.to_numeric(_obs, errors="coerce").dropna().unique()
            )
            _allowed_norm = set(float(v) for v in _allowed)
        else:
            _obs_norm = set(_obs.astype(str).unique())
            _allowed_norm = set(str(v) for v in _allowed)
        _bad_vals = sorted(_obs_norm - _allowed_norm, key=str)
        if _bad_vals:
            impossible_flag = True
            impossible_note = f"values outside declared output domain: {_bad_vals}"
            _contract_violations.append(f"{dv}: {_bad_vals} not in {sorted(_allowed_norm, key=str)}")

    # Sparsity / separation gate -- C6 (sparsity_df) only covers ANALYSIS_VARS, not
    # DERIVED_VARS, so binary/categorical derived features must be checked here too.
    # Exact values kept in derived_validation_df; a share-safe display copy is made.
    separation_flag = False
    too_sparse_flag = False
    min_cell_count = -1
    if vtype in ("binary", "categorical"):
        _obs2 = df_analysis[[dv, TARGET_COL]].dropna(subset=[dv])
        _g0 = _obs2[_obs2[TARGET_COL] == 0]
        _g1 = _obs2[_obs2[TARGET_COL] == 1]
        _cells = []
        for _lvl in sorted(_obs2[dv].unique(), key=str):
            _cells.append(int((_g0[dv] == _lvl).sum()))
            _cells.append(int((_g1[dv] == _lvl).sum()))
        min_cell_count = min(_cells) if _cells else 0
        separation_flag = any(c == 0 for c in _cells)
        too_sparse_flag = (not separation_flag) and (min_cell_count < 5)
    _min_cell_display = share_safe.safe_count(
        min_cell_count if min_cell_count >= 0 else None,
        threshold=_SS_C10_THR, enabled=_SS_C10,
    )

    row = {
        "derived_feature": dv,
        "type": vtype,
        "N_valid": n_valid,
        "missing_%": miss_pct,
        "max_src_missing_%": max_src_miss,
        "derived_missingness_review": derived_missingness_review,
        "miss_flag": derived_missingness_review,   # legacy alias, same value
        "association_measure": association_measure,
        "association_strength": round(association_strength, 3) if pd.notna(association_strength) else float("nan"),
        "|r|_vs_target": round(association_strength, 3) if pd.notna(association_strength) else float("nan"),
        "high_target_association_review": high_target_association_review,
        "max_redundancy": round(redundancy_max, 3) if pd.notna(redundancy_max) else float("nan"),
        "redundancy_detail": redundancy_detail,
        "impossible_flag": impossible_flag,
        "impossible_note": impossible_note,
        "separation_flag": separation_flag,
        "too_sparse_flag": too_sparse_flag,
        "min_cell_count": min_cell_count,
        "min_cell_count_display": _min_cell_display,
        "derived_missingness_context": _miss_context,
    }
    validation_rows.append(row)

    flags = []
    if derived_missingness_review:
        flags.append("MISSINGNESS_REVIEW")
    if high_target_association_review:
        flags.append("HIGH_TARGET_ASSOC_REVIEW")
    if impossible_flag:
        flags.append("CONTRACT_VIOLATION")
    if separation_flag:
        flags.append("SEPARATION")
    elif too_sparse_flag:
        flags.append("SPARSE")
    flag_str = " | ".join(flags) if flags else "ok"
    print(f"  {dv:<40} {flag_str}  [{association_measure}={row['association_strength']}]")

# (C3 / PART H) fail loud on any contract gap or violation -- deterministic
# derivation-integrity failures, not tolerated.
if _missing_contracts:
    raise RuntimeError(
        "C10: materialized derived feature(s) have NO DERIVED_FEATURE_CONTRACTS "
        f"entry: {_missing_contracts}. Every materialized derived feature must "
        "have a shared formula/valid-value contract (defined in C9)."
    )
if _contract_violations:
    raise RuntimeError(
        "C10: derived-feature deterministic valid-value contract VIOLATED -- an "
        "observed derived value is outside the formula's own declared output "
        "domain: " + "; ".join(_contract_violations)
    )

derived_validation_df = pd.DataFrame(validation_rows, columns=_VALIDATION_COLS + ["derived_missingness_context"])
# share-safe display copy: exact analytical frame keeps every value; the printed
# copy hides protected small min-cell counts only (presentation layer).
derived_validation_display_df = derived_validation_df.drop(columns=["min_cell_count", "derived_missingness_context"])
print()
print(derived_validation_display_df.to_string(index=False))
print()
print("NOTE: association_strength is a TYPE-CORRECT descriptive measure "
      "(abs_spearman / abs_point_biserial / cramers_v -- named per row, NOT a "
      "signed cross-comparable effect). high_target_association_review "
      "is a lineage-review flag ONLY -- no eligibility effect. "
      "min_cell_count shown share-safe; exact value retained in derived_validation_df.")

# ── PART H reconciliation: every materialized DERIVED_VARS member is covered ──
_recon_c10 = []
for _dv in DERIVED_VARS:
    _has_meta = _dv in derived_meta
    _has_contract = _dv in DERIVED_FEATURE_CONTRACTS
    _n_rows = int((derived_validation_df["derived_feature"] == _dv).sum())
    _recon_c10.append({"derived_feature": _dv, "has_derived_meta": _has_meta,
                       "has_contract": _has_contract, "validation_rows": _n_rows})
derived_coverage_df = pd.DataFrame(
    _recon_c10, columns=["derived_feature", "has_derived_meta", "has_contract", "validation_rows"]
)
print()
print("C10 derived-feature coverage reconciliation:")
print(derived_coverage_df.to_string(index=False) if len(derived_coverage_df) else "  (no materialized derived features)")
_cov_bad = derived_coverage_df[
    (~derived_coverage_df["has_derived_meta"]) | (~derived_coverage_df["has_contract"])
    | (derived_coverage_df["validation_rows"] != 1)
] if len(derived_coverage_df) else derived_coverage_df
if len(_cov_bad):
    raise RuntimeError(
        "C10 coverage reconciliation FAILED -- each materialized DERIVED_VARS member "
        "must have derived_meta, a DERIVED_FEATURE_CONTRACTS entry, and exactly one "
        f"derived_validation_df row:\\n{_cov_bad.to_string(index=False)}"
    )

# ── Distribution plots for derived features ────────────────────────────────────
print()
print("Derived feature distributions:")
for dv in DERIVED_VARS:
    vtype = infer_var_type(df_analysis[dv])
    _data = df_analysis[dv].dropna()
    if _data.empty:
        print(f"  {dv}: all missing — skipping plot")
        continue
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    if vtype == "numeric":
        sns.histplot(
            data=df_analysis[[dv, TARGET_COL]].dropna(),
            x=dv, hue=TARGET_COL, stat="density", common_norm=False,
            kde=True, element="step", ax=axes[0], palette={0: _C0, 1: _C1},
        )
        sns.boxplot(
            data=df_analysis[[dv, TARGET_COL]].dropna(),
            x=TARGET_COL, y=dv, hue=TARGET_COL, ax=axes[1],
            palette={0: _C0, 1: _C1}, legend=False,
        )
        axes[1].set_xlabel("0=Vaginal  1=Intrapartum CS")
    else:
        # LEFT: aggregate level-count bar (share-safe: small bars masked)
        _vc = df_analysis[dv].value_counts().sort_index()
        _cohort_n = int(df_analysis[dv].notna().sum())
        _bar_x, _bar_h = [], []
        for _lev, _cnt in _vc.items():
            _disp = share_safe.safe_count_with_complement(
                int(_cnt), _cohort_n, threshold=_SS_C10_THR, enabled=_SS_C10)
            _bar_x.append(str(_lev))
            _bar_h.append(np.nan if isinstance(_disp, str) else int(_cnt))
        axes[0].bar([x for x, h in zip(_bar_x, _bar_h) if not (isinstance(h, float) and np.isnan(h))],
                    [h for h in _bar_h if not (isinstance(h, float) and np.isnan(h))], color=_C0)
        axes[0].set_xlabel(dv)
        axes[0].set_ylabel("count (small cells suppressed)")
        axes[0].tick_params(axis="x", rotation=45)
        # RIGHT: explicitly-denominated target-stratified rate -- P(target=1 | level).
        # Row-normalised crosstab (denominator = N within that derived level),
        # matching the corrected-C4b "within-level %" convention. This is
        # P(target | category), NOT P(category | target).
        _ct = pd.crosstab(df_analysis[dv], df_analysis[TARGET_COL])
        _within_level_n = _ct.sum(axis=1)
        _p_t1_given_level = (_ct.get(1, pd.Series(0, index=_ct.index)) / _within_level_n)
        _rate_x, _rate_h = [], []
        for _lev in _ct.index:
            _c1 = int(_ct.get(1, pd.Series(0, index=_ct.index)).get(_lev, 0))
            _t = int(_within_level_n.get(_lev, 0))
            _pct, _ = share_safe.safe_pct_with_denominator(
                _c1, _t, threshold=_SS_C10_THR, enabled=_SS_C10)
            _rate_x.append(str(_lev))
            _rate_h.append(_pct if isinstance(_pct, (int, float)) else np.nan)
        axes[1].bar(_rate_x, _rate_h, color=_C1)
        axes[1].set_xlabel(f"{dv} level")
        axes[1].set_ylabel("P(target=1 | level)  %   [denominator = N within level]")
        axes[1].tick_params(axis="x", rotation=45)
        axes[1].set_ylim(0, max(100, np.nanmax(_rate_h + [1]) * 1.15))
    _n_miss_p = int(df_analysis[dv].isna().sum())
    _n_disp = share_safe.safe_count_with_complement(
        len(_data), len(df_analysis), threshold=_SS_C10_THR, enabled=_SS_C10)
    fig.suptitle(f"{dv}  (N={_n_disp}, missing={share_safe.safe_count(_n_miss_p, threshold=_SS_C10_THR, enabled=_SS_C10)})")
    plt.tight_layout()
    plt.show()

# ── Original-predictor redundancy matrix (recheck) ────────────────────────────
print()
print("Original-predictor redundancy recheck (Spearman rho >= 0.7 | Cramér's V >= 0.5):")
_numeric_vars = [c for c in ANALYSIS_VARS if infer_var_type(df_analysis[c]) == "numeric"]
_cat_vars = [c for c in ANALYSIS_VARS if infer_var_type(df_analysis[c]) in ("binary", "categorical")]

_REDUNDANCY_PAIRS_COLS = ["var1", "var2", "measure", "value"]
high_redundancy_pairs = []
if len(_numeric_vars) >= 2:
    for i, v1 in enumerate(_numeric_vars):
        for v2 in _numeric_vars[i + 1:]:
            _pair = df_analysis[[v1, v2]].dropna()
            if len(_pair) >= 10:
                rho = stats.spearmanr(_pair[v1], _pair[v2]).statistic
                if pd.notna(rho) and abs(rho) >= 0.7:
                    high_redundancy_pairs.append({"var1": v1, "var2": v2,
                                                   "measure": "spearman_rho",
                                                   "value": round(float(rho), 3)})
if len(_cat_vars) >= 2:
    for i, v1 in enumerate(_cat_vars):
        for v2 in _cat_vars[i + 1:]:
            _pair = df_analysis[[v1, v2]].dropna()
            if len(_pair) >= 10:
                _tab = pd.crosstab(_pair[v1], _pair[v2])
                if _tab.shape[0] >= 2 and _tab.shape[1] >= 2:
                    cv = cramers_v(_tab)
                    if pd.notna(cv) and cv >= 0.5:
                        high_redundancy_pairs.append({"var1": v1, "var2": v2,
                                                       "measure": "cramers_v",
                                                       "value": round(cv, 3)})

redundancy_pairs_df = pd.DataFrame(high_redundancy_pairs, columns=_REDUNDANCY_PAIRS_COLS)
if len(redundancy_pairs_df):
    print(redundancy_pairs_df.to_string(index=False))
else:
    print("  No high-redundancy pairs found (rho >= 0.7 or V >= 0.5).")

# ── Explicit named redundancy pairs (raw source vs. deterministic derivative) ──
# The generic pairwise scan above will surface these numerically, but the
# specific relationship, audit visibility, and enforcement point are
# documented explicitly here rather than left implicit in a large pairs table.
print()
print("Named raw/deterministic-derivative pairs (explicit documentation):")
_named_pairs = [
    {
        "pair": ("mode_of_conception", "mode_of_conception_ivf_vs_all"),
        "relationship_type": (
            "mode_of_conception_ivf_vs_all is a deterministic re-expression of "
            "mode_of_conception (== 1 iff mode_of_conception == 1, else 0; "
            "Decision 30), carrying no information not already in "
            "mode_of_conception."
        ),
        "both_visible_for_audit": "yes -- both remain in df_analysis and ANALYSIS_VARS",
        "may_both_enter_same_model": (
            "NO -- this is one of the eight HARD, target-independent co-entry "
            "pairs in the C13 contract (reason_type = deterministic_recompute; "
            "sole authored source: contracts/model_coentry_constraints.yaml). "
            "EDA C keeps BOTH eligible (it does not pre-judge eligibility by "
            "dropping one), but the contract records that they may never be "
            "simultaneously entered as independent model predictors, in any "
            "model family including LASSO / Elastic Net. This is a "
            "deterministic-lineage fact, NOT target-informed feature selection."
        ),
        "redundancy_decision_enforced_where": (
            "C13 hard co-entry registry (target-independent, global). EDA C keeps "
            "both eligible; the co-entry prohibition is a fixed contract, not a "
            "target-informed CV choice."
        ),
    },
]
for _p in _named_pairs:
    _v1, _v2 = _p["pair"]
    _both_present = _v1 in df_analysis.columns and _v2 in df_analysis.columns
    print(f"  {_v1} <-> {_v2}  (both present in df_analysis: {_both_present})")
    print(f"    Relationship  : {_p['relationship_type']}")
    print(f"    Audit visible : {_p['both_visible_for_audit']}")
    print(f"    Same model?   : {_p['may_both_enter_same_model']}")
    print(f"    Enforced where: {_p['redundancy_decision_enforced_where']}")
    if _both_present:
        _pair_data = df_analysis[[_v1, _v2]].dropna()
        if len(_pair_data) >= 10:
            _tab = pd.crosstab(_pair_data[_v1], _pair_data[_v2])
            if _tab.shape[0] >= 2 and _tab.shape[1] >= 2:
                _cv = cramers_v(_tab)
                print(f"    Measured Cramer's V (this run, N={len(_pair_data)}): {_cv:.3f}")
""")

SC10B_HEADER = md("eda-c-s10b-header", """
## Section C10b — Derived-Feature Formula and Interpretation Registry

Documents, for **every materialized** derived feature validated in C10 above:
the exact formula/rule, its intended clinical interpretation, and its
valid-value range. This is documentation only — it creates no new column.

**Single source of truth.** The deterministic parts (formula inputs, rule,
allowed non-missing output values, NaN propagation) are pulled directly from
the shared `DERIVED_FEATURE_CONTRACTS` object defined in C9 and also used by
C10's valid-value check and the tests — there is **no second, independently
maintained valid-value set**. C10b adds only the clinical-interpretation text.

**Coverage is FAIL-LOUD.** If any materialized `DERIVED_VARS` member has no
registry entry, this section raises — a canonical EDA C run must never claim
complete derived-feature documentation while a materialized feature has no
formula contract.

`derived_endo_surgery_adhesion_status` appears here as **lineage-only**
documentation (it is created upstream in Data Cleaning B, not in EDA C, and is
not in `DERIVED_VARS`); its current B implementation has **3 active states** —
the retired `prior_surgery_adhesion_status_unknown` state is not materialized
and is not listed as an active valid value.
""")

SC10B_REGISTRY = code("eda-c-s10b-registry", """
# Clinical-interpretation text ONLY -- the deterministic formula/valid-value
# parts come from the shared DERIVED_FEATURE_CONTRACTS (C9). Keeping the two
# layers separate avoids a divergent second registry (PART D3).
_DERIVED_INTERPRETATION = {
    "derived_prior_endo_surgery_procedure_status": {
        "interpretation": (
            "Exploratory prior-endometriosis-surgery status with a coarse "
            "documentation-status distinction for a selected subset of reliably "
            "coded structured procedure variables; NOT a severity score, NOT a "
            "burden score, and NOT a claim that 'no selected procedure documented' "
            "means no procedure occurred"
        ),
    },
    "derived_placental_dysfunction_proxy": {
        "interpretation": (
            "Exploratory placenta-mediated complication proxy based only on PET "
            "status and IUGR; NOT a validated clinical score, NOT a severity "
            "score, and NOT a missingness indicator"
        ),
    },
    "derived_nulliparity_with_prior_cs": {
        "interpretation": (
            "SANITY-CHECK ONLY -- flags a logically inconsistent combination "
            "(nulliparous but has a prior CS); not a modeling candidate. A "
            "non-zero count indicates a data-quality issue, not a real clinical "
            "subgroup"
        ),
    },
    "derived_hypertension_pih_pet_spectrum": {
        "interpretation": (
            "Approved 3-level clinical grouping of the hypertension family "
            "(Decision 77): none / PIH-gestational-hypertension / "
            "preeclampsia-spectrum. Defined from clinical/source semantics "
            "(Decision 45), NOT target association. Co-entry with the individual "
            "hypertension source variables is review_within_modeling "
            "(hypertension_spectrum relationship group) -- NOT an automatic HARD "
            "pair; this feature has no HARD co-entry pair in the C13 registry"
        ),
    },
    "derived_diabetes_type_grouped": {
        "interpretation": (
            "Approved 4-level grouping of diabetes_type's confirmed code "
            "dictionary (Decision 78): no_diabetes / pregestational (1,2,3) / "
            "GDMA1 (4) / GDMA2 (5). Grouped on category-size and clinical-"
            "interpretability grounds, NOT target association"
        ),
    },
}

# Lineage-only entry for the B-created adhesion-status column (NOT in DERIVED_VARS).
_ADHESION_LINEAGE_ONLY = {
    "derived_endo_surgery_adhesion_status": {
        "status": "lineage_only -- created in Data Cleaning B (Section B5g, 2026-08-27), not EDA C",
        "formula": (
            "no_prior_endo_surgery if endometriosis_surgery==0; "
            "prior_surgery_without_documented_adhesions if endometriosis_surgery==1 and "
            "endo_surgery_adhesiolysis==0; prior_surgery_with_documented_adhesions if "
            "endometriosis_surgery==1 and endo_surgery_adhesiolysis==1"
        ),
        "interpretation": (
            "Exploratory prior-endometriosis-surgery adhesion finding/status "
            "representation; does NOT indicate whether adhesiolysis was performed; "
            "NOT a severity/burden score, NOT a standalone missingness indicator"
        ),
        "active_valid_values": "{no_prior_endo_surgery, prior_surgery_without_documented_adhesions, "
                               "prior_surgery_with_documented_adhesions} + NaN (3 active states; "
                               "the retired 'prior_surgery_adhesion_status_unknown' state is NOT "
                               "materialized in the current B implementation)",
    },
}

# Assemble the printed registry for materialized features from the SHARED contract.
DERIVED_VAR_FORMULAS = {}
for _dv in DERIVED_VARS:
    _c = DERIVED_FEATURE_CONTRACTS.get(_dv)
    _i = _DERIVED_INTERPRETATION.get(_dv, {})
    if _c is None:
        continue
    _allowed_disp = "{" + ", ".join(sorted(str(v) for v in _c["allowed_values"])) + ", NaN}"
    DERIVED_VAR_FORMULAS[_dv] = {
        "formula_inputs": _c["formula_inputs"],
        "formula": _c["rule"],
        "nan_propagation": _c["nan_propagation"],
        "valid_range": _allowed_disp,
        "intended_interpretation": _i.get("interpretation", "(interpretation text missing)"),
    }

print("Derived-feature formula/interpretation/valid-range registry "
      "(deterministic parts from the shared DERIVED_FEATURE_CONTRACTS):")
for _dv in DERIVED_VARS:
    _f = DERIVED_VAR_FORMULAS.get(_dv)
    if _f is None:
        continue
    print(f"  {_dv}")
    print(f"    Formula inputs : {_f['formula_inputs']}")
    print(f"    Rule           : {_f['formula']}")
    print(f"    NaN propagation : {_f['nan_propagation']}")
    print(f"    Valid range    : {_f['valid_range']}")
    print(f"    Interpretation : {_f['intended_interpretation']}")

print()
print("Lineage-only (created in Data Cleaning B, not EDA C):")
for _dv, _e in _ADHESION_LINEAGE_ONLY.items():
    print(f"  {_dv}  [{_e['status']}]")
    print(f"    Rule                : {_e['formula']}")
    print(f"    Active valid values : {_e['active_valid_values']}")

# PART D1: missing registry coverage of a MATERIALIZED feature is now FAIL-LOUD.
_missing_registry = [dv for dv in DERIVED_VARS if dv not in DERIVED_VAR_FORMULAS]
if _missing_registry:
    raise RuntimeError(
        "C10b: materialized derived feature(s) have NO formula/interpretation "
        f"registry entry: {_missing_registry}. A canonical EDA C run must not "
        "claim complete derived-feature validation while a materialized feature "
        "has no formula contract."
    )
# Cross-check: the shared contract's allowed_values must match what C10 validated.
for _dv in DERIVED_VARS:
    _c10_note = derived_validation_df.loc[
        derived_validation_df["derived_feature"] == _dv, "impossible_note"
    ]
    assert len(_c10_note) == 1 and not str(_c10_note.iloc[0]).startswith("values outside"), (
        f"C10b: {_dv} failed its C10 valid-value contract check -- registries disagree"
    )
print()
print("C10b coverage OK: every materialized DERIVED_VARS member has a shared-contract "
      "registry entry; no divergent valid-value set is maintained here.")
""")


# ── Section C10c ───────────────────────────────────────────────────────────────
SC10C_HEADER = md("eda-c-s10c-header", """
## Section C10c — Predictor–Predictor Relationships & Redundancy (adapts CURRENT A2.10)

Ports the richer **CURRENT A2 Section A2.10** predictor–predictor architecture
onto the cleaned analysis universe (`ANALYSIS_VARS` + implementable derived
features, i.e. `SCREEN_VARS`):

- **A. Numeric–numeric** — Spearman correlation matrix + heatmap; high-|ρ| pair
  table (|ρ| ≥ 0.7); one scatterplot per high-|ρ| pair (not every pair).
- **B. Numeric–categorical** — per pair, Kruskal–Wallis H + epsilon-squared
  effect size. The Kruskal H statistic is computed only on the **retained
  groups** (each ≥ 3 observations, preserving the A2 convention), so the
  epsilon-squared denominator and the reported analysis N use **exactly those
  same observations** — `n_analyzed = Σ len(retained group)`, never
  `len(complete_pair)`. Each row exposes `n_complete_pair`, `n_analyzed`,
  `n_excluded_small_groups`, `n_groups_analyzed`, `kruskal_H`, `p_value`,
  `epsilon_squared`. A pair with fewer than two analyzable groups is skipped
  with a documented reason. The ε² ≥ 0.10 descriptive threshold is applied to
  the **corrected** effect size. No eligibility decision depends on it.
- **C. Categorical–categorical** — Cramér's V matrix + heatmap; high-V pair
  table (V ≥ 0.5).
- **D. Representation-relationship classification** for **every** high-association
  pair from A, B **and** C — including numeric×categorical: `exact/superseded
  duplicate` / `deterministic re-expression` / `clinically overlapping` /
  `clinically distinct but correlated`. Each row keeps its own
  `strength_measure` (`spearman_rho` / `cramers_v` / `epsilon_squared`) — these
  are **different, non-interchangeable** strength scales, never compared as a
  signed effect. B-lineage matching uses **exact source-variable tokens** (the
  feature-dictionary comma delimiter), not substring containment.
- **D (audit).** The known deterministic pairs `P ↔ nulliparity` and
  `CS ↔ S_P_CS` are audited explicitly: if they meet the live high-association
  criterion they appear in the classification table; otherwise their measured
  relationship is reported as a named deterministic-lineage check so the known
  relationship is never lost to an arbitrary descriptive threshold.

**No variable is removed here.** High pairwise association is disclosed for
EDA D's collinearity handling — a high correlation between two clinically
distinct predictors is NOT a duplicate. No target variable is used in any
representation-classification decision.

### Cramér's V estimator — final methodological decision (2026-09-01)
The **uncorrected** Cramér's V estimator (`chi2_contingency(..., correction=
False)`, `sqrt(chi2 / (n * (min(table.shape) - 1)))`) is retained as canonical
across A1/A2/EDA C for cross-stage consistency, not because it is assumed to
be universally superior to the bias-corrected (Bergsma–Wicher) estimator. It
is a **descriptive/diagnostic association-strength measure only**: the V ≥ 0.5
threshold above is a descriptive review threshold, no feature
eligibility/exclusion decision is based on Cramér's V alone, and no hard
co-entry constraint is ever generated from it. A bias-corrected sensitivity
check was performed against the live 431-row cohort's high-association
categorical–categorical pairs (49 pairs at the current V ≥ 0.5 threshold,
including the newly-eligible PET-family pairs): it changed values slightly
and moved 3 pairs below the descriptive 0.5 threshold
(`indication_for_induction_status`↔`derived_hypertension_pih_pet_spectrum`,
`any_PET_cat`↔`indication_for_induction_status`,
`endo_resection_ovarian_endometrioma_unilateral`↔`derived_prior_endo_surgery_
procedure_status`). It changed **no** eligibility, candidate-pool,
hard-exclusion, co-entry, or modeling decision — therefore it does not
replace the canonical estimator.
""")

SC10C_RELATIONSHIPS = code("eda-c-s10c-relationships", """
# C10c runs before C11, so SCREEN_VARS is not defined yet -- build the same
# universe inline (ANALYSIS_VARS + implementable derived features).
_rel_vars = [c for c in (ANALYSIS_VARS + [dv for dv in DERIVED_VARS
             if dv != "derived_nulliparity_with_prior_cs"]) if c in df_analysis.columns]
_num = [c for c in _rel_vars if infer_var_type(df_analysis[c]) == "numeric"]
_cat = [c for c in _rel_vars if infer_var_type(df_analysis[c]) in ("binary", "categorical")]
print(f"C10c predictor-predictor scope: {len(_rel_vars)} variables ({len(_num)} numeric, {len(_cat)} binary/categorical)")

# ── A. Numeric-numeric: Spearman matrix + heatmap + high-|rho| pairs ──────────
numeric_spearman_df = pd.DataFrame()
nn_high_pairs_df = pd.DataFrame()
if len(_num) >= 2:
    numeric_spearman_df = df_analysis[_num].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(min(1.0 + 0.5 * len(_num), 14), min(1.0 + 0.5 * len(_num), 14)))
    sns.heatmap(numeric_spearman_df, cmap="vlag", center=0, vmin=-1, vmax=1, square=True,
                cbar_kws={"shrink": 0.6}, ax=ax)
    ax.set_title("C10c-A  Spearman correlation matrix (numeric predictors)")
    plt.tight_layout(); plt.show(); plt.close(fig)
    _nn = []
    for _i in range(len(_num)):
        for _j in range(_i + 1, len(_num)):
            _a, _b = _num[_i], _num[_j]
            _pair = df_analysis[[_a, _b]].dropna()
            if len(_pair) < 10:
                continue
            _rho = stats.spearmanr(_pair[_a], _pair[_b]).statistic
            if pd.notna(_rho) and abs(_rho) >= 0.7:
                _nn.append({"var_a": _a, "var_b": _b, "spearman_rho": round(float(_rho), 3), "n": len(_pair)})
    nn_high_pairs_df = pd.DataFrame(_nn, columns=["var_a", "var_b", "spearman_rho", "n"])
    if len(nn_high_pairs_df):
        nn_high_pairs_df = nn_high_pairs_df.sort_values(
            "spearman_rho", key=lambda s: s.abs(), ascending=False)
    print()
    print("A. High numeric-numeric correlation (|Spearman rho| >= 0.7):")
    print(nn_high_pairs_df.to_string(index=False) if len(nn_high_pairs_df) else "  none")
    for _r in nn_high_pairs_df.to_dict("records"):
        _pd = df_analysis[[_r["var_a"], _r["var_b"], TARGET_COL]].dropna()
        fig, ax = plt.subplots(figsize=(5, 4))
        sns.scatterplot(data=_pd, x=_r["var_a"], y=_r["var_b"], hue=TARGET_COL, palette={0: _C0, 1: _C1}, ax=ax, s=22)
        ax.set_title(f"{_r['var_a']} vs {_r['var_b']}  (rho={_r['spearman_rho']}, n={_r['n']})")
        plt.tight_layout(); plt.show(); plt.close(fig)
else:
    print("A. Fewer than 2 numeric predictors -- numeric-numeric matrix skipped.")

# ── B. Numeric-categorical: Kruskal-Wallis + epsilon^2 ────────────────────────
# BLOCKER 1 FIX: the Kruskal H statistic is computed on the RETAINED groups
# only (each >= 3 obs, the A2 convention). The epsilon-squared denominator and
# the reported analysis N must therefore use those SAME observations, not
# len(complete_pair). Every field below reconciles:
#   n_complete_pair = n_analyzed + n_excluded_small_groups.
_NUMCAT_MIN_GROUP = 3
_NUMCAT_MIN_PAIR = 15


def _epsilon_squared(h_stat, n_analyzed, k_groups):
    # n_analyzed MUST be the number of observations actually passed to
    # stats.kruskal (sum of retained group sizes), not the full complete-pair N.
    return float((h_stat - k_groups + 1) / (n_analyzed - k_groups)) if n_analyzed > k_groups else float("nan")


_NUMCAT_COLS = [
    "numeric", "categorical", "n_complete_pair", "n_analyzed",
    "n_excluded_small_groups", "n_groups_analyzed", "kruskal_H", "p_value",
    "epsilon_squared", "high_association", "skipped_reason",
]
_numcat_rows = []
for _nc in _num:
    for _cc in _cat:
        _pair = df_analysis[[_nc, _cc]].dropna()
        _n_complete = int(len(_pair))
        if _n_complete < _NUMCAT_MIN_PAIR or _pair[_cc].nunique() < 2:
            continue
        _kept = [(str(_gn), g[_nc].to_numpy()) for _gn, g in _pair.groupby(_cc)
                 if len(g) >= _NUMCAT_MIN_GROUP]
        _n_groups = len(_kept)
        _n_analyzed = int(sum(len(v) for _, v in _kept))
        _n_excluded = _n_complete - _n_analyzed
        if _n_groups < 2:
            _numcat_rows.append({
                "numeric": _nc, "categorical": _cc, "n_complete_pair": _n_complete,
                "n_analyzed": _n_analyzed, "n_excluded_small_groups": _n_excluded,
                "n_groups_analyzed": _n_groups, "kruskal_H": float("nan"),
                "p_value": float("nan"), "epsilon_squared": float("nan"),
                "high_association": False,
                "skipped_reason": f"fewer than 2 groups with >= {_NUMCAT_MIN_GROUP} observations",
            })
            continue
        try:
            _h, _p = stats.kruskal(*[v for _, v in _kept])
        except ValueError as _e:
            _numcat_rows.append({
                "numeric": _nc, "categorical": _cc, "n_complete_pair": _n_complete,
                "n_analyzed": _n_analyzed, "n_excluded_small_groups": _n_excluded,
                "n_groups_analyzed": _n_groups, "kruskal_H": float("nan"),
                "p_value": float("nan"), "epsilon_squared": float("nan"),
                "high_association": False, "skipped_reason": f"kruskal ValueError: {_e}",
            })
            continue
        _eps2 = _epsilon_squared(_h, _n_analyzed, _n_groups)
        _numcat_rows.append({
            "numeric": _nc, "categorical": _cc, "n_complete_pair": _n_complete,
            "n_analyzed": _n_analyzed, "n_excluded_small_groups": _n_excluded,
            "n_groups_analyzed": _n_groups, "kruskal_H": round(float(_h), 2),
            "p_value": float(_p),
            "epsilon_squared": round(_eps2, 3) if pd.notna(_eps2) else float("nan"),
            "high_association": bool(pd.notna(_eps2) and _eps2 >= 0.10),
            "skipped_reason": "",
        })

numeric_categorical_df = pd.DataFrame(_numcat_rows, columns=_NUMCAT_COLS)
if len(numeric_categorical_df):
    numeric_categorical_df = numeric_categorical_df.sort_values(
        "epsilon_squared", ascending=False, na_position="last")
# reconciliation: every analyzed row must satisfy n_complete = n_analyzed + n_excluded
_bad_recon = numeric_categorical_df[
    numeric_categorical_df["n_complete_pair"]
    != numeric_categorical_df["n_analyzed"] + numeric_categorical_df["n_excluded_small_groups"]
] if len(numeric_categorical_df) else numeric_categorical_df
if len(_bad_recon):
    raise RuntimeError(
        "C10c-B reconciliation FAILED: n_complete_pair != n_analyzed + "
        f"n_excluded_small_groups for:\\n{_bad_recon.to_string(index=False)}"
    )
numcat_high_pairs_df = (
    numeric_categorical_df[numeric_categorical_df["high_association"]].copy()
    if len(numeric_categorical_df) else numeric_categorical_df
)
print()
print("B. Numeric x categorical (Kruskal-Wallis on retained groups; epsilon^2 uses "
      "n_analyzed = sum of retained-group sizes, NOT len(complete_pair)):")
print(numeric_categorical_df.to_string(index=False) if len(numeric_categorical_df) else "  none analyzable")
print(f"  strong (epsilon^2 >= 0.10, corrected): {len(numcat_high_pairs_df)}")

# ── C. Categorical-categorical: Cramer's V matrix + heatmap + high-V pairs ────
categorical_cramersv_df = pd.DataFrame()
cc_high_pairs_df = pd.DataFrame(columns=["var_a", "var_b", "cramers_v", "n"])
if len(_cat) >= 2:
    _cv_mat = pd.DataFrame(np.eye(len(_cat)), index=_cat, columns=_cat)
    _cc = []
    for _i in range(len(_cat)):
        for _j in range(_i + 1, len(_cat)):
            _a, _b = _cat[_i], _cat[_j]
            _pair = df_analysis[[_a, _b]].dropna()
            _v = float("nan")
            if len(_pair) >= 10:
                _tab = pd.crosstab(_pair[_a], _pair[_b])
                if _tab.shape[0] >= 2 and _tab.shape[1] >= 2:
                    _v = cramers_v(_tab)
            _cv_mat.loc[_a, _b] = _cv_mat.loc[_b, _a] = _v
            if pd.notna(_v) and _v >= 0.5:
                _cc.append({"var_a": _a, "var_b": _b, "cramers_v": round(_v, 3), "n": len(_pair)})
    categorical_cramersv_df = _cv_mat
    cc_high_pairs_df = pd.DataFrame(_cc, columns=["var_a", "var_b", "cramers_v", "n"])
    if len(cc_high_pairs_df):
        cc_high_pairs_df = cc_high_pairs_df.sort_values("cramers_v", ascending=False)
    fig, ax = plt.subplots(figsize=(min(1.0 + 0.45 * len(_cat), 16), min(1.0 + 0.45 * len(_cat), 16)))
    sns.heatmap(_cv_mat.astype(float), cmap="rocket_r", vmin=0, vmax=1, square=True,
                cbar_kws={"shrink": 0.6}, ax=ax)
    ax.set_title("C10c-C  Cramer's V matrix (binary/categorical predictors)")
    ax.tick_params(labelsize=7)
    plt.tight_layout(); plt.show(); plt.close(fig)
    print()
    print("C. High categorical-categorical association (Cramer's V >= 0.5):")
    print(cc_high_pairs_df.to_string(index=False) if len(cc_high_pairs_df) else "  none")
else:
    print("C. Fewer than 2 binary/categorical predictors -- Cramer's V matrix skipped.")

# ── D. Representation-relationship classification for EVERY high-association pair ─
# BLOCKER 2 FIX: numeric x categorical high pairs are now included, not only
# numeric-numeric and categorical-categorical. Uses lineage/decision facts only
# (target-independent -- no target variable is referenced anywhere in D).
# PART G: exact source-variable-token B-lineage matching (feature-dictionary
# comma delimiter), NOT substring containment.
_B_SRC_TOKENS = {}
if B_FEATURE_DICT is not None and "new_column" in B_FEATURE_DICT.columns:
    for _newc, _srcc in zip(B_FEATURE_DICT["new_column"], B_FEATURE_DICT["source_column"]):
        _B_SRC_TOKENS[str(_newc)] = [t.strip() for t in str(_srcc).split(",") if t.strip()]

_DETERMINISTIC_PAIRS = {
    frozenset({"mode_of_conception", "mode_of_conception_ivf_vs_all"}): "deterministic re-expression (ivf_vs_all == 1 iff mode_of_conception == 1) -- HARD target-independent co-entry pair in the C13 YAML contract; the two must never enter a model together",
    frozenset({"P", "nulliparity"}): "deterministic derivation (nulliparity == 1 iff P == 0; nulliparity is recomputed upstream directly from the authoritative parity count P) -- review-only relationship group (parity_obstetric_history), NOT a hard co-entry pair: nulliparity is a NONLINEAR basis function of P, so P (count) and I(P == 0) (threshold) can jointly enter a model; joint entry is a modeling-review / coefficient-stability matter, not a global ban. P also carries the full parity count",
    frozenset({"S_P_CS", "CS"}): "deterministic re-expression at the binary level (S_P_CS == 1 iff CS > 0) -- review-only relationship group, not a hard co-entry pair; CS also carries the prior-CS count, clinically distinct for TOLAC risk",
    frozenset({"BMI_before", "weight_before_pregnancy"}): "index vs component (BMI_before = weight/(height/100)^2)",
    frozenset({"BMI_before", "height"}): "index vs component (BMI_before = weight/(height/100)^2)",
}
_OVERLAP_FAMILIES = {
    "endometriosis phenotype": {"endometrioma", "endometrioma_size_status", "endometrioma_presence_laterality",
                                 "deep_endometriosis", "adenomyosis", "peritoneal_endometriosis", "cs_scar_endometriosis"},
    "hypertension spectrum": {"pregnancy_related_hypertensive_disorder", "PIH", "mild_PET", "SIPET",
                               "severe_PET_cat", "any_PET_cat", "derived_hypertension_pih_pet_spectrum"},
    "diabetes": {"gestational_diabetes", "diabetes_type", "derived_diabetes_type_grouped"},
    "parity / obstetric history": {"G", "P", "LIVE_BIRTH", "AB", "EUP", "nulliparity"},
    "prior CS": {"S_P_CS", "CS", "VBAC"},
    "prior endo surgery": {"endometriosis_surgery", "derived_endo_surgery_adhesion_status",
                            "derived_prior_endo_surgery_procedure_status"},
}


def _exact_b_lineage(a, b):
    # exact variable-token membership, not substring containment
    return (b in _B_SRC_TOKENS.get(a, [])) or (a in _B_SRC_TOKENS.get(b, []))


def _classify_pair(a, b):
    fs = frozenset({a, b})
    if _exact_b_lineage(a, b):
        return "exact/superseded or direct-lineage representation (one is derived in B from the other)"
    if fs in _DETERMINISTIC_PAIRS:
        return _DETERMINISTIC_PAIRS[fs]
    for _fam, _members in _OVERLAP_FAMILIES.items():
        if a in _members and b in _members:
            return f"clinically overlapping ({_fam}) -- redundancy disclosed, both retained"
    return "clinically distinct but correlated -- retain both; NOT a duplicate"


_REL_COLS = ["var_a", "var_b", "relationship_kind", "strength_measure", "strength", "n",
             "representation_classification"]
_all_high_pairs = []
for _r in (nn_high_pairs_df.to_dict("records") if len(nn_high_pairs_df) else []):
    _all_high_pairs.append({
        "var_a": _r["var_a"], "var_b": _r["var_b"], "relationship_kind": "numeric-numeric",
        "strength_measure": "spearman_rho", "strength": _r["spearman_rho"], "n": _r["n"],
        "representation_classification": _classify_pair(_r["var_a"], _r["var_b"]),
    })
for _r in (cc_high_pairs_df.to_dict("records") if len(cc_high_pairs_df) else []):
    _all_high_pairs.append({
        "var_a": _r["var_a"], "var_b": _r["var_b"], "relationship_kind": "categorical-categorical",
        "strength_measure": "cramers_v", "strength": _r["cramers_v"], "n": _r["n"],
        "representation_classification": _classify_pair(_r["var_a"], _r["var_b"]),
    })
for _r in (numcat_high_pairs_df.to_dict("records") if len(numcat_high_pairs_df) else []):
    _all_high_pairs.append({
        "var_a": _r["numeric"], "var_b": _r["categorical"], "relationship_kind": "numeric-categorical",
        "strength_measure": "epsilon_squared", "strength": _r["epsilon_squared"], "n": _r["n_analyzed"],
        "representation_classification": _classify_pair(_r["numeric"], _r["categorical"]),
    })
representation_relationship_df = pd.DataFrame(_all_high_pairs, columns=_REL_COLS)
if len(representation_relationship_df):
    representation_relationship_df = representation_relationship_df.sort_values(
        ["relationship_kind", "strength"], ascending=[True, False])
print()
print("D. Representation-relationship classification of EVERY high-association pair "
     "(numeric-numeric + categorical-categorical + numeric-categorical; "
     "target-independent lineage/decision facts only; strength_measure kept per row):")
print(representation_relationship_df.to_string(index=False) if len(representation_relationship_df)
      else "  no high-association pairs to classify")

# ── D (audit). Named deterministic cross-type / lineage checks ────────────────
# P/nulliparity and CS/S_P_CS are known deterministic relationships. If they
# do not clear the descriptive high-association threshold above, their measured
# relationship is still reported here so the known relationship is not lost.
_DET_AUDIT_COLS = ["var_a", "var_b", "pair_type", "strength_measure", "measured_strength",
                   "in_representation_table", "known_relationship"]
_det_audit_rows = []
_rep_pairs_seen = {frozenset({r["var_a"], r["var_b"]}) for r in _all_high_pairs}
for _fs, _rel in _DETERMINISTIC_PAIRS.items():
    _a, _b = sorted(_fs)
    if _a not in df_analysis.columns or _b not in df_analysis.columns:
        _det_audit_rows.append({
            "var_a": _a, "var_b": _b, "pair_type": "n/a (not both present)",
            "strength_measure": "n/a", "measured_strength": float("nan"),
            "in_representation_table": False, "known_relationship": _rel,
        })
        continue
    _ta = infer_var_type(df_analysis[_a])
    _tb = infer_var_type(df_analysis[_b])
    _pr = df_analysis[[_a, _b]].dropna()
    _meas = float("nan")
    _measure = "n/a"
    _ptype = f"{_ta}-{_tb}"
    if len(_pr) >= 10:
        if _ta == "numeric" and _tb == "numeric":
            _measure = "spearman_rho"
            _rr = stats.spearmanr(_pr[_a], _pr[_b]).statistic
            _meas = float(abs(_rr)) if pd.notna(_rr) else float("nan")
        elif _ta in ("binary", "categorical") and _tb in ("binary", "categorical"):
            _measure = "cramers_v"
            _tab = pd.crosstab(_pr[_a], _pr[_b])
            _meas = cramers_v(_tab) if min(_tab.shape) >= 2 else float("nan")
        else:
            _measure = "epsilon_squared"
            _numv, _catv = (_a, _b) if _ta == "numeric" else (_b, _a)
            _kept2 = [g[_numv].to_numpy() for _gn, g in _pr.groupby(_catv) if len(g) >= _NUMCAT_MIN_GROUP]
            if len(_kept2) >= 2:
                _hh, _ = stats.kruskal(*_kept2)
                _meas = _epsilon_squared(_hh, int(sum(len(v) for v in _kept2)), len(_kept2))
    _det_audit_rows.append({
        "var_a": _a, "var_b": _b, "pair_type": _ptype, "strength_measure": _measure,
        "measured_strength": round(_meas, 3) if pd.notna(_meas) else float("nan"),
        "in_representation_table": _fs in _rep_pairs_seen,
        "known_relationship": _rel,
    })
deterministic_lineage_audit_df = pd.DataFrame(_det_audit_rows, columns=_DET_AUDIT_COLS)
print()
print("D (audit). Named deterministic-pair lineage checks "
      "(reported regardless of the descriptive high-association threshold):")
print(deterministic_lineage_audit_df.to_string(index=False) if len(deterministic_lineage_audit_df)
      else "  (none)")
for _key in (("P", "nulliparity"), ("CS", "S_P_CS")):
    _row = deterministic_lineage_audit_df[
        (deterministic_lineage_audit_df["var_a"].isin(_key))
        & (deterministic_lineage_audit_df["var_b"].isin(_key))
    ]
    if len(_row):
        _r0 = _row.iloc[0]
        print(f"  {_key[0]} <-> {_key[1]}: {_r0['strength_measure']}="
              f"{_r0['measured_strength']}, in representation table: {_r0['in_representation_table']} "
              f"({_r0['known_relationship']})")

print()
print("REMINDER: C10c removes NO variable and changes NO eligibility. High pairwise "
      "association between clinically distinct predictors is a collinearity note for "
      "EDA D, not a duplicate. epsilon_squared, spearman_rho and Cramer's V are "
      "separate, non-interchangeable strength scales.")
""")


# ── Section C11 ────────────────────────────────────────────────────────────────
SC11_HEADER = md("eda-c-s11-header", """
## Section C11 — Exploratory Statistical Screening

> **EXPLORATORY SCREENING ONLY — not feature selection.**
> **Final feature selection must occur inside the modeling pipeline / cross-validation, not here.**

Association tests between each candidate variable (approved + derived) and the target.

**Test-selection contract (corrected 2026-09-01 -- see that correction's
Parts A-D). Every `SCREEN_VARS` member gets exactly one explicit screening
record; no variable silently disappears.**

- **Target-group support:** before any inferential test, the complete-case
  subset must contain at least one `target=0` AND at least one `target=1`
  observation. If either group is empty, the test is skipped
  (`test_status = "skipped_no_two_target_groups"`, `p_value = NaN`,
  `included_in_bh = False`) rather than crashed or given a fabricated p-value.
- **Numeric variables:** two-sided Mann-Whitney U, unchanged. Effect size is
  **signed** rank-biserial r, computed as
  `r = 2 * U(target1, target0) / (n1 * n0) - 1`, where `U(target1, target0)`
  is the Mann-Whitney U statistic computed with the `target=1` sample as the
  first argument (the count of (target1_i, target0_j) pairs with
  `target1_i > target0_j`, ties counted as 0.5). **Positive r means the
  predictor tends to be HIGHER in `target_intrapartum_cs = 1` than in
  `target_intrapartum_cs = 0`.** (Corrected 2026-09-01 -- the previous formula
  computed U with the target=0 sample first, which silently produced the
  opposite sign; the two-sided p-value is unchanged by this convention, since
  Mann-Whitney's two-sided p-value does not depend on argument order.)
  `effect_contrast = "target1_vs_target0"`; `target0_median` / `target1_median`
  are reported alongside.
- **Categorical variables — assumption diagnostics:** built from complete
  cases only. Every categorical/binary row records `table_shape`,
  `min_expected_count`, `n_expected_cells_lt5`, `pct_expected_cells_lt5`, and
  `any_expected_lt1` (from `scipy.stats.contingency.expected_freq`) — a sparse
  Rx2 table is never silently called an ordinary valid asymptotic chi-square.
- **2x2 tables:** unchanged project convention -- Fisher's exact test when the
  minimum expected cell count is `< 5`, ordinary chi-square (`correction=False`)
  otherwise. Effect size is an odds ratio with an **explicit, labelled
  contrast**: for a canonical binary 0/1 predictor,
  `OR = odds(target=1 | predictor=1) / odds(target=1 | predictor=0)`
  (`effect_contrast = "predictor1_vs_predictor0 (target1 odds)"`); for any
  other two-level categorical predictor, the exact two observed levels are
  recorded as `effect_level` (numerator/exposure) and `reference_level`
  (denominator/reference), sorted ascending, with
  `effect_contrast = "{effect_level}_vs_{reference_level} (target1 odds)"`.
  No unlabelled OR is ever emitted.
- **Zero-cell 2x2 tables:** if any of the four cells is 0, the ordinary sample
  OR is 0/undefined/infinite. No ad hoc continuity correction is invented.
  `effect_size = NaN` and `effect_estimate_status =
  "zero_cell_unstable_or_undefined"`; the exact/asymptotic test p-value (still
  valid) is retained and still enters the BH family.
- **Multi-level (Rx2) categorical tables (the corrected blocker):** an
  **assumption-aware** strategy replaces the previous "always asymptotic
  chi-square" behavior:
  1. **Adequate table** (no expected cell `< 1`, and `<= 20%` of expected
     cells `< 5` -- a conventional Cochran's-rule threshold; no stricter
     project-specific rule exists) -> ordinary asymptotic chi-square
     (`correction=False`), `test_status = "tested"`.
  2. **Sparse table**, installed SciPy supports a native Monte Carlo
     contingency-table method (`scipy.stats.chi2_contingency(...,
     method=scipy.stats.MonteCarloMethod(...))`, added in SciPy 1.15,
     feature-detected via `hasattr`, not a hardcoded version string) ->
     reproducible Monte Carlo p-value with a fixed seed and a fixed resample
     count (both named in the code), `test_status = "tested_monte_carlo"`,
     test name explicitly says "Monte Carlo" -- it is never presented as the
     ordinary asymptotic p-value.
  3. **Sparse table, no Monte Carlo support available** (or the call itself
     fails) -> `test_status = "descriptive_only_sparse_multilevel"`,
     `p_value = NaN`, `included_in_bh = False`. Cramér's V is still reported
     (see below) -- an invalid asymptotic p-value is never fabricated as a
     fallback.
- **Multi-level effect size:** Cramér's V is always computed and reported for
  multi-level categorical predictors, independent of which p-value branch
  above was taken -- the p-value method and the effect-size measure are two
  separate, clearly-labelled concerns; a Monte Carlo p-value does not change
  Cramér's V's definition.
- **Binary prevalence wording:** the two by-target percentages reported for a
  binary predictor are **predictor prevalence within each target group**
  (`predictor_prevalence_target1_pct`, `predictor_prevalence_target0_pct` --
  `g1.mean()*100` / `g0.mean()*100`), never "CS risk/rate" or "vaginal rate"
  -- those would be the reverse conditional (risk of the target given the
  predictor), which is not what these two group-means compute.

**BH-FDR family:** `SCREEN_VARS` is the **screening universe** (one row per
member, always) -- it is NOT automatically the BH hypothesis family. The
family is every `SCREEN_VARS` member with `included_in_bh = True`, i.e. every
successfully tested hypothesis (asymptotic or Monte Carlo) with a finite,
valid p-value; `bh_family_n` records that count and is attached to every row.
Skipped/descriptive-only rows stay visible in `screening_df` with
`included_in_bh = False` and `q_value_bh = NaN` -- "Screened N variables"
never implies all N contributed a p-value to Benjamini-Hochberg.

**Tested-hypothesis family scope (updated 2026-08-16 -- corrects a stale
pre-Decision-65 description; unchanged by the 2026-09-01 correction above):**
`SCREEN_VARS` itself is `ANALYSIS_VARS` + derived features, excluding the one
sanity-check-only derived feature. As of Decision 65 (2026-08-12),
`ANALYSIS_VARS` is the unified union of `predictor_allowed`,
`secondary_near_delivery_predictor`, and
`intrapartum_predictor_exclude_from_prelabor_model` columns present in
`df_analysis` -- only `intrapartum_candidate_pending_timing_confirmation`
columns (and other `_FORBIDDEN_COLS` categories) remain structurally absent
from `df_analysis` and therefore outside the BH-FDR family; secondary- and
intrapartum-horizon variables ARE part of it. This is intentional, not an
oversight: a variable's FDR-adjusted q-value is a property of the family it was
tested alongside, so **reclassifying any variable into or out of `ANALYSIS_VARS`
changes the family size and will shift every other tested variable's q-value**
(their raw p-values and effect sizes are unaffected) — this is the expected,
correct behavior of Benjamini-Hochberg, not a defect, and does not by itself
change any variable's eligibility decision. This remains the project's single
**global, unified multi-horizon** screening family -- Stage 1/2/3 are NOT
split into separate BH families in this correction; q-values are descriptive
exploratory signals only, not eligibility criteria, and stage-specific
modeling does not treat this global q-value as a fold-safe feature-selection
result.

A variable with a significant FDR-corrected q-value has an association signal
worth investigating further in the modeling pipeline. It is not sufficient grounds
for automatic inclusion — clinical rationale and redundancy considerations apply.

A non-significant q-value does not rule out a variable if it has strong clinical
prior support. Clinical priority tier (from `config.py`) is included where available.

**Presentation:** `screening_df` always retains exact analytical values. A
presentation-only `screening_display_df` additionally share-safe-suppresses
small `N` / `N_missing` / `target0_n` / `target1_n` / sparse-expected-cell-count
values under `SHARE_SAFE_MODE` for the printed table only -- p-values,
q-values, and effect sizes are never altered or suppressed.
""")

SC11_SCREENING = code("eda-c-s11-screening", """
print("=" * 70)
print("EXPLORATORY SCREENING ONLY — not feature selection.")
print("Final feature selection must occur inside the modeling pipeline / cross-validation.")
print("=" * 70)
print()


# ── Sparse-multilevel test-selection constants (2026-09-01 C11 correction) ─────
# Conventional Cochran's-rule chi-square adequacy threshold for an Rx2 table:
# no expected cell <1, and no more than this fraction of expected cells <5.
# No stricter CURRENT project rule exists, so this conventional threshold is
# used and documented explicitly (see SC11_HEADER).
MULTILEVEL_ADEQUACY_MAX_PCT_LT5 = 20.0
# Fixed, documented Monte Carlo configuration -- reproducible by construction.
MONTE_CARLO_SEED = 20260901
MONTE_CARLO_N_RESAMPLES = 9999


def benjamini_hochberg(p_values):
    # Benjamini-Hochberg FDR correction. NaN p-values (skipped / descriptive-
    # only hypotheses) are excluded from the family (m) and pass through as
    # NaN q-values, aligned position-for-position with the input index.
    # 2026-09-01 correction: any FINITE p-value outside [0, 1] now fails loud
    # instead of being silently accepted into the BH family -- the underlying
    # ranking/cummin algorithm itself is unchanged (validated independently in
    # test_c11_statistical_screening_correction_2026_09_01.py).
    p = pd.to_numeric(pd.Series(p_values), errors="coerce")
    adjusted = pd.Series(float("nan"), index=p.index, dtype=float)
    valid = p.dropna()
    _invalid = valid[(valid < 0) | (valid > 1)]
    if len(_invalid):
        raise ValueError(
            f"benjamini_hochberg received {len(_invalid)} finite p-value(s) "
            f"outside [0, 1]: {sorted(_invalid.tolist())}"
        )
    valid = valid.sort_values()
    if valid.empty:
        return adjusted
    m = len(valid)
    raw = valid * m / np.arange(1, m + 1)
    adjusted.loc[raw.index] = raw.iloc[::-1].cummin().iloc[::-1].clip(upper=1.0)
    return adjusted


def _categorical_assumption_diagnostics(table):
    # Chi-square adequacy diagnostics for a complete-case contingency table.
    # Used both for the 2x2 exact-vs-asymptotic decision (unchanged threshold)
    # and the multi-level adequate-vs-sparse decision (new). No rounding here
    # -- decisions below compare against these values directly, so rounding
    # first could shift a value across its own decision boundary.
    _expected = stats.contingency.expected_freq(table.to_numpy())
    _n_cells = int(_expected.size)
    _n_lt5 = int((_expected < 5).sum())
    return {
        "table_shape": table.shape,
        "min_expected_count": float(_expected.min()),
        "n_expected_cells_lt5": _n_lt5,
        "pct_expected_cells_lt5": (100.0 * _n_lt5 / _n_cells if _n_cells else float("nan")),
        "any_expected_lt1": bool((_expected < 1).any()),
    }


def _sparse_multilevel_monte_carlo(table):
    # Reproducible Monte Carlo chi-square p-value for a sparse Rx2 table,
    # using SciPy's native chi2_contingency(..., method=MonteCarloMethod(...))
    # support (added in SciPy 1.15). Feature-detected via hasattr, not a
    # hardcoded version string, so this degrades gracefully on an older SciPy
    # build. Returns (p_value, statistic), or None if unsupported or if the
    # call itself fails for any reason -- either way the caller falls back to
    # the explicit descriptive-only branch rather than an invalid asymptotic
    # p-value.
    if not hasattr(stats, "MonteCarloMethod"):
        return None
    try:
        _rng = np.random.default_rng(MONTE_CARLO_SEED)
        _method = stats.MonteCarloMethod(n_resamples=MONTE_CARLO_N_RESAMPLES, rng=_rng)
        _res = stats.chi2_contingency(table, correction=False, method=_method)
        return float(_res.pvalue), float(_res.statistic)
    except Exception:
        return None


# ── Timing label normalization ─────────────────────────────────────────────────
# Maps raw TIMING_MAP / derived_meta timing values to the richer labeling scheme
# used for feature-selection review. Per project guidance: timing must not become
# the dominant reason for excluding variables -- this remains true below (timing
# is disclosure-only; see timing_uncertain/meets_quality_bar further down, which
# never hard-exclude a variable from the pool).
#
# CORRECTED 2026-08-18 (timing-leakage prevention audit, gestational_age_at_
# delivery_days): the previous version of this function returned
# 'unknown_but_likely_pre_delivery' for genuinely unknown/absent timing,
# justified by a comment claiming "every variable reaching this point already
# passed the predictor_allowed classification gate in C3". That premise is
# FALSE -- SCREEN_VARS is built from ANALYSIS_VARS, which under Decision 65
# (2026-08-12) is the union of predictor_allowed, secondary_near_delivery_predictor,
# and intrapartum_predictor_exclude_from_prelabor_model; the latter two
# categories are never gated through C3's predictor_allowed check and, by
# config.py's own convention, are deliberately never given a TIMING_MAP entry
# at all (that map "may only contain predictor_allowed keys"). So every
# secondary/intrapartum-horizon variable with no TIMING_MAP entry was silently
# being asserted "likely pre-delivery" by default -- an assumption, not a fact.
# UNKNOWN TIMING != PRE-DELIVERY AVAILABLE: genuinely unknown/unclear timing
# now normalizes to a neutral 'timing_unknown' label instead. This label still
# sets timing_uncertain=True (unchanged, disclosure-only) and still never hard-
# excludes a variable (eligibility_status/candidate_role_for_modeling_review
# are driven by explicit classification-category branches elsewhere in this
# file, not by this function) -- the only behavior change is that
# compute_priority_score below no longer grants an implicit "presumed
# pre-delivery" scoring bonus for a variable whose timing is genuinely
# unresolved. Hard timing exclusion for variables truly known only at/after
# delivery is enforced upstream, at the canonical classification level (C2/C3
# -- those columns never reach ANALYSIS_VARS/SCREEN_VARS at all); this
# function was never the right place for that decision and still is not.
_POST_OUTCOME_RAW_TIMINGS = {"postpartum", "post_delivery", "neonatal", "outcome"}


def normalize_timing_label(raw_timing):
    if raw_timing in ("pre_pregnancy", "pregnancy"):
        return raw_timing
    # "antepartum" (a Data Cleaning B feature-dictionary clinical_timing value
    # for the PPROM timing family) means "during pregnancy, before birth" -- it
    # is a pre-delivery timing, equivalent to "pregnancy" for every use here
    # (descriptive labelling + the pre-admission scoring bonus). Added 2026-08-31
    # C2 correction so the feature dictionary can be authoritative for
    # B-registered variables' timing without collapsing to "timing_unknown".
    if raw_timing == "antepartum":
        return "pregnancy"
    if raw_timing == "admission_labor":
        return "admission_or_pre_delivery"
    if raw_timing in _POST_OUTCOME_RAW_TIMINGS:
        return "postpartum_or_outcome"
    if raw_timing in ("unclear", "unknown", "same_as_source", None):
        return "timing_unknown"
    return "timing_unknown"


SCREEN_VARS = ANALYSIS_VARS + [dv for dv in DERIVED_VARS
                                if dv != "derived_nulliparity_with_prior_cs"]

# Fail loud (2026-09-01 correction): SCREEN_VARS must not contain duplicate
# variable names -- a duplicate would silently receive two screening rows and
# corrupt the BH family count.
_screen_vars_series = pd.Series(SCREEN_VARS)
_screen_var_dups = sorted(set(_screen_vars_series[_screen_vars_series.duplicated()]))
if _screen_var_dups:
    raise AssertionError(f"SCREEN_VARS contains duplicate variable name(s): {_screen_var_dups}")

_SKIP_ROW_TEMPLATE = {
    "test_status": None, "included_in_bh": False, "test": "none",
    "statistic": float("nan"), "p_value": float("nan"),
    "effect_size": float("nan"), "effect_size_type": "—",
    "effect_contrast": "—", "effect_level": float("nan"),
    "reference_level": float("nan"), "effect_estimate_status": "not_applicable",
    "target0_median": float("nan"), "target1_median": float("nan"),
    "table_shape": "—", "min_expected_count": float("nan"),
    "n_expected_cells_lt5": float("nan"), "pct_expected_cells_lt5": float("nan"),
    "any_expected_lt1": None,
    "predictor_prevalence_target1_pct": float("nan"),
    "predictor_prevalence_target0_pct": float("nan"),
}

screening_rows = []
for col in SCREEN_VARS:
    if col not in df_analysis.columns:
        # No variable may silently disappear -- record the gap explicitly
        # rather than a silent `continue`. Not expected to fire given the
        # current ANALYSIS_VARS/df_analysis contract; kept as a fail-safe.
        screening_rows.append({
            **_SKIP_ROW_TEMPLATE,
            "variable": col, "type": "unknown", "N": 0, "N_missing": None,
            "target0_n": 0, "target1_n": 0, "n_levels": 0,
            "test_status": "skipped_variable_absent_from_df_analysis",
            "extra_info": "variable listed in SCREEN_VARS but absent from df_analysis",
        })
        continue

    vtype = infer_var_type(df_analysis[col])
    _pair = df_analysis[[col, TARGET_COL]].dropna()
    n_levels = int(_pair[col].nunique())
    g0 = _pair.loc[_pair[TARGET_COL] == 0, col]
    g1 = _pair.loc[_pair[TARGET_COL] == 1, col]

    if len(_pair) < 10 or n_levels < 2:
        screening_rows.append({
            **_SKIP_ROW_TEMPLATE,
            "variable": col, "type": vtype,
            "N": len(_pair), "N_missing": int(df_analysis[col].isna().sum()),
            "target0_n": int(len(g0)), "target1_n": int(len(g1)), "n_levels": n_levels,
            "test_status": "skipped_insufficient_data_or_zero_variance",
            "extra_info": "insufficient data or zero variance",
        })
        continue

    # A1 -- target-group support: never run an inferential test with an
    # empty target group; never fabricate a null p-value.
    if len(g0) == 0 or len(g1) == 0:
        screening_rows.append({
            **_SKIP_ROW_TEMPLATE,
            "variable": col, "type": vtype,
            "N": int(len(_pair)), "N_missing": int(df_analysis[col].isna().sum()),
            "target0_n": int(len(g0)), "target1_n": int(len(g1)), "n_levels": n_levels,
            "test_status": "skipped_no_two_target_groups",
            "extra_info": "one target group has zero complete-case observations",
        })
        continue

    if vtype == "numeric":
        n_g0, n_g1 = len(g0), len(g1)
        # Two-sided Mann-Whitney U, target=1 sample first so the signed
        # rank-biserial r below has an explicit, clinically readable
        # direction: positive r = predictor tends to be HIGHER in target=1
        # than target=0. r = 2*U(target1, target0)/(n1*n0) - 1. The two-sided
        # p-value is identical regardless of argument order (verified in the
        # correction tests), so this sign fix does not change any p-value.
        stat_g1, p = stats.mannwhitneyu(g1, g0, alternative="two-sided")
        effect = (2 * stat_g1 / (n_g1 * n_g0) - 1) if n_g0 * n_g1 > 0 else float("nan")
        screening_rows.append({
            "variable": col, "type": vtype,
            "N": int(len(_pair)), "N_missing": int(df_analysis[col].isna().sum()),
            "target0_n": n_g0, "target1_n": n_g1, "n_levels": n_levels,
            "test_status": "tested", "included_in_bh": True,
            "test": "Mann-Whitney U", "statistic": round(float(stat_g1), 1),
            "p_value": float(p), "effect_size": round(float(effect), 3),
            "effect_size_type": "rank-biserial r",
            "effect_contrast": "target1_vs_target0",
            "effect_level": float("nan"), "reference_level": float("nan"),
            "effect_estimate_status": "ok",
            "target0_median": float(g0.median()), "target1_median": float(g1.median()),
            "table_shape": "—", "min_expected_count": float("nan"),
            "n_expected_cells_lt5": float("nan"), "pct_expected_cells_lt5": float("nan"),
            "any_expected_lt1": None,
            "predictor_prevalence_target1_pct": float("nan"),
            "predictor_prevalence_target0_pct": float("nan"),
            "extra_info": f"target0_median={g0.median():.2f} target1_median={g1.median():.2f}",
        })
        continue

    # ── Categorical / binary ────────────────────────────────────────────────
    _tab = pd.crosstab(_pair[col], _pair[TARGET_COL])
    _levels = sorted(_pair[col].unique())
    _diag = _categorical_assumption_diagnostics(_tab)

    if _tab.shape == (2, 2):
        # Unchanged project convention: Fisher exact when the minimum
        # expected cell count is < 5, ordinary chi-square otherwise.
        if _diag["min_expected_count"] < 5:
            stat_ = float("nan")
            _, p = stats.fisher_exact(_tab)
            test_name = "Fisher exact"
        else:
            stat_, p, _, _ = stats.chi2_contingency(_tab, correction=False)
            test_name = "chi-square"
        test_status = "tested"
        included_in_bh = True

        reference_level, effect_level = _levels[0], _levels[1]
        _is_canonical_01 = False
        try:
            _is_canonical_01 = {float(reference_level), float(effect_level)} == {0.0, 1.0}
        except (TypeError, ValueError):
            _is_canonical_01 = False
        if _is_canonical_01:
            reference_level, effect_level = 0, 1

        # Explicit contrast: OR = odds(target=1|predictor=effect_level) /
        # odds(target=1|predictor=reference_level). Any zero cell among the
        # four counts makes the ordinary sample OR 0/undefined/infinite -- no
        # continuity correction is invented; effect_size is left NaN with an
        # explicit status, and the (still valid) test p-value is retained.
        a_ = int(_tab.loc[effect_level, 1])
        b_ = int(_tab.loc[effect_level, 0])
        c_ = int(_tab.loc[reference_level, 1])
        d_ = int(_tab.loc[reference_level, 0])
        if min(a_, b_, c_, d_) == 0:
            effect = float("nan")
            effect_estimate_status = "zero_cell_unstable_or_undefined"
        else:
            effect = round(float((a_ * d_) / (b_ * c_)), 3)
            effect_estimate_status = "ok"
        effect_size_type = "odds ratio"
        effect_contrast = (
            "predictor1_vs_predictor0 (target1 odds)" if _is_canonical_01
            else f"{effect_level}_vs_{reference_level} (target1 odds)"
        )
    else:
        # The corrected blocker: assumption-aware Rx2 test selection.
        reference_level = effect_level = float("nan")
        effect_estimate_status = "not_applicable"
        effect_contrast = "association_strength (unsigned)"
        _adequate = (
            not _diag["any_expected_lt1"]
            and _diag["pct_expected_cells_lt5"] <= MULTILEVEL_ADEQUACY_MAX_PCT_LT5
        )
        if _adequate:
            stat_, p, _, _ = stats.chi2_contingency(_tab, correction=False)
            test_name = "chi-square"
            test_status = "tested"
            included_in_bh = True
        else:
            _mc = _sparse_multilevel_monte_carlo(_tab)
            if _mc is not None:
                p, stat_ = _mc
                test_name = (
                    f"chi-square (Monte Carlo, seed={MONTE_CARLO_SEED}, "
                    f"n_resamples={MONTE_CARLO_N_RESAMPLES})"
                )
                test_status = "tested_monte_carlo"
                included_in_bh = True
            else:
                stat_, p = float("nan"), float("nan")
                test_name = "none"
                test_status = "descriptive_only_sparse_multilevel"
                included_in_bh = False
        # Cramér's V is always reported, independent of which p-value branch
        # above was taken.
        effect = round(cramers_v(_tab), 3)
        effect_size_type = "Cramér's V"

    if vtype == "binary":
        # Predictor prevalence WITHIN each target group, not "CS risk"/
        # "vaginal rate" (those would be the reverse conditional).
        predictor_prevalence_target1_pct = round(float(g1.mean()) * 100, 1)
        predictor_prevalence_target0_pct = round(float(g0.mean()) * 100, 1)
        extra_info = (
            f"predictor_prevalence_target1_pct={predictor_prevalence_target1_pct}% "
            f"predictor_prevalence_target0_pct={predictor_prevalence_target0_pct}%"
        )
    else:
        predictor_prevalence_target1_pct = float("nan")
        predictor_prevalence_target0_pct = float("nan")
        extra_info = f"levels={list(_levels)}"

    screening_rows.append({
        "variable": col, "type": vtype,
        "N": int(len(_pair)), "N_missing": int(df_analysis[col].isna().sum()),
        "target0_n": int(len(g0)), "target1_n": int(len(g1)), "n_levels": n_levels,
        "test_status": test_status, "included_in_bh": included_in_bh,
        "test": test_name,
        "statistic": (round(float(stat_), 3) if pd.notna(stat_) else float("nan")),
        "p_value": float(p) if pd.notna(p) else float("nan"),
        "effect_size": effect, "effect_size_type": effect_size_type,
        "effect_contrast": effect_contrast,
        "effect_level": effect_level, "reference_level": reference_level,
        "effect_estimate_status": effect_estimate_status,
        "target0_median": float("nan"), "target1_median": float("nan"),
        "table_shape": _diag["table_shape"], "min_expected_count": _diag["min_expected_count"],
        "n_expected_cells_lt5": _diag["n_expected_cells_lt5"],
        "pct_expected_cells_lt5": _diag["pct_expected_cells_lt5"],
        "any_expected_lt1": _diag["any_expected_lt1"],
        "predictor_prevalence_target1_pct": predictor_prevalence_target1_pct,
        "predictor_prevalence_target0_pct": predictor_prevalence_target0_pct,
        "extra_info": extra_info,
    })

screening_df = pd.DataFrame(screening_rows)

# Fail loud: every SCREEN_VARS member must receive EXACTLY one screening row.
_row_counts = screening_df["variable"].value_counts()
_missing_rows = [v for v in SCREEN_VARS if v not in _row_counts.index]
_multi_rows = sorted(v for v, n in _row_counts.items() if n > 1)
if _missing_rows:
    raise AssertionError(f"SCREEN_VARS member(s) received zero screening rows: {_missing_rows}")
if _multi_rows:
    raise AssertionError(f"SCREEN_VARS member(s) received more than one screening row: {_multi_rows}")

screening_df["q_value_bh"] = benjamini_hochberg(screening_df["p_value"]).values
screening_df["fdr_sig"] = screening_df["q_value_bh"] < 0.05

# Fail loud: included_in_bh must exactly match "has a finite p_value" -- the
# two are defined together above; this is a construction sanity check, not a
# second independent rule.
_finite_p_mask = screening_df["p_value"].notna()
_bh_mismatch = screening_df.loc[screening_df["included_in_bh"] != _finite_p_mask, "variable"].tolist()
if _bh_mismatch:
    raise AssertionError(f"included_in_bh disagrees with p_value finiteness for: {_bh_mismatch}")

bh_family_n = int(_finite_p_mask.sum())
screening_df["bh_family_n"] = bh_family_n
if bh_family_n != int(screening_df["included_in_bh"].sum()):
    raise AssertionError("bh_family_n does not match the count of included_in_bh=True rows")

screening_df["clinical_tier"] = screening_df["variable"].map(
    lambda v: CLINICAL_TIER.get(v, "—")
)
screening_df["timing_raw"] = screening_df["variable"].map(
    lambda v: TIMING_MAP.get(v, derived_meta.get(v, {}).get("timing", "unknown"))
)
screening_df["timing"] = screening_df["timing_raw"].map(normalize_timing_label)
screening_df["original_or_derived"] = screening_df["variable"].apply(
    lambda v: "derived" if v in DERIVED_VARS else "original"
)
screening_df = screening_df.sort_values("q_value_bh", ascending=True)

# ── Reconciliation summary ──────────────────────────────────────────────────
_n_tested = int((screening_df["test_status"] == "tested").sum())
_n_tested_mc = int((screening_df["test_status"] == "tested_monte_carlo").sum())
_n_descriptive_only = int((screening_df["test_status"] == "descriptive_only_sparse_multilevel").sum())
_n_skipped_no_groups = int((screening_df["test_status"] == "skipped_no_two_target_groups").sum())
_n_skipped_insufficient = int((screening_df["test_status"] == "skipped_insufficient_data_or_zero_variance").sum())
_n_skipped_absent = int((screening_df["test_status"] == "skipped_variable_absent_from_df_analysis").sum())

print(f"SCREEN_VARS universe: {len(SCREEN_VARS)} variables (one screening record each)")
print(
    f"  inferentially tested: {_n_tested + _n_tested_mc} "
    f"(asymptotic chi-square/Fisher/Mann-Whitney={_n_tested}, sparse-multilevel Monte Carlo={_n_tested_mc})"
)
print(
    f"  descriptive-only / skipped: {len(SCREEN_VARS) - (_n_tested + _n_tested_mc)} "
    f"(sparse multi-level descriptive-only={_n_descriptive_only}, "
    f"no two target groups={_n_skipped_no_groups}, "
    f"insufficient data/zero variance={_n_skipped_insufficient}, "
    f"absent from df_analysis={_n_skipped_absent})"
)
print(f"  BH-FDR family N (bh_family_n): {bh_family_n}")
print(f"  FDR-significant (q < 0.05): {int(screening_df['fdr_sig'].sum())}")
print()

# ── Share-safe presentation-only view ───────────────────────────────────────
# screening_df above keeps exact analytical values throughout -- this view is
# for the printed table only and never feeds back into any computation.
_SS_C11 = bool(SHARE_SAFE_MODE) if "SHARE_SAFE_MODE" in dir() else True


def _suppress_screening_display_row(row):
    return pd.Series({
        "N": share_safe.safe_count(row["N"], enabled=_SS_C11),
        "N_missing": share_safe.safe_count(row["N_missing"], enabled=_SS_C11),
        "target0_n": share_safe.safe_count_with_complement(row["target0_n"], row["N"], enabled=_SS_C11),
        "target1_n": share_safe.safe_count_with_complement(row["target1_n"], row["N"], enabled=_SS_C11),
        "n_expected_cells_lt5": (
            share_safe.safe_count(row["n_expected_cells_lt5"], enabled=_SS_C11)
            if pd.notna(row["n_expected_cells_lt5"]) else row["n_expected_cells_lt5"]
        ),
    })


screening_display_df = screening_df.copy()
_display_overrides = screening_df.apply(_suppress_screening_display_row, axis=1)
for _c in _display_overrides.columns:
    screening_display_df[_c] = _display_overrides[_c]

print(screening_display_df[[
    "variable", "original_or_derived", "type", "N", "N_missing",
    "test", "test_status", "p_value", "q_value_bh", "included_in_bh", "fdr_sig",
    "effect_size", "effect_size_type", "effect_contrast",
    "clinical_tier", "timing",
]].to_string(index=False))
print()
print("=" * 70)
print("REMINDER: q-values are exploratory signals only.")
print("Final feature selection must occur inside the modeling pipeline.")
print("=" * 70)
""")


# ── Section C12 ────────────────────────────────────────────────────────────────
SC12_HEADER = md("eda-c-s12-header", """
## Section C12 — Candidate Feature Review Table

> **This table is a candidate review document only.**
> **Final feature selection must occur inside the modeling pipeline / cross-validation — not here.**

One row per variable (original approved + derived). The `candidate_role_for_modeling_review`
column summarises the screening evidence and known constraints using a **neutral
review taxonomy** (corrected 2026-09-01 -- see below):

| Role | Meaning |
|------|---------|
| `association_signal_review` | FDR-significant (± high clinical tier); an association signal **worth investigating in the modeling pipeline** -- never automatic inclusion |
| `clinical_priority_review` | High clinical-priority tier, no FDR signal; a clinically-motivated candidate for discussion |
| `horizon_specific_review` | Secondary/intrapartum-horizon classification, or ambiguous pre-admission timing; routing information, not a quality judgment |
| `general_review` | Redundant with another approved variable, or no particular signal either way; include only with clinical justification |
| `soft_risk_review` | Separation, sparse target cells, or high target-association -- **target-informed, full-dataset risk flags that must never drive pre-CV inclusion or exclusion**; the variable stays in the eligible pool if it clears the (target-independent) hard-exclusion rules |
| `hard_exclusion_review` | A genuinely **target-independent** hard issue only -- a deterministic derived-output contract violation/impossible value, or explicit pending timing confirmation; matches `eligibility_status="hard_excluded"` |

**Methodological correction (2026-09-01):** the previous taxonomy
(`include_candidate` / `review_candidate` / `secondary_candidate` /
`exclude_candidate`) labelled separation, high target-association
(`leakage_flag`), and sparse cells as `exclude_candidate` -- contradicting
C12b's own architecture, which treats all three as **soft, target-informed,
descriptive warnings that never remove a variable from the pool before CV**.
No other code in this repository reads the old role field name or its
specific values (confirmed by a repo-wide trace); the field name
`candidate_role_for_modeling_review` is unchanged for continuity, but every
value now uses the neutral taxonomy above. `predictor_classification` remains
the sole authoritative horizon field; `eligibility_status` /
`hard_exclusion_reason` (C12b) remain the sole authoritative eligibility
fields. FDR/nominal association **never** implies automatic inclusion;
separation/sparsity/high target-association **never** imply exclusion.

**Roles are screening recommendations only.** A variable must not be mechanically
included or excluded from the modeling pipeline based on this table alone.
""")

SC12_CANDIDATE_TABLE = code("eda-c-s12-candidate-table", """
print("=" * 70)
print("CANDIDATE FEATURE REVIEW TABLE")
print("EXPLORATORY ONLY — not feature selection.")
print("Final feature selection must occur inside the modeling pipeline / cross-validation.")
print("=" * 70)
print()

# Domain assignment for derived features (2026-09-01 C12 correction, Part B):
# the local DERIVED_DOMAIN_MAP registry was retired -- it was a second,
# incomplete domain registry that had drifted stale (missing
# derived_hypertension_pih_pet_spectrum / derived_diabetes_type_grouped) and
# was largely dead code anyway: derived_endo_surgery_adhesion_status is no
# longer is_derived (relocated to Data Cleaning B, see the C9 note below --
# its domain already comes from DOMAIN_MAP via the B feature dictionary, not
# this map), so only C9-materialized features could ever reach the
# DERIVED_DOMAIN_MAP.get(...) fallback. C9 already stores each materialized
# derived feature's authoritative domain directly in derived_meta[dv]["domain"]
# (set at creation time in eda_c_part3_feature_engineering.py) -- use that
# single source of truth instead of a second hand-maintained copy, and fail
# loud rather than silently exporting "unknown" for a materialized modeling
# derived predictor with no registered domain.

# B-created (non-C9-derived) column lineage, read from Data Cleaning B's own
# feature dictionary -- used below to populate source_columns for columns
# like endometrioma_presence_laterality that are neither raw classification-
# CSV rows nor C9 feature-engineered (is_derived=False for both).
B_CREATED_SOURCE_COLUMNS = (
    dict(zip(B_FEATURE_DICT["new_column"], B_FEATURE_DICT["source_column"]))
    if B_FEATURE_DICT is not None and "new_column" in B_FEATURE_DICT.columns
    else {}
)

# Early load of compute_structural_applicability_aware_missing_pct (Part B3,
# 2026-08-27 correction) -- needed inside the main screening loop below, ahead
# of the later eda_c_screening_helpers import used for data_type/variance
# (Section C12b). structural_missingness_registry itself is already a global
# from eda_c_part1_setup_gate.py (same shared notebook namespace).
_early_helpers_path = _root / "analysis" / "eda" / "notebook_build" / "eda_c" / "eda_c_screening_helpers.py"
_early_helpers_spec = importlib.util.spec_from_file_location("_eda_c_screening_helpers_early", _early_helpers_path)
_early_helpers = importlib.util.module_from_spec(_early_helpers_spec)
_early_helpers_spec.loader.exec_module(_early_helpers)
compute_structural_applicability_aware_missing_pct = _early_helpers.compute_structural_applicability_aware_missing_pct

candidate_rows = []

for col in SCREEN_VARS:
    if col not in df_analysis.columns:
        continue

    is_derived = col in DERIVED_VARS
    src_cols_str = derived_meta.get(col, {}).get("source_columns", col) if is_derived else col
    vtype = infer_var_type(df_analysis[col])
    # Domain (2026-09-01 correction, Part B): derived_meta is the single
    # source of truth for a materialized derived feature's domain -- fail
    # loud rather than silently falling back to "unknown" for one.
    if is_derived:
        if "domain" not in derived_meta.get(col, {}):
            raise AssertionError(
                f"{col}: materialized derived feature has no 'domain' entry in "
                "derived_meta -- register one in eda_c_part3_feature_engineering.py "
                "rather than silently exporting an unknown domain."
            )
        domain = derived_meta[col]["domain"]
    else:
        domain = DOMAIN_MAP.get(col, "unknown")
    timing_raw = (derived_meta.get(col, {}).get("timing", "unknown")
                  if is_derived else TIMING_MAP.get(col, "unknown"))
    timing = normalize_timing_label(timing_raw)
    # Whole-cohort naive (RAW) missingness -- always computed, always exported.
    # NOT necessarily the PRIMARY missingness value used for modeling-facing
    # metadata/scoring (see the three-tier contract immediately below).
    miss_pct = round(df_analysis[col].isna().mean() * 100, 1)
    clinical_tier = CLINICAL_TIER.get(col, "—") if not is_derived else "derived"

    # ── Three-tier structural-missingness PRIMARY contract (2026-09-01
    # correction, Part C -- restores the exact distinction C5 already makes,
    # which this file had collapsed into one applicability-aware figure for
    # BOTH tiers):
    #   1. ORDINARY variable            -> PRIMARY = RAW whole-column NaN rate.
    #   2. CONFIRMED STRUCTURAL variable -> PRIMARY = genuine missingness
    #      WITHIN the applicable subgroup (structural non-applicability is
    #      NOT missingness).
    #   3. APPLICABILITY-LINKED variable (no preprocessing mask) -> PRIMARY =
    #      RAW whole-column NaN rate. The applicability relationship is known
    #      and its Data Cleaning B treatment is resolved, but no code-enforced
    #      structural-missingness gate exists, so the applicability-aware
    #      figure is exported ONLY as a separate, explicitly-labelled
    #      SENSITIVITY diagnostic -- it never replaces the primary view.
    # Uses the same STRUCTURAL_NAN_COLS (confirmed tier only) /
    # APPLICABILITY_LINKED_COLS (applicability-linked tier) sets and
    # structural_missingness_registry.applicability_gate_for() as C5 -- never
    # inferred from the raw missingness figure itself.
    _applicability_linked_set = set(APPLICABILITY_LINKED_COLS) if "APPLICABILITY_LINKED_COLS" in dir() else set()
    _is_confirmed_structural = col in STRUCTURAL_NAN_COLS
    _is_applicability_linked = col in _applicability_linked_set
    structural_applicability_status = (
        "confirmed_structural" if _is_confirmed_structural
        else ("applicability_linked_no_preprocessing_mask" if _is_applicability_linked else "none")
    )
    _structural_applicability = None
    if _is_confirmed_structural or _is_applicability_linked:
        _applicability_gate = structural_missingness_registry.applicability_gate_for(col)
        _structural_applicability = compute_structural_applicability_aware_missing_pct(
            col, df_analysis, _applicability_gate
        )
    if _is_confirmed_structural and _structural_applicability is not None:
        primary_missing_pct_for_modeling = _structural_applicability["genuine_missing_pct"]
    else:
        # Applicability-linked AND ordinary variables both use RAW as PRIMARY --
        # without a code-enforced gate the applicability-aware figure is never
        # swapped in as authoritative.
        primary_missing_pct_for_modeling = miss_pct
    applicability_aware_missing_pct_sensitivity = (
        _structural_applicability["genuine_missing_pct"] if _structural_applicability is not None else None
    )

    # Screening stats (2026-09-01 correction, Part G: propagate the corrected
    # C11 inferential-contract metadata alongside the preserved p/q/effect
    # fields). Every SCREEN_VARS member gets exactly one screening_df row
    # (enforced fail-loud in C11 itself), so the `else` branch below is a
    # defensive fallback, not an expected live path.
    _s_row = screening_df.loc[screening_df["variable"] == col]
    if len(_s_row):
        _sr = _s_row.iloc[0]
        p_val = _sr["p_value"]
        q_val = _sr["q_value_bh"]
        fdr_sig = bool(_sr["fdr_sig"])
        effect_size = _sr["effect_size"]
        effect_size_type = _sr["effect_size_type"]
        c11_test_status = _sr["test_status"]
        c11_test = _sr["test"]
        c11_included_in_bh = bool(_sr["included_in_bh"])
        c11_bh_family_n = _sr["bh_family_n"]
        c11_effect_contrast = _sr["effect_contrast"]
        c11_effect_estimate_status = _sr["effect_estimate_status"]
        c11_target0_n = _sr["target0_n"]
        c11_target1_n = _sr["target1_n"]
    else:
        p_val = q_val = effect_size = float("nan")
        fdr_sig = False
        effect_size_type = "—"
        c11_test_status = "not_screened"
        c11_test = "not_screened"
        c11_included_in_bh = False
        c11_bh_family_n = bh_family_n if "bh_family_n" in dir() else None
        c11_effect_contrast = "—"
        c11_effect_estimate_status = "not_applicable"
        c11_target0_n = None
        c11_target1_n = None

    # Derived feature flags from C10 (high target association, impossible values, sparsity/separation)
    _v_row = derived_validation_df.loc[derived_validation_df["derived_feature"] == col] if is_derived and len(derived_validation_df) else pd.DataFrame()
    high_target_association_review = bool(_v_row.iloc[0]["high_target_association_review"]) if len(_v_row) else False
    impossible_flag = bool(_v_row.iloc[0]["impossible_flag"]) if len(_v_row) else False

    # Sparsity / separation — from C6 (original ANALYSIS_VARS) or C10 (DERIVED_VARS,
    # which C6's sparsity_df never covers).
    if is_derived:
        separation = bool(_v_row.iloc[0]["separation_flag"]) if len(_v_row) else False
        sparse = bool(_v_row.iloc[0]["too_sparse_flag"]) if len(_v_row) else False
        min_cell_count = int(_v_row.iloc[0]["min_cell_count"]) if len(_v_row) else -1
    else:
        _sp_row = sparsity_df.loc[sparsity_df["variable"] == col] if col in sparsity_df["variable"].values else pd.DataFrame()
        separation = bool(_sp_row.iloc[0]["separation_risk"]) if len(_sp_row) else False
        sparse = bool(_sp_row.iloc[0]["too_sparse"]) if len(_sp_row) else False
        min_cell_count = int(_sp_row.iloc[0]["min_cell_count"]) if len(_sp_row) else -1
    event_info = (f"min_cell={min_cell_count}" if vtype != "numeric" and min_cell_count >= 0
                  else (f"med={round(float(df_analysis[col].dropna().median()), 1)}" if vtype == "numeric" else "—"))

    # Redundancy flag
    _is_in_redundant_pair = (
        len(redundancy_pairs_df) > 0 and col in (
            list(redundancy_pairs_df.get("var1", [])) + list(redundancy_pairs_df.get("var2", []))
        )
    )

    # Secondary near-delivery / intrapartum-confirmed classification. Both
    # pass through the same generic QC/screening logic below as every other
    # candidate (separation/leakage/impossible-value checks still apply
    # first); their classification only routes them to a review-oriented
    # role afterward, rather than either hard-excluding them (pre-Decision-65
    # behavior for intrapartum) or silently treating them as indistinguishable
    # from predictor_allowed. predictor_classification (added below) is the
    # authoritative field for downstream horizon filtering -- this role/reason
    # is descriptive only.
    is_secondary = col in SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS
    is_intrapartum_confirmed = col in INTRAPARTUM_PREDICTOR_EXCLUDE_COLS

    # Primary model timing check
    primary_eligible = derived_meta.get(col, {}).get("primary_model_eligible", None) if is_derived else None
    if primary_eligible is None:
        primary_eligible = "yes" if timing in ("pre_pregnancy", "pregnancy") else "review"

    # Determine candidate role (2026-09-01 correction, Part A -- neutral
    # review taxonomy that cannot be mistaken for target-informed pre-CV
    # feature selection; see SC12_HEADER for the full mapping/rationale).
    # `candidate_role_for_modeling_review` is DESCRIPTIVE ONLY: it never
    # implies inclusion (association_signal_review) or exclusion
    # (soft_risk_review) by itself -- eligibility_status/hard_exclusion_reason
    # from C12b remain the sole authoritative eligibility fields, and
    # predictor_classification remains the sole authoritative horizon field.
    # Only a genuinely target-independent hard issue (impossible_flag here;
    # pending-timing-confirmation in the separate block below) may receive
    # the exclusion-oriented `hard_exclusion_review` label -- separation,
    # sparse cells, and high target association are all target-informed,
    # full-dataset statistics and must never be framed as exclusion
    # recommendations before CV.
    reasons = []
    if impossible_flag:
        role = "hard_exclusion_review"
        reasons.append("impossible values detected (deterministic derived-output contract violation)")
    elif separation:
        role = "soft_risk_review"
        reasons.append("separation in 2x2 table (target-informed modeling-stage risk, not an exclusion)")
    elif high_target_association_review:
        role = "soft_risk_review"
        reasons.append(
            f"|association with target| > {DERIVED_TARGET_ASSOC_REVIEW_THRESHOLD} (high_target_association_review "
            "-- lineage/semantic review warranted, not proof of leakage by itself)"
        )
    elif is_secondary:
        role = "horizon_specific_review"
        reasons.append("secondary_near_delivery_predictor classification")
    elif is_intrapartum_confirmed:
        role = "horizon_specific_review"
        reasons.append(
            "intrapartum_predictor_exclude_from_prelabor_model classification "
            "(confirmed intrapartum timing; part of the unified master pool "
            "per Decision 65, eligible for the intrapartum modeling horizon only)"
        )
    elif primary_eligible == "no":
        role = "horizon_specific_review"
        reasons.append("not primary-model eligible per feature plan")
    elif sparse:
        role = "soft_risk_review"
        reasons.append("too sparse (events < 5) -- target-informed modeling-stage risk, not an exclusion")
    elif _is_in_redundant_pair:
        role = "general_review"
        reasons.append("high redundancy with another approved variable")
    elif fdr_sig and clinical_tier in ("1", "2", 1, 2, "tier_1", "tier_2"):
        role = "association_signal_review"
        reasons.append("FDR-significant + high clinical tier -- a signal worth investigating, not automatic inclusion")
    elif fdr_sig:
        role = "association_signal_review"
        reasons.append("FDR-significant -- a signal worth investigating, not automatic inclusion")
    elif clinical_tier in ("1", 1, "tier_1"):
        role = "clinical_priority_review"
        reasons.append("high clinical tier but not FDR-significant")
    elif primary_eligible == "review" and not is_derived:
        role = "horizon_specific_review"
        reasons.append("timing or eligibility requires clinical review")
    else:
        role = "general_review"
        reasons.append("no FDR signal; include only with clinical justification")

    # predictor_classification: the authoritative original classification,
    # preserved as metadata through screening so the modeling boundary can
    # later derive horizon-specific eligibility without re-deriving it here
    # (Decision 65 / multi-horizon plan Batch 2). Original (non-derived)
    # variables get it directly from the classification CSV-derived lists;
    # derived (C9 feature-engineered) variables have no raw classification-CSV
    # row of their own, so their approved classification is read from
    # derived_meta (set at creation time in eda_c_part3_feature_engineering.py
    # -- all three currently implemented derived predictors are approved
    # predictor_allowed).
    if col in PREDICTOR_ALLOWED_COLS:
        predictor_classification = "predictor_allowed"
    elif col in SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS:
        predictor_classification = "secondary_near_delivery_predictor"
    elif col in INTRAPARTUM_PREDICTOR_EXCLUDE_COLS:
        predictor_classification = "intrapartum_predictor_exclude_from_prelabor_model"
    elif is_derived:
        predictor_classification = derived_meta.get(col, {}).get("analytical_role", "predictor_allowed")
    elif col in B_CREATED_PREDICTOR_CLASSIFICATION:
        # B_CREATED_PREDICTOR_CLASSIFICATION is now a live projection of Data
        # Cleaning B's exported feature dictionary (2026-08-16), not a local
        # override -- see eda_c_part1_setup_gate.py. A column with an UNSET
        # value here should already have been excluded from
        # B_CREATED_ANALYSIS_VARS / SCREEN_VARS upstream; this branch is
        # normally only reached for columns with a real, resolved value.
        predictor_classification = B_CREATED_PREDICTOR_CLASSIFICATION[col]
    else:
        predictor_classification = "unknown"

    candidate_rows.append({
        "variable": col,
        "predictor_classification": predictor_classification,
        "original_or_derived": "derived" if is_derived else "original",
        "source_columns": (
            src_cols_str if is_derived
            else B_CREATED_SOURCE_COLUMNS.get(col, "—")
        ),
        "domain": domain,
        "timing": timing,
        "timing_raw": timing_raw,
        # Missingness metadata (2026-09-01 correction, Part C/C1): raw_missing_pct
        # and primary_missing_pct_for_modeling are the new explicit fields;
        # missing_% is kept as the raw value (compat, unchanged meaning);
        # effective_missing_pct_for_exclusion is kept ONLY as a documented
        # compatibility alias of primary_missing_pct_for_modeling (its old name
        # is stale -- the generic missingness hard-exclusion rule no longer
        # exists) -- it never carries a applicability-linked sensitivity value.
        "missing_%": miss_pct,
        "raw_missing_pct": miss_pct,
        "primary_missing_pct_for_modeling": primary_missing_pct_for_modeling,
        "effective_missing_pct_for_exclusion": primary_missing_pct_for_modeling,
        "structural_applicability_status": structural_applicability_status,
        "applicability_aware_missing_pct_sensitivity": applicability_aware_missing_pct_sensitivity,
        "structural_applicability_applicable_n": (
            _structural_applicability["applicable_n"] if _structural_applicability is not None else None
        ),
        "structural_applicability_genuine_missing_applicable_n": (
            _structural_applicability["genuine_missing_applicable_n"] if _structural_applicability is not None else None
        ),
        "model_entry_mode": B_CREATED_MODEL_ENTRY_MODE.get(col, "direct"),
        "redundant_with": (
            B_CREATED_REDUNDANT_WITH.get(col)
            if B_CREATED_REDUNDANT_WITH.get(col) not in (None, "UNSET") else None
        ),
        "event_count_info": event_info,
        "min_cell_count": min_cell_count,
        "p_value": round(p_val, 4) if pd.notna(p_val) else float("nan"),
        "fdr_q_value": round(q_val, 4) if pd.notna(q_val) else float("nan"),
        "effect_size": round(effect_size, 3) if pd.notna(effect_size) else float("nan"),
        "effect_size_type": effect_size_type,
        # C11 audit metadata (2026-09-01 correction, Part G) -- additive,
        # never used to change hard eligibility.
        "test_status": c11_test_status,
        "test": c11_test,
        "included_in_bh": c11_included_in_bh,
        "bh_family_n": c11_bh_family_n,
        "effect_contrast": c11_effect_contrast,
        "effect_estimate_status": c11_effect_estimate_status,
        "target0_n": c11_target0_n,
        "target1_n": c11_target1_n,
        "redundancy_flag": _is_in_redundant_pair,
        "high_target_association_review": high_target_association_review,
        "impossible_flag": impossible_flag,
        "separation_flag": separation,
        "too_sparse_flag": sparse,
        "clinical_priority_tier": clinical_tier,
        "primary_model_eligible": primary_eligible,
        "candidate_role_for_modeling_review": role,
        "reason": "; ".join(reasons),
    })

candidate_df = pd.DataFrame(candidate_rows).sort_values(
    ["candidate_role_for_modeling_review", "fdr_q_value"],
    ascending=[True, True],
)

PENDING_TIMING_CONFIRMATION_REASON = (
    "pending_timing_confirmation_before_intrapartum_cs_decision"
)
_pending_timing_rows = []
_already_listed = set(candidate_df["variable"]) if len(candidate_df) else set()
for _pending_col in PENDING_TIMING_CONFIRMATION_COLS:
    if _pending_col in _already_listed:
        continue
    _pending_timing_rows.append({
        "variable": _pending_col,
        "predictor_classification": "intrapartum_candidate_pending_timing_confirmation",
        "original_or_derived": "original",
        # "—" matches the convention used for every other original (non-derived)
        # variable's source_columns value elsewhere in this file (see the main
        # screening loop above). Previously read "classification_csv", a leftover
        # placeholder with no real source-column meaning for these original,
        # not-statistically-screened rows (2026-07-26 classification reconciliation;
        # 2026-07-28 split into this residual plus the
        # intrapartum_predictor_exclude_from_prelabor_model block below -- both
        # groups' membership has changed since via later decisions; see the live
        # counts printed elsewhere in this notebook, not hardcoded here).
        "source_columns": "—",
        "domain": DOMAIN_MAP.get(_pending_col, "pending_timing_confirmation"),
        "timing": "pending_timing_confirmation",
        "timing_raw": "pending_timing_confirmation",
        "missing_%": float("nan"),
        "raw_missing_pct": float("nan"),
        "primary_missing_pct_for_modeling": float("nan"),
        "effective_missing_pct_for_exclusion": float("nan"),
        "structural_applicability_status": "not_screened",
        "applicability_aware_missing_pct_sensitivity": None,
        "structural_applicability_applicable_n": None,
        "structural_applicability_genuine_missing_applicable_n": None,
        "event_count_info": "not screened",
        "min_cell_count": -1,
        "p_value": float("nan"),
        "fdr_q_value": float("nan"),
        "effect_size": float("nan"),
        "effect_size_type": "not_screened",
        # C11 metadata (Part G): pending-timing rows were never screened --
        # explicit "not_screened" / included_in_bh=False, not ambiguous NaN.
        "test_status": "not_screened",
        "test": "not_screened",
        "included_in_bh": False,
        "bh_family_n": bh_family_n if "bh_family_n" in dir() else None,
        "effect_contrast": "—",
        "effect_estimate_status": "not_applicable",
        "target0_n": None,
        "target1_n": None,
        "redundancy_flag": False,
        "high_target_association_review": False,
        "impossible_flag": False,
        "separation_flag": False,
        "too_sparse_flag": False,
        "clinical_priority_tier": "pending",
        "primary_model_eligible": "no",
        # A true target-independent hard issue (explicit pending timing
        # confirmation, Part A3) -- the one case where the exclusion-oriented
        # role is correct, not a contradiction of the soft-warning/hard-
        # exclusion separation the rest of this file now enforces.
        "candidate_role_for_modeling_review": "hard_exclusion_review",
        "reason": (
            "intrapartum_candidate_pending_timing_confirmation classification; "
            "excluded pending clinical confirmation that the value was available "
            "before the intrapartum cesarean decision"
        ),
    })
if _pending_timing_rows:
    candidate_df = pd.concat([candidate_df, pd.DataFrame(_pending_timing_rows)], ignore_index=True)
    print(f"Added {len(_pending_timing_rows)} pending timing-confirmation exclusion rows "
          "from the classification CSV.")

# NOTE: the category-wide "confirmed-intrapartum exclusion" placeholder-row
# block that used to live here was removed 2026-08-13 (Decision 65 / multi-
# horizon plan Batch 2). intrapartum_predictor_exclude_from_prelabor_model
# variables are now part of ANALYSIS_VARS/SCREEN_VARS (see
# eda_c_part1_setup_gate.py) and are screened through the normal loop above
# like every other candidate -- see the is_intrapartum_confirmed branch,
# which routes them to candidate_role_for_modeling_review="horizon_specific_review"
# (renamed 2026-09-01 from "secondary_candidate"; unless a hard QC rule fires
# first) instead of an unconditional exclusion-oriented placeholder row.
# Their classification is preserved via predictor_classification for the
# modeling-boundary horizon split.

_role_counts = candidate_df["candidate_role_for_modeling_review"].value_counts()
print(f"Candidate table: {len(candidate_df)} variables")
for _role, _n in _role_counts.items():
    print(f"  {_role}: {_n}")
print()
print(candidate_df.to_string(index=False))
print()
print("=" * 70)
print("REMINDER: this table is a candidate review document only.")
print("Final feature selection must occur inside the modeling pipeline / cross-validation.")
print("=" * 70)
""")


# ── Section C12b ────────────────────────────────────────────────────────────────
SC12B_HEADER = md("eda-c-s12b-header", """
## Section C12b — Eligibility Filtering and Candidate Pool Construction

> **EDA C performs eligibility filtering only. It does not choose the final modeling
> variables.** Every variable that clears every hard-exclusion rule below is exported
> in the candidate pool — there is no cap, no greedy pick, no compact "primary list."
> Final variable/model selection happens later, in EDA D, under cross-validation.

Applies a fixed set of **hard exclusion** rules to every screened variable (original
approved + derived). A variable failing **any** hard rule is dropped from the
candidate pool entirely. Variables that clear all hard rules are exported, along
with **soft warning** flags that disclose remaining concerns without removing the
variable from the pool — those concerns (rare prevalence, timing uncertainty,
redundancy with another variable) are exactly the kind of thing regularized/stepwise
methods in EDA D are equipped to resolve statistically, not something EDA C should
pre-judge by dropping the variable.

### Hard exclusion rules (any one of these removes a variable from the pool)
**RECLASSIFIED 2026-08-19 (target-informed pre-CV screening consistency
correction, no new numbered clinical Decision):** separation, boundary-sparse
instability, and too-sparse are no longer hard-exclusion rules — see the
"Soft warnings" section below.
**RECLASSIFIED again 2026-08-20 (same correction, closing the one remaining
gap):** `leakage_flag` (target-correlation smoke test) is *also* no longer a
hard-exclusion rule — see "Soft warnings" below. A full-dataset correlation
with the target, however large, is a WARNING that lineage/semantic review is
warranted, not proof of leakage by itself; it must not perform automatic
pre-CV feature selection. All remaining hard-exclusion rules are fully
target-independent (never read `target_intrapartum_cs` at all), so predictor
eligibility continues to be decided before any CV split without using any
full-dataset target-informed statistic as an automatic pre-CV filter.
Semantic/clinical leakage — post-outcome, post-delivery, or intrapartum-only
variables identified by clinical meaning, timing, or explicit classification
(`leakage_exclude`, `intrapartum_or_post_delivery_exclude`, etc.) — is
enforced upstream in C2/C3 (see the Note below) and by the
`predictor_classification` gate, and is completely unaffected by this
correction: those exclusions were never based on a target-correlation
statistic and remain exactly as strict as before.
1. **Invalid / impossible values** — `impossible_flag` (C10).
2. **Zero variance** — fewer than 2 distinct non-missing values in the cohort (no
   missing values, exactly one observed unique value). Enforced during pool
   construction.
3. **~~High missingness above a threshold~~ — REMOVED in the 2026-08-31
   methodological rebuild.** In a predictive CV project a high-missingness
   predictor is handled by fold-safe imputation / an explicit not-documented
   category inside the training fold, not by pre-CV deletion. Missingness is now
   (a) diagnostic metadata -- `raw_missing_pct` (always whole-cohort),
   `primary_missing_pct_for_modeling` (the modeling-facing PRIMARY value; see
   the three-tier contract below), `structural_applicability_status`,
   `applicability_aware_missing_pct_sensitivity`, and the structural-applicability
   `_n` fields (`effective_missing_pct_for_exclusion` is retained ONLY as a
   documented compatibility alias of `primary_missing_pct_for_modeling` --
   its old name is stale now that no generic missingness rule exists to be
   "excluded" from; it never carries a applicability-linked sensitivity value) --
   (b) a SOFT warning (`high_missingness_diagnostic`) above the 40%
   `HIGH_MISSINGNESS_DIAGNOSTIC_THRESHOLD` (evaluated against the PRIMARY
   value), and (c) a machine-readable downstream preprocessing requirement
   (C13). The ad-hoc `HIGH_MISSINGNESS_EXCLUDE_OVERRIDE = {"BMI_after",
   "weight_in_pregnancy"}` escape hatch existed only to circumvent the generic
   rule and is retired (empty set).

   **Three-tier structural-missingness PRIMARY contract (2026-09-01
   correction — restores the exact distinction C5 already makes, which this
   section had collapsed into one applicability-aware figure for both
   structural tiers):**
   1. **Ordinary** variable → PRIMARY = RAW whole-column NaN rate.
   2. **Confirmed structural** variable (`STRUCTURAL_NAN_COLS`, a documented
      code-enforced subgroup gate) → PRIMARY = genuine missingness **within**
      the applicable subgroup; structural non-applicability outside it is not
      missingness.
   3. **Applicability-linked (no preprocessing mask)** variable
      (`APPLICABILITY_LINKED_COLS`) → the applicability relationship is known
      and its Data Cleaning B treatment is resolved, but there is **no**
      code-enforced structural-missingness gate, so PRIMARY = RAW whole-column
      NaN rate, exactly like an ordinary variable. The applicability-aware
      figure is exported ONLY as a separate, explicitly-labelled
      `applicability_aware_missing_pct_sensitivity` diagnostic and **never**
      silently replaces the primary value. Nothing about this tier is pending a
      clinical or methodological decision.
      `gestational_age_at_PPROM_days` is the live example: raw ≈96.3%
      is PRIMARY; ≈5.9% (genuine-missing within the PPROM==1 subgroup) is
      sensitivity-only.
4. **Hard clinical unresolved / pending decision** — corrected 2026-09-01
   (Part E): the legacy `primary_model_eligible` field (C8 explicitly
   documents it as **legacy/compatibility only**) is no longer read here at
   all. A materialized derived predictor is hard-excluded on this basis only
   when its authoritative `derived_meta[dv]["analytical_role"]` is an
   explicit unresolved-state value (`"review"` / `"unresolved"`) rather than
   an approved role (`"predictor_allowed"`, etc.) -- and a materialized
   derived feature with NO registered `analytical_role` at all fails loud
   rather than being silently treated as resolved or unresolved. A
   conditionally-unresolved feature (e.g. `derived_placental_dysfunction_proxy`
   while its `any_PET_cat` source remains UNSET, Decision 71) is simply never
   materialized in the first place, so it never reaches `DERIVED_VARS`/
   `SCREEN_VARS`/the candidate pool at all -- there is nothing for this rule
   to exclude in that case.
5. **Sanity-check-only derived feature** — `derived_nulliparity_with_prior_cs`
   (`analytical_role="sanity_check_only"` in its C8 plan entry; constructed
   purely to detect data contradictions, never a modeling candidate). This
   rule is **structurally inert, not merely inactive**: the feature is
   explicitly excluded from `SCREEN_VARS` before C12 even builds
   `candidate_df` (see C11's `SCREEN_VARS` construction), so it never becomes
   a `candidate_df` row for this rule to evaluate in the first place -- it is
   NOT an active candidate-pool exclusion mechanism today, only defense-in-depth
   against a future accidental change that adds it to `SCREEN_VARS`.
6. **Pending timing confirmation (original variable)** — an original variable
   classified `intrapartum_candidate_pending_timing_confirmation`
   (`pending_timing_confirmation_before_intrapartum_cs_decision`); distinct from
   rule 4, which covers only a *derived* feature's unresolved `analytical_role`
   state, not an original variable awaiting clinical timing confirmation.

Note: **hard timing exclusion** (post-event / intrapartum / post-delivery / neonatal
variables) is already enforced upstream in C2/C3 — those columns never reach
`ANALYSIS_VARS`/`SCREEN_VARS` in the first place, so no additional rule is needed here.

### Soft warnings (disclosure only — never remove a variable from the pool)
- **Rare feature** — cohort-wide prevalence < 3% or fewer than 15 total positive
  cases. Was always disclosure-only; effect estimates may be unstable but the
  variable is not excluded.
- **Timing uncertain** — timing normalizes to `timing_unknown` (renamed 2026-08-18
  from `unknown_but_likely_pre_delivery`; the old name asserted a pre-delivery
  presumption for genuinely unresolved timing, which was not always true — see the
  `normalize_timing_label` correction). Timing uncertainty alone was never
  sufficient to exclude a variable and still isn't; the only behavior change from
  the rename is that genuinely unknown timing no longer earns an implicit
  "presumed pre-delivery" bonus in `priority_score`.
- **Redundancy-demoted** — a member of a redundancy family that has a **fixed,
  target-independent representative** (e.g. `parity_history` → `nulliparity`),
  and is not that representative. It **remains in the pool**, disclosed via
  `redundancy_group`/`redundancy_demoted`.
- **Redundancy-unresolved** (2026-08-31 rebuild) — a member of a redundancy
  family with **no** fixed representative (`representative=None`). EDA C no
  longer picks a winner by `priority_score` (that used target effect size + FDR
  — target-informed pre-CV selection). **Every member stays eligible**, flagged
  `redundancy_unresolved` / `redundancy_unresolved_group`; the co-entry choice
  is deferred to EDA D under CV.
- **Weak univariate signal** (`weak_univariate_signal`; renamed 2026-09-01 from the
  misleading `below_quality_bar`) — `clinical_priority_tier < 1 AND p_value >= 0.05
  AND fdr_q_value >= 0.05 AND nominal p >= 0.05`. **A weak univariate association is
  NOT low data quality** and does **not** imply exclusion: interactions and
  multivariable effects may still make the predictor useful. Disclosure only; never
  affects eligibility.
- **Separation risk** (`separation_risk`) / **Sparse-event risk** (`sparse_event_risk`)
  / **Boundary-sparse instability risk** (`boundary_sparse_instability_risk`) —
  **added 2026-08-19**, moved here from the hard-exclusion rules above. Empty cell in
  the 2×N target crosstab (separation), fewest target-group cell count < 5 (too
  sparse), or exactly at that boundary with a large odds ratio (boundary-sparse
  instability) are all computed from a full-dataset target crosstabulation —
  using them to remove a variable from the candidate pool before any CV split is
  target-informed pre-CV feature selection, which this project's methodology
  prohibits (predictor eligibility must be target-independent; sparse-event/
  separation instability is a modeling-stage estimation concern — regularized/
  penalized estimation, fold-specific diagnostics — not a pre-model exclusion
  reason, consistent with Decision 74/77/78's own "deferred to Modeling D"
  language, now made architecturally consistent rather than merely asserted in
  prose). The variable **remains in the pool**; `min_cell_count`/`separation_flag`/
  `too_sparse_flag` are still fully computed and exported for descriptive/audit
  purposes and for Modeling D's own sparse-event-aware handling.
- **High target association — review** (`high_target_association_review`; renamed
  2026-09-01 from the misleading `target_correlation_leakage_risk`, and its
  legacy `leakage_flag` column alias fully retired the same day) —
  **added 2026-08-20**, moved here from the hard-exclusion rules above.
  `high_target_association_review` (`|correlation with target| >
  DERIVED_TARGET_ASSOC_REVIEW_THRESHOLD`, derived features only, C10). **High
  association with the target is NOT by itself evidence of leakage** — actual
  leakage is determined from timing / provenance / post-outcome semantics /
  classification (enforced upstream in C2/C3, never here). This flag is a
  descriptive prompt for manual lineage review of a derived feature's construction;
  it never removes a variable. A strong full-dataset target correlation is useful
  as a signal that lineage/semantic review is warranted (it may indicate a
  post-outcome-proxy construction bug in a derived feature) — but correlation
  strength alone does not prove leakage, and must not itself perform feature
  selection ahead of CV. The variable **remains in the pool**;
  `high_target_association_review`/`|r|_vs_target` are still fully computed and
  exported for descriptive/audit purposes and for manual lineage review. This
  does not affect semantic/clinical leakage exclusion (post-outcome,
  post-delivery, intrapartum-only, or
  explicitly `leakage_exclude`/`intrapartum_or_post_delivery_exclude`-classified
  variables), which is timing- and classification-based, never
  correlation-based, and is unchanged by this correction — see the Note above.

### Four eligibility/disclosure columns
- `eligibility_status` — `"eligible"` or `"hard_excluded"`.
- `hard_exclusion_reason` — populated only when hard-excluded (one or more of the 6
  rules above, joined with `; `); null when eligible.
- `soft_warning_flags` — any applicable soft warnings, joined with `; `.
- `review_reason` — a distinct clinical-caveat note (from `MANUAL_KNOWN_LIMITATIONS`,
  or C12's descriptive-role rationale for any role other than
  `association_signal_review` -- see SC12_HEADER) for variables that ARE in
  the pool but merit a clinician's attention; null when there is no such caveat.

### `parity_history` redundancy family — clinically distinct counts, no fixed representative
`P` is authoritative for prior-parity status (`manual_decisions_log.md`
Decision 11), and `nulliparity` is corrected upstream directly from `P` as a
deterministic binarisation (`nulliparity == 1` iff `P == 0`), not an
independent measurement. `G` (gravidity), `LIVE_BIRTH`, `AB` (abortions), and
`EUP` (ectopic pregnancies) are clinically **distinct** obstetric-history
counts that `nulliparity` does not subsume, so this family has **no fixed
canonical representative** in EDA C: `config.py`'s
`REDUNDANCY_GROUPS["parity_history"]` default (`representative="nulliparity"`)
is deliberately not honoured — the only family EDA C honours a
fixed-representative demotion for is `endometrioma_location`. **`G`, `P`,
`LIVE_BIRTH`, `AB`, `EUP`, and `nulliparity` all remain eligible and in the
exported candidate pool**, flagged `redundancy_unresolved`
(family=`parity_history`); this is a **review-only** relationship group and the
co-entry choice among all its members (`G` / `AB` / `EUP` / `LIVE_BIRTH` / `P`
/ `nulliparity`) is resolved within modeling / CV. `P` ↔ `nulliparity` is a
**deterministic derivation** (`nulliparity == I(P == 0)`) but **not** one of
the eight hard co-entry pairs: `nulliparity` is a *nonlinear* basis function of
`P`, so `P` (count) and `I(P == 0)` (threshold) may jointly enter a model, and
their joint entry is a modeling-review / coefficient-stability matter, not a
global ban. Live EDA C has `redundancy_demoted = 0` for this family (and
overall). `parity_binary_0_vs_1plus` is retired and is no longer created or
exported.

### Composite priority score (DESCRIPTIVE ONLY — never a filter or a tiebreaker)
Each effect size is normalized to a comparable ~0-1 scale by its own type before
combining with clinical tier, FDR signal, timing, and missingness — using the
same weights as `analysis/model_variable_readiness/config.py` `SCORING_WEIGHTS`.
`priority_score` is exported as a ranking/sort column on the candidate pool.
**2026-08-31 rebuild:** it is **not** used to cap or trim the pool, and it is
**no longer** used to pick a redundancy-family representative (that was
target-informed pre-CV selection — removed). It carries target-derived signal
and must never drive an eligibility or co-entry decision.

### Advisory-only EPV statistic
A conservative event-per-variable cap (`min(floor(0.10 * n_rows), floor(n_events / 6))`)
is still computed and printed for reference, but it is **advisory only** — it is never
used to filter or cap the exported candidate pool.

### Share-safe presentation (`candidate_display_df`, added 2026-09-01)
`candidate_df` / `candidate_pool_df` / `excluded_features_df` are analytical/audit
frames and always keep exact values. `candidate_display_df` (+
`candidate_pool_display_df` / `excluded_features_display_df`) is a presentation-only
copy, share-safe-suppressed under `SHARE_SAFE_MODE` for `min_cell_count`,
`target0_n`/`target1_n` (propagated from C11), the structural-applicability `_n`
fields, and any `event_count_info` text that embeds a protected small count — used
for the printed previews only. `p_value` / `q_value_bh` / `fdr_q_value` / `effect_size`
/ eligibility fields are never masked.
""")

SC12B_SELECTION = code("eda-c-s12b-selection", """
import math

print("=" * 70)
print("ELIGIBILITY FILTERING AND CANDIDATE POOL CONSTRUCTION")
print("EDA C performs eligibility filtering only -- it does not choose final")
print("modeling variables. Final variable/model selection happens in EDA D.")
print("=" * 70)
print()


# ── Advisory-only EPV statistic (NOT used to filter or cap the pool) ────────────
def compute_feature_caps(n_rows, n_events, row_fraction=0.10, events_denominator=6):
    max_by_rows = math.floor(row_fraction * n_rows)
    max_by_events = math.floor(n_events / events_denominator)
    max_features = min(max_by_rows, max_by_events)
    return max_by_rows, max_by_events, max_features


N_ROWS = len(df_analysis)
N_EVENTS = int((df_analysis[TARGET_COL] == 1).sum())
_ADVISORY_BY_ROWS, _ADVISORY_BY_EVENTS, ADVISORY_CONSERVATIVE_FEATURE_CAP = compute_feature_caps(N_ROWS, N_EVENTS)

print("ADVISORY ONLY -- NOT used to filter or cap the candidate pool:")
print(f"  n_rows={N_ROWS}  n_events={N_EVENTS}")
print(f"  a conservative EPV-based primary-model cap would be ~{ADVISORY_CONSERVATIVE_FEATURE_CAP} "
      f"features (min(10% of rows, events/6)) -- for EDA D's reference only.")
print()


# ── Redundancy families ──────────────────────────────────────────────────────────
# Config-driven clinical redundancy groups (from
# analysis/model_variable_readiness/config.py, which may declare a
# `representative`) plus EDA-C-specific derived-vs-source overlap groups.
# CORRECTED 2026-09-01 (Part I, five-family audit -- see the
# EDA_C_FIXED_REPRESENTATIVE_FAMILIES definition and comment further below,
# and README "Five fixed-representative families"): `representative=None`
# does NOT mean "score-resolved at runtime" -- EDA C no longer picks a
# redundancy-family winner by priority_score at all (that was target-informed
# pre-CV selection, removed in the 2026-08-31 rebuild). It means every live
# member of that family stays eligible in the exported pool, flagged
# `redundancy_unresolved`, with the co-entry choice deferred to EDA D under
# CV. A fixed-representative demotion is honoured in EDA C ONLY for a family
# explicitly listed in `EDA_C_FIXED_REPRESENTATIVE_FAMILIES` (currently just
# `endometrioma_location`) -- config.py's own `representative` value for every
# OTHER family (including its own `parity_history` default) is deliberately
# NOT honoured here, regardless of what config.py itself says, because it is
# shared with other stages where it may still apply differently.
#
# "parity_history" is intentionally NOT overridden by DERIVED_REDUNDANCY_GROUPS
# below -- an earlier version of this pipeline gave it a fixed representative
# (the now-retired parity_binary_0_vs_1plus) because preprocessing's raw
# nulliparity disagreed with P at the time (Decision 11, 2026-07-02).
# Preprocessing now overwrites nulliparity directly from P, so nulliparity is
# itself the authoritative, P-derived predictor and there is no longer a
# disagreement to override. config.py's own default representative for this
# family ("nulliparity") is NOT honoured by EDA C either way --
# `parity_history` members G/LIVE_BIRTH/AB/EUP are clinically distinct
# obstetric counts, not subsumed by the nulliparity binarisation, so it is
# NOT in EDA_C_FIXED_REPRESENTATIVE_FAMILIES and demotes nothing here: G, P,
# LIVE_BIRTH, AB, EUP, and nulliparity all remain eligible, flagged
# redundancy_unresolved. See SC12B_HEADER's "parity_history redundancy
# family" subsection for the full corrected explanation.
DERIVED_REDUNDANCY_GROUPS = {
    "placental_dysfunction_representation": {
        "members": ["derived_placental_dysfunction_proxy", "any_PET_cat", "IUGR"],
        "representative": None,
    },
    "prior_endo_surgery_status_representation": {
        "members": ["endometriosis_surgery", "derived_prior_endo_surgery_procedure_status"],
        "representative": None,
    },
    "endo_surgery_adhesion_status_representation": {
        "members": ["endometriosis_surgery", "derived_endo_surgery_adhesion_status"],
        "representative": None,
    },
    # endometrioma_presence_laterality_representation: added Decision 70
    # (2026-08-15) with endometrioma_presence_laterality's classification.
    # Groups the derived laterality variable with its own direct lineage
    # (endometrioma, endometrioma_laterality, endometrioma_place_clean, per
    # cleaning_b_feature_dictionary.csv) so a redundant representation cannot
    # co-enter the model. endometrioma_laterality/endometrioma_place_clean
    # are excluded from Data Cleaning B's export entirely and are never
    # actually screened; only endometrioma vs. endometrioma_presence_
    # laterality can co-occur in practice.
    "endometrioma_presence_laterality_representation": {
        "members": ["endometrioma", "endometrioma_laterality", "endometrioma_place_clean",
                    "endometrioma_presence_laterality"],
        "representative": None,
    },
    # hypertension_pih_pet_spectrum_representation: added Decision 77
    # (2026-08-19) alongside derived_hypertension_pih_pet_spectrum's creation.
    # Groups the new 3-level clinical grouping with the full source-variable
    # family it summarizes (config.py's REDUNDANCY_GROUPS["hypertension"]
    # covers only the six predictor_allowed source variables it was already
    # tracking there -- HELLP/eclampsia were not previously in that group
    # despite being predictor_allowed and part of the umbrella derivation;
    # both are added here rather than to config.py, since config.py is
    # guarded to preprocessing-level source variables only and this group's
    # purpose is specifically to protect the new derived feature).
    # representative=None: the individual subtype variables retain
    # independent clinical value (e.g. distinguishing PIH from preeclampsia
    # severity) that the 3-level grouping intentionally coarsens -- same
    # policy as diabetes_status/surgical_detail_overlap below.
    "hypertension_pih_pet_spectrum_representation": {
        "members": ["pregnancy_related_hypertensive_disorder", "PIH", "mild_PET",
                    "severe_PET", "any_PET", "SIPET", "HELLP", "eclampsia",
                    "derived_hypertension_pih_pet_spectrum"],
        "representative": None,
    },
    # diabetes_representation: added Decision 78 (2026-08-19) alongside
    # derived_diabetes_type_grouped's creation. Extends A2's existing
    # diabetes_status group (gestational_diabetes/diabetes_type, association-
    # only evidence, Cramer's V 0.982, not an independently confirmed
    # derivation -- see a2_part1_setup_scope.py) with the new derived
    # member. representative=None for the same association-only-evidence
    # reason as diabetes_status itself.
    "diabetes_representation": {
        "members": ["gestational_diabetes", "diabetes_type", "derived_diabetes_type_grouped"],
        "representative": None,
    },
    # endometrioma_size_status_representation: added Decision 84 (2026-08-19)
    # alongside endometrioma_size_status's predictor-eligibility approval
    # (closes the forgotten-eligibility gap left open by Decision 71). Groups
    # the categorical size/status representation with its own direct lineage
    # (endometrioma, endometrioma_size_clean, per cleaning_b_feature_dictionary.csv)
    # so a redundant representation cannot co-enter the model -- same pattern
    # as endometrioma_presence_laterality_representation above.
    # endometrioma_size_clean is excluded from Data Cleaning B's export
    # entirely and is never actually screened; only endometrioma vs.
    # endometrioma_size_status can co-occur in practice. The retired
    # endometrioma_size_severity representation is deliberately NOT listed
    # here -- it no longer exists as a column anywhere in the pipeline
    # (fully replaced, not merely excluded from export), so there is no live
    # column for it to be redundant with.
    "endometrioma_size_status_representation": {
        "members": ["endometrioma", "endometrioma_size_clean", "endometrioma_size_status"],
        "representative": None,
    },
    # Note on representative=None groups below -- CORRECTED 2026-09-01 (Part I;
    # supersedes the 2026-08-27 note that used to read here). representative=None
    # IS disclosure-only under the current (2026-08-31 rebuild / 2026-09-01
    # five-family-audit) architecture: EDA C does not pick a per-group winner by
    # priority_score any more (see the EDA_C_FIXED_REPRESENTATIVE_FAMILIES block
    # below) -- every live member of a representative=None group stays eligible
    # in the exported pool, flagged redundancy_unresolved, and the co-entry
    # choice is deferred to EDA D under CV. This remains exactly why the
    # adenomyosis multi-hot family (see the comment near the end of this dict)
    # must still NOT be grouped at all: even under the current disclosure-only
    # mechanism, grouping 13 members that are not mutually exclusive (a
    # positive-disease flag plus its own granular sub-feature indicators) would
    # incorrectly flag 12 of them redundancy_unresolved against a family they
    # do not actually compete with -- a misleading disclosure, not a lost
    # feature (no member is actually removed from the pool either way).
    #
    # BMI_after_representation: BMI_after_cat is not materialized as a real df
    # column -- it is a documented-only, fold-safe-deferred representation
    # computed only at modeling time, so this group currently has only one live
    # member (BMI_after itself, disclosed model_entry_mode=transform_source_only)
    # and affects nothing today -- kept registered so a future accidental
    # re-materialization of BMI_after_cat as a real column is correctly caught.
    "BMI_after_representation": {
        "members": ["BMI_after", "BMI_after_cat"],
        "representative": None,
    },
    # weight_in_pregnancy_representation: weight_in_pregnancy__missing_ind has
    # been retired entirely (its former redundancy with the fold-safe
    # weight_in_pregnancy_cat representation's own not_documented bucket is now
    # moot -- the indicator can no longer exist to be redundant with anything)
    # and removed from this group's members, matching the
    # BMI_after_representation pattern above. Currently only
    # weight_in_pregnancy itself is a live member (weight_in_pregnancy_cat
    # never materializes as a real df column), so this group affects nothing
    # today -- registered so it activates automatically if
    # weight_in_pregnancy_cat ever becomes live.
    "weight_in_pregnancy_representation": {
        "members": ["weight_in_pregnancy", "weight_in_pregnancy_cat"],
        "representative": None,
    },
    # pprom_timing_representation: the raw binary PPROM predictor overlaps with
    # the fold-safe gestational_age_at_PPROM_days_timing_status representation's
    # own no_PPROM category (Part A13). Both PPROM and
    # gestational_age_at_PPROM_days are live members today. CORRECTED 2026-09-01
    # (Part I): this group does NOT demote gestational_age_at_PPROM_days -- it
    # has representative=None like every other family here, so BOTH members
    # stay eligible, flagged redundancy_unresolved(family=pprom_timing_representation);
    # the co-entry choice between them is deferred to EDA D under CV, not
    # resolved by this group's registration.
    "pprom_timing_representation": {
        "members": ["gestational_age_at_PPROM_days", "PPROM", "gestational_age_at_PPROM_days_timing_status"],
        "representative": None,
    },
    # indication_for_induction_status_representation: induction_any_bin is
    # reconstructable from indication_for_induction_status (no_induction -> 0,
    # else -> 1) -- both are live members. CORRECTED 2026-09-01 (Part I): this
    # group does NOT demote either variable in favor of the other --
    # representative=None means both stay eligible, flagged
    # redundancy_unresolved(family=indication_for_induction_status_representation);
    # deferred to EDA D under CV, not resolved here.
    "indication_for_induction_status_representation": {
        "members": ["induction_any_bin", "indication_for_induction_status"],
        "representative": None,
    },
    # adenomyosis_sonographic_features_status_representation (Decision 85's
    # deferred registration): DELETED, not replaced -- 2026-08-27 fix, rationale
    # updated 2026-09-01 (Part I) to match the current disclosure-only
    # mechanism (this group was originally deleted because the OLDER
    # score-based auto-demotion mechanism wrongly demoted 12 of its 13 live
    # members; that specific mechanism no longer exists, but registering this
    # group would still incorrectly flag those 12 members redundancy_unresolved
    # against a family they do not actually compete with). The retired
    # combination-level categorical this group used to protect no longer
    # exists (superseded by the multi-hot indicators), and the multi-hot
    # family must NOT be grouped with plain adenomyosis at all -- same as
    # endo_resection_* (Decision 19), which has no redundancy_group
    # registration for the identical reason: a positive-disease binary flag
    # and its granular sub-feature multi-hot indicators are not mutually
    # exclusive.
}
ALL_REDUNDANCY_GROUPS = dict(REDUNDANCY_GROUPS)
ALL_REDUNDANCY_GROUPS.update(DERIVED_REDUNDANCY_GROUPS)


# ── Composite priority score ──────────────────────────────────────────────────────
def _tier_to_numeric(clinical_priority_tier):
    if clinical_priority_tier in (2, "2", "tier_2"):
        return 2.0
    if clinical_priority_tier in (1, "1", "tier_1"):
        return 1.0
    if clinical_priority_tier == "derived":
        return 1.0  # derived features are clinically motivated by construction
    return 0.0


def _effect_to_unit_scale(effect_size, effect_size_type):
    if pd.isna(effect_size):
        return 0.0
    if effect_size_type in ("rank-biserial r", "Cramér's V"):
        return float(min(abs(effect_size), 1.0))
    if effect_size_type == "odds ratio":
        if effect_size <= 0:
            return 0.0
        # log-odds-ratio, capped so OR ~= 7.4 (log = 2) already reaches the ceiling
        return float(min(abs(np.log(effect_size)) / 2.0, 1.0))
    return 0.0


def compute_priority_score(row):
    tier = _tier_to_numeric(row["clinical_priority_tier"])
    eff = _effect_to_unit_scale(row["effect_size"], row["effect_size_type"])
    fdr_bonus = (SCORING_WEIGHTS.get("fdr_significant_bonus", 0.5)
                 if pd.notna(row["fdr_q_value"]) and row["fdr_q_value"] < 0.05 else 0.0)
    if row["timing"] in ("pre_pregnancy", "pregnancy"):
        timing_term = SCORING_WEIGHTS.get("timing_pre_admission_bonus", 1.0)
    else:
        # 'timing_unknown' (2026-08-18 correction, was 'unknown_but_likely_
        # pre_delivery'): genuinely unresolved timing no longer earns an
        # implicit "presumed pre-delivery" scoring bonus -- neutral like
        # 'admission_or_pre_delivery' and 'postpartum_or_outcome'. See the
        # normalize_timing_label comment above for the full rationale.
        timing_term = 0.0
    # 2026-09-01 correction (Part D): the missingness term now uses the SAME
    # three-tier PRIMARY missingness semantics as C5/C12 (ordinary /
    # applicability-linked -> raw; confirmed-structural -> genuine missingness within
    # the applicable subgroup), via primary_missing_pct_for_modeling. The
    # previous blanket "0.0 penalty for every STRUCTURAL_NAN_COLS variable"
    # rule is REMOVED -- it silently erased real within-subgroup missingness
    # information for a confirmed-structural variable that has genuine
    # missing values inside its applicable subgroup. A confirmed-structural
    # variable with 0% genuine missingness within its applicable subgroup
    # still naturally scores a 0.0 penalty (0/10 * weight == 0) -- no special
    # case is needed to produce that outcome. priority_score remains
    # descriptive only -- it never filters, caps, or ranks-to-select the pool.
    _pen_pct = row.get("primary_missing_pct_for_modeling", row.get("effective_missing_pct_for_exclusion", row["missing_%"]))
    if pd.isna(_pen_pct):
        _pen_pct = row["missing_%"]
    miss_penalty = SCORING_WEIGHTS.get("missingness_penalty_per_10pct", -0.4) * (_pen_pct / 10.0)
    score = (
        SCORING_WEIGHTS.get("clinical_tier", 3.0) * tier
        + SCORING_WEIGHTS.get("association_effect", 4.0) * eff
        + fdr_bonus + timing_term + miss_penalty
    )
    return round(float(score), 3)


candidate_df["priority_score"] = candidate_df.apply(compute_priority_score, axis=1)

# Per-variable metadata: data type, non-missing count, unique-value count.
#
# Bug fix (2026-07-30, discovered during Decision 37 / oligohydramnios): these
# summaries must reflect the variable's ACTUAL observed data, independent of
# whether statistical screening was performed. At the time of this fix,
# `df_analysis` was restricted to ANALYSIS_VARS = PREDICTOR_ALLOWED_COLS +
# derived features only, deliberately excluding PENDING_TIMING_CONFIRMATION_COLS
# and INTRAPARTUM_PREDICTOR_EXCLUDE_COLS. Decision 65 (2026-08-12) later widened
# ANALYSIS_VARS to also include INTRAPARTUM_PREDICTOR_EXCLUDE_COLS (see
# eda_c_part1_setup_gate.py, ORIGINAL_ANALYSIS_VARS) -- today, only
# PENDING_TIMING_CONFIRMATION_COLS (via `_FORBIDDEN_COLS`) remains structurally
# excluded from df_analysis, even though those variables are real columns in the
# loaded dataset (`df`) with real data. The underlying bug this fix addresses is
# unchanged: the previous code fell back to a hardcoded 0/"unknown" placeholder
# whenever a variable was absent from df_analysis, which `zero_variance_flag =
# n_unique <= 1` then misread as a zero/non-variation finding for every such
# variable -- "not statistically screened" is not the same fact as "zero
# variance", "zero non-missing observations", or "impossible values", and must
# never be conflated with them. `event_count_info == "not screened"` (set above
# for both forbidden groups) already distinguishes skipped-screening rows from
# genuinely-screened ones; inferential fields (p_value/effect_size/fdr_q_value)
# correctly stay NaN for skipped rows and are unaffected by this fix -- only the
# deterministic, non-inferential data-quality summaries below are corrected.
# `df` (the full loaded dataset, never column-restricted) is the fallback source
# for any variable absent from df_analysis; both frames are checked because
# derived features (part3) exist only in df_analysis, not in df. The summary
# logic itself lives in eda_c_screening_helpers.py (loaded from disk, same
# pattern as config.py above) so it is independently unit-tested rather than
# duplicated here.
_screening_helpers_path = _root / "analysis" / "eda" / "notebook_build" / "eda_c" / "eda_c_screening_helpers.py"
_screening_helpers_spec = importlib.util.spec_from_file_location(
    "_eda_c_screening_helpers", _screening_helpers_path
)
_screening_helpers = importlib.util.module_from_spec(_screening_helpers_spec)
_screening_helpers_spec.loader.exec_module(_screening_helpers)
compute_observed_variance_summary = _screening_helpers.compute_observed_variance_summary
resolve_observed_series = _screening_helpers.resolve_observed_series

candidate_df["data_type"] = candidate_df["variable"].apply(
    lambda v: (
        infer_var_type(resolve_observed_series(v, df_analysis, df))
        if resolve_observed_series(v, df_analysis, df) is not None else "unknown"
    )
)
_observed_summary = candidate_df["variable"].apply(
    lambda v: compute_observed_variance_summary(v, df_analysis, df)
)
candidate_df["non_missing_count"] = _observed_summary.apply(lambda t: t[0])
candidate_df["n_unique"] = _observed_summary.apply(lambda t: t[1])
# Hard exclusion rule #6: zero variance. The helper applies the project policy:
# constant status may be audited across all variables, but automatic exclusion is
# limited to the analytical predictor scope and requires no missing values plus
# exactly one observed unique value. All-missing and partially missing single-
# value variables are handled separately through missingness logic.
candidate_df["zero_variance_flag"] = _observed_summary.apply(lambda t: t[2])


# ── Hard exclusion rule #8: hard clinical unresolved / pending decision ─────────
# 2026-09-01 correction (Part E): retired the legacy `primary_model_eligible`
# field as an all-horizon hard-exclusion driver -- C8 explicitly documents it
# as legacy/compatibility only; the authoritative multi-horizon contract is
# `analytical_role` + `earliest_entry_stage`. Only iterates SCREEN_VARS members
# (never the sanity-check-only feature, which C11 already excludes from
# SCREEN_VARS -- see Part F) so every materialized derived predictor reaching
# this check is expected to have a real, resolved analytical_role; a
# materialized one with none at all fails loud rather than being silently
# treated as resolved. A derived feature is hard-excluded here only when its
# analytical_role is an EXPLICIT unresolved-state value -- an approved role
# (predictor_allowed, etc.) is never treated as unresolved regardless of what
# the legacy field says. A conditionally-unresolved feature (e.g.
# derived_placental_dysfunction_proxy while any_PET_cat is UNSET, Decision 71)
# is simply never materialized, so it never reaches DERIVED_VARS/SCREEN_VARS
# at all -- there is nothing here for this rule to exclude in that case.
_UNRESOLVED_ANALYTICAL_ROLES = {"review", "unresolved"}
_hard_excl_pending_review = set()
for _dv in DERIVED_VARS:
    if _dv not in SCREEN_VARS:
        continue
    _dv_role = derived_meta.get(_dv, {}).get("analytical_role")
    if _dv_role is None:
        raise AssertionError(
            f"{_dv}: materialized derived predictor (in SCREEN_VARS) has no "
            "'analytical_role' in derived_meta -- the multi-horizon contract "
            "requires every materialized modeling derived feature to declare "
            "its role explicitly; primary_model_eligible is legacy/compat only "
            "and must not be used to infer this."
        )
    if _dv_role in _UNRESOLVED_ANALYTICAL_ROLES:
        _hard_excl_pending_review.add(_dv)
_hard_excl_pending_timing_confirmation = set(PENDING_TIMING_CONFIRMATION_COLS)
# NOTE: _hard_excl_intrapartum_predictor_exclude (a category-wide hard
# exclusion of intrapartum_predictor_exclude_from_prelabor_model) was removed
# 2026-08-13 (Decision 65 / multi-horizon plan Batch 2). That classification
# is now part of the unified master pool and is only hard-excluded if it
# independently trips one of the substantive QC rules below (leakage,
# separation, sparsity, missingness, zero-variance, etc.), exactly like any
# predictor_allowed variable.

# ── Modeling-risk flag: severe quasi-separation (boundary-sparse instability) ───
# A variable can legitimately pass the C6/C10 too_sparse_flag rule (min_cell >= 5)
# while still sitting exactly on that boundary. Combined with a large odds ratio,
# this is the classic small-cell instability pattern (a rare feature with a
# huge-looking effect estimate driven by a handful of events).
# RECLASSIFIED 2026-08-19 (target-informed pre-CV screening consistency
# correction, no new numbered clinical Decision -- see that correction's log
# entry): this was a hard exclusion from the whole candidate pool in the prior
# design. min_cell_count/effect_size(odds ratio) are both computed from a
# full-dataset target crosstabulation, making this a target-dependent
# statistic -- excluding a variable from the candidate pool on this basis
# before any CV split is exactly the target-informed pre-CV feature-selection
# pattern this project's methodology prohibits (predictor eligibility must be
# target-independent; sparse-event/separation risk is a modeling-stage
# concern, per Decision 74/77/78's own "deferred to Modeling D" language).
# Now a disclosure-only modeling-risk flag (soft_warning_flags), same
# treatment as redundancy_demoted -- the variable remains in the pool, the
# risk is disclosed, not silently hidden. Renamed from
# _hard_excl_boundary_sparse (no longer a hard-exclusion set).
MIN_EVENT_CELL_BOUNDARY = 5  # matches the C6/C10 too_sparse_flag threshold (min_cell < 5)
BOUNDARY_SPARSE_OR_THRESHOLD = 3.0


def _is_boundary_sparse_unstable(row):
    if row["min_cell_count"] != MIN_EVENT_CELL_BOUNDARY:
        return False
    if row["effect_size_type"] != "odds ratio" or pd.isna(row["effect_size"]):
        return False
    return row["effect_size"] > BOUNDARY_SPARSE_OR_THRESHOLD


_boundary_sparse_risk_vars = set(
    candidate_df.loc[candidate_df.apply(_is_boundary_sparse_unstable, axis=1), "variable"]
)

# Manual clinical-interpretation notes for specific variables (reviewed case by case;
# not derived automatically). Feeds review_reason for ELIGIBLE variables that still
# carry a clinical caveat -- this is a first-class part of the pipeline; extend it
# directly in source when a new caveat is agreed, rather than editing exported files.
MANUAL_KNOWN_LIMITATIONS = {
    # oligohydramnios: entry removed 2026-07-30 (Decision 37, EDA B14 DEC-04
    # resolved), then reclassified back to predictor_allowed 2026-08-04
    # (Decision 62, superseding Decision 37 -- Keren clarified it is assessed
    # by ultrasound during pregnancy, like polyhydramnios). No manual
    # limitation note is added here for it -- it is now screened normally
    # like any other predictor_allowed variable, with no special caveat
    # beyond the ordinary screening gates.
    "aspirin_during_pregnancy": (
        "Represents pregnancy risk-management context/prophylaxis, not a causal "
        "medication effect."
    ),
    "endometrioma_size_clean": (
        "High missingness / conditional applicability -- interpret cautiously if "
        "still eligible. Missingness is diagnostic/soft-warning only in the current "
        "architecture (see high_missingness_diagnostic / structural_applicability_status); "
        "it is never itself a hard_exclusion_reason (2026-09-01 wording correction -- "
        "the generic missingness hard-exclusion rule this note originally referred to "
        "was removed 2026-08-31)."
    ),
}

# ── Missingness: DIAGNOSTIC ONLY (2026-08-31 methodological rebuild) ───────────
# The generic full-cohort ">40% effective missingness -> hard exclusion" rule
# has been REMOVED. In a predictive CV project, a high-missingness predictor is
# handled by fold-safe imputation / an explicit not-documented category inside
# the training fold, not by pre-CV deletion. High missingness is now:
#   * always exported as diagnostic metadata (raw_missing_pct /
#     primary_missing_pct_for_modeling / structural-applicability fields --
#     see the three-tier PRIMARY contract in SC12B_HEADER, Part C), and
#   * a SOFT warning (`high_missingness_diagnostic`) above the 40% mark
#     (evaluated against the PRIMARY value, never the raw value for a
#     confirmed-structural variable, and never the sensitivity value for a
#     applicability-linked one),
# and it changes eligibility ONLY when an explicit upstream clinical/
# methodological decision already declares the variable unusable (handled by
# classification / _FORBIDDEN_COLS upstream, or by the sanity-check-only /
# pending-review rules below -- never by a bare percentage here).
HIGH_MISSINGNESS_DIAGNOSTIC_THRESHOLD = 40.0  # percent -- SOFT warning boundary, not an exclusion
# HIGH_MISSINGNESS_EXCLUDE_OVERRIDE (2026-09-01 wording correction, Part J):
# everything below this line is HISTORICAL PROVENANCE for this now-permanently-
# inert name (always `set()` today, kept only for back-compat). There is no
# current exemption mechanism to describe, because there is no current generic
# missingness EXCLUSION rule left for any variable to be "exempted" from --
# high missingness is diagnostic-only, uniformly, for every variable. The
# BMI_after/weight_in_pregnancy provenance below is retained only because it
# explains real historical decisions (Decisions 86-89) that shaped where these
# two variables ended up (ordinary secondary_near_delivery_predictor
# candidates, `model_entry_mode=transform_source_only`, fold-safe categorical
# treatment carried in the C13 downstream_preprocessing_requirement contract)
# -- not because any override is still active.
#
# BMI_after: added 2026-08-27 (variable-specific high-missingness override,
# implementing the dedicated BMI_after missingness review -- see
# docs/clinical_decisions/manual_decisions_log.md). Approved as a
# representation/model-architecture exception, not a repeal of the generic
# 40% rule (which still existed as a hard-exclusion rule at that point in the
# project's history): BMI_after is entirely deterministic from
# weight_in_pregnancy/height (zero independent missingness, zero
# deterministically-reconstructable rows), but the project's primary logistic
# model family uses linear main effects only (no automatic
# interaction/polynomial terms), so BMI_after's normalized ratio
# representation is not reconstructable from its raw source columns by that
# model class -- unlike a variable whose exclusion would lose no
# representational information. `weight_in_pregnancy` itself was NOT added at
# the time; it remained subject to the (then still-active) generic rule. This
# override did not change BMI_after's Stage 1/2/3 timing eligibility
# (Decision 86, unaffected, not reopened).
#
# EMPTIED 2026-08-27 (Decision 89, same day as Decision 87): Decision 88
# originally closed the missingness-handling question with a modeling-stage
# fold-safe transformer, leaving raw BMI_after itself as the (overridden)
# EDA C candidate. Decision 89 simplified this further -- BMI_after_cat is
# now created directly in Data Cleaning B as a complete (0% missing)
# categorical, and raw BMI_after is hard-excluded from ANALYSIS_VARS entirely
# via MODEL_CANDIDATE_EXCLUDE_DESPITE_CLASSIFICATION_COLS
# (eda_c_part1_setup_gate.py) -- it never reaches candidate_df, so this rule
# never even evaluates it. BMI_after_cat itself never needs an override
# either: its own missingness is 0% (every row falls into one of its four
# categories), so it never trips the >40% threshold in the first place. The
# "BMI_after" entry was therefore removed 2026-08-27 (Decision 89) as
# genuinely unnecessary at the time.
#
# RE-POPULATED 2026-08-27, same day (correction supersedes Decision 89's
# materialize-in-B mechanism only): BMI_after_cat is no longer materialized
# in Data Cleaning B at all -- raw BMI_after is back in the candidate pool
# (secondary_near_delivery_predictor, model_entry_mode=transform_source_only)
# with its real 57.3% whole-cohort missingness, and there is no registered
# structural-applicability gate for it (its missingness is genuine, not
# structural), so its PRIMARY missingness is that same 57.3% figure -- BMI_after
# and weight_in_pregnancy both have an approved-but-deferred fold-safe
# categorical treatment plan (BMI_after_cat / weight_in_pregnancy_cat,
# computed at modeling time), disclosed via
# `fold_safe_representation_pending_modeling_stage`, not via any missingness
# override mechanism (2026-08-31 rebuild removed the generic rule this
# override circumvented, so the override itself became meaningless, not just
# unnecessary).
# gestational_age_at_PPROM_days: PENDING-structural, so its PRIMARY missingness
# is the RAW ~96.3% (2026-09-01 three-tier correction, Part C -- previously
# this section wrongly implied its low applicability-aware figure was already
# authoritative here).
HIGH_MISSINGNESS_EXCLUDE_OVERRIDE = set()  # retired -- kept as an empty name for back-compat only


def _is_high_missingness_diagnostic(row):
    # Uses primary_missing_pct_for_modeling (the tier-aware PRIMARY value --
    # RAW for ordinary/applicability-linked, genuine-within-applicable-subgroup
    # for confirmed-structural; see the three-tier contract in SC12B_HEADER).
    # effective_missing_pct_for_exclusion is read as a fallback ONLY for
    # defensive compatibility with a row that predates this field (never
    # expected live) -- it is now a pure alias of the same value, not an
    # independent computation. SOFT diagnostic only -- never removes a
    # variable from the pool.
    _pct = row.get("primary_missing_pct_for_modeling", row.get("effective_missing_pct_for_exclusion", row["missing_%"]))
    return pd.notna(_pct) and _pct > HIGH_MISSINGNESS_DIAGNOSTIC_THRESHOLD


_high_missingness_diagnostic_vars = set(
    candidate_df.loc[candidate_df.apply(_is_high_missingness_diagnostic, axis=1), "variable"]
)
# Retained name for downstream code that still references it -- now ALWAYS empty
# (no variable is hard-excluded for missingness under the rebuilt architecture).
_hard_excl_high_missingness = set()


def _is_sanity_check_only(col):
    # 2026-09-01 correction (Part F): checks the authoritative analytical_role
    # (matches the C8 plan's own "sanity_check_only" contract) rather than the
    # legacy primary_model_eligible=="no" field. In practice this predicate
    # never fires for any live candidate_df row: derived_nulliparity_with_prior_cs
    # is excluded from SCREEN_VARS before candidate_df is even built (see C11),
    # so it is NOT an active candidate-pool exclusion mechanism today -- this
    # remains here purely as defense-in-depth against a future accidental
    # change that adds it to SCREEN_VARS.
    return derived_meta.get(col, {}).get("analytical_role") == "sanity_check_only"


# ── Hard-exclusion reason (target-independent rules only) and eligibility_status ─
# separation_flag / too_sparse_flag / boundary-sparse-instability REMOVED from
# hard exclusion 2026-08-19 (target-informed pre-CV screening consistency
# correction -- see that correction's manual_decisions_log.md entry). All
# three are computed from a full-dataset target crosstabulation
# (min_cell_count / separation are counts of target=0 vs target=1 rows per
# category level); using them to remove a variable from the candidate pool
# before any CV split is target-informed pre-CV feature selection, which this
# project's methodology prohibits (predictor eligibility must be
# target-independent; sparse-event/separation risk is a modeling-stage
# concern -- see Decision 74/77/78's own "deferred to Modeling D" language,
# now made architecturally consistent rather than merely asserted in prose).
# They remain fully computed and disclosed via soft_warning_flags below
# (separation_risk / sparse_event_risk / boundary_sparse_instability_risk) --
# a modeling-risk flag, not an eligibility exclusion.
#
# leakage_flag REMOVED from hard exclusion 2026-08-20 (same target-informed
# pre-CV screening consistency correction, closing the one remaining gap --
# see the hard-exclusion-rules docstring above and that correction's
# manual_decisions_log.md entry). leakage_flag (derived-feature correlation
# with target_intrapartum_cs > LEAKAGE_FLAG_THRESHOLD, C10) is itself computed
# from the target column; automatically removing a variable from the pool on
# that basis alone, before any CV split, is target-informed pre-CV feature
# selection -- a strong full-dataset correlation is a WARNING that lineage/
# semantic review is needed, not proof of leakage. It remains fully computed
# and disclosed via soft_warning_flags below (high_target_association_review)
# -- a modeling-risk/review flag, not an eligibility exclusion. This does NOT
# weaken semantic/clinical leakage protection: post-outcome, post-delivery, or
# intrapartum-only variables are excluded upstream in C2/C3 (before
# ANALYSIS_VARS/SCREEN_VARS is even built) purely by clinical timing and
# explicit classification (leakage_exclude,
# intrapartum_or_post_delivery_exclude, etc.) -- never by a correlation
# statistic -- and that mechanism is completely untouched by this change.
#
# Every remaining hard-exclusion rule below is target-independent: impossible
# values, zero variance, hard-clinical-unresolved, pending-timing-confirmation,
# and sanity-check-only. The generic high-missingness rule was REMOVED in the
# 2026-08-31 methodological rebuild (see the missingness-rule note above) --
# missingness is now diagnostic + soft warning only.
def _hard_exclusion_reasons(row):
    reasons = []
    if row["impossible_flag"]:
        reasons.append("invalid_or_impossible_values")
    if row["zero_variance_flag"]:
        reasons.append("zero_variance")
    if row["variable"] in _hard_excl_pending_review:
        reasons.append("hard_clinical_unresolved_pending_review")
    if row["variable"] in _hard_excl_pending_timing_confirmation:
        reasons.append(PENDING_TIMING_CONFIRMATION_REASON)
    if _is_sanity_check_only(row["variable"]):
        reasons.append("sanity_check_only_not_a_modeling_candidate")
    return "; ".join(reasons)


candidate_df["hard_exclusion_reason"] = candidate_df.apply(_hard_exclusion_reasons, axis=1)
_hard_excluded_mask = candidate_df["hard_exclusion_reason"] != ""
candidate_df["eligibility_status"] = np.where(_hard_excluded_mask, "hard_excluded", "eligible")
candidate_df.loc[~_hard_excluded_mask, "hard_exclusion_reason"] = None


# ── Soft warnings (disclosure only -- never remove a variable from the pool) ────
RARE_PREVALENCE_THRESHOLD = 0.03   # 3% of the cohort
RARE_ABSOLUTE_COUNT_THRESHOLD = 15  # total positive count across the full cohort


def _rare_feature_flag(variable):
    if variable not in df_analysis.columns:
        return False
    s = df_analysis[variable]
    if not set(s.dropna().unique()).issubset({0, 1, 0.0, 1.0}):
        return False
    total_pos = int((s == 1).sum())
    prevalence = total_pos / len(df_analysis)
    return prevalence < RARE_PREVALENCE_THRESHOLD or total_pos < RARE_ABSOLUTE_COUNT_THRESHOLD


candidate_df["rare_feature_flag"] = candidate_df["variable"].apply(_rare_feature_flag)

# Timing-uncertain flag: timing uncertainty alone is never sufficient to exclude a
# variable from the pool -- disclosure only.
candidate_df["timing_uncertain"] = candidate_df["timing"] == "timing_unknown"


# Quality bar is disclosure-only now (it used to gate the old compact "primary" pick).
def _meets_quality_bar(row):
    tier = _tier_to_numeric(row["clinical_priority_tier"])
    fdr_sig = pd.notna(row["fdr_q_value"]) and row["fdr_q_value"] < 0.05
    nominal_sig = pd.notna(row["p_value"]) and row["p_value"] < 0.05
    return tier >= 1 or fdr_sig or nominal_sig


candidate_df["meets_quality_bar"] = candidate_df.apply(_meets_quality_bar, axis=1)


# ── Redundancy resolution: TARGET-INDEPENDENT ONLY (2026-08-31 rebuild;
#    five-family audit 2026-09-01) ───────────────────────────────────────────
# METHODOLOGICAL CORRECTION: the previous version, when a redundancy family had
# `representative=None`, chose the surviving representative by `priority_score`
# (which includes target effect size + FDR) -- target-informed pre-CV feature
# selection. That is removed.
#
# 2026-09-01 FIVE-FAMILY AUDIT (see README "Five fixed-representative families"):
# config.py's five fixed-representative families were traced against source
# lineage + the decision log. Only families where one representation is an
# explicitly-approved canonical replacement/supersession of the other(s)
# (Category A) may keep a fixed-representative demotion IN EDA C. The audit
# result:
#   parity_history        -> B (nulliparity is a deterministic binarisation of P;
#                                G/LIVE_BIRTH/AB/EUP are distinct obstetric counts)
#   prior_cs_count         -> C (S_P_CS = CS>0, but CS carries the count, which is
#                                clinically distinct for TOLAC risk)
#   anthropometry          -> B (BMI_before is the index; weight_before_pregnancy /
#                                height are its own components -- do not demote
#                                components merely because the index exists)
#   hypertension           -> C (PIH / mild_PET / SIPET carry distinct severity
#                                information; Decision 77 retained them ungrouped)
#   endometrioma_location  -> A (endometrioma_place_clean/_laterality superseded by
#                                endometrioma_presence_laterality, Decision 24/25/70)
#                                -- but INERT: neither raw member is in Batch19, so
#                                this family has < 2 present members and demotes
#                                nothing anyway.
# => EDA C honours a fixed-representative demotion ONLY for families named in
#    EDA_C_FIXED_REPRESENTATIVE_FAMILIES (currently the one Category-A family).
#    Every other family -- config or derived, whatever its `representative` value
#    -- is treated as representative=None: all members kept, redundancy_unresolved,
#    choice deferred to EDA D under CV. config.py is NOT modified (it is shared
#    with other stages / descriptive-only there); this override is EDA-C-local.
EDA_C_FIXED_REPRESENTATIVE_FAMILIES = {"endometrioma_location"}
_redundancy_demoted = {}     # variable -> (group_name, representative_variable)  [Category-A families only]
_redundancy_unresolved = {}  # variable -> group_name                            [all other families]
for _grp, _def in ALL_REDUNDANCY_GROUPS.items():
    _members_present = [m for m in _def["members"] if m in candidate_df["variable"].values]
    if len(_members_present) < 2:
        continue
    _fixed_rep = _def.get("representative")
    _fixed_rep_eligible = (
        _grp in EDA_C_FIXED_REPRESENTATIVE_FAMILIES
        and _fixed_rep is not None
        and _fixed_rep in _members_present
        and candidate_df.loc[candidate_df["variable"] == _fixed_rep, "eligibility_status"].iloc[0] == "eligible"
    )
    if _fixed_rep_eligible:
        for _m in _members_present:
            if _m != _fixed_rep:
                _redundancy_demoted[_m] = (_grp, _fixed_rep)
    else:
        # No target-independent canonical winner -> keep all members, defer to CV.
        for _m in _members_present:
            _redundancy_unresolved[_m] = _grp

candidate_df["redundancy_group"] = candidate_df["variable"].apply(
    lambda v: (
        _redundancy_demoted[v][0] if v in _redundancy_demoted
        else (_redundancy_unresolved[v] if v in _redundancy_unresolved else "—")
    )
)
candidate_df["redundancy_demoted"] = candidate_df["variable"].isin(_redundancy_demoted)
candidate_df["redundancy_unresolved"] = candidate_df["variable"].isin(_redundancy_unresolved)
candidate_df["redundancy_unresolved_group"] = candidate_df["variable"].apply(
    lambda v: _redundancy_unresolved.get(v, "—")
)


# ── soft_warning_flags and review_reason (built once all inputs are ready) ──────
# separation_risk / sparse_event_risk / boundary_sparse_instability_risk added
# 2026-08-19; high_target_association_review added 2026-08-20 (renamed 2026-09-01; same
# target-informed pre-CV screening consistency correction): disclosure-only
# modeling-risk flags for the four target-dependent statistics that were
# previously hard exclusions -- see the removal note on
# _hard_exclusion_reasons above. Same disclosure-not-exclusion treatment as
# redundancy_demoted; separation/sparsity must be handled inside Modeling D
# (regularized/penalized estimation, fold-specific diagnostics), and a
# disclosed high_target_association_review must be resolved by manual
# lineage/semantic review of the derived feature's construction, not by an
# automatic statistical rule -- neither is resolved here.
def _soft_warning_flags(row):
    flags = []
    if row["rare_feature_flag"]:
        flags.append("rare_feature")
    if row["timing_uncertain"]:
        flags.append("timing_uncertain")
    if row["redundancy_demoted"]:
        flags.append(f"redundancy_demoted(family={row['redundancy_group']})")
    if row.get("redundancy_unresolved"):
        # representative=None family -- BOTH/ALL members stay eligible; the
        # co-entry choice is a CV/modeling decision, never made here.
        flags.append(f"redundancy_unresolved(family={row.get('redundancy_unresolved_group', row['redundancy_group'])})")
    if not row["meets_quality_bar"]:
        flags.append("weak_univariate_signal")
    if row["separation_flag"]:
        flags.append("separation_risk")
    elif row["too_sparse_flag"]:
        flags.append("sparse_event_risk")
    if row["variable"] in _boundary_sparse_risk_vars:
        flags.append("boundary_sparse_instability_risk")
    if row["high_target_association_review"]:
        flags.append("high_target_association_review")
    # high_missingness_diagnostic: the generic >40% HARD rule was removed in the
    # 2026-08-31 rebuild. A pool variable above the 40% (structural-applicability-
    # aware) mark keeps missing_%/effective_missing_pct populated and carries
    # this SOFT flag so downstream fold-safe imputation/encoding is explicitly
    # planned -- it is never a reason for pre-CV deletion.
    if row["variable"] in _high_missingness_diagnostic_vars:
        flags.append("high_missingness_diagnostic")
    # fold_safe_representation_pending_modeling_stage: added 2026-08-27
    # (Part A9/A11/A13/A20/A22 correction). Distinct from
    # high_missingness_risk_documented_override above -- this flags that the
    # variable's APPROVED model-facing representation is a fold-safe
    # categorical computed only at modeling time (never a real column here),
    # so "eligible" must never be read as "safe to feed directly into a
    # design matrix as a plain numeric predictor."
    if row.get("model_entry_mode") == "transform_source_only":
        flags.append("fold_safe_representation_pending_modeling_stage")
    return "; ".join(flags)


candidate_df["soft_warning_flags"] = candidate_df.apply(_soft_warning_flags, axis=1)


def _review_reason(row):
    # 2026-09-01 correction (Part A4): under the old taxonomy this only fired
    # for role=="review_candidate", so an eligible variable carrying a soft
    # risk (separation/high-target-association/sparse -- all "exclude_candidate"
    # under the OLD, contradictory taxonomy) silently lost its explicit review
    # reason. Every DESCRIPTIVE role except "association_signal_review" (a
    # clean positive-only signal, by construction of the role if/elif chain in
    # SC12_CANDIDATE_TABLE -- a row only reaches that role when none of the
    # soft-risk/horizon/redundancy branches above it fired) now carries its
    # reason forward here; "hard_exclusion_review" rows are never eligible
    # (see eligibility_status), so the guard below already excludes them.
    parts = []
    if row["variable"] in MANUAL_KNOWN_LIMITATIONS:
        parts.append(MANUAL_KNOWN_LIMITATIONS[row["variable"]])
    if (row["eligibility_status"] == "eligible"
            and row["candidate_role_for_modeling_review"] != "association_signal_review"):
        parts.append(row["reason"])
    text = "; ".join(parts)
    return text if text else None


candidate_df["review_reason"] = candidate_df.apply(_review_reason, axis=1)


# ── Candidate pool: every eligible variable, no cap, no greedy pick ─────────────
candidate_pool_df = (
    candidate_df.loc[candidate_df["eligibility_status"] == "eligible"]
    .sort_values("priority_score", ascending=False)
    .reset_index(drop=True)
)
excluded_features_df = (
    candidate_df.loc[candidate_df["eligibility_status"] == "hard_excluded"]
    .sort_values("variable")
    .reset_index(drop=True)
)

# Fail-loud rule (Decision 70, 2026-08-15; strengthened 2026-08-16): no
# "unknown"/"UNSET"/unclassified variable may enter the eligible EDA C
# candidate pool. "UNSET" is the centralized-registry sentinel (Data Cleaning
# B's exported feature dictionary); "unknown" is this file's own historical
# fallback for anything not covered by any classification source at all.
# B-created columns with UNSET metadata are excluded upstream in
# eda_c_part1_setup_gate.py (B_CREATED_EXCLUDED_UNSET_METADATA) before they
# ever reach SCREEN_VARS, so this check should never actually fire for them
# in practice -- it remains here as defense-in-depth, not the primary gate.
# This does not block the overall EDA C run's provisional status.
_unknown_in_pool = candidate_pool_df.loc[
    candidate_pool_df["predictor_classification"].isna()
    | candidate_pool_df["predictor_classification"].isin(["unknown", "UNSET"]),
    "variable",
].tolist()
if _unknown_in_pool:
    raise AssertionError(
        "Fail-loud rule violated: unknown/UNSET/unclassified variable(s) in "
        f"the eligible candidate pool: {_unknown_in_pool}. Register a "
        "predictor_classification for each in Data Cleaning B's centralized "
        "feature-creation registry (cleaning_b_part1_setup_inputs.py, "
        "new_feature_dictionary_entry) or derived_meta before it may enter the pool."
    )

# Informational only: pool size if fixed-representative families were additionally
# resolved to their (target-independent) representative. representative=None
# families contribute NOTHING to this reduction any more -- their members are all
# kept and the choice is deferred to CV (2026-08-31 rebuild).
_post_redundancy_mask = (
    (candidate_df["eligibility_status"] == "eligible") & (~candidate_df["redundancy_demoted"])
)
eligible_pool_df = candidate_df.loc[_post_redundancy_mask].sort_values("priority_score", ascending=False)

candidate_df["_sort_key"] = candidate_df["eligibility_status"].map({"eligible": 0, "hard_excluded": 1})
candidate_df = candidate_df.sort_values(["_sort_key", "priority_score"], ascending=[True, False]).drop(columns="_sort_key")

# ── Share-safe presentation-only view (2026-09-01 correction, Part H) ──────────
# candidate_df / candidate_pool_df / excluded_features_df above always keep
# exact analytical values -- this view is for printed/displayed tables only
# and never feeds back into any computation, p/q/effect-size, or eligibility
# logic (those are never masked here).
_SS_C12 = bool(SHARE_SAFE_MODE) if "SHARE_SAFE_MODE" in dir() else True


def _suppress_candidate_display_row(row):
    _min_cell = row["min_cell_count"]
    _min_cell_disp = (
        share_safe.safe_count(_min_cell, enabled=_SS_C12)
        if isinstance(_min_cell, (int, float)) and pd.notna(_min_cell) and _min_cell >= 0
        else _min_cell
    )
    _t0, _t1 = row.get("target0_n"), row.get("target1_n")
    _local_total = (_t0 + _t1) if (pd.notna(_t0) and pd.notna(_t1)) else None
    _t0_disp = share_safe.safe_count_with_complement(_t0, _local_total, enabled=_SS_C12) if pd.notna(_t0) else _t0
    _t1_disp = share_safe.safe_count_with_complement(_t1, _local_total, enabled=_SS_C12) if pd.notna(_t1) else _t1
    _applic_n = row["structural_applicability_applicable_n"]
    _applic_n_disp = share_safe.safe_count(_applic_n, enabled=_SS_C12) if pd.notna(_applic_n) else _applic_n
    _genuine_n = row["structural_applicability_genuine_missing_applicable_n"]
    _genuine_n_disp = share_safe.safe_count(_genuine_n, enabled=_SS_C12) if pd.notna(_genuine_n) else _genuine_n
    # event_count_info embeds min_cell_count as text ("min_cell=N") for a
    # categorical/binary variable -- rebuild it from the already-suppressed
    # display value so the protected small count isn't leaked via the string.
    _event_info_disp = row["event_count_info"]
    if isinstance(_event_info_disp, str) and _event_info_disp.startswith("min_cell="):
        _event_info_disp = f"min_cell={_min_cell_disp}"
    return pd.Series({
        "min_cell_count": _min_cell_disp,
        "target0_n": _t0_disp,
        "target1_n": _t1_disp,
        "structural_applicability_applicable_n": _applic_n_disp,
        "structural_applicability_genuine_missing_applicable_n": _genuine_n_disp,
        "event_count_info": _event_info_disp,
    })


candidate_display_df = candidate_df.copy()
_cd_display_overrides = candidate_df.apply(_suppress_candidate_display_row, axis=1)
for _c in _cd_display_overrides.columns:
    candidate_display_df[_c] = _cd_display_overrides[_c]
candidate_pool_display_df = candidate_display_df.loc[candidate_display_df["eligibility_status"] == "eligible"]
excluded_features_display_df = (
    candidate_display_df.loc[candidate_display_df["eligibility_status"] == "hard_excluded"]
    .sort_values("variable")
)

print(f"Screened variables: {len(candidate_df)}")
print(f"Hard-excluded: {len(excluded_features_df)}")
print(f"Eligible candidate pool (exported, includes redundancy-flagged members): {len(candidate_pool_df)}")
print(f"  of which redundancy-demoted (fixed-representative family, kept in pool, flagged): {int(candidate_pool_df['redundancy_demoted'].sum())}")
print(f"  of which redundancy-unresolved (representative=None family, kept in pool, choice deferred to CV): {int(candidate_pool_df['redundancy_unresolved'].sum())}")
print(f"  if fixed-representative families were additionally reduced: {len(eligible_pool_df)}")
print()

_hard_excl_counts = {
    # leakage_or_post_outcome_proxy / complete_or_quasi_separation /
    # severe_quasi_separation_boundary_sparse_instability /
    # too_sparse_insufficient_cell_counts REMOVED from this dict (2026-08-19
    # separation/sparsity; 2026-08-20 leakage_flag) -- none are hard-exclusion
    # rules any more, see _soft_counts below.
    "invalid_or_impossible_values": int(candidate_df["impossible_flag"].sum()),
    "zero_variance": int(candidate_df["zero_variance_flag"].sum()),
    # high_missingness_exceeds_threshold REMOVED as a hard-exclusion rule
    # (2026-08-31 methodological rebuild) -- reported as a soft warning
    # (`high_missingness_diagnostic`) in _soft_counts below. Kept here pinned at
    # 0 so downstream manifest consumers that read this key do not KeyError.
    "high_missingness_exceeds_threshold": 0,
    "hard_clinical_unresolved_pending_review": int(candidate_df["variable"].isin(_hard_excl_pending_review).sum()),
    PENDING_TIMING_CONFIRMATION_REASON: int(candidate_df["variable"].isin(_hard_excl_pending_timing_confirmation).sum()),
    # NOTE: the category-wide intrapartum_predictor_exclude_from_prelabor_model
    # hard-exclusion count was removed here 2026-08-13 (Decision 65 / multi-
    # horizon plan Batch 2) -- that classification is no longer a hard-exclusion
    # rule of its own. Its per-variable disposition is still fully visible via
    # candidate_df["predictor_classification"].
    # sanity_check_only: structurally guaranteed to be 0 (Part F, 2026-09-01) --
    # derived_nulliparity_with_prior_cs is excluded from SCREEN_VARS before
    # candidate_df is even built (see C11), so it never becomes a candidate_df
    # row for this predicate to match. Kept as a live, executable defense-in-depth
    # count, not evidence of an active candidate-pool exclusion mechanism.
    "sanity_check_only": int(candidate_df["variable"].apply(_is_sanity_check_only).sum()),
}
print("Hard-exclusion counts by rule (not mutually exclusive -- a variable can trip more than one):")
for _k, _v in _hard_excl_counts.items():
    print(f"  {_k}: {_v}")
print()

_soft_counts = {
    "rare_feature": int(candidate_df["rare_feature_flag"].sum()),
    "timing_uncertain": int(candidate_df["timing_uncertain"].sum()),
    "redundancy_demoted": int(candidate_df["redundancy_demoted"].sum()),
    "redundancy_unresolved": int(candidate_df["redundancy_unresolved"].sum()),
    "high_missingness_diagnostic": int(candidate_df["variable"].isin(_high_missingness_diagnostic_vars).sum()),
    # weak_univariate_signal: renamed 2026-09-01 from below_quality_bar (a weak
    # univariate association is NOT low data quality and never excludes).
    "weak_univariate_signal": int((~candidate_df["meets_quality_bar"]).sum()),
    # separation_risk / sparse_event_risk / boundary_sparse_instability_risk
    # added 2026-08-19; high_target_association_review added 2026-08-20 (renamed
    # 2026-09-01 from target_correlation_leakage_risk -- high target association
    # is NOT by itself leakage) -- disclosure only, never removes a variable.
    "separation_risk": int(candidate_df["separation_flag"].sum()),
    "sparse_event_risk": int((candidate_df["too_sparse_flag"] & ~candidate_df["separation_flag"]).sum()),
    "boundary_sparse_instability_risk": int(candidate_df["variable"].isin(_boundary_sparse_risk_vars).sum()),
    "high_target_association_review": int(candidate_df["high_target_association_review"].sum()),
}
print("Soft-warning counts (disclosure only -- NOT excluded from the pool):")
for _k, _v in _soft_counts.items():
    print(f"  {_k}: {_v}")
print()

print(f"Candidate pool preview (top 15 of {len(candidate_pool_df)} by priority_score, share-safe display):")
_POOL_PREVIEW_COLS = [
    "variable", "domain", "timing", "missing_%", "p_value", "fdr_q_value",
    "effect_size", "effect_size_type", "priority_score", "soft_warning_flags", "review_reason",
]
print(candidate_pool_display_df[_POOL_PREVIEW_COLS].head(15).to_string(index=False))
print()

print(f"Hard-excluded variables ({len(excluded_features_df)}):")
print(excluded_features_display_df[["variable", "hard_exclusion_reason"]].to_string(index=False))
print()
print("=" * 70)
""")


# ── Section C12c ───────────────────────────────────────────────────────────────
SC12C_HEADER = md("eda-c-s12c-header", """
## Section C12c — Candidate Pool Validation Checks

Assert-style checks on the C12b candidate pool. These run every time this
notebook executes (independent of the `SAVE_*` export flags) so a broken pool
is caught immediately, not only when files are written.

`pool_validation_passed = True` only when every check below passes. These checks
exist specifically to confirm the hard-exclusion taxonomy was applied correctly --
i.e. that no hard-excluded variable leaked into the exported candidate pool.

**Strengthened 2026-09-01 (Part L):** additional checks confirm SCREEN_VARS
completeness/uniqueness in `candidate_df`; every materialized derived predictor
has a non-unknown `domain`; separation/high-target-association/sparse-event
variables remain **eligible** (soft warning, never a hard exclusion);
`hard_exclusion_reason` never contains a target-informed metric token and only
ever uses the approved target-independent vocabulary; the three-tier
missingness PRIMARY contract holds (applicability-linked primary == raw;
confirmed-structural primary == genuine-within-applicable-subgroup; ordinary
primary == raw); `high_missingness_diagnostic` is evaluated against the
PRIMARY value; `candidate_display_df` never alters analytical p/q/effect-size
values; every SCREEN_VARS member has C11 `test_status` populated; and the
zero-variance hard exclusions are exactly the four expected live variables.
""")

SC12C_VALIDATE = code("eda-c-s12c-validate", """
print("=" * 70)
print("CANDIDATE POOL VALIDATION CHECKS")
print("=" * 70)

_POOL_VARS = list(candidate_pool_df["variable"])
_check_matrix_cols = [TARGET_COL] + _POOL_VARS
_check_matrix = df_analysis[[c for c in _check_matrix_cols if c in df_analysis.columns]].copy()

_POSTPARTUM_OUTCOME_HINTS = set(LEAKAGE_EXCLUDE_COLS) | set(INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS)
_PENDING_TIMING_HINTS = set(PENDING_TIMING_CONFIRMATION_COLS)

# 2026-09-01 correction (Part K): the exact, exhaustive, target-independent
# hard-exclusion vocabulary. Every non-null hard_exclusion_reason value must
# be composed only of tokens from this set -- a target-informed C10/C11
# metric (p-value, q-value, FDR significance, effect size, separation, sparse
# cells, target association, priority score, redundancy) must NEVER appear.
_APPROVED_HARD_EXCLUSION_VOCAB = {
    "invalid_or_impossible_values",
    "zero_variance",
    "hard_clinical_unresolved_pending_review",
    PENDING_TIMING_CONFIRMATION_REASON,
    "sanity_check_only_not_a_modeling_candidate",
}
_TARGET_INFORMED_HARD_EXCLUSION_TOKENS = (
    "p_value", "q_value", "fdr", "effect_size", "separation", "sparse",
    "target_association", "priority_score", "redundancy", "high_target_association_review",
)
# NOTE: _INTRAPARTUM_PREDICTOR_EXCLUDE_HINTS (backing the check that
# intrapartum_predictor_exclude_from_prelabor_model must be absent from the
# candidate pool) was removed 2026-08-13 (Decision 65 / multi-horizon plan
# Batch 2) -- that classification is now an approved, expected member of the
# unified master pool. See the predictor_classification metadata check below
# instead.

pool_validation_checks = {
    "Target column exists in dataset":
        TARGET_COL in df.columns,
    "All candidate-pool variables exist in the processed dataset":
        all(v in df_analysis.columns for v in _POOL_VARS),
    "Target column is not among candidate-pool variables":
        TARGET_COL not in _POOL_VARS,
    "No candidate-pool variable is an ID column":
        not (set(_POOL_VARS) & set(ID_COLS)),
    # leakage_flag is no longer a hard-exclusion criterion (2026-08-20,
    # target-informed pre-CV screening consistency correction -- it is a
    # full-dataset target-correlation statistic, so hard-excluding on it
    # before any CV split was the same anti-pattern already corrected for
    # separation/sparsity on 2026-08-19). A candidate-pool variable WITH this
    # risk flag is expected and correct, as long as the risk is disclosed via
    # soft_warning_flags rather than silently hidden -- same self-consistency
    # pattern as redundancy_demoted/separation_risk/sparse_event_risk.
    "Every candidate-pool variable with a high target association discloses high_target_association_review":
        bool(
            candidate_pool_df.loc[candidate_pool_df["high_target_association_review"], "soft_warning_flags"]
            .str.contains("high_target_association_review").all()
        ) if candidate_pool_df["high_target_association_review"].any() else True,
    "No candidate-pool variable is a known postpartum/delivery/neonatal outcome variable":
        not (set(_POOL_VARS) & _POSTPARTUM_OUTCOME_HINTS),
    "No candidate-pool variable is pending timing confirmation":
        not (set(_POOL_VARS) & _PENDING_TIMING_HINTS),
    "Every candidate-pool variable has a populated predictor_classification (Decision 65 metadata-preservation requirement)":
        bool(
            candidate_pool_df["predictor_classification"].notna().all()
            and (candidate_pool_df["predictor_classification"] != "unknown").all()
        ) if "predictor_classification" in candidate_pool_df.columns else False,
    # separation_flag / too_sparse_flag / boundary-sparse-instability are no
    # longer hard-exclusion criteria (2026-08-19, target-informed pre-CV
    # screening consistency correction) -- a candidate-pool variable WITH one
    # of these target-dependent risk flags is expected and correct, as long
    # as the risk is disclosed via soft_warning_flags rather than silently
    # hidden. Same self-consistency pattern as redundancy_demoted.
    "Every candidate-pool variable with separation risk discloses separation_risk":
        bool(
            candidate_pool_df.loc[candidate_pool_df["separation_flag"], "soft_warning_flags"]
            .str.contains("separation_risk").all()
        ) if candidate_pool_df["separation_flag"].any() else True,
    "Every candidate-pool variable with sparse-event risk discloses sparse_event_risk":
        bool(
            candidate_pool_df.loc[
                candidate_pool_df["too_sparse_flag"] & ~candidate_pool_df["separation_flag"], "soft_warning_flags"
            ].str.contains("sparse_event_risk").all()
        ) if (candidate_pool_df["too_sparse_flag"] & ~candidate_pool_df["separation_flag"]).any() else True,
    "No candidate-pool variable has impossible values":
        not bool(candidate_pool_df["impossible_flag"].any()),
    "No candidate-pool variable is zero-variance":
        not bool(candidate_pool_df["zero_variance_flag"].any()),
    "Every candidate-pool variable with boundary-sparse instability risk discloses boundary_sparse_instability_risk":
        bool(
            candidate_pool_df.loc[
                candidate_pool_df["variable"].isin(_boundary_sparse_risk_vars), "soft_warning_flags"
            ].str.contains("boundary_sparse_instability_risk").all()
        ) if (set(_POOL_VARS) & _boundary_sparse_risk_vars) else True,
    # 2026-08-31 rebuild: the generic >40% missingness HARD rule is removed.
    # We now only verify that a high-missingness pool member DISCLOSES the soft
    # diagnostic (same disclosure-not-exclusion pattern as separation/sparsity).
    f"Every candidate-pool variable above {HIGH_MISSINGNESS_DIAGNOSTIC_THRESHOLD:.0f}% effective missingness discloses high_missingness_diagnostic":
        bool(
            candidate_pool_df.loc[
                candidate_pool_df["variable"].isin(_high_missingness_diagnostic_vars), "soft_warning_flags"
            ].str.contains("high_missingness_diagnostic").all()
        ) if (set(_POOL_VARS) & _high_missingness_diagnostic_vars) else True,
    "No candidate-pool variable is hard-excluded for missingness (generic >40% rule removed 2026-08-31)":
        not (set(_POOL_VARS) & _hard_excl_high_missingness),
    "No candidate-pool variable is pending hard clinical review":
        not (set(_POOL_VARS) & _hard_excl_pending_review),
    "All pending timing-confirmation variables are hard-excluded":
        set(PENDING_TIMING_CONFIRMATION_COLS).issubset(set(excluded_features_df["variable"])),
    # "All confirmed-intrapartum (excluded-from-prelabor-model) variables are
    # hard-excluded" -- RETIRED 2026-08-15 (found stale during the Decision
    # 67/69 EDA C sync; matches the _INTRAPARTUM_PREDICTOR_EXCLUDE_HINTS
    # removal note above, which was already updated 2026-08-13 for Decision 65
    # but this sibling check was missed at the time). Decision 65 made
    # intrapartum_predictor_exclude_from_prelabor_model variables an approved,
    # expected part of the unified master pool -- screened normally, eligible
    # for the intrapartum modeling horizon, not unconditionally hard-excluded.
    # Superseded by the predictor_classification metadata check above, which
    # already verifies every pool variable (including this classification)
    # carries a populated, non-"unknown" predictor_classification tag.
    "No candidate-pool variable is the sanity-check-only derived feature":
        not any(_is_sanity_check_only(v) for v in _POOL_VARS),
    "Every hard-excluded variable has a non-null hard_exclusion_reason":
        bool((candidate_df.loc[candidate_df["eligibility_status"] == "hard_excluded", "hard_exclusion_reason"].notna()).all()),
    "Every eligible variable has a null hard_exclusion_reason":
        bool((candidate_df.loc[candidate_df["eligibility_status"] == "eligible", "hard_exclusion_reason"].isna()).all()),
    "Every screened variable has eligibility_status populated":
        bool(candidate_df["eligibility_status"].notna().all()),
    "Check matrix (target + candidate-pool variables) has the same row count as df_analysis":
        len(_check_matrix) == len(df_analysis),
    "Check matrix contains target + all candidate-pool variables (no fewer, no more)":
        list(_check_matrix.columns) == _check_matrix_cols,
    "Check matrix contains no hard-excluded columns":
        not (set(_check_matrix.columns) - {TARGET_COL} - set(_POOL_VARS)),
    "No duplicate columns in the check matrix":
        not _check_matrix.columns.duplicated().any(),

    # ── 2026-09-01 correction additions (Part L, C12c strengthening) ────────
    "Every SCREEN_VARS variable appears exactly once in candidate_df":
        set(SCREEN_VARS).issubset(set(candidate_df["variable"]))
        and bool(candidate_df.loc[candidate_df["variable"].isin(SCREEN_VARS), "variable"].value_counts().eq(1).all()),
    "candidate_df has no duplicate variable rows":
        not candidate_df["variable"].duplicated().any(),
    "Every candidate_df row has a populated predictor_classification":
        bool(
            candidate_df["predictor_classification"].notna().all()
            and (candidate_df["predictor_classification"] != "unknown").all()
        ),
    "Every materialized derived modeling predictor has a non-unknown domain":
        (
            bool(
                candidate_df.loc[candidate_df["original_or_derived"] == "derived", "domain"].notna().all()
                and (candidate_df.loc[candidate_df["original_or_derived"] == "derived", "domain"] != "unknown").all()
            ) if (candidate_df["original_or_derived"] == "derived").any() else True
        ),
    "Separation-risk variables remain eligible (soft warning only, never a hard exclusion)":
        (
            bool((candidate_df.loc[candidate_df["separation_flag"], "eligibility_status"] == "eligible").all())
            if candidate_df["separation_flag"].any() else True
        ),
    "High-target-association-review variables remain eligible (soft warning only, never a hard exclusion)":
        (
            bool((candidate_df.loc[candidate_df["high_target_association_review"], "eligibility_status"] == "eligible").all())
            if candidate_df["high_target_association_review"].any() else True
        ),
    "Sparse-event-risk variables remain eligible (soft warning only, never a hard exclusion)":
        (
            bool((candidate_df.loc[candidate_df["too_sparse_flag"], "eligibility_status"] == "eligible").all())
            if candidate_df["too_sparse_flag"].any() else True
        ),
    "No hard_exclusion_reason contains a target-informed metric token":
        not any(
            any(_tok in str(_r) for _tok in _TARGET_INFORMED_HARD_EXCLUSION_TOKENS)
            for _r in candidate_df.loc[candidate_df["hard_exclusion_reason"].notna(), "hard_exclusion_reason"]
        ),
    "Every hard_exclusion_reason token belongs to the approved target-independent vocabulary":
        all(
            all(_tok in _APPROVED_HARD_EXCLUSION_VOCAB for _tok in str(_r).split("; "))
            for _r in candidate_df.loc[candidate_df["hard_exclusion_reason"].notna(), "hard_exclusion_reason"]
        ),
    "Pending-structural variables' primary missingness equals raw missingness":
        (
            bool((
                candidate_df.loc[candidate_df["structural_applicability_status"]
                                  == "applicability_linked_no_preprocessing_mask", "primary_missing_pct_for_modeling"]
                .reset_index(drop=True)
                == candidate_df.loc[candidate_df["structural_applicability_status"]
                                     == "applicability_linked_no_preprocessing_mask", "raw_missing_pct"]
                .reset_index(drop=True)
            ).all())
            if (candidate_df["structural_applicability_status"] == "applicability_linked_no_preprocessing_mask").any()
            else True
        ),
    "Confirmed-structural variables' primary missingness equals genuine missingness within the applicable subgroup":
        (
            bool((
                candidate_df.loc[candidate_df["structural_applicability_status"]
                                  == "confirmed_structural", "primary_missing_pct_for_modeling"]
                .reset_index(drop=True)
                == candidate_df.loc[candidate_df["structural_applicability_status"]
                                     == "confirmed_structural", "applicability_aware_missing_pct_sensitivity"]
                .reset_index(drop=True)
            ).all())
            if (candidate_df["structural_applicability_status"] == "confirmed_structural").any() else True
        ),
    "Ordinary variables' primary missingness equals raw missingness":
        (
            bool((
                candidate_df.loc[candidate_df["structural_applicability_status"] == "none", "primary_missing_pct_for_modeling"]
                .reset_index(drop=True)
                == candidate_df.loc[candidate_df["structural_applicability_status"] == "none", "raw_missing_pct"]
                .reset_index(drop=True)
            ).all())
            if (candidate_df["structural_applicability_status"] == "none").any() else True
        ),
    "high_missingness_diagnostic is based on the PRIMARY missingness value":
        (
            bool((
                candidate_df.loc[candidate_df["variable"].isin(_high_missingness_diagnostic_vars),
                                  "primary_missing_pct_for_modeling"]
                > HIGH_MISSINGNESS_DIAGNOSTIC_THRESHOLD
            ).all())
            if _high_missingness_diagnostic_vars else True
        ),
    "candidate_display_df masking does not alter candidate_df analytical p/q/effect-size values":
        bool(
            candidate_display_df["p_value"].equals(candidate_df["p_value"])
            and candidate_display_df["fdr_q_value"].equals(candidate_df["fdr_q_value"])
            and candidate_display_df["effect_size"].equals(candidate_df["effect_size"])
        ),
    "Every SCREEN_VARS member's candidate_df row has C11 test_status populated":
        bool(candidate_df.loc[candidate_df["variable"].isin(SCREEN_VARS), "test_status"].notna().all()),
    "Hard-excluded zero-variance variables are exactly the expected four (alcohol, eclampsia, HELLP, IUFD)":
        set(candidate_df.loc[candidate_df["zero_variance_flag"], "variable"]) == {"HELLP", "IUFD", "alcohol", "eclampsia"},
}

for _label, _passed in pool_validation_checks.items():
    print(f"  [{'PASS' if _passed else 'FAIL'}] {_label}")

pool_validation_passed = all(pool_validation_checks.values())
print()
print(f"pool_validation_passed = {pool_validation_passed}")
if not pool_validation_passed:
    _failed_checks = [k for k, v in pool_validation_checks.items() if not v]
    print("FAILED CHECKS — resolve before handing this candidate pool off to EDA D:")
    for _f in _failed_checks:
        print(f"  - {_f}")
print("=" * 70)
""")

SC12D_HEADER = md("eda-c-s12d-header", """
## Section C12d — Derived-Feature Final Role in the Candidate Pipeline

Closes the last field of the C10/C10b derived-feature validation record:
where each derived feature actually landed after C12b's eligibility filtering
-- eligible pool, hard-excluded (with reason), or not screened at all. This
is a read-only cross-reference of `candidate_df`/`candidate_pool_df` against
`DERIVED_VARS`; it does not change eligibility.
""")

SC12D_FINAL_ROLE = code("eda-c-s12d-final-role", """
print("Derived-feature final role in the candidate pipeline:")
_final_role_rows = []
for _dv in DERIVED_VARS:
    if _dv in set(candidate_pool_df["variable"]):
        _role = "ELIGIBLE (in the exported candidate pool)"
    elif _dv in set(candidate_df["variable"]):
        _reason = candidate_df.loc[candidate_df["variable"] == _dv, "hard_exclusion_reason"]
        _role = f"HARD-EXCLUDED: {_reason.iloc[0] if len(_reason) else '?'}"
    elif _is_sanity_check_only(_dv):
        # 2026-09-01 correction (Part F/M): explicit wording rather than the
        # generic fallback -- this feature is excluded from SCREEN_VARS
        # BEFORE candidate_df is built (see C11), so it is never a hard
        # exclusion; it was never a modeling candidate in the first place.
        _role = "NOT SCREENED (sanity-check-only; not part of the screening universe)"
    else:
        _role = "NOT SCREENED (not in candidate_df)"
    _final_role_rows.append({"derived_feature": _dv, "final_role": _role})
    print(f"  {_dv:<40} {_role}")
final_role_df = pd.DataFrame(_final_role_rows)
""")


# ── Section C12e ───────────────────────────────────────────────────────────────
SC12E_HEADER = md("eda-c-s12e-header", """
## Section C12e — Comprehensive Repeated-EDA Readiness Table (adapts CURRENT A2.12)

One readable master row per screened variable — the final summary of the
repeated EDA before the notebook transitions to **Feature Engineering** (already
executed in C8/C9) → **Feature Screening / Eligibility** (C12b) →
**Stage-Specific Modeling Handoff** (C13).

Columns mirror **CURRENT A2 Section A2.12** (`SB5_ELIGIBLE_TABLE`) plus this
project's stage/contract additions: `variable_type`, `predictor_classification`,
`earliest_entry_stage`, `model_entry_mode`, `non_missing_n`, and three explicit
missingness views (2026-09-01 correction, Part M -- never conflate the
applicability-linked sensitivity value with the primary one): `raw_missing_pct` (always
whole-cohort), `primary_missing_pct` (the modeling-facing PRIMARY value --
raw for ordinary/applicability-linked, genuine-within-applicable-subgroup for
confirmed-structural), `applicability_aware_missing_pct_sensitivity`
(applicability-linked sensitivity diagnostic only, never authoritative), and
`structural_applicability_status`; rare/sparse/separation flags; C11
`test_status`/`included_in_bh`; univariate `p` / BH-FDR `q` / effect size;
`redundancy_group`; source/derived; `soft_warning_flags`; `eligibility_status`;
`downstream_preprocessing_requirement`.

**It uses `p` / `q` / effect size for DESCRIPTION ONLY — never to decide
eligibility.** (The `downstream_preprocessing_requirement` column is populated
in C13; it is shown here as `--` and cross-referenced.)
""")

SC12E_TABLE = code("eda-c-s12e-table", """
_stage_from_cls = {"predictor_allowed": 1, "secondary_near_delivery_predictor": 2,
                   "intrapartum_predictor_exclude_from_prelabor_model": 3}
_cd = candidate_df.copy()
_cd["earliest_entry_stage"] = _cd["predictor_classification"].map(_stage_from_cls)
# structural_applicability_status is already computed once, correctly, in C12
# (SC12_CANDIDATE_TABLE's three-tier PRIMARY contract, 2026-09-01 correction)
# and carried on candidate_df -- reusing it here (rather than a second,
# independent recomputation) guarantees this table can never silently drift
# from C12's own status.

_READINESS_COLS = [
    "variable", "data_type", "predictor_classification", "earliest_entry_stage",
    "model_entry_mode", "non_missing_count",
    # Three explicit missingness views (2026-09-01 correction, Part M): never
    # label the applicability-linked sensitivity value as primary/effective.
    "raw_missing_pct", "primary_missing_pct_for_modeling",
    "applicability_aware_missing_pct_sensitivity", "structural_applicability_status",
    "rare_feature_flag", "too_sparse_flag", "separation_flag",
    # C11 test/BH status propagated for context (Part M) -- descriptive only.
    "test_status", "included_in_bh",
    "p_value", "fdr_q_value", "effect_size", "effect_size_type",
    "redundancy_group", "redundancy_unresolved", "original_or_derived",
    "soft_warning_flags", "eligibility_status", "hard_exclusion_reason",
]
_READINESS_COLS = [c for c in _READINESS_COLS if c in _cd.columns]
repeated_eda_readiness_df = (
    _cd[_READINESS_COLS]
    .rename(columns={
        "data_type": "variable_type",
        "non_missing_count": "non_missing_n",
        "primary_missing_pct_for_modeling": "primary_missing_pct",
        "fdr_q_value": "bh_fdr_q",
        "original_or_derived": "source_or_derived",
    })
    .sort_values(["eligibility_status", "earliest_entry_stage", "variable"])
    .reset_index(drop=True)
)
repeated_eda_readiness_df["downstream_preprocessing_requirement"] = "-- (populated in C13 export)"

print("=" * 70)
print("COMPREHENSIVE REPEATED-EDA READINESS TABLE (C12e) -- descriptive summary")
print("p / q / effect size are DESCRIPTIVE ONLY -- they never decide eligibility.")
print("=" * 70)
with pd.option_context("display.max_rows", 200, "display.width", 240):
    print(repeated_eda_readiness_df.to_string(index=False))
print()
print(f"Rows: {len(repeated_eda_readiness_df)}  |  eligible: "
      f"{int((repeated_eda_readiness_df['eligibility_status'] == 'eligible').sum())}  |  "
      f"hard-excluded: {int((repeated_eda_readiness_df['eligibility_status'] == 'hard_excluded').sum())}")
print("By earliest_entry_stage (eligible only): "
      + str(repeated_eda_readiness_df.loc[repeated_eda_readiness_df['eligibility_status'] == 'eligible', 'earliest_entry_stage']
             .value_counts().sort_index().to_dict()))
print()
print(">>> End of the repeated-EDA portion. The notebook now proceeds:")
print(">>> Feature Engineering (C8/C9, already run) -> Feature Screening / Eligibility (C12b) ->")
print(">>> Stage-Specific Modeling Handoff (C13).")
""")


EDA_C_PART4_CELLS = [
    SC10_HEADER,
    SC10_VALIDATE,
    SC10B_HEADER,
    SC10B_REGISTRY,
    SC10C_HEADER,
    SC10C_RELATIONSHIPS,
    SC11_HEADER,
    SC11_SCREENING,
    SC12_HEADER,
    SC12_CANDIDATE_TABLE,
    SC12B_HEADER,
    SC12B_SELECTION,
    SC12C_HEADER,
    SC12C_VALIDATE,
    SC12D_HEADER,
    SC12D_FINAL_ROLE,
    SC12E_HEADER,
    SC12E_TABLE,
]


if __name__ == "__main__":
    print(f"EDA C Part 4 cells defined: {len(EDA_C_PART4_CELLS)}")

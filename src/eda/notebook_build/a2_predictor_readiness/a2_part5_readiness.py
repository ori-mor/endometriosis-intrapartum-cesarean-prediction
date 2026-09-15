#!/usr/bin/env python3
"""EDA A2 — Part 5: cell definitions (sections A2.12-A2.15).

Sections:
  A2.12 — Comprehensive predictor screening summary (relocated here 2026-08-08;
        was B5 in a2_part2_missingness.py). Reuses assoc_df (A2.9), miss_df
        (A2.7), and sparse_df (A2.8) rather than recomputing its own association
        pass -- see the cell header for detail.
  A2.13 — Variable-readiness scoring: transparent additive score per primary predictor
  A2.14 — Clinical assumptions and remaining methodological limitations
  A2.15 — EDA A2 action log and conclusions

A2.13 uses local helper metadata and SCORING_WEIGHTS defined in the EDA setup cell.

A2.14 is the key human-decision interface. Nothing in A2.14 runs statistical tests —
it presents structured questions with known data context.

Depends on: df, df_primary, PRIMARY_COLS, PRIORITY_VARS, TARGET_COL,
miss_df, sparse_df, assoc_df, and config vars from Part 1. predictor_diagnostic_df
is now built locally in this file's own A2.12 cell (no longer a cross-file dependency).
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
        "id": cid, "cell_type": "code", "metadata": {},
        "source": src(text), "outputs": [], "execution_count": None,
    }


# ── Section A2.12 (relocated from a2_part2_missingness.py, formerly B5) ──────
SB5_HEADER = md("eda-b-s05-header", """
## Section A2.12 — Comprehensive Predictor Diagnostic Summary

**Purpose:** Produce a single reference table covering all PRIMARY_COLS with every
available diagnostic metric, so no variable is silently omitted from the analysis
record. This section reuses the results already computed earlier (missingness from
A2.7, sparsity from A2.8, and the formal association test from A2.9) rather than
recomputing a second, independent association pass.

**Methodological approach:** this table is a diagnostic summary, not a pre-model
recommendation layer. Whole-cohort target-derived information (`too_sparse`,
`separation_risk`, `effect_size`) is displayed, clearly marked, but is never used to
generate an include/exclude/discuss recommendation, define a pre-model candidate
list, or set a display order — the table is sorted by a target-independent key only
(clinical tier, then variable name), so that no target-derived signal creates an
indirect selection path into the model.

**What this checks:**
- Missingness, sparsity, association, and redundancy per primary predictor
- Clinical timing classification (`measurement_horizon`: baseline / near_delivery /
  intrapartum, with `pending_timing_confirmation` / `unclear` used only where applicable)

**What this does NOT do:**
- Generates no INCLUDE / EXCLUDE / DISCUSS / recommendation label
- Does not define a pre-model candidate list or change variable classification
- No variables are removed or reclassified
- Does not rerun the association test — `effect_size`/`fdr_q` are read directly from
  `assoc_df` (Section A2.9), the formal ranked test

**Output:** `predictor_diagnostic_df` — one row per primary predictor, all diagnostic
metrics combined, in target-independent order. The object itself carries every field
listed below; the inline printed table further down is a selected, readable excerpt of
that object, not a narrower object -- see that cell's own note on which fields are
excerpted.

**Columns (all present on the `predictor_diagnostic_df` object):**
- `missing_%` / `structural_nan` — from A2.7
- `cs_events` / `separation_risk` / `too_sparse` — from A2.8 (target-derived; descriptive)
- `effect_size` / `fdr_q` — reused directly from A2.9's formal association test
  (`assoc_df`; target-derived; descriptive). `fdr_q` is stored at full precision;
  `fdr_q_display` is the formatted string for display only.
- `redundancy_group` / `is_representative` — from the redundancy-group definitions
  (target-independent)
- `human_decision_needed` — yes if clinical judgment is required before modeling (see A2.14)
""")

SB5_ELIGIBLE_TABLE = code("eda-b-s05-eligible-table", """
# ── Reuse A2.9's formal association test (assoc_df) -- do not recompute ────
# Previously this cell ran its own independent quick Mann-Whitney/chi-square +
# BH-FDR pass over PRIMARY_COLS, duplicating A2.9's formal, canonical
# association test with a slightly different implementation (no retain_flag /
# effect_magnitude / per-group N breakdown), risking silent drift between the
# two. assoc_df (built in A2.9, iterating the same PRIMARY_COLS) is looked up
# directly instead.
_assoc_lk_b12 = assoc_df.set_index("variable")

# Redundancy lookup. representative=None means the group is association-only
# evidence (no independently documented derivation/source relationship) --
# treat every member as non-demotable (is_representative=True) rather than
# auto-demoting all of them, which `_m == None` would otherwise do.
_red_group = {}
_red_rep   = {}
for _gname, _gdef in REDUNDANCY_GROUPS.items():
    for _m in _gdef["members"]:
        _red_group[_m] = _gname
        _red_rep[_m]   = (
            True if _gdef["representative"] is None else (_m == _gdef["representative"])
        )

# the hand-maintained `_CLINICAL_DEC` dict (which had
# drifted out of sync with A2.14's CLINICAL_DECISIONS -- see the
# TIMING_REVIEW_STATUS definition in Part 1 for the full history) is removed.
# `human_decision_needed` below is now derived directly from
# TIMING_REVIEW_STATUS, the single canonical registry both A2.12 and A2.14 read
# from (A2.14's CLINICAL_DECISIONS entries are validated against it at
# runtime, not independently duplicated).

# Build comprehensive diagnostic table. No recommendation/suggestion column is
# computed from any of these metrics -- every column
# below is either target-independent (timing, clinical_tier, missingness,
# redundancy) or an explicitly target-derived DESCRIPTIVE metric reused as-is
# from its canonical source (A2.8's sparse_df, A2.9's assoc_df).
_rows = []
for _col in PRIMARY_COLS:
    _miss_row = miss_df[miss_df["variable"] == _col].iloc[0] if _col in miss_df["variable"].values else {}
    _sp_row   = sparse_df[sparse_df["variable"] == _col].iloc[0] if _col in sparse_df["variable"].values else {}
    _m_pct    = float(_miss_row.get("missing_%", 0))
    _struct   = bool(_miss_row.get("structural_nan", False))
    _sep      = bool(_sp_row.get("separation_risk", False))
    _sparse   = bool(_sp_row.get("too_sparse", False))
    _cs_ev    = _sp_row.get("cs_events", "—")
    _min_cell = _sp_row.get("min_any_cell", None)
    # Internal-only (never in _display_cols below, same pattern already used
    # elsewhere in this notebook for a raw value kept for computation but
    # excluded from any displayed table) -- needed to apply the same
    # cross-artifact-safe suppression to cs_events as A2.8/A2.15 use.
    _vag_ev_internal = _sp_row.get("min_vaginal_cell", None)
    _n_analyzed_internal = _sp_row.get("N_analyzed", None)
    _type_internal = _sp_row.get("type", None)
    if _col in _assoc_lk_b12.index:
        _eff_raw = _assoc_lk_b12.loc[_col, "effect_size"]
        _eff     = float(_eff_raw) if pd.notna(_eff_raw) else None
        _q_raw   = _assoc_lk_b12.loc[_col, "q_value_bh"]
        _q       = float(_q_raw) if pd.notna(_q_raw) else None
        _fdr_sig = bool(_assoc_lk_b12.loc[_col, "fdr_sig"])
    else:
        _eff, _q, _fdr_sig = None, None, False
    # Full-precision numeric fdr_q (reused directly from assoc_df, matching
    # effect_size's own treatment) -- fdr_q_display is formatting only via
    # the canonical fmt_pval() formatter, never used in any computation.
    _q_display = fmt_pval(_q)
    _grp      = _red_group.get(_col, "—")
    _is_rep   = _red_rep.get(_col, True)
    _tier     = CLINICAL_TIER.get(_col, 0)
    _timing   = TIMING_MAP.get(_col, "unknown")
    # modeling_clearance: orthogonal to _timing (measurement
    # horizon) -- see MODELING_CLEARANCE_MAP's definition in Part 1. Never
    # describe a "pending_timing_confirmation" variable as cleared just
    # because its horizon label happens to be "intrapartum". Direct indexing
    # (not .get(_col, "cleared")) is deliberate -- see MODELING_CLEARANCE_MAP's
    # fail-loud coverage assertions in Part 1: a fail-open default would
    # silently treat an unmapped variable as cleared for modeling.
    _clearance = MODELING_CLEARANCE_MAP[_col]

    # Human decision needed? (target-independent: driven by the canonical
    # TIMING_REVIEW_STATUS registry -- OPEN means clinical/timing review is
    # still required -- and timing classification, not by effect_size)
    _human = TIMING_REVIEW_STATUS.get(_col) == "OPEN" or _timing == "unclear"

    _rows.append({
        "variable":            _col,
        "predictor_classification": PRIMARY_COLS_CLASSIFICATION.get(_col, "unknown"),
        "earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(_col),
        "measurement_horizon": _timing,
        "modeling_clearance":  _clearance,
        "clinical_tier":       _tier,
        "missing_%":           _m_pct,
        "structural_nan":      _struct,
        "cs_events":           _cs_ev,
        "min_any_cell":        _min_cell,
        "_min_vaginal_cell":   _vag_ev_internal,
        "_N_analyzed":         _n_analyzed_internal,
        "_sparse_type":        _type_internal,
        "separation_risk":     _sep,
        "too_sparse":          _sparse,
        "effect_size":         _eff,
        "fdr_q":               _q,
        "fdr_q_display":       _q_display,
        "fdr_sig":             _fdr_sig,
        "redundancy_group":    _grp,
        "is_representative":   _is_rep,
        "human_decision_needed": _human,
        "decision_question":   TIMING_REVIEW_REASON.get(_col, ""),
    })

# Target-independent stable ordering only: clinical tier (a pre-specified
# clinical judgment, not derived from target_intrapartum_cs), then variable
# name alphabetically. No target-derived column (effect_size, fdr_q,
# too_sparse, separation_risk) participates in sort order, so a target
# permutation cannot change this table's row order (see the regression test).
predictor_diagnostic_df = pd.DataFrame(_rows).sort_values(
    ["clinical_tier", "variable"], ascending=[False, True]
)

print(f"All primary predictors — comprehensive diagnostic summary — {len(predictor_diagnostic_df)} variables:")
print("(effect_size / fdr_q reused directly from A2.9's assoc_df -- not recomputed here;")
print(" fdr_q is full precision, fdr_q_display below is formatted for display only)")
print("(sort order is target-independent: clinical_tier desc, then variable name)")
print("(this printed table is a selected excerpt -- predictor_diagnostic_df itself carries")
print(" every column listed in this section's header, e.g. structural_nan/fdr_sig/")
print(" is_representative/decision_question, not shown inline below)")
print()
# Share-safe display copy: cs_events/min_any_cell are reused
# directly from A2.8's sparse_df raw values -- same small-cell risk as A2.8
# itself (a numerator below the disclosure threshold), suppressed here on
# the same convention. predictor_diagnostic_df keeps true values for any
# downstream use.
#
# cs_events must be suppressed on both the within-CS-group complement AND
# the cross-group total-positive complement A1's Section A6 separately
# reports. This table does not display min_vaginal_cell (it
# is not in _display_cols below), but a LARGE, unsuppressed cs_events shown
# here can still combine with A1's total to recover a small vaginal
# complement even though this table never shows that number itself -- the
# disclosure risk does not require both numbers to live in the same table.
# Reuses share_safe.suppress_binary_target_display() via the internal-only
# _min_vaginal_cell/_N_analyzed/_sparse_type columns (dropped from
# _display_cols -- same "raw value kept internally, excluded from any
# displayed table" convention already used elsewhere in this notebook).
_pdd_display = predictor_diagnostic_df.copy()
_cs_events_fixed = []
for _idx, _row in predictor_diagnostic_df.iterrows():
    if (_row["_sparse_type"] == "binary" and isinstance(_row["cs_events"], str)
            and "/" in _row["cs_events"] and _row["_min_vaginal_cell"] is not None):
        _cs_n, _cs_d = (int(x) for x in _row["cs_events"].split("=")[-1].split("/"))
        _vag_n = int(_row["_min_vaginal_cell"])
        _vag_d = int(_row["_N_analyzed"]) - _cs_d
        _, _cd = share_safe.suppress_binary_target_display(
            _vag_n, _cs_n, _vag_d, _cs_d, enabled=SHARE_SAFE_MODE
        )
        _cs_events_fixed.append(_cd if isinstance(_cd, str) else f"{_cd}/{_cs_d}")
    else:
        _cs_events_fixed.append(_suppress_cs_events_label(_row["cs_events"]))
_pdd_display["cs_events"] = _cs_events_fixed
_pdd_display["min_any_cell"] = _pdd_display["min_any_cell"].apply(
    lambda n: share_safe.safe_count(n, enabled=SHARE_SAFE_MODE)
)
_display_cols = ["variable","predictor_classification","earliest_entry_stage","measurement_horizon",
                 "modeling_clearance","missing_%","cs_events","min_any_cell",
                 "separation_risk","too_sparse","effect_size","fdr_q_display","redundancy_group","human_decision_needed"]
print("Summary by earliest-entry stage:")
print(predictor_diagnostic_df["earliest_entry_stage"].value_counts().sort_index().to_string())
print()
print("Summary by modeling_clearance:")
print(predictor_diagnostic_df["modeling_clearance"].value_counts().to_string())
print()
_pdd_attention_mask = (
    (predictor_diagnostic_df["missing_%"] > 30)
    | predictor_diagnostic_df["separation_risk"]
    | predictor_diagnostic_df["too_sparse"]
    | (predictor_diagnostic_df["redundancy_group"] != "—")
    | (predictor_diagnostic_df["modeling_clearance"] != "cleared")
)
_pdd_attention = _pdd_display[_pdd_attention_mask]
print(f"Variables requiring special attention (high missing_%, separation, too sparse, "
      f"redundancy-group membership, or non-cleared modeling_clearance): {len(_pdd_attention)} "
      f"of {len(predictor_diagnostic_df)}")
if len(_pdd_attention):
    print(_pdd_attention[_display_cols].to_string(index=False))
else:
    print("  (none)")
print()
print("The full predictor_diagnostic_df table (all primary predictors, every column) "
      "remains available in memory.")
print()
print(f"Separation risk : {predictor_diagnostic_df['separation_risk'].sum()} variables "
      f"(descriptive only -- see A2.13; not auto-excluded from any candidate list here)")
print(f"Too sparse      : {predictor_diagnostic_df['too_sparse'].sum()} variables (descriptive only -- see A2.13)")
print(f"Human decision  : {predictor_diagnostic_df['human_decision_needed'].sum()} variables (see A2.14)")
print(f"FDR q<0.05      : {predictor_diagnostic_df['fdr_sig'].sum()} variables (descriptive only)")
_ko5_pending_clearance = predictor_diagnostic_df[
    predictor_diagnostic_df["modeling_clearance"] == "pending_timing_confirmation"
]["variable"].tolist()
print(f"Modeling clearance pending: {len(_ko5_pending_clearance)} variable(s) -- {_ko5_pending_clearance} -- "
      "measurement_horizon may say 'intrapartum' for these, but that is a timing fact, not a "
      "clearance claim; they remain blocked from every model until clinically confirmed (see A2.14/A2.15).")
""")

SB5_KEY_OBS = md("eda-b-s05-key-observations", """**Key observations — comprehensive predictor diagnostic table:**""")

SB5_KEY_OBS_CODE = code("eda-b-s05-key-observations-code", """
_ko5_sep = predictor_diagnostic_df[predictor_diagnostic_df["separation_risk"]]
_ko5_sparse = predictor_diagnostic_df[
    predictor_diagnostic_df["too_sparse"] & ~predictor_diagnostic_df["separation_risk"]
]
_ko5_nonrep = predictor_diagnostic_df[~predictor_diagnostic_df["is_representative"]]
print(f"- {len(predictor_diagnostic_df)} primary predictors summarized in one diagnostic "
      f"table; {int(predictor_diagnostic_df['human_decision_needed'].sum())} flagged for "
      f"human/clinical decision (see A2.14).")
if len(_ko5_sep):
    print(f"- {len(_ko5_sep)} variable(s) have complete separation (an empty "
          f"target-by-level cell): {_ko5_sep['variable'].tolist()} -- a hard modeling "
          f"constraint for unpenalized logistic regression specifically, not resolved here.")
if len(_ko5_sparse):
    print(f"- {len(_ko5_sparse)} variable(s) are too sparse (<5 in some target-by-level "
          f"cell) without being fully separated: {_ko5_sparse['variable'].tolist()}.")
if len(_ko5_nonrep):
    print(f"- {len(_ko5_nonrep)} variable(s) are the non-representative member of a "
          f"redundancy group -- flagged for consideration during Feature Selection, "
          f"not auto-excluded here.")
print("- No recommendation (include/exclude/discuss) is computed in this table; see the")
print("  A2.12 methodology note for why an indirect target-informed selection path was")
print("  removed from this section.")
""")


# ── Section A2.13 ───────────────────────────────────────────────────────────────
SB13_HEADER = md("eda-b-s13-header", """
## Section A2.13 — Variable-Readiness Diagnostics (Descriptive Only)

**Purpose:** Assign a transparent additive readiness score to each primary predictor
and report it as a complete, descriptive diagnostic table, grouped by each variable's
earliest cumulative-stage entry point. This is a screening/diagnostic tool, not a
feature-selection step.

> **IMPORTANT: This section does NOT select final model variables.** No Top-N/Core/
> Extended candidate list is produced. Every eligible variable is retained and shown.
> Final variable inclusion for any stage's model requires all of: outstanding clinical
> considerations resolved (Section A2.14), clinical approval of the final variable set,
> and modeling validation (cross-validation, convergence check, calibration assessment).

**Design principles:** no Top-N ranking is produced, since a ranked list computed over
only the Stage-2-only or Stage-3-only increment (small stage-specific increments) would
imply a level of selection this section does not perform -- every eligible variable in
every stage is retained instead. No stage receives a systematic scoring bonus or penalty
purely from its classification label. Whole-cohort information about
`target_intrapartum_cs` never determines a pre-model candidate set: the score is built
entirely from properties that do not depend on the observed target (predictor
eligibility, missingness/data availability, predictor-predictor redundancy).
Predictor-vs-target association evidence (`effect_size`, `fdr_sig`, from A2.9) and
target-by-level sparsity/separation (from A2.8) remain available as **descriptive/
warning columns only** -- useful context for clinical review -- but are not summed
into the score and do not filter any variable from the output table.

**What this checks:**
- Additive, target-independent readiness score per primary predictor (transparent,
  explainable), reported for every eligible variable, grouped by earliest cumulative
  prediction-stage entry (Stage 1 / Stage 2 / Stage 3)
- Separation-risk and too-sparse status shown as warning flags on every row (not used
  to exclude)

**What this does NOT do:**
- No Top-N truncation of any kind, and specifically no ranked list over just the
  Stage-2-only or Stage-3-only increment
- Scoring weights are NOT changed here — see `SCORING_WEIGHTS` in the EDA setup cell
- Statistical tests are NOT changed — the descriptive columns use outputs from A2.7/A2.8/A2.9
- Variables are NOT added to or removed from PRIMARY_COLS by this section
- Whole-cohort target information does NOT rank, include, or exclude any variable here

**Score components** (weights from `SCORING_WEIGHTS`; all target-independent):
- `s_clinical` = CLINICAL_TIER × 3.0
- `s_miss`     = -0.4 × (missing% / 10). For structural-NaN columns with a confirmed
  subgroup-applicability gate (`STRUCTURAL_SUBGROUP_GATES`), missing% here is the
  genuine within-applicable-subgroup rate, not the (inflated) full-cohort rate;
  deterministic structural non-applicability itself is never penalized. For a
  structural column with no confirmed gate, the full-cohort missing% is used as-is
- `s_redund`   = -2.5 if non-representative member of a redundancy group

**Displayed but NOT scored (descriptive/warning only):**
- `effect_size` / `fdr_sig` — predictor-vs-target association (A2.9)
- `too_sparse` / `separation_risk` — target-by-level cell sparsity (A2.8)

**Output:** one complete readiness diagnostic table (`score_df`), covering every
eligible variable, grouped by `earliest_entry_stage` and sorted by score within each
group for readability only -- not a candidate/recommendation ranking.
""")

SB13_SCORING = code("eda-b-s13-scoring", """
# ── Build score table from A2.7/A2.8/A2.9 outputs ───────────────────────────────
# assoc_df, miss_df, sparse_df, predictor_diagnostic_df built in earlier
# sections. Required upstream inputs: fail loudly (not a silent {} fallback)
# if this cell is ever executed out of sequence --
# a silent fallback would let A2.13 render a plausible-looking but wrong score
# table (every association/sparsity/missingness lookup would resolve to a
# default) instead of surfacing that a required prior section was skipped.

_assoc_lk  = assoc_df.set_index("variable")
_miss_lk   = miss_df.set_index("variable")
_sparse_lk = sparse_df.set_index("variable")

# Demoted members from redundancy groups. representative=None means the group
# is association-only evidence (no independently documented derivation/source
# relationship) -- no member is auto-demoted for that group; see A2.10d's
# surgical_detail_overlap for the current example.
_demoted = set()
for _gdef in REDUNDANCY_GROUPS.values():
    _present = [m for m in _gdef["members"] if m in PRIMARY_COLS]
    if len(_present) >= 2 and _gdef["representative"] is not None:
        _demoted.update(m for m in _present if m != _gdef["representative"])

w = SCORING_WEIGHTS
_score_rows = []

for col in PRIMARY_COLS:
    _tier    = CLINICAL_TIER.get(col, 0)
    _timing  = TIMING_MAP.get(col, "unclear")
    # modeling_clearance: orthogonal to _timing (measurement
    # horizon only) -- see MODELING_CLEARANCE_MAP's definition in Part 1.
    # Displayed alongside the score as descriptive/warning context; not part
    # of the score itself (matching this section's target-independence rule
    # for every other descriptive/warning column). Direct indexing (not
    # .get(col, "cleared")) is deliberate -- an unmapped variable must raise,
    # never be silently treated as cleared for modeling.
    _clearance = MODELING_CLEARANCE_MAP[col]

    # Association and target-by-level sparsity/separation -- DESCRIPTIVE /
    # WARNING columns only. Whole-cohort information
    # about target_intrapartum_cs must never determine a pre-model candidate
    # set; these are displayed for clinical-review context but are NOT summed
    # into the score and do NOT filter Core/Extended membership below.
    _eff = float(_assoc_lk.loc[col, "effect_size"]) if (
        col in _assoc_lk.index and pd.notna(_assoc_lk.loc[col, "effect_size"])
    ) else None
    _fdr_sig = bool(_assoc_lk.loc[col, "fdr_sig"]) if col in _assoc_lk.index else False
    _too_sparse = bool(_sparse_lk.loc[col, "too_sparse"]) if col in _sparse_lk.index else False
    _separation_risk = bool(_sparse_lk.loc[col, "separation_risk"]) if (
        col in _sparse_lk.index and "separation_risk" in _sparse_lk.columns
    ) else False

    # Missingness (target-independent: data availability only). A structural
    # column does not automatically get a zero missingness penalty -- that
    # would be too coarse, because a structural
    # column can still have genuine missing values within the subgroup where
    # it actually applies. Where a confirmed subgroup-applicability gate
    # exists (STRUCTURAL_SUBGROUP_GATES, checked via miss_df's
    # genuine_missing_pct_in_subgroup column, built in A2.7), the score uses
    # that genuine within-subgroup rate; deterministic structural
    # non-applicability itself is never penalized either way. For a
    # structural column with no confirmed gate, the full-cohort missing_%
    # is used as-is (conservative -- not assumed exempt).
    _full_miss_pct = float(_miss_lk.loc[col, "missing_%"]) if col in _miss_lk.index else 0.0
    _structural = col in STRUCTURAL_NAN_COLS
    _has_confirmed_gate = col in STRUCTURAL_SUBGROUP_GATES
    if _structural and _has_confirmed_gate and col in _miss_lk.index:
        _genuine_pct = _miss_lk.loc[col, "genuine_missing_pct_in_subgroup"]
        _miss_pct_for_score = float(_genuine_pct) if pd.notna(_genuine_pct) else 0.0
    else:
        _miss_pct_for_score = _full_miss_pct

    # Score components -- all target-independent. See A2.13 header for the
    # full target-independence rationale. No timing term: a variable's
    # cumulative-stage entry point (earliest_entry_stage, below) is reported
    # separately and must never bias the score itself (see A2.13 header,
    # "Timing-bonus removal").
    s_clin   = w["clinical_tier"]              * _tier
    s_miss   = w["missingness_penalty_per_10pct"] * (_miss_pct_for_score / 10.0)
    s_red    = w["redundancy_demotion"] if col in _demoted else 0.0
    total    = s_clin + s_miss + s_red

    _score_rows.append({
        "variable":          col,
        "predictor_classification": PRIMARY_COLS_CLASSIFICATION.get(col, "unknown"),
        "earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(col),
        "measurement_horizon": _timing,
        "modeling_clearance": _clearance,
        "clinical_tier":     _tier,
        "missing_%":         _full_miss_pct,
        "missing_%_used_in_score": round(_miss_pct_for_score, 1),
        "structural_nan":    _structural,
        "redundancy_demoted": col in _demoted,
        # "+ 0.0" after round() normalizes an exact-zero component to a
        # plain 0.0 -- display-only cosmetic fix for the negative-zero float
        # (e.g. round(-0.4 * 0.0, 2) == -0.0) that pure round() can otherwise
        # produce; the underlying score computation above is unaffected.
        "s_clinical":        round(s_clin, 2) + 0.0,
        "s_miss":            round(s_miss, 2) + 0.0,
        "s_redund":          round(s_red, 2) + 0.0,
        "score":             round(total, 2) + 0.0,
        # Descriptive/warning only -- NOT part of the score above.
        "effect_size":       _eff,
        "fdr_sig":           _fdr_sig,
        "too_sparse":        _too_sparse,
        "separation_risk":   _separation_risk,
    })

score_df = pd.DataFrame(_score_rows).sort_values(
    ["earliest_entry_stage", "score"], ascending=[True, False])

_show = ["variable","predictor_classification","earliest_entry_stage","measurement_horizon",
         "modeling_clearance","clinical_tier",
         "missing_%","missing_%_used_in_score","score",
         "effect_size","too_sparse","separation_risk","redundancy_demoted"]
print(f"Variable-readiness diagnostic summary — {len(score_df)} eligible variables "
      "(grouped by earliest entry stage):")
print(score_df.groupby("earliest_entry_stage").size().to_string())
print()
_score_warn_mask = (
    score_df["too_sparse"] | score_df["separation_risk"] | score_df["redundancy_demoted"]
)
_score_warn = score_df[_score_warn_mask]
print(f"Variables with a non-default warning (too_sparse, separation_risk, or "
      f"redundancy_demoted): {len(_score_warn)} of {len(score_df)}")
if len(_score_warn):
    print(_score_warn[_show].to_string(index=False))
else:
    print("  (none)")
print()
print("The full score_df table (every eligible variable, all columns) remains available")
print("in memory.")
print()
print("Score components (all target-independent): s_clinical + s_miss + s_redund = score")
print("(no timing term -- see A2.13 header, 'Timing-bonus removal')")
print("missing_% is the full-cohort figure (informational); missing_%_used_in_score is")
print("the genuine within-applicable-subgroup rate for structural columns with a")
print("confirmed subgroup gate, and the full-cohort rate otherwise -- see A2.7/A2.13 header.")
print("effect_size / too_sparse / separation_risk are shown for clinical-review context")
print("only -- they are NOT part of the score and do NOT filter any variable from this table.")
""")

SB13_FINAL_LISTS = code("eda-b-s13-final-lists", """
# ── Complete per-stage readiness diagnostics -- NOT a Top-N candidate list ──
# no ranked Top-N list is produced over the whole pool
# or over any single-stage increment. A Top-N ranking over the small
# Stage-3-only increment is not a meaningful selection and can be mistaken
# for feature selection -- every eligible variable is retained and reported
# instead, grouped by earliest_entry_stage.
_primary_df = score_df.copy()

# redundancy_demoted used to be a hard filter here,
# removing those variables from the table entirely before the per-stage
# "all retained" print below -- which made that print misleading (it claimed
# every variable was retained while some had already been silently dropped).
# No variable is filtered out of this diagnostic table for any reason
# (matching the same target-independence rule already applied to
# too_sparse/separation_risk): redundancy_demoted is now displayed as a
# warning column, exactly like too_sparse/separation_risk, so a human
# reviewer sees it without the notebook excluding on their behalf.
_diagnostic_pool = _primary_df.sort_values(
    ["earliest_entry_stage", "score", "variable"], ascending=[True, False, True])

_show2 = ["variable","predictor_classification","measurement_horizon","modeling_clearance",
          "clinical_tier","score",
          "effect_size","too_sparse","separation_risk","redundancy_demoted"]
_STAGE_LABELS = {
    1: "Stage 1 (pre-labor)",
    2: "Stage 2 (pre-labor + near-delivery) -- newly eligible at this stage",
    3: "Stage 3 (pre-labor + near-delivery + intrapartum) -- newly eligible at this stage",
}
for _stage in (1, 2, 3):
    _stage_df = _diagnostic_pool[_diagnostic_pool["earliest_entry_stage"] == _stage]
    print(f"{_STAGE_LABELS[_stage]}: {len(_stage_df)} variable(s), all shown below "
          f"(no Top-N truncation, no redundancy-demoted exclusion)")
    print(_stage_df[_show2].to_string(index=False))
    _stage_warn = _stage_df[_stage_df["too_sparse"] | _stage_df["separation_risk"]]["variable"].tolist()
    if _stage_warn:
        print(f"  WARNING: {len(_stage_warn)} variable(s) have a target-by-level sparsity/"
              f"separation warning and require explicit clinical/modeling review before use: "
              f"{_stage_warn}")
    _stage_demoted = _stage_df[_stage_df["redundancy_demoted"]]["variable"].tolist()
    if _stage_demoted:
        print(f"  WARNING: {len(_stage_demoted)} variable(s) are redundancy-demoted "
              f"(predictor-predictor relationship, not target-derived) and require explicit "
              f"review before joint use with their redundancy-group representative -- see "
              f"A2.10d for the redundancy-group review: {_stage_demoted}")
    print()

_n_demoted = int(_primary_df["redundancy_demoted"].sum())
print(f"{_n_demoted} of {len(_primary_df)} variables above carry a redundancy_demoted "
      f"warning; none are excluded from this table (see A2.10d for the redundancy-group "
      f"review).")
print()
print("These are descriptive readiness diagnostics only -- they do NOT select final model")
print("variables for any stage. Final selection requires clinical review (Section A2.14),")
print("clinical approval of the final variable set, and modeling validation.")
""")

SB13_STAGE_ONLY_PLOT_HEADER = md("eda-b-s13-stage-only-plot-header", """
**Compact Stage 2-only / Stage 3-only summary:** the tables
above already group every variable by `earliest_entry_stage`, but Stage 2 and
Stage 3 additions are each individually small groups (exact current counts are
shown live in each panel's title below, not hardcoded here) that can be easy
to overlook inside this notebook's larger paginated distribution plots (Section A2.4),
which mix every stage together. The compact chart below isolates just these two
groups so their readiness scores are visible at a glance, without paging through
every Stage-1 variable to find them.
""")

SB13_STAGE_ONLY_PLOT = code("eda-b-s13-stage-only-plot", """
_stage2_only_df = _diagnostic_pool[_diagnostic_pool["earliest_entry_stage"] == 2]
_stage3_only_df = _diagnostic_pool[_diagnostic_pool["earliest_entry_stage"] == 3]

if len(_stage2_only_df) == 0 and len(_stage3_only_df) == 0:
    print("No Stage 2-only or Stage 3-only variables in the current PRIMARY_COLS -- "
          "compact summary skipped.")
else:
    _max_levels = max(len(_stage2_only_df), len(_stage3_only_df), 1)
    fig, axes = plt.subplots(1, 2, figsize=(13, max(4.5, 0.55 * _max_levels + 1.8)),
                              layout="constrained")
    for ax, _df, _label in [
        (axes[0], _stage2_only_df, "Stage 2-only (secondary_near_delivery_predictor)"),
        (axes[1], _stage3_only_df, "Stage 3-only (intrapartum_predictor_exclude_from_prelabor_model)"),
    ]:
        if len(_df) == 0:
            ax.set_visible(False)
            continue
        _plot_df = _df.sort_values("score", ascending=True)
        _colors = ["#c0392b" if d else "#2980b9" for d in _plot_df["redundancy_demoted"]]
        ax.barh(_plot_df["variable"], _plot_df["score"], color=_colors)
        ax.set_title(f"{_label}\\n(N={len(_df)} variable(s))", fontsize=12, pad=10)
        ax.set_xlabel("Readiness score (descriptive only)", fontsize=11)
        ax.tick_params(axis="y", labelsize=10.5)
        ax.tick_params(axis="x", labelsize=10)
    fig.suptitle("Stage 2-only / Stage 3-only variables -- readiness score at a glance "
                 "(red bar = redundancy_demoted warning)", fontsize=14)
    plt.show()
    print(f"Stage 2-only: {len(_stage2_only_df)} variable(s) -- {sorted(_stage2_only_df['variable'].tolist())}")
    print(f"Stage 3-only: {len(_stage3_only_df)} variable(s) -- {sorted(_stage3_only_df['variable'].tolist())}")
    print("This chart is descriptive only -- score does not select final model variables.")
""")

SB13_STAGE_ONLY_OUTCOME_HEADER = md("eda-b-s13-stage-only-outcome-header", """
**Stage 2-only / Stage 3-only outcome-stratified panels:** the
readiness-score chart above shows a single descriptive score per variable, not the
actual data. The panels below show real outcome-stratified summaries for each Stage
2-only and Stage 3-only variable, by type: binary variables get a vaginal-vs-CS
positivity rate (matching Section A2.4's format), numeric variables get a
median/IQR-by-outcome summary with a Mann-Whitney test, and categorical variables get
an outcome-stratified level breakdown (matching Section A2.4's format, with the same
small-cell suppression). These are **descriptive only** -- they perform no feature
selection, and (per the A2.14/A2.15 warnings) any variable currently marked
`pending_timing_confirmation` in `modeling_clearance` remains timing-open and not
cleared for modeling regardless of what is shown here.
""")

SB13_STAGE_ONLY_OUTCOME_PANEL = code("eda-b-s13-stage-only-outcome-panel", """
_stage_only_vars = (
    [(v, 2) for v in sorted(_stage2_only_df["variable"])]
    + [(v, 3) for v in sorted(_stage3_only_df["variable"])]
)
if not _stage_only_vars:
    print("No Stage 2-only or Stage 3-only variables -- outcome panels skipped.")
else:
    _g0_so = df_primary[df_primary[TARGET_COL] == 0]
    _g1_so = df_primary[df_primary[TARGET_COL] == 1]
    for _col, _stage in _stage_only_vars:
        if _col not in df_primary.columns:
            continue
        _vtype = infer_var_type(df_primary[_col])
        print(f"[{_col}]  (Stage {_stage}-only, type={_vtype})")
        if _vtype == "binary":
            _sub = df_primary[[_col, TARGET_COL]].dropna(subset=[_col])
            _g0s, _g1s = _sub[_sub[TARGET_COL] == 0], _sub[_sub[TARGET_COL] == 1]
            _n_pos0 = int((_g0s[_col] == 1).sum())
            _n_pos1 = int((_g1s[_col] == 1).sum())
            # Centralized binary display protection -- shared with A2.4/A2.6/A2.8/A2.9.
            _vd, _cd = share_safe.suppress_binary_target_display(
                _n_pos0, _n_pos1, len(_g0s), len(_g1s), enabled=SHARE_SAFE_MODE
            )
            _r0 = f"{100*_n_pos0/len(_g0s):.1f}%" if not isinstance(_vd, str) and len(_g0s) else (_vd if isinstance(_vd, str) else "—")
            _r1 = f"{100*_n_pos1/len(_g1s):.1f}%" if not isinstance(_cd, str) and len(_g1s) else (_cd if isinstance(_cd, str) else "—")
            _res = chi2_or_fisher(_col, df_primary, TARGET_COL)
            print(f"  N={len(_sub)}, miss={df_primary[_col].isna().sum()} | "
                  f"vaginal={_r0} (N={len(_g0s)}) | CS={_r1} (N={len(_g1s)}) | "
                  f"{_res['test']}: p={fmt_pval(_res['p_value'])}")
        elif _vtype == "numeric":
            _sub = df_primary[[_col, TARGET_COL]].dropna(subset=[_col])
            _g0s, _g1s = _sub[_sub[TARGET_COL] == 0][_col], _sub[_sub[TARGET_COL] == 1][_col]
            _pv, _eff = mannwhitney_with_effect(_g0s, _g1s)
            print(f"  N={len(_sub)}, miss={df_primary[_col].isna().sum()} | "
                  f"vaginal: {fmt_median_iqr(_g0s)} | CS: {fmt_median_iqr(_g1s)} | "
                  f"Mann-Whitney p={fmt_pval(_pv)}, |r|={fmt_effect(_eff)}")
        elif _vtype == "categorical":
            _sub = df_primary[[_col, TARGET_COL]].dropna(subset=[_col])
            _g0s, _g1s = _sub[_sub[TARGET_COL] == 0], _sub[_sub[TARGET_COL] == 1]
            _vc = _sub[_col].value_counts()
            print(f"  N={len(_sub)}, miss={df_primary[_col].isna().sum()}, "
                  f"{_sub[_col].nunique()} levels:")
            # Reconstruction-aware combination -- same rationale as A2.4's
            # categorical loop: a combined bucket with only one member (or a
            # total still <5) discloses that one rare level's exact count,
            # either directly or by subtracting the shown levels from the
            # printed N above. Fold smallest-first until the combined bucket
            # is empty or safely >=5.
            _level_totals_so = {_lv: int((_sub[_col] == _lv).sum()) for _lv in _vc.index[:10]}
            _visible_so, _below_n_so, _below_k_so = share_safe.safe_combine_rare_levels(
                _level_totals_so, threshold=5
            )
            for _lv in _vc.index[:10]:
                if _lv not in _visible_so:
                    continue
                _n_tot = _visible_so[_lv]
                _n_vag = int((_g0s[_col] == _lv).sum())
                _n_cs = int((_g1s[_col] == _lv).sum())
                # Complement-aware WITHIN THIS LEVEL (_n_vag + _n_cs ==
                # _n_tot exactly): checking against len(_g0s)/len(_g1s) (the
                # whole column's group sizes) alone is not sufficient, since
                # `total={_n_tot}` is printed on the same line -- a
                # safe-looking large _n_vag next to a safe _n_tot still
                # discloses a small _n_cs by subtraction. Checking each
                # against _n_tot (same fix as A2.4's categorical loop) makes
                # both suppress together whenever either is a protected
                # small cell.
                _vag_d = share_safe.safe_count_with_complement(_n_vag, _n_tot, enabled=SHARE_SAFE_MODE)
                _cs_d = share_safe.safe_count_with_complement(_n_cs, _n_tot, enabled=SHARE_SAFE_MODE)
                # safe_count_with_complement() and safe_pct_disclosure() detect the
                # identical suppression condition independently -- composing both
                # unconditionally previously printed a redundant, duplicated
                # suppression phrase side by side (same pattern already fixed
                # in A2.4's categorical loop). Omit the percentage
                # phrase when the count itself is already a suppression marker.
                _vag_pct_so_txt = f" ({safe_pct_disclosure(_n_vag, len(_g0s))})" if isinstance(_vag_d, (int, float)) else ""
                _cs_pct_so_txt = f" ({safe_pct_disclosure(_n_cs, len(_g1s))})" if isinstance(_cs_d, (int, float)) else ""
                print(f"    {_lv}: total={_n_tot} | vaginal={_vag_d}{_vag_pct_so_txt} | "
                      f"CS={_cs_d}{_cs_pct_so_txt}")
            if _below_k_so:
                if _below_n_so is not None and _below_n_so >= 5:
                    print(f"    [{share_safe.format_combined_levels_note(_below_k_so, _below_n_so)}]")
                else:
                    print(f"    [{_below_k_so} smaller categor{'y' if _below_k_so == 1 else 'ies'} "
                          f"combined: too few total observations to display safely, suppressed]")
            if _sub[_col].nunique() > 10:
                print(f"    ... ({_sub[_col].nunique() - 10} more levels)")
        else:
            print(f"  (type={_vtype}: no dedicated panel format -- see A2.4/A2.9 for full coverage)")
        print()
    print("These panels are descriptive only and perform no feature selection.")
""")

SB13_STAGE_ONLY_OUTCOME_GRAPH_HEADER = md("eda-b-s13-stage-only-outcome-graph-header", """
**Stage 2-only / Stage 3-only outcome-stratified graphs:** the
text panels above report the same numbers this section now also plots. Binary
variables get a grouped vaginal-vs-CS positivity-rate bar chart (matching Section A2.4's
format); numeric variables get a boxplot by outcome (no patient-level point overlay);
categorical variables get grouped/normalized within-target-group % bars by level
(matching Section A2.4's format, top levels only, rare levels suppressed). Denominators
(N per group) are shown in each panel title where safe. The same small-cell and
complementary-cell suppression rules used throughout this notebook (`share_safe`)
apply here too -- a suppressed cell renders as a **missing bar labeled "Suppressed"**,
never as a 0-height bar and never as a raw small count. A suppressed rate is unknown
to the reader, not 0%, and must never look identical to a genuine, unsuppressed 0%.
These graphs are **descriptive only**: they perform no feature selection, readiness
scoring, exclusion, or model-eligibility determination, and (per the A2.14/A2.15 warnings)
any variable currently marked `pending_timing_confirmation` in `modeling_clearance`
(Section A2.12/A2.13's live, dynamically-derived list -- never hardcoded here) remains
blocked from every model regardless of what is shown here. The
readiness-score chart earlier in this section remains a separate, purely descriptive
score summary -- it is not a substitute for these outcome-stratified graphs, and these
graphs are not a substitute for it.
""")

SB13_STAGE_ONLY_OUTCOME_GRAPH = code("eda-b-s13-stage-only-outcome-graph", """
# Shared suppression-annotation helper: a suppressed
# rate is UNKNOWN to the reader, not 0% -- it must never be encoded as a
# numeric zero bar height, which would be indistinguishable from a genuine,
# unsuppressed 0%. A suppressed cell is instead plotted as np.nan (no bar
# rendered by matplotlib for a NaN height) with an explicit 'Suppressed'
# text annotation at that position. Raw analytical counts/percentages
# (_pct0/_pct1/_vag_pct_so/_cs_pct_so, all from share_safe) are kept fully
# separate from these display-only plotted heights.
def _so_plot_value(display_value):
    return float(display_value) if isinstance(display_value, (int, float)) else np.nan


def _so_annotate_suppressed(ax, x, y=50, fontsize=9):
    ax.text(x, y, "Suppressed", ha="center", va="center", fontsize=fontsize,
            fontstyle="italic", color="firebrick",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))


if not _stage_only_vars:
    print("No Stage 2-only or Stage 3-only variables -- outcome graphs skipped.")
else:
    # Paginated (was one tall ~10-panel figure): 2 columns x up to 3 rows
    # (6/page) keeps each page report/slide-sized instead of an unreadably
    # long single figure.
    _PAGE_SIZE_SO = 6
    _NCOLS_SO = 2
    _so_pages = [_stage_only_vars[i:i + _PAGE_SIZE_SO] for i in range(0, len(_stage_only_vars), _PAGE_SIZE_SO)]
    _n_pages_so = len(_so_pages)
    for _pg_so_i, _page_vars_so in enumerate(_so_pages, start=1):
      _n_panels_so = len(_page_vars_so)
      _nrows_so = int(np.ceil(_n_panels_so / _NCOLS_SO))
      fig, axes = plt.subplots(_nrows_so, _NCOLS_SO, figsize=(6.5 * _NCOLS_SO, 4.6 * _nrows_so),
                                layout="constrained")
      axes = np.array(axes).reshape(-1)
      for _i_so, (_col, _stage) in enumerate(_page_vars_so):
        ax = axes[_i_so]
        if _col not in df_primary.columns:
            ax.set_visible(False)
            continue
        _vtype = infer_var_type(df_primary[_col])
        _sub = df_primary[[_col, TARGET_COL]].dropna(subset=[_col])
        _n_sub = len(_sub)
        _miss_n = int(df_primary[_col].isna().sum())
        # Direct indexing (not .get(_col, "cleared")) is deliberate -- see
        # MODELING_CLEARANCE_MAP's fail-loud coverage assertions in Part 1.
        _clearance_so = MODELING_CLEARANCE_MAP[_col]
        _pending_tag = "  [pending clearance]" if _clearance_so == "pending_timing_confirmation" else ""

        if _vtype == "binary":
            # Raw counts/percentages kept separate from the suppressed display
            # values plotted below (share_safe convention used throughout).
            _g0s = _sub[_sub[TARGET_COL] == 0]
            _g1s = _sub[_sub[TARGET_COL] == 1]
            _n_pos0 = int((_g0s[_col] == 1).sum())
            _n_pos1 = int((_g1s[_col] == 1).sum())
            _pct0 = share_safe.safe_pct_with_denominator(_n_pos0, len(_g0s), enabled=SHARE_SAFE_MODE)[0]
            _pct1 = share_safe.safe_pct_with_denominator(_n_pos1, len(_g1s), enabled=SHARE_SAFE_MODE)[0]
            _plot0 = _so_plot_value(_pct0)
            _plot1 = _so_plot_value(_pct1)
            ax.bar([0, 1], [_plot0, _plot1], width=0.5, color=[C0, C1])
            for _xpos, _pv in [(0, _plot0), (1, _plot1)]:
                if np.isnan(_pv):
                    _so_annotate_suppressed(ax, _xpos)
            ax.set_ylim(0, 100)
            ax.set_xticks([0, 1])
            ax.set_xticklabels([f"Vaginal\\n(N={len(_g0s)})", f"CS\\n(N={len(_g1s)})"], fontsize=10)
            ax.tick_params(axis="y", labelsize=9.5)
            ax.set_ylabel("Positivity rate (%)", fontsize=10.5)
            ax.set_title(f"{_col} [Stage {_stage}]{_pending_tag}\\n"
                         f"binary, N={_n_sub}, miss={_miss_n}", fontsize=11, pad=8)

        elif _vtype == "numeric":
            # Boxplot by outcome only -- no patient-level point overlay.
            # showfliers=False: sns.boxplot's default
            # showfliers=True renders individual outlier points as markers,
            # which is itself a patient-level point overlay -- exactly what
            # this panel documents that it does not have. No stripplot/
            # swarmplot/scatter layer is added either.
            _sub_p = _sub.copy()
            _sub_p[TARGET_COL] = _sub_p[TARGET_COL].astype(str)
            sns.boxplot(data=_sub_p, x=TARGET_COL, y=_col, hue=TARGET_COL, ax=ax,
                        palette={"0": C0, "1": C1}, width=0.5, linewidth=1.1,
                        legend=False, showfliers=False)
            ax.set_xlabel("0=Vaginal  1=CS", fontsize=10.5)
            ax.set_ylabel("")
            ax.tick_params(labelsize=9.5)
            ax.set_title(f"{_col} [Stage {_stage}]{_pending_tag}\\n"
                         f"numeric, N={_n_sub}, miss={_miss_n}", fontsize=11, pad=8)

        elif _vtype == "categorical":
            _g0s = _sub[_sub[TARGET_COL] == 0]
            _g1s = _sub[_sub[TARGET_COL] == 1]
            _g0s_n, _g1s_n = len(_g0s), len(_g1s)
            _n_levels_so = _sub[_col].nunique()
            _top_levels_so = _sub[_col].value_counts().index[:6]
            _ct_so = pd.crosstab(_sub[_col], _sub[TARGET_COL]).reindex(_top_levels_so)
            _vag_counts_so = _ct_so.get(0, pd.Series(0, index=_ct_so.index))
            _cs_counts_so = _ct_so.get(1, pd.Series(0, index=_ct_so.index))
            # Checking each side's percentage only against the GLOBAL group
            # size (_g0s_n/_g1s_n) is not sufficient -- this notebook's own
            # text panel for these same Stage-2/3-only variables (immediately
            # above/below this graph) prints each level's exact total
            # (n_tot). A vaginal rate shown unsuppressed here, combined with
            # that already-visible exact total, discloses a small CS count by
            # subtraction even though neither this graph's own denominator
            # check nor the text panel's CS cell alone would flag it.
            # Checking against each level's own total (matching the text
            # panel) closes this.
            _n_tot_so = _vag_counts_so + _cs_counts_so
            _vag_pct_so = [
                share_safe.safe_pct_with_denominator(int(n), int(t), enabled=SHARE_SAFE_MODE)[0]
                for n, t in zip(_vag_counts_so, _n_tot_so)
            ]
            _cs_pct_so = [
                share_safe.safe_pct_with_denominator(int(n), int(t), enabled=SHARE_SAFE_MODE)[0]
                for n, t in zip(_cs_counts_so, _n_tot_so)
            ]
            # Suppressed (string) cells plot as np.nan (no bar rendered), with
            # an explicit 'Suppressed' annotation -- never a 0-height bar, and
            # never the raw small count/percentage.
            _vag_plot_so = [_so_plot_value(v) for v in _vag_pct_so]
            _cs_plot_so = [_so_plot_value(v) for v in _cs_pct_so]
            _x_so = range(len(_ct_so))
            _w_so = 0.35
            ax.bar([j - _w_so / 2 for j in _x_so], _vag_plot_so, _w_so, color=C0)
            ax.bar([j + _w_so / 2 for j in _x_so], _cs_plot_so, _w_so, color=C1)
            for _j_bar, (_vv, _cv) in enumerate(zip(_vag_plot_so, _cs_plot_so)):
                if np.isnan(_vv):
                    _so_annotate_suppressed(ax, _j_bar - _w_so / 2, fontsize=8)
                if np.isnan(_cv):
                    _so_annotate_suppressed(ax, _j_bar + _w_so / 2, fontsize=8)
            ax.set_ylim(0, 100)
            # A level suppressed on BOTH sides never shows its real category
            # name either (matching A2.4's categorical-plot rule) --
            # a bar next to a real rare-category label can still disclose
            # "this category exists" in a small cohort. Checked against the
            # raw display values (_vag_pct_so/_cs_pct_so), not the plotted
            # np.nan heights, so this classification is unambiguous.
            _xtick_labels_so = [
                str(_lv)[:16] if (isinstance(_vp, (int, float)) or isinstance(_cp, (int, float)))
                else "[suppressed]"
                for _lv, _vp, _cp in zip(_ct_so.index, _vag_pct_so, _cs_pct_so)
            ]
            ax.set_xticks(list(_x_so))
            ax.set_xticklabels(_xtick_labels_so, rotation=40, ha="right", fontsize=9.5)
            ax.tick_params(axis="y", labelsize=9.5)
            ax.set_ylabel("Within-target-group %", fontsize=10.5)
            _level_note = f", top {len(_top_levels_so)} of {_n_levels_so} levels" if _n_levels_so > 6 else ""
            ax.set_title(f"{_col} [Stage {_stage}]{_pending_tag}\\n"
                         f"categorical, N={_n_sub}, miss={_miss_n}{_level_note}", fontsize=11, pad=8)

        else:
            ax.axis("off")
            ax.set_title(f"{_col} [Stage {_stage}]\\n(type={_vtype}: no graph format -- see text panel above)",
                         fontsize=11)

      for _j_so in range(_n_panels_so, len(axes)):
          axes[_j_so].set_visible(False)

      fig.suptitle(f"Stage 2-only / Stage 3-only variables -- outcome-stratified graphs "
                   f"(page {_pg_so_i}/{_n_pages_so}) (descriptive only; small cells "
                   f"suppressed -- shown as a missing bar labeled 'Suppressed', never as 0%)",
                   fontsize=13.5)
      # Legend placed BELOW the grid (not at the top) so it never competes with
      # fig.suptitle for the same reserved space -- an earlier "outside upper
      # center" placement visually collided with the suptitle text.
      _legend_handles = [
          plt.Rectangle((0, 0), 1, 1, color=C0), plt.Rectangle((0, 0), 1, 1, color=C1),
      ]
      fig.legend(_legend_handles, ["Vaginal", "Intrapartum CS"], loc="outside lower center",
                 ncol=2, fontsize=10.5)
      plt.show()
    print("These graphs are descriptive only -- they perform no feature selection, readiness")
    print("scoring, exclusion, or model-eligibility determination. See modeling_clearance")
    print("(Section A2.12/A2.13) for which of these variables remain blocked from every model.")
    print("A suppressed rate is shown as a missing bar labeled 'Suppressed', never as 0%.")
""")


# ── Section A2.14 ───────────────────────────────────────────────────────────────
SB14_HEADER = md("eda-b-s14-header", """
## Section A2.14 — Clinical Assumptions and Modeling Considerations

**Purpose:** State the timing/eligibility assumptions underlying the primary
predictor pool, and the remaining clinical or modeling considerations relevant to
their use, so a reader can evaluate them directly.

**What this contains:**
- A brief summary of the timing/eligibility assumptions already reflected in the
  current predictor classification
- Remaining clinical and modeling considerations for a small number of
  sparse-event or overlapping-representation variables, each with its analytical
  consequence

**What this does NOT do:**
- This section does not itself reclassify any variable or run statistical tests

**Output:** Printed summary of the timing/eligibility assumptions and
remaining clinical/modeling considerations
""")

SB14_REGISTRY = code("eda-b-s14-registry", """
# ── Clinical assumption tracking ──────────────────────────────────────────
# Each entry: variable | data_issue | clinical_question | current_status
# current_status/decision are retained internally to drive the live-metadata
# guard and the resolved/open counts below; the printed narrative further
# down reframes this as assumptions and their analytical consequences rather
# than a decision-tracking log.

CLINICAL_DECISIONS = [
    {
        "variable": "S_P_CS",
        "data_issue": (
            "A small number of intrapartum-CS-group events among prior-CS "
            "patients (below the project's n<5 disclosure threshold); near "
            "the point of complete separation."
        ),
        "clinical_question": (
            "Prior-CS patients attempting a trial of labor rarely have an "
            "intrapartum CS in this cohort for a clinically expected reason. "
            "The variable is retained despite its small event count; how to "
            "handle that sparsity (sparse-event-aware / penalized estimation, "
            "cross-validated stability assessment) is a modeling-stage "
            "consideration, not decided by a full-dataset p-value."
        ),
        "current_status": "RESOLVED",
        "decision": (
            "Retained as a predictive candidate. Rarity / possible "
            "near-separation is a modeling-stage concern (sparse-event-aware "
            "handling / penalization, cross-validated stability assessment "
            "during modeling), not a reason for pre-model exclusion -- and is "
            "not decided by this variable's full-dataset univariate p-value. "
            "Final retention is determined during modeling."
        ),
    },
    {
        "variable": "cs_scar_endometriosis",
        "data_issue": (
            "Exactly 5 intrapartum-CS-group events -- at the sparsity threshold "
            "used elsewhere in this notebook. Effect size 0.134 (meaningful)."
        ),
        "clinical_question": (
            "This cohort-specific variable's meaningful effect size (0.134) "
            "is retained despite its borderline event sparsity; weighing that "
            "sparsity against its effect size during model specification "
            "(sparse-event-aware handling, cross-validated stability "
            "assessment) is a modeling-stage consideration, not decided by a "
            "full-dataset p-value."
        ),
        "current_status": "RESOLVED",
        "decision": (
            "Retained as a predictive candidate. Clinically specific "
            "to endometriosis and available before the outcome; sparse target-"
            "event counts are a modeling-stage concern, not a pre-model "
            "exclusion reason, and are not decided by this variable's "
            "full-dataset univariate p-value. Final retention is determined "
            "during modeling."
        ),
    },
    {
        "variable": "superficial_endometriosis",
        "data_issue": (
            "Not applicable -- this variable is clinically_redundant_exclude "
            "and is not in PRIMARY_COLS at any stage, so no "
            "target association or effect size for it is computed or shown "
            "anywhere in this notebook."
        ),
        "clinical_question": (
            "Whether superficial_endometriosis or peritoneal_endometriosis "
            "should represent this overlapping phenotype information in "
            "modeling, given the two variables' imperfect empirical "
            "agreement (~63.2%)."
        ),
        "current_status": "RESOLVED",
        "decision": (
            "Clinical experts selected peritoneal_endometriosis as the "
            "canonical modeled representation of this overlapping phenotype "
            "information, despite the two variables' imperfect empirical "
            "agreement (~63.2%) -- not because they were found statistically "
            "equivalent, and not a merge of the two columns. "
            "superficial_endometriosis is retained in the dataset for audit, "
            "cohort-rule derivation, and outcome-independent sensitivity "
            "analysis, but is excluded from every prediction stage and "
            "carries no modeling recommendation."
        ),
    },
    {
        "variable": "oligohydramnios",
        "data_issue": "6 intrapartum-CS-group events; effect 0.083.",
        "clinical_question": (
            "Whether this is consistently documented from antepartum "
            "ultrasound (pre-labor predictor) or can also be an intrapartum "
            "finding (potential leakage)."
        ),
        "current_status": "RESOLVED",
        "decision": (
            "Assessed by ultrasound during pregnancy, consistently with "
            "polyhydramnios, and therefore available before delivery. "
            "Classified predictor_allowed; included in the primary pre-labor pool."
        ),
    },
    {
        # Near-delivery horizon (secondary_near_delivery_predictor) is correct.
        "variable": "placental_abruption",
        "data_issue": "A small number of intrapartum-CS-group events, below the project's n<5 disclosure threshold (too_sparse). Effect 0.099. Classified secondary_near_delivery_predictor (Stage 2+).",
        "clinical_question": (
            "Whether this is always documented antepartum/pre-CS-decision, or "
            "can be coded from intrapartum/intraoperative findings."
        ),
        "current_status": "RESOLVED",
        "decision": (
            "Near-delivery horizon confirmed correct. Classified "
            "secondary_near_delivery_predictor; eligible from "
            "Stage 2 (pre-labor + near-delivery) onward."
        ),
    },
    {
        # This variable represents information available during labor and
        # before the cesarean decision. The actual modeling-relevant variable is the
        # combined intrapartum_fever_or_chorioamnionitis_bin indicator
        # (chorioamnionitis itself is source_or_text_audit_exclude, not a
        # modeling candidate at any stage) -- referenced directly here.
        "variable": "intrapartum_fever_or_chorioamnionitis_bin",
        "data_issue": (
            "Combines information from chorioamnionitis and intrapartum_fever. "
            "Classified intrapartum_predictor_exclude_from_prelabor_model "
            "(Stage 3 only)."
        ),
        "clinical_question": (
            "Whether this combined indicator is diagnosed/documented before "
            "the decision to perform a CS in every record."
        ),
        "current_status": "RESOLVED",
        "decision": (
            "Available during labor "
            "and before the cesarean decision -- intrapartum "
            "timing. Eligible only for Stage 3 (an intrapartum "
            "risk-update model, not an early/prelabor model), excluded from "
            "Stage 1 and Stage 2."
        ),
    },
    {
        # This variable represents information available during labor and
        # before the cesarean decision.
        "variable": "meconium_stained_amniotic_fluid",
        "data_issue": "Typically an intrapartum finding. Classified intrapartum_predictor_exclude_from_prelabor_model (Stage 3 only).",
        "clinical_question": (
            "Whether this is recorded before the CS decision in every case, "
            "or only documented at delivery."
        ),
        "current_status": "RESOLVED",
        "decision": (
            "Available during labor "
            "and before the cesarean decision -- intrapartum "
            "timing. Eligible only for Stage 3 (an intrapartum "
            "risk-update model, not an early/prelabor model), excluded from "
            "Stage 1 and Stage 2."
        ),
    },
    {
        "variable": "Hb_before_delivery",
        "data_issue": (
            "Timing is heterogeneous (pregnancy or day of admission) but "
            "confirmed never taken during labor."
        ),
        "clinical_question": (
            "Whether this is measured with consistent enough timing across "
            "the cohort to serve as a pre-labor predictor."
        ),
        "current_status": "RESOLVED",
        "decision": (
            "Always available before any intrapartum event, but timing is "
            "heterogeneous across the pregnancy/admission window. Classified "
            "secondary_near_delivery_predictor; analyzed separately from the "
            "primary pool for that reason, not on timing/leakage grounds."
        ),
    },
    {
        "variable": (
            "Hypertensive pregnancy disorder subcategories "
            "(pregnancy_related_hypertensive_disorder / any_PET / PIH / "
            "mild_PET / severe_PET / SIPET)"
        ),
        "data_issue": (
            "Each subcategory has a small number of intrapartum-CS-group "
            "events (below the project's n<5 disclosure threshold); all are "
            "sparse individually."
        ),
        "clinical_question": (
            "Whether these subcategories represent clinically distinct risk "
            "profiles (supporting separate variables) or a shared underlying "
            "process (supporting a single composite indicator) is a clinical "
            "judgment this EDA does not resolve."
        ),
        "current_status": "RESOLVED",
        "decision": (
            "derived_hypertension_pih_pet_spectrum "
            "is a 3-level grouped/composite representation "
            "(no_hypertensive_disorder / pih_gestational_htn / preeclampsia_spectrum "
            "+ explicit missing/unresolved state), defined from predefined clinical/source "
            "semantics, not target association. The individual "
            "subcategory variables are retained ungrouped as well -- they carry "
            "independent clinical value (e.g. distinguishing PIH from preeclampsia "
            "severity) that the composite intentionally coarsens -- registered "
            "together in DERIVED_REDUNDANCY_GROUPS "
            "('hypertension_pih_pet_spectrum_representation', representative=None) "
            "so all members are flagged for review rather than one being "
            "auto-demoted. Sparse individual-subcategory event counts remain a "
            "modeling-stage (Modeling D) concern, not a pre-model exclusion reason."
        ),
    },
]

# ── Live-metadata guard ────────────────────────────────────────────────────
# CLINICAL_DECISIONS above is a hardcoded snapshot, not derived from live
# metadata at runtime. Unlike the classification-count validation gate in
# Part 1 (which hard-fails on drift), nothing previously tied a RESOLVED
# entry's claimed classification to the live variable_classification_minimal.csv,
# so this registry could silently go stale as the project evolves. This guard
# asserts that each RESOLVED entry's variable still exists and still carries
# the classification the resolution implies, using the same
# PENDING_TIMING_CONFIRMATION_COLS / INTRAPARTUM_PREDICTOR_EXCLUDE_COLS /
# SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS lists already built from live
# metadata in Part 1. Does not alter any clinical decision, status, or
# classification -- read-only cross-check only.
# chorioamnionitis/meconium_stained_amniotic_fluid/
# placental_abruption were removed from this dict when their CLINICAL_
# DECISIONS entries were OPEN (this RESOLVED-only guard skips non-RESOLVED
# entries, so no mapping was needed then).
# all three RESOLVED again -- re-registered below
# with their live-metadata expectations, meconium_stained_amniotic_fluid and
# intrapartum_fever_or_chorioamnionitis_bin at intrapartum_predictor_exclude_
# from_prelabor_model (Stage 3 only) and placental_abruption at
# secondary_near_delivery_predictor (Stage 2+, corrected same day -- its
# near-delivery horizon was already correct).
_RESOLVED_EXPECTED_GROUP = {
    "oligohydramnios": (
        "predictor_allowed",
        PREDICTOR_ALLOWED_COLS,
    ),
    "S_P_CS": (
        "predictor_allowed",
        PREDICTOR_ALLOWED_COLS,
    ),
    "cs_scar_endometriosis": (
        "predictor_allowed",
        PREDICTOR_ALLOWED_COLS,
    ),
    "Hb_before_delivery": (
        "secondary_near_delivery_predictor",
        SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS,
    ),
    "placental_abruption": (
        "secondary_near_delivery_predictor",
        SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS,
    ),
    "meconium_stained_amniotic_fluid": (
        "intrapartum_predictor_exclude_from_prelabor_model",
        INTRAPARTUM_PREDICTOR_EXCLUDE_COLS,
    ),
    "intrapartum_fever_or_chorioamnionitis_bin": (
        "intrapartum_predictor_exclude_from_prelabor_model",
        INTRAPARTUM_PREDICTOR_EXCLUDE_COLS,
    ),
}
_registry_guard_errors = []
for _d in CLINICAL_DECISIONS:
    if _d["current_status"] != "RESOLVED":
        continue
    _var = _d["variable"]
    if _var not in _RESOLVED_EXPECTED_GROUP:
        continue  # no live-metadata mapping registered for this RESOLVED entry
    _expected_label, _expected_cols = _RESOLVED_EXPECTED_GROUP[_var]
    if _var not in df.columns:
        _registry_guard_errors.append(
            f"{_var}: RESOLVED entry references a variable no "
            "longer present in the current dataset"
        )
    elif _var not in _expected_cols:
        _registry_guard_errors.append(
            f"{_var}: RESOLVED entry expects classification "
            f"'{_expected_label}', but the live classification CSV no longer "
            "places it there -- entry may be stale and requires review"
        )
if _registry_guard_errors:
    raise ValueError(
        "Clinical assumption tracking (A2.14) is out of sync with live "
        "classification metadata: " + "; ".join(_registry_guard_errors)
    )
print(f"  Assumption tracking cross-checked against live classification "
      f"metadata: {len(_RESOLVED_EXPECTED_GROUP)} resolved entries checked, "
      "all consistent.")

# cross-check CLINICAL_DECISIONS' current_status against
# TIMING_REVIEW_STATUS (Part 1), the single canonical registry A2.12 reads
# directly. This is the guard that makes TIMING_REVIEW_STATUS/CLINICAL_
# DECISIONS "one canonical registry" in practice rather than two
# independently hand-maintained lists that can silently drift apart again --
# any mismatch here fails loudly instead of quietly going stale.
# Most CLINICAL_DECISIONS entries' "variable" field is itself the actual
# column name; the one combined-description entry (hypertensive disorder
# subcategories) is expanded to its constituent columns explicitly below.
_decision_entry_columns = {
    "Hypertensive pregnancy disorder subcategories "
    "(pregnancy_related_hypertensive_disorder / any_PET / PIH / "
    "mild_PET / severe_PET / SIPET)": [
        "pregnancy_related_hypertensive_disorder", "any_PET", "PIH",
        "mild_PET", "severe_PET", "SIPET",
    ],
}
_timing_sync_errors = []
_timing_checked_cols = set()
for _d in CLINICAL_DECISIONS:
    _cols_for_entry = _decision_entry_columns.get(_d["variable"], [_d["variable"]])
    for _c in _cols_for_entry:
        if _c not in TIMING_REVIEW_STATUS:
            continue  # not a variable TIMING_REVIEW_STATUS tracks (e.g. superficial_endometriosis)
        _timing_checked_cols.add(_c)
        if TIMING_REVIEW_STATUS[_c] != _d["current_status"]:
            _timing_sync_errors.append(
                f"{_c}: TIMING_REVIEW_STATUS says '{TIMING_REVIEW_STATUS[_c]}' but "
                f"CLINICAL_DECISIONS says '{_d['current_status']}'"
            )
_timing_missing_cols = set(TIMING_REVIEW_STATUS) - _timing_checked_cols
if _timing_missing_cols:
    _timing_sync_errors.append(
        f"TIMING_REVIEW_STATUS tracks column(s) with no matching CLINICAL_DECISIONS "
        f"entry: {sorted(_timing_missing_cols)}"
    )
if _timing_sync_errors:
    raise ValueError(
        "TIMING_REVIEW_STATUS (Part 1) and CLINICAL_DECISIONS (A2.14) have drifted "
        "out of sync -- update both together: " + "; ".join(_timing_sync_errors)
    )
print(f"  TIMING_REVIEW_STATUS cross-checked against CLINICAL_DECISIONS: "
      f"{len(_timing_checked_cols)} column(s) consistent.")

# Narrow, deterministic re-derivation of the one hardcoded CS-group event
# count among the resolved entries (oligohydramnios). Descriptive only -- a
# drifted narrative count does not itself indicate a classification or
# safety problem, so this warns rather than blocks.
if "oligohydramnios" in df.columns and TARGET_COL in df.columns:
    _oligo_cs_events = int((df.loc[df[TARGET_COL] == 1, "oligohydramnios"] == 1).sum())
    if _oligo_cs_events != 6:
        print(f"  WARNING: the oligohydramnios timing assumption above states 6 "
              f"CS-group events; live dataset currently shows {_oligo_cs_events}. "
              "Narrative text may need updating (not blocking).")
    else:
        print(f"  oligohydramnios event count re-derived from live data: "
              f"{_oligo_cs_events} CS-group events -- matches the assumption text above.")

# Same narrow, deterministic re-derivation for cs_scar_endometriosis's two
# hardcoded narrative numbers (event count + effect size) -- previously only
# oligohydramnios had this guard, leaving this entry's numbers unprotected
# against future cohort drift even though they are correct today. Warns
# (does not block) on drift, matching the oligohydramnios pattern; a small
# tolerance on the effect size avoids a hard failure on harmless display
# rounding.
if "cs_scar_endometriosis" in df.columns and TARGET_COL in df.columns:
    _cs_scar_cs_events = int((df.loc[df[TARGET_COL] == 1, "cs_scar_endometriosis"] == 1).sum())
    _cs_scar_drift = []
    if _cs_scar_cs_events != 5:
        _cs_scar_drift.append(
            f"CS-group events: narrative states 5, live dataset currently shows {_cs_scar_cs_events}"
        )
    _cs_scar_eff = None
    if "assoc_df" in dir():
        _cs_scar_row = assoc_df[assoc_df["variable"] == "cs_scar_endometriosis"]
        if len(_cs_scar_row) and pd.notna(_cs_scar_row.iloc[0]["effect_size"]):
            _cs_scar_eff = float(_cs_scar_row.iloc[0]["effect_size"])
            if abs(_cs_scar_eff - 0.134) > 0.01:  # tolerate harmless display rounding
                _cs_scar_drift.append(
                    f"effect size: narrative states ~0.134, live dataset currently shows {_cs_scar_eff:.3f}"
                )
    if _cs_scar_drift:
        print(f"  WARNING: the cs_scar_endometriosis timing assumption above may be stale -- "
              + "; ".join(_cs_scar_drift) + ". Narrative text may need updating (not blocking).")
    else:
        print(f"  cs_scar_endometriosis event count/effect size re-derived from live data: "
              f"{_cs_scar_cs_events} CS-group events"
              + (f", effect={_cs_scar_eff:.3f}" if _cs_scar_eff is not None else "")
              + " -- matches the assumption text above.")

print("=" * 70)
print("TIMING AND ELIGIBILITY ASSUMPTIONS")
print("=" * 70)
print()
for d in CLINICAL_DECISIONS:
    if d["current_status"] != "RESOLVED":
        continue
    print(f"[{d['variable']}]")
    print(f"  Assumption : {d['clinical_question']}")
    print(f"  Consequence: {d['decision']}")
    print()

print("=" * 70)
print("CLINICAL AND MODELING CONSIDERATIONS")
print("=" * 70)
print()
print("The following variables are retained in the primary predictor pool but")
print("warrant specific care during model specification -- none require a further")
print("clinical decision before EDA can proceed, and none are excluded here.")
print()
for d in CLINICAL_DECISIONS:
    if d["current_status"] != "OPEN":
        continue
    print(f"[{d['variable']}]")
    print(f"  Data context: {d['data_issue']}")
    print(f"  Consideration: {d['clinical_question']}")
    print()

print("Analytical consequence: coefficient estimates for the sparse-event variables")
print("(S_P_CS, cs_scar_endometriosis) would likely be unstable under ordinary")
print("unpenalized logistic regression; a penalized or bias-reduced (Firth) estimation")
print("approach is preferable if either is retained in a multivariable model (Section")
print("A2.8). The hypertensive-disorder subcategories overlap in representation; whether")
print("to model them separately or as a composite indicator should be assessed during")
print("model specification, informed by clinical input on the categories' distinctness.")
""")

SB14_PENDING_VARS = code("eda-b-s14-pending-vars", """
# Variables pending source/coding review would be excluded from statistical
# testing on source-ambiguity grounds; membership is read from the current
# variable classification, not a fixed list.
if not MANUAL_REVIEW_PENDING_COLS:
    print("No variables remain classified as pending source/coding review.")
else:
    print("Variables pending source/coding review:")
    print()
    for col in MANUAL_REVIEW_PENDING_COLS:
        if col not in df.columns:
            print(f"  {col}: NOT IN FILE")
            continue
        n_avail  = int(df[col].notna().sum())
        miss_pct = round(df[col].isna().mean() * 100, 1)
        # Small-cell disclosure guard: only report a top value if its count is
        # >=5 (project convention), else omit rather than expose it.
        top_vals = {str(k): int(v) for k, v in df[col].value_counts(dropna=True).head(3).items() if v >= 5}
        print(f"  {col}")
        print(f"    Available: {n_avail}/{len(df)} ({miss_pct}% missing)")
        print(f"    Top values (n>=5 only): {top_vals}")
        print(f"    Block reason: source ambiguity (prior surgery vs current CS findings)")
        print()
""")


# ── Section A2.15 ───────────────────────────────────────────────────────────────
SB15_HEADER = md("eda-b-s15-header", """
## Section A2.15 — EDA Conclusions and Modeling Handoff

**Purpose:** Summarize this EDA stage's findings and state the explicit
methodological requirements for any subsequent modeling stage.

**What this documents:**
- Cohort and target size; primary predictor coverage
- Major data-quality findings: missingness (including structural missingness),
  sparsity, and separation limitations
- Exploratory univariable association findings (explicitly labeled exploratory)
- Redundancy findings
- Variables unavailable at the intended pre-labor prediction time
- Modeling implications for any subsequent stage

**What this does NOT do:**
- No variables are removed or reclassified here
- Does not assign a final feature set: whole-cohort univariate screening in this
  notebook is not a feature-selection rule (see the modeling-implications
  statement below)

**Output:** Printed EDA findings summary and modeling handoff
""")

SB15_ACTION_LOG = code("eda-b-s15-action-log", """
# ── Findings summary (data-quality + redundancy) ──────────────────────────
# Purely descriptive aggregation of diagnostics already computed in A2.7-A2.11 --
# no owner/status/workflow fields; every finding here is a description of the
# data, not a proposed or recorded action.
print("=" * 70)
print("DATA-QUALITY AND REDUNDANCY FINDINGS SUMMARY")
print("=" * 70)
print()

if "miss_df" in dir():
    _high_miss = miss_df[miss_df["missing_%"] > 30]
    _struct_miss = miss_df[miss_df["structural_nan"]]
    print(f"Missingness: {len(_high_miss)} primary predictor(s) with >30% full-cohort "
          f"missingness; {len(_struct_miss)} carry a confirmed structural-missingness flag "
          f"(a deterministic non-applicability component outside their defined subgroup; "
          f"some may also retain genuine missingness within the applicable subgroup -- see "
          f"A2.7 for the separated quantities, not a blanket 'no data-quality gap' claim).")

if "sparse_df" in dir():
    _sep_n = int(sparse_df["separation_risk"].sum())
    _sparse_n = int(sparse_df["too_sparse"].sum())
    print(f"Sparsity/separation: {_sep_n} variable(s) show complete/quasi-complete "
          f"separation, {_sparse_n} are too sparse (<5 in some target-by-level cell) -- "
          f"both are fitting-stability diagnostics for ordinary unpenalized logistic "
          f"regression specifically (Section A2.8), not automatic exclusions.")

if "_high_corr_pairs" in dir() and _high_corr_pairs:
    print(f"Redundancy (numeric-numeric): {len(_high_corr_pairs)} pair(s) with "
          f"|Spearman rho|>=0.7: "
          f"{[(p['var1'], p['var2']) for p in _high_corr_pairs]}.")
if "_high_v_pairs" in dir() and _high_v_pairs:
    print(f"Redundancy (categorical-categorical): {len(_high_v_pairs)} pair(s) with "
          f"Cramer's V>=0.5: {[(p['var1'], p['var2']) for p in _high_v_pairs]}.")

if "outlier_df" in dir() and len(outlier_df):
    print(f"Outliers: {len(outlier_df)} numeric predictor(s) have IQR-flagged extreme "
          f"values (Section A2.11, target-blind screening); each is labeled "
          f"'extreme_value_review_item', not an error determination.")

print()
print(f"Leakage/post-outcome safety: {len(LEAKAGE_EXCLUDE_COLS)} leakage_exclude and "
      f"{len(INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS)} intrapartum_or_post_delivery_exclude "
      f"column(s) are confirmed absent from PRIMARY_COLS (enforced by the Section A2.2 scope gate).")
""")

SB15_CONCLUSIONS = code("eda-b-s15-conclusions", """
print("=" * 70)
print("EDA CONCLUSIONS AND MODELING HANDOFF")
print("=" * 70)
print()
print("COHORT STATUS: the current analysis uses the working")
print(f"cohort of N={len(df)}. 16 records with suspected superficial-only")
print("endometriosis are excluded from this cohort (full before/after")
print("reconciliation in EDA A Part 1, Section A4). Sensitivity cohorts excluding a")
print("broader or narrower group remain reconstructable from this dataset via the")
print("decision67_sensitivity_19group_excluded / _26group_excluded flag columns.")
print()
print(f"1. COHORT: N={len(df)}, Vaginal={n0} ({100*n0/len(df):.1f}%), "
      f"Intrapartum CS={n1} ({100*n1/len(df):.1f}%), Ratio={n0/n1:.1f}:1")
print()
print(f"2. PRIMARY PREDICTORS SCREENED: {len(PRIMARY_COLS)}")
print(f"   (from the unified 3-class predictor universe -- predictor_allowed "
      f"({len(PREDICTOR_ALLOWED_COLS)}) + secondary_near_delivery_predictor "
      f"({len(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)}) + "
      f"intrapartum_predictor_exclude_from_prelabor_model "
      f"({len(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)}) -- after zero-variance/all-missing drops; "
      f"see PRIMARY_COLS_CLASSIFICATION for the per-variable breakdown)")
print()

if "miss_df" in dir():
    _high = miss_df[miss_df["missing_%"] > 30]
    print(f"3. HIGH MISSINGNESS (>30% full-cohort, descriptive severity band): {len(_high)} "
          "variable(s) -- see Section A2.7 for the per-variable breakdown.")

if "sparse_df" in dir():
    _sep = sparse_df[sparse_df["separation_risk"]]
    print(f"\\n4. SEPARATION RISK (empty target-by-level cell -- unstable for ordinary "
          f"unpenalized logistic regression, not a universal exclusion): {len(_sep)} "
          "variable(s) -- see Section A2.8 for the per-variable breakdown.")
    _sp  = sparse_df[sparse_df["too_sparse"]]
    print(f"5. TOO SPARSE (minimum non-zero target-by-level cell is 1-4, excluding "
          f"separation-risk cases -- review before use): {len(_sp)} "
          "variable(s) -- see Section A2.8 for the per-variable breakdown.")

if "assoc_df" in dir():
    print(f"\\n6. EXPLORATORY UNIVARIABLE ASSOCIATIONS (BH-FDR q<0.05; screening evidence "
          f"only, NOT a feature-selection rule): {int(assoc_df['fdr_sig'].sum())}")
    for _, r in assoc_df[assoc_df["fdr_sig"]].iterrows():
        # Canonical display formatting -- full precision remains in assoc_df
        # itself; a nonzero q-value must never render as a literal "0.000".
        print(f"   {r['variable']}: effect={fmt_effect(r['effect_size'])}, q={fmt_pval(r['q_value_bh'])}")

if "_high_corr_pairs" in dir() or "_high_v_pairs" in dir():
    _n_num_redund = len(_high_corr_pairs) if "_high_corr_pairs" in dir() else 0
    _n_cat_redund = len(_high_v_pairs) if "_high_v_pairs" in dir() else 0
    print(f"\\n7. REDUNDANCY FINDINGS: {_n_num_redund} high numeric-numeric correlation "
          f"pair(s), {_n_cat_redund} high categorical-categorical association pair(s) "
          f"(Section A2.10) -- flagged for review, not auto-resolved.")

if "PRIMARY_COLS_CLASSIFICATION" in dir():
    print(f"\\n8. PRIMARY_COLS WORKING-FRAME COMPOSITION (after target-independent "
          f"zero-variance removal; horizon-specific modeling eligibility is decided "
          f"downstream, at the modeling boundary, not in A2 -- NOTE: the canonical "
          f"classification counts, e.g. predictor_allowed=60, are larger than the "
          f"working-frame counts below, which exclude the zero-variance columns dropped "
          f"from PRIMARY_COLS; see item 2 above):")
    _pc_counts = pd.Series(PRIMARY_COLS_CLASSIFICATION).value_counts()
    for _cls, _n in _pc_counts.items():
        print(f"   {_cls}: {_n}")
    print(f"   intrapartum_candidate_pending_timing_confirmation: "
          f"{len(PENDING_TIMING_CONFIRMATION_COLS)} (remains excluded -- timing unresolved by definition)")

_b15_total_decisions = len(CLINICAL_DECISIONS)
_b15_resolved_decisions = sum(1 for d in CLINICAL_DECISIONS if d["current_status"] == "RESOLVED")
_b15_open_decisions = _b15_total_decisions - _b15_resolved_decisions
# Explicit, dynamically-derived blocking statement for the timing-open variables --
# derived only from MODELING_CLEARANCE_MAP (Part 1), the single
# structured clearance registry (itself derived from CLINICAL_REVIEW_REGISTRY's
# blocks_modeling boolean), never an independently maintained name list, so
# this stays consistent with the actual blocked set after a future
# clinical decision.
_b15_timing_blocked = sorted(
    variable
    for variable, clearance in MODELING_CLEARANCE_MAP.items()
    if clearance == "pending_timing_confirmation"
)
print(f"\\n9. CLINICAL/SCIENTIFIC ASSUMPTIONS (Section A2.14): {_b15_total_decisions} total, "
      f"{_b15_resolved_decisions} resolved, {_b15_open_decisions} open")
print(f"   {len(_b15_timing_blocked)} modeling-blocking unresolved timing question(s); "
      f"{_b15_open_decisions} open clinical/human decision(s) remain in the A2.14 registry "
      "-- none currently block EDA completion or modeling clearance on timing grounds. "
      "This is a count of OPEN clinical/human decisions specifically, not a claim that "
      "zero downstream modeling considerations of any kind remain -- e.g. sparse-event/"
      "separation handling and representation/redundancy choices are documented "
      "elsewhere (A2.10d, A2.13) as non-blocking notes for Modeling D, independent of this "
      "count. Any OPEN decision listed below requires clinical/modeling judgment later "
      "but is not an unresolved EDA task:")
for _d in CLINICAL_DECISIONS:
    if _d["current_status"] == "OPEN":
        print(f"     - {_d['variable']}")
print()
print("9b. TIMING-OPEN VARIABLES -- NOT CLEARED FOR MODELING:")
if _b15_timing_blocked:
    print(f"    {_b15_timing_blocked}")
    print("    Per-delivery pre-CS-decision availability is NOT confirmed for these "
          "variables (see A2.14). They must NOT enter any model -- pre-labor, near-"
          "delivery, or intrapartum-stage -- until that timing is clinically confirmed "
          "on a per-delivery basis. Their current classification "
          "(secondary_near_delivery_predictor / intrapartum_predictor_exclude_from_"
          "prelabor_model) reflects a plausible-but-unconfirmed timing assumption, not "
          "a modeling clearance.")
else:
    print("    None currently OPEN.")
print()
print("10. MODELING IMPLICATIONS:")
implications = [
    "No whole-cohort univariable p-value, FDR result, effect size, or separation/"
    "sparsity flag from this notebook is a final feature-selection rule.",
    "Any target-dependent feature selection must occur within a training/resampling "
    "context (e.g. nested cross-validation), not on the whole cohort as done here.",
    "Imputation, missing-indicator construction, encoding, and scaling must be fit "
    "within training folds only, unless a transformation is deterministic and "
    "outcome-independent.",
    "Model evaluation should assess both discrimination and calibration, not "
    "discrimination alone.",
    "The target class imbalance (~6:1 vaginal-to-CS) must be addressed explicitly "
    "in the modeling approach (e.g. class weighting, appropriate resampling, or a "
    "threshold/metric strategy suited to imbalance), not ignored.",
    "Sparse-event variables identified in Section A2.8/A2.14 warrant a penalized or "
    "bias-reduced (Firth) estimation approach if retained, rather than ordinary "
    "unpenalized maximum likelihood.",
    "Reported estimates should include uncertainty (e.g. confidence or credible "
    "intervals) and stability/sensitivity analysis appropriate to a modestly sized "
    "cohort, not a single point estimate.",
    "Missing-data follow-up: " + " and ".join(sorted(APPLICABILITY_LINKED_COLS)) +
    " show potentially structural missingness patterns that remain unconfirmed. "
    "Until confirmed, they must be handled as ordinary missingness rather than "
    "structural-by-design.",
]
for i, p in enumerate(implications, 1):
    print(f"   {i}. {p}")
print()
print("=" * 70)
""")

SB15_CONSTANT_VARIABLE_VALIDATION = code("eda-b-s15-constant-variable-validation", """
print("=" * 70)
print("FINAL CONSTANT / NEAR-ZERO-VARIANCE VALIDATION")
print("=" * 70)
_val_errors = []

# 1. Zero-variance predictor_allowed (Stage 1) set -- validated STRUCTURALLY
#    by cross-checking against Part 1's independently-computed drop set
#    (_zero_var, from a2_part1_setup_scope.py's SB2_SCOPE cell), rather
#    than against a hardcoded variable-name set. A supervisor reclassifying
#    a variable, or the cohort gaining/losing a zero-variance column, must
#    never fail this check on its own; only genuine disagreement between
#    Part 1 and Part 5 about which columns are zero-variance should fail it
#    (e.g. one of the two accidentally computing against a different
#    dataframe). Current zero-variance predictor_allowed members are printed
#    below for descriptive/audit visibility only.
_actual_zv_predictors = {
    c for c in PREDICTOR_ALLOWED_COLS
    if c in df.columns and is_true_zero_variance_for_exclusion(df[c])
}
_part1_zv_stage1 = set(_zero_var) & set(STAGE_1_COLS)
print(f"1. Zero-variance predictor_allowed set (descriptive): {sorted(_actual_zv_predictors)}")
if _actual_zv_predictors != _part1_zv_stage1:
    _val_errors.append(
        f"Zero-variance predictor_allowed set computed here ({sorted(_actual_zv_predictors)}) "
        f"disagrees with Part 1's independently-computed drop set restricted to Stage 1 "
        f"({sorted(_part1_zv_stage1)}) -- Part 1 and Part 5 must agree on which columns "
        "are zero-variance."
    )

# 2. PRIMARY_COLS composition, validated structurally BY STAGE rather than
#    against hardcoded per-stage counts (which go stale on every approved
#    reclassification and give no signal about *why* they changed). Each
#    stage's empirically-retained set is checked for exact SET equality
#    against (canonical stage-only membership) minus (an unusable-column set
#    recomputed independently below, directly from EDA_ALL_CANDIDATE_COLS
#    and the live dataframe) -- this ties PRIMARY_COLS's actual contents
#    back to a freshly-derived expectation, not to Part 1's own _drop_set
#    object (comparing PRIMARY_COLS against the exact set used to build it
#    would be tautological and would always pass regardless of a real
#    construction bug). Any divergence here is therefore a real bug, not a
#    legitimate reclassification. Current per-stage counts are printed below
#    for descriptive/audit visibility only -- they are expected to change
#    whenever predictor_allowed / secondary_near_delivery_predictor /
#    intrapartum_predictor_exclude_from_prelabor_model membership changes,
#    and that is not a failure.
_stage1_set, _stage2_only_set, _stage3_only_set = (
    set(STAGE_1_COLS), set(STAGE_2_COLS) - set(STAGE_1_COLS), set(STAGE_3_COLS) - set(STAGE_2_COLS),
)
_stage1_retained = sorted(c for c in PRIMARY_COLS if c in _stage1_set)
_stage2_retained = sorted(c for c in PRIMARY_COLS if c in _stage2_only_set)
_stage3_retained = sorted(c for c in PRIMARY_COLS if c in _stage3_only_set)
print(f"2. PRIMARY_COLS composition by stage (descriptive): "
      f"Stage 1={len(_stage1_retained)}, Stage 2 additions={len(_stage2_retained)}, "
      f"Stage 3 additions={len(_stage3_retained)} -- total {len(PRIMARY_COLS)}")
# Independent recomputation: this does NOT read Part 1's _all_missing/
# _zero_var/_drop_set objects (reusing those directly would make this check
# tautological, since PRIMARY_COLS was itself built from _drop_set -- the
# comparison would then always pass by algebra, not by evidence). Instead,
# the unusable-column set is recomputed here from scratch, directly from the
# canonical Stage 1-3 candidate columns and the live dataframe, using the
# same shared, canonical zero-variance/all-missing test functions (reusing
# the definition of "zero variance" is correct; reusing the already-computed
# result is not). Any divergence from PRIMARY_COLS's actual composition
# below is therefore a genuine construction bug, not a legitimate
# reclassification.
_recomputed_all_missing = {
    c for c in EDA_ALL_CANDIDATE_COLS if c in df.columns and df[c].isna().all()
}
_recomputed_zero_var = {
    c for c in EDA_ALL_CANDIDATE_COLS
    if c in df.columns and c not in _recomputed_all_missing
    and is_true_zero_variance_for_exclusion(df[c])
}
_recomputed_drop_set = _recomputed_all_missing | _recomputed_zero_var
_expected_stage1_retained = _stage1_set - _recomputed_drop_set
_expected_stage2_retained = _stage2_only_set - _recomputed_drop_set
_expected_stage3_retained = _stage3_only_set - _recomputed_drop_set
if set(_stage1_retained) != _expected_stage1_retained:
    _val_errors.append(
        f"Stage 1 retained set is {_stage1_retained}, expected "
        f"{sorted(_expected_stage1_retained)} (canonical Stage 1 minus the independently "
        "recomputed unusable-column set)"
    )
if set(_stage2_retained) != _expected_stage2_retained:
    _val_errors.append(
        f"Stage 2 additions retained set is {_stage2_retained}, expected "
        f"{sorted(_expected_stage2_retained)} (canonical Stage 2 additions minus the "
        "independently recomputed unusable-column set)"
    )
if set(_stage3_retained) != _expected_stage3_retained:
    _val_errors.append(
        f"Stage 3 additions retained set is {_stage3_retained}, expected "
        f"{sorted(_expected_stage3_retained)} (canonical Stage 3 additions minus the "
        "independently recomputed unusable-column set)"
    )
# Explicit nesting safety net: empirical Stage 1 must always be a subset of
# canonical Stage 1 (true by construction, asserted here directly per the
# project's structural-robustness requirements rather than left implicit).
if not (set(_stage1_retained) <= _stage1_set):
    _val_errors.append("Empirical Stage 1 retained set is not a subset of canonical Stage 1.")

# 3. Neither trial-of-labor variable enters PRIMARY_COLS or the eligible pool.
_tol_vars = {"trial_of_labor", "trial_of_labor_corrected"}
_tol_in_primary = _tol_vars & set(PRIMARY_COLS)
print(f"3. trial_of_labor / trial_of_labor_corrected in PRIMARY_COLS: {sorted(_tol_in_primary)} (expected empty)")
if _tol_in_primary:
    _val_errors.append(f"trial-of-labor variable(s) present in PRIMARY_COLS: {_tol_in_primary}")

# 6. No zero-variance variable among PRIMARY_COLS (redundant with #1 but checked
#    directly against the live df_primary actually used for analysis).
_zv_in_primary = [c for c in PRIMARY_COLS if is_true_zero_variance_for_exclusion(df_primary[c])]
print(f"6. Zero-variance variables remaining in PRIMARY_COLS: {_zv_in_primary} (expected empty)")
if _zv_in_primary:
    _val_errors.append(f"Zero-variance variable(s) leaked into PRIMARY_COLS: {_zv_in_primary}")

# 7. Near-zero-variance flags (descriptive) do not remove anything from
#    PRIMARY_COLS. placental_abruption is NOT absent from PRIMARY_COLS -- it
#    is not in predictor_allowed but is still included via Stage 2
#    (secondary_near_delivery_predictor), same as every other Stage 2/3
#    member. The near-zero-variance SET across the full Stage-1-3
#    PRIMARY_COLS is NOT hardcoded here: it is computed live below (not
#    compared to a hardcoded set), including for the Stage 2/3 rare-event
#    variables documented in A2.14 (e.g. placental_abruption,
#    meconium_stained_amniotic_fluid,
#    intrapartum_fever_or_chorioamnionitis_bin).
_nzv_primary_live = sorted(
    c for c in PRIMARY_COLS if near_zero_variance_flag(df_primary[c])[0]
)
print(f"7. Near-zero-variance predictors across the full Stage 1-3 PRIMARY_COLS "
      f"(descriptive only, flag never excludes -- expected set intentionally not "
      f"hardcoded here, see comment above): {_nzv_primary_live}")

if _val_errors:
    raise AssertionError("Constant-variable validation failed: " + "; ".join(_val_errors))
print()
print("All constant / near-zero-variance validation checks PASSED.")
print("=" * 70)
""")


# ── Collect Part 5 cells ──────────────────────────────────────────────────────
EDA_B_PART5_CELLS = [
    SB5_HEADER, SB5_ELIGIBLE_TABLE, SB5_KEY_OBS, SB5_KEY_OBS_CODE,
    SB13_HEADER, SB13_SCORING, SB13_FINAL_LISTS,
    SB13_STAGE_ONLY_PLOT_HEADER, SB13_STAGE_ONLY_PLOT,
    SB13_STAGE_ONLY_OUTCOME_HEADER, SB13_STAGE_ONLY_OUTCOME_PANEL,
    SB13_STAGE_ONLY_OUTCOME_GRAPH_HEADER, SB13_STAGE_ONLY_OUTCOME_GRAPH,
    SB14_HEADER, SB14_REGISTRY, SB14_PENDING_VARS,
    SB15_HEADER, SB15_ACTION_LOG, SB15_CONCLUSIONS,
    SB15_CONSTANT_VARIABLE_VALIDATION,
]

if __name__ == "__main__":
    print(f"EDA A2 Part 5 cells defined: {len(EDA_B_PART5_CELLS)}")

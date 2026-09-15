#!/usr/bin/env python3
"""EDA A2 — Part 2: cell definitions (sections A2.7-A2.8, displayed order; this file's
own historical section IDs remain B3-B4 -- see the note below).

Sections:
  B3 (displayed as A2.7) — Missingness deep-dive (per methodology: thresholds + by-target pattern)
  B4 (displayed as A2.8) — Sparsity, event counts, and separation risk

Reorg note (2026-08-08): the former B5 (all eligible pre-delivery predictors --
comprehensive summary table) was relocated to a2_part5_readiness.py, where
it is now displayed as A2.12, positioned after A2.9's (formerly B10's) formal
association test so it can reuse that result instead of recomputing its own
quick association pass. This file's cell-ID prefixes ("eda-b-s03-...",
"eda-b-s04-...") are unchanged for execution stability; only the markdown
section numbers shown to the reader changed.

Depends on: df, df_primary, PRIMARY_COLS, PRIORITY_VARS, TARGET_COL, and all config
variables defined in a2_part1_setup_scope.py.
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


# ── Section A2.3 ────────────────────────────────────────────────────────────────
SB3_HEADER = md("eda-b-s03-header", """
## Section A2.7 — Missingness Deep-Dive

**Purpose:** Detailed missingness analysis for all primary predictors in the
cumulative Stage 1-3 A2 predictor-readiness working frame (`df_primary`) --
this includes Stage 2 (near-delivery) and Stage 3 (intrapartum) variables
alongside Stage 1 (pre-labor) ones, not pre-labor/pre-delivery variables only;
`earliest_entry_stage` distinguishes each variable's Stage 1/2/3 availability
throughout this section's tables. Includes by-target differential missingness
check and visual heatmap.

**What this checks:**
- Per-variable missingness count and %, with threshold bins
- Row-level missingness: how many delivery records have ≥1 / ≥5 / ≥10 missing among PRIMARY_COLS
- Differential missingness by target group (flagged if >5% difference between groups)
- Structural NaN variables (subgroup-specific by clinical design)

**What this does NOT do:**
- No imputation, no rows or columns are removed
- Does not determine missingness mechanism (MAR/MCAR/MNAR) — further analysis required

**Output:** Per-variable table with missingness severity bands + category summary +
row-level summary + differential missingness table + heatmap

**Missingness severity bands (descriptive, not prescriptive):**
The bands below are descriptive severity labels only, not a universal treatment
protocol. Actual handling of missing data is variable-type-specific and
model-specific, decided at the modeling stage, not assigned automatically from a
missingness percentage here:
- **≥70%** — severe: a variable at this level typically warrants close scrutiny before
  use as a predictor, but the appropriate response (exclusion, a missing-indicator,
  or another approach) depends on the variable's type and role, not on this band alone
- **40–70%** — moderate. Continuous variables are **not** automatically converted to an
  "unknown"/categorical bucket at this band — that is one possible approach among
  several and requires a case-by-case, variable-type-specific decision
- **<40%** — mild. Differential/patterned missingness may be *reported* descriptively,
  but the missingness mechanism (MAR/MCAR/MNAR) **cannot be identified or proven from
  observed data alone** — this table does not claim to test or determine mechanism
- **0%** — complete

**Important:** target-differential missingness (see the by-target cell below) may be
reported descriptively but must not drive pre-split feature selection or imputation
policy. Any imputation, missing-indicator construction, scaling, or encoding used for
a predictive model must be fitted within training folds only, unless the
transformation is deterministic and outcome-independent (e.g. the structural-fill
rule documented for the `endo_resection_*` family in preprocessing). No imputation is
performed in this notebook.

Structural-NaN variables are flagged separately: they carry a deterministic
non-applicability component outside their defined subgroup; that structural
component is expected by clinical design and is not itself a data-quality gap.
Some structural variables may also retain genuine missingness *within* the
applicable subgroup, which is reported separately below -- the flag alone does not
mean a structural variable's missingness is fully explained by non-applicability.
**Never impute structural non-applicability blindly.**
Where a confirmed subgroup-applicability gate exists (`STRUCTURAL_SUBGROUP_GATES`,
Part 1), the table below also reports the genuine missingness rate *within* the
applicable subgroup, separately from the full-cohort rate that structural
non-applicability otherwise inflates.
""")

SB3_MISS_TABLE = code("eda-b-s03-miss-table", """
# ── Per-variable missingness table ────────────────────────────────────────
# Structural NaN handling: for a
# STRUCTURAL_NAN_COLS member (e.g. endo_resection_* / endo_surgery_adhesiolysis,
# NaN outside endometriosis_surgery==1; endometrioma_size_clean/place_clean/
# laterality, NaN outside endometrioma==1), missing_% computed across the FULL
# cohort is dominated by clinically-expected non-applicability, not genuine
# missingness -- e.g. endo_resection_no_resection is "missing" for roughly
# half the full cohort (every row outside endometriosis_surgery==1) even
# though it is 0% missing within its applicable subgroup. The exact
# full-cohort percentage is cohort-size-dependent and is not hardcoded here
# -- see the live miss_df table below for the current figure.
# These columns get their own descriptive category (not scored by the ordinary
# severity bands); missing_n/% are still reported (informational), just not
# read as an ordinary-missingness severity signal.
#
# For the subset of structural columns with a
# CONFIRMED subgroup-applicability gate (STRUCTURAL_SUBGROUP_GATES, Part 1),
# this table also reports genuine within-applicable-subgroup missingness --
# not every NaN in a structural variable is equivalent: some structural
# variables can still have real missing values within the subgroup where they
# actually apply, and that genuine rate should not be silently hidden behind
# the inflated full-cohort percentage.
_miss_rows = []
for _col in PRIMARY_COLS:
    _miss_n   = int(df_primary[_col].isna().sum())
    _miss_pct = round(df_primary[_col].isna().mean() * 100, 1)
    _structural = _col in STRUCTURAL_NAN_COLS
    _pending_structural = _col in APPLICABILITY_LINKED_COLS
    if _structural:
        _cat = "structural_by_design"
    elif _pending_structural:
        # Empirically subgroup-patterned but NO code-enforced gate -- a
        # distinct third state, never counted as structural_by_design and
        # never granted a missingness-penalty exemption (see
        # structural_missingness_registry.py).
        _cat = APPLICABILITY_LINKED_NO_PREPROCESSING_MASK_LABEL
    elif _miss_pct >= 70:
        _cat = "severe_ge70pct"
    elif _miss_pct >= 40:
        _cat = "moderate_40_70pct"
    elif _miss_pct > 0:
        _cat = "mild_lt40pct"
    else:
        _cat = "complete"

    # Within-applicable-subgroup breakdown (only where a confirmed gate exists).
    _applic_n, _nonapplic_n, _genuine_miss_n, _genuine_miss_pct = None, None, None, None
    if _col in STRUCTURAL_SUBGROUP_GATES:
        _gate_col, _gate_val = STRUCTURAL_SUBGROUP_GATES[_col]
        if _gate_col in df.columns:
            _applic_mask   = df[_gate_col] == _gate_val
            _applic_n      = int(_applic_mask.sum())
            _nonapplic_n   = int(len(df) - _applic_n)
            _genuine_miss_n   = int(df.loc[_applic_mask, _col].isna().sum())
            _genuine_miss_pct = (
                round(100 * _genuine_miss_n / _applic_n, 1) if _applic_n else None
            )

    _miss_rows.append({
        "variable":       _col,
        "earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(_col),
        "missing_n":      _miss_n,
        "missing_%":      _miss_pct,
        "category":       _cat,
        "structural_nan": _structural,
        "potentially_structural_pending": _pending_structural,
        "applicable_subgroup_n":         _applic_n,
        "structurally_non_applicable_n": _nonapplic_n,
        "genuine_missing_n_in_subgroup":   _genuine_miss_n,
        "genuine_missing_pct_in_subgroup": _genuine_miss_pct,
        "note": (
            "structural — subgroup variable; missing_% above is full-cohort. "
            + (
                "Genuine within-subgroup missingness is reported in the "
                "genuine_missing_pct_in_subgroup column (confirmed gate)."
                if _col in STRUCTURAL_SUBGROUP_GATES else
                "No confirmed subgroup-applicability gate for this column in "
                "current preprocessing metadata; within-subgroup breakdown not "
                "computed (not guessed)."
            ) if _structural
            else "potentially structural — empirically subgroup-patterned in the "
                 "current cohort, but NO code-enforced preprocessing gate exists "
                 "(unlike structural_by_design). Not exempt from the missingness "
                 "severity bands' clinical interpretation; missing_% above is the "
                 "genuine full-cohort figure, not inflated by a confirmed gate."
            if _pending_structural
            else ""
        ),
    })

miss_df = pd.DataFrame(_miss_rows).sort_values("missing_%", ascending=False)

_miss_show = ["variable", "earliest_entry_stage", "missing_n", "missing_%", "category", "structural_nan",
              "potentially_structural_pending",
              "applicable_subgroup_n", "genuine_missing_pct_in_subgroup"]
print(f"Missingness summary — all primary predictors (N={len(df)}, {len(miss_df)} variables screened):")
print()
_high_miss = miss_df[(miss_df["missing_%"] > 30) & (~miss_df["structural_nan"])]
print(f"Variables with >30% missing, non-structural (N={len(_high_miss)}):")
if len(_high_miss):
    print(_high_miss[_miss_show].to_string(index=False))
else:
    print("  (none)")
print()
_gated = miss_df[miss_df["structural_nan"] | miss_df["potentially_structural_pending"]]
print(f"Structural / applicability-gated missingness (N={len(_gated)}):")
if len(_gated):
    print(_gated[["variable", "missing_n", "missing_%", "category",
                   "applicable_subgroup_n", "genuine_missing_pct_in_subgroup"]].to_string(index=False))
print()
print("genuine_missing_pct_in_subgroup is populated only for structural columns with a")
print("confirmed subgroup-applicability gate (see STRUCTURAL_SUBGROUP_GATES, Part 1);")
print("for the rest, missing_% above remains the only available (full-cohort) figure.")
print("The full miss_df table (all primary predictors) remains available in memory.")
print()

# Row-level missingness among PRIMARY_COLS
_row_miss_prim = df_primary[PRIMARY_COLS].isna().sum(axis=1)
_r1p = int((_row_miss_prim >= 1).sum())
_r5p = int((_row_miss_prim >= 5).sum())
_r10p = int((_row_miss_prim >= 10).sum())
print(f"Row-level missingness (among {len(PRIMARY_COLS)} PRIMARY_COLS, N={len(df_primary)}):")
print(f"  Rows with >= 1  missing : {_r1p:>3}  ({100*_r1p/len(df_primary):.1f}%)")
print(f"  Rows with >= 5  missing : {_r5p:>3}  ({100*_r5p/len(df_primary):.1f}%)")
print(f"  Rows with >= 10 missing : {_r10p:>3}  ({100*_r10p/len(df_primary):.1f}%)")
_n_structural_in_scope = sum(1 for c in PRIMARY_COLS if c in STRUCTURAL_NAN_COLS)
if _n_structural_in_scope:
    print(f"  Note: counted across all {len(PRIMARY_COLS)} PRIMARY_COLS, including "
          f"{_n_structural_in_scope} structural-NaN column(s) whose NaN is largely "
          "clinically-expected non-applicability, not genuine missingness -- these counts "
          "should not be read as 'this many rows have genuine missing predictor values'.")
print()

# Category summary
for _cat_name in ["structural_by_design", APPLICABILITY_LINKED_NO_PREPROCESSING_MASK_LABEL,
                   "severe_ge70pct", "moderate_40_70pct",
                   "mild_lt40pct", "complete"]:
    _sub = miss_df[miss_df["category"] == _cat_name]
    _struct_note = f"  ({_sub['structural_nan'].sum()} structural NaN)" if _sub['structural_nan'].sum() > 0 else ""
    print(f"  [{_cat_name}]: {len(_sub)} variables{_struct_note}")
""")

SB3_MISS_BY_TARGET = code("eda-b-s03-miss-by-target", """
# ── Missingness by target group ───────────────────────────────────────────
# An association between missingness and an observed variable/group (here,
# the target) is evidence against a simple MCAR interpretation for that
# variable -- it is compatible with MAR (missingness depending on an
# observed variable). It does NOT establish MNAR (missingness depending on
# the variable's own unobserved value): that cannot be demonstrated from the
# observed dataset alone.
# NOTE: This is a screening flag only; it does not prove a mechanism.
_mt_rows = []
_g0 = df_primary[df_primary[TARGET_COL] == 0]
_g1 = df_primary[df_primary[TARGET_COL] == 1]
for _col in PRIMARY_COLS:
    _m0 = round(_g0[_col].isna().mean() * 100, 1)
    _m1 = round(_g1[_col].isna().mean() * 100, 1)
    _diff = round(abs(_m1 - _m0), 1)
    _mt_rows.append({
        "variable":        _col,
        "miss_%_vaginal":  _m0,
        "miss_%_cs":       _m1,
        "abs_diff_%":      _diff,
        "flag_diff_>5pct": _diff > 5,
    })
mt = pd.DataFrame(_mt_rows).sort_values("abs_diff_%", ascending=False)

_flagged = mt[mt["flag_diff_>5pct"]]
print(f"Missingness by target group — differential flag (>5% difference):")
print(f"  {len(_flagged)} variable(s) with >5% missingness difference between vaginal and CS groups:")
if len(_flagged):
    print(_flagged.to_string(index=False))
else:
    print("  None — no differential missingness detected.")
print()
print("  Note: Differential missingness is a screening signal, not proof of mechanism.")
print("  Structural NaN variables will show differential missingness by design.")
""")

SB3_MISS_HEATMAP = code("eda-b-s03-miss-heatmap", """
# ── Missingness heatmap ───────────────────────────────────────────────────
_cols_with_miss = sorted(
    [c for c in PRIMARY_COLS if df_primary[c].isna().any()],
    key=lambda c: df_primary[c].isna().mean(),
    reverse=True,
)
if not _cols_with_miss:
    print("No missing values in primary predictors — heatmap skipped.")
else:
    _n_show = min(40, len(_cols_with_miss))
    _hm = df_primary[_cols_with_miss[:_n_show]].isna().astype(int)
    _fig_w = max(11, _n_show * 0.4)
    _fig_h = max(5, _n_show * 0.3)
    fig, ax = plt.subplots(figsize=(_fig_w, _fig_h), layout="constrained")
    sns.heatmap(_hm.T, cmap="Greys", cbar=False, ax=ax,
                xticklabels=False, yticklabels=_hm.columns.tolist())
    ax.set_xlabel(f"Delivery records (N={len(df_primary)}, rows anonymised)", fontsize=11.5)
    ax.set_title(
        f"Missingness heatmap — {len(_cols_with_miss)} primary predictors with missing values"
        + (f" (first {_n_show} shown)" if len(_cols_with_miss) > _n_show else ""),
        fontsize=13, pad=12,
    )
    ax.tick_params(axis="y", labelsize=9.5, rotation=0)
    plt.show()
    print("Black = missing | White = present | Sorted by missingness%")
    print("Structural NaN variables (subgroup design) will appear as solid black bands.")
""")

SB3_COMISSINGNESS = code("eda-b-s03-comissingness", """
# ── Co-missingness: which predictor pairs tend to be missing together ─────
# Descriptive only. Does NOT change missingness handling, imputation, or
# eligibility -- adds a diagnostic view on top of the existing per-variable
# missingness table above. Distinguishes structural (subgroup-by-design,
# e.g. endometrioma_size_clean is NaN whenever endometrioma==0) from
# ordinary missingness so a high co-missingness pair is not misread as an
# unexplained joint gap when it is simply the same structural subgroup rule
# acting on two variables at once.
_miss_cols_co = [c for c in PRIMARY_COLS if df_primary[c].isna().any()]
if len(_miss_cols_co) < 2:
    print("Fewer than 2 primary predictors have any missingness — co-missingness skipped.")
else:
    _miss_ind = df_primary[_miss_cols_co].isna().astype(int)
    _co_rows = []
    for i in range(len(_miss_cols_co)):
        for j in range(i + 1, len(_miss_cols_co)):
            c1, c2 = _miss_cols_co[i], _miss_cols_co[j]
            _both = int(((_miss_ind[c1] == 1) & (_miss_ind[c2] == 1)).sum())
            if _both == 0:
                continue
            _n1, _n2 = int(_miss_ind[c1].sum()), int(_miss_ind[c2].sum())
            _jaccard = _both / (_n1 + _n2 - _both) if (_n1 + _n2 - _both) > 0 else np.nan
            _struct = (c1 in STRUCTURAL_NAN_COLS) or (c2 in STRUCTURAL_NAN_COLS)
            # either_structural_nan=True only says at least ONE member is a
            # structural column -- it does NOT imply the pair shares a common
            # cause (e.g. one member could be endometrioma-gated and the other
            # could have no confirmed gate at all, or a different gate
            # entirely). shared_structural_gate is the stricter, separate
            # diagnostic: True only when BOTH members have a CONFIRMED gate
            # (STRUCTURAL_SUBGROUP_GATES, Part 1) AND that gate is identical
            # for both -- the only case where "they share the same documented
            # subgroup rule" is actually a justified claim.
            _gate1 = STRUCTURAL_SUBGROUP_GATES.get(c1)
            _gate2 = STRUCTURAL_SUBGROUP_GATES.get(c2)
            _shared_gate = (_gate1 is not None) and (_gate1 == _gate2)
            # Aggregate/structural metadata only (a gate column name + value,
            # e.g. "endometrioma==1") -- never a patient-level count -- shown
            # only when a shared gate is actually confirmed.
            _shared_gate_label = f"{_gate1[0]}=={_gate1[1]}" if _shared_gate else ""
            _co_rows.append({
                "var1": c1, "var2": c2,
                "n_both_missing": _both,
                "n1_missing": _n1, "n2_missing": _n2,
                "jaccard_overlap": round(_jaccard, 3),
                "either_structural_nan": _struct,
                "shared_structural_gate": _shared_gate,
                "shared_gate_label": _shared_gate_label,
            })
    if not _co_rows:
        print("No predictor pairs share any jointly-missing rows.")
    else:
        comiss_df = pd.DataFrame(_co_rows).sort_values("jaccard_overlap", ascending=False)
        _high_overlap = comiss_df[comiss_df["jaccard_overlap"] >= 0.5]
        print(f"Co-missingness pairs with jointly-missing rows: {len(comiss_df)}")
        print(f"High-overlap pairs (Jaccard >= 0.5, i.e. mostly missing together): "
              f"{len(_high_overlap)}")
        print(_high_overlap.to_string(index=False) if len(_high_overlap) else "  (none)")
        print()
        print("Full co-missingness table (top 20 by Jaccard overlap):")
        print(comiss_df.head(20).to_string(index=False))
        print()
        _n_shared_gate = int(comiss_df["shared_structural_gate"].sum())
        print(f"Pairs sharing a CONFIRMED structural gate (shared_structural_gate=True): "
              f"{_n_shared_gate}")
        print("Interpretation: shared_structural_gate=True means BOTH members have a")
        print("confirmed subgroup-applicability gate (STRUCTURAL_SUBGROUP_GATES) AND it is")
        print("the identical gate (see shared_gate_label, e.g. 'endometrioma==1') -- only for")
        print("these pairs is co-missingness actually explained by sharing the same")
        print("documented subgroup rule, not an unexplained joint data-collection gap.")
        print("either_structural_nan=True alone (without shared_structural_gate=True) means")
        print("only that AT LEAST ONE member is a structural column -- it does NOT establish")
        print("a common cause for the pair: the other member may have no confirmed gate at")
        print("all, or a different gate entirely, so their co-missingness remains unexplained")
        print("by this table. For non-structural and either-only pairs, a high Jaccard")
        print("overlap identifies a shared missingness pattern/process worth investigating --")
        print("it does not, by itself, establish MCAR, MAR, or MNAR for that pair. Correlated")
        print("missingness indicators can also arise from a shared data-collection process")
        print("(e.g. one form/panel not completed) that remains independent of the")
        print("underlying data values, which would still be consistent with MCAR for each")
        print("variable individually. The missingness mechanism cannot be established from")
        print("this table alone.")
""")

SB3_KEY_OBS = md("eda-b-s03-key-observations", """**Key observations — missingness:**""")

SB3_KEY_OBS_CODE = code("eda-b-s03-key-observations-code", """
_ko3_high = miss_df[(miss_df["missing_%"] >= 30) & (~miss_df["structural_nan"])]
_ko3_struct = miss_df[miss_df["structural_nan"]]
print(f"- {int((miss_df['missing_%'] == 0).sum())} of {len(miss_df)} primary predictors "
      f"are fully complete.")
print(f"- {len(_ko3_struct)} predictor(s) carry a structural_nan flag, indicating a "
      f"deterministic non-applicability component outside their defined subgroup; some "
      f"may also have genuine within-subgroup missingness (reported separately above).")
if len(_ko3_high):
    print(f"- {len(_ko3_high)} non-structural predictor(s) have >=30% missing "
          f"({_ko3_high.sort_values('missing_%', ascending=False)['variable'].tolist()[:6]}"
          f"{'...' if len(_ko3_high) > 6 else ''}) -- flag for missingness-mechanism "
          f"consideration before any imputation approach is chosen.")
if "comiss_df" in dir() and len(comiss_df):
    print(f"- {len(comiss_df)} predictor pair(s) share jointly-missing rows; "
          f"{int((comiss_df['jaccard_overlap'] >= 0.5).sum())} have Jaccard overlap "
          f">=0.5. As above, high co-missingness alone does not establish MCAR, MAR, or "
          f"MNAR for those pairs (a shared, value-independent data-collection process "
          f"can also produce correlated missingness) -- the practical handling decision "
          f"for these pairs is deferred to the later cleaning/modeling workflow under "
          f"acknowledged mechanism uncertainty, not resolved by this table.")
""")


# ── Section A2.4 ────────────────────────────────────────────────────────────────
SB4_HEADER = md("eda-b-s04-header", """
## Section A2.8 — Sparsity, Event Counts, and Separation Risk

**Purpose:** Quantify the availability of CS-group events for each binary and categorical
predictor. Low event counts are a fitting/instability concern for certain modeling
approaches, not a universal exclusion rule (see the methodology note below).

**What this checks:**
- Target-by-level cell counts for all binary and categorical PRIMARY_COLS
- `rare_flag`: any target-by-level cell < 10 observations
- `too_sparse`: minimum non-zero target-by-level cell is 1-4 (quasi-separation/instability
  risk); zero-cell cases are classified separately as `separation_risk`, so the two flags
  are mutually exclusive
- `separation_risk`: any target-by-level cell = 0 (complete/quasi-complete separation)

**What this does NOT do:**
- No variables are removed from PRIMARY_COLS here
- No statistical tests (event counts only)

**Methodological approach:** complete or quasi-complete separation is a
serious fitting/instability problem specifically for ordinary **unpenalized**
maximum-likelihood logistic regression (the coefficient can diverge or fail to
converge). It is **not** a universal statement that a flagged variable "cannot enter
logistic regression" under any approach — penalized regression (L1/L2/elastic-net),
Firth's bias-reduced logistic regression, and Bayesian approaches handle separation
differently and remain viable. Whole-cohort target-by-level sparsity/separation must
not be used as an automatic pre-model feature-exclusion rule applied before model
selection or resampling; this section reports diagnostics and warnings only.
Model-specific handling belongs to the modeling pipeline and, where it depends on the
target, must occur inside the appropriate training/resampling context (e.g. checked
per fold, not once on the whole cohort).

**Output:** Per-variable sparsity table + separation risk summary

**Note:** VBAC is expected to show complete separation in this cohort (a structural
consequence of the trial-of-labor cohort definition, not a data-quality issue).
""")

SB4_SPARSITY = code("eda-b-s04-sparsity", """
_sparse_rows = []
_g0 = df_primary[df_primary[TARGET_COL] == 0]
_g1 = df_primary[df_primary[TARGET_COL] == 1]

for _col in PRIMARY_COLS:
    _vtype = infer_var_type(df_primary[_col])
    _sub   = df_primary[[_col, TARGET_COL]].dropna(subset=[_col])
    _g1s   = _sub[_sub[TARGET_COL] == 1]
    _g0s   = _sub[_sub[TARGET_COL] == 0]

    _sep_risk  = False
    _too_sparse = False
    _rare_flag  = False
    _cs_events  = None
    _vaginal_events = None
    _min_cell = None
    _cs_events_label = None

    if _vtype == "binary":
        _n_pos1 = int((_g1s[_col] == 1).sum())
        _n_neg1 = len(_g1s) - _n_pos1
        _n_pos0 = int((_g0s[_col] == 1).sum())
        _n_neg0 = len(_g0s) - _n_pos0
        _cells  = [_n_pos1, _n_neg1, _n_pos0, _n_neg0]
        _cs_events = _n_pos1
        _vaginal_events = _n_pos0
        _min_cell = min(_cells)
        _cs_events_label = f"{_n_pos1}/{len(_g1s)}"
        _sep_risk   = any(c == 0 for c in _cells)
        _too_sparse = (not _sep_risk) and (_min_cell < 5)
        _rare_flag  = any(c < 10 for c in _cells)

    elif _vtype == "categorical":
        _levels = _sub[_col].dropna().unique()
        _level_cs = [int((_g1s[_col] == lv).sum()) for lv in _levels]
        _level_vag = [int((_g0s[_col] == lv).sum()) for lv in _levels]
        _level_tot= [int((_sub[_col]  == lv).sum()) for lv in _levels]
        _cs_events = min(_level_cs) if _level_cs else 0
        _vaginal_events = min(_level_vag) if _level_vag else 0
        _all_side_cells = _level_cs + _level_vag
        _min_cell = min(_all_side_cells) if _all_side_cells else 0
        _cs_events_label = f"min={_cs_events}/{len(_g1s)}"
        _sep_risk   = any(c == 0 for c in _all_side_cells)
        _too_sparse = (not _sep_risk) and (_min_cell < 5)
        _rare_flag  = any(c < 10 for c in _all_side_cells) or any(t < 10 for t in _level_tot)

    _sparse_rows.append({
        "variable":          _col,
        "earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(_col),
        "type":              _vtype,
        "N_analyzed":        len(_sub),
        "cs_events":         _cs_events_label if _cs_events_label else "—",
        "min_vaginal_cell":  _vaginal_events,
        "min_any_cell":      _min_cell,
        "separation_risk":   _sep_risk,
        "too_sparse":        _too_sparse,
        "rare_flag":         _rare_flag,
    })

sparse_df = pd.DataFrame(_sparse_rows)

# Share-safe display copy: this section's whole purpose is to
# surface small target-by-level cells, so the boolean flags
# (separation_risk/too_sparse/rare_flag) are always shown unconditionally --
# suppressing those would defeat the section's diagnostic purpose. But the
# EXACT raw counts (cs_events, min_vaginal_cell, min_any_cell) are
# exactly the kind of small, potentially patient-identifying count this
# notebook's share-safe convention exists to protect in a shared HTML export.
# sparse_df itself (with true raw values) is unchanged and remains the
# source A2.12/A2.13 read from downstream -- both only consume the boolean flags,
# never these raw count columns, so suppressing only the display copy here
# has no effect on any downstream computation.
def _suppress_cs_events_label(s):
    # Checking only the numerator is not sufficient -- a large unsuppressed
    # numerator still discloses a small complement by simple subtraction
    # the moment the denominator is visible (as it always is here, embedded
    # in the same "N/D" string). Both numerator and complement are checked.
    if not SHARE_SAFE_MODE or not isinstance(s, str) or s == "—":
        return s
    _tail = s.split("=")[-1]  # handles both "N/D" and "min=N/D"
    _numerator_str, _denom_str = _tail.split("/")
    _numerator, _denom = int(_numerator_str), int(_denom_str)
    _complement = _denom - _numerator
    if (0 < _numerator < 5) or (0 < _complement < 5):
        return "suppressed (n<5 in a cell)"
    return s

_sparse_display = sparse_df.copy()
# Centralized binary display protection: for a binary predictor,
# min_vaginal_cell (the vaginal-side positive event count) and cs_events (the
# CS-side event count) must be suppressed together, not independently -- a
# large, "safe-looking" min_vaginal_cell can otherwise be combined with A1's
# unstratified total-positive count to recover an independently-suppressed
# cs_events value. share_safe.suppress_binary_target_display() (the same
# function A2.4/A2.9 use) closes this by checking both sides together
# against BOTH the same-group and cross-group totals.
_min_vag_disp, _cs_events_disp = [], []
for _idx, _row in sparse_df.iterrows():
    if _row["type"] == "binary" and isinstance(_row["cs_events"], str) and "/" in _row["cs_events"]:
        _cs_n, _cs_d = (int(x) for x in _row["cs_events"].split("=")[-1].split("/"))
        _vag_n = int(_row["min_vaginal_cell"])
        # vaginal_group_n is not stored on sparse_df directly -- recomputed
        # from N_analyzed (complete-case N for this variable) minus the CS
        # group size, both already available on this row.
        _vag_d = int(_row["N_analyzed"]) - _cs_d
        _vd, _cd = share_safe.suppress_binary_target_display(
            _vag_n, _cs_n, _vag_d, _cs_d, enabled=SHARE_SAFE_MODE
        )
        _min_vag_disp.append(_vd)
        _cs_events_disp.append(_cd if isinstance(_cd, str) else f"{_cd}/{_cs_d}")
    else:
        _min_vag_disp.append(share_safe.safe_count(_row["min_vaginal_cell"], enabled=SHARE_SAFE_MODE))
        _cs_events_disp.append(_suppress_cs_events_label(_row["cs_events"]))
_sparse_display["min_vaginal_cell"] = _min_vag_disp
_sparse_display["cs_events"] = _cs_events_disp
_sparse_display["min_any_cell"] = _sparse_display["min_any_cell"].apply(
    lambda n: share_safe.safe_count(n, enabled=SHARE_SAFE_MODE)
)

print("Sparsity and event-count table — primary predictors:")
print("(cs_events / min_vaginal_cell / min_any_cell are suppressed below when they")
print(" reveal a cell with n<5 and SHARE_SAFE_MODE is on; the boolean flags")
print(" separation_risk/too_sparse/rare_flag are always shown, since flagging small")
print(" cells for clinical review is this section's purpose.)")
print(_sparse_display.to_string(index=False))
print()

# Separation risk — diagnostic warning, not an automatic exclusion (see the
# methodology note in this section's header: a fitting problem for ordinary
# unpenalized MLE logistic regression specifically, not every modeling approach).
_sep = sparse_df[sparse_df["separation_risk"]]
if len(_sep):
    print(f"SEPARATION RISK — {len(_sep)} variable(s) with an empty target-by-level cell:")
    for _, _r in _sep.iterrows():
        _r_disp = _sparse_display.loc[_sparse_display["variable"] == _r["variable"]].iloc[0]
        print(f"  {_r['variable']}: cs_events={_r_disp['cs_events']} — "
              f"min_vaginal_cell={_r_disp['min_vaginal_cell']} — "
              "unstable/non-convergent for ordinary unpenalized logistic regression; "
              "review before use, and consider a penalized/Firth/Bayesian approach if included.")
print()

# Too sparse -- variable names only (not raw counts), so this list is safe
# to print unconditionally regardless of SHARE_SAFE_MODE.
_sp = sparse_df[sparse_df["too_sparse"]]
print(f"Too sparse (minimum non-zero target-by-level cell is 1-4, excluding "
      f"separation-risk cases): {sorted(_sp['variable'].tolist())}")
print("  These require clinical judgment before inclusion.")
""")


# ── Collect Part 2 cells ──────────────────────────────────────────────────────
EDA_B_PART2_CELLS = [
    SB3_HEADER, SB3_MISS_TABLE, SB3_MISS_BY_TARGET, SB3_MISS_HEATMAP, SB3_COMISSINGNESS,
    SB3_KEY_OBS, SB3_KEY_OBS_CODE,
    SB4_HEADER, SB4_SPARSITY,
]

if __name__ == "__main__":
    print(f"EDA A2 Part 2 cells defined: {len(EDA_B_PART2_CELLS)}")

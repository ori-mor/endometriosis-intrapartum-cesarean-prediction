#!/usr/bin/env python3
"""EDA A2 — Part 3: cell definitions (displayed as sections A2.3-A2.6; this file's
own historical section IDs remain B6-B9 -- see the 2026-08-08 reorg note in
build_a2_notebook.py for why file name and displayed section number no
longer match).

Sections:
  A2.3 (was B6) — Numeric distributions (priority variables, histogram+boxplot by target, skewness)
  A2.4 (was B7) — Binary and categorical distributions (positivity rates, bar charts by target)
  A2.5 (was B8) — Endometriosis phenotype domain EDA
  A2.6 (was B9) — Obstetric + pregnancy domain EDA; secondary near-delivery add-on reference

Full univariate plot + statistics coverage is generated for every numeric
predictor (A2.3), every binary predictor (A2.4, paginated bar-chart grids), and every
categorical predictor (A2.4) currently in PRIMARY_COLS. PRIORITY_VARS additionally receive deeper
domain-specific interpretation in A2.5/A2.6, but plot/statistics coverage itself is
complete for the full predictor pool, not priority-only. All PRIMARY_COLS also
appear in the comprehensive summary table (A2.12).

Depends on: df, df_primary, PRIMARY_COLS, PRIORITY_VARS, OTHER_PRIMARY,
TARGET_COL, all config vars, and helper functions from Part 1.
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


# ── Section A2.6 ────────────────────────────────────────────────────────────────
SB6_HEADER = md("eda-b-s06-header", """
## Section A2.3 — Numeric Distributions: Full Coverage

**Purpose:** Visualise the distribution of every numeric `PRIMARY_COLS` modeling-pathway
variable currently in the primary predictor pool, split by target group, and report the
complete univariate summary table (N, missing, unique count, mean, SD, median,
Q1/Q3/IQR, min/max, skew, IQR outlier bounds and flag count) for each. The exact
count is derived live from `PRIMARY_COLS` and printed in the cell below.

**What this checks:**
- Histogram (integer-aligned bins for discrete count variables: `G`, `P`, `LIVE_BIRTH`,
  `AB`, `CS`; KDE + 20-bin histogram for continuous measurements) + boxplot split by
  target group, for **every** numeric predictor — not a priority subset
- Full descriptive-statistics table, including explicit IQR and IQR 1.5x outlier
  bounds/flag counts, for every numeric predictor
- Skewness (|skewness| > 1.5 flagged)

**What this does NOT do:**
- No transformations are applied
- No values are removed or altered
- Deep outlier analysis (target-blind screening) remains in A2.11 — this section
  reports bounds/counts only, not a data-quality classification

**Priority vs. full coverage:** every numeric predictor receives identical
descriptive-statistics and plot coverage here. `PRIORITY_VARS` membership (marked
with a `*` in plot titles) indicates which variables additionally receive deeper
domain-specific interpretation later (A2.5/A2.6), not which variables are plotted —
plotting coverage is complete for every numeric predictor regardless of priority status.

**Output:** Paginated plot grid (histogram + boxplot per variable, full coverage) +
full descriptive-statistics table
""")

SB6_NUMERIC_PLOTS = code("eda-b-s06-numeric-plots", """
_all_num_vars = [c for c in PRIMARY_COLS if infer_var_type(df_primary[c]) == "numeric"]
print(f"Numeric PRIMARY_COLS modeling-pathway variables in the primary pool: {len(_all_num_vars)}")
print(f"  {_all_num_vars}")
print(f"  (of which PRIORITY_VARS, marked with a star below): "
      f"{[c for c in _all_num_vars if c in PRIORITY_VARS]}")

# Paginated so no single figure becomes unreadably tall/cramped. At 6
# variables/page (the prior density), each row's title and its neighbor's
# bottom xlabel annotation (N=/miss=/skew=) sat close enough together that
# plt.tight_layout()'s automatic spacing was not generous enough to keep
# adjacent rows visually separated -- confirmed by direct visual inspection
# of the rendered figure. Fixed by (1) capping density at 3 variables/page
# (14 numeric PRIMARY_COLS vars -> 5 pages instead of 3) and (2) switching
# from tight_layout() to Matplotlib's constrained-layout engine with
# explicit, generous inter-row/inter-column padding -- a single coherent
# layout system rather than stacking tight_layout on top of a manual
# suptitle y-offset (the prior fig.suptitle(..., y=1.002) had no rect/pad
# reserved for it under tight_layout, risking collision with row 1).
_PAGE_SIZE = 3
_ROW_HEIGHT_IN = 4.5  # generous fixed height per variable row
_pages = [_all_num_vars[i:i + _PAGE_SIZE] for i in range(0, len(_all_num_vars), _PAGE_SIZE)]
for _pg_i, _page_vars in enumerate(_pages, start=1):
    _n_v = len(_page_vars)
    fig, axes = plt.subplots(
        _n_v, 2, figsize=(12, _ROW_HEIGHT_IN * _n_v), layout="constrained",
        squeeze=False,
    )
    # constrained_layout reflows automatically as content is added, but the
    # default padding is tuned for compact figures -- explicitly widen it so
    # row titles/xlabels never sit flush against the neighboring row.
    fig.get_layout_engine().set(w_pad=0.35, h_pad=0.6, hspace=0.08, wspace=0.06)
    for i, col in enumerate(_page_vars):
        plot_numeric_dist(df_primary, col, TARGET_COL, axes[i][0], axes[i][1])
        if col in PRIORITY_VARS:
            axes[i][0].set_title(f"* {axes[i][0].get_title()}", fontsize=12)
    fig.suptitle(f"Numeric predictors — histogram (left) + boxplot by target (right) "
                 f"— page {_pg_i}/{len(_pages)}", fontsize=14)
    plt.show()
print()
print("* = PRIORITY_VARS (receives additional domain-specific interpretation in A2.5/A2.6).")
print("Discrete count variables (G, P, LIVE_BIRTH, AB, CS) use integer-aligned bins,")
print("not a continuous-density histogram, to avoid implying false granularity.")
""")

SB6_SKEWNESS = code("eda-b-s06-skewness", """
_all_num = [c for c in PRIMARY_COLS if infer_var_type(df_primary[c]) == "numeric"]
_skew_rows = []
for col in _all_num:
    s = df_primary[col].dropna()
    _iqr = iqr_bounds(df_primary[col])
    _skew_rows.append({
        "variable":      col,
        "earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(col),
        "N":             len(s),
        "N_missing":     df_primary[col].isna().sum(),
        "n_unique":      int(s.nunique()),
        "mean":          round(s.mean(), 2) if len(s) else None,
        "SD":            round(s.std(), 2) if len(s) else None,
        "median":        round(s.median(), 2) if len(s) else None,
        "Q1":            _iqr["Q1"],
        "Q3":            _iqr["Q3"],
        "IQR":           _iqr["IQR"],
        "min":           round(s.min(), 2) if len(s) else None,
        "max":           round(s.max(), 2) if len(s) else None,
        "skewness":      round(s.skew(), 3) if len(s) else None,
        "high_skew_flag": abs(s.skew()) > 1.5 if len(s) else False,
        "iqr_lower_bound": _iqr["lower_bound"],
        "iqr_upper_bound": _iqr["upper_bound"],
        "n_iqr_flagged": _iqr["n_flagged"],
        "pct_iqr_flagged": _iqr["pct_flagged"],
        "iqr_zero":      _iqr["iqr_zero"],
        "priority":      col in PRIORITY_VARS,
    })
skew_df = pd.DataFrame(_skew_rows).sort_values("skewness", key=abs, ascending=False)
print("Numeric predictor full descriptive-statistics table (sorted by |skewness|):")
print(skew_df.to_string(index=False))
_high = skew_df[skew_df["high_skew_flag"]]
print(f"\\n  High-skew variables (|skewness|>1.5): {len(_high)}")
print("  Descriptive audit information only -- skewness alone never triggers or "
      "selects a transform (Data Cleaning B Section B3 / EDA C Section C14).")
for _, r in _high.iterrows():
    print(f"    {r['variable']}: skew={r['skewness']}")

# zero-IQR variables (e.g. CS) get real Q1/Q3/IQR
# values above but iqr_lower_bound/iqr_upper_bound/n_iqr_flagged are
# withheld (NaN/0) by iqr_bounds() -- explicitly reported here rather than
# silently reading as "0 outliers found", matching EDA A Part 1 Section A8's
# existing behavior for the same situation.
_skew_iqr_zero = skew_df[skew_df["iqr_zero"]]
if len(_skew_iqr_zero):
    print(f"\\n  Variables with IQR == 0 ({len(_skew_iqr_zero)}) -- standard 1.5x-IQR "
          f"flagging is not informative for these and none was performed, but Q1/Q3/IQR "
          f"remain reported above: {_skew_iqr_zero['variable'].tolist()}")

print()
print("Interpretation: this table is descriptive only. IQR flagging is target-blind:")
print("the observed outcome plays no part in whether a value is flagged. A2.11 performs")
print("a deeper target-blind data-quality review of the same flagged values; its")
print("separate outcome-sensitivity block is purely descriptive and does not determine")
print("whether a flagged value is an outlier or an error. A high skew or outlier count")
print("does not, by itself, exclude a variable from the candidate pool.")
""")

SB6_KEY_OBS = md("eda-b-s06-key-observations", """**Key observations — numeric distributions:**""")

SB6_KEY_OBS_CODE = code("eda-b-s06-key-observations-code", """
print(f"- {len(skew_df)} numeric predictors summarized; "
      f"{int(skew_df['high_skew_flag'].sum())} flagged high-skew (|skew|>1.5): "
      f"{skew_df.loc[skew_df['high_skew_flag'], 'variable'].tolist()}.")
_ko6_out = skew_df[skew_df["n_iqr_flagged"] > 0].sort_values("pct_iqr_flagged", ascending=False)
if len(_ko6_out):
    print(f"- {len(_ko6_out)} numeric predictor(s) have IQR-flagged values, highest rate "
          f"'{_ko6_out.iloc[0]['variable']}' ({_ko6_out.iloc[0]['pct_iqr_flagged']}%) -- "
          f"clinically plausible extremes until reviewed in A2.11; none removed here.")
print("- Skew and outlier counts are descriptive; they inform the EDA C transformation")
print("  plan but do not by themselves justify removing or transforming a variable now.")
""")


# ── Section A2.7 ────────────────────────────────────────────────────────────────
SB7_HEADER = md("eda-b-s07-header", """
## Section A2.4 — Binary and Categorical Distributions: Full Coverage

**Purpose:** Document the event rate (positivity rate), contingency-table test, and
near-zero-variance status for every binary predictor, and full level-count +
target-stratified bar-plot coverage for every categorical predictor.

**What this checks:**
- Positivity rate in vaginal group vs CS group for every binary PRIMARY_COLS
  variable (exact count derived from PRIMARY_COLS and printed in the output below)
- Absolute difference in positivity rate (sorted descending)
- Chi-square or Fisher exact test (auto-selected on expected-cell adequacy,
  matching A2.9's test-selection rule), Cramér's V, minimum expected cell count
- Separation flag: any group with 0 positive events
- Near-zero-variance flag (descriptive only — see the Part 1 helper docstring for
  the exact rule): a dominant category ≥99% or, for exactly 2 categories, a
  minority count <5. This is a distinct, purely descriptive concept from **true**
  zero variance — true zero-variance columns are excluded entirely, upstream, in
  Section A2.2's scope construction (`is_true_zero_variance_for_exclusion()`, a
  target-independent, value-only rule), so they never reach `PRIMARY_COLS` or this
  table at all. The near-zero-variance flag computed here never excludes or
  reclassifies a variable
- Level counts, percentages, and target-stratified bar plot for every categorical
  predictor (exact count derived live from PRIMARY_COLS, printed below)

**What this does NOT do:**
- Does not replace A2.9's full formal association ranking (this section's tests are
  reported per-variable here for completeness; A2.9 remains the primary ranked table)
- No transformation or imputation
- Near-zero-variance flags do not change eligibility

**Output:** Full rate + test table (every binary variable) + paginated grouped
bar-chart grids (every binary + every categorical predictor) + categorical level-count table

**Finding a specific Stage 2/3 variable:** every table and plot below covers all
stages together (`earliest_entry_stage` is shown per variable in each table); the
paginated grids page through every stage mixed together, so a single Stage 2 or
Stage 3 variable is not visually isolated here. For a compact, dedicated view of
just the Stage 2-only and Stage 3-only variables (5 and 5 variables respectively as
of the current working-frame classification — see Section A2.2's scope-construction
output above for the live, authoritative count), see Section A2.13's Stage 2-only/
Stage 3-only summary chart.
""")

SB7_BINARY = code("eda-b-s07-binary", """
_g0 = df_primary[df_primary[TARGET_COL] == 0]
_g1 = df_primary[df_primary[TARGET_COL] == 1]
_rate_rows = []
_all_bin = [c for c in PRIMARY_COLS if infer_var_type(df_primary[c]) == "binary"]

for col in _all_bin:
    sub = df_primary[[col, TARGET_COL]].dropna(subset=[col])
    g0s = sub[sub[TARGET_COL] == 0]
    g1s = sub[sub[TARGET_COL] == 1]
    n_pos0 = int((g0s[col] == 1).sum())
    n_pos1 = int((g1s[col] == 1).sum())
    r0 = round(n_pos0 / len(g0s) * 100, 1) if len(g0s) else None
    r1 = round(n_pos1 / len(g1s) * 100, 1) if len(g1s) else None
    diff = round(abs(r1 - r0), 1) if (r0 is not None and r1 is not None) else None
    sep  = (n_pos1 == 0 or (len(g1s) - n_pos1) == 0)
    # Canonical dict API: chi2_or_fisher() returns a
    # dict, not a positional tuple -- unpacking it positionally (e.g.
    # `pv, test, _ = chi2_or_fisher(...)`) raises ValueError (too many values
    # to unpack), which a broad `except Exception` previously swallowed into a
    # silent test="error"/p=None row. No try/except here: a genuinely
    # unexpected failure on a validated, non-empty PRIMARY_COLS column should
    # fail loudly rather than render as a misleading "error" result.
    _res = chi2_or_fisher(col, df_primary, TARGET_COL)
    _pv, _test = _res["p_value"], _res["test"]
    _ct = pd.crosstab(sub[col], sub[TARGET_COL])
    _exp = stats.chi2_contingency(_ct, correction=False)[3] if _ct.shape == (2, 2) else None
    _min_exp = round(float(_exp.min()), 2) if _exp is not None else None
    _v = cramers_v(_ct)
    _nzv_flag, _nzv_frac, _ = near_zero_variance_flag(df_primary[col])
    _rate_rows.append({
        "variable":         col,
        "earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(col),
        "N_analyzed":       len(sub),
        "N_missing":        df_primary[col].isna().sum(),
        "vaginal_N":        len(g0s),
        "cs_N":             len(g1s),
        "vaginal_pos_%":    r0,
        "cs_pos_%":         r1,
        "abs_diff_%":       diff,
        "vaginal_events":   n_pos0,
        "cs_events":        n_pos1,
        "separation_risk":  sep,
        "min_expected_cell": _min_exp,
        "test":             _test,
        "p_value":          _pv,
        "cramers_v":        _v,
        "near_zero_variance": _nzv_flag,
        "priority":         col in PRIORITY_VARS,
    })

rate_df = pd.DataFrame(_rate_rows).sort_values("abs_diff_%", ascending=False, na_position="last")
# Share-safe display copy: cs_events is a
# raw event count that can be small for a rare binary predictor -- suppressed
# in the printed table when SHARE_SAFE_MODE is on. The underlying rate_df
# keeps real values for downstream computation (e.g. near-zero-variance
# flagging above, which is already computed before this point).
#
# cs_pos_%/vaginal_pos_% are suppressed on the same n<5 (numerator or
# complement) rule as cs_events: since the per-column group denominator
# (cs_N/vaginal_N) is also shown, printing cs_pos_% alone would reconstruct a
# suppressed cs_events count, so both percentage columns and vaginal_events
# must be protected together with it.
_rate_display = rate_df.copy()
# Centralized binary target-stratified display protection: every rendered
# surface in this notebook (and A1's own A6 table) that shows a binary
# predictor's vaginal/CS positive count uses ONE shared decision --
# share_safe.suppress_binary_target_display() -- rather than an independent
# per-surface check, because a "safe-looking" count shown on one side could
# otherwise combine with A1's separately-reported unstratified total
# (n_positive = vaginal_events + cs_events, by construction) to recover a
# protected complement. See that function's own docstring for the full
# rationale (both the same-group-negative-cell axis and the cross-group
# total-positive axis).
_vag_cs_disp = [
    share_safe.suppress_binary_target_display(
        int(_vn), int(_cn), int(_vd), int(_cd), enabled=SHARE_SAFE_MODE
    )
    for _vn, _cn, _vd, _cd in zip(
        rate_df["vaginal_events"], rate_df["cs_events"], rate_df["vaginal_N"], rate_df["cs_N"]
    )
]
_rate_display["vaginal_events"] = [v for v, c in _vag_cs_disp]
_rate_display["cs_events"] = [c for v, c in _vag_cs_disp]
# Percentage suppression is driven by whether the corresponding event count
# above was suppressed (either reason), so the two columns can never
# disagree about whether a given cell is protected.
_rate_display["cs_pos_%"] = [
    p if not isinstance(disp, str) else "suppressed (n<5 in a cell)"
    for disp, p in zip(_rate_display["cs_events"], rate_df["cs_pos_%"])
]
_rate_display["vaginal_pos_%"] = [
    p if not isinstance(disp, str) else "suppressed (n<5 in a cell)"
    for disp, p in zip(_rate_display["vaginal_events"], rate_df["vaginal_pos_%"])
]
# abs_diff_% (a difference of two percentages) can indirectly re-derive a
# suppressed individual percentage if the other one is shown -- suppress it
# too whenever either underlying group percentage was suppressed. rate_df
# itself (used for sorting/plotting above) is unaffected -- only this
# printed display copy.
_rate_display["abs_diff_%"] = [
    "suppressed (n<5 in a cell)"
    if (isinstance(cs, str) or isinstance(vg, str)) else diff
    for cs, vg, diff in zip(_rate_display["cs_pos_%"], _rate_display["vaginal_pos_%"], rate_df["abs_diff_%"])
]
print(f"Binary predictors — full rate + test table (all {len(_all_bin)}, sorted by abs difference):")
print(_rate_display.to_string(index=False))
_nzv_bin = rate_df[rate_df["near_zero_variance"]]
print(f"\\nNear-zero-variance binary predictors (descriptive flag only, not excluded): "
      f"{len(_nzv_bin)}")
for _, r in _nzv_bin.iterrows():
    _safe_events = share_safe.safe_count(r["cs_events"], enabled=SHARE_SAFE_MODE)
    # Row-specific analyzed CS-group N (cs_N), not the global cohort-wide n1
    # -- a column with any missingness has cs_N < n1 (e.g. severe_PET,
    # cs_N=60 vs n1=61), so using the global n1 here understated the true
    # analyzed denominator for such columns. The main rate_df table above
    # already reports cs_N correctly per row; this footnote now matches it.
    print(f"    {r['variable']}: cs_events={_safe_events}/{int(r['cs_N'])}, test={r['test']}, "
          f"p={r['p_value']} -- sparse-event effect estimate; interpret with caution")

# Bar chart — priority binary variables (deeper-interpretation subset)
#
# Share-safe: bar heights must come from the already-suppressed
# _rate_display, not the RAW rate_df -- a suppressed percentage's exact bar
# height is just as disclosive as printing the number, whether or not the
# TABLE shows it. Bar heights are taken from _rate_display (aligned by
# the shared row index), converting any suppression marker to NaN (no bar
# rendered) with an explicit 'Suppressed' text annotation, mirroring the
# convention already used elsewhere in this notebook (Section A2.13's
# stage-only-outcome graphs) -- a suppressed rate is UNKNOWN to the reader,
# never rendered as a 0-height bar.
def _bin_plot_value(display_value):
    return float(display_value) if isinstance(display_value, (int, float)) else np.nan


def _bin_annotate_suppressed(ax, x, y=5, fontsize=8):
    ax.text(x, y, "Suppressed", ha="center", va="bottom", fontsize=fontsize,
            fontstyle="italic", color="firebrick", rotation=90,
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))


_prio_bin = rate_df[rate_df["priority"]].dropna(subset=["abs_diff_%"]).head(16)
if len(_prio_bin):
    _prio_display = _rate_display.loc[_prio_bin.index]
    _prio_vag_plot = [_bin_plot_value(v) for v in _prio_display["vaginal_pos_%"]]
    _prio_cs_plot = [_bin_plot_value(v) for v in _prio_display["cs_pos_%"]]
    x   = range(len(_prio_bin))
    w   = 0.35
    fig, ax = plt.subplots(figsize=(13, 5), layout="constrained")
    ax.bar([i - w/2 for i in x], _prio_vag_plot, w,
           label=f"Vaginal (n={n0})", color=C0)
    ax.bar([i + w/2 for i in x], _prio_cs_plot, w,
           label=f"Intrapartum CS (n={n1})", color=C1)
    for _i, (_v, _c) in enumerate(zip(_prio_vag_plot, _prio_cs_plot)):
        if np.isnan(_v):
            _bin_annotate_suppressed(ax, _i - w/2)
        if np.isnan(_c):
            _bin_annotate_suppressed(ax, _i + w/2)
    ax.set_xticks(list(x))
    ax.set_xticklabels(_prio_bin["variable"].tolist(), rotation=40, ha="right", fontsize=10)
    ax.tick_params(axis="y", labelsize=10)
    ax.set_ylabel("Positivity rate (%)", fontsize=11.5)
    ax.set_title("* Priority binary predictors — positivity rate by target "
                 "(deeper interpretation subset)", fontsize=13, pad=12)
    ax.legend(fontsize=10)
    plt.show()
""")

SB7_BINARY_FULL_PLOTS = code("eda-b-s07-binary-full-plots", """
# Full coverage: paginated grouped bar charts for ALL binary predictors in
# rate_df (not only the priority subset above), so no binary predictor is
# plot-omitted. The count is derived live below (len(_bin_order)) and printed
# in both the chart titles and the summary line -- never hardcoded here.
# Horizontal orientation (predictor names on the y-axis, 8/page) so long
# predictor names stay readable without steep label rotation -- a 12/page
# vertical-bar layout with 45-degree rotated labels was still too crowded for
# publication/report reuse.
# Share-safe: plotted from _rate_display (the already share-safe-suppressed
# copy built in the previous cell), not raw rate_df -- same rationale as the
# priority chart above. Suppression markers are
# converted to NaN (no bar rendered) with an explicit 'Suppressed'
# annotation via _bin_plot_value()/_bin_annotate_suppressed() (defined in
# the previous cell, reused here unchanged).
_PAGE_SIZE_BIN = 8
_bin_order = rate_df["variable"].tolist()
_bin_pages = [_bin_order[i:i + _PAGE_SIZE_BIN] for i in range(0, len(_bin_order), _PAGE_SIZE_BIN)]
for _pg_i, _page_vars in enumerate(_bin_pages, start=1):
    _pg_df = _rate_display[_rate_display["variable"].isin(_page_vars)].set_index("variable").loc[_page_vars]
    _pg_vag_plot = [_bin_plot_value(v) for v in _pg_df["vaginal_pos_%"]]
    _pg_cs_plot = [_bin_plot_value(v) for v in _pg_df["cs_pos_%"]]
    y = range(len(_pg_df))
    h = 0.35
    fig, ax = plt.subplots(figsize=(11, max(4.5, 0.85 * len(_pg_df) + 1.6)), layout="constrained")
    # No global N in the legend: each bar's rate uses that PREDICTOR's own
    # non-missing group denominator (vaginal_N/cs_N in rate_df above), which
    # differs by variable whenever there is any missingness (e.g. the
    # endo_resection_* family: vaginal_N=192/cs_N=30, vs. the full-cohort
    # n0=370/n1=61) -- a single global n0/n1 in the legend previously misstated
    # the analyzed denominator for such columns.
    ax.barh([j + h/2 for j in y], _pg_vag_plot, h,
            label="Vaginal", color=C0)
    ax.barh([j - h/2 for j in y], _pg_cs_plot, h,
            label="Intrapartum CS", color=C1)
    for _j, (_v, _c) in enumerate(zip(_pg_vag_plot, _pg_cs_plot)):
        if np.isnan(_v):
            ax.text(1, _j + h/2, "Suppressed", ha="left", va="center", fontsize=8,
                    fontstyle="italic", color="firebrick",
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))
        if np.isnan(_c):
            ax.text(1, _j - h/2, "Suppressed", ha="left", va="center", fontsize=8,
                    fontstyle="italic", color="firebrick",
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))
    ax.set_yticks(list(y))
    ax.set_yticklabels(
        [f"*{v}" if v in PRIORITY_VARS else v for v in _pg_df.index],
        fontsize=11
    )
    ax.invert_yaxis()
    ax.tick_params(axis="x", labelsize=10)
    ax.set_xlabel("Positivity rate (%)", fontsize=11.5)
    ax.set_title(f"All binary predictors — positivity rate by target "
                 f"(page {_pg_i}/{len(_bin_pages)} of {len(_bin_order)})\\n"
                 f"Rates use each predictor's own non-missing group denominator "
                 f"(exact N is reported in the rate table above), not a single cohort-wide N.",
                 fontsize=11.5, pad=12)
    ax.legend(fontsize=10, loc="lower right")
    plt.show()
print(f"Full binary bar-chart coverage: {len(_bin_order)} of {len(_bin_order)} "
      "binary predictors plotted across the pages above.")
""")

SB7_CATEGORICAL = code("eda-b-s07-categorical", """
_cat_vars = [c for c in PRIMARY_COLS if infer_var_type(df_primary[c]) == "categorical"]
print(f"Categorical PRIMARY_COLS modeling-pathway variables: {len(_cat_vars)}  {_cat_vars}")
if not _cat_vars:
    print("No multi-level categorical primary predictors.")
else:
    # Small-cell disclosure guard: reuses this
    # project's existing sparse-cell convention (n < 5 -- the same threshold
    # already used for A2.8's too_sparse/min_expected_cell, and for the
    # small-subgroup disclosure guard in eda_a_part2_summaries.py) rather than
    # inventing a new one. Printing every level's exact total/vaginal/CS count
    # unconditionally previously exposed near-patient-level cells for real --
    # several categorical predictors in this cohort have one or more levels
    # with a handful of patients each. Any level with total N < 5 is now
    # combined into one suppressed bucket instead of printed individually;
    # raw per-patient counts stay available internally (cramers_v/
    # chi2_or_fisher below still use the full, unsuppressed contingency table).
    _CAT_MIN_DISCLOSURE_N = 5
    _cat_test_rows = []
    for col in _cat_vars:
        sub = df_primary[[col, TARGET_COL]].dropna(subset=[col])
        g0s = sub[sub[TARGET_COL] == 0]
        g1s = sub[sub[TARGET_COL] == 1]
        _n_levels = sub[col].nunique()
        _vc = sub[col].value_counts()
        _rare_levels = _vc[_vc < 10].index.tolist()  # rare-category rule: count < 10,
        # consistent with this project's existing A2.8 sparsity "rare_flag" convention.
        print(f"  {col} (N={len(sub)}, miss={df_primary[col].isna().sum()}, "
              f"{_n_levels} levels, rare levels (<10 obs, count only -- see suppression "
              f"below): {len(_rare_levels)}):")
        # Reconstruction-aware combination: a naive "combine every level with
        # count<5 into one bucket" guard is not enough on its own -- if only
        # ONE level ever needed combining, the bucket's own total IS that
        # level's exact count, and withholding that total would not help
        # either, since N is
        # printed on the header line above and every OTHER level is shown
        # individually -- a reader can recompute the same exact value as
        # N minus the sum of the shown levels regardless.
        # safe_combine_rare_levels() instead folds levels into the combined
        # bucket smallest-first until the bucket's own total is empty or
        # safely >= threshold (folding in an otherwise-safe level if
        # necessary), so neither the printed aggregate nor the N-minus-shown-
        # levels arithmetic can isolate any single rare level's exact count.
        _level_totals = {lv: int((sub[col] == lv).sum()) for lv in _vc.index[:10]}
        _visible_levels, _below_n, _below_k = share_safe.safe_combine_rare_levels(
            _level_totals, threshold=_CAT_MIN_DISCLOSURE_N
        )
        for lv in _vc.index[:10]:
            if lv not in _visible_levels:
                continue
            n_tot  = _visible_levels[lv]
            n_cs   = int((g1s[col] == lv).sum())
            n_vag  = int((g0s[col] == lv).sum())
            # Share-safe: n_tot>=5 (checked above) does not
            # guarantee its target-group split does -- e.g. n_tot=5 could be
            # 3 vaginal / 2 CS, disclosing a small CS-group cell even though
            # the level as a whole passed the suppression threshold. Suppress
            # n_vag/n_cs and their percentages independently.
            # Complement-aware WITHIN THIS LEVEL (n_vag + n_cs == n_tot
            # exactly, since sub already dropped rows missing `col` and
            # TARGET_COL is never missing): checking each against len(g0s)/
            # len(g1s) (the whole column's vaginal/CS group sizes) alone is
            # NOT sufficient -- it misses that `total={n_tot}` is printed on
            # this same line, so a "safe-looking" large n_vag next to a safe
            # n_tot still discloses a small n_cs by subtraction even when
            # n_cs itself is separately flagged. Checking each against n_tot
            # (its complement is the OTHER class within this level) makes
            # both n_vag_disp and n_cs_disp suppress together whenever either
            # one is a protected small cell, so neither the printed count nor
            # total-minus-shown-count arithmetic can recover it.
            _vag_disp = share_safe.safe_count_with_complement(n_vag, n_tot, enabled=SHARE_SAFE_MODE)
            _cs_disp = share_safe.safe_count_with_complement(n_cs, n_tot, enabled=SHARE_SAFE_MODE)
            # safe_count_with_complement() and safe_pct_disclosure() detect
            # the identical suppression condition (same numerator/complement,
            # same threshold) independently -- composing both unconditionally
            # previously printed a redundant, duplicated suppression phrase
            # side by side. When the
            # count itself is already suppressed (a non-numeric marker
            # string), the percentage is necessarily suppressed too under the
            # same condition, so its own "(suppressed...)" phrase is
            # redundant and omitted; the percentage is shown in parentheses
            # only when the count was not suppressed. Suppression itself is
            # unchanged -- no small-cell value is disclosed either way.
            _vag_pct_str = f" ({safe_pct_disclosure(n_vag, len(g0s))})" if isinstance(_vag_disp, (int, float)) else ""
            _cs_pct_str = f" ({safe_pct_disclosure(n_cs, len(g1s))})" if isinstance(_cs_disp, (int, float)) else ""
            print(f"    {lv}: total={n_tot} ({safe_pct(n_tot, len(sub))}) | "
                  f"vaginal={_vag_disp}{_vag_pct_str} "
                  f"| CS={_cs_disp}{_cs_pct_str}")
        if _below_k:
            if _below_n is not None and _below_n >= _CAT_MIN_DISCLOSURE_N:
                print(f"    [{share_safe.format_combined_levels_note(_below_k, _below_n)}]")
            else:
                # Pathological case: this variable's entire non-missing
                # population is too small (even combined) to display any
                # breakdown safely -- not expected for any current
                # PRIMARY_COLS categorical variable in this cohort.
                print(f"    [{_below_k} smaller categor{'y' if _below_k == 1 else 'ies'} "
                      f"combined: too few total observations to display safely, suppressed]")
        if _n_levels > 10:
            print(f"    ... ({_n_levels-10} more levels)")
        # Canonical dict API -- see the A2.4 binary-loop comment above for why
        # there is no positional unpacking / broad except here.
        _ct = pd.crosstab(sub[col], sub[TARGET_COL])
        _res = chi2_or_fisher(col, df_primary, TARGET_COL)
        _pv, _test = _res["p_value"], _res["test"]
        _v = cramers_v(_ct)
        _min_exp = round(float(stats.chi2_contingency(_ct, correction=False)[3].min()), 2)
        _cat_test_rows.append({
            "variable": col, "earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(col),
            "N": len(sub), "n_levels": _n_levels,
            "n_rare_levels": len(_rare_levels), "test": _test,
            "min_expected_cell": _min_exp, "p_value": _pv, "cramers_v": _v,
        })
        print(f"    -> {_test}: p={_pv}, Cramer's V={_v}, min_expected_cell={_min_exp}")
        print()
    cat_test_df = pd.DataFrame(_cat_test_rows)
    print("Categorical predictor association summary:")
    print(cat_test_df.to_string(index=False))
""")

SB7_CATEGORICAL_PLOTS = code("eda-b-s07-categorical-plots", """
# Target-stratified bar plots for every categorical predictor (full coverage,
# not a text-only summary). One variable per row (horizontal bars) so long
# category labels and up to 8 levels per variable (matching the level cap
# already used in the printed table above) stay legible at normal document
# width -- a 2-per-row vertical-bar grid was too dense for publication use.
if _cat_vars:
    _n_c = len(_cat_vars)
    _level_counts = []
    for col in _cat_vars:
        _sub_n = df_primary[[col, TARGET_COL]].dropna(subset=[col])
        _level_counts.append(min(8, _sub_n[col].nunique()))
    # Row height scales with the number of levels actually shown, so a
    # variable with 8 levels gets as much vertical room as it needs while a
    # binary-like categorical (2-3 levels) does not waste page space.
    _row_heights = [max(2.4, 0.5 * lv + 1.3) for lv in _level_counts]
    fig, axes = plt.subplots(
        _n_c, 1, figsize=(11.5, sum(_row_heights)),
        gridspec_kw={"height_ratios": _row_heights}, layout="constrained",
    )
    axes = np.atleast_1d(axes)
    # within-target-group percentages, not raw counts -- a
    # raw-count bar chart makes level sizes visually incomparable across
    # target groups of very different size (vaginal vs. CS is roughly a
    # 6:1 split in the current cohort), and previously showed exact small
    # counts directly. N is shown in the title so the denominator is never
    # hidden. A suppressed (small-cell) rate is UNKNOWN to the reader, not
    # 0% -- it is plotted as np.nan (no bar rendered by matplotlib for a NaN
    # height) with an explicit 'Suppressed' text annotation, mirroring the
    # same convention already established in Section A2.13's Stage-only
    # outcome graphs (a2_part5_readiness.py, SB13_STAGE_ONLY_OUTCOME_GRAPH)
    # rather than the previous 0-height-bar encoding, which made a suppressed
    # cell visually indistinguishable from a genuine, unsuppressed 0%. A
    # genuine 0% still renders as a real zero-height bar; the raw small count
    # itself is never shown either way.
    def _cat_plot_value(display_value):
        return float(display_value) if isinstance(display_value, (int, float)) else np.nan

    def _cat_annotate_suppressed(ax, y, x=50, fontsize=9):
        ax.text(x, y, "Suppressed", ha="center", va="center", fontsize=fontsize,
                fontstyle="italic", color="firebrick",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))

    for i, col in enumerate(_cat_vars):
        ax = axes[i]
        sub = df_primary[[col, TARGET_COL]].dropna(subset=[col])
        g0s_n, g1s_n = int((sub[TARGET_COL] == 0).sum()), int((sub[TARGET_COL] == 1).sum())
        # Whether ANY level's target-by-level cell is a protected small count
        # (1-4) is determined from the FULL crosstab (every level, not just
        # the top-8 plotted below) -- this decides both the per-level
        # percentage suppression rule and whether the title may show exact
        # target-specific margins (see below).
        _ct_full = pd.crosstab(sub[col], sub[TARGET_COL])
        _has_small_cell_plot = bool(((_ct_full >= 1) & (_ct_full <= 4)).any().any())
        _top_levels = sub[col].value_counts().index[:8]
        _plot_df = sub[sub[col].isin(_top_levels)].copy()
        _ct = pd.crosstab(_plot_df[col], _plot_df[TARGET_COL], normalize=False).reindex(_top_levels)
        _vag_counts = _ct.get(0, pd.Series(0, index=_ct.index))
        _cs_counts = _ct.get(1, pd.Series(0, index=_ct.index))
        # Checked against each level's own total (not g0s_n/g1s_n, the
        # global group sizes), consistent with A2.4's text table and the
        # Stage-2/3 graph: a percentage safe relative to the global group can
        # still disclose a protected complement within its own level.
        _n_tot_plot = _vag_counts + _cs_counts
        _vag_pct = [
            share_safe.safe_pct_with_denominator(int(n), int(t), enabled=SHARE_SAFE_MODE)[0]
            for n, t in zip(_vag_counts, _n_tot_plot)
        ]
        _cs_pct = [
            share_safe.safe_pct_with_denominator(int(n), int(t), enabled=SHARE_SAFE_MODE)[0]
            for n, t in zip(_cs_counts, _n_tot_plot)
        ]
        # Suppressed (string) values plot as np.nan (no bar rendered), with an
        # explicit 'Suppressed' annotation added below -- never a 0-height bar,
        # and never the raw small count itself.
        _vag_plot = [_cat_plot_value(v) for v in _vag_pct]
        _cs_plot = [_cat_plot_value(v) for v in _cs_pct]
        _y = range(len(_ct))
        _h = 0.35
        ax.barh([j + _h/2 for j in _y], _vag_plot, _h, label="Vaginal", color=C0)
        ax.barh([j - _h/2 for j in _y], _cs_plot, _h, label="Intrapartum CS", color=C1)
        for _j_bar, (_vv, _cv) in enumerate(zip(_vag_plot, _cs_plot)):
            if np.isnan(_vv):
                _cat_annotate_suppressed(ax, _j_bar + _h/2)
            if np.isnan(_cv):
                _cat_annotate_suppressed(ax, _j_bar - _h/2)
        ax.set_xlim(0, 100)
        ax.set_yticks(list(_y))
        # a level whose bar is suppressed on BOTH
        # sides (both vag_pct and cs_pct are strings, i.e. a small cell on
        # every target group it appears in) previously still showed its real
        # category name on the axis -- disclosing "this rare category
        # exists in this cohort" even with no numerical bar rendered next to
        # it (just a 'Suppressed' annotation), in a small cohort where that
        # alone can be identifying. Its label is
        # replaced with a generic placeholder instead; only a level with at
        # least one non-suppressed side keeps its real name.
        _ytick_labels = [
            str(_lv)[:32] if (isinstance(_vp, (int, float)) or isinstance(_cp, (int, float)))
            else "[suppressed]"
            for _lv, _vp, _cp in zip(_ct.index, _vag_pct, _cs_pct)
        ]
        ax.set_yticklabels(_ytick_labels, fontsize=10.5)
        ax.invert_yaxis()
        ax.tick_params(axis="x", labelsize=10)
        # Share-safe title: exact target-specific complete-case margins
        # (vaginal n=.../CS n=...) must not be shown for a variable with a
        # protected per-level cell -- combined with the per-level breakdown
        # above (or with A2.9's own N_vaginal/N_cs), that would let a reader
        # recover the hidden level's exact split by subtraction. When this
        # variable has any protected cell, the title states only the safe
        # aggregate N and omits the target-specific margins entirely.
        if _has_small_cell_plot:
            _title_margins = "target-group Ns suppressed for disclosure protection"
        else:
            _title_margins = f"vaginal n={g0s_n}, CS n={g1s_n}"
        ax.set_title(f"{col}  (N={len(sub)} — {_title_margins} — "
                     f"miss={df_primary[col].isna().sum()}, {sub[col].nunique()} levels)",
                     fontsize=12, pad=10)
        ax.set_xlabel("Within-target-group %", fontsize=11)
        ax.legend(fontsize=10, loc="lower right", framealpha=0.9)
    fig.suptitle("Categorical predictors — within-target-group % by level (top 8 levels shown; "
                 "small cells suppressed -- shown as a missing bar labeled 'Suppressed', never as 0%)",
                 fontsize=14)
    plt.show()
""")

SB7_KEY_OBS = md("eda-b-s07-key-observations", """**Key observations — binary and categorical distributions:**""")

SB7_KEY_OBS_CODE = code("eda-b-s07-key-observations-code", """
print(f"- {len(rate_df)} binary predictors summarized; "
      f"{int(rate_df['separation_risk'].sum())} show complete separation, "
      f"{len(_nzv_bin)} are near-zero-variance (descriptive flag only).")
_ko7_top = rate_df.dropna(subset=['abs_diff_%']).head(3)
if len(_ko7_top):
    print(f"- Largest vaginal-vs-CS rate gaps: "
          f"{list(zip(_ko7_top['variable'], _ko7_top['abs_diff_%']))} -- descriptive "
          f"only; formal ranked association is in A2.9.")
if _cat_vars:
    _ko7_rare_cat = cat_test_df[cat_test_df["n_rare_levels"] > 0]
    if len(_ko7_rare_cat):
        print(f"- {len(_ko7_rare_cat)} categorical predictor(s) have at least one rare "
              f"level (<10 obs): {_ko7_rare_cat['variable'].tolist()} -- flag for later "
              f"review of level-grouping options during Feature Selection.")
print("- No variable is modified, grouped, or excluded based on these distributions.")
""")


# ── Section A2.8 ────────────────────────────────────────────────────────────────
SB8_HEADER = md("eda-b-s08-header", """
## Section A2.5 — Endometriosis Phenotype Domain EDA

**Purpose:** Give deeper, narrative interpretation to a curated subset of
endometriosis-specific primary predictors, respecting the subgroup structure of
endometrioma-related variables. This section is a domain-focused *complement* to
the full-coverage statistical tables in A2.3/A2.4/A2.12, not a replacement for them.

**What this checks:**
- A curated set of endometriosis binary predictors: positivity rates +
  chi-square/Fisher test by target (deeper narrative than A2.4's table)
- Endometrioma subgroup: `endometrioma_size_clean` and `endometrioma_laterality` analysed
  within the endometrioma=1 subgroup only (structural NaN for non-endometrioma patients)

**What this does NOT do:**
- No reclassification of endometriosis subtypes
- Structural NaN subgroup analysis is restricted to the clinically correct subgroup

**Curated subset given deeper narrative interpretation here:**
`deep_endometriosis`, `adenomyosis`, `endometrioma`,
`endometriosis_surgery`, `cs_scar_endometriosis`, `peritoneal_endometriosis`,
`endometrioma_size_clean` (subgroup), `endometrioma_laterality` (subgroup)

`superficial_endometriosis` is intentionally excluded from this diagnostic entirely
(not merely filtered downstream): it is `clinically_redundant_exclude` --
`peritoneal_endometriosis` is the modeled representation of this overlapping
information. No target association or effect size for `superficial_endometriosis` is
shown anywhere in this notebook.

**Other endometriosis-domain primary predictors:**
`endometrioma_place_clean` (subgroup), `endo_surgery_adhesiolysis`, and the 10
`endo_resection_*` multi-hot columns are `predictor_allowed` -- **not**
`manual_review_pending` (the current classification has zero `manual_review_pending`
variables). They receive full statistical coverage in A2.4
(every binary/categorical predictor) and appear in A2.12's comprehensive table; they
are simply not individually narrated in this domain section's curated subset above.

**Output:** Binary predictor table + grouped bar chart + endometrioma subgroup analysis
""")

SB8_ENDO_BINARY = code("eda-b-s08-endo-binary", """
# superficial_endometriosis is deliberately NOT in this list: it is
# clinically_redundant_exclude, not a modeling candidate at any
# stage, and this diagnostic must show no target association or effect size
# for it. peritoneal_endometriosis is the canonical modeled phenotype for the
# overlapping information.
_ENDO_BINARY = [
    "deep_endometriosis", "adenomyosis",
    "endometrioma", "endometriosis_surgery", "cs_scar_endometriosis",
    "peritoneal_endometriosis",
]
_endo_avail = [c for c in _ENDO_BINARY if c in PRIMARY_COLS]
print("=== Endometriosis binary predictors ===")
print(f"{'Variable':<40} {'N':>4} {'Miss%':>6} {'Vag%':>6} {'CS%':>5} {'p':>8} {'V':>5}")
print("-" * 80)
for col in _endo_avail:
    sub = df_primary[[col, TARGET_COL]].dropna(subset=[col])
    g0s = sub[sub[TARGET_COL] == 0]
    g1s = sub[sub[TARGET_COL] == 1]
    # Share-safe: safe_pct() only formats percentages -- it does
    # NOT suppress small cells despite the name. This printed table
    # previously showed an unsuppressed CS-group % that can reconstruct a
    # small event count (e.g. "3.2%" of a small n1 implies ~2 patients).
    # Reuses safe_pct's "—" convention for a zero denominator.
    _r0_val, _ = share_safe.safe_pct_with_denominator(
        int((g0s[col] == 1).sum()), len(g0s), enabled=SHARE_SAFE_MODE
    )
    _r1_val, _ = share_safe.safe_pct_with_denominator(
        int((g1s[col] == 1).sum()), len(g1s), enabled=SHARE_SAFE_MODE
    )
    r0 = f"{_r0_val:.1f}%" if isinstance(_r0_val, (int, float)) else (_r0_val or "—")
    r1 = f"{_r1_val:.1f}%" if isinstance(_r1_val, (int, float)) else (_r1_val or "—")
    n_miss = df_primary[col].isna().sum()
    # Canonical dict API -- see the A2.4 binary-loop comment above.
    _res = chi2_or_fisher(col, df_primary, TARGET_COL)
    pv = _res["p_value"]
    ct = pd.crosstab(sub[col], sub[TARGET_COL])
    v  = cramers_v(ct)
    print(f"  {col:<38} {len(sub):>4} {n_miss/len(df_primary)*100:>5.1f}% "
          f"{r0:>6} {r1:>5} {str(pv):>8} {str(v):>5}")

# Bar chart
# this chart previously computed .mean()*100 directly on the
# full target-group slice, where a missing value in a NaN-containing endo
# column evaluates to False (not dropped), diluting the rate toward 0% --
# inconsistent with the printed table above, which correctly drops missing
# per column first. Reuses the exact same per-column dropna pattern as that
# table so the chart and table always agree.
_er = []
for c in _endo_avail:
    if c not in df_primary.columns:
        continue
    _sub = df_primary[[c, TARGET_COL]].dropna(subset=[c])
    _g0s = _sub[_sub[TARGET_COL] == 0]
    _g1s = _sub[_sub[TARGET_COL] == 1]
    _vag_pct, _ = share_safe.safe_pct_with_denominator(
        int((_g0s[c] == 1).sum()), len(_g0s), enabled=SHARE_SAFE_MODE
    )
    _cs_pct, _ = share_safe.safe_pct_with_denominator(
        int((_g1s[c] == 1).sum()), len(_g1s), enabled=SHARE_SAFE_MODE
    )
    _er.append({"var": c, "vaginal_%": _vag_pct, "cs_%": _cs_pct})
if _er:
    _er_df = pd.DataFrame(_er)
    # Suppressed (string) values plot as np.nan (no bar rendered), with an
    # explicit 'Suppressed' text annotation at that bar's position -- the
    # same convention already established in eda-b-s07-categorical-plots and
    # A2.13's stage-only outcome graphs (SB13_STAGE_ONLY_OUTCOME_GRAPH). A
    # suppressed rate is UNKNOWN to the reader, not 0% -- it must never be
    # encoded as a numeric zero / 0-height bar, which would be visually
    # indistinguishable from a genuine, unsuppressed 0%. A genuine 0% still
    # renders as a real zero-height bar; the raw small count itself is never
    # shown either way. The printed table above remains the authoritative,
    # explicitly-labeled-suppressed record.
    def _endo_plot_value(display_value):
        return float(display_value) if isinstance(display_value, (int, float)) else np.nan

    def _endo_annotate_suppressed(ax, x, y=50, fontsize=9):
        ax.text(x, y, "Suppressed", ha="center", va="center", fontsize=fontsize,
                fontstyle="italic", color="firebrick",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))

    _er_df["vaginal_%_plot"] = [_endo_plot_value(v) for v in _er_df["vaginal_%"]]
    _er_df["cs_%_plot"] = [_endo_plot_value(v) for v in _er_df["cs_%"]]
    x = range(len(_er_df))
    w = 0.35
    fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
    ax.bar([i-w/2 for i in x], _er_df["vaginal_%_plot"], w, label=f"Vaginal (n={n0})", color=C0)
    ax.bar([i+w/2 for i in x], _er_df["cs_%_plot"],      w, label=f"Intrapartum CS (n={n1})", color=C1)
    for _i_bar, (_vv, _cv) in enumerate(zip(_er_df["vaginal_%_plot"], _er_df["cs_%_plot"])):
        if np.isnan(_vv):
            _endo_annotate_suppressed(ax, _i_bar - w/2)
        if np.isnan(_cv):
            _endo_annotate_suppressed(ax, _i_bar + w/2)
    ax.set_ylim(0, 100)
    ax.set_xticks(list(x))
    ax.set_xticklabels([r["var"].replace("_"," ") for r in _er], rotation=30, ha="right", fontsize=10.5)
    ax.tick_params(axis="y", labelsize=10)
    ax.set_ylabel("Positivity rate (%)", fontsize=11.5)
    ax.set_title("Endometriosis phenotype variables — positivity rate by target", fontsize=13, pad=12)
    ax.legend(fontsize=10)
    plt.show()
    if SHARE_SAFE_MODE and (
        _er_df["vaginal_%"].astype(str).str.contains("suppressed").any()
        or _er_df["cs_%"].astype(str).str.contains("suppressed").any()
    ):
        print("  NOTE: one or more bars above are shown as a missing bar labeled 'Suppressed' "
              "because the underlying rate is based on a small (n<5) cell -- see the printed "
              "table above for the explicit suppression label. A suppressed rate is UNKNOWN to "
              "the reader, not 0%, and must never be read as a true 0%.")
""")

SB8_ENDO_SUBGROUP = code("eda-b-s08-endo-subgroup", """
# ── Endometrioma subgroup analysis ────────────────────────────────────────
# endometrioma_size_clean and endometrioma_laterality are structural NaN:
# only meaningful for patients with endometrioma=1.
# Always print the subgroup N explicitly.

print("=== Endometrioma subgroup variables ===")
print("  IMPORTANT: These variables are structural NaN for patients without endometrioma.")
print("  Analysis is limited to the endometrioma=1 subgroup.")
print()

if "endometrioma" in df_primary.columns:
    _endo1 = df_primary[df_primary["endometrioma"] == 1].copy()
    print(f"  Endometrioma=1 subgroup: N={len(_endo1)} (of {len(df_primary)} total)")
    print(f"  Target in subgroup: 0={int((_endo1[TARGET_COL]==0).sum())}, "
          f"1={int((_endo1[TARGET_COL]==1).sum())}")
    print()

    for col in ["endometrioma_size_clean", "endometrioma_laterality"]:
        if col not in _endo1.columns:
            continue
        _sub  = _endo1[[col, TARGET_COL]].dropna(subset=[col])
        _n_avail = len(_sub)
        _n_miss  = len(_endo1) - _n_avail
        _vtype   = infer_var_type(_endo1[col])
        print(f"  {col}:")
        print(f"    N available (endo=1 with value): {_n_avail}  |  N missing in subgroup: {_n_miss}")
        if _vtype == "numeric":
            s = _sub[col]
            print(f"    Range: [{s.min():.1f}, {s.max():.1f}]  |  Median: {s.median():.1f}  |  "
                  f"IQR: [{s.quantile(0.25):.1f}, {s.quantile(0.75):.1f}]")
            g0s = _sub[_sub[TARGET_COL]==0][col]
            g1s = _sub[_sub[TARGET_COL]==1][col]
            if len(g0s) >= 3 and len(g1s) >= 3:
                pv, eff = mannwhitney_with_effect(g0s, g1s)
                print(f"    Vaginal: {fmt_median_iqr(g0s)}  |  CS: {fmt_median_iqr(g1s)}")
                print(f"    Mann-Whitney: p={pv}, |r|={eff}  (N_analyzed={len(_sub)})")
        else:
            # Small-cell disclosure guard (item J): same n<5 convention as A2.4's
            # categorical breakdown -- a raw value_counts() dict on a subgroup
            # could otherwise expose a near-patient-level cell if a category
            # is rare within this (endometrioma=1) subgroup.
            # Reconstruction-aware (see the main categorical loop's comment
            # above for the full rationale): a combined bucket with only one
            # member, or a combined total still <5, would disclose that one
            # rare category's exact count directly -- and even withholding it
            # would not help, since N_available is printed on the line above
            # and every other category is shown individually. Fold
            # smallest-first until the combined bucket is empty or safely
            # >=5, exactly like the main categorical loop.
            _vc_sub = _sub[col].value_counts()
            _visible_vc, _below_vc_n, _below_vc_k = share_safe.safe_combine_rare_levels(
                {str(k): int(v) for k, v in _vc_sub.items()}, threshold=5
            )
            _vc_parts = [f"counts (categories with n>=5)={_visible_vc}"]
            if _below_vc_k:
                if _below_vc_n is not None and _below_vc_n >= 5:
                    _vc_parts.append(share_safe.format_combined_levels_note(_below_vc_k, _below_vc_n))
                else:
                    _vc_parts.append(
                        f"{_below_vc_k} smaller categor{'y' if _below_vc_k == 1 else 'ies'} "
                        "combined (too few total observations to display safely, suppressed)"
                    )
            print(f"    Value counts: {'; '.join(_vc_parts)}")
        print()

    # Endometrioma size distribution plot
    if "endometrioma_size_clean" in _endo1.columns:
        _sz_sub = _endo1[["endometrioma_size_clean", TARGET_COL]].dropna()
        if len(_sz_sub) >= 10:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
            plot_numeric_dist(_endo1, "endometrioma_size_clean", TARGET_COL, ax1, ax2)
            fig.suptitle(f"Endometrioma size (mm) — subgroup N={len(_sz_sub)} "
                         f"(of {len(_endo1)} with endometrioma=1)", fontsize=13)
            plt.show()
else:
    print("  'endometrioma' column not found in df_primary.")

# Any genuinely manual_review_pending endometriosis surgical-detail variables
# (source ambiguity, not yet statistically tested); membership is read from
# the current variable classification, not a fixed list.
if MANUAL_REVIEW_PENDING_COLS:
    print("=== Endometriosis surgical detail variables (manual_review_pending) ===")
    print("  These are NOT included in statistical tests — source (prior surgery vs current CS)")
    print("  is unconfirmed. Summary for awareness only.")
    for col in MANUAL_REVIEW_PENDING_COLS:
        if col not in df.columns:
            continue
        n_avail  = int(df[col].notna().sum())
        miss_pct = round(df[col].isna().mean() * 100, 1)
        # Small-cell disclosure guard: only report a top value if its
        # count is >=5 (project convention), else omit rather than expose it.
        top_vals = {str(k): int(v) for k, v in df[col].value_counts(dropna=True).head(3).items() if v >= 5}
        print(f"  {col}: N_available={n_avail} ({miss_pct}% missing) | top values (n>=5 only): {top_vals}")
else:
    print("No endometriosis surgical-detail variable is currently classified "
          "manual_review_pending.")
""")


# ── Section A2.9 ────────────────────────────────────────────────────────────────
SB9_HEADER = md("eda-b-s09-header", """
## Section A2.6 — Obstetric and Pregnancy Domain EDA

**Purpose:** Analyse non-endometriosis primary predictors grouped by clinical domain.
Covers all obstetric history, pregnancy complications, and demographic variables.

**What this checks:**
- Demographics / Anthropometry: AGE, BMI, weight, height (Mann-Whitney + boxplot)
- Obstetric history: G, P, CS, nulliparity, S_P_CS, VBAC
- Mode of conception: IVF vs other
- Pregnancy complications: hypertensive disorders, gestational diabetes,
  placental/fetal complications, medications
- Variables with `timing='unclear'`: documented for A2.14 registry (not tested)

**What this does NOT do:**
- Does not resolve timing ambiguity for `timing='unclear'` variables

**Output:** Per-domain association tables + boxplots for anthropometrics. The unified
predictor universe (`PRIMARY_COLS`) already includes
`secondary_near_delivery_predictor` and `intrapartum_predictor_exclude_from_prelabor_model`
variables alongside `predictor_allowed` ones -- there is no separate "future add-on"
reference table; any such variable belonging to a domain group above is analysed here
once, in place, like every other primary predictor. Horizon-specific modeling
eligibility (pre-labor / near-delivery / intrapartum) is decided only at the modeling
boundary, downstream of EDA C -- not in this descriptive section.

Groups: Demographics → Obstetric History → Mode of Conception →
Pregnancy Complications → Medications
""")

SB9_DEMOGRAPHICS = code("eda-b-s09-demographics", """
print("=== Group: Demographics and Anthropometry ===")
_DEMO = ["AGE", "BMI_before", "BMI_after", "weight_before_pregnancy",
         "weight_in_pregnancy", "height"]
_demo_avail = [c for c in _DEMO if c in PRIMARY_COLS]
_g0 = df_primary[df_primary[TARGET_COL] == 0]
_g1 = df_primary[df_primary[TARGET_COL] == 1]

for col in _demo_avail:
    sub = df_primary[[col, TARGET_COL]].dropna(subset=[col])
    g0s = sub[sub[TARGET_COL] == 0]
    g1s = sub[sub[TARGET_COL] == 1]
    pv, eff = mannwhitney_with_effect(g0s[col], g1s[col])
    print(f"  {col:<25} N={len(sub):>3} (miss={df_primary[col].isna().sum()}) "
          f"| overall: {fmt_median_iqr(sub[col])}"
          f" | vaginal: {g0s[col].median():.1f} → CS: {g1s[col].median():.1f}"
          f" | MW p={pv}, |r|={eff}")

# Compact boxplot for key anthropometric vars
_key_demo = [c for c in ["AGE", "BMI_before"] if c in PRIMARY_COLS]
if _key_demo:
    fig, axes = plt.subplots(1, len(_key_demo), figsize=(6*len(_key_demo), 4.2), layout="constrained")
    if len(_key_demo) == 1: axes = [axes]
    for ax, col in zip(axes, _key_demo):
        sub_p = df_primary[[col, TARGET_COL]].dropna().copy()
        sub_p[TARGET_COL] = sub_p[TARGET_COL].astype(str)
        sns.boxplot(data=sub_p, x=TARGET_COL, y=col, hue=TARGET_COL, ax=ax,
                    palette={"0": C0, "1": C1}, width=0.5, linewidth=1.2, legend=False)
        ax.set_title(f"{col}\\n(N={sub_p.shape[0]}, miss={df_primary[col].isna().sum()})", fontsize=12, pad=8)
        ax.set_xlabel("0=Vaginal  1=CS", fontsize=11)
        ax.tick_params(labelsize=10)
    fig.suptitle("Demographics — boxplot by target", fontsize=13)
    plt.show()
print()
""")

SB9_OBSTETRIC = code("eda-b-s09-obstetric", """
# Centralized binary target-stratified display helper: checking each side's
# own within-group complement independently is not sufficient, because it
# misses the cross-group total-positive complement (the same quantity A1's
# Section A6 separately reports as this variable's unstratified n_positive)
# and the other side's own suppression state. Every binary vaginal/CS
# percentage pair in this notebook goes through
# share_safe.suppress_binary_target_display() (shared with A2.4/A2.8/A2.9) via
# this one local formatting wrapper, reused by every cell below that prints
# a binary predictor's target-stratified rate.
def _binary_pct_pair(n_pos0, n_pos1, g0s, g1s):
    _vd, _cd = share_safe.suppress_binary_target_display(
        n_pos0, n_pos1, len(g0s), len(g1s), enabled=SHARE_SAFE_MODE
    )
    _vs = f"{100*n_pos0/len(g0s):.1f}%" if not isinstance(_vd, str) and len(g0s) else (_vd if isinstance(_vd, str) else "—")
    _cs = f"{100*n_pos1/len(g1s):.1f}%" if not isinstance(_cd, str) and len(g1s) else (_cd if isinstance(_cd, str) else "—")
    return _vs, _cs


print("=== Group: Obstetric History ===")
_OB_NUM = ["G", "P", "CS"]
_OB_BIN = ["nulliparity", "S_P_CS", "VBAC"]
_g0 = df_primary[df_primary[TARGET_COL] == 0]
_g1 = df_primary[df_primary[TARGET_COL] == 1]

for col in [c for c in _OB_NUM if c in PRIMARY_COLS]:
    sub = df_primary[[col, TARGET_COL]].dropna(subset=[col])
    g0s = sub[sub[TARGET_COL] == 0]; g1s = sub[sub[TARGET_COL] == 1]
    pv, eff = mannwhitney_with_effect(g0s[col], g1s[col])
    print(f"  {col:<12} N={len(sub):>3} | median: overall={sub[col].median():.1f} "
          f"vaginal={g0s[col].median():.1f} CS={g1s[col].median():.1f} | MW p={pv}, |r|={eff}")

for col in [c for c in _OB_BIN if c in PRIMARY_COLS]:
    sub = df_primary[[col, TARGET_COL]].dropna(subset=[col])
    g0s = sub[sub[TARGET_COL] == 0]; g1s = sub[sub[TARGET_COL] == 1]
    n_pos0 = int((g0s[col] == 1).sum()); n_pos1 = int((g1s[col] == 1).sum())
    sep = (n_pos1 == 0 or len(g1s) - n_pos1 == 0)
    # Canonical dict API -- see the A2.4 binary-loop comment above.
    _res = chi2_or_fisher(col, df_primary, TARGET_COL)
    pv, test = _res["p_value"], _res["test"]
    sep_note = "  ⚠ SEPARATION" if sep else ""
    _vag_disp, _cs_disp = _binary_pct_pair(n_pos0, n_pos1, g0s, g1s)
    print(f"  {col:<20} N={len(sub):>3} | vaginal={_vag_disp} "
          f"CS={_cs_disp} | {test} p={pv}{sep_note}")
print()

print("=== Group: Mode of Conception ===")
col = "mode_of_conception_ivf_vs_all"
if col in PRIMARY_COLS:
    sub = df_primary[[col, TARGET_COL]].dropna(subset=[col])
    g0s = sub[sub[TARGET_COL] == 0]; g1s = sub[sub[TARGET_COL] == 1]
    n_pos0 = int((g0s[col] == 1).sum()); n_pos1 = int((g1s[col] == 1).sum())
    # Canonical dict API -- see the A2.4 binary-loop comment above.
    _res = chi2_or_fisher(col, df_primary, TARGET_COL)
    pv, test = _res["p_value"], _res["test"]
    _vag_disp, _cs_disp = _binary_pct_pair(n_pos0, n_pos1, g0s, g1s)
    print(f"  IVF: vaginal={_vag_disp} CS={_cs_disp} "
          f"| {test} p={pv} (N={len(sub)}, miss={df_primary[col].isna().sum()})")
print()
""")

SB9_COMPLICATIONS = code("eda-b-s09-complications", """
_COMPLICATION_GROUPS = {
    "Hypertensive Disorders": [
        "pregnancy_related_hypertensive_disorder", "PIH", "mild_PET",
        "severe_PET", "any_PET", "SIPET",
    ],
    "Gestational Diabetes": ["gestational_diabetes", "diabetes_type"],
    "Placental / Fetal":    ["PPROM", "placenta_previa", "IUGR",
                              "Fetus_Anamoly", "polyhydramnios"],
    "Medications":          ["aspirin_during_pregnancy", "clexane_during_pregnancy"],
    "General Comorbidity":  ["any_medical_problem", "regular_medications",
                              "smoking", "alcohol"],
}

for _grp_name, _grp_vars in _COMPLICATION_GROUPS.items():
    _avail = [c for c in _grp_vars if c in PRIMARY_COLS]
    if not _avail:
        continue
    print(f"=== Group: {_grp_name} ===")
    for col in _avail:
        sub = df_primary[[col, TARGET_COL]].dropna(subset=[col])
        g0s = sub[sub[TARGET_COL] == 0]; g1s = sub[sub[TARGET_COL] == 1]
        vtype = infer_var_type(df_primary[col])
        n_miss = df_primary[col].isna().sum()
        sep = False
        if vtype == "numeric":
            pv, eff = mannwhitney_with_effect(g0s[col], g1s[col])
            print(f"  {col:<35} N={len(sub):>3} miss={n_miss:>3} "
                  f"| vaginal={g0s[col].median():.1f} CS={g1s[col].median():.1f} "
                  f"| MW p={pv}, |r|={eff}")
        else:
            n_pos0 = int((g0s[col] == 1).sum()) if vtype=="binary" else None
            n_pos1 = int((g1s[col] == 1).sum()) if vtype=="binary" else None
            if vtype == "binary":
                sep = (n_pos1 == 0 or len(g1s) - n_pos1 == 0)
            # Canonical dict API -- see the A2.4 binary-loop comment above.
            _res = chi2_or_fisher(col, df_primary, TARGET_COL)
            pv, test = _res["p_value"], _res["test"]
            # _binary_pct_pair (defined in eda-b-s09-obstetric, the prior
            # cell) applies the shared disclosure protection -- see that
            # cell's comment for the full rationale.
            if n_pos0 is not None and n_pos1 is not None:
                _r0, _r1 = _binary_pct_pair(n_pos0, n_pos1, g0s, g1s)
            else:
                _r0, _r1 = "—", "—"
            sep_note = "  ⚠ SEPARATION" if sep else ""
            print(f"  {col:<35} N={len(sub):>3} miss={n_miss:>3} "
                  f"| vaginal={_r0} CS={_r1} | {test} p={pv}{sep_note}")
    print()

# Timing-unclear variables — note only
_TIMING_UNCLEAR = [c for c in PRIMARY_COLS
                   if TIMING_MAP.get(c, "unknown") == "unclear"]
if _TIMING_UNCLEAR:
    print("=== Variables with UNCLEAR TIMING (→ A2.14 clinical decision registry) ===")
    for col in _TIMING_UNCLEAR:
        print(f"  {col}: timing='unclear' — excluded from main analysis. See A2.14.")
    print()
""")

# NOTE: eda-b-s09-admission-ref (the "SECONDARY NEAR-DELIVERY / LABOR-ADJACENT
# VARIABLES -- Future Add-On Model Reference" cell) was removed 2026-08-13 per
# Decision 65 / the multi-horizon implementation plan Batch 1. Its entire
# purpose was to show secondary_near_delivery_predictor variables in a
# separate side-table because they were excluded from PRIMARY_COLS. Now that
# PRIMARY_COLS is the unified 3-class union (see eda-b-s02-scope), every
# variable ADMISSION_LABOR_COLS used to cover here is already analysed once,
# in place, by the domain-grouped cells above (e.g. PPROM in
# eda-b-s09-complications' "Placental / Fetal" group; BMI_after and
# weight_in_pregnancy in eda-b-s09-demographics) or by the comprehensive
# per-type cells in A2.3/A2.4/A2.7/A2.10/A2.12/A2.13, which iterate all of PRIMARY_COLS
# regardless of domain grouping. Keeping this cell would have shown the same
# variables a second time with a now-incorrect "not in main model" framing.


# ── Collect Part 3 cells ──────────────────────────────────────────────────────
EDA_B_PART3_CELLS = [
    SB6_HEADER, SB6_NUMERIC_PLOTS, SB6_SKEWNESS, SB6_KEY_OBS, SB6_KEY_OBS_CODE,
    SB7_HEADER, SB7_BINARY, SB7_BINARY_FULL_PLOTS, SB7_CATEGORICAL, SB7_CATEGORICAL_PLOTS,
    SB7_KEY_OBS, SB7_KEY_OBS_CODE,
    SB8_HEADER, SB8_ENDO_BINARY, SB8_ENDO_SUBGROUP,
    SB9_HEADER, SB9_DEMOGRAPHICS, SB9_OBSTETRIC, SB9_COMPLICATIONS,
]

if __name__ == "__main__":
    print(f"EDA A2 Part 3 cells defined: {len(EDA_B_PART3_CELLS)}")

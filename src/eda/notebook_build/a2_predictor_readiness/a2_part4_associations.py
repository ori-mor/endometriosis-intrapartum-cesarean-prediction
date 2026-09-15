#!/usr/bin/env python3
"""EDA A2 — Part 4: cell definitions (displayed as sections A2.9-A2.11; this file's
own historical section IDs remain B10-B12 -- see the 2026-08-08 reorg note in
build_a2_notebook.py).

Sections:
  A2.9 (was B10) — Bivariate association + BH-FDR (full ranked table, primary predictors)
  A2.10 (was B11, B11b, B11c) — Predictor-predictor relationships and redundancy:
      A2.10a numeric x numeric (was B11's Spearman correlation block)
      A2.10b numeric x categorical (was B11b)
      A2.10c categorical x categorical (was B11's Cramer's V block, previously
           untitled as its own subsection)
      A2.10d redundancy review: clinical redundancy groups + mode_of_conception
           example (was B11's redundancy-groups block + B11c)
  A2.11 (was B12) — Outlier screening (IQR rule + 3-tier decision framework)

Depends on: df_primary, PRIMARY_COLS, PRIORITY_VARS, TARGET_COL,
all config vars, and helpers from Part 1.
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


# ── Section A2.10 ───────────────────────────────────────────────────────────────
SB10_HEADER = md("eda-b-s10-header", """
## Section A2.9 — Predictor–Target Associations (BH-FDR Corrected)

**Purpose:** Rank all primary predictors by their univariate association with
`target_intrapartum_cs`. This is the complete, formal association test; its result
(`assoc_df`) is reused directly by Section A2.12's comprehensive summary table rather
than being recomputed there.

**What this checks:**
- Mann-Whitney U + rank-biserial |r| for numeric predictors
- Chi-square or Fisher exact + Cramér's V for binary/categorical predictors
- Test type auto-selected based on variable type
- Benjamini-Hochberg FDR correction across all primary predictors

**What this does NOT do:**
- This is univariate screening only — NOT feature selection
- A non-significant p-value does NOT mean the variable should be excluded
- Clinical priority is considered alongside statistical evidence: statistical
  non-significance alone does not justify exclusion, and clinical priority alone does
  not justify inclusion either — `clinical_priority_flag` is a descriptive label, not
  a decision rule
- Multivariate interactions are not tested here

**Output:** Full ranked association table (`assoc_df`) with per-group N, per-group
missing N, direction of association, effect sizes (with a descriptive small/
moderate/large label), p-values, BH-FDR q-values, and a clinical-priority flag

`clinical_priority_flag`: marks variables with a pre-specified clinical priority
(CLINICAL_TIER ≥ 2, assigned in Part 1 independently of this section's statistical
results). This is a descriptive label on the table, not a decision A2.9 makes -- it
does not itself retain, include, or exclude any variable from a model.
""")

SB10_ASSOC = code("eda-b-s10-assoc", """
# Clinically important variables -- pre-specified priority, independent of p-value.
# This flag is descriptive (it marks pre-specified clinical priority on the
# table); it is not A2.9 making a retention decision.
_CLINICAL_PRIORITY_SET = set(c for c, t in CLINICAL_TIER.items() if t >= 2)


def _effect_magnitude(vtype, eff):
    # Simplified descriptive small/moderate/large heuristic used for this A2
    # display only -- a convenient reading aid, not a validated universal
    # convention, and never used to filter or exclude a variable.
    if eff is None or (isinstance(eff, float) and np.isnan(eff)):
        return "—"
    if vtype == "numeric":  # rank-biserial |r|
        return "small" if eff < 0.3 else ("moderate" if eff < 0.5 else "large")
    # Cramer's V, binary target: three-label small/moderate/large bands at
    # <0.30 / 0.30-<0.50 / >=0.50 -- matches the numeric rank-biserial |r|
    # bands above (same three-level convention, not a separate cutoff set).
    # e.g. adenomyosis_sonographic_features_clean at V~0.457 -> "moderate",
    # not "large" (that requires V>=0.50).
    # Cramer's V from a sparse/high-cardinality table should still be read
    # alongside N, table_shape, sparse_cell_flag, and the p/q columns above --
    # this banding does not by itself validate or invalidate the statistic.
    return "small" if eff < 0.3 else ("moderate" if eff < 0.5 else "large")


_assoc_rows = []
for col in PRIMARY_COLS:
    vtype  = infer_var_type(df_primary[col])
    sub    = df_primary[[col, TARGET_COL]].dropna(subset=[col])
    n      = len(sub)
    n_miss = df_primary[col].isna().sum()
    g0s    = sub[sub[TARGET_COL] == 0]
    g1s    = sub[sub[TARGET_COL] == 1]
    n_miss_0 = int(df_primary.loc[df_primary[TARGET_COL] == 0, col].isna().sum())
    n_miss_1 = int(df_primary.loc[df_primary[TARGET_COL] == 1, col].isna().sum())
    _min_exp, _table_shape, _n_levels, _sparse_flag = None, "—", None, None
    _has_small_cell = False

    if vtype == "numeric":
        pval, eff = mannwhitney_with_effect(g0s[col], g1s[col])
        test = "Mann-Whitney U"
        summ_0 = fmt_median_iqr(g0s[col])
        summ_1 = fmt_median_iqr(g1s[col])
        if pd.notna(g0s[col].median()) and pd.notna(g1s[col].median()):
            direction = ("higher in intrapartum CS" if g1s[col].median() > g0s[col].median()
                         else ("higher in vaginal" if g1s[col].median() < g0s[col].median() else "equal medians"))
        else:
            direction = "—"
    else:
        # Canonical dict API. No broad except here: chi2_or_fisher() and its
        # underlying contingency_association_test() already handle every
        # expected statistical edge case internally (sparse 2x2 -> deterministic
        # exact Fisher; sparse r x c -> deterministic fixed-seed Monte Carlo
        # Fisher-Freeman-Halton). An unexpected failure on a validated,
        # non-empty PRIMARY_COLS column should fail loudly rather than
        # silently render as p=None/test="error" -- a silent fallback there
        # would mask a real API-mismatch bug.
        _res = chi2_or_fisher(col, df_primary, TARGET_COL)
        pval, test = _res["p_value"], _res["test"]
        _min_exp, _table_shape = _res["min_expected_cell"], _res["table_shape"]
        _n_levels, _sparse_flag = _res["n_levels"], _res["sparse_flag"]
        ct  = pd.crosstab(sub[col], sub[TARGET_COL])
        eff = cramers_v(ct)
        # For a multi-level categorical
        # variable, this row's N_vaginal/N_cs marginals are the row/column
        # totals of the SAME crosstab (ct) whose individual cells Section
        # A2.4 displays (folding rare levels together via
        # safe_combine_rare_levels()). If ANY cell of ct is a protected
        # small count (1-4), showing N_vaginal/N_cs here -- unconditionally,
        # regardless of what A2.4 folds -- lets a reader recover the hidden
        # level's exact vaginal/CS split by subtracting every OTHER level
        # A2.4 shows individually from these marginals (e.g. endometrioma_
        # place_clean: N_cs=25, two visible levels 11+10 -> hidden level's
        # CS=4). Complementary-suppress N_vaginal/N_cs/N_missing_vaginal/
        # N_missing_cs for this row whenever this is possible.
        _has_small_cell = bool(vtype != "binary" and ((ct >= 1) & (ct <= 4)).any().any())
        # Centralized binary display protection: share_safe.suppress_binary_
        # target_display() (shared with A2.4/A2.6/A2.8) checks each side's
        # own within-group complement together with the cross-group
        # total-positive complement A1's Section A6 separately reports
        # (n_positive = this row's own two event counts, summed), and with
        # the other side's own suppression state.
        if vtype == "binary":
            _n_pos0, _n_pos1 = int((g0s[col] == 1).sum()), int((g1s[col] == 1).sum())
            _vd, _cd = share_safe.suppress_binary_target_display(
                _n_pos0, _n_pos1, len(g0s), len(g1s), enabled=SHARE_SAFE_MODE
            )
            summ_0 = f"{100*_n_pos0/len(g0s):.1f}%" if not isinstance(_vd, str) and len(g0s) else (_vd if isinstance(_vd, str) else "—")
            summ_1 = f"{100*_n_pos1/len(g1s):.1f}%" if not isinstance(_cd, str) and len(g1s) else (_cd if isinstance(_cd, str) else "—")
        else:
            summ_0, summ_1 = "—", "—"
        if vtype == "binary" and len(g0s) and len(g1s):
            _r0 = (g0s[col]==1).mean(); _r1 = (g1s[col]==1).mean()
            direction = ("higher in intrapartum CS" if _r1 > _r0
                         else ("higher in vaginal" if _r1 < _r0 else "equal rates"))
        else:
            direction = "see level-wise rates (A2.4)"

    _assoc_rows.append({
        "variable":    col,
        "earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(col),
        "type":        vtype,
        "N":           n,
        "N_missing":   n_miss,
        # Raw/unsuppressed -- this dataframe (assoc_df) is the underlying
        # analytical result and must not be altered; a separate display
        # copy (_assoc_display, built below after assoc_df/BH-FDR) applies
        # cross-section suppression for the printed table only.
        "N_vaginal":   len(g0s), "N_cs": len(g1s),
        "N_missing_vaginal": n_miss_0, "N_missing_cs": n_miss_1,
        # Internal-only flag (dropped from the printed table, like
        # N_complete_case for numcat_df) -- True whenever this categorical
        # variable's A2.4 crosstab contains a protected small cell (1-4),
        # meaning N_vaginal/N_cs/N_missing_vaginal/N_missing_cs must be
        # complementary-suppressed in the display copy (see the cross-
        # section rationale above).
        "_has_small_cell": _has_small_cell,
        "vaginal_summ": summ_0,
        "cs_summ":     summ_1,
        "direction":   direction,
        "test":        test,
        "table_shape": _table_shape,
        "n_levels":    _n_levels,
        "min_expected_cell": _min_exp,
        "sparse_cell_flag": _sparse_flag,
        # Full-precision computational value -- never rounded. p_value_display
        # is formatting only (see fmt_pval()) and must never be reused
        # programmatically (BH input, ranking, threshold comparison).
        "p_value":     pval,
        "p_value_display": fmt_pval(pval),
        "effect_size": eff if not isinstance(eff, str) else None,
        "effect_size_display": fmt_effect(eff if not isinstance(eff, str) else None),
        "effect_magnitude": _effect_magnitude(vtype, eff if not isinstance(eff, str) else None),
        "clinical_priority_flag": col in _CLINICAL_PRIORITY_SET,
    })

assoc_df = (pd.DataFrame(_assoc_rows)
            .sort_values("effect_size", ascending=False, na_position="last"))
# BH-FDR always receives the full-precision, unrounded p_value column above
# -- never p_value_display.
assoc_df["q_value_bh"] = benjamini_hochberg(assoc_df["p_value"]).values
assoc_df["fdr_sig"]    = assoc_df["q_value_bh"] < 0.05
assoc_df["q_value_bh_display"] = assoc_df["q_value_bh"].apply(fmt_pval)

print(f"Association ranking — {len(assoc_df)} primary predictors tested")
print(f"(Vaginal n={n0}, Intrapartum CS n={n1})")
print(f"  Raw p<0.05:    {int((assoc_df['p_value'] < 0.05).sum())} variable(s)")
print(f"  BH-FDR q<0.05: {int(assoc_df['fdr_sig'].sum())} variable(s)")
print()
# Cross-section display copy: N_vaginal/N_cs/N_missing_vaginal/N_missing_cs
# are complementary-suppressed for any row flagged _has_small_cell above --
# assoc_df itself (sorted, BH-FDR-annotated) is unaffected.
_assoc_display = assoc_df.copy()
for _col_name in ("N_vaginal", "N_cs", "N_missing_vaginal", "N_missing_cs"):
    _assoc_display[_col_name] = [
        share_safe.COMPLEMENTARY_SUPPRESSION_LABEL if (_flag and SHARE_SAFE_MODE) else _val
        for _flag, _val in zip(assoc_df["_has_small_cell"], assoc_df[_col_name])
    ]
_show = ["variable","earliest_entry_stage","type","N","N_vaginal","N_cs","N_missing_vaginal","N_missing_cs",
         "vaginal_summ","cs_summ","direction","test","table_shape","min_expected_cell",
         "sparse_cell_flag","p_value_display","q_value_bh_display","fdr_sig",
         "effect_size_display","effect_magnitude","clinical_priority_flag"]
print(f"BH-FDR-significant findings (q<0.05, N={int(assoc_df['fdr_sig'].sum())}):")
_assoc_sig_display = _assoc_display[assoc_df["fdr_sig"]]
if len(_assoc_sig_display):
    print(_assoc_sig_display[_show].to_string(index=False))
else:
    print("  (none)")
print()
print("Interpretation: FDR threshold is screening — not feature selection. This is")
print("univariate association only; it does not establish multivariable predictive")
print("value, and a large effect size does not by itself prove clinical relevance")
print("or vice versa. No variable is removed from PRIMARY_COLS based on this table.")
print("p_value/effect_size are stored at full precision internally; the display columns")
print("above show display-formatted values only (see fmt_pval/fmt_effect). The full")
print("assoc_df table (all primary predictors, unrounded) remains available in memory.")
print()
print("Pre-specified clinical priority (CLINICAL_TIER>=2, independent of p-value):")
for _, r in assoc_df[assoc_df["clinical_priority_flag"]].iterrows():
    print(f"  {r['variable']}: effect={r['effect_size_display']} ({r['effect_magnitude']}), p={r['p_value_display']}")
""")

SB10_KEY_OBS = md("eda-b-s10-key-observations", """**Key observations — predictor-vs-target association:**""")

SB10_KEY_OBS_CODE = code("eda-b-s10-key-observations-code", """
print(f"- {len(assoc_df)} primary predictors screened; "
      f"{int((assoc_df['p_value'] < 0.05).sum())} reach raw p<0.05, "
      f"{int(assoc_df['fdr_sig'].sum())} reach BH-FDR q<0.05.")
_ko10_large = assoc_df[assoc_df["effect_magnitude"] == "large"]
if len(_ko10_large):
    print(f"- Large observed univariate effect-size category: {_ko10_large['variable'].tolist()} "
          f"({_ko10_large['effect_size_display'].tolist()}) -- this is a descriptive "
          f"effect-size label only. It does not imply statistical significance, does not "
          f"establish predictive robustness, and should be interpreted cautiously for "
          f"sparse/high-cardinality tables (see table_shape/sparse_cell_flag above).")
else:
    print("- No primary predictor falls into the 'large' descriptive effect-size category "
          "under the corrected thresholds in this cohort.")
_ko10_priority_nonsig = assoc_df[assoc_df["clinical_priority_flag"] & (assoc_df["p_value"] >= 0.05)]
if len(_ko10_priority_nonsig):
    print(f"- {len(_ko10_priority_nonsig)} clinically pre-prioritized variable(s) are not "
          f"statistically significant here (non-significance does not itself justify "
          f"exclusion) -- requires consideration during Feature Selection alongside "
          f"clinical judgment.")
print("- No variable is added to or removed from PRIMARY_COLS based on this table.")
""")


# ── Section A2.10 (was B11 / B11b / B11c) ────────────────────────────────────────
SB11_HEADER = md("eda-b-s11-header", """
## Section A2.10 — Predictor–Predictor Relationships and Redundancy

**Purpose:** Identify pairs of primary predictors that are statistically or clinically
redundant, using `REDUNDANCY_GROUPS` (A2.10d). Redundancy groups are of two kinds, not
one: some are prespecified/clinical, defined ahead of time from derivation or clinical
overlap; others are association-informed, defined from the A2.10a–A2.10c signals themselves
and reviewed for redundancy, not decided in advance. A candidate representative is
proposed only where a group's provenance actually supports designating one -- several
groups intentionally have no representative (`representative=None`) and are surfaced for
review rather than auto-resolved. Organized into four sub-sections:
- **A2.10a** — numeric × numeric (Spearman correlation)
- **A2.10b** — numeric × categorical (Mann-Whitney U / Kruskal-Wallis)
- **A2.10c** — categorical × categorical (Cramér's V)
- **A2.10d** — redundancy review (`REDUNDANCY_GROUPS` + a worked example)

**What this does NOT do (applies across A2.10a–A2.10d):**
- Redundancy group membership, or a high-correlation/high-association flag, does not
  automatically exclude a variable
- A proposed candidate representative, where one exists, is a prespecified/provisional
  redundancy-review proposal, not a final feature-selection or exclusion decision -- and
  no representative is proposed at all for groups without one
- Final redundancy decisions require clinical review

**Important note on `gestational_age_at_PPROM_days`:**
This variable is numeric (a member of `_num_cols`) and, under its current
classification, does not enter the categorical x categorical Cramér's V screening
in A2.10c at all -- an earlier claim of a "V=1.0" pair involving it is stale and
must not be read as a current result. The current relevant finding is a **Spearman**
pair in A2.10a below: `gestational_age_at_PPROM_days` x `gestational_age_at_delivery_days`,
N=16, rho~=0.993. This pairwise N is very small (16 of 431 rows), so the estimate is
unstable and weakly generalizable -- a strong observed correlation at this N does
**not** by itself establish redundancy. It should not be described as definitively a
"statistical artefact"; the defensible statement is that it requires low-N caution,
not a dismissal.
""")

SB10A_HEADER = md("eda-b-s10a-header", """
### A2.10a — Numeric × Numeric

**What this checks:**
- Spearman correlation for all numeric-numeric pairs (|ρ| ≥ 0.7 flagged)
- Spearman matrix is computed on complete-case pairs (sample size noted per pair)
- Spearman asymptotic/approximate p-value (scipy `spearmanr`, same complete-case pair
  as rho) — this is an asymptotic (t-distribution-based) approximation, not an exact
  or permutation p-value; scipy's own documentation notes it is only accurate for
  large samples (>500 observations). Pairs with a small complete-case N (e.g. the
  `gestational_age_at_PPROM_days` pairs, N=16) should be interpreted with caution
  regardless of how small the displayed p-value is. BH-FDR-adjusted p-value is also
  computed across the full pairwise table, alongside a same-redundancy-family flag.
- Scatterplots for every numeric-numeric pair reaching raw/nominal p<0.05
  (uncorrected — see the BH-FDR q-value column for the multiplicity-adjusted result),
  paginated for readability — not an unreadable all-pairs wall of plots, and not
  restricted to only the high-correlation/same-family subset. |rho|>=0.7 pairs remain
  separately flagged as potential redundancy in each subplot title and in the printed
  list — see the cell immediately below the heatmap/table.

**Output:** Spearman heatmap + pairwise table + scatterplots for pairs at raw p<0.05
""")

SB11_CORR = code("eda-b-s11-corr", """
_num_cols = [c for c in PRIMARY_COLS if infer_var_type(df_primary[c]) == "numeric"]
_CORR_THRESH = 0.7

_num_family = {}
for _gname, _gdef in REDUNDANCY_GROUPS.items():
    for _m in _gdef["members"]:
        _num_family[_m] = _gname

if len(_num_cols) >= 2:
    _corr = df_primary[_num_cols].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(max(9, len(_num_cols)*0.75),
                                     max(7, len(_num_cols)*0.75)),
                            layout="constrained")
    sns.heatmap(_corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
                vmin=-1, vmax=1, ax=ax, annot_kws={"size": 9}, linewidths=0.3,
                cbar_kws={"label": "Spearman rho"})
    ax.set_title("Spearman correlation — primary numeric predictors", fontsize=14, pad=12)
    ax.tick_params(axis="x", labelsize=10, rotation=45)
    ax.tick_params(axis="y", labelsize=10, rotation=0)
    plt.setp(ax.get_xticklabels(), ha="right")
    cbar = ax.collections[0].colorbar
    cbar.ax.tick_params(labelsize=10)
    cbar.set_label("Spearman rho", fontsize=11)
    plt.show()

    _high_corr_pairs = []
    _corr_pair_rows = []
    _cols = _corr.columns.tolist()
    for i in range(len(_cols)):
        for j in range(i+1, len(_cols)):
            _pair = df_primary[[_cols[i], _cols[j]]].dropna()
            _n_original = len(df_primary)
            _n_complete = len(_pair)
            _n_dropped = _n_original - _n_complete
            rho = _corr.iloc[i, j]
            # Asymptotic/approximate pairwise p-value (NOT exact/permutation --
            # scipy.stats.spearmanr uses a t-distribution approximation, accurate
            # per scipy's own docs only for large samples >500) via scipy on the
            # same complete-case pair; not derivable from the correlation matrix
            # alone. Small-N pairs (e.g. N=16) should be read with caution
            # regardless of how small the displayed p-value is -- see A2.10a header.
            if _n_complete >= 3:
                _rho_exact, _pv = stats.spearmanr(_pair[_cols[i]], _pair[_cols[j]])
            else:
                _pv = np.nan
            _same_family = (
                _cols[i] in _num_family and _cols[j] in _num_family
                and _num_family[_cols[i]] == _num_family[_cols[j]]
            )
            # Full-precision computational values -- never rounded; *_display
            # columns are formatting only (see fmt_pval()/fmt_effect()).
            _pair_result = {
                "var1": _cols[i],
                "var2": _cols[j],
                "N_original": _n_original,
                "N_complete_pair": _n_complete,
                "N_missing_or_dropped": _n_dropped,
                "spearman_rho": float(rho) if pd.notna(rho) else np.nan,
                "spearman_rho_display": fmt_effect(rho if pd.notna(rho) else None),
                "p_value": float(_pv) if pd.notna(_pv) else np.nan,
                "p_value_display": fmt_pval(_pv if pd.notna(_pv) else None),
                "high_corr_flag": bool(pd.notna(rho) and abs(rho) >= _CORR_THRESH),
                "same_redundancy_family": _same_family,
                "redundancy_family": _num_family.get(_cols[i]) if _same_family else "—",
            }
            _corr_pair_rows.append(_pair_result)
            if pd.notna(rho) and abs(rho) >= _CORR_THRESH:
                _high_corr_pairs.append(_pair_result)

    _corr_pair_df = pd.DataFrame(_corr_pair_rows)
    # BH-FDR always receives the full-precision, unrounded p_value column.
    _corr_pair_df["q_value_bh"] = benjamini_hochberg(_corr_pair_df["p_value"]).values
    _corr_pair_df["q_value_bh_display"] = _corr_pair_df["q_value_bh"].apply(fmt_pval)
    _corr_show = ["var1", "var2", "N_original", "N_complete_pair", "N_missing_or_dropped",
                  "spearman_rho_display", "p_value_display", "q_value_bh_display",
                  "high_corr_flag", "same_redundancy_family", "redundancy_family"]
    print(f"Pairwise Spearman correlation — {len(_corr_pair_df)} numeric pairs evaluated "
          f"with complete-case denominators (BH-FDR applied across all pairs):")
    print(f"  Pairs with |rho|>={_CORR_THRESH}: {len(_high_corr_pairs)}")
    print()
    print("Caution: p-values above are scipy's asymptotic Spearman approximation, not exact/")
    print("permutation p-values -- accuracy is not guaranteed for pairs with a small complete-case")
    print("N (e.g. the gestational_age_at_PPROM_days pairs, N=16). A very small asymptotic p-value")
    print("at low N should not be read as equivalent in reliability to the same p-value at N=431.")
    print()
    if _high_corr_pairs:
        print(f"High-correlation / redundancy-review pairs (|rho|>={_CORR_THRESH}):")
        print(_corr_pair_df[_corr_pair_df["high_corr_flag"]][_corr_show].to_string(index=False))
    else:
        print(f"No numeric pairs with |rho|>={_CORR_THRESH}.")
    print()
    print("Note: |rho| >= 0.7 is a screening flag only. No variable is deleted here")
    print("solely for high correlation -- see A2.10d redundancy groups below and A2.13")
    print("for how redundancy is actually resolved (demotion, not deletion).")
    print("The full pairwise correlation table (_corr_pair_df, all pairs) remains available")
    print("in memory.")
else:
    print(f"Fewer than 2 numeric primary predictors — correlation skipped.")
    _high_corr_pairs = []
    _corr_pair_df = pd.DataFrame()
""")

SB11_SCATTER = code("eda-b-s11-scatter", """
# Scatterplots for EVERY numeric-numeric pair reaching raw/nominal p<0.05
# (uncorrected -- see the BH-FDR q-value column in the table above for the
# multiplicity-adjusted result) on its Spearman correlation -- all eligible
# pairs are screened in the table above; this cell visualizes all of the
# raw-p-significant ones, paginated to avoid an unreadable wall of plots.
# |rho|>=0.7 pairs and same-redundancy-family pairs are additionally flagged
# in their subplot title as potential redundancy -- flagging is a screening
# signal only, never an automatic deletion; the final call belongs to
# Feature Selection (clinical meaning, timing, missingness, source/derived
# status, modeling relevance).
_scatter_pairs = []
if len(_corr_pair_df):
    for _, r in _corr_pair_df.iterrows():
        if pd.notna(r["p_value"]) and r["p_value"] < 0.05:
            _scatter_pairs.append((r["var1"], r["var2"], r))

# De-duplicate while preserving order
_seen_pairs = set()
_scatter_pairs_dedup = []
for v1, v2, r in _scatter_pairs:
    key = tuple(sorted([v1, v2]))
    if key not in _seen_pairs:
        _seen_pairs.add(key)
        _scatter_pairs_dedup.append((v1, v2, r))

if not _scatter_pairs_dedup:
    print("No numeric-numeric pairs reached raw p<0.05 — no scatterplots generated.")
else:
    _n_sc = len(_scatter_pairs_dedup)
    _NCOLS_SC = 3
    _PER_PAGE = 6  # 2 x 3 grid per page -- a 3x4/12-panel page was too dense for report reuse
    _n_pages = int(np.ceil(_n_sc / _PER_PAGE))
    print(f"All eligible numeric-numeric pairs screened: {len(_corr_pair_df)}. "
          f"Pairs visualized here (raw p<0.05): {_n_sc}, across {_n_pages} page(s).")
    for _page in range(_n_pages):
        _page_pairs = _scatter_pairs_dedup[_page * _PER_PAGE:(_page + 1) * _PER_PAGE]
        _nrows_sc = int(np.ceil(len(_page_pairs) / _NCOLS_SC))
        fig, axes = plt.subplots(_nrows_sc, _NCOLS_SC,
                                  figsize=(6.8 * _NCOLS_SC, 5.6 * _nrows_sc),
                                  layout="constrained")
        axes = np.array(axes).reshape(-1)
        for i, (v1, v2, r) in enumerate(_page_pairs):
            ax = axes[i]
            _sub = df_primary[[v1, v2, TARGET_COL]].dropna()
            for _tval, _color, _label in [(0, C0, "Vaginal"), (1, C1, "Intra-CS")]:
                _pts = _sub[_sub[TARGET_COL] == _tval]
                ax.scatter(_pts[v1], _pts[v2], alpha=0.45, s=20, color=_color,
                           label=f"{_label} (n={len(_pts)})")
            _flag = ""
            if r["high_corr_flag"]:
                _flag = "  [|rho|>=0.7: potential redundancy]"
            elif r["same_redundancy_family"]:
                _flag = f"  [same family: {r['redundancy_family']}]"
            ax.set_xlabel(v1, fontsize=11.5)
            ax.set_ylabel(v2, fontsize=11.5)
            ax.tick_params(labelsize=10.5)
            # Display-formatted values (fmt_effect()/fmt_pval(), already
            # computed in _corr_pair_df above) -- not the raw full-precision
            # floats, which can render as very long strings (e.g. a p-value
            # like 7.393711705479312e-121) and visually overflow into the
            # neighboring subplot's title area. Formatting only; the
            # underlying _corr_pair_df/statistics are unchanged.
            ax.set_title(f"{v1} vs {v2}{_flag}\\nN={len(_sub)}, rho={r['spearman_rho_display']}, "
                         f"p={r['p_value_display']}", fontsize=11, wrap=True, pad=9)
            if i == 0:
                ax.legend(fontsize=10, loc="best")
        for j in range(len(_page_pairs), len(axes)):
            axes[j].set_visible(False)
        fig.suptitle(f"Numeric-numeric pairs with raw p<0.05 — page {_page + 1}/{_n_pages} "
                     f"(colored by target; correlation does not imply causation)",
                     fontsize=13)
        plt.show()
    print(f"Shown: {_n_sc} pair(s) with raw p<0.05, across {_n_pages} page(s). Units are the "
          f"original clinical scale (counts, mm, years as applicable). No fitted trend "
          f"line is shown; Spearman rho/p already summarize monotonic association.")
""")

SB11_NN_KEY_OBS = md("eda-b-s11-nn-key-observations", """**Key observations — numeric-numeric relationships:**""")

SB11_NN_KEY_OBS_CODE = code("eda-b-s11-nn-key-observations-code", """
if len(_corr_pair_df):
    print(f"- {len(_corr_pair_df)} eligible numeric-numeric pairs screened; "
          f"{int((_corr_pair_df['p_value'] < 0.05).sum())} reached raw p<0.05 and are "
          f"visualized above; {len(_high_corr_pairs)} exceed |rho|>=0.7.")
    if _high_corr_pairs:
        # Group by pre-specified redundancy family rather than a single blanket
        # "count/anthropometry" label -- a pair with no registered family (e.g. the
        # gestational-timing PPROM/delivery pair) is not the same kind of finding as
        # a parity-count or weight/BMI pair and must not be summarized as if it were.
        _hc_by_family = {}
        for p in _high_corr_pairs:
            _hc_by_family.setdefault(p["redundancy_family"], []).append(p)
        for _fam, _pairs in _hc_by_family.items():
            _fam_label = _fam if _fam != "—" else "no pre-specified redundancy family"
            print(f"- Potential redundancy (|rho|>=0.7), {_fam_label}: "
                  f"{[(p['var1'], p['var2']) for p in _pairs]}")
            for p in _pairs:
                if p["N_complete_pair"] < 30:
                    print(f"    CAUTION: {p['var1']} <--> {p['var2']} has only "
                          f"N={p['N_complete_pair']} complete-case pairs -- a small, "
                          f"weakly generalizable sample; the strong observed correlation "
                          f"does NOT by itself establish redundancy at this N.")
        print("- Requires consideration during Feature Selection, not resolved here.")
    print("- No numeric predictor is removed or transformed based on this screening.")
else:
    print("- Fewer than 2 numeric primary predictors; correlation screening skipped.")
""")


# ── Section A2.10b — Numeric x Categorical Predictor Relationships ─────────────
SB11_NUMCAT_HEADER = md("eda-b-s11b-numcat-header", """
### A2.10b — Numeric × Categorical Predictor Relationships

**Purpose:** Systematically screen relationships between eligible numeric predictors and
eligible categorical/binary predictors -- predictor-predictor, not predictor-vs-target
(A2.9 already covers vs-target). This closes the gap between A2.10a's numeric-numeric
correlation (above) and the categorical-categorical screening (below, A2.10c), completing
predictor-predictor relationship coverage for the primary predictor set.

**What this checks:**
- Every (numeric predictor, categorical/binary predictor) pair among `PRIMARY_COLS`
- 2 groups -> Mann-Whitney U (+ rank-biserial |r|)
- 3+ groups -> Kruskal-Wallis (+ epsilon-squared)
- Analytical N and per-group N for every pair (complete cases for that pair only)
- Pairs with fewer than 2 usable groups (a group needs >=3 observations to be tested)
  are skipped and reported separately, never silently dropped
- Benjamini-Hochberg FDR across all screened pairs (informational)

**What this does NOT do:**
- Does not assume normality — tests are nonparametric by design, matching the
  numeric-vs-target approach already used in A2.9
- Does not remove, impute, or transform any variable
- Does not decide feature inclusion — exploratory screening only

**Output:** Full screening table (`numcat_df`, all eligible pairs) + paginated boxplots
for the subset that reaches BH-FDR q<0.05, OR reaches raw/nominal p<0.05 **and** has a
moderate-or-larger effect size (both conditions are required together on the raw-p
branch — a moderate/large effect size alone, without raw p<0.05, is **not** sufficient
to be plotted; such pairs remain visible in the full `numcat_df` table but are not
plotted here). The screening table is comprehensive; plots are selective by design
(see Key observations below for the exact all-screened vs. visualized counts).
""")

SB11_NUMCAT_SCREEN = code("eda-b-s11b-numcat-screen", """
def _kw_epsilon_squared(H, k, n):
    # Epsilon-squared effect size for Kruskal-Wallis (Tomczak & Tomczak, 2014) --
    # same descriptive small/moderate/large convention as eta-squared.
    if n <= k:
        return np.nan
    return (H - k + 1) / (n - k)


def _numcat_effect_magnitude(effect_type, eff):
    if eff is None or (isinstance(eff, float) and np.isnan(eff)):
        return "—"
    if effect_type == "rank_biserial_r":
        return "small" if eff < 0.3 else ("moderate" if eff < 0.5 else "large")
    return "small" if eff < 0.06 else ("moderate" if eff < 0.14 else "large")  # epsilon-squared


_catlike_cols = [c for c in PRIMARY_COLS if infer_var_type(df_primary[c]) in ("binary", "categorical")]
print(f"Numeric predictors: {len(_num_cols)} | Categorical/binary predictors: {len(_catlike_cols)}")
print(f"Total eligible numeric x categorical pairs: {len(_num_cols) * len(_catlike_cols)}")
print()

_numcat_rows = []
_numcat_skipped = []
for _num in _num_cols:
    for _cat in _catlike_cols:
        _sub = df_primary[[_num, _cat]].dropna()
        _n_complete = len(_sub)
        _grp = _sub.groupby(_cat)[_num]
        _group_ns_all = _grp.size().to_dict()
        _groups = {lvl: vals.values for lvl, vals in _grp if len(vals) >= 3}
        _n_groups_total = _sub[_cat].nunique()
        if len(_groups) < 2:
            _numcat_skipped.append({
                "numeric": _num, "categorical": _cat, "N": _n_complete,
                "n_groups_total": _n_groups_total,
                "n_groups_usable": len(_groups),
                "reason": "fewer than 2 groups with >=3 observations",
            })
            continue
        _k = len(_groups)
        # N actually entering the test -- may be smaller than _n_complete
        # whenever one or more category levels have <3 observations (those
        # levels are excluded from the test but were part of the complete-
        # case pair). This is the denominator that must be reported as the
        # pair's primary "N" -- see the restricted-level fields below.
        _n_tested = sum(len(v) for v in _groups.values())
        _n_levels_excluded_lt3 = _n_groups_total - _k
        if _k == 2:
            _g0, _g1 = list(_groups.values())
            _stat, _pval = stats.mannwhitneyu(_g0, _g1, alternative="two-sided")
            _eff = abs(1 - (2 * _stat) / (len(_g0) * len(_g1)))
            _test, _eff_type = "Mann-Whitney U", "rank_biserial_r"
        else:
            _stat, _pval = stats.kruskal(*_groups.values())
            _eff = _kw_epsilon_squared(_stat, _k, _n_tested)
            _test, _eff_type = "Kruskal-Wallis", "epsilon_squared"
        # Share-safe: group_Ns_str must not suppress each category's group
        # size INDEPENDENTLY via plain safe_count(), because N_tested (the
        # sum of the >=3-observation groups) is printed alongside this string
        # in the same row/panel (e.g. a plot title). A safe-looking large
        # group next to a safe N_tested still discloses a small remaining
        # group by subtraction (e.g. N_tested=16, one group=13 -> the other
        # group=3, exactly the reconstruction this project's own share_safe
        # module warns about).
        # share_safe.safe_combine_rare_levels() (the same helper already
        # used for A2.4/A2.7/Stage2-3's own level-count breakdowns) is the
        # correct general approach here too: it protects against a reader who
        # knows the overall total and the individually-shown level totals,
        # by folding small levels together until the combined bucket is
        # itself either empty or safely >=5.
        # Built from _groups (the >=3-observation
        # subset actually entering the test, matching _n_tested exactly), NOT
        # _group_ns_all (every level, matching the DELIBERATELY-hidden
        # _n_complete/N_complete_case). safe_combine_rare_levels() already
        # protects any single rare level's exact count from being isolated
        # within this breakdown -- but the breakdown's own SUM is just as
        # disclosive as a single number: summing to _n_complete would silently
        # defeat N_complete_case's own suppression (see the comment on
        # N_complete_case above) by letting a reader recompute it directly
        # from the visible parts. Summing to _n_tested instead reveals nothing
        # beyond what N_tested (already safely printed elsewhere) discloses.
        _group_ns_tested = {lvl: len(vals) for lvl, vals in _groups.items()}
        _group_ns_visible, _group_ns_combined_n, _group_ns_combined_k = share_safe.safe_combine_rare_levels(
            _group_ns_tested, threshold=5
        )
        _group_ns_parts = [f"{k}:{v}" for k, v in _group_ns_visible.items()]
        if _group_ns_combined_k:
            if _group_ns_combined_n is not None and _group_ns_combined_n >= 5:
                _group_ns_parts.append(
                    share_safe.format_combined_levels_note(_group_ns_combined_k, _group_ns_combined_n, unit="level")
                )
            else:
                _group_ns_parts.append(
                    f"{_group_ns_combined_k} smaller level(s) suppressed (too few even combined)"
                )
        _group_ns_str = ", ".join(_group_ns_parts) if _group_ns_parts else "suppressed (n<5 in every level)"

        # Full-precision computational values -- never rounded; *_display
        # columns are formatting only (see fmt_pval()/fmt_effect()).
        _numcat_rows.append({
            "numeric": _num, "categorical": _cat,
            "numeric_earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(_num),
            "categorical_earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(_cat),
            "n_groups": _k,
            "n_groups_total": _n_groups_total,
            "n_levels_excluded_lt3": _n_levels_excluded_lt3,
            "restricted_level_analysis": _n_levels_excluded_lt3 > 0,
            # N_tested is the statistical test's actual denominator (sum of
            # only the levels with >=3 observations) -- this, NOT the larger
            # complete-case count, is the primary N for this pair.
            "N_tested": _n_tested,
            # N_complete_case is kept for internal/audit purposes ONLY -- it
            # is deliberately excluded from _show_nc (the publicly displayed
            # table below) and from plot titles (A2.10b plots), because
            # displaying N_complete_case next to N_tested would let a reader
            # back out the exact patient count of an excluded rare (<3)
            # category level by simple subtraction, defeating the existing
            # group_Ns_str share-safe suppression on that same level.
            "N_complete_case": _n_complete,
            "group_Ns": _group_ns_all,
            # group_Ns (the raw dict) is kept unsuppressed for any internal
            # computation but is never included in the displayed columns
            # (_show_nc below); group_Ns_str (computed above, share-safe) is
            # the only display-facing version.
            "group_Ns_str": _group_ns_str,
            "test": _test,
            "statistic": float(_stat),
            "p_value": float(_pval) if pd.notna(_pval) else np.nan,
            "p_value_display": fmt_pval(_pval if pd.notna(_pval) else None),
            "effect_size": float(_eff) if pd.notna(_eff) else np.nan,
            "effect_size_display": fmt_effect(_eff if pd.notna(_eff) else None),
            "effect_type": _eff_type,
            "effect_magnitude": _numcat_effect_magnitude(_eff_type, _eff),
        })

numcat_df = pd.DataFrame(_numcat_rows)
# BH-FDR always receives the full-precision, unrounded p_value column.
numcat_df["q_value_bh"] = benjamini_hochberg(numcat_df["p_value"]).values
numcat_df["fdr_sig"] = numcat_df["q_value_bh"] < 0.05
numcat_df["q_value_bh_display"] = numcat_df["q_value_bh"].apply(fmt_pval)

print(f"Pairs screened: {len(numcat_df)} | Pairs skipped (insufficient groups): {len(_numcat_skipped)}")
print(f"Raw p<0.05: {int((numcat_df['p_value'] < 0.05).sum())} | "
      f"BH-FDR q<0.05: {int(numcat_df['fdr_sig'].sum())}")
_n_restricted_level = int(numcat_df["restricted_level_analysis"].sum())
print(f"Restricted-level analyses (>=1 category level with <3 complete-case observations "
      f"excluded from the test; tested on the remaining levels only): {_n_restricted_level} "
      f"of {len(numcat_df)} -- see n_groups vs n_groups_total/n_levels_excluded_lt3 below. "
      f"Only the NUMBER of excluded levels is shown, never their exact patient count.")
print()

_numcat_sig = numcat_df[
    numcat_df["fdr_sig"]
    | ((numcat_df["p_value"] < 0.05) & numcat_df["effect_magnitude"].isin(["moderate", "large"]))
].sort_values("effect_size", ascending=False, na_position="last")

# NOTE: N_tested (the statistical test's actual denominator), not the larger
# N_complete_case, is shown here as the pair's primary N -- see the row-
# construction comment above. n_groups_total/n_levels_excluded_lt3 disclose
# how many levels were excluded (count only, never their exact size) so a
# restricted-level analysis is explicit rather than silently implied.
_show_nc = ["numeric", "numeric_earliest_entry_stage", "categorical",
            "categorical_earliest_entry_stage", "n_groups", "n_groups_total",
            "n_levels_excluded_lt3", "restricted_level_analysis", "N_tested",
            "group_Ns_str", "test", "p_value_display", "q_value_bh_display",
            "effect_size_display", "effect_magnitude"]
print(f"Significant/relevant pairs (BH-FDR q<0.05 OR [raw p<0.05 AND moderate+ effect]): {len(_numcat_sig)}")
if len(_numcat_sig):
    print(_numcat_sig[_show_nc].head(20).to_string(index=False))
    if len(_numcat_sig) > 20:
        print(f"... ({len(_numcat_sig) - 20} more rows; full result in numcat_df)")
else:
    print("None.")
print()
if _numcat_skipped:
    print(f"Skipped pairs (insufficient usable groups): {len(_numcat_skipped)} "
          f"e.g. {[(r['numeric'], r['categorical']) for r in _numcat_skipped[:5]]}"
          f"{' ...' if len(_numcat_skipped) > 5 else ''}")
print()
print("NOTE: numcat_df holds the FULL screening table (all eligible pairs, including")
print("non-significant ones); only the significant/relevant subset above and the plots")
print("below are shown inline. All pairs screened vs. pairs visualized are reported")
print("separately by design.")
""")

SB11_NUMCAT_PLOTS = code("eda-b-s11b-numcat-plots", """
if len(_numcat_sig) == 0:
    print("No numeric x categorical pairs met the plotting threshold — no plots generated.")
else:
    _nc_pairs = list(zip(_numcat_sig["numeric"], _numcat_sig["categorical"]))
    # 2x2 (4/page), not the prior 3x4/12-panel page: these titles carry
    # test name + N + p + effect (+ an excluded-level note), long enough that
    # a denser grid crowded them -- category tick labels need the room too.
    _NCOLS_NC, _PER_PAGE_NC = 2, 4
    _n_nc = len(_nc_pairs)
    _n_pages_nc = int(np.ceil(_n_nc / _PER_PAGE_NC))
    print(f"Boxplots for {_n_nc} significant/relevant pair(s) (of {len(numcat_df)} "
          f"screened), {_n_pages_nc} page(s):")
    for _page in range(_n_pages_nc):
        _page_pairs = _nc_pairs[_page * _PER_PAGE_NC:(_page + 1) * _PER_PAGE_NC]
        _nrows_nc = int(np.ceil(len(_page_pairs) / _NCOLS_NC))
        fig, axes = plt.subplots(_nrows_nc, _NCOLS_NC, figsize=(7.5 * _NCOLS_NC, 5.8 * _nrows_nc),
                                  layout="constrained")
        axes = np.array(axes).reshape(-1)
        for i, (num, cat) in enumerate(_page_pairs):
            ax = axes[i]
            _row = numcat_df[(numcat_df["numeric"] == num) & (numcat_df["categorical"] == cat)].iloc[0]
            _sub = df_primary[[num, cat]].dropna()
            _sub_p = _sub.copy()
            _sub_p[cat] = _sub_p[cat].astype(str)
            # a boxplot of a rare category level (n<5)
            # is a more severe disclosure than a suppressed bar chart -- with
            # only 1-4 points, the box/whiskers reveal near-exact individual
            # values, not just a count. Levels with
            # fewer than 5 observations are excluded from this plot (the
            # underlying numcat_df table is unaffected -- full data remains
            # there for computation).
            _level_counts = _sub_p[cat].value_counts()
            _plot_levels = _level_counts[_level_counts >= 5].index.tolist()
            _n_excluded_levels = _level_counts[_level_counts < 5].shape[0]
            _sub_p = _sub_p[_sub_p[cat].isin(_plot_levels)]
            # hue=cat (redundant with x=cat) + a single flat color= triggers
            # seaborn's "gradient palette from color=" FutureWarning in
            # current seaborn -- x=cat alone with a single color already
            # produces one undodged box per category level in that color, so
            # hue/legend are unnecessary here.
            sns.boxplot(data=_sub_p, x=cat, y=num, ax=ax, color=C0,
                        width=0.5, linewidth=1.0)
            # Two DIFFERENT thresholds are in play and must not be conflated:
            # the statistical test (numcat_df/_row) used every level with
            # >=3 complete-case observations; this plot additionally excludes
            # any level with <5 observations for disclosure protection (a
            # boxplot of 1-4 points reveals near-exact individual values).
            # The title therefore reports the TEST's own denominator
            # (N_tested, labeled explicitly as such) rather than an unlabeled
            # "N", and never prints an exact plotted-N -- doing so could
            # let a reader back out a suppressed 3-4-person level's exact
            # size from N_tested by subtraction. The excluded-level count
            # (never its exact size) is the only plot-specific disclosure.
            _excl_note = (f" ({_n_excluded_levels} level(s) <5 excluded from plot only)"
                          if _n_excluded_levels else "")
            # Display-formatted values (fmt_pval()/fmt_effect(), already
            # computed in numcat_df above) -- not the raw full-precision
            # floats, which can render as very long strings and visually
            # overflow into the neighboring subplot's title area. Formatting
            # only; the underlying numcat_df/statistics are unchanged.
            ax.set_title(f"{num} by {cat}\\n{_row['test']}, N_tested={_row['N_tested']}, "
                         f"p={_row['p_value_display']}, eff={_row['effect_size_display']} "
                         f"({_row['effect_magnitude']}){_excl_note}", fontsize=11.5, wrap=True, pad=10)
            ax.set_xlabel(cat, fontsize=11.5)
            ax.set_ylabel(num, fontsize=11.5)
            ax.tick_params(axis="x", labelsize=10.5, rotation=30)
            ax.tick_params(axis="y", labelsize=10.5)
        for j in range(len(_page_pairs), len(axes)):
            axes[j].set_visible(False)
        fig.suptitle(f"Numeric x categorical — significant/relevant pairs — "
                     f"page {_page + 1}/{_n_pages_nc}", fontsize=13)
        plt.show()
    print(f"Plotted {_n_nc} of {len(numcat_df)} screened pairs (full table: numcat_df). "
          f"Title N_tested is the statistical test's own denominator (levels with >=3 "
          f"obs); the boxplot itself additionally excludes any level with <5 obs for "
          f"disclosure protection, so the number of points actually drawn can be smaller "
          f"than N_tested -- see each title's excluded-level count.")
""")

SB11_NUMCAT_KEY_OBS = md("eda-b-s11b-numcat-key-observations", """**Key observations — numeric x categorical relationships:**""")

SB11_NUMCAT_KEY_OBS_CODE = code("eda-b-s11b-numcat-key-observations-code", """
print(f"- {len(numcat_df)} of {len(_num_cols) * len(_catlike_cols)} eligible "
      f"numeric x categorical pairs were testable; {len(_numcat_skipped)} were skipped "
      f"for having fewer than 2 usable groups (typically a rare category with <3 "
      f"complete-case observations).")
print(f"- {len(_numcat_sig)} pair(s) are significant/relevant by the stated threshold "
      f"(BH-FDR q<0.05, or raw p<0.05 with a moderate-or-larger effect); these are the "
      f"ones plotted above.")
if len(_numcat_sig):
    # .iloc[0] after a descending sort is only "the top row" -- if the maximum
    # effect_size is shared by more than one pair (ties are common at the 1.0
    # ceiling for near-deterministic binary relationships), silently reporting
    # a single row as uniquely "strongest" is a sort-order artifact, not a
    # substantive finding. Report every tied pair instead, and note explicitly
    # that an equal effect-size estimate does NOT imply equal evidentiary
    # strength when pairwise N differs (a small-N pair reaching the same
    # nominal effect as a full-cohort pair is far weaker/less generalizable).
    _ko_nc_max_eff = _numcat_sig["effect_size"].max()
    _ko_nc_tied = _numcat_sig[_numcat_sig["effect_size"] == _ko_nc_max_eff]
    if len(_ko_nc_tied) > 1:
        _ko_nc_tied_desc = []
        for _, _r in _ko_nc_tied.iterrows():
            _desc = (f"{_r['numeric']} by {_r['categorical']} ({_r['test']}, "
                      f"N_tested={_r['N_tested']}, p={_r['p_value_display']})")
            if _r["N_tested"] < 30:
                _desc += " [LOW N -- interpret with caution]"
            _ko_nc_tied_desc.append(_desc)
        print(f"- Largest observed effect-size estimate (tied across {len(_ko_nc_tied)} "
              f"pairs, effect={fmt_effect(_ko_nc_max_eff)}): {_ko_nc_tied_desc}. Equal "
              f"effect-size estimates do NOT imply equal evidentiary strength -- these "
              f"pairs differ substantially in pairwise N and p-value; requires "
              f"consideration during Feature Selection if any tied pair's variables are "
              f"candidates for the same model.")
    else:
        _ko_nc_top = _numcat_sig.iloc[0]
        print(f"- Largest observed effect-size estimate: {_ko_nc_top['numeric']} by "
              f"{_ko_nc_top['categorical']} ({_ko_nc_top['test']}, "
              f"effect={_ko_nc_top['effect_size_display']}, {_ko_nc_top['effect_magnitude']}) -- "
              f"requires consideration during Feature Selection if both variables are "
              f"candidates for the same model.")
print("- This screening does not by itself imply redundancy (a numeric-categorical "
      "association is expected for many clinically related pairs); flag pairs with "
      "large effect sizes for a closer look, but no variable is excluded here.")
""")


SB10C_HEADER = md("eda-b-s10c-header", """
### A2.10c — Categorical × Categorical Predictor Relationships

**Purpose:** Systematically screen all eligible categorical/binary predictor pairs for
association strength (Cramér's V), completing predictor-predictor relationship coverage
alongside A2.10a (numeric × numeric) and A2.10b (numeric × categorical).

**What this checks:**
- Chi-square when expected-cell assumptions are satisfied; when they are not
  (Cochran's rule of thumb: any expected cell < 5 for 2x2, or >20% of expected
  cells < 5 for r x c) -- classical Fisher exact for sparse 2x2 tables, or the
  Fisher-Freeman-Halton exact-test framework for sparse r x c tables (valid for
  r x c, not only 2x2), computed via a deterministic fixed-seed Monte Carlo
  p-value (100,000 resamples in the current helper) rather than full
  enumeration -- see each pair's own `test` column for the exact seed/resample
  count used, for every eligible pair (N≥10, both dimensions ≥2 levels)
- Cramér's V (V ≥ 0.5 flagged as potential redundancy)
- BH-FDR-adjusted p-value (computed from full-precision raw p-values) across the
  full pairwise table
- Minimum expected cell count and sparse-cell fraction reported per pair

**What this does NOT do:**
- A high Cramér's V does not by itself establish redundancy — see the caution note
  below on sparse/high-cardinality tables
- Final redundancy decisions require clinical review (A2.10d)

**Output:** Cramér's V heatmap (flagged-pair subset) + full pairwise table
""")

SB11_CRAMERS = code("eda-b-s11-cramers", """
# Uses the shared contingency_association_test() helper (Part 1) -- the same
# Chi-square/Fisher(-Freeman-Halton)/Monte-Carlo selection logic used for
# predictor-vs-target testing in A2.9, so r x c categorical/binary pairs get
# the identical statistically valid sparse-cell handling, rather than the
# asymptotic Chi-square p-value alone for sparse r x c tables.

_V_THRESH = 0.5
# _catlike_cols already built in A2.10b above (binary + categorical PRIMARY_COLS);
# reused here for the systematic categorical-categorical screening.

_catcat_rows = []
for _i in range(len(_catlike_cols)):
    for _j in range(_i + 1, len(_catlike_cols)):
        c1, c2 = _catlike_cols[_i], _catlike_cols[_j]
        sub = df_primary[[c1, c2]].dropna()
        n = len(sub)
        if n < 10:
            continue
        ct = pd.crosstab(sub[c1], sub[c2])
        if ct.shape[0] < 2 or ct.shape[1] < 2:
            continue
        test, stat, pval, min_exp, sparse_frac, sparse_flag = contingency_association_test(ct)
        v = cramers_v(ct)
        _catcat_rows.append({
            "var1": c1, "var2": c2,
            "var1_earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(c1),
            "var2_earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(c2),
            "N": n, "table_shape": f"{ct.shape[0]}x{ct.shape[1]}",
            "test": test,
            # Full-precision computational values -- never rounded. Display
            # columns (*_display) are formatting only.
            "statistic": float(stat) if pd.notna(stat) else np.nan,
            "p_value": float(pval) if pd.notna(pval) else np.nan,
            "p_value_display": fmt_pval(pval),
            "min_expected_cell": min_exp,
            "sparse_cell_fraction": sparse_frac,
            "cramers_v": v,
            "cramers_v_display": fmt_effect(v),
            "sparse_cell_warning": sparse_flag,
            "high_v_flag": bool(pd.notna(v) and v >= _V_THRESH),
        })

catcat_df = pd.DataFrame(_catcat_rows)
# BH-FDR always receives the full-precision, unrounded p_value column.
catcat_df["q_value_bh"] = benjamini_hochberg(catcat_df["p_value"]).values
catcat_df["fdr_sig"] = catcat_df["q_value_bh"] < 0.05
catcat_df["q_value_bh_display"] = catcat_df["q_value_bh"].apply(fmt_pval)

_catcat_possible = len(_catlike_cols) * (len(_catlike_cols) - 1) // 2
print(f"Categorical/binary predictors screened: {len(_catlike_cols)}")
print(f"Eligible pairs (N>=10, both dimensions >=2 levels): {len(catcat_df)} of "
      f"{_catcat_possible} possible")
print(f"Raw p<0.05: {int((catcat_df['p_value'] < 0.05).sum())} | "
      f"BH-FDR q<0.05: {int(catcat_df['fdr_sig'].sum())} | "
      f"V>={_V_THRESH} (potential redundancy): {int(catcat_df['high_v_flag'].sum())} | "
      f"sparse-cell warning: {int(catcat_df['sparse_cell_warning'].sum())}")
print()

_catcat_flagged = catcat_df[
    catcat_df["fdr_sig"] | catcat_df["high_v_flag"]
].sort_values("cramers_v", ascending=False, na_position="last")
_show_cc = ["var1", "var1_earliest_entry_stage", "var2", "var2_earliest_entry_stage",
            "N", "table_shape", "test", "min_expected_cell",
            "p_value_display", "q_value_bh_display",
            "cramers_v_display", "high_v_flag", "sparse_cell_warning"]

_catcat_high_v = catcat_df[catcat_df["high_v_flag"]].sort_values("cramers_v", ascending=False)
print(f"High-Cramer's-V redundancy-review pairs (V>={_V_THRESH}): {len(_catcat_high_v)}")
if len(_catcat_high_v):
    print(_catcat_high_v[_show_cc].head(25).to_string(index=False))
    if len(_catcat_high_v) > 25:
        print(f"... ({len(_catcat_high_v) - 25} more rows; full result in catcat_df)")
else:
    print("None.")
print()

_catcat_sig_only = catcat_df[catcat_df["fdr_sig"] & ~catcat_df["high_v_flag"]].sort_values(
    "cramers_v", ascending=False, na_position="last"
)
print(f"Additional BH-FDR-significant pairs (q<0.05, below the V>={_V_THRESH} redundancy "
      f"threshold): {len(_catcat_sig_only)}")
if len(_catcat_sig_only):
    print(_catcat_sig_only[_show_cc].head(10).to_string(index=False))
    if len(_catcat_sig_only) > 10:
        print(f"... ({len(_catcat_sig_only) - 10} more rows; full result in catcat_df)")
else:
    print("None.")
_high_v_pairs = [
    {"var1": r["var1"], "var2": r["var2"], "cramers_v": r["cramers_v"]}
    for _, r in catcat_df[catcat_df["high_v_flag"]].sort_values("cramers_v", ascending=False).iterrows()
]
print()
print("NOTE: catcat_df holds the FULL systematic screening table for all eligible")
print("categorical/binary predictor pairs (chi-square/Fisher as appropriate, with a")
print("sparse-cell caution flag); only the flagged subset above and the heatmap below")
print("(restricted to variables in a flagged pair, for readability) are shown inline.")
""")

SB11_CRAMERS_HEATMAP = code("eda-b-s11-cramers-heatmap", """
_flagged_vars = sorted(set(_catcat_flagged["var1"]) | set(_catcat_flagged["var2"]))
if len(_flagged_vars) < 2:
    print("Fewer than 2 variables in the flagged subset — heatmap skipped.")
else:
    # Capped at 20 (was 40): a 40-variable matrix was analytically valid but
    # not publication-readable. Ranking (most-connected first, via the
    # existing degree count within the flagged-pair subset, _catcat_flagged --
    # NOT the full catcat_df) is unchanged -- only the display cap is lower,
    # so cell annotations stay legible at every cap size below.
    _MAX_HEATMAP_VARS = 20
    if len(_flagged_vars) > _MAX_HEATMAP_VARS:
        _deg = pd.concat([_catcat_flagged["var1"], _catcat_flagged["var2"]]).value_counts()
        _flagged_vars = _deg.head(_MAX_HEATMAP_VARS).index.tolist()
        print(f"DISPLAY SUBSET ONLY: the flagged variable set ({len(_deg)}) exceeds "
              f"{_MAX_HEATMAP_VARS}; this heatmap shows the {_MAX_HEATMAP_VARS} "
              f"most-connected variables only (by degree count within the flagged-pair "
              f"subset, i.e. how often each variable appears among the {len(_catcat_flagged)} "
              f"flagged pairs -- not degree over the full catcat_df screening table). "
              f"No categorical/binary pair is removed analytically -- the complete "
              f"screening result for every eligible pair remains in catcat_df above, "
              f"unaffected by this inline display cap.")
    _n = len(_flagged_vars)
    _vm = np.full((_n, _n), np.nan)
    for i in range(_n):
        _vm[i, i] = 1.0
    _lookup = {}
    for _, r in catcat_df.iterrows():
        _lookup[(r["var1"], r["var2"])] = r["cramers_v"]
        _lookup[(r["var2"], r["var1"])] = r["cramers_v"]
    for i, c1 in enumerate(_flagged_vars):
        for j, c2 in enumerate(_flagged_vars):
            if i != j:
                _vm[i, j] = _lookup.get((c1, c2), np.nan)
    _v_df = pd.DataFrame(_vm, index=_flagged_vars, columns=_flagged_vars)
    fig, ax = plt.subplots(figsize=(max(9, _n * 0.6), max(7, _n * 0.6)), layout="constrained")
    sns.heatmap(_v_df, cmap="YlOrRd", vmin=0, vmax=1, ax=ax,
                cbar_kws={"label": "Cramer's V"}, linewidths=0.2,
                annot=(_n <= 20), fmt=".2f", annot_kws={"size": 9})
    ax.set_title(f"Cramer's V — display subset: top {_n} of {len(_catlike_cols)} screened "
                 f"predictors\\n(most-connected flagged variables; see catcat_df for the "
                 f"complete screening result)",
                 fontsize=13, pad=12)
    ax.tick_params(axis="x", labelsize=10, rotation=45)
    ax.tick_params(axis="y", labelsize=10, rotation=0)
    plt.setp(ax.get_xticklabels(), ha="right")
    cbar = ax.collections[0].colorbar
    cbar.ax.tick_params(labelsize=10)
    cbar.set_label("Cramer's V", fontsize=11)
    plt.show()
    print(f"DISPLAY SUBSET ONLY: this heatmap shows {_n} variable(s) (capped at "
          f"{_MAX_HEATMAP_VARS} for inline readability). The complete categorical/binary "
          f"predictor-pair screening -- every eligible pair, not just this displayed "
          f"subset -- remains in catcat_df above; no pair is removed analytically by "
          f"this display cap.")
""")

SB11_CC_KEY_OBS = md("eda-b-s11-cc-key-observations", """**Key observations — categorical x categorical relationships:**""")

SB11_CC_KEY_OBS_CODE = code("eda-b-s11-cc-key-observations-code", """
print(f"- {len(catcat_df)} of {_catcat_possible} possible categorical/binary predictor "
      f"pairs were eligible (N>=10, both dimensions with >=2 levels) and screened.")
print(f"- {int(catcat_df['sparse_cell_warning'].sum())} pair(s) carry a sparse-cell "
      f"caution flag -- interpret those p-values/effect sizes conservatively.")
if len(_high_v_pairs):
    print(f"- {len(_high_v_pairs)} pair(s) reach V>={_V_THRESH} (potential redundancy), "
          f"e.g. {[(p['var1'], p['var2']) for p in _high_v_pairs[:5]]}"
          f"{' ...' if len(_high_v_pairs) > 5 else ''} -- see the redundancy groups and "
          f"mode_of_conception review below for two of these examined in detail.")
    _ko11cc_high_v_df = catcat_df[catcat_df["high_v_flag"]]
    _ko11cc_high_v_sparse_n = int(_ko11cc_high_v_df["sparse_cell_warning"].sum())
    print(f"  CAUTION: {_ko11cc_high_v_sparse_n} of these {len(_high_v_pairs)} pair(s) "
          f"also carry a sparse-cell warning (small expected cell counts and/or "
          f"high-cardinality tables). A high Cramer's V in a sparse or high-cardinality "
          f"contingency table is NOT by itself evidence of redundancy -- redundancy "
          f"should only be treated as established when supported by variable "
          f"definitions, derivation lineage, or clear clinical/structural evidence (as "
          f"for mode_of_conception vs mode_of_conception_ivf_vs_all below), not by "
          f"association strength alone. High-V pairs are not automatically added to "
          f"REDUNDANCY_GROUPS.")
print("- Screening flags overlap, not automatic exclusion; the final redundancy call "
      "belongs to Feature Selection.")
""")

SB10D_HEADER = md("eda-b-s10d-header", """
### A2.10d — Redundancy Review

**Purpose:** Apply `REDUNDANCY_GROUPS` to the association/correlation signals from
A2.10a–A2.10c, proposing a candidate representative per group (where one is justified) for
later feature-selection review, plus a worked example (`mode_of_conception` vs
`mode_of_conception_ivf_vs_all`).

**Not every group in `REDUNDANCY_GROUPS` has the same provenance** -- two distinct
kinds of group are shown below:
1. **Prespecified groups with an independently justified representative** (clinical
   priority and/or a documented source/derivation relationship, e.g.
   `conception_method` -- see the worked example) -- these list a candidate
   representative for later feature-selection review.
2. **Association-informed, review-only groups** (`surgical_detail_overlap`,
   `diabetes_status`) -- added *after* A2.10a–c's statistical screening flagged a strong
   association between their members, with no independently documented derivation
   showing one variable is computed from the other. These have `representative=None`:
   no member is proposed over another, and none is automatically demoted -- both/all
   members are simply flagged for clinical/Feature Selection review.

**What this checks:**
- Each group's members and, where independently justified, a candidate
  representative proposed for later feature-selection review; groups without
  independent derivation/source evidence are shown with no representative instead

**What this does NOT do:**
- Redundancy group membership does not automatically exclude a variable
- The candidate representative proposed for a Type-1 group is prespecified/
  provisional, not a final feature-selection or exclusion decision
- A Type-2 (association-informed, `representative=None`) group never causes an
  automatic representative choice or demotion for any of its members
- Final redundancy decisions require clinical review

**Output:** Redundancy groups summary (grouped by provenance type above) + a worked
deterministic-partition example
""")

SB11_REDUND_GROUPS = code("eda-b-s11-redundancy-groups", """
print("Redundancy groups (REDUNDANCY_GROUPS):")
print("Groups with an independently justified (clinical priority and/or documented")
print("source/derivation) representative propose it here for later feature-selection")
print("review; other members are flagged for redundancy review. Groups with")
print("representative=None are association-informed, review-only groups -- no member")
print("is proposed over another, and none is auto-demoted. Either way, these are")
print("prespecified/provisional proposals or review flags, not final feature selection.")
print()
for gname, gdef in REDUNDANCY_GROUPS.items():
    _present = [m for m in gdef["members"] if m in PRIMARY_COLS]
    _rep     = gdef["representative"]
    if len(_present) < 2:
        continue
    print(f"  [{gname}]")
    if _rep is None:
        # No representative asserted: evidence is association-only (no
        # independently documented derivation/source relationship), so no
        # member is proposed over another -- all are flagged for clinical/
        # Feature Selection review instead of a candidate-representative proposal.
        print(f"    Association-informed, review-only group (representative=None) -- "
              f"no independently documented derivation/source relationship; no member "
              f"is proposed over another or auto-demoted. All members flagged for "
              f"review: {_present}")
    else:
        _flagged = [m for m in _present if m != _rep]
        print(f"    Candidate representative (for later feature-selection review): '{_rep}'")
        print(f"    Other members (flagged for redundancy review)                : {_flagged}")
    print()

print("NOTE: groups with a candidate representative rest on independently documented")
print("clinical priority and/or source-derivation evidence, not on association strength")
print("alone; groups with representative=None rest on association evidence only (no")
print("confirmed derivation) and never auto-demote any member. Final decision requires")
print("clinical and modeling review either way.")
""")


# ── A2.10d worked example: mode_of_conception redundancy (was B11c) ────────────
SB11_MOC_HEADER = md("eda-b-s11c-mode-of-conception-header", """
**Worked example: `mode_of_conception` vs `mode_of_conception_ivf_vs_all`**

Both variables are `predictor_allowed` and both are in `PRIMARY_COLS`, so this pair is
already included in the systematic categorical-categorical screening above (A2.10c). This
block documents it explicitly with its own deterministic-partition-structure evidence
for clinical review, rather than leaving it to be found only inside a large table.
The worked example below states the deterministic derivation of
`mode_of_conception_ivf_vs_all` from `mode_of_conception`
and verifies it against the live cohort -- it intentionally does not enumerate which
source levels occur in this cohort or their counts (see the cell below); the rule
alone is sufficient to demonstrate the source/derived relationship, and enumerating
observed levels/counts here would risk disclosing a small cell.
""")

SB11_MOC = code("eda-b-s11c-mode-of-conception", """
_moc_sub = df_primary[["mode_of_conception", "mode_of_conception_ivf_vs_all"]].dropna()
_moc_ct = pd.crosstab(_moc_sub["mode_of_conception"], _moc_sub["mode_of_conception_ivf_vs_all"])
_moc_v = cramers_v(_moc_ct)
print(f"N={len(_moc_sub)}")
print()
# Share-safe (derivation-rule display, not a per-level enumeration): even a
# structure-only per-level mapping list still discloses which rare source
# codes exist in this cohort, and -- because the complete-case N is printed
# above and every non-rare level's exact count would otherwise be shown --
# a reader could reconstruct a small masked level's exact count by
# subtraction. The purpose of this worked example is to demonstrate the
# deterministic derivation of mode_of_conception_ivf_vs_all from
# mode_of_conception, not which source codes
# happen to occur in this cohort or their counts. The rule is verified
# against the live data internally below; only a pass/fail summary is
# printed, never a per-level breakdown or count. _moc_ct/_moc_v themselves
# (used for the analytical conclusion) are unaffected -- this is a
# display-only change.
_MOC_IVF_SOURCE_CODE = 1  # mode_of_conception == 1 is the IVF source code.
_moc_rule_violations = 0
for _lvl in _moc_ct.index:
    _expected_col = 1 if _lvl == _MOC_IVF_SOURCE_CODE else 0
    _observed_cols = [c for c in _moc_ct.columns if _moc_ct.loc[_lvl, c] > 0]
    if _observed_cols != [_expected_col]:
        _moc_rule_violations += 1
print("Deterministic derivation: mode_of_conception_ivf_vs_all = 1 iff mode_of_conception == 1.")
print(f"  mode_of_conception == {_MOC_IVF_SOURCE_CODE} (the IVF source code)  ->  "
      f"mode_of_conception_ivf_vs_all = 1")
print(f"  mode_of_conception != {_MOC_IVF_SOURCE_CODE} (any other source code)  ->  "
      f"mode_of_conception_ivf_vs_all = 0")
if _moc_rule_violations == 0:
    print("  Verified against the live cohort: every source level follows this rule exactly "
          "(a clean deterministic partition) -- see Cramer's V below for the resulting "
          "association strength.")
else:
    print(f"  NOTE: {_moc_rule_violations} source level(s) do not follow this rule exactly in "
          "the current cohort -- not a clean deterministic partition for those level(s).")
print()
print(f"Cramer's V = {_moc_v}")
print()
print("Interpretation:")
print("  mode_of_conception is the richer, multi-level source variable (its levels")
print("  include an IVF code among other conception-method codes).")
print("  mode_of_conception_ivf_vs_all is a derived binary collapse of the same")
print("  underlying information: the derivation rule above defines a deterministic")
print("  partition -- every mode_of_conception level maps to exactly one")
print("  mode_of_conception_ivf_vs_all value -- consistent with a source/derived")
print("  relationship rather than two independently measured variables.")
print("  Using both simultaneously in a model would be redundant: the binary variable")
print("  contributes no information beyond what the source categorical variable")
print("  already encodes for the IVF-vs-not split.")
print("  This pair is flagged for potential redundancy (see REDUNDANCY_GROUPS")
print("  ['conception_method']). The final choice between the richer categorical")
print("  representation and the binary collapse (a documented clinical preference for")
print("  IVF-vs-all comparisons) is deferred to Feature Selection based")
print("  on clinical meaning, missingness, and modeling relevance -- not decided here.")
""")

SB11_REDUNDANCY_KEY_OBS = md("eda-b-s11-redundancy-key-observations", """**Key observations — redundancy review:**""")

SB11_REDUNDANCY_KEY_OBS_CODE = code("eda-b-s11-redundancy-key-observations-code", """
_ko11r_groups_present = {g: d for g, d in REDUNDANCY_GROUPS.items()
                          if len([m for m in d["members"] if m in PRIMARY_COLS]) >= 2}
print(f"- {len(_ko11r_groups_present)} of {len(REDUNDANCY_GROUPS)} defined redundancy "
      f"groups have >=2 members currently in PRIMARY_COLS: {list(_ko11r_groups_present)}.")
print(f"- mode_of_conception vs mode_of_conception_ivf_vs_all: Cramer's V={_moc_v} "
      f"(deterministic source/derived pair, see A2.10d above) -- flag for later review "
      f"during Feature Selection, not resolved here.")
print("- endo_surgery_adhesiolysis vs endo_resection_adhesiolysis: newly registered "
      "(surgical_detail_overlap) after the systematic categorical-categorical "
      "screening flagged a strong association -- an association-informed, "
      "review-only group (representative=None), not a pre-defined clinical group. "
      "The two variables are clinically related / potentially overlapping -- both "
      "describe adhesiolysis during endometriosis surgery, but at different "
      "detail/representation levels (a standalone summary flag vs. one indicator "
      "in a related multi-hot family). Strong association alone does not prove "
      "identical meaning, so no representative is auto-selected here and neither "
      "member is auto-demoted; which (if either) should represent the concept is "
      "deferred to Feature Selection / clinical review.")
print("- gestational_diabetes vs diabetes_type (diabetes_status): same "
      "association-informed, review-only status (representative=None) -- a "
      "near-perfect cross-tabulation is suggestive of a source/derived relationship "
      "but has not been independently confirmed as an actual derivation, so neither "
      "member is auto-demoted here either.")
print("- No group membership or flagged pair causes a variable to be dropped from "
      "PRIMARY_COLS; redundancy groups are proposals/review flags for Feature "
      "Selection only, and an association-informed (representative=None) group "
      "never auto-demotes any of its members.")
""")


# ── Section A2.11 (was B12) ────────────────────────────────────────────────────
SB12_HEADER = md("eda-b-s12-header", """
## Section A2.11 — Deep Outlier Analysis

**Purpose:** Deep, target-blind diagnostic outlier screening for all numeric primary
predictors using the IQR 1.5x rule. EDA A Section A8 contains a simpler count-only
screening pass; this is the deep analysis.

**Methodological approach:** the observed outcome (`target_intrapartum_cs`) must not
determine whether a predictor value is treated as erroneous, implausible, or worth
reviewing -- classifying an "outlier" using the target would make data-quality
judgments depend on the very outcome the model is meant to predict. This section is
therefore split into two clearly separate blocks:
1. **Target-blind screening** (this cell, `outlier_df`): IQR-based statistical
   extremeness only. Every flagged value is labeled `extreme_value_review_item`, not
   "error" or "plausible" -- this notebook has no documented clinical plausibility
   range, source-validation flag, or coding-rule registry for these numeric predictors
   that would let a target-blind process actually distinguish a data-entry error from a
   real clinical extreme. That distinction requires clinical/source review, not a
   target-rate comparison.
2. **Descriptive outcome-sensitivity block** (the next cell, `outlier_sensitivity_df`):
   an optional, clearly-labeled, purely descriptive contrast of outcome rate and
   univariate association with vs. without the flagged values. This block is shown for
   transparency only -- it explicitly does **not** determine cleaning, tiering,
   inclusion, exclusion, or preprocessing for any variable.

**What this checks:**
- IQR 1.5x bounds, outlier count/%, and actual range for all numeric PRIMARY_COLS
- (separate cell) descriptive outcome-rate and effect-estimate sensitivity, correctly
  computed as flagged outliers vs. the TRUE non-outlier subset (not the full cohort)

**What this does NOT do:**
- No outliers are removed here — this section is diagnostic only
- No target-derived signal (CS rate, p-value, effect size, significance change) is used
  to assign a tier, a data-quality label, or a deletion/keep recommendation
- Approved deletions may only happen in preprocessing, with a target-independent
  clinical justification, never here

**Output:** `outlier_df` — per-variable IQR bounds, outlier counts, and a target-blind
`extreme_value_review_item` label. `outlier_sensitivity_df` — separate descriptive-only
outcome-sensitivity contrast (see caveat above).
""")

SB12_OUTLIERS = code("eda-b-s12-outliers", """
# ── Target-blind IQR screening ────────────────────────────────────────────
# No target_intrapartum_cs information is read anywhere in this cell. Every
# flagged variable receives the same target-independent review label -- this
# notebook has no clinical-plausibility-range or source-validation registry
# for numeric predictors that would let a target-blind process distinguish a
# data-entry error from a real clinical extreme.
_num_cols = [c for c in PRIMARY_COLS if infer_var_type(df_primary[c]) == "numeric"]
_outlier_log = []
_iqr_zero_log = []  # variables with IQR==0 -- standard 1.5x-IQR flagging is
                     # not informative for these (see the note below); reported
                     # separately rather than silently producing bounds=[Q1,Q1] and
                     # flagging every nonzero value. Matches EDA A Part 1 Section A8's
                     # existing, already-approved behavior for the same situation
                     # (e.g. CS, a right-skewed low-count clinical variable).

for col in _num_cols:
    s = df_primary[col].dropna()
    if len(s) < 4: continue
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        _iqr_zero_log.append(col)
        continue
    lo, hi = q1 - 1.5*iqr, q3 + 1.5*iqr
    out_mask = (df_primary[col] < lo) | (df_primary[col] > hi)
    n_out = int(out_mask.sum())
    if n_out == 0: continue

    _outlier_log.append({
        "variable":            col,
        "earliest_entry_stage": PRIMARY_COLS_EARLIEST_STAGE.get(col),
        "N_observed":          len(s),
        "n_outliers":          n_out,
        # The scientifically interpretable within-variable outlier
        # proportion -- share of THIS variable's own non-missing values that
        # are IQR-flagged. A full-cohort-denominator figure is also kept
        # (renamed, not called a bare "%") for audit/cross-variable-scale
        # comparison only -- see the printed note below for why the two can
        # differ sharply for a heavily-missing variable.
        "outlier_pct_among_observed": round(n_out/len(s)*100, 1),
        "outlier_pct_of_full_cohort": round(n_out/len(df_primary)*100, 1),
        "iqr_bounds":          f"[{lo:.2f}, {hi:.2f}]",
        "actual_range":        f"[{s.min():.2f}, {s.max():.2f}]",
        "data_quality_status": "extreme_value_review_item",
    })

if not _outlier_log:
    print("No IQR outliers detected across numeric primary predictors.")
else:
    # Target-independent order: both percentage columns are computed purely
    # from each predictor's own IQR/observed-value distribution, never from
    # target_intrapartum_cs -- sorting by either is descriptive/readability
    # only, not a target-informed ranking. Sorted by the within-variable
    # (observed-denominator) proportion, the scientifically interpretable one.
    outlier_df = pd.DataFrame(_outlier_log).sort_values(
        "outlier_pct_among_observed", ascending=False)
    # Share-safe display copy: n_outliers can be small (1-4) --
    # same convention as EDA A's Section A8. outlier_df itself keeps true
    # values (used by the sensitivity block below and for sorting above).
    _outlier_display = outlier_df.copy()
    # Complement-aware against each variable's own N_observed for the
    # observed-denominator percentage, and against the full-cohort N for the
    # full-cohort-denominator percentage -- each suppressed relative to the
    # denominator it is actually a fraction of.
    _outlier_display["n_outliers"] = [
        share_safe.safe_count_with_complement(int(_n), int(_n_obs), enabled=SHARE_SAFE_MODE)
        for _n, _n_obs in zip(outlier_df["n_outliers"], outlier_df["N_observed"])
    ]
    _outlier_display["outlier_pct_among_observed"] = [
        share_safe.safe_pct_with_denominator(int(n), int(n_obs), enabled=SHARE_SAFE_MODE)[0]
        for n, n_obs in zip(outlier_df["n_outliers"], outlier_df["N_observed"])
    ]
    _outlier_display["outlier_pct_of_full_cohort"] = [
        share_safe.safe_pct_with_denominator(int(n), len(df_primary), enabled=SHARE_SAFE_MODE)[0]
        for n in outlier_df["n_outliers"]
    ]
    _outlier_show = ["variable", "earliest_entry_stage", "N_observed", "n_outliers",
                      "outlier_pct_among_observed", "outlier_pct_of_full_cohort",
                      "iqr_bounds", "actual_range", "data_quality_status"]
    print(f"Outlier screening — IQR 1.5x — {len(_num_cols)} numeric primary predictors:")
    print(f"  Variables with outliers: {len(outlier_df)}")
    print()
    print(_outlier_display[_outlier_show].to_string(index=False))
    print()
    print("outlier_pct_among_observed = n_outliers / N_observed -- the scientifically")
    print("interpretable within-variable outlier proportion. outlier_pct_of_full_cohort =")
    print("n_outliers / full-cohort N -- kept for audit/cross-variable-scale comparison only;")
    print("for a variable with substantial missingness the two can differ sharply (e.g. a")
    print("variable observed in only a small fraction of the cohort can have a high share of")
    print("its OWN observed values flagged while looking negligible against the full cohort).")
    print("All entries are labeled 'extreme_value_review_item' -- a target-blind,")
    print("statistical-extremeness flag only, not an error/plausible determination.")
    print("No outliers are removed here. Any approved removal must happen in")
    print("preprocessing, and must rest on a target-independent clinical justification")
    print("(documented plausibility range, source validation, or a known coding rule),")
    print("never on this table alone.")

if _iqr_zero_log:
    print()
    print(f"Variables with IQR == 0 ({len(_iqr_zero_log)}) -- standard 1.5x-IQR flagging "
          f"is not informative for these and none was performed, but they remain "
          f"evaluated numeric primary predictors, not silently dropped: {_iqr_zero_log}")
""")

SB12_SENSITIVITY_HEADER = md("eda-b-s12b-sensitivity-header", """
### A2.11 — Descriptive Outcome-Sensitivity Block (NOT used for tiering)

**This block is descriptive only.** It reports how the observed outcome rate and the
univariate predictor-target association differ between the flagged outliers and the
true non-outlier subset. It does **not** determine data-quality status, a keep/delete
recommendation, cleaning action, or predictor eligibility for any variable -- that
determination is Section A2.11's target-blind `outlier_df` above (or, ultimately,
clinical/source review). A larger difference here does not imply an error, and an
unchanged association does not imply the extreme value is real; both are equally
consistent with ordinary sampling variability in a modestly sized cohort.
""")

SB12_SENSITIVITY = code("eda-b-s12b-sensitivity", """
_sensitivity_log = []

for col in _num_cols:
    s = df_primary[col].dropna()
    if len(s) < 4: continue
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0: continue  # not informative -- see A2.11's outlier_df note above
    lo, hi = q1 - 1.5*iqr, q3 + 1.5*iqr
    out_mask = (df_primary[col] < lo) | (df_primary[col] > hi)
    n_out = int(out_mask.sum())
    if n_out == 0: continue
    in_mask = (df_primary[col] >= lo) & (df_primary[col] <= hi)

    # Outcome rate: outliers vs the TRUE non-outlier subset (not the full
    # cohort -- comparing outliers to a group that still contains them would
    # mislabel the contrast). Full precision throughout; `is not None` /
    # pd.notna(), never truthiness, so a genuine 0.0 rate is not mistaken for
    # "no data".
    out_sub = df_primary.loc[out_mask & df_primary[TARGET_COL].notna(), TARGET_COL]
    in_sub  = df_primary.loc[in_mask & df_primary[TARGET_COL].notna(), TARGET_COL]
    rate_out = float(out_sub.mean()) if len(out_sub) > 0 else None
    rate_in  = float(in_sub.mean()) if len(in_sub) > 0 else None
    delta_rate = (
        abs(rate_out - rate_in) if (rate_out is not None and rate_in is not None) else None
    )

    # Effect-MAGNITUDE sensitivity: full data vs. non-outlier-only.
    # mannwhitney_with_effect() returns the ABSOLUTE rank-biserial |r| (never
    # signed), so a difference between its two outputs is only ever an
    # effect-magnitude shift, not a signed effect-estimate shift -- it cannot
    # represent a direction reversal (two magnitudes near zero can look like
    # a small shift here even if the underlying association actually flips
    # sign when outliers are excluded). Reported as a continuous magnitude
    # shift (preferred over a binary "significance changed" read, which is
    # unstable with sparse events); no new inferential procedure is
    # introduced to also capture direction.
    _n_non_outliers = int(in_mask.sum())
    _sub_in = df_primary.loc[in_mask & df_primary[TARGET_COL].notna(), [col, TARGET_COL]]
    if len(_sub_in) >= 10:
        p_all, effect_all = mannwhitney_with_effect(
            df_primary.loc[df_primary[TARGET_COL]==0, col].dropna(),
            df_primary.loc[df_primary[TARGET_COL]==1, col].dropna()
        )
        p_excl, effect_excl = mannwhitney_with_effect(
            _sub_in[_sub_in[TARGET_COL]==0][col],
            _sub_in[_sub_in[TARGET_COL]==1][col]
        )
    else:
        p_all, effect_all, p_excl, effect_excl = None, None, None, None
    effect_magnitude_shift = (
        abs(effect_all - effect_excl)
        if (effect_all is not None and effect_excl is not None) else None
    )

    _sensitivity_log.append({
        "variable":               col,
        "N_observed":             len(s),
        "N_non_outliers":         _n_non_outliers,
        "n_outliers":             n_out,
        "outcome_rate_outliers":  rate_out,
        "outcome_rate_non_outliers": rate_in,
        "abs_rate_difference":    delta_rate,
        "p_value_full_data":      p_all,
        "effect_full_data":       effect_all,
        "p_value_non_outliers_only": p_excl,
        "effect_non_outliers_only":  effect_excl,
        "abs_effect_magnitude_shift": effect_magnitude_shift,
    })

if not _sensitivity_log:
    print("No IQR outliers detected — sensitivity block skipped.")
else:
    # Target-independent public order: this table's values (outcome rates,
    # p-values, effect magnitudes) are all target-derived DESCRIPTIVE
    # diagnostics, but the DISPLAY ORDER itself must not be built from one of
    # them (that would create a target-informed ranking even in a purely
    # descriptive block) -- sorted by variable name instead. All sensitivity
    # values themselves are unchanged.
    outlier_sensitivity_df = pd.DataFrame(_sensitivity_log).sort_values("variable")
    # Share-safe display copy: outcome_rate_outliers is the TARGET rate
    # within the (often small) outlier subgroup -- this ties a tiny subgroup
    # directly to the sensitive target, a more severe disclosure than an
    # ordinary event count. Suppressed whenever n_outliers (or its
    # complement within the outlier subgroup, i.e. the same n<5 rule applied
    # to the outcome count) is small. outlier_sensitivity_df itself is unaffected.
    def _suppress_outlier_rate(rate, n):
        if rate is None or not SHARE_SAFE_MODE:
            return rate
        _n_events = round(rate * n)
        _pct_disp, _ = share_safe.safe_pct_with_denominator(_n_events, n, enabled=SHARE_SAFE_MODE)
        return _pct_disp if isinstance(_pct_disp, str) else rate

    _sensitivity_display = outlier_sensitivity_df.copy()
    # Share-safe: N_non_outliers was previously copied through unsuppressed.
    # N_observed and N_non_outliers are each individually "safe-looking"
    # (typically large), but N_observed - N_non_outliers == n_outliers
    # exactly (they are complements by construction) -- showing both exact
    # totals side by side in the same row discloses a suppressed n_outliers
    # (1-4) by simple subtraction regardless of what the n_outliers column
    # itself shows. Suppressing N_non_outliers whenever its complement
    # (n_outliers) is small -- the same safe_count_with_complement()
    # convention already used for n_outliers itself -- closes this.
    _sensitivity_display["N_non_outliers"] = [
        share_safe.safe_count_with_complement(int(_n_non), int(_n_obs), enabled=SHARE_SAFE_MODE)
        for _n_non, _n_obs in zip(outlier_sensitivity_df["N_non_outliers"], outlier_sensitivity_df["N_observed"])
    ]
    _sensitivity_display["n_outliers"] = [
        share_safe.safe_count_with_complement(int(_n), int(_n_obs), enabled=SHARE_SAFE_MODE)
        for _n, _n_obs in zip(outlier_sensitivity_df["n_outliers"], outlier_sensitivity_df["N_observed"])
    ]
    _sensitivity_display["outcome_rate_outliers"] = [
        _suppress_outlier_rate(rate, n)
        for rate, n in zip(outlier_sensitivity_df["outcome_rate_outliers"], outlier_sensitivity_df["n_outliers"])
    ]
    # Two further fields are reconstruction risks and must be suppressed too,
    # even though neither is a "count" itself:
    #   - abs_rate_difference is |outcome_rate_outliers - outcome_rate_non_
    #     outliers|; even with outcome_rate_outliers hidden, showing this
    #     difference together with the (visible) outcome_rate_non_outliers
    #     algebraically hands back outcome_rate_outliers, from which the
    #     protected outlier TARGET-EVENT count is recoverable.
    #   - outcome_rate_non_outliers, shown as a precise percentage next to a
    #     known/near-known denominator, can pin its own exact numerator to a
    #     single integer once rounding is accounted for -- the same
    #     rounding-plus-denominator attack this project's disclosure policy
    #     is designed to close elsewhere.
    #
    # The suppression trigger must be whether outcome_rate_outliers ITSELF
    # needed suppression (already computed above via _suppress_outlier_rate(),
    # which checks the target-event count), not whether n_outliers's own
    # SUBGROUP MEMBERSHIP count is small: n_outliers can be large (e.g. 11,
    # 12, 18, 19) while the TARGET-EVENT count WITHIN those outliers
    # (round(outcome_rate_outliers * n_outliers)) is still 1-4 -- e.g.
    # n_outliers=11 but only 1 of those 11 is an intrapartum-CS case. The
    # target-event count, not the subgroup-membership count, is the actual
    # quantity these two fields are algebraically dependent on.
    _outlier_rate_protected = [isinstance(v, str) for v in _sensitivity_display["outcome_rate_outliers"]]
    _sensitivity_display["outcome_rate_non_outliers"] = [
        "suppressed (n<5 in a cell)" if protected else rate
        for protected, rate in zip(_outlier_rate_protected, outlier_sensitivity_df["outcome_rate_non_outliers"])
    ]
    _sensitivity_display["abs_rate_difference"] = [
        "suppressed (n<5 in a cell)" if protected else diff
        for protected, diff in zip(_outlier_rate_protected, outlier_sensitivity_df["abs_rate_difference"])
    ]
    # Canonical display formatting (fmt_pval/fmt_effect, already used
    # throughout this notebook) -- full-precision values remain in
    # outlier_sensitivity_df itself; a nonzero p-value must never render as
    # a literal "0.000" here.
    _sensitivity_display["p_value_full_data"] = _sensitivity_display["p_value_full_data"].apply(fmt_pval)
    _sensitivity_display["p_value_non_outliers_only"] = _sensitivity_display["p_value_non_outliers_only"].apply(fmt_pval)
    _sensitivity_display["effect_full_data"] = _sensitivity_display["effect_full_data"].apply(fmt_effect)
    _sensitivity_display["effect_non_outliers_only"] = _sensitivity_display["effect_non_outliers_only"].apply(fmt_effect)
    _sensitivity_display["abs_effect_magnitude_shift"] = _sensitivity_display["abs_effect_magnitude_shift"].apply(fmt_effect)
    _sensitivity_show = ["variable", "N_observed", "N_non_outliers", "n_outliers",
                          "outcome_rate_outliers", "outcome_rate_non_outliers", "abs_rate_difference",
                          "p_value_full_data", "effect_full_data",
                          "p_value_non_outliers_only", "effect_non_outliers_only",
                          "abs_effect_magnitude_shift"]
    print("Descriptive outcome-sensitivity contrast (outliers vs. TRUE non-outlier subset):")
    print(_sensitivity_display[_sensitivity_show].to_string(index=False))
    print()
    print("abs_effect_magnitude_shift is a MAGNITUDE-only comparison (mannwhitney_with_effect()")
    print("returns absolute rank-biserial |r|) -- it cannot represent a direction reversal; a")
    print("small value here does not rule out the underlying association flipping sign between")
    print("the full-data and non-outlier-only fits.")
    print("REMINDER: descriptive only. Does NOT determine cleaning, tiering, inclusion,")
    print("exclusion, or preprocessing for any variable -- see A2.11's outlier_df above")
    print("for the (target-blind) data-quality-review label.")
""")

SB12_KEY_OBS = md("eda-b-s12-key-observations", """**Key observations — deep outlier screening:**""")

SB12_KEY_OBS_CODE = code("eda-b-s12-key-observations-code", """
if "outlier_df" in dir() and len(outlier_df):
    print(f"- {len(outlier_df)} of {len(_num_cols)} numeric primary predictors have "
          f"IQR-flagged values; all are labeled 'extreme_value_review_item' "
          f"(target-blind -- see A2.11 methodology note above).")
    print("- No value is removed or modified here, and any approved removal must happen")
    print("  in preprocessing with a target-independent clinical justification.")
    if "outlier_sensitivity_df" in dir() and len(outlier_sensitivity_df):
        print(f"- A separate, purely descriptive outcome-sensitivity contrast is reported "
              f"for {len(outlier_sensitivity_df)} variable(s) above -- it does not change "
              f"this section's data-quality labels or any downstream eligibility.")
else:
    print("- No IQR-flagged values among numeric primary predictors in the current cohort.")
""")


# ── Collect Part 4 cells ──────────────────────────────────────────────────────
EDA_B_PART4_CELLS = [
    SB10_HEADER, SB10_ASSOC, SB10_KEY_OBS, SB10_KEY_OBS_CODE,
    SB11_HEADER, SB10A_HEADER, SB11_CORR, SB11_SCATTER, SB11_NN_KEY_OBS, SB11_NN_KEY_OBS_CODE,
    SB11_NUMCAT_HEADER, SB11_NUMCAT_SCREEN, SB11_NUMCAT_PLOTS,
    SB11_NUMCAT_KEY_OBS, SB11_NUMCAT_KEY_OBS_CODE,
    SB10C_HEADER, SB11_CRAMERS, SB11_CRAMERS_HEATMAP, SB11_CC_KEY_OBS, SB11_CC_KEY_OBS_CODE,
    SB10D_HEADER, SB11_REDUND_GROUPS, SB11_MOC_HEADER, SB11_MOC,
    SB11_REDUNDANCY_KEY_OBS, SB11_REDUNDANCY_KEY_OBS_CODE,
    SB12_HEADER, SB12_OUTLIERS, SB12_SENSITIVITY_HEADER, SB12_SENSITIVITY,
    SB12_KEY_OBS, SB12_KEY_OBS_CODE,
]

if __name__ == "__main__":
    print(f"EDA A2 Part 4 cells defined: {len(EDA_B_PART4_CELLS)}")

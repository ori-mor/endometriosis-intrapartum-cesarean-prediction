#!/usr/bin/env python3
"""EDA A — Part 2: cell definitions (sections A5-A10).

Sections (methodological order, reorganized 2026-08-08 -- see
docs/clinical_decisions/manual_decisions_log.md for the reorg rationale):
  A5  — Predictor pool and exclusion rationale (formerly A7)
  A6  — Univariate descriptive overview of predictor candidates (Table 1 style)
  A7  — Dataset missingness overview: ALL columns (with row-level summary) (formerly A5)
  A8  — Initial IQR outlier screening: numeric predictor candidates (count only)
  A9  — Findings registry (screening findings only, no decisions)
  A10 — Part 1 summary / handoff

All sections are read-only and aggregate only. No association tests.
Depends on variables defined in Part 1: df, inv_df, and all config lists.
Cell IDs intentionally retain their original "sNN" numbering (e.g.
"eda-a-s07-header" for the cell now displayed as Section A5) for execution
stability; the displayed section number comes from each cell's markdown
text, not from its ID.
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


# ── Section A5 ────────────────────────────────────────────────────────────────
SA5_HEADER = md("eda-a-s05-header", """
## Section A7 — Dataset Missingness Overview

This section documents missing values across all dataset columns: a per-column
missingness summary grouped by classification, a row-level summary of how many delivery
records have ≥1 / ≥5 / ≥10 missing values, a subgroup applicability report, and a missingness
heatmap for visual pattern detection. Structural NaN variables — whose missingness is by
clinical design rather than a data-quality issue — are flagged separately throughout (see
the methodology note below).

**Methodology note — structural vs. in-subgroup missingness:** structural missingness
refers to values that are not applicable *outside* the relevant subgroup (e.g.
`endometrioma_size_clean` is NaN for every patient without an endometrioma, by design).
Missing values *within* the applicable subgroup remain genuine missingness and are
reported and evaluated separately below — a structural-NaN flag does not mean every
missing value for that column is structural.
""")

SA5_MISS_TABLE = code("eda-a-s05-miss-table", """
# EDA A boundary: missingness is reported only.
# No rows or columns are removed, no imputation, no missing indicator columns.
# Structural vs. true missingness is separated below via the canonical
# SUBGROUP_ACCOUNTING mapping (built once in Section A3, Part 1).

# Missingness summary by group
_miss_summary = (
    inv_df.groupby("group")
    .agg(
        n_columns        = ("column", "count"),
        n_complete       = ("missing_%", lambda x: (x == 0).sum()),
        n_partial        = ("missing_%", lambda x: ((x > 0) & (x < 70)).sum()),
        n_high_miss      = ("missing_%", lambda x: (x >= 70).sum()),
        mean_missing_pct = ("missing_%", "mean"),
    )
    .round(1)
)
print("Missingness summary by group:")
print(_miss_summary.to_string())
print()
print("Note: this table is descriptive only. Missingness bins (n_partial, n_high_miss "
      ">=70%) are not used for exclusion or feature selection. Structural NaN (values "
      "not applicable outside a subgroup, e.g. endometrioma-only fields) can inflate a "
      "group's raw missing% relative to its in-subgroup missingness -- see the "
      "methodology note above.")
print()

# Row-level missingness summary
_row_miss = df.isna().sum(axis=1)
_r1 = int((_row_miss >= 1).sum())
_r5 = int((_row_miss >= 5).sum())
_r10 = int((_row_miss >= 10).sum())
print(f"Row-level missingness (across all {len(df.columns)} columns):")
print(f"  Rows with >= 1  missing value : {_r1:>3}  ({100*_r1/len(df):.1f}%)")
print(f"  Rows with >= 5  missing values: {_r5:>3}  ({100*_r5/len(df):.1f}%)")
print(f"  Rows with >= 10 missing values: {_r10:>3}  ({100*_r10/len(df):.1f}%)")
print(f"  Note: computed across all {len(df.columns)} dataset columns -- structural, outcome, "
      "leakage/source, and excluded variables included, not only predictor_allowed "
      "columns. This does NOT mean every record has >=10 missing predictor values.")
print()

# Subgroup applicability report -- reports each
# SUBGROUP_APPLICABLE_COLS entry with its own subgroup denominator, never the
# full-cohort denominator, and never as ordinary missingness. Most entries
# (adhesions/surgical_site_infection/etc.) use the cesarean subgroup;
# age_at_neonatal_death uses the neonatal_death==1 subgroup instead -- the
# mask is looked up per entry by subgroup_label, not hardcoded to cesarean.
#
# Small-subgroup disclosure guard: when the applicable subgroup denominator
# is small enough that a value breakdown could reveal an individual row's raw
# value (e.g. age_at_neonatal_death, whose applicable subgroup is small in
# the current cohort), printing it would violate this notebook's own safety
# rule that outputs must be
# aggregate-only and must never expose patient-level rows. Reuses this
# project's existing sparse-cell convention (n < 5, the same threshold used
# for too_sparse/min_expected_cell elsewhere in the EDA workflow) rather than
# a bespoke cutoff. Applies generically to every SUBGROUP_APPLICABLE_COLS
# entry -- not specific to any one variable -- so any future entry with a
# small subgroup is protected automatically.
#
# The same threshold is also applied PER-CELL below: a large subgroup can
# still contain individual small cells --
# e.g. a rare category, or a continuous variable's raw value_counts(), which
# for a measurement like endometrioma_size_clean has many cells of frequency
# 1 (a near-patient-level disclosure). Reporting behavior is chosen from the
# canonical variable-type schema (VARIABLE_TYPE_MAP, Part 1), not inferred:
#   - continuous/count: aggregate descriptive statistics only (mean, SD,
#     median, Q1, Q3, IQR, min, max) -- never raw values or a frequency table.
#   - categorical/binary/ordinal: per-category counts, but any category below
#     the threshold is combined into a single suppressed bucket rather than
#     printed individually.
#   - any other/unknown type (e.g. free text): no value breakdown at all --
#     documented-count only.
_SG_MIN_DISCLOSURE_N = 5
# Reuses the canonical SUBGROUP_MASKS built once in Section A3 (Part 1) --
# not redefined here, so A3/A7/A9/A10 all use exactly the same masks.
_sg_rows = []
for _sg_col, _sg_meta in SUBGROUP_APPLICABLE_COLS.items():
    _sg_label_a5 = _sg_meta["subgroup_label"]
    _sg_mask_a5 = SUBGROUP_MASKS[_sg_label_a5]
    _n_sg_a5 = int(_sg_mask_a5.sum())
    # Validation (not reader-facing): a subgroup-applicable variable must be
    # structural NaN outside its clinically applicable subgroup, never an
    # ordinary non-null value.
    _sg_n_outside_non_null = int(df.loc[~_sg_mask_a5, _sg_col].notna().sum())
    assert _sg_n_outside_non_null == 0, (
        f"{_sg_col}: {_sg_n_outside_non_null} non-null value(s) found outside its "
        f"clinically applicable subgroup ({_sg_label_a5}); these are expected to be "
        f"structural NaN."
    )
    _sg_series_in = df.loc[_sg_mask_a5, _sg_col]
    _sg_documented_n = int(_sg_series_in.notna().sum())
    _sg_vtype = VARIABLE_TYPE_MAP.get(_sg_col, "unknown")
    if _n_sg_a5 < _SG_MIN_DISCLOSURE_N:
        _sg_dist_a5 = f"Not reported (subgroup n<{_SG_MIN_DISCLOSURE_N})"
    elif _sg_vtype in ("continuous", "count"):
        if _sg_documented_n < _SG_MIN_DISCLOSURE_N:
            _sg_dist_a5 = f"Not reported (documented n<{_SG_MIN_DISCLOSURE_N})"
        else:
            _sg_s = _sg_series_in.dropna()
            _sg_q1, _sg_q3 = _sg_s.quantile(0.25), _sg_s.quantile(0.75)
            _sg_dist_a5 = (
                f"mean={_sg_s.mean():.1f}, SD={_sg_s.std():.1f}, "
                f"median={_sg_s.median():.1f}, IQR=[{_sg_q1:.1f}, {_sg_q3:.1f}], "
                f"range=[{_sg_s.min():.1f}, {_sg_s.max():.1f}]"
            )
    elif _sg_vtype in ("categorical", "binary", "ordinal"):
        # share_safe.safe_combine_rare_levels() (not a naive "combine every
        # level below threshold into one bucket" -- see that helper's own
        # docstring) is required here rather than an ad hoc combine: when
        # only ONE level falls below the threshold, a naive combined-bucket
        # total IS that single level's exact count, so printing "1 category
        # combined, n=4" still directly discloses 4. The shared helper folds
        # smallest-first until the combined bucket is either empty or safely
        # >= threshold (or, pathologically, the whole per-level breakdown
        # must be suppressed).
        _sg_vc_full = _sg_series_in.value_counts(dropna=True)
        _sg_level_counts = {str(k): int(v) for k, v in _sg_vc_full.items()}
        _sg_visible, _sg_combined_n, _sg_combined_k = share_safe.safe_combine_rare_levels(
            _sg_level_counts, threshold=_SG_MIN_DISCLOSURE_N
        )
        if not _sg_visible and _sg_combined_n is not None and _sg_combined_n < _SG_MIN_DISCLOSURE_N:
            _sg_dist_a5 = f"Not reported (n<{_SG_MIN_DISCLOSURE_N} in every category, combined)"
        else:
            _sg_dist_parts = [f"{k}: {v}" for k, v in _sg_visible.items()]
            if _sg_combined_k:
                _sg_dist_parts.append(
                    share_safe.format_combined_levels_note(_sg_combined_k, _sg_combined_n)
                )
            _sg_dist_a5 = "; ".join(_sg_dist_parts) if _sg_dist_parts else f"Not reported (n<{_SG_MIN_DISCLOSURE_N} in every category)"
    else:
        _sg_dist_a5 = "Distribution not shown for this variable type"

    # Share-safe display of the table's own "Applicable N" / "Observed N" /
    # "Missing within subgroup" columns -- previously always printed as exact
    # integers regardless of size, even when the "Distribution" field for the
    # same row was already correctly suppressed (e.g. age_at_neonatal_death,
    # whose Applicable N is a protected small cell). safe_count() protects a
    # small total on its own;
    # safe_count_with_complement() additionally protects Observed N whenever
    # its complement (the missing count) would itself be a small cell -- a
    # large, "safe-looking" Observed N shown next to a safe Applicable N
    # still discloses a small missing count by subtraction otherwise.
    _sg_applicable_disp = share_safe.safe_count(
        _n_sg_a5, threshold=_SG_MIN_DISCLOSURE_N, enabled=SHARE_SAFE_MODE
    )
    _sg_observed_disp = share_safe.safe_count_with_complement(
        _sg_documented_n, _n_sg_a5, threshold=_SG_MIN_DISCLOSURE_N, enabled=SHARE_SAFE_MODE
    )

    # Missing WITHIN the applicable subgroup -- genuine/unresolved missingness,
    # distinct from structural NaN outside the subgroup.
    _sg_acc = SUBGROUP_ACCOUNTING[_sg_col]
    if _sg_acc["fully_explained_by_structural"]:
        _sg_miss_str = f"0 of {_sg_applicable_disp}"
    else:
        _sg_miss_n = _sg_acc["missing_inside_applicable_N"]
        if isinstance(_sg_observed_disp, str) or isinstance(_sg_applicable_disp, str):
            # Observed N and/or Applicable N is itself protected in this row
            # -- the exact missing count cannot be safely shown alongside it
            # either, UNLESS it is a genuine zero (a zero missing count
            # discloses nothing about any individual record and stays
            # visible regardless of whether the totals themselves are
            # hidden, consistent with this project's "genuine zero stays
            # zero" convention).
            _sg_miss_disp = 0 if _sg_miss_n == 0 else share_safe.safe_count(
                _sg_miss_n, threshold=_SG_MIN_DISCLOSURE_N, enabled=SHARE_SAFE_MODE
            )
            _sg_miss_str = f"{_sg_miss_disp} of {_sg_applicable_disp}"
        else:
            _sg_pct_disp, _ = share_safe.safe_pct_with_denominator(
                _sg_miss_n, _n_sg_a5, threshold=_SG_MIN_DISCLOSURE_N, enabled=SHARE_SAFE_MODE
            )
            _sg_miss_str = f"{_sg_miss_n} of {_n_sg_a5} ({_sg_pct_disp}%)"

    _sg_rows.append({
        "Variable": _sg_col,
        "Applicable subgroup": _sg_label_a5,
        "Applicable N": _sg_applicable_disp,
        "Observed N": _sg_observed_disp,
        "Missing within subgroup": _sg_miss_str,
        "Distribution / summary": _sg_dist_a5,
    })

_sg_table = pd.DataFrame(_sg_rows)
print("Subgroup-applicable variables — missingness within their clinically applicable subgroup:")
print(_sg_table.to_string(index=False))
print()

# Full per-column missingness table sorted by group then by missing%
_miss_cols = inv_df.sort_values(
    ["group", "missing_%"], ascending=[True, False]
)[["column", "group", "missing_%", "structural_nan", "potentially_structural_pending"]].copy()

# Print only columns with any missingness
_with_miss = _miss_cols[_miss_cols["missing_%"] > 0]
print(f"Columns with any missing values: {len(_with_miss)} of {len(df.columns)}")
print()
print(_with_miss.to_string(index=False))
""")

SA5_MISS_HEATMAP = code("eda-a-s05-miss-heatmap", """
# Missingness heatmap — all columns sorted by missing%
# x-axis = anonymised delivery-record rows, y-axis = variables with missing values
# No patient-level IDs on any axis.

_miss_sorted = inv_df.sort_values("missing_%", ascending=False)["column"].tolist()
_miss_matrix = df[_miss_sorted].isna().astype(int)  # 1=missing, 0=present

# Only show columns with any missing to keep the heatmap readable
_cols_with_miss = [c for c in _miss_sorted if df[c].isna().any()]
if len(_cols_with_miss) == 0:
    print("No missing values — heatmap skipped.")
else:
    _hm_data = df[_cols_with_miss].isna().astype(int)
    _n_show = min(30, len(_cols_with_miss))
    _hm_data = _hm_data.iloc[:, :_n_show]

    _fig_w = max(10, _n_show * 0.35)
    fig, ax = plt.subplots(figsize=(_fig_w, 5))
    sns.heatmap(
        _hm_data.T, cmap="Greys", cbar=False, ax=ax,
        yticklabels=_hm_data.columns.tolist(),
        xticklabels=False,  # no patient-level row labels
    )
    ax.set_xlabel(f"Delivery records (N={len(df)}, rows anonymised)")
    ax.set_ylabel("")
    ax.set_title(
        f"Missingness heatmap — {len(_cols_with_miss)} columns with missing values"
        + (f" (first {_n_show} shown)" if len(_cols_with_miss) > _n_show else "")
    )
    ax.tick_params(axis="y", labelsize=7)
    plt.tight_layout()
    plt.show()
    print(f"Black = missing  |  White = present  |  Sorted by missing%")
    print("Note: this heatmap is an internal descriptive diagnostic only. "
          "It is not used for row/column exclusion or imputation decisions.")
""")

SA5_KEY_OBS = md("eda-a-s05-key-observations", """**Key observations:**""")

SA5_KEY_OBS_CODE = code("eda-a-s05-key-observations-code", """
# `structural_nan` is CONFIRMED-only (a code-enforced
# subgroup gate) -- `~inv_df["structural_nan"]` therefore now correctly
# INCLUDES potentially_structural_pending columns in the "requires review"
# high-missingness bucket below, rather than silently exempting them the way
# the prior combined flag did. A pending/unconfirmed column must never be
# given a free pass from missingness review.
_ko5_high_miss = inv_df[(inv_df["missing_%"] >= 70) & (~inv_df["structural_nan"])]
_ko5_struct = inv_df[inv_df["structural_nan"]]
_ko5_pending = inv_df[inv_df["potentially_structural_pending"]]
_ko5_pred_miss = inv_df[(inv_df["group"] == "predictor_allowed") & (inv_df["missing_%"] > 0)]

print(f"- {int((inv_df['missing_%'] == 0).sum())} of {len(inv_df)} columns are fully "
      f"complete; {len(_with_miss)} columns have at least some missingness.")
_ko5_partial_struct_n = sum(
    1 for c in SUBGROUP_ACCOUNTING if not SUBGROUP_ACCOUNTING[c]["fully_explained_by_structural"]
)
print(f"- {len(_ko5_struct)} column(s) have a CONFIRMED structural-missingness component "
      f"(code-enforced subgroup gate) outside a clinically applicable subgroup; "
      f"{_ko5_partial_struct_n} of these also retain genuine missingness within the "
      f"applicable subgroup (not fully explained by clinical applicability), as detailed "
      f"in the subgroup applicability report below.")
if len(_ko5_pending):
    print(f"- {len(_ko5_pending)} additional column(s) are POTENTIALLY structural but "
          f"PENDING confirmation (no code-enforced gate): "
          f"{_ko5_pending['column'].tolist()}. These are never treated as structural-by-"
          f"design and remain subject to ordinary missingness review.")
if len(_ko5_high_miss):
    print(f"- {len(_ko5_high_miss)} column(s) without a CONFIRMED structural-missingness "
          f"gate have >=70% missing "
          f"(e.g. {_ko5_high_miss.sort_values('missing_%', ascending=False)['column'].tolist()[:5]}"
          f"{'...' if len(_ko5_high_miss) > 5 else ''}) -- this set includes any "
          f"potentially-structural-pending column with high missingness, which is NOT "
          f"exempted from this review bucket. This is a descriptive, whole-dataset "
          f"finding across all {len(df.columns)} columns -- it includes audit/source/comment/outcome "
          f"and other non-modeling variables that are not candidates for imputation at "
          f"all. It does NOT imply that every such column requires missingness-mechanism "
          f"review; that assessment is only relevant for variables actually considered "
          f"for downstream analysis/modeling and for which a missing-data treatment "
          f"decision is needed.")
print(f"- {len(_ko5_pred_miss)} of {int((inv_df['group']=='predictor_allowed').sum())} "
      f"predictor_allowed variables have any missingness. Note: the row-level "
      f"missingness summary above is computed across all {len(df.columns)} dataset "
      f"columns, not restricted to predictor_allowed variables, so it does not represent "
      f"predictor-frame row-level missingness; that is evaluated separately in the "
      f"companion notebook's Section A2.7.")
print("- Observed missingness patterns above may suggest MCAR does not hold for some "
      "variables (e.g. concentration in specific columns or co-occurring gaps), but MNAR "
      "cannot be established from the observed dataset alone -- this requires "
      "consideration during the cleaning/modeling stage, not a conclusion drawn here.")
""")


# ── Section A6 ────────────────────────────────────────────────────────────────
SA6_HEADER = md("eda-a-s06-header", """
## Section A6 — Univariate Descriptive Overview of Predictor Candidates

This section provides an unstratified, Table-1-style descriptive overview of all current
`predictor_allowed` variables, using each variable's statistical type (numeric,
binary, or categorical) to report the appropriate summary: numeric variables get N,
missingness, mean, SD, median, IQR, and min/max; binary variables get N, missingness, and
positive count/rate; categorical variables get N, missingness, and number of levels. No
association tests, between-group comparisons, or variable selection are performed here —
those are covered elsewhere in this notebook and its companion.

This section is intentionally scoped to Stage 1 (`predictor_allowed`) only, consistent
with Part 1's role as a basic, all-columns inventory. Full descriptive and statistical
coverage of Stage 2 (`predictor_allowed` + `secondary_near_delivery_predictor`) and
Stage 3 (Stage 2 + `intrapartum_predictor_exclude_from_prelabor_model`) — the cumulative
prediction stages — is provided in the companion Part 2 notebook,
which attaches each variable's earliest cumulative-stage entry point to every summary
table it builds.
""")

SA6_TABLE1 = code("eda-a-s06-table1", """
def _infer_var_type(s, bin_thresh=3, cat_thresh=20):
    # Schema-first: consult the canonical variable_type_schema_minimal.csv
    # (VARIABLE_TYPE_MAP, loaded in Part 1) so numeric-coded categorical
    # variables (e.g. mode_of_conception) and small-range count variables
    # (e.g. G/P/LIVE_BIRTH/AB/CS) are typed correctly. Falls back to the
    # legacy dtype/unique-count heuristic only for a variable absent from
    # the schema (e.g. if the schema file could not be found).
    col = getattr(s, "name", None)
    if col in VARIABLE_TYPE_MAP:
        return SCHEMA_TO_EDA_TYPE.get(VARIABLE_TYPE_MAP[col], "categorical")
    s2 = s.dropna()
    if s2.empty:
        return "empty"
    if s2.nunique() <= bin_thresh and set(s2.unique()).issubset({0, 1, 0.0, 1.0}):
        return "binary"
    if pd.api.types.is_numeric_dtype(s) and s2.nunique() > cat_thresh:
        return "numeric"
    if s2.nunique() <= cat_thresh:
        return "categorical"
    return "numeric"

_numeric_rows, _binary_rows, _cat_rows = [], [], []

for _col in PREDICTOR_ALLOWED_COLS:
    if _col not in df.columns:
        continue
    _vtype = _infer_var_type(df[_col])
    _sub   = df[[_col]].dropna()
    _miss_n   = int(df[_col].isna().sum())
    _miss_pct = round(df[_col].isna().mean() * 100, 1)
    # Consult both structural-missingness registries (matching Section A3's
    # convention): APPLICABILITY_LINKED_COLS for the PENDING/unconfirmed tier
    # (no code-enforced gate), and SUBGROUP_APPLICABLE_COLS for the CONFIRMED
    # tier (code-enforced gate, e.g. cesarean-only or
    # endometriosis_surgery==1-only variables). Kept
    # as two SEPARATE booleans, matching Section A3's inv_df -- a pending
    # column must never be labeled "structural_nan" (confirmed) here.
    _structural_confirmed = _col in SUBGROUP_APPLICABLE_COLS
    _structural_pending = _col in APPLICABILITY_LINKED_COLS

    if _vtype == "numeric":
        _s = _sub[_col]
        _numeric_rows.append({
            "variable": _col, "N": len(_sub), "missing_%": _miss_pct,
            "structural_nan": _structural_confirmed,
            "potentially_structural_pending": _structural_pending,
            "mean": round(_s.mean(), 2), "SD": round(_s.std(), 2),
            "median": round(_s.median(), 2),
            "Q1": round(_s.quantile(0.25), 2), "Q3": round(_s.quantile(0.75), 2),
            "min": round(_s.min(), 2), "max": round(_s.max(), 2),
        })
    elif _vtype == "binary":
        _n_pos = int((_sub[_col] == 1).sum())
        _pos_pct = round(100 * _n_pos / len(_sub), 1) if len(_sub) else None
        _zero_variance = bool(_pos_pct is not None and _pos_pct in (0, 100))
        # True zero-variance (no positive cases, or -- symmetrically -- no
        # negative cases) is distinct from merely rare/near-zero-variance
        # (a nonzero but small minority category). Both are descriptive flags
        # only; eligibility is unchanged in Part 1 either way.
        # n_positive/positive_% here MUST stay raw
        # numeric -- this dict feeds the analytical _binary_rows/_ko6_binary_df
        # used for numeric comparisons below (zero-variance/rare-variance
        # filtering) and in Section A6's key-observations cell. Storing a
        # share-safe *string* here instead (as a prior revision did) made
        # `_ko6_binary_df["positive_%"] < 5` crash at runtime with TypeError
        # the moment any binary variable had 1-4 positive cases, since pandas
        # cannot compare a string to an int. Suppression is applied only to a
        # separate display copy, built just before printing, below.
        _binary_rows.append({
            "variable": _col, "N": len(_sub), "missing_%": _miss_pct,
            "structural_nan": _structural_confirmed,
            "potentially_structural_pending": _structural_pending,
            "n_positive": _n_pos,
            "positive_%": _pos_pct,
            "zero_variance": _zero_variance,
        })
    else:
        _cat_rows.append({
            "variable": _col, "N": len(_sub), "missing_%": _miss_pct,
            "structural_nan": _structural_confirmed,
            "potentially_structural_pending": _structural_pending,
            "n_levels": int(_sub[_col].nunique()),
        })

print("Note: these summaries are unstratified and are not association tests with the target.")
print()
if _numeric_rows:
    print("Numeric predictor candidates:")
    print(pd.DataFrame(_numeric_rows).to_string(index=False))
    print()
if _binary_rows:
    print("Binary predictor candidates:")
    # Share-safe display copy ONLY: n_positive can be small
    # (1-4) for a rare whole-cohort binary finding -- suppressed here for
    # display, on the same numerator-OR-complement n<5 rule used elsewhere.
    # The underlying _binary_rows list (and any DataFrame built from it
    # below, e.g. _ko6_binary_df) keeps raw numeric values for computation.
    _binary_df_display = pd.DataFrame(_binary_rows)
    # n_positive is shown alongside its own N in the
    # same row -- plain safe_count() only checks the numerator, so a large
    # unsuppressed n_positive (e.g. 443 of N=447) still discloses a small
    # complement (4) by subtraction. Uses the complement-aware helper.
    _binary_df_display["n_positive"] = [
        share_safe.safe_count_with_complement(int(_r["n_positive"]), int(_r["N"]), enabled=SHARE_SAFE_MODE)
        for _r in _binary_rows
    ]
    _binary_df_display["positive_%"] = [
        share_safe.safe_pct_with_denominator(int(_r["n_positive"]), int(_r["N"]), enabled=SHARE_SAFE_MODE)[0]
        for _r in _binary_rows
    ]
    print(_binary_df_display.to_string(index=False))
    print()
if _cat_rows:
    print("Categorical predictor candidates (multi-level):")
    print(pd.DataFrame(_cat_rows).to_string(index=False))
""")

SA6_KEY_OBS = md("eda-a-s06-key-observations", """**Key observations:**""")

SA6_KEY_OBS_CODE = code("eda-a-s06-key-observations-code", """
# _binary_rows holds raw numeric n_positive/positive_%
# (see the SA6_TABLE1 comment above); safe to compare numerically below.
_ko6_binary_df = pd.DataFrame(_binary_rows)
print(f"- {len(_numeric_rows)} numeric, {len(_binary_rows)} binary, and {len(_cat_rows)} "
      f"multi-level categorical predictor candidates in the current predictor_allowed pool.")
if len(_ko6_binary_df):
    _ko6_zerovar = _ko6_binary_df.loc[_ko6_binary_df["zero_variance"], "variable"].tolist()
    _ko6_rare = _ko6_binary_df.loc[
        ~_ko6_binary_df["zero_variance"] &
        ((_ko6_binary_df["positive_%"] < 5) | (_ko6_binary_df["positive_%"] > 95)), "variable"
    ].tolist()
    if _ko6_zerovar:
        print(f"- Zero-variance binary predictor(s) (no positive cases observed in this "
              f"cohort): {_ko6_zerovar}. These remain in the {len(PREDICTOR_ALLOWED_COLS)}-variable "
              f"predictor_allowed pool in Part 1; final analytical handling occurs in Part 2.")
    if _ko6_rare:
        print(f"- Rare/near-zero-variance binary variable(s) (<5% or >95% positive, but "
              f"not zero-variance): {_ko6_rare} -- flag for near-zero-variance "
              f"consideration during Feature Selection; not modified here.")
    _ko6_struct_bin = _ko6_binary_df.loc[_ko6_binary_df["structural_nan"], "variable"].tolist()
    if _ko6_struct_bin:
        print(f"- {len(_ko6_struct_bin)} binary predictor(s) carry a CONFIRMED structural_nan "
              f"flag (code-enforced subgroup gate; missingness is by clinical design outside "
              f"an applicable subgroup, not a data-quality gap; see A7 for the full subgroup "
              f"breakdown): {_ko6_struct_bin}")
    _ko6_pending_bin = _ko6_binary_df.loc[
        _ko6_binary_df["potentially_structural_pending"], "variable"
    ].tolist()
    if _ko6_pending_bin:
        print(f"- {len(_ko6_pending_bin)} binary predictor(s) are POTENTIALLY structural but "
              f"PENDING confirmation (no code-enforced gate, not exempted from missingness "
              f"review): {_ko6_pending_bin}")
print("- These summaries are unstratified descriptives; between-group (vaginal vs. "
      "intrapartum CS) comparisons with formal tests are performed in the companion "
      "predictor-readiness notebook.")
""")


# ── Section A7 ────────────────────────────────────────────────────────────────
SA7_HEADER = md("eda-a-s07-header", """
## Section A5 — Predictor Pool and Exclusion Rationale

This section defines the primary predictor pool and documents, group by group, why
every other variable is excluded or deferred from it: source, free-text, or audit-only
variables (`source_or_text_audit_exclude`); variables used to define or verify the
cohort (`cohort_control_exclude`); broad or clinically heterogeneous variables
(`clinically_nonspecific_exclude`); variables retained for audit, cohort-rule
derivation, or outcome-independent sensitivity analysis but excluded from every stage
because an alternative variable is the approved modeled representation of the same
information (`clinically_redundant_exclude`); variables that directly encode the
target or CS decision (`leakage_exclude`); intrapartum/postpartum/neonatal variables
(`intrapartum_or_post_delivery_exclude`); near-delivery variables excluded from Stage 1
but added in Stage 2 and remaining eligible in Stage 3 -- not a hard exclusion and not
intrapartum-only (`secondary_near_delivery_predictor`); confirmed-intrapartum-timing
variables excluded from the current pre-labor predictor pool only
(`intrapartum_predictor_exclude_from_prelabor_model`); timing not reliably determinable
from this dataset (`intrapartum_candidate_pending_timing_confirmation`); variables
awaiting source/coding clarification (`manual_review_pending`); timing/context not yet
confirmed (`awaiting_clinical_clarification`); and patient/delivery identifiers (`id`,
never used in any model). No variable classification is changed and no statistical
analysis is performed here — this section documents the existing classification and
re-asserts, as a safety check, that no excluded column appears in `predictor_allowed`.
""")

SA7_RECONCILIATION_HEADER = md("eda-a-s07-reconciliation-header", """**Predictor pool and exclusion accounting:**""")

SA7_RECONCILIATION = code("eda-a-s07-reconciliation", """
# Full column accounting, derived dynamically from the canonical classification
# data (never hardcoded): total columns = Stage 1 + Stage 2 additions + Stage 3
# additions + everything else excluded/deferred from every prediction stage + target.
# These five groups are disjoint by construction (each column belongs to exactly one
# canonical classification label) and sum exactly to the total column count.
_a5_total_cols = len(df.columns)
_a5_n_stage1 = len(PREDICTOR_ALLOWED_COLS)
_a5_n_stage2 = len(SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS)
_a5_n_stage3 = len(INTRAPARTUM_PREDICTOR_EXCLUDE_COLS)
_a5_n_target = len(TARGET_COLS)
# "Excluded/deferred" here means excluded from ALL THREE prediction stages -- the
# 5 Stage-3 variables are NOT counted here, since they are eligible for Stage 3
# (see the companion Part 2 notebook), not hard exclusions.
_a5_n_excluded = _a5_total_cols - _a5_n_stage1 - _a5_n_stage2 - _a5_n_stage3 - _a5_n_target

print(f"{_a5_total_cols} total columns = {_a5_n_stage1} Stage 1 (pre-labor) "
      f"+ {_a5_n_stage2} Stage 2 additions (secondary near-delivery) "
      f"+ {_a5_n_stage3} Stage 3 additions (intrapartum) "
      f"+ {_a5_n_excluded} excluded/deferred from every stage "
      f"+ {_a5_n_target} target")
print()
print(f"- The {_a5_n_stage1} predictor_allowed variables form Stage 1 (pre-labor) of the "
      f"cumulative 3-stage predictor universe.")
print(f"- The {_a5_n_stage2} secondary_near_delivery_predictor variables are not hard "
      f"exclusions -- they are excluded from Stage 1 but added in Stage 2 (pre-labor + "
      f"near-delivery) and remain in Stage 3; see the companion Part 2 notebook for full "
      f"Stage 2/3 coverage.")
print(f"- The {_a5_n_stage3} intrapartum_predictor_exclude_from_prelabor_model variables "
      f"are also not hard exclusions -- they are excluded from Stage 1 and Stage 2 but "
      f"added in Stage 3 (pre-labor + near-delivery + intrapartum); see the "
      f"companion Part 2 notebook.")
print(f"- The {_a5_n_excluded} variables shown in the exclusion audit below are excluded "
      f"or deferred from every prediction stage (Stage 1, 2, and 3 alike) -- e.g. "
      f"leakage, post-delivery, source/audit-only, cohort-control, or pending-review "
      f"variables.")
print(f"- The target ({_a5_n_target} column) is not a predictor.")
""")

SA7_EXCLUSIONS = code("eda-a-s07-exclusions", """
# Groups excluded from ALL THREE prediction stages (hard exclusions) -- these
# are the groups that make up _a5_n_excluded in the reconciliation above.
_EXCL_GROUPS = [
    ("source_or_text_audit_exclude",
     SOURCE_OR_TEXT_AUDIT_EXCLUDE_COLS,
     "Source, free-text, or raw-detail variables retained for "
     "audit/documentation only; excluded from direct modeling."),
    ("cohort_control_exclude",
     COHORT_CONTROL_EXCLUDE_COLS,
     "Variables used to define, filter, or verify the analytical cohort. "
     "Retained for audit and reproducibility but excluded from predictor "
     "modeling."),
    ("clinically_nonspecific_exclude",
     CLINICALLY_NONSPECIFIC_EXCLUDE_COLS,
     "Broad or clinically heterogeneous variables that lack sufficient "
     "specificity for meaningful predictor modeling. Retained for "
     "documentation and audit but excluded from predictor modeling "
     "following clinical expert guidance."),
    ("clinically_redundant_exclude",
     CLINICALLY_REDUNDANT_EXCLUDE_COLS,
     "Retained for audit, cohort-rule derivation, and outcome-independent "
     "sensitivity analyses, but excluded from every prediction stage because "
     "clinical experts selected a different variable as the modeled "
     "representation of the overlapping information."),
    ("leakage_exclude",
     LEAKAGE_EXCLUDE_COLS,
     "Variables that directly encode the target, cesarean decision, cesarean "
     "indication, or operative findings after the target decision."),
    ("intrapartum_or_post_delivery_exclude",
     INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS,
     "Variables measured or determined during labor, delivery, postpartum, or "
     "neonatal period; retained for outcomes/audit only."),
    ("intrapartum_candidate_pending_timing_confirmation",
     PENDING_TIMING_CONFIRMATION_COLS,
     "Timing relative to admission/labor cannot be reliably determined from "
     "this dataset; excluded from the primary pre-labor model on conservative "
     "timing-uncertainty grounds, not confirmed intrapartum."),
    ("manual_review_pending",
     MANUAL_REVIEW_PENDING_COLS,
     "Source or coding ambiguous (prior surgery vs current CS findings). "
     "Excluded until clinical/source review is complete; some variables may become "
     "candidates for a future model version after review."),
    ("awaiting_clinical_clarification",
     AWAITING_CLINICAL_CLARIFICATION_COLS,
     "Timing relative to the CS decision is unconfirmed. "
     "Pending clinical review before any use in modeling."),
    ("id",
     ID_COLS,
     "Patient/delivery identifiers. Must never enter any model."),
]

# Shown separately, NOT included in _EXCL_GROUPS / _total_excl: this group is
# a Stage 3 addition, not a hard exclusion from every stage --
# it is excluded from Stage 1 and Stage 2 only, and IS eligible in Stage 3.
_STAGE3_GROUP = (
    "intrapartum_predictor_exclude_from_prelabor_model",
    INTRAPARTUM_PREDICTOR_EXCLUDE_COLS,
    "Clinically confirmed intrapartum timing; excluded from "
    "Stage 1 and Stage 2, but added in Stage 3 (pre-labor + near-delivery + "
    "intrapartum) -- NOT a hard exclusion from every stage.",
)
print(f"STAGE 3 ADDITION (not a hard exclusion) -- "
      f"{_STAGE3_GROUP[0].upper()}  ({len(_STAGE3_GROUP[1])} columns)")
print(f"    Why: {_STAGE3_GROUP[2]}")
print(f"    Columns: {_STAGE3_GROUP[1]}")
print()

_total_excl = sum(len(g) for _, g, _ in _EXCL_GROUPS)
print(f"Hard-excluded variable groups (excluded from every prediction stage) — "
      f"{_total_excl} columns total")
print(f"(Of {len(df.columns)} total columns in the processed dataset; matches "
      f"_a5_n_excluded above)")
print()

for _grp_name, _grp_cols, _why in _EXCL_GROUPS:
    _present = [c for c in _grp_cols if c in df.columns]
    _absent  = [c for c in _grp_cols if c not in df.columns]
    print(f"  {_grp_name.upper()}  ({len(_grp_cols)} configured, {len(_present)} in file)")
    print(f"    Why: {_why}")
    print(f"    Columns: {_present[:6]}" +
          (f"  ... and {len(_present)-6} more" if len(_present) > 6 else ""))
    if _absent:
        print(f"    Not in file: {_absent}")
    print()

# Safety re-assert: no excluded column is in PREDICTOR_ALLOWED_COLS
_excl_set = set(
    c for _, cols, _ in _EXCL_GROUPS for c in cols
)
_overlap = sorted(set(PREDICTOR_ALLOWED_COLS) & _excl_set)
if _overlap:
    print(f"Note: {len(_overlap)} variable(s) unexpectedly appear in both the eligible "
          f"predictor set and an excluded category: {_overlap}")
else:
    print("No variables in the eligible predictor set overlap with categories excluded from prediction.")

print()
# Dynamic, not hardcoded: correctly reflects the current canonical registry
# state, whether or not any variables remain pending.
_a5_pending_total = (
    len(PENDING_TIMING_CONFIRMATION_COLS)
    + len(MANUAL_REVIEW_PENDING_COLS)
    + len(AWAITING_CLINICAL_CLARIFICATION_COLS)
)
if _a5_pending_total == 0:
    print("No variables currently remain in pending timing, manual-review, or "
          "clinical-clarification groups (all three groups are empty in the "
          "current canonical classification).")
else:
    print(f"Note: {_a5_pending_total} variable(s) remain in pending timing, "
          f"manual-review, or clinical-clarification groups; these are "
          f"deferred to clinical review before any modeling use.")
print("Current classifications reflect the canonical registry state at notebook build time.")
""")

SA7_KEY_OBS = md("eda-a-s07-key-observations", """**Key observations:**""")

SA7_KEY_OBS_CODE = code("eda-a-s07-key-observations-code", """
print(f"- {_total_excl} of {len(df.columns)} columns are excluded or deferred from "
      f"every prediction stage, spread across {len(_EXCL_GROUPS)} rationale groups "
      f"(leakage, post-delivery timing, source/audit-only, pending review, etc.).")
_ko7_largest = max(_EXCL_GROUPS, key=lambda g: len(g[1]))
print(f"- Largest exclusion group: '{_ko7_largest[0]}' ({len(_ko7_largest[1])} columns).")
print("- " + (
    "No variables in the eligible predictor set overlap with categories excluded from prediction."
    if not _overlap else f"Overlap detected involving: {_overlap}."
))
print("- These are documentation/audit groupings only; no variable is dropped from the "
      "dataframe by this notebook.")
""")


# ── Section A8 — Outlier Screening (simplified; deep analysis is EDA A Part 2, Section A2.11) ──
SA_OUTLIERS_HEADER = md("eda-a-s12-outliers-header", """
## Section A8 — Initial IQR Outlier Screening

This section screens the numeric predictor candidates (the `continuous` and
`count` types from the variable-type schema, restricted to `predictor_allowed` variables)
for potential outliers using the IQR 1.5× rule, reporting per-variable bounds and the
count/rate of values outside them. This is a screening diagnostic only: no values are
removed or modified, no modeling eligibility is changed, and an IQR flag is not itself a
classification of a value as erroneous — statistical extremeness is not equivalent to
clinical impossibility. The main results table below lists only the predictors with at
least one flagged value (`n_flagged >= 1`); predictors with zero flags, and predictors
whose IQR is zero (for which standard 1.5×IQR flagging is not informative), are reported
separately so the full evaluated set remains visible. Descriptive outlier sensitivity
analysis, including outcome-rate comparison, is presented in A2 Section A2.11; those
target-aware comparisons are descriptive only and do not determine preprocessing or
feature selection.
""")

SA_OUTLIERS = code("eda-a-s12-outliers", """
# Outlier screening — IQR 1.5x, canonical numeric predictor_allowed columns only.
# SCREENING ONLY: no values removed, no modeling eligibility changed, no automatic
# classification as errors. The target is never consulted to decide whether an
# observation is flagged, and no feature selection is performed here.

# Numeric predictor set is read directly from the canonical variable-type schema
# (VARIABLE_TYPE_MAP, loaded in Part 1) -- the same source of truth already
# established in A3/A6 -- rather than re-inferred from storage dtype/cardinality.
# "continuous" and "count" are the schema's numeric types (see SCHEMA_TO_EDA_TYPE
# in Part 1, which maps both to the EDA "numeric" category).
_num_pred = [
    c for c in PREDICTOR_ALLOWED_COLS
    if c in df.columns
    and VARIABLE_TYPE_MAP.get(c) in ("continuous", "count")
]

_out_rows = []          # predictors with n_flagged >= 1 (the main results table)
_no_flag_rows = []      # predictors with IQR > 0 but zero flagged values
_iqr_zero_rows = []     # predictors with IQR == 0 -- not meaningfully screenable by
                        # the standard 1.5x-IQR rule; still evaluated and reported.
                        # IQR == 0 does NOT necessarily mean zero variance in the
                        # variable itself (e.g. a skewed distribution can have Q1==Q3
                        # while still having a wide observed range) and is not
                        # described as "constant" or "near-constant" here.
_insufficient_rows = [] # fewer than 4 non-missing values -- quartiles not reliable

for _col in _num_pred:
    _s = df[_col].dropna()
    if len(_s) < 4:
        _insufficient_rows.append(_col)
        continue
    _q1, _q3 = _s.quantile(0.25), _s.quantile(0.75)
    _iqr = _q3 - _q1
    # Matches A3/A6's convention: APPLICABILITY_LINKED_COLS is the PENDING/
    # unconfirmed tier (no code-enforced gate), SUBGROUP_APPLICABLE_COLS is
    # the CONFIRMED tier (code-enforced gate, e.g. endometrioma_size_clean).
    # kept as two SEPARATE booleans -- a pending
    # column must never be labeled "structural_nan" (confirmed) here.
    # Display/metadata only -- does not affect IQR bounds, flagged_%, or
    # which observations are flagged.
    _structural_confirmed = _col in SUBGROUP_APPLICABLE_COLS
    _structural_pending = _col in APPLICABILITY_LINKED_COLS
    if _iqr == 0:
        _iqr_zero_rows.append({
            "variable":       _col,
            "N_non_missing":  len(_s),
            "structural_nan": _structural_confirmed,
            "potentially_structural_pending": _structural_pending,
            "note":           "IQR-based outlier screening not informative because IQR = 0",
        })
        continue
    _lo, _hi = _q1 - 1.5 * _iqr, _q3 + 1.5 * _iqr
    _n_out = int(((df[_col] < _lo) | (df[_col] > _hi)).sum())
    # flagged_% denominator is N_non_missing (observed values actually eligible for
    # IQR screening), not the full cohort N -- missing values are excluded from the
    # variable-specific IQR calculation, not imputed, and must not be counted as if
    # they were screened-and-not-flagged.
    # n_flagged/flagged_% here MUST stay raw numeric --
    # this dict feeds _out_df, which is sorted by flagged_% both below and
    # again in the key-observations cell. Storing a share-safe *string* here
    # instead (as a prior revision did) made `.sort_values("flagged_%")`
    # crash at runtime with TypeError the moment any predictor had 1-4
    # flagged values, since Python/pandas cannot order a string against a
    # float. Suppression is applied only to a separate display copy, built
    # just before printing, below.
    _row = {
        "variable":       _col,
        "N_non_missing":  len(_s),
        "n_flagged":      _n_out,
        "flagged_%":      round(100 * _n_out / len(_s), 1),
        "iqr_lower":      round(_lo, 2),
        "iqr_upper":      round(_hi, 2),
        "actual_min":     round(_s.min(), 2),
        "actual_max":     round(_s.max(), 2),
        "structural_nan": _structural_confirmed,
        "potentially_structural_pending": _structural_pending,
    }
    (_out_rows if _n_out >= 1 else _no_flag_rows).append(_row)

print(f"Canonical numeric predictor candidates evaluated (continuous/count types, "
      f"predictor_allowed only): {len(_num_pred)}")
if _insufficient_rows:
    print(f"  {len(_insufficient_rows)} variable(s) have fewer than 4 non-missing "
          f"values and could not be screened: {_insufficient_rows}")
print()

if not _out_rows:
    print("No canonical numeric predictor has an IQR-flagged value (n_flagged >= 1) "
          "in the current cohort.")
else:
    _out_df = pd.DataFrame(_out_rows).sort_values("flagged_%", ascending=False)
    print(f"Variables with at least one IQR-flagged value (n_flagged >= 1): "
          f"{len(_out_df)} of {len(_num_pred)} evaluated.")
    print("This table contains ONLY predictors with n_flagged >= 1 -- it is not the "
          "full evaluated set (see the zero-flag and IQR=0 breakdowns below).")
    print()
    # Share-safe display copy ONLY: n_flagged can be small
    # (1-4); _out_df itself (sorted above, and reused in the key-observations
    # cell below) keeps raw numeric values throughout.
    _out_df_display = _out_df.copy()
    # n_flagged is shown alongside N_non_missing in
    # the same row -- plain safe_count() only checks the numerator, so a
    # large unsuppressed n_flagged still discloses a small complement by
    # subtraction. Uses the complement-aware helper.
    _out_df_display["n_flagged"] = [
        share_safe.safe_count_with_complement(int(_n), int(_N), enabled=SHARE_SAFE_MODE)
        for _n, _N in zip(_out_df["n_flagged"], _out_df["N_non_missing"])
    ]
    _out_df_display["flagged_%"] = [
        share_safe.safe_pct_with_denominator(int(_n), int(_N), enabled=SHARE_SAFE_MODE)[0]
        for _n, _N in zip(_out_df["n_flagged"], _out_df["N_non_missing"])
    ]
    print(_out_df_display.to_string(index=False))
    print()
    print("Flagged observations are carried forward for deeper analytical and, where")
    print("clinically relevant, clinical review. No observation is classified as")
    print("erroneous based on the IQR rule alone.")
    print("Descriptive outlier sensitivity analysis, including outcome-rate comparison,")
    print("is presented in A2 Section A2.11; those target-aware comparisons are")
    print("descriptive only and do not determine preprocessing or feature selection.")

print()
_no_flag_vars = [r["variable"] for r in _no_flag_rows]
print(f"Variables with IQR > 0 and zero flagged values ({len(_no_flag_rows)}): "
      f"{_no_flag_vars}")

if _iqr_zero_rows:
    print()
    print(f"Variables with IQR == 0 ({len(_iqr_zero_rows)}) -- standard 1.5x-IQR "
          f"flagging is not informative for these and none was performed, but they "
          f"remain evaluated canonical numeric predictors, not silently dropped:")
    print(pd.DataFrame(_iqr_zero_rows).to_string(index=False))
""")

SA_OUTLIERS_KEY_OBS = md("eda-a-s12-key-observations", """**Key observations:**""")

SA_OUTLIERS_KEY_OBS_CODE = code("eda-a-s12-key-observations-code", """
if "_out_df" in dir() and len(_out_df):
    # _out_df holds raw numeric flagged_%; sort is safe.
    _ko12_top = _out_df.sort_values("flagged_%", ascending=False).iloc[0]
    _ko12_top_pct_disp, _ = share_safe.safe_pct_with_denominator(
        int(_ko12_top["n_flagged"]), int(_ko12_top["N_non_missing"]), enabled=SHARE_SAFE_MODE
    )
    _ko12_top_pct_str = (
        f"{_ko12_top_pct_disp}%" if isinstance(_ko12_top_pct_disp, (int, float)) else str(_ko12_top_pct_disp)
    )
    print(f"- {len(_out_df)} of {len(_num_pred)} numeric predictor candidates have at "
          f"least one IQR-flagged value; highest flagged rate is "
          f"'{_ko12_top['variable']}' ({_ko12_top_pct_str}).")
    _ko12_struct = _out_df.loc[_out_df["structural_nan"], "variable"].tolist()
    if _ko12_struct:
        print(f"- Flagged variable(s) that are also CONFIRMED structural-NaN "
              f"(interpret bounds with the applicable subgroup in mind): {_ko12_struct}")
    _ko12_pending = _out_df.loc[_out_df["potentially_structural_pending"], "variable"].tolist()
    if _ko12_pending:
        print(f"- Flagged variable(s) that are POTENTIALLY structural but PENDING "
              f"confirmation (no code-enforced gate): {_ko12_pending}")
    print("- No observation is classified as erroneous based on the IQR rule alone, and "
          "none are removed or altered here. Descriptive outlier sensitivity analysis, "
          "including outcome-rate comparison, is presented in A2 Section A2.11; those "
          "target-aware comparisons are descriptive only and do not determine "
          "preprocessing or feature selection.")
else:
    print("- No numeric predictor candidate has an IQR-flagged value in the current cohort.")
""")


# ── Section A9 — Findings Registry ────────────────────────────────────────────
SA_REGISTRY_HEADER = md("eda-a-s15-registry-header", """
## Section A9 — Findings Summary

This section summarizes key data-quality and eligibility screening findings already
identified in earlier EDA A sections — high missingness among predictor candidates, IQR
outlier flags from Section A8, and predictor-pool exclusions for leakage or post-delivery
timing. These are screening signals and proposals only: this section does not modify
data, variable classifications, preprocessing, or modeling eligibility. Full per-variable
detail is retained internally for review rather than printed in full here.
""")

SA_REGISTRY = code("eda-a-s15-registry", """
# EDA A Findings Registry — screening findings only.
# All entries are proposals / screening signals. No decisions are made here.
# No classifications are changed. No preprocessing is modified.

_registry_rows = []

# ── High missingness (>30%) among predictor candidates ──────────────────
# A column-level structural_nan=True flag means the variable HAS a structural
# component -- it does not by itself mean the observed missingness is fully
# explained by clinical design. SUBGROUP_ACCOUNTING (Section A3, Part 1)
# distinguishes "fully explained" (0 missing within the applicable subgroup)
# from "structural NaN outside the subgroup, but genuine missingness also
# remains inside it" -- the latter must never be reported as "by clinical
# design; never impute blindly" as a blanket statement.
if "inv_df" in dir():
    for _, _r in inv_df[inv_df["group"] == "predictor_allowed"].iterrows():
        if _r["missing_%"] > 30:
            _col_name = _r["column"]
            _acc = SUBGROUP_ACCOUNTING.get(_col_name) if "SUBGROUP_ACCOUNTING" in dir() else None
            if _acc is not None and _acc["fully_explained_by_structural"]:
                _sev = "by_design"
                _step = (
                    "Structural NaN -- missingness is fully explained by clinical design "
                    "(0 missing within the applicable subgroup); never impute blindly."
                )
            elif _acc is not None:
                _sev = "review"
                _step = (
                    f"Structural missingness exists outside the clinically applicable "
                    f"subgroup; {_acc['missing_inside_applicable_N']} of "
                    f"{_acc['applicable_N']} applicable rows "
                    f"({_acc['missing_inside_applicable_%']}%) remain missing within "
                    f"the subgroup -- assess missingness mechanism for this "
                    f"within-subgroup portion in EDA A Part 2 before imputation."
                )
            else:
                # this branch is only reached when the
                # column has no SUBGROUP_ACCOUNTING entry, i.e. it is NOT in
                # SUBGROUP_APPLICABLE_COLS (not confirmed) -- so
                # _r["structural_nan"] (confirmed-only) is always False here
                # by construction. A potentially_structural_pending column
                # (no code-enforced gate) must NEVER be assigned "by_design"
                # severity -- that would exempt it from missingness review.
                # It gets its own "review" severity with an explicit note
                # instead.
                _pending = bool(_r.get("potentially_structural_pending", False))
                if _pending:
                    _sev = "review"
                    _step = (
                        "POTENTIALLY structural (empirical missingness pattern only, no "
                        "code-enforced gate) -- PENDING clinical/source confirmation. Not "
                        "exempted from missingness review and not eligible for NaN-to-zero "
                        "recoding until confirmed."
                    )
                else:
                    _sev = "review"
                    _step = (
                        "Assess observed missingness patterns and the plausibility of MCAR/MAR "
                        "when planning downstream handling in EDA A Part 2; MNAR cannot be "
                        "established from observed data alone."
                    )
            _registry_rows.append({
                "section":          "A7 — Missingness",
                "variable":         _col_name,
                "finding_type":     "high_missingness",
                "missing_%":        _r["missing_%"],
                "severity":         _sev,
                "suggested_next_step": _step,
            })

# ── Outlier-flagged numeric predictors ──────────────────────────────────
if "_out_df" in dir() and len(_out_df):
    for _, _r in _out_df.iterrows():
        # Share-safe: _r["n_flagged"] is raw here (_out_df keeps
        # raw numeric values); suppress only in this printed registry text.
        _n_flagged_disp = share_safe.safe_count(int(_r["n_flagged"]), enabled=SHARE_SAFE_MODE)
        _registry_rows.append({
            "section":          "A8 — Outlier screening",
            "variable":         _r["variable"],
            "finding_type":     "iqr_outlier_flag",
            "missing_%":        None,
            "severity":         "screening_flag",
            "suggested_next_step": (
                f"{_n_flagged_disp} value(s) outside IQR bounds "
                f"[{_r['iqr_lower']}, {_r['iqr_upper']}]. Carry forward for deeper "
                "analytical review and, where clinically relevant, clinical review. "
                "IQR flagging alone does not classify the observation as erroneous. "
                "See EDA A Part 2, Section A2.11 for deeper analysis."
            ),
        })

# ── Excluded groups (audit reference) ───────────────────────────────────
for _grp, _cols in [
    ("leakage_exclude",                   LEAKAGE_EXCLUDE_COLS),
    ("intrapartum_or_post_delivery_exclude", INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS),
    ("manual_review_pending",             MANUAL_REVIEW_PENDING_COLS),
    ("awaiting_clinical_clarification",   AWAITING_CLINICAL_CLARIFICATION_COLS),
]:
    for _c in _cols:
        if _c in df.columns:
            _registry_rows.append({
                "section":          "A5 — Exclusion documentation",
                "variable":         _c,
                "finding_type":     _grp,
                "missing_%":        None,
                "severity":         "excluded",
                "suggested_next_step": (
                    "Classification confirmed; excluded from modeling. See A5 for rationale."
                ),
            })

if not _registry_rows:
    print("No findings to report.")
else:
    # Retained in the notebook namespace at full per-variable detail for internal
    # review; the reader-facing output below is a concise summary, not the full table.
    eda_a_registry = pd.DataFrame(_registry_rows)
    _n_high_miss = int((eda_a_registry["finding_type"] == "high_missingness").sum())
    _n_outlier = int((eda_a_registry["finding_type"] == "iqr_outlier_flag").sum())
    _excluded_types = [
        "leakage_exclude", "intrapartum_or_post_delivery_exclude",
        "manual_review_pending", "awaiting_clinical_clarification",
    ]
    _n_excluded = int(eda_a_registry["finding_type"].isin(_excluded_types).sum())

    print("Summary of screening findings:")
    print()
    print(f"- Substantial missingness (>30%) among predictor_allowed candidates: "
          f"{_n_high_miss} variable(s). See Section A7 for the full missingness "
          f"breakdown and the structural-vs-genuine distinction.")
    print(f"- Flagged by descriptive IQR outlier screening: {_n_outlier} variable(s). "
          f"See Section A8; IQR flagging alone does not classify an observation as "
          f"erroneous.")
    print(f"- Excluded from the predictor pool (leakage, post-delivery timing, or "
          f"pending clinical review): {_n_excluded} variable(s), not part of the "
          f"predictor_allowed pool. See Section A5 for the full exclusion rationale.")
    print()
    print("These are screening findings and proposed next steps only; no variable is")
    print("removed or reclassified here, and no new exclusion or modeling decision is")
    print("introduced.")
""")


# ── Section A10 — Final Summary ───────────────────────────────────────────────
SA_SUMMARY_HEADER = md("eda-a-s16-summary-header", """
## Section A10 — Part 1 Summary / Handoff

This section summarizes what is ready to carry forward into EDA A Part 2, what still
requires review, and what is permanently excluded from modeling.
""")

SA_SUMMARY = code("eda-a-s16-summary", """
print("=" * 70)
print("EDA A SUMMARY")
print("=" * 70)
print()
print(f"Cohort  : N={len(df)} (Vaginal={EXPECTED_N0}, Intrapartum CS={EXPECTED_N1}, "
      f"Ratio={EXPECTED_N0/EXPECTED_N1:.1f}:1)")
print(f"Dataset : {df.shape[0]} rows x {df.shape[1]} columns — all {df.shape[1]} columns have "
      f"an assigned classification")
print()

print("VARIABLE GROUPS:")
if "inv_df" in dir():
    for _g, _n in inv_df.groupby("group").size().sort_values(ascending=False).items():
        _col_unit = "column" if _n == 1 else "columns"
        print(f"  {_g:<45} {_n:>4} {_col_unit}")
print()

print("READY FOR EDA A PART 2:")
_ready = [c for c in PREDICTOR_ALLOWED_COLS if c in df.columns]
print(f"  predictor_allowed                : {len(_ready)} columns (predictor_allowed pool entering Part 2)")
if "_ko6_zerovar" in dir() and _ko6_zerovar:
    _n_effective = len(_ready) - len(_ko6_zerovar)
    print(f"    -- of these {len(_ready)}, {len(_ko6_zerovar)} ({sorted(_ko6_zerovar)}) were found in A6 to "
          f"have zero variance in this cohort (no positive cases observed). They remain part of the "
          f"canonical {len(_ready)}-variable predictor_allowed pool -- classification is unchanged and "
          f"they are NOT removed from it here -- but a variable with zero observed variance cannot "
          f"contribute to any variable-level inferential/modeling analysis (no contrast to estimate). "
          f"The effective candidate count actually usable for Part 2's inferential/modeling analysis "
          f"is therefore {len(_ready)} - {len(_ko6_zerovar)} = {_n_effective}.")
_snr = [c for c in SECONDARY_NEAR_DELIVERY_PREDICTOR_COLS if c in df.columns]
print(f"  secondary_near_delivery_predictor: {len(_snr)} columns (Stage 2 addition; eligible in "
      f"Stage 2 and Stage 3; full coverage in Part 2)")
_ipe = [c for c in INTRAPARTUM_PREDICTOR_EXCLUDE_COLS if c in df.columns]
print(f"  intrapartum_predictor_exclude_from_prelabor_model: {len(_ipe)} columns (Stage 3 addition; "
      f"excluded from Stage 1 and Stage 2, eligible only in Stage 3; NOT a hard "
      f"exclusion -- full coverage in Part 2)")
print()

print("REQUIRES REVIEW BEFORE MODELING:")
if "inv_df" in dir():
    # A variable with a structural component is only excluded from this review
    # list if its missingness is FULLY explained by clinical design (0 missing
    # within the applicable subgroup) -- see SUBGROUP_ACCOUNTING (Section A3,
    # Part 1). A column-level structural_nan=True flag alone is not sufficient:
    # some structural variables also carry genuine missingness inside their
    # applicable subgroup, which still requires review.
    #
    # The remaining candidates are split into two distinctly labeled groups so
    # this heading never implies that a subgroup-applicable predictor's full-
    # column missing_% (which is high mainly because it is not applicable
    # outside its subgroup) represents genuine within-subgroup missingness at
    # that same magnitude.
    _high_miss_candidates = inv_df[
        (inv_df["group"] == "predictor_allowed") & (inv_df["missing_%"] > 30)
    ]
    _hm_nonstructural, _hm_subgroup = [], []
    for _, _r in _high_miss_candidates.iterrows():
        _acc = SUBGROUP_ACCOUNTING.get(_r["column"]) if "SUBGROUP_ACCOUNTING" in dir() else None
        if _acc is not None and _acc["fully_explained_by_structural"]:
            continue  # fully explained by clinical design -- no review needed
        (_hm_subgroup if _acc is not None else _hm_nonstructural).append((_r, _acc))
    if _hm_nonstructural or _hm_subgroup:
        # Named "high-priority" (not "MISSINGNESS FINDINGS REQUIRING REVIEW") because
        # this list is restricted to predictor_allowed variables with >30% missing --
        # it is not the complete missingness picture (see A7 for the full per-column
        # missingness report across all dataset columns) and should not be read as such.
        print("  HIGH-PRIORITY MISSINGNESS FINDINGS:")
    if _hm_nonstructural:
        _hm_unit = "variable" if len(_hm_nonstructural) == 1 else "variables"
        print(f"    High non-structural missingness (full-column >30%, no CONFIRMED "
              f"applicable-subgroup structural component -- none of these are exempted "
              f"from review, including any potentially-structural-pending column below): "
              f"{len(_hm_nonstructural)} {_hm_unit}")
        for _r, _ in _hm_nonstructural:
            # flag a potentially-structural-pending column
            # explicitly here too, rather than lumping it in as flatly
            # "non-structural" -- it has a suspected (but unconfirmed) pattern,
            # not a confirmed absence of any structural explanation.
            _pending_note = (
                "  [POTENTIALLY STRUCTURAL -- PENDING CONFIRMATION]"
                if _r.get("potentially_structural_pending", False) else ""
            )
            print(f"      {_r['column']}: {_r['missing_%']}%{_pending_note}")
    if _hm_subgroup:
        _hm2_unit = "predictor" if len(_hm_subgroup) == 1 else "predictors"
        print(f"    Subgroup-applicable {_hm2_unit} with genuine within-subgroup "
              f"missingness (full-column missing_% is high mainly due to structural "
              f"non-applicability, not genuine missingness -- see A7 for the full "
              f"subgroup breakdown): {len(_hm_subgroup)} {_hm2_unit}")
        for _r, _acc in _hm_subgroup:
            print(f"      {_r['column']}: {_acc['missing_inside_applicable_N']} of "
                  f"{_acc['applicable_N']} applicable rows missing "
                  f"({_acc['missing_inside_applicable_%']}%) (full-column missing_%="
                  f"{_r['missing_%']}%)")
if "_out_df" in dir() and len(_out_df):
    _out_unit = "variable" if len(_out_df) == 1 else "variables"
    print(f"  IQR outlier-flagged predictors : {len(_out_df)} {_out_unit} (see A8)")
_pending = MANUAL_REVIEW_PENDING_COLS + AWAITING_CLINICAL_CLARIFICATION_COLS
_pending_in = [c for c in _pending if c in df.columns]
if _pending_in:
    _pending_unit = "variable" if len(_pending_in) == 1 else "variables"
    print(f"  Pending clinical review        : {len(_pending_in)} {_pending_unit} (see A5)")
print()

print("SELECTED HARD EXCLUSIONS (not exhaustive -- see A5 for the complete")
print("non-modeling breakdown, including source/audit, ID, cohort-control, and")
print("clinically nonspecific groups):")
_n_excl = len(LEAKAGE_EXCLUDE_COLS) + len(INTRAPARTUM_OR_POST_DELIVERY_EXCLUDE_COLS)
print(f"  leakage + intrapartum/post-delivery = {_n_excl} columns")
print()
print("NEXT STEP: 02b_eda_a_initial_predictor_readiness.ipynb")
print("  That notebook performs: predictor-vs-target association testing, deep missingness")
print("  analysis, numeric/categorical predictor-predictor correlation and association")
print("  screening, redundancy analysis, deep outlier review, and variable-readiness")
print("  scoring for predictor candidates.")
print("=" * 70)
""")


# ── Automated Dataset Profiling Reports (supplementary only) ──────────────────
# Placed immediately after A5 (predictor pool/exclusion rationale is defined),
# before A6. Deliberately unnumbered (not "A5b"/"A6") to avoid a renumbering
# cascade through every existing "see A6"/"see A7" cross-reference in this
# notebook -- this is a supplementary, non-canonical addition, not a new
# numbered analysis section.
SA_PROFILING_HEADER = md("eda-a-s07c-profiling-header", """
## Supplementary Automated Profiling

Supplementary automated dataset profiling reports are available for internal
review but were not part of the primary analysis presented in this notebook
and are disabled by default. When enabled, they cover the full dataset and
the `predictor_allowed` variable set separately, and are configured to omit
row-level sample values. They are not a substitute for the manual EDA in
this notebook.
""")

SA_PROFILING_CODE = code("eda-a-s07c-profiling-code", """
# Opt-in gate: both flags required before any library import, output
# directory creation, or file write. Disabled by default.
if not (RUN_AUTOMATED_PROFILING and SAVE_AGGREGATED_OUTPUTS):
    print("Supplementary automated profiling was not run for this analysis "
          "(disabled by default; not part of the primary analysis).")
else:
    try:
        from ydata_profiling import ProfileReport
        _YDATA_AVAILABLE = True
    except ImportError:
        _YDATA_AVAILABLE = False
        print("Automated profiling library not available; supplementary reports were not generated.")

    _PROFILING_OUT_DIR = (_root / "outputs/manual_review/eda_a_profiling") if _root else Path.cwd() / "eda_a_profiling"
    _PROFILING_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Scopes ──────────────────────────────────────────────────────────────
    # Column counts are derived from the current variable-type/classification
    # files loaded in Part 1, not hardcoded.
    assert df.shape[1] == len(classification_df), (
        f"Expected {len(classification_df)} columns in the processed dataset "
        f"(from the current classification file); found {df.shape[1]}."
    )
    assert len(PREDICTOR_ALLOWED_COLS) > 0, "predictor_allowed classification is empty."
    _pac_missing_from_df = [c for c in PREDICTOR_ALLOWED_COLS if c not in df.columns]
    assert not _pac_missing_from_df, (
        f"predictor_allowed column(s) not found in the dataset: {_pac_missing_from_df}"
    )
    print(f"  Initial predictor pool (predictor_allowed): {len(PREDICTOR_ALLOWED_COLS)} columns")
    _profile_predictor_cols = list(PREDICTOR_ALLOWED_COLS)

    # ── Dataset-profiling allowlist (distinct from model-predictor eligibility) ──
    # A column is admitted only if its type is aggregate-summarizable AND (for
    # structural-registry members) its applicable subgroup meets the
    # disclosure threshold. Default-deny: any future column type not already
    # recognized here is excluded rather than silently profiled in detail.
    _PROFILING_ALLOWED_TYPES = {"binary", "categorical", "ordinal", "continuous", "count"}
    _MIN_SUBGROUP_DISCLOSURE_N = 5  # project's established small-cell convention
    _confirmed_structural = structural_missingness_registry.CONFIRMED_STRUCTURAL
    _disallowed_rare_detail = sorted(
        v for v, meta in _confirmed_structural.items()
        if meta["expected_applicable_denominator"] < _MIN_SUBGROUP_DISCLOSURE_N
    )
    _PROFILING_ALLOWED_COLS = sorted(
        c for c in df.columns
        if VARIABLE_TYPE_MAP.get(c) in _PROFILING_ALLOWED_TYPES
        and c not in _disallowed_rare_detail
    )

    _profiling_status = []

    def _report_path(name):
        return _PROFILING_OUT_DIR / name

    def _status(tool, scope, path, ok, note=""):
        _profiling_status.append({"tool": tool, "scope": scope, "path": str(path), "success": ok, "note": note})

    # ── ydata-profiling ────────────────────────────────────────────────────
    if _YDATA_AVAILABLE:
        print("Generating supplementary profiling reports...")

        def _make_ydata_report(data, title, minimal):
            _r = ProfileReport(data, title=title, minimal=minimal, explorative=not minimal)
            # Suppresses the dataframe-level sample tab (head/tail/random rows)
            # and duplicate-row preview. This does NOT suppress a separate
            # per-variable widget that ydata-profiling renders for categorical
            # columns showing that column's raw first 1st-5th row values --
            # that widget is removed by post-generation redaction below.
            # vars.cat.n_obs/vars.bool.n_obs are deliberately left at their
            # library defaults: they do not control the row-level widget, only
            # a separate, legitimate compact top-categories preview table.
            _r.config.samples.head = 0
            _r.config.samples.tail = 0
            _r.config.samples.random = 0
            _r.config.duplicates.head = 0
            return _r

        # The per-variable row-sample widget has no dedicated suppression flag
        # in the installed ydata-profiling version; the only available flag
        # (`vars.cat.redact`) also blanks legitimate frequency-table category
        # labels, which is not acceptable. Instead, the widget's HTML fragment
        # is stripped post-generation and the result is verified before it is
        # treated as final (see _generate_ydata_report_safely below).
        import os as _os
        import re as _re
        _YDATA_SAMPLE_WIDGET_RE = _re.compile(
            r'<div class=col-sm-3><div class=table-responsive>'
            r'<p class="h4 item-header">Sample<table[^>]*>.*?</table></div></div>',
            _re.DOTALL,
        )
        # Literal ordinal row labels unique to this widget (no other
        # ydata-profiling template emits "1st row"/"2nd row"/etc.) -- used as
        # a fail-loud invariant check independent of the redaction pattern
        # itself, so a future ydata-profiling HTML structure change cannot
        # silently pass through an unredacted report.
        _ROW_ORDINAL_MARKERS = ("1st row", "2nd row", "3rd row", "4th row", "5th row")

        def _generate_ydata_report_safely(data, title, minimal, final_path):
            \"\"\"Generate to a temporary file, redact, validate, then atomically
            replace final_path only if the report is verified free of
            row-level sample widgets. On any failure, the temporary file is
            removed and any previously validated final_path is left intact.\"\"\"
            _tmp_path = final_path.with_name(final_path.stem + ".raw.tmp" + final_path.suffix)
            try:
                _make_ydata_report(data, title, minimal).to_file(_tmp_path)
                _html = _tmp_path.read_text(encoding="utf-8")
                _n_before = len(_YDATA_SAMPLE_WIDGET_RE.findall(_html))
                _redacted_html, _n_removed = _YDATA_SAMPLE_WIDGET_RE.subn("", _html)
                _n_remaining = sum(_redacted_html.count(_m) for _m in _ROW_ORDINAL_MARKERS)
                if _n_remaining:
                    raise RuntimeError(
                        f"YData privacy redaction FAILED for {final_path.name}: "
                        f"{_n_remaining} row-level ordinal-sample marker(s) (e.g. '1st row') "
                        f"remain after redaction ({_n_before} widget(s) detected, {_n_removed} "
                        f"removed by the known pattern). ydata-profiling's rendered HTML "
                        f"structure may have changed since this redaction pattern was verified "
                        f"-- this report requires manual privacy review and must not be treated "
                        f"as safe or copied to any review location."
                    )
                _tmp_path.write_text(_redacted_html, encoding="utf-8")
                _os.replace(_tmp_path, final_path)  # atomic on the same filesystem
                return _n_before, _n_removed
            except Exception:
                if _tmp_path.exists():
                    _tmp_path.unlink()
                raise

        try:
            # Allowlist-admitted columns only -- minimal=True: with up to 156
            # columns, full pairwise interactions/correlations would be
            # expensive and are not needed for a structural overview.
            _ydata_full_input = df[_PROFILING_ALLOWED_COLS].copy()
            _p = _report_path("EDA_A_YData_Full_Dataset.html")
            _n_before, _n_removed = _generate_ydata_report_safely(
                _ydata_full_input, "EDA A -- Broad Structural Profile (Automated Profiling, Supplementary) -- INTERNAL ONLY",
                minimal=True, final_path=_p,
            )
            _status("ydata-profiling", "full dataset", _p, True,
                    note=f"verified safe: {_n_before} row-sample widget(s) detected, "
                         f"{_n_removed} removed, 0 remaining")
        except Exception as _exc:
            _status("ydata-profiling", "full dataset", _report_path("EDA_A_YData_Full_Dataset.html"), False, str(_exc))

        try:
            # Predictor pool: small enough for the full (non-minimal) report.
            _p = _report_path("EDA_A_YData_Predictor_Pool.html")
            _n_before, _n_removed = _generate_ydata_report_safely(
                df[_profile_predictor_cols].copy(),
                "EDA A -- Restricted Predictor Profile: predictor_allowed (Automated Profiling, Supplementary) -- INTERNAL ONLY",
                minimal=False, final_path=_p,
            )
            _status("ydata-profiling", "predictor pool", _p, True,
                    note=f"verified safe: {_n_before} row-sample widget(s) detected, "
                         f"{_n_removed} removed, 0 remaining")
        except Exception as _exc:
            _status("ydata-profiling", "predictor pool", _report_path("EDA_A_YData_Predictor_Pool.html"), False, str(_exc))
    else:
        _status("ydata-profiling", "full dataset", _report_path("EDA_A_YData_Full_Dataset.html"), False, "library not installed")
        _status("ydata-profiling", "predictor pool", _report_path("EDA_A_YData_Predictor_Pool.html"), False, "library not installed")

    print("\\nSupplementary automated profiling summary:")
    for _s in _profiling_status:
        _label = "generated" if _s["success"] else "not generated"
        print(f"  {_s['scope']}: {_label}")
""")


# ── Collect Part 2 cells ──────────────────────────────────────────────────────
# Methodological order: A5=predictor pool/exclusion rationale
# (formerly A7), A6=univariate descriptive overview (unchanged position),
# A7=missingness overview (formerly A5), A8-A10 unchanged position.
EDA_A_PART2_CELLS = [
    SA7_HEADER, SA7_RECONCILIATION_HEADER, SA7_RECONCILIATION,
    SA7_EXCLUSIONS, SA7_KEY_OBS, SA7_KEY_OBS_CODE,
    SA_PROFILING_HEADER, SA_PROFILING_CODE,
    SA6_HEADER, SA6_TABLE1, SA6_KEY_OBS, SA6_KEY_OBS_CODE,
    SA5_HEADER, SA5_MISS_TABLE, SA5_MISS_HEATMAP, SA5_KEY_OBS, SA5_KEY_OBS_CODE,
    SA_OUTLIERS_HEADER, SA_OUTLIERS, SA_OUTLIERS_KEY_OBS, SA_OUTLIERS_KEY_OBS_CODE,
    SA_REGISTRY_HEADER, SA_REGISTRY,
    SA_SUMMARY_HEADER, SA_SUMMARY,
]

if __name__ == "__main__":
    print(f"EDA A Part 2 cells defined: {len(EDA_A_PART2_CELLS)}")

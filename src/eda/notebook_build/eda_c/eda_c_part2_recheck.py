#!/usr/bin/env python3
"""EDA C — Part 2 cell definitions (sections C4–C7, plus C4b).

Targeted recheck of the approved predictor set on the final corrected dataset.
Does not repeat A2 analysis — verifies that A2 findings still hold.

C4  — Descriptive summary table (Table 1 style, by target and domain)
C4b — Distribution plots (numeric histograms/boxplots, binary/categorical bar
      charts, by target), grouped by domain and saved to outputs/eda_c/figures/.
      Diagnostic only -- closes the visual-parity gap with EDA A2 (folder
      `a2_predictor_readiness`, renamed 2026-08-24 from `eda_b`; Sections
      A2.3-A2.6, renumbered from B6-B9 in the 2026-08-08 EDA A/A2 reorg).
      No cleaning, imputation, or row/column changes.
C5  — Missingness recheck (per variable + row-level + imputation recommendation)
C6  — Sparsity and separation gate (binary/categorical)
C7  — Outlier recheck (numeric variables only)
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


# ── Section C4 ─────────────────────────────────────────────────────────────────
SC4_HEADER = md("eda-c-s04-header", """
## Section C4 — Descriptive Summary Table (Table 1)

Table 1–style, target-stratified description of the **baseline staged analysis
universe (pre-screen)** — every current `ANALYSIS_VARS` member — split by
`target_intrapartum_cs` (0 = vaginal delivery, 1 = intrapartum CS).

**This is descriptive repeated EDA. No variable is selected or excluded here.**
C4 runs *before* the C12 target-independent hard eligibility screen, so the
baseline universe still contains variables that C12 may later hard-exclude
(including zero-variance variables such as `alcohol` / `HELLP` / `eclampsia` /
`IUFD`). No p-value, no FDR, no ranking, no causal interpretation of
between-group differences, and no eligibility decision is produced in C4.

**Type-specific summaries** (variable type from the authoritative C2
variable-type contract — `infer_var_type` → `VARIABLE_TYPE_MAP`; never
dtype-guessed for a B-stage variable):

| type | table | summary |
|---|---|---|
| numeric | `numeric_descriptive_df` | overall mean / SD / median / Q1 / Q3 / IQR / min / max + per-target median [Q1, Q3] |
| binary | `binary_descriptive_df` | positive n / **non-missing denominator** / % , per target group; observed values must be ⊆ {0, 1} or C4 fails loud |
| multi-level categorical | `categorical_descriptive_df` | **long format, one row per variable × observed category**, ALL levels — never reduced to category `1` |

A concise one-row-per-variable overview is `descriptive_variable_overview_df`
(also kept under the name `descriptive_df`).

**Percentage denominators.** Percentages for binary and categorical levels are
calculated **among non-missing observations for that variable within the
relevant target group** — never the full target-group size. Missingness is
reported separately (basic variable-level only; the full structural /
applicability-aware missingness analysis stays in C5 / C5b).

Each table also carries `earliest_entry_stage` and the cumulative
`available_prediction_horizons` (reused from C3/C3b, not rebuilt here):
stage 1 → `Stage 1; Stage 2; Stage 3`, stage 2 → `Stage 2; Stage 3`,
stage 3 → `Stage 3`. Variables are grouped by clinical domain
(`DOMAIN_MAP`).
""")

SC4_DESCRIPTIVE = code("eda-c-s04-descriptive", """
TYPE_INFERENCE_WARNINGS = []


def _legacy_infer_var_type(series, binary_threshold=3, category_threshold=20):
    observed = series.dropna()
    if observed.empty:
        return "empty"
    values = set(observed.unique())
    if observed.nunique() <= binary_threshold and values.issubset({0, 1, 0.0, 1.0}):
        return "binary"
    if pd.api.types.is_numeric_dtype(series) and observed.nunique() > category_threshold:
        return "numeric"
    return "categorical"


def _record_type_warning(message):
    if message not in TYPE_INFERENCE_WARNINGS:
        TYPE_INFERENCE_WARNINGS.append(message)
        print(f"TYPE WARNING: {message}")


def _derived_expected_type_to_eda_type(expected_type):
    text = str(expected_type or "").lower()
    if "binary" in text:
        return "binary"
    if "categorical" in text:
        return "categorical"
    if "numeric" in text or "count" in text or "integer" in text:
        return "numeric"
    return None


def infer_var_type(series, binary_threshold=3, category_threshold=20):
    col = getattr(series, "name", None)
    if col in VARIABLE_TYPE_MAP:
        schema_type = VARIABLE_TYPE_MAP[col]
        return SCHEMA_TO_EDA_TYPE.get(schema_type, "categorical")
    if isinstance(col, str) and col.endswith("__missing_ind"):
        return "binary"
    if "derived_meta" in globals() and col in derived_meta:
        derived_type = _derived_expected_type_to_eda_type(derived_meta[col].get("expected_type"))
        if derived_type is not None:
            return derived_type
    # 2026-08-31 C2 correction (variable-type contract): a variable present at
    # the Data Cleaning B handoff (i.e. in ANALYSIS_VARS) with no authoritative
    # type-schema entry is a METADATA INTEGRITY problem -- EDA C must NOT
    # silently dtype/unique-count guess a B-stage type. Fail loud. The legacy
    # inference path below survives ONLY for genuinely C-created derived
    # features whose type EDA C registers in derived_meta (handled above).
    if isinstance(col, str) and "ANALYSIS_VARS" in globals() and col in ANALYSIS_VARS:
        raise RuntimeError(
            f"VARIABLE TYPE CONTRACT FAILED: {col!r} is in ANALYSIS_VARS but has no "
            "Data Cleaning B type-schema entry (VARIABLE_TYPE_MAP) and no registered "
            "derived_meta type. EDA C does not dtype-guess a B-stage variable's type "
            "-- fix the Data Cleaning B type-schema snapshot."
        )
    if col:
        _record_type_warning(
            f"{col}: variable type schema/derived metadata entry not found; used legacy dtype/unique-count inference."
        )
    else:
        _record_type_warning("Unnamed series: used legacy dtype/unique-count inference.")
    return _legacy_infer_var_type(
        series,
        binary_threshold=binary_threshold,
        category_threshold=category_threshold,
    )


# ── Type-correct Table-1 descriptives ────────────────────────────────────────
# PRE-SCREEN, descriptive only. THREE separate type-specific tables. Binary and
# multi-level categorical variables are NEVER routed through the same (s == 1)
# formatter -- a genuine categorical predictor keeps ALL its observed levels.
# Types come from the authoritative C2 variable-type contract (infer_var_type ->
# VARIABLE_TYPE_MAP); no dtype guessing for a B-stage variable. No statistical
# test, no p-value, no FDR, no ranking, no eligibility change.

_HORIZON_DISPLAY_C4 = {1: "Stage 1; Stage 2; Stage 3", 2: "Stage 2; Stage 3", 3: "Stage 3"}


def _c4_horizons(_col):
    # cumulative semantics reused from C3/C3b; stage membership NOT rebuilt here
    return _HORIZON_DISPLAY_C4.get(EARLIEST_ENTRY_STAGE.get(_col), "--")


_N0 = int((df_analysis[TARGET_COL] == 0).sum())
_N1 = int((df_analysis[TARGET_COL] == 1).sum())
_C4_BINARY_CONTRACT = {0, 1}

_numeric_rows, _binary_rows, _categorical_rows, _overview_rows = [], [], [], []
_c4_recon_errors = []

for col in ANALYSIS_VARS:
    var_type = infer_var_type(df_analysis[col])
    if var_type not in ("numeric", "binary", "categorical"):
        raise RuntimeError(
            "C4: ANALYSIS_VARS member {!r} resolved to descriptive type {!r}; C4 "
            "summarises only numeric / binary / categorical staged predictors -- "
            "fix the Data Cleaning B type-schema snapshot.".format(col, var_type)
        )
    domain = DOMAIN_MAP.get(col, "unknown")
    timing = TIMING_MAP.get(col, "unknown")
    stage = EARLIEST_ENTRY_STAGE.get(col)
    horizons = _c4_horizons(col)

    _s_all = df_analysis[col]
    _obs_all = _s_all.dropna()
    n_all = int(_obs_all.shape[0])
    n_miss = int(_s_all.isna().sum())
    miss_pct = round(_s_all.isna().mean() * 100, 1)
    _obs0 = df_analysis.loc[df_analysis[TARGET_COL] == 0, col].dropna()
    _obs1 = df_analysis.loc[df_analysis[TARGET_COL] == 1, col].dropna()
    n0 = int(_obs0.shape[0])
    n1 = int(_obs1.shape[0])

    _overview_rows.append({
        "variable": col, "type": var_type, "domain": domain, "timing": timing,
        "earliest_entry_stage": stage if stage is not None else "",
        "available_prediction_horizons": horizons,
        "N_available": n_all, "missing_n": n_miss, "missing_%": miss_pct,
        "n_unique": int(_obs_all.nunique()),
    })

    if var_type == "numeric":
        def _miqr(s):
            if not len(s):
                return "—"
            return "{:.2f} [{:.2f}, {:.2f}]".format(
                float(s.median()), float(s.quantile(0.25)), float(s.quantile(0.75)))
        _q1 = float(_obs_all.quantile(0.25)) if n_all else None
        _q3 = float(_obs_all.quantile(0.75)) if n_all else None
        _numeric_rows.append({
            "variable": col, "domain": domain,
            "earliest_entry_stage": stage if stage is not None else "",
            "available_prediction_horizons": horizons,
            "N_nonmissing": n_all, "missing_n": n_miss, "missing_%": miss_pct,
            "mean": round(float(_obs_all.mean()), 3) if n_all else None,
            "SD": round(float(_obs_all.std()), 3) if n_all else None,
            "median": round(float(_obs_all.median()), 3) if n_all else None,
            "Q1": round(_q1, 3) if _q1 is not None else None,
            "Q3": round(_q3, 3) if _q3 is not None else None,
            "IQR": round(_q3 - _q1, 3) if _q1 is not None else None,
            "min": round(float(_obs_all.min()), 3) if n_all else None,
            "max": round(float(_obs_all.max()), 3) if n_all else None,
            "target0_N_nonmissing": n0, "target0_median_Q1_Q3": _miqr(_obs0),
            "target1_N_nonmissing": n1, "target1_median_Q1_Q3": _miqr(_obs1),
        })

    elif var_type == "binary":
        _observed = _obs_all.unique().tolist()
        _codes = set()
        for _v in _observed:
            try:
                _codes.add(int(_v))
            except (TypeError, ValueError):
                _codes.add(_v)
        if not _codes.issubset(_C4_BINARY_CONTRACT):
            raise RuntimeError(
                "C4: binary variable {!r} has observed non-missing value(s) {} "
                "outside the current 0/1 binary contract -- refusing to silently "
                "treat another code as the positive category. Fix Data Cleaning B "
                "or the type-schema snapshot.".format(col, sorted(map(str, _observed)))
            )

        def _pos(s):
            return int((pd.to_numeric(s, errors="coerce") == 1).sum())
        _p_all, _p0, _p1 = _pos(_obs_all), _pos(_obs0), _pos(_obs1)
        _binary_rows.append({
            "variable": col, "domain": domain,
            "earliest_entry_stage": stage if stage is not None else "",
            "available_prediction_horizons": horizons,
            "N_nonmissing": n_all, "missing_n": n_miss, "missing_%": miss_pct,
            "positive_n": _p_all, "positive_denominator_nonmissing": n_all,
            "positive_pct_of_nonmissing": round(_p_all / n_all * 100, 1) if n_all else None,
            "target0_denominator_nonmissing": n0, "target0_positive_n": _p0,
            "target0_positive_pct": round(_p0 / n0 * 100, 1) if n0 else None,
            "target1_denominator_nonmissing": n1, "target1_positive_n": _p1,
            "target1_positive_pct": round(_p1 / n1 * 100, 1) if n1 else None,
            "zero_variance_descriptive_flag": bool(_obs_all.nunique() <= 1),
        })

    else:  # multi-level categorical -- ALL observed levels, long format
        _levels = sorted(_obs_all.unique().tolist(), key=lambda x: str(x))
        _vc_all, _vc0, _vc1 = _obs_all.value_counts(), _obs0.value_counts(), _obs1.value_counts()
        _seen, _sum_all, _sum0, _sum1 = [], 0, 0, 0
        for _lev in _levels:
            _c_all = int(_vc_all.get(_lev, 0))
            _c0 = int(_vc0.get(_lev, 0))
            _c1 = int(_vc1.get(_lev, 0))
            _sum_all += _c_all; _sum0 += _c0; _sum1 += _c1
            _seen.append(_lev)
            _categorical_rows.append({
                "variable": col, "domain": domain,
                "earliest_entry_stage": stage if stage is not None else "",
                "available_prediction_horizons": horizons,
                "category_value": _lev,
                "variable_N_nonmissing": n_all,
                "overall_category_n": _c_all,
                "overall_category_pct_of_nonmissing": round(_c_all / n_all * 100, 1) if n_all else None,
                "target0_denominator_nonmissing": n0, "target0_category_n": _c0,
                "target0_category_pct": round(_c0 / n0 * 100, 1) if n0 else None,
                "target1_denominator_nonmissing": n1, "target1_category_n": _c1,
                "target1_category_pct": round(_c1 / n1 * 100, 1) if n1 else None,
                "missing_n": n_miss, "missing_%": miss_pct,
            })
        # ── category reconciliation: counts must sum to the non-missing denominator
        if _sum_all != n_all:
            _c4_recon_errors.append(
                "{}: overall category counts sum to {} != non-missing N {}".format(col, _sum_all, n_all))
        if _sum0 != n0:
            _c4_recon_errors.append(
                "{}: target-0 category counts sum to {} != target-0 non-missing N {}".format(col, _sum0, n0))
        if _sum1 != n1:
            _c4_recon_errors.append(
                "{}: target-1 category counts sum to {} != target-1 non-missing N {}".format(col, _sum1, n1))
        if len(_seen) != len(set(map(str, _seen))):
            _c4_recon_errors.append("{}: a category value appears more than once in the summary".format(col))

if _c4_recon_errors:
    raise RuntimeError("C4 categorical reconciliation FAILED: " + "; ".join(_c4_recon_errors))

numeric_descriptive_df = (
    pd.DataFrame(_numeric_rows).sort_values(["domain", "variable"]).reset_index(drop=True)
    if _numeric_rows else pd.DataFrame()
)
binary_descriptive_df = (
    pd.DataFrame(_binary_rows).sort_values(["domain", "variable"]).reset_index(drop=True)
    if _binary_rows else pd.DataFrame()
)
categorical_descriptive_df = (
    pd.DataFrame(_categorical_rows).sort_values(["domain", "variable"], kind="stable").reset_index(drop=True)
    if _categorical_rows else pd.DataFrame()
)
descriptive_variable_overview_df = (
    pd.DataFrame(_overview_rows).sort_values(["domain", "variable"]).reset_index(drop=True)
)
# Backward-compatible name: no downstream cell consumes the old wide/sparse
# frame (verified) -- `descriptive_df` is kept as the concise per-variable
# overview so any external reference still resolves to a sensible object.
descriptive_df = descriptive_variable_overview_df

# every categorical ANALYSIS_VAR must appear with EXACTLY its observed level set
_cat_vars_expected = [c for c in ANALYSIS_VARS if infer_var_type(df_analysis[c]) == "categorical"]
for _cv in _cat_vars_expected:
    _obs_levels = set(map(str, df_analysis[_cv].dropna().unique().tolist()))
    _rep_levels = set(map(str, categorical_descriptive_df.loc[
        categorical_descriptive_df["variable"] == _cv, "category_value"].tolist()))
    if _obs_levels != _rep_levels:
        raise RuntimeError(
            "C4: categorical variable {!r} observed levels {} != represented "
            "levels {}".format(_cv, sorted(_obs_levels), sorted(_rep_levels))
        )

print("=" * 70)
print("C4 -- TABLE-1 DESCRIPTIVES (pre-screen baseline staged analysis universe;")
print("      descriptive only -- no variable is selected or excluded here)")
print("=" * 70)
print("Cohort: N={} | target_intrapartum_cs=0 (vaginal) N={} | =1 (intrapartum CS) N={}".format(
    len(df_analysis), _N0, _N1))
print("Baseline staged analysis universe: {} predictors "
      "({} numeric, {} binary, {} multi-level categorical).".format(
          len(ANALYSIS_VARS), len(numeric_descriptive_df), len(binary_descriptive_df),
          len(_cat_vars_expected)))
print("Denominator: binary/categorical percentages are among NON-MISSING observations")
print("for that variable within the relevant target group; missingness reported separately.")
print()

print("--- NUMERIC (overall stats + per-target median [Q1, Q3]) ---")
print(numeric_descriptive_df.to_string(index=False) if len(numeric_descriptive_df) else "(none)")
print()
print("--- BINARY (positive n / non-missing denominator / %) ---")
print(binary_descriptive_df.to_string(index=False) if len(binary_descriptive_df) else "(none)")
print()
print("--- MULTI-LEVEL CATEGORICAL (long format: one row per variable x observed category; ALL levels) ---")
if len(categorical_descriptive_df):
    _CAT_PRINT_CAP = 40
    if len(categorical_descriptive_df) > _CAT_PRINT_CAP:
        print("(printed view SHORTENED to the first {} of {} rows; the complete analytical "
              "table is categorical_descriptive_df in memory)".format(
                  _CAT_PRINT_CAP, len(categorical_descriptive_df)))
        print(categorical_descriptive_df.head(_CAT_PRINT_CAP).to_string(index=False))
    else:
        print(categorical_descriptive_df.to_string(index=False))
else:
    print("(none)")
print()

print("C4 reconciliation PASSED: for every categorical variable the category counts sum to "
      "the non-missing denominator overall and within target 0 and target 1, and every "
      "observed category is represented exactly once.")
if TYPE_INFERENCE_WARNINGS:
    print("Type-inference legacy-path warnings this run: {}".format(len(TYPE_INFERENCE_WARNINGS)))
print("No statistical test, p-value, FDR, ranking, or eligibility decision is produced in C4. "
      "Target-independent hard eligibility screening is C12; final eligible pool is decided there.")
""")


# ── Section C4b ────────────────────────────────────────────────────────────────
SC4B_HEADER = md("eda-c-s04b-header", """
## Section C4b — Distribution Plots (Repeated EDA, Baseline Staged Analysis Universe)

Visual repeated-EDA check for every member of the **baseline staged analysis
universe (pre-screen)** — the current `ANALYSIS_VARS` — matching the level of
visual detail EDA A2 (folder `a2_predictor_readiness`, renamed 2026-08-24 from
`eda_b`; Sections A2.3–A2.6, renumbered from B6–B9 in the 2026-08-08 EDA A/A2
reorg) applied before cleaning — now applied to the cleaned Batch 19 dataset.
This is descriptive repeated EDA: **no variable is selected, excluded, or
reclassified here, and final eligibility is decided later in C12.**

- **Numeric — continuous measurements:** histogram + KDE + boxplot by target.
- **Numeric — discrete integer counts** (obstetric counts such as `G` / `P` /
  `LIVE_BIRTH` / `AB` / `CS` where every observed value is a whole number and
  the observed range is small): **integer-aligned histogram bins, no KDE** —
  a continuous-support density curve between integer values would imply false
  granularity. This reuses A2's `_is_discrete_count` convention; it is a
  plotting-subtype distinction only and never redefines the variable's type.
- **Binary / categorical:** aggregate level-count bar chart + target-stratified
  rate bar chart.

**Small-cell disclosure protection (presentation layer only).** The saved
figures reuse the project-wide share-safe convention (`eda_shared/share_safe.py`,
threshold n<5, the same `SHARE_SAFE_MODE` flag A2 uses). A protected small
target-by-level cell (or a per-variable count with a small complement) is
rendered as an **absent bar with an italic "Suppressed" annotation** — never a
zero-height bar, so a suppressed value is visually distinct from a genuine 0%;
exact protected counts are never printed in a title or annotation; a category
label whose every target side is suppressed is shown as `[suppressed]`. This
masks the **drawn surface only** — every underlying count, proportion, and
DataFrame keeps its true value and no downstream calculation is affected.

Grouped by clinical domain (`DOMAIN_MAP`; `unknown` fallback, same as C4). One
figure per domain group is saved under `outputs/eda_c/figures/` — an
EDA-C-scoped, git-ignored location (aggregate plots only, no patient-level
rows in any file). Each variable's panel title carries its
`earliest_entry_stage` and cumulative `available_prediction_horizons`
(reused from C3/C3b, not rebuilt here).

**Plot-coverage accounting.** Every `ANALYSIS_VARS` member is reconciled in
`c4b_plot_coverage_df` (`variable`, `type`, `domain`, `earliest_entry_stage`,
`plot_status`, `reason`). An all-missing variable may be explicitly skipped
(documented). A genuine plotting-implementation failure for an analyzable
variable is reported and then **fails loud** — a canonical run cannot silently
claim full visual coverage while a variable failed to plot.

**Diagnostic only.** This section does not clean, impute, delete rows or
columns, or drop any variable. Skew is handled by C7's outlier recheck and
sparse levels by C6's sparsity gate; C4b only cross-references those. C6 is a
diagnostic section — it does not itself automatically resolve a sparse
predictor; final treatment of any flagged variable is reviewed separately.
""")

SC4B_PLOTS = code("eda-c-s04b-plots", """
from pathlib import Path as _PathC4b

_FIG_DIR = (_root / "outputs" / "eda_c" / "figures") if _root else _PathC4b("outputs/eda_c/figures")
if "notebooks" in _FIG_DIR.resolve().parts:
    raise RuntimeError(
        f"EDA C figures directory resolved under 'notebooks/' ({_FIG_DIR.resolve()}) -- "
        "this indicates a working-directory/path-anchoring bug. Refusing to write "
        "figures to a non-canonical location."
    )
_FIG_DIR.mkdir(parents=True, exist_ok=True)

_SS = bool(SHARE_SAFE_MODE) if "SHARE_SAFE_MODE" in dir() else True
_SS_THRESHOLD = share_safe.DEFAULT_DISCLOSURE_THRESHOLD

# Cumulative prediction-horizon display, reused from C3/C3b -- stage membership is NOT rebuilt here.
_HORIZON_DISPLAY_C4B = {1: "Stage 1; Stage 2; Stage 3", 2: "Stage 2; Stage 3", 3: "Stage 3"}


def _c4b_stage_label(_col):
    _st = EARLIEST_ENTRY_STAGE.get(_col)
    if _st is None:
        return "earliest entry stage --"
    return f"earliest entry stage {_st}  |  horizons: {_HORIZON_DISPLAY_C4B.get(_st, '--')}"


def _safe_stem(name):
    return "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in str(name))


def _c4b_is_discrete_count(s, max_range=15):
    # Port of a2_predictor_readiness._is_discrete_count: every non-missing value
    # is a whole number AND the observed range is small enough for per-integer
    # bins to stay readable (obstetric counts), as opposed to a wide-range
    # integer-valued measurement (AGE, diagnosis_year). Plotting-subtype only --
    # the variable's authoritative type is unchanged.
    s2 = s.dropna()
    if s2.empty:
        return False
    if not np.all(np.mod(s2.astype(float), 1) == 0):
        return False
    return (float(s2.max()) - float(s2.min())) <= max_range


def _c4b_annotate_suppressed(_ax, _x, _y, _rot=0):
    _ax.text(_x, _y, "Suppressed", ha="center", va="center", fontsize=7.5,
             fontstyle="italic", color="firebrick", rotation=_rot,
             bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))


# Group ANALYSIS_VARS by domain (DOMAIN_MAP), same "unknown" fallback as C4.
_domain_groups = {}
for _col in ANALYSIS_VARS:
    _dom = DOMAIN_MAP.get(_col, "unknown")
    _domain_groups.setdefault(_dom, []).append(_col)

print("=" * 70)
print("C4b -- DISTRIBUTION PLOTS (diagnostic only -- no data changes)")
print("=" * 70)
print(f"Plotting {len(ANALYSIS_VARS)} baseline staged-analysis-universe variables "
      f"across {len(_domain_groups)} domain groups")
print(f"Figures saved to: {_FIG_DIR.resolve()}")
print(f"Share-safe figure rendering: {_SS} (small-cell threshold n<{_SS_THRESHOLD}; "
      "presentation layer only -- analytical values unaffected)")
print()

_saved_figures = []
_plot_notes = []
_c4b_coverage_rows = []

for _dom, _cols in sorted(_domain_groups.items()):
    _n = len(_cols)
    _fig, _axes = plt.subplots(_n, 2, figsize=(10, 3.4 * _n), squeeze=False)
    for _i, _col in enumerate(_cols):
        _ax_left, _ax_right = _axes[_i, 0], _axes[_i, 1]
        _vtype = infer_var_type(df_analysis[_col])
        _stage = EARLIEST_ENTRY_STAGE.get(_col)
        _cov = {
            "variable": _col, "type": _vtype, "domain": _dom,
            "earliest_entry_stage": _stage if _stage is not None else "",
            "plot_status": "plotted", "reason": "",
        }
        _data = df_analysis[[_col, TARGET_COL]].dropna()
        _n_miss = int(df_analysis[_col].isna().sum())
        _n_obs = int(_data.shape[0])
        if _data.empty:
            _ax_left.set_visible(False)
            _ax_right.set_visible(False)
            _cov["plot_status"] = "skipped_all_missing"
            _cov["reason"] = "variable is 100% missing in the cleaned analysis universe"
            _c4b_coverage_rows.append(_cov)
            _plot_notes.append(f"{_col}: all missing -- skipped (documented in c4b_plot_coverage_df)")
            continue
        try:
            if _vtype == "numeric":
                _discrete = _c4b_is_discrete_count(df_analysis[_col])
                if _discrete:
                    _lo, _hi = int(_data[_col].min()), int(_data[_col].max())
                    _bins = np.arange(_lo - 0.5, _hi + 1.5, 1)
                    for _tv, _clr, _lab in [(0, _C0, "Vaginal"), (1, _C1, "Intra-CS")]:
                        _vals = _data.loc[_data[TARGET_COL] == _tv, _col]
                        _ax_left.hist(_vals, bins=_bins, alpha=0.55, color=_clr,
                                      density=True, label=f"{_lab} (n={len(_vals)})")
                    _ax_left.set_xticks(range(_lo, _hi + 1))
                    _ax_left.set_ylabel("proportion")
                    _ax_left.legend(fontsize=8)
                else:
                    sns.histplot(
                        data=_data, x=_col, hue=TARGET_COL, stat="density", common_norm=False,
                        kde=True, element="step", ax=_ax_left, palette={0: _C0, 1: _C1},
                    )
                sns.boxplot(
                    data=_data, x=TARGET_COL, y=_col, hue=TARGET_COL, ax=_ax_right,
                    palette={0: _C0, 1: _C1}, legend=False,
                )
                _ax_right.set_xlabel("0=Vaginal  1=Intrapartum CS")
                _skew = float(df_analysis[_col].dropna().skew())
                _cov["reason"] = ("discrete integer count: integer-aligned bins, no KDE"
                                  if _discrete else "continuous: histogram + KDE")
                if abs(_skew) > 1.5:
                    _plot_notes.append(
                        f"{_col}: skewness={_skew:.2f} (already flagged in C7 outlier recheck)"
                    )
            else:
                # ---- LEFT: aggregate level-count bar, share-safe masked -------
                _vc = df_analysis[_col].value_counts().sort_index()
                _cohort_n = int(df_analysis[_col].notna().sum())
                _heights, _labels, _supp_idx = [], [], []
                for _k, (_lev, _cnt) in enumerate(_vc.items()):
                    _disp = share_safe.safe_count_with_complement(
                        int(_cnt), _cohort_n, threshold=_SS_THRESHOLD, enabled=_SS)
                    if isinstance(_disp, str):
                        _heights.append(np.nan)
                        _labels.append("[suppressed]")
                        _supp_idx.append(_k)
                    else:
                        _heights.append(int(_cnt))
                        _labels.append(str(_lev))
                _xs = list(range(len(_vc)))
                _ax_left.bar([x for x, h in zip(_xs, _heights) if not np.isnan(h)],
                             [h for h in _heights if not np.isnan(h)], color=_C0)
                _ymax = max([h for h in _heights if not np.isnan(h)], default=1)
                for _k in _supp_idx:
                    _c4b_annotate_suppressed(_ax_left, _k, _ymax * 0.5, _rot=90)
                _ax_left.set_xticks(_xs)
                _ax_left.set_xticklabels(_labels, fontsize=8)
                _ax_left.set_xlabel(_col)
                _ax_left.set_ylabel("count (small cells suppressed)")

                # ---- RIGHT: target-stratified rate, share-safe masked --------
                _sub = df_analysis[[_col, TARGET_COL]].dropna(subset=[_col])
                _g0n = int((_sub[TARGET_COL] == 0).sum())
                _g1n = int((_sub[TARGET_COL] == 1).sum())
                if _vtype == "binary":
                    _obs_codes = set()
                    for _v in _sub[_col].dropna().unique():
                        try:
                            _obs_codes.add(int(_v))
                        except (TypeError, ValueError):
                            _obs_codes.add(_v)
                    _pos0 = int((pd.to_numeric(_sub.loc[_sub[TARGET_COL] == 0, _col], errors="coerce") == 1).sum())
                    _pos1 = int((pd.to_numeric(_sub.loc[_sub[TARGET_COL] == 1, _col], errors="coerce") == 1).sum())
                    _d0, _d1 = share_safe.suppress_binary_target_display(
                        _pos0, _pos1, _g0n, _g1n, threshold=_SS_THRESHOLD, enabled=_SS)
                    _r0 = (round(_pos0 / _g0n * 100, 1) if (_g0n and not isinstance(_d0, str)) else np.nan)
                    _r1 = (round(_pos1 / _g1n * 100, 1) if (_g1n and not isinstance(_d1, str)) else np.nan)
                    _ax_right.bar([0, 1], [_r0, _r1], color=[_C0, _C1])
                    for _bx, _bv in zip([0, 1], [_r0, _r1]):
                        if np.isnan(_bv):
                            _c4b_annotate_suppressed(_ax_right, _bx, 5, _rot=90)
                    _ax_right.set_xticks([0, 1])
                    _ax_right.set_xticklabels(["Vaginal", "Intra-CS"], fontsize=9)
                    _ax_right.set_ylabel("positive rate (%)")
                    _ax_right.set_ylim(0, max(100, np.nanmax([_r0, _r1, 1]) * 1.15))
                else:
                    _levels = list(_sub[_col].value_counts().index[:8])
                    _ct = pd.crosstab(_sub[_col], _sub[TARGET_COL]).reindex(_levels).fillna(0)
                    _v0 = _ct.get(0, pd.Series(0, index=_ct.index))
                    _v1 = _ct.get(1, pd.Series(0, index=_ct.index))
                    _tot = (_v0 + _v1)
                    _p0, _p1, _lbls = [], [], []
                    for _lev in _levels:
                        _c0, _c1, _t = int(_v0.get(_lev, 0)), int(_v1.get(_lev, 0)), int(_tot.get(_lev, 0))
                        _pd0 = share_safe.safe_pct_with_denominator(_c0, _t, threshold=_SS_THRESHOLD, enabled=_SS)[0]
                        _pd1 = share_safe.safe_pct_with_denominator(_c1, _t, threshold=_SS_THRESHOLD, enabled=_SS)[0]
                        _p0.append(_pd0 if isinstance(_pd0, (int, float)) else np.nan)
                        _p1.append(_pd1 if isinstance(_pd1, (int, float)) else np.nan)
                        _both_supp = (not isinstance(_pd0, (int, float))) and (not isinstance(_pd1, (int, float)))
                        _lbls.append("[suppressed]" if _both_supp else str(_lev)[:24])
                    _yy = np.arange(len(_levels))
                    _hh = 0.38
                    _ax_right.barh(_yy + _hh / 2, _p0, _hh, color=_C0, label="Vaginal")
                    _ax_right.barh(_yy - _hh / 2, _p1, _hh, color=_C1, label="Intra-CS")
                    for _bi, (_a, _b) in enumerate(zip(_p0, _p1)):
                        if np.isnan(_a):
                            _c4b_annotate_suppressed(_ax_right, 2, _bi + _hh / 2)
                        if np.isnan(_b):
                            _c4b_annotate_suppressed(_ax_right, 2, _bi - _hh / 2)
                    _ax_right.set_yticks(list(_yy))
                    _ax_right.set_yticklabels(_lbls, fontsize=8)
                    _ax_right.set_xlabel("within-level % (small cells suppressed)")
                    _ax_right.legend(fontsize=8)
                _min_level_n = int(_vc.min()) if len(_vc) else 0
                _cov["reason"] = "binary/categorical: share-safe level-count + target-stratified rate"
                if _min_level_n < 5:
                    _plot_notes.append(
                        f"{_col}: a level has a small aggregate count (already flagged in C6 sparsity gate; "
                        "exact value suppressed here)"
                    )
        except Exception as _e:
            _ax_left.set_visible(False)
            _ax_right.set_visible(False)
            _cov["plot_status"] = "failed"
            _cov["reason"] = f"{type(_e).__name__}: {_e}"
            _c4b_coverage_rows.append(_cov)
            _plot_notes.append(f"{_col}: PLOTTING FAILED ({type(_e).__name__}: {_e})")
            continue
        # share-safe title -- no exact protected count in the title
        _n_obs_disp = share_safe.safe_count_with_complement(
            _n_obs, len(df_analysis), threshold=_SS_THRESHOLD, enabled=_SS)
        _n_miss_disp = share_safe.safe_count(_n_miss, threshold=_SS_THRESHOLD, enabled=_SS)
        _ax_left.set_title(
            f"{_col}  (N={_n_obs_disp}, missing={_n_miss_disp}, type={_vtype})\\n{_c4b_stage_label(_col)}",
            fontsize=8,
        )
        _c4b_coverage_rows.append(_cov)
    _fig.suptitle(f"Domain: {_dom}", fontsize=12, y=1.0)
    plt.tight_layout()
    _out_path = _FIG_DIR / f"domain_{_safe_stem(_dom)}_distributions.png"
    _fig.savefig(_out_path, dpi=110, bbox_inches="tight")
    _saved_figures.append(str(_out_path))
    plt.show()
    plt.close(_fig)
    print(f"  Saved: {_out_path}  ({_n} variables)")

# ── Plot-coverage reconciliation ──────────────────────────────────────────────
c4b_plot_coverage_df = pd.DataFrame(_c4b_coverage_rows)[
    ["variable", "type", "domain", "earliest_entry_stage", "plot_status", "reason"]
]
_expected_n = len(ANALYSIS_VARS)
_covered = set(c4b_plot_coverage_df["variable"])
_missing_from_coverage = sorted(set(ANALYSIS_VARS) - _covered)
_extra_in_coverage = sorted(_covered - set(ANALYSIS_VARS))
_n_plotted = int((c4b_plot_coverage_df["plot_status"] == "plotted").sum())
_n_all_missing = int((c4b_plot_coverage_df["plot_status"] == "skipped_all_missing").sum())
_n_failed = int((c4b_plot_coverage_df["plot_status"] == "failed").sum())

print()
print(f"Saved {len(_saved_figures)} domain-grouped figures to {_FIG_DIR.resolve()}")
print()
print("C4b PLOT-COVERAGE RECONCILIATION (vs ANALYSIS_VARS):")
print(f"  expected variable count            : {_expected_n}")
print(f"  successfully plotted               : {_n_plotted}")
print(f"  all-missing, explicitly skipped    : {_n_all_missing}")
print(f"  plotting failures                  : {_n_failed}")
if _missing_from_coverage:
    print(f"  NOT accounted for in coverage table: {_missing_from_coverage}")
if _extra_in_coverage:
    print(f"  coverage rows not in ANALYSIS_VARS : {_extra_in_coverage}")
if _n_failed:
    print()
    print("  Failed variables:")
    for _r in c4b_plot_coverage_df[c4b_plot_coverage_df["plot_status"] == "failed"].to_dict("records"):
        print(f"    - {_r['variable']} ({_r['type']}): {_r['reason']}")
if _plot_notes:
    print()
    print("Notes for manual review (informational only -- no automatic action taken):")
    for _note in _plot_notes:
        print(f"  - {_note}")

# A canonical run must not silently claim full visual coverage when an
# analyzable variable failed to plot, or when a variable is unaccounted for.
if _missing_from_coverage or _extra_in_coverage:
    raise RuntimeError(
        "C4b coverage reconciliation FAILED: coverage table does not match "
        f"ANALYSIS_VARS (missing={_missing_from_coverage}, extra={_extra_in_coverage})."
    )
if _n_failed:
    raise RuntimeError(
        f"C4b: {_n_failed} analyzable variable(s) failed to plot (see the list above). "
        "Refusing to let a canonical run report full visual coverage with unresolved "
        "plotting failures. An all-missing variable may be skipped; a plotting-"
        "implementation error must be fixed."
    )
print()
print(f"C4b coverage reconciled: {_n_plotted} plotted + {_n_all_missing} all-missing-skipped "
      f"= {_expected_n} ANALYSIS_VARS members; 0 unresolved failures.")
print("No rows, columns, or values were changed. No variable was dropped, reclassified, or "
      "made (in)eligible based on these plots. Share-safe suppression affects the rendered "
      "figure surface only.")
""")


# ── Section C4c ────────────────────────────────────────────────────────────────
SC4C_HEADER = md("eda-c-s04c-header", """
## Section C4c — Before-Versus-After Cleaning: Column Summary / Cleaning-Effect Comparison

**Purpose:** For columns Data Cleaning B actually changed (per its own audit
trail, `cleaning_b_column_actions.csv` — not re-derived here), show a
**column-level before-versus-after summary** so the cleaning effect is visible
rather than only described: `dtype`, missingness, distinct-value count, and the
recorded B action metadata, comparing the raw Batch 18 column against the
cleaned column reaching this notebook.

**This is a column summary / cleaning-effect comparison, not a row-level value
comparison.** No validated row-alignment contract between Batch 18 and Batch 19
is asserted here, so C4c deliberately does **not** attempt a per-row
old-value → new-value diff. (A genuine value-level comparison could be added
only if a canonical, validated Batch18→Batch19 row-alignment contract existed;
a fragile row-order-based join is not used just to satisfy older wording.)

**Canonical inputs only.** Both files are resolved from repository-root
canonical paths — the action log from the current Data Cleaning B audit
location (`outputs/data_cleaning/audit/`), Batch 18 from
`outputs/preprocessing/processed/` (used **only** as the pre-B comparison
source, never as EDA C's analytical input — EDA C's analytical input is the
SHA-verified Batch 19 from C3). There is **no** current-working-directory
alternate: if a canonical file is unavailable the section discloses that and
shows what it can, but never silently takes a same-named file from the CWD.

**Scope.** Restricted to changed columns that are in the current staged
analytical universe (`ANALYSIS_VARS`) **or** are a direct B source-column /
`redundant_with` counterpart of a registered representation that is itself in
`ANALYSIS_VARS`. This is an intentional restriction expressed through current
metadata — not the accidental `ANALYSIS_VARS ∪ df.columns` union (which, because
`df.columns` is the whole cleaned universe, made the `ANALYSIS_VARS` restriction
meaningless). C4c does not repeat the full Data Cleaning B report.
""")

SC4C_COMPARE = code("eda-c-s04c-compare", """
# ── B1: canonical repository-root paths ONLY -- no CWD alternate ───────────────
_actions_path = (
    (_root / CLEANED_AUDIT_SUBPATH / "cleaning_b_column_actions.csv")
    if _root is not None else None
)
_raw18_path = (
    (_root / PREPROC_PROCESSED_SUBPATH / "work_df_batch18.xlsx")
    if _root is not None else None
)

if _actions_path is None or not _actions_path.is_file():
    print("C4c: canonical Data Cleaning B action log "
          f"({_actions_path if _actions_path is not None else 'outputs/data_cleaning/audit/cleaning_b_column_actions.csv'}) "
          "is unavailable -- before/after column summary skipped. No CWD-local "
          "substitute is used.")
else:
    _actions_df = pd.read_csv(_actions_path)
    _changed_actions = _actions_df[_actions_df["action"].astype(str) != "none"].copy()
    print(f"Data Cleaning B column actions with a recorded change: {len(_changed_actions)} "
          f"(of {len(_actions_df)} audited columns)")
    print(_changed_actions["action"].value_counts().to_string())
    print()

    # ── B4: safe boolean parsing of CSV audit fields ─────────────────────────
    _BOOL_TRUE = {"true", "1", "yes", "y", "t"}
    _BOOL_FALSE = {"false", "0", "no", "n", "f", "", "nan", "none", "na"}

    def _audit_bool(_v, _field, _col):
        # Never use Python bool("False")/bool(nan) semantics on a CSV cell.
        if isinstance(_v, bool):
            return _v
        if _v is None or (isinstance(_v, float) and pd.isna(_v)):
            return False
        _s = str(_v).strip().lower()
        if _s in _BOOL_TRUE:
            return True
        if _s in _BOOL_FALSE:
            return False
        raise ValueError(
            f"C4c: audit field {_field!r} for column {_col!r} has an unrecognized "
            f"boolean value {_v!r} -- refusing to silently coerce it to True. Fix "
            "cleaning_b_column_actions.csv or extend the recognized token set."
        )

    # ── B3: intentional scope via current metadata (NOT ANALYSIS_VARS | df.columns)
    _scope = set(ANALYSIS_VARS)
    _fd_scope = B_FEATURE_DICT if ("B_FEATURE_DICT" in dir() and B_FEATURE_DICT is not None) else None
    if _fd_scope is not None:
        for _r in _fd_scope.to_dict("records"):
            _newc = str(_r.get("new_column", "")).strip()
            if _newc not in _scope:
                continue
            for _key in ("source_column", "redundant_with"):
                _val = _r.get(_key)
                if _val is None or (isinstance(_val, float) and pd.isna(_val)):
                    continue
                for _piece in str(_val).replace(";", ",").split(","):
                    _piece = _piece.strip()
                    if _piece and _piece.lower() not in ("nan", "unset", "none", "na", ""):
                        _scope.add(_piece)

    _in_scope_changed = sorted(set(_changed_actions["column"].astype(str)) & _scope)
    print(f"Changed columns relevant to the current staged analytical universe: "
          f"{len(_in_scope_changed)}")
    print("  (ANALYSIS_VARS members + direct B source-column / redundant_with counterparts "
          "of registered representations in ANALYSIS_VARS)")

    _df_raw18 = None
    if _raw18_path is None or not _raw18_path.is_file():
        print()
        print("Canonical work_df_batch18.xlsx is unavailable at "
              f"{_raw18_path if _raw18_path is not None else 'outputs/preprocessing/processed/'} "
              "-- showing B action-log metadata only, no before/after column summary. "
              "No CWD-local substitute is used.")
        for _col in _in_scope_changed[:20]:
            _row = _changed_actions[_changed_actions["column"].astype(str) == _col].iloc[0]
            print(f"  {_col}: action={_row['action']} | detail={_row.get('detail', '')}")
    else:
        _df_raw18 = pd.read_excel(_raw18_path)
        _compare_rows = []
        _metadata_only = []
        for _col in _in_scope_changed:
            _row = _changed_actions[_changed_actions["column"].astype(str) == _col].iloc[0]
            _rcc = _audit_bool(_row.get("row_count_changed"), "row_count_changed", _col)
            _imp = _audit_bool(_row.get("imputation_performed"), "imputation_performed", _col)
            if _col not in _df_raw18.columns or _col not in df.columns:
                # B source column that was renamed/consolidated away, or a
                # representation with no raw 'before' counterpart -- metadata only.
                _metadata_only.append({
                    "column": _col, "action": _row["action"],
                    "in_batch18": _col in _df_raw18.columns,
                    "in_batch19": _col in df.columns,
                    "row_count_changed": _rcc, "imputation_performed": _imp,
                    "detail": str(_row.get("detail", "")),
                })
                continue
            _raw_s = _df_raw18[_col]
            _clean_s = df[_col]
            _compare_rows.append({
                "column": _col,
                "action": _row["action"],
                "dtype_before": str(_raw_s.dtype),
                "dtype_after": str(_clean_s.dtype),
                "missing_before": int(_raw_s.isna().sum()),
                "missing_after": int(_clean_s.isna().sum()),
                "n_unique_before": int(_raw_s.nunique(dropna=True)),
                "n_unique_after": int(_clean_s.nunique(dropna=True)),
                "row_count_changed": _rcc,
                "imputation_performed": _imp,
            })
        cleaning_effect_comparison_df = pd.DataFrame(_compare_rows)
        if len(cleaning_effect_comparison_df):
            print()
            print("Before (Batch 18, raw) vs after (Batch 19, cleaned) -- COLUMN-LEVEL "
                  "summary for in-scope changed columns (dtype / missingness / distinct "
                  "values / B action metadata; NOT a row-level value diff):")
            print(cleaning_effect_comparison_df.to_string(index=False))
        else:
            print()
            print("No in-scope changed column was present under the same name in both "
                  "Batch 18 and Batch 19.")
        if _metadata_only:
            print()
            print("In-scope changed columns with no aligned same-name before/after pair "
                  "(B rename / consolidation / new representation) -- action metadata only:")
            print(pd.DataFrame(_metadata_only).to_string(index=False))

    print()
    print("This section reflects Data Cleaning B's own recorded actions only. It is a "
          "column-level before/after summary (cleaning-effect comparison), not a row-level "
          "value comparison; it does not repeat the full preprocessing report and does not "
          "change any value, row, classification, or eligibility here. Batch 18 is used "
          "solely as the pre-B comparison source; EDA C's analytical input remains the "
          "SHA-verified Batch 19 resolved in C3.")
""")


# ── Section C5 ─────────────────────────────────────────────────────────────────
SC5_HEADER = md("eda-c-s05-header", """
## Section C5 — Missingness Recheck

Per-variable and row-level missingness diagnostic for the **baseline staged
analysis universe (pre-screen)** — the current `ANALYSIS_VARS`. This is a
**missingness-burden diagnostic only**: it does not select, exclude, or
reclassify any variable, and it does **not** establish complete-case analysis
as a default modelling approach. The downstream modelling architecture uses
**fold-safe preprocessing / imputation** (fitted inside cross-validation
training folds); C5 informs that plan, it does not pre-empt it.

**Structural missingness is registry-driven** (`eda_shared/structural_missingness_registry.py`),
in three states that are never conflated:

- **`confirmed_structural`** — a documented, code-enforced subgroup gate. A NaN
  *outside* the applicable subgroup is structural non-applicability, **not**
  analytical missingness. A NaN *within* the applicable subgroup **is** genuine
  analytical missingness and is counted. The whole variable is therefore
  **not** dropped from the row-level metric — only its non-applicable NaNs are.
  Fails loud if a confirmed structural variable lacks the applicability
  metadata needed to interpret it. No NaN→0 recode.
- **`applicability_linked_no_preprocessing_mask`** — the applicability
  relationship is known and its Data Cleaning B treatment is resolved, but no
  preprocessing-enforced structural-missingness mask exists for it (unlike
  `confirmed_structural`). Its **raw** missingness therefore **stays counted**
  in the conservative primary metric by design — there is no code-enforced
  gate to subtract non-applicable NaNs — and the applicability-aware view is
  provided only as a separately labelled sensitivity diagnostic. Nothing about
  this tier is pending a clinical or methodological decision.
  `gestational_age_at_PPROM_days` sits in this tier; it is not treated as a
  `confirmed_structural` variable.
- **`none`** — ordinary missingness; raw missingness counted.
  `diabetes_type` is explicitly `none` (0% missing, no gate).

**Two row-level views** are produced:

| metric | ordinary vars | confirmed structural | applicability-linked (no mask) |
|---|---|---|---|
| `row_missing_count_primary` (canonical, conservative) | raw NaN | NaN **within** the applicable subgroup only | **raw** NaN |
| `row_missing_count_applicability_linked_sensitivity` (diagnostic, labelled) | raw NaN | NaN within applicable subgroup only | NaN within the applicable subgroup only |

The sensitivity view is an **applicability-aware sensitivity diagnostic** for
the applicability-linked tier — explicitly *not* the canonical missingness count.

Counts are reported as **observations (deliveries / rows)**, not "patients":
the dataset contract is one analytical delivery row per row, not necessarily
one unique woman per row across the whole cohort, and unique-woman counts are
never inferred from `delivery_id`.

The treatment / imputation-planning column is a **planning document only** — no
imputation is executed here; all learned imputation occurs inside
cross-validation training folds.
""")

SC5_MISSINGNESS = code("eda-c-s05-missingness", """
# ── Registry tiers (2026-08-31 C2 correction: structural status is registry-
# driven, two disjoint tiers, never config.py). ───────────────────────────────
#   confirmed_structural  -> STRUCTURAL_NAN_COLS (code-enforced gate)
#   applicability_linked_no_preprocessing_mask -> APPLICABILITY_LINKED_COLS
# diabetes_type is deliberately NOT structural in either tier.
_APPLICABILITY_LINKED = set(APPLICABILITY_LINKED_COLS) if "APPLICABILITY_LINKED_COLS" in dir() else set()
_CONFIRMED_STRUCT = set(STRUCTURAL_NAN_COLS)
_MEM = B_FEATURE_MODEL_ENTRY_MODE if "B_FEATURE_MODEL_ENTRY_MODE" in dir() else {}
_N_ROWS = len(df_analysis)


def _c5_applicable_mask(_col, *, _required):
    # Resolve the registry applicability mask for a structural variable.
    # _required=True (confirmed tier): missing metadata -> FAIL LOUD.
    # _required=False (applicability-linked tier): missing gate -> None (caller uses raw).
    _gate = structural_missingness_registry.applicability_gate_for(_col)
    if _gate is None:
        if _required:
            raise RuntimeError(
                f"C5: {_col!r} is a CONFIRMED structural variable but the registry "
                "returns no applicability gate -- cannot separate structural "
                "non-applicability from genuine within-subgroup missingness. FAIL LOUD."
            )
        return None
    _gcol = _gate["gate_column"]
    if _gcol not in df_analysis.columns:
        raise RuntimeError(
            f"C5: applicability gate for {_col!r} references gate column {_gcol!r}, "
            "absent from the analysis dataset -- refusing an all-False mask. FAIL LOUD."
        )
    return df_analysis[_gcol].isin(_gate["gate_values"])


# ── Per-variable missingness table ────────────────────────────────────────────
miss_rows = []
for col in ANALYSIS_VARS:
    _s = df_analysis[col]
    n_miss = int(_s.isna().sum())
    miss_pct = round(_s.isna().mean() * 100, 1)
    is_structural = col in _CONFIRMED_STRUCT
    is_applicability_linked = col in _APPLICABILITY_LINKED
    struct_status = ("confirmed_structural" if is_structural
                     else ("applicability_linked_no_preprocessing_mask" if is_applicability_linked
                           else "none"))
    var_type = infer_var_type(_s)
    _mem = _MEM.get(col, "direct")

    _applicable_n = ""
    _miss_within_applicable_n = ""
    _aaw_pct = ""
    _nonapplicable_nan_n = ""
    if is_structural or is_applicability_linked:
        _mask = _c5_applicable_mask(col, _required=is_structural)
        if _mask is not None:
            _applicable_n = int(_mask.sum())
            _miss_within_applicable_n = int(_s[_mask].isna().sum())
            _nonapplicable_nan_n = int(_s[~_mask].isna().sum())
            _aaw_pct = (round(_miss_within_applicable_n / _applicable_n * 100, 1)
                        if _applicable_n else np.nan)

    # counted-in-primary-row-metric semantics
    if is_structural:
        _counted_primary = "NaN within applicable subgroup only"
    else:
        _counted_primary = "raw NaN"

    # ── D1/D2/D3: treatment recommendation respects the modeling contract ─────
    if is_structural:
        treatment_rec = (
            "confirmed structural — applicability-gated, subgroup-aware handling. "
            "NaN outside the applicable subgroup is non-applicability, not missingness; "
            "within-subgroup missingness follows the variable's modeling contract. "
            "No blind median/mode imputation, no NaN->0 recode."
        )
    elif is_applicability_linked:
        treatment_rec = (
            "applicability-linked; no preprocessing mask — raw missingness stays "
            "counted in the primary metric (no code-enforced gate exists to subtract "
            "non-applicable NaNs). Treatment follows the variable's modeling "
            "contract (model_entry_mode"
            + (" = transform_source_only, i.e. deferred to the fold-safe modeling "
               "transformation contract" if _mem == "transform_source_only" else "")
            + "), NOT blind median/mode imputation and NOT a NaN->0 recode. "
            "Applicability-aware view is sensitivity-only."
        )
    elif _mem == "transform_source_only":
        treatment_rec = (
            "transform_source_only — representation/treatment is deferred to the "
            "fold-safe modeling transformation contract. Not an ordinary direct "
            "predictor; no generic median/mode imputation and no generic missing "
            "indicator is proposed here."
        )
    elif col == "BMI_before":
        # BMI_before is NOT directly median-imputed. Its model contract is
        # fold_safe_recomputed_continuous / FS_RECOMPUTED_BMI_V1: height and
        # weight_before_pregnancy are median-imputed inside the training fold
        # and BMI_before is then recomputed from those component values.
        treatment_rec = (
            "fold-safe recomputed continuous (FS_RECOMPUTED_BMI_V1) — height and "
            "weight_before_pregnancy are median-imputed within the training fold "
            "and BMI_before is recomputed from those components; BMI_before "
            "itself is NOT directly median-imputed. No missing indicator."
        )
    elif miss_pct == 0:
        treatment_rec = "none required (0% missing)"
    elif var_type == "numeric":
        treatment_rec = (
            "direct numeric — approved median imputation, fitted within the "
            "training fold only. A missing indicator is NOT proposed generically; "
            "only an explicit current variable-level decision would add one."
        )
    else:
        treatment_rec = (
            "direct categorical — missingness treatment/encoding fitted within the "
            "training fold according to the variable's modeling contract. No new "
            "explicit 'unknown' category is proposed here unless an approved current "
            "representation already defines one."
        )

    miss_rows.append({
        "variable": col,
        "type": var_type,
        "model_entry_mode": _mem,
        "N_missing_raw": n_miss,
        "missing_%_raw": miss_pct,
        "structural_nan": is_structural,
        "structural_status": struct_status,
        "applicable_n": _applicable_n,
        "nonapplicable_nan_n": _nonapplicable_nan_n,
        "missing_within_applicable_n": _miss_within_applicable_n,
        "applicability_aware_missing_%": _aaw_pct,
        "counted_in_primary_row_metric": _counted_primary,
        "treatment_recommendation": treatment_rec,
    })

missingness_df = (
    pd.DataFrame(miss_rows)
    .sort_values(["structural_nan", "missing_%_raw"], ascending=[False, False])
    .reset_index(drop=True)
)
print("Per-variable missingness (baseline staged analysis universe, pre-screen):")
print(missingness_df.to_string(index=False))

# ── Row-level missingness — PRIMARY conservative + applicability-linked sensitivity
# Confirmed structural: count ONLY NaN within the applicable subgroup (structural
# non-applicability is not missingness). Applicability-linked (no preprocessing
# mask): raw NaN in the primary metric (no code-enforced gate to subtract
# non-applicable NaNs). Ordinary: raw NaN.
_ordinary_vars = [c for c in ANALYSIS_VARS
                  if c not in _CONFIRMED_STRUCT and c not in _APPLICABILITY_LINKED]
_confirmed_vars = [c for c in ANALYSIS_VARS if c in _CONFIRMED_STRUCT]
_applicability_linked_vars = [c for c in ANALYSIS_VARS if c in _APPLICABILITY_LINKED]

_ord_missing = df_analysis[_ordinary_vars].isna()

_conf_missing = pd.DataFrame(index=df_analysis.index)
for _c in _confirmed_vars:
    _m = _c5_applicable_mask(_c, _required=True)
    _conf_missing[_c] = df_analysis[_c].isna() & _m

_al_missing_raw = df_analysis[_applicability_linked_vars].isna() if _applicability_linked_vars else pd.DataFrame(index=df_analysis.index)
_al_missing_sens = pd.DataFrame(index=df_analysis.index)
for _c in _applicability_linked_vars:
    _m = _c5_applicable_mask(_c, _required=False)
    _al_missing_sens[_c] = (df_analysis[_c].isna() & _m) if _m is not None else df_analysis[_c].isna()

row_missing_count_primary = (
    _ord_missing.sum(axis=1) + _conf_missing.sum(axis=1) + _al_missing_raw.sum(axis=1)
).astype(int)
row_missing_count_applicability_linked_sensitivity = (
    _ord_missing.sum(axis=1) + _conf_missing.sum(axis=1) + _al_missing_sens.sum(axis=1)
).astype(int)

print()
print("Row-level missingness -- PRIMARY conservative metric (row_missing_count_primary):")
print("  ordinary vars: raw NaN | confirmed structural: NaN within applicable subgroup "
      "only | applicability-linked (no mask): raw NaN")
for threshold in [1, 3, 5]:
    _n = int((row_missing_count_primary >= threshold).sum())
    _pct = round(_n / _N_ROWS * 100, 1)
    print(f"  Observations (deliveries/rows) with >= {threshold} missing: {_n} ({_pct}%)")

print()
print("Row-level missingness -- applicability-linked SENSITIVITY diagnostic (NOT the canonical "
      "count; row_missing_count_applicability_linked_sensitivity):")
print("  identical to primary except applicability-linked vars use their applicability-aware "
      "missingness instead of raw NaN")
for threshold in [1, 3, 5]:
    _n = int((row_missing_count_applicability_linked_sensitivity >= threshold).sum())
    _pct = round(_n / _N_ROWS * 100, 1)
    print(f"  Observations (deliveries/rows) with >= {threshold} missing: {_n} ({_pct}%)")

# ── Live confirmed-structural example: non-applicable NaN excluded vs applicable
# missing included ───────────────────────────────────────────────────────────
print()
print("Confirmed-structural handling check (non-applicable NaN excluded; applicable "
      "missing included):")
if _confirmed_vars:
    for _c in _confirmed_vars:
        _m = _c5_applicable_mask(_c, _required=True)
        _app_n = int(_m.sum())
        _nonapp_nan = int(df_analysis.loc[~_m, _c].isna().sum())
        _app_miss = int(df_analysis.loc[_m, _c].isna().sum())
        print(f"  {_c}: applicable_n={_app_n} | non-applicable NaN (excluded from missingness)"
              f"={_nonapp_nan} | missing WITHIN applicable subgroup (counted)={_app_miss}")
else:
    print("  (no confirmed-structural variable is in the current staged analysis universe)")

print()
print("Applicability-linked (no preprocessing mask) example:")
if _applicability_linked_vars:
    for _c in _applicability_linked_vars:
        _m = _c5_applicable_mask(_c, _required=False)
        _raw = int(df_analysis[_c].isna().sum())
        if _m is None:
            print(f"  {_c}: raw missing (counted in primary)={_raw}; no registry gate -> "
                  "sensitivity == raw")
        else:
            _app_n = int(_m.sum())
            _app_miss = int(df_analysis.loc[_m, _c].isna().sum())
            print(f"  {_c}: status=applicability_linked_no_preprocessing_mask | raw missing "
                  f"(counted in PRIMARY)={_raw} | applicability-aware within-subgroup missing "
                  f"(SENSITIVITY ONLY, applicable_n={_app_n})={_app_miss} -- NOT relabelled "
                  "'genuine/effective missingness'")
else:
    print("  (no applicability-linked variable is in the current staged analysis universe)")

# ── High-missingness diagnostic (Part E) -- diagnostic only, never eligibility ─
_high_miss = missingness_df.loc[missingness_df["missing_%_raw"] > 20].copy()
print()
if len(_high_miss):
    print(f"Variables with >20% RAW whole-cohort missingness ({len(_high_miss)}) -- "
          "DIAGNOSTIC ONLY, does not affect eligibility (no generic >20%/>40% hard rule):")
    _hm_disp = _high_miss[["variable", "type", "structural_status", "missing_%_raw",
                           "applicability_aware_missing_%", "counted_in_primary_row_metric"]]
    print(_hm_disp.to_string(index=False))
    print("  A confirmed-structural variable with high RAW NaN is NOT automatically a data-"
          "quality problem -- most of that NaN is structural non-applicability (see "
          "applicability_aware_missing_%). An applicability-linked variable's high raw NaN "
          "stays visible as raw NaN, not relabelled a confirmed 'effective missingness'.")
else:
    print("No variable exceeds 20% raw whole-cohort missingness.")
""")


# ── Section C5b ────────────────────────────────────────────────────────────────
SC5B_HEADER = md("eda-c-s05b-header", """
## Section C5b — Missingness Deep-Dive (adapts CURRENT A2.7)

Ports A2.7's analytical components onto the cleaned Batch 19 data, **aligned
with C5's canonical missingness contract**:

- ordinary variables → **raw NaN**;
- confirmed structural → only NaN **inside the applicable subgroup** is
  analytical missingness (structural non-applicability is not missingness);
- applicability-linked (no preprocessing mask) → **raw NaN** is canonical /
  conservative; the applicability-aware interpretation is a **sensitivity
  diagnostic only** and never replaces the raw primary values.

Contents:

- **A. Missingness-by-target** — (1) a **RAW whole-column missingness by
  target** table, then (2) the **C5-PRIMARY analytical** view per target group,
  carrying `applicable_n` / `missing_within_applicable_n` /
  `applicability_aware_missing_pct` for structural / applicability-gated
  variables (for an *applicability-linked* variable these are explicitly
  labelled **sensitivity only** and do not replace the raw primary
  values). **Descriptive only** — a target-group difference is NOT evidence of
  MAR, MNAR, or causality and never changes eligibility.
- **B. Missingness heatmap** — depicts **PRIMARY analytical missingness**
  (observations × variables) using the same semantics as C5; confirmed
  structural non-applicability is **not** rendered as analytical missingness.
  Confirmed / applicability-linked status stays annotated; row order is unsorted (no
  clinically meaningful ordering justified); no identifiers. A secondary RAW
  whole-column heatmap is shown only if it would differ from the primary one.
- **C. Co-missingness** — computed on the **same PRIMARY masks** as C5
  (confirmed structural non-applicability is not co-missingness;
  applicability-linked variables use raw NaN because no preprocessing mask
  exists for them). `jaccard` / `lift_vs_independence` are **descriptive pattern
  metrics only** — NOT MAR, NOT MNAR, NOT a causal missingness mechanism, NOT
  redundancy, NOT a feature-exclusion decision.

Terminology: counts are **observations (deliveries / rows)**, never
"patients"; unique women are not inferred from delivery rows. The generic
`>40%` hard exclusion is **not** restored.
""")

SC5B_DEEPDIVE = code("eda-c-s05b-deepdive", """
_APPLICABILITY_LINKED = set(APPLICABILITY_LINKED_COLS) if "APPLICABILITY_LINKED_COLS" in dir() else set()
_CONFIRMED_STRUCT_C5B = set(STRUCTURAL_NAN_COLS)


def _struct_tag(_v):
    if _v in _CONFIRMED_STRUCT_C5B:
        return "confirmed_structural"
    if _v in _APPLICABILITY_LINKED:
        return "applicability_linked_no_preprocessing_mask"
    return "none"


def _c5b_applicable_mask(_v):
    # registry applicability mask for a structural / applicability-linked variable, else None.
    _gate = structural_missingness_registry.applicability_gate_for(_v)
    if _gate is None:
        return None
    _gcol = _gate["gate_column"]
    if _gcol not in df_analysis.columns:
        raise RuntimeError(
            f"C5b: applicability gate for {_v!r} references gate column {_gcol!r}, "
            "absent from the analysis dataset -- refusing an all-False mask. FAIL LOUD."
        )
    return df_analysis[_gcol].isin(_gate["gate_values"])


def _c5b_primary_missing_mask(_v):
    # PRIMARY analytical missingness mask, identical semantics to C5:
    #   ordinary            -> raw isna
    #   confirmed structural -> isna & applicable   (FAIL LOUD if no gate)
    #   applicability-linked -> raw isna            (no preprocessing mask)
    _isna = df_analysis[_v].isna()
    if _v in _CONFIRMED_STRUCT_C5B:
        _m = _c5b_applicable_mask(_v)
        if _m is None:
            raise RuntimeError(
                f"C5b: {_v!r} is confirmed structural but the registry gives no "
                "applicability gate -- cannot separate structural non-applicability "
                "from within-subgroup missingness. FAIL LOUD."
            )
        return _isna & _m
    return _isna


_miss_vars = [c for c in ANALYSIS_VARS if df_analysis[c].isna().any()]
_miss_vars_primary = [c for c in ANALYSIS_VARS if bool(_c5b_primary_missing_mask(c).any())]
print(f"Variables with any RAW missingness in the analysis universe: {len(_miss_vars)} / {len(ANALYSIS_VARS)}")
print(f"Variables with any PRIMARY analytical missingness (C5 semantics): "
      f"{len(_miss_vars_primary)} / {len(ANALYSIS_VARS)}")

# ── A. Missingness-by-target ──────────────────────────────────────────────────
_g0m = df_analysis[TARGET_COL] == 0
_g1m = df_analysis[TARGET_COL] == 1
_n0_c5b, _n1_c5b = int(_g0m.sum()), int(_g1m.sum())

_RAW_BT_COLS = ["variable", "structural_status", "earliest_entry_stage",
                "raw_missing_pct_target0", "raw_missing_pct_target1", "raw_abs_diff_pct"]
_raw_bt_rows = []
for _c in _miss_vars:
    _m0 = round(df_analysis.loc[_g0m, _c].isna().mean() * 100, 1)
    _m1 = round(df_analysis.loc[_g1m, _c].isna().mean() * 100, 1)
    _st = EARLIEST_ENTRY_STAGE.get(_c)
    _raw_bt_rows.append({
        "variable": _c, "structural_status": _struct_tag(_c),
        "earliest_entry_stage": _st if _st is not None else "",
        "raw_missing_pct_target0": _m0, "raw_missing_pct_target1": _m1,
        "raw_abs_diff_pct": round(abs(_m0 - _m1), 1),
    })
raw_missingness_by_target_df = pd.DataFrame(_raw_bt_rows, columns=_RAW_BT_COLS)
if len(raw_missingness_by_target_df):
    raw_missingness_by_target_df = raw_missingness_by_target_df.sort_values(
        "raw_abs_diff_pct", ascending=False).reset_index(drop=True)
print()
print("A(1). RAW whole-column missingness by target group (DESCRIPTIVE ONLY -- "
      "not MAR/MNAR/causal evidence, never an exclusion reason):")
print(raw_missingness_by_target_df.to_string(index=False) if len(raw_missingness_by_target_df)
      else "  (no variable has any missingness)")

_BT_COLS = ["variable", "structural_status", "earliest_entry_stage",
            "raw_missing_pct_target0", "raw_missing_pct_target1", "raw_abs_diff_pct",
            "primary_missing_pct_target0", "primary_missing_pct_target1", "primary_abs_diff_pct",
            "applicable_n_target0", "applicable_n_target1",
            "missing_within_applicable_n_target0", "missing_within_applicable_n_target1",
            "applicability_aware_missing_pct_target0", "applicability_aware_missing_pct_target1",
            "applicability_aware_view_label"]
_bt_rows = []
for _c in _miss_vars:
    _st = EARLIEST_ENTRY_STAGE.get(_c)
    _tag = _struct_tag(_c)
    _rm0 = round(df_analysis.loc[_g0m, _c].isna().mean() * 100, 1)
    _rm1 = round(df_analysis.loc[_g1m, _c].isna().mean() * 100, 1)
    _pmask = _c5b_primary_missing_mask(_c)
    _pm0 = round(_pmask[_g0m].mean() * 100, 1) if _n0_c5b else np.nan
    _pm1 = round(_pmask[_g1m].mean() * 100, 1) if _n1_c5b else np.nan
    _appmask = _c5b_applicable_mask(_c) if _tag != "none" else None
    _an0 = _an1 = _mw0 = _mw1 = _aa0 = _aa1 = ""
    _label = ""
    if _appmask is not None:
        _a0 = _appmask & _g0m
        _a1 = _appmask & _g1m
        _an0, _an1 = int(_a0.sum()), int(_a1.sum())
        _mw0 = int(df_analysis.loc[_a0, _c].isna().sum())
        _mw1 = int(df_analysis.loc[_a1, _c].isna().sum())
        _aa0 = round(_mw0 / _an0 * 100, 1) if _an0 else np.nan
        _aa1 = round(_mw1 / _an1 * 100, 1) if _an1 else np.nan
        _label = ("confirmed_structural -- this IS the canonical primary per-target value"
                  if _tag == "confirmed_structural"
                  else "applicability-linked sensitivity view only -- does NOT replace raw primary")
    _bt_rows.append({
        "variable": _c, "structural_status": _tag,
        "earliest_entry_stage": _st if _st is not None else "",
        "raw_missing_pct_target0": _rm0, "raw_missing_pct_target1": _rm1,
        "raw_abs_diff_pct": round(abs(_rm0 - _rm1), 1),
        "primary_missing_pct_target0": _pm0, "primary_missing_pct_target1": _pm1,
        "primary_abs_diff_pct": round(abs(_pm0 - _pm1), 1) if pd.notna(_pm0) and pd.notna(_pm1) else np.nan,
        "applicable_n_target0": _an0, "applicable_n_target1": _an1,
        "missing_within_applicable_n_target0": _mw0, "missing_within_applicable_n_target1": _mw1,
        "applicability_aware_missing_pct_target0": _aa0, "applicability_aware_missing_pct_target1": _aa1,
        "applicability_aware_view_label": _label,
    })
missingness_by_target_df = pd.DataFrame(_bt_rows, columns=_BT_COLS)
if len(missingness_by_target_df):
    missingness_by_target_df = missingness_by_target_df.sort_values(
        "raw_abs_diff_pct", ascending=False).reset_index(drop=True)
print()
print("A(2). C5-PRIMARY analytical missingness by target group (confirmed structural: NaN "
      "within applicable subgroup only | applicability-linked (no mask): raw NaN | ordinary: raw NaN). "
      "DESCRIPTIVE ONLY -- not MAR/MNAR/causal, never an exclusion reason:")
print(missingness_by_target_df.to_string(index=False) if len(missingness_by_target_df)
      else "  (no variable has any missingness)")
print("  For an applicability-linked variable the applicability_aware_* columns are a "
      "sensitivity-only diagnostic and do NOT replace the raw primary values.")

# ── B. Missingness heatmap (PRIMARY analytical missingness) ────────────────────
if _miss_vars_primary:
    _prim_mat = pd.DataFrame(
        {c: _c5b_primary_missing_mask(c).astype(int) for c in _miss_vars_primary},
        index=df_analysis.index,
    )
    _order = _prim_mat.mean().sort_values(ascending=False).index.tolist()
    _fig_h = max(4, 0.16 * len(_order) + 2)
    fig, ax = plt.subplots(figsize=(11, _fig_h))
    sns.heatmap(_prim_mat[_order].T, cbar=False, cmap=["#e8eef3", "#c0392b"], ax=ax)
    ax.set_xlabel(f"observations (deliveries / rows) (n={len(df_analysis)}, unsorted row order)")
    ax.set_ylabel("variable (desc. by PRIMARY analytical missing rate)")
    _yt = [(f"{v}  *confirmed-struct" if v in _CONFIRMED_STRUCT_C5B
            else (f"{v}  *applicability-linked" if v in _APPLICABILITY_LINKED else v)) for v in _order]
    ax.set_yticks([i + 0.5 for i in range(len(_order))])
    ax.set_yticklabels(_yt, fontsize=8)
    ax.set_title("C5b-B  PRIMARY analytical-missingness heatmap (red = analytical missing; "
                 "structural non-applicability is NOT shown as missing)")
    plt.tight_layout()
    plt.show()
    plt.close(fig)

    # Secondary RAW heatmap only if it would actually differ from the primary one.
    _raw_only_extra = sorted(set(_miss_vars) - set(_miss_vars_primary))
    _raw_differs = bool(_raw_only_extra) or any(
        not df_analysis[c].isna().equals(_c5b_primary_missing_mask(c)) for c in _miss_vars_primary
    )
    if _raw_differs:
        _raw_order = (df_analysis[_miss_vars].isna().mean().sort_values(ascending=False).index.tolist())
        _raw_mat = df_analysis[_raw_order].isna().astype(int)
        fig, ax = plt.subplots(figsize=(11, max(4, 0.16 * len(_raw_order) + 2)))
        sns.heatmap(_raw_mat.T, cbar=False, cmap=["#e8eef3", "#c0392b"], ax=ax)
        ax.set_xlabel(f"observations (deliveries / rows) (n={len(df_analysis)}, unsorted row order)")
        ax.set_ylabel("variable (desc. by RAW missing rate)")
        ax.set_yticks([i + 0.5 for i in range(len(_raw_order))])
        ax.set_yticklabels(
            [(f"{v}  *confirmed-struct" if v in _CONFIRMED_STRUCT_C5B
              else (f"{v}  *applicability-linked" if v in _APPLICABILITY_LINKED else v)) for v in _raw_order],
            fontsize=8)
        ax.set_title("C5b-B (secondary)  RAW whole-column missingness heatmap "
                     "(includes structural non-applicability)")
        plt.tight_layout()
        plt.show()
        plt.close(fig)
    else:
        print("B. Secondary RAW-missingness heatmap omitted -- identical to the PRIMARY heatmap "
              "in the current cohort (every confirmed-structural variable is 0% missing, so "
              "raw NaN and primary analytical missingness coincide).")
else:
    print("B. No PRIMARY analytical missingness in the analysis universe -- heatmap skipped.")

# ── C. Co-missingness (PRIMARY masks) ─────────────────────────────────────────
_CO_COLS = ["var_a", "var_b", "n_both_missing", "jaccard", "lift_vs_independence",
            "a_structural", "b_structural"]
_co_rows = []
_mv = _miss_vars_primary
_prim_cache = {c: _c5b_primary_missing_mask(c) for c in _mv}
for _i in range(len(_mv)):
    for _j in range(_i + 1, len(_mv)):
        _a, _b = _mv[_i], _mv[_j]
        _ma, _mb = _prim_cache[_a], _prim_cache[_b]
        _both = int((_ma & _mb).sum())
        if _both == 0:
            continue
        _either = int((_ma | _mb).sum())
        _jacc = round(_both / _either, 3) if _either else 0.0
        _exp = _ma.mean() * _mb.mean() * len(df_analysis)
        _lift = round(_both / _exp, 2) if _exp > 0 else float("inf")
        if _jacc >= 0.5 or (_lift != float("inf") and _lift >= 3 and _both >= 5):
            _co_rows.append({
                "var_a": _a, "var_b": _b, "n_both_missing": _both,
                "jaccard": _jacc, "lift_vs_independence": _lift,
                "a_structural": _struct_tag(_a), "b_structural": _struct_tag(_b),
            })
comissingness_df = pd.DataFrame(_co_rows, columns=_CO_COLS)
if len(comissingness_df):
    comissingness_df = comissingness_df.sort_values("jaccard", ascending=False).reset_index(drop=True)
print()
print("C. Co-missingness on PRIMARY analytical-missingness masks (Jaccard >= 0.5, OR "
      "lift >= 3x with >= 5 co-missing) -- DESCRIPTIVE ONLY:")
if len(comissingness_df):
    print(comissingness_df.to_string(index=False))
    print("Interpretation is structural / shared-source pattern detection -- NOT redundancy, "
          "NOT a feature-exclusion decision, and NOT evidence of MAR, MNAR, or any causal "
          "missingness mechanism.")
else:
    print("  No variable pairs meet the co-missingness thresholds on the primary masks.")
print()
print("D. Retained from C5 unchanged: whole-cohort per-variable missingness, applicability-"
      "aware row-level missingness (`row_missing_count_primary` + labelled applicability-linked "
      "sensitivity), and the structural-missingness registry (see C5 + C3b). "
      "Generic >40% hard exclusion NOT restored.")
""")


# ── Section C6 ─────────────────────────────────────────────────────────────────
SC6_HEADER = md("eda-c-s06-header", """
## Section C6 — Sparsity and Separation Diagnostic

For binary and categorical variables in the **baseline staged analysis
universe (pre-screen)** this section tabulates, per target group and **observed**
level:

- **Separation warning** (`separation_risk`) — an empty target-by-level cell.
  For an **unregularized, dummy-coded** logistic-regression coefficient this is
  a separation / unstable-estimation warning: the maximum-likelihood estimate
  for that coefficient may be infinite or unstable (it diverges). It does
  **not** mean that every downstream **regularized / penalized** logistic model
  necessarily cannot fit the variable.
- **Small-cell / sparse warning** (`too_sparse`) — no empty cell, but the
  smallest target-by-level cell count is `< 5`. The `< 5` value is a
  **heuristic review threshold** (the project's established small-cell
  convention), **not** a universal statistical exclusion rule: it does not by
  itself merge or drop a category or a variable, and downstream category
  encoding / handling is fold-safe and model-stage dependent.

**This is a soft diagnostic, not an eligibility gate.** `separation_risk` /
`too_sparse` / `min_cell_count` are informational flags, surfaced for review and
carried forward as disclosed soft-warning flags in the C12 pipeline; they do
**not** by themselves hard-exclude a variable, change a classification, or
change `earliest_entry_stage`. Target-independent hard eligibility is decided in
C12, not here. A variable flagged here is expected to remain in the candidate
pool with the corresponding risk flag disclosed.

**C6 vs C12 — distinct concerns:**

- **C6** is an *observed* target-by-level sparsity / separation diagnostic — it
  only iterates the levels actually present in the data. A binary variable with
  a single observed level does **not** trigger C6's empty-cell logic (there is
  no second observed level to be empty), and it is **not** forced into C6 as
  "separation".
- **C12** performs the *target-independent* **zero-variance hard exclusion**
  (one observed value, no missingness). That is where a constant predictor is
  removed from the eligible pool. The two are deliberately separate.

**Share-safe display.** The printed table `sparsity_display_df` suppresses
protected small counts (`min_cell_count`, `cs_group_events`, per-variable
missing counts) per the project disclosure threshold (`n < 5`), reusing the
`share_safe` helper / `SHARE_SAFE_MODE` already loaded for C4b. A suppressed
value is shown as a suppression marker, **never** converted to `0`. The
analytical `sparsity_df` keeps exact values unchanged for the downstream
C10 / C12 pipeline.
""")

SC6_SPARSITY = code("eda-c-s06-sparsity", """
_SS_C6 = bool(SHARE_SAFE_MODE) if "SHARE_SAFE_MODE" in dir() else True
_SS_C6_THR = share_safe.DEFAULT_DISCLOSURE_THRESHOLD

sparsity_rows = []
for col in ANALYSIS_VARS:
    var_type = infer_var_type(df_analysis[col])
    if var_type not in ("binary", "categorical"):
        continue

    observed = df_analysis[[col, TARGET_COL]].dropna(subset=[col])
    group0 = observed[observed[TARGET_COL] == 0]
    group1 = observed[observed[TARGET_COL] == 1]
    levels = sorted(observed[col].unique())

    all_cells = []
    for level in levels:
        all_cells.append(int((group0[col] == level).sum()))
        all_cells.append(int((group1[col] == level).sum()))

    min_cell = min(all_cells) if all_cells else 0
    separation = any(c == 0 for c in all_cells)
    too_sparse = (not separation) and (min_cell < 5)
    cs_events = int((group1[col] == 1).sum()) if set(levels).issubset({0, 1, 0.0, 1.0}) else None
    single_observed_level = len(levels) <= 1

    sparsity_rows.append({
        "variable": col,
        "type": var_type,
        "N_analyzed": len(observed),
        "N_missing": int(df_analysis[col].isna().sum()),
        "n_levels": len(levels),
        "single_observed_level": single_observed_level,
        "min_cell_count": min_cell,
        "cs_group_events": cs_events,
        "separation_risk": separation,
        "too_sparse": too_sparse,
        "flag": "SEPARATION" if separation else ("SPARSE" if too_sparse else "ok"),
    })

# ── analytical frame -- EXACT values, consumed downstream (C10 / C12). Column
# set and semantics unchanged; `single_observed_level` is an additive
# disclosure column only. ─────────────────────────────────────────────────────
sparsity_df = pd.DataFrame(sparsity_rows).sort_values(
    ["separation_risk", "too_sparse", "min_cell_count"],
    ascending=[False, False, True],
).reset_index(drop=True)

# soft-warning list (2026-09-01: the former "blocking"-named list is retired --
# these are diagnostic warnings, NOT an eligibility gate).
sparsity_warning_vars = (
    sparsity_df.loc[sparsity_df["separation_risk"] | sparsity_df["too_sparse"], "variable"].tolist()
)

# ── presentation-only share-safe copy -- suppresses protected small counts;
# does NOT feed any downstream calculation. ───────────────────────────────────
sparsity_display_df = sparsity_df.copy()
_n_rows_c6 = len(df_analysis)
sparsity_display_df["min_cell_count"] = [
    share_safe.safe_count(int(v), threshold=_SS_C6_THR, enabled=_SS_C6) for v in sparsity_df["min_cell_count"]
]
sparsity_display_df["cs_group_events"] = [
    (None if pd.isna(v) else share_safe.safe_count(int(v), threshold=_SS_C6_THR, enabled=_SS_C6))
    for v in sparsity_df["cs_group_events"]
]
sparsity_display_df["N_missing"] = [
    share_safe.safe_count(int(v), threshold=_SS_C6_THR, enabled=_SS_C6) for v in sparsity_df["N_missing"]
]
sparsity_display_df["N_analyzed"] = [
    share_safe.safe_count_with_complement(int(v), _n_rows_c6, threshold=_SS_C6_THR, enabled=_SS_C6)
    for v in sparsity_df["N_analyzed"]
]

print("C6 -- Sparsity and Separation DIAGNOSTIC (soft warnings only -- NOT an eligibility gate):")
print(sparsity_display_df.to_string(index=False))
print()
print(f"Sparsity / separation warnings (diagnostic): {len(sparsity_warning_vars)} variable(s)")
if sparsity_warning_vars:
    print(f"  {sparsity_warning_vars}")
    print("  These are surfaced for review and are carried forward as DISCLOSED soft-warning")
    print("  flags (separation_risk / sparse_event_risk) in the C12 pipeline. They do NOT")
    print("  hard-exclude a variable, change its classification, or change earliest_entry_stage.")
print()
print("min_cell_count < 5 is a heuristic small-cell review threshold, not a statistical")
print("exclusion rule -- no category or variable is merged or dropped here. Zero variance is")
print("a separate, target-independent C12 hard exclusion (see the section header). The printed")
print("table above is share-safe (sparsity_display_df); the analytical sparsity_df keeps exact")
print("values for the downstream C10 / C12 pipeline. Suppressed cells show a marker, not 0.")
""")


# ── Section C7 ─────────────────────────────────────────────────────────────────
SC7_HEADER = md("eda-c-s07-header", """
## Section C7 — Outlier Recheck (Numeric Variables — Statistical IQR Screen)

Target-blind IQR 1.5× extreme-value flags for every numeric variable in the
**baseline staged analysis universe (pre-screen)** — the current `ANALYSIS_VARS`.
C7 runs *before* the C12 target-independent hard eligibility screen.

**What C7 reports** per numeric variable: `N_nonmissing`, `missing_n` /
`missing_pct`, median / Q1 / Q3 / IQR / min / max, the IQR 1.5× bounds, the
count of non-missing values outside those bounds (`n_outliers`), and the
outlier rate **among the non-missing observations that were actually eligible
for the IQR calculation** (`outlier_pct_of_nonmissing`).

**Denominator correction (2026-09-01).** The outlier rate is
`n_outliers / N_nonmissing × 100` (`outlier_pct_of_nonmissing`) — computed on
the non-missing values only. The previous `outlier_mask.mean()` used the full
cohort as the denominator (a `NaN` comparison is `False`), understating the rate
for any variable with missingness. `outlier_pct_of_all_rows` is kept as
optional whole-cohort context and is **not** the ranking key. For every numeric
variable `N_nonmissing + missing_n == len(df_analysis)` and
`0 <= n_outliers <= N_nonmissing` are asserted (fail loud). A variable with
`N_nonmissing == 0` is marked `all_missing / not_evaluable` (quartiles / skew /
rate not computed) and is **not** excluded — eligibility is decided in C12. A
variable with a small but non-zero `N_nonmissing` keeps its descriptive
calculation where technically defined; `N_nonmissing` is shown prominently and
its outlier rate is to be read as small-N / less stable. No `< 4` (or any other
new) evaluability / exclusion threshold is introduced.

**What C7 does NOT do:**

- It does **not** classify a flagged value as a "plausible extreme", a
  "possible data error", or "unclear". There is **no clinical plausible-range
  registry in EDA C and none is invented here** — EDA A2's outlier section and
  Data Cleaning B follow the same principle (plausibility-range / impossible-value
  handling is owned by preprocessing). The plausibility of the known extreme
  records was already reviewed **upstream, target-blind**, using the
  preprocessing review exports; C7 therefore performs only descriptive,
  target-blind IQR / skewness diagnostics and does **not** re-adjudicate,
  remove, cap, or transform any value.
- **An IQR 1.5× flag is a statistical-extremeness signal only — NOT a data
  error and NOT grounds for removal.** No value is removed, capped,
  winsorized, or transformed in C7.
- No transformation is fitted here. `transformation_review_flag`
  (`|skewness| > 1.5`) is a **descriptive audit signal only** — it does
  **not** mean "log-transform" and it never overrides a variable's
  model-entry contract (e.g. `transform_source_only`). It does **not** route
  a variable to any downstream transformation and has **zero effect** on the
  C14 treatment plan.

C14's `transformation_plan` is derived from the C13 `physical_variable_type`
contract (aligned with Data Cleaning B Section B3, 2026-09-01), never from
this flag or from skewness. A future nonlinear functional-form alternative
may only be introduced by a separate, explicit modeling-stage rationale,
evaluated fold-safely inside cross-validation if data-dependent — never
merely because this flag is set.
""")

SC7_OUTLIERS = code("eda-c-s07-outliers", """
_numeric_analysis_vars = [c for c in ANALYSIS_VARS if infer_var_type(df_analysis[c]) == "numeric"]
_N_ROWS_C7 = len(df_analysis)
outlier_rows = []
_c7_recon_errors = []
for col in _numeric_analysis_vars:
    _s = df_analysis[col]
    values = _s.dropna()
    N_nonmissing = int(len(values))
    missing_n = int(_s.isna().sum())
    missing_pct = round(_s.isna().mean() * 100, 1)
    # ── C2 reconciliation ───────────────────────────────────────────────────
    if N_nonmissing + missing_n != _N_ROWS_C7:
        _c7_recon_errors.append(
            f"{col}: N_nonmissing({N_nonmissing}) + missing_n({missing_n}) != cohort N ({_N_ROWS_C7})")
    if N_nonmissing == 0:
        # all-missing: do NOT compute quartiles / skew / rate; do NOT exclude.
        outlier_rows.append({
            "variable": col, "N_nonmissing": 0, "missing_n": missing_n, "missing_pct": missing_pct,
            "median": None, "q1": None, "q3": None, "iqr": None, "min": None, "max": None,
            "iqr_lower": None, "iqr_upper": None, "n_outliers": None,
            "outlier_pct_of_nonmissing": None, "outlier_pct_of_all_rows": None,
            "skewness": None, "transformation_review_flag": False,
            "evaluability": "all_missing / not_evaluable",
        })
        continue
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    # outlier mask is computed on the NON-MISSING values only (a NaN comparison
    # is False, so masking df_analysis[col] silently used the full cohort as the
    # denominator -- the 2026-09-01 blocker).
    _outlier_mask_nonmissing = (values < lower) | (values > upper)
    n_outliers = int(_outlier_mask_nonmissing.sum())
    if not (0 <= n_outliers <= N_nonmissing):
        _c7_recon_errors.append(
            f"{col}: n_outliers({n_outliers}) not in [0, N_nonmissing({N_nonmissing})]")
    outlier_pct_of_nonmissing = round(n_outliers / N_nonmissing * 100, 1)
    outlier_pct_of_all_rows = round(n_outliers / _N_ROWS_C7 * 100, 1)
    skewness = float(values.skew()) if N_nonmissing >= 3 else float("nan")
    outlier_rows.append({
        "variable": col,
        "N_nonmissing": N_nonmissing,
        "missing_n": missing_n,
        "missing_pct": missing_pct,
        "median": round(float(values.median()), 3),
        "q1": round(float(q1), 3),
        "q3": round(float(q3), 3),
        "iqr": round(float(iqr), 3),
        "min": round(float(values.min()), 3),
        "max": round(float(values.max()), 3),
        "iqr_lower": round(float(lower), 3),
        "iqr_upper": round(float(upper), 3),
        "n_outliers": n_outliers,
        "outlier_pct_of_nonmissing": outlier_pct_of_nonmissing,
        "outlier_pct_of_all_rows": outlier_pct_of_all_rows,
        "skewness": round(skewness, 3) if pd.notna(skewness) else None,
        "transformation_review_flag": bool(pd.notna(skewness) and abs(skewness) > 1.5),
        "evaluability": "evaluated" if pd.notna(skewness) else "evaluated (skewness needs N>=3)",
    })

if _c7_recon_errors:
    raise RuntimeError("C7 reconciliation FAILED: " + "; ".join(_c7_recon_errors))

outlier_df = pd.DataFrame(outlier_rows)
if len(outlier_df):
    outlier_df = outlier_df.sort_values(
        "outlier_pct_of_nonmissing", ascending=False, na_position="last"
    ).reset_index(drop=True)

_evald_c7 = outlier_df[outlier_df["N_nonmissing"] > 0] if len(outlier_df) else outlier_df
_pool_min_n = int(_evald_c7["N_nonmissing"].min()) if len(_evald_c7) else 0
_pool_max_n = int(_evald_c7["N_nonmissing"].max()) if len(_evald_c7) else 0

print("C7 -- Outlier recheck: STATISTICAL IQR 1.5x extreme-value flags (target-blind).")
print(f"Numeric variables in the baseline staged analysis universe (pre-screen): "
      f"{len(_numeric_analysis_vars)}")
print(f"N_nonmissing across evaluated numeric variables: min={_pool_min_n}, max={_pool_max_n} "
      f"(of {_N_ROWS_C7} rows). A variable with a materially smaller N_nonmissing has a less "
      "stable IQR outlier rate -- read it descriptively (no evaluability/exclusion threshold "
      "is applied).")
print("Outlier rate = n_outliers / N_nonmissing * 100  (outlier_pct_of_nonmissing) -- the "
      "non-missing observations eligible for the IQR calculation, NOT the full cohort. "
      "outlier_pct_of_all_rows is whole-cohort context only.")
print()
print(outlier_df.to_string(index=False))
print()
print("C7 reconciliation PASSED: N_nonmissing + missing_n == cohort N and "
      "0 <= n_outliers <= N_nonmissing for every numeric variable.")
_not_eval_c7 = outlier_df[outlier_df["N_nonmissing"] == 0] if len(outlier_df) else outlier_df
if len(_not_eval_c7):
    print(f"\\n{len(_not_eval_c7)} numeric variable(s) marked 'all_missing / not_evaluable' -- "
          f"NOT evaluated for outliers and NOT excluded (eligibility is decided in C12): "
          f"{_not_eval_c7['variable'].tolist()}")
print()
print("No value was removed, capped, winsorized, or transformed. An IQR 1.5x flag is a "
      "statistical-extremeness signal only -- NOT a data error. C7 does NOT classify a flagged "
      "value clinically: no plausible-range registry exists in EDA C, and the plausibility of "
      "the known extreme records was already reviewed upstream, target-blind, using the "
      "preprocessing review exports -- C7 performs descriptive target-blind IQR / skewness "
      "diagnostics only and does not re-adjudicate them. transformation_review_flag "
      "(|skewness| > 1.5) is a descriptive audit signal only -- it is not a log-transform "
      "decision, never overrides a model-entry contract (e.g. transform_source_only), and has "
      "zero effect on the C14 transformation_plan, which is derived from physical_variable_type "
      "instead.")
print()
print("Before/after-cleaning comparison note: EDA A2's A2.11 (a2_predictor_readiness, "
      "pre-cleaning) used the identical IQR 1.5x methodology on the same underlying numeric "
      "predictors before Data Cleaning B ran. A2 does not persist its outlier table to a file "
      "this notebook can load, so a mechanical row-for-row diff is not available here -- but "
      "the method is unchanged, so any material shift in flagged-value counts reflects Data "
      "Cleaning B's deterministic cleaning / representation changes. Data Cleaning B removes "
      "no analytical row and fits no learned / full-cohort imputation of any kind; learned "
      "imputation is deferred to modeling and fitted inside training folds only. See A2.11 in "
      "the EDA A2 notebook for the pre-cleaning comparison.")
""")


# ── Section C7b ────────────────────────────────────────────────────────────────
SC7B_HEADER = md("eda-c-s07b-header", """
## Section C7b — Three Cumulative-Stage Sweetviz Profiling Reports

Internal automated profiling of the **three cumulative prediction-stage
candidate pools** built in C3 (`STAGE_1_COLS` / `STAGE_2_COLS` / `STAGE_3_COLS`):

| Report | Scope |
|--------|-------|
| `eda_c_stage1_sweetviz.html` | Stage 1 (pre-labor) predictors + target |
| `eda_c_stage2_cumulative_sweetviz.html` | Stage 1 + Stage 2 (near-delivery) + target |
| `eda_c_stage3_cumulative_sweetviz.html` | Stage 1 + Stage 2 + Stage 3 (intrapartum) + target |

These are **cumulative**, not Stage-2-only / Stage-3-only. The scope is
`df_analysis` restricted to each cumulative stage — it already excludes IDs,
leakage, source/audit-only, and post-outcome variables by construction (C3).
The target is included for descriptive profiling only.

**Sweetviz's correlations and target associations are descriptive diagnostics
only** — they never hard-filter a predictor (same rule as C11).

Output: `outputs/manual_review/eda_c_sweetviz/` (git-ignored: `*.html` +
`outputs/manual_review/`). The HTML reports must never be committed.

Guarded import: if `sweetviz` is not installed the subsection fails loudly for
profiling only (it does **not** silently substitute another profiler) and the
rest of EDA C continues.
""")

SC7B_SWEETVIZ = code("eda-c-s07b-sweetviz", """
# Opt-in gate (default True -- the canonical EDA C run attempts all three).
RUN_STAGE_SWEETVIZ = True

_SV_OUT_DIR = (_root / "outputs" / "manual_review" / "eda_c_sweetviz") if _root else Path("outputs/manual_review/eda_c_sweetviz")
_sv_status = []

if not RUN_STAGE_SWEETVIZ:
    print("C7b: RUN_STAGE_SWEETVIZ = False -- three cumulative Sweetviz reports were not generated.")
else:
    try:
        import sweetviz as _sv
        _SV_AVAILABLE = True
    except ImportError as _sv_exc:
        _SV_AVAILABLE = False
        print("C7b: sweetviz is not installed -- the three cumulative Sweetviz reports "
              "were NOT generated. Install it (pip install sweetviz) and re-run this "
              "section. No substitute profiler is used. Rest of EDA C is unaffected.")
        print(f"     import error: {_sv_exc}")

    if _SV_AVAILABLE:
        if "notebooks" in _SV_OUT_DIR.resolve().parts:
            raise RuntimeError(
                f"Sweetviz output dir resolved under 'notebooks/' ({_SV_OUT_DIR.resolve()}) "
                "-- working-directory/path-anchoring bug; refusing to write there."
            )
        _SV_OUT_DIR.mkdir(parents=True, exist_ok=True)

        _SV_STAGE_SCOPES = {
            "eda_c_stage1_sweetviz.html": ("Stage 1 (pre-labor)", STAGE_1_COLS),
            "eda_c_stage2_cumulative_sweetviz.html": ("Stage 1 + 2 cumulative (pre-labor + near-delivery)", STAGE_2_COLS),
            "eda_c_stage3_cumulative_sweetviz.html": ("Stage 1 + 2 + 3 cumulative (+ intrapartum)", STAGE_3_COLS),
        }
        _SV_FORBIDDEN = set(ID_COLS) | {"_row_key_delivery_id"}
        # ── Stage universe used by C7b = the PRE-HARD-EXCLUSION cumulative stage
        # pools (STAGE_1/2/3_COLS from C3). This is deliberate: the repeated EDA
        # should PROFILE (and thereby reveal) zero-variance / sparse / extreme
        # issues at each horizon, not silently drop them beforehand. C-level
        # hard exclusion (C12b) happens later and does not touch this universe.
        print(f"C7b stage universe = pre-hard-exclusion cumulative pools: "
              f"Stage1={len(STAGE_1_COLS)}, Stage2_cum={len(STAGE_2_COLS)}, Stage3_cum={len(STAGE_3_COLS)}")
        for _fname, (_label, _cols) in _SV_STAGE_SCOPES.items():
            _scope_cols = [TARGET_COL] + [c for c in _cols if c in df_analysis.columns and c not in _SV_FORBIDDEN]
            _scope_cols = list(dict.fromkeys(_scope_cols))
            _leak = _SV_FORBIDDEN & set(_scope_cols)
            if _leak:
                raise RuntimeError(f"C7b SAFETY: forbidden columns in Sweetviz scope for {_fname}: {sorted(_leak)}")
            _universe_n = len(_scope_cols) - 1  # predictors in the repeated-EDA universe
            # Identify true constants (single observed value, no missing) for
            # transparency -- they STAY in the repeated-EDA universe; only the
            # HTML rendering may omit them if Sweetviz cannot render a constant.
            _constants = [
                c for c in _scope_cols if c != TARGET_COL
                and df_analysis[c].notna().all() and df_analysis[c].nunique(dropna=True) <= 1
            ]
            _out_path = _SV_OUT_DIR / _fname
            _rendered_cols = list(_scope_cols)
            _profiling_omitted = []
            try:
                _report = _sv.analyze(df_analysis[_rendered_cols].copy(), target_feat=TARGET_COL)
                _report.show_html(str(_out_path), open_browser=False, layout="vertical")
            except Exception as _rep_exc:
                # Retry without constants -- rendering-only omission, universe unchanged.
                _rendered_cols = [c for c in _scope_cols if c not in set(_constants)]
                _profiling_omitted = list(_constants)
                try:
                    _report = _sv.analyze(df_analysis[_rendered_cols].copy(), target_feat=TARGET_COL)
                    _report.show_html(str(_out_path), open_browser=False, layout="vertical")
                    print(f"  NOTE: {_fname} -- Sweetviz could not render {len(_constants)} constant "
                          f"column(s) {_constants}; omitted from the HTML ONLY, retained in the "
                          f"repeated-EDA universe. ({_rep_exc})")
                except Exception as _rep_exc2:
                    _sv_status.append((_fname, False, str(_rep_exc2), _universe_n, _profiling_omitted))
                    print(f"  FAILED to generate {_fname}: {_rep_exc2}")
                    continue
            _sv_status.append((_fname, True, _label, _universe_n, _profiling_omitted))
            print(f"  Written: {_out_path}  [{_label}: repeated-EDA universe = target + {_universe_n} predictors"
                  + (f"; {len(_profiling_omitted)} constant(s) omitted from HTML rendering only" if _profiling_omitted else "")
                  + f"; constants present in universe: {_constants or 'none'}]")

        print()
        _n_ok = sum(1 for r in _sv_status if r[1])
        print(f"C7b: {_n_ok}/3 cumulative Sweetviz reports generated in {_SV_OUT_DIR.resolve()}")
        print("     Descriptive profiling only -- Sweetviz associations/correlations do NOT filter predictors.")
        print("     A profiling-only omission (an un-renderable constant) NEVER changes analytical eligibility.")
        print("     HTML is git-ignored (*.html + outputs/manual_review/) -- never commit it.")
        if _n_ok < 3:
            print("     WARNING: not all three reports were produced -- see the per-file messages above.")
""")


EDA_C_PART2_CELLS = [
    SC4_HEADER,
    SC4_DESCRIPTIVE,
    SC4B_HEADER,
    SC4B_PLOTS,
    SC4C_HEADER,
    SC4C_COMPARE,
    SC5_HEADER,
    SC5_MISSINGNESS,
    SC5B_HEADER,
    SC5B_DEEPDIVE,
    SC6_HEADER,
    SC6_SPARSITY,
    SC7_HEADER,
    SC7_OUTLIERS,
    SC7B_HEADER,
    SC7B_SWEETVIZ,
]


if __name__ == "__main__":
    print(f"EDA C Part 2 cells defined: {len(EDA_C_PART2_CELLS)}")

"""Forest-plot figures (Section J).

Pure functions: every plotting function takes a results dataframe (as
produced by ``univariable_analysis.py`` / ``adjusted_endometriosis_analysis.py``)
and returns a ``matplotlib.figure.Figure`` — no file I/O here (see
``publication_exports.py`` for saving). This keeps the plotting code fully
unit-testable against small synthetic dataframes.

A row is plotted as an OR point only when it has a finite OR, finite CI
low/high, AND ``fit_status == OK``. Every other row is classified into
exactly one of two DISTINCT, never-conflated buckets (see
``classify_forest_rows``):

    - ``NO_SINGLE_OR`` — a genuinely fitted, valid association that
      structurally has no single clinically interpretable OR (a categorical
      source-level omnibus row, or a nonlinear-spline source row). This is
      NOT the same thing as "not estimable" and must never be labeled that
      way.
    - ``NOT_ESTIMABLE`` — an actual failed / ``NOT_FITTED`` / separation /
      unsupported fit.

Neither bucket is ever fabricated onto the plot as an OR point; each is
listed in its own separate text sidebar instead.
"""
from __future__ import annotations

import textwrap

import matplotlib

matplotlib.use("Agg")  # headless-safe; publication_exports.py controls actual file writes

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from publication_analysis.publication_display_labels import add_display_label_column

FIT_OK = "OK"

# Three-way forest-row estimability classification (targeted correction #2).
PLOTTABLE_SINGLE_OR = "PLOTTABLE_SINGLE_OR"
NO_SINGLE_OR = "NO_SINGLE_OR"
NOT_ESTIMABLE = "NOT_ESTIMABLE"

MAX_ROWS_PER_FOREST_PLOT = 15

# --- Layout-only constants (presentation, never affects classification/OR/CI) ---
Y_LABEL_WRAP_WIDTH = 44  # characters per line before a y-axis label wraps
SIDEBAR_WRAP_WIDTH = 105  # characters per line before a sidebar note wraps
SIDEBAR_LINE_HEIGHT_IN = 0.17  # inches per wrapped sidebar text line
SIDEBAR_BLOCK_GAP_IN = 0.08  # extra inches between sidebar blocks
XLABEL_RESERVE_IN = 0.55  # inches reserved below the axes for the x-axis label/ticks
TOP_MARGIN_IN = 0.35  # inches reserved above the axes (more if a title is present)
TITLE_RESERVE_IN = 0.35
FIG_WIDTH_MIN_IN = 8.0
FIG_WIDTH_MAX_IN = 14.0
LEFT_MARGIN_CHAR_WIDTH_IN = 0.075  # approx inches per character of the longest y-tick line


def _wrap_text(label: object, width: int) -> str:
    """Wrap ``label`` onto multiple lines at ``width`` characters — display
    only, never alters the underlying value."""
    text = str(label)
    wrapped = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    return "\n".join(wrapped) if wrapped else text


def _wrapped_line_count(text: str) -> int:
    return text.count("\n") + 1


def _longest_line_len(text: str) -> int:
    return max((len(line) for line in text.split("\n")), default=0)


def _configure_readable_log_xaxis(ax) -> None:
    """Replace matplotlib's default log-scale tick behavior with a small,
    fixed set of plain-decimal, non-overlapping tick labels (targeted
    readability correction).

    matplotlib's default log-scale locator auto-generates many closely
    spaced major/minor ticks whenever the plotted range does not span a full
    decade (e.g. a narrow CI such as AGE's ~1.0-1.16), producing an
    illegible cluster of overlapping "1.02x10^0 1.04x10^0 ..." labels. This
    function never changes the axis scale, the x-limits, or any plotted
    OR/CI value -- it only chooses which log-scale grid lines carry a
    visible label, and formats those labels as plain decimals (``1.1``, not
    ``1.1x10^0``).
    """
    ax.xaxis.set_minor_locator(mticker.NullLocator())
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())

    xmin, xmax = ax.get_xlim()
    if not (np.isfinite(xmin) and np.isfinite(xmax)) or xmin <= 0 or xmax <= xmin:
        return

    # "Nice" 1-2-5 tick candidates across several decades; keep only those
    # that fall inside the actual plotted range.
    candidates = sorted(
        {mult * (10.0 ** exp) for exp in range(-4, 5) for mult in (1, 2, 5)}
    )
    ticks = [v for v in candidates if xmin <= v <= xmax]

    if len(ticks) < 2:
        # Range narrower than one 1-2-5 step (e.g. AGE's ~1.0-1.16): fall
        # back to a handful of evenly log-spaced ticks spanning the actual
        # data range instead of matplotlib's dense default.
        ticks = list(np.geomspace(xmin, xmax, num=5))

    # Cap the number of labeled ticks so labels never crowd/overlap even for
    # a wide range with many "nice" candidates inside it.
    max_ticks = 6
    if len(ticks) > max_ticks:
        step = max(1, len(ticks) // max_ticks)
        ticks = ticks[::step]

    # 3 significant figures: enough precision to distinguish adjacent ticks
    # (even in the narrowest fallback range above) without the 6-sig-fig
    # clutter a bare '%g' produces (e.g. "0.992875" -> "0.993").
    ax.xaxis.set_major_locator(mticker.FixedLocator(ticks))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, pos: f"{v:.3g}"))


def group_variables_for_forest(
    variables: list[str], group_map: dict[str, str], max_per_plot: int = MAX_ROWS_PER_FOREST_PLOT
) -> list[list[str]]:
    """Split a long variable list into logically-grouped chunks (by domain), each capped in size.

    Never compresses more than ``max_per_plot`` variables into a single
    forest plot; groups sharing a domain are kept together where they fit.
    """
    by_group: dict[str, list[str]] = {}
    for variable in variables:
        by_group.setdefault(group_map.get(variable, "other"), []).append(variable)

    chunks: list[list[str]] = []
    for _, members in sorted(by_group.items()):
        for start in range(0, len(members), max_per_plot):
            chunks.append(members[start : start + max_per_plot])
    return chunks


def _is_plottable_or_row(
    results_df: pd.DataFrame, or_col: str, ci_low_col: str, ci_high_col: str, fit_status_col: str,
) -> pd.Series:
    """A row is a genuine, plottable single-OR point only when it has a
    finite OR, finite CI low/high, AND ``fit_status == OK`` — never a row
    with ``fit_status == OK`` but a null OR (a categorical source-level
    omnibus row, a nonlinear-spline source row, or any other row whose
    effect has no legitimate single-OR interpretation)."""
    fit_ok = results_df[fit_status_col] == FIT_OK
    or_numeric = pd.to_numeric(results_df[or_col], errors="coerce")
    ci_low_numeric = pd.to_numeric(results_df[ci_low_col], errors="coerce")
    ci_high_numeric = pd.to_numeric(results_df[ci_high_col], errors="coerce")
    finite = (
        np.isfinite(or_numeric.astype(float))
        & np.isfinite(ci_low_numeric.astype(float))
        & np.isfinite(ci_high_numeric.astype(float))
    )
    return fit_ok & finite


def _is_omnibus_or_nonlinear_row(row: pd.Series) -> bool:
    """True for a row that has no legitimate single-OR interpretation BY
    CONSTRUCTION — a categorical source-level omnibus row or a
    nonlinear-spline source row — independent of whether its underlying fit
    happened to succeed. Detected structurally (never by predictor name):

    - ``effect_representation == 'nonlinear_spline'`` (set by
      ``univariable_analysis.run_univariable_master`` for a
      ``NONLINEAR_FORM_APPROVED`` source row);
    - ``support_status == 'SEE_LEVEL_SUPPORT'`` (set for every categorical
      source row, since support is inherently level-specific there — see
      ``univariable_analysis.SUPPORT_SEE_LEVEL_SUPPORT``);
    - an adjusted-analysis source row whose ``comparison`` field names an
      "omnibus" test (``adjusted_endometriosis_analysis.py``'s categorical
      source rows use the literal comparison string "categorical
      source-level omnibus (cluster-robust Wald)").
    """
    if row.get("effect_representation") == "nonlinear_spline":
        return True
    if row.get("support_status") == "SEE_LEVEL_SUPPORT":
        return True
    comparison = row.get("comparison")
    if isinstance(comparison, str) and "omnibus" in comparison:
        return True
    return False


def group_has_plottable_or_row(
    results_df: pd.DataFrame,
    or_col: str = "odds_ratio",
    ci_low_col: str = "ci_low",
    ci_high_col: str = "ci_high",
    fit_status_col: str = "fit_status",
) -> bool:
    """True iff at least one row in ``results_df`` is a genuine, plottable
    single-OR point (finite OR + finite CI + ``fit_status == OK``) -- used by
    the notebook to decide whether to generate/save/display a forest-plot
    figure for a given domain group at all, or instead print a concise text
    message (see ``describe_non_plottable_forest_group``). This is a DISPLAY
    routing decision only: it never drops, filters, or alters any underlying
    table row -- ``univariable_master`` / the exported CSVs are unaffected
    regardless of which branch the notebook takes.
    """
    if not len(results_df):
        return False
    return bool(_is_plottable_or_row(results_df, or_col, ci_low_col, ci_high_col, fit_status_col).any())


def describe_non_plottable_forest_group(
    results_df: pd.DataFrame,
    label_col: str = "predictor",
    or_col: str = "odds_ratio",
    ci_low_col: str = "ci_low",
    ci_high_col: str = "ci_high",
    fit_status_col: str = "fit_status",
) -> str:
    """Concise text describing a forest-plot group with ZERO plottable
    single-OR estimates (see ``group_has_plottable_or_row``) -- printed by
    the notebook in place of generating a large, mostly-empty forest-plot
    image for that group. Mirrors the same NO_SINGLE_OR / NOT_ESTIMABLE
    classification and wording ``plot_forest`` itself uses for its sidebar
    text, so the message is consistent whichever path a group takes. Never
    suppresses or alters any underlying table row -- purely a routing
    decision about which DISPLAY a group gets.
    """
    categories = classify_forest_rows(results_df, or_col, ci_low_col, ci_high_col, fit_status_col)
    no_single_or = results_df[categories == NO_SINGLE_OR]
    non_estimable = results_df[categories == NOT_ESTIMABLE]

    parts = []
    if len(no_single_or):
        names = ", ".join(no_single_or[label_col].astype(str).tolist())
        parts.append(f"no single OR (source-level omnibus/nonlinear result): {names}")
    if len(non_estimable):
        names = ", ".join(non_estimable[label_col].astype(str).tolist())
        parts.append(f"not estimable: {names}")
    detail = "; ".join(parts) if parts else "no predictors in this group"

    return (
        "No plottable single-OR estimate in this group -- see the results table "
        f"above for exact values ({detail})."
    )


def classify_forest_rows(
    results_df: pd.DataFrame,
    or_col: str = "odds_ratio",
    ci_low_col: str = "ci_low",
    ci_high_col: str = "ci_high",
    fit_status_col: str = "fit_status",
) -> pd.Series:
    """Classify every row into exactly one of ``PLOTTABLE_SINGLE_OR`` /
    ``NO_SINGLE_OR`` / ``NOT_ESTIMABLE`` (targeted correction #2).

    - ``PLOTTABLE_SINGLE_OR``: finite OR + finite CI low/high + ``fit_status
      == OK``.
    - ``NO_SINGLE_OR``: ``fit_status == OK`` but the row is a categorical
      source-level omnibus result or a nonlinear-spline source result (see
      ``_is_omnibus_or_nonlinear_row``) — a genuinely estimable, valid
      association with no legitimate single OR by construction. Never
      classified as ``NOT_ESTIMABLE``.
    - ``NOT_ESTIMABLE``: everything else — a failed / ``NOT_FITTED`` /
      separation / unsupported fit, or any other row without a finite OR+CI
      for a reason other than the two structural cases above.
    """
    categories = pd.Series(NOT_ESTIMABLE, index=results_df.index, dtype=object)
    if not len(results_df):
        return categories

    plottable = _is_plottable_or_row(results_df, or_col, ci_low_col, ci_high_col, fit_status_col)
    fit_ok = results_df[fit_status_col] == FIT_OK
    no_single_or = (~plottable) & fit_ok & results_df.apply(_is_omnibus_or_nonlinear_row, axis=1)

    categories[plottable] = PLOTTABLE_SINGLE_OR
    categories[no_single_or] = NO_SINGLE_OR
    return categories


def prepare_forest_rows(
    master_df: pd.DataFrame,
    label_col: str = "predictor",
    row_type_col: str = "row_type",
    level_col: str = "level",
    reference_level_col: str = "reference_level",
    model_variant_col: str | None = None,
    required_model_variant: str | None = None,
) -> pd.DataFrame:
    """Select rows eligible for forest-plot consideration and build a clear
    display label for categorical level-vs-reference rows.

    - If ``model_variant_col`` / ``required_model_variant`` are given,
      restricts to that ONE model variant (e.g. PRIMARY-only for the adjusted
      endometriosis forest) — a sensitivity-variant row is never silently
      mixed onto the same plot as the main estimate. If ``model_variant_col``
      is given but that column does not exist in ``master_df``, this raises
      ``KeyError`` rather than silently skipping the filter (targeted
      correction #7B) — a caller asking for a single model variant must never
      end up with every variant mixed together because the column name was
      wrong.
    - Restricts to ``row_type in {'source', 'level'}`` (defensive — both
      ``univariable_master`` and the adjusted master only ever contain
      these two).
    - A ``row_type == 'level'`` row's label becomes
      ``"{predictor}: {level} vs {reference_level}"``; a ``row_type ==
      'source'`` row keeps its bare label.

    Does NOT itself decide estimability/plottability — ``plot_forest`` calls
    ``classify_forest_rows`` to split rows into ``PLOTTABLE_SINGLE_OR`` /
    ``NO_SINGLE_OR`` / ``NOT_ESTIMABLE`` (never fabricates a single-OR point
    for a categorical-omnibus, nonlinear-spline, descriptive-only, or
    otherwise non-estimable row); such rows pass through here unchanged and
    are listed in the plot's own separate sidebars rather than dropped
    silently or mislabeled.
    """
    df = master_df.copy()
    if model_variant_col:
        if model_variant_col not in df.columns:
            raise KeyError(
                f"prepare_forest_rows: model_variant_col={model_variant_col!r} was supplied "
                f"but is not a column of the given dataframe (columns: {list(master_df.columns)}) "
                "— refusing to silently skip the model-variant filter."
            )
        if required_model_variant:
            df = df[df[model_variant_col] == required_model_variant]
    if row_type_col in df.columns:
        df = df[df[row_type_col].isin(["source", "level"])]

    df = df.reset_index(drop=True)
    if row_type_col in df.columns and level_col in df.columns and reference_level_col in df.columns:
        is_level = df[row_type_col] == "level"
        if is_level.any():
            df.loc[is_level, label_col] = (
                df.loc[is_level, label_col].astype(str)
                + ": "
                + df.loc[is_level, level_col].astype(str)
                + " vs "
                + df.loc[is_level, reference_level_col].astype(str)
            )
    return df


def plot_forest(
    results_df: pd.DataFrame,
    label_col: str = "predictor",
    or_col: str = "odds_ratio",
    ci_low_col: str = "ci_low",
    ci_high_col: str = "ci_high",
    fit_status_col: str = "fit_status",
    title: str = "",
    log_scale: bool = True,
):
    """Build one forest plot.

    A row is plotted as an OR point only when it has a finite OR, finite CI
    low/high, AND ``fit_status == OK``. Every other row is classified by
    ``classify_forest_rows`` into ``NO_SINGLE_OR`` (a genuinely fitted,
    valid categorical-omnibus or nonlinear-spline association with no
    legitimate single OR by construction) or ``NOT_ESTIMABLE`` (an actual
    failed / ``NOT_FITTED`` / separation / unsupported fit) — these are
    reported in two SEPARATE text sidebars; neither is ever fabricated onto
    the plot, and a ``NO_SINGLE_OR`` row is never labeled "not estimable".
    """
    categories = classify_forest_rows(results_df, or_col, ci_low_col, ci_high_col, fit_status_col)
    estimable = results_df[categories == PLOTTABLE_SINGLE_OR].copy()
    no_single_or = results_df[categories == NO_SINGLE_OR].copy()
    non_estimable = results_df[categories == NOT_ESTIMABLE].copy()

    n_rows = max(len(estimable), 1)

    # --- y-axis labels: wrapped for readability, never altering the value ---
    wrapped_labels = [_wrap_text(l, Y_LABEL_WRAP_WIDTH) for l in estimable[label_col]] if len(estimable) else []
    label_line_counts = [_wrapped_line_count(t) for t in wrapped_labels] or [1]
    longest_label_line = max((_longest_line_len(t) for t in wrapped_labels), default=0)
    # Variable-height row bands (in "line units"): matplotlib places tick
    # labels at whatever y-position we give them, so a row whose label wraps
    # onto e.g. 4 lines gets a proportionally taller band than a 1-line row
    # -- giving every row the SAME uniform spacing (as a plain integer
    # np.arange would) is what let adjacent multi-line labels visually
    # collide with their neighbors regardless of total figure height.
    label_units = [max(1, n) for n in label_line_counts]
    total_label_units = sum(label_units) if label_units else 1

    # --- sidebar blocks (NO_SINGLE_OR / NOT_ESTIMABLE): wrapped, one clearly
    # labeled block per category, always placed below the plotted axes so
    # they can never overlap the x-axis, plotted points, or y-tick labels.
    sidebar_blocks: list[str] = []
    if len(no_single_or):
        names = ", ".join(no_single_or[label_col].astype(str).tolist())
        sidebar_blocks.append(
            _wrap_text(f"No single OR — source-level omnibus/nonlinear result; see table: {names}",
                       SIDEBAR_WRAP_WIDTH)
        )
    if len(non_estimable):
        names = ", ".join(non_estimable[label_col].astype(str).tolist())
        sidebar_blocks.append(
            _wrap_text(f"Not estimable (excluded from plot, see table): {names}", SIDEBAR_WRAP_WIDTH)
        )
    sidebar_total_lines = sum(_wrapped_line_count(b) for b in sidebar_blocks)
    sidebar_height_in = (
        sidebar_total_lines * SIDEBAR_LINE_HEIGHT_IN + len(sidebar_blocks) * SIDEBAR_BLOCK_GAP_IN
    )

    # --- figure geometry: axes area sized for (possibly multi-line) labels,
    # plus a dedicated, fixed-size footer reserved for the sidebar blocks
    # (never scaled inversely by row count -- that was the original overlap
    # bug: a large plot's sidebar offset shrank toward the x-axis instead of
    # staying clear of it).
    axes_height_in = 0.30 * total_label_units + 0.6
    title_reserve_in = TITLE_RESERVE_IN if title else 0.05
    fig_height = axes_height_in + XLABEL_RESERVE_IN + TOP_MARGIN_IN + title_reserve_in + sidebar_height_in
    fig_width = min(FIG_WIDTH_MAX_IN, max(FIG_WIDTH_MIN_IN, 3.5 + longest_label_line * LEFT_MARGIN_CHAR_WIDTH_IN))

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    if len(estimable):
        # Cumulative, variable-height band positions (top row first), so a
        # multi-line wrapped label gets a taller band than a single-line one
        # -- see label_units above. Bands are contiguous (no gap) and exactly
        # cover [0, total_label_units], each row centered in its own band.
        y_positions = []
        cum_from_top = 0.0
        for u in label_units:
            cum_from_top += u / 2.0
            y_positions.append(total_label_units - cum_from_top)
            cum_from_top += u / 2.0
        y_positions = np.array(y_positions)
        ax.errorbar(
            estimable[or_col],
            y_positions,
            xerr=[
                estimable[or_col] - estimable[ci_low_col],
                estimable[ci_high_col] - estimable[or_col],
            ],
            fmt="o",
            color="#2b4c7e",
            ecolor="#2b4c7e",
            capsize=3,
        )
        ax.set_yticks(y_positions)
        ax.set_yticklabels(wrapped_labels, fontsize=8)
        ax.set_ylim(-0.5, total_label_units + 0.5)  # breathing room above/below the outermost rows
        ax.axvline(1.0, color="grey", linestyle="--", linewidth=1)
        if log_scale:
            ax.set_xscale("log")
            _configure_readable_log_xaxis(ax)
        ax.set_xlabel("Odds ratio (95% CI)" + (" [log scale]" if log_scale else ""))
    else:
        # Final micro-correction #4: "No estimable predictors" was incorrect
        # whenever the frame contains valid NO_SINGLE_OR rows (categorical
        # omnibus / nonlinear spline) -- those ARE estimable, they simply have
        # no single plottable OR point. This message describes the empty
        # PLOTTABLE_SINGLE_OR panel only; NO_SINGLE_OR / NOT_ESTIMABLE rows
        # are still reported in their own separate sidebars below.
        ax.text(0.5, 0.5, "No plottable single-OR estimates in this group", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])

    if title:
        ax.set_title(title)

    # --- fixed-geometry layout: axes occupy the top portion of the figure;
    # a dedicated footer band below is reserved solely for the sidebar text,
    # so the sidebar can never be drawn on top of the x-axis/labels/points
    # regardless of how many rows or sidebar predictors there are.
    bottom_fraction = (XLABEL_RESERVE_IN + sidebar_height_in) / fig_height
    top_fraction = 1.0 - (TOP_MARGIN_IN + title_reserve_in) / fig_height
    left_fraction = min(0.45, max(0.18, (1.0 + longest_label_line * LEFT_MARGIN_CHAR_WIDTH_IN) / fig_width))
    fig.subplots_adjust(left=left_fraction, right=0.97, bottom=bottom_fraction, top=top_fraction)

    line_height_fraction = SIDEBAR_LINE_HEIGHT_IN / fig_height
    block_gap_fraction = SIDEBAR_BLOCK_GAP_IN / fig_height
    # Start just below the reserved x-axis-label band, and go down from there
    # -- entirely below the axes, in figure (not axes) coordinates, so the
    # position is never rescaled by the number of plotted rows.
    cursor_fraction = bottom_fraction - XLABEL_RESERVE_IN / fig_height
    for block in sidebar_blocks:
        fig.text(
            0.02,
            cursor_fraction,
            block,
            fontsize=7,
            transform=fig.transFigure,
            va="top",
        )
        n_lines = _wrapped_line_count(block)
        cursor_fraction -= n_lines * line_height_fraction + block_gap_fraction

    return fig


def plot_endometriosis_forest(
    results_df: pd.DataFrame,
    or_col: str = "odds_ratio",
    ci_low_col: str = "ci_low",
    ci_high_col: str = "ci_high",
    fit_status_col: str = "fit_status",
    title: str = "Endometriosis-specific predictors — crude association",
):
    """Crude univariable forest for the endometriosis family.

    ``results_df`` is expected to be a canonical univariable result frame
    (the canonical ``univariable_master`` filtered to the 35 endometriosis-
    family predictors — see ``publication_display_labels``/Section J's crude
    forest cell; NOT the Section E ``endometriosis_findings`` table, which is
    intentionally source-level only and would omit legitimate categorical
    level-vs-reference OR points) — NOT a binary-only re-fit. Categorical
    source-level omnibus rows and nonlinear-spline source rows are never
    given a fabricated OR point (see ``plot_forest``); a categorical LEVEL
    row is relabeled "{clinical predictor label}: {level} vs {reference_level}"
    when the relevant columns are present. Uses the clinical display-label
    layer (``publication_display_labels.py``) for the plotted label while
    leaving the technical ``predictor`` column of ``results_df`` untouched —
    a predictor without a documented clinical label falls back to its bare
    technical name (never a fabricated label).
    """
    labeled = add_display_label_column(
        results_df, predictor_col="predictor", label_col="predictor_display_label"
    )
    prepared = prepare_forest_rows(labeled, label_col="predictor_display_label")
    return plot_forest(
        prepared,
        label_col="predictor_display_label",
        or_col=or_col,
        ci_low_col=ci_low_col,
        ci_high_col=ci_high_col,
        fit_status_col=fit_status_col,
        title=title,
    )


def plot_endometriosis_adjusted_forest(
    adjusted_master_df: pd.DataFrame,
    title: str = "Endometriosis-specific predictors — adjusted association (PRIMARY)",
):
    """Adjusted endometriosis forest — PRIMARY model variant ONLY.

    ``adjusted_master_df`` is the full adjusted master table (both
    ``PRIMARY``/``SENSITIVITY_IVF`` variants, both source/level row types —
    see ``adjusted_endometriosis_analysis.run_adjusted_analysis_for_family``).
    This function restricts to ``model_variant == PRIMARY`` internally — the
    SENSITIVITY_IVF variant is never mixed onto the same plot as the main
    adjusted estimate. Categorical source-level omnibus rows and Class C
    (``NOT_FITTED``) rows are never given a fabricated OR point; categorical
    LEVEL rows are relabeled "{clinical exposure label}: {level} vs
    {reference_level}". Uses the clinical display-label layer
    (``publication_display_labels.py``) for the plotted label while leaving
    the technical ``exposure`` column untouched — an exposure without a
    documented clinical label falls back to its bare technical name.
    """
    from publication_analysis.adjusted_endometriosis_analysis import (
        MODEL_VARIANT_PRIMARY,
    )

    labeled = add_display_label_column(
        adjusted_master_df, predictor_col="exposure", label_col="exposure_display_label"
    )
    prepared = prepare_forest_rows(
        labeled,
        label_col="exposure_display_label",
        model_variant_col="model_variant",
        required_model_variant=MODEL_VARIANT_PRIMARY,
    )
    renamed = prepared.rename(
        columns={
            "adjusted_or": "odds_ratio",
            "adjusted_ci_low": "ci_low",
            "adjusted_ci_high": "ci_high",
        }
    )
    return plot_forest(renamed, label_col="exposure_display_label", title=title)


def plot_incremental_value_by_stage(by_stage: dict):
    """Stage 1/2/3 Arm A vs. Arm B PR-AUC comparison. Only meaningful once released (Section H)."""
    stages = sorted(by_stage.keys())
    arm_a = [by_stage[s].get("arm_a", {}).get("pr_auc") for s in stages]
    arm_b = [by_stage[s].get("arm_b", {}).get("pr_auc") for s in stages]

    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.arange(len(stages))
    width = 0.35
    ax.bar(x - width / 2, arm_a, width, label="Arm A (non-endometriosis only)")
    ax.bar(x + width / 2, arm_b, width, label="Arm B (full pool)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Stage {s}" for s in stages])
    ax.set_ylabel("PR-AUC")
    ax.set_title("Incremental predictive value by stage")
    ax.legend()
    fig.tight_layout()
    return fig

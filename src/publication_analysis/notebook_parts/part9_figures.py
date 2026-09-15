"""Publication notebook — Part 9: figures (Section I)."""
from publication_analysis.notebook_parts._cell_helpers import code, md

PART9_CELLS = [
    md(
        "pub-s19-header",
        """
---
## Section I — Figures

Forest plots with a reference line at OR = 1, a logarithmic OR axis, and
visible confidence intervals. A row is plotted as an OR point only when it
has a finite OR, finite CI, AND `fit_status == OK`. Every other row is
classified into exactly one of two distinct sidebars (never conflated) via
`figures.classify_forest_rows`: `NO_SINGLE_OR` — a categorical source-level
omnibus row or a nonlinear-spline source row, a genuinely estimable
association with no legitimate single OR by construction, reported as "No
single OR — source-level omnibus/nonlinear result; see table" — and
`NOT_ESTIMABLE` — a Class C (`NOT_FITTED`) exposure or any other genuinely
failed/unsupported fit. Neither is ever given a fabricated point. Categorical
LEVEL rows are labeled `"{clinical predictor label}: {level} vs
{reference_level}"` using the clinical display-label layer
(`publication_display_labels.py`; the technical predictor/exposure column is
kept alongside, untouched, for traceability). Long predictor lists are split
into logically grouped figures (by domain) rather than compressed into one
unreadable plot. Every figure is saved to disk first, then re-displayed
inline via `exports.display_saved_figure` (`IPython.display.Image` on the
saved PNG bytes) — backend-independent, so a headless plotting backend never
silently degrades the notebook's inline output to a text-only `Figure(...)`
repr.
""",
    ),
    code(
        "pub-s19-imports",
        """
from publication_analysis import publication_figures as figures
from publication_analysis import publication_display_labels
""",
    ),
    code(
        "pub-s19-univariable-forests",
        """
domain_map = dict(zip(features_df["variable"], features_df["domain"]))
plot_ready_predictors = sorted(
    univariable_master.loc[univariable_master["row_type"] == "source", "predictor"]
)
chunks = figures.group_variables_for_forest(plot_ready_predictors, domain_map)

# Clinical display labels (Section I correction #4): the technical
# `predictor` column is kept untouched (used for grouping/traceability
# below); a separate `predictor_display_label` column drives what is
# actually shown on the figure. A predictor without a documented clinical
# label falls back to its bare technical name (never a fabricated label).
univariable_master_labeled = publication_display_labels.add_display_label_column(
    univariable_master, predictor_col="predictor", label_col="predictor_display_label"
)
univariable_forest_rows = figures.prepare_forest_rows(
    univariable_master_labeled, label_col="predictor_display_label"
)

univariable_forest_figures = []
for i, chunk in enumerate(chunks):
    # `predictor` (technical, untouched by prepare_forest_rows since the
    # display label lives in a separate column) groups level rows with their
    # source predictor correctly, without needing to parse the display label.
    chunk_df = univariable_forest_rows[univariable_forest_rows["predictor"].isin(chunk)]
    # Readability correction: a domain group with ZERO plottable single-OR
    # estimates (e.g. every member is NOT_FITTED/non-estimable, or a lone
    # categorical-omnibus/nonlinear-spline result) no longer generates a
    # large, mostly-empty forest-plot image -- it prints a concise directive
    # message instead. This is a DISPLAY decision only: no univariable_master
    # / exported table row is ever dropped or altered by this branch.
    if figures.group_has_plottable_or_row(chunk_df):
        fig = figures.plot_forest(
            chunk_df,
            label_col="predictor_display_label",
            title=f"Univariable associations — group {i + 1}",
        )
        saved_path = exports.save_figure(fig, f"{exports.FOREST_UNIVARIABLE_PREFIX}group_{i + 1}.png")
        univariable_forest_figures.append(fig)
        exports.display_saved_figure(saved_path)
    else:
        print(
            f"Univariable associations — group {i + 1}: "
            + figures.describe_non_plottable_forest_group(chunk_df, label_col="predictor_display_label")
        )
""",
    ),
    code(
        "pub-s19-endometriosis-crude-forest",
        """
# Built from the canonical univariable_master (Section D), filtered to the
# 35 endometriosis-family predictors -- NOT from `endometriosis_findings`
# (Section E), which is intentionally source-level only and would omit
# legitimate categorical level-vs-reference OR points (Section I correction
# #3). No re-fit here: this is a read/filter/present operation only, and
# preserves source rows (incl. NO_SINGLE_OR omnibus/nonlinear rows) as well
# as categorical level rows.
endometriosis_family_master_rows = univariable_master[
    univariable_master["predictor"].isin(endo_family_names)
].copy()

fig_crude = figures.plot_endometriosis_forest(endometriosis_family_master_rows)
saved_path_crude = exports.save_figure(fig_crude, exports.FOREST_ENDOMETRIOSIS_CRUDE_PNG)
exports.display_saved_figure(saved_path_crude)
""",
    ),
    code(
        "pub-s19-endometriosis-adjusted-forest",
        """
fig_adjusted = figures.plot_endometriosis_adjusted_forest(adjusted_master)
saved_path_adjusted = exports.save_figure(fig_adjusted, exports.FOREST_ENDOMETRIOSIS_ADJUSTED_PNG)
exports.display_saved_figure(saved_path_adjusted)
""",
    ),
]

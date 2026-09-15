"""Publication notebook — Part 8: final predictive-model context (current +
historical), including the already-generated final PR #3 publication outputs.

Final micro-correction #6: the dedicated PENDING Arm-A/B incremental-value
section was removed from this notebook (no such artifact exists); the
utility loader remains available in ``predictive_context_loaders.py`` for
historical/internal use, but this notebook never displays a placeholder
PENDING section or a skipped figure for it. Decision 99's completed
exploratory negative conclusion is retained, read-only, in this part's
Compact Ridge context cell.
"""
from publication_analysis.notebook_parts._cell_helpers import code, md

PART8_CELLS = [
    md(
        "pub-s17-header",
        """
---
## Section H — Final Predictive-Model Context

**Predictive model results, loaded read-only from already-persisted
artifacts — never re-fit or rerun here.** Kept clearly separate from the
inferential/association results in Sections D–G above: this section
describes how well a model predicts out-of-sample; Sections D–G describe
which predictors are *associated* with the outcome. `CLAUDE.md` is not the
numerical authority for these metrics — the persisted artifacts under
`outputs/final_modeling/` are.

**Current final predictive architecture: Compact Ridge (Decision 99).** The
original Stage 3 / lasso_logistic Final-D run is retained below only as
explicitly-labeled **HISTORICAL / SUPERSEDED** context for methodological
chronology — it is never described as the current winner. Compact Ridge is
internally validated only (50 repeated-grouped-CV folds on the same
development cohort) — it is **not** externally validated.

`compact_ridge_context` was already loaded read-only in Section E above
(needed there for `current_compact_ridge_member`) — reused here, not
reloaded, so this notebook reads the locked validation manifest exactly
once per run.

**No dedicated Arm-A/B (non-endometriosis-vs-full-pool) incremental-value
artifact exists**, and this notebook does not display a placeholder section
for one. This does not mean the question was never examined: the completed
exploratory model-improvement process behind Decision 99 (four analyses on
`exploratory/overnight-model-improvement`) already reached a documented
negative conclusion — no stable incremental predictive value from any
endometriosis-specific predictor, individually or aggregated — surfaced
read-only below via `compact_ridge_context.endometriosis_forced_predictor_note`.
That conclusion is **exploratory model-development context**, clearly
distinct from the association-inference evidence in Sections D–G above.
""",
    ),
    code(
        "pub-s17-load-compact-ridge",
        """
print(f"Compact Ridge context status: {compact_ridge_context.status}")
if compact_ridge_context.status == pred_context.STATUS_COMPLETE:
    print(f"Architecture: {compact_ridge_context.architecture_name}")
    print(f"Frozen predictors ({len(compact_ridge_context.frozen_predictors)}): "
          f"{compact_ridge_context.frozen_predictors}")
    print(f"N = {compact_ridge_context.n_rows}, "
          f"outer CV = {compact_ridge_context.outer_repeats} x {compact_ridge_context.outer_folds} "
          f"({compact_ridge_context.n_folds_ok}/{compact_ridge_context.n_folds_total} folds OK)")
    print(f"PR-AUC:  {compact_ridge_context.pr_auc:.3f}")
    print(f"AUROC:   {compact_ridge_context.auroc:.3f}")
    print(f"Brier:   {compact_ridge_context.brier:.3f}")
    print(f"Calibration intercept / slope: {compact_ridge_context.calibration_intercept:.2f} / "
          f"{compact_ridge_context.calibration_slope:.2f}")
    print(f"Final full-cohort refit available: {compact_ridge_context.final_refit_available}")
    if compact_ridge_context.final_refit_available:
        print(f"  chosen C = {compact_ridge_context.final_refit_chosen_C}, "
              f"intercept = {compact_ridge_context.final_refit_intercept:.3f}")
        print(f"  n_rows_used = {compact_ridge_context.final_refit_n_rows_used}, "
              f"n_rows_expected = {compact_ridge_context.final_refit_n_rows_expected}, "
              f"converged = {compact_ridge_context.final_refit_converged}")
        print(f"  endometriosis predictor forced into final architecture: "
              f"{compact_ridge_context.endometriosis_forced_predictor}")
        print(f"  {compact_ridge_context.endometriosis_forced_predictor_note}")
else:
    print(compact_ridge_context.message)
""",
    ),
    md(
        "pub-s17b-final-d-historical-header",
        """
### HISTORICAL / SUPERSEDED — original Final-D Stage 3 / lasso_logistic run

Superseded by Decision 99. Retained for methodological chronology only —
never the current winner. This run had no holdout, no threshold, and
inadequate calibration; `final_refit` was never run for it.

`final_d_context` below carries ONLY what `run_manifest.json` itself
recorded for this one original run (pathway/family/stage/PR-AUC) — it is
never cross-read from any other artifact (final micro-correction #7). The
historical Stage 3/LASSO comparator's full metric set (AUROC, Brier,
calibration included), fitted for direct comparability under the frozen-fold
Compact Ridge validation protocol, is shown separately and correctly
attributed in the version-controlled PR #3 performance table below.
""",
    ),
    code(
        "pub-s17b-load-final-d",
        """
final_d_context = pred_context.load_final_d_predictive_context()
print(f"Final-D context status: {final_d_context.status} (label: {final_d_context.label})")
if final_d_context.status == pred_context.STATUS_COMPLETE:
    print(f"Winning pathway: {final_d_context.winning_pathway}")
    print(f"Original recorded PR-AUC: {final_d_context.pr_auc}")
    if final_d_context.message:
        print(final_d_context.message)
else:
    print(final_d_context.message)
""",
    ),
    md(
        "pub-s17c-final-outputs-header",
        """
### Already-generated final publication-facing outputs (PR #3)

The tables and figures below are the **already-generated, accepted**
publication-facing Compact Ridge outputs under
`outputs/results/compact_ridge_final/` (produced by
`analysis/reports/compact_ridge_final_outputs.py` — a results/visualization
task only: no model fitting, refitting, hyperparameter search, or new
statistical inference). They are **displayed read-only here, never
regenerated by this notebook**.

This gives two independent views of the same locked architecture: the
numeric `compact_ridge_context` printed above is loaded directly from the
locked Decision 99 manifests (validation/provenance); the table/figures below
are the separately-produced, presentation-ready PR #3 artifacts. Neither is
recomputed by this cell.

**If Ridge coefficients are shown below, they are penalized coefficients on
the modeling/encoded scale — NOT conventional adjusted odds ratios** (see
`outputs/results/compact_ridge_final/README.md`).
""",
    ),
    code(
        "pub-s17c-final-outputs-performance-table",
        """
from IPython.display import Markdown

compact_ridge_final_dir = pred_context.REPO_ROOT / "outputs" / "results" / "compact_ridge_final"

# Final micro-correction #3: the version-controlled `.md` table is the
# publication display AUTHORITY -- the `.csv` counterpart is gitignored/
# local-only (see .gitignore) and must never be required for this cell to
# show the accepted PR #3 table. Displayed read-only; never regenerated.
final_performance_table_md_path = compact_ridge_final_dir / "tables" / "table_final_model_performance.md"
if not final_performance_table_md_path.exists():
    raise FileNotFoundError(
        f"Version-controlled final model performance table not found: "
        f"{final_performance_table_md_path}. This file is committed to the repository "
        "(see outputs/results/compact_ridge_final/README.md) and must be present."
    )
print(f"Final model performance table (PR #3, version-controlled, read-only): "
      f"{final_performance_table_md_path}")
display(Markdown(final_performance_table_md_path.read_text(encoding="utf-8")))
""",
    ),
    code(
        "pub-s17c-final-outputs-coefficients-table",
        """
final_coefficients_table_md_path = compact_ridge_final_dir / "tables" / "table_final_ridge_coefficients.md"
if not final_coefficients_table_md_path.exists():
    raise FileNotFoundError(
        f"Version-controlled final Ridge coefficients table not found: "
        f"{final_coefficients_table_md_path}. This file is committed to the repository "
        "(see outputs/results/compact_ridge_final/README.md) and must be present."
    )
print(
    "NOTE: these are penalized Compact Ridge coefficients on the modeling/encoded "
    "scale -- NOT conventional adjusted odds ratios "
    "(see outputs/results/compact_ridge_final/README.md)."
)
display(Markdown(final_coefficients_table_md_path.read_text(encoding="utf-8")))

# OPTIONAL internal cross-check only (never the display authority, never
# required): a local-only, gitignored .csv counterpart may or may not exist
# on this machine -- its absence must never make the table above disappear.
_performance_csv_path = compact_ridge_final_dir / "tables" / "table_final_model_performance.csv"
_coefficients_csv_path = compact_ridge_final_dir / "tables" / "table_final_ridge_coefficients.csv"
if _performance_csv_path.exists() and _coefficients_csv_path.exists():
    print(f"(optional local cross-check CSVs also present: {_performance_csv_path.name}, "
          f"{_coefficients_csv_path.name})")
""",
    ),
    code(
        "pub-s17c-final-outputs-figures",
        """
from IPython.display import Image

for figure_name in (
    "figure_compact_ridge_precision_recall.png",
    "figure_compact_ridge_roc.png",
    "figure_compact_ridge_calibration.png",
):
    figure_path = compact_ridge_final_dir / "figures" / figure_name
    if not figure_path.exists():
        raise FileNotFoundError(
            f"Version-controlled final Compact Ridge figure not found: {figure_path}."
        )
    display(Image(filename=str(figure_path)))
""",
    ),
    md(
        "pub-s17d-adjusted-or-header",
        """
### Secondary clinically interpretable adjusted associations

The table and figure below are the already-generated, **accepted** outputs
of a separate, secondary descriptive analysis
(`analysis/reports/final_adjusted_or_analysis.py`) — read-only inputs to
this notebook, never recomputed here. This analysis fits one prespecified
ordinary (unpenalized) maximum-likelihood multivariable logistic regression
using the same six source predictors as the locked Decision 99 Compact
Ridge architecture (`AGE`, `nulliparity`, `S_P_CS`, `BMI_before`,
`derived_hypertension_pih_pet_spectrum`, `induction_any_bin`), to provide
clinically interpretable adjusted odds ratios (ORs) with 95% confidence
intervals in original clinical units.

- These are **ordinary unpenalized adjusted odds ratios** — not the
  penalized Compact Ridge coefficients shown above (which are on a
  standardized/encoded modeling scale and were tuned for predictive
  performance, not unbiased conditional-association estimation).
- They are a **secondary clinical-interpretation analysis**, distinct from
  the exploratory endometriosis-specific adjusted association analysis in
  Section F above (which adjusts one endometriosis exposure at a time for
  `AGE + nulliparity + S_P_CS`). Neither analysis is merged into, or
  replaces, the other.
- They do **not** alter Decision 99 or any reported predictive performance
  (PR-AUC, AUROC, Brier, calibration) — those remain exclusively sourced
  from the locked Ridge validation artifacts above.
""",
    ),
    code(
        "pub-s17d-adjusted-or-table",
        """
adjusted_or_dir = compact_ridge_final_dir / "adjusted_or"

adjusted_or_table_md_path = adjusted_or_dir / "table_adjusted_odds_ratios.md"
if not adjusted_or_table_md_path.exists():
    raise FileNotFoundError(
        f"Accepted six-predictor adjusted-OR table not found: {adjusted_or_table_md_path}. "
        "This file is committed to the repository "
        "(see outputs/results/compact_ridge_final/adjusted_or/README.md) and must be present."
    )
print(f"Adjusted odds ratio table (accepted, version-controlled, read-only): "
      f"{adjusted_or_table_md_path}")
display(Markdown(adjusted_or_table_md_path.read_text(encoding="utf-8")))
""",
    ),
    code(
        "pub-s17d-adjusted-or-figure",
        """
adjusted_or_figure_path = adjusted_or_dir / "figure_adjusted_odds_ratios.png"
if not adjusted_or_figure_path.exists():
    raise FileNotFoundError(
        f"Accepted adjusted-OR forest figure not found: {adjusted_or_figure_path}."
    )
display(Image(filename=str(adjusted_or_figure_path)))
""",
    ),
    code(
        "pub-s17d-adjusted-or-firth-sensitivity",
        """
# Firth (bias-reduced penalized-likelihood) sensitivity analysis, fit on the
# identical design because two hypertension categories are sparse-celled.
# MLE remains the PRIMARY adjusted-OR model above; this cell surfaces only
# the accepted verdict text, never a second forest plot, and is never
# recomputed here.
adjusted_or_readme_path = adjusted_or_dir / "README.md"
if not adjusted_or_readme_path.exists():
    raise FileNotFoundError(f"Accepted adjusted-OR README not found: {adjusted_or_readme_path}.")
_adjusted_or_readme_text = adjusted_or_readme_path.read_text(encoding="utf-8")
_verdict_marker = "Overall sensitivity verdict:"
_verdict_line = next(
    (line for line in _adjusted_or_readme_text.splitlines() if _verdict_marker in line),
    None,
)
if _verdict_line is None:
    raise ValueError(
        f"Could not locate '{_verdict_marker}' in {adjusted_or_readme_path}."
    )
print("Firth sensitivity analysis (identical six-predictor design, sparse-cell trigger):")
print(_verdict_line.strip())
print("MLE remains the primary adjusted-OR model; Firth is sensitivity only — "
      "see table_adjusted_odds_ratios_firth_sensitivity.md for the supplementary table.")

adjusted_or_firth_table_md_path = adjusted_or_dir / "table_adjusted_odds_ratios_firth_sensitivity.md"
if adjusted_or_firth_table_md_path.exists():
    display(Markdown(adjusted_or_firth_table_md_path.read_text(encoding="utf-8")))
""",
    ),
]

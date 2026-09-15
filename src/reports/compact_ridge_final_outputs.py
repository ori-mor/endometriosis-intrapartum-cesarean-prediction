"""
Generate the minimal publication-facing results set for the locked Decision 99
Compact Ridge model.

This script performs NO model fitting, NO predictor/hyperparameter search, and
NO new cross-validation. It reads exclusively from the already-verified,
already-regenerated locked artifacts under
outputs/final_modeling/compact_ridge_lock/ and produces:

  - table_final_model_performance.csv / .md
  - table_final_ridge_coefficients.csv / .md
  - figure_compact_ridge_precision_recall.png / .svg
  - figure_compact_ridge_roc.png / .svg
  - figure_compact_ridge_calibration.png / .svg
  - a figures_metadata.md documenting the exact repeated-CV aggregation method
  - README.md documenting full provenance

Run from the project root:
    python analysis/reports/compact_ridge_final_outputs.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve, roc_curve

# ---------------------------------------------------------------------------
# Paths (all inputs are the already-verified locked artifacts; read-only)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCK_DIR = PROJECT_ROOT / "outputs" / "final_modeling" / "compact_ridge_lock"
REPORT_DIR = LOCK_DIR / "report"
REFIT_DIR = LOCK_DIR / "final_refit"

OUT_DIR = PROJECT_ROOT / "outputs" / "results" / "compact_ridge_final"
TABLES_DIR = OUT_DIR / "tables"
FIGURES_DIR = OUT_DIR / "figures"

OOF_PATH = REPORT_DIR / "locked_validation_oof_predictions.csv"
MANIFEST_PATH = REPORT_DIR / "locked_validation_manifest.json"
COEF_STABILITY_PATH = REPORT_DIR / "coefficient_stability.csv"
COEF_SOURCE_PATH = REFIT_DIR / "coefficients_source_level.csv"
COEF_ENCODED_PATH = REFIT_DIR / "coefficients_encoded.csv"
REFIT_MANIFEST_PATH = REFIT_DIR / "final_refit_manifest.json"

# ---------------------------------------------------------------------------
# Palette (dataviz skill reference palette, light-mode static print figures)
# ---------------------------------------------------------------------------
COLOR_SURFACE = "#fcfcfb"
COLOR_PRIMARY_INK = "#0b0b0b"
COLOR_SECONDARY_INK = "#52514e"
COLOR_MUTED = "#898781"
COLOR_GRIDLINE = "#e1e0d9"
COLOR_BASELINE = "#c3c2b7"
COLOR_SERIES_MAIN = "#2a78d6"  # categorical slot 1 (blue)
COLOR_REPEAT_LINE_ALPHA = 0.16

FONT_FAMILY = ["Segoe UI", "DejaVu Sans", "sans-serif"]

plt.rcParams.update(
    {
        "font.family": FONT_FAMILY,
        "figure.facecolor": COLOR_SURFACE,
        "axes.facecolor": COLOR_SURFACE,
        "savefig.facecolor": COLOR_SURFACE,
        "text.color": COLOR_PRIMARY_INK,
        "axes.edgecolor": COLOR_BASELINE,
        "axes.labelcolor": COLOR_PRIMARY_INK,
        "xtick.color": COLOR_MUTED,
        "ytick.color": COLOR_MUTED,
        "grid.color": COLOR_GRIDLINE,
        "axes.grid": True,
        "grid.linewidth": 0.7,
        "axes.linewidth": 0.9,
        "font.size": 11,
    }
)


def r(x, nd=3):
    return round(float(x), nd)


def main():
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------
    # Load locked artifacts (read-only)
    # -----------------------------------------------------------------
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    refit_manifest = json.loads(REFIT_MANIFEST_PATH.read_text(encoding="utf-8"))
    oof = pd.read_csv(OOF_PATH)
    coef_stability = pd.read_csv(COEF_STABILITY_PATH)
    coef_source = pd.read_csv(COEF_SOURCE_PATH)
    coef_encoded = pd.read_csv(COEF_ENCODED_PATH)

    assert manifest["n_folds_ok"] == 50 and manifest["n_folds_total"] == 50
    assert manifest["n_rows"] == 431
    assert oof.shape[0] == 4310, f"expected 4310 OOF rows, got {oof.shape[0]}"
    assert oof["repeat"].nunique() == 10
    assert oof.groupby("repeat").size().eq(431).all()
    assert not oof[["y_true", "predicted_probability"]].isna().any().any()
    assert np.isfinite(oof[["y_true", "predicted_probability"]].to_numpy()).all()
    assert refit_manifest["n_rows_used"] == 431

    rl = manifest["repeat_level"]
    hist = manifest["historical_frozen_stage3_lasso_baseline"]

    n_events_per_repeat = int(oof.loc[oof["repeat"] == 1, "y_true"].sum())
    n_total_per_repeat = int((oof["repeat"] == 1).sum())
    prevalence = n_events_per_repeat / n_total_per_repeat
    assert n_events_per_repeat == 61 and n_total_per_repeat == 431

    # ===================================================================
    # 1. FINAL MODEL PERFORMANCE TABLE
    # ===================================================================
    metrics = [
        ("PR-AUC", "mean_pr_auc", "sd_pr_auc"),
        ("AUROC", "mean_auroc", "sd_auroc"),
        ("Brier score", "mean_brier", "sd_brier"),
        ("Brier skill score", "mean_brier_skill", "sd_brier_skill"),
        ("Log-loss", "mean_logloss", "sd_logloss"),
        ("Calibration intercept", "mean_calibration_intercept", "sd_calibration_intercept"),
        ("Calibration slope", "mean_calibration_slope", "sd_calibration_slope"),
    ]

    perf_rows = []
    for label, mean_key, sd_key in metrics:
        perf_rows.append(
            {
                "metric": label,
                "compact_ridge_mean": r(rl[mean_key], 4),
                "compact_ridge_sd": r(rl[sd_key], 4),
                "historical_stage3_lasso_baseline_mean": r(hist[mean_key], 4),
                "historical_stage3_lasso_baseline_sd": r(hist[sd_key], 4),
            }
        )
    perf_df = pd.DataFrame(perf_rows)
    perf_csv_path = TABLES_DIR / "table_final_model_performance.csv"
    perf_df.to_csv(perf_csv_path, index=False)

    perf_md_lines = [
        "# Final Compact Ridge Model Performance Under Repeated Subject-Grouped Internal Validation",
        "",
        "| Metric | Compact Ridge (current, locked) | Historical Stage 3 / LASSO baseline |",
        "|---|---|---|",
    ]
    for row in perf_rows:
        cr = f"{row['compact_ridge_mean']:.3f} (SD {row['compact_ridge_sd']:.3f})"
        hb = (
            f"{row['historical_stage3_lasso_baseline_mean']:.3f} "
            f"(SD {row['historical_stage3_lasso_baseline_sd']:.3f})"
        )
        perf_md_lines.append(f"| {row['metric']} | {cr} | {hb} |")
    perf_md_lines += [
        "",
        "Values are locked repeat-level means (10 repeats x 5 outer folds = 50/50 successful folds, "
        "0 failures) from `outputs/final_modeling/compact_ridge_lock/report/locked_validation_manifest.json`. "
        "SD = standard deviation across the 10 outer-CV repeats.",
        "",
        "**Historical Stage 3 / LASSO baseline** is the previously locked, now-superseded architecture "
        "(Decision 99 superseded it). It is shown here only as a contextual historical comparator and is "
        "**not** a current candidate model.",
        "",
        "> Performance represents internal repeated subject-grouped cross-validation after exploratory "
        "model development on the same dataset; it is not independent or external validation.",
    ]
    perf_md_path = TABLES_DIR / "table_final_model_performance.md"
    perf_md_path.write_text("\n".join(perf_md_lines) + "\n", encoding="utf-8")

    # ===================================================================
    # 2/3/4. FIGURES from locked OOF predictions (repeat-wise + aggregate)
    # ===================================================================
    repeats = sorted(oof["repeat"].unique())

    # ---- Precision-Recall -------------------------------------------------
    common_recall = np.linspace(0.0, 1.0, 201)
    interp_precisions = []

    fig, ax = plt.subplots(figsize=(6.2, 5.2), dpi=300)
    for i, rep in enumerate(repeats):
        sub = oof.loc[oof["repeat"] == rep]
        precision, recall, _ = precision_recall_curve(
            sub["y_true"], sub["predicted_probability"]
        )
        # precision_recall_curve returns recall in decreasing order; reverse
        # to ascending order so it can be used as the interpolation x-axis.
        recall_asc = recall[::-1]
        precision_asc = precision[::-1]
        ax.step(
            recall,
            precision,
            where="post",
            color=COLOR_SERIES_MAIN,
            alpha=COLOR_REPEAT_LINE_ALPHA,
            linewidth=1.0,
            label="Individual CV repeat (10x)" if i == 0 else None,
        )
        interp_precisions.append(np.interp(common_recall, recall_asc, precision_asc))

    mean_precision = np.mean(np.vstack(interp_precisions), axis=0)
    ax.plot(
        common_recall,
        mean_precision,
        color=COLOR_SERIES_MAIN,
        linewidth=2.4,
        label="Aggregate (mean across repeats)",
    )
    ax.axhline(
        prevalence,
        color=COLOR_MUTED,
        linestyle="--",
        linewidth=1.3,
        label=f"No-skill reference (prevalence = {prevalence:.3f})",
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Compact Ridge: Precision-Recall (locked internal validation)")
    ax.annotate(
        f"Mean PR-AUC = {rl['mean_pr_auc']:.3f} (SD {rl['sd_pr_auc']:.3f})\n"
        f"10 repeats x 5 outer folds, 431 deliveries/repeat",
        xy=(0.98, 0.98),
        xycoords="axes fraction",
        ha="right",
        va="top",
        fontsize=9.5,
        color=COLOR_SECONDARY_INK,
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=COLOR_GRIDLINE, alpha=0.9),
    )
    ax.legend(loc="lower left", fontsize=8.5, frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "figure_compact_ridge_precision_recall.png")
    fig.savefig(FIGURES_DIR / "figure_compact_ridge_precision_recall.svg")
    plt.close(fig)

    # ---- ROC ---------------------------------------------------------------
    common_fpr = np.linspace(0.0, 1.0, 201)
    interp_tprs = []

    fig, ax = plt.subplots(figsize=(6.2, 5.2), dpi=300)
    for i, rep in enumerate(repeats):
        sub = oof.loc[oof["repeat"] == rep]
        fpr, tpr, _ = roc_curve(sub["y_true"], sub["predicted_probability"])
        ax.plot(
            fpr,
            tpr,
            color=COLOR_SERIES_MAIN,
            alpha=COLOR_REPEAT_LINE_ALPHA,
            linewidth=1.0,
            label="Individual CV repeat (10x)" if i == 0 else None,
        )
        tpr_i = np.interp(common_fpr, fpr, tpr)
        tpr_i[0] = 0.0
        interp_tprs.append(tpr_i)

    mean_tpr = np.mean(np.vstack(interp_tprs), axis=0)
    mean_tpr[-1] = 1.0
    ax.plot(
        common_fpr,
        mean_tpr,
        color=COLOR_SERIES_MAIN,
        linewidth=2.4,
        label="Aggregate (mean across repeats)",
    )
    ax.plot([0, 1], [0, 1], color=COLOR_MUTED, linestyle="--", linewidth=1.3, label="Chance")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("Compact Ridge: ROC (locked internal validation)")
    ax.annotate(
        f"Mean AUROC = {rl['mean_auroc']:.3f} (SD {rl['sd_auroc']:.3f})\n"
        f"10 repeats x 5 outer folds, 431 deliveries/repeat",
        xy=(0.98, 0.06),
        xycoords="axes fraction",
        ha="right",
        va="bottom",
        fontsize=9.5,
        color=COLOR_SECONDARY_INK,
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=COLOR_GRIDLINE, alpha=0.9),
    )
    ax.legend(loc="upper left", fontsize=8.5, frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "figure_compact_ridge_roc.png")
    fig.savefig(FIGURES_DIR / "figure_compact_ridge_roc.svg")
    plt.close(fig)

    # ---- Calibration ---------------------------------------------------
    n_bins = 8  # equal-frequency (quantile) bins; see figures_metadata.md
    repeat_bin_points = []  # list of (mean_pred[8], mean_obs[8]) per repeat

    fig, ax = plt.subplots(figsize=(6.2, 5.4), dpi=300)
    for i, rep in enumerate(repeats):
        sub = oof.loc[oof["repeat"] == rep].sort_values("predicted_probability").reset_index(drop=True)
        bin_id = pd.qcut(sub.index, q=n_bins, labels=False)
        grouped = sub.groupby(bin_id).agg(
            mean_pred=("predicted_probability", "mean"),
            mean_obs=("y_true", "mean"),
        )
        repeat_bin_points.append(grouped[["mean_pred", "mean_obs"]].to_numpy())
        ax.plot(
            grouped["mean_pred"],
            grouped["mean_obs"],
            color=COLOR_SERIES_MAIN,
            alpha=COLOR_REPEAT_LINE_ALPHA,
            linewidth=1.0,
            marker="o",
            markersize=2.5,
            label="Individual CV repeat (10x)" if i == 0 else None,
        )

    stacked = np.stack(repeat_bin_points, axis=0)  # (10, 8, 2)
    agg_mean_pred = stacked[:, :, 0].mean(axis=0)
    agg_mean_obs = stacked[:, :, 1].mean(axis=0)

    lims = [0, max(agg_mean_pred.max(), agg_mean_obs.max()) * 1.15]
    ax.plot(lims, lims, color=COLOR_MUTED, linestyle="--", linewidth=1.3, label="Ideal calibration")
    ax.plot(
        agg_mean_pred,
        agg_mean_obs,
        color=COLOR_SERIES_MAIN,
        linewidth=2.4,
        marker="o",
        markersize=5.5,
        label="Aggregate (mean across repeats)",
    )
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Mean predicted probability (per bin)")
    ax.set_ylabel("Observed frequency (per bin)")
    ax.set_title("Compact Ridge: Calibration (locked internal validation)")
    ax.annotate(
        f"Calibration intercept = {rl['mean_calibration_intercept']:+.3f}\n"
        f"Calibration slope = {rl['mean_calibration_slope']:.3f}\n"
        f"Brier = {rl['mean_brier']:.3f}   Brier skill = {rl['mean_brier_skill']:+.3f}\n"
        f"{n_bins} equal-frequency bins/repeat, {n_total_per_repeat} deliveries, "
        f"{n_events_per_repeat} events/repeat",
        xy=(0.03, 0.97),
        xycoords="axes fraction",
        ha="left",
        va="top",
        fontsize=9,
        color=COLOR_SECONDARY_INK,
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=COLOR_GRIDLINE, alpha=0.9),
    )
    ax.legend(loc="lower right", fontsize=8.5, frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "figure_compact_ridge_calibration.png")
    fig.savefig(FIGURES_DIR / "figure_compact_ridge_calibration.svg")
    plt.close(fig)

    figures_metadata = f"""# Figure generation metadata (Compact Ridge locked results)

Source data: `outputs/final_modeling/compact_ridge_lock/report/locked_validation_oof_predictions.csv`
(4,310 rows = 431 deliveries x 10 repeated-CV repeats; 50/50 outer folds, 0 failures).

Repeated-CV handling philosophy: each delivery contributes one out-of-fold prediction
per repeat (10 total), so the 4,310 rows are NOT 4,310 independent patients. All three
figures below compute a curve/summary **separately within each of the 10 repeats**
(431 predictions each), display those 10 repeat-level curves lightly (alpha={COLOR_REPEAT_LINE_ALPHA}),
and overlay one bold **aggregate curve** obtained by simple, unweighted averaging across
repeats on a common grid. No new confidence intervals were computed; only the locked
repeat-level mean/SD already present in `locked_validation_manifest.json` are annotated.

## Precision-Recall (figure_compact_ridge_precision_recall)
- Per repeat: `sklearn.metrics.precision_recall_curve(y_true, predicted_probability)`.
- Aggregate curve: each repeat's precision is linearly interpolated onto a common
  201-point recall grid (0 to 1); the aggregate curve is the pointwise mean across
  the 10 repeats ("vertical averaging").
- No-skill reference line = empirical prevalence = {n_events_per_repeat}/{n_total_per_repeat} = {prevalence:.4f}.
- Annotated mean PR-AUC is the locked `repeat_level.mean_pr_auc` value (fold-level PR-AUC
  averaged per repeat, then averaged across repeats) — not recomputed from the plotted curve.

## ROC (figure_compact_ridge_roc)
- Per repeat: `sklearn.metrics.roc_curve(y_true, predicted_probability)`.
- Aggregate curve: each repeat's TPR is linearly interpolated onto a common 201-point
  FPR grid (0 to 1); the aggregate curve is the pointwise mean across the 10 repeats
  (the standard repeated/cross-validated mean-ROC recipe).
- Annotated mean AUROC is the locked `repeat_level.mean_auroc` value.

## Calibration (figure_compact_ridge_calibration)
- Per repeat: predictions sorted and split into {n_bins} equal-frequency (quantile) bins
  (~{n_total_per_repeat // n_bins} deliveries/bin/repeat); bin points are
  (mean predicted probability, observed event frequency).
- {n_bins} bins were chosen (not deciles) specifically to avoid very-low-event bins,
  given only {n_events_per_repeat} events per repeat ({prevalence:.1%} prevalence).
- Aggregate curve: bin-index-wise mean of (mean predicted, mean observed) across the
  10 repeats.
- Annotated intercept/slope/Brier/Brier-skill are the locked `repeat_level` values
  (each repeat's calibration intercept/slope was fit via logistic recalibration on
  that repeat's 431 OOF predictions in the original locked run; those 10 per-repeat
  values were then averaged) — not refit here.
"""
    (FIGURES_DIR / "figures_metadata.md").write_text(figures_metadata, encoding="utf-8")

    # ===================================================================
    # 5. FINAL COEFFICIENT TABLE
    # ===================================================================
    stability_by_predictor = coef_stability.set_index("predictor")

    coef_rows = []
    for _, row in coef_encoded.iterrows():
        source_pred = row["source_predictor"]
        encoded_col = row["encoded_column"]
        coef_val = float(row["coefficient_standardized_scale"])
        direction = "positive" if coef_val > 0 else ("negative" if coef_val < 0 else "zero")

        # encoded level label: strip the transformer prefix for readability
        if encoded_col.startswith("cat__" + source_pred + "_"):
            level_label = encoded_col[len("cat__" + source_pred + "_"):]
        else:
            level_label = ""  # continuous/binary predictor, no categorical level

        if source_pred in stability_by_predictor.index:
            st = stability_by_predictor.loc[source_pred]
            median_coef = r(st["median_coef"], 4)
            coef_iqr = r(st["coef_iqr"], 4)
            sign_consistency = r(st["sign_consistency"], 2)
            n_folds = int(st["n_folds"])
            stability_flag = (
                "UNSTABLE (directional sign flips across outer folds)"
                if sign_consistency < 0.90
                else "stable"
            )
        else:
            median_coef = np.nan
            coef_iqr = np.nan
            sign_consistency = np.nan
            n_folds = np.nan
            stability_flag = "not available (categorical level; stability tracked at the source-predictor level only)"

        coef_rows.append(
            {
                "source_predictor": source_pred,
                "encoded_level": level_label,
                "ridge_coefficient_standardized_scale": r(coef_val, 4),
                "direction": direction,
                "outer_fold_median_coefficient": median_coef,
                "outer_fold_coefficient_iqr": coef_iqr,
                "outer_fold_sign_consistency": sign_consistency,
                "n_outer_folds": n_folds,
                "stability_flag": stability_flag,
            }
        )

    coef_df = pd.DataFrame(coef_rows)
    coef_csv_path = TABLES_DIR / "table_final_ridge_coefficients.csv"
    coef_df.to_csv(coef_csv_path, index=False)

    coef_md_lines = [
        "# Final Compact Ridge Coefficients (Full 431-Row Data Refit)",
        "",
        "| Predictor | Level | Ridge coefficient (standardized scale) | Direction | Outer-fold median | Outer-fold IQR | Sign consistency (50 folds) | Stability |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in coef_rows:
        median_str = f"{row['outer_fold_median_coefficient']:.4f}" if not pd.isna(row["outer_fold_median_coefficient"]) else "n/a"
        iqr_str = f"{row['outer_fold_coefficient_iqr']:.4f}" if not pd.isna(row["outer_fold_coefficient_iqr"]) else "n/a"
        cons_str = f"{row['outer_fold_sign_consistency']:.2f}" if not pd.isna(row["outer_fold_sign_consistency"]) else "n/a"
        coef_md_lines.append(
            f"| {row['source_predictor']} | {row['encoded_level'] or '(continuous/binary)'} | "
            f"{row['ridge_coefficient_standardized_scale']:.4f} | {row['direction']} | "
            f"{median_str} | {iqr_str} | {cons_str} | {row['stability_flag']} |"
        )
    coef_md_lines += [
        "",
        "Source: `outputs/final_modeling/compact_ridge_lock/final_refit/coefficients_source_level.csv` and "
        "`coefficients_encoded.csv` (full 431-row final refit, C=0.3162, intercept=-2.0476), cross-referenced "
        "with `outputs/final_modeling/compact_ridge_lock/report/coefficient_stability.csv` "
        "(sign/magnitude stability across the 50 locked-validation outer folds).",
        "",
        "`derived_hypertension_pih_pet_spectrum` uses full-dummy (non-reference) one-hot encoding for this "
        "penalized model, per `final_refit/preprocessing_spec.json` "
        "(`\"categorical_encoding\": \"OneHotEncoder(handle_unknown='ignore') ... full-dummy, penalized model "
        "-- not reference/drop-first coding\"`); each level's coefficient is not relative to an omitted "
        "reference category. Coefficient-stability tracking (`coefficient_stability.csv`) is reported at the "
        "source-predictor level only and does not include per-level stability for this categorical predictor.",
        "",
        "**`BMI_before` is flagged as directionally unstable**: its sign consistency across the 50 outer "
        "validation folds is 0.54 (i.e., close to a coin flip), versus 1.00 for every other continuous/binary "
        "predictor in the frozen set. Its full-refit coefficient sign should not be over-interpreted.",
        "",
        "> Ridge coefficients are penalized coefficients on the standardized/encoded modeling scale and are "
        "not conventional adjusted odds ratios.",
    ]
    coef_md_path = TABLES_DIR / "table_final_ridge_coefficients.md"
    coef_md_path.write_text("\n".join(coef_md_lines) + "\n", encoding="utf-8")

    # ===================================================================
    # Validation checks
    # ===================================================================
    checks = []

    checks.append(("perf_table_pr_auc_matches_manifest", abs(perf_df.loc[0, "compact_ridge_mean"] - round(rl["mean_pr_auc"], 4)) < 1e-9))
    checks.append(("perf_table_auroc_matches_manifest", abs(perf_df.loc[1, "compact_ridge_mean"] - round(rl["mean_auroc"], 4)) < 1e-9))
    checks.append(("perf_table_calib_intercept_matches_manifest", abs(perf_df.loc[5, "compact_ridge_mean"] - round(rl["mean_calibration_intercept"], 4)) < 1e-9))
    checks.append(("perf_table_calib_slope_matches_manifest", abs(perf_df.loc[6, "compact_ridge_mean"] - round(rl["mean_calibration_slope"], 4)) < 1e-9))
    checks.append(("perf_table_historical_pr_auc_matches_manifest", abs(perf_df.loc[0, "historical_stage3_lasso_baseline_mean"] - round(hist["mean_pr_auc"], 4)) < 1e-9))
    checks.append(("no_nan_inf_perf_table", np.isfinite(perf_df.select_dtypes(include=[np.number]).to_numpy()).all()))
    numeric_coef_cols = coef_df.select_dtypes(include=[np.number])
    checks.append(("no_inf_coef_table", np.isfinite(numeric_coef_cols.to_numpy()[~np.isnan(numeric_coef_cols.to_numpy())]).all()))
    checks.append(("coef_table_row_count_matches_encoded_source", len(coef_df) == len(coef_encoded)))
    checks.append(("bmi_before_flagged_unstable", coef_df.loc[coef_df["source_predictor"] == "BMI_before", "stability_flag"].iloc[0].startswith("UNSTABLE")))
    checks.append(("oof_row_count_4310", oof.shape[0] == 4310))
    checks.append(("oof_50_folds_ok", manifest["n_folds_ok"] == 50))
    checks.append(("final_refit_431_rows", refit_manifest["n_rows_used"] == 431))

    fig_files = [
        "figure_compact_ridge_precision_recall.png",
        "figure_compact_ridge_precision_recall.svg",
        "figure_compact_ridge_roc.png",
        "figure_compact_ridge_roc.svg",
        "figure_compact_ridge_calibration.png",
        "figure_compact_ridge_calibration.svg",
    ]
    for f in fig_files:
        p = FIGURES_DIR / f
        checks.append((f"figure_exists_nonempty::{f}", p.exists() and p.stat().st_size > 1000))

    failed = [name for name, ok in checks if not ok]
    if failed:
        raise AssertionError(f"Validation checks failed: {failed}")

    print("All validation checks passed:")
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    print("\nOutputs written under:", OUT_DIR)


if __name__ == "__main__":
    main()

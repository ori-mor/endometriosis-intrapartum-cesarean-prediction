"""Read-only loaders for existing, persisted predictive-modeling artifacts.

Sections H and I of the publication notebook. All loaders are CONSUMERS of
already-written result artifacts only:

    - Section I (primary): the CURRENT locked predictive architecture —
      Decision 99, Compact Ridge — loaded from
      ``outputs/final_modeling/compact_ridge_lock/`` (locked internal
      validation + full-cohort final refit).
    - Section I (historical/superseded): the original Stage 3 / lasso_logistic
      Final-D run, loaded from ``outputs/final_modeling/final_run/`` for
      methodological chronology only. This run is SUPERSEDED by Decision 99
      and must never be described as the current winner.
    - Section H: non-endometriosis incremental-value results (Arm A:
      non-endometriosis-only vs. Arm B: full pool), loaded from
      ``outputs/final_modeling/non_endometriosis_incremental_value/`` if and
      when that directory/summary exists. As of Decision 99, the completed
      exploratory model-improvement process already reached a documented
      negative conclusion (no stable incremental value from any
      endometriosis-specific predictor) — surfaced via the Compact Ridge
      final-refit manifest's ``endometriosis_forced_predictor_note``, not by
      this loader, which stays a strict read-only PENDING/COMPLETE consumer
      of the (currently nonexistent) dedicated incremental-value artifact.

HARD RULE: no function in this module may fit, refit, tune, or otherwise
execute the predictive pipeline. Every function here only opens files with
``open()``/``json.load()``/``pandas.read_csv()`` and never imports
``analysis.modeling.final_modeling`` or any of its scripts
(``non_endometriosis_incremental_value.py``, ``incremental_value_arms.py``,
``matched_unconstrained_benchmark.py``, ``stage_nested_cv_search.py``).

FAIL LOUD, never fake-COMPLETE: a result that claims ``STATUS_COMPLETE`` must
carry every field this module treats as required for that status. If a
required field is missing from an artifact that IS present, the loader raises
``PredictiveContextLoadError`` rather than silently defaulting the status or
returning a metric as ``None``. Only a genuinely absent directory/artifact
yields ``STATUS_NOT_FOUND`` / ``STATUS_PENDING``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPACT_RIDGE_RESULTS_DIR = REPO_ROOT / "outputs" / "final_modeling" / "compact_ridge_lock"
FINAL_D_RESULTS_DIR = REPO_ROOT / "outputs" / "final_modeling" / "final_run"
INCREMENTAL_VALUE_DIR = REPO_ROOT / "outputs" / "final_modeling" / "non_endometriosis_incremental_value"

FINAL_D_MANIFEST_CANDIDATES = [
    "run_manifest.json",
    "final_run_manifest.json",
    "manifest.json",
]

INCREMENTAL_VALUE_SUMMARY_CANDIDATES = [
    "incremental_value_summary.json",
    "summary.json",
    "results_summary.json",
]

STATUS_COMPLETE = "COMPLETE"
STATUS_PENDING = "PENDING"
STATUS_NOT_FOUND = "NOT_FOUND"

HISTORICAL_SUPERSEDED = "HISTORICAL_SUPERSEDED"


class PredictiveContextLoadError(RuntimeError):
    """Raised when a status of ``STATUS_COMPLETE`` would otherwise carry a
    missing required field. This module never returns a fake-COMPLETE object
    with ``None`` metrics."""


def _find_first_existing(directory: Path, candidates: list[str]) -> Path | None:
    for name in candidates:
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def _require(manifest: dict, path: str, *keys: str):
    """Walk nested dict keys; raise ``PredictiveContextLoadError`` naming the
    full dotted path if any key along the way is absent."""
    cur = manifest
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            raise PredictiveContextLoadError(
                f"{path}: missing required field '{'.'.join(keys)}' (stopped at {key!r})."
            )
        cur = cur[key]
    return cur


# ---------------------------------------------------------------------------
# CURRENT predictive architecture — Decision 99, Compact Ridge
# ---------------------------------------------------------------------------
# Expected Decision 99 lock invariants (artifact-INTEGRITY validation only —
# never a recomputed model result; see load_compact_ridge_predictive_context).
EXPECTED_FROZEN_PREDICTOR_COUNT = 6
EXPECTED_OUTER_REPEATS = 10
EXPECTED_OUTER_FOLDS = 5
EXPECTED_N_FOLDS_TOTAL = 50
EXPECTED_N_ROWS = 431


@dataclass
class CompactRidgePredictiveContext:
    status: str
    architecture_name: str | None = None
    frozen_predictors: list[str] = field(default_factory=list)
    n_rows: int | None = None
    outer_repeats: int | None = None
    outer_folds: int | None = None
    n_folds_ok: int | None = None
    n_folds_total: int | None = None
    pr_auc: float | None = None
    auroc: float | None = None
    brier: float | None = None
    calibration_intercept: float | None = None
    calibration_slope: float | None = None
    final_refit_available: bool = False
    final_refit_chosen_C: float | None = None
    final_refit_intercept: float | None = None
    final_refit_source_coefficients: dict | None = None
    final_refit_n_rows_used: int | None = None
    final_refit_n_rows_expected: int | None = None
    final_refit_converged: bool | None = None
    endometriosis_forced_predictor: str | None = None
    endometriosis_forced_predictor_note: str | None = None
    source_paths: list[str] = field(default_factory=list)
    message: str = ""


def load_compact_ridge_predictive_context(
    results_dir: Path = COMPACT_RIDGE_RESULTS_DIR,
) -> CompactRidgePredictiveContext:
    """Load the CURRENT locked predictive architecture (Decision 99, Compact
    Ridge) from its persisted, already-executed artifacts.

    Reads ``report/locked_validation_manifest.json`` (required: locked
    50-fold internal-validation headline metrics) and, if present,
    ``final_refit/final_refit_manifest.json`` (the full-431-row refit).
    Read-only — never imports or executes any final-modeling code.

    ARTIFACT-INTEGRITY VALIDATION ONLY (never a recomputed model result):
    raises ``PredictiveContextLoadError`` unless the persisted manifests are
    internally consistent with the locked Decision 99 design —
    ``frozen_predictors`` unique and exactly
    ``EXPECTED_FROZEN_PREDICTOR_COUNT`` (6); ``outer_repeats * outer_folds ==
    n_folds_total``; ``n_folds_ok == n_folds_total``; the locked validation
    protocol is exactly ``EXPECTED_OUTER_REPEATS x EXPECTED_OUTER_FOLDS`` (10
    x 5 = 50) successful folds; and ``n_rows == EXPECTED_N_ROWS`` (431). When
    a final-refit manifest is present, also requires ``n_rows_used ==
    n_rows_expected == EXPECTED_N_ROWS`` and ``converged is True``.
    """
    if not results_dir.exists():
        return CompactRidgePredictiveContext(
            status=STATUS_NOT_FOUND,
            message=f"Compact Ridge results directory not found: {results_dir}",
        )

    validation_path = results_dir / "report" / "locked_validation_manifest.json"
    if not validation_path.exists():
        raise PredictiveContextLoadError(
            f"Compact Ridge results directory exists but the locked validation manifest "
            f"is missing: {validation_path}. Refusing to report a COMPLETE/NOT_FOUND status "
            "without knowing which — this must be investigated, not silently guessed."
        )

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    v_path = str(validation_path)

    frozen_predictors = _require(validation, v_path, "frozen_predictors")
    n_rows = _require(validation, v_path, "n_rows")
    outer_repeats = _require(validation, v_path, "cv", "outer_repeats")
    outer_folds = _require(validation, v_path, "cv", "outer_folds")
    n_folds_ok = _require(validation, v_path, "n_folds_ok")
    n_folds_total = _require(validation, v_path, "n_folds_total")
    pr_auc = _require(validation, v_path, "repeat_level", "mean_pr_auc")
    auroc = _require(validation, v_path, "repeat_level", "mean_auroc")
    brier = _require(validation, v_path, "repeat_level", "mean_brier")
    calibration_intercept = _require(validation, v_path, "repeat_level", "mean_calibration_intercept")
    calibration_slope = _require(validation, v_path, "repeat_level", "mean_calibration_slope")

    # ---- artifact-integrity validation (never a recomputed model result) ----
    frozen_predictors = list(frozen_predictors)
    if len(set(frozen_predictors)) != len(frozen_predictors):
        raise PredictiveContextLoadError(
            f"{v_path}: frozen_predictors contains duplicate entries: {frozen_predictors}."
        )
    if len(frozen_predictors) != EXPECTED_FROZEN_PREDICTOR_COUNT:
        raise PredictiveContextLoadError(
            f"{v_path}: expected exactly {EXPECTED_FROZEN_PREDICTOR_COUNT} frozen_predictors, "
            f"found {len(frozen_predictors)}: {frozen_predictors}."
        )
    if outer_repeats * outer_folds != n_folds_total:
        raise PredictiveContextLoadError(
            f"{v_path}: cv.outer_repeats ({outer_repeats}) * cv.outer_folds ({outer_folds}) "
            f"!= n_folds_total ({n_folds_total})."
        )
    if n_folds_ok != n_folds_total:
        raise PredictiveContextLoadError(
            f"{v_path}: n_folds_ok ({n_folds_ok}) != n_folds_total ({n_folds_total}) -- the "
            "locked validation run must have zero failed folds."
        )
    if (outer_repeats, outer_folds, n_folds_total) != (
        EXPECTED_OUTER_REPEATS, EXPECTED_OUTER_FOLDS, EXPECTED_N_FOLDS_TOTAL,
    ):
        raise PredictiveContextLoadError(
            f"{v_path}: expected the locked validation protocol to be "
            f"{EXPECTED_OUTER_REPEATS} x {EXPECTED_OUTER_FOLDS} = {EXPECTED_N_FOLDS_TOTAL} "
            f"successful folds, found outer_repeats={outer_repeats}, outer_folds={outer_folds}, "
            f"n_folds_total={n_folds_total}."
        )
    if n_rows != EXPECTED_N_ROWS:
        raise PredictiveContextLoadError(
            f"{v_path}: n_rows ({n_rows}) != the locked canonical cohort size ({EXPECTED_N_ROWS})."
        )

    source_paths = [v_path]

    refit_path = results_dir / "final_refit" / "final_refit_manifest.json"
    final_refit_available = refit_path.exists()
    final_refit_chosen_C = None
    final_refit_intercept = None
    final_refit_source_coefficients = None
    final_refit_n_rows_used = None
    final_refit_n_rows_expected = None
    final_refit_converged = None
    endometriosis_forced_predictor = None
    endometriosis_forced_predictor_note = None
    if final_refit_available:
        refit = json.loads(refit_path.read_text(encoding="utf-8"))
        r_path = str(refit_path)
        final_refit_chosen_C = _require(refit, r_path, "chosen_C")
        final_refit_intercept = _require(refit, r_path, "intercept")
        final_refit_source_coefficients = _require(refit, r_path, "signed_source_coef")
        final_refit_n_rows_used = _require(refit, r_path, "n_rows_used")
        final_refit_n_rows_expected = _require(refit, r_path, "n_rows_expected")
        final_refit_converged = _require(refit, r_path, "converged")
        endometriosis_forced_predictor = refit.get("endometriosis_forced_predictor")
        endometriosis_forced_predictor_note = refit.get("endometriosis_forced_predictor_note")
        source_paths.append(r_path)

        if final_refit_n_rows_used != EXPECTED_N_ROWS:
            raise PredictiveContextLoadError(
                f"{r_path}: n_rows_used ({final_refit_n_rows_used}) != {EXPECTED_N_ROWS}."
            )
        if final_refit_n_rows_expected != EXPECTED_N_ROWS:
            raise PredictiveContextLoadError(
                f"{r_path}: n_rows_expected ({final_refit_n_rows_expected}) != {EXPECTED_N_ROWS}."
            )
        if final_refit_converged is not True:
            raise PredictiveContextLoadError(
                f"{r_path}: converged is {final_refit_converged!r}, expected True."
            )

    return CompactRidgePredictiveContext(
        status=STATUS_COMPLETE,
        architecture_name="Compact Ridge",
        frozen_predictors=list(frozen_predictors),
        n_rows=n_rows,
        outer_repeats=outer_repeats,
        outer_folds=outer_folds,
        n_folds_ok=n_folds_ok,
        n_folds_total=n_folds_total,
        pr_auc=pr_auc,
        auroc=auroc,
        brier=brier,
        calibration_intercept=calibration_intercept,
        calibration_slope=calibration_slope,
        final_refit_available=final_refit_available,
        final_refit_chosen_C=final_refit_chosen_C,
        final_refit_intercept=final_refit_intercept,
        final_refit_source_coefficients=final_refit_source_coefficients,
        final_refit_n_rows_used=final_refit_n_rows_used,
        final_refit_n_rows_expected=final_refit_n_rows_expected,
        final_refit_converged=final_refit_converged,
        endometriosis_forced_predictor=endometriosis_forced_predictor,
        endometriosis_forced_predictor_note=endometriosis_forced_predictor_note,
        source_paths=source_paths,
    )


# ---------------------------------------------------------------------------
# HISTORICAL / SUPERSEDED — original Final-D Stage 3 / lasso_logistic winner
# ---------------------------------------------------------------------------
@dataclass
class FinalDPredictiveContext:
    """Chronology of the ORIGINAL Final-D run only (final micro-correction
    #7): every field here comes from that one run's own ``run_manifest.json``
    — never cross-read from any other artifact. The current Compact Ridge vs.
    historical-frozen-comparator performance display (AUROC/Brier/calibration
    included) lives exclusively in the version-controlled PR #3 table
    (``outputs/results/compact_ridge_final/tables/table_final_model_performance.md``),
    which this context is never merged with — two provenance chains are never
    silently presented as if they were one original Final-D artifact.
    """

    status: str
    label: str = HISTORICAL_SUPERSEDED
    run_id: str | None = None
    execution_commit: str | None = None
    winning_pathway: str | None = None
    stage: int | str | None = None
    model_family: str | None = None
    pr_auc: float | None = None
    source_path: str | None = None
    message: str = ""


def load_final_d_predictive_context(
    results_dir: Path = FINAL_D_RESULTS_DIR,
) -> FinalDPredictiveContext:
    """Load the original, now-SUPERSEDED Final-D result (read-only), for
    methodological chronology only. This is HISTORICAL context — Decision 99
    / Compact Ridge is the current final predictive architecture, never this.

    Reads ONLY ``run_manifest.json``: ``completion_status`` (never defaulted
    — a manifest without this field is a load error, not an assumed
    COMPLETE), ``run_id``, ``git_provenance.git_sha``, and the winning
    ``family``/``stage``/PR-AUC recorded directly in ``winning_strategy``.

    Final micro-correction #7: this function no longer cross-reads AUROC /
    Brier / calibration from the Compact Ridge lock's
    ``historical_frozen_stage3_lasso_baseline`` block — mixing a metric
    sourced from a DIFFERENT artifact into this one's fields silently
    presented two distinct provenance chains as if they were one original
    Final-D measurement. That same historical-comparator metric set (AUROC/
    Brier/calibration included) is instead shown, correctly attributed, in
    the version-controlled PR #3 performance table
    (``outputs/results/compact_ridge_final/tables/table_final_model_performance.md``).
    """
    if not results_dir.exists():
        return FinalDPredictiveContext(
            status=STATUS_NOT_FOUND,
            message=f"Final-D results directory not found: {results_dir}",
        )

    manifest_path = _find_first_existing(results_dir, FINAL_D_MANIFEST_CANDIDATES)
    if manifest_path is None:
        return FinalDPredictiveContext(
            status=STATUS_NOT_FOUND,
            message=(
                f"No recognizable manifest found under {results_dir}; "
                f"searched: {FINAL_D_MANIFEST_CANDIDATES}"
            ),
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    m_path = str(manifest_path)

    status = _require(manifest, m_path, "completion_status")
    winning_strategy = _require(manifest, m_path, "winning_strategy")
    model_family = _require(winning_strategy, m_path, "family")
    stage = _require(winning_strategy, m_path, "stage")
    pr_auc = _require(
        winning_strategy, m_path, "evidence", "best_by_mean_pr_auc", "mean_pr_auc"
    )

    return FinalDPredictiveContext(
        status=status,
        run_id=manifest.get("run_id"),
        execution_commit=(manifest.get("git_provenance") or {}).get("git_sha"),
        winning_pathway=f"Stage {stage} / {model_family}",
        stage=stage,
        model_family=model_family,
        pr_auc=pr_auc,
        source_path=m_path,
    )


# ---------------------------------------------------------------------------
# HISTORICAL / SUPERSEDED — Stage 3 / LASSO per-fold selection frequency and
# coefficient-sign consistency for the endometriosis family (OPTIONAL
# enrichment for Section E; never the current/canonical predictive evidence)
# ---------------------------------------------------------------------------
# The scope actually compared for winner selection — "matched_unconstrained_
# benchmark" is explicitly excluded from the primary comparison per
# winner_selection.json's own "excludes_from_primary_comparison" list, so the
# winning family/stage recorded in run_manifest.json's winning_strategy was
# necessarily chosen within this one model_scope.
HISTORICAL_LASSO_MODEL_SCOPE = "primary_constrained"
FINAL_D_SOURCE_PREDICTOR_SELECTION_CSV = "fold_results/source_predictor_selection.csv"
FINAL_D_TRANSFORMED_COEFFICIENTS_CSV = "coefficients/transformed_feature_coefficients.csv"


@dataclass
class HistoricalLassoEndometriosisStats:
    status: str
    selection_frequency: dict[str, float] = field(default_factory=dict)
    sign_consistency: dict[str, float] = field(default_factory=dict)
    winning_family: str | None = None
    winning_stage: int | None = None
    model_scope: str | None = None
    source_paths: list[str] = field(default_factory=list)
    message: str = ""


def load_final_d_historical_lasso_endometriosis_stats(
    predictors: list[str],
    results_dir: Path = FINAL_D_RESULTS_DIR,
) -> HistoricalLassoEndometriosisStats:
    """OPTIONAL read-only enrichment: per-fold selection frequency and
    coefficient-sign consistency for ``predictors``, computed from the
    already-persisted HISTORICAL Stage-3/LASSO (SUPERSEDED, Decision 99)
    fold-level artifacts under ``outputs/final_modeling/final_run/`` —
    ``fold_results/source_predictor_selection.csv`` (per-fold
    selected/active booleans) and ``coefficients/transformed_feature_coefficients.csv``
    (per-fold coefficient values).

    Never re-fits anything: this only aggregates booleans/coefficients that
    the historical run already recorded, restricted to that run's own
    recorded winning ``family``/``stage`` (read from ``run_manifest.json``'s
    ``winning_strategy`` — never hardcoded) within
    ``HISTORICAL_LASSO_MODEL_SCOPE``.

    Returns ``STATUS_NOT_FOUND`` (never raises) if any required artifact is
    missing or the winning family/stage cannot be determined — this is
    optional historical enrichment for Section E, not part of what a
    ``STATUS_COMPLETE`` Compact Ridge context means. Callers must never label
    the returned statistics as current/canonical predictive evidence — see
    ``research_signal_summary.build_endometriosis_findings_table``'s
    explicitly-named ``historical_lasso_selection_frequency`` /
    ``historical_lasso_sign_consistency`` fields.
    """
    manifest_path = _find_first_existing(results_dir, FINAL_D_MANIFEST_CANDIDATES)
    selection_path = results_dir / FINAL_D_SOURCE_PREDICTOR_SELECTION_CSV
    coef_path = results_dir / FINAL_D_TRANSFORMED_COEFFICIENTS_CSV
    if manifest_path is None or not selection_path.exists() or not coef_path.exists():
        return HistoricalLassoEndometriosisStats(
            status=STATUS_NOT_FOUND,
            message=(
                "historical Stage-3/LASSO fold-level selection/coefficient artifacts not "
                f"found under {results_dir}"
            ),
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    winning_strategy = manifest.get("winning_strategy") or {}
    family = winning_strategy.get("family")
    stage = winning_strategy.get("stage")
    if family is None or stage is None:
        return HistoricalLassoEndometriosisStats(
            status=STATUS_NOT_FOUND,
            message=f"{manifest_path}: winning_strategy family/stage not recorded",
        )

    selection = pd.read_csv(selection_path)
    selection = selection[
        (selection["model_scope"] == HISTORICAL_LASSO_MODEL_SCOPE)
        & (selection["family"] == family)
        & (selection["stage"] == stage)
    ]
    coefficients = pd.read_csv(coef_path)
    coefficients = coefficients[
        (coefficients["model_scope"] == HISTORICAL_LASSO_MODEL_SCOPE)
        & (coefficients["family"] == family)
        & (coefficients["stage"] == stage)
    ]

    # ---- completeness gate for selection_frequency (final micro-correction
    # #7): the winning-pathway slice must have EXACTLY EXPECTED_N_FOLDS_TOTAL
    # (50) distinct (repeat, outer_fold) pairs, and every requested predictor
    # that appears at all must have exactly one selection record per fold.
    # A partial/ambiguous denominator is never estimated from -- the entire
    # selection_frequency enrichment is omitted (never raised, since this is
    # optional historical enrichment) if the completeness condition fails.
    n_distinct_folds = int(selection[["repeat", "outer_fold"]].drop_duplicates().shape[0])
    selection_complete = n_distinct_folds == EXPECTED_N_FOLDS_TOTAL

    selection_frequency: dict[str, float] = {}
    if selection_complete:
        pred_fold_counts = selection.groupby("source_predictor")[["repeat", "outer_fold"]].apply(
            lambda g: len(g.drop_duplicates())
        )
        for predictor in predictors:
            pred_selection = selection[selection["source_predictor"] == predictor]
            if not len(pred_selection):
                continue
            # One selection record per predictor per fold -- a predictor
            # observed fewer times than the full 50-fold denominator would
            # silently understate/overstate its true selection frequency.
            if int(pred_fold_counts.get(predictor, 0)) != EXPECTED_N_FOLDS_TOTAL:
                continue
            selection_frequency[predictor] = float(pred_selection["active_postfit"].mean())

    completeness_message = (
        ""
        if selection_complete
        else (
            f"historical selection-frequency enrichment omitted: expected exactly "
            f"{EXPECTED_N_FOLDS_TOTAL} distinct (repeat, outer_fold) pairs for the winning "
            f"pathway ({HISTORICAL_LASSO_MODEL_SCOPE}/{family}/stage {stage}), found "
            f"{n_distinct_folds} -- refusing to estimate from a partial denominator."
        )
    )

    # ---- sign_consistency: never aggregate multiple transformed
    # coefficients of a multi-level categorical source predictor into one
    # apparent source-level sign (final micro-correction #7). Only computed
    # for a predictor when every one of its ACTIVE folds contributes exactly
    # ONE transformed coefficient (true binary/continuous predictors);
    # ambiguous multi-coefficient (one-hot categorical) source predictors are
    # omitted entirely rather than guessing a representative sign.
    sign_consistency: dict[str, float] = {}
    for predictor in predictors:
        pred_active_coef = coefficients[
            (coefficients["source_predictor"] == predictor) & (coefficients["active"])
        ]
        if not len(pred_active_coef):
            continue
        per_fold_transformed_feature_counts = pred_active_coef.groupby(
            ["repeat", "outer_fold"]
        )["transformed_feature"].nunique()
        if (per_fold_transformed_feature_counts > 1).any():
            continue  # ambiguous multi-coefficient (one-hot categorical) source predictor
        n_positive = int((pred_active_coef["coefficient"] > 0).sum())
        n_negative = int((pred_active_coef["coefficient"] < 0).sum())
        n_signed = n_positive + n_negative
        if n_signed:
            sign_consistency[predictor] = max(n_positive, n_negative) / n_signed

    return HistoricalLassoEndometriosisStats(
        status=STATUS_COMPLETE,
        selection_frequency=selection_frequency,
        sign_consistency=sign_consistency,
        winning_family=family,
        winning_stage=stage,
        model_scope=HISTORICAL_LASSO_MODEL_SCOPE,
        source_paths=[str(manifest_path), str(selection_path), str(coef_path)],
        message=completeness_message,
    )


# ---------------------------------------------------------------------------
# Section H — non-endometriosis incremental predictive value
# ---------------------------------------------------------------------------
@dataclass
class IncrementalValueResult:
    status: str
    by_stage: dict = field(default_factory=dict)
    source_path: str | None = None
    message: str = ""


def load_incremental_value_results(
    results_dir: Path = INCREMENTAL_VALUE_DIR,
) -> IncrementalValueResult:
    """Load the non-endometriosis incremental-value summary (read-only).

    Expected shape once released: per-stage (1/2/3) Arm A (non-endometriosis
    predictors only) vs. Arm B (full pool with endometriosis available)
    metrics — primary PR-AUC, secondary AUROC/Brier/calibration
    intercept/slope, plus paired B-minus-A uncertainty.

    Returns a ``PENDING`` result (never raises, never triggers modeling) when
    this specific dedicated artifact does not exist. This is NOT the same as
    "incremental-value work has never been done": Decision 99's completed
    exploratory model-improvement process (four analyses on
    ``exploratory/overnight-model-improvement``) already reached a documented
    negative conclusion, which is surfaced separately, read-only, via
    ``load_compact_ridge_predictive_context().endometriosis_forced_predictor_note``
    — never fabricated here as if this dedicated Arm-A/B artifact existed.
    """
    if not results_dir.exists():
        return IncrementalValueResult(
            status=STATUS_PENDING,
            message=(
                "PENDING - no dedicated Arm-A/B incremental-value artifact has been "
                f"generated at {results_dir}. This does not mean incremental value was "
                "never examined: see the Decision 99 conclusion in "
                "load_compact_ridge_predictive_context().endometriosis_forced_predictor_note."
            ),
        )

    summary_path = _find_first_existing(results_dir, INCREMENTAL_VALUE_SUMMARY_CANDIDATES)
    if summary_path is None:
        return IncrementalValueResult(
            status=STATUS_PENDING,
            message=(
                "PENDING - directory exists but no recognizable summary found under "
                f"{results_dir}; searched: {INCREMENTAL_VALUE_SUMMARY_CANDIDATES}"
            ),
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return IncrementalValueResult(
        status=STATUS_COMPLETE,
        by_stage=summary.get("by_stage", summary),
        source_path=str(summary_path),
    )

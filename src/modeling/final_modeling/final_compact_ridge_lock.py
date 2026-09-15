"""Final locked architecture: Compact Ridge Logistic Regression -- CANONICAL.

Freezes the final predictive-modeling architecture selected after the
completed exploratory model-improvement work (overnight model-improvement
experiment + Endometriosis Add-On Experiment + Endometriosis Signal Recovery
audit + Endometriosis Feature Profiling ranking + Endometriosis Phenotype
Aggregation audit, all on branch `exploratory/overnight-model-improvement`).
This module performs NO further architecture search, NO predictor search,
NO new estimator comparison -- it locks and validates the frozen 6-predictor
architecture only.

Frozen predictors (no `gestational_age_at_delivery_days`, no
endometriosis-specific predictor forced in):

    AGE, nulliparity, S_P_CS, BMI_before,
    derived_hypertension_pih_pet_spectrum, induction_any_bin

Estimator: L2 (Ridge) logistic regression, probability-aware selection rule
identical to the "compact_ridge_brier" / Arm F1_brier procedure used
throughout the exploratory work -- PR-AUC one-SE band, then lowest inner
Brier, then smallest C (least shrinkage-reversed / most-regularized) as a
final tiebreak. C grid: 15-point logspace(-2, 1.5), unchanged from every
exploratory compact-ridge arm.

Two products, kept strictly separate:

  A. LOCKED INTERNAL-VALIDATION RUN (`run_locked_validation` /
     `aggregate_locked_validation`) -- canonical repeated 10x5 subject-grouped
     outer CV, canonical grouped inner CV, fold-safe preprocessing (median
     impute + standardize + fold-safe BMI_before recompute from
     height/weight_before_pregnancy). This is the run whose repeat/fold
     metrics constitute the FINAL reported model performance. Because this
     architecture was selected using exploratory analyses on the SAME
     development dataset (not a held-out or externally collected sample),
     these numbers must always be described as internal repeated grouped
     validation after exploratory model development -- never as an
     independent test set or external validation.

  B. FINAL FULL-DATA REFIT (`full_data_refit`) -- fits the frozen
     architecture once on all 431 deliveries, using the identical frozen
     tuning procedure (C selected by one canonical grouped 5-fold inner
     split of the full cohort, `repeat=1, fold=1` -- the same
     deterministic seed convention `modeling_core.inner_seed` uses inside
     every outer fold, simply applied once with no outer holdout since
     there is none left to hold out). This produces the coefficients used
     going forward; its own training-set performance is NEVER reported as
     model performance -- only Part A's repeated grouped CV numbers are.

No endometriosis structural constraint applies (the frozen set is
intentionally endometriosis-free; forcing one in was explicitly rejected).
No hard co-entry pair contains more than one of the 6 frozen predictors
(verified: `induction_any_bin`'s only hard partner,
`indication_for_induction_status`, is not in the frozen set), so no
training-fold hard-pair resolution step is needed.

    python -m analysis.modeling.final_modeling.final_compact_ridge_lock --validate
    python -m analysis.modeling.final_modeling.final_compact_ridge_lock --refit
    python -m analysis.modeling.final_modeling.final_compact_ridge_lock --all
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modeling_core as core  # noqa: E402
from fit_convergence import fit_logistic_with_convergence  # noqa: E402
from source_predictor_activity import (  # noqa: E402
    COEFFICIENT_ACTIVITY_TOLERANCE, active_source_predictors,
    build_column_to_source_map, source_level_coefficients, source_sign,
)

warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parents[3]
_EPS = 1e-6

# --------------------------------------------------------------------------
# Frozen architecture -- do not edit without a new, explicit re-lock decision
# --------------------------------------------------------------------------
FROZEN_PREDICTORS: tuple[str, ...] = (
    "AGE", "nulliparity", "S_P_CS", "BMI_before",
    "derived_hypertension_pih_pet_spectrum", "induction_any_bin",
)
FROZEN_PENALTY = "l2"
RIDGE_C_GRID: tuple[float, ...] = tuple(float(c) for c in np.logspace(-2, 1.5, 15))
SELECTION_RULE = "pr_auc_one_se_then_brier"  # identical to compact_ridge_brier / Arm F1_brier

WORKSPACE = REPO_ROOT / "outputs" / "final_modeling" / "compact_ridge_lock"
FOLDS_DIR, PREDS_DIR = WORKSPACE / "folds", WORKSPACE / "preds"
REPORT_DIR, REFIT_DIR = WORKSPACE / "report", WORKSPACE / "final_refit"
for _d in (FOLDS_DIR, PREDS_DIR, REPORT_DIR, REFIT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CANON_RUN = REPO_ROOT / "outputs" / "final_modeling" / "final_run"
CANON_OOF = CANON_RUN / "predictions" / "primary_outer_oof_predictions.csv"

METRICS = ("pr_auc", "auroc", "brier", "brier_skill", "logloss",
           "calibration_intercept", "calibration_slope")


# --------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------
def load_context():
    matrix, registry, _manifest = core.load_inputs()
    y = matrix[core.TARGET].astype(int)
    X = matrix.drop(columns=[core.TARGET])
    groups = np.asarray(core.load_groups(matrix))
    eligibility = core.build_stage_predictor_metadata(registry)
    splits = core.make_outer_splits(y, groups)  # canonical 10x5, canonical seeds
    row_ids = [f"row_{i:04d}" for i in range(len(matrix))]
    return {"matrix": matrix, "registry": registry, "X": X, "y": y,
            "groups": groups, "eligibility": eligibility, "splits": splits,
            "row_ids": row_ids}


def verify_frozen_set_contract(registry: pd.DataFrame) -> pd.DataFrame:
    """Confirm every frozen predictor is a currently-eligible candidate and
    that none is endometriosis-specific."""
    cmf = pd.read_csv(REPO_ROOT / "outputs" / "eda_c" / "candidate_model_features.csv").set_index("variable")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from endometriosis_family import ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY as ENDO_FAM
    rows = []
    for v in FROZEN_PREDICTORS:
        r = cmf.loc[v]
        rows.append({"predictor": v, "eligibility_status": r["eligibility_status"],
                     "earliest_entry_stage": int(r["earliest_entry_stage"]),
                     "is_endometriosis_specific": v in ENDO_FAM})
    df = pd.DataFrame(rows)
    assert (df["eligibility_status"].str.lower() == "eligible").all(), f"non-eligible frozen predictor:\n{df}"
    assert not df["is_endometriosis_specific"].any(), f"an endometriosis-specific predictor was frozen in:\n{df}"
    return df


# --------------------------------------------------------------------------
# Fit / predict / metrics
# --------------------------------------------------------------------------
def fit_ridge(X_fit: pd.DataFrame, y_fit: pd.Series, eligibility: pd.DataFrame,
              C: float, seed: int = core.SEED_BASE) -> dict[str, Any]:
    members = list(FROZEN_PREDICTORS)
    pre = core.build_preprocessor(members, eligibility, scaling=True)
    in_cols = [c for c in members if c in X_fit.columns] + \
              [c for c in ("height", "weight_before_pregnancy") if c in X_fit.columns and c not in members]
    # build_preprocessor's fold-safe BMI_before transformer reads height/weight_before_pregnancy
    # internally; deduplicate while preserving order (mirrors constrained_selection._input_columns).
    in_cols = list(dict.fromkeys(in_cols))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        Z = np.asarray(pre.fit_transform(X_fit[in_cols], y_fit), dtype=float)
        est = LogisticRegression(penalty="l2", C=float(C), solver="lbfgs",
                                  fit_intercept=True, max_iter=20000, tol=1e-4, random_state=seed)
        fit = fit_logistic_with_convergence(est, Z, y_fit)
    names = [str(n) for n in pre.get_feature_names_out()]
    cmap = build_column_to_source_map(pre, members)
    coef = fit.estimator.coef_.ravel()
    active = active_source_predictors(coef, names, cmap, COEFFICIENT_ACTIVITY_TOLERANCE)
    level = source_level_coefficients(coef, names, cmap)
    signed = {s: source_sign(c) for s, c in level.items()}
    return {"preprocessor": pre, "estimator": fit.estimator, "input_cols": in_cols,
            "feature_names": names, "column_to_source_map": cmap, "coef": coef,
            "intercept": float(fit.estimator.intercept_[0]), "converged": bool(fit.converged),
            "convergence": fit.as_record(), "active_sources": sorted(active),
            "n_active_sources": len(active), "signed_source_coef": signed,
            "source_level_coefficients": level, "l2_coef_norm": float(np.sqrt(np.sum(coef ** 2)))}


def predict_ridge(fitrec: dict[str, Any], X_eval: pd.DataFrame) -> np.ndarray:
    pre, est, in_cols = fitrec["preprocessor"], fitrec["estimator"], fitrec["input_cols"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return np.asarray(est.predict_proba(pre.transform(X_eval[in_cols]))[:, 1], dtype=float)


def _prob_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    pc = np.clip(p, _EPS, 1 - _EPS)
    return {"pr_auc": float(average_precision_score(y, p)),
            "brier": float(brier_score_loss(y, p)),
            "logloss": float(log_loss(y, pc, labels=[0, 1])),
            "auroc": float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else float("nan")}


def _outer_metrics(y_true: np.ndarray, probs: np.ndarray, train_prev: float) -> dict[str, Any]:
    y = y_true.astype(int)
    pc = np.clip(probs, _EPS, 1 - _EPS)
    brier = float(brier_score_loss(y, probs))
    brier_prev = float(np.mean((y - train_prev) ** 2))
    ci, cs = core.calibration_intercept_slope(y, probs)
    return {"pr_auc": float(average_precision_score(y, probs)),
            "auroc": float(roc_auc_score(y, probs)) if len(np.unique(y)) > 1 else None,
            "brier": brier, "brier_skill": (1.0 - brier / brier_prev) if brier_prev > 0 else None,
            "logloss": float(log_loss(y, pc, labels=[0, 1])),
            "calibration_intercept": ci, "calibration_slope": cs,
            "prevalence": float(np.mean(y)), "train_prevalence": float(train_prev)}


# --------------------------------------------------------------------------
# Inner-CV C selection: PR-AUC one-SE band -> lowest inner Brier -> smallest C
# --------------------------------------------------------------------------
def _eval_c_inner(X_tr: pd.DataFrame, y_tr: pd.Series, groups_tr: np.ndarray,
                   eligibility: pd.DataFrame, C: float, repeat: int, fold: int) -> dict[str, Any]:
    inner = core.make_inner_splits(y_tr, groups_tr, repeat, fold)
    recs = []
    for itr, iva in inner:
        fr = fit_ridge(X_tr.iloc[itr], y_tr.iloc[itr], eligibility, C)
        rec = {"converged": fr["converged"]}
        if fr["converged"]:
            p = predict_ridge(fr, X_tr.iloc[iva])
            rec.update(_prob_metrics(y_tr.iloc[iva].to_numpy(), p))
            rec["scorable"] = True
        else:
            rec["scorable"] = False
        recs.append(rec)
    valid = all(r["scorable"] for r in recs)

    def _m(k): return float(np.mean([r[k] for r in recs])) if valid else None
    def _se(k):
        v = [r[k] for r in recs]
        return float(np.std(v, ddof=1) / math.sqrt(len(v))) if valid and len(v) > 1 else 0.0
    return {"C": C, "inner_valid": valid, "mean_pr_auc": _m("pr_auc"), "se_pr_auc": _se("pr_auc"),
            "mean_brier": _m("brier"), "mean_logloss": _m("logloss")}


def select_C(evals: list[dict[str, Any]]) -> float:
    valid = [e for e in evals if e["inner_valid"] and e["mean_pr_auc"] is not None]
    if not valid:
        raise RuntimeError("no inner-valid C in the frozen grid -- refuses to silently widen the search")
    best = max(valid, key=lambda e: e["mean_pr_auc"])
    thr = best["mean_pr_auc"] - best["se_pr_auc"]
    band = [e for e in valid if e["mean_pr_auc"] >= thr]
    chosen = sorted(band, key=lambda e: (round(e["mean_brier"], 6), e["C"]))[0]
    return float(chosen["C"])


# --------------------------------------------------------------------------
# A. Locked internal-validation run
# --------------------------------------------------------------------------
def _fold_path(r: int, f: int) -> Path: return FOLDS_DIR / f"r{r:02d}_f{f}.json"
def _preds_path(r: int, f: int) -> Path: return PREDS_DIR / f"r{r:02d}_f{f}.csv"


def _atomic_json(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8"); tmp.replace(path)


def _atomic_csv(path: Path, df: pd.DataFrame) -> None:
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    df.to_csv(tmp, index=False); tmp.replace(path)


def _run_one_fold(ctx: dict, split: dict[str, Any]) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    repeat, fold = split["repeat"], split["fold"]
    fp = _fold_path(repeat, fold)
    if fp.is_file():
        return {"repeat": repeat, "fold": fold, "skipped": True}
    X, y, groups = ctx["X"], ctx["y"], ctx["groups"]
    tr, va = split["train_idx"], split["val_idx"]
    X_tr, y_tr, g_tr = X.iloc[tr], y.iloc[tr], groups[tr]
    X_va, y_va = X.iloc[va], y.iloc[va]
    yv = y_va.to_numpy()
    train_prev = float(y_tr.mean())
    t0 = time.time()

    evals = [_eval_c_inner(X_tr, y_tr, g_tr, ctx["eligibility"], C, repeat, fold) for C in RIDGE_C_GRID]
    chosen_C = select_C(evals)
    refit = fit_ridge(X_tr, y_tr, ctx["eligibility"], chosen_C)
    if not refit["converged"]:
        rec = {"repeat": repeat, "fold": fold, "status": "FAILED",
               "reason": "outer refit at selected C did not converge"}
        _atomic_json(fp, rec)
        return {"repeat": repeat, "fold": fold, "status": "FAILED"}
    probs = predict_ridge(refit, X_va)
    om = _outer_metrics(yv, probs, train_prev)
    rec = {"repeat": repeat, "fold": fold, "status": "OK", "chosen_C": chosen_C,
           "selection_rule": SELECTION_RULE, "outer": om,
           "active_sources": refit["active_sources"], "n_active_sources": refit["n_active_sources"],
           "signed_source_coef": refit["signed_source_coef"], "l2_coef_norm": refit["l2_coef_norm"],
           "intercept": refit["intercept"], "n_val": int(len(yv)), "n_val_pos": int(yv.sum()),
           "secs": round(time.time() - t0, 1)}
    _atomic_json(fp, rec)
    _atomic_csv(_preds_path(repeat, fold),
                pd.DataFrame({"row_id": [ctx["row_ids"][i] for i in va], "y_true": yv,
                              "predicted_probability": probs}))
    return {"repeat": repeat, "fold": fold, "status": "OK", "pr_auc": round(om["pr_auc"], 4)}


def run_locked_validation(n_jobs: int = 12) -> dict[str, Any]:
    ctx = load_context()
    verify_frozen_set_contract(ctx["registry"]).to_csv(REPORT_DIR / "frozen_set_contract.csv", index=False)
    t0 = time.time()
    out = Parallel(n_jobs=n_jobs, backend="loky", verbose=5)(
        delayed(_run_one_fold)(ctx, s) for s in ctx["splits"])
    n_ok = sum(1 for o in out if o.get("status") == "OK")
    n_fail = sum(1 for o in out if o.get("status") == "FAILED")
    n_skip = sum(1 for o in out if o.get("skipped"))
    return {"n_units": len(ctx["splits"]), "n_ok": n_ok, "n_failed": n_fail,
            "n_skipped": n_skip, "secs": round(time.time() - t0, 1)}


def _pooled(y: np.ndarray, p: np.ndarray) -> dict[str, float | None]:
    two = len(np.unique(y)) == 2
    pc = np.clip(p, _EPS, 1 - _EPS)
    brier = float(brier_score_loss(y, p))
    prev = float(np.mean(y))
    bp = float(np.mean((y - prev) ** 2))
    ci, cs = core.calibration_intercept_slope(y, p)
    return {"pr_auc": float(average_precision_score(y, p)) if two else None,
            "auroc": float(roc_auc_score(y, p)) if two else None,
            "brier": brier, "brier_skill": (1 - brier / bp) if bp > 0 else None,
            "logloss": float(log_loss(y, pc, labels=[0, 1])),
            "calibration_intercept": ci, "calibration_slope": cs}


def aggregate_locked_validation() -> dict[str, Any]:
    ctx = load_context()
    n_rows = len(ctx["matrix"])

    fold_rows = []
    for p in sorted(FOLDS_DIR.glob("*.json")):
        rr = json.loads(p.read_text(encoding="utf-8"))
        base = {k: rr.get(k) for k in ("repeat", "fold", "status", "reason", "chosen_C",
                                       "n_active_sources", "intercept", "l2_coef_norm")}
        for k, v in (rr.get("outer") or {}).items():
            base[f"outer_{k}"] = v
        fold_rows.append(base)
    fold_df = pd.DataFrame(fold_rows).sort_values(["repeat", "fold"])
    fold_df.to_csv(REPORT_DIR / "fold_level_metrics.csv", index=False)
    assert (fold_df["status"] == "OK").all(), f"non-OK folds present:\n{fold_df[fold_df.status != 'OK']}"
    assert len(fold_df) == 50, f"expected 50 canonical outer folds, found {len(fold_df)}"

    # repeat-level pooled OOF (canonical convention: pool within a repeat, then average over repeats)
    by_rep: dict[int, list[pd.DataFrame]] = {}
    for f in sorted(PREDS_DIR.glob("r*_f*.csv")):
        rep = int(f.stem.split("_")[0][1:])
        by_rep.setdefault(rep, []).append(pd.read_csv(f))
    per_rep_metrics = {}
    all_oof = []
    for rep, parts in sorted(by_rep.items()):
        d = pd.concat(parts, ignore_index=True)
        pos = d["row_id"].str.slice(4).astype(int).to_numpy()
        assert len(np.unique(pos)) == n_rows, f"repeat {rep}: incomplete OOF coverage ({len(np.unique(pos))}/{n_rows})"
        d["repeat"] = rep
        all_oof.append(d)
        per_rep_metrics[rep] = _pooled(d["y_true"].to_numpy(), d["predicted_probability"].to_numpy())
    oof_full = pd.concat(all_oof, ignore_index=True).sort_values(["repeat", "row_id"])
    oof_full.to_csv(REPORT_DIR / "locked_validation_oof_predictions.csv", index=False)

    repeat_level = {"n_repeats": len(per_rep_metrics)}
    for k in METRICS:
        vals = [m[k] for m in per_rep_metrics.values() if m[k] is not None]
        repeat_level[f"mean_{k}"] = float(np.mean(vals)) if vals else None
        repeat_level[f"sd_{k}"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
    pd.DataFrame([{"repeat": r, **m} for r, m in per_rep_metrics.items()]).to_csv(
        REPORT_DIR / "repeat_level_metrics.csv", index=False)

    # historical frozen Stage-3 LASSO baseline, same OOF file the whole exploratory arc used
    baseline = None
    if CANON_OOF.is_file():
        b = pd.read_csv(CANON_OOF)
        b = b[(b["model_scope"] == "primary_constrained") & (b["stage"] == 3) & (b["family"] == "lasso_logistic")]
        b_by_rep = {}
        for rep, d in b.groupby("repeat"):
            b_by_rep[rep] = _pooled(d["target"].to_numpy() if "target" in d.columns else d["y_true"].to_numpy(),
                                     d["predicted_probability"].to_numpy())
        baseline = {"n_repeats": len(b_by_rep)}
        for k in METRICS:
            vals = [m[k] for m in b_by_rep.values() if m[k] is not None]
            baseline[f"mean_{k}"] = float(np.mean(vals)) if vals else None
            baseline[f"sd_{k}"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0

    # coefficient stability across the 50 outer fits
    stab_rows = []
    coef_by_source: dict[str, list[float]] = {}
    for p in sorted(FOLDS_DIR.glob("*.json")):
        rr = json.loads(p.read_text(encoding="utf-8"))
        for s, c in (rr.get("signed_source_coef") or {}).items():
            if c is not None:
                coef_by_source.setdefault(s, []).append(c)
    for s in FROZEN_PREDICTORS:
        c = np.array(coef_by_source.get(s, []), dtype=float)
        if c.size == 0:
            continue
        pos = int(np.sum(c > 0)); neg = int(np.sum(c < 0))
        stab_rows.append({"predictor": s, "n_folds": len(c), "median_coef": float(np.median(c)),
                          "coef_iqr": float(np.percentile(c, 75) - np.percentile(c, 25)),
                          "sign_consistency": max(pos, neg) / len(c)})
    pd.DataFrame(stab_rows).to_csv(REPORT_DIR / "coefficient_stability.csv", index=False)

    manifest = {
        "generated_utc": core.utc_now() if hasattr(core, "utc_now") else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_type": "LOCKED_INTERNAL_VALIDATION",
        "note": "This is INTERNAL repeated grouped cross-validation performed after exploratory "
                "model development on the SAME development dataset. It is NOT an independent test "
                "set and NOT external validation.",
        "frozen_predictors": list(FROZEN_PREDICTORS),
        "penalty": FROZEN_PENALTY, "C_grid": list(RIDGE_C_GRID), "selection_rule": SELECTION_RULE,
        "cv": {"outer_repeats": core.OUTER_REPEATS, "outer_folds": core.OUTER_FOLDS,
               "inner_folds": core.INNER_FOLDS, "seed_base": core.SEED_BASE},
        "n_folds_ok": int((fold_df.status == "OK").sum()), "n_folds_total": len(fold_df),
        "n_rows": n_rows,
        "repeat_level": repeat_level,
        "historical_frozen_stage3_lasso_baseline": baseline,
        "chosen_C_by_fold": {f"r{r}_f{f}": c for r, f, c in
                             fold_df[["repeat", "fold", "chosen_C"]].itertuples(index=False)},
    }
    (REPORT_DIR / "locked_validation_manifest.json").write_text(
        json.dumps(_clean(manifest), indent=2), encoding="utf-8")
    print(json.dumps({"status": "AGGREGATED", "repeat_level": repeat_level}, indent=2))
    return manifest


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


# --------------------------------------------------------------------------
# B. Final full-data refit
# --------------------------------------------------------------------------
def full_data_refit() -> dict[str, Any]:
    ctx = load_context()
    X, y, groups, eligibility = ctx["X"], ctx["y"], ctx["groups"], ctx["eligibility"]
    n_rows = len(X)

    # Same frozen selection procedure, applied ONCE to the full cohort via the
    # canonical repeat=1,fold=1 grouped-5-fold inner split (the same
    # deterministic inner_seed() convention used inside every outer fold of
    # Part A -- there is no outer holdout left once we are refitting on all
    # data, so this is the single canonical inner-CV configuration).
    evals = [_eval_c_inner(X, y, groups, eligibility, C, repeat=1, fold=1) for C in RIDGE_C_GRID]
    chosen_C = select_C(evals)

    final = fit_ridge(X, y, eligibility, chosen_C)
    if not final["converged"]:
        raise RuntimeError("final full-data refit did not converge")

    coef_table = pd.DataFrame({
        "encoded_column": final["feature_names"],
        "source_predictor": [final["column_to_source_map"].get(n) for n in final["feature_names"]],
        "coefficient_standardized_scale": final["coef"],
    })
    coef_table.to_csv(REFIT_DIR / "coefficients_encoded.csv", index=False)

    source_table = pd.DataFrame([
        {"source_predictor": s, "coefficient_standardized_scale": c, "sign": final["signed_source_coef"].get(s)}
        for s, c in final["source_level_coefficients"].items()
    ])
    source_table.to_csv(REFIT_DIR / "coefficients_source_level.csv", index=False)

    pre = final["preprocessor"]
    prep_spec = {
        "predictors": list(FROZEN_PREDICTORS),
        "input_columns_read": final["input_cols"],
        "transformers": [
            {"name": name, "columns": list(cols) if not hasattr(cols, "tolist") else cols.tolist(),
             "steps": [type(s).__name__ for s in (trans.steps if hasattr(trans, "steps") else [trans])]
             if trans not in ("drop", "passthrough") else str(trans)}
            for name, trans, cols in pre.transformers_
        ],
        "scaling": "StandardScaler on all numeric/encoded columns (fit on the full 431-row cohort "
                   "for this final refit; fold-safe / training-fold-only for Part A's CV)",
        "bmi_before_note": "BMI_before is fold-safe-recomputed from height and weight_before_pregnancy "
                            "(FoldSafeRecomputedBMITransformer) -- here fit on the full cohort, not a fold.",
        "categorical_encoding": "OneHotEncoder(handle_unknown='ignore') for derived_hypertension_pih_pet_spectrum "
                                 "(full-dummy, penalized model -- not reference/drop-first coding)",
        "missingness": "median impute (numeric) / most-frequent impute (categorical) fit on the full cohort",
    }
    (REFIT_DIR / "preprocessing_spec.json").write_text(json.dumps(_clean(prep_spec), indent=2), encoding="utf-8")

    git_sha = _git_sha()
    manifest = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_type": "FINAL_FULL_DATA_REFIT",
        "note": "Fit ONCE on all 431 deliveries. Training-set fit statistics are NOT model "
                "performance -- performance is reported exclusively from the locked internal "
                "validation run (locked_validation_manifest.json).",
        "n_rows_used": n_rows, "n_rows_expected": 431,
        "frozen_predictors": list(FROZEN_PREDICTORS),
        "penalty": FROZEN_PENALTY, "C_grid": list(RIDGE_C_GRID), "selection_rule": SELECTION_RULE,
        "tuning_inner_cv": {"repeat": 1, "fold": 1, "inner_folds": core.INNER_FOLDS,
                            "seed": core.inner_seed(1, 1),
                            "note": "one canonical grouped-5-fold split of the full cohort, same "
                                    "deterministic seed convention as every outer fold's inner CV"},
        "chosen_C": chosen_C,
        "intercept": final["intercept"],
        "converged": final["converged"], "convergence_detail": final["convergence"],
        "n_active_source_predictors": final["n_active_sources"], "active_sources": final["active_sources"],
        "l2_coef_norm": final["l2_coef_norm"],
        "signed_source_coef": final["signed_source_coef"],
        "reproducibility": {
            "git_sha": git_sha, "branch": "final-model/compact-ridge-lock (isolated worktree, based on origin/main)",
            "eda_c_registry_sha256": core.sha256_file(core.CANDIDATE_REGISTRY_PATH) if hasattr(core, "sha256_file") else None,
            "eda_c_matrix_sha256": core.sha256_file(core.MATRIX_PATH) if hasattr(core, "sha256_file") else None,
        },
        "endometriosis_forced_predictor": None,
        "endometriosis_forced_predictor_note": "No endometriosis-specific predictor is present in the "
            "frozen architecture. The completed endometriosis exploratory analyses "
            "(endo_addon / endo_signal_recovery / endo_feature_profiling / endo_phenotype_aggregation, "
            "all on exploratory/overnight-model-improvement) found no stable incremental predictive "
            "value from any measured endometriosis phenotype/severity/surgical-history variable "
            "beyond this obstetric core; that negative result is retained as part of the scientific "
            "findings, not overridden by forcing a predictor into the model.",
    }
    (REFIT_DIR / "final_refit_manifest.json").write_text(json.dumps(_clean(manifest), indent=2), encoding="utf-8")
    print(json.dumps({"status": "REFIT_DONE", "chosen_C": chosen_C, "intercept": final["intercept"],
                      "n_active_sources": final["n_active_sources"]}, indent=2))
    return manifest


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--refit", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--n-jobs", type=int, default=12)
    args = ap.parse_args(argv)
    if args.all or args.validate:
        print(run_locked_validation(args.n_jobs))
    if args.all or args.aggregate or args.validate:
        aggregate_locked_validation()
    if args.all or args.refit:
        full_data_refit()
    if not any([args.validate, args.aggregate, args.refit, args.all]):
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

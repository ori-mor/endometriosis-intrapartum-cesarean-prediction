#!/usr/bin/env python3
"""Deterministic logistic elastic-net estimator with per-feature penalties.

Conventions matched to sklearn ``LogisticRegression`` for the validation suite:

- The optimized objective is weighted mean logistic loss plus an elastic-net
  penalty.
- Sample weights are not renormalized before fitting; the smooth loss is
  divided by ``sum(sample_weight)``.
- ``C`` maps to ``alpha = 1 / (C * sum(sample_weight))``. This is the same
  L2 convention used by sklearn's lbfgs logistic implementation after dividing
  the summed objective by ``sum(sample_weight)``.
- The intercept is handled as an unpenalized separate coefficient.
- Penalty factors apply only to non-intercept coefficients. A factor of 0
  makes that coefficient fully unpenalized for both L1 and L2 terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.utils.validation import check_X_y, check_array, check_is_fitted


def sigmoid(z: np.ndarray) -> np.ndarray:
    out = np.empty_like(z, dtype=float)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    exp_z = np.exp(z[~pos])
    out[~pos] = exp_z / (1.0 + exp_z)
    return out


def stable_logistic_loss_terms(y: np.ndarray, linear: np.ndarray) -> np.ndarray:
    y_signed = 2.0 * y - 1.0
    return np.logaddexp(0.0, -y_signed * linear)


def balanced_class_sample_weight(y: np.ndarray) -> np.ndarray:
    classes, counts = np.unique(y, return_counts=True)
    if set(classes.tolist()) != {0, 1}:
        raise ValueError("Balanced class weights require both binary classes 0 and 1.")
    total = float(len(y))
    class_weight = {int(cls): total / (2.0 * float(count)) for cls, count in zip(classes, counts)}
    return np.asarray([class_weight[int(value)] for value in y], dtype=float)


def resolve_sample_weight(
    y: np.ndarray,
    sample_weight: np.ndarray | None,
    class_weight: str | dict[int, float] | None,
) -> np.ndarray:
    if sample_weight is None:
        weights = np.ones(len(y), dtype=float)
    else:
        weights = np.asarray(sample_weight, dtype=float).copy()
    if class_weight is None:
        return weights
    if class_weight == "balanced":
        weights *= balanced_class_sample_weight(y)
        return weights
    if isinstance(class_weight, dict):
        weights *= np.asarray([class_weight.get(int(value), 1.0) for value in y], dtype=float)
        return weights
    raise ValueError(f"Unsupported class_weight={class_weight!r}")


def logistic_elastic_net_objective(
    theta: np.ndarray,
    X: np.ndarray,
    y: np.ndarray,
    sample_weight: np.ndarray,
    C: float,
    l1_ratio: float,
    penalty_factors: np.ndarray,
    fit_intercept: bool,
) -> float:
    if fit_intercept:
        intercept = theta[0]
        beta = theta[1:]
    else:
        intercept = 0.0
        beta = theta
    weight_sum = float(np.sum(sample_weight))
    alpha = 1.0 / (float(C) * weight_sum)
    linear = intercept + X @ beta
    loss = float(np.sum(sample_weight * stable_logistic_loss_terms(y, linear)) / weight_sum)
    l2 = 0.5 * alpha * (1.0 - l1_ratio) * float(np.sum(penalty_factors * beta * beta))
    l1 = alpha * l1_ratio * float(np.sum(penalty_factors * np.abs(beta)))
    return loss + l2 + l1


def smooth_objective(
    theta: np.ndarray,
    X: np.ndarray,
    y: np.ndarray,
    sample_weight: np.ndarray,
    C: float,
    l1_ratio: float,
    penalty_factors: np.ndarray,
    fit_intercept: bool,
) -> float:
    if fit_intercept:
        intercept = theta[0]
        beta = theta[1:]
    else:
        intercept = 0.0
        beta = theta
    weight_sum = float(np.sum(sample_weight))
    alpha = 1.0 / (float(C) * weight_sum)
    linear = intercept + X @ beta
    loss = float(np.sum(sample_weight * stable_logistic_loss_terms(y, linear)) / weight_sum)
    l2 = 0.5 * alpha * (1.0 - l1_ratio) * float(np.sum(penalty_factors * beta * beta))
    return loss + l2


def smooth_gradient(
    theta: np.ndarray,
    X: np.ndarray,
    y: np.ndarray,
    sample_weight: np.ndarray,
    C: float,
    l1_ratio: float,
    penalty_factors: np.ndarray,
    fit_intercept: bool,
) -> np.ndarray:
    if fit_intercept:
        intercept = theta[0]
        beta = theta[1:]
    else:
        intercept = 0.0
        beta = theta
    weight_sum = float(np.sum(sample_weight))
    alpha = 1.0 / (float(C) * weight_sum)
    linear = intercept + X @ beta
    residual = (sigmoid(linear) - y) * sample_weight / weight_sum
    beta_grad = X.T @ residual + alpha * (1.0 - l1_ratio) * penalty_factors * beta
    if fit_intercept:
        return np.concatenate([[float(np.sum(residual))], beta_grad])
    return beta_grad


def soft_threshold(values: np.ndarray, threshold: np.ndarray) -> np.ndarray:
    return np.sign(values) * np.maximum(np.abs(values) - threshold, 0.0)


def proximal_step(
    theta: np.ndarray,
    grad: np.ndarray,
    step_size: float,
    C: float,
    l1_ratio: float,
    penalty_factors: np.ndarray,
    sample_weight_sum: float,
    fit_intercept: bool,
) -> np.ndarray:
    candidate = theta - step_size * grad
    alpha = 1.0 / (float(C) * sample_weight_sum)
    threshold = step_size * alpha * l1_ratio * penalty_factors
    if fit_intercept:
        out = candidate.copy()
        out[1:] = soft_threshold(candidate[1:], threshold)
        return out
    return soft_threshold(candidate, threshold)


def proximal_residual(
    theta: np.ndarray,
    grad: np.ndarray,
    step_size: float,
    C: float,
    l1_ratio: float,
    penalty_factors: np.ndarray,
    sample_weight_sum: float,
    fit_intercept: bool,
) -> float:
    prox = proximal_step(theta, grad, step_size, C, l1_ratio, penalty_factors, sample_weight_sum, fit_intercept)
    return float(np.linalg.norm(theta - prox) / max(1.0, np.linalg.norm(theta)))


@dataclass
class FitDiagnostics:
    converged: bool
    n_iter: int
    objective: float
    smooth_objective: float
    proximal_residual: float
    failure_reason: str | None
    step_size: float


class ForcedEndoLogisticRegression(BaseEstimator, ClassifierMixin):
    """Binary logistic regression with exact L1 prox and penalty factors."""

    def __init__(
        self,
        C: float = 1.0,
        l1_ratio: float = 1.0,
        penalty_factors: np.ndarray | None = None,
        fit_intercept: bool = True,
        class_weight: str | dict[int, float] | None = None,
        max_iter: int = 5000,
        tol: float = 1e-8,
        backtracking: bool = True,
        backtracking_shrink: float = 0.5,
        backtracking_expand: float = 1.05,
        min_step_size: float = 1e-14,
    ) -> None:
        self.C = C
        self.l1_ratio = l1_ratio
        self.penalty_factors = penalty_factors
        self.fit_intercept = fit_intercept
        self.class_weight = class_weight
        self.max_iter = max_iter
        self.tol = tol
        self.backtracking = backtracking
        self.backtracking_shrink = backtracking_shrink
        self.backtracking_expand = backtracking_expand
        self.min_step_size = min_step_size

    def _initial_step_size(self, X: np.ndarray, sample_weight: np.ndarray, penalty_factors: np.ndarray) -> float:
        weight_sum = float(np.sum(sample_weight))
        if self.fit_intercept:
            X_aug = np.column_stack([np.ones(X.shape[0]), X])
            penalty_aug = np.concatenate([[0.0], penalty_factors])
        else:
            X_aug = X
            penalty_aug = penalty_factors
        weighted_X = X_aug * np.sqrt(sample_weight / weight_sum)[:, None]
        gram = weighted_X.T @ weighted_X
        lipschitz = 0.25 * float(np.linalg.eigvalsh(gram).max())
        alpha = 1.0 / (float(self.C) * weight_sum)
        lipschitz += alpha * (1.0 - float(self.l1_ratio)) * float(np.max(penalty_aug))
        return 1.0 / max(lipschitz, 1e-12)

    def _validate_parameters(self, n_features: int) -> np.ndarray:
        if not np.isfinite(self.C) or self.C <= 0:
            raise ValueError("C must be finite and positive.")
        if not 0.0 <= float(self.l1_ratio) <= 1.0:
            raise ValueError("l1_ratio must be in [0, 1].")
        if self.penalty_factors is None:
            factors = np.ones(n_features, dtype=float)
        else:
            factors = np.asarray(self.penalty_factors, dtype=float)
        if factors.shape != (n_features,):
            raise ValueError(f"penalty_factors must have shape ({n_features},).")
        if not np.isfinite(factors).all() or (factors < 0).any():
            raise ValueError("penalty_factors must be finite and non-negative.")
        return factors

    def fit(self, X: np.ndarray, y: np.ndarray, sample_weight: np.ndarray | None = None) -> "ForcedEndoLogisticRegression":
        X, y = check_X_y(X, y, accept_sparse=False, dtype=float, ensure_2d=True)
        y = y.astype(int)
        classes = np.unique(y)
        if set(classes.tolist()) != {0, 1}:
            raise ValueError("This estimator requires binary classes 0 and 1 in the training data.")
        factors = self._validate_parameters(X.shape[1])
        weights = resolve_sample_weight(y, sample_weight, self.class_weight)
        if not np.isfinite(weights).all() or (weights <= 0).any():
            raise ValueError("sample weights must be finite and positive.")
        sample_weight_sum = float(np.sum(weights))

        n_theta = X.shape[1] + (1 if self.fit_intercept else 0)
        theta = np.zeros(n_theta, dtype=float)
        yk = theta.copy()
        t = 1.0
        step_size = self._initial_step_size(X, weights, factors)
        diagnostics = FitDiagnostics(False, 0, np.nan, np.nan, np.inf, "max_iter_reached", step_size)

        for iteration in range(1, int(self.max_iter) + 1):
            grad = smooth_gradient(yk, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept)
            current_smooth = smooth_objective(yk, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept)
            local_step = step_size
            while True:
                next_theta = proximal_step(
                    yk, grad, local_step, self.C, self.l1_ratio, factors, sample_weight_sum, self.fit_intercept
                )
                diff = next_theta - yk
                candidate_smooth = smooth_objective(
                    next_theta, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept
                )
                upper_bound = current_smooth + float(grad @ diff) + float(diff @ diff) / (2.0 * local_step)
                if (not self.backtracking) or candidate_smooth <= upper_bound + 1e-12:
                    break
                local_step *= float(self.backtracking_shrink)
                if local_step < float(self.min_step_size):
                    diagnostics = FitDiagnostics(
                        False,
                        iteration,
                        logistic_elastic_net_objective(
                            theta, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept
                        ),
                        smooth_objective(theta, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept),
                        np.inf,
                        "step_size_underflow",
                        local_step,
                    )
                    self._set_fit_result(theta, factors, weights, diagnostics)
                    return self

            next_grad = smooth_gradient(next_theta, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept)
            residual = proximal_residual(
                next_theta,
                next_grad,
                local_step,
                self.C,
                self.l1_ratio,
                factors,
                sample_weight_sum,
                self.fit_intercept,
            )
            obj = logistic_elastic_net_objective(next_theta, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept)
            if not np.isfinite(obj) or not np.isfinite(residual):
                diagnostics = FitDiagnostics(False, iteration, obj, np.nan, residual, "non_finite_fit_value", local_step)
                self._set_fit_result(next_theta, factors, weights, diagnostics)
                return self
            if residual <= float(self.tol):
                diagnostics = FitDiagnostics(
                    True,
                    iteration,
                    obj,
                    smooth_objective(next_theta, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept),
                    residual,
                    None,
                    local_step,
                )
                self._set_fit_result(next_theta, factors, weights, diagnostics)
                return self

            next_t = 0.5 * (1.0 + np.sqrt(1.0 + 4.0 * t * t))
            yk = next_theta + ((t - 1.0) / next_t) * (next_theta - theta)
            theta = next_theta
            t = next_t
            step_size = min(local_step * float(self.backtracking_expand), self._initial_step_size(X, weights, factors))

        final_grad = smooth_gradient(theta, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept)
        final_residual = proximal_residual(
            theta, final_grad, step_size, self.C, self.l1_ratio, factors, sample_weight_sum, self.fit_intercept
        )
        diagnostics = FitDiagnostics(
            False,
            int(self.max_iter),
            logistic_elastic_net_objective(theta, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept),
            smooth_objective(theta, X, y, weights, self.C, self.l1_ratio, factors, self.fit_intercept),
            final_residual,
            "max_iter_reached",
            step_size,
        )
        self._set_fit_result(theta, factors, weights, diagnostics)
        return self

    def _set_fit_result(
        self,
        theta: np.ndarray,
        penalty_factors: np.ndarray,
        sample_weight: np.ndarray,
        diagnostics: FitDiagnostics,
    ) -> None:
        if self.fit_intercept:
            self.intercept_ = np.asarray([theta[0]], dtype=float)
            self.coef_ = theta[1:].reshape(1, -1)
        else:
            self.intercept_ = np.asarray([0.0], dtype=float)
            self.coef_ = theta.reshape(1, -1)
        self.classes_ = np.asarray([0, 1])
        self.penalty_factors_ = penalty_factors.copy()
        self.sample_weight_sum_ = float(np.sum(sample_weight))
        self.n_iter_ = np.asarray([diagnostics.n_iter], dtype=int)
        self.converged_ = bool(diagnostics.converged)
        self.objective_ = float(diagnostics.objective)
        self.smooth_objective_ = float(diagnostics.smooth_objective)
        self.proximal_residual_ = float(diagnostics.proximal_residual)
        self.failure_reason_ = diagnostics.failure_reason
        self.step_size_ = float(diagnostics.step_size)

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        check_is_fitted(self, ["coef_", "intercept_"])
        X = check_array(X, accept_sparse=False, dtype=float, ensure_2d=True)
        return self.intercept_[0] + X @ self.coef_[0]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        linear = self.decision_function(X)
        p1 = sigmoid(linear)
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    def diagnostics(self) -> dict[str, Any]:
        check_is_fitted(self, ["coef_", "intercept_"])
        return {
            "converged": bool(self.converged_),
            "n_iter": int(self.n_iter_[0]),
            "objective": float(self.objective_),
            "smooth_objective": float(self.smooth_objective_),
            "proximal_residual": float(self.proximal_residual_),
            "failure_reason": self.failure_reason_,
            "step_size": float(self.step_size_),
            "sample_weight_sum": float(self.sample_weight_sum_),
        }

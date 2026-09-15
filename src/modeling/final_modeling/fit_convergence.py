#!/usr/bin/env python3
"""Centralized convergence-aware logistic-regression fitting.

Correction 16 (Final D closure pass, 2026-09-01): convergence is part of MODEL
VALIDITY, not a cosmetic warning. Every logistic fit in the constrained
pathways -- Top-N (unpenalized) and LASSO / Elastic-Net (saga) -- goes through
``fit_logistic_with_convergence()`` so that:

* ``sklearn.exceptions.ConvergenceWarning`` is explicitly CAPTURED
  (``warnings.catch_warnings(record=True)`` + ``simplefilter("always", ...)``)
  rather than relied on appearing in stdout;
* a non-converged fit is marked ``converged = False`` and the caller treats it
  as an INVALID candidate (its PR-AUC never contributes to any ranking, its
  outer-training refit triggers the inner-ranked fallback, and if nothing
  converges the pathway/fold fails loud);
* ``n_iter`` / ``max_iter`` / ``solver`` are recorded for the stability log.

This module fits ONLY. It never scores, never selects, never looks at a
validation fold.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.exceptions import ConvergenceWarning


@dataclass(frozen=True)
class FitResult:
    estimator: Any
    converged: bool
    convergence_warning: bool
    n_iter: int | None
    max_iter: int | None
    solver: str | None
    warning_messages: tuple[str, ...]

    def as_record(self) -> dict[str, Any]:
        return {
            "converged": self.converged,
            "convergence_warning": self.convergence_warning,
            "n_iter": self.n_iter,
            "max_iter": self.max_iter,
            "solver": self.solver,
        }


def _extract_n_iter(estimator) -> int | None:
    n_iter = getattr(estimator, "n_iter_", None)
    if n_iter is None:
        return None
    try:
        arr = np.asarray(n_iter).ravel()
        return int(arr.max()) if arr.size else None
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def fit_logistic_with_convergence(estimator, Z, y) -> FitResult:
    """Fit ``estimator`` on ``(Z, y)`` capturing ConvergenceWarning.

    Returns a :class:`FitResult`. ``converged`` is ``False`` iff at least one
    ``ConvergenceWarning`` was raised during ``fit``. The estimator is returned
    fitted either way -- it is the caller's responsibility to reject an
    unconverged fit (do not read its coefficients as a valid result).
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        estimator.fit(Z, np.asarray(y))
    conv_msgs = tuple(
        str(w.message) for w in caught if issubclass(w.category, ConvergenceWarning)
    )
    converged = not conv_msgs
    return FitResult(
        estimator=estimator,
        converged=converged,
        convergence_warning=bool(conv_msgs),
        n_iter=_extract_n_iter(estimator),
        max_iter=getattr(estimator, "max_iter", None),
        solver=getattr(estimator, "solver", None),
        warning_messages=conv_msgs,
    )

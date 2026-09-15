"""Endometriosis-specific findings (Section E) and research-signal triangulation (Section G).

Combines, per endometriosis-specific predictor:
    - crude univariable association (from ``univariable_analysis.py``);
    - adjusted association (from ``adjusted_endometriosis_analysis.py``);
    - exploratory BH-FDR q-value;
    - ``current_compact_ridge_member`` — whether the predictor is one of the
      locked Decision 99 Compact Ridge frozen predictors, derived read-only
      from ``predictive_context_loaders.load_compact_ridge_predictive_context()``
      (never hardcoded here, never re-fit);
    - OPTIONAL ``historical_lasso_selection_frequency`` /
      ``historical_lasso_sign_consistency`` — read-only, explicitly-named
      HISTORICAL Stage-3/LASSO (SUPERSEDED, Decision 99) per-fold statistics,
      when those already-persisted fold-level artifacts are available (see
      ``predictive_context_loaders.load_final_d_historical_lasso_endometriosis_stats``).
      These are never the current/canonical predictive evidence and are
      omitted entirely (not filled with an empty placeholder) when the
      underlying historical artifact is not available;
    - rarity / separation status.

Automatic code in this module may assign ONLY objective, mechanically
derivable statuses:
    INSUFFICIENT_SUPPORT, STANDARD_OR_NOT_ESTIMABLE, SPARSE_EXPLORATORY,
    REVIEW_REQUIRED.

Scientific labels such as PROMISING_EXPLORATORY, CONSISTENT_MULTI-SOURCE_SIGNAL,
or NO_APPARENT_SIGNAL are deliberately NEVER assigned by this module — that
kind of scientific interpretation happens in the written project report, not
in an executable table. Final micro-correction #5: this module therefore
never emits a placeholder scientific-conclusion field (no
``final_scientific_label``, no blank ``interpretation_note``) — only the
objective, mechanically-derived evidence/status fields listed above.

Known conservative handling: a predictor with single-subject support or a
complete-separation fit (e.g. the documented ``adenomyosis_feature_7`` /
``adenomyosis_feature_11`` pattern) is never promoted past
``INSUFFICIENT_SUPPORT`` / ``STANDARD_OR_NOT_ESTIMABLE`` by this code, no
matter how extreme its crude odds ratio looks.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from publication_analysis.adjusted_endometriosis_analysis import (
    MODEL_VARIANT_PRIMARY,
    ROW_TYPE_SOURCE,
)
from publication_analysis.univariable_analysis import (
    FIT_OK,
    SEPARATION_COMPLETE,
    SEPARATION_SINGLE_CASE,
    SUPPORT_INSUFFICIENT,
    SUPPORT_SPARSE,
)

INSUFFICIENT_SUPPORT = "INSUFFICIENT_SUPPORT"
STANDARD_OR_NOT_ESTIMABLE = "STANDARD_OR_NOT_ESTIMABLE"
SPARSE_EXPLORATORY = "SPARSE_EXPLORATORY"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

AUTOMATIC_STATUSES = {
    INSUFFICIENT_SUPPORT,
    STANDARD_OR_NOT_ESTIMABLE,
    SPARSE_EXPLORATORY,
    REVIEW_REQUIRED,
}


def _automatic_status_for_row(row: pd.Series) -> str:
    support_status = row.get("support_status")
    separation_status = row.get("separation_status")
    fit_status = row.get("fit_status")

    if support_status == SUPPORT_INSUFFICIENT or separation_status in (
        SEPARATION_COMPLETE,
        SEPARATION_SINGLE_CASE,
    ):
        return INSUFFICIENT_SUPPORT
    if fit_status != FIT_OK:
        return STANDARD_OR_NOT_ESTIMABLE
    if support_status == SUPPORT_SPARSE:
        return SPARSE_EXPLORATORY
    return REVIEW_REQUIRED


ENDOMETRIOSIS_FINDINGS_COLUMNS = [
    "predictor",
    "clinical_meaning",
    "inferential_role",
    "row_type",
    "model_analysis_N",
    "model_events",
    "model_non_events",
    "model_unique_subjects",
    "odds_ratio",
    "ci_low",
    "ci_high",
    "coef_p_value",
    "omnibus_p_value",
    "effect_representation",
    "hypothesis_type",
    "raw_p",
    "bh_q",
    "in_bh_family",
    "fit_status",
    "separation_status",
    "support_status",
    "rarity_support_status",
    "current_compact_ridge_member",
    "historical_lasso_selection_frequency",
    "historical_lasso_sign_consistency",
]


def build_endometriosis_findings_table(
    univariable_master: pd.DataFrame,
    hypothesis_fdr: pd.DataFrame,
    endo_family_names: Iterable[str],
    frozen_predictors: Iterable[str] | None = None,
    historical_lasso_selection_frequency: dict[str, float] | None = None,
    historical_lasso_sign_consistency: dict[str, float] | None = None,
    clinical_meaning: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Build the Section E endometriosis-specific findings table.

    SOURCE-level, one row per each of the 35 canonical endometriosis-family
    members (see ``publication_contract.endometriosis_family_names``) — built
    by FILTERING/JOINING the canonical Section D tables (``univariable_master``
    from ``univariable_analysis.run_univariable_master`` and ``hypothesis_fdr``
    from ``univariable_analysis.apply_global_bh``), never by fitting a second,
    endometriosis-only regression or computing a second BH-FDR family. The
    global ``bh_q`` / ``in_bh_family`` columns are the SAME GLOBAL 81-predictor
    family already computed in Section D.

    Binary / linear-continuous / count predictors carry a genuine
    ``odds_ratio`` on their source row. Categorical predictors carry their
    source-level omnibus p-value in ``omnibus_p_value`` with ``odds_ratio``
    left null (per-level ORs live in ``univariable_master``'s
    ``row_type == 'level'`` rows — a separate detail table, not flattened in
    here). Nonlinear-spline predictors likewise carry an omnibus
    ``omnibus_p_value`` with no single OR. ``DESCRIPTIVE_ONLY`` /
    ``PENDING_REPRESENTATION_REVIEW`` / non-estimable predictors keep
    ``fit_status`` transparent with every OR/CI/p field null — never a
    fabricated point estimate.

    ``frozen_predictors`` is the read-only Compact Ridge frozen-predictor list
    (``predictive_context_loaders.load_compact_ridge_predictive_context()
    .frozen_predictors``) used ONLY to derive ``current_compact_ridge_member``
    membership — never hardcoded here.

    ``historical_lasso_selection_frequency`` / ``historical_lasso_sign_consistency``
    are OPTIONAL read-only lookups sourced from already-persisted HISTORICAL
    Stage-3/LASSO (SUPERSEDED, Decision 99) fold-level artifacts by
    ``predictive_context_loaders.py``. When not supplied (or when that
    historical artifact is not available), the corresponding columns are
    still emitted but left null for every predictor — never silently omitted
    from the table shape, and never mislabeled as current/canonical
    predictive evidence. This function never fits or reruns anything.
    """
    frozen_predictors = set(frozen_predictors or [])
    historical_lasso_selection_frequency = historical_lasso_selection_frequency or {}
    historical_lasso_sign_consistency = historical_lasso_sign_consistency or {}
    clinical_meaning = clinical_meaning or {}

    family = sorted(set(endo_family_names))

    source_rows = univariable_master[
        (univariable_master["row_type"] == "source")
        & (univariable_master["predictor"].isin(family))
    ].copy()

    missing = sorted(set(family) - set(source_rows["predictor"]))
    if missing:
        raise ValueError(
            f"build_endometriosis_findings_table: no univariable_master source row for "
            f"endometriosis-family predictor(s) {missing} — all 35 members must be represented."
        )
    if source_rows["predictor"].duplicated().any():
        dupes = sorted(source_rows.loc[source_rows["predictor"].duplicated(), "predictor"].unique())
        raise ValueError(
            f"build_endometriosis_findings_table: duplicate univariable_master source row(s) "
            f"for predictor(s) {dupes}."
        )
    if len(source_rows) != len(family):
        raise ValueError(
            f"build_endometriosis_findings_table: expected {len(family)} endometriosis source "
            f"rows, found {len(source_rows)}."
        )

    # Fail-loud hardening (targeted correction #7A): hypothesis_fdr must carry
    # EXACTLY one row for every endometriosis-family predictor. A missing row
    # would otherwise silently produce NaN hypothesis_type/raw_p/bh_q fields
    # via the left-join below; a duplicated row would silently fan out this
    # table. Both must raise, never pass through unnoticed.
    hyp_family_counts = (
        hypothesis_fdr.loc[hypothesis_fdr["predictor"].isin(family), "predictor"].value_counts()
    )
    missing_hyp = sorted(set(family) - set(hyp_family_counts.index))
    if missing_hyp:
        raise ValueError(
            f"build_endometriosis_findings_table: hypothesis_fdr has no row for "
            f"endometriosis-family predictor(s) {missing_hyp} — every family member must have "
            "exactly one hypothesis_fdr row; refusing to silently produce NaN FDR fields."
        )
    dupes_hyp = sorted(hyp_family_counts[hyp_family_counts > 1].index)
    if dupes_hyp:
        raise ValueError(
            f"build_endometriosis_findings_table: hypothesis_fdr has more than one row for "
            f"endometriosis-family predictor(s) {dupes_hyp} — expected exactly one row per predictor."
        )

    df = source_rows.merge(
        hypothesis_fdr[["predictor", "hypothesis_type", "raw_p", "bh_q", "in_bh_family"]],
        on="predictor",
        how="left",
    )
    if len(df) != len(source_rows):
        raise ValueError(
            "build_endometriosis_findings_table: join against hypothesis_fdr changed row "
            "count — hypothesis_fdr must have at most one row per predictor."
        )

    df["rarity_support_status"] = df.apply(_automatic_status_for_row, axis=1)
    df["current_compact_ridge_member"] = df["predictor"].isin(frozen_predictors)
    df["historical_lasso_selection_frequency"] = df["predictor"].map(
        historical_lasso_selection_frequency
    )
    df["historical_lasso_sign_consistency"] = df["predictor"].map(
        historical_lasso_sign_consistency
    )
    df["clinical_meaning"] = df["predictor"].map(clinical_meaning).fillna("")

    return df[ENDOMETRIOSIS_FINDINGS_COLUMNS].sort_values("predictor").reset_index(drop=True)


def build_endometriosis_level_detail(
    univariable_master: pd.DataFrame, endo_family_names: Iterable[str]
) -> pd.DataFrame:
    """Separate, clearly-named categorical level-detail table (reporting only,
    not part of the source-level findings table or any BH family): the
    ``row_type == 'level'`` rows of ``univariable_master`` restricted to the
    endometriosis family's categorical members.
    """
    family = sorted(set(endo_family_names))
    return univariable_master[
        (univariable_master["row_type"] == "level")
        & (univariable_master["predictor"].isin(family))
    ].reset_index(drop=True)


def build_research_signal_evidence(
    endometriosis_findings_df: pd.DataFrame,
    adjusted_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the Section G triangulation table.

    Combines support, crude association, adjusted association (when
    available), predictor-level BH-FDR, ``current_compact_ridge_member`` /
    the optional ``historical_lasso_*`` fields (carried through unchanged
    from ``endometriosis_findings_df`` — see
    ``build_endometriosis_findings_table``), and rarity/separation status.
    Assigns only the automatic, objective statuses listed in the module
    docstring. Final micro-correction #5: this table never emits a
    placeholder scientific-conclusion field (no ``final_scientific_label``)
    — manual scientific interpretation happens in the written project
    report, not here.

    ``adjusted_df`` is the full adjusted master table (both ``PRIMARY`` and
    ``SENSITIVITY_IVF`` model variants, both ``source`` and ``level`` row
    types — see ``adjusted_endometriosis_analysis.py``). The MAIN adjusted
    association fields merged in here come ONLY from
    ``model_variant == MODEL_VARIANT_PRIMARY`` AND ``row_type == ROW_TYPE_SOURCE``
    — exactly one source-level PRIMARY record per endometriosis source
    predictor. A sensitivity-variant or categorical-level row is never
    silently used as the main adjusted estimate; if a categorical omnibus
    detail or the PRIMARY-vs-sensitivity comparison is needed, merge/expose
    those as separate fields/tables rather than mixing them in here.
    """
    evidence = endometriosis_findings_df.copy()

    if adjusted_df is not None:
        primary_source = adjusted_df[
            (adjusted_df["model_variant"] == MODEL_VARIANT_PRIMARY)
            & (adjusted_df["row_type"] == ROW_TYPE_SOURCE)
        ]
        if primary_source["exposure"].duplicated().any():
            dupes = sorted(
                primary_source.loc[primary_source["exposure"].duplicated(), "exposure"].unique()
            )
            raise ValueError(
                f"build_research_signal_evidence: adjusted_df has duplicate PRIMARY "
                f"source-level row(s) for exposure(s) {dupes} — ambiguous join."
            )
        adjusted_cols = primary_source.set_index("exposure")[
            ["adjusted_or", "adjusted_ci_low", "adjusted_ci_high", "adjusted_p", "fit_status"]
        ].rename(columns={"fit_status": "adjusted_fit_status"})
        n_before = len(evidence)
        evidence = evidence.merge(
            adjusted_cols, left_on="predictor", right_index=True, how="left"
        )
        if len(evidence) != n_before:
            raise ValueError(
                "build_research_signal_evidence: PRIMARY source-level join changed row "
                "count — this must be a 1:1 join, never a fan-out."
            )
    else:
        evidence["adjusted_or"] = pd.NA
        evidence["adjusted_ci_low"] = pd.NA
        evidence["adjusted_ci_high"] = pd.NA
        evidence["adjusted_p"] = pd.NA
        evidence["adjusted_fit_status"] = pd.NA

    assert evidence["rarity_support_status"].isin(AUTOMATIC_STATUSES).all(), (
        "build_research_signal_evidence found a non-automatic status leaking through — "
        "only INSUFFICIENT_SUPPORT / STANDARD_OR_NOT_ESTIMABLE / SPARSE_EXPLORATORY / "
        "REVIEW_REQUIRED may be assigned automatically."
    )
    if evidence["predictor"].duplicated().any():
        raise ValueError("build_research_signal_evidence: duplicate predictor rows in output.")

    return evidence

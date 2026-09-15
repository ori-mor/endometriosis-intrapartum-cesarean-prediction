"""Publication notebook — Part 5: endometriosis-specific findings (Section E)."""
from publication_analysis.notebook_parts._cell_helpers import code, md

PART5_CELLS = [
    md(
        "pub-s12-header",
        """
---
## Section E — Endometriosis-Specific Findings

All 35 canonical endometriosis-specific predictors (`endo_family_names`, from
`publication_contract.endometriosis_family_names()`, loaded read-only in
Section A), with support, crude univariable association, exploratory BH-FDR,
and — read-only, from the locked Decision 99 Compact Ridge artifacts, never
re-fit here — `current_compact_ridge_member` membership. Historical Stage-3/
LASSO (SUPERSEDED) fold-level selection-frequency/sign-consistency, when
available, is retained ONLY under its explicit `historical_lasso_*` names —
it is never the current/canonical predictive evidence.

**Single source of truth:** this section does NOT run its own univariable
fit and does NOT compute its own BH-FDR family. It filters/joins the
canonical Section D tables (`univariable_master`, `hypothesis_fdr`) down to
the 35 endometriosis-family members — the `bh_q` here is the SAME GLOBAL
81-predictor family already computed in Section D, never a second
endometriosis-only family.

The current predictive-model context is loaded HERE (before this section's
table is built), not deferred to Section H below — Section E executes before
Section H in this notebook's cell order and must not depend on a later
backfill that never happens.

Known conservative handling: sparse-support predictors such as
`adenomyosis_feature_7` / `adenomyosis_feature_11` (single-subject support /
complete-separation pattern documented in `CLAUDE.md`) are automatically
routed to `INSUFFICIENT_SUPPORT`, never promoted to a "stable finding" by
code.
""",
    ),
    code(
        "pub-s12-imports",
        """
from publication_analysis import research_signal_summary as signal
from publication_analysis import publication_display_labels
from publication_analysis import predictive_context_loaders as pred_context
""",
    ),
    code(
        "pub-s12-load-current-model-context",
        """
# Loaded HERE (before this section's table is built), read-only, from the
# already-persisted locked Decision 99 Compact Ridge artifacts -- never
# re-fits or reruns the predictive model. `compact_ridge_context` is reused
# (not reloaded) by the final predictive-model context section below.
#
# FAIL LOUD, never false-negative membership (final micro-correction #2): for
# THIS notebook, the Compact Ridge artifact is REQUIRED. A missing/incomplete
# artifact must halt the run here -- it must never silently degrade into an
# empty frozen-predictor set, which would otherwise mark every one of the 35
# endometriosis predictors `current_compact_ridge_member = False` even though
# the true membership is actually UNKNOWN (artifact failed to load), not
# "none of them are members".
compact_ridge_context = pred_context.load_compact_ridge_predictive_context()
if compact_ridge_context.status != pred_context.STATUS_COMPLETE:
    raise pred_context.PredictiveContextLoadError(
        "Compact Ridge predictive context is REQUIRED for this notebook but is not "
        f"COMPLETE (status={compact_ridge_context.status!r}, message={compact_ridge_context.message!r}). "
        "Refusing to silently treat missing current-model context as an empty "
        "frozen-predictor set -- fix the locked artifact tree before proceeding."
    )
frozen_predictors = set(compact_ridge_context.frozen_predictors)
print(f"Compact Ridge context status: {compact_ridge_context.status}")
print(
    f"current_compact_ridge_member derived from {len(frozen_predictors)} frozen predictor(s): "
    f"{sorted(frozen_predictors)}"
)

# OPTIONAL, explicitly-named HISTORICAL enrichment only (Stage-3/LASSO,
# SUPERSEDED by Decision 99): per-fold selection frequency / coefficient-sign
# consistency for the endometriosis family, read-only from already-persisted
# fold-level artifacts if present. Never the current/canonical predictive
# evidence -- see Section H below for why Compact Ridge, not this run, is
# the current architecture.
historical_lasso_stats = pred_context.load_final_d_historical_lasso_endometriosis_stats(
    sorted(endo_family_names)
)
print(f"Historical Stage-3/LASSO fold-level stats status: {historical_lasso_stats.status}")
""",
    ),
    code(
        "pub-s12-endo-findings-table",
        """
endometriosis_findings = signal.build_endometriosis_findings_table(
    univariable_master,
    hypothesis_fdr,
    endo_family_names,
    frozen_predictors=frozen_predictors,
    historical_lasso_selection_frequency=(
        historical_lasso_stats.selection_frequency
        if historical_lasso_stats.status == pred_context.STATUS_COMPLETE
        else None
    ),
    historical_lasso_sign_consistency=(
        historical_lasso_stats.sign_consistency
        if historical_lasso_stats.status == pred_context.STATUS_COMPLETE
        else None
    ),
    clinical_meaning={
        p: publication_display_labels.DISPLAY_LABELS[p]
        for p in endo_family_names
        if p in publication_display_labels.DISPLAY_LABELS
    },
)

print(f"endometriosis findings rows: {len(endometriosis_findings)} (expected 35)")
assert len(endometriosis_findings) == 35

exports.save_table_csv(endometriosis_findings, exports.ENDOMETRIOSIS_FINDINGS_CSV)
endometriosis_findings
""",
    ),
    md(
        "pub-s12b-level-detail-header",
        """
### Categorical level-detail for the endometriosis family (reporting only)

Per-level ORs/CIs for the endometriosis family's categorical predictors
(e.g. `endometrioma_size_status`, `endometrioma_presence_laterality`) — a
separate detail table, not flattened into the source-level findings table
above and not part of any BH family.
""",
    ),
    code(
        "pub-s12b-level-detail",
        """
endometriosis_level_detail = signal.build_endometriosis_level_detail(
    univariable_master, endo_family_names
)
endometriosis_level_detail
""",
    ),
]

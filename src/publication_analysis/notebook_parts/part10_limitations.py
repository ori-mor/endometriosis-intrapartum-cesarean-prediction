"""Publication notebook — Part 10: limitations and closing notes."""
from publication_analysis.notebook_parts._cell_helpers import md

PART10_CELLS = [
    md(
        "pub-s20-header",
        """
---
## Limitations

- **Association, not causation.** Nothing in this notebook establishes a
  causal effect of any endometriosis phenotype on intrapartum cesarean
  delivery; all associations may reflect confounding by factors not in the
  locked `PRIMARY_ADJUSTMENT_SET` (`AGE + nulliparity + S_P_CS`), or by
  factors that cannot be adjusted for without risking over-adjustment
  (variables downstream of the phenotype itself).
- **Small event count.** 61 intrapartum-CS events across up to 81 candidate
  predictors means most univariable and adjusted estimates — especially for
  rare endometriosis-specific sub-phenotypes — are exploratory, with wide
  confidence intervals; several are not reliably estimable at all
  (`STANDARD_OR_NOT_RELIABLY_ESTIMABLE`).
- **The adjustment sets are locked, not tunable — but still a specific,
  pre-specified choice.** `PRIMARY_ADJUSTMENT_SET` (`AGE + nulliparity +
  S_P_CS`) and `SENSITIVITY_ADJUSTMENT_SET` (adding
  `mode_of_conception_ivf_vs_all`) are approved (Adjusted Association Design
  Lock, Checkpoint C) and never altered based on a univariable p-value, a
  predictive-model selection result, or an exposure's observed OR — but they
  remain one specific, small conventional-covariate choice, not an
  exhaustive confounder set.
- **Complete-case inferential models (Section F).** The exploratory
  endometriosis-specific adjusted association models (one endometriosis
  exposure at a time, `PRIMARY_ADJUSTMENT_SET`/`SENSITIVITY_ADJUSTMENT_SET`)
  use complete-case rows only; no multiple imputation has been performed.
  Any adjusted analysis flagged with a high complete-case loss
  (`COMPLETE_CASE_RETENTION_WARNING`, Section F) may warrant a future MICE
  sensitivity analysis.
- **Different missing-data handling in the secondary six-predictor
  adjusted-OR analysis (Section H).** Unlike Section F, the secondary
  adjusted-OR analysis over the six Compact Ridge source predictors does
  **not** use complete-case deletion: all 431 cohort rows are retained via
  the same fold-safe reconstruction/imputation contract as the locked
  Compact Ridge final refit (`BMI_before` recomputed from
  component-level-imputed `height`/`weight_before_pregnancy`;
  `derived_hypertension_pih_pet_spectrum`'s 15 missing values imputed with
  the full-cohort mode). These are single reconstructions/imputations
  treated as fixed at estimation time, so the reported confidence intervals
  do not propagate that uncertainty — see
  `outputs/results/compact_ridge_final/adjusted_or/README.md` for the full
  methodology. This is a different, and not interchangeable, missing-data
  policy from Section F's complete-case approach; neither should be assumed
  to generalize to the other. This same secondary analysis also uses
  ordinary model-based MLE/Firth standard errors rather than the
  subject-cluster-robust SEs used in Section F; the 431 deliveries in this
  cohort correspond to 430 subject groups, with only one subject
  contributing two deliveries, which narrows but does not by itself prove
  zero impact of that choice.
- **Multiplicity.** BH-FDR q-values are an exploratory research aid across
  many simultaneous predictor-level tests: one global 81-predictor family in
  Section D, and a separate PRIMARY adjusted endometriosis analysis family in
  Section F. All 35 endometriosis-family source exposures are represented in
  the PRIMARY adjusted analysis; Class C (`STANDARD_ADJUSTED_MODEL_NOT_
  DEFENSIBLE`) exposures are `NOT_FITTED` and never enter the BH procedure at
  all. Benjamini-Hochberg correction is applied only to the estimable Class
  A/B PRIMARY source-level p-values (the exact counts — total represented,
  Class A/B eligible, and actually-estimable — are printed in Section F where
  `adjusted_primary_bh` is built, never hardcoded here). These q-values are
  not used here to decide predictive-model eligibility, to delete any
  predictor from a table, or as a substitute for clinical judgment about
  relevance.
- **Repeated deliveries.** A small number of subjects contribute more than
  one delivery to this cohort (Section A). Subject-cluster-robust standard
  errors are used where technically appropriate, but this does not fully
  resolve every possible source of within-subject correlation for every
  predictor.
- **Incremental predictive value: no dedicated Arm-A/B artifact exists.**
  No dedicated non-endometriosis-vs-full-pool comparison artifact has been
  generated — this does not mean the question was never examined: Decision
  99's completed exploratory model-improvement process already reached a
  documented negative conclusion (no stable incremental value from any
  endometriosis-specific predictor), surfaced read-only in Section H. The
  triangulation table in Section G does not depend on this artifact.
- **Predictive context is internal-validation only, and partly historical.**
  Section H's current Compact Ridge (Decision 99) metrics come from internal
  repeated grouped cross-validation on the same development cohort used for
  exploratory model development — not external validation. The Stage 3 /
  lasso_logistic Final-D metrics shown alongside it are explicitly
  HISTORICAL/SUPERSEDED context for methodological chronology only. Neither
  is re-validated here, and neither should be read as validating the
  associations in Sections D–G (prediction and association are different
  questions — see the introduction).
""",
    ),
]

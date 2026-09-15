"""Publication representation contract: canonical predictive model
representation vs. publication (inferential/descriptive) representation.

Per the task brief, the publication/inferential analysis must use final
cleaned / clinically approved representations, but must NOT blindly reuse
machine-only transformations built for the predictive pipeline (z-scores,
``StandardScaler`` outputs, transformed feature names such as ``num__...``,
fold-specific scaling values or cutpoints).

This module reads only variable-level metadata
(``outputs/eda_c/candidate_model_features.csv`` — no patient rows). It never
invents a clinically interpretable representation that is not already
documented: where none exists, the row is marked
``PENDING_REPRESENTATION_REVIEW`` rather than guessing.

There is exactly ONE representation-decision source of truth in this module:
``build_publication_representation_contract()``. No other function builds an
independent decision table (a prior parallel "representation-audit" policy
that duplicated this decision table — and disagreed with it on categorical
defaults and binary semantics — has been removed; see the Checkpoint-B
targeted-correction pass).

``publication_status`` values:
    APPROVED                 — final publication/inferential representation
                                requiring no further clinical representation
                                decision before inferential use. Covers every
                                signed-off inferential representation regardless
                                of role — BINARY, CATEGORICAL, CONTINUOUS and
                                COUNT (for BINARY, the numeric 0/1 contrast
                                itself, not necessarily a clinical
                                present/absent label; see
                                ``binary_semantic_status``).
    PENDING_CLINICAL_SIGNOFF — architectural status retained for possible
                                future use: a concrete CATEGORICAL / CONTINUOUS
                                / COUNT representation proposed and grounded in
                                a cited repository source but not yet signed off
                                by a clinician. NO row in the current live
                                contract carries this status — every
                                CATEGORICAL / CONTINUOUS / COUNT representation
                                is signed off (APPROVED). If it is ever used
                                again, a future real-data run must NOT silently
                                treat it as final clinical approval.
    DESCRIPTIVE_ONLY          — safe to show in raw/native units for Table 1,
                                but no per-unit OR interpretation is asserted.
    PENDING_REPRESENTATION_REVIEW — no defensible reference / order / unit is
                                on record at all; nothing is fitted
                                inferentially and nothing is invented here.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from publication_analysis.publication_contract import load_candidate_features

APPROVED = "APPROVED"
PENDING_CLINICAL_SIGNOFF = "PENDING_CLINICAL_SIGNOFF"
DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"
PENDING_REPRESENTATION_REVIEW = "PENDING_REPRESENTATION_REVIEW"
VALID_PUBLICATION_STATUSES = {
    APPROVED,
    PENDING_CLINICAL_SIGNOFF,
    DESCRIPTIVE_ONLY,
    PENDING_REPRESENTATION_REVIEW,
}

# Binary semantic-support vocabulary (Checkpoint-B targeted-correction §2).
# binary_passthrough / physical_variable_type=binary alone is NEVER treated
# as proof that 0=absent and 1=present for a SPECIFIC predictor -- that is a
# per-predictor clinical-semantics claim, not a machine-representation fact.
BINARY_SEMANTIC_EXPLICIT = "EXPLICITLY_DOCUMENTED"
BINARY_SEMANTIC_GENERIC = "GENERIC_1_VS_0"

# ===========================================================================
# Functional-form gate (Representation Sign-off + Functional-Form Gate task)
# ===========================================================================
# APPROVING A REPORTING UNIT IS NOT THE SAME AS PROVING THAT THE CONTINUOUS
# PREDICTOR HAS A LINEAR LOG-ODDS RELATIONSHIP. `publication_status` /
# `inferential_role` / `support_status` are never overloaded with this
# information -- functional_form_status is a distinct, separately-gated field.
FF_NOT_APPLICABLE = "NOT_APPLICABLE"
FF_PENDING_REVIEW = "PENDING_FUNCTIONAL_FORM_REVIEW"
FF_LINEAR_APPROVED = "LINEAR_FORM_APPROVED"
FF_NONLINEAR_APPROVED = "NONLINEAR_FORM_APPROVED"
FF_NONLINEARITY_REVIEW_REQUIRED = "NONLINEARITY_REVIEW_REQUIRED"
FF_INSUFFICIENT_INFO = "INSUFFICIENT_INFORMATION_FOR_FORM_REVIEW"
VALID_FUNCTIONAL_FORM_STATUSES = {
    FF_NOT_APPLICABLE,
    FF_PENDING_REVIEW,
    FF_LINEAR_APPROVED,
    FF_NONLINEAR_APPROVED,
    FF_NONLINEARITY_REVIEW_REQUIRED,
    FF_INSUFFICIENT_INFO,
}

# ---------------------------------------------------------------------------
# FINAL FUNCTIONAL-FORM LOCK (manual decisions, informed by the independently
# reviewed functional-form diagnostics under outputs/publication_analysis/
# audit/). These are DATA-INFORMED, EXPLORATORY methodological decisions, not
# prospectively prespecified ones: reporting units were chosen for clinical
# interpretability first, and the subsequent linear-vs-nonlinear functional-
# form review then used the observed study data and outcome. No functional
# form here was selected by an automatic p<0.05 rule and no outcome-derived
# cutpoint was created; the manual decision weighed robust cluster-robust
# Wald evidence, fitted-curve shape, data support, sparsity, clinical
# plausibility, and parsimony. Inferential findings for these predictors
# remain exploratory rather than confirmatory.
# ---------------------------------------------------------------------------
FINAL_LINEAR_FORM_APPROVED_PREDICTORS = {
    "AGE", "BMI_before", "height", "Hb_before_delivery", "G", "AB",
}
FINAL_NONLINEAR_FORM_APPROVED_PREDICTORS = {
    "weight_before_pregnancy", "gestational_age_at_delivery_days",
}
FINAL_DESCRIPTIVE_ONLY_LOCKED_PREDICTORS = {"P", "CS", "LIVE_BIRTH"}

FUNCTIONAL_FORM_LOCK_DISCLOSURE = (
    "FINAL FUNCTIONAL-FORM LOCK (manual, data-informed, exploratory decision): "
    "the reporting unit was chosen for clinical interpretability, and the "
    "linear-vs-nonlinear functional-form review that followed used the "
    "observed study data and outcome -- this is a data-informed exploratory "
    "methodological decision, not a prospectively prespecified one. No "
    "functional form was selected by an automatic p<0.05 rule and no "
    "outcome-derived cutpoint was created. The manual decision weighed "
    "cluster-robust Wald evidence, fitted-curve shape, data support, "
    "sparsity, clinical plausibility, and parsimony. Inferential findings "
    "remain exploratory rather than confirmatory."
)

# ===========================================================================
# Checkpoint B — full 81-row publication representation contract
# ===========================================================================
# One row per canonical source predictor, in canonical registry order. Every
# non-trivial representation decision is grounded in an existing repository
# source (persisted in ``source_of_decision``); where no defensible
# reference / order / unit is on record, the row is left
# ``PENDING_REPRESENTATION_REVIEW`` rather than having one invented.
#
# ``inferential_role`` is EXACTLY one of the six values below (CHECKPOINT B §1).
ROLE_BINARY = "BINARY"
ROLE_CONTINUOUS = "CONTINUOUS"
ROLE_COUNT = "COUNT"
ROLE_CATEGORICAL = "CATEGORICAL"
ROLE_DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"
ROLE_PENDING = "PENDING_REPRESENTATION_REVIEW"
VALID_INFERENTIAL_ROLES = {
    ROLE_BINARY,
    ROLE_CONTINUOUS,
    ROLE_COUNT,
    ROLE_CATEGORICAL,
    ROLE_DESCRIPTIVE_ONLY,
    ROLE_PENDING,
}

PUBLICATION_REPRESENTATION_CONTRACT_COLUMNS = [
    "predictor",
    "physical_type",
    "earliest_entry_stage",
    "canonical_model_representation",
    "model_entry_mode",
    "publication_status",
    "publication_value_source",
    "publication_representation",
    "inferential_role",
    "binary_semantic_status",
    "reference_label",
    "comparison_label",
    "clinical_unit",
    "native_unit",
    "reporting_unit",
    "continuous_unit_scale",
    "reference_level",
    "category_order",
    "raw_code_to_publication_label",
    "functional_form_status",
    "source_of_decision",
    "needs_clinical_signoff",
    "reason",
]

REPRESENTATION_REVIEW_TABLE_COLUMNS = [
    "predictor",
    "physical_type",
    "earliest_entry_stage",
    "inferential_role",
    "publication_status",
    "reference_level",
    "category_order",
    "native_unit",
    "reporting_unit",
    "continuous_unit_scale",
    "functional_form_status",
    "source_of_decision",
    "reason",
    "needs_clinical_signoff",
]

# publication_value_source vocabulary
VS_RAW_CLEANED = "raw_cleaned_column"
VS_RECOMPUTED = "deterministic_recomputed_column"
VS_DERIVED_CATEGORICAL = "derived_categorical_column"
VS_TRANSFORM_SOURCE_RAW = "fold_safe_transform_source_raw_column"


class PublicationRepresentationContractError(RuntimeError):
    """Raised when the 81-row representation contract violates its own invariants."""


# --- continuous predictors with a proposed clinically interpretable scale ----
# (native_unit, reporting_unit, continuous_unit_scale, clinical_unit,
#  publication_value_source, source_of_decision, reason)
_CONTINUOUS_SPEC: dict[str, dict[str, object]] = {
    "AGE": {
        "native_unit": "years",
        "reporting_unit": "1 year",
        "continuous_unit_scale": 1.0,
        "clinical_unit": "years",
        "publication_value_source": VS_RAW_CLEANED,
        "functional_form_status": FF_LINEAR_APPROVED,
        "source_of_decision": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml (AGE: value in years) "
            "+ CLAUDE.md Approved Clinical Rules (native clinical unit, no fold transform) "
            "+ FINAL FUNCTIONAL-FORM LOCK (ordinary one-slope logistic association, subject-"
            "cluster-robust covariance)"
        ),
        "reason": (
            "Native clinical unit; OR reported per 1 year, one-slope logistic association. "
            "LINEAR_FORM_APPROVED (final, locked). " + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
    "BMI_before": {
        "native_unit": "kg/m^2",
        "reporting_unit": "1 kg/m^2",
        "continuous_unit_scale": 1.0,
        "clinical_unit": "kg/m^2",
        "publication_value_source": VS_RECOMPUTED,
        "functional_form_status": FF_LINEAR_APPROVED,
        "source_of_decision": (
            "CLAUDE.md 'Anthropometry / Hb missingness (Data Cleaning B)' "
            "+ manual_decisions_log.md Decision 27 "
            "(deterministically recomputed from observed weight/height only; NaN if either input missing) "
            "+ FINAL FUNCTIONAL-FORM LOCK (ordinary one-slope logistic association, subject-"
            "cluster-robust covariance)"
        ),
        "reason": (
            "Three distinct things, never interchangeable, none implying "
            "the others: "
            "(1) Data Cleaning B defines the canonical treatment POLICY and "
            "component-level reconstruction STRATEGY for BMI_before, but "
            "does not itself median-impute BMI_before directly and does not "
            "fit any predictive-CV median on the full cohort -- its own "
            "output (used for THIS univariable/descriptive representation) "
            "is a deterministic recompute from observed "
            "height/weight_before_pregnancy only, with NaN preserved "
            "whenever either input is missing (complete-case here, no "
            "imputation at this stage). "
            "(2) The predictive Decision 99 Compact Ridge model (locked "
            "internal-validation nested CV) also never median-imputes "
            "BMI_before directly: when a component is missing, the "
            "height/weight_before_pregnancy medians it uses are learned "
            "ONLY inside the relevant outer/inner TRAINING FOLD, via "
            "`FoldSafeRecomputedBMITransformer`, and BMI_before is then "
            "recomputed from those fold-safe components -- never from a "
            "full-cohort median for this predictive use. "
            "(3) The one-time final full-data refit and the separate "
            "secondary six-predictor adjusted-OR/Firth analysis both reuse "
            "the identical `FoldSafeRecomputedBMITransformer` component-level "
            "strategy, but fit its medians on their own corresponding full "
            "analysis dataset (the full 431-row refit cohort, and the "
            "full-cohort secondary analysis, respectively) rather than a "
            "training fold -- Modeling implements each of these data-derived "
            "steps at the correct scope (fold-safe for (2), full-cohort for "
            "(3)); this contract row is Data Cleaning B's own complete-case "
            "representation only and reflects none of them. OR reported per "
            "1 kg/m^2, one-slope logistic association. LINEAR_FORM_APPROVED "
            "(final, locked). " + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
    "height": {
        "native_unit": "cm",
        "reporting_unit": "5 cm",
        "continuous_unit_scale": 5.0,
        "clinical_unit": "cm",
        "publication_value_source": VS_RAW_CLEANED,
        "functional_form_status": FF_LINEAR_APPROVED,
        "source_of_decision": (
            "CLAUDE.md 'Anthropometry / Hb missingness (Data Cleaning B)' "
            "(raw cm retained, NaN preserved, no imputation in Data Cleaning B) "
            "+ FINAL FUNCTIONAL-FORM LOCK (ordinary one-slope logistic association, subject-"
            "cluster-robust covariance)"
        ),
        "reason": (
            "Raw clinical unit; OR reported per 5 cm, one-slope logistic association. "
            "LINEAR_FORM_APPROVED (final, locked). " + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
    "weight_before_pregnancy": {
        "native_unit": "kg",
        "reporting_unit": "Nonlinear spline (df=3)",
        "continuous_unit_scale": None,
        "clinical_unit": "kg",
        "publication_value_source": VS_RAW_CLEANED,
        "functional_form_status": FF_NONLINEAR_APPROVED,
        "source_of_decision": (
            "CLAUDE.md 'Anthropometry / Hb missingness (Data Cleaning B)' "
            "(raw kg retained, NaN preserved, no imputation in Data Cleaning B) "
            "+ FINAL FUNCTIONAL-FORM LOCK (fixed natural cubic spline, df=3, "
            "patsy cr(x, df=3, constraints=\"center\"); source-level spline omnibus "
            "cluster-robust Wald association -- no single OR)"
        ),
        "reason": (
            "Raw clinical unit (kg). NONLINEAR_FORM_APPROVED (final, locked): final "
            "inferential representation is a fixed natural cubic spline (df=3); the "
            "source-level result is a spline omnibus cluster-robust Wald p-value, not a "
            "per-unit OR -- no single spline-basis coefficient is clinically interpreted. "
            + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
    "Hb_before_delivery": {
        "native_unit": "g/dL",
        "reporting_unit": "1 g/dL",
        "continuous_unit_scale": 1.0,
        "clinical_unit": "g/dL",
        "publication_value_source": VS_RAW_CLEANED,
        "functional_form_status": FF_LINEAR_APPROVED,
        "source_of_decision": (
            "CLAUDE.md 'Hb_before_delivery, Hb_after_delivery — in-place cleaning' "
            "(cleaned to numeric g/dL; NaN preserved, imputation training-fold-only downstream) "
            "+ FINAL FUNCTIONAL-FORM LOCK (ordinary one-slope logistic association, subject-"
            "cluster-robust covariance)"
        ),
        "reason": (
            "Numeric g/dL; OR reported per 1 g/dL, one-slope logistic association. "
            "LINEAR_FORM_APPROVED (final, locked). " + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
    "gestational_age_at_delivery_days": {
        "native_unit": "days",
        "reporting_unit": "Nonlinear spline (df=3)",
        "continuous_unit_scale": None,
        "clinical_unit": "weeks of gestation (stored as integer days)",
        "publication_value_source": VS_RAW_CLEANED,
        "functional_form_status": FF_NONLINEAR_APPROVED,
        "source_of_decision": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml "
            "(gestational_age_at_delivery: weeks + days); stored as integer days in the EDA C matrix "
            "+ FINAL FUNCTIONAL-FORM LOCK (fixed natural cubic spline, df=3, "
            "patsy cr(x, df=3, constraints=\"center\"); source-level spline omnibus "
            "cluster-robust Wald association -- no single OR)"
        ),
        "reason": (
            "Continuous gestational age; native days. NONLINEAR_FORM_APPROVED (final, "
            "locked): final inferential representation is a fixed natural cubic spline "
            "(df=3); the source-level result is a spline omnibus cluster-robust Wald "
            "p-value, not a per-unit OR -- no single spline-basis coefficient is clinically "
            "interpreted. This predictor is Stage 3 / intrapartum-horizon -- any future "
            "interpretation must describe it as an association available at the Stage-3 "
            "horizon, not a baseline risk factor. " + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
}

# FINAL FUNCTIONAL-FORM LOCK: only G and AB remain ordinary whole-cohort COUNT
# predictors. P, CS, and LIVE_BIRTH are now DESCRIPTIVE_ONLY (see
# _DESCRIPTIVE_ONLY_SPEC below) -- they are never fit as a primary
# whole-cohort per-additional-unit OR.
_COUNT_SPEC: dict[str, dict[str, object]] = {
    "G": {
        "reporting_unit": "1 pregnancy",
        "clinical_unit": "count (number of pregnancies, including the current one)",
        "functional_form_status": FF_LINEAR_APPROVED,
        "source_of_decision": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml "
            "(G: number of pregnancies, including the current one) "
            "+ FINAL FUNCTIONAL-FORM LOCK (ordinary one-slope count association, subject-"
            "cluster-robust covariance)"
        ),
        "reason": (
            "Ordinary obstetric-history count; OR reported per 1 pregnancy, one-slope "
            "logistic association. The full observed count support is retained; the upper "
            "tail is sparse (documented, not merged). No cutoff or grouped G predictor is "
            "created. LINEAR_FORM_APPROVED (final, locked). " + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
    "AB": {
        "reporting_unit": "1 pregnancy loss / abortion",
        "clinical_unit": "count (number of abortions / pregnancy losses)",
        "functional_form_status": FF_LINEAR_APPROVED,
        "source_of_decision": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml "
            "(AB: number of abortions / pregnancy losses) "
            "+ FINAL FUNCTIONAL-FORM LOCK (ordinary one-slope count association, subject-"
            "cluster-robust covariance)"
        ),
        "reason": (
            "Ordinary obstetric-history count; OR reported per 1 pregnancy loss / abortion, "
            "one-slope logistic association. The raw count is retained; no cutoff or "
            "grouping is created. LINEAR_FORM_APPROVED (final, locked). "
            + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
}

# --- categoricals with a repository-supported reference AND category order ----
_CATEGORICAL_APPROVED: dict[str, dict[str, object]] = {
    "endometrioma_size_status": {
        "reference_level": "no_endometrioma",
        "category_order": [
            "no_endometrioma",
            "endometrioma_less_than_30mm",
            "endometrioma_30mm_or_more",
            "endometrioma_size_unknown",
        ],
        "source_of_decision": (
            "CLAUDE.md Approved Clinical Rules 'Endometrioma derived variables (Data Cleaning B)' "
            "+ manual_decisions_log.md Decisions 22/24/25/70/84 "
            "(explicit 4-level enumeration; clinically-sourced 30 mm cutoff; unknown is an explicit category)"
        ),
        "reason": (
            "Reference = absence of endometrioma; order follows the documented clinical size gradient "
            "with the explicit unknown category last. Clinical sign-off given (Representation Sign-off task)."
        ),
    },
    "endometrioma_presence_laterality": {
        "reference_level": "none",
        "category_order": ["none", "unilateral", "bilateral", "laterality_unknown"],
        "source_of_decision": (
            "CLAUDE.md Approved Clinical Rules 'Endometrioma derived variables (Data Cleaning B)' "
            "+ manual_decisions_log.md Decisions 22/24/25/70/84 "
            "(explicit 4-level enumeration; right/left intentionally collapsed)"
        ),
        "reason": (
            "Reference = no endometrioma; order none < unilateral < bilateral with the explicit "
            "unknown-laterality category last. Clinical sign-off given (Representation Sign-off task)."
        ),
    },
    "any_PET_cat": {
        "reference_level": "absent",
        "category_order": ["absent", "present", "not_documented"],
        "source_of_decision": (
            "CLAUDE.md Approved Clinical Rules '(severe_PET / any_PET)' "
            "+ manual_decisions_log.md Decisions 27/71/94 "
            "(explicit present/absent/not_documented enumeration; approved Stage-1 predictor_allowed)"
        ),
        "reason": (
            "Reference = preeclampsia absent; documented-status categorical with the explicit "
            "not_documented category last. Clinical sign-off given (Representation Sign-off task)."
        ),
    },
    "severe_PET_cat": {
        "reference_level": "absent",
        "category_order": ["absent", "present", "not_documented"],
        "source_of_decision": (
            "CLAUDE.md Approved Clinical Rules '(severe_PET / any_PET)' "
            "+ manual_decisions_log.md Decisions 27/71/94 "
            "(explicit present/absent/not_documented enumeration; approved Stage-1 predictor_allowed)"
        ),
        "reason": (
            "Reference = severe preeclampsia absent; documented-status categorical with the explicit "
            "not_documented category last. Only 2 'present' rows — separation risk noted. Clinical sign-off given (Representation Sign-off task)."
        ),
    },
    # --- newly resolved (Representation Sign-off + Functional-Form Gate task) --
    "derived_diabetes_type_grouped": {
        "reference_level": "no_diabetes",
        "category_order": ["no_diabetes", "pregestational", "GDMA1", "GDMA2"],
        "source_of_decision": (
            "analysis/eda/notebook_build/eda_c/eda_c_part3_feature_engineering.py "
            "DERIVED_FEATURE_CONTRACTS['derived_diabetes_type_grouped'] "
            "(deterministic grouping: 0->no_diabetes, 1/2/3->pregestational, 4->GDMA1, 5->GDMA2) "
            "+ Representation Sign-off task (clinical-meaning-based display order approved)"
        ),
        "reason": (
            "NOMINAL dummy-coded categorical; reference = no_diabetes. The display order "
            "(no_diabetes, pregestational, GDMA1, GDMA2) does NOT imply a numeric severity scale "
            "-- it reflects clinical grouping/interpretability, not outcome association. "
            "Clinical sign-off given (Representation Sign-off task)."
        ),
    },
    "derived_hypertension_pih_pet_spectrum": {
        "reference_level": "no_hypertensive_disorder",
        "category_order": ["no_hypertensive_disorder", "pih_gestational_htn", "preeclampsia_spectrum"],
        "source_of_decision": (
            "analysis/eda/notebook_build/eda_c/eda_c_part3_feature_engineering.py "
            "DERIVED_FEATURE_CONTRACTS['derived_hypertension_pih_pet_spectrum'] "
            "+ Representation Sign-off task (clinical-meaning-based display order approved)"
        ),
        "reason": (
            "NOMINAL dummy-coded categorical; reference = no_hypertensive_disorder. The three "
            "states are not modeled as a numeric score. Existing unresolved-state missingness "
            "behavior is preserved -- unresolved PET documentation is never converted to absence. "
            "Clinical sign-off given (Representation Sign-off task)."
        ),
    },
    "derived_prior_endo_surgery_procedure_status": {
        "reference_level": "no_prior_endo_surgery",
        "category_order": [
            "no_prior_endo_surgery",
            "prior_surgery_no_selected_procedure_documented",
            "prior_surgery_with_selected_procedure_documented",
        ],
        "source_of_decision": (
            "analysis/eda/notebook_build/eda_c/eda_c_part3_feature_engineering.py "
            "DERIVED_FEATURE_CONTRACTS['derived_prior_endo_surgery_procedure_status'] "
            "+ Representation Sign-off task (exploratory categorical approved)"
        ),
        "reason": (
            "EXPLORATORY nominal dummy-coded categorical; reference = no_prior_endo_surgery. "
            "'prior_surgery_no_selected_procedure_documented' means EXACTLY: prior endometriosis "
            "surgery with none of the SELECTED structured procedure indicators documented as "
            "positive -- it must never be read as 'no procedure' / 'no resection' / 'no treatment', "
            "since the selected structured variables are only a subset of possible procedures. "
            "Association only, no causal-effect language. Clinical sign-off given (Representation "
            "Sign-off task)."
        ),
    },
    "derived_endo_surgery_adhesion_status": {
        "reference_level": "no_prior_endo_surgery",
        "category_order": [
            "no_prior_endo_surgery",
            "prior_surgery_without_documented_adhesions",
            "prior_surgery_with_documented_adhesions",
        ],
        "source_of_decision": (
            "analysis/data_cleaning/notebook_build/data_cleaning_b/"
            "cleaning_b_part4_transformations_imputation_plan.py "
            "(3-level status) + Representation Sign-off task (exploratory categorical approved)"
        ),
        "reason": (
            "EXPLORATORY nominal dummy-coded categorical; reference = no_prior_endo_surgery. "
            "'without documented adhesions' is a documentation/finding state, not overstated as "
            "biological proof adhesions were absent. Association only, no causal-effect language. "
            "Clinical sign-off given (Representation Sign-off task)."
        ),
    },
    "smoking": {
        "reference_level": "non_smoker",
        "category_order": ["non_smoker", "former_smoker", "current_smoker"],
        "source_of_decision": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml "
            "(smoking: 0 = non-smoker, 1 = current smoker, 2 = former smoker) "
            "+ Representation Sign-off task (publication label set + display order approved)"
        ),
        "reason": (
            "NOMINAL categorical; reference = non_smoker. Publication labels (non_smoker / "
            "former_smoker / current_smoker) map from the established raw source codes "
            "(0/1/2) -- see raw_code_to_publication_label. The DISPLAY order "
            "(non_smoker, former_smoker, current_smoker) intentionally differs from the raw "
            "numeric code order (0=non-smoker, 1=current, 2=former) and carries no ordinal "
            "meaning; raw codes must never be used as a continuous predictor. Former/current "
            "smoking are not combined merely because a level is sparse -- if inference proves "
            "unstable, the sparse/non-estimable status is reported instead of collapsing levels. "
            "Clinical sign-off given (Representation Sign-off task)."
        ),
    },
    "mode_of_conception": {
        "reference_level": "spontaneous",
        "category_order": ["spontaneous", "IUI", "IVF", "other_fertility_treatment"],
        "source_of_decision": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml "
            "(mode_of_conception: 0 = spontaneous, 1 = IVF, 2 = IUI, 3 = other fertility treatment) "
            "+ Representation Sign-off task (publication label set + display order approved)"
        ),
        "reason": (
            "NOMINAL categorical; reference = spontaneous. Publication labels (spontaneous / IVF / "
            "IUI / other_fertility_treatment) map from the established raw source codes (0/1/2/3) "
            "-- see raw_code_to_publication_label. Display order has no ordinal numerical meaning; "
            "IUI/IVF/other are never collapsed based on observed outcomes. The separate canonical "
            "binary source predictor mode_of_conception_ivf_vs_all is unaffected and unaltered by "
            "this decision -- any redundancy between the two is reporting context, not a reason to "
            "change the frozen 81-predictor inventory. Clinical sign-off given (Representation "
            "Sign-off task)."
        ),
    },
}

# Raw numeric source code -> publication display label, for categoricals whose
# analysis-matrix column stores opaque integer codes rather than pre-labeled
# strings (Representation Sign-off task §5E/§5F). This mapping is contract
# metadata only -- it does not itself relabel any data, and the canonical
# analysis matrix is never mutated. The centralized publication-preparation
# layer ``prepare_predictor_for_publication_inference(...)`` applies it, and
# ``run_univariable_master()`` routes every categorical predictor through that
# layer before fitting. Any non-missing raw code with no entry in the mapping
# fails loud (``PublicationLabelMappingError``) -- it is never silently dropped
# or given a guessed label.
_RAW_CODE_TO_LABEL: dict[str, dict[int, str]] = {
    "smoking": {0: "non_smoker", 1: "current_smoker", 2: "former_smoker"},
    "mode_of_conception": {0: "spontaneous", 1: "IVF", 2: "IUI", 3: "other_fertility_treatment"},
    # DESCRIPTIVE_ONLY (Table 1 display only -- diabetes_type is never fitted
    # inferentially; see _DESCRIPTIVE_ONLY_SPEC below). Restated verbatim from
    # this predictor's own already-approved source_of_decision/reason text
    # above and docs/data_dictionary/clinical_variable_dictionary.yaml
    # (diabetes_type codes_he: "0 - No diabetes, 1 - Pregestational diabetes,
    # 2 - Diabetes type 1, 3 - Diabetes type 2, 4 - GDMA1, 5 - GDMA2").
    "diabetes_type": {
        0: "no_diabetes",
        1: "pregestational_diabetes",
        2: "diabetes_type_1",
        3: "diabetes_type_2",
        4: "GDMA1",
        5: "GDMA2",
    },
}

_DESCRIPTIVE_ONLY_SPEC: dict[str, dict[str, object]] = {
    # --- FINAL FUNCTIONAL-FORM LOCK §1C: moved from COUNT to DESCRIPTIVE_ONLY ---
    "P": {
        "clinical_unit": "count (number of previous deliveries)",
        "native_unit": "count",
        "publication_value_source": VS_RAW_CLEANED,
        "source_of_decision": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml "
            "(P: number of previous deliveries) + FINAL FUNCTIONAL-FORM LOCK"
        ),
        "reason": (
            "Moved to DESCRIPTIVE_ONLY (final, locked): the clinically important contrast "
            "is largely nulliparous vs parous, and the project already contains the "
            "corrected canonical nulliparity predictor (BINARY, EXPLICITLY_DOCUMENTED). No "
            "new P categories are created after viewing the outcome; no primary "
            "whole-cohort per-additional-delivery OR is fitted. Remains fully visible in "
            "Table 1, the representation/quality audit, and descriptive support outputs. "
            + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
    "CS": {
        "clinical_unit": "count (number of previous cesarean sections)",
        "native_unit": "count",
        "publication_value_source": VS_RAW_CLEANED,
        "source_of_decision": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml "
            "(CS: number of previous cesarean sections) + FINAL FUNCTIONAL-FORM LOCK"
        ),
        "reason": (
            "Moved to DESCRIPTIVE_ONLY (final, locked): support above zero is very sparse, "
            "and the project already contains the clinically interpretable binary S_P_CS "
            "predictor (BINARY, EXPLICITLY_DOCUMENTED). No per-additional-CS OR is used. "
            "Remains fully visible in Table 1, the representation/quality audit, and "
            "descriptive support outputs. " + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
    "LIVE_BIRTH": {
        "clinical_unit": "count (number of previous live births)",
        "native_unit": "count",
        "publication_value_source": VS_RAW_CLEANED,
        "source_of_decision": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml "
            "(LIVE_BIRTH: number of previous live births) + FINAL FUNCTIONAL-FORM LOCK"
        ),
        "reason": (
            "Moved to DESCRIPTIVE_ONLY (final, locked): the observed pattern does not "
            "support a simple constant +1 interpretation, and no prospectively justified "
            "alternative grouping exists. No 0-vs-1+ or other outcome-inspected grouping is "
            "invented. Remains fully visible in Table 1, the representation/quality audit, "
            "and descriptive support outputs. " + FUNCTIONAL_FORM_LOCK_DISCLOSURE
        ),
    },
    "gestational_age_at_PPROM_days": {
        "clinical_unit": "days of gestation at PPROM (PPROM subgroup only)",
        "native_unit": "days",
        "publication_value_source": VS_TRANSFORM_SOURCE_RAW,
        "source_of_decision": (
            "outputs/eda_c/candidate_model_features.csv "
            "(model_entry_mode=transform_source_only, FS_PPROM_TIMING_CAT_V1); "
            "structurally observed only in the PPROM subgroup (415/431 rows missing)"
        ),
        "reason": (
            "Structurally defined only within the PPROM subgroup, so it is not an ordinary "
            "whole-cohort fixed predictor. Descriptive information is preserved transparently; "
            "it is not entered into the primary whole-cohort univariable association analysis, and "
            "the predictive pipeline's fold-safe PPROM-timing categorical is not reused here. A "
            "future PPROM-only subgroup analysis is a separate question, out of scope here. "
            "KEPT DESCRIPTIVE_ONLY (Representation Sign-off task)."
        ),
    },
    # --- newly resolved DESCRIPTIVE_ONLY (Representation Sign-off task §6) ---
    "indication_for_induction_status": {
        "clinical_unit": "induction indication status (high-cardinality)",
        "native_unit": "category label",
        "publication_value_source": VS_DERIVED_CATEGORICAL,
        "source_of_decision": (
            "outputs/eda_c/candidate_model_features.csv (physical_n_categories = 22); "
            "Representation Sign-off task §6A"
        ),
        "reason": (
            "High-cardinality field (~22 observed levels/combinations representing heterogeneous "
            "induction indications); with only 61 target events, an ordinary many-parameter "
            "categorical association model is not supported. No post-hoc outcome-driven grouping "
            "is used to force estimability. Retained fully in descriptive tables / quality audit."
        ),
    },
    "diabetes_type": {
        "clinical_unit": "raw diabetes code (6-level, retained for transparency)",
        "native_unit": "category label",
        "publication_value_source": VS_RAW_CLEANED,
        "source_of_decision": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml "
            "(diabetes_type: 0 = No diabetes, 1 = Pregestational, 2 = Type 1, 3 = Type 2, 4 = GDMA1, "
            "5 = GDMA2) + Representation Sign-off task §6B"
        ),
        "reason": (
            "The raw 6-code representation contains sparse subtypes and is not an ordinal severity "
            "scale. The clinically interpretable derived_diabetes_type_grouped representation is now "
            "APPROVED for inferential analysis (see _CATEGORICAL_APPROVED); reporting two competing "
            "inferential parameterizations of the same raw coding is avoided without scientific "
            "reason. Raw diabetes_type is retained descriptively for transparency only -- its Table 1 "
            "levels are shown using this same documented code dictionary (see "
            "_RAW_CODE_TO_LABEL['diabetes_type']) rather than the bare numeric codes; this is a "
            "display-only mapping and never feeds any inferential fit."
        ),
    },
    "weight_in_pregnancy": {
        "clinical_unit": "kg (raw, self-reported, non-standardized timing)",
        "native_unit": "kg",
        "publication_value_source": VS_TRANSFORM_SOURCE_RAW,
        "source_of_decision": (
            "CLAUDE.md 'weight_in_pregnancy (current)' + Data Cleaning B README "
            "(secondary_near_delivery_predictor; approved predictive representation is the fold-safe "
            "weight_in_pregnancy_cat quantile categorical fitted training-fold-only) "
            "+ Representation Sign-off task §6C"
        ),
        "reason": (
            "Measurement timing is not sufficiently standardized (self-reported, non-standardized "
            "timing). The canonical predictive representation is fold-safe / training-fold fitted; "
            "those quantile cutpoints are not reused for inference, and no new clinical cutpoint is "
            "invented. Raw values remain useful descriptively."
        ),
    },
    "BMI_after": {
        "clinical_unit": "kg/m^2 (raw, postpartum/discharge-influenced timing)",
        "native_unit": "kg/m^2",
        "publication_value_source": VS_TRANSFORM_SOURCE_RAW,
        "source_of_decision": (
            "CLAUDE.md 'BMI_after (current)' "
            "+ manual_decisions_log.md Decisions 39/40/61/69/86/87/88/89/91 "
            "(secondary_near_delivery_predictor; approved predictive representation is the fold-safe "
            "BMI_after_cat tertile categorical fitted training-fold-only; no fixed clinical cutpoint "
            "documented) + Representation Sign-off task §6D"
        ),
        "reason": (
            "Near-delivery / postpartum-discharge-influenced timing. The predictive representation "
            "uses training-fold cutpoints; no fixed clinical publication cutpoint is justified, and "
            "fold-specific tertiles are not reused for inference. Raw values remain descriptive."
        ),
    },
}

# All 10 predictors that were previously PENDING_REPRESENTATION_REVIEW have
# now been resolved (Representation Sign-off task): 6 moved to
# _CATEGORICAL_APPROVED (derived_diabetes_type_grouped,
# derived_hypertension_pih_pet_spectrum, derived_prior_endo_surgery_procedure_
# status, derived_endo_surgery_adhesion_status, smoking, mode_of_conception)
# and 4 moved to _DESCRIPTIVE_ONLY_SPEC (indication_for_induction_status,
# diabetes_type, weight_in_pregnancy, BMI_after). This dict remains as the
# architectural fallback for any FUTURE predictor with no defensible
# reference/order/unit on record -- it is empty by design, not because the
# PENDING_REPRESENTATION_REVIEW code path was removed.
_PENDING_SPEC: dict[str, dict[str, str]] = {}

# --- binary predictors with a repository source that EXPLICITLY states what
# 0 and 1 mean for THAT predictor (Checkpoint-B targeted-correction §2).
# Found by a read-only audit of analysis/preprocessing/run_preprocessing.py
# (log_deviation_event 'documented=' annotations whose text itself states a
# 0/1 -> meaning mapping — not merely that a documented= field exists),
# CLAUDE.md, and docs/data_dictionary/clinical_variable_dictionary.yaml
# codes_he. For every OTHER binary predictor, physical_variable_type=binary /
# model_representation_type=binary_passthrough establishes only the numeric
# 0/1 coding itself, never a predictor-specific clinical present/absent
# meaning -- those predictors are BINARY_SEMANTIC_GENERIC (see
# _contract_row_for), and their reference/comparison labels are only ever
# "value 0" / "value 1 vs value 0", never "absent"/"present"/"no"/"yes".
_BINARY_EXPLICIT_SEMANTICS: dict[str, dict[str, str]] = {
    "nulliparity": {
        "reference_label": "value 0 = one or more prior deliveries",
        "comparison_label": "value 1 = no prior deliveries",
        "semantic_source": (
            "analysis/preprocessing/run_preprocessing.py "
            '(log_deviation_event documented="Binary 0/1: 1 = no prior deliveries, '
            '0 = one or more prior deliveries.")'
        ),
    },
    "S_P_CS": {
        "reference_label": "value 0 = no previous CS",
        "comparison_label": "value 1 = previous CS",
        "semantic_source": (
            "analysis/preprocessing/run_preprocessing.py "
            '(documented="Binary field: 0=no previous CS, 1=previous CS") '
            "+ CLAUDE.md 'S_P_CS — Status Post Cesarean Section' (1=yes, 0=no)"
        ),
    },
    "adenomyosis": {
        # Re-audited (Checkpoint-B final micro-correction #4): the original
        # citation only established what value 1 means (via the QA
        # correction rule). A second, independent repository source
        # explicitly states what value 0 means: Data Cleaning B's multi-hot
        # adenomyosis-feature derivation
        # (analysis/data_cleaning/notebook_build/data_cleaning_b/
        # cleaning_b_part4_transformations_imputation_plan.py, ~line 1088-90)
        # states verbatim: "`adenomyosis == 0` rows: all 11 indicators are
        # `0` (no redundant `no_adenomyosis` category is created here --
        # the existing binary `adenomyosis` variable already represents
        # disease absence)." Both values are now explicitly documented from
        # genuine repository sources -- EXPLICITLY_DOCUMENTED retained.
        "reference_label": "value 0 = disease absence (no adenomyosis)",
        "comparison_label": (
            "value 1 = adenomyosis present (QA rule: sonographic feature codes 1-10 "
            "present -> must be 1)"
        ),
        "semantic_source": (
            "analysis/preprocessing/run_preprocessing.py "
            '(documented="Binary 0/1. Documented QA rule: if sonographic features include '
            'codes 1-10, adenomyosis must be 1.") establishes value 1; '
            "analysis/data_cleaning/notebook_build/data_cleaning_b/"
            "cleaning_b_part4_transformations_imputation_plan.py "
            '(SB5F_ADENOMYOSIS section: "the existing binary `adenomyosis` variable already '
            'represents disease absence" for adenomyosis == 0 rows) establishes value 0'
        ),
    },
    "endometriosis_surgery": {
        "reference_label": "value 0 = no surgery",
        "comparison_label": "value 1 = surgery",
        "semantic_source": (
            "analysis/preprocessing/run_preprocessing.py "
            '(documented="Binary field: 0=no surgery, 1=surgery.")'
        ),
    },
    "Fetus_Anamoly": {
        "reference_label": "value 0 = no documented fetal problem",
        "comparison_label": "value 1 = documented fetal problem",
        "semantic_source": (
            "analysis/preprocessing/run_preprocessing.py "
            '(documented="Binary field: 0=no documented fetal problem, '
            '1=documented fetal problem")'
        ),
    },
    "mode_of_conception_ivf_vs_all": {
        "reference_label": "value 0 = other fertility treatment or no treatment (טיפול אחר או ללא טיפול)",
        "comparison_label": "value 1 = IVF (הפריה חוץ גופית)",
        "semantic_source": (
            "docs/data_dictionary/clinical_variable_dictionary.yaml "
            "(mode_of_conception_ivf_vs_all codes_he: "
            "\"1 - IVF (הפריה חוץ גופית), "
            "0 - טיפול אחר או ללא טיפול\")"
        ),
    },
}

_BINARY_GENERIC_SOURCE_OF_DECISION = (
    "outputs/eda_c/candidate_model_features.csv: physical_variable_type=binary, "
    "model_representation_type=binary_passthrough. This establishes only the canonical "
    "0/1 numeric coding for this predictor -- no predictor-specific repository source "
    "establishes which of 0/1 corresponds to a particular clinical meaning (e.g. "
    "presence vs. absence) for THIS predictor. binary_passthrough is a machine-"
    "representation fact, not a per-predictor clinical-semantics claim."
)


@dataclass
class PublicationRepresentationContractSummary:
    n_total: int
    n_by_role: dict[str, int]
    n_by_publication_status: dict[str, int]
    n_by_binary_semantic_status: dict[str, int]
    n_by_functional_form_status: dict[str, int]
    n_needs_signoff: int
    pending_predictors: list[str]
    pending_clinical_signoff_predictors: list[str]
    functional_form_review_predictors: list[str]


def _blank_contract_row(
    predictor: str,
    physical_type: str,
    earliest_entry_stage: object = None,
    canonical_model_representation: object = None,
    model_entry_mode: object = None,
) -> dict[str, object]:
    return {
        "predictor": predictor,
        "physical_type": physical_type,
        "earliest_entry_stage": earliest_entry_stage,
        "canonical_model_representation": canonical_model_representation,
        "model_entry_mode": model_entry_mode,
        "publication_status": None,
        "publication_value_source": None,
        "publication_representation": None,
        "inferential_role": None,
        "binary_semantic_status": None,
        "reference_label": None,
        "comparison_label": None,
        "clinical_unit": None,
        "native_unit": None,
        "reporting_unit": "n/a",
        "continuous_unit_scale": None,
        "reference_level": None,
        "category_order": None,
        "raw_code_to_publication_label": None,
        # Safe default: only CONTINUOUS/COUNT roles override this to
        # FF_PENDING_REVIEW below. Every other role (BINARY, CATEGORICAL,
        # DESCRIPTIVE_ONLY, PENDING_REPRESENTATION_REVIEW) has no linear-
        # functional-form question to begin with.
        "functional_form_status": FF_NOT_APPLICABLE,
        "source_of_decision": None,
        "needs_clinical_signoff": None,
        "reason": None,
    }


def _contract_row_for(
    predictor: str,
    physical_type: str,
    earliest_entry_stage: object = None,
    canonical_model_representation: object = None,
    model_entry_mode: object = None,
) -> dict[str, object]:
    row = _blank_contract_row(
        predictor, physical_type, earliest_entry_stage, canonical_model_representation, model_entry_mode
    )

    if predictor in _PENDING_SPEC:
        spec = _PENDING_SPEC[predictor]
        row.update(
            publication_status=PENDING_REPRESENTATION_REVIEW,
            inferential_role=ROLE_PENDING,
            publication_value_source=spec["publication_value_source"],
            publication_representation="pending representation review — not fitted",
            clinical_unit="not yet defined (pending representation review)",
            native_unit="not yet defined",
            source_of_decision=spec["source_of_decision"],
            needs_clinical_signoff=True,
            reason=spec["reason"],
        )
        return row

    if predictor in _DESCRIPTIVE_ONLY_SPEC:
        spec = _DESCRIPTIVE_ONLY_SPEC[predictor]
        row.update(
            publication_status=DESCRIPTIVE_ONLY,
            inferential_role=ROLE_DESCRIPTIVE_ONLY,
            publication_value_source=spec["publication_value_source"],
            publication_representation=(
                f"descriptive only, raw {spec['native_unit']} — no fixed inferential representation"
            ),
            clinical_unit=spec["clinical_unit"],
            native_unit=spec["native_unit"],
            source_of_decision=spec["source_of_decision"],
            # A FINAL decision to describe-not-fit a predictor is itself a
            # completed clinical/methodological decision -- it is NOT an
            # awaiting-sign-off state. needs_clinical_signoff stays False so
            # these resolved rows never appear in the representation sign-off
            # review table.
            needs_clinical_signoff=False,
            reason=spec["reason"],
            # DISPLAY-ONLY (targeted closure pass): a DESCRIPTIVE_ONLY
            # predictor is never routed through run_univariable_master's
            # inferential dispatch (fit_status stays NOT_FITTED regardless of
            # this field), so populating raw_code_to_publication_label here
            # only makes Table 1's build_table1() show the already-documented
            # clinical labels for its raw numeric codes instead of the bare
            # 0/1/2/.../n values -- it never changes eligibility, category
            # membership, or any modeling/inferential result. None for every
            # DESCRIPTIVE_ONLY predictor without an entry in
            # _RAW_CODE_TO_LABEL (unchanged pass-through behavior).
            raw_code_to_publication_label=_RAW_CODE_TO_LABEL.get(predictor),
        )
        return row

    if predictor in _CATEGORICAL_APPROVED:
        spec = _CATEGORICAL_APPROVED[predictor]
        order = list(spec["category_order"])
        row.update(
            publication_status=APPROVED,
            inferential_role=ROLE_CATEGORICAL,
            publication_value_source=VS_DERIVED_CATEGORICAL,
            publication_representation=(
                f"APPROVED categorical (treatment/dummy coding), reference={spec['reference_level']!r}, "
                f"display order={order}"
            ),
            clinical_unit="categorical level",
            native_unit="category label",
            reference_level=spec["reference_level"],
            category_order=order,
            raw_code_to_publication_label=_RAW_CODE_TO_LABEL.get(predictor),
            functional_form_status=FF_NOT_APPLICABLE,
            source_of_decision=spec["source_of_decision"],
            needs_clinical_signoff=False,
            reason=spec["reason"],
        )
        return row

    if predictor in _CONTINUOUS_SPEC:
        spec = _CONTINUOUS_SPEC[predictor]
        ff_status = spec["functional_form_status"]
        if ff_status == FF_NONLINEAR_APPROVED:
            publication_representation = (
                f"APPROVED continuous, raw {spec['native_unit']} -- final inferential "
                "representation is a NONLINEAR natural cubic spline (df=3); no single OR "
                "(see functional_form_status / spline omnibus p-value)"
            )
        else:
            publication_representation = (
                f"APPROVED continuous, raw {spec['native_unit']}, OR per {spec['reporting_unit']} "
                "-- LINEAR functional form (final, locked)"
            )
        row.update(
            publication_status=APPROVED,
            inferential_role=ROLE_CONTINUOUS,
            publication_value_source=spec["publication_value_source"],
            publication_representation=publication_representation,
            clinical_unit=spec["clinical_unit"],
            native_unit=spec["native_unit"],
            reporting_unit=spec["reporting_unit"],
            continuous_unit_scale=spec["continuous_unit_scale"],
            functional_form_status=ff_status,
            source_of_decision=spec["source_of_decision"],
            needs_clinical_signoff=False,
            reason=spec["reason"],
        )
        return row

    if predictor in _COUNT_SPEC:
        spec = _COUNT_SPEC[predictor]
        row.update(
            publication_status=APPROVED,
            inferential_role=ROLE_COUNT,
            publication_value_source=VS_RAW_CLEANED,
            publication_representation=(
                f"APPROVED count, OR per {spec['reporting_unit']} -- LINEAR functional form "
                "(final, locked)"
            ),
            clinical_unit=spec["clinical_unit"],
            native_unit="count",
            reporting_unit=spec["reporting_unit"],
            continuous_unit_scale=1.0,
            functional_form_status=spec["functional_form_status"],
            source_of_decision=spec["source_of_decision"],
            reason=spec["reason"],
            needs_clinical_signoff=False,
        )
        return row

    if physical_type == "binary":
        if predictor in _BINARY_EXPLICIT_SEMANTICS:
            sem = _BINARY_EXPLICIT_SEMANTICS[predictor]
            row.update(
                publication_status=APPROVED,
                inferential_role=ROLE_BINARY,
                publication_value_source=VS_RAW_CLEANED,
                publication_representation=(
                    f"binary passthrough, {sem['comparison_label']} vs {sem['reference_label']}"
                ),
                binary_semantic_status=BINARY_SEMANTIC_EXPLICIT,
                reference_label=sem["reference_label"],
                comparison_label=sem["comparison_label"],
                clinical_unit="binary indicator (0/1)",
                native_unit="code 0/1",
                reference_level=0,
                source_of_decision=(
                    "outputs/eda_c/candidate_model_features.csv (physical_variable_type=binary, "
                    "model_representation_type=binary_passthrough) + " + sem["semantic_source"]
                ),
                needs_clinical_signoff=False,
                reason=(
                    "Canonical 0/1 binary passthrough with an explicit repository-documented "
                    f"numeric-to-meaning mapping ({sem['comparison_label']} vs "
                    f"{sem['reference_label']}); reference = value 0."
                ),
            )
        else:
            row.update(
                publication_status=APPROVED,
                inferential_role=ROLE_BINARY,
                publication_value_source=VS_RAW_CLEANED,
                publication_representation="binary passthrough, value 1 vs value 0",
                binary_semantic_status=BINARY_SEMANTIC_GENERIC,
                reference_label="value 0",
                comparison_label="value 1 vs value 0",
                clinical_unit="binary indicator (0/1)",
                native_unit="code 0/1",
                reference_level=0,
                source_of_decision=_BINARY_GENERIC_SOURCE_OF_DECISION,
                needs_clinical_signoff=False,
                reason=(
                    "Canonical 0/1 binary passthrough; the statistically valid publication "
                    "contrast is value 1 vs value 0 with reference = value 0. No clinical "
                    "present/absent/yes/no label is asserted — no predictor-specific "
                    "repository source documents which numeric value corresponds to which "
                    "clinical meaning for this predictor."
                ),
            )
        return row

    # --- fallbacks for predictors without an explicit spec entry -------------
    # A categorical (or unrecognised physical type) with no repository-supported
    # reference level AND category order is left PENDING — never given an
    # invented representation (CHECKPOINT B §1E).
    if physical_type == "categorical":
        row.update(
            publication_status=PENDING_REPRESENTATION_REVIEW,
            inferential_role=ROLE_PENDING,
            publication_value_source=VS_DERIVED_CATEGORICAL,
            publication_representation="pending representation review — not fitted",
            clinical_unit="not yet defined (pending representation review)",
            native_unit="category label",
            source_of_decision="none on record",
            needs_clinical_signoff=True,
            reason=(
                "No repository source establishes both a defensible reference level and a "
                "defensible category order for this categorical predictor, so it stays "
                "PENDING and is not fitted in Checkpoint B."
            ),
        )
        return row

    if physical_type in ("continuous", "count"):
        # No documented clinical unit/scale for this predictor -> do NOT invent
        # an inferential representation (Checkpoint-B targeted-correction §6).
        # This fallback must stay PENDING even though every currently-live
        # continuous/count predictor is already covered by _CONTINUOUS_SPEC /
        # _COUNT_SPEC above and never reaches this branch today.
        row.update(
            publication_status=PENDING_REPRESENTATION_REVIEW,
            inferential_role=ROLE_PENDING,
            publication_value_source=VS_RAW_CLEANED,
            publication_representation="pending representation review — not fitted",
            clinical_unit="not yet defined (pending representation review)",
            native_unit="not yet defined",
            source_of_decision=(
                "none on record — no documented clinical unit/scale for this "
                f"{physical_type} predictor"
            ),
            needs_clinical_signoff=True,
            reason=(
                "No documented clinical unit / scale is on record for this continuous/count "
                "predictor. Per the representation-contract principle (no documented unit -> "
                "do not invent an inferential representation), this predictor stays "
                "PENDING_REPRESENTATION_REVIEW rather than being auto-approved with an "
                "unknown per-1-unit default."
            ),
        )
        return row

    row.update(
        publication_status=PENDING_REPRESENTATION_REVIEW,
        inferential_role=ROLE_PENDING,
        publication_value_source="unknown",
        publication_representation="pending representation review — not fitted",
        clinical_unit="not yet defined",
        native_unit="not yet defined",
        source_of_decision="none on record",
        needs_clinical_signoff=True,
        reason=(
            f"Unrecognised physical_variable_type {physical_type!r}; needs a manual "
            "representation decision before any inferential use."
        ),
    )
    return row


def _validate_publication_representation_contract(
    contract_df: pd.DataFrame, features_df: pd.DataFrame
) -> None:
    problems: list[str] = []

    if list(contract_df["predictor"]) != list(features_df["variable"]):
        problems.append(
            "contract predictor order does not match the canonical registry order "
            "(outputs/eda_c/candidate_model_features.csv)"
        )
    if contract_df["predictor"].duplicated().any():
        dupes = sorted(contract_df.loc[contract_df["predictor"].duplicated(), "predictor"])
        problems.append(f"duplicate predictor rows: {dupes}")
    if len(contract_df) != len(features_df):
        problems.append(
            f"contract has {len(contract_df)} rows, registry has {len(features_df)}"
        )

    bad_roles = sorted(set(contract_df["inferential_role"]) - VALID_INFERENTIAL_ROLES)
    if bad_roles:
        problems.append(f"invalid inferential_role value(s): {bad_roles}")

    bad_statuses = sorted(set(contract_df["publication_status"]) - VALID_PUBLICATION_STATUSES)
    if bad_statuses:
        problems.append(f"invalid publication_status value(s): {bad_statuses}")

    # APPROVED must never coexist with needs_clinical_signoff=True (Checkpoint-B
    # targeted-correction §4) -- a representation cannot be simultaneously final
    # and still awaiting clinical sign-off. Proposals awaiting sign-off belong
    # to PENDING_CLINICAL_SIGNOFF instead.
    contradictory = contract_df[
        (contract_df["publication_status"] == APPROVED)
        & contract_df["needs_clinical_signoff"].astype(bool)
    ]
    if len(contradictory):
        problems.append(
            "APPROVED rows must never have needs_clinical_signoff=True "
            f"(contradiction): {sorted(contradictory['predictor'])}"
        )

    cat_rows = contract_df[contract_df["inferential_role"] == ROLE_CATEGORICAL]
    for _, r in cat_rows.iterrows():
        ref = r["reference_level"]
        order = r["category_order"]
        if ref is None or (isinstance(ref, str) and not ref.strip()):
            problems.append(f"{r['predictor']}: CATEGORICAL row has an empty reference_level")
        if not isinstance(order, list) or len(order) == 0:
            problems.append(f"{r['predictor']}: CATEGORICAL row has an empty category_order")
        elif ref not in order:
            problems.append(
                f"{r['predictor']}: reference_level {ref!r} is not in category_order {order}"
            )

    # --- functional-form gate invariants (Representation Sign-off + ---------
    # --- Functional-Form Gate task) ------------------------------------------
    bad_ff_statuses = sorted(set(contract_df["functional_form_status"]) - VALID_FUNCTIONAL_FORM_STATUSES)
    if bad_ff_statuses:
        problems.append(f"invalid functional_form_status value(s): {bad_ff_statuses}")

    # Only CONTINUOUS/COUNT roles ever have a linear-functional-form question;
    # every other role must be NOT_APPLICABLE, never left PENDING/approved/
    # flagged by mistake.
    non_continuous_count = contract_df[~contract_df["inferential_role"].isin([ROLE_CONTINUOUS, ROLE_COUNT])]
    mislabeled_ff = non_continuous_count[non_continuous_count["functional_form_status"] != FF_NOT_APPLICABLE]
    if len(mislabeled_ff):
        problems.append(
            "non-CONTINUOUS/COUNT rows must have functional_form_status=NOT_APPLICABLE: "
            f"{sorted(mislabeled_ff['predictor'])}"
        )
    # Conversely, every CONTINUOUS/COUNT row must carry an actual functional-
    # form review status, never the NOT_APPLICABLE placeholder meant for roles
    # with no linearity question.
    continuous_count = contract_df[contract_df["inferential_role"].isin([ROLE_CONTINUOUS, ROLE_COUNT])]
    unset_ff = continuous_count[continuous_count["functional_form_status"] == FF_NOT_APPLICABLE]
    if len(unset_ff):
        problems.append(
            f"CONTINUOUS/COUNT rows must not have functional_form_status=NOT_APPLICABLE: "
            f"{sorted(unset_ff['predictor'])}"
        )

    if problems:
        raise PublicationRepresentationContractError(
            "Publication representation contract invariants violated:\n- "
            + "\n- ".join(problems)
        )


def build_publication_representation_contract(
    features_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the full 81-row publication representation contract.

    Exactly one row per canonical source predictor, in canonical registry
    order (the order of ``outputs/eda_c/candidate_model_features.csv``). Reads
    only that variable-level registry (no patient rows) unless ``features_df``
    is supplied directly (used by synthetic tests). Raises
    ``PublicationRepresentationContractError`` if any predictor has no
    representation decision on record or if the contract invariants fail.
    """
    if features_df is None:
        features_df = load_candidate_features()

    if "variable" not in features_df.columns:
        raise PublicationRepresentationContractError(
            "features_df must have a 'variable' column"
        )
    phys = (
        dict(zip(features_df["variable"], features_df["physical_variable_type"]))
        if "physical_variable_type" in features_df.columns
        else {}
    )
    # Self-auditing fields (Checkpoint-B targeted-correction §8): pulled
    # directly from the canonical registry so the contract alone documents
    # where each predictor entered and its predictive representation,
    # without a separate undocumented ad-hoc join elsewhere. Missing columns
    # (synthetic test fixtures) degrade gracefully to None per predictor.
    stage_by_name = (
        dict(zip(features_df["variable"], features_df["earliest_entry_stage"]))
        if "earliest_entry_stage" in features_df.columns
        else {}
    )
    model_repr_by_name = (
        dict(zip(features_df["variable"], features_df["model_representation_type"]))
        if "model_representation_type" in features_df.columns
        else {}
    )
    entry_mode_by_name = (
        dict(zip(features_df["variable"], features_df["model_entry_mode"]))
        if "model_entry_mode" in features_df.columns
        else {}
    )

    rows = [
        _contract_row_for(
            str(v),
            str(phys.get(v, "")),
            earliest_entry_stage=stage_by_name.get(v),
            canonical_model_representation=model_repr_by_name.get(v),
            model_entry_mode=entry_mode_by_name.get(v),
        )
        for v in features_df["variable"]
    ]
    contract_df = pd.DataFrame(rows, columns=PUBLICATION_REPRESENTATION_CONTRACT_COLUMNS)
    _validate_publication_representation_contract(contract_df, features_df)
    return contract_df


def build_representation_review_table(
    contract_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Clinical sign-off table: every predictor whose representation still
    genuinely needs a clinical/representation decision —
    ``needs_clinical_signoff == True`` OR
    ``inferential_role == PENDING_REPRESENTATION_REVIEW``.

    This is a sign-off table, not an approval: Checkpoint B never silently
    converts a sign-off-required proposal into a clinically approved one.

    Finalized ``DESCRIPTIVE_ONLY`` predictors are RESOLVED decisions
    (``needs_clinical_signoff == False``) and are deliberately NOT listed
    here. For the current live 81-row contract there are no unresolved
    representation decisions, so this table has zero rows.
    """
    if contract_df is None:
        contract_df = build_publication_representation_contract()

    mask = contract_df["needs_clinical_signoff"].astype(bool) | (
        contract_df["inferential_role"] == ROLE_PENDING
    )
    return contract_df.loc[mask, REPRESENTATION_REVIEW_TABLE_COLUMNS].reset_index(drop=True)


def summarize_publication_representation_contract(
    contract_df: pd.DataFrame,
) -> PublicationRepresentationContractSummary:
    role_counts = contract_df["inferential_role"].value_counts()
    status_counts = contract_df["publication_status"].value_counts()
    binary_rows = contract_df[contract_df["inferential_role"] == ROLE_BINARY]
    binary_semantic_counts = binary_rows["binary_semantic_status"].value_counts()
    ff_counts = contract_df["functional_form_status"].value_counts()
    return PublicationRepresentationContractSummary(
        n_total=len(contract_df),
        n_by_role={role: int(role_counts.get(role, 0)) for role in sorted(VALID_INFERENTIAL_ROLES)},
        n_by_publication_status={
            status: int(status_counts.get(status, 0)) for status in sorted(VALID_PUBLICATION_STATUSES)
        },
        n_by_binary_semantic_status={
            BINARY_SEMANTIC_EXPLICIT: int(binary_semantic_counts.get(BINARY_SEMANTIC_EXPLICIT, 0)),
            BINARY_SEMANTIC_GENERIC: int(binary_semantic_counts.get(BINARY_SEMANTIC_GENERIC, 0)),
        },
        n_by_functional_form_status={
            status: int(ff_counts.get(status, 0)) for status in sorted(VALID_FUNCTIONAL_FORM_STATUSES)
        },
        n_needs_signoff=int(contract_df["needs_clinical_signoff"].astype(bool).sum()),
        pending_predictors=list(
            contract_df.loc[
                contract_df["inferential_role"] == ROLE_PENDING, "predictor"
            ]
        ),
        pending_clinical_signoff_predictors=list(
            contract_df.loc[
                contract_df["publication_status"] == PENDING_CLINICAL_SIGNOFF, "predictor"
            ]
        ),
        functional_form_review_predictors=list(
            contract_df.loc[
                contract_df["functional_form_status"] == FF_PENDING_REVIEW, "predictor"
            ]
        ),
    )


class PublicationLabelMappingError(RuntimeError):
    """Raised when a predictor's stored analysis-matrix values cannot be
    deterministically prepared for publication-facing categorical inference
    (Functional-Form Methodological Correction pass §7)."""


def prepare_predictor_for_publication_inference(
    matrix_df: pd.DataFrame, predictor: str, representation_contract_row: pd.Series,
) -> pd.Series:
    """Return a publication-ready Series for `predictor` from the analysis
    matrix, applying the representation contract's
    ``raw_code_to_publication_label`` mapping when one is defined.

    This is the SINGLE centralized preparation layer -- callers (in
    particular ``run_univariable_master``) must never special-case
    individual predictor names; every categorical predictor is routed
    through this same function, using the representation contract as the
    sole source of truth for whether/how to map.

    - NEVER mutates ``matrix_df`` (returns a new Series).
    - NaN is preserved exactly (never mapped, never imputed).
    - If ``raw_code_to_publication_label`` is not defined for this predictor
      (None / empty / NaN), the stored column already IS the publication
      representation -- returned unchanged (a genuine pass-through, not a
      guess). This covers the 4 ``derived_*`` / PIH-spectrum categoricals
      that already store the exact approved label strings.
    - If a mapping IS defined: every non-missing raw stored value must be a
      key in the mapping, or this raises ``PublicationLabelMappingError``
      (fail loud -- never silently drop or guess an unmapped code).
    - After mapping (or pass-through), if the contract's ``reference_level``
      is not found among the resulting non-missing values, raises
      ``PublicationLabelMappingError``.
    - If the contract's ``category_order`` is an explicit list, every
      resulting non-missing observed level must be within it, or this
      raises ``PublicationLabelMappingError``.
    - Never infers a mapping from observed values and never consults the
      outcome column -- this function does not even receive the outcome.
    """
    if predictor not in matrix_df.columns:
        raise PublicationLabelMappingError(
            f"{predictor}: not present in the supplied analysis matrix."
        )
    raw_series = matrix_df[predictor]
    code_map = representation_contract_row.get("raw_code_to_publication_label")

    if not code_map:  # None, {}, or NaN -> already publication-ready as-is
        prepared = raw_series.copy()
    else:
        non_missing = raw_series.dropna()
        unmapped = sorted(
            {v for v in non_missing.unique() if int(v) not in code_map},
            key=lambda x: str(x),
        )
        if unmapped:
            raise PublicationLabelMappingError(
                f"{predictor}: raw stored value(s) {unmapped} have no entry in the "
                f"approved raw_code_to_publication_label mapping {code_map}. Refusing "
                "to guess a label for an unmapped code."
            )
        prepared = raw_series.map(lambda v: code_map[int(v)] if pd.notna(v) else v)
        prepared.name = predictor

    reference_level = representation_contract_row.get("reference_level")
    category_order = representation_contract_row.get("category_order")
    observed = set(prepared.dropna().unique())

    if reference_level is not None and observed and reference_level not in observed:
        raise PublicationLabelMappingError(
            f"{predictor}: reference_level {reference_level!r} is not present among "
            f"the observed values {sorted(observed, key=str)} after preparation."
        )
    if isinstance(category_order, list) and category_order:
        outside_order = sorted(observed - set(category_order), key=str)
        if outside_order:
            raise PublicationLabelMappingError(
                f"{predictor}: observed level(s) {outside_order} after preparation are "
                f"outside the approved category_order {category_order}."
            )

    return prepared


if __name__ == "__main__":
    _contract = build_publication_representation_contract()
    _summary = summarize_publication_representation_contract(_contract)
    print(f"publication representation contract rows: {_summary.n_total}")
    print(f"by inferential_role: {_summary.n_by_role}")
    print(f"by publication_status: {_summary.n_by_publication_status}")
    print(f"binary semantic status: {_summary.n_by_binary_semantic_status}")
    print(f"needs_clinical_signoff: {_summary.n_needs_signoff}")
    print(f"PENDING_REPRESENTATION_REVIEW ({len(_summary.pending_predictors)}): "
          f"{_summary.pending_predictors}")
    print(f"PENDING_CLINICAL_SIGNOFF ({len(_summary.pending_clinical_signoff_predictors)}): "
          f"{_summary.pending_clinical_signoff_predictors}")
    print(f"functional_form_status: {_summary.n_by_functional_form_status}")
    print(f"PENDING_FUNCTIONAL_FORM_REVIEW ({len(_summary.functional_form_review_predictors)}): "
          f"{_summary.functional_form_review_predictors}")
    _review = build_representation_review_table(_contract)
    print(f"representation review table rows: {len(_review)}")

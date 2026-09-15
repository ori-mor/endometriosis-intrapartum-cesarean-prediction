"""A/B/C feasibility classification for the adjusted endometriosis-specific
association analysis (Adjusted Association Design Lock, Checkpoint C).

This is the independently reviewed final feasibility classification from the
ADJ_MICRO audit (see ``temp/ADJ_MICRO_02_support.csv`` /
``temp/ADJ_MICRO_03_review_summary.txt`` for the full review record), fixed
here in code as the approved partition of the 35-member
``ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY`` (the canonical family registry,
loaded read-only via ``publication_contract.endometriosis_family_names()``):

    A -- STANDARD_ADJUSTED_MODEL_FEASIBLE      (10)
    B -- STANDARD_ADJUSTED_MODEL_HIGH_CAUTION  (16)
    C -- STANDARD_ADJUSTED_MODEL_NOT_DEFENSIBLE (9)

The classifier keys ONLY on structural/design facts (zero-cell counts,
exposed-subject/event support, categorical zero-event levels, and two named
structural-overlap cases) -- never on a Checkpoint-C or adjusted p-value. C
exposures are never fit with ordinary adjusted logistic regression; they
remain in every result table with an explicit NOT_FITTED status and a
name-keyed reason from ``C_CLASS_NOT_DEFENSIBLE_REASONS``.
"""
from __future__ import annotations

from publication_analysis.publication_contract import endometriosis_family_names

CLASS_A = "STANDARD_ADJUSTED_MODEL_FEASIBLE"
CLASS_B = "STANDARD_ADJUSTED_MODEL_HIGH_CAUTION"
CLASS_C = "STANDARD_ADJUSTED_MODEL_NOT_DEFENSIBLE"

EXPOSURE_CLASS_A: frozenset[str] = frozenset(
    {
        "adenomyosis",
        "adenomyosis_feature_1",
        "adenomyosis_feature_3",
        "adenomyosis_features_unknown",
        "deep_endometriosis",
        "derived_endo_surgery_adhesion_status",
        "derived_prior_endo_surgery_procedure_status",
        "endometrioma",
        "endometriosis_surgery",
        "peritoneal_endometriosis",
    }
)

EXPOSURE_CLASS_B: frozenset[str] = frozenset(
    {
        "adenomyosis_feature_2",
        "adenomyosis_feature_4",
        "adenomyosis_feature_5",
        "adenomyosis_feature_10",
        "bladder_lesion_resected",
        "bowel_lesion_resected",
        "cs_scar_endometriosis",
        "endo_resection_adhesiolysis",
        "endo_resection_adnexa",
        "endo_resection_fallopian_tube",
        "endo_resection_lesion",
        "endo_resection_no_resection",
        "endo_resection_ovarian_endometrioma_bilateral",
        "endo_resection_ovarian_endometrioma_unilateral",
        "endometrioma_size_status",
        "vaginal_opening_during_surgery",
    }
)

EXPOSURE_CLASS_C: frozenset[str] = frozenset(
    {
        "adenomyosis_feature_6",
        "adenomyosis_feature_7",
        "adenomyosis_feature_8",
        "adenomyosis_feature_9",
        "adenomyosis_feature_11",
        "endo_resection_appendix",
        "endo_resection_epiploica",
        "endo_resection_uterus",
        "endometrioma_presence_laterality",
    }
)

# Categorical (non-binary) members of the family. Binary members are fit with
# a single 0/1 term; these are fit with treatment/dummy coding against the
# approved reference level from publication_representations._CATEGORICAL_APPROVED.
CATEGORICAL_EXPOSURES: frozenset[str] = frozenset(
    {
        "derived_endo_surgery_adhesion_status",
        "derived_prior_endo_surgery_procedure_status",
        "endometrioma_size_status",
        "endometrioma_presence_laterality",  # class C -- never fit, kept for completeness
    }
)

B_CLASS_CAUTION_REASONS: dict[str, str] = {
    "adenomyosis_feature_2": (
        "Exposed group has only 1 exposed event despite 6 exposed unique subjects "
        "(5-9 band) -- adjusted-OR precision would rest on an extremely thin event margin."
    ),
    "adenomyosis_feature_4": (
        "Exposed group has only 2 exposed events despite 39 exposed unique subjects "
        "(>=20 band) -- subject count alone does not guarantee estimable precision when "
        "the exposed-event margin is this thin."
    ),
    "adenomyosis_feature_5": "Only 1 exposed event despite 22 exposed unique subjects (>=20 band).",
    "adenomyosis_feature_10": "Only 1 exposed event despite 10 exposed unique subjects (10-19 band).",
    "bladder_lesion_resected": (
        "Binary operative-finding indicator: contrast is finding/procedure present vs a "
        "heterogeneous value-0 group containing both operated-negative and never-operated women."
    ),
    "bowel_lesion_resected": (
        "Binary operative-finding indicator: contrast is finding/procedure present vs a "
        "heterogeneous value-0 group containing both operated-negative and never-operated women."
    ),
    "cs_scar_endometriosis": (
        "Binary operative-finding indicator: contrast is finding/procedure present vs a "
        "heterogeneous value-0 group containing both operated-negative and never-operated women."
    ),
    "endo_resection_adhesiolysis": (
        "Binary operative-finding indicator: contrast is finding/procedure present vs a "
        "heterogeneous value-0 group containing both operated-negative and never-operated women."
    ),
    "endo_resection_adnexa": (
        "Binary operative-finding indicator population/contrast caveat, reinforced by only 1 "
        "exposed event despite 11 exposed unique subjects (10-19 band)."
    ),
    "endo_resection_fallopian_tube": (
        "Binary operative-finding indicator population/contrast caveat, reinforced by only 2 "
        "exposed events despite 27 exposed unique subjects."
    ),
    "endo_resection_lesion": (
        "Binary operative-finding indicator population/contrast caveat (support itself is ample: "
        "173 exposed subjects, 21 exposed events -- caution is about contrast definition, not sparsity)."
    ),
    "endo_resection_no_resection": (
        "Binary operative-finding indicator population/contrast caveat, reinforced by only 7 "
        "exposed unique subjects (5-9 band)."
    ),
    "endo_resection_ovarian_endometrioma_bilateral": (
        "Binary operative-finding indicator population/contrast caveat, reinforced by only 2 "
        "exposed events despite 27 exposed unique subjects."
    ),
    "endo_resection_ovarian_endometrioma_unilateral": (
        "Binary operative-finding indicator population/contrast caveat (support ample: "
        "82 exposed subjects, 11 exposed events)."
    ),
    "endometrioma_size_status": (
        "Multi-parameter categorical model with limited event information "
        "(events-per-parameter ~8.71, informational 10-EPP guideline, non-binding)."
    ),
    "vaginal_opening_during_surgery": (
        "Binary operative-finding indicator population/contrast caveat (support ample: "
        "24 exposed subjects, 5 exposed events)."
    ),
}

C_CLASS_NOT_DEFENSIBLE_REASONS: dict[str, str] = {
    "adenomyosis_feature_6": "Complete/structural separation -- exposed N=4, zero exposed events (zero event cell).",
    "adenomyosis_feature_7": "Complete/structural separation -- exposed N=1, that 1 row is an event (zero non-event cell).",
    "adenomyosis_feature_8": "Complete/structural separation -- exposed N=1, zero exposed events (zero event cell).",
    "adenomyosis_feature_9": "Ultra-rare exposed group (4 unique subjects) -- not scientifically reliable regardless of convergence.",
    "adenomyosis_feature_11": "Complete/structural separation -- exposed N=1, that 1 row is an event (zero non-event cell).",
    "endo_resection_appendix": "Ultra-rare exposed group (4 unique subjects) -- not scientifically reliable regardless of convergence.",
    "endo_resection_epiploica": "Complete/structural separation -- exposed N=1, zero exposed events (zero event cell).",
    "endo_resection_uterus": "Complete/structural separation -- exposed N=9, zero exposed events (zero event cell).",
    "endometrioma_presence_laterality": (
        "Categorical level 'laterality_unknown' (N=5) has zero events -- complete separation for that level."
    ),
}

class FeasibilityPartitionError(RuntimeError):
    """Raised when the A/B/C partition does not match its required invariants."""


def classify(predictor: str) -> str:
    if predictor in EXPOSURE_CLASS_A:
        return CLASS_A
    if predictor in EXPOSURE_CLASS_B:
        return CLASS_B
    if predictor in EXPOSURE_CLASS_C:
        return CLASS_C
    raise FeasibilityPartitionError(
        f"{predictor!r} is not a member of any approved feasibility class "
        "(A/B/C) -- it may not be part of the locked 35-member family."
    )


def caution_reason(predictor: str) -> str:
    """Machine-readable caution / non-defensibility reason. Empty string for class A."""
    if predictor in EXPOSURE_CLASS_B:
        return B_CLASS_CAUTION_REASONS[predictor]
    if predictor in EXPOSURE_CLASS_C:
        return C_CLASS_NOT_DEFENSIBLE_REASONS[predictor]
    return ""


def exposure_class_map() -> dict[str, str]:
    """All 35 members mapped to their approved feasibility class."""
    out: dict[str, str] = {}
    for member in EXPOSURE_CLASS_A:
        out[member] = CLASS_A
    for member in EXPOSURE_CLASS_B:
        out[member] = CLASS_B
    for member in EXPOSURE_CLASS_C:
        out[member] = CLASS_C
    return out


def assert_family_partition() -> None:
    """Fail loud unless A/B/C are disjoint, total 35, and equal the canonical family."""
    problems: list[str] = []

    overlap_ab = EXPOSURE_CLASS_A & EXPOSURE_CLASS_B
    overlap_ac = EXPOSURE_CLASS_A & EXPOSURE_CLASS_C
    overlap_bc = EXPOSURE_CLASS_B & EXPOSURE_CLASS_C
    if overlap_ab:
        problems.append(f"A/B overlap: {sorted(overlap_ab)}")
    if overlap_ac:
        problems.append(f"A/C overlap: {sorted(overlap_ac)}")
    if overlap_bc:
        problems.append(f"B/C overlap: {sorted(overlap_bc)}")

    if len(EXPOSURE_CLASS_A) != 10:
        problems.append(f"class A has {len(EXPOSURE_CLASS_A)} members, expected 10")
    if len(EXPOSURE_CLASS_B) != 16:
        problems.append(f"class B has {len(EXPOSURE_CLASS_B)} members, expected 16")
    if len(EXPOSURE_CLASS_C) != 9:
        problems.append(f"class C has {len(EXPOSURE_CLASS_C)} members, expected 9")

    union = EXPOSURE_CLASS_A | EXPOSURE_CLASS_B | EXPOSURE_CLASS_C
    if len(union) != 35:
        problems.append(f"A|B|C union has {len(union)} members, expected 35")

    canonical = endometriosis_family_names()
    if union != canonical:
        only_in_union = sorted(union - canonical)
        only_in_canonical = sorted(canonical - union)
        problems.append(
            "A|B|C union does not equal the canonical ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY -- "
            f"only_in_partition={only_in_union}, only_in_canonical={only_in_canonical}"
        )

    if set(B_CLASS_CAUTION_REASONS) != EXPOSURE_CLASS_B:
        problems.append("B_CLASS_CAUTION_REASONS keys do not exactly match EXPOSURE_CLASS_B")
    if set(C_CLASS_NOT_DEFENSIBLE_REASONS) != EXPOSURE_CLASS_C:
        problems.append("C_CLASS_NOT_DEFENSIBLE_REASONS keys do not exactly match EXPOSURE_CLASS_C")

    if problems:
        raise FeasibilityPartitionError(
            "Adjusted-association feasibility partition invalid:\n- " + "\n- ".join(problems)
        )

#!/usr/bin/env python3
"""Explicit, semantically-reviewed endometriosis-specific predictor family
for the final-modeling constrained pathways.

Every one of the 9 primary constrained pathways (3 cumulative stages x 3
model families) must contain at least one ACTIVE endometriosis-specific
source predictor. "Endometriosis-specific" is defined here as an explicit,
hand-authored, per-member-clinically-justified registry -- NOT a substring
heuristic and NOT "everything eligible in a broad domain".

Why not a substring heuristic: the retired
``modeling_core.is_endometriosis_predictor()`` matched only ``"endo"`` /
``"adenomyosis"`` in the variable name or domain string, silently EXCLUDING
three confirmed endometriosis-surgical-history predictors whose names contain
neither token (``vaginal_opening_during_surgery``,
``bladder_lesion_resected``, ``bowel_lesion_resected``).

Why not "the whole domain": eligibility and a shared broad domain are NOT
sufficient. Each of the 35 members below was reviewed individually and is
endometriosis-specific in clinical meaning -- an endometriosis/adenomyosis
phenotype, an endometrioma finding, a prior-endometriosis-surgery state, or a
component of the endometriosis-resection operative record. No generic
obstetric / maternal / pregnancy / non-endometriosis surgical variable is
included merely because it coexists with endometriosis variables or shares a
domain string. The per-member rationale is machine-readable
(``ENDOMETRIOSIS_FAMILY_RATIONALE``) and exportable
(``export_family()``); the Section 37 A-U report reproduces the exact list.

All current members enter at Stage 1, so every stage pool contains the full
family; ``endometriosis_family_in_stage()`` still intersects defensively.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

# ---------------------------------------------------------------------------
# Per-member clinical rationale. This dict IS the family definition
# (ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY is derived from its keys). Every
# entry names why the variable is endometriosis-specific, not merely
# endometriosis-adjacent.
# ---------------------------------------------------------------------------
ENDOMETRIOSIS_FAMILY_RATIONALE: dict[str, str] = {
    # --- endometriosis / adenomyosis phenotype (19) ------------------------
    "adenomyosis": "Adenomyosis diagnosis (endometrial tissue within the myometrium) -- the uterine form of the endometriosis disease spectrum; project-canonical endometriosis-family term.",
    "adenomyosis_feature_1": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_feature_2": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_feature_3": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_feature_4": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_feature_5": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_feature_6": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_feature_7": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_feature_8": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_feature_9": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_feature_10": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_feature_11": "Sonographic adenomyosis feature indicator (adenomyosis phenotype multi-hot family).",
    "adenomyosis_features_unknown": "'Adenomyosis sonographic features not documented' indicator -- the unknown level of the adenomyosis phenotype multi-hot family (still an adenomyosis-phenotype representation column).",
    "cs_scar_endometriosis": "Caesarean-section scar endometriosis -- a site-specific endometriosis phenotype.",
    "deep_endometriosis": "Deep infiltrating endometriosis phenotype.",
    "endometrioma": "Ovarian endometrioma (endometriotic cyst) presence.",
    "endometrioma_presence_laterality": "Endometrioma laterality (none / unilateral / bilateral / unknown) -- an endometrioma phenotype representation.",
    "endometrioma_size_status": "Endometrioma size category (<30mm / >=30mm / unknown / no endometrioma) -- an endometrioma phenotype representation.",
    "peritoneal_endometriosis": "Peritoneal endometriosis phenotype.",
    # --- prior endometriosis surgery / operative phenotype (16) -----------
    "bladder_lesion_resected": "Bladder endometriotic lesion resected during endometriosis surgery -- endometriosis-specific operative phenotype (urinary-tract deep endometriosis).",
    "bowel_lesion_resected": "Bowel endometriotic lesion resected during endometriosis surgery -- endometriosis-specific operative phenotype (bowel deep endometriosis).",
    "derived_endo_surgery_adhesion_status": "Prior-endometriosis-surgery state combined with documented adhesions (no_prior_endo_surgery / prior_surgery_with(out)_documented_adhesions) -- derived directly from the endometriosis_surgery record.",
    "derived_prior_endo_surgery_procedure_status": "Prior-endometriosis-surgery procedure status -- derived directly from the endometriosis surgical history.",
    "endo_resection_adhesiolysis": "Adhesiolysis component of the endometriosis-resection operation (endo_resection_sites multi-hot; scoped to the endometriosis surgery, not generic surgery).",
    "endo_resection_adnexa": "Adnexal resection component of the endometriosis-resection operation (endo_resection_sites multi-hot).",
    "endo_resection_appendix": "Appendiceal resection component of the endometriosis-resection operation -- appendiceal endometriosis (endo_resection_sites multi-hot).",
    "endo_resection_epiploica": "Epiploica resection component of the endometriosis-resection operation (endo_resection_sites multi-hot).",
    "endo_resection_fallopian_tube": "Fallopian-tube resection component of the endometriosis-resection operation (endo_resection_sites multi-hot).",
    "endo_resection_lesion": "Endometriotic lesion resection component of the endometriosis-resection operation (endo_resection_sites multi-hot).",
    "endo_resection_no_resection": "'Endometriosis surgery performed, no resection' indicator -- the no-resection level of the endometriosis-resection operative multi-hot (scoped to endometriosis surgery).",
    "endo_resection_ovarian_endometrioma_bilateral": "Bilateral ovarian endometrioma resected during the endometriosis-resection operation (endo_resection_sites multi-hot).",
    "endo_resection_ovarian_endometrioma_unilateral": "Unilateral ovarian endometrioma resected during the endometriosis-resection operation (endo_resection_sites multi-hot).",
    "endo_resection_uterus": "Uterine resection component of the endometriosis-resection operation (endo_resection_sites multi-hot).",
    "endometriosis_surgery": "History of endometriosis surgery (binary).",
    "vaginal_opening_during_surgery": "Vaginal opening/entry during endometriosis surgery -- endometriosis-specific operative phenotype indicating posterior deep infiltrating endometriosis requiring colpotomy.",
}

ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY: frozenset[str] = frozenset(ENDOMETRIOSIS_FAMILY_RATIONALE)
# Backwards-compatible alias (older name used elsewhere in this rebuild).
ENDOMETRIOSIS_FAMILY: frozenset[str] = ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY

# The three members a name/domain substring heuristic ("endo"/"adenomyosis")
# would silently miss -- asserted present by validate_endometriosis_family().
SUBSTRING_HEURISTIC_MISSES: frozenset[str] = frozenset(
    {"vaginal_opening_during_surgery", "bladder_lesion_resected", "bowel_lesion_resected"}
)

_ENDO_DOMAINS = frozenset({"endometriosis_phenotype", "prior_endo_surgery"})


def validate_endometriosis_family(eligible_pool: Iterable[str]) -> None:
    """Fail loud if the hand-authored family has drifted from the live pool
    or if the semantic-rationale coverage is incomplete."""
    pool = {str(v) for v in eligible_pool}
    missing = sorted(ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY - pool)
    if missing:
        raise RuntimeError(
            "endometriosis_family: hand-authored member(s) no longer in the EDA C "
            f"eligible pool: {missing}. The registry and the live pool have "
            "diverged -- reconcile endometriosis_family.py against the current "
            "candidate_model_features.csv before running any pathway."
        )
    if set(ENDOMETRIOSIS_FAMILY_RATIONALE) != set(ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY):
        raise RuntimeError("endometriosis_family: rationale dict and family set are out of sync.")
    for name, why in ENDOMETRIOSIS_FAMILY_RATIONALE.items():
        if len(why.strip()) < 20:
            raise RuntimeError(f"endometriosis_family: rationale for {name!r} is too thin to be a review record.")
    if not SUBSTRING_HEURISTIC_MISSES <= ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY:
        raise RuntimeError(
            "endometriosis_family: the substring-heuristic-miss guard members "
            f"{sorted(SUBSTRING_HEURISTIC_MISSES)} must all be family members."
        )


def reconcile_with_domain(registry: pd.DataFrame) -> dict[str, list[str]]:
    """Audit helper: where does the hand-authored family disagree with the
    registry's own endometriosis domain columns? Informational only -- the
    hand-authored, per-member-reviewed list is authoritative."""
    if "variable" not in registry.columns or "domain" not in registry.columns:
        raise RuntimeError("endometriosis_family.reconcile_with_domain: registry needs 'variable' and 'domain'.")
    by_domain = {
        str(r["variable"])
        for _, r in registry.iterrows()
        if str(r["domain"]) in _ENDO_DOMAINS
    }
    return {
        "in_family_not_in_endo_domain": sorted(ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY - by_domain),
        "in_endo_domain_not_in_family": sorted(by_domain - ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY),
    }


def family_table() -> pd.DataFrame:
    """The exact family as a 2-column table (member, endometriosis_specific_rationale),
    sorted for a stable export/report."""
    rows = [
        {"member": k, "endometriosis_specific_rationale": v}
        for k, v in sorted(ENDOMETRIOSIS_FAMILY_RATIONALE.items())
    ]
    return pd.DataFrame(rows, columns=["member", "endometriosis_specific_rationale"])


def export_family(path: str | Path) -> Path:
    """Write the exact family list. `.json` -> {member: rationale}; anything
    else -> 2-column CSV. Returns the written path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == ".json":
        p.write_text(
            json.dumps(
                {
                    "n_members": len(ENDOMETRIOSIS_FAMILY_RATIONALE),
                    "members": dict(sorted(ENDOMETRIOSIS_FAMILY_RATIONALE.items())),
                },
                indent=2,
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
    else:
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["member", "endometriosis_specific_rationale"])
            for k, v in sorted(ENDOMETRIOSIS_FAMILY_RATIONALE.items()):
                w.writerow([k, v])
    return p


def endometriosis_family_in_stage(stage_pool_members: Iterable[str]) -> list[str]:
    """The endometriosis-family members present in a given stage pool,
    in the order they appear in `stage_pool_members`."""
    members = list(dict.fromkeys(str(v) for v in stage_pool_members))
    return [v for v in members if v in ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY]


def has_active_endometriosis(active_source_predictors: Iterable[str]) -> bool:
    """True iff at least one active source predictor is in the family.

    NOTE: 'active' here means the caller has already resolved activity through
    source_predictor_activity.active_source_predictors() at the centralized
    COEFFICIENT_ACTIVITY_TOLERANCE -- a coefficient at or below that threshold
    is numerical zero and never reaches this function as 'active'.
    """
    return bool(ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY & {str(v) for v in active_source_predictors})


if __name__ == "__main__":  # pragma: no cover - manual verification aid
    tbl = family_table()
    print(f"ENDOMETRIOSIS_SPECIFIC_PREDICTOR_FAMILY -- {len(tbl)} members\n")
    for _, r in tbl.iterrows():
        print(f"  {r['member']:<46} {r['endometriosis_specific_rationale']}")

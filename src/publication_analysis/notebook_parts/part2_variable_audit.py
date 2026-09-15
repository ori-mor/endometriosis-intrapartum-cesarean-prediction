"""Publication notebook — Part 2: full 81-row publication representation
contract and the full variable / quality audit (both Section B)."""
from publication_analysis.notebook_parts._cell_helpers import code, md

PART2_CELLS = [
    md(
        "pub-s04-header",
        """
---
## Section B — Representation Contract and Data Quality Audit

### Publication Representation Contract (all 81 source predictors)

Exactly **one row per canonical source predictor**, in canonical registry
order. Each predictor is assigned an `inferential_role` — one of
`BINARY`, `CONTINUOUS`, `COUNT`, `CATEGORICAL`, `DESCRIPTIVE_ONLY`, or
`PENDING_REPRESENTATION_REVIEW` — grounded in an existing repository source
recorded in `source_of_decision`. This contract is the **single
representation-decision source of truth** for the whole publication package —
no other module builds an independent decision table.

`publication_status` is distinct from `inferential_role`. In the current
final contract **no representation decision remains pending**: all **73**
`BINARY` / `CATEGORICAL` / `CONTINUOUS` / `COUNT` predictors carry an
**`APPROVED`** inferential representation, and the remaining **8** predictors
carry a **final `DESCRIPTIVE_ONLY`** representation — a completed
clinical/methodological decision to describe rather than fit, **not** an
awaiting-sign-off state. No row is `PENDING_CLINICAL_SIGNOFF` or
`PENDING_REPRESENTATION_REVIEW`; `PENDING_CLINICAL_SIGNOFF` is retained only
as an architectural status for possible future use.

For `BINARY` predictors, `binary_semantic_status` distinguishes
**`EXPLICITLY_DOCUMENTED`** (a repository source states what 0 and 1 mean for
*that* predictor) from **`GENERIC_1_VS_0`** (the predictor is canonically 0/1
binary, but no repository source documents a predictor-specific clinical
present/absent/yes/no meaning — the reportable contrast is only "value 1 vs
value 0", never "present vs absent"). `physical_variable_type=binary` /
`model_representation_type=binary_passthrough` alone never proves a
clinical present/absent meaning.

Machine-only predictive transformations (fold-specific cutpoints, quantile
bins, scaler outputs) are **never** reused for inferential reporting. Where
no defensible reference level / category order / clinical unit is on record,
the predictor stays `PENDING_REPRESENTATION_REVIEW` — a representation is
never invented here.
""",
    ),
    code(
        "pub-s04-representation-contract",
        """
from publication_analysis import publication_representations as repr_mod
from publication_analysis import publication_exports as exports

representation_contract = repr_mod.build_publication_representation_contract()
repr_summary = repr_mod.summarize_publication_representation_contract(representation_contract)

print(f"source predictors in contract: {repr_summary.n_total}")
print("inferential_role counts:")
for role, n in repr_summary.n_by_role.items():
    print(f"  {role:31s} {n}")
print("publication_status counts:")
for status, n in repr_summary.n_by_publication_status.items():
    print(f"  {status:31s} {n}")
print("binary_semantic_status counts (BINARY predictors only):")
for status, n in repr_summary.n_by_binary_semantic_status.items():
    print(f"  {status:31s} {n}")
print(f"needs_clinical_signoff = True (expect 0 — no pending representation decisions): {repr_summary.n_needs_signoff}")

exports.ensure_output_dirs()
exports.save_table_csv(representation_contract, exports.PUBLICATION_REPRESENTATION_CONTRACT_CSV)
representation_contract
""",
    ),
    md(
        "pub-s04b-review-header",
        """
### Representation sign-off review table

Every predictor that still **genuinely** needs a clinical/representation
decision: `needs_clinical_signoff == True` **or**
`inferential_role == PENDING_REPRESENTATION_REVIEW`. The 8 finalized
`DESCRIPTIVE_ONLY` predictors are **resolved** decisions and are not listed
here. For the current live 81-row contract this table is **empty** — no
representation decision remains pending.
""",
    ),
    code(
        "pub-s04b-review-table",
        """
representation_review = repr_mod.build_representation_review_table(representation_contract)

pending_predictors = repr_summary.pending_predictors
pending_signoff_predictors = repr_summary.pending_clinical_signoff_predictors
print(f"rows requiring clinical sign-off / review: {len(representation_review)}")
print(f"PENDING_REPRESENTATION_REVIEW ({len(pending_predictors)}):")
for name in pending_predictors:
    print(f"  - {name}")
print(f"PENDING_CLINICAL_SIGNOFF ({len(pending_signoff_predictors)}, proposed but not clinician-approved):")
for name in pending_signoff_predictors:
    print(f"  - {name}")

exports.save_table_csv(representation_review, exports.REPRESENTATION_SIGNOFF_REVIEW_CSV)
representation_review
""",
    ),
    md(
        "pub-s06-header",
        """
### Full variable / quality audit

For all 81 eligible predictors: earliest stage, domain, endometriosis-family
membership, publication `inferential_role`, non-missing / missing counts,
unique-value counts, and (for binary predictors) `value_1_rows` /
`value_1_unique_subjects` counts — i.e. rows/subjects where the stored
numeric value equals 1. This is a **numeric** count, not a claim of clinical
positivity: see `binary_semantic_status` in the representation contract for
which binary predictors have a repository-documented clinical meaning for
value 1 versus value 0.
""",
    ),
    code(
        "pub-s06-quality-audit",
        """
from publication_analysis.descriptive_analysis import (
    variable_types_from_candidate_features,
    stage_map_from_candidate_features,
)

variable_types = variable_types_from_candidate_features(features_df)
stage_map = stage_map_from_candidate_features(features_df)
endo_family = contract.endometriosis_family_names()

_role_by_pred = representation_contract.set_index("predictor")["inferential_role"].to_dict()
_status_by_pred = representation_contract.set_index("predictor")["publication_status"].to_dict()
_domain_by_pred = features_df.set_index("variable")["domain"].to_dict()

quality_rows = []
for variable in features_df["variable"]:
    series = df[variable]
    non_missing = series.dropna()
    row = {
        "predictor": variable,
        "earliest_stage": stage_map.get(variable),
        "domain": _domain_by_pred.get(variable),
        "endometriosis_specific": variable in endo_family,
        "inferential_role": _role_by_pred.get(variable),
        "publication_status": _status_by_pred.get(variable),
        "N_nonmissing": int(non_missing.shape[0]),
        "missing_n": int(series.isna().sum()),
        "missing_pct": round(100.0 * series.isna().sum() / len(series), 1),
        "unique_values": int(series.nunique(dropna=True)),
    }
    if variable_types.get(variable) == "binary":
        # "value_1", not "positive": this is a numeric count (stored value
        # == 1), not a clinical-positivity claim. See binary_semantic_status
        # in the representation contract for which predictors have a
        # repository-documented clinical meaning for value 1 vs value 0.
        value_1_rows = non_missing[non_missing == 1]
        row["value_1_rows"] = int(len(value_1_rows))
        row["value_1_unique_subjects"] = int(
            subject_groups.loc[value_1_rows.index].nunique()
        )
    quality_rows.append(row)

import pandas as pd

variable_quality_audit = pd.DataFrame(quality_rows)
exports.save_table_csv(variable_quality_audit, exports.MISSINGNESS_SUPPORT_AUDIT_CSV)
variable_quality_audit.head(20)
""",
    ),
]

"""
Manual clinical decision tables and composite-key decision application.

This module holds record-level manual clinical decisions that are applied by
composite key (subject_number + delivery_id) during preprocessing, together
with the validation and merge logic that applies them safely.

Two kinds of decisions are represented:

- Manual feature-code decisions (ADENOMYOSIS_MANUAL_FEATURE_DECISIONS):
  authoritative corrections that assign specific adenomyosis sonographic
  feature codes to named records, overriding automated free-text parsing.
- Manual review-status decisions (ADENOMYOSIS_REVIEW_STATUS_DECISIONS):
  final clinical review outcomes for records that remain unresolved after
  automated parsing and manual feature-code correction; these populate
  review-file annotations only and never change analytical columns.

All decisions are validated against their target dataframe by
validate_composite_key_decisions before being applied: duplicate keys and
unmatched decision keys are treated as hard errors, never silently ignored.

The canonical private version contains the record-level decision rows. They are intentionally omitted here for privacy.
"""

import pandas as pd


# PRIVACY REDACTION NOTICE
# The canonical private source contains record-level composite-key decisions here.
# Their literal subject/delivery identifiers and patient-specific rationale have been
# removed from this public privacy-redacted repository copy. The schema and
# application/validation logic are retained; the tables below are intentionally
# empty (schema-only) as a result.

ADENOMYOSIS_MANUAL_FEATURE_DECISIONS = pd.DataFrame(
    columns=["subject_number", "delivery_id", "manual_codes", "rule_label", "rule_reason"]
)

ADENOMYOSIS_REVIEW_STATUS_DECISIONS = pd.DataFrame(
    columns=["subject_number", "delivery_id", "review_decision", "review_reason"]
)


def apply_adenomyosis_review_status_decisions(review_df, decisions_df=None):
    """Apply validated composite-key manual review-status decisions to a review dataframe.

    Populates manual_review_decision/manual_review_reason only for matching rows.
    Never touches adenomyosis_sonographic_features_clean or adenomyosis.
    """
    decisions = ADENOMYOSIS_REVIEW_STATUS_DECISIONS if decisions_df is None else decisions_df
    if decisions.empty or review_df.empty:
        return review_df, 0
    key_cols = ["subject_number", "delivery_id"]
    review_dups = review_df.duplicated(key_cols, keep=False)
    if review_dups.any():
        raise ValueError("adenomyosis review status decisions: duplicate subject_number + delivery_id pairs in review_df")
    decision_dups = decisions.duplicated(key_cols, keep=False)
    if decision_dups.any():
        raise ValueError("adenomyosis review status decisions: duplicate subject_number + delivery_id pairs in decision table")
    probe = decisions[key_cols].merge(review_df[key_cols], on=key_cols, how="left", indicator=True, validate="one_to_one")
    unmatched = probe["_merge"].ne("both")
    if unmatched.any():
        raise ValueError("adenomyosis review status decisions: unmatched manual decision key(s) found")

    merged = review_df.merge(
        decisions, on=key_cols, how="left", validate="one_to_one", indicator="_adeno_review_merge",
    )
    matched = merged["_adeno_review_merge"].eq("both")
    merged["manual_review_decision"] = merged["manual_review_decision"].astype(object)
    merged["manual_review_reason"] = merged["manual_review_reason"].astype(object)
    merged.loc[matched, "manual_review_decision"] = merged.loc[matched, "review_decision"]
    merged.loc[matched, "manual_review_reason"] = merged.loc[matched, "review_reason"]
    merged = merged.drop(columns=["review_decision", "review_reason", "_adeno_review_merge"])
    return merged, int(matched.sum())


def validate_composite_key_decisions(df, decisions_df, context):
    """Validate record-level decisions before applying them by subject_number + delivery_id."""
    key_cols = ["subject_number", "delivery_id"]
    missing_input = [col for col in key_cols if col not in df.columns]
    missing_decision = [col for col in key_cols if col not in decisions_df.columns]
    if missing_input:
        raise ValueError(f"{context}: input is missing key column(s): {missing_input}")
    if missing_decision:
        raise ValueError(f"{context}: decision table is missing key column(s): {missing_decision}")
    input_dups = df.duplicated(key_cols, keep=False)
    if input_dups.any():
        raise ValueError(f"{context}: duplicate subject_number + delivery_id pairs in input")
    decision_dups = decisions_df.duplicated(key_cols, keep=False)
    if decision_dups.any():
        raise ValueError(f"{context}: duplicate subject_number + delivery_id pairs in decision table")

    probe = decisions_df[key_cols].merge(df[key_cols], on=key_cols, how="left", indicator=True, validate="one_to_one")
    unmatched = probe["_merge"].ne("both")
    if unmatched.any():
        raise ValueError(f"{context}: unmatched manual decision key(s) found")


def apply_adenomyosis_manual_feature_decisions(df, decisions_df=None):
    """Apply validated record-level adenomyosis feature decisions by composite key."""
    decisions = ADENOMYOSIS_MANUAL_FEATURE_DECISIONS if decisions_df is None else decisions_df
    if decisions.empty:
        return df, 0
    validate_composite_key_decisions(df, decisions, "adenomyosis manual feature decisions")
    merged = df.merge(
        decisions,
        on=["subject_number", "delivery_id"],
        how="left",
        validate="one_to_one",
        indicator="_adeno_manual_merge",
    )
    matched = merged["_adeno_manual_merge"].eq("both")
    for idx in merged.index[matched]:
        merged.at[idx, "_adeno_clean_list"] = sorted(merged.at[idx, "manual_codes"])
        merged.at[idx, "_adeno_clean_source"] = merged.at[idx, "rule_label"]
        merged.at[idx, "_adeno_rule_labels"] = [merged.at[idx, "rule_label"]]
    drop_cols = ["manual_codes", "rule_label", "rule_reason", "_adeno_manual_merge"]
    return merged.drop(columns=[col for col in drop_cols if col in merged.columns]), int(matched.sum())

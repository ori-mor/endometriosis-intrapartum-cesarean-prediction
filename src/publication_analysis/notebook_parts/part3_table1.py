"""Publication notebook — Part 3: Table 1 full descriptive cohort table (Section C)."""
from publication_analysis.notebook_parts._cell_helpers import code, md

PART3_CELLS = [
    md(
        "pub-s08-header",
        """
---
## Section C — Table 1: Full Descriptive Cohort Table

All 81 eligible predictors, ordered by earliest entry stage. **One summary
rule per variable**: for every continuous / count variable the mean ± SD vs
median [IQR] choice is decided **once** — from an explicit override if given,
otherwise from the full-cohort distribution — and then applied unchanged to
the Overall, Vaginal-delivery and Intrapartum-CS columns. A variable is
never shown as mean ± SD in one column and median [IQR] in another.

Categorical levels use the contract's `category_order`, which is now
**APPROVED** for every categorical predictor (a concrete order grounded in a
cited repository source, clinically signed off — no `category_order` remains
`PENDING_CLINICAL_SIGNOFF`); where no order applies, a deterministic neutral
order (lexical, never frequency-driven, never outcome-driven) with explicit
unknown / not-documented categories last. An explicit `category_order` is a
**closed set**: every level actually observed for that predictor must be
represented in it, or `order_categorical_levels` raises
`UnexpectedCategoryLevelError` rather than silently appending or dropping the
unexpected level. The 8 `DESCRIPTIVE_ONLY` predictors (a final describe-not-fit
decision) are still **described** here — DESCRIPTIVE_ONLY means "not fitted
inferentially", not "hidden from Table 1". This table is **descriptive
only** — no inferential p-values.
""",
    ),
    code(
        "pub-s08-imports",
        """
from publication_analysis import descriptive_analysis
from publication_analysis import compact_tables
from publication_analysis import publication_display_labels
import pandas as pd
""",
    ),
    code(
        "pub-s08-table1",
        """
TARGET_COL = "target_intrapartum_cs"

# Repository-grounded category orders come from the representation
# contract; every categorical predictor's order is now APPROVED
# (clinically signed off — no PENDING_CLINICAL_SIGNOFF rows remain).
category_order_map = {
    row.predictor: list(row.category_order)
    for row in representation_contract.itertuples()
    if isinstance(row.category_order, list) and row.category_order
}

table1 = descriptive_analysis.build_table1(
    df,
    variables=list(features_df["variable"]),
    variable_types=variable_types,
    stage_map=stage_map,
    outcome_col=TARGET_COL,
    category_order_map=category_order_map,
    representation_contract=representation_contract,
    predictor_display_labels=publication_display_labels.DISPLAY_LABELS,
)

exports.save_table_csv(table1, exports.TABLE_1_FULL_DESCRIPTIVE_CSV)
exports.save_table_xlsx(table1, exports.TABLE_1_FULL_DESCRIPTIVE_XLSX)
table1.head(20)
""",
    ),
    md(
        "pub-s08b-compact-table1-header",
        """
### Compact Table 1 — main Results descriptive subset

The full Table 1 above remains the complete Appendix-level descriptive
cohort table. This compact version is a researcher-approved main-text subset
based on final-model variables, literature relevance, and cohort-description
relevance. It is derived directly from Full Table 1 and therefore reuses the
same descriptive values. It remains **descriptive only**: no ORs, p-values,
confidence intervals, FDR q-values, or significance markers are added.
""",
    ),
    code(
        "pub-s08b-compact-table1",
        """
table1_saved = pd.read_csv(exports.TABLES_DIR / exports.TABLE_1_FULL_DESCRIPTIVE_CSV)
compact_table1 = compact_tables.build_compact_table1(table1_saved)
compact_tables.assert_compact_table1_matches_full(compact_table1, table1_saved)

compact_table1_sources = compact_table1["Variable"].str.split(": ", n=1).str[0].nunique()
print(f"Compact Table 1 source-variable concepts: {compact_table1_sources}")
print(f"Compact Table 1 display rows: {len(compact_table1)}")
assert compact_table1_sources == 13

exports.save_table_csv(compact_table1, exports.TABLE_1_COMPACT_DESCRIPTIVE_CSV)
exports.save_table_xlsx(compact_table1, exports.TABLE_1_COMPACT_DESCRIPTIVE_XLSX)
compact_table1
""",
    ),
]

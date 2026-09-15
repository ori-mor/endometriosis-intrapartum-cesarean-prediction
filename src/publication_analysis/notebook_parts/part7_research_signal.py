"""Publication notebook — Part 7: research-signal triangulation (Section G)."""
from publication_analysis.notebook_parts._cell_helpers import code, md

PART7_CELLS = [
    md(
        "pub-s16-header",
        """
---
## Section G — Research-Signal Triangulation

Combines support, crude association, adjusted association, predictor-level
BH-FDR, `current_compact_ridge_member` (and, where available, the explicitly
HISTORICAL `historical_lasso_*` fields — see Section E), and
rarity/separation status for each endometriosis-specific predictor.

The adjusted association fields merged in below come ONLY from the PRIMARY
model variant's source-level rows in `adjusted_master` (Section F) — never
the SENSITIVITY_IVF variant and never a categorical level-detail row — so
each of the 35 endometriosis predictors contributes exactly one unambiguous
adjusted estimate here.

Automatic code assigns **only** the objective statuses `INSUFFICIENT_SUPPORT`,
`STANDARD_OR_NOT_ESTIMABLE`, `SPARSE_EXPLORATORY`, `REVIEW_REQUIRED` — never
a scientific label like `PROMISING_EXPLORATORY`,
`CONSISTENT_MULTI-SOURCE_SIGNAL`, or `NO_APPARENT_SIGNAL`. This table carries
no placeholder scientific-conclusion column at all: the written project
report, not this executable notebook, is where the evidence below is
manually interpreted.
""",
    ),
    code(
        "pub-s16-evidence-table",
        """
research_signal_evidence = signal.build_research_signal_evidence(
    endometriosis_findings, adjusted_df=adjusted_master
)

print(f"research-signal evidence rows: {len(research_signal_evidence)} (expected 35, no duplicates)")
assert len(research_signal_evidence) == 35
assert not research_signal_evidence["predictor"].duplicated().any()

exports.save_table_csv(research_signal_evidence, exports.RESEARCH_SIGNAL_EVIDENCE_CSV)
research_signal_evidence
""",
    ),
]

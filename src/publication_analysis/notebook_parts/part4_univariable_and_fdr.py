"""Publication notebook — Part 4: full 81-predictor univariable master
dispatcher and the single global predictor-level BH-FDR family (both
Section D)."""
from publication_analysis.notebook_parts._cell_helpers import code, md

PART4_CELLS = [
    md(
        "pub-s10-header",
        """
---
## Section D — Univariable Association Analysis (all 81 source predictors)

`run_univariable_master(...)` dispatches **every one of the 81 source
predictors** by its `inferential_role` in the representation contract:

- `BINARY` → value-1-vs-value-0 logistic association (reference = value 0).
  The label is **"value 1 vs value 0"**, not "present vs absent" — see the
  contract's `binary_semantic_status`: only `EXPLICITLY_DOCUMENTED`
  predictors have a repository-documented clinical present/absent/yes/no
  meaning; `GENERIC_1_VS_0` predictors report only the numeric contrast;
- `CONTINUOUS` / `COUNT` with `functional_form_status = LINEAR_FORM_APPROVED`
  → OR per the contract's `continuous_unit_scale`;
- `CONTINUOUS` with `functional_form_status = NONLINEAR_FORM_APPROVED`
  (`weight_before_pregnancy`, `gestational_age_at_delivery_days`) → fixed
  natural cubic spline (df=3), **no single OR** — a source-level spline
  omnibus cluster-robust Wald p-value in `omnibus_p_value`;
- `CATEGORICAL` → an explicit-reference model: one `row_type='source'` row
  carrying the **source-level omnibus** p-value (its `support_status` is
  `SEE_LEVEL_SUPPORT`, not a blanket `OK` — support is inherently
  level-specific), plus one `row_type='level'` row per non-reference level
  with its own level-specific `support_status` **and** level-specific
  `level_unique_subjects` (computed within that level's rows only, never
  copied from the whole model's subject count);
- `DESCRIPTIVE_ONLY` / `PENDING_REPRESENTATION_REVIEW` → retained with
  `fit_status = NOT_FITTED` and a stated reason.

No predictor is dropped. Sample adequacy is reported as `model_analysis_N` /
`model_events` / `model_non_events` / `model_unique_subjects` (and, for
binary predictors, `value_1_n` / `value_0_n` / `value_1_events` /
`value_0_events` — numerically neutral names, never "exposed"/"unexposed",
since a `GENERIC_1_VS_0` predictor has no repository-documented clinical
exposure meaning) — never collapsed into a single "analysis_n". A
`CONTINUOUS`/`COUNT` predictor's `support_status` is `NOT_APPLICABLE_
CONTINUOUS_COUNT`, never `OK`/`SPARSE_EXPLORATORY`/`INSUFFICIENT_SUPPORT`
derived from outcome-cell counts — those describe outcome balance, not
predictor/exposure support, and a continuous/count predictor has no
carrier cell to be sparse in. A non-estimable MLE (complete / quasi-separation, zero
cells, numerical failure) is kept with a transparent `fit_status`, never
given a fabricated OR. Firth-type penalized regression is out of scope here.

Standard errors are subject-cluster-robust on the Section A grouping key.
""",
    ),
    code(
        "pub-s10-imports",
        """
from publication_analysis import univariable_analysis as uni
from publication_analysis import compact_tables
from publication_analysis import publication_display_labels
""",
    ),
    md(
        "pub-s09b-functional-form-header",
        """
### Pre-check — FINAL FUNCTIONAL-FORM LOCK

**Appears BEFORE the univariable master dispatch below.** APPROVING A
REPORTING UNIT IS NOT THE SAME AS PROVING A PARTICULAR LOG-ODDS FUNCTIONAL
FORM. Every `CONTINUOUS` / `COUNT` predictor in the representation contract
carries a separate `functional_form_status`, gated independently of
`publication_status` / `inferential_role`. The functional-form review that
followed the diagnostics under
`outputs/publication_analysis/audit/functional_form_review.csv` is now
**manually locked** — a final, clinical/methodological decision, not an
automatic p<0.05 rule:

- **`LINEAR_FORM_APPROVED` (6 predictors):** `AGE`, `BMI_before`, `height`,
  `Hb_before_delivery`, `G`, `AB` — ordinary one-slope logistic association,
  subject-cluster-robust covariance, one OR / 95% CI / coefficient p-value
  per the approved reporting unit.
- **`NONLINEAR_FORM_APPROVED` (2 predictors):** `weight_before_pregnancy`,
  `gestational_age_at_delivery_days` — fixed natural cubic spline
  (`patsy cr(x, df=3, constraints="center")`), subject-cluster-robust
  covariance, **no single OR** — the source-level result is a spline omnibus
  cluster-robust Wald p-value. `gestational_age_at_delivery_days` is Stage 3 /
  intrapartum-horizon; it is never interpreted as a baseline risk factor.
- **`DESCRIPTIVE_ONLY` (moved out of COUNT):** `P`, `CS`, `LIVE_BIRTH` — no
  primary whole-cohort OR is fitted (see the corrected `nulliparity` and
  `S_P_CS` predictors for the clinically interpretable contrasts). Still
  fully visible in Table 1 / the quality audit / descriptive support outputs.

These are manually reviewed, **data-informed, exploratory** methodological
decisions — reporting units were chosen for clinical interpretability, and
the linear-vs-nonlinear review then used the observed study data and
outcome. No outcome-derived cutpoint was created, and no functional form was
selected by an automatic p-value rule; findings for these predictors remain
exploratory rather than confirmatory, not prospectively prespecified.

`run_univariable_master(...)` now dispatches `LINEAR_FORM_APPROVED` to the
one-slope OR path and `NONLINEAR_FORM_APPROVED` to the fixed-spline omnibus
path; any other `functional_form_status` value still yields
`fit_status = NOT_FITTED`, **fail-loud, with no override flag** — there is no
executable path left where an unresolved functional form is silently fitted.
""",
    ),
    code(
        "pub-s09b-functional-form-load",
        """
import pandas as pd

functional_form_review_path = exports.AUDIT_DIR / exports.FUNCTIONAL_FORM_REVIEW_CSV
if functional_form_review_path.exists():
    functional_form_review = pd.read_csv(functional_form_review_path)
    print(f"functional-form review table (diagnostic evidence, not re-run here): {len(functional_form_review)} rows")
    print(functional_form_review["functional_form_status"].value_counts().to_string())
else:
    functional_form_review = None
    print(
        f"functional_form_review.csv not found at {functional_form_review_path} -- "
        "run analysis/publication_analysis/run_functional_form_diagnostic.py first."
    )

print("FINAL locked functional_form_status counts (representation contract):")
print(representation_contract["functional_form_status"].value_counts().to_string())

ff_gated_predictors = sorted(
    representation_contract.loc[
        ~representation_contract["functional_form_status"].isin(
            ["LINEAR_FORM_APPROVED", "NONLINEAR_FORM_APPROVED", "NOT_APPLICABLE"]
        ),
        "predictor",
    ]
)
print(f"predictors still gated (unresolved functional_form_status) ({len(ff_gated_predictors)}): "
      f"{ff_gated_predictors}")
assert len(ff_gated_predictors) == 0, "FINAL FUNCTIONAL-FORM LOCK expects zero unresolved predictors"
functional_form_review
""",
    ),
    code(
        "pub-s10-run-univariable-master",
        """
univariable_master = uni.run_univariable_master(
    matrix_df=df,
    contract_df=representation_contract,
    outcome_col=TARGET_COL,
    subject_groups=subject_groups,
)

n_source = int((univariable_master["row_type"] == "source").sum())
print(f"source-level rows (one per predictor): {n_source}")
print(f"total rows (incl. categorical level detail): {len(univariable_master)}")
print(univariable_master["fit_status"].value_counts().to_string())

exports.save_table_csv(univariable_master, exports.UNIVARIABLE_MASTER_CSV)
univariable_master.head(25)
""",
    ),
    md(
        "pub-s11-header",
        """
### One global predictor-level BH-FDR family

`build_predictor_level_hypothesis_table(...)` reduces the master table to
**exactly one source-level hypothesis row per predictor** (81 rows):
`binary_coefficient` / `continuous_coefficient` / `count_coefficient` /
`categorical_omnibus` / `nonlinear_spline_omnibus` / `not_estimable`.
Categorical predictors enter the family **once**, via their omnibus p-value;
the two `NONLINEAR_FORM_APPROVED` predictors likewise enter **once**, via
their spline omnibus cluster-robust Wald p-value — no individual
spline-basis coefficient p-value ever becomes an independent family member.

`apply_global_bh(...)` then runs Benjamini-Hochberg **once** across every
estimable source-level raw p-value. It is an exploratory research aid only —
never used to decide model eligibility or to delete a predictor from a
table. The Checkpoint-C endometriosis family will **join** this global
`bh_q`, never recompute its own.
""",
    ),
    code(
        "pub-s11-global-bh",
        """
hypothesis_table = uni.build_predictor_level_hypothesis_table(univariable_master)
assert len(hypothesis_table) == 81, "expected exactly 81 source-level hypothesis rows"

hypothesis_fdr = uni.apply_global_bh(hypothesis_table)

n_estimable = int(hypothesis_fdr["in_bh_family"].sum())
print(f"source-level hypothesis rows: {len(hypothesis_fdr)}")
print(f"estimable raw p-values in the single BH family: {n_estimable}")
print(hypothesis_table["hypothesis_type"].value_counts().to_string())

exports.save_table_csv(hypothesis_fdr, exports.PREDICTOR_LEVEL_HYPOTHESIS_FDR_CSV)
hypothesis_fdr.sort_values("raw_p", na_position="last").head(25)
""",
    ),
    md(
        "pub-s11b-levels-header",
        """
### Categorical level-detail (reporting only — not part of the BH family)

The per-level ORs / CIs for `CATEGORICAL` predictors, shown for
interpretation. These `row_type='level'` rows are reporting detail; the
multiple-testing family above used one omnibus p-value per categorical
source predictor.
""",
    ),
    code(
        "pub-s11b-level-detail",
        """
categorical_level_detail = univariable_master[
    univariable_master["row_type"] == "level"
].copy()

exports.save_table_csv(
    categorical_level_detail, exports.UNIVARIABLE_PREDICTOR_LEVEL_TESTS_CSV
)
categorical_level_detail
""",
    ),
    md(
        "pub-s11c-compact-table2-header",
        """
### Compact Table 2 — univariable associations of final Compact Ridge predictors

The full Section D tables above remain the complete Appendix-level
univariable evidence for all 81 source predictors. This compact table contains
only the six predictors included in the locked final Compact Ridge
architecture. Membership is **not** determined by raw p-value, BH-FDR q-value,
odds-ratio magnitude, rank, or statistical significance.

For the multi-level hypertensive-disorder predictor, the source row preserves
the canonical source-level omnibus inference. Its non-reference category rows
are displayed underneath as category subrows so the crude category-specific
ORs/CIs can be read. Those subrows are not additional predictors, not separate
Compact Ridge selections, and not separate BH-FDR hypotheses.
""",
    ),
    code(
        "pub-s11c-compact-table2",
        """
univariable_master_saved = pd.read_csv(exports.TABLES_DIR / exports.UNIVARIABLE_MASTER_CSV)
hypothesis_fdr_saved = pd.read_csv(
    exports.TABLES_DIR / exports.PREDICTOR_LEVEL_HYPOTHESIS_FDR_CSV
)

compact_table2 = compact_tables.build_compact_table2(
    univariable_master=univariable_master_saved,
    hypothesis_fdr=hypothesis_fdr_saved,
    representation_contract=representation_contract,
    predictor_display_labels=publication_display_labels.DISPLAY_LABELS,
)
compact_tables.assert_compact_table2_matches_sources(
    compact_table2=compact_table2,
    univariable_master=univariable_master_saved,
    hypothesis_fdr=hypothesis_fdr_saved,
    representation_contract=representation_contract,
    predictor_display_labels=publication_display_labels.DISPLAY_LABELS,
)

compact_table2_source_rows = int((compact_table2["Row type"] == "source").sum())
compact_table2_subrows = compact_table2.loc[
    compact_table2["Row type"] == "category_subrow",
    ["Variable", "Level", "Reference", "Crude OR", "95% CI", "Level p"],
]
print(f"Compact Table 2 source rows: {compact_table2_source_rows}")
print(f"Compact Table 2 categorical subrows: {len(compact_table2_subrows)}")
print("Compact Table 2 source variables:")
print(list(compact_table2.loc[compact_table2["Row type"] == "source", "Variable"]))
assert compact_table2_source_rows == 6

exports.save_table_csv(
    compact_table2,
    exports.TABLE_2_COMPACT_FINAL_PREDICTORS_UNIVARIABLE_CSV,
)
exports.save_table_xlsx(
    compact_table2,
    exports.TABLE_2_COMPACT_FINAL_PREDICTORS_UNIVARIABLE_XLSX,
)
compact_table2
""",
    ),
]

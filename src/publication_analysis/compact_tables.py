"""Researcher-approved compact publication tables.

The compact tables are display subsets of the already-built publication
evidence. They never refit models and never select rows by p-value, q-value,
odds-ratio magnitude, or any other outcome-driven ranking.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Mapping

import pandas as pd

TABLE1_COLUMNS = [
    "Variable",
    "Clinical Label",
    "Stage",
    "Overall",
    "Vaginal delivery",
    "Intrapartum CS",
    "Missing n (%)",
]

COMPACT_TABLE1_CONCEPT_TO_VARIABLE = OrderedDict(
    [
        ("Maternal age", "AGE"),
        ("Pre-pregnancy BMI", "BMI_before"),
        ("Nulliparity", "nulliparity"),
        ("Prior cesarean section", "S_P_CS"),
        (
            "Hypertensive disease spectrum",
            "derived_hypertension_pih_pet_spectrum",
        ),
        ("Labor induction", "induction_any_bin"),
        ("Prior VBAC history", "VBAC"),
        ("Mode of conception", "mode_of_conception"),
        ("Gestational age at delivery", "gestational_age_at_delivery_days"),
        ("Deep endometriosis", "deep_endometriosis"),
        ("Endometrioma", "endometrioma"),
        ("Adenomyosis", "adenomyosis"),
        ("Prior endometriosis surgery", "endometriosis_surgery"),
    ]
)

FINAL_COMPACT_RIDGE_PREDICTORS = (
    "AGE",
    "BMI_before",
    "nulliparity",
    "S_P_CS",
    "derived_hypertension_pih_pet_spectrum",
    "induction_any_bin",
)

TABLE2_COMPACT_COLUMNS = [
    "Variable",
    "Clinical Label",
    "Row type",
    "Level",
    "Reference",
    "Stage",
    "Effect representation / comparison",
    "N",
    "Events",
    "Non-events",
    "Unique subjects",
    "Crude OR",
    "95% CI",
    "Predictor-level raw p",
    "Predictor-level BH q",
    "Level p",
    "In BH family",
    "Fit status",
    "Separation status",
    "Support status",
    "Reason",
]


class CompactTableError(RuntimeError):
    """Raised when a compact table cannot be derived from canonical evidence."""


def _base_variable(display_variable: object) -> str:
    return str(display_variable).split(": ", 1)[0]


def _clean_cell(value: object) -> object:
    if pd.isna(value):
        return ""
    return value


def _format_ci(row: pd.Series, low_col: str, high_col: str) -> str:
    low = row.get(low_col)
    high = row.get(high_col)
    if pd.isna(low) or pd.isna(high) or low == "" or high == "":
        return ""
    return f"{low}-{high}"


def build_compact_table1(full_table1: pd.DataFrame) -> pd.DataFrame:
    """Return the approved compact descriptive Table 1.

    Rows are copied directly from the full Table 1. For categorical source
    variables, every full-table display row for that source variable is kept.
    """
    missing_cols = [c for c in TABLE1_COLUMNS if c not in full_table1.columns]
    if missing_cols:
        raise CompactTableError(f"Full Table 1 missing columns: {missing_cols}")

    full = full_table1.loc[:, TABLE1_COLUMNS].copy()
    full["_base_variable"] = full["Variable"].map(_base_variable)

    selected_frames = []
    for concept, variable in COMPACT_TABLE1_CONCEPT_TO_VARIABLE.items():
        rows = full.loc[full["_base_variable"] == variable, TABLE1_COLUMNS]
        if rows.empty:
            raise CompactTableError(
                f"Compact Table 1 concept {concept!r} maps to {variable!r}, "
                "but no matching row was found in Full Table 1."
            )
        selected_frames.append(rows)

    compact = pd.concat(selected_frames, ignore_index=True)
    observed_sources = compact["Variable"].map(_base_variable).nunique()
    expected_sources = len(COMPACT_TABLE1_CONCEPT_TO_VARIABLE)
    if observed_sources != expected_sources:
        raise CompactTableError(
            f"Compact Table 1 expected {expected_sources} source concepts, "
            f"observed {observed_sources}."
        )
    return compact


def assert_compact_table1_matches_full(
    compact_table1: pd.DataFrame, full_table1: pd.DataFrame
) -> None:
    """Fail if any compact Table 1 row differs from the full-table source row."""
    full = full_table1.loc[:, TABLE1_COLUMNS].copy()
    for idx, row in compact_table1.loc[:, TABLE1_COLUMNS].iterrows():
        mask = full["Variable"].eq(row["Variable"])
        if not mask.any():
            raise CompactTableError(
                f"Compact Table 1 row {idx} variable {row['Variable']!r} "
                "is absent from Full Table 1."
            )
        source = full.loc[mask].iloc[0]
        if not source.equals(row):
            raise CompactTableError(
                f"Compact Table 1 row {idx} for {row['Variable']!r} does not "
                "match the Full Table 1 source row exactly."
            )


def _stage_map_from_contract(representation_contract: pd.DataFrame) -> dict[str, object]:
    if "predictor" not in representation_contract.columns:
        raise CompactTableError("Representation contract missing 'predictor'.")
    if "earliest_entry_stage" not in representation_contract.columns:
        raise CompactTableError(
            "Representation contract missing 'earliest_entry_stage'."
        )
    return dict(
        zip(
            representation_contract["predictor"],
            representation_contract["earliest_entry_stage"],
            strict=False,
        )
    )


def build_compact_table2(
    univariable_master: pd.DataFrame,
    hypothesis_fdr: pd.DataFrame,
    representation_contract: pd.DataFrame,
    predictor_display_labels: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Return crude univariable results for the six final Ridge predictors.

    The six source rows are selected only by the locked Compact Ridge predictor
    list. Categorical level rows are added only as subrows for those selected
    predictors and carry no separate BH q-value.
    """
    predictor_display_labels = predictor_display_labels or {}
    stage_map = _stage_map_from_contract(representation_contract)

    master_cols = {"predictor", "row_type", "inferential_role", "fit_status"}
    missing_master = sorted(master_cols - set(univariable_master.columns))
    if missing_master:
        raise CompactTableError(
            f"Univariable master missing columns: {missing_master}"
        )

    fdr_cols = {"predictor", "raw_p", "bh_q", "in_bh_family"}
    missing_fdr = sorted(fdr_cols - set(hypothesis_fdr.columns))
    if missing_fdr:
        raise CompactTableError(f"Hypothesis FDR table missing columns: {missing_fdr}")

    fdr_by_predictor = hypothesis_fdr.set_index("predictor", drop=False)
    rows = []

    for predictor in FINAL_COMPACT_RIDGE_PREDICTORS:
        source_matches = univariable_master.loc[
            (univariable_master["predictor"] == predictor)
            & (univariable_master["row_type"] == "source")
        ]
        if len(source_matches) != 1:
            raise CompactTableError(
                f"Expected one source row for {predictor!r}; found "
                f"{len(source_matches)}."
            )
        if predictor not in fdr_by_predictor.index:
            raise CompactTableError(f"No predictor-level FDR row for {predictor!r}.")

        source = source_matches.iloc[0]
        fdr = fdr_by_predictor.loc[predictor]
        label = predictor_display_labels.get(predictor, predictor)
        rows.append(
            {
                "Variable": predictor,
                "Clinical Label": label,
                "Row type": "source",
                "Level": "",
                "Reference": _clean_cell(source.get("reference_level", "")),
                "Stage": stage_map.get(predictor, ""),
                "Effect representation / comparison": _clean_cell(
                    source.get("effect_representation", "")
                ),
                "N": _clean_cell(source.get("model_analysis_N", "")),
                "Events": _clean_cell(source.get("model_events", "")),
                "Non-events": _clean_cell(source.get("model_non_events", "")),
                "Unique subjects": _clean_cell(
                    source.get("model_unique_subjects", "")
                ),
                "Crude OR": _clean_cell(source.get("odds_ratio", "")),
                "95% CI": _format_ci(source, "ci_low", "ci_high"),
                "Predictor-level raw p": _clean_cell(fdr.get("raw_p", "")),
                "Predictor-level BH q": _clean_cell(fdr.get("bh_q", "")),
                "Level p": "",
                "In BH family": _clean_cell(fdr.get("in_bh_family", "")),
                "Fit status": _clean_cell(source.get("fit_status", "")),
                "Separation status": _clean_cell(
                    source.get("separation_status", "")
                ),
                "Support status": _clean_cell(source.get("support_status", "")),
                "Reason": _clean_cell(source.get("reason", "")),
            }
        )

        level_rows = univariable_master.loc[
            (univariable_master["predictor"] == predictor)
            & (univariable_master["row_type"] == "level")
        ]
        for _, level in level_rows.iterrows():
            rows.append(
                {
                    "Variable": predictor,
                    "Clinical Label": label,
                    "Row type": "category_subrow",
                    "Level": _clean_cell(level.get("level", "")),
                    "Reference": _clean_cell(level.get("reference_level", "")),
                    "Stage": stage_map.get(predictor, ""),
                    "Effect representation / comparison": _clean_cell(
                        level.get("effect_representation", "")
                    ),
                    "N": _clean_cell(level.get("level_n", "")),
                    "Events": _clean_cell(level.get("level_events", "")),
                    "Non-events": _clean_cell(level.get("level_non_events", "")),
                    "Unique subjects": _clean_cell(
                        level.get("level_unique_subjects", "")
                    ),
                    "Crude OR": _clean_cell(level.get("odds_ratio", "")),
                    "95% CI": _format_ci(level, "ci_low", "ci_high"),
                    "Predictor-level raw p": "",
                    "Predictor-level BH q": "",
                    "Level p": _clean_cell(level.get("coef_p_value", "")),
                    "In BH family": False,
                    "Fit status": _clean_cell(level.get("fit_status", "")),
                    "Separation status": _clean_cell(
                        level.get("separation_status", "")
                    ),
                    "Support status": _clean_cell(level.get("support_status", "")),
                    "Reason": _clean_cell(level.get("reason", "")),
                }
            )

    compact = pd.DataFrame(rows, columns=TABLE2_COMPACT_COLUMNS)
    source_count = int((compact["Row type"] == "source").sum())
    if source_count != len(FINAL_COMPACT_RIDGE_PREDICTORS):
        raise CompactTableError(
            f"Compact Table 2 expected {len(FINAL_COMPACT_RIDGE_PREDICTORS)} "
            f"source rows, observed {source_count}."
        )
    observed_sources = tuple(compact.loc[compact["Row type"] == "source", "Variable"])
    if observed_sources != FINAL_COMPACT_RIDGE_PREDICTORS:
        raise CompactTableError(
            "Compact Table 2 source-row order/membership mismatch: "
            f"{observed_sources!r}."
        )
    return compact


def assert_compact_table2_matches_sources(
    compact_table2: pd.DataFrame,
    univariable_master: pd.DataFrame,
    hypothesis_fdr: pd.DataFrame,
    representation_contract: pd.DataFrame,
    predictor_display_labels: Mapping[str, str] | None = None,
) -> None:
    """Fail if compact Table 2 no longer matches canonical univariable evidence."""
    rebuilt = build_compact_table2(
        univariable_master=univariable_master,
        hypothesis_fdr=hypothesis_fdr,
        representation_contract=representation_contract,
        predictor_display_labels=predictor_display_labels,
    )
    observed = compact_table2.reset_index(drop=True).copy()
    expected = rebuilt.reset_index(drop=True).copy()
    observed = observed.fillna("")
    expected = expected.fillna("")
    pd.testing.assert_frame_equal(
        observed,
        expected,
        check_dtype=False,
    )

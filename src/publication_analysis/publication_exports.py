"""Export contract for publication-analysis tables and figures (Section 18).

Every write in this module is validated to land under
``outputs/publication_analysis/`` — never under ``outputs/final_modeling/``
or anywhere else. This is enforced by ``assert_safe_output_path`` on every
save call, not just documented by convention.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_ROOT = REPO_ROOT / "outputs" / "publication_analysis"
TABLES_DIR = OUTPUT_ROOT / "tables"
FIGURES_DIR = OUTPUT_ROOT / "figures"
AUDIT_DIR = OUTPUT_ROOT / "audit"
INTERMEDIATE_DIR = OUTPUT_ROOT / "intermediate"

FORBIDDEN_ROOTS = [
    REPO_ROOT / "outputs" / "final_modeling",
    REPO_ROOT / "analysis" / "modeling" / "final_modeling",
]

# Expected table filenames (Section 18).
TABLE_1_FULL_DESCRIPTIVE_CSV = "table_1_full_descriptive.csv"
TABLE_1_FULL_DESCRIPTIVE_XLSX = "table_1_full_descriptive.xlsx"
TABLE_1_COMPACT_DESCRIPTIVE_CSV = "table_1_compact_descriptive.csv"
TABLE_1_COMPACT_DESCRIPTIVE_XLSX = "table_1_compact_descriptive.xlsx"
VARIABLE_REPRESENTATION_AUDIT_CSV = "variable_representation_audit.csv"
PUBLICATION_REPRESENTATION_CONTRACT_CSV = "publication_representation_contract.csv"
REPRESENTATION_SIGNOFF_REVIEW_CSV = "representation_signoff_review.csv"
MISSINGNESS_SUPPORT_AUDIT_CSV = "missingness_support_audit.csv"
UNIVARIABLE_OR_FULL_CSV = "univariable_or_full.csv"
UNIVARIABLE_MASTER_CSV = "univariable_master.csv"
PREDICTOR_LEVEL_HYPOTHESIS_FDR_CSV = "predictor_level_hypothesis_fdr.csv"
UNIVARIABLE_PREDICTOR_LEVEL_TESTS_CSV = "univariable_predictor_level_tests.csv"
TABLE_2_COMPACT_FINAL_PREDICTORS_UNIVARIABLE_CSV = (
    "table_2_compact_final_predictors_univariable.csv"
)
TABLE_2_COMPACT_FINAL_PREDICTORS_UNIVARIABLE_XLSX = (
    "table_2_compact_final_predictors_univariable.xlsx"
)
APPENDIX_TABLE_A2_FULL_UNIVARIABLE_CSV = "appendix_table_a2_full_univariable.csv"
APPENDIX_TABLE_A2_FULL_UNIVARIABLE_XLSX = "appendix_table_a2_full_univariable.xlsx"
APPENDIX_TABLE_A2_FULL_UNIVARIABLE_MD = "appendix_table_a2_full_univariable.md"
ENDOMETRIOSIS_FINDINGS_CSV = "endometriosis_findings.csv"
ADJUSTED_ENDOMETRIOSIS_ANALYSIS_CSV = "adjusted_endometriosis_analysis.csv"
ADJUSTED_PRIMARY_VS_SENSITIVITY_CSV = "adjusted_primary_vs_sensitivity.csv"
RESEARCH_SIGNAL_EVIDENCE_CSV = "research_signal_evidence.csv"
FUNCTIONAL_FORM_REVIEW_CSV = "functional_form_review.csv"
FUNCTIONAL_FORM_COUNT_SUPPORT_CSV = "functional_form_count_value_support.csv"
FUNCTIONAL_FORM_COUNT_LEVEL_PREDICTIONS_CSV = "functional_form_count_level_predictions.csv"

# Functional-form diagnostic audit figures live in their own subdirectory
# under AUDIT_DIR (Representation Sign-off + Functional-Form Gate task §13).
FUNCTIONAL_FORM_FIGURES_DIR = AUDIT_DIR / "functional_form"

# Expected figure filename patterns (Section 18).
FOREST_UNIVARIABLE_PREFIX = "forest_univariable_"
FOREST_ENDOMETRIOSIS_CRUDE_PNG = "forest_endometriosis_crude.png"
FOREST_ENDOMETRIOSIS_ADJUSTED_PNG = "forest_endometriosis_adjusted.png"
INCREMENTAL_VALUE_BY_STAGE_PNG = "incremental_value_by_stage.png"


class PublicationExportPathError(RuntimeError):
    """Raised when an export path resolves outside outputs/publication_analysis/."""


def assert_safe_output_path(path: Path) -> Path:
    resolved = path.resolve()
    output_root_resolved = OUTPUT_ROOT.resolve()
    try:
        resolved.relative_to(output_root_resolved)
    except ValueError as exc:
        raise PublicationExportPathError(
            f"Refusing to write outside {output_root_resolved}: {resolved}"
        ) from exc

    for forbidden in FORBIDDEN_ROOTS:
        forbidden_resolved = forbidden.resolve()
        try:
            resolved.relative_to(forbidden_resolved)
        except ValueError:
            continue
        raise PublicationExportPathError(
            f"Refusing to write under forbidden path {forbidden_resolved}: {resolved}"
        )

    return resolved


def _resolve_export_path(filename: str, subdir: Path) -> Path:
    path = subdir / filename
    return assert_safe_output_path(path)


def ensure_output_dirs() -> None:
    for directory in (TABLES_DIR, FIGURES_DIR, AUDIT_DIR, INTERMEDIATE_DIR):
        assert_safe_output_path(directory / ".keep").parent.mkdir(parents=True, exist_ok=True)


def save_table_csv(df: pd.DataFrame, filename: str, subdir: Path | None = None) -> Path:
    path = _resolve_export_path(filename, subdir if subdir is not None else TABLES_DIR)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def save_table_xlsx(df: pd.DataFrame, filename: str, subdir: Path | None = None) -> Path:
    path = _resolve_export_path(filename, subdir if subdir is not None else TABLES_DIR)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
    return path


def _dataframe_to_markdown(df: pd.DataFrame) -> str:
    """Minimal GitHub-flavored-Markdown table renderer (no ``tabulate`` dependency)."""
    headers = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in df.iterrows():
        cells = ["" if pd.isna(v) else str(v) for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def save_table_markdown(df: pd.DataFrame, filename: str, subdir: Path | None = None) -> Path:
    """Write a Markdown rendering suitable for direct project-book insertion."""
    path = _resolve_export_path(filename, subdir if subdir is not None else TABLES_DIR)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dataframe_to_markdown(df), encoding="utf-8")
    return path


def save_figure(fig, filename: str, subdir: Path | None = None, dpi: int = 200) -> Path:
    path = _resolve_export_path(filename, subdir if subdir is not None else FIGURES_DIR)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path


def display_saved_figure(path: Path) -> None:
    """Display an already-saved PNG file inline via ``IPython.display.Image``.

    Backend-independent: never relies on the active matplotlib backend (e.g.
    the headless ``Agg`` backend used throughout this package) providing an
    ``image/png`` MIME representation for a bare ``display(fig)`` call, which
    silently falls back to a text-only ``Figure(...)`` repr under ``Agg`` with
    no inline-backend hook registered. Does not redraw, resize, or otherwise
    modify the figure — it only re-displays the exact bytes already written
    to disk by ``save_figure``.
    """
    from IPython.display import Image, display

    display(Image(filename=str(path)))

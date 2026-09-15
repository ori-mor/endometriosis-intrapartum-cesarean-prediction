# Reusable utility functions for the preprocessing pipeline.
# All functions are clinically neutral — they handle data mechanics only.
# Clinical recoding decisions live in run_preprocessing.py batch functions.

import pandas as pd
import numpy as np
import os
import csv
import re
import hashlib
import subprocess
from datetime import datetime


# ---------------------------------------------------------------------------
# Column mapping utilities
# ---------------------------------------------------------------------------

def build_rename_map(column_mapping):
    """Return {raw_name: standardized_name} for columns whose names differ."""
    return {raw: std for raw, std, _, _ in column_mapping if raw != std}


def validate_mapping(df_columns, column_mapping):
    """
    Check that every raw column in df is present in column_mapping.
    Returns (ok: bool, unmapped: list, dup_in_mapping: list).
    """
    mapped_raws = {raw for raw, _, _, _ in column_mapping}
    unmapped = [c for c in df_columns if c not in mapped_raws]
    seen = {}
    dup_in_mapping = []
    for raw, std, _, _ in column_mapping:
        if raw in seen:
            dup_in_mapping.append((raw, seen[raw], std))
        else:
            seen[raw] = std
    return len(unmapped) == 0 and len(dup_in_mapping) == 0, unmapped, dup_in_mapping


def save_column_mapping_csv(column_mapping, out_path):
    """Write column_mapping.csv."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["raw_column_name", "standardized_name", "mapping_type", "notes"])
        for raw, std, mtype, notes in column_mapping:
            writer.writerow([raw, std, mtype, notes])


# ---------------------------------------------------------------------------
# Missing value utilities
# ---------------------------------------------------------------------------

def normalize_missing_values(series, extra_tokens=None):
    """
    Replace common representations of missing/unknown with NaN.

    Recognized tokens (case-insensitive, after stripping): empty string,
    whitespace-only, 'na', 'n/a', 'nan', 'none', 'null', 'unknown',
    'not known', 'not available', 'לא ידוע', 'לא ידוע (לפני 2019)'.
    Pass extra_tokens list to extend.

    Returns a new Series; original is not modified.
    """
    DEFAULT_TOKENS = {
        "", "na", "n/a", "nan", "none", "null",
        "unknown", "not known", "not available",
        "לא ידוע",          # לא ידוע
        "לא ידוע (לפני 2019)",  # לא ידוע (לפני 2019)
    }
    tokens = DEFAULT_TOKENS | set(t.lower() for t in (extra_tokens or []))

    def _replace(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip().lower()
        if s in tokens:
            return np.nan
        return val

    return series.map(_replace)


# ---------------------------------------------------------------------------
# Binary / numeric cleaning
# ---------------------------------------------------------------------------

def clean_binary_numeric(series, pos_values=None, neg_values=None):
    """
    Coerce a series to clean binary 0/1 integers.

    pos_values: additional raw values that map to 1  (e.g. ['yes', 'כן'])
    neg_values: additional raw values that map to 0  (e.g. ['no', 'לא'])

    Numeric 1 -> 1, numeric 0 -> 0.
    Unrecognized values -> NaN.
    NaN stays NaN.
    Returns a new Series (float to accommodate NaN).
    """
    pos = {1, "1", "yes", "true"} | set(v.lower() if isinstance(v, str) else v for v in (pos_values or []))
    neg = {0, "0", "no", "false"} | set(v.lower() if isinstance(v, str) else v for v in (neg_values or []))

    def _coerce(val):
        if pd.isna(val):
            return np.nan
        v = val if not isinstance(val, str) else val.strip().lower()
        if v in pos:
            return 1.0
        if v in neg:
            return 0.0
        try:
            n = float(val)
            if n == 1.0:
                return 1.0
            if n == 0.0:
                return 0.0
        except (ValueError, TypeError):
            pass
        return np.nan

    return series.map(_coerce)


def validate_expected_binary_values(series, col_name, allowed=None):
    """
    Check that a series contains only expected values.
    allowed defaults to {0, 1, np.nan}.
    Returns (ok: bool, unexpected_values: list).
    """
    if allowed is None:
        allowed = {0, 1, 0.0, 1.0, np.nan}
    unexpected = [v for v in series.unique() if not (
        (isinstance(v, float) and np.isnan(v)) or v in allowed
    )]
    return len(unexpected) == 0, unexpected


# ---------------------------------------------------------------------------
# Free-text detection and splitting
# ---------------------------------------------------------------------------

def detect_free_text(series):
    """
    Return a boolean mask: True where cell contains free text
    (any letter, Hebrew or Latin).

    Genuine missing values (NaN, pd.NA, None, NaT) are excluded before any
    string conversion, so they are never turned into literal strings (e.g.
    "nan") and never classified as free text.
    """
    pattern = re.compile(r"[A-Za-zא-ת]")
    non_missing = series.notna()
    result = pd.Series(False, index=series.index, dtype=bool)
    result.loc[non_missing] = (
        series.loc[non_missing].astype(str).str.contains(pattern, na=False)
    )
    return result


def split_text_to_comment(df, source_col, comment_col):
    """
    For rows where source_col contains free text:
      - Copy the raw value into comment_col (creating it if absent).
      - Replace the source_col value with NaN so it can be recoded numerically.

    Does NOT assign a binary value — caller decides the recode logic.
    Returns modified df copy.
    """
    df = df.copy()
    if comment_col not in df.columns:
        df[comment_col] = np.nan
    text_mask = detect_free_text(df[source_col])
    # Only overwrite comment_col where it is currently empty
    empty_comment = df[comment_col].isna()
    df.loc[text_mask & empty_comment, comment_col] = df.loc[text_mask & empty_comment, source_col]
    # Clear text from source column
    df.loc[text_mask, source_col] = np.nan
    return df


# ---------------------------------------------------------------------------
# Multi-code field parsing
# ---------------------------------------------------------------------------

_SEPARATOR_RE = re.compile(r"[\s,;+/]+")


def normalize_multi_code_string(raw_value, valid_codes, strict=False):
    """
    Parse a raw cell value that may contain multiple integer codes.
    - Splits on whitespace, comma, semicolon, plus, slash.
    - Keeps only codes present in valid_codes (set/list of ints).
    - Removes duplicates, sorts ascending.
    - Returns a sorted list of valid int codes, or [] if nothing valid found.
    - Returns [] for NaN / empty / whitespace-only inputs.
    - A token that is not parseable as a number at all (e.g. stray
      punctuation debris from the separator split) is silently skipped, same
      as always -- it carries no numeric information to lose.
    - A token that IS parseable as a number but is not an exact integer or
      exact-integer-valued float (e.g. "3.4") is a DIFFERENT case: it looks
      like a genuine code with unexpected precision, not noise. This is
      never silently truncated to its integer part (`int(float("3.4"))`
      used to silently become `3`, a real data-corruption risk) -- it fails
      loud instead (ValueError), audit-visible at the exact source cell,
      consistent with this project's "flag for review, never auto-correct
      an ambiguous parse" convention used throughout preprocessing. This
      fail-loud behavior is unconditional -- it applies regardless of
      `strict`.

    `strict` (default False, preserves legacy behavior for all pre-existing
    callers -- start_of_labor, induction indication, indication_for_CS):
    - False (default): an exact-integer token outside `valid_codes` is
      silently dropped, same as always. This is the historical behavior
      relied upon by callers that were never audited for "unmapped code
      must surface" semantics.
    - True: an exact-integer token outside `valid_codes` is NOT silently
      dropped -- it raises ValueError instead (same "fail loud, audit
      visible" treatment already given to non-integer tokens like "3.4"),
      EXCEPT for the literal token `0`, which both callers using strict
      mode (adenomyosis sonographic features, endo_resection site codes)
      treat as a recognized non-informative sentinel handled at a separate
      layer above this function (an exact-zero *whole cell* has its own
      dedicated "no specific feature" / "no_resection" meaning resolved by
      the caller before or after this call) -- `0` is therefore still
      silently skipped when it is the ONLY meaningful numeric token in the
      cell, never raises in that case. However, if `0` appears ALONGSIDE
      any other numeric token (valid or invalid) in the same cell -- e.g.
      "0,1" or "1,0" -- that is not a clean exact-zero-sentinel cell and
      not an ordinary valid code list either; it is an ambiguous mixed
      value that could silently discard real clinical information (the
      zero) if resolved by simply dropping the zero and keeping the rest.
      In strict mode this raises ValueError rather than ever returning a
      partial code list. This preserves exact-zero-cell semantics
      unchanged while ensuring any other genuinely out-of-range numeric
      code (e.g. "12" when only 1-11 are valid), or a zero mixed with any
      other token, can never disappear silently -- the whole cell fails
      loud rather than returning a misleading partial code list.

    Example:
        normalize_multi_code_string("3, 5, 4, 10", range(1,12)) -> [3, 4, 5, 10]
        normalize_multi_code_string("3+5 4 10", range(1,12))    -> [3, 4, 5, 10]
        normalize_multi_code_string(0, range(1,12))             -> []
        normalize_multi_code_string(np.nan, range(1,12))        -> []
        normalize_multi_code_string("3.4", range(1,12))         -> raises ValueError
        normalize_multi_code_string("3.0", range(1,12))         -> [3]  (exact-integer-valued float)
        normalize_multi_code_string("12", range(1,12))                    -> []  (default, legacy silent drop)
        normalize_multi_code_string("12", range(1,12), strict=True)       -> raises ValueError
        normalize_multi_code_string("1,12", range(1,12), strict=True)     -> raises ValueError (never partial [1])
        normalize_multi_code_string("0", range(1,12), strict=True)        -> []  (exact-zero sentinel, alone)
        normalize_multi_code_string("0,1", range(1,12), strict=True)      -> raises ValueError (zero mixed with another token, never partial [1])
        normalize_multi_code_string("0,1", range(1,12))                   -> [1]  (default, legacy silent drop, unchanged)
    """
    if pd.isna(raw_value):
        return []
    valid_set = set(int(c) for c in valid_codes)
    tokens = _SEPARATOR_RE.split(str(raw_value).strip())
    parsed_ints = []
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        try:
            f = float(t)
        except (ValueError, TypeError):
            # Not parseable as a number at all -- noise, not a code; skipped
            # as before, no information lost.
            continue
        if not f.is_integer():
            raise ValueError(
                f"normalize_multi_code_string: token {t!r} in raw value {raw_value!r} parses as "
                f"a number ({f}) but is not an exact integer or exact-integer-valued float. "
                "This is not silently truncated -- it requires manual review before this cell "
                "can be parsed. If this is a genuine data-entry artifact, resolve it via an "
                "explicit, documented correction, not a silent int() coercion."
            )
        parsed_ints.append(int(f))

    if strict and 0 in parsed_ints and any(n != 0 for n in parsed_ints):
        raise ValueError(
            f"normalize_multi_code_string: raw value {raw_value!r} mixes the zero sentinel "
            f"token with another numeric token (parsed integers: {sorted(set(parsed_ints))}). "
            "An exact-zero cell has its own dedicated 'no specific feature' / 'no_resection' "
            "meaning and is only unambiguous when it is the sole numeric token in the cell. "
            "Zero combined with any other code is not silently resolved by dropping the zero -- "
            "resolve it via an explicit, documented correction before this cell can be parsed."
        )

    codes = []
    for n in parsed_ints:
        if n in valid_set:
            codes.append(n)
        elif strict and n != 0:
            raise ValueError(
                f"normalize_multi_code_string: raw value {raw_value!r} contains integer {n}, "
                f"which is outside the approved code set {sorted(valid_set)}. "
                "This is not silently dropped -- an unmapped numeric code could represent real "
                "clinical information. Resolve it via an explicit, documented correction before "
                "this cell can be parsed."
            )
    return sorted(set(codes))


def parse_multi_code_field(series, valid_codes, strict=False):
    """
    Apply normalize_multi_code_string to every cell in a Series.
    Returns a new Series of sorted lists of valid int codes.
    NaN / empty / all-invalid cells -> [].
    See normalize_multi_code_string for `strict` semantics.
    """
    return series.map(lambda v: normalize_multi_code_string(v, valid_codes, strict=strict))


def create_multihot_columns(df, source_col, valid_codes, prefix=None):
    """
    Expand a multi-code column into binary one-hot columns.

    source_col must already contain lists (output of parse_multi_code_field).
    Creates columns named  {prefix}_{code}  for each code in valid_codes.
    prefix defaults to source_col.

    Cells with an empty list get 0 in all columns.
    Returns df copy with new columns appended (source_col unchanged).
    """
    df = df.copy()
    pfx = prefix if prefix is not None else source_col
    for code in sorted(int(c) for c in valid_codes):
        col_name = f"{pfx}_{code}"
        df[col_name] = df[source_col].map(
            lambda lst: 1 if isinstance(lst, list) and code in lst else 0
        )
    return df


# ---------------------------------------------------------------------------
# Subgroup NA logic
# ---------------------------------------------------------------------------

def set_outside_subgroup_to_na(df, value_col, subgroup_mask, new_col=None):
    """
    Set values outside a subgroup to NaN:
      - Rows WHERE subgroup_mask is True  -> copy existing value as-is.
      - Rows WHERE subgroup_mask is False -> set to NaN (not relevant outside subgroup).

    If new_col is given, result goes into a new column (source preserved).
    If new_col is None, result overwrites value_col in-place.
    Returns df copy.

    Example use: suspected_endo_lesions_during_CS is only relevant for CS rows.
      set_outside_subgroup_to_na(df, 'suspected_endo_lesions_during_CS',
                                 df['type_of_CS'].isin([2,3]))
    """
    df = df.copy()
    target = new_col if new_col else value_col
    df[target] = np.where(subgroup_mask, df[value_col], np.nan)
    return df


# ---------------------------------------------------------------------------
# Review dataframe
# ---------------------------------------------------------------------------

def create_review_dataframe(df, mask, cols, id_cols=None):
    """
    Extract rows matching mask for manual review.
    id_cols: list of identifier columns to always include (e.g. ['delivery_id', 'subject_number']).
    cols: additional columns relevant to the review.
    Adds empty columns: manual_review_decision, manual_review_reason, manual_review_notes.
    Returns a new DataFrame (does not modify df).
    """
    id_cols = id_cols or []
    all_cols = [c for c in id_cols + cols if c in df.columns]
    review_df = df.loc[mask, all_cols].copy()
    review_df["manual_review_decision"] = np.nan
    review_df["manual_review_reason"] = np.nan
    review_df["manual_review_notes"] = np.nan
    return review_df


# ---------------------------------------------------------------------------
# diagnosis_date -> diagnosis_year unresolved-row QA (PARTNER-FIX-02)
# ---------------------------------------------------------------------------

# Values with an approved, explicit resolution status. Kept as literal-value
# sets (not regex) so the categorization below can never silently expand to
# match a value nobody has reviewed.
_DIAGNOSIS_DATE_UNKNOWN_VALUE_TOKENS = {"לא ידוע"}

DIAGNOSIS_DATE_FAILURE_CATEGORIES = {
    "unknown_value":
        "Source value is the literal Hebrew 'unknown' marker with no further "
        "specificity; no year can be derived.",
    "date_range":
        "Source value is a year range (e.g. 'YYYY-YYYY' or 'YYYY/YYYY'); a single "
        "year cannot be attributed without inventing one.",
    "approximate_or_uncertain":
        "Source value is Hebrew qualifier/approximation text (e.g. an uncertain or "
        "bounded year); not reliable enough to resolve to a single year.",
    "unsupported_format":
        "Source value does not match any date format the Batch 5 parser recognizes "
        "(day/month/year, month/year, or plain year).",
    "impossible_date":
        "Source value parses to a calendar-impossible or out-of-range year "
        "(outside 1900-2100).",
    "other_unresolved_nonmissing_value":
        "Source value is non-missing but does not match any recognized or currently "
        "defined failure pattern; retained unresolved pending further review.",
}


def extract_diagnosis_year(val):
    """
    Extract diagnosis_year from diagnosis_date using only approved formats.

    The source diagnosis_date value is not modified. The only approved
    two-digit-year branch is strict D/M/23 or DD/MM/23, interpreted as
    D/M/2023 after validating day and month. No general century inference
    exists for other two-digit years.
    """
    if pd.isna(val):
        return np.nan
    if hasattr(val, "year") and not isinstance(val, str):
        return int(val.year)

    s = str(val).strip()
    if re.search(r"[א-ת׳-׳×]", s):
        return np.nan
    if re.match(r"^\d{4}[-/]\d{4}$", s):
        return np.nan

    try:
        f = float(s)
        if f == int(f):
            y = int(f)
            return y if 1900 <= y <= 2100 else np.nan
    except (ValueError, TypeError):
        pass

    m = re.match(r"^(\d{1,2})/(\d{1,2})/23$", s)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        try:
            datetime(2023, month, day)
        except ValueError:
            return np.nan
        return 2023

    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        y = int(m.group(3))
        return y if 1900 <= y <= 2100 else np.nan

    m = re.match(r"^\d{1,2}/(\d{4})$", s)
    if m:
        y = int(m.group(1))
        return y if 1900 <= y <= 2100 else np.nan

    return np.nan


def categorize_diagnosis_date_failure(raw_value):
    """
    Read-only QA characterization of why a non-missing diagnosis_date value
    did not resolve to a diagnosis_year under Batch 5's
    extract_diagnosis_year rules.

    This does not parse, infer, or assign a year -- it only labels the reason
    a value stayed unresolved, using the same signals extract_diagnosis_year
    already
    acts on (Hebrew qualifier text, YYYY/YYYY or YYYY-YYYY ranges, and
    out-of-range years). Must be re-reviewed if extract_diagnosis_year's own
    rules ever change.
    """
    s = str(raw_value).strip()

    if s in _DIAGNOSIS_DATE_UNKNOWN_VALUE_TOKENS:
        return "unknown_value"

    if re.match(r"^\d{4}[-/]\d{4}$", s):
        return "date_range"

    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        year = int(m.group(3))
        if not (1900 <= year <= 2100):
            return "impossible_date"

    if re.search(r"[א-ת]", s):
        return "approximate_or_uncertain"

    if re.search(r"[0-9]", s):
        return "unsupported_format"

    return "other_unresolved_nonmissing_value"


def build_diagnosis_date_unresolved_qa(df):
    """
    Deterministic, read-only QA table of every row where diagnosis_date is
    non-missing but diagnosis_year could not be resolved. Does not modify df,
    does not assign a year, and does not add an analytical column -- purely a
    diagnostic export keyed by subject_number + delivery_id.

    Sort order is a documented stable sort by (subject_number, delivery_id)
    ascending (mergesort, so ties -- none expected given composite-key
    uniqueness -- would preserve original row order).
    """
    mask = df["diagnosis_date"].notna() & df["diagnosis_year"].isna()
    qa = df.loc[mask, ["subject_number", "delivery_id", "diagnosis_date", "diagnosis_year"]].copy()

    qa["diagnosis_date_normalized"] = qa["diagnosis_date"].map(lambda v: str(v).strip())
    qa["failure_category"] = qa["diagnosis_date"].map(categorize_diagnosis_date_failure)
    qa["failure_explanation"] = qa["failure_category"].map(DIAGNOSIS_DATE_FAILURE_CATEGORIES)
    qa["source_is_missing"] = False
    qa["source_is_nonmissing_unresolved"] = True
    qa["automatic_parsing_result"] = qa["diagnosis_year"]
    qa["review_status"] = "reviewed_remains_unresolved"
    qa["decision_status"] = "no_action_required_remains_missing"
    qa["relevant_rule_or_note"] = (
        "Batch 5 extract_diagnosis_year rule: value cannot be reliably "
        "resolved to a single year; diagnosis_year remains NaN by approved "
        "decision (see manual_decisions_log.md)."
    )

    qa = qa.sort_values(["subject_number", "delivery_id"], kind="mergesort").reset_index(drop=True)

    column_order = [
        "subject_number", "delivery_id", "diagnosis_date", "diagnosis_date_normalized",
        "failure_category", "failure_explanation", "source_is_missing",
        "source_is_nonmissing_unresolved", "automatic_parsing_result", "diagnosis_year",
        "review_status", "decision_status", "relevant_rule_or_note",
    ]
    return qa[column_order]


# ---------------------------------------------------------------------------
# nulliparity <- P canonical correction (PARTNER-FIX-03A, PRE-B3-003)
# ---------------------------------------------------------------------------

def classify_p_validity(p_raw):
    """
    Classify each value of the parity-count source column P for the
    nulliparity-from-P correction. A value is 'valid' only if non-missing,
    numeric, finite, integer-valued, and >= 0 (no maximum threshold).

    Returns (category, p_numeric): category is a string Series with values
    in {'valid', 'missing_P', 'non_numeric_P', 'non_finite_P', 'negative_P',
    'non_integer_P', 'other_invalid_P'}; p_numeric is the numeric-coerced
    value (NaN wherever not numeric).
    """
    idx = p_raw.index
    category = pd.Series("other_invalid_P", index=idx, dtype=object)

    missing_mask = p_raw.isna()
    category.loc[missing_mask] = "missing_P"

    p_numeric = pd.to_numeric(p_raw, errors="coerce")
    non_numeric_mask = (~missing_mask) & p_numeric.isna()
    category.loc[non_numeric_mask] = "non_numeric_P"

    checkable_mask = (~missing_mask) & (~non_numeric_mask)
    finite_mask = checkable_mask & np.isfinite(p_numeric)
    non_finite_mask = checkable_mask & ~finite_mask
    category.loc[non_finite_mask] = "non_finite_P"

    negative_mask = finite_mask & (p_numeric < 0)
    category.loc[negative_mask] = "negative_P"

    non_integer_mask = finite_mask & (p_numeric >= 0) & (p_numeric != np.floor(p_numeric))
    category.loc[non_integer_mask] = "non_integer_P"

    valid_mask = finite_mask & (p_numeric >= 0) & (p_numeric == np.floor(p_numeric))
    category.loc[valid_mask] = "valid"

    return category, p_numeric


def compute_nulliparity_from_P(df):
    """
    Row-level, read-only computation of the nulliparity-from-P correction.
    Does not modify df. Returns a diagnostic DataFrame aligned to df.index
    (same row order, one row per input row).

    Approved transformation: valid P==0 -> nulliparity=1; valid P>=1 ->
    nulliparity=0; invalid or missing P -> nulliparity=NaN.
    """
    idx = df.index
    p_category, p_numeric = classify_p_validity(df["P"])
    old_nulliparity = df["nulliparity"]
    valid_mask = p_category == "valid"

    expected_nulliparity = pd.Series(np.nan, index=idx, dtype="float64")
    expected_nulliparity.loc[valid_mask & (p_numeric == 0)] = 1.0
    expected_nulliparity.loc[valid_mask & (p_numeric >= 1)] = 0.0

    same_value = (
        (expected_nulliparity == old_nulliparity)
        | (expected_nulliparity.isna() & old_nulliparity.isna())
    )

    contradiction_category = pd.Series("other_unresolved", index=idx, dtype=object)
    contradiction_category.loc[valid_mask & (p_numeric == 0) & (old_nulliparity == 1)] = (
        "consistent_P0_nulliparity1"
    )
    contradiction_category.loc[valid_mask & (p_numeric >= 1) & (old_nulliparity == 0)] = (
        "consistent_P1plus_nulliparity0"
    )
    contradiction_category.loc[valid_mask & (p_numeric == 0) & (old_nulliparity == 0)] = (
        "contradiction_P0_nulliparity0"
    )
    contradiction_category.loc[valid_mask & (p_numeric >= 1) & (old_nulliparity == 1)] = (
        "contradiction_P1plus_nulliparity1"
    )
    contradiction_category.loc[valid_mask & old_nulliparity.isna()] = "P_present_nulliparity_missing"
    contradiction_category.loc[(p_category == "missing_P") & old_nulliparity.isna()] = "both_missing"
    contradiction_category.loc[(p_category == "missing_P") & old_nulliparity.notna()] = (
        "P_missing_nulliparity_present"
    )
    contradiction_category.loc[
        (~valid_mask) & (p_category != "missing_P") & old_nulliparity.notna()
    ] = "P_invalid_nulliparity_present"

    correction_status = pd.Series("already_correct", index=idx, dtype=object)
    correction_status.loc[~valid_mask] = "set_missing_due_to_invalid_P"
    correction_status.loc[valid_mask & ~same_value] = "correction_applied"

    diag = pd.DataFrame({
        "subject_number": df["subject_number"],
        "delivery_id": df["delivery_id"],
        "P": df["P"],
        "P_numeric": p_numeric,
        "p_validity_category": p_category,
        "old_nulliparity": old_nulliparity,
        "expected_nulliparity": expected_nulliparity,
        "contradiction_category": contradiction_category,
        "correction_status": correction_status,
    }, index=idx)
    diag["subject_number_missing"] = df["subject_number"].isna()
    diag["delivery_id_missing"] = df["delivery_id"].isna()
    diag["composite_key_complete"] = ~(diag["subject_number_missing"] | diag["delivery_id_missing"])
    return diag


def build_nulliparity_from_P_qa(diag):
    """
    Build the two required QA sheets from compute_nulliparity_from_P's
    diagnostic frame: 'contradictions' (rows whose nulliparity value was
    actually corrected) and 'invalid_or_missing_P' (rows where P could not
    be used, so nulliparity was set to missing). Read-only; both sheets are
    sorted deterministically by (subject_number, delivery_id).
    """
    contradictions_mask = diag["contradiction_category"].isin([
        "contradiction_P0_nulliparity0", "contradiction_P1plus_nulliparity1",
    ])
    contradictions = diag.loc[contradictions_mask].copy()
    contradictions["final_nulliparity"] = contradictions["expected_nulliparity"]
    contradictions = contradictions[[
        "subject_number", "delivery_id", "P", "P_numeric", "old_nulliparity",
        "expected_nulliparity", "final_nulliparity", "contradiction_category",
        "correction_status", "subject_number_missing", "delivery_id_missing",
        "composite_key_complete",
    ]]
    contradictions = contradictions.sort_values(
        ["subject_number", "delivery_id"], kind="mergesort"
    ).reset_index(drop=True)

    invalid_mask = diag["p_validity_category"] != "valid"
    invalid_or_missing_P = diag.loc[invalid_mask].copy()
    invalid_or_missing_P["final_nulliparity"] = invalid_or_missing_P["expected_nulliparity"]
    invalid_or_missing_P = invalid_or_missing_P[[
        "subject_number", "delivery_id", "P", "P_numeric", "p_validity_category",
        "old_nulliparity", "expected_nulliparity", "final_nulliparity",
        "correction_status", "subject_number_missing", "delivery_id_missing",
        "composite_key_complete",
    ]]
    invalid_or_missing_P = invalid_or_missing_P.sort_values(
        ["subject_number", "delivery_id"], kind="mergesort"
    ).reset_index(drop=True)

    return {"contradictions": contradictions, "invalid_or_missing_P": invalid_or_missing_P}


# ---------------------------------------------------------------------------
# Before/after summary
# ---------------------------------------------------------------------------

def summarize_before_after_counts(series_before, series_after, col_name):
    """
    Return a compact dict summarising value_counts before and after a change.
    Useful for audit entries.
    """
    def vc(s):
        return s.value_counts(dropna=False).to_dict()

    before = vc(series_before)
    after = vc(series_after)
    changed = int((series_before != series_after).sum())
    return {
        "column": col_name,
        "before": before,
        "after": after,
        "rows_changed": changed,
    }


# ---------------------------------------------------------------------------
# Audit / deviation logging
#
# Portability note: every batch function builds its file paths via
# run_preprocessing.py's resolve_path()/PROJECT_ROOT, which are intentionally
# absolute (anchored to this script's own __file__ location) so that actual
# file I/O (open/os.makedirs/to_excel) is robust regardless of the caller's
# working directory. Embedding those same absolute strings directly into
# committed Markdown content would leak a machine-specific path
# (e.g. "C:\Users\<name>\..."). _to_relative_display() strips the project-root
# prefix from any text before it is written to disk, so every *_PATH-derived
# variable can keep being passed straight into an f-string without every
# individual call site needing to remember to convert it.
# ---------------------------------------------------------------------------

_UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
# analysis/preprocessing/src/ -> up 3 levels -> project root (mirrors
# run_preprocessing.py's own PROJECT_ROOT, computed independently here so
# this module has no import-time dependency on run_preprocessing.py).
_PROJECT_ROOT_FOR_DISPLAY = os.path.abspath(os.path.join(_UTILS_DIR, "..", "..", ".."))


def _to_relative_display(text):
    """Strip the machine-specific project-root absolute prefix from any path
    embedded in Markdown content, so committed audit files stay portable
    across machines/users. No-op for text that doesn't contain the prefix."""
    root = _PROJECT_ROOT_FOR_DISPLAY
    for variant in (root.replace("\\", "/") + "/", root + os.sep, root.replace("\\", "/"), root):
        if variant in text:
            text = text.replace(variant, "")
    return text


AUDIT_MARKDOWN_DISCLOSURE_THRESHOLD = 5
_RECORD_DETAIL_SUPPRESSED_LINE = (
    "- Record-level details suppressed under the tracked-audit privacy rule. "
    "Aggregate counts and local review-file references are retained where safe."
)
_SMALL_CELL_SUPPRESSED_LINE = (
    "- Value breakdown suppressed under the small-cell rule (n<5); "
    "record-level details remain only in local review outputs when required."
)
_TABLE_DETAIL_SUPPRESSED_NOTE = (
    "Small-cell or record-level details suppressed under the tracked-audit "
    "privacy rule; local review workbook retains details where required."
)


# Narrow, explicit allowlist for the exact approved Batch 19 identifier-
# integrity aggregate-count lines (run_preprocessing.py, "## Identifier
# integrity" block; see docs/clinical_decisions, read-only review finding
# PRE-ALL-001). Each pattern is a literal, fully-anchored match of the whole
# stripped line -- exact wording, exact "= " spacing, a plain non-negative
# integer, and nothing else on the line. This is deliberately NOT a generic
# "subject_number = N" / "delivery_id = N" allowance (that would defeat the
# privacy rule for genuine record-level values); it recognizes only these
# four specific, pre-approved aggregate-count sentences by their complete
# literal text, so no other content -- prose, table rows, or a real patient
# key that merely happens to reuse the word "missing"/"duplicate" -- can
# satisfy it. Adding a new approved aggregate line requires a new literal
# pattern here, not a loosened existing one.
_APPROVED_IDENTIFIER_INTEGRITY_AGGREGATE_PATTERNS = [
    r"^- missing subject_number = \d+$",
    r"^- missing delivery_id = \d+$",
    r"^- duplicate delivery_id = \d+$",
    r"^- duplicate available subject_number \+ delivery_id pairs = \d+$",
]


def _is_approved_identifier_integrity_aggregate_line(text):
    """True only for one of the four exact, pre-approved Batch 19
    identifier-integrity aggregate-count line formats (see
    _APPROVED_IDENTIFIER_INTEGRITY_AGGREGATE_PATTERNS above). Used solely to
    exempt these specific lines from _contains_patient_key_value's
    record-level suppression -- every other patient-key/value form (prose,
    table cells, any line not matching one of these four literal templates)
    remains fail-closed and suppressed as before."""
    stripped = text.strip()
    return any(
        re.match(pattern, stripped) for pattern in _APPROVED_IDENTIFIER_INTEGRITY_AGGREGATE_PATTERNS
    )


def _contains_patient_key_value(text):
    """Return True when text contains an actual subject/delivery identifier.

    Exempts the four exact, pre-approved Batch 19 identifier-integrity
    aggregate-count lines (see _is_approved_identifier_integrity_aggregate_line)
    -- these report a safe row COUNT (e.g. "missing subject_number = 8"), not
    a record-level identifier VALUE, but share the same "field = digits"
    surface syntax the patterns below must otherwise catch. Every other line
    shape, including a real identifier value embedded in prose or a table
    cell, is unaffected and still flagged.
    """
    if _is_approved_identifier_integrity_aggregate_line(text):
        return False
    patterns = [
        r"\bsubject_number\s*[=/]\s*(?:nan|\d+(?:\.\d+)?)\b",
        r"\bsubject_number\s+\d+(?:\.\d+)?(?:'s)?\b",
        r"\bdelivery_id\s*[=/]\s*(?:nan|\d+(?:\.\d+)?)\b",
        r"\bdelivery_id\s+\d+(?:\.\d+)?\b",
        r"\bPatient\s+\d+\b",
        r"\bsubject\s+\d+(?:'s)?\b",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _contains_small_cell_value_breakdown(text, threshold=AUDIT_MARKDOWN_DISCLOSURE_THRESHOLD):
    """Detect compact value-count dictionaries that expose n<threshold."""
    if "{" not in text or "}" not in text:
        return False
    pairs = re.findall(r"(?::|,)\s*(-?\d+)\s*(?:[,}])", text)
    return any(0 <= int(value) < threshold for value in pairs)


def _contains_small_cell_prose_detail(text, threshold=AUDIT_MARKDOWN_DISCLOSURE_THRESHOLD):
    """Detect prose that exposes small nonzero counts in tracked audit Markdown."""
    if threshold <= 1:
        return False

    small = rf"[1-{threshold - 1}]"
    small_count_context = (
        r"(?:rows?|records?|cases?|corrections?|contradictions?|findings?|"
        r"values?|missing|free-text|text|NaN|unresolved|corrected|recoded|filled|"
        r"review|QA|with)"
    )
    if re.search(rf"\bRows:\*\*\s+{small}\b", text, flags=re.IGNORECASE):
        return True
    if re.search(
        rf"\b{small_count_context}\b[^.\n|;]*:\s*{small}\b",
        text,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(
        rf"\b(?:filled|corrected|recoded|set)\s+{small}\b",
        text,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(
        rf"\b{small}\s+(?:free-text|text|NaN|missing|unresolved)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(rf":\s*{small}\s*(?:\||$)", text):
        return True

    direct_count = re.search(
        rf"\b{small}\s+"
        r"(?:rows?|records?|cases?|corrections?|contradictions?|findings?|values?)\b",
        text,
        flags=re.IGNORECASE,
    )
    if direct_count:
        return True

    has_review_context = re.search(
        r"\b(rows?|records?|review|QA|manual|unresolved|corrected|"
        r"contradictions?|values?|findings?)\b",
        text,
        flags=re.IGNORECASE,
    )
    coded_small_count = re.search(
        rf"\b{small}\s+[A-Za-z][A-Za-z0-9_/-]*(?:=|,|\)|\s)",
        text,
    )
    return bool(has_review_context and coded_small_count)


def _contains_record_level_value_change(text):
    """Detect line-level clinical values tied to an individual record."""
    patterns = [
        r"\braw\s*=\s*[^;,)]+",
        r"\bderived\s*=\s*[^;,)]+",
        r"\bbefore\s*=\s*[^;,)]+",
        r"\bafter\s*=\s*[^;,)]+",
        r"\b\d+(?:\.\d+)?\s*->\s*(?:nan|\d+(?:\.\d+)?)\b",
        r"\bNaN\s*->\s*\d+(?:\.\d+)?\b",
        r"\bdiagnosis_date\s*=",
        r"\bsupporting\s*:",
        r"\bCorrections\s*:",
        r"\bBefore\s*->\s*after\b",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _contains_quoted_clinical_text(text):
    """Detect likely raw patient free text embedded in a Markdown line."""
    if re.search(r"[\u0590-\u05FF]", text) and re.search(r"['\"`].+['\"`]", text):
        return True
    if re.search(
        r"\b(raw free-text|free-text value|original text|raw value)\b",
        text,
        flags=re.IGNORECASE,
    ):
        if re.search(r"['\"`][^'\"`]{8,}['\"`]", text):
            return True
    return False


def _sanitize_markdown_table_row(line, note=_TABLE_DETAIL_SUPPRESSED_NOTE):
    """Suppress sensitive cells while preserving the review-inventory schema."""
    cells = line.split("|")
    if len(cells) < 4:
        return _RECORD_DETAIL_SUPPRESSED_LINE

    for idx in range(1, len(cells) - 1):
        if re.fullmatch(r"\s*[1-4]\s*", cells[idx]):
            cells[idx] = " n<5 "

    cells[-2] = f" {note} "
    return "|".join(cells)


def privacy_safe_count(n, noun="rows", threshold=AUDIT_MARKDOWN_DISCLOSURE_THRESHOLD):
    """Return a tracked-Markdown-safe count string."""
    try:
        n_int = int(n)
    except (TypeError, ValueError):
        return f"{noun}: count unavailable"
    if 0 < n_int < threshold:
        return f"{noun}: n<5 (suppressed)"
    return f"{noun}: {n_int}"


def sanitize_tracked_audit_markdown(content):
    """Render preprocessing audit Markdown safe for version control.

    This is a defense-in-depth renderer for tracked Markdown only. It does not
    alter local review workbooks or dataframe values; it only prevents patient
    keys, row-level clinical values, raw free text, and small-cell breakdowns
    from being copied into committed Markdown.
    """
    sanitized_lines = []
    suppress_continuation = False

    for raw_line in str(content).splitlines():
        line = raw_line
        stripped = line.strip()

        if suppress_continuation and (line.startswith(" ") or line.startswith("\t")):
            continue
        suppress_continuation = False

        if not stripped:
            sanitized_lines.append(line)
            continue

        patient_key = _contains_patient_key_value(line)
        row_values = _contains_record_level_value_change(line)
        quoted_text = _contains_quoted_clinical_text(line)
        small_breakdown = _contains_small_cell_value_breakdown(line)
        small_prose = _contains_small_cell_prose_detail(line)

        if line.lstrip().startswith("|") and (
            patient_key or row_values or quoted_text or small_breakdown or small_prose
        ):
            sanitized_lines.append(_sanitize_markdown_table_row(line))
            continue

        if line.lstrip().startswith("|") and patient_key:
            line = re.sub(
                r"subject_number\s*[=/ ]\s*(?:nan|\d+(?:\.\d+)?)(?:'s)?\s*/?\s*"
                r"(?:delivery_id\s*[=/ ]\s*(?:nan|\d+(?:\.\d+)?))?",
                "record-level key suppressed",
                line,
                flags=re.IGNORECASE,
            )
            line = re.sub(
                r"delivery_id\s*[=/ ]\s*(?:nan|\d+(?:\.\d+)?)",
                "record-level key suppressed",
                line,
                flags=re.IGNORECASE,
            )
            line = re.sub(
                r"subject\s+\d+(?:\.\d+)?(?:'s)?",
                "record-level subject suppressed",
                line,
                flags=re.IGNORECASE,
            )
            line = line.replace("record-level key suppressed's", "record-level key suppressed")
            line = line.replace("record-level subject suppressed's", "record-level subject suppressed")
            sanitized_lines.append(line)
            continue

        if patient_key or row_values or quoted_text:
            sanitized_lines.append(_RECORD_DETAIL_SUPPRESSED_LINE)
            if raw_line.startswith("-") or raw_line.startswith("  -"):
                suppress_continuation = True
            continue

        if small_breakdown:
            sanitized_lines.append(_SMALL_CELL_SUPPRESSED_LINE)
            continue

        if small_prose:
            sanitized_lines.append(_SMALL_CELL_SUPPRESSED_LINE)
            continue

        line = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "<date suppressed>", line)
        sanitized_lines.append(line)

    return "\n".join(sanitized_lines) + ("\n" if str(content).endswith("\n") else "")


def sha256_of_file(path, chunk_size=1 << 20):
    """Return the hex SHA-256 digest of a file's bytes, or None if unreadable."""
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def get_git_commit_hash(project_root):
    """Return the current HEAD commit hash, or a clear 'unavailable' string.

    Never raises: audit-log generation must not fail just because git is
    missing or the tree isn't a git repository (e.g. a packaged export)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return "unavailable (git command failed — not a git repository or no commits yet)"
    except (OSError, subprocess.SubprocessError):
        return "unavailable (git executable not found)"


def format_run_header(input_dataset_relpath, input_dataset_sha256):
    """One identity block, written once per run, identifying exactly which
    execution produced the audit content that follows it."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit = get_git_commit_hash(_PROJECT_ROOT_FOR_DISPLAY)
    hash_display = input_dataset_sha256 if input_dataset_sha256 else "unavailable (input file unreadable)"
    return (
        "## Run identity\n"
        f"- Execution timestamp: {ts}\n"
        f"- Git commit (HEAD): {commit}\n"
        f"- Input dataset: {input_dataset_relpath}\n"
        f"- Input dataset SHA-256: {hash_display}\n\n"
        "This section is rewritten at the start of every run. It always "
        "describes the single most recent execution only — see the batch "
        "entries below for that same execution's results.\n\n"
    )


def write_batch_summary(path, content):
    """Overwrite one batch's standalone summary Markdown file with `content`.

    Unlike log_audit_event/log_deviation_event (which append within a
    shared, run-scoped file), each batch has its own summary file, so this
    always truncates and rewrites rather than appending."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(sanitize_tracked_audit_markdown(_to_relative_display(content)))


def log_audit_event(path, batch_name, content):
    """Append a batch-level audit entry (within the current run's section —
    see init_audit_log, which resets this file's header at the start of
    every run so it always represents exactly one execution)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "a", encoding="utf-8") as f:
        rendered = _to_relative_display(f"\n## {batch_name} — {ts}\n\n{content}\n")
        f.write(sanitize_tracked_audit_markdown(rendered))


# Alias used in existing batch functions
append_audit_entry = log_audit_event


def log_deviation_event(path, variable, raw_variable, documented, action,
                        reason, requires_approval, batch, affected_count=None):
    """Append one entry to the preprocessing_deviations.md log (within the
    current run's section — see init_deviation_log)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    approval_str = "YES — requires approval before execution" if requires_approval else "No"
    entry = (
        f"\n---\n"
        f"**Variable:** {variable}\n"
        f"**Original variable name:** {raw_variable}\n"
        f"**Documented instruction:** {documented}\n"
        f"**Action taken:** {action}\n"
        f"**Reason:** {reason}\n"
        f"**Requires approval:** {approval_str}\n"
        f"**Batch:** {batch}\n"
        f"**Timestamp:** {ts}\n"
    )
    if affected_count is not None:
        entry += f"**Affected rows:** {affected_count}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(sanitize_tracked_audit_markdown(_to_relative_display(entry)))


# Alias used in existing batch functions
append_deviation = log_deviation_event


def init_deviation_log(path, run_header=""):
    """(Re)write this run's header. Always truncates and rewrites the file —
    an audit log must represent exactly one identified execution, never a
    silent accumulation of unrelated prior runs' full history underneath it."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Preprocessing Deviations Log\n\n")
        f.write("Tracks every deviation from the documented preprocessing plan, "
                 "for the single run identified below.\n\n")
        f.write(_to_relative_display(run_header))


def init_audit_log(path, run_header=""):
    """(Re)write this run's header. Always truncates and rewrites the file —
    see init_deviation_log for why this must not be append-only across runs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Preprocessing Audit Log\n\n")
        f.write("Tracks batch-level decisions and summaries for the single "
                 "run identified below.\n\n")
        f.write(_to_relative_display(run_header))

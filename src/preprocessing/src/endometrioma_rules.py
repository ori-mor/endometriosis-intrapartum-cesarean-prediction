"""
Deterministic parsing rules for the endometrioma location (place) field.

These functions extract valid endometrioma place codes (1=right, 2=left,
3=bilateral) from a raw source cell, distinguish documented "not specified"
missing-value text from genuinely uncodeable free text, and derive
laterality (unilateral vs bilateral) from the cleaned place value.
"""

import re

import numpy as np
import pandas as pd


def normalize_endometrioma_place_missing_text(value):
    """Return normalized text used only to detect documented missing location phrases."""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    text = re.sub(r"^[\s,.;:()\\[\\]{}\"'\u05f3\u05f4]+|[\s,.;:()\\[\\]{}\"'\u05f3\u05f4]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def is_documented_missing_endometrioma_place(value):
    """Exact documented missing-value phrase for endometrioma location, with superficial formatting tolerated."""
    return normalize_endometrioma_place_missing_text(value) == "לא צוין"


def extract_endometrioma_place_codes(value):
    """Extract valid endometrioma place codes; documented missing text returns no codes."""
    valid_place_codes = {1, 2, 3}
    non_informative_place = {"0", "0.0"}
    if pd.isna(value):
        return set()
    text = str(value).strip()
    if not text or text in non_informative_place or is_documented_missing_endometrioma_place(text):
        return set()
    codes = set()
    for match in re.finditer(r"\d+", text):
        code = int(match.group())
        if code in valid_place_codes:
            codes.add(code)
    return codes


def clean_endometrioma_place_value(value):
    """Return 1=right, 2=left, 3=bilateral, or NaN when location is missing/unknown."""
    codes = extract_endometrioma_place_codes(value)
    if not codes:
        return np.nan
    if 3 in codes or (1 in codes and 2 in codes):
        return 3
    if 1 in codes:
        return 1
    if 2 in codes:
        return 2
    return np.nan


def derive_endometrioma_laterality(place_clean):
    """Return 1=unilateral, 2=bilateral, or NaN when place cannot be derived."""
    if pd.isna(place_clean):
        return np.nan
    if place_clean in (1, 2):
        return 1
    if place_clean == 3:
        return 2
    return np.nan


def has_uncodeable_endometrioma_place_text(value):
    """Detect meaningful non-missing location text that lacks a valid place code."""
    if pd.isna(value):
        return False
    text = str(value).strip()
    if not text or text in {"0", "0.0"} or is_documented_missing_endometrioma_place(text):
        return False
    return bool(re.search(r"[A-Za-z\u0590-\u05FF]", text)) and not extract_endometrioma_place_codes(value)


# ---------------------------------------------------------------------------
# endometrioma_size -> endometrioma_size_clean (PARTNER-FIX-04, F-1)
#
# Attribution-aware parser: never selects a value solely because it is the
# largest number in a free-text cell. A prior version extracted every
# number and took the unconditional maximum, which misattributed a
# measurements belonging to a different pathology/structure from an
# endometrioma measurement. This version distinguishes
# measurements explicitly attributable to an endometrioma from measurements
# attributable to a different structure or pathology (dermoid, fibroid/
# myoma, endometrial lining/thickness, follicle) before selecting the
# longest dimension.
# ---------------------------------------------------------------------------

ENDOMETRIOMA_SIZE_PARSER_VERSION = "endometrioma_size_v2_attribution_aware_2026-08-02"

_UNIT_ALPHA_BOUNDARY = r"A-Za-z\u05D0-\u05EA"
_UNIT_LEFT_BOUNDARY = r"(?<![" + _UNIT_ALPHA_BOUNDARY + r"])"
_UNIT_RIGHT_BOUNDARY = r"(?![" + _UNIT_ALPHA_BOUNDARY + r"])"
_UNIT_QUOTE_CHARS = r"[\"'\u05F3\u05F4\u2018\u2019\u201C\u201D\u2032\u2033]"
_CM_UNIT_PATTERN = (
    _UNIT_LEFT_BOUNDARY
    + r"(?:\u05E1\s*(?:" + _UNIT_QUOTE_CHARS + r"{0,2})\s*\u05DE|c\s*\.?\s*m|centimeters?)"
    + _UNIT_RIGHT_BOUNDARY
)
_MM_UNIT_PATTERN = (
    _UNIT_LEFT_BOUNDARY
    + r"(?:\u05DE\s*(?:" + _UNIT_QUOTE_CHARS + r"{0,2})\s*\u05DE|m\s*\.?\s*m|millimeters?)"
    + _UNIT_RIGHT_BOUNDARY
)
_CM_UNIT_RE = re.compile(_CM_UNIT_PATTERN, re.IGNORECASE)
_MM_UNIT_RE = re.compile(_MM_UNIT_PATTERN, re.IGNORECASE)
_LESS_THAN_1CM_RE = re.compile(
    r"(?:<|less\s+than|smaller\s+than|\u05E7\u05D8\u05DF|\u05E7\u05D8\u05E0\u05D4|"
    r"\u05E7\u05D8\u05E0\u05D9\u05DD|\u05E4\u05D7\u05D5\u05EA)\s*(?:\u05DE|m)?\s*1\s*"
    r"(?:" + _CM_UNIT_PATTERN + r")",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_NON_INFORMATIVE_SIZE = frozenset({
    "\u05DC\u05D0 \u05E6\u05D5\u05D9\u05DF", "\u05DC\u05D0 \u05E6\u05D5\u05D9\u05D9\u05DF", "\u05DC\u05D0 \u05E6\u05D5\u05D9\u05DF \u05D2\u05D5\u05D3\u05DC", "\u05DC\u05D0 \u05E6\u05D5\u05D9\u05D9\u05DF \u05D2\u05D5\u05D3\u05DC",
})
_HAS_LETTER_RE = re.compile(r"[A-Za-z\u05D0-\u05EA]")
_DIM_RE = re.compile(r"\d+(?:\.\d+)?[\s]*[,xX*\u2013-][\s]*\d+(?:\.\d+)?")
_ENDOMETRIOMA_KEYWORD_RE = re.compile(r"\u05D0\u05E0\u05D3\u05D5\u05DE\u05D8\u05E8\u05D9\u05D5\u05DE|endometrioma", re.IGNORECASE)
_EXCLUSION_KEYWORD_RE = re.compile(
    r"\u05D3\u05E8\u05DE\u05D5\u05D0\u05D9\u05D3|dermoid"
    r"|\u05E9\u05E8\u05D9\u05E8\u05E0\u05D9|\u05DE\u05D9\u05D5\u05DE\u05D4|fibroid|myoma"
    r"|\u05E8\u05D9\u05E8\u05D9\u05EA|endometrial\s*(?:thick|lining)"
    r"|\u05D6\u05E7\u05D9\u05E7|follicle",
    re.IGNORECASE,
)
_DATE_PATTERN_RE = re.compile(r"\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}")
_STRUCTURE_MARKER_RE = re.compile(r"\u05E9\u05D7\u05DC\u05D4")


def _normalize_unit_text(text):
    import unicodedata
    return unicodedata.normalize("NFKC", str(text)).lower()


def _has_cm_unit(text):
    return bool(_CM_UNIT_RE.search(_normalize_unit_text(text)))


def _has_mm_unit(text):
    return bool(_MM_UNIT_RE.search(_normalize_unit_text(text)))


def _has_clear_size_signal(s):
    """True if s has an explicit mm/cm unit, a dimension pattern, or 2+ numeric values."""
    return bool(
        _has_mm_unit(s) or _has_cm_unit(s) or _DIM_RE.search(s) or len(_NUMBER_RE.findall(s)) >= 2
    )


def _split_endometrioma_size_clauses(s):
    """Split into clauses on commas always, and on periods only when NOT a
    decimal point (a naive split would shatter "23.1" into "23"/"1"), then
    further split before each repeated "\u05E9\u05D7\u05DC\u05D4" (ovary) mention -- the
    recurring structural marker that introduces a distinct anatomical
    side/mass in this dataset, often with no separating punctuation."""
    parts = [p.strip() for p in re.split(r"(?<!\d)\.(?!\d)|,", s) if p.strip()]
    out = []
    for p in parts:
        sub = re.split(r"(?=\u05E9\u05D7\u05DC\u05D4)", p)
        out.extend(x.strip() for x in sub if x.strip())
    return out


def _endometrioma_size_clause_numbers_mm(clause):
    date_spans = [m.span() for m in _DATE_PATTERN_RE.finditer(clause)]
    nums = []
    for m in _NUMBER_RE.finditer(clause):
        if any(a <= m.start() < b for a, b in date_spans):
            continue  # exclude numbers that are part of a date, not a size
        num = float(m.group())
        after = clause[m.end():m.end() + 12]
        if _has_cm_unit(after):
            nums.append(num * 10)
        elif _has_mm_unit(after):
            nums.append(num)
        else:
            nums.append(num)  # no unit -> assume mm per documentation
    return nums


def parse_endometrioma_size_mm_with_evidence(val):
    """Attribution-aware endometrioma size parser. Returns a dict with full
    audit evidence (raw_value, candidate/excluded measurements and
    contexts, selected measurement, decision_type, decision_reason).

    Rule: never select a value solely because it is the largest number in
    the cell. A "simple" cell (no competing structure/pathology named) is
    parsed with the original max-of-all-numbers rule -- this covers the
    large majority of rows and must not regress. A "complex" cell (an
    explicit alternate-pathology keyword anywhere, or 2+ distinct "\u05E9\u05D7\u05DC\u05D4"
    mentions, e.g. separate right/left ovary measurements) is resolved
    per clause:
      1. Any clause naming a different pathology (dermoid, fibroid/myoma,
         endometrial lining/thickness, follicle) is excluded outright.
      2. If exactly one non-excluded clause remains, it is used by
         elimination.
      3. If 2+ non-excluded clauses remain, only clauses explicitly naming
         an endometrioma count.
      4. If nothing survives step 2/3, the value is NaN.
    """
    ev = {
        "raw_value": val, "candidate_measurements": "", "candidate_contexts": "",
        "excluded_measurements": "", "selected_measurement": None,
        "selected_unit": None, "processed_value_mm": np.nan,
        "decision_type": None, "decision_reason": None,
    }
    if pd.isna(val):
        ev["decision_type"] = "missing"
        ev["decision_reason"] = "source value is missing"
        return ev
    try:
        if float(str(val).strip()) == 0.0:
            ev["decision_type"] = "zero_treated_as_missing"
            ev["decision_reason"] = "0 is a placeholder for not-recorded, not a true zero size"
            return ev
    except (ValueError, TypeError):
        pass
    s = str(val).strip()
    if not s:
        ev["decision_type"] = "missing"
        ev["decision_reason"] = "empty string"
        return ev
    if s.lower() in _NON_INFORMATIVE_SIZE:
        ev["decision_type"] = "non_informative_text"
        ev["decision_reason"] = "known non-informative placeholder text"
        return ev
    if _LESS_THAN_1CM_RE.search(s):
        ev.update(selected_measurement="<1cm", selected_unit="cm", processed_value_mm=10.0,
                  decision_type="less_than_1cm_rule",
                  decision_reason="approved 'less than 1cm' -> 10mm rule")
        return ev
    if _HAS_LETTER_RE.search(s) and not _has_clear_size_signal(s):
        ev["decision_type"] = "vague_text_no_size_signal"
        ev["decision_reason"] = "letters+digits present but no mm/cm unit or dimension pattern"
        return ev

    # A cell is "complex" only when it shows a genuine signal of competing
    # structures/pathologies: an explicit alternate-pathology keyword, or
    # 2+ distinct "ovary" mentions. A plain comma/dimension-separated list
    # of numbers with neither signal (e.g. "44mm, 45mm", "23.1*16.2*21.7mm")
    # is the ordinary multiple-dimensions-of-one-lesion case.
    is_complex = (
        bool(_EXCLUSION_KEYWORD_RE.search(s))
        or len(_STRUCTURE_MARKER_RE.findall(s)) >= 2
    )

    if not is_complex:
        nums_mm = _endometrioma_size_clause_numbers_mm(s)
        if not nums_mm:
            ev["decision_type"] = "no_parseable_number"
            ev["decision_reason"] = "no numeric measurement found"
            return ev
        val_mm = max(nums_mm)
        ev.update(
            candidate_measurements="; ".join(str(n) for n in nums_mm),
            candidate_contexts=s, selected_measurement=val_mm, selected_unit="mm",
            processed_value_mm=val_mm, decision_type="simple_single_context",
            decision_reason="single measurement context; no competing structure or pathology mentioned",
        )
        return ev

    # Complex/mixed cell: per-clause attribution.
    clauses = _split_endometrioma_size_clauses(s)
    clauses_with_numbers = [c for c in clauses if _NUMBER_RE.search(c)]
    surviving, excluded = [], []
    for clause in clauses_with_numbers:
        nums_mm = _endometrioma_size_clause_numbers_mm(clause)
        if not nums_mm:
            continue
        if _EXCLUSION_KEYWORD_RE.search(clause):
            excluded.extend((n, clause) for n in nums_mm)
            continue
        is_positive = bool(_ENDOMETRIOMA_KEYWORD_RE.search(clause))
        surviving.extend((n, clause, is_positive) for n in nums_mm)

    ev["candidate_measurements"] = "; ".join(str(n) for n, _c, _p in surviving)
    ev["candidate_contexts"] = " | ".join(sorted({c for _n, c, _p in surviving}))
    ev["excluded_measurements"] = "; ".join(f"{n} ({c})" for n, c in excluded)

    if not surviving:
        ev["decision_type"] = "all_measurements_excluded_or_unresolved"
        ev["decision_reason"] = "every measurement in this cell was excluded as a different pathology/structure"
        return ev

    distinct_clauses = {c for _n, c, _p in surviving}
    if len(distinct_clauses) == 1:
        pool = surviving
        decision_type = "resolved_by_elimination"
        decision_reason = "only one non-excluded measurement context remained after removing other-pathology clauses"
    else:
        pool = [(n, c, p) for n, c, p in surviving if p]
        decision_type = "resolved_by_explicit_attribution"
        decision_reason = "multiple candidate structures present; only explicitly-labeled endometrioma measurement(s) used"
        if not pool:
            ev["decision_type"] = "ambiguous_multiple_unattributed_structures"
            ev["decision_reason"] = (
                "multiple distinct measurement contexts present, none explicitly labeled as "
                "endometrioma -- cannot attribute confidently"
            )
            return ev

    val_mm = max(n for n, _c, _p in pool)
    ev.update(selected_measurement=val_mm, selected_unit="mm", processed_value_mm=val_mm,
              decision_type=decision_type, decision_reason=decision_reason)
    return ev

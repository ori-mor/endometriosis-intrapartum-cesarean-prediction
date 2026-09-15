"""
Deterministic parsing and classification rules for adenomyosis sonographic
free-text and numeric-code fields.

These functions implement explicit, auditable literal-text matching for the
adenomyosis sonographic-features source variable: they detect specific
predefined sonographic findings (e.g. globular uterus, myometrial cysts,
fan-shaped shadowing) in free text, and separately parse numeric-only
multi-code cells. Ambiguous or unmatched descriptions are left uncoded for
clinical review instead of being forced into an approximate category.

Codes 1-10 represent specific sonographic features and are diagnostic enough
to support correcting the binary `adenomyosis` variable from 0 to 1. Code 11
alone is not diagnostic on its own (see adenomyosis_has_diagnostic_code).

Negation handling: a finding is only coded when it is positively asserted.
_feature_phrase_is_negated() and _longest_nonoverlapping_matches() together
detect a negation word (e.g. "no", "without", "ללא", "אין", "לא") placed
directly before a matched finding, or separated from it by a single short
descriptive word, and ensure that when a finding's pattern list has both a
specific phrase and a shorter word contained within it, negation is judged
once on the longest/most specific match rather than being overridden by the
shorter overlapping pattern.
"""

import re

import numpy as np
import pandas as pd


def normalize_adenomyosis_feature_text(value):
    """Normalize text for rule matching without modifying the source value."""
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    replacements = {
        "\u05f3": "'",
        "\u05f4": '"',
        "`": "'",
        "´": "'",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "-": " ",
        "־": " ",
        "–": " ",
        "—": " ",
        "/": " ",
        "\\": " ",
        ",": " ",
        ".": " ",
        ";": " ",
        ":": " ",
        "(": " ",
        ")": " ",
        "[": " ",
        "]": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# Negation trigger words, checked immediately before a matched finding.
# \b anchors the right edge of the trigger word so it cannot match as a prefix
# of an unrelated longer word (e.g. English "no" inside "normal", Hebrew "אין"
# inside "אינה"). The optional (?:\s+\S{0,12})? group allows at most one short
# intervening word between the trigger and the finding (e.g. "no clear
# globular uterus"), and the direct-adjacency case ("no globular uterus", with
# no intervening word at all) is matched by simply skipping that group.
_NEGATION_TRIGGER_WORDS = ("ללא", "אין", "לא", "not", "no", "without")
_NEGATION_PATTERNS = tuple(
    rf"(?:^|\s){re.escape(word)}\b(?:\s+\S{{0,12}})?\s*$"
    for word in _NEGATION_TRIGGER_WORDS
)


def _feature_phrase_is_negated(normalized_text, start_index):
    """Return True only when a direct negation appears immediately before a matched feature.

    Handles both the negation word placed directly before the finding
    ("no globular uterus") and one short intervening word
    ("no clear globular uterus").
    """
    before = normalized_text[max(0, start_index - 35):start_index].strip()
    return any(re.search(pattern, before) for pattern in _NEGATION_PATTERNS)


def _longest_nonoverlapping_matches(normalized_text, patterns):
    """Return match spans for `patterns`, discarding any span fully contained in a longer one.

    The pattern lists for a single finding intentionally include both a
    specific multi-word phrase and a shorter word contained within it (e.g.
    "רחם גלובולרי" and bare "גלובולרי"). Evaluating negation independently for
    each of those overlapping matches lets the shorter, less specific match
    "win" via OR-logic even when the longer, more specific phrase was
    correctly detected as negated. Collapsing fully-contained shorter spans
    down to their longest enclosing match first means negation is judged once
    per real-world occurrence, using the most complete surrounding context.
    """
    spans = [
        (match.start(), match.end())
        for pattern in patterns
        for match in re.finditer(pattern, normalized_text)
    ]
    spans.sort(key=lambda span: (span[0], span[0] - span[1]))
    kept = []
    for start, end in spans:
        if any(k_start <= start and end <= k_end for k_start, k_end in kept):
            continue
        kept.append((start, end))
    return kept


def _has_positive_pattern(normalized_text, patterns):
    """Return True if any non-negated match of `patterns` exists in `normalized_text`.

    Deduplicates overlapping matches first (via
    _longest_nonoverlapping_matches) so a short pattern contained inside a
    longer, already-negated phrase cannot resurrect a positive result.
    Read-only: does not modify the input text."""
    for start, _end in _longest_nonoverlapping_matches(normalized_text, patterns):
        if not _feature_phrase_is_negated(normalized_text, start):
            return True
    return False


def classify_adenomyosis_free_text(value):
    """
    Return deterministic adenomyosis feature codes from explicit literal text.

    The original source text is not modified. Ambiguous descriptions stay uncoded
    for clinician review instead of being forced into an "other" category.
    """
    text = normalize_adenomyosis_feature_text(value)
    if not text:
        return [], []

    assignments = []
    if _has_positive_pattern(
        text,
        (
            r"\bglobular uterus\b",
            r"\bglobular\b",
            r"רחם גלובולרי",
            r"מבנה רחם גלובולרי",
            r"מבנה מעט גלובולרי",
            r"גלובולרי",
        ),
    ):
        assignments.append((1, "explicit_globular_uterus"))

    if _has_positive_pattern(
        text,
        (
            r"\bmyometrial cysts?\b",
            r"ציסטה מיומטריאלית",
            r"ציסטות מיומטריאליות",
        ),
    ):
        assignments.append((5, "explicit_myometrial_cysts"))

    if _has_positive_pattern(
        text,
        (
            r"\bfan shaped shadowing\b",
            r"\bfan shaped shadows\b",
            r"הצללה בצורת מניפה",
            r"הצללות בצורת מניפה",
        ),
    ):
        assignments.append((9, "explicit_fan_shaped_shadowing"))

    codes = sorted({code for code, _ in assignments})
    labels = [label for _, label in assignments]
    return codes, labels


def classify_adenomyosis_features_value(value, normalize_multi_code_string_func):
    """
    Classify one adenomyosis sonographic-features cell.

    Numeric-only code fields may contain multiple codes and are returned sorted.
    Free text is coded only by explicit, auditable literal rules.
    """
    valid_codes = set(range(1, 12))
    if pd.isna(value):
        return [], "nan_or_empty", []
    raw = str(value).strip()
    if raw in ("", "0", "0.0"):
        return [], "nan_or_empty", []

    normalized = normalize_adenomyosis_feature_text(raw)
    has_letters = bool(re.search(r"[A-Za-z\u0590-\u05FF]", normalized))
    if has_letters:
        text_codes, rule_labels = classify_adenomyosis_free_text(raw)
        if text_codes:
            return text_codes, "explicit_literal_text", rule_labels
        return [], "free_text_unmatched", []

    codes = normalize_multi_code_string_func(raw, valid_codes)
    return codes, "numeric_codes", []


def adenomyosis_codes_to_clean_value(code_list):
    """Encode clean adenomyosis feature codes as comma-separated sorted codes."""
    return ",".join(str(code) for code in sorted(code_list)) if code_list else np.nan


def adenomyosis_has_diagnostic_code(code_list):
    """Codes 1-10 are diagnostic enough to correct adenomyosis from 0 to 1; code 11 alone is not."""
    return isinstance(code_list, list) and any(1 <= code <= 10 for code in code_list)

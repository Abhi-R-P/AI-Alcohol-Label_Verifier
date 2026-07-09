"""Pure scoring helpers for the extraction eval — no I/O, no network.

Compares an extracted field value against ground truth. Text fields match when
they're equal after light normalization (case/whitespace/punctuation) or highly
similar; ABV matches within tolerance; None means "absent" and matches only None.
"""
from __future__ import annotations

import difflib
import re
from typing import Optional

# Fields scored for extraction accuracy.
SCORED_FIELDS = [
    "brand_name",
    "class_type",
    "abv",
    "net_contents",
    "bottler_name",
    "bottler_address",
    "country_of_origin",
    "government_warning_text",
]

_TEXT_SIMILARITY = 0.90
_ABV_TOLERANCE = 0.3


def _norm(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _is_blank(v: object) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def match_text(extracted: Optional[str], expected: Optional[str]) -> bool:
    exp_blank, ext_blank = _is_blank(expected), _is_blank(extracted)
    if exp_blank:
        return ext_blank  # expected absent -> correct only if extracted absent
    if ext_blank:
        return False
    ne, nx = _norm(expected), _norm(extracted)
    if ne == nx:
        return True
    return difflib.SequenceMatcher(None, ne, nx).ratio() >= _TEXT_SIMILARITY


def match_abv(extracted: Optional[float], expected: Optional[float]) -> bool:
    if expected is None:
        return extracted is None
    if extracted is None or isinstance(extracted, bool):
        return False
    try:
        return abs(float(extracted) - float(expected)) <= _ABV_TOLERANCE
    except (TypeError, ValueError):
        return False


def match_field(field: str, extracted, expected) -> bool:
    if field == "abv":
        return match_abv(extracted, expected)
    return match_text(extracted, expected)


def score_record(extracted: dict, expected: dict) -> dict[str, bool]:
    """Per-field correctness for one label."""
    return {
        f: match_field(f, extracted.get(f), expected.get(f)) for f in SCORED_FIELDS
    }

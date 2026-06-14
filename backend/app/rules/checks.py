"""Deterministic compliance rules.

Each rule is a pure function of (extraction, ocr_confidence, profile) and returns
zero or one Finding. Keeping them pure and side-effect-free makes them trivially
unit-testable — see backend/tests/test_rules.py.
"""
from __future__ import annotations

from typing import Callable, Optional

from app.config import get_settings
from app.schemas import Finding, LabelExtraction, Profile

# (code, severity, human description) — also surfaced via GET /rules.
RULE_CATALOG: list[tuple[str, str, str]] = [
    ("MISSING_GOV_WARNING", "error", "Government health warning text not detected."),
    ("MISSING_ABV", "error", "Alcohol by volume (ABV) not found on the label."),
    ("ABV_OUT_OF_RANGE", "warn", "ABV is outside the plausible 0-100% range."),
    ("ABV_MISMATCH", "warn", "ABV does not match the expected profile value."),
    ("MISSING_NET_CONTENTS", "error", "Net contents / volume statement not found."),
    ("MISSING_BRAND", "warn", "Brand name not detected."),
    ("BRAND_MISMATCH", "warn", "Brand name does not match the expected profile value."),
    ("LOW_OCR_CONFIDENCE", "warn", "OCR confidence is low; consider re-photographing."),
]

# A rule takes the inputs and returns a Finding or None.
Rule = Callable[[LabelExtraction, float, Optional[Profile]], Optional[Finding]]


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def check_gov_warning(ext: LabelExtraction, ocr_conf: float, profile: Optional[Profile]):
    if not ext.government_warning_present:
        return Finding(
            code="MISSING_GOV_WARNING",
            severity="error",
            message="Government health warning text not detected on the label.",
        )
    return None


def check_abv(ext: LabelExtraction, ocr_conf: float, profile: Optional[Profile]):
    if ext.abv_percent is None:
        return Finding(
            code="MISSING_ABV",
            severity="error",
            message="Alcohol by volume (ABV) not found on the label.",
        )
    if not (0 < ext.abv_percent < 100):
        return Finding(
            code="ABV_OUT_OF_RANGE",
            severity="warn",
            message=f"ABV {ext.abv_percent}% is outside the plausible 0-100% range.",
        )
    return None


def check_abv_mismatch(ext: LabelExtraction, ocr_conf: float, profile: Optional[Profile]):
    if profile is None or profile.abv_percent is None or ext.abv_percent is None:
        return None
    # Allow a small tolerance for OCR/label rounding.
    if abs(ext.abv_percent - profile.abv_percent) > 0.3:
        return Finding(
            code="ABV_MISMATCH",
            severity="warn",
            message=(
                f"ABV {ext.abv_percent}% does not match expected "
                f"{profile.abv_percent}%."
            ),
        )
    return None


def check_net_contents(ext: LabelExtraction, ocr_conf: float, profile: Optional[Profile]):
    if not _norm(ext.net_contents):
        return Finding(
            code="MISSING_NET_CONTENTS",
            severity="error",
            message="Net contents / volume statement not found on the label.",
        )
    return None


def check_brand(ext: LabelExtraction, ocr_conf: float, profile: Optional[Profile]):
    if not _norm(ext.brand_name):
        return Finding(
            code="MISSING_BRAND",
            severity="warn",
            message="Brand name not detected on the label.",
        )
    return None


def check_brand_mismatch(ext: LabelExtraction, ocr_conf: float, profile: Optional[Profile]):
    if profile is None or not _norm(profile.brand_name) or not _norm(ext.brand_name):
        return None
    if _norm(profile.brand_name) not in _norm(ext.brand_name) and _norm(
        ext.brand_name
    ) not in _norm(profile.brand_name):
        return Finding(
            code="BRAND_MISMATCH",
            severity="warn",
            message=(
                f"Brand '{ext.brand_name}' does not match expected "
                f"'{profile.brand_name}'."
            ),
        )
    return None


def check_ocr_confidence(ext: LabelExtraction, ocr_conf: float, profile: Optional[Profile]):
    threshold = get_settings().ocr_confidence_threshold
    if ocr_conf < threshold:
        return Finding(
            code="LOW_OCR_CONFIDENCE",
            severity="warn",
            message=(
                f"OCR confidence {ocr_conf:.0f} is below {threshold:.0f}; "
                "results may be unreliable — consider re-photographing."
            ),
        )
    return None


ALL_RULES: list[Rule] = [
    check_gov_warning,
    check_abv,
    check_abv_mismatch,
    check_net_contents,
    check_brand,
    check_brand_mismatch,
    check_ocr_confidence,
]

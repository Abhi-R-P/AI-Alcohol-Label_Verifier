"""Verdict roll-up and soft-warning tests for the unified engine."""
from __future__ import annotations

from app.rules.validate import REQUIRED_WARNING_PHRASE, validate_label
from app.schemas import LabelExtraction, Profile

COMPLIANT = LabelExtraction(
    brand_name="Old Mill IPA",
    class_type="IPA",
    abv=6.5,
    net_contents="355 mL",
    producer="Old Mill Brewing",
    government_warning=True,
)
WARNING_TEXT = f"{REQUIRED_WARNING_PHRASE} According to the Surgeon General..."
HIGH_CONF = 90.0


def codes(findings):
    return {f.code for f in findings}


def test_low_ocr_confidence_warns():
    verdict, _, warnings = validate_label(COMPLIANT, WARNING_TEXT, ocr_confidence=10.0)
    assert verdict == "WARN"
    assert "LOW_OCR_CONFIDENCE" in codes(warnings)


def test_brand_mismatch_against_profile_warns():
    profile = Profile(brand_name="Different Brand")
    verdict, _, warnings = validate_label(COMPLIANT, WARNING_TEXT, HIGH_CONF, profile)
    assert verdict == "WARN"
    assert "BRAND_MISMATCH" in codes(warnings)


def test_brand_substring_match_against_profile_passes():
    profile = Profile(brand_name="Old Mill")  # substring of extracted brand
    verdict, _, warnings = validate_label(COMPLIANT, WARNING_TEXT, HIGH_CONF, profile)
    assert verdict == "PASS"
    assert "BRAND_MISMATCH" not in codes(warnings)


def test_abv_mismatch_against_profile_warns():
    profile = Profile(abv_percent=5.0)
    verdict, _, warnings = validate_label(COMPLIANT, WARNING_TEXT, HIGH_CONF, profile)
    assert verdict == "WARN"
    assert "ABV_MISMATCH" in codes(warnings)


def test_abv_within_tolerance_passes():
    profile = Profile(abv_percent=6.6)  # within 0.3 tolerance of 6.5
    _, _, warnings = validate_label(COMPLIANT, WARNING_TEXT, HIGH_CONF, profile)
    assert "ABV_MISMATCH" not in codes(warnings)


def test_field_failure_outranks_warning_in_verdict():
    ext = COMPLIANT.model_copy(update={"net_contents": None})
    # Also trigger a soft warning via low confidence.
    verdict, fields, warnings = validate_label(ext, WARNING_TEXT, ocr_confidence=10.0)
    assert verdict == "FAIL"  # a failed field outranks any warning
    assert fields["net_contents"].passed is False
    assert "LOW_OCR_CONFIDENCE" in codes(warnings)

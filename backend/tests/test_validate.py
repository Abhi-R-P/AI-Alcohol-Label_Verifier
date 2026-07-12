"""Tests for the unified deterministic validation engine (presence + fields)."""
from __future__ import annotations

from app.rules.validate import CANONICAL_GOV_WARNING, is_compliant, validate_label
from app.schemas import ApplicationData, LabelExtraction

COMPLIANT = LabelExtraction(
    brand_name="Old Mill IPA",
    class_type="IPA",
    abv=6.5,
    net_contents="355 mL",
    bottler_name="Old Mill Brewing Co.",
    bottler_address="Portland, OR",
    country_of_origin="USA",
    government_warning_text=CANONICAL_GOV_WARNING,
)
HIGH_CONF = 90.0


def test_fully_compliant_label_passes():
    verdict, fields, warnings = validate_label(COMPLIANT, HIGH_CONF)
    assert verdict == "PASS"
    assert is_compliant(fields)
    assert warnings == []


def test_missing_required_field_fails_only_that_field():
    ext = COMPLIANT.model_copy(update={"bottler_name": None})
    verdict, fields, _ = validate_label(ext, HIGH_CONF)
    assert verdict == "FAIL"
    assert fields["bottler_name"].status == "fail"
    assert fields["brand_name"].status == "pass"


def test_missing_bottler_address_fails():
    ext = COMPLIANT.model_copy(update={"bottler_address": None})
    verdict, fields, _ = validate_label(ext, HIGH_CONF)
    assert verdict == "FAIL"
    assert fields["bottler_address"].status == "fail"


def test_abv_missing_fails():
    ext = COMPLIANT.model_copy(update={"abv": None})
    verdict, fields, _ = validate_label(ext, HIGH_CONF)
    assert verdict == "FAIL"
    assert fields["abv"].status == "fail"


def test_abv_out_of_range_fails():
    ext = COMPLIANT.model_copy(update={"abv": 150.0})
    verdict, fields, _ = validate_label(ext, HIGH_CONF)
    assert verdict == "FAIL"
    assert "between 0 and 100" in fields["abv"].reason


def test_country_of_origin_optional_absent_is_info_not_pass():
    # An absent optional field must be neutral "info" (not a green PASS), and
    # must not fail the overall verdict.
    ext = COMPLIANT.model_copy(update={"country_of_origin": None})
    verdict, fields, _ = validate_label(ext, HIGH_CONF)
    assert fields["country_of_origin"].status == "info"
    assert fields["country_of_origin"].extracted is None
    assert verdict == "PASS"


def test_country_of_origin_present_passes():
    verdict, fields, _ = validate_label(COMPLIANT, HIGH_CONF)  # has "USA"
    assert fields["country_of_origin"].status == "pass"


def test_low_ocr_confidence_warns():
    verdict, _, warnings = validate_label(COMPLIANT, ocr_confidence=10.0)
    assert verdict == "WARN"
    assert any(w.code == "LOW_OCR_CONFIDENCE" for w in warnings)


def test_missing_field_at_high_confidence_fails():
    ext = COMPLIANT.model_copy(update={"net_contents": None})
    verdict, fields, _ = validate_label(ext, ocr_confidence=HIGH_CONF)
    assert verdict == "FAIL"
    assert fields["net_contents"].status == "fail"


def test_low_confidence_downgrades_missing_to_warn():
    # A field we couldn't read on a low-quality image -> WARN "couldn't read",
    # not FAIL "missing" (goes to human review rather than rejection).
    ext = COMPLIANT.model_copy(update={"net_contents": None, "abv": None})
    verdict, fields, warnings = validate_label(ext, ocr_confidence=10.0)
    assert verdict == "WARN"
    assert fields["net_contents"].status == "warn"
    assert fields["abv"].status == "warn"
    assert any(w.code == "LOW_OCR_CONFIDENCE" for w in warnings)


def test_low_confidence_does_not_mask_a_present_mismatch():
    # A present value that mismatches the application still FAILs even at low conf.
    from app.schemas import ApplicationData

    verdict, fields, _ = validate_label(
        COMPLIANT, ocr_confidence=10.0,
        application=ApplicationData(brand_name="Completely Different Ale"),
    )
    assert fields["brand_name"].status == "fail"
    assert verdict == "FAIL"

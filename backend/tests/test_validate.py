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


def test_country_of_origin_optional_when_absent():
    ext = COMPLIANT.model_copy(update={"country_of_origin": None})
    verdict, fields, _ = validate_label(ext, HIGH_CONF)
    assert fields["country_of_origin"].status == "pass"
    assert verdict == "PASS"


def test_low_ocr_confidence_warns():
    verdict, _, warnings = validate_label(COMPLIANT, ocr_confidence=10.0)
    assert verdict == "WARN"
    assert any(w.code == "LOW_OCR_CONFIDENCE" for w in warnings)


def test_field_fail_outranks_warn():
    ext = COMPLIANT.model_copy(update={"net_contents": None})
    verdict, fields, _ = validate_label(ext, ocr_confidence=10.0)
    assert verdict == "FAIL"
    assert fields["net_contents"].status == "fail"

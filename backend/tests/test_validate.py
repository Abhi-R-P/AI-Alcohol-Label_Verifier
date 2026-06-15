"""Tests for the unified deterministic validation engine."""
from __future__ import annotations

from app.rules.validate import REQUIRED_WARNING_PHRASE, is_compliant, validate_label
from app.schemas import LabelExtraction

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


def test_fully_compliant_label_passes_all_fields():
    verdict, fields, warnings = validate_label(COMPLIANT, WARNING_TEXT, HIGH_CONF)
    assert verdict == "PASS"
    assert is_compliant(fields)
    assert warnings == []


def test_missing_warning_phrase_fails():
    verdict, fields, _ = validate_label(COMPLIANT, "no warning here", HIGH_CONF)
    assert verdict == "FAIL"
    assert fields["government_warning"].passed is False
    assert REQUIRED_WARNING_PHRASE in fields["government_warning"].reason


def test_warning_phrase_match_is_case_insensitive():
    _, fields, _ = validate_label(COMPLIANT, "government warning: ...", HIGH_CONF)
    assert fields["government_warning"].passed is True


def test_abv_missing_fails():
    ext = COMPLIANT.model_copy(update={"abv": None})
    verdict, fields, _ = validate_label(ext, WARNING_TEXT, HIGH_CONF)
    assert verdict == "FAIL"
    assert fields["abv"].passed is False
    assert "missing" in fields["abv"].reason.lower()


def test_abv_out_of_range_fails():
    ext = COMPLIANT.model_copy(update={"abv": 150.0})
    verdict, fields, _ = validate_label(ext, WARNING_TEXT, HIGH_CONF)
    assert verdict == "FAIL"
    assert "between 0 and 100" in fields["abv"].reason


def test_missing_required_field_fails_only_that_field():
    ext = COMPLIANT.model_copy(update={"producer": None})
    verdict, fields, _ = validate_label(ext, WARNING_TEXT, HIGH_CONF)
    assert verdict == "FAIL"
    assert fields["producer"].passed is False
    assert fields["brand_name"].passed is True


def test_blank_required_field_treated_as_missing():
    ext = COMPLIANT.model_copy(update={"brand_name": "   "})
    _, fields, _ = validate_label(ext, WARNING_TEXT, HIGH_CONF)
    assert fields["brand_name"].passed is False

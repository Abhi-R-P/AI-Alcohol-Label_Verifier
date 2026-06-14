"""Tests for the deterministic per-field validation engine."""
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


def test_fully_compliant_label_passes_all_fields():
    results = validate_label(COMPLIANT, WARNING_TEXT)
    assert is_compliant(results)
    assert all(r.passed and r.reason is None for r in results.values())


def test_missing_warning_phrase_fails():
    results = validate_label(COMPLIANT, "no warning here")
    assert results["government_warning"].passed is False
    assert REQUIRED_WARNING_PHRASE in results["government_warning"].reason


def test_warning_phrase_match_is_case_insensitive():
    results = validate_label(COMPLIANT, "government warning: ...")
    assert results["government_warning"].passed is True


def test_abv_missing_fails():
    ext = COMPLIANT.model_copy(update={"abv": None})
    results = validate_label(ext, WARNING_TEXT)
    assert results["abv"].passed is False
    assert "missing" in results["abv"].reason.lower()


def test_abv_out_of_range_fails():
    ext = COMPLIANT.model_copy(update={"abv": 150.0})
    results = validate_label(ext, WARNING_TEXT)
    assert results["abv"].passed is False
    assert "between 0 and 100" in results["abv"].reason


def test_missing_required_field_fails_only_that_field():
    ext = COMPLIANT.model_copy(update={"producer": None})
    results = validate_label(ext, WARNING_TEXT)
    assert results["producer"].passed is False
    assert results["brand_name"].passed is True
    assert is_compliant(results) is False


def test_blank_required_field_treated_as_missing():
    ext = COMPLIANT.model_copy(update={"brand_name": "   "})
    results = validate_label(ext, WARNING_TEXT)
    assert results["brand_name"].passed is False

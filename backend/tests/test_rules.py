"""Strict government-warning + fuzzy application-comparison tests."""
from __future__ import annotations

from app.rules.validate import (
    CANONICAL_GOV_WARNING,
    check_government_warning,
    validate_label,
)
from app.schemas import ApplicationData, LabelExtraction

BASE = LabelExtraction(
    brand_name="Stone's Throw Lager",
    class_type="Lager",
    abv=5.0,
    net_contents="12 FL OZ",
    bottler_name="Stone's Throw Brewing",
    bottler_address="Austin, TX",
    country_of_origin="USA",
    government_warning_text=CANONICAL_GOV_WARNING,
)


# --- Government warning strictness ---------------------------------------

def test_exact_warning_passes():
    assert check_government_warning(CANONICAL_GOV_WARNING).status == "pass"


def test_warning_whitespace_normalized_passes():
    noisy = "  GOVERNMENT WARNING:  (1) According to the Surgeon General, women " \
        "should not drink alcoholic beverages during pregnancy because of the " \
        "risk of birth defects. (2) Consumption of alcoholic beverages impairs " \
        "your ability to drive a car or operate machinery, and may cause health problems."
    assert check_government_warning(noisy).status == "pass"


def test_warning_wrong_case_warns():
    lowered = CANONICAL_GOV_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
    assert check_government_warning(lowered).status == "warn"


def test_warning_missing_fails():
    assert check_government_warning(None).status == "fail"


def test_warning_substantively_different_fails():
    assert check_government_warning("Drink responsibly. Do not drive.").status == "fail"


# --- Fuzzy application comparison (Dave Morrison's STONE'S THROW) --------

def test_apostrophe_case_difference_warns_not_fails():
    # Label says "Stone's Throw Lager"; application typed "STONES THROW LAGER".
    app = ApplicationData(brand_name="STONES THROW LAGER")
    verdict, fields, _ = validate_label(BASE, 90.0, application=app)
    assert fields["brand_name"].status == "warn"
    assert verdict in ("WARN", "PASS") and verdict != "FAIL"


def test_exact_application_match_passes():
    app = ApplicationData(brand_name="Stone's Throw Lager", abv=5.0)
    _, fields, _ = validate_label(BASE, 90.0, application=app)
    assert fields["brand_name"].status == "pass"
    assert fields["abv"].status == "pass"


def test_substantive_brand_mismatch_fails():
    app = ApplicationData(brand_name="Completely Different Ale")
    verdict, fields, _ = validate_label(BASE, 90.0, application=app)
    assert fields["brand_name"].status == "fail"
    assert verdict == "FAIL"


def test_abv_beyond_tolerance_fails():
    app = ApplicationData(abv=9.0)  # label is 5.0
    _, fields, _ = validate_label(BASE, 90.0, application=app)
    assert fields["abv"].status == "fail"


def test_abv_within_tolerance_passes():
    app = ApplicationData(abv=5.2)  # within 0.3 of 5.0
    _, fields, _ = validate_label(BASE, 90.0, application=app)
    assert fields["abv"].status == "pass"

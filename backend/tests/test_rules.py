"""Deterministic rule-engine tests — fast, no network, high value."""
from __future__ import annotations

from app.rules.engine import evaluate
from app.schemas import LabelExtraction, Profile

# A fully-compliant label used as a baseline; tweak per test.
COMPLIANT = LabelExtraction(
    brand_name="Old Mill IPA",
    producer="Old Mill Brewing",
    class_type="IPA",
    abv=6.5,
    net_contents="355 mL",
    government_warning=True,
)
HIGH_CONF = 90.0


def codes(findings):
    return {f.code for f in findings}


def test_compliant_label_passes():
    verdict, findings = evaluate(COMPLIANT, HIGH_CONF)
    assert verdict == "PASS"
    assert findings == []


def test_missing_gov_warning_fails():
    ext = COMPLIANT.model_copy(update={"government_warning": False})
    verdict, findings = evaluate(ext, HIGH_CONF)
    assert verdict == "FAIL"
    assert "MISSING_GOV_WARNING" in codes(findings)


def test_missing_abv_fails():
    ext = COMPLIANT.model_copy(update={"abv": None})
    verdict, findings = evaluate(ext, HIGH_CONF)
    assert verdict == "FAIL"
    assert "MISSING_ABV" in codes(findings)


def test_abv_out_of_range_warns():
    ext = COMPLIANT.model_copy(update={"abv": 150.0})
    verdict, findings = evaluate(ext, HIGH_CONF)
    assert verdict == "WARN"
    assert "ABV_OUT_OF_RANGE" in codes(findings)


def test_missing_net_contents_fails():
    ext = COMPLIANT.model_copy(update={"net_contents": None})
    verdict, findings = evaluate(ext, HIGH_CONF)
    assert verdict == "FAIL"
    assert "MISSING_NET_CONTENTS" in codes(findings)


def test_low_ocr_confidence_warns():
    verdict, findings = evaluate(COMPLIANT, 10.0)
    assert verdict == "WARN"
    assert "LOW_OCR_CONFIDENCE" in codes(findings)


def test_brand_mismatch_against_profile_warns():
    profile = Profile(brand_name="Different Brand")
    verdict, findings = evaluate(COMPLIANT, HIGH_CONF, profile)
    assert verdict == "WARN"
    assert "BRAND_MISMATCH" in codes(findings)


def test_brand_match_against_profile_passes():
    profile = Profile(brand_name="Old Mill")  # substring match
    verdict, findings = evaluate(COMPLIANT, HIGH_CONF, profile)
    assert verdict == "PASS"
    assert "BRAND_MISMATCH" not in codes(findings)


def test_abv_mismatch_against_profile_warns():
    profile = Profile(abv_percent=5.0)
    verdict, findings = evaluate(COMPLIANT, HIGH_CONF, profile)
    assert verdict == "WARN"
    assert "ABV_MISMATCH" in codes(findings)


def test_abv_within_tolerance_passes():
    profile = Profile(abv_percent=6.6)  # within 0.3 tolerance of 6.5
    verdict, findings = evaluate(COMPLIANT, HIGH_CONF, profile)
    assert "ABV_MISMATCH" not in codes(findings)


def test_error_outranks_warn_in_verdict():
    ext = COMPLIANT.model_copy(
        update={"government_warning": False, "abv": 150.0}
    )
    verdict, findings = evaluate(ext, HIGH_CONF)
    # Has both an error (gov warning) and a warn (abv range) -> FAIL wins.
    assert verdict == "FAIL"
    assert {"MISSING_GOV_WARNING", "ABV_OUT_OF_RANGE"} <= codes(findings)

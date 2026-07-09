"""Tests for the pure eval scoring helpers."""
from __future__ import annotations

from eval.scoring import match_abv, match_text, score_record


def test_text_exact_and_normalized_match():
    assert match_text("Old Mill IPA", "Old Mill IPA")
    assert match_text("old  mill ipa", "Old Mill IPA")  # case/space
    assert match_text("Stone's Throw", "Stones Throw")  # punctuation


def test_text_substantive_difference_does_not_match():
    assert not match_text("Completely Different", "Old Mill IPA")


def test_absent_matches_only_absent():
    assert match_text(None, None)
    assert not match_text("something", None)
    assert not match_text(None, "expected value")


def test_abv_tolerance():
    assert match_abv(6.5, 6.5)
    assert match_abv(6.6, 6.5)      # within 0.3
    assert not match_abv(8.0, 6.5)  # beyond tolerance
    assert match_abv(None, None)
    assert not match_abv(None, 6.5)


def test_score_record_counts_fields():
    expected = {
        "brand_name": "Old Mill IPA",
        "class_type": "India Pale Ale",
        "abv": 6.5,
        "net_contents": "355 mL",
        "bottler_name": "Old Mill Brewing Co.",
        "bottler_address": "Portland, OR",
        "country_of_origin": "USA",
        "government_warning_text": None,
    }
    extracted = dict(expected, net_contents=None)  # one wrong field
    scores = score_record(extracted, expected)
    assert scores["brand_name"] is True
    assert scores["net_contents"] is False
    assert sum(scores.values()) == len(scores) - 1

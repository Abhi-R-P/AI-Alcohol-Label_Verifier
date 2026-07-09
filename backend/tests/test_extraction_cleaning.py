"""Placeholder/sentinel values must become None, not pass as real fields."""
from __future__ import annotations

import pytest

from app.rules.validate import CANONICAL_GOV_WARNING, validate_label
from app.schemas import LabelExtraction


@pytest.mark.parametrize(
    "placeholder",
    ["<UNKNOWN>", "unknown", "N/A", "n/a", "None", "not visible", "  UNKNOWN  ", "-"],
)
def test_placeholder_strings_become_none(placeholder):
    ext = LabelExtraction(brand_name=placeholder, class_type=placeholder)
    assert ext.brand_name is None
    assert ext.class_type is None


def test_real_values_are_preserved_and_trimmed():
    ext = LabelExtraction(brand_name="  Old Mill IPA  ", country_of_origin="USA")
    assert ext.brand_name == "Old Mill IPA"
    assert ext.country_of_origin == "USA"


def test_placeholder_field_fails_presence_not_passes():
    # The screenshot bug: "<UNKNOWN>" fields were shown as PASS. They must FAIL.
    ext = LabelExtraction(
        brand_name="<UNKNOWN>",
        class_type="<UNKNOWN>",
        abv=None,
        net_contents="<UNKNOWN>",
        bottler_name="<UNKNOWN>",
        bottler_address="<UNKNOWN>",
        government_warning_text=None,
    )
    verdict, fields, _ = validate_label(ext, ocr_confidence=90.0)
    assert verdict == "FAIL"
    for key in ("brand_name", "class_type", "net_contents", "bottler_name", "bottler_address"):
        assert fields[key].status == "fail", key
        assert fields[key].extracted is None

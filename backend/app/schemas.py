"""Pydantic models shared across the pipeline and the API surface."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Severity = Literal["error", "warn", "info"]
Verdict = Literal["PASS", "WARN", "FAIL"]
FieldStatus = Literal["pass", "warn", "fail"]

# Placeholder strings a model may emit instead of null for an unreadable field.
# These must NOT be treated as real extracted values.
_SENTINEL_VALUES = {
    "", "unknown", "n/a", "na", "none", "null", "nil", "not visible",
    "not present", "not shown", "not stated", "not specified", "not found",
    "not legible", "illegible", "not applicable", "not available", "unspecified",
    "no value", "missing", "-", "--", "–", "—",
}


def _clean_field(value: object) -> Optional[str]:
    """Map placeholder/sentinel strings to None; trim real values."""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    key = stripped.lower().strip("<>[](){} ").rstrip(".").strip()
    if key in _SENTINEL_VALUES:
        return None
    return stripped or None


class LabelExtraction(BaseModel):
    """Structured TTB fields Claude extracts from the OCR'd label text.

    Flat and typed (passed to the structured-output API). A field is `None`
    when not present on the label.
    """

    brand_name: Optional[str] = Field(None, description="Brand name / fanciful name.")
    class_type: Optional[str] = Field(
        None, description="Class/type designation, e.g. 'IPA', 'Cabernet Sauvignon', 'Vodka'."
    )
    abv: Optional[float] = Field(
        None, description="Alcohol by volume as a percentage number, e.g. 6.5."
    )
    net_contents: Optional[str] = Field(
        None, description="Net contents / volume statement, e.g. '750 mL', '12 FL OZ'."
    )
    bottler_name: Optional[str] = Field(
        None, description="Name of the bottler / producer / importer."
    )
    bottler_address: Optional[str] = Field(
        None, description="City and state (and/or full address) of the bottler/importer."
    )
    country_of_origin: Optional[str] = Field(
        None, description="Country of origin, if stated (required for imports)."
    )
    government_warning_text: Optional[str] = Field(
        None,
        description=(
            "The government health warning statement copied VERBATIM as printed "
            "on the label (preserve wording, capitalization, and punctuation). "
            "Null if no government warning appears."
        ),
    )

    @field_validator(
        "brand_name",
        "class_type",
        "net_contents",
        "bottler_name",
        "bottler_address",
        "country_of_origin",
        "government_warning_text",
        mode="before",
    )
    @classmethod
    def _null_placeholders(cls, v: object) -> Optional[str]:
        # A field the model couldn't read must be None, not "<UNKNOWN>"/"N/A" —
        # otherwise a placeholder would pass the presence check.
        return _clean_field(v)


class ApplicationData(BaseModel):
    """Expected values from the COLA application, to compare the label against.

    Every field is optional — only provided fields are compared; the rest fall
    back to presence/format checks.
    """

    brand_name: Optional[str] = None
    class_type: Optional[str] = None
    abv: Optional[float] = None
    net_contents: Optional[str] = None
    bottler_name: Optional[str] = None
    bottler_address: Optional[str] = None
    country_of_origin: Optional[str] = None


class FieldResult(BaseModel):
    """Per-field validation outcome (three-state)."""

    status: FieldStatus
    reason: Optional[str] = None
    extracted: Optional[str] = Field(None, description="Value read from the label.")
    expected: Optional[str] = Field(None, description="Value from the application, if any.")


class Finding(BaseModel):
    code: str
    severity: Severity
    message: str


class Timings(BaseModel):
    ocr_ms: int = 0
    claude_ms: int = 0
    rules_ms: int = 0
    total_ms: int = 0


class ImageResult(BaseModel):
    filename: str
    verdict: Verdict
    fields: LabelExtraction
    ocr_text: str = Field("", description="Raw text extracted by OCR.")
    ocr_confidence: float = Field(0.0, description="Mean OCR confidence (0-100).")
    field_validation: dict[str, FieldResult] = {}
    findings: list[Finding] = []
    timings: Timings = Timings()
    error: Optional[str] = None


class Summary(BaseModel):
    total: int = 0
    passed: int = 0
    warned: int = 0
    failed: int = 0


class VerifyResponse(BaseModel):
    summary: Summary
    results: list[ImageResult]


class RuleInfo(BaseModel):
    code: str
    severity: Severity
    description: str

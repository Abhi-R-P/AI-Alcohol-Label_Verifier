"""Pydantic models shared across the pipeline and the API surface."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["error", "warn", "info"]
Verdict = Literal["PASS", "WARN", "FAIL"]


class LabelExtraction(BaseModel):
    """Structured fields Claude extracts from the OCR'd label text.

    This is the schema passed to the Anthropic structured-output API, so keep it
    flat and typed. A field is `None` when it is not present on the label.
    """

    brand_name: Optional[str] = Field(None, description="Product / brand name.")
    class_type: Optional[str] = Field(
        None, description="Beverage class/type, e.g. 'IPA', 'Cabernet Sauvignon', 'Vodka'."
    )
    abv: Optional[float] = Field(
        None, description="Alcohol by volume as a percentage number, e.g. 6.5."
    )
    net_contents: Optional[str] = Field(
        None, description="Net contents / volume statement, e.g. '750 mL', '12 FL OZ'."
    )
    producer: Optional[str] = Field(None, description="Producer, bottler, or importer.")
    government_warning: bool = Field(
        False,
        description="True only if the government health warning text is present on the label.",
    )


class Profile(BaseModel):
    """Optional expected values to validate the extracted label against."""

    brand_name: Optional[str] = None
    abv_percent: Optional[float] = None
    net_contents: Optional[str] = None
    region: Optional[str] = None


class Finding(BaseModel):
    code: str
    severity: Severity
    message: str


class FieldResult(BaseModel):
    """Deterministic per-field validation outcome."""

    passed: bool
    reason: Optional[str] = None


class Timings(BaseModel):
    ocr_ms: int = 0
    claude_ms: int = 0
    rules_ms: int = 0
    total_ms: int = 0


class ImageResult(BaseModel):
    filename: str
    verdict: Verdict
    fields: LabelExtraction
    ocr_confidence: float = Field(
        0.0, description="Mean OCR confidence (0-100) for the image."
    )
    findings: list[Finding] = []
    field_validation: dict[str, FieldResult] = {}
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

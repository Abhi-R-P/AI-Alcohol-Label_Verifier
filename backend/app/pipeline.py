"""Per-image orchestration: decode -> OCR -> Claude extraction -> rules.

`process_image` handles one image end to end and never raises — failures are
captured into the ImageResult so a single bad image doesn't sink the batch.
"""
from __future__ import annotations

import time
from typing import Optional

from app.config import get_settings
from app.rules.engine import evaluate
from app.schemas import Finding, ImageResult, LabelExtraction, Profile, Timings
from app.services.extract import ExtractionError, ExtractionTimeout, extract_fields
from app.services.image import load_and_normalize
from app.services.ocr import run_ocr


def _ms_since(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def process_image(
    filename: str, raw: bytes, profile: Optional[Profile] = None
) -> ImageResult:
    settings = get_settings()
    overall_start = time.perf_counter()
    timings = Timings()

    # 1. Decode & normalize.
    try:
        img = load_and_normalize(raw, settings.max_image_edge)
    except Exception as exc:  # noqa: BLE001 - surface any decode failure as a result
        timings.total_ms = _ms_since(overall_start)
        return ImageResult(
            filename=filename,
            verdict="FAIL",
            fields=LabelExtraction(),
            findings=[
                Finding(
                    code="DECODE_FAILED",
                    severity="error",
                    message=f"Could not read image: {exc}",
                )
            ],
            timings=timings,
            error=str(exc),
        )

    # 2. OCR.
    ocr_start = time.perf_counter()
    ocr = run_ocr(img)
    timings.ocr_ms = _ms_since(ocr_start)

    # 3. Claude structured extraction. A timeout degrades gracefully to the
    #    OCR-only path with a warning rather than failing the whole image.
    extra_findings: list[Finding] = []
    error: Optional[str] = None
    claude_start = time.perf_counter()
    try:
        extraction = extract_fields(ocr.text)
    except ExtractionTimeout:
        extraction = LabelExtraction()
        extra_findings.append(
            Finding(
                code="EXTRACTION_TIMEOUT",
                severity="warn",
                message="Field extraction timed out; verdict based on OCR only.",
            )
        )
        error = "extraction_timeout"
    except ExtractionError as exc:
        extraction = LabelExtraction()
        extra_findings.append(
            Finding(
                code="EXTRACTION_FAILED",
                severity="error",
                message=f"Field extraction failed: {exc}",
            )
        )
        error = str(exc)
    timings.claude_ms = _ms_since(claude_start)

    # 4. Deterministic rules.
    rules_start = time.perf_counter()
    verdict, findings = evaluate(extraction, ocr.mean_confidence, profile)
    timings.rules_ms = _ms_since(rules_start)

    findings = extra_findings + findings
    # An extraction error is itself an error-severity finding -> FAIL.
    if any(f.severity == "error" for f in findings):
        verdict = "FAIL"

    timings.total_ms = _ms_since(overall_start)
    return ImageResult(
        filename=filename,
        verdict=verdict,
        fields=extraction,
        ocr_confidence=ocr.mean_confidence,
        findings=findings,
        timings=timings,
        error=error,
    )

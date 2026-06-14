"""Structured field extraction from OCR text via the Claude API.

Claude only *extracts* fields here — it never decides regulatory compliance.
That deterministic logic lives in `app/rules/`. We use the SDK's structured
output (`messages.parse`) so the response is schema-validated into a
`LabelExtraction`, and a low `max_tokens` + client timeout to protect the
per-image latency budget.
"""
from __future__ import annotations

from functools import lru_cache

import anthropic

from app.config import get_settings
from app.schemas import LabelExtraction

# Prompt template. The schema itself is enforced by the SDK's structured-output
# mode (output_format=LabelExtraction), so the model cannot return anything but
# valid JSON matching the six fields. The prompt focuses on *how* to read noisy
# OCR text. Single call, no multi-step reasoning.
SYSTEM_PROMPT = """\
You extract structured fields from OCR'd text taken from a single alcohol \
product label.

The OCR text is often noisy: misread characters (0/O, 1/l, 5/S), broken or \
merged words, stray symbols, wrong casing, and out-of-order fragments. Read \
through that noise to recover the intended values.

Extract exactly these fields:
- brand_name: the product or brand name.
- class_type: the beverage class/type (e.g. "IPA", "Cabernet Sauvignon", "Vodka").
- abv: alcohol by volume as a number only (e.g. 6.5 for "ABV 6.5%" or "ALC. 6,5% VOL").
- net_contents: the volume statement as written (e.g. "750 mL", "12 FL OZ").
- producer: the producer, bottler, or importer.
- government_warning: true ONLY if government health warning text appears, else false.

Rules:
- If a field is not present or cannot be reasonably recovered, set it to null \
(government_warning to false).
- Do NOT invent, translate, or infer values not supported by the text.
- Do NOT judge regulatory compliance — only report what the label says.

Example
OCR text:
"OLO MlLL  IPA  india pale ale  ALC 6.5% BY VOL  355 mL  Brewed and bottled by \
Old Mill Brewing Co.  GOVERNMENT WARNING: According to the Surgeon General..."
Correct extraction:
{"brand_name": "Old Mill", "class_type": "India Pale Ale", "abv": 6.5, \
"net_contents": "355 mL", "producer": "Old Mill Brewing Co.", \
"government_warning": true}\
"""


class ExtractionTimeout(Exception):
    """Raised when the Claude call exceeds the configured timeout."""


class ExtractionError(Exception):
    """Raised when extraction fails for a non-timeout reason (e.g. refusal)."""


@lru_cache
def _client() -> anthropic.Anthropic:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ExtractionError("ANTHROPIC_API_KEY is not set.")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def extract_fields(ocr_text: str) -> LabelExtraction:
    """Extract label fields from OCR text. Returns a validated LabelExtraction.

    Raises ExtractionTimeout on timeout, ExtractionError otherwise.
    """
    settings = get_settings()

    if not ocr_text.strip():
        # Nothing for the model to read — short-circuit with an empty extraction.
        return LabelExtraction()

    try:
        response = _client().with_options(
            timeout=settings.extraction_timeout_s, max_retries=0
        ).messages.parse(
            model=settings.extraction_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"OCR text from the label:\n\n{ocr_text}",
                }
            ],
            output_format=LabelExtraction,
        )
    except anthropic.APITimeoutError as exc:
        raise ExtractionTimeout(str(exc)) from exc
    except anthropic.APIError as exc:
        raise ExtractionError(str(exc)) from exc

    if response.parsed_output is None:
        raise ExtractionError(
            f"Model returned no structured output (stop_reason={response.stop_reason})."
        )
    return response.parsed_output

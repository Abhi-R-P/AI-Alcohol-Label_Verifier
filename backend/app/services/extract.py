"""Structured field extraction from OCR text via the Claude API.

Claude only *extracts* fields here — it never decides regulatory compliance.
That deterministic logic lives in `app/rules/`. We get strict structured output
by defining a tool whose input schema is the TTB fields and forcing Claude to
call it (`tool_choice`). A low `max_tokens` + client timeout protect the
per-image latency budget. Single call, no multi-step reasoning.
"""
from __future__ import annotations

from functools import lru_cache

import anthropic

from app.config import get_settings
from app.schemas import LabelExtraction

SYSTEM_PROMPT = """\
You extract structured fields from OCR'd text taken from a single alcohol \
product label (a TTB COLA label).

The OCR text is often noisy: misread characters (0/O, 1/l, 5/S), broken or \
merged words, stray symbols, wrong casing, and out-of-order fragments. Read \
through that noise to recover the intended values.

Call the `record_label_fields` tool with these fields:
- brand_name: the brand / fanciful name.
- class_type: the class/type designation (e.g. "IPA", "Cabernet Sauvignon", "Vodka").
- abv: alcohol by volume as a number only (e.g. 6.5 for "ABV 6.5%" / "ALC. 6,5% VOL").
- net_contents: the volume statement as written (e.g. "750 mL", "12 FL OZ").
- bottler_name: the bottler / producer / importer name (e.g. "Bottled by Old Mill Brewing Co.").
- bottler_address: the bottler/importer city and state, or full address, if present.
- country_of_origin: the country of origin, if stated.
- government_warning_text: the government health warning statement copied VERBATIM \
as printed — preserve exact wording, capitalization, and punctuation. This is used \
for a strict compliance check, so do NOT paraphrase, correct, or complete it. Copy \
only what actually appears; null if no government warning is present.

Rules:
- If a field is not present or cannot be reasonably recovered, set it to null.
- Do NOT invent, translate, infer, or "fix" values not supported by the text.
- Do NOT judge regulatory compliance — only report what the label says.
"""

EXTRACTION_TOOL = {
    "name": "record_label_fields",
    "description": "Record the structured fields extracted from the alcohol label.",
    "input_schema": {
        "type": "object",
        "properties": {
            "brand_name": {"type": ["string", "null"]},
            "class_type": {"type": ["string", "null"]},
            "abv": {"type": ["number", "null"]},
            "net_contents": {"type": ["string", "null"]},
            "bottler_name": {"type": ["string", "null"]},
            "bottler_address": {"type": ["string", "null"]},
            "country_of_origin": {"type": ["string", "null"]},
            "government_warning_text": {"type": ["string", "null"]},
        },
        "required": [
            "brand_name",
            "class_type",
            "abv",
            "net_contents",
            "bottler_name",
            "bottler_address",
            "country_of_origin",
            "government_warning_text",
        ],
    },
}


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
        return LabelExtraction()

    try:
        response = _client().with_options(
            timeout=settings.extraction_timeout_s, max_retries=0
        ).messages.create(
            model=settings.extraction_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "record_label_fields"},
            messages=[
                {"role": "user", "content": f"OCR text from the label:\n\n{ocr_text}"}
            ],
        )
    except anthropic.APITimeoutError as exc:
        raise ExtractionTimeout(str(exc)) from exc
    except anthropic.APIError as exc:
        raise ExtractionError(str(exc)) from exc

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise ExtractionError(
            f"Model did not return the extraction tool (stop_reason={response.stop_reason})."
        )
    return LabelExtraction.model_validate(tool_use.input)

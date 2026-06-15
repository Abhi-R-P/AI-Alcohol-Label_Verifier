"""Structured field extraction from OCR text via the Claude API.

Claude only *extracts* fields here — it never decides regulatory compliance.
That deterministic logic lives in `app/rules/`. We get strict structured output
by defining a tool whose input schema is the six label fields and forcing Claude
to call it (`tool_choice`). The tool's `input` is therefore a schema-shaped JSON
object we validate into a `LabelExtraction`. A low `max_tokens` + client timeout
protect the per-image latency budget. Single call, no multi-step reasoning.
"""
from __future__ import annotations

from functools import lru_cache

import anthropic

from app.config import get_settings
from app.schemas import LabelExtraction

SYSTEM_PROMPT = """\
You extract structured fields from OCR'd text taken from a single alcohol \
product label.

The OCR text is often noisy: misread characters (0/O, 1/l, 5/S), broken or \
merged words, stray symbols, wrong casing, and out-of-order fragments. Read \
through that noise to recover the intended values.

Call the `record_label_fields` tool with exactly these fields:
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
"""

# Tool schema = the six label fields. Forcing this tool yields strict, typed
# JSON without depending on a specific SDK's structured-output helper.
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
            "producer": {"type": ["string", "null"]},
            "government_warning": {"type": "boolean"},
        },
        "required": [
            "brand_name",
            "class_type",
            "abv",
            "net_contents",
            "producer",
            "government_warning",
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
        # Nothing for the model to read — short-circuit with an empty extraction.
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
                {
                    "role": "user",
                    "content": f"OCR text from the label:\n\n{ocr_text}",
                }
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


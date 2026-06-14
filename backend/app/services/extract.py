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

SYSTEM_PROMPT = (
    "You extract structured fields from OCR'd text taken from an alcohol product "
    "label. The OCR text may contain noise, misreads, and broken words. Return only "
    "the fields defined by the schema. If a field is not present in the text, set it "
    "to null (and government_warning_present to false). Do not guess, translate, or "
    "infer values that are not supported by the text. Do not make any judgment about "
    "regulatory compliance — only report what the label says."
)


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

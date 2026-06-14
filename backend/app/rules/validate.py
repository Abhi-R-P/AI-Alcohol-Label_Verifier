"""Pure, deterministic per-field validation for alcohol label compliance.

No AI here — this is the rule layer that decides pass/fail. It returns a
structured result per field (`passed` + `reason` if failed) so callers can show
exactly which requirement each field met or missed.

Rules enforced:
  - government_warning: the label text must contain the literal required phrase
    "GOVERNMENT WARNING:".
  - abv: must be numeric and between 0 and 100 (exclusive).
  - required fields (brand_name, class_type, net_contents, producer): must be
    present (non-empty).
"""
from __future__ import annotations

from app.schemas import FieldResult, LabelExtraction

REQUIRED_WARNING_PHRASE = "GOVERNMENT WARNING:"
REQUIRED_TEXT_FIELDS = ("brand_name", "class_type", "net_contents", "producer")


def _ok() -> FieldResult:
    return FieldResult(passed=True)


def _fail(reason: str) -> FieldResult:
    return FieldResult(passed=False, reason=reason)


def validate_label(fields: LabelExtraction, ocr_text: str = "") -> dict[str, FieldResult]:
    """Validate extracted label fields. Returns {field_name: FieldResult}.

    `ocr_text` is the raw OCR string; the government-warning check looks for the
    required phrase there (case-insensitive) so the rule never depends on AI.
    """
    results: dict[str, FieldResult] = {}

    # 1. Government warning must include the required phrase, verbatim.
    if REQUIRED_WARNING_PHRASE.casefold() in (ocr_text or "").casefold():
        results["government_warning"] = _ok()
    else:
        results["government_warning"] = _fail(
            f'Required phrase "{REQUIRED_WARNING_PHRASE}" not found in label text.'
        )

    # 2. ABV must be numeric and between 0 and 100.
    abv = fields.abv
    if abv is None:
        results["abv"] = _fail("ABV is missing.")
    elif isinstance(abv, bool) or not isinstance(abv, (int, float)):
        results["abv"] = _fail("ABV is not numeric.")
    elif not (0 < abv < 100):
        results["abv"] = _fail(f"ABV {abv} is not between 0 and 100.")
    else:
        results["abv"] = _ok()

    # 3. All required text fields must be present.
    for name in REQUIRED_TEXT_FIELDS:
        value = getattr(fields, name)
        if value is None or not str(value).strip():
            results[name] = _fail(f"{name} is missing.")
        else:
            results[name] = _ok()

    return results


def is_compliant(results: dict[str, FieldResult]) -> bool:
    """True only if every field passed."""
    return all(r.passed for r in results.values())

"""Single, deterministic compliance engine — the one source of truth.

No AI here. Given the extracted fields (plus the raw OCR text, OCR confidence,
and an optional expected profile) it returns:

  - verdict:          PASS / WARN / FAIL
  - field_results:    per-field {passed, reason} for the six required fields
  - warnings:         soft issues that don't fail a field (low OCR confidence,
                      profile mismatches)

Hard rules (a failure makes the field fail and the verdict FAIL):
  - government_warning: OCR text must contain the literal "GOVERNMENT WARNING:".
  - abv: must be numeric and between 0 and 100 (exclusive).
  - brand_name / class_type / net_contents / producer: must be present.
"""
from __future__ import annotations

from typing import Optional

from app.schemas import FieldResult, Finding, LabelExtraction, Profile, RuleInfo, Verdict

REQUIRED_WARNING_PHRASE = "GOVERNMENT WARNING:"
REQUIRED_TEXT_FIELDS: list[tuple[str, str]] = [
    ("brand_name", "Brand name"),
    ("class_type", "Class / type"),
    ("net_contents", "Net contents"),
    ("producer", "Producer"),
]

# Surfaced via GET /rules and the UI legend.
RULE_CATALOG: list[tuple[str, str, str]] = [
    ("GOVERNMENT_WARNING", "error", 'Label text must contain the phrase "GOVERNMENT WARNING:".'),
    ("ABV", "error", "ABV must be present, numeric, and between 0 and 100."),
    ("REQUIRED_FIELD", "error", "Brand, class/type, net contents, and producer must be present."),
    ("LOW_OCR_CONFIDENCE", "warn", "OCR confidence is low; results may be unreliable."),
    ("BRAND_MISMATCH", "warn", "Brand does not match the expected profile."),
    ("ABV_MISMATCH", "warn", "ABV does not match the expected profile."),
]


def _ok() -> FieldResult:
    return FieldResult(passed=True)


def _fail(reason: str) -> FieldResult:
    return FieldResult(passed=False, reason=reason)


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_label(
    fields: LabelExtraction,
    ocr_text: str = "",
    ocr_confidence: float = 100.0,
    profile: Optional[Profile] = None,
    ocr_threshold: float = 55.0,
) -> tuple[Verdict, dict[str, FieldResult], list[Finding]]:
    """Run all rules. Returns (verdict, field_results, warnings)."""
    field_results: dict[str, FieldResult] = {}

    # 1. Government warning — literal phrase in the OCR text (deterministic).
    field_results["government_warning"] = (
        _ok()
        if REQUIRED_WARNING_PHRASE.casefold() in (ocr_text or "").casefold()
        else _fail(f'Required phrase "{REQUIRED_WARNING_PHRASE}" not found in label text.')
    )

    # 2. ABV — numeric and in range.
    abv = fields.abv
    if abv is None:
        field_results["abv"] = _fail("ABV is missing.")
    elif not _is_number(abv):
        field_results["abv"] = _fail("ABV is not numeric.")
    elif not (0 < abv < 100):
        field_results["abv"] = _fail(f"ABV {abv} is not between 0 and 100.")
    else:
        field_results["abv"] = _ok()

    # 3. Required text fields present.
    for key, label in REQUIRED_TEXT_FIELDS:
        value = getattr(fields, key)
        field_results[key] = (
            _ok() if value is not None and str(value).strip() else _fail(f"{label} is missing.")
        )

    # 4. Soft warnings (do not fail a field).
    warnings: list[Finding] = []
    if ocr_confidence < ocr_threshold:
        warnings.append(
            Finding(
                code="LOW_OCR_CONFIDENCE",
                severity="warn",
                message=(
                    f"OCR confidence {ocr_confidence:.0f} is below {ocr_threshold:.0f}; "
                    "results may be unreliable — consider re-photographing."
                ),
            )
        )
    if profile is not None:
        if (
            _norm(profile.brand_name)
            and _norm(fields.brand_name)
            and _norm(profile.brand_name) not in _norm(fields.brand_name)
            and _norm(fields.brand_name) not in _norm(profile.brand_name)
        ):
            warnings.append(
                Finding(
                    code="BRAND_MISMATCH",
                    severity="warn",
                    message=f"Brand '{fields.brand_name}' does not match expected '{profile.brand_name}'.",
                )
            )
        if profile.abv_percent is not None and _is_number(abv) and abs(abv - profile.abv_percent) > 0.3:
            warnings.append(
                Finding(
                    code="ABV_MISMATCH",
                    severity="warn",
                    message=f"ABV {abv}% does not match expected {profile.abv_percent}%.",
                )
            )

    # 5. Verdict roll-up.
    if any(not r.passed for r in field_results.values()):
        verdict: Verdict = "FAIL"
    elif warnings:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return verdict, field_results, warnings


def is_compliant(field_results: dict[str, FieldResult]) -> bool:
    return all(r.passed for r in field_results.values())


def rule_catalog() -> list[RuleInfo]:
    return [RuleInfo(code=c, severity=s, description=d) for c, s, d in RULE_CATALOG]

"""Single, deterministic compliance engine — the one source of truth.

No AI here. Given the extracted fields (plus OCR confidence and an optional
expected `ApplicationData` from the COLA application), it returns:

  - verdict:          PASS / WARN / FAIL
  - field_results:    per-field {status, reason, extracted, expected}
  - warnings:         non-field soft findings (e.g. low OCR confidence)

Two validation modes, combined per field:
  1. Presence/format  — is a required field present? is ABV numeric & in range?
  2. Comparison       — when the application supplies an expected value, does the
                        label match it? Exact → PASS; minor formatting/case/
                        punctuation difference → WARN (judgment, e.g. the
                        "STONE'S THROW" apostrophe case); substantive → FAIL.

The government warning is always checked strictly, word-for-word, against the
mandated statement.
"""
from __future__ import annotations

import difflib
import re
from typing import Optional

from app.schemas import (
    ApplicationData,
    FieldResult,
    Finding,
    LabelExtraction,
    RuleInfo,
    Verdict,
)

# The full mandated government warning (27 CFR 16.21).
CANONICAL_GOV_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)

# Fields required to be present on the label (independent of the application).
REQUIRED_FIELDS: list[tuple[str, str]] = [
    ("brand_name", "Brand name"),
    ("class_type", "Class / type"),
    ("net_contents", "Net contents"),
    ("bottler_name", "Bottler name"),
    ("bottler_address", "Bottler address"),
]
# Optional presence (only failed when the application expects a value).
OPTIONAL_FIELDS: list[tuple[str, str]] = [("country_of_origin", "Country of origin")]

# Similarity thresholds for fuzzy comparison.
_WARN_SIMILARITY = 0.85          # extracted vs expected: minor difference -> WARN
_WARN_WARNING_SIMILARITY = 0.90  # gov warning near-match -> WARN

RULE_CATALOG: list[tuple[str, str, str]] = [
    ("GOVERNMENT_WARNING", "error", 'Government warning must match the mandated statement word-for-word.'),
    ("ABV", "error", "ABV must be present, numeric, and between 0 and 100."),
    ("REQUIRED_FIELD", "error", "Brand, class/type, net contents, and bottler name/address must be present."),
    ("FIELD_MISMATCH", "error", "A field does not match the value on the application."),
    ("MINOR_MISMATCH", "warn", "A field differs from the application only in formatting/case/punctuation."),
    ("LOW_OCR_CONFIDENCE", "warn", "OCR confidence is low; results may be unreliable."),
]


def _ok(**kw) -> FieldResult:
    return FieldResult(status="pass", **kw)


def _warn(reason: str, **kw) -> FieldResult:
    return FieldResult(status="warn", reason=reason, **kw)


def _fail(reason: str, **kw) -> FieldResult:
    return FieldResult(status="fail", reason=reason, **kw)


def _collapse_ws(s: Optional[str]) -> str:
    """Trim and collapse internal whitespace (OCR/label spacing is noisy)."""
    return re.sub(r"\s+", " ", (s or "").strip())


def _loose(s: Optional[str]) -> str:
    """Case/punctuation-insensitive form for fuzzy comparison."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_government_warning(extracted: Optional[str]) -> FieldResult:
    """Strict word-for-word check against the mandated statement."""
    canonical = CANONICAL_GOV_WARNING
    if not extracted or not extracted.strip():
        return _fail("Government warning not found on the label.", expected=canonical)

    ext_ws, can_ws = _collapse_ws(extracted), _collapse_ws(canonical)
    # Exact (whitespace-normalized only): correct wording, caps, punctuation.
    if ext_ws == can_ws:
        return _ok(extracted=ext_ws, expected=canonical)

    ext_loose, can_loose = _loose(extracted), _loose(canonical)
    # Same words, but case/punctuation/spacing differs -> formatting WARN.
    if ext_loose == can_loose:
        return _warn(
            "Warning wording is correct but capitalization/punctuation differs "
            "from the required statement (must be exact).",
            extracted=ext_ws,
            expected=canonical,
        )
    # Very close -> likely OCR noise or a small omission; flag for human review.
    if _similarity(ext_loose, can_loose) >= _WARN_WARNING_SIMILARITY:
        return _warn(
            "Warning nearly matches the required statement; verify wording exactly.",
            extracted=ext_ws,
            expected=canonical,
        )
    return _fail(
        "Government warning does not match the required statement.",
        extracted=ext_ws,
        expected=canonical,
    )


def _compare_text(extracted: Optional[str], expected: Optional[str], label: str) -> FieldResult:
    """Compare a text field to the application (when expected is provided)."""
    ext = _collapse_ws(extracted)
    if not ext:
        return _fail(f"{label} is missing from the label.", expected=expected)

    if expected is None or not str(expected).strip():
        # No expected value — presence is enough.
        return _ok(extracted=ext)

    exp = _collapse_ws(str(expected))
    if ext == exp:
        return _ok(extracted=ext, expected=exp)
    if _loose(ext) == _loose(exp):
        return _warn(
            f"{label} matches the application except for case/spacing/punctuation.",
            extracted=ext,
            expected=exp,
        )
    if _similarity(_loose(ext), _loose(exp)) >= _WARN_SIMILARITY:
        return _warn(
            f"{label} differs slightly from the application (‘{ext}’ vs ‘{exp}’).",
            extracted=ext,
            expected=exp,
        )
    return _fail(
        f"{label} does not match the application (‘{ext}’ vs ‘{exp}’).",
        extracted=ext,
        expected=exp,
    )


def _check_abv(extracted: Optional[float], expected: Optional[float]) -> FieldResult:
    ext_str = None if extracted is None else f"{extracted}%"
    exp_str = None if expected is None else f"{expected}%"
    if extracted is None:
        return _fail("ABV is missing from the label.", expected=exp_str)
    if not _is_number(extracted):
        return _fail("ABV is not numeric.", extracted=ext_str, expected=exp_str)
    if not (0 < extracted < 100):
        return _fail(f"ABV {extracted}% is not between 0 and 100.", extracted=ext_str)
    if expected is None:
        return _ok(extracted=ext_str)
    diff = abs(extracted - expected)
    if diff == 0:
        return _ok(extracted=ext_str, expected=exp_str)
    if diff <= 0.3:  # within typical TTB tolerance
        return _ok(extracted=ext_str, expected=exp_str)
    if diff <= 1.0:
        return _warn(
            f"ABV {extracted}% is close to but differs from the application {expected}%.",
            extracted=ext_str,
            expected=exp_str,
        )
    return _fail(
        f"ABV {extracted}% does not match the application {expected}%.",
        extracted=ext_str,
        expected=exp_str,
    )


def validate_label(
    fields: LabelExtraction,
    ocr_confidence: float = 100.0,
    application: Optional[ApplicationData] = None,
    ocr_threshold: float = 55.0,
) -> tuple[Verdict, dict[str, FieldResult], list[Finding]]:
    """Run all rules. Returns (verdict, field_results, warnings)."""
    app = application or ApplicationData()
    results: dict[str, FieldResult] = {}

    # Government warning — always strict.
    results["government_warning"] = check_government_warning(fields.government_warning_text)

    # ABV.
    results["abv"] = _check_abv(fields.abv, app.abv)

    # Required text fields (presence + optional comparison).
    for key, label in REQUIRED_FIELDS:
        results[key] = _compare_text(getattr(fields, key), getattr(app, key), label)

    # Optional text fields: only checked when the application expects a value,
    # or reported as informational when present.
    for key, label in OPTIONAL_FIELDS:
        extracted = getattr(fields, key)
        expected = getattr(app, key)
        if expected:
            results[key] = _compare_text(extracted, expected, label)
        elif _collapse_ws(extracted):
            results[key] = _ok(extracted=_collapse_ws(extracted))
        else:
            # Absent optional field -> neutral "info", not a green PASS.
            results[key] = FieldResult(
                status="info", reason="Not stated (optional — required only for imports)."
            )

    # Soft warnings.
    warnings: list[Finding] = []
    if ocr_confidence < ocr_threshold:
        warnings.append(
            Finding(
                code="LOW_OCR_CONFIDENCE",
                severity="warn",
                message=(
                    f"OCR confidence {ocr_confidence:.0f} is below {ocr_threshold:.0f}; "
                    "results may be unreliable — consider a clearer photo."
                ),
            )
        )

    # Low-quality image: a field we simply couldn't read shouldn't be reported
    # the same as a genuinely non-compliant one. Downgrade "missing" fails to a
    # "couldn't read" warning so the label goes to human review, not rejection.
    # (Only applies in OCR mode, where a confidence signal exists.)
    if ocr_confidence < ocr_threshold:
        for key, res in results.items():
            if res.status == "fail" and res.extracted is None:
                results[key] = FieldResult(
                    status="warn",
                    reason=(
                        "Could not read this field — the image may be low quality; "
                        "retry with a clearer, straight-on photo."
                    ),
                    expected=res.expected,
                )

    # Verdict roll-up: any fail -> FAIL; else any warn (field or soft) -> WARN.
    statuses = [r.status for r in results.values()]
    if "fail" in statuses:
        verdict: Verdict = "FAIL"
    elif "warn" in statuses or warnings:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return verdict, results, warnings


def is_compliant(results: dict[str, FieldResult]) -> bool:
    # "info" (optional & absent) is neutral — doesn't break compliance.
    return all(r.status in ("pass", "info") for r in results.values())


def rule_catalog() -> list[RuleInfo]:
    return [RuleInfo(code=c, severity=s, description=d) for c, s, d in RULE_CATALOG]

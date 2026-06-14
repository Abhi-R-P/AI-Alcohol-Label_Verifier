"""Runs every rule and rolls findings up into a verdict."""
from __future__ import annotations

from typing import Optional

from app.rules.checks import ALL_RULES, RULE_CATALOG
from app.schemas import Finding, LabelExtraction, Profile, RuleInfo, Verdict


def evaluate(
    extraction: LabelExtraction,
    ocr_confidence: float,
    profile: Optional[Profile] = None,
) -> tuple[Verdict, list[Finding]]:
    """Apply all rules and return (verdict, findings).

    Verdict roll-up: any `error` -> FAIL; else any `warn` -> WARN; else PASS.
    """
    findings = [
        finding
        for rule in ALL_RULES
        if (finding := rule(extraction, ocr_confidence, profile)) is not None
    ]

    if any(f.severity == "error" for f in findings):
        verdict: Verdict = "FAIL"
    elif any(f.severity == "warn" for f in findings):
        verdict = "WARN"
    else:
        verdict = "PASS"

    return verdict, findings


def rule_catalog() -> list[RuleInfo]:
    """The active rule catalog, for GET /rules and the UI legend."""
    return [
        RuleInfo(code=code, severity=severity, description=desc)
        for code, severity, desc in RULE_CATALOG
    ]

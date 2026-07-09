# Deployed-app run (vision mode) — measured results

A real run of the live app (`EXTRACTION_MODE=vision`) over 7 labels. All results
reported `OCR confidence 100`, confirming vision mode. Captured 2026-07-08.

## Latency (per label)

| stat | seconds |
|---|---|
| min | 1.7 |
| median | 2.5 |
| mean | 2.4 |
| max | 2.8 |

All 7 labels completed in ≈2–3s — comfortably under the ≤5s target.

## Verdicts

| label | verdict | time (s) | note |
|---|---|---|---|
| ABC Distillery Bourbon | PASS | 2.3 | all 8 fields + full warning extracted correctly |
| (mock, no warning) | FAIL (2) | 2.7 | warning + ABV absent |
| (photo) | FAIL (3) | 2.6 | warning, ABV, bottler name absent |
| Malt & Hop Grape Ale | FAIL (1) | 2.5 | warning all-caps → **WARN** (strict check); ABV absent |
| Generic Vodka | FAIL (2) | 1.7 | warning + bottler address absent (ABV read = 40.0%) |
| Generic Whiskey | FAIL (2) | 2.1 | warning + ABV absent |
| Hawk's Shadow Orange Muscat | FAIL | 2.8 | real wine label — investigate which field failed |

## Observations

- Vision mode extracts a compliant real label fully and correctly (ABC Bourbon → PASS).
- The strict government-warning check correctly downgrades an all-caps rendering to
  WARN ("wording correct but capitalization/punctuation differs — must be exact").
- Adversarial/garbled labels correctly FAIL (no hallucinated PASS).
- Placeholder guard confirmed — no `<UNKNOWN>` false-passes.

## Follow-ups

- `Hawk's Shadow` (a likely-compliant wine) FAILed; confirm whether it's a genuine
  missing field (e.g. net contents not visible) or a vision miss (false negative).
- Independent ground truth for these exact 7 files was not available, so this
  records measured latency + observed behavior, not a field-accuracy percentage.
  Use `eval/real/` with ground truth for accuracy numbers.

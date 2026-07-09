# Extraction eval

Measures how accurately fields are extracted, and compares the two extraction
strategies: **OCR → Claude (text)** vs. **Claude vision (image)**.

## Why

The app extracts fields via OCR-then-Claude by default. This harness quantifies
that choice — field-level accuracy and latency — and lets you compare it against
sending the image straight to Claude's vision model, so the architecture decision
is evidence-based rather than assumed.

## Dataset

`ground_truth.csv` defines a small set of labels with known field values.
`generate_samples.py` renders them into deterministic PNGs (`samples/`) so the
eval is reproducible anywhere without shipping image binaries. These are clean
rendered labels; real-world photos (glare, angle, blur) are the natural harder
next set — drop them in `samples/` and add matching `ground_truth.csv` rows.

## Run

From `backend/` (needs `ANTHROPIC_API_KEY`; OCR mode also needs Tesseract):

```bash
python eval/generate_samples.py     # create samples/ from ground_truth.csv
python eval/run_eval.py             # both modes  (or: --mode ocr | --mode vision)
```

Output: a per-field accuracy table + median latency for each mode, and a
side-by-side comparison, written to `results/latest.md` and printed.

## Scoring

`scoring.py` (pure, unit-tested in `tests/test_eval_scoring.py`): text fields
match after case/whitespace/punctuation normalization or ≥90% similarity; ABV
within ±0.3; a field that should be absent matches only when extracted as null.

## Notes

- `samples/` and `results/` are gitignored (regenerated locally).
- Cost: OCR mode sends only text; vision mode sends the image (more input tokens
  per call) — read exact token usage from the Anthropic console for a $ figure.

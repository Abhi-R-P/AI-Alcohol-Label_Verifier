# Real-photo eval set

Real / real-looking label images for a harder eval than the synthetic renders.
Ground truth (`ground_truth.csv`) was transcribed by reading each image.

## The images (save them here with these exact filenames)

| filename | what it is | expected |
|---|---|---|
| `abc_bourbon.jpg` | Clean bourbon mockup (front + back), correct government warning | should verify cleanly (**PASS**) |
| `hawks_shadow.jpg` | Real winery label (Hawk's Shadow Orange Muscat), correct warning | good real-world test; note the **apostrophe** in "Hawk's" and that net contents may be absent in the crop |
| `rudrebison_walls.jpg` | AI-generated, gibberish text, no valid warning | **negative control — must NOT pass** (FAIL) |
| `chluni_mays.jpg` | AI-generated, gibberish | **negative control** (FAIL) |
| `spnetler.jpg` | AI-generated, gibberish | **negative control** (FAIL) |

The image files are gitignored (they're external assets) — only this ground truth
is committed. Drop the five images into this folder before running.

## Run

From `backend/` (needs `ANTHROPIC_API_KEY`; OCR mode also needs Tesseract):

```bash
python eval/run_eval.py --samples-dir real/real --truth real/ground_truth.csv
# (or --mode vision / --mode ocr)
```

Wait — the image dir and the CSV both live in `eval/real/`, so:

```bash
python eval/run_eval.py --samples-dir real --truth real/ground_truth.csv
```

Output: per-field accuracy + median latency for OCR vs. vision, written to
`eval/results/latest.md`.

## Reading the numbers

- The 2 legitimate labels drive **field extraction accuracy**.
- The 3 AI-garbled images are **hallucination checks**: a good result returns
  `null` for their fields (matching the blank ground truth) and never PASSes —
  extracting confident-looking values from gibberish is the failure mode to catch.
- Expect **vision** mode to outperform **ocr** on the photographed/curved labels.

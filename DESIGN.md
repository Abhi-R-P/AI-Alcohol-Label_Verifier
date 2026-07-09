# AI Alcohol Label Verifier — MVP Architecture

> Scope: 48-hour build. No auth, no database. Batch image upload via a simple
> loop (no async job queue). Target latency ≤ 5s per image.

## 1. Overview

A user uploads one or more photos of an alcohol product label. For each image the
system runs OCR to lift raw text, sends that text to the Claude API for
**structured field extraction**, and then runs a
**deterministic rule-based validation layer** that flags compliance issues
(missing government warning, ABV out of range, net contents missing, etc.).

The frontend shows a per-image verdict: `PASS`, `WARN`, or `FAIL` with itemized findings.

## 2. Architecture Diagram (text)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Browser (User)                                │
│                                                                            │
│   Next.js App (App Router)                                                 │
│   ┌──────────────┐   ┌──────────────┐   ┌────────────────────────────┐    │
│   │ Upload Form  │   │ Results Grid │   │ Per-image Findings Panel   │    │
│   │ (multi-file) │   │ PASS/WARN/   │   │ (extracted fields + rules) │    │
│   └──────┬───────┘   │   FAIL chips │   └────────────────────────────┘    │
│          │           └──────────────┘                                      │
└──────────┼─────────────────────────────────────────────────────────────  ┘
           │  multipart/form-data  (POST /verify · single: POST /upload-label)
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend (Python)                           │
│                                                                            │
│   /verify  ──►  for each image (simple loop):                              │
│                                                                            │
│      ┌───────────┐   ┌────────────┐   ┌──────────────┐   ┌─────────────┐  │
│      │ 1. Decode │──►│ 2. OCR     │──►│ 3. Claude    │──►│ 4. Rule     │  │
│      │  & resize │   │ (Tesseract │   │  Extraction  │   │  Validation │  │
│      │           │   │  / vision) │   │  (structured │   │  (pure      │  │
│      │           │   │            │   │   JSON)      │   │   Python)   │  │
│      └───────────┘   └────────────┘   └──────┬───────┘   └──────┬──────┘  │
│                                              │                  │         │
│                                       Anthropic API   rules/validate.py    │
│                                       (claude-haiku-4-5)                   │
│                                                                            │
│   Aggregate per-image results ──► JSON response                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Why this shape
- **OCR before Claude** keeps the LLM input small (text, not raw image bytes),
  which lowers token cost and latency and keeps extraction deterministic-ish.
  (Claude vision on the raw image is a possible future fallback for low-confidence
  OCR — not implemented; see §7.)
- **Rules stay out of the LLM.** Compliance logic is deterministic, auditable,
  and testable. Claude only *extracts*; it never *decides* pass/fail.

## 3. Request Flow

1. User selects one or more images in the Next.js page (drag-and-drop or browse)
   and submits.
2. Frontend posts `multipart/form-data`: a single image → `POST /upload-label`;
   multiple → `POST /verify`. Both accept optional expected COLA values — an
   `application` JSON (applied to all) or, for batch, a `csv_file` mapping
   `filename` → expected fields.
3. Backend reads/validates every upload, then processes images **concurrently**
   through a bounded worker pool (`BATCH_CONCURRENCY`, default 3) — each image:
   1. **Decode & normalize** — open with Pillow, auto-orient, downscale to a max
      edge (~1280px), grayscale. Bounds OCR cost.
   2. **OCR** — Tesseract (`pytesseract`) returns raw text + mean confidence.
   3. **Extract** — send the OCR text to Claude with a **forced tool call**,
      yielding schema-validated JSON for the full TTB field set: `brand_name`,
      `class_type`, `abv`, `net_contents`, `bottler_name`, `bottler_address`,
      `country_of_origin`, and `government_warning_text` (verbatim). A client
      timeout bounds latency; on timeout the image degrades to OCR-only with an
      `EXTRACTION_TIMEOUT` warning rather than failing.
   4. **Validate** — pass the fields (plus OCR confidence and any expected
      application data) through `rules/validate.py`, which returns a `verdict`, a
      per-field `{status, reason, extracted, expected}` map (`field_validation`),
      and soft `warnings`.
   5. Build `ImageResult{filename, verdict, fields, ocr_text, ocr_confidence,
      field_validation, findings, timings, error}`.
4. `/upload-label` returns one `ImageResult`; `/verify` returns
   `{ summary: {total, passed, warned, failed}, results: [...] }`.
5. Frontend renders a result card per image: overall PASS/WARN/FAIL plus the
   field-by-field checklist with extracted values and reasons.

Per-image latency budget (≤ 5s target):
`decode ~150ms · OCR ~0.5–1.2s · Claude (haiku) ~0.7–2s · rules <10ms` → typically under 5s.

## 4. Folder Structure

```
ai-alcohol-label-verifier/
├── DESIGN.md
├── README.md
├── DEPLOY.md                         # Render/Railway + Vercel deploy guide
├── render.yaml                       # Render Blueprint (backend)
├── .github/workflows/
│   └── backend-tests.yml            # CI: runs the rule tests on push
│
├── frontend/                        # Next.js (App Router, TS, Tailwind)
│   ├── app/
│   │   ├── page.tsx                  # upload (drag-drop) + results view
│   │   ├── layout.tsx
│   │   └── globals.css              # Tailwind directives
│   ├── components/
│   │   └── LabelResult.tsx          # per-image card: verdict + field checklist
│   ├── lib/
│   │   ├── api.ts                    # fetch wrapper -> /upload-label, /verify
│   │   └── types.ts                  # mirrors backend schemas
│   ├── public/                       # static assets (e.g. logo.png)
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── next.config.js
│
└── backend/                         # FastAPI (Python)
    ├── app/
    │   ├── main.py                   # FastAPI app, CORS, routes
    │   ├── config.py                 # env: ANTHROPIC_API_KEY, model, limits
    │   ├── schemas.py                # Pydantic: ImageResult, FieldResult, Finding, Profile
    │   ├── pipeline.py               # orchestrates per-image steps (the loop)
    │   ├── services/
    │   │   ├── image.py              # decode, orient, resize, grayscale
    │   │   ├── ocr.py                # Tesseract wrapper -> text + confidence
    │   │   └── extract.py            # Claude structured extraction (forced tool)
    │   └── rules/
    │       └── validate.py           # unified engine: verdict + per-field results + warnings
    ├── tests/                        # rule/validation + eval-scoring unit tests
    ├── eval/                         # accuracy harness: OCR vs vision
    │   ├── ground_truth.csv · generate_samples.py · run_eval.py · scoring.py
    ├── Dockerfile                    # installs tesseract-ocr; binds $PORT
    ├── requirements.txt
    ├── pytest.ini
    └── .env.example
```

## 5. Key Endpoints

### `POST /upload-label` — single image
`multipart/form-data` with one `file`. Returns a single `ImageResult` (the same
object shape as one entry in `/verify`'s `results`).

### `POST /verify` — batch
`multipart/form-data`.

| field        | type             | notes                                     |
|--------------|------------------|-------------------------------------------|
| `files`      | file[] (1..N)    | JPEG/PNG/WebP; server caps count & size   |
| `application`| JSON string opt. | expected values, applied to all images    |
| `csv_file`   | file opt.        | per-image expected values, keyed by `filename` |

Response `200`:
```json
{
  "summary": { "total": 1, "passed": 0, "warned": 0, "failed": 1 },
  "results": [
    {
      "filename": "label1.jpg",
      "verdict": "FAIL",
      "fields": {
        "brand_name": "Old Mill IPA",
        "class_type": "IPA",
        "abv": 6.5,
        "net_contents": null,
        "bottler_name": "Old Mill Brewing Co.",
        "bottler_address": "Portland, OR",
        "country_of_origin": "USA",
        "government_warning_text": "GOVERNMENT WARNING: (1) According to..."
      },
      "ocr_text": "OLD MILL IPA ... ALC 6.5% BY VOL ...",
      "ocr_confidence": 88.0,
      "field_validation": {
        "government_warning": { "status": "pass", "reason": null, "extracted": "GOVERNMENT WARNING: ...", "expected": "GOVERNMENT WARNING: ..." },
        "brand_name": { "status": "warn", "reason": "Matches the application except for case/spacing/punctuation.", "extracted": "Old Mill IPA", "expected": "OLD MILL IPA" },
        "net_contents": { "status": "fail", "reason": "Net contents is missing from the label.", "extracted": null, "expected": null }
      },
      "findings": [],
      "timings": { "ocr_ms": 740, "claude_ms": 1320, "rules_ms": 2, "total_ms": 2100 },
      "error": null
    }
  ]
}
```

### `GET /healthz` — liveness/readiness (checks Tesseract + API key presence).

### `GET /rules` — returns the active rule catalog (code, severity, description).
Lets the frontend render a legend and makes the validation layer self-documenting.

## 6. The Two AI / Logic Boundaries

**Claude extraction (`services/extract.py`)** — `claude-haiku-4-5` by default
(fastest tier, for the ≤5s budget; `claude-sonnet-4-6` / `claude-opus-4-8`
configurable via `EXTRACTION_MODEL`). A **forced tool call** (`tool_choice`) whose
input schema is the full TTB field set yields schema-validated JSON in a single
call — including the government-warning statement copied **verbatim** for the
strict check. Claude only reports what the label says; it never judges compliance.

**Rule engine (`rules/validate.py`)** — pure Python, deterministic, unit-tested.
`validate_label()` returns the verdict and a per-field `{status, reason,
extracted, expected}` map (three-state: pass / warn / fail):
- **Government warning** — matched word-for-word against the canonical 27 CFR
  statement: exact → pass; correct wording but case/punctuation differs → warn;
  substantively different or absent → fail.
- **ABV** — numeric and 0–100; when the application supplies an expected value,
  compared within tolerance (≤0.3 pass, ≤1.0 warn, else fail).
- **Required fields** (brand, class/type, net contents, bottler name/address) —
  must be present; when expected values are supplied, compared with **fuzzy
  judgment** (exact → pass, minor formatting/case/apostrophe difference → warn,
  substantive mismatch → fail). Country of origin is optional.
- **Soft warnings** (→ warn): `LOW_OCR_CONFIDENCE`.

Verdict roll-up: any field `fail` → FAIL; else any `warn` → WARN; else PASS.

## 7. Trade-offs & Notes (MVP-honest)

- **Bounded-concurrency batch.** Images are processed via `asyncio.gather` over a
  bounded worker pool (`BATCH_CONCURRENCY`, default 3; each `process_image` runs
  in a threadpool since OCR + the Claude client are blocking). Concurrency is
  capped rather than unbounded to protect memory on small hosts — a deliberate
  middle ground between a naive sequential loop and a full async job queue.
- **No DB/auth** → results live only in the response; nothing persisted. Acceptable
  for MVP demo.
- **OCR vs. vision (both implemented).** `EXTRACTION_MODE=vision` (default) sends
  the image directly to a multimodal model — most robust on real photos;
  `EXTRACTION_MODE=ocr` sends Tesseract text (cheaper on clean scans).
  `backend/eval/` measures accuracy + latency for both.
- **Low-confidence handling (OCR mode).** When OCR mean confidence is below
  threshold, a field that couldn't be read is reported as a "couldn't read —
  retry" **WARN** rather than a hard FAIL, so a blurry photo goes to human review
  instead of being rejected like a genuinely non-compliant label. (Vision mode
  has no OCR-confidence proxy, so this applies to OCR mode.)
- **Placeholder guard.** Extracted placeholder strings (`<UNKNOWN>`, `N/A`, …)
  are normalized to null so they can't pass a presence check as real values.
- **Latency guard (implemented).** An Anthropic client timeout (~4s,
  `EXTRACTION_TIMEOUT_S`) plus a low `max_tokens` protect the 5s budget; on
  timeout the image degrades to OCR-only with an `EXTRACTION_TIMEOUT` warning
  rather than failing. Extraction errors never 500 — they become a result.
- **Limits/validation (implemented).** FastAPI enforces max file count, max file
  size, allowed content types, and rejects empty files before any work.

## 8. Minimal Dependencies

- **Frontend:** `next`, `react`, `typescript`. No state library needed.
- **Backend:** `fastapi`, `uvicorn`, `python-multipart`, `pillow`, `pytesseract`
  (+ system `tesseract-ocr`), `anthropic`, `pydantic`, `pytest`.

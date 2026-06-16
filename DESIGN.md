# AI Alcohol Label Verifier — MVP Architecture

> Scope: 48-hour build. No auth, no database. Batch image upload via a simple
> loop (no async job queue). Target latency ≤ 5s per image.

## 1. Overview

A user uploads one or more photos of an alcohol product label. For each image the
system runs OCR to lift raw text, sends that text (plus a target product profile)
to the Claude API for **structured field extraction**, and then runs a
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
   multiple → `POST /verify` (with an optional `profile` field carrying expected
   brand / ABV / net-contents to validate against). Both run the same per-image
   pipeline below.
3. Backend processes each `UploadFile` (a simple sequential loop for `/verify`):
   1. **Decode & normalize** — open with Pillow, auto-orient, downscale to a max
      edge (~1280px), grayscale. Bounds OCR cost.
   2. **OCR** — Tesseract (`pytesseract`) returns raw text + mean confidence.
   3. **Extract** — send the OCR text to Claude with a **forced tool call** whose
      input schema is the six fields, yielding schema-validated JSON. Returns
      typed values: `brand_name`, `class_type`, `abv`, `net_contents`,
      `producer`, `government_warning` (null when absent; no per-field confidence).
      A client timeout bounds latency; on timeout the image degrades to OCR-only
      with an `EXTRACTION_TIMEOUT` warning rather than failing.
   4. **Validate** — pass the fields (plus OCR text, OCR confidence, profile)
      through `rules/validate.py`, which returns a `verdict`, a per-field
      `{passed, reason}` map (`field_validation`), and soft `warnings`.
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
    ├── tests/
    │   ├── test_rules.py             # verdict roll-up + soft warnings
    │   └── test_validate.py          # per-field validation
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

| field     | type             | notes                                     |
|-----------|------------------|-------------------------------------------|
| `files`   | file[] (1..N)    | JPEG/PNG/WebP; server caps count & size   |
| `profile` | JSON string opt. | expected `{brand_name, abv_percent, net_contents, region}` |

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
        "producer": "Old Mill Brewing Co.",
        "government_warning": true
      },
      "ocr_text": "OLD MILL IPA ... ALC 6.5% BY VOL ...",
      "ocr_confidence": 88.0,
      "field_validation": {
        "government_warning": { "passed": true, "reason": null },
        "abv": { "passed": true, "reason": null },
        "brand_name": { "passed": true, "reason": null },
        "class_type": { "passed": true, "reason": null },
        "net_contents": { "passed": false, "reason": "Net contents is missing." },
        "producer": { "passed": true, "reason": null }
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
input schema is the six fields yields schema-validated JSON in a single call.
System prompt: "You extract fields from OCR'd alcohol label text. Set a field to
null when absent. Do not infer values or judge regulatory compliance."

**Rule engine (`rules/validate.py`)** — pure Python, deterministic, unit-tested.
A single `validate_label()` returns the verdict, a per-field `{passed, reason}`
map, and soft warnings:
- Hard field rules (a failure → `FAIL`): `GOVERNMENT_WARNING` (literal
  "GOVERNMENT WARNING:" present in OCR text), `ABV` (numeric and 0–100),
  `REQUIRED_FIELD` (brand, class/type, net contents, producer present).
- Soft warnings (→ `WARN`): `LOW_OCR_CONFIDENCE`, `BRAND_MISMATCH`,
  `ABV_MISMATCH` (the last two only when a `profile` is supplied).

Verdict roll-up: any failed field → `FAIL`; else any warning → `WARN`; else `PASS`.

## 7. Trade-offs & Notes (MVP-honest)

- **Batch = synchronous loop.** N images are processed sequentially in one
  request. Simple and adequate for small batches. Risk: large batches blow the
  per-request time → cap N (e.g. 10) and surface that in the UI. (Easy follow-up:
  process the loop with a bounded `asyncio.gather` over the Claude calls — same
  code shape, no queue/DB.)
- **No DB/auth** → results live only in the response; nothing persisted. Acceptable
  for MVP demo.
- **OCR fallback (future, not implemented).** If Tesseract confidence is very
  low, a future version could send the resized image directly to Claude vision
  instead of OCR text. Currently a low-confidence read is surfaced as a
  `LOW_OCR_CONFIDENCE` warning instead.
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

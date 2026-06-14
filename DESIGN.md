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
           │  multipart/form-data  (POST /api/verify)
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
│                                       Anthropic API      rules/*.py       │
│                                       (claude-sonnet-4-6)                  │
│                                                                            │
│   Aggregate per-image results ──► JSON response                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Why this shape
- **OCR before Claude** keeps the LLM input small (text, not raw image bytes),
  which lowers token cost and latency and keeps extraction deterministic-ish.
  Claude's vision can read the label directly — kept as a fallback path for
  low-confidence OCR (see §7).
- **Rules stay out of the LLM.** Compliance logic is deterministic, auditable,
  and testable. Claude only *extracts*; it never *decides* pass/fail.

## 3. Request Flow

1. User selects N images in the Next.js upload form and submits.
2. Frontend POSTs `multipart/form-data` to FastAPI `POST /verify` (one request,
   N files). An optional `profile` field carries expected values (brand, ABV,
   volume) to validate against.
3. Backend loops over each `UploadFile`:
   1. **Decode & normalize** — open with Pillow, auto-orient, downscale to a max
      edge (~1600px), grayscale. Bounds the OCR + upload cost.
   2. **OCR** — Tesseract (`pytesseract`) returns raw text + mean confidence.
   3. **Extract** — send raw text to Claude with a strict JSON schema (tool/
      structured output). Returns typed fields: `brand_name`, `abv_percent`,
      `net_contents`, `government_warning_present`, `country_of_origin`,
      `producer`, etc., each with a `found`/`confidence` marker.
   4. **Validate** — pass extracted fields through `rules/` engine. Each rule
      yields a `Finding{code, severity, message}`.
   5. Build `ImageResult{filename, verdict, fields, findings, timings}`.
4. Backend returns `{ results: [...], summary: {...} }`.
5. Frontend renders a results grid; clicking a card opens the findings panel.

Per-image latency budget (≤ 5s target):
`decode ~150ms · OCR ~600–1200ms · Claude ~1–2.5s · rules <10ms` → ~2–4s typical.

## 4. Folder Structure

```
ai-alcohol-label-verifier/
├── DESIGN.md
├── README.md
│
├── frontend/                        # Next.js (App Router, TS)
│   ├── app/
│   │   ├── page.tsx                  # upload + results view
│   │   └── layout.tsx
│   ├── components/
│   │   ├── UploadForm.tsx            # multi-file picker + submit
│   │   ├── ResultsGrid.tsx          # PASS/WARN/FAIL cards
│   │   └── FindingsPanel.tsx        # extracted fields + rule findings
│   ├── lib/
│   │   └── api.ts                    # fetch wrapper -> /verify
│   ├── package.json
│   └── next.config.js
│
└── backend/                         # FastAPI (Python)
    ├── app/
    │   ├── main.py                   # FastAPI app, CORS, routes
    │   ├── config.py                 # env: ANTHROPIC_API_KEY, limits
    │   ├── schemas.py                # Pydantic: ImageResult, Finding, Profile
    │   ├── pipeline.py               # orchestrates per-image steps (the loop)
    │   ├── services/
    │   │   ├── image.py              # decode, orient, resize, grayscale
    │   │   ├── ocr.py                # Tesseract wrapper -> text + confidence
    │   │   └── extract.py            # Claude structured extraction
    │   └── rules/
    │       ├── engine.py             # runs all rules, computes verdict
    │       └── checks.py             # individual rule functions
    ├── tests/
    │   ├── test_rules.py             # deterministic — high value, fast
    │   └── fixtures/                 # sample OCR text + expected findings
    ├── requirements.txt
    └── .env.example
```

## 5. Key Endpoints

### `POST /verify`  — primary
Batch verify. `multipart/form-data`.

| field     | type             | notes                                     |
|-----------|------------------|-------------------------------------------|
| `files`   | file[] (1..N)    | JPEG/PNG; server caps count & size        |
| `profile` | JSON string opt. | expected `{brand_name, abv_percent, net_contents, region}` |

Response `200`:
```json
{
  "summary": { "total": 2, "pass": 1, "warn": 0, "fail": 1 },
  "results": [
    {
      "filename": "label1.jpg",
      "verdict": "FAIL",
      "fields": {
        "brand_name":  { "value": "Old Mill IPA", "confidence": 0.93 },
        "abv_percent": { "value": 6.5, "confidence": 0.88 },
        "net_contents":{ "value": null, "confidence": 0.0 },
        "government_warning_present": { "value": false, "confidence": 0.9 }
      },
      "findings": [
        { "code": "MISSING_GOV_WARNING", "severity": "error",
          "message": "Government health warning text not detected." },
        { "code": "MISSING_NET_CONTENTS", "severity": "error",
          "message": "Net contents / volume not found on label." }
      ],
      "timings_ms": { "ocr": 740, "claude": 1820, "rules": 3 }
    }
  ]
}
```

### `GET /healthz` — liveness/readiness (checks Tesseract + API key presence).

### `GET /rules` — returns the active rule catalog (code, severity, description).
Lets the frontend render a legend and makes the validation layer self-documenting.

## 6. The Two AI / Logic Boundaries

**Claude extraction (`services/extract.py`)** — `claude-sonnet-4-6` (fast + cheap
enough for ≤5s, strong structured output). Use **tool/structured output** so the
response is schema-validated JSON, not free text. System prompt: "You extract
fields from OCR'd alcohol label text. Return only the schema. If a field is not
present, set value=null and confidence=0. Do not infer regulatory compliance."

**Rule engine (`rules/`)** — pure Python, deterministic, unit-tested. Example rules:
- `MISSING_GOV_WARNING` (error) — government warning absent.
- `ABV_MISSING` / `ABV_OUT_OF_RANGE` (error/warn) — ABV absent or implausible (e.g. >0% & <100%; or mismatch vs `profile.abv_percent`).
- `MISSING_NET_CONTENTS` (error) — no volume statement.
- `BRAND_MISMATCH` (warn) — extracted brand ≠ `profile.brand_name`.
- `LOW_OCR_CONFIDENCE` (warn) — OCR mean confidence below threshold → suggests re-photo.

Verdict roll-up: any `error` → `FAIL`; else any `warn` → `WARN`; else `PASS`.

## 7. Trade-offs & Notes (MVP-honest)

- **Batch = synchronous loop.** N images are processed sequentially in one
  request. Simple and adequate for small batches. Risk: large batches blow the
  per-request time → cap N (e.g. 10) and surface that in the UI. (Easy follow-up:
  process the loop with a bounded `asyncio.gather` over the Claude calls — same
  code shape, no queue/DB.)
- **No DB/auth** → results live only in the response; nothing persisted. Acceptable
  for MVP demo.
- **OCR fallback.** If Tesseract confidence is very low, optionally send the
  (resized) image directly to Claude vision instead of OCR text. Costs more
  latency/tokens, so it's gated behind a confidence threshold, off by default.
- **Latency guard.** Set an Anthropic client timeout (~4s) and `max_tokens` low
  (a few hundred — output is a small JSON object) to protect the 5s budget;
  on timeout return the OCR fields with a `EXTRACTION_TIMEOUT` warn finding
  rather than failing the whole image.
- **Limits/validation.** Enforce max file size, max file count, and allowed MIME
  types in FastAPI before doing any work.

## 8. Minimal Dependencies

- **Frontend:** `next`, `react`, `typescript`. No state library needed.
- **Backend:** `fastapi`, `uvicorn`, `python-multipart`, `pillow`, `pytesseract`
  (+ system `tesseract-ocr`), `anthropic`, `pydantic`, `pytest`.

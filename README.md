# AI Alcohol Label Verifier

Batch-verify alcohol product labels. Each uploaded image is read by Claude
(vision by default, or OCR), structured into typed TTB fields, and checked
against a deterministic rule-based validation layer that returns a
`PASS` / `WARN` / `FAIL` verdict with per-field findings.

## Live demo

**https://ai-alcohol-label-verifier.vercel.app/**

The backend runs on a free tier that sleeps after ~15 min idle, so the *first*
request may take up to ~60s to wake, then it's fast (~2–3s/label). If the first
upload errors, retry once.

See [`DESIGN.md`](./DESIGN.md) for the architecture, request flow, and trade-offs,
and [`DEPLOY.md`](./DEPLOY.md) for deployment.

```
Next.js (upload + results)  ──POST /verify──▶  FastAPI
                                                 └ for each image:
                                                   decode → OCR (Tesseract)
                                                   → Claude extraction (structured JSON)
                                                   → rule engine → verdict
```

Claude only **extracts** fields; it never decides compliance. All pass/fail
logic lives in `backend/app/rules/` and is unit-tested.

## Features

- **Single and batch image uploads** — verify one label (`POST /upload-label`) or
  many concurrently in a single request (`POST /verify`).
- **OCR-based label extraction** — Tesseract reads the raw text off each image.
- **Claude-powered structured extraction** — the OCR text is turned into the full
  TTB field set: brand, class/type, ABV, net contents, bottler name, bottler
  address, country of origin, and the government-warning text (verbatim).
- **Deterministic rule-based validation** — a pure-Python engine checks each field.
- **Strict government-warning check** — the warning is matched **word-for-word**
  against the mandated 27 CFR statement (exact → PASS, formatting/case-only
  difference → WARN, otherwise FAIL).
- **Label-vs-application comparison** — supply expected COLA values (a form, or a
  CSV for batch) and each field is compared with **fuzzy judgment**: exact → PASS,
  minor formatting/apostrophe/case difference → WARN, substantive mismatch → FAIL.
- **PASS / WARN / FAIL verdicts** — a three-state roll-up, per field and per label.
- **Itemized findings** — per-field status, reason, and extracted-vs-expected
  values, plus soft warnings (e.g. low OCR confidence). Processing time is shown
  per label.

## Approach

The pipeline is a linear, inspectable sequence:

```
OCR  →  Claude extraction  →  Rule engine  →  Verdict
```

1. **OCR** lifts raw text from the image (with grayscale/resize preprocessing).
2. **Claude extraction** maps that noisy text into a strict, typed schema via a
   forced tool call — a single API call, no multi-step reasoning.
3. **Rule engine** applies deterministic checks to the extracted fields.
4. **Verdict** rolls the field results up into PASS / WARN / FAIL.

**Claude is used only for structured extraction — it never makes a compliance
decision.** The boundary is deliberate: extracting fields from messy OCR is a
fuzzy, language-shaped task an LLM is well suited to, whereas a compliance
verdict must be **auditable, reproducible, and explainable**. Deterministic
validation gives identical output for identical input, is unit-testable, and lets
every PASS/FAIL be traced to a specific rule — properties a regulatory workflow
needs and that a non-deterministic model can't guarantee.

## Tools Used

- **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS.
- **Backend:** FastAPI, Uvicorn, Pydantic (Python 3.11).
- **OCR:** Tesseract via `pytesseract`, with Pillow for image preprocessing.
- **AI model:** Anthropic Claude (`claude-haiku-4-5` by default for latency;
  `claude-sonnet-4-6` / `claude-opus-4-8` configurable), using tool-use for
  schema-constrained output.
- **Testing & CI:** `pytest`, with a GitHub Actions workflow running the rule tests.
- **Deployment:** Docker (backend) on Render, Vercel (frontend).

## Layout

- `backend/` — FastAPI service (`app/`), pipeline, rule engine, tests.
- `frontend/` — Next.js App Router UI.

## Backend

Requires Python 3.10+ and the `tesseract-ocr` system package.

```bash
# Install Tesseract (Debian/Ubuntu)
sudo apt-get install -y tesseract-ocr

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set ANTHROPIC_API_KEY

uvicorn app.main:app --reload --port 8000
```

Endpoints:
- `POST /upload-label` — `multipart/form-data`: a single `file` + optional
  `application` (JSON of expected values); returns one result.
- `POST /verify` — `multipart/form-data`: `files` (1..N images) + optional
  `application` (JSON, applied to all) or `csv_file` (per-image expected values,
  keyed by a `filename` column). Images are processed concurrently.
- `GET /rules` — the active rule catalog.
- `GET /healthz` — checks Tesseract + API key.

Run the rule tests (no network / API key needed):

```bash
cd backend && pip install pydantic pytest && python -m pytest
```

## Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE defaults to http://localhost:8000
npm run dev                        # http://localhost:3000
```

## Environment variables

**Backend** (`backend/.env`):
- `ANTHROPIC_API_KEY` — **required**. Your Claude API key.
- `CORS_ORIGINS` — required in production. Allowed frontend origin(s), comma-separated.
- `EXTRACTION_MODE` — optional, default `vision` (`vision` | `ocr`).
- `EXTRACTION_MODEL` — optional, default `claude-haiku-4-5`.

**Frontend** (`frontend/.env.local`):
- `NEXT_PUBLIC_API_BASE` — **required**. Backend URL (default `http://localhost:8000`). Build-time.

## Model & extraction mode

Extraction defaults to `claude-haiku-4-5` to keep per-image latency under the
~5s target. For higher accuracy at the cost of latency, set
`EXTRACTION_MODEL=claude-sonnet-4-6` (or `claude-opus-4-8`) in `backend/.env`.

Two extraction strategies are supported via `EXTRACTION_MODE`:
- `vision` (default) — the image is sent directly to Claude's vision model (no
  OCR). Most robust on real-world photos (angles, glare, stylized/curved labels).
- `ocr` — Tesseract lifts text, Claude structures it. Cheaper for clean scans;
  also emits an OCR-confidence signal that, when low, downgrades unreadable fields
  to a "couldn't read — retry" WARN rather than a hard FAIL.

See [`backend/eval/`](./backend/eval/README.md) for a harness that measures
field-level accuracy and latency and **compares the two modes** head-to-head.

## Evaluation

`backend/eval/` contains a reproducible harness: a small ground-truth dataset,
a synthetic sample generator, and a runner that reports per-field accuracy and
median latency for OCR vs. vision extraction. Run from `backend/`:

```bash
python eval/generate_samples.py    # render labeled samples
python eval/run_eval.py            # OCR vs vision -> results/latest.md
```

The scoring logic is pure and unit-tested (`tests/test_eval_scoring.py`).

**Measured performance:** a live run over 7 labels (vision mode) completed in
1.7–2.8s each (median 2.5s) — under the ≤5s target with ~2× headroom. See
[`backend/eval/deployed-run.md`](./backend/eval/deployed-run.md).

## Assumptions & Tradeoffs

- **Prototype scope vs. full TTB compliance** — implements the core checks
  (strict government warning, ABV presence/range/tolerance, required-field
  presence, and label-vs-application matching), not the complete 27 CFR ruleset
  (e.g. class-specific ABV tolerances, standards of fill). Built to extend.
- **Bounded-concurrency batch** — images are processed concurrently via a bounded
  worker pool (default 3, `BATCH_CONCURRENCY`) rather than an async job queue —
  fast for interactive batches while capping memory on small hosts.
- **OCR quality limitations** — accuracy depends on photo quality; low-confidence
  reads are flagged rather than silently trusted, and no advanced image cleanup
  is applied.
- **No persistence or auth** — results are returned per request and nothing is
  stored; there are no user accounts. Appropriate for a prototype, not production.
- **Deterministic validation over AI-driven compliance** — accepts slightly more
  rule-writing effort in exchange for auditable, reproducible, testable verdicts.

## Prototype Scope / Requirements Addressed

- **Automated routine verification** — removes manual field-by-field checking.
- **Batch processing** — multiple labels verified in one request.
- **Human-readable results** — a per-field checklist with reasons and a clear
  PASS / WARN / FAIL verdict.
- **Simple workflow for non-technical users** — drag-and-drop upload, plain-language
  field labels, no jargon required to interpret results.
- **Extensible rules architecture** — rules live in one engine
  (`backend/app/rules/validate.py`); adding a check is a localized change plus a
  catalog entry, with unit tests alongside.
  
## Development Process

Generative AI tools were used during development to accelerate implementation,
scaffold components, and iterate on architecture decisions. All system design,
validation logic, requirements mapping, testing, and final technical decisions
were reviewed and implemented as part of the development process.

The compliance determination logic remains fully deterministic and is not
generated at runtime by an LLM.

## Security & Privacy Notes

This is a prototype. The following security considerations apply:

**API Key Management**
API keys are managed via environment variables and never committed to source control. A `.env.example` file is provided with placeholder values. Confirm `.env` is listed in `.gitignore` before deploying or sharing the repository.

**Data Handling**
No label images or extracted data are persisted — all processing is in-memory and session-scoped. Nothing is logged or stored between requests.

**Third-Party API Transmission**
Images are transmitted to Anthropic's API for processing. A production deployment would require a data processing agreement and routing through FedRAMP-compliant infrastructure (e.g. Anthropic available via Azure Government marketplace).

**Authentication**
No authentication layer is included — appropriate for a standalone proof-of-concept. A production build would integrate with TTB's existing identity provider.

**CORS Policy**
CORS is open (`allow_origins=["*"]`) for prototype convenience and would be restricted to internal TTB domains in production.

**Federal Network Dependency**
This prototype calls `api.anthropic.com` directly. In federal network environments where outbound traffic to external ML endpoints is blocked (as noted by TTB IT), this would fail. The production path is to route through Azure API Management inside Treasury's Azure Government boundary.

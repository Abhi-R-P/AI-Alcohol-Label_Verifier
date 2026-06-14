# AI Alcohol Label Verifier

Batch-verify alcohol product labels. Each uploaded image is OCR'd, structured
into typed fields by the Claude API, and checked against a deterministic
rule-based validation layer that returns a `PASS` / `WARN` / `FAIL` verdict with
itemized findings.

See [`DESIGN.md`](./DESIGN.md) for the architecture, request flow, and trade-offs.

```
Next.js (upload + results)  ──POST /verify──▶  FastAPI
                                                 └ for each image:
                                                   decode → OCR (Tesseract)
                                                   → Claude extraction (structured JSON)
                                                   → rule engine → verdict
```

Claude only **extracts** fields; it never decides compliance. All pass/fail
logic lives in `backend/app/rules/` and is unit-tested.

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
- `POST /verify` — `multipart/form-data`: `files` (1..N images) + optional `profile` (JSON).
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

## Model

Extraction defaults to `claude-opus-4-8`. For tighter latency/cost on this
OCR-text task, set `EXTRACTION_MODEL=claude-sonnet-4-6` (or `claude-haiku-4-5`)
in `backend/.env` — both support structured outputs.

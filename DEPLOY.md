# Deployment Guide

Backend (FastAPI) → **Render** via Docker; frontend (Next.js) → **Vercel**.
Deploy the backend first — you need its URL for the frontend.

## 1. Backend (Render)

The repo ships `render.yaml` (Blueprint) and `backend/Dockerfile` (the Dockerfile
installs Tesseract, which OCR requires).

1. Render → **New → Blueprint** → connect this repo/branch. It reads `render.yaml`
   and creates the `label-verifier-api` service (Docker, root `backend/`).
2. When prompted, set the secret env vars:
   - `ANTHROPIC_API_KEY = sk-ant-…`
   - `CORS_ORIGINS = https://<your-frontend>.vercel.app`  (exact origin, no trailing slash)
3. Apply, then verify:
   ```bash
   curl https://label-verifier-api.onrender.com/healthz
   # {"status":"ok","tesseract":true,"api_key_configured":true,"model":"claude-haiku-4-5"}
   ```
   Both `tesseract` and `api_key_configured` must be `true`.

> Don't set `PORT` — Render injects it and the Dockerfile binds `$PORT`.

## 2. Frontend (Vercel)

1. Vercel → **Add New → Project** → import the repo.
2. **Root Directory:** `frontend` (Next.js auto-detected).
3. Env var: `NEXT_PUBLIC_API_BASE = https://label-verifier-api.onrender.com`
   (no trailing slash).
4. **Settings → Git → Production Branch** = your deploy branch (so pushes publish
   to the production domain, not a protected preview URL).
5. **Settings → Deployment Protection → Vercel Authentication → Disabled** (so an
   external reviewer can open it without a Vercel login).
6. Deploy → note the production URL, then ensure the backend's `CORS_ORIGINS`
   matches it exactly (redeploy the backend if you change it).

## 3. Environment variables

**Backend (Render)**

| Variable | Required | Default | Notes |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | yes | — | Claude API key (env only; never commit). |
| `CORS_ORIGINS` | yes | `http://localhost:3000` | Frontend origin(s), comma-separated. `*` allows any (demo only). |
| `EXTRACTION_MODEL` | no | `claude-haiku-4-5` | `claude-sonnet-4-6` / `claude-opus-4-8` for more accuracy, slower. |
| `EXTRACTION_TIMEOUT_S` | no | `4.0` | Per-image Claude timeout. |
| `MAX_FILES` / `MAX_FILE_MB` | no | `10` / `10` | Batch + size caps. |

**Frontend (Vercel)**

| Variable | Required | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | yes | Backend URL, no trailing slash. **Build-time — redeploy after changing.** |

## 4. Common pitfalls

| Symptom | Fix |
|---|---|
| `/healthz` → `"tesseract": false` | Deployed without Docker — use the Docker/Blueprint path. |
| `/healthz` → `"api_key_configured": false` | Set `ANTHROPIC_API_KEY` on Render and redeploy. |
| Browser "Failed to fetch" / CORS error | Set `CORS_ORIGINS` to the exact frontend origin; redeploy backend. CORS isn't auth — non-browser clients bypass it. |
| Frontend calls `localhost:8000` in prod | `NEXT_PUBLIC_API_BASE` unset/changed without rebuild — set it and **redeploy**. |
| App URL returns **403** | Vercel Deployment Protection on, or you're using a preview (hashed) URL — disable protection and use the production domain. |
| New asset (e.g. logo) 404s after deploy | File must be in `frontend/public/`; redeploy with **build cache off**. |
| First request slow then fine | Render free-tier cold start; hit `/healthz` to warm, or use a paid instance. |

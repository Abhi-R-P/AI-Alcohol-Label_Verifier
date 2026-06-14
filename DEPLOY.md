# Deployment Guide

Deploy the **FastAPI backend** to Render or Railway (Docker) and the **Next.js
frontend** to Vercel. Order matters: deploy the backend first so you have its URL
for the frontend's `NEXT_PUBLIC_API_BASE`.

> The backend ships with `backend/Dockerfile`, which installs Tesseract. Use the
> Docker path on whichever host you pick — it's the reliable way to get OCR
> working in the cloud.

---

## 1. Backend — Render (Docker)

1. Push this repo to GitHub (already done if you're reading this).
2. Render dashboard → **New → Web Service** → connect the repo.
3. Settings:
   - **Root Directory:** `backend`
   - **Runtime / Language:** `Docker` (Render auto-detects `backend/Dockerfile`)
   - **Instance type:** Free is fine for a demo.
4. **Environment → Add environment variables** (see the table in §4):
   ```
   ANTHROPIC_API_KEY = sk-ant-...
   CORS_ORIGINS      = https://<your-frontend>.vercel.app
   ```
5. **Create Web Service.** When live, note the URL, e.g.
   `https://label-verifier-api.onrender.com`.
6. Verify:
   ```bash
   curl https://label-verifier-api.onrender.com/healthz
   # {"status":"ok","tesseract":true,"api_key_configured":true,"model":"claude-opus-4-8"}
   ```
   `tesseract` must be `true` and `api_key_configured` must be `true`.

---

## 1-alt. Backend — Railway (Docker)

1. Railway → **New Project → Deploy from GitHub repo** → pick the repo.
2. Open the service → **Settings → Root Directory:** `backend`
   (Railway auto-detects the `Dockerfile`).
3. **Variables** tab → add the same vars as above (`ANTHROPIC_API_KEY`, `CORS_ORIGINS`).
4. **Settings → Networking → Generate Domain** to get a public URL.
5. Verify with the same `curl .../healthz` as above.

> Don't set `PORT` yourself — Render and Railway inject it, and the Dockerfile
> already binds to `$PORT`.

---

## 2. Frontend — Vercel

1. Vercel → **Add New → Project** → import the repo.
2. Settings:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Next.js (auto-detected).
3. **Environment Variables** → add:
   ```
   NEXT_PUBLIC_API_BASE = https://label-verifier-api.onrender.com
   ```
   (your backend URL from step 1 — **no trailing slash**).
4. **Deploy.** You'll get `https://<your-frontend>.vercel.app`.
5. Go back to the **backend** and make sure `CORS_ORIGINS` equals this exact
   Vercel URL, then redeploy the backend if you just changed it.

---

## 3. Wire the two together (CORS)

The backend only accepts browser requests from origins listed in `CORS_ORIGINS`.
After both are deployed, confirm the backend's `CORS_ORIGINS` is the frontend's
real URL (comma-separate to allow several, e.g. preview + prod):

```
CORS_ORIGINS = https://label-verifier.vercel.app,http://localhost:3000
```

---

## 4. Environment variables

### Backend (Render / Railway)

| Variable               | Required | Example                                   | Notes |
|------------------------|----------|-------------------------------------------|-------|
| `ANTHROPIC_API_KEY`    | **Yes**  | `sk-ant-...`                              | Your Claude API key. |
| `CORS_ORIGINS`         | **Yes**  | `https://app.vercel.app`                  | The frontend origin(s), comma-separated. |
| `EXTRACTION_MODEL`     | No       | `claude-opus-4-8`                         | Default; set `claude-sonnet-4-6` for lower latency/cost. |
| `EXTRACTION_TIMEOUT_S` | No       | `4.0`                                     | Per-image Claude timeout. |
| `MAX_FILES`            | No       | `10`                                      | Batch cap. |
| `MAX_FILE_MB`          | No       | `10`                                      | Per-file size cap. |

### Frontend (Vercel)

| Variable               | Required | Example                                   | Notes |
|------------------------|----------|-------------------------------------------|-------|
| `NEXT_PUBLIC_API_BASE` | **Yes**  | `https://label-verifier-api.onrender.com` | Backend URL, no trailing slash. Build-time — redeploy after changing. |

### Getting a Claude API key

console.anthropic.com → **Settings → API Keys → Create Key**. Store it only in the
host's env-var settings — never commit it.

---

## 5. Common pitfalls & fixes

| Symptom | Cause | Fix |
|---|---|---|
| `/healthz` shows `"tesseract": false`; OCR returns empty text | Tesseract not installed (deployed without Docker) | Use the Docker runtime so `backend/Dockerfile` installs `tesseract-ocr`. |
| `/healthz` shows `"api_key_configured": false` | `ANTHROPIC_API_KEY` not set on the host | Add it in the host's env vars and redeploy. |
| Frontend shows "Failed to fetch" / CORS error in console | Backend `CORS_ORIGINS` doesn't include the Vercel URL | Set `CORS_ORIGINS` to the exact frontend origin and redeploy the backend. |
| Frontend calls `http://localhost:8000` in production | `NEXT_PUBLIC_API_BASE` not set, or set after build | Set it in Vercel **and redeploy** — `NEXT_PUBLIC_*` is baked in at build time. |
| Requests fail only in the browser, work in `curl` | Trailing slash / wrong scheme in `NEXT_PUBLIC_API_BASE` | Use `https://…` with **no** trailing slash. |
| First request after idle is very slow / times out | Render/Railway free tier cold start (not the 5s budget) | Hit `/healthz` to warm it, or use a paid always-on instance. |
| `401`/`authentication_error` from Claude | Invalid or rotated API key | Recreate the key in the Anthropic console and update the env var. |
| Large photos rejected with `413` | File exceeds `MAX_FILE_MB` | Raise `MAX_FILE_MB`, or downscale images before upload. |

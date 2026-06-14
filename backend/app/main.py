"""FastAPI app: batch label verification endpoint plus health and rule catalog."""
from __future__ import annotations

import json
import shutil
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.pipeline import process_image
from app.rules.engine import rule_catalog
from app.schemas import (
    ImageResult,
    Profile,
    RuleInfo,
    Summary,
    VerifyResponse,
)

app = FastAPI(title="AI Alcohol Label Verifier", version="0.1.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


async def _read_image(upload: UploadFile) -> bytes:
    """Validate type/size and return the raw bytes of one uploaded image."""
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type for {upload.filename}: {upload.content_type}.",
        )
    raw = await upload.read()
    if len(raw) > settings.max_file_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"{upload.filename} exceeds {settings.max_file_bytes} bytes.",
        )
    return raw


@app.get("/healthz")
def healthz() -> dict:
    """Liveness/readiness: checks Tesseract availability and API key presence."""
    return {
        "status": "ok",
        "tesseract": shutil.which("tesseract") is not None,
        "api_key_configured": bool(settings.anthropic_api_key),
        "model": settings.extraction_model,
    }


@app.get("/rules", response_model=list[RuleInfo])
def rules() -> list[RuleInfo]:
    """The active rule catalog — powers the UI legend and self-documents the layer."""
    return rule_catalog()


@app.post("/upload-label", response_model=ImageResult)
async def upload_label(file: UploadFile = File(...)) -> ImageResult:
    """Full single-image flow: OCR -> Claude extraction -> validation.

    Returns one combined result: raw OCR text, the structured fields Claude
    extracted, deterministic per-field validation, the rolled-up verdict, and
    per-stage timings. Speed is bounded by the OCR step plus a single
    timeout-capped Claude call (see EXTRACTION_TIMEOUT_S) to stay under ~5s.
    """
    raw = await _read_image(file)
    # process_image is the shared OCR -> Claude -> validation orchestration; it
    # captures per-image failures into the result rather than raising.
    return process_image(file.filename or "image", raw)


@app.post("/verify", response_model=VerifyResponse)
async def verify(
    files: list[UploadFile] = File(...),
    profile: Optional[str] = Form(None),
) -> VerifyResponse:
    """Batch verify: run the full OCR -> Claude -> validation flow on each image.

    Accepts one or many images plus an optional expected `profile` (JSON). Images
    are processed sequentially in a simple loop (no async queue); the response
    carries the per-image results array in upload order plus PASS/WARN/FAIL counts.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > settings.max_files:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files: {len(files)} (max {settings.max_files}).",
        )

    parsed_profile: Optional[Profile] = None
    if profile:
        try:
            parsed_profile = Profile.model_validate(json.loads(profile))
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid profile: {exc}")

    results = []
    for upload in files:
        raw = await _read_image(upload)
        # Simple synchronous loop — adequate for small MVP batches.
        results.append(process_image(upload.filename or "image", raw, parsed_profile))

    summary = Summary(
        total=len(results),
        passed=sum(r.verdict == "PASS" for r in results),
        warned=sum(r.verdict == "WARN" for r in results),
        failed=sum(r.verdict == "FAIL" for r in results),
    )
    return VerifyResponse(summary=summary, results=results)

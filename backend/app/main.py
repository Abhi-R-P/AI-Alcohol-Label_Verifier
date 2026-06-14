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
from app.services.ocr import extract_raw_text
from app.schemas import (
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


@app.post("/upload-label")
async def upload_label(file: UploadFile = File(...)) -> dict:
    """OCR a single label image and return the raw extracted text.

    No external APIs — pure local Tesseract OCR with grayscale preprocessing.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}.",
        )
    raw = await file.read()
    if len(raw) > settings.max_file_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"{file.filename} exceeds {settings.max_file_bytes} bytes.",
        )
    try:
        text = extract_raw_text(raw, settings.max_image_edge)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"filename": file.filename, "text": text}


@app.post("/verify", response_model=VerifyResponse)
async def verify(
    files: list[UploadFile] = File(...),
    profile: Optional[str] = Form(None),
) -> VerifyResponse:
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
        # Simple synchronous loop — adequate for small MVP batches.
        results.append(process_image(upload.filename or "image", raw, parsed_profile))

    summary = Summary(
        total=len(results),
        passed=sum(r.verdict == "PASS" for r in results),
        warned=sum(r.verdict == "WARN" for r in results),
        failed=sum(r.verdict == "FAIL" for r in results),
    )
    return VerifyResponse(summary=summary, results=results)

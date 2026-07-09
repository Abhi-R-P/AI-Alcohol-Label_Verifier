"""FastAPI app: single + batch label verification, health, and rule catalog."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import shutil
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.pipeline import process_image
from app.rules.validate import rule_catalog
from app.schemas import (
    ApplicationData,
    ImageResult,
    RuleInfo,
    Summary,
    VerifyResponse,
)

app = FastAPI(title="AI Alcohol Label Verifier", version="0.2.0")

settings = get_settings()
_allow_all = "*" in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all else settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_CSV_FIELDS = (
    "brand_name",
    "class_type",
    "abv",
    "net_contents",
    "bottler_name",
    "bottler_address",
    "country_of_origin",
)


async def _read_image(upload: UploadFile) -> bytes:
    """Validate type/size and return the raw bytes of one uploaded image."""
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type for {upload.filename}: {upload.content_type}.",
        )
    raw = await upload.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail=f"{upload.filename} is empty.")
    if len(raw) > settings.max_file_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"{upload.filename} exceeds {settings.max_file_bytes} bytes.",
        )
    return raw


def _parse_application(raw: Optional[str]) -> Optional[ApplicationData]:
    if not raw:
        return None
    try:
        return ApplicationData.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid application JSON.")


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None or not str(value).strip():
        return None
    try:
        return float(str(value).strip().rstrip("%"))
    except ValueError:
        return None


def _parse_csv(raw: bytes) -> dict[str, ApplicationData]:
    """Parse an expected-values CSV keyed by a `filename` column."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.")
    reader = csv.DictReader(io.StringIO(text))
    mapping: dict[str, ApplicationData] = {}
    for row in reader:
        filename = (row.get("filename") or row.get("file") or "").strip()
        if not filename:
            continue
        mapping[filename] = ApplicationData(
            brand_name=(row.get("brand_name") or None),
            class_type=(row.get("class_type") or None),
            abv=_to_float(row.get("abv")),
            net_contents=(row.get("net_contents") or None),
            bottler_name=(row.get("bottler_name") or None),
            bottler_address=(row.get("bottler_address") or None),
            country_of_origin=(row.get("country_of_origin") or None),
        )
    return mapping


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
async def upload_label(
    file: UploadFile = File(...),
    application: Optional[str] = Form(None),
) -> ImageResult:
    """Full single-image flow: OCR -> Claude extraction -> validation.

    Optional `application` (JSON) supplies expected COLA values to compare against.
    """
    raw = await _read_image(file)
    app_data = _parse_application(application)
    return await run_in_threadpool(
        process_image, file.filename or "image", raw, app_data
    )


@app.post("/verify", response_model=VerifyResponse)
async def verify(
    files: list[UploadFile] = File(...),
    application: Optional[str] = Form(None),
    csv_file: Optional[UploadFile] = File(None),
) -> VerifyResponse:
    """Batch verify: OCR -> Claude -> validation for each image, concurrently.

    Expected COLA values may come from `application` (JSON, applied to all images)
    or a `csv_file` mapping `filename` -> expected fields (per image). Images are
    processed concurrently with a bounded worker pool (no async queue system).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > settings.max_files:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files: {len(files)} (max {settings.max_files}).",
        )

    single_app = _parse_application(application)
    csv_map: dict[str, ApplicationData] = {}
    if csv_file is not None:
        csv_map = _parse_csv(await csv_file.read())

    # Read + validate all files first (fast, sequential), then process concurrently.
    prepared: list[tuple[str, bytes, Optional[ApplicationData]]] = []
    for upload in files:
        raw = await _read_image(upload)
        name = upload.filename or "image"
        app_data = csv_map.get(name) or single_app
        prepared.append((name, raw, app_data))

    semaphore = asyncio.Semaphore(max(1, settings.batch_concurrency))

    async def _run(name: str, raw: bytes, app_data: Optional[ApplicationData]) -> ImageResult:
        async with semaphore:
            return await run_in_threadpool(process_image, name, raw, app_data)

    results = await asyncio.gather(*(_run(*item) for item in prepared))

    summary = Summary(
        total=len(results),
        passed=sum(r.verdict == "PASS" for r in results),
        warned=sum(r.verdict == "WARN" for r in results),
        failed=sum(r.verdict == "FAIL" for r in results),
    )
    return VerifyResponse(summary=summary, results=list(results))

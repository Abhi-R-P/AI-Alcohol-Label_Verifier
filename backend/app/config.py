"""Runtime configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from functools import lru_cache


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Settings:
    def __init__(self) -> None:
        self.anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
        # Haiku is the fastest tier and is more than capable of structured
        # extraction from short OCR text — the right default for the <5s budget.
        # Override with EXTRACTION_MODEL=claude-sonnet-4-6 / claude-opus-4-8 for
        # higher accuracy at the cost of latency.
        self.extraction_model: str = os.environ.get("EXTRACTION_MODEL", "claude-haiku-4-5")
        # "ocr" (Tesseract -> text -> Claude) or "vision" (image -> Claude).
        self.extraction_mode: str = os.environ.get("EXTRACTION_MODE", "ocr").strip().lower()
        self.max_files: int = _get_int("MAX_FILES", 10)
        # Concurrent images per batch. Bounded to protect memory on small hosts.
        self.batch_concurrency: int = _get_int("BATCH_CONCURRENCY", 3)
        self.max_file_bytes: int = _get_int("MAX_FILE_MB", 10) * 1024 * 1024
        # Smaller long-edge => faster OCR. 1280 keeps label text legible while
        # cutting Tesseract CPU time on constrained hosts.
        self.max_image_edge: int = _get_int("MAX_IMAGE_EDGE", 1280)
        self.extraction_timeout_s: float = _get_float("EXTRACTION_TIMEOUT_S", 4.0)
        self.ocr_confidence_threshold: float = _get_float("OCR_CONFIDENCE_THRESHOLD", 55.0)
        self.cors_origins: list[str] = [
            o.strip().rstrip("/")  # tolerate trailing slashes; browsers send none
            for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
            if o.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()

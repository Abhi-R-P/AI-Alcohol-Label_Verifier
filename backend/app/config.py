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
        self.extraction_model: str = os.environ.get("EXTRACTION_MODEL", "claude-opus-4-8")
        self.max_files: int = _get_int("MAX_FILES", 10)
        self.max_file_bytes: int = _get_int("MAX_FILE_MB", 10) * 1024 * 1024
        self.max_image_edge: int = _get_int("MAX_IMAGE_EDGE", 1600)
        self.extraction_timeout_s: float = _get_float("EXTRACTION_TIMEOUT_S", 4.0)
        self.ocr_confidence_threshold: float = _get_float("OCR_CONFIDENCE_THRESHOLD", 55.0)
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
            if o.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()

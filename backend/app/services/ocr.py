"""Tesseract OCR wrapper returning extracted text plus mean confidence."""
from __future__ import annotations

from dataclasses import dataclass

import pytesseract
from PIL import Image


@dataclass
class OcrResult:
    text: str
    mean_confidence: float  # 0-100; 0.0 when no words were recognized


def run_ocr(img: Image.Image) -> OcrResult:
    """Run Tesseract and aggregate per-word confidences into a mean."""
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    words: list[str] = []
    confidences: list[float] = []
    for word, conf in zip(data["text"], data["conf"]):
        word = word.strip()
        if not word:
            continue
        try:
            conf_val = float(conf)
        except (TypeError, ValueError):
            continue
        if conf_val < 0:  # Tesseract uses -1 for non-text regions
            continue
        words.append(word)
        confidences.append(conf_val)

    text = " ".join(words)
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return OcrResult(text=text, mean_confidence=round(mean_conf, 1))


def extract_raw_text(raw: bytes, max_edge: int = 1600) -> str:
    """Image bytes -> raw extracted text string.

    Handles preprocessing (EXIF-orient, grayscale, downscale) via
    `load_and_normalize`. Returns plain text; raises ValueError if the bytes
    can't be decoded as an image.
    """
    # Imported here to avoid a circular import at module load.
    from app.services.image import load_and_normalize

    try:
        img = load_and_normalize(raw, max_edge)
    except Exception as exc:  # noqa: BLE001 - normalize any decode failure
        raise ValueError(f"Could not read image: {exc}") from exc

    return run_ocr(img).text

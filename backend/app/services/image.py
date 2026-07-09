"""Image decode + normalization: auto-orient, downscale, grayscale.

Keeping the long edge bounded caps both OCR cost and memory. We also decode as
cheaply as possible (JPEG draft mode + a pixel cap) so a large phone photo can't
OOM the process on a small instance.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps

# Reject absurdly large images before fully decoding them (decompression-bomb
# guard + memory protection). 25 MP comfortably covers real label photos.
Image.MAX_IMAGE_PIXELS = 25_000_000


def load_and_normalize(raw: bytes, max_edge: int) -> Image.Image:
    """Decode bytes into a normalized grayscale PIL image ready for OCR."""
    img = Image.open(io.BytesIO(raw))
    # For JPEGs, draft() decodes at a reduced scale (1/2, 1/4, ...) directly,
    # cutting peak memory and CPU before the full raster is ever materialized.
    # No-op for formats that don't support it (e.g. PNG).
    img.draft("L", (max_edge, max_edge))
    # Honor EXIF orientation so rotated phone photos OCR correctly.
    img = ImageOps.exif_transpose(img)
    img = img.convert("L")  # grayscale

    long_edge = max(img.size)
    if long_edge > max_edge:
        scale = max_edge / long_edge
        new_size = (round(img.width * scale), round(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)

    return img


def normalize_for_vision(raw: bytes, max_edge: int) -> bytes:
    """Decode, orient, and downscale to bounded JPEG bytes for Claude vision.

    Keeps color (vision benefits from it) but caps the long edge to bound token
    cost/latency. Returns re-encoded JPEG bytes.
    """
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    long_edge = max(img.size)
    if long_edge > max_edge:
        scale = max_edge / long_edge
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

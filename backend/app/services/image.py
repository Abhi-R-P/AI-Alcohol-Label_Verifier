"""Image decode + normalization: auto-orient, downscale, grayscale.

Keeping the long edge bounded caps both OCR cost and (if we ever fall back to
vision) the token cost of the image.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps


def load_and_normalize(raw: bytes, max_edge: int) -> Image.Image:
    """Decode bytes into a normalized grayscale PIL image ready for OCR."""
    img = Image.open(io.BytesIO(raw))
    # Honor EXIF orientation so rotated phone photos OCR correctly.
    img = ImageOps.exif_transpose(img)
    img = img.convert("L")  # grayscale

    long_edge = max(img.size)
    if long_edge > max_edge:
        scale = max_edge / long_edge
        new_size = (round(img.width * scale), round(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)

    return img

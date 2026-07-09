"""Render synthetic label images from ground_truth.csv (reproducible eval set).

These are plain rendered labels, not photos — they give a deterministic,
committable dataset with known ground truth so the eval runs anywhere. Real
photos (glare/angle/blur) are the natural next step for a harder eval set.

    python eval/generate_samples.py    # writes PNGs into eval/samples/
"""
from __future__ import annotations

import csv
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.rules.validate import CANONICAL_GOV_WARNING

HERE = Path(__file__).resolve().parent
SAMPLES = HERE / "samples"
WIDTH = 1000


def _font(size: int) -> ImageFont.FreeTypeFont:
    # Pillow >= 10.1 ships a scalable default font.
    return ImageFont.load_default(size=size)


def render(row: dict) -> Image.Image:
    lines: list[tuple[str, int]] = [
        (row["brand_name"], 46),
        (row["class_type"], 30),
        (f"ALC. {row['abv']}% BY VOL", 30),
    ]
    if row.get("net_contents"):
        lines.append((row["net_contents"], 30))
    lines.append((f"Bottled by {row['bottler_name']}", 26))
    if row.get("bottler_address"):
        lines.append((row["bottler_address"], 26))
    if row.get("country_of_origin"):
        lines.append((f"Product of {row['country_of_origin']}", 26))

    img = Image.new("RGB", (WIDTH, 900), "white")
    draw = ImageDraw.Draw(img)
    y = 40
    for text, size in lines:
        draw.text((50, y), text, fill="black", font=_font(size))
        y += size + 18

    if str(row.get("has_warning", "")).strip().lower() == "yes":
        y += 20
        for wrapped in textwrap.wrap(CANONICAL_GOV_WARNING, width=78):
            draw.text((50, y), wrapped, fill="black", font=_font(22))
            y += 30
    return img


def main() -> None:
    SAMPLES.mkdir(exist_ok=True)
    with open(HERE / "ground_truth.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        render(row).save(SAMPLES / row["filename"])
        print(f"wrote {row['filename']}")
    print(f"\n{len(rows)} label images in {SAMPLES}")


if __name__ == "__main__":
    main()

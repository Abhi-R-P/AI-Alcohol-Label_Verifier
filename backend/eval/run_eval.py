"""Run the extraction eval: OCR vs. vision, field accuracy + latency.

Prereqs: generated samples (`python eval/generate_samples.py`), Tesseract
installed (for OCR mode), and ANTHROPIC_API_KEY set. Run from `backend/`:

    python eval/run_eval.py                # both modes
    python eval/run_eval.py --mode ocr     # or: vision

Writes a markdown report to eval/results/latest.md and prints it.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import time
from pathlib import Path

from app.rules.validate import CANONICAL_GOV_WARNING
from app.services.extract import extract_fields, extract_fields_vision
from app.services.image import load_and_normalize, normalize_for_vision
from app.services.ocr import run_ocr
from eval.scoring import SCORED_FIELDS, score_record

HERE = Path(__file__).resolve().parent
SAMPLES = HERE / "samples"
RESULTS = HERE / "results"
MAX_EDGE = 1280


def load_ground_truth(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["filename"]] = {
                "brand_name": row.get("brand_name") or None,
                "class_type": row.get("class_type") or None,
                "abv": float(row["abv"]) if row.get("abv") else None,
                "net_contents": row.get("net_contents") or None,
                "bottler_name": row.get("bottler_name") or None,
                "bottler_address": row.get("bottler_address") or None,
                "country_of_origin": row.get("country_of_origin") or None,
                "government_warning_text": (
                    CANONICAL_GOV_WARNING
                    if str(row.get("has_warning", "")).strip().lower() == "yes"
                    else None
                ),
            }
    return out


def extract_one(mode: str, raw: bytes) -> tuple[dict, float]:
    """Return (extracted_fields_dict, latency_seconds) for one image."""
    start = time.perf_counter()
    if mode == "vision":
        extraction = extract_fields_vision(normalize_for_vision(raw, MAX_EDGE))
    else:
        text = run_ocr(load_and_normalize(raw, MAX_EDGE)).text
        extraction = extract_fields(text)
    return extraction.model_dump(), time.perf_counter() - start


def run_mode(mode: str, truth: dict[str, dict], samples_dir: Path) -> dict:
    per_field_hits = {f: 0 for f in SCORED_FIELDS}
    latencies: list[float] = []
    n = 0
    for filename, expected in truth.items():
        path = samples_dir / filename
        if not path.exists():
            print(f"  (skip {filename}: not generated)")
            continue
        extracted, latency = extract_one(mode, path.read_bytes())
        latencies.append(latency)
        scores = score_record(extracted, expected)
        for f, ok in scores.items():
            per_field_hits[f] += int(ok)
        n += 1
        print(f"  {mode:6} {filename}: {sum(scores.values())}/{len(scores)} fields, {latency:.1f}s")
    return {"n": n, "per_field_hits": per_field_hits, "latencies": latencies}


def _md_table(mode: str, res: dict) -> str:
    n = res["n"] or 1
    lines = [f"### {mode.upper()} mode ({res['n']} labels)", "", "| field | accuracy |", "|---|---|"]
    total = 0
    for f in SCORED_FIELDS:
        acc = res["per_field_hits"][f] / n
        total += res["per_field_hits"][f]
        lines.append(f"| {f} | {acc:.0%} |")
    overall = total / (n * len(SCORED_FIELDS))
    med = statistics.median(res["latencies"]) if res["latencies"] else 0.0
    lines += ["", f"**Overall accuracy: {overall:.0%} · median latency: {med:.1f}s**", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["ocr", "vision", "both"], default="both")
    parser.add_argument("--samples-dir", default="samples", help="dir of images, relative to eval/")
    parser.add_argument("--truth", default="ground_truth.csv", help="ground-truth CSV, relative to eval/")
    args = parser.parse_args()
    modes = ["ocr", "vision"] if args.mode == "both" else [args.mode]

    samples_dir = HERE / args.samples_dir
    truth = load_ground_truth(HERE / args.truth)
    report = [f"# Extraction eval — {len(truth)} labels ({args.samples_dir})\n"]
    summary_rows = []
    for mode in modes:
        print(f"\n== {mode} ==")
        res = run_mode(mode, truth, samples_dir)
        report.append(_md_table(mode, res))
        n = res["n"] or 1
        overall = sum(res["per_field_hits"].values()) / (n * len(SCORED_FIELDS))
        med = statistics.median(res["latencies"]) if res["latencies"] else 0.0
        summary_rows.append((mode, overall, med))

    if len(summary_rows) > 1:
        report.append("### Comparison\n\n| mode | overall accuracy | median latency |\n|---|---|---|")
        for mode, overall, med in summary_rows:
            report.append(f"| {mode} | {overall:.0%} | {med:.1f}s |")
        report.append(
            "\n_Cost note: OCR mode sends only text; vision mode sends the image "
            "(more input tokens per call). Check exact usage in the Anthropic console._"
        )

    RESULTS.mkdir(exist_ok=True)
    out = "\n".join(report) + "\n"
    (RESULTS / "latest.md").write_text(out, encoding="utf-8")
    print("\n" + out)
    print(f"(written to {RESULTS / 'latest.md'})")


if __name__ == "__main__":
    main()

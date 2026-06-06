#!/usr/bin/env python3
"""
Tesseract OCR for component values — uses OBB orientation to deskew crops.

Pipeline:
  1. Load 134-image GT set with HDC component labels (YOLO-OBB)
  2. Extract rotation angle from OBB polygon points
  3. Deskew crop to horizontal
  4. Run Tesseract on deskewed crop
  5. Parse value from OCR text

Run:
  python wire_detection/benchmark/component_ocr_tess.py
  python wire_detection/benchmark/component_ocr_tess.py --limit 10
  python wire_detection/benchmark/component_ocr_tess.py --resume
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytesseract

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

# ── Data paths ──
GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
HDC_BASE = Path("/home/claw/circuit-digitization/roboflow_test2")
HDC_SPLITS = ["train", "valid", "test"]
OUT_DIR = Path(SCRIPT_DIR.parent.parent / "output" / "component_ocr_tess")

# ── Component class names ──
COMPONENT_TYPES = {
    0: "junction", 1: "terminal", 2: "resistor", 3: "capacitor",
    4: "inductor", 5: "diode", 6: "transistor", 7: "voltage_source",
    8: "ground", 9: "wire", 10: "ic_opamp", 11: "switch",
    12: "fuse", 13: "transformer", 14: "antenna", 15: "probe",
    16: "crossover", 17: "crystal", 18: "relay", 19: "speaker",
}

# Types that typically have readable values
VALUE_TYPES = {2, 3, 4, 5, 6, 7, 10}  # R, C, L, D, Q, V, IC

# Common value patterns
VALUE_PATTERNS = [
    # Resistor: 10k, 4.7k, 1M, 100R, 4R7
    r'(\d+\.?\d*)\s*[kKmMgG]\s*[ΩR]?',
    r'(\d+\.?\d*)\s*[ΩR]',
    r'(\d+\.?\d*[kKmMgG])',
    # Capacitor: 100n, 10u, 0.1u, 22p
    r'(\d+\.?\d*)\s*[pPnNuUμmM]\s*[Ff]?',
    r'(\d+\.?\d*[pPnNuUμmM])',
    # Inductor: 10m, 100u
    r'(\d+\.?\d*)\s*[mMuUμ]\s*[Hh]?',
    r'(\d+\.?\d*[mMuUμ])',
    # Voltage: 5V, 12V, 3.3V
    r'(\d+\.?\d*)\s*[Vv]',
    # Part numbers: 1N4148, 2N2222, LM741
    r'([12][Nn]\d{3,4})',
    r'(LM\d{3,4})',
    r'(NE\d{3,4})',
    # Generic numbers
    r'(\d+\.?\d*)',
]


def find_hdc_label(image_name: str) -> Path | None:
    """Find HDC component label by filename prefix."""
    for split in HDC_SPLITS:
        label_dir = HDC_BASE / split / "labels"
        for pattern in [f"{image_name}.rf.*.txt", f"{image_name}_jpg.rf.*.txt"]:
            matches = sorted(label_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def parse_components(text: str, w: int, h: int) -> list:
    """Parse YOLO-OBB component labels with polygon points."""
    comps = []
    for line in text.splitlines():
        p = line.split()
        if len(p) != 9:
            continue
        try:
            cls = int(p[0])
            c = [float(x) for x in p[1:9]]
        except ValueError:
            continue
        xs = [int(c[i] * w) for i in range(0, 8, 2)]
        ys = [int(c[i] * h) for i in range(1, 8, 2)]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        polygon = [(xs[i], ys[i]) for i in range(4)]
        comps.append({"cls": cls, "bbox": bbox, "polygon": polygon})
    return comps


def get_rotation_angle(polygon: list[tuple[int, int]]) -> float:
    """Get rotation angle from OBB polygon (shortest edge angle)."""
    n = len(polygon)
    edges = []
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        length = math.hypot(x2 - x1, y2 - y1)
        angle = math.atan2(y2 - y1, x2 - x1)
        edges.append((length, angle))
    # Shortest edge gives the text orientation
    edges.sort(key=lambda e: e[0])
    return edges[0][1]


def deskew_crop(img: np.ndarray, angle_rad: float) -> np.ndarray:
    """Rotate crop to make text horizontal."""
    angle_deg = math.degrees(angle_rad)
    # Normalize to [-90, 90]
    while angle_deg > 90:
        angle_deg -= 180
    while angle_deg < -90:
        angle_deg += 180
    if abs(angle_deg) < 5:
        return img  # Already roughly horizontal
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def crop_component(gray: np.ndarray, bbox: tuple, margin_pct: float = 0.4) -> np.ndarray | None:
    """Crop component region with margin."""
    h, w = gray.shape
    x1, y1, x2, y2 = bbox
    mx = int((x2 - x1) * margin_pct)
    my = int((y2 - y1) * margin_pct)
    cx1 = max(0, x1 - mx)
    cy1 = max(0, y1 - my)
    cx2 = min(w, x2 + mx)
    cy2 = min(h, y2 + my)
    if cx2 - cx1 < 10 or cy2 - cy1 < 10:
        return None
    return gray[cy1:cy2, cx1:cx2]


def preprocess_for_ocr(img: np.ndarray) -> np.ndarray:
    """Preprocess image for better Tesseract accuracy."""
    # Upscale small crops
    h, w = img.shape
    if max(h, w) < 50:
        scale = 50 / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Adaptive threshold
    binary = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 11, 2)

    # Denoise
    binary = cv2.medianBlur(binary, 3)

    return binary


def extract_value(text: str, comp_type: str) -> dict:
    """Extract component value from OCR text."""
    text = text.strip()
    if not text:
        return {"value": None, "raw": text, "confidence": "none"}

    # Try specific patterns first
    for pattern in VALUE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            value = match.group(0)
            return {"value": value, "raw": text, "confidence": "high"}

    # If we got any text, return it as low confidence
    if len(text) > 1 and any(c.isdigit() for c in text):
        return {"value": text, "raw": text, "confidence": "low"}

    return {"value": None, "raw": text, "confidence": "none"}


def ocr_component(crop: np.ndarray, comp_type: str, polygon: list) -> dict:
    """Run Tesseract OCR on a component crop with deskewing."""
    # Deskew using OBB rotation
    angle = get_rotation_angle(polygon)
    deskewed = deskew_crop(crop, angle)

    # Preprocess
    processed = preprocess_for_ocr(deskewed)

    # Run Tesseract
    try:
        text = pytesseract.image_to_string(processed, config='--psm 7 -c tessedit_char_whitelist=0123456789.kKmMgGnNuUpPμRFHVfLlIiOoWwXx')
        text = text.strip()
    except Exception:
        text = ""

    return extract_value(text, comp_type)


def load_checkpoint(jsonl_path: Path) -> dict[str, dict]:
    """Load already-processed results."""
    results = {}
    if jsonl_path.exists():
        for line in jsonl_path.read_text().splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    results[rec["image"]] = rec
                except (json.JSONDecodeError, KeyError):
                    continue
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUT_DIR / "results.jsonl"

    all_images = sorted(GT_IMAGES.glob("*.jpg"))
    print(f"Found {len(all_images)} images in GT set")

    done = {}
    if args.resume and jsonl_path.exists():
        done = load_checkpoint(jsonl_path)
        print(f"Resuming: {len(done)} images already processed")

    n_img = 0
    t0 = time.perf_counter()

    for img_path in all_images:
        image_name = img_path.stem
        if image_name in done:
            continue
        if args.limit and n_img >= args.limit:
            break

        gray = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape

        hdc_path = find_hdc_label(image_name)
        if hdc_path is None:
            continue

        components = parse_components(hdc_path.read_text(encoding="utf-8"), w, h)
        if not components:
            continue

        # OCR each value-type component
        comp_results = {}
        for i, comp in enumerate(components):
            cls = comp["cls"]
            comp_type = COMPONENT_TYPES.get(cls, f"class_{cls}")

            if cls not in VALUE_TYPES:
                comp_results[f"comp_{i}"] = {
                    "type": comp_type, "value": None, "confidence": "skipped"
                }
                continue

            crop = crop_component(gray, comp["bbox"])
            if crop is None:
                comp_results[f"comp_{i}"] = {
                    "type": comp_type, "value": None, "confidence": "no_crop"
                }
                continue

            result = ocr_component(crop, comp_type, comp["polygon"])
            comp_results[f"comp_{i}"] = {
                "type": comp_type,
                "bbox": comp["bbox"],
                **result,
            }

        record = {"image": image_name, "components": len(components), "values": comp_results}
        with open(jsonl_path, "a") as f:
            f.write(json.dumps(record) + "\n")
        done[image_name] = record
        n_img += 1

        if n_img % 10 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  [{n_img}/{len(all_images)}] {elapsed:.0f}s", file=sys.stderr)

    # Summary
    total_comps = sum(r["components"] for r in done.values())
    value_counts = {"high": 0, "low": 0, "none": 0, "skipped": 0}
    for r in done.values():
        for v in r["values"].values():
            conf = v.get("confidence", "none")
            value_counts[conf] = value_counts.get(conf, 0) + 1

    print(f"\n{'='*60}")
    print(f"TESSERACT OCR RESULTS — {len(done)} images, {total_comps} components")
    print(f"{'='*60}")
    print(f"  High confidence:   {value_counts.get('high', 0)}")
    print(f"  Low confidence:    {value_counts.get('low', 0)}")
    print(f"  No value found:    {value_counts.get('none', 0)}")
    print(f"  Skipped:           {value_counts.get('skipped', 0)}")
    print(f"{'='*60}")

    (OUT_DIR / "summary.json").write_text(json.dumps({
        "images": len(done), "total_components": total_comps, "value_counts": value_counts
    }, indent=2))

    elapsed = time.perf_counter() - t0
    print(f"\nResults: {OUT_DIR}")
    print(f"Time: {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

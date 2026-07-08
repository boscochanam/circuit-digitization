#!/usr/bin/env python3
"""
VLM Component Value OCR — extract component values from cropped regions.

Pipeline:
  1. Load 134-image GT set with HDC component labels
  2. For each component, crop the bbox region
  3. Send crop to VLM: "What is the value of this {component_type}?"
  4. Save results as JSON: {image: {component_name: {value, unit, raw_response}}}

Run:
  python wire_detection/benchmark/component_ocr.py
  python wire_detection/benchmark/component_ocr.py --limit 5    # quick test
  python wire_detection/benchmark/component_ocr.py --resume     # skip processed images
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from wire_detection.paths import gt_images_dir, hdc_root, output_dir

# ── Data paths ──
HDC_SPLITS = ["train", "valid", "test"]
OUT_DIR = output_dir() / "component_ocr"

# ── Component class names (from YOLO-OBB training) ──
COMPONENT_TYPES = {
    0: "junction", 1: "terminal", 2: "resistor", 3: "capacitor",
    4: "inductor", 5: "diode", 6: "transistor", 7: "voltage_source",
    8: "ground", 9: "wire", 10: "ic_opamp", 11: "switch",
    12: "fuse", 13: "transformer", 14: "antenna", 15: "probe",
    16: "crossover", 17: "crystal", 18: "relay", 19: "speaker",
}

# Types that typically have readable values
VALUE_TYPES = {2, 3, 4, 5, 6, 7, 10}  # R, C, L, D, Q, V, IC

PROMPT = """You are reading a circuit schematic. This component is a {comp_type}.

Look at the text label near or on this component. What is its value?

Examples:
- Resistor: "10k" means 10kΩ, "4.7R" means 4.7Ω, "1M" means 1MΩ
- Capacitor: "100n" means 100nF, "10u" means 10µF, "0.1u" means 0.1µF
- Inductor: "10m" means 10mH, "100u" means 100µH
- Diode: "1N4148" is the part number
- Transistor: "2N2222" is the part number
- Voltage source: "5V", "12V", "3.3V"

Return ONLY a JSON object with these fields:
{{"value": "the value string as written", "unit": "the unit (ohm/farad/henry/V/A/part_number/none)", "confidence": "high/medium/low"}}

If you cannot read any value, return: {{"value": null, "unit": null, "confidence": "none"}}

Do NOT include any explanation — only the JSON."""


def find_hdc_label(image_name: str) -> Path | None:
    """Find HDC component label by filename prefix."""
    for split in HDC_SPLITS:
        label_dir = hdc_root() / split / "labels"
        # Try multiple patterns: {stem}.rf.*, {stem}_jpg.rf.*, {stem}_png.rf.*
        for pattern in [f"{image_name}.rf.*.txt", f"{image_name}_jpg.rf.*.txt", f"{image_name}_png.rf.*.txt"]:
            matches = sorted(label_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def parse_components(text: str, w: int, h: int) -> list:
    """Parse YOLO-OBB component labels."""
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


def crop_component(gray: np.ndarray, bbox: tuple, margin_pct: float = 0.3) -> np.ndarray | None:
    """Crop component region with margin for surrounding text."""
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


def encode_image(img: np.ndarray) -> str:
    """Encode image as base64 data URL."""
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    b64 = base64.b64encode(buf).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


BATCH_PROMPT = """You are reading a circuit schematic. I will show you multiple components from the same image.

For each component image (labeled #1, #2, etc.), identify its value from the text label.

Component types: {comp_types}

Return a JSON array with one object per component:
[{{"index": 0, "value": "10k", "unit": "ohm", "confidence": "high"}}, ...]

Examples:
- Resistor: "10k" = 10kΩ, "4.7R" = 4.7Ω, "1M" = 1MΩ
- Capacitor: "100n" = 100nF, "10u" = 10µF
- Inductor: "10m" = 10mH, "100u" = 100µH
- Diode/Transistor: part number like "1N4148"
- Voltage source: "5V", "12V"

If a component has no readable value, use {{"value": null, "unit": null, "confidence": "none"}}.

Return ONLY the JSON array — no explanation."""


def call_vlm_batch(components: list[dict], model: str, api_key: str) -> list[dict]:
    """Send multiple cropped components in one VLM call."""
    import urllib.request

    if not components:
        return []

    # Build message content with multiple images
    content = [{"type": "text", "text": BATCH_PROMPT.format(
        comp_types=", ".join(c["type"] for c in components)
    )}]

    for i, comp in enumerate(components):
        data_url = encode_image(comp["crop"])
        content.append({"type": "text", "text": f"Component #{i} ({comp['type']}):"})
        content.append({"type": "image_url", "image_url": {"url": data_url}})

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
    }

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            raw = result["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
    except Exception as e:
        return [{"value": None, "unit": None, "confidence": "error", "error": str(e)}]


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
    ap.add_argument("--limit", type=int, default=0, help="Max images to process")
    ap.add_argument("--resume", action="store_true", help="Skip processed images")
    ap.add_argument("--model", default="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
                    help="VLM model (OpenRouter)")
    args = ap.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        # Try loading from hermes config
        config_path = Path.home() / ".hermes" / "config.yaml"
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            providers = cfg.get("providers", {})
            for p in providers.values():
                if "openrouter" in str(p.get("name", "")).lower():
                    api_key = p.get("api_key", "")
                    break
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY env var or configure in hermes config")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUT_DIR / "results.jsonl"

    # Discover images
    all_images = sorted(gt_images_dir().glob("*.jpg"))
    print(f"Found {len(all_images)} images in GT set")

    # Load checkpoint
    done = {}
    if args.resume and jsonl_path.exists():
        done = load_checkpoint(jsonl_path)
        print(f"Resuming: {len(done)} images already processed")

    n_img = 0
    t0 = time.perf_counter()

    # Progress bar
    try:
        from tqdm import tqdm
        pbar = tqdm(total=len(all_images), desc="Component OCR", unit="img", initial=len(done))
    except ImportError:
        pbar = None

    for img_path in all_images:
        image_name = img_path.stem
        if image_name in done:
            if pbar:
                pbar.update(1)
            continue
        if args.limit and n_img >= args.limit:
            break

        # Load image and component labels
        gray = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            if pbar:
                pbar.update(1)
            continue
        h, w = gray.shape

        hdc_path = find_hdc_label(image_name)
        if hdc_path is None:
            if pbar:
                pbar.update(1)
            continue

        hdc_text = hdc_path.read_text(encoding="utf-8")
        components = parse_components(hdc_text, w, h)
        if not components:
            if pbar:
                pbar.update(1)
            continue

        # Collect value-type components for batch OCR
        value_components = []
        value_indices = []
        comp_results = {}

        for i, comp in enumerate(components):
            cls = comp["cls"]
            comp_type = COMPONENT_TYPES.get(cls, f"class_{cls}")

            if cls not in VALUE_TYPES:
                comp_results[f"comp_{i}"] = {
                    "type": comp_type,
                    "value": None,
                    "unit": None,
                    "confidence": "skipped",
                }
                continue

            crop = crop_component(gray, comp["bbox"])
            if crop is None:
                comp_results[f"comp_{i}"] = {
                    "type": comp_type,
                    "value": None,
                    "unit": None,
                    "confidence": "no_crop",
                }
                continue

            value_components.append({"type": comp_type, "bbox": comp["bbox"], "crop": crop})
            value_indices.append(i)

        # Batch OCR all value-type components in one VLM call
        if value_components:
            batch_results = call_vlm_batch(value_components, args.model, api_key)
            for j, idx in enumerate(value_indices):
                vlm_result = batch_results[j] if j < len(batch_results) else {"value": None, "confidence": "error"}
                comp_results[f"comp_{idx}"] = {
                    "type": value_components[j]["type"],
                    "bbox": value_components[j]["bbox"],
                    **vlm_result,
                }

        # Save
        record = {
            "image": image_name,
            "components": len(components),
            "values": comp_results,
        }
        with open(jsonl_path, "a") as f:
            f.write(json.dumps(record) + "\n")
        done[image_name] = record
        n_img += 1

        if pbar:
            pbar.update(1)
            pbar.set_postfix(img=n_img, comps=len(components))
        elif n_img % 10 == 0:
            elapsed = time.perf_counter() - t0
            rate = n_img / elapsed if elapsed > 0 else 0
            print(f"  [{n_img}] {elapsed:.0f}s, {rate:.1f} img/s", file=sys.stderr)

    if pbar:
        pbar.close()

    # Summary
    total_comps = sum(r["components"] for r in done.values())
    value_counts = {"high": 0, "medium": 0, "low": 0, "none": 0, "skipped": 0, "error": 0}
    for r in done.values():
        for v in r["values"].values():
            conf = v.get("confidence", "none")
            value_counts[conf] = value_counts.get(conf, 0) + 1

    print(f"\n{'='*60}")
    print(f"COMPONENT OCR RESULTS — {len(done)} images, {total_comps} components")
    print(f"{'='*60}")
    print(f"  High confidence:   {value_counts.get('high', 0)}")
    print(f"  Medium confidence: {value_counts.get('medium', 0)}")
    print(f"  Low confidence:    {value_counts.get('low', 0)}")
    print(f"  No value found:    {value_counts.get('none', 0)}")
    print(f"  Skipped (N/A):     {value_counts.get('skipped', 0)}")
    print(f"  Errors:            {value_counts.get('error', 0)}")
    print(f"{'='*60}")

    # Save summary
    (OUT_DIR / "summary.json").write_text(json.dumps({
        "images": len(done),
        "total_components": total_comps,
        "value_counts": value_counts,
    }, indent=2))

    elapsed = time.perf_counter() - t0
    print(f"\nResults saved to: {OUT_DIR}")
    print(f"Total time: {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

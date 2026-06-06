"""Component value OCR endpoint — VLM-based value extraction."""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import cv2
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# Component class names (from Roboflow data.yaml)
COMPONENT_TYPES = {
    0: "and", 1: "antenna", 2: "capacitor-adjustable", 3: "capacitor-polarized",
    4: "capacitor-unpolarized", 5: "crossover", 6: "crystal", 7: "diac",
    8: "diode", 9: "diode-LED", 10: "diode-thyrector", 11: "diode-zener",
    12: "fuse", 13: "gnd", 14: "inductor", 15: "inductor-ferrite",
    16: "IC", 17: "IC-NE555", 18: "IC-voltage-reg", 19: "junction",
    20: "lamp", 21: "magnetic", 22: "mechanical", 23: "microphone",
    24: "motor", 25: "nand", 26: "nor", 27: "not",
    28: "opamp", 29: "opamp-schmitt", 30: "optical", 31: "optocoupler",
    32: "or", 33: "probe", 34: "probe-current", 35: "probe-voltage",
    36: "relay", 37: "resistor", 38: "resistor-adjustable", 39: "resistor-photo",
    40: "socket", 41: "speaker", 42: "switch", 43: "terminal",
    44: "text", 45: "thyristor", 46: "transformer", 47: "transistor-BJT",
    48: "transistor-FET", 49: "transistor-photo", 50: "triac", 51: "unknown",
    52: "varistor", 53: "voltage-AC", 54: "voltage-battery", 55: "voltage-DC",
    56: "vss", 57: "xor",
}
# Only OCR text labels (class 44) — they ARE the values
# Resistors/caps/inductors are symbols; their values are in nearby text labels
VALUE_TYPES = {44}

PROMPT = """You are reading a text label from a circuit schematic. The label is a {comp_type}.

Read the text exactly as written. Common formats:
- Resistor: "10k" (10kΩ), "4.7R" (4.7Ω), "1M" (1MΩ)
- Capacitor: "100n" (100nF), "10u" (10µF), "22p" (22pF)
- Inductor: "10m" (10mH), "100u" (100µH)
- Voltage: "5V", "12V", "3.3V"
- Part number: "1N4148", "2N2222", "LM741"

Return ONLY a JSON object: {{"value": "the text as written", "unit": "ohm/farad/henry/V/part_number/none", "confidence": "high/medium/low"}}

If no value is visible, return: {{"value": null, "unit": null, "confidence": "none"}}
No explanation — only JSON."""


class OCRRequest(BaseModel):
    image_idx: int = 0
    dataset: str = "gt_labels"
    model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"


def _find_hdc_label(image_name: str, hdc_base: Path) -> Path | None:
    for split in ["train", "valid", "test"]:
        label_dir = hdc_base / split / "labels"
        for pattern in [f"{image_name}.rf.*.txt", f"{image_name}_jpg.rf.*.txt"]:
            matches = sorted(label_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def _parse_components(text: str, w: int, h: int) -> list:
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
        comps.append({"cls": cls, "bbox": bbox})
    return comps


def _crop_component(gray, bbox, margin_pct=0.3):
    h, w = gray.shape
    x1, y1, x2, y2 = bbox
    mx = int((x2 - x1) * margin_pct)
    my = int((y2 - y1) * margin_pct)
    cx1, cy1 = max(0, x1 - mx), max(0, y1 - my)
    cx2, cy2 = min(w, x2 + mx), min(h, y2 + my)
    if cx2 - cx1 < 10 or cy2 - cy1 < 10:
        return None
    return gray[cy1:cy2, cx1:cx2]


def _call_vlm_batch(components: list, model: str, api_key: str) -> list:
    import urllib.request
    if not components:
        return []

    content = [{"type": "text", "text": f"Read the text labels from these circuit components. For each, return value, unit, confidence. Common: 10k=10kΩ, 100n=100nF, 5V=5V. Return JSON array.\n\nComponent types: {', '.join(c['type'] for c in components)}"}]

    for i, comp in enumerate(components):
        _, buf = cv2.imencode(".jpg", comp["crop"], [cv2.IMWRITE_JPEG_QUALITY, 90])
        b64 = base64.b64encode(buf).decode("utf-8")
        content.append({"type": "text", "text": f"\n#{i} ({comp['type']}):"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
    }

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        raw = result["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [parsed]


@router.post("/api/ocr")
def run_ocr(req: OCRRequest):
    import wire_detection.api.deps as deps

    # Get image list
    images = deps.registry.list_images(req.dataset)
    if req.image_idx < 0 or req.image_idx >= len(images):
        return {"error": f"index {req.image_idx} out of range"}

    img_path = images[req.image_idx]
    gray = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return {"error": "could not read image"}
    h, w = gray.shape

    # Find HDC labels
    image_name = img_path.stem
    hdc_base = Path(os.environ.get("HDC_PATH", "/home/claw/circuit-digitization/roboflow_test2"))
    hdc_path = _find_hdc_label(image_name, hdc_base)
    if hdc_path is None:
        return {"error": "no component labels found", "components": []}

    components = _parse_components(hdc_path.read_text(encoding="utf-8"), w, h)

    # Collect value-type components
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    value_comps = []
    value_indices = []
    results = []

    for i, comp in enumerate(components):
        comp_type = COMPONENT_TYPES.get(comp["cls"], f"class_{comp['cls']}")
        if comp["cls"] not in VALUE_TYPES:
            results.append({"index": i, "type": comp_type, "value": None, "confidence": "skipped"})
            continue

        crop = _crop_component(gray, comp["bbox"])
        if crop is None:
            results.append({"index": i, "type": comp_type, "value": None, "confidence": "no_crop"})
            continue

        value_comps.append({"type": comp_type, "bbox": comp["bbox"], "crop": crop})
        value_indices.append(i)

    # Batch VLM OCR
    if value_comps and api_key:
        vlm_results = _call_vlm_batch(value_comps, req.model, api_key)
        for j, idx in enumerate(value_indices):
            vlm_r = vlm_results[j] if j < len(vlm_results) else {"value": None, "confidence": "error"}
            results.insert(idx, {"index": idx, "type": value_comps[j]["type"], **vlm_r})  # type: ignore
    elif value_comps:
        return {"error": "no OPENROUTER_API_KEY set", "components": results}

    return {"image": image_name, "total_components": len(components), "components": results}

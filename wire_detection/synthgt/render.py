"""Render a single synthetic circuit (CircuitSpec) to a clean, schematic-style PNG.

Used by the VLM connectivity experiment (benchmark/vlm_connectivity_eval.py): we feed
the rendered image to a vision model and ask it to recover the netlist, then score its
component-connectivity against the authored ground truth (synthesize.intended_pairs).

Design choices for a FAIR vlm test:
  * white background, black wires, labelled component boxes (R1, V1, ...) -- looks like a
    schematic a human would read;
  * NO pin-index labels and NO net/junction colouring -- those would leak the very
    connectivity structure the model is supposed to infer;
  * components are drawn as rotated rectangles with a type-prefixed designator so the model
    can name them the same way the ground truth does (index order == draw order).

Reuses synthesize_clean() for geometry so the rendered picture is pixel-consistent with the
coordinates the rest of synthgt scores against.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFont

from wire_detection.synthgt.circuits import CircuitSpec
from wire_detection.synthgt.synthesize import synthesize_clean

# designator prefixes -- MUST match the order/types used by intended_pairs (component index)
TYPE_PREFIX = {
    "voltage-DC": "V",
    "resistor": "R",
    "inductor": "L",
    "diode": "D",
    "gnd": "GND",
    "capacitor": "C",
}

_BG = "white"
_WIRE = "black"
_BOX_FILL = "#f2f2f2"
_BOX_BORDER = "black"
_TEXT = "black"


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _rotated_rect(cx, cy, w, h, angle_deg):
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    hw, hh = w / 2, h / 2
    corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    return [
        (cos_a * dx - sin_a * dy + cx, sin_a * dx + cos_a * dy + cy)
        for dx, dy in corners
    ]


def render_circuit(spec: CircuitSpec, out_path: str, size: int = 700) -> str:
    """Render `spec` to a clean schematic PNG at `out_path`. Returns out_path.

    The designator drawn on component i is f"{prefix}{i+1}" -- i.e. R1 is component
    index 0. The VLM prompt tells the model to use exactly these labels so its answer
    maps back to component indices for scoring.
    """
    components, wires, pin_pos = synthesize_clean(spec)

    if spec.comps:
        xs = [c.cx for c in spec.comps]
        ys = [c.cy for c in spec.comps]
        min_x, max_x = min(xs) - 90, max(xs) + 90
        min_y, max_y = min(ys) - 90, max(ys) + 90
    else:
        min_x, max_x, min_y, max_y = 0, 1, 0, 1
    range_x = (max_x - min_x) or 1
    range_y = (max_y - min_y) or 1

    pad = 60
    scale = min((size - 2 * pad) / range_x, (size - 2 * pad) / range_y)

    def tx(x):
        return pad + (x - min_x) * scale

    def ty(y):
        return pad + (y - min_y) * scale

    img = Image.new("RGB", (size, size), _BG)
    draw = ImageDraw.Draw(img)
    font_comp = _font(15)

    # wires
    for (a, b) in wires:
        draw.line([(tx(a[0]), ty(a[1])), (tx(b[0]), ty(b[1]))], fill=_WIRE, width=3)

    # solder dots where >2 wire endpoints coincide (a real schematic cue, not a leak:
    # it marks visible junctions exactly as a hand drawing would)
    from collections import Counter

    ep_count = Counter()
    for (a, b) in wires:
        ep_count[a] += 1
        ep_count[b] += 1
    for ep, cnt in ep_count.items():
        if cnt > 2:
            x, y = tx(ep[0]), ty(ep[1])
            draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=_WIRE)

    # component boxes + designators
    for i, c in enumerate(spec.comps):
        cx, cy = tx(c.cx), ty(c.cy)
        if c.orient == "H":
            raw_w, raw_h = c.size, 30
        else:
            raw_w, raw_h = 30, c.size
        angle = getattr(c, "angle", 0.0) or 0.0
        bw, bh = max(raw_w * scale, 40), max(raw_h * scale, 30)
        corners = _rotated_rect(cx, cy, bw, bh, angle)
        draw.polygon(corners, fill=_BOX_FILL, outline=_BOX_BORDER, width=3)
        prefix = TYPE_PREFIX.get(c.type, "U")
        label = f"{prefix}{i + 1}"
        if c.value and c.value not in ("0", "D_default"):
            label += f" {c.value}"
        draw.text((cx, cy), label, fill=_TEXT, font=font_comp, anchor="mm")

    img.save(out_path, "PNG")
    return out_path


def render_all(out_dir: str) -> dict[str, str]:
    """Render every circuit in the CATALOG to `out_dir/<name>.png`. Returns {name: path}."""
    import os

    from wire_detection.synthgt.circuits import CATALOG

    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    for spec in CATALOG:
        paths[spec.name] = render_circuit(spec, os.path.join(out_dir, f"{spec.name}.png"))
    return paths


if __name__ == "__main__":
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/synthgt_render"
    rendered = render_all(out)
    for name, path in rendered.items():
        print(f"{name}: {path}")

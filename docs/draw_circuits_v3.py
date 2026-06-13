"""Generate visual diagrams of the 9 synthetic eval circuits — v3
Clean component bounding boxes, pin dots, wire endpoints, net junctions.
"""
from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont
from wire_detection.synthgt.circuits import CATALOG
from wire_detection.synthgt.synthesize import synthesize_clean

COLS, ROWS = 3, 4
CELL_W, CELL_H = 440, 370
PAD_X, PAD_Y = 25, 40
MARGIN = 40

W = MARGIN * 2 + COLS * CELL_W + (COLS - 1) * PAD_X
H = MARGIN * 2 + ROWS * CELL_H + (ROWS - 1) * PAD_Y + 80

img = Image.new("RGB", (W, H), "#111827")
draw = ImageDraw.Draw(img)

try:
    FNT = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
    FNT_R = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
    font_title = FNT(20)
    font_sub = FNT_R(12)
    font_comp = FNT(11)
    font_val = FNT_R(10)
    font_pin = FNT_R(9)
    font_label = FNT_R(10)
except Exception:
    font_title = font_sub = font_comp = font_val = font_pin = font_label = ImageFont.load_default()

# Component colors: (fill, border)
TYPE_COL = {
    "voltage-DC": ("#991b1b", "#ef4444"),
    "resistor":   ("#166534", "#22c55e"),
    "inductor":   ("#155e75", "#06b6d4"),
    "diode":      ("#854d0e", "#f59e0b"),
    "gnd":        ("#374151", "#9ca3af"),
}
TYPE_PREFIX = {"voltage-DC": "V", "resistor": "R", "inductor": "L", "diode": "D", "gnd": "GND"}

WIRE_COL = "#64748b"
PIN_COL = "#facc15"
EP_COL = "#f97316"
JUNCTION_COL = "#3b82f6"


def draw_component_box(draw, cx, cy, w, h, ctype, label, value):
    fill, border = TYPE_COL.get(ctype, ("#333", "#666"))
    x1, y1 = cx - w / 2, cy - h / 2
    x2, y2 = cx + w / 2, cy + h / 2

    # Solid filled box with border
    draw.rounded_rectangle([x1, y1, x2, y2], radius=4, fill=fill, outline=border, width=2)

    # Label centered in box
    draw.text((cx, cy - 1), label, fill="#fff", font=font_comp, anchor="mm")
    if value and value not in ("0", "D_default"):
        draw.text((cx, cy + 11), value, fill="#d1d5db", font=font_val, anchor="mm")


def draw_circuit(draw, spec, cell_x, cell_y):
    # Cell background
    draw.rounded_rectangle(
        [cell_x, cell_y, cell_x + CELL_W, cell_y + CELL_H],
        radius=8, fill="#1e293b", outline="#334155", width=1,
    )
    # Title
    draw.text((cell_x + CELL_W // 2, cell_y + 10), spec.name,
              fill="#e94560", font=font_sub, anchor="mt")
    info = f"{len(spec.comps)} comps · {len(spec.nets)} nets · {spec.expect_mA:.1f}mA"
    draw.text((cell_x + CELL_W // 2, cell_y + 24), info,
              fill="#6b7280", font=font_label, anchor="mt")

    components, wires, pin_pos = synthesize_clean(spec)
    if not spec.comps:
        return

    # Compute scale from spec component positions
    xs = [c.cx for c in spec.comps]
    ys = [c.cy for c in spec.comps]
    min_x, max_x = min(xs) - 50, max(xs) + 50
    min_y, max_y = min(ys) - 50, max(ys) + 50
    range_x = max_x - min_x or 1
    range_y = max_y - min_y or 1

    pad = 50
    scale_x = (CELL_W - 2 * pad) / range_x
    scale_y = (CELL_H - 2 * pad - 10) / range_y
    scale = min(scale_x, scale_y)

    def tx(x): return cell_x + pad + (x - min_x) * scale
    def ty(y): return cell_y + pad + 10 + (y - min_y) * scale

    # 1) Draw wires (behind everything)
    for w in wires:
        x1, y1 = tx(w[0][0]), ty(w[0][1])
        x2, y2 = tx(w[1][0]), ty(w[1][1])
        draw.line([(x1, y1), (x2, y2)], fill=WIRE_COL, width=2)

    # 2) Draw wire endpoint dots
    for w in wires:
        for ep in w:
            x, y = tx(ep[0]), ty(ep[1])
            r = 3
            draw.ellipse([x - r, y - r, x + r, y + r], fill=EP_COL)

    # 3) Draw net junction dots (where ≥2 wire endpoints coincide)
    from collections import Counter
    ep_count = Counter()
    for w in wires:
        ep_count[w[0]] += 1
        ep_count[w[1]] += 1
    for ep, cnt in ep_count.items():
        if cnt > 1:
            x, y = tx(ep[0]), ty(ep[1])
            r = 5
            draw.ellipse([x - r, y - r, x + r, y + r], fill=JUNCTION_COL, outline="#1d4ed8", width=1)

    # 4) Draw component bounding boxes (from pipeline format)
    for i, c in enumerate(spec.comps):
        cx, cy = tx(c.cx), ty(c.cy)
        comp_tuple = components[i]
        bbox = comp_tuple[2]  # (x1, y1, x2, y2) in raw coords
        raw_w = bbox[2] - bbox[0]
        raw_h = bbox[3] - bbox[1]
        bw = raw_w * scale
        bh = raw_h * scale
        prefix = TYPE_PREFIX.get(c.type, "?")
        draw_component_box(draw, cx, cy, max(bw, 32), max(bh, 24), c.type,
                           f"{prefix}{i + 1}", c.value)

    # 5) Draw pin dots ON TOP of component boxes
    for (ci, pi), (px, py) in pin_pos.items():
        x, y = tx(px), ty(py)
        r = 4
        draw.ellipse([x - r, y - r, x + r, y + r], fill=PIN_COL, outline="#000", width=1)
        # Small pin label
        draw.text((x + 6, y - 5), f"p{pi}", fill=PIN_COL, font=font_pin, anchor="lm")

    # Note
    note = spec.note[:55] if spec.note else ""
    draw.text((cell_x + CELL_W // 2, cell_y + CELL_H - 8), note,
              fill="#4b5563", font=font_label, anchor="mb")


# Draw all 9
for idx, spec in enumerate(CATALOG):
    row, col = idx // COLS, idx % COLS
    cx = MARGIN + col * (CELL_W + PAD_X)
    cy = MARGIN + 60 + row * (CELL_H + PAD_Y)
    draw_circuit(draw, spec, cx, cy)

# Legend
draw.text((W // 2, 56),
          "■ component bbox   ● pin (yellow)   ● wire endpoint (orange)   ● net junction (blue)",
          fill="#6b7280", font=font_label, anchor="mt")

out = "/home/claw/circuit-digitization/docs/synthgt_catalog_v3.png"
img.save(out, "PNG")
print(f"Saved to {out} ({W}x{H})")

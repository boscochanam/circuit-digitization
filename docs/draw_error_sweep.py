"""Visualize clean vs error-injected wire layouts.
One seed per panel: green = clean wires, red = error-injected wires.
"""
from __future__ import annotations
import math
from PIL import Image, ImageDraw, ImageFont
from wire_detection.synthgt.circuits import CATALOG_BY_NAME
from wire_detection.synthgt.synthesize import (
    synthesize_clean, inject_errors, ERROR_LEVELS,
)

try:
    FNT = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
    FNT_R = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
    font_title = FNT(18)
    font_sub = FNT_R(12)
    font_comp = FNT(11)
    font_pin = FNT_R(9)
    font_label = FNT_R(10)
except Exception:
    font_title = font_sub = font_comp = font_pin = font_label = ImageFont.load_default()

TYPE_COL = {
    "voltage-DC": ("#991b1b", "#ef4444"),
    "resistor":   ("#166534", "#22c55e"),
    "inductor":   ("#155e75", "#06b6d4"),
    "diode":      ("#854d0e", "#f59e0b"),
    "gnd":        ("#374151", "#9ca3af"),
}
TYPE_PREFIX = {"voltage-DC": "V", "resistor": "R", "inductor": "L", "diode": "D", "gnd": "GND"}

WIRE_CLEAN = "#22c55e"
WIRE_ERROR = "#ef4444"
PIN_COL = "#facc15"
EP_CLEAN = "#22c55e"
EP_ERROR = "#f97316"


def rotated_rect(cx, cy, w, h, angle_deg):
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    half_w, half_h = w / 2, h / 2
    corners = [(-half_w, -half_h), (half_w, -half_h),
               (half_w, half_h), (-half_w, half_h)]
    return [(int(cos_a * dx - sin_a * dy + cx),
             int(sin_a * dx + cos_a * dy + cy))
            for dx, dy in corners]


def get_scale(spec, panel_w, panel_h):
    xs = [c.cx for c in spec.comps]
    ys = [c.cy for c in spec.comps]
    min_x, max_x = min(xs) - 80, max(xs) + 80
    min_y, max_y = min(ys) - 80, max(ys) + 80
    range_x = max_x - min_x or 1
    range_y = max_y - min_y or 1
    pad = 45
    sc = min((panel_w - 2 * pad) / range_x, (panel_h - 2 * pad - 10) / range_y)
    def tx(x): return pad + (x - min_x) * sc
    def ty(y): return pad + 10 + (y - min_y) * sc
    return tx, ty, sc


def draw_panel(img, spec, clean_wires, err_wires, pin_pos, cell_x, cell_y, title):
    PW, PH = 480, 360
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([cell_x, cell_y, cell_x + PW, cell_y + PH],
                           radius=8, fill="#1e293b", outline="#334155", width=1)
    draw.text((cell_x + PW // 2, cell_y + 10), title,
              fill="#e94560", font=font_sub, anchor="mt")

    tx, ty, sc = get_scale(spec, PW, PH)
    ox, oy = cell_x, cell_y

    def sx(x): return ox + tx(x)
    def sy(y): return oy + ty(y)

    # Wires (green for clean, red for error)
    wire_col = WIRE_CLEAN if err_wires is clean_wires else WIRE_ERROR
    ep_col = EP_CLEAN if err_wires is clean_wires else EP_ERROR
    for w in err_wires:
        draw.line([(sx(w[0][0]), sy(w[0][1])), (sx(w[1][0]), sy(w[1][1]))],
                  fill=wire_col, width=2)
    for w in err_wires:
        for ep in w:
            r = 3
            draw.ellipse([sx(ep[0])-r, sy(ep[1])-r, sx(ep[0])+r, sy(ep[1])+r],
                         fill=ep_col)

    # Components
    for i, c in enumerate(spec.comps):
        fill, border = TYPE_COL.get(c.type, ("#333", "#666"))
        prefix = TYPE_PREFIX.get(c.type, "?")
        if c.orient == "H":
            raw_w, raw_h = c.size, 30
        else:
            raw_w, raw_h = 30, c.size
        angle = getattr(c, "angle", 0.0) or 0.0
        bw, bh = raw_w * sc, raw_h * sc
        corners = rotated_rect(sx(c.cx), sy(c.cy), max(bw, 28), max(bh, 20), angle)
        draw.polygon(corners, fill=fill, outline=border, width=2)
        draw.text((sx(c.cx), sy(c.cy) - 1), f"{prefix}{i+1}",
                  fill="#fff", font=font_comp, anchor="mm")

    # Pins
    for (ci, pi), (px, py) in pin_pos.items():
        x, y = sx(px), sy(py)
        draw.ellipse([x-4, y-4, x+4, y+4], fill=PIN_COL, outline="#000", width=1)


# Config
circuits = ["divider_rr", "ring6_r", "angled_v", "angled_parallel"]
SEED = 0
LEVELS = [0, 1, 2, 3, 4]

COLS = len(LEVELS)
ROWS = len(circuits)
PW, PH = 480, 360
PAD_X, PAD_Y = 12, 12
MARGIN = 30

W = MARGIN * 2 + COLS * PW + (COLS - 1) * PAD_X
H = MARGIN * 2 + ROWS * PH + (ROWS - 1) * PAD_Y + 50

img = Image.new("RGB", (W, H), "#111827")
draw = ImageDraw.Draw(img)

draw.text((W // 2, 12), "Green = clean wires · Red = error-injected (seed 0)",
          fill="#e94560", font=font_title, anchor="mt")
draw.text((W // 2, 32), "Orange dots = displaced endpoints · Yellow dots = pin positions",
          fill="#6b7280", font=font_label, anchor="mt")

for row, cname in enumerate(circuits):
    spec = CATALOG_BY_NAME[cname]
    components, clean_wires, pin_pos = synthesize_clean(spec)

    for col, sev in enumerate(LEVELS):
        cx = MARGIN + col * (PW + PAD_X)
        cy = MARGIN + 50 + row * (PH + PAD_Y)

        if sev == 0:
            err_wires = clean_wires
            title = "Clean (L0)"
        else:
            err_wires = inject_errors(clean_wires, sev, SEED, pin_pos=pin_pos)
            p = ERROR_LEVELS[sev]
            title = f"L{sev}: jit={p[0]:.0f} cut={p[1]:.0f} anchor={p[4]:.0%}/{p[5]:.0f}px"

        draw_panel(img, spec, clean_wires, err_wires, pin_pos, cx, cy, title)

out = "/home/claw/circuit-digitization/docs/synthgt_error_sweep.png"
img.save(out, "PNG")
print(f"Saved to {out} ({W}x{H})")

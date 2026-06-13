"""Error sweep visualization: clean → L4 for key circuits.
One seed per panel, green=clean wires, red=error-injected.
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
    font_title = FNT(16)
    font_sub = FNT_R(11)
    font_comp = FNT(10)
    font_pin = FNT_R(8)
    font_label = FNT_R(9)
except Exception:
    font_title = font_sub = font_comp = font_pin = font_label = ImageFont.load_default()

TYPE_COL = {
    "voltage-DC": ("#7f1d1d", "#ef4444"),
    "resistor":   ("#14532d", "#22c55e"),
    "inductor":   ("#164e63", "#06b6d4"),
    "diode":      ("#78350f", "#f59e0b"),
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


def get_tx_ty(spec, pw, ph):
    xs = [c.cx for c in spec.comps]
    ys = [c.cy for c in spec.comps]
    min_x, max_x = min(xs) - 80, max(xs) + 80
    min_y, max_y = min(ys) - 80, max(ys) + 80
    range_x = max_x - min_x or 1
    range_y = max_y - min_y or 1
    pad = 40
    sc = min((pw - 2 * pad) / range_x, (ph - 2 * pad - 10) / range_y)
    def tx(x): return pad + (x - min_x) * sc
    def ty(y): return pad + 10 + (y - min_y) * sc
    return tx, ty, sc


def draw_panel(img, spec, wires, pin_pos, cx, cy, pw, ph, title):
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([cx, cy, cx + pw, cy + ph],
                           radius=6, fill="#1e293b", outline="#334155", width=1)
    draw.text((cx + pw // 2, cy + 8), title, fill="#e94560", font=font_sub, anchor="mt")

    tx, ty, sc = get_tx_ty(spec, pw, ph)
    ox, oy = cx, cy
    sx = lambda x: ox + tx(x)
    sy = lambda y: oy + ty(y)

    # Wires
    for w in wires:
        draw.line([(sx(w[0][0]), sy(w[0][1])), (sx(w[1][0]), sy(w[1][1]))],
                  fill=WIRE_ERROR if wires is not spec._clean else WIRE_CLEAN, width=2)
    # Endpoints
    for w in wires:
        for ep in w:
            r = 3
            col = EP_ERROR if wires is not spec._clean else EP_CLEAN
            draw.ellipse([sx(ep[0])-r, sy(ep[1])-r, sx(ep[0])+r, sy(ep[1])+r], fill=col)

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
        corners = rotated_rect(sx(c.cx), sy(c.cy), max(bw, 24), max(bh, 18), angle)
        draw.polygon(corners, fill=fill, outline=border, width=2)
        draw.text((sx(c.cx), sy(c.cy)), f"{prefix}{i+1}",
                  fill="#fff", font=font_comp, anchor="mm")

    # Pins
    for (ci, pi), (px, py) in pin_pos.items():
        x, y = sx(px), sy(py)
        draw.ellipse([x-3, y-3, x+3, y+3], fill=PIN_COL, outline="#000", width=1)


# Config
circuits = [
    ("parallel_rr", "Easy — parallel R"),
    ("divider_rr", "Series divider"),
    ("ring6_r", "Hard — 6-component ring"),
    ("angled_ring4", "Hard — diamond + angles"),
    ("angled_parallel", "Hardest — angled parallel"),
]
SEED = 0
LEVELS = [0, 1, 2, 3, 4]

COLS = len(LEVELS)
ROWS = len(circuits)
PW, PH = 350, 280
PAD_X, PAD_Y = 10, 10
MARGIN = 25

W = MARGIN * 2 + COLS * PW + (COLS - 1) * PAD_X
H = MARGIN * 2 + ROWS * PH + (ROWS - 1) * PAD_Y + 45

img = Image.new("RGB", (W, H), "#111827")
draw = ImageDraw.Draw(img)

draw.text((W // 2, 8), "Error sweep: green=clean · red=error (seed 0)",
          fill="#e94560", font=font_title, anchor="mt")
draw.text((W // 2, 26), "Orange dots=displaced endpoints · Yellow dots=pin positions",
          fill="#6b7280", font=font_label, anchor="mt")

for row, (cname, label) in enumerate(circuits):
    spec = CATALOG_BY_NAME[cname]
    components, clean_wires, pin_pos = synthesize_clean(spec)

    for col, sev in enumerate(LEVELS):
        cx = MARGIN + col * (PW + PAD_X)
        cy = MARGIN + 40 + row * (PH + PAD_Y)

        if sev == 0:
            err_wires = clean_wires
            title = "Clean"
        else:
            err_wires = inject_errors(clean_wires, sev, SEED, pin_pos=pin_pos)
            p = ERROR_LEVELS[sev]
            title = f"L{sev} (jit={p[0]:.0f} cut={p[1]:.0f} anchor={p[4]:.0%}/{p[5]:.0f}px)"

        # Tag spec for panel drawing
        spec._clean = clean_wires
        draw_panel(img, spec, err_wires, pin_pos, cx, cy, PW, PH, title)

    # Row label
    draw.text((MARGIN - 5, MARGIN + 40 + row * (PH + PAD_Y) + PH // 2),
              label, fill="#e94560", font=font_label, anchor="rm")

out = "/home/claw/circuit-digitization/docs/synthgt_error_sweep.png"
img.save(out, "PNG")
print(f"Saved to {out} ({W}x{H})")

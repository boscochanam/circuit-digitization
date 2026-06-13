"""Before/after join visualization: clean → detected (error-injected) → joined.
Shows what the algorithm recovers from the corrupted input.
"""
from __future__ import annotations
import math
from PIL import Image, ImageDraw, ImageFont
from wire_detection.synthgt.circuits import CATALOG_BY_NAME
from wire_detection.synthgt.synthesize import (
    synthesize_clean, inject_errors, ERROR_LEVELS,
)
from wire_detection.core.join_strategies import run_strategy

try:
    FNT = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
    FNT_R = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
    font_title = FNT(16)
    font_sub = FNT_R(11)
    font_comp = FNT(10)
    font_label = FNT_R(9)
except Exception:
    font_title = font_sub = font_comp = font_label = ImageFont.load_default()

TYPE_COL = {
    "voltage-DC": ("#7f1d1d", "#ef4444"),
    "resistor":   ("#14532d", "#22c55e"),
    "inductor":   ("#164e63", "#06b6d4"),
    "diode":      ("#78350f", "#f59e0b"),
    "gnd":        ("#374151", "#9ca3af"),
}
TYPE_PREFIX = {"voltage-DC": "V", "resistor": "R", "inductor": "L", "diode": "D", "gnd": "GND"}

PIN_COL = "#facc15"
EP_COL = "#f97316"


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


def draw_components(draw, spec, pin_pos, tx, ty, sc, ox, oy):
    """Draw component polygons and pin dots."""
    sx = lambda x: ox + tx(x)
    sy = lambda y: oy + ty(y)
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
    for (ci, pi), (px, py) in pin_pos.items():
        x, y = sx(px), sy(py)
        draw.ellipse([x-3, y-3, x+3, y+3], fill=PIN_COL, outline="#000", width=1)


def draw_wires(draw, wires, tx, ty, ox, oy, color, ep_color, width=2):
    sx = lambda x: ox + tx(x)
    sy = lambda y: oy + ty(y)
    for w in wires:
        draw.line([(sx(w[0][0]), sy(w[0][1])), (sx(w[1][0]), sy(w[1][1]))],
                  fill=color, width=width)
    for w in wires:
        for ep in w:
            r = 3
            draw.ellipse([sx(ep[0])-r, sy(ep[1])-r, sx(ep[0])+r, sy(ep[1])+r], fill=ep_color)


def make_panel(img, spec, detected_wires, joined_wires, pin_pos, cx, cy, pw, ph,
               title, show_joined_edges=False, joined_edges=None):
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([cx, cy, cx + pw, cy + ph],
                           radius=6, fill="#1e293b", outline="#334155", width=1)
    draw.text((cx + pw // 2, cy + 8), title, fill="#e94560", font=font_sub, anchor="mt")

    tx, ty, sc = get_tx_ty(spec, pw, ph)
    ox, oy = cx, cy

    # Detected wires (orange/red)
    draw_wires(draw, detected_wires, tx, ty, ox, oy, "#ef4444", EP_COL)

    # Joined edges (cyan) — connections the algorithm made between pins
    if show_joined_edges and joined_edges:
        sx = lambda x: ox + tx(x)
        sy = lambda y: oy + ty(y)
        for (a, b) in joined_edges:
            draw.line([(sx(a[0]), sy(a[1])), (sx(b[0]), sy(b[1]))],
                      fill="#06b6d4", width=2)

    # Components and pins on top
    draw_components(draw, spec, pin_pos, tx, ty, sc, ox, oy)


def extract_joined_edges(joined_wires, pin_pos, spec):
    """Extract which pin pairs the join algorithm connected.
    Returns list of ((px1,py1), (px2,py2)) for each wire after joining."""
    edges = []
    for w in joined_wires:
        edges.append((w[0], w[1]))
    return edges


# Config
circuits = [
    ("divider_rr", "Series divider"),
    ("ring6_r", "6-component ring"),
    ("angled_ring4", "Diamond + angles"),
    ("angled_parallel", "Angled parallel"),
]
SEED = 2
SEV = 3  # heavy error — enough to break things but not total chaos

PW, PH = 350, 280
COLS = 3  # Ground truth | Detected | Joined
ROWS = len(circuits)
PAD_X, PAD_Y = 10, 10
MARGIN = 25

W = MARGIN * 2 + COLS * PW + (COLS - 1) * PAD_X
H = MARGIN * 2 + ROWS * PH + (ROWS - 1) * PAD_Y + 50

img = Image.new("RGB", (W, H), "#111827")
draw = ImageDraw.Draw(img)

draw.text((W // 2, 8), "Ground truth → Detected (L3 error) → Joined (graph_rescue)",
          fill="#e94560", font=font_title, anchor="mt")
draw.text((W // 2, 26),
          "Green = ground truth · Orange = detected wires · Cyan = algorithm recovery",
          fill="#6b7280", font=font_label, anchor="mt")

# Column headers
for col, label in enumerate(["Ground Truth", "Detected (L3)", "Joined (graph_rescue)"]):
    cx = MARGIN + col * (PW + PAD_X) + PW // 2
    draw.text((cx, 40), label, fill="#94a3b8", font=font_label, anchor="mt")

for row, (cname, label) in enumerate(circuits):
    spec = CATALOG_BY_NAME[cname]
    components, clean_wires, pin_pos = synthesize_clean(spec)
    err_wires = inject_errors(clean_wires, SEV, SEED, pin_pos=pin_pos)
    _, joined_net = run_strategy("graph_rescue", err_wires, components)

    # Classify wires using the actual join result
    connected = joined_net.connected_wires()
    recovered = [w for i, w in enumerate(err_wires) if i in connected]
    missed = [w for i, w in enumerate(err_wires) if i not in connected]

    # Ground truth
    make_panel(img, spec, clean_wires, clean_wires, pin_pos,
               MARGIN, MARGIN + 50 + row * (PH + PAD_Y), PW, PH,
               "Ground Truth")

    # Detected (all error wires)
    make_panel(img, spec, err_wires, err_wires, pin_pos,
               MARGIN + 1 * (PW + PAD_X), MARGIN + 50 + row * (PH + PAD_Y), PW, PH,
               f"Detected ({len(err_wires)} wires)")

    # Joined — recovered wires in green, missed in dim red
    panel_cx = MARGIN + 2 * (PW + PAD_X)
    panel_cy = MARGIN + 50 + row * (PH + PAD_Y)
    draw.rounded_rectangle([panel_cx, panel_cy, panel_cx + PW, panel_cy + PH],
                           radius=6, fill="#1e293b", outline="#334155", width=1)
    draw.text((panel_cx + PW // 2, panel_cy + 8),
              f"Joined (recovered {len(recovered)}/{len(clean_wires)})",
              fill="#e94560", font=font_sub, anchor="mt")

    tx, ty, sc = get_tx_ty(spec, PW, PH)
    ox, oy = panel_cx, panel_cy
    # Recovered wires (green)
    draw_wires(draw, recovered, tx, ty, ox, oy, "#22c55e", "#22c55e")
    # Missed wires (dim red, dashed feel)
    draw_wires(draw, missed, tx, ty, ox, oy, "#7f1d1d", "#7f1d1d", width=1)
    draw_components(draw, spec, pin_pos, tx, ty, sc, ox, oy)

    # Row label
    draw.text((MARGIN - 5, MARGIN + 50 + row * (PH + PAD_Y) + PH // 2),
              label, fill="#e94560", font=font_label, anchor="rm")

out = "/home/claw/circuit-digitization/docs/synthgt_join_demo.png"
img.save(out, "PNG")
print(f"Saved to {out} ({W}x{H})")

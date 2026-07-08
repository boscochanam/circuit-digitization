"""Detailed view of ring6_r showing why error endpoints don't connect.

Shows:
- Component bboxes (colored boxes)
- Pin positions (yellow dots with labels)
- Error-injected wire endpoints (red/orange dots)
- Join radius circles around each pin (30px)
- Distance labels from each endpoint to nearest pin
"""
from __future__ import annotations
import math
from PIL import Image, ImageDraw, ImageFont
from wire_detection.synthgt.circuits import CATALOG_BY_NAME
from wire_detection.synthgt.synthesize import synthesize_clean, inject_errors
from wire_detection.paths import DOCS_DIR

try:
    FNT = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
    FNT_R = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
except Exception:
    FNT = FNT_R = lambda s: ImageFont.load_default()

font_title = FNT(16)
font_comp = FNT(11)
font_pin = FNT_R(9)
font_dist = FNT(9)
font_ep = FNT(8)

JOIN_RADIUS = 30

TYPE_COL = {
    "voltage-DC": ("#7f1d1d", "#ef4444"),
    "resistor":   ("#14532d", "#22c55e"),
}
TYPE_PREFIX = {"voltage-DC": "V", "resistor": "R"}

spec = CATALOG_BY_NAME['ring6_r']
components, clean_wires, pin_pos = synthesize_clean(spec)
err_wires = inject_errors(clean_wires, 3, 0, pin_pos=pin_pos)

# Scale up for visibility
SCALE = 3
PAD = 60

# Compute bounds
all_x = [c.cx for c in spec.comps] + [p[0] for p in pin_pos.values()]
all_y = [c.cy for c in spec.comps] + [p[1] for p in pin_pos.values()]
min_x, max_x = min(all_x) - 100, max(all_x) + 100
min_y, max_y = min(all_y) - 100, max(all_y) + 100

W = int((max_x - min_x) * SCALE + 2 * PAD)
H = int((max_y - min_y) * SCALE + 2 * PAD) + 60

def sx(x): return int(PAD + (x - min_x) * SCALE)
def sy(y): return int(PAD + 60 + (y - min_y) * SCALE)

img = Image.new("RGB", (W, H), "#111827")
draw = ImageDraw.Draw(img)

# Title
draw.text((W // 2, 12), "ring6_r — Why endpoints don't join (L3, seed=0)", fill="#e94560", font=font_title, anchor="mt")
draw.text((W // 2, 34), f"Join radius = {JOIN_RADIUS}px  ·  Yellow circles = pin reach", fill="#6b7280", font=font_pin, anchor="mt")

# Draw join radius circles around each pin (faint)
for (ci, pi), (px, py) in pin_pos.items():
    x, y = sx(px), sy(py)
    r = JOIN_RADIUS * SCALE
    draw.ellipse([x-r, y-r, x+r, y+r], outline="#facc1530", width=1)

# Draw components
for i, c in enumerate(spec.comps):
    fill, border = TYPE_COL.get(c.type, ("#333", "#666"))
    prefix = TYPE_PREFIX.get(c.type, "?")
    if c.orient == "H":
        raw_w, raw_h = c.size, 30
    else:
        raw_w, raw_h = 30, c.size
    x1, y1 = sx(c.cx - raw_w//2), sy(c.cy - raw_h//2)
    x2, y2 = sx(c.cx + raw_w//2), sy(c.cy + raw_h//2)
    draw.rectangle([x1, y1, x2, y2], fill=fill, outline=border, width=2)
    draw.text((sx(c.cx), sy(c.cy)), f"{prefix}{i+1}", fill="#fff", font=font_comp, anchor="mm")

# Draw pins with labels
for (ci, pi), (px, py) in pin_pos.items():
    x, y = sx(px), sy(py)
    draw.ellipse([x-5, y-5, x+5, y+5], fill="#facc15", outline="#000", width=1)
    draw.text((x+8, y-8), f"P{ci},{pi}", fill="#facc15", font=font_pin, anchor="lt")

# Draw error wires
WIRE_COLORS = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#06b6d4", "#a855f7"]
for i, w in enumerate(err_wires):
    color = WIRE_COLORS[i % len(WIRE_COLORS)]
    draw.line([(sx(w[0][0]), sy(w[0][1])), (sx(w[1][0]), sy(w[1][1]))],
              fill=color, width=3)
    # Endpoints
    for ep in w:
        x, y = sx(ep[0]), sy(ep[1])
        draw.ellipse([x-4, y-4, x+4, y+4], fill=color, outline="#fff", width=1)

# Distance annotations for each endpoint
for i, w in enumerate(err_wires):
    color = WIRE_COLORS[i % len(WIRE_COLORS)]
    for ep_idx, ep in enumerate(w):
        # Find nearest pin
        nearest_key = min(pin_pos.keys(), key=lambda k: math.hypot(ep[0]-pin_pos[k][0], ep[1]-pin_pos[k][1]))
        nearest_pin = pin_pos[nearest_key]
        dist = math.hypot(ep[0]-nearest_pin[0], ep[1]-nearest_pin[1])
        
        x, y = sx(ep[0]), sy(ep[1])
        # Draw line to nearest pin
        px, py = sx(nearest_pin[0]), sy(nearest_pin[1])
        draw.line([(x, y), (px, py)], fill=color + "60", width=1)
        
        # Distance label
        mid_x = (x + px) // 2
        mid_y = (y + py) // 2
        status = "OK" if dist <= JOIN_RADIUS else "TOO FAR"
        dist_color = "#22c55e" if dist <= JOIN_RADIUS else "#ef4444"
        draw.text((mid_x, mid_y - 8), f"{dist:.0f}px {status}", fill=dist_color, font=font_dist, anchor="mb")

# Legend
ly = H - 30
draw.text((PAD, ly), "Lines show distance from each endpoint to its nearest pin. "
          "Only endpoints within 30px connect.", fill="#9ca3af", font=font_pin, anchor="lt")

out = str(DOCS_DIR / "synthgt_ring6_detail.png")
img.save(out, "PNG")
print(f"Saved {out} ({W}x{H})")

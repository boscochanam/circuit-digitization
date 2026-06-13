"""Generate visual diagrams of the 9 synthetic eval circuits — with component
bounding boxes, pin positions, and wire endpoints clearly shown.

Purpose: audit whether the synthetic layout looks like real detector output
(component OBBs, wire segments between pin positions, endpoint dots).
"""
from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont
from wire_detection.synthgt.circuits import CATALOG
from wire_detection.synthgt.synthesize import (
    build_components, pin_positions, synthesize_clean, inject_errors,
    ERROR_LEVELS,
)

# Layout: 3 columns x 3 rows
COLS, ROWS = 3, 3
CELL_W, CELL_H = 440, 380
PAD_X, PAD_Y = 25, 40
MARGIN = 40

W = MARGIN * 2 + COLS * CELL_W + (COLS - 1) * PAD_X
H = MARGIN * 2 + ROWS * CELL_H + (ROWS - 1) * PAD_Y + 70

img = Image.new("RGB", (W, H), "#111827")
draw = ImageDraw.Draw(img)

try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    font_comp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
    font_val = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    font_pin = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
    font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
except Exception:
    font_title = font_sub = font_comp = font_val = font_pin = font_label = ImageFont.load_default()

# Colors
C = {
    "voltage-DC": ("#ef4444", "#7f1d1d"),   # red fill/border
    "resistor":   ("#22c55e", "#14532d"),    # green
    "inductor":   ("#06b6d4", "#164e63"),    # cyan
    "diode":      ("#f59e0b", "#78350f"),    # amber
    "gnd":        ("#9ca3af", "#374151"),    # grey
}
WIRE_COL = "#94a3b8"
PIN_COL = "#facc15"       # yellow pin dots
EP_COL = "#f97316"        # orange wire endpoint dots
NET_DOT = "#3b82f6"       # blue net junction dot
GRID_COL = "#1f2937"      # subtle grid
bbox_outline = "#475569"  # bounding box outline (dim)

def draw_component_box(draw, cx, cy, w, h, ctype, label, value):
    """Draw component bounding box with fill, outline, and label."""
    fill, border = C.get(ctype, ("#333", "#555"))
    x1, y1 = cx - w // 2, cy - h // 2
    x2, y2 = cx + w // 2, cy + h // 2
    
    # Filled semi-transparent box (simulate with lighter fill)
    draw.rounded_rectangle([x1, y1, x2, y2], radius=3, fill=fill + "33", outline=border, width=2)
    
    # Cross-hatch inside to show "this is a component region"
    for i in range(0, int(w), 8):
        draw.line([(x1 + i, y1), (x1 + i - h * 0.3, y2)], fill=border, width=1)
    
    # Component symbol in center
    sym = {"voltage-DC": "⚡", "resistor": "⏛", "inductor": "⌇", "diode": "▶", "gnd": "⏚"}.get(ctype, "?")
    draw.text((cx, cy - 2), label, fill="#fff", font=font_comp, anchor="mm")
    
    # Value below
    if value and value not in ("0", "D_default"):
        draw.text((cx, cy + 10), value, fill="#d1d5db", font=font_val, anchor="mm")

def draw_pin(draw, x, y, pin_name, comp_label):
    """Draw a pin as a bright dot with label."""
    r = 4
    draw.ellipse([x - r, y - r, x + r, y + r], fill=PIN_COL, outline="#000", width=1)
    draw.text((x + 7, y - 3), pin_name, fill=PIN_COL, font=font_pin, anchor="lm")

def draw_wire(draw, x1, y1, x2, y2):
    """Draw a wire with endpoint markers."""
    draw.line([(x1, y1), (x2, y2)], fill=WIRE_COL, width=2)
    # Endpoint dots
    for px, py in [(x1, y1), (x2, y2)]:
        r = 3
        draw.ellipse([px - r, py - r, px + r, py + r], fill=EP_COL)

def draw_circuit(draw, spec, cell_x, cell_y):
    """Draw one circuit in its cell with full detail."""
    # Cell background
    draw.rounded_rectangle(
        [cell_x, cell_y, cell_x + CELL_W, cell_y + CELL_H],
        radius=8, fill="#1e293b", outline="#334155", width=1
    )
    
    # Title
    draw.text((cell_x + CELL_W // 2, cell_y + 10), spec.name, fill="#e94560", font=font_sub, anchor="mt")
    info = f"{len(spec.comps)} comps · {len(spec.nets)} nets · {spec.expect_mA:.1f}mA"
    draw.text((cell_x + CELL_W // 2, cell_y + 24), info, fill="#6b7280", font=font_label, anchor="mt")
    
    # Synthesize clean layout
    components, wires, pin_pos = synthesize_clean(spec)
    
    # Compute scale
    if not spec.comps:
        return
    xs = [c.cx for c in spec.comps]
    ys = [c.cy for c in spec.comps]
    min_x, max_x = min(xs) - 40, max(xs) + 40
    min_y, max_y = min(ys) - 40, max(ys) + 40
    range_x = max_x - min_x or 1
    range_y = max_y - min_y or 1
    
    pad = 50
    scale_x = (CELL_W - 2 * pad) / range_x
    scale_y = (CELL_H - 2 * pad - 10) / range_y
    scale = min(scale_x, scale_y)
    
    def tx(x): return cell_x + pad + (x - min_x) * scale
    def ty(y): return cell_y + pad + 10 + (y - min_y) * scale
    
    # Draw wires (behind components)
    for w in wires:
        draw_wire(draw, tx(w[0][0]), ty(w[0][1]), tx(w[1][0]), ty(w[1][1]))
    
    # Draw net junction dots (where multiple wires meet)
    from collections import Counter
    endpoint_counts = Counter()
    for w in wires:
        endpoint_counts[(w[0])] += 1
        endpoint_counts[(w[1])] += 1
    for ep, count in endpoint_counts.items():
        if count > 1:
            x, y = tx(ep[0]), ty(ep[1])
            r = 5
            draw.ellipse([x - r, y - r, x + r, y + r], fill=NET_DOT, outline="#1d4ed8", width=1)
    
    # Draw components (on top of wires)
    for i, c in enumerate(spec.comps):
        cx, cy = tx(c.cx), ty(c.cy)
        # Component bbox from the pipeline format: (cls, vertices, bbox)
        comp_tuple = components[i]
        bbox = comp_tuple[2]  # (x1, y1, x2, y2)
        bw = (bbox[2] - bbox[0]) * scale
        bh = (bbox[3] - bbox[1]) * scale
        
        draw_component_box(draw, cx, cy, max(bw, 30), max(bh, 24), c.type,
                          f"{c.type.split('-')[0][0].upper()}{i+1}", c.value)
    
    # Draw pins (on top of everything)
    for (ci, pi), (px, py) in pin_pos.items():
        draw_pin(draw, tx(px), ty(py), f"p{pi}", f"{spec.comps[ci].type[0].upper()}{ci+1}")
    
    # Legend line at bottom
    note = spec.note[:55] if spec.note else ""
    draw.text((cell_x + CELL_W // 2, cell_y + CELL_H - 8), note, fill="#4b5563", font=font_label, anchor="mb")

# Draw all 9 circuits
for idx, spec in enumerate(CATALOG):
    row = idx // COLS
    col = idx % COLS
    cx = MARGIN + col * (CELL_W + PAD_X)
    cy = MARGIN + 60 + row * (CELL_H + PAD_Y)
    draw_circuit(draw, spec, cx, cy)

# Legend at top
ly = 58
draw.text((W // 2, ly + 52), "Yellow = pins · Orange = wire endpoints · Blue = net junction · Hatched box = component bbox", fill="#6b7280", font=font_label, anchor="mt")

out = "/home/claw/circuit-digitization/docs/synthgt_catalog_v2.png"
img.save(out, "PNG")
print(f"Saved to {out} ({W}x{H})")

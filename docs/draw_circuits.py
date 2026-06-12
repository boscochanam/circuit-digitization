"""Generate visual diagrams of the 9 synthetic eval circuits."""
from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont
from wire_detection.synthgt.circuits import CATALOG

# Layout: 3 columns x 3 rows
COLS, ROWS = 3, 3
CELL_W, CELL_H = 420, 320
PAD_X, PAD_Y = 30, 50
MARGIN = 40

W = MARGIN * 2 + COLS * CELL_W + (COLS - 1) * PAD_X
H = MARGIN * 2 + ROWS * CELL_H + (ROWS - 1) * PAD_Y + 60  # extra for title

img = Image.new("RGB", (W, H), "#1a1a2e")
draw = ImageDraw.Draw(img)

try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    font_comp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    font_val = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
except:
    font_title = font_sub = font_comp = font_val = font_label = ImageFont.load_default()

# Colors
COL_V = "#e74c3c"    # voltage source - red
COL_R = "#2ecc71"    # resistor - green
COL_L = "#00bcd4"    # inductor - cyan
COL_D = "#f39c12"    # diode - yellow
COL_GND = "#95a5a6"  # gnd - grey
COL_WIRE = "#ecf0f1"  # wire - light
COL_BG = "#16213e"    # cell bg
COL_TEXT = "#ecf0f1"
COL_NET = "#3498db"   # net labels

TYPE_COLORS = {
    "voltage-DC": COL_V, "resistor": COL_R, "inductor": COL_L,
    "diode": COL_D, "gnd": COL_GND,
}
TYPE_SYMBOLS = {
    "voltage-DC": "V", "resistor": "R", "inductor": "L",
    "diode": "D", "gnd": "GND",
}

# Title
draw.text((W // 2, 15), "Synthetic Eval — 9 Ground-Truth Circuits", fill="#e94560", font=font_title, anchor="mt")
draw.text((W // 2, 42), "Author a netlist → lay out as coords → inject error → run real join + SPICE → score", fill="#888", font=font_sub, anchor="mt")

def draw_component(draw, cx, cy, ctype, label, value, size=28):
    """Draw a component symbol at (cx, cy)."""
    col = TYPE_COLORS.get(ctype, "#fff")
    sym = TYPE_SYMBOLS.get(ctype, "?")
    
    if ctype == "voltage-DC":
        # Circle with + and -
        r = size // 2
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=2)
        draw.text((cx, cy - 4), "+", fill=col, font=font_comp, anchor="mm")
        draw.text((cx, cy + 8), "−", fill=col, font=font_comp, anchor="mm")
    elif ctype == "resistor":
        # Zigzag
        r = size // 2
        pts = []
        for i in range(7):
            x = cx - r + i * (2 * r) / 6
            y = cy + (6 if i % 2 == 0 else -6)
            pts.append((x, y))
        draw.line(pts, fill=col, width=2)
    elif ctype == "inductor":
        # Coil bumps
        r = size // 2
        for i in range(3):
            x0 = cx - r + i * (2 * r) / 3
            x1 = cx - r + (i + 1) * (2 * r) / 3
            draw.arc([x0, cy - 8, x1, cy + 8], 180, 360, fill=col, width=2)
    elif ctype == "diode":
        # Triangle + bar
        r = size // 2
        draw.polygon([(cx - r, cy - r), (cx - r, cy + r), (cx + r, cy)], outline=col, fill=None)
        draw.line([(cx + r, cy - r), (cx + r, cy + r)], fill=col, width=2)
    elif ctype == "gnd":
        # Three horizontal lines
        for i in range(3):
            w = 12 - i * 4
            y = cy - 4 + i * 5
            draw.line([(cx - w, y), (cx + w, y)], fill=col, width=2)
    
    # Label below
    draw.text((cx, cy + size // 2 + 8), f"{label}", fill=COL_TEXT, font=font_comp, anchor="mt")
    if value and value != "0":
        draw.text((cx, cy + size // 2 + 22), f"{value}", fill="#aaa", font=font_val, anchor="mt")

def draw_wire(draw, x1, y1, x2, y2):
    """Draw a wire between two points."""
    draw.line([(x1, y1), (x2, y2)], fill=COL_WIRE, width=2)

def draw_net_label(draw, x, y, text):
    draw.text((x, y), text, fill=COL_NET, font=font_label, anchor="mm")

def draw_circuit(draw, spec, cell_x, cell_y):
    """Draw one circuit in its cell."""
    # Cell background
    draw.rounded_rectangle(
        [cell_x, cell_y, cell_x + CELL_W, cell_y + CELL_H],
        radius=8, fill=COL_BG, outline="#333", width=1
    )
    
    # Title
    draw.text((cell_x + CELL_W // 2, cell_y + 12), spec.name, fill="#e94560", font=font_sub, anchor="mt")
    info = f"{len(spec.comps)} comps · {len(spec.nets)} nets · {spec.expect_mA:.1f}mA"
    draw.text((cell_x + CELL_W // 2, cell_y + 28), info, fill="#888", font=font_label, anchor="mt")
    
    # Compute scale to fit components in cell
    if not spec.comps:
        return
    xs = [c.cx for c in spec.comps]
    ys = [c.cy for c in spec.comps]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    range_x = max_x - min_x or 1
    range_y = max_y - min_y or 1
    
    # Map to cell with padding
    pad = 55
    scale_x = (CELL_W - 2 * pad) / range_x
    scale_y = (CELL_H - 2 * pad - 20) / range_y
    scale = min(scale_x, scale_y)
    
    def tx(x): return cell_x + pad + (x - min_x) * scale
    def ty(y): return cell_y + pad + 20 + (y - min_y) * scale
    
    # Draw wires first (nets)
    from wire_detection.synthgt.synthesize import build_components, pin_positions
    components = build_components(spec)
    pin_pos = pin_positions(components)
    
    for net in spec.nets:
        pts = sorted({pin_pos[m] for m in net})
        for i in range(len(pts) - 1):
            draw_wire(draw, tx(pts[i][0]), ty(pts[i][1]), tx(pts[i+1][0]), ty(pts[i+1][1]))
        # Draw net node dot
        if len(pts) >= 2:
            mid_x = sum(p[0] for p in pts) / len(pts)
            mid_y = sum(p[1] for p in pts) / len(pts)
    
    # Draw components on top
    for i, c in enumerate(spec.comps):
        cx, cy = tx(c.cx), ty(c.cy)
        draw_component(draw, cx, cy, c.type, f"{TYPE_SYMBOLS.get(c.type, '?')}{i+1}", c.value)
    
    # Note at bottom
    if spec.note:
        note = spec.note[:60]
        draw.text((cell_x + CELL_W // 2, cell_y + CELL_H - 10), note, fill="#666", font=font_label, anchor="mb")

# Draw all 9 circuits
for idx, spec in enumerate(CATALOG):
    row = idx // COLS
    col = idx % COLS
    cx = MARGIN + col * (CELL_W + PAD_X)
    cy = MARGIN + 55 + row * (CELL_H + PAD_Y)
    draw_circuit(draw, spec, cx, cy)

out = "/home/claw/circuit-digitization/docs/synthgt_catalog.png"
img.save(out, "PNG")
print(f"Saved to {out} ({W}x{H})")

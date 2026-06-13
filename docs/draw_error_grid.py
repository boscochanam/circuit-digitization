"""Error sweep grid: each circuit x severity level, using draw_circuits_v4 style."""
from __future__ import annotations
import math
from collections import Counter
from itertools import combinations
from PIL import Image, ImageDraw, ImageFont
from wire_detection.synthgt.circuits import CATALOG
from wire_detection.synthgt.synthesize import (
    inject_errors, intended_pairs, synthesize_clean,
)
from wire_detection.core.join_strategies import run_strategy

COLS = 5  # L0..L4
LEVELS = [0, 1, 2, 3, 4]
LEVEL_COLORS = ["#22c55e", "#38bdf8", "#facc15", "#f97316", "#ef4444"]
LEVEL_LABELS = ["L0  Clean", "L1  Mild", "L2  Moderate", "L3  Heavy", "L4  Severe"]

CELL_W, CELL_H = 260, 220
PAD_X, PAD_Y = 12, 30
MARGIN = 40
ROW_LABEL_W = 100

try:
    FNT = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
    FNT_R = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
    font_comp = FNT(10)
    font_val = FNT_R(9)
    font_pin = FNT_R(8)
    font_label = FNT_R(10)
    font_header = FNT(13)
    font_score = FNT(10)
except Exception:
    font_comp = font_val = font_pin = font_label = font_header = font_score = ImageFont.load_default()

TYPE_COL = {
    "voltage-DC": ("#991b1b", "#ef4444"),
    "resistor":   ("#166534", "#22c55e"),
    "inductor":   ("#155e75", "#06b6d4"),
    "diode":      ("#854d0e", "#f59e0b"),
    "gnd":        ("#374151", "#9ca3af"),
}
TYPE_PREFIX = {"voltage-DC": "V", "resistor": "R", "inductor": "L", "diode": "D", "gnd": "GND"}

WIRE_COL = "#64748b"
WIRE_ERR_COL = "#ef4444"
PIN_COL = "#facc15"
EP_COL = "#f97316"
JUNCTION_COL = "#3b82f6"


def rotated_rect(cx, cy, w, h, angle_deg):
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    half_w, half_h = w / 2, h / 2
    corners = [(-half_w, -half_h), (half_w, -half_h),
               (half_w, half_h), (-half_w, half_h)]
    return [(int(cos_a * dx - sin_a * dy + cx),
             int(sin_a * dx + cos_a * dy + cy))
            for dx, dy in corners]


def draw_cell(img_draw, spec, wires, components, pin_pos, x0, y0, w, h, level, f1, prec, rec):
    # Background
    img_draw.rounded_rectangle(
        [x0, y0, x0 + w, y0 + h],
        radius=6, fill="#1e293b", outline="#334155", width=1,
    )

    if not spec.comps:
        return

    xs = [c.cx for c in spec.comps]
    ys = [c.cy for c in spec.comps]
    min_x, max_x = min(xs) - 80, max(xs) + 80
    min_y, max_y = min(ys) - 80, max(ys) + 80
    range_x = max_x - min_x or 1
    range_y = max_y - min_y or 1

    pad = 40
    scale_x = (w - 2 * pad) / range_x
    scale_y = (h - 2 * pad - 24) / range_y  # leave room for score
    scale = min(scale_x, scale_y)

    def tx(x): return x0 + pad + (x - min_x) * scale
    def ty(y): return y0 + pad + (y - min_y) * scale

    # Wires
    wire_col = WIRE_COL if level == 0 else WIRE_ERR_COL
    for wr in wires:
        x1, y1 = tx(wr[0][0]), ty(wr[0][1])
        x2, y2 = tx(wr[1][0]), ty(wr[1][1])
        img_draw.line([(x1, y1), (x2, y2)], fill=wire_col, width=2)

    # Wire endpoint dots
    for wr in wires:
        for ep in wr:
            ex, ey = tx(ep[0]), ty(ep[1])
            r = 2
            img_draw.ellipse([ex - r, ey - r, ex + r, ey + r], fill=EP_COL)

    # Net junction dots
    ep_count = Counter()
    for wr in wires:
        ep_count[wr[0]] += 1
        ep_count[wr[1]] += 1
    for ep, cnt in ep_count.items():
        if cnt > 1:
            jx, jy = tx(ep[0]), ty(ep[1])
            r = 4
            img_draw.ellipse([jx - r, jy - r, jx + r, jy + r], fill=JUNCTION_COL, outline="#1d4ed8", width=1)

    # Component polygons
    for i, c in enumerate(spec.comps):
        cx, cy = tx(c.cx), ty(c.cy)
        prefix = TYPE_PREFIX.get(c.type, "?")
        if c.orient == "H":
            raw_w, raw_h = c.size, 30
        else:
            raw_w, raw_h = 30, c.size
        angle = getattr(c, "angle", 0.0) or 0.0
        bw = raw_w * scale
        bh = raw_h * scale
        fill, border = TYPE_COL.get(c.type, ("#333", "#666"))
        corners = rotated_rect(cx, cy, max(bw, 28), max(bh, 20), angle)
        img_draw.polygon(corners, fill=fill, outline=border, width=1)
        img_draw.text((cx, cy - 1), f"{prefix}{i+1}", fill="#fff", font=font_comp, anchor="mm")

    # Pin dots
    for (ci, pi), (px, py) in pin_pos.items():
        px_s, py_s = tx(px), ty(py)
        r = 3
        img_draw.ellipse([px_s - r, py_s - r, px_s + r, py_s + r], fill=PIN_COL, outline="#000", width=1)

    # Score badge
    color = "#22c55e" if f1 >= 0.99 else "#facc15" if f1 >= 0.8 else "#ef4444"
    score_text = f"F1={f1:.2f}  P={prec:.2f}  R={rec:.2f}"
    img_draw.text((x0 + w // 2, y0 + h - 8), score_text, fill=color, font=font_score, anchor="mb")


def main():
    n_rows = len(CATALOG)
    W = MARGIN * 2 + ROW_LABEL_W + COLS * CELL_W + (COLS - 1) * PAD_X
    H = MARGIN * 2 + 70 + n_rows * CELL_H + (n_rows - 1) * PAD_Y

    img = Image.new("RGB", (W, H), "#111827")
    draw = ImageDraw.Draw(img)

    # Column headers
    for j, label in enumerate(LEVEL_LABELS):
        cx = MARGIN + ROW_LABEL_W + j * (CELL_W + PAD_X) + CELL_W // 2
        draw.text((cx, MARGIN + 10), label, fill=LEVEL_COLORS[j], font=font_header, anchor="mt")

    # Legend
    draw.text((W // 2, MARGIN + 35),
              "■ component   ● pin (yellow)   ● endpoint (orange)   ● junction (blue)   ─ wire",
              fill="#6b7280", font=font_label, anchor="mt")

    for i, spec in enumerate(CATALOG):
        row_y = MARGIN + 70 + i * (CELL_H + PAD_Y)

        # Row label
        draw.text((MARGIN + ROW_LABEL_W // 2, row_y + CELL_H // 2),
                  spec.name, fill="#e94560", font=font_label, anchor="mm")

        components, wires_clean, pin_pos = synthesize_clean(spec)
        gt_pairs = intended_pairs(spec)

        for j, level in enumerate(LEVELS):
            col_x = MARGIN + ROW_LABEL_W + j * (CELL_W + PAD_X)

            if level == 0:
                wires = wires_clean
            else:
                wires = inject_errors(wires_clean, level, seed=42,
                                      pin_pos=pin_pos, components=components)

            # Run join
            _, netlist = run_strategy("graph_rescue", wires, components)
            got_pairs = set()
            node_comps = {}
            for (ci, _pin), nid in netlist.pin_to_node.items():
                node_comps.setdefault(nid, set()).add(ci)
            for comps_set in node_comps.values():
                got_pairs.update(combinations(sorted(comps_set), 2))

            tp = len(gt_pairs & got_pairs)
            fp = len(got_pairs - gt_pairs)
            fn = len(gt_pairs - got_pairs)
            prec = tp / (tp + fp) if (tp + fp) else 1.0
            rec = tp / (tp + fn) if (tp + fn) else 1.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 1.0

            # Adjust component sizes for cell
            cell_spec = spec
            draw_cell(draw, cell_spec, wires, components, pin_pos,
                      col_x, row_y, CELL_W, CELL_H, level, f1, prec, rec)

    out = "/home/claw/circuit-digitization/docs/synthgt_error_grid.png"
    img.save(out, "PNG")
    print(f"Saved to {out} ({W}x{H})")


if __name__ == "__main__":
    main()

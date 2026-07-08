"""Visual evaluation grid: GT → before join → after join for difficult circuits.
After column shows ACTUAL join result: green=recovered, red=missed connections."""
from __future__ import annotations
import math
from collections import Counter
from itertools import combinations
from PIL import Image, ImageDraw, ImageFont
from wire_detection.synthgt.circuits import CATALOG, CATALOG_BY_NAME
from wire_detection.paths import DOCS_DIR
from wire_detection.synthgt.synthesize import (
    inject_errors, intended_pairs, synthesize_clean,
)
from wire_detection.core.join_strategies import run_strategy

DIFFICULT = ["ring6_r", "dense_pair", "angled_v", "angled_ring4"]
LEVELS = [3, 4]
LEVEL_NAMES = {3: "L3 Heavy", 4: "L4 Severe"}

COLS_PER_LEVEL = 3
COL_HEADERS = ["Ground Truth", "Before Join", "After Join"]

CELL_W, CELL_H = 300, 260
PAD_X, PAD_Y = 16, 50
MARGIN = 50
ROW_LABEL_W = 110

try:
    FNT = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s)
    FNT_R = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", s)
    font_comp = FNT(10)
    font_val = FNT_R(9)
    font_pin = FNT_R(8)
    font_label = FNT_R(11)
    font_header = FNT(13)
    font_score = FNT(11)
    font_title = FNT(16)
except Exception:
    font_comp = font_val = font_pin = font_label = font_header = font_score = font_title = ImageFont.load_default()

TYPE_COL = {
    "voltage-DC": ("#991b1b", "#ef4444"),
    "resistor":   ("#166534", "#22c55e"),
    "inductor":   ("#155e75", "#06b6d4"),
    "diode":      ("#854d0e", "#f59e0b"),
    "gnd":        ("#374151", "#9ca3af"),
}
TYPE_PREFIX = {"voltage-DC": "V", "resistor": "R", "inductor": "L", "diode": "D", "gnd": "GND"}

WIRE_GT_COL = "#22c55e"
WIRE_BEFORE_COL = "#ef4444"
WIRE_RECOVERED_COL = "#22c55e"
WIRE_MISSED_COL = "#ef4444"
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


def draw_components(draw, spec, tx, ty, scale):
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
        draw.polygon(corners, fill=fill, outline=border, width=1)
        draw.text((cx, cy - 1), f"{prefix}{i+1}", fill="#fff", font=font_comp, anchor="mm")


def draw_pins(draw, pin_pos, tx, ty):
    for (ci, pi), (px, py) in pin_pos.items():
        px_s, py_s = tx(px), ty(py)
        r = 3
        draw.ellipse([px_s - r, py_s - r, px_s + r, py_s + r], fill=PIN_COL, outline="#000", width=1)


def draw_wires(draw, wires, tx, ty, color, width=2):
    for wr in wires:
        x1, y1 = tx(wr[0][0]), ty(wr[0][1])
        x2, y2 = tx(wr[1][0]), ty(wr[1][1])
        draw.line([(x1, y1), (x2, y2)], fill=color, width=width)


def draw_endpoints(draw, wires, tx, ty):
    for wr in wires:
        for ep in wr:
            ex, ey = tx(ep[0]), ty(ep[1])
            r = 2
            draw.ellipse([ex - r, ey - r, ex + r, ey + r], fill=EP_COL)


def draw_junctions(draw, wires, tx, ty):
    ep_count = Counter()
    for wr in wires:
        ep_count[wr[0]] += 1
        ep_count[wr[1]] += 1
    for ep, cnt in ep_count.items():
        if cnt > 1:
            jx, jy = tx(ep[0]), ty(ep[1])
            r = 4
            draw.ellipse([jx - r, jy - r, jx + r, jy + r], fill=JUNCTION_COL, outline="#1d4ed8", width=1)


def get_join_result(wires, components):
    _, netlist = run_strategy("graph_rescue", wires, components)
    got_pairs = set()
    node_comps = {}
    for (ci, _pin), nid in netlist.pin_to_node.items():
        node_comps.setdefault(nid, set()).add(ci)
    for comps_set in node_comps.values():
        got_pairs.update(combinations(sorted(comps_set), 2))
    return netlist, got_pairs


def score(gt_pairs, got_pairs):
    tp = len(gt_pairs & got_pairs)
    fp = len(got_pairs - gt_pairs)
    fn = len(gt_pairs - got_pairs)
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 1.0
    return f1, prec, rec


def get_net_components(netlist):
    """Map component index -> net id."""
    comp_to_net = {}
    for (ci, _pin), nid in netlist.pin_to_node.items():
        comp_to_net[ci] = nid
    return comp_to_net


def draw_cell_colored(draw, spec, wires, components, pin_pos, x0, y0, w, h,
                      netlist):
    """Draw cell where wires are colored green/red based on join success."""
    draw.rounded_rectangle(
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

    pad = 35
    scale_x = (w - 2 * pad) / range_x
    scale_y = (h - 2 * pad) / range_y
    scale = min(scale_x, scale_y)

    def tx(x): return x0 + pad + (x - min_x) * scale
    def ty(y): return y0 + pad + (y - min_y) * scale

    # Draw components first (behind wires)
    draw_components(draw, spec, tx, ty, scale)
    draw_pins(draw, pin_pos, tx, ty)

    # Draw wires colored by join result: green=recovered, red=missed
    connected = netlist.connected_wires()
    for w_idx, wr in enumerate(wires):
        color = WIRE_RECOVERED_COL if w_idx in connected else WIRE_MISSED_COL
        x1, y1 = tx(wr[0][0]), ty(wr[0][1])
        x2, y2 = tx(wr[1][0]), ty(wr[1][1])
        draw.line([(x1, y1), (x2, y2)], fill=color, width=2)

    draw_endpoints(draw, wires, tx, ty)
    draw_junctions(draw, wires, tx, ty)


def main():
    n_rows = len(DIFFICULT)
    n_level_cols = len(LEVELS) * COLS_PER_LEVEL
    W = MARGIN * 2 + ROW_LABEL_W + n_level_cols * CELL_W + (n_level_cols - 1) * PAD_X + (len(LEVELS) - 1) * 30
    H = MARGIN * 2 + 80 + n_rows * CELL_H + (n_rows - 1) * PAD_Y

    img = Image.new("RGB", (W, H), "#111827")
    draw = ImageDraw.Draw(img)

    draw.text((W // 2, MARGIN), "Visual Join Evaluation — Difficult Circuits",
              fill="#e94560", font=font_title, anchor="mt")

    for li, level in enumerate(LEVELS):
        group_x = MARGIN + ROW_LABEL_W + li * (COLS_PER_LEVEL * CELL_W + (COLS_PER_LEVEL - 1) * PAD_X + 30)
        group_w = COLS_PER_LEVEL * CELL_W + (COLS_PER_LEVEL - 1) * PAD_X
        draw.text((group_x + group_w // 2, MARGIN + 30),
                  LEVEL_NAMES[level], fill=["#f97316", "#ef4444"][li], font=font_header, anchor="mt")

    for li, level in enumerate(LEVELS):
        for ci, header in enumerate(COL_HEADERS):
            cx = MARGIN + ROW_LABEL_W + li * (COLS_PER_LEVEL * CELL_W + (COLS_PER_LEVEL - 1) * PAD_X + 30) + ci * (CELL_W + PAD_X) + CELL_W // 2
            draw.text((cx, MARGIN + 50), header, fill="#9ca3af", font=font_label, anchor="mt")

    draw.text((W // 2, MARGIN + 68),
              "green=GT wire   red=error wire   green after=recovered   red after=missed connection",
              fill="#6b7280", font=font_label, anchor="mt")

    for i, name in enumerate(DIFFICULT):
        spec = CATALOG_BY_NAME[name]
        row_y = MARGIN + 80 + i * (CELL_H + PAD_Y)

        draw.text((MARGIN + ROW_LABEL_W // 2, row_y + CELL_H // 2),
                  spec.name, fill="#e94560", font=font_label, anchor="mm")

        components, wires_clean, pin_pos = synthesize_clean(spec)
        gt_pairs = intended_pairs(spec)

        for li, level in enumerate(LEVELS):
            wires_err = inject_errors(wires_clean, level, seed=42,
                                      pin_pos=pin_pos, components=components)
            netlist, got_pairs = get_join_result(wires_err, components)
            f1, prec, rec = score(gt_pairs, got_pairs)

            group_x = MARGIN + ROW_LABEL_W + li * (COLS_PER_LEVEL * CELL_W + (COLS_PER_LEVEL - 1) * PAD_X + 30)

            # Column 0: Ground Truth
            cx = group_x
            draw.rounded_rectangle([cx, row_y, cx + CELL_W, row_y + CELL_H],
                                   radius=6, fill="#1e293b", outline="#334155", width=1)
            # Simple GT drawing
            xs = [c.cx for c in spec.comps]
            ys = [c.cy for c in spec.comps]
            min_x, max_x = min(xs) - 80, max(xs) + 80
            min_y, max_y = min(ys) - 80, max(ys) + 80
            range_x = max_x - min_x or 1
            range_y = max_y - min_y or 1
            pad = 35
            scale_x = (CELL_W - 2 * pad) / range_x
            scale_y = (CELL_H - 2 * pad) / range_y
            scale = min(scale_x, scale_y)
            def tx0(x): return cx + pad + (x - min_x) * scale
            def ty0(y): return row_y + pad + (y - min_y) * scale
            draw_components(draw, spec, tx0, ty0, scale)
            draw_pins(draw, pin_pos, tx0, ty0)
            draw_wires(draw, wires_clean, tx0, ty0, WIRE_GT_COL)
            draw_endpoints(draw, wires_clean, tx0, ty0)
            draw_junctions(draw, wires_clean, tx0, ty0)

            # Column 1: Before Join (error wires)
            cx = group_x + 1 * (CELL_W + PAD_X)
            draw.rounded_rectangle([cx, row_y, cx + CELL_W, row_y + CELL_H],
                                   radius=6, fill="#1e293b", outline="#334155", width=1)
            def tx1(x): return cx + pad + (x - min_x) * scale
            def ty1(y): return row_y + pad + (y - min_y) * scale
            draw_components(draw, spec, tx1, ty1, scale)
            draw_pins(draw, pin_pos, tx1, ty1)
            draw_wires(draw, wires_err, tx1, ty1, WIRE_BEFORE_COL)
            draw_endpoints(draw, wires_err, tx1, ty1)
            draw_junctions(draw, wires_err, tx1, ty1)

            # Column 2: After Join (colored by success)
            cx = group_x + 2 * (CELL_W + PAD_X)
            draw_cell_colored(draw, spec, wires_err, components, pin_pos,
                              cx, row_y, CELL_W, CELL_H, netlist)

            # Score badge
            color = "#22c55e" if f1 >= 0.99 else "#facc15" if f1 >= 0.8 else "#ef4444"
            score_text = f"F1={f1:.2f}  P={prec:.2f}  R={rec:.2f}"
            draw.text((cx + CELL_W // 2, row_y + CELL_H - 8), score_text,
                      fill=color, font=font_score, anchor="mb")

    out = str(DOCS_DIR / "synthgt_join_eval.png")
    img.save(out, "PNG")
    print(f"Saved to {out} ({W}x{H})")


if __name__ == "__main__":
    main()

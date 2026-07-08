"""Generate a visual grid: each circuit x severity level, showing clean vs error."""
from itertools import combinations
from PIL import Image, ImageDraw
from wire_detection.synthgt.circuits import CATALOG
from wire_detection.synthgt.synthesize import (
    inject_errors, intended_pairs, synthesize_clean,
)
from wire_detection.core.join_strategies import run_strategy
from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.paths import DOCS_DIR

CELL_W, CELL_H = 220, 180
PAD = 8
COLS = 5  # L0..L4
LEVELS = [0, 1, 2, 3, 4]
LEVEL_COLORS = ["#2ecc71", "#3498db", "#f39c12", "#e74c3c", "#8e44ad"]
LEVEL_LABELS = ["L0\nClean", "L1\nMild", "L2\nMod", "L3\nHeavy", "L4\nSevere"]

NAME_TO_CLS = {v: k for k, v in COMPONENT_TYPES.items()}
COMP_COLORS = {"R": "#e74c3c", "C": "#3498db", "L": "#2ecc71", "V": "#f39c12",
               "D": "#9b59b6", "Q": "#1abc9c", "J": "#95a5a6", "T": "#95a5a6"}


def draw_circuit(draw, wires, components, pin_pos, x0, y0, w, h):
    if not wires and not components:
        return
    all_x = [p[0] for wr in wires for p in wr]
    all_y = [p[1] for wr in wires for p in wr]
    for comp in components:
        bbox = comp[2]
        all_x.extend([bbox[0], bbox[2]])
        all_y.extend([bbox[1], bbox[3]])
    if not all_x:
        return
    minX, maxX = min(all_x), max(all_x)
    minY, maxY = min(all_y), max(all_y)
    rng_x = maxX - minX or 1
    rng_y = maxY - minY or 1
    scale = min((w - 20) / rng_x, (h - 30) / rng_y)
    ox = x0 + (w - rng_x * scale) / 2 - minX * scale
    oy = y0 + (h - 30 - rng_y * scale) / 2 - minY * scale

    def tx(p):
        return int(ox + p[0] * scale), int(oy + p[1] * scale)

    # Wires
    for wire in wires:
        p1, p2 = tx(wire[0]), tx(wire[1])
        draw.line([p1, p2], fill="#777777", width=2)

    # Components
    for i, comp in enumerate(components):
        cls_id = comp[0]
        bbox = comp[2]
        type_name = NAME_TO_CLS.get(cls_id, "?")
        color = COMP_COLORS.get(type_name, "#7f8c8d")
        x1, y1 = tx((bbox[0], bbox[1]))
        x2, y2 = tx((bbox[2], bbox[3]))
        draw.rectangle([x1, y1, x2, y2], fill=color, outline="white", width=1)
        label = f"{type_name}{i+1}"
        tw = draw.textlength(label)
        draw.text(((x1+x2-tw)/2, (y1+y2-8)/2), label, fill="white")

    # Pins
    for (ci, pi), pp in pin_pos.items():
        px, py = tx(pp)
        draw.ellipse([px-2, py-2, px+2, py+2], fill="yellow")


def main():
    circuits = CATALOG
    n_rows = len(circuits)
    img_w = COLS * (CELL_W + PAD) + PAD + 120
    img_h = n_rows * (CELL_H + PAD) + PAD + 40
    img = Image.new("RGB", (img_w, img_h), "#1a1a2e")
    draw = ImageDraw.Draw(img)

    # Column headers
    for j, label in enumerate(LEVEL_LABELS):
        x = 120 + PAD + j * (CELL_W + PAD) + CELL_W // 2
        for k, line in enumerate(label.split("\n")):
            draw.text((x - 10, 5 + k * 14), line, fill=LEVEL_COLORS[j])

    for i, spec in enumerate(circuits):
        row_y = 40 + i * (CELL_H + PAD)
        draw.text((5, row_y + CELL_H // 2 - 6), spec.name, fill="white")
        components, wires_clean, pin_pos = synthesize_clean(spec)
        gt_pairs = intended_pairs(spec)

        for j, level in enumerate(LEVELS):
            col_x = 120 + PAD + j * (CELL_W + PAD)
            cell_img = Image.new("RGB", (CELL_W, CELL_H), "#16213e")
            cell_draw = ImageDraw.Draw(cell_img)

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

            draw_circuit(cell_draw, wires, components, pin_pos, 0, 0, CELL_W, CELL_H - 20)
            color = "#2ecc71" if f1 >= 0.99 else "#f39c12" if f1 >= 0.8 else "#e74c3c"
            cell_draw.text((4, CELL_H - 18), f"F1={f1:.2f} P={prec:.2f} R={rec:.2f}", fill=color)

            img.paste(cell_img, (col_x, row_y))

    img.save(str(DOCS_DIR / "synthgt_grid_v2.png"))
    print("Saved docs/synthgt_grid_v2.png")


if __name__ == "__main__":
    main()

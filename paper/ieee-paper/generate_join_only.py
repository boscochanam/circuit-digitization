#!/usr/bin/env python3
"""Join-result-only panels on GROUND-TRUTH components (matches the benchmark), with
junctions/terminals annotated so junction merging is visible, and the TRUE per-figure
F1 (scored vs the verified net-GT). Run on claw:
  ./.venv/bin/python paper/ieee-paper/generate_join_only.py
"""
import cv2, json, colorsys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from wire_detection.benchmark.build_net_gt import GT_IMAGES, find_hdc_label, parse_components
from wire_detection.benchmark.join_eval_134 import detect_wires
from wire_detection.benchmark.join_eval_real_f1 import comp_pairs, gt_pairs, prf
from wire_detection.core.join_strategies import run_strategy, make_pins, make_pins_junction_aware
from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.paths import GROUND_TRUTH_DIR, REPO_ROOT

OUTPUT = REPO_ROOT / "paper" / "ieee-paper" / "figures" / "join_only"
OUTPUT.mkdir(parents=True, exist_ok=True)
GT_NETS = json.load(open(GROUND_TRUTH_DIR / "real_nets_verified.json"))

CANDIDATES = ["C37_D2_P4", "C112_D1_P1", "C83_D2_P4", "C19_D1_P2", "C111_D1_P1"]
STRUCT = {"junction", "terminal", "gnd", "vss", "crossover", "text"}


def net_color(i):
    h = (i * 0.61803398875) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.80, 1.0)
    return (int(b * 255), int(g * 255), int(r * 255))


def render(name):
    entry = GT_NETS[name + "_jpg"]
    keep = set(entry["electrical_idxs"])
    gtp = gt_pairs(entry["nets"], keep)
    gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    h, w = gray.shape
    comps = parse_components(find_hdc_label(name).read_text(), w, h)
    wires = detect_wires(gray, comps)
    std = make_pins(wires, comps)
    junc = make_pins_junction_aware(wires, comps)
    pins, nl = run_strategy("scale_completion", wires, comps, std_pins=std, junc_pins=junc)
    pred = comp_pairs(nl, keep); p, r, f1 = prf(gtp, pred)

    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    img = (img * 0.35 + 45).astype(np.uint8)

    # net id per wire and per component
    nets = [n for n in nl.nodes if n.wires]
    netidx = {id(n): i for i, n in enumerate(nets)}
    comp_net = {}
    for n in nets:
        for pn in n.pins:
            comp_net[pn.component_idx] = netidx[id(n)]
    pin_pos = {(pn.component_idx, pn.pin_idx): (int(pn.x), int(pn.y)) for pn in pins}

    # 1) colour each net's actual wire segments + short pin stubs
    STUB = 55
    for i, node in enumerate(nets):
        col = net_color(i); wends = []
        for wi in node.wires:
            if 0 <= wi < len(wires):
                (x1, y1), (x2, y2) = wires[wi]
                a, b = (int(x1), int(y1)), (int(x2), int(y2))
                cv2.line(img, a, b, col, 3, cv2.LINE_AA); wends += [a, b]
        for pn in node.pins:
            k = (pn.component_idx, pn.pin_idx)
            if k not in pin_pos: continue
            pt = pin_pos[k]
            if wends:
                nb = min(wends, key=lambda e: (e[0]-pt[0])**2 + (e[1]-pt[1])**2)
                if (nb[0]-pt[0])**2 + (nb[1]-pt[1])**2 <= STUB**2:
                    cv2.line(img, pt, nb, col, 2, cv2.LINE_AA)

    # 2) draw components: devices = OBB+label; junctions/terminals = annotated markers
    for ci, (cls, verts, bbox) in enumerate(comps):
        tname = COMPONENT_TYPES.get(int(cls), "?")
        cx = sum(v[0] for v in verts) // 4; cy = sum(v[1] for v in verts) // 4
        ncol = net_color(comp_net[ci]) if ci in comp_net else (120, 120, 120)
        if tname == "junction":
            cv2.drawMarker(img, (cx, cy), ncol, cv2.MARKER_DIAMOND, 22, 3, cv2.LINE_AA)
            cv2.drawMarker(img, (cx, cy), (255, 255, 255), cv2.MARKER_DIAMOND, 22, 1, cv2.LINE_AA)
            cv2.putText(img, "J", (cx + 10, cy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1, cv2.LINE_AA)
        elif tname in ("terminal", "gnd", "vss"):
            cv2.drawMarker(img, (cx, cy), (200, 200, 200), cv2.MARKER_TRIANGLE_UP, 16, 2, cv2.LINE_AA)
        elif tname in ("text", "crossover"):
            pass
        else:  # SPICE device
            pts = np.array(verts, dtype=np.int32).reshape((-1, 1, 2))
            fill = img.copy(); cv2.fillPoly(fill, [pts], (95, 95, 70))
            cv2.addWeighted(fill, 0.5, img, 0.5, 0, img)
            cv2.polylines(img, [pts], True, (200, 200, 170), 2, cv2.LINE_AA)
            cv2.putText(img, tname.split("-")[0], (cx - 16, min(v[1] for v in verts) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (235, 235, 210), 1, cv2.LINE_AA)

    # 3) device pins on top (coloured dots)
    for pn in pins:
        cls = comps[pn.component_idx][0]
        if COMPONENT_TYPES.get(int(cls), "") in STRUCT: continue
        k = (pn.component_idx, pn.pin_idx)
        if k in comp_net and k in pin_pos:
            pt = pin_pos[k]; col = net_color(comp_net.get(pn.component_idx, 0))
            cv2.circle(img, pt, 5, col, -1, cv2.LINE_AA)
            cv2.circle(img, pt, 5, (255, 255, 255), 1, cv2.LINE_AA)

    njunc = sum(1 for c in comps if COMPONENT_TYPES.get(int(c[0]), "") == "junction")
    fig, ax = plt.subplots(figsize=(9, 9), dpi=200)
    ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)); ax.axis('off')
    ax.set_title(f"{name.replace('_','-')}  |  {len(nets)} nets, {len(keep)} devices, {njunc} junctions  |  "
                 f"F1={f1:.3f} (P={p:.2f}, R={r:.2f})  [GT components]",
                 fontsize=12, fontweight='bold')
    out = OUTPUT / f"{name.replace('_','-')}-join.png"
    plt.savefig(out, bbox_inches='tight', pad_inches=0.05); plt.close()
    print(f"  OK {name}: nets={len(nets)} junctions={njunc} F1={f1:.3f} -> {out}")


if __name__ == '__main__':
    for n in CANDIDATES:
        render(n)
    print(f"Done -> {OUTPUT}/")

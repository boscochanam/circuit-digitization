#!/usr/bin/env python3
"""Fig 2 pipeline composite on GROUND-TRUTH components (consistent with every number in
the paper, which isolates the join). Six stages per circuit: original, component occlusion,
Sauvola binarization, morphological close, detected wires, and the join result (nets coloured
on the actual conductors, junctions annotated, true component-pair F1 vs the verified net-GT).

Run on claw:  ./.venv/bin/python paper/ieee-paper/generate_pipeline_examples.py
"""
import os, sys, cv2, json, colorsys
import numpy as np
from pathlib import Path

sys.path.insert(0, '/home/claw/circuit-digitization')
os.chdir('/home/claw/circuit-digitization')

from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig, build_component_mask, crop_to_roi, shift_components,
    detect_wires_experiment, sauvola_binary,
)
from wire_detection.benchmark.build_net_gt import GT_IMAGES, find_hdc_label, parse_components
from wire_detection.benchmark.join_eval_real_f1 import comp_pairs, gt_pairs, prf
from wire_detection.core.join_strategies import run_strategy, DEFAULT_STRATEGY, make_pins, make_pins_junction_aware
from wire_detection.core.component_classes import COMPONENT_TYPES
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

cfg = ExperimentConfig(
    name="a16", sauvola_k=0.285, sauvola_window=67, close_kernel=3,
    ccl_min_area=28, endpoint_mode="pca", dedup_mode="overlap",
    dedup_angle=12, dedup_dist=18, anchor_filter_enabled=True,
    anchor_endpoint_dist=16.0, anchor_link_dist=8.0, extraction_mode="component",
)

OUTPUT = Path("/home/claw/circuit-digitization/paper/ieee-paper/figures/pipeline_examples")
OUTPUT.mkdir(parents=True, exist_ok=True)
GT_NETS = json.load(open("ground_truth/real_nets_verified.json"))

# Structural / non-device GT classes (58-class CGHD taxonomy) — no SPICE pins.
SKIP_PIN_TYPES = {
    "junction", "terminal", "gnd", "vss", "crossover", "text",
    "unknown", "mechanical", "optical", "probe", "probe-current", "probe-voltage",
}


def is_skip(cls):
    return COMPONENT_TYPES.get(int(cls), "") in SKIP_PIN_TYPES


def is_junction(cls):
    return COMPONENT_TYPES.get(int(cls), "") == "junction"


def net_color(i):
    h = (i * 0.61803398875) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.80, 1.0)
    return (int(b * 255), int(g * 255), int(r * 255))


def draw_obb(img, vertices, color, thickness=1):
    pts = np.array(vertices, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(img, [pts], True, color, thickness, cv2.LINE_AA)


def run_pipeline(img_path, name):
    from PIL import Image
    gray = np.array(Image.open(img_path).convert('L'))
    h, w = gray.shape
    stages = {'original': gray.copy()}

    comp_labels = parse_components(find_hdc_label(name).read_text(), w, h)
    entry = GT_NETS[name + "_jpg"]
    keep = set(entry["electrical_idxs"])
    gtp = gt_pairs(entry["nets"], keep)

    occluded = build_component_mask(gray, comp_labels, cfg.occlusion_margin)
    stages['occluded'] = occluded.copy()
    cropped, ox, oy = crop_to_roi(occluded, comp_labels, cfg.crop_padding)
    local_components = shift_components(comp_labels, ox, oy)
    stages['cropped'] = cropped.copy()

    binary = sauvola_binary(cropped, cfg.sauvola_k, cfg.sauvola_window)
    stages['binary'] = binary.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.close_kernel, cfg.close_kernel))
    stages['closed'] = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    lines_local = detect_wires_experiment(cropped, local_components, cfg)
    lines_global = [((int(x1 + ox), int(y1 + oy)), (int(x2 + ox), int(y2 + oy)))
                    for (x1, y1), (x2, y2) in lines_local]
    stages['n_wires'] = len(lines_global)

    # Detected-wires overlay (red wires + green device OBBs)
    overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for (x1, y1), (x2, y2) in lines_global:
        cv2.line(overlay, (x1, y1), (x2, y2), (0, 0, 255), 2, cv2.LINE_AA)
    for cls, verts, _bbox in comp_labels:
        if not is_skip(cls):
            draw_obb(overlay, verts, (0, 200, 0), 2)
    stages['wire_overlay'] = overlay.copy()

    # Join (consistent global frame: global wires + global GT components)
    pins, netlist = run_strategy(DEFAULT_STRATEGY, lines_global, comp_labels,
                                 std_pins=make_pins(lines_global, comp_labels),
                                 junc_pins=make_pins_junction_aware(lines_global, comp_labels))
    pred = comp_pairs(netlist, keep)
    p, r, f1 = prf(gtp, pred)

    join_overlay = (cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) * 0.35 + 45).astype(np.uint8)
    nets = [n for n in netlist.nodes if n.wires]
    netidx = {id(n): i for i, n in enumerate(nets)}
    comp_net = {}
    for n in nets:
        for pn in n.pins:
            comp_net[pn.component_idx] = netidx[id(n)]
    pin_pos = {(pn.component_idx, pn.pin_idx): (int(pn.x), int(pn.y)) for pn in pins}

    # 1) colour each net on its actual wires + short pin stubs
    for i, node in enumerate(nets):
        col = net_color(i); wends = []
        for wi in node.wires:
            if 0 <= wi < len(lines_global):
                (x1, y1), (x2, y2) = lines_global[wi]
                a, b = (int(x1), int(y1)), (int(x2), int(y2))
                cv2.line(join_overlay, a, b, col, 3, cv2.LINE_AA); wends += [a, b]
        for pn in node.pins:
            k = (pn.component_idx, pn.pin_idx)
            if k not in pin_pos: continue
            pt = pin_pos[k]
            if wends:
                nb = min(wends, key=lambda e: (e[0]-pt[0])**2 + (e[1]-pt[1])**2)
                if (nb[0]-pt[0])**2 + (nb[1]-pt[1])**2 <= 55*55:
                    cv2.line(join_overlay, pt, nb, col, 2, cv2.LINE_AA)

    # 2) components: devices = OBB fill+label; junctions = coloured diamonds; terminals = triangles
    for ci, (cls, verts, _bbox) in enumerate(comp_labels):
        tname = COMPONENT_TYPES.get(int(cls), "?")
        cx = sum(v[0] for v in verts) // 4; cy = sum(v[1] for v in verts) // 4
        ncol = net_color(comp_net[ci]) if ci in comp_net else (120, 120, 120)
        if is_junction(cls):
            cv2.drawMarker(join_overlay, (cx, cy), ncol, cv2.MARKER_DIAMOND, 20, 3, cv2.LINE_AA)
            cv2.drawMarker(join_overlay, (cx, cy), (255, 255, 255), cv2.MARKER_DIAMOND, 20, 1, cv2.LINE_AA)
        elif tname in ("terminal", "gnd", "vss"):
            cv2.drawMarker(join_overlay, (cx, cy), (200, 200, 200), cv2.MARKER_TRIANGLE_UP, 15, 2, cv2.LINE_AA)
        elif tname not in ("text", "crossover"):
            pts = np.array(verts, dtype=np.int32).reshape((-1, 1, 2))
            fill = join_overlay.copy(); cv2.fillPoly(fill, [pts], (95, 95, 70))
            cv2.addWeighted(fill, 0.5, join_overlay, 0.5, 0, join_overlay)
            cv2.polylines(join_overlay, [pts], True, (200, 200, 170), 2, cv2.LINE_AA)
            cv2.putText(join_overlay, tname.split("-")[0], (cx - 16, min(v[1] for v in verts) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (235, 235, 210), 1, cv2.LINE_AA)

    # 3) device pins on top
    for pn in pins:
        if is_skip(comp_labels[pn.component_idx][0]): continue
        k = (pn.component_idx, pn.pin_idx)
        if k in pin_pos and pn.component_idx in comp_net:
            pt = pin_pos[k]; col = net_color(comp_net[pn.component_idx])
            cv2.circle(join_overlay, pt, 5, col, -1, cv2.LINE_AA)
            cv2.circle(join_overlay, pt, 5, (255, 255, 255), 1, cv2.LINE_AA)

    stages['join_overlay'] = join_overlay
    stages['n_nets'] = len(nets)
    stages['n_devices'] = len(keep)
    stages['n_junctions'] = sum(1 for c in comp_labels if is_junction(c[0]))
    stages['f1'] = f1; stages['p'] = p; stages['r'] = r
    return stages


def save_composite(stages, name, output_path):
    fig, axes = plt.subplots(2, 3, figsize=(14, 9.6), dpi=300)
    title_map = [
        ('original', 'Original'),
        ('occluded', 'Component Occlusion'),
        ('binary', 'Sauvola Binarization'),
        ('closed', 'Morphological Close'),
        ('wire_overlay', f'Detected Wires ({stages["n_wires"]})'),
        ('join_overlay', f'Join Result: {stages["n_nets"]} nets, {stages["n_devices"]} devices, '
                         f'{stages["n_junctions"]} junctions'),
    ]
    for ax, (key, title) in zip(axes.flat, title_map):
        img = stages.get(key)
        if img is not None:
            ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img.ndim == 3 else img, cmap=None if img.ndim == 3 else 'gray')
        ax.set_title(title, fontsize=10, fontweight='bold'); ax.axis('off')
    plt.tight_layout(pad=0.8, rect=[0, 0, 1, 0.95])
    fig.suptitle(f"{name.replace('_','-')} (GT components): {stages['n_wires']} wires, {stages['n_nets']} nets, "
                 f"connectivity F1 = {stages['f1']:.3f}", fontsize=13, fontweight='bold', y=0.995)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close()


if __name__ == '__main__':
    candidates = [("C37_D2_P4", "C37-D2-P4-jpg.png"), ("C111_D1_P1", "C111-D1-P1-jpg.png")]
    for name, out_name in candidates:
        img_path = GT_IMAGES / f"{name}_jpg.jpg"
        if not img_path.exists():
            print(f"ERROR: missing {img_path}"); continue
        stages = run_pipeline(img_path, name)
        save_composite(stages, name, OUTPUT / out_name)
        print(f"  OK {name}: {stages['n_wires']} wires, {stages['n_nets']} nets, "
              f"{stages['n_junctions']} junctions, F1={stages['f1']:.3f} -> {OUTPUT/out_name}")
    print(f"Done -> {OUTPUT}/")

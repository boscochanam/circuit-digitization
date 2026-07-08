#!/usr/bin/env python3
"""High-quality pipeline visualization with OBB polygons and clear connections."""
import os, cv2, math
import numpy as np
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig, build_component_mask, crop_to_roi, shift_components,
    detect_wires_experiment, sauvola_binary,
)
from wire_detection.core.join_strategies import run_strategy, make_pins, DEFAULT_STRATEGY
from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.paths import REPO_ROOT, expand_path, gt_images_dir, hdc_root

RELAY_IDS = {cid for cid, name in COMPONENT_TYPES.items()
             if name in ("junction", "terminal", "gnd", "crossover")}
SPICE_CLASSES = {
    "resistor", "capacitor-unpolarized", "capacitor-polarized",
    "inductor", "diode", "voltage-AC", "voltage-DC",
}
spice_cls_ids = {cid for cid, name in COMPONENT_TYPES.items() if name in SPICE_CLASSES}

cfg = ExperimentConfig(
    name="a16", sauvola_k=0.285, sauvola_window=67, close_kernel=3,
    ccl_min_area=28, endpoint_mode="pca", dedup_mode="overlap",
    dedup_angle=12, dedup_dist=18, anchor_filter_enabled=True,
    anchor_endpoint_dist=16.0, anchor_link_dist=8.0, extraction_mode="component",
)

HDC_SPLITS = ["train", "valid", "test"]
CGHD_WORKSPACE = expand_path(os.environ.get("CGHD_WORKSPACE", REPO_ROOT / "data" / "workspace"))


def find_hdc_label_by_prefix(hdc_base, image_name):
    for split in HDC_SPLITS:
        label_dir = hdc_base / split / "labels"
        matches = sorted(label_dir.glob(f"{image_name}_jpg.rf.*.txt"))
        if matches:
            return matches[0]
    return None

def find_exact_match_hdc(hdc_base, image_name, orig_gray):
    stem = f"{image_name}_jpg"
    best_match = None
    best_diff = float('inf')
    for split in HDC_SPLITS:
        img_dir = hdc_base / split / "images"
        label_dir = hdc_base / split / "labels"
        if not img_dir.exists():
            continue
        for f in sorted(img_dir.glob(f"{stem}.rf.*.jpg")):
            rob = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
            if rob is not None and rob.shape == orig_gray.shape:
                diff = np.mean(np.abs(rob.astype(float) - orig_gray.astype(float)))
                if diff < best_diff:
                    best_diff = diff
                    lbl = label_dir / f.name.replace('.jpg', '.txt')
                    if lbl.exists():
                        best_match = (lbl, f, diff)
    if best_match and best_match[2] < 1.0:
        return best_match[0], best_match[1]
    return None, None

def load_hdc_labels(label_path, img_wh):
    """Load YOLO-OBB labels preserving true OBB vertices."""
    w, h = img_wh
    components = []
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 9:
                continue
            cls_id = int(parts[0])
            coords = [float(x) for x in parts[1:9]]
            # True OBB vertices (normalized → pixel)
            xs = [coords[i] * w for i in range(0, 8, 2)]
            ys = [coords[i] * h for i in range(1, 8, 2)]
            pts = [(int(xs[i]), int(ys[i])) for i in range(4)]
            # AABB from OBB (for pipeline logic that needs bbox)
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)
            components.append((cls_id, pts, (int(x1), int(y1), int(x2), int(y2))))
    return components


def draw_obb(img, vertices, color, thickness=1):
    """Draw oriented bounding box using true 4-corner polygon."""
    pts = np.array(vertices, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(img, [pts], True, color, thickness, cv2.LINE_AA)


def run_pipeline(img_path, hdc_base):
    from PIL import Image
    name = Path(img_path).stem
    pil_img = Image.open(img_path).convert('L')
    gray = np.array(pil_img)
    stages = {}
    stages['original'] = gray.copy()

    lookup_name = name
    if name.endswith('_jpg'):
        lookup_name = name[:-4]
    elif name.endswith('_jpeg'):
        lookup_name = name[:-5]

    hdc_label = find_hdc_label_by_prefix(hdc_base, lookup_name)
    exact_label, exact_img_path = find_exact_match_hdc(hdc_base, lookup_name, gray)

    comp_labels = []
    if exact_label:
        comp_labels = load_hdc_labels(exact_label, (gray.shape[1], gray.shape[0]))
        if exact_img_path:
            gray = cv2.imread(str(exact_img_path), cv2.IMREAD_GRAYSCALE)
            stages['original'] = gray.copy()
    elif hdc_label:
        comp_labels = load_hdc_labels(hdc_label, (gray.shape[1], gray.shape[0]))

    if comp_labels:
        occluded = build_component_mask(gray, comp_labels, cfg.occlusion_margin)
        stages['occluded'] = occluded.copy()
    else:
        occluded = gray
        stages['occluded'] = gray.copy()

    if comp_labels:
        cropped, ox, oy = crop_to_roi(occluded, comp_labels, cfg.crop_padding)
        local_components = shift_components(comp_labels, ox, oy)
    else:
        cropped, ox, oy = occluded, 0, 0
        local_components = comp_labels
    stages['cropped'] = cropped.copy()

    binary = sauvola_binary(cropped, cfg.sauvola_k, cfg.sauvola_window)
    stages['binary'] = binary.copy()

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.close_kernel, cfg.close_kernel))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    stages['closed'] = closed.copy()

    lines_local = detect_wires_experiment(cropped, local_components, cfg)
    lines_global = [((int(x1 + ox), int(y1 + oy)), (int(x2 + ox), int(y2 + oy)))
                    for (x1, y1), (x2, y2) in lines_local]
    stages['n_wires'] = len(lines_global)

    # Wire overlay with OBB polygons
    overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for (x1, y1), (x2, y2) in lines_global:
        cv2.line(overlay, (x1, y1), (x2, y2), (0, 0, 255), 2, cv2.LINE_AA)
    # Draw OBB polygons (yellow for all, green for SPICE)
    for comp in comp_labels:
        cls_id, verts, bbox = comp
        color = (0, 200, 0) if cls_id in spice_cls_ids else (0, 180, 255)
        draw_obb(overlay, verts, color, 1)
    stages['wire_overlay'] = overlay.copy()

    # Join result with OBB polygons, large pin dots, and connection lines
    if comp_labels and lines_global:
        has_relays = any(c[0] in RELAY_IDS for c in comp_labels)
        if has_relays:
            from generate_candidates import _junction_relay_netlist
            netlist = _junction_relay_netlist(lines_global, comp_labels, local_components, ox, oy)
            pins = make_pins(lines_global, local_components)
        else:
            pins, netlist = run_strategy(DEFAULT_STRATEGY, lines_global, local_components)

        attached_pins = set()
        for node in netlist.nodes:
            for pin in node.pins:
                attached_pins.add((pin.component_idx, pin.pin_idx))

        join_overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        join_overlay = (join_overlay * 0.4 + 40).astype(np.uint8)

        # Draw OBB polygons for SPICE components
        for comp in comp_labels:
            cls_id, verts, bbox = comp
            if cls_id in spice_cls_ids:
                draw_obb(join_overlay, verts, (60, 60, 45), 1)
                # Label with component type
                cx = sum(v[0] for v in verts) // 4
                cy = min(v[1] for v in verts) - 4
                tname = COMPONENT_TYPES.get(cls_id, "?").split("-")[0]
                cv2.putText(join_overlay, tname, (cx - 15, max(12, cy)),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 140), 1, cv2.LINE_AA)
            elif cls_id in RELAY_IDS:
                draw_obb(join_overlay, verts, (80, 80, 60), 1)

        # Draw nets with distinct colors per net
        net_colors = [
            (180, 80, 20), (20, 120, 180), (20, 160, 80),
            (160, 40, 160), (40, 160, 160), (180, 140, 40),
            (100, 60, 180), (60, 180, 100),
        ]
        nets = [n for n in netlist.nodes if n.wires]

        # Draw wire connections first (colored by net)
        for ni, node in enumerate(nets):
            color = net_colors[ni % len(net_colors)]
            for wi in node.wires:
                if 0 <= wi < len(lines_global):
                    ep1, ep2 = lines_global[wi]
                    cv2.line(join_overlay, ep1, ep2, color, 2, cv2.LINE_AA)

        # Draw pins: green=attached, red=unattached, with connection lines
        for pin in pins:
            px = int(pin.x) + ox
            py = int(pin.y) + oy
            is_attached = (pin.component_idx, pin.pin_idx) in attached_pins
            comp_cls = local_components[pin.component_idx][0]

            if comp_cls not in spice_cls_ids:
                continue

            # Find which net this pin belongs to (for connection line color)
            pin_net_color = None
            if is_attached:
                for ni, node in enumerate(nets):
                    for np_ in node.pins:
                        if np_.component_idx == pin.component_idx and np_.pin_idx == pin.pin_idx:
                            pin_net_color = net_colors[ni % len(net_colors)]
                            break

            # Draw connection line from pin to nearest wire endpoint in same net
            if is_attached and pin_net_color:
                # Find the wire endpoint closest to this pin
                min_dist = float('inf')
                best_ep = None
                for wi in [w for n in nets for w in n.wires
                          if any(p.component_idx == pin.component_idx and p.pin_idx == pin.pin_idx
                                 for p in n.pins)]:
                    if wi < len(lines_global):
                        for ep in lines_global[wi]:
                            d = math.hypot(ep[0] - px, ep[1] - py)
                            if d < min_dist:
                                min_dist = d
                                best_ep = ep
                if best_ep and min_dist < 50:
                    cv2.line(join_overlay, (px, py), best_ep, pin_net_color, 1, cv2.LINE_AA)

            # Draw pin dot (larger, clearer)
            dot_color = (0, 220, 0) if is_attached else (0, 0, 255)
            cv2.circle(join_overlay, (px, py), 4, dot_color, -1, cv2.LINE_AA)
            cv2.circle(join_overlay, (px, py), 4, (255, 255, 255), 1, cv2.LINE_AA)

        stages['join_overlay'] = join_overlay.copy()
        stages['n_nets'] = len(nets)
        stages['n_comps'] = sum(1 for c in comp_labels if c[0] in spice_cls_ids)

    return stages


def save_composite(stages, name, output_path):
    """Save 2×3 grid at high resolution."""
    fig, axes = plt.subplots(2, 3, figsize=(14, 9.5), dpi=150)
    title_map = [
        ('original', 'Original'),
        ('occluded', 'Component Occlusion'),
        ('binary', 'Sauvola Binarization'),
        ('closed', 'Morphological Close'),
        ('wire_overlay', f'Detected Wires ({stages["n_wires"]})'),
        ('join_overlay', f'Join Result ({stages.get("n_nets", "?")} nets, {stages.get("n_comps", "?")} components)'),
    ]
    for ax, (key, title) in zip(axes.flat, title_map):
        img = stages.get(key)
        if img is not None:
            if len(img.shape) == 3:
                ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            else:
                ax.imshow(img, cmap='gray')
        ax.set_title(title, fontsize=10, fontweight='bold')
        ax.axis('off')
    fig.suptitle(name, fontsize=12, fontweight='bold', y=0.99)
    plt.tight_layout(pad=0.5)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', pad_inches=0.1)
    plt.close()


if __name__ == '__main__':
    gt_images = gt_images_dir()
    hdc_base = hdc_root()
    output = CGHD_WORKSPACE / "ieee-paper" / "figures" / "pipeline_candidates"
    output.mkdir(parents=True, exist_ok=True)

    candidates = [
        ("C29_D2_P4_jpg.jpg", "C29-D2-P4"),
        ("C34_D1_P1_jpg.jpg", "C34-D1-P1"),
        ("C84_D2_P1_jpg.jpg", "C84-D2-P1"),
        ("C4_D2_P1_jpg.jpg", "C4-D2-P1"),
        ("C37_D2_P4_jpg.jpg", "C37-D2-P4"),
        ("C63_D2_P3_jpg.jpg", "C63-D2-P3"),
    ]
    for fname, safe_name in candidates:
        img_path = gt_images / fname
        if not img_path.exists():
            continue
        print(f"Processing {safe_name}...")
        stages = run_pipeline(img_path, hdc_base)
        save_composite(stages, f"{safe_name} — {stages['n_wires']} wires, {stages.get('n_nets','?')} nets",
                       str(output / f"{safe_name}.png"))
        print(f"  OK: {stages['n_wires']} wires, {stages.get('n_nets','?')} nets")
    print(f"\nDone. Files in {output}/")

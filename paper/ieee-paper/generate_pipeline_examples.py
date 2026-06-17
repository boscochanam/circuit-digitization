#!/usr/bin/env python3
"""Generate pipeline example figures for the IEEE paper.
Produces 2x3 grid composites for C245-D2-P1 and C236-D2-P3.
"""
import os, sys, cv2, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

sys.path.insert(0, '/home/claw/circuit-digitization')
os.chdir('/home/claw/circuit-digitization')

from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig, build_component_mask, crop_to_roi, shift_components,
    detect_wires_experiment, sauvola_binary,
)
from wire_detection.core.join_strategies import run_strategy, make_pins, DEFAULT_STRATEGY
from wire_detection.core.component_classes import COMPONENT_TYPES

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

GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
HDC_BASE = Path("/home/claw/circuit-digitization/roboflow_test2")
HDC_SPLITS = ["train", "valid", "test"]
OUTPUT = Path("/home/claw/circuit-digitization/paper/ieee-paper/figures/pipeline_examples")
OUTPUT.mkdir(parents=True, exist_ok=True)


def find_hdc_label_by_prefix(image_name):
    """Find the Roboflow/HDC label file matching an image name prefix."""
    for split in HDC_SPLITS:
        label_dir = HDC_BASE / split / "labels"
        if not label_dir.exists():
            continue
        matches = sorted(label_dir.glob(f"{image_name}_jpg.rf.*.txt"))
        if matches:
            return matches[0]
        # Also try jpeg suffix
        matches = sorted(label_dir.glob(f"{image_name}_jpeg.rf.*.txt"))
        if matches:
            return matches[0]
    return None


def find_exact_match_hdc(image_name, orig_gray):
    """Find the exact pixel-matching Roboflow image and label."""
    for suffix in ["_jpg", "_jpeg"]:
        stem = f"{image_name}{suffix}"
        best_match = None
        best_diff = float('inf')
        for split in HDC_SPLITS:
            img_dir = HDC_BASE / split / "images"
            label_dir = HDC_BASE / split / "labels"
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
            xs = [coords[i] * w for i in range(0, 8, 2)]
            ys = [coords[i] * h for i in range(1, 8, 2)]
            pts = [(int(xs[i]), int(ys[i])) for i in range(4)]
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)
            components.append((cls_id, pts, (int(x1), int(y1), int(x2), int(y2))))
    return components


def draw_obb(img, vertices, color, thickness=1):
    """Draw oriented bounding box using true 4-corner polygon."""
    pts = np.array(vertices, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(img, [pts], True, color, thickness, cv2.LINE_AA)


def run_pipeline(img_path):
    """Run the full pipeline and collect stage images."""
    from PIL import Image
    name = Path(img_path).stem
    pil_img = Image.open(img_path).convert('L')
    gray = np.array(pil_img)
    stages = {}
    stages['original'] = gray.copy()

    # Strip known suffixes to get the base lookup name
    lookup_name = name
    for suffix in ('_jpg', '_jpeg', '_png'):
        if lookup_name.endswith(suffix):
            lookup_name = lookup_name[:-len(suffix)]
            break

    hdc_label = find_hdc_label_by_prefix(lookup_name)
    exact_label, exact_img_path = find_exact_match_hdc(lookup_name, gray)

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
    for comp in comp_labels:
        cls_id, verts, bbox = comp
        color = (0, 200, 0) if cls_id in spice_cls_ids else (0, 180, 255)
        draw_obb(overlay, verts, color, 1)
    stages['wire_overlay'] = overlay.copy()

    # Join result
    if comp_labels and lines_global:
        has_relays = any(c[0] in RELAY_IDS for c in comp_labels)
        if has_relays:
            # Fallback: use basic pin-based join for circuits with relays
            pins = make_pins(lines_global, local_components)
            # Build a simple netlist from wire connections
            from wire_detection.core.join_strategies import run_strategy
            pins, netlist = run_strategy(DEFAULT_STRATEGY, lines_global, local_components)
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
                cx = sum(v[0] for v in verts) // 4
                cy = min(v[1] for v in verts) - 4
                tname = COMPONENT_TYPES.get(cls_id, "?").split("-")[0]
                cv2.putText(join_overlay, tname, (cx - 15, max(12, cy)),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 140), 1, cv2.LINE_AA)
            elif cls_id in RELAY_IDS:
                draw_obb(join_overlay, verts, (80, 80, 60), 1)

        net_colors = [
            (180, 80, 20), (20, 120, 180), (20, 160, 80),
            (160, 40, 160), (40, 160, 160), (180, 140, 40),
            (100, 60, 180), (60, 180, 100),
        ]
        nets = [n for n in netlist.nodes if n.wires]

        for ni, node in enumerate(nets):
            color = net_colors[ni % len(net_colors)]
            for wi in node.wires:
                if 0 <= wi < len(lines_global):
                    ep1, ep2 = lines_global[wi]
                    cv2.line(join_overlay, ep1, ep2, color, 2, cv2.LINE_AA)

        for pin in pins:
            px = int(pin.x) + ox
            py = int(pin.y) + oy
            is_attached = (pin.component_idx, pin.pin_idx) in attached_pins
            comp_cls = local_components[pin.component_idx][0]

            if comp_cls not in spice_cls_ids:
                continue

            pin_net_color = None
            if is_attached:
                for ni, node in enumerate(nets):
                    for np_ in node.pins:
                        if np_.component_idx == pin.component_idx and np_.pin_idx == pin.pin_idx:
                            pin_net_color = net_colors[ni % len(net_colors)]
                            break

            if is_attached and pin_net_color:
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

            dot_color = (0, 220, 0) if is_attached else (0, 0, 255)
            cv2.circle(join_overlay, (px, py), 4, dot_color, -1, cv2.LINE_AA)
            cv2.circle(join_overlay, (px, py), 4, (255, 255, 255), 1, cv2.LINE_AA)

        stages['join_overlay'] = join_overlay.copy()
        stages['n_nets'] = len(nets)
        stages['n_comps'] = sum(1 for c in comp_labels if c[0] in spice_cls_ids)

    return stages


def save_composite(stages, name, output_path):
    """Save 2×3 grid at high resolution (300 dpi)."""
    fig, axes = plt.subplots(2, 3, figsize=(14, 9.5), dpi=300)
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
    plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close()


if __name__ == '__main__':
    candidates = [
        ("C245_D2_P1_jpg.jpg", "C245-D2-P1-jpg.png"),
        ("C236_D2_P3_jpeg.jpg", "C236-D2-P3-jpeg.png"),
    ]
    for fname, out_name in candidates:
        img_path = GT_IMAGES / fname
        if not img_path.exists():
            print(f"ERROR: Source image not found: {img_path}")
            continue
        print(f"Processing {out_name} from {img_path}...")
        stages = run_pipeline(img_path)
        out_path = OUTPUT / out_name
        save_composite(stages, f"{out_name.replace('.png','')} — {stages['n_wires']} wires, {stages.get('n_nets','?')} nets",
                       out_path)
        print(f"  OK: {stages['n_wires']} wires, {stages.get('n_nets','?')} nets → {out_path}")
    print(f"\nDone. Files in {OUTPUT}/")

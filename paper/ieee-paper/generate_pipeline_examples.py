#!/usr/bin/env python3
"""Pipeline visualization using trained YOLO model for component detection.
Shows all real component pins (not just SPICE passives)."""
import os, sys, cv2, math
import numpy as np
from pathlib import Path

sys.path.insert(0, '/home/claw/circuit-digitization')
os.chdir('/home/claw/circuit-digitization')

from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig, build_component_mask, crop_to_roi, shift_components,
    detect_wires_experiment, sauvola_binary,
)
from wire_detection.core.join_strategies import run_strategy, DEFAULT_STRATEGY
from wire_detection.core.component_classes import COMPONENT_TYPES
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Config
cfg = ExperimentConfig(
    name="a16", sauvola_k=0.285, sauvola_window=67, close_kernel=3,
    ccl_min_area=28, endpoint_mode="pca", dedup_mode="overlap",
    dedup_angle=12, dedup_dist=18, anchor_filter_enabled=True,
    anchor_endpoint_dist=16.0, anchor_link_dist=8.0, extraction_mode="component",
)

GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
OUTPUT = Path("/home/claw/circuit-digitization/paper/ieee-paper/figures/pipeline_examples")
OUTPUT.mkdir(parents=True, exist_ok=True)

# Classes that are "relay" / structural — don't show as pins
SKIP_PIN_TYPES = {
    "junction", "terminal", "gnd", "crossover", "vss",
    "text", "unknown", "mechanical", "optical",
    "probe", "probe-current", "probe-voltage",
}
SKIP_PIN_IDS = {cid for cid, name in COMPONENT_TYPES.items() if name in SKIP_PIN_TYPES}


def load_yolo_components(image_path):
    """Run trained YOLO model and return components in standard format."""
    from ultralytics import YOLO
    model_path = "models/component_detection/yolo26m_obb_16class_aug.pt"
    model = YOLO(model_path)
    results = model(str(image_path), task="obb", conf=0.5)
    
    components = []
    for result in results:
        if result.obb is None:
            continue
        for i in range(len(result.obb.cls)):
            cls_id = int(result.obb.cls[i])
            bbox = result.obb.xyxy[i].tolist()
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            polygon = result.obb.xyxyxyxy[i].tolist()
            polygon_pts = [(int(p[0]), int(p[1])) for p in polygon]
            components.append((cls_id, polygon_pts, (x1, y1, x2, y2)))
    return components


def draw_obb(img, vertices, color, thickness=1):
    pts = np.array(vertices, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(img, [pts], True, color, thickness, cv2.LINE_AA)


def run_pipeline(img_path):
    from PIL import Image
    pil_img = Image.open(img_path).convert('L')
    gray = np.array(pil_img)
    stages = {}
    stages['original'] = gray.copy()

    # Use trained YOLO model for component detection
    comp_labels = load_yolo_components(img_path)

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

    # Wire overlay
    overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for (x1, y1), (x2, y2) in lines_global:
        cv2.line(overlay, (x1, y1), (x2, y2), (0, 0, 255), 2, cv2.LINE_AA)
    for comp in comp_labels:
        cls_id, verts, bbox = comp
        if cls_id not in SKIP_PIN_IDS:
            draw_obb(overlay, verts, (0, 200, 0), 1)
    stages['wire_overlay'] = overlay.copy()

    # Join result — no colored net lines, just pin dots
    if comp_labels and lines_global:
        pins, netlist = run_strategy(DEFAULT_STRATEGY, lines_global, local_components)

        attached_pins = set()
        for node in netlist.nodes:
            for pin in node.pins:
                attached_pins.add((pin.component_idx, pin.pin_idx))

        join_overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        join_overlay = (join_overlay * 0.4 + 40).astype(np.uint8)

        # Draw OBB polygons for all components
        for comp in comp_labels:
            cls_id, verts, bbox = comp
            if cls_id not in SKIP_PIN_IDS:
                draw_obb(join_overlay, verts, (60, 60, 45), 1)
                cx = sum(v[0] for v in verts) // 4
                cy = min(v[1] for v in verts) - 4
                tname = COMPONENT_TYPES.get(cls_id, "?").split("-")[0]
                cv2.putText(join_overlay, tname, (cx - 15, max(12, cy)),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 140), 1, cv2.LINE_AA)

        # Draw pin dots for ALL components (not just SPICE passives)
        for pin in pins:
            px = int(pin.x) + ox
            py = int(pin.y) + oy
            comp_cls = local_components[pin.component_idx][0]
            if comp_cls in SKIP_PIN_IDS:
                continue

            is_attached = (pin.component_idx, pin.pin_idx) in attached_pins
            dot_color = (0, 220, 0) if is_attached else (0, 0, 255)
            cv2.circle(join_overlay, (px, py), 4, dot_color, -1, cv2.LINE_AA)
            cv2.circle(join_overlay, (px, py), 4, (255, 255, 255), 1, cv2.LINE_AA)

        stages['join_overlay'] = join_overlay.copy()
        nets = [n for n in netlist.nodes if n.wires]
        stages['n_nets'] = len(nets)
        stages['n_comps'] = sum(1 for c in comp_labels if c[0] not in SKIP_PIN_IDS)

    return stages


def save_composite(stages, name, output_path):
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
    plt.tight_layout(pad=0.8, rect=[0, 0, 1, 0.95])
    fig.suptitle(name, fontsize=13, fontweight='bold', y=0.995)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close()


if __name__ == '__main__':
    candidates = [
        ("C84_D1_P2_jpg.jpg", "C84-D1-P2-jpg.png"),
        ("C83_D2_P4_jpg.jpg", "C83-D2-P4-jpg.png"),
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

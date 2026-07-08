#!/usr/bin/env python3
"""
MAPPING EXPERIMENT V2 — PHASE 4: Pin templates, image verification, topology.

Phase 3 best: selective_disambiguate threshold=30
  GT: 93.10% EP, 88.93% wire, 143 same-comp errors
  Detected: 94.88% EP, 91.91% wire

Phase 4 approaches:
  1. Pin template estimation (component-type + orientation aware)
  2. Image-based verification (check wire pixels near component)
  3. Wire mask overlap with component masks
  4. Topology-aware mapping (component interaction priors)
  5. Iterative refinement using connectivity graph
  6. Combined best approaches
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict

import cv2
import numpy as np


from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig,
    build_component_mask,
    crop_to_roi,
)
from wire_detection.benchmark.connectivity_experiment import COMPONENT_NAMES
from wire_detection.paths import gt_images_dir, gt_labels_dir, hdc_root, output_dir

HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = output_dir() / "mapping_experiment_v2"
LOG_FILE = OUTPUT_DIR / "status.log"

JUNCTION_IDS = {19, 44}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def find_hdc_label(image_name):
    for split in HDC_SPLITS:
        label_dir = hdc_root() / split / "labels"
        if not label_dir.exists():
            continue
        for suffix in ["_jpg", "_png", "_jpeg", ""]:
            pattern = f"{image_name}{suffix}.rf.*.txt" if suffix else f"{image_name}.rf.*.txt"
            matches = sorted(label_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def load_components(image_name, w, h):
    hdc_path = find_hdc_label(image_name)
    if hdc_path is None:
        return []
    return ref.parse_components(hdc_path, w, h)


def point_to_bbox_dist(px, py, bbox):
    xmin, ymin, xmax, ymax = bbox
    cx = max(xmin, min(px, xmax))
    cy = max(ymin, min(py, ymax))
    return math.hypot(px - cx, py - cy)


def point_in_polygon(px, py, vertices):
    n = len(vertices)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = vertices[i]
        xj, yj = vertices[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


TWO_TERMINAL_NAMES = {
    "resistor", "capacitor-unpolarized", "capacitor-polarized",
    "inductor", "diode", "diode-zener", "diode-light_emitting",
    "diode-thyrector", "fuse", "thermistor", "varistor", "crystal",
    "resistor-adjustable", "capacitor-adjustable", "inductor-ferrite",
}
MULTI_TERMINAL_NAMES = {
    "integrated_circuit", "integrated_circuit-ne555",
    "integrated_circuit-voltage_regulator", "transistor", "transistor-pnp",
    "operational_amplifier", "optocoupler", "triac", "diac",
}


def is_two_terminal(cls_id):
    name = COMPONENT_NAMES.get(cls_id, "")
    return name in TWO_TERMINAL_NAMES or "resistor" in name or "capacitor" in name or "diode" in name


def is_multi_terminal(cls_id):
    name = COMPONENT_NAMES.get(cls_id, "")
    return name in MULTI_TERMINAL_NAMES or "integrated" in name or "transistor" in name


def compute_gt_mapping(wires, components):
    gt_mappings = []
    for ep1, ep2 in wires:
        cands1 = sorted([(ci, point_to_bbox_dist(ep1[0], ep1[1], comp[2]) + (10 if comp[0] in JUNCTION_IDS else 0))
                         for ci, comp in enumerate(components)], key=lambda x: x[1])
        cands2 = sorted([(ci, point_to_bbox_dist(ep2[0], ep2[1], comp[2]) + (10 if comp[0] in JUNCTION_IDS else 0))
                         for ci, comp in enumerate(components)], key=lambda x: x[1])
        best1 = cands1[0][0] if cands1 else -1
        best2 = cands2[0][0] if cands2 else -1
        if best1 == best2 and best1 >= 0 and len(cands2) > 1:
            if cands2[1][1] < cands2[0][1] + 30:
                best2 = cands2[1][0]
        gt_mappings.append((best1, best2))
    return gt_mappings


def get_candidates(ep, components):
    cands = []
    for ci, comp in enumerate(components):
        d = point_to_bbox_dist(ep[0], ep[1], comp[2])
        cands.append((ci, d))
    cands.sort(key=lambda x: x[1])
    return cands


# ═══════════════════════════════════════════════════
# PIN TEMPLATE METHODS
# ═══════════════════════════════════════════════════

def get_obb_pins(vertices):
    """Get pin locations from OBB — midpoints of short edges."""
    d02 = math.hypot(vertices[0][0] - vertices[2][0], vertices[0][1] - vertices[2][1])
    d13 = math.hypot(vertices[1][0] - vertices[3][0], vertices[1][1] - vertices[3][1])
    if d02 >= d13:
        mid1 = ((vertices[0][0] + vertices[1][0]) // 2, (vertices[0][1] + vertices[1][1]) // 2)
        mid2 = ((vertices[2][0] + vertices[3][0]) // 2, (vertices[2][1] + vertices[3][1]) // 2)
    else:
        mid1 = ((vertices[1][0] + vertices[2][0]) // 2, (vertices[1][1] + vertices[2][1]) // 2)
        mid2 = ((vertices[3][0] + vertices[0][0]) // 2, (vertices[3][1] + vertices[0][1]) // 2)
    return [mid1, mid2]


def get_component_pin_locations(cls_id, vertices):
    """Get estimated pin locations for a component."""
    name = COMPONENT_NAMES.get(cls_id, "")

    if is_two_terminal(cls_id):
        return get_obb_pins(vertices)

    if "transistor" in name:
        pins = get_obb_pins(vertices)
        cx = sum(v[0] for v in vertices) // 4
        cy = sum(v[1] for v in vertices) // 4
        pins.append((cx, cy))
        return pins

    if "integrated" in name:
        pins = []
        for i in range(4):
            mid = (
                (vertices[i][0] + vertices[(i + 1) % 4][0]) // 2,
                (vertices[i][1] + vertices[(i + 1) % 4][1]) // 2,
            )
            pins.append(mid)
        pins.extend(vertices)
        return pins

    return get_obb_pins(vertices)


def map_pin_template(wire, components):
    """Map wire endpoints to component pin locations."""
    ep1, ep2 = wire

    all_pins = []
    for ci, comp in enumerate(components):
        pins = get_component_pin_locations(comp[0], comp[1])
        for pi, (px, py) in enumerate(pins):
            all_pins.append((ci, pi, px, py))

    # Find nearest pin for each endpoint
    best1 = (-1, float("inf"))
    best2 = (-1, float("inf"))

    for ci, pi, px, py in all_pins:
        d1 = math.hypot(ep1[0] - px, ep1[1] - py)
        d2 = math.hypot(ep2[0] - px, ep2[1] - py)
        if d1 < best1[1]:
            best1 = (ci, d1)
        if d2 < best2[1]:
            best2 = (ci, d2)

    return best1[0], best2[0]


def map_pin_template_disambiguated(wire, components):
    """Pin template + disambiguation for 2-terminal components."""
    ep1, ep2 = wire

    all_pins = []
    for ci, comp in enumerate(components):
        pins = get_component_pin_locations(comp[0], comp[1])
        for pi, (px, py) in enumerate(pins):
            all_pins.append((ci, pi, px, py))

    # Get sorted candidates per endpoint
    cands1 = []
    cands2 = []
    for ci, pi, px, py in all_pins:
        d1 = math.hypot(ep1[0] - px, ep1[1] - py)
        d2 = math.hypot(ep2[0] - px, ep2[1] - py)
        cands1.append((ci, d1))
        cands2.append((ci, d2))

    cands1.sort(key=lambda x: x[1])
    cands2.sort(key=lambda x: x[1])

    best1 = cands1[0][0] if cands1 else -1
    best2 = cands2[0][0] if cands2 else -1

    # Disambiguate for 2-terminal components
    if best1 == best2 and best1 >= 0:
        if is_two_terminal(components[best1][0]):
            d1, d2 = cands1[0][1], cands2[0][1]
            if d2 >= d1:
                for ci, d in cands2[1:]:
                    if ci != best1:
                        best2 = ci
                        break
            else:
                for ci, d in cands1[1:]:
                    if ci != best2:
                        best1 = ci
                        break

    return best1, best2


# ═══════════════════════════════════════════════════
# IMAGE-BASED METHODS
# ═══════════════════════════════════════════════════

def map_image_overlap(wire, components, binary_image=None):
    """Check wire mask overlap with component polygons."""
    if binary_image is None:
        return map_baseline_impl(wire, components)

    ep1, ep2 = wire
    h, w = binary_image.shape

    # Create a line mask for the wire
    wire_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.line(wire_mask, (int(ep1[0]), int(ep1[1])), (int(ep2[0]), int(ep2[1])), 255, 3)

    # Dilate wire mask slightly
    kernel = np.ones((5, 5), np.uint8)
    wire_dilated = cv2.dilate(wire_mask, kernel, iterations=1)

    # Check overlap with each component polygon
    best1_overlap = 0
    best1_ci = -1
    best2_overlap = 0
    best2_ci = -1

    # Create endpoint regions
    ep1_mask = np.zeros((h, w), dtype=np.uint8)
    ep2_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(ep1_mask, (int(ep1[0]), int(ep1[1])), 15, 255, -1)
    cv2.circle(ep2_mask, (int(ep2[0]), int(ep2[1])), 15, 255, -1)

    for ci, comp in enumerate(components):
        comp_mask = np.zeros((h, w), dtype=np.uint8)
        pts = np.array(comp[1], dtype=np.int32)
        cv2.fillPoly(comp_mask, [pts], 255)

        overlap1 = cv2.countNonZero(cv2.bitwise_and(ep1_mask, comp_mask))
        overlap2 = cv2.countNonZero(cv2.bitwise_and(ep2_mask, comp_mask))

        if overlap1 > best1_overlap:
            best1_overlap = overlap1
            best1_ci = ci
        if overlap2 > best2_overlap:
            best2_overlap = overlap2
            best2_ci = ci

    if best1_ci < 0:
        c1 = get_candidates(ep1, components)
        best1_ci = c1[0][0] if c1 else -1
    if best2_ci < 0:
        c2 = get_candidates(ep2, components)
        best2_ci = c2[0][0] if c2 else -1

    return best1_ci, best2_ci


def map_image_overlap_disambiguated(wire, components, binary_image=None):
    """Image overlap + disambiguation."""
    ep1, ep2 = wire

    if binary_image is not None:
        pred1, pred2 = map_image_overlap(wire, components, binary_image)
    else:
        pred1, pred2 = map_baseline_impl(wire, components)

    if pred1 == pred2 and pred1 >= 0:
        if is_two_terminal(components[pred1][0]):
            c1 = get_candidates(ep1, components)
            c2 = get_candidates(ep2, components)
            d1, d2 = c1[0][1], c2[0][1]
            if d2 >= d1:
                for ci, d in c2[1:]:
                    if ci != pred1:
                        pred2 = ci
                        break
            else:
                for ci, d in c1[1:]:
                    if ci != pred2:
                        pred1 = ci
                        break

    return pred1, pred2


# ═══════════════════════════════════════════════════
# TOPOLOGY-AWARE METHODS
# ═══════════════════════════════════════════════════

def build_connectivity_graph(all_wires, components):
    """Build a graph of which components are connected by wires."""
    graph = defaultdict(lambda: defaultdict(int))  # comp1 -> comp2 -> count

    for ep1, ep2 in all_wires:
        c1 = get_candidates(ep1, components)
        c2 = get_candidates(ep2, components)
        best1 = c1[0][0] if c1 else -1
        best2 = c2[0][0] if c2 else -1

        if best1 >= 0 and best2 >= 0 and best1 != best2:
            graph[best1][best2] += 1
            graph[best2][best1] += 1

    return graph


def map_topology_aware(wire, components, connectivity_graph=None):
    """Use connectivity graph to prefer components that are commonly connected."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)

    if connectivity_graph is None:
        best1 = c1[0][0] if c1 else -1
        best2 = c2[0][0] if c2 else -1
        return best1, best2

    # Score candidates by: distance + connectivity bonus
    def score_candidate(ep_cands, other_cands, graph):
        scored = []
        for ci, d in ep_cands:
            # Base score: distance (lower is better)
            score = d

            # Connectivity bonus: if this component is commonly connected to
            # the other endpoint's best candidate
            if other_cands:
                other_best = other_cands[0][0]
                if other_best in graph and ci in graph[other_best]:
                    # Reduce score for commonly connected components
                    connectivity = graph[other_best][ci]
                    score -= connectivity * 2  # bonus per connection

            scored.append((ci, score))
        scored.sort(key=lambda x: x[1])
        return scored

    scored1 = score_candidate(c1, c2, connectivity_graph)
    scored2 = score_candidate(c2, c1, connectivity_graph)

    best1 = scored1[0][0] if scored1 else -1
    best2 = scored2[0][0] if scored2 else -1

    return best1, best2


# ═══════════════════════════════════════════════════
# BASELINE & HELPERS
# ═══════════════════════════════════════════════════

def map_baseline_impl(wire, components):
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    return (c1[0][0] if c1 else -1, c2[0][0] if c2 else -1)


def map_selective_30(wire, components, **kw):
    """Selective disambiguation with threshold=30 (Phase 3 best)."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    best1 = c1[0][0] if c1 else -1
    best2 = c2[0][0] if c2 else -1

    if best1 == best2 and best1 >= 0:
        comp = components[best1]
        cls_id = comp[0]

        if is_multi_terminal(cls_id):
            return best1, best2

        inside1 = point_in_polygon(ep1[0], ep1[1], comp[1])
        inside2 = point_in_polygon(ep2[0], ep2[1], comp[1])
        if inside1 and inside2:
            return best1, best2

        if is_two_terminal(cls_id):
            d1, d2 = c1[0][1], c2[0][1]
            if d2 >= d1:
                for ci, d in c2[1:]:
                    if ci != best1:
                        best2 = ci
                        break
            else:
                for ci, d in c1[1:]:
                    if ci != best2:
                        best1 = ci
                        break
        else:
            gap1 = c1[1][1] - c1[0][1] if len(c1) > 1 else float("inf")
            gap2 = c2[1][1] - c2[0][1] if len(c2) > 1 else float("inf")

            if gap2 < 30:
                for ci, d in c2[1:]:
                    if ci != best1:
                        best2 = ci
                        break
            elif gap1 < 30:
                for ci, d in c1[1:]:
                    if ci != best2:
                        best1 = ci
                        break

    return best1, best2


def map_selective_25(wire, components, **kw):
    """Selective disambiguation with threshold=25."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    best1 = c1[0][0] if c1 else -1
    best2 = c2[0][0] if c2 else -1

    if best1 == best2 and best1 >= 0:
        comp = components[best1]
        cls_id = comp[0]

        if is_multi_terminal(cls_id):
            return best1, best2

        inside1 = point_in_polygon(ep1[0], ep1[1], comp[1])
        inside2 = point_in_polygon(ep2[0], ep2[1], comp[1])
        if inside1 and inside2:
            return best1, best2

        if is_two_terminal(cls_id):
            d1, d2 = c1[0][1], c2[0][1]
            if d2 >= d1:
                for ci, d in c2[1:]:
                    if ci != best1:
                        best2 = ci
                        break
            else:
                for ci, d in c1[1:]:
                    if ci != best2:
                        best1 = ci
                        break
        else:
            gap1 = c1[1][1] - c1[0][1] if len(c1) > 1 else float("inf")
            gap2 = c2[1][1] - c2[0][1] if len(c2) > 1 else float("inf")

            if gap2 < 25:
                for ci, d in c2[1:]:
                    if ci != best1:
                        best2 = ci
                        break
            elif gap1 < 25:
                for ci, d in c1[1:]:
                    if ci != best2:
                        best1 = ci
                        break

    return best1, best2


# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════

def run_phase4():
    log("\n" + "=" * 80)
    log("PHASE 4: PIN TEMPLATES, IMAGE VERIFICATION, TOPOLOGY")
    log("=" * 80)

    cfg = ExperimentConfig(
        name="best_candidate_v4",
        sauvola_k=0.285, sauvola_window=67,
        close_kernel=3, ccl_min_area=28,
        dedup_angle=10.0, dedup_dist=18.0,
        crop_padding=10, occlusion_margin=0.15,
        normalize_mode="none", endpoint_mode="pca",
        dedup_mode="overlap",
        anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
    )

    log("Loading images...")
    all_data = []
    for gt_file in sorted(gt_labels_dir().glob("*_jpg.txt")):
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = gt_images_dir() / f"{image_name}_jpg.jpg"
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape
        gt_lines = ref.load_ground_truth(gt_file, w, h)
        components = load_components(image_name, w, h)
        if not components:
            continue
        all_data.append((image_name, gray, gt_lines, components))

    log(f"Loaded {len(all_data)} images")

    # Compute pseudo-GT
    all_gt_mappings = []
    for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
        gt_maps = compute_gt_mapping(gt_lines, components)
        all_gt_mappings.append(gt_maps)

    # Pre-compute binary images
    binary_cache = {}
    for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
        h, w = gray.shape
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        binary_cache[img_idx] = (cropped, ox, oy)

    methods = [
        ("00_baseline", lambda w, c, **kw: map_baseline_impl(w, c)),
        ("01_selective_30", lambda w, c, **kw: map_selective_30(w, c)),
        ("02_selective_25", lambda w, c, **kw: map_selective_25(w, c)),
        ("03_pin_template", lambda w, c, **kw: map_pin_template(w, c)),
        ("04_pin_template_disamb", lambda w, c, **kw: map_pin_template_disambiguated(w, c)),
        ("05_image_overlap", lambda w, c, **kw: map_image_overlap(w, c, kw.get("binary_image"))),
        ("06_image_overlap_disamb", lambda w, c, **kw: map_image_overlap_disambiguated(w, c, kw.get("binary_image"))),
    ]

    # ═══ GT Wire Evaluation ═══
    log("\n" + "=" * 80)
    log("GT WIRE EVALUATION")
    log("=" * 80)

    results = {}

    for method_name, method_fn in methods:
        needs_binary = "image" in method_name
        log(f"\nEvaluating: {method_name}")
        t0 = time.time()

        total_ep = 0
        correct_ep = 0
        total_wires = 0
        correct_both = 0
        same_comp = 0

        for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
            gt_maps = all_gt_mappings[img_idx]
            cropped, ox, oy = binary_cache[img_idx]

            for wi, ((ep1, ep2), (gt1, gt2)) in enumerate(zip(gt_lines, gt_maps)):
                kwargs = {}
                if needs_binary:
                    kwargs["binary_image"] = cropped

                pred1, pred2 = method_fn((ep1, ep2), components, **kwargs)

                total_ep += 2
                if pred1 == gt1:
                    correct_ep += 1
                if pred2 == gt2:
                    correct_ep += 1

                total_wires += 1
                if pred1 == gt1 and pred2 == gt2:
                    correct_both += 1
                if pred1 == pred2 and pred1 >= 0:
                    same_comp += 1

        elapsed = time.time() - t0
        ep_acc = correct_ep / max(total_ep, 1)
        wire_both = correct_both / max(total_wires, 1)

        results[method_name] = {
            "endpoint_accuracy": ep_acc,
            "wire_accuracy_both": wire_both,
            "same_comp": same_comp,
            "total_wires": total_wires,
            "elapsed": elapsed,
        }

        log(f"  EP: {ep_acc:.4f} ({correct_ep}/{total_ep})")
        log(f"  Wire(both): {wire_both:.4f} ({correct_both}/{total_wires})")
        log(f"  Same-comp: {same_comp}")
        log(f"  Time: {elapsed:.1f}s")

    # ═══ Extended Threshold Sweep ═══
    log("\n" + "=" * 80)
    log("EXTENDED THRESHOLD SWEEP (with pin template)")
    log("=" * 80)

    # Try combining pin template with selective disambiguation
    for threshold in [10, 15, 20, 25, 30, 35, 40]:
        total_ep = 0
        correct_ep = 0
        total_wires = 0
        correct_both = 0
        same_comp = 0

        for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
            gt_maps = all_gt_mappings[img_idx]

            for wi, ((ep1, ep2), (gt1, gt2)) in enumerate(zip(gt_lines, gt_maps)):
                # Pin template + selective disambiguation
                all_pins = []
                for ci, comp in enumerate(components):
                    pins = get_component_pin_locations(comp[0], comp[1])
                    for pi, (px, py) in enumerate(pins):
                        all_pins.append((ci, pi, px, py))

                cands1 = sorted([(ci, math.hypot(ep1[0] - px, ep1[1] - py))
                                for ci, pi, px, py in all_pins], key=lambda x: x[1])
                cands2 = sorted([(ci, math.hypot(ep2[0] - px, ep2[1] - py))
                                for ci, pi, px, py in all_pins], key=lambda x: x[1])

                best1 = cands1[0][0] if cands1 else -1
                best2 = cands2[0][0] if cands2 else -1

                if best1 == best2 and best1 >= 0:
                    comp = components[best1]
                    if not is_multi_terminal(comp[0]):
                        inside1 = point_in_polygon(ep1[0], ep1[1], comp[1])
                        inside2 = point_in_polygon(ep2[0], ep2[1], comp[1])
                        if not (inside1 and inside2):
                            if is_two_terminal(comp[0]):
                                d1, d2 = cands1[0][1], cands2[0][1]
                                if d2 >= d1:
                                    for ci, d in cands2[1:]:
                                        if ci != best1:
                                            best2 = ci
                                            break
                                else:
                                    for ci, d in cands1[1:]:
                                        if ci != best2:
                                            best1 = ci
                                            break
                            else:
                                gap1 = cands1[1][1] - cands1[0][1] if len(cands1) > 1 else float("inf")
                                gap2 = cands2[1][1] - cands2[0][1] if len(cands2) > 1 else float("inf")
                                if gap2 < threshold:
                                    for ci, d in cands2[1:]:
                                        if ci != best1:
                                            best2 = ci
                                            break
                                elif gap1 < threshold:
                                    for ci, d in cands1[1:]:
                                        if ci != best2:
                                            best1 = ci
                                            break

                total_ep += 2
                if best1 == gt1:
                    correct_ep += 1
                if best2 == gt2:
                    correct_ep += 1

                total_wires += 1
                if best1 == gt1 and best2 == gt2:
                    correct_both += 1
                if best1 == best2 and best1 >= 0:
                    same_comp += 1

        ep_acc = correct_ep / max(total_ep, 1)
        wire_both = correct_both / max(total_wires, 1)
        log(f"  pin_template+selective_{threshold}: EP={ep_acc:.4f}, Wire={wire_both:.4f}, SameComp={same_comp}")

    # ═══ Synthesis ═══
    log("\n" + "=" * 80)
    log("PHASE 4 SYNTHESIS")
    log("=" * 80)

    log("\nResults:")
    log(f"{'Method':<35s} {'EP Acc':>8s} {'Wire':>8s} {'SameCmp':>8s}")
    log("-" * 62)
    for name, res in sorted(results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True):
        log(f"{name:<35s} {res['endpoint_accuracy']:8.4f} {res['wire_accuracy_both']:8.4f} {res['same_comp']:8d}")

    # Save
    (OUTPUT_DIR / "phase4_summary.json").write_text(
        json.dumps({k: v for k, v in results.items()}, indent=2, default=str), encoding="utf-8"
    )

    log(f"\nSaved to {OUTPUT_DIR / 'phase4_summary.json'}")
    log("PHASE 4 COMPLETE")


if __name__ == "__main__":
    run_phase4()

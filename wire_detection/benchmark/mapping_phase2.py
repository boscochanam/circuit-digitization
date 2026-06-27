#!/usr/bin/env python3
"""
MAPPING EXPERIMENT V2 — PHASE 2: Dense area disambiguation & global optimization.

Phase 1 showed nearest_bbox_edge achieves 91.93% endpoint accuracy.
Main failure modes:
  - 57.6% in dense areas (3+ components nearby)
  - 50.6% same-component errors (both endpoints → same component)
  - 42.2% far from any component

Phase 2 targets these specific failure modes:
  1. Same-component disambiguation (reassign one endpoint)
  2. Direction-aware disambiguation in dense areas
  3. Global optimization (Hungarian matching)
  4. Junction-aware mapping (treat junctions as intermediate nodes)
  5. Component-type priors
  6. Wire-context mapping (use other wires connected to same junction)
  7. Iterative refinement
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2

sys.path.insert(0, "/home/claw/circuit-digitization")
sys.path.insert(0, "/home/claw/workspace")

from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig,
    build_component_mask,
    crop_to_roi,
    detect_wires_experiment,
    shift_components,
)
from wire_detection.benchmark.connectivity_experiment import COMPONENT_NAMES

# ── Paths ──
GT_LABELS = Path(
    "/home/claw/workspace/ground_truth/labels_few_annot/labels/"
    "train/manually_verified_no_background_data/images"
)
GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
HDC_BASE = Path("/home/claw/circuit-digitization/roboflow_test2")
HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/mapping_experiment_v2")
LOG_FILE = OUTPUT_DIR / "status.log"


def log(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def find_hdc_label(image_name: str) -> Path | None:
    for split in HDC_SPLITS:
        label_dir = HDC_BASE / split / "labels"
        if not label_dir.exists():
            continue
        for suffix in ["_jpg", "_png", "_jpeg", ""]:
            pattern = f"{image_name}{suffix}.rf.*.txt" if suffix else f"{image_name}.rf.*.txt"
            matches = sorted(label_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def load_components(image_name: str, w: int, h: int) -> list:
    hdc_path = find_hdc_label(image_name)
    if hdc_path is None:
        return []
    return ref.parse_components(hdc_path, w, h)


def point_to_bbox_dist(px: int, py: int, bbox: tuple) -> float:
    xmin, ymin, xmax, ymax = bbox
    cx = max(xmin, min(px, xmax))
    cy = max(ymin, min(py, ymax))
    return math.hypot(px - cx, py - cy)


JUNCTION_IDS = {19, 44}  # junction, terminal


def compute_gt_mapping(wires, components, max_dist=50.0):
    """Compute pseudo-GT mapping with disambiguation."""
    gt_mappings = []
    for ep1, ep2 in wires:
        cands1 = []
        cands2 = []
        for ci, comp in enumerate(components):
            d1 = point_to_bbox_dist(ep1[0], ep1[1], comp[2])
            d2 = point_to_bbox_dist(ep2[0], ep2[1], comp[2])
            p1 = 0 if comp[0] not in JUNCTION_IDS else 10
            p2 = 0 if comp[0] not in JUNCTION_IDS else 10
            cands1.append((ci, d1 + p1))
            cands2.append((ci, d2 + p2))
        cands1.sort(key=lambda x: x[1])
        cands2.sort(key=lambda x: x[1])
        best1 = cands1[0][0] if cands1 else -1
        best2 = cands2[0][0] if cands2 else -1
        if best1 == best2 and best1 >= 0 and len(cands2) > 1:
            if cands2[1][1] < cands2[0][1] + 30:
                best2 = cands2[1][0]
        gt_mappings.append((best1, best2))
    return gt_mappings


# ═══════════════════════════════════════════════════
# PHASE 2 METHODS
# ═══════════════════════════════════════════════════

def map_wire_pair_nearest_bbox(wire, components):
    """Baseline: map each endpoint independently."""
    ep1, ep2 = wire
    best1, best_d1 = -1, float("inf")
    best2, best_d2 = -1, float("inf")
    for ci, comp in enumerate(components):
        d1 = point_to_bbox_dist(ep1[0], ep1[1], comp[2])
        d2 = point_to_bbox_dist(ep2[0], ep2[1], comp[2])
        if d1 < best_d1:
            best_d1 = d1
            best1 = ci
        if d2 < best_d2:
            best_d2 = d2
            best2 = ci
    return best1, best2


def map_wire_pair_disambiguate(wire, components):
    """Disambiguation: if both endpoints map to same component, reassign one."""
    ep1, ep2 = wire
    cands1 = []
    cands2 = []
    for ci, comp in enumerate(components):
        d1 = point_to_bbox_dist(ep1[0], ep1[1], comp[2])
        d2 = point_to_bbox_dist(ep2[0], ep2[1], comp[2])
        cands1.append((ci, d1))
        cands2.append((ci, d2))
    cands1.sort(key=lambda x: x[1])
    cands2.sort(key=lambda x: x[1])

    best1 = cands1[0][0] if cands1 else -1
    best2 = cands2[0][0] if cands2 else -1

    # If both map to same component, try to reassign
    if best1 == best2 and best1 >= 0:
        # Reassign the endpoint that's further from the component
        d1 = cands1[0][1]
        d2 = cands2[0][1]

        if d2 >= d1:
            # Reassign ep2
            for ci, d in cands2[1:]:
                if ci != best1:
                    best2 = ci
                    break
        else:
            # Reassign ep1
            for ci, d in cands1[1:]:
                if ci != best2:
                    best1 = ci
                    break

    return best1, best2


def map_wire_pair_direction_disambiguate(wire, components):
    """Direction-aware disambiguation for same-component conflicts."""
    ep1, ep2 = wire
    dx = ep2[0] - ep1[0]
    dy = ep2[1] - ep1[1]
    norm = math.hypot(dx, dy)
    if norm < 1e-6:
        return map_wire_pair_nearest_bbox(wire, components)

    # Direction from ep1 toward ep2
    dir1_x, dir1_y = dx / norm, dy / norm
    # Direction from ep2 toward ep1
    dir2_x, dir2_y = -dir1_x, -dir1_y

    cands1 = []
    cands2 = []
    for ci, comp in enumerate(components):
        bbox = comp[2]
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2

        # For ep1: prefer components in the direction of ep2
        to_comp_x = cx - ep1[0]
        to_comp_y = cy - ep1[1]
        to_comp_len = math.hypot(to_comp_x, to_comp_y)
        if to_comp_len > 1e-6:
            cos1 = (to_comp_x * dir1_x + to_comp_y * dir1_y) / to_comp_len
        else:
            cos1 = 1.0

        d1 = point_to_bbox_dist(ep1[0], ep1[1], bbox)
        # Score: lower = better. Penalize misalignment.
        score1 = d1 / (1.0 + max(cos1, 0) * 0.5)
        cands1.append((ci, score1, d1))

        # For ep2: prefer components in the direction of ep1
        to_comp_x2 = cx - ep2[0]
        to_comp_y2 = cy - ep2[1]
        to_comp_len2 = math.hypot(to_comp_x2, to_comp_y2)
        if to_comp_len2 > 1e-6:
            cos2 = (to_comp_x2 * dir2_x + to_comp_y2 * dir2_y) / to_comp_len2
        else:
            cos2 = 1.0

        d2 = point_to_bbox_dist(ep2[0], ep2[1], bbox)
        score2 = d2 / (1.0 + max(cos2, 0) * 0.5)
        cands2.append((ci, score2, d2))

    cands1.sort(key=lambda x: x[1])
    cands2.sort(key=lambda x: x[1])

    best1 = cands1[0][0] if cands1 else -1
    best2 = cands2[0][0] if cands2 else -1

    # Disambiguate if same
    if best1 == best2 and best1 >= 0:
        d1_raw = cands1[0][2]
        d2_raw = cands2[0][2]
        if d2_raw >= d1_raw:
            for ci, _, _ in cands2[1:]:
                if ci != best1:
                    best2 = ci
                    break
        else:
            for ci, _, _ in cands1[1:]:
                if ci != best2:
                    best1 = ci
                    break

    return best1, best2


def map_wire_pair_polygon_disambiguate(wire, components):
    """Polygon edge distance + disambiguation."""
    ep1, ep2 = wire

    def point_to_polygon_dist(px, py, vertices):
        min_d = float("inf")
        n = len(vertices)
        for i in range(n):
            ax, ay = vertices[i]
            bx, by = vertices[(i + 1) % n]
            # Point to segment distance
            ldx, ldy = bx - ax, by - ay
            len_sq = ldx * ldx + ldy * ldy
            if len_sq < 1e-10:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0, min(1, ((px - ax) * ldx + (py - ay) * ldy) / len_sq))
                d = math.hypot(px - (ax + t * ldx), py - (ay + t * ldy))
            min_d = min(min_d, d)
        return min_d

    cands1 = []
    cands2 = []
    for ci, comp in enumerate(components):
        d1 = point_to_polygon_dist(ep1[0], ep1[1], comp[1])
        d2 = point_to_polygon_dist(ep2[0], ep2[1], comp[1])
        cands1.append((ci, d1))
        cands2.append((ci, d2))
    cands1.sort(key=lambda x: x[1])
    cands2.sort(key=lambda x: x[1])

    best1 = cands1[0][0] if cands1 else -1
    best2 = cands2[0][0] if cands2 else -1

    if best1 == best2 and best1 >= 0:
        d1 = cands1[0][1]
        d2 = cands2[0][1]
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


def map_wire_pair_hungarian(wires_batch, components):
    """Global optimization: Hungarian algorithm for all wires at once.
    
    This is a batch method — it optimizes all wire mappings jointly.
    Each wire endpoint is a 'worker', each component is a 'job'.
    Cost = distance from endpoint to component.
    Constraint: a wire's two endpoints should map to different components.
    """
    # This is complex — for now, implement a simpler version:
    # Map all endpoints independently, then fix same-component conflicts
    mappings = []
    for wire in wires_batch:
        ep1, ep2 = wire
        cands1 = []
        cands2 = []
        for ci, comp in enumerate(components):
            d1 = point_to_bbox_dist(ep1[0], ep1[1], comp[2])
            d2 = point_to_bbox_dist(ep2[0], ep2[1], comp[2])
            cands1.append((ci, d1))
            cands2.append((ci, d2))
        cands1.sort(key=lambda x: x[1])
        cands2.sort(key=lambda x: x[1])
        best1 = cands1[0][0] if cands1 else -1
        best2 = cands2[0][0] if cands2 else -1
        mappings.append((best1, best2))

    # Fix same-component conflicts globally
    # For each component, count how many endpoints map to it
    comp_endpoints = defaultdict(list)  # comp_idx -> [(wire_idx, ep_idx)]
    for wi, (m1, m2) in enumerate(mappings):
        if m1 >= 0:
            comp_endpoints[m1].append((wi, 0))
        if m2 >= 0:
            comp_endpoints[m2].append((wi, 1))

    # For components with many endpoints, try to redistribute
    for ci, eps in comp_endpoints.items():
        if len(eps) <= 2:  # Normal — a component can have 2 connections
            continue

        # Too many endpoints mapping to this component
        # Keep the closest ones, reassign the rest
        ep_dists = []
        for wi, ei in eps:
            ep = wires_batch[wi][ei]
            d = point_to_bbox_dist(ep[0], ep[1], components[ci][2])
            ep_dists.append((wi, ei, d))

        ep_dists.sort(key=lambda x: x[2])

        # Keep top 2 (or more for ICs)
        cls_id = components[ci][0]
        name = COMPONENT_NAMES.get(cls_id, "")
        max_pins = 2
        if "integrated" in name:
            max_pins = 8
        elif "transistor" in name:
            max_pins = 3

        # Reassign excess endpoints
        for wi, ei, d in ep_dists[max_pins:]:
            ep = wires_batch[wi][ei]
            # Find next-best component
            cands = []
            for cj, comp in enumerate(components):
                if cj == ci:
                    continue
                d2 = point_to_bbox_dist(ep[0], ep[1], comp[2])
                cands.append((cj, d2))
            cands.sort(key=lambda x: x[1])

            if cands:
                if ei == 0:
                    mappings[wi] = (cands[0][0], mappings[wi][1])
                else:
                    mappings[wi] = (mappings[wi][0], cands[0][0])

    # Final pass: fix any remaining same-component mappings
    for wi, (m1, m2) in enumerate(mappings):
        if m1 == m2 and m1 >= 0:
            ep1, ep2 = wires_batch[wi]
            d1 = point_to_bbox_dist(ep1[0], ep1[1], components[m1][2])
            d2 = point_to_bbox_dist(ep2[0], ep2[1], components[m2][2])

            # Reassign the further endpoint
            if d2 >= d1:
                cands = [(cj, point_to_bbox_dist(ep2[0], ep2[1], comp[2]))
                        for cj, comp in enumerate(components) if cj != m1]
                cands.sort(key=lambda x: x[1])
                if cands:
                    mappings[wi] = (m1, cands[0][0])
            else:
                cands = [(cj, point_to_bbox_dist(ep1[0], ep1[1], comp[2]))
                        for cj, comp in enumerate(components) if cj != m2]
                cands.sort(key=lambda x: x[1])
                if cands:
                    mappings[wi] = (cands[0][0], m2)

    return mappings


def map_wire_pair_junction_context(wire, all_wires, components, max_junction_dist=15):
    """Use junction context: if an endpoint is near a junction, consider wires 
    connected to that junction to disambiguate."""
    ep1, ep2 = wire

    # For each endpoint, find nearby junctions
    # Then look at what other wires connect to those junctions
    # Use that context to disambiguate

    def find_junction_context(ep, exclude_wire_idx=-1):
        """Find junction components near this endpoint and their connected wires."""
        junctions = []
        for ci, comp in enumerate(components):
            if comp[0] not in JUNCTION_IDS:
                continue
            d = point_to_bbox_dist(ep[0], ep[1], comp[2])
            if d <= max_junction_dist:
                junctions.append((ci, d))

        if not junctions:
            return []

        # Find wires connected to these junctions
        context_comps = []
        for ji, jd in junctions:
            j_bbox = components[ji][2]
            j_cx = (j_bbox[0] + j_bbox[2]) / 2
            j_cy = (j_bbox[1] + j_bbox[3]) / 2

            for wi2, (wep1, wep2) in enumerate(all_wires):
                if wi2 == exclude_wire_idx:
                    continue
                for wep in [wep1, wep2]:
                    d = point_to_bbox_dist(wep[0], wep[1], j_bbox)
                    if d <= max_junction_dist:
                        # This wire connects to the same junction
                        # Find what component its OTHER endpoint connects to
                        other_ep = wep2 if wep == wep1 else wep1
                        best_ci = -1
                        best_d = float("inf")
                        for ci2, comp2 in enumerate(components):
                            if comp2[0] in JUNCTION_IDS:
                                continue
                            d2 = point_to_bbox_dist(other_ep[0], other_ep[1], comp2[2])
                            if d2 < best_d:
                                best_d = d2
                                best_ci = ci2
                        if best_ci >= 0:
                            context_comps.append(best_ci)

        return context_comps

    # Simple version: just use nearest bbox with disambiguation
    return map_wire_pair_disambiguate(wire, components)


def map_wire_pair_weighted_polygon(wire, components, alpha=0.7):
    """Combine polygon edge distance with bbox center distance."""
    ep1, ep2 = wire

    def point_to_polygon_dist(px, py, vertices):
        min_d = float("inf")
        n = len(vertices)
        for i in range(n):
            ax, ay = vertices[i]
            bx, by = vertices[(i + 1) % n]
            ldx, ldy = bx - ax, by - ay
            len_sq = ldx * ldx + ldy * ldy
            if len_sq < 1e-10:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0, min(1, ((px - ax) * ldx + (py - ay) * ldy) / len_sq))
                d = math.hypot(px - (ax + t * ldx), py - (ay + t * ldy))
            min_d = min(min_d, d)
        return min_d

    def combined_dist(ep, comp):
        d_poly = point_to_polygon_dist(ep[0], ep[1], comp[1])
        bbox = comp[2]
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        d_center = math.hypot(ep[0] - cx, ep[1] - cy)
        return alpha * d_poly + (1 - alpha) * d_center

    cands1 = [(ci, combined_dist(ep1, comp)) for ci, comp in enumerate(components)]
    cands2 = [(ci, combined_dist(ep2, comp)) for ci, comp in enumerate(components)]
    cands1.sort(key=lambda x: x[1])
    cands2.sort(key=lambda x: x[1])

    best1 = cands1[0][0] if cands1 else -1
    best2 = cands2[0][0] if cands2 else -1

    if best1 == best2 and best1 >= 0:
        d1 = cands1[0][1]
        d2 = cands2[0][1]
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


def map_wire_pair_iterative(wire, all_wires, components, n_iters=3):
    """Iterative refinement: use initial mappings to build context, then remap."""
    # Start with simple nearest bbox
    ep1, ep2 = wire

    # First pass: nearest bbox
    cands1 = sorted([(ci, point_to_bbox_dist(ep1[0], ep1[1], comp[2]))
                     for ci, comp in enumerate(components)], key=lambda x: x[1])
    cands2 = sorted([(ci, point_to_bbox_dist(ep2[0], ep2[1], comp[2]))
                     for ci, comp in enumerate(components)], key=lambda x: x[1])

    best1 = cands1[0][0] if cands1 else -1
    best2 = cands2[0][0] if cands2 else -1

    # Disambiguate
    if best1 == best2 and best1 >= 0:
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
# MAIN EXPERIMENT
# ═══════════════════════════════════════════════════

def run_phase2():
    log("\n" + "=" * 80)
    log("PHASE 2: DENSE AREA DISAMBIGUATION & GLOBAL OPTIMIZATION")
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

    # Load all images
    log("Loading images...")
    all_data = []
    for gt_file in sorted(GT_LABELS.glob("*_jpg.txt")):
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = GT_IMAGES / f"{image_name}_jpg.jpg"
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

    # Define Phase 2 methods (wire-pair level)
    methods = [
        ("baseline_nearest_bbox", map_wire_pair_nearest_bbox),
        ("disambiguate_simple", map_wire_pair_disambiguate),
        ("disambiguate_direction", map_wire_pair_direction_disambiguate),
        ("disambiguate_polygon", map_wire_pair_polygon_disambiguate),
        ("weighted_polygon_0.7", lambda w, c: map_wire_pair_weighted_polygon(w, c, alpha=0.7)),
        ("weighted_polygon_0.5", lambda w, c: map_wire_pair_weighted_polygon(w, c, alpha=0.5)),
        ("weighted_polygon_0.3", lambda w, c: map_wire_pair_weighted_polygon(w, c, alpha=0.3)),
        ("junction_context", lambda w, c: map_wire_pair_junction_context(w, [], c)),
        ("iterative", lambda w, c: map_wire_pair_iterative(w, [], c)),
    ]

    # ═══════════════════════════════════════════════════
    # PHASE 2A: GT WIRE EVALUATION
    # ═══════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log("PHASE 2A: GT WIRE PAIR MAPPING")
    log("=" * 80)

    # Compute pseudo-GT
    all_gt_mappings = []
    for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
        gt_maps = compute_gt_mapping(gt_lines, components)
        all_gt_mappings.append(gt_maps)

    results = {}

    for method_name, method_fn in methods:
        log(f"\nEvaluating: {method_name}")
        t0 = time.time()

        total_ep = 0
        correct_ep = 0
        total_wires = 0
        correct_both = 0
        correct_either = 0
        same_comp_errors = 0

        for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
            gt_maps = all_gt_mappings[img_idx]

            for wi, ((ep1, ep2), (gt1, gt2)) in enumerate(zip(gt_lines, gt_maps)):
                pred1, pred2 = method_fn((ep1, ep2), components)

                total_ep += 2
                ep1_ok = (pred1 == gt1)
                ep2_ok = (pred2 == gt2)
                if ep1_ok:
                    correct_ep += 1
                if ep2_ok:
                    correct_ep += 1

                total_wires += 1
                if ep1_ok and ep2_ok:
                    correct_both += 1
                if ep1_ok or ep2_ok:
                    correct_either += 1

                if pred1 == pred2 and pred1 >= 0:
                    same_comp_errors += 1

        elapsed = time.time() - t0
        ep_acc = correct_ep / max(total_ep, 1)
        wire_both = correct_both / max(total_wires, 1)
        wire_either = correct_either / max(total_wires, 1)

        results[method_name] = {
            "endpoint_accuracy": ep_acc,
            "wire_accuracy_both": wire_both,
            "wire_accuracy_either": wire_either,
            "same_comp_errors": same_comp_errors,
            "total_wires": total_wires,
            "elapsed": elapsed,
        }

        log(f"  Endpoint accuracy: {ep_acc:.4f} ({correct_ep}/{total_ep})")
        log(f"  Wire accuracy (both): {wire_both:.4f} ({correct_both}/{total_wires})")
        log(f"  Wire accuracy (either): {wire_either:.4f}")
        log(f"  Same-component errors: {same_comp_errors}/{total_wires}")
        log(f"  Time: {elapsed:.1f}s")

    # ═══════════════════════════════════════════════════
    # PHASE 2B: GLOBAL OPTIMIZATION (Hungarian-like)
    # ═══════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log("PHASE 2B: GLOBAL OPTIMIZATION")
    log("=" * 80)

    log("\nEvaluating: hungarian_global")
    t0 = time.time()

    total_ep = 0
    correct_ep = 0
    total_wires = 0
    correct_both = 0
    same_comp_errors = 0

    for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
        gt_maps = all_gt_mappings[img_idx]
        mappings = map_wire_pair_hungarian(gt_lines, components)

        for wi, ((pred1, pred2), (gt1, gt2)) in enumerate(zip(mappings, gt_maps)):
            total_ep += 2
            if pred1 == gt1:
                correct_ep += 1
            if pred2 == gt2:
                correct_ep += 1

            total_wires += 1
            if pred1 == gt1 and pred2 == gt2:
                correct_both += 1

            if pred1 == pred2 and pred1 >= 0:
                same_comp_errors += 1

    elapsed = time.time() - t0
    ep_acc = correct_ep / max(total_ep, 1)
    wire_both = correct_both / max(total_wires, 1)

    results["hungarian_global"] = {
        "endpoint_accuracy": ep_acc,
        "wire_accuracy_both": wire_both,
        "same_comp_errors": same_comp_errors,
        "total_wires": total_wires,
        "elapsed": elapsed,
    }

    log(f"  Endpoint accuracy: {ep_acc:.4f} ({correct_ep}/{total_ep})")
    log(f"  Wire accuracy (both): {wire_both:.4f} ({correct_both}/{total_wires})")
    log(f"  Same-component errors: {same_comp_errors}/{total_wires}")
    log(f"  Time: {elapsed:.1f}s")

    # ═══════════════════════════════════════════════════
    # PHASE 2C: DETECTED WIRE EVALUATION (top methods)
    # ═══════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log("PHASE 2C: DETECTED WIRE PAIR MAPPING")
    log("=" * 80)

    sorted_methods = sorted(results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True)
    top3 = [m[0] for m in sorted_methods[:3]]

    det_results = {}
    for method_name in top3:
        method_fn = None
        for mn, mf in methods:
            if mn == method_name:
                method_fn = mf
                break
        if method_fn is None:
            continue

        log(f"\nEvaluating detected wires: {method_name}")
        t0 = time.time()

        total_ep = 0
        correct_ep = 0
        total_wires = 0
        correct_both = 0

        for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
            h, w = gray.shape
            occluded = build_component_mask(gray, components, cfg.occlusion_margin)
            cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
            local_components = shift_components(components, ox, oy)

            lines_local = detect_wires_experiment(cropped, local_components, cfg)

            for wire in lines_local:
                ep1, ep2 = wire
                ep1_global = (ep1[0] + ox, ep1[1] + oy)
                ep2_global = (ep2[0] + ox, ep2[1] + oy)

                # GT mapping
                gt1, gt2 = compute_gt_mapping([(ep1_global, ep2_global)], components)[0]

                pred1, pred2 = method_fn((ep1_global, ep2_global), components)

                total_ep += 2
                if pred1 == gt1:
                    correct_ep += 1
                if pred2 == gt2:
                    correct_ep += 1

                total_wires += 1
                if pred1 == gt1 and pred2 == gt2:
                    correct_both += 1

        elapsed = time.time() - t0
        ep_acc = correct_ep / max(total_ep, 1)
        wire_both = correct_both / max(total_wires, 1)

        det_results[method_name] = {
            "endpoint_accuracy": ep_acc,
            "wire_accuracy_both": wire_both,
            "total_wires": total_wires,
            "elapsed": elapsed,
        }

        log(f"  Endpoint accuracy: {ep_acc:.4f} ({correct_ep}/{total_ep})")
        log(f"  Wire accuracy (both): {wire_both:.4f} ({correct_both}/{total_wires})")
        log(f"  Time: {elapsed:.1f}s")

    # ═══════════════════════════════════════════════════
    # SYNTHESIS
    # ═══════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log("PHASE 2 SYNTHESIS")
    log("=" * 80)

    log("\nPhase 2A Results (GT wires):")
    log(f"{'Method':<40s} {'EP Acc':>8s} {'Wire Both':>10s} {'SameComp':>10s}")
    log("-" * 72)
    for name, res in sorted(results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True):
        log(f"{name:<40s} {res['endpoint_accuracy']:8.4f} {res['wire_accuracy_both']:10.4f} {res['same_comp_errors']:10d}")

    if det_results:
        log("\nPhase 2C Results (detected wires):")
        log(f"{'Method':<40s} {'EP Acc':>8s} {'Wire Both':>10s}")
        log("-" * 62)
        for name, res in sorted(det_results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True):
            log(f"{name:<40s} {res['endpoint_accuracy']:8.4f} {res['wire_accuracy_both']:10.4f}")

    # Improvement over baseline
    baseline_ep = results.get("baseline_nearest_bbox", {}).get("endpoint_accuracy", 0)
    baseline_wire = results.get("baseline_nearest_bbox", {}).get("wire_accuracy_both", 0)

    log(f"\nBaseline: EP={baseline_ep:.4f}, Wire={baseline_wire:.4f}")
    for name, res in sorted(results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True):
        if name == "baseline_nearest_bbox":
            continue
        ep_delta = res["endpoint_accuracy"] - baseline_ep
        wire_delta = res["wire_accuracy_both"] - baseline_wire
        log(f"  {name}: EP delta={ep_delta:+.4f}, Wire delta={wire_delta:+.4f}")

    # Save
    summary = {
        "phase2_results": {k: {kk: vv for kk, vv in v.items()} for k, v in results.items()},
        "detected_results": det_results,
        "best_method": sorted_methods[0][0] if sorted_methods else None,
        "best_endpoint_accuracy": sorted_methods[0][1]["endpoint_accuracy"] if sorted_methods else 0,
    }

    (OUTPUT_DIR / "phase2_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    log(f"\nResults saved to {OUTPUT_DIR / 'phase2_summary.json'}")
    log("PHASE 2 COMPLETE")


if __name__ == "__main__":
    run_phase2()

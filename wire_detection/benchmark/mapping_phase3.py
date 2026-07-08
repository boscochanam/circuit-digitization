#!/usr/bin/env python3
"""
MAPPING EXPERIMENT V2 — PHASE 3: Smart disambiguation & ensemble.

Phase 2 showed:
  - Baseline: 91.93% EP, 85.39% wire, 425 same-comp errors
  - Simple disambiguate: 90.22% EP, 85.30% wire, 0 same-comp errors
  - On detected wires: disambiguate 90.57% wire (better than baseline 90.31%)

Problem: Simple disambiguation hurts EP accuracy by 1.7% because it sometimes
reassigns endpoints that SHOULD map to the same component (e.g., two pins on an IC).

Phase 3 solutions:
  1. Type-aware disambiguation (only for 2-terminal components)
  2. Confidence-based disambiguation (only when 2nd candidate is close)
  3. Wire-length-aware (short wires inside components are OK)
  4. Containment check (if endpoint is INSIDE component polygon, don't reassign)
  5. Hybrid: baseline + selective disambiguation
  6. Ensemble voting
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from pathlib import Path

import cv2


from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig,
    build_component_mask,
    crop_to_roi,
    detect_wires_experiment,
    shift_components,
)
from wire_detection.benchmark.connectivity_experiment import COMPONENT_NAMES
from wire_detection.paths import gt_images_dir, gt_labels_dir, hdc_root, output_dir

HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = output_dir() / "mapping_experiment_v2"
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
        label_dir = hdc_root() / split / "labels"
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


def point_to_bbox_dist(px, py, bbox):
    xmin, ymin, xmax, ymax = bbox
    cx = max(xmin, min(px, xmax))
    cy = max(ymin, min(py, ymax))
    return math.hypot(px - cx, py - cy)


def point_in_polygon(px, py, vertices):
    """Check if point is inside polygon using ray casting."""
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


JUNCTION_IDS = {19, 44}
TWO_TERMINAL_TYPES = {
    "resistor", "capacitor-unpolarized", "capacitor-polarized",
    "inductor", "diode", "diode-zener", "diode-light_emitting",
    "diode-thyrector", "fuse", "thermistor", "varistor", "crystal",
    "resistor-adjustable", "capacitor-adjustable", "inductor-ferrite",
    "magnetic", "relay", "switch",
}
MULTI_TERMINAL_TYPES = {
    "integrated_circuit", "integrated_circuit-ne555",
    "integrated_circuit-voltage_regulator", "transistor", "transistor-pnp",
    "operational_amplifier", "optocoupler", "triac", "diac",
}


def is_two_terminal(cls_id):
    name = COMPONENT_NAMES.get(cls_id, "")
    return name in TWO_TERMINAL_TYPES or "resistor" in name or "capacitor" in name or "diode" in name


def is_multi_terminal(cls_id):
    name = COMPONENT_NAMES.get(cls_id, "")
    return name in MULTI_TERMINAL_TYPES or "integrated" in name or "transistor" in name


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


# ═══════════════════════════════════════════════════
# PHASE 3 METHODS
# ═══════════════════════════════════════════════════

def get_candidates(ep, components):
    """Get sorted candidates for an endpoint."""
    cands = []
    for ci, comp in enumerate(components):
        d = point_to_bbox_dist(ep[0], ep[1], comp[2])
        cands.append((ci, d))
    cands.sort(key=lambda x: x[1])
    return cands


def map_baseline(wire, components):
    """Baseline: nearest bbox edge, no disambiguation."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    return (c1[0][0] if c1 else -1, c2[0][0] if c2 else -1)


def map_disambiguate_always(wire, components):
    """Simple disambiguation: always reassign when same component."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    best1 = c1[0][0] if c1 else -1
    best2 = c2[0][0] if c2 else -1

    if best1 == best2 and best1 >= 0:
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

    return best1, best2


def map_disambiguate_two_terminal_only(wire, components):
    """Only disambiguate for 2-terminal components."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    best1 = c1[0][0] if c1 else -1
    best2 = c2[0][0] if c2 else -1

    if best1 == best2 and best1 >= 0:
        # Only disambiguate if it's a 2-terminal component
        cls_id = components[best1][0]
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

    return best1, best2


def map_disambiguate_confidence(wire, components, gap_threshold=20):
    """Only disambiguate when the 2nd candidate is within gap_threshold of 1st."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    best1 = c1[0][0] if c1 else -1
    best2 = c2[0][0] if c2 else -1

    if best1 == best2 and best1 >= 0:
        d1, d2 = c1[0][1], c2[0][1]
        # Reassign the endpoint whose 2nd candidate is closest
        gap1 = c1[1][1] - c1[0][1] if len(c1) > 1 else float("inf")
        gap2 = c2[1][1] - c2[0][1] if len(c2) > 1 else float("inf")

        # Only reassign if there's a reasonable alternative
        if d2 >= d1 and gap2 < gap_threshold:
            for ci, d in c2[1:]:
                if ci != best1:
                    best2 = ci
                    break
        elif d1 > d2 and gap1 < gap_threshold:
            for ci, d in c1[1:]:
                if ci != best2:
                    best1 = ci
                    break

    return best1, best2


def map_disambiguate_containment(wire, components):
    """Don't reassign if endpoint is INSIDE the component polygon."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    best1 = c1[0][0] if c1 else -1
    best2 = c2[0][0] if c2 else -1

    if best1 == best2 and best1 >= 0:
        # Check if either endpoint is inside the component polygon
        comp = components[best1]
        inside1 = point_in_polygon(ep1[0], ep1[1], comp[1])
        inside2 = point_in_polygon(ep2[0], ep2[1], comp[1])

        if inside1 and inside2:
            # Both inside — likely a legitimate same-component connection
            return best1, best2

        # Reassign the one that's NOT inside (or the further one if both outside)
        if inside1 and not inside2:
            # ep1 is inside, reassign ep2
            for ci, d in c2[1:]:
                if ci != best1:
                    best2 = ci
                    break
        elif inside2 and not inside1:
            # ep2 is inside, reassign ep1
            for ci, d in c1[1:]:
                if ci != best2:
                    best1 = ci
                    break
        else:
            # Neither inside — reassign the further one
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

    return best1, best2


def map_disambiguate_smart(wire, components):
    """Combined smart disambiguation: containment + type-aware + confidence."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    best1 = c1[0][0] if c1 else -1
    best2 = c2[0][0] if c2 else -1

    if best1 == best2 and best1 >= 0:
        comp = components[best1]
        cls_id = comp[0]

        # Multi-terminal components: don't disambiguate
        if is_multi_terminal(cls_id):
            return best1, best2

        # Check containment
        inside1 = point_in_polygon(ep1[0], ep1[1], comp[1])
        inside2 = point_in_polygon(ep2[0], ep2[1], comp[1])

        if inside1 and inside2:
            return best1, best2

        # 2-terminal: always disambiguate
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
            # Unknown type: disambiguate with confidence check
            gap2 = c2[1][1] - c2[0][1] if len(c2) > 1 else float("inf")
            gap1 = c1[1][1] - c1[0][1] if len(c1) > 1 else float("inf")

            d1, d2 = c1[0][1], c2[0][1]
            if d2 >= d1 and gap2 < 25:
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


def map_ensemble_vote(wire, components):
    """Ensemble: run 3 methods, majority vote per endpoint."""
    ep1, ep2 = wire

    methods = [map_baseline, map_disambiguate_two_terminal_only, map_disambiguate_containment]
    votes1 = defaultdict(int)
    votes2 = defaultdict(int)

    for method in methods:
        m1, m2 = method(wire, components)
        votes1[m1] += 1
        votes2[m2] += 1

    # Majority vote
    best1 = max(votes1.items(), key=lambda x: x[1])[0] if votes1 else -1
    best2 = max(votes2.items(), key=lambda x: x[1])[0] if votes2 else -1

    # If tie, use baseline
    if best1 == -1:
        c1 = get_candidates(ep1, components)
        best1 = c1[0][0] if c1 else -1
    if best2 == -1:
        c2 = get_candidates(ep2, components)
        best2 = c2[0][0] if c2 else -1

    return best1, best2


def map_selective_disambiguate(wire, components, confidence_threshold=15):
    """Baseline by default, disambiguate only when baseline produces same-component AND confident alternative exists."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    best1 = c1[0][0] if c1 else -1
    best2 = c2[0][0] if c2 else -1

    if best1 != best2 or best1 < 0:
        return best1, best2

    # Same component — check if we should disambiguate
    comp = components[best1]
    cls_id = comp[0]

    # Never disambiguate for multi-terminal
    if is_multi_terminal(cls_id):
        return best1, best2

    # Check containment — if both inside, don't disambiguate
    inside1 = point_in_polygon(ep1[0], ep1[1], comp[1])
    inside2 = point_in_polygon(ep2[0], ep2[1], comp[1])
    if inside1 and inside2:
        return best1, best2

    # For 2-terminal components: always try to disambiguate
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
        return best1, best2

    # For other types: only disambiguate if confident alternative exists
    gap1 = c1[1][1] - c1[0][1] if len(c1) > 1 else float("inf")
    gap2 = c2[1][1] - c2[0][1] if len(c2) > 1 else float("inf")

    if gap2 < confidence_threshold:
        for ci, d in c2[1:]:
            if ci != best1:
                best2 = ci
                break
    elif gap1 < confidence_threshold:
        for ci, d in c1[1:]:
            if ci != best2:
                best1 = ci
                break

    return best1, best2


# ═══════════════════════════════════════════════════
# SWEEP: Find optimal confidence threshold
# ═══════════════════════════════════════════════════

def sweep_confidence_threshold(all_data, all_gt_mappings, thresholds):
    """Sweep confidence threshold for selective disambiguation."""
    results = {}

    for threshold in thresholds:
        total_ep = 0
        correct_ep = 0
        total_wires = 0
        correct_both = 0
        same_comp = 0

        for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
            gt_maps = all_gt_mappings[img_idx]

            for wi, ((ep1, ep2), (gt1, gt2)) in enumerate(zip(gt_lines, gt_maps)):
                pred1, pred2 = map_selective_disambiguate((ep1, ep2), components, confidence_threshold=threshold)

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

        ep_acc = correct_ep / max(total_ep, 1)
        wire_both = correct_both / max(total_wires, 1)
        results[threshold] = {
            "endpoint_accuracy": ep_acc,
            "wire_accuracy_both": wire_both,
            "same_comp": same_comp,
        }

    return results


# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════

def run_phase3():
    log("\n" + "=" * 80)
    log("PHASE 3: SMART DISAMBIGUATION & ENSEMBLE")
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

    methods = [
        ("00_baseline", map_baseline),
        ("01_disambiguate_always", map_disambiguate_always),
        ("02_disambiguate_two_terminal", map_disambiguate_two_terminal_only),
        ("03_disambiguate_containment", map_disambiguate_containment),
        ("04_disambiguate_smart", map_disambiguate_smart),
        ("05_ensemble_vote", map_ensemble_vote),
        ("06_selective_10", lambda w, c: map_selective_disambiguate(w, c, 10)),
        ("07_selective_15", lambda w, c: map_selective_disambiguate(w, c, 15)),
        ("08_selective_20", lambda w, c: map_selective_disambiguate(w, c, 20)),
        ("09_selective_25", lambda w, c: map_selective_disambiguate(w, c, 25)),
        ("10_selective_30", lambda w, c: map_selective_disambiguate(w, c, 30)),
    ]

    # ═══ GT Wire Evaluation ═══
    log("\n" + "=" * 80)
    log("GT WIRE EVALUATION")
    log("=" * 80)

    results = {}

    for method_name, method_fn in methods:
        log(f"\nEvaluating: {method_name}")
        t0 = time.time()

        total_ep = 0
        correct_ep = 0
        total_wires = 0
        correct_both = 0
        correct_either = 0
        same_comp = 0

        for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
            gt_maps = all_gt_mappings[img_idx]

            for wi, ((ep1, ep2), (gt1, gt2)) in enumerate(zip(gt_lines, gt_maps)):
                pred1, pred2 = method_fn((ep1, ep2), components)

                total_ep += 2
                e1 = (pred1 == gt1)
                e2 = (pred2 == gt2)
                if e1:
                    correct_ep += 1
                if e2:
                    correct_ep += 1

                total_wires += 1
                if e1 and e2:
                    correct_both += 1
                if e1 or e2:
                    correct_either += 1
                if pred1 == pred2 and pred1 >= 0:
                    same_comp += 1

        elapsed = time.time() - t0
        ep_acc = correct_ep / max(total_ep, 1)
        wire_both = correct_both / max(total_wires, 1)

        results[method_name] = {
            "endpoint_accuracy": ep_acc,
            "wire_accuracy_both": wire_both,
            "wire_accuracy_either": correct_either / max(total_wires, 1),
            "same_comp": same_comp,
            "total_wires": total_wires,
            "elapsed": elapsed,
        }

        log(f"  EP: {ep_acc:.4f} ({correct_ep}/{total_ep})")
        log(f"  Wire(both): {wire_both:.4f} ({correct_both}/{total_wires})")
        log(f"  Same-comp: {same_comp}")
        log(f"  Time: {elapsed:.1f}s")

    # ═══ Confidence Threshold Sweep ═══
    log("\n" + "=" * 80)
    log("CONFIDENCE THRESHOLD SWEEP")
    log("=" * 80)

    thresholds = [5, 8, 10, 12, 15, 18, 20, 25, 30, 40, 50]
    sweep_results = sweep_confidence_threshold(all_data, all_gt_mappings, thresholds)

    log(f"\n{'Threshold':>10s} {'EP Acc':>10s} {'Wire Both':>10s} {'SameComp':>10s}")
    log("-" * 45)
    for t in thresholds:
        r = sweep_results[t]
        log(f"{t:10d} {r['endpoint_accuracy']:10.4f} {r['wire_accuracy_both']:10.4f} {r['same_comp']:10d}")

    # ═══ Detected Wire Evaluation (top 3) ═══
    log("\n" + "=" * 80)
    log("DETECTED WIRE EVALUATION (top 3)")
    log("=" * 80)

    sorted_methods = sorted(results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True)
    top3_names = [m[0] for m in sorted_methods[:3]]

    det_results = {}
    for method_name in top3_names:
        method_fn = None
        for mn, mf in methods:
            if mn == method_name:
                method_fn = mf
                break
        if method_fn is None:
            continue

        log(f"\nDetected wires: {method_name}")
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
                ep1g = (ep1[0] + ox, ep1[1] + oy)
                ep2g = (ep2[0] + ox, ep2[1] + oy)

                gt1, gt2 = compute_gt_mapping([(ep1g, ep2g)], components)[0]
                pred1, pred2 = method_fn((ep1g, ep2g), components)

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
        }

        log(f"  EP: {ep_acc:.4f}, Wire: {wire_both:.4f} ({total_wires} wires)")

    # ═══ Synthesis ═══
    log("\n" + "=" * 80)
    log("PHASE 3 SYNTHESIS")
    log("=" * 80)

    log("\nGT Wire Results:")
    log(f"{'Method':<35s} {'EP Acc':>8s} {'Wire':>8s} {'SameCmp':>8s}")
    log("-" * 62)
    for name, res in sorted(results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True):
        log(f"{name:<35s} {res['endpoint_accuracy']:8.4f} {res['wire_accuracy_both']:8.4f} {res['same_comp']:8d}")

    if det_results:
        log("\nDetected Wire Results:")
        log(f"{'Method':<35s} {'EP Acc':>8s} {'Wire':>8s}")
        log("-" * 55)
        for name, res in sorted(det_results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True):
            log(f"{name:<35s} {res['endpoint_accuracy']:8.4f} {res['wire_accuracy_both']:8.4f}")

    # Save
    summary = {
        "gt_results": {k: v for k, v in results.items()},
        "det_results": det_results,
        "sweep": {str(k): v for k, v in sweep_results.items()},
        "best_method": sorted_methods[0][0],
        "best_ep": sorted_methods[0][1]["endpoint_accuracy"],
    }

    (OUTPUT_DIR / "phase3_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    log(f"\nSaved to {OUTPUT_DIR / 'phase3_summary.json'}")
    log("PHASE 3 COMPLETE")


if __name__ == "__main__":
    run_phase3()

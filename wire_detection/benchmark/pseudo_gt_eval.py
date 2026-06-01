#!/usr/bin/env python3
"""
PSEUDO-GT CONNECTIVITY EVALUATION

Uses GT wire endpoints + nearest_edge to establish "ground truth" component
connections, then checks if detected wires connect to the same components.

Metrics:
  - gt_connect_rate    : % of GT wire endpoints that reach a component (sanity check)
  - agreement_rate     : % of matched wires where detected connects to same components as GT
  - mismatch_rate      : % of matched wires connecting to DIFFERENT components
  - detected_orphan    : % of detected wire endpoints that don't connect (but GT does)
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

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
from wire_detection.benchmark.connectivity_experiment import (
    connect_nearest_edge,
    load_components,
    find_hdc_label,
    METHODS,
    _line_intersects_rect,
    _segments_intersect,
    _on_segment,
)

# ── Paths ──
GT_LABELS = Path("/home/claw/workspace/ground_truth/labels_few_annot/labels/train/manually_verified_no_background_data/images")
GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/connectivity_experiment")


def connect_extend_along_wire(endpoint, wire_dir, components, max_dist=120):
    """Extend from endpoint along wire direction until hitting a component bbox.
    
    Unlike ray_cast which steps along the ray, this uses line-rect intersection
    for exact hit detection. The wire_dir is the direction FROM the other endpoint
    TOWARD this endpoint (i.e., the direction the wire is "arriving" from).
    """
    ex, ey = endpoint
    dx, dy = wire_dir
    norm = math.hypot(dx, dy)
    if norm < 1e-6:
        return []
    dx, dy = dx / norm, dy / norm
    
    # Extend in the wire's arrival direction (opposite = where it came from)
    # Also extend slightly in the forward direction (wire might poke into bbox)
    best = None
    for direction in [1, -1]:  # forward and backward along wire axis
        ray_dx, ray_dy = dx * direction, dy * direction
        end_x = ex + ray_dx * max_dist
        end_y = ey + ray_dy * max_dist
        
        for ci, comp in enumerate(components):
            xmin, ymin, xmax, ymax = comp[2]  # bbox
            if _line_intersects_rect(ex, ey, end_x, end_y, xmin, ymin, xmax, ymax):
                # Compute distance to bbox edge
                dist = _dist_to_bbox_edge(ex, ey, ray_dx, ray_dy, xmin, ymin, xmax, ymax)
                if dist is not None and dist <= max_dist:
                    if best is None or dist < best[1]:
                        best = (ci, dist)
    
    return [best] if best else []


def _dist_to_bbox_edge(ox, oy, dx, dy, xmin, ymin, xmax, ymax):
    """Distance from origin along ray (dx,dy) to first intersection with bbox."""
    candidates = []
    
    # Vertical edges (x = xmin, x = xmax)
    if abs(dx) > 1e-9:
        for x_edge in [xmin, xmax]:
            t = (x_edge - ox) / dx
            if t > 0:
                y_hit = oy + t * dy
                if ymin <= y_hit <= ymax:
                    candidates.append(t)
    
    # Horizontal edges (y = ymin, y = ymax)
    if abs(dy) > 1e-9:
        for y_edge in [ymin, ymax]:
            t = (y_edge - oy) / dy
            if t > 0:
                x_hit = ox + t * dx
                if xmin <= x_hit <= xmax:
                    candidates.append(t)
    
    return min(candidates) if candidates else None


def get_endpoint_components_extend(endpoint, other_endpoint, components, max_dist=120):
    """Get components using direction-aware extension."""
    wire_dir = (endpoint[0] - other_endpoint[0], endpoint[1] - other_endpoint[1])
    hits = connect_extend_along_wire(endpoint, wire_dir, components, max_dist=max_dist)
    return tuple(sorted([ci for ci, dist in hits]))


def match_gt_to_detected(gt_lines, det_lines, max_dist=30):
    """Match detected lines to GT lines by endpoint proximity.
    
    A detected line matches a GT line if both endpoints are within max_dist
    of the GT endpoints (in either order).
    
    Returns list of (gt_idx, det_idx) pairs.
    """
    matches = []
    used_det = set()
    
    for gi, (gp1, gp2) in enumerate(gt_lines):
        best_di = None
        best_dist = float("inf")
        
        for di, (dp1, dp2) in enumerate(det_lines):
            if di in used_det:
                continue
            # Try both orientations
            d1 = math.hypot(gp1[0]-dp1[0], gp1[1]-dp1[1]) + math.hypot(gp2[0]-dp2[0], gp2[1]-dp2[1])
            d2 = math.hypot(gp1[0]-dp2[0], gp1[1]-dp2[1]) + math.hypot(gp2[0]-dp1[0], gp2[1]-dp1[1])
            d = min(d1, d2)
            if d < best_dist and d < max_dist * 2:
                best_dist = d
                best_di = di
        
        if best_di is not None:
            matches.append((gi, best_di))
            used_det.add(best_di)
    
    return matches


def get_endpoint_components(endpoint, components, max_dist=50):
    """Get sorted list of (comp_idx, dist) for components near an endpoint."""
    hits = connect_nearest_edge(endpoint, components, max_dist=max_dist)
    return tuple(sorted([ci for ci, dist in hits]))


def is_endpoint_ambiguous(endpoint, components, max_dist=50):
    """Check if endpoint connection is ambiguous (multiple components equally close).
    Returns (is_ambiguous, nearest_comp_idx, second_nearest_dist).
    """
    import math
    ex, ey = endpoint
    dists = []
    for ci, comp in enumerate(components):
        xmin, ymin, xmax, ymax = comp[2]
        cx = max(xmin, min(ex, xmax))
        cy = max(ymin, min(ey, ymax))
        d = math.hypot(ex - cx, ey - cy)
        if d <= max_dist:
            dists.append((d, ci))
    dists.sort()
    if len(dists) == 0:
        return True, None, 0  # no connection = ambiguous
    if len(dists) == 1:
        return False, dists[0][1], float("inf")  # only one = unambiguous
    # Ambiguous if 2nd nearest is within 2x the nearest distance
    ratio = dists[1][0] / max(dists[0][0], 0.1)
    return ratio < 2.0, dists[0][1], dists[1][0]


def run_pseudo_gt_eval(
    all_data,
    max_match_dist=30,
    max_connect_dist=50,
):
    """Run pseudo-GT connectivity evaluation."""
    
    total_gt_endpoints = 0
    total_gt_connected = 0
    total_matched_wires = 0
    total_agreement = 0
    total_mismatch = 0
    total_det_orphan_gt_connected = 0
    total_agreement_ext = 0
    total_mismatch_ext = 0
    
    # Per-component-class stats
    class_agree = defaultdict(int)
    class_total = defaultdict(int)
    
    image_results = []
    
    # Track ambiguity
    total_unambiguous = 0
    total_ambiguous = 0
    agree_unambiguous = 0
    agree_ambiguous = 0
    
    t0 = time.time()
    
    for image_name, gray, components, gt_lines in all_data:
        h, w = gray.shape
        
        # ── GT connectivity (pseudo ground truth) ──
        gt_connections = []
        for gp1, gp2 in gt_lines:
            ep1_comps = get_endpoint_components(gp1, components, max_connect_dist)
            ep2_comps = get_endpoint_components(gp2, components, max_connect_dist)
            gt_connections.append((ep1_comps, ep2_comps))
        
        # ── GT connectivity via extension (for comparison) ──
        gt_connections_ext = []
        for gp1, gp2 in gt_lines:
            ep1_comps = get_endpoint_components_extend(gp1, gp2, components, 120)
            ep2_comps = get_endpoint_components_extend(gp2, gp1, components, 120)
            gt_connections_ext.append((ep1_comps, ep2_comps))
            
            total_gt_endpoints += 2
            if ep1_comps: total_gt_connected += 1
            if ep2_comps: total_gt_connected += 1
        
        # ── Detected wire connectivity ──
        cfg = ExperimentConfig(
            name="best_v4", sauvola_k=0.285, sauvola_window=67,
            close_kernel=3, ccl_min_area=28, endpoint_mode="pca",
            dedup_mode="overlap", dedup_angle=10, dedup_dist=18,
            anchor_filter_enabled=True, anchor_endpoint_dist=12.0,
            anchor_link_dist=8.0,
        )
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_comps = shift_components(components, ox, oy)
        lines_local = detect_wires_experiment(cropped, local_comps, cfg)
        lines_global = [((x1+ox, y1+oy), (x2+ox, y2+oy)) for (x1,y1),(x2,y2) in lines_local]
        
        det_connections = []
        for dp1, dp2 in lines_global:
            ep1_comps = get_endpoint_components(dp1, components, max_connect_dist)
            ep2_comps = get_endpoint_components(dp2, components, max_connect_dist)
            det_connections.append((ep1_comps, ep2_comps))
        
        det_connections_ext = []
        for dp1, dp2 in lines_global:
            ep1_comps = get_endpoint_components_extend(dp1, dp2, components, 120)
            ep2_comps = get_endpoint_components_extend(dp2, dp1, components, 120)
            det_connections_ext.append((ep1_comps, ep2_comps))
        
        # ── Match and compare ──
        matches = match_gt_to_detected(gt_lines, lines_global, max_match_dist)
        
        img_agree = 0
        img_mismatch = 0
        img_det_orphan = 0
        
        for gi, di in matches:
            gt_c1, gt_c2 = gt_connections[gi]
            det_c1, det_c2 = det_connections[di]
            gt_c1e, gt_c2e = gt_connections_ext[gi]
            det_c1e, det_c2e = det_connections_ext[di]
            
            total_matched_wires += 1
            
            # Check agreement: do detected endpoints hit the same components as GT?
            ep1_agree = (gt_c1 == det_c1) or (not gt_c1 and not det_c1)
            ep2_agree = (gt_c2 == det_c2) or (not gt_c2 and not det_c2)
            
            # Extension-based agreement
            ep1_agree_ext = (gt_c1e == det_c1e) or (not gt_c1e and not det_c1e)
            ep2_agree_ext = (gt_c2e == det_c2e) or (not gt_c2e and not det_c2e)
            
            # Nearest-edge agreement
            if ep1_agree and ep2_agree:
                total_agreement += 1
                img_agree += 1
            else:
                total_mismatch += 1
                img_mismatch += 1
            
            # Extension agreement
            if ep1_agree_ext and ep2_agree_ext:
                total_agreement_ext += 1
            else:
                total_mismatch_ext += 1
            
            # Ambiguity analysis
            gp1, gp2 = gt_lines[gi]
            amb1, _, _ = is_endpoint_ambiguous(gp1, components, max_connect_dist)
            amb2, _, _ = is_endpoint_ambiguous(gp2, components, max_connect_dist)
            is_ambiguous = amb1 or amb2
            
            if is_ambiguous:
                total_ambiguous += 1
                if ep1_agree and ep2_agree:
                    agree_ambiguous += 1
            else:
                total_unambiguous += 1
                if ep1_agree and ep2_agree:
                    agree_unambiguous += 1
                
                # Classify: is detected connecting to wrong component, or orphan?
                for gt_comp, det_comp in [(gt_c1, det_c1), (gt_c2, det_c2)]:
                    if gt_comp and not det_comp:
                        total_det_orphan_gt_connected += 1
                        img_det_orphan += 1
            
            # Track per-component-class stats
            for comp_set in [gt_c1, gt_c2]:
                for ci in comp_set:
                    cls_id = components[ci][0]
                    class_total[cls_id] += 1
                    if (gt_c1 == det_c1 and ep1_agree) or (gt_c2 == det_c2 and ep2_agree):
                        class_agree[cls_id] += 1
        
        image_results.append({
            "image": image_name,
            "gt_wires": len(gt_lines),
            "det_wires": len(lines_global),
            "matched": len(matches),
            "agree": img_agree,
            "mismatch": img_mismatch,
            "det_orphan": img_det_orphan,
        })
        
        if len(image_results) % 25 == 0:
            print(f"  processed {len(image_results)} images...")
    
    elapsed = time.time() - t0
    
    # ── Aggregate ──
    summary = {
        "images": len(all_data),
        "gt_wires": sum(r["gt_wires"] for r in image_results),
        "det_wires": sum(r["det_wires"] for r in image_results),
        "matched_wires": total_matched_wires,
        "match_rate": round(total_matched_wires / max(sum(r["gt_wires"] for r in image_results), 1), 4),
        "gt_connect_rate": round(total_gt_connected / max(total_gt_endpoints, 1), 4),
        "agreement_rate": round(total_agreement / max(total_matched_wires, 1), 4),
        "mismatch_rate": round(total_mismatch / max(total_matched_wires, 1), 4),
        "det_orphan_gt_connected_rate": round(total_det_orphan_gt_connected / max(total_matched_wires * 2, 1), 4),
        "unambiguous_wires": total_unambiguous,
        "ambiguous_wires": total_ambiguous,
        "unambiguous_rate": round(total_unambiguous / max(total_matched_wires, 1), 4),
        "agree_unambiguous": round(agree_unambiguous / max(total_unambiguous, 1), 4),
        "agree_ambiguous": round(agree_ambiguous / max(total_ambiguous, 1), 4),
        "elapsed_s": round(elapsed, 1),
        "max_match_dist": max_match_dist,
        "max_connect_dist": max_connect_dist,
        "extension_agreement_rate": round(total_agreement_ext / max(total_matched_wires, 1), 4),
        "extension_mismatch_rate": round(total_mismatch_ext / max(total_matched_wires, 1), 4),
    }
    
    # Per-component-class breakdown
    class_breakdown = {}
    for cls_id in sorted(class_total.keys()):
        from wire_detection.benchmark.connectivity_experiment import COMPONENT_NAMES
        name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
        class_breakdown[name] = {
            "total": class_total[cls_id],
            "agree": class_agree.get(cls_id, 0),
            "rate": round(class_agree.get(cls_id, 0) / max(class_total[cls_id], 1), 4),
        }
    
    return {
        "summary": summary,
        "class_breakdown": class_breakdown,
        "worst_images": sorted(image_results, key=lambda r: r["mismatch"], reverse=True)[:10],
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("PSEUDO-GT CONNECTIVITY EVALUATION")
    print("=" * 60)
    
    # Preload all data
    from wire_detection.benchmark.connectivity_experiment import preload_all_images
    all_data = preload_all_images()
    
    print(f"\nRunning pseudo-GT evaluation...")
    result = run_pseudo_gt_eval(all_data)
    summary = result["summary"]
    
    print(f"\n{'=' * 60}")
    print(f"RESULTS")
    print(f"{'=' * 60}")
    print(f"  GT wires:           {summary['gt_wires']}")
    print(f"  Detected wires:     {summary['det_wires']}")
    print(f"  Matched pairs:      {summary['matched_wires']} ({summary['match_rate']:.1%} of GT)")
    print(f"")
    print(f"  GT connect rate:    {summary['gt_connect_rate']:.1%} (sanity: GT endpoints near components)")
    print(f"  Agreement (edge):   {summary['agreement_rate']:.1%} (nearest_edge: same component as GT)")
    print(f"  Mismatch (edge):    {summary['mismatch_rate']:.1%}")
    print(f"  Agreement (ext):    {summary['extension_agreement_rate']:.1%} (extend_along_wire: same component as GT)")
    print(f"  Mismatch (ext):     {summary['extension_mismatch_rate']:.1%}")
    print(f"  Det orphan (GT ok): {summary['det_orphan_gt_connected_rate']:.1%} (GT connects, detected doesn't)")
    print(f"")
    print(f"  Unambiguous wires:  {summary['unambiguous_wires']} ({summary['unambiguous_rate']:.1%} of matched)")
    print(f"  Ambiguous wires:    {summary['ambiguous_wires']}")
    print(f"  Agree (unambig):    {summary['agree_unambiguous']:.1%} (only clear pseudo-GT)")
    print(f"  Agree (ambig):      {summary['agree_ambiguous']:.1%} (ambiguous pseudo-GT)")
    print(f"  Time: {summary['elapsed_s']:.1f}s")
    
    # Per-component breakdown
    print(f"\n{'─' * 50}")
    print(f"Per-component-class agreement (top 15):")
    print(f"{'─' * 50}")
    sorted_classes = sorted(result["class_breakdown"].items(), key=lambda x: x[1]["total"], reverse=True)
    for name, stats in sorted_classes[:15]:
        print(f"  {name:<35} {stats['agree']:>4}/{stats['total']:>4}  ({stats['rate']:.1%})")
    
    # Worst images
    print(f"\n{'─' * 50}")
    print(f"Worst images (most mismatches):")
    print(f"{'─' * 50}")
    for r in result["worst_images"][:5]:
        print(f"  {r['image']:<30} matched={r['matched']} agree={r['agree']} mismatch={r['mismatch']} orphan={r['det_orphan']}")
    
    # Save
    out_path = OUTPUT_DIR / "pseudo_gt_results.json"
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "class_breakdown": result["class_breakdown"], "worst_images": result["worst_images"]}, f, indent=2)
    print(f"\n✓ Results saved to {out_path}")


if __name__ == "__main__":
    main()

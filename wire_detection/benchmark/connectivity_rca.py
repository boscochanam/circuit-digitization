#!/usr/bin/env python3
"""
ROOT CAUSE ANALYSIS — Why does the connectivity filter remove TPs?

Classifies every wire removed by the filter into failure categories:
  1. junction_nearby  — endpoint near a junction (point component, small bbox)
  2. terminal_nearby  — endpoint near a terminal symbol
  3. bbox_mismatch    — wire enters component bbox but endpoint is just outside
  4. sparse_area      — no components within 2x threshold (truly isolated wire)
  5. cluster_capped   — removed by per-component cap (too many wires on one comp)
  6. small_bbox       — nearest component has tiny bbox (junction/terminal-like)
  7. long_wire        — wire is long enough that endpoints naturally distant
  8. distant_component — component exists but far away
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
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
    COMPONENT_NAMES,
)

# ── Paths ──
GT_LABELS = Path(
    "/home/claw/workspace/ground_truth/labels_few_annot/labels/"
    "train/manually_verified_no_background_data/images"
)
GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
HDC_BASE = Path("/home/claw/circuit-digitization/roboflow_test2")
HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/connectivity_rca")

# Junction-like and terminal-like class IDs
JUNCTION_CLASSES = {19}   # junction
TERMINAL_CLASSES = {44}   # terminal
POINT_LIKE = JUNCTION_CLASSES | TERMINAL_CLASSES


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


def wire_length(ep1: tuple[int, int], ep2: tuple[int, int]) -> float:
    return math.hypot(ep2[0] - ep1[0], ep2[1] - ep1[1])


def point_to_bbox_dist(px: int, py: int, bbox: tuple[int, int, int, int]) -> float:
    """Distance from point to nearest point on bbox edge (0 if inside)."""
    xmin, ymin, xmax, ymax = bbox
    cx = max(xmin, min(px, xmax))
    cy = max(ymin, min(py, ymax))
    return math.hypot(px - cx, py - cy)


def classify_endpoint_reason(
    endpoint: tuple[int, int],
    components: list,
    threshold: float = 50.0,
    expanded_threshold: float = 100.0,
) -> dict:
    """Classify why an endpoint does/doesn't connect to a component."""
    ex, ey = endpoint

    # Find all components within expanded threshold
    nearby = []
    for ci, comp in enumerate(components):
        cls_id, vertices, bbox = comp
        d = point_to_bbox_dist(ex, ey, bbox)
        if d <= expanded_threshold:
            nearby.append((ci, cls_id, d, bbox))

    nearby.sort(key=lambda x: x[2])

    result = {
        "endpoint": endpoint,
        "nearest_dist": nearby[0][2] if nearby else None,
        "nearest_cls": nearby[0][1] if nearby else None,
        "nearest_name": COMPONENT_NAMES.get(nearby[0][1], "?") if nearby else None,
        "n_within_expanded": len(nearby),
        "category": None,
    }

    if not nearby:
        result["category"] = "sparse_area"
        return result

    nearest_ci, nearest_cls, nearest_dist, nearest_bbox = nearby[0]

    # Check if junction/terminal is nearby (they have tiny bboxes)
    junction_nearby = any(cls in JUNCTION_CLASSES for _, cls, _, _ in nearby[:3])
    terminal_nearby = any(cls in TERMINAL_CLASSES for _, cls, _, _ in nearby[:3])

    # Check bbox size (point-like components have tiny bboxes)
    bx1, by1, bx2, by2 = nearest_bbox
    bbox_area = (bx2 - bx1) * (by2 - by1)
    bbox_diag = math.hypot(bx2 - bx1, by2 - by1)

    if nearest_dist <= threshold:
        # This endpoint DOES connect (shouldn't be in removed set)
        result["category"] = "connected"
    elif junction_nearby and nearest_dist <= expanded_threshold:
        result["category"] = "junction_nearby"
    elif terminal_nearby and nearest_dist <= expanded_threshold:
        result["category"] = "terminal_nearby"
    elif bbox_area < 400:  # < 20x20 pixels
        result["category"] = "small_bbox"
    elif nearest_dist <= threshold * 1.3:  # just barely outside
        result["category"] = "bbox_mismatch"
    elif len(nearby) >= 3:
        result["category"] = "cluster_area"  # dense, but endpoint between components
    else:
        result["category"] = "distant_component"

    return result


@dataclass
class WireRCA:
    """RCA for a single wire that was removed by the filter."""
    image: str
    wire_ep1: tuple[int, int]
    wire_ep2: tuple[int, int]
    is_tp: bool
    is_fp: bool
    wire_len: float
    # Why was it removed?
    removal_reason: str   # "orphan" or "capped"
    # Endpoint classification
    ep1_info: dict = field(default_factory=dict)
    ep2_info: dict = field(default_factory=dict)
    # Combined category
    category: str = "unclear"


def categorize_wire(wrc: WireRCA) -> str:
    """Assign a single category to a removed wire."""
    cats = [wrc.ep1_info.get("category"), wrc.ep2_info.get("category")]

    # Junction nearby on either endpoint
    if "junction_nearby" in cats:
        return "junction_nearby"
    if "terminal_nearby" in cats:
        return "terminal_nearby"

    # Small bbox on either endpoint
    if "small_bbox" in cats:
        return "small_bbox"

    # Just barely outside threshold
    if "bbox_mismatch" in cats:
        return "bbox_mismatch"

    # Dense area, between components
    if "cluster_area" in cats:
        return "cluster_area"

    # Truly sparse
    if "sparse_area" in cats:
        return "sparse_area"

    # Distant but some component exists
    if "distant_component" in cats:
        return "distant_component"

    return "unclear"


def classify_detected_wires(
    lines_global: list[tuple[tuple[int, int], tuple[int, int]]],
    gt_lines: list[tuple[tuple[int, int], tuple[int, int]]],
    match_dist: float = 20.0,
) -> tuple[set[int], set[int], set[int]]:
    """Classify detected wires as TP, FP, or redundant. Returns (tp_indices, fp_indices, red_indices)."""
    matched_gt = [False] * len(gt_lines)
    tp_set: set[int] = set()
    fp_set: set[int] = set()
    red_set: set[int] = set()

    for di, det in enumerate(lines_global):
        best_dist = float("inf")
        best_gi = -1
        for gi, gt in enumerate(gt_lines):
            dist = (
                ref._point_to_segment_dist(det[0], gt[0], gt[1]) +
                ref._point_to_segment_dist(det[1], gt[0], gt[1])
            ) / 2
            if dist < best_dist:
                best_dist = dist
                best_gi = gi

        if best_dist <= match_dist:
            if matched_gt[best_gi]:
                red_set.add(di)
            else:
                tp_set.add(di)
                matched_gt[best_gi] = True
        else:
            fp_set.add(di)

    return tp_set, fp_set, red_set


def run_rca(
    max_dist: float = 50.0,
    max_per_component: int = 2,
) -> list[WireRCA]:
    """Run RCA on all images, returning per-wire analysis."""
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

    all_rca: list[WireRCA] = []

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

        # Detect wires
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_components = shift_components(components, ox, oy)

        lines_local = detect_wires_experiment(cropped, local_components, cfg)
        lines_global = [
            ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
            for (x1, y1), (x2, y2) in lines_local
        ]

        # Classify detected wires as TP/FP
        tp_set, fp_set, red_set = classify_detected_wires(lines_global, gt_lines)

        # Connect all wires to components and find orphans
        for wi, (ep1, ep2) in enumerate(lines_global):
            # Find nearest component for each endpoint
            ep1_info = classify_endpoint_reason(ep1, local_components, max_dist)
            ep2_info = classify_endpoint_reason(ep2, local_components, max_dist)

            is_tp = wi in tp_set
            is_fp = wi in fp_set or wi in red_set

            # Check if orphan (neither endpoint connects within threshold)
            ep1_fail = (ep1_info.get("nearest_dist") is not None and ep1_info["nearest_dist"] > max_dist) or ep1_info.get("nearest_dist") is None
            ep2_fail = (ep2_info.get("nearest_dist") is not None and ep2_info["nearest_dist"] > max_dist) or ep2_info.get("nearest_dist") is None

            if ep1_fail and ep2_fail:
                wrc = WireRCA(
                    image=image_name,
                    wire_ep1=ep1,
                    wire_ep2=ep2,
                    is_tp=is_tp,
                    is_fp=is_fp,
                    wire_len=wire_length(ep1, ep2),
                    removal_reason="orphan",
                    ep1_info=ep1_info,
                    ep2_info=ep2_info,
                )
                wrc.category = categorize_wire(wrc)
                all_rca.append(wrc)

    return all_rca


def main():
    print("Running RCA on connectivity filter (max_dist=50, expanded=100)...")
    t0 = time.time()
    all_rca = run_rca(max_dist=50.0)
    elapsed = time.time() - t0
    print(f"Analyzed {len(all_rca)} removed wires in {elapsed:.1f}s\n")

    # ── Aggregate by category ──
    cat_data: dict[str, dict] = {}
    for wrc in all_rca:
        cat = wrc.category
        if cat not in cat_data:
            cat_data[cat] = {"count": 0, "tp": 0, "fp": 0, "dists": [], "lens": []}
        cat_data[cat]["count"] += 1
        if wrc.is_tp:
            cat_data[cat]["tp"] += 1
        if wrc.is_fp:
            cat_data[cat]["fp"] += 1
        # Nearest distance (from either endpoint)
        dists = []
        if wrc.ep1_info.get("nearest_dist") is not None:
            dists.append(wrc.ep1_info["nearest_dist"])
        if wrc.ep2_info.get("nearest_dist") is not None:
            dists.append(wrc.ep2_info["nearest_dist"])
        if dists:
            cat_data[cat]["dists"].append(min(dists))
        cat_data[cat]["lens"].append(wrc.wire_len)

    # Print table
    print("=" * 100)
    print("ROOT CAUSE ANALYSIS — Why are wires removed?")
    print("=" * 100)
    print(f"{'Category':<22s} {'Count':>6s} {'TP':>6s} {'FP':>6s} {'TP%':>6s} "
          f"{'AvgDist':>8s} {'AvgLen':>8s} {'Pgain':>6s}")
    print("-" * 100)

    total_tp = sum(v["tp"] for v in cat_data.values())
    total_fp = sum(v["fp"] for v in cat_data.values())

    for cat in sorted(cat_data, key=lambda c: cat_data[c]["count"], reverse=True):
        v = cat_data[cat]
        avg_dist = np.mean(v["dists"]) if v["dists"] else 0
        avg_len = np.mean(v["lens"]) if v["lens"] else 0
        tp_pct = v["tp"] / max(v["count"], 1) * 100
        p_gain = v["fp"] / max(v["count"], 1) * 100
        print(f"{cat:<22s} {v['count']:6d} {v['tp']:6d} {v['fp']:6d} {tp_pct:5.1f}% "
              f"{avg_dist:8.1f} {avg_len:8.1f} {p_gain:5.1f}%")

    print("-" * 100)
    print(f"{'TOTAL':<22s} {len(all_rca):6d} {total_tp:6d} {total_fp:6d} "
          f"{total_tp/max(len(all_rca),1)*100:5.1f}%")
    print()

    # ── Key insight: which categories are SAFE to remove (high FP, low TP)? ──
    print("CATEGORY VERDICT:")
    print("-" * 80)
    for cat in sorted(cat_data, key=lambda c: cat_data[c]["fp"], reverse=True):
        v = cat_data[cat]
        if v["count"] < 5:
            continue
        tp_rate = v["tp"] / max(v["count"], 1)
        fp_rate = v["fp"] / max(v["count"], 1)
        if fp_rate > 0.5:
            verdict = "SAFE TO REMOVE — majority FP"
        elif tp_rate > 0.8:
            verdict = "DANGEROUS — mostly TP, don't remove"
        elif tp_rate > 0.5:
            verdict = "RISKY — more TPs than FPs"
        else:
            verdict = "MIXED — evaluate tradeoff"
        print(f"  {cat:<22s}: {verdict} (TP={v['tp']}, FP={v['fp']})")

    # ── Per-image breakdown: which images lose the most TPs? ──
    print("\nIMAGES LOSING MOST TPs:")
    print("-" * 80)
    img_tp_loss: dict[str, int] = defaultdict(int)
    img_fp_loss: dict[str, int] = defaultdict(int)
    img_cats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for wrc in all_rca:
        if wrc.is_tp:
            img_tp_loss[wrc.image] += 1
        if wrc.is_fp:
            img_fp_loss[wrc.image] += 1
        img_cats[wrc.image][wrc.category] += 1

    worst_imgs = sorted(img_tp_loss.items(), key=lambda x: x[1], reverse=True)[:15]
    print(f"  {'Image':<25s} {'TP_lost':>8s} {'FP_lost':>8s} {'Net':>6s}  Top categories")
    for img, tp_lost in worst_imgs:
        fp_lost = img_fp_loss[img]
        cats_str = ", ".join(f"{c}:{n}" for c, n in
                            sorted(img_cats[img].items(), key=lambda x: x[1], reverse=True)[:3])
        print(f"  {img:<25s} {tp_lost:8d} {fp_lost:8d} {tp_lost - fp_lost:+5d}  {cats_str}")

    # ── Nearest component analysis: what component types are nearby? ──
    print("\nNEAREST COMPONENT TYPE (for removed wires):")
    print("-" * 80)
    comp_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "tp": 0, "fp": 0, "dists": []})
    for wrc in all_rca:
        for ep_info in [wrc.ep1_info, wrc.ep2_info]:
            if ep_info.get("nearest_name"):
                name = ep_info["nearest_name"]
                comp_stats[name]["count"] += 1
                if wrc.is_tp:
                    comp_stats[name]["tp"] += 1
                if wrc.is_fp:
                    comp_stats[name]["fp"] += 1
                if ep_info.get("nearest_dist") is not None:
                    comp_stats[name]["dists"].append(ep_info["nearest_dist"])

    print(f"  {'CompType':<25s} {'Count':>6s} {'TP':>6s} {'FP':>6s} {'AvgDist':>8s}")
    for name in sorted(comp_stats, key=lambda n: comp_stats[n]["count"], reverse=True)[:15]:
        v = comp_stats[name]
        avg_d = np.mean(v["dists"]) if v["dists"] else 0
        print(f"  {name:<25s} {v['count']:6d} {v['tp']:6d} {v['fp']:6d} {avg_d:8.1f}")

    # ── Wire length analysis ──
    print("\nWIRE LENGTH DISTRIBUTION (removed wires):")
    print("-" * 80)
    len_bins = [(0, 20, "short"), (20, 50, "medium"), (50, 100, "long"), (100, 99999, "very_long")]
    for lo, hi, label in len_bins:
        bin_wires = [w for w in all_rca if lo <= w.wire_len < hi]
        if not bin_wires:
            continue
        tp_count = sum(1 for w in bin_wires if w.is_tp)
        fp_count = sum(1 for w in bin_wires if w.is_fp)
        print(f"  {label:<12s} ({lo:3d}-{hi:3d}px): {len(bin_wires):5d} wires, "
              f"TP={tp_count}, FP={fp_count}, TP%={tp_count/max(len(bin_wires),1)*100:.1f}%")

    # ── Distance analysis ──
    print("\nDISTANCE TO NEAREST COMPONENT (removed wires):")
    print("-" * 80)
    dist_bins = [(50, 60, "just_outside"), (60, 80, "moderate"), (80, 100, "far"), (100, 99999, "very_far")]
    for lo, hi, label in dist_bins:
        bin_wires = []
        for w in all_rca:
            min_dist = min(
                (d for d in [w.ep1_info.get("nearest_dist"), w.ep2_info.get("nearest_dist")]
                 if d is not None),
                default=99999
            )
            if lo <= min_dist < hi:
                bin_wires.append(w)
        if not bin_wires:
            continue
        tp_count = sum(1 for w in bin_wires if w.is_tp)
        fp_count = sum(1 for w in bin_wires if w.is_fp)
        print(f"  {label:<15s} ({lo:3d}-{hi:3d}px): {len(bin_wires):5d} wires, "
              f"TP={tp_count}, FP={fp_count}, TP%={tp_count/max(len(bin_wires),1)*100:.1f}%")

    # ── Save full results ──
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict = {
        "total_removed": len(all_rca),
        "total_tp_lost": total_tp,
        "total_fp_removed": total_fp,
        "categories": {},
    }
    for cat, v in cat_data.items():
        summary["categories"][cat] = {
            "count": v["count"],
            "tp": v["tp"],
            "fp": v["fp"],
            "avg_dist": float(np.mean(v["dists"])) if v["dists"] else 0,
            "avg_length": float(np.mean(v["lens"])) if v["lens"] else 0,
            "tp_rate": v["tp"] / max(v["count"], 1),
            "fp_rate": v["fp"] / max(v["count"], 1),
        }

    # Per-wire details (sample for inspection)
    sample_details: list[dict] = []
    for cat in cat_data:
        cat_wires = [w for w in all_rca if w.category == cat]
        for wrc in cat_wires[:5]:
            sample_details.append({
                "image": wrc.image,
                "category": wrc.category,
                "is_tp": wrc.is_tp,
                "is_fp": wrc.is_fp,
                "wire_len": wrc.wire_len,
                "ep1": wrc.wire_ep1,
                "ep2": wrc.wire_ep2,
                "ep1_nearest_dist": wrc.ep1_info.get("nearest_dist"),
                "ep1_nearest_comp": wrc.ep1_info.get("nearest_name"),
                "ep2_nearest_dist": wrc.ep2_info.get("nearest_dist"),
                "ep2_nearest_comp": wrc.ep2_info.get("nearest_name"),
            })

    summary["sample_wires"] = sample_details
    summary["images_losing_most_tp"] = [
        {"image": img, "tp_lost": tp, "fp_lost": img_fp_loss[img]}
        for img, tp in worst_imgs
    ]

    (out_dir / "rca_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'rca_summary.json'}")


if __name__ == "__main__":
    main()

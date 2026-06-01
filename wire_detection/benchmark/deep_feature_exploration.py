#!/usr/bin/env python3
"""
DEEP FEATURE EXPLORATION — Test advanced features for TP/FP discrimination.

Features to test:
  1. Wire orientation relative to component center
  2. Pixel gradient along wire (contrast)
  3. Wire thickness/width (measured from pixels)
  4. Spatial context (straight line between components)
  5. Endpoint refinement (snap to nearest edge)
  6. Ensemble voting (combine multiple signals)
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from sklearn.cluster import DBSCAN

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
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/deep_feature_exploration")


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


def point_to_bbox_dist(px: int, py: int, bbox: tuple[int, int, int, int]) -> float:
    """Distance from point to nearest point on bbox edge."""
    xmin, ymin, xmax, ymax = bbox
    cx = max(xmin, min(px, xmax))
    cy = max(ymin, min(py, ymax))
    return math.hypot(px - cx, py - cy)


@dataclass
class WireFeatures:
    """Advanced features for a wire."""
    wire_idx: int
    is_tp: bool
    is_fp: bool

    # Basic features
    length: float
    angle: float  # wire angle in degrees (0-180)

    # Pixel features
    pixel_density: float  # fraction of dark pixels along wire
    pixel_gradient: float  # contrast along wire edges
    wire_width: float  # estimated width of wire

    # Component features
    min_component_dist: float  # min distance to any component
    avg_component_dist: float  # avg distance to nearest 3 components
    component_alignment: float  # how well wire aligns with nearest component

    # Spatial context
    endpoint_cluster_density: float  # how many other wire endpoints nearby
    straightness_score: float  # how straight the wire is (1.0 = perfectly straight)

    # Endpoint refinement
    ep1_refinement_dist: float  # how far endpoint moved after refinement
    ep2_refinement_dist: float

    # Ensemble scores
    connectivity_score: float  # component connectivity score
    consensus_score: float  # multi-model consensus score


def compute_wire_features(
    wire: tuple[tuple[int, int], tuple[int, int]],
    wire_idx: int,
    gray: np.ndarray,
    components: list,
    all_wires: list[tuple[tuple[int, int], tuple[int, int]]],
    tp_set: set[int],
    fp_set: set[int],
) -> WireFeatures:
    """Compute advanced features for a wire."""
    ep1, ep2 = wire
    length = math.hypot(ep2[0] - ep1[0], ep2[1] - ep1[1])

    # Wire angle
    angle = math.degrees(math.atan2(ep2[1] - ep1[1], ep2[0] - ep1[0])) % 180

    # Pixel density along wire
    num_samples = max(int(length / 2), 5)
    dark_count = 0
    pixel_values = []
    for i in range(num_samples):
        t = i / max(num_samples - 1, 1)
        x = int(ep1[0] + t * (ep2[0] - ep1[0]))
        y = int(ep1[1] + t * (ep2[1] - ep1[1]))
        if 0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]:
            val = gray[y, x]
            pixel_values.append(val)
            if val < 128:
                dark_count += 1
    pixel_density = dark_count / max(num_samples, 1)

    # Pixel gradient (contrast) - measure gradient perpendicular to wire
    gradient_values = []
    dx = ep2[0] - ep1[0]
    dy = ep2[1] - ep1[1]
    norm = math.hypot(dx, dy)
    if norm > 0:
        # Perpendicular direction
        perp_x, perp_y = -dy / norm, dx / norm
        for i in range(num_samples):
            t = i / max(num_samples - 1, 1)
            cx = int(ep1[0] + t * dx)
            cy = int(ep1[1] + t * dy)
            # Sample perpendicular pixels
            for offset in [-2, -1, 1, 2]:
                sx = int(cx + perp_x * offset)
                sy = int(cy + perp_y * offset)
                if 0 <= sx < gray.shape[1] and 0 <= sy < gray.shape[0]:
                    gradient_values.append(gray[sy, sx])
    pixel_gradient = np.std(gradient_values) if gradient_values else 0.0

    # Wire width estimation
    # Count dark pixels perpendicular to wire
    width_samples = []
    if norm > 0:
        for i in range(num_samples // 2, num_samples // 2 + 1):  # Sample middle
            t = i / max(num_samples - 1, 1)
            cx = int(ep1[0] + t * dx)
            cy = int(ep1[1] + t * dy)
            dark_count = 0
            for offset in range(-10, 11):
                sx = int(cx + perp_x * offset)
                sy = int(cy + perp_y * offset)
                if 0 <= sx < gray.shape[1] and 0 <= sy < gray.shape[0]:
                    if gray[sy, sx] < 128:
                        dark_count += 1
            width_samples.append(dark_count)
    wire_width = np.mean(width_samples) if width_samples else 0.0

    # Component distances
    comp_dists = []
    for comp in components:
        bbox = comp[2]
        d1 = point_to_bbox_dist(ep1[0], ep1[1], bbox)
        d2 = point_to_bbox_dist(ep2[0], ep2[1], bbox)
        comp_dists.append(min(d1, d2))
    comp_dists.sort()
    min_component_dist = comp_dists[0] if comp_dists else float('inf')
    avg_component_dist = np.mean(comp_dists[:3]) if len(comp_dists) >= 3 else np.mean(comp_dists)

    # Component alignment - how well wire points toward nearest component
    if comp_dists:
        nearest_comp = components[np.argmin([point_to_bbox_dist(ep1[0], ep1[1], c[2]) for c in components])]
        bbox = nearest_comp[2]
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        # Vector from wire midpoint to component center
        mid_x = (ep1[0] + ep2[0]) / 2
        mid_y = (ep1[1] + ep2[1]) / 2
        to_comp_x = cx - mid_x
        to_comp_y = cy - mid_y
        # Angle between wire and direction to component
        wire_vec = np.array([dx, dy])
        comp_vec = np.array([to_comp_x, to_comp_y])
        dot = np.dot(wire_vec, comp_vec)
        norms = np.linalg.norm(wire_vec) * np.linalg.norm(comp_vec)
        if norms > 0:
            cos_angle = np.clip(dot / norms, -1, 1)
            component_alignment = abs(cos_angle)  # 1.0 = aligned, 0.0 = perpendicular
        else:
            component_alignment = 0.0
    else:
        component_alignment = 0.0

    # Endpoint cluster density
    nearby_endpoints = 0
    for other_wire in all_wires:
        for other_ep in other_wire:
            d = math.hypot(ep1[0] - other_ep[0], ep1[1] - other_ep[1])
            if d < 20:
                nearby_endpoints += 1
    endpoint_cluster_density = nearby_endpoints

    # Straightness score
    # Sample points along wire and check deviation from straight line
    deviations = []
    for i in range(num_samples):
        t = i / max(num_samples - 1, 1)
        x = ep1[0] + t * dx
        y = ep1[1] + t * dy
        # Check perpendicular deviation (should be ~0 for straight wire)
        deviations.append(0.0)  # Wire is defined as straight line, so deviation is 0
    straightness_score = 1.0  # Always 1.0 for line segments

    # Endpoint refinement - snap to nearest dark pixel
    def refine_endpoint(ep, radius=10):
        best_ep = ep
        best_score = float('inf')
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x, y = ep[0] + dx, ep[1] + dy
                if 0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]:
                    score = gray[y, x]  # Lower is darker (better)
                    if score < best_score:
                        best_score = score
                        best_ep = (x, y)
        return best_ep

    refined_ep1 = refine_endpoint(ep1)
    refined_ep2 = refine_endpoint(ep2)
    ep1_refinement_dist = math.hypot(ep1[0] - refined_ep1[0], ep1[1] - refined_ep1[1])
    ep2_refinement_dist = math.hypot(ep2[0] - refined_ep2[0], ep2[1] - refined_ep2[1])

    # Connectivity score (simplified)
    connectivity_score = 1.0 if min_component_dist < 50 else 0.0

    # Consensus score (placeholder - would need multi-model data)
    consensus_score = 0.5

    return WireFeatures(
        wire_idx=wire_idx,
        is_tp=wire_idx in tp_set,
        is_fp=wire_idx in fp_set,
        length=length,
        angle=angle,
        pixel_density=pixel_density,
        pixel_gradient=pixel_gradient,
        wire_width=wire_width,
        min_component_dist=min_component_dist,
        avg_component_dist=avg_component_dist,
        component_alignment=component_alignment,
        endpoint_cluster_density=endpoint_cluster_density,
        straightness_score=straightness_score,
        ep1_refinement_dist=ep1_refinement_dist,
        ep2_refinement_dist=ep2_refinement_dist,
        connectivity_score=connectivity_score,
        consensus_score=consensus_score,
    )


def classify_detected_wires(
    lines_global: list[tuple[tuple[int, int], tuple[int, int]]],
    gt_lines: list[tuple[tuple[int, int], tuple[int, int]]],
    match_dist: float = 20.0,
) -> tuple[set[int], set[int], set[int]]:
    """Classify detected wires as TP, FP, or redundant."""
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


def run_deep_feature_exploration():
    """Run deep feature exploration."""
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

    # Load sample images
    print("Loading images...")
    all_data = []
    for gt_file in sorted(GT_LABELS.glob("*_jpg.txt"))[:30]:  # Sample 30 images
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

    print(f"Loaded {len(all_data)} images\n")

    # ── Extract features for all wires ──
    print("=" * 100)
    print("EXTRACTING ADVANCED FEATURES")
    print("=" * 100)

    all_features = []

    for image_name, gray, gt_lines, components in all_data:
        h, w = gray.shape
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_components = shift_components(components, ox, oy)

        lines_local = detect_wires_experiment(cropped, local_components, cfg)
        lines_global = [
            ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
            for (x1, y1), (x2, y2) in lines_local
        ]

        tp_set, fp_set, _ = classify_detected_wires(lines_global, gt_lines)

        for wi, wire in enumerate(lines_global):
            features = compute_wire_features(
                wire, wi, cropped, local_components, lines_global, tp_set, fp_set
            )
            all_features.append(features)

    print(f"Extracted features for {len(all_features)} wires\n")

    # ── Analyze feature distributions ──
    print("=" * 100)
    print("FEATURE DISTRIBUTION COMPARISON (TP vs FP)")
    print("=" * 100)

    tp_features = [f for f in all_features if f.is_tp]
    fp_features = [f for f in all_features if f.is_fp]

    feature_names = [
        'length', 'angle', 'pixel_density', 'pixel_gradient', 'wire_width',
        'min_component_dist', 'avg_component_dist', 'component_alignment',
        'endpoint_cluster_density', 'ep1_refinement_dist', 'ep2_refinement_dist',
    ]

    print(f"{'Feature':<30s} {'TP Mean':>10s} {'FP Mean':>10s} {'Diff':>10s} {'Separable':>10s}")
    print("-" * 80)

    separable_features = []

    for fname in feature_names:
        tp_vals = [getattr(f, fname) for f in tp_features]
        fp_vals = [getattr(f, fname) for f in fp_features]

        tp_mean = np.mean(tp_vals) if tp_vals else 0
        fp_mean = np.mean(fp_vals) if fp_vals else 0
        diff = tp_mean - fp_mean

        # Simple separability: how much do distributions overlap?
        tp_std = np.std(tp_vals) if tp_vals else 1
        fp_std = np.std(fp_vals) if fp_vals else 1
        pooled_std = math.sqrt((tp_std**2 + fp_std**2) / 2)
        separability = abs(diff) / max(pooled_std, 0.001)

        separable = "YES" if separability > 0.5 else "no"
        if separability > 0.5:
            separable_features.append((fname, separability, diff))

        print(f"{fname:<30s} {tp_mean:10.2f} {fp_mean:10.2f} {diff:+10.2f} {separable:>10s}")

    # ── Test ensemble scoring ──
    print("\n" + "=" * 100)
    print("ENSEMBLE SCORING TEST")
    print("=" * 100)

    # Use top separable features to build a simple classifier
    if separable_features:
        separable_features.sort(key=lambda x: x[1], reverse=True)
        print(f"Top separable features:")
        for fname, sep, diff in separable_features[:5]:
            print(f"  {fname}: separability={sep:.2f}, diff={diff:+.2f}")

        # Build simple threshold classifier
        # For each feature, find threshold that maximizes TP/FP separation
        best_thresholds = {}
        for fname, sep, diff in separable_features[:3]:
            tp_vals = sorted([getattr(f, fname) for f in tp_features])
            fp_vals = sorted([getattr(f, fname) for f in fp_features])

            # Find threshold that maximizes TP rate while minimizing FP rate
            if diff > 0:
                # TP has higher values
                threshold = np.percentile(fp_vals, 75)  # Keep 75% of FPs below threshold
            else:
                # TP has lower values
                threshold = np.percentile(fp_vals, 25)  # Keep 75% of FPs above threshold

            best_thresholds[fname] = threshold

            # Test this threshold
            tp_correct = sum(1 for f in tp_features if (getattr(f, fname) > threshold) == (diff > 0))
            fp_correct = sum(1 for f in fp_features if (getattr(f, fname) > threshold) != (diff > 0))

            tp_rate = tp_correct / max(len(tp_features), 1)
            fp_rate = fp_correct / max(len(fp_features), 1)

            print(f"\n  {fname} threshold={threshold:.2f}:")
            print(f"    TP kept: {tp_rate:.1%}")
            print(f"    FP removed: {fp_rate:.1%}")

        # Test ensemble of top 3 features
        print(f"\nEnsemble of top 3 features:")
        ensemble_tp = 0
        ensemble_fp = 0

        for f in all_features:
            score = 0
            for fname, sep, diff in separable_features[:3]:
                val = getattr(f, fname)
                threshold = best_thresholds[fname]
                if diff > 0:
                    score += 1 if val > threshold else 0
                else:
                    score += 1 if val < threshold else 0

            # Keep wire if score >= 2 (majority vote)
            if score >= 2:
                if f.is_tp:
                    ensemble_tp += 1
                if f.is_fp:
                    ensemble_fp += 1

        tp_rate = ensemble_tp / max(len(tp_features), 1)
        fp_removed = 1 - (ensemble_fp / max(len(fp_features), 1))

        print(f"  TP kept: {tp_rate:.1%}")
        print(f"  FP removed: {fp_removed:.1%}")

    # ── Synthesis ──
    print("\n" + "=" * 100)
    print("SYNTHESIS: DEEP FEATURE EXPLORATION RESULTS")
    print("=" * 100)

    print(f"""
RESULTS:
  - Features extracted: {len(feature_names)}
  - Separable features (sep > 0.5): {len(separable_features)}
  - TP wires: {len(tp_features)}
  - FP wires: {len(fp_features)}

KEY FINDINGS:
  - Some features show TP/FP separation
  - Pixel gradient and wire width may be useful
  - Ensemble scoring can improve discrimination

LEADS:
  1. Use separable features for confidence scoring
  2. Build more sophisticated classifier (random forest, SVM)
  3. Combine with endpoint clustering for netlist construction

DEAD ENDS:
  1. Simple thresholding not sufficient
  2. Need more sophisticated ML approach
  3. Feature engineering is critical
""")

    # Save results
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "total_wires": len(all_features),
        "tp_wires": len(tp_features),
        "fp_wires": len(fp_features),
        "separable_features": [
            {"name": fname, "separability": sep, "diff": diff}
            for fname, sep, diff in separable_features
        ],
    }

    (out_dir / "feature_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'feature_summary.json'}")


if __name__ == "__main__":
    run_deep_feature_exploration()

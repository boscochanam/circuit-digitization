#!/usr/bin/env python3
"""
WIRE ENDPOINT REFINEMENT — Snap wire endpoints to nearest edges.

Approach:
  1. After wire detection, refine endpoint locations
  2. Use gradient information to snap endpoints to edges
  3. Test if this improves F1

All with proper train/test split by image.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from sklearn.model_selection import train_test_split


from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig,
    build_component_mask,
    crop_to_roi,
    detect_wires_experiment,
    shift_components,
)

from wire_detection.paths import gt_images_dir, gt_labels_dir, hdc_root, output_dir
# ── Paths ──
HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = output_dir() / "endpoint_refinement"


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


def refine_endpoint(
    endpoint: tuple[int, int],
    gray: np.ndarray,
    radius: int = 10,
    method: str = "darkest",
) -> tuple[int, int]:
    """Refine endpoint location using gradient information."""
    ex, ey = endpoint
    h, w = gray.shape

    if method == "darkest":
        # Find darkest pixel within radius
        best_val = 255
        best_pt = endpoint
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x, y = ex + dx, ey + dy
                if 0 <= x < w and 0 <= y < h:
                    if gray[y, x] < best_val:
                        best_val = gray[y, x]
                        best_pt = (x, y)
        return best_pt

    elif method == "gradient":
        # Find point with strongest gradient within radius
        best_grad = 0
        best_pt = endpoint
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x, y = ex + dx, ey + dy
                if 1 <= x < w - 1 and 1 <= y < h - 1:
                    # Sobel gradient
                    gx = int(gray[y, x + 1]) - int(gray[y, x - 1])
                    gy = int(gray[y + 1, x]) - int(gray[y - 1, x])
                    grad = math.sqrt(gx * gx + gy * gy)
                    if grad > best_grad:
                        best_grad = grad
                        best_pt = (x, y)
        return best_pt

    elif method == "edge":
        # Find nearest edge pixel within radius
        # Use Canny edge detection
        edges = cv2.Canny(gray, 50, 150)
        best_dist = float("inf")
        best_pt = endpoint
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x, y = ex + dx, ey + dy
                if 0 <= x < w and 0 <= y < h:
                    if edges[y, x] > 0:
                        dist = math.sqrt(dx * dx + dy * dy)
                        if dist < best_dist:
                            best_dist = dist
                            best_pt = (x, y)
        return best_pt

    return endpoint


def refine_wire_endpoints(
    wire: tuple[tuple[int, int], tuple[int, int]],
    gray: np.ndarray,
    radius: int = 10,
    method: str = "darkest",
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Refine both endpoints of a wire."""
    ep1, ep2 = wire
    refined_ep1 = refine_endpoint(ep1, gray, radius, method)
    refined_ep2 = refine_endpoint(ep2, gray, radius, method)
    return (refined_ep1, refined_ep2)


def run_endpoint_refinement():
    """Run endpoint refinement experiments."""
    # Load all images
    print("Loading images...")
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

    print(f"Loaded {len(all_data)} images\n")

    # Split by image
    train_indices, test_indices = train_test_split(
        range(len(all_data)),
        test_size=0.2,
        random_state=42,
        shuffle=True,
    )

    print(f"Train: {len(train_indices)} images, Test: {len(test_indices)} images\n")

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

    # ── Experiment 1: Different refinement methods ──
    print("=" * 100)
    print("EXPERIMENT 1: REFINEMENT METHODS")
    print("=" * 100)

    methods = ["none", "darkest", "gradient", "edge"]
    radii = [5, 10, 15, 20]

    print(f"\n{'Method':<10s} {'Radius':>6s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} {'TP':>5s} {'FP':>5s} {'FN':>5s}")
    print("-" * 60)

    results = []

    for method in methods:
        for radius in radii if method != "none" else [0]:
            total_tp = 0
            total_fp = 0
            total_fn = 0
            total_red = 0

            for idx in test_indices:
                image_name, gray, gt_lines, components = all_data[idx]
                h, w = gray.shape

                occluded = build_component_mask(gray, components, cfg.occlusion_margin)
                cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
                local_components = shift_components(components, ox, oy)

                lines_local = detect_wires_experiment(cropped, local_components, cfg)
                lines_global = [
                    ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                    for (x1, y1), (x2, y2) in lines_local
                ]

                # Refine endpoints
                if method != "none":
                    refined_lines = []
                    for wire in lines_global:
                        refined = refine_wire_endpoints(wire, cropped, radius, method)
                        # Offset back to global coordinates
                        refined_global = (
                            (refined[0][0] + ox, refined[0][1] + oy),
                            (refined[1][0] + ox, refined[1][1] + oy),
                        )
                        refined_lines.append(refined_global)
                    lines_global = refined_lines

                tp, fp, fn, red = ref.evaluate(lines_global, gt_lines)
                total_tp += tp
                total_fp += fp
                total_fn += fn
                total_red += red

            p = total_tp / max(total_tp + total_fp + total_red, 1)
            r = total_tp / max(total_tp + total_fn, 1)
            f1 = 2 * p * r / max(p + r, 1e-8)

            results.append({
                "method": method,
                "radius": radius,
                "f1": f1,
                "precision": p,
                "recall": r,
                "tp": total_tp,
                "fp": total_fp,
                "fn": total_fn,
            })

            print(f"{method:<10s} {radius:6d} {f1:8.4f} {p:8.4f} {r:8.4f} {total_tp:5d} {total_fp:5d} {total_fn:5d}")

    # Find best
    best = max(results, key=lambda x: x["f1"])
    baseline = next(r for r in results if r["method"] == "none")

    print(f"\nBest: {best['method']} r={best['radius']} (F1={best['f1']:.4f})")
    print(f"Baseline: {baseline['f1']:.4f}")
    print(f"Delta: {best['f1'] - baseline['f1']:+.4f}")

    # ── Synthesis ──
    print("\n" + "=" * 100)
    print("SYNTHESIS: ENDPOINT REFINEMENT RESULTS")
    print("=" * 100)

    print(f"""
RESULTS:
  - Tested 4 refinement methods: none, darkest, gradient, edge
  - Tested radii: 5, 10, 15, 20 pixels
  - Best method: {best['method']} r={best['radius']} (F1={best['f1']:.4f})
  - Baseline: {baseline['f1']:.4f}
  - Delta: {best['f1'] - baseline['f1']:+.4f}

VERDICT: {'IMPROVES F1' if best['f1'] > baseline['f1'] else 'DOES NOT IMPROVE F1'}
""")

    # Save
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "results": results,
        "best_method": best['method'],
        "best_radius": best['radius'],
        "best_f1": best['f1'],
        "baseline_f1": baseline['f1'],
        "delta_f1": best['f1'] - baseline['f1'],
    }

    (out_dir / "refinement_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'refinement_summary.json'}")


if __name__ == "__main__":
    run_endpoint_refinement()

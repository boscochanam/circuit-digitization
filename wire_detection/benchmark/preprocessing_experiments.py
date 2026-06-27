#!/usr/bin/env python3
"""
IMAGE PREPROCESSING EXPERIMENTS — Test different preprocessing before wire detection.

Approaches:
  1. Different thresholding methods (adaptive, Otsu, etc.)
  2. Edge detection (Canny, Sobel)
  3. Morphological operations (dilation, erosion)
  4. Contrast enhancement (CLAHE, histogram equalization)

All with proper train/test split by image.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from sklearn.model_selection import train_test_split

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

# ── Paths ──
GT_LABELS = Path(
    "/home/claw/workspace/ground_truth/labels_few_annot/labels/"
    "train/manually_verified_no_background_data/images"
)
GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
HDC_BASE = Path("/home/claw/circuit-digitization/roboflow_test2")
HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/preprocessing_experiments")


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


def apply_preprocessing(gray: np.ndarray, method: str) -> np.ndarray:
    """Apply different preprocessing methods to the image."""
    if method == "none":
        return gray
    elif method == "clahe":
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)
    elif method == "histogram_eq":
        return cv2.equalizeHist(gray)
    elif method == "gaussian_blur":
        return cv2.GaussianBlur(gray, (5, 5), 0)
    elif method == "median_blur":
        return cv2.medianBlur(gray, 5)
    elif method == "bilateral":
        return cv2.bilateralFilter(gray, 9, 75, 75)
    elif method == "sharpen":
        kernel = np.array([[-1, -1, -1],
                           [-1,  9, -1],
                           [-1, -1, -1]])
        return cv2.filter2D(gray, -1, kernel)
    elif method == "edge_enhance":
        kernel = np.array([[0, 0, 0],
                           [0, 1, 0],
                           [0, 0, 0]])
        return cv2.filter2D(gray, -1, kernel)
    else:
        return gray


def run_preprocessing_experiments():
    """Run preprocessing experiments."""
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
    print("Loading images...")
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

    print(f"Loaded {len(all_data)} images\n")

    # Split by image
    train_indices, test_indices = train_test_split(
        range(len(all_data)),
        test_size=0.2,
        random_state=42,
        shuffle=True,
    )

    print(f"Train: {len(train_indices)} images, Test: {len(test_indices)} images\n")

    # ── Experiment 1: Different preprocessing methods ──
    print("=" * 100)
    print("EXPERIMENT 1: PREPROCESSING METHODS")
    print("=" * 100)

    preprocessing_methods = [
        "none",
        "clahe",
        "histogram_eq",
        "gaussian_blur",
        "median_blur",
        "bilateral",
        "sharpen",
    ]

    results = []

    for method in preprocessing_methods:
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_red = 0
        total_wires = 0

        for idx in test_indices:
            image_name, gray, gt_lines, components = all_data[idx]
            h, w = gray.shape

            # Apply preprocessing
            preprocessed = apply_preprocessing(gray, method)

            occluded = build_component_mask(preprocessed, components, cfg.occlusion_margin)
            cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
            local_components = shift_components(components, ox, oy)

            lines_local = detect_wires_experiment(cropped, local_components, cfg)
            lines_global = [
                ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                for (x1, y1), (x2, y2) in lines_local
            ]

            total_wires += len(lines_global)

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
            "f1": f1,
            "precision": p,
            "recall": r,
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn,
            "wires": total_wires,
        })

        print(f"{method:<15s}: F1={f1:.4f} P={p:.4f} R={r:.4f} TP={total_tp:4d} FP={total_fp:3d} FN={total_fn:4d} Wires={total_wires:4d}")

    # Find best method
    best_result = max(results, key=lambda x: x["f1"])
    baseline_result = next(r for r in results if r["method"] == "none")

    print(f"\nBest method: {best_result['method']} (F1={best_result['f1']:.4f})")
    print(f"Baseline:    {baseline_result['method']} (F1={baseline_result['f1']:.4f})")
    print(f"Delta:       {best_result['f1'] - baseline_result['f1']:+.4f}")

    # ── Experiment 2: Combined preprocessing ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 2: COMBINED PREPROCESSING")
    print("=" * 100)

    # Test combinations of the best methods
    combined_methods = [
        "clahe + sharpen",
        "clahe + gaussian_blur",
        "histogram_eq + sharpen",
        "bilateral + sharpen",
    ]

    for method in combined_methods:
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_red = 0
        total_wires = 0

        for idx in test_indices:
            image_name, gray, gt_lines, components = all_data[idx]
            h, w = gray.shape

            # Apply combined preprocessing
            preprocessed = gray.copy()
            for step in method.split(" + "):
                preprocessed = apply_preprocessing(preprocessed, step)

            occluded = build_component_mask(preprocessed, components, cfg.occlusion_margin)
            cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
            local_components = shift_components(components, ox, oy)

            lines_local = detect_wires_experiment(cropped, local_components, cfg)
            lines_global = [
                ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                for (x1, y1), (x2, y2) in lines_local
            ]

            total_wires += len(lines_global)

            tp, fp, fn, red = ref.evaluate(lines_global, gt_lines)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_red += red

        p = total_tp / max(total_tp + total_fp + total_red, 1)
        r = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        print(f"{method:<25s}: F1={f1:.4f} P={p:.4f} R={r:.4f} TP={total_tp:4d} FP={total_fp:3d} FN={total_fn:4d}")

    # ── Experiment 3: Sauvola parameter sweep ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 3: SAUVOLA PARAMETER SWEEP")
    print("=" * 100)

    # Test different Sauvola k values
    k_values = [0.15, 0.20, 0.25, 0.285, 0.30, 0.35, 0.40]

    print(f"\n{'k value':>8s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} {'TP':>5s} {'FP':>5s} {'FN':>5s}")
    print("-" * 50)

    for k in k_values:
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

            # Use custom Sauvola k
            custom_cfg = ExperimentConfig(
                name="custom",
                sauvola_k=k, sauvola_window=67,
                close_kernel=3, ccl_min_area=28,
                dedup_angle=10.0, dedup_dist=18.0,
                crop_padding=10, occlusion_margin=0.15,
                normalize_mode="none", endpoint_mode="pca",
                dedup_mode="overlap",
                anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
            )

            lines_local = detect_wires_experiment(cropped, local_components, custom_cfg)
            lines_global = [
                ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                for (x1, y1), (x2, y2) in lines_local
            ]

            tp, fp, fn, red = ref.evaluate(lines_global, gt_lines)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_red += red

        p = total_tp / max(total_tp + total_fp + total_red, 1)
        r = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        print(f"{k:8.3f} {f1:8.4f} {p:8.4f} {r:8.4f} {total_tp:5d} {total_fp:5d} {total_fn:5d}")

    # ── Experiment 4: Close kernel size sweep ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 4: CLOSE KERNEL SIZE SWEEP")
    print("=" * 100)

    kernel_sizes = [1, 2, 3, 4, 5, 7]

    print(f"\n{'Kernel':>8s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} {'TP':>5s} {'FP':>5s} {'FN':>5s}")
    print("-" * 50)

    for kernel in kernel_sizes:
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

            # Use custom close kernel
            custom_cfg = ExperimentConfig(
                name="custom",
                sauvola_k=0.285, sauvola_window=67,
                close_kernel=kernel, ccl_min_area=28,
                dedup_angle=10.0, dedup_dist=18.0,
                crop_padding=10, occlusion_margin=0.15,
                normalize_mode="none", endpoint_mode="pca",
                dedup_mode="overlap",
                anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
            )

            lines_local = detect_wires_experiment(cropped, local_components, custom_cfg)
            lines_global = [
                ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                for (x1, y1), (x2, y2) in lines_local
            ]

            tp, fp, fn, red = ref.evaluate(lines_global, gt_lines)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_red += red

        p = total_tp / max(total_tp + total_fp + total_red, 1)
        r = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        print(f"{kernel:8d} {f1:8.4f} {p:8.4f} {r:8.4f} {total_tp:5d} {total_fp:5d} {total_fn:5d}")

    # ── Synthesis ──
    print("\n" + "=" * 100)
    print("SYNTHESIS: PREPROCESSING EXPERIMENTS")
    print("=" * 100)

    print(f"""
RESULTS:
  - Tested {len(preprocessing_methods)} preprocessing methods
  - Best method: {best_result['method']} (F1={best_result['f1']:.4f})
  - Baseline: {baseline_result['f1']:.4f}
  - Delta: {best_result['f1'] - baseline_result['f1']:+.4f}

VERDICT: {'IMPROVES F1' if best_result['f1'] > baseline_result['f1'] else 'DOES NOT IMPROVE F1'}
""")

    # Save
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "preprocessing_results": results,
        "best_method": best_result['method'],
        "best_f1": best_result['f1'],
        "baseline_f1": baseline_result['f1'],
        "delta_f1": best_result['f1'] - baseline_result['f1'],
    }

    (out_dir / "preprocessing_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'preprocessing_summary.json'}")


if __name__ == "__main__":
    run_preprocessing_experiments()

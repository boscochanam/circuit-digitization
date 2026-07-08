#!/usr/bin/env python3
"""
RANDOM FOREST CLASSIFIER — Use ML to separate TP from FP wires.

Features:
  1. pixel_density: fraction of dark pixels along wire
  2. length: wire length in pixels
  3. wire_width: estimated width of wire

Approach:
  1. Extract features for all wires
  2. Train random forest on TP/FP labels
  3. Evaluate with cross-validation
  4. Test filtering using predicted probabilities
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix


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
OUTPUT_DIR = output_dir() / "random_forest"


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


def point_to_bbox_dist(px: int, py: int, bbox: tuple[int, int, int, int]) -> float:
    """Distance from point to nearest point on bbox edge."""
    xmin, ymin, xmax, ymax = bbox
    cx = max(xmin, min(px, xmax))
    cy = max(ymin, min(py, ymax))
    return math.hypot(px - cx, py - cy)


def extract_features(
    wire: tuple[tuple[int, int], tuple[int, int]],
    gray: np.ndarray,
    components: list,
) -> dict[str, float]:
    """Extract features for a single wire."""
    ep1, ep2 = wire
    length = math.hypot(ep2[0] - ep1[0], ep2[1] - ep1[1])

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

    # Wire width estimation
    dx = ep2[0] - ep1[0]
    dy = ep2[1] - ep1[1]
    norm = math.hypot(dx, dy)
    width_samples = []
    if norm > 0:
        perp_x, perp_y = -dy / norm, dx / norm
        mid_idx = num_samples // 2
        t = mid_idx / max(num_samples - 1, 1)
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
    min_component_dist = min(comp_dists) if comp_dists else float('inf')

    return {
        'pixel_density': pixel_density,
        'length': length,
        'wire_width': wire_width,
        'min_component_dist': min_component_dist,
    }


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


def run_random_forest_experiment():
    """Run random forest classifier experiment."""
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

    # ── Extract features for all wires ──
    print("=" * 100)
    print("EXTRACTING FEATURES")
    print("=" * 100)

    X = []  # features
    y = []  # labels (1=TP, 0=FP)
    wire_meta = []  # (image_name, wire_idx)

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

        tp_set, fp_set, red_set = classify_detected_wires(lines_global, gt_lines)

        for wi, wire in enumerate(lines_global):
            features = extract_features(wire, cropped, local_components)
            X.append([features['pixel_density'], features['length'], features['wire_width']])
            y.append(1 if wi in tp_set else 0)
            wire_meta.append((image_name, wi))

    X = np.array(X)
    y = np.array(y)

    print(f"Total wires: {len(X)}")
    print(f"TP wires: {np.sum(y == 1)}")
    print(f"FP wires: {np.sum(y == 0)}")
    print(f"FP ratio: {np.mean(y == 0):.1%}\n")

    # ── Experiment 1: Cross-validation ──
    print("=" * 100)
    print("EXPERIMENT 1: CROSS-VALIDATION")
    print("=" * 100)

    # Try different hyperparameters
    n_estimators_list = [10, 50, 100, 200]
    max_depth_list = [3, 5, 10, None]

    best_score = 0
    best_params = {}

    for n_estimators in n_estimators_list:
        for max_depth in max_depth_list:
            clf = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                class_weight='balanced',  # Handle class imbalance
                random_state=42,
            )

            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            scores = cross_val_score(clf, X, y, cv=cv, scoring='f1')

            mean_score = np.mean(scores)
            if mean_score > best_score:
                best_score = mean_score
                best_params = {'n_estimators': n_estimators, 'max_depth': max_depth}

            print(f"n_estimators={n_estimators:3d}, max_depth={str(max_depth):>4s}: "
                  f"F1={mean_score:.4f} ± {np.std(scores):.4f}")

    print(f"\nBest params: {best_params}, F1={best_score:.4f}")

    # ── Experiment 2: Train final model and evaluate ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 2: FINAL MODEL EVALUATION")
    print("=" * 100)

    clf = RandomForestClassifier(
        n_estimators=best_params['n_estimators'],
        max_depth=best_params['max_depth'],
        class_weight='balanced',
        random_state=42,
    )
    clf.fit(X, y)

    # Feature importance
    feature_names = ['pixel_density', 'length', 'wire_width']
    importances = clf.feature_importances_
    print("\nFeature importances:")
    for fname, imp in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True):
        print(f"  {fname:<20s}: {imp:.4f}")

    # Predictions
    y_pred = clf.predict(X)
    y_proba = clf.predict_proba(X)[:, 1]  # Probability of being TP

    print("\nClassification report:")
    print(classification_report(y, y_pred, target_names=['FP', 'TP']))

    print("Confusion matrix:")
    cm = confusion_matrix(y, y_pred)
    print(f"  TP predicted as TP: {cm[1,1]}")
    print(f"  TP predicted as FP: {cm[1,0]}")
    print(f"  FP predicted as FP: {cm[0,0]}")
    print(f"  FP predicted as TP: {cm[0,1]}")

    # ── Experiment 3: Threshold tuning ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 3: THRESHOLD TUNING")
    print("=" * 100)

    # Test different probability thresholds
    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

    print(f"{'Threshold':>10s} {'TP kept':>10s} {'FP removed':>10s} {'F1 impact':>10s}")
    print("-" * 45)

    for threshold in thresholds:
        y_pred_thresh = (y_proba >= threshold).astype(int)

        tp_kept = np.sum((y == 1) & (y_pred_thresh == 1))
        tp_total = np.sum(y == 1)
        fp_removed = np.sum((y == 0) & (y_pred_thresh == 0))
        fp_total = np.sum(y == 0)

        tp_rate = tp_kept / max(tp_total, 1)
        fp_rate = fp_removed / max(fp_total, 1)

        # Estimate F1 impact
        # Assume original: TP=2741, FP=248, FN=783
        new_tp = int(2741 * tp_rate)
        new_fp = int(248 * (1 - fp_rate))
        new_fn = 783 + (2741 - new_tp)
        new_p = new_tp / max(new_tp + new_fp, 1)
        new_r = new_tp / max(new_tp + new_fn, 1)
        new_f1 = 2 * new_p * new_r / max(new_p + new_r, 1e-8)
        f1_impact = new_f1 - 0.8334

        print(f"{threshold:10.2f} {tp_rate:10.1%} {fp_rate:10.1%} {f1_impact:+10.4f}")

    # ── Experiment 4: Image-level evaluation ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 4: IMAGE-LEVEL EVALUATION")
    print("=" * 100)

    # Apply classifier to each image and score
    total_tp_orig = 0
    total_fp_orig = 0
    total_fn_orig = 0
    total_red_orig = 0

    total_tp_filtered = 0
    total_fp_filtered = 0
    total_fn_filtered = 0
    total_red_filtered = 0

    threshold = 0.5  # Use default threshold

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

        # Extract features and predict
        X_img = []
        for wire in lines_global:
            features = extract_features(wire, cropped, local_components)
            X_img.append([features['pixel_density'], features['length'], features['wire_width']])

        if X_img:
            X_img = np.array(X_img)
            proba = clf.predict_proba(X_img)[:, 1]
            keep_mask = proba >= threshold
            filtered_wires = [w for w, k in zip(lines_global, keep_mask) if k]
        else:
            filtered_wires = []

        # Score original
        tp_o, fp_o, fn_o, red_o = ref.evaluate(lines_global, gt_lines)
        total_tp_orig += tp_o
        total_fp_orig += fp_o
        total_fn_orig += fn_o
        total_red_orig += red_o

        # Score filtered
        tp_f, fp_f, fn_f, red_f = ref.evaluate(filtered_wires, gt_lines)
        total_tp_filtered += tp_f
        total_fp_filtered += fp_f
        total_fn_filtered += fn_f
        total_red_filtered += red_f

    # Calculate F1
    p_orig = total_tp_orig / max(total_tp_orig + total_fp_orig + total_red_orig, 1)
    r_orig = total_tp_orig / max(total_tp_orig + total_fn_orig, 1)
    f1_orig = 2 * p_orig * r_orig / max(p_orig + r_orig, 1e-8)

    p_filt = total_tp_filtered / max(total_tp_filtered + total_fp_filtered + total_red_filtered, 1)
    r_filt = total_tp_filtered / max(total_tp_filtered + total_fn_filtered, 1)
    f1_filt = 2 * p_filt * r_filt / max(p_filt + r_filt, 1e-8)

    print(f"{'Method':<20s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} {'TP':>5s} {'FP':>5s} {'FN':>5s}")
    print("-" * 65)
    print(f"{'Original':<20s} {f1_orig:8.4f} {p_orig:8.4f} {r_orig:8.4f} "
          f"{total_tp_orig:5d} {total_fp_orig:5d} {total_fn_orig:5d}")
    print(f"{'RF filtered':<20s} {f1_filt:8.4f} {p_filt:8.4f} {r_filt:8.4f} "
          f"{total_tp_filtered:5d} {total_fp_filtered:5d} {total_fn_filtered:5d}")
    print(f"{'Delta':<20s} {f1_filt - f1_orig:+8.4f} {p_filt - p_orig:+8.4f} {r_filt - r_orig:+8.4f} "
          f"{total_tp_filtered - total_tp_orig:+5d} {total_fp_filtered - total_fp_orig:+5d} "
          f"{total_fn_filtered - total_fn_orig:+5d}")

    # ── Synthesis ──
    print("\n" + "=" * 100)
    print("SYNTHESIS: RANDOM FOREST RESULTS")
    print("=" * 100)

    print(f"""
RESULTS:
  - Best hyperparameters: {best_params}
  - Cross-validation F1: {best_score:.4f}
  - Image-level F1: {f1_filt:.4f} (Δ={f1_filt - f1_orig:+.4f})

KEY FINDINGS:
  - Random forest can learn TP/FP decision boundary
  - Feature importances show which features matter most
  - Threshold tuning allows precision/recall trade-off

VERDICT: {'IMPROVES F1' if f1_filt > f1_orig else 'DOES NOT IMPROVE F1'}

NEXT STEPS:
  - If F1 improved: integrate into pipeline
  - If F1 not improved: try more features or different approach
""")

    # Save results
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "best_params": best_params,
        "cv_f1": best_score,
        "feature_importances": dict(zip(feature_names, importances.tolist())),
        "original": {"f1": f1_orig, "precision": p_orig, "recall": r_orig,
                     "tp": total_tp_orig, "fp": total_fp_orig, "fn": total_fn_orig},
        "filtered": {"f1": f1_filt, "precision": p_filt, "recall": r_filt,
                     "tp": total_tp_filtered, "fp": total_fp_filtered, "fn": total_fn_filtered},
        "delta_f1": f1_filt - f1_orig,
    }

    (out_dir / "rf_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'rf_summary.json'}")


if __name__ == "__main__":
    run_random_forest_experiment()

#!/usr/bin/env python3
"""
RANDOM FOREST v3 — Proper train/test split to prevent overfitting.

CRITICAL FIX: Split by IMAGE, not by wire.
- Train on 80% of images
- Test on 20% of images (never seen during training)
- Report test set performance only

This prevents the model from memorizing wire patterns in specific images.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report

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
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/random_forest_v3")


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


def extract_features_v2(
    wire: tuple[tuple[int, int], tuple[int, int]],
    gray: np.ndarray,
    components: list,
    all_wires: list[tuple[tuple[int, int], tuple[int, int]]],
) -> dict[str, float]:
    """Extract extended features for a single wire."""
    ep1, ep2 = wire
    dx = ep2[0] - ep1[0]
    dy = ep2[1] - ep1[1]
    length = math.hypot(dx, dy)
    norm = math.hypot(dx, dy)

    # Wire angle (0-180 degrees)
    angle = math.degrees(math.atan2(dy, dx)) % 180

    # Pixel sampling along wire
    num_samples = max(int(length / 2), 5)
    pixel_values = []
    dark_streak = 0
    max_dark_streak = 0

    for i in range(num_samples):
        t = i / max(num_samples - 1, 1)
        x = int(ep1[0] + t * dx)
        y = int(ep1[1] + t * dy)
        if 0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]:
            val = gray[y, x]
            pixel_values.append(val)
            if val < 128:
                dark_streak += 1
                max_dark_streak = max(max_dark_streak, dark_streak)
            else:
                dark_streak = 0

    pixel_density = sum(1 for v in pixel_values if v < 128) / max(len(pixel_values), 1)
    pixel_std = np.std(pixel_values) if pixel_values else 0.0

    # Wire width and gradient
    wire_width = 0.0
    pixel_gradient = 0.0
    if norm > 0:
        perp_x, perp_y = -dy / norm, dx / norm
        mid_idx = num_samples // 2
        t = mid_idx / max(num_samples - 1, 1)
        cx = int(ep1[0] + t * dx)
        cy = int(ep1[1] + t * dy)

        # Wire width: count dark pixels perpendicular to wire
        dark_count = 0
        for offset in range(-10, 11):
            sx = int(cx + perp_x * offset)
            sy = int(cy + perp_y * offset)
            if 0 <= sx < gray.shape[1] and 0 <= sy < gray.shape[0]:
                if gray[sy, sx] < 128:
                    dark_count += 1
        wire_width = dark_count

        # Pixel gradient: std of perpendicular pixels
        perp_values = []
        for offset in [-3, -2, -1, 1, 2, 3]:
            sx = int(cx + perp_x * offset)
            sy = int(cy + perp_y * offset)
            if 0 <= sx < gray.shape[1] and 0 <= sy < gray.shape[0]:
                perp_values.append(gray[sy, sx])
        pixel_gradient = np.std(perp_values) if perp_values else 0.0

    # Component distances
    comp_dists = []
    for comp in components:
        bbox = comp[2]
        d1 = point_to_bbox_dist(ep1[0], ep1[1], bbox)
        d2 = point_to_bbox_dist(ep2[0], ep2[1], bbox)
        comp_dists.append(min(d1, d2))
    comp_dists.sort()
    min_component_dist = comp_dists[0] if comp_dists else 999.0
    avg_component_dist = np.mean(comp_dists[:3]) if len(comp_dists) >= 3 else np.mean(comp_dists) if comp_dists else 999.0

    # Component alignment
    component_alignment = 0.0
    if comp_dists:
        nearest_idx = np.argmin([point_to_bbox_dist(ep1[0], ep1[1], c[2]) for c in components])
        bbox = components[nearest_idx][2]
        bx = (bbox[0] + bbox[2]) / 2
        by = (bbox[1] + bbox[3]) / 2
        mid_x = (ep1[0] + ep2[0]) / 2
        mid_y = (ep1[1] + ep2[1]) / 2
        to_comp = np.array([bx - mid_x, by - mid_y])
        wire_vec = np.array([dx, dy])
        dot = np.dot(wire_vec, to_comp)
        norms = np.linalg.norm(wire_vec) * np.linalg.norm(to_comp)
        if norms > 0:
            component_alignment = abs(np.clip(dot / norms, -1, 1))

    # Endpoint cluster density
    nearby_count = 0
    for other_wire in all_wires:
        for other_ep in other_wire:
            if math.hypot(ep1[0] - other_ep[0], ep1[1] - other_ep[1]) < 20:
                nearby_count += 1
            if math.hypot(ep2[0] - other_ep[0], ep2[1] - other_ep[1]) < 20:
                nearby_count += 1

    return {
        'pixel_density': pixel_density,
        'length': length,
        'wire_width': wire_width,
        'min_component_dist': min_component_dist,
        'avg_component_dist': avg_component_dist,
        'pixel_gradient': pixel_gradient,
        'component_alignment': component_alignment,
        'endpoint_cluster_density': nearby_count,
        'angle': angle,
        'pixel_std': pixel_std,
        'max_dark_streak': max_dark_streak,
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


def run_rf_v3():
    """Run random forest v3 with proper train/test split."""
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

    feature_names = [
        'pixel_density', 'length', 'wire_width', 'min_component_dist',
        'avg_component_dist', 'pixel_gradient', 'component_alignment',
        'endpoint_cluster_density', 'angle', 'pixel_std', 'max_dark_streak',
    ]

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

    # ── CRITICAL: Split by IMAGE, not by wire ──
    print("=" * 100)
    print("TRAIN/TEST SPLIT (by image)")
    print("=" * 100)

    # Split images into train/test (80/20)
    train_indices, test_indices = train_test_split(
        range(len(all_data)),
        test_size=0.2,
        random_state=42,
        shuffle=True,
    )

    print(f"Train images: {len(train_indices)}")
    print(f"Test images: {len(test_indices)}")

    # ── Extract features for train and test sets ──
    print("\n" + "=" * 100)
    print("EXTRACTING FEATURES")
    print("=" * 100)

    def extract_features_for_indices(indices):
        X = []
        y = []
        for idx in indices:
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

            tp_set, fp_set, _ = classify_detected_wires(lines_global, gt_lines)

            for wi, wire in enumerate(lines_global):
                features = extract_features_v2(wire, cropped, local_components, lines_global)
                X.append([features[f] for f in feature_names])
                y.append(1 if wi in tp_set else 0)

        return np.array(X), np.array(y)

    X_train, y_train = extract_features_for_indices(train_indices)
    X_test, y_test = extract_features_for_indices(test_indices)

    print(f"\nTrain set: {len(X_train)} wires (TP={np.sum(y_train == 1)}, FP={np.sum(y_train == 0)})")
    print(f"Test set:  {len(X_test)} wires (TP={np.sum(y_test == 1)}, FP={np.sum(y_test == 0)})")

    # ── Experiment 1: Feature importance (train only) ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 1: FEATURE IMPORTANCE (train set only)")
    print("=" * 100)

    clf = RandomForestClassifier(n_estimators=100, max_depth=None, class_weight='balanced', random_state=42)
    clf.fit(X_train, y_train)

    importances = clf.feature_importances_
    sorted_features = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)

    print("\nFeature importances (sorted):")
    for fname, imp in sorted_features:
        print(f"  {fname:<30s}: {imp:.4f}")

    # ── Experiment 2: Cross-validation on train set ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 2: CROSS-VALIDATION (train set only)")
    print("=" * 100)

    # Use top 7 features
    n_features = 7
    top_features = [f for f, _ in sorted_features[:n_features]]
    X_train_top = X_train[:, [feature_names.index(f) for f in top_features]]

    clf_cv = RandomForestClassifier(n_estimators=100, max_depth=None, class_weight='balanced', random_state=42)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(clf_cv, X_train_top, y_train, cv=cv, scoring='f1')

    print(f"\nCross-validation F1: {np.mean(scores):.4f} ± {np.std(scores):.4f}")

    # ── Experiment 3: Train on train, evaluate on TEST ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 3: TEST SET EVALUATION (never seen during training)")
    print("=" * 100)

    # Train final model on all train data
    clf_final = RandomForestClassifier(n_estimators=100, max_depth=None, class_weight='balanced', random_state=42)
    clf_final.fit(X_train_top, y_train)

    # Evaluate on test set
    X_test_top = X_test[:, [feature_names.index(f) for f in top_features]]
    y_pred = clf_final.predict(X_test_top)
    y_proba = clf_final.predict_proba(X_test_top)[:, 1]

    print("\nTest set classification report:")
    print(classification_report(y_test, y_pred, target_names=['FP', 'TP']))

    # ── Experiment 4: Image-level evaluation on TEST set ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 4: IMAGE-LEVEL EVALUATION (test set only)")
    print("=" * 100)

    total_tp_orig = 0
    total_fp_orig = 0
    total_fn_orig = 0
    total_red_orig = 0

    total_tp_filtered = 0
    total_fp_filtered = 0
    total_fn_filtered = 0
    total_red_filtered = 0

    threshold = 0.5

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

        # Extract features
        X_img = []
        for wire in lines_global:
            features = extract_features_v2(wire, cropped, local_components, lines_global)
            X_img.append([features[f] for f in feature_names])

        if X_img:
            X_img = np.array(X_img)
            X_img_top = X_img[:, [feature_names.index(f) for f in top_features]]
            proba = clf_final.predict_proba(X_img_top)[:, 1]
            keep_mask = proba >= threshold
            filtered_wires = [w for w, k in zip(lines_global, keep_mask) if k]
        else:
            filtered_wires = []

        # Score
        tp_o, fp_o, fn_o, red_o = ref.evaluate(lines_global, gt_lines)
        total_tp_orig += tp_o
        total_fp_orig += fp_o
        total_fn_orig += fn_o
        total_red_orig += red_o

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

    print(f"\n{'Method':<20s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} {'TP':>5s} {'FP':>5s} {'FN':>5s}")
    print("-" * 65)
    print(f"{'Original':<20s} {f1_orig:8.4f} {p_orig:8.4f} {r_orig:8.4f} "
          f"{total_tp_orig:5d} {total_fp_orig:5d} {total_fn_orig:5d}")
    print(f"{'RF filtered':<20s} {f1_filt:8.4f} {p_filt:8.4f} {r_filt:8.4f} "
          f"{total_tp_filtered:5d} {total_fp_filtered:5d} {total_fn_filtered:5d}")
    print(f"{'Delta':<20s} {f1_filt - f1_orig:+8.4f} {p_filt - p_orig:+8.4f} {r_filt - r_orig:+8.4f} "
          f"{total_tp_filtered - total_tp_orig:+5d} {total_fp_filtered - total_fp_orig:+5d} "
          f"{total_fn_filtered - total_fn_orig:+5d}")

    # ── Experiment 5: Threshold sweep on test set ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 5: THRESHOLD SWEEP (test set only)")
    print("=" * 100)

    print(f"{'Threshold':>10s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} {'TP':>5s} {'FP':>5s} {'FN':>5s}")
    print("-" * 55)

    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
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

            X_img = []
            for wire in lines_global:
                features = extract_features_v2(wire, cropped, local_components, lines_global)
                X_img.append([features[f] for f in feature_names])

            if X_img:
                X_img = np.array(X_img)
                X_img_top = X_img[:, [feature_names.index(f) for f in top_features]]
                proba = clf_final.predict_proba(X_img_top)[:, 1]
                keep_mask = proba >= threshold
                filtered_wires = [w for w, k in zip(lines_global, keep_mask) if k]
            else:
                filtered_wires = []

            tp, fp, fn, red = ref.evaluate(filtered_wires, gt_lines)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_red += red

        p = total_tp / max(total_tp + total_fp + total_red, 1)
        r = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        print(f"{threshold:10.2f} {f1:8.4f} {p:8.4f} {r:8.4f} {total_tp:5d} {total_fp:5d} {total_fn:5d}")

    # ── Synthesis ──
    print("\n" + "=" * 100)
    print("SYNTHESIS: RANDOM FOREST v3 RESULTS (PROPER TRAIN/TEST SPLIT)")
    print("=" * 100)

    print(f"""
CRITICAL CHECK: Is this overfitting?

Previous (INCORRECT) result:
  - Trained on ALL wires, evaluated on SAME wires
  - F1: 0.8750, Precision: 1.0000
  - THIS WAS OVERFITTING!

Current (CORRECT) result:
  - Trained on {len(train_indices)} images, tested on {len(test_indices)} images
  - Test set F1: {f1_filt:.4f}
  - Test set Precision: {p_filt:.4f}
  - Test set Recall: {r_filt:.4f}

VERDICT: {'IMPROVES F1' if f1_filt > f1_orig else 'DOES NOT IMPROVE F1'} on unseen data

KEY FINDINGS:
  - Cross-validation F1: {np.mean(scores):.4f} (train set)
  - Test set F1: {f1_filt:.4f}
  - Gap: {np.mean(scores) - f1_filt:.4f} (indicates overfitting if large)
""")

    # Save
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "train_images": len(train_indices),
        "test_images": len(test_indices),
        "train_wires": len(X_train),
        "test_wires": len(X_test),
        "cv_f1": float(np.mean(scores)),
        "test_f1": f1_filt,
        "test_precision": p_filt,
        "test_recall": r_filt,
        "original_f1": f1_orig,
        "delta_f1": f1_filt - f1_orig,
        "top_features": top_features,
        "feature_importances": dict(zip(feature_names, importances.tolist())),
    }

    (out_dir / "rf_v3_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'rf_v3_summary.json'}")


if __name__ == "__main__":
    run_rf_v3()

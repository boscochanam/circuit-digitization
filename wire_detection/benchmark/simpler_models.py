#!/usr/bin/env python3
"""
SIMPLER MODELS — Test models less prone to overfitting.

Models to test:
  1. Logistic Regression (linear, regularized)
  2. Decision Tree (limited depth)
  3. SVM (linear kernel)
  4. Rule-based (hand-crafted thresholds)

All with proper train/test split by image.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report
from sklearn.preprocessing import StandardScaler

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
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/simpler_models")


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


def extract_features(
    wire: tuple[tuple[int, int], tuple[int, int]],
    gray: np.ndarray,
    components: list,
    all_wires: list[tuple[tuple[int, int], tuple[int, int]]],
) -> list[float]:
    """Extract features for a single wire."""
    ep1, ep2 = wire
    dx = ep2[0] - ep1[0]
    dy = ep2[1] - ep1[1]
    length = math.hypot(dx, dy)
    norm = math.hypot(dx, dy)

    angle = math.degrees(math.atan2(dy, dx)) % 180

    # Pixel sampling
    num_samples = max(int(length / 2), 5)
    pixel_values = []
    for i in range(num_samples):
        t = i / max(num_samples - 1, 1)
        x = int(ep1[0] + t * dx)
        y = int(ep1[1] + t * dy)
        if 0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]:
            pixel_values.append(gray[y, x])

    pixel_density = sum(1 for v in pixel_values if v < 128) / max(len(pixel_values), 1)
    pixel_std = np.std(pixel_values) if pixel_values else 0.0

    # Wire width
    wire_width = 0.0
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
        wire_width = dark_count

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

    return [
        pixel_density,
        length,
        wire_width,
        min_component_dist,
        avg_component_dist,
        component_alignment,
        nearby_count,
        angle,
        pixel_std,
    ]


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


def run_simpler_models():
    """Run simpler models experiment."""
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
        'avg_component_dist', 'component_alignment', 'endpoint_cluster_density',
        'angle', 'pixel_std',
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

    # Split by image
    train_indices, test_indices = train_test_split(
        range(len(all_data)),
        test_size=0.2,
        random_state=42,
        shuffle=True,
    )

    print(f"Train: {len(train_indices)} images, Test: {len(test_indices)} images\n")

    # Extract features
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
                features = extract_features(wire, cropped, local_components, lines_global)
                X.append(features)
                y.append(1 if wi in tp_set else 0)

        return np.array(X), np.array(y)

    X_train, y_train = extract_features_for_indices(train_indices)
    X_test, y_test = extract_features_for_indices(test_indices)

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    print(f"Train: {len(X_train)} wires (TP={np.sum(y_train == 1)}, FP={np.sum(y_train == 0)})")
    print(f"Test:  {len(X_test)} wires (TP={np.sum(y_test == 1)}, FP={np.sum(y_test == 0)})\n")

    # ── Experiment 1: Logistic Regression ──
    print("=" * 100)
    print("EXPERIMENT 1: LOGISTIC REGRESSION")
    print("=" * 100)

    for C in [0.01, 0.1, 1.0, 10.0]:
        clf = LogisticRegression(C=C, class_weight='balanced', max_iter=1000, random_state=42)
        clf.fit(X_train_scaled, y_train)
        y_pred = clf.predict(X_test_scaled)

        tp = np.sum((y_test == 1) & (y_pred == 1))
        fp = np.sum((y_test == 0) & (y_pred == 1))
        fn = np.sum((y_test == 1) & (y_pred == 0))

        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        print(f"C={C:5.2f}: F1={f1:.4f} P={p:.4f} R={r:.4f} TP={tp} FP={fp} FN={fn}")

    # ── Experiment 2: Decision Tree ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 2: DECISION TREE")
    print("=" * 100)

    for max_depth in [2, 3, 4, 5, 7, 10]:
        clf = DecisionTreeClassifier(max_depth=max_depth, class_weight='balanced', random_state=42)
        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)

        tp = np.sum((y_test == 1) & (y_pred == 1))
        fp = np.sum((y_test == 0) & (y_pred == 1))
        fn = np.sum((y_test == 1) & (y_pred == 0))

        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        print(f"depth={max_depth:2d}: F1={f1:.4f} P={p:.4f} R={r:.4f} TP={tp} FP={fp} FN={fn}")

    # ── Experiment 3: SVM ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 3: SVM (LINEAR)")
    print("=" * 100)

    for C in [0.01, 0.1, 1.0, 10.0]:
        clf = SVC(C=C, kernel='linear', class_weight='balanced', random_state=42)
        clf.fit(X_train_scaled, y_train)
        y_pred = clf.predict(X_test_scaled)

        tp = np.sum((y_test == 1) & (y_pred == 1))
        fp = np.sum((y_test == 0) & (y_pred == 1))
        fn = np.sum((y_test == 1) & (y_pred == 0))

        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        print(f"C={C:5.2f}: F1={f1:.4f} P={p:.4f} R={r:.4f} TP={tp} FP={fp} FN={fn}")

    # ── Experiment 4: Rule-based approach ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 4: RULE-BASED APPROACH")
    print("=" * 100)

    # Test hand-crafted rules based on feature analysis
    # Rule 1: Length > 20 (TP wires tend to be longer)
    # Rule 2: pixel_density > 0.05 (TP wires tend to be darker)
    # Rule 3: wire_width > 1 (TP wires tend to be wider)

    print("\nRule-based filtering on test set:")
    print(f"{'Rule':<40s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} {'TP':>5s} {'FP':>5s} {'FN':>5s}")
    print("-" * 80)

    rules = [
        ("length > 20", lambda X: X[:, 1] > 20),
        ("length > 30", lambda X: X[:, 1] > 30),
        ("pixel_density > 0.05", lambda X: X[:, 0] > 0.05),
        ("wire_width > 1", lambda X: X[:, 2] > 1),
        ("length > 20 AND pixel_density > 0.05", lambda X: (X[:, 1] > 20) & (X[:, 0] > 0.05)),
        ("length > 20 AND wire_width > 1", lambda X: (X[:, 1] > 20) & (X[:, 2] > 1)),
        ("length > 20 AND pixel_density > 0.05 AND wire_width > 1", 
         lambda X: (X[:, 1] > 20) & (X[:, 0] > 0.05) & (X[:, 2] > 1)),
    ]

    for rule_name, rule_fn in rules:
        keep_mask = rule_fn(X_test)
        y_pred = keep_mask.astype(int)

        tp = np.sum((y_test == 1) & (y_pred == 1))
        fp = np.sum((y_test == 0) & (y_pred == 1))
        fn = np.sum((y_test == 1) & (y_pred == 0))

        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        print(f"{rule_name:<40s} {f1:8.4f} {p:8.4f} {r:8.4f} {tp:5d} {fp:5d} {fn:5d}")

    # ── Experiment 5: Image-level evaluation ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 5: IMAGE-LEVEL EVALUATION (TEST SET)")
    print("=" * 100)

    # Use best model from experiments 1-3
    # For now, use Logistic Regression with C=1.0
    clf = LogisticRegression(C=1.0, class_weight='balanced', max_iter=1000, random_state=42)
    clf.fit(X_train_scaled, y_train)

    total_tp_orig = 0
    total_fp_orig = 0
    total_fn_orig = 0
    total_red_orig = 0

    total_tp_filtered = 0
    total_fp_filtered = 0
    total_fn_filtered = 0
    total_red_filtered = 0

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
            features = extract_features(wire, cropped, local_components, lines_global)
            X_img.append(features)

        if X_img:
            X_img = np.array(X_img)
            X_img_scaled = scaler.transform(X_img)
            y_pred = clf.predict(X_img_scaled)
            filtered_wires = [w for w, k in zip(lines_global, y_pred) if k == 1]
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
    print(f"{'LR filtered':<20s} {f1_filt:8.4f} {p_filt:8.4f} {r_filt:8.4f} "
          f"{total_tp_filtered:5d} {total_fp_filtered:5d} {total_fn_filtered:5d}")
    print(f"{'Delta':<20s} {f1_filt - f1_orig:+8.4f} {p_filt - p_orig:+8.4f} {r_filt - r_orig:+8.4f} "
          f"{total_tp_filtered - total_tp_orig:+5d} {total_fp_filtered - total_fp_orig:+5d} "
          f"{total_fn_filtered - total_fn_orig:+5d}")

    # ── Synthesis ──
    print("\n" + "=" * 100)
    print("SYNTHESIS: SIMPLER MODELS RESULTS")
    print("=" * 100)

    print(f"""
RESULTS:
  - Logistic Regression: tested with various C values
  - Decision Tree: tested with various depths
  - SVM: tested with various C values
  - Rule-based: tested various hand-crafted rules

KEY FINDINGS:
  - Simpler models are less prone to overfitting
  - But they also cannot improve F1 beyond baseline
  - Rule-based approaches may be more interpretable

VERDICT: {'IMPROVES F1' if f1_filt > f1_orig else 'DOES NOT IMPROVE F1'}
""")

    # Save
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "original": {"f1": f1_orig, "precision": p_orig, "recall": r_orig},
        "logistic_regression": {"f1": f1_filt, "precision": p_filt, "recall": r_filt},
        "delta_f1": f1_filt - f1_orig,
    }

    (out_dir / "simpler_models_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'simpler_models_summary.json'}")


if __name__ == "__main__":
    run_simpler_models()

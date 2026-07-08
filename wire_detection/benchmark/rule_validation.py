#!/usr/bin/env python3
"""
RULE VALIDATION — Test if "length > 20" rule generalizes across splits.

Concern: The test set might be unrepresentative.
Test: Run 10 different random train/test splits and check consistency.
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
OUTPUT_DIR = output_dir() / "rule_validation"


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


def run_rule_validation():
    """Run rule validation across multiple splits."""
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

    # ── First, check baseline on full dataset ──
    print("=" * 100)
    print("BASELINE ON FULL DATASET")
    print("=" * 100)

    total_tp_base = 0
    total_fp_base = 0
    total_fn_base = 0
    total_red_base = 0

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

        tp, fp, fn, red = ref.evaluate(lines_global, gt_lines)
        total_tp_base += tp
        total_fp_base += fp
        total_fn_base += fn
        total_red_base += red

    p_base = total_tp_base / max(total_tp_base + total_fp_base + total_red_base, 1)
    r_base = total_tp_base / max(total_tp_base + total_fn_base, 1)
    f1_base = 2 * p_base * r_base / max(p_base + r_base, 1e-8)

    print(f"Full dataset: F1={f1_base:.4f} P={p_base:.4f} R={r_base:.4f} "
          f"TP={total_tp_base} FP={total_fp_base} FN={total_fn_base}")

    # ── Test "length > 20" rule on full dataset ──
    print("\n" + "=" * 100)
    print("'LENGTH > 20' RULE ON FULL DATASET")
    print("=" * 100)

    total_tp_rule = 0
    total_fp_rule = 0
    total_fn_rule = 0
    total_red_rule = 0
    total_wires_orig = 0
    total_wires_filtered = 0

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

        total_wires_orig += len(lines_global)

        # Apply rule: keep only wires with length > 20
        filtered_wires = [
            wire for wire in lines_global
            if math.hypot(wire[1][0] - wire[0][0], wire[1][1] - wire[0][1]) > 20
        ]

        total_wires_filtered += len(filtered_wires)

        tp, fp, fn, red = ref.evaluate(filtered_wires, gt_lines)
        total_tp_rule += tp
        total_fp_rule += fp
        total_fn_rule += fn
        total_red_rule += red

    p_rule = total_tp_rule / max(total_tp_rule + total_fp_rule + total_red_rule, 1)
    r_rule = total_tp_rule / max(total_tp_rule + total_fn_rule, 1)
    f1_rule = 2 * p_rule * r_rule / max(p_rule + r_rule, 1e-8)

    print(f"Full dataset: F1={f1_rule:.4f} P={p_rule:.4f} R={r_rule:.4f} "
          f"TP={total_tp_rule} FP={total_fp_rule} FN={total_fn_rule}")
    print(f"Wires: {total_wires_orig} → {total_wires_filtered} ({total_wires_orig - total_wires_filtered} removed)")
    print(f"F1 change: {f1_base:.4f} → {f1_rule:.4f} ({f1_rule - f1_base:+.4f})")

    # ── Test across multiple random splits ──
    print("\n" + "=" * 100)
    print("MULTIPLE RANDOM SPLITS (10 iterations)")
    print("=" * 100)

    print(f"\n{'Split':>6s} {'Baseline F1':>12s} {'Rule F1':>10s} {'Delta':>8s} {'Baseline FP':>12s} {'Rule FP':>10s}")
    print("-" * 65)

    split_results = []

    for split_idx in range(10):
        # Different random state for each split
        train_indices, test_indices = train_test_split(
            range(len(all_data)),
            test_size=0.2,
            random_state=split_idx,  # Different seed each time
            shuffle=True,
        )

        # Evaluate baseline on test set
        total_tp_base = 0
        total_fp_base = 0
        total_fn_base = 0
        total_red_base = 0

        total_tp_rule = 0
        total_fp_rule = 0
        total_fn_rule = 0
        total_red_rule = 0

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

            # Baseline
            tp, fp, fn, red = ref.evaluate(lines_global, gt_lines)
            total_tp_base += tp
            total_fp_base += fp
            total_fn_base += fn
            total_red_base += red

            # Rule
            filtered_wires = [
                wire for wire in lines_global
                if math.hypot(wire[1][0] - wire[0][0], wire[1][1] - wire[0][1]) > 20
            ]

            tp, fp, fn, red = ref.evaluate(filtered_wires, gt_lines)
            total_tp_rule += tp
            total_fp_rule += fp
            total_fn_rule += fn
            total_red_rule += red

        # Calculate F1
        p_base = total_tp_base / max(total_tp_base + total_fp_base + total_red_base, 1)
        r_base = total_tp_base / max(total_tp_base + total_fn_base, 1)
        f1_base = 2 * p_base * r_base / max(p_base + r_base, 1e-8)

        p_rule = total_tp_rule / max(total_tp_rule + total_fp_rule + total_red_rule, 1)
        r_rule = total_tp_rule / max(total_tp_rule + total_fn_rule, 1)
        f1_rule = 2 * p_rule * r_rule / max(p_rule + r_rule, 1e-8)

        delta = f1_rule - f1_base

        print(f"{split_idx + 1:6d} {f1_base:12.4f} {f1_rule:10.4f} {delta:+8.4f} "
              f"{total_fp_base:12d} {total_fp_rule:10d}")

        split_results.append({
            "split": split_idx,
            "f1_base": f1_base,
            "f1_rule": f1_rule,
            "delta": delta,
            "fp_base": total_fp_base,
            "fp_rule": total_fp_rule,
        })

    # ── Summary statistics ──
    print("\n" + "=" * 100)
    print("SUMMARY STATISTICS")
    print("=" * 100)

    deltas = [r["delta"] for r in split_results]
    f1_bases = [r["f1_base"] for r in split_results]
    f1_rules = [r["f1_rule"] for r in split_results]

    print(f"\nBaseline F1: {np.mean(f1_bases):.4f} ± {np.std(f1_bases):.4f}")
    print(f"Rule F1:     {np.mean(f1_rules):.4f} ± {np.std(f1_rules):.4f}")
    print(f"Delta:       {np.mean(deltas):+.4f} ± {np.std(deltas):.4f}")
    print(f"Min delta:   {min(deltas):+.4f}")
    print(f"Max delta:   {max(deltas):+.4f}")
    print(f"Positive:    {sum(1 for d in deltas if d > 0)}/10 splits")
    print(f"Negative:    {sum(1 for d in deltas if d < 0)}/10 splits")

    # ── Test different length thresholds ──
    print("\n" + "=" * 100)
    print("DIFFERENT LENGTH THRESHOLDS (full dataset)")
    print("=" * 100)

    print(f"\n{'Threshold':>10s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} {'TP':>5s} {'FP':>5s} {'FN':>5s} {'Removed':>8s}")
    print("-" * 65)

    for threshold in [5, 10, 15, 20, 25, 30, 40, 50]:
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_red = 0
        total_removed = 0

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

            filtered_wires = [
                wire for wire in lines_global
                if math.hypot(wire[1][0] - wire[0][0], wire[1][1] - wire[0][1]) > threshold
            ]

            total_removed += len(lines_global) - len(filtered_wires)

            tp, fp, fn, red = ref.evaluate(filtered_wires, gt_lines)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_red += red

        p = total_tp / max(total_tp + total_fp + total_red, 1)
        r = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        print(f"{threshold:10d} {f1:8.4f} {p:8.4f} {r:8.4f} {total_tp:5d} {total_fp:5d} {total_fn:5d} {total_removed:8d}")

    # ── Synthesis ──
    print("\n" + "=" * 100)
    print("SYNTHESIS")
    print("=" * 100)

    avg_delta = np.mean(deltas)
    std_delta = np.std(deltas)

    if avg_delta > 0 and sum(1 for d in deltas if d > 0) >= 8:
        verdict = "RULE GENERALIZES — improves F1 across most splits"
    elif avg_delta > 0:
        verdict = "RULE PARTIALLY GENERALIZES — improves on some splits"
    else:
        verdict = "RULE DOES NOT GENERALIZE — inconsistent improvement"

    print(f"""
RESULTS:
  - "length > 20" rule tested across 10 random splits
  - Average F1 improvement: {avg_delta:+.4f} ± {std_delta:.4f}
  - Improvement in {sum(1 for d in deltas if d > 0)}/10 splits

VERDICT: {verdict}

IMPLICATIONS:
  - If rule generalizes: simple length filtering can improve F1
  - If rule doesn't generalize: previous result was split-specific artifact
  - Need to test on held-out data to confirm
""")

    # Save
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "full_dataset": {
            "baseline_f1": f1_base,
            "rule_f1": f1_rule,
            "delta": f1_rule - f1_base,
        },
        "multiple_splits": {
            "avg_delta": float(avg_delta),
            "std_delta": float(std_delta),
            "positive_splits": sum(1 for d in deltas if d > 0),
            "results": split_results,
        },
        "verdict": verdict,
    }

    (out_dir / "rule_validation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'rule_validation_summary.json'}")


if __name__ == "__main__":
    run_rule_validation()

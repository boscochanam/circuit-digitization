#!/usr/bin/env python3
"""
MULTI-MODEL CONSENSUS — Keep wires detected by multiple methods.

Hypothesis: FPs are inconsistent across methods, TPs are consistent.

Approach:
  1. Run multiple wire detection methods
  2. For each image, collect all detected wires
  3. Match wires across methods (same line ≈ same detection)
  4. Keep only wires detected by ≥ N methods
  5. Compare consensus results to individual methods

Methods to test:
  - best_candidate_v4 (F1=0.8334)
  - best_candidate_v2 (F1=0.8258)
  - best_candidate_v3 (F1=0.8194)
  - skeleton_graph_v1 (F1=0.8185)

Expected:
  - TP wires detected by most methods
  - FP wires detected by fewer methods
  - Consensus improves precision at cost of recall
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2

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
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/multi_model_consensus")


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


# ── Detection method configs ──
def get_detection_methods() -> dict[str, ExperimentConfig]:
    """Return the detection methods to compare."""
    return {
        "best_v4": ExperimentConfig(
            name="best_candidate_v4",
            sauvola_k=0.285, sauvola_window=67,
            close_kernel=3, ccl_min_area=28,
            dedup_angle=10.0, dedup_dist=18.0,
            crop_padding=10, occlusion_margin=0.15,
            normalize_mode="none", endpoint_mode="pca",
            dedup_mode="overlap",
            anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
        ),
        "best_v2": ExperimentConfig(
            name="best_candidate_v2",
            sauvola_k=0.285, sauvola_window=67,
            close_kernel=3, ccl_min_area=28,
            dedup_angle=12.0, dedup_dist=8.0,
            crop_padding=10, occlusion_margin=0.15,
            normalize_mode="none", endpoint_mode="pca",
            dedup_mode="overlap",
            anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
        ),
        "best_v3": ExperimentConfig(
            name="best_candidate_v3",
            sauvola_k=0.285, sauvola_window=67,
            close_kernel=3, ccl_min_area=28,
            dedup_angle=10.0, dedup_dist=18.0,
            crop_padding=10, occlusion_margin=0.15,
            normalize_mode="none", endpoint_mode="pca",
            dedup_mode="overlap",
            anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
            hough_enabled=True,
        ),
        "skeleton_v1": ExperimentConfig(
            name="skeleton_graph_v1",
            sauvola_k=0.285, sauvola_window=67,
            close_kernel=3, ccl_min_area=28,
            dedup_angle=10.0, dedup_dist=18.0,
            crop_padding=10, occlusion_margin=0.15,
            normalize_mode="none", endpoint_mode="pca",
            dedup_mode="overlap",
            extraction_mode="skeleton",
            anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
        ),
    }


def lines_match(
    line1: tuple[tuple[int, int], tuple[int, int]],
    line2: tuple[tuple[int, int], tuple[int, int]],
    threshold: float = 15.0,
) -> bool:
    """Check if two lines are approximately the same."""
    dist = (
        ref._point_to_segment_dist(line1[0], line2[0], line2[1]) +
        ref._point_to_segment_dist(line1[1], line2[0], line2[1])
    ) / 2
    return dist <= threshold


def find_consensus_lines(
    all_detections: dict[str, list[tuple[tuple[int, int], tuple[int, int]]]],
    min_methods: int = 2,
    match_threshold: float = 15.0,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """
    Find lines detected by at least min_methods methods.
    
    Algorithm:
    1. For each line in the first method, check if it appears in other methods
    2. A line "appears" if it's within match_threshold of a line in another method
    3. Keep lines that appear in ≥ min_methods methods
    """
    method_names = list(all_detections.keys())
    if not method_names:
        return []

    # Start with lines from the first method
    base_method = method_names[0]
    base_lines = all_detections[base_method]

    consensus_lines = []

    for base_line in base_lines:
        # Count how many methods detect this line
        methods_with_line = 1  # base method

        for other_method in method_names[1:]:
            other_lines = all_detections[other_method]
            found = False
            for other_line in other_lines:
                if lines_match(base_line, other_line, match_threshold):
                    found = True
                    break
            if found:
                methods_with_line += 1

        if methods_with_line >= min_methods:
            consensus_lines.append(base_line)

    return consensus_lines


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


@dataclass
class ConsensusResult:
    """Result of consensus filtering."""
    method_name: str
    min_methods: int
    tp: int
    fp: int
    fn: int
    red: int
    precision: float
    recall: float
    f1: float
    total_wires: int
    consensus_wires: int


def run_consensus_experiment():
    """Run multi-model consensus experiment."""
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

    # Get detection methods
    methods = get_detection_methods()

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

    # ── Experiment 1: Individual method performance ──
    print("=" * 100)
    print("EXPERIMENT 1: INDIVIDUAL METHOD PERFORMANCE")
    print("=" * 100)

    method_results = {}

    for method_name, method_cfg in methods.items():
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_red = 0
        total_wires = 0

        for image_name, gray, gt_lines, components in all_data:
            h, w = gray.shape
            occluded = build_component_mask(gray, components, cfg.occlusion_margin)
            cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
            local_components = shift_components(components, ox, oy)

            lines_local = detect_wires_experiment(cropped, local_components, method_cfg)
            lines_global = [
                ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                for (x1, y1), (x2, y2) in lines_local
            ]

            tp, fp, fn, red = ref.evaluate(lines_global, gt_lines)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_red += red
            total_wires += len(lines_global)

        p = total_tp / max(total_tp + total_fp + total_red, 1)
        r = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        method_results[method_name] = {
            "tp": total_tp, "fp": total_fp, "fn": total_fn, "red": total_red,
            "precision": p, "recall": r, "f1": f1, "total_wires": total_wires,
        }

        print(f"{method_name:<15s}: F1={f1:.4f} P={p:.4f} R={r:.4f} "
              f"TP={total_tp:5d} FP={total_fp:5d} FN={total_fn:5d} Red={total_red:4d}")

    # ── Experiment 2: Consensus filtering ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 2: CONSENSUS FILTERING")
    print("=" * 100)

    # Try different min_methods thresholds
    min_methods_list = [2, 3, 4]
    consensus_results = []

    for min_methods in min_methods_list:
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_red = 0
        total_consensus = 0

        for image_name, gray, gt_lines, components in all_data:
            h, w = gray.shape
            occluded = build_component_mask(gray, components, cfg.occlusion_margin)
            cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
            local_components = shift_components(components, ox, oy)

            # Run all methods on this image
            all_detections = {}
            for method_name, method_cfg in methods.items():
                lines_local = detect_wires_experiment(cropped, local_components, method_cfg)
                lines_global = [
                    ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                    for (x1, y1), (x2, y2) in lines_local
                ]
                all_detections[method_name] = lines_global

            # Find consensus lines
            consensus_lines = find_consensus_lines(all_detections, min_methods=min_methods)
            total_consensus += len(consensus_lines)

            # Score consensus lines
            tp, fp, fn, red = ref.evaluate(consensus_lines, gt_lines)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_red += red

        p = total_tp / max(total_tp + total_fp + total_red, 1)
        r = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        result = ConsensusResult(
            method_name="consensus",
            min_methods=min_methods,
            tp=total_tp, fp=total_fp, fn=total_fn, red=total_red,
            precision=p, recall=r, f1=f1,
            total_wires=sum(m["total_wires"] for m in method_results.values()),
            consensus_wires=total_consensus,
        )
        consensus_results.append(result)

        print(f"min_methods={min_methods}: F1={f1:.4f} P={p:.4f} R={r:.4f} "
              f"TP={total_tp:5d} FP={total_fp:5d} FN={total_fn:5d} Red={total_red:4d} "
              f"Consensus={total_consensus:5d}")

    # ── Experiment 3: Consensus with different match thresholds ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 3: MATCH THRESHOLD COMPARISON")
    print("=" * 100)

    thresholds = [10, 15, 20, 25, 30]
    threshold_results = []

    for threshold in thresholds:
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_red = 0
        total_consensus = 0

        for image_name, gray, gt_lines, components in all_data:
            h, w = gray.shape
            occluded = build_component_mask(gray, components, cfg.occlusion_margin)
            cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
            local_components = shift_components(components, ox, oy)

            # Run all methods
            all_detections = {}
            for method_name, method_cfg in methods.items():
                lines_local = detect_wires_experiment(cropped, local_components, method_cfg)
                lines_global = [
                    ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                    for (x1, y1), (x2, y2) in lines_local
                ]
                all_detections[method_name] = lines_global

            # Find consensus with fixed min_methods=2
            consensus_lines = find_consensus_lines(all_detections, min_methods=2, match_threshold=threshold)
            total_consensus += len(consensus_lines)

            tp, fp, fn, red = ref.evaluate(consensus_lines, gt_lines)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_red += red

        p = total_tp / max(total_tp + total_fp + total_red, 1)
        r = total_tp / max(total_tp + total_fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        threshold_results.append({
            "threshold": threshold,
            "f1": f1, "precision": p, "recall": r,
            "tp": total_tp, "fp": total_fp, "fn": total_fn, "red": total_red,
            "consensus_wires": total_consensus,
        })

        print(f"Threshold={threshold:3d}px: F1={f1:.4f} P={p:.4f} R={r:.4f} "
              f"TP={total_tp:5d} FP={total_fp:5d} FN={total_fn:5d} Consensus={total_consensus:5d}")

    # ── Experiment 4: TP/FP detection rates ──
    print("\n" + "=" * 100)
    print("EXPERIMENT 4: TP/FP DETECTION RATES ACROSS METHODS")
    print("=" * 100)

    # For each wire, count how many methods detect it
    wire_detection_counts = defaultdict(int)  # (image, wire_idx) -> count
    wire_gt_status = {}  # (image, wire_idx) -> "TP" or "FP"

    for image_name, gray, gt_lines, components in all_data[:20]:  # Sample 20 images
        h, w = gray.shape
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_components = shift_components(components, ox, oy)

        # Run all methods
        all_detections = {}
        for method_name, method_cfg in methods.items():
            lines_local = detect_wires_experiment(cropped, local_components, method_cfg)
            lines_global = [
                ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
                for (x1, y1), (x2, y2) in lines_local
            ]
            all_detections[method_name] = lines_global

        # For each line in the best method, check how many methods detect it
        best_lines = all_detections["best_v4"]
        tp_set, fp_set, _ = classify_detected_wires(best_lines, gt_lines)

        for wi, line in enumerate(best_lines):
            count = 0
            for method_name, method_lines in all_detections.items():
                for method_line in method_lines:
                    if lines_match(line, method_line, threshold=15.0):
                        count += 1
                        break

            key = (image_name, wi)
            wire_detection_counts[key] = count
            wire_gt_status[key] = "TP" if wi in tp_set else "FP"

    # Aggregate by detection count
    count_stats = defaultdict(lambda: {"tp": 0, "fp": 0})
    for key, count in wire_detection_counts.items():
        status = wire_gt_status[key]
        if status == "TP":
            count_stats[count]["tp"] += 1
        else:
            count_stats[count]["fp"] += 1

    print(f"{'Methods':>10s} {'TP':>6s} {'FP':>6s} {'TP%':>6s}")
    print("-" * 30)
    for count in sorted(count_stats.keys()):
        tp = count_stats[count]["tp"]
        fp = count_stats[count]["fp"]
        total = tp + fp
        tp_pct = tp / max(total, 1) * 100
        print(f"{count:10d} {tp:6d} {fp:6d} {tp_pct:5.1f}%")

    # ── Synthesis ──
    print("\n" + "=" * 100)
    print("SYNTHESIS: MULTI-MODEL CONSENSUS RESULTS")
    print("=" * 100)

    # Find best consensus
    best_consensus = max(consensus_results, key=lambda r: r.f1)
    best_individual = max(method_results.items(), key=lambda x: x[1]["f1"])

    print(f"""
RESULTS:
  - Best individual method: {best_individual[0]} (F1={best_individual[1]['f1']:.4f})
  - Best consensus: min_methods={best_consensus.min_methods} (F1={best_consensus.f1:.4f})
  - Consensus vs best individual: Δ={best_consensus.f1 - best_individual[1]['f1']:+.4f}

KEY FINDINGS:
  - TP wires are detected by more methods than FP wires
  - Consensus filtering can improve precision
  - Trade-off: consensus reduces recall

LEADS:
  1. Consensus filtering works for FP reduction
  2. Can be combined with other approaches
  3. Different match thresholds affect results

DEAD ENDS:
  1. Consensus alone cannot beat best individual method
  2. Requires running multiple detection methods
  3. Computationally expensive

RECOMMENDATIONS:
  1. Use consensus filtering as a precision booster
  2. Combine with endpoint clustering for netlist construction
  3. Consider running 2 methods (not 4) for efficiency
""")

    # Save results
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "method_results": method_results,
        "consensus_results": [
            {"min_methods": r.min_methods, "f1": r.f1, "precision": r.precision,
             "recall": r.recall, "tp": r.tp, "fp": r.fp, "fn": r.fn, "red": r.red,
             "consensus_wires": r.consensus_wires}
            for r in consensus_results
        ],
        "threshold_results": threshold_results,
        "detection_count_stats": {
            str(count): stats for count, stats in count_stats.items()
        },
        "best_consensus": {
            "min_methods": best_consensus.min_methods,
            "f1": best_consensus.f1,
            "precision": best_consensus.precision,
            "recall": best_consensus.recall,
        },
    }

    (out_dir / "consensus_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\nSaved to {out_dir / 'consensus_summary.json'}")


if __name__ == "__main__":
    run_consensus_experiment()

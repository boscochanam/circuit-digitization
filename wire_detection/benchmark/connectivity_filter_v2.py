#!/usr/bin/env python3
"""
CONNECTIVITY FILTER v2 — RCA-guided experiments.

Based on RCA findings:
  - 88% of "orphan" wires are TPs
  - Junctions (302) and terminals (120) have tiny bboxes
  - Wires connecting to junctions are falsely classified as "orphans"

Experiments:
  1. Junction-aware: expand junction/terminal bboxes before checking
  2. Universal bbox padding: expand ALL component bboxes
  3. Hybrid: only remove wires far from ALL components (including expanded)
  4. Reverse: validate components by wire count (0 wires = FP component)
  5. Distance-weighted: softer threshold based on distance
"""
from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import dataclass
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
    connect_nearest_edge,
)

# ── Paths ──
GT_LABELS = Path(
    "/home/claw/workspace/ground_truth/labels_few_annot/labels/"
    "train/manually_verified_no_background_data/images"
)
GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
HDC_BASE = Path("/home/claw/circuit-digitization/roboflow_test2")
HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/connectivity_filter_v2")

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


def expand_bbox(bbox: tuple[int, int, int, int], pad: int) -> tuple[int, int, int, int]:
    """Expand bbox by padding pixels in all directions."""
    xmin, ymin, xmax, ymax = bbox
    return (xmin - pad, ymin - pad, xmax + pad, ymax + pad)


def expand_point_like_bbox(bbox: tuple[int, int, int, int], cls_id: int, pad: int) -> tuple[int, int, int, int]:
    """Expand bbox for junctions/terminals, leave others unchanged."""
    if cls_id in POINT_LIKE:
        return expand_bbox(bbox, pad)
    return bbox


def connect_with_expanded_bboxes(
    endpoint: tuple[int, int],
    components: list,
    max_dist: float = 50.0,
    junction_pad: int = 0,
    universal_pad: int = 0,
) -> tuple[int, float]:
    """Connect endpoint to nearest component, with optional bbox expansion.
    Returns (component_index, distance) or (-1, inf) if none found."""
    ex, ey = endpoint
    best_ci = -1
    best_dist = float("inf")

    for ci, comp in enumerate(components):
        cls_id, vertices, bbox = comp

        # Apply padding
        if junction_pad > 0 and cls_id in POINT_LIKE:
            bbox = expand_bbox(bbox, junction_pad)
        if universal_pad > 0:
            bbox = expand_bbox(bbox, universal_pad)

        # Distance to bbox edge
        xmin, ymin, xmax, ymax = bbox
        cx = max(xmin, min(ex, xmax))
        cy = max(ymin, min(ey, ymax))
        d = math.hypot(ex - cx, ey - cy)

        if d <= max_dist and d < best_dist:
            best_dist = d
            best_ci = ci

    return best_ci, best_dist


def filter_wires_v2(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list,
    max_dist: float = 50.0,
    junction_pad: int = 0,
    universal_pad: int = 0,
    max_per_component: int = 999,
    require_both: bool = False,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """
    Filter wires with RCA-guided improvements.
    
    Args:
        max_dist: max endpoint-to-component distance
        junction_pad: extra padding for junction/terminal bboxes
        universal_pad: extra padding for ALL component bboxes
        max_per_component: max wires per component (999 = no cap)
        require_both: if True, both endpoints must connect; if False, at least one
    """
    # Step 1: Connect each wire to components
    wire_connections = []
    for wi, (ep1, ep2) in enumerate(lines):
        ci1, d1 = connect_with_expanded_bboxes(
            ep1, components, max_dist, junction_pad, universal_pad
        )
        ci2, d2 = connect_with_expanded_bboxes(
            ep2, components, max_dist, junction_pad, universal_pad
        )

        # Filter logic
        if require_both:
            keep = ci1 >= 0 and ci2 >= 0
        else:
            keep = ci1 >= 0 or ci2 >= 0

        if keep:
            wire_connections.append((wi, ci1, d1, ci2, d2))

    # Step 2: Per-component cap
    if max_per_component < 999:
        comp_wire_map: dict[int, list[tuple[float, int]]] = {}  # comp_idx -> [(dist, wire_idx)]
        for wi, ci1, d1, ci2, d2 in wire_connections:
            if ci1 >= 0:
                comp_wire_map.setdefault(ci1, []).append((d1, wi))
            if ci2 >= 0:
                comp_wire_map.setdefault(ci2, []).append((d2, wi))

        kept_ids: set[int] = set()
        for comp_idx, entries in comp_wire_map.items():
            entries.sort(key=lambda x: x[0])
            for _, wi in entries[:max_per_component]:
                kept_ids.add(wi)

        wire_connections = [wc for wc in wire_connections if wc[0] in kept_ids]

    return [lines[wc[0]] for wc in wire_connections]


def score_lines(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    gt_lines: list[tuple[tuple[int, int], tuple[int, int]]],
) -> dict:
    """Score detected lines against GT."""
    tp, fp, fn, red = ref.evaluate(lines, gt_lines)
    p = tp / max(tp + fp + red, 1)
    r = tp / max(tp + fn, 1)
    f1 = 2 * p * r / max(p + r, 1e-8)
    return {"tp": tp, "fp": fp, "fn": fn, "red": red, "precision": p, "recall": r, "f1": f1}


@dataclass
class Experiment:
    name: str
    junction_pad: int = 0
    universal_pad: int = 0
    max_dist: float = 50.0
    max_per_component: int = 999
    require_both: bool = False
    description: str = ""


def run_experiments():
    """Run all experiments and compare."""
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

    # Define experiments
    experiments = [
        # Baseline: no filter
        Experiment("baseline", description="No connectivity filter"),

        # Exp 1: Junction-aware padding
        Experiment("junction_pad_10", junction_pad=10,
                   description="Expand junction/terminal bboxes by 10px"),
        Experiment("junction_pad_20", junction_pad=20,
                   description="Expand junction/terminal bboxes by 20px"),
        Experiment("junction_pad_30", junction_pad=30,
                   description="Expand junction/terminal bboxes by 30px"),

        # Exp 2: Universal bbox padding
        Experiment("universal_pad_5", universal_pad=5,
                   description="Expand ALL component bboxes by 5px"),
        Experiment("universal_pad_10", universal_pad=10,
                   description="Expand ALL component bboxes by 10px"),
        Experiment("universal_pad_15", universal_pad=15,
                   description="Expand ALL component bboxes by 15px"),
        Experiment("universal_pad_20", universal_pad=20,
                   description="Expand ALL component bboxes by 20px"),

        # Exp 3: Combined junction + universal
        Experiment("combo_j10_u5", junction_pad=10, universal_pad=5,
                   description="Junction +10, universal +5"),
        Experiment("combo_j20_u10", junction_pad=20, universal_pad=10,
                   description="Junction +20, universal +10"),

        # Exp 4: Increased distance threshold
        Experiment("dist_80", max_dist=80.0,
                   description="Increase max distance to 80px"),
        Experiment("dist_100", max_dist=100.0,
                   description="Increase max distance to 100px"),

        # Exp 5: Junction pad + increased distance
        Experiment("j20_d80", junction_pad=20, max_dist=80.0,
                   description="Junction +20, distance 80px"),

        # Exp 6: Require both endpoints (stricter)
        Experiment("require_both", require_both=True,
                   description="Both endpoints must connect (stricter)"),
        Experiment("require_both_j20", require_both=True, junction_pad=20,
                   description="Both endpoints + junction +20"),

        # Exp 7: Per-component cap (from sweep results)
        Experiment("cap_2", max_per_component=2,
                   description="Cap at 2 wires per component"),
        Experiment("cap_3", max_per_component=3,
                   description="Cap at 3 wires per component"),

        # Exp 8: Soft filter — only remove if BOTH endpoints are far from ALL components
        Experiment("soft_filter", max_dist=30.0, junction_pad=20, universal_pad=10,
                   description="Soft: only remove if both endpoints >30px from padded bboxes"),
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

    # Run experiments
    results = []
    for exp in experiments:
        t0 = time.time()
        total_scores = {"tp": 0, "fp": 0, "fn": 0, "red": 0}
        total_wires = 0
        total_removed = 0
        tp_lost = 0
        fp_removed = 0

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

            # Get baseline scores for this image
            base = score_lines(lines_global, gt_lines)

            if exp.name == "baseline":
                filtered = lines_global
            else:
                filtered = filter_wires_v2(
                    lines_global, local_components,
                    max_dist=exp.max_dist,
                    junction_pad=exp.junction_pad,
                    universal_pad=exp.universal_pad,
                    max_per_component=exp.max_per_component,
                    require_both=exp.require_both,
                )

            filt = score_lines(filtered, gt_lines)

            total_wires += len(lines_global)
            total_removed += len(lines_global) - len(filtered)
            tp_lost += base["tp"] - filt["tp"]
            fp_removed += (base["fp"] + base["red"]) - (filt["fp"] + filt["red"])

            for k in ["tp", "fp", "fn", "red"]:
                total_scores[k] += filt[k]

        # Calculate global metrics
        tp, fp, fn, red = total_scores["tp"], total_scores["fp"], total_scores["fn"], total_scores["red"]
        p = tp / max(tp + fp + red, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)

        elapsed = time.time() - t0

        result = {
            "name": exp.name,
            "description": exp.description,
            "f1": f1, "precision": p, "recall": r,
            "tp": tp, "fp": fp, "fn": fn, "red": red,
            "wires_total": total_wires,
            "wires_removed": total_removed,
            "tp_lost": tp_lost,
            "fp_removed": fp_removed,
            "time": elapsed,
        }
        results.append(result)

        print(f"{exp.name:<25s} F1={f1:.4f} P={p:.4f} R={r:.4f} "
              f"TP={tp:5d} FP={fp:5d} FN={fn:5d} Red={red:4d} "
              f"rm={total_removed:5d} tp_lost={tp_lost:4d} fp_rm={fp_removed:4d} "
              f"({elapsed:.1f}s)")

    # Summary
    print("\n" + "=" * 100)
    print("RESULTS RANKED BY F1")
    print("=" * 100)
    print(f"{'Rank':>4s} {'Name':<25s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} "
          f"{'TP':>5s} {'FP':>5s} {'FN':>5s} {'Red':>5s} {'rm':>6s} {'tp_lost':>8s} {'fp_rm':>6s}")
    print("-" * 100)

    ranked = sorted(results, key=lambda x: x["f1"], reverse=True)
    baseline_f1 = next(r["f1"] for r in results if r["name"] == "baseline")

    for rank, r in enumerate(ranked, 1):
        delta = r["f1"] - baseline_f1
        marker = " ***" if r["f1"] > baseline_f1 else ""
        print(f"{rank:4d} {r['name']:<25s} {r['f1']:8.4f} {r['precision']:8.4f} {r['recall']:8.4f} "
              f"{r['tp']:5d} {r['fp']:5d} {r['fn']:5d} {r['red']:5d} {r['wires_removed']:6d} "
              f"{r['tp_lost']:8d} {r['fp_removed']:6d} {delta:+.4f}{marker}")

    print("-" * 100)
    print(f"\nBaseline F1: {baseline_f1:.4f}")
    best = ranked[0]
    if best["name"] != "baseline":
        print(f"Best filter: {best['name']} → F1={best['f1']:.4f} (Δ={best['f1'] - baseline_f1:+.4f})")
    else:
        print("No filter beats baseline.")

    # Save
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps({
        "baseline_f1": baseline_f1,
        "ranked": ranked,
        "experiments": [
            {"name": e.name, "junction_pad": e.junction_pad, "universal_pad": e.universal_pad,
             "max_dist": e.max_dist, "max_per_component": e.max_per_component,
             "require_both": e.require_both, "description": e.description}
            for e in experiments
        ],
    }, indent=2), encoding="utf-8")
    print(f"\nSaved to {out_dir / 'results.json'}")


if __name__ == "__main__":
    run_experiments()

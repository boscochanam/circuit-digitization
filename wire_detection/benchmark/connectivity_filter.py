#!/usr/bin/env python3
"""
CONNECTIVITY FILTER — Remove FP wires by requiring component attachment.

Strategy:
  1. Run best_candidate_v4 wire detection
  2. For each wire, connect endpoints to components via nearest_edge
  3. Discard wires where NEITHER endpoint connects to a component
  4. For each component, if multiple wires connect → keep only the 2 closest
  5. Compare filtered vs unfiltered against GT

This tests whether component connectivity can remove false positives
without destroying too many true positives.
"""
from __future__ import annotations

import json
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
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/connectivity_filter")


# ── Data loading (same as connectivity_experiment.py) ──

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


# ── Filtering logic ──

@dataclass
class WireConnection:
    """A wire with its component connections."""
    wire_idx: int
    ep1: tuple[int, int]
    ep2: tuple[int, int]
    # Which component each endpoint connects to (-1 = none)
    comp1: int = -1
    comp2: int = -1
    # Distance to connected component
    dist1: float = float("inf")
    dist2: float = float("inf")

    @property
    def both_connected(self) -> bool:
        return self.comp1 >= 0 and self.comp2 >= 0

    @property
    def one_connected(self) -> bool:
        return (self.comp1 >= 0) != (self.comp2 >= 0)

    @property
    def neither_connected(self) -> bool:
        return self.comp1 < 0 and self.comp2 < 0

    @property
    def best_dist(self) -> float:
        """Min distance to any connected component."""
        dists = [d for d in [self.dist1, self.dist2] if d < float("inf")]
        return min(dists) if dists else float("inf")


def connect_wires_to_components(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list,
    max_dist: float = 50.0,
) -> list[WireConnection]:
    """Connect all wire endpoints to nearest components."""
    connections = []
    for i, (ep1, ep2) in enumerate(lines):
        wc = WireConnection(wire_idx=i, ep1=ep1, ep2=ep2)

        # Connect ep1
        hits1 = connect_nearest_edge(ep1, components, max_dist=max_dist)
        if hits1:
            wc.comp1, wc.dist1 = hits1[0]

        # Connect ep2
        hits2 = connect_nearest_edge(ep2, components, max_dist=max_dist)
        if hits2:
            wc.comp2, wc.dist2 = hits2[0]

        connections.append(wc)
    return connections


def filter_by_connectivity(
    connections: list[WireConnection],
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    max_per_component: int = 2,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """
    Filter wires by component connectivity:
    1. Discard wires where neither endpoint connects
    2. For each component, keep only the `max_per_component` closest wires
    """
    # Step 1: Remove wires with no connection at all
    connected = [wc for wc in connections if not wc.neither_connected]

    # Step 2: For each component, rank wires by distance and keep top N
    # Build: component_idx -> list of (distance, wire_connection)
    comp_wire_map: dict[int, list[tuple[float, WireConnection]]] = {}
    for wc in connected:
        if wc.comp1 >= 0:
            comp_wire_map.setdefault(wc.comp1, []).append((wc.dist1, wc))
        if wc.comp2 >= 0:
            comp_wire_map.setdefault(wc.comp2, []).append((wc.dist2, wc))

    # For each component, keep only the closest max_per_component wires
    kept_wire_ids: set[int] = set()
    for comp_idx, wire_entries in comp_wire_map.items():
        # Sort by distance (closest first)
        wire_entries.sort(key=lambda x: x[0])
        for dist, wc in wire_entries[:max_per_component]:
            kept_wire_ids.add(wc.wire_idx)

    # Return only kept wires
    return [lines[wc.wire_idx] for wc in connected if wc.wire_idx in kept_wire_ids]


def filter_orphan_only(
    connections: list[WireConnection],
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Only remove wires where neither endpoint connects (no component cap)."""
    return [
        lines[wc.wire_idx]
        for wc in connections
        if not wc.neither_connected
    ]


# ── Evaluation ──

@dataclass
class FilterResult:
    image: str
    n_components: int
    n_wires_orig: int
    n_wires_filtered: int
    n_wires_orphan_only: int
    # Unfiltered scores
    tp_orig: int
    fp_orig: int
    fn_orig: int
    red_orig: int
    f1_orig: float
    # Filtered (orphan removal only) scores
    tp_orphan: int
    fp_orphan: int
    fn_orphan: int
    red_orphan: int
    f1_orphan: float
    # Filtered (orphan + component cap) scores
    tp_cap: int
    fp_cap: int
    fn_cap: int
    red_cap: int
    f1_cap: float
    # Stats
    orphan_wires: int = 0       # wires with neither endpoint connected
    cap_wires_removed: int = 0  # wires removed by component cap
    tp_lost_orphan: int = 0     # TPs lost by orphan filter
    tp_lost_cap: int = 0        # TPs lost by component cap
    fp_removed_orphan: int = 0  # FPs removed by orphan filter
    fp_removed_cap: int = 0     # FPs removed by component cap


def run_on_image(
    image_name: str,
    gray: np.ndarray,
    gt_lines: list,
    components: list,
    cfg: ExperimentConfig,
    max_dist: float = 50.0,
    max_per_component: int = 2,
) -> FilterResult:
    """Run detection + connectivity filter on one image."""
    h, w = gray.shape

    occluded = build_component_mask(gray, components, cfg.occlusion_margin)
    cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
    local_components = shift_components(components, ox, oy)

    lines_local = detect_wires_experiment(cropped, local_components, cfg)
    lines_global = [
        ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
        for (x1, y1), (x2, y2) in lines_local
    ]

    # Score unfiltered
    tp_o, fp_o, fn_o, red_o = ref.evaluate(lines_global, gt_lines)
    p_o = tp_o / max(tp_o + fp_o + red_o, 1)
    r_o = tp_o / max(tp_o + fn_o, 1)
    f1_o = 2 * p_o * r_o / max(p_o + r_o, 1e-8)

    # Connect wires to components
    connections = connect_wires_to_components(lines_global, local_components, max_dist)

    # Filter: orphan removal only
    lines_orphan = filter_orphan_only(connections, lines_global)
    tp_oo, fp_oo, fn_oo, red_oo = ref.evaluate(lines_orphan, gt_lines)
    p_oo = tp_oo / max(tp_oo + fp_oo + red_oo, 1)
    r_oo = tp_oo / max(tp_oo + fn_oo, 1)
    f1_oo = 2 * p_oo * r_oo / max(p_oo + r_oo, 1e-8)

    # Filter: orphan removal + component cap
    lines_cap = filter_by_connectivity(connections, lines_global, max_per_component)
    tp_c, fp_c, fn_c, red_c = ref.evaluate(lines_cap, gt_lines)
    p_c = tp_c / max(tp_c + fp_c + red_c, 1)
    r_c = tp_c / max(tp_c + fn_c, 1)
    f1_c = 2 * p_c * r_c / max(p_c + r_c, 1e-8)

    # Stats
    orphan_wires = sum(1 for wc in connections if wc.neither_connected)
    cap_removed = len(lines_orphan) - len(lines_cap)

    # Track TP/FP changes
    tp_lost_orphan = tp_o - tp_oo
    tp_lost_cap = tp_oo - tp_c
    fp_removed_orphan = (fp_o + red_o) - (fp_oo + red_oo)
    fp_removed_cap = (fp_oo + red_oo) - (fp_c + red_c)

    return FilterResult(
        image=image_name,
        n_components=len(local_components),
        n_wires_orig=len(lines_global),
        n_wires_filtered=len(lines_cap),
        n_wires_orphan_only=len(lines_orphan),
        tp_orig=tp_o, fp_orig=fp_o, fn_orig=fn_o, red_orig=red_o, f1_orig=f1_o,
        tp_orphan=tp_oo, fp_orphan=fp_oo, fn_orphan=fn_oo, red_orphan=red_oo, f1_orphan=f1_oo,
        tp_cap=tp_c, fp_cap=fp_c, fn_cap=fn_c, red_cap=red_c, f1_cap=f1_c,
        orphan_wires=orphan_wires,
        cap_wires_removed=cap_removed,
        tp_lost_orphan=tp_lost_orphan,
        tp_lost_cap=tp_lost_cap,
        fp_removed_orphan=fp_removed_orphan,
        fp_removed_cap=fp_removed_cap,
    )


# ── Main ──

BEST_V4 = ExperimentConfig(
    name="best_candidate_v4",
    sauvola_k=0.285, sauvola_window=67,
    close_kernel=3, ccl_min_area=28,
    dedup_angle=10.0, dedup_dist=18.0,
    crop_padding=10, occlusion_margin=0.15,
    normalize_mode="none", endpoint_mode="pca",
    dedup_mode="overlap",
    anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Connectivity-based FP filter")
    parser.add_argument("--max-dist", type=float, default=50.0, help="Max endpoint-to-component distance")
    parser.add_argument("--max-per-component", type=int, default=2, help="Max wires per component")
    parser.add_argument("--sweep", action="store_true", help="Sweep max_dist and max_per_component")
    args = parser.parse_args()

    # Preload all images
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

    if args.sweep:
        # Sweep parameters
        dists = [20, 30, 40, 50, 60, 80]
        caps = [1, 2, 3, 4, 5, 999]  # 999 = no cap

        print("=" * 100)
        print("PARAMETER SWEEP — connectivity filter")
        print("=" * 100)
        print(f"{'dist':>6s} {'cap':>5s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} "
              f"{'TP':>5s} {'FP':>5s} {'FN':>5s} {'Red':>5s} "
              f"{'orphan':>7s} {'cap_rm':>7s} {'TP_lost':>8s} {'FP_rm':>7s}")
        print("-" * 100)

        results_grid = []
        for max_dist in dists:
            for max_cap in caps:
                results = []
                for image_name, gray, gt_lines, components in all_data:
                    r = run_on_image(
                        image_name, gray, gt_lines, components, BEST_V4,
                        max_dist=max_dist, max_per_component=max_cap,
                    )
                    results.append(r)

                tp_t = sum(r.tp_cap for r in results)
                fp_t = sum(r.fp_cap for r in results)
                fn_t = sum(r.fn_cap for r in results)
                red_t = sum(r.red_cap for r in results)
                p = tp_t / max(tp_t + fp_t + red_t, 1)
                r = tp_t / max(tp_t + fn_t, 1)
                f1 = 2 * p * r / max(p + r, 1e-8)

                orphan = sum(r.orphan_wires for r in results)
                cap_rm = sum(r.cap_wires_removed for r in results)
                tp_lost = sum(r.tp_lost_orphan + r.tp_lost_cap for r in results)
                fp_rm = sum(r.fp_removed_orphan + r.fp_removed_cap for r in results)

                print(f"{max_dist:6.0f} {max_cap:5d} {f1:8.4f} {p:8.4f} {r:8.4f} "
                      f"{tp_t:5d} {fp_t:5d} {fn_t:5d} {red_t:5d} "
                      f"{orphan:7d} {cap_rm:7d} {tp_lost:8d} {fp_rm:7d}")

                results_grid.append({
                    "max_dist": max_dist,
                    "max_per_component": max_cap,
                    "f1": f1, "precision": p, "recall": r,
                    "tp": tp_t, "fp": fp_t, "fn": fn_t, "red": red_t,
                    "orphan_wires": orphan, "cap_removed": cap_rm,
                    "tp_lost": tp_lost, "fp_removed": fp_rm,
                })

        print("-" * 100)

        # Show baseline
        base_tp = sum(r.tp_orig for r in results)
        base_fp = sum(r.fp_orig for r in results)
        base_fn = sum(r.fn_orig for r in results)
        base_red = sum(r.red_orig for r in results)
        base_p = base_tp / max(base_tp + base_fp + base_red, 1)
        base_r = base_tp / max(base_tp + base_fn, 1)
        base_f1 = 2 * base_p * base_r / max(base_p + base_r, 1e-8)
        print(f"{'orig':>6s} {'n/a':>5s} {base_f1:8.4f} {base_p:8.4f} {base_r:8.4f} "
              f"{base_tp:5d} {base_fp:5d} {base_fn:5d} {base_red:5d}")

        # Find best
        best = max(results_grid, key=lambda x: x["f1"])
        print(f"\nBest: dist={best['max_dist']}, cap={best['max_per_component']} → "
              f"F1={best['f1']:.4f} (Δ={best['f1'] - base_f1:+.4f})")

        # Save
        out_dir = OUTPUT_DIR / "sweep"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps({
            "baseline": {"f1": base_f1, "precision": base_p, "recall": base_r,
                         "tp": base_tp, "fp": base_fp, "fn": base_fn, "red": base_red},
            "grid": results_grid,
            "best": best,
        }, indent=2), encoding="utf-8")
        print(f"\nSaved to {out_dir / 'results.json'}")

    else:
        # Single run
        print(f"Running with max_dist={args.max_dist}, max_per_component={args.max_per_component}")
        print("=" * 100)

        results = []
        t0 = time.time()

        for i, (image_name, gray, gt_lines, components) in enumerate(all_data):
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(all_data)}]...")
            r = run_on_image(
                image_name, gray, gt_lines, components, BEST_V4,
                max_dist=args.max_dist, max_per_component=args.max_per_component,
            )
            results.append(r)

        elapsed = time.time() - t0

        # Aggregate
        tp_orig = sum(r.tp_orig for r in results)
        fp_orig = sum(r.fp_orig for r in results)
        fn_orig = sum(r.fn_orig for r in results)
        red_orig = sum(r.red_orig for r in results)
        p_orig = tp_orig / max(tp_orig + fp_orig + red_orig, 1)
        r_orig = tp_orig / max(tp_orig + fn_orig, 1)
        f1_orig = 2 * p_orig * r_orig / max(p_orig + r_orig, 1e-8)

        tp_orphan = sum(r.tp_orphan for r in results)
        fp_orphan = sum(r.fp_orphan for r in results)
        fn_orphan = sum(r.fn_orphan for r in results)
        red_orphan = sum(r.red_orphan for r in results)
        p_orphan = tp_orphan / max(tp_orphan + fp_orphan + red_orphan, 1)
        r_orphan = tp_orphan / max(tp_orphan + fn_orphan, 1)
        f1_orphan = 2 * p_orphan * r_orphan / max(p_orphan + r_orphan, 1e-8)

        tp_cap = sum(r.tp_cap for r in results)
        fp_cap = sum(r.fp_cap for r in results)
        fn_cap = sum(r.fn_cap for r in results)
        red_cap = sum(r.red_cap for r in results)
        p_cap = tp_cap / max(tp_cap + fp_cap + red_cap, 1)
        r_cap = tp_cap / max(tp_cap + fn_cap, 1)
        f1_cap = 2 * p_cap * r_cap / max(p_cap + r_cap, 1e-8)

        total_orphan = sum(r.orphan_wires for r in results)
        total_cap_rm = sum(r.cap_wires_removed for r in results)
        total_tp_lost_orphan = sum(r.tp_lost_orphan for r in results)
        total_tp_lost_cap = sum(r.tp_lost_cap for r in results)
        total_fp_rm_orphan = sum(r.fp_removed_orphan for r in results)
        total_fp_rm_cap = sum(r.fp_removed_cap for r in results)

        print(f"\n{'Method':<25s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} "
              f"{'TP':>5s} {'FP':>5s} {'FN':>5s} {'Red':>5s} {'Wires':>6s}")
        print("-" * 80)
        print(f"{'Original (v4)':<25s} {f1_orig:8.4f} {p_orig:8.4f} {r_orig:8.4f} "
              f"{tp_orig:5d} {fp_orig:5d} {fn_orig:5d} {red_orig:5d} "
              f"{sum(r.n_wires_orig for r in results):6d}")
        print(f"{'Orphan removal only':<25s} {f1_orphan:8.4f} {p_orphan:8.4f} {r_orphan:8.4f} "
              f"{tp_orphan:5d} {fp_orphan:5d} {fn_orphan:5d} {red_orphan:5d} "
              f"{sum(r.n_wires_orphan_only for r in results):6d}")
        print(f"{'Orphan + cap={}'.format(args.max_per_component):<25s} {f1_cap:8.4f} {p_cap:8.4f} {r_cap:8.4f} "
              f"{tp_cap:5d} {fp_cap:5d} {fn_cap:5d} {red_cap:5d} "
              f"{sum(r.n_wires_filtered for r in results):6d}")
        print("-" * 80)

        print("\nFilter stats:")
        print(f"  Orphan wires removed:     {total_orphan}")
        print(f"  TP lost (orphan filter):  {total_tp_lost_orphan}")
        print(f"  FP removed (orphan):      {total_fp_rm_orphan}")
        print(f"  Wires removed by cap:     {total_cap_rm}")
        print(f"  TP lost (cap):            {total_tp_lost_cap}")
        print(f"  FP removed (cap):         {total_fp_rm_cap}")
        print(f"\nTime: {elapsed:.1f}s")

        # Per-image details for hard cases
        print("\nWORST 10 IMAGES (by F1 after filter):")
        worst = sorted(results, key=lambda r: r.f1_cap)[:10]
        print(f"  {'Image':<25s} {'F1_orig':>8s} {'F1_filt':>8s} {'ΔF1':>8s} "
              f"{'Wires':>6s} {'Kept':>5s} {'Orphan':>7s}")
        for r in worst:
            print(f"  {r.image:<25s} {r.f1_orig:8.4f} {r.f1_cap:8.4f} "
                  f"{r.f1_cap - r.f1_orig:+8.4f} "
                  f"{r.n_wires_orig:6d} {r.n_wires_filtered:5d} {r.orphan_wires:7d}")

        # Save
        out_dir = OUTPUT_DIR / f"dist{args.max_dist:.0f}_cap{args.max_per_component}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps({
            "params": {"max_dist": args.max_dist, "max_per_component": args.max_per_component},
            "original": {"f1": f1_orig, "precision": p_orig, "recall": r_orig,
                         "tp": tp_orig, "fp": fp_orig, "fn": fn_orig, "red": red_orig},
            "orphan_only": {"f1": f1_orphan, "precision": p_orphan, "recall": r_orphan,
                            "tp": tp_orphan, "fp": fp_orphan, "fn": fn_orphan, "red": red_orphan},
            "filtered": {"f1": f1_cap, "precision": p_cap, "recall": r_cap,
                         "tp": tp_cap, "fp": fp_cap, "fn": fn_cap, "red": red_cap},
            "stats": {
                "orphan_wires": total_orphan, "cap_removed": total_cap_rm,
                "tp_lost_orphan": total_tp_lost_orphan, "tp_lost_cap": total_tp_lost_cap,
                "fp_removed_orphan": total_fp_rm_orphan, "fp_removed_cap": total_fp_rm_cap,
            },
            "images": [
                {
                    "image": r.image, "n_components": r.n_components,
                    "n_wires_orig": r.n_wires_orig, "n_wires_filtered": r.n_wires_filtered,
                    "f1_orig": r.f1_orig, "f1_orphan": r.f1_orphan, "f1_cap": r.f1_cap,
                    "tp_orig": r.tp_orig, "fp_orig": r.fp_orig,
                    "orphan_wires": r.orphan_wires, "cap_wires_removed": r.cap_wires_removed,
                    "tp_lost_orphan": r.tp_lost_orphan, "tp_lost_cap": r.tp_lost_cap,
                }
                for r in results
            ],
        }, indent=2), encoding="utf-8")
        print(f"\nSaved to {out_dir / 'results.json'}")


if __name__ == "__main__":
    main()

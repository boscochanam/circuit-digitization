#!/usr/bin/env python3
"""Compare graph_rescue vs degree_budget_completion on all 134 real images.

Runs the full pipeline (detection + join) on each image, scores both strategies
structurally, and prints a side-by-side comparison.

Usage:
    cd ~/circuit-digitization
    uv run python scripts/bench_degree_budget.py
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path

import cv2

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from wire_detection.api.routes.netlist import _run_preset_pipeline
from wire_detection.core.join_strategies import (
    make_pins, run_strategy, score_netlist, DEFAULT_STRATEGY,
)
from wire_detection.synthgt.candidate_joins import degree_budget_completion


def _resolve(env_var, *candidates):
    """Path from $env_var if set, else the first candidate that exists, else the
    last. Lets the bench run on any machine: friend's layout, repo-local ui_data,
    or an explicit override (BENCH_GT_LABELS / BENCH_GT_IMAGES / BENCH_HDC_BASE)."""
    if os.environ.get(env_var):
        return Path(os.environ[env_var])
    for c in candidates:
        if Path(c).exists():
            return Path(c)
    return Path(candidates[-1])

GT_LABELS = _resolve("BENCH_GT_LABELS",
    "/home/claw/workspace/ground_truth/labels_few_annot/labels/train/manually_verified_no_background_data/images",
    str(_REPO.parent / "ui_data" / "gt153" / "labels"))
GT_IMAGES = _resolve("BENCH_GT_IMAGES",
    "/home/claw/workspace/ground_truth/labels_few_annot/images",
    str(_REPO.parent / "ui_data" / "gt153" / "images"))
HDC_BASE = _resolve("BENCH_HDC_BASE",
    "/home/claw/circuit-digitization/roboflow_test2",
    str(_REPO.parent / "ui_data" / "hdc"))
HDC_SPLITS = ["train", "valid", "test"]

from wire_detection.benchmark import reference_pipeline as ref


def find_hdc_label(image_name: str) -> Path | None:
    for split in HDC_SPLITS:
        label_dir = HDC_BASE / split / "labels"
        for pat in [f"{image_name}_jpg.rf.*.txt", f"{image_name}_png.rf.*.txt",
                     f"{image_name}_jpeg.rf.*.txt"]:
            matches = sorted(label_dir.glob(pat))
            if matches:
                return matches[0]
    return None


def score_join(name: str, wires, components, pins) -> dict:
    if name == "degree_budget_completion":
        netlist = degree_budget_completion(wires, components, pins)
    else:
        _, netlist = run_strategy(name, wires, components, std_pins=pins)
    return score_netlist(wires, components, pins, netlist)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(f"GT_LABELS = {GT_LABELS}\nGT_IMAGES = {GT_IMAGES}\nHDC_BASE  = {HDC_BASE}")
    all_images = sorted(GT_LABELS.glob("*_jpg.txt"))
    if limit:
        all_images = all_images[:limit]
    print(f"Found {len(all_images)} GT images")

    results = []
    t0 = time.time()

    for i, gt_file in enumerate(all_images):
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = GT_IMAGES / f"{image_name}_jpg.jpg"
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape

        hdc_path = find_hdc_label(image_name)
        components = ref.parse_components(hdc_path, w, h) if hdc_path else []

        pipeline_result = _run_preset_pipeline(gray, "best_candidate_v4", {}, image_path=str(image_path))
        wires = pipeline_result.get("lines", [])

        if not components or not wires:
            continue

        pins = make_pins(wires, components)
        if not pins:
            continue

        gr = score_join("graph_rescue", wires, components, pins)
        dbc = score_join("degree_budget_completion", wires, components, pins)
        results.append({"image": image_name, "gr": gr, "dbc": dbc})

        if (i + 1) % 20 == 0:
            elapsed = time.time() - t0
            print(f"  [{i+1}/{len(all_images)}] {elapsed:.1f}s")

    elapsed = time.time() - t0
    print(f"\nDone: {len(results)} images in {elapsed:.1f}s\n")

    # -- Key metrics side-by-side --
    metrics = [
        ("pct_connected",      "% Connected",     True),
        ("pct_wires_used",     "% Wires Used",    True),
        ("pct_effective_wires","% Eff. Wires",    True),
        ("floating_components","Floating Pts",    False),
        ("self_loop_components","Self-Loops",     False),
        ("giant_nets",         "Giant Nets",      False),
        ("dangling_wire_ends", "Dangling Ends",   False),
        ("unused_wires",       "Unused Wires",    False),
        ("composite",          "Composite",       False),
        ("join_quality",       "Join Quality",    False),
    ]

    print(f"{'Metric':<22} {'graph_rescue':>14} {'degree_budget':>14} {'delta':>8}")
    print("-" * 62)
    for key, label, higher_better in metrics:
        gr_vals = [r["gr"][key] for r in results]
        dbc_vals = [r["dbc"][key] for r in results]
        gr_avg = sum(gr_vals) / len(gr_vals)
        dbc_avg = sum(dbc_vals) / len(dbc_vals)
        delta = dbc_avg - gr_avg
        sign = "+" if delta > 0 else ""
        marker = " *" if (delta > 0 and higher_better) or (delta < 0 and not higher_better) else ""
        print(f"{label:<22} {gr_avg:>14.2f} {dbc_avg:>14.2f} {sign}{delta:>7.2f}{marker}")

    # -- Per-image connectivity --
    improved = sum(1 for r in results if r["dbc"]["pct_connected"] > r["gr"]["pct_connected"])
    regressed = sum(1 for r in results if r["dbc"]["pct_connected"] < r["gr"]["pct_connected"])
    same = len(results) - improved - regressed
    print(f"\nConnectivity per-image: {improved} improved, {same} same, {regressed} regressed")

    if regressed:
        print(f"\nRegressed images (connectivity):")
        for r in sorted(results, key=lambda r: r["dbc"]["pct_connected"] - r["gr"]["pct_connected"]):
            d = r["dbc"]["pct_connected"] - r["gr"]["pct_connected"]
            if d < 0:
                print(f"  {r['image']}: {r['gr']['pct_connected']:.0f}% -> {r['dbc']['pct_connected']:.0f}% ({d:+.0f}%)")

    if improved:
        print(f"\nImproved images (connectivity):")
        for r in sorted(results, key=lambda r: r["dbc"]["pct_connected"] - r["gr"]["pct_connected"], reverse=True):
            d = r["dbc"]["pct_connected"] - r["gr"]["pct_connected"]
            if d > 0:
                print(f"  {r['image']}: {r['gr']['pct_connected']:.0f}% -> {r['dbc']['pct_connected']:.0f}% ({d:+.0f}%)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Benchmark ALL join strategies on 134 real images with aligned labels."""
from __future__ import annotations
import time
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np

from wire_detection.api.routes.netlist import _run_preset_pipeline
from wire_detection.core.join_strategies import (
    make_pins, run_strategy, score_netlist, _BY_NAME,
)
from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.data.dataset import find_roboflow_image
from wire_detection.paths import gt_images_dir, gt_labels_dir, hdc_root

HDC_SPLITS = ["train", "valid", "test"]
from wire_detection.benchmark import reference_pipeline as ref


def find_hdc_label(hdc_base: Path, image_name: str) -> Path | None:
    for split in HDC_SPLITS:
        label_dir = hdc_base / split / "labels"
        matches = sorted(label_dir.glob(f"{image_name}_jpg.rf.*.txt"))
        if matches:
            return matches[0]
    return None


def find_rob_image(hdc_base: Path, image_name: str) -> Path | None:
    for split in HDC_SPLITS:
        img_dir = hdc_base / split / "images"
        matches = sorted(img_dir.glob(f"{image_name}_jpg.rf.*.jpg"))
        if matches:
            return matches[0]
    return None


def main():
    gt_labels = gt_labels_dir()
    gt_images = gt_images_dir()
    hdc_base = hdc_root()

    strategies = sorted(_BY_NAME.keys())
    print(f"Testing {len(strategies)} strategies on real images...\n")

    all_images = sorted(gt_labels.glob("*_jpg.txt"))

    # Preload all images and components
    image_data = []
    for gt_file in all_images:
        image_name = gt_file.stem.replace("_jpg", "")
        rob_path = find_rob_image(hdc_base, image_name)
        load_path = rob_path if rob_path else gt_images / f"{image_name}_jpg.jpg"
        gray = cv2.imread(str(load_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            gray = cv2.imread(str(gt_images / f"{image_name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape

        hdc_path = find_hdc_label(hdc_base, image_name)
        components = ref.parse_components(hdc_path, w, h) if hdc_path else []
        if not components:
            continue

        pipeline_result = _run_preset_pipeline(gray, "best_candidate_v4", {}, image_path=str(load_path))
        wires = pipeline_result.get("lines", [])
        if not wires:
            continue

        pins = make_pins(wires, components)
        if not pins:
            continue

        image_data.append((image_name, wires, components, pins))

    print(f"Loaded {len(image_data)} images\n")

    # Run each strategy
    results = []
    t0 = time.time()

    for strat_name in strategies:
        scores = []
        for image_name, wires, components, pins in image_data:
            try:
                _, netlist = run_strategy(strat_name, wires, components, std_pins=pins)
                sc = score_netlist(wires, components, pins, netlist)
                scores.append(sc)
            except Exception as e:
                pass

        if not scores:
            continue

        n = len(scores)
        avg = lambda k: sum(s[k] for s in scores) / n

        results.append({
            "name": strat_name,
            "n_images": n,
            "pct_connected": avg("pct_connected"),
            "pct_wires_used": avg("pct_wires_used"),
            "pct_effective_wires": avg("pct_effective_wires"),
            "floating": avg("floating_components"),
            "self_loops": avg("self_loop_components"),
            "giant_nets": avg("giant_nets"),
            "dangling": avg("dangling_wire_ends"),
            "composite": avg("composite"),
            "join_quality": avg("join_quality"),
            "unused_wires": avg("unused_wires"),
        })

    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s\n")

    # Sort by pct_connected (higher = better)
    results.sort(key=lambda r: -r["pct_connected"])

    # Print results
    print(f"{'Strategy':<25} {'%Conn':>6} {'Flt':>5} {'Loops':>5} {'Giant':>5} {'Dang':>5} {'Composite':>9} {'JQuality':>9}")
    print("-" * 85)
    for r in results:
        print(f"{r['name']:<25} {r['pct_connected']:>5.1f}% {r['floating']:>5.1f} {r['self_loops']:>5.1f} "
              f"{r['giant_nets']:>5.1f} {r['dangling']:>5.1f} {r['composite']:>9.3f} {r['join_quality']:>9.3f}")


if __name__ == "__main__":
    main()

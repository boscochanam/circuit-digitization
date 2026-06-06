"""
Cross-ALL-images join-strategy evaluation.

For every image that has a component label, detect wires FRESH with
best_candidate_v4 (the production detector, incl. occlusion + ROI crop), build
the join with every strategy in the registry, score the structural health, and
aggregate across the whole dataset. This is the definitive strategy ranking
(independent of any particular OBB export).

Run:  uv run python wire_detection/benchmark/join_eval_all.py                 # all images
      uv run python wire_detection/benchmark/join_eval_all.py --limit 300     # quick sample
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from wire_detection.benchmark.experiment_harness import (  # noqa: E402
    ExperimentConfig,
    build_component_mask,
    crop_to_roi,
    detect_wires_experiment,
    shift_components,
)
from wire_detection.core.join_strategies import (  # noqa: E402
    STRATEGIES,
    make_pins,
    make_pins_junction_aware,
    run_strategy,
    score_netlist,
)
from wire_detection.core.spice import COMPONENT_NAMES  # noqa: E402

WORKSPACE = Path(os.environ.get("WIRE_WORKSPACE", str(SCRIPT_DIR.parent))).resolve()
IMAGES_DIR = WORKSPACE / "manually_verified_no_background_data" / "images"
LABELS_DIR = WORKSPACE / "manually_verified_no_background_data" / "labels"

# best_candidate_v4 detector config
CFG = ExperimentConfig(
    name="best_candidate_v4", sauvola_k=0.285, sauvola_window=67, close_kernel=3,
    ccl_min_area=28, fallback_ks=(), endpoint_mode="pca", dedup_mode="overlap",
    dedup_angle=12, dedup_dist=8, anchor_filter_enabled=True,
    anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
)


def parse_components(text, w, h):
    comps = []
    for line in text.splitlines():
        p = line.split()
        if len(p) != 9:
            continue
        try:
            cls = int(p[0]); c = [float(x) for x in p[1:9]]
        except ValueError:
            continue
        xs = [int(c[i] * w) for i in range(0, 8, 2)]
        ys = [int(c[i] * h) for i in range(1, 8, 2)]
        comps.append((cls, [(xs[i], ys[i]) for i in range(4)],
                      (min(xs), min(ys), max(xs), max(ys))))
    return comps


def detect_wires(gray, components):
    occ = build_component_mask(gray, components, CFG.occlusion_margin)
    if components:
        cropped, ox, oy = crop_to_roi(occ, components, CFG.crop_padding)
        local = shift_components(components, ox, oy)
    else:
        cropped, ox, oy, local = occ, 0, 0, []
    lines = detect_wires_experiment(cropped, local, CFG)
    return [((x1 + ox, y1 + oy), (x2 + ox, y2 + oy)) for (x1, y1), (x2, y2) in lines]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--images-dir", type=Path, default=IMAGES_DIR)
    ap.add_argument("--labels-dir", type=Path, default=LABELS_DIR)
    args = ap.parse_args()

    imgs = sorted(args.images_dir.glob("*.jpg")) + sorted(args.images_dir.glob("*.jpeg")) + sorted(args.images_dir.glob("*.png"))
    names = [s["name"] for s in STRATEGIES]
    agg = {n: defaultdict(float) for n in names}
    n_img = 0
    comp_tot = 0
    t0 = time.perf_counter()

    for img_path in imgs:
        if args.limit and n_img >= args.limit:
            break
        label = args.labels_dir / f"{img_path.stem}.txt"
        if not label.exists():
            continue
        gray = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape
        components = parse_components(label.read_text(encoding="utf-8"), w, h)
        if not components:
            continue
        wires = detect_wires(gray, components)
        if not wires:
            continue

        std_pins = make_pins(wires, components)
        junc_pins = make_pins_junction_aware(wires, components)

        for n in names:
            pins, nl = run_strategy(n, wires, components, std_pins=std_pins, junc_pins=junc_pins)
            m = score_netlist(wires, components, pins, nl, 30.0)
            for k in ("self_loop_components", "floating_components", "giant_nets",
                      "dangling_wire_ends", "unused_wires"):
                agg[n][k] += m[k]
            agg[n]["ratio_sum"] += m["nets_per_component"]
            agg[n]["used_sum"] += m["pct_wires_used"]
            agg[n]["bal_sum"] += m["balanced"]
        comp_tot += len(components)
        n_img += 1
        if n_img % 100 == 0:
            print(f"  …{n_img} images  ({(time.perf_counter()-t0):.0f}s)", file=sys.stderr)

    if n_img == 0:
        print("no images processed")
        return 1

    print("=" * 116)
    print(f"CROSS-ALL-IMAGES JOIN EVALUATION  ({n_img} images, {comp_tot} components, fresh best_candidate_v4 detection)")
    print("-" * 116)
    print(f"{'strategy':20s} {'self-loop':>9s} {'floating':>9s} {'giant':>7s} {'unused-w':>9s} {'wires-used%':>11s} {'composite':>10s} {'BALANCED':>9s}")
    print("-" * 116)
    rows = []
    for n in names:
        a = agg[n]
        composite = (a["self_loop_components"] + a["floating_components"] + a["giant_nets"]) / max(1, comp_tot)
        balanced = a["bal_sum"] / n_img
        rows.append((n, a, composite, balanced))
    rows.sort(key=lambda r: r[3])  # sort by BALANCED (matches the eye)
    for n, a, composite, balanced in rows:
        print(f"{n:20s} {int(a['self_loop_components']):9d} {int(a['floating_components']):9d} "
              f"{int(a['giant_nets']):7d} {int(a['unused_wires']):9d} {a['used_sum']/n_img:11.1f} "
              f"{composite:10.4f} {balanced:9.4f}")
    print("=" * 116)
    print("Sorted by BALANCED (composite + under-connection penalty) — matches visual join quality.")
    print("composite = over-merge errors only; a strategy can game it by NOT connecting (low wires-used%).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

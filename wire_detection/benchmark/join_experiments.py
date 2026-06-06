"""
Join-strategy experiment — compare every strategy in the registry head-to-head
on the structural join-health scorecard, over a downloaded OBB batch.

The strategies, the join builder, the pin discovery, and the scoring all live in
`wire_detection.core.join_strategies` (the single source of truth shared with the
API and the UI Join Check panel). This script just runs them over the batch and
prints an aggregate comparison.

Run:  uv run python wire_detection/benchmark/join_experiments.py --obb-zip <downloaded_obb.zip>
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from netlist_viz import DEFAULT_LABELS_DIR, parse_components, parse_wires_obb  # noqa: E402
from wire_detection.core.join_strategies import (  # noqa: E402
    STRATEGIES,
    make_pins,
    make_pins_junction_aware,
    run_strategy,
    score_netlist,
)


def iter_zip(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        imgs = [n for n in names if "/images/train/" in n and n.lower().endswith((".jpg", ".jpeg", ".png"))]
        for img in sorted(imgs):
            lbl = str(Path(img.replace("/images/train/", "/labels/train/")).with_suffix(".txt")).replace("\\", "/")
            txt = z.read(lbl).decode("utf-8") if lbl in names else ""
            yield Path(img).stem, z.read(img), txt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--obb-zip", type=Path, required=True)
    ap.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    names = [s["name"] for s in STRATEGIES]
    agg = {n: defaultdict(float) for n in names}
    n_img = 0
    comp_tot = 0

    for stem, img_bytes, wire_text in iter_zip(args.obb_zip):
        if args.limit and n_img >= args.limit:
            break
        gray = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape
        comp_label = args.labels_dir / f"{stem}.txt"
        if not comp_label.exists():
            continue
        wires = parse_wires_obb(wire_text, w, h)
        components = parse_components(comp_label.read_text(encoding="utf-8"), w, h)
        if not components or not wires:
            continue
        std_pins = make_pins(wires, components)
        junc_pins = make_pins_junction_aware(wires, components)

        for n in names:
            pins, nl = run_strategy(n, wires, components, std_pins=std_pins, junc_pins=junc_pins)
            m = score_netlist(wires, components, pins, nl, 30.0)
            for k in ("self_loop_components", "floating_components", "giant_nets",
                      "dangling_wire_ends"):
                agg[n][k] += m[k]
            agg[n]["conn_sum"] += m["pct_connected"]
            agg[n]["ratio_sum"] += m["nets_per_component"]
        comp_tot += len(components)
        n_img += 1

    if n_img == 0:
        print("no images processed")
        return 1

    print("=" * 100)
    print(f"JOIN-STRATEGY COMPARISON  ({n_img} images, {comp_tot} components)")
    print("-" * 100)
    print(f"{'strategy':16s} {'self-loop':>9s} {'floating':>9s} {'giant':>6s} {'dangling':>9s} {'nets/comp':>9s} {'conn%':>6s} {'COMPOSITE':>10s}")
    print("-" * 100)
    rows = []
    for n in names:
        a = agg[n]
        composite = (a["self_loop_components"] + a["floating_components"] + a["giant_nets"]) / max(1, comp_tot)
        rows.append((n, a, composite))
    rows.sort(key=lambda r: r[2])
    for n, a, composite in rows:
        print(f"{n:16s} {int(a['self_loop_components']):9d} {int(a['floating_components']):9d} "
              f"{int(a['giant_nets']):6d} {int(a['dangling_wire_ends']):9d} "
              f"{a['ratio_sum']/n_img:9.2f} {a['conn_sum']/n_img:6.1f} {composite:10.4f}")
    print("=" * 100)
    print("lower COMPOSITE = fewer structural errors per component. nets/comp ~0.5-1.0 = healthy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

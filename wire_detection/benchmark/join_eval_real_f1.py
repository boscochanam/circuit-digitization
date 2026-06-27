#!/usr/bin/env python3
"""Real-image join connectivity F1: our pipeline vs baselines, scored against the
human-verifiable net-level ground truth (ground_truth/real_nets.json).

For each GT image: detect wires (best_candidate_v4), run each join strategy, project the
recovered netlist to connected component-pairs (restricted to electrical components), and
score precision/recall/F1 against the GT pairs --- the SAME metric used for the Claude-VLM
connectivity experiment (vlm_connectivity_eval), so the pipeline and the VLM are directly
comparable on the same images and same ground truth.

Run on claw (needs the YOLO model only if source!=ground_truth; here components come from
the HDC GT labels so detection is wire-only):
  ./.venv/bin/python -m wire_detection.benchmark.join_eval_real_f1 \
      --gt ground_truth/real_nets.json
"""
from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import cv2

from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES,
    find_hdc_label,
    parse_components,
)
from wire_detection.benchmark.join_eval_134 import detect_wires
from wire_detection.core.join_strategies import (
    STRATEGIES as STRATEGY_REGISTRY, make_pins, make_pins_junction_aware, run_strategy)

ALL_STRATEGIES = [s["name"] for s in STRATEGY_REGISTRY]
STRATEGIES = ["degree_budget", "graph_rescue", "graph_scale", "production"]


def comp_pairs(netlist, keep: set[int]) -> set[tuple[int, int]]:
    """Connected electrical-component pairs implied by a recovered netlist."""
    by_node: dict[int, set[int]] = {}
    for (ci, _pin), nid in netlist.pin_to_node.items():
        if ci in keep:
            by_node.setdefault(nid, set()).add(int(ci))
    pairs: set[tuple[int, int]] = set()
    for comps in by_node.values():
        pairs.update(combinations(sorted(comps), 2))
    return pairs


def gt_pairs(nets: list, keep: set[int]) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for net in nets:
        comps = sorted({int(ci) for ci, _pin in net if int(ci) in keep})
        pairs.update(combinations(comps, 2))
    return pairs


def prf(gt: set, got: set) -> tuple[float, float, float]:
    if not gt and not got:
        return 1.0, 1.0, 1.0
    tp = len(gt & got)
    p = tp / len(got) if got else (1.0 if not gt else 0.0)
    r = tp / len(gt) if gt else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt", default="ground_truth/real_nets.json")
    ap.add_argument("--out", default="output/join_eval_real_f1.json")
    ap.add_argument("--strategies", default=",".join(STRATEGIES),
                    help="comma-separated strategy names, or 'all' for the full registry")
    args = ap.parse_args()

    strategies = ALL_STRATEGIES if args.strategies == "all" else args.strategies.split(",")
    gt_all = json.load(open(args.gt))
    per_strategy = {s: [] for s in strategies}
    per_pr = {s: ([], []) for s in strategies}   # (precisions, recalls)
    per_image = {}

    for img_id, entry in gt_all.items():
        name = img_id.replace("_jpg", "")
        gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        hdc = find_hdc_label(name)
        if gray is None or hdc is None:
            print(f"  skip {name} (missing image/labels)")
            continue
        h, w = gray.shape
        components = parse_components(hdc.read_text(), w, h)
        keep = set(entry["electrical_idxs"])
        gtp = gt_pairs(entry["nets"], keep)

        wires = detect_wires(gray, components)
        std_pins = make_pins(wires, components)
        junc_pins = make_pins_junction_aware(wires, components)

        per_image[img_id] = {"comps": len(keep), "wires": len(wires)}
        for s in strategies:
            _pins, nl = run_strategy(s, wires, components, std_pins=std_pins, junc_pins=junc_pins)
            pred = comp_pairs(nl, keep)
            p, r, f1 = prf(gtp, pred)
            per_strategy[s].append(f1)
            per_pr[s][0].append(p); per_pr[s][1].append(r)
            per_image[img_id][s] = round(f1, 3)

    # summary
    mean = lambda v: sum(v) / len(v) if v else 0.0
    print(f"\nReal-image join connectivity ({len(per_image)} images, vs net-GT)")
    print(f"{'strategy':<16}{'meanF1':>8}{'meanP':>8}{'meanR':>8}")
    print("-" * 40)
    rows = sorted(((s, mean(per_strategy[s]), mean(per_pr[s][0]), mean(per_pr[s][1]))
                   for s in strategies), key=lambda x: -x[1])
    for s, mf, mp, mr in rows:
        print(f"{s:<16}{mf:>8.3f}{mp:>8.3f}{mr:>8.3f}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"per_image": per_image,
               "mean_f1": {s: mean(per_strategy[s]) for s in strategies},
               "mean_p": {s: mean(per_pr[s][0]) for s in strategies},
               "mean_r": {s: mean(per_pr[s][1]) for s in strategies}},
              open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Isolate the line-detector's contribution: run the best join (scale_completion) on
(a) the DETECTED wires and (b) the PERFECT human-traced GT wires, scored vs the verified
net-GT. The gap = how much connectivity error is the detector's fault vs the join's.

Run on claw:
  ./.venv/bin/python -m wire_detection.benchmark.detection_ceiling --gt ground_truth/real_nets_verified.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import cv2

from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES, GT_WIRE_LABELS, find_hdc_label, parse_components, parse_gt_wires)
from wire_detection.benchmark.join_eval_134 import detect_wires
from wire_detection.benchmark.join_eval_real_f1 import gt_pairs, prf, comp_pairs
from wire_detection.core.join_strategies import make_pins, run_strategy

STRAT = "scale_completion"


def score(wires, comps, keep, gtp):
    pins = make_pins(wires, comps)
    _p, nl = run_strategy(STRAT, wires, comps, std_pins=pins)
    return prf(gtp, comp_pairs(nl, keep))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default="ground_truth/real_nets_verified.json")
    ap.add_argument("--out", default="output/detection_ceiling.json")
    args = ap.parse_args()
    gt = json.load(open(args.gt))

    det, perf = ([], [], []), ([], [], [])
    for img_id, entry in gt.items():
        name = img_id.replace("_jpg", "")
        gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        hdc = find_hdc_label(name)
        wf = GT_WIRE_LABELS / f"{name}_jpg.txt"
        if gray is None or hdc is None or not wf.exists():
            continue
        h, w = gray.shape
        comps = parse_components(hdc.read_text(), w, h)
        keep = set(entry["electrical_idxs"])
        gtp = gt_pairs(entry["nets"], keep)
        for acc, wires in ((det, detect_wires(gray, comps)),
                           (perf, parse_gt_wires(wf.read_text(), w, h))):
            p, r, f1 = score(wires, comps, keep, gtp)
            acc[0].append(p); acc[1].append(r); acc[2].append(f1)

    mean = lambda v: sum(v) / len(v) if v else 0.0
    print(f"\nscale_completion: detected wires vs perfect GT wires ({len(det[0])} imgs)")
    print(f"{'wires':<16}{'meanF1':>8}{'meanP':>8}{'meanR':>8}")
    print("-" * 40)
    print(f"{'detected':<16}{mean(det[2]):>8.3f}{mean(det[0]):>8.3f}{mean(det[1]):>8.3f}")
    print(f"{'perfect GT':<16}{mean(perf[2]):>8.3f}{mean(perf[0]):>8.3f}{mean(perf[1]):>8.3f}")
    print(f"\ndetector accounts for {mean(perf[2]) - mean(det[2]):+.3f} F1 of the gap to perfect")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"detected": {"f1": mean(det[2]), "p": mean(det[0]), "r": mean(det[1])},
               "perfect_gt": {"f1": mean(perf[2]), "p": mean(perf[0]), "r": mean(perf[1])}},
              open(args.out, "w"), indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

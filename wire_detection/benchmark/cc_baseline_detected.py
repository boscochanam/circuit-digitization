#!/usr/bin/env python3
"""B1b — CCL join on the SAME detected wire segments our endpoint-graph join uses.

This isolates the JOIN ALGORITHM (vs the raw-pixel binarization confound in cc_baseline.py):
rasterize the detected wire segments to a mask, connected-components, assign each terminal to
the nearest blob. Compare against our endpoint-graph + completion join on identical input.
This is the apples-to-apples "naive CCL join" vs "our join" comparison for the paper.

Run on claw:
  ./.venv/bin/python -m wire_detection.benchmark.cc_baseline_detected --gt ground_truth/real_nets_verified.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from wire_detection.benchmark.build_net_gt import GT_IMAGES, find_hdc_label, parse_components
from wire_detection.benchmark.join_eval_134 import detect_wires
from wire_detection.benchmark.join_eval_real_f1 import gt_pairs, prf, comp_pairs
from wire_detection.benchmark.cc_baseline import pairs_from_pinnet
from wire_detection.core.join_strategies import make_pins, run_strategy


def detected_wire_ccl(gray, comps, pins, wires, dilate=3, reach=26, min_blob=10):
    h, w = gray.shape
    mask = np.zeros((h, w), np.uint8)
    for (a, b) in wires:
        cv2.line(mask, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), 255, 2)
    if dilate:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate, dilate))
        mask = cv2.dilate(mask, k)
    _n, labels = cv2.connectedComponents(mask, 8)
    sizes = np.bincount(labels.ravel())
    pin_net = {}
    for p in pins:
        x, y = int(p.x), int(p.y)
        x0, x1 = max(0, x - reach), min(w, x + reach + 1)
        y0, y1 = max(0, y - reach), min(h, y + reach + 1)
        sub = labels[y0:y1, x0:x1]
        ys, xs = np.nonzero(sub)
        best, bd = -1, 1e9
        for yy, xx in zip(ys, xs):
            lab = sub[yy, xx]
            if sizes[lab] < min_blob:
                continue
            d = (xx + x0 - x) ** 2 + (yy + y0 - y) ** 2
            if d < bd:
                bd, best = d, int(lab)
        pin_net[(p.component_idx, p.pin_name)] = best
    return pin_net


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default="ground_truth/real_nets_verified.json")
    ap.add_argument("--out", default="output/cc_baseline_detected.json")
    args = ap.parse_args()
    gt = json.load(open(args.gt))

    DILATES = [3, 7, 11, 15]
    acc = {f"detCCL_d{d}": ([], [], []) for d in DILATES}
    acc["ours_scale_completion"] = ([], [], [])
    for img_id, entry in gt.items():
        name = img_id.replace("_jpg", "")
        gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        hdc = find_hdc_label(name)
        if gray is None or hdc is None:
            continue
        h, w = gray.shape
        comps = parse_components(hdc.read_text(), w, h)
        keep = set(entry["electrical_idxs"])
        gtp = gt_pairs(entry["nets"], keep)
        wires = detect_wires(gray, comps)
        pins = make_pins(wires, comps)
        for d in DILATES:
            pn = detected_wire_ccl(gray, comps, pins, wires, dilate=d)
            p, r, f1 = prf(gtp, pairs_from_pinnet(pn, keep))
            acc[f"detCCL_d{d}"][0].append(p); acc[f"detCCL_d{d}"][1].append(r); acc[f"detCCL_d{d}"][2].append(f1)
        _pins, nl = run_strategy("scale_completion", wires, comps, std_pins=pins)
        p, r, f1 = prf(gtp, comp_pairs(nl, keep))
        acc["ours_scale_completion"][0].append(p); acc["ours_scale_completion"][1].append(r); acc["ours_scale_completion"][2].append(f1)

    mean = lambda v: sum(v) / len(v) if v else 0.0
    print(f"\nB1b CCL-on-detected-wires vs our join (same detected wires), verified GT")
    print(f"{'method':<26}{'meanF1':>8}{'meanP':>8}{'meanR':>8}")
    print("-" * 50)
    out = {}
    for m, (P, R, F) in sorted(acc.items(), key=lambda kv: -mean(kv[1][2])):
        out[m] = {"f1": mean(F), "p": mean(P), "r": mean(R)}
        print(f"{m:<26}{mean(F):>8.3f}{mean(P):>8.3f}{mean(R):>8.3f}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

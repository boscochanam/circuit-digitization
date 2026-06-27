#!/usr/bin/env python3
"""Literature connectivity baselines on the human-verified net-GT, scored with the same
component-pair-F1 metric as our join — the first apples-to-apples comparison on hand-drawn
net-level GT (no prior work reports this; see docs/research/literature-review-connectivity.md).

Baseline B1 — CCL net-tracing ("erase-and-label", the SINA / AMSnet 1.0 / Bayer recipe):
  binarize -> paint detected component boxes blank -> connected-components on residual wire
  pixels -> each blob = one net -> assign each component terminal to the blob it touches ->
  terminals sharing a blob are connected. Crossing wires merge (the known failure mode).

Run on claw:
  ./.venv/bin/python -m wire_detection.benchmark.cc_baseline --gt ground_truth/real_nets_verified.json
"""
from __future__ import annotations
import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np

from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES, find_hdc_label, parse_components, electrical_indices)
from wire_detection.benchmark.join_eval_real_f1 import gt_pairs, prf
from wire_detection.core.join_strategies import make_pins


def binarize(gray, block=35, C=10, close=3, close_iter=2):
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, block | 1, C)
    if close:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close, close))
        ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, k, iterations=close_iter)  # bridge pencil gaps
    return ink


def cc_nets(gray, components, pins, erase_margin=1, reach=26, min_blob=25, **bkw):
    """Return {pin_key: net_label}. Erase component boxes, CCL on residual (gap-bridged) ink,
    assign each terminal to the NEAREST blob pixel within `reach` (robust to the box-erase gap)."""
    h, w = gray.shape
    ink = binarize(gray, **bkw)
    for _cls, _v, (x1, y1, x2, y2) in components:        # erase component boxes -> wires only
        cv2.rectangle(ink, (max(0, x1 - erase_margin), max(0, y1 - erase_margin)),
                      (min(w - 1, x2 + erase_margin), min(h - 1, y2 + erase_margin)), 0, -1)
    _n, labels = cv2.connectedComponents(ink, connectivity=8)
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


def pairs_from_pinnet(pin_net, keep):
    by_net = defaultdict(set)
    for (ci, _pn), lab in pin_net.items():
        if lab != -1 and ci in keep:
            by_net[lab].add(ci)
    pairs = set()
    for comps in by_net.values():
        pairs.update(combinations(sorted(comps), 2))
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default="ground_truth/real_nets_verified.json")
    ap.add_argument("--out", default="output/cc_baseline.json")
    args = ap.parse_args()
    gt = json.load(open(args.gt))

    # give the baseline its best shot: sweep gap-bridging (close kernel/iter) + terminal reach
    CONFIGS = [
        ("close5x2_reach26",  dict(close=5,  close_iter=2), 26),
        ("close9x2_reach30",  dict(close=9,  close_iter=2), 30),
        ("close13x2_reach36", dict(close=13, close_iter=2), 36),
        ("close9x3_reach30",  dict(close=9,  close_iter=3), 30),
        ("close17x2_reach40", dict(close=17, close_iter=2), 40),
        ("close21x2_reach44", dict(close=21, close_iter=2), 44),
        ("close25x2_reach48", dict(close=25, close_iter=2), 48),
        ("close31x2_reach54", dict(close=31, close_iter=2), 54),
        ("close39x2_reach60", dict(close=39, close_iter=2), 60),
        ("close47x2_reach64", dict(close=47, close_iter=2), 64),
        ("close59x2_reach70", dict(close=59, close_iter=2), 70),
    ]
    # cache images/comps/pins/gt once
    items = []
    for img_id, entry in gt.items():
        name = img_id.replace("_jpg", "")
        gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        hdc = find_hdc_label(name)
        if gray is None or hdc is None:
            continue
        h, w = gray.shape
        comps = parse_components(hdc.read_text(), w, h)
        keep = set(entry["electrical_idxs"])
        items.append((img_id, gray, comps, keep, gt_pairs(entry["nets"], keep), make_pins([], comps)))

    mean = lambda v: sum(v) / len(v) if v else 0.0
    print(f"\nB1 CCL net-tracing (erase-and-label) vs verified GT ({len(items)} images)")
    print(f"{'config':<22}{'meanF1':>8}{'meanP':>8}{'meanR':>8}")
    print("-" * 46)
    results = {}
    for cname, bkw, reach in CONFIGS:
        F = P = R = 0.0
        for _id, gray, comps, keep, gtp, pins in items:
            pin_net = cc_nets(gray, comps, pins, reach=reach, **bkw)
            p, r, f1 = prf(gtp, pairs_from_pinnet(pin_net, keep))
            F += f1; P += p; R += r
        nz = len(items)
        results[cname] = {"f1": F / nz, "p": P / nz, "r": R / nz}
        print(f"{cname:<22}{F/nz:>8.3f}{P/nz:>8.3f}{R/nz:>8.3f}")
    best = max(results, key=lambda c: results[c]["f1"])
    print(f"\nBEST: {best} -> F1 {results[best]['f1']:.3f}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"best": best, "configs": results}, open(args.out, "w"), indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

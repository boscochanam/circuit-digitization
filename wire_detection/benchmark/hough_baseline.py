#!/usr/bin/env python3
"""B2 — Hough + proximity net tracing (Reddy & Panicker-style classical connectivity), on the
human-verified net-GT, same component-pair-F1 metric. Erase component boxes, extract wire
segments with the probabilistic Hough transform, union segments whose endpoints are close
(transitive), and assign each component terminal to the nearest segment's net. A directly
comparable classical baseline that uses line primitives rather than blob/contour connectivity.

Run on claw:
  ./.venv/bin/python -m wire_detection.benchmark.hough_baseline --gt ground_truth/real_nets_verified.json
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np

from wire_detection.benchmark.build_net_gt import GT_IMAGES, find_hdc_label, parse_components
from wire_detection.benchmark.join_eval_real_f1 import gt_pairs, prf
from wire_detection.core.join_strategies import make_pins


def hough_nets(gray, components, pins, link_tol=14, reach=26, min_len=18):
    h, w = gray.shape
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, 35, 10)
    for _c, _v, (x1, y1, x2, y2) in components:
        cv2.rectangle(ink, (max(0, x1 - 1), max(0, y1 - 1)), (min(w - 1, x2 + 1), min(h - 1, y2 + 1)), 0, -1)
    lines = cv2.HoughLinesP(ink, 1, np.pi / 180, threshold=30, minLineLength=min_len, maxLineGap=10)
    segs = [] if lines is None else [tuple(map(int, l[0])) for l in lines]
    if not segs:
        return {(p.component_idx, p.pin_name): -1 for p in pins}
    # union segments whose endpoints are within link_tol (transitive)
    parent = list(range(len(segs)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a, b):
        ra, rb = find(a), find(b); parent[ra] = rb
    eps = [((s[0], s[1]), (s[2], s[3])) for s in segs]
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            d = min(math.hypot(a[0]-b[0], a[1]-b[1]) for a in eps[i] for b in eps[j])
            if d <= link_tol:
                union(i, j)
    # assign each pin to the net of the nearest segment (by point-to-endpoint distance) within reach
    pin_net = {}
    for p in pins:
        best, bd = -1, reach + 1
        for si, (a, b) in enumerate(eps):
            d = min(math.hypot(p.x - a[0], p.y - a[1]), math.hypot(p.x - b[0], p.y - b[1]))
            if d < bd:
                bd, best = d, find(si)
        pin_net[(p.component_idx, p.pin_name)] = best
    return pin_net


def pairs_from_pinnet(pin_net, keep):
    by = defaultdict(set)
    for (ci, _pn), lab in pin_net.items():
        if lab != -1 and ci in keep:
            by[lab].add(ci)
    pairs = set()
    for comps in by.values():
        pairs.update(combinations(sorted(comps), 2))
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default="ground_truth/real_nets_verified.json")
    ap.add_argument("--out", default="output/hough_baseline.json")
    args = ap.parse_args()
    gt = json.load(open(args.gt))
    CONFIGS = [("link10_reach22", 10, 22), ("link14_reach26", 14, 26),
               ("link20_reach30", 20, 30), ("link28_reach36", 28, 36),
               ("link36_reach42", 36, 42), ("link44_reach48", 44, 48), ("link56_reach56", 56, 56)]
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
        items.append((gray, comps, keep, gt_pairs(entry["nets"], keep), make_pins([], comps)))
    mean = lambda v: sum(v) / len(v) if v else 0.0
    print(f"\nB2 Hough+proximity net tracing vs verified GT ({len(items)} images)")
    print(f"{'config':<18}{'F1':>8}{'P':>8}{'R':>8}")
    print("-" * 42)
    results = {}
    for cname, link, reach in CONFIGS:
        F = P = R = 0.0
        for gray, comps, keep, gtp, pins in items:
            pn = hough_nets(gray, comps, pins, link_tol=link, reach=reach)
            p, r, f1 = prf(gtp, pairs_from_pinnet(pn, keep))
            F += f1; P += p; R += r
        n = len(items); results[cname] = {"f1": F/n, "p": P/n, "r": R/n}
        print(f"{cname:<18}{F/n:>8.3f}{P/n:>8.3f}{R/n:>8.3f}")
    best = max(results, key=lambda c: results[c]["f1"])
    print(f"\nBEST: {best} -> F1 {results[best]['f1']:.3f}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"best": best, "configs": results}, open(args.out, "w"), indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

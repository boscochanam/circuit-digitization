#!/usr/bin/env python3
"""Debug/audit overlay for the CGHD-annotation reference: conductors coloured by reference net,
polygons outlined (electrical = red with index, junction = green, crossover = magenta,
other = grey). Writes PNGs to a scratch dir (derived from CGHD images: CC licence, do not commit).

  PYTHONPATH=~/circuit-digitization python cghd_viz.py --ref out/cghd_ref_nets.json --out out/viz C4_D2_P4 ...
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cghd_common import load_gray, load_shapes, load_stroke_mask, is_electrical  # noqa: E402
from cghd_ref import build_reference, _disk  # noqa: E402

PAL = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48), (145, 30, 180),
       (70, 200, 200), (240, 50, 230), (160, 200, 60), (250, 150, 150), (0, 128, 128),
       (170, 110, 40), (128, 0, 0), (0, 0, 128), (128, 128, 0), (255, 180, 0)]


def render(drafter, stem, max_side=1600):
    shapes, W, H = load_shapes(drafter, stem)
    S = load_stroke_mask(drafter, stem)
    r = build_reference(shapes, S)
    gray = load_gray(drafter, stem)
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    img = (img * 0.35 + 165).astype(np.uint8)
    # recompute conductor labels exactly as build_reference does, colour by net
    erase = np.zeros((H, W), np.uint8)
    for s in shapes:
        cv2.fillPoly(erase, [np.round(s["points"]).astype(np.int32)], 1)
    erase = cv2.dilate(erase, _disk(r["d_erase"]))
    img[S & (erase > 0)] = (120, 120, 120)
    Wm = (S & (erase == 0)).astype(np.uint8)
    img[Wm > 0] = (0, 0, 0)
    # colour conductors by the net of the symbols they touch (approx: nearest net member)
    net_of = {}
    for ni, net in enumerate(r["nets"]):
        for i in net:
            net_of.setdefault(i, []).append(ni)
    th = max(2, int(round(max(W, H) / 700)))
    for ni, net in enumerate(r["nets"]):
        col = PAL[ni % len(PAL)]
        pts = [shapes[i]["points"].mean(axis=0) for i in net]
        for a in range(len(pts)):
            for b in range(a + 1, len(pts)):
                cv2.line(img, tuple(int(v) for v in pts[a]), tuple(int(v) for v in pts[b]), col, th)
    for i, s in enumerate(shapes):
        p = np.round(s["points"]).astype(np.int32)
        k = s["label"]
        if k == "junction":
            col = (0, 170, 0)
        elif k == "crossover":
            col = (200, 0, 200)
        elif is_electrical(k):
            col = (0, 0, 230)
        else:
            col = (150, 150, 150)
        cv2.polylines(img, [p], True, col, th)
        if k not in ("junction", "crossover", "text"):
            x, y = p[:, 0].min(), p[:, 1].min()
            cv2.putText(img, f"{i}", (int(x), int(max(20, y - 6))), cv2.FONT_HERSHEY_SIMPLEX,
                        th * 0.5, col, th)
    sc = max_side / max(W, H)
    if sc < 1:
        img = cv2.resize(img, (int(W * sc), int(H * sc)), interpolation=cv2.INTER_AREA)
    return img, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stems", nargs="+")
    ap.add_argument("--out", default="out/viz")
    args = ap.parse_args()
    from cghd_common import list_samples
    dmap = {s: d for d, s in list_samples()}
    Path(args.out).mkdir(parents=True, exist_ok=True)
    for stem in args.stems:
        img, r = render(dmap[stem], stem)
        cv2.imwrite(f"{args.out}/{stem}.png", img)
        print(stem, "nets:", r["nets"], "flags:", json.dumps(r["flags"]), "xover:", r["crossovers"])


if __name__ == "__main__":
    main()

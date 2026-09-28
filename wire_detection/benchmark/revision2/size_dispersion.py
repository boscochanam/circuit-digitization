#!/usr/bin/env python3
"""Per-image component-size dispersion on the 31-image net-GT (R2-6).

For every image: diagonals of the SPICE-active (electrical) GT component boxes and of
all GT boxes; reports max/median, max/min and coefficient of variation, plus the
image's characteristic scale s (median diagonal over all boxes, as estimate_scale).
Joined with per-image F1 from rescale_n31.json (factor 1.0) offline.

  PYTHONPATH=~/circuit-digitization ~/circuit-digitization/.venv/bin/python size_dispersion.py
"""
from __future__ import annotations

import json
import math
import os
import statistics
from pathlib import Path

import cv2

REPO = Path(os.environ.get("CIRCUIT_REPO", Path.home() / "circuit-digitization"))
os.chdir(REPO)

from wire_detection.benchmark.build_net_gt import GT_IMAGES, find_hdc_label, parse_components  # noqa: E402
from wire_detection.core.component_classes import COMPONENT_TYPES  # noqa: E402
from wire_detection.core.join_graph import estimate_scale  # noqa: E402


def stats(d):
    d = sorted(d)
    med = statistics.median(d)
    return {"n": len(d), "min": d[0], "median": med, "max": d[-1],
            "max_over_median": d[-1] / med, "max_over_min": d[-1] / d[0],
            "cv": statistics.pstdev(d) / statistics.mean(d)}


def main():
    gt = json.load(open("ground_truth/real_nets_verified.json"))
    out = {}
    for img_id, e in gt.items():
        name = img_id.replace("_jpg", "")
        g = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        h, w = g.shape
        comps = parse_components(find_hdc_label(name).read_text(), w, h)
        diag = [math.hypot(b[2] - b[0], b[3] - b[1]) for _c, _v, b in comps]
        el = [diag[i] for i in e["electrical_idxs"]]
        types = sorted({COMPONENT_TYPES.get(int(comps[i][0]), "?") for i in e["electrical_idxs"]})
        out[img_id] = {"s": estimate_scale(comps, []), "electrical": stats(el),
                       "all": stats(diag), "electrical_types": types}
    p = Path.home() / "rev2_scratch" / "size_dispersion_n31.json"
    json.dump(out, open(p, "w"), indent=1)
    print("wrote", p)


if __name__ == "__main__":
    main()

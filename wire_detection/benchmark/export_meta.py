#!/usr/bin/env python3
"""Export electrical-component bboxes (normalized) + a clean grayscale+wires overlay (no
boxes/numbers baked) so the UI can draw boxes+labels itself."""
from __future__ import annotations
import json
from pathlib import Path
import cv2

from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES, GT_WIRE_LABELS, find_hdc_label, parse_components, parse_gt_wires,
    electrical_indices,
)

NAMES = ["C84_D2_P1", "C22_D2_P3", "C29_D2_P4", "C15_D2_P2", "C20_D2_P2",
         "C138_D1_P3", "C92_D1_P3", "C109_D2_P3", "C21_D1_P3", "C28_D1_P3"]

meta = {}
outdir = Path("output/net_gt_clean")
outdir.mkdir(parents=True, exist_ok=True)
for name in NAMES:
    gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    hdc = find_hdc_label(name)
    wf = GT_WIRE_LABELS / f"{name}_jpg.txt"
    if gray is None or hdc is None or not wf.exists():
        print("skip", name); continue
    h, w = gray.shape
    comps = parse_components(hdc.read_text(), w, h)
    wires = parse_gt_wires(wf.read_text(), w, h)
    elec = electrical_indices(comps)
    scale = max(1, int(round(1500 / max(w, h))))
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if scale > 1:
        img = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    S = lambda p: (int(p[0] * scale), int(p[1] * scale))
    for a, b in wires:                       # draw wires clearly (dark), nothing else
        cv2.line(img, S(a), S(b), (40, 40, 40), max(2, scale))
    cv2.imwrite(str(outdir / f"{name}.png"), img)
    meta[f"{name}_jpg"] = {
        "img_wh": [img.shape[1], img.shape[0]],
        "bboxes": {str(i): [round(comps[i][2][0]/w, 4), round(comps[i][2][1]/h, 4),
                            round(comps[i][2][2]/w, 4), round(comps[i][2][3]/h, 4)]
                   for i in elec},
    }
    print(f"  {name}: {len(elec)} elec, {img.shape[1]}px")
Path("output/net_gt_clean/meta.json").write_text(json.dumps(meta))
print("wrote output/net_gt_clean/meta.json")

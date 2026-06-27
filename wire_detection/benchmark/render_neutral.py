#!/usr/bin/env python3
"""Neutral verification overlays: grayscale scan + electrical component boxes labelled by
index, NO net colouring (so the human can trace wires unbiased). Native res, upscaled."""
from __future__ import annotations
import sys
from pathlib import Path
import cv2

from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES, GT_WIRE_LABELS, find_hdc_label, parse_components, parse_gt_wires,
    electrical_indices,
)


def render(name: str, outdir: Path) -> None:
    gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    hdc = find_hdc_label(name)
    gt_wire_file = GT_WIRE_LABELS / f"{name}_jpg.txt"
    if gray is None or hdc is None or not gt_wire_file.exists():
        print(f"  skip {name}"); return
    h, w = gray.shape
    components = parse_components(hdc.read_text(), w, h)
    wires = parse_gt_wires(gt_wire_file.read_text(), w, h)
    elec = set(electrical_indices(components))
    scale = max(1, int(round(1500 / max(w, h))))
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if scale > 1:
        img = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    S = lambda p: (int(p[0] * scale), int(p[1] * scale))
    # draw GT wires faintly so wiring is visible but not coloured
    for a, b in wires:
        cv2.line(img, S(a), S(b), (90, 90, 90), max(1, scale))
    for i in sorted(elec):
        x1, y1, x2, y2 = components[i][2]
        cv2.rectangle(img, S((x1, y1)), S((x2, y2)), (0, 0, 255), 2 * scale)
        cv2.putText(img, str(i), (int(x1*scale), max(14*scale, int(y1*scale)-5*scale)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7*scale, (0, 0, 255), max(1, scale))
    outdir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(outdir / f"{name}.png"), img)
    print(f"  {name}: {len(elec)} elec -> {img.shape[1]}x{img.shape[0]}")


if __name__ == "__main__":
    names = sys.argv[1:] or [
        "C84_D2_P1", "C22_D2_P3", "C29_D2_P4", "C15_D2_P2", "C20_D2_P2",
        "C138_D1_P3", "C92_D1_P3", "C109_D2_P3", "C21_D1_P3", "C28_D1_P3",
    ]
    out = Path("output/net_gt_neutral")
    for n in names:
        render(n, out)

#!/usr/bin/env python3
"""Verification-friendly net-GT overlays: each net's wires + pins drawn in one colour
at their TRUE positions (not component centres), at native resolution. For human GT check."""
from __future__ import annotations
import sys
from pathlib import Path
import cv2

from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.core.join_strategies import make_pins, make_pins_junction_aware, run_strategy
from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES, GT_WIRE_LABELS, find_hdc_label, parse_components, parse_gt_wires,
    electrical_indices, GT_STRATEGY,
)

PALETTE = [
    (60, 76, 231), (75, 180, 60), (200, 130, 0), (48, 130, 245), (180, 30, 145),
    (240, 240, 70), (230, 50, 240), (60, 245, 210), (190, 190, 250), (128, 128, 0),
    (40, 110, 170), (0, 0, 200), (128, 0, 0), (0, 128, 128), (0, 215, 255),
    (140, 0, 140), (90, 90, 220), (0, 165, 255), (130, 200, 130), (200, 100, 200),
]


def render(name: str, outdir: Path) -> None:
    img_path = GT_IMAGES / f"{name}_jpg.jpg"
    gray = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    hdc = find_hdc_label(name)
    gt_wire_file = GT_WIRE_LABELS / f"{name}_jpg.txt"
    if gray is None or hdc is None or not gt_wire_file.exists():
        print(f"  skip {name}"); return
    h, w = gray.shape
    components = parse_components(hdc.read_text(), w, h)
    wires = parse_gt_wires(gt_wire_file.read_text(), w, h)
    std_pins = make_pins(wires, components)
    junc_pins = make_pins_junction_aware(wires, components)
    _pins, nl = run_strategy(GT_STRATEGY, wires, components, std_pins=std_pins, junc_pins=junc_pins)
    elec = set(electrical_indices(components))

    # upscale small images so labels are legible
    scale = max(1, int(round(1400 / max(w, h))))
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if scale > 1:
        img = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    def S(p):
        return (int(p[0] * scale), int(p[1] * scale))

    # faint all wires first
    for a, b in wires:
        cv2.line(img, S(a), S(b), (210, 210, 210), 1 * scale)

    # colour each net's wires + pins
    for node in nl.nodes:
        col = PALETTE[node.node_id % len(PALETTE)]
        for wi in node.wires:
            a, b = wires[wi]
            cv2.line(img, S(a), S(b), col, 2 * scale)
        for p in node.pins:
            cv2.circle(img, S((p.x, p.y)), 4 * scale, col, -1)
            cv2.putText(img, f"n{node.node_id}", (int(p.x*scale)+5*scale, int(p.y*scale)-3*scale),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35*scale, col, max(1, scale))

    # component boxes: electrical = red thick + big index; others = grey thin + small index
    for i, (_cls, _verts, (x1, y1, x2, y2)) in enumerate(components):
        is_e = i in elec
        bcol = (0, 0, 255) if is_e else (120, 120, 120)
        cv2.rectangle(img, S((x1, y1)), S((x2, y2)), bcol, (2 if is_e else 1) * scale)
        cv2.putText(img, str(i), (int(x1*scale), max(12*scale, int(y1*scale)-4*scale)),
                    cv2.FONT_HERSHEY_SIMPLEX, (0.7 if is_e else 0.4)*scale, bcol, max(1, scale))

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{name}.png"
    cv2.imwrite(str(out), img)
    print(f"  {name}: {len(nl.nodes)} nets, {len(components)} comps -> {out.name} ({img.shape[1]}x{img.shape[0]})")


if __name__ == "__main__":
    names = sys.argv[1:] or [
        "C84_D2_P1", "C22_D2_P3", "C29_D2_P4", "C15_D2_P2", "C20_D2_P2",
        "C138_D1_P3", "C92_D1_P3", "C109_D2_P3", "C21_D1_P3", "C28_D1_P3",
    ]
    outdir = Path("output/net_gt_verify")
    for n in names:
        render(n, outdir)

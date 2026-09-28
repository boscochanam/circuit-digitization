#!/usr/bin/env python3
"""Redraw the audit overlay images with context boxes for parts outside the scored subset.

The audit UI draws boxes only for the scored electrical components (R/C/L/D/Q/V/IC types).
Switches, potentiometers, photoresistors, logic gates, speakers, transformers etc. are
annotated in CGHD but not scored, so without a box they look like missing labels. This
script burns a thin gray box with the CGHD class name for each such part into
<audit>/overlays/<stem>.png. It does not touch real_nets_working.json (audit progress).

  PYTHONPATH=~/circuit-digitization python cghd_audit_overlays.py --audit out/cghd_ref_audit
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cghd_common import is_electrical, list_samples, load_gray, load_shapes  # noqa

CONTEXT_SKIP = {"junction", "crossover", "text", "antenna"}
# Supply symbols get their own note: they connect only through drawn wires in this benchmark.
SUPPLY = {"gnd", "vss", "vdd", "terminal"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", required=True)
    args = ap.parse_args()
    audit = Path(args.audit)
    stems = json.load(open(audit / "sample.json"))["stems"]
    dmap = {s: d for d, s in list_samples()}
    n_boxes = 0
    for s in stems:
        shapes, W, H = load_shapes(dmap[s], s)
        g = load_gray(dmap[s], s)
        H0, W0 = g.shape[:2]
        sc = 1600 / max(W0, H0)
        g = cv2.resize(g, (int(round(W0 * sc)), int(round(H0 * sc))), interpolation=cv2.INTER_AREA)
        img = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
        for sh in shapes:
            lab = sh["label"]
            if lab in CONTEXT_SKIP or lab.startswith("probe") or is_electrical(lab):
                continue
            p = sh["points"]
            x1, y1 = int(p[:, 0].min() * sc), int(p[:, 1].min() * sc)
            x2, y2 = int(p[:, 0].max() * sc), int(p[:, 1].max() * sc)
            cv2.rectangle(img, (x1, y1), (x2, y2), (150, 150, 150), 2)
            txt = f"{lab} (wires only)" if lab in SUPPLY else f"{lab} (not scored)"
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            ty = max(th + 4, y1 - 5)
            cv2.rectangle(img, (x1, ty - th - 4), (x1 + tw + 4, ty + 3), (255, 255, 255), -1)
            cv2.putText(img, txt, (x1 + 2, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (90, 90, 90), 1,
                        cv2.LINE_AA)
            n_boxes += 1
        cv2.imwrite(str(audit / "overlays" / f"{s}.png"), img)
    print(f"redrew {len(stems)} overlays, {n_boxes} context boxes")


if __name__ == "__main__":
    main()

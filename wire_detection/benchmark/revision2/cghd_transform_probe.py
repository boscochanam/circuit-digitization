#!/usr/bin/env python3
"""Estimate, per CGHD sample that also exists as a 704x704 benchmark copy
(labels_few_annot/images/<stem>_jpg.jpg), the dihedral transform k (0..7, see
cghd_common.dihedral_array) relating the EXIF-corrected CGHD original to the benchmark copy.

Two independent estimates: (a) correlation of blurred adaptive-threshold ink maps over the 8
candidate transforms; (b) where our committed component labels exist, mean best AABB IoU between
our boxes and the transformed CGHD polygons. They agree on every image with labels (53/53).

  PYTHONPATH=~/circuit-digitization python cghd_transform_probe.py --out transform_probe.json
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cghd_common import BENCH_IMAGES, dihedral_array, dihedral_norm, list_samples, load_gray, load_shapes  # noqa

REPO = Path.home() / "circuit-digitization"


def ink(a):
    a = cv2.resize(a, (704, 704), interpolation=cv2.INTER_AREA)
    b = cv2.adaptiveThreshold(a, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 35, 10)
    return cv2.GaussianBlur(b.astype(float), (0, 0), 3)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy; u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i
    return i / u if u > 0 else 0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); args = ap.parse_args()
    CL = REPO / "ground_truth/component_labels"; WL = REPO / "ground_truth/wire_labels"
    rows = []
    for d, s in list_samples():
        g = BENCH_IMAGES / f"{s}_jpg.jpg"
        if not g.exists():
            continue
        im = load_gray(d, s); H, W = im.shape
        g7 = ink(cv2.imread(str(g), 0))
        ec = [float(np.corrcoef(ink(dihedral_array(im, k)).ravel(), g7.ravel())[0, 1]) for k in range(8)]
        ke = int(np.argmax(ec))
        shapes, _, _ = load_shapes(d, s)
        cg = [(sh["points"][:, 0].min()/W, sh["points"][:, 1].min()/H, sh["points"][:, 0].max()/W, sh["points"][:, 1].max()/H) for sh in shapes]
        kb = ious = None
        lf = CL / f"{s}_jpg.txt"
        if lf.exists():
            ours = []
            for line in open(lf):
                q = line.split()
                if len(q) != 9: continue
                c = list(map(float, q[1:])); ours.append((min(c[0::2]), min(c[1::2]), max(c[0::2]), max(c[1::2])))
            sc = []
            for k in range(8):
                t = []
                for (x1, y1, x2, y2) in cg:
                    a = dihedral_norm(x1, y1, k); b = dihedral_norm(x2, y2, k)
                    t.append((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
                sc.append(float(np.mean([max(iou(o, c) for c in t) for o in ours])))
            kb = int(np.argmax(sc)); ious = round(sc[kb], 3)
        rows.append(dict(stem=s, drafter=d, W=W, H=H, k_ink=ke, ink_corr=round(ec[ke], 3), ink_corr_identity=round(ec[0], 3),
                         k_box=kb, box_iou=ious, has_component_labels=lf.exists(), has_wire_labels=(WL / f"{s}_jpg.txt").exists()))
    json.dump(rows, open(args.out, "w"), indent=1)
    lab = [r for r in rows if r["k_box"] is not None]
    print(f"{len(rows)} benchmark copies; {sum(r['k_ink'] != 0 for r in rows)} non-identity; "
          f"labels {len(lab)}, ink/box agree {sum(r['k_ink'] == r['k_box'] for r in lab)}")


if __name__ == "__main__":
    main()

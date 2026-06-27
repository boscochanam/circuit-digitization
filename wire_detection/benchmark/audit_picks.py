#!/usr/bin/env python3
"""For every image: what label does find_hdc_label CURRENTLY pick, vs the IDENTITY label
(rf image == GT image)? Flag mismatches — those have rotated/augmented (wrong) boxes."""
import cv2, numpy as np, sys
from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES, find_hdc_label, HDC_BASE, HDC_SPLITS)


def identity_label(name, gray):
    best, bestd = None, 1e9
    for sp in HDC_SPLITS:
        for f in sorted((HDC_BASE / sp / "labels").glob(f"{name}_jpg.rf.*.txt")):
            hashpart = f.name.split(".rf.")[1].rsplit(".txt", 1)[0]
            ri_p = HDC_BASE / sp / "images" / f"{name}_jpg.rf.{hashpart}.jpg"
            if not ri_p.exists():
                continue
            ri = cv2.imread(str(ri_p), cv2.IMREAD_GRAYSCALE)
            if ri is None or ri.shape != gray.shape:
                continue
            d = float(np.abs(ri.astype(int) - gray.astype(int)).mean())
            if d < bestd:
                best, bestd = f, d
    return best, bestd


names = sys.argv[1:]
bad = 0
for name in names:
    gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        print(f"{name}: NO GT IMAGE"); continue
    cur = find_hdc_label(name)
    ident, d = identity_label(name, gray)
    cur_h = cur.name.split(".rf.")[1][:8] if cur else "none"
    id_h = ident.name.split(".rf.")[1][:8] if ident else "none"
    ok = (cur and ident and cur.name == ident.name)
    if not ok:
        bad += 1
    print(f"{name:14} current={cur_h}  identity={id_h} (diff {d:.1f})  {'OK' if ok else '<<< MISMATCH (wrong boxes)'}")
print(f"\n{bad}/{len(names)} images currently use the WRONG (augmented) label")

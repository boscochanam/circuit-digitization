#!/usr/bin/env python3
"""Alignment check: for each electrical component box, what fraction of pixels is ink?
A box on blank paper (misaligned / rotated-augmentation label) has near-zero ink."""
import cv2, numpy as np, json, sys
from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES, find_hdc_label, parse_components, electrical_indices)

batch = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "ground_truth/real_nets_batch2.json"))


def ink_frac(gray, box):
    x1, y1, x2, y2 = box
    x1, y1 = max(0, x1), max(0, y1)
    sub = gray[y1:y2, x1:x2]
    if sub.size == 0:
        return 0.0
    thr = gray.mean() - 1.0 * gray.std()
    return float((sub < thr).mean())


rows = []
for k in batch:
    name = k[:-4]
    gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    hdc = find_hdc_label(name)
    h, w = gray.shape
    comps = parse_components(hdc.read_text(), w, h)
    elec = electrical_indices(comps)
    fr = [ink_frac(gray, comps[i][2]) for i in elec]
    empty = sum(1 for f in fr if f < 0.03)
    rows.append((empty, len(elec), round(float(np.mean(fr)), 3) if fr else 0.0, name))

rows.sort(reverse=True)
print("EMPTY /elec meanInk  image")
for e, n, m, nm in rows:
    flag = "  <-- LIKELY MISALIGNED" if e >= max(1, n // 3) else ""
    print(f"{e:>5} {n:>5} {m:>7}  {nm}{flag}")

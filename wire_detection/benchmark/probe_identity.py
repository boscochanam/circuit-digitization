#!/usr/bin/env python3
"""For flagged images, list ALL rf label copies with (a) ink-alignment of their boxes on the
GT image and (b) pixel-match of their rf IMAGE to the GT image. The identity copy = best
image match; verify its boxes also have high ink (i.e. it aligns)."""
import cv2, numpy as np, sys
from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES, parse_components, electrical_indices, HDC_BASE, HDC_SPLITS)


def all_rf(name):
    out = []
    for sp in HDC_SPLITS:
        for f in sorted((HDC_BASE / sp / "labels").glob(f"{name}_jpg.rf.*.txt")):
            out.append((sp, f))
    return out


def ink(gray, comps, elec):
    thr = gray.mean() - gray.std()
    fr = []
    for i in elec:
        x1, y1, x2, y2 = comps[i][2]
        sub = gray[max(0, y1):y2, max(0, x1):x2]
        fr.append(float((sub < thr).mean()) if sub.size else 0.0)
    return round(float(np.mean(fr)), 3) if fr else 0.0


names = sys.argv[1:] or ["C136_D1_P1", "C23_D1_P2", "C92_D2_P1", "C19_D1_P2"]
for name in names:
    gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    h, w = gray.shape
    print(f"\n=== {name} ({w}x{h}) ===")
    for sp, f in all_rf(name):
        comps = parse_components(f.read_text(), w, h)
        elec = electrical_indices(comps)
        # find matching rf image
        hashpart = f.name.split(".rf.")[1].rsplit(".txt", 1)[0]
        rfimg = HDC_BASE / sp / "images" / f"{name}_jpg.rf.{hashpart}.jpg"
        match = "?"
        if rfimg.exists():
            ri = cv2.imread(str(rfimg), cv2.IMREAD_GRAYSCALE)
            if ri.shape == gray.shape:
                match = round(float(np.abs(ri.astype(int) - gray.astype(int)).mean()), 1)
        print(f"  {sp}/{hashpart[:8]}: boxInk={ink(gray,comps,elec):.3f}  imgDiff(vsGT)={match}")

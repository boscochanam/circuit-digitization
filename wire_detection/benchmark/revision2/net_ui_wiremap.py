#!/usr/bin/env python3
"""Build the wire maps the net-verification UIs use to colour the drawn wires of each group.

For every image: segment the ink of the photo (illumination-flattened, hysteresis threshold
chosen per image: the pair linking the most parts without grid or ruled paper flooding the
strokes), erase the scored component boxes, and take the connected components of what is
left as conductors. Plain crossings are split as in cghd_ref.py: at a four-arm skeleton
junction with no dot, the ink is cut and opposite arms are re-joined straight through. A
conductor is kept when it touches at least one scored box (within a small ring outside the
box). Output per image:

  <out>/<stem>.png   conductor id per pixel, RGB-encoded (id = R + 256*G; 0 = no wire),
                     dilated by 2 px so thin strokes stay visible when zoomed out
  <out>/<stem>.json  {"conductors": {id: [touched component idx]}, "dropped": n,
                      "thresholds": [strong, weak], "crossings": n}

Conductors spanning >= 92% of the image width or height are dropped (paper rulings, page
edges); "dropped" counts them so the UI can warn that the map is incomplete. The map is a
viewing aid only: faint ink can be missing and an unusual crossing can stay merged.

  python -m wire_detection.benchmark.revision2.net_ui_wiremap --set audit
  python -m wire_detection.benchmark.revision2.net_ui_wiremap --set n31
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from skimage.filters import apply_hysteresis_threshold
from skimage.morphology import skeletonize

ROOT = Path(__file__).resolve().parents[3]
SETS = {  # images, scored-box metadata, output dir
    "audit": (ROOT / "ground_truth/cghd_ref_audit/overlays_plain",
              ROOT / "ground_truth/cghd_ref_audit/net_gt_ui_meta.json",
              ROOT / "ground_truth/cghd_ref_audit/wiremap"),
    "n31": (ROOT / "ground_truth/net_gt_ui_overlays",
            ROOT / "ground_truth/net_gt_ui_meta.json",
            ROOT / "ground_truth/net_gt_ui_wiremap"),
}


def _norm(gray):
    g = gray.astype(np.float32)
    return cv2.GaussianBlur(g / np.maximum(cv2.GaussianBlur(g, (0, 0), 25), 1), (0, 0), 1.0)


def _mask(n, strong, weak):
    m = apply_hysteresis_threshold(1 - n, 1 - weak, 1 - strong).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))


def _split_crossings(m):
    """Label ink with plain crossings cut: a skeleton junction with four arms, no dot (local
    ink thickness < 2.2x the stroke half-width) and two near-opposite arm pairs is erased in a
    disc, and each opposite pair of arms is re-joined. Returns (n, labels, n_crossings)."""
    sk = skeletonize(m > 0)
    nb = cv2.filter2D(sk.astype(np.uint8), -1, np.ones((3, 3), np.float32)) - sk
    br = (sk & (nb >= 3)).astype(np.uint8)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    hw = float(np.median(dt[sk])) if sk.any() else 1.5
    R = int(max(6, round(3.5 * hw)))
    H, W = m.shape
    yy, xx = np.mgrid[-R - 5:R + 6, -R - 5:R + 6]
    rr = np.hypot(yy, xx)
    nbr, _, _, cen = cv2.connectedComponentsWithStats(cv2.dilate(br, np.ones((R | 1, R | 1), np.uint8)))
    cut, joins = m.copy(), []
    for cx, cy in cen[1:]:
        cx, cy = int(round(cx)), int(round(cy))
        if cx < R + 5 or cy < R + 5 or cx >= W - R - 5 or cy >= H - R - 5:
            continue
        win = (slice(cy - R - 5, cy + R + 6), slice(cx - R - 5, cx + R + 6))
        if dt[win][rr <= R / 2].max() > 2.2 * hw:          # a junction dot: connected
            continue
        ann = (sk[win] & (rr > R + 1) & (rr <= R + 4)).astype(np.uint8)
        na, alab = cv2.connectedComponents(ann, connectivity=8)
        if na - 1 != 4:
            continue
        pts, dirs = [], []
        for a in range(1, 5):
            ys, xs = np.nonzero(alab == a)
            v = np.array([xs.mean() - R - 5, ys.mean() - R - 5])
            dirs.append(v / (np.linalg.norm(v) + 1e-9))
            pts.append((cy - R - 5 + ys[0], cx - R - 5 + xs[0]))
        pairings = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
        best = min(pairings, key=lambda pr: sum(dirs[a] @ dirs[b] for a, b in pr))
        if any(dirs[a] @ dirs[b] > -0.7 for a, b in best):  # arms not straight through
            continue
        cut[win][rr <= R] = 0
        joins += [(pts[a], pts[b]) for a, b in best]
    n, lab = cv2.connectedComponents(cut)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for (ya, xa), (yb, xb) in joins:
        a, b = find(lab[ya, xa]), find(lab[yb, xb])
        if a and b:
            parent[a] = b
    root = np.array([find(i) for i in range(n)])
    return n, root[lab], len(joins) // 2


def _conductors(m, rects, W, H, split=False):
    m = m.copy()
    for x1, y1, x2, y2 in rects.values():
        m[y1:y2, x1:x2] = 0
    ncross = 0
    if split:
        n, lab, ncross = _split_crossings(m)
    else:
        n, lab = cv2.connectedComponents(m)
    r = max(4, round(0.006 * max(W, H)))
    touched = {}
    for i, (x1, y1, x2, y2) in rects.items():
        for c in np.unique(lab[max(0, y1 - r):y2 + r, max(0, x1 - r):x2 + r]):
            if c:
                touched.setdefault(int(c), set()).add(i)
    return n, lab, touched, ncross


def build(img_path, boxes):
    """Pick the threshold pair that links the most parts without one blob reaching most boxes
    (grid or ruled paper flooding the strokes), then label conductors at that setting."""
    gray = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    H, W = gray.shape
    rects = {int(i): (int(b[0] * W), int(b[1] * H), int(np.ceil(b[2] * W)), int(np.ceil(b[3] * H)))
             for i, b in boxes.items()}
    nrm = _norm(gray)
    best = None
    for strong in (0.62, 0.67, 0.72, 0.77, 0.82):
        for weak in (strong, strong + 0.04, strong + 0.08, strong + 0.12):
            if weak > 0.92:
                continue
            res = _conductors(_mask(nrm, strong, weak), rects, W, H)
            sizes = [len(t) for t in res[2].values()]
            if len(rects) >= 5 and sizes and max(sizes) > 0.6 * len(rects):
                continue
            score = sum(s >= 2 for s in sizes)
            if best is None or score > best[0]:
                best = (score, (strong, weak), None)
    if best is None:   # every setting floods: fall back to the strictest
        best = (0, (0.62, 0.62), None)
    thr = best[1]
    n, lab, touched, ncross = _conductors(_mask(nrm, *thr), rects, W, H, split=True)
    dropped = 0
    keep = {}
    for c, t in touched.items():
        ys, xs = np.nonzero(lab == c)
        if xs.max() - xs.min() >= 0.92 * W or ys.max() - ys.min() >= 0.92 * H:
            dropped += 1
            continue
        keep[c] = sorted(t)
    remap = np.zeros(n, np.int32)
    for new, c in enumerate(sorted(keep), 1):
        remap[c] = new
    ids = cv2.dilate(remap[lab].astype(np.float32), np.ones((5, 5), np.uint8)).astype(np.int32)
    rgb = np.dstack([ids % 256, ids // 256, np.zeros_like(ids)]).astype(np.uint8)
    return rgb, {"conductors": {str(remap[c]): t for c, t in keep.items()}, "dropped": dropped,
                 "thresholds": [round(x, 2) for x in thr], "crossings": ncross}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=sorted(SETS), required=True)
    args = ap.parse_args()
    imgs, meta_path, out = SETS[args.set]
    out.mkdir(exist_ok=True)
    for key, m in json.loads(meta_path.read_text()).items():
        stem = key.replace("_jpg", "")
        img = imgs / f"{stem}.png"
        if not img.exists():
            print(f"  skip {stem} (no image)")
            continue
        rgb, meta = build(img, m["bboxes"])
        cv2.imwrite(str(out / f"{stem}.png"), rgb[:, :, ::-1])
        (out / f"{stem}.json").write_text(json.dumps(meta))
        multi = sum(len(t) >= 2 for t in meta["conductors"].values())
        print(f"{stem}: {len(meta['conductors'])} conductors ({multi} link >=2 parts), "
              f"{meta['dropped']} dropped, {meta['crossings']} crossings split, thresholds={meta['thresholds']}")


if __name__ == "__main__":
    main()

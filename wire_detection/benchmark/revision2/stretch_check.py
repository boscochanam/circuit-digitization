#!/usr/bin/env python3
"""Verify that the 31 benchmark images (704x704) are Roboflow STRETCH resizes of (a dihedral
transform of) the CGHD-1152 source -- either the photo or its binary segmentation map --
EXIF-corrected CGHD-1152 originals.

For each stem: load the original, apply EXIF transpose, convert to gray, resize to 704x704
(no aspect preservation), and compare to the benchmark image by PSNR and Pearson correlation.
As controls, also compare (a) without EXIF transpose and (b) a letterboxed (aspect-preserving,
padded) resize.

Run on claw:
  PYTHONPATH=~/circuit-digitization /home/claw/venv-ml/bin/python stretch_check.py \
      --gt ~/circuit-digitization/ground_truth/real_nets_verified.json --out stretch_check.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

GT_IMAGES = Path(os.environ.get("WIRE_GT_IMAGES", "/home/claw/workspace/ground_truth/labels_few_annot/images"))
CGHD = Path(os.environ.get("CGHD_ORIG", str(Path.home() / "cghd_orig/cghd")))


def find_original(stem: str) -> Path | None:
    for ext in ("jpg", "jpeg", "png", "JPG", "JPEG", "PNG"):
        hits = glob.glob(str(CGHD / "drafter_*" / "images" / f"{stem}.{ext}"))
        if hits:
            return Path(hits[0])
    return None


def load_original(path: Path, exif: bool = True) -> np.ndarray:
    im = Image.open(path)
    if exif:
        im = ImageOps.exif_transpose(im)
    return np.array(im.convert("L"))


def psnr(a, b):
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def corr(a, b):
    a = a.astype(np.float64).ravel(); b = b.astype(np.float64).ravel()
    a -= a.mean(); b -= b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d else 0.0


def letterbox(img, size):
    h, w = img.shape
    s = size / max(h, w)
    nh, nw = round(h * s), round(w * s)
    r = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    out = np.full((size, size), 255, np.uint8)
    y0, x0 = (size - nh) // 2, (size - nw) // 2
    out[y0:y0 + nh, x0:x0 + nw] = r
    return out


# dihedral transforms applied to the (EXIF-corrected) original BEFORE the stretch resize.
# name -> fn(img). Point mapping for each is in e2e_detected.py (same names).
DIHEDRAL = {
    "id": lambda a: a,
    "fliplr": lambda a: a[:, ::-1],
    "flipud": lambda a: a[::-1, :],
    "rot180": lambda a: a[::-1, ::-1],
    "transpose": lambda a: a.T,
    "rot90cw": lambda a: np.rot90(a, -1),
    "rot90ccw": lambda a: np.rot90(a, 1),
    "antitranspose": lambda a: np.rot90(a, 2).T,
}


def find_seg(stem: str) -> Path | None:
    for ext in ("jpg", "jpeg", "png", "JPG", "JPEG", "PNG"):
        hits = glob.glob(str(CGHD / "drafter_*" / "segmentation" / f"{stem}.{ext}"))
        if hits:
            return Path(hits[0])
    return None


def best_match(src: np.ndarray, bench: np.ndarray):
    bh, bw = bench.shape
    res = {}
    for name, fn in DIHEDRAL.items():
        a = np.ascontiguousarray(fn(src))
        r = cv2.resize(a, (bw, bh), interpolation=cv2.INTER_AREA)
        res[name] = (corr(r, bench), psnr(r, bench))
    name = max(res, key=lambda k: res[k][0])
    return name, res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out", default="stretch_check.json")
    args = ap.parse_args()
    stems = [k.replace("_jpg", "") for k in json.load(open(args.gt))]
    rows = []
    for stem in stems:
        bench = cv2.imread(str(GT_IMAGES / f"{stem}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        op = find_original(stem)
        if bench is None or op is None:
            rows.append({"stem": stem, "error": "missing"}); continue
        exif_orient = Image.open(op).getexif().get(0x0112, 1)
        orig = load_original(op, exif=True)
        orig_noexif = load_original(op, exif=False)
        H, W = orig.shape
        bh, bw = bench.shape
        rec = {"stem": stem, "orig_path": str(op), "orig_wh": [W, H], "bench_wh": [bw, bh],
               "exif_orientation": int(exif_orient), "aspect_w_over_h": round(W / H, 4)}
        sp = find_seg(stem)
        cands = {"image_exif": orig, "image_noexif": orig_noexif}
        if sp is not None:
            seg = load_original(sp, exif=True)
            rec["seg_path"] = str(sp); rec["seg_wh"] = [seg.shape[1], seg.shape[0]]
            cands["seg"] = seg
        best = None
        for src_name, src in cands.items():
            tname, res = best_match(src, bench)
            c, q = res[tname]
            rec[src_name] = {"best_transform": tname, "corr": round(c, 4), "psnr": round(q, 2),
                             "corr_identity": round(res["id"][0], 4)}
            if best is None or c > best[2]:
                best = (src_name, tname, c, q)
        # letterbox control on the best source/transform
        src = np.ascontiguousarray(DIHEDRAL[best[1]](cands[best[0]]))
        lb = letterbox(src, bw)
        rec["letterbox_control"] = {"corr": round(corr(lb, bench), 4), "psnr": round(psnr(lb, bench), 2)}
        rec["best"] = {"source": best[0], "transform": best[1], "corr": round(best[2], 4), "psnr": round(best[3], 2)}
        rows.append(rec)
        print(stem, rec["orig_wh"], "exif", exif_orient, "best", rec["best"], "lb", rec["letterbox_control"])
    ok = [r for r in rows if "error" not in r]
    from collections import Counter
    summ = {
        "n": len(rows), "n_found": len(ok),
        "best_source_counts": dict(Counter(r["best"]["source"] for r in ok)),
        "best_transform_counts": dict(Counter(r["best"]["transform"] for r in ok)),
        "best_corr_min": min(r["best"]["corr"] for r in ok),
        "best_corr_median": float(np.median([r["best"]["corr"] for r in ok])),
        "best_psnr_min": min(r["best"]["psnr"] for r in ok),
        "best_psnr_median": float(np.median([r["best"]["psnr"] for r in ok])),
        "letterbox_corr_median": float(np.median([r["letterbox_control"]["corr"] for r in ok])),
        "n_exif_rotated": sum(1 for r in ok if r["exif_orientation"] not in (0, 1)),
        "aspect_min": min(r["aspect_w_over_h"] for r in ok), "aspect_max": max(r["aspect_w_over_h"] for r in ok),
        "aspect_median": float(np.median([r["aspect_w_over_h"] for r in ok])),
        "n_non_square": sum(1 for r in ok if abs(r["aspect_w_over_h"] - 1) > 0.01),
        "orig_long_side_median": float(np.median([max(r["orig_wh"]) for r in ok])),
    }
    json.dump({"summary": summ, "per_image": rows}, open(args.out, "w"), indent=2)
    print(json.dumps(summ, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

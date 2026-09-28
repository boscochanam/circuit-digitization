#!/usr/bin/env python3
"""Choose the input resolution for running the FROZEN wire extractor on CGHD originals, using
only wire-level ground truth (never a join/connectivity score).

The extractor's pixel parameters (Sauvola window 67, CCL min_area 28, dedup 8 px, anchor 16 px)
were tuned on 704x704 stretched copies. On the 52 CGHD samples that also carry our human wire
labels (ground_truth/wire_labels, benchmark frame) we compare:

  A  benchmark condition: 704x704 benchmark copy + our committed component labels (paper setup)
  A' 704x704 benchmark copy + CGHD polygons mapped into that frame
  B  EXIF-corrected CGHD original resized with PRESERVED aspect, CGHD polygons scaled:
       long704   long side = 704
       area704   sqrt(W*H) = 704  (same pixel count as the benchmark copies)
       long880, long1024
     detected segments are mapped back into the benchmark frame (normalise, dihedral k,
     x704) and scored with the paper's wire matcher (reference_pipeline.evaluate, 20 px).

Rule fixed before running: take the preserved-aspect PHOTO candidate with the highest pooled wire
F1 (the long-side grid was extended to 1280/1536 after 1024 came out on top of the first grid;
still wire-level only, no join score was computed before the choice was fixed).
Note: 45/52 of these benchmark copies are the CGHD binary stroke map, not the photo (see
docs/research/experiments/revision2/e2e_detected_n31.md), so A is not a photo condition;
seg_* rows run the extractor on the stroke map for the modality comparison.

  PYTHONPATH=~/circuit-digitization python cghd_resolution.py --probe out/transform_probe.json \
      --out out/cghd_resolution.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cghd_common import (BENCH_IMAGES, dihedral_array, dihedral_norm, list_samples, load_gray,  # noqa
                         load_shapes, load_stroke_mask, shapes_to_components)

REPO = Path.home() / "circuit-digitization"
CANDIDATES = {"stretch704_area": ("stretch", 704, cv2.INTER_AREA),
              "stretch704_linear": ("stretch", 704, cv2.INTER_LINEAR),
              "long704": ("long", 704), "area704": ("area", 704), "long880": ("long", 880),
              "long1024": ("long", 1024), "long1280": ("long", 1280), "long1536": ("long", 1536),
              # modality reference (NOT candidates): the CGHD binary stroke map as input
              "seg_stretch704": ("stretch", 704, cv2.INTER_AREA, "seg"),
              "seg_long1024": ("long", 1024, cv2.INTER_AREA, "seg")}
PHOTO_CANDIDATES = [c for c, r in CANDIDATES.items() if r[0] != "stretch" and (len(r) < 4 or r[3] != "seg")]


def target_size(W, H, rule):
    kind, v = rule[0], rule[1]
    if kind == "stretch":
        return v, v
    s = v / max(W, H) if kind == "long" else v / math.sqrt(W * H)
    return max(1, int(round(W * s))), max(1, int(round(H * s)))


def prep(gray_full, shapes, size, interp=cv2.INTER_AREA):
    w, h = size
    H, W = gray_full.shape
    g = cv2.resize(gray_full, (w, h), interpolation=interp)
    return g, shapes_to_components(shapes, w / W, h / H)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    from wire_detection.benchmark.join_eval_134 import detect_wires
    from wire_detection.benchmark import reference_pipeline as ref
    probe = {r["stem"]: r for r in json.load(open(args.probe))}
    dmap = {s: d for d, s in list_samples()}
    WL = REPO / "ground_truth/wire_labels"
    CL = REPO / "ground_truth/component_labels"
    stems = sorted(s for s, r in probe.items() if r["has_wire_labels"])
    conds = ["A_bench_ourlabels", "A_bench_cghdpolys"] + list(CANDIDATES)
    per = {c: {} for c in conds}
    bench_bin = {}
    for stem in stems:
        d = dmap[stem]; k = probe[stem]["k_box"] if probe[stem]["k_box"] is not None else probe[stem]["k_ink"]
        g7 = cv2.imread(str(BENCH_IMAGES / f"{stem}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        h7, w7 = g7.shape
        gt = ref.load_ground_truth(WL / f"{stem}_jpg.txt", w7, h7)
        bench_bin[stem] = float(((g7 < 30) | (g7 > 225)).mean())
        full = load_gray(d, stem); H, W = full.shape
        seg = np.where(load_stroke_mask(d, stem), 0, 255).astype(np.uint8)
        shapes, _, _ = load_shapes(d, stem)

        def score(c, lines):
            tp, fp, fn, red = ref.evaluate(lines, gt)
            per[c][stem] = [tp, fp, fn, red]

        # A: paper condition
        comps = ref.parse_components(CL / f"{stem}_jpg.txt", w7, h7)
        score("A_bench_ourlabels", detect_wires(g7, comps))
        # A': CGHD polygons mapped into the benchmark frame
        sh7 = []
        for s in shapes:
            p = s["points"] / [W, H]
            x, y = dihedral_norm(p[:, 0], p[:, 1], k)
            sh7.append({"label": s["label"], "points": np.stack([x * w7, y * h7], 1)})
        score("A_bench_cghdpolys", detect_wires(g7, shapes_to_components(sh7, 1.0, 1.0)))
        # B: preserved-aspect resizes of the original
        for c, rule in CANDIDATES.items():
            w, h = target_size(W, H, rule)
            src = seg if len(rule) > 3 and rule[3] == "seg" else full
            g, cp = prep(src, shapes, (w, h), rule[2] if len(rule) > 2 else cv2.INTER_AREA)
            lines = detect_wires(g, cp)
            mapped = []
            for (a, b) in lines:
                pa = dihedral_norm(a[0] / w, a[1] / h, k); pb = dihedral_norm(b[0] / w, b[1] / h, k)
                mapped.append(((int(round(pa[0] * w7)), int(round(pa[1] * h7))),
                               (int(round(pb[0] * w7)), int(round(pb[1] * h7)))))
            score(c, mapped)
        print(stem, {c: per[c][stem] for c in conds}, flush=True)

    summ = {}
    for c in conds:
        T = np.array(list(per[c].values()))
        tp, fp, fn, red = T.sum(0)
        P = tp / max(tp + fp + red, 1); R = tp / max(tp + fn, 1); F = 2 * P * R / max(P + R, 1e-9)
        pf = [2 * (t / max(t + f + r, 1)) * (t / max(t + n, 1)) / max(t / max(t + f + r, 1) + t / max(t + n, 1), 1e-9)
              for t, f, n, r in T]
        summ[c] = {"tp": int(tp), "fp": int(fp), "fn": int(fn), "red": int(red), "p": P, "r": R, "f1": F,
                   "macro_f1": float(np.mean(pf))}
        print(f"{c:<20} F1={F:.4f} P={P:.4f} R={R:.4f} macroF1={np.mean(pf):.4f}")
    chosen = max(PHOTO_CANDIDATES, key=lambda c: summ[c]["f1"])
    # modality split of the paper condition: which benchmark copies are CGHD stroke maps
    for c in ("A_bench_ourlabels", chosen):
        for mod in ("bench_is_segmap", "bench_is_photo"):
            sel = [s for s in stems if (bench_bin[s] > 0.9) == (mod == "bench_is_segmap")]
            T = np.array([per[c][s] for s in sel]); tp, fp, fn, red = T.sum(0)
            P = tp / max(tp + fp + red, 1); R = tp / max(tp + fn, 1)
            summ.setdefault("by_modality", {})[f"{c}|{mod}"] = {"n": len(sel), "f1": 2 * P * R / max(P + R, 1e-9), "p": P, "r": R}
            print(c, mod, len(sel), round(2 * P * R / max(P + R, 1e-9), 4))
    print("chosen:", chosen)
    json.dump({"n": len(stems), "summary": summ, "chosen": chosen, "rule": "max pooled wire F1 among "
               "preserved-aspect candidates", "candidates": {c: [str(x) for x in v] for c, v in CANDIDATES.items()},
               "photo_candidates": PHOTO_CANDIDATES, "bench_binary_fraction": bench_bin, "per_image": per}, open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()

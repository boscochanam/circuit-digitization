#!/usr/bin/env python3
"""Input-preprocessing ablation on the 17 images that are both human-net-verified and in the CGHD
polygon subset. Nothing is tuned: frozen extractor + scale_completion, our committed component
labels (normalised, benchmark frame), human nets as labels, same pair metric as join_eval_real_f1.

Inputs (all in the benchmark copy's orientation, dihedral k from transform_probe.json):
  i   benchmark 704x704 copy (paper condition)
  ii  CGHD photo, EXIF-corrected, oriented like the copy, stretched to 704x704
  iii photo, aspect preserved, long side 704
  iv  photo, aspect preserved, long side 1024 (the CGHD-benchmark input)
  v   CGHD stroke map, oriented, stretched to 704x704 (modality reference)

  PYTHONPATH=~/circuit-digitization python cghd_input_ablation.py --probe out/transform_probe.json --out out/cghd_input_ablation.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cghd_common import BENCH_IMAGES, dihedral_array, list_samples, load_gray, load_stroke_mask  # noqa

REPO = Path.home() / "circuit-digitization"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    from wire_detection.benchmark.join_eval_134 import detect_wires
    from wire_detection.benchmark.join_eval_real_f1 import comp_pairs, gt_pairs
    from wire_detection.benchmark.reference_pipeline import parse_components
    from wire_detection.core.join_strategies import make_pins, run_strategy
    probe = {r["stem"]: r for r in json.load(open(args.probe))}
    human = json.load(open(REPO / "ground_truth/real_nets_verified.json"))
    dmap = {s: d for d, s in list_samples()}
    stems = sorted(k[:-4] for k in human if k[:-4] in dmap)
    conds = ["i_bench704", "ii_photo_stretch704", "iii_photo_long704", "iv_photo_long1024", "v_seg_stretch704"]
    per = {c: {} for c in conds}
    modality = {}
    for s in stems:
        d = dmap[s]; k = probe[s]["k_box"]
        e = human[f"{s}_jpg"]; keep = set(e["electrical_idxs"])
        gtp = gt_pairs(e["nets"], keep)
        b = cv2.imread(str(BENCH_IMAGES / f"{s}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        modality[s] = "segmap" if float(((b < 30) | (b > 225)).mean()) > 0.9 else "photo"
        photo = dihedral_array(load_gray(d, s), k)
        seg = dihedral_array(np.where(load_stroke_mask(d, s), 0, 255).astype(np.uint8), k)
        H, W = photo.shape
        imgs = {"i_bench704": b,
                "ii_photo_stretch704": cv2.resize(photo, (704, 704), interpolation=cv2.INTER_AREA),
                "v_seg_stretch704": cv2.resize(seg, (704, 704), interpolation=cv2.INTER_AREA)}
        for c, L in (("iii_photo_long704", 704), ("iv_photo_long1024", 1024)):
            sc = L / max(W, H)
            imgs[c] = cv2.resize(photo, (int(round(W * sc)), int(round(H * sc))), interpolation=cv2.INTER_AREA)
        for c in conds:
            g = imgs[c]; h, w = g.shape
            comps = parse_components(REPO / "ground_truth/component_labels" / f"{s}_jpg.txt", w, h)
            assert len(comps) == e["n_components"]
            wires = detect_wires(g, comps)
            _p, nl = run_strategy("scale_completion", wires, comps, std_pins=make_pins(wires, comps))
            pred = comp_pairs(nl, keep)
            per[c][s] = [len(gtp & pred), len(pred - gtp), len(gtp - pred)]
        print(s, modality[s], {c: per[c][s] for c in conds}, flush=True)
    summ = {}
    for grp in ("all", "photo", "segmap"):
        sel = [s for s in stems if grp == "all" or modality[s] == grp]
        for c in conds:
            tp, fp, fn = np.array([per[c][s] for s in sel]).sum(0)
            P = tp / max(tp + fp, 1); R = tp / max(tp + fn, 1)
            summ[f"{grp}|{c}"] = {"n": len(sel), "tp": int(tp), "fp": int(fp), "fn": int(fn),
                                  "p": P, "r": R, "f1": 2 * P * R / max(P + R, 1e-9)}
            print(f"{grp:<7}{c:<22} n={len(sel):>2} F1={summ[f'{grp}|{c}']['f1']:.3f} P={P:.3f} R={R:.3f}")
    json.dump({"stems": stems, "modality_of_bench_copy": modality, "summary": summ, "per_image": per},
              open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()

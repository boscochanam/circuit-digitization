#!/usr/bin/env python3
"""Evaluate the FROZEN pipeline and baselines against the CGHD-annotation connectivity reference
(cghd_ref.py, variant v2). Produces per-image tp/fp/fn for every method; statistics are computed
locally by cghd_stats.py (pure numpy, no images).

Per sample (all 257 with instance polygons):
  input  : EXIF-corrected photo resized with preserved aspect so the long side is 1024 px
           (choice fixed on wire-level GT by cghd_resolution.py before any join score was
           computed). Secondary condition "seg": the CGHD binary stroke map at the same size
           (NOT independent of the reference, which is built from that map: upper-bound only).
  comps  : CGHD instance polygons -> our component tuples (cghd_common.shapes_to_components),
           class names mapped to our 58-class ids. Same index order as the reference.
  wires  : our frozen best_candidate_v4 extractor (join_eval_134.detect_wires).
  methods: join strategies scale_completion (ours, DEFAULT_STRATEGY), degree_budget, graph_scale,
           graph_rescue, production (run_strategy, unmodified); Hough+proximity
           (hough_baseline.hough_nets, all 7 configs; link44_reach48 is the config the paper
           selected on the 31 images); CCL on detected wires (cc_baseline_detected, dilates
           3/7/11/15; d15 is the paper's selected config).
  score  : component-pair connectivity over the reference's electrical subset (identical to
           join_eval_real_f1: pairs of electrical components sharing a net).

  PYTHONPATH=~/circuit-digitization python cghd_eval.py --ref out/cghd_ref_nets_v2.json \
      --out out/cghd_eval_photo.json [--input seg]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cghd_common import list_samples, load_gray, load_shapes, load_stroke_mask, shapes_to_components  # noqa

JOIN = ["scale_completion", "degree_budget", "graph_scale", "graph_rescue", "production"]
HOUGH = [("link10_reach22", 10, 22), ("link14_reach26", 14, 26), ("link20_reach30", 20, 30),
         ("link28_reach36", 28, 36), ("link36_reach42", 36, 42), ("link44_reach48", 44, 48),
         ("link56_reach56", 56, 56)]
DILATES = [3, 7, 11, 15]
LONG_SIDE = 1024


def ref_pairs(nets, keep):
    out = set()
    for net in nets:
        m = sorted({int(c) for c, _ in net if int(c) in keep})
        out.update(combinations(m, 2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--input", default="photo", choices=["photo", "seg"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    from wire_detection.benchmark.join_eval_134 import detect_wires
    from wire_detection.benchmark.join_eval_real_f1 import comp_pairs
    from wire_detection.benchmark.hough_baseline import hough_nets, pairs_from_pinnet
    from wire_detection.benchmark.cc_baseline_detected import detected_wire_ccl
    from wire_detection.benchmark.cc_baseline import pairs_from_pinnet as cc_pairs
    from wire_detection.core.join_strategies import DEFAULT_STRATEGY, make_pins, make_pins_junction_aware, run_strategy
    assert DEFAULT_STRATEGY == "scale_completion", DEFAULT_STRATEGY
    ref = json.load(open(args.ref))
    samples = list_samples()
    if args.limit:
        samples = samples[:args.limit]
    out = {"input": args.input, "long_side": LONG_SIDE, "ref": args.ref,
           "ref_variant": ref["_provenance"].get("variant"), "images": {}}
    t0 = time.time()
    for n, (d, stem) in enumerate(samples):
        r = ref[stem]
        shapes, _, _ = load_shapes(d, stem)
        assert len(shapes) == r["n_components"]
        src = load_gray(d, stem) if args.input == "photo" else \
            np.where(load_stroke_mask(d, stem), 0, 255).astype(np.uint8)
        H, W = src.shape
        s = LONG_SIDE / max(W, H)
        w, h = int(round(W * s)), int(round(H * s))
        gray = cv2.resize(src, (w, h), interpolation=cv2.INTER_AREA)
        comps = shapes_to_components(shapes, w / W, h / H)
        keep = set(r["electrical_idxs"])
        gtp = ref_pairs(r["nets"], keep)
        wires = detect_wires(gray, comps)
        std = make_pins(wires, comps)
        junc = make_pins_junction_aware(wires, comps)
        rec = {"drafter": d, "n_components": len(comps), "n_electrical": len(keep), "n_ref_pairs": len(gtp),
               "n_wires": len(wires), "img_wh": [w, h], "clean": r["clean"], "methods": {}}

        rec["pred_pairs"] = {}

        def put(name, pred):
            rec["methods"][name] = [len(gtp & pred), len(pred - gtp), len(gtp - pred)]
            rec["pred_pairs"][name] = sorted([int(a), int(b)] for a, b in pred)
        for m in JOIN:
            _p, nl = run_strategy(m, wires, comps, std_pins=std, junc_pins=junc)
            put(m, comp_pairs(nl, keep))
        pins0 = make_pins([], comps)
        for cname, link, reach in HOUGH:
            put(f"hough_{cname}", pairs_from_pinnet(hough_nets(gray, comps, pins0, link_tol=link, reach=reach), keep))
        for dl in DILATES:
            put(f"cc_detCCL_d{dl}", cc_pairs(detected_wire_ccl(gray, comps, std, wires, dilate=dl), keep))
        out["images"][stem] = rec
        mm = rec["methods"]
        print(f"{n+1:>3} {stem:<12} {d:<11} elec={len(keep):>3} pairs={len(gtp):>4} wires={len(wires):>4} "
              f"ours={mm['scale_completion']} hough44={mm['hough_link44_reach48']} cc15={mm['cc_detCCL_d15']} "
              f"[{time.time()-t0:.0f}s]", flush=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print("wrote", args.out)


if __name__ == "__main__":
    main()

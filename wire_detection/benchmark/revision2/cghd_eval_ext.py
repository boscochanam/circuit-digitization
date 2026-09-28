#!/usr/bin/env python3
"""Re-run the FROZEN photo-input evaluation (exactly cghd_eval.py's per-image path) on the 164
held-out clean images, storing PIN-LEVEL predicted nets over ALL components for every method.

Why: cghd_eval.py stores only predicted pairs restricted to the electrical subset, which cannot be
re-scored over a larger component set (extended-components variant) or after closing switches
(switch-closed variant, which needs the nodes on both sides of every switch). Nothing is re-tuned:
input (photo, long side 1024, INTER_AREA), components (CGHD polygons -> our tuples), wires
(join_eval_134.detect_wires), pins (make_pins / make_pins_junction_aware), strategies and the two
paper-selected baseline configs (Hough link44_reach48, CCL d15) are the ones of cghd_eval.py.

Per image and method we store ``nodes``: a list of [[ci, pin_name], ...] (every predicted node with
>=1 pin; Hough/CCL pins with label -1 are unattached and dropped) plus ``pairs_elec``, the pairs
over the electrical subset computed with the ORIGINAL helpers (comp_pairs / pairs_from_pinnet), for
the reproduction check against the stored cghd_eval_photo.json.

  PYTHONPATH=~/circuit-digitization python cghd_eval_ext.py --ref out/cghd_ref_nets_v2.json \
      --stems out/ho164.txt --out out/cghd_eval_ext_photo.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cghd_common import list_samples, load_gray, load_shapes, shapes_to_components  # noqa: E402

JOIN = ["scale_completion", "degree_budget", "graph_scale", "graph_rescue", "production"]
HOUGH = [("link44_reach48", 44, 48)]
DILATES = [15]
LONG_SIDE = 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--stems", required=True, help="whitespace-separated stem list")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    from wire_detection.benchmark.join_eval_134 import detect_wires
    from wire_detection.benchmark.join_eval_real_f1 import comp_pairs
    from wire_detection.benchmark.hough_baseline import hough_nets, pairs_from_pinnet
    from wire_detection.benchmark.cc_baseline_detected import detected_wire_ccl
    from wire_detection.benchmark.cc_baseline import pairs_from_pinnet as cc_pairs
    from wire_detection.core.join_strategies import DEFAULT_STRATEGY, make_pins, make_pins_junction_aware, run_strategy
    assert DEFAULT_STRATEGY == "scale_completion", DEFAULT_STRATEGY
    ref = json.load(open(args.ref))
    want = set(open(args.stems).read().split())
    samples = [s for s in list_samples() if s[1] in want]
    assert len(samples) == len(want), (len(samples), len(want))
    out = {"input": "photo", "long_side": LONG_SIDE, "ref": args.ref, "images": {}}
    t0 = time.time()
    for n, (d, stem) in enumerate(samples):
        r = ref[stem]
        shapes, _, _ = load_shapes(d, stem)
        assert len(shapes) == r["n_components"]
        src = load_gray(d, stem)
        H, W = src.shape
        s = LONG_SIDE / max(W, H)
        w, h = int(round(W * s)), int(round(H * s))
        gray = cv2.resize(src, (w, h), interpolation=cv2.INTER_AREA)
        comps = shapes_to_components(shapes, w / W, h / H)
        keep = set(r["electrical_idxs"])
        wires = detect_wires(gray, comps)
        std = make_pins(wires, comps)
        junc = make_pins_junction_aware(wires, comps)
        rec = {"drafter": d, "n_components": len(comps), "labels": [x["label"] for x in shapes],
               "n_wires": len(wires), "methods": {}}

        def put_nl(name, nl, pairs):
            by = defaultdict(list)
            for (ci, pn), nid in nl.pin_to_node.items():
                by[nid].append([int(ci), str(pn)])
            rec["methods"][name] = {"nodes": [sorted(v) for _k, v in sorted(by.items())],
                                    "pairs_elec": sorted([int(a), int(b)] for a, b in pairs)}

        def put_pn(name, pin_net, pairs):
            by = defaultdict(list)
            for (ci, pn), lab in pin_net.items():
                if lab != -1:
                    by[lab].append([int(ci), str(pn)])
            rec["methods"][name] = {"nodes": [sorted(v) for _k, v in sorted(by.items(), key=lambda kv: str(kv[0]))],
                                    "pairs_elec": sorted([int(a), int(b)] for a, b in pairs)}
        for m in JOIN:
            _p, nl = run_strategy(m, wires, comps, std_pins=std, junc_pins=junc)
            put_nl(m, nl, comp_pairs(nl, keep))
        pins0 = make_pins([], comps)
        for cname, link, reach in HOUGH:
            pn = hough_nets(gray, comps, pins0, link_tol=link, reach=reach)
            put_pn(f"hough_{cname}", pn, pairs_from_pinnet(pn, keep))
        for dl in DILATES:
            pn = detected_wire_ccl(gray, comps, std, wires, dilate=dl)
            put_pn(f"cc_detCCL_d{dl}", pn, cc_pairs(pn, keep))
        out["images"][stem] = rec
        print(f"{n+1:>3} {stem:<12} {d:<11} wires={len(wires):>4} [{time.time()-t0:.0f}s]", flush=True)
    json.dump(out, open(args.out, "w"))
    print("wrote", args.out)


if __name__ == "__main__":
    main()

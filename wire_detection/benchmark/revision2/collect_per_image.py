#!/usr/bin/env python3
"""Revision-2 (Access-2026-33821) per-image input collector.

Produces docs/research/experiments/revision2/per_image_inputs_n31.json with, for each of the
31 human-verified images (GT iteration order):

  * Hough+proximity per-image tp/fp/fn for EVERY config in hough_baseline.CONFIGS (the
    committed hough_micro_n31.json only stores pooled counts). Uses hough_baseline.hough_nets
    unchanged, so the pooled counts must reproduce hough_micro_n31.json exactly (asserted).
  * Component statistics: bbox diagonals over ALL parsed components (exactly the set that
    join_graph.estimate_scale sees; s = sorted(diags)[n//2]) and over the electrical subset,
    per-class counts (crossover = class 5), n GT pairs.

It reads the original CGHD JPEGs and the identity-matched HDC OBB labels through the same
build_net_gt.find_hdc_label / parse_components that every join eval uses. It does NOT touch
pipeline code or any committed result JSON.

The committed per_image_inputs_n31.json was produced ON CLAW, where it reproduces the pooled
hough_micro_n31.json counts exactly for all 7 configs. CAUTION: a local roboflow_test2/ may be a
different Roboflow export whose ".rf.<hash>" copies are not the identity copies; the script
therefore also checks every selected label against the committed identity labels in
ground_truth/component_labels/ and records `label_matches_committed` per image (on claw: 31/31).

Rerun on claw (default data paths), from a scratch copy:
  cd ~/circuit-digitization && REV2_REPO=$PWD PYTHONPATH=$PWD \
    ./.venv/bin/python ~/rev2_scratch/collect_per_image.py --out ~/rev2_scratch/out/per_image_inputs_n31.json
(also works locally with WIRE_GT_IMAGES=ground_truth/local_eval/images if the HDC labels
match). Then run stats_strata.py (pure, no images needed).
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import cv2

from wire_detection.benchmark.build_net_gt import GT_IMAGES, find_hdc_label, parse_components
from wire_detection.benchmark.hough_baseline import hough_nets, pairs_from_pinnet
from wire_detection.benchmark.join_eval_real_f1 import gt_pairs
from wire_detection.core.join_graph import estimate_scale
from wire_detection.core.join_strategies import make_pins

import os
REPO = Path(os.environ.get("REV2_REPO", Path(__file__).resolve().parents[3]))
EXP = REPO / "docs/research/experiments"
HOUGH_CONFIGS = [("link10_reach22", 10, 22), ("link14_reach26", 14, 26),
                 ("link20_reach30", 20, 30), ("link28_reach36", 28, 36),
                 ("link36_reach42", 36, 42), ("link44_reach48", 44, 48),
                 ("link56_reach56", 56, 56)]  # identical to hough_baseline.main()
CROSSOVER_CLS = 5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default=str(REPO / "ground_truth/real_nets_verified.json"))
    ap.add_argument("--out", default=str(EXP / "revision2/per_image_inputs_n31.json"))
    args = ap.parse_args()
    gt = json.load(open(args.gt))
    out = {"gt_file": str(Path(args.gt).relative_to(REPO)) if args.gt.startswith(str(REPO)) else args.gt,
           "images": {}}
    pooled = {c: [0, 0, 0] for c, _, _ in HOUGH_CONFIGS}
    for img_id, entry in gt.items():
        name = img_id.replace("_jpg", "")
        gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        hdc = find_hdc_label(name)
        if gray is None or hdc is None:
            raise SystemExit(f"missing image/labels for {name} (GT_IMAGES={GT_IMAGES})")
        h, w = gray.shape
        comps = parse_components(hdc.read_text(), w, h)
        if len(comps) != entry["n_components"]:
            raise SystemExit(f"{name}: parsed {len(comps)} comps != GT n_components {entry['n_components']}")
        keep = set(entry["electrical_idxs"])
        gtp = gt_pairs(entry["nets"], keep)
        pins = make_pins([], comps)
        committed = REPO / "ground_truth/component_labels" / f"{img_id}.txt"
        rec = {"hough": {}, "label_matches_committed":
               (committed.read_text() == hdc.read_text()) if committed.exists() else None}
        for cname, link, reach in HOUGH_CONFIGS:
            pred = pairs_from_pinnet(hough_nets(gray, comps, pins, link_tol=link, reach=reach), keep)
            tp, fp, fn = len(gtp & pred), len(pred - gtp), len(gtp - pred)
            rec["hough"][cname] = [tp, fp, fn]
            for k, v in enumerate((tp, fp, fn)):
                pooled[cname][k] += v
        diags_all = [math.hypot(b[2] - b[0], b[3] - b[1]) for _c, _v, b in comps]
        diags_el = [diags_all[i] for i in sorted(keep)]
        cls_counts = Counter(int(c) for c, _v, _b in comps)
        rec.update({
            "img_wh": [w, h],
            "hdc_label": hdc.name,
            "n_components_all": len(comps),
            "n_electrical": len(keep),
            "n_gt_pairs": len(gtp),
            "n_nets": len(entry["nets"]),
            "n_crossover": cls_counts.get(CROSSOVER_CLS, 0),
            "class_counts": {str(k): v for k, v in sorted(cls_counts.items())},
            "scale_s": estimate_scale(comps, []),
            "diags_all": [round(d, 3) for d in diags_all],
            "diags_electrical": [round(d, 3) for d in diags_el],
            "electrical_classes": [int(comps[i][0]) for i in sorted(keep)],
        })
        out["images"][img_id] = rec
        print(f"{name:<14} comps={len(comps):>3} elec={len(keep):>2} pairs={len(gtp):>3} "
              f"xover={rec['n_crossover']} s={rec['scale_s']:.1f} hough44={rec['hough']['link44_reach48']}")
    ref = json.load(open(EXP / "hough_micro_n31.json"))["configs"]
    for cname, (tp, fp, fn) in pooled.items():
        r = ref[cname]["micro"]
        ok = (tp, fp, fn) == (r["tp"], r["fp"], r["fn"])
        print(f"hough {cname}: pooled {tp}/{fp}/{fn} vs committed {r['tp']}/{r['fp']}/{r['fn']} "
              f"{'OK' if ok else 'MISMATCH'}")
        out.setdefault("hough_reproduction", {})[cname] = {"pooled": [tp, fp, fn],
                                                           "committed": [r["tp"], r["fp"], r["fn"]],
                                                           "match": ok}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

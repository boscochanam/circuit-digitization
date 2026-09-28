#!/usr/bin/env python3
"""Controlled image-rescaling robustness of the join (R1-3 / R2-6, Access-2026-33821).

Every one of the 31 human-verified net-GT images is resampled by a factor f
(cv2.INTER_AREA for f<1, INTER_CUBIC for f>1). Component OBBs and GT wire labels
are YOLO-normalised, so they are re-projected exactly onto the resized W x H grid
with the SAME parsers the paper's evaluation uses (parse_components /
parse_gt_wires); at f=1.0 everything is byte-identical to join_eval_real_f1 /
detection_ceiling.

Arms
  A  join only : human-traced GT wires (scaled) + GT boxes (scaled)
  B  full      : wires re-extracted from the rescaled image with the FROZEN
                 extractor (pixel-valued Sauvola window, min_area, ...) + GT boxes

Methods (nothing in the pipeline is modified; the "unclamped" and "fixed-px"
completion variants are obtained by swapping completion-module globals inside
this process only)
  scale_completion           shipped default (scale-relative, clamped tolerances)
  scale_completion_unclamped same, tau = k*s with the pixel clamps removed
  fixedpx_completion         same algorithm, all tolerances fixed pixels
                             (tau_pin 30 / tau_join 14 / tau_t 10, completion tau 30,
                             reach 4*30=120px) -- the fixed-px ablation config
  graph_scale                scale-relative base graph, no completion
  graph_dir_30               fixed-pixel base graph (registry), no completion
  production                 radius union-find, fixed 30px (legacy)

Run on claw:
  PYTHONPATH=~/circuit-digitization ~/circuit-digitization/.venv/bin/python \
      rescale_eval.py --out rescale_n31.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import time
from multiprocessing import Pool
from pathlib import Path

import cv2

REPO = Path(os.environ.get("CIRCUIT_REPO", Path.home() / "circuit-digitization"))
os.chdir(REPO)  # detector CFG / relative paths resolve against the repo

from wire_detection.benchmark.build_net_gt import (  # noqa: E402
    GT_IMAGES, GT_WIRE_LABELS, find_hdc_label, parse_components, parse_gt_wires)
from wire_detection.benchmark.join_eval_134 import detect_wires  # noqa: E402
from wire_detection.benchmark.join_eval_real_f1 import comp_pairs, gt_pairs  # noqa: E402
from wire_detection.core.join_graph import estimate_scale  # noqa: E402
from wire_detection.core.join_strategies import make_pins, make_pins_junction_aware  # noqa: E402

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from methods import (FIXED, FIXED_COMPLETION_TAU, K, METHODS, REACH,  # noqa: E402
                     run_method)

FACTORS = [0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]


def resize(gray, f):
    if f == 1.0:
        return gray
    h, w = gray.shape
    W, H = max(1, round(w * f)), max(1, round(h * f))
    return cv2.resize(gray, (W, H), interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC)


def job(args):
    img_id, entry, f = args
    name = img_id.replace("_jpg", "")
    gray0 = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
    hdc = find_hdc_label(name)
    wf = GT_WIRE_LABELS / f"{name}_jpg.txt"
    if gray0 is None or hdc is None or not wf.exists():
        return img_id, f, None
    gray = resize(gray0, f)
    H, W = gray.shape
    comps = parse_components(hdc.read_text(), W, H)
    keep = set(entry["electrical_idxs"])
    gtp = gt_pairs(entry["nets"], keep)
    diags = sorted(math.hypot(b[2] - b[0], b[3] - b[1]) for _c, _v, b in comps)
    out = {"W": W, "H": H, "median_diag": estimate_scale(comps, []),
           "diag_min": diags[0], "diag_max": diags[-1], "arms": {}}
    t0 = time.time()
    arm_wires = {"A_gt_wires": parse_gt_wires(wf.read_text(), W, H),
                 "B_detected": detect_wires(gray, comps)}
    out["detect_s"] = round(time.time() - t0, 2)
    for arm, wires in arm_wires.items():
        std = make_pins(wires, comps)
        junc = make_pins_junction_aware(wires, comps)
        res = {"n_wires": len(wires)}
        for m in METHODS:
            pred = comp_pairs(run_method(m, wires, comps, std, junc), keep)
            res[m] = (len(gtp & pred), len(pred - gtp), len(gtp - pred))
        out["arms"][arm] = res
    return img_id, f, out


def micro(counts):
    TP = sum(c[0] for c in counts); FP = sum(c[1] for c in counts); FN = sum(c[2] for c in counts)
    P = TP / (TP + FP) if TP + FP else 1.0
    R = TP / (TP + FN) if TP + FN else 1.0
    F = 2 * P * R / (P + R) if P + R else 0.0
    return {"f1": F, "p": P, "r": R, "tp": TP, "fp": FP, "fn": FN}


def img_prf(c):
    tp, fp, fn = c
    if tp + fp + fn == 0:
        return 1.0, 1.0, 1.0
    p = tp / (tp + fp) if tp + fp else (1.0 if tp + fn == 0 else 0.0)
    r = tp / (tp + fn) if tp + fn else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default="ground_truth/real_nets_verified.json")
    ap.add_argument("--out", default=str(Path.home() / "rev2_scratch" / "rescale_n31.json"))
    ap.add_argument("--factors", default=",".join(map(str, FACTORS)))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260928)
    args = ap.parse_args()

    factors = [float(x) for x in args.factors.split(",")]
    gt = json.load(open(args.gt))
    jobs = [(k, e, f) for f in factors for k, e in gt.items()]
    t0 = time.time()
    with Pool(args.workers) as pool:
        results = pool.map(job, jobs, chunksize=1)
    per = {}  # per[f][img] = out
    for img_id, f, out in results:
        if out is not None:
            per.setdefault(f, {})[img_id] = out
    imgs = sorted(set.intersection(*[set(per[f]) for f in factors]))
    arms = ["A_gt_wires", "B_detected"]

    summary = {}
    for arm in arms:
        summary[arm] = {}
        for m in METHODS:
            summary[arm][m] = {}
            for f in factors:
                cs = [per[f][i]["arms"][arm][m] for i in imgs]
                mi = micro(cs)
                prfs = [img_prf(c) for c in cs]
                mi.update(macro_f1=statistics.mean(x[2] for x in prfs),
                          macro_p=statistics.mean(x[0] for x in prfs),
                          macro_r=statistics.mean(x[1] for x in prfs))
                summary[arm][m][str(f)] = mi

    # paired image bootstrap of micro-F1(f) - micro-F1(1.0), same resampled image set
    rng = random.Random(args.seed)
    idx_sets = [[rng.randrange(len(imgs)) for _ in imgs] for _ in range(args.boot)]
    boot = {}
    for arm in arms:
        boot[arm] = {}
        for m in METHODS:
            base = [per[1.0][i]["arms"][arm][m] for i in imgs]
            boot[arm][m] = {}
            for f in factors:
                if f == 1.0:
                    continue
                cur = [per[f][i]["arms"][arm][m] for i in imgs]
                d0 = micro(cur)["f1"] - micro(base)["f1"]
                ds = sorted(micro([cur[j] for j in s])["f1"] - micro([base[j] for j in s])["f1"]
                            for s in idx_sets)
                boot[arm][m][str(f)] = {"diff": d0, "lo": ds[int(0.025 * len(ds))],
                                        "hi": ds[int(0.975 * len(ds)) - 1]}
            # CI band for the absolute micro-F1 curve (figure)
            for f in factors:
                cur = [per[f][i]["arms"][arm][m] for i in imgs]
                vs = sorted(micro([cur[j] for j in s])["f1"] for s in idx_sets)
                summary[arm][m][str(f)]["ci_lo"] = vs[int(0.025 * len(vs))]
                summary[arm][m][str(f)]["ci_hi"] = vs[int(0.975 * len(vs)) - 1]

    # paired image bootstrap of micro-F1(scale_completion) - micro-F1(other), per factor
    boot_vs_sc = {}
    for arm in arms:
        boot_vs_sc[arm] = {}
        for m in METHODS:
            if m == "scale_completion":
                continue
            boot_vs_sc[arm][m] = {}
            for f in factors:
                a = [per[f][i]["arms"][arm]["scale_completion"] for i in imgs]
                b = [per[f][i]["arms"][arm][m] for i in imgs]
                ds = sorted(micro([a[j] for j in s])["f1"] - micro([b[j] for j in s])["f1"]
                            for s in idx_sets)
                boot_vs_sc[arm][m][str(f)] = {"diff": micro(a)["f1"] - micro(b)["f1"],
                                              "lo": ds[int(0.025 * len(ds))],
                                              "hi": ds[int(0.975 * len(ds)) - 1]}

    # tolerance-clamp diagnostics for scale_completion (does k*s fall inside the clamp?)
    clamp = {}
    for f in factors:
        s_vals = [per[f][i]["median_diag"] for i in imgs]
        clamp[str(f)] = {
            "median_s": statistics.median(s_vals),
            "tau_pin_clamped_frac": sum(not (24 <= 0.62 * s <= 60) for s in s_vals) / len(s_vals),
            "tau_join_clamped_frac": sum(not (11 <= 0.30 * s <= 28) for s in s_vals) / len(s_vals),
            "tau_t_clamped_frac": sum(not (8 <= 0.20 * s <= 20) for s in s_vals) / len(s_vals),
        }

    payload = {
        "experiment": "controlled image rescaling, 31-image human-verified net-GT",
        "gt": args.gt, "n_images": len(imgs), "images": imgs, "factors": factors,
        "methods": METHODS,
        "config": {
            "interpolation": "INTER_AREA for f<1, INTER_CUBIC for f>1, W,H=round(704*f)",
            "labels": "YOLO-normalised OBB comps + GT wires re-projected onto W x H via "
                      "parse_components / parse_gt_wires (int truncation as in the paper eval)",
            "detector": "join_eval_134.detect_wires (best_candidate_v4), frozen pixel params",
            "scale_completion_k": K, "clamps": {"tau_pin": [24, 60], "tau_join": [11, 28],
                                               "tau_t": [8, 20], "completion_tau": [24, 60]},
            "fixed_px": {**FIXED, "completion_tau": FIXED_COMPLETION_TAU, "reach_factor": REACH},
            "bootstrap": {"B": args.boot, "seed": args.seed, "type": "paired image resample"},
            "shared_pixel_constants_not_scaled": "make_pins: DBSCAN eps 20px, max_comp_dist 50px, "
                                                 "15px override gate; assignment radius "
                                                 "max(tau_pin, 0.5*diag)",
        },
        "summary": summary, "paired_bootstrap_vs_f1": boot,
        "paired_bootstrap_sc_minus_method": boot_vs_sc, "clamp_diagnostics": clamp,
        "per_image": {str(f): {i: per[f][i] for i in imgs} for f in factors},
        "runtime_s": round(time.time() - t0, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(payload, open(args.out, "w"), indent=1)

    for arm in arms:
        print(f"\n== {arm}: micro-F1 (TP/FP/FN) ==")
        print(f"{'method':<28}" + "".join(f"{f:>9}" for f in factors))
        for m in METHODS:
            print(f"{m:<28}" + "".join(f"{summary[arm][m][str(f)]['f1']:>9.3f}" for f in factors))
        sc = summary[arm]["scale_completion"]["1.0"]
        print(f"scale_completion @1.0: {sc['tp']}/{sc['fp']}/{sc['fn']}")
    print("\nclamp diag:", json.dumps(clamp, indent=0))
    print(f"wrote {args.out} in {payload['runtime_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

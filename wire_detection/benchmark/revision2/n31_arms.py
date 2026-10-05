#!/usr/bin/env python3
"""Every join arm on the 31-image human-verified benchmark, with per-image predicted pairs.

One driver for the arms that the paper reports beside the main table (Access-2026-33821,
Sections V-C, V-F, V-G, V-I): edge-rule ablations (base graph and full pipeline), the
mechanism ablations (occlusion off, shared-component guard off, wire witness required),
annotated wires, annotated crossover boxes deleted, and the completion-reach sweep. Each arm
stores its predicted component pairs per image, so it can be rescored against revised nets
without rerunning (`--rescore`).

Inputs: ground_truth/real_nets_verified.json, the 704x704 benchmark copies (WIRE_GT_IMAGES),
the identity-copy component labels (ground_truth/component_labels/<img>.txt) and the wire
labels (WIRE_GT_WIRE_LABELS, default ground_truth/wire_labels).

  WIRE_GT_IMAGES=ground_truth/local_eval/images \\
    uv run python -m wire_detection.benchmark.revision2.n31_arms \\
      --out docs/research/experiments/revision2/n31_arms.json
  uv run python -m wire_detection.benchmark.revision2.n31_arms --rescore \\
      --out docs/research/experiments/revision2/n31_arms.json --gt <nets.json>
"""
from __future__ import annotations

import argparse
import json
import os
from itertools import combinations
from pathlib import Path

import cv2

from wire_detection.benchmark.build_net_gt import parse_components, parse_gt_wires
from wire_detection.benchmark.join_eval_134 import CFG, crop_to_roi, detect_wires, detect_wires_experiment, shift_components
from wire_detection.benchmark.join_eval_real_f1 import comp_pairs
from wire_detection.core import completion
from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.core.join_graph import build_endpoint_graph
from wire_detection.core.join_strategies import make_pins

REPO = Path(__file__).resolve().parents[3]
IMAGES = Path(os.environ.get("WIRE_GT_IMAGES", REPO / "ground_truth/local_eval/images"))
WIRES = Path(os.environ.get("WIRE_GT_WIRE_LABELS", REPO / "ground_truth/wire_labels"))
LABELS = REPO / "ground_truth/component_labels"

BASE = {"tau_pin": 0.62, "tau_join": 0.30, "tau_t": 0.20, "directional": True,
        "t_junctions": True, "rail_taps": True, "scale_rel": True}
EDGE_CONFIGS = {
    "baseline": BASE,
    "t_junctions_off": {**BASE, "t_junctions": False},
    "rail_taps_off": {**BASE, "rail_taps": False},
    "t_junctions+rail_taps_off": {**BASE, "t_junctions": False, "rail_taps": False},
    "directional_off": {**BASE, "directional": False},
    "scale_rel_off_fixedpx": {**BASE, "tau_pin": 30.0, "tau_join": 14.0, "tau_t": 10.0,
                              "scale_rel": False},
}
REACHES = (3.0, 3.5, 4.0, 4.5, 5.0)


def full(wires, comps, pins, graph_kwargs=BASE, **kw):
    """scale_completion with an arbitrary base-graph configuration."""
    saved = completion._BASES["scale"]["kwargs"]
    completion._BASES["scale"]["kwargs"] = graph_kwargs
    try:
        return completion.degree_budget_completion(
            wires, comps, pins, base="scale", **{"reach_factor": 4.0, "relax_witness": True, **kw})
    finally:
        completion._BASES["scale"]["kwargs"] = saved


def wires_without_occlusion(gray, comps):
    """detect_wires with the occlusion step removed; cropping and every setting unchanged."""
    cropped, ox, oy = crop_to_roi(gray, comps, CFG.crop_padding)
    lines = detect_wires_experiment(cropped, shift_components(comps, ox, oy), CFG)
    return [((x1 + ox, y1 + oy), (x2 + ox, y2 + oy)) for (x1, y1), (x2, y2) in lines]


def pairs_of(nl, keep, remap=None):
    p = comp_pairs(nl, set(range(10 ** 6)) if remap else keep)
    if remap:
        p = {tuple(sorted((remap[a], remap[b]))) for a, b in p}
        p = {q for q in p if q[0] in keep and q[1] in keep}
    return sorted(p)


def run(gt):
    out = {}
    for k, e in gt.items():
        gray = cv2.imread(str(IMAGES / f"{k}.jpg"), cv2.IMREAD_GRAYSCALE)
        h, w = gray.shape
        comps = parse_components((LABELS / f"{k}.txt").read_text(), w, h)
        keep = set(e["electrical_idxs"])
        wires = detect_wires(gray, comps)
        pins = make_pins(wires, comps)
        arms, info = {}, {"n_wires": len(wires)}
        for name, kw in EDGE_CONFIGS.items():
            arms[f"base:{name}"] = pairs_of(build_endpoint_graph(wires, comps, pins, **kw), keep)
            arms[f"full:{name}"] = pairs_of(full(wires, comps, pins, kw), keep)
        st = {}
        full(wires, comps, pins, stats=st)
        info["guard_rejects"] = st.get("guard_rejects", 0)
        arms["guard_off"] = pairs_of(full(wires, comps, pins, guard=False), keep)
        arms["witness_required"] = pairs_of(full(wires, comps, pins, relax_witness=False), keep)
        for r in REACHES:
            arms[f"reach_{r}"] = pairs_of(full(wires, comps, pins, reach_factor=r), keep)
        w_occ = wires_without_occlusion(gray, comps)
        info["n_wires_occlusion_off"] = len(w_occ)
        arms["occlusion_off"] = pairs_of(full(w_occ, comps, make_pins(w_occ, comps)), keep)
        wl = WIRES / f"{k}.txt"
        if wl.exists():
            aw = parse_gt_wires(wl.read_text(), w, h)
            arms["annotated_wires"] = pairs_of(full(aw, comps, make_pins(aw, comps)), keep)
        # annotated crossover boxes deleted before joining (indices remapped for scoring)
        kept = [i for i, c in enumerate(comps) if COMPONENT_TYPES.get(c[0]) != "crossover"]
        info["n_crossover"] = len(comps) - len(kept)
        if len(kept) < len(comps):
            c2 = [comps[i] for i in kept]
            p2 = make_pins(wires, c2)
            arms["crossover_deleted"] = pairs_of(full(wires, c2, p2), keep, remap=dict(enumerate(kept)))
        else:
            arms["crossover_deleted"] = arms["full:baseline"]
        out[k] = {"arms": arms, "info": info}
        print(k, info, flush=True)
    return out


def gt_pairs(e):
    keep = set(e["electrical_idxs"]); s = set()
    for n in e["nets"]:
        s |= set(combinations(sorted({int(i) for i, _ in n if int(i) in keep}), 2))
    return s


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else (1.0 if not fn else 0.0)
    r = tp / (tp + fn) if tp + fn else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def score(per_image, gt):
    arms = sorted({a for v in per_image.values() for a in v["arms"]})
    res = {}
    for a in arms:
        rows = {}
        for k, v in per_image.items():
            if a not in v["arms"]:
                continue
            g, p = gt_pairs(gt[k]), {tuple(x) for x in v["arms"][a]}
            rows[k] = (len(g & p), len(p - g), len(g - p))
        tp, fp, fn = (sum(c[i] for c in rows.values()) for i in range(3))
        P, R, F = prf(tp, fp, fn)
        ref = {tuple(x) for x in per_image[next(iter(rows))]["arms"]["full:baseline"]}  # noqa: F841
        changed = sum(1 for k in rows if per_image[k]["arms"][a] != per_image[k]["arms"]["full:baseline"])
        res[a] = {"micro": {"f1": F, "p": P, "r": R, "tp": tp, "fp": fp, "fn": fn},
                  "macro_f1": sum(prf(*c)[2] for c in rows.values()) / len(rows),
                  "n_images": len(rows), "changed_vs_full_baseline": changed,
                  "per_image": {k: list(c) for k, c in rows.items()}}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default=str(REPO / "ground_truth/real_nets_verified.json"))
    ap.add_argument("--out", default=str(REPO / "docs/research/experiments/revision2/n31_arms.json"))
    ap.add_argument("--rescore", action="store_true", help="score stored pairs against --gt")
    args = ap.parse_args()
    gt = json.load(open(args.gt))
    if args.rescore:
        per_image = json.load(open(args.out))["per_image"]
    else:
        per_image = run(gt)
    res = score(per_image, gt)
    for a, v in res.items():
        m = v["micro"]
        print(f"{a:32s} {m['f1']:.4f} {m['tp']}/{m['fp']}/{m['fn']} macro {v['macro_f1']:.4f} "
              f"changed {v['changed_vs_full_baseline']}/{v['n_images']}")
    json.dump({"gt": os.path.relpath(args.gt, REPO), "scores": res, "per_image": per_image},
              open(args.out, "w"), indent=1)
    print("wrote", args.out)


if __name__ == "__main__":
    main()

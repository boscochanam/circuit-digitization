#!/usr/bin/env python3
"""Search for a join variant that beats production degree_budget, evaluated against the
human-verified net-GT.

degree_budget = graph_rescue base + floating-pin b-matching completion. It tops F1 via the
best recall, but the graph_scale/graph_30 bases have higher *precision*. This sweeps the
completion's BASE graph and REACH budget + witness policy to see if a higher-precision base
plus completion yields a better F1. Production code (core/completion.py) is untouched.

Run on claw:
  ./.venv/bin/python -m wire_detection.benchmark.join_variant_search --gt ground_truth/real_nets_verified.json
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

from wire_detection.core.join_graph import build_endpoint_graph, estimate_scale, extend_wires
from wire_detection.core.completion import netlist_from_uf, _INERT_TYPES
from wire_detection.benchmark.build_net_gt import GT_IMAGES, find_hdc_label, parse_components
from wire_detection.benchmark.join_eval_134 import detect_wires
from wire_detection.benchmark.join_eval_real_f1 import comp_pairs, gt_pairs, prf
from wire_detection.core.join_strategies import make_pins

BASE_GRAPH = dict(tau_pin=0.62, tau_join=0.30, tau_t=0.20, directional=True,
                  t_junctions=True, scale_rel=True)
BASES = {
    "rescue":  dict(extend=12, kwargs={**BASE_GRAPH, "dead_end_rescue": True}),   # production base
    "scale":   dict(extend=0,  kwargs={**BASE_GRAPH}),                            # higher precision
    "scale12": dict(extend=12, kwargs={**BASE_GRAPH}),                            # graph_full base
}


def completion_variant(wires, components, std_pins, base="rescue", reach_factor=2.5,
                       relax_witness=True, slot_cap=3):
    if not std_pins:
        return netlist_from_uf(std_pins, {})
    cfg = BASES[base]
    w = extend_wires(wires, cfg["extend"]) if cfg["extend"] else list(wires)
    basenl = build_endpoint_graph(w, components, std_pins, **cfg["kwargs"])

    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for p in std_pins:
        find((p.component_idx, p.pin_name))
    node_members = defaultdict(list)
    for (ci, pin_name), nid in basenl.pin_to_node.items():
        node_members[nid].append((ci, pin_name))
    for keys in node_members.values():
        for k in keys[1:]:
            union(keys[0], k)

    s = estimate_scale(components, w)
    tau = min(60.0, max(24.0, 0.62 * s))
    reach = reach_factor * tau
    comp_type = {p.component_idx: p.component_name for p in std_pins}
    pin_pos = {(p.component_idx, p.pin_name): (float(p.x), float(p.y)) for p in std_pins}

    root_comps = defaultdict(set)
    for p in std_pins:
        root_comps[find((p.component_idx, p.pin_name))].add(p.component_idx)

    def is_inert(ci):
        t = comp_type.get(ci)
        return (t in _INERT_TYPES) if t else False

    floating = [(p.component_idx, p.pin_name) for p in std_pins
                if not is_inert(p.component_idx)
                and root_comps[find((p.component_idx, p.pin_name))] == {p.component_idx}]
    if not floating:
        return netlist_from_uf(std_pins, parent, base_netlist=basenl)

    wends = [((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))) for (a, b) in w]

    def witness_cost(fp, tg):
        fx, fy = pin_pos[fp]; tx, ty = pin_pos[tg]
        best = float("inf")
        for (e0, e1) in wends:
            m1 = max(math.hypot(e0[0] - fx, e0[1] - fy), math.hypot(e1[0] - tx, e1[1] - ty))
            m2 = max(math.hypot(e0[0] - tx, e0[1] - ty), math.hypot(e1[0] - fx, e1[1] - fy))
            m = min(m1, m2)
            if m <= reach and m < best:
                best = m
        return best

    targets = []; target_index = {}; edges = []
    fp_index = {fp: i for i, fp in enumerate(floating)}
    for fp in floating:
        fci = fp[0]; fx, fy = pin_pos[fp]
        for tg, (tx, ty) in pin_pos.items():
            if tg[0] == fci or find(tg) == find(fp):
                continue
            d = math.hypot(tx - fx, ty - fy)
            if d > reach:
                continue
            wc = witness_cost(fp, tg)
            if wc == float("inf"):
                if not relax_witness:
                    continue
                cost = d
            else:
                cost = wc
            if tg not in target_index:
                target_index[tg] = len(targets); targets.append(tg)
            edges.append((fp_index[fp], target_index[tg], cost))
    if not edges:
        return netlist_from_uf(std_pins, parent, base_netlist=basenl)

    nF = len(floating)
    demand = defaultdict(int)
    for _f, t, _c in edges:
        demand[t] += 1
    slot_of_target = []; target_slots = defaultdict(list)
    for t in range(len(targets)):
        for _ in range(max(1, min(slot_cap, demand.get(t, 1)))):
            target_slots[t].append(len(slot_of_target)); slot_of_target.append(t)
    n_slot = len(slot_of_target); big = 1e6; dummy_cost = reach * 1.5
    cost_mat = np.full((nF, n_slot + nF), big, dtype=float)
    for i in range(nF):
        cost_mat[i, n_slot + i] = dummy_cost
    for f, t, cost in edges:
        for col in target_slots[t]:
            if cost < cost_mat[f, col]:
                cost_mat[f, col] = cost
    rows, cols = linear_sum_assignment(cost_mat)

    net_comps = defaultdict(set)
    for p in std_pins:
        net_comps[find((p.component_idx, p.pin_name))].add(p.component_idx)
    for r, c in zip(rows, cols):
        if c >= n_slot or cost_mat[r, c] >= big:
            continue
        fp = floating[r]; tg = targets[slot_of_target[c]]
        rf, rt = find(fp), find(tg)
        if rf == rt or (net_comps[rf] & net_comps[rt]):
            continue
        merged = net_comps[rf] | net_comps[rt]
        union(fp, tg)
        net_comps[find(fp)] = merged
    return netlist_from_uf(std_pins, parent, base_netlist=basenl)


VARIANTS = {
    "db_rescue_r2.5 (prod)": dict(base="rescue", reach_factor=2.5, relax_witness=True),
    "db_scale_r2.5":         dict(base="scale", reach_factor=2.5, relax_witness=True),
    "db_scale_r3.0":         dict(base="scale", reach_factor=3.0, relax_witness=True),
    "db_scale_r3.5":         dict(base="scale", reach_factor=3.5, relax_witness=True),
    "db_scale_r4.0":         dict(base="scale", reach_factor=4.0, relax_witness=True),
    "db_scale_r4.5":         dict(base="scale", reach_factor=4.5, relax_witness=True),
    "db_scale_r5.0":         dict(base="scale", reach_factor=5.0, relax_witness=True),
    "db_scale_r3.0_wonly":   dict(base="scale", reach_factor=3.0, relax_witness=False),
    "db_scale_r4.0_wonly":   dict(base="scale", reach_factor=4.0, relax_witness=False),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default="ground_truth/real_nets_verified.json")
    ap.add_argument("--out", default="output/join_variant_search.json")
    args = ap.parse_args()
    gt = json.load(open(args.gt))

    accF = {v: [] for v in VARIANTS}; accP = {v: [] for v in VARIANTS}; accR = {v: [] for v in VARIANTS}
    for img_id, entry in gt.items():
        name = img_id.replace("_jpg", "")
        gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        hdc = find_hdc_label(name)
        if gray is None or hdc is None:
            continue
        h, w = gray.shape
        comps = parse_components(hdc.read_text(), w, h)
        keep = set(entry["electrical_idxs"])
        gtp = gt_pairs(entry["nets"], keep)
        wires = detect_wires(gray, comps)
        std = make_pins(wires, comps)
        for vname, kw in VARIANTS.items():
            nl = completion_variant(wires, comps, std, **kw)
            p, r, f1 = prf(gtp, comp_pairs(nl, keep))
            accF[vname].append(f1); accP[vname].append(p); accR[vname].append(r)

    mean = lambda v: sum(v) / len(v) if v else 0.0
    n = len(accF[list(VARIANTS)[0]])
    print(f"\nJoin variant search vs verified GT ({n} images)")
    print(f"{'variant':<26}{'meanF1':>8}{'meanP':>8}{'meanR':>8}")
    print("-" * 50)
    for v, mf in sorted(((v, mean(accF[v])) for v in VARIANTS), key=lambda x: -x[1]):
        print(f"{v:<26}{mf:>8.3f}{mean(accP[v]):>8.3f}{mean(accR[v]):>8.3f}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({v: {"f1": mean(accF[v]), "p": mean(accP[v]), "r": mean(accR[v])} for v in VARIANTS},
              open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

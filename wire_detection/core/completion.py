"""Degree-budget completion: a post-processing join layer on top of the
endpoint-graph (graph_rescue) netlist.

Discovered + verified via the synthgt ground-truth search (see
docs/synthetic-eval-plan.md "Strategy search"). A pin whose net touches only its
own component is "floating" -- the signature of a wire the detector dropped or
over-displaced. Such pins are reconnected to OTHER components via reach-bounded
min-cost b-matching (scipy linear_sum_assignment, <=1 edge per floating pin),
which recovers dropped connections while the bounded edge budget structurally
limits over-merge. Two safeguards make it production-safe:

  * SELF-LOOP GUARD -- the matching never merges two nets that already share a
    component, so a two-terminal part (R/C/L/D) is never shorted onto one net.
  * WIRE TRACKING -- `netlist_from_uf` carries the base graph_rescue wires onto
    the final nodes (NetNode.wires), which the SPICE / current overlay reads;
    completion edges are wireless by nature (inferred, like a manual pin merge).

Registered in join_strategies.py as the "degree_budget" strategy (kind=completion).
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment

from wire_detection.core.join_graph import build_endpoint_graph, estimate_scale
from wire_detection.core.netlist import Netlist, NetNode

# Component types that legitimately touch only one net -> never treated as a
# "floating" (dropped-wire) deficit to be completed.
_INERT_TYPES = {"gnd", "vss", "text", "antenna", "probe", "probe-current",
                "probe-voltage", "junction", "terminal"}
REACH_FACTOR = 2.5


def netlist_from_uf(std_pins, parent, base_netlist=None):
    """Materialize a Netlist from a union-find over pin-keys (comp_idx, pin_name).

    The synthgt scorer reads only pin_to_node, but the real pipeline (score_netlist
    wire coverage, the SPICE / current overlay) reads NetNode.wires. So when a
    `base_netlist` (the graph_rescue netlist this builds on) is given, each base
    node's wire indices are carried onto the final node its pins landed in.
    Completion-only connections legitimately have NO wire and add none.
    """
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    roots: dict = {}
    nl = Netlist()
    for p in std_pins:
        k = (p.component_idx, p.pin_name)
        nl.pin_to_node[k] = roots.setdefault(find(parent.setdefault(k, k)), len(roots))
    groups: dict = defaultdict(list)
    for p in std_pins:
        groups[nl.pin_to_node[(p.component_idx, p.pin_name)]].append(p)
    nl.nodes = [NetNode(node_id=nid, pins=ps) for nid, ps in groups.items()]
    if base_netlist is not None:
        node_by_id = {n.node_id: n for n in nl.nodes}
        carried: dict = defaultdict(set)
        for bnode in base_netlist.nodes:
            fnid = None
            for bp in bnode.pins:   # all of a base node's pins land in one final node
                fnid = nl.pin_to_node.get((bp.component_idx, bp.pin_name))
                if fnid is not None:
                    break
            if fnid is not None:
                carried[fnid].update(bnode.wires)
        for nid, wset in carried.items():
            node_by_id[nid].wires = sorted(wset)
    return nl


def _scale_tau(components, wires):
    s = estimate_scale(components, wires)
    return min(60.0, max(24.0, 0.62 * s))


def degree_budget_completion(wires, components, std_pins, relax_witness=True):
    """graph_rescue base + degree-budget completion of floating pins.

    Returns a Netlist. `relax_witness=True` (the verified variant) also allows
    pure-distance completion edges when no wire-witness exists, recovering
    truly-dropped wires.
    """
    if not std_pins:
        return netlist_from_uf(std_pins, {})

    base = build_endpoint_graph(
        wires, components, std_pins,
        tau_pin=0.62, tau_join=0.30, tau_t=0.20,
        directional=True, t_junctions=True, scale_rel=True, dead_end_rescue=True,
    )

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
    for (ci, pin_name), nid in base.pin_to_node.items():
        node_members[nid].append((ci, pin_name))
    for keys in node_members.values():
        for k in keys[1:]:
            union(keys[0], k)

    tau = _scale_tau(components, wires)
    reach = REACH_FACTOR * tau
    comp_type = {p.component_idx: p.component_name for p in std_pins}
    pin_pos = {(p.component_idx, p.pin_name): (float(p.x), float(p.y)) for p in std_pins}

    root_comps = defaultdict(set)
    for p in std_pins:
        root_comps[find((p.component_idx, p.pin_name))].add(p.component_idx)

    def is_inert(ci):
        t = comp_type.get(ci)
        return (t in _INERT_TYPES) if t else False

    floating = []
    for p in std_pins:
        ci = p.component_idx
        if is_inert(ci):
            continue
        k = (ci, p.pin_name)
        if root_comps[find(k)] == {ci}:
            floating.append(k)
    if not floating:
        return netlist_from_uf(std_pins, parent, base_netlist=base)

    wends = [((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))) for (a, b) in wires]

    def witness_cost(fp_key, tg_key):
        fx, fy = pin_pos[fp_key]; tx, ty = pin_pos[tg_key]
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
        return netlist_from_uf(std_pins, parent, base_netlist=base)

    nF = len(floating); slot_cap = 3
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

    # Apply matches with a SELF-LOOP GUARD (one pin per component per net): merging
    # two nets that already share a component would put that component's two pins on
    # one net -- a short. Skip those; the floating pin stays floating (the component
    # is still connected via its other pin, so connectivity holds).
    net_comps = defaultdict(set)
    for p in std_pins:
        net_comps[find((p.component_idx, p.pin_name))].add(p.component_idx)
    for r, c in zip(rows, cols):
        if c >= n_slot or cost_mat[r, c] >= big:
            continue
        fp = floating[r]; tg = targets[slot_of_target[c]]
        rf, rt = find(fp), find(tg)
        if rf == rt:
            continue
        if net_comps[rf] & net_comps[rt]:   # shared component -> would self-loop
            continue
        merged = net_comps[rf] | net_comps[rt]
        union(fp, tg)
        net_comps[find(fp)] = merged
    return netlist_from_uf(std_pins, parent, base_netlist=base)

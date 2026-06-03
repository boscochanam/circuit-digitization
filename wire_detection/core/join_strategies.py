"""Join-strategy registry — the single source of truth for HOW wires are joined
into electrical nodes, plus structural scoring.

The production join (`build_netlist`) ties a wire-end to EVERY pin within 30px
(transitive union-find), which over-merges. This module exposes that as one named
strategy among several alternatives so they can be compared head-to-head — in the
experiment CLI, the API, and the UI — by both the image overlay and the metrics.

A strategy = an "attach rule" (which pins a wire-end grabs) + a radius (+ optional
anchor check). `build(name, …)` returns a `Netlist`. `score_netlist(…)` returns the
structural health metrics (errors that are wrong by circuit laws — no GT needed).
"""
from __future__ import annotations

import math
from collections import defaultdict

from wire_detection.core.netlist import (
    NetNode,
    Netlist,
    build_netlist,
    derive_pins_from_obb,
    discover_pins,
)
from wire_detection.core.join_graph import build_endpoint_graph
from wire_detection.core.mapping import TWO_TERMINAL_TYPES
from wire_detection.core.spice import COMPONENT_NAMES


def make_pins(wires, components):
    """Pin set shared by every strategy: static OBB pins for ALL components,
    with positions overridden by DBSCAN endpoint-clustered pins where available
    (matches the production /api/netlist path)."""
    all_pins = []
    for ci, comp in enumerate(components):
        tname = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        all_pins.extend(derive_pins_from_obb(ci, comp, tname))
    clustered = discover_pins(wires, components)
    if clustered:
        ov = {(cp.component_idx, cp.pin_idx): (cp.x, cp.y) for cp in clustered}
        for p in all_pins:
            k = (p.component_idx, p.pin_idx)
            if k in ov:
                p.x, p.y = ov[k]
    return all_pins

# component types that legitimately touch only one net (not "floating" errors)
INERT_TYPES = {"junction", "terminal", "gnd", "antenna", "probe", "crossover", "wire"}


# ── attach rules: given an endpoint, which pins does the wire tie? ──

def attach_all(ep, pins, radius, components=None):
    return [p for p in pins if math.hypot(ep[0] - p.x, ep[1] - p.y) <= radius]


def attach_nearest_k(ep, pins, radius, k, components=None):
    near = [(math.hypot(ep[0] - p.x, ep[1] - p.y), p) for p in pins]
    near = sorted((dp for dp in near if dp[0] <= radius), key=lambda dp: dp[0])
    return [p for _d, p in near[:k]]


def attach_anchored(ep, pins, radius, k, components, margin=8):
    """Nearest-k, but only pins whose OWN component bbox the endpoint actually
    reaches (within `margin`) — a connectivity check, not bare proximity."""
    cands = []
    for p in pins:
        d = math.hypot(ep[0] - p.x, ep[1] - p.y)
        if d > radius:
            continue
        if components is not None and 0 <= p.component_idx < len(components):
            x1, y1, x2, y2 = components[p.component_idx][2]
            if not (x1 - margin <= ep[0] <= x2 + margin and y1 - margin <= ep[1] <= y2 + margin):
                continue
        cands.append((d, p))
    cands.sort(key=lambda dp: dp[0])
    return [p for _d, p in cands[:k]]


def attach_density(ep, pins, base, k=1, shrink=0.07, floor=0.45):
    """Density-adaptive nearest-k: shrink the radius where many pins crowd the
    endpoint, so dense areas don't over-grab."""
    within = [(math.hypot(ep[0] - p.x, ep[1] - p.y), p) for p in pins]
    within = [dp for dp in within if dp[0] <= base]
    r_eff = base * max(floor, 1.0 - shrink * max(0, len(within) - 1))
    sel = sorted((dp for dp in within if dp[0] <= r_eff), key=lambda dp: dp[0])
    return [p for _d, p in sel[:k]]


# ── wire-end extension (occlusion-gap fix) ──

def extend_wires(wires, px):
    """Lengthen each wire by `px` at both ends along its direction so endpoints
    truncated at component edges reach the component pin."""
    if not px:
        return wires
    out = []
    for (x1, y1), (x2, y2) in wires:
        dx, dy = x2 - x1, y2 - y1
        ln = math.hypot(dx, dy)
        if ln < 1e-6:
            out.append(((x1, y1), (x2, y2)))
            continue
        ux, uy = dx / ln, dy / ln
        out.append(((int(x1 - ux * px), int(y1 - uy * px)),
                    (int(x2 + ux * px), int(y2 + uy * px))))
    return out


# ── junction-aware pins: relocate junction/terminal pins to where wires meet ──

_JUNCTION_TYPES = {"junction", "terminal", "gnd", "crossover"}


def make_pins_junction_aware(wires, components, max_comp_dist=40):
    """Standard pins, but each junction/terminal pin is moved to the centroid of
    the wire endpoints near it — so junctions get a real meeting-point pin that
    nearby wire-ends snap to (fewer dangling + correct junction merges)."""
    pins = make_pins(wires, components)
    by_comp: dict[int, list] = {}
    for p in pins:
        by_comp.setdefault(p.component_idx, []).append(p)
    for ci, comp in enumerate(components):
        if COMPONENT_NAMES.get(comp[0], "") not in _JUNCTION_TYPES:
            continue
        x_min, y_min, x_max, y_max = comp[2]
        near = []
        for ep1, ep2 in wires:
            for ep in (ep1, ep2):
                cx = max(x_min, min(ep[0], x_max))
                cy = max(y_min, min(ep[1], y_max))
                if math.hypot(ep[0] - cx, ep[1] - cy) <= max_comp_dist:
                    near.append(ep)
        if not near:
            continue
        mx = int(sum(e[0] for e in near) / len(near))
        my = int(sum(e[1] for e in near) / len(near))
        for p in by_comp.get(ci, []):
            p.x, p.y = mx, my
    return pins


# ── mutual nearest-neighbour attach builder ──

def build_mutual(wires, components, pins, radius):
    """Each pin attaches to the SINGLE wire-end that is globally nearest to it
    (within radius); a wire then ties the pins that chose its two ends. Symmetric
    — avoids a crowded endpoint grabbing many pins."""
    def key(p):
        return (p.component_idx, p.pin_name)

    endpoints = []  # (wire_idx, end, (x, y))
    for wi, (a, b) in enumerate(wires):
        endpoints.append((wi, 0, a))
        endpoints.append((wi, 1, b))

    # each pin -> index of its nearest endpoint within radius
    pin_ep = {}
    for pi, p in enumerate(pins):
        best, bi = radius, None
        for ei, (_wi, _end, ep) in enumerate(endpoints):
            d = math.hypot(ep[0] - p.x, ep[1] - p.y)
            if d <= best:
                best, bi = d, ei
        if bi is not None:
            pin_ep[pi] = bi

    ep_pins = defaultdict(list)
    for pi, ei in pin_ep.items():
        ep_pins[ei].append(pins[pi])

    parent = {key(p): key(p) for p in pins}
    pin_by_key = {key(p): p for p in pins}

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    wires_for_first = defaultdict(list)
    for wi in range(len(wires)):
        grp = ep_pins.get(2 * wi, []) + ep_pins.get(2 * wi + 1, [])
        keys = list({key(p) for p in grp})
        if len(keys) < 2:
            continue
        for kk in keys[1:]:
            union(keys[0], kk)
        wires_for_first[keys[0]].append(wi)

    groups = defaultdict(list)
    for k in parent:
        groups[find(k)].append(pin_by_key[k])
    nl = Netlist()
    nl.pin_to_node = {}
    for nid, (root, plist) in enumerate(groups.items()):
        wl = []
        for p in plist:
            wl.extend(wires_for_first.get(key(p), []))
        nl.nodes.append(NetNode(node_id=nid, pins=plist, wires=sorted(set(wl))))
        for p in plist:
            nl.pin_to_node[key(p)] = nid
    return nl


# ── generic union-find builder parameterized by an attach fn ──

def build_variant(wires, components, pins, attach_fn):
    def key(p):
        return (p.component_idx, p.pin_name)

    pin_by_key = {key(p): p for p in pins}
    parent = {key(p): key(p) for p in pins}

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    wires_for_first = defaultdict(list)
    for wi, (ep1, ep2) in enumerate(wires):
        grp = attach_fn(ep1, pins, components) + attach_fn(ep2, pins, components)
        keys = list({key(p) for p in grp})
        if len(keys) < 2:
            continue
        for kk in keys[1:]:
            union(keys[0], kk)
        wires_for_first[keys[0]].append(wi)

    groups = defaultdict(list)
    for k in parent:
        groups[find(k)].append(pin_by_key[k])

    nl = Netlist()
    nl.pin_to_node = {}
    for nid, (root, plist) in enumerate(groups.items()):
        wlist = []
        for p in plist:
            wlist.extend(wires_for_first.get(key(p), []))
        nl.nodes.append(NetNode(node_id=nid, pins=plist, wires=sorted(set(wlist))))
        for p in plist:
            nl.pin_to_node[key(p)] = nid
    return nl


# ── the registry ──
# order matters (UI lists them in this order). `kind` selects the attach rule.
STRATEGIES = [
    {"name": "production", "label": "Production (all pins within 30px)",
     "desc": "Current pipeline: a wire-end grabs EVERY pin within 30px, transitive. Over-merges.",
     "radius": 30, "kind": "production"},
    {"name": "nearest1_30", "label": "Nearest pin only (30px)",
     "desc": "Each wire-end ties only its single nearest pin. A wire bridges exactly 2 pins. Fewest shorts.",
     "radius": 30, "kind": "nearest", "k": 1},
    {"name": "nearest2_30", "label": "Up to 2 nearest (30px)",
     "desc": "Each end ties its 2 nearest pins — allows small junctions while limiting over-grab.",
     "radius": 30, "kind": "nearest", "k": 2},
    {"name": "anchored1_30", "label": "Nearest + anchor check (30px)",
     "desc": "Nearest pin only, AND the wire-end must actually reach that pin's component bbox.",
     "radius": 30, "kind": "anchored", "k": 1},
    {"name": "all_18", "label": "Tighter radius (18px, all)",
     "desc": "Production rule but a tighter 18px radius. Fewer over-grabs, more dangling.",
     "radius": 18, "kind": "all"},
    {"name": "nearest1_18", "label": "Nearest only, tighter (18px)",
     "desc": "Nearest-pin attach with an 18px radius. Aggressive against over-merge.",
     "radius": 18, "kind": "nearest", "k": 1},
    {"name": "anchored2_30", "label": "Anchored, up to 2 (30px)",
     "desc": "Anchor check (wire reaches component) but allows 2 pins per end.",
     "radius": 30, "kind": "anchored", "k": 2},
    {"name": "mutual_30", "label": "Mutual nearest (30px)",
     "desc": "A pin attaches to the wire-end globally nearest to it — symmetric, avoids crowded-endpoint over-grab.",
     "radius": 30, "kind": "mutual"},
    {"name": "density_30", "label": "Density-adaptive nearest (30px)",
     "desc": "Nearest attach with a radius that shrinks where pins are crowded (dense areas).",
     "radius": 30, "kind": "density", "k": 1},
    {"name": "junction_n1_30", "label": "Junction-aware pins + nearest (30px)",
     "desc": "Relocate junction/terminal pins to the wire-meet point, then nearest attach. Targets dangling + junction merges.",
     "radius": 30, "kind": "nearest", "k": 1, "pins": "junction"},
    {"name": "extend12_n1_30", "label": "Extend ends 12px + nearest (30px)",
     "desc": "Lengthen wire ends 12px (occlusion-gap fix), then nearest attach. Targets dangling at component edges.",
     "radius": 30, "kind": "nearest", "k": 1, "extend": 12},
    {"name": "junction_extend_n1", "label": "Junction pins + extend + nearest",
     "desc": "Combine junction-aware pins, 12px end extension, and nearest attach — the best-of stack.",
     "radius": 30, "kind": "nearest", "k": 1, "pins": "junction", "extend": 12},
    # ── endpoint-graph family (wire endpoints AND pins are nodes; wire-to-wire edges) ──
    {"name": "graph_30", "label": "Endpoint graph (30px)",
     "desc": "Wire ends + pins are graph nodes; adds endpoint↔endpoint and T-junction (endpoint↔wire-body) edges. Connects rails/junctions the pin-only join can't.",
     "radius": 30, "kind": "graph",
     "graph": {"tau_pin": 30.0, "tau_join": 14.0, "tau_t": 10.0, "directional": False, "t_junctions": True}},
    {"name": "graph_dir_30", "label": "Endpoint graph + directional (30px)",
     "desc": "Endpoint graph, but a wire-end binds the pin it POINTS at (distance × angle), not merely the nearest. Cuts side-grab shorts.",
     "radius": 30, "kind": "graph",
     "graph": {"tau_pin": 30.0, "tau_join": 14.0, "tau_t": 10.0, "directional": True, "t_junctions": True}},
    {"name": "graph_scale", "label": "Endpoint graph, scale-relative",
     "desc": "Endpoint graph with tolerances = k×(median component size), so one rule fits the ~6× circuit-scale range. Directional.",
     "radius": 30, "kind": "graph",
     "graph": {"tau_pin": 0.62, "tau_join": 0.30, "tau_t": 0.20, "directional": True, "t_junctions": True, "scale_rel": True}},
    {"name": "graph_full", "label": "Endpoint graph + extend + scale (flagship)",
     "desc": "Endpoint graph: scale-relative tolerances, directional pin binding, T-junctions, and 12px end extension. The most robust across cases.",
     "radius": 30, "kind": "graph", "extend": 12,
     "graph": {"tau_pin": 0.62, "tau_join": 0.30, "tau_t": 0.20, "directional": True, "t_junctions": True, "scale_rel": True}},
    {"name": "graph_rescue", "label": "Endpoint graph + dead-end rescue",
     "desc": "graph_full plus dead-end rescue: a wire anchored on ONE pin extends its dangling end (2.2x reach, directional) to the pin it points at — recovers wires the detector cut short.",
     "radius": 30, "kind": "graph", "extend": 12,
     "graph": {"tau_pin": 0.62, "tau_join": 0.30, "tau_t": 0.20, "directional": True, "t_junctions": True, "scale_rel": True, "dead_end_rescue": True}},
]
_BY_NAME = {s["name"]: s for s in STRATEGIES}
# The endpoint-graph join with dead-end rescue — best join_quality across the eval
# (see docs/join-verification.md). Used by /api/netlist (netlist+topology+SPICE) and
# as the Join Check default; `production` stays in the registry for comparison.
DEFAULT_STRATEGY = "graph_rescue"


def list_strategies():
    return [{"name": s["name"], "label": s["label"], "desc": s["desc"]} for s in STRATEGIES]


def _build_with_pins(s, wires, components, pins):
    radius, kind, k = s["radius"], s["kind"], s.get("k", 1)
    if kind == "production":
        return build_netlist(wires, components, pins, max_pin_dist=radius)
    if kind == "mutual":
        return build_mutual(wires, components, pins, radius)
    if kind == "graph":
        return build_endpoint_graph(wires, components, pins, **s.get("graph", {}))
    if kind == "all":
        attach = lambda ep, pp, comps: attach_all(ep, pp, radius)
    elif kind == "anchored":
        attach = lambda ep, pp, comps: attach_anchored(ep, pp, radius, k, comps)
    elif kind == "density":
        attach = lambda ep, pp, comps: attach_density(ep, pp, radius, k)
    else:  # nearest
        attach = lambda ep, pp, comps: attach_nearest_k(ep, pp, radius, k)
    return build_variant(wires, components, pins, attach)


def run_strategy(name, wires, components, std_pins=None, junc_pins=None):
    """Run a full strategy → (pins, netlist). Handles per-strategy pin mode and
    wire-end extension. Pass cached std_pins/junc_pins to avoid recomputing."""
    s = _BY_NAME.get(name) or _BY_NAME[DEFAULT_STRATEGY]
    if s.get("pins") == "junction":
        pins = junc_pins if junc_pins is not None else make_pins_junction_aware(wires, components)
    else:
        pins = std_pins if std_pins is not None else make_pins(wires, components)
    w = extend_wires(wires, s["extend"]) if s.get("extend") else wires
    netlist = _build_with_pins(s, w, components, pins)
    return pins, netlist


def build(name, wires, components, pins, max_pin_dist=None):
    """Back-compat: build with caller-supplied pins (ignores per-strategy pin mode)."""
    s = _BY_NAME.get(name) or _BY_NAME[DEFAULT_STRATEGY]
    w = extend_wires(wires, s["extend"]) if s.get("extend") else wires
    return _build_with_pins(s, w, components, pins)


# ── structural scoring (no ground truth needed) ──

def _nearest_pin_dist(ep, pins):
    best = float("inf")
    for p in pins:
        d = math.hypot(ep[0] - p.x, ep[1] - p.y)
        if d < best:
            best = d
    return best


def score_netlist(wires, components, pins, netlist, max_pin_dist=30.0, giant=8):
    pin_node = dict(netlist.pin_to_node)
    node_comps: dict[int, set] = {}
    for (ci, _pn), nid in pin_node.items():
        node_comps.setdefault(nid, set()).add(ci)

    comp_pins: dict[int, list] = {}
    for p in pins:
        comp_pins.setdefault(p.component_idx, []).append(p)

    self_loops = floating = connected = non_inert = 0
    for ci, comp in enumerate(components):
        tname = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        my_nodes = [pin_node.get((ci, p.pin_name)) for p in comp_pins.get(ci, [])]
        my_nodes = [n for n in my_nodes if n is not None]
        is_conn = any(len(node_comps.get(n, set())) >= 2 for n in my_nodes)
        if tname not in INERT_TYPES:
            non_inert += 1
            if is_conn:
                connected += 1
            else:
                floating += 1
        if tname in TWO_TERMINAL_TYPES and len(my_nodes) >= 2 and len(set(my_nodes)) < len(my_nodes):
            self_loops += 1

    giant_nets = sum(1 for cs in node_comps.values() if len(cs) > giant)
    dangling = 0
    for ep1, ep2 in wires:
        for ep in (ep1, ep2):
            if not pins or _nearest_pin_dist(ep, pins) > max_pin_dist:
                dangling += 1

    # UNDER-MERGE signal: wires that exist but were never used to join any pins
    # into a net. A conservative strategy (mutual/nearest) drives the over-merge
    # terms down by simply NOT connecting — that shows up here as unused wires,
    # which the eye reads as "sparse / fragmented joins". The over-merge composite
    # alone misses this; report it alongside.
    used_wires = set()
    effective_wires = set()  # wires inside a net that spans >=2 DISTINCT components
    for n in netlist.nodes:
        used_wires.update(n.wires)
        if len({p.component_idx for p in n.pins}) >= 2:
            effective_wires.update(n.wires)
    n_wires = len(wires)
    unused_wires = max(0, n_wires - len(used_wires))
    pct_wires_used = round(100.0 * len(used_wires) / max(1, n_wires), 1)
    # effective use is NOT gameable by wire-to-wire chaining that never reaches a
    # component: a pin-less or single-component chain contributes 0 effective wires.
    pct_effective_wires = round(100.0 * len(effective_wires) / max(1, n_wires), 1)

    nets = [n for n in netlist.nodes if len(n.pins) >= 2]
    n_comp = len(components)
    # over-merge composite (original)
    composite = round((self_loops + floating + giant_nets) / max(1, n_comp), 4)
    # balanced composite: also penalise under-connection (unused wires), so a
    # strategy can't win just by refusing to join. Lower = better on BOTH axes.
    # CAVEAT: uses raw wire-use, so it can be GAMED by wire-to-wire chains that never
    # reach a component (used%=100 but conn%=0). Prefer join_quality below.
    balanced = round(composite + 0.5 * (unused_wires / max(1, n_wires)), 4)
    # join_quality: the robust objective. composite (floating + over-merge) plus an
    # under-connection penalty based on EFFECTIVE wires (those joining >=2 components),
    # so pin-less chaining can't fake it. Lower = better.
    join_quality = round(composite + 0.5 * (1.0 - len(effective_wires) / max(1, n_wires)), 4)
    return {
        "n_components": n_comp,
        "n_nets": len(nets),
        "self_loop_components": self_loops,
        "floating_components": floating,
        "giant_nets": giant_nets,
        "dangling_wire_ends": dangling,
        "unused_wires": unused_wires,
        "pct_wires_used": pct_wires_used,
        "pct_effective_wires": pct_effective_wires,
        "pct_connected": round(100.0 * connected / max(1, non_inert), 1),
        "nets_per_component": round(len(nets) / max(1, n_comp), 2),
        "composite": composite,
        "balanced": balanced,
        "join_quality": join_quality,
    }

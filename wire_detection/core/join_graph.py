"""Endpoint-graph join — a connectivity model that fixes the structural limits of
the pin-only join (see join_strategies.build_netlist).

The production join makes ONLY component pins graph nodes and uses wires as edges
that merge all pins near both ends. That cannot represent wire-to-wire connectivity
(T-junctions, rails, collinear fragments) and over-merges via all-to-all grabbing.

This builds a graph where BOTH wire endpoints AND component pins are nodes:

  edges:
    1. wire body            ep1 — ep2                       (always)
    2. endpoint ↔ endpoint  |epi - epj| <= tau_join         (fragments, junctions, corners)
    3. endpoint ↔ pin       nearest pin <= tau_pin           (component binding; optional
                            directional: prefer pins the wire points at)
    4. endpoint ↔ wire body point-to-segment <= tau_t        (T-junctions onto rails/buses,
                            no junction-component label needed)

  nets = connected components of {pins ∪ endpoints}, projected onto pins.

Tolerances can be SCALE-RELATIVE (tau = k * characteristic scale) so one strategy
works across the ~6x circuit-scale range in the data. Returns a `Netlist` compatible
with score_netlist.
"""
from __future__ import annotations

import math
from collections import defaultdict

from wire_detection.core.component_assignment import (
    assign_endpoint_to_component,
    pick_pin_for_component,
)
from wire_detection.core.netlist import NetNode, Netlist


# ── geometry ──

def _pt_seg(p, a, b):
    """Distance from point p to segment a-b, and the projection parameter t in [0,1]."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return math.hypot(px - ax, py - ay), 0.0
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    t = max(0.0, min(1.0, t))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot(px - qx, py - qy), t


def estimate_scale(components, wires):
    """Characteristic pixel scale of the schematic — median component bbox diagonal,
    falling back to median wire length. Used to make tolerances scale-relative."""
    diags = []
    for comp in components:
        x1, y1, x2, y2 = comp[2]
        diags.append(math.hypot(x2 - x1, y2 - y1))
    if diags:
        diags.sort()
        s = diags[len(diags) // 2]
        if s > 1.0:
            return s
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in wires]
    if lens:
        lens.sort()
        return max(lens[len(lens) // 2], 1.0)
    return 40.0


# ── union-find ──

class _UF:
    def __init__(self):
        self.parent = {}

    def add(self, x):
        if x not in self.parent:
            self.parent[x] = x

    def find(self, x):
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def build_endpoint_graph(
    wires,
    components,
    pins,
    *,
    tau_pin=30.0,
    tau_join=14.0,
    tau_t=10.0,
    directional=False,
    t_junctions=True,
    scale_rel=False,
    dead_end_rescue=False,
    rescue_factor=2.2,
):
    """Build a netlist from the unified endpoint graph. Tolerances are pixels, or
    multiples of the characteristic scale when scale_rel=True (tau_pin etc. are then
    read as k-factors)."""
    if scale_rel:
        s = estimate_scale(components, wires)
        # clamp so tolerances never collapse on small circuits (would orphan pins)
        # nor explode on huge ones (would over-merge). Floors ~= the fixed defaults.
        tau_pin = min(60.0, max(24.0, tau_pin * s))
        tau_join = min(28.0, max(11.0, tau_join * s))
        tau_t = min(20.0, max(8.0, tau_t * s))

    uf = _UF()

    def pkey(p):
        return ("pin", p.component_idx, p.pin_name)

    def ekey(wi, end):
        return ("ep", wi, end)

    for p in pins:
        uf.add(pkey(p))

    # endpoint coords + register nodes; edge 1: wire body
    eps = []  # (wi, end, (x,y))
    for wi, (a, b) in enumerate(wires):
        for end, ep in ((0, a), (1, b)):
            uf.add(ekey(wi, end))
            eps.append((wi, end, (float(ep[0]), float(ep[1]))))
        uf.union(ekey(wi, 0), ekey(wi, 1))

    # edge 2: endpoint ↔ endpoint (fragments / junctions / corners)
    n = len(eps)
    for i in range(n):
        wi, ei, pi = eps[i]
        for j in range(i + 1, n):
            wj, ej, pj = eps[j]
            if wi == wj:
                continue
            if math.hypot(pi[0] - pj[0], pi[1] - pj[1]) <= tau_join:
                uf.union(ekey(wi, ei), ekey(wj, ej))

    # edge 3: endpoint ↔ pin — COMPONENT-FIRST assignment
    # Step 1: assign each endpoint to the nearest COMPONENT (by bbox proximity)
    # Step 2: once assigned, route to the correct pin based on geometry
    # This handles the common case where endpoints land INSIDE a component's
    # bbox but far from its pin (e.g., 50-80px from pin, but visually overlapping).
    wire_dir = {}
    for wi, (a, b) in enumerate(wires):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        wire_dir[wi] = (dx / L, dy / L)

    # Group pins by component for fast lookup
    comp_pins_map: dict[int, list] = defaultdict(list)
    for p in pins:
        comp_pins_map[p.component_idx].append(p)

    for wi, end, ep in eps:
        ux, uy = wire_dir[wi]
        if end == 0:           # outward direction points away from the wire body
            ux, uy = -ux, -uy

        bestkey = None

        # Use shared component-assignment logic (component_assignment.py)
        comp_result = assign_endpoint_to_component(ep, components, tau_pin)

        if comp_result.component_idx is not None:
            # Endpoint assigned to a component → pick pin by geometry
            ci = comp_result.component_idx
            pin_idx = pick_pin_for_component(ep, ci, components[ci][2], pins)
            if pin_idx is not None:
                # Find the actual pin object
                for p in comp_pins_map.get(ci, []):
                    if p.pin_idx == pin_idx:
                        bestkey = pkey(p)
                        break
        else:
            # --- Step 2b: no component nearby → fall back to nearest pin ---
            best, bestkey_candidate = None, None
            for p in pins:
                d = math.hypot(ep[0] - p.x, ep[1] - p.y)
                if d > tau_pin:
                    continue
                score = d
                if directional and d > 1e-6:
                    vx, vy = (p.x - ep[0]) / d, (p.y - ep[1]) / d
                    cos = ux * vx + uy * vy            # +1 = pin straight ahead of the wire
                    score = d * (1.0 - 0.35 * max(0.0, cos))
                if best is None or score < best:
                    best, bestkey_candidate = score, pkey(p)
            if bestkey_candidate is not None:
                bestkey = bestkey_candidate

        if bestkey is not None:
            uf.union(ekey(wi, end), bestkey)

    # edge 4: endpoint ↔ wire body (T-junction onto a rail/bus)
    if t_junctions:
        for wi, end, ep in eps:
            for wj, (a, b) in enumerate(wires):
                if wj == wi:
                    continue
                d, t = _pt_seg(ep, a, b)
                # only a genuine mid-span landing (not near wj's own ends — those are
                # covered by edge 2) counts as a T-junction
                if d <= tau_t and 0.15 <= t <= 0.85:
                    uf.union(ekey(wi, end), ekey(wj, 0))

    # edge 5: pin ↔ wire body — a component terminal lying ALONG a passing wire/rail
    # (the wire's body, not its end, reaches the pin). This connects rail-tapped
    # components the endpoint-only binding misses, lifting real connectivity without
    # the all-to-all over-merge. Mid-span only (ends are covered by edge 3).
    for p in pins:
        for wi, (a, b) in enumerate(wires):
            d, t = _pt_seg((p.x, p.y), a, b)
            if d <= tau_t and 0.05 <= t <= 0.95:
                uf.union(pkey(p), ekey(wi, 0))

    # dead-end rescue: a wire firmly anchored at ONE end (its net spans exactly one
    # component) but dangling at the other is almost always a real connection the
    # DETECTOR cut short. Give that free end a longer, DIRECTIONAL reach (rescue_factor
    # × tau_pin) toward a pin on a DIFFERENT component. Gated on the one-anchor evidence
    # + forward direction, so it doesn't reintroduce the all-to-all over-merge.
    if dead_end_rescue:
        rescue_r = rescue_factor * tau_pin
        root_comps = defaultdict(set)
        for p in pins:
            root_comps[uf.find(pkey(p))].add(p.component_idx)
        for wi, (a, b) in enumerate(wires):
            ka, kb = ekey(wi, 0), ekey(wi, 1)
            comps_here = root_comps.get(uf.find(ka), set()) | root_comps.get(uf.find(kb), set())
            if len(comps_here) != 1:
                continue                      # only rescue single-component dead-ends
            anchored = next(iter(comps_here))
            for end, ep in ((0, a), (1, b)):
                # skip the anchored end (its nearest pin is on the anchored component)
                np_d, np_comp = float("inf"), None
                for p in pins:
                    d = math.hypot(ep[0] - p.x, ep[1] - p.y)
                    if d < np_d:
                        np_d, np_comp = d, p.component_idx
                if np_comp == anchored and np_d <= tau_pin:
                    continue                  # this is (near) the anchored end
                ux, uy = wire_dir[wi]
                if end == 0:
                    ux, uy = -ux, -uy
                best, bk = None, None
                for p in pins:
                    if p.component_idx == anchored:
                        continue
                    d = math.hypot(ep[0] - p.x, ep[1] - p.y)
                    if d > rescue_r or d < 1e-6:
                        continue
                    vx, vy = (p.x - ep[0]) / d, (p.y - ep[1]) / d
                    if ux * vx + uy * vy < 0.30:   # must point roughly toward the pin
                        continue
                    if best is None or d < best:
                        best, bk = d, pkey(p)
                if bk is not None:
                    uf.union(ekey(wi, end), bk)

    # project onto pins → nets
    groups = defaultdict(list)
    for p in pins:
        groups[uf.find(pkey(p))].append(p)

    # wires belonging to a net = wires whose endpoint shares the net's root
    root_wires = defaultdict(set)
    for wi, end, ep in eps:
        root_wires[uf.find(ekey(wi, end))].add(wi)

    nl = Netlist()
    nl.pin_to_node = {}
    for nid, (root, plist) in enumerate(groups.items()):
        wl = sorted(root_wires.get(root, set()))
        nl.nodes.append(NetNode(node_id=nid, pins=plist, wires=wl))
        for p in plist:
            nl.pin_to_node[(p.component_idx, p.pin_name)] = nid
    return nl

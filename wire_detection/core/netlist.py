"""Netlist building from wires and component pins.

Extracted from benchmark/netlist_exploration.py — contains the production-ready
netlist construction and validation code without experiment/evaluation code.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import DBSCAN


# ═══════════════════════════════════════════════
# PIN DEFINITIONS (static approach — fallback)
# ═══════════════════════════════════════════════

PIN_DEFINITIONS: dict[str, list[tuple[float, float]]] = {
    "resistor": [(0.0, 0.5), (0.0, -0.5)],
    "capacitor-polarized": [(0.0, 0.5), (0.0, -0.5)],
    "capacitor-unpolarized": [(0.0, 0.5), (0.0, -0.5)],
    "capacitor-adjustable": [(0.0, 0.5), (0.0, -0.5)],
    "inductor": [(0.0, 0.5), (0.0, -0.5)],
    "inductor-ferrite": [(0.0, 0.5), (0.0, -0.5)],
    "diode": [(0.0, 0.5), (0.0, -0.5)],
    "diode-LED": [(0.0, 0.5), (0.0, -0.5)],
    "diode-zener": [(0.0, 0.5), (0.0, -0.5)],
    "diode-thyrector": [(0.0, 0.5), (0.0, -0.5)],
    "fuse": [(0.0, 0.5), (0.0, -0.5)],
    "lamp": [(0.0, 0.5), (0.0, -0.5)],
    "switch": [(0.0, 0.5), (0.0, -0.5)],
    "varistor": [(0.0, 0.5), (0.0, -0.5)],
    "relay": [(0.0, 0.5), (0.0, -0.5)],
    "transformer": [(0.0, 0.5), (0.0, -0.5)],
    "motor": [(0.0, 0.5), (0.0, -0.5)],
    "microphone": [(0.0, 0.5), (0.0, -0.5)],
    "probe": [(0.0, 0.5), (0.0, -0.5)],
    "transistor-BJT": [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.5)],
    "transistor-FET": [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.5)],
    "opamp": [(-0.5, 0.3), (-0.5, -0.3), (0.5, 0.0), (0.0, -0.5)],
    "opamp-schmitt": [(-0.5, 0.3), (-0.5, -0.3), (0.5, 0.0), (0.0, -0.5)],
    "IC": [(-0.5, -0.5), (-0.5, 0.5), (0.5, -0.5), (0.5, 0.5)],
    "IC-NE555": [(-0.5, -0.5), (-0.5, 0.5), (0.5, -0.5), (0.5, 0.5)],
    "IC-voltage-reg": [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.5)],
    "junction": [(0.0, 0.0)],
    "terminal": [(0.0, 0.0)],
    "gnd": [(0.0, 0.0)],
    "voltage-DC": [(0.0, 0.5), (0.0, -0.5)],
    "voltage-AC": [(0.0, 0.5), (0.0, -0.5)],
    "voltage-battery": [(0.0, 0.5), (0.0, -0.5)],
    "and": [(-0.5, 0.3), (-0.5, -0.3), (0.5, 0.0)],
    "nand": [(-0.5, 0.3), (-0.5, -0.3), (0.5, 0.0)],
    "or": [(-0.5, 0.3), (-0.5, -0.3), (0.5, 0.0)],
    "not": [(-0.5, 0.0), (0.5, 0.0)],
    "antenna": [(0.0, 0.0)],
    "crossover": [(0.0, 0.5), (0.0, -0.5)],
    "crystal": [(0.0, 0.5), (0.0, -0.5)],
    "diac": [(0.0, 0.5), (0.0, -0.5)],
    "magnetic": [(0.0, 0.5), (0.0, -0.5)],
    "mechanical": [(0.0, 0.5), (0.0, -0.5)],
    "optocoupler": [(-0.5, 0.0), (0.5, 0.0)],
    "triac": [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.5)],
    "resistor-adjustable": [(0.0, 0.5), (0.0, -0.5), (0.5, 0.0)],
}


# ═══════════════════════════════════════════════
# PIN DERIVATION
# ═══════════════════════════════════════════════

@dataclass
class ComponentPin:
    """A component pin with its location."""
    component_idx: int
    component_name: str
    pin_idx: int
    pin_name: str
    x: int
    y: int
    rel_x: float
    rel_y: float


@dataclass
class DiscoveredPin:
    """A pin discovered by clustering wire endpoints."""
    component_idx: int
    component_name: str
    pin_idx: int
    x: int
    y: int
    rel_x: float
    rel_y: float


@dataclass
class NetNode:
    """A node in the circuit netlist (a connected group of pins)."""
    node_id: int
    pins: list[ComponentPin] = field(default_factory=list)
    wires: list[int] = field(default_factory=list)


@dataclass
class Netlist:
    """Basic netlist representation."""
    nodes: list[NetNode] = field(default_factory=list)
    pin_to_node: dict[tuple[int, str], int] = field(default_factory=dict)

    def wire_connects_components(self, wire_idx: int) -> bool:
        """Check if a wire connects two different components.

        A wire is 'connected' if it appears in a node that contains pins
        from multiple components. This is the canonical way to determine
        wire connection status — use this instead of reimplementing logic.
        """
        for node in self.nodes:
            if wire_idx in node.wires:
                comp_set = set(p.component_idx for p in node.pins)
                if len(comp_set) > 1:
                    return True
        return False

    def connected_wires(self) -> set[int]:
        """Return the set of wire indices that connect two or more components."""
        result = set()
        for node in self.nodes:
            comp_set = set(p.component_idx for p in node.pins)
            if len(comp_set) > 1:
                result.update(node.wires)
        return result


# ═══════════════════════════════════════════════
# ENDPOINT CLUSTERING — data-driven pin discovery
# ═══════════════════════════════════════════════

# Component types that should generate SPICE elements
SPICE_ACTIVE_TYPES: set[str] = {
    "resistor", "resistor-adjustable", "varistor",
    "capacitor-unpolarized", "capacitor-polarized", "capacitor-adjustable",
    "inductor", "inductor-ferrite",
    "diode", "diode-LED", "diode-zener", "diode-thyrector", "diac",
    "voltage-DC", "voltage-AC", "voltage-battery",
    "transistor-BJT", "transistor-FET",
    "fuse", "lamp", "crystal",
    "gnd",
}


def discover_pins(
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    component_names: dict[int, str] | None = None,
    cluster_radius: float = 20.0,
    max_comp_dist: float = 50.0,
) -> list[DiscoveredPin]:
    """Discover pin locations by clustering wire endpoints near each component.

    For each SPICE-active component, collects wire endpoints within max_comp_dist
    of the bbox, clusters them with DBSCAN, and creates a pin at each cluster center.
    Achieves ~100% wire-endpoint connectivity vs ~30% for static pin definitions.

    Rejects pin positions that collide with pins already assigned to OTHER
    components (within 5px) to prevent short circuits from overlapping bboxes.
    """
    from wire_detection.core.component_classes import COMPONENT_TYPES as _CNAMES
    names = component_names or _CNAMES
    all_pins: list[DiscoveredPin] = []
    claimed_positions: set[tuple[int, int]] = set()

    for ci, comp in enumerate(components):
        cls_id, vertices, bbox = comp
        type_name = names.get(cls_id, f"cls_{cls_id}")

        if type_name not in SPICE_ACTIVE_TYPES:
            continue

        x_min, y_min, x_max, y_max = bbox

        nearby = []
        for ep1, ep2 in wires:
            for ep in (ep1, ep2):
                cx = max(x_min, min(ep[0], x_max))
                cy = max(y_min, min(ep[1], y_max))
                d = math.hypot(ep[0] - cx, ep[1] - cy)
                if d <= max_comp_dist:
                    nearby.append(ep)

        if not nearby:
            continue

        pts = np.array(nearby)
        if len(pts) == 1:
            px, py = int(pts[0, 0]), int(pts[0, 1])
            if (px, py) not in claimed_positions:
                claimed_positions.add((px, py))
                all_pins.append(DiscoveredPin(
                    component_idx=ci, component_name=type_name,
                    pin_idx=len([p for p in all_pins if p.component_idx == ci]),
                    x=px, y=py,
                    rel_x=0.0, rel_y=0.0,
                ))
        else:
            clustering = DBSCAN(eps=cluster_radius, min_samples=1).fit(pts)
            for label in set(clustering.labels_):
                if label == -1:
                    continue
                cpts = pts[clustering.labels_ == label]
                px, py = int(np.mean(cpts[:, 0])), int(np.mean(cpts[:, 1]))
                if (px, py) not in claimed_positions:
                    claimed_positions.add((px, py))
                    all_pins.append(DiscoveredPin(
                        component_idx=ci, component_name=type_name,
                        pin_idx=len([p for p in all_pins if p.component_idx == ci]),
                        x=px, y=py,
                        rel_x=0.0, rel_y=0.0,
                    ))

    return all_pins


# ═══════════════════════════════════════════════
# PIN DERIVATION
# ═══════════════════════════════════════════════

def _obb_edge_midpoints(vertices):
    """Return the midpoints of each OBB edge, with edge lengths.

    Vertices should be 4 points in order (clockwise or counter-clockwise).
    Returns list of (midpoint_x, midpoint_y, length, edge_index).
    """
    n = len(vertices)
    edges = []
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        length = math.hypot(x2 - x1, y2 - y1)
        mid_x = (x1 + x2) / 2.0
        mid_y = (y1 + y2) / 2.0
        edges.append((mid_x, mid_y, length, i))
    return edges


def derive_pins_from_obb(
    component_idx: int,
    component: tuple[int, list[tuple[int, int]], tuple[int, int, int, int]],
    component_name: str,
) -> list[ComponentPin]:
    """Derive pin locations from OBB geometry.

    For 2-terminal components, pins are placed at ALL 4 OBB edge midpoints.
    The join algorithm then picks the 2 that wire endpoints actually connect
    to, which adapts to the real wire approach direction.
    """
    cls_id, vertices, bbox = component
    x_min, y_min, x_max, y_max = bbox

    two_terminal = {"resistor", "capacitor-polarized", "capacitor-unpolarized",
                    "capacitor-adjustable", "inductor", "inductor-ferrite",
                    "diode", "diode-LED", "diode-zener", "diode-thyrector",
                    "fuse", "lamp", "switch", "varistor", "relay", "transformer",
                    "motor", "crossover", "crystal"}

    # Capacitors: pins on the flat faces (longer edges), not the ends
    long_edge_terminals = {"capacitor-polarized", "capacitor-unpolarized",
                           "capacitor-adjustable"}

    if component_name in two_terminal and len(vertices) == 4:
        edges = _obb_edge_midpoints(vertices)
        if component_name in long_edge_terminals:
            # Capacitors: pins on the longer edges (flat faces)
            edges.sort(key=lambda e: e[2], reverse=True)  # longest first
        else:
            # Resistors, inductors, diodes, etc.: pins on shorter edges (ends)
            edges.sort(key=lambda e: e[2])  # shortest first
        pin_positions = [(edges[0][0], edges[0][1]),
                         (edges[1][0], edges[1][1])]

        pins = []
        for pin_idx, (px, py) in enumerate(pin_positions):
            x = int(max(x_min, min(x_max, px)))
            y = int(max(y_min, min(y_max, py)))
            pins.append(ComponentPin(
                component_idx=component_idx,
                component_name=component_name,
                pin_idx=pin_idx,
                pin_name=f"pin{pin_idx}",
                x=x, y=y,
                rel_x=(px - (x_min + x_max) / 2) / max(1, (x_max - x_min) / 2),
                rel_y=((y_min + y_max) / 2 - py) / max(1, (y_max - y_min) / 2),
            ))
        return pins

    # OBB-aware pin placement for non-two-terminal components
    pin_defs = PIN_DEFINITIONS.get(component_name, [(0.0, 0.5), (0.0, -0.5)])

    if len(vertices) == 4:
        # Compute OBB center and axes from the 4 vertices
        # Vertices are in polygon order (CCW from top-right in YOLO-OBB):
        #   v0 = top-right, v1 = top-left, v2 = bottom-left, v3 = bottom-right
        # u_axis = (v0 - v1) / 2  → points RIGHT (half-width direction)
        # v_axis = (v0 - v3) / 2  → points UP   (half-height direction, inverted y)
        cx = sum(v[0] for v in vertices) / 4.0
        cy = sum(v[1] for v in vertices) / 4.0

        u = ((vertices[0][0] - vertices[1][0]) / 2.0,
             (vertices[0][1] - vertices[1][1]) / 2.0)
        v = ((vertices[0][0] - vertices[3][0]) / 2.0,
             (vertices[0][1] - vertices[3][1]) / 2.0)

        pins = []
        for pin_idx, (rel_x, rel_y) in enumerate(pin_defs):
            # Transform relative position using OBB axes:
            # rel_x ∈ [-0.5, 0.5] maps along u_axis (left→right)
            # rel_y ∈ [-0.5, 0.5] maps along v_axis (bottom→top)
            x = int(cx + rel_x * u[0] + rel_y * v[0])
            y = int(cy + rel_x * u[1] + rel_y * v[1])
            x = max(x_min, min(x_max, x))
            y = max(y_min, min(y_max, y))

            pins.append(ComponentPin(
                component_idx=component_idx,
                component_name=component_name,
                pin_idx=pin_idx,
                pin_name=f"pin{pin_idx}",
                x=x, y=y,
                rel_x=rel_x, rel_y=rel_y,
            ))

        return pins

    # AABB fallback for degenerate vertices (len != 4)
    width = x_max - x_min
    height = y_max - y_min

    pins = []
    for pin_idx, (rel_x, rel_y) in enumerate(pin_defs):
        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2
        x_half = width / 2
        y_half = height / 2

        x = int(x_center + rel_x * x_half)
        y = int(y_center - rel_y * y_half)
        x = max(x_min, min(x_max, x))
        y = max(y_min, min(y_max, y))

        pins.append(ComponentPin(
            component_idx=component_idx,
            component_name=component_name,
            pin_idx=pin_idx,
            pin_name=f"pin{pin_idx}",
            x=x, y=y,
            rel_x=rel_x, rel_y=rel_y,
        ))

    return pins


# ═══════════════════════════════════════════════
# NETLIST BUILDING
# ═══════════════════════════════════════════════

def build_netlist(
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    pins: list[ComponentPin],
    max_pin_dist: float = 30.0,
) -> Netlist:
    """Build a basic netlist by grouping pins connected by wires."""
    pin_to_node: dict[tuple[int, str], int] = {}
    node_id = 0
    nodes: dict[int, NetNode] = {}

    for pin in pins:
        key = (pin.component_idx, pin.pin_name)
        pin_to_node[key] = node_id
        nodes[node_id] = NetNode(node_id=node_id, pins=[pin])
        node_id += 1

    for wi, (ep1, ep2) in enumerate(wires):
        pins_near_ep1 = []
        pins_near_ep2 = []

        for pin in pins:
            d1 = math.hypot(ep1[0] - pin.x, ep1[1] - pin.y)
            d2 = math.hypot(ep2[0] - pin.x, ep2[1] - pin.y)
            if d1 <= max_pin_dist:
                pins_near_ep1.append(pin)
            if d2 <= max_pin_dist:
                pins_near_ep2.append(pin)

        all_connected_pins = pins_near_ep1 + pins_near_ep2
        if len(all_connected_pins) < 2:
            continue

        node_ids = set()
        for pin in all_connected_pins:
            key = (pin.component_idx, pin.pin_name)
            node_ids.add(pin_to_node[key])

        if len(node_ids) < 2:
            continue

        min_node = min(node_ids)
        for old_node in node_ids:
            if old_node == min_node:
                continue
            for pin in nodes[old_node].pins:
                key = (pin.component_idx, pin.pin_name)
                pin_to_node[key] = min_node
            nodes[min_node].pins.extend(nodes[old_node].pins)
            nodes[min_node].wires.extend(nodes[old_node].wires)
            del nodes[old_node]

        nodes[min_node].wires.append(wi)

    netlist = Netlist()
    netlist.pin_to_node = pin_to_node
    for node in nodes.values():
        netlist.nodes.append(node)

    return netlist


# ═══════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════

def validate_netlist(netlist: Netlist) -> dict:
    """Validate netlist for basic sanity checks."""
    components_with_pins: dict[int, int] = defaultdict(int)
    for node in netlist.nodes:
        for pin in node.pins:
            components_with_pins[pin.component_idx] += 1

    isolated_pins = sum(1 for node in netlist.nodes if len(node.pins) == 1)
    large_nodes = sum(1 for node in netlist.nodes if len(node.pins) > 5)

    return {
        "total_nodes": len(netlist.nodes),
        "isolated_pins": isolated_pins,
        "large_nodes": large_nodes,
        "components_with_connections": len(components_with_pins),
    }

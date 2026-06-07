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
    """
    from wire_detection.core.component_classes import COMPONENT_TYPES as _CNAMES
    names = component_names or _CNAMES
    all_pins: list[DiscoveredPin] = []

    for ci, comp in enumerate(components):
        cls_id, vertices, bbox = comp
        type_name = names.get(cls_id, f"cls_{cls_id}")

        if type_name not in SPICE_ACTIVE_TYPES:
            continue

        x_min, y_min, x_max, y_max = bbox

        # Collect nearby wire endpoints
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
            all_pins.append(DiscoveredPin(
                component_idx=ci, component_name=type_name,
                pin_idx=len([p for p in all_pins if p.component_idx == ci]),
                x=int(pts[0, 0]), y=int(pts[0, 1]),
                rel_x=0.0, rel_y=0.0,
            ))
        else:
            clustering = DBSCAN(eps=cluster_radius, min_samples=1).fit(pts)
            for label in set(clustering.labels_):
                if label == -1:
                    continue
                cpts = pts[clustering.labels_ == label]
                all_pins.append(DiscoveredPin(
                    component_idx=ci, component_name=type_name,
                    pin_idx=len([p for p in all_pins if p.component_idx == ci]),
                    x=int(np.mean(cpts[:, 0])), y=int(np.mean(cpts[:, 1])),
                    rel_x=0.0, rel_y=0.0,
                ))

    return all_pins


# ═══════════════════════════════════════════════
# PIN DERIVATION
# ═══════════════════════════════════════════════

def derive_pins_from_obb(
    component_idx: int,
    component: tuple[int, list[tuple[int, int]], tuple[int, int, int, int]],
    component_name: str,
) -> list[ComponentPin]:
    """Derive pin locations from OBB geometry."""
    cls_id, vertices, bbox = component
    pin_defs = PIN_DEFINITIONS.get(component_name, [(0.0, 0.5), (0.0, -0.5)])

    pins = []
    for pin_idx, (rel_x, rel_y) in enumerate(pin_defs):
        x_min, y_min, x_max, y_max = bbox
        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2
        x_half = (x_max - x_min) / 2
        y_half = (y_max - y_min) / 2

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

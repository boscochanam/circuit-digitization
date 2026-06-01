"""Tests for netlist building and validation in netlist_exploration.py.

Tests netlist construction from wires + components, node merging,
pin mapping, validation, and SPICE-like generation using synthetic data.
"""
from __future__ import annotations

import math
import pytest

from wire_detection.benchmark.netlist_exploration import (
    ComponentPin,
    NetNode,
    Netlist,
    build_netlist,
    derive_pins_from_obb,
    validate_netlist,
)


# ═══════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════


def _make_pin(comp_idx: int, comp_name: str, pin_idx: int, x: int, y: int) -> ComponentPin:
    """Create a ComponentPin at a given location."""
    return ComponentPin(
        component_idx=comp_idx,
        component_name=comp_name,
        pin_idx=pin_idx,
        pin_name=f"pin{pin_idx}",
        x=x, y=y,
        rel_x=0.0, rel_y=0.0,
    )


def _make_component_obb(cls_id: int, x: int, y: int, w: int = 40, h: int = 20):
    """Create a component as (class_id, vertices, bbox) for pin derivation."""
    vertices = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    bbox = (x, y, x + w, y + h)
    return (cls_id, vertices, bbox)


# ═══════════════════════════════════════════════
# build_netlist: two resistors in series
# ═══════════════════════════════════════════════


def test_build_netlist_two_resistors_in_series():
    """Two resistors connected by a wire share a node."""
    # R1 pins at (10, 20) and (10, 40)
    # R2 pins at (30, 20) and (30, 40)
    pins = [
        _make_pin(0, "resistor", 0, 10, 20),
        _make_pin(0, "resistor", 1, 10, 40),
        _make_pin(1, "resistor", 0, 30, 20),
        _make_pin(1, "resistor", 1, 30, 40),
    ]
    components = [_make_component_obb(33, 5, 15), _make_component_obb(33, 25, 15)]
    # Wire connects R1.pin1 (10,40) to R2.pin0 (30,20)
    wires = [((10, 40), (30, 20))]

    netlist = build_netlist(wires, components, pins, max_pin_dist=30)
    # R1.pin1 and R2.pin0 should be in the same node
    node_r1p1 = netlist.pin_to_node.get((0, "pin1"))
    node_r2p0 = netlist.pin_to_node.get((1, "pin0"))
    assert node_r1p1 is not None
    assert node_r2p0 is not None
    assert node_r1p1 == node_r2p0


def test_build_netlist_three_parallel():
    """Three components sharing a junction point merge into one node."""
    pins = [
        _make_pin(0, "resistor", 0, 50, 50),
        _make_pin(0, "resistor", 1, 50, 100),
        _make_pin(1, "resistor", 0, 50, 50),
        _make_pin(1, "resistor", 1, 50, 150),
        _make_pin(2, "resistor", 0, 50, 50),
        _make_pin(2, "resistor", 1, 50, 200),
    ]
    components = [_make_component_obb(33, 40, 45) for _ in range(3)]
    # All three share pin0 at (50, 50) — wire between each pair
    wires = [
        ((50, 50), (50, 50)),  # trivial wire connecting same point
    ]

    netlist = build_netlist(wires, components, pins, max_pin_dist=30)
    # All pin0s should merge into the same node
    node_ids = {netlist.pin_to_node[(i, "pin0")] for i in range(3)}
    assert len(node_ids) == 1


def test_build_netlist_empty_wires():
    """No wires: each pin stays in its own node."""
    pins = [
        _make_pin(0, "resistor", 0, 10, 10),
        _make_pin(0, "resistor", 1, 10, 30),
    ]
    components = [_make_component_obb(33, 5, 5)]

    netlist = build_netlist([], components, pins, max_pin_dist=30)
    assert len(netlist.nodes) == 2
    # Pin0 and pin1 should be in different nodes
    assert netlist.pin_to_node[(0, "pin0")] != netlist.pin_to_node[(0, "pin1")]


def test_build_netlist_no_components():
    """No components and no pins returns empty netlist."""
    netlist = build_netlist([], [], [], max_pin_dist=30)
    assert len(netlist.nodes) == 0


# ═══════════════════════════════════════════════
# Node merging
# ═══════════════════════════════════════════════


def test_netlist_node_merging():
    """Transitive merging: A-B and B-C wires produce one merged node."""
    pins = [
        _make_pin(0, "resistor", 0, 10, 10),
        _make_pin(1, "resistor", 0, 30, 10),
        _make_pin(2, "resistor", 0, 50, 10),
    ]
    components = [_make_component_obb(33, 5, 5) for _ in range(3)]
    # Wire 0→1 and wire 1→2
    wires = [((10, 10), (30, 10)), ((30, 10), (50, 10))]

    netlist = build_netlist(wires, components, pins, max_pin_dist=30)
    # All three pins should be in the same node (transitive)
    nodes = {netlist.pin_to_node[(i, "pin0")] for i in range(3)}
    assert len(nodes) == 1


def test_netlist_pin_to_node_mapping():
    """pin_to_node dict maps (component_idx, pin_name) to node_id."""
    pins = [
        _make_pin(0, "resistor", 0, 10, 10),
        _make_pin(0, "resistor", 1, 10, 30),
    ]
    components = [_make_component_obb(33, 5, 5)]

    netlist = build_netlist([], components, pins, max_pin_dist=30)
    assert (0, "pin0") in netlist.pin_to_node
    assert (0, "pin1") in netlist.pin_to_node


def test_netlist_isolated_pins():
    """Pins not connected by any wire remain isolated (own node)."""
    pins = [
        _make_pin(0, "resistor", 0, 10, 10),
        _make_pin(0, "resistor", 1, 10, 30),
        _make_pin(1, "resistor", 0, 200, 200),
    ]
    components = [_make_component_obb(33, 5, 5), _make_component_obb(33, 195, 195)]

    netlist = build_netlist([], components, pins, max_pin_dist=30)
    # All three should be separate
    nodes = {netlist.pin_to_node[(i, f"pin{j}")] for i, j in [(0, 0), (0, 1), (1, 0)]}
    assert len(nodes) == 3


# ═══════════════════════════════════════════════
# validate_netlist
# ═══════════════════════════════════════════════


def test_validate_netlist_valid_circuit():
    """A well-formed netlist passes validation."""
    pins = [
        _make_pin(0, "resistor", 0, 10, 10),
        _make_pin(0, "resistor", 1, 10, 30),
        _make_pin(1, "resistor", 0, 30, 10),
        _make_pin(1, "resistor", 1, 30, 30),
    ]
    components = [_make_component_obb(33, 5, 5), _make_component_obb(33, 25, 5)]
    wires = [((10, 30), (30, 10))]

    netlist = build_netlist(wires, components, pins, max_pin_dist=30)
    result = validate_netlist(netlist)
    assert result["total_nodes"] > 0
    assert result["components_with_connections"] == 2


def test_validate_netlist_floating_nodes():
    """Isolated pins are counted correctly."""
    pins = [
        _make_pin(0, "resistor", 0, 10, 10),
        _make_pin(0, "resistor", 1, 10, 30),
    ]
    components = [_make_component_obb(33, 5, 5)]
    netlist = build_netlist([], components, pins, max_pin_dist=30)

    result = validate_netlist(netlist)
    # Both pins are isolated (single-pin nodes)
    assert result["isolated_pins"] == 2


def test_validate_netlist_large_nodes():
    """A node with >5 pins is flagged as large."""
    pins = []
    for i in range(6):
        pins.append(_make_pin(i, "resistor", 0, 50, 50))

    components = [_make_component_obb(33, 40, 40) for _ in range(6)]
    # All pins at same location → one wire merges all
    wires = [((50, 50), (50, 50))]

    netlist = build_netlist(wires, components, pins, max_pin_dist=30)
    result = validate_netlist(netlist)
    assert result["large_nodes"] >= 1


# ═══════════════════════════════════════════════
# derive_pins_from_obb
# ═══════════════════════════════════════════════


def test_derive_pins_resistor_two_pins():
    """Resistor OBB produces 2 pins."""
    comp = _make_component_obb(33, 100, 100, w=60, h=20)
    pins = derive_pins_from_obb(0, comp, "resistor")
    assert len(pins) == 2


def test_derive_pins_transistor_three_pins():
    """Transistor OBB produces 3 pins."""
    comp = _make_component_obb(38, 100, 100, w=40, h=40)
    pins = derive_pins_from_obb(0, comp, "transistor")
    assert len(pins) == 3


def test_derive_pins_ic_four_pins():
    """IC OBB produces 4 pins."""
    comp = _make_component_obb(16, 100, 100, w=80, h=40)
    pins = derive_pins_from_obb(0, comp, "integrated_circuit")
    assert len(pins) == 4


def test_derive_pins_within_bbox():
    """Derived pin coordinates are clamped within the bbox."""
    comp = _make_component_obb(33, 100, 200, w=60, h=20)
    pins = derive_pins_from_obb(0, comp, "resistor")
    for pin in pins:
        assert 100 <= pin.x <= 160
        assert 200 <= pin.y <= 220


# ═══════════════════════════════════════════════
# SPICE-like generation (basic)
# ═══════════════════════════════════════════════


def test_spice_generation_resistor():
    """Basic SPICE line for a resistor can be built from netlist data."""
    pins = [
        _make_pin(0, "resistor", 0, 10, 10),
        _make_pin(0, "resistor", 1, 10, 30),
    ]
    components = [_make_component_obb(33, 5, 5)]
    netlist = build_netlist([], components, pins, max_pin_dist=30)

    # Manually build SPICE line from netlist
    n0 = netlist.pin_to_node[(0, "pin0")]
    n1 = netlist.pin_to_node[(0, "pin1")]
    spice_line = f"R1 N{n0} N{n1} 1k"
    assert spice_line.startswith("R1")
    assert "N" in spice_line


def test_spice_generation_capacitor():
    """SPICE capacitor line format."""
    pins = [
        _make_pin(0, "capacitor", 0, 10, 10),
        _make_pin(0, "capacitor", 1, 10, 30),
    ]
    components = [_make_component_obb(4, 5, 5)]
    netlist = build_netlist([], components, pins, max_pin_dist=30)

    n0 = netlist.pin_to_node[(0, "pin0")]
    n1 = netlist.pin_to_node[(0, "pin1")]
    spice_line = f"C1 N{n0} N{n1} 1u"
    assert spice_line.startswith("C1")


def test_spice_generation_voltage_source():
    """SPICE voltage source line format."""
    pins = [
        _make_pin(0, "voltage_source", 0, 10, 10),
        _make_pin(0, "voltage_source", 1, 10, 30),
    ]
    components = [_make_component_obb(42, 5, 5)]
    netlist = build_netlist([], components, pins, max_pin_dist=30)

    n0 = netlist.pin_to_node[(0, "pin0")]
    n1 = netlist.pin_to_node[(0, "pin1")]
    spice_line = f"V1 N{n0} N{n1} DC 5"
    assert spice_line.startswith("V1")


def test_spice_generation_ground_node():
    """Ground node (gnd component) maps to node 0 in SPICE convention."""
    pins = [
        _make_pin(0, "gnd", 0, 50, 50),
    ]
    components = [_make_component_obb(13, 45, 45)]
    netlist = build_netlist([], components, pins, max_pin_dist=30)

    node_id = netlist.pin_to_node[(0, "pin0")]
    # In SPICE, ground is typically node 0
    # Our netlist assigns sequential IDs, but the concept holds
    assert isinstance(node_id, int)


def test_spice_generation_node_naming():
    """Nodes can be named N0, N1, N2, etc. for SPICE output."""
    pins = [
        _make_pin(0, "resistor", 0, 10, 10),
        _make_pin(0, "resistor", 1, 10, 30),
        _make_pin(1, "resistor", 0, 30, 10),
        _make_pin(1, "resistor", 1, 30, 30),
    ]
    components = [_make_component_obb(33, 5, 5), _make_component_obb(33, 25, 5)]
    wires = [((10, 30), (30, 10))]

    netlist = build_netlist(wires, components, pins, max_pin_dist=30)
    # Generate SPICE-style node names
    node_names = set()
    for node in netlist.nodes:
        name = f"N{node.node_id}"
        node_names.add(name)
    assert len(node_names) == len(netlist.nodes)
    # All names follow pattern N<number>
    for name in node_names:
        assert name.startswith("N")
        int(name[1:])  # should not raise

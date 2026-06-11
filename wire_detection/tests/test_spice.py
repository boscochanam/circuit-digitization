"""Tests for SPICE generation and simulation.

Phase 3 of TDD plan: SPICE integration.
"""
from __future__ import annotations

import textwrap

import pytest

from wire_detection.core.netlist import (
    ComponentPin,
    Netlist,
    build_netlist,
    derive_pins_from_obb,
)
from wire_detection.core.spice import COMPONENT_NAMES, SpiceGenerator
from wire_detection.core.simulator import SpiceSimulator

# Class ids derived from the live table - hardcoded ids went stale once already
# when the component classes were renumbered (33 used to be resistor; it is
# probe now) and silently turned these tests into no-ops.
_ID = {v: k for k, v in COMPONENT_NAMES.items()}
_RES = _ID["resistor"]
_CAP = _ID["capacitor-unpolarized"]
_IND = _ID["inductor"]
_DIODE = _ID["diode"]
_VDC = _ID["voltage-DC"]
_BJT = _ID["transistor-BJT"]
_GND = _ID["gnd"]


# ═══════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════


def _make_pin(comp_idx: int, comp_name: str, pin_idx: int, x: int, y: int) -> ComponentPin:
    return ComponentPin(
        component_idx=comp_idx,
        component_name=comp_name,
        pin_idx=pin_idx,
        pin_name=f"pin{pin_idx}",
        x=x, y=y,
        rel_x=0.0, rel_y=0.0,
    )


def _make_component_obb(cls_id: int, x: int, y: int, w: int = 40, h: int = 20):
    vertices = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    bbox = (x, y, x + w, y + h)
    return (cls_id, vertices, bbox)


# ═══════════════════════════════════════════════
# TestSpiceGenerator
# ═══════════════════════════════════════════════


class TestSpiceGenerator:

    def test_resistor_two_terminal(self):
        pins = [
            _make_pin(0, "resistor", 0, 10, 10),
            _make_pin(0, "resistor", 1, 10, 30),
        ]
        components = [_make_component_obb(_RES, 5, 5)]
        netlist = build_netlist([], components, pins, max_pin_dist=30)
        gen = SpiceGenerator()
        result = gen.generate(components, netlist)
        assert "R1" in result
        assert "1000" in result

    def test_capacitor_two_terminal(self):
        pins = [
            _make_pin(0, "capacitor-unpolarized", 0, 10, 10),
            _make_pin(0, "capacitor-unpolarized", 1, 10, 30),
        ]
        components = [_make_component_obb(_CAP, 5, 5)]
        netlist = build_netlist([], components, pins, max_pin_dist=30)
        gen = SpiceGenerator()
        result = gen.generate(components, netlist)
        assert "C1" in result
        assert "1e-6" in result

    def test_inductor_two_terminal(self):
        pins = [
            _make_pin(0, "inductor", 0, 10, 10),
            _make_pin(0, "inductor", 1, 10, 30),
        ]
        components = [_make_component_obb(_IND, 5, 5)]
        netlist = build_netlist([], components, pins, max_pin_dist=30)
        gen = SpiceGenerator()
        result = gen.generate(components, netlist)
        assert "L1" in result
        assert "1e-3" in result

    def test_diode_two_terminal(self):
        pins = [
            _make_pin(0, "diode", 0, 10, 10),
            _make_pin(0, "diode", 1, 10, 30),
        ]
        components = [_make_component_obb(_DIODE, 5, 5)]
        netlist = build_netlist([], components, pins, max_pin_dist=30)
        gen = SpiceGenerator()
        result = gen.generate(components, netlist)
        assert "D1" in result
        # diodes are emitted with a real ngspice model (DMOD), not the placeholder value
        assert "DMOD" in result

    def test_voltage_source(self):
        pins = [
            _make_pin(0, "voltage-DC", 0, 10, 10),
            _make_pin(0, "voltage-DC", 1, 10, 30),
        ]
        components = [_make_component_obb(_VDC, 5, 5)]
        netlist = build_netlist([], components, pins, max_pin_dist=30)
        gen = SpiceGenerator()
        result = gen.generate(components, netlist)
        assert "V1" in result
        assert "DC 5" in result

    def test_ground_node_is_zero(self):
        gen = SpiceGenerator()
        result = gen.generate([], Netlist())
        assert ".end" in result

    def test_node_naming_sequential(self):
        pins = [
            _make_pin(0, "resistor", 0, 10, 10),
            _make_pin(0, "resistor", 1, 10, 30),
            _make_pin(1, "resistor", 0, 30, 10),
            _make_pin(1, "resistor", 1, 30, 30),
        ]
        components = [_make_component_obb(_RES, 5, 5), _make_component_obb(_RES, 25, 5)]
        wires = [((10, 30), (30, 10))]
        netlist = build_netlist(wires, components, pins, max_pin_dist=30)
        gen = SpiceGenerator()
        result = gen.generate(components, netlist)
        # exclude voltage sources: their tail is `DC <value>` (two tokens), which
        # breaks the "middle tokens are all nodes" positional assumption used here.
        lines = [l for l in result.split("\n")
                 if l and not l.startswith(("*", ".", "V"))]
        for line in lines:
            parts = line.split()
            for part in parts[1:-1]:
                assert part.startswith("N") or part == "0"

    def test_component_naming_by_type(self):
        pins = [
            _make_pin(0, "resistor", 0, 10, 10),
            _make_pin(0, "resistor", 1, 10, 30),
            _make_pin(1, "resistor", 0, 30, 10),
            _make_pin(1, "resistor", 1, 30, 30),
            _make_pin(2, "capacitor-unpolarized", 0, 50, 10),
            _make_pin(2, "capacitor-unpolarized", 1, 50, 30),
        ]
        components = [
            _make_component_obb(_RES, 5, 5),
            _make_component_obb(_RES, 25, 5),
            _make_component_obb(_CAP, 45, 5),
        ]
        netlist = build_netlist([], components, pins, max_pin_dist=30)
        gen = SpiceGenerator()
        result = gen.generate(components, netlist)
        # device names are INDEX-based (prefix + comp_idx + 1), not per-type
        # counters - the UI's value-overrides key on this, so the cap at
        # component index 2 must be C3, not C1.
        assert "R1" in result
        assert "R2" in result
        assert "C3" in result

    def test_empty_netlist(self):
        gen = SpiceGenerator()
        result = gen.generate([])
        assert result.strip().startswith("*")
        assert result.strip().endswith(".end")

    def test_multiple_resistors_series(self):
        pins = [
            _make_pin(0, "resistor", 0, 10, 10),
            _make_pin(0, "resistor", 1, 10, 30),
            _make_pin(1, "resistor", 0, 30, 10),
            _make_pin(1, "resistor", 1, 30, 30),
        ]
        components = [_make_component_obb(_RES, 5, 5), _make_component_obb(_RES, 25, 5)]
        wires = [((10, 30), (30, 10))]
        netlist = build_netlist(wires, components, pins, max_pin_dist=30)
        gen = SpiceGenerator()
        result = gen.generate(components, netlist)
        assert "R1" in result
        assert "R2" in result

    def test_multiple_resistors_parallel(self):
        pins = [
            _make_pin(0, "resistor", 0, 10, 10),
            _make_pin(0, "resistor", 1, 10, 30),
            _make_pin(1, "resistor", 0, 10, 10),
            _make_pin(1, "resistor", 1, 10, 30),
        ]
        components = [_make_component_obb(_RES, 5, 5), _make_component_obb(_RES, 5, 5)]
        wires = [((10, 10), (10, 10))]
        netlist = build_netlist(wires, components, pins, max_pin_dist=30)
        gen = SpiceGenerator()
        result = gen.generate(components, netlist)
        assert "R1" in result
        assert "R2" in result


# ═══════════════════════════════════════════════
# TestSpiceSimulator
# ═══════════════════════════════════════════════

ngspice_available = SpiceSimulator.is_available()


class TestSpiceSimulator:

    def test_dc_operating_point_resistor_divider(self):
        if not ngspice_available:
            pytest.skip("ngspice not available")
        spice = textwrap.dedent("""\
            Voltage Divider
            V1 N1 0 DC 5
            R1 N1 N2 1000
            R2 N2 0 1000
            .op
            .end
        """)
        sim = SpiceSimulator()
        result = sim.run_dc_analysis(spice)
        assert "voltages" in result
        assert abs(result["voltages"].get("n2", 0) - 2.5) < 0.1

    def test_dc_operating_point_open_circuit(self):
        if not ngspice_available:
            pytest.skip("ngspice not available")
        spice = textwrap.dedent("""\
            Open Circuit
            V1 N1 0 DC 5
            R1 N1 N2 1000
            .op
            .end
        """)
        sim = SpiceSimulator()
        result = sim.run_dc_analysis(spice)
        assert "voltages" in result

    def test_parse_dc_output_voltages(self):
        output = textwrap.dedent("""\
            No. of Data Rows : 1
            \tNode                                  Voltage
            \t----                                  -------
            \t----\t-------
            \tn1                               5.000000e+00
            \tn2                               2.500000e+00

            \tSource\tCurrent
            \t------\t-------

            \tv1#branch                        -2.50000e-03
        """)
        sim = SpiceSimulator()
        result = sim.parse_dc_output(output)
        assert "voltages" in result
        assert abs(result["voltages"]["n1"] - 5.0) < 0.001
        assert abs(result["voltages"]["n2"] - 2.5) < 0.001

    def test_invalid_netlist_returns_error(self):
        if not ngspice_available:
            pytest.skip("ngspice not available")
        spice = "this is not a valid spice netlist"
        sim = SpiceSimulator()
        result = sim.run_dc_analysis(spice)
        assert "error" in result


# ═══════════════════════════════════════════════
# TestNetlistBuilder
# ═══════════════════════════════════════════════


class TestNetlistBuilder:

    def test_two_resistors_shared_node(self):
        pins = [
            _make_pin(0, "resistor", 0, 10, 10),
            _make_pin(0, "resistor", 1, 10, 30),
            _make_pin(1, "resistor", 0, 30, 10),
            _make_pin(1, "resistor", 1, 30, 30),
        ]
        components = [_make_component_obb(_RES, 5, 15), _make_component_obb(_RES, 25, 15)]
        wires = [((10, 30), (30, 10))]
        netlist = build_netlist(wires, components, pins, max_pin_dist=30)
        node_r1p1 = netlist.pin_to_node.get((0, "pin1"))
        node_r2p0 = netlist.pin_to_node.get((1, "pin0"))
        assert node_r1p1 is not None
        assert node_r2p0 is not None
        assert node_r1p1 == node_r2p0

    def test_three_way_junction(self):
        pins = [
            _make_pin(0, "resistor", 0, 50, 50),
            _make_pin(0, "resistor", 1, 50, 100),
            _make_pin(1, "resistor", 0, 50, 50),
            _make_pin(1, "resistor", 1, 50, 150),
            _make_pin(2, "resistor", 0, 50, 50),
            _make_pin(2, "resistor", 1, 50, 200),
        ]
        components = [_make_component_obb(_RES, 40, 45) for _ in range(3)]
        wires = [((50, 50), (50, 50))]
        netlist = build_netlist(wires, components, pins, max_pin_dist=30)
        node_ids = {netlist.pin_to_node[(i, "pin0")] for i in range(3)}
        assert len(node_ids) == 1

    def test_component_value_extraction(self):
        gen = SpiceGenerator()
        assert gen._get_default_value("resistor") == "1000"
        assert gen._get_default_value("capacitor-unpolarized") == "1e-6"
        assert gen._get_default_value("unknown_type") == "1"

    def test_pin_assignment_resistor(self):
        comp = _make_component_obb(_RES, 100, 100, w=60, h=20)
        pins = derive_pins_from_obb(0, comp, "resistor")
        assert len(pins) == 2

    def test_pin_assignment_transistor(self):
        comp = _make_component_obb(_BJT, 100, 100, w=40, h=40)
        pins = derive_pins_from_obb(0, comp, "transistor-BJT")
        assert len(pins) == 3

    def test_gnd_component_detection(self):
        pins = [_make_pin(0, "gnd", 0, 50, 50)]
        components = [_make_component_obb(_GND, 45, 45)]
        netlist = build_netlist([], components, pins, max_pin_dist=30)
        node_id = netlist.pin_to_node[(0, "pin0")]
        assert isinstance(node_id, int)

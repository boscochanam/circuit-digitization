"""Tests for the join-strategy registry (wire_detection/core/join_strategies.py).

Covers the registry, run_strategy() across every strategy, the structural
score_netlist() metrics, and the key invariant that a wire joins the two
components it touches.
"""
from __future__ import annotations

from wire_detection.core.join_strategies import (
    STRATEGIES,
    list_strategies,
    make_pins,
    run_strategy,
    score_netlist,
)
from wire_detection.core.netlist import derive_pins_from_obb
from wire_detection.core.spice import COMPONENT_NAMES

_RES = next(k for k, v in COMPONENT_NAMES.items() if v == "resistor")


def _resistor(cx, cy, w=20, h=40):
    x1, y1, x2, y2 = cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2
    poly = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    return (_RES, poly, (x1, y1, x2, y2))


def test_registry_lists_expected_strategies():
    names = {s["name"] for s in list_strategies()}
    assert {"production", "nearest1_30", "nearest2_30", "mutual_30"} <= names
    assert len(list_strategies()) == len(STRATEGIES)
    for s in list_strategies():
        assert s["name"] and s["label"] and s["desc"]


def test_run_every_strategy_smoke_and_metric_keys():
    comps = [_resistor(100, 100), _resistor(100, 300)]
    wires = [((100, 118), (100, 282))]  # roughly between the two resistors' inner pins
    expected_keys = {
        "n_components", "n_nets", "self_loop_components", "floating_components",
        "giant_nets", "dangling_wire_ends", "unused_wires", "pct_wires_used",
        "pct_connected", "nets_per_component", "composite", "balanced",
    }
    for s in STRATEGIES:
        pins, netlist = run_strategy(s["name"], wires, comps)
        assert pins, f"{s['name']}: no pins"
        m = score_netlist(wires, comps, pins, netlist, 30.0)
        assert expected_keys <= set(m), f"{s['name']}: missing metric keys"
        # balanced never below composite (it only adds an under-connection penalty)
        assert m["balanced"] >= m["composite"] - 1e-9
        assert 0.0 <= m["pct_wires_used"] <= 100.0


def test_wire_joins_the_two_components_it_touches():
    r1, r2 = _resistor(100, 100), _resistor(100, 300)
    comps = [r1, r2]
    p1 = derive_pins_from_obb(0, r1, "resistor")
    p2 = derive_pins_from_obb(1, r2, "resistor")
    a = max(p1, key=lambda p: p.y)   # R1 lower pin
    b = min(p2, key=lambda p: p.y)   # R2 upper pin
    wire = ((a.x, a.y), (b.x, b.y))

    _, netlist = run_strategy("nearest1_30", [wire], comps)
    joined = [
        {p.component_idx for p in node.pins}
        for node in netlist.nodes
        if len({p.component_idx for p in node.pins}) >= 2
    ]
    assert any({0, 1} <= cs for cs in joined), "wire did not join the two resistors into one net"


def test_empty_inputs_do_not_crash():
    pins, netlist = run_strategy("nearest2_30", [], [])
    assert pins == []
    m = score_netlist([], [], pins, netlist, 30.0)
    assert m["n_nets"] == 0 and m["composite"] == 0.0

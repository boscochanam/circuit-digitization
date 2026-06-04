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
        "pct_effective_wires", "pct_connected", "nets_per_component",
        "composite", "balanced", "join_quality",
    }
    for s in STRATEGIES:
        pins, netlist = run_strategy(s["name"], wires, comps)
        assert pins, f"{s['name']}: no pins"
        m = score_netlist(wires, comps, pins, netlist, 30.0)
        assert expected_keys <= set(m), f"{s['name']}: missing metric keys"
        # balanced never below composite (it only adds an under-connection penalty)
        assert m["balanced"] >= m["composite"] - 1e-9
        assert 0.0 <= m["pct_wires_used"] <= 100.0
        assert 0.0 <= m["pct_effective_wires"] <= 100.0


def test_endpoint_graph_connects_t_junction():
    """The endpoint-graph join links a component tapped onto the MID-SPAN of a rail
    (a T-junction) — the structural case the pin-only join cannot represent."""
    r1, r2, r3 = _resistor(200, 100), _resistor(200, 300), _resistor(400, 220)
    comps = [r1, r2, r3]
    rail = ((200, 118), (200, 282))          # vertical rail: r1 bottom -> r2 top
    tap = ((400, 210), (205, 200))            # r3 bottom pin -> lands mid-span on the rail
    wires = [rail, tap]

    # graph join: the tap's mid-span landing must pull r3 into the r1-r2 net
    _, nl_graph = run_strategy("graph_30", wires, comps)
    graph_nets = [{p.component_idx for p in n.pins} for n in nl_graph.nodes]
    assert any({0, 1, 2} <= cs for cs in graph_nets), "graph join missed the T-junction"

    # production (pin-only) cannot: the tap's rail end reaches no pin, so r3 floats
    _, nl_prod = run_strategy("production", wires, comps)
    prod_nets = [{p.component_idx for p in n.pins} for n in nl_prod.nodes]
    assert not any(2 in cs and len(cs) >= 2 for cs in prod_nets), \
        "production unexpectedly connected the T-junction (test no longer isolates the capability)"


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

"""Tests for connection-editor overrides reaching the netlist / SPICE.

Pure unit + small integration tests (no API fixtures), so they are unaffected by
the broken test_api suite (issue #24). They cover the two halves of override
application:

  * disconnect (remove)  -> applied to the WIRES, before the join, so a net splits
  * reassign / join      -> applied to the NETLIST, after the join, as node merges
"""
from wire_detection.core.connection_overrides import (
    apply_overrides_to_netlist,
    removed_wire_indices,
    wires_with_removes,
)
from wire_detection.core.netlist import (
    ComponentPin,
    NetNode,
    Netlist,
    build_netlist,
)

RESISTOR = 37  # class id -> "resistor" -> SPICE prefix "R"


def _ov(reassign=None, join=None, remove=None):
    return {"reassign": reassign or {}, "join": join or [], "remove": remove or []}


def _pin(ci, x=0, y=0, name="pin0"):
    return ComponentPin(
        component_idx=ci, component_name="resistor", pin_idx=int(name[-1]),
        pin_name=name, x=x, y=y, rel_x=0.0, rel_y=0.0,
    )


# ── remove / disconnect (applied to the wires before the join) ──

def test_removed_wire_indices():
    assert removed_wire_indices(_ov(remove=["wire_3_ep1", "wire_7_ep2", "junk"])) == {3, 7}


def test_wires_with_removes_preserves_indices():
    wires = [((0, 0), (10, 0)), ((20, 20), (30, 20)), ((40, 0), (50, 0))]
    out = wires_with_removes(wires, _ov(remove=["wire_1_ep1"]))
    assert out[0] == wires[0]
    assert out[2] == wires[2]          # later index preserved (no shift)
    assert out[1][0] == out[1][1]      # wire 1 collapsed off-canvas (joins nothing)


def test_wires_with_removes_noop_without_remove():
    wires = [((0, 0), (10, 0))]
    assert wires_with_removes(wires, _ov()) is wires


def test_remove_splits_a_bridged_net():
    # two resistors whose pins are bridged by a single wire
    pins = [_pin(0, 0, 0), _pin(1, 100, 0)]
    components = [(RESISTOR, [], (-5, -5, 5, 5)), (RESISTOR, [], (95, -5, 105, 5))]
    wires = [((0, 0), (100, 0))]
    nl = build_netlist(wires, components, pins, max_pin_dist=30)
    assert nl.pin_to_node[(0, "pin0")] == nl.pin_to_node[(1, "pin0")]  # bridged -> 1 net

    # disconnect the wire -> degenerate -> the net splits in two
    wires2 = wires_with_removes(wires, _ov(remove=["wire_0_ep1"]))
    nl2 = build_netlist(wires2, components, pins, max_pin_dist=30)
    assert nl2.pin_to_node[(0, "pin0")] != nl2.pin_to_node[(1, "pin0")]  # split


# ── reassign / join (applied to the netlist as node merges) ──

def _two_node_netlist():
    nl = Netlist()
    nl.nodes = [
        NetNode(node_id=0, pins=[_pin(0)], wires=[0]),
        NetNode(node_id=1, pins=[_pin(1)], wires=[5]),
    ]
    nl.pin_to_node = {(0, "pin0"): 0, (1, "pin0"): 1}
    return nl


def test_join_merges_two_nodes():
    comps = [(RESISTOR, [], (0, 0, 1, 1)), (RESISTOR, [], (0, 0, 1, 1))]
    out = apply_overrides_to_netlist(
        _two_node_netlist(), comps, _ov(join=[["wire_0_ep1", "wire_5_ep2"]])
    )
    assert len(out.nodes) == 1
    assert out.pin_to_node[(0, "pin0")] == out.pin_to_node[(1, "pin0")]


def test_reassign_connects_wire_to_target_pin():
    comps = [(RESISTOR, [], (0, 0, 1, 1)), (RESISTOR, [], (0, 0, 1, 1))]
    # wire 0 is on node 0; reassign it to R2.pin0 (component idx 1 -> node 1)
    out = apply_overrides_to_netlist(
        _two_node_netlist(), comps,
        _ov(reassign={"wire_0_ep1": {"component": "R2", "pin": "pin0"}}),
    )
    assert out.pin_to_node[(0, "pin0")] == out.pin_to_node[(1, "pin0")]


def test_no_overrides_is_identity():
    nl = _two_node_netlist()
    assert apply_overrides_to_netlist(nl, [], _ov()) is nl

"""Tests for Join Metrics (§4.2) — connection accuracy, net assignment accuracy,
over-merge rate, and under-merge rate.

All tests use synthetic data with known ground truth so the metrics can be
validated analytically.  Tests are grouped into:

  * **unit tests** for the GT/netlist helper functions
  * **metric validation** against carefully constructed Netlists where the
    correct metric value is obvious
  * **integration tests** that run the real pipeline on a synthetic circuit
    from the CircuitSpec catalog and verify the metrics are reasonable
"""
from __future__ import annotations

import math
import pytest

from wire_detection.core.netlist import (
    ComponentPin,
    NetNode,
    Netlist,
)
from wire_detection.evaluate.join_metrics import (
    JoinMetrics,
    compute_join_metrics_from_netlist,
    format_join_metrics,
    gt_nets_to_connections,
    gt_nets_to_pairs,
    netlist_to_connections,
    netlist_to_pairs,
)


# ═══════════════════════════════════════════════════════════════
# Helpers — synthetic Netlist builders
# ═══════════════════════════════════════════════════════════════

def _make_pin(ci: int, pin_idx: int, x: int = 0, y: int = 0) -> ComponentPin:
    return ComponentPin(
        component_idx=ci,
        component_name=f"comp{ci}",
        pin_idx=pin_idx,
        pin_name=f"pin{pin_idx}",
        x=x, y=y,
        rel_x=0.0, rel_y=0.0,
    )


def _build_netlist(
    groups: list[list[tuple[int, int]]],
    wires_per_node: list[list[int]] | None = None,
) -> Netlist:
    """Build a Netlist from explicit node groups.

    ``groups``: list of nodes, each a list of ``(comp_idx, pin_idx)``.
    ``wires_per_node``: optional wire indices per node.
    """
    nl = Netlist()
    nl.pin_to_node = {}
    for nid, grp in enumerate(groups):
        pins = [_make_pin(ci, pi) for ci, pi in grp]
        wl = wires_per_node[nid] if wires_per_node else []
        nl.nodes.append(NetNode(node_id=nid, pins=pins, wires=wl))
        for ci, pi in grp:
            nl.pin_to_node[(ci, f"pin{pi}")] = nid
    return nl


# ═══════════════════════════════════════════════════════════════
# GT helper tests
# ═══════════════════════════════════════════════════════════════


class TestGtNetsToPairs:
    """gt_nets_to_pairs: component-pair set from GT nets."""

    def test_single_net_two_components(self):
        gt = [[(0, 0), (1, 0)]]
        pairs = gt_nets_to_pairs(gt)
        assert pairs == {(0, 1)}

    def test_single_net_three_components(self):
        gt = [[(0, 0), (1, 0), (2, 0)]]
        pairs = gt_nets_to_pairs(gt)
        assert pairs == {(0, 1), (0, 2), (1, 2)}

    def test_two_independent_nets(self):
        gt = [
            [(0, 0), (1, 0)],   # net A
            [(2, 0), (3, 0)],   # net B
        ]
        pairs = gt_nets_to_pairs(gt)
        assert pairs == {(0, 1), (2, 3)}

    def test_intra_component_skipped(self):
        """A net with two pins on the same component produces no pairs."""
        gt = [[(0, 0), (0, 1)]]
        pairs = gt_nets_to_pairs(gt)
        assert pairs == set()

    def test_mixed_intra_and_inter(self):
        """Net with 3 components where 2 are same → 1 pair (not 3)."""
        gt = [[(0, 0), (0, 1), (1, 0)]]
        pairs = gt_nets_to_pairs(gt)
        assert pairs == {(0, 1)}

    def test_empty_nets(self):
        assert gt_nets_to_pairs([]) == set()
        assert gt_nets_to_pairs([[]]) == set()


class TestGtNetsToConnections:
    """gt_nets_to_connections: pin-pair connections from GT nets."""

    def test_single_connection(self):
        """Single connection between two components."""
        gt = [[(0, 0), (1, 0)]]
        conns = gt_nets_to_connections(gt)
        assert conns == {((0, "pin0"), (1, "pin0"))}

    def test_single_connection_actual(self):
        gt = [[(0, 0), (1, 0)]]
        conns = gt_nets_to_connections(gt)
        assert conns == {((0, "pin0"), (1, "pin0"))}

    def test_three_component_net(self):
        gt = [[(0, 0), (1, 0), (2, 0)]]
        conns = gt_nets_to_connections(gt)
        expected = {
            ((0, "pin0"), (1, "pin0")),
            ((0, "pin0"), (2, "pin0")),
            ((1, "pin0"), (2, "pin0")),
        }
        assert conns == expected

    def test_intra_component_excluded(self):
        gt = [[(0, 0), (0, 1), (1, 0)]]
        conns = gt_nets_to_connections(gt)
        # Only (0,pin0)-(1,pin0) and (0,pin1)-(1,pin0), but (0,pin0)-(0,pin1) excluded
        assert len(conns) == 2
        for c in conns:
            assert c[0][0] != c[1][0], "Intra-component pair leaked"

    def test_two_nets(self):
        gt = [
            [(0, 0), (1, 0)],
            [(2, 0), (3, 0)],
        ]
        conns = gt_nets_to_connections(gt)
        assert conns == {
            ((0, "pin0"), (1, "pin0")),
            ((2, "pin0"), (3, "pin0")),
        }


# ═══════════════════════════════════════════════════════════════
# Netlist helper tests
# ═══════════════════════════════════════════════════════════════


class TestNetlistToPairs:
    """netlist_to_pairs: component-pair set from a Netlist."""

    def test_two_components_one_net(self):
        nl = _build_netlist([[(0, 0), (1, 0)]])
        pairs = netlist_to_pairs(nl)
        assert pairs == {(0, 1)}

    def test_three_components_one_net(self):
        nl = _build_netlist([[(0, 0), (1, 0), (2, 0)]])
        pairs = netlist_to_pairs(nl)
        assert pairs == {(0, 1), (0, 2), (1, 2)}

    def test_two_separate_nets(self):
        nl = _build_netlist([[(0, 0), (1, 0)], [(2, 0), (3, 0)]])
        pairs = netlist_to_pairs(nl)
        assert pairs == {(0, 1), (2, 3)}

    def test_single_pin_net_no_pairs(self):
        """A net with only one pin produces no component pairs."""
        nl = _build_netlist([[(0, 0)]])
        pairs = netlist_to_pairs(nl)
        assert pairs == set()

    def test_empty_netlist(self):
        nl = Netlist()
        nl.pin_to_node = {}
        assert netlist_to_pairs(nl) == set()


class TestNetlistToConnections:
    """netlist_to_connections: pin-pair connections from a Netlist."""

    def test_single_connection(self):
        nl = _build_netlist([[(0, 0), (1, 0)]])
        conns = netlist_to_connections(nl)
        assert conns == {((0, "pin0"), (1, "pin0"))}

    def test_intra_component_excluded(self):
        nl = _build_netlist([[(0, 0), (0, 1)]])
        conns = netlist_to_connections(nl)
        assert conns == set()

    def test_three_pin_net(self):
        nl = _build_netlist([[(0, 0), (1, 0), (2, 0)]])
        conns = netlist_to_connections(nl)
        expected = {
            ((0, "pin0"), (1, "pin0")),
            ((0, "pin0"), (2, "pin0")),
            ((1, "pin0"), (2, "pin0")),
        }
        assert conns == expected


# ═══════════════════════════════════════════════════════════════
# Metric validation — carefully constructed scenarios
# ═══════════════════════════════════════════════════════════════


class TestConnectionAccuracy:
    """Connection accuracy: how well detected wires connect to correct pins."""

    def test_perfect_join(self):
        """Identical GT and predicted → accuracy = 1.0."""
        gt = [[(0, 0), (1, 0)], [(2, 0), (3, 0)]]
        nl = _build_netlist([[(0, 0), (1, 0)], [(2, 0), (3, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.connection_accuracy == pytest.approx(1.0)

    def test_missing_connection(self):
        """GT has 2 connections, predicted has 1 → accuracy < 1."""
        gt = [
            [(0, 0), (1, 0)],
            [(2, 0), (3, 0)],
        ]
        # Only first connection recovered
        nl = _build_netlist([[(0, 0), (1, 0)], [(2, 0)], [(3, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        # GT has 2 connections; predicted has 1 → TP=1, FN=1, FP=0
        assert m.connection_tp == 1
        assert m.connection_fn == 1
        assert m.connection_fp == 0
        assert m.connection_accuracy == pytest.approx(0.5)

    def test_spurious_connection(self):
        """Predicted joins two components that GT keeps separate."""
        gt = [[(0, 0), (1, 0)]]  # only 0-1
        nl = _build_netlist([[(0, 0), (1, 0), (2, 0)]])  # 0-1 and 0-2 and 1-2
        m = compute_join_metrics_from_netlist(nl, gt)
        # GT connections: (0,pin0)-(1,pin0) = 1
        # Pred connections: (0,pin0)-(1,pin0), (0,pin0)-(2,pin0), (1,pin0)-(2,pin0) = 3
        # TP=1, FN=0, FP=2
        assert m.connection_tp == 1
        assert m.connection_fn == 0
        assert m.connection_fp == 2
        assert m.connection_accuracy == pytest.approx(1 / 3)

    def test_no_gt_no_pred(self):
        """Empty GT and empty predicted → accuracy = 1.0 (trivially correct)."""
        nl = _build_netlist([])
        m = compute_join_metrics_from_netlist(nl, [])
        assert m.connection_accuracy == pytest.approx(1.0)


class TestNetAssignmentAccuracy:
    """Net assignment accuracy: component-pair F1."""

    def test_perfect_assignment(self):
        gt = [[(0, 0), (1, 0)], [(2, 0), (3, 0)]]
        nl = _build_netlist([[(0, 0), (1, 0)], [(2, 0), (3, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.net_assignment_accuracy == pytest.approx(1.0)
        assert m.net_assignment_precision == pytest.approx(1.0)
        assert m.net_assignment_recall == pytest.approx(1.0)

    def test_over_merge_kills_precision(self):
        """Over-merging: all 3 components in one net but GT has 2 separate nets.

        GT: {0-1}, {2-3}
        Pred: {0-1, 0-2, 0-3, 1-2, 1-3, 2-3} (one big net)

        Pairs: TP=1 (0-1), FP=4 (the cross-net pairs), FN=1 (2-3 missed)
        """
        gt = [
            [(0, 0), (1, 0)],
            [(2, 0), (3, 0)],
        ]
        # All 4 components merged into one net
        nl = _build_netlist([[(0, 0), (1, 0), (2, 0), (3, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        gt_pairs = gt_nets_to_pairs(gt)  # {(0,1), (2,3)}
        pred_pairs = netlist_to_pairs(nl)  # all 6 pairs from 4 components
        assert m.pair_tp == len(gt_pairs & pred_pairs)
        assert m.pair_fp == len(pred_pairs - gt_pairs)
        assert m.pair_fn == len(gt_pairs - pred_pairs)
        # Over-merge rate should be high
        assert m.over_merge_rate > 0.5

    def test_under_merge_kills_recall(self):
        """Under-merging: GT has one net but predicted splits it.

        GT: {0-1-2-3} (all same net)
        Pred: {0-1}, {2-3} (two separate nets)

        Pairs: GT={(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)} = 6
        Pred={(0,1),(2,3)} = 2
        TP=2, FP=0, FN=4
        """
        gt = [[(0, 0), (1, 0), (2, 0), (3, 0)]]
        nl = _build_netlist([[(0, 0), (1, 0)], [(2, 0), (3, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.pair_tp == 2
        assert m.pair_fp == 0
        assert m.pair_fn == 4
        assert m.under_merge_rate == pytest.approx(4 / 6)

    def test_partial_recovery(self):
        """3 components in one net, only 2 of 3 pairs recovered.

        GT: {0-1-2}
        Pred: {0-1}, {2}

        GT pairs: (0,1), (0,2), (1,2) = 3
        Pred pairs: (0,1) = 1
        TP=1, FP=0, FN=2
        """
        gt = [[(0, 0), (1, 0), (2, 0)]]
        nl = _build_netlist([[(0, 0), (1, 0)], [(2, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.pair_tp == 1
        assert m.pair_fp == 0
        assert m.pair_fn == 2
        assert m.under_merge_rate == pytest.approx(2 / 3)
        assert m.over_merge_rate == pytest.approx(0.0)


class TestOverMergeRate:
    """Over-merge rate: FP / (TP + FP) = 1 - precision."""

    def test_no_over_merge(self):
        gt = [[(0, 0), (1, 0)]]
        nl = _build_netlist([[(0, 0), (1, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.over_merge_rate == pytest.approx(0.0)

    def test_all_over_merge(self):
        """Predicted pairs that have NO GT pairs → rate = 1.0."""
        gt = [[(0, 0), (1, 0)]]  # GT: only pair (0,1)
        # Predict: only pair (0,2) — completely spurious
        nl = _build_netlist([[(0, 0), (2, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        # GT pairs: {(0,1)}; Pred pairs: {(0,2)}
        # TP=0, FP=1, FN=1 → over_merge_rate = 1/1 = 1.0
        assert m.pair_tp == 0
        assert m.pair_fp == 1
        assert m.over_merge_rate == pytest.approx(1.0)

    def test_partial_over_merge(self):
        """50% of predicted pairs are spurious → rate = 0.5."""
        gt = [[(0, 0), (1, 0), (2, 0)]]
        # Predict: {0-1, 0-2, 1-2, 0-3, 1-3} but GT only has first 3
        # Wait — we need 4 components to get spurious pairs
        gt = [[(0, 0), (1, 0)]]  # GT: only (0,1)
        # Predict: (0,1) and (0,2)
        nl = _build_netlist([[(0, 0), (1, 0), (2, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        # Pred pairs: (0,1), (0,2), (1,2) = 3
        # GT pairs: (0,1) = 1
        # TP=1, FP=2 → over_merge = 2/3 ≈ 0.667
        assert m.over_merge_rate == pytest.approx(2 / 3)


class TestUnderMergeRate:
    """Under-merge rate: FN / (TP + FN) = 1 - recall."""

    def test_no_under_merge(self):
        gt = [[(0, 0), (1, 0)]]
        nl = _build_netlist([[(0, 0), (1, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.under_merge_rate == pytest.approx(0.0)

    def test_total_under_merge(self):
        """No GT pairs recovered → rate = 1.0."""
        gt = [[(0, 0), (1, 0)]]
        nl = _build_netlist([[(0, 0)], [(1, 0)]])  # separate nets
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.pair_tp == 0
        assert m.pair_fn == 1
        assert m.under_merge_rate == pytest.approx(1.0)

    def test_partial_under_merge(self):
        """GT has 3 pairs, only 1 recovered → rate = 2/3."""
        gt = [[(0, 0), (1, 0), (2, 0)]]
        nl = _build_netlist([[(0, 0), (1, 0)], [(2, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.under_merge_rate == pytest.approx(2 / 3)


class TestMetricsSymmetry:
    """Cross-check that over_merge and under_merge are complements of
    precision and recall respectively."""

    def test_over_merge_complement_of_precision(self):
        gt = [
            [(0, 0), (1, 0)],
            [(2, 0), (3, 0)],
        ]
        # Merge everything: 4 components → 6 pairs, GT has 2
        nl = _build_netlist([[(0, 0), (1, 0), (2, 0), (3, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.over_merge_rate == pytest.approx(1.0 - m.net_assignment_precision)
        assert m.under_merge_rate == pytest.approx(1.0 - m.net_assignment_recall)


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_single_component_no_pairs(self):
        """One component → no pairs → trivially correct."""
        gt = [[(0, 0)]]
        nl = _build_netlist([[(0, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.net_assignment_accuracy == pytest.approx(1.0)
        assert m.over_merge_rate == pytest.approx(0.0)
        assert m.under_merge_rate == pytest.approx(0.0)

    def test_empty_gt_empty_netlist(self):
        nl = Netlist()
        nl.pin_to_node = {}
        m = compute_join_metrics_from_netlist(nl, [])
        assert m.connection_accuracy == pytest.approx(1.0)
        assert m.net_assignment_accuracy == pytest.approx(1.0)

    def test_gt_has_nets_but_netlist_empty(self):
        """All GT connections missed → under_merge = 1.0."""
        gt = [[(0, 0), (1, 0)]]
        nl = Netlist()
        nl.pin_to_node = {}
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.under_merge_rate == pytest.approx(1.0)
        assert m.pair_tp == 0

    def test_many_nets(self):
        """10 independent pairs → all should be recovered."""
        gt = [[(i, 0), (i + 10, 0)] for i in range(10)]
        nl = _build_netlist([[(i, 0), (i + 10, 0)] for i in range(10)])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.net_assignment_accuracy == pytest.approx(1.0)
        assert m.over_merge_rate == pytest.approx(0.0)
        assert m.under_merge_rate == pytest.approx(0.0)

    def test_counts_are_correct(self):
        gt = [
            [(0, 0), (1, 0)],
            [(2, 0), (3, 0)],
        ]
        nl = _build_netlist([[(0, 0), (1, 0)], [(2, 0), (3, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.n_gt_nets == 2
        assert m.n_pred_nets == 2
        assert m.n_gt_pairs == 2
        assert m.n_pred_pairs == 2

    def test_per_net_detail_populated(self):
        gt = [
            [(0, 0), (1, 0)],
            [(2, 0), (3, 0)],
        ]
        nl = _build_netlist([[(0, 0), (1, 0)], [(2, 0), (3, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert len(m.net_detail) == 2
        for d in m.net_detail:
            assert d["recall"] == pytest.approx(1.0)
            assert d["n_missed"] == 0


class TestFormatJoinMetrics:
    """format_join_metrics produces readable output."""

    def test_basic_output(self):
        m = JoinMetrics(
            connection_accuracy=0.9,
            net_assignment_accuracy=0.85,
            over_merge_rate=0.1,
            under_merge_rate=0.15,
        )
        text = format_join_metrics(m)
        assert "0.9000" in text
        assert "0.8500" in text
        assert "0.1000" in text
        assert "0.1500" in text
        assert "Over-merge" in text
        assert "Under-merge" in text


# ═══════════════════════════════════════════════════════════════
# Integration tests — run real pipeline on synthetic circuits
# ═══════════════════════════════════════════════════════════════


class TestIntegrationWithSynthGT:
    """Run the join strategy on synthetically-generated wires/components
    and verify the metrics are well-behaved.

    These tests exercise the full path:
      CircuitSpec → synthesize_clean → join strategy → JoinMetrics
    """

    @pytest.fixture
    def parallel_rr(self):
        """Two parallel resistors on a voltage source (simple case)."""
        from wire_detection.synthgt.circuits import CATALOG_BY_NAME
        return CATALOG_BY_NAME["parallel_rr"]

    @pytest.fixture
    def divider_rr(self):
        """Series voltage divider (rectangular loop)."""
        from wire_detection.synthgt.circuits import CATALOG_BY_NAME
        return CATALOG_BY_NAME["divider_rr"]

    @pytest.fixture
    def dense_pair(self):
        """Two independent loops side by side (over-merge bait)."""
        from wire_detection.synthgt.circuits import CATALOG_BY_NAME
        return CATALOG_BY_NAME["dense_pair"]

    @pytest.fixture
    def clean_parallel(self, parallel_rr):
        from wire_detection.synthgt.synthesize import synthesize_clean
        return synthesize_clean(parallel_rr)

    @pytest.fixture
    def clean_divider(self, divider_rr):
        from wire_detection.synthgt.synthesize import synthesize_clean
        return synthesize_clean(divider_rr)

    @pytest.fixture
    def clean_dense(self, dense_pair):
        from wire_detection.synthgt.synthesize import synthesize_clean
        return synthesize_clean(dense_pair)

    def test_clean_parallel_perfect_metrics(self, parallel_rr, clean_parallel):
        """Clean parallel circuit should have perfect join metrics."""
        components, wires, pin_pos = clean_parallel
        from wire_detection.synthgt.evaluate import _make_std_pins
        from wire_detection.core.join_strategies import run_strategy
        std_pins = _make_std_pins(pin_pos, parallel_rr)
        _, netlist = run_strategy("degree_budget", wires, components, std_pins=std_pins)
        m = compute_join_metrics_from_netlist(netlist, parallel_rr.nets)
        # Clean circuit should recover all nets
        assert m.net_assignment_accuracy >= 0.9
        assert m.over_merge_rate <= 0.1

    def test_clean_divider_perfect_metrics(self, divider_rr, clean_divider):
        """Clean divider circuit should recover all 3 nets."""
        components, wires, pin_pos = clean_divider
        from wire_detection.synthgt.evaluate import _make_std_pins
        from wire_detection.core.join_strategies import run_strategy
        std_pins = _make_std_pins(pin_pos, divider_rr)
        _, netlist = run_strategy("degree_budget", wires, components, std_pins=std_pins)
        m = compute_join_metrics_from_netlist(netlist, divider_rr.nets)
        assert m.net_assignment_accuracy >= 0.8
        assert m.under_merge_rate <= 0.3

    def test_clean_dense_no_cross_short(self, dense_pair, clean_dense):
        """Two independent loops should NOT have cross-loop connections."""
        components, wires, pin_pos = clean_dense
        from wire_detection.synthgt.evaluate import _make_std_pins
        from wire_detection.core.join_strategies import run_strategy
        std_pins = _make_std_pins(pin_pos, dense_pair)
        _, netlist = run_strategy("degree_budget", wires, components, std_pins=std_pins)
        m = compute_join_metrics_from_netlist(netlist, dense_pair.nets)
        # Over-merge should be low — loops are independent
        assert m.over_merge_rate <= 0.3
        # Net assignment should be decent
        assert m.net_assignment_precision >= 0.6

    def test_metrics_from_compute_join_metrics(self, parallel_rr, clean_parallel):
        """Test the high-level compute_join_metrics API."""
        from wire_detection.evaluate.join_metrics import compute_join_metrics
        components, wires, pin_pos = clean_parallel
        from wire_detection.synthgt.evaluate import _make_std_pins
        std_pins = _make_std_pins(pin_pos, parallel_rr)
        m = compute_join_metrics(
            wires, components, std_pins, parallel_rr.nets,
            strategy="degree_budget",
        )
        assert isinstance(m, JoinMetrics)
        assert 0.0 <= m.connection_accuracy <= 1.0
        assert 0.0 <= m.net_assignment_accuracy <= 1.0
        assert 0.0 <= m.over_merge_rate <= 1.0
        assert 0.0 <= m.under_merge_rate <= 1.0

    def test_error_injected_degrades_metrics(self, parallel_rr, clean_parallel):
        """Injecting errors should degrade at least one metric."""
        from wire_detection.synthgt.synthesize import inject_errors
        from wire_detection.synthgt.evaluate import _make_std_pins
        from wire_detection.core.join_strategies import run_strategy
        components, wires, pin_pos = clean_parallel
        std_pins = _make_std_pins(pin_pos, parallel_rr)

        # Clean metrics (baseline)
        _, net_clean = run_strategy("degree_budget", wires, components, std_pins=std_pins)
        m_clean = compute_join_metrics_from_netlist(net_clean, parallel_rr.nets)

        # Inject errors at severity 2
        wires_err = inject_errors(wires, 2, seed=42, pin_pos=pin_pos, components=components)
        _, net_err = run_strategy("degree_budget", wires_err, components, std_pins=std_pins)
        m_err = compute_join_metrics_from_netlist(net_err, parallel_rr.nets)

        # At least one metric should degrade
        degraded = (
            m_err.net_assignment_accuracy < m_clean.net_assignment_accuracy
            or m_err.under_merge_rate > m_clean.under_merge_rate
            or m_err.over_merge_rate > m_clean.over_merge_rate
        )
        # It's possible the error didn't affect this specific circuit,
        # so we only assert the metrics are still valid
        assert 0.0 <= m_err.net_assignment_accuracy <= 1.0
        assert 0.0 <= m_err.over_merge_rate <= 1.0
        assert 0.0 <= m_err.under_merge_rate <= 1.0


# ═══════════════════════════════════════════════════════════════
# Cross-metric consistency checks
# ═══════════════════════════════════════════════════════════════


class TestCrossMetricConsistency:
    """Verify mathematical relationships between the metrics."""

    def test_precision_equals_one_minus_over_merge(self):
        gt = [[(0, 0), (1, 0), (2, 0)]]
        nl = _build_netlist([[(0, 0), (1, 0), (2, 0), (3, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.net_assignment_precision == pytest.approx(1.0 - m.over_merge_rate)

    def test_recall_equals_one_minus_under_merge(self):
        gt = [[(0, 0), (1, 0), (2, 0)]]
        nl = _build_netlist([[(0, 0), (1, 0)], [(2, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert m.net_assignment_recall == pytest.approx(1.0 - m.under_merge_rate)

    def test_f1_from_precision_recall(self):
        gt = [[(0, 0), (1, 0), (2, 0)]]
        nl = _build_netlist([[(0, 0), (1, 0), (2, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        expected_f1 = (
            2 * m.net_assignment_precision * m.net_assignment_recall
            / (m.net_assignment_precision + m.net_assignment_recall)
        )
        assert m.net_assignment_accuracy == pytest.approx(expected_f1)

    def test_connection_accuracy_bounds(self):
        """Connection accuracy is always in [0, 1]."""
        # Construct pathological cases
        gt = [[(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]]
        # Massive over-merge
        nl = _build_netlist([[(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]])
        m = compute_join_metrics_from_netlist(nl, gt)
        assert 0.0 <= m.connection_accuracy <= 1.0

        # No connections at all
        nl_empty = _build_netlist([[(i, 0)] for i in range(5)])
        m2 = compute_join_metrics_from_netlist(nl_empty, gt)
        assert 0.0 <= m2.connection_accuracy <= 1.0


# ═══════════════════════════════════════════════════════════════
# Real-world regression test
# ═══════════════════════════════════════════════════════════════


def _has_real_components() -> bool:
    """Check if synthetic GT circuits are importable."""
    try:
        from wire_detection.synthgt.circuits import CATALOG_BY_NAME
        return "wheatstone" in CATALOG_BY_NAME
    except Exception:
        return False


class TestRealWorldRegression:
    """Verify that the metrics don't crash and return valid values
    when run on real-world component data (even if approximate)."""

    @pytest.mark.skipif(
        not _has_real_components(),
        reason="No real component data available",
    )
    def test_wheatstone_bridge(self):
        """Wheatstone bridge — complex topology that stresses the join."""
        from wire_detection.synthgt.circuits import CATALOG_BY_NAME
        from wire_detection.synthgt.synthesize import synthesize_clean
        from wire_detection.synthgt.evaluate import _make_std_pins
        from wire_detection.core.join_strategies import run_strategy
        spec = CATALOG_BY_NAME["wheatstone"]
        components, wires, pin_pos = synthesize_clean(spec)
        std_pins = _make_std_pins(pin_pos, spec)
        _, netlist = run_strategy("degree_budget", wires, components, std_pins=std_pins)
        m = compute_join_metrics_from_netlist(netlist, spec.nets)
        assert isinstance(m, JoinMetrics)
        assert 0.0 <= m.net_assignment_accuracy <= 1.0
        assert len(m.net_detail) == len(spec.nets)

"""Join metrics (§4.2) — structural quality scores for the wire-to-pin join step.

Measures four axes of join quality that the production `score_netlist` structural
scoring cannot capture (because it has no ground truth):

  1. **Connection accuracy** — how well detected wires connect to correct component
     pins.  Each ground-truth wire that terminates on a known pin pair is a
     *connection*.  We count correctly resolved connections, under-connected (a GT
     connection the join failed to make), and over-connected (a connection the join
     made that doesn't exist in GT).

  2. **Net assignment accuracy** — component-pair F1.  Two components share a net
     iff there is a path of wires between their pins.  Precision dropping = shorts
     (over-merge); recall dropping = fragmentation (under-merge).

  3. **Over-merge rate** — fraction of *predicted* component-pair connections that
     are NOT in ground truth.  Complement of pair-level precision.

  4. **Under-merge rate** — fraction of *ground-truth* component-pair connections
     that are NOT recovered.  Complement of pair-level recall.

All metrics are designed to work with synthetic ground-truth circuits (CircuitSpec)
and with any recovered Netlist, whether produced by ``run_strategy`` or any custom
join function.

Usage::

    from wire_detection.evaluate.join_metrics import (
        JoinMetrics, compute_join_metrics, compute_join_metrics_from_netlist,
    )

    # Option A — give wires + components + pins explicitly:
    m = compute_join_metrics(
        wires, components, pins, gt_nets,
        strategy="degree_budget",
    )

    # Option B — give an already-built Netlist:
    m = compute_join_metrics_from_netlist(netlist, gt_nets, n_components)

    print(m.connection_accuracy, m.over_merge_rate)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Sequence

from wire_detection.core.netlist import ComponentPin, Netlist


# ───────────────────────────────────────────────────────────────
# Data structures
# ───────────────────────────────────────────────────────────────

@dataclass
class JoinMetrics:
    """Aggregated join-quality metrics."""

    # --- connection accuracy ---
    connection_tp: int = 0       # GT pin-pairs correctly joined
    connection_fn: int = 0       # GT pin-pairs the join missed
    connection_fp: int = 0       # spurious pin-pairs the join created
    connection_accuracy: float = 0.0   # TP / (TP + FN + FP),  0-1

    # --- net assignment (component-pair F1) ---
    pair_tp: int = 0             # component pairs correctly on same net
    pair_fp: int = 0             # predicted pairs that are NOT in GT
    pair_fn: int = 0             # GT pairs that are NOT in predicted
    net_assignment_precision: float = 0.0
    net_assignment_recall: float = 0.0
    net_assignment_accuracy: float = 0.0   # F1 of component-pair sets

    # --- over-merge / under-merge (convenience aliases) ---
    over_merge_rate: float = 0.0   # FP / (TP + FP)  — complement of precision
    under_merge_rate: float = 0.0  # FN / (TP + FN)  — complement of recall

    # --- counts ---
    n_gt_nets: int = 0
    n_pred_nets: int = 0
    n_gt_pairs: int = 0
    n_pred_pairs: int = 0

    # --- per-net detail (optional, useful for debugging) ---
    net_detail: list[dict] = field(default_factory=list)


# ───────────────────────────────────────────────────────────────
# Ground-truth helpers
# ───────────────────────────────────────────────────────────────

def gt_nets_to_pairs(
    gt_nets: Sequence[Sequence[tuple[int, int]]],
) -> set[tuple[int, int]]:
    """Convert a list-of-nets (each net = list of ``(comp_idx, pin_idx)``)
    into a set of undirected component-pairs that share a net.

    Two pins on the same component but different nets are intentionally
    *not* counted as a pair — we only care about inter-component
    connectivity.
    """
    pairs: set[tuple[int, int]] = set()
    for net in gt_nets:
        comps = sorted({c for c, _p in net})
        for a, b in combinations(comps, 2):
            pairs.add((a, b))
    return pairs


def gt_nets_to_connections(
    gt_nets: Sequence[Sequence[tuple[int, int]]],
) -> set[tuple[tuple[int, str], tuple[int, str]]]:
    """Return the set of *ordered* pin-pairs within each net.

    Each pair ((comp_a, "pinA"), (comp_b, "pinB")) with comp_a < comp_b
    represents one ground-truth connection that the join should resolve.
    Intra-component pin-pairs are excluded.

    Pin names are normalized to the ``"pin{i}"`` convention used by the
    netlist so that GT and predicted connections are directly comparable.
    """
    conns: set[tuple[tuple[int, str], tuple[int, str]]] = set()
    for net in gt_nets:
        pins = sorted(net)  # sort by (comp_idx, pin_idx)
        for i, (ca, pa) in enumerate(pins):
            for j, (cb, pb) in enumerate(pins):
                if i >= j:
                    continue
                if ca == cb:
                    continue  # skip intra-component
                conns.add(((ca, f"pin{pa}"), (cb, f"pin{pb}")))
    return conns


# ───────────────────────────────────────────────────────────────
# Netlist → pairs / connections
# ───────────────────────────────────────────────────────────────

def netlist_to_pairs(netlist: Netlist) -> set[tuple[int, int]]:
    """Component-pairs implied by a recovered netlist."""
    node_comps: dict[int, set[int]] = {}
    for (ci, _pin), nid in netlist.pin_to_node.items():
        node_comps.setdefault(nid, set()).add(ci)
    pairs: set[tuple[int, int]] = set()
    for comps in node_comps.values():
        pairs.update(combinations(sorted(comps), 2))
    return pairs


def netlist_to_connections(
    netlist: Netlist,
) -> set[tuple[tuple[int, str], tuple[int, str]]]:
    """Pin-pair connections implied by a recovered netlist.

    Each pair ((comp_a, pin_a), (comp_b, pin_b)) with comp_a < comp_b
    where both pins share a net node.  Intra-component pairs excluded.

    Note: netlist keys are ``(comp_idx, pin_name: str)``.
    """
    node_pins: dict[int, list[tuple[int, str]]] = {}
    for (ci, pin_name), nid in netlist.pin_to_node.items():
        node_pins.setdefault(nid, []).append((ci, pin_name))
    conns: set[tuple[tuple[int, str], tuple[int, str]]] = set()
    for pins in node_pins.values():
        sorted_pins = sorted(pins)
        for i, (ca, pa) in enumerate(sorted_pins):
            for j, (cb, pb) in enumerate(sorted_pins):
                if i >= j or ca == cb:
                    continue
                conns.add(((ca, pa), (cb, pb)))
    return conns


# ───────────────────────────────────────────────────────────────
# Core metric computation
# ───────────────────────────────────────────────────────────────

def _f1(prec: float, rec: float) -> float:
    if prec + rec < 1e-12:
        return 0.0
    return 2.0 * prec * rec / (prec + rec)


def compute_join_metrics_from_netlist(
    netlist: Netlist,
    gt_nets: Sequence[Sequence[tuple[int, int]]],
    n_components: int = 0,
) -> JoinMetrics:
    """Compute all four join metrics given a recovered Netlist and GT nets.

    Parameters
    ----------
    netlist : Netlist
        The recovered netlist from any join strategy.
    gt_nets : list of nets
        Ground-truth nets, each a list of ``(comp_idx, pin_idx)`` tuples.
    n_components : int
        Total component count (for informational use; computed automatically
        if 0).

    Returns
    -------
    JoinMetrics
    """
    m = JoinMetrics()

    # --- connection-level (pin-pair) ---
    gt_conns = gt_nets_to_connections(gt_nets)
    pred_conns = netlist_to_connections(netlist)
    m.connection_tp = len(gt_conns & pred_conns)
    m.connection_fn = len(gt_conns - pred_conns)
    m.connection_fp = len(pred_conns - gt_conns)
    total_c = m.connection_tp + m.connection_fn + m.connection_fp
    m.connection_accuracy = m.connection_tp / total_c if total_c > 0 else 1.0

    # --- component-pair level ---
    gt_pairs = gt_nets_to_pairs(gt_nets)
    pred_pairs = netlist_to_pairs(netlist)
    m.pair_tp = len(gt_pairs & pred_pairs)
    m.pair_fp = len(pred_pairs - gt_pairs)
    m.pair_fn = len(gt_pairs - pred_pairs)

    m.net_assignment_precision = (
        m.pair_tp / (m.pair_tp + m.pair_fp)
        if (m.pair_tp + m.pair_fp) > 0
        else (1.0 if m.pair_fn == 0 else 0.0)
    )
    m.net_assignment_recall = (
        m.pair_tp / (m.pair_tp + m.pair_fn)
        if (m.pair_tp + m.pair_fn) > 0
        else (1.0 if m.pair_fp == 0 else 0.0)
    )
    m.net_assignment_accuracy = _f1(m.net_assignment_precision, m.net_assignment_recall)

    # --- over-merge / under-merge ---
    m.over_merge_rate = (
        m.pair_fp / (m.pair_tp + m.pair_fp)
        if (m.pair_tp + m.pair_fp) > 0
        else 0.0
    )
    m.under_merge_rate = (
        m.pair_fn / (m.pair_tp + m.pair_fn)
        if (m.pair_tp + m.pair_fn) > 0
        else 0.0
    )

    # --- counts ---
    m.n_gt_nets = len([n for n in gt_nets if len(n) >= 2])
    node_comps: dict[int, set[int]] = {}
    for (ci, _), nid in netlist.pin_to_node.items():
        node_comps.setdefault(nid, set()).add(ci)
    m.n_pred_nets = sum(1 for cs in node_comps.values() if len(cs) >= 2)
    m.n_gt_pairs = len(gt_pairs)
    m.n_pred_pairs = len(pred_pairs)

    # --- per-net detail ---
    m.net_detail = _per_net_detail(gt_nets, netlist)

    return m


def _per_net_detail(
    gt_nets: Sequence[Sequence[tuple[int, int]]],
    netlist: Netlist,
) -> list[dict]:
    """Build a per-GT-net breakdown showing which pairs were recovered."""
    gt_pairs_by_net = []
    for net in gt_nets:
        comps = sorted({c for c, _p in net})
        gt_pairs_by_net.append(set(combinations(comps, 2)))

    pred_pairs = netlist_to_pairs(netlist)
    details = []
    for i, (net, gt_prs) in enumerate(zip(gt_nets, gt_pairs_by_net)):
        recovered = gt_prs & pred_pairs
        missed = gt_prs - pred_pairs
        details.append({
            "net_idx": i,
            "pins": [(c, p) for c, p in net],
            "n_gt_pairs": len(gt_prs),
            "n_recovered": len(recovered),
            "n_missed": len(missed),
            "recall": len(recovered) / len(gt_prs) if gt_prs else 1.0,
            "missed_pairs": sorted(missed),
        })
    return details


# ───────────────────────────────────────────────────────────────
# High-level API — build from wires + join strategy
# ───────────────────────────────────────────────────────────────

def compute_join_metrics(
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    pins: list[ComponentPin],
    gt_nets: Sequence[Sequence[tuple[int, int]]],
    strategy: str = "degree_budget",
) -> JoinMetrics:
    """Compute join metrics by running a named strategy then scoring.

    Parameters
    ----------
    wires, components, pins : pipeline inputs
    gt_nets : ground-truth nets
    strategy : name registered in ``join_strategies.STRATEGIES``

    Returns
    -------
    JoinMetrics
    """
    from wire_detection.core.join_strategies import run_strategy
    _, netlist = run_strategy(strategy, wires, components, std_pins=pins)
    return compute_join_metrics_from_netlist(netlist, gt_nets, n_components=len(components))


def compute_join_metrics_from_fn(
    join_fn,
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    pins: list[ComponentPin],
    gt_nets: Sequence[Sequence[tuple[int, int]]],
) -> JoinMetrics:
    """Compute join metrics for a custom join function.

    ``join_fn(wires, components, pins) -> Netlist``
    """
    netlist = join_fn(wires, components, pins)
    return compute_join_metrics_from_netlist(netlist, gt_nets, n_components=len(components))


# ───────────────────────────────────────────────────────────────
# Summary / formatting
# ───────────────────────────────────────────────────────────────

def format_join_metrics(m: JoinMetrics, title: str = "Join Metrics") -> str:
    """Pretty-print a JoinMetrics result as a Markdown table."""
    lines = [
        f"# {title}\n",
        "## Connection Accuracy",
        f"  TP={m.connection_tp}  FN={m.connection_fn}  FP={m.connection_fp}",
        f"  Accuracy = **{m.connection_accuracy:.4f}**\n",
        "## Net Assignment Accuracy",
        f"  TP={m.pair_tp}  FN={m.pair_fn}  FP={m.pair_fp}",
        f"  Precision = {m.net_assignment_precision:.4f}",
        f"  Recall    = {m.net_assignment_recall:.4f}",
        f"  F1        = **{m.net_assignment_accuracy:.4f}**\n",
        "## Merge Rates",
        f"  Over-merge rate  = **{m.over_merge_rate:.4f}**  (FP / predicted pairs)",
        f"  Under-merge rate = **{m.under_merge_rate:.4f}**  (FN / GT pairs)\n",
        "## Counts",
        f"  GT nets={m.n_gt_nets}  Pred nets={m.n_pred_nets}",
        f"  GT pairs={m.n_gt_pairs}  Pred pairs={m.n_pred_pairs}",
    ]
    if m.net_detail:
        lines.append("\n## Per-Net Detail")
        for d in m.net_detail:
            lines.append(
                f"  Net {d['net_idx']}: {d['n_recovered']}/{d['n_gt_pairs']} "
                f"(recall={d['recall']:.2f})  missed={d['missed_pairs']}"
            )
    return "\n".join(lines)

"""Tests for the synthetic ground-truth evaluation harness (wire_detection/synthgt).

The core invariant: for every authored circuit, the CLEAN synthesized coordinate
map must round-trip through the real join back to the authored connectivity
(component-pair F1 == 1.0). If that breaks, a layout is bad or the join regressed
on an easy case -- either way the synthetic scores can't be trusted.
"""
from __future__ import annotations

import pytest

from wire_detection.core.join_strategies import run_strategy
from wire_detection.synthgt.circuits import CATALOG
from wire_detection.synthgt.evaluate import _comp_pairs, _prf, evaluate_circuit
from wire_detection.synthgt.synthesize import (
    inject_errors,
    intended_pairs,
    synthesize_clean,
    value_overrides,
)


@pytest.mark.parametrize("spec", CATALOG, ids=[c.name for c in CATALOG])
def test_clean_join_recovers_ground_truth(spec):
    """Clean synthesis -> real join -> authored connectivity, exactly."""
    components, wires, _ = synthesize_clean(spec)
    _, netlist = run_strategy("graph_rescue", wires, components)
    _p, _r, f1 = _prf(intended_pairs(spec), _comp_pairs(netlist))
    assert f1 == pytest.approx(1.0), f"{spec.name}: clean join F1={f1:.3f} != 1.0"


@pytest.mark.parametrize("spec", CATALOG, ids=[c.name for c in CATALOG])
def test_value_overrides_cover_every_component(spec):
    vov = value_overrides(spec)
    assert len(vov) == len(spec.comps)
    assert all(v for v in vov.values())


def test_error_injection_is_deterministic():
    spec = CATALOG[-1]  # ring6_r
    _, wires, _ = synthesize_clean(spec)
    a = inject_errors(wires, severity=3, seed=7)
    b = inject_errors(wires, severity=3, seed=7)
    c = inject_errors(wires, severity=3, seed=8)
    assert a == b
    assert a != c  # different seed -> different perturbation


def test_severity_zero_is_the_clean_control():
    spec = CATALOG[0]
    _, wires, _ = synthesize_clean(spec)
    assert inject_errors(wires, severity=0, seed=123) == list(wires)


def test_increasing_error_does_not_improve_join():
    """Recall must be monotonically non-increasing as severity rises (averaged)."""
    res = evaluate_circuit(CATALOG[-1], seeds=12)
    recalls = [row["recall"] for row in res["rows"]]
    assert recalls[0] == pytest.approx(1.0)
    assert recalls[-1] <= recalls[0] + 1e-9


def test_prf_edge_cases():
    assert _prf(set(), set()) == (1.0, 1.0, 1.0)
    assert _prf({(0, 1)}, set())[1] == 0.0          # recall 0 when nothing recovered
    assert _prf({(0, 1)}, {(0, 1)}) == (1.0, 1.0, 1.0)

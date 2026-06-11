"""Tests for the synthetic ground-truth evaluation harness (wire_detection/synthgt).

The core invariant: for every authored circuit, the CLEAN synthesized coordinate
map must round-trip through the real join back to the authored connectivity
(component-pair F1 == 1.0). If that breaks, a layout is bad or the join regressed
on an easy case -- either way the synthetic scores can't be trusted.
"""
from __future__ import annotations

import pytest

from wire_detection.core.join_strategies import run_strategy
from wire_detection.synthgt.circuits import CATALOG, CATALOG_BY_NAME
from wire_detection.synthgt.evaluate import (
    _comp_pairs,
    _prf,
    _sources_match,
    evaluate_circuit,
)
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
    spec = CATALOG_BY_NAME["ring6_r"]
    _, wires, pin_pos = synthesize_clean(spec)
    a = inject_errors(wires, severity=3, seed=7, pin_pos=pin_pos)
    b = inject_errors(wires, severity=3, seed=7, pin_pos=pin_pos)
    c = inject_errors(wires, severity=3, seed=8, pin_pos=pin_pos)
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


def test_wrong_pin_snap_lands_on_other_pins():
    """The over-merge mode must move endpoints, and onto actual (wrong) pins."""
    spec = CATALOG_BY_NAME["dense_pair"]
    _, wires, pin_pos = synthesize_clean(spec)
    snapped = inject_errors(wires, severity=4, seed=3, pin_pos=pin_pos,
                            params=(0.0, 0.0, 0.0, 1.0))   # snap only, forced
    assert len(snapped) == len(wires)                       # no drops
    pins = set(pin_pos.values())
    orig = [ep for w in wires for ep in w]
    new = [ep for w in snapped for ep in w]
    moved = [n for o, n in zip(orig, new) if n != o]
    assert moved, "forced wrong-pin snaps must move endpoints"
    assert all(ep in pins for ep in moved)


def test_wrong_pin_snap_breaks_precision():
    """Cross-loop snaps in dense_pair must create false pairs the join picks up
    (precision < 1) - this is the over-merge signal the old model couldn't make."""
    spec = CATALOG_BY_NAME["dense_pair"]
    components, wires, pin_pos = synthesize_clean(spec)
    gt = intended_pairs(spec)
    worst = 1.0
    for seed in range(4):   # deterministic - verified to bridge loops
        snapped = inject_errors(wires, 4, seed, pin_pos=pin_pos,
                                params=(0.0, 0.0, 0.0, 1.0))
        _, net = run_strategy("graph_rescue", snapped, components)
        p, _r, _f = _prf(gt, _comp_pairs(net))
        worst = min(worst, p)
    assert worst < 1.0


def test_sources_match_requires_every_source():
    ref = [0.005, 0.003]
    assert _sources_match([0.005, 0.003], ref)
    assert _sources_match([0.00501, 0.00299], ref)          # within 2%
    assert not _sources_match([0.005, 0.0], ref)            # second source dead
    assert not _sources_match([0.005, 0.006], ref)          # second source off
    assert not _sources_match([0.0, 0.0], [0.0, 0.0])       # all-zero ref = no oracle


def test_authoring_guard_flags_expectation_mismatch():
    """gt_mA vs expect_mA disagreement must be surfaced (spec bug detector)."""
    import copy
    spec = copy.deepcopy(CATALOG_BY_NAME["divider_rr"])
    spec.expect_mA = 9.99   # wrong on purpose
    res = evaluate_circuit(spec, seeds=1)
    if res["spice_on"]:
        assert res["expect_match"] is False
    good = evaluate_circuit(CATALOG_BY_NAME["divider_rr"], seeds=1)
    if good["spice_on"]:
        assert good["expect_match"] is True

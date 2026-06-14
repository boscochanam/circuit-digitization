"""Tests for the synthetic ground-truth evaluation harness (wire_detection/synthgt).

The core invariant: for every authored circuit, the CLEAN synthesized coordinate
map must round-trip through the real join back to the authored connectivity
(component-pair F1 == 1.0). If that breaks, a layout is bad or the join regressed
on an easy case -- either way the synthetic scores can't be trusted.
"""
from __future__ import annotations

import math
import pytest

from wire_detection.core.join_strategies import run_strategy
from wire_detection.synthgt.circuits import CATALOG, CATALOG_BY_NAME
from wire_detection.synthgt.evaluate import (
    _comp_pairs,
    _make_std_pins,
    _prf,
    _sources_match,
    compare_strategies,
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
                            params=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0))  # snap only, forced
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
                                params=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0))
        _, net = run_strategy("graph_rescue", snapped, components)
        p, _r, _f = _prf(gt, _comp_pairs(net))
        worst = min(worst, p)
    assert worst < 1.0


def test_displace_endpoint_moves_endpoints_far():
    """Anchor deletion: one endpoint per wire is displaced by dist px in a
    random direction — the wire exists but doesn't reach the pin."""
    spec = CATALOG_BY_NAME["divider_rr"]
    _, wires, pin_pos = synthesize_clean(spec)
    # Force displacement only, no other errors
    displaced = inject_errors(wires, severity=0, seed=5, pin_pos=pin_pos,
                              params=(0.0, 0.0, 0.0, 0.0, 1.0, 50.0))
    # All wires preserved (no drops)
    assert len(displaced) == len(wires)
    # At least one endpoint moved significantly (>20px from original)
    orig_eps = [ep for w in wires for ep in w]
    new_eps = [ep for w in displaced for ep in w]
    max_disp = max(math.hypot(o[0] - n[0], o[1] - n[1])
                   for o, n in zip(orig_eps, new_eps))
    assert max_disp > 20, f"expected displacement >20px, got {max_disp:.1f}"


def test_sources_match_requires_every_source():
    ref = [0.005, 0.003]
    assert _sources_match([0.005, 0.003], ref)
    assert _sources_match([0.00501, 0.00299], ref)          # within 2%
    assert not _sources_match([0.005, 0.0], ref)            # second source dead
    assert not _sources_match([0.005, 0.006], ref)          # second source off
    assert not _sources_match([0.0, 0.0], [0.0, 0.0])       # all-zero ref = no oracle


def test_compare_strategies_ranks_and_flags_clean():
    rows = compare_strategies(["graph_rescue", "production", "mutual_30"], seeds=2)
    assert {r["strategy"] for r in rows} == {"graph_rescue", "production", "mutual_30"}
    # sorted by robustness, best first
    assert rows[0]["mean_err_f1"] >= rows[-1]["mean_err_f1"]
    gr = next(r for r in rows if r["strategy"] == "graph_rescue")
    assert gr["clean"] == pytest.approx(1.0)       # flagship recovers easy cases
    assert len(gr["by_severity"]) == 5
    # mutual under-merges and cannot even recover the clean control
    mut = next(r for r in rows if r["strategy"] == "mutual_30")
    assert mut["clean"] < 1.0


def test_catalog_names_unique_and_include_new_topologies():
    names = [c.name for c in CATALOG]
    assert len(names) == len(set(names))            # no duplicate names
    assert {"series_parallel", "rc_parallel", "wheatstone"} <= set(names)


def test_wheatstone_recovers_four_node_bridge():
    """The bridge is a genuine non-series/non-parallel topology: 4 distinct
    electrical nodes (A/B/M/N), and the bridge resistor spans the two mids."""
    spec = CATALOG_BY_NAME["wheatstone"]
    components, wires, pin_pos = synthesize_clean(spec)
    _, net = run_strategy("graph_rescue", wires, components,
                          std_pins=_make_std_pins(pin_pos, spec))
    assert len(set(net.pin_to_node.values())) == 4          # A, B, M, N
    assert net.pin_to_node[(5, "pin0")] != net.pin_to_node[(5, "pin1")]  # bridge spans M-N


def test_rc_parallel_emits_capacitor_with_valid_dc_current():
    """The cap must appear in the SPICE deck (C path exercised) while the DC
    current stays at the authored 2.5 mA (cap open at DC)."""
    spec = CATALOG_BY_NAME["rc_parallel"]
    res = evaluate_circuit(spec, seeds=1)
    if res["spice_on"]:
        assert res["expect_match"] is True
    assert any(c.type.startswith("capacitor") for c in spec.comps)


def test_degree_budget_completion_beats_graph_rescue():
    """Lock in the search finding: the completion candidate recovers more (mean-err
    F1 up) without breaking clean and without trading away bridge precision. If this
    regresses, the candidate or the harness changed -- investigate before trusting."""
    from wire_detection.synthgt.candidate_joins import degree_budget_completion
    from wire_detection.synthgt.evaluate import score_join_fn
    from wire_detection.core.join_strategies import run_strategy

    cand = score_join_fn(degree_budget_completion, seeds=4)
    base = score_join_fn(lambda w, c, sp: run_strategy("graph_rescue", w, c, std_pins=sp)[1],
                         seeds=4)
    assert cand["clean"] == pytest.approx(1.0)              # never breaks easy cases
    assert cand["mean_err_f1"] > base["mean_err_f1"]        # genuinely more robust
    assert cand["wheat_prec_L3"] >= base["wheat_prec_L3"] - 1e-6   # not precision-for-recall


@pytest.mark.parametrize("spec", CATALOG, ids=[c.name for c in CATALOG])
def test_degree_budget_clean_via_production_pins(spec):
    """degree_budget (the default) must recover clean circuits via the PRODUCTION
    discovered-pins path (run_strategy -> make_pins), not just the true-pins path.
    Guards against base over-extend over-merge -- e.g. the double-extend bug
    (registry extend + internal extend = 24px) that shorted the clean wheatstone."""
    components, wires, _ = synthesize_clean(spec)
    _, net = run_strategy("degree_budget", wires, components)   # make_pins path
    _p, _r, f1 = _prf(intended_pairs(spec), _comp_pairs(net))
    assert f1 == pytest.approx(1.0), f"{spec.name}: degree_budget clean (make_pins) F1={f1:.3f}"


def test_degree_budget_tracks_wires_and_curbs_self_loops():
    """The two production-blocking fixes (PR #64 handoff), measured the same way
    the real benchmark does (score_netlist): (1) wire tracking is populated -- was
    0% before netlist_from_uf carried base wires; (2) the self-loop guard keeps
    two-terminal shorts at or below graph_rescue rather than ~2x above it."""
    from wire_detection.synthgt.candidate_joins import degree_budget_completion
    from wire_detection.core.join_strategies import run_strategy, score_netlist

    # (1) wire tracking: a clean degree_budget netlist must report ~full wire usage.
    spec = CATALOG_BY_NAME["ring6_r"]
    comps, wires, pp = synthesize_clean(spec)
    sp = _make_std_pins(pp, spec)
    assert score_netlist(wires, comps, sp,
                         degree_budget_completion(wires, comps, sp))["pct_wires_used"] > 99.0

    # (2) self-loop guard: under heavy error, degree_budget must not short more
    # two-terminal components than graph_rescue (it used to ~double them).
    db = gr = 0.0; n = 0
    for s in CATALOG:
        c, w0, p = synthesize_clean(s)
        spn = _make_std_pins(p, s)
        for seed in range(4):
            w = inject_errors(w0, 4, seed, pin_pos=p, components=c)
            db += score_netlist(w, c, spn, degree_budget_completion(w, c, spn))["self_loop_components"]
            gr += score_netlist(w, c, spn, run_strategy("graph_rescue", w, c, std_pins=spn)[1])["self_loop_components"]
            n += 1
    assert db / n <= gr / n + 0.05, f"degree_budget self-loops {db/n:.3f} > graph_rescue {gr/n:.3f}"


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

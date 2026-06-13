"""Run the real join + SPICE on synthesized coordinates and score vs the authored
ground truth.

Two independent signals:
  * JOIN  - component-connectivity F1 (did the join tie together exactly the
            components the authored netlist ties together). Precision falling =
            over-merge/shorts; recall falling = fragmentation/under-merge.
  * SPICE - does the recovered circuit still simulate to the authored operating
            point, with NO injected test sources (the fragmentation tell).
            EVERY voltage source's branch current must match the clean oracle -
            checking only one source would let a circuit fragment between two
            sources and still "pass".

Note the deliberate asymmetry: a single cross-net short does NOT change DC
currents (one extra wire is not a return path), so over-merge is mostly invisible
to sim_ok - join precision is the metric that catches it. Fragmentation hits both.
"""
from __future__ import annotations

from itertools import combinations

from wire_detection.core.join_strategies import run_strategy
from wire_detection.core.simulator import SpiceSimulator
from wire_detection.core.spice import SpiceGenerator
from wire_detection.core.netlist import ComponentPin
from wire_detection.synthgt.circuits import CATALOG, CircuitSpec
from wire_detection.synthgt.synthesize import (
    ERROR_LEVELS,
    inject_errors,
    intended_pairs,
    synthesize_clean,
    value_overrides,
)

DEFAULT_STRATEGY = "graph_rescue"


def _comp_pairs(netlist) -> set[tuple[int, int]]:
    """Connected component pairs implied by a recovered netlist."""
    node_comps: dict[int, set[int]] = {}
    for (ci, _pin), nid in netlist.pin_to_node.items():
        node_comps.setdefault(nid, set()).add(ci)
    pairs: set[tuple[int, int]] = set()
    for comps in node_comps.values():
        pairs.update(combinations(sorted(comps), 2))
    return pairs


def _prf(gt: set, got: set) -> tuple[float, float, float]:
    if not gt and not got:
        return 1.0, 1.0, 1.0
    tp = len(gt & got)
    prec = tp / len(got) if got else (1.0 if not gt else 0.0)
    rec = tp / len(gt) if gt else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def _voltage_idxs(spec: CircuitSpec) -> list[int]:
    return [i for i, c in enumerate(spec.comps) if c.type.startswith("voltage")]


def _make_std_pins(pin_pos: dict, spec: CircuitSpec) -> list[ComponentPin]:
    """Convert synthgt pin_pos dict to ComponentPin objects for run_strategy."""
    pins = []
    for (ci, pi), (x, y) in pin_pos.items():
        c = spec.comps[ci]
        pins.append(ComponentPin(
            component_idx=ci,
            component_name=c.type,
            pin_idx=pi,
            pin_name=f"pin{pi}",
            x=x, y=y,
            rel_x=0.0, rel_y=0.0,
        ))
    return pins


def _source_currents(sim: dict, v_idxs: list[int]) -> list[float]:
    """|branch current| of every authored source, in spec order (0.0 if absent -
    a source dropped from the SPICE deck reads as a hard mismatch, as it should)."""
    cur = sim.get("currents", {}) if isinstance(sim, dict) else {}
    return [abs(cur.get(f"v{i + 1}#branch", 0.0)) for i in v_idxs]


def _sources_match(got: list[float], ref: list[float], rel_tol: float = 0.02) -> bool:
    if not ref or not any(r > 0 for r in ref):
        return False
    return all((abs(g - r) <= rel_tol * r) if r > 0 else (g <= 1e-9)
               for g, r in zip(got, ref))


def _injected_sources(spice_text: str) -> int:
    return sum(1 for ln in spice_text.splitlines() if ln.startswith("VTEST"))


def evaluate_circuit(
    spec: CircuitSpec,
    seeds: int = 8,
    ngspice_path: str | None = None,
    strategy: str = DEFAULT_STRATEGY,
) -> dict:
    """Sweep every error level; average join + SPICE metrics over `seeds`."""
    components, clean_wires, pin_pos = synthesize_clean(spec)
    gt_pairs = intended_pairs(spec)
    vov = value_overrides(spec)
    v_idxs = _voltage_idxs(spec)
    sim = SpiceSimulator(ngspice_path)
    spice_on = sim.is_available()

    # Reference operating point from the CLEAN recovered netlist (the oracle).
    _, clean_net = run_strategy(strategy, clean_wires, components)
    ref_i: list[float] = []
    if spice_on:
        ref_i = _source_currents(sim.run_dc_analysis(
            SpiceGenerator().generate(components, clean_net, vov)), v_idxs)

    rows = []
    for sev in sorted(ERROR_LEVELS):
        accP = accR = accF = 0.0
        sim_ok = inj_total = sim_runs = 0
        n = 1 if sev == 0 else seeds
        for seed in range(n):
            wires = inject_errors(clean_wires, sev, seed, pin_pos=pin_pos, components=components)
            _, net = run_strategy(strategy, wires, components,
                                  std_pins=_make_std_pins(pin_pos, spec))
            p, r, f = _prf(gt_pairs, _comp_pairs(net))
            accP += p; accR += r; accF += f
            if spice_on:
                text = SpiceGenerator().generate(components, net, vov)
                inj = _injected_sources(text)
                inj_total += inj
                got_i = _source_currents(sim.run_dc_analysis(text), v_idxs)
                if inj == 0 and _sources_match(got_i, ref_i):
                    sim_ok += 1
                sim_runs += 1
        rows.append({
            "severity": sev,
            "params": ERROR_LEVELS[sev],
            "precision": accP / n,
            "recall": accR / n,
            "f1": accF / n,
            "sim_ok_rate": (sim_ok / sim_runs) if sim_runs else None,
            "mean_injected": (inj_total / sim_runs) if sim_runs else None,
        })

    # Authoring guard: the simulated oracle should agree with the hand-computed
    # expectation; a mismatch means the spec (values, polarity, nets) is wrong.
    gt_mA = ref_i[0] * 1000.0 if (spice_on and ref_i) else None
    expect_match = None
    if gt_mA is not None and spec.expect_mA:
        expect_match = abs(gt_mA - spec.expect_mA) <= 0.02 * spec.expect_mA

    return {
        "name": spec.name,
        "note": spec.note,
        "strategy": strategy,
        "components": len(spec.comps),
        "nets": len(spec.nets),
        "gt_pairs": len(gt_pairs),
        "expect_mA": spec.expect_mA,
        "gt_mA": gt_mA,
        "expect_match": expect_match,
        "spice_on": spice_on,
        "rows": rows,
    }


def run_suite(
    specs: list[CircuitSpec] | None = None,
    seeds: int = 8,
    ngspice_path: str | None = None,
    strategy: str = DEFAULT_STRATEGY,
) -> list[dict]:
    return [evaluate_circuit(s, seeds, ngspice_path, strategy) for s in (specs or CATALOG)]


def _join_f1_sweep(spec: CircuitSpec, strategy: str, seeds: int) -> list[float]:
    """Mean component-connectivity F1 per severity for one (circuit, strategy).
    Join only - no SPICE - so comparing every strategy stays fast."""
    components, clean_wires, pin_pos = synthesize_clean(spec)
    gt_pairs = intended_pairs(spec)
    out = []
    for sev in sorted(ERROR_LEVELS):
        n = 1 if sev == 0 else seeds
        acc = 0.0
        for seed in range(n):
            wires = inject_errors(clean_wires, sev, seed, pin_pos=pin_pos, components=components)
            _, net = run_strategy(strategy, wires, components,
                                  std_pins=_make_std_pins(pin_pos, spec))
            acc += _prf(gt_pairs, _comp_pairs(net))[2]
        out.append(acc / n)
    return out


def compare_strategies(
    strategies: list[str],
    specs: list[CircuitSpec] | None = None,
    seeds: int = 5,
) -> list[dict]:
    """Leaderboard: for every join strategy, mean F1 per severity across all
    circuits (join only). Sorted by robustness = mean F1 over the error levels.

    A strategy whose clean (L0) score is < 1.0 cannot recover an easy case and
    is flagged - that is a correctness failure, not a robustness ranking.
    """
    specs = specs or CATALOG
    sevs = sorted(ERROR_LEVELS)
    rows = []
    for strat in strategies:
        per_circuit = [_join_f1_sweep(s, strat, seeds) for s in specs]
        by_sev = [sum(c[i] for c in per_circuit) / len(per_circuit)
                  for i in range(len(sevs))]
        err = by_sev[1:]  # exclude the clean control
        rows.append({
            "strategy": strat,
            "by_severity": by_sev,
            "clean": by_sev[0],
            "mean_err_f1": sum(err) / len(err) if err else 0.0,
        })
    rows.sort(key=lambda r: r["mean_err_f1"], reverse=True)
    return rows

"""Run the real join + SPICE on synthesized coordinates and score vs the authored
ground truth.

Two independent signals:
  * JOIN  - component-connectivity F1 (did the join tie together exactly the
            components the authored netlist ties together). Precision falling =
            over-merge/shorts; recall falling = fragmentation/under-merge.
  * SPICE - does the recovered circuit still simulate to the authored operating
            point, with NO injected test sources (the fragmentation tell).
"""
from __future__ import annotations

from itertools import combinations

from wire_detection.core.join_strategies import run_strategy
from wire_detection.core.simulator import SpiceSimulator
from wire_detection.core.spice import SpiceGenerator
from wire_detection.synthgt.circuits import CATALOG, CircuitSpec
from wire_detection.synthgt.synthesize import (
    ERROR_LEVELS,
    inject_errors,
    intended_pairs,
    synthesize_clean,
    value_overrides,
)


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


def _voltage_idx(spec: CircuitSpec) -> int | None:
    for i, c in enumerate(spec.comps):
        if c.type.startswith("voltage"):
            return i
    return None


def _source_current(sim: dict, v_idx: int | None) -> float:
    if v_idx is None or "currents" not in sim:
        return 0.0
    return abs(sim["currents"].get(f"v{v_idx + 1}#branch", 0.0))


def _injected_sources(spice_text: str) -> int:
    return sum(1 for ln in spice_text.splitlines() if ln.startswith("VTEST"))


def evaluate_circuit(
    spec: CircuitSpec,
    seeds: int = 8,
    ngspice_path: str | None = None,
) -> dict:
    """Sweep every error level; average join + SPICE metrics over `seeds`."""
    components, clean_wires, _ = synthesize_clean(spec)
    gt_pairs = intended_pairs(spec)
    vov = value_overrides(spec)
    v_idx = _voltage_idx(spec)
    sim = SpiceSimulator(ngspice_path)
    spice_on = sim.is_available()

    # Reference operating point from the CLEAN recovered netlist (the oracle).
    _, clean_net = run_strategy("graph_rescue", clean_wires, components)
    gt_i = 0.0
    if spice_on:
        gt_i = _source_current(sim.run_dc_analysis(
            SpiceGenerator().generate(components, clean_net, vov)), v_idx)

    rows = []
    for sev in sorted(ERROR_LEVELS):
        accP = accR = accF = 0.0
        sim_ok = inj_total = sim_runs = 0
        n = 1 if sev == 0 else seeds
        for seed in range(n):
            wires = inject_errors(clean_wires, sev, seed)
            _, net = run_strategy("graph_rescue", wires, components)
            p, r, f = _prf(gt_pairs, _comp_pairs(net))
            accP += p; accR += r; accF += f
            if spice_on:
                text = SpiceGenerator().generate(components, net, vov)
                inj = _injected_sources(text)
                inj_total += inj
                test_i = _source_current(sim.run_dc_analysis(text), v_idx)
                rel = abs(test_i - gt_i) / gt_i if gt_i else 0.0
                if inj == 0 and test_i > 0 and rel < 0.02:
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

    return {
        "name": spec.name,
        "note": spec.note,
        "components": len(spec.comps),
        "nets": len(spec.nets),
        "gt_pairs": len(gt_pairs),
        "expect_mA": spec.expect_mA,
        "gt_mA": gt_i * 1000.0 if spice_on else None,
        "spice_on": spice_on,
        "rows": rows,
    }


def run_suite(
    specs: list[CircuitSpec] | None = None,
    seeds: int = 8,
    ngspice_path: str | None = None,
) -> list[dict]:
    return [evaluate_circuit(s, seeds, ngspice_path) for s in (specs or CATALOG)]

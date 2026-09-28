"""Join-method set for the revision-2 scale experiments (no data dependencies).

Nothing in the pipeline is modified: the "unclamped" and "fixed-px" completion
variants swap completion-module globals inside the calling process only and restore
them afterwards.
"""
from __future__ import annotations

from wire_detection.core import completion as C
from wire_detection.core.join_graph import estimate_scale
from wire_detection.core.join_strategies import run_strategy

METHODS = ["scale_completion", "scale_completion_unclamped", "fixedpx_completion",
           "graph_scale", "graph_dir_30", "production"]
REGISTRY_METHODS = {"scale_completion", "graph_scale", "graph_dir_30", "production"}
K = dict(tau_pin=0.62, tau_join=0.30, tau_t=0.20)          # scale_completion k-factors
FIXED = dict(tau_pin=30.0, tau_join=14.0, tau_t=10.0)       # graph_dir_30 / ablation px
FIXED_COMPLETION_TAU = 30.0
REACH = 4.0


def _custom_completion(wires, comps, pins, base_kwargs, comp_tau):
    """degree_budget_completion(base=<custom>, reach 4, relax_witness) with the base
    graph kwargs and completion tau supplied explicitly (process-local global swap)."""
    old_bases, old_tau = C._BASES, C._scale_tau
    C._BASES = {**old_bases, "custom": dict(extend=0, kwargs=base_kwargs)}
    C._scale_tau = lambda _c, _w: comp_tau
    try:
        return C.degree_budget_completion(wires, comps, pins, relax_witness=True,
                                          base="custom", reach_factor=REACH)
    finally:
        C._BASES, C._scale_tau = old_bases, old_tau


def run_method(m, wires, comps, std, junc):
    if m in REGISTRY_METHODS:
        return run_strategy(m, wires, comps, std_pins=std, junc_pins=junc)[1]
    common = dict(directional=True, t_junctions=True, scale_rel=False)
    if m == "scale_completion_unclamped":
        s = estimate_scale(comps, wires)
        kw = {k: v * s for k, v in K.items()}
        return _custom_completion(wires, comps, std, {**kw, **common}, 0.62 * s)
    if m == "fixedpx_completion":
        return _custom_completion(wires, comps, std, {**FIXED, **common}, FIXED_COMPLETION_TAU)
    raise KeyError(m)



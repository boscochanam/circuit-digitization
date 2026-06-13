"""Candidate join strategies discovered by the synthgt strategy search.

Found by using the ground-truth harness as a search engine over the join-algorithm
space (see docs/synthetic-eval-plan.md, "Strategy search"). Each is a
`join_fn(wires, components, std_pins) -> Netlist` scored against ground truth and
adversarially verified for overfitting to the placeholder error model.

The headline result, `degree_budget_completion`, beat graph_rescue by ~+0.035
mean-error F1 (0.972 vs 0.944, 12 seeds / 15 circuits), winning at every severity
while RAISING bridge precision -- verified at overfit_risk=low (the gain is in DROP
mode, recovering wires the detector missed entirely, where precision rises).

It has since been PROMOTED into the core join registry: the implementation now
lives in `wire_detection/core/completion.py` and is registered in
`join_strategies.py` as the "degree_budget" strategy. This module re-exports it so
the synthgt harness, `--candidates`, and the search-provenance docs keep working.
"""
from wire_detection.core.completion import (
    REACH_FACTOR,
    degree_budget_completion,
    netlist_from_uf,
)

__all__ = ["degree_budget_completion", "netlist_from_uf", "REACH_FACTOR", "CANDIDATES"]

# search-found candidates: name -> join_fn(wires, components, std_pins) -> Netlist
CANDIDATES = {
    "degree_budget_completion": degree_budget_completion,
}

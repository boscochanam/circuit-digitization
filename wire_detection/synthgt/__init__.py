"""Synthetic ground-truth evaluation for the join + SPICE pipeline.

The detector leaves hand-drawn circuits fragmented, and there is no net-level
ground truth to score the join against (see issue #20). This package takes the
*other* direction: start from a known-good circuit (a netlist we author), lay it
out as a coordinate map the way the detector's output looks, optionally inject
detector-style error, then run the **real** join + SPICE and score the result
against the netlist we started with.

That gives, at scale and for free:
  * net-level ground truth for the join (component-connectivity F1), and
  * a SPICE oracle (the authored circuit's operating point) to check the sim.

IMPORTANT - read `docs/synthetic-eval-plan.md`. The value of the *join* numbers
hinges entirely on the fidelity of the error model in `synthesize.py`, which is a
first-pass PLACEHOLDER and is NOT yet calibrated to the real detector's failure
distribution. Treat synthetic join scores as a regression/robustness signal, not
as a predictor of real-image performance, until the error model is calibrated.
The SPICE/sim half is sound on its own (we control the netlist).
"""
from wire_detection.synthgt.circuits import CATALOG, CircuitSpec, Comp
from wire_detection.synthgt.evaluate import evaluate_circuit, run_suite

__all__ = ["CATALOG", "CircuitSpec", "Comp", "evaluate_circuit", "run_suite"]

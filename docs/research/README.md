# Research & Experiments

This directory contains experiment logs, synthesis documents, and analysis related to the wire detection and netlist extraction research.

## Benchmark Results

- **[expanded-benchmark.md](expanded-benchmark.md)** — Full benchmark of 36 configs on 134 images. `best_candidate_v4` wins at F1=0.8334.

## Joining & Netlist

- **[join-verification.md](join-verification.md)** — Joining strategy evaluation, endpoint-graph join model, verification tooling. The `graph_rescue` strategy beats production on 53/58 images.
- **[netlist-exploration.md](netlist-exploration.md)** — Synthesis of all netlist extraction approaches. Endpoint clustering recommended for SPICE netlist construction.

## Wire Detection

- **[connectivity.md](connectivity.md)** — Wire-to-component connectivity methods (99.3% reachability) and why connectivity filtering fails for FP removal.
- **[mapping-experiment.md](mapping-experiment.md)** — Wire-to-component mapping methods (25+ approaches tested, selective disambiguation wins).

## Data Quality

- **[vlm-experiments.md](vlm-experiments.md)** — Nemotron VLM classification of circuit images by paper type.

## Implementation

- **[iteration-tracker.md](iteration-tracker.md)** — Lead priority queue, completed leads, dead ends for FP removal. All leads exhausted; accepting F1=0.8334.
- **[tdd-plan.md](tdd-plan.md)** — 6-week TDD implementation plan for backend/frontend restructuring.

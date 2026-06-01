# Wire-to-Component Connectivity

## Problem

Given detected wire endpoints and component bounding boxes (from YOLO-OBB labels), determine which components each wire connects to. This is the bridge between wire detection and netlist extraction for SPICE simulation.

## Methods

| Method | Description | Reachability | Both-Connected | Discard Rate |
|--------|-------------|-------------|----------------|-------------|
| **nearest_edge** | Project endpoint to closest bbox edge point | **99.3%** | **98.7%** | **0.1%** |
| radial_search | Find bboxes within radius R | 98.8% | 98.0% | 0.4% |
| nearest_center | Closest component center within radius | 98.8% | 97.8% | 0.3% |
| ray_cast | Extend along wire axis until hitting bbox | 96.9% | 95.8% | 2.1% |
| axis_sweep | Extend H/V only (Manhattan routing) | 96.3% | 93.2% | 0.6% |

**Winner:** `nearest_edge` with 50px threshold.

### Metrics explained
- **Reachability**: % of wire endpoints that connect to *any* component
- **Both-Connected**: % of wires where *both* endpoints reach a component
- **Discard Rate**: % of wires where *neither* endpoint connects (noise)

## Limitation

Reachability metrics measure whether an endpoint lands near *any* component, not whether it connects to the *correct* component. Agreement with pseudo-GT (GT wire endpoints + nearest_edge) is used as a proxy for correctness.

## Pseudo-GT Evaluation

1. Take GT wire endpoints
2. Run `nearest_edge` to get "ground truth" component connections
3. For each detected wire matched to a GT wire, check if it connects to the same components
4. Measure agreement rate

## Files

- `wire_detection/benchmark/connectivity_experiment.py` — Method comparison harness
- `wire_detection/benchmark/pseudo_gt_eval.py` — Pseudo-GT agreement evaluation
- `output/connectivity_experiment/` — Results and visualizations

## Future Work

- Manual labeling of wire→component connections (~20 images)
- Structural validation (netlist consistency checks)
- Circuit semantics (known circuit topology matching)
- SPICE netlist generation from connected graph

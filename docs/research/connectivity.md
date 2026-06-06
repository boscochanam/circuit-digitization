# Wire-to-Component Connectivity

## TL;DR

Wire-to-component connectivity works well for **netlist construction** (99.3% reachability) but **cannot filter FP wires** — 88% of "orphan" wires are true positives. Use connectivity for mapping, not quality filtering.

---

## Part 1: Connectivity Methods

### Problem

Given detected wire endpoints and component bounding boxes (from YOLO-OBB labels), determine which components each wire connects to. This is the bridge between wire detection and netlist extraction for SPICE simulation.

### Methods Compared

| Method | Description | Reachability | Both-Connected | Discard Rate |
|--------|-------------|-------------|----------------|-------------|
| **nearest_edge** | Project endpoint to closest bbox edge point | **99.3%** | **98.7%** | **0.1%** |
| radial_search | Find bboxes within radius R | 98.8% | 98.0% | 0.4% |
| nearest_center | Closest component center within radius | 98.8% | 97.8% | 0.3% |
| ray_cast | Extend along wire axis until hitting bbox | 96.9% | 95.8% | 2.1% |
| axis_sweep | Extend H/V only (Manhattan routing) | 96.3% | 93.2% | 0.6% |

**Winner:** `nearest_edge` with 50px threshold.

### Metrics Explained

- **Reachability**: % of wire endpoints that connect to *any* component
- **Both-Connected**: % of wires where *both* endpoints reach a component
- **Discard Rate**: % of wires where *neither* endpoint connects (noise)

### Limitation

Reachability metrics measure whether an endpoint lands near *any* component, not whether it connects to the *correct* component. Agreement with pseudo-GT (GT wire endpoints + nearest_edge) is used as a proxy for correctness.

### Pseudo-GT Evaluation

1. Take GT wire endpoints
2. Run `nearest_edge` to get "ground truth" component connections
3. For each detected wire matched to a GT wire, check if it connects to the same components
4. Measure agreement rate

### Files

- `wire_detection/benchmark/connectivity_experiment.py` — Method comparison harness
- `wire_detection/benchmark/pseudo_gt_eval.py` — Pseudo-GT agreement evaluation
- `output/connectivity_experiment/` — Results and visualizations

---

## Part 2: Connectivity Filtering (Dead End)

**Connectivity-based filtering cannot improve F1 beyond the baseline (0.8334).** Every tested configuration makes F1 worse. The fundamental issue: 88% of "orphan" wires are true positives, and there's no connectivity-based signal that reliably distinguishes TP wires from FP wires.

### RCA Summary (634 removed wires)

| Category | Count | TP | FP | TP% | Verdict |
|----------|------:|----:|----:|-----:|---------|
| sparse_area | 306 | 273 | 33 | 89.2% | DANGEROUS |
| junction_nearby | 248 | 220 | 28 | 88.7% | DANGEROUS |
| terminal_nearby | 50 | 40 | 10 | 80.0% | RISKY |
| small_bbox | 17 | 13 | 4 | 76.5% | RISKY |
| bbox_mismatch | 7 | 5 | 2 | 71.4% | RISKY |
| distant_component | 6 | 6 | 0 | 100.0% | DANGEROUS |
| **TOTAL** | **634** | **557** | **77** | **87.9%** | — |

### Why It Fails

1. **Junction/Terminal Bbox Problem** — Junctions (302 hits) and terminals (120 hits) have tiny bboxes. Wire endpoints land *outside* these bboxes even when physically connected. 248 wires near junctions are classified as "orphans" — 88.7% are TPs.

2. **Sparse Area Wires** — 306 wires have no components within 100px. These are legitimate wires connecting distant parts of the circuit. 89.2% are TPs.

3. **No Discriminating Signal** — Both TP and FP wires can be far from components. Both TP and FP wires can be near junctions. Component connectivity alone cannot separate them.

### Experiments (18 configurations)

| Rank | Config | F1 | Δ vs Baseline |
|------|--------|---:|--------------:|
| 1 | baseline | 0.8334 | — |
| 2 | j20_d80 | 0.7896 | -0.044 |
| 3 | dist_100 | 0.7891 | -0.044 |
| ... | ... | ... | ... |
| 18 | cap_2 | 0.6793 | -0.154 |

**No configuration beats baseline.**

### Implications

Component connectivity is **not a reliable filter for wire quality**, but it IS useful for:

1. **Netlist construction:** Wire-to-component mapping for circuit simulation
2. **Component validation:** Components with 0 wires are likely FP detections
3. **Circuit topology:** Building the graph of component connections

### Files

- `wire_detection/benchmark/connectivity_rca.py` — RCA framework
- `wire_detection/benchmark/connectivity_filter_v2.py` — 18 experiment configurations
- `output/connectivity_rca/rca_summary.json` — per-wire RCA data
- `output/connectivity_filter_v2/results.json` — experiment results

---

## Recommendations

1. **Accept baseline F1=0.8334** — it's already good
2. **Focus on FN reduction** — find the 783 missed wires
3. **Use connectivity for netlist, not filtering** — map wires to components for SPICE
4. **Consider component-aware detection** — train wire detector to be aware of component locations during detection, not just post-filtering

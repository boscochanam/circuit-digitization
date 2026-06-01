# Connectivity Filter Experiments — Synthesis

## TL;DR

**Connectivity-based filtering cannot improve F1 beyond the baseline (0.8334).**

Every tested configuration makes F1 worse. The fundamental issue: 88% of "orphan" wires are true positives, and there's no connectivity-based signal that reliably distinguishes TP wires from FP wires.

---

## RCA Summary (634 removed wires)

| Category | Count | TP | FP | TP% | Verdict |
|----------|------:|----:|----:|-----:|---------|
| sparse_area | 306 | 273 | 33 | 89.2% | DANGEROUS |
| junction_nearby | 248 | 220 | 28 | 88.7% | DANGEROUS |
| terminal_nearby | 50 | 40 | 10 | 80.0% | RISKY |
| small_bbox | 17 | 13 | 4 | 76.5% | RISKY |
| bbox_mismatch | 7 | 5 | 2 | 71.4% | RISKY |
| distant_component | 6 | 6 | 0 | 100.0% | DANGEROUS |
| **TOTAL** | **634** | **557** | **77** | **87.9%** | — |

**Key finding:** 87.9% of wires removed by connectivity filtering are true positives.

---

## Root Causes

### 1. Junction/Terminal Bbox Problem
- Junctions (302 hits) and terminals (120 hits) have tiny bboxes
- Wire endpoints land *outside* these bboxes even when physically connected
- 248 wires near junctions are classified as "orphans" — 88.7% are TPs

### 2. Sparse Area Wires
- 306 wires have no components within 100px
- These are legitimate wires connecting distant parts of the circuit
- 89.2% are TPs

### 3. No Discriminating Signal
- Both TP and FP wires can be far from components
- Both TP and FP wires can be near junctions
- Component connectivity alone cannot distinguish wire quality

---

## Experiments Run (18 configurations)

| Rank | Config | F1 | Δ vs Baseline | Notes |
|------|--------|---:|--------------:|-------|
| 1 | baseline | 0.8334 | — | No filter |
| 2 | j20_d80 | 0.7896 | -0.044 | Junction +20, dist 80 |
| 3 | dist_100 | 0.7891 | -0.044 | Distance 100px |
| 4 | dist_80 | 0.7731 | -0.060 | Distance 80px |
| 5 | combo_j20_u10 | 0.7719 | -0.062 | Junction +20, universal +10 |
| ... | ... | ... | ... | ... |
| 18 | cap_2 | 0.6793 | -0.154 | Cap at 2 wires/component |

**No configuration beats baseline.**

---

## Why Connectivity Filtering Fails

The wire detection algorithm (best_candidate_v4) already achieves F1=0.8334. The remaining errors are:

1. **False Negatives (783 wires):** Wires the algorithm misses entirely
   - These can't be fixed by post-filtering
   
2. **False Positives (248 wires):** Wires the algorithm detects incorrectly
   - These are mixed in with 2741 true positives
   - Component connectivity doesn't separate them

3. **Redundant (65 wires):** Duplicate detections of the same wire
   - Already handled by dedup logic

The FP-to-TP ratio is 248:2741 (9%). Any filter that removes enough wires to catch FPs will inevitably remove far more TPs.

---

## Implications for Netlist Extraction

Component connectivity is **not a reliable filter for wire quality**, but it IS useful for:

1. **Netlist construction:** Wire-to-component mapping for circuit simulation
2. **Component validation:** Components with 0 wires are likely FP detections
3. **Circuit topology:** Building the graph of component connections

The 99.3% connection rate (from connectivity experiment) is valid for *reachability* — wires DO connect to components. The 6.1% agreement rate with pseudo-GT is a *precision* issue (connecting to the *wrong* component in dense areas), not a *recall* issue.

---

## Recommendations

1. **Accept baseline F1=0.8334** — it's already good
2. **Focus on FN reduction** — find the 783 missed wires
3. **Use connectivity for netlist, not filtering** — map wires to components for SPICE
4. **Consider component-aware detection** — train wire detector to be aware of component locations during detection, not just post-filtering

---

## Files

- `connectivity_rca.py` — RCA framework
- `connectivity_filter_v2.py` — 18 experiment configurations
- `output/connectivity_rca/rca_summary.json` — per-wire RCA data
- `output/connectivity_filter_v2/results.json` — experiment results

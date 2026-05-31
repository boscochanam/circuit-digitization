# Netlist Extraction Exploration — Complete Analysis

## Executive Summary

**No approach successfully filters FP wires without destroying TPs.** The fundamental problem: the wire detector (F1=0.8334) produces 10% FP wires, and there's no post-hoc signal that reliably separates them from the 90% TPs.

However, **pin-level connectivity** shows promise for netlist construction (not filtering), and **iterative refinement** may improve accuracy.

---

## Exploration Results

### 1. Pin-Level Connectivity

| Metric | Value |
|--------|------:|
| Total wires analyzed | 248 |
| Both endpoints near pin (≤30px) | 30 (12.1%) |
| One endpoint near pin | 44 (17.7%) |
| Neither endpoint near pin | 174 (70.2%) |
| Average distance to nearest pin | 84.0px |

**Finding:** Pin-level connectivity (29.8%) is much lower than bbox connectivity (99.3%).

**Root Cause:** Pin derivation from OBB is too simplistic. Pins are placed at fixed relative positions (e.g., 0.0, ±0.5), but real pin locations depend on:
- Component orientation (not just OBB center)
- Component-specific geometry (different pin layouts per type)
- Wire routing conventions (wires may connect to the body, not the pin)

**Lead:** If we can derive accurate pin locations, pin-level connectivity would give precise netlist connections.

**Dead End:** Static pin definitions don't work. Need dynamic pin inference.

---

### 2. Confidence Scoring

| Metric | Value |
|--------|------:|
| TP average confidence | 0.344 |
| FP average confidence | 0.344 |
| Confidence difference | 0.000 |

**Finding:** Confidence scoring shows NO difference between TP and FP wires.

**Root Cause:** The scoring features (length, pixel density, pin proximity) don't distinguish TP from FP because:
- Both TP and FP wires have similar lengths
- Both TP and FP wires have similar pixel densities
- Pin proximity is not a reliable signal (see above)

**Dead End:** Simple confidence scoring doesn't work. Need more sophisticated features.

---

### 3. Netlist Validation

| Metric | Value |
|--------|------:|
| Netlists built | 20 |
| Average nodes per image | 48.3 |
| Average isolated pins | 47.0 |
| Average large nodes (>5 pins) | 0.2 |

**Finding:** Most pins are isolated (47 out of 48.3 nodes).

**Root Cause:** Pin-level connectivity is too low (29.8%), so most pins don't get connected.

**Lead:** If we improve pin derivation, netlist quality will improve.

---

## Approaches Tested

### ❌ FAILED: Bbox Connectivity Filtering
- **Approach:** Remove wires where neither endpoint is within 50px of a component bbox
- **Result:** F1 drops from 0.8334 to 0.7731 (best case)
- **RCA:** 88% of "orphan" wires are TPs. Junctions/terminals have tiny bboxes.

### ❌ FAILED: Per-Component Cap
- **Approach:** Keep only the 2 closest wires per component
- **Result:** F1 drops from 0.8334 to 0.6793
- **RCA:** Real circuits have components with many connections. Cap removes TPs.

### ❌ FAILED: Require Both Endpoints
- **Approach:** Both wire endpoints must connect to a component
- **Result:** F1 drops from 0.8334 to 0.6824
- **RCA:** Many valid wires have one endpoint near a pin, one far away.

### ❌ FAILED: Confidence Scoring
- **Approach:** Score wires by length, pixel density, pin proximity
- **Result:** TP and FP have identical scores (0.344)
- **RCA:** Features don't distinguish TP from FP.

### ⚠️ PARTIAL: Pin-Level Connectivity
- **Approach:** Derive pins from OBB, connect wires to specific pins
- **Result:** 29.8% connectivity (vs 99.3% for bbox)
- **RCA:** Pin derivation is too simplistic. Need dynamic inference.

---

## Leads for Further Exploration

### Lead 1: Iterative Pin Refinement
**Hypothesis:** Use wire endpoints to infer pin locations, then re-evaluate connectivity.

**Approach:**
1. Start with bbox connectivity (99.3%)
2. For each component, cluster wire endpoints near the bbox
3. Use cluster centers as pin locations
4. Re-evaluate connectivity with refined pins

**Why it might work:** Wire endpoints ARE the connection points. Clustering them would give accurate pin locations.

**Risk:** Chicken-and-egg problem — need pins to connect wires, need wires to find pins.

---

### Lead 2: Wire Endpoint Clustering
**Hypothesis:** Group wire endpoints by proximity to form "connection zones."

**Approach:**
1. For each component, find all wire endpoints within 50px
2. Cluster endpoints by spatial proximity (e.g., DBSCAN)
3. Each cluster = a "pin" or "connection point"
4. Connect wires to the nearest cluster

**Why it might work:** This is data-driven — pin locations emerge from the wire detection itself.

**Risk:** Noisy endpoints may create spurious clusters.

---

### Lead 3: Component-Aware Wire Detection
**Hypothesis:** Train wire detector to be aware of component locations during detection.

**Approach:**
1. Modify wire detection to prefer lines that connect to components
2. Add component proximity as a feature in line scoring
3. Use component bboxes as "attractors" for wire endpoints

**Why it might work:** This addresses the root cause — the wire detector doesn't know about components.

**Risk:** Requires retraining or significant pipeline changes.

---

### Lead 4: Topology-Based Post-Hoc Validation
**Hypothesis:** Use circuit topology knowledge to identify and remove spurious connections.

**Approach:**
1. Build initial netlist with all detected wires
2. Check for impossible topologies:
   - Short circuits (voltage sources connected together)
   - Floating components (no connections)
   - Degree-1 nodes (dangling wires)
3. Remove wires that create impossible topologies

**Why it might work:** Circuit topology has constraints. Violations indicate FPs.

**Risk:** Requires domain knowledge about valid circuit topologies.

---

### Lead 5: Multi-Model Consensus
**Hypothesis:** Use multiple wire detection methods and keep only wires detected by all.

**Approach:**
1. Run best_candidate_v4 (F1=0.8334)
2. Run skeleton_graph_v1 (F1=0.8185)
3. Run adaptive thresholding (F1=0.755)
4. Keep only wires detected by ≥2 methods

**Why it might work:** FPs are likely to be inconsistent across methods.

**Risk:** May remove TPs that are only detected by one method.

---

## Dead Ends

### ❌ Bbox Proximity
Cannot use bbox proximity to filter wires. 88% of "orphans" are TPs.

### ❌ Per-Component Cap
Cannot limit wires per component. Real circuits have components with many connections.

### ❌ Require Both Endpoints
Cannot require both endpoints to connect. Many valid wires have one endpoint far from components.

### ❌ Simple Confidence Scoring
Cannot use simple features (length, pixel density, pin proximity) to score wires. TP and FP have identical scores.

### ❌ Static Pin Definitions
Cannot use fixed pin positions per component type. Real pin locations depend on orientation and geometry.

---

## Recommendations

### For Netlist Extraction (Not Filtering)

1. **Use Wire Endpoint Clustering (Lead 2)**
   - Don't try to derive pins from OBB
   - Use wire endpoints themselves to define connection points
   - Cluster endpoints near each component to form "pins"
   - This is data-driven and avoids the pin derivation problem

2. **Build Netlist with Soft Connections**
   - Don't hard-assign wires to pins
   - Use probabilistic connections (wire is 80% connected to pin A, 20% to pin B)
   - This handles ambiguity in dense areas

3. **Validate Topology (Lead 4)**
   - After building netlist, check for impossible configurations
   - Remove wires that create short circuits or floating components
   - This is post-hoc cleaning, not filtering

### For Wire Filtering (If Needed)

1. **Use Multi-Model Consensus (Lead 5)**
   - Run multiple detection methods
   - Keep only wires detected by ≥2 methods
   - This may remove FPs while keeping most TPs

2. **Train Component-Aware Detector (Lead 3)**
   - Modify wire detection to be aware of components
   - This addresses the root cause
   - Requires significant effort

### For SPICE Simulation

1. **Accept Imperfect Netlist**
   - F1=0.8334 means 10% of connections are wrong
   - For many circuits, this is acceptable
   - Manual review of suspicious connections

2. **Use Confidence Scores**
   - Even if TP/FP have same average, individual wires vary
   - Set threshold to remove low-confidence wires
   - Trade recall for precision

3. **Iterative Refinement**
   - Build initial netlist
   - Run SPICE simulation
   - Compare to expected behavior
   - Remove connections that cause unexpected behavior

---

## Next Steps

1. **Implement Wire Endpoint Clustering (Lead 2)**
   - Most promising for netlist construction
   - Data-driven, avoids pin derivation problem
   - Can be tested on existing data

2. **Test Multi-Model Consensus (Lead 5)**
   - Easy to implement
   - May improve precision at cost of recall
   - Worth testing as a baseline

3. **Explore Topology Validation (Lead 4)**
   - Requires domain knowledge
   - Can be implemented incrementally
   - Good for post-hoc cleaning

4. **Consider Component-Aware Detection (Lead 3)**
   - Long-term solution
   - Addresses root cause
   - Requires significant effort

---

## Files

- `netlist_exploration.py` — Comprehensive exploration code
- `connectivity_rca.py` — Root cause analysis for connectivity filter
- `connectivity_filter_v2.py` — 18 filter experiment configurations
- `output/netlist_exploration/exploration_summary.json` — Exploration results
- `output/connectivity_rca/rca_summary.json` — RCA data
- `output/connectivity_filter_v2/results.json` — Filter experiment results

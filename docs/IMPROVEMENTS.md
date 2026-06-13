# Improvement Roadmap — Joining & Detection

> **For next agent:** This is a temp scratchpad of validated improvement leads.
> Real + synthetic benchmarks are complete. These are ranked by expected impact.

---

## 1. Self-Loop Elimination in `degree_budget_completion` 🔴 High Impact

**Problem:** `degree_budget_completion` produces +2.8 self-loops/image on real data
(+0.3 on synthetic). These break SPICE simulation (a component's two pins end up
on the same net).

**Root cause:** When completing a two-terminal component (R, C, L, D), both floating
pins can be assigned to the same net via cross-completion.

**Proposed fix:** In `degree_budget_completion`, after finding completion candidates,
check if the target component has 2 floating pins. If so, only allow one pin to
complete to a given net. The other pin must find a different net.

**Validation:** Re-run on real (133 images) + synthetic (15 circuits). Expect:
- Self-loops: 4.4 → ~1-2 (real), 0.3 → ~0 (synthetic)
- Connectivity: should stay at 83.8% (real), 0.970 (synthetic)
- Wire coverage: should stay ~82% (real)

**File (corrected):** `wire_detection/synthgt/candidate_joins.py` → `degree_budget_completion()`.
NOT `core/joining.py` — degree_budget lives in the synthgt module; it was evaluated
on real data but never moved to core. So "promote to default" (#3) also requires
registering it as a core join strategy first — that step is NOT yet done.

**✅ DONE (synthetic-validated):** added a self-loop guard — the completion
b-matching refuses to merge two nets that already share a component (one pin per
component per net), and skips any match that would. Synthetic self-loops/image
0.37 → **0.15** at L4 (now *below* graph_rescue's 0.17); mean-err F1 unchanged at
0.972; connectivity 99–100%. **Real (133 images) still needs re-running** — the
bench script (`scripts/bench_degree_budget.py`) has machine-specific `/home/claw`
paths; point them at the local dataset to confirm 4.4 → ~1–2.

---

## 2. Wire Tracking in `netlist_from_uf` 🟡 Medium Impact

**Problem:** `degree_budget_completion` populates `n.components` but NOT `n.wires`.
This means wire tracking shows 0% for degree_budget results.

**Root cause:** `netlist_from_uf()` built nodes with an empty `wires=[]`; the base
graph_rescue wires were discarded on the way to the final netlist.

**File (corrected):** `wire_detection/synthgt/candidate_joins.py` → `netlist_from_uf()`
(NOT `core/netlist.py`).

**✅ DONE (synthetic-validated):** `netlist_from_uf` now accepts the base netlist
and carries each base node's wire indices onto the final node its pins landed in;
`degree_budget_completion` passes its graph_rescue base through. Completion edges
are wireless by nature (inferred, like a manual pin-to-pin merge) and add none.
Synthetic `pct_wires_used` 0% → **100%** (matches graph_rescue) at every error
level. Verify on real with the bench script once its paths are fixed.

---

## 3. Per-Image Adaptive Parameters 🟡 Medium Impact

**Problem:** 31/133 real images (23%) have F1 < 0.50 on detection. These are
bimodal lighting or dense circuits where fixed Sauvola params fail.

**Proposed approach:**
- Classify images by paper type (white, tan, blue, green) using VLM or color histogram
- Use per-type Sauvola k values (e.g., tan paper needs k=0.35, white k=0.25)
- Could also adapt window_size based on circuit density

**Validation:** Run expanded_benchmark with per-type configs. Target: reduce
F1 < 0.50 count from 31 to < 15 images.

**Files:** `wire_detection/core/pipeline.py`, `wire_detection/benchmark/expanded_benchmark.py`

---

## 4. Reach Factor Tuning on Real Data 🟢 Low Impact

**Problem:** `REACH_FACTOR=2.5` is hardcoded. Chris's analysis showed 2.8x and 3.5x
were "noise" on synthetic, but real images have different scale.

**Proposed approach:** Sweep reach_factor ∈ {2.0, 2.5, 3.0, 3.5} on real images only.
Check if connectivity improves without increasing self-loops.

**Validation:** Run `bench_all_joins.py` with different reach factors.

**File:** `wire_detection/core/joining.py` → `degree_budget_completion()`

---

## 5. Detection-Side: Component Occlusion Improvement 🟢 Low Impact

**Problem:** Component occlusion uses local median color, but some components
(resistors with colored bands, ICs with text) leave residual edges that get
detected as wires.

**Proposed approach:** After median fill, apply a small Gaussian blur (σ=1.5)
inside component bboxes to smooth residual edges.

**Validation:** Re-run detection benchmark. Check if FP count decreases.

**File:** `wire_detection/core/pipeline.py` → occlusion step

---

## 6. Synthetic Circuit Coverage Expansion 🟢 Low Impact

**Current catalog:** 15 circuits (series, parallel, series_parallel, rc_series,
rc_parallel, rc_cascade, bridge, wheatstone, h_bridge, ladder, filter, coupled,
gnd_ref, two_sources, dense_pair)

**Missing topologies:**
- Multi-stage filters (Sallen-Key, multiple feedback)
- Op-amp circuits (with feedback paths)
- Transistor circuits (common emitter, differential pair)
- Power supply circuits (rectifier, regulator)

**Why it matters:** More topologies = better validation that joining algorithms
generalize. Current set is weighted toward passive-only circuits.

**File:** `wire_detection/synthgt/circuits.py` → CATALOG dict

---

## Benchmark Reference

**Real images (aligned labels, 133 images):**
```
degree_budget_comp:  83.8% conn,  3.8 flt,  4.4 loops,  82% wires
graph_rescue:        72.1% conn,  6.4 flt,  1.6 loops,  82% wires
graph_full:          65.1% conn,  7.5 flt,  1.6 loops,  81% wires
production:          62.9% conn,  6.6 flt,  3.4 loops,  69% wires
```

**Synthetic (15 circuits, L4 error):**
```
degree_budget_comp:  0.970 F1
graph_rescue:        0.948 F1
```

**Detection:** best_candidate_v4 F1 = 0.774 (aligned labels)

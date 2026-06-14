# 🚨 READ THIS FIRST — Critical Preprocessing Steps

The wire detection pipeline **WILL NOT WORK** without these three preprocessing steps. Many AI agents skip them and produce garbage results.

## MANDATORY Preprocessing (in order)

### 1. Component Detection (Single Source of Truth)

**🚨 CRITICAL — Use the trained model for all component detection.**

The trained YOLO model at `models/component_detection/yolo26m_obb_16class_aug.pt` is the **single source of truth** for component labels. This replaces Roboflow's pre-trained model.

```python
from ultralytics import YOLO

model = YOLO('models/component_detection/yolo26m_obb_16class_aug.pt')
results = model('path/to/image.jpg', task='obb')

# Extract component bounding boxes from results
for result in results:
    if result.obb:
        for i in range(len(result.obb.cls)):
            cls_id = int(result.obb.cls[i])
            bbox = result.obb.xyxy[i].tolist()  # [x1, y1, x2, y2]
            conf = float(result.obb.conf[i])
```

**Why this matters:** Previous pipeline used Roboflow's pre-trained model (non-standard class IDs like 37, 14, 55). Our trained model has consistent 16-class labels that map directly to circuit components.

**Legacy: Roboflow Label Matching (deprecated)**
The Roboflow model at `roboflow_test2/` is kept for reference but should NOT be used for new work. If you must use it (e.g., for backward compatibility with existing eval scripts):

- **Always use `find_exact_match_roboflow()`** from `wire_detection/data/dataset.py`
- Each Roboflow image has multiple `.rf.<hash>` versions — some augmented, some pixel-identical
- `find_roboflow_image()` returns the first match (may be augmented, wrong coordinate space)
- Paths: `/home/claw/circuit-digitization/roboflow_test2/{train,valid,test}/labels/`
- Images: `/home/claw/workspace/ground_truth/labels_few_annot/images/`
- Labels: `/home/claw/workspace/ground_truth/labels_few_annot/labels/train/manually_verified_no_background_data/images/`
- Matches: **134 images** with both GT wire labels and HDC component labels (3,524 total wire annotations)

### 2. Component Occlusion  
Fill each component polygon with **local median color** (NOT white, NOT black — use `np.median()` of local region).
- Margin: 15% of bbox size, min 5px
- This removes text, component edges, internal structures

### 3. ROI Crop + Padding
Crop to union of all component bounding boxes + 10px padding in all directions.
- This removes scanner border artifacts and paper edges
- Remember to add the offset (rx1, ry1) back to all detected line endpoints

## Pipeline Params (DO NOT CHANGE)
- Sauvola: k=0.285, window=67
- Close: ellipse 3×3
- CCL: min_area=28
- PCA endpoints (not extremal)
- Overlap dedup: angle=12°, dist=8px  
- Anchor filter: endpoint_dist=**16**, link_dist=8
- **NO merge, NO length filter** — both destroy TPs

## Expanded Benchmark (134 images, all 36 configs)
Run: `uv run python wire_detection/benchmark/expanded_benchmark.py`

### Top Configs (Jun 2026, corrected eval — exact-match labels on original images)
| Rank | Config | F1 | Precision | Recall | FP | FN |
|---|---|---|---|---|---|---|
| 1 | **a16** (anchor_endpoint_dist=16) | **0.9755** | 0.9729 | 0.9781 | 47 | 77 |
| 2 | v4 baseline (anchor_endpoint_dist=12) | 0.9730 | 0.9741 | 0.9719 | 44 | 99 |
| 3 | best_candidate_v2 | 0.9589 | 0.9442 | 0.9742 | 81 | 91 |
| 4 | best_candidate_v1 | 0.9498 | 0.9213 | 0.9801 | 112 | 70 |
| 5 | best_candidate_v3 | 0.9490 | 0.9235 | 0.9759 | 110 | 85 |

### Key Findings
- **a16** (Sauvola + component extraction + anchor_endpoint_dist=16) is the winner
- Only change from v4 baseline: anchor_endpoint_dist 12 → 16 (+0.0025 F1)
- **Sauvola dominates all other thresholding methods** — adaptive Gaussian F1=0.928, OTSU F1=0.828, Triangle F1=0.795
- Skeleton extraction loses recall (FN=402 vs 77) — breaks thin wires
- Adaptive thresholding fusion adds nothing — Sauvola already captures optimal per-pixel threshold
- Parameter sweep shows pipeline is **robust** — k, window, link_dist, dedup_angle variations have minimal effect

### Per-image Breakdown (a16)
- **117 images** (87%) — F1 >= 0.90
- **Median F1: 1.000**
- **4 images** (3%) — F1 < 0.50 (dense circuits where large component occlusion eats wire endpoints)

## VLM Quality Assessment
- Module: `wire_detection.vlm` — classify images by paper type via VLM or programmatic scores
- CLI: `wire-vlm classify`, `wire-vlm sweep`, `wire-vlm audit-pipeline`
- Doc: `docs/vlm-experiments.md`

## Component Detection Model (Jun 2026)

**Location:** `models/component_detection/yolo26m_obb_16class_aug.pt` (46MB, not in git — see .gitignore)
**SHA256:** `d700b33f90191968af9f7f2798fff5e90a3f1ea473b811adc241bc570987264d`

**Model:** YOLO26M-OBB, trained on CGHD dataset (same dataset used for wire detection pipeline)
- **16 classes** (merged from 61 original — class merging was critical)
- **2,652 train / 468 val** images, 85/15 random split
- **Excluded drafter_0** (different drawing style from all other drafters)

### Performance (Best: Run 2)
| Metric | Value |
|--------|-------|
| mAP50 | **88.5%** |
| mAP50-95 | 78.3% |
| Precision | 95.6% |
| Recall | 88.6% |
| Epochs | 200 |

### Per-Class Recall
- **Perfect:** operational_amplifier (100%)
- **Strong (>90%):** inductor, voltage_source, capacitor, transistor, resistor, diode, integrated_circuit, other
- **Moderate (80-90%):** gnd, text, junction, terminal, switch, vss
- **Weak (<80%):** crossover (70.7%) — crossing wires visually ambiguous

### Training Config
- Augmentations: mosaic=1.0, mixup=0.15, degrees=10, translate=0.2, scale=0.5, shear=2, fliplr=0.5, flipud=0.1, erasing=0.4, hsv, randaugment
- Optimizer: AdamW, lr0=0.001, cos_lr=true
- Image size: 1024, Batch: 17

### Key Learnings
1. **Class merging:** 61→16 classes improved mAP from ~50% to 85%
2. **Augmentations:** +3.5% mAP over no-augmentation baseline
3. **M model > L model:** Smaller model generalizes better on this dataset size with augmentations
4. **Crossover remains hardest:** Two crossing wires look identical to regular wires

### Usage
```python
from ultralytics import YOLO
model = YOLO('models/component_detection/yolo26m_obb_16class_aug.pt')
results = model('path/to/image.jpg', task='obb')
```

## Common Errors Agents Make
1. ✗ Using Roboflow model instead of trained model → wrong class IDs (37, 14, 55), inconsistent labels. **Use `models/component_detection/yolo26m_obb_16class_aug.pt`**
2. ✗ Skipping occlusion entirely → FP count explodes
3. ✗ Filling with white (255) instead of median color → edges become wires
4. ✗ Not cropping to ROI → scanner borders detected as wires  
5. ✗ Forgetting coordinate offset after crop → lines in wrong position
6. ✗ Using merge or length filter → 64 TPs destroyed
7. ✗ Using old params (otsu, dilate=5, min_area=30, dedup_dist=12) → wrong pipeline
8. ✗ Not matching HDC labels → no occlusion at all
9. ✗ Using pixel-diff matching instead of prefix matching → only finds 23/134 images
10. ✗ Using `find_roboflow_image()` (first-match) instead of `find_exact_match_roboflow()` → labels from augmented version applied to original image → wrong occlusion polygons. **Always use exact-match.**
11. ✗ Using original GT image with first-match Roboflow labels → 28/30 poor images have augmented versions with different coordinate space. Use `find_exact_match_roboflow()` to get labels in the same coordinate space as the original.

## Netlist / SPICE / Topology Pipeline

The netlist pipeline lives in `wire_detection/api/routes/netlist.py` (`/api/netlist` POST).

**Pin discovery** (`wire_detection/core/netlist.py`):
- `derive_pins_from_obb()` — static pins for ALL component types (junctions, terminals, R, C, L, etc.) via OBB geometry
- `discover_pins()` — DBSCAN clustering of wire endpoints near SPICE-active components (R, C, L, D, Q, V only)
- **Combined in `_build_netlist_data()`**: OBB pins from ALL components + override positions from `discover_pins` where available → `build_netlist()` with 30px max_pin_dist

**Params flow**: Tuner params (`sauvola_k`, `ccl_min_area`, `dedup_angle`, etc.) are forwarded through `NetlistRequest.params` → `_build_netlist_data(params_overrides)` → `_run_preset_pipeline()`. Changing tuner sliders now affects netlist output.

**SPICE generation** (`wire_detection/core/spice.py`):
- `SpiceGenerator.generate(components, Netlist)` — produces `.end`-delimited SPICE
- Junctions and terminals produce SPICE lines but aren't valid simulation elements
- Auto-injects 5V source when no VSRC detected

**UI entry point**: `ui/src/app/HomeClient.tsx` — desktop layout shows 4-panel image grid + 3 tabs (Netlist, Simulation, Topology)

**Topology tab** (`ui/src/components/CircuitGraph.tsx`):
- Built with **React Flow v12** (`@xyflow/react`) — replaces the old custom SVG implementation
- Renders components at actual image-coordinate positions, scaled to a 0-800 coordinate space
- **Compact 24px colored circles** (halved from 44px) reduce overlap in dense layouts
- **Component scale slider** (0.3×–3.0×) in the info bar adjusts node size on the fly
- 134+ connection lines (edges) rendered via React Flow's `straight` edge type
- Built-in zoom (mouse wheel) and pan (click-drag)
- `fitView` on load auto-scales to show all components
- Click a node to select — highlights connected edges in blue, dims unconnected nodes
- Click the background to deselect
- React Flow `Controls` component for +/- zoom buttons (bottom-right)
- Legend bar shows color swatches by component type + component/connection count

**Custom node** (`ui/src/components/CircuitNode.tsx`):
- Colored circle with `border-radius: 50%`, type-specific colors
- Component name label inside (7-9px font, adjusts with scale)
- Pulsing glow on selection, type label shown below on selection
- `Handle` components (invisible) required for edge rendering
- Accepts `scale` and `dimmed` data props for dynamic sizing and selection dimming

**CRITICAL — React Flow v12 pitfalls:**
- Do **NOT** use `useNodesState()` or `useEdgesState()` from `@xyflow/react` — in React 19 StrictMode these silently drop edges and duplicate nodes. Use plain `useState<Node[]>` + `applyNodeChanges` / `useState<Edge[]>` + `applyEdgeChanges` instead.
- Use `type: "straight"` for edges (not `"default"`) — cleaner look, fewer rendering edge cases.
- `<Handle>` components on custom nodes are REQUIRED for edges to render (even if invisible).
- Use `as unknown as YourDataType` cast for node `data` from `NodeProps` (React Flow v12 typing quirk).

**Key architecture rules:**
1. `api/main.py` does NOT exist — entry point is `api/server.py` (uvicorn `api.server:app`)
2. Backend runs on port 8000, UI on port 4200 (proxied via Next.js rewrites)
3. All `localhost:8000` calls happen server-side in Next.js server actions, never from the browser

## Netlist / Joining (COMPLETE — `degree_budget` is default)

**Status:** Node joining is substantially complete. `degree_budget`
(graph_rescue + floating-pin recovery) is the promoted default strategy.
Beats graph_rescue on **92/133 images** with 0 regressions.

**Strategy:** `wire_detection/core/join_strategies.py` — 12+ composable strategies,
registry-based. `DEFAULT_STRATEGY = "degree_budget"`. Strategies compose:
1. Pin localization — static OBB pins + DBSCAN clustering (SPICE-active types)
2. Wire conditioning — optional end-extension
3. Attach — which pins each wire-end connects to
4. Merge — union-find across pins + endpoints

**Endpoint-graph join** (`wire_detection/core/join_graph.py`):
- Both wire endpoints AND component pins are graph nodes
- 5 edge types: wire body, endpoint↔endpoint, endpoint↔pin, endpoint↔wire-body (T-junction), pin↔wire-body
- Scale-relative tolerances (`k × median component size`) for ~6× circuit-scale range
- `graph_rescue` gives dangling wire-ends a longer directional reach toward pins on different components

**Verification tooling:**
- `wire_detection/benchmark/netlist_validate.py` — structural join-health scorecard
- `wire_detection/benchmark/netlist_viz.py` — image-grounded overlays (`_joins.png`) + per-net stepper
- **Join Check** UI tab (`JoinCheckPanel.tsx`, `/api/join_overlay`) — cycle strategies, view metrics + overlays

**Key numbers (134-image GT set, fresh best_candidate_v4 detection):**
| Strategy | balanced | composite | wires-used% | nets/comp | self-loop | floating | % Connected |
|----------|----------|-----------|-------------|-----------|-----------|----------|-------------|
| **degree_budget** (default) | **0.3100** | 0.2861 | **99.3** | 0.158 | 433 | 948 | **81.9%** |
| graph_rescue | 0.3732 | 0.3718 | 99.4 | 0.117 | 208 | 1629 | 68.8% |
| graph_scale | 0.3691 | 0.3635 | 99.5 | 0.135 | 77 | 1724 | 67.0% |
| graph_dir_30 | 0.3697 | 0.3632 | 99.5 | 0.131 | 85 | 1709 | 67.3% |
| graph_full | 0.3747 | 0.3739 | 99.4 | 0.116 | 207 | 1641 | 68.6% |
| junction_extend_n1 | 0.4411 | 0.3483 | 83.2 | 0.143 | 45 | 1690 | 68.0% |
| production (old) | 0.4738 | 0.3299 | 77.1 | 0.109 | 441 | 1175 | 77.5% |

`degree_budget` = graph_rescue + floating-pin recovery. +13.1pp connectivity over graph_rescue, 0 regressions.

Full details: `docs/research/join-verification.md`

## Shared Component-Assignment Logic (MANDATORY)

**The component-assignment logic is centralized in `wire_detection/core/component_assignment.py`.** This module is the SINGLE SOURCE OF TRUTH for determining which component and pin a wire endpoint belongs to.

**Why this exists:** The join pipeline and visualizations both need to answer "which component does this endpoint connect to?" If they implement this independently, they diverge (see RCA in git history — visualization showed endpoints as disconnected when the pipeline had correctly assigned them).

**API:**
```python
from wire_detection.core.component_assignment import (
    assign_endpoint_to_component,  # Step 1: nearest component by bbox proximity
    pick_pin_for_component,        # Step 2: which pin based on geometry
    assign_endpoint_to_pin,        # Combined: assign to component, then pick pin
    snap_endpoint,                 # For visualization: snap to pin coordinates
)
```

**Rules:**
1. **NEVER reimplement component-assignment logic locally** — always import from `component_assignment.py`
2. **Visualizations** use `snap_endpoint(ep, components, pin_pos)` to snap endpoints to pin positions
3. **Pipeline code** uses `assign_endpoint_to_component()` + `pick_pin_for_component()` in the union-find graph builder
4. **Tests** should verify that both pipeline and visualization produce identical assignments

**Assignment algorithm (must match everywhere):**
- Distance from endpoint to bbox (0 if inside, else to nearest edge)
- Assignment radius: `max(tau_pin, 0.5 × component diagonal)`
- Pin selection: horizontal → left/right, vertical → top/bottom

**Known gotchas:**
- `core/netlist.py` imports `sklearn` but `scikit-learn` is **missing from
  `pyproject.toml`** → clean installs crash `/api/netlist` + `/api/join_overlay`.
  Add it to deps.
- `ui/package.json` `dev` script (`HOSTNAME=0.0.0.0 next…`) fails on Windows; run
  `pnpm exec next dev -p 4200`.
- ngspice isn't bundled; Simulation fails gracefully until the binary is on PATH.
  Simulation uses generator default values, so it does **not** validate joins.

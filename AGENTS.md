# 🚨 READ THIS FIRST — Critical Preprocessing Steps

The wire detection pipeline **WILL NOT WORK** without these three preprocessing steps. Many AI agents skip them and produce garbage results.

## MANDATORY Preprocessing (in order)

### 1. HDC Label Matching
Each image needs YOLO-OBB component labels from roboflow_test2.

**🚨 CRITICAL — Exact-Match Label Selection (Jun 2026):**
Each Roboflow image has **multiple** `.rf.<hash>` versions — some augmented, some pixel-identical to the original. `find_roboflow_image()` returns the first match (sorted by filename), which may be augmented. Its labels are in a **different coordinate space** and will produce wrong occlusion polygons on the original image.

**Always use `find_exact_match_roboflow()`** from `wire_detection/data/dataset.py` (or `find_exact_match()` from `expanded_benchmark.py`). This finds the Roboflow version with pixel error < 0.01 (identical to original) and returns its labels. These labels are in the **same coordinate space** as the original image, so occlusion polygons are correct.

```python
# CORRECT — exact-match labels (same coord space as original)
from wire_detection.data.dataset import find_exact_match_roboflow
result = find_exact_match_roboflow(orig_path, hdc_base=HDC_BASE)
if result:
    rob_path, label_path = result
    components = ref.parse_components(label_path, w, h)

# WRONG — first-match labels (may be augmented, wrong coord space)
from wire_detection.data.dataset import find_roboflow_image
rob_path = find_roboflow_image(orig_path)  # may return augmented version!
```

- Paths: `/home/claw/circuit-digitization/roboflow_test2/{train,valid,test}/labels/`
- Augmented images: `/home/claw/circuit-digitization/roboflow_test2/{train,valid,test}/images/`
- Images: `/home/claw/workspace/ground_truth/labels_few_annot/images/`
- Labels: `/home/claw/workspace/ground_truth/labels_few_annot/labels/train/manually_verified_no_background_data/images/`
- Matches: **134 images** with both GT wire labels and HDC component labels (3,524 total wire annotations)
- **28 of 30 poor images** have augmented Roboflow versions — using first-match labels causes incorrect occlusion

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
- **91+ images** (68%+) — F1 >= 0.90
- **Median F1: 1.000**
- **31 images** (23%) — F1 < 0.50 (poor: bimodal lighting, dense circuits)

## VLM Quality Assessment
- Module: `wire_detection.vlm` — classify images by paper type via VLM or programmatic scores
- CLI: `wire-vlm classify`, `wire-vlm sweep`, `wire-vlm audit-pipeline`
- Doc: `docs/vlm-experiments.md`

## Common Errors Agents Make
1. ✗ Skipping occlusion entirely → FP count explodes
2. ✗ Filling with white (255) instead of median color → edges become wires
3. ✗ Not cropping to ROI → scanner borders detected as wires  
4. ✗ Forgetting coordinate offset after crop → lines in wrong position
5. ✗ Using merge or length filter → 64 TPs destroyed
6. ✗ Using old params (otsu, dilate=5, min_area=30, dedup_dist=12) → wrong pipeline
7. ✗ Not matching HDC labels → no occlusion at all
8. ✗ Using pixel-diff matching instead of prefix matching → only finds 23/134 images
9. ✗ Using `find_roboflow_image()` (first-match) instead of `find_exact_match_roboflow()` → labels from augmented version applied to original image → wrong occlusion polygons. **Always use exact-match.**
10. ✗ Using original GT image with first-match Roboflow labels → 28/30 poor images have augmented versions with different coordinate space. Use `find_exact_match_roboflow()` to get labels in the same coordinate space as the original.

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

## Netlist / Joining (COMPLETE — `graph_rescue` is default)

**Status:** Node joining is substantially complete. The endpoint-graph join
(`graph_rescue`) is the default strategy and beats the original production join
on **53/58 images** with 100% effective wire usage and 84% connectivity.

**Strategy:** `wire_detection/core/join_strategies.py` — 12+ composable strategies,
registry-based. `DEFAULT_STRATEGY = "graph_rescue"`. Strategies compose:
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
| Strategy | balanced | composite | wires-used% | nets/comp | self-loop | floating |
|----------|----------|-----------|-------------|-----------|-----------|----------|
| **graph_rescue** (default) | **0.1247** | 0.1176 | **97.7** | 0.123 | 233 | 276 |
| graph_scale | 0.1261 | 0.1163 | 97.5 | 0.157 | 96 | 454 |
| graph_dir_30 | 0.1262 | 0.1128 | 97.6 | 0.153 | 110 | 409 |
| graph_full | 0.1262 | 0.1195 | 97.7 | 0.120 | 233 | 288 |
| junction_extend_n1 | 0.1954 | 0.1096 | 83.4 | 0.142 | 72 | 415 |
| production (old) | 0.2504 | 0.1140 | 73.0 | 0.119 | 224 | 266 |

Graph strategies dominate the top 5. `graph_rescue` uses 97.7% of wires (vs production's 73%) while keeping low over-merge.

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

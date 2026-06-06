# 🚨 READ THIS FIRST — Critical Preprocessing Steps

The wire detection pipeline **WILL NOT WORK** without these three preprocessing steps. Many AI agents skip them and produce garbage results.

## MANDATORY Preprocessing (in order)

### 1. HDC Label Matching
Each image needs YOLO-OBB component labels from roboflow_test2. **Use filename prefix matching** (not pixel-difference) — HDC files have `.rf.XXXX` suffixes from Roboflow augmentation.
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
- Anchor filter: endpoint_dist=12, link_dist=8
- **NO merge, NO length filter** — both destroy TPs

## Expanded Benchmark (134 images, all 36 configs)
Run: `uv run python wire_detection/benchmark/expanded_benchmark.py`

### Top Configs (Jun 2026)
| Rank | Config | F1 | Precision | Recall |
|---|---|---|---|---|
| 1 | **best_candidate_v4** | **0.8334** | 0.898 | 0.778 |
| 2 | best_candidate_v2 | 0.8258 | 0.873 | 0.784 |
| 3 | best_candidate_v3 | 0.8194 | 0.856 | 0.786 |
| 4 | skeleton_graph_v1 | 0.8185 | 0.815 | 0.822 |
| 5 | best_candidate_v1 | 0.8170 | 0.845 | 0.791 |

### Key Findings
- **best_candidate_v4** (Sauvola + component extraction) is the winner
- Skeleton graph methods (v5-v8) have higher precision but worse F1
- **OTSU is terrible** for this dataset (F1 < 0.67)
- Adaptive thresholding beats OTSU but not Sauvola (F1=0.755 vs 0.833)
- Sauvola adaptive gaussian fusion (F1=0.765) doesn't beat plain Sauvola

### Per-image Breakdown (best_candidate_v4)
- **91 images** (68%) — F1 >= 0.90
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

## Join Verification (the joining is the weak link — see `docs/join-verification.md`)

Detection F1 (0.83) does **not** measure join quality, and there's no end-to-end
netlist-correctness metric. The production join **over-merges** (≈58 components →
≈3.5 nets/image; 6.7% of components self-loop-shorted) because `build_netlist`
ties a wire-end to **every** pin within 30px (not the nearest) + transitive
union-find, which runs away in dense areas / at junctions.

Tooling for verifying & tracking joins (full details in `docs/join-verification.md`):
- `wire_detection/benchmark/netlist_validate.py` — structural join-health scorecard (composite = struct
  errors/component; the regression number to track).
- `wire_detection/benchmark/netlist_viz.py` — image-grounded join overlays (`_joins.png`) + `--isolate <stem>`
  per-net stepper. Legend: cyan=wire, green=nearest-pin join, orange=extra over-join.
- **Join Check** UI tab + `/api/join_overlay` (`api/routes/join_overlay.py`,
  `JoinCheckPanel.tsx`) — same overlay in the tuner, with all-nets + per-net views.
  Use **Topology** to spot an over-merged net, **Join Check** to prove which pins
  shouldn't be in it.

**Gotchas discovered:**
- `core/netlist.py` imports `sklearn` but `scikit-learn` is **missing from
  `pyproject.toml`** → clean installs crash `/api/netlist` + `/api/join_overlay`.
  Add it to deps.
- `ui/package.json` `dev` script (`HOSTNAME=0.0.0.0 next…`) fails on Windows; run
  `pnpm exec next dev -p 4200`.
- ngspice isn't bundled; Simulation fails gracefully until the binary is on PATH.
  Simulation uses generator default values, so it does **not** validate joins.

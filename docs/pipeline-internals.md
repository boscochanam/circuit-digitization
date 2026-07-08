# Pipeline Internals

The engineering contract for the wire-detection and netlist pipeline: the preprocessing steps that
the detector depends on, the parameters that must not drift, the join architecture, and the shared
modules that other code is required to call rather than reimplement.

## Mandatory preprocessing

The wire-detection pipeline does not work without these three steps, in this order. Skipping any of
them produces unusable output.

### 1. Component detection (single source of truth)

The trained YOLO model at `models/component_detection/yolo26m_obb_16class_aug.pt` is the single
source of truth for component labels.

```python
from ultralytics import YOLO

model = YOLO('models/component_detection/yolo26m_obb_16class_aug.pt')
results = model('path/to/image.jpg', task='obb')

for result in results:
    if result.obb:
        for i in range(len(result.obb.cls)):
            cls_id = int(result.obb.cls[i])
            bbox = result.obb.xyxy[i].tolist()  # [x1, y1, x2, y2]
            conf = float(result.obb.conf[i])
```

**Why this matters:** an earlier version of the pipeline used a Roboflow pre-trained model whose
class IDs were non-standard (37, 14, 55). The trained model has consistent 16-class labels that map
directly onto circuit components. See
[Benchmark Provenance](benchmark-provenance.md#component-detection-model-jun-2026) for the model's
measured performance.

#### Legacy: Roboflow label matching (deprecated)

The Roboflow model under `roboflow_test2/` is kept for reference and should not be used for new
work. If it must be used — for backward compatibility with an existing evaluation script — then:

- Always use `find_exact_match_roboflow()` from `wire_detection/data/dataset.py`.
- Each Roboflow image has multiple `.rf.<hash>` versions; some are augmented, some are
  pixel-identical to the original.
- `find_roboflow_image()` returns the *first* match, which may be an augmented copy in a different
  coordinate space.
- Matching yields **134 images** with both ground-truth wire labels and component labels (3,524
  total wire annotations).

### 2. Component occlusion

Fill each component polygon with the **local median colour** — not white, not black. Use
`np.median()` over the local region.

- Margin: 15% of the bounding-box size, minimum 5px.
- This removes text, component edges, and internal structure that would otherwise be detected as
  wire.

### 3. ROI crop and padding

Crop to the union of all component bounding boxes plus 10px of padding in every direction.

- This removes scanner border artifacts and paper edges.
- Add the offset `(rx1, ry1)` back to every detected line endpoint afterwards.

## Pipeline parameters

These are the tuned values. They are not free parameters.

| Stage | Value |
|---|---|
| Sauvola | `k=0.285`, `window=67` |
| Close | ellipse 3×3 |
| CCL | `min_area=28` |
| Endpoints | PCA (not extremal) |
| Overlap dedup | `angle=12°`, `dist=8px` |
| Anchor filter | `endpoint_dist=16`, `link_dist=8` |
| Merge | **off** |
| Length filter | **off** |

Merge and the length filter both destroy true positives (64 TPs in the reference benchmark) and
must stay off.

## Component-detection configuration

The component label source is switched via `wire_detection/config/defaults.yaml`:

```yaml
component_detection:
  source: model  # "model" | "ground_truth" | "roboflow"
  model_path: models/component_detection/yolo26m_obb_16class_aug.pt
  confidence_threshold: 0.5
```

| Source | Meaning |
|---|---|
| `model` | Trained YOLO26M-OBB. Default, single source of truth. |
| `ground_truth` | Ground-truth annotation files. For benchmarking and evaluation. |
| `roboflow` | Legacy Roboflow model. Deprecated; emits a warning. |

```python
from wire_detection.data.component_loader import load_components

# Uses the source configured in defaults.yaml
components = load_components(image_path)

# Override the source explicitly
components = load_components(image_path, source="ground_truth")
```

## Pitfalls

Failure modes that have actually occurred, and what they look like.

1. **Using the Roboflow model instead of the trained model** — wrong class IDs (37, 14, 55) and
   inconsistent labels. Use `models/component_detection/yolo26m_obb_16class_aug.pt`.
2. **Skipping occlusion** — the false-positive count explodes.
3. **Filling occlusions with white (255) instead of the local median colour** — the fill edges
   become wires.
4. **Not cropping to the ROI** — scanner borders are detected as wires.
5. **Forgetting the coordinate offset after the crop** — every detected line lands in the wrong
   position.
6. **Enabling merge or the length filter** — 64 true positives destroyed.
7. **Using the old parameters** (`otsu`, `dilate=5`, `min_area=30`, `dedup_dist=12`) — that is a
   different pipeline.
8. **Not matching component labels to the image** — no occlusion happens at all.
9. **Pixel-diff matching instead of prefix matching** when pairing images with labels — finds only
   23 of the 134 images.
10. **`find_roboflow_image()` (first match) instead of `find_exact_match_roboflow()`** — labels from
    an augmented copy get applied to the original image, so the occlusion polygons are wrong.
    Always use the exact-match lookup.
11. **Original ground-truth image plus first-match Roboflow labels** — 28 of the 30 poor-performing
    images have augmented versions in a different coordinate space. `find_exact_match_roboflow()`
    returns labels in the same coordinate space as the original.

## Netlist, SPICE and topology

The netlist pipeline lives in `wire_detection/api/routes/netlist.py` (`POST /api/netlist`).

### Pin discovery

In `wire_detection/core/netlist.py`:

- `derive_pins_from_obb()` — static pins for **all** component types (junctions, terminals, R, C, L,
  and so on) derived from OBB geometry.
- `discover_pins()` — DBSCAN clustering of wire endpoints near SPICE-active components (R, C, L, D,
  Q, V only).
- Combined in `_build_netlist_data()`: OBB pins from all components, plus override positions from
  `discover_pins()` where available, then `build_netlist()` with a 30px `max_pin_dist`.

### Parameter flow

Tuner parameters (`sauvola_k`, `ccl_min_area`, `dedup_angle`, and the rest) are forwarded through
`NetlistRequest.params` → `_build_netlist_data(params_overrides)` → `_run_preset_pipeline()`.
Changing a tuner slider therefore affects the netlist output.

### SPICE generation

In `wire_detection/core/spice.py`:

- `SpiceGenerator.generate(components, Netlist)` produces `.end`-delimited SPICE.
- Junctions and terminals produce SPICE lines but are not valid simulation elements.
- A 5V source is auto-injected when no voltage source is detected.

### Architecture rules

1. `api/main.py` does not exist — the entry point is `api/server.py` (uvicorn `api.server:app`).
2. The backend runs on port 8000, the UI on port 4200 (proxied via Next.js rewrites).
3. All `localhost:8000` calls happen server-side in Next.js server actions, never from the browser.

## Join architecture

`wire_detection/core/join_strategies.py` holds 12+ composable, registry-based strategies.
`DEFAULT_STRATEGY = "scale_completion"` (promoted Jun 2026; previously `degree_budget`).

Strategies compose four stages:

1. **Pin localization** — static OBB pins plus DBSCAN clustering for SPICE-active types.
2. **Wire conditioning** — optional end-extension.
3. **Attach** — which pins each wire-end connects to.
4. **Merge** — union-find across pins and endpoints.

### Endpoint graph

In `wire_detection/core/join_graph.py`, both wire endpoints and component pins are graph nodes.
There are five edge types:

1. Wire body
2. Endpoint ↔ endpoint
3. Endpoint ↔ pin
4. Endpoint ↔ wire-body (T-junction)
5. Pin ↔ wire-body (rail tap)

Tolerances are scale-relative (`k × median component size`) to cover the roughly 6× circuit-scale
range in the dataset. `graph_rescue` gives dangling wire-ends a longer directional reach toward pins
on a *different* component.

Measured strategy results are in [Benchmark Provenance](benchmark-provenance.md#connectivity-join-human-verified-net-level-benchmark).

### Verification tooling

- `wire_detection/benchmark/netlist_validate.py` — structural join-health scorecard.
- `wire_detection/benchmark/netlist_viz.py` — image-grounded overlays (`_joins.png`) plus a
  per-net stepper.
- The **Join Check** UI tab (`JoinCheckPanel.tsx`, `/api/join_overlay`) — cycle strategies, view
  metrics and overlays.

## Shared component-assignment logic

`wire_detection/core/component_assignment.py` is the **single source of truth** for deciding which
component and which pin a wire endpoint belongs to.

**Why it exists:** the join pipeline and the visualizations both need to answer "which component
does this endpoint connect to?" When they implemented it independently they diverged — the
visualization drew endpoints as disconnected that the pipeline had correctly assigned.

```python
from wire_detection.core.component_assignment import (
    assign_endpoint_to_component,  # Step 1: nearest component by bbox proximity
    pick_pin_for_component,        # Step 2: which pin, based on geometry
    assign_endpoint_to_pin,        # Combined: assign to component, then pick pin
    snap_endpoint,                 # For visualization: snap to pin coordinates
)
```

### Rules

1. Never reimplement component-assignment logic locally. Import it from
   `component_assignment.py`.
2. Visualizations use `snap_endpoint(ep, components, pin_pos)` to snap endpoints to pin positions.
3. Pipeline code uses `assign_endpoint_to_component()` plus `pick_pin_for_component()` in the
   union-find graph builder.
4. Tests should verify that the pipeline and the visualizations produce identical assignments.

### Assignment algorithm (must match everywhere)

- Distance from the endpoint to the **OBB**: zero if inside the rotated rectangle, otherwise the
  distance to the nearest OBB edge.
- Falls back to AABB distance when OBB vertices are unavailable.
- Assignment radius: `max(tau_pin, 0.5 × component diagonal)` — still the AABB diagonal.
- Pin selection: nearest-pin Euclidean routing (`pick_pin_for_component`).

### OBB changes (Jun 15 2026)

- `component_assignment.py`: `assign_endpoint_to_component` uses `obb_distance()`
  (point to rotated rectangle) instead of `bbox_distance()` (AABB).
- `netlist.py`: `derive_pins_from_obb` places pins at OBB edge midpoints. Two-terminal components:
  capacitors use the **longest** edges (the flat faces), everything else uses the **shortest** edges
  (the ends). Non-two-terminal components use the OBB axes instead of AABB dimensions.
- `join_graph.py`: degree-based pin pruning — for components with more than two pins (for example
  from four-edge midpoint placement), only the two most-connected pins are kept, which prevents
  spurious short circuits.

### Files that consume component assignment

| File | Usage |
|------|-------|
| `wire_detection/core/join_graph.py` | Pipeline: endpoint → component → pin, in union-find |
| `docs/draw_3panel.py` | Visualization: snap endpoints to pin positions |
| `docs/draw_circuits*.py` | Circuit catalog visualizations |
| `docs/draw_error_sweep.py` | Error sweep visualizations |

### Visualizations must use the real algorithm

Any visualization that shows connection status (connected/disconnected, recovered/missed) must use
the same logic as the pipeline.

Do this:

```python
from wire_detection.core.netlist import Netlist

# Does this wire connect two components? Ask the netlist.
is_connected = net.wire_connects_components(wire_idx)

# Or get all connected wires at once
connected = net.connected_wires()
```

Not this:

```python
# Wrong — reimplementing the containment test locally.
if x1 <= ep[0] <= x2 and y1 <= ep[1] <= y2:
    # Misses endpoints that are NEAR but OUTSIDE the bbox
    ...
# Wrong — reimplementing union-find traversal
for node in net.nodes:
    if wire_idx in node.wires:
        ...
```

The pipeline assigns an endpoint to the nearest component within a
`max(tau_pin, 0.5 × diagonal)` radius. An endpoint can sit 10-80px outside the bounding box and
still be assigned to that component. A visualization that only checks "inside the bbox" will render
those endpoints as disconnected.

### Connected wires: snap to pin positions

In result visualizations (the three-panel "After Join" figure), draw connected wires between the
**actual pin positions** they were assigned to, not at the error-injected endpoint positions. The
algorithm assigns an endpoint to a component and derives a pin position from geometry; the
error-injected endpoint may be 10-80px away from that pin, so drawing at the injected position makes
the wire visually fail to reach the component.

Use the netlist's `pin_to_node` and `nodes` to find which pins share a node with the wire, then snap
each endpoint to the nearest pin:

```python
node_pins = {node.node_id: [(p.x, p.y) for p in node.pins] for node in net.nodes}
wire_node = {}
for node in net.nodes:
    for w_idx in node.wires:
        wire_node[w_idx] = node.node_id
# For each wire: snap ep0 to nearest pin, ep1 to second-nearest pin in same node
```

### Changing the assignment logic

1. Edit only `wire_detection/core/component_assignment.py`.
2. Run the tests:
   `uv run python -m pytest wire_detection/tests/test_join_strategies.py wire_detection/tests/test_synthgt.py -x -q`
3. Run the evaluation: `uv run python -m wire_detection.synthgt --seeds 1 --strategy graph_rescue`
4. Regenerate the visualizations: `uv run python docs/draw_3panel.py`
5. Verify that L0 (clean) still gives F1 = 1.00 across all circuits.

## Tuner UI internals

The Topology view and the connection editor. Entry point: `ui/src/app/HomeClient.tsx`, which shows
a four-panel image grid plus three tabs (Netlist, Simulation, Topology).

### Data flow

`HomeClient.tsx` is the orchestrator. The Topology view fetches a `TopologyResult` (wires, pins,
components, nodes) and renders it via `TopologyOverlay` (the SVG over the image) plus the docked
`ConnectionEditorPanel` (the wire-editing UI).

Manual edits are **overrides** (`{reassign, join, remove}`) saved per image at
`wire_detection/overrides/{dataset}/{idx}.json`. The backend bakes them into the netlist as node
**merges** (union-find), so SPICE, voltage and current all reflect them. Reassign and join only ever
*merge* nets — they never detach from the old net; use the Disconnect action for removal.

### Do not fetch nav-sensitive data via server actions

Several server actions fire at once when you navigate between images (pipeline, overrides, netlist,
simulation, topology). Next serializes server actions, and one can be left hanging so its promise
never settles — which is why the topology overlay used to show the *previous* image until you
toggled the view. Fetch nav-sensitive data client-side instead (`fetch("/api/...")`; the same-origin
`/api` is rewritten to the backend in `next.config.ts`) with an `AbortController` so the latest
request wins. See the topology fetch in `HomeClient.tsx`.

### "Unconnected" means floating terminals, not floating wires

The join attaches essentially every detected wire to a net that touches a component, so floating
*wires* are approximately zero. The real "needs wiring" signal is a component **pin** whose net
touches no *other* component — a dead end. Those are ringed amber. Text-label pins are excluded:
each sits on its own isolated node and would otherwise all read as dead ends.

### Topology signals

The connection editor's info button opens an in-app legend. In code:

- **Net colour** — every wire and pin is coloured by its node id (`NODE_COLORS`). Same colour means
  same electrical net.
- **Green / red wire-end dots** (`isEndpointConnected` in `TopologyOverlay`) — green if the wire's
  endpoint sits on a multi-component net, red if it dangles or dead-ends. Red is the Quick Fix
  target: auto-connect to the nearest good pin within 50px.
- **Amber pin rings** — a component pin whose net touches no *other* component, the dead-end signal
  above. Drawn in the pins layer, so they only show when Pins is on.
- The dots and the rings are two overlapping "needs connecting" signals at different granularity
  (wire endpoint versus component pin). Keep them consistent if you change one, and prefer extending
  Quick Fix over adding a third signal.

### Datasets

`?ds=` and `?idx=` deep-link the dataset and image. The image list per dataset comes from the
backend `/api/list?ds=...`; load it for the *requested* dataset. HDC exposes roughly 1,680 images,
`gt_labels` roughly 94.

### Topology tab (`ui/src/components/CircuitGraph.tsx`)

Built with **React Flow v12** (`@xyflow/react`), replacing an earlier custom SVG implementation.

- Renders components at their actual image-coordinate positions, scaled to a 0-800 coordinate space.
- Compact 24px coloured circles reduce overlap in dense layouts.
- A component-scale slider (0.3×–3.0×) in the info bar adjusts node size on the fly.
- Connection lines are rendered via React Flow's `straight` edge type.
- Built-in zoom (mouse wheel) and pan (click-drag); `fitView` on load auto-scales to show all
  components.
- Click a node to select it: connected edges highlight in blue and unconnected nodes dim. Click the
  background to deselect.
- React Flow's `Controls` component provides the zoom buttons.
- A legend bar shows colour swatches by component type plus component and connection counts.

Custom node (`ui/src/components/CircuitNode.tsx`): a coloured circle
(`border-radius: 50%`) with type-specific colours, the component name inside (7-9px font, scaling
with the slider), a pulsing glow on selection and the type label below it. Invisible `Handle`
components are required for edge rendering. The node accepts `scale` and `dimmed` data props.

### React Flow v12 pitfalls

- Do **not** use `useNodesState()` or `useEdgesState()` from `@xyflow/react`. Under React 19
  StrictMode they silently drop edges and duplicate nodes. Use plain `useState<Node[]>` with
  `applyNodeChanges`, and `useState<Edge[]>` with `applyEdgeChanges`.
- Use `type: "straight"` for edges, not `"default"` — cleaner, and fewer rendering edge cases.
- `<Handle>` components on custom nodes are required for edges to render, even when invisible.
- Cast node `data` from `NodeProps` with `as unknown as YourDataType` — a React Flow v12 typing
  quirk.

### Known environment gotchas

- The `ui/package.json` `dev` script (`HOSTNAME=0.0.0.0 next…`) fails on Windows. Run
  `pnpm exec next dev -p 4200` instead.
- `ngspice` is not bundled. Simulation fails gracefully until the binary is on `PATH`. Simulation
  uses the generator's default component values, so it does **not** validate joins.

## Quality assessment

- Module: `wire_detection.vlm` — classify images by paper type, via a vision-language model or
  programmatic scores.
- CLI: `wire-vlm classify`, `wire-vlm sweep`, `wire-vlm audit-pipeline`.
- Documentation: [`docs/research/vlm-experiments.md`](research/vlm-experiments.md).

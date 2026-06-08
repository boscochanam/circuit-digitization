# Circuit Connectivity Visualization — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add interactive wire/component visualization with connectivity mapping directly on the schematic image, plus a topology graph view.

**Architecture:** Three-phase rollout — (1) structured topology JSON endpoint + interactive SVG overlay on the image, (2) React Flow topology graph tab with bidirectional selection, (3) path tracing between selected components.

**Tech Stack:** FastAPI (backend), Next.js + React + SVG overlays (frontend), React Flow v12 (graph view)

---

## Current State

**Backend data available today:**
- `/api/process` → `lines` (wire endpoints), `components` (bboxes, names, types)
- `/api/netlist` → `nodes` (pins, wire indices), `components`, `connections` (empty), `spice_netlist`
- `/api/join_overlay` → rendered PNG only (no structured pin/wire data)
- Pin data: `ComponentPin` has `x, y, component_idx, pin_name` — but only exposed inside netlist nodes

**Frontend:**
- `CircuitViewport.tsx` — image + component labels (div overlays), pan/zoom
- `OverlayControls.tsx` — view bar (Source, Threshold, Detected, Dilated, Voltage, Current, Join check)
- `JoinCheckPanel.tsx` — server-rendered join overlay image (not interactive)
- No wire/pin SVG overlays, no graph view

**Key constraint:** React Flow v12 pitfall — do NOT use `useNodesState` / `useEdgesState` from `@xyflow/react` in React 19 StrictMode. Use `useState` + `applyNodeChanges` / `applyEdgeChanges`.

---

## Phase 1: Interactive Wire/Component Overlay

### What we're building
An SVG layer on top of the schematic image that renders:
- **Wires** as clickable `<line>` elements (colored by netlist node)
- **Pins** as small circles at pin coordinates
- **Component bboxes** as semi-transparent rectangles
- Click a wire → highlight it + show connected components in a tooltip
- Click a component → highlight all wires/pins in its net
- Color legend showing node colors

### Data needed
The existing `/api/netlist` endpoint returns nodes with pin references, but is missing:
- Per-pin x/y coordinates
- Per-wire endpoint coordinates
- Wire-to-node assignment (which wires belong to which node)

We need a **new endpoint** `/api/topology` that returns the full structured graph.

---

### Task 1: Create `/api/topology` backend endpoint

**Objective:** Return structured JSON with all wires, pins, components, and their node assignments — everything needed to render the interactive overlay.

**Files:**
- Create: `wire_detection/api/routes/topology.py`
- Modify: `wire_detection/api/routes/__init__.py` (register router)

**Endpoint:** `POST /api/topology`

**Request model:** Same as `JoinOverlayRequest` (reuse or alias)

**Response shape:**
```json
{
  "wires": [
    {"idx": 0, "ep1": [357, 163], "ep2": [180, 176], "node_id": 1}
  ],
  "pins": [
    {"x": 174, "y": 428, "component_idx": 0, "component_name": "V1", "pin_name": "pin0", "node_id": 0}
  ],
  "components": [
    {"idx": 0, "name": "V1", "type": "voltage-DC", "bbox": [122, 296, 226, 395], "node_ids": [0, 1]}
  ],
  "nodes": [
    {"node_id": 0, "wire_count": 2, "pin_count": 4, "component_count": 3}
  ],
  "warnings": []
}
```

**Implementation:**
1. Reuse the same pipeline + join strategy as `/api/netlist`
2. After `run_strategy()`, iterate `netlist.nodes`:
   - For each node, emit wire indices → look up wire endpoints from the wires list
   - For each pin, emit `(x, y, component_idx, component_name, pin_name, node_id)`
3. For each component, collect unique `node_id`s from its pins
4. Assign each wire to the node it belongs to (from `node.wires`)

**Verification:** `curl -s http://localhost:8000/api/topology -H 'Content-Type: application/json' -d '{"img_idx": 117}' | python3 -m json.tool | head -30`

---

### Task 2: Create `fetchTopologyAction` server action

**Objective:** Frontend server action to call `/api/topology`.

**Files:**
- Modify: `ui/src/app/actions.ts`

**Implementation:**
```typescript
export async function fetchTopologyAction(
  img_idx: number, ds: string, preset: string,
  params: Record<string, string | number>, strategy: string
): Promise<TopologyResult> {
  const res = await fetch("http://localhost:8000/api/topology", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ img_idx, ds, preset, params, strategy }),
  });
  return res.json();
}
```

**Verification:** Build succeeds, no type errors.

---

### Task 3: Add `TopologyResult` types

**Objective:** TypeScript interfaces matching the `/api/topology` response.

**Files:**
- Modify: `ui/src/lib/types.ts`

**Types to add:**
```typescript
export interface TopologyWire {
  idx: number;
  ep1: [number, number];
  ep2: [number, number];
  node_id: number;
}

export interface TopologyPin {
  x: number;
  y: number;
  component_idx: number;
  component_name: string;
  pin_name: string;
  node_id: number;
}

export interface TopologyComponent {
  idx: number;
  name: string;
  type: string;
  bbox: [number, number, number, number];
  node_ids: number[];
}

export interface TopologyNode {
  node_id: number;
  wire_count: number;
  pin_count: number;
  component_count: number;
}

export interface TopologyResult {
  wires: TopologyWire[];
  pins: TopologyPin[];
  components: TopologyComponent[];
  nodes: TopologyNode[];
  warnings: string[];
}
```

**Verification:** TypeScript compiles.

---

### Task 4: Build `TopologyOverlay` SVG component

**Objective:** SVG overlay that renders wires, pins, and component bboxes on top of the image.

**Files:**
- Create: `ui/src/components/TopologyOverlay.tsx`

**Props:**
```typescript
interface TopologyOverlayProps {
  topology: TopologyResult;
  imgWidth: number;
  imgHeight: number;
  scaleX: number;
  scaleY: number;
  selectedNode: number | null;
  selectedComponent: string | null;
  onWireClick: (nodeId: number) => void;
  onComponentClick: (name: string) => void;
  showWires: boolean;
  showPins: boolean;
  showComponents: boolean;
}
```

**Rendering:**
1. `<svg>` sized to match the image, positioned absolute on top
2. Wires: `<line>` with `stroke` color from a node-color palette (12 distinct colors, cycling)
3. Pins: `<circle r="3">` with fill from node color
4. Component bboxes: `<rect>` with semi-transparent fill, `stroke` by type color
5. Selected node → thick stroke (3px) + glow filter on its wires/pins
6. Unselected → dim to 30% opacity when something is selected

**Node color palette:**
```typescript
const NODE_COLORS = [
  '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
  '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990',
  '#dcbeff', '#9A6324',
];
```

**Verification:** Render on image 117 — wires should be visible colored lines, pins as small dots.

---

### Task 5: Add topology toggle to `OverlayControls`

**Objective:** Add a "Topology" button in the view bar that activates the SVG overlay.

**Files:**
- Modify: `ui/src/components/OverlayControls.tsx`

**Changes:**
- Add to the Analysis group: `{ id: "topology", label: "Topology" }`
- This replaces the server-rendered image overlay with the interactive SVG overlay

**Verification:** Button appears in view bar, clicking it switches to topology mode.

---

### Task 6: Wire up topology in `CircuitViewport`

**Objective:** Fetch topology data and render `TopologyOverlay` when "Topology" view is active.

**Files:**
- Modify: `ui/src/components/CircuitViewport.tsx`
- Modify: `ui/src/app/HomeClient.tsx`

**Changes in HomeClient:**
- Add `topologyActive` state
- Fetch topology when active (useEffect + fetchTopologyAction)
- Pass `topology` data to CircuitViewport

**Changes in CircuitViewport:**
- When `activeOverlay === "topology"`, render `<TopologyOverlay>` instead of the image overlay
- Keep the source image visible underneath (dimmed or full opacity)
- Handle click events → set selected node/component state
- Show tooltip on wire/component click (component name, pin count, connected wires)

**Tooltip content:**
```
Node N2 (3 pins)
  V1.pin0, R2.pin0, J4.pin0
  2 wires, 3 components
```

**Verification:**
1. Click "Topology" → wires appear as colored lines on image
2. Click a wire → highlight its node, show tooltip
3. Click a component → highlight its connected wires
4. Click background → deselect all

---

### Task 7: Add topology controls panel

**Objective:** Toggle checkboxes for wires/pins/components visibility + node legend.

**Files:**
- Modify: `ui/src/components/TopologyOverlay.tsx` (add control bar)

**UI:**
- Checkbox toggles: Wires ✓, Pins ✓, Components ✓
- Node color legend: colored dots with "N0", "N1" labels (top 8 nodes)
- "Show all" / "Isolate" button to focus on one node

**Verification:** Toggles work, legend shows correct colors.

---

### Task 8: Commit and deploy Phase 1

```bash
git add -A && git commit -m "feat: interactive topology overlay with wire/component visualization"
docker compose down && docker compose up --build -d
```

**Manual verification:**
1. Navigate to `?idx=117`, click "Topology"
2. Wires are colored lines matching their netlist nodes
3. Click R2 → its wires highlight, tooltip shows "R2: pin0→N0, pin1→N3"
4. Toggle "Pins" off → pins disappear, wires remain
5. Select a node in the legend → isolate that net

---

## Phase 2: Topology Graph View

### What we're building
A new tab (like "Join check") that renders the circuit as a React Flow graph — components as nodes, wires as edges. Bidirectional selection: click in graph → highlights on image, and vice versa.

---

### Task 9: Create `TopologyGraph` component

**Objective:** React Flow graph rendering the circuit topology.

**Files:**
- Create: `ui/src/components/TopologyGraph.tsx`

**Props:**
```typescript
interface TopologyGraphProps {
  topology: TopologyResult;
  selectedNode: number | null;
  selectedComponent: string | null;
  onNodeSelect: (nodeId: number | null) => void;
  onComponentSelect: (name: string | null) => void;
}
```

**Implementation:**
1. Convert topology data to React Flow nodes + edges
2. Component nodes: positioned at image-coordinate centroids (scaled to 0-800 space)
3. Edge between two component nodes if they share a netlist node
4. Use `type: "straight"` for edges
5. Custom node component (reuse `CircuitNode.tsx` pattern from AGENTS.md)
6. Use `useState<Node[]>` + `applyNodeChanges` (NOT `useNodesState`)
7. `fitView` on load

**Node data:**
```typescript
{ label: "R2", type: "resistor", color: "#0000FF", nodeIds: [0, 3] }
```

**Edge data:**
```typescript
{ source: "comp-0", target: "comp-1", label: "N0", animated: false }
```

**Verification:** Graph shows V1, R2, R3 as nodes with edges labeled by shared net.

---

### Task 10: Add "Graph" tab to BottomPanel

**Objective:** New tab in the bottom panel for the topology graph.

**Files:**
- Modify: `ui/src/components/BottomPanel.tsx`
- Modify: `ui/src/app/HomeClient.tsx`

**Changes:**
- Add `{ value: "graph", label: "Graph" }` to TABS
- Add `BottomPanelTab` union: `"netlist" | "warnings" | "raw" | "graph"`
- Render `<TopologyGraph>` when `bottomPanelTab === "graph"`

**Verification:** "Graph" tab appears, clicking it shows the React Flow graph.

---

### Task 11: Bidirectional selection sync

**Objective:** Selecting a component in the graph highlights it on the image, and vice versa.

**Files:**
- Modify: `ui/src/app/HomeClient.tsx`
- Modify: `ui/src/components/TopologyGraph.tsx`
- Modify: `ui/src/components/TopologyOverlay.tsx`

**State management:**
- Shared `selectedComponent` state in HomeClient (already exists)
- Graph node click → `onComponentSelect(name)` → updates shared state
- Topology overlay click → same callback
- Both components receive `selectedComponent` as prop and highlight accordingly

**Verification:**
1. Click R2 in graph → R2 highlights on image
2. Click R2 on image → R2 highlights in graph
3. Click background in either → deselects in both

---

### Task 12: Graph node details panel

**Objective:** Clicking a graph node shows a details panel (pins, connected nets, current/voltage if available).

**Files:**
- Modify: `ui/src/components/TopologyGraph.tsx`

**UI:**
- Side panel (or popover) when a node is selected:
  - Component name, type, bbox
  - Pin list with coordinates and net assignments
  - Connected components (via shared nets)
  - Voltage/current if simulation data is available

**Verification:** Click R2 in graph → details show "R2: resistor, pins: pin0→N0, pin1→N3, connected: V1 (N0), R3 (N3)".

---

### Task 13: Commit and deploy Phase 2

```bash
git add -A && git commit -m "feat: topology graph view with bidirectional selection"
docker compose down && docker compose up --build -d
```

---

## Phase 3: Path Tracing

### What we're building
Select two components → highlight the path through the circuit, showing voltage drops and current along the way.

---

### Task 14: Add path-finding backend endpoint

**Objective:** Given two component names, return the path through the netlist (sequence of nodes and components).

**Files:**
- Create: Add to `wire_detection/api/routes/topology.py`

**Endpoint:** `POST /api/path`

**Request:**
```json
{"img_idx": 117, "from": "V1", "to": "R3", "ds": "gt_labels", "preset": "best_candidate_v4"}
```

**Response:**
```json
{
  "path": [
    {"type": "component", "name": "V1", "node_id": 0},
    {"type": "node", "node_id": 0, "components": ["V1", "R2"]},
    {"type": "component", "name": "R2", "node_id": 3},
    {"type": "node", "node_id": 3, "components": ["R2", "R3"]},
    {"type": "component", "name": "R3", "node_id": 1}
  ],
  "voltage_drop": 5.0,
  "current": 0.0025
}
```

**Implementation:**
1. Build adjacency graph from netlist nodes
2. BFS from source component's node to target component's node
3. Return the path as alternating component/node entries
4. If simulation data available, compute voltage drop and current along path

**Verification:** `curl` returns correct path for V1→R3 on image 117.

---

### Task 15: Add path-tracing UI

**Objective:** User selects two components → path highlights on image and graph.

**Files:**
- Modify: `ui/src/components/TopologyOverlay.tsx`
- Modify: `ui/src/components/TopologyGraph.tsx`
- Modify: `ui/src/app/HomeClient.tsx`

**UX:**
1. Shift+click a component to set it as "path start"
2. Shift+click another to set "path end"
3. Path highlights in a bright color (e.g., gold/yellow) with thicker lines
4. Tooltip shows: "V1 → N0 → R2 → N3 → R3: 5V drop, 2.5mA"
5. Click background to clear path

**State in HomeClient:**
```typescript
const [pathStart, setPathStart] = useState<string | null>(null);
const [pathEnd, setPathEnd] = useState<string | null>(null);
const [pathData, setPathData] = useState<PathResult | null>(null);
```

**Verification:**
1. Shift+click V1, then Shift+click R3
2. Path V1→R2→R3 highlights in gold on image
3. Graph shows same path highlighted
4. Tooltip shows "5V drop, 2.5mA"

---

### Task 16: Commit and deploy Phase 3

```bash
git add -A && git commit -m "feat: path tracing between selected components"
docker compose down && docker compose up --build -d
```

---

## Verification Checklist

After all phases:
- [ ] `?idx=117` → Topology view shows V1, R2, R3 as colored wires/pins
- [ ] Click a wire → highlights node, shows connected components
- [ ] Click a component → highlights all its wires/pins
- [ ] Graph tab shows circuit as React Flow nodes/edges
- [ ] Click in graph ↔ highlights on image (bidirectional)
- [ ] Shift+click two components → path highlights with voltage/current
- [ ] Toggle wire/pin/component visibility
- [ ] Node color legend works
- [ ] No regressions on Voltage/Current/Join Check overlays
- [ ] Docker build clean, no TypeScript errors

---

## Files Summary

**New files:**
- `wire_detection/api/routes/topology.py` — `/api/topology` + `/api/path` endpoints
- `ui/src/components/TopologyOverlay.tsx` — SVG overlay on image
- `ui/src/components/TopologyGraph.tsx` — React Flow graph view

**Modified files:**
- `wire_detection/api/routes/__init__.py` — register topology router
- `ui/src/app/actions.ts` — add `fetchTopologyAction`, `fetchPathAction`
- `ui/src/lib/types.ts` — add `TopologyResult`, `TopologyWire`, `TopologyPin`, etc.
- `ui/src/components/OverlayControls.tsx` — add "Topology" button
- `ui/src/components/BottomPanel.tsx` — add "Graph" tab
- `ui/src/components/CircuitViewport.tsx` — render TopologyOverlay when active
- `ui/src/app/HomeClient.tsx` — topology state, path state, shared selection

**Key existing files (reference only, do not modify):**
- `wire_detection/core/netlist.py` — `ComponentPin`, `NetNode`, `Netlist` dataclasses
- `wire_detection/core/join_strategies.py` — `run_strategy()` returns `(pins, netlist)`
- `wire_detection/core/spice.py` — `SpiceGenerator`, `COMPONENT_NAMES`
- `wire_detection/api/routes/netlist.py` — `_build_netlist_data()` pattern to reuse
- `wire_detection/api/routes/join_overlay.py` — rendering pattern reference

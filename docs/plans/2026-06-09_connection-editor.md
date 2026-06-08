# Connection Editor — Manual Override for Wire-Component Joining

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Allow users to manually correct false connections in the auto-joined netlist via a visual endpoint editor on the topology overlay.

**Architecture:** Backend override system + frontend interactive endpoint editing on the topology overlay.

**Tech Stack:** FastAPI (backend), Next.js + SVG overlay (frontend)

---

## Current State

**What exists today:**
- `/api/topology` returns auto-joined wires, pins, components, nodes
- TopologyOverlay renders wires as colored lines, pins as dots, component rects
- Click interaction: wire → highlight node, component → highlight component
- Path tracing via shift+click
- Join strategy runs via `run_strategy()` in `wire_detection/core/join_strategies.py`

**Problem:** The auto-join sometimes makes wrong decisions — connecting wire endpoints to wrong components, missing connections, or creating spurious nodes. There's no way to fix these without re-running the pipeline with different parameters.

**Goal:** Let users override specific join decisions and have those overrides persist and affect the netlist/SPICE output.

---

## How Overrides Work

### Override Types

1. **Reassign** — Move a wire endpoint from its current pin to a different component's pin
   - `wire_3_ep2` currently on `V1.pin0` → reassign to `R2.pin1`

2. **Join** — Merge two wire endpoints (on different nodes) into the same node
   - `wire_0_ep1` + `wire_5_ep2` → both end up on the same node

3. **Remove** — Disconnect a wire endpoint from its node entirely
   - `wire_2_ep1` → no longer connected to any pin (floating endpoint)

### Storage

Override files stored at:
```
wire_detection/overrides/{dataset}/{img_idx}.json
```

Format:
```json
{
  "reassign": {
    "wire_3_ep2": {"component": "R2", "pin": "pin1"}
  },
  "join": [
    ["wire_0_ep1", "wire_5_ep2"]
  ],
  "remove": [
    "wire_2_ep1"
  ]
}
```

### Application Order

1. Run normal `run_strategy()` to get base join
2. Apply `reassign` overrides — move endpoint to new pin
3. Apply `remove` overrides — disconnect endpoints from nodes
4. Apply `join` overrides — merge nodes containing the joined endpoints
5. Rebuild node assignments with updated connections

---

## Implementation Tasks

### Task 1: Override storage layer

**Objective:** Read/write override files, validate override keys.

**Files:**
- Create: `wire_detection/core/connection_overrides.py`

**Functions:**
```python
def load_overrides(dataset: str, img_idx: int) -> dict:
    """Load overrides from JSON file. Returns empty dict if no file exists."""

def save_overrides(dataset: str, img_idx: int, overrides: dict) -> None:
    """Save overrides to JSON file. Creates directory if needed."""

def validate_override_key(key: str, wires: list, components: list) -> str | None:
    """Validate a wire endpoint key like 'wire_3_ep2'. Returns error message or None."""
```

**Key format:** `wire_{idx}_ep{1|2}` — maps to `wires[idx].ep1` or `wires[idx].ep2`

**Verification:** Unit tests for load/save/validate with sample data.

---

### Task 2: Override application in topology builder

**Objective:** Apply overrides after `run_strategy()` to modify the join result.

**Files:**
- Modify: `wire_detection/api/routes/topology.py` — update `_build_topology_data()`

**Changes:**
1. Accept optional `overrides` parameter in `_build_topology_data()`
2. After `run_strategy()`, apply overrides in order: reassign → remove → join
3. Rebuild wire_to_node mapping, pin assignments, node summaries
4. Return updated topology data

**Application logic:**
```python
def apply_overrides(wires, components_raw, all_pins, netlist, overrides):
    """Apply connection overrides to modify join results.
    
    1. reassign: Move wire endpoint to a different component pin
       - Remove endpoint from current node
       - Add endpoint to target component's pin node
       - May create new node if pin isn't in any existing node
    
    2. remove: Disconnect wire endpoint from its node
       - Remove endpoint from its node
       - Endpoint becomes floating (node_id = None)
    
    3. join: Merge two nodes
       - Find which nodes the two endpoints belong to
       - Merge smaller node into larger node
       - Update all wire/pin assignments
    """
```

**Verification:** POST to `/api/topology` with overrides, verify changed connections.

---

### Task 3: Override API endpoints

**Objective:** CRUD endpoints for managing overrides.

**Files:**
- Modify: `wire_detection/api/routes/topology.py`

**Endpoints:**

```
GET  /api/topology/overrides?idx=117&ds=gt_labels
  → Returns current overrides for an image

POST /api/topology/overrides
  Body: {"dataset": "gt_labels", "img_idx": 117, "overrides": {...}}
  → Saves overrides, returns updated topology

DELETE /api/topology/overrides?idx=117&ds=gt_labels
  → Clears all overrides for an image
```

**Verification:** CRUD cycle works, overrides persist across requests.

---

### Task 4: Frontend types and server actions

**Objective:** TypeScript types and server actions for override management.

**Files:**
- Modify: `ui/src/lib/types.ts`
- Modify: `ui/src/app/actions.ts`

**Types to add:**
```typescript
export interface ConnectionOverrides {
  reassign: Record<string, { component: string; pin: string }>;
  join: [string, string][];
  remove: string[];
}

export interface OverrideResponse {
  overrides: ConnectionOverrides;
  topology: TopologyResult;
}
```

**Actions to add:**
```typescript
export async function fetchOverridesAction(idx: number, ds: string): Promise<ConnectionOverrides>
export async function saveOverridesAction(idx: number, ds: string, overrides: ConnectionOverrides): Promise<TopologyResult>
export async function clearOverridesAction(idx: number, ds: string): Promise<void>
```

**Verification:** Build succeeds, actions callable.

---

### Task 5: Endpoint click UI in TopologyOverlay

**Objective:** Make wire endpoints clickable to open an edit panel.

**Files:**
- Modify: `ui/src/components/TopologyOverlay.tsx`

**Changes:**
1. Add small invisible `<circle>` elements at each wire endpoint (r=6, transparent fill, pointer cursor)
2. Click an endpoint → set `selectedEndpoint` state (e.g., `"wire_3_ep2"`)
3. Show a small floating panel near the clicked endpoint with:
   - Current connection info: "Connected to R2.pin1 (Node 2)"
   - **Reassign** button → opens pin selector dropdown
   - **Join with…** button → enters "join mode" (click another endpoint to join)
   - **Disconnect** button → removes endpoint from node
4. Click background or press Escape → close panel

**Panel positioning:**
- Position relative to the endpoint's screen coordinates
- Offset slightly to avoid covering the endpoint
- Dark background matching existing controls

**Verification:** Click endpoint → panel appears with current info and action buttons.

---

### Task 6: Pin selector for reassignment

**Objective:** Dropdown/list of all available pins to reassign an endpoint to.

**Files:**
- Modify: `ui/src/components/TopologyOverlay.tsx` (or create `EndpointEditPanel.tsx`)

**UI:**
- List all component pins grouped by component
- Each entry shows: "R2.pin1 (Node 2)" or "R3.pin0 (Node 1)"
- Current connection highlighted
- Click a pin → triggers reassign override
- Search/filter input for large circuits

**Data source:** Topology data's `pins` and `components` arrays

**Verification:** Select a new pin → endpoint reassigns, overlay updates.

---

### Task 7: Join mode UX

**Objective:** Interactive join workflow — select endpoints to merge.

**Files:**
- Modify: `ui/src/components/TopologyOverlay.tsx`

**UX:**
1. Click endpoint → panel shows "Join with…" button
2. Click "Join with…" → enters join mode:
   - Panel shows "Click another endpoint to join with wire_3_ep2"
   - Other endpoints glow/pulse to indicate they're selectable
   - Click another endpoint → triggers join override
   - Press Escape → cancel join mode
3. Visual feedback: joined endpoints get matching colors

**Verification:** Join two endpoints → they merge into same node, colors match.

---

### Task 8: Disconnect action

**Objective:** Remove an endpoint from its node.

**Files:**
- Modify: `ui/src/components/TopologyOverlay.tsx`

**Behavior:**
1. Click endpoint → panel shows "Disconnect" button
2. Click "Disconnect" → triggers remove override
3. Endpoint becomes floating: renders as grey dot, no node color
4. Wire line from that endpoint becomes dashed grey

**Verification:** Disconnect endpoint → it floats, wire becomes dashed.

---

### Task 9: Override state management in HomeClient

**Objective:** Track overrides, refetch topology after changes.

**Files:**
- Modify: `ui/src/app/HomeClient.tsx`

**State:**
```typescript
const [overrides, setOverrides] = useState<ConnectionOverrides>({ reassign: {}, join: [], remove: [] });
const [editingEndpoint, setEditingEndpoint] = useState<string | null>(null);
const [joinMode, setJoinMode] = useState<{ source: string } | null>(null);
```

**Flow:**
1. On image load: fetch existing overrides
2. On override change: save overrides → refetch topology → update overlay
3. Pass `overrides`, `editingEndpoint`, `joinMode` to CircuitViewport/TopologyOverlay

**Verification:** Override persists across page reloads (stored on disk).

---

### Task 10: Visual indicators for edited connections

**Objective:** Show which connections have been manually overridden.

**Files:**
- Modify: `ui/src/components/TopologyOverlay.tsx`

**Indicators:**
- Reassigned endpoints: small yellow diamond marker
- Joined endpoints: matching colored rings around endpoint dots
- Disconnected endpoints: dashed wire, grey endpoint dot
- Override count badge on the topology controls bar

**Verification:** Visual distinction between auto-joined and manually overridden connections.

---

### Task 11: Reset overrides

**Objective:** Button to clear all overrides for the current image.

**Files:**
- Modify: `ui/src/components/TopologyOverlay.tsx`

**UI:**
- "Reset" button in the controls bar (only visible when overrides exist)
- Click → calls `clearOverridesAction` → refetches topology
- Confirmation dialog for destructive action

**Verification:** Click reset → all connections revert to auto-joined state.

---

### Task 12: Commit and deploy

```bash
git add -A && git commit -m "feat: connection editor — manual wire endpoint overrides"
docker compose down && docker compose up --build -d
```

**Manual verification:**
1. Navigate to `?idx=117`, click "Topology"
2. Click a wire endpoint → edit panel appears
3. Reassign endpoint to different pin → overlay updates, connection changes
4. Join two endpoints → they merge into one node
5. Disconnect an endpoint → it floats
6. Refresh page → overrides persist
7. Click "Reset" → connections revert to auto-joined

---

## Key Design Decisions

1. **Overrides stored on disk** (not in browser state) — persists across sessions, works for multiple users
2. **Applied after auto-join** — overrides modify the join result, not replace it. If the pipeline is re-run with different params, overrides still apply on top.
3. **Endpoint key format** — `wire_{idx}_ep{1|2}` is stable (wire index doesn't change between runs for same image)
4. **Join merges nodes** — doesn't create new connections, just merges existing nodes that the endpoints belong to
5. **Remove creates floating endpoints** — wire still exists but endpoint has no node assignment

## Critical Pitfalls

- **Override application order matters** — reassign first (may create new nodes), then remove, then join (merges existing nodes)
- **Wire index stability** — wire indices come from the pipeline's line detection order. If pipeline params change, indices may shift. Overrides should be validated against current wire indices on load.
- **Join can create cycles** — merging nodes that are already connected via other paths. The netlist builder must handle this gracefully.
- **SPICE impact** — overrides change the netlist, which changes simulation results. Current/voltage overlays should reflect overridden connections.

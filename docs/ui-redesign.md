# UI Redesign: Circuit-Centric Architecture

## Design Philosophy

**The circuit is the product.** Every other view (detection, joining, simulation) is a lens into how the circuit was built. The UI should feel like an interactive circuit editor, not a pipeline debugger.

**Three principles:**
1. **Show the result first** — the digitized circuit (components + values + connections) is always visible
2. **Layers, not tabs** — pipeline stages are overlays you toggle, not separate pages
3. **Edit in place** — component values are editable directly on the circuit; simulation updates live

---

## Layout Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  TOOLBAR                                                        │
│  [◀ 1/134 ▶]  [GT Labels ▾]  [Best v4 ▾]  [Pipeline ▾]        │
│                         [Circuit ▾]  [Simulate ▾]               │
├───────────────┬─────────────────────────────────────────────────┤
│               │                                                 │
│   SIDEBAR     │              MAIN VIEWPORT                      │
│   (280px)     │                                                 │
│               │   ┌─────────────────────────────────────┐      │
│   ┌─────────┐ │   │                                     │      │
│   │Params   │ │   │   CIRCUIT GRAPH (React Flow)        │      │
│   │Sliders  │ │   │   - Components as nodes             │      │
│   │         │ │   │   - Connections as edges            │      │
│   │         │ │   │   - Values displayed on nodes       │      │
│   │         │ │   │   - Click node → edit value         │      │
│   │         │ │   │   - Voltage map overlay             │      │
│   │         │ │   │   - Join overlay overlay            │      │
│   └─────────┘ │   │                                     │      │
│               │   └─────────────────────────────────────┘      │
│   ┌─────────┐ │                                                 │
│   │Components│ │   ┌─────────────────────────────────────┐      │
│   │List      │ │   │  BOTTOM PANEL (collapsible)         │      │
│   │+ values  │ │   │  - SPICE netlist (syntax highlighted)│     │
│   │         │ │   │  - Component table (sortable)        │      │
│   │         │ │   │  - Warnings / errors                 │      │
│   └─────────┘ │   └─────────────────────────────────────┘      │
│               │                                                 │
└───────────────┴─────────────────────────────────────────────────┘
```

---

## Toolbar (Top Bar)

Fixed header. Always visible.

| Element | Type | Behavior |
|---------|------|----------|
| Image nav | `◀ 1/134 ▶` | Previous/next image. Shows current index + total |
| Dataset | `GT Labels ▾` | Dropdown: GT Labels (153), HDC (3986), Synthetic (50) |
| Pipeline preset | `Best v4 ▾` | Dropdown: all presets from `/api/presets` |
| Pipeline overlay | `Pipeline ▾` | Toggle: None / Source / Threshold / Detected Lines / Dilated |
| Circuit overlay | `Circuit ▾` | Toggle: Components / Connections / Values / All |
| Simulation overlay | `Simulate ▾` | Toggle: None / Voltage Map / Current Flow |

**Key behavior:** Pipeline/Circuit/Simulate are independent overlays that stack. You can see "Detected Lines + Voltage Map + Component Values" simultaneously.

---

## Sidebar (Left Panel, 280px wide)

Two sections, scrollable independently.

### Section 1: Pipeline Parameters

Same sliders as current, but with better labeling:

| Parameter | Slider | Range | Default | Tooltip |
|-----------|--------|-------|---------|---------|
| Sauvola k | `sauvola_k` | 0.1–1.0 | 0.285 | Threshold sensitivity. Lower = more wires detected |
| Window size | `sauvola_window` | 11–151 | 67 | Local window for adaptive threshold |
| Close kernel | `close_kernel` | 1–7 | 3 | Morphological closing (fills gaps in wires) |
| Min area | `ccl_min_area` | 5–100 | 28 | Minimum connected component area (pixels) |
| Dedup angle | `dedup_angle` | 5–30 | 12 | Max angle difference to merge duplicate lines |
| Dedup dist | `dedup_dist` | 5–30 | 8 | Max distance to merge duplicate lines |
| Anchor endpoint | `anchor_endpoint_dist` | 5–25 | 12 | Max distance from wire end to component |
| Anchor link | `anchor_link_dist` | 5–20 | 8 | Max distance from wire body to component |

**Behavior:**
- Slider change → debounce 300ms → re-run pipeline → update circuit view
- "Reset to defaults" button
- Show current values as labels next to sliders

### Section 2: Component List

Scrollable list of all detected components. Each row shows:

```
┌──────────────────────────────────────┐
│ 🔵 R1    resistor    [10kΩ]  ▾     │
│ 🔴 C1    capacitor   [100nF] ▾     │
│ 🟢 L1    inductor    [10mH]  ▾     │
│ ⚫ J1    junction    —       ▾     │
│ ⚪ T1    terminal    —       ▾     │
└──────────────────────────────────────┘
```

- Colored dot = component type color (matches circuit graph)
- Name = component reference (R1, C1, etc.)
- Type = component class name
- Value = editable inline (click to edit)
- `▾` = expand to see pin details

**Click a component** → highlights it in the circuit graph, shows its connections.

**Edit value** → inline text input → press Enter → updates SPICE netlist → re-run simulation if auto-simulate is on.

---

## Main Viewport (Center)

### Default View: Interactive Circuit Graph

The React Flow graph is the primary view. Components are nodes, connections are edges.

**Node design (updated):**
```
    ┌─────────┐
    │  R1     │  ← component name
    │  10kΩ   │  ← value (editable)
    └─────────┘
```

- Circle with component type color
- Name inside (bold)
- Value below name (lighter, clickable to edit)
- Selected node: pulsing glow + connected edges highlighted
- Hover: tooltip with full details (type, pins, node membership)

**Edge design:**
- Straight lines between connected components
- Color: black for normal, blue for selected, red for over-joined
- Thickness: 1.5px normal, 2.5px selected

**Interaction:**
- **Click node** → select, show in component list, highlight connections
- **Double-click node** → open value editor inline
- **Mouse wheel** → zoom (0.3x – 3x)
- **Drag background** → pan
- **Drag node** → reposition (layout stays manual)

**Scale slider** in bottom-right corner of viewport (0.3x – 3.0x) for adjusting node size.

### Overlay Modes (stackable)

Each overlay is a semi-transparent layer on top of the circuit graph:

**Pipeline overlay:**
- Shows the detection pipeline output as a background image
- Opacity slider: 0% (transparent) – 100% (fully obscures circuit)
- Useful for checking "did the detector find the right wires?"

**Join overlay:**
- Color-coded wires: cyan = wire, green = good join, orange = over-join
- Strategy dropdown: production / graph_rescue / nearest2_30 / etc.
- Shows net boundaries as colored regions

**Voltage map overlay:**
- Heatmap on the circuit: blue = 0V, red = 5V
- Auto-runs DC simulation when toggled on
- Shows voltage values at each node

---

## Bottom Panel (Collapsible)

Three tabs within the bottom panel (not page-level tabs):

| Tab | Content |
|-----|---------|
| **Netlist** | SPICE code (syntax highlighted, copy button), component table (sortable by name/type/node), node connectivity table |
| **Warnings** | Structural errors (self-loops, floating components, giant nets), join quality metrics |
| **Raw** | JSON view of pipeline result (for debugging) |

**Default:** Netlist tab, collapsed to 200px. Drag to expand. Double-click header to toggle full/collapsed.

---

## User Flows

### Flow 1: Inspect a circuit

1. Select image from grid (or use arrow keys)
2. Circuit graph loads with components + connections
3. Click a component → see its connections highlighted
4. Edit its value in the component list
5. Toggle "Simulate → Voltage Map" → see voltage distribution

### Flow 2: Tune detection parameters

1. Adjust slider (e.g., Sauvola k from 0.285 to 0.25)
2. After 300ms debounce, pipeline re-runs
3. Circuit graph updates with new detections
4. Toggle "Pipeline → Detected Lines" to see what changed
5. Component list updates (more/fewer components)
6. If auto-simulate is on, voltage map updates too

### Flow 3: Verify joins

1. Toggle "Circuit → Connections" to see all edges
2. Toggle "Simulate → Join Overlay" to see join quality
3. Use strategy dropdown to compare: graph_rescue vs production
4. Click a component to see which net it belongs to
5. Check "Warnings" tab for self-loops and floating components

### Flow 4: Edit component values for simulation

1. Click component in circuit graph or component list
2. Type new value (e.g., "4.7k" for resistor)
3. Press Enter → value updates everywhere
4. SPICE netlist auto-updates
5. If auto-simulate is on, voltage map recalculates
6. See new voltage distribution

### Flow 5: Export SPICE netlist

1. Click "Bottom Panel" to expand
2. Click "Netlist" tab
3. See SPICE code with syntax highlighting
4. Click "Copy" button
5. Paste into ngspice, LTspice, etc.

---

## State Management

### Global State (Zustand or React Context)

```typescript
interface AppState {
  // Image
  imageIdx: number;
  dataset: string;
  imageList: string[];
  
  // Pipeline
  preset: string;
  params: Record<string, number>;
  pipelineResult: PipelineResult | null;
  
  // Circuit
  netlist: NetlistResult | null;
  selectedComponent: string | null;
  componentValues: Record<string, string>;  // user-edited values
  
  // Overlays
  pipelineOverlay: 'none' | 'source' | 'threshold' | 'detected' | 'dilated';
  circuitOverlay: 'none' | 'components' | 'connections' | 'values' | 'all';
  simOverlay: 'none' | 'voltage' | 'current';
  joinStrategy: string;
  
  // UI
  sidebarOpen: boolean;
  bottomPanelOpen: boolean;
  bottomPanelTab: 'netlist' | 'warnings' | 'raw';
}
```

### Data Flow

```
User adjusts slider
  → usePipeline hook (debounced 300ms)
  → POST /api/process
  → PipelineResult (overlay images, wire count)
  → POST /api/netlist
  → NetlistResult (components, nodes, SPICE)
  → Update circuit graph
  → If auto-simulate: POST /api/simulate
  → VoltageMap result
  → Update voltage overlay
```

### API Endpoints (existing)

| Endpoint | Method | Used For |
|----------|--------|----------|
| `/api/list?ds=X` | GET | Image list |
| `/api/thumb?idx=N&ds=X` | GET | Thumbnail |
| `/api/presets` | GET | Pipeline presets |
| `/api/datasets` | GET | Dataset info |
| `/api/process` | POST | Run detection pipeline |
| `/api/netlist` | POST | Build netlist + SPICE |
| `/api/join_overlay` | POST | Join verification overlay |
| `/api/sim_overlay` | POST | Voltage map overlay |
| `/api/join_strategies` | GET | Available join strategies |
| `/api/simulate` | POST | DC operating point |
| `/api/ocr` | POST | Component value OCR (new) |

---

## File Structure (Proposed)

```
ui/src/
├── app/
│   ├── page.tsx              # Server: fetch initial data
│   ├── HomeClient.tsx        # Root layout, state provider
│   ├── actions.ts            # Server actions (API proxy)
│   └── globals.css           # Global styles
├── components/
│   ├── Toolbar.tsx           # Top bar: image nav, dataset, overlays
│   ├── Sidebar.tsx           # Left panel: params + component list
│   ├── ParamSliders.tsx      # Pipeline parameter controls
│   ├── ComponentList.tsx     # Component list with editable values
│   ├── CircuitViewport.tsx   # Main area: circuit graph + overlays
│   ├── CircuitGraph.tsx      # React Flow graph (existing, modified)
│   ├── CircuitNode.tsx       # Custom node (existing, modified)
│   ├── BottomPanel.tsx       # Collapsible bottom panel
│   ├── NetlistTab.tsx        # SPICE code + tables (from NetlistPanel)
│   ├── WarningsTab.tsx       # Structural errors + metrics
│   ├── OverlayControls.tsx   # Overlay toggles + opacity
│   ├── ZoomableImage.tsx     # Zoom/pan for overlay images (existing)
│   ├── ValueEditor.tsx       # Inline component value editor
│   └── JoinCheckPanel.tsx    # Join verification (existing, refactored)
├── hooks/
│   ├── useImages.ts          # Image list management (existing)
│   ├── usePipeline.ts        # Pipeline execution (existing, debounced)
│   ├── useNetlist.ts         # Netlist fetch + cache (existing)
│   └── useSimulation.ts      # Simulation execution (new)
├── lib/
│   ├── panels.ts             # Panel constants (existing)
│   ├── types.ts              # TypeScript interfaces (existing)
│   └── api.ts                # API utility (existing)
└── stores/
    └── appStore.ts           # Zustand global state (new)
```

---

## Implementation Phases

### Phase 1: Foundation (no visual changes yet)
- [ ] Create `appStore.ts` with Zustand
- [ ] Create `Toolbar.tsx` (replaces old header)
- [ ] Create `Sidebar.tsx` wrapper
- [ ] Create `CircuitViewport.tsx` wrapper
- [ ] Create `BottomPanel.tsx` wrapper
- [ ] Wire up state management
- [ ] **Agent checkpoint:** All existing functionality still works

### Phase 2: Circuit as Primary View
- [ ] Move `CircuitGraph` into `CircuitViewport`
- [ ] Circuit graph is default view (not 4-panel grid)
- [ ] Add component values to node display
- [ ] Add inline value editing on nodes
- [ ] Add component selection → highlight connections
- [ ] Add `ComponentList` with editable values
- [ ] **Agent checkpoint:** Circuit graph is primary, values editable

### Phase 3: Overlay System
- [ ] Create `OverlayControls.tsx` (toggle buttons + opacity)
- [ ] Pipeline overlay: detection images as background
- [ ] Join overlay: color-coded wires
- [ ] Voltage map overlay: heatmap
- [ ] Multiple overlays can stack
- [ ] **Agent checkpoint:** Overlays toggle on/off

### Phase 4: Parameter Tuning
- [ ] Move sliders to `ParamSliders.tsx` in sidebar
- [ ] Debounced pipeline re-run on slider change
- [ ] Circuit graph updates in real-time
- [ ] Component list updates with new detections
- [ ] **Agent checkpoint:** Sliders affect circuit live

### Phase 5: Simulation Integration
- [ ] Create `useSimulation` hook
- [ ] Auto-run simulation when overlay toggled on
- [ ] Voltage values on nodes
- [ ] Editable component values → re-simulate
- [ ] SPICE netlist auto-updates
- [ ] **Agent checkpoint:** Simulation works end-to-end

### Phase 6: Bottom Panel
- [ ] Collapsible panel with tabs
- [ ] Netlist tab: SPICE code + tables
- [ ] Warnings tab: structural errors
- [ ] Raw tab: JSON debug view
- [ ] **Agent checkpoint:** All info accessible

---

## Agent Handoff Checklist

When an agent picks up this work, it should:

1. **Read this file first** — `docs/ui-redesign.md`
2. **Check current phase** — look at which Phase items are checked
3. **Run the app** — `docker compose up -d` → http://localhost:4200
4. **Check git log** — `git log --oneline -5` for recent changes
5. **Run tests** — `cd ui && npx tsc --noEmit` for type checking
6. **Verify last checkpoint** — each phase has an "Agent checkpoint" step

**State file:** `docs/ui-redesign-state.json`
```json
{
  "currentPhase": 2,
  "completedPhases": [1],
  "lastCheckpoint": "Circuit graph is primary, values editable",
  "knownIssues": ["Overlay opacity not wired yet"],
  "nextStep": "Phase 3: Overlay System"
}
```

---

## Design Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| Jun 2026 | Circuit graph as primary view | The circuit IS the product; pipeline is a means to an end |
| Jun 2026 | Overlays instead of tabs | Users need to see multiple layers simultaneously |
| Jun 2026 | Inline value editing | Reduces clicks; edit in context, not in a modal |
| Jun 2026 | Debounced pipeline (300ms) | Prevents API spam during slider drag |
| Jun 2026 | Zustand for state | Lightweight, no boilerplate, works with React 19 |

---

## Open Questions

1. **Auto-simulate:** Should simulation run automatically when values change, or require explicit "Run" button? (Proposal: auto-run with 500ms debounce)
2. **Component positioning:** Keep fixed image-coordinate layout, or allow user repositioning? (Proposal: fixed by default, drag to reposition)
3. **Undo/redo:** Should value edits be undoable? (Proposal: yes, for simulation; not for pipeline params)
4. **Export:** Should we support exporting as KiCad, Eagle, or just SPICE? (Proposal: SPICE only for now)

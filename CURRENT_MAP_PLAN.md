# Current Map Feature — Implementation Plan

## Goal
Add a "Current" map overlay alongside the existing "Voltage" map. When the user clicks "Current" in the View bar, the schematic is overlaid with a heatmap showing current magnitude through each component and its connecting wires.

## Architecture (mirrors the voltage map pattern exactly)

### Data Flow
```
User clicks "Current" → fetchCurrentOverlayAction → /api/current_overlay
→ Backend: pipeline → join → SPICE → ngspice DC op → compute per-component I
→ Generate overlay image (components + wires colored by current) → return base64
→ Frontend displays overlay
```

### Current Computation (Ohm's Law)
The DC operating point gives us node voltages for every net. Combined with component values and pin connectivity, we compute current through each 2-terminal component:
- **Resistors (R):** I = |V_anode - V_cathode| / R
- **Capacitors (C):** In DC steady state, I ≈ 0 (show as grey/zero)
- **Inductors (L):** In DC steady state, I = |V_anode - V_cathode| / R_series (use small series R ≈ 0.01Ω if no series resistance → high current)
- **Diodes (D):** Use branch current from ngspice if available, else estimate from voltage drop
- **Voltage sources (V):** Use branch current directly from ngspice `#branch` data
- **Other (Q, etc.):** Grey (no simple calculation)

Wires inherit the max current of the components they connect to.

---

## Files to Create/Modify

### 1. Backend: `wire_detection/api/routes/current_overlay.py` (NEW)
- New FastAPI router with `POST /api/current_overlay`
- Reuses the same pipeline/join/SPICE flow as `sim_overlay.py`
- Computes per-component currents from node voltages + component values
- Generates a colored overlay: components drawn as filled rectangles, wires as colored lines
- Colormap: `cv2.COLORMAP_HOT` (black→red→yellow→white for 0→max current)
- Returns: `{ overlay: base64, available: bool, component_currents: [...], imin: float, imax: float, warnings: [...], spice_netlist: str }`

### 2. Backend: `wire_detection/api/models.py` (MODIFY)
- Add `CurrentOverlayRequest` — same fields as `SimOverlayRequest` (can just reuse it)

### 3. Backend: `wire_detection/api/server.py` (MODIFY)
- Register the new `current_overlay` router

### 4. Frontend: `ui/src/lib/types.ts` (MODIFY)
- Add `CurrentOverlayResult` interface:
  ```ts
  interface CurrentOverlayResult {
    overlay: string;           // base64 PNG
    available: boolean;
    component_currents: Array<{ name: string; current: number }>;
    imin?: number;
    imax?: number;
    warnings: string[];
    spice_netlist?: string;
  }
  ```

### 5. Frontend: `ui/src/app/actions.ts` (MODIFY)
- Add `fetchCurrentOverlayAction()` server action — POST to `/api/current_overlay`

### 6. Frontend: `ui/src/components/OverlayControls.tsx` (MODIFY)
- Add `{ id: "current", label: "Current" }` to the Simulation group items (next to Voltage)
- Both Voltage and Current share the same `hasPipelineResult` disabled state

### 7. Frontend: `ui/src/components/CircuitViewport.tsx` (MODIFY)
- Add `currentOverlayUrl` prop
- In `getOverlayUrl()`: add case `if (type === "current") return currentOverlayUrl ?? null`

### 8. Frontend: `ui/src/app/HomeClient.tsx` (MODIFY)
- Add `currentOverlayUrl` state
- Add `currentActive` state (boolean)
- Update `handleOverlayChange` to set `currentActive = overlay === "current"`
- Add useEffect that calls `fetchCurrentOverlayAction` when `currentActive` is true
- Pass `currentOverlayUrl` to CircuitViewport
- Pass `currentActive` to the simulation hook or handle independently

### 9. Frontend: `ui/src/hooks/useCurrentSimulation.ts` (NEW, optional)
- Could reuse `useSimulation` pattern but for current map
- OR just inline the fetch in HomeClient (simpler, matches how voltage overlay works with `handleRunSimOverlay`)

---

## Key Design Decisions

1. **Separate endpoint** (`/api/current_overlay`) rather than adding a `mode` param to `/api/sim_overlay` — cleaner separation, voltage overlay image generation doesn't need to change.

2. **Capacitors show ~0 current** in DC analysis — this is physically correct. The overlay will show them as grey/dim. If the user wants to see AC currents, that's a future feature.

3. **Wires colored by max connected component current** — a wire connecting R1 (5mA) and R2 (2mA) shows 5mA. This gives a visually intuitive "current flow" picture.

4. **Hot colormap** (black→red→yellow→white) — distinct from the jet colormap used for voltage, so users can immediately tell which mode they're in.

5. **Component current labels** — show "5.0mA" text on each component with significant current (>1% of max), similar to voltage labels.

---

## Verification Checklist
1. `npx tsc --noEmit` — TypeScript compiles
2. `docker compose down && docker compose up --build` — containers rebuild
3. Load UI → click "Current" → overlay appears with colored components
4. Click "Voltage" → voltage overlay still works (no regression)
5. Adjust component values → current map updates
6. Components without SPICE models show grey

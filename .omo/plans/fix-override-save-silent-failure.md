# Fix: Override Save Silent Failure

## Problem

When a user makes manual wire-connection edits (reassign/join/disconnect) via the Connection Editor in the Topology view, the overrides appear in the UI but:

1. **Never persist to disk** — `wire_detection/overrides/{ds}/{idx}.json` is never created
2. **Netlist/simulation don't reflect the edits** — they load overrides from disk, which is empty
3. **The UI lies** — the Connection Editor shows the override as if it was saved

### Root Cause

In `HomeClient.tsx`, the `handleReassign` (and `handleJoin`, `handleDisconnect`) callbacks **optimistically update React state** before the backend confirms the save:

```typescript
// Current (broken):
const handleReassign = useCallback(async (...) => {
  try {
    const updatedTopology = await saveOverridesAction(...);
    setOverrides(newOverrides);  // ← updates state even if backend returned error
    setTopology(updatedTopology);
  } catch (e) {
    console.error("Reassign failed:", e);  // ← only logs, user never sees this
  }
}, [...]);
```

The backend `POST /api/topology/overrides` validates the override keys against the current topology. If validation fails (e.g. wire index mismatch due to preset differences), it returns a 400 error — but the frontend treats the response as success and updates state anyway.

### Secondary Issue

The `save_override` endpoint in `topology.py` hardcodes `preset="best_candidate_v4"` when rebuilding topology for validation, but the user may be viewing a different preset. Wire indices can shift between presets, causing validation to fail for legitimate overrides.

---

## Plan

### Step 1: Fix `HomeClient.tsx` — Don't Update State on Failed Saves

**File**: `ui/src/app/HomeClient.tsx`

Modify `handleReassign`, `handleJoin`, `handleDisconnect`, and `handleUpdateOverrides` to **check the response for errors** before updating state.

**Before** (all three handlers follow this pattern):
```typescript
const updatedTopology = await saveOverridesAction(...);
setOverrides(newOverrides);
setTopology(updatedTopology);
```

**After**:
```typescript
const result = await saveOverridesAction(...);
if (result && 'error' in result) {
  // Backend rejected the override — don't update local state
  console.error("Override save failed:", result.error);
  return;
}
setOverrides(newOverrides);
setTopology(result);
```

**Also**: Surface the error to the user via a toast/notification instead of silently logging to console. The codebase already has an `ocrStatus` toast pattern — reuse that pattern for override errors.

Add a new state variable:
```typescript
const [overrideError, setOverrideError] = useState<string | null>(null);
```

And display it as a toast (similar to `ocrStatus`).

### Step 2: Fix Backend Error Response Shape

**File**: `wire_detection/api/routes/topology.py`

The `save_override` endpoint currently returns `JSONResponse({"error": ...}, status_code=400)` on validation failure. The frontend needs to distinguish this from a successful topology response.

**Current return on success**: `JSONResponse(updated_topo_dict)` — a flat dict with keys `wires`, `pins`, `components`, `nodes`, `warnings`.

**Current return on error**: `JSONResponse({"error": "..."}, status_code=400)`

The frontend check `if (result && 'error' in result)` will work because the success response doesn't have an `error` key. But verify this is consistent — the `_build_topology_data` function can return `{"error": "index out of range"}` which also has an `error` key. Need to ensure the frontend handles both 400 errors and 200-with-error-key.

**Change**: Make the error responses use HTTP 400 consistently, and have the frontend check `response.ok` before parsing:

```typescript
// In saveOverridesAction or the callers:
const res = await fetch("/api/topology/overrides", { ... });
if (!res.ok) {
  const body = await res.json();
  throw new Error(body.error || "Failed to save override");
}
const topology = await res.json();
```

This is cleaner than checking for `error` key in the response body.

### Step 3: Fix Preset Mismatch in Validation

**File**: `wire_detection/api/routes/topology.py`

The `save_override` endpoint hardcodes `preset="best_candidate_v4"`:
```python
topo = _build_topology_data(
    img_idx=data.img_idx,
    ds=data.dataset,
    preset="best_candidate_v4",  # ← hardcoded
)
```

But the user might be on a different preset. Wire indices are detection-dependent — different presets produce different wire sets.

**Fix**: Accept `preset` in `OverrideRequest` and use it for validation:

```python
class OverrideRequest(BaseModel):
    dataset: str = "gt_labels"
    img_idx: int
    overrides: dict
    preset: str = "best_candidate_v4"  # ← add with default
```

Then in `save_override`:
```python
topo = _build_topology_data(
    img_idx=data.img_idx,
    ds=data.dataset,
    preset=data.preset,  # ← use request preset
)
```

And update the frontend `saveOverridesAction` to pass the current preset:
```typescript
export async function saveOverridesAction(
  idx: number, ds: string, overrides: ConnectionOverrides, preset: string
): Promise<TopologyResult> {
  return fetchBackend("/api/topology/overrides", {
    method: "POST",
    body: JSON.stringify({ dataset: ds, img_idx: idx, overrides, preset }),
  });
}
```

Update all callers in `HomeClient.tsx` to pass `pipe.preset`.

### Step 4: Fix `_build_topology_data` Return Shape Consistency

**File**: `wire_detection/api/routes/topology.py`

The `_build_topology_data` function returns `{"error": "..."}` on failure, which is a valid topology-like dict. The `save_override` endpoint checks this:

```python
if "error" in topo:
    return JSONResponse({"error": topo["error"]}, status_code=404)
```

This is fine — the 404 distinguishes it from a successful response. No change needed here, but worth noting for the frontend fix.

### Step 5: JSON Import/Export for Overrides

Add copy/paste support so users can export overrides as JSON and import them on other images or sessions.

#### Standard Notation

The JSON format matches the existing `ConnectionOverrides` type exactly:

```json
{
  "reassign": {
    "wire_1_ep2": { "component": "J3", "pin": "pin0" },
    "wire_6_ep2": { "component": "J9", "pin": "pin0" },
    "wire_2_ep2": { "component": "J9", "pin": "pin0" },
    "wire_5_ep1": { "component": "X10", "pin": "pin1" },
    "wire_5_ep2": { "component": "J6", "pin": "pin0" },
    "wire_4_ep1": { "component": "J6", "pin": "pin0" },
    "wire_3_ep2": { "component": "J2", "pin": "pin0" }
  },
  "join": [],
  "remove": []
}
```

**Rules**:
- Keys in `reassign` are `wire_{idx}_ep{1|2}` — the wire endpoint identifier
- Values are `{ "component": "<SPICE name>", "pin": "<pin_name>" }` — the target
- `join` is a list of 2-element arrays: `[["wire_1_ep2", "wire_3_ep1"]]`
- `remove` is a list of endpoint keys to disconnect: `["wire_5_ep2"]`
- All three keys (`reassign`, `join`, `remove`) are always present (empty if no edits)

#### UI Changes

**File**: `ui/src/components/ConnectionEditorPanel.tsx`

Add two buttons to the Connection Editor header bar (next to the existing Reset button):

1. **Copy** button — copies current overrides as formatted JSON to clipboard
2. **Import** button — opens a small textarea/modal where the user can paste JSON, validates it, and applies it

**Copy button**:
```typescript
const handleCopyOverrides = useCallback(() => {
  const json = JSON.stringify(overrides, null, 2);
  navigator.clipboard.writeText(json).then(() => {
    // show "Copied!" feedback
  });
}, [overrides]);
```

**Import button**:
- Shows a textarea pre-filled with the current overrides JSON (or empty if none)
- User edits/pastes JSON
- On "Apply": parse JSON → validate structure (must have `reassign`, `join`, `remove` keys with correct types) → call `onUpdateOverrides(parsed)`
- Validation is client-side only (the backend re-validates on save)
- Show parse errors inline if JSON is malformed

**Layout in the editor header**:
```
[Connection editor]              [Reset 3] [Copy] [Import] [–]
```

When there are no overrides, Copy exports `{ "reassign": {}, "join": [], "remove": [] }` and Import is still available (to paste from a previous session).

#### File: `ui/src/components/ConnectionEditorPanel.tsx`

Add to the `Props` interface:
```typescript
onUpdateOverrides: (next: ConnectionOverrides) => void;  // already exists
```

Add state:
```typescript
const [importOpen, setImportOpen] = useState(false);
const [importText, setImportText] = useState("");
const [importError, setImportError] = useState<string | null>(null);
```

Add import validation:
```typescript
function parseOverrides(text: string): { ok: true; data: ConnectionOverrides } | { ok: false; error: string } {
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed !== "object" || parsed === null) return { ok: false, error: "Expected a JSON object" };
    if (!("reassign" in parsed) || !("join" in parsed) || !("remove" in parsed))
      return { ok: false, error: "Missing required keys: reassign, join, remove" };
    if (typeof parsed.reassign !== "object") return { ok: false, error: "'reassign' must be an object" };
    if (!Array.isArray(parsed.join)) return { ok: false, error: "'join' must be an array" };
    if (!Array.isArray(parsed.remove)) return { ok: false, error: "'remove' must be an array" };
    return { ok: true, data: parsed as ConnectionOverrides };
  } catch (e) {
    return { ok: false, error: `Invalid JSON: ${e instanceof Error ? e.message : e}` };
  }
}
```

---

## Files to Modify

| File | Change |
|------|--------|
| `ui/src/app/HomeClient.tsx` | Check response before updating state; add error toast for failed overrides |
| `ui/src/app/actions.ts` | Update `saveOverridesAction` signature to accept `preset`; use `res.ok` check |
| `wire_detection/api/models.py` | Add `preset` field to `OverrideRequest` |
| `wire_detection/api/routes/topology.py` | Use `data.preset` instead of hardcoded string in `save_override` |
| `ui/src/components/ConnectionEditorPanel.tsx` | Add Copy/Import buttons with JSON import modal |

---

## Verification

1. **Manual test**: Open image idx=39, make a reassign override → check that `wire_detection/overrides/gt_labels/39.json` is created on disk
2. **Reload test**: After saving, reload the page → verify the override persists in the Connection Editor
3. **Simulation test**: After saving, check that the Netlist tab and Simulation reflect the new connections
4. **Error test**: Try to reassign to a non-existent component → verify an error toast appears (not silent failure)
5. **Preset test**: Switch to a different preset, make an override → verify it saves and validates correctly
6. **Copy test**: Make overrides → click Copy → paste into a text editor → verify valid JSON with correct structure
7. **Import test**: Copy JSON from one image → navigate to another image → click Import → paste → verify overrides appear and save correctly
8. **Import error test**: Paste malformed JSON → verify inline error message (no crash)
9. **Round-trip test**: Make overrides on image A → Copy → navigate to image B → Import → Save → reload image B → verify overrides persist

---

## Scope

- **In scope**: Frontend error handling, backend preset parameter, save persistence, JSON import/export
- **Out of scope**: Changing the override data model, modifying the join strategy logic, fixing detection pipeline

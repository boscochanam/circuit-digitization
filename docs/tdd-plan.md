# Circuit Digitization — TDD Implementation Plan

## Current State

**Backend**: 95 Python files, 31 benchmark scripts, 9 test files  
**Frontend**: 15 TS/TSX files, 0 test files  
**Test coverage**: Minimal — only pipeline stages and benchmark harness tested

---

## Phase 1: Test Existing Functionality (RED → GREEN)

### 1.1 Backend API Tests (`tests/test_api.py`)

```python
# Test cases for wire_detection/api/server.py

def test_list_presets_returns_all_presets()
def test_list_presets_contains_best_candidate_v4()
def test_list_presets_legacy_has_no_params()
def test_list_presets_non_legacy_has_params()

def test_list_images_returns_array()
def test_list_images_gt_labels_has_images()
def test_list_images_invalid_dataset_returns_empty()

def test_get_thumb_returns_jpeg()
def test_get_thumb_invalid_index_returns_404()

def test_datasets_returns_dict()
def test_datasets_has_gt_labels_key()

def test_process_legacy_threshold_returns_overlay()
def test_process_legacy_threshold_returns_threshold()
def test_process_legacy_threshold_returns_line_count()

def test_process_preset_returns_overlay()
def test_process_preset_returns_threshold()
def test_process_preset_returns_dilated()
def test_process_preset_returns_params()
def test_process_preset_invalid_returns_400()
def test_process_preset_out_of_range_returns_404()
```

### 1.2 Benchmark Utility Tests (`tests/test_benchmark_utils.py`)

```python
# Test cases for shared benchmark utilities

def test_point_to_bbox_dist_inside_returns_zero()
def test_point_to_bbox_dist_outside_returns_correct_distance()
def test_point_to_bbox_dist_on_edge_returns_zero()

def test_point_in_polygon_inside()
def test_point_in_polygon_outside()
def test_point_in_polygon_on_edge()

def test_point_to_polygon_dist_inside_returns_zero()
def test_point_to_polygon_dist_outside()

def test_load_ground_truth_returns_tuples()
def test_load_ground_truth_coordinate_range()

def test_parse_components_returns_tuples()
def test_parse_components_has_bbox()
def test_parse_components_has_vertices()

def test_find_hdc_label_prefix_matching()
def test_find_hdc_label_no_match_returns_none()

def test_build_component_mask_fills_polygons()
def test_crop_to_roi_returns_offset()
def test_shift_components_adjusts_coordinates()
```

### 1.3 Wire-to-Component Mapping Tests (`tests/test_mapping.py`)

```python
# Test cases for mapping methods

def test_map_baseline_nearest_component()
def test_map_baseline_equidistant_picks_first()
def test_map_baseline_far_endpoint_returns_minus_one()

def test_selective_disambiguate_two_terminal_reassigns()
def test_selective_disambiguate_multi_terminal_keeps()
def test_selective_disambiguate_inside_polygon_keeps()
def test_selective_disambiguate_threshold_respected()

def test_point_in_polygon_inside()
def test_point_in_polygon_outside()
def test_point_in_polygon_on_vertex()

def test_is_two_terminal_resistor()
def test_is_two_terminal_capacitor()
def test_is_two_terminal_diode()
def test_is_multi_terminal_transistor()
def test_is_multi_terminal_ic()
```

### 1.4 Netlist Extraction Tests (`tests/test_netlist.py`)

```python
# Test cases for netlist building

def test_build_netlist_two_resistors_in_series()
def test_build_netlist_three_components_parallel()
def test_build_netlist_empty_wires()
def test_build_netlist_no_components()

def test_netlist_node_merging()
def test_netlist_pin_to_node_mapping()
def test_netlist_isolated_pins()

def test_validate_netlist_floating_nodes()
def test_validate_netlist_large_nodes()
def test_validate_netlist_valid_circuit()

def test_spice_generation_resistor()
def test_spice_generation_capacitor()
def test_spice_generation_voltage_source()
def test_spice_generation_ground_node()
def test_spice_generation_node_naming()
```

### 1.5 Frontend API Tests (`ui/src/__tests__/api.test.ts`)

```typescript
// Test cases for UI API layer

describe('apiUrl', () => {
  it('returns same-origin path in browser')
  it('returns direct URL for SSR')
  it('handles leading slash')
  it('handles no leading slash')
})

describe('listImages', () => {
  it('returns array of strings')
  it('throws on non-array response')
  it('throws on non-OK status')
})

describe('runPipeline', () => {
  it('sends correct body format')
  it('returns line_count')
  it('returns overlay base64')
  it('throws on error response')
})
```

### 1.6 Frontend Component Tests (`ui/src/__tests__/HomeClient.test.tsx`)

```typescript
// Test cases for main UI component

describe('HomeClient', () => {
  it('renders header with title')
  it('renders preset selector')
  it('renders image viewport')
  it('renders panel tabs')
  it('renders metrics bar')
  
  it('loads images on mount')
  it('runs pipeline on image change')
  it('switches panels on tab click')
  it('navigates images with arrows')
  it('opens grid view')
  it('opens bottom sheet on mobile')
  
  it('shows loading state during pipeline')
  it('shows error state on pipeline failure')
  it('shows empty state when no images')
})
```

---

## Phase 2: Code Organization (REFACTOR)

### 2.1 Backend Restructure

**Before:**
```
wire_detection/
├── api/
│   └── server.py          # 438 lines, monolith
├── benchmark/
│   └── 31 scripts          # standalone experiments
└── tests/
    └── 9 test files
```

**After:**
```
wire_detection/
├── api/
│   ├── __init__.py
│   ├── server.py           # FastAPI app setup only
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── presets.py      # /api/presets
│   │   ├── process.py      # /api/process
│   │   ├── datasets.py     # /api/datasets, /api/list
│   │   └── netlist.py      # /api/netlist (NEW)
│   ├── models.py           # Pydantic request/response models
│   └── deps.py             # Shared dependencies (registry, cache)
├── core/
│   ├── __init__.py
│   ├── mapping.py          # Wire-to-component mapping (extracted from benchmark)
│   ├── netlist.py          # Netlist building (extracted from benchmark)
│   └── spice.py            # SPICE generation (NEW)
├── benchmark/
│   └── (unchanged — experiment scripts)
└── tests/
    ├── conftest.py
    ├── test_api.py
    ├── test_mapping.py
    ├── test_netlist.py
    └── test_spice.py
```

**Changes:**
1. Extract `_run_preset_pipeline()` from `server.py` → `routes/process.py`
2. Extract `PRESETS` dict → `routes/presets.py`
3. Extract mapping methods from `benchmark/mapping_phase3.py` → `core/mapping.py`
4. Extract netlist code from `benchmark/netlist_exploration.py` → `core/netlist.py`
5. Add Pydantic models for all API requests/responses
6. Create `deps.py` for shared registry/cache singletons

### 2.2 Frontend Restructure

**Before:**
```
ui/src/
├── app/
│   ├── HomeClient.tsx      # 702 lines, monolith
│   ├── actions.ts          # Server actions
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   └── ui/                 # Unused shadcn components
└── lib/
    ├── api.ts              # Client-side API (duplicate)
    └── backend.ts          # SSR API
```

**After:**
```
ui/src/
├── app/
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── ImageViewport.tsx    # Image display + navigation
│   ├── PanelTabs.tsx        # Panel switching
│   ├── Sidebar.tsx          # Desktop controls
│   ├── BottomSheet.tsx      # Mobile controls
│   ├── MetricsBar.tsx       # Stats display
│   ├── ImageGrid.tsx        # Grid view
│   ├── NetlistPanel.tsx     # NEW: Netlist display
│   └── SimulationPanel.tsx  # NEW: SPICE results
├── hooks/
│   ├── usePipeline.ts       # Pipeline state + fetching
│   └── useImages.ts         # Image list + navigation
├── lib/
│   ├── api.ts               # Single API layer
│   └── types.ts             # Shared types
└── __tests__/
    ├── api.test.ts
    └── HomeClient.test.tsx
```

**Changes:**
1. Extract `HomeClient.tsx` into 6+ components
2. Extract state management into custom hooks
3. Delete `lib/backend.ts` — use single `lib/api.ts`
4. Delete unused `components/ui/` shadcn components
5. Add `NetlistPanel.tsx` and `SimulationPanel.tsx`

### 2.3 Shared Types (`ui/src/lib/types.ts`)

```typescript
export interface PipelineResult {
  line_count: number;
  blob_count: number;
  elapsed_ms: number;
  overlay: string;
  threshold: string;
  dilated: string;
  lines: Array<{ ep1: [number, number]; ep2: [number, number] }>;
  components: Array<{
    class_id: number;
    name: string;
    bbox: [number, number, number, number];
    vertices: Array<[number, number]>;
  }>;
  preset: string;
  params: Record<string, unknown>;
}

export interface NetlistResult {
  nodes: Array<{
    id: number;
    pins: Array<{ component: string; pin: string }>;
  }>;
  components: Array<{
    name: string;
    type: string;
    pins: string[];
  }>;
  connections: Array<{
    from: { component: string; pin: string };
    to: { component: string; pin: string };
    wire_idx: number;
  }>;
  spice_netlist: string;
  warnings: string[];
}
```

---

## Phase 3: SPICE Integration (NEW FEATURE — TDD)

### 3.1 Core Module: `core/spice.py`

**Tests first:**

```python
# tests/test_spice.py

class TestSpiceGenerator:
    def test_resistor_two_terminal(self):
        """R1 node1 node2 1000"""
        
    def test_capacitor_two_terminal(self):
        """C1 node1 node2 1e-6"""
        
    def test_inductor_two_terminal(self):
        """L1 node1 node2 1e-3"""
        
    def test_diode_two_terminal(self):
        """D1 node1 node2 D_default"""
        
    def test_voltage_source(self):
        """V1 node1 node2 DC 5"""
        
    def test_ground_node_is_zero(self):
        """GND maps to node 0"""
        
    def test_node_naming_sequential(self):
        """N1, N2, N3..."""
        
    def test_component_naming_by_type(self):
        """R1, R2, C1, C2, Q1, U1..."""
        
    def test_empty_netlist(self):
        """Returns minimal valid SPICE"""
        
    def test_multiple_resistors_series(self):
        """R1 N1 N2 1k\nR2 N2 N3 2k"""
        
    def test_multiple_resistors_parallel(self):
        """R1 N1 N2 1k\nR2 N1 N2 2k"""

class TestSpiceSimulator:
    def test_dc_operating_point_resistor_divider(self):
        """V=5V, R1=1k, R2=1k → V_mid=2.5V"""
        
    def test_dc_operating_point_open_circuit(self):
        """No current flow, voltages preserved"""
        
    def test_ac_analysis_rc_lowpass(self):
        """R=1k, C=1uF → fc=159Hz"""
        
    def test_parse_dc_output_voltages(self):
        """Parse node voltages from ngspice output"""
        
    def test_parse_dc_output_currents(self):
        """Parse branch currents from ngspice output"""
        
    def test_invalid_netlist_returns_error(self):
        """Missing component, syntax error"""
        
    def test_missing_ground_returns_error(self):
        """No ground node defined"""

class TestNetlistBuilder:
    def test_two_resistors_shared_node(self):
        """R1.pin2 connects to R2.pin1 → same node"""
        
    def test_three_way_junction(self):
        """3 wires meeting at same point → same node"""
        
    def test_component_value_extraction(self):
        """Default values for unknown components"""
        
    def test_pin_assignment_resistor(self):
        """pin1, pin2"""
        
    def test_pin_assignment_transistor(self):
        """B, C, E"""
        
    def test_pin_assignment_ic(self):
        """pin1, pin2, ... pinN"""
        
    def test_gnd_component_detection(self):
        """GND class → node 0"""
```

### 3.2 API Endpoint: `routes/netlist.py`

```python
# Tests for /api/netlist endpoint

def test_netlist_endpoint_returns_spice()
def test_netlist_endpoint_returns_nodes()
def test_netlist_endpoint_returns_components()
def test_netlist_endpoint_returns_warnings()
def test_netlist_endpoint_invalid_image_returns_404()
def test_netlist_endpoint_no_components_returns_warning()
def test_netlist_endpoint_no_wires_returns_warning()
```

### 3.3 Frontend Components

```typescript
// __tests__/NetlistPanel.test.tsx

describe('NetlistPanel', () => {
  it('renders SPICE netlist with syntax highlighting')
  it('renders component list')
  it('renders node table')
  it('shows warnings')
  it('shows loading state')
  it('shows error state')
  it('has copy-to-clipboard button')
  it('has download .spice button')
})

describe('SimulationPanel', () => {
  it('shows DC operating point results')
  it('shows voltage table')
  it('shows current table')
  it('shows simulate button')
  it('shows loading during simulation')
  it('shows error on simulation failure')
  it('shows circuit diagram')
})
```

---

## Phase 4: Implementation Order

### Week 1: Test Foundation
- [ ] Write `tests/test_api.py` — all API endpoint tests (RED)
- [ ] Write `tests/test_benchmark_utils.py` — geometry, loading, parsing (RED)
- [ ] Write `tests/test_mapping.py` — mapping methods (RED)
- [ ] Make all tests GREEN (fix any bugs found)

### Week 2: Backend Reorganize
- [ ] Extract `api/routes/presets.py` from `server.py`
- [ ] Extract `api/routes/process.py` from `server.py`
- [ ] Extract `api/routes/datasets.py` from `server.py`
- [ ] Create `api/models.py` with Pydantic models
- [ ] Create `api/deps.py` for shared state
- [ ] Run all tests — should stay GREEN

### Week 3: Core Module
- [ ] Create `core/mapping.py` — extract best mapping method
- [ ] Create `core/netlist.py` — extract netlist builder
- [ ] Write `tests/test_netlist.py` (RED)
- [ ] Implement netlist builder to pass tests (GREEN)

### Week 4: SPICE Module
- [ ] Install ngspice
- [ ] Write `tests/test_spice.py` (RED)
- [ ] Create `core/spice.py` — SPICE generator
- [ ] Create `core/simulator.py` — ngspice wrapper
- [ ] Make all SPICE tests GREEN

### Week 5: API + Frontend
- [ ] Create `api/routes/netlist.py` — `/api/netlist` endpoint
- [ ] Extract frontend components from `HomeClient.tsx`
- [ ] Create `hooks/usePipeline.ts` and `hooks/useImages.ts`
- [ ] Consolidate `lib/api.ts` and `lib/backend.ts`
- [ ] Write frontend tests
- [ ] Create `NetlistPanel.tsx`
- [ ] Create `SimulationPanel.tsx`

### Week 6: Integration + Polish
- [ ] End-to-end test: image → detect → map → netlist → SPICE → simulate
- [ ] Wire up NetlistPanel to `/api/netlist`
- [ ] Wire up SimulationPanel to simulation results
- [ ] Add syntax highlighting for SPICE netlist
- [ ] Add circuit diagram visualization
- [ ] Add export/download functionality

---

## Test Execution

```bash
# Backend tests
cd /home/claw/circuit-digitization
uv run pytest wire_detection/tests/ -v

# Frontend tests
cd /home/claw/circuit-digitization/ui
npm test

# End-to-end
uv run pytest tests/e2e/ -v
```

---

## Success Criteria

### Phase 1 Complete
- [ ] All existing API endpoints have tests
- [ ] All geometry utilities have tests
- [ ] All mapping methods have tests
- [ ] All tests pass

### Phase 2 Complete
- [ ] `server.py` < 100 lines (just app setup)
- [ ] `HomeClient.tsx` < 100 lines (just composition)
- [ ] No duplicate API code
- [ ] All tests still pass

### Phase 3 Complete
- [ ] SPICE generator produces valid netlists
- [ ] Simulator runs DC analysis
- [ ] API returns netlist + SPICE text
- [ ] UI shows netlist with syntax highlighting
- [ ] UI shows simulation results
- [ ] All tests pass

### Phase 4 Complete
- [ ] End-to-end flow works
- [ ] User can: upload image → see detected wires → view netlist → run simulation → see results
- [ ] Export .spice file works
- [ ] Mobile-responsive netlist/simulation panels

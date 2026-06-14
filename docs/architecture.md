# Architecture

The framework is organized as two top-level packages and supporting infrastructure:

```
LineDetection/
├── wire_detection/          # Python backend (pipeline, sdg, evaluate, experiment, api)
│   ├── pipeline/            # Composable detection pipeline
│   ├── api/                 # FastAPI server
│   ├── data/                # Dataset registry with YAML config
│   ├── sdg/                 # Synthetic data generator
│   ├── evaluate/            # Evaluation metrics and reporting
│   ├── experiment/          # Parameter sweep engine
│   ├── config/              # Dataset YAML configs
│   └── tests/               # Test suite
├── ui/                      # Next.js frontend
├── docker-compose.yml       # Orchestrates both services
├── Dockerfile.python        # Python backend container
└── pyproject.toml           # Package metadata and CLI entry points
```

## Backend (`wire_detection/`)

### Pipeline Module

The core detection pipeline — a chain of independent stages. Each stage implements the `PipelineStage` ABC:
```python
class PipelineStage(ABC):
    name: str
    def run(self, image: np.ndarray, params: dict) -> StageOutput: ...
    def visualize(self, image: np.ndarray, output: StageOutput) -> np.ndarray: ...
```

Stages are composed by the `Pipeline` class and built from config via `PipelineFactory`. See [Pipeline Overview](pipeline/overview.md).

### Component Detection

The component detection module uses a trained YOLO26M-OBB model as the single source of truth for component labels.

**Model:** `models/component_detection/yolo26m_obb_16class_aug.pt`
**HuggingFace:** [boscochanam/circuit-component-detector](https://huggingface.co/boscochanam/circuit-component-detector)
**Performance:** 88.5% mAP50, 88.6% recall on CGHD-1152 dataset

**Usage:**
```python
from wire_detection.data.component_loader import load_components

# Uses config from defaults.yaml (component_detection.source)
components = load_components(image_path)
```

**Config toggle** (`wire_detection/config/defaults.yaml`):
```yaml
component_detection:
  source: model  # "model" | "ground_truth" | "roboflow"
  model_path: models/component_detection/yolo26m_obb_16class_aug.pt
  confidence_threshold: 0.5
```

### API Module

FastAPI server with CORS, LRU image cache, and endpoints for listing images, serving thumbnails, running the pipeline, and querying available stages/datasets. See [API Endpoints](api/endpoints.md).

**Endpoints:**
- `/api/list`, `/api/thumb`, `/api/datasets`, `/api/presets` — data listing
- `/api/process` — run wire detection with tunable params
- `/api/netlist` — build netlist (combined OBB + clustered pin discovery)  
- `/api/simulate` — run ngspice DC analysis
- Entry point: `api/server.py` (not `main.py`)

### Netlist Module (`core/netlist.py`)

Two pin discovery strategies combined:
1. `derive_pins_from_obb()` — OBB geometry for ALL 44 component types
2. `discover_pins()` — DBSCAN wire-endpoint clustering for SPICE-active types only
- Combined in `_build_netlist_data()`: OBB for everything + wire-guided override positions → `build_netlist()`

### SPICE Module (`core/spice.py`)

`SpiceGenerator` produces `.end`-delimited SPICE netlists from component labels and `Netlist` node assignments. Generates unique `.model` definitions for transistors/diodes. Auto-injects 5V VSRC when no voltage source detected.

## UI (`ui/`)

Next.js 15 app with:
- **Desktop**: 4-panel image grid (Detected Lines, Threshold, Dilated/Closed, Source) always visible + 3 bottom tabs (Netlist, Simulation, Topology)
- **Mobile**: 7 swipeable panels (touch/swipe navigation)
- **Topology tab**: SVG circuit graph with position-based layout (actual image coordinates), zoom (wheel) and pan (drag)
- **Param flow**: Tuner sliders → `/api/process` + `/api/netlist` (params forwarded to both)
- No browser-side `localhost:8000` calls — all backend fetches via Next.js server actions

### Data Module

Dataset registry that resolves paths, validates structure, and normalizes labels. Supports multiple label formats (YOLO OBB, YOLOv8 pose). See [Configuration](api/configuration.md).

### SDG Module

Generates realistic circuit schematic images with bezier-curve wires, component boxes, paper textures, and tool strokes. Exports labels in multiple formats. See [SDG](sdg.md).

### Evaluate Module

Line-distance metric with greedy matching for comparing detected lines against ground truth. Generates per-image and aggregate reports. See [Evaluation](evaluate.md).

### Experiment Module

Grid and random parameter search engine with checkpointing and markdown ranking tables. See [Experiment Engine](experiment.md).

## Frontend (`ui/`)

Next.js 14 app with TypeScript, shadcn/ui components, and dark theme. Features:

- **Sidebar** — dataset selector, image picker, all pipeline parameter sliders, Run button, stats
- **4-panel grid** — Detected Lines, Threshold, Dilated, Source — click for fullscreen
- **Image picker** — full-screen modal with 5-column thumbnail grid, lazy-loaded
- **Live updates** — slider release triggers pipeline run with abortable requests

## CLI Entry Points

Defined in `pyproject.toml` and installed as console scripts:

| Command | Module | Description |
|---------|--------|-------------|
| `wire-tune` | `api.server:main` | Start the FastAPI tuner server |
| `wire-pipeline` | `pipeline.cli:main` | Run pipeline on a single image |
| `wire-sdg` | `sdg.cli:main` | Generate synthetic dataset |
| `wire-eval` | `evaluate.cli:main` | Evaluate detections against ground truth |
| `wire-sweep` | `experiment.cli:main` | Run a parameter sweep |

## Data Flow

```
Config (YAML/dict) → PipelineFactory → Pipeline (composed stages)
                                         ↓
Image → [crop → mask → threshold → invert → dilate → CCL → contour_extract → dedup → length_filter]
                                         ↓
                                  PipelineResult (lines, intermediate images, timing)
                                         ↓
                              Optional: Evaluate against GT → EvalResult (F1, precision, recall)
```

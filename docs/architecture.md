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

### API Module

FastAPI server with CORS, LRU image cache, and endpoints for listing images, serving thumbnails, running the pipeline, and querying available stages/datasets. See [API Endpoints](api/endpoints.md).

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

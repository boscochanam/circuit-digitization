# Wire Detection Framework — Implementation Plan

## Overview

Build the next-gen **Wire Detection Framework** as two separate top-level packages:

```
LineDetection/
├── wire_detection/          # Python package (pipeline, sdg, evaluate, experiment, api)
├── ui/                      # NextJS frontend
├── docker-compose.yml       # Orchestrates both services
├── Dockerfile.python        # Python backend container
└── project_blueprint/       # Spec + this plan
```

---

## Phase 1: Python Package Scaffold (`wire_detection/`)

### 1.1 Project Metadata

| File | Purpose |
|------|---------|
| `wire_detection/pyproject.toml` | Package metadata, dependencies, CLI entry points |

**Dependencies:** `numpy`, `opencv-python`, `pydantic>=2.5`, `albumentations`, `pyyaml`, `fastapi`, `uvicorn`, `scipy`, `scikit-image`

**Dev:** `pytest`, `pytest-cov`, `ruff`, `mypy`

**CLI entry points:**
- `wire-sdg` → `sdg.cli:main`
- `wire-eval` → `evaluate.cli:main`
- `wire-sweep` → `experiment.cli:main`
- `wire-tune` → `api.server:main`
- `wire-pipeline` → `pipeline.cli:main`

### 1.2 Config Module (`wire_detection/config/`)

| File | Description |
|------|-------------|
| `__init__.py` | Package init |
| `schema.py` | Pydantic models: `PipelineConfig`, `StageConfig`, `SweepConfig`, `DatasetConfig`, `SDGConfig`, `EvalConfig` |
| `defaults.yaml` | Default pipeline parameters (baseline: Otsu, k5, i1, min_area=30, dedup_angle=10, dedup_dist=12) |
| `datasets.yaml` | Dataset registry paths |
| `sweeps.yaml` | Pre-defined sweep configs |

### 1.3 Pipeline Module (`wire_detection/pipeline/`)

The core detection pipeline — composable stages + pluggable backends.

#### Types & Core

| File | Description |
|------|-------------|
| `__init__.py` | Public API exports |
| `types.py` | `Line = tuple[tuple[int,int], tuple[int,int]]`, `StageOutput`, `PipelineResult`, `PipelineStage` ABC |
| `core.py` | `Pipeline` class — composes stages, runs sequentially, collects intermediate outputs |
| `factory.py` | `PipelineFactory.from_config(dict)` — builds pipeline from config dict |
| `registry.py` | `STAGES`, `BACKENDS`, `JOINERS` registries with `register_*` / `list_*` functions |

#### Stages

Each stage implements `PipelineStage` ABC with `run(image, params) → StageOutput` and `visualize(image, output) → np.ndarray`.

| File | Stage | Ported From | Key Params |
|------|-------|-------------|------------|
| `stages/__init__.py` | — | — | — |
| `stages/crop.py` | Crop to ROI | `pipeline.py:run_pipeline` (bbox crop) | `padding: int` |
| `stages/mask.py` | Mask polygon regions | `pipeline.py:ImageCache` masking | `fill_value: int` |
| `stages/threshold.py` | Binary threshold | `pipeline.py:threshold_image` | `mode: otsu|manual|adaptive`, `value: int`, `block_size: int`, `c: int` |
| `stages/invert.py` | Bitwise NOT | `pipeline.py:bw_inv` | — |
| `stages/dilate.py` | Morphological dilation | `pipeline.py:dilate_binary` | `kernel_size: int`, `iterations: int`, `shape: cross|ellipse|rect` |
| `stages/ccl.py` | Connected components | `run_mega_sweep.py:ccl_components` | `min_area: int`, `connectivity: 4|8`, `backend: opencv|scipy` |
| `stages/contour_extract.py` | Contour extreme points → line | `src/__init__.py:find_endpoints` | — |
| `stages/dedup.py` | Global angle+distance dedup | `run_mega_sweep.py:global_dedup` | `angle_thresh: int`, `dist_thresh: int` |
| `stages/length_filter.py` | Min/max line length | `pipeline.py:filter_short_lines` | `min_length: int`, `max_length: int` |

#### Backends (Plugin System)

| File | Description |
|------|-------------|
| `backends/__init__.py` | Backend registry initialization |
| `backends/registry.py` | `PipelineBackend` ABC, `register_backend()`, `BACKENDS` dict |
| `backends/contour.py` | Default: contour extreme points pipeline (wraps the full Pipeline) |
| `backends/sina.py` | SINA CCL baseline (component mask → CCL → treat blobs as nets) |

### 1.4 Data Module (`wire_detection/data/`)

| File | Description |
|------|-------------|
| `__init__.py` | Public API |
| `dataset.py` | `DatasetConfig` pydantic model, `DATASETS` registry dict, `get_dataset(key)`, `list_datasets()` |
| `transforms.py` | Albumentations augmentation pipelines (for SDG + eval preprocessing) |

Built from existing dataset paths in `tuner.py:DATASETS`.

### 1.5 SDG Module (`wire_detection/sdg/`)

Synthetic data generator for wire images with ground truth labels.

| File | Description |
|------|-------------|
| `__init__.py` | Public API exports |
| `generator.py` | `SDGConfig` pydantic model, `SDG` class with `generate(cfg)` and `generate_one(rng)` |
| `primitives.py` | Wire primitives: bezier curves (2-4 control points), straight lines, arcs. Configurable width, color, anti-aliasing |
| `backgrounds.py` | Background generators: plain, ruled paper, graph paper, grid lines, gaussian noise, salt & pepper |
| `compositor.py` | Composite N wires + optional component bboxes → image + labels |
| `augment.py` | Per-image augmentation: blur, contrast, noise, rotation, scaling, shearing (albumentations) |
| `formats.py` | Label export: YOLOv8 pose, COCO keypoints, custom line-segment format |

### 1.6 Evaluate Module (`wire_detection/evaluate/`)

| File | Description | Ported From |
|------|-------------|-------------|
| `__init__.py` | Public API |
| `metric.py` | `point_to_segment_dist()`, `segment_dist()`, `line_distance_matrix()` | `eval_synthetic.py` |
| `match.py` | Greedy matching of detections to GT, `evaluate()` → `EvalResult(tp, fp, redundant, fn, recall, precision, f1)` | `eval_synthetic.py:evaluate()` |
| `report.py` | Per-image + aggregate report, markdown table, CSV export |
| `visualize.py` | Overlay detections + GT on images | `visualize.py` |
| `cli.py` | CLI entry for `wire-eval` |

### 1.7 Experiment Module (`wire_detection/experiment/`)

| File | Description |
|------|-------------|
| `__init__.py` | Public API |
| `sweep.py` | `SweepConfig` pydantic model, grid/random search engine, checkpointing |
| `runner.py` | Run a single config across N images with timing |
| `reporter.py` | Generate markdown ranking tables, CSV export, best-config summary |
| `presets.py` | Named config presets: `baseline`, `aggressive`, `conservative`, `no_dedup`, `heavy_dilate` |
| `cli.py` | CLI entry for `wire-sweep` |

### 1.8 FastAPI Backend (`wire_detection/api/`)

| File | Description |
|------|-------------|
| `__init__.py` | — |
| `server.py` | FastAPI app creation, lifespan, CORS, uvicorn `main()` entry point |
| `cache.py` | Thread-safe `ImageCache` (ported from `pipeline.py:ImageCache`) |
| `routes.py` | API endpoints |

**API Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/list?ds=<key>` | JSON array of image filenames |
| `GET` | `/api/thumb?idx=<n>&ds=<key>` | JPEG thumbnail (80px) |
| `POST` | `/api/process` | Run pipeline with JSON params → `{line_count, elapsed_ms, overlay, threshold, dilated, masked}` as base64 JPEG |

### 1.9 Test Suite (`wire_detection/tests/`)

| File | Description |
|------|-------------|
| `__init__.py` | — |
| `conftest.py` | Fixtures: synthetic images (small), GT labels, sample configs |
| `test_pipeline.py` | Unit tests for each stage (isolated, synthetic input) |
| `test_sdg.py` | SDG output validation (correct shapes, label format) |
| `test_evaluate.py` | Metric correctness (known distances, edge cases) |
| `test_integration.py` | End-to-end: pipeline → eval on synthetic image with known GT |

**Coverage target:** ≥80% for `pipeline/`, `evaluate/`, `sdg/`.

---

## Phase 2: NextJS Frontend (`ui/`)

Modern replacement for the existing `tuner.py` embedded HTML/JS.

### 2.1 Project Setup

| File | Description |
|------|-------------|
| `ui/package.json` | NextJS 14, TypeScript, React 18 |
| `ui/tsconfig.json` | TypeScript config |
| `ui/next.config.js` | Dev API proxy to `http://localhost:8000` |
| `ui/Dockerfile` | Multi-stage: `pnpm install → pnpm build → pnpm start` |
| `ui/.dockerignore` | node_modules, .next |

### 2.2 Pages & API Routes

| File | Description |
|------|-------------|
| `ui/pages/index.tsx` | Main tuner page (server-rendered shell, client-side interactivity) |
| `ui/pages/api/list.ts` | Proxies `GET /api/list?ds=` to Python backend |
| `ui/pages/api/thumb.ts` | Proxies `GET /api/thumb?idx=&ds=` to Python backend |
| `ui/pages/api/process.ts` | Proxies `POST /api/process` to Python backend |
| `ui/pages/_app.tsx` | App wrapper with global styles |

### 2.3 Components

| File | Description |
|------|-------------|
| `ui/components/Sidebar.tsx` | Left sidebar: dataset toggle, image picker, all parameter sliders, Run button, stats bar |
| `ui/components/ImageGrid.tsx` | 4-panel grid: Detected Lines / Threshold / Dilated / Masked with loading spinners |
| `ui/components/ImagePicker.tsx` | Modal with scrollable thumbnail grid (80px), lazy-loaded, keyboard nav |
| `ui/components/ParamSlider.tsx` | Reusable slider with label, value display, disabled state |
| `ui/components/StatsBar.tsx` | Line count, blob count, elapsed ms, threshold info |
| `ui/components/ToggleGroup.tsx` | Segmented button group (HDC/Synth, Otsu/Manual) |

### 2.4 Styles & Logic

| File | Description |
|------|-------------|
| `ui/styles/globals.css` | Dark theme (GitHub-dark inspired), grid layout, animation keyframes |
| `ui/hooks/usePipeline.ts` | Custom hook: manages pipeline state, abortable fetch, auto-run on param change |
| `ui/lib/api.ts` | API client functions: `listImages`, `getThumb`, `runPipeline` |

All behaviors from existing tuner preserved:
- Slider `change` (release) triggers pipeline run
- AbortController cancels in-flight requests on rapid changes
- Flash animation on panel update
- Loading overlays per panel (not global)
- Image picker modal with selected state
- Thumbnail cache via browser HTTP cache

---

## Phase 3: Docker Compose & Dev Tooling

### 3.1 Docker Setup

| File | Description |
|------|-------------|
| `Dockerfile.python` | Python 3.11+, installs `wire_detection` with deps, exposes port 8000 |
| `ui/Dockerfile` | Node 20, pnpm, NextJS standalone output |
| `docker-compose.yml` | Two services: `backend` (Python) + `frontend` (NextJS), shared network |

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.python
    ports: ["8000:8000"]
    volumes:
      - ./wire_detection:/app/wire_detection  # dev hot-reload
      - /path/to/datasets:/data                # dataset mounts
    environment:
      - DATASETS_YAML=/app/config/datasets.yaml
    command: uvicorn wire_detection.api.server:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./ui
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on: [backend]
    volumes:
      - ./ui:/app  # dev hot-reload
```

### 3.2 Environment Config

| File | Description |
|------|-------------|
| `.env.example` | `DATASETS_YAML`, `BACKEND_PORT`, `FRONTEND_PORT`, dataset paths |

---

## Key Code Reuse Map

| Existing File | New Location | Strategy |
|---------------|--------------|----------|
| `experiments/pipeline.py:run_pipeline` | `pipeline/core.py` + `stages/*` | Decompose into composable stages |
| `experiments/pipeline.py:ImageCache` | `api/cache.py` | Direct port |
| `src/__init__.py:find_endpoints` | `pipeline/stages/contour_extract.py` | Direct port |
| `src/__init__.py:blobs_to_lines` | `pipeline/stages/ccl.py` (combine CCL + contour) | Split into two stages |
| `run_mega_sweep.py:global_dedup` | `pipeline/stages/dedup.py` | Direct port |
| `run_mega_sweep.py:ccl_components` | `pipeline/stages/ccl.py` | Direct port |
| `eval_synthetic.py:segment_dist, evaluate` | `evaluate/metric.py`, `match.py` | Direct port |
| `tuner.py` (HTML+CSS+JS) | `ui/` components | Rebuild in React+TS |
| `visualize.py` | `evaluate/visualize.py` | Direct port |

---

## Implementation Order

The build order minimizes blocking dependencies:

```
Phase 1:
  1.1 pyproject.toml + deps
  1.2 config/schema.py (Pydantic models — everything depends on these)
  1.3 pipeline/types.py + pipeline/stages/* (core detection logic)
  1.4 pipeline/core.py + factory.py (composable pipeline)
  1.5 evaluate/metric.py + match.py (can test with hardcoded lines)
  1.6 data/dataset.py (dataset registry)
  1.7 experiment/sweep.py (uses pipeline + evaluate)
  1.8 sdg/ (independent module)
  1.9 tests/
  1.10 api/ (FastAPI backend — last, depends on everything above)

Phase 2:
  2.1 ui/ project scaffold
  2.2 ui/components/* (build + test against real API)
  2.3 ui/pages/api/* (proxy routes)
  2.4 ui/pages/index.tsx (assemble components)

Phase 3:
  3.1 Dockerfile.python
  3.2 ui/Dockerfile
  3.3 docker-compose.yml
```

---

## Out of Scope (v1)

- GPU-accelerated CCL
- Bayesian optimization (Optuna) — grid/random search only
- Multi-machine distributed sweeps
- REST API mode (stateless, no HTML)
- Component-aware dedup
- Online learning from tuner adjustments

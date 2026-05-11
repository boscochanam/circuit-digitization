# SINA — Schematic Image to Netlist Tool + Wire Detection Framework

This repo contains two projects under one roof:

1. **SINA** (legacy): CV-based system that converts circuit schematic images into netlists for IC and PCB designs.
2. **Wire Detection Framework**: A modular Python pipeline for detecting wires in circuit schematics, with a synthetic data generator, evaluation tools, experiment sweeper, FastAPI server, and NextJS tuner UI.

---

## Wire Detection Framework

### Quickstart

```bash
# Backend
uv venv && uv sync
uv run wire-tune           # Starts API server on :8000

# Frontend (separate terminal)
cd ui && pnpm install && pnpm dev   # Starts on :3000
```

Or with Docker:

```bash
docker compose down && docker compose up --build
```

### Architecture

```
wire_detection/
├── pipeline/        # 9-stage pipeline (crop → mask → threshold → invert → dilate → CCL → contour_extract → dedup → length_filter)
│   ├── stages/      # Individual pipeline stages with registration system
│   ├── factory.py   # PipelineFactory builds pipelines from config dicts
│   └── registry.py  # Stage registry for discovery
├── api/             # FastAPI server
│   ├── server.py    # Endpoints: /api/list, /api/thumb, /api/process, /api/datasets, /api/stages
│   └── cache.py     # LRU image cache
├── data/            # Dataset registry
│   └── dataset.py   # DatasetRegistry with YAML config, OBB label parsing
├── sdg/             # Synthetic data generator (ported from LineSDGSoftware)
│   ├── generator.py # SDG class — component-based circuit schematic generation
│   ├── backgrounds.py, textures.py  # Paper textures, tool strokes, background loader
│   ├── primitives.py # Geometry utilities (bezier curves, intersections, bounding boxes)
│   └── formats.py   # Label export (YOLOv8 pose, lines, COCO)
├── evaluate/        # Evaluation metrics (point-to-segment distance, greedy matching, reports)
├── experiment/      # Grid/random sweep runner
├── config/          # Dataset YAML configs
│   ├── datasets.yaml        # Local dev paths
│   └── datasets.docker.yaml # Docker paths (/data/...)
└── tests/           # 54+ passing tests
```

### Pipeline Stages

| Stage | Description |
|-------|-------------|
| `crop` | Crop to region of interest |
| `mask` | Apply binary mask |
| `threshold` | Otsu, manual, or adaptive thresholding |
| `invert` | Invert binary image |
| `dilate` | Morphological dilation (kernel size, iterations) |
| `ccl` | Connected component labeling with min area filter |
| `contour_extract` | Extract line segments from component contours |
| `dedup` | Remove duplicate lines by angle + distance thresholds |
| `length_filter` | Filter by minimum line length |

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/list?ds=<dataset>` | List image filenames for a dataset |
| `GET /api/thumb?idx=<n>&ds=<dataset>` | Return thumbnail as JPEG |
| `GET /api/datasets` | Dataset info (path, image count) |
| `POST /api/process` | Run pipeline with tunable params |
| `GET /api/stages` | List available pipeline stages |

### Synthetic Data Generation (SDG)

Generates realistic circuit schematic images with component boxes and bezier-curve wires:

```bash
wire-sdg --num-images 1000 --image-size 640 640 --output-dir data/synthetic
```

The SDG creates component-to-component connections using:
- Paper texture backgrounds with imperfections
- Bezier curves with natural jitter
- Tool strokes (gel pen, ballpoint, pencil)
- Component boxes that occlude underlying lines (realistic circuit layout)

### Configuration

Dataset paths are configured via YAML. The `DATASETS_YAML` env var selects which config to use:

```yaml
# datasets.yaml (local dev)
hand_drawn:
  path: /path/to/roboflow_test
  image_glob: "**/images/*.jpg"
  label_format: yolo_obb

synthetic:
  path: /path/to/dataset_pose
  image_glob: "train/images/*.jpg"
  label_format: yolov8_pose
```

```yaml
# datasets.docker.yaml (Docker)
hand_drawn:
  path: /data/hand_drawn
  image_glob: "**/images/*.jpg"
```

### Datasets

| Dataset | Source | Count | Description |
|---------|--------|-------|-------------|
| `hand_drawn` | Roboflow | 140 | Hand-drawn circuit wires with OBB labels |
| `hdc` | Roboflow | 1993 | PCB schematics with component labels |
| `synthetic` | SDG + LineSDGSoftware | 2000+ | Generated bezier-wire schematics |
| `database` | Local | 662 | Raw schematic images (no labels) |

### UI Tuner

Next.js app with:
- **Sidebar**: Dataset selector, image picker, parameter sliders (threshold mode, dilate kernel, area, dedup, length), live diagnostics panel
- **4-panel grid**: Detected Lines, Threshold, Dilated, Source — click any panel for fullscreen preview
- **Image picker**: Full-screen modal with 5-column thumbnail grid (click to select)
- Dark theme with shadcn/ui components

---

## Legacy SINA

### IC Netlist Generator

Converts IC schematic images into netlists by detecting components, analyzing wire connections, and handling crossing points.

[View IC Documentation](Netlist%20Generator/IC/README.md)

### PCB Netlist Generator

Processes PCB schematics with text removal, pin detection, and multi-stage netlist generation with SPICE output support.

[View PCB Documentation](Netlist%20Generator/PCB/README.md)

---

## Development

```bash
# Run tests
uv run pytest wire_detection/tests/ -q

# Type check
uv run mypy wire_detection/

# Lint
uv run ruff check wire_detection/
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DATASETS_YAML` | Path to dataset config YAML (default: `config/datasets.yaml`) |
| `NEXT_PUBLIC_API_URL` | Backend API URL for frontend (default: `http://localhost:8000`) |

---

## License

See [LICENSE.txt](LICENSE.txt) for details.

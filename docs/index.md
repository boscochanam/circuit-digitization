# Wire Detection Framework

A modular Python framework for detecting wires in circuit schematic images. Combines a classical computer vision pipeline with a synthetic data generator, evaluation toolkit, experiment engine, FastAPI backend, and Next.js tuner UI.

## Key Features

- **Composable CV pipeline** — 9 independent stages (crop, mask, threshold, dilate, CCL, contour extraction, dedup, length filter) that can be arranged and configured via YAML or dict
- **Pluggable backends** — compare classical CV, YOLO, or third-party approaches through a common interface
- **Synthetic data generator** — generate realistic circuit schematic images with bezier-curve wires, paper textures, and tool strokes; export in YOLOv8 pose, COCO, or custom formats
- **Evaluation framework** — line-distance metric with greedy matching, aggregate reports, and visualization overlays
- **Experiment engine** — grid and random parameter sweeps with checkpointing and markdown ranking
- **Interactive tuner UI** — Next.js app with live 4-panel visualization (detected lines, threshold, dilated, source), parameter sliders, and dataset browser
- **Docker support** — backend + frontend as separate containers orchestrated via docker-compose

## Architecture Overview

```
wire_detection/          # Python backend package
├── pipeline/            # 9-stage detection pipeline
├── api/                 # FastAPI server
├── data/                # Dataset registry
├── sdg/                 # Synthetic data generator
├── evaluate/            # Evaluation metrics
├── experiment/          # Parameter sweep engine
└── tests/               # 54+ tests

ui/                      # Next.js frontend
├── src/app/             # Pages and layout
├── src/components/      # React components (sidebar, image grid, picker)
└── src/lib/             # API client and utilities
```

## Quick Links

- [Getting Started](getting-started.md)
- [Architecture](architecture.md)
- [Pipeline Stages](pipeline/stages.md)
- [API Endpoints](api/endpoints.md)
- [CLI Reference](cli.md)
- [Deployment](deployment.md)

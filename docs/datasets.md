# Dataset Setup

The framework uses several datasets for wire detection, component detection, and evaluation. These datasets are **not** included in the repository — they must be downloaded or generated separately.

## Available Datasets

| Key | Source | Images | Labels | Purpose |
|-----|--------|--------|--------|---------|
| `hdc` | Roboflow export | 1,993 | YOLO OBB (57 component classes) | Component detection training + masked wire detection |
| `hand_drawn` | Roboflow export | 140 | YOLO OBB (wire polygons) | Wire detection evaluation benchmark |
| `synthetic` | Self-generated | 2,000+ | YOLOv8 pose / lines | Large-scale parameter sweeps |
| `database` | Local collection | 662 | None | Visual inspection / real-world testing |

## Quick Start

### 1. Download Datasets

**HDC-Recognition** and **Hand-drawn wires** are exported from [Roboflow](https://roboflow.com/). Place them at the repo root:

```
LineDetection/
├── roboflow_test2/          # HDC dataset (1993 images)
│   ├── train/images/
│   ├── train/labels/
│   ├── valid/images/
│   └── valid/labels/
├── roboflow_test/           # Hand-drawn wires (140 images)
│   ├── train/images/
│   ├── train/labels/
│   └── valid/images/
│   └── valid/labels/
├── Database/                # Raw schematic images (662 images)
│   ├── 001-099/
│   ├── 100-199/
│   └── ...
└── data/synthetic/          # Generated synthetic dataset
    ├── images/
    └── labels/
```

### 2. Generate Synthetic Dataset

```bash
uv run wire-sdg \
  --num-images 2000 \
  --image-size 1024 1024 \
  --output-dir data/synthetic
```

### 3. Configure Paths

Edit `wire_detection/config/datasets.yaml` to point to your dataset locations:

```yaml
datasets:
  hdc:
    path: ./roboflow_test2          # relative to project root
    image_glob: "**/images/*.jpg"

  hand_drawn:
    path: ./roboflow_test
    image_glob: "**/images/*.jpg"

  synthetic:
    path: ./data/synthetic
    image_glob: "images/*.jpg"

  database:
    path: ./Database
    image_glob: "*/*.jpg"
```

### 4. Verify

```bash
# Check that datasets are found
curl http://localhost:8000/api/datasets
```

Expected response:
```json
{
  "hdc": { "image_count": 1993, ... },
  "hand_drawn": { "image_count": 140, ... },
  "database": { "image_count": 662, ... }
}
```

## Docker Setup

When using Docker Compose, datasets are mounted from the host into the container:

```yaml
services:
  backend:
    volumes:
      - ./roboflow_test2:/data/hdc
      - ./roboflow_test:/data/hand_drawn
      - ./Database:/data/database
    environment:
      - DATASETS_YAML=/app/wire_detection/config/datasets.docker.yaml
```

The Docker config (`datasets.docker.yaml`) uses `/data/<key>` paths that match these mount points. No additional configuration needed.

## Dataset Directory Layout

```
hdc/                          # roboflow_test2/
├── train/
│   ├── images/               # *.jpg
│   └── labels/               # *.txt  (YOLO OBB: class_id x1 y1 x2 y2 x3 y3 x4 y4)
├── valid/
│   ├── images/
│   └── labels/
└── test/
    ├── images/
    └── labels/

hand_drawn/                   # roboflow_test/
├── train/
│   ├── images/
│   └── labels/
└── valid/
    ├── images/
    └── labels/

database/                     # Database/
├── 001-099/                  # Raw circuit images
├── 100-199/
└── ...

synthetic/                    # data/synthetic/
├── images/                   # Generated images
└── labels/                   # Generated labels (lines format)
```

## Environment Configuration

Use the `DATASETS_YAML` environment variable to select a different config file:

```bash
# Local development (default)
export DATASETS_YAML=wire_detection/config/datasets.yaml

# Docker (handled automatically by docker-compose.yml)
export DATASETS_YAML=/app/wire_detection/config/datasets.docker.yaml
```

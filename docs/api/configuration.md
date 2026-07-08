# Configuration

## Dataset Configuration

Dataset paths are configured via YAML files. The `DATASETS_YAML` environment variable selects which config to use.

### Local Development

```yaml
# wire_detection/config/datasets.yaml
hand_drawn:
  path: /path/to/roboflow_test
  image_glob: "**/images/*.jpg"
  label_format: yolo_obb

synthetic:
  path: /path/to/dataset_pose
  image_glob: "train/images/*.jpg"
  label_format: yolov8_pose

hdc:
  path: /path/to/roboflow_test2
  image_glob: "**/images/*.jpg"
  label_format: yolo_obb
  component_labels: true

database:
  path: /path/to/Database
  image_glob: "*/*.jpg"
  label_format: null
```

### Docker

```yaml
# wire_detection/config/datasets.docker.yaml
hand_drawn:
  path: /data/hand_drawn
  image_glob: "**/images/*.jpg"

hdc:
  path: /data/hdc
  image_glob: "**/images/*.jpg"
  label_format: yolo_obb
  component_labels: true
```

## Datasets

| Key | Images | Labels | Purpose |
|-----|--------|--------|---------|
| `hand_drawn` | 140 | YOLO OBB (wire polygons) | Primary wire detection benchmark |
| `hdc` | 1,993 | YOLO OBB (57 component classes) | Component detection + masked wire detection |
| `synthetic` | 2,000+ | YOLOv8 pose (2 keypoints) | Large-scale parameter sweeps |
| `database` | 662 | None | Visual inspection / real-world testing |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATASETS_YAML` | `config/datasets.yaml` | Path to dataset config YAML |
| `WIRE_GT_IMAGES` | none (required for real-image evaluation) | CGHD source scans; not redistributed with this repository |
| `GT_LABELS_PATH` | none | Root of the wire-label corpus (`labels_few_annot`), mounted by docker-compose for the tuner UI. Also a fallback for `WIRE_GT_IMAGES`, which is then read from `$GT_LABELS_PATH/images` |
| `WIRE_GT_WIRE_LABELS` | `ground_truth/wire_labels` | Ground-truth wire polylines; committed, so set only to relocate |
| `WIRE_COMPONENT_LABELS` | `ground_truth/component_labels` | Component labels used for occlusion; committed, so set only to relocate |
| `WIRE_HDC_BASE` | `<repo>/roboflow_test2` | Roboflow HDC-Recognition export. A fallback source of component labels only; most workflows never need it |
| `SYNTHETIC_PATH` | `<repo>/data/synthetic` | Generated synthetic wire corpus; set only to relocate it |
| `WIRE_OUTPUT_DIR` | `<repo>/output` | Writable directory for generated artifacts |
| `WIRE_CGHD_WORKSPACE` | `<repo>/data/workspace` | Scratch dir for one-off CGHD quality-audit artifacts |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL for the frontend |

## Docker Compose

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.python
    ports: ["8000:8000"]
    volumes:
      - /path/to/datasets:/data
    environment:
      - DATASETS_YAML=/app/wire_detection/config/datasets.docker.yaml

  frontend:
    build: ./ui
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
```

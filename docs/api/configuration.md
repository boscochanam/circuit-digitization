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

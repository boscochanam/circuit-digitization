# Dataset Setup

The framework uses several datasets for wire detection, component detection, and evaluation. These datasets are **not** included in the repository — they must be downloaded or generated separately.

## Available Datasets

| Key | Source | Images | Labels | Purpose |
|-----|--------|--------|--------|---------|
| `hdc` | Roboflow export | 4,833 | YOLO OBB (58 component classes) | Component detection training + masked wire detection |
| `hand_drawn` | Roboflow export | 140 | YOLO OBB (wire polygons) | Wire detection evaluation benchmark |
| `cghd` | Kaggle | 4,503 | PASCAL VOC XML (61 classes) | Multi-drafter evaluation benchmark |
| `synthetic` | Self-generated | variable | Lines format | Large-scale parameter sweeps |
| `database` | Local collection | 662 | None | Visual inspection / real-world testing |

## Reference Datasets

### CGHD1152 — Multi-Drafter Ground Truth

[CGHD1152](https://www.kaggle.com/datasets/johannesbayer/cghd1152) is a public benchmark dataset for handwritten circuit diagrams with annotations from **33 different drafters**.

| Property | Value |
|---|---|
| Source | johannesbayer/cghd1152 (Kaggle) |
| Total images | 4,503 |
| Total annotations | 3,269 (PASCAL VOC XML) |
| Resolution | 1000×1000 |
| Drafters | 33 (drafter_-1 through drafter_31) |
| Classes | 61 (all 58 HDC classes covered + 3 extras) |
| Extras | Instance segmentation polygons + binary stroke masks |
| License | See Kaggle page |

**Drafter breakdown:**

| Drafter | Annotations | Images | Status |
|---|---|---|---|
| drafter_0 | 149 | 1,039 | ⚠️ Outlier (10× others) |
| drafter_-1 | 144 | 145 | Pre-numbering batch |
| drafter_1–31 | 96 each | ~108 each | Standard 12×2×4 structure |
| drafter_17 | 96 | 19 | ⚠️ Missing 77 images |
| drafter_28 | 96 | 0 | ❌ Annotations only, no images |

### Class Coverage

CGHD1152 covers **100% of the HDC Roboflow classes** (58/58). It adds 3 classes not in HDC:

| Class | Description |
|---|---|
| `block` | Block diagram element |
| `explanatory` | Annotation callout / label |
| `inductor.coupled` | Coupled inductor variant |

**Naming convention:** HDC uses dashes (`capacitor-polarized`), CGHD uses dots (`capacitor.polarized`). Maps cleanly via normalization.

## Quick Start

### 1. Download Datasets

**HDC-Recognition** is exported from [Roboflow](https://universe.roboflow.com/line-k1z2h/hdc-recognition-66e7m).

**CGHD1152** is available on Kaggle:

```bash
curl -L -o ~/Downloads/cghd1152.zip \
  https://www.kaggle.com/api/v1/datasets/download/johannesbayer/cghd1152
```

Place them at the repo root:

```
circuit-digitization/
├── roboflow_test2/          # HDC dataset (4,833 images)
│   ├── train/images/
│   ├── train/labels/
│   ├── valid/images/
│   └── valid/labels/
├── cghd1152/                # CGHD reference dataset
│   ├── drafter_-1/images/
│   ├── drafter_-1/annotations/
│   ├── drafter_0/ ...
│   └── ...
├── Database/                # Raw schematic images (662 images)
└── data/synthetic/          # Generated synthetic dataset
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
    path: ./roboflow_test2
    image_glob: "**/images/*.jpg"
    label_format: yolo_obb
    label_glob: "**/labels/*.txt"
    component_labels: true
    description: "HDC-Recognition PCB schematics, 4,833 images, 58 classes"

  cghd:
    path: ./cghd1152
    image_glob: "*/images/*.jpg"
    label_format: pascal_voc
    label_glob: "*/annotations/*.xml"
    component_labels: true
    description: "CGHD1152 hand-drawn circuits, 4,503 images, 61 classes, 33 drafters"

  synthetic:
    path: ./data/synthetic
    image_glob: "images/*.jpg"
    label_format: lines
    label_glob: "labels/*.txt"
    description: "Synthetic bezier-curve wires on varied backgrounds"

  database:
    path: ./Database
    image_glob: "*/*.jpg"
    label_format: null
    label_glob: null
    description: "Raw schematic images for visual inspection"
```

## Data Quality Considerations

The CGHD1152 dataset contains **significant quality variation** across drafters. See the [Data Quality Guide](data-quality.md) for filtering and pre-processing strategies.

Key findings from a 200-image sample:

- **96%** of images have lined or graph paper backgrounds
- **10%** have significant uneven lighting / shadows
- **~2%** are too dark (mean brightness <60) or overexposed (mean >240)
- Most are phone photos, not flatbed scans

**Recommendation:** Use CGHD1152 for evaluation (robustness across drafting styles), not for training. Train on the cleaner HDC Roboflow data.

## Docker Setup

When using Docker Compose, datasets are mounted from the host into the container:

```yaml
services:
  backend:
    volumes:
      - ./roboflow_test2:/data/hdc
      - ./cghd1152:/data/cghd
      - ./Database:/data/database
    environment:
      - DATASETS_YAML=/app/wire_detection/config/datasets.docker.yaml
```

## Environment Configuration

Use the `DATASETS_YAML` environment variable to select a different config file:

```bash
export DATASETS_YAML=wire_detection/config/datasets.yaml
```

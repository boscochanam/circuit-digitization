# Synthetic Data Generation

The SDG module generates realistic circuit schematic images with labeled wires for development and benchmarking without manual annotation.

## Usage

```bash
# Generate 1000 synthetic images
wire-sdg --num-images 1000 --image-size 640 640 --output-dir data/synthetic

# With custom parameters
wire-sdg \
  --num-images 500 \
  --image-size 1024 1024 \
  --wires-per-image 3 15 \
  --wire-width 1 4 \
  --output-dir data/synthetic
```

## Features

### Wire Primitives
- **Bezier curves** — 2-4 control points with configurable curvature
- **Straight lines** — direct endpoint-to-endpoint
- **Arcs** — curved segments
- Configurable width (1-6px), color (grayscale or RGB), anti-aliasing

### Paper Textures
- **Plain** — white or light gray background
- **Grid** — ruled paper, graph paper
- **Noise** — Gaussian noise, salt & pepper
- **Real scans** — load scanned paper texture images

### Tool Strokes
Simulates different writing instruments:
- **Gel pen** — dark gray (30-60), solid
- **Ballpoint** — medium gray (60-100) or washed blue
- **Pencil** — lighter graphite (80-140), variable pressure

### Component Boxes
- Rectangle components that occlude underlying wires
- Wires always terminate at component edges (realistic circuit layout)
- Component-to-wire junction labels for joiner evaluation

### Label Export

| Format | Description |
|--------|-------------|
| YOLOv8 pose | 2 keypoints per wire (endpoints), normalized, leftmost-first ordering |
| COCO keypoints | Standard COCO JSON format |
| Custom lines | Simple `((x1,y1),(x2,y2))` format |

## Deterministic Mode

Fixed seed per image for reproducibility:

```python
from wire_detection.sdg import SDG, SDGConfig

cfg = SDGConfig(
    num_images=100,
    seed=42,  # deterministic
    output_dir="data/synthetic",
)
SDG().generate(cfg)
```

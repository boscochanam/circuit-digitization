# CLI Reference

## wire-tune

Start the FastAPI tuner server.

```bash
wire-tune [--host HOST] [--port PORT]

# Default: http://localhost:8000
wire-tune

# Custom port
wire-tune --port 8080
```

## wire-pipeline

Run the detection pipeline on a single image.

```bash
wire-pipeline <image_path> [--params PARAMS_JSON]

# Run with default params
wire-pipeline schematic.jpg

# Custom params
wire-pipeline schematic.jpg \
  --params '{"threshold": {"mode": "otsu"}, "dilate": {"kernel_size": 3}}'

# Output JSON
wire-pipeline schematic.jpg --json
```

## wire-sdg

Generate synthetic dataset.

```bash
wire-sdg --num-images NUM --output-dir DIR

# Full options
wire-sdg \
  --num-images 1000 \
  --image-size 640 640 \
  --wires-per-image 3 15 \
  --wire-width 1 4 \
  --backgrounds plain grid \
  --label-format yolov8_pose \
  --seed 42 \
  --output-dir data/synthetic
```

## wire-eval

Evaluate detections against ground truth.

```bash
wire-eval --dataset <key> [--backend <name>]

# Evaluate with default pipeline
wire-eval --dataset hand_drawn

# Specific backend with custom params
wire-eval \
  --dataset hand_drawn \
  --backend contour \
  --params '{"dilate": {"kernel_size": 7}}' \
  --dist-thresh 15

# Output report
wire-eval --dataset hand_drawn --output report.csv
```

## wire-sweep

Run a parameter sweep.

```bash
wire-sweep [--preset <name>] [--dataset <key>]

# Predefined preset
wire-sweep --preset baseline

# Custom sweep
wire-sweep \
  --dataset synthetic \
  --max-images 200 \
  --variable '{"dilate.kernel_size": [3, 5, 7, 9]}' \
  --metric f1 \
  --parallel 4

# Resume interrupted sweep
wire-sweep --resume /path/to/checkpoint.json
```

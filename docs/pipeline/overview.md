# Pipeline Overview

The detection pipeline is a chain of composable stages that convert an input circuit schematic image into a list of detected line segments. Each stage is independently benchmarkable and swappable.

## How It Works

1. A `Pipeline` is constructed from a list of `PipelineStage` instances
2. `pipeline.run(image, params)` executes stages sequentially, passing intermediate results
3. Each stage's output is collected for visualization
4. The final result contains detected lines, per-stage outputs, and timing

## PipelineFactory

Pipelines are built from config dicts or YAML via `PipelineFactory`:

```python
from wire_detection.pipeline.factory import PipelineFactory

pipeline = PipelineFactory.from_config({
    "stages": ["crop", "mask", "threshold", "invert", "dilate",
               "ccl", "contour_extract", "dedup", "length_filter"],
    "crop": {"padding": 10},
    "threshold": {"mode": "otsu"},
    "dilate": {"kernel_size": 5, "iterations": 1},
    "ccl": {"min_area": 30},
    "dedup": {"angle": 10, "dist": 12},
    "length_filter": {"min_length": 20},
})

result = pipeline.run(image)
```

## Default Pipeline

The 9-stage pipeline, executed in order:

| # | Stage | Purpose |
|---|-------|---------|
| 1 | `crop` | Crop to component bounding box region with padding |
| 2 | `mask` | Fill component polygons with white (occlude wires behind components) |
| 3 | `threshold` | Convert grayscale to binary (Otsu, manual, or adaptive) |
| 4 | `invert` | Bitwise NOT so wires become white on black |
| 5 | `dilate` | Morphological dilation to thicken thin wires |
| 6 | `ccl` | Connected component labeling, filter by minimum area |
| 7 | `contour_extract` | Extract one line segment per blob (farthest contour extremes) |
| 8 | `dedup` | Merge collinear/overlapping lines by angle + distance threshold |
| 9 | `length_filter` | Remove lines shorter than minimum length |

## Config-Driven

Every aspect of the pipeline is configurable:

```yaml
# config/sweeps.yaml
baseline:
  stages:
    - threshold
    - invert
    - dilate
    - ccl
    - contour_extract
    - dedup
    - length_filter
  threshold:
    mode: otsu
  dilate:
    kernel_size: 5
    iterations: 1
  ccl:
    min_area: 30
  dedup:
    angle: 10
    dist: 12
  length_filter:
    min_length: 20
```

## Result Type

```python
class PipelineResult(TypedDict):
    lines: list[Line]                     # Final detected lines
    raw_lines: list[Line]                 # Lines before dedup/filter
    blob_count: int
    stage_outputs: dict[str, np.ndarray]  # Intermediate images
    params_used: dict
    elapsed_ms: float
```

## Plugin Architecture

New stages and backends can be registered without modifying framework code:

```python
from wire_detection.pipeline.registry import register_stage

@register_stage("my_custom_stage")
class MyStage(PipelineStage):
    name = "my_custom_stage"
    def run(self, image, params):
        # custom logic
        return StageOutput(...)
```

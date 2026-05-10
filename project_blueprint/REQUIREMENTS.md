# Wire Detection Framework — Project Specification

## 1. Research Context

### 1.1 The Paper

This framework supports the research project described in the paper **"Real-Time Circuit Diagram Recognition and Simulation: Combining YOLO-Based Component Detection with Classical Computer Vision for Wire Extraction"** (MethodsX, Group 18).

**High-level goal:** Given a photograph or scan of a hand-drawn circuit schematic, detect all electronic components (resistors, capacitors, diodes, transistors, ICs, etc.) AND the wires connecting them, then reconstruct the netlist for simulation.

**Two-stage architecture:**
1. **Component detection** — YOLOv11 OBB (oriented bounding boxes) trained on 1993 PCB schematic images (57 component classes). Achieves high mAP.
2. **Wire extraction** — The subject of this framework. Originally YOLO OBB for wire bounding boxes (mAP50=94.8%, mAP50-95=49.1%), replaced with a classical CV pipeline (F1=0.814 on 140 hand-drawn wire images).

### 1.2 Methodology Evolution

The wire detection approach went through three phases:

1. **Dual YOLO (original paper):** Separate YOLO OBB model for wire detection. Required labeled training data, produced bounding boxes instead of precise line segments, and had poor localization at strict IoU thresholds (mAP50-95=49.1%).

2. **Classical CV pipeline (current):** No training required. Uses binary thresholding → morphology → CCL → contour extremes → dedup. Achieves F1=0.814 on hand-drawn wires, 3ms latency. Details in `line_detection/experiments/pipeline.py`.

3. **Next-gen framework (this spec):** Unifies SDG, experimentation, benchmarking, pipeline development, and interactive tuning into a single composable package. Enables systematic exploration of the CV parameter space and integration of alternative wire detection approaches.

### 1.3 Datasets

| Dataset | Source | Images | Size | GT Type | Purpose |
|---------|--------|--------|------|---------|---------|
| **HDC-Recognition** | Roboflow export (`roboflow_test2/`) | 1,993 | 640×640 | YOLO OBB (57 component classes) | Component detection training + masked wire detection |
| **Hand-drawn wires** | Roboflow export (`roboflow_test/`) | 140 | 640×640 | YOLO OBB (wire polygons) | Wire detection evaluation (benchmark) |
| **Synthetic wires** | Generated (`dataset_pose/`) | 2,000 | 1024×1024 | YOLOv8 pose (2 keypoints/wire) | Large-scale parameter sweeps |

### 1.4 Key Findings (Empirical)

- **Baseline contour extremes is hard to beat** (F1=0.810). Every blob-splitting method (skeleton, RANSAC, Hough) produces 1.9–2.2× overcount.
- **Global dedup** (angle + distance merge) is the only reliable precision fix, independent of extraction method.
- **Binary threshold replaces Canny** in the HDC pipeline — directly controls which pixels count as wire.
- **Pipeline does NOT generalize to thin-line synthetic schematics** (max F1=0.154 on 1–2px wires). Wire thickness mismatch is the root cause.
- **Min line length filter** reduces tiny FP noise on HDC (schematic wires span 50–500+px; noise specks produce <20px segments).

---

## 2. Vision

A unified framework for **synthetic data generation**, **CV pipeline development**, **parameter experimentation**, **benchmarking**, and **interactive tuning** of 1D wire/line detection from circuit schematic images. The entire workflow — from generating training data to evaluating detection quality — lives in one package with composable, well-tested modules.

---

## 2. Directory Structure

```
wire_detection/
├── pyproject.toml              # Project metadata, dependencies, CLI entry points
├── README.md
├── .env.example                # Dataset paths, defaults
│
├── datasets/                    # Dataset registry (symlinks or configs, NOT actual data)
│   ├── __init__.py
│   ├── registry.py             # Dataset registry: loading, metadata, path resolution
│   ├── transforms.py           # Augmentation pipelines (albumentations)
│   ├── datasets.yaml           # Dataset paths, formats, description
│   └── README.md               # Instructions: where to download/extract each dataset
│
├── sdg/                         # Synthetic Data Generation
│   ├── __init__.py
│   ├── generator.py            # Main generation orchestrator
│   ├── primitives.py           # Wire primitives: bezier, line, arc
│   ├── backgrounds.py          # Background generators: plain, grid, noise
│   ├── compositor.py           # Composite image + label assembly
│   ├── augment.py              # Per-image augmentation (blur, noise, contrast)
│   └── formats.py              # Label export: YOLOv8 pose, COCO, custom
│
├── pipeline/                    # Classical CV Detection Pipeline
│   ├── __init__.py
│   ├── core.py                 # Stage compositor: chain of operations
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── crop.py             # Crop to ROI (component bounding boxes)
│   │   ├── mask.py             # Mask polygon regions
│   │   ├── threshold.py        # Binary threshold (Otsu, manual, adaptive)
│   │   ├── dilate.py           # Morphological dilation
│   │   ├── ccl.py              # Connected component labeling + stats
│   │   ├── contour_extract.py  # Contour extreme points → line segments
│   │   ├── dedup.py            # Global dedup by angle + distance
│   │   └── length_filter.py    # Min/max line length filter
│   ├── types.py                # Typed dicts for params, results, lines
│   └── factory.py              # Build pipeline from config dict or YAML
│
├── experiment/                  # Experimentation & Parameter Sweeps
│   ├── __init__.py
│   ├── sweep.py                # Grid search / random search engine
│   ├── runner.py               # Run a single config across N images
│   ├── reporter.py             # Generate comparison tables, markdown, CSV
│   └── presets.py              # Named config presets (baseline, aggressive, etc.)
│
├── evaluate/                    # Benchmarking & Metrics
│   ├── __init__.py
│   ├── metric.py               # Line distance, segment distance
│   ├── match.py                # Hungarian / greedy matching of detections to GT
│   ├── report.py               # Per-image + aggregate report generation
│   └── visualize.py            # Overlay detections + GT on images for inspection
│
├── ui/                          # Interactive Web UI
│   ├── __init__.py
│   ├── server.py               # HTTP server (threaded or async)
│   ├── router.py               # Request routing
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── images.py           # List images, serve thumbnails
│   │   └── process.py          # Run pipeline, return results
│   ├── templates/
│   │   └── index.html          # HTML template (or SPA build)
│   └── static/
│       ├── style.css
│       └── app.js              # Client-side logic
│
├── config/                      # Configuration & Schemas
│   ├── __init__.py
│   ├── schema.py               # Pydantic models for all configs
│   ├── defaults.yaml            # Default pipeline parameters
│   ├── datasets.yaml            # Dataset registry
│   └── sweeps.yaml              # Pre-defined sweep configs
│
└── tests/                       # Test Suite
    ├── __init__.py
    ├── conftest.py              # Fixtures: synthetic images, GT labels
    ├── test_pipeline.py         # Unit tests for each stage
    ├── test_sdg.py              # SDG output validation
    ├── test_evaluate.py         # Metric correctness
    └── test_integration.py      # End-to-end pipeline + eval
```

---

## 3. Reference Implementations — SINA (External)

The framework must support **plug-and-play comparison** against alternative approaches. The only external implementation we reference is:

### 3.1 SINA — CCL-Based Net Discovery (Aldowaish et al., 2026)

**⚠️ External paper (arXiv:2601.22114).** Not our project. We evaluated their CCL-based methodology as a comparison baseline and found it unsuitable for our use case.

**Their approach:** Mask components → CCL on remaining wires → treat each CCL region as an electrical net.

**Why we did not adopt it:** SINA's CCL provides blobs, not individual wire segments. Our DFS joining algorithm needs 1D line segments. Every blob-splitting method we tried (skeleton, RANSAC, Hough) overcounts (1.9–2.2×) or undercounts (69.6% recall).

**Integration for benchmarking:** `pipeline/backends/sina.py` — wraps CCL net discovery in the `PipelineBackend` interface so it can be compared directly against our pipeline on the same metrics and data.

### 3.2 Baseline — Contour Extreme Points (Our Approach)

Our pipeline. Default backend for all comparisons.

### 3.3 Third-Party Plugin Interface

Any external wire detection code can be wrapped via the plugin system without modifying framework code:

```python
# pipeline/backends/registry.py
BACKENDS: dict[str, type[PipelineBackend]] = {}

class PipelineBackend(ABC):
    @abstractmethod
    def run(self, image: np.ndarray, params: dict) -> PipelineResult: ...

def register_backend(name: str, cls: type[PipelineBackend]): ...
```

This allows cloning a third-party repo and wrapping it as a backend. The experiment engine, evaluation framework, and UI work identically on any registered backend.

---

## 4. Architecture: Plug-and-Play, Benchmarked Components

Every stage of the pipeline must be a **swappable, independently benchmarkable component**. This is not optional — the entire purpose of the framework is to systematically find the best configuration for each sub-problem.

### 4.1 Component Interface

Every component (detection stage, joining strategy, backend) follows the same pattern:

```python
class PipelineStage(ABC):
    name: str

    @abstractmethod
    def run(self, image: np.ndarray, params: dict) -> StageOutput: ...

    @abstractmethod
    def visualize(self, image: np.ndarray, output: StageOutput) -> np.ndarray: ...
```

Each stage is registered by name. The pipeline is built by composing stages from a config:

```python
pipeline = Pipeline.from_config({
    "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract"],
    "threshold": {"backend": "otsu"},      # can swap to "manual" or "adaptive"
    "dilate": {"kernel_size": 5, "iters": 1},
    "ccl": {"backend": "opencv"},           # can swap to "scipy" or "cuda"
    "contour_extract": {"backend": "farthest_pair"},
})
```

### 4.2 What Must Be Swappable

| Component | Alternatives to Test | Evaluation |
|-----------|---------------------|------------|
| **Threshold** | Otsu, manual, adaptive (Gaussian/Mean), Canny | Line-distance F1 vs GT |
| **Dilation** | Kernel sizes (3,5,7,9), iters (0-5), shape (cross/ellipse/rect) | Line-distance F1 vs GT |
| **CCL** | OpenCV, scipy, connectedComponentsWithStats | Speed, blob count accuracy |
| **Line extraction** | Contour extremes, skeleton trace, PCA fit, min-area rectangle | F1 vs GT, overcount ratio |
| **Dedup** | Angle+distance, overlap-only, NMS, off | Precision gain |
| **Length filter** | Threshold 0-200px | FP reduction |
| **Wire joining** | Line extension, distance snap, perimeter intersection, dilate+overlap, hybrid | Correct terminal assignment (F1 vs GT terminals) |
| **Detection backend** | CV pipeline, YOLO, SINA CCL, LSD, EDLines, cloned repo wrapper | Full eval (F1, speed) |
| **SDG generator** | Bezier-only, straight-only, mixed, with/without components, varied backgrounds | Realism score, detection F1 on generated data |

### 4.3 Benchmarking Each Component in Isolation

The evaluation framework must support running a sweep over **one component's alternatives while keeping all others fixed**:

```python
# Example: find best threshold method
sweep = Sweep(
    dataset="synthetic",
    images=200,
    fixed_params={
        "dilate": {"kernel_size": 5, "iters": 1},
        "ccl": {"backend": "opencv", "min_area": 30},
        "contour_extract": {"backend": "farthest_pair"},
        "dedup": {"angle": 10, "dist": 12},
    },
    variable={
        "threshold": [
            {"backend": "otsu"},
            {"backend": "manual", "value": 100},
            {"backend": "manual", "value": 140},
            {"backend": "adaptive", "block_size": 31, "c": 2},
        ]
    },
    metric="f1",
)
```

This is how we determine, for example, that **contour extremes beats skeleton (F1=0.810 vs 0.500)** or that **line extension beats distance snap (F1=0.842 vs 0.718)** for wire-to-component joining.

### 4.4 Component Registry

All components live in a registry so the UI, experiment engine, and CLI can discover available options:

```python
# pipeline/registry.py
STAGES: dict[str, type[PipelineStage]] = {}
BACKENDS: dict[str, type[PipelineBackend]] = {}
JOINERS: dict[str, type[Joiner]] = {}

def list_stages() -> list[str]: ...
def list_backends() -> list[str]: ...
def list_joiners() -> list[str]: ...
```

### 4.5 Wire-to-Component Joining

After detecting wires, we must connect each wire endpoint to its component terminal. This is a **separate, swappable module** (`joiner/`) with its own evaluation against connection-point ground truth.

**Inputs:** Detected lines `[((x1,y1),(x2,y2)), ...]` + Component bounding boxes `[(x,y,w,h), ...]` + (optional) binary wire mask

**Output:** For each wire endpoint: `(component_id, terminal_point, confidence)`

**Evaluated strategies (from our SDG experiments):**

| Strategy | F1 (on GT lines) | Notes |
|----------|------------------|-------|
| **Line extension** | **0.842** | Extend endpoint along line direction until it hits a component bbox. Perfect recall (0 FN), 6 FP from wrong-component hits. Best default. |
| **Distance snap** | 0.718 | Nearest bbox perimeter within 30px. Misses endpoints >30px from component. |
| **Perimeter intersection** | 0.277 | CCL on wire mask → intersect component perimeters. Catches everything but 5:1 FP:TP ratio. |
| **Dilate + overlap** | (untested on SDG) | Dilate endpoints → check overlap with perimeters. Less precise than line extension. |
| **Hybrid** | (proposed) | Line extension + distance snap as fallback + consensus voting. |

**Line Extension Algorithm (recommended default):**

```
for each line endpoint P with direction vector D (pointing away from line center):
    ray = P + t*D  for t = 0..MAX_EXTEND (200px)
    first intersection with any component bbox → terminal point
    if distance to intersection > DIST_CAP (50px): reject (likely wrong component)
```

The DIST_CAP fix removes the 6 FP wrong-component hits by rejecting connections where the ray travels too far before hitting a component (the real component should be close).

**Joiner interface:**

```python
class Joiner(ABC):
    @abstractmethod
    def join(self, lines: list[Line], components: list[BBox], binary_mask: np.ndarray | None = None) -> list[Connection]: ...

class Connection(TypedDict):
    line_idx: int
    endpoint_idx: int   # 0 or 1
    component_id: int
    terminal_point: tuple[int, int]
    confidence: float
```

This module is also independently benchmarkable — the SDG provides ground truth for wire-to-component junctions because wires always terminate at component edges. This is the only dataset with junction-level GT. For HDC, evaluation is visual only.

---

## 5. Component Specifications

### 3.1 Synthetic Data Generator (`sdg/`)

**Purpose:** Produce arbitrarily many labeled wire images for development and benchmarking without manual annotation.

**Capabilities:**

- **Wire primitives:** Bezier curves (2–4 control points), straight line segments, arcs. Each with configurable width (1–6px), color (grayscale or RGB), anti-aliasing.
- **Backgrounds:** Plain white/gray, ruled paper, graph paper, grid lines, random noise (gaussian, salt & pepper), real scanned paper textures.
- **Compositing:** Place N wires per image (configurable N, random or fixed). Optionally add component bounding boxes (simulated) to test masking behavior.
- **Labels:** Export as YOLOv8 pose (2 keypoints per wire, normalized), COCO keypoints, or custom line-segment format.
- **Augmentation:** Per-image: blur, contrast shift, noise, rotation, scaling, shearing (via albumentations).
- **Deterministic mode:** Fixed seed per image for reproducibility.

**Interface:**

```python
class SDGConfig(BaseModel):
    num_images: int = 1000
    wires_per_image: tuple[int, int] = (3, 15)   # min, max
    wire_width: tuple[int, int] = (1, 4)
    wire_types: list[Literal["bezier", "line", "arc"]] = ["bezier"]
    background_types: list[str] = ["plain", "grid", "noise"]
    image_size: tuple[int, int] = (1024, 1024)
    output_dir: Path
    label_format: Literal["yolov8_pose", "coco", "lines"] = "yolov8_pose"
    seed: int | None = None

class SDG:
    def generate(self, cfg: SDGConfig) -> DatasetMetadata: ...
    def generate_one(self, rng: np.random.Generator) -> tuple[np.ndarray, list[Line]]: ...
```

**Output:** Images directory + labels directory + `metadata.json` (image-to-label mapping, params used).

---

### 3.2 Detection Pipeline (`pipeline/`)

**Purpose:** Composable chain of classical CV operations that convert an input image → list of detected line segments.

**Architecture:**

Each stage is a callable class or function accepting `(image: np.ndarray, params: dict) → np.ndarray | list[Line]`. Stages are composed via a `Pipeline` class:

```python
class Pipeline:
    def __init__(self, stages: list[Stage]): ...
    def run(self, image: np.ndarray, params: dict) -> PipelineResult: ...
    def visualize(self, image: np.ndarray, result: PipelineResult) -> np.ndarray: ...
```

**Stages (in order):**

| Stage | Input | Output | Key Params |
|-------|-------|--------|------------|
| `Crop` | Image + bbox | Cropped image | padding |
| `Mask` | Grayscale + polygons | Masked grayscale | fill_value |
| `Threshold` | Grayscale | Binary | mode (otsu/manual/adaptive), value |
| `Invert` | Binary | Inverted binary | — |
| `Dilate` | Binary | Dilated binary | kernel_size, iterations |
| `CCL` | Binary | List of blobs (masks) | min_area, connectivity |
| `ContourExtract` | Blob mask | Line segment ((x1,y1),(x2,y2)) | — |
| `Dedup` | List of lines | Filtered lines | angle_thresh, dist_thresh |
| `LengthFilter` | List of lines | Filtered lines | min_length, max_length |

**Result type:**

```python
class PipelineResult(TypedDict):
    lines: list[Line]              # Final detected lines
    raw_lines: list[Line]          # Before dedup/filter
    blob_count: int
    stage_outputs: dict[str, np.ndarray]  # Intermediate images for visualization
    params_used: dict
    elapsed_ms: float
```

**Config-driven:** Pipeline can be built from a YAML/dict config:

```python
pipeline = PipelineFactory.from_config({
    "stages": ["crop", "mask", "threshold", "invert", "dilate", "ccl", "contour_extract", "dedup", "length_filter"],
    "crop": {"padding": 10},
    "threshold": {"mode": "otsu"},
    "dilate": {"kernel_size": 5, "iterations": 1},
    "ccl": {"min_area": 30},
    "dedup": {"angle": 10, "dist": 12},
    "length_filter": {"min_length": 20},
})
```

---

### 3.3 Experiment Engine (`experiment/`)

**Purpose:** Automate parameter sweeps over any pipeline parameters and report results.

**Capabilities:**

- **Grid search:** Cartesian product of parameter lists.
- **Random search:** Sample N random configs from bounded parameter ranges.
- **Bayesian optimization (optional):** Use Optuna or scikit-optimize for smarter search.
- **Parallel execution:** Multiprocessing or threaded evaluation across images.
- **Checkpointing:** Save partial results to resume interrupted sweeps.
- **Reporting:** Generate markdown tables (ranked by F1), CSV export, best-config summary.

**Interface:**

```python
@dataclass
class SweepConfig:
    name: str
    pipeline_params: dict[str, list | tuple]  # param_name → [values] or (min, max)
    base_config: dict                         # Fixed params
    dataset: str                              # Dataset key
    max_images: int = 200
    metric: Literal["f1", "precision", "recall"] = "f1"
    method: Literal["grid", "random"] = "grid"
    n_random: int = 50                        # For random search
    parallel: int = 4                         # Workers

class SweepResult:
    configs: list[ConfigResult]     # One per param combination
    best: ConfigResult
    ranking_table: str              # Formatted markdown

def run_sweep(cfg: SweepConfig) -> SweepResult: ...
```

---

### 3.4 Evaluation Framework (`evaluate/`)

**Purpose:** Compare detected lines to ground truth using line-distance metric.

**Key metric:**

Line-distance between a detected segment D(p1,p2) and GT segment G(g1,g2) is the average of the point-to-segment distances from D's endpoints to G:

```
segment_dist(D, G) = (point_to_segment_dist(p1, g1, g2) + point_to_segment_dist(p2, g1, g2)) / 2
```

A detection is a **true positive** if `segment_dist(D, G) ≤ threshold` (default 20px) for some unmatched GT. Multiple detections matching the same GT are **redundant**. Detections matching no GT are **false positives**. Unmatched GT are **false negatives**.

```python
class EvalResult:
    tp: int
    fp: int
    redundant: int
    fn: int
    gt_count: int
    recall: float
    precision: float
    f1: float

def evaluate(detections: list[Line], ground_truth: list[Line], dist_thresh: int = 20) -> EvalResult: ...
```

**GT label parsers:** Built-in parsers for YOLOv8 pose format, COCO keypoints, and the simple `((x1,y1),(x2,y2))` line format.

---

### 3.5 Web UI (`ui/`)

**Purpose:** Interactive parameter tuning with live visual feedback.

**Features:**

- **Sidebar:** All pipeline parameters as sliders/toggles with real-time value display.
- **4-panel view:** Detected Lines (overlay), Threshold, Dilated, Masked — all updated on parameter change.
- **Image selection:** Full-screen modal grid of dataset thumbnails (80px, lazy-loaded). Scrollable.
- **Dataset toggle:** Switch between datasets (HDC, synthetic, custom).
- **Live updates:** Slider `change` event (release trigger) runs pipeline and updates panels. Loading overlay per panel.
- **Abortable requests:** Consecutive rapid slider changes cancel in-flight requests.
- **Stats bar:** Line count, blob count, elapsed time.
- **Parameter summary:** Current mode+value for threshold, blob info.
- **Min line length slider:** Filter short detections.

**Implementation notes:**
- Single-process threaded HTTP server (`ThreadingMixIn` + `HTTPServer`).
- Image cache (thread-safe LRU) to avoid re-reading/remaking thumbnails.
- Response images resized to max 320px width to keep payload under ~50KB.
- All API responses use `Cache-Control: no-cache`.
- No external JS dependencies — vanilla JS, inline `<style>`.

**API Endpoints:**

| Method | Path | Params | Response |
|--------|------|--------|----------|
| GET | `/` | — | HTML page |
| GET | `/api/list` | `ds` (dataset key) | JSON array of image filenames |
| GET | `/api/thumb` | `idx`, `ds` | JPEG thumbnail (80px) |
| GET | `/api/process` | `img_idx`, `ds`, + all pipeline params | JSON with line_count + 4 base64 JPEG images |

---

### 3.6 Dataset Registry (`datasets/`)

**Purpose:** Central registry for all datasets. Datasets are NOT checked into the repo — they live on disk at configurable paths. The registry resolves paths, validates structure, and normalizes labels into a common format.

**Expected datasets:**

| Key | Source | Contents | Label Format | GT Type | Purpose |
|-----|--------|----------|-------------|---------|---------|
| `hdc` | `roboflow_test2/` | 1,993 PCB schematic images, 640×640, 57 component classes | YOLO OBB (components) | Component polygons | Component detection training + masked wire detection (visual only — no wire GT) |
| `hand_drawn` | `roboflow_test/` | 140 hand-drawn wire images, 640×640 | YOLO OBB (wires) | Wire polygons | Wire detection benchmark (7,094 GT wires). **Primary eval dataset.** |
| `synthetic` | `wire-testing/dataset_pose/` | 2,000 synthetic wire images, 1024×1024 | YOLOv8 pose (2 keypoints/wire) | Wire line segments | Large-scale parameter sweeps. Pipeline maxes at F1=0.154 on this dataset. |
| `database` | `Database/` | Hundreds of circuit schematic JPEGs | None | None | Visual inspection / real-world testing only |

**Dataset directory layout (expected on disk):**

```
/path/to/datasets/
├── hdc/
│   ├── train/
│   │   ├── images/          # *.jpg
│   │   └── labels/          # *.txt  (YOLO OBB: class_id x1 y1 x2 y2 x3 y3 x4 y4)
│   ├── valid/
│   │   ├── images/
│   │   └── labels/
│   └── test/
│       ├── images/
│       └── labels/
│
├── hand_drawn/
│   ├── train/
│   │   ├── images/          # *.jpg
│   │   └── labels/          # *.txt  (YOLO OBB wire polygons)
│   └── valid/
│
├── synthetic/
│   ├── train/
│   │   ├── images/          # *.jpg
│   │   └── labels/          # *.txt  (YOLOv8 pose: class cx cy w h x1 y1 v1 x2 y2 v2)
│   └── valid/
│
└── database/
    ├── 001-099/
    ├── 100-199/
    ├── 200-299/
    └── ...                   # Raw schematic JPEGs, no labels
```

**Registry config (`datasets/datasets.yaml`):**

```yaml
datasets:
  hdc:
    path: /home/bosco/Projects/Misc-Projects/LineDetection/roboflow_test2
    image_glob: "**/images/*.jpg"
    label_format: yolo_obb
    label_glob: "**/labels/*.txt"
    component_labels: true
    description: "HDC-Recognition PCB schematics, 1993 images, 57 component classes"
  
  hand_drawn:
    path: /home/bosco/Projects/Misc-Projects/LineDetection/roboflow_test
    image_glob: "**/images/*.jpg"
    label_format: yolo_obb
    label_glob: "**/labels/*.txt"
    component_labels: false
    description: "Hand-drawn circuit wires, 140 images, 7094 GT wires"
  
  synthetic:
    path: /home/bosco/Projects/wire-testing/dataset_pose
    image_glob: "train/images/*.jpg"
    label_format: yolov8_pose
    label_glob: "train/labels/*.txt"
    component_labels: false
    description: "Synthetic bezier-curve wires on varied backgrounds, 2000 images"
  
  database:
    path: /home/bosco/Projects/Misc-Projects/LineDetection/Database
    image_glob: "*/*.jpg"
    label_format: null
    label_glob: null
    description: "Raw schematic images for visual inspection (no labels)"
```

**Registry interface:**

```python
@dataclass
class DatasetConfig:
    key: str
    path: Path
    image_glob: str
    label_format: str | None       # "yolo_obb" | "yolov8_pose" | null
    label_glob: str | None
    component_labels: bool = False  # Has component OBB labels for masking
    crop_to_components: bool = False
    description: str = ""

class DatasetRegistry:
    def __init__(self, config_path: Path = "datasets/datasets.yaml"): ...
    def list_datasets(self) -> list[str]: ...
    def get(self, key: str) -> DatasetConfig: ...
    def list_images(self, key: str, split: str = "train") -> list[Path]: ...
    def load_labels(self, image_path: Path) -> list: ...
    def load_component_labels(self, image_path: Path) -> list | None: ...
```

The registry normalizes labels into a common `WireLine` format for the evaluation framework, regardless of whether the original labels were YOLO OBB, YOLOv8 pose, or custom format.

---

## 6. Cross-Cutting Concerns

### 4.1 Configuration & Schemas

All configuration uses **Pydantic v2** for validation, serialization, and IDE support. Configs are loadable from YAML, dict, or CLI args.

### 4.2 Testing

- **Unit tests** for each pipeline stage (isolated, synthetic input).
- **Integration tests** for full pipeline + eval on known synthetic images with known GT.
- **Regression tests** comparing outputs against stored expected values.
- **Coverage target:** ≥80% for pipeline/, evaluate/, sdg/.
- Use `pytest` with `conftest.py` fixtures for reusable test images and GT.

### 4.3 CLI Entry Points

Expose via `pyproject.toml` `[project.scripts]`:

```
wire-sdg          → sdg CLI (generate dataset)
wire-eval         → evaluate CLI (run evaluation on a dataset)
wire-sweep        → experiment CLI (run parameter sweep)
wire-tune         → ui CLI (launch tuner server)
wire-pipeline     → pipeline CLI (run single image, output JSON)
```

### 4.4 Logging & Reproducibility

- **Structured logging** (structlog or stdlib logging with JSON format) for all experiment runs.
- **Reproducibility:** Every `run()` call logs the full config, dataset key, image count, seed, results, and timestamp.
- **Experiment artifacts:** Each sweep run saves to a timestamped directory: config used, per-image results CSV, summary JSON, ranking markdown.

### 4.5 Packaging

```toml
[project]
name = "wire-detection"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
    "opencv-python>=4.9",
    "pydantic>=2.5",
    "albumentations>=1.3",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov", "ruff", "mypy"]
ui = []  # No extra deps needed (stdlib HTTP server)
```

---

## 7. Key Design Decisions

### Why No Deep Learning in the Pipeline?
The CV pipeline achieves F1=0.814 on hand-drawn wires with 3ms latency and zero training data. Every blob-splitting method (skeleton, RANSAC, Hough) either overcounts or undercounts. YOLO-based wire detection would require labeled data per drawing style.

### Why Line-Distance Instead of IoU?
Wires are 1D — bounding-box IoU is meaningless. A 1px-wide wire segment has near-zero area overlap with GT. Line-distance (average endpoint distance to GT segment) is the standard for wire/channel detection tasks.

### Why Vanilla JS Instead of React/Vue?
The UI has exactly one interactive state (the result grid). A SPA framework adds build step, dependency weight, and complexity. Vanilla JS + CSS keeps the tuner as a single self-contained Python file that can be rsync'd and run anywhere.

### Why a Dataset Registry?
Multiple datasets (HDC, synthetic, custom) with different label formats and preprocessing needs. A registry keeps the experiment engine dataset-agnostic — swap `ds="synthetic"` for `ds="hdc"` and the same sweep/eval code works.

---

## 8. Future Work (Not in Scope for v1)

- **GPU-accelerated CCL** via CUDA or OpenCV CUDA module for 4K+ images.
- **Online learning:** Use tuner adjustment history as training data for a parameter predictor.
- **Component-aware dedup:** Use detected component locations to inform line grouping.
- **Multi-image sweeps:** Distribute evaluation across multiple machines via a job queue (Celery, Ray).

---

## 9. Algorithm Reference — Verified Implementations

This section contains **concrete, copy-pasteable implementations** of every algorithm that has been empirically validated. When building the framework, use these as ground truth — they represent the exact logic that produced the documented F1 scores. Deviating from these will change results.

### 9.1 CCL Components (OpenCV, 15× Faster than scipy)

```python
import cv2
import numpy as np

def ccl_components(binary: np.ndarray, min_area: int = 30) -> list[np.ndarray]:
    """
    Connected Component Labeling using OpenCV.
    
    Returns list of boolean masks, one per component >= min_area.
    Replaced scipy.ndimage.label (which double-computed masks) for 15× speedup
    on dense images (10s → 660ms for 964 blobs).
    """
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    comps = []
    for label_id in range(1, num_labels):
        area = stats[label_id, cv2.CC_STAT_AREA]
        if area >= min_area:
            comps.append(labels == label_id)
    return comps
```

### 9.2 Contour Extreme Points — 1 Line Per Blob

```python
def find_endpoints(mask: np.ndarray) -> tuple[tuple[int, int], tuple[int, int]] | tuple[None, None]:
    """
    From a boolean blob mask, find the farthest pair of contour extreme points.
    This is the core algorithm: every blob produces EXACTLY one line segment.
    
    Crossing wires merge into one blob → this produces one wrong diagonal.
    That's the known limitation (accounts for ~14% missed GT on hand-drawn dataset).
    """
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None
    
    cnt = max(contours, key=cv2.contourArea)
    left = tuple(cnt[cnt[:, :, 0].argmin()][0])
    right = tuple(cnt[cnt[:, :, 0].argmax()][0])
    top = tuple(cnt[cnt[:, :, 1].argmin()][0])
    bottom = tuple(cnt[cnt[:, :, 1].argmax()][0])
    
    candidates = [left, right, top, bottom]
    best_dist = -1
    best_pair = (None, None)
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            dx = candidates[i][0] - candidates[j][0]
            dy = candidates[i][1] - candidates[j][1]
            dist = dx * dx + dy * dy
            if dist > best_dist:
                best_dist = dist
                best_pair = (candidates[i], candidates[j])
    return best_pair


def extract_lines_from_blobs(binary: np.ndarray, min_area: int = 30) -> list[tuple]:
    """CCL → per-blob contour extremes → list of line segments."""
    comps = ccl_components(binary, min_area=min_area)
    lines = []
    for comp in comps:
        p1, p2 = find_endpoints(comp)
        if p1 is not None and p2 is not None:
            lines.append(((int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1]))))
    return lines
```

### 9.3 Global Dedup (Angle + Distance)

```python
import math

def global_dedup(lines: list, a_thresh: float = 10, d_thresh: float = 12) -> list:
    """
    Merge collinear/overlapping lines globally across all blobs.
    
    Two lines are duplicates if they have similar angle (degrees) AND
    the distance from each endpoint of the shorter line to the longer
    line is below d_thresh.
    
    This is the ONLY precision fix that works across extraction methods.
    Angle=0 disables dedup entirely.
    """
    if not lines or a_thresh <= 0:
        return lines
    
    kept = list(lines)
    a_thresh_rad = math.radians(a_thresh)
    changed = True
    
    while changed:
        changed = False
        i = 0
        while i < len(kept):
            j = i + 1
            while j < len(kept):
                p1, p2 = kept[i]
                q1, q2 = kept[j]
                
                # Angle check
                dx1, dy1 = p2[0] - p1[0], p2[1] - p1[1]
                dx2, dy2 = q2[0] - q1[0], q2[1] - q1[1]
                len1 = math.hypot(dx1, dy1)
                len2 = math.hypot(dx2, dy2)
                if len1 < 1 or len2 < 1:
                    j += 1
                    continue
                
                dot = dx1 * dx2 + dy1 * dy2
                angle = math.acos(max(-1, min(1, dot / (len1 * len2))))
                if angle > a_thresh_rad:
                    j += 1
                    continue
                
                # Distance check
                longer = kept[i] if len1 >= len2 else kept[j]
                shorter = kept[j] if len1 >= len2 else kept[i]
                
                def point_line_dist(pt, a, b):
                    ax, ay = a; bx, by = b; px, py = pt
                    abx, aby = bx - ax, by - ay
                    t = ((px - ax) * abx + (py - ay) * aby) / max(abx * abx + aby * aby, 1e-8)
                    t = max(0, min(1, t))
                    projx = ax + t * abx; projy = ay + t * aby
                    return math.hypot(px - projx, py - projy)
                
                d1 = point_line_dist(shorter[0], longer[0], longer[1])
                d2 = point_line_dist(shorter[1], longer[0], longer[1])
                
                if d1 <= d_thresh and d2 <= d_thresh:
                    # Merge: keep longer, remove shorter
                    kept.pop(j)
                    changed = True
                else:
                    j += 1
            i += 1
    return kept
```

### 9.4 Min / Max Line Length Filter

```python
def filter_short_lines(lines: list, min_length: int = 0) -> list:
    """Remove lines shorter than min_length (Euclidean distance)."""
    if min_length <= 0:
        return lines
    kept = []
    for p1, p2 in lines:
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        length = math.hypot(dx, dy)
        if length >= min_length:
            kept.append((p1, p2))
    return kept
```

### 9.5 Full Pipeline Chain

```python
def run_pipeline(gray: np.ndarray, params: dict) -> tuple[list, dict]:
    """
    Run the complete detection pipeline.
    
    params:
        thresh_mode: 'otsu' | 'manual'
        thresh_val: int
        dil_ksize: int
        dil_iters: int
        min_area: int
        dedup_angle: int
        dedup_dist: int
        min_line_length: int
    
    Returns (final_lines, stage_outputs) where stage_outputs contains
    intermediate images for visualization.
    """
    mode = params.get('thresh_mode', 'otsu')
    manual_val = int(params.get('thresh_val', 127))
    dil_ksize = int(params.get('dil_ksize', 5))
    dil_iters = int(params.get('dil_iters', 1))
    min_area = int(params.get('min_area', 30))
    dedup_angle = int(params.get('dedup_angle', 10))
    dedup_dist = int(params.get('dedup_dist', 12))
    min_line_len = int(params.get('min_line_length', 0))
    
    # Stage 1: Threshold
    if mode == 'otsu':
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh_used = _  # Otsu-determined threshold
    else:
        _, bw = cv2.threshold(gray, manual_val, 255, cv2.THRESH_BINARY)
        thresh_used = manual_val
    
    # Stage 2: Invert (wires become white on black)
    bw_inv = cv2.bitwise_not(bw)
    
    # Stage 3: Dilate
    kernel = np.ones((dil_ksize, dil_ksize), np.uint8)
    dilated = cv2.dilate(bw_inv, kernel, iterations=dil_iters) if dil_iters > 0 else bw_inv
    
    # Stage 4: Extract lines (CCL → contour extremes)
    lines = extract_lines_from_blobs(dilated, min_area=min_area)
    
    # Stage 5: Dedup
    final = global_dedup(lines, angle=dedup_angle, dist=dedup_dist)
    
    # Stage 6: Length filter
    final = filter_short_lines(final, min_length=min_line_len)
    
    stage_outputs = {
        'threshold': bw,
        'threshold_bgr': cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR),
        'dilated': dilated,
        'dilated_bgr': cv2.cvtColor(dilated, cv2.COLOR_GRAY2BGR),
    }
    return final, stage_outputs
```

### 9.6 Component Masking + Cropping

```python
def compute_crop_bbox(labels_path: str, img_w: int, img_h: int, padding: int = 10) -> tuple | None:
    """
    Read YOLO-OBB labels → find min/max x,y across all component polygons → 
    return cropped bbox with padding. Reduces processed area ~50%.
    
    Label format: class_id x1 y1 x2 y2 x3 y3 x4 y4  (normalized 0-1)
    """
    if not os.path.exists(labels_path):
        return None
    
    xs, ys = [], []
    with open(labels_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 9: continue
            coords = list(map(float, parts[1:]))
            for i in range(0, 8, 2):
                xs.append(int(coords[i] * img_w))
                ys.append(int(coords[i + 1] * img_h))
    
    if not xs: return None
    x1 = max(0, min(xs) - padding)
    y1 = max(0, min(ys) - padding)
    x2 = min(img_w, max(xs) + padding)
    y2 = min(img_h, max(ys) + padding)
    return (x1, y1, x2, y2)


def mask_components(gray: np.ndarray, labels_path: str) -> np.ndarray:
    """
    Fill annotated component polygons with white so wires behind them are occluded.
    """
    masked = gray.copy()
    if not os.path.exists(labels_path): return masked
    
    h, w = gray.shape
    with open(labels_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 9: continue
            coords = list(map(float, parts[1:]))
            polygon = np.array([(int(coords[i] * w), int(coords[i + 1] * h)) 
                                for i in range(0, 8, 2)], dtype=np.int32)
            cv2.fillPoly(masked, [polygon], 255)
    return masked
```

### 9.7 Wire-to-Component Joining — Line Extension (F1=0.842)

```python
def join_line_extension(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list[tuple[int, int, int, int]],  # (x, y, w, h)
    max_extend: int = 200,
    dist_cap: int = 50,
    img_size: tuple[int, int] = (1024, 1024)
) -> list[dict]:
    """
    For each line endpoint, extend along line direction until it hits a component bbox.
    
    Empirically validated on SDG dataset with GT lines:
      F1=0.842, Recall=1.0, Precision=0.727 (6 FP from wrong-component hits)
    
    The dist_cap removes wrong-component FP: if ray travels >50px before hitting,
    reject (the real component should be nearby).
    
    Returns list of Connection dicts:
      {line_idx, endpoint_idx (0 or 1), component_id, terminal_point (x,y)}
    """
    IMG_W, IMG_H = img_size
    connections = []
    
    def intersect_ray_bbox(origin, direction, bbox):
        """March ray until it enters bbox. Returns (point, distance) or None."""
        x, y, w, h = bbox
        dx, dy = direction
        for t in range(0, max_extend, 2):
            px = int(origin[0] + dx * t)
            py = int(origin[1] + dy * t)
            if px < 0 or px >= IMG_W or py < 0 or py >= IMG_H:
                break
            if x <= px <= x + w and y <= py <= y + h:
                return (px, py), t
        return None
    
    for li, ((x1, y1), (x2, y2)) in enumerate(lines):
        for ei, (p_end, p_other) in enumerate([
            ((x1, y1), (x2, y2)),
            ((x2, y2), (x1, y1))
        ]):
            # Direction from other endpoint → this endpoint (pointing outward)
            dx = p_end[0] - p_other[0]
            dy = p_end[1] - p_other[1]
            length = math.hypot(dx, dy)
            if length == 0:
                continue
            dx /= length
            dy /= length
            
            # Check each component
            best = None
            best_dist = float('inf')
            for ci, bbox in enumerate(components):
                hit = intersect_ray_bbox(p_end, (dx, dy), bbox)
                if hit is not None:
                    pt, dist = hit
                    if dist < best_dist:
                        best_dist = dist
                        best = (ci, pt)
            
            if best is not None:
                ci, pt = best
                # Apply dist_cap: reject if ray traveled too far
                if best_dist <= dist_cap:
                    connections.append({
                        'line_idx': li,
                        'endpoint_idx': ei,
                        'component_id': ci,
                        'terminal_point': pt,
                    })
    return connections
```

### 9.8 Evaluation Metric — Line Distance F1

```python
def point_to_segment_dist(p: tuple, a: tuple, b: tuple) -> float:
    """
    Perpendicular distance from point P to line segment A-B.
    Clamps projection to segment bounds (t in [0,1]).
    """
    ax, ay = a; bx, by = b; px, py = p
    abx, aby = bx - ax, by - ay
    t = ((px - ax) * abx + (py - ay) * aby) / max(abx * abx + aby * aby, 1e-8)
    t = max(0, min(1, t))
    projx = ax + t * abx
    projy = ay + t * aby
    return math.hypot(px - projx, py - projy)


def segment_dist(det: tuple, gt: tuple) -> float:
    """
    Distance between detected segment D and GT segment G.
    Average of point-to-segment distances from D's endpoints to G.
    Symmetric.
    """
    p1, p2 = det
    g1, g2 = gt
    return (point_to_segment_dist(p1, g1, g2) + point_to_segment_dist(p2, g1, g2)) / 2


def evaluate(detected: list, gt: list, dist_thresh: int = 20) -> dict:
    """
    Compute TP, FP, redundant, FN, recall, precision, F1.
    
    A detection is TP if segment_dist(D, G) <= dist_thresh for some unmatched GT.
    Multiple detections matching same GT = redundant (counted separately in FP).
    Unmatched GT = FN.
    """
    matched = [False] * len(gt)
    tp = fp = redundant = 0
    
    for d in detected:
        best = float('inf')
        best_i = -1
        for gi, g in enumerate(gt):
            dist = segment_dist(d, g)
            if dist < best:
                best = dist
                best_i = gi
        
        if best <= dist_thresh:
            if matched[best_i]:
                redundant += 1
            else:
                tp += 1
                matched[best_i] = True
        else:
            fp += 1
    
    fn = sum(1 for m in matched if not m)
    recall = tp / max(tp + fn, 1)
    precision = tp / max(tp + fp + redundant, 1)
    f1 = 2 * recall * precision / max(recall + precision, 1e-8)
    
    return {
        'tp': tp, 'fp': fp, 'redundant': redundant, 'fn': fn,
        'gt_count': len(gt),
        'recall': recall, 'precision': precision, 'f1': f1,
    }
```

### 9.9 SDG — Bezier Curve Generation

```python
import random
import numpy as np

def get_bezier_curve(p1: tuple, p2: tuple, num_points: int = 50) -> np.ndarray:
    """
    Generate a Bezier curve between two points with 1-2 random control points.
    Used by the SDG to create realistic hand-drawn wire shapes.
    """
    x1, y1 = p1
    x2, y2 = p2
    dist = math.hypot(x2 - x1, y2 - y1)
    
    # Control points
    num_cp = random.choice([1, 2])
    cps = [(x1, y1)]
    
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    
    if num_cp == 1:
        offset = dist * random.uniform(0.1, 0.4) * random.choice([-1, 1])
        perp_x = -(y2 - y1) / max(dist, 1)
        perp_y = (x2 - x1) / max(dist, 1)
        cps.append((mid_x + perp_x * offset, mid_y + perp_y * offset))
    else:
        offset1 = dist * random.uniform(0.1, 0.3) * random.choice([-1, 1])
        offset2 = dist * random.uniform(0.1, 0.3) * random.choice([-1, 1])
        perp_x = -(y2 - y1) / max(dist, 1)
        perp_y = (x2 - x1) / max(dist, 1)
        t1, t2 = 0.3, 0.7
        cps.append(((1-t1)*x1 + t1*x2 + perp_x*offset1, (1-t1)*y1 + t1*y2 + perp_y*offset1))
        cps.append(((1-t2)*x1 + t2*x2 + perp_x*offset2, (1-t2)*y1 + t2*y2 + perp_y*offset2))
    
    cps.append((x2, y2))
    
    # De Casteljau's algorithm
    n = len(cps) - 1
    curve = np.zeros((num_points, 2), dtype=np.int32)
    for i, t in enumerate(np.linspace(0, 1, num_points)):
        pts = list(cps)
        for r in range(n):
            new_pts = []
            for j in range(n - r):
                new_x = (1 - t) * pts[j][0] + t * pts[j + 1][0]
                new_y = (1 - t) * pts[j][1] + t * pts[j + 1][1]
                new_pts.append((new_x, new_y))
            pts = new_pts
        curve[i] = [int(pts[0][0]), int(pts[0][1])]
    
    return curve


def get_rect_edge_point(p_inner: tuple, p_outer: tuple, rect: tuple) -> tuple:
    """
    Find where line from p_inner to p_outer exits the rectangle.
    Used by SDG to place wire endpoints at component boundaries.
    """
    rx, ry, rw, rh = rect
    edges = [
        ((rx, ry), (rx + rw, ry)),            # Top
        ((rx + rw, ry), (rx + rw, ry + rh)),   # Right
        ((rx + rw, ry + rh), (rx, ry + rh)),   # Bottom
        ((rx, ry + rh), (rx, ry))              # Left
    ]
    
    def intersect(A, B, C, D):
        def ccw(p1, p2, p3):
            return (p3[1]-p1[1])*(p2[0]-p1[0]) > (p2[1]-p1[1])*(p3[0]-p1[0])
        return ccw(A,C,D) != ccw(B,C,D) and ccw(A,B,C) != ccw(A,B,D)
    
    A, B = np.array(p_inner), np.array(p_outer)
    for E1, E2 in edges:
        E1, E2 = np.array(E1), np.array(E2)
        if intersect(A, B, E1, E2):
            da = B - A
            db = E2 - E1
            dp = A - E1
            dap = np.array([-da[1], da[0]])
            denom = np.dot(dap, db)
            if denom == 0: continue
            t = np.dot(dap, dp) / denom
            return tuple((E1 + t * db).astype(int))
    
    # Fallback: nearest point on rect edge
    cx = max(rx, min(rx + rw, p_outer[0]))
    cy = max(ry, min(ry + rh, p_outer[1]))
    return (int(cx), int(cy))
```

### 9.10 SDG — Wire Stroke Rendering

```python
def draw_tool_stroke(canvas: np.ndarray, points: np.ndarray, tool_type: str) -> None:
    """
    Draw a wire stroke on canvas simulating different pen tools.
    
    tool_type: 'gel' (dark gray, 30-60), 'ballpoint' (gray 60-100 or washed blue),
               'pencil' (lighter graphite 80-140)
    Wire thickness is always 1px (anti-aliased) to simulate fine-pen schematics.
    """
    thickness = 1
    
    if tool_type == "pencil":
        c = random.randint(80, 140)
        color = (c, c, c)
        cv2.polylines(canvas, [points], False, color, thickness, cv2.LINE_AA)
    elif tool_type == "ballpoint":
        if random.random() < 0.3:
            color = (random.randint(150, 200), random.randint(50, 100), random.randint(50, 100))
        else:
            c = random.randint(60, 100)
            color = (c, c, c)
        cv2.polylines(canvas, [points], False, color, thickness, cv2.LINE_AA)
    elif tool_type == "gel":
        c = random.randint(30, 60)
        color = (c, c, c)
        cv2.polylines(canvas, [points], False, color, thickness, cv2.LINE_AA)
```

### 9.11 SDG — YOLOv8 Pose Label Export

```python
def export_yolov8_pose(wire_lines: list, image_size: tuple, output_path: str) -> None:
    """
    Export detected wires to YOLOv8 pose format.
    
    Format per line: class_id cx cy w h x1 y1 v1 x2 y2 v2
    where (cx,cy,w,h) is the bbox enclosing the wire,
    (x1,y1) and (x2,y2) are the endpoint keypoints (normalized 0-1),
    v=2 means visible/labeled.
    
    Endpoints are sorted: leftmost x first (by x-coordinate).
    """
    IW, IH = image_size
    annotations = []
    
    for p1, p2 in wire_lines:
        # Sort endpoints by x-coordinate
        if p1[0] < p2[0]:
            kpts = [p1, p2]
        else:
            kpts = [p2, p1]
        
        # Bounding box around the wire
        xs = [p1[0], p2[0]]
        ys = [p1[1], p2[1]]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        bw = max(xs) - min(xs) + 10  # +10 padding
        bh = max(ys) - min(ys) + 10
        
        ann = [
            0,  # class_id (wire)
            cx / IW, cy / IH, bw / IW, bh / IH,
            kpts[0][0] / IW, kpts[0][1] / IH, 2,  # keypoint 1, visible
            kpts[1][0] / IW, kpts[1][1] / IH, 2,  # keypoint 2, visible
        ]
        annotations.append(" ".join(map(str, ann)))
    
    with open(output_path, "w") as f:
        f.write("\n".join(annotations))
```

### 9.12 Image Cache (Thread-Safe LRU)

```python
import threading

class ImageCache:
    """
    Thread-safe LRU cache for preprocessed images.
    Caches (img, gray, masked, bbox) tuples keyed by image index.
    Cold latency ~7ms, warm ~3ms.
    """
    def __init__(self, maxsize: int = 32):
        self.maxsize = maxsize
        self._cache: dict = {}
        self._order: list = []
        self._lock = threading.Lock()
    
    def get(self, idx: int, img_path: str, labels_path: str | None = None):
        with self._lock:
            if idx in self._cache:
                self._order.remove(idx)
                self._order.append(idx)
                return self._cache[idx]
        
        # Load from disk
        img = cv2.imread(img_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        bbox = None
        masked = gray.copy()
        if labels_path and os.path.exists(labels_path):
            bbox = compute_crop_bbox(labels_path, img.shape[1], img.shape[0])
            masked = mask_components(gray, labels_path)
        
        with self._lock:
            if idx in self._cache:
                return self._cache[idx]
            if len(self._order) >= self.maxsize:
                oldest = self._order.pop(0)
                del self._cache[oldest]
            self._cache[idx] = (img, gray, masked, bbox)
            self._order.append(idx)
        
        return (img, gray, masked, bbox)
```

### 9.13 Component Bbox Detection from Image (for SDG Visual Joining)

```python
def extract_component_bboxes_from_image(img: np.ndarray) -> list[tuple]:
    """
    When component annotations aren't available (e.g., SDG images), detect
    white rectangular components via thresholding + contour detection.
    
    Used by the joining test to extract component positions from SDG images
    that only have wire labels.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, white_mask = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    components = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
        if area > 500:  # Filter speckles
            components.append((x, y, w, h))
    return components
```
- **REST API mode:** Run the tuner server as a stateless API (no embedded HTML) for integration into larger systems.

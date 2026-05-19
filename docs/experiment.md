# Experiment Engine

The experiment engine automates parameter sweeps over any pipeline parameters and reports results ranked by F1 score.

## Usage

```bash
# Run a predefined sweep
wire-sweep --preset baseline

# Custom grid search
wire-sweep \
  --dataset synthetic \
  --max-images 200 \
  --variable '{"dilate.kernel_size": [3, 5, 7], "threshold.mode": ["otsu", "manual"]}'
```

## Capabilities

### Grid Search
Cartesian product of all parameter combinations:

```python
from wire_detection.experiment.sweep import SweepConfig, run_sweep

cfg = SweepConfig(
    name="threshold_comparison",
    dataset="hand_drawn",
    max_images=140,
    fixed_params={
        "dilate": {"kernel_size": 5, "iterations": 1},
        "ccl": {"min_area": 30},
        "dedup": {"angle": 10, "dist": 12},
    },
    variable={
        "threshold": [
            {"mode": "otsu"},
            {"mode": "manual", "value": 100},
            {"mode": "manual", "value": 140},
            {"mode": "adaptive", "block_size": 31, "c": 2},
        ]
    },
    metric="f1",
)

result = run_sweep(cfg)
print(result.ranking_table)
```

### Random Search
Sample N random configs from bounded ranges:

```python
cfg = SweepConfig(
    method="random",
    n_random=50,
    variable={
        "dilate": {"kernel_size": [3, 9], "iterations": [1, 3]},
        "ccl": {"min_area": [10, 100]},
    },
)
```

### Presets

Pre-defined configs for common scenarios:

| Preset | Description |
|--------|-------------|
| `baseline` | Default pipeline (Otsu, k5, i1, min_area=30, dedup_angle=10, dedup_dist=12) |
| `aggressive` | More dilation, lower area threshold |
| `conservative` | Less dilation, higher area threshold |
| `no_dedup` | Pipeline without dedup stage |
| `heavy_dilate` | Large kernel, multiple iterations |

## Final Results (May 2026)

Benchmark on 23 circuit schematic images (704×704) with 300 ground-truth wire segments. Evaluation: point-based F1 (endpoint distance ≤20px).

### Best Pipeline: Sauvola+CCL+Merge (Occluded)

```
occlude components → Sauvola k=0.3 (w=51) → close(ellipse 3×3) → CCL(min_area=20) → dedup(10°,18px) → length_filter(10px) → collinear_merge(10°,30px gap)
```

- **Global F1: 0.627** | **Avg F1: 0.576**
- Precision: **0.627** | Recall: **0.627**
- TP=188 FP=112 FN=112
- **+8% over previous best** (0.593), **+68% over original** (0.370)

### Strategy Comparison

| Strategy | Global F1 | TP | FP | FN | P | R |
|---|---|---|---|---|---|---|
| | **Sauvola+CCL+Merge (occluded)** | **0.627** | 188 | 112 | 112 | **0.627** | **0.627** |
| Sauvola+CCL (no merge, old params) | 0.508 | 134 | 94 | 166 | 0.588 | 0.447 |
| HoughLinesP + Canny | 0.415 | 156 | 295 | 144 | 0.346 | 0.520 |
| Old (strategy+close+ct+merge) | 0.370 | 86 | 79 | 214 | 0.521 | 0.287 |

### Key Insight

Three changes drove improvement:
1. **Collinear merge** — redundant fragments on the same GT line were counted as FPs (29%). Merge eliminates them.
2. **Sauvola k=0.3** (was 0.5) — more sensitive, catches thin traces.
3. **Relaxed close(3)/CCL(20)/len(10)** — captures thin wires previously filtered out.

### Best Config

```json
{"sauvola_k": 0.3, "sauvola_window": 51, "close_kernel": 3, "ccl_min_area": 20,
 "dedup_angle": 10, "dedup_dist": 18, "merge_angle": 10, "merge_gap": 30, "min_length": 10}
```

### Files

- Best config: `~/workspace/experiment_v7/best_config.json`
- Full sweep: `~/workspace/iterative_benchmark.py`
- Obsidian docs: `Knowledge_Base/01_Projects/Circuit Digitization/`

## Features

- **Checkpointing** — save partial results to resume interrupted sweeps
- **Parallel execution** — multiprocessing across images
- **Ranking tables** — markdown tables ranked by selected metric
- **CSV export** — full results for further analysis
- **Best-config summary** — top-N configs with all metrics

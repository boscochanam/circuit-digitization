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

## Features

- **Checkpointing** — save partial results to resume interrupted sweeps
- **Parallel execution** — multiprocessing across images
- **Ranking tables** — markdown tables ranked by selected metric
- **CSV export** — full results for further analysis
- **Best-config summary** — top-N configs with all metrics

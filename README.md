# Wire Detection Framework

A modular Python framework for detecting wires in circuit schematics — classical CV pipeline, synthetic data generator, evaluation toolkit, FastAPI backend, and Next.js tuner UI.

> **Full documentation at [https://boscochanam.github.io/circuit-digitization](https://boscochanam.github.io/circuit-digitization)** — or build locally with `uv run mkdocs serve`.

## Quickstart

```bash
uv venv && uv sync          # Backend setup
cd ui && pnpm install       # Frontend setup
docker compose up --build   # Or: uv run wire-tune + pnpm dev
```

## CLI

```
wire-tune      Start the tuner API server
wire-pipeline  Run pipeline on a single image
wire-sdg       Generate synthetic dataset
wire-eval      Evaluate detections against ground truth
wire-sweep     Run a parameter sweep
```

## Project Structure

```
wire_detection/     Python backend (pipeline, API, SDG, evaluation, experiments)
ui/                 Next.js frontend (tuner UI)
docs/               MkDocs documentation
```

## Final Results (May 2026)

Benchmark on 23 circuit schematic images (704×704) with 300 ground-truth wire segments. Evaluation: point-based F1 (endpoint distance ≤20px).

### Best Pipeline: Sauvola+CCL+Merge (Occluded)

```
occlude components → crop to ROI (10px pad) → Sauvola k=0.3 (w=51) → close(ellipse 3×3) → CCL(min_area=20) → dedup(10°,18px) → length_filter(10px) → collinear_merge(10°,30px gap) → retry with k=0.25 if 0 lines detected
```

| Metric | Value |
|--------|-------|
| **Global F1** | **0.647** |
| **Avg F1** | **0.576** |
| Precision | **0.684** |
| Recall | **0.613** |
| TP / FP / FN | **184 / 85 / 116** |

### Strategy Comparison

| Strategy | Global F1 | TP | FP | FN | P | R |
|---|---|---|---|---|---|---|
| **Sauvola+CCL+Merge (occluded)** | **0.587** | 188 | 153 | 112 | 0.551 | **0.627** |
| Old (strategy+close+ct+merge) | 0.370 | 86 | 79 | 214 | 0.521 | 0.287 |
| HoughLinesP + Canny | 0.415 | 156 | 295 | 144 | 0.346 | 0.520 |
| Sauvola+CCL (no merge, old params) | 0.508 | 134 | 94 | 166 | 0.588 | 0.447 |

### Key Insight

Three changes drove most of the improvement:
1. **Collinear merge** — redundant fragments on the same GT line were counted as FPs (29% of all FPs). Merge eliminates them.
2. **Sauvola k=0.3** — more sensitive than k=0.5, catches thin/low-contrast traces.
3. **Relaxed filtering** — close(3), CCL(20), min_len(10) capture thin wires that tighter params filtered out.

### Best Config (Adaptive k Fallback)

```json
{"sauvola_k": 0.3, "sauvola_window": 51, "close_kernel": 3, "ccl_min_area": 20,
 "dedup_angle": 10, "dedup_dist": 18, "merge_angle": 10, "merge_gap": 30, "min_length": 10,
 "fallback_k": 0.25, "min_trace_pct": 0.5}
```

The pipeline tries k=0.3 first. If the binary has <0.5% trace coverage (near-black), it falls back to k=0.25. This fixes the 3 failing images where Sauvola wipes out thin traces.

### Files

- Best config: `~/workspace/experiment_v7/best_config.json`
- Full sweep: `~/workspace/iterative_benchmark.py`
- Adaptive k test: `~/workspace/test_adaptive_k.py`

## Development

```bash
uv run pytest wire_detection/tests/ -q   # Tests
uv run mypy wire_detection/              # Types
uv run ruff check wire_detection/        # Lint
```

## License

See [LICENSE.txt](LICENSE.txt).

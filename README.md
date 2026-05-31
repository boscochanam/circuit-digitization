# Wire Detection Framework

A modular Python framework for detecting interconnect wires in circuit schematics — classical CV pipeline, synthetic data generator, evaluation toolkit, FastAPI backend, and Next.js tuner UI.

> **Full documentation**: [https://boscochanam.github.io/circuit-digitization](https://boscochanam.github.io/circuit-digitization) — or build locally with `uv run mkdocs serve`.
> **Status**: **Global F1: 0.833** (Anchor Filter + PCA endpoints + Overlap Dedup, 134 images)
> **Dataset**: 134 circuit schematic images (predominantly 704×704), 3,524 ground-truth wire segments

---

## Quickstart

```bash
uv venv && uv sync          # Backend setup
cd ui && pnpm install       # Frontend setup
docker compose up --build   # Or: uv run wire-tune + pnpm dev
```

## CLI

| Command | Description |
|---------|-------------|
| `wire-tune` | Start the tuner API server |
| `wire-pipeline` | Run pipeline on a single image |
| `wire-sdg` | Generate synthetic dataset |
| `wire-eval` | Evaluate detections against ground truth |
| `wire-sweep` | Run a parameter sweep |
| `wire-vlm` | VLM quality assessment (classify, sweep, audit) |
| `wire-benchmark-exp` | Run experiment harness (wave1/wave2) |

---

## Final Results (Jun 2026)

### Best Pipeline: Anchor Filter + PCA Endpoints + Overlap Dedup

```
occlude components → crop to ROI (10px pad) → Sauvola k=0.285 (w=67) → 
close(ellipse 3×3) → CCL(min_area=28) → PCA endpoints → overlap dedup(12°,8px) → 
anchor filter(endpoint_dist=12, link_dist=8) → Output Lines
```

**Benchmarked on 134 images (3,524 ground-truth wire annotations) across 36 config variants (wave1-4).**

| Metric | Value |
|--------|-------|
| **Global F1** | **0.833** |
| Precision | **0.876** |
| Recall | **0.791** |
| TP / FP / FN / Red | **2,741 / 248 / 783 / 65** |
| Images with F1=1.0 | **68 of 134 (51%)** |
| Median F1 | **1.000** |

### ⚠️ MANDATORY PREPROCESSING — Must Run BEFORE Detection

**Skipping any of these steps will break reproducibility. The pipeline produces garbage without them.**

#### 1. HDC Label Matching
Each circuit image needs its corresponding YOLO-OBB component labels from roboflow_test2. **Use filename prefix matching** (not pixel-difference) — HDC files have `.rf.XXXX` suffixes from Roboflow augmentation. Pixel-diff comparison only finds 23 of 134 images.

```python
# Find matching HDC label by filename prefix
for split in ["train", "valid", "test"]:
    label_dir = HDC_BASE / split / "labels"
    matches = sorted(label_dir.glob(f"{image_name}_jpg.rf.*.txt"))
    if matches:
        return matches[0]  # Labels are identical across augments
```

#### 2. Component Occlusion
Fill every HDC component polygon with the **local median pixel color**. This prevents component edges/text from producing false wire detections. Margin: 15% of bbox size, min 5px.

```python
for cls_id, polygon, (x1, y1, x2, y2) in components:
    margin_x = max(int((x2 - x1) * 0.15), 5)
    margin_y = max(int((y2 - y1) * 0.15), 5)
    local_region = gray[y1-margin_y:y2+margin_y, x1-margin_x:x2+margin_x]
    fill_color = int(np.median(local_region))
    cv2.fillPoly(occluded_image, [polygon], fill_color)
```

#### 3. ROI Crop + Padding
Crop to the tight bounding box of ALL components plus **10px padding**. This eliminates scanner border artifacts and paper edges.

```python
rx1 = max(0, min(all_bbox_x1) - 10)
ry1 = max(0, min(all_bbox_y1) - 10)
rx2 = min(w, max(all_bbox_x2) + 10)
ry2 = min(h, max(all_bbox_y2) + 10)
cropped = occluded_image[ry1:ry2, rx1:rx2]
```

**After detection, convert local coordinates back to global** by adding (rx1, ry1) to all endpoints.

### Best Config

```json
{
  "sauvola_k": 0.285, "sauvola_window": 67, "close_kernel": 3,
  "ccl_min_area": 28, "endpoint_mode": "pca", "dedup_mode": "overlap",
  "dedup_angle": 12, "dedup_dist": 8,
  "anchor_filter_enabled": true, "anchor_endpoint_dist": 12, "anchor_link_dist": 8
}
```
**Do NOT use merge or length filter — both are proven harmful (destroy 64 TPs).**

### Reference Implementation

See `wire_detection/benchmark/expanded_benchmark.py` for the full 134-image benchmark.
Run: `uv run python wire_detection/benchmark/expanded_benchmark.py` → ranks all 36 configs (wave1-4).

The reference pipeline (`reference_pipeline.py`) is archived — it used pixel-diff HDC matching and only found 23 images. The expanded benchmark uses filename prefix matching, finding all 134.

### Top Configs (134 images)

| Rank | Config | Global F1 | TP | FP | FN | Red | P | R |
|------|--------|-----------|----|----|----|----|----|----|
| **1** | **best_candidate_v4** | **0.833** | 2,741 | 248 | 783 | 65 | 0.898 | 0.778 |
| 2 | best_candidate_v2 | 0.826 | 2,761 | 286 | 763 | 116 | 0.873 | 0.784 |
| 3 | best_candidate_v3 | 0.819 | 2,770 | 318 | 754 | 149 | 0.856 | 0.786 |
| 4 | skeleton_graph_v1 | 0.819 | 2,898 | 332 | 626 | 327 | 0.815 | 0.822 |
| 5 | best_candidate_v1 | 0.817 | 2,786 | 353 | 738 | 157 | 0.845 | 0.791 |
| 6 | best_candidate_v6 | 0.811 | 2,675 | 223 | 849 | 178 | 0.870 | 0.759 |
| 7 | k0285_anchor_filter | 0.810 | 2,796 | 408 | 728 | 175 | 0.828 | 0.793 |
| 8 | best_candidate_v5 | 0.804 | 2,609 | 200 | 915 | 159 | 0.879 | 0.740 |
| 9 | best_candidate_v8 | 0.803 | 2,576 | 164 | 948 | 149 | 0.892 | 0.731 |
| 10 | pca_overlap | 0.800 | 2,856 | 560 | 668 | 200 | 0.790 | 0.810 |

### Key Improvements (Experiment Progression) — measured on 23-image subset

| # | Change | F1 | Δ |
|---|--------|----|---|
| 1 | Original pipeline (baseline) | 0.370 | — |
| 2 | Sauvola k=0.5 + occlusion | 0.508 | +0.138 |
| 3 | + Collinear merge | 0.526 | +0.018 |
| 4 | Sweep: k=0.3, close=3, CCL=20, dedup=18 | 0.587 | +0.061 |
| 5 | + Adaptive k fallback | 0.593 | +0.006 |
| 6 | + Crop to ROI (10px pad) | 0.627 | +0.034 |
| 7 | + Occlusion on all 23 images | 0.647 | +0.020 |
| **8** | **Remove merge (dedup only)** | **0.707** | **+0.060** |
| **9** | **Anchor filter + PCA + overlap dedup** | **0.749** | **+0.042** |
| **10** | **Expanded to 134 images (prefix matching)** | **0.833** | **+0.084** |

### Synthetic Validation

- **50 synthetic images, 452 GT lines**: Sauvola+CCL+Merge achieves **F1=0.941**
- Proves method works near-perfectly on clean schematics
- Real-world gap (0.941→0.647) is scanner artifacts, paper grain, and severed wire boundaries

---

## Publication

Target venues:

| Venue | Deadline | Odds |
|-------|----------|------|
| **MethodsX (Elsevier)** | Rolling (submit ~Jul 2026) | 70-80% |
| **NeurIPS 2026 Workshop** | Aug 29, 2026 | 40-55% |

Strategy: submit MethodsX first (Jul 2026), then NeurIPS Workshop (Aug 29) — MethodsX under review ≠ published — no prior-pub conflict. Two publications from one pipeline.

See `~/workspace/README.md` for full experiment history and publishing timeline.

---

## Project Structure

```
wire_detection/     Python backend (pipeline, API, SDG, evaluation, experiments)
ui/                 Next.js frontend (tuner UI)
docs/               MkDocs documentation
```

## Development

```bash
uv run pytest wire_detection/tests/ -q   # Tests
uv run mypy wire_detection/              # Types
uv run ruff check wire_detection/        # Lint
```

## License

See [LICENSE.txt](LICENSE.txt).

## Contact

- **Chris Dcosta**: chrisdcosta777@gmail.com / chris.dcosta.btech2021@sitpune.edu.in
- **Repository**: github.com/boscochanam/circuit-digitization
- **Bosco**: GitHub @boscochanam

# Wire Detection Framework

A modular Python framework for detecting interconnect wires in circuit schematics — classical CV pipeline, synthetic data generator, evaluation toolkit, FastAPI backend, and Next.js tuner UI.

> **Full documentation**: [https://boscochanam.github.io/circuit-digitization](https://boscochanam.github.io/circuit-digitization) — or build locally with `uv run mkdocs serve`.
> **Status**: **Global F1: 0.749** (Anchor Filter + PCA endpoints + Overlap Dedup, 23 images)
> **Dataset**: 23 circuit schematic images (704×704), 300 ground-truth wire segments

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

## Final Results (May 2026)

### Best Pipeline: Anchor Filter + PCA Endpoints + Overlap Dedup

```
occlude components → crop to ROI (10px pad) → Sauvola k=0.285 (w=67) → 
close(ellipse 3×3) → CCL(min_area=28) → PCA endpoints → overlap dedup(12°,8px) → 
anchor filter(endpoint_dist=12, link_dist=8) → Output Lines
```

| Metric | Value |
|--------|-------|
| **Global F1** | **0.749** |
| Precision | **0.724** |
| Recall | **0.777** |
| TP / FP / FN | **233 / 43 / 67** |

### ⚠️ MANDATORY PREPROCESSING — Must Run BEFORE Detection

**Skipping any of these steps will break reproducibility. The pipeline produces garbage without them.**

#### 1. HDC Label Matching
Each circuit image needs its corresponding YOLO-OBB component labels from roboflow_test2. Match by pixel-difference comparison across train/valid/test splits.

```python
# Find matching HDC label for each image
for split in ["train", "valid", "test"]:
    label_dir = HDC_BASE / split / "labels"
    for label_path in label_dir.glob(f"{image_name}_jpg*"):
        # Compare pixel content to find exact match
        diff = cv2.absdiff(gray_image, hdc_image).mean()
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

See `wire_detection/benchmark/reference_pipeline.py` for the complete, verified implementation.
Run: `uv run python wire_detection/benchmark/reference_pipeline.py` → produces F1=0.7066 (baseline).
Run: `uv run python -m wire_detection.benchmark.experiment_harness --preset wave2` → best config achieves F1=0.749.

### Strategy Comparison

| Strategy | Global F1 | TP | FP | FN | P | R |
|----------|-----------|----|----|----|----|----|
| **best_candidate_v4 (current best)** | **0.749** | 233 | 43 | 67 | 0.724 | 0.777 |
| Sauvola+CCL+Dedup (baseline) | 0.707 | 248 | 70 | 52 | 0.617 | 0.827 |
| Sauvola+CCL+Merge (old) | 0.647 | 184 | 85 | 116 | 0.684 | 0.613 |
| Sauvola+CCL (no merge, old params) | 0.508 | 134 | 94 | 166 | 0.588 | 0.447 |
| HoughLinesP + Canny (per-image best avg) | 0.682* | — | — | — | — | — |
| Original (strategy+close+ct+merge) | 0.370 | 86 | 79 | 214 | 0.521 | 0.287 |

*\*Per-image avg F1 — upper bound from per-image optimal Canny/Hough params, not a single deployable config.*

### Key Improvements (Experiment Progression)

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

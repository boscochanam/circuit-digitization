# 🚨 READ THIS FIRST — Critical Preprocessing Steps

The wire detection pipeline **WILL NOT WORK** without these three preprocessing steps. Many AI agents skip them and produce garbage results.

## MANDATORY Preprocessing (in order)

### 1. HDC Label Matching
Each image needs YOLO-OBB component labels from roboflow_test2. **Use filename prefix matching** (not pixel-difference) — HDC files have `.rf.XXXX` suffixes from Roboflow augmentation.
- Paths: `/home/claw/circuit-digitization/roboflow_test2/{train,valid,test}/labels/`
- Images: `/home/claw/workspace/ground_truth/labels_few_annot/images/`
- Labels: `/home/claw/workspace/ground_truth/labels_few_annot/labels/train/manually_verified_no_background_data/images/`
- Matches: **134 images** with both GT wire labels and HDC component labels (3,524 total wire annotations)

### 2. Component Occlusion  
Fill each component polygon with **local median color** (NOT white, NOT black — use `np.median()` of local region).
- Margin: 15% of bbox size, min 5px
- This removes text, component edges, internal structures

### 3. ROI Crop + Padding
Crop to union of all component bounding boxes + 10px padding in all directions.
- This removes scanner border artifacts and paper edges
- Remember to add the offset (rx1, ry1) back to all detected line endpoints

## Pipeline Params (DO NOT CHANGE)
- Sauvola: k=0.285, window=67
- Close: ellipse 3×3
- CCL: min_area=28
- PCA endpoints (not extremal)
- Overlap dedup: angle=12°, dist=8px  
- Anchor filter: endpoint_dist=12, link_dist=8
- **NO merge, NO length filter** — both destroy TPs

## Reference Pipeline (Broken — paths don't exist)
Old: `uv run python wire_detection/benchmark/reference_pipeline.py` — F1=0.7066 on 23 images
The `labels_few_annot/` directory was removed. Use the expanded benchmark instead.

## Expanded Benchmark (134 images, all 20 configs)
Run: `uv run python wire_detection/benchmark/expanded_benchmark.py`
Expected output: full ranking of all 20 configs on 134 images (3,524 GT wires)

### Top Configs (Jun 2026)
| Rank | Config | F1 | Precision | Recall |
|---|---|---|---|---|
| 1 | **best_candidate_v4** | **0.8314** | 0.876 | 0.791 |
| 2 | best_candidate_v2 | 0.8241 | 0.853 | 0.797 |
| 3 | best_candidate_v3 | 0.8170 | 0.835 | 0.800 |
| 4 | best_candidate_v1 | 0.8143 | 0.828 | 0.801 |
| 5 | k0285_anchor_filter | 0.8074 | 0.814 | 0.801 |

### Per-image Breakdown (best_candidate_v4)
- **91 images** (68%) — F1 >= 0.90 (68 of those at F1=1.0, perfect)
- **99 images** (74%) — F1 >= 0.70
- **103 images** (77%) — F1 >= 0.50
- **31 images** (23%) — F1 < 0.50 (poor)
- **Median F1: 1.000**
- Full results: `output/benchmark_experiments/expanded_full_ranking/`

## VLM Quality Assessment
- Module: `wire_detection.vlm` — classify images by paper type via VLM or programmatic scores
- CLI: `wire-vlm classify`, `wire-vlm sweep`, `wire-vlm audit-pipeline`
- Doc: `docs/vlm-experiments.md` — full Nemotron experiment methodology
- Data: `docs/experiments/data/` — saved VLM results (330 CGHD1152 images)

## Common Errors Agents Make
1. ✗ Skipping occlusion entirely → FP count explodes
2. ✗ Filling with white (255) instead of median color → edges become wires
3. ✗ Not cropping to ROI → scanner borders detected as wires  
4. ✗ Forgetting coordinate offset after crop → lines in wrong position
5. ✗ Using merge or length filter → 64 TPs destroyed
6. ✗ Using old params (otsu, dilate=5, min_area=30, dedup_dist=12) → wrong pipeline
7. ✗ Not matching HDC labels → no occlusion at all
8. ✗ Using pixel-diff matching instead of prefix matching → only finds 23/134 images

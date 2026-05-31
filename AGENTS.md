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

## Expanded Benchmark (134 images, all 36 configs)
Run: `uv run python wire_detection/benchmark/expanded_benchmark.py`

### Top Configs (Jun 2026)
| Rank | Config | F1 | Precision | Recall |
|---|---|---|---|---|
| 1 | **best_candidate_v4** | **0.8334** | 0.898 | 0.778 |
| 2 | best_candidate_v2 | 0.8258 | 0.873 | 0.784 |
| 3 | best_candidate_v3 | 0.8194 | 0.856 | 0.786 |
| 4 | skeleton_graph_v1 | 0.8185 | 0.815 | 0.822 |
| 5 | best_candidate_v1 | 0.8170 | 0.845 | 0.791 |

### Key Findings
- **best_candidate_v4** (Sauvola + component extraction) is the winner
- Skeleton graph methods (v5-v8) have higher precision but worse F1
- **OTSU is terrible** for this dataset (F1 < 0.67)
- Adaptive thresholding beats OTSU but not Sauvola (F1=0.755 vs 0.833)
- Sauvola adaptive gaussian fusion (F1=0.765) doesn't beat plain Sauvola

### Per-image Breakdown (best_candidate_v4)
- **91 images** (68%) — F1 >= 0.90
- **Median F1: 1.000**
- **31 images** (23%) — F1 < 0.50 (poor: bimodal lighting, dense circuits)

## VLM Quality Assessment
- Module: `wire_detection.vlm` — classify images by paper type via VLM or programmatic scores
- CLI: `wire-vlm classify`, `wire-vlm sweep`, `wire-vlm audit-pipeline`
- Doc: `docs/vlm-experiments.md`

## Common Errors Agents Make
1. ✗ Skipping occlusion entirely → FP count explodes
2. ✗ Filling with white (255) instead of median color → edges become wires
3. ✗ Not cropping to ROI → scanner borders detected as wires  
4. ✗ Forgetting coordinate offset after crop → lines in wrong position
5. ✗ Using merge or length filter → 64 TPs destroyed
6. ✗ Using old params (otsu, dilate=5, min_area=30, dedup_dist=12) → wrong pipeline
7. ✗ Not matching HDC labels → no occlusion at all
8. ✗ Using pixel-diff matching instead of prefix matching → only finds 23/134 images

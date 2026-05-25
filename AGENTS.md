# 🚨 READ THIS FIRST — Critical Preprocessing Steps

The wire detection pipeline **WILL NOT WORK** without these three preprocessing steps. Many AI agents skip them and produce garbage results.

## MANDATORY Preprocessing (in order)

### 1. HDC Label Matching
Each image needs YOLO-OBB component labels from roboflow_test2. Match by pixel-difference.
- Paths: `/home/claw/circuit-digitization/roboflow_test2/{train,valid,test}/labels/`
- Images: `/home/claw/workspace/ground_truth/labels_few_annot/images/`

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

## Reference Implementation
Run: `uv run python wire_detection/benchmark/reference_pipeline.py`
Expected output: F1=0.7066, TP=248, FP=70, FN=52

## Best Config (May 2026)
Run: `uv run python -m wire_detection.benchmark.experiment_harness --preset wave2`
Best: **best_candidate_v4** → F1=0.749, TP=233, FP=43, FN=67

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

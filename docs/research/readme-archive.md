# README research-log archive

Archived from the pre-2026-07 `README.md`, which doubled as an internal research log.
This material is kept for historical context. **Current, authoritative numbers live in
[`docs/research/experiments/SUMMARY.md`](experiments/SUMMARY.md).** Some figures below
(notably the 0.833 prefix-match wire F1 and the 23-image progression) predate the corrected
evaluations and are superseded by the headline results in the current `README.md`.

---

## Two wire-detection numbers (0.976 vs 0.833)

The repo historically reported two wire-detection F1 figures on the **same 134 images**. They
differ only in how predicted lines are matched to ground truth:

| Eval | F1 | GT matching | Where |
|------|----|-------------|-------|
| **a16 (exact-match)** | **0.976** | exact-match labels on original images (strict, current) | AGENTS.md, paper |
| best_candidate_v4 (prefix-match) | 0.833 | filename prefix matching (looser GT alignment) | tables below |

The **0.976 exact-match number is the headline** (paper Table I). The 0.833 prefix-match number
and the tables below predate the corrected eval and are kept for historical comparison. The only
config change between the v4 baseline and a16 is `anchor_endpoint_dist` 12 → 16.

## Best pipeline: anchor filter + PCA endpoints + overlap dedup

```
occlude components → crop to ROI (10px pad) → Sauvola k=0.285 (w=67) →
close(ellipse 3×3) → CCL(min_area=28) → PCA endpoints → overlap dedup(12°,8px) →
anchor filter(endpoint_dist=16, link_dist=8) → Output Lines
```

Benchmarked on 134 images (3,524 ground-truth wire annotations) across 36 config variants
(wave1–4). Figures below are the legacy prefix-match eval — see the current README for the
corrected exact-match F1 = 0.976.

| Metric | Value (prefix-match eval) |
|--------|-------|
| Global F1 | 0.833 |
| Precision | 0.876 |
| Recall | 0.791 |
| TP / FP / FN / Red | 2,741 / 248 / 783 / 65 |
| Images with F1=1.0 | 68 of 134 (51%) |
| Median F1 | 1.000 |

## Mandatory preprocessing — must run before detection

Skipping any of these steps breaks reproducibility; the pipeline degrades badly without them.

### 1. Component detection

Use the trained YOLO model for all component detection. The model is the single source of truth.

```python
from wire_detection.data.component_loader import load_components

# Uses config from defaults.yaml (component_detection.source)
components = load_components(image_path)

# Or override source explicitly
components = load_components(image_path, source="ground_truth")
```

Model: `models/component_detection/yolo26m_obb_16class_aug.pt` (88.5% mAP@0.5).

### 2. Component occlusion

Fill every component polygon with the local median pixel color. This prevents component edges and
text from producing false wire detections. Margin: 15% of bbox size, min 5px.

```python
for cls_id, polygon, (x1, y1, x2, y2) in components:
    margin_x = max(int((x2 - x1) * 0.15), 5)
    margin_y = max(int((y2 - y1) * 0.15), 5)
    local_region = gray[y1-margin_y:y2+margin_y, x1-margin_x:x2+margin_x]
    fill_color = int(np.median(local_region))
    cv2.fillPoly(occluded_image, [polygon], fill_color)
```

### 3. ROI crop + padding

Crop to the tight bounding box of ALL components plus 10px padding. This eliminates scanner border
artifacts and paper edges.

```python
rx1 = max(0, min(all_bbox_x1) - 10)
ry1 = max(0, min(all_bbox_y1) - 10)
rx2 = min(w, max(all_bbox_x2) + 10)
ry2 = min(h, max(all_bbox_y2) + 10)
cropped = occluded_image[ry1:ry2, rx1:rx2]
```

After detection, convert local coordinates back to global by adding (rx1, ry1) to all endpoints.

### Best config (legacy prefix-match tuning)

```json
{
  "sauvola_k": 0.285, "sauvola_window": 67, "close_kernel": 3,
  "ccl_min_area": 28, "endpoint_mode": "pca", "dedup_mode": "overlap",
  "dedup_angle": 12, "dedup_dist": 8,
  "anchor_filter_enabled": true, "anchor_endpoint_dist": 16, "anchor_link_dist": 8
}
```

Do NOT use merge or length filter — both were shown harmful (destroy 64 TPs).

## Top configs (134 images, prefix-match eval)

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

## Experiment progression (measured on 23-image subset)

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

## Node joining strategy comparison (134-image GT set, post double-extend fix, Jun 2026)

Lower `balanced` is better. This was the join sweep on structural join-health metrics, before the
switch to the human-verified net-level benchmark (see current README for the connectivity results).

| Strategy | balanced | wires-used% | self-loop | floating |
|----------|----------|-------------|-----------|----------|
| **degree_budget** | **0.2710** | **99.4** | 213 | 1084 |
| graph_scale | 0.3610 | 99.5 | 62 | 1726 |
| graph_dir_30 | 0.3613 | 99.5 | 71 | 1711 |
| graph_rescue | 0.3679 | 99.4 | 213 | 1607 |

## Synthetic validation (early)

- 50 synthetic images, 452 GT lines: Sauvola+CCL+Merge achieves F1 = 0.941.
- The real-world gap at the time (0.941 → 0.647) was attributed to scanner artifacts, paper grain,
  and severed wire boundaries.
</content>
</invoke>

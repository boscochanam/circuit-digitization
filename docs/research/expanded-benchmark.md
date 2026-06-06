# Expanded Benchmark — All Configs on 134 Images

**Date:** June 2026  
**Dataset:** 134 circuit schematic images, 3,524 ground-truth wire annotations  
**Configs evaluated:** 36 (wave1 + wave2 + wave3 + wave4 variants)

## Background

The original benchmark pipeline (`reference_pipeline.py`) used pixel-difference matching to pair ground-truth images with HDC component labels. This only found **23 of 134** available images because the Roboflow-augmented images had `.rf.XXXX` suffixes that prevented exact pixel matching.

The expanded benchmark replaces pixel-diff matching with **filename prefix matching**, finding all 134 images that have both GT wire labels and HDC component labels.

## Methodology

- **Matching:** Filename prefix match (e.g., `C100_D1_P1_jpg.rf.XXXX.txt` matches GT `C100_D1_P1_jpg.txt`)
- **Evaluation:** Per-image precision/recall/F1 at 20px distance threshold
- **Global metrics:** Aggregated TP/FP/FN/Red across all images
- **Hardware:** CPU only (no GPU needed for classical CV pipeline)
- **Config waves:**
  - Wave 1 (10 configs): Baseline, CLAHE, k=0.275/0.285, dual threshold, PCA, overlap dedup, anchor filter
  - Wave 2 (10 configs): Reconnect, PCA+overlap combos, best_candidate_v1-v4
  - Wave 3 (7 configs): Skeleton graph extraction, best_candidate_v5-v8
  - Wave 4 (9 configs): OTSU, adaptive mean/gaussian, triangle thresholding, fusion methods

## Full Results (36 configs)

| Rank | Config | F1 | Precision | Recall | TP | FP | FN | Red |
|---|---|---|---|---|---|---|---|---|
| **1** | **best_candidate_v4** | **0.8334** | **0.898** | 0.778 | 2,741 | **248** | 783 | 65 |
| 2 | best_candidate_v2 | 0.8258 | 0.873 | 0.784 | 2,761 | 286 | 763 | 116 |
| 3 | best_candidate_v3 | 0.8194 | 0.856 | 0.786 | 2,770 | 318 | 754 | 149 |
| 4 | skeleton_graph_v1 | 0.8185 | 0.815 | **0.822** | **2,898** | 332 | **626** | 327 |
| 5 | best_candidate_v1 | 0.8170 | 0.845 | 0.791 | 2,786 | 353 | 738 | 157 |
| 6 | best_candidate_v6 | 0.8106 | 0.870 | 0.759 | 2,675 | 223 | 849 | 178 |
| 7 | k0285_anchor_filter | 0.8101 | 0.828 | 0.793 | 2,796 | 408 | 728 | 175 |
| 8 | best_candidate_v5 | 0.8038 | 0.879 | 0.740 | 2,609 | 200 | 915 | 159 |
| 9 | best_candidate_v8 | 0.8034 | 0.892 | 0.731 | 2,576 | 164 | 948 | 149 |
| 10 | pca_overlap | 0.8000 | 0.790 | 0.810 | 2,856 | 560 | 668 | 200 |
| 11 | pca_endpoints | 0.7984 | 0.786 | 0.811 | 2,857 | 564 | 667 | 212 |
| 12 | overlap_dedup | 0.7975 | 0.788 | 0.807 | 2,843 | 566 | 681 | 197 |
| 13 | k0275_pca_overlap | 0.7973 | 0.784 | 0.811 | 2,858 | 594 | 666 | 193 |
| 14 | k0285 | 0.7969 | 0.784 | 0.811 | 2,857 | 592 | 667 | 197 |
| 15 | baseline_control | 0.7950 | 0.783 | 0.807 | 2,844 | 575 | 680 | 212 |
| 16 | wider_window | 0.7950 | 0.783 | 0.807 | 2,844 | 576 | 680 | 211 |
| 17 | dual_threshold | 0.7950 | 0.783 | 0.807 | 2,844 | 575 | 680 | 212 |
| 18 | best_candidate_v7 | 0.7948 | **0.902** | 0.711 | 2,504 | 141 | 1,020 | 132 |
| 19 | k0275 | 0.7940 | 0.780 | 0.809 | 2,850 | 600 | 674 | 205 |
| 20 | reconnect_only | 0.7928 | 0.779 | 0.807 | 2,844 | 590 | 680 | 217 |
| 21 | k0275_reconnect | 0.7919 | 0.776 | 0.809 | 2,850 | 614 | 674 | 210 |
| 22 | sauvola_adaptive_gaussian_fusion | 0.7649 | 0.817 | 0.719 | 2,535 | 365 | 989 | 204 |
| 23 | adaptive_gaussian_skeleton | 0.7549 | 0.831 | 0.691 | 2,436 | 339 | 1,088 | 155 |
| 24 | combined_safe | 0.7503 | 0.705 | 0.802 | 2,826 | 933 | 698 | 250 |
| 25 | clahe_fallback | 0.7500 | 0.706 | 0.800 | 2,819 | 922 | 705 | 252 |
| 26 | adaptive_mean_skeleton | 0.7450 | 0.819 | 0.684 | 2,409 | 320 | 1,115 | 214 |
| 27 | triangle_skeleton | 0.6780 | 0.780 | 0.600 | 2,113 | 354 | 1,411 | 242 |
| 28 | sauvola_otsu_fusion | 0.6742 | 0.737 | 0.622 | 2,190 | 587 | 1,334 | 196 |
| 29 | otsu_component | 0.6669 | 0.689 | 0.646 | 2,278 | 824 | 1,246 | 206 |
| 30 | otsu_skeleton | 0.6560 | 0.745 | 0.586 | 2,066 | 559 | 1,458 | 150 |
| 31 | otsu_skeleton_reconnect | 0.6495 | 0.727 | 0.587 | 2,068 | 617 | 1,456 | 159 |
| 32 | skeleton_graph_full | 0.6430 | 0.557 | 0.761 | 2,683 | 1,386 | 841 | 752 |
| 33 | otsu_clahe_skeleton | 0.6209 | 0.618 | 0.624 | 2,198 | 1,057 | 1,326 | 301 |
| 34 | skeleton_graph_recall | 0.6020 | 0.500 | 0.756 | 2,664 | **1,702** | 860 | **961** |

**Spread:** 0.231 (top to bottom) — Sauvola component extraction is still the clear winner.

## Best Config: `best_candidate_v4`

```json
{
  "sauvola_k": 0.285,
  "sauvola_window": 67,
  "close_kernel": 3,
  "ccl_min_area": 28,
  "endpoint_mode": "pca",
  "dedup_mode": "overlap",
  "dedup_angle": 12,
  "dedup_dist": 8,
  "anchor_filter_enabled": true,
  "anchor_endpoint_dist": 12,
  "anchor_link_dist": 8
}
```

### Per-Image Breakdown

| Category | Count | % |
|---|---|---|
| F1 = 1.0 (perfect) | 68 | 51% |
| F1 >= 0.9 | 91 | 68% |
| F1 >= 0.7 | 99 | 74% |
| F1 >= 0.5 | 103 | 77% |
| F1 < 0.5 | 31 | 23% |
| F1 < 0.4 (hard cases) | 25 | 19% |

**Median F1:** 1.000  
**Mean F1:** 0.796  
**Std Dev:** 0.320

## Method Comparison

### By Extraction Mode

| Mode | Best F1 | Best Config | Notes |
|---|---|---|---|
| **Component (CCL)** | **0.8334** | best_candidate_v4 | Winner — Sauvola + CCL + PCA + dedup + anchor filter |
| Skeleton Graph | 0.8185 | skeleton_graph_v1 | Higher recall (+4%) but lower precision |
| Skeleton (OTSU) | 0.6560 | otsu_skeleton | Terrible — OTSU wrong for bimodal images |
| Skeleton (adaptive) | 0.7549 | adaptive_gaussian_skeleton | Better than OTSU, worse than Sauvola |

### By Threshold Method

| Threshold | Best F1 | Best Config |
|---|---|---|
| **Sauvola (k=0.285, w=67)** | **0.8334** | best_candidate_v4 |
| Adaptive Gaussian | 0.7649 | sauvola_adaptive_gaussian_fusion |
| Adaptive Mean | 0.7450 | adaptive_mean_skeleton |
| Triangle | 0.6780 | triangle_skeleton |
| OTSU | 0.6669 | otsu_component |
| Sauvola + OTSU fusion | 0.6742 | sauvola_otsu_fusion |

### Why OTSU Fails

OTSU thresholding selects the optimal global threshold by maximizing inter-class variance, assuming bimodal intensity. This dataset has:
- **Near-white backgrounds** (mean pixel > 230) → OTSU over-thresholds, missing wires
- **Shadows/creases** (mean pixel ~100-140) → OTSU under-thresholds, floods with FPs
- **Varied lighting** across different images → no single global threshold works

Sauvola's local adaptive thresholding (computed per-pixel in a 67×67 window) handles these variations naturally.

### Why Skeleton Graph Methods Are Worse

The skeleton graph extraction (wave3) traces pixel-level paths through skeletonized wire blobs, then scores/reconnects paths using graph anchors and support lines. Theoretically better at multi-segment wires.

**Problem:** Skeleton graph produces 1.7-3.7× more detections than component extraction, with many phantom paths. The `score_cluster` dedup helps but can't match the simplicity of CCL's "one blob = one wire" assumption.

### What Precision-Focused Configs Tell Us

| Config | F1 | Precision | Recall | FP |
|---|---|---|---|---|
| best_candidate_v7 | 0.795 | **0.902** | 0.711 | 141 |
| best_candidate_v8 | 0.803 | 0.892 | 0.731 | 164 |
| best_candidate_v4 | **0.833** | 0.898 | 0.778 | 248 |

Pushing for higher precision (v7/v8) costs recall — you can get 141 FPs (v7) but at 0.902 precision / 0.711 recall, you miss 24% of wires. The F1-optimal point is v4 at 248 FPs.

## Worst 10 Images

| Image | F1 | GT | Det | TP | FP | FN | Issue |
|---|---|---|---|---|---|---|---|
| C101_D1_P1 | 0.000 | 10 | 1 | 0 | 1 | 10 | No TP found |
| C10_D2_P3 | 0.000 | 8 | 5 | 0 | 5 | 8 | All detections are FP |
| C205_D1_P2 | 0.113 | 35 | 18 | 3 | 13 | 32 | Dense, shadowy |
| C7_D2_P2 | 0.122 | 37 | 12 | 3 | 9 | 34 | Contrast issue |
| C28_D1_P1 | 0.148 | 41 | 13 | 4 | 8 | 37 | Poor binarization |
| C100_D2_P4 | 0.154 | 17 | 22 | 3 | 16 | 14 | Near-white background |
| C58_D1_P3 | 0.162 | 48 | 26 | 6 | 20 | 42 | Very dense circuit |
| C167_D2_P1 | 0.167 | 10 | 2 | 1 | 1 | 9 | Low contrast |
| C8_D1_P1 | 0.170 | 36 | 23 | 5 | 18 | 31 | Bimodal lighting |
| C28_D1_P4 | 0.171 | 46 | 24 | 6 | 16 | 40 | Shadow on dense circuit |

## How to Reproduce

```bash
cd /home/claw/circuit-digitization
uv run python wire_detection/benchmark/expanded_benchmark.py
```

Results saved to `output/benchmark_experiments/expanded_full_ranking/`.

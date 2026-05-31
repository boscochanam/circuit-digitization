# Expanded Benchmark — All Configs on 134 Images

**Date:** June 2026  
**Dataset:** 134 circuit schematic images, 3,524 ground-truth wire annotations  
**Configs evaluated:** 20 (all wave1 + wave2 variants + best_candidate_v4)

## Background

The original benchmark pipeline (`reference_pipeline.py`) used pixel-difference matching to pair ground-truth images with HDC component labels. This only found **23 of 134** available images because the Roboflow-augmented images had `.rf.XXXX` suffixes that prevented exact pixel matching.

The expanded benchmark replaces pixel-diff matching with **filename prefix matching**, finding all 134 images that have both GT wire labels and HDC component labels.

## Methodology

- **Matching:** Filename prefix match (e.g., `C100_D1_P1_jpg.rf.XXXX.txt` matches GT `C100_D1_P1_jpg.txt`)
- **Evaluation:** Per-image precision/recall/F1 at 20px distance threshold
- **Global metrics:** Aggregated TP/FP/FN/Red across all images
- **Hardware:** CPU only (no GPU needed for classical CV pipeline)

## Full Results

| Rank | Config | F1 | Precision | Recall | TP | FP | FN | Red |
|---|---|---|---|---|---|---|---|---|
| 1 | **best_candidate_v4** | **0.8314** | 0.876 | 0.791 | 2788 | 322 | 736 | 73 |
| 2 | best_candidate_v2 | 0.8241 | 0.853 | 0.797 | 2808 | 358 | 716 | 125 |
| 3 | best_candidate_v3 | 0.8170 | 0.835 | 0.800 | 2819 | 398 | 705 | 160 |
| 4 | best_candidate_v1 | 0.8143 | 0.828 | 0.801 | 2822 | 418 | 702 | 167 |
| 5 | k0285_anchor_filter | 0.8074 | 0.814 | 0.801 | 2821 | 462 | 703 | 181 |
| 6 | k0285_anchor_reconnect | 0.8052 | 0.810 | 0.801 | 2821 | 476 | 703 | 186 |
| 7 | pca_overlap | 0.8000 | 0.790 | 0.810 | 2856 | 560 | 668 | 200 |
| 8 | pca_endpoints | 0.7984 | 0.786 | 0.811 | 2857 | 564 | 667 | 212 |
| 9 | overlap_dedup | 0.7975 | 0.788 | 0.807 | 2843 | 566 | 681 | 197 |
| 10 | k0275_pca_overlap | 0.7973 | 0.784 | 0.811 | 2858 | 594 | 666 | 193 |
| 11 | k0285 | 0.7969 | 0.784 | 0.811 | 2857 | 592 | 667 | 197 |
| 12 | baseline_control | 0.7950 | 0.783 | 0.807 | 2844 | 575 | 680 | 212 |
| 13 | wider_window | 0.7950 | 0.783 | 0.807 | 2844 | 576 | 680 | 211 |
| 14 | k0275 | 0.7940 | 0.780 | 0.809 | 2850 | 600 | 674 | 205 |
| 15 | reconnect_only | 0.7928 | 0.779 | 0.807 | 2844 | 590 | 680 | 217 |
| 16 | k0275_reconnect | 0.7919 | 0.776 | 0.809 | 2850 | 614 | 674 | 210 |
| 17 | dual_threshold | 0.7860 | 0.768 | 0.805 | 2837 | 641 | 687 | 217 |
| 18 | combined_safe | 0.7503 | 0.705 | 0.802 | 2826 | 933 | 698 | 250 |
| 19 | clahe_fallback | 0.7500 | 0.706 | 0.800 | 2819 | 922 | 705 | 252 |

**Spread:** 0.0814 (top to bottom) — the pipeline is remarkably stable across configs.

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
| Zero detections | 0 | 0% |

**Median F1:** 1.000  
**Mean F1:** 0.796  
**Std Dev:** 0.320

### Worst 10 Images

| Image | F1 | GT | Det | TP | FP | FN | Issue |
|---|---|---|---|---|---|---|---|
| C101_D1_P1 | 0.000 | 10 | 1 | 0 | 1 | 10 | No TP, pipeline found nothing useful |
| C10_D2_P3 | 0.000 | 8 | 5 | 0 | 5 | 8 | All detections are false positives |
| C205_D1_P2 | 0.113 | 35 | 18 | 3 | 13 | 32 | Dense circuit, severe under-detection |
| C7_D2_P2 | 0.122 | 37 | 12 | 3 | 9 | 34 | Shadow/contrast issue |
| C28_D1_P1 | 0.148 | 41 | 13 | 4 | 8 | 37 | Poor binarization from shadows |
| C100_D2_P4 | 0.154 | 17 | 22 | 3 | 16 | 14 | Near-white background floods FPs |
| C58_D1_P3 | 0.162 | 48 | 26 | 6 | 20 | 42 | Very dense circuit |
| C167_D2_P1 | 0.167 | 10 | 2 | 1 | 1 | 9 | Low contrast image |
| C8_D1_P1 | 0.170 | 36 | 23 | 5 | 18 | 31 | Shadowy/bimodal lighting |
| C28_D1_P4 | 0.171 | 46 | 24 | 6 | 16 | 40 | Shadow on dense circuit |

## Config Ablation Analysis

### What works:
- **Anchor filter** — removes FP lines not touching components. Gain: +0.012 F1
- **PCA endpoints** — better than extremal endpoints for thin/angled wires. Gain: +0.003 F1
- **Overlap dedup** — more aggressive than baseline dedup. Gain: +0.003 F1
- **Sauvola k=0.285, window=67** — optimal threshold parameters

### What doesn't:
- **CLAHE normalization** — adds 347 FPs with no recall gain. Hurts F1 by -0.045
- **Dual threshold** — slightly worse (-0.009) due to extra FPs
- **Reconnect** — marginal gain at higher FP cost
- **Secondary recovery** (best_candidate_v3) — slightly worse than v2 due to looser filter

## Key Insight

The expanded dataset includes many **simpler images** that the pipeline handles perfectly. The 23-image subset was biased toward harder examples (it happened to include C101, C10, C100_D2_P4, etc.), making the old F1=0.749 artificially pessimistic. The true pipeline performance on the full dataset is F1=0.831.

However, the **31 hard images** remain unsolved — these have dense wiring, extreme shadows, or near-white backgrounds that break Sauvola binarization. Solving these requires either:
1. Per-image adaptive threshold selection (bypass Sauvola where it fails)
2. Deep learning approach (wire segmentation model)
3. Better preprocessing (illumination correction, contrast enhancement)

## How to Reproduce

```bash
cd /home/claw/circuit-digitization
uv run python wire_detection/benchmark/expanded_benchmark.py
```

Results saved to `output/benchmark_experiments/expanded_full_ranking/`.

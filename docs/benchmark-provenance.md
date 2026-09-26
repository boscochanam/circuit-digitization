# Benchmark Provenance

This page is the empirical provenance record for the numbers reported in the IEEE Access
manuscript. It states, for each headline figure, what was measured, on which data, with which
configuration, and where the backing artifact lives.

The authoritative result store is
[`docs/research/experiments/SUMMARY.md`](research/experiments/SUMMARY.md), which indexes the
committed result JSONs. This page records the provenance and the caveats; the JSONs record the
values.

## Wire detection — expanded benchmark (134 images)

**Reproduce:**

```bash
uv run python wire_detection/benchmark/expanded_benchmark.py
```

Dataset: 134 CGHD-1152 images that have both ground-truth wire labels and component labels
(3,524 ground-truth wire annotations). All 36 pipeline configurations are evaluated.

### Two evaluations, two "best F1" numbers

!!! warning "Do not confuse the two tables"
    This repository contains **two different evaluations of the same 134 images**. They differ
    only in how predicted lines are matched to ground truth, and they therefore report different
    best-F1 values.

    | Eval | Best F1 | Ground-truth matching | Status |
    |---|---|---|---|
    | **a16** (this page) | **0.9755** | Exact-match labels on the original images | **Current. Paper Table I.** |
    | `best_candidate_v4` | 0.8334 | Filename prefix matching (looser GT alignment) | Superseded; kept for history |

    The older prefix-match evaluation, with its full 36-config ranking, per-image breakdown and
    failure analysis, lives in
    [`docs/research/expanded-benchmark.md`](research/expanded-benchmark.md). It predates the
    corrected evaluation and is retained for comparison only. The same distinction is recorded in
    [`docs/research/readme-archive.md`](research/readme-archive.md).

    The only *pipeline* change between the `best_candidate_v4` baseline and a16 is
    `anchor_endpoint_dist` 12 → 16. Everything else in the F1 gap comes from correcting the
    ground-truth matching: prefix matching could attach labels from a Roboflow-augmented copy of an
    image (a different coordinate space) to the original image.

### Top configs (Jun 2026, corrected eval — exact-match labels on original images)

Primary artifacts, recovered from the machine that produced them and committed 2026-07-08:

- `docs/research/experiments/wire_threshold_full_ranking_jun2026.json` — all 36 configs, global
  F1/P/R and TP/FP/FN. Produced by `wire_detection/benchmark/expanded_benchmark.py` (2026-06-15).
- `docs/research/experiments/wire_a16_summary_jun2026.json` — the a16 run (2026-06-16), which
  postdates the 36-config sweep and so does not appear in it. Carries the frozen config and the
  full per-image breakdown (n=134).

| Rank | Config | F1 | Precision | Recall | FP | FN |
|---|---|---|---|---|---|---|
| 1 | **a16** (anchor_endpoint_dist=16) | **0.9755** | 0.9729 | 0.9781 | 47 | 77 |
| 2 | v4 baseline (anchor_endpoint_dist=12) | 0.9730 | 0.9741 | 0.9719 | 44 | 99 |
| 3 | best_candidate_v2 | 0.9589 | 0.9442 | 0.9742 | 81 | 91 |
| 4 | best_candidate_v1 | 0.9498 | 0.9213 | 0.9801 | 112 | 70 |
| 5 | best_candidate_v3 | 0.9490 | 0.9235 | 0.9759 | 110 | 85 |

### Key findings and thresholding ablations

- **a16** (Sauvola + component extraction + `anchor_endpoint_dist=16`) is the winner.
- Only change from the v4 baseline: `anchor_endpoint_dist` 12 → 16 (+0.0025 F1).
- **Sauvola dominates all other thresholding methods.** Best config per thresholding family, read
  off `wire_threshold_full_ranking_jun2026.json`:

  | Family | Best config | F1 | Precision | Recall |
  |---|---|---|---|---|
  | adaptive Gaussian | `adaptive_gaussian_skeleton` | 0.8452 | 0.8723 | 0.8198 |
  | Otsu | `otsu_component` | 0.7894 | 0.7962 | 0.7826 |
  | Triangle | `triangle_skeleton` | 0.7583 | 0.8185 | 0.7063 |

  Note these compare *thresholding families at their own best extraction mode*, not a clean
  binarization ablation: `otsu_component` uses component extraction, the other two use skeleton.

  > **Corrected 2026-07-08.** This bullet previously read "OTSU F1=0.828, Triangle F1=0.795".
  > Both were wrong, and both were cell misreads from the *superseded* prefix-match table in
  > `docs/research/expanded-benchmark.md`: 0.828 is the **precision** column of
  > `k0285_anchor_filter` (`:46`), and 0.795 is the **F1 of `baseline_control`** (`:54`), a Sauvola
  > config. The paper's Table I never carried the error — it reports `otsu_component` = 0.789,
  > which matches the primary artifact exactly.
- Skeleton extraction loses recall (FN=402 vs 77) — it breaks thin wires.
- Adaptive thresholding fusion adds nothing — Sauvola already captures the optimal per-pixel
  threshold.
- The parameter sweep shows the pipeline is **robust**: `k`, `window`, `link_dist` and
  `dedup_angle` variations have minimal effect.

### Per-image breakdown (a16)

- **117 images** (87%) — F1 >= 0.90
- **Median F1: 1.000**
- **4 images** (3%) — F1 < 0.50 (dense circuits where large component occlusion eats wire
  endpoints)

### Showcase examples used in the paper (a16)

Verified visually — clean wire detection, correct joins, good complexity range:

- **C84_D2_P1** — 42 wires, 4 nets, 44 components, F1=1.000. Dense but clean. Best all-around
  showcase.
- **C29_D2_P4** — 26 wires, 7 nets, 22 components, F1=1.000. Medium complexity, good variety.
- **C34_D1_P1** — 19 wires, 4 nets, 24 components, F1=1.000. Simpler, easy to follow.
- **C63_D2_P3** — 72 wires, F1=1.000. Maximum-complexity stress test.

Visualization script: `paper/ieee-paper/generate_candidates_v2.py`.

## Connectivity (join) — human-verified net-level benchmark

**Status:** node joining is validated on human-verified net-level ground truth.
**`scale_completion`** (high-precision scale-relative endpoint-graph base + degree-budget
floating-pin completion at reach 4×scale) is the promoted default since Jun 2026.

The primary metric is **micro-F1** (pair-level, pooled across images); macro is reported
alongside.

| Method | micro-F1 |
|---|---|
| **`scale_completion` (default)** | **0.890** (P 0.919 / R 0.864, macro 0.901) |
| `degree_budget` (prior default; completion on the `graph_rescue` base) | 0.829 |
| `graph_scale` | 0.816 |
| `graph_rescue` | 0.787 |
| `production` (radius union-find) | 0.667 |
| Connected-component net tracing (identical detected wires) | 0.624 |
| Hough + proximity | 0.805 |

Measured on the 31-image human-verified net-GT. The result is validated on independent synthetic
ground truth as well, which rules out bootstrap bias. Detection is **not** the bottleneck: on
perfect ground-truth wires the **micro-F1 is unchanged at 0.890** (macro +0.015 to 0.916).
`degree_budget` and `graph_rescue` remain registered as fallbacks.

### Evaluation tooling

Under `wire_detection/benchmark/`:

- `join_eval_real_f1`
- `join_variant_search`
- `cc_baseline`
- `cc_baseline_detected`
- `detection_ceiling`
- `build_verified_gt`

Results land in [`docs/research/experiments/SUMMARY.md`](research/experiments/SUMMARY.md).

### Caveat: the double-extend bug

!!! note "Applies to the join-strategy comparison table below"
    A double-extend bug was fixed: the `degree_budget` registry entry carried `extend=12` *and*
    the completion function extends 12px internally, giving 24px in the `run_strategy` / API path,
    which over-merged. It is now a single 12px extension.

    The zero-regressions and dominance claims hold, but the exact per-image percentages and
    self-loop counts in the join-strategy table were measured **before** the fix — re-run the
    production pipeline to refresh them. The standalone `bench_degree_budget.py` was unaffected,
    because it calls the completion function directly and therefore always single-extends.

### Join strategy comparison (134-image GT set)

Fresh `best_candidate_v4` detection, post OBB/capacitor fix, Jun 15 2026. Subject to the
double-extend caveat above.

| Strategy | balanced | composite | wires-used% | nets/comp | self-loop | floating | giant |
|----------|----------|-----------|-------------|-----------|-----------|----------|-------|
| **degree_budget** (default at the time) | **0.2710** | **0.2689** | 99.4 | 0.213 | 213 | 1084 | 109 |
| graph_scale | 0.3610 | 0.3584 | 99.5 | 0.149 | 62 | 1726 | 86 |
| graph_dir_30 | 0.3613 | 0.3588 | 99.5 | 0.145 | 71 | 1711 | 94 |
| graph_rescue | 0.3679 | 0.3676 | 99.4 | 0.124 | 213 | 1607 | 102 |

`degree_budget` = `graph_rescue` + floating-pin recovery. Lowest balanced + composite scores, zero
regressions.

Full details: [`docs/research/join-verification.md`](research/join-verification.md).

## Component detection model (Jun 2026)

**Weights:** `models/component_detection/yolo26m_obb_16class_aug.pt` (46 MB, not in git — see
`.gitignore`; fetch with `uv run scripts/download_model.py`).
**SHA256:** `d700b33f90191968af9f7f2798fff5e90a3f1ea473b811adc241bc570987264d`
**HuggingFace:** [boscochanam/circuit-component-detector](https://huggingface.co/boscochanam/circuit-component-detector)
**Dataset:** [CGHD-1152 (Kaggle mirror)](https://www.kaggle.com/datasets/johannesbayer/cghd1152)

YOLO26M-OBB, trained on the CGHD dataset (the same dataset used for the wire-detection pipeline).

- **16 classes**, merged down from the 61 original classes (see the confounding caveat on key
  learning 1 below before treating the merge as a measured win). The
  exact mapping is committed at
  [`docs/research/experiments/detector/class_map.json`](research/experiments/detector/class_map.json):
  **8 merge targets** (electrically-equivalent variants of `resistor`, `capacitor`, `diode`,
  `transistor`, `inductor`, `voltage_source`, `integrated_circuit`, `operational_amplifier`),
  **7 pass-through** classes (`terminal`, `crossover`, `switch`, `text`, `junction`, `gnd`, `vss`),
  and **`other`**, which absorbs **30 of the 61 originals** and is therefore not a discriminative
  label.
- **2,652 train / 468 val** images, 85/15 random split.
- **`drafter_0` excluded** — its drawing style differs from every other drafter.

### Performance (best: run 2)

These are the metrics of the **released `best.pt`** — the maximum-fitness checkpoint, at
**epoch 121** — which is the file `scripts/download_model.py` fetches. They are *not* the final-epoch
numbers.

| Metric | Value |
|--------|-------|
| mAP50 | **89.0%** |
| mAP50-95 | 78.5% |
| Precision | 95.8% |
| Recall | 88.6% |
| Best-fitness epoch | 121 (of 200) |

Ultralytics saves `best.pt` at maximum fitness (`0.1*mAP50 + 0.9*mAP50-95`), not at the last epoch.
The **final** epoch (200) is `last.pt`, which is **not distributed**; it scored mAP50 88.47,
mAP50-95 78.31, precision 95.62, recall 88.63. Earlier revisions of this document reported those
final-epoch figures (88.5 / 78.3 / 95.6 / 88.6), i.e. the metrics of a checkpoint nobody can
download.

### Per-class recall

- **Perfect:** `operational_amplifier` (100%)
- **Strong (>90%):** `inductor`, `voltage_source`, `capacitor`, `transistor`, `resistor`, `diode`,
  `integrated_circuit`, `other`
- **Moderate (80-90%):** `gnd`, `text`, `junction`, `terminal`, `switch`, `vss`
- **Weak (<80%):** `crossover` (70.7%) — crossing wires are visually ambiguous

### Training configuration

- Augmentations: `mosaic=1.0`, `mixup=0.15`, `degrees=10`, `translate=0.2`, `scale=0.5`, `shear=2`,
  `fliplr=0.5`, `flipud=0.1`, `erasing=0.4`, HSV jitter, RandAugment
- Optimizer: AdamW, `lr0=0.001`, `cos_lr=true`
- Image size: 1024. Batch: 17.

### Key learnings

1. **Class merging:** 61 → 16 classes improved mAP from ~50% to 85%. **Confounded — the paper does
   not cite this.** The ~50% figure comes from a YOLO26L / 150-epoch / batch-5 run; the 85% figure
   from a YOLO26M / 200-epoch / batch-17 run. Model size, schedule length and batch size all changed
   alongside the class count. The merge plausibly helps; this comparison cannot say by how much.
2. **Augmentations:** +3.5% mAP over the no-augmentation baseline. A cleaner comparison (same
   schedule, same batch), but the baseline's `results.csv` is missing 53 epoch rows, so it is
   reported as a log-derived observation, not a measured ablation.
3. **M model beats L model:** the smaller model generalizes better at this dataset size once
   augmentations are on. **Confounded — the paper does not cite this either.** It compares YOLO26L
   *without* augmentation against YOLO26M *with* augmentation; no L + augmentation run exists.
4. **Crossover remains hardest:** two crossing wires look identical to a regular wire.
5. **Class weighting did not help:** run 3 (`augmentations_weights_16class_yolo26m`) never beat
   run 2 on any metric.

### Provenance

Training logs for all three runs — `results.csv` and `run_metadata.json` each — are committed at
[`docs/research/experiments/detector/`](research/experiments/detector/README.md), alongside `class_map.json`
and a [`README.md`](research/experiments/detector/README.md) that derives every number here from
those CSVs (the README is the source of record). The 89.0% mAP figure is the epoch-121 row of
`augmentations_16class_yolo26m/results.csv`, and it reproduces the metrics embedded in the published
HuggingFace weights (SHA256 above) exactly.

Caveat: the *baseline* run's `results.csv` is missing 53 epoch rows and is not fully
reconstructible. No number in the paper depends on it.

## Historical evaluations

Earlier exploration is preserved but superseded, and the paper does not depend on it:

- [`docs/research/expanded-benchmark.md`](research/expanded-benchmark.md) — the 36-config
  prefix-match ranking, best F1 0.8334.
- [`docs/research/connectivity.md`](research/connectivity.md) — connectivity-based false-positive
  filtering; no configuration beats the 0.8334 baseline.
- [`docs/research/netlist-exploration.md`](research/netlist-exploration.md) — endpoint clustering
  for pin discovery (153.4% connectivity vs 29.8% for static pins).
- [`docs/research/iteration-tracker.md`](research/iteration-tracker.md) — the exhausted
  false-positive-removal leads, including the machine-learning classifiers that overfit.
- [`docs/research/mapping-experiment.md`](research/mapping-experiment.md) — wire-to-component
  mapping, superseding an early 69% nearest-component result with 93.10% endpoint accuracy.

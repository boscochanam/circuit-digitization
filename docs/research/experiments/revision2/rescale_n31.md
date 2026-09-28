# Controlled image rescaling: 31-image human-verified net-GT (R1-3, R2-6)

Scripts: `wire_detection/benchmark/revision2/{rescale_eval,methods,size_dispersion,synth_mixed_size,plot_rescale}.py`.
Data: `rescale_n31.json` (all per-image counts, bootstrap CIs, config, seed), `size_dispersion_n31.json`,
`synth_mixed_size.json`. Figure: `paper/ieee-paper/figures/rescale_robustness.pdf`.
Run on claw (repo at 925a86f, clean tree; scripts ran from `~/rev2_scratch`). The runs are deterministic: a second full run produced identical per-image counts.

## Setup

- All 31 images (704x704 px) resampled by f in {0.35, 0.5, 0.75, 1, 1.5, 2, 3} (INTER_AREA below 1, INTER_CUBIC above 1).
  GT component OBBs and GT wire labels are YOLO-normalised, so they are re-projected onto the
  resized grid with the paper's own parsers (`parse_components`, `parse_gt_wires`).
- **Arm A (join only):** annotated GT wires plus GT boxes, both scaled.
  **Arm B (full):** wires re-extracted from the rescaled image with the frozen extractor. Its Sauvola window, `min_area`, occlusion margins and ROI padding are all in pixels. GT boxes are scaled.
- Methods: `scale_completion` (shipped default, tau = k*s with pixel clamps); `scale_completion_unclamped`
  (the same with the clamps removed); `fixedpx_completion` (the same algorithm with every tolerance fixed:
  tau_pin/join/t = 30/14/10 px, which is the fixed-px ablation config, plus a completion tau of 30 px, i.e. reach 120 px);
  `graph_scale` (base, no completion); `graph_dir_30` (fixed-px base); `production` (30 px radius union-find).
  No pipeline code was changed. The two custom variants swap completion-module globals inside the process only.
- Metric: component-pair connectivity, micro (pair-pooled) as the primary metric. The CIs come from a paired image bootstrap
  (B = 10,000, seed 20260928).

**Reproduction at f = 1.0:** Arm B `scale_completion` gives 418/37/66, micro-F1 0.890 (P 0.919 / R 0.864, macro 0.901), which matches
the paper exactly. Arm A gives 420/40/64, micro-F1 0.890, which matches `fair_join_comparison_n31.json`. `graph_scale` 0.816,
`graph_dir_30` 0.820 and `production` 0.667 also match the earlier results.

## Results: micro-F1

### Arm A: join only (annotated wires)

| method | 0.35 | 0.5 | 0.75 | 1.0 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|
| **scale_completion** | 0.855 | 0.895 | 0.886 | **0.890** | 0.888 | 0.887 | 0.887 |
| scale_completion_unclamped | 0.874 | 0.868 | 0.878 | 0.884 | 0.884 | 0.885 | 0.881 |
| fixedpx_completion | 0.837 | 0.879 | 0.886 | 0.891 | 0.900 | 0.888 | 0.878 |
| graph_scale (base) | 0.817 | 0.841 | 0.836 | 0.842 | 0.835 | 0.831 | 0.832 |
| graph_dir_30 (fixed-px base) | 0.808 | 0.838 | 0.831 | 0.842 | 0.842 | 0.834 | 0.835 |
| production (30 px) | 0.702 | 0.702 | 0.737 | 0.690 | 0.575 | 0.429 | 0.153 |

scale_completion TP/FP/FN: 461/133/23, 441/61/43, 416/39/68, 420/40/64, 416/37/68, 412/33/72, 412/33/72.
Macro-F1: 0.910, 0.931, 0.924, 0.916, 0.924, 0.922, 0.925.
Paired change vs f = 1 [95% CI]: −0.035 [−0.061, −0.005], +0.005 [−0.011, +0.023], −0.004 [−0.017, +0.011], —,
−0.002 [−0.016, +0.014], −0.003 [−0.027, +0.019], −0.003 [−0.031, +0.022].

### Arm B: full pipeline (wires re-extracted)

| method | 0.35 | 0.5 | 0.75 | 1.0 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|
| **scale_completion** | 0.580 | 0.690 | 0.811 | **0.890** | 0.877 | 0.866 | 0.866 |
| scale_completion_unclamped | 0.488 | 0.642 | 0.802 | 0.867 | 0.878 | 0.871 | 0.864 |
| fixedpx_completion | 0.588 | 0.700 | 0.827 | 0.884 | 0.883 | 0.871 | 0.833 |
| graph_scale (base) | 0.210 | 0.417 | 0.709 | 0.816 | 0.858 | 0.846 | 0.836 |
| graph_dir_30 (fixed-px base) | 0.217 | 0.434 | 0.712 | 0.820 | 0.858 | 0.849 | 0.827 |
| production (30 px) | 0.595 | 0.642 | 0.687 | 0.667 | 0.610 | 0.468 | 0.187 |

scale_completion TP/FP/FN: 210/30/274, 278/44/206, 354/35/130, 418/37/66, 443/83/41, 427/75/57, 423/70/61.
Macro-F1: 0.517, 0.641, 0.804, 0.901, 0.888, 0.881, 0.875.
Paired change vs f = 1: −0.310 [−0.407, −0.221], −0.200 [−0.277, −0.129], −0.079 [−0.145, −0.028], —,
−0.013 [−0.045, +0.018], −0.024 [−0.062, +0.011], −0.024 [−0.063, +0.009].
Detected wire count (sum over 31 images; GT = 675): 241, 403, 596, 666, 716, 738, 727.

### Paired scale_completion minus fixedpx_completion [95% CI]

| arm | 0.35 | 0.5 | 0.75 | 1.0 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|
| A | +0.018 [−.011,+.047] | +0.015 [+.003,+.027] | −0.000 | −0.001 | −0.012 [−.025,−.001] | −0.001 | +0.009 [−.009,+.025] |
| B | −0.008 | −0.011 [−.021,.000] | −0.016 [−.034,−.001] | +0.006 | −0.006 | −0.005 | +0.033 [+.012,+.061] |

scale_completion minus production is positive with the CI excluding 0 at every factor ≥ 0.75 in both arms, and it grows to +0.73 (A) and +0.68 (B) at f = 3.

### Clamp diagnostics (share of images where k*s falls outside the clamp, tau_pin)
f = 0.35: 100%, 0.5: 94%, 0.75: 71%, 1.0: 39%, 1.5: 35%, 2.0: 35%, 3.0: 84% (median s = 15, 22, 33, 43, 65, 86, 130 px).

## Interpretation

1. **The join holds up from 0.5x to 3x.** With annotated wires, scale_completion stays within
   0.886–0.895 (±0.005 of native) over a 6x range of resolution. Every CI includes 0. The only significant drop is at
   0.35x (median component diagonal of about 15 px), −0.035. There the lower clamps bind for every image, the effective
   tolerances are about 2.5x the scale-relative value (24 px floor vs 0.62 x 15 px), and precision falls (0.78) as neighbouring nets merge.
2. **The fixed-radius rule breaks.** Production (30 px union-find) loses 0.54 F1 by 3x, because its radius does not grow with the
   drawing and recall collapses to 0.08. It also over-merges at small scales (P 0.54).
3. **Scale-relative vs fixed-px tolerances inside the graph+completion model: the difference is small.** This has to be said honestly.
   The fixed-px variant of the same algorithm is roughly as scale-robust as the shipped one between 0.5x and 2x. The differences are ≤ 0.016 and
   mostly inside the CI. scale_completion is better where fixed px is most mismatched: A at 0.5x (+0.015, CI excludes 0), and B at 3x (+0.033, CI
   excludes 0; the fixed-px variant loses recall, R 0.81). The reason is that most of the size adaptation in the endpoint graph does not
   come from the scalar tau = k*s. It comes from component-relative geometry that every graph variant shares: component-first
   assignment with radius max(tau_pin, 0.5 x the component's own diagonal), and OBB-derived pins. So the scale robustness claim is best attributed to the
   component-relative endpoint-to-component binding plus completion, not to the median-diagonal tau alone.
4. **The clamps are a native-resolution tuning.** Removing them helps at 0.35x in arm A (0.874 vs 0.855) but costs 0.023 F1 at native
   resolution in arm B. The clamp floors therefore carry real weight on the small-drawing end of this dataset (39% of images at f = 1).
5. **At extreme sizes the full pipeline is limited by extraction, not by the join.** Arm B falls to 0.58 at 0.35x and 0.69 at 0.5x,
   while arm A stays at 0.86–0.90. The extractor finds only 241/675 wire segments at 0.35x (the Sauvola window of 67 px and min_area of 28 px
   are pixel-valued, and occlusion eats short wires). Recall drives the loss: R 0.43 at P 0.88. Completion recovers much of it
   (graph_scale base 0.21 → 0.58). Upscaling costs at most −0.024 (CI includes 0), mostly FPs from fragmented strokes.
   This supports the reviewer's observation for downscaled inputs, and it places the cause in the frozen pixel-valued extractor.
   A practical fix is to resample inputs to a nominal component size before extraction; that fix was not tested here.

## R2-6: size heterogeneity within one image

**Real images.** The electrical-component diagonal ratio max/median ranges from 1.05 to 4.76
(`size_dispersion_n31.json`). The three most heterogeneous images all contain an IC, and all three score well at native scale:
C242 (IC, max/median 4.8): 27/4/0 (F1 0.93). C66 (NE555, 4.3): 27/2/14 (F1 0.77). C15 (NE555, 2.5): 16/2/2 (F1 0.89).
The IC is not the main error source. In C66, 4 of the 14 FNs involve the IC, which accounts for 10 of the 41 GT pairs (proportional). C242 and C15 have 0 FNs involving the IC.
n = 3, so this is anecdotal.

**Synthetic (`synth_mixed_size.json`).** One axis-aligned component per authored circuit is redrawn m x
larger or smaller in both axes, keeping only geometrically clean variants. The error model is the same placeholder as the synthetic leaderboard (L1–L4, 8 seeds).
Mean F1 over L1–L4 (clean L0 in parentheses):

| group | n | scale_completion | unclamped | fixedpx_completion | graph_scale | graph_dir_30 | production |
|---|---|---|---|---|---|---|---|
| authored (control) | 15 | **0.975** (1.00) | 0.969 | 0.951 | 0.947 | 0.944 | 0.697 |
| one comp x0.5 | 51 | **0.963** (0.99) | 0.953 (0.97) | 0.933 (1.00) | 0.935 | 0.925 (1.00) | 0.697 |
| one comp x2 | 36 | **0.969** (1.00) | 0.964 | 0.940 | 0.937 | 0.935 | 0.690 |
| one comp x3 | 36 | **0.970** (1.00) | 0.965 | 0.939 | 0.936 | 0.933 | 0.693 |

The control reproduces `synthetic_leaderboard.json` (0.975 / 0.944). Enlarging one component 2–3x costs scale_completion
about 0.005, and it keeps first place with a lead of about 0.03 over the fixed-px completion. Shrinking one component is the harder case: −0.012. In
the 5 wheatstone variants with one 40x15 px bridge arm, the clean L0 join makes one spurious pair (F1 0.923) under all
scale-relative methods and production, while the fixed-px graphs stay exact. A component much smaller than the median is the
failure mode of a median-derived tau.

## Caveats

- Rescaling simulates resolution/zoom change, not different drafting styles (pen width, relative symbol size). Pen strokes scale with the image,
  so this tests scale invariance, not true intra-drawing heterogeneity.
- Integer truncation of re-projected coordinates adds about 1 px of noise at small f. Pin-discovery constants (DBSCAN eps 20 px,
  max_comp_dist 50 px, 15 px override gate) are fixed pixels and are shared by every method.
- The fixed-px completion tau (30 px) is a chosen reference point, not a tuned value. Only one fixed-px operating point was tested.
- Components are GT boxes in both arms. Detector (YOLO) behaviour under rescaling is not measured.
- The synthetic error model is in fixed pixels and uncalibrated (see `synthgt/synthesize.py`). The synthetic numbers are a robustness
  signal only.

# Revision 2: paired statistics, complexity strata, size dispersion (N=31)

> **Label correction, 2026-10-05.** Four images of the 31-image human-verified benchmark were corrected (plain crossings are not connections; C112, C242, C66, C15). Numbers in this file that depend on the 31-image nets predate the correction; the current values (e.g. ours 0.884, VLM 0.946, end to end 0.602, reference vs human 0.971) are in `docs/research/experiments/SUMMARY.md` (Revision 2) and the paper. Regenerated JSON next to this file is current.

Reviewer points: R2-1 (statistical testing), R1-5 (recall on complex circuits), R2-6 (component-size variation within an image).
All numbers are in `stats_strata_n31.json`. Scripts are in `wire_detection/benchmark/revision2/`:

- `collect_per_image.py` was run on claw. It produces `per_image_inputs_n31.json` (per-image Hough counts plus component-size stats).
- `stats_strata.py` does the pure analysis and runs locally.

Seeds: bootstrap 20260928, permutation 20260929. B=10,000 bootstrap resamples, 100k Monte Carlo permutations.

## 0. Reproduction of the paper numbers

Pooled micro-F1 and macro-F1 were recomputed from per-image tp/fp/fn. Every method matches the committed JSON exactly:

| Method | micro-F1 | macro-F1 | exact images |
|---|---|---|---|
| ours (scale_completion) | 0.890 | 0.901 | 11 |
| degree_budget | 0.829 | 0.853 | 11 |
| graph_scale | 0.816 | 0.838 | 9 |
| graph_rescue | 0.787 | 0.813 | 9 |
| production | 0.667 | 0.674 | 6 |
| Hough best (link44_reach48) | 0.805 | 0.847 | 7 |
| CCL-on-detected best (d15) | 0.624 | 0.611 | 8 |
| VLM | 0.923 | 0.9488 (committed 0.9489) | 21 |

Notes on reproduction:

- **VLM macro.** The committed value averages F1s that were first rounded to 3 dp. The unrounded mean is 0.94883, which rounds to 0.949 either way.
- **Hough per-image counts.** These were not committed before. Regenerated on claw, they reproduce the pooled counts for all 7 configs exactly.
- **Local run caveat.** The same run on the laptop does *not* reproduce: 31 of 31 images get different HDC labels. The local `roboflow_test2/` export has different `.rf.<hash>` copies. The labels claw selects match the committed `ground_truth/component_labels/` byte for byte (31/31).
- **Oracle tuning.** The Hough and CCL settings are the best on this same test set. That tuning favors those baselines.

## 1. Paired tests: ours minus comparator (positive means ours is better)

Methods used:

- Bootstrap: paired over images, B=10,000, 95% percentile CI. The p-value comes from inverting the percentile CI; its floor is about 1e-4.
- Permutation: the two methods' labels are swapped within each image. The test is exact when at most 22 images differ, otherwise Monte Carlo with 100k draws.
- Wilcoxon: signed-rank on per-image F1. Zero differences are dropped (`zero_method='wilcox'`); the Pratt variant is in the JSON.
- Holm correction is applied within each test type over the 7 comparisons.

| vs | Δ micro-F1 [95% CI] | Holm p: bootstrap | Holm p: perm (micro) | Holm p: perm (mean per-image F1) | Holm p: Wilcoxon | W/T/L |
|---|---|---|---|---|---|---|
| degree_budget | +0.061 [+0.025, +0.100] | 0.0007 | 0.0010 | 0.0037 | 0.0089 | 11/18/2 |
| graph_scale | +0.075 [+0.038, +0.113] | 0.0007 | 0.0016 | 0.0010 | 0.0048 | 14/16/1 |
| graph_rescue | +0.103 [+0.065, +0.142] | 0.0007 | 0.0001 | 0.0001 | 0.0015 | 17/14/0 |
| production | +0.224 [+0.166, +0.281] | 0.0007 | 0.0001 | 0.0001 | 0.0001 | 25/6/0 |
| Hough (oracle-tuned) | +0.086 [+0.045, +0.127] | 0.0007 | 0.0016 | 0.033 | 0.030 | 19/8/4 |
| CCL-detected (oracle-tuned) | +0.267 [+0.136, +0.409] | 0.0007 | 0.0004 | 0.0001 | 0.0003 | 21/8/2 |
| **VLM** | **−0.033 [−0.078, +0.008]** | **0.12** | **0.15** | **0.033** | **0.030** | **7/11/13** |

What the table shows:

- **Ours vs every deterministic baseline.** Ours is significantly better on every test after Holm correction. The Hough margin is the weakest on per-image-F1 tests (Holm p ≈ 0.03).
- **Ours vs the VLM, micro-F1.** The pooled micro-F1 difference is not significant (CI includes 0; p = 0.12 and 0.15). This agrees with the paper's [−0.009, +0.078] for VLM−ours.
- **Ours vs the VLM, per-image F1.** This is significant at α = 0.05 after Holm (p ≈ 0.03, 13 VLM wins vs 7 ours). The paper should not say the two are "statistically indistinguishable" without adding "on micro-F1". The VLM is better on per-image (macro) F1.

**Jackknife (leave one image out).** Ours' micro-F1 stays between 0.885 (drop C37) and 0.900 (drop C66). Under every one of the 31 deletions, the sign of the difference against each comparator is unchanged: ours stays above every baseline and below the VLM on point estimate.

## 2. Complexity strata (R1-5)

Strata are by electrical component count. Values are micro P / R / F1, with the 95% bootstrap CI for recall.

| Stratum (n images) | ours | degree_budget | graph_scale | Hough | VLM |
|---|---|---|---|---|---|
| ≤5 (15) | .952/.929 [.83,1.0]/.940 | .963/.906/.933 | .963/.906/.933 | .914/.871/.892 | 1.0/.965/.982 |
| 6–9 (4) | .912/.788 [.49,.95]/.846 | .907/.742/.817 | .907/.591/.716 | .927/.773/.843 | .982/.833/.902 |
| ≥10 (12) | .911/.862 [.79,.93]/.886 | .739/.892/.808 | .922/.709/.801 | .696/.886/.779 | .960/.868/.912 |

Ours minus comparator (Δ micro-F1) on the ≥10 stratum:

| vs | Δ micro-F1 [95% CI] |
|---|---|
| degree_budget | +0.078 [+0.031, +0.129] |
| graph_scale | +0.084 [+0.041, +0.127] |
| Hough | +0.106 [+0.058, +0.161] |
| VLM | −0.026 [−0.087, +0.030] |

Findings on complexity:

- **Ours on complex images (≥10) vs simple ones (≤5).** Recall is −0.068 lower (CI [−0.176, +0.055], permutation p = 0.32). F1 is −0.055 lower (CI [−0.119, +0.015], p = 0.16). Neither drop is significant between strata.
- **Per-image rank correlation.** Recall and F1 do fall with complexity. Spearman ρ between electrical count and recall is −0.48 (p = 0.007), and between electrical count and F1 is −0.53 (p = 0.002). Every method shows the same trend: VLM ρ(F1) = −0.51, graph_scale −0.65, degree_budget −0.59. So complex circuits are harder for all methods, including the VLM. They are not a failure mode specific to our method.
- **Strata by GT-pair count** (≤8 / 9–22 / ≥23) show the same pattern. Ours' F1 is .961 / .865 / .885.
- **Crossovers.** Ours' recall is .884 on the 23 images without a crossover and .834 on the 8 with one. The difference is −0.050 (p = 0.51) and not significant. Only 8 images have a crossover (C66 has 6).
- **Sample sizes.** The 6–9 stratum has only 4 images, so its CIs are very wide.

## 3. Component-size dispersion (R2-6)

Scale s is the middle sorted bbox diagonal over *all* parsed components, as in `join_graph.estimate_scale`. Spearman correlations for ours:

| Dispersion measure | vs F1: ρ (p) | vs F1, partial on n_electrical: ρ (p) | vs n_electrical: ρ (p) |
|---|---|---|---|
| CV, all components | +0.18 (0.33) | +0.09 (0.64) | −0.20 (0.27) |
| CV, electrical components | −0.38 (0.037) | −0.25 (0.18) | +0.34 (0.065) |
| max/min, electrical components | −0.60 (0.0004) | −0.41 (0.024) | +0.62 (0.0002) |
| max electrical diagonal / s | −0.18 (0.32) | +0.01 (0.96) | +0.37 (0.043) |

Findings on dispersion:

- **Low vs high dispersion halves** (split at the median electrical CV, 0.216). Ours' F1 is 0.922 vs 0.867. The difference is −0.055 (CI [−0.116, +0.020], p = 0.14) and not significant. Split by all-component CV instead, the halves are 0.887 vs 0.894.
- **The max/min effect is mostly complexity.** More components give a larger max/min ratio (ρ = 0.62). Once component count is controlled, the effect shrinks but survives (partial ρ = −0.41, p = 0.024).
- **The effect is not specific to our join.** The VLM correlates about as strongly (max/min vs F1: ρ = −0.55; partial −0.34, p = 0.064).
- **No sign that the scale-relative tolerance itself fails.** Size relative to the scale anchor (max electrical diagonal / s) does not correlate with F1 (partial ρ ≈ 0).
- **Images that mix a large IC with small parts.** Three images qualify: C15 (NE555, max/s = 6.8), C242 (IC, 8.9) and C66 (NE555, 9.4). Ours' F1 on them is .889, .931 and .771. Pooled over the three, micro-F1 is 0.854, vs 0.898 on the other 28 images. With n = 3 this is anecdotal. The worst of the three, C66, also has 6 crossovers and the smallest scale (s = 14.8 px).

## Caveats

- **Sample size.** N = 31 and strata are small, so the non-significant stratum differences are "not detected", not "absent".
- **Oracle-tuned baselines.** The Hough and CCL settings were chosen on the test set.
- **Multiple testing.** Holm correction covers the 7 comparisons within each test type, not across the four test types.

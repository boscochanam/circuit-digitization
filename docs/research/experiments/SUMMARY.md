# Experiment summary

Index of the committed result artifacts behind the IEEE Access manuscript (Access-2026-33821).
The revision-2 section below is current and matches `paper/ieee-paper/paper-access.tex`. The
June 2026 section further down is kept for history; where the two disagree, revision 2 wins.

Conventions for every connectivity number: component-pair **micro-F1** (pairs of electrical
components R/C/L/D/Q/V/IC sharing a net, pooled over images) is primary, macro-F1 alongside.
Connectivity is read from drawn wires only (terminals and supply symbols are wire ends; no label
reading). Joins receive annotated component boxes and the pipeline's own detected wires unless
noted.

## Revision 2 (Sept 2026)

Scripts: `wire_detection/benchmark/revision2/`. Results: `docs/research/experiments/revision2/`.
Seeds: bootstrap 20260928, permutation 20260929; B = 10,000 image-level resamples; Holm
correction within each test type.

### Paired tests, strata, size dispersion (31 human-verified images)
`revision2/stats_strata_n31.md` / `.json` (`stats_strata.py`; per-image Hough counts from
`collect_per_image.py`, `per_image_inputs_n31.json`).
- All paper numbers reproduce from per-image counts: ours 0.890 (P 0.919 / R 0.864, macro 0.901).
- Ours beats every deterministic comparator on every test after Holm: rescue graph + completion
  +0.061 [+0.025, +0.100], scale-relative base +0.075, rescue base +0.103, radius union-find
  +0.224, Hough (oracle-tuned) +0.086, CCL on detected wires (oracle-tuned) +0.267.
- VLM (Claude Opus 4.8): ours −0.033 [−0.078, +0.008] on micro-F1, not significant (Holm p 0.12
  bootstrap / 0.15 permutation). Per image the VLM is better (W/T/L 7/11/13, Wilcoxon Holm
  p = 0.030). Do not call the two "statistically indistinguishable".
- Leave-one-image-out: ours 0.885–0.900; no deletion flips the sign of any comparison.
- Complexity: F1 falls with electrical-component count for every method (ours Spearman
  ρ = −0.53); the ≤5 vs ≥10 recall drop (−0.068) is not significant. On ≥10 components ours
  beats the deterministic comparators by +0.078 to +0.106.
- Size dispersion: max/min electrical diagonal vs F1, partial on count, ρ = −0.41 (p = 0.024);
  similar for the VLM. Size relative to the scale anchor is uncorrelated with F1.

### Controlled rescaling (31 images)
`revision2/rescale_n31.md` / `.json` (`rescale_eval.py`, `methods.py`, `plot_rescale.py` →
`paper/ieee-paper/figures/rescale_robustness.pdf`); `size_dispersion_n31.json`
(`size_dispersion.py`); `synth_mixed_size.json` (`synth_mixed_size.py`).
- Factors 0.35–3×. Join only (annotated wires): within ±0.005 of native from 0.5× to 3×;
  −0.035 [−0.061, −0.005] at 0.35×. Radius union-find: 0.690 → 0.153 at 3×.
- Full pipeline (wires re-extracted): 0.580 / 0.690 / 0.811 / 0.890 / 0.877 / 0.866 / 0.866.
  Downscaling loss comes from the pixel-valued extractor (241 of 675 segments found at 0.35×).
- Fixed-pixel tolerances in the same algorithm stay within 0.016 between 0.5× and 2×; most of
  the scale robustness comes from component-relative assignment plus completion.
- Synthetic mixed-size: enlarging one component costs ~0.005; shrinking one costs 0.012.

### End to end with the trained detector (31 images)
`revision2/e2e_detected_n31.md` / `.json` (`e2e_detected.py`, `stretch_check.py` →
`stretch_check_n31.json`, `make_e2e_md.py`).
- Detector on the EXIF-corrected CGHD original at 1024 px, conf 0.5: micro-F1 **0.627**
  [0.519, 0.731] (P 0.603 / R 0.653). Electrical detection P/R/F1 0.886 / 0.858 / 0.872.
- Sequential decomposition of the −0.263 gap: missed components −0.131, spurious detections
  −0.072, localization −0.043, classification −0.017.
- **The old 0.247 was a bug**: `detected_boxes_eval.py` at fe109ec relabelled classes with a
  hardcoded index table that matched the checkpoint on 1 of 16 indices. The fixed script gives
  0.504 on the 704×704 copies (`e2e_old_script_*.json`).
- Orientation: 0.491 on the 14 re-oriented benchmark copies vs 0.739 on the other 17.
- All 13 annotated crossovers detected as crossovers; the e2e numbers are not held-out detector
  estimates (the training split manifest was not retained).

### Image provenance
`revision2/stretch_check_n31.json`, `revision2/image_modality.json`,
`revision2/cghd_ref/transform_probe.json`.
- The 704×704 benchmark copies are non-aspect-preserving Roboflow resizes of the CGHD originals;
  14 of 31 are also flipped/rotated. 16 of 31 net-benchmark and 45 of 134 wire-benchmark copies
  are CGHD binary stroke maps, not photographs.
- Wire F1 on the 134: 0.976 best variant (a16, `wire_a16_summary_jun2026.json`), 0.973 deployed
  12°/8 px setting (`revision2/wire_rerun_deployed.json`); by modality (paper Sec. V-B) 0.967 on
  the 89 photographs, 0.986 on the 45 stroke maps (flags in `image_modality.json`).

### Independent held-out benchmark (164 CGHD photographs, 24 drafters)
`revision2/cghd_ref_benchmark.md` / `.json` (`cghd_ref.py`, `cghd_validate.py`,
`cghd_transform_probe.py`, `cghd_resolution.py`, `cghd_eval.py`, `cghd_stats.py`,
`cghd_input_ablation.py`); reference nets in `ground_truth/cghd_ref/cghd_ref_nets.json`;
per-image raw outputs in `revision2/cghd_ref/`.
- Reference nets derived from CGHD v12 (Zenodo 10056817) stroke maps + symbol polygons; 179 of
  257 images pass the quality checks; 164 clean images outside the 31 form the primary set
  (3874 reference pairs). Input: photo, long side 1024 (fixed on wire-level labels first).
- Reference vs human nets on the 17 overlaps: micro-F1 0.939 (P 0.993 / R 0.891); 0.964 on the
  15 clean ones.
- Ours **0.711** [0.671, 0.748] (P 0.766 / R 0.664, macro 0.724). Rescue graph + completion
  0.659, scale-relative base 0.595, rescue base 0.592, CCL 0.594, radius union-find 0.518, Hough
  0.480. Every difference Holm p = 0.0006 (test floor).
- Robustness: strict held-out (155) 0.707; all 257 incl. unclean 0.626; stroke-map input 0.775.
  Per drafter 0.465–0.917 (median 0.709).
- Gap 0.890 → 0.711 is mostly input modality (photo vs stroke map): on the 17 overlaps ours
  scores 0.896 on the benchmark copies and 0.728 on photographs at long side 1024.

### Extended scoring conventions (164 / 139 images)
`revision2/cghd_ref_extended_scoring.md` / `.json` (`cghd_eval_ext.py` →
`revision2/cghd_ref/cghd_eval_ext_photo.json`, `cghd_extended_scoring.py`).
- A (more device types scored): 0.709; B (switches closed): 0.712; C (grounds merged): 0.679;
  A+B+C: 0.676. Ours first in every variant (weakest margin +0.030 vs rescue + completion,
  A+B+C on 139, Holm p = 0.025).
- Excluding the 25 wire-benchmark overlaps (139 images), primary scoring: 0.709; by drawing
  (123 images): 0.704.
- Supporting inventories: `revision2/heldout_unscored_parts.json`, `revision2/heldout_strata_prf.json`.

### Reference audit (40 random held-out draws)
`revision2/cghd_audit_results.json` (`cghd_audit_score.py`); audited nets, timing log and model
pre-screen in `ground_truth/cghd_ref_audit/` (`cghd_audit_export.py`, `cghd_audit_ui.py`,
`cghd_audit_overlays.py`).
- 37 scored: 23 human-verified, 11 blind-model-matched, 3 model-adjudicated; 3 densest (21–30
  electrical components) excluded.
- Reference vs final nets: micro-F1 **0.988** (P 1.000 / R 0.975; 853 pairs), exact on 32/37.
  Human-checked 23 alone: 0.988, exact on 21.
- Ours vs final nets 0.764; +0.055 [+0.026, +0.084] over rescue + completion.
- Median human check 85 s per image (22 timed saves).

---

# June 2026 join method study (historical)

> Superseded where revision 2 disagrees. In particular: the "detection is not the bottleneck"
> claim below is conditional on annotated component boxes and does not hold end to end (0.627 with
> the trained detector); "statistically indistinguishable" and cost claims about the VLM are
> withdrawn (see revision 2).


All on the **31-image human-verified net-level GT** (`ground_truth/real_nets_verified.json`),
component-pair F1 over SPICE-active components. **Primary metric = micro-F1** (pair-level, pooled
across images); macro-F1 reported alongside. Branch `experiments/join-method-benchmark`.

## Join strategy ranking (real detected wires, verified GT)
| strategy | micro-F1 | macro-F1 |
|---|---|---|
| **scale_completion** (NEW default) | **0.890** | 0.901 |
| degree_budget (prev default) | 0.829 | 0.853 |
| graph_scale | 0.816 | 0.838 |
| graph_rescue | 0.787 | 0.813 |
| production (radius) | 0.667 | 0.674 |

scale_completion micro precision 0.919 / recall 0.864.

scale_completion = graph_scale base (scale-relative endpoint graph, no end-extension/dead-end
rescue → high precision) + degree-budget floating-pin completion at reach 4×tau. Reach sweep is a
broad plateau (F1 0.895–0.907 over reach 3–5) → robust, not overfit.

## Independent validation (authored synthetic GT, no graph_scale seeding)
scale_completion 0.975 mean-F1 (#1) ≥ degree_budget 0.972 ≥ graph_rescue 0.957 ≥ graph_scale
0.947. Confirms the real-GT win is not bootstrap bias.

## Literature baseline (connected-component net tracing)
- Raw-pixel erase-and-CCL (SINA/AMSnet/Bayer recipe): no precise operating point on hand-drawn
  photos — F1 0.11–0.24 at sensible gap-bridging; reaches 0.82 only with degenerate 59px closing
  (P collapses to 0.75, merges by proximity).
- CCL on the SAME detected wires (isolates join algorithm): best micro-F1 0.624 (P 0.965 / R 0.461)
  vs our 0.890.

## Detected vs annotated wires (historical heading: "detection is not the bottleneck")
scale_completion micro-F1 0.890 on detected wires = **0.890 on perfect GT wires** (micro unchanged;
macro 0.901 → 0.916, +0.015) → detector costs ~0 micro / +0.015 macro. Remaining gap = intrinsic
join ambiguity, not detection. (Wire-detection F1 itself 0.976.)

## VLM (Claude Opus 4.8) connectivity vs verified GT (N=31 e2e)
micro-F1 0.923 (P 0.970, R 0.880, macro 0.949); exact on 21/31 images; synthetic authored control
0.99. Paired VLM−ours micro diff +0.033, bootstrap 95% CI [−0.009, +0.078] (includes 0 → not significant on micro-F1; per image the VLM is better, see revision 2). Precise (rarely invents a wrong connection) but misses pairs on complex circuits;
~10^5 tokens/image, free-form (non-simulatable), no structural guarantee. Matches the geometric
pipeline's accuracy at far higher cost.

## Caveats
N=31 (small); net-GT bootstrapped by graph_scale then human-corrected (mitigated by synthetic
validation + the human catching graph_scale's over-splits during verification). 2 images dropped
by the sanity filter (C8_D1_P3 BJT-in-4-nets, C105_D1_P4 IC-isolated edit-slips). VLM e2e now N=31.

## Classical connectivity baselines (best config over a tolerance sweep, verified GT)
| baseline | micro-F1 | P | R |
|---|---|---|---|
| **scale_completion (ours)** | **0.890** | 0.919 | 0.864 |
| Hough + proximity (Reddy&Panicker family) | 0.805 | — | — |
| connected-components on detected wires | 0.624 | 0.965 | 0.461 |
| raw-pixel erase-and-CCL | ~0.24 sane / 0.82 degenerate | — | — |
Hough denoises via line-fitting → strongest classical baseline, but still −0.085 vs ours, lower recall.

## Deeper literature pass (2026-06-28, beyond the first agent sweep)
- **Peker et al.** (IEEE Access 2026, arnumber 11359167) — closest contemporary; contour node detection
  + LTspice validation; their own MOSFET set, 85.33% hand-drawn / 93.33% printed whole-netlist. Added.
- **Netlistify** (Huang, Chen, Ho, Kang, Lin, Liu, Ren; NVIDIA, MLCAD 2025) — LEARNED Transformer
  connectivity, +12.4% F1 over AMSnet on PRINTED AMS. Not runnable on hand-drawn w/o retraining. Added.
- **CircuitNet** (GitHub aaanthonyyy) — open hand-drawn, traditional CV + CNN + heuristic netlist gen;
  early-stage notebooks. Added as related open work.
- Others noted (related work only, not comparable): ML-netlisting-subcircuits (IEEE 10988466),
  hand-drawn signal-integrity netlisting (10754479), offline hand-drawn netlist (10410980), Enginuity
  multi-domain diagram dataset (arXiv 2601.13299), OmniSch PCB benchmark (2604.00270).
- **Comparability verdict:** learned methods (Netlistify, Hu GAT) train on printed AMS → not runnable on
  our hand-drawn CGHD without their data/models. Reproducible-on-our-benchmark baselines = classical
  (CCL, Hough) — both implemented and beaten by ours. SINA/CircuitNet code exists but adapting to CGHD
  net-GT is high-effort/uncertain; their connectivity recipe (CCL/contour) is already represented.

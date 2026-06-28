# Experiment summary — join method study on human-verified net-GT (2026-06-28)

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

## Detection is not the bottleneck
scale_completion micro-F1 0.890 on detected wires = **0.890 on perfect GT wires** (micro unchanged;
macro 0.901 → 0.916, +0.015) → detector costs ~0 micro / +0.015 macro. Remaining gap = intrinsic
join ambiguity, not detection. (Wire-detection F1 itself 0.976.)

## VLM (Claude Opus 4.8) connectivity vs verified GT (N=31 e2e)
micro-F1 0.923 (P 0.970, R 0.880, macro 0.949); exact on 21/31 images; synthetic authored control
0.99. Paired VLM−ours micro diff +0.033, bootstrap 95% CI [−0.009, +0.078] (includes 0 → statistically
indistinguishable). Precise (rarely invents a wrong connection) but misses pairs on complex circuits;
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

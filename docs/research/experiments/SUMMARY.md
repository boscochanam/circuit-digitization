# Experiment summary — join method study on human-verified net-GT (2026-06-28)

All on the **31-image human-verified net-level GT** (`ground_truth/real_nets_verified.json`),
component-pair F1 over SPICE-active components. Branch `experiments/join-method-benchmark`.

## Join strategy ranking (real detected wires, verified GT)
| strategy | F1 | P | R |
|---|---|---|---|
| **scale_completion** (NEW default) | **0.901** | 0.936 | 0.888 |
| scale_completion_w (witness-only) | 0.907 | 0.936 | 0.898 |
| degree_budget (prev default) | 0.853 | 0.866 | 0.879 |
| graph_30 / graph_dir_30 | 0.842 | 0.918 | 0.801 |
| graph_scale | 0.838 | 0.920 | 0.795 |
| graph_full / graph_rescue | 0.813 | 0.841 | 0.807 |
| production (radius) | 0.674 | 0.850 | 0.629 |

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
- CCL on the SAME detected wires (isolates join algorithm): best 0.611 (15px dilate) vs our 0.901.

## Detection is not the bottleneck
scale_completion on detected wires 0.901 vs perfect GT wires 0.916 → detector costs only +0.015
F1. Remaining gap = intrinsic join ambiguity, not detection. (Wire-detection F1 itself 0.976.)

## VLM (Claude Opus 4.8) connectivity vs verified GT (N=9 e2e subset)
0.90 F1 (P 0.95, R 0.87); synthetic authored control 0.99. Precise (rarely invents a wrong
connection) but misses pairs on complex circuits; ~10^5 tokens/image, free-form (non-simulatable),
no structural guarantee. Matches the geometric pipeline's accuracy at far higher cost.

## Caveats
N=31 (small); net-GT bootstrapped by graph_scale then human-corrected (mitigated by synthetic
validation + the human catching graph_scale's over-splits during verification). 2 images dropped
by the sanity filter (C8_D1_P3 BJT-in-4-nets, C105_D1_P4 IC-isolated edit-slips). VLM e2e still N=9
(new images lack VLM responses).

## Classical connectivity baselines (best config over a tolerance sweep, verified GT)
| baseline | F1 | P | R |
|---|---|---|---|
| **scale_completion (ours)** | **0.901** | 0.94 | 0.89 |
| Hough + proximity (Reddy&Panicker family) | 0.847 | 0.86 | 0.87 |
| connected-components on detected wires | 0.611 | 0.88 | 0.53 |
| raw-pixel erase-and-CCL | ~0.24 sane / 0.82 degenerate | — | — |
Hough denoises via line-fitting → strongest classical baseline, but still −0.05 vs ours, lower recall.

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

> 12 comments, one-shot resubmission. One row per comment: what was asked, what changed, and what is still open. Manuscript sources: paper-access.tex (A) and paper-build.tex (B), kept in sync. Work line: main.

## All comments in one table

| Comment | Asked | Done | Remaining |
|---|---|---|---|
| R1-1 single collection, 31 images | Only 31 hand-verified images from a single collection, with wide confidence intervals: no proof the method works on other drawing styles or at larger scale, and the hand-verified labels themselves carry possible residual bias. | Results labeled as within-collection only, with drafter groups presented descriptively (16 direct and 15 inferred assignments disclosed, per-drafter table included); no broad claims and no held-out-drafter experiment; residual label bias disclosed as mitigated but not eliminated, with independently authored synthetic data as the second leg; future expansion described as future work. | Owner read-through |
| R1-2 complex parts | Which complex devices are really handled: pin modeling for non-trivial parts, and switches currently exported as plain resistors. | New capability table separating tested connectivity, estimated pins, and illustrative export, with a metric-boundary row; switch behavior stated exactly as the code does it (midpoint pins, conditional 0.001-ohm emission). | Owner read-through |
| R1-3 hand-set thresholds | Fixed scale-relative thresholds set by hand, including the alpha the reviewer names; no adaptive learning; behavior at size extremes unknown. | All values stated plainly (alpha 0.35 fallback-only with formula, multipliers 0.62/0.30/0.20, clamps, 4x reach, macro sweep 0.895-0.903); untested extremes admitted. | Nothing |
| R1-4 no values, can't simulate | No component values are read, so the output cannot simulate despite SPICE-format claims. | Scope stated in abstract, intro, and conclusion; retitled including heads and diagram; export labeled illustrative throughout, external values required. | Nothing |
| R1-5 small circuits only | Narrow coverage of 3 to 14 supported parts with median 7; dense buses and multilayer crossings untested. | Limits stated; true distribution printed in the caption (15 at most 5, 12 at least 10, median 7, range 3-14); nothing claimed beyond it. | Nothing |
| R1-6 memristor citations | Cite two suggested papers (memristor neural circuit with classical conditioning; memristive decision-making for navigation) in the SPICE-simulation sections. | Both checked and cited in Related Work with full references (IEEE Trans. Consumer Electronics, Feb 2026; IEEE Trans. Industrial Informatics, vol. 22). | Template check |
| R2-1 statistics, roadmap | Statistical treatment of the results plus a research roadmap; historical timing data missing. | Sampling in four strata with independent annotation and adjudication described; roadmap added; missing timing honestly noted. | Owner read-through |
| R2-2 VLM comparison | Whether the VLM comparison is fair (it receives annotated boxes) and how cost is framed. | Labeled as a diagnostic with identical annotated inputs (21/31 exact on both sides); no equivalence or cost claims. | Nothing |
| R2-3 title overclaims | Title promises simulation-ready SPICE output the method does not produce. | Retitled everywhere, including running heads and the pipeline diagram; metric boundary stated. | PDF rebuild |
| R2-4 crossing wires | Whether crossings get merged into junctions, including detector misses, and what that costs netlist correctness. | Measured tradeoff reported in full (27/4/0 goes to 19/0/8, stored artifact kept); removing edges also removes true connections, so no gain claimed; detector-miss part honestly marked unmeasured. | Nothing possible |
| R2-5 ablations | Module ablations judged severely insufficient as evidence for each part's contribution. | Real table as observed, including fixed-pixel base 0.820 vs scale-relative 0.816 and full-pipeline ties at 0.890 presented as-is without spin; missing full-occlusion and scale tests disclosed. | Nothing provable |
| R2-6 single-scalar limit | Discussion point on the limits of single-scalar evaluation. | Kept as-is; no change needed. | Nothing |

Shared language everywhere: a non-finding is not equivalence; no blanket guarantees; pair scores do not certify pin layouts; lab-condition results do not prove real-world dominance.

## Reference numbers

Join 0.890 (418/37/66) on all 31; perfect-wire 0.88983 (420/40/64). Wire ledger: 0.9755 = 10°/18px config, 0.9726 = 12°/8px production. Otsu 0.789. VLM 0.923, 21/31 exact. Reach sweep macro 0.895–0.903. Numeric gate: 192/192 stored comparisons pass.

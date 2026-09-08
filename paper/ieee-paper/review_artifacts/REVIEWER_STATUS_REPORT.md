> 12 comments, one-shot resubmission. One row per comment: what was asked, what changed, and what is still open. Manuscript sources: paper-access.tex (A) and paper-build.tex (B), kept in sync. Work line: main.

## All comments in one table

| Comment | Asked | Done | Remaining |
|---|---|---|---|
| R1-1 single collection, 31 images | Proof it works beyond one collection. | Results labeled as within-collection only, with data origins disclosed; no broad claims; future expansion described as future work. | Owner read-through |
| R1-2 complex parts | Which complex parts are really handled, and how. | New capability table separating tested connectivity, estimated pins, and illustrative export; switch behavior stated exactly as the code does it. | Owner read-through |
| R1-3 hand-set thresholds | Why fixed numbers, including the named alpha. | All values stated plainly (alpha 0.35, multipliers, clamps); untested extremes admitted. | Nothing |
| R1-4 no values, can't simulate | Without reading values the output can't simulate. | Scope stated in abstract, intro, and conclusion; retitled; export labeled illustrative throughout. | Nothing |
| R1-5 small circuits only | Coverage is narrow (3 to 14 parts, median 7). | Limits stated; true distribution printed in the caption; nothing claimed beyond it. | Nothing |
| R1-6 memristor citations | Cite two suggested papers. | Both checked and cited in Related Work with full references. | Template check |
| R2-1 statistics, roadmap | Statistical treatment plus a roadmap. | Sampling and checking process described; roadmap added; missing timing honestly noted. | Owner read-through |
| R2-2 VLM comparison | Fairness and cost framing of the VLM test. | Labeled as a diagnostic with identical inputs; no equivalence or cost claims. | Nothing |
| R2-3 title overclaims | Title promises simulatable output. | Retitled everywhere, including running heads and the pipeline diagram. | PDF rebuild |
| R2-4 crossing wires | Effect of crossings, including detector misses. | Measured tradeoff reported in full (27/4/0 goes to 19/0/8); detector-miss part honestly marked unmeasured. | Nothing possible |
| R2-5 ablations | Proof each part of the method matters. | Real table as observed, ties presented without spin; missing tests disclosed. | Nothing provable |
| R2-6 single-scalar limit | Discussion point on evaluation limits. | Kept as-is; no change needed. | Nothing |

Shared language everywhere: a non-finding is not equivalence; no blanket guarantees; pair scores do not certify pin layouts; lab-condition results do not prove real-world dominance.

## Reference numbers

Join 0.890 (418/37/66) on all 31; perfect-wire 0.88983 (420/40/64). Wire ledger: 0.9755 = 10°/18px config, 0.9726 = 12°/8px production. Otsu 0.789. VLM 0.923, 21/31 exact. Reach sweep macro 0.895–0.903. Numeric gate: 192/192 stored comparisons pass.

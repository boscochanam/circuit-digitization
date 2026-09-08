# Reviewer Response Status — IEEE Access 33821

> 12 comments, one-shot resubmission. Every item below states what the reviewer asked, what changed, where the evidence lives, and what (if anything) is still open. Manuscript sources: `paper-access.tex` (A) and `paper-build.tex` (B), kept in sync. Work line: `main`.

## At a glance

| Comment | Status | Remaining |
|---|---|---|
| R1-1 single corpus, N=31 | In manuscript | Owner read-through |
| R1-2 complex-device pins | In manuscript | Owner read-through |
| R1-3 manual thresholds | In manuscript | Nothing |
| R1-4 no OCR, not simulatable | In manuscript | Nothing (PDF rebuilds it) |
| R1-5 small circuits | In manuscript | Nothing |
| R1-6 memristor citations | Done | Template check |
| R2-1 statistics, roadmap | In manuscript | Owner read-through |
| R2-2 VLM oracle, cost | In manuscript | Nothing |
| R2-3 SPICE title | Done | PDF rebuild (T7) |
| R2-4 crossover merges | Partial by design | Nothing possible without new data |
| R2-5 ablations | Partial | Nothing further provable |
| R2-6 single-scalar limit | Closed | Nothing |

Shared language enforced throughout: nonsignificance is not equivalence; no global short-free guarantee; component-pair F1 does not certify pin topology; GT-box results do not prove end-to-end dominance.

## R1-1 — Single corpus, N=31 — In manuscript

**Asked:** 31 images from one corpus cannot establish generalization.
**Done:** Drafter groups presented as descriptive within-corpus results with direct/inferred provenance disclosed (16 direct, 15 inferred); no held-out-drafter experiment claimed; future stratified-expansion protocol described as future, not completed. Join micro-F1 0.890 reported with its 95% bootstrap CI [0.855, 0.924].
**Remaining:** owner read-through (#85).

## R1-2 — Complex-device pins — In manuscript

**Asked:** which complex devices are actually handled, and how?
**Done:** new capability table (`tab:capabilities`) separating evaluated connectivity from generic pin construction and illustrative export, with a metric-boundary row. Switch wording made exact: shorter OBB-edge midpoint pins, long-axis AABB fallback, fixed 0.001-ohm emission only when pins 0 and 1 reach distinct nodes. Verified against `netlist.py` / `spice.py`.
**Remaining:** owner read-through (#83).

## R1-3 — Manual thresholds — In manuscript

**Asked:** fixed scale-relative parameters (reviewer names alpha explicitly).
**Done:** multipliers stated as fixed and manual (0.62/0.30/0.20, clamps 24–60/11–28/8–20); directional scoring fixed at alpha 0.35, fallback-only, with the exact formula; completion reach at 4x clamped pin scale; reach sweep reported as macro 0.895–0.903; extremes (rescaling, heterogeneous symbol sizes) conceded untested. Method prose rewritten from code (`join_graph.py`, `completion.py`).
**Remaining:** nothing.

## R1-4 — No OCR, not simulatable — In manuscript

**Asked:** no component values are read, so output cannot simulate.
**Done:** scope sentences in abstract, pipeline overview, metric definition, and conclusion; retitle to Structural Circuit Netlists (title, running heads, diagram node); export labeled illustrative throughout, with external values/models required.
**Remaining:** nothing (PDF rebuild carries it).

## R1-5 — Small circuits — In manuscript

**Asked:** narrow coverage (3–14 supported components, median 7).
**Done:** dense-bus/multilayer limitation stated; histogram caption gives the true distribution (15 ≤5, 12 ≥10, median 7, range 3–14); no generalization beyond the tested population claimed.
**Remaining:** nothing (builder to reconcile histogram label during T7).

## R1-6 — Memristor citations — Done

**Asked:** cite two memristor-circuit papers.
**Done:** both records abstract-verified (IEEE TCE Feb 2026; IEEE TII vol. 22, 2026) and cited in Related Work as neighboring SPICE-deployment domains, with bibliography entries in both sources. Response flipped from decline to cited.
**Remaining:** template structure check (#84).

## R2-1 — Statistics, roadmap — In manuscript

**Asked:** statistical treatment and research roadmap.
**Done:** four-strata sampling description, independent annotation/adjudication, effort and provenance logs; "same accuracy" language fixed; historical timing honestly absent; roadmap paragraph added.
**Remaining:** owner read-through (#85).

## R2-2 — VLM comparison — In manuscript

**Asked:** fairness and cost framing of the VLM reference.
**Done:** VLM recast as an oracle-component-box diagnostic (both methods get annotated boxes); paired diff +0.033, CI [−0.009, +0.078] reported as nonsignificant, never as equivalence; cost multiples and superiority claims removed.
**Remaining:** nothing.

## R2-3 — SPICE title — Done

**Asked:** title overclaims simulation-ready SPICE output.
**Done:** retitled end-to-end (title, headers, abstract, conclusion, figure node) with the metric boundary stated: the metric measures component-pair connectivity, not pin correctness or simulation equivalence.
**Remaining:** PDF rebuild (T7).

## R2-4 — Crossover merges — Partial by design

**Asked:** effect of crossing wires on netlist correctness, including detector misses.
**Done:** causal two-edge C242 intervention reported with full tradeoff (TP/FP/FN 27/4/0 → 19/0/8, artifact `crossover-causal.json`); stated plainly that removing edges also removes true connections (no mitigation-gain claim) and that detector-miss effects were not measured.
**Remaining:** nothing achievable without new experiments — submitted as an honest partial.

## R2-5 — Ablations — Partial

**Asked:** evidence for each module's contribution ("severely insufficient").
**Done:** genuine base/full table; fixed-pixel base 0.820 vs scale-relative 0.816 reported as observed (not spun); full-pipeline ties at 0.890 presented as bounded negative evidence, never as proof that mechanisms are dispensable; missing full-occlusion and end-to-end scale ablations disclosed in paper and response.
**Remaining:** nothing further provable on existing data.

## R2-6 — Single-scalar limit — Closed

**Asked:** discussion-only point on evaluation limits.
**Done:** disclosure kept as-is; no change needed and none made.

## Reference numbers

Join 0.890 (418/37/66) on all 31; perfect-wire 0.88983 (420/40/64). Wire ledger: 0.9755 = 10°/18px config, 0.9726 = 12°/8px production. Otsu 0.789. VLM 0.923, 21/31 exact. Reach sweep macro 0.895–0.903. Numeric gate: 192/192 stored comparisons pass (SHAs in the amended plan).

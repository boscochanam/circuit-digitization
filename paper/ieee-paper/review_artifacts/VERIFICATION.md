# Verification at 8538797 — 8 September 2026

Verified `revision/access-2026-33821-astra-verify` at
`8538797d9a75392b02236a752e661e69e0175b57`, initially clean. This is a source and
stored-evidence audit, not submission approval. No detector, evaluation, simulation,
bootstrap, scientific test or PDF build was run. Existing PDF text was extracted
mechanically; no page-appearance judgment is claimed. No push or issue update.

A/B = `paper-access.tex` / `paper-build.tex`; R = `review_artifacts/RESPONSE_TO_REVIEWERS.md`;
I = `review_artifacts/REVIEW_CHANGES.md`; E = `docs/research/experiments`;
V = `/home/claw/circuit-digitization-validation-20260907`;
K = V/`context/01_review_materials`; S = V/`notes/scratch`.
All line anchors in this phase refer to the audited starting commit.

## Acceptance results

PASS means the stated check passed, not that every reviewer concern is empirically
answered. FAIL includes a literal acceptance condition that conflicts with the
amended plan; the conflict is recorded rather than silently waived.

| Item | Result | Evidence / remaining condition |
|---|---|---|
| T1 selective-port implementation, amended D1/P | PASS | `f249ae6` ports Introduction and `sec:limitations` to both sources; I maps all 19 zero-context fork hunks H01–H19. Retitle, conditional recast, ablation/drafter tables and response are present. No merge/rebase. |
| T1 literal #81 diff restriction | FAIL | #81 says “diff limited to paper-access.tex plus review artifacts.” T1 also changes B, required by the plan and paper instructions. D1 brief requests explicit acceptance of that exception. Do not close #81 under its unchanged wording. |
| T1 immutable evidence / newer figures | PASS | E tree at `36b9a8e` and `8538797` is identical: Git tree `e1f6c2c729c3775c651db7ce0cf1c25cb83d25c3`. Figure diff contains only authorized pipeline TikZ node text; every binary figure is preserved. T1 itself changes no figure. |
| T3 #83 / R1-2 | PASS | A:381–397 / B:357–373: three device groups, four columns, fourth metric-boundary row; exact switch pins 0/1 distinct-node condition and 0.001-ohm substitution. Code and stored population agree. |
| T4 IEEE-template source conversion / plan | PASS | Actual TXT/PDF located and hashed below. Exactly six concerns per reviewer, twelve verbatim concerns, twelve nonempty responses/actions; original/revised title and manuscript ID distinguished. R1-6 follows the specified no-citation action. |
| T4 literal #84 all-twelve manuscript references | FAIL | R1-6 is intentionally response-only (“No citation added; relevance rationale supplied here”), so it has no manuscript section reference. The plan explicitly prescribes this exception. D3 brief requests acceptance; do not manufacture a manuscript change. Final signer/PDF pages remain absent and are not source-template completion. |
| T5 amended P scientific-prose scope | PASS | A/B/R qualify matched annotated boxes, nonsignificance, unmeasured detector effects, incomplete ablations, corpus coverage and external values/models. No scientific closure inferred from the response fields. |
| T6 widened method-description fidelity | PASS | A:118–156 / B:94–132 agree with executable branches of assignment, graph and completion code; fallback alpha 0.35, fixed clamps, clamped reach, slot/dummy costs, and post-assignment guard correctly scoped. |
| T6 J specified headline ledger | PASS | Stored JSON loading verifies join/VLM/CI, base/full ablations, perfect wires, wire configuration/Otsu, reach range, synthetic L4 and C242 counts. Details in `verification_evidence/inspection.json`. |
| T6 J whole-submission numeric gate / strict #85 | FAIL | 191 of 192 recorded stored-number/display comparisons pass; Gaussian chart label 0.928 conflicts with 0.8452311293. Group aggregate F1 values and detector metrics do not yet have original aggregate JSON pointers here; qualified provenance below. |
| A/B abstract, scientific prose and table-cell synchronization | PASS | Abstract equal; Introduction through Data and Code Availability equal after the two named in-body figure-call substitutions. All seven tabular blocks equal; captions shared. |
| A/B complete figure dependencies / whole-submission P | FAIL | Three concept figures use PDFs in A and native TikZ in B. Pipeline PDF still says “SPICE Netlist / + simulation.” A/B source-prose equality cannot certify this graphic. Histogram internal population label also conflicts with corrected caption. |
| Source labels and citation resolution | PASS | Each source has 19 unique labels; no unresolved refs/cites, no uncited bibliography items; all 26 bibliography entries follow first-citation order. This does not certify bibliographic facts or rendered typography. |

Issue bodies were fetched with `gh issue view 81,83,84,85 --repo
boscochanam/circuit-digitization --json number,title,body,state,url` (four calls),
saved in `verification_evidence/issue-*.json`. Plain `gh issue view` first failed
on the deprecated Projects-classic GraphQL field; explicit JSON fields succeeded.
All four issues are OPEN. The issue-85 instruction to retain provisional 0.247
conflicts with the amended plan's default removal without auditable predictions;
the plan governs, and removal is correctly implemented.

## Spec identity: supplied file is not the amended version

V/`notes/IMPLEMENTATION_PLAN.md` hashes to
`7fd5e7a295f11fd7f6b9b42fecc4a35a435d1860d54bf801e70bdab6c9c23323`.
It still says D3 ACCEPT and does not contain the widened red-team P contract.
The actual amendment is `0f410c9:notes/IMPLEMENTATION_PLAN.md`, later removed by
`cefe77b` with the other working copies. Recovered verbatim as
`verification_evidence/amended-plan.md`, SHA256
`5288998c45e83e29552d994e238704f44602f607566664071cca19f9cf49d951`.
This audit applies its widened P/J requirements and D3 MODIFY, alongside the
supplied `PLAN_REDTEAM.md` (SHA256
`b29dcbab52ac68de57129c612ee6bd9e0edcde93f4e0a44e2287d700dd6c29ce`).
It does not alter the external notes or infer additional author decisions.

## T4 template and twelve-comment P checks

Actual template: K/`IEEE_Access_Response_to_Reviewers_TEMPLATE.txt`, SHA256
`efc079bd1c81a64a10aa4a751ee4da0dbc89b01a398f913adb2f224c86fb2051`.
Sibling actual PDF: SHA256
`e6a2986d1b5337a2a1e413cff3d3a44e690841e470e050eb91ae143a0cfea103`.
It specifies manuscript ID/title, editor salutation/closing and
Reviewer/Concern, Author response, Author action fields. The draft's intended-package
wording avoids falsely claiming upload. The unsigned signatory is a disclosed gap.
The response template is distinct from the **manuscript** class `ieeeaccess.cls`;
template presence does not establish an Access build environment.

K/`decision-email-raw.txt` SHA256
`5d9ac227a2ad93a703a955d0183cf2d5bd5d0c0138f81914c445109eee80e730`.
Compared all twelve full plain-text concerns after whitespace normalization only,
not the duplicated HTML portion; all twelve match. Both suggested titles match.

| Concern | P result | A / B anchor and substantive boundary |
|---|---|---|
| R1-1 | PASS | 318 / 294; descriptive drafter groups, direct/inferred provenance, no held-out-drafter experiment. |
| R1-2 | PASS | 385 / 361 `tab:capabilities`; metric/export/geometry separate. |
| R1-3 | PASS | 124–132 / 100–108; actual alpha/fallback, manual clamps, untested rescaling; bounded macro reach sweep. |
| R1-4 | PASS source; FAIL consumed graphic | 114 / 90; external values/models and real-scan simulation boundary; pipeline PDF retains old product claim. |
| R1-5 | PASS source; FAIL graphic population wording | 313 / 289; electrical-subset 3–14, median 7, 15 ≤5 / 12 ≥10; dense buses/multilayer untested. |
| R1-6 | PASS prescribed exception | R only; exact titles, polite relevance decline, no full-paper-review assertion, no citation promised. |
| R2-1 | PASS | 379 / 355; four sampling strata, independent annotation/adjudication, effort/provenance logs; explicitly future, historical timing absent. |
| R2-2 | PASS | 366–370 / 342–346; identical annotated component priors; +0.033 CI [−0.009,+0.078] without equivalence/cost superiority. |
| R2-3 | PASS source | A:41 / B:28 title; Abstract/Conclusion explicitly distinguish output from measured property. |
| R2-4 | PASS bounded response; empirical request unmeasured | 399 / 375; two edges, 27/4/0 → 19/0/8; no mitigation/prevalence/detector-causality inference. |
| R2-5 | PASS bounded response; coverage incomplete | 246 / 222 `tab:edge_ablation`; base 0.816 → 0.820, full-count ties, no masking/identity explanation; full occlusion and completion-wide scale removal untested. |
| R2-6 | PASS | 130 / 106; single scalar, large IC/small discrete example, retained completion scale dependence. |

T3 static evidence: `core/netlist.py:245` (`derive_pins_from_obb`, shorter OBB
edges and AABB fallback), `core/spice.py:203` (switch) and :274 (unsupported
models), `core/component_classes.py` prefix vocabulary,
`data/component_loader.py` merged model labels, and
`benchmark/join_eval_real_f1.py:38` component-pair projection.
T6 static evidence: `core/component_assignment.py:51–145`,
`core/join_graph.py:116–231`, `core/completion.py:94–235` and the deployed
`scale_completion` registry configuration. Read executable branches rather than
stale code comments; no assignment logic was reimplemented.

## Whole-submission claim sweep

Read all scientific paragraphs through Data and Code Availability, bibliography,
captions/table notes, all R sentences, three TikZ diagrams and extracted text of
seven consumed PDFs. Raw normalized line hits and full extracted PDF text are in
`inspection.json`; patterns are recorded so absence claims are reproducible.
Historical `manuscript_changes.diff` is provenance, not submission prose, and is
deliberately excluded from the live-claim gate.

- Zero hits in live TeX/R/TikZ for: “statistically indistinguishable,” “same
  accuracy,” “far more expensive,” “two to three orders,” “100–1000,”
  “structurally guaranteed,” “structurally valid by construction,” “largely
  solved,” “primary/dominant failure mode,” “without over-merging,” “same
  floating pins,” and `0.247`.
- The 47 broader hit lines were read in context. Equivalence, guarantees,
  endpoint-drop and upper-bound hits mostly explicitly deny those inferences.
  R's original title and quoted reviewer allegations are necessary provenance;
  “fairness” in the verbatim concern is not an author fairness claim. Related-work
  SPICE output describes cited systems, not our product. Completion diagram's
  same-component matching prohibition is local, not a guarantee against base shorts.
- **FAIL:** `figures/pipeline_overview.pdf`, consumed at A:75, still extracts
  “SPICE / Netlist,” “Pin discovery,” “+ simulation.” TikZ:22 is corrected. This
  contradicts the caption and prevents a whole-submission P PASS.
- **FAIL:** `figures/complexity_histogram.pdf` still labels the population
  “SPICE-active components per image,” while A:313 / B:289 defines the evaluated
  electrical subset (including ICs). Do not conflate `SPICE_ACTIVE_TYPES`, export
  primitives and evaluator membership. Extracted title begins “e 31-image…”;
  clipping is suspected but cannot be certified from extraction alone.
- Editorial exceptions to assess in phase 2: B:73's generalization about how
  prior systems represent wires; B:85 “caps per-pin degree”; B:138 “mean F1 over
  error levels” versus per-level table columns; completion's “min-cost” caption
  shorthand versus post-assignment guarded output. These are not silently endorsed.

## J evidence coverage and remaining exceptions

`verification_evidence/inspect_sources.py` loads stored JSON only, formats values
to manuscript precision, counts existing metadata/rows, and sums stored integer
counts. It does not recompute F1, rescore predictions or bootstrap intervals.
`inspection.json` has exact path/key/stored/display/PASS-or-FAIL for 192 comparisons
and SHA256 of every loaded numeric artifact. The integer simulation percentages
use nearest integer with ties to even (12.5% → 12%); rounding convention is an
editorial item, not an altered simulation score.

Verified inventories: 31 images, electrical subset range 3–14/median 7, counts
15/12 at ≤5/≥10; drafter group sizes 7/5/5/4 and stored TP/FP/FN sums
56/6/2, 85/14/15, 37/1/0, 21/0/4; 134 wire images, median stored F1 1.000,
117 with stored F1 ≥0.90. Exact VLM stored F1==1 rows: 21/31.

Recovered additional JSON without rerunning: original checkout
`/home/claw/circuit-digitization/output/benchmark_experiments/expanded_full_ranking/`
has `best_candidate_v1`, `v2`, `v3`, `adaptive_gaussian_skeleton` and
`triangle_skeleton` `summary.json` files. Stored wire-table alternatives agree.
The Gaussian chart's 0.928 fails against stored `global_f1=0.8452311293153891`.
**Correction to I's inherited ledger:** its proposed Triangle 0.795 is not
established by these recovered artifacts; `triangle_skeleton.global_f1` is
0.7582635186595582, agreeing with the chart. Do not replace Triangle with 0.795
without identifying the intended configuration/generation.

The per-drafter aggregate micro/macro F1 cells match
E/`revision_evidence/drafter_map.md:116–120`; integer counts and group sizes trace
to JSON as above, but no original group-score JSON was found in E, V/notes or the
original checkout's output tree. The detector 88.5%/70.7% values are accepted plan
inputs, not verified afresh from an original detector-metric JSON here. Pipeline
example counts/F1 require their exact generator configuration and rendered panels;
neither a different wire run nor rounded net-GT score certifies those image assets.
These qualifications prevent “every number independently verified” overstatement.

## Source immutability and phase-1 disposition

Current A SHA256: `3af1831456fba56f1935fc322e7407faf93b38d238297a5c93ddba70ccbd58b7`.
Current B SHA256: `3007bfa0c424913ac26dfb0530ca0373ff4893d3b808fa18c1e01b90f1547c70`.
Current R SHA256: `d17bb1d1d0d5eae237fbfa982927e6a0dccc7d610b31734e4256a9cdb7e91cf4`.
Frontmatter and Acknowledgment-through-end are byte-identical within each source
from `cefe77b` through `8538797`; this checks noninterference, not author approval.
Historical fork diff SHA256 remains
`ad5b4b5d230a61294330fb69f654d01a7c781cd7e85a8cc5b460ccd6f955a30a`.

Phase 1 records the failures and does not close any issue. Phase 2's inventories
and decision briefs will distinguish genuine human facts, team choices and
dependent technical work. Quota percentage cannot be measured: no authoritative
session-attributed start/end quota counters or denominator are exposed; context
capacity and elapsed time are not quota consumption.

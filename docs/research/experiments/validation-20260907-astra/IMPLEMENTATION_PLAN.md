# Implementation plan

## Contract and notation

Amended scope: this plan and the component-first pin-assignment paragraph in A/B are updated now. Only that prose correction is complete; all other implementation/build actions below remain future work. No push, email, submission, PDF build, code change, scientific/test rerun, or author/funding/bio edit is authorized here. Base `36b9a8e`; fork `10c1b92`, parent `9bbe9e9`. Settled results remain inputs.

**M** = `/home/claw/circuit-digitization-merge-20260907`; **V** = `/home/claw/circuit-digitization-validation-20260907`; **B** = `M/paper/ieee-paper/paper-build.tex`; **A** = `M/paper/ieee-paper/paper-access.tex`; **E** = `M/docs/research/experiments`; **C** = `V/notes/REVIEWER_CLOSEOUT.md`; **T** = `V/notes/TEAM_REPORT_20260907.md`; **K** = `V/context/01_review_materials`; **R** = proposed `M/paper/ieee-paper/review_artifacts/RESPONSE_TO_REVIEWERS.md`; **I** = proposed sibling `REVIEW_CHANGES.md`. Citations expand through these exact paths. “Both” means A and B at the quoted anchor; B citations identify present text, not future insertion lines.

## D1–D4 verdicts

| Decision | Verdict | Evidence and action |
|---|---|---|
| D1 merge direction | MODIFY | Selectively port fork prose/review scaffolding onto the revision; do not rebase the shared fork. `9bbe9e9..10c1b92` changes A and four review artifacts, not B. Fork A’s “Left:~a four-transistor analog cell” caption differs from newer B:61; preserve revision experiments/figures and explicitly synchronize both sources. |
| D2 retitle | ACCEPT | Adopt “Structural Circuit Netlists,” implemented in `10c1b92:paper/ieee-paper/paper-access.tex`, anchor `\title{From Hand-Drawn Schematics to Structural Circuit Netlists`. Define structural as topological pin connectivity; this addresses C:15 without reopening synonyms. |
| D3 response base | ACCEPT | Use fork R (`10c1b92`) as scaffolding, correcting device/autonomous claims. Convert into concern/response/action fields required by K/IEEE_Access_Response_to_Reviewers_TEMPLATE.txt:17. This follows T:20. |
| D4 PDF ownership | MODIFY | Retain one accountable builder (T:21). Specify clean IEEEtran → clean IEEE Access → highlighted IEEE Access → package checks. T supplies no layout order. Enumerated checks replace visual inspection as the sole gate; editorial judgment remains OPEN. |

## Mechanical verification contract

**P — prose:** Read each changed paragraph, adjacent paragraphs, and corresponding R response. Normalize whitespace/TeX escapes for literal checks. Record required clauses and forbidden-phrase search results in I. Pass means specified clauses present, prohibited claims absent, and edits synchronized across A/B/R. Additional editorial judgments go to OPEN.

**J — numbers:** Load existing JSON with `json.load`; compare stored fields to manuscript values rounded to displayed precision, counts by equality. Record path/key/display/PASS or FAIL in I. Do not execute evaluation, detector, simulation, bootstrap, or test entry points; do not recompute settled scores. Missing pointers go to OPEN.

### Authorized method-description correction — COMPLETE; T6 prose subtask

Both, anchor “\textbf{Component-first pin assignment:}” (B:108; A:132): replaced AABB center-side routing with endpoint-to-OBB distance (zero inside, nearest edge outside), AABB fallback when four OBB vertices are unavailable, nearest eligible component within the existing radius based on the AABB diagonal, then nearest-pin Euclidean routing. Implementation evidence: M/wire_detection/core/component_assignment.py:51, :79, :103 and :129. No implementation or parameter changes.

P completed: corrected paragraphs match exactly in A/B; “for horizontal components” and “else bottom pin” are absent from that paragraph; OBB/AABB fallback, AABB-diagonal radius and “smallest Euclidean distance” clauses are present. Preserve this correction during T1 porting; T6 must retain it during the later prose pass. No build or rerun was performed.

T6 ledger:

- E/join_micro_n31.json:1370, `micro.scale_completion`: 0.8903, TP/FP/FN 418/37/66; :1412 `macro.scale_completion.f1` must be labeled separately.
- E/bootstrap_ci_n31.json:2, `join/scale_completion.micro`: CI [0.855,0.924]; :74 `VLM_minus_ours_micro`: +0.033, CI [−0.009,+0.078]. E/vlm_clean_rerun_n31.json:2, `n`/`micro.F1`: 31/0.923. Count stored `rows` with `F1 == 1` only to cross-check accepted 21/31 (T:62), without rescoring predictions.
- E/revision_evidence/edge_ablation_results.json:2, `full_pipeline_scale_completion`: compare each configuration’s `micro` fields to baseline. Base fixed-pixel entry at :1741, `scale_rel_off_fixedpx`: preserve 0.816 versus 0.820 and full ties 0.890 (C:17); do not invent a rounded delta.
- E/join_reach_sweep_n31.json:12, `db_scale_r3.0` through `db_scale_r5.0`, `f1`: macro 0.895–0.903 (T:63), not image-rescaling evidence.
- E/drafter_map_n31.json:2: count stored drafter_1/2/10/12 assignments against 7/5/5/4 (B:300). Preserve direct/inferred provenance (B:290); no re-identification.
- E/synthetic_leaderboard.json:3/:111: select scale_completion/production, `by_severity[4]`; display L4 0.95/0.36.
- Perfect-wire micro 0.8898 is accepted (T:59); its JSON pointer is OPEN. E/detection_ceiling_n31.json:2 contains macro values, not micro evidence.
- Wire ledger: 0.9755 = dedup 10°/18px; 0.9726 = 12°/8px; Otsu 0.789 (T:60–61). JSON pointers OPEN. Label both `\label{tab:wire_benchmark}` and `\label{fig:wire_benchmark}` configurations explicitly; do not change production parameters or infer missing precision/recall.

## Twelve-comment implementation

### R1-1 — descriptive drafter groups; T5/T6

Both, “To probe cross-style generalization within the single corpus” (B:290): replace purpose/conclusion with “These groups describe within-corpus variation, not evidence of unseen-drafter transfer.” Preserve provenance and cells; caption adds “Groups with at least four images; overall includes all benchmark images.”

P: quoted sentences present; “supporting cross-drafter generalization” absent. J: drafter ledger. R concern from K/decision-email-raw.txt:122, “Single dataset source and an extremely small manually verified benchmark”; response explicitly says no held-out-drafter experiment.

### R1-2 — capability table; T3

Both, replace “The pipeline emits SPICE-active netlist pins only” (B:350). Table caption: “Connectivity evaluation, generic pin construction, and illustrative export are distinct capabilities.” Columns: device group/evaluated scope/pin construction/export limitation. Rows: benchmark R/C/L/D/Q/voltage and IC; switches; transformers/thyristors/optocouplers and other complex devices.

First row: component-pair evaluation, not universal validated pin templates (E/revision_evidence/crossover-bridge-check.md:20). IC lacks a supported export model (M/wire_detection/core/spice.py:274). Switches can export as a 0.001-ohm resistor with two distinct nodes (spice.py:203). Complex-device-specific connectivity is unvalidated; generic guesses may exist and export may be skipped. Transformer geometry exists (M/wire_detection/core/netlist.py:264); detector vocabulary is merged, not individual complex classes (M/wire_detection/data/component_loader.py:32).

P: three rows/four columns present; explicitly state that listing a group is not evidence of separately detected model classes; blanket “their pin relationships are not extracted” and exclusion from all emission absent. Compare implementation clauses to cited code, not `SPICE_ACTIVE_TYPES` as a proxy for evaluated population. R anchor at fork SHA: “Limited support for complex component types”; correct its blanket exclusion too.

### R1-3 — threshold sensitivity; T6

Both, “The tolerances” (B:106), “A reach sweep shows a broad F1 plateau” (B:214), `\label{tab:edge_ablation}`. State fixed/manual pin/join/T multipliers 0.62/0.30/0.20 and clamps 24–60/11–28/8–20 px (E/revision_evidence/edge_ablation_results.json:5; M/wire_detection/core/join_graph.py:120). Add “Extreme-size performance was not evaluated by controlled image rescaling.” Describe reach sweep as bounded within-benchmark sensitivity.

P: sentence present; “so a single parameter setting works across circuits of varying size” and “robust rather than tuned to a spike” absent. J: reach/ablation ledger. R anchor: “Fixed, manually configured scale-relative thresholds”; disclose completion retains scale dependence.

### R1-4 — scope; T2

Both, “Automated digitization” (B:42), “We address these challenges with a complete deterministic pipeline” (B:73), “The output is a netlist mapping” (B:90). Introduction/method must say: “We evaluate topological recovery with illustrative SPICE export; component values and device models require external specification, and simulation equivalence on real scans is not validated.” Remove “and, as we do,” before the related-work LTspice validation claim (B:77); retain separately scoped synthetic simulation (B:142).

**Abstract before:** “structural SPICE-format netlist”; “statistically indistinguishable … far more expensive and without structural guarantees” (B:42).

**Abstract after:** “We present a deterministic pipeline for structural circuit-netlist recovery using an occlusion-first wire extractor, an endpoint graph, and degree-budget completion. Structural netlists represent topological pin connectivity; illustrative SPICE export requires externally specified values and device models. Simulation equivalence on real scans is not validated. On 31 human-verified CGHD-1152 images, the join achieves component-pair micro-F1 0.890 with annotated component boxes and detected wires. Under the same component priors, the VLM reaches 0.923; the paired difference has a 95% confidence interval of [−0.009,+0.078], which does not establish equivalence. These results provide within-corpus evidence, not autonomous reconstruction or unseen-style generalization.”

P/J: exact scope clauses and ledger. R anchor: “No component-value recognition or complete simulatable SPICE output.”

### R1-5 — complexity coverage; T5

Both, “The set is bimodal rather than” (B:285): retain descriptive counts, remove rebuttal framing, append “Component-count breadth does not validate dense buses or multilayer crossings; performance on these cases remains untested.” Preserve histogram asset.

P: sentence beside histogram. J: cross-check caption counts using stored per-image component counts in E/join_micro_n31.json; if absent, use existing `ground_truth/real_nets_verified.json` component lists without detection. R anchor: “No dedicated dense-bus or multi-layer-crossing verification.”

### R1-6 — reference relevance; T4

R, “Suggested memristive-circuit references” (`10c1b92`): retain polite decline, quote both suggested titles verbatim from K/decision-email-raw.txt:148, explain their proposed application/simulation context does not strengthen this connectivity-extraction comparison. Do not imply full-paper review. Action: “No citation added; relevance rationale supplied.”

P: both titles match letter; concern/response/action nonempty; no promised citation/escalation. No manuscript edit. Optional-citation basis: K/decision-email-raw.txt:40.

### R2-1 — uncertainty and roadmap; T5

Both, “Annotation was performed by a single human annotator” (B:350): retain missing timing logs. Add future protocol with four strata: component count, drafter, crossing/bus structure, capture conditions; independent annotation/adjudication; per-image effort and provenance logs. Include “This is a proposed expansion protocol, not completed annotation.”

P: four strata, both stages, logs, and future sentence present; no invented historical hours/sample target. J: existing CIs only. R anchor: “Statistical reliability, annotation cost, and expansion roadmap”; apply shared nonsignificance correction.

### R2-2 — conditional VLM evidence; T5

Both, “To quantify the separation argued” (B:340), “The VLM thus edges” (B:342), “accuracy matches the VLM's” (B:71). Remove autonomous numeric paragraph from submission unless OPEN provenance is recovered; keep internal status in I. Remove cost/token multiples, free-form-output criticism, detector-dominance/distribution-shift inference. Narrow caption “dominant failure mode in end-to-end digitization” (B:52) and discussion “self-loop guard prevents the catastrophic short-circuit failures” (B:348) to local safeguards without global guarantees.

**VLM before:** “an explicit model reaches the same accuracy” (B:342).

**VLM after:** “Both methods receive the same annotated component boxes; the geometric method uses detected wires. This is a conditional connectivity comparison, not an autonomous end-to-end comparison. The VLM reaches micro-F1 0.923 versus 0.890 for the geometric join and is exact on 21/31 images. The paired difference is +0.033, with 95% CI [−0.009,+0.078]. Inclusion of zero does not establish equivalence. These results do not establish comparative cost superiority or a global guarantee against incorrect merges. Autonomous performance requires separately auditable evaluation.”

P: replacement present; “same accuracy,” “statistically indistinguishable,” “two to three orders,” “structurally guaranteed,” “far more expensive” absent in A/B/R. J: VLM ledger. R anchor: “VLM comparison has an oracle advantage”; clarify both receive annotations rather than conceding asymmetric inputs.

### R2-3 — title/conclusion; T2

Both, `\title{From Hand-Drawn Schematics to SPICE Netlists` (B:28; A:41), `\markboth` (B:37; A:55).

**Title before → after:** “From Hand-Drawn Schematics to SPICE Netlists: A Deterministic Pipeline with Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark” → replace only “SPICE Netlists” with “Structural Circuit Netlists.” Apply to both running-head arguments and R title.

**Conclusion before:** “We present a complete deterministic pipeline”; “does not raise micro-F1 at all” (B:354).

**Conclusion after:** “We present structural circuit-netlist recovery using an occlusion-first wire extractor and endpoint-graph joining with degree-budget completion. On the 31-image within-corpus benchmark with annotated component boxes, connectivity micro-F1 is 0.8903; perfect-wire input gives 0.8898. These scores round alike but do not establish an autonomous detection bottleneck. Synthetic L4 connectivity F1 is 0.95 versus 0.36 for the radius baseline. The VLM comparison is conditional and does not establish equivalence or cost superiority. Export remains illustrative: values and device models require external specification, and real-scan simulation equivalence is unvalidated. Broader styles, dense buses, and mixed-scale schematics require future evaluation.”

Also replace “unchanged”/“essentially zero” interpretation at B:280 with this bounded observation. P/J; perfect-wire insertion awaits JSON pointer. R anchor: “SPICE-netlist title and abstract claim.”

### R2-4 — crossover tradeoff; T5/T6

Both, “We quantified this exposure with a causal ablation” (B:350): replace single-edge/rare/safe-mitigation interpretation with audit’s two-edge C242 intervention and TP/FP/FN 27/4/0 → 19/0/8 (V/notes/scratch/crossover-causal.json:2, `C242_D1_P1_jpg.baseline` and `C242_D1_P1_jpg.no_crossing_type2`). Preserve GT-box context; add “Removing these edges also removes true connections; this is not a demonstrated mitigation gain. Detector-miss effects were not measured.” No prevalence extrapolation.

P: sentences/qualification present; remove “single edge type-2 union is the sole cause” and “real but rare.” J completed against `/home/claw/circuit-digitization-validation-20260907/notes/scratch/crossover-causal.json`: compare `tp`, `len(fp)`, and `len(fn)` in the two C242 records to (27,4,0) and (19,0,8). `C242_D1_P1_jpg.removed_edges` (:63) contains exactly [[459.0,369.0],[456.0,364.0]] and [[460.0,357.0],[456.0,364.0]]. This closes the crossover provenance OPEN item. Pushback #2 and its fallback rerun recommendation are withdrawn; no rerun. The manuscript R2-4 edit remains future work. R anchor: “Crossover recall and impact on netlist correctness.”

### R2-5 — ablation boundary; T6

Both, “Leave-one-out ablation” (B:217), “Fixed-pixel tolerances (scale-rel. off)” (B:231), “The edge-type ablation” (B:236). Rename row “Fixed-pixel base tolerances; completion unchanged.” Report 0.816 → 0.820 and equal full counts; delete “same dropped connections,” “reconnects the same floating pins,” positive scaling benefit. Add “Equal aggregate counts do not establish identical recovered connections. Full occlusion removal and removal of scale dependence throughout completion were not tested.” Delete activation explanations unless existing JSON fields are identified.

P/J. T7 converts table to `table*` sized within text width, retaining every data column. R anchor: “Insufficient ablation study.”

### R2-6 — single scalar; T6

Both, retain “Because $s$ is a single scalar per image, intra-image size variance is not modeled” and mixed IC/discrete example (B:106); apply R1-3 disclosure, no dispersion table. P: sentence/example survive; no mixed-size robustness claim. R anchor: “Mixed component sizes within one schematic”; cite retained discussion, not a new experiment (C:18).

## Package checklist — D4 order

1. **Response:** T4 uses IEEE template; twelve complete concerns copied from K/decision-email-raw.txt:122/:182, only wrapping normalized. Exactly six concerns per reviewer and twelve nonempty responses/actions. Fill original ID/title/signer, distinguish revised title. I maps actions to quoted final-source anchors and PDF pages. Replace fork diff with final-source diff against confirmed reviewed baseline; preserve fork provenance separately.
2. **Clean IEEEtran:** T7 builds B in fresh output directory with `latexmk -pdf -halt-on-error -interaction=nonstopmode`. Exit zero; zero missing files, undefined references/citations, overfull boxes. Save source SHA/logs. No scientific scripts.
3. **Clean IEEE Access:** same checks for A using actual template files. Compare normalized scientific paragraphs/tables between sources: extract abstract and Introduction-through-Data-and-Code-Availability text, strip layout commands/comments, collapse whitespace, and require equality; list any template-only exceptions in I with both exact strings. Compare table cell strings independently, preserving numeric text. Freeze sources.
4. **Highlighted Access:** generate against confirmed reviewed source, including grammar/captions/tables. Map every source-diff hunk to highlighted page/region; zero unmapped hunks. Record deleted-only hunks in the response change index when they have no surviving text to highlight; retain a marked deletion in the diff artifact. Maintain separate clean PDF. Baseline is OPEN.
5. **Package:** use `pdfinfo` page count; checklist has exactly one row per page per PDF. Check extracted text boxes inside page bounds, no intersecting table columns, every final-source caption text represented in extracted PDF text (normalize whitespace/TeX escapes; use I to map source labels to captions). Record missing-glyph warnings (must be zero). Compare clean/highlighted final text after removing deletion markup. Mathematical typography/reference-format judgments go to OPEN (K/IEEE_Access_Resubmission_Checklist.txt:32/:48). Include sources/assets, clean/highlighted PDFs, response PDF, I, logs and SHA256 manifest (checklist :58/:69/:81/:87). No upload here.
6. **Authors:** T8 written approvals tied to final source SHA: byline/order, affiliations, ORCIDs, bios/photos, funding, consent. Compare approved fields literally across A/B/R. If byline differs from reviewed version, require completed change form and recorded permission (K/decision-email-raw.txt:81).

## OPEN — exact missing inputs

Seven OPEN items remain: six required and one optional (autonomous-result retention). The crossover provenance item is closed by the JSON cross-check in R2-4. These quoted requests specify inputs, not inferred answers. Resolve with artifact path/SHA/field; mandatory unresolved inputs block package readiness.

- “Name accepting owners for T3, T4, T5, T6 and the single T7 builder.” T:50–54 says “Assignee TBD.” Record Bosco’s D2 acceptance (T:49).
- “Supply existing JSON paths and keys for perfect-wire micro 0.8898 and wire configuration/Otsu results 0.9755/0.9726/0.789.” Provenance gap only; facts remain accepted (T:59–61).
- “If retaining autonomous numbers, supply detected-box predictions, component matches and result JSON.” C:14. Default removal makes this optional.
- “Identify the exact reviewed manuscript source/PDF pair for highlighting by SHA256.” K and V/context/00_original_paper candidates are not interchangeable; fork parent is not automatically reviewed baseline.
- “Supply actual IEEE Access template support files/environment and name the author approving rendered pages.” Compilation remains unverified (C:24).
- “Supply each author’s approval of byline/order, affiliations, ORCIDs, bios/photos, funding and final submission consent; provide byline-change form if applicable.” T:55; K/decision-email-raw.txt:81. Filled fields are not approval.
- “Provide named editorial sign-off for reference relevance, grammar, mathematical typography and page appearance.” Tie approval to final PDF SHA; mechanical checks cannot establish these judgments.

## Ordered execution and dependencies

1. **T1 Bosco + Pranavesh:** record D1/D2 decisions/SHAs, selectively port fork scaffolding, preserve experiment/figure hashes against `36b9a8e`, synchronize A/B. No rebase/push required.
2. **T2 Bosco; designated T3/T5/T6:** implement remaining anchored items; preserve the completed T6 method-description correction above. T3/T5/T6 depend on T1; T2 on D2. T8 author inputs proceed independently.
3. **Designated T4:** draft after D3; finalize actions after step 2. T6 runs P/J ledger; missing mandatory provenance blocks freeze.
4. **Single T7:** after T1–T6 and required T8 inputs, execute D4 order. Source corrections invalidate affected downstream PDFs/diff mappings.
5. **Bosco:** compare manifest with author approvals/OPEN resolutions. Ready requires artifacts and mechanical PASS records; push/submission remain separate.

## Ready-to-execute summary

- Preserve corrected assignment prose and revision evidence; selectively port fork prose.
- Lock Structural Circuit Netlists in both sources/heads.
- Complete twelve concern/response/action sets.
- Remove unsupported autonomy, equivalence and validity claims.
- Use verified crossover JSON; recover remaining JSON provenance without reruns.
- Resolve owners, reviewed baseline, template and author inputs.
- Freeze synchronized sources after P/J checks.
- Build IEEEtran → IEEE Access → highlighted IEEE Access.
- Package hashes/logs/sign-offs; no push or submission here.

## Addendum 2026-09-07 (operator verification, not Astra output)

- `git merge-base origin/main HEAD` (merge worktree) is EMPTY: the fork line (child of origin/main `9bbe9e9`) and the revision line (child of local duplicated-history `33f5e3d` family) share no common commit. A git merge/rebase across them requires `--allow-unrelated-histories` and would produce a whole-tree conflict storm. T1 MUST be a manual selective port, never a merge/rebase. D1's "selective port" verdict stands; its reasoning is now stronger.
- Read-only `git apply --check` of the fork's paper-access.tex diff onto this worktree FAILS (first failure at the title/author block region). Expect hand-resolved conflicts everywhere both lines rewrote (abstract, VLM section, conclusion). Budget T1 as prose surgery, not patch application.
- Component-first prose correction (`823aef6`, both sources) independently verified against `wire_detection/core/component_assignment.py` (obb_distance zero-inside/nearest-edge, AABB fallback, max(tau_pin, 0.5*diag) radius) and committed on the isolated merge branch. Nothing pushed.

# Plan red-team — 8 September 2026

**Pushback: do not execute this plan unchanged.** Twelve headings exist, but semantic response closure, method fidelity, figure coverage and freeze dependencies remain incomplete. Narrowing claims is defensible; it does not guarantee that reviewers will accept missing experiments.

Read-only audit; no experiments, tests, builds, pushes, emails or manuscript edits. Only this report was written. Existing JSONs were loaded, not rescored. Evidence is the current merge checkout `212e872`, fork `10c1b92`, and audit branch `3bc3b1abc61d86457f0b567c08fa678800046ddc`.

**Paths:** M = `/home/claw/circuit-digitization-merge-20260907`; V = `/home/claw/circuit-digitization-validation-20260907`; B/A = M/`paper/ieee-paper/paper-{build,access}.tex`; S = V/`notes/scratch`; P = V/`notes/IMPLEMENTATION_PLAN.md`; K = V/`context/01_review_materials`; R = fork `paper/ieee-paper/review_artifacts/RESPONSE_TO_REVIEWERS.md`. B anchors also occur in A unless stated otherwise.

The requested branch has no `notes/IMPLEMENTATION_PLAN.md`. Its tracked copy is `docs/research/experiments/validation-20260907-astra/IMPLEMENTATION_PLAN.md`, byte-identical to P: SHA256 `7fd5e7a295f11fd7f6b9b42fecc4a35a435d1860d54bf801e70bdab6c9c23323`. This audit uses that verified content, including the operator addendum.

## Findings ranked by acceptance risk

| Rank | Risk | Finding | File/anchor evidence | Affected work |
|---|---|---|---|---|
| 1 | Critical | Retitle can substitute an unvalidated pin-correctness claim for the SPICE claim | P D2/R1-4; B:142; `wire_detection/benchmark/join_eval_real_f1.py:38–55`; S/`fresh-join-ablation.json`, `shorted_two_pin_components` | D2, T2/T3/T5 |
| 2 | Critical | Banned conclusions survive unassigned paragraphs and figure contents | B:67,77,114,124,132,212,272,334,348; A:75; `figures/pipeline_overview_tikz.tex:22`; P P-contract | T1/T2/T5/T7 |
| 3 | High | “Complete” method correction leaves a contradictory edge rule and missing requested alpha | B:100,108,124; `core/join_graph.py:176–209`; P R1-3 | T6; R1-3/R2-5 |
| 4 | High | R2-4 still does not measure the requested crossover-recognition effect | K/`decision-email-raw.txt:203–209`; P R2-4; S/`crossover-causal.json` | T4/T5/T6 |
| 5 | High | Ablation response risks replacing evidence with an unproved completion explanation | P R2-5; R reviewer 2 §5; B:217–236 | D3, T4/T6 |
| 6 | High | No figure-dependency closure; preserving hashes conflicts with correcting claims | P T1/package §3; A:75 versus B:51; S/`source-checks.txt`, BODY DIFF | T1/T6/T7 |
| 7 | High | Response prose outside targeted anchors can contradict final manuscript | R opening, reviewer 1 §5, reviewer 2 §5; P D3/P-contract | D3, T4/T6 |
| 8 | High | Final response, author approval and PDF steps contain unresolved dependency cycles | P ordered execution §§3–4; package §§1,3,6 | D4, T4/T7/T8 |
| 9 | Medium–high | All mandatory numeric provenance OPENs are already locally resolvable | S/`fresh-join-ablation.json:103`; `historical-wire-config.json:2215`; `wire-rerun.json:79,4351` | T6, OPEN |
| 10 | Medium | OPEN bundles mix genuine human decisions with unassigned mechanical work | P OPEN; A:35–36; K checklist “grammar”, “math”, “references” | T6/T7/T8 |

### 1. Structural output is not validated pin topology

P defines structural netlists as “topological pin connectivity,” then presents 0.890 as its success measure. The evaluator explicitly discards `_pin` and scores unordered component pairs. Incorrect terminal identities and some different net partitions can therefore escape this metric. The existing audit records eight same-node two-pin assignments across four images, including perfect component-pair scoring coexisting with a shorted component (V/`notes/VALIDATION_NOTES.md`, F1). This is a more fundamental boundary than absent OCR.

**Required disposition:** distinguish the representation produced from the property evaluated, explicitly stating that component-pair F1 does not certify pin assignment, exact net partition, absence of shorts or simulation equivalence. P's capability table should carry that boundary. D2's title can survive; its proposed definition alone cannot close R2-3.

### 2. The banned-claims gate is too narrow

P searches particular phrases and changed/adjacent paragraphs. Counterexamples outside its explicit replacements:

- B:67 calls joining the “primary failure mode in end-to-end digitization”; B:77 calls recognition “largely solved.” Both contradict the conditional framing.
- B:114 promises connectivity “without over-merging”; B:124/132 says the guard prevents shorts. The guard only rejects additional completion merges; it cannot undo base unions (`core/completion.py:215–235`). B:334 infers fragmentation rather than shorts from high precision, which does not establish that distinction.
- B:212 calls the answer key independent of every method and says synthetic validation rules out residual bootstrap bias; B:272 similarly denies a bootstrap artifact. Human correction and independent synthetic evidence mitigate, but cannot exclude, bias in the real labels.
- B:348 turns 97.6% wire F1 into a roughly 2% endpoint-drop rate. F1 is neither endpoint recall nor a causal measurement of simulation failures.
- B:278 calls a finite baseline sweep an “upper bound” and generalizes that no prior system provides a suitable module. These exceed the tested implementations/configurations.
- The pipeline diagram ends with “SPICE Netlist” and “+ simulation” (`pipeline_overview_tikz.tex:22`). Fixing the title and caption leaves the visual product claim.

**Required disposition:** a whole-submission semantic claim audit, including diagram labels, captions, table notes, response opening and imported assets. A global search for “fair” must be context-aware: P rejects VLM fairness/superiority claims, not every legitimate controlled-baseline description.

### 3. Method fidelity is not finished

B:100 adds an edge for *each* nearby endpoint/pin with weight `d(1−alpha cos(theta))`. Actual `join_graph.py:176–209` selects one component/pin; only when no component is assigned does it search pins using `d(1−0.35 max(0,cos))`. Union-find does not optimize stored graph weights. P's completed B:108 paragraph describes the primary branch but leaves this preceding contradiction intact. Reviewer 1 explicitly names alpha (letter:133–137), yet P adds three tolerance multipliers and no alpha value or activation condition.

B:124 also writes an at-most-one-edge, nonnegative-cost minimization that admits the empty solution; the implementation uses mandatory row assignments including dummy opt-out costs and target slots (`completion.py:200–213`). This needs an accurate mathematical description, not merely typography approval. Resolve from existing code during T6, without changing algorithms or rerunning them.

### 4. Crossover response remains a deliberate partial answer

The recovered two-edge intervention establishes a joining failure near annotated crossovers and its TP/FP/FN tradeoff. It does **not** analyze which missed/misclassified detector crossovers caused autonomous false merges, the particular concern in R2-4. P acknowledges this honestly but still risks treating paragraph completion as substantive closure.

**Required disposition:** R must explicitly say the detector-error effect remains unmeasured and explain why the conditioned failure analysis is the evidence supplied. Do not call R2-4 CLOSED or imply that 70.7% recall caused the observed four false pairs. No new run is authorized here; reviewer dissatisfaction remains a scientific risk, not an administrative OPEN awaiting a person.

### 5. Ablation is defensible only as bounded negative evidence

R2-5 has no detailed prescribed experiment, so the existing base/full table is a real response. But identical full counts do not prove completion “masks these differences,” as R reviewer 2 §5 says; several base interventions also tie. P prohibits identical-connection explanations but does not explicitly remove this scaffold inference. Nor does it establish occlusion's claimed quantitative contribution: B:173 says removing it creates “hundreds” of false detections, while P admits full occlusion removal was not tested.

**Required disposition:** map each claimed module benefit to stored evidence or narrow it. State the absence of full occlusion and end-to-end scale ablations in the response as well as the paper. Retain observed completion/base differences; do not infer activation or recovered-pair identity from aggregate ties. This improves the response, but the reviewer's “severely insufficient” judgment may still stand.

### 6. Figure synchronization and preservation conflict

A includes `figures/pipeline_overview.pdf`, `endpoint_graph.pdf` and `completion.pdf`; B inputs TikZ sources. Root/paper instructions asserting shared native inputs are stale. P's scientific-text equality check strips layout commands and can pass while different figure content is shipped. Caption extraction cannot validate internal labels. T1's blanket experiment/figure hash preservation would also forbid updating the misleading pipeline diagram identified above.

**Required disposition:** classify immutable evidence versus presentation assets needing correction; record each figure's consumed source/asset, generator/config provenance and corresponding A/B dependency. Highlight changed figure content, including binary-only changes. T6 must settle this before T7. Frozen data does not imply frozen explanatory graphics.

### 7. D3 imports scientific debt

Fork R's opening claims added “cross-style evidence.” Reviewer 1 §5 says “3–14 supported components, median 7”; P's R1-5 only directs histogram-count checking and adds a limitation. A nonempty action field is not verification of this extra range or of the response's component-population terminology. The same section carries the crossover summary, and reviewer 2 §5 retains the inference in finding 5.

**Required disposition:** validate every R sentence against final source and evidence, including untargeted introductions and numerical clauses. All twelve concern texts must be reproduced, not the fork's paraphrased headings; P correctly requires that conversion. D3 becomes MODIFY: retain organization, regenerate factual responses from the final evidence ledger. Merely correcting device/autonomous passages is insufficient.

### 8. Freeze sequence needs explicit back-edges

P finalizes T4 before T7, but requires I to contain final PDF pages. It freezes sources after clean Access, then obtains author approvals in package step 6, although T7 already depends on required T8 inputs. The distinction between factual input approval and approval of final artifacts is missing. T2 depends only on D2 in the dependency text, so a later T1 port could overwrite its edits despite the numbered order suggesting otherwise.

**Required disposition:** baseline/owners/template discovery first; T1 before all overlapping body edits; author facts before source freeze; T2/T3/T5/T6 before final scientific response; clean build before response page references; response rendering and highlighted-copy verification before package freeze; final consent tied to that package. Changes to approved text trigger renewed downstream checks. One builder survives, but D4 needs this explicit dependency graph and a defined response-PDF production/check step. Human page approval remains necessary; mechanical checks alone are not readiness.

## All twelve response paths challenged

| Comment | Path after attack |
|---|---|
| R1-1 | T5/T6 descriptive groups + CI + concession is viable; remove residual independence/generalization claims (2,7). |
| R1-2 | T3 capability table is viable; add metric/export-versus-pin-validation boundary (1). |
| R1-3 | Incomplete: alpha and actual assignment/fallback missing (3); concede untested extremes. |
| R1-4 | Viable scope correction, but requires diagram and metric fixes (1,2,6). |
| R1-5 | Viable coverage concession; audit fork range/population wording, keep dense buses untested (7). |
| R1-6 | Complete planned path: exact titles + relevance decline; no citation obligation or escalation needed. |
| R2-1 | Roadmap/no timing logs + existing CI is viable; independence claims still undermine conservatism (2). |
| R2-2 | Conditional comparison is viable only with global text/figure/response sweep (2,6,7). |
| R2-3 | Title choice survives, validation implication does not (1). |
| R2-4 | Partial by design: join tradeoff supplied, detector-miss effect unanswered empirically (4). |
| R2-5 | Partial: genuine table, incomplete mechanism coverage and residual causal explanation (5). |
| R2-6 | Discussion path survives; preserve single-scalar/mixed-size limitation. |

## D1–D4 dispositions

- **D1 MODIFY survives.** Unrelated histories, A-only fork edits and newer revision figures defeat wholesale merge/rebase. Challenge: selective port can overwrite corrected prose and retain stale assets. Require an allowlist and figure exception ledger (6), not a different merge direction.
- **D2 ACCEPT survives as title choice only.** “Structural Circuit Netlists” resolves the value-reading implication if accompanied by finding 1's measurement limitation. Bosco's title lock remains a real decision, not evidence of technical validity.
- **D3 ACCEPT overturned → MODIFY.** Fork structure is useful; factual prose requires comprehensive reconciliation (5,7).
- **D4 MODIFY survives, insufficiently specified.** One builder and separate clean/highlighted artifacts are sound. Findings 6/8 require dependency and figure-content gates; adding mechanical checks cannot replace accountable editorial approval.

## Every OPEN challenged

1. **Owners/D2:** accepting task ownership and title lock require actual people; cannot invent acceptance. Mechanical assignment tables can be prepared by an agent. P should not delay independent evidence work for this.
2. **Numeric provenance: CLOSED by inspection in this audit.** S/`fresh-join-ablation.json` → `perfect.f1 = 0.8898305084745762`, `perfect.{tp,fp,fn}=420/40/64`. S/`historical-wire-config.json` → `[1].global_f1 = 0.9755200226404415`, `[1].config.{dedup_angle,dedup_dist}=10/18`. S/`wire-rerun.json` → `[0].global_f1 = 0.972629796839729`, `[0].config` gives 12/8; `[2].global_f1 = 0.7893531768746423` (`otsu_component`). Stored precision/recall are available too. Respective file SHA256s: `e65eab270d1ce4c3506ac12476c3b49b77e2e334d5fa238c31784ad076f34639`, `105bb706697e8b07f6f4445aaf3f8dd86dfff7395abca8f4e01df444219d76c7`, `8e58d76704aeb5e241b234f1e40bae43c413518a6c5f474def95110735d6d1cd`. Existing filenames containing “rerun” describe prior work, not actions performed here. Package these artifacts/provenance in the execution phase; no human discovery or fresh run is needed.
3. **Autonomous result:** default removal closes this optional decision operationally. Existing markdown is insufficient prediction/matching provenance; do not promote it. No reason to block the package.
4. **Reviewed baseline:** genuinely unresolved identity. V/context/00_original_paper and K's August-25 manuscript are candidates, not proof of what was reviewed. File hashing/diff inventory is agent work; confirmation from the submitted record is a human/account-access dependency. Do not equate the fork parent with the reviewed version.
5. **Template/environment:** mixed. Locating/retrieving template support and preparing a reproducible build environment are technical tasks, not author-only facts. No tracked class was found. Actual render approval needs a named person; today's no-build rule explains why it remains unverified, not why humans must supply the environment.
6. **Authors:** consent, identity and funding truth remain human-owned. An agent can inventory existing fields and discrepancies first; A already contains ORCIDs/bios. A:35–36 still carries publication/DOI placeholders, omitted from P's explicit T8 list. Assign their template-appropriate disposition without inventing dates or identifiers; final sign-off must cover it.
7. **Editorial sign-off:** human approval survives. Source grammar checks, mathematical notation defects (3), reference ordering/format checks and a concrete exceptions list can be prepared by agents before handoff. P currently assigns no comprehensive source-edit pass for these checklist requirements; obtaining a name alone does not fulfill them.

**Readiness judgment:** the plan needs corrected closure criteria and dependencies before execution. The largest remaining scientific risks are pin-level overinterpretation, persistent global claims, and the deliberately partial R2-4/R2-5 answers. None is resolved by completing twelve response fields or producing a clean build.

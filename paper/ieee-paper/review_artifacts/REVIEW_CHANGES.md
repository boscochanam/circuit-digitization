# Source change index and execution record — 8 September 2026

This records the authorized prose revision on `revision/access-2026-33821-merge-20260907`, starting at `212e872`. It is **not** a final reviewed-baseline diff, pagination index, rendered-page approval or submission-ready manifest. No algorithms, parameters, author/funding/bio fields, reruns, builds, pushes or email were changed/performed. The sole figure-content exception is the explicitly authorized text of `figures/pipeline_overview_tikz.tex:22`; all binary figures and other figure sources are unchanged.

The plan was read from `/home/claw/circuit-digitization-validation-20260907/notes/IMPLEMENTATION_PLAN.md`, verified against audit branch `validation/audit-20260907-astra` at `docs/research/experiments/validation-20260907-astra/IMPLEMENTATION_PLAN.md`, and amended as `notes/IMPLEMENTATION_PLAN.md` on this merge branch. The audit branch was not moved. `notes/PLAN_REDTEAM.md` preserves the supplied report unchanged. The response uses the organization of fork `10c1b92`, but its factual prose was rewritten and the twelve complete concerns were copied from the decision letter with whitespace normalization only; no unrelated histories were merged.

## Per-finding disposition

All manuscript anchors below occur in **both** live sources. PDF pages remain pending a later authorized build against the confirmed reviewed baseline.

| Finding | Disposition / source action | Evidence or stable anchors | Local commit group |
|---|---|---|---|
| 1 | Source correction complete: authorized D2 title/heads; output/metric distinction; four-row capability table | Abstract; Introduction; Pipeline Overview; synthetic metric definition; `tab:capabilities`, including “Metric boundary”; Conclusion; evaluator `comp_pairs`/`gt_pairs` discards pin identity | `1cc61ec` |
| 2 | Source claim sweep complete, including captions and the authorized pipeline node text; stale binary contents remain a T7 blocker | `fig:pipeline`, `fig:endpoint_graph`, `fig:completion`, `fig:join_comparison`, `fig:real_join_fig`; Related Work; real evaluation; VLM section; Discussion. No equivalence/global-short/endpoint-drop/baseline-upper-bound claims retained | `8d97dcc`, `10c1208` |
| 3 | Source correction complete: component-first versus fallback selection, alpha 0.35, unweighted union-find, clamped completion reach, witness costs, mandatory row/slot/dummy assignment and guarded application | “Edge type 3”; “The tolerances”; “Degree-budget completion retains”; “When candidates exist”; “Matches are then applied”; `core/join_graph.py:176–209`, `core/completion.py:139–235` | `7a11ae4` |
| 4 | Honest source/response qualification complete; scientific detector-error effect remains unmeasured | Discussion “Component detection has reported”; R2-4; two-edge C242 TP/FP/FN 27/4/0 → 19/0/8 | `79e5017`; response group |
| 5 | Honest negative-ablation wording complete; no full-occlusion or completion-wide scale-removal evidence claimed | `tab:edge_ablation` and following paragraph; Wire Detection Benchmark; R2-5. Same aggregate counts do not prove same pairs, activations or completion masking | `79e5017`, `10c1208`; response group |
| 6 | Plan/figure ledger complete for this pass; figure reconciliation and rendering remain technical T7 work | Ledger below; A uses three PDF concept assets, B uses TikZ. Binary-only changes must later receive highlight mappings | `0f410c9`; this index |
| 7 | Response scaffold factual rewrite complete; twelve verbatim concerns + twelve responses/actions; final pagination/render/approval pending | `RESPONSE_TO_REVIEWERS.md`, including opening, electrical-subset range, crossover and ablation answers. No claim that per-drafter cells show transfer | response group |
| 8 | Plan back-edges corrected; actual package freeze not performed | T1 before overlapping edits; T8 factual input before freeze; clean pagination before T4 page references; response/highlight checks before package freeze; subsequent edits invalidate affected artifacts/approvals | `0f410c9` |
| 9 | Numeric provenance CLOSED from existing local files and verified hashes; no rerun | Exact paths/fields/hashes below and plan T6 ledger | `0f410c9`; this index |
| 10 | Agent/human responsibilities separated; original A:35–36 publication-history/DOI fields explicitly added to T8 spec and left untouched | Plan OPEN/T8; protected fields checked against starting SHA; technical template/source checks are not author-only inputs | `0f410c9` |

Additional planned prose completed: descriptive drafter groups/provenance (R1-1), generic-device/export distinctions (R1-2), manual threshold/mixed-size limits (R1-3/R2-6), electrical-subset complexity and dense-bus limits (R1-5), proposed annotation/expansion protocol with no invented timing (R2-1), conditional VLM comparison with provisional autonomous numbers removed (R2-2), and exact-title relevance decline (R1-6). Otsu remains 0.789. The wire caption/text identifies historical 10°/18px deduplication versus production 12°/8px; no production setting changed.

## Existing-artifact numeric ledger

S = `/home/claw/circuit-digitization-validation-20260907/notes/scratch`. Files were loaded and hashed only. These external audit files are not copied into the submission source bundle in this pass; a later package task must include or otherwise supply their provenance without a scientific rerun.

| Artifact | Stored fields and displayed result | SHA256 |
|---|---|---|
| S/`fresh-join-ablation.json` | `perfect.f1=0.8898305084745762` → 0.8898; `perfect.{tp,fp,fn}=420/40/64`; stored P/R → 0.913/0.868 | `e65eab270d1ce4c3506ac12476c3b49b77e2e334d5fa238c31784ad076f34639` |
| S/`historical-wire-config.json` | `[1].global_f1=0.9755200226404415` → 0.9755/0.976; `[1].config.{dedup_angle,dedup_dist}=10/18`; `[1].precision/recall` → 0.973/0.978; `[0]` anchor-12 row → 0.973/0.974/0.972 | `105bb706697e8b07f6f4445aaf3f8dd86dfff7395abca8f4e01df444219d76c7` |
| S/`wire-rerun.json` | `[0].global_f1=0.972629796839729` → 0.9726 with `[0].config` 12°/8px; `[2].global_f1=0.7893531768746423` → 0.789, `[2].config.name=otsu_component`, stored P/R → 0.796/0.783 | `8e58d76704aeb5e241b234f1e40bae43c413518a6c5f474def95110735d6d1cd` |
| S/`crossover-causal.json` | `C242_D1_P1_jpg.baseline` versus `.no_crossing_type2`: `tp`, lengths of stored `fp`/`fn` → 27/4/0 versus 19/0/8; `.removed_edges` has two edges | `7346b9708d8575bafe9d44000209158984534839e2736a02df1a83f8c219e263` |

Other stored-data checks (no rescoring): `docs/research/experiments/join_micro_n31.json` supplies `micro.scale_completion` and `macro.scale_completion`; `bootstrap_ci_n31.json` supplies `join/scale_completion.micro` and `VLM_minus_ours_micro`; `vlm_clean_rerun_n31.json` supplies n, micro/macro and stored exact component-pair rows. `join_reach_sweep_n31.json` records macro-F1 for reach factors 3–5; its 3.5 row is 0.8954648, accounting for the corrected lower bound. `ground_truth/real_nets_verified.json` electrical index lists and `join_micro_n31.json` per-image `comps` fields give 31 images, range 3–14, median 7, 15 at most five and 12 at least ten; the response calls these the evaluated electrical subset. These are inventory checks, not recomputed connectivity scores.

## T1/T7 figure dependency and presentation ledger

All paths below are relative to `paper/ieee-paper`. A = Access; B = local IEEEtran source. Generator/source mappings are obtained by static inspection, not certified regeneration provenance. All existing binary asset hashes are unchanged from `212e872`. Internal PDF text was extracted mechanically to stdout; no PDF was built or visually judged. No generator was executed.

| Scientific figure | A consumption | B consumption | Source/data/config provenance and required T7 action |
|---|---|---|---|
| Pipeline overview | `figures/pipeline_overview.pdf`, text width | `figures/pipeline_overview_tikz.tex`, input | TikZ node 22 now says Structural Netlist / Inferred pin-to-node map. Existing PDF still extracts “SPICE Netlist”, “Pin discovery”, “+ simulation”. **Must reconcile before submission.** The legacy `generate_concept_figures.py` also defines a pipeline generator; do not assume it reproduces the TikZ. |
| Endpoint graph | `figures/endpoint_graph.pdf`, column width | `figures/endpoint_graph_tikz.tex`, input | Existing PDF/TikZ relationship is not certified by source equality. Current `generate_concept_figures.py` emits a differently named `endpoint_graph_concept.pdf`. Confirm correct production path and content during T7. |
| Completion | `figures/completion.pdf`, column width | `figures/completion_tikz.tex`, input | Existing PDF has a local same-component matching guard label; caption now limits the guarantee. Current concept generator emits `completion_concept.pdf`, not this consumed filename. Reconcile actual dependency/provenance at T7. |
| C37 pipeline example | `figures/pipeline_examples/C37-D2-P4-jpg.png`, 0.48 text width | Same | `generate_pipeline_examples.py`, `cfg` uses dedup 12°/18px and anchor 16, distinct from both wire-table historical 10°/18px and production 12°/8px. Preserve the image/config-specific caption, not benchmark wire counts. |
| C111 pipeline example | `figures/pipeline_examples/C111-D1-P1-jpg.png`, 0.48 text width | Same | Same generator/config; its image-frame selection is conditional on matching labels. Do not infer asset counts from unrelated wire benchmarks. |
| Wire benchmark | `figures/wire_benchmark.pdf`, column width | Same | `generate_concept_figures.py:wire_benchmark` hardcodes values. PDF text confirms adaptive Gaussian 0.928 and Triangle 0.758, while corrected evidence uses 0.845 and 0.795 respectively. **Stale chart requires later correction**, not a new scientific run. Headline 0.976/Otsu 0.789 remain consistent; caption identifies historical dedup settings. |
| Synthetic join comparison | `figures/join_comparison.pdf`, text width | Same | `generate_join_comparison.py` has stored plot arrays for severity and per-circuit values; references `synthetic_leaderboard.json` and `per_circuit_scale_completion_l4_n16.json`. Caption no longer infers fragmentation-only errors from precision. |
| Real join comparison | `figures/real_join_comparison.pdf`, column width | Same | `generate_real_join_fig.py` reads `bootstrap_ci_n31.json`, `cc_detected_micro_n31.json`, `hough_micro_n31.json`. PDF text agrees with displayed 0.890/0.829/0.816/0.787/0.667/0.805/0.624 and VLM 0.923; caption is now conditional. Render appearance remains unchecked. |
| Complexity histogram | `figures/complexity_histogram.pdf`, 0.82 text width in single-column figure | Same | No generator located by repository text search. Electrical-subset counts checked against existing JSON; source caption corrected. Recover historical generation provenance and address the known single-column width risk in the later layout phase; no figure change here. |

Immutable scientific evidence must be preserved. Presentation assets need not be treated as scientifically authoritative merely because their hashes are frozen. T7 must account for internal figure text and changed binary regions in highlighting, not only caption/source hunks. The ablation table's existing width issue and the new capability table also need target-template layout checks; none was performed here.

### Figure/source hashes at source-review handoff

| Path | SHA256 | Relative to starting commit |
|---|---|---|
| `figures/pipeline_overview_tikz.tex` | `43ff4098b924e214a7124fd872bb11410b8823607d2a4967a19ed04baad2167c` | authorized node-label text only |
| `figures/pipeline_overview.pdf` | `a29120b1042237332b2724b0ccbaabef584bf77893a3c677676300831070178b` | unchanged |
| `figures/endpoint_graph_tikz.tex` | `33c99e5860134a8ed4389d737226794423bb6427862c50ca92420fe0d594217a` | unchanged |
| `figures/endpoint_graph.pdf` | `05ed63fb57b489c44d1f1e15f3ac029ca3849be66ee56e1a531b3192bb73fe40` | unchanged |
| `figures/completion_tikz.tex` | `fa6541b8d9d3af1eebb076317e4b697e91dfcf936695a5336a9c10829245d8cf` | unchanged |
| `figures/completion.pdf` | `a31bbfdaa52a63df4f74cb9e448937980cbe55a385fb5aa13a0aeb8f70f57fd6` | unchanged |
| `figures/pipeline_examples/C37-D2-P4-jpg.png` | `d415a90fc0dda36aeb7507810d51c910bb9b1257166faf33677f314379da4b19` | unchanged |
| `figures/pipeline_examples/C111-D1-P1-jpg.png` | `17ef978c639fb3753db57baffb2755210db6c822e022535f5034710bb48ebbbe` | unchanged |
| `figures/wire_benchmark.pdf` | `19c0b4903cfc7189f41e868fbeec2fbb8570aac18ac63f4ac8b5c5b1ca62d8a0` | unchanged |
| `figures/join_comparison.pdf` | `c4059b9617ea82a2f24acb0d54140ea398d1a20cf7663fc6fccefe9e3b77f3e0` | unchanged |
| `figures/real_join_comparison.pdf` | `4229b82e1a72ba3df16ff5fbabd0b4afc351b030427618592d3ee28ae845975d` | unchanged |
| `figures/complexity_histogram.pdf` | `a9333f787ae1fb4df863c355286b4671536a96ab9845dee4507e5e0cda38cdbf` | unchanged |
| `generate_pipeline_examples.py` | `1b616cd0020513d5f4026f8241804b76d55d652aec0f2f244f6ed92b5f57e112` | unchanged |
| `generate_concept_figures.py` | `11a1ff767da6385208b3f74511d43cb35dc0f979c3b318806acffa0ab2c487ce` | unchanged |
| `generate_join_comparison.py` | `72143943f162b4c27247742b2c7de6a3abee4a4bef2cbf137a5366a0c3a13455` | unchanged |
| `generate_real_join_fig.py` | `9dafbb1202228523edf33a9d46cc7919e15cdef139b0f49454c341c6386c5e79` | unchanged |

## Source verification and limits

- PASS: abstracts and scientific bodies match across A/B after whitespace/comment normalization and the two pre-existing body figure-input substitutions (`endpoint_graph`, `completion`). The pre-Introduction pipeline source/PDF difference is separately listed above, not silently normalized into a figure PASS.
- PASS: all 15 captions are identical across A/B; existing table numeric tokens are unchanged; source references resolve to labels; label names are unique and relevant LaTeX environments are balanced. These are source checks, not compilation/layout certification.
- PASS: both complete preambles/frontmatter match `212e872` after only the authorized title/running-head replacement. From Acknowledgment through bibliography and biographies, both files are unchanged. Original A:35–36 remains untouched.
- PASS: twelve reviewer concerns match the decision letter verbatim after whitespace normalization; twelve nonempty responses and actions. Responses use source anchors and do not invent final PDF pages.
- PASS: literal banned-claim regressions are absent from the live prose; semantic review checked negations, conditional comparisons, residual scientific limitations, captions and response text. The known stale binary exceptions above prevent a whole-package claim of closure.
- PASS: protected algorithm/config files and all binary figures are unchanged; the only changed figure-source line is the explicitly authorized node label. `git diff --check` passes.
- No test suite, benchmark, detector, simulation, bootstrap, figure generator, TeX compiler, PDF build or publishing command was run. Mechanical extraction of existing figure text is not a render approval.

## Human inputs still required

1. Accepting owners for remaining team follow-through and one accountable T7 builder.
2. Identify the actual reviewed source/PDF pair from the submitted record. The audit branch/fork parent and August-25 manuscript are not assumed to be that baseline.
3. Approve author/byline/order, affiliations, existing ORCIDs, biographies/photos, funding and publication-history/template-DOI disposition. Provide byline-change permission/form if comparison to the confirmed reviewed byline requires it. No such field was edited.
4. Give editorial and rendered-page approval, then final consent tied to the frozen source/PDF/package hashes after T7 and final response pagination. A later edit invalidates affected checks and approvals.

Technical work still outside this pass: template/environment preparation; correction/reconciliation of stale figure assets; layout and clean/highlighted/response PDF builds; final page references; evidence packaging and final manifest. These are not inherently human-only tasks. Scientific limitations remain pin-level correctness, detector-miss causality, full occlusion/scale ablations and broader generalization; a signature or build does not resolve them.

## Source hashes (not submission-package approval)

- `paper-access.tex`: `b264325a5168cc35f4258c971f62f781c3631531127e83be0e343e654aa3d0ee`
- `paper-build.tex`: `10e1e45c23baa35791d20a4e0d907ccf96becd130ef380958b12e41b9aa53795`
- `review_artifacts/RESPONSE_TO_REVIEWERS.md`: `129728e884f4df23bd1b0cfb9d1fafcfda8440bab57b97482199e1255a75fda9`

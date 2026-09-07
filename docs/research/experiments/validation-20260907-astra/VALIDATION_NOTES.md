# Independent validation — 2026-09-07

## 1. Verdict

**Do not rely without fixes for submission or autonomous image-to-SPICE claims. Rely with caveats on the controlled connectivity results and historical wire benchmark.**

Phase 1 was completed and recorded separately in [PHASE1_ASSESSMENT.md](PHASE1_ASSESSMENT.md) before this structured report. This is an audit of detached commit `36b9a8ebfd7d38856c8fe12e533dbdc91e5947c5`, the supplied historical patches, and the separately supplied dirty patch/PDF artifacts. No production code was edited, no model retrained, and no email, GitHub comment, push, or submission was made.

The main controlled result is real: fresh execution on all 31 verified images reproduces **418/37/66 TP/FP/FN, micro-F1 0.890308839**, with every per-image count matching the committed artifact. Fresh synthetic evaluation reproduces the rounded **0.95 versus 0.36** L4 comparison. The VLM artifact recomputes to **0.923076923**, **21/31 exact**, and **14/15 exact among the small cases**; the stored bootstrap intervals reproduce. This is substantial evidence for the controlled component-pair experiment.

It does not establish a globally short-free netlist, exact terminal connectivity, equivalent VLM accuracy, unseen-style generalization, or an autonomous pipeline at 0.890. The current manuscript and submission artifacts still make claims beyond that evidence. The revision also has a reversed ablation interpretation, a parameter/result mismatch, an outdated committed PDF, and a visibly clipped new table in the supplied revision PDF.

Evidence labels used below:

- **Fact:** directly read in code/history/artifact or freshly observed; the source is identified.
- **Inference:** a conclusion from those facts, with its scope stated.
- **Estimate:** derived descriptive quantity, not a measured population guarantee.
- **Unverified:** required underlying evidence or execution is absent. A committed prose report is evidence that someone reported a result, not independent proof of its underlying run.

The tests use the supplied symlinked environment. The full CGHD corpus and trained detector are absent from the dedicated checkout. However, the externally configured **134-image wire subset and component-label assets are available read-only**, and were actually used; this audit therefore does include a full rerun of selected wire configurations on that subset and all 31 join images. It does **not** include model validation, detector training-split reproduction, a new VLM call, or TeX compilation.

## 2. Contribution-by-contribution assessment

The pull status comes from [pranavesh-activity.md](../context/02_pranavesh/pranavesh-activity.md). Content and ancestry were checked independently in local git. The exported focused PR files have blank filename headings; their hunk contents are useful, but they are not complete author-attribution records.

| Contribution | Author-owned changes and evidence | Current survival / assessment |
|---|---|---|
| **PR #2 — merged: experiment harness** | `30c020b` adds 802 lines in `wire_detection/benchmark/experiment_harness.py`: config/result dataclasses, local-median masking, ROI offsets, PCA extraction, overlap dedup, anchoring, reconnection/secondary-recovery experiments, overlays and config ranking. Actual patch: [pr-2-focused.md](../context/02_pranavesh/pr-2-focused.md); `git show 30c020b`. | Substantial retained implementation, extended by #4 and later authors. Current history contains equivalent author commit **`c44fd56`**, not `30c020b`; their harness contents have identical SHA256 `34e545f428bd23a53a7212896fbf40d87c72e39603b0f4d1dd42ac6a163404a6`. Do not count rewritten equivalents as separate contributions. The later winning extractor uses this infrastructure, but the original test/config numbers are historical. |
| **PR #2 — reference portability, entry point, regression** | Same commit changes hardcoded reference paths to `WIRE_GT_IMAGES`, `WIRE_GT_LABELS`, `WIRE_HDC_BASE`, and split overrides; adds `wire-benchmark-exp`; adds baseline test for 0.7066 and 248/70/52/84. | Entry point and path overrides survive. Better portability was a real improvement. Current test expects 0.9432 after later revisions, yet guards only a hardcoded HDC directory. A clean/default-path invocation fails; empty experiments silently proceed. These weaknesses do not erase the contribution. |
| **PR #4 — merged: hybrid/port/threshold experiments** | Author/squash commit **`f8c2331`** has one parent (`9cc27a3`), Pranav as author and GitHub as committer, with coauthor trailer. It adds about 1,984 harness lines and changes 56: threshold alternatives/fusion, skeleton and Hough extraction, port gating, seed/stroke repair, candidate selection, waves 3–8 and synthetic scoring. Actual hunks in [pr-4-focused.md](../context/02_pranavesh/pr-4-focused.md). | Retained experimental branches; the default a16 component/PCA path does not activate most of these recovery options. It is incorrect to call all this the production winner or the later endpoint-graph join. The June completion/default promotion appears in Chris/Bosco history (`a9cd0c3`, `77aebf7`, `82d8c80`), not this PR. |
| **PR #4 — learned branch and local GT export** | Adds `learned_branch.py` (TinyUNet, synthetic pretrain, GT fine-tune, evaluation) and `build_local_reference_hdc.py` (CGHD instance JSON/XML to OBB labels and copied source images). | Both remain. Learned branch has **training/evaluation overlap**: both enumerate the same GT directory; its result is not a held-out generalization score. Export script assumes a specific local corpus layout and writes into a directory named `roboflow_test2`; the directory name does not mean those exported annotations are predictions from a Roboflow model. No independent learned-model benchmark was run. |
| **PR #4 — quality analysis, tests, VLM CLI maintenance** | Adds `quality_analysis.py`, tests for CGHD subset export and VLM CLI audit, extends benchmark tests; VLM CLI change removes an unused `rows` binding. | Tools and tests survive. The quality analyzer joins historic reference/candidate scores to image-quality metadata; it is not proof of VLM connectivity capability. PR #4 did **not** author the entire pre-existing `wire_detection.vlm` package. Reference parsing assumes UTF-16 and exact historical row formats (`quality_analysis.py:41`); default input paths require external/local artifacts. |
| **PR #4 — MethodsX draft/assets** | Adds `paper/main.tex`, frontmatter, sections, figure generator, tables, references and PDF. | Historical. Later rewritten around joining, then archived under [archive/paper-methodsx](../repo/archive/paper-methodsx) by `0345487` (equivalent history includes `e8b87a5`). Current archived prose contains later authors' changes and stale scores (e.g. adaptive Gaussian 0.928 / Otsu 0.828). Do not attribute the entire current archived draft to Pranavesh. |
| **PR #75 — closed, not merged: legacy IEEE rewrite** | [pr-75-focused.md](../context/02_pranavesh/pr-75-focused.md), especially lines 44–418 and 450 onward: reworks pipeline-example generator toward API preset reuse and exact-match lookup, switches the illustrative case, proposes a four-panel presentation, retitles legacy `paper.tex` to **NetGuard**, adds structural-score/synthetic tables and uncertainty, expands name/byline and references. Reports 0.9416 synthetic F1 and structural error 0.2710; explicitly concedes no real net-GT in that draft. Six binary figure patches have no text. | These are scientific presentation changes, not implementation of a new join algorithm. `paper.tex` is explicitly superseded in the paper AGENTS file; the live two-source manuscript is different and now has real net-GT. Current generator was subsequently changed in Bosco-authored commits. The pack does not identify a unique #75 author commit or complete commit list, so ownership of each overlapping hunk and binary figure is **unverified**; PR authorship alone is insufficient. No evidence found that the proposed NetGuard rewrite became the live manuscript. |
| **PR #77 — closed, content integrated through #78** | Author commit **`22d6882`** (equivalent text-only `1585966`): both TeX sources, two TikZ sources, regenerated PDF. Removes resizebox wrappers, enlarges drawing units/device boxes and panel spacing, changes floats to `figure*`, shortens abstract and algorithm exposition, removes subsection headings. | **Present in ancestry via `0a286d4` → `aab509e` (merged PR #78)**. The conflict-resolution merge and incoming main-branch content are Bosco's integration work, not newly authored Pranavesh content. Much native layout/prose survives. Later `9d54a51` replaces inline TikZ in Access with PDF figures, so “both sources input the same TikZ” is stale. No compiler available; existing PDFs are not proof that today's sources compile. |
| **PR #77 — author/funding/affiliation edits** | Same author diff adds “Kumar”, contact emails, Pranavesh's USC bio, replaces funding placeholder with **“This work received no external funding.”** In local build it removes “Symbiosis Centre for Applied AI” from the affiliation; the Access edit initially retains it and adds emails. Other bios become generic placeholders. | Full name and no-funding statement survive; later commits change affiliations/bios and add authors. These require factual author confirmation, not a formatting sign-off. No consent/funding evidence was supplied. This audit cannot determine the actual submitted byline merely from the four-author pre-August snapshot: the decision email already addresses six authors. |

**Attribution boundary:** #2/#4 are May work, #75/#77 are June work, and reviewers responded in August. The revision commits `fe109ec` and `36b9a8e` are Bosco-authored. It would be chronologically wrong to criticize Pranavesh for failing to implement August reviewer requests in his June PRs. The question is whether those changes remain sound and whether the **current** revision closes the review.

## 3. Findings, ordered by severity

### F1 — High: the claimed global structural guarantee is false

**Fact.** [join_graph.py](../repo/wire_detection/core/join_graph.py), lines 143–152 and 210–231, unions endpoint and rail proximity edges without a no-shared-component guard. [completion.py](../repo/wire_detection/core/completion.py), lines 123–137, imports those base unions; lines 215–235 guard only subsequent completion merges. It never separates already shorted base nets.

Fresh final netlists contain eight same-node two-pin electrical-component assignments across four images; see `shorted_two_pin_components` in [fresh-join-ablation.json](scratch/fresh-join-ablation.json). These are structural assignments, not eight independently adjudicated physical error labels. The GT uses component membership with generic terminal marker `e`; it does not certify pin-specific correctness. A perfect component-pair score can coexist with a shorted component (C109 is one concrete example).

[paper-build.tex](../repo/paper/ieee-paper/paper-build.tex):71, 123, 341 and 347 promises structural validity/short prevention much more broadly. These inherited claims survive #77's prose simplification and the August revision. **Inference:** the guard limits additional completion shorts, but cannot guarantee an electrically correct or globally short-free recovered graph. The plan's recommendation to retain “structural guarantees” is not justified.

### F2 — High: output scope and “dominant bottleneck” still exceed the experiment

**Fact.** The title and running heads remain “SPICE Netlists” (`paper-build.tex:28,37`; Access `:41,55–57`). The revised abstract explicitly says values are not read (`build:42`), which is good, but the conclusion (`:353`) does not repeat the values limitation. The introduction and Fig. 1 caption (`:52,67,77`) still frame joining as the end-to-end bottleneck / recognition as largely solved, while `:339` reports detected-box micro-F1 **0.247** and calls detection the autonomous bottleneck.

The perfect-wire run reproduces **420/40/64**, micro-F1 **0.889830508**, versus **0.890308839** on detected wires. They round to the same 0.890; they are not literally identical. Both use supplied component boxes. This comparison isolates wire quality conditional on those boxes; it cannot establish an end-to-end detector bottleneck hierarchy.

**Fact.** [spice.py](../repo/wire_detection/core/spice.py):200–276 converts a switch into a resistor, represents FETs with a PNP BJT model, skips unsupported IC/opamp primitives, and may redirect same-node R/C/L terminals to ground; lines 282 onward inject illustrative test supplies. Therefore SPICE serialization is not an exact reconstruction certificate. [join_eval_real_f1.py](../repo/wire_detection/benchmark/join_eval_real_f1.py):38–55 scores unordered component pairs, discarding terminal identity. **Inference:** an honest scope is component-pair/topological recovery plus illustrative SPICE export and externally supplied values. Changing “simulatable” to “structurally valid” alone did not solve the scope problem.

### F3 — High: source, compiled manuscript and resubmission package disagree

**Fact.** The committed `paper/ieee-paper/paper-build.pdf` still says **“simulation-ready SPICE netlists”** in its abstract and lacks the new provisional detected-box, annotation and ablation passages. Compare extracted [current-pdf.txt](scratch/current-pdf.txt):16 onward with `paper-build.tex:42,213,339,349`. This PDF is stale relative to HEAD.

The separately supplied [25-Aug revision PDF](../context/01_review_materials/paper-build_MANUSCRIPT_2026-08-25.pdf) does include the revision. Its **page 6 ablation table runs beyond the right page edge**, hiding columns. This was visually inspected, not inferred from source: [rendered page](scratch/revision-page6.png). The source puts a long six-column table in a single-column `table` (`build:213–233`); the complexity plot is also declared `0.82\textwidth` inside a single-column `figure` (`:281–287`), a separate layout risk.

The dirty patch explicitly fixes unescaped `C138_D1_P3` to `C138\_D1\_P3` in both sources and includes a regenerated binary PDF. That fix is **not in this clean checkout** (`build:341`, Access `:365`). The patch was inspected but not applied. Text parsing cannot prove that unescaped TeX compiles successfully.

**Blocker:** `pdflatex`, `latexmk`, and `tectonic` are all absent. No source compilation was attempted or claimed. The Access source now includes compiled concept PDFs while the local build inputs TikZ; body comparison found that intentional figure-path difference plus a funding comment, not substantive prose divergence. The Access render remains unverified.

No completed 12-comment response or highlighted manuscript was found in the supplied pack/tracked checkout. The supplied response document is a blank template with placeholder ID/title. Commit prose referring to a response letter is not the letter itself. The decision letter requires response, highlighted PDF, and clean manuscript; those package items are not demonstrated here.

### F4 — High: “scale-relative tolerances are worth +0.005” has the sign backwards

**Fact, freshly reproduced.** `paper-build.tex:213,235` says scale-relative tolerances add +0.005 / switching to fixed pixels “costs” 0.005. The table and [edge_ablation_results.json](../repo/docs/research/experiments/revision_evidence/edge_ablation_results.json) show the opposite:

| Base-graph condition | TP/FP/FN | Exact micro-F1 |
|---|---|---|
| Scale relative | 352/27/132 | 0.815758980 |
| Fixed pixels | 356/28/128 | 0.820276498 |

Fixed pixels improve by **0.004517517** on this diagnostic. Both full pipelines tie at 418/37/66. This is a transcription/interpretation error introduced in the August manuscript integration, not a failed numerical artifact or a #77 algorithm change.

### F5 — High: 0.9755 belongs to a different wire configuration than the mandated parameters

**Fact, freshly reproduced on 134/134 exact-aligned images and 3,524 GT segments.**

| Config actually executed | Dedup angle / distance | TP / FP / FN / redundant | Wire F1 |
|---|---|---|---|
| Mandated current a16 settings | 12° / 8px | 3447 / 49 / 77 / 68 | **0.972629797** |
| Historical a16, other settings identical | 10° / 18px | 3447 / 47 / 77 / 49 | **0.975520023** |
| Current-parameter anchor12 | 12° / 8px | 3425 / 46 / 99 / 66 | 0.970117547 |
| Historical v4 anchor12 | 10° / 18px | 3425 / 44 / 99 / 47 | 0.973011364 |

See [wire-rerun.json](scratch/wire-rerun.json), [historical-wire-config.json](scratch/historical-wire-config.json), and their logs. `expanded_benchmark.py:218–225` explicitly uses **10/18**; `join_eval_134.py:60–77` uses **12/8**; root AGENTS says 12/8 but quotes the 10/18 scores. No production parameter was changed. **Inference:** the historical result is valid, but its configuration identity is incorrectly communicated. The correctly reproduced 31-image join result is unaffected.

Wire precision is **TP/(TP+FP+redundant)**, not TP/(TP+FP); `reference_pipeline.py:356–384`, `expanded_benchmark.py:163–165`. Omitting the redundant count from headline tables makes their listed FP/precision appear inconsistent. These are segment-match scores, not endpoint error percentages: the discussion's “97.6% accurate detector drops ~2% of wire endpoints” (`build:347`) is not a valid inference from wire F1.

### F6 — High: production entry points do not implement the documented universal model-source switch

**Fact.** [netlist.py API](../repo/wire_detection/api/routes/netlist.py):47–61 and [process.py](../repo/wire_detection/api/routes/process.py):148–168 load registry annotation labels and may substitute a Roboflow image. [dataset.py](../repo/wire_detection/data/dataset.py):268–289 uses `load_component_labels` plus `find_roboflow_image`. This path is not the new model loader, and changing `component_detection.source` in defaults does not route this netlist path through YOLO.

[component_loader.py](../repo/wire_detection/data/component_loader.py):90 uses `ComponentDetectionConfig()` rather than reading `defaults.yaml`; model output at :161–174 returns raw **16-class IDs**, whereas [component_classes.py](../repo/wire_detection/core/component_classes.py):10–29 / the join use the **58-class IDs**. For example raw model 0 means resistor, but core 0 means AND. The detected-box evaluation wrapper explicitly remaps these IDs (`detected_boxes_eval.py:64–81`); the public loader does not. This is an integration contract hazard, not evidence that the wrapper used the deprecated detector.

The separate generic pipeline's `defaults.yaml:1–36` also retains old k/window/min-area/endpoint/dedup settings and white-fill configuration; it is not the documented winning harness preset. **Inference:** users cannot reproduce the claimed model-driven system just by following the root AGENTS source-toggle example. Treat benchmark, annotation-backed UI, generic pipeline, and model wrapper as distinct entry points until their contracts are reconciled.

### F7 — High: detected-box evidence remains provisional for more reasons than absent CIs

**Fact.** The committed evidence is [detected_boxes_results.md](../repo/docs/research/experiments/revision_evidence/detected_boxes_results.md) and [conf025.md](../repo/docs/research/experiments/revision_evidence/detected_boxes_conf025.md), not their full per-image result JSON/model-output manifests. The .5 run reports 31 images, 226 GT electrical components, 242 detections, 148 matches, component F1 0.632 and join 0.247. The .25 note reports join 0.244. No detected-box VLM cell is established by these notes; similarly named old response files are not proof of the missing cell for this matched model protocol.

[detected_boxes_eval.py](../repo/wire_detection/benchmark/detected_boxes_eval.py):130–147 greedily matches boxes by axis-aligned IoU **without class compatibility**. Matching occurs across all symbols before the electrical subset is counted. Its “component detection F1” is therefore an electrical-subset box-matching statistic, not the same metric/protocol as the cited 88.5% detector mAP. Output names are not a substitute for detector model hash, inference settings, matched IDs, or a split/overlap manifest. Merged detector subtypes also lose polarity/device distinctions.

**Unverified:** trained-model mAP/70.7% crossover recall and the new inference runs were not independently rerun; the required model is absent in the dedicated checkout. It is good that the paper says “provisionally” (`build:339`). It should not infer a demonstrated distribution shift or a clean causal detector effect merely by comparing unlike mAP and F1 statistics. Reproduce and audit the wrapper before elevating this number into a definitive end-to-end conclusion.

### F8 — Medium/high: crossover causality is supported; a safe mitigation is not

**Fact.** Fresh label inspection confirms **13 crossovers in 8/31 images**. The default graph does not use class-specific rules for edge types 2/4/5. The plan's `_JUNCTION_TYPES` concern is real for that optional pin heuristic, but flagship `scale_completion` uses ordinary pins, so that set alone is not the diagnosis.

Fresh isolated type-2 suppression at the documented crossing locations reproduced:

- **C242:** original TP/FP/FN **27/4/0**; suppressing two crossing-adjacent edges gives **19/0/8**. The four false pairs disappear, but eight true pairs are lost (F1 falls from 0.9310 to 0.8261).
- **C112:** **20/1/0** unchanged; its false pair survives elsewhere.
- **C66:** false pairs remain **2**, while TP falls **27→23**; suppressing crossing-near unions also removes valid connectivity.

Exact edges and pair sets: [crossover-causal.json](scratch/crossover-causal.json); scratch implementation: [followup.py](scratch/followup.py). This confirms the principal causal diagnosis in the committed crossover report, not every claim in its discarded temporary scripts. The current manuscript's “a single edge type-2 union” (`build:349`) is less precise than the two removed unions. The report emphasizes FP removal while omitting the TP loss. **Inference:** do not implement a blanket exclusion on the assumption that it is harmless, and do not infer improvement from the FP-only result. A disclosure-only revision is defensible if its language stays narrow.

### F9 — Medium/high: empty-data evaluation can report perfect micro-F1

**Fact, reproduced.** With an absent HDC path, `join_eval_real_f1.py` skips all 31 images, exits **0**, and writes **n=0, micro-F1=1.0**. See [empty-join-output.txt](scratch/empty-join-output.txt) and [empty-join.json](scratch/empty-join.json). Cause: :86–89 silently skips missing assets; :117–120 assigns P=R=1 when both pooled denominators are zero. `detected_boxes_eval.py` uses the same empty-count convention. Evaluation output needs a nonempty expected sample-count check.

The #2 harness has a related fail-open path: absent GT files yield global F1 0.0 and still run its synthetic experiment. The focused test's skip guard checks only `/home/claw/circuit-digitization/roboflow_test2` (`test_benchmark_experiment.py:14–21`), not the configured GT inputs. With inherited paths it passes; with the three WIRE variables unset it fails **1 failed, 2 passed**, expecting 0.9432 and getting 0.0. `beat_reference` still compares against **0.7066** (`experiment_harness.py:1524`), not the current baseline. Historical headers still advertise the obsolete 23-image generation.

### F10 — Medium: learned-branch numbers cannot be presented as held-out performance

**Fact.** `learned_branch.py:119` and `:214` enumerate the same `ref.GT_LABELS.glob("*_jpg.txt")`; `:277–287` fine-tunes on that dataset for 12 default epochs and then evaluates it. There is no split argument or withheld list. This was introduced in #4, remains in current code, and is independent of the later YOLO component detector.

Seeding Python, NumPy and Torch (`:22–25`) is explicit, but the augmentation `A.Compose` is constructed without an explicit seed (`:110–117`); deterministic augmentation reproduction is not demonstrated by these tests. The two new threshold/port tests check mask shape and port count, not recovery accuracy, coordinate invariants, split separation or learned-model generalization. Keep this branch labeled exploratory/in-sample until a real split and reproduction record exist.

### F11 — Medium: ablation coverage and scale robustness are incomplete, and the intervention is narrower than its name

**Fact.** The six-row base/full ablation is reproducible and valuable: disabling T-junctions, rail taps, both, direction, or base scale-relative tolerances leaves all full-pipeline counts unchanged. It is no longer merely a strategy horse-race. However, “scale-relative off” changes only the **base** graph: completion still calls `_scale_tau` and uses `reach_factor * clamp(.62*s,24,60)` (`completion.py:94–96,134–135`). It is not leave-all-scale-dependence-out.

No committed full occlusion-off join row, planned joint tolerance multiplier/alpha sweep, or scale-dispersion-versus-F1 table was found. Completion-off can be read from the base/full comparison (0.8158→0.8903), but edge redundancy and score aggregation mean zero delta does not prove all recovered nets are identical or that completion is the sole reason every flag ties. In particular, the stored base scores for T/rail/direction also tie.

The scalar assumption and clamps are explicitly disclosed (`build:106`), a useful response to R2-6. The actual reach variable is the **clamped pin tolerance**, not raw median diagonal `s`, contrary to `build:123,210`. The reach sweep is correctly labeled **macro**, but its claimed 3–5 range **0.898–0.903** omits the **3.5 point 0.895464817** in `join_reach_sweep_n31.json`. The actual range is about **0.895–0.903**. Treat this as in-benchmark sensitivity, not evidence of general extreme-scale adaptation.

### F12 — Medium: matched priors and nonsignificance are sound; equivalence/cost/output claims are not established

**Fact.** Both methods' controlled scores use supplied GT component boxes; `join_eval_real_f1.py:91–103` and the VLM harness description support correcting R2-2's premise. Macro and micro are correctly distinguished in the main result table. Recomputed bootstrap values match exactly: ours CI **[0.854715516,0.923950301]**, paired VLM−ours **+0.032768084**, CI **[−0.009184500,+0.078096126]**.

**Inference:** this fails to reject zero difference; it does not demonstrate equivalence or “matches accuracy.” The plan's replacement wording makes that same mistake. Images are the resampling unit; repeated circuit IDs and small drafter groups mean these intervals are not a held-out-drafter generalization test.

No measured per-image VLM usage/cost ledger or paired runtime/cost protocol was supplied to substantiate **10^5 tokens/image** and **100–1000× cheaper**. The stored aggregate F1 cannot prove those claims. The VLM was requested to return JSON (`build:339`), so “free-form rather than structured/machine-checkable output” is misleading as a categorical contrast. The geometry's global validity guarantee is separately contradicted by F1.

### F13 — Medium: limited-data, drafter and device disclosures improve the paper but still need precision

**Fact.** Complexity recomputation gives **15 images ≤5 electrical components, 12 ≥10, median 7, maximum 14**. The 134-image detector benchmark is broader evidence for extraction, not 134 verified connectivity examples. Filename `D1/D2` denotes drawing index, not drafter; the old `cross_drafter_test.py:17–18` and classifier naming must not be reused to assert drafter validation.

The drafter report distinguishes **16 directly matched / 15 formula-inferred** assignments. The simple committed `drafter_map_n31.json` does not carry those per-entry confidence labels. The manuscript discloses inference globally and reports cells of size 4–7; it does not establish unseen-drafter testing or uniform generalization. The original truncated-archive reconstruction was not independently repeated in this audit; mapped F1 arithmetic is supported by the committed counts, archive provenance remains reported evidence.

Annotation by a single person, no timing log, and inability to report per-image cost are now explicit (`build:349`). This is better than inventing estimated minutes; the plan explicitly allowed that fallback. A concrete stratified expansion roadmap and the planned per-row CIs are absent; the figure includes intervals for five joins and a VLM band, but its generator uses `None` for Hough/CCL intervals (`generate_real_join_fig.py:34–39`).

The device paragraph (`build:349`) says complex-device pins are not extracted and switches are excluded from emission. Yet `netlist.py:34–37,68–70,298` provides generic templates/fallbacks for switches, relays, transformers and optocouplers, while `spice.py:202–212` explicitly emits a closed-switch resistor. Generic geometry is not validated pin recovery; located classes collapsed into the detector's `other` class are not separately established detections. A support table should distinguish detected class, generic pin guess, evaluated electrical subset and actual export behavior.

### F14 — Medium: manuscript algorithm description is stale relative to the shared assignment implementation

`paper-build.tex:108` describes AABB center-side routing. The code uses **OBB distance** (`component_assignment.py:86–111`) followed by **nearest-pin Euclidean selection** (`:114–134`), imported by `join_graph.py:178–183`. Directional weighting is confined to a fallback branch (`join_graph.py:190–204`), not applied as the manuscript's generic weighted-edge exposition suggests. The implementation performs unions rather than a weighted graph optimization; completion solves a slot assignment then rejects matches under a post-hoc guard, not a globally reoptimized guarded b-matching. These are inherited method-description issues, not evidence that #77 implemented an alternative algorithm.

### F15 — Medium: submission metadata needs verification, not automatic restoration

PR #77 substantively changed author identity presentation and the funding declaration. Later Bosco commits `934d48c` reorder Talupuri/Chiwhane; `a2eb56e` add Singh/Das and update bios/photos. Current Access frontmatter has six ORCIDs, so root/paper AGENTS' “all ORCIDs/bios still missing” is stale. Access retains placeholder publication history and a template DOI (`paper-access.tex:35–36`); build uses “Shwetambari A. Chiwhane” while Access byline uses “Shwetambari Chiwhane.”

**Unverified:** author-approved spelling/order, actual submitted byline, affiliations, bio facts, no-funding declaration and consent records. The original snapshot has four authors, but the August decision email names six recipients; that prevents a justified conclusion that the two additions necessarily occurred after submission. Confirm against the portal's actual submitted source/PDF before invoking a byline-change process. Do not silently revert names or add/remove authors based on either AGENTS or a stale snapshot.

### F16 — Lower severity: machine-specific fallbacks and presentation issues complicate reproduction

- `expanded_benchmark.py:18–19` prepends the other checkout and workspace to `sys.path`; `bootstrap_ci.py:17` hardcodes `/home/bosco/Projects/...`. Scratch runs explicitly pinned imports to the dedicated repo and checked for foreign `wire_detection` imports; none remained.
- `build_net_gt.py:84–115` chooses nearest pixel match and falls back to the first label when comparison is impossible. `expanded_benchmark.py:130–137` likewise falls back if exact match fails; standalone `join_eval_134.py:82–91` is still first-match. This violates the strict documented coordinate-safety expectation on missing/mismatched assets. All 31/134 inputs actually used here passed exact-image checks, so this did not invalidate these reruns.
- The Fig. 2 generator (`generate_pipeline_examples.py:40–44`) uses dedup 12°/18px and selects label-aligned example images. The canonical 12°/8px join run returns **12 wires for C111**, while the current caption says **11**; C37's **35 wires/7 GT nets** is verified. Figure counts must be tied to the generator's exact image/config, not copied from the benchmark and assumed interchangeable.
- PR #77's larger TikZ component rectangles retain old pin coordinates, making some schematic pins lie inside the illustrated bodies. Its full-width native figures and later column-width PDF inclusions have different scaling/readability. This is a conceptual-figure/render issue, not an algorithmic gain; validate the actual Access PDF.
- Fresh Ruff reports **157 findings**. They are not all scientific bugs and were not automatically fixed. AST parsing of all **173 Python files** succeeds. The important test gaps are model-to-core integration, empty-dataset failure, learned split separation, and claim-level terminal/short correctness, not merely total lint count.

## 4. Coverage of all 12 reviewer comments

Status assesses substantive closure in the inspected current revision. A **satisfied** row does not certify a completed response letter or reviewer acceptance. The formal response/highlighted package is absent for all rows in the supplied evidence.

| Comment | Status | Evidence / deviation from Claude plan / remaining gap |
|---|---|---|
| **R1-1: single corpus, N=31, styles/CIs** | **Partial** | Single-corpus scope, 31-image qualifier, headline CI, complexity and small per-drafter table exist (`build:42,210,281–309,349`). Missing broader connectivity validation/expansion roadmap; inferred drafter provenance and non-held-out design limit generalization. Prose fallback is justified; claiming that 134 wire images establishes connectivity breadth is not. |
| **R1-2: unsupported complex-device pin relations** | **Partial** | Named limitation is added (`build:349`), but no three-tier support table, and assertions about located classes, pin absence, IC export and switches do not match code (F2/F13). Not implementing new pin models is justified; describing capabilities inaccurately is not. |
| **R1-3: manually tuned thresholds/extreme scale** | **Partial** | Scalar/clamps, fixed-base diagnostic and reach sweep exist (`build:106,210–235`). Planned multiplier/alpha robustness sweep absent; fixed-base comparison retains scale in completion and is interpreted with reversed sign. No adaptive learner is required to close the request, but supporting claims must match the tested intervention. |
| **R1-4: no OCR/values, not simulation ready** | **Partial** | Abstract explicitly excludes value reading; supplied-box experiment/export limitations remain underqualified elsewhere. Title retained and conclusion lacks value caveat. Deviation from retitling can be argued only with consistent syntax/topology wording; current implementation/export and prose do not yet justify it. |
| **R1-5: small circuits, dense buses/crossings** | **Partial** | 15/31 ≤5, 12/31 ≥10 and max14 verified, with histogram and limited complexity analysis. This is a useful correction, but it does not validate dense/multilayer bus routing. T-junction zero-effect evidence emphasizes that gap. Planned explicit out-of-domain statement / appropriately bounded complexity claim remains needed. |
| **R1-6: two suggested memristor citations** | **Missing** | No completed response explaining relevance or politely declining found. The decision letter explicitly permits declining irrelevant suggestions, so omission from bibliography alone is not a defect; lack of an explicit response is. No email to the editor is warranted by the supplied evidence. |
| **R2-1: N=31 statistics, annotation cost/roadmap** | **Partial** | Reproducible image-bootstrap CIs and honest no-timing-log statement are strengths. No fabricated cost estimate. Missing expansion roadmap and CIs on all baseline rows; equivalence language still too strong. The plan's fallback to process description is justified, but its promise of full closure is premature. |
| **R2-2: VLM oracle advantage / detector asymmetry** | **Partial** | “Matched component priors” correctly fixes the premise: both controlled methods use GT boxes. Provisional detected-box geometry evidence is disclosed, but full per-image detector evidence and the matched detected-box VLM cell are absent; F7/F12 limit cost/equivalence claims. A complete 2×2 table is not necessary if missing cells are honestly stated, but cannot be claimed as completed. |
| **R2-3: SPICE title vs topological scope** | **Partial** | Same scope issue as R1-4. Explicit value clause helps; title/running heads remain unchanged. Stale committed PDF still promises simulation-ready output. Scope correction must reach title/abstract/intro/conclusion and actual deliverable PDF. |
| **R2-4: crossover misses and net merges** | **Partial** | Exposure and causal analysis are now real and largely independently confirmed, improving substantially on the plan's C66 suspicion. C242 is the supported case. No verified causal attribution of model misses; suppression trades FP for FN, and the manuscript still claims global short prevention. Disclosure without a new detector is justified; “single edge”/safe-fix implications and contradictory guarantees need correction. |
| **R2-5: insufficient ablation** | **Partial** | Genuine base/full module interventions now reproduce, so this is meaningful progress beyond a horse-race. Missing occlusion-off and a truly scale-off full pipeline; flag effects are overinterpreted and sign is reversed. The new table is clipped in the provided PDF. Zero effects are valid findings, not evidence that every mechanism has been credited. |
| **R2-6: one scalar within heterogeneous schematic** | **Satisfied narrowly** | Explicit one-scalar limitation and fixed clamps are present in Method (`build:106`, Access `:130`). This answers the requested discussion. The plan's extra dispersion-vs-F1 table/local-scale future-work proposal was not implemented; omission is defensible if no empirical robustness claim is attached. F11 still requires correcting reach definition and overclaiming. |

## 5. Exact checks, commands and outcomes

All commands below ran from `/home/claw/circuit-digitization-validation-20260907/repo`. `PYTHONDONTWRITEBYTECODE=1` prevented imports from writing bytecode through the symlinked environment/other checkouts; pytest cache was disabled. Scratch output was written only under `../notes/scratch/`. Existing data outside this workspace were read, not modified. No mutation of production parameters was made; in-memory interventions were confined to scratch audit scripts.

### Environment and history

`cat ../VALIDATOR_PROMPT.md` and ordered context reads; `git status --short`; `git log --all --format='%h %p %an %s' --author='Pranav\|tkprnv\|tk-pranav'`; `git show 30c020b`, `git show f8c2331`, `git show 22d6882 -- '*.tex'`, `git show 0a286d4`, `git show aab509e`; ancestry checks for equivalent commits; source/historical-body inspection. The initial sandbox read failed before permissions changed; all audit work continued after the user's updated environment allowed execution.

Environment values actually inherited:

```text
WIRE_GT_IMAGES=/home/claw/workspace/ground_truth/labels_few_annot/images
WIRE_GT_LABELS=/home/claw/workspace/ground_truth/labels_few_annot/labels/train/manually_verified_no_background_data/images
WIRE_HDC_BASE=/home/claw/circuit-digitization/roboflow_test2
.venv -> /home/claw/circuit-digitization/.venv
pdflatex=None; latexmk=None; tectonic=None
repo/models/component_detection/yolo26m_obb_16class_aug.pt: absent
```

### Tests and failure controls

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider > ../notes/scratch/pytest-default.txt 2>&1
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider wire_detection/tests/test_benchmark_experiment.py > ../notes/scratch/pytest-focus-default.txt 2>&1
env -u WIRE_GT_IMAGES -u WIRE_GT_LABELS -u WIRE_HDC_BASE PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider wire_detection/tests/test_benchmark_experiment.py > ../notes/scratch/pytest-focus-unset.txt 2>&1
WIRE_HDC_BASE=/home/claw/circuit-digitization-validation-20260907/notes/scratch/absent-labels PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m wire_detection.benchmark.join_eval_real_f1 --strategies scale_completion --out ../notes/scratch/empty-join.json > ../notes/scratch/empty-join-output.txt 2>&1
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check --no-cache wire_detection > ../notes/scratch/ruff.txt 2>&1
```

Actual outputs: **495 passed, 18 skipped in 17.81s**; focused **3 passed in 7.97s**; unset paths **1 failed, 2 passed in 4.55s**, `expected 0.9432, got 0.0`; empty join exits 0 with **0 images / micro-F1 1.000**; Ruff exits 1 with **157 errors**. “default” in the first two log filenames means inherited environment, not unset dataset variables. Those filenames must not obscure the path dependency.

AST parsing used `ast.parse(p.read_text(), filename=str(p))` for every `Path('wire_detection').rglob('*.py')`: **173 parsed successfully**. The same check saved ancestry and body diff in [source-checks.txt](scratch/source-checks.txt). This is a syntax check, not bytecode compilation or a substitute for runtime tests.

### Fresh real-data, wire, causal and statistical checks

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python ../notes/scratch/validate.py > ../notes/scratch/validate-output.txt 2>&1
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python ../notes/scratch/wire_and_ci.py > ../notes/scratch/wire-ci-output.txt 2>&1
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python ../notes/scratch/followup.py > ../notes/scratch/followup-output.txt 2>&1
```

- [validate.py](scratch/validate.py): validates aligned labels for all 31, source-pinned imports, aggregate artifact arithmetic, 6× base/full ablations, perfect-wire comparison, crossover exposure, final same-node two-pin assignments, and GT showcase counts. **All full baseline per-image counts match**. Output includes label SHA256s. This script reports CV descriptively; it does not claim a causal size-heterogeneity result.
- [wire_and_ci.py](scratch/wire_and_ci.py): **134 exact matches**, two current-parameter wire configs and all four Otsu variants; six CI entries reproduce exactly. Best Otsu **0.789353177**, all alternatives lower. Its exploratory paired-CI check initially used seed **12345**, producing slightly different bounds; this was an audit-script difference, not a repository defect.
- [followup.py](scratch/followup.py): resolves the wire discrepancy with historical **10/18** configs; recomputes paired CI using the implementation's actual **12346** seed, **exact match**; tests causal removal of documented type-2 crossing edges in three images. It constructs an in-memory graph-function copy for one union condition; shared component-assignment functions remain untouched. It makes no prediction about a deployable mitigation.

The Otsu plan disagreement is therefore resolved with fresh evidence: **keep 0.789 for the measured Otsu config; do not substitute 0.828**. The additional a16 config discrepancy must also be disclosed rather than calling every headline “bit-for-bit reproduced” under the mandated settings.

### Synthetic benchmark

The exact Python check, launched with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -` and redirected to [synthetic-output.txt](scratch/synthetic-output.txt), was:

```python
import json
from pathlib import Path
from wire_detection.synthgt.evaluate import compare_strategies
from wire_detection.synthgt.circuits import CATALOG
s = ['scale_completion', 'degree_budget', 'graph_rescue', 'graph_scale', 'production']
r = compare_strategies(s, CATALOG, seeds=8)
Path('../notes/scratch/synthetic-rerun.json').write_text(json.dumps(r, indent=2))
print('circuits', len(CATALOG), 'seeds', 8)
for row in r:
    print(row)
```

**15 circuits, 8 seeds**; L4: **0.948045031, 0.941589105, 0.898453583, 0.849734623, 0.363528694** respectively; clean score 1.0 for all five. This is join-only evaluation, **not** a fresh ngspice/current-equivalence validation.

### PDFs and source synchronization

```bash
pdftotext -layout paper/ieee-paper/paper-build.pdf ../notes/scratch/current-pdf.txt
pdftoppm -f 6 -l 6 -scale-to 1600 -png -singlefile ../context/01_review_materials/paper-build_MANUSCRIPT_2026-08-25.pdf ../notes/scratch/revision-page6 > ../notes/scratch/pdf-render.txt 2>&1
command -v pdflatex latexmk tectonic pdftotext
```

Extraction and rendering succeeded; page 6 was visually inspected. Only `pdftotext` is available among the four queried commands. Source body diff confirms synchronized substantive prose, with intentional concept-figure inclusion differences and a funding comment. Both clean sources still contain the unescaped example identifier fixed by the unapplied dirty patch. **No compilation success inferred from existing PDF files.**

## 6. Prioritized actions for Bosco

1. **Correct the scientific claims before packaging:** scope to topological/component-pair recovery and SPICE export with external values; qualify GT-box versus autonomous evidence; remove global no-shorts, equivalence and unsupported cost claims. Fix the ablation sign, reach definition/range and distinguish segment F1 from endpoint recall. These are evidenced prose corrections, not requests for a new model.
2. **Reconcile the exact wire config ledger:** 0.9755 is verified for 10°/18px; 12°/8px gives 0.9726 here. State which config each paper table, figure and join run uses. Preserve the verified Otsu 0.789. Do not silently retune production during this reconciliation.
3. **Finish reviewer-facing closure:** use the 12-row register above to write the missing concern/response/action document; explicitly address the citation suggestion. Correct the device-support description, provide the bounded expansion/process statement, and either supply missing robustness evidence or explicitly narrow the claims. Existing zero-effect results should be reported honestly.
4. **Make reproduction fail clearly and preserve provenance:** nonempty/expected sample-count assertions, strict coordinate matching, explicit dataset paths, model/core class contract, and source-pinned scripts. Before making the detected-box result definitive, retain per-image predictions/matches, model identity and inference settings and validate the metric. Label the learned branch in-sample unless given a held-out split. These actions are triggered by reproduced failures/code paths, not speculative refactoring.
5. **Treat crossover mitigation as an experiment, not a quick safe fix:** the observed suppression sacrifices TP. Retain the causal disclosure and, if implementing a mitigation, evaluate TP/FP/FN and terminal/net integrity before claiming improvement. The current headline does not need silent replacement merely because a disclosed limitation exists.
6. **Produce one coherent submission bundle after author verification:** confirm actual submitted byline, current names/affiliations/ORCIDs/bios and funding; resolve template metadata; incorporate the known TeX escape correction; rebuild both target layouts, repair the clipped table, inspect figures, and export matching clean/highlighted PDFs. The existing committed PDF is not the revised manuscript. Confirm author-only facts; do not automatically undo changes based on the incomplete snapshot comparison.

All supporting scratch scripts, outputs and the prior Phase 1 assessment are retained beside this report. Production findings were deliberately not fixed in this audit.

# Response to Reviewers

Original Manuscript ID: Access-2026-33821  
Original Article Title: “From Hand-Drawn Schematics to SPICE Netlists: A Deterministic Pipeline with Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark”  
Revised Article Title: “From Hand-Drawn Schematics to Structural Circuit Netlists: A Deterministic Pipeline with Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark”

Draft for author review. Final PDF page references, rendered response, figure reconciliation and submission-package approvals are pending; this source draft does not certify package readiness.

We thank the Associate Editor and reviewers for their assessment. We have narrowed the scientific claims, corrected descriptions to match the implementation, and qualified the existing evidence. Per-drafter results describe within-corpus variation. Component-pair scores do not certify pin-level correctness or simulation equivalence. No new experiments were run for this prose revision. The source changes and outstanding package checks are recorded in `REVIEW_CHANGES.md`.

## Reviewer 1

### Concern 1: Single corpus and benchmark size

**Reviewer’s concern.** Single dataset source and an extremely small manually verified benchmark: All experiments are carried out on the CGHD-1152 dataset only. The self-built human-verified benchmark merely contains 31 images with wide confidence intervals and insufficient coverage of sample distributions, which cannot prove that the proposed method can be universally adapted to various hand-drawing styles.

**Author response.** We agree that 31 images from one corpus do not establish universal or unseen-style generalization. The manuscript now presents the drafter groups as descriptive within-corpus results, discloses 16 direct and 15 inferred drafter assignments, and explicitly states that no held-out-drafter experiment was performed. The join micro-F1 0.890 has an existing 95% bootstrap CI of [0.855, 0.924]. Human correction and independently authored synthetic data mitigate, but do not eliminate, concern about residual bias in bootstrapped real labels. We describe a future stratified expansion protocol and do not claim that it has been completed.

**Author action.** Revised Abstract, Introduction, “Real-Image Net-Level Evaluation,” “Descriptive Per-Drafter Results” (Table `tab:per_drafter`), Discussion and Conclusion. Added the proposed sampling/annotation protocol and removed unseen-style and label-independence claims.

### Concern 2: Device capabilities

**Reviewer’s concern.** The algorithm only supports basic passive and active discrete components: Complex components such as transformers, thyristors and optocouplers can only be located, while their pin connection relationships cannot be extracted, limiting the range of component types supported by netlist generation.

**Author response.** We distinguish evaluated component-pair connectivity, geometric pin construction and illustrative export. The benchmark includes R/C/L/D/Q, voltage-source and IC groups, but this does not validate universal device-specific pin templates. Some complex types have generic geometry or fallback pins; their electrical pin semantics remain unvalidated. The detector merges original classes, so listing a group is not evidence that it is separately detected. A switch can be exported as a 0.001-ohm resistor when two distinct nodes are available; ICs lack a supported export model. Unsupported primitives may be omitted or substituted. Component-pair F1 discards terminal identity and does not certify pin assignment, exact net partition, absence of shorts or simulation equivalence.

**Author action.** Replaced the blanket “pins not extracted/excluded from emission” statement with the four-column capability table (`tab:capabilities`), including a metric-boundary row. Clarified output and evaluation scope in the Abstract, Pipeline Overview, metric definition and Conclusion.

### Concern 3: Manual thresholds and extreme sizes

**Reviewer’s concern.** Reliance on manual tuning of fixed scale-relative thresholds: Hyperparameters including τ_join, τ_t and α need to be manually configured according to the median diagonal length of circuit components. Without an adaptive parameter learning mechanism, the detection accuracy tends to decline when processing circuits of extreme sizes.

**Author response.** The multipliers are fixed and manually configured, not learned: pin/join/T tolerances use 0.62/0.30/0.20 times the component scale, clamped to 24–60/11–28/8–20 pixels. Directional scoring has alpha 0.35 and is used only in the fallback pin search when no component is assigned; the score is d[1−0.35 max(0, cos(theta))] for nonzero distances above the implementation cutoff. Completion reach is four times the clamped pin scale. Its existing reach-factor sweep from 3 to 5 yields macro-F1 0.895–0.903 on this benchmark. Fixed-pixel base tolerances score 0.820 versus 0.816 for the scale-relative base; completion remains scale-dependent. These results do not establish robustness to extreme image sizes or heterogeneous symbol sizes. Controlled image rescaling was not evaluated.

**Author action.** Rewrote the Endpoint-Graph Join Model and Degree-Budget Completion descriptions from the implementation; corrected the reach unit, sweep range and fixed-pixel interpretation in `tab:edge_ablation` and its discussion. Retained the mixed-size limitation.

### Concern 4: Values and simulation-ready output

**Reviewer’s concern.** Lack of a closed-loop framework for component value recognition: The pipeline only reconstructs topological connections of circuits without integrating OCR to identify parameters of resistors, capacitors and voltage sources, so it cannot directly export complete simulation netlists that can be imported into SPICE.

**Author response.** We agree that image-derived values and device models are required for faithful simulation and are outside the evaluated task. The revised title says “Structural Circuit Netlists.” The manuscript describes inferred pin-to-node output and illustrative SPICE export, requiring external values and device models; real-scan simulation equivalence is not validated. Export substitutions and unsupported primitives are disclosed. Component-pair connectivity does not certify a simulator-ready or pin-correct reconstruction. Simulation results for authored synthetic circuits remain separately scoped.

**Author action.** Revised title/running heads, Abstract, Introduction, Pipeline Overview, metric definition, capability table, Discussion and Conclusion. Removed the related-work implication that our real scans were validated by LTspice. Corrected the pipeline TikZ output-node text; the Access figure PDF remains pending regeneration in the later build phase.

### Concern 5: Dense buses and crossing complexity

**Reviewer’s concern.** Inability to handle complex circuits with multi-layer crossings and dense buses: The test samples adopted in this paper are dominated by simple topologies with 3 to 6 components. No dedicated verification is conducted for circuits with high-density multi-track buses and multi-layer crossed wiring, leading to a significant drop in recall on complex circuits.

**Author response.** The benchmark contains 3–14 components per image in the evaluated electrical subset (median 7): 15 images have at most five and 12 have at least ten. These are electrical-subset counts, not total detected objects or proof of support for all device types. Component-count breadth does not validate dense buses or multilayer crossings; their performance remains untested. The separately reported annotated-box crossover intervention illustrates a joining failure and a precision/recall tradeoff, not dense-bus validation or a safe mitigation.

**Author action.** Replaced the rebuttal-style complexity caption (`fig:complexity_hist`) with descriptive counts and the explicit coverage limitation. Narrowed the crossover Discussion and Conclusion. Preserved the existing histogram asset.

### Concern 6: Suggested references

**Reviewer’s concern.** It is suggested that the authors cite two papers in the sections related to SPICE simulation of memristive analog circuits: "A Memristor-Based Neural Network Circuit with Classical Conditioning and Fear Generalization" and "Biologically Plausible Memristive Decision-Making Circuit for Adaptive Control in Industrial Autonomous Navigation". Both papers complete full SPICE netlist modeling and simulation verification for memristive circuits, which complement the EDA technical route of converting hand-drawn schematics to SPICE netlists proposed in this paper in application scenarios, and can enrich relevant literature support for digital parsing and simulation deployment of analog memristive circuits.

**Author response.** We respectfully did not add “A Memristor-Based Neural Network Circuit with Classical Conditioning and Fear Generalization” or “Biologically Plausible Memristive Decision-Making Circuit for Adaptive Control in Industrial Autonomous Navigation.” Based on the application and SPICE-simulation context described in the recommendation, these references do not strengthen the present comparison of image-based connectivity extraction. Our narrowed task does not evaluate memristive-circuit simulation deployment. This relevance decision does not assert that we reviewed the full papers.

**Author action.** No citation added; relevance rationale supplied here.

## Reviewer 2

### Concern 1: Statistical reliability and expansion

**Reviewer’s concern.** The scale of the human-verified benchmark is insufficient, casting doubt on the statistical reliability of the conclusions. The evaluation in this paper covers only 31 images. The authors should explicitly clarify the annotation cost and provide a roadmap for dataset expansion, or alternatively supply additional support through more rigorous statistical testing. If 31 images represent the entirety of currently available data, the wording of the conclusions should be made considerably more conservative.

**Author response.** We retain the existing bootstrap intervals and explicitly limit conclusions to 31 images from one corpus. Annotation was performed by one human annotator without per-image timing logs, so we cannot report a measured annotation-cost figure. The proposed expansion protocol stratifies by component count, drafter, crossing/bus structure and capture conditions, uses independent annotation followed by adjudication, and records per-image effort and provenance. It is future work, not completed collection. A confidence interval containing zero is not evidence of equivalence, and synthetic corroboration does not exclude residual real-label bias.

**Author action.** Revised the Abstract, real-image evaluation, VLM diagnostic, Discussion and Conclusion; added the future expansion protocol without inventing timing or sample-size commitments.

### Concern 2: Conditional VLM comparison

**Reviewer’s concern.** There is a fundamental fairness issue in the VLM comparison experiment. The VLM enjoys an "oracle advantage" with respect to critical prior information, whereas the geometric pipeline must bear the burden of detection errors. In the paper, the VLM is provided with ground-truth annotated component bounding boxes; under such conditions, the fact that the VLM still shows no statistically significant difference from the geometric method does not sufficiently support the conclusion that "the geometric method is superior in terms of cost and structural validity."

**Author response.** We correct the experiment's scope and the prior superiority claims. Both methods receive the same annotated component boxes; the geometric method uses detected wires. This is an oracle-component-box connectivity diagnostic, not an autonomous end-to-end comparison. The VLM scores component-pair micro-F1 0.923 versus 0.890, and is exact under that metric on 21/31 images. The paired VLM-minus-join difference is +0.033 with 95% CI [−0.009, +0.078], which does not establish equivalence. We make no comparative cost-superiority or global short-free guarantee. The provisional autonomous numeric paragraph has been removed because its prediction/matching provenance is not sufficiently auditable for this submission draft.

**Author action.** Replaced the VLM section and Introduction comparison; revised Abstract, real-join caption (`fig:real_join_fig`), Discussion and Conclusion. Removed cost/token multiples, free-form-output criticism, equivalence language, autonomous bottleneck claims and global structural guarantees.

### Concern 3: Title and measured output

**Reviewer’s concern.** The paper title claims to generate SPICE netlists, yet the paper explicitly acknowledges that it "makes no attempt to read component values." This implies that the current system outputs a topological netlist rather than a simulatable SPICE netlist, which constitutes a notable discrepancy with the claims made in both the title and the abstract.

**Author response.** The title is now “From Hand-Drawn Schematics to Structural Circuit Netlists: A Deterministic Pipeline with Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark.” We distinguish the pin-to-node representation produced from component-pair connectivity evaluated. The latter discards terminal identity and does not certify exact pin assignments, net partitions, shorts or simulation equivalence. External values and device models are required for illustrative SPICE export, and real-scan simulation equivalence remains unvalidated.

**Author action.** Applied the title and both running-head arguments in both manuscript sources. Added the metric boundary to the Abstract, Introduction, Pipeline Overview, metric definition, capability table and Conclusion.

### Concern 4: Crossover recognition and false merges

**Reviewer’s concern.** The impact of low recall in a critical component category on netlist correctness has not been sufficiently analyzed. The recall of the crossover class in component detection is only 70.7%, substantially lower than that of other categories. Misclassification of crossovers will introduce systematic errors in electrical connectivity, causing two wire segments that should remain electrically independent to be erroneously merged into the same net.

**Author response.** The 70.7% crossover recall identifies a detector-category weakness, but the join-isolation evaluation uses annotated boxes and does not measure the effect of detector misses or misclassifications on autonomous netlists. We therefore provide a conditional joining failure analysis rather than attributing observed false pairs to detector recall. The audit contains 13 annotated crossovers in eight images. In C242_D1_P1, suppressing two crossing-adjacent endpoint–endpoint edges changes TP/FP/FN from 27/4/0 to 19/0/8. Removing the four false pairs also loses eight true pairs; this is not a demonstrated mitigation gain or a prevalence estimate. The requested detector-error effect remains empirically unmeasured, so this is a partial analysis of the failure pathway.

**Author action.** Replaced the single-edge, rarity and safe-suppression interpretation in Discussion with the full two-edge tradeoff and its annotated-box boundary. Explicitly retained the unresolved detector-miss effect; no mitigation or new detector experiment is claimed.

### Concern 5: Ablation coverage

**Reviewer’s concern.** The ablation study is severely insufficient.

**Author response.** We report the existing base-graph/full-pipeline interventions for T-junctions, rail taps, directional preference and base tolerance scaling. Several base rows tie; fixed-pixel base tolerances score 0.820 versus 0.816. Every full-pipeline row has aggregate TP/FP/FN 418/37/66. These ties neither establish identical recovered connections nor prove that completion masks differences. The baseline comparison improves from 0.816 to 0.890 with completion, but the ablations do not establish that other mechanisms are generally unnecessary. Full occlusion removal and removal of scale dependence throughout completion were not tested. This is bounded ablation evidence, not complete coverage of all proposed modules.

**Author action.** Corrected `tab:edge_ablation` caption/row label and interpretation; removed activation/identical-connection explanations and the unsupported quantified occlusion benefit. Rewrote the method description to distinguish graph selection, mandatory slot/dummy assignment and guarded application. Table layout verification remains for T7.

### Concern 6: Mixed component sizes

**Reviewer’s concern.** The setting of τ = k·s may fail when component sizes within a single schematic vary substantially, and no relevant discussion addressing this limitation is provided.

**Author response.** We now explicitly state that one scalar per image does not model intra-image size variation, including schematics mixing a large IC with small discrete symbols. Pixel clamps bound tolerances but do not establish adaptation to heterogeneous symbols. The fixed-pixel ablation changes the base graph only; completion retains its clamped scale dependence. A controlled mixed-size or rescaling experiment was not performed.

**Author action.** Retained and clarified the mixed-size limitation in the Endpoint-Graph Join Model, specified completion's scale rule, and scoped the reach sweep and ablation interpretation accordingly.

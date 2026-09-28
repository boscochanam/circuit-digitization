# Response to Reviewers

**Manuscript ID:** Access-2026-33821

**Original title:** From Hand-Drawn Schematics to SPICE Netlists: A Deterministic Pipeline with Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark

**Revised title:** From Hand-Drawn Schematics to Structural Circuit Netlists: A Deterministic Pipeline with Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark

Dear Editor,

We thank the editor and both reviewers for their careful reading. The comments identified real weaknesses, and addressing them has changed the paper substantially. The main changes are:

1. **A second, independent benchmark** (Section V-D, Table 6): 164 held-out photographs from 24 of the 25 CGHD drafters. Its reference nets are derived from the CGHD authors' own stroke-segmentation maps and symbol polygons, not from our method, and its images were not used to develop or tune the join. The reference agrees with our human-verified nets at micro-F1 0.939 on the 17 images the two sets share. A human audit of 22 of 40 randomly drawn held-out images confirms the reference: against the human-corrected nets it scores micro-F1 0.998 (exact on 21 of 22 images, no false pairs). The audit tool presented the images in order of size, so the 22 checked are mostly the smaller circuits (median 6 electrical components, against 16 for the 18 unchecked).
2. **Paired significance testing** (Section IV-C; Tables 5 and 6): image-level bootstrap and sign-flip permutation tests on both benchmarks, plus Wilcoxon tests on the human-verified set, all with Holm correction.
3. **End-to-end evaluation with our trained component detector** (Section V-G, Table 10), with the loss decomposed into missed, spurious, mislocalized and misclassified components.
4. **Robustness experiments** (Section V-E): complexity strata on both benchmarks (Table 7), within-image component-size analysis, controlled rescaling from 0.35x to 3x (Fig. 8), and a synthetic mixed-size test that exposes one failure case.
5. **A corrected title and scope**: the paper now claims structural netlists only, and states once, in a single Scope and Limitations subsection (VI-A), what the method and metric do not cover.

During the revision we also found and corrected several errors of our own relative to the submitted manuscript, all disclosed in the revision:

- **Image provenance.** The description was incomplete: the 704×704 benchmark copies are non-aspect-preserving resizes, 14 of the 31 are re-oriented relative to the CGHD files, and 16 of the 31 are CGHD's binary stroke maps rather than photographs (Section IV-A). The results do not depend on modality (Sections V-B and V-C).
- **Wire-detection score.** The submitted manuscript labelled the 0.976 wire-detection F1 as our configuration. That score belongs to the best of 36 variants; the extractor used in all experiments scores 0.973. Table 4 now lists both, with the deployed row marked.
- **Join description.** Section III now describes the join as implemented. Within the assigned component, an endpoint takes the nearest pin; the submitted text said the side was chosen by the box's aspect ratio. Each endpoint binds to at most one pin, and the directional score applies only in the fallback pin search, not to every endpoint-to-pin edge. The completion reach is 4τ_pin with τ_pin clamped to 24–60 px, not 4s. The code that produced every reported number is unchanged.
- **Fig. 2 counts.** The caption gave 36 wires and 12 nets for the left circuit and 12 wires for the right one; the generator's output has 35 wires and 7 nets, and 11 wires.
- **Complexity analysis.** The submitted text described only a weak correlation between F1 and circuit size (r = −0.19). The revised analysis finds Spearman ρ = −0.53 (p = 0.002) between our per-image F1 and component count, with a recall drop from the smallest to the largest stratum that is not significant (Section V-E).

Section, table and figure numbers below refer to the revised manuscript. A highlighted version marks all changes.

Sincerely,

Bosco Chanam (corresponding author), on behalf of all authors

---

## Reviewer 1

### Comment 1.1: Single corpus and benchmark size

> Single dataset source and an extremely small manually verified benchmark: All experiments are carried out on the CGHD-1152 dataset only. The self-built human-verified benchmark merely contains 31 images with wide confidence intervals and insufficient coverage of sample distributions, which cannot prove that the proposed method can be universally adapted to various hand-drawing styles.

**Response.** We agree that 31 images from ten drafters could not support conclusions about drawing styles in general. We have added a second real-image benchmark built to remove the three weaknesses of the first. It is larger (164 images, 3874 reference component pairs), it covers 24 of the 25 CGHD drafters, and its reference nets come from the CGHD authors' own annotations rather than from a join like ours. We validated the derived reference against our human-verified nets on the 17 images the two sets share (micro-F1 0.939, precision 0.993). A human audit of 22 of 40 randomly drawn held-out images then found the reference exact on 21 of them (micro-F1 0.998 against the corrected nets), and on those 22 images our join (0.803) leads every baseline against the human labels. The audit tool listed the images in order of size, so the 22 checked are mostly the smaller circuits (median 6 electrical components, against 16 for the 18 unchecked); the 17-image validation above has more circuits with at least ten electrical components (9 of 17, against 5 of 22). The join was not developed or tuned on these images. The extractor settings were chosen earlier on the wire benchmark, which includes resized copies of 25 of the held-out images. Excluding those 25 images gives 0.709 [0.663, 0.751] on 139 images, and excluding every photograph of their drawings gives 0.704 on 123 images; in both cases our join still ranks first and every margin has a CI above zero.

On this held-out set, our join reaches micro-F1 0.711 [0.671, 0.748] and beats every deterministic comparator, with Holm-adjusted p < 0.001 for each (Table 6). Its margin over the strongest comparator, the prior completion variant, is +0.053 [+0.033, +0.074]. Per-drafter micro-F1 ranges from 0.465 to 0.917 (median 0.709), and our join is the best evaluated method for 15 of the 24 drafters. The absolute score is lower than on the 31-image set. The 31 images were sampled by circuit content and size, not appearance, but they happen to have mostly plain backgrounds, and half of their benchmark copies are clean stroke maps; the held-out photographs include grid paper and cluttered backgrounds. We traced most of the gap to these input photographs: CGHD provides stroke maps for exactly this subset, and the benchmark copies of these drawings are mostly those clean maps. On the photographs themselves, wire extraction is the main source of error. Input quality does not explain the whole gap: with stroke maps as input, our held-out score is 0.775, and we attribute part of the residual to having selected our configuration on the 31 images (Section V-D, "Gap to the human-verified benchmark"). On both benchmarks our join ranks first and the endpoint-graph variants keep their order.

All images still come from CGHD. The Scope and Limitations subsection states this, and the expansion plan there extends the evaluation to other corpora and to printed schematics.

**Changes.** New Section V-D and Table 6; per-drafter spread in V-D; datasets in IV-A; limitations in VI-A.

### Comment 1.2: Complex devices

> The algorithm only supports basic passive and active discrete components: Complex components such as transformers, thyristors and optocouplers can only be located, while their pin connection relationships cannot be extracted, limiting the range of component types supported by netlist generation.

**Response.** The reviewer is correct. Connectivity is evaluated for resistors, capacitors, inductors, diodes, transistors, sources and integrated circuits. For transformers, thyristors and optocouplers, the pipeline has only geometric pin templates, which are not validated, and no export model. Table 12 now states what is evaluated, how pins are constructed and what is exported for each device group, and Section VI-A lists complex devices as a limitation. We also extended the scoring on the held-out benchmark (Section V-D, "Scoring conventions"): with switches, potentiometers, photoresistors, fuses, lamps, varistors, crystals, speakers and microphones added to the scored set, our join scores 0.709 and still leads every baseline (+0.055 [+0.036, +0.077] over the strongest). Treating switches as closed, or merging all ground symbols into one node, leaves the ranking unchanged. The component-pair metric does not check which terminal of a device is used. Validating device-specific terminal semantics needs pin-level ground truth, which neither CGHD nor our benchmarks provide. We name it as future work rather than claim it.

**Changes.** New Table 12; extended scoring in Section V-D; Section VI-A.

### Comment 1.3: Hand-set thresholds and extreme sizes

> Reliance on manual tuning of fixed scale-relative thresholds: Hyperparameters including τ_join, τ_t and α need to be manually configured according to the median diagonal length of circuit components. Without an adaptive parameter learning mechanism, the detection accuracy tends to decline when processing circuits of extreme sizes.

**Response.** Two clarifications, then new evidence. First, the multipliers and clamps are fixed once for all images. No per-image tuning is needed: the scale s is computed automatically from each image's component boxes, and each endpoint is bound to a component within a radius that grows with that component's own diagonal (Section III-C). Second, we have now tested extreme sizes directly. We resampled all 31 images by factors from 0.35 to 3 (Section V-E, Fig. 8).

- **With annotated wires,** our join stays within ±0.005 of its native micro-F1 from 0.5x to 3x, with every CI including zero. It drops only at 0.35x (−0.035), where the lower pixel clamps bind.
- **The fixed-radius legacy rule** falls from 0.690 to 0.153 at 3x.
- **In the full pipeline,** upscaling costs at most 0.024. Downscaling loses accuracy because the extractor's Sauvola window and minimum-area parameters are in pixels; the join is not the cause.

We also ran the same algorithm with fixed pixel tolerances. It stays within 0.016 of the scale-relative version between 0.5x and 2x. So most of the scale robustness comes from component-relative endpoint assignment and completion, and the paper now credits them accordingly. The paper also states that the clamps are tuned to native resolution. Learning the tolerances would be a different method that needs training data this task does not have. We list resampling inputs to a nominal component size, and scale-aware extraction parameters, as next steps.

**Changes.** Section III-C (component-relative assignment); new "Controlled rescaling" in V-E and Fig. 8; Section VI-A.

### Comment 1.4: Component values and simulation-ready output

> Lack of a closed-loop framework for component value recognition: The pipeline only reconstructs topological connections of circuits without integrating OCR to identify parameters of resistors, capacitors and voltage sources, so it cannot directly export complete simulation netlists that can be imported into SPICE.

**Response.** We agree, and we have narrowed the claim to match the contribution. The title now reads "Structural Circuit Netlists". The introduction states that value and device-model recognition is out of scope. The SPICE export is described as illustrative, using placeholder values, and simulation of real scans is not claimed. Recognizing values with OCR and linking them to components is a separate problem with its own evaluation. Adding an unvalidated OCR stage would add an error source without evidence, so we leave it to future work. The simulation-accuracy results remain, but only for synthetic circuits with authored values (Section V-A).

**Changes.** Title and running heads; Abstract; Section I; Section VI-A.

### Comment 1.5: Dense buses and crossing complexity

> Inability to handle complex circuits with multi-layer crossings and dense buses: The test samples adopted in this paper are dominated by simple topologies with 3 to 6 components. No dedicated verification is conducted for circuits with high-density multi-track buses and multi-layer crossed wiring, leading to a significant drop in recall on complex circuits.

**Response.** The 3–6 component range applies to the synthetic suite only. The real benchmarks are larger: the 31 human-verified images contain 3–14 electrical components (median 7; 12 images have at least ten), and the held-out benchmark contains circuits with 20 or more. Table 7 now splits both benchmarks by component count.

- **Correction.** The submitted manuscript described only a weak correlation between F1 and circuit size (r = −0.19). The revised analysis finds a stronger one: our per-image F1 correlates with component count at Spearman ρ = −0.53 (p = 0.002).
- **On the 31 images,** our recall falls from the ≤5 to the ≥10 stratum by −0.068 [−0.18, +0.05], which is not significant (p = 0.32). F1 falls with complexity for every method, including the VLM.
- **On images with at least ten components,** our join beats the prior completion variant, the scale-relative base and Hough linking by +0.078 to +0.106, with CIs excluding zero.
- **On the held-out benchmark,** our micro-F1 falls from 0.845 (≤5 components) to 0.693 (≥20), and our recall is 0.773, 0.741, 0.664 and 0.623 in the ≤5, 6–9, 10–19 and ≥20 strata. F1 falls with circuit size for every method except connected-component tracing, whose low recall rises on the larger circuits (F1 0.519 to 0.655). On the smallest circuits the prior completion variant is slightly ahead (0.856), but on circuits with 20 or more components our join leads it by 0.085, and Hough linking falls to 0.347.

For crossings, Section V-H analyzes the 13 annotated crossovers, including the end-to-end run with the detector. We did not evaluate dense multi-track buses or multi-layer crossings; neither benchmark contains enough of them, and Section VI-A says so.

**Changes.** New Table 7 and "Circuit complexity" in V-E; Section V-H; Section VI-A.

### Comment 1.6: Suggested references

> It is suggested that the authors cite two papers in the sections related to SPICE simulation of memristive analog circuits: "A Memristor-Based Neural Network Circuit with Classical Conditioning and Fear Generalization" and "Biologically Plausible Memristive Decision-Making Circuit for Adaptive Control in Industrial Autonomous Navigation". [...]

**Response.** We thank the reviewer. Both works are now cited in Related Work, as examples of SPICE-level modeling in neighboring hardware domains.

**Changes.** Section II; references for both works (Gao et al., IEEE Trans. Consumer Electronics, 2026; Gao et al., IEEE Trans. Industrial Informatics, vol. 22, 2026).

---

## Reviewer 2

### Comment 2.1: Statistical reliability, annotation cost and expansion

> The scale of the human-verified benchmark is insufficient, casting doubt on the statistical reliability of the conclusions. The evaluation in this paper covers only 31 images. The authors should explicitly clarify the annotation cost and provide a roadmap for dataset expansion, or alternatively supply additional support through more rigorous statistical testing. If 31 images represent the entirety of currently available data, the wording of the conclusions should be made considerably more conservative.

**Response.** We have taken all three routes the reviewer offers.

*More rigorous testing.* Every comparison is now paired over images, with an image-level bootstrap (10,000 resamples), a sign-flip permutation test and a Wilcoxon signed-rank test, all with Holm correction (Section IV-C). On the 31 images, our join beats every deterministic comparator on every test (Table 5). For example, it beats the prior completion variant by +0.061 [+0.025, +0.100] and Hough linking by +0.086 [+0.045, +0.127]. Leaving out any one image keeps our micro-F1 within 0.885–0.900 and changes the sign of no comparison.

*More data.* The new held-out benchmark (164 images, 24 drafters, Comment 1.1) repeats the comparison on data not used for development. Every margin remains significant there (Table 6).

*Annotation cost and roadmap.* No timing log was kept for the original 31 images, so we cannot report their cost. For the held-out audit, the verification tool records a timestamp at every save: checking and correcting one image took a median of 77 s (mean 123 s) over 20 timed saves. Because the tool proposes nets from the derived reference, a larger human-verified benchmark is now inexpensive to build. Section VI-A gives the expansion plan:

- sampling stratified by component count, drafter, crossing and bus structure, and capture conditions;
- two annotators per image, with disagreements adjudicated;
- other corpora and printed schematics.

We also made the conclusions more conservative where the data require it. The VLM comparison is reported as the tests show it, not as a tie (Comment 2.2).

**Changes.** Section IV-C; Tables 5 and 6; Section V-D; Section VI-A.

### Comment 2.2: Fairness of the VLM comparison

> There is a fundamental fairness issue in the VLM comparison experiment. The VLM enjoys an "oracle advantage" with respect to critical prior information, whereas the geometric pipeline must bear the burden of detection errors. In the paper, the VLM is provided with ground-truth annotated component bounding boxes; under such conditions, the fact that the VLM still shows no statistically significant difference from the geometric method does not sufficiently support the conclusion that "the geometric method is superior in terms of cost and structural validity."

**Response.** We agree that the conclusion the reviewer paraphrases was not supported. The submitted manuscript stated that our join is "statistically indistinguishable from the VLM on these circuits while being deterministic, two to three orders of magnitude cheaper, and structurally valid by construction: the self-loop guard guarantees that no two-terminal component is emitted shorted", and the Conclusion repeated that the VLM works "at two to three orders of magnitude higher cost and without structurally valid output". We have removed both statements, along with every cost and structural-validity comparison. The structural guarantee was also wrong: the guard only rejects completion merges between nets that already share a component, and it does not repair same-component merges made by the base graph (Section VI-A).

The submitted text also misdescribed the inputs. It said the VLM "is given exactly what the join receives". That was inaccurate. The VLM received the annotated electrical-component boxes, drawn on the image and numbered, without class labels. Our join received the same boxes with their classes, plus the annotated junction, terminal, ground and crossover boxes. Neither received annotated wires: our join worked from its own extracted wires, and the VLM read the wires from the image. The VLM was run on the human-verified benchmark only. Section V-I now states this at the outset.

The comparison is now reported in full (Section V-I, Table 5):

- **Pooled pairs:** our join trails the VLM by −0.033 [−0.078, +0.008], which is not significant (Holm-adjusted p = 0.12).
- **Per image:** the VLM is significantly better (13 wins, 11 ties, 7 losses; Wilcoxon p = 0.030).

We present the VLM as a reference system, not as a method we match or surpass. The two systems also differ in their requirements. The VLM requires a call to a proprietary model for every image. Our join runs locally and deterministically without connectivity training data, and every connection it reports can be traced to a wire segment or a completion edge.

To address the detection burden directly, we added an end-to-end evaluation in which our trained detector supplies the components (Section V-G, Table 10). End-to-end micro-F1 is 0.627 [0.519, 0.731], against 0.890 with annotated boxes. Replacing the boxes one factor at a time attributes −0.131 to missed components, −0.072 to spurious detections, −0.043 to box localization and −0.017 to classification. Missed components cost the most because every pair involving a missed component is lost. The benchmark images were probably in the detector's training split, so this estimate is optimistic for detection, and Section VI-A states so.

**Changes.** Section V-I (rewritten); new Section V-G and Table 10; Abstract; Section VI.

### Comment 2.3: Title versus output

> The paper title claims to generate SPICE netlists, yet the paper explicitly acknowledges that it "makes no attempt to read component values." This implies that the current system outputs a topological netlist rather than a simulatable SPICE netlist, which constitutes a notable discrepancy with the claims made in both the title and the abstract.

**Response.** We agree. The title now reads "From Hand-Drawn Schematics to Structural Circuit Netlists", and the abstract, introduction, running heads and pipeline figure describe the output as a structural netlist that maps component pins to electrical nodes. Section IV-B defines the component-pair metric and states that it ignores terminal identity. Section VI-A adds that export is illustrative and that simulation of real scans is not evaluated. The word "SPICE" no longer describes our evaluated output.

**Changes.** Title; running heads; Abstract; Sections I, III-A, IV-B and VI-A; Fig. 1.

### Comment 2.4: Crossover recall and false merges

> The impact of low recall in a critical component category on netlist correctness has not been sufficiently analyzed. The recall of the crossover class in component detection is only 70.7%, substantially lower than that of other categories. Misclassification of crossovers will introduce systematic errors in electrical connectivity, causing two wire segments that should remain electrically independent to be erroneously merged into the same net.

**Response.** The reviewer describes a real pathway: three of our edge rules do not consult crossover labels, so an undetected crossover can merge two independent wires. We now measure it three ways (Section V-H).

1. **With annotated boxes:**
   - Images containing crossovers have recall 0.834, against 0.884 without (p = 0.51).
   - Deleting all crossover annotations before joining changes predictions on 6 of the 8 crossover images and raises micro-F1 slightly (+0.010).
2. **In one case study (C242_D1_P1),** suppressing the crossing-adjacent edges removes four false pairs but also eight true ones. A simple suppression rule is therefore not a fix.
3. **In the new end-to-end run,** the trained detector found and correctly labeled all 13 crossovers in the benchmark at every tested threshold, so none of the false pairs in Table 10 comes from a missed or misclassified crossover. These images were probably in the detector's training split, so this is not a held-out estimate of crossover recall.

Section III-B reports the detector's per-class recall: crossover recall (70.7%) is 12.4 points below the next lowest class (vss, 83.1%). Thirteen instances cannot test the 70.7% validation recall. On this benchmark, crossover detection is not the limiting factor; missed electrical components and wire extraction are. We state this scope in Section VI-A and do not claim a mitigation.

**Changes.** Section III-B (detector and per-class recall); new Section V-H; Section VI-A.

### Comment 2.5: Ablations

> The ablation study is severely insufficient.

**Response.** The revision adds the following experiments.

- **Mechanism ablations** (Table 9):
  - Removing only the occlusion step drops micro-F1 from 0.890 to 0.336, and predictions change on all 31 images.
  - Requiring a wire witness for every completion edge lowers micro-F1 to 0.884.
  - The shared-component guard fires on 18 images and rejects 38 merges. Those merges would join two pins of one component, which the pair metric cannot see, so the score is unchanged.
- **Tolerance design** (Section V-E): the fixed-pixel and unclamped variants are evaluated across seven image scales. They separate the contribution of scale-relative tolerances from that of component-relative assignment and completion.
- **Mixed component sizes** (Section V-E): a synthetic test that also documents a failure case.
- **End-to-end decomposition** (Table 10): the cost of each detector error type.
- **Edge-rule ablation** (new Table 8): disabling T-junction, rail-tap or directional rules leaves the counts unchanged, so these rules give no measurable gain on this benchmark.

**Changes.** Tables 8, 9 and 10; Section V-E; Section V-F.

### Comment 2.6: Mixed component sizes

> The setting of τ = k·s may fail when component sizes within a single schematic vary substantially, and no relevant discussion addressing this limitation is provided.

**Response.** We now analyze this directly (Section V-E, "Component-size variation within an image" and "Synthetic mixed-size circuits").

- **On the 31 real images:** the overall dispersion of component sizes is unrelated to F1 (ρ = +0.18, p = 0.33). The largest-to-smallest size ratio correlates with lower F1, but it also rises with component count. After controlling for count, the partial correlation is −0.41 (p = 0.024) for our join, a significant effect (−0.34 for the VLM, p = 0.064). Size heterogeneity therefore does lower accuracy somewhat, while the size of the largest component relative to s shows no effect.
- **In synthetic circuits with one component redrawn at 0.5x, 2x or 3x its size,** enlarging a component costs about 0.005 and shrinking one costs 0.012.
- **The reviewer's concern holds in one case:** a Wheatstone bridge with one very small arm. There, the median-derived tolerances add a spurious pair even on clean wires, while fixed-pixel graphs stay exact.

The component-first assignment already scales with each component's own diagonal (Section III-C), which explains why most cases are unaffected. Section VI-A lists the small-component case as a limitation.

**Changes.** Section III-C; Section V-E (two new parts); Section VI-A.

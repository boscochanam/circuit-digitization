# Manuscript rewrite spec — final resubmission (Access-2026-33821)

> **Label correction, 2026-10-05.** Four images of the 31-image human-verified benchmark were corrected (plain crossings are not connections; C112, C242, C66, C15). Numbers in this file that depend on the 31-image nets predate the correction; the current values (e.g. ours 0.884, VLM 0.946, end to end 0.602, reference vs human 0.971) are in `docs/research/experiments/SUMMARY.md` (Revision 2) and the paper. Regenerated JSON next to this file is current.

Status: 2026-09-28. Source of truth for every number added in this revision. All values
trace to `docs/research/experiments/revision2/*` (committed). Supersedes the defensive
framing doctrine in `paper/ieee-paper/AGENTS.md` (author decision 2026-09-28): keep every
claim honest, but state each limitation once, in one Limitations subsection, and lead with
contributions and evidence.

## Editorial principles

1. Confident, precise, plain. No "does not establish X, Y, Z" tails on every paragraph.
   One consolidated "Scope and Limitations" subsection carries the caveats.
2. Never overclaim: no simulation-ready claims, no equivalence from a non-significant test,
   no global short-free guarantees, no autonomous-accuracy claims beyond the measured e2e.
3. Every reviewer concern gets substantive evidence in the paper (see mapping at bottom).
4. Title stays: "From Hand-Drawn Schematics to Structural Circuit Netlists: A Deterministic
   Pipeline with Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark".
   (Optionally "...and Human-Verified and Independent Connectivity Benchmarks" — do NOT change;
   keep the locked title.)
5. Keep `paper-access.tex` and `paper-build.tex` bodies identical (only preamble/front matter
   and the three concept-figure includes differ: Access uses the PDFs, build uses TikZ \input).
6. Don't touch author names, affiliations, ORCIDs, bios, funding.
7. Target length: roughly the current length (Access ~12 pages). Add the new sections, pay for
   them by deleting repeated disclaimers and redundant prose.

## Structure

- Abstract (≤250 words, one paragraph, IEEE Access style, no citations/abbrev soup).
- I Introduction — problem, why joining is hard, contributions as a numbered list (4 items):
  (1) occlusion-first extractor producing an endpoint representation;
  (2) typed endpoint-graph join + degree-budget completion;
  (3) two real-image connectivity benchmarks: 31 human-verified images + an independent
      164-image held-out benchmark derived from CGHD's own stroke/polygon annotations (24
      drafters), [+ 40-image human audit — placeholder `\AUDITRESULT` until the user finishes];
  (4) an evaluation protocol: paired significance testing, complexity/scale robustness,
      end-to-end with a trained detector, and a VLM reference under identical component inputs.
  One sentence of scope: structural connectivity; component values/device models are out of scope.
- II Related Work — keep content; trim; keep Gao memristor citations (R1-6).
- III Method — keep; delete hedges. Add one sentence (from rescaling result) that each endpoint
  is bound to a component within max(τ_pin, 0.5×that component's own diagonal), so assignment
  scales with each component, not only with the image scalar s.
- IV Experimental setup (new short section or subsection): datasets and image provenance
  (see "Image provenance" below), metrics (component-pair micro-F1 primary, macro alongside;
  define once, including that it ignores terminal identity), statistical protocol
  (paired image-level bootstrap B=10k, sign-flip permutation, Wilcoxon, Holm across comparisons).
- V Results:
  A Synthetic evaluation (keep, shorten).
  B Wire detection (keep Table I; add the modality split sentence).
  C Human-verified benchmark (N=31): Table real_join + new paired-test table (or merged column
    "Δ vs ours [95% CI], Holm p"). Figure real_join_comparison.
  D Independent held-out benchmark (N=164, 24 drafters): new table + text (validation of the
    reference against human labels; results; per-drafter spread; gap decomposition).
  E Robustness: complexity strata (both benchmarks), size dispersion, controlled rescaling
    (new Figure rescale_robustness.pdf, figures/rescale_robustness.pdf, column width), synthetic
    mixed-size test incl. the Wheatstone failure case.
  F Ablations (edge-rule table + mechanism table; keep, shorten prose).
  G End-to-end with detected components (new subsection).
  H Crossovers (condensed: annotated-box audit + detector check + e2e: all 13 detected).
  I VLM reference under identical component boxes (rewrite; honest on per-image test).
  J Per-drafter (N=31 table can be dropped or merged into D's per-drafter figure/sentence —
    prefer keeping the small table if space allows).
- VI Discussion + Scope and Limitations (single subsection; bullet-like paragraphs, each once).
- VII Conclusion (short, numbers, no hedging chains).
- Acknowledgment, Data and Code Availability (add: CGHD-derived reference nets and audit
  labels released in the repo, derived from CGHD annotations; licence note as author item).

## Verified numbers

> Superseded in places by later fixes (see git log after 0d961d7): 45/134 stroke maps (not 36), wire F1 photo 0.967 / stroke map 0.986, deployed wire F1 0.973, audit = 37 of 40 draws (cghd_audit_results.json). The manuscript is the authority.


### Benchmark 1: human-verified N=31 (annotated component boxes, detected wires)
- scale_completion micro-F1 0.890 (P 0.919, R 0.864; macro 0.901; TP/FP/FN 418/37/66;
  95% bootstrap CI [0.855, 0.924]). Leave-one-image-out range 0.885–0.900.
- Baselines (micro): degree_budget 0.829, graph_scale 0.816, graph_rescue 0.787,
  radius union-find 0.667, Hough+proximity best 0.805, connected-components best 0.624.
- Paired Δ ours − baseline (micro, bootstrap 95% CI), Holm-adjusted p (bootstrap/permutation/
  Wilcoxon), per-image W/T/L:
  - rescue graph + completion: +0.061 [+0.025, +0.100], p 0.0007/0.001/0.009, 11/18/2
  - scale-rel. graph base: +0.075, p ≤ 0.005 all, 14/16/1
  - rescue graph base: +0.103, p ≤ 0.002 all, 17/14/0
  - radius union-find: +0.224, p ≤ 0.001 all, 25/6/0
  - connected components: +0.267, p ≤ 0.001 all, 21/8/2
  - Hough: +0.086 [+0.045, +0.127], micro p ≤ 0.002; per-image-F1 tests p ≈ 0.03, 19/8/4
  - Note: Hough/CCL use their best configuration chosen on this same set (favours them).
- VLM (Claude Opus 4.8) given the same boxes: micro 0.923 (P 0.970, R 0.880, macro 0.949),
  exact on 21/31. Ours − VLM = −0.033 [−0.078, +0.008], micro bootstrap p 0.12 (permutation
  0.15) — not significant; per-image mean-F1 tests favour the VLM (Wilcoxon p 0.030; W/T/L
  7/11/13 ours/ties/VLM). State plainly: the VLM is better per image; on pooled pairs the
  difference is not significant. Position the VLM as a reference system that needs a
  proprietary API call per image; don't claim equivalence or superiority.
- Perfect (annotated) wires: 0.8898 micro (macro 0.916).
- Strata by electrical component count (ours, micro P/R/F1): ≤5 (15 imgs) .952/.929/.940;
  6–9 (4) .912/.788/.846; ≥10 (12) .911/.862/.886. Recall drop ≤5→≥10: −0.068
  [−0.18, +0.05], permutation p = 0.32 (not significant). Per-image Spearman: F1 vs count
  ρ = −0.53 (p = 0.002) — every method incl. the VLM shows the same trend. On ≥10: ours
  beats degree_budget/graph_scale/Hough by +0.078 to +0.106 (CIs exclude 0); vs VLM −0.026
  [−0.087, +0.030]. Images with crossovers (8): recall .834 vs .884 without, p = 0.51.
- Size dispersion: overall dispersion unrelated to F1 (ρ = +0.18, p = 0.33); electrical
  max/min diagonal ratio ρ = −0.60 but confounded with count (ρ = 0.62); partial ρ = −0.41
  (p = 0.024) controlling for count, VLM −0.34 similarly; component size relative to s:
  partial ρ ≈ 0. Three IC + small-parts images (C15, C242, C66): 0.854 vs 0.898 others (n=3).
- Mechanism ablations (existing table, keep): occlusion off 0.336 (103/26/381); guard off
  unchanged; witness required 0.884. Edge-rule ablation table unchanged (ties at 418/37/66;
  fixed-pixel base 0.820 vs 0.816).
- Reach sweep ρ ∈ [3,5]: macro 0.895–0.903.

### Image provenance (must be disclosed, Setup section)
- The 134 wire-benchmark and 31 net-benchmark images are 704×704 copies from a Roboflow
  export of CGHD: non-aspect-preserving resizes; 14/31 are also flipped/rotated relative to
  the CGHD file; 16/31 (and 36/134) are CGHD's binary stroke-segmentation renderings rather
  than photos. Wire labels were drawn on these copies.
- Results do not hinge on modality: wire F1 photos 0.974 (98 imgs) vs stroke maps 0.980 (36);
  join micro-F1 photos 0.883 (15) vs stroke maps 0.895 (16).

### Benchmark 2: independent CGHD-annotation reference (held-out)
- Reference construction: CGHD stroke-segmentation map minus (dilated) symbol instance
  polygons → connected conductors; conductor connects every polygon it touches (text
  excluded); junctions merge; crossovers paired straight-through by local direction
  (180° ± 45°), otherwise flagged; composite outlines (transformer/optocoupler/relay) that
  contain sub-parts ignored. Extends CGHD's own `generate_wires` tooling. Quality flags:
  179/257 images clean (fail: 29 ambiguous crossover, 17 isolated part, 28 over-connected).
- Validation vs human labels on the 17 overlapping images: micro 0.939 (P 0.993, R 0.891;
  11/17 exact; 0.964 on 15 clean). Disagreements inspected: mostly reference misses (stroke
  gaps, ambiguous crossings) and a switch convention; 5 pairs where the reference was right.
  The reference mainly under-connects, so it understates every method's precision.
- Caveat: clean filter and v2 junction fix chosen after inspecting the 17 overlaps
  (earlier-version numbers in the JSON).
- Held-out clean set: 164 images (excluding the 31), 3874 GT pairs, all 24 drafters. Input:
  CGHD photo, aspect preserved, long side 1024, chosen on wire-level GT (52 overlaps) before
  any join score was computed.
- Results (micro-F1 [95% CI]; ours − baseline; all Holm-adjusted p = 0.0006 (resolution floor)):
  ours 0.711 [0.671, 0.748] (P 0.766, R 0.664, macro 0.724); rescue+completion 0.659
  (+0.053 [+0.033, +0.074]); scale-rel. base 0.595 (+0.117); rescue base 0.592 (+0.119);
  radius union-find 0.518 (+0.194); connected components 0.594 (+0.117); Hough 0.480
  (+0.231; best Hough tuned on this set 0.509).
- Robustness: stricter held-out (drop other photos of the 31 drawings, 155 imgs) 0.707;
  all 257 incl. unclean 0.626; switch-closed reference variant 0.698.
- By electrical-component count: 0.845 (≤5) → 0.693 (≥20).
- Per-drafter (ours): 0.465–0.917, median 0.709 (IQR 0.658–0.770); ours best of the paper's
  methods for 15/24 drafters.
- Gap to 0.890 decomposed: these are harder photos (CGHD produced stroke maps for them; the
  benchmark used those maps). Wire F1 on those photos ≈ 0.80–0.82 vs 0.98 on the copies;
  join on the 17 overlaps: 0.896 on benchmark copies vs 0.728 on the photo (long side 1024).
  Circuit-size re-weighting explains ≈ +0.01, reference recall ≈ +0.01; ≈ 0.16 is photo
  input quality → wire extraction on difficult photos is the dominant error source on this
  benchmark; the join ranking transfers.
- Human audit of 40 random held-out images: PENDING (user). Leave a clearly marked
  placeholder `% TODO-AUDIT` in both sources and in the abstract only if space; do not invent.

### Robustness: controlled rescaling (31 images, factors 0.35–3)
- Join-only (annotated wires): ours within ±0.005 of native from 0.5× to 3× (all CIs include
  0); only 0.35× drops (−0.035 [−0.061, −0.005]) when lower pixel clamps bind. Radius
  union-find (30 px) collapses with enlargement: 0.690 native → 0.429 at 2× → 0.153 at 3×.
- Full pipeline (re-extracted wires): ours 0.580 / 0.690 / 0.811 / 0.890 / 0.877 / 0.866 /
  0.866 at 0.35/0.5/0.75/1/1.5/2/3×. Upscaling costs ≤ 0.024 (CIs include 0); downscaling
  loss is wire extraction (pixel-valued Sauvola window/min_area/occlusion margins; only 241 of
  675 segments found at 0.35×); completion recovers much of it (scale-rel. base alone 0.21).
- Fixed-pixel variant of the same algorithm is within 0.016 of ours between 0.5× and 2×;
  scale-relative wins only at mismatched ends (join-only 0.5×: +0.015; full 3×: +0.033, CIs
  exclude 0). Honest attribution: scale robustness comes mostly from component-relative
  endpoint assignment + completion, not τ = k·s alone. Clamps fall outside a bound for 39%
  of images at native scale; removing clamps costs 0.023 at native (full pipeline).
- Synthetic mixed-size: one component per circuit redrawn at 0.5/2/3×: enlarging costs ≈0.005
  and ours stays ≈0.03 above fixed-pixel; shrinking −0.012. Failure case: 5 Wheatstone
  variants with a 40×15 px arm — scale-relative methods and radius add one spurious pair even
  on clean wires; fixed-pixel graphs stay exact.
- Caveats: rescaling tests zoom, not style; components are annotated boxes.

### End-to-end with the trained detector (31 images)
- Detector (YOLO26m-OBB, 16 classes) run on the unstretched EXIF-corrected CGHD original at
  its training size (1024), boxes mapped into the benchmark frame, conf 0.5 (deployment
  threshold; not tuned): electrical-component detection P/R/F1 0.886/0.858/0.872 (same when
  class must match).
- Join micro-F1 0.627 [0.519, 0.731] (TP/FP/FN 316/208/168, macro 0.656); Δ vs annotated
  boxes −0.263 [−0.366, −0.170]. conf 0.25: 0.613; 0.35: 0.616.
- Loss decomposition (sequential): missed electrical components −0.131; spurious detections
  −0.072; localization −0.043; classification −0.017.
- Orientation: 14 re-oriented images 0.491 vs 0.739 on the other 17 (detector is orientation
  sensitive).
- Crossovers: all 13 annotated crossovers detected as crossovers at every threshold → no false
  pairs attributable to missed/misclassified crossovers here; 13 instances cannot test 70.7%.
- Oracle check: annotated boxes through the same matching path reproduce 418/37/66.
- Caveat: benchmark images likely in the detector's training split (no manifest; 85/15 random
  split of CGHD excl. drafter_0) → optimistic for detection.
- The previously reported provisional 0.247 was caused by a class-index mapping bug in the
  scoring script (fixed); do not mention it in the paper, mention in the response letter only
  if needed.
- Component detection: report mAP@0.5 89.0% for the released checkpoint (best-fitness epoch),
  crossover validation recall 70.7%. One mention.

## Reviewer-concern → manuscript mapping
- R1-1 / R2-1 (N=31, one corpus, stats, cost, roadmap): Benchmark 2 (164 held-out, 24
  drafters, independent labels), Holm paired tests, LOO, human audit (+ timing → cost),
  expansion roadmap one paragraph in Limitations.
- R1-2 (complex devices): capability table stays (shortened caption); Limitations.
- R1-3 / R2-6 (thresholds, extreme/mixed sizes): rescaling figure + dispersion + synthetic
  mixed-size incl. failure case; clamps disclosed.
- R1-4 / R2-3 (values, SPICE title): structural-netlist title; scope sentence; export illustrative.
- R1-5 (complex circuits): strata on both benchmarks (≥10 on N=31; up to ≥20 on N=164).
- R1-6: citations kept.
- R2-2 (VLM oracle): identical boxes to both methods (neither receives wires); e2e with the
  detector for our pipeline; honest VLM statistics.
- R2-4 (crossover): e2e detector check + annotated audit + counterfactual.
- R2-5 (ablation): existing tables + rescaling arms (fixed-pixel, no-clamp) + e2e decomposition.

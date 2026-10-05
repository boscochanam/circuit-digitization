# CGHD-annotation connectivity benchmark (revision 2, Access-2026-33821)

> **Label correction, 2026-10-05.** Four images of the 31-image human-verified benchmark were corrected (plain crossings are not connections; C112, C242, C66, C15). Numbers in this file that depend on the 31-image nets predate the correction; the current values (e.g. ours 0.884, VLM 0.946, end to end 0.602, reference vs human 0.971) are in `docs/research/experiments/SUMMARY.md` (Revision 2) and the paper. Regenerated JSON next to this file is current.

Every number below is in `cghd_ref_benchmark.json`. Raw per-image files are in `cghd_ref/`, and the
reference nets are in `ground_truth/cghd_ref/cghd_ref_nets.json`. Scripts live in
`wire_detection/benchmark/revision2/cghd_*.py`. They ran on claw from a scratch copy; no pipeline
code was modified.

## Why this benchmark exists

Both reviewers raised the same problem with the net benchmark. It has 31 images from one corpus. Its
labels were bootstrapped from a graph join similar to ours. And `scale_completion` was chosen on those
same 31 images. This benchmark answers all three. Its labels come from the CGHD authors' own
annotations: the binary stroke maps and the coarse instance polygons in CGHD v12 (Zenodo 10056817).
It covers 257 images from 24 drafters. The primary set leaves out the 31 images.

## 1. Reference construction (`cghd_ref.py`, frozen variant v2)

The method extends CGHD's own `segmentation.generate_wires`, which fills every polygon into the
stroke map and treats the remaining blobs as wires.

1. The stroke mask is `seg <= 127`. The stroke width `sw` is estimated as 2·area/boundary.
2. The wire mask is the stroke mask minus every polygon, each dilated by `d_e = max(2, round(0.5 sw))`.
   Container polygons are the exception (transformer, optocoupler or relay holding sub-components).
   They are grouping-only: they are not erased and take no contacts.
3. Conductors are the 8-connected components of the wire mask with area ≥ max(10, 0.5 sw²).
4. A conductor touches a polygon when it comes within `d_e + max(3, round(sw))` px of it. Text
   polygons take no contacts.
5. Junction polygons are conductive nodes. They also connect directly to an adjacent polygon when
   there is ink in the gap.
6. Crossovers are not conductive. Each crossover's arms are paired straight through: each arm's
   direction is the local wire direction measured in a ring out to 4·sw, and two arms pair when
   they point within 180°±45° of each other. v2 also counts an abutting junction as an arm. Any
   crossover whose arm count is not 0, 1, 2 or 4, or that leaves an arm unpaired, is flagged
   ambiguous.
7. A net is the set of symbols touched by one union-find group. Groups touching a single symbol are
   dropped. Every symbol takes part in the topology, including terminals, gnd and switches. Separate
   gnd symbols are not merged. Pin names are `'e'`.

Scoring uses the paper's electrical subset (`electrical_indices` / `SIMULATABLE_PREFIXES`). An image
is **clean** when it meets all of these conditions:
- no crossover is ambiguous;
- no electrical part is isolated;
- no electrical part appears in more nets than it has terminals (`MAX_TERMINALS` for 2- and
  3-terminal parts, 8 for opamps, 64 for ICs);
- it has at least one electrical pair.

By that rule, 179 of 257 images are clean. The unclean ones break down like this:
- 29 have ambiguous crossovers;
- 17 have isolated parts;
- 28 have over-connected parts, mostly BJT/FET leads joined inside the symbol polygon.

Class mapping is `.`→`-` plus renames (`transistor.bjt`→`transistor-BJT`, `integrated_circuit`→`IC`,
`operational_amplifier`→`opamp`, …). On the 17 overlapping images, the matched classes agree with our
labels 100% of the time.

**Recipe history, for honesty:**
- v1 was built by looking at about 8 images, 2 of which are among the 17 overlaps. No agreement
  score had been computed at that point.
- v2 added junction arms after the disagreement analysis below turned up C66_D2_P4.
- `v2_switch_closed` is a sensitivity variant only.

## 2. Frames and image modality (verified)

The 704×704 benchmark copies are **stretched** resizes of the EXIF-corrected original. In 74 of 194
of them, the copy is also flipped or rotated (dihedral k≠0). On all 52 copies that carry our labels,
ink correlation and box IoU pick the same k (`transform_probe.json`).

Among the 257-image CGHD subset, the benchmark copy is usually the CGHD **binary stroke map**, not
the photo: ink IoU is about 0.98–0.99. That covers 16 of the 31 net-benchmark images and 45 of the
134 wire-benchmark images, which matches `e2e_detected_n31.md` and `image_modality.json`.

## 3. Validation against the human nets (17 overlaps; `cghd_validate_v2.json`)

The CGHD polygons were Hungarian-matched to our component labels at IoU ≥ 0.3. Every electrical
component matched.

| set | n | P | R | micro-F1 | macro-F1 | exact |
|---|---|---|---|---|---|---|
| all 17 (v2) | 17 | 0.993 | 0.891 | **0.939** | 0.957 | 11 |
| reference-clean | 15 | 0.996 | 0.934 | **0.964** | 0.970 | 11 |
| v1, all 17 | 17 | 0.993 | 0.884 | 0.935 | 0.955 | 11 |
| v2_switch_closed, clean | 15 | 0.996 | 0.967 | 0.981 | 0.988 | 12 |

Each disagreement was checked by eye (v2, all 17): 33 were pairs the reference missed (FN) and 2 were
pairs it added that the human nets lack (FP).

| Cause | Pairs | Images | Which side is right |
|---|---|---|---|
| Ambiguous crossovers on a doubled rail | 16 FN + 1 FP | C66, flagged unclean | Human |
| Switch convention: the human nets bridge switches | 7 FN | C15, C29 | Convention. Every method under test treats a switch as a component. |
| Gaps in the drawing or stroke map near a corner or junction | 5 FN | C15, C19 | Human |
| T-junction inside a BJT polygon | 1 FN | C2, flagged unclean | Human |
| Human merged across an undotted crossing that CGHD annotates as a crossover | 4 FN | C242 | Reference |
| Human omitted the 555's GND and CV pins from the C8 net | 1 FP | C15 | Reference |

On clean images, the reference's own errors are 5 of 241 human pairs. That is about as many as the errors
we found in the human labels.

The same stored photo-input predictions were also scored against the human nets and against the
reference on the 17 images:

| method | micro-F1 vs human | micro-F1 vs reference |
|---|---|---|
| scale_completion | 0.714 | 0.723 |
| degree_budget | 0.717 | 0.730 |
| graph_scale | 0.629 | 0.632 |
| production | 0.501 | 0.495 |
| CCL d15 | 0.364 | 0.362 |
| Hough link44 | 0.788 | 0.738 |

Method ranks agree, apart from Hough, which gains from the human switch bridging.

## 4. Input resolution (`cghd_resolution.json`, wire-level GT only, fixed before any join score)

This was checked on the 52 wire-GT overlaps. The rule was set in advance: pick the photo resize that
preserves aspect and gives the best pooled wire-F1.

| Condition | Wire-F1 | Recall |
|---|---|---|
| Benchmark condition | 0.981 | — |
| Photo, stretched 704 | 0.815 | — |
| Photo, long side 704 | 0.779 | — |
| Photo, area 704 | 0.822 | — |
| Photo, long side 880 | 0.828 | — |
| **Photo, long side 1024 (chosen)** | **0.834** | 0.811 |
| Photo, long side 1280 | 0.826 | — |
| Photo, long side 1536 | 0.811 | — |
| Stroke map, stretched 704 | 0.973 | — |

With long side 1024, wire-F1 is 0.956 on the 7 images whose benchmark copy is a photo. On the 45 whose
copy is a stroke map it is 0.822. The drop against the paper's 0.98 is a **modality** effect (real
photos versus clean stroke maps), not a resolution effect.

## 5. Results

The primary set is held-out and clean: 164 images, 24 drafters, 3874 reference pairs, with **photo**
input at long side 1024. CIs come from an image bootstrap (B=10k). The difference column is ours minus
the baseline, from a paired bootstrap. Each Holm-adjusted p is the larger of the bootstrap and
permutation values; every comparison is at the floor of 0.0006.

| method | micro-F1 [95% CI] | P | R | macro-F1 | TP/FP/FN | ours − baseline [95% CI] | win/tie/loss |
|---|---|---|---|---|---|---|---|
| **scale_completion** | **0.711** [0.671, 0.748] | 0.766 | 0.664 | 0.724 | 2573/787/1301 | | |
| degree_budget | 0.659 [0.625, 0.690] | 0.622 | 0.699 | 0.699 | 2709/1644/1165 | +0.053 [+0.033, +0.074] | 85/44/35 |
| graph_scale | 0.595 [0.544, 0.640] | 0.785 | 0.479 | 0.583 | 1855/508/2019 | +0.117 [+0.097, +0.138] | 112/46/6 |
| graph_rescue | 0.592 [0.552, 0.629] | 0.631 | 0.558 | 0.606 | 2161/1262/1713 | +0.119 [+0.097, +0.142] | 113/31/20 |
| production | 0.518 [0.479, 0.560] | 0.478 | 0.565 | 0.493 | 2188/2389/1686 | +0.194 [+0.159, +0.229] | 136/13/15 |
| Hough link44_reach48 | 0.480 [0.416, 0.548] | 0.328 | 0.895 | 0.652 | 3469/7103/405 | +0.231 [+0.168, +0.282] | 90/22/52 |
| CCL detCCL_d15 | 0.594 [0.543, 0.638] | 0.798 | 0.473 | 0.507 | 1834/463/2040 | +0.117 [+0.083, +0.156] | 117/12/35 |

The best Hough configuration chosen on this very test set (link28_reach36) reaches only 0.509; for CCL,
d15 is already the best.

Robustness checks on the primary set:
- **Strict held-out** (drop every picture of any drawing that appears among the 31; 155 images):
  ours 0.707. The differences are the same to within 0.005.
- **All 257, unclean included:** ours 0.626, and it is still ahead of every baseline.
- **Reference variants** (the stored predictions re-scored on the held-out clean set of each variant):
  - v1: ours 0.715, degree_budget 0.662;
  - switch-closed: ours 0.698, degree_budget 0.626.

**Per-drafter spread for ours** (24 drafters): micro-F1 ranges from 0.465 to 0.917, with median 0.709
and IQR 0.658–0.770. Ours has the best F1 of the paper methods for 15 of the 24 drafters.

**By electrical-component count** (micro-F1):

| components | images | ours | degree_budget | Hough |
|---|---|---|---|---|
| ≤5 | 41 | 0.845 | 0.856 | 0.835 |
| 6–9 | 41 | 0.779 | 0.756 | 0.701 |
| 10–19 | 60 | 0.694 | 0.656 | 0.593 |
| ≥20 | 22 | 0.693 | 0.608 | 0.347 |

**Stroke-map input** is a secondary condition. It is not independent of the reference, because the
reference is built from that same map. Treat it as an upper bound for the setting of the paper's
benchmark copies. On the held-out clean set, ours scores 0.775 [0.727, 0.814] and graph_scale is the
closest baseline at 0.721 (+0.054 [+0.041, +0.069]). Per-drafter F1 runs from 0.642 to 0.957.

## 6. Caveats

- **Absolute level.** The 0.711 on photos is far below the 0.890 reported on the 31 images. The main
  reason is the change of input modality: half of the 31 benchmark copies are clean stroke maps.
  Lined paper, faint pencil and perspective all hurt the frozen extractor. The *ranking*, not the
  absolute level, is what transfers.
- **The reference is not human-verified.** It agrees with the human labels at 0.94–0.96, but its
  recall is its weak side: stroke-map gaps and T-junctions inside symbol polygons. That tends to
  understate every method's precision, and ours with it. A 40-image audit batch has been staged, but
  nobody has audited it yet.
- **Choices made on the 17 overlaps.** The clean filter and the v2 junction-arm fix were settled
  after looking at them. These are reference choices, not method choices; the sensitivity results
  are in §5.
- **Baselines keep their 31-image settings.** The Hough and CCL settings are in pixels, fixed on the
  31 images at 704 px, and not re-tuned for long side 1024. The oracle row in §5 shows the upper
  bound if they were.
- **Licence.** The Zenodo record says CC BY 4.0. The README bundled with the dataset says
  CC BY-SA 3.0. This needs settling before the derived nets are released. No CGHD images are in the
  repo: the audit overlays are gitignored.

## Audit batch

`ground_truth/cghd_ref_audit/` holds 40 images drawn with seed 20260928 from the held-out clean set of
164. The nets use the same schema as `real_nets_working.json`, next to the UI metadata file. Serve it
with `python -m wire_detection.benchmark.revision2.cghd_audit_ui`. This reuses `gt_verify_ui.py`
unchanged, with its paths redirected. The overlay images are grayscale CGHD photos at long side 1600.
They are local only; to regenerate them, run `cghd_audit_export.py` on claw.

## 7. What causes the absolute drop? (follow-up, input ablation, nothing tuned)

The question is which input change moves F1. Nothing was tuned: the extractor, `scale_completion` and
our own GT component boxes are all fixed. Inputs (i)–(v):
- (i) the 704×704 benchmark copy (the paper condition);
- (ii) the CGHD photo, EXIF-corrected, rotated/flipped to match the copy, stretched to 704×704;
- (iii) the same photo, aspect preserved, long side 704;
- (iv) the same photo, aspect preserved, long side 1024 (the §5 input);
- (v) the CGHD stroke map, oriented the same way, stretched to 704×704.

**Wire-F1, 52 wire-GT overlaps** (data: `cghd_resolution.json`), split by whether the benchmark copy
is a photo or a stroke map:

| copy is | n | (i) | (ii) | (iii) | (iv) | (v) |
|---|---|---|---|---|---|---|
| photo | 7 | 0.979 | 0.966 | 0.940 | 0.956 | — |
| stroke map | 45 | 0.981 | 0.799 | 0.762 | 0.821 | 0.973 |

**Join micro-F1, 17 net overlaps**: `scale_completion`, our GT boxes, scored against the human nets
(data: `cghd_ref/cghd_input_ablation.json`). The copy is a stroke map for 16 of the 17.

| input | (i) | (ii) | (iii) | (iv) | (v) |
|---|---|---|---|---|---|
| micro-F1 | 0.896 | 0.665 | 0.677 | 0.728 | 0.897 |
| recall | 0.881 | 0.512 | 0.525 | 0.591 | 0.878 |

**Findings:**
- **Geometry is not the cause.** Where the copy is a photo, (ii) ≈ (i) and (iv) is close. The pixel
  parameters therefore do not depend on the stretched-704 geometry.
- **Photo input is the cause.** Swapping the photo in for the stroke map drops wire-F1 from 0.98 to
  about 0.8 and join-F1 from 0.90 to 0.67–0.73, whatever the geometry. The stroke map at 704
  reproduces (i).
- **The benchmark's own photo stratum does not stand in for these photos.** The benchmark's 98 photo
  copies score 0.974 wire-F1, and its 15 photo images score 0.883 join-F1. But these are *different*
  photos from the stroke-map ones. The CGHD-segmentation subset, which is exactly the set the
  benchmark replaced with stroke maps, contains photos the extractor handles much worse: lined
  paper, faint pencil, perspective.
- **No re-run.** Stretched 704 is not better than long side 1024 on the overlaps (join 0.665 vs 0.728;
  wire 0.799 vs 0.821). So the §5 table stays on long1024. That choice was made only from evidence on
  the overlaps.
- **Held-out difficulty is small (about +0.01).** The 164 held-out images are larger: median 9.5
  electrical components vs 7, and 13% have ≥20 vs 0%. Re-weighting ours to the 31's size
  distribution moves it only from 0.711 to 0.723.
- **Reference labels are also a small effect (about +0.01).** On the 17, the same photo-input
  predictions score 0.714 against the human nets and 0.723 against the reference. The reference's
  lower recall barely changes the level.

So nearly all of the 0.89 → 0.71 gap comes from running on real photos. A further 0.02 or so comes
from the larger held-out circuits and the reference labels.

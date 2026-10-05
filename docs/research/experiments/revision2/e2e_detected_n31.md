# End-to-end join with detected component boxes (N=31) — revision 2

Scripts: `wire_detection/benchmark/revision2/{stretch_check,e2e_detected,make_e2e_md}.py`, run on claw with `/home/claw/venv-ml/bin/python`, `PYTHONPATH=~/circuit-digitization` (repo at 925a86f; no pipeline code differs from 69a9994). Answer key: `ground_truth/real_nets_verified.json`; component GT: `ground_truth/component_labels/` (verified byte-equal to `find_hdc_label()` on claw for 31/31; `electrical_idxs` equal to `electrical_indices()` for 31/31).

Config: strategy `scale_completion`, greedy AABB IoU match >= 0.3 (as `detected_boxes_eval.py`), confs [0.25, 0.35, 0.5], detector `models/component_detection/yolo26m_obb_16class_aug.pt` at training imgsz 1024 (the checkpoint's own default imgsz is also 1024), paired image bootstrap B=10000, seed 20260928 (same resample indices for every arm). Runtime ~95 s on claw CPU.

## 1. What the 704x704 benchmark images are

For every stem, the EXIF-corrected CGHD original **and** its binary segmentation map (when CGHD ships one) were put through all 8 flips/rotations, stretched to 704x704 (no aspect preservation), and correlated with the benchmark image.

- Best match: source = photo for 15, segmentation map for 16 images.
- Orientation: identity for 17/31; the other 14 are flipped/transposed/rotated (transpose 6, flipud 2, fliplr 2, rot90ccw 2, rot180 1, antitranspose 1).
- Stretch correlation median 0.9984 (PSNR median 42.0 dB), min 0.805; after a small ECC affine refinement (used on 5 images, residual few-pixel shifts) min 0.867, median 0.9984. Aspect-preserving letterbox control: median corr 0.224. So the stretch is confirmed.
- Original aspect ratios W/H: 0.562–2.899 (median 1.333); 31/31 are non-square; median long side 1824 px. Only 1 image carries a non-trivial EXIF orientation (C10_D2_P3, tag 6).
- Mapping check: CGHD's own VOC boxes pushed through the same original->704 mapping match 900/900 annotated boxes, median per-image median IoU 0.934 (worst image 0.798).

Correction to the hypothesis: the benchmark images are not only stretched; 16/31 are the CGHD binary segmentation map (background removed) rather than the photo, and 14/31 are in a different orientation from the CGHD file.

## 2. The old 0.247 figure

| script version | micro-F1 | P | R | macro-F1 | elec. det P/R/F1 |
|---|---|---|---|---|---|
| `detected_boxes_eval.py` @ fe109ec (hardcoded class-index table) | 0.247 | 0.298 | 0.211 | 0.324 | 0.612/0.655/0.632 |
| `detected_boxes_eval.py` current (names from `model.names`, b2e245f fix) | 0.504 | 0.526 | 0.483 | 0.523 | 0.809/0.748/0.777 |

0.247 reproduces exactly, but only with the pre-fix script: it relabelled model classes with a hardcoded index table that agreed with the checkpoint on 1 of 16 indices. `revision_evidence/detected_boxes_results.md` (Aug 16) predates the Sep 26 fix and was never regenerated. **With the fixed script the 704-image number is 0.504, not 0.247.**

## 3. End-to-end results (component-pair F1)

Headline, pre-specified: detector on the original at its deployment threshold 0.5 (`orig@0.5`). The conf sweep is reported, not tuned on.

| arm | micro-F1 | P | R | TP/FP/FN | macro-F1 | micro 95% CI | Δ vs GT boxes | Δ 95% CI |
|---|---|---|---|---|---|---|---|---|
| annotated boxes (paper condition) | 0.884 | 0.895 | 0.873 | 407/48/59 | 0.896 | [0.849, 0.918] | +0.000 | [+0.000, +0.000] |
| detector on original, conf 0.25 | 0.588 | 0.543 | 0.642 | 299/252/167 | 0.641 | [0.475, 0.703] | -0.296 | [-0.398, -0.193] |
| detector on original, conf 0.35 | 0.591 | 0.549 | 0.642 | 299/246/167 | 0.647 | [0.478, 0.707] | -0.292 | [-0.395, -0.190] |
| **detector on original, conf 0.5** | 0.602 | 0.569 | 0.639 | 298/226/168 | 0.646 | [0.497, 0.709] | -0.282 | [-0.378, -0.187] |
| detector on 704 benchmark image, conf 0.25 | 0.501 | 0.471 | 0.534 | 249/280/217 | 0.555 | [0.401, 0.610] | -0.383 | [-0.493, -0.267] |
| detector on 704 benchmark image, conf 0.35 | 0.509 | 0.488 | 0.532 | 248/260/218 | 0.559 | [0.409, 0.621] | -0.375 | [-0.484, -0.257] |
| detector on 704 benchmark image, conf 0.5 | 0.501 | 0.512 | 0.489 | 228/217/238 | 0.522 | [0.390, 0.618] | -0.383 | [-0.505, -0.259] |
| diagnostic: original re-oriented to benchmark frame, conf 0.25 | 0.651 | 0.614 | 0.693 | 323/203/143 | 0.646 | [0.565, 0.736] | -0.233 | [-0.313, -0.156] |
| diagnostic: original re-oriented to benchmark frame, conf 0.35 | 0.650 | 0.618 | 0.685 | 319/197/147 | 0.645 | [0.555, 0.740] | -0.234 | [-0.322, -0.153] |
| diagnostic: original re-oriented to benchmark frame, conf 0.5 | 0.658 | 0.635 | 0.682 | 318/183/148 | 0.643 | [0.570, 0.742] | -0.226 | [-0.307, -0.150] |

Electrical-subset component detection (IoU >= 0.3; class-agnostic = any electrical class, class-aware = same SPICE prefix R/C/L/D/Q/V/U):

| arm | GT | det | agnostic P/R/F1 | class-aware P/R/F1 |
|---|---|---|---|---|
| orig@0.25 | 226 | 224 | 0.871/0.863/0.867 | 0.871/0.863/0.867 |
| orig@0.35 | 226 | 223 | 0.874/0.863/0.869 | 0.874/0.863/0.869 |
| orig@0.5 | 226 | 219 | 0.886/0.858/0.872 | 0.886/0.858/0.872 |
| det704@0.25 | 226 | 229 | 0.786/0.796/0.791 | 0.769/0.779/0.774 |
| det704@0.35 | 226 | 222 | 0.797/0.783/0.790 | 0.779/0.765/0.772 |
| det704@0.5 | 226 | 209 | 0.809/0.748/0.777 | 0.789/0.730/0.759 |
| benchorient@0.25 | 226 | 218 | 0.894/0.863/0.878 | 0.894/0.863/0.878 |
| benchorient@0.35 | 226 | 212 | 0.910/0.854/0.881 | 0.910/0.854/0.881 |
| benchorient@0.5 | 226 | 208 | 0.918/0.845/0.880 | 0.918/0.845/0.880 |

Split by benchmark orientation (micro-F1, TP/FP/FN):

| subset | n | GT boxes | orig@0.5 | benchorient@0.5 | det704@0.5 |
|---|---|---|---|---|---|
| re-oriented benchmark image | 14 | 0.873 (200/25/33) | 0.481 (109/111/124) | 0.600 (129/68/104) | 0.551 (117/75/116) |
| same orientation as CGHD file | 17 | 0.894 (207/23/26) | 0.704 (189/115/44) | 0.704 (189/115/44) | 0.457 (111/142/122) |

The detector is orientation-sensitive (trained with ±10° rotation only): e.g. C9_D2_P3 yields 15 boxes in its file orientation and 0–1 under any 90° rotation, and on C19_D1_P2 two-terminal boxes come out perpendicular to the annotation in the file orientation. `benchorient` is therefore a diagnostic, not a deployment condition; on the 17 identity-orientation images `orig` and `benchorient` coincide. The end-to-end loss concentrates in the 14 images whose benchmark copy is re-oriented (orig 0.481 there vs 0.704 on the other 17), and re-orienting the input to the benchmark frame recovers part of it. One possible reading, not testable here, is that the detector saw these circuits in the benchmark orientation during training (see section 6).

## 4. Scoring soundness and loss decomposition (detections from `orig`)

| arm | micro-F1 | P | R | TP/FP/FN | macro-F1 | micro 95% CI | Δ vs GT boxes | Δ 95% CI |
|---|---|---|---|---|---|---|---|---|
| oracle: GT boxes through the detection relabel/IoU-match path | 0.884 | 0.895 | 0.873 | 407/48/59 | 0.896 | [0.849, 0.918] | +0.000 | [+0.000, +0.000] |
| oracle, GT boxes shuffled (seeded) through the same path | 0.887 | 0.899 | 0.876 | 408/46/58 | 0.898 | [0.851, 0.922] | +0.003 | [-0.002, +0.010] |

The identity-order oracle reproduces 407/48/59 exactly (annotated boxes: 407/48/59), so the relabel/matching code is sound. Shuffling the component list alone moves the result to 408/46/58 (+0.003): the downstream pipeline is mildly order-dependent, so differences of a few pairs between arms are within this noise floor.

Decomposition at each conf (A -> B -> C -> D -> E; each step changes one thing):

| arm | micro-F1 | P | R | TP/FP/FN | macro-F1 | micro 95% CI | Δ vs GT boxes | Δ 95% CI |
|---|---|---|---|---|---|---|---|---|
| A annotated boxes | 0.884 | 0.895 | 0.873 | 407/48/59 | 0.896 | [0.849, 0.918] | +0.000 | [+0.000, +0.000] |
| B' drop only undetected NON-electrical GT boxes @0.25 | 0.881 | 0.880 | 0.882 | 411/56/55 | 0.899 | [0.843, 0.918] | -0.003 | [-0.009, +0.001] |
| B'' drop only undetected electrical GT boxes @0.25 | 0.745 | 0.837 | 0.672 | 313/61/153 | 0.748 | [0.643, 0.836] | -0.139 | [-0.229, -0.065] |
| B drop all undetected GT boxes @0.25 | 0.744 | 0.823 | 0.678 | 316/68/150 | 0.748 | [0.642, 0.834] | -0.140 | [-0.230, -0.067] |
| C B + unmatched detections @0.25 | 0.662 | 0.658 | 0.667 | 311/162/155 | 0.691 | [0.531, 0.789] | -0.221 | [-0.345, -0.108] |
| D detected geometry, GT class @0.25 | 0.606 | 0.553 | 0.670 | 312/252/154 | 0.649 | [0.486, 0.724] | -0.278 | [-0.389, -0.172] |
| E detected geometry + class @0.25 | 0.588 | 0.543 | 0.642 | 299/252/167 | 0.641 | [0.475, 0.703] | -0.296 | [-0.398, -0.193] |
| A annotated boxes | 0.884 | 0.895 | 0.873 | 407/48/59 | 0.896 | [0.849, 0.918] | +0.000 | [+0.000, +0.000] |
| B' drop only undetected NON-electrical GT boxes @0.35 | 0.882 | 0.884 | 0.880 | 410/54/56 | 0.899 | [0.844, 0.918] | -0.002 | [-0.008, +0.002] |
| B'' drop only undetected electrical GT boxes @0.35 | 0.745 | 0.837 | 0.672 | 313/61/153 | 0.748 | [0.643, 0.836] | -0.139 | [-0.229, -0.065] |
| B drop all undetected GT boxes @0.35 | 0.744 | 0.823 | 0.678 | 316/68/150 | 0.748 | [0.642, 0.834] | -0.140 | [-0.230, -0.067] |
| C B + unmatched detections @0.35 | 0.663 | 0.661 | 0.665 | 310/159/156 | 0.695 | [0.530, 0.790] | -0.221 | [-0.345, -0.107] |
| D detected geometry, GT class @0.35 | 0.609 | 0.559 | 0.670 | 312/246/154 | 0.655 | [0.489, 0.727] | -0.274 | [-0.386, -0.168] |
| E detected geometry + class @0.35 | 0.591 | 0.549 | 0.642 | 299/246/167 | 0.647 | [0.478, 0.707] | -0.292 | [-0.395, -0.190] |
| A annotated boxes | 0.884 | 0.895 | 0.873 | 407/48/59 | 0.896 | [0.849, 0.918] | +0.000 | [+0.000, +0.000] |
| B' drop only undetected NON-electrical GT boxes @0.5 | 0.881 | 0.878 | 0.884 | 412/57/54 | 0.899 | [0.847, 0.915] | -0.003 | [-0.012, +0.007] |
| B'' drop only undetected electrical GT boxes @0.5 | 0.746 | 0.843 | 0.670 | 312/58/154 | 0.746 | [0.645, 0.836] | -0.137 | [-0.228, -0.065] |
| B drop all undetected GT boxes @0.5 | 0.742 | 0.822 | 0.676 | 315/68/151 | 0.744 | [0.642, 0.830] | -0.142 | [-0.229, -0.071] |
| C B + unmatched detections @0.5 | 0.672 | 0.682 | 0.663 | 309/144/157 | 0.693 | [0.549, 0.790] | -0.211 | [-0.327, -0.107] |
| D detected geometry, GT class @0.5 | 0.620 | 0.579 | 0.667 | 311/226/155 | 0.654 | [0.508, 0.730] | -0.264 | [-0.367, -0.165] |
| E detected geometry + class @0.5 | 0.602 | 0.569 | 0.639 | 298/226/168 | 0.646 | [0.497, 0.709] | -0.282 | [-0.378, -0.187] |

At conf 0.5 the 0.282 micro-F1 gap splits into: missed components -0.142 (almost entirely electrical: dropping only missed non-electrical boxes gives 0.881), spurious detections -0.070, localization of matched boxes -0.052, classification -0.018. Steps are sequential, so shares depend on order.

## 5. Crossovers (R2-4)

| arm | GT crossovers | detected as crossover | misclassified | missed | false crossover dets |
|---|---|---|---|---|---|
| orig@0.25 | 13 | 13 | 0 | 0 | 4 |
| orig@0.35 | 13 | 13 | 0 | 0 | 4 |
| orig@0.5 | 13 | 13 | 0 | 0 | 4 |
| det704@0.25 | 13 | 13 | 0 | 0 | 5 |
| det704@0.35 | 13 | 12 | 0 | 1 | 4 |
| det704@0.5 | 13 | 12 | 0 | 1 | 4 |

| arm | micro-F1 | P | R | TP/FP/FN | macro-F1 | micro 95% CI | Δ vs GT boxes | Δ 95% CI |
|---|---|---|---|---|---|---|---|---|
| E @0.25 | 0.588 | 0.543 | 0.642 | 299/252/167 | 0.641 | [0.475, 0.703] | -0.296 | [-0.398, -0.193] |
| F: E with every not-detected-as-crossover GT crossover restored @0.25 | 0.588 | 0.543 | 0.642 | 299/252/167 | 0.641 | [0.475, 0.703] | -0.296 | [-0.398, -0.193] |
| G: E minus the correctly detected crossovers @0.25 | 0.593 | 0.573 | 0.614 | 286/213/180 | 0.643 | [0.476, 0.706] | -0.291 | [-0.399, -0.187] |
| E @0.35 | 0.591 | 0.549 | 0.642 | 299/246/167 | 0.647 | [0.478, 0.707] | -0.292 | [-0.395, -0.190] |
| F: E with every not-detected-as-crossover GT crossover restored @0.35 | 0.591 | 0.549 | 0.642 | 299/246/167 | 0.647 | [0.478, 0.707] | -0.292 | [-0.395, -0.190] |
| G: E minus the correctly detected crossovers @0.35 | 0.596 | 0.580 | 0.614 | 286/207/180 | 0.649 | [0.480, 0.710] | -0.287 | [-0.396, -0.183] |
| E @0.5 | 0.602 | 0.569 | 0.639 | 298/226/168 | 0.646 | [0.497, 0.709] | -0.282 | [-0.378, -0.187] |
| F: E with every not-detected-as-crossover GT crossover restored @0.5 | 0.602 | 0.569 | 0.639 | 298/226/168 | 0.646 | [0.497, 0.709] | -0.282 | [-0.378, -0.187] |
| G: E minus the correctly detected crossovers @0.5 | 0.609 | 0.603 | 0.616 | 287/189/179 | 0.650 | [0.503, 0.713] | -0.274 | [-0.375, -0.179] |

In the `orig` arm every one of the 13 annotated crossovers (8 images) is detected as a crossover at every tested threshold, so F = E: **zero** false-positive pairs on this set are attributable to missed or misclassified crossovers. Deleting the correctly detected crossovers (G) changes micro-F1 by +0.007 at 0.5 (TP 298->287, FP 226->189). The 70.7% validation recall is therefore not exercised here; 13 instances cannot estimate it.

## 6. Detector train/val overlap

- Training log (`models/component_detection/training_config.json`, `docs/research/experiments/detector/*/run_metadata.json`): 2,652 train / 468 val, `85/15 random`, seed 42, `drafter_0` excluded, dataset YAML `/home/bflcv/Projects/Components/data/cghd_16class.yaml`. No per-image split list exists in the repo, on claw, or in the checkpoint (its args only name the YAML); `detector/README.md` records that the YAML and val images are on no reachable machine.
- The CGHD copy on claw (Zenodo v12) has 24 x 96 = 2,304 images outside drafter_0 (3,341 total), which does not reconcile with 2,652 + 468 = 3,120, so the training image source/version itself is not identified.
- The 31 benchmark images come from drafters 1, 2, 3, 4, 6, 7, 9, 10, 12 and 21 (none from drafter_0), so each was eligible for training; under a uniform 85/15 split the expected number in the detector's training set is ~26 of 31. Membership of any specific image cannot be established. The e2e numbers above are therefore **not held-out** detector estimates; if anything they are optimistic for detection.

## Per-image (conf 0.5)

| image | source/orient | GT elec | orig det-elec matched | GT boxes TP/FP/FN | orig TP/FP/FN | orig F1 | det704 TP/FP/FN | benchorient TP/FP/FN |
|---|---|---|---|---|---|---|---|---|
| C84_D2_P1_jpg | image/transpose | 12 | 12 | 25/0/8 | 21/6/12 | 0.700 | 24/10/9 | 16/4/17 |
| C22_D2_P3_jpg | seg/flipud | 10 | 7 | 19/2/3 | 8/25/14 | 0.291 | 9/23/13 | 13/32/9 |
| C29_D2_P4_jpg | seg/id | 7 | 7 | 13/2/4 | 17/4/0 | 0.895 | 9/2/8 | 17/4/0 |
| C15_D2_P2_jpg | seg/id | 7 | 5 | 17/1/2 | 10/11/9 | 0.500 | 6/15/13 | 10/11/9 |
| C20_D2_P2_jpg | seg/fliplr | 4 | 3 | 6/0/0 | 3/3/3 | 0.500 | 3/3/3 | 3/3/3 |
| C138_D1_P3_jpg | image/transpose | 5 | 4 | 6/0/4 | 4/2/6 | 0.500 | 2/1/8 | 1/0/9 |
| C109_D2_P3_jpg | image/transpose | 3 | 3 | 3/0/0 | 3/0/0 | 1.000 | 3/0/0 | 3/0/0 |
| C21_D1_P3_jpg | seg/rot90ccw | 10 | 9 | 15/4/7 | 9/9/13 | 0.450 | 14/1/8 | 15/10/7 |
| C28_D1_P3_jpg | image/rot180 | 14 | 5 | 24/7/2 | 1/21/25 | 0.042 | 0/5/26 | 0/3/26 |
| C113_D2_P3_jpg | image/transpose | 3 | 2 | 3/0/0 | 1/2/2 | 0.333 | 3/0/0 | 1/2/2 |
| C5_D1_P1_jpg | seg/flipud | 3 | 3 | 3/0/0 | 3/0/0 | 1.000 | 0/0/3 | 3/0/0 |
| C10_D2_P3_jpg | image/id | 4 | 0 | 2/1/2 | 0/0/4 | 0.000 | 0/0/4 | 0/0/4 |
| C115_D2_P3_jpg | seg/id | 4 | 4 | 4/0/0 | 4/0/0 | 1.000 | 4/0/0 | 4/0/0 |
| C134_D2_P2_jpg | image/id | 4 | 4 | 4/0/0 | 4/5/0 | 0.615 | 4/1/0 | 4/5/0 |
| C134_D2_P4_jpg | image/id | 4 | 4 | 4/0/0 | 4/1/0 | 0.889 | 4/0/0 | 4/1/0 |
| C4_D2_P4_jpg | seg/id | 4 | 4 | 6/0/0 | 6/0/0 | 1.000 | 0/6/6 | 6/0/0 |
| C111_D1_P1_jpg | image/fliplr | 5 | 4 | 7/0/0 | 4/3/3 | 0.571 | 2/8/5 | 4/3/3 |
| C137_D1_P2_jpg | image/id | 5 | 5 | 7/0/0 | 7/1/0 | 0.933 | 2/10/5 | 7/1/0 |
| C9_D1_P1_jpg | image/id | 5 | 5 | 8/1/0 | 6/0/2 | 0.857 | 7/1/1 | 6/0/2 |
| C9_D1_P3_jpg | image/id | 5 | 5 | 8/1/0 | 6/1/2 | 0.800 | 7/1/1 | 6/1/2 |
| C9_D2_P3_jpg | seg/antitranspose | 5 | 4 | 8/1/0 | 5/3/3 | 0.625 | 8/1/0 | 0/0/8 |
| C103_D2_P1_jpg | image/id | 7 | 7 | 3/0/8 | 3/0/8 | 0.429 | 2/2/9 | 3/0/8 |
| C112_D1_P1_jpg | image/transpose | 7 | 7 | 17/4/0 | 17/4/0 | 0.895 | 14/12/3 | 17/3/0 |
| C19_D1_P2_jpg | seg/rot90ccw | 10 | 5 | 29/6/3 | 8/30/24 | 0.229 | 29/0/3 | 22/6/10 |
| C242_D1_P1_jpg | seg/id | 10 | 9 | 23/8/0 | 17/14/6 | 0.630 | 15/14/8 | 17/14/6 |
| C2_D2_P1_jpg | seg/id | 10 | 10 | 21/2/0 | 21/12/0 | 0.778 | 14/14/7 | 21/12/0 |
| C33_D2_P2_jpg | seg/id | 10 | 10 | 21/0/2 | 21/0/2 | 0.955 | 2/3/21 | 21/0/2 |
| C37_D2_P4_jpg | seg/id | 11 | 10 | 23/0/0 | 17/16/6 | 0.607 | 5/31/18 | 17/16/6 |
| C66_D2_P4_jpg | seg/id | 12 | 11 | 22/7/7 | 24/42/5 | 0.505 | 14/33/15 | 24/42/5 |
| C83_D2_P4_jpg | seg/id | 12 | 12 | 21/0/1 | 22/8/0 | 0.846 | 16/9/6 | 22/8/0 |
| C77_D2_P2_jpg | image/transpose | 14 | 14 | 35/1/6 | 22/3/19 | 0.667 | 6/11/35 | 31/2/10 |

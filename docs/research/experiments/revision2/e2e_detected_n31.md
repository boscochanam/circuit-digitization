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
| annotated boxes (paper condition) | 0.890 | 0.919 | 0.864 | 418/37/66 | 0.901 | [0.854, 0.925] | +0.000 | [+0.000, +0.000] |
| detector on original, conf 0.25 | 0.613 | 0.575 | 0.655 | 317/234/167 | 0.651 | [0.494, 0.723] | -0.278 | [-0.388, -0.175] |
| detector on original, conf 0.35 | 0.616 | 0.582 | 0.655 | 317/228/167 | 0.657 | [0.498, 0.727] | -0.274 | [-0.385, -0.172] |
| **detector on original, conf 0.5** | 0.627 | 0.603 | 0.653 | 316/208/168 | 0.656 | [0.519, 0.731] | -0.263 | [-0.366, -0.170] |
| detector on 704 benchmark image, conf 0.25 | 0.501 | 0.480 | 0.525 | 254/275/230 | 0.556 | [0.401, 0.611] | -0.389 | [-0.497, -0.275] |
| detector on 704 benchmark image, conf 0.35 | 0.512 | 0.500 | 0.525 | 254/254/230 | 0.560 | [0.411, 0.623] | -0.378 | [-0.487, -0.263] |
| detector on 704 benchmark image, conf 0.5 | 0.504 | 0.526 | 0.483 | 234/211/250 | 0.523 | [0.394, 0.619] | -0.387 | [-0.506, -0.264] |
| diagnostic: original re-oriented to benchmark frame, conf 0.25 | 0.675 | 0.648 | 0.705 | 341/185/143 | 0.656 | [0.590, 0.754] | -0.215 | [-0.298, -0.144] |
| diagnostic: original re-oriented to benchmark frame, conf 0.35 | 0.674 | 0.653 | 0.696 | 337/179/147 | 0.655 | [0.581, 0.759] | -0.216 | [-0.306, -0.141] |
| diagnostic: original re-oriented to benchmark frame, conf 0.5 | 0.682 | 0.671 | 0.694 | 336/165/148 | 0.653 | [0.597, 0.761] | -0.208 | [-0.291, -0.138] |

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
| re-oriented benchmark image | 14 | 0.881 (203/22/33) | 0.491 (112/108/124) | 0.610 (132/65/104) | 0.547 (117/75/119) |
| same orientation as CGHD file | 17 | 0.900 (215/15/33) | 0.739 (204/100/44) | 0.739 (204/100/44) | 0.467 (117/136/131) |

The detector is orientation-sensitive (trained with ±10° rotation only): e.g. C9_D2_P3 yields 15 boxes in its file orientation and 0–1 under any 90° rotation, and on C19_D1_P2 two-terminal boxes come out perpendicular to the annotation in the file orientation. `benchorient` is therefore a diagnostic, not a deployment condition; on the 17 identity-orientation images `orig` and `benchorient` coincide. The end-to-end loss concentrates in the 14 images whose benchmark copy is re-oriented (orig 0.491 there vs 0.739 on the other 17), and re-orienting the input to the benchmark frame recovers part of it. One possible reading, not testable here, is that the detector saw these circuits in the benchmark orientation during training (see section 6).

## 4. Scoring soundness and loss decomposition (detections from `orig`)

| arm | micro-F1 | P | R | TP/FP/FN | macro-F1 | micro 95% CI | Δ vs GT boxes | Δ 95% CI |
|---|---|---|---|---|---|---|---|---|
| oracle: GT boxes through the detection relabel/IoU-match path | 0.890 | 0.919 | 0.864 | 418/37/66 | 0.901 | [0.854, 0.925] | +0.000 | [+0.000, +0.000] |
| oracle, GT boxes shuffled (seeded) through the same path | 0.893 | 0.923 | 0.866 | 419/35/65 | 0.903 | [0.857, 0.928] | +0.003 | [-0.002, +0.010] |

The identity-order oracle reproduces 418/37/66 exactly, so the relabel/matching code is sound. Shuffling the component list alone moves the result to 419/35/65 (+0.003): the downstream pipeline is mildly order-dependent, so differences of a few pairs between arms are within this noise floor.

Decomposition at each conf (A -> B -> C -> D -> E; each step changes one thing):

| arm | micro-F1 | P | R | TP/FP/FN | macro-F1 | micro 95% CI | Δ vs GT boxes | Δ 95% CI |
|---|---|---|---|---|---|---|---|---|
| A annotated boxes | 0.890 | 0.919 | 0.864 | 418/37/66 | 0.901 | [0.854, 0.925] | +0.000 | [+0.000, +0.000] |
| B' drop only undetected NON-electrical GT boxes @0.25 | 0.892 | 0.908 | 0.876 | 424/43/60 | 0.905 | [0.857, 0.925] | +0.001 | [+0.000, +0.005] |
| B'' drop only undetected electrical GT boxes @0.25 | 0.758 | 0.869 | 0.671 | 325/49/159 | 0.754 | [0.654, 0.846] | -0.133 | [-0.222, -0.061] |
| B drop all undetected GT boxes @0.25 | 0.760 | 0.859 | 0.682 | 330/54/154 | 0.755 | [0.659, 0.847] | -0.130 | [-0.219, -0.059] |
| C B + unmatched detections @0.25 | 0.677 | 0.685 | 0.669 | 324/149/160 | 0.698 | [0.543, 0.801] | -0.213 | [-0.337, -0.100] |
| D detected geometry, GT class @0.25 | 0.630 | 0.585 | 0.682 | 330/234/154 | 0.659 | [0.506, 0.743] | -0.261 | [-0.376, -0.158] |
| E detected geometry + class @0.25 | 0.613 | 0.575 | 0.655 | 317/234/167 | 0.651 | [0.494, 0.723] | -0.278 | [-0.388, -0.175] |
| A annotated boxes | 0.890 | 0.919 | 0.864 | 418/37/66 | 0.901 | [0.854, 0.925] | +0.000 | [+0.000, +0.000] |
| B' drop only undetected NON-electrical GT boxes @0.35 | 0.892 | 0.912 | 0.874 | 423/41/61 | 0.905 | [0.858, 0.926] | +0.002 | [+0.000, +0.005] |
| B'' drop only undetected electrical GT boxes @0.35 | 0.758 | 0.869 | 0.671 | 325/49/159 | 0.754 | [0.654, 0.846] | -0.133 | [-0.222, -0.061] |
| B drop all undetected GT boxes @0.35 | 0.760 | 0.859 | 0.682 | 330/54/154 | 0.755 | [0.659, 0.847] | -0.130 | [-0.219, -0.059] |
| C B + unmatched detections @0.35 | 0.678 | 0.689 | 0.667 | 323/146/161 | 0.702 | [0.542, 0.803] | -0.212 | [-0.337, -0.099] |
| D detected geometry, GT class @0.35 | 0.633 | 0.591 | 0.682 | 330/228/154 | 0.665 | [0.510, 0.746] | -0.257 | [-0.372, -0.154] |
| E detected geometry + class @0.35 | 0.616 | 0.582 | 0.655 | 317/228/167 | 0.657 | [0.498, 0.727] | -0.274 | [-0.385, -0.172] |
| A annotated boxes | 0.890 | 0.919 | 0.864 | 418/37/66 | 0.901 | [0.854, 0.925] | +0.000 | [+0.000, +0.000] |
| B' drop only undetected NON-electrical GT boxes @0.5 | 0.892 | 0.906 | 0.878 | 425/44/59 | 0.905 | [0.861, 0.923] | +0.002 | [-0.007, +0.009] |
| B'' drop only undetected electrical GT boxes @0.5 | 0.759 | 0.876 | 0.669 | 324/46/160 | 0.753 | [0.656, 0.847] | -0.132 | [-0.220, -0.061] |
| B drop all undetected GT boxes @0.5 | 0.759 | 0.859 | 0.680 | 329/54/155 | 0.752 | [0.659, 0.843] | -0.131 | [-0.219, -0.062] |
| C B + unmatched detections @0.5 | 0.687 | 0.711 | 0.665 | 322/131/162 | 0.700 | [0.561, 0.802] | -0.203 | [-0.321, -0.099] |
| D detected geometry, GT class @0.5 | 0.644 | 0.613 | 0.680 | 329/208/155 | 0.664 | [0.530, 0.748] | -0.246 | [-0.353, -0.151] |
| E detected geometry + class @0.5 | 0.627 | 0.603 | 0.653 | 316/208/168 | 0.656 | [0.519, 0.731] | -0.263 | [-0.366, -0.170] |

At conf 0.5 the 0.263 micro-F1 gap splits into: missed components -0.131 (almost entirely electrical: dropping only missed non-electrical boxes gives 0.892), spurious detections -0.072, localization of matched boxes -0.043, classification -0.017. Steps are sequential, so shares depend on order.

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
| E @0.25 | 0.613 | 0.575 | 0.655 | 317/234/167 | 0.651 | [0.494, 0.723] | -0.278 | [-0.388, -0.175] |
| F: E with every not-detected-as-crossover GT crossover restored @0.25 | 0.613 | 0.575 | 0.655 | 317/234/167 | 0.651 | [0.494, 0.723] | -0.278 | [-0.388, -0.175] |
| G: E minus the correctly detected crossovers @0.25 | 0.592 | 0.583 | 0.601 | 291/208/193 | 0.641 | [0.477, 0.703] | -0.298 | [-0.404, -0.198] |
| E @0.35 | 0.616 | 0.582 | 0.655 | 317/228/167 | 0.657 | [0.498, 0.727] | -0.274 | [-0.385, -0.172] |
| F: E with every not-detected-as-crossover GT crossover restored @0.35 | 0.616 | 0.582 | 0.655 | 317/228/167 | 0.657 | [0.498, 0.727] | -0.274 | [-0.385, -0.172] |
| G: E minus the correctly detected crossovers @0.35 | 0.596 | 0.590 | 0.601 | 291/202/193 | 0.646 | [0.481, 0.707] | -0.295 | [-0.401, -0.194] |
| E @0.5 | 0.627 | 0.603 | 0.653 | 316/208/168 | 0.656 | [0.519, 0.731] | -0.263 | [-0.366, -0.170] |
| F: E with every not-detected-as-crossover GT crossover restored @0.5 | 0.627 | 0.603 | 0.653 | 316/208/168 | 0.656 | [0.519, 0.731] | -0.263 | [-0.366, -0.170] |
| G: E minus the correctly detected crossovers @0.5 | 0.608 | 0.613 | 0.603 | 292/184/192 | 0.647 | [0.502, 0.711] | -0.282 | [-0.380, -0.191] |

In the `orig` arm every one of the 13 annotated crossovers (8 images) is detected as a crossover at every tested threshold, so F = E: **zero** false-positive pairs on this set are attributable to missed or misclassified crossovers. Deleting the correctly detected crossovers (G) changes micro-F1 by -0.019 at 0.5 (TP 316->292, FP 208->184). The 70.7% validation recall is therefore not exercised here; 13 instances cannot estimate it.

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
| C15_D2_P2_jpg | seg/id | 7 | 5 | 16/2/2 | 9/12/9 | 0.462 | 5/16/13 | 9/12/9 |
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
| C112_D1_P1_jpg | image/transpose | 7 | 7 | 20/1/0 | 20/1/0 | 0.976 | 14/12/6 | 20/0/0 |
| C19_D1_P2_jpg | seg/rot90ccw | 10 | 5 | 29/6/3 | 8/30/24 | 0.229 | 29/0/3 | 22/6/10 |
| C242_D1_P1_jpg | seg/id | 10 | 9 | 27/4/0 | 21/10/6 | 0.724 | 19/10/8 | 21/10/6 |
| C2_D2_P1_jpg | seg/id | 10 | 10 | 21/2/0 | 21/12/0 | 0.778 | 14/14/7 | 21/12/0 |
| C33_D2_P2_jpg | seg/id | 10 | 10 | 21/0/2 | 21/0/2 | 0.955 | 2/3/21 | 21/0/2 |
| C37_D2_P4_jpg | seg/id | 11 | 10 | 23/0/0 | 17/16/6 | 0.607 | 5/31/18 | 17/16/6 |
| C66_D2_P4_jpg | seg/id | 12 | 11 | 27/2/14 | 36/30/5 | 0.673 | 17/30/24 | 36/30/5 |
| C83_D2_P4_jpg | seg/id | 12 | 12 | 21/0/1 | 22/8/0 | 0.846 | 16/9/6 | 22/8/0 |
| C77_D2_P2_jpg | image/transpose | 14 | 14 | 35/1/6 | 22/3/19 | 0.667 | 6/11/35 | 31/2/10 |

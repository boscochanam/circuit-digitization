# CGHD held-out benchmark: extended scoring variants (revision 2)

> **Label correction, 2026-10-05.** Four images of the 31-image human-verified benchmark were corrected (plain crossings are not connections; C112, C242, C66, C15). Numbers in this file that depend on the 31-image nets predate the correction; the current values (e.g. ours 0.884, VLM 0.946, end to end 0.602, reference vs human 0.971) are in `docs/research/experiments/SUMMARY.md` (Revision 2) and the paper. Regenerated JSON next to this file is current.

Numbers are in `cghd_ref_extended_scoring.json`. Scripts: `wire_detection/benchmark/revision2/cghd_eval_ext.py`
(run on claw) and `cghd_extended_scoring.py` (local, numpy only). Nothing was re-tuned. The reference is the
frozen v2 (`ground_truth/cghd_ref/cghd_ref_nets.json`). The input is the §5 primary condition (photo, long side 1024), and the
image sets are the 164 held-out clean images plus two subsets of them. Only the scoring changes.

## Why the join was re-run

`cghd_eval_photo.json` stores predicted pairs only over the electrical subset, so it cannot be re-scored over a
larger component set or after closing switches. `cghd_eval_ext.py` repeats the per-image path of `cghd_eval.py`
line for line: same resize, same CGHD-polygon components, `detect_wires`, `make_pins`/`make_pins_junction_aware`,
`run_strategy`, Hough link44_reach48 and CCL d15. It runs on the 164 images and stores pin-level predicted nodes over
**all** components.

**Reproduction check:** the electrical-subset pairs derived from the stored nodes match the stored `pred_pairs` for
every image and method, and the per-image TP/FP/FN match `cghd_eval_photo.json` exactly. Micro-F1 matches
`cghd_ref_benchmark.json` to machine precision: ours 0.7114 on 164
images. Result: exact = True.

## Variant A: extended components

The scored set is the electrical subset (R/C/L/V/D/Q/U) plus these simple two-terminal parts. Counts are instances /
images on the 164.

- `crystal` -> crystal: 5 / 5
- `fuse` -> fuse: 6 / 5
- `lamp` -> lamp: 7 / 5
- `microphone` -> microphone: 5 / 5
- `resistor.adjustable` -> resistor-adjustable: 35 / 30
- `resistor.photo` -> resistor-photo: 3 / 3
- `speaker` -> speaker: 26 / 21
- `switch` -> switch: 52 / 30
- `varistor` -> varistor: 8 / 7

77 of the 164 images contain at least one of them.

**How pins are built.** Our pin builder (`derive_pins_from_obb`) gives each of these parts pins:
- switch, fuse, lamp, varistor and crystal go through the two-terminal OBB branch (the two short-edge midpoints);
- microphone gets the 2-pin `PIN_DEFINITIONS` entry;
- speaker and resistor-photo get the default 2 pins;
- resistor-adjustable gets 3 pins (two ends and the wiper).

These parts were already in the join's topology in every run. Only the scoring ignored them.

**Excluded, and why:**
- multi-terminal or active parts: thyristor, triac, transistor-photo, logic gates, optocoupler, relay, transformer
  (these three are also containers in the reference);
- nodes rather than parts: terminal, gnd, vss, junction;
- connectors, instruments or unclear classes: socket, probe-current, magnetic, mechanical, optical, antenna, unknown;
- motor: one instance only, and an electromechanical load rather than a clearly passive part.

`A_core`, a sensitivity variant that adds only switch, potentiometer and photoresistor, is in the JSON. There ours
scores 0.711 on the 164 images.

### Held-out clean (164)
n = 164 images, 4451 reference pairs. Versus primary scoring: reference pairs change in 76 images (+577 / -0 pairs); ours' TP/FP/FN change in 76 images.

| method | micro-F1 [95% CI] | P | R | macro-F1 | TP/FP/FN | ours - baseline [95% CI] | Holm p | win/tie/loss |
|---|---|---|---|---|---|---|---|---|
| **scale_completion (ours)** | 0.709 [0.670, 0.744] | 0.759 | 0.664 | 0.722 | 2957/939/1494 |  |  |  |
| degree_budget | 0.653 [0.621, 0.684] | 0.612 | 0.700 | 0.691 | 3116/1976/1335 | +0.055 [+0.036, +0.077] | 0.0006 | 86/41/37 |
| graph_scale | 0.595 [0.548, 0.638] | 0.777 | 0.482 | 0.580 | 2146/616/2305 | +0.113 [+0.095, +0.134] | 0.0006 | 122/36/6 |
| graph_rescue | 0.590 [0.551, 0.625] | 0.619 | 0.563 | 0.599 | 2505/1542/1946 | +0.119 [+0.097, +0.141] | 0.0006 | 120/26/18 |
| production | 0.510 [0.474, 0.550] | 0.474 | 0.553 | 0.494 | 2461/2730/1990 | +0.198 [+0.165, +0.231] | 0.0006 | 139/11/14 |
| Hough link44_reach48 | 0.482 [0.422, 0.545] | 0.330 | 0.888 | 0.650 | 3951/8008/500 | +0.227 [+0.167, +0.276] | 0.0006 | 93/20/51 |
| CCL detCCL_d15 | 0.588 [0.539, 0.631] | 0.794 | 0.467 | 0.505 | 2080/540/2371 | +0.120 [+0.086, +0.162] | 0.0006 | 120/9/35 |

### Excluding the 134 wire-benchmark images (139)
n = 139 images, 3964 reference pairs. Versus primary scoring: reference pairs change in 67 images (+523 / -0 pairs); ours' TP/FP/FN change in 67 images.

| method | micro-F1 [95% CI] | P | R | macro-F1 | TP/FP/FN | ours - baseline [95% CI] | Holm p | win/tie/loss |
|---|---|---|---|---|---|---|---|---|
| **scale_completion (ours)** | 0.707 [0.663, 0.747] | 0.770 | 0.654 | 0.726 | 2591/772/1373 |  |  |  |
| degree_budget | 0.649 [0.613, 0.683] | 0.610 | 0.692 | 0.691 | 2744/1754/1220 | +0.059 [+0.037, +0.082] | 0.0006 | 73/35/31 |
| graph_scale | 0.592 [0.539, 0.641] | 0.796 | 0.472 | 0.581 | 1870/479/2094 | +0.115 [+0.094, +0.137] | 0.0006 | 106/28/5 |
| graph_rescue | 0.585 [0.542, 0.625] | 0.620 | 0.555 | 0.597 | 2200/1351/1764 | +0.122 [+0.099, +0.146] | 0.0006 | 106/19/14 |
| production | 0.512 [0.472, 0.554] | 0.464 | 0.572 | 0.511 | 2266/2621/1698 | +0.195 [+0.159, +0.232] | 0.0006 | 116/11/12 |
| Hough link44_reach48 | 0.470 [0.408, 0.537] | 0.318 | 0.899 | 0.661 | 3563/7624/401 | +0.237 [+0.174, +0.290] | 0.0006 | 76/18/45 |
| CCL detCCL_d15 | 0.599 [0.547, 0.645] | 0.788 | 0.483 | 0.514 | 1914/515/2050 | +0.108 [+0.072, +0.152] | 0.0006 | 100/7/32 |

## Variant B: switch closed (symmetric)

Each switch is treated as a wire:
- **Reference:** every v2 net that contains a given switch is unioned (transitively).
- **Each prediction:** every predicted node that holds any pin of that switch is unioned.

Switches are not scored, and the scored set is the electrical subset.

**What the old 0.698 number was.** It is not symmetric. It re-scored the stored predictions, with no merge, against
the rebuilt reference `cghd_ref_nets_v2_switch_closed.json` (switch treated as a conductive junction). It was also
computed on that variant's own held-out clean set of 166 images, not the 164.
Re-derived here: ours 0.698, degree_budget
0.626.

**Checks on the 164:**
- The net-union reference and the rebuilt reference give identical electrical pairs
  (both 3938, only one of the two 0 / 0).
- Asymmetric scoring gives ours 0.708.
- Symmetric scoring gives ours 0.712.

So the lower 0.698 came from the unmerged predictions and the different image set, not from the method.

### Held-out clean (164)
n = 164 images, 3938 reference pairs. Versus primary scoring: reference pairs change in 19 images (+64 / -0 pairs); ours' TP/FP/FN change in 20 images.

| method | micro-F1 [95% CI] | P | R | macro-F1 | TP/FP/FN | ours - baseline [95% CI] | Holm p | win/tie/loss |
|---|---|---|---|---|---|---|---|---|
| **scale_completion (ours)** | 0.712 [0.672, 0.748] | 0.768 | 0.663 | 0.723 | 2611/787/1327 |  |  |  |
| degree_budget | 0.659 [0.626, 0.691] | 0.627 | 0.696 | 0.699 | 2741/1634/1197 | +0.052 [+0.032, +0.074] | 0.0006 | 84/46/34 |
| graph_scale | 0.594 [0.543, 0.639] | 0.787 | 0.476 | 0.580 | 1876/507/2062 | +0.118 [+0.098, +0.140] | 0.0006 | 113/45/6 |
| graph_rescue | 0.593 [0.552, 0.629] | 0.636 | 0.555 | 0.604 | 2186/1252/1752 | +0.119 [+0.097, +0.141] | 0.0006 | 112/33/19 |
| production | 0.518 [0.479, 0.560] | 0.481 | 0.560 | 0.492 | 2206/2376/1732 | +0.194 [+0.159, +0.229] | 0.0006 | 136/13/15 |
| Hough link44_reach48 | 0.485 [0.421, 0.554] | 0.333 | 0.895 | 0.654 | 3523/7058/415 | +0.227 [+0.162, +0.278] | 0.0006 | 89/21/54 |
| CCL detCCL_d15 | 0.591 [0.540, 0.635] | 0.799 | 0.469 | 0.505 | 1847/466/2091 | +0.121 [+0.087, +0.160] | 0.0006 | 116/15/33 |

### Excluding the 134 wire-benchmark images (139)
n = 139 images, 3501 reference pairs. Versus primary scoring: reference pairs change in 18 images (+60 / -0 pairs); ours' TP/FP/FN change in 19 images.

| method | micro-F1 [95% CI] | P | R | macro-F1 | TP/FP/FN | ours - baseline [95% CI] | Holm p | win/tie/loss |
|---|---|---|---|---|---|---|---|---|
| **scale_completion (ours)** | 0.709 [0.664, 0.750] | 0.776 | 0.652 | 0.728 | 2282/658/1219 |  |  |  |
| degree_budget | 0.653 [0.617, 0.688] | 0.623 | 0.687 | 0.697 | 2406/1458/1095 | +0.055 [+0.033, +0.079] | 0.0006 | 72/38/29 |
| graph_scale | 0.589 [0.533, 0.639] | 0.800 | 0.466 | 0.579 | 1631/408/1870 | +0.120 [+0.098, +0.144] | 0.0006 | 100/35/4 |
| graph_rescue | 0.587 [0.542, 0.627] | 0.633 | 0.546 | 0.600 | 1913/1107/1588 | +0.122 [+0.098, +0.147] | 0.0006 | 99/24/16 |
| production | 0.519 [0.477, 0.565] | 0.471 | 0.579 | 0.508 | 2026/2276/1475 | +0.189 [+0.151, +0.228] | 0.0006 | 114/12/13 |
| Hough link44_reach48 | 0.475 [0.405, 0.546] | 0.321 | 0.909 | 0.668 | 3181/6722/320 | +0.234 [+0.168, +0.288] | 0.0006 | 72/19/48 |
| CCL detCCL_d15 | 0.603 [0.549, 0.650] | 0.794 | 0.486 | 0.516 | 1700/441/1801 | +0.106 [+0.072, +0.146] | 0.0006 | 98/11/30 |

Primary scoring on the 139 images, for reference: ours 0.709.
Excluding by *drawing* instead (any picture of a drawing in the 134 set) leaves 123 images. Those results are in the
JSON (`heldout_clean_not_wire134_drawing`): ours 0.704 primary,
0.703 A, and
0.702 B.
Every difference in A and B is positive and has Holm p = 0.0006.

## Variant C: grounds merged (symmetric)

Electrically, all ground symbols are one node. So in the reference, and in every method's predictions (predicted
nodes holding a pin of a gnd symbol), all nets touching any CGHD `gnd` symbol are unioned into one node. Separately,
all nets touching any `vss` symbol are unioned into one node. CGHD has no `vdd` class; the merge code handles it,
but there are 0 instances. The scored set is the electrical subset.

**Ground inventory on the 164 images:**
- 65 images have at least one gnd, and 47 have two or more.
- 18 have at least one vss, and 12 have two or more.
- 48 have two or more of gnd or vss.
- 17 have both gnd and vss (they are kept as separate nodes).

### Held-out clean (164)
n = 164 images, 4652 reference pairs. Versus primary scoring: reference pairs change in 43 images (+778 / -0 pairs); ours' TP/FP/FN change in 45 images.

| method | micro-F1 [95% CI] | P | R | macro-F1 | TP/FP/FN | ours - baseline [95% CI] | Holm p | win/tie/loss |
|---|---|---|---|---|---|---|---|---|
| **scale_completion (ours)** | 0.679 [0.642, 0.715] | 0.758 | 0.615 | 0.710 | 2861/911/1791 |  |  |  |
| degree_budget | 0.644 [0.613, 0.677] | 0.610 | 0.682 | 0.696 | 3173/2026/1479 | +0.035 [+0.012, +0.059] | 0.0038 | 76/43/45 |
| graph_scale | 0.565 [0.517, 0.611] | 0.775 | 0.445 | 0.575 | 2068/601/2584 | +0.114 [+0.095, +0.135] | 0.0006 | 111/48/5 |
| graph_rescue | 0.576 [0.537, 0.615] | 0.619 | 0.539 | 0.602 | 2507/1544/2145 | +0.103 [+0.080, +0.126] | 0.0006 | 110/31/23 |
| production | 0.527 [0.485, 0.570] | 0.469 | 0.600 | 0.496 | 2792/3160/1860 | +0.153 [+0.112, +0.196] | 0.0006 | 129/14/21 |
| Hough link44_reach48 | 0.532 [0.463, 0.596] | 0.379 | 0.894 | 0.672 | 4157/6811/495 | +0.147 [+0.087, +0.203] | 0.0006 | 80/22/62 |
| CCL detCCL_d15 | 0.597 [0.551, 0.638] | 0.763 | 0.491 | 0.503 | 2283/708/2369 | +0.082 [+0.047, +0.123] | 0.0006 | 114/13/37 |

### Excluding the 134 wire-benchmark images (139)
n = 139 images, 4187 reference pairs. Versus primary scoring: reference pairs change in 40 images (+746 / -0 pairs); ours' TP/FP/FN change in 42 images.

| method | micro-F1 [95% CI] | P | R | macro-F1 | TP/FP/FN | ours - baseline [95% CI] | Holm p | win/tie/loss |
|---|---|---|---|---|---|---|---|---|
| **scale_completion (ours)** | 0.672 [0.630, 0.712] | 0.767 | 0.598 | 0.709 | 2503/762/1684 |  |  |  |
| degree_budget | 0.638 [0.603, 0.675] | 0.609 | 0.669 | 0.692 | 2802/1796/1385 | +0.034 [+0.007, +0.060] | 0.0130 | 64/36/39 |
| graph_scale | 0.559 [0.506, 0.610] | 0.788 | 0.433 | 0.569 | 1813/488/2374 | +0.113 [+0.093, +0.135] | 0.0006 | 98/38/3 |
| graph_rescue | 0.570 [0.527, 0.613] | 0.619 | 0.528 | 0.596 | 2212/1362/1975 | +0.102 [+0.076, +0.127] | 0.0006 | 97/23/19 |
| production | 0.526 [0.481, 0.572] | 0.459 | 0.615 | 0.507 | 2575/3031/1612 | +0.146 [+0.101, +0.194] | 0.0006 | 108/12/19 |
| Hough link44_reach48 | 0.524 [0.450, 0.592] | 0.369 | 0.902 | 0.684 | 3775/6455/412 | +0.148 [+0.083, +0.207] | 0.0006 | 64/19/56 |
| CCL detCCL_d15 | 0.605 [0.557, 0.650] | 0.760 | 0.503 | 0.510 | 2107/667/2080 | +0.066 [+0.032, +0.109] | 0.0006 | 96/9/34 |

## A+B+C combined (extended components, switches closed, grounds merged)

### Held-out clean (164)
n = 164 images, 5567 reference pairs. Versus primary scoring: reference pairs change in 92 images (+1693 / -0 pairs); ours' TP/FP/FN change in 93 images.

| method | micro-F1 [95% CI] | P | R | macro-F1 | TP/FP/FN | ours - baseline [95% CI] | Holm p | win/tie/loss |
|---|---|---|---|---|---|---|---|---|
| **scale_completion (ours)** | 0.676 [0.638, 0.711] | 0.762 | 0.607 | 0.710 | 3378/1054/2189 |  |  |  |
| degree_budget | 0.644 [0.610, 0.678] | 0.618 | 0.672 | 0.693 | 3741/2313/1826 | +0.032 [+0.009, +0.056] | 0.0084 | 73/42/49 |
| graph_scale | 0.563 [0.515, 0.608] | 0.777 | 0.441 | 0.573 | 2454/704/3113 | +0.113 [+0.095, +0.132] | 0.0006 | 122/38/4 |
| graph_rescue | 0.578 [0.538, 0.619] | 0.628 | 0.536 | 0.599 | 2985/1768/2582 | +0.097 [+0.074, +0.121] | 0.0006 | 113/29/22 |
| production | 0.524 [0.485, 0.564] | 0.475 | 0.583 | 0.498 | 3247/3590/2320 | +0.152 [+0.111, +0.195] | 0.0006 | 127/12/25 |
| Hough link44_reach48 | 0.549 [0.483, 0.611] | 0.398 | 0.886 | 0.677 | 4935/7471/632 | +0.127 [+0.064, +0.184] | 0.0006 | 80/20/64 |
| CCL detCCL_d15 | 0.589 [0.545, 0.627] | 0.766 | 0.478 | 0.501 | 2662/812/2905 | +0.087 [+0.050, +0.130] | 0.0006 | 112/11/41 |

### Excluding the 134 wire-benchmark images (139)
n = 139 images, 5041 reference pairs. Versus primary scoring: reference pairs change in 80 images (+1600 / -0 pairs); ours' TP/FP/FN change in 81 images.

| method | micro-F1 [95% CI] | P | R | macro-F1 | TP/FP/FN | ours - baseline [95% CI] | Holm p | win/tie/loss |
|---|---|---|---|---|---|---|---|---|
| **scale_completion (ours)** | 0.668 [0.627, 0.710] | 0.773 | 0.589 | 0.708 | 2968/872/2073 |  |  |  |
| degree_budget | 0.638 [0.602, 0.678] | 0.619 | 0.659 | 0.691 | 3322/2048/1719 | +0.030 [+0.004, +0.056] | 0.0251 | 60/35/44 |
| graph_scale | 0.555 [0.503, 0.607] | 0.794 | 0.427 | 0.568 | 2153/558/2888 | +0.113 [+0.094, +0.134] | 0.0006 | 106/30/3 |
| graph_rescue | 0.573 [0.528, 0.618] | 0.631 | 0.525 | 0.594 | 2647/1551/2394 | +0.095 [+0.069, +0.122] | 0.0006 | 99/21/19 |
| production | 0.524 [0.482, 0.567] | 0.466 | 0.598 | 0.512 | 3015/3452/2026 | +0.144 [+0.099, +0.191] | 0.0006 | 105/11/23 |
| Hough link44_reach48 | 0.542 [0.472, 0.607] | 0.389 | 0.893 | 0.688 | 4504/7070/537 | +0.126 [+0.058, +0.188] | 0.0014 | 64/17/58 |
| CCL detCCL_d15 | 0.596 [0.550, 0.637] | 0.762 | 0.489 | 0.508 | 2465/771/2576 | +0.073 [+0.036, +0.119] | 0.0006 | 92/9/38 |

**Why C lowers every graph method.** Merging grounds turns several separate ground nets into one large net. The number
of pairs in a net grows roughly with the square of its size, so this net's pairs come to dominate the pair count.
Any ground symbol that a method leaves unattached now costs pairs with every part on the common ground, not just its
own local neighbours. Ours loses recall (0.664 -> 0.615)
while its precision holds. Hough over-merges anyway, so it gains. Ours stays ahead of every baseline:
- against degree_budget, +0.035, CI above 0, Holm p =
  0.0038 (C, 164 images);
- against degree_budget, +0.030, Holm p = 0.0251
  (A+B+C, 139 images), the weakest case;
- against the other baselines, p = 0.0006, except Hough in A+B+C on 139 images (p = 0.0014).

The drawing-level 123-image subset for C and A+B+C is in the JSON.

## Caveats

- **Reference health of the added parts.** The clean filter checks electrical parts only, and the image set is held
  fixed at the primary 164. Among the added parts, 1 switch is isolated in the reference
  (C250_D2_P4). 13 switches sit in 3–4 nets; these are
  SPDT or multi-pole drawings. The pipeline gives every switch only 2 pins, so on those it cannot reach every
  reference pair in variant A. In variant B, closing such a switch joins all of its throws, which is a convention
  choice.
- **Holm p.** Each Holm p is the larger of the Holm-adjusted bootstrap and Monte-Carlo permutation p (B = 10,000;
  100k permutations; seeds as in `stats_strata.py`). Every comparison sits at the bootstrap floor of 0.0006.
- **Baseline settings.** The Hough and CCL settings are the paper-selected ones and were not re-tuned, as in §5.


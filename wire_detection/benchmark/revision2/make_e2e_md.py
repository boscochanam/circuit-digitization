#!/usr/bin/env python3
"""Render docs/research/experiments/revision2/e2e_detected_n31.md from the e2e JSON outputs.

  python wire_detection/benchmark/revision2/make_e2e_md.py \
      --e2e docs/research/experiments/revision2/e2e_detected_n31.json \
      --stretch docs/research/experiments/revision2/stretch_check_n31.json \
      --old-current <old_repro.json> --old-prefix <old_fe109ec.json> \
      --out docs/research/experiments/revision2/e2e_detected_n31.md
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict


def f3(x):
    return f"{x:.3f}"


def ci(c):
    return f"[{c[0]:.3f}, {c[1]:.3f}]"


def dci(c):
    return f"[{c[0]:+.3f}, {c[1]:+.3f}]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--e2e", required=True)
    ap.add_argument("--stretch", required=True)
    ap.add_argument("--old-current", required=True)
    ap.add_argument("--old-prefix", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = json.load(open(a.e2e))
    st = json.load(open(a.stretch))
    oc = json.load(open(a.old_current))
    op = json.load(open(a.old_prefix))
    S = d["summary"]
    cfg = d["config"]
    L = []
    w = L.append

    w("# End-to-end join with detected component boxes (N=31) — revision 2\n")
    w("Scripts: `wire_detection/benchmark/revision2/{stretch_check,e2e_detected,make_e2e_md}.py`, run on "
      "claw with `/home/claw/venv-ml/bin/python`, `PYTHONPATH=~/circuit-digitization` (repo at 925a86f; "
      "no pipeline code differs from 69a9994). Answer key: `ground_truth/real_nets_verified.json`; component "
      "GT: `ground_truth/component_labels/` (verified byte-equal to `find_hdc_label()` on claw for "
      f"{d['label_checks']['committed_equals_find_hdc_label']}/31; `electrical_idxs` equal to "
      f"`electrical_indices()` for {d['label_checks']['elec_idx_equal']}/31).\n")
    w(f"Config: strategy `{cfg['strategy']}`, greedy AABB IoU match >= {cfg['iou_match_thresh']} (as "
      f"`detected_boxes_eval.py`), confs {cfg['confs']}, detector `{cfg['model']}` at training imgsz "
      f"{cfg['train_imgsz']} (the checkpoint's own default imgsz is also {cfg['model_overrides_ckpt'].get('imgsz')}), "
      f"paired image bootstrap B={cfg['bootstrap_B']}, seed {cfg['seed']} (same resample indices for every arm). "
      "Runtime ~95 s on claw CPU.\n")

    # ── 1 stretch
    s = st["summary"]
    w("## 1. What the 704x704 benchmark images are\n")
    w("For every stem, the EXIF-corrected CGHD original **and** its binary segmentation map (when CGHD ships one) "
      "were put through all 8 flips/rotations, stretched to 704x704 (no aspect preservation), and correlated "
      "with the benchmark image.\n")
    w(f"- Best match: source = photo for {s['best_source_counts'].get('image_exif', 0)}, "
      f"segmentation map for {s['best_source_counts'].get('seg', 0)} images.")
    w(f"- Orientation: identity for {s['best_transform_counts'].get('id', 0)}/31; the other "
      f"{31 - s['best_transform_counts'].get('id', 0)} are flipped/transposed/rotated "
      f"({', '.join(f'{k} {v}' for k, v in s['best_transform_counts'].items() if k != 'id')}).")
    g = d["geometry_summary"]
    w(f"- Stretch correlation median {s['best_corr_median']:.4f} (PSNR median {s['best_psnr_median']:.1f} dB), "
      f"min {s['best_corr_min']:.3f}; after a small ECC affine refinement (used on {g['ecc_used']} images, residual "
      f"few-pixel shifts) min {g['corr_aligned_min']:.3f}, median {g['corr_aligned_median']:.4f}. Aspect-preserving "
      f"letterbox control: median corr {s['letterbox_corr_median']:.3f}. So the stretch is confirmed.")
    w(f"- Original aspect ratios W/H: {s['aspect_min']:.3f}–{s['aspect_max']:.3f} (median {s['aspect_median']:.3f}); "
      f"31/31 are non-square; median long side {s['orig_long_side_median']:.0f} px. Only 1 image carries a "
      "non-trivial EXIF orientation (C10_D2_P3, tag 6).")
    vs = d["voc_sanity_summary"]
    w(f"- Mapping check: CGHD's own VOC boxes pushed through the same original->704 mapping match "
      f"{vs['matched']}/{vs['gt_boxes']} annotated boxes, median per-image median IoU {vs['median_of_median_iou']:.3f} "
      f"(worst image {vs['min_median_iou']:.3f}).\n")
    w("Correction to the hypothesis: the benchmark images are not only stretched; 16/31 are the CGHD binary "
      "segmentation map (background removed) rather than the photo, and 14/31 are in a different orientation from "
      "the CGHD file.\n")

    # ── 2 old number
    w("## 2. The old 0.247 figure\n")
    oc_m = oc["micro"]["scale_completion"]; op_m = op["micro"]["scale_completion"]
    w("| script version | micro-F1 | P | R | macro-F1 | elec. det P/R/F1 |")
    w("|---|---|---|---|---|---|")
    w(f"| `detected_boxes_eval.py` @ fe109ec (hardcoded class-index table) | {f3(op_m['f1'])} | {f3(op_m['p'])} | "
      f"{f3(op_m['r'])} | {f3(op['macro_f1']['scale_completion'])} | {f3(op['component_detection']['precision'])}/"
      f"{f3(op['component_detection']['recall'])}/{f3(op['component_detection']['f1'])} |")
    w(f"| `detected_boxes_eval.py` current (names from `model.names`, b2e245f fix) | {f3(oc_m['f1'])} | {f3(oc_m['p'])} | "
      f"{f3(oc_m['r'])} | {f3(oc['macro_f1']['scale_completion'])} | {f3(oc['component_detection']['precision'])}/"
      f"{f3(oc['component_detection']['recall'])}/{f3(oc['component_detection']['f1'])} |\n")
    w("0.247 reproduces exactly, but only with the pre-fix script: it relabelled model classes with a hardcoded "
      "index table that agreed with the checkpoint on 1 of 16 indices. `revision_evidence/detected_boxes_results.md` "
      "(Aug 16) predates the Sep 26 fix and was never regenerated. **With the fixed script the 704-image number is "
      "0.504, not 0.247.**\n")

    # ── 3 headline
    def row(arm, label=None):
        x = S[arm]
        return (f"| {label or arm} | {f3(x['f1'])} | {f3(x['p'])} | {f3(x['r'])} | {x['tp']}/{x['fp']}/{x['fn']} | "
                f"{f3(x['macro_f1'])} | {ci(x['micro_f1_ci95'])} | {x['diff_vs_gt']:+.3f} | {dci(x['diff_vs_gt_ci95'])} |")
    hdr = ["| arm | micro-F1 | P | R | TP/FP/FN | macro-F1 | micro 95% CI | Δ vs GT boxes | Δ 95% CI |",
           "|---|---|---|---|---|---|---|---|---|"]
    w("## 3. End-to-end results (component-pair F1)\n")
    w("Headline, pre-specified: detector on the original at its deployment threshold 0.5 (`orig@0.5`). "
      "The conf sweep is reported, not tuned on.\n")
    L.extend(hdr)
    w(row("gt_direct", "annotated boxes (paper condition)"))
    for c in cfg["confs"]:
        w(row(f"orig@{c}", f"**detector on original, conf {c}**" if c == 0.5 else f"detector on original, conf {c}"))
    for c in cfg["confs"]:
        w(row(f"det704@{c}", f"detector on 704 benchmark image, conf {c}"))
    for c in cfg["confs"]:
        w(row(f"benchorient@{c}", f"diagnostic: original re-oriented to benchmark frame, conf {c}"))
    w("")
    w("Electrical-subset component detection (IoU >= 0.3; class-agnostic = any electrical class, class-aware = "
      "same SPICE prefix R/C/L/D/Q/V/U):\n")
    w("| arm | GT | det | agnostic P/R/F1 | class-aware P/R/F1 |")
    w("|---|---|---|---|---|")
    for src in ("orig", "det704", "benchorient"):
        for c in cfg["confs"]:
            q = d["detection_quality_electrical"][f"{src}@{c}"]
            ag, aw = q["agnostic"], q["aware"]
            w(f"| {src}@{c} | {q['gt_elec']} | {q['det_elec']} | {f3(ag['p'])}/{f3(ag['r'])}/{f3(ag['f1'])} | "
              f"{f3(aw['p'])}/{f3(aw['r'])}/{f3(aw['f1'])} |")
    w("")
    # orientation split
    grp = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    n = defaultdict(int)
    for r in d["per_image"].values():
        t = "same orientation as CGHD file" if r["geometry"]["transform"] == "id" else "re-oriented benchmark image"
        n[t] += 1
        for arm in ("gt_direct", "orig@0.5", "benchorient@0.5", "det704@0.5"):
            x = r["arms"][arm]; gg = grp[t][arm]
            gg[0] += x["tp"]; gg[1] += x["fp"]; gg[2] += x["fn"]
    w("Split by benchmark orientation (micro-F1, TP/FP/FN):\n")
    w("| subset | n | GT boxes | orig@0.5 | benchorient@0.5 | det704@0.5 |")
    w("|---|---|---|---|---|---|")
    for t in grp:
        cells = []
        for arm in ("gt_direct", "orig@0.5", "benchorient@0.5", "det704@0.5"):
            tp, fp, fn = grp[t][arm]
            cells.append(f"{2 * tp / (2 * tp + fp + fn):.3f} ({tp}/{fp}/{fn})")
        w(f"| {t} | {n[t]} | " + " | ".join(cells) + " |")
    keys = ["re-oriented benchmark image", "same orientation as CGHD file"]

    def f1g(t, arm="orig@0.5"):
        tp, fp, fn = grp[t][arm]
        return f"{2 * tp / (2 * tp + fp + fn):.3f}"
    w("\nThe detector is orientation-sensitive (trained with ±10° rotation only): e.g. C9_D2_P3 yields 15 boxes in its "
      "file orientation and 0–1 under any 90° rotation, and on C19_D1_P2 two-terminal boxes come out perpendicular to "
      "the annotation in the file orientation. `benchorient` is therefore a diagnostic, not a deployment condition; "
      "on the 17 identity-orientation images `orig` and `benchorient` coincide. The end-to-end loss concentrates in the "
      f"{n[keys[0]]} images whose benchmark copy is re-oriented (orig {f1g(keys[0])} there vs {f1g(keys[1])} on the "
      f"other {n[keys[1]]}), and re-orienting the "
      "input to the benchmark frame recovers part of it. One possible reading, not testable here, is that the detector "
      "saw these circuits in the benchmark orientation during training (see section 6).\n")

    # ── 4 soundness + decomposition
    w("## 4. Scoring soundness and loss decomposition (detections from `orig`)\n")
    L.extend(hdr)
    w(row("gt_oracle_matching_identity_order", "oracle: GT boxes through the detection relabel/IoU-match path"))
    w(row("gt_oracle_matching", "oracle, GT boxes shuffled (seeded) through the same path"))
    w("")
    sm = d["summary"]
    cnt = lambda a: f"{sm[a]['tp']}/{sm[a]['fp']}/{sm[a]['fn']}"  # noqa: E731
    w(f"The identity-order oracle reproduces {cnt('gt_oracle_matching_identity_order')} exactly (annotated boxes: "
      f"{cnt('gt_direct')}), so the relabel/matching code is sound. Shuffling the "
      f"component list alone moves the result to {cnt('gt_oracle_matching')} "
      f"({sm['gt_oracle_matching']['f1'] - sm['gt_direct']['f1']:+.3f}): the downstream pipeline is mildly "
      "order-dependent, so differences of a few pairs between arms are within this noise floor.\n")
    w("Decomposition at each conf (A -> B -> C -> D -> E; each step changes one thing):\n")
    L.extend(hdr)
    for c in cfg["confs"]:
        w(row("gt_direct", "A annotated boxes"))
        w(row(f"B_nonelec_missed_only@{c}", f"B' drop only undetected NON-electrical GT boxes @{c}"))
        w(row(f"B_elec_missed_only@{c}", f"B'' drop only undetected electrical GT boxes @{c}"))
        w(row(f"B_gt_minus_missed@{c}", f"B drop all undetected GT boxes @{c}"))
        w(row(f"C_plus_spurious@{c}", f"C B + unmatched detections @{c}"))
        w(row(f"D_det_loc_gt_class@{c}", f"D detected geometry, GT class @{c}"))
        w(row(f"orig@{c}", f"E detected geometry + class @{c}"))
    w("")
    A = S["gt_direct"]["f1"]
    B = S["B_gt_minus_missed@0.5"]["f1"]; C = S["C_plus_spurious@0.5"]["f1"]
    D = S["D_det_loc_gt_class@0.5"]["f1"]; E = S["orig@0.5"]["f1"]
    w(f"At conf 0.5 the {A - E:.3f} micro-F1 gap splits into: missed components {B - A:+.3f} (almost entirely "
      f"electrical: dropping only missed non-electrical boxes gives {S['B_nonelec_missed_only@0.5']['f1']:.3f}), "
      f"spurious detections {C - B:+.3f}, localization of matched boxes {D - C:+.3f}, classification {E - D:+.3f}. "
      "Steps are sequential, so shares depend on order.\n")

    # ── 5 crossover
    w("## 5. Crossovers (R2-4)\n")
    w("| arm | GT crossovers | detected as crossover | misclassified | missed | false crossover dets |")
    w("|---|---|---|---|---|---|")
    for src in ("orig", "det704"):
        for c in cfg["confs"]:
            x = d["detection_quality_electrical"][f"{src}@{c}"]["crossover"]
            w(f"| {src}@{c} | {x['gt']} | {x['detected_as_crossover']} | {x['misclassified']} | {x['missed']} | "
              f"{x['false_crossover_dets']} |")
    w("")
    L.extend(hdr)
    for c in cfg["confs"]:
        w(row(f"orig@{c}", f"E @{c}"))
        w(row(f"F_fix_crossover@{c}", f"F: E with every not-detected-as-crossover GT crossover restored @{c}"))
        w(row(f"G_drop_det_crossover@{c}", f"G: E minus the correctly detected crossovers @{c}"))
    w("")
    w("In the `orig` arm every one of the 13 annotated crossovers (8 images) is detected as a crossover at every "
      "tested threshold, so F = E: **zero** false-positive pairs on this set are attributable to missed or "
      "misclassified crossovers. Deleting the correctly detected crossovers (G) changes micro-F1 by "
      f"{S['G_drop_det_crossover@0.5']['f1'] - S['orig@0.5']['f1']:+.3f} at 0.5 (TP {S['orig@0.5']['tp']}->"
      f"{S['G_drop_det_crossover@0.5']['tp']}, FP {S['orig@0.5']['fp']}->{S['G_drop_det_crossover@0.5']['fp']}). "
      "The 70.7% validation recall is therefore not exercised here; 13 instances cannot estimate it.\n")

    # ── 6 overlap
    w("## 6. Detector train/val overlap\n")
    w("- Training log (`models/component_detection/training_config.json`, `docs/research/experiments/detector/*/run_metadata.json`): "
      "2,652 train / 468 val, `85/15 random`, seed 42, `drafter_0` excluded, dataset YAML "
      "`/home/bflcv/Projects/Components/data/cghd_16class.yaml`. No per-image split list exists in the repo, on claw, "
      "or in the checkpoint (its args only name the YAML); `detector/README.md` records that the YAML and val images "
      "are on no reachable machine.")
    w("- The CGHD copy on claw (Zenodo v12) has 24 x 96 = 2,304 images outside drafter_0 (3,341 total), which does not "
      "reconcile with 2,652 + 468 = 3,120, so the training image source/version itself is not identified.")
    w("- The 31 benchmark images come from drafters 1, 2, 3, 4, 6, 7, 9, 10, 12 and 21 (none from drafter_0), so each was "
      "eligible for training; under a uniform 85/15 split "
      "the expected number in the detector's training set is ~26 of 31. Membership of any specific image cannot be "
      "established. The e2e numbers above are therefore **not held-out** detector estimates; if anything they are "
      "optimistic for detection.\n")

    # ── per image
    w("## Per-image (conf 0.5)\n")
    w("| image | source/orient | GT elec | orig det-elec matched | GT boxes TP/FP/FN | orig TP/FP/FN | orig F1 | det704 TP/FP/FN | benchorient TP/FP/FN |")
    w("|---|---|---|---|---|---|---|---|---|")
    for i, r in d["per_image"].items():
        ar = r["arms"]
        t = lambda k: f"{ar[k]['tp']}/{ar[k]['fp']}/{ar[k]['fn']}"
        gm = r["geometry"]
        w(f"| {i} | {gm['source']}/{gm['transform']} | {r['n_gt_elec']} | {r['conf']['0.5']['orig']['elec_match_agnostic']} | "
          f"{t('gt_direct')} | {t('orig@0.5')} | {ar['orig@0.5']['f1']:.3f} | {t('det704@0.5')} | {t('benchorient@0.5')} |")
    open(a.out, "w").write("\n".join(L) + "\n")
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

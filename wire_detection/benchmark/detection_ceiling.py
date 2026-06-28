#!/usr/bin/env python3
"""Fair join vs VLM comparison: run join strategies on detected vs perfect GT wires.

Both modes use GT HDC component labels (same oracle detection the VLM overlay gives).
The gap between detected and perfect GT wires isolates the wire detector; comparing
perfect GT wires + GT labels to the saved VLM scores is the apples-to-apples join test.

Default strategies: scale_completion (promoted SOTA) and scale_completion_w (best F1 on
detected wires in join_newstrat_n31).

Run on claw (needs CGHD wire labels):
  ./.venv/bin/python -m wire_detection.benchmark.detection_ceiling \\
      --gt ground_truth/real_nets_verified.json \\
      --out docs/research/experiments/fair_join_comparison_n31.json

Local (detected wires only — set WIRE_GT_IMAGES to a dir with *_jpg.jpg symlinks):
  WIRE_GT_IMAGES=ground_truth/local_eval/images \\
  WIRE_HDC_BASE=roboflow_test2 \\
  uv run python -m wire_detection.benchmark.detection_ceiling --perfect-gt-skip
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES,
    GT_WIRE_LABELS,
    find_hdc_label,
    parse_components,
    parse_gt_wires,
)
from wire_detection.benchmark.join_eval_134 import detect_wires
from wire_detection.benchmark.join_eval_real_f1 import comp_pairs, gt_pairs, prf
from wire_detection.core.join_strategies import (
    DEFAULT_STRATEGY,
    make_pins,
    make_pins_junction_aware,
    run_strategy,
)

DEFAULT_STRATEGIES = ["scale_completion", "scale_completion_w"]
DEFAULT_VLM = "docs/research/experiments/vlm_clean_rerun_n31.json"


def score(wires, comps, keep, gtp, strategy: str):
    std = make_pins(wires, comps)
    junc = make_pins_junction_aware(wires, comps)
    _p, nl = run_strategy(strategy, wires, comps, std_pins=std, junc_pins=junc)
    pred = comp_pairs(nl, keep)
    p, r, f1 = prf(gtp, pred)
    return p, r, f1, (len(gtp & pred), len(pred - gtp), len(gtp - pred))


def run_mode(gt: dict, strategies: list[str], wire_mode: str) -> dict[str, dict]:
    acc = {s: ([], [], []) for s in strategies}
    cnt = {s: [] for s in strategies}
    n = 0
    for img_id, entry in gt.items():
        name = img_id.replace("_jpg", "")
        gray = cv2.imread(str(GT_IMAGES / f"{name}_jpg.jpg"), cv2.IMREAD_GRAYSCALE)
        hdc = find_hdc_label(name)
        if gray is None or hdc is None:
            print(f"  skip {name} (missing image/HDC labels)")
            continue
        h, w = gray.shape
        comps = parse_components(hdc.read_text(), w, h)
        keep = set(entry["electrical_idxs"])
        gtp = gt_pairs(entry["nets"], keep)

        if wire_mode == "detected":
            wires = detect_wires(gray, comps)
        else:
            wf = GT_WIRE_LABELS / f"{name}_jpg.txt"
            if not wf.exists():
                print(f"  skip {name} (missing GT wire labels)")
                continue
            wires = parse_gt_wires(wf.read_text(), w, h)

        for s in strategies:
            p, r, f1, c = score(wires, comps, keep, gtp, s)
            acc[s][0].append(p)
            acc[s][1].append(r)
            acc[s][2].append(f1)
            cnt[s].append(c)
        n += 1

    mean = lambda v: sum(v) / len(v) if v else 0.0
    out = {}
    for s in strategies:
        TP = sum(c[0] for c in cnt[s]); FP = sum(c[1] for c in cnt[s]); FN = sum(c[2] for c in cnt[s])
        P = TP / (TP + FP) if TP + FP else 1.0
        R = TP / (TP + FN) if TP + FN else 1.0
        F = 2 * P * R / (P + R) if P + R else 0.0
        out[s] = {"f1": F, "p": P, "r": R, "tp": TP, "fp": FP, "fn": FN,  # micro (primary)
                  "macro_f1": mean(acc[s][2]), "macro_p": mean(acc[s][0]), "macro_r": mean(acc[s][1]),
                  "counts": cnt[s], "n": n}
    return out


def print_table(title: str, rows: list[tuple[str, float, float, float]]) -> None:
    print(f"\n{title}")
    print(f"{'method':<22}{'meanF1':>8}{'meanP':>8}{'meanR':>8}")
    print("-" * 46)
    for name, f1, p, r in rows:
        print(f"{name:<22}{f1:>8.3f}{p:>8.3f}{r:>8.3f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt", default="ground_truth/real_nets_verified.json")
    ap.add_argument("--out", default="docs/research/experiments/fair_join_comparison_n31.json")
    ap.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES),
                    help="comma-separated join strategy names")
    ap.add_argument("--vlm-json", default=DEFAULT_VLM,
                    help="saved VLM N=31 scores (given GT boxes + wire overlay)")
    ap.add_argument("--perfect-gt-skip", action="store_true",
                    help="skip perfect-GT wire mode (when wire labels unavailable)")
    args = ap.parse_args()

    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    gt = json.load(open(args.gt))

    print(f"GT images: {GT_IMAGES}")
    print(f"GT wire labels: {GT_WIRE_LABELS}")
    print(f"Strategies: {strategies} (default SOTA: {DEFAULT_STRATEGY})")

    detected = run_mode(gt, strategies, "detected")
    perfect = {} if args.perfect_gt_skip else run_mode(gt, strategies, "perfect_gt")

    vlm = None
    vlm_path = Path(args.vlm_json)
    if vlm_path.exists():
        vlm_raw = json.load(open(vlm_path))
        mic = vlm_raw.get("micro", {})
        vlm = {"f1": mic.get("F1"), "p": mic.get("P"), "r": mic.get("R"),
               "macro_f1": vlm_raw.get("macro_f1"), "n": vlm_raw.get("n"),
               "note": ("Claude Opus 4.8, clean blind subagents (one per image), given the scan "
                        "with numbered GT component boxes and raw pixels (NO wire overlay); "
                        "not an end-to-end run. micro=pair-pooled, macro=mean per-image F1.")}

    rows = []
    for s in strategies:
        d = detected.get(s, {})
        if d.get("n"):
            rows.append((f"join/{s}/det", d["f1"], d["p"], d["r"]))
    for s in strategies:
        p = perfect.get(s, {})
        if p.get("n"):
            rows.append((f"join/{s}/oracle", p["f1"], p["p"], p["r"]))
    if vlm and vlm.get("f1") is not None:
        rows.append(("VLM/boxes-only", vlm["f1"], vlm["p"], vlm["r"]))
    rows.sort(key=lambda x: -x[1])
    print_table(f"Fair connectivity comparison (N={detected.get(strategies[0], {}).get('n', 0)} verified)", rows)

    if perfect and detected:
        sc = DEFAULT_STRATEGY
        if sc in detected and sc in perfect:
            gap = perfect[sc]["f1"] - detected[sc]["f1"]
            print(f"\nWire detector cost ({sc}): {gap:+.3f} F1")
        if vlm and sc in perfect:
            print(f"VLM vs {sc} oracle join: {vlm['f1'] - perfect[sc]['f1']:+.3f} F1")

    payload = {
        "n_verified": detected.get(strategies[0], {}).get("n", 0),
        "metric_note": ("All rows: component-pair F1 restricted to SPICE-active components, same metric "
                        "for join and VLM. Top-level f1/p/r are MICRO (pair-pooled across the 31 images); "
                        "macro_f1/macro_p/macro_r are the mean of per-image scores."),
        "fair_comparison_note": ("Join rows use GT HDC component labels + Sauvola-detected wires (det) or "
                                 "human-traced GT wire segments (oracle/ceiling). The VLM row uses the same "
                                 "GT component boxes (numbered on the scan) + raw pixels, NO wire overlay, "
                                 "via clean blind subagents. Both produce nets over the same component "
                                 "indices and are scored identically."),
        "strategies": strategies,
        "detected_wires_gt_components": detected,
        "perfect_gt_wires_gt_components": perfect or None,
        "vlm_boxes_only": vlm,
        "paths": {"gt_images": str(GT_IMAGES), "gt_wire_labels": str(GT_WIRE_LABELS)},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(payload, open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

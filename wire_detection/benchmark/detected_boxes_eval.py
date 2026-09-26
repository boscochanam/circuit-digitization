#!/usr/bin/env python3
"""End-to-end join F1 on DETECTED component boxes (trained YOLO26M-OBB model), scored
against the same 31-image human-verified net-level ground truth used by
join_eval_real_f1.py / detection_ceiling.py.

Why a wrapper instead of editing join_eval_real_f1.py: that script (and comp_pairs/
gt_pairs) assumes predicted-netlist component indices are IDENTICAL to the GT
component-list indices, because both are built by parsing the same HDC label file.
That invariant breaks the moment components come from a live detector: the model finds
a different number of boxes, in a different order, with no shared index space. To reuse
the existing pair-F1 scorer unmodified, this script IoU-matches each detected box to a
GT box and relabels the detected netlist's component indices to their matched GT index
before calling comp_pairs — unmatched detections get a sentinel id that can never
coincide with a real GT index (so they can only ever contribute false positives, never
spurious true positives).

Run (needs the trained model + ultralytics; CPU is fine, ~1-5s/image):
  /home/claw/venv-ml/bin/python -m wire_detection.benchmark.detected_boxes_eval \
      --gt ground_truth/real_nets_verified.json \
      --out /tmp/detected_boxes_results.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2

from wire_detection.benchmark.build_net_gt import (
    GT_IMAGES,
    electrical_indices,
    find_hdc_label,
    parse_components,
)
from wire_detection.benchmark.join_eval_134 import detect_wires
from wire_detection.benchmark.join_eval_real_f1 import comp_pairs, gt_pairs, prf
from wire_detection.core.component_classes import COMPONENT_TYPES
from wire_detection.core.join_strategies import make_pins, make_pins_junction_aware, run_strategy

DEFAULT_STRATEGIES = ["scale_completion", "scale_completion_w"]
MODEL_PATH = "models/component_detection/yolo26m_obb_16class_aug.pt"
CONF_THRESHOLD = 0.5

# The checkpoint embeds its OWN class-name table (``model.names``), and the index
# order is NOT stable across retrains. Do not hardcode index -> class: the shipped
# `yolo26m_obb_16class_aug.pt` reports
#   0 resistor, 1 terminal, 2 crossover, 3 capacitor, 4 diode, 5 transistor,
#   6 switch, 7 inductor, 8 voltage_source, 9 text, 10 junction, 11 gnd,
#   12 vss, 13 integrated_circuit, 14 operational_amplifier, 15 other
# whereas an earlier hardcoded table here listed 2=diode/15=crossover and agreed on
# only 1 of 16 indices. That silently relabelled every detected crossover as a diode.
# Resolve by NAME at load time instead.
MODEL_CLASS_NAME_TO_GT_CLASS = {
    "resistor": 37,                 # -> resistor
    "capacitor": 4,                 # -> capacitor-unpolarized
    "diode": 8,                     # -> diode
    "transistor": 47,               # -> transistor-BJT
    "inductor": 14,                 # -> inductor
    "voltage_source": 55,           # -> voltage-DC
    "integrated_circuit": 16,       # -> IC
    "operational_amplifier": 28,    # -> opamp
    "other": 51,                    # -> unknown
    "gnd": 13,                      # -> gnd
    "text": 44,                     # -> text
    "junction": 19,                 # -> junction
    "terminal": 43,                 # -> terminal
    "switch": 42,                   # -> switch
    "vss": 56,                      # -> vss
    "crossover": 5,                 # -> crossover
}
# Kept for backwards compatibility; prefer name-based resolution below.
TRAINED_MODEL_CLASSES = dict(MODEL_CLASS_NAME_TO_GT_CLASS)

_MODEL_CLASS_TO_GT_CLASS = None


def _model_to_gt_class_map(model) -> dict:
    """index -> GT class id, resolved from the checkpoint's own class names."""
    global _MODEL_CLASS_TO_GT_CLASS
    if _MODEL_CLASS_TO_GT_CLASS is None:
        names = getattr(model, "names", None) or {}
        unknown = []
        mapping = {}
        for idx, name in names.items():
            key = str(name).strip().lower()
            if key in MODEL_CLASS_NAME_TO_GT_CLASS:
                mapping[int(idx)] = MODEL_CLASS_NAME_TO_GT_CLASS[key]
            else:
                mapping[int(idx)] = 51          # unknown bucket
                unknown.append(name)
        if unknown:
            print(f"  warning: unmapped model classes -> 'unknown': {sorted(set(unknown))}")
        _MODEL_CLASS_TO_GT_CLASS = mapping
    return _MODEL_CLASS_TO_GT_CLASS


_YOLO_MODEL = None


def _get_model():
    global _YOLO_MODEL
    if _YOLO_MODEL is None:
        from ultralytics import YOLO
        _YOLO_MODEL = YOLO(MODEL_PATH)
    return _YOLO_MODEL


def detect_components(image_path: Path) -> list:
    """Run the trained YOLO-OBB model -> [(gt_scheme_cls, [4 verts], bbox)]."""
    model = _get_model()
    results = model(str(image_path), task="obb", conf=CONF_THRESHOLD, verbose=False)
    out = []
    for result in results:
        if result.obb is None:
            continue
        for i in range(len(result.obb.cls)):
            model_cls = int(result.obb.cls[i])
            x1, y1, x2, y2 = [int(v) for v in result.obb.xyxy[i].tolist()]
            poly = [(int(p[0]), int(p[1])) for p in result.obb.xyxyxyxy[i].tolist()]
            gt_cls = _model_to_gt_class_map(model).get(model_cls, 51)  # default: unknown
            out.append((gt_cls, poly, (x1, y1, x2, y2)))
    return out


def iou(a: tuple, b: tuple) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def match_detections_to_gt(det_comps: list, gt_comps: list, iou_thresh: float = 0.3):
    """Greedy max-IoU matching. Returns (det_idx -> gt_idx map, n_matched)."""
    pairs = []
    for di, d in enumerate(det_comps):
        for gi, g in enumerate(gt_comps):
            v = iou(d[2], g[2])
            if v >= iou_thresh:
                pairs.append((v, di, gi))
    pairs.sort(reverse=True)
    used_d, used_g = set(), set()
    mapping = {}
    for v, di, gi in pairs:
        if di in used_d or gi in used_g:
            continue
        used_d.add(di)
        used_g.add(gi)
        mapping[di] = gi
    return mapping, len(mapping)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt", default="ground_truth/real_nets_verified.json")
    ap.add_argument("--out", default="/tmp/detected_boxes_results.json")
    ap.add_argument("--out-md", default="/tmp/detected_boxes_results.md")
    ap.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    ap.add_argument("--iou-thresh", type=float, default=0.3)
    args = ap.parse_args()

    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    gt_all = json.load(open(args.gt))

    t0 = time.time()
    per_strategy_counts = {s: [] for s in strategies}          # (tp, fp, fn) per image
    per_strategy_pr = {s: ([], []) for s in strategies}        # (p, r) per image for macro
    per_image = {}
    det_counts = {"gt_electrical": 0, "det_electrical": 0, "matched_electrical": 0}

    for img_id, entry in gt_all.items():
        name = img_id.replace("_jpg", "")
        img_path = GT_IMAGES / f"{name}_jpg.jpg"
        gray = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        hdc = find_hdc_label(name)
        if gray is None or hdc is None:
            print(f"  skip {name} (missing image/labels)")
            continue
        h, w = gray.shape

        gt_comps = parse_components(hdc.read_text(), w, h)
        gt_keep = set(entry["electrical_idxs"])
        gtp = gt_pairs(entry["nets"], gt_keep)

        det_comps = detect_components(img_path)
        det_keep = set(electrical_indices(det_comps))

        mapping, n_matched = match_detections_to_gt(det_comps, gt_comps, args.iou_thresh)
        # component-detection quality bookkeeping (electrical subset only)
        matched_electrical = sum(1 for di, gi in mapping.items() if di in det_keep and gi in gt_keep)
        det_counts["gt_electrical"] += len(gt_keep)
        det_counts["det_electrical"] += len(det_keep)
        det_counts["matched_electrical"] += matched_electrical

        wires = detect_wires(gray, det_comps)
        std_pins = make_pins(wires, det_comps)
        junc_pins = make_pins_junction_aware(wires, det_comps)

        per_image[img_id] = {
            "gt_comps": len(gt_comps), "det_comps": len(det_comps),
            "gt_electrical": len(gt_keep), "det_electrical": len(det_keep),
            "matched_electrical": matched_electrical, "wires": len(wires),
        }
        for s in strategies:
            _pins, nl = run_strategy(s, wires, det_comps, std_pins=std_pins, junc_pins=junc_pins)
            # relabel predicted component indices to GT index space via the IoU match;
            # unmatched detections get a sentinel that can never equal a real GT idx.
            # build translated netlist pairs directly (mirrors comp_pairs but relabels ci)
            by_node: dict[int, set] = {}
            for (ci, _pin), nid in nl.pin_to_node.items():
                if ci in det_keep:
                    label = mapping.get(ci, f"unmatched_{name}_{ci}")
                    by_node.setdefault(nid, set()).add(label)
            from itertools import combinations
            pred = set()
            for comps in by_node.values():
                pred.update(combinations(sorted(comps, key=str), 2))
            # normalize pair order for comparability with gt pairs (ints only match ints)
            pred_int_pairs = set()
            for a, b in pred:
                if isinstance(a, int) and isinstance(b, int):
                    lo, hi = sorted((a, b))
                    pred_int_pairs.add((lo, hi))
                else:
                    pred_int_pairs.add((a, b))  # involves an unmatched detection -> can only be FP

            p, r, f1 = prf(gtp, pred_int_pairs)
            tp = len(gtp & pred_int_pairs); fp = len(pred_int_pairs - gtp); fn = len(gtp - pred_int_pairs)
            per_strategy_counts[s].append((tp, fp, fn))
            per_strategy_pr[s][0].append(p)
            per_strategy_pr[s][1].append(r)
            per_image[img_id][s] = {"f1": round(f1, 3), "p": round(p, 3), "r": round(r, 3),
                                     "tp": tp, "fp": fp, "fn": fn}
        print(f"  {name}: gt_comps={len(gt_comps)} det_comps={len(det_comps)} "
              f"matched_elec={matched_electrical}/{len(gt_keep)}")

    runtime = time.time() - t0
    mean = lambda v: sum(v) / len(v) if v else 0.0

    def micro(s):
        TP = sum(c[0] for c in per_strategy_counts[s])
        FP = sum(c[1] for c in per_strategy_counts[s])
        FN = sum(c[2] for c in per_strategy_counts[s])
        P = TP / (TP + FP) if TP + FP else 1.0
        R = TP / (TP + FN) if TP + FN else 1.0
        F = 2 * P * R / (P + R) if P + R else 0.0
        return {"f1": F, "p": P, "r": R, "tp": TP, "fp": FP, "fn": FN}

    macro_f1 = {s: mean([per_image[i][s]["f1"] for i in per_image]) for s in strategies}

    print(f"\nDetected-box join connectivity ({len(per_image)} images, vs net-GT)")
    print(f"{'strategy':<18}{'microF1':>9}{'microP':>8}{'microR':>8}{'macroF1':>9}")
    print("-" * 52)
    micro_all = {s: micro(s) for s in strategies}
    for s in strategies:
        mi = micro_all[s]
        print(f"{s:<18}{mi['f1']:>9.3f}{mi['p']:>8.3f}{mi['r']:>8.3f}{macro_f1[s]:>9.3f}")

    comp_p = det_counts["matched_electrical"] / det_counts["det_electrical"] if det_counts["det_electrical"] else 0.0
    comp_r = det_counts["matched_electrical"] / det_counts["gt_electrical"] if det_counts["gt_electrical"] else 0.0
    comp_f1 = 2 * comp_p * comp_r / (comp_p + comp_r) if (comp_p + comp_r) else 0.0
    print(f"\nComponent detection (electrical subset, IoU>={args.iou_thresh}): "
          f"P={comp_p:.3f} R={comp_r:.3f} F1={comp_f1:.3f} "
          f"(gt={det_counts['gt_electrical']} det={det_counts['det_electrical']} matched={det_counts['matched_electrical']})")
    print(f"Runtime: {runtime:.1f}s ({runtime / max(1, len(per_image)):.1f}s/image)")

    worst = sorted(per_image.items(), key=lambda kv: kv[1].get(strategies[0], {}).get("f1", 1.0))[:8]

    payload = {
        "strategies": strategies,
        "micro": micro_all,
        "macro_f1": macro_f1,
        "component_detection": {
            "electrical_gt": det_counts["gt_electrical"],
            "electrical_detected": det_counts["det_electrical"],
            "electrical_matched": det_counts["matched_electrical"],
            "precision": comp_p, "recall": comp_r, "f1": comp_f1,
            "iou_thresh": args.iou_thresh,
        },
        "runtime_sec": runtime,
        "n_images": len(per_image),
        "per_image": per_image,
        "per_image_worst": [{"image": k, **{s: v.get(s) for s in strategies},
                              "gt_electrical": v["gt_electrical"], "det_electrical": v["det_electrical"]}
                             for k, v in worst],
        # flattened top-level keys for the primary strategy, for convenient scripting
        "micro_f1": micro_all[strategies[0]]["f1"],
        "micro_p": micro_all[strategies[0]]["p"],
        "micro_r": micro_all[strategies[0]]["r"],
        "macro_f1_primary": macro_f1[strategies[0]],
        "n_components_gt": det_counts["gt_electrical"],
        "n_components_detected": det_counts["det_electrical"],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(payload, open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")

    md = [f"# Detected-box join eval (N={len(per_image)})\n",
          f"Model: `{MODEL_PATH}` conf={CONF_THRESHOLD}, IoU match thresh={args.iou_thresh}\n",
          f"Runtime: {runtime:.1f}s total, {runtime / max(1, len(per_image)):.2f}s/image\n",
          "\n## Join F1 (component-pair, detected boxes)\n",
          "| strategy | microF1 | microP | microR | macroF1 |",
          "|---|---|---|---|---|"]
    for s in strategies:
        mi = micro_all[s]
        md.append(f"| {s} | {mi['f1']:.3f} | {mi['p']:.3f} | {mi['r']:.3f} | {macro_f1[s]:.3f} |")
    md.append(f"\n## Component detection quality (electrical subset)\n")
    md.append(f"P={comp_p:.3f} R={comp_r:.3f} F1={comp_f1:.3f} "
              f"(gt={det_counts['gt_electrical']}, det={det_counts['det_electrical']}, matched={det_counts['matched_electrical']})\n")
    md.append("\n## Worst images (primary strategy)\n")
    md.append("| image | f1 | p | r | gt_elec | det_elec |")
    md.append("|---|---|---|---|---|---|")
    for k, v in worst:
        s0 = v.get(strategies[0], {})
        md.append(f"| {k} | {s0.get('f1')} | {s0.get('p')} | {s0.get('r')} | {v['gt_electrical']} | {v['det_electrical']} |")
    Path(args.out_md).write_text("\n".join(md) + "\n")
    print(f"wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

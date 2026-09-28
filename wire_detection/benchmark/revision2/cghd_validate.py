#!/usr/bin/env python3
"""Validate the CGHD-annotation connectivity reference against our human-verified nets.

On the images that are both in the 31-image human-verified benchmark
(ground_truth/real_nets_verified.json) and among the 257 CGHD samples with instance polygons:

 1. map CGHD polygons into the benchmark frame: normalise by the EXIF-corrected size, apply the
    per-image dihedral transform k (cghd_transform_probe.json; Roboflow flip/rot90 augmentation
    of the 704x704 copies), compare with our committed component labels
    (ground_truth/component_labels/<stem>_jpg.txt, normalised OBB -> AABB);
 2. one-to-one match (Hungarian on AABB IoU, accept IoU >= 0.3);
 3. component-pair agreement F1 of the CGHD reference (prediction) against the human nets
    (reference), over electrical components matched on both sides ("matched" view), and a
    "strict" view where every unmatched electrical component's pairs count as errors.

  PYTHONPATH=~/circuit-digitization python cghd_validate.py --ref out/cghd_ref_nets.json \
      --probe transform_probe.json --out out/cghd_validate.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cghd_common import dihedral_norm, is_electrical, list_samples, load_shapes, our_type_name  # noqa

REPO = Path.home() / "circuit-digitization"


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def pairs_of(nets, keep):
    out = set()
    for net in nets:
        m = sorted({int(c) for c, _ in net if int(c) in keep})
        out.update(combinations(m, 2))
    return out


def prf(gt, pred):
    tp = len(gt & pred); fp = len(pred - gt); fn = len(gt - pred)
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return dict(tp=tp, fp=fp, fn=fn, p=p, r=r, f1=f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--probe", required=True)
    ap.add_argument("--human", default=str(REPO / "ground_truth/real_nets_verified.json"))
    ap.add_argument("--labels", default=str(REPO / "ground_truth/component_labels"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    from wire_detection.core.component_classes import COMPONENT_TYPES
    ref = json.load(open(args.ref))
    human = json.load(open(args.human))
    probe = {r["stem"]: r for r in json.load(open(args.probe))}
    dmap = {s: d for d, s in list_samples()}
    stems = sorted(k[:-4] for k in human if k[:-4] in dmap)
    rows, TOT = [], {"matched": Counter(), "strict": Counter()}
    confusion = Counter()
    for stem in stems:
        h = human[f"{stem}_jpg"]
        pr = probe[stem]
        k = pr["k_box"]
        assert k is not None and pr["k_box"] == pr["k_ink"], stem
        shapes, _Wj, _Hj = load_shapes(dmap[stem], stem)
        W, H = ref[stem]["img_wh"]
        cg = []
        for s in shapes:
            p = s["points"] / [W, H]
            a = dihedral_norm(p[:, 0], p[:, 1], k)
            cg.append((a[0].min(), a[1].min(), a[0].max(), a[1].max()))
        ours = []
        for line in open(Path(args.labels) / f"{stem}_jpg.txt"):
            q = line.split()
            if len(q) != 9:
                continue
            c = list(map(float, q[1:]))
            ours.append((int(q[0]), (min(c[0::2]), min(c[1::2]), max(c[0::2]), max(c[1::2]))))
        assert len(ours) == h["n_components"], (stem, len(ours), h["n_components"])
        M = np.array([[iou(o[1], c) for c in cg] for o in ours])
        ri, ci = linear_sum_assignment(-M)
        match = {int(a): int(b) for a, b in zip(ri, ci) if M[a, b] >= 0.3}
        for a, b in match.items():
            confusion[(COMPONENT_TYPES[ours[a][0]], our_type_name(shapes[b]["label"]))] += 1
        hk = set(h["electrical_idxs"])
        rk = set(ref[stem]["electrical_idxs"])
        both = {a for a in hk if a in match and match[a] in rk}
        hp = pairs_of(h["nets"], both)
        hp_c = {tuple(sorted((match[a], match[b]))) for a, b in hp}
        rp = pairs_of(ref[stem]["nets"], {match[a] for a in both})
        m = prf(hp_c, rp)
        # strict: all human electrical pairs vs all ref electrical pairs (unmatched -> errors)
        inv = {v: kk for kk, v in match.items()}
        hp_all = {tuple(sorted((match.get(a, 10_000 + a), match.get(b, 10_000 + b))))
                  for a, b in pairs_of(h["nets"], hk)}
        rp_all = pairs_of(ref[stem]["nets"], rk)
        st = prf(hp_all, rp_all)
        for key, v in (("matched", m), ("strict", st)):
            for c in ("tp", "fp", "fn"):
                TOT[key][c] += v[c]
        fn_pairs = sorted(hp_c - rp); fp_pairs = sorted(rp - hp_c)
        rows.append({"stem": stem, "drafter": dmap[stem], "k": k,
                     "n_human_elec": len(hk), "n_ref_elec": len(rk), "n_both": len(both),
                     "unmatched_human_elec": sorted(a for a in hk if a not in both),
                     "mean_match_iou": float(np.mean([M[a, b] for a, b in match.items()])) if match else 0,
                     "ref_clean": ref[stem]["clean"], "ref_flags": ref[stem]["flags"],
                     "matched": m, "strict": st,
                     "fn_pairs_cghd_idx": fn_pairs, "fp_pairs_cghd_idx": fp_pairs,
                     "match_ours_to_cghd": {str(a): b for a, b in match.items()}})
        print(f"{stem:<12} {dmap[stem]:<11} k={k} elec h/r/both={len(hk)}/{len(rk)}/{len(both)} "
              f"matchedF1={m['f1']:.3f} (tp{m['tp']} fp{m['fp']} fn{m['fn']}) strictF1={st['f1']:.3f} "
              f"clean={ref[stem]['clean']}")

    def pooled(c):
        return prf_counts(c["tp"], c["fp"], c["fn"])
    summary = {}
    for key in ("matched", "strict"):
        for sub, sel in (("all", rows), ("ref_clean", [r for r in rows if r["ref_clean"]])):
            c = Counter()
            for r in sel:
                for q in ("tp", "fp", "fn"):
                    c[q] += r[key][q]
            summary[f"{key}_{sub}"] = {"n": len(sel), **prf_counts(c["tp"], c["fp"], c["fn"]),
                                       "macro_f1": float(np.mean([r[key]["f1"] for r in sel])) if sel else None,
                                       "n_exact": sum(r[key]["fp"] == 0 and r[key]["fn"] == 0 for r in sel)}
    conf_off = {f"{a} -> {b}": n for (a, b), n in confusion.items() if a != b}
    out = {"n_images": len(rows), "summary": summary, "class_confusion_offdiag": conf_off,
           "class_agreement": sum(n for (a, b), n in confusion.items() if a == b) / max(1, sum(confusion.values())),
           "rows": rows}
    json.dump(out, open(args.out, "w"), indent=1)
    for k2, v in summary.items():
        print(k2, json.dumps({kk: (round(x, 3) if isinstance(x, float) else x) for kk, x in v.items()}))
    print("class agreement", round(out["class_agreement"], 3), "offdiag", conf_off)


def prf_counts(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "p": p, "r": r, "f1": f}


if __name__ == "__main__":
    main()

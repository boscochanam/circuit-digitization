#!/usr/bin/env python3
"""Rescore stored predictions after a correction of the human-verified nets.

Some 31-image results cannot be rerun locally: the VLM answers (one model call per image), the
end-to-end detector runs (CGHD originals) and the reference-vs-human validation (CGHD v12
polygons). Each stores enough to rescore without rerunning: the VLM transcripts hold the
returned nets, and the e2e and validation rows hold their false-positive and false-negative
pairs (the VLM's returned nets are committed in vlm_clean_rerun_n31_nets.json, extracted from the
local session transcripts). For every image whose component pairs differ between --old-gt (the nets the stored
results were scored against) and --gt, this script reconstructs the predicted pairs, checks
that they reproduce the stored row under the old nets, and rescores them under the new nets.

  uv run python -m wire_detection.benchmark.revision2.rescore_labels --old-gt <old.json>

Rewrites in place (with a provenance note):
  docs/research/experiments/vlm_clean_rerun_n31.json
  docs/research/experiments/revision2/e2e_detected_n31.json
  docs/research/experiments/revision2/cghd_ref/cghd_validate_v2.json
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import re
from itertools import combinations
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
EXP = REPO / "docs/research/experiments"
TRANSCRIPTS = EXP.parent / "session-artifacts/3863951f-0f13-4730-8c2c-4af7f3011b71/subagents"
E2E_SEED = 20260928


def _cv(x):
    return int(x) if str(x).isdigit() else str(x)


def key(p):
    return tuple(sorted((_cv(x) for x in p), key=str))


def gt_pairs(entry, nets=None):
    keep = set(entry["electrical_idxs"])
    s = set()
    for n in (nets if nets is not None else entry["nets"]):
        s |= {key(p) for p in combinations(sorted({int(i) for i, _ in n if int(i) in keep}), 2)}
    return s


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else (1.0 if not fn else 0.0)
    r = tp / (tp + fn) if tp + fn else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def micro(rows):
    tp, fp, fn = (sum(r[k] for r in rows) for k in ("tp", "fp", "fn"))
    p, r, f = prf(tp, fp, fn)
    return {"f1": f, "p": p, "r": r, "tp": tp, "fp": fp, "fn": fn}


VLM_NETS = EXP / "vlm_clean_rerun_n31_nets.json"


def vlm_nets(stem):
    """Final nets the VLM returned for one image: the committed extract, else the transcript."""
    if VLM_NETS.exists():
        nets = json.load(open(VLM_NETS))["nets"]
        if f"{stem}_jpg" in nets:
            return nets[f"{stem}_jpg"]
    for f in glob.glob(str(TRANSCRIPTS / "*.jsonl")):
        lines = [json.loads(x) for x in open(f)]
        first = lines[0]["message"]["content"]
        first = first if isinstance(first, str) else json.dumps(first)
        if not re.search(rf"vlm_clean/{stem}(_jpg)?\.png", first):
            continue
        nets = None
        for ln in lines:
            m = ln.get("message", {})
            if m.get("role") != "assistant":
                continue
            c = m["content"]
            t = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict))
            found = re.findall(r'\{"nets":\s*(\[.*?\]\])\}', t)
            if found:
                nets = json.loads(found[-1])
        return nets
    raise SystemExit(f"no VLM transcript for {stem}")


def rescore_vlm(old, new, changed, note):
    path = EXP / "vlm_clean_rerun_n31.json"
    d = json.load(open(path))
    for r in d["rows"]:
        k = r["img"]
        if k not in changed:
            continue
        keep = set(new[k]["electrical_idxs"])
        P = {key(p) for n in vlm_nets(k[:-4]) for p in combinations(sorted({i for i in n if i in keep}), 2)}
        go, gn = gt_pairs(old[k]), gt_pairs(new[k])
        assert (len(go & P), len(P - go), len(go - P)) == (int(r["tp"]), int(r["fp"]), int(r["fn"])), k
        tp, fp, fn = len(gn & P), len(P - gn), len(gn - P)
        p, rr, f = prf(tp, fp, fn)
        r.update(tp=tp, fp=fp, fn=fn, P=round(p, 3), R=round(rr, 3), F1=round(f, 3))
    tp, fp, fn = (sum(int(r[x]) for r in d["rows"]) for x in ("tp", "fp", "fn"))
    p, rr, f = prf(tp, fp, fn)
    d["micro"] = {"P": p, "R": rr, "F1": f, "TP": tp, "FP": fp, "FN": fn}
    d["macro_f1"] = sum(float(r["F1"]) for r in d["rows"]) / len(d["rows"])
    d.setdefault("rescored", []).append(note)
    json.dump(d, open(path, "w"), indent=2)
    return d["micro"]


def rescore_pairs_row(r, go, gn, tp_key="tp"):
    FN = {key(p) for p in r["fn_pairs"]}
    FP = {key(p) for p in r["fp_pairs"]}
    assert len(go - FN) == r[tp_key] and len(FN) == r["fn"] and len(FP) == r["fp"]
    P = (go - FN) | FP
    return P, (len(gn & P), len(P - gn), len(gn - P))


def rescore_e2e(old, new, changed, note):
    path = EXP / "revision2/e2e_detected_n31.json"
    d = json.load(open(path))
    for k in changed:
        go, gn = gt_pairs(old[k]), gt_pairs(new[k])
        for r in d["per_image"][k]["arms"].values():
            P, (tp, fp, fn) = rescore_pairs_row(r, go, gn)
            p, rr, f = prf(tp, fp, fn)
            r.update(tp=tp, fp=fp, fn=fn, p=p, r=rr, f1=f,
                     fp_pairs=[list(map(str, x)) for x in sorted(P - gn, key=str)],
                     fn_pairs=[list(map(str, x)) for x in sorted(gn - P, key=str)])
    ids = list(d["per_image"])
    arms = list(d["summary"])
    cnt = {a: np.array([[d["per_image"][i]["arms"][a][x] for x in ("tp", "fp", "fn")] for i in ids]) for a in arms}
    idx = np.random.default_rng(E2E_SEED).integers(0, len(ids), size=(d["config"]["bootstrap_B"], len(ids)))

    def boot(c):
        tp, fp, fn = c[idx].sum(1).T
        den = 2 * tp + fp + fn
        return np.where(den > 0, 2 * tp / np.maximum(den, 1), 1.0)
    base = boot(cnt["gt_direct"])
    rows_gt = [d["per_image"][i]["arms"]["gt_direct"] for i in ids]
    for a in arms:
        rows = [d["per_image"][i]["arms"][a] for i in ids]
        mi, bs = micro(rows), boot(cnt[a])
        d["summary"][a] = mi | {
            "macro_f1": float(np.mean([r["f1"] for r in rows])),
            "micro_f1_ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
            "diff_vs_gt": mi["f1"] - micro(rows_gt)["f1"],
            "diff_vs_gt_ci95": [float(np.percentile(bs - base, 2.5)), float(np.percentile(bs - base, 97.5))]}
    d["config"].setdefault("rescored", []).append(note)
    json.dump(d, open(path, "w"), indent=1)
    return d["summary"]["orig@0.5"]


def rescore_validation(old, new, changed, note):
    path = EXP / "revision2/cghd_ref/cghd_validate_v2.json"
    d = json.load(open(path))
    for r in d["rows"]:
        k = r["stem"] + "_jpg"
        if k not in changed:
            continue
        m = {int(a): int(b) for a, b in r["match_ours_to_cghd"].items()}
        unmatched = {int(x) for x in r["unmatched_human_elec"]}

        def to_cghd(S):
            return {tuple(sorted((m[a], m[b]))) for a, b in S
                    if a in m and b in m and a not in unmatched and b not in unmatched}
        go, gn = to_cghd(gt_pairs(old[k])), to_cghd(gt_pairs(new[k]))
        for view in ("matched", "strict"):
            v = dict(r[view]); v["fn_pairs"], v["fp_pairs"] = r["fn_pairs_cghd_idx"], r["fp_pairs_cghd_idx"]
            P, (tp, fp, fn) = rescore_pairs_row(v, go, gn)
            p, rr, f = prf(tp, fp, fn)
            r[view] = {"tp": tp, "fp": fp, "fn": fn, "p": p, "r": rr, "f1": f}
        r["fn_pairs_cghd_idx"] = [list(x) for x in sorted(gn - P)]
        r["fp_pairs_cghd_idx"] = [list(x) for x in sorted(P - gn)]
    for view in ("matched", "strict"):
        for subset, rows in (("all", d["rows"]), ("ref_clean", [r for r in d["rows"] if r["ref_clean"]])):
            mi = micro([r[view] for r in rows])
            d["summary"][f"{view}_{subset}"] = {"n": len(rows), **mi,
                                                "macro_f1": float(np.mean([r[view]["f1"] for r in rows])),
                                                "n_exact": sum(r[view]["fp"] == 0 and r[view]["fn"] == 0 for r in rows)}
    d.setdefault("rescored", []).append(note)
    json.dump(d, open(path, "w"), indent=1)
    return d["summary"]["matched_all"], d["summary"]["matched_ref_clean"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-gt", required=True, help="nets the stored results were scored against")
    ap.add_argument("--gt", default=str(REPO / "ground_truth/real_nets_verified.json"))
    args = ap.parse_args()
    old, new = json.load(open(args.old_gt)), json.load(open(args.gt))
    changed = sorted(k for k in new if gt_pairs(old[k]) != gt_pairs(new[k]))
    note = f"{datetime.date.today()}: rescored {', '.join(c[:-4] for c in changed)} against corrected human nets"
    print("changed:", changed)
    print("VLM:", rescore_vlm(old, new, changed, note))
    s = rescore_e2e(old, new, changed, note)
    print("e2e orig@0.5:", {x: s[x] for x in ("f1", "tp", "fp", "fn", "micro_f1_ci95", "diff_vs_gt")})
    print("validation all / clean:", rescore_validation(old, new, changed, note))


if __name__ == "__main__":
    main()

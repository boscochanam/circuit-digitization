#!/usr/bin/env python3
"""Score the human audit of the CGHD-annotation reference (ground_truth/cghd_ref_audit/).

For every image the auditor marked verified: agreement of the original reference nets
(`_nets_original`) with the human-corrected nets, and every method's stored held-out
predictions (cghd_ref/cghd_eval_photo.json) against both. Per-image effort comes from
timing_log.jsonl (gaps between consecutive saves; gaps over 15 min count as breaks).

  python -m wire_detection.benchmark.revision2.cghd_audit_score
"""
import itertools, json, random, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUD = ROOT / "ground_truth" / "cghd_ref_audit"
EVAL = ROOT / "docs/research/experiments/revision2/cghd_ref/cghd_eval_photo.json"
OUT = ROOT / "docs/research/experiments/revision2/cghd_audit_results.json"
METHODS = {"ours": "scale_completion", "rescue_completion": "degree_budget", "scale_base": "graph_scale",
           "rescue_base": "graph_rescue", "radius_uf": "production", "hough": "hough_link44_reach48",
           "cc": "cc_detCCL_d15"}


def pairs(nets, keep):
    s = set()
    for n in nets:
        s |= set(itertools.combinations(sorted({i for i, _ in n if i in keep}), 2))
    return s


def prf(rows):
    tp, fp, fn = map(sum, zip(*rows))
    P = tp / (tp + fp) if tp + fp else 1.0
    R = tp / (tp + fn) if tp + fn else 1.0
    return {"f1": 2 * P * R / (P + R) if P + R else 0.0, "p": P, "r": R, "tp": tp, "fp": fp, "fn": fn}


def main():
    w = json.load(open(AUD / "real_nets_working.json"))
    im = json.load(open(EVAL))["images"]
    ver = sorted(k for k, e in w.items() if "human-verified" in e.get("source", ""))
    cnt = lambda g, p: (len(g & p), len(p - g), len(g - p))
    H, Rf = {}, {}
    for k in ver:
        keep = set(w[k]["electrical_idxs"])
        H[k], Rf[k] = pairs(w[k]["nets"], keep), pairs(w[k]["_nets_original"], keep)
    out = {"n_verified": len(ver), "images": ver,
           "reference_vs_human": prf([cnt(H[k], Rf[k]) for k in ver]),
           "exact_images": sum(H[k] == Rf[k] for k in ver),
           "changed": {k: {"added": sorted(map(list, H[k] - Rf[k])), "removed": sorted(map(list, Rf[k] - H[k]))}
                       for k in ver if H[k] != Rf[k]},
           "methods": {}, "paired_vs_ours_human": {}}
    P = {n: {k: {tuple(sorted(x)) for x in im[k[:-4]]["pred_pairs"][m]} for k in ver} for n, m in METHODS.items()}
    for n in METHODS:
        out["methods"][n] = {"vs_human": prf([cnt(H[k], P[n][k]) for k in ver]),
                             "vs_reference": prf([cnt(Rf[k], P[n][k]) for k in ver])}
    rng = random.Random(1)
    for n in METHODS:
        if n == "ours":
            continue
        d = []
        for _ in range(10000):
            s = [rng.choice(ver) for _ in ver]
            d.append(prf([cnt(H[k], P["ours"][k]) for k in s])["f1"] - prf([cnt(H[k], P[n][k]) for k in s])["f1"])
        d.sort()
        out["paired_vs_ours_human"][n] = {"diff": out["methods"]["ours"]["vs_human"]["f1"] - out["methods"][n]["vs_human"]["f1"],
                                           "ci95": [d[250], d[9750]]}
    t = [json.loads(l) for l in open(AUD / "timing_log.jsonl")]
    gaps = [b["t"] - a["t"] for a, b in zip(t, t[1:]) if b["t"] - a["t"] < 900]
    out["timing"] = {"n_intervals": len(gaps), "median_s": statistics.median(gaps), "mean_s": statistics.mean(gaps),
                     "note": "save-to-save gaps; >15 min excluded as breaks; the first image has no start time"}
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("n_verified", "reference_vs_human", "exact_images", "timing")}, indent=1))


if __name__ == "__main__":
    main()

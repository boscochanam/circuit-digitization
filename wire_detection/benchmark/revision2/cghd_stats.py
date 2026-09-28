#!/usr/bin/env python3
"""Statistics for the CGHD-annotation connectivity benchmark (pure numpy/scipy, no images).

Inputs (produced on claw, copied into docs/research/experiments/revision2/cghd_ref/):
  cghd_eval_photo.json / cghd_eval_seg.json   per-image tp/fp/fn + predicted pairs, every method
  ground_truth/cghd_ref/cghd_ref_nets.json    the reference (v2) incl. clean flags
  cghd_ref_nets_v1.json, cghd_ref_nets_v2_switch_closed.json   reference variants (re-scoring)
  cghd_validate_v2.json                       CGHD<->our component matching on the 17 overlaps
  ground_truth/real_nets_verified.json        human nets (only for the 17-overlap cross-check)

Subsets
  heldout_clean  (PRIMARY) reference-clean images whose stem is NOT one of the 31 human-verified
                 images (those 31 were used to select scale_completion and the baseline configs)
  heldout_strict_clean  additionally drops every picture of a drawing (C<n>_D<m>) that has a
                 picture among the 31
  all_clean, heldout_all (incl. flagged images), all
Conventions follow stats_strata.py (same bootstrap / permutation / Wilcoxon / Holm code, seeds).

  .venv/bin/python -m wire_detection.benchmark.revision2.cghd_stats
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

from wire_detection.benchmark.revision2.stats_strata import (
    SEED_BOOT, SEED_PERM, holm, micro_scalar, paired_bootstrap, per_image_prf, perm_test,
    stratum_summary, wilcoxon)

REPO = Path(__file__).resolve().parents[3]
EXP = REPO / "docs/research/experiments/revision2"
RAW = EXP / "cghd_ref"
REF = REPO / "ground_truth/cghd_ref/cghd_ref_nets.json"
OUT = EXP / "cghd_ref_benchmark.json"
OURS = "scale_completion"
PAPER_BASELINES = ["degree_budget", "graph_scale", "graph_rescue", "production",
                   "hough_link44_reach48", "cc_detCCL_d15"]


def drawing(stem):
    return re.match(r"(C\d+_D\d+)_P\d+", stem).group(1)


def rescore(E, ref, stems, method):
    C = []
    for s in stems:
        keep = set(ref[s]["electrical_idxs"])
        gt = set()
        for net in ref[s]["nets"]:
            m = sorted({int(c) for c, _ in net if int(c) in keep})
            gt.update(combinations(m, 2))
        pred = {tuple(p) for p in E["images"][s]["pred_pairs"][method]}
        C.append([len(gt & pred), len(pred - gt), len(gt - pred)])
    return np.array(C)


def analyse(E, ref, stems, methods, rng_seed=SEED_BOOT):
    M = {m: np.array([E["images"][s]["methods"][m] for s in stems]) for m in methods}
    res = {"n_images": len(stems), "n_ref_pairs": int(sum(E["images"][s]["n_ref_pairs"] for s in stems)),
           "methods": {}}
    for m, C in M.items():
        res["methods"][m] = stratum_summary(C, np.arange(len(stems)), np.random.default_rng(rng_seed))
        res["methods"][m]["n_exact"] = int(((C[:, 1] == 0) & (C[:, 2] == 0)).sum())
    comps = [m for m in PAPER_BASELINES if m in M]
    fo = per_image_prf(M[OURS])[:, 2]
    tests = {}
    for m in comps:
        fm = per_image_prf(M[m])[:, 2]
        d = fo - fm
        tests[m] = {"bootstrap_micro": paired_bootstrap(M[OURS], M[m], np.random.default_rng(SEED_BOOT)),
                    "permutation": perm_test(M[OURS], M[m], np.random.default_rng(SEED_PERM)),
                    "wilcoxon_f1": wilcoxon(fo, fm),
                    "win_tie_loss_f1": [int((d > 1e-12).sum()), int((np.abs(d) <= 1e-12).sum()),
                                        int((d < -1e-12).sum())]}
    for key, getter in [("bootstrap_micro", lambda t: t["bootstrap_micro"]["p_two_sided"]),
                        ("perm_micro", lambda t: t["permutation"]["p_micro_f1"]),
                        ("perm_meanf1", lambda t: t["permutation"]["p_mean_f1"]),
                        ("wilcoxon", lambda t: t["wilcoxon_f1"]["wilcox"]["p"])]:
        for m, a in zip(comps, holm([getter(tests[m]) for m in comps])):
            tests[m].setdefault("holm", {})[key] = a
    res["paired_tests_ours_minus_baseline"] = tests
    # oracle-best Hough / CC config on THIS subset (optimistic for the baseline)
    for fam in ("hough_", "cc_detCCL_"):
        best = max((m for m in methods if m.startswith(fam)), key=lambda m: micro_scalar(M[m])[2])
        res[f"oracle_best_{fam.rstrip('_')}"] = {"config": best, "micro_f1": micro_scalar(M[best])[2]}
    # per drafter
    byd = defaultdict(list)
    for i, s in enumerate(stems):
        byd[E["images"][s]["drafter"]].append(i)
    pdr = {}
    for d, idx in sorted(byd.items(), key=lambda kv: int(kv[0].split("_")[1])):
        row = {"n_images": len(idx)}
        for m in [OURS] + comps:
            P, R, F = micro_scalar(M[m][idx])
            row[m] = {"micro_f1": F, "micro_p": P, "micro_r": R}
        pdr[d] = row
    fs = np.array([pdr[d][OURS]["micro_f1"] for d in pdr])
    res["per_drafter"] = pdr
    res["per_drafter_spread_ours"] = {"n_drafters": len(pdr), "min": float(fs.min()), "max": float(fs.max()),
                                      "median": float(np.median(fs)),
                                      "iqr": [float(np.percentile(fs, 25)), float(np.percentile(fs, 75))],
                                      "n_drafters_ours_best_of_paper_methods":
                                          int(sum(pdr[d][OURS]["micro_f1"] >= max(pdr[d][m]["micro_f1"] for m in comps) - 1e-12
                                                  for d in pdr))}
    # strata by electrical count
    ne = np.array([E["images"][s]["n_electrical"] for s in stems])
    sdef = {"electrical<=5": ne <= 5, "electrical6-9": (ne >= 6) & (ne <= 9),
            "electrical10-19": (ne >= 10) & (ne <= 19), "electrical>=20": ne >= 20}
    st = {}
    for name, mask in sdef.items():
        idx = np.where(mask)[0]
        if len(idx) == 0:
            continue
        st[name] = {m: stratum_summary(M[m], idx, np.random.default_rng(SEED_BOOT)) for m in [OURS] + comps}
    res["strata"] = st
    return res


def main():
    ref = json.load(open(REF))
    stems_all = sorted(k for k in ref if not k.startswith("_"))
    human = json.load(open(REPO / "ground_truth/real_nets_verified.json"))
    h31 = {k[:-4] for k in human}
    d31 = {drawing(s) for s in h31}
    clean = {s for s in stems_all if ref[s]["clean"]}
    subsets = {
        "heldout_clean": [s for s in stems_all if s in clean and s not in h31],
        "heldout_strict_clean": [s for s in stems_all if s in clean and drawing(s) not in d31],
        "all_clean": [s for s in stems_all if s in clean],
        "heldout_all": [s for s in stems_all if s not in h31],
        "all": stems_all,
        "overlap17_clean": [s for s in stems_all if s in clean and s in h31],
    }
    out = {"reference": str(REF.relative_to(REPO)), "primary_subset": "heldout_clean",
           "primary_input": "photo", "subset_sizes": {k: len(v) for k, v in subsets.items()},
           "n_drafters": {k: len({ref[s]["drafter"] for s in v}) for k, v in subsets.items()},
           "conditions": {}}
    for cond in ("photo", "seg"):
        E = json.load(open(RAW / f"cghd_eval_{cond}.json"))
        methods = list(next(iter(E["images"].values()))["methods"])
        out["conditions"][cond] = {"input": E["input"], "long_side": E["long_side"],
                                   "subsets": {k: analyse(E, ref, v, methods) for k, v in subsets.items()}}
        # reference-variant sensitivity (re-score stored predictions), primary subset only
        sens = {}
        for var in ("v1", "v2_switch_closed"):
            rv = json.load(open(RAW / f"cghd_ref_nets_{var}.json"))
            idx = [s for s in stems_all if rv[s]["clean"] and s not in h31]
            sens[var] = {"n_images": len(idx),
                         **{m: dict(zip(("micro_p", "micro_r", "micro_f1"),
                                        micro_scalar(rescore(E, rv, idx, m)))) for m in [OURS] + PAPER_BASELINES}}
        out["conditions"][cond]["reference_variant_sensitivity"] = sens
    # 17-overlap cross-check: same stored predictions (photo input) scored against the HUMAN nets
    V = json.load(open(RAW / "cghd_validate_v2.json"))
    E = json.load(open(RAW / "cghd_eval_photo.json"))
    cross = {m: {"vs_human": [0, 0, 0], "vs_cghd_ref": [0, 0, 0]} for m in [OURS] + PAPER_BASELINES}
    for row in V["rows"]:
        s = row["stem"]
        h = human[f"{s}_jpg"]
        mp = {int(a): b for a, b in row["match_ours_to_cghd"].items()}
        rk = set(ref[s]["electrical_idxs"])
        both = {mp[a] for a in h["electrical_idxs"] if a in mp and mp[a] in rk}
        hp = set()
        for net in h["nets"]:
            mem = sorted({mp[int(c)] for c, _ in net if int(c) in mp and mp[int(c)] in both})
            hp.update(combinations(mem, 2))
        rp = set()
        for net in ref[s]["nets"]:
            mem = sorted({int(c) for c, _ in net if int(c) in both})
            rp.update(combinations(mem, 2))
        for m in cross:
            pred = {tuple(p) for p in E["images"][s]["pred_pairs"][m] if p[0] in both and p[1] in both}
            for key, g in (("vs_human", hp), ("vs_cghd_ref", rp)):
                c = cross[m][key]
                c[0] += len(g & pred); c[1] += len(pred - g); c[2] += len(g - pred)
    out["overlap17_photo_scored_against_human_vs_reference"] = {
        m: {k: {"tp": v[0], "fp": v[1], "fn": v[2], "micro_f1": micro_scalar(np.array([v]))[2]} for k, v in d.items()}
        for m, d in cross.items()}
    json.dump(out, open(OUT, "w"), indent=1)
    # console summary
    for cond in ("photo", "seg"):
        for sub in ("heldout_clean", "heldout_strict_clean", "all_clean", "all"):
            r = out["conditions"][cond]["subsets"][sub]
            print(f"\n[{cond}] {sub}: n={r['n_images']} pairs={r['n_ref_pairs']}")
            for m in [OURS] + PAPER_BASELINES:
                q = r["methods"][m]
                t = r["paired_tests_ours_minus_baseline"].get(m)
                extra = "" if t is None else (f" diff={t['bootstrap_micro']['diff']:+.3f} "
                                              f"CI[{t['bootstrap_micro']['ci95'][0]:+.3f},{t['bootstrap_micro']['ci95'][1]:+.3f}] "
                                              f"pHolm(boot)={t['holm']['bootstrap_micro']:.4f} pHolm(perm)={t['holm']['perm_micro']:.4f}")
                print(f"  {m:<22} F1={q['micro_f1']:.3f} [{q['micro_f1_ci95'][0]:.3f},{q['micro_f1_ci95'][1]:.3f}] "
                      f"P={q['micro_p']:.3f} R={q['micro_r']:.3f} macro={q['macro_f1']:.3f} "
                      f"tp/fp/fn={q['tp']}/{q['fp']}/{q['fn']}{extra}")
            print("  oracle:", r["oracle_best_hough"], r["oracle_best_cc_detCCL"], "drafters:", r["per_drafter_spread_ours"])
    print("\nsensitivity", json.dumps(out["conditions"]["photo"]["reference_variant_sensitivity"], indent=0)[:1500])
    print("\ncross17", json.dumps(out["overlap17_photo_scored_against_human_vs_reference"]))
    print("wrote", OUT)


if __name__ == "__main__":
    main()

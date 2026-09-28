#!/usr/bin/env python3
"""Revision-2 (Access-2026-33821) statistics: paired significance tests, complexity strata,
and component-size dispersion for the 31-image human-verified connectivity benchmark.

Answers reviewer points R2-1 (rigorous statistical testing), R1-5 (recall on complex
circuits) and R2-6 (intra-image component-size variation).

Inputs (all committed, no images needed):
  docs/research/experiments/join_micro_n31.json        per-image tp/fp/fn, 5 join strategies
  docs/research/experiments/cc_detected_micro_n31.json per-image counts (GT order), CCL join
  docs/research/experiments/vlm_clean_rerun_n31.json   per-image rows, Claude VLM
  docs/research/experiments/revision2/per_image_inputs_n31.json
        per-image Hough counts (all configs) + component-size stats; produced on claw by
        wire_detection/benchmark/revision2/collect_per_image.py (reproduces the pooled
        hough_micro_n31.json counts exactly).
  ground_truth/real_nets_verified.json                  image order / electrical idxs

Outputs:
  docs/research/experiments/revision2/stats_strata_n31.json   every number + per-image tables
  (the .md summary next to it is written by hand from this JSON)

Rerun (pure numpy/scipy, seconds):
  .venv/bin/python -m wire_detection.benchmark.revision2.stats_strata

Conventions
  * Per-image P/R/F1 follow join_eval_real_f1.prf exactly (empty pred on non-empty GT -> P=0).
  * micro-F1 pools tp/fp/fn over images; macro-F1 is the mean of per-image F1.
  * All differences are ours (scale_completion) minus the comparator; positive = ours better.
  * Paired bootstrap: resample image indices with replacement, B=10000, numpy
    default_rng(SEED_BOOT); 95% percentile CI; two-sided p = min(1, 2*min(#{d*<=0}, #{d*>=0})+1)/(B+1)
    (percentile-inversion p-value).
  * Paired permutation (sign-flip / label-swap within image): exact enumeration over images whose
    two methods differ when that set has <= 22 images, else Monte Carlo 100k (seed SEED_PERM).
    Run for two statistics: mean per-image F1 difference and pooled micro-F1 difference.
    p = #{|T*| >= |T_obs| - 1e-12} / #perms (exact) or (+1)/(M+1) (MC).
  * Wilcoxon signed-rank on per-image F1: zero_method='wilcox' (zero differences dropped,
    primary) and 'pratt' (zeros kept in ranking); scipy chooses exact vs normal approx.
  * Holm-Bonferroni applied within each test type across the 7 comparisons.
  * Hough and CCL comparators use the configuration with the best micro-F1 ON THIS TEST SET
    (link44_reach48, detCCL_d15): an optimistic, oracle-tuned baseline.
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
from scipy import stats

REPO = Path(__file__).resolve().parents[3]
EXP = REPO / "docs/research/experiments"
OUT = EXP / "revision2/stats_strata_n31.json"
B = 10000
SEED_BOOT = 20260928
SEED_PERM = 20260929
MC_PERMS = 100_000
EXACT_MAX = 22
OURS = "scale_completion"
HOUGH_BEST = "link44_reach48"
CC_BEST = "detCCL_d15"
LARGE_CLASSES = {16, 17, 18, 28, 29, 31, 36, 46}  # IC, NE555, V-reg, opamp(s), optocoupler, relay, transformer
COMPONENT_TYPES = None  # filled lazily from wire_detection.core.component_classes


# ---------------------------------------------------------------- metrics
def prf_counts(tp, fp, fn):
    ngt, npred = tp + fn, tp + fp
    if ngt == 0 and npred == 0:
        return 1.0, 1.0, 1.0
    p = tp / npred if npred else (1.0 if ngt == 0 else 0.0)
    r = tp / ngt if ngt else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def micro(C):
    """C: (n,3) array of tp,fp,fn -> (P,R,F1) pooled."""
    TP, FP, FN = C.sum(axis=-2).T if C.ndim == 3 else C.sum(axis=0)
    P = np.where(TP + FP > 0, TP / np.maximum(TP + FP, 1), 1.0)
    R = np.where(TP + FN > 0, TP / np.maximum(TP + FN, 1), 1.0)
    F = np.where(P + R > 0, 2 * P * R / np.maximum(P + R, 1e-300), 0.0)
    return P, R, F


def micro_scalar(C):
    P, R, F = micro(np.asarray(C))
    return float(P), float(R), float(F)


def per_image_prf(C):
    return np.array([prf_counts(*map(int, c)) for c in C])


# ---------------------------------------------------------------- loading
def load():
    gt = json.load(open(REPO / "ground_truth/real_nets_verified.json"))
    imgs = list(gt.keys())
    J = json.load(open(EXP / "join_micro_n31.json"))
    assert list(J["per_image"].keys()) == imgs, "join per_image order != GT order"
    CC = json.load(open(EXP / "cc_detected_micro_n31.json"))
    V = {r["img"]: r for r in json.load(open(EXP / "vlm_clean_rerun_n31.json"))["rows"]}
    H = json.load(open(EXP / "revision2/per_image_inputs_n31.json"))
    assert list(H["images"].keys()) == imgs
    methods = {}
    for s in ["scale_completion", "degree_budget", "graph_scale", "graph_rescue", "production"]:
        methods[s] = np.array([[J["per_image"][im][s][k] for k in ("tp", "fp", "fn")] for im in imgs])
    # CC counts are stored in GT order; cross-check against ours
    assert np.array_equal(np.array(CC["ours_scale_completion"]["counts"]), methods[OURS]), \
        "cc_detected counts order mismatch"
    methods[f"cc_{CC_BEST}"] = np.array(CC[CC_BEST]["counts"])
    methods[f"hough_{HOUGH_BEST}"] = np.array([H["images"][im]["hough"][HOUGH_BEST] for im in imgs])
    methods["vlm"] = np.array([[V[im]["tp"], V[im]["fp"], V[im]["fn"]] for im in imgs])
    # consistency: every method's tp+fn equals the GT pair count
    npairs = np.array([H["images"][im]["n_gt_pairs"] for im in imgs])
    for m, C in methods.items():
        assert np.array_equal(C[:, 0] + C[:, 2], npairs), f"{m}: tp+fn != n_gt_pairs"
    committed = {
        **{s: (J["micro"][s], J["macro"][s]) for s in J["micro"]},
        f"cc_{CC_BEST}": (CC[CC_BEST]["micro"], CC[CC_BEST]["macro"]),
        f"hough_{HOUGH_BEST}": tuple(json.load(open(EXP / "hough_micro_n31.json"))["configs"][HOUGH_BEST][k]
                                     for k in ("micro", "macro")),
        "vlm": ({"f1": json.load(open(EXP / "vlm_clean_rerun_n31.json"))["micro"]["F1"]},
                {"f1": json.load(open(EXP / "vlm_clean_rerun_n31.json"))["macro_f1"]}),
    }
    return gt, imgs, methods, H, committed


# ---------------------------------------------------------------- tests
def boot_idx(n, rng, b=B):
    return rng.integers(0, n, size=(b, n))


def paired_bootstrap(Ca, Cb, rng):
    idx = boot_idx(len(Ca), rng)
    _, _, Fa = micro(Ca[idx]); _, _, Fb = micro(Cb[idx])
    d = Fa - Fb
    obs = micro_scalar(Ca)[2] - micro_scalar(Cb)[2]
    lo, hi = np.percentile(d, [2.5, 97.5])
    p = min(1.0, (2 * min((d <= 0).sum(), (d >= 0).sum()) + 1) / (B + 1))
    return {"diff": obs, "ci95": [float(lo), float(hi)], "p_two_sided": float(p),
            "frac_boot_diff_le0": float((d <= 0).mean())}


def perm_test(Ca, Cb, rng):
    """Within-image label swap. Returns p for mean-F1-diff and micro-F1-diff statistics."""
    fa, fb = per_image_prf(Ca)[:, 2], per_image_prf(Cb)[:, 2]
    diff_img = np.array([not np.array_equal(a, b) for a, b in zip(Ca, Cb)])
    k = int(diff_img.sum())
    obs_mean = float((fa - fb).mean())
    obs_micro = micro_scalar(Ca)[2] - micro_scalar(Cb)[2]
    same = ~diff_img
    base = Ca[same].sum(axis=0)  # identical in both arms
    A, Bm = Ca[diff_img], Cb[diff_img]
    dd = (fa - fb)[diff_img]
    if k <= EXACT_MAX:
        signs = np.array(list(itertools.product([1, -1], repeat=k)), dtype=np.int8) if k else np.ones((1, 0), np.int8)
        exact = True
    else:
        signs = rng.choice(np.array([1, -1], np.int8), size=(MC_PERMS, k))
        exact = False
    # mean-F1 statistic
    T = (signs * dd).sum(axis=1) / len(fa)
    # micro statistic: sign +1 keeps assignment, -1 swaps a<->b for that image (chunked)
    Tm = np.empty(len(signs))
    for c0 in range(0, len(signs), 65536):
        keep = (signs[c0:c0 + 65536] == 1)[:, :, None]
        armA = np.where(keep, A[None], Bm[None]).sum(axis=1) + base
        armB = np.where(keep, Bm[None], A[None]).sum(axis=1) + base
        Tm[c0:c0 + 65536] = micro(armA[:, None, :])[2] - micro(armB[:, None, :])[2]
    def pval(Tstar, obs):
        c = int((np.abs(Tstar) >= abs(obs) - 1e-12).sum())
        return c / len(Tstar) if exact else (c + 1) / (len(Tstar) + 1)
    return {"n_images_differing": k, "exact": exact, "n_perms": int(len(signs)),
            "mean_f1_diff": obs_mean, "p_mean_f1": pval(T, obs_mean),
            "micro_f1_diff": obs_micro, "p_micro_f1": pval(Tm, obs_micro)}


def wilcoxon(fa, fb):
    d = fa - fb
    nz = int((np.abs(d) > 1e-12).sum())
    out = {"n_nonzero": nz, "n_zero": int(len(d) - nz)}
    for zm in ("wilcox", "pratt"):
        if nz == 0:
            out[zm] = {"stat": None, "p": 1.0}; continue
        try:
            r = stats.wilcoxon(fa, fb, zero_method=zm, alternative="two-sided")
            out[zm] = {"stat": float(r.statistic), "p": float(r.pvalue)}
        except ValueError as e:
            out[zm] = {"stat": None, "p": None, "err": str(e)}
    # exact variant on the nonzero diffs (ties among |d| may exist; scipy falls back if so)
    return out


def holm(ps):
    ps = np.asarray(ps, float); m = len(ps); order = np.argsort(ps)
    adj = np.empty(m); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * ps[i])); adj[i] = run
    return adj.tolist()


def stratum_summary(C, idx, rng, b=B):
    C = C[idx]; n = len(C)
    P, R, F = micro_scalar(C)
    bi = rng.integers(0, n, size=(b, n))
    bP, bR, bF = micro(C[bi])
    ci = lambda x: [float(v) for v in np.percentile(x, [2.5, 97.5])]
    pf = per_image_prf(C)
    return {"n_images": n, "tp": int(C[:, 0].sum()), "fp": int(C[:, 1].sum()), "fn": int(C[:, 2].sum()),
            "micro_p": P, "micro_r": R, "micro_f1": F,
            "micro_p_ci95": ci(bP), "micro_r_ci95": ci(bR), "micro_f1_ci95": ci(bF),
            "macro_f1": float(pf[:, 2].mean()), "macro_r": float(pf[:, 1].mean())}


def group_diff_test(C, g1, g2, rng, which=1):
    """Unpaired: micro metric (0=P,1=R,2=F1) in group g2 minus group g1; bootstrap CI within
    groups + permutation p (shuffle group labels, MC 100k)."""
    g1, g2 = np.asarray(g1), np.asarray(g2)
    obs = micro_scalar(C[g2])[which] - micro_scalar(C[g1])[which]
    b1 = rng.integers(0, len(g1), size=(B, len(g1))); b2 = rng.integers(0, len(g2), size=(B, len(g2)))
    d = micro(C[g2][b2])[which] - micro(C[g1][b1])[which]
    allidx = np.concatenate([g1, g2]); n2 = len(g2)
    cnt = 0
    perm_rng = np.random.default_rng(SEED_PERM + 7)
    Tp = np.empty(MC_PERMS)
    for i in range(MC_PERMS // 1000):
        P = np.argsort(perm_rng.random((1000, len(allidx))), axis=1)
        sel = allidx[P]
        Tp[i*1000:(i+1)*1000] = micro(C[sel[:, :n2]])[which] - micro(C[sel[:, n2:]])[which]
    cnt = int((np.abs(Tp) >= abs(obs) - 1e-12).sum())
    return {"diff_g2_minus_g1": float(obs), "ci95": [float(v) for v in np.percentile(d, [2.5, 97.5])],
            "perm_p_two_sided": (cnt + 1) / (MC_PERMS + 1)}


def partial_spearman(x, y, z):
    """Rank-based partial correlation of x,y controlling z (Pearson on residualised ranks);
    p-value from t with n-3 df."""
    rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
    res = lambda a: a - np.polyval(np.polyfit(rz, a, 1), rz)
    r = float(np.corrcoef(res(rx), res(ry))[0, 1]); n = len(x)
    t = r * math.sqrt((n - 3) / max(1e-300, 1 - r * r))
    return {"rho_partial": r, "p": float(2 * stats.t.sf(abs(t), n - 3)), "controlling": "n_electrical"}


def spearman(x, y):
    r = stats.spearmanr(x, y)
    return {"rho": float(r.statistic), "p": float(r.pvalue)}


# ---------------------------------------------------------------- main
def main():
    global COMPONENT_TYPES
    try:
        from wire_detection.core.component_classes import COMPONENT_TYPES as CT
        COMPONENT_TYPES = CT
    except Exception:
        COMPONENT_TYPES = {}
    gt, imgs, M, H, committed = load()
    n = len(imgs)
    rng = np.random.default_rng(SEED_BOOT)
    res = {"config": {"B": B, "seed_bootstrap": SEED_BOOT, "seed_permutation": SEED_PERM,
                      "mc_perms": MC_PERMS, "exact_perm_max_images": EXACT_MAX, "n_images": n,
                      "ours": OURS, "hough_config": HOUGH_BEST, "cc_config": CC_BEST,
                      "note_baseline_tuning": "hough/cc configs are the best-micro-F1 config on this "
                                              "same test set (oracle-tuned, favourable to the baseline)"}}

    # ---- 1. reproduction
    rep = {}
    for m, C in M.items():
        P, R, F = micro_scalar(C); pf = per_image_prf(C)
        cm, cM = committed[m]
        rep[m] = {"micro_f1": F, "micro_p": P, "micro_r": R, "macro_f1": float(pf[:, 2].mean()),
                  "committed_micro_f1": cm["f1"], "committed_macro_f1": cM["f1"],
                  "micro_match": abs(F - cm["f1"]) < 1e-9,
                  # committed macros were averaged over 3-dp-rounded per-image F1s -> 5e-4 tolerance
                  "macro_match": abs(pf[:, 2].mean() - cM["f1"]) < 5e-4,
                  "n_images_exact": int(((C[:, 1] == 0) & (C[:, 2] == 0)).sum())}
    res["reproduction"] = rep

    # ---- 2. paired tests
    comps = [m for m in M if m != OURS]
    fo = per_image_prf(M[OURS])[:, 2]
    tests = {}
    for m in comps:
        fm = per_image_prf(M[m])[:, 2]
        d = fo - fm
        tests[m] = {
            "bootstrap_micro": paired_bootstrap(M[OURS], M[m], np.random.default_rng(SEED_BOOT)),
            "permutation": perm_test(M[OURS], M[m], np.random.default_rng(SEED_PERM)),
            "wilcoxon_f1": wilcoxon(fo, fm),
            "win_tie_loss_f1": [int((d > 1e-12).sum()), int((np.abs(d) <= 1e-12).sum()), int((d < -1e-12).sum())],
            "win_tie_loss_counts_identical": int(sum(np.array_equal(a, b) for a, b in zip(M[OURS], M[m]))),
        }
    for key, getter in [("bootstrap_micro", lambda t: t["bootstrap_micro"]["p_two_sided"]),
                        ("perm_micro", lambda t: t["permutation"]["p_micro_f1"]),
                        ("perm_meanf1", lambda t: t["permutation"]["p_mean_f1"]),
                        ("wilcoxon", lambda t: t["wilcoxon_f1"]["wilcox"]["p"])]:
        adj = holm([getter(tests[m]) for m in comps])
        for m, a in zip(comps, adj):
            tests[m].setdefault("holm", {})[key] = a
    res["paired_tests"] = tests

    # ---- 3. jackknife
    loo = np.array([micro_scalar(np.delete(M[OURS], i, axis=0))[2] for i in range(n)])
    loo_diff = {m: [float(min(v)), float(max(v))] for m, v in
                ((m, [micro_scalar(np.delete(M[OURS], i, 0))[2] - micro_scalar(np.delete(M[m], i, 0))[2]
                      for i in range(n)]) for m in comps)}
    res["jackknife_ours"] = {"micro_f1_min": float(loo.min()), "micro_f1_max": float(loo.max()),
                             "argmin_image_dropped": imgs[int(loo.argmin())],
                             "argmax_image_dropped": imgs[int(loo.argmax())],
                             "per_image": dict(zip(imgs, loo.round(4).tolist())),
                             "diff_range_vs_comparators": loo_diff,
                             "sign_of_diff_constant": {m: (r[0] > 0) == (r[1] > 0) for m, r in loo_diff.items()}}

    # ---- 4. complexity strata
    ne = np.array([H["images"][im]["n_electrical"] for im in imgs])
    npairs = np.array([H["images"][im]["n_gt_pairs"] for im in imgs])
    nx = np.array([H["images"][im]["n_crossover"] for im in imgs])
    nall = np.array([H["images"][im]["n_components_all"] for im in imgs])
    strata_defs = {
        "electrical<=5": np.where(ne <= 5)[0], "electrical6-9": np.where((ne >= 6) & (ne <= 9))[0],
        "electrical>=10": np.where(ne >= 10)[0], "electrical<=9": np.where(ne <= 9)[0],
        "pairs<=8": np.where(npairs <= 8)[0], "pairs9-22": np.where((npairs >= 9) & (npairs <= 22))[0],
        "pairs>=23": np.where(npairs >= 23)[0],
        "crossover=0": np.where(nx == 0)[0], "crossover>=1": np.where(nx >= 1)[0],
    }
    strata = {}
    for sname, idx in strata_defs.items():
        strata[sname] = {"images": [imgs[i] for i in idx],
                         "methods": {m: stratum_summary(M[m], idx, np.random.default_rng(SEED_BOOT)) for m in M}}
        # paired ours-minus-comparator micro-F1 within stratum
        strata[sname]["paired_diff_vs_ours"] = {
            m: paired_bootstrap(M[OURS][idx], M[m][idx], np.random.default_rng(SEED_BOOT)) for m in comps}
    res["strata"] = strata
    res["strata_group_tests"] = {
        m: {"recall_electrical>=10_minus_<=5": group_diff_test(M[m], strata_defs["electrical<=5"],
                                                              strata_defs["electrical>=10"],
                                                              np.random.default_rng(SEED_BOOT), which=1),
            "f1_electrical>=10_minus_<=5": group_diff_test(M[m], strata_defs["electrical<=5"],
                                                          strata_defs["electrical>=10"],
                                                          np.random.default_rng(SEED_BOOT), which=2),
            "recall_crossover>=1_minus_0": group_diff_test(M[m], strata_defs["crossover=0"],
                                                          strata_defs["crossover>=1"],
                                                          np.random.default_rng(SEED_BOOT), which=1)}
        for m in [OURS, "degree_budget", "graph_scale", f"hough_{HOUGH_BEST}", "vlm"]}
    corr = {}
    for m in M:
        pf = per_image_prf(M[m])
        corr[m] = {"n_electrical_vs_recall": spearman(ne, pf[:, 1]),
                   "n_electrical_vs_f1": spearman(ne, pf[:, 2]),
                   "n_electrical_vs_precision": spearman(ne, pf[:, 0]),
                   "n_gt_pairs_vs_recall": spearman(npairs, pf[:, 1]),
                   "n_gt_pairs_vs_f1": spearman(npairs, pf[:, 2]),
                   "n_crossover_vs_recall": spearman(nx, pf[:, 1])}
    res["complexity_spearman"] = corr

    # ---- 5. size dispersion
    disp = {}
    for i, im in enumerate(imgs):
        h = H["images"][im]
        da, de = np.array(h["diags_all"]), np.array(h["diags_electrical"])
        s = h["scale_s"]
        ecl = h["electrical_classes"]
        disp[im] = {"scale_s": s, "cv_all": float(da.std() / da.mean()), "maxmin_all": float(da.max() / da.min()),
                    "cv_electrical": float(de.std() / de.mean()), "maxmin_electrical": float(de.max() / de.min()),
                    "max_electrical_over_s": float(de.max() / s), "min_electrical_over_s": float(de.min() / s),
                    "median_electrical_over_s": float(np.median(de) / s),
                    "frac_electrical_gt_2s": float((de > 2 * s).mean()),
                    "large_part_classes": sorted({COMPONENT_TYPES.get(c, str(c)) for c in ecl if c in LARGE_CLASSES}),
                    "n_components_all": int(nall[i]), "n_electrical": int(ne[i])}
    res["dispersion_per_image"] = disp
    keys = ["cv_all", "maxmin_all", "cv_electrical", "maxmin_electrical", "max_electrical_over_s"]
    pf_o = per_image_prf(M[OURS])
    dcorr = {k: {"vs_f1": spearman([disp[im][k] for im in imgs], pf_o[:, 2]),
                 "vs_recall": spearman([disp[im][k] for im in imgs], pf_o[:, 1]),
                 "vs_f1_partial_n_electrical": partial_spearman([disp[im][k] for im in imgs], pf_o[:, 2], ne),
                 "vs_recall_partial_n_electrical": partial_spearman([disp[im][k] for im in imgs], pf_o[:, 1], ne),
                 "vs_n_electrical": spearman([disp[im][k] for im in imgs], ne)} for k in keys}
    # is the dispersion effect specific to our scale-relative join, or generic image difficulty?
    res["dispersion_spearman_other_methods"] = {
        m: {k: {"vs_f1": spearman([disp[im][k] for im in imgs], per_image_prf(M[m])[:, 2]),
                "vs_f1_partial_n_electrical": partial_spearman([disp[im][k] for im in imgs],
                                                               per_image_prf(M[m])[:, 2], ne)}
            for k in ["cv_electrical", "maxmin_electrical"]}
        for m in M if m != OURS}
    # partial check: dispersion vs complexity (confound)
    dcorr["cv_electrical_vs_n_electrical"] = spearman([disp[im]["cv_electrical"] for im in imgs], ne)
    dcorr["cv_all_vs_n_electrical"] = spearman([disp[im]["cv_all"] for im in imgs], ne)
    res["dispersion_spearman_ours"] = dcorr
    halves = {}
    for k in ["cv_electrical", "cv_all", "max_electrical_over_s"]:
        v = np.array([disp[im][k] for im in imgs]); med = float(np.median(v))
        lo, hi = np.where(v <= med)[0], np.where(v > med)[0]
        halves[k] = {"median": med,
                     "low": {m: stratum_summary(M[m], lo, np.random.default_rng(SEED_BOOT)) for m in [OURS, "vlm", "degree_budget", f"hough_{HOUGH_BEST}"]},
                     "high": {m: stratum_summary(M[m], hi, np.random.default_rng(SEED_BOOT)) for m in [OURS, "vlm", "degree_budget", f"hough_{HOUGH_BEST}"]},
                     "ours_f1_high_minus_low": group_diff_test(M[OURS], lo, hi, np.random.default_rng(SEED_BOOT), which=2),
                     "ours_recall_high_minus_low": group_diff_test(M[OURS], lo, hi, np.random.default_rng(SEED_BOOT), which=1),
                     "low_images": [imgs[i] for i in lo], "high_images": [imgs[i] for i in hi]}
    res["dispersion_halves"] = halves
    mixed = [im for im in imgs if disp[im]["large_part_classes"]]
    res["images_with_large_parts"] = {im: {"classes": disp[im]["large_part_classes"],
                                           "maxmin_electrical": disp[im]["maxmin_electrical"],
                                           "max_electrical_over_s": disp[im]["max_electrical_over_s"],
                                           "ours_f1": float(pf_o[imgs.index(im), 2]),
                                           "ours_recall": float(pf_o[imgs.index(im), 1])} for im in mixed}
    if mixed:
        mi = [imgs.index(im) for im in mixed]; rest = [i for i in range(n) if i not in mi]
        res["large_parts_vs_rest_ours"] = {"with": stratum_summary(M[OURS], np.array(mi), np.random.default_rng(SEED_BOOT)),
                                           "without": stratum_summary(M[OURS], np.array(rest), np.random.default_rng(SEED_BOOT))}

    # ---- per-image table
    table = {}
    for i, im in enumerate(imgs):
        row = {"n_electrical": int(ne[i]), "n_gt_pairs": int(npairs[i]), "n_crossover": int(nx[i]),
               "n_components_all": int(nall[i])}
        for m, C in M.items():
            p, r, f = prf_counts(*map(int, C[i]))
            row[m] = {"tp": int(C[i, 0]), "fp": int(C[i, 1]), "fn": int(C[i, 2]),
                      "p": round(p, 4), "r": round(r, 4), "f1": round(f, 4)}
        table[im] = row
    res["per_image"] = table

    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print_summary(res, comps)
    print(f"\nwrote {OUT}")


def print_summary(res, comps):
    print("== reproduction")
    for m, r in res["reproduction"].items():
        print(f"  {m:<24} micro {r['micro_f1']:.4f} (committed {r['committed_micro_f1']:.4f}) "
              f"macro {r['macro_f1']:.4f} (committed {r['committed_macro_f1']:.4f}) "
              f"exact={r['n_images_exact']} {'OK' if r['micro_match'] and r['macro_match'] else 'MISMATCH'}")
    print("== paired tests (ours - X)")
    for m in comps:
        t = res["paired_tests"][m]; b = t["bootstrap_micro"]; pm = t["permutation"]; w = t["wilcoxon_f1"]
        print(f"  {m:<24} d={b['diff']:+.4f} CI[{b['ci95'][0]:+.4f},{b['ci95'][1]:+.4f}] "
              f"pboot={b['p_two_sided']:.4f} pperm_micro={pm['p_micro_f1']:.4f} pperm_mean={pm['p_mean_f1']:.4f} "
              f"pwilc={w['wilcox']['p']} (nz={w['n_nonzero']}) W/T/L={t['win_tie_loss_f1']} "
              f"holm(boot/permµ/permMean/wilc)={t['holm']['bootstrap_micro']:.4f}/{t['holm']['perm_micro']:.4f}/{t['holm']['perm_meanf1']:.4f}/{t['holm']['wilcoxon']:.4f} "
              f"k={pm['n_images_differing']} exact={pm['exact']}")
    j = res["jackknife_ours"]
    print(f"== jackknife ours micro-F1 [{j['micro_f1_min']:.4f}, {j['micro_f1_max']:.4f}]; sign const {j['sign_of_diff_constant']}")
    print("== strata (micro P/R/F1)")
    for s, d in res["strata"].items():
        line = f"  {s:<16} n={d['methods'][OURS]['n_images']:>2} "
        for m in [OURS, "degree_budget", "graph_scale", "hough_link44_reach48", "cc_detCCL_d15", "vlm"]:
            x = d["methods"][m]
            line += f"| {m[:10]} {x['micro_p']:.3f}/{x['micro_r']:.3f}/{x['micro_f1']:.3f} "
        print(line)
    print("== spearman ours", {k: (round(v['rho'], 3), round(v['p'], 4)) for k, v in res["complexity_spearman"][OURS].items()})
    print("== group tests", json.dumps(res["strata_group_tests"][OURS], indent=None))
    print("== dispersion (ours)")
    for k, v in res["dispersion_spearman_ours"].items():
        print("  ", k, json.dumps(v))
    print("== dispersion (others)")
    for m, v in res["dispersion_spearman_other_methods"].items():
        print("  ", m, {k: (round(x['vs_f1']['rho'], 3), round(x['vs_f1']['p'], 4), round(x['vs_f1_partial_n_electrical']['rho_partial'], 3), round(x['vs_f1_partial_n_electrical']['p'], 4)) for k, x in v.items()})
    for k, h in res["dispersion_halves"].items():
        print("  halves", k, "median", round(h["median"], 3), "low", {m: round(x["micro_f1"], 3) for m, x in h["low"].items()},
              "high", {m: round(x["micro_f1"], 3) for m, x in h["high"].items()}, "ours dF1", json.dumps(h["ours_f1_high_minus_low"]))
    print("== large parts", json.dumps(res.get("images_with_large_parts"), indent=None))
    if "large_parts_vs_rest_ours" in res:
        print("   with/without", {k: (v["n_images"], round(v["micro_f1"], 3), round(v["micro_r"], 3)) for k, v in res["large_parts_vs_rest_ours"].items()})


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Bootstrap 95% CIs for the real-image connectivity benchmark (N=31).

Resamples the 31 images with replacement (B=10000, fixed seed) and reports the 2.5/97.5
percentile interval for micro-F1 (recomputed from pooled per-image tp/fp/fn) and macro-F1
(mean of per-image F1). Covers the top join strategies and the Claude-VLM, plus the
ours-vs-VLM paired difference. Reads the per-image artifacts produced by the modified
join_eval_real_f1 / detection_ceiling / score_vlm scripts. Pure stdlib, runs locally.
"""
from __future__ import annotations
import json
import random
from pathlib import Path

EXP = Path("/home/bosco/Projects/Misc-Projects/circuit-digitization/docs/research/experiments")
B = 10000
SEED = 12345


def micro_f1(counts):
    TP = sum(c[0] for c in counts); FP = sum(c[1] for c in counts); FN = sum(c[2] for c in counts)
    P = TP / (TP + FP) if TP + FP else 1.0
    R = TP / (TP + FN) if TP + FN else 1.0
    return 2 * P * R / (P + R) if P + R else 0.0


def macro_f1(f1s):
    return sum(f1s) / len(f1s) if f1s else 0.0


def pctile(xs, q):
    xs = sorted(xs)
    i = q * (len(xs) - 1)
    lo = int(i); hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def boot_ci(per_image_counts, per_image_f1):
    """per_image_* are lists aligned by image index."""
    rng = random.Random(SEED)
    n = len(per_image_counts)
    micro_samps, macro_samps = [], []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        micro_samps.append(micro_f1([per_image_counts[i] for i in idx]))
        macro_samps.append(macro_f1([per_image_f1[i] for i in idx]))
    return {
        "micro": {"point": micro_f1(per_image_counts),
                  "lo": pctile(micro_samps, 0.025), "hi": pctile(micro_samps, 0.975)},
        "macro": {"point": macro_f1(per_image_f1),
                  "lo": pctile(macro_samps, 0.025), "hi": pctile(macro_samps, 0.975)},
    }


def load_join():
    """join_micro_n31.json: per_image[img][strategy] = {f1,tp,fp,fn}; ordered dict."""
    d = json.load(open(EXP / "join_micro_n31.json"))
    imgs = list(d["per_image"].keys())
    strategies = [s for s in d["micro"].keys()]
    out = {}
    for s in strategies:
        counts = [(d["per_image"][im][s]["tp"], d["per_image"][im][s]["fp"], d["per_image"][im][s]["fn"]) for im in imgs]
        f1s = [d["per_image"][im][s]["f1"] for im in imgs]
        out[s] = (imgs, counts, f1s)
    return out


def load_vlm():
    """vlm_clean_rerun_n31.json: rows[] with img,tp,fp,fn,F1."""
    d = json.load(open(EXP / "vlm_clean_rerun_n31.json"))
    rows = {r["img"]: r for r in d["rows"]}
    return rows


def main():
    join = load_join()
    vlm_rows = load_vlm()
    imgs = join["scale_completion"][0]

    print(f"Bootstrap 95% CI (B={B}, seed={SEED}, N={len(imgs)})\n")
    print(f"{'method':<24}{'micro F1 [95% CI]':<28}{'macro F1 [95% CI]'}")
    print("-" * 80)

    report = {}
    # join strategies
    for s, (ims, counts, f1s) in join.items():
        ci = boot_ci(counts, f1s)
        report[f"join/{s}"] = ci
        print(f"{s:<24}{ci['micro']['point']:.3f} [{ci['micro']['lo']:.3f}, {ci['micro']['hi']:.3f}]"
              f"      {ci['macro']['point']:.3f} [{ci['macro']['lo']:.3f}, {ci['macro']['hi']:.3f}]")

    # VLM aligned to same image order
    vcounts = [(vlm_rows[im]["tp"], vlm_rows[im]["fp"], vlm_rows[im]["fn"]) for im in imgs]
    vf1 = [vlm_rows[im]["F1"] for im in imgs]
    vci = boot_ci(vcounts, vf1)
    report["VLM"] = vci
    print(f"{'VLM (Claude Opus 4.8)':<24}{vci['micro']['point']:.3f} [{vci['micro']['lo']:.3f}, {vci['micro']['hi']:.3f}]"
          f"      {vci['macro']['point']:.3f} [{vci['macro']['lo']:.3f}, {vci['macro']['hi']:.3f}]")

    # paired difference VLM - ours (scale_completion), micro
    rng = random.Random(SEED + 1)
    sc_counts = join["scale_completion"][1]
    n = len(imgs)
    diffs = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(micro_f1([vcounts[i] for i in idx]) - micro_f1([sc_counts[i] for i in idx]))
    point = micro_f1(vcounts) - micro_f1(sc_counts)
    dlo, dhi = pctile(diffs, 0.025), pctile(diffs, 0.975)
    report["VLM_minus_ours_micro"] = {"point": point, "lo": dlo, "hi": dhi}
    print(f"\nPaired micro-F1 diff (VLM - scale_completion): {point:+.3f} [{dlo:+.3f}, {dhi:+.3f}]")
    print(f"  -> CI {'excludes' if (dlo > 0 or dhi < 0) else 'includes'} 0")

    json.dump(report, open(EXP / "bootstrap_ci_n31.json", "w"), indent=2)
    print(f"\nwrote {EXP / 'bootstrap_ci_n31.json'}")


if __name__ == "__main__":
    main()

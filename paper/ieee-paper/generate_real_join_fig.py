#!/usr/bin/env python3
"""Regenerate figures/real_join_comparison.pdf: micro-F1 on the 31-image verified benchmark,
with 95% bootstrap CI error bars and the VLM as a dashed upper-reference line.
Reads the consistent micro results pulled from claw + the local bootstrap CIs."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

EXP = Path(__file__).resolve().parents[2] / "docs/research/experiments"
OUT = Path(__file__).resolve().parent / "figures/real_join_comparison.pdf"

ci = json.load(open(EXP / "bootstrap_ci_n31.json"))

# (label, micro-F1, ci_lo, ci_hi, group)
def m(key):
    c = ci[key]["micro"]
    return c["point"], c["lo"], c["hi"]

# Labels match Fig. join_comparison naming for the same strategies.
joins = [
    ("Scale-rel. + compl. (ours)", *m("join/scale_completion"), "ours"),
    ("Rescue + compl.", *m("join/degree_budget"), "join"),
    ("Scale-rel. base", *m("join/graph_scale"), "join"),
    ("Rescue base", *m("join/graph_rescue"), "join"),
    ("Radius u-find", *m("join/production"), "join"),
]
# classical baselines (best config) — micro from the baseline jsons
cc = json.load(open(EXP / "cc_detected_micro_n31.json"))
hough = json.load(open(EXP / "hough_micro_n31.json"))
cc_best = max((v for k, v in cc.items() if k.startswith("detCCL")), key=lambda v: v["micro"]["f1"])
hough_best = hough["configs"][hough["best"]]
baselines = [
    ("Hough+prox (best)", hough_best["micro"]["f1"], None, None, "baseline"),
    ("Conn.-comp. (best)", cc_best["micro"]["f1"], None, None, "baseline"),
]

bars = joins + baselines
vlm_pt, vlm_lo, vlm_hi = m("VLM")

colors = {"ours": "#1f77b4", "join": "#7fb3d5", "baseline": "#bdbdbd"}
# Horizontal bars: 7 long strategy names stay horizontal and legible at
# \columnwidth (3.45in), values sit at bar ends clear of the CI whiskers.
fig, ax = plt.subplots(figsize=(3.45, 2.4), dpi=300)
ys = range(len(bars))
vals = [b[1] for b in bars]
ax.barh(ys, vals, color=[colors[b[4]] for b in bars], edgecolor="black",
        linewidth=0.5, zorder=2, height=0.72)
ax.invert_yaxis()  # ours on top
# CI error bars where available; value labels beyond the upper whisker
for i, b in enumerate(bars):
    if b[2] is not None:
        ax.errorbar(b[1], i, xerr=[[b[1] - b[2]], [b[3] - b[1]]], fmt="none",
                    ecolor="black", elinewidth=1.0, capsize=2.5, zorder=3)
    ax.text((b[3] if b[3] is not None else b[1]) + 0.008, i, f"{b[1]:.3f}",
            ha="left", va="center", fontsize=8)
# VLM reference band + line, labeled directly (no legend box over the bars)
ax.axvspan(vlm_lo, vlm_hi, color="#d62728", alpha=0.10, zorder=0)
ax.axvline(vlm_pt, color="#d62728", ls="--", lw=1.2, zorder=1)
ax.text(vlm_pt + 0.012, len(bars) - 1.25, f"VLM\n{vlm_pt:.3f}",
        ha="left", va="center", fontsize=8, color="#d62728")
ax.set_yticks(list(ys))
ax.set_yticklabels([b[0] for b in bars], fontsize=8)
ax.set_xlabel("Connectivity micro-F1", fontsize=8)
ax.tick_params(axis="x", labelsize=8)
ax.set_xlim(0.55, 1.0)
ax.grid(axis="x", ls=":", alpha=0.4, zorder=0)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout()
OUT.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT, bbox_inches="tight", pad_inches=0.03)
print(f"wrote {OUT}")
print(f"  ours={vals[0]:.3f}  VLM={vlm_pt:.3f}  Hough={hough_best['micro']['f1']:.3f}  CCL={cc_best['micro']['f1']:.3f}")

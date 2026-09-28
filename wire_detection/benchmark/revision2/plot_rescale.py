#!/usr/bin/env python3
"""Figure: connectivity micro-F1 vs image scale factor (rescale_n31.json).

  uv run python wire_detection/benchmark/revision2/plot_rescale.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, NullLocator  # noqa: E402

SRC = Path("docs/research/experiments/revision2/rescale_n31.json")
OUT = Path("paper/ieee-paper/figures/rescale_robustness.pdf")

# validated categorical slots 1-4 (blue, orange, aqua, magenta) + marker/linestyle
# secondary encoding (adjacent-pair CVD dE 6.1 is in the floor band)
STYLE = {
    "scale_completion":   ("Scale-rel. graph + completion", "#2a78d6", "o", "-"),
    "fixedpx_completion": ("Fixed-px graph + completion", "#eb6834", "s", "--"),
    "graph_scale":        ("Scale-rel. graph (base)", "#1baf7a", "^", "-."),
    "production":         ("Radius union-find (30 px)", "#e87ba4", "D", ":"),
}
ARMS = [("A_gt_wires", "(a) Join only: annotated wires"),
        ("B_detected", "(b) Full: wires re-extracted")]


def main():
    d = json.load(open(SRC))
    fs = d["factors"]
    plt.rcParams.update({"font.size": 7.5, "font.family": "serif", "axes.linewidth": 0.6,
                         "pdf.fonttype": 42})
    fig, axes = plt.subplots(2, 1, figsize=(3.5, 4.1), sharex=True)
    for ax, (arm, title) in zip(axes, ARMS):
        for m, (lab, col, mk, ls) in STYLE.items():
            s = d["summary"][arm][m]
            y = [s[str(f)]["f1"] for f in fs]
            if m == "scale_completion":
                ax.fill_between(fs, [s[str(f)]["ci_lo"] for f in fs],
                                [s[str(f)]["ci_hi"] for f in fs], color=col, alpha=0.16,
                                lw=0, label="95% bootstrap CI")
            ax.plot(fs, y, ls=ls, marker=mk, color=col, lw=1.4, ms=3.6, label=lab,
                    mec="white", mew=0.5)
        ax.axvline(1.0, color="#9a9a94", lw=0.6, zorder=0)
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(FixedLocator(fs))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xticklabels([f"{f:g}" for f in fs])
        ax.set_ylim(0.0, 1.0)
        ax.set_ylabel("Connectivity micro-F1")
        ax.set_title(title, fontsize=7.5, loc="left", pad=3)
        ax.grid(axis="y", color="#e4e4df", lw=0.5)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(width=0.6, length=2.5)
    axes[-1].set_xlabel("Image scale factor $f$ (log scale; native = 1)")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=2, frameon=False, fontsize=6.6,
               bbox_to_anchor=(0.5, -0.005), handlelength=2.4, columnspacing=1.0)
    fig.tight_layout(rect=(0, 0.12, 1, 1), h_pad=0.6)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    fig.savefig(Path(__import__('os').environ.get('PREVIEW_DIR', '.')) / 'rescale_preview.png', dpi=220, bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()

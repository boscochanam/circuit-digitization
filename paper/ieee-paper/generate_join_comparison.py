#!/usr/bin/env python3
"""Fig: join-strategy comparison (light, sans-serif, descriptive labels).

Panel (a): synthetic robustness, mean join-F1 by error severity L0--L4, per strategy
           (15 circuits x 8 seeds). Values mirror Table II (tab:join_leaderboard).
Panel (b): the headline join (scale_completion) per circuit at L4, with simulation
           accuracy. Values mirror Table V (tab:per_circuit), sourced from
           docs/research/experiments/per_circuit_scale_completion_l4_n16.json.

Regenerate locally:  uv run --with matplotlib python paper/ieee-paper/generate_join_comparison.py
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
    "font.size": 10, "axes.titlesize": 12, "figure.dpi": 300,
})

# ---- Panel (a): mean join-F1 by severity (matches Table II) ----
SEV = ["L0", "L1", "L2", "L3", "L4"]
STRATS = [
    ("Scale-rel.\n+ compl.\n(ours)", [1.00, 1.00, 1.00, 0.96, 0.95]),
    ("Rescue\n+ compl.",             [1.00, 1.00, 1.00, 0.95, 0.94]),
    ("Rescue\nbase",                 [1.00, 1.00, 1.00, 0.94, 0.89]),
    ("Scale-rel.\nbase",             [1.00, 1.00, 1.00, 0.94, 0.85]),
    ("Radius\nu-find",               [1.00, 0.97, 0.90, 0.56, 0.36]),
    ("Nearest\n+ anchor",            [1.00, 0.97, 0.89, 0.38, 0.32]),
]
# blue ramp L0->L4 (dark to light) then orange/red for the degraded high levels
SEV_COLORS = ["#1b3a6b", "#2e6db4", "#7eb3e0", "#f5a05a", "#e0552b"]

# ---- Panel (b): scale_completion per circuit at L4 (matches Table V) ----
CIRC = [
    ("Parallel\nR-R",   1.00, 25),
    ("R-R\ndivider",    0.99, 69),
    ("RL\nseries",      0.99, 81),
    ("Diode-R\nloop",   0.99, 69),
    ("Dual R\nloops",   0.93, 12),
    ("4-comp.\nloop",   0.94, 56),
    ("Wheat-\nstone",   0.82, 6),
    ("6-comp.\nring",   0.95, 50),
]

fig, (axa, axb) = plt.subplots(1, 2, figsize=(13.5, 5.0))

# Panel (a): grouped bars
n = len(STRATS); w = 0.16
x = np.arange(n)
for i, (sv, col) in enumerate(zip(SEV, SEV_COLORS)):
    vals = [s[1][i] for s in STRATS]
    axa.bar(x + (i - 2) * w, vals, w, label=sv, color=col, edgecolor="black", lw=0.4, zorder=3)
axa.axhline(0.5, color="#888", ls=":", lw=1.0, zorder=1)
axa.set_xticks(x); axa.set_xticklabels([s[0] for s in STRATS], fontsize=8.5)
axa.set_ylabel("Join F1"); axa.set_ylim(0, 1.05)
axa.set_title("(a) Strategy robustness under error injection")
axa.legend(title="Error level", ncol=5, fontsize=8, title_fontsize=8.5,
           loc="lower center", frameon=True, columnspacing=1.0, handlelength=1.2)
axa.grid(axis="y", ls=":", alpha=0.4, zorder=0)
for s in ("top", "right"):
    axa.spines[s].set_visible(False)

# Panel (b): F1 bars + simulation-accuracy line
xb = np.arange(len(CIRC))
f1 = [c[1] for c in CIRC]; sim = [c[2] for c in CIRC]
axb.bar(xb, f1, 0.62, color="#2e6db4", edgecolor="black", lw=0.4, zorder=3)
for i, v in enumerate(f1):
    axb.text(i, v + 0.012, f"{v:.2f}", ha="center", va="bottom", fontsize=8)
axb.set_xticks(xb); axb.set_xticklabels([c[0] for c in CIRC], fontsize=8.5)
axb.set_ylabel("Join F1 (L4)"); axb.set_ylim(0, 1.08)
axb.set_title("(b) Scale-relative completion join per circuit at L4")
axb.grid(axis="y", ls=":", alpha=0.4, zorder=0)
for s in ("top",):
    axb.spines[s].set_visible(False)
ax2 = axb.twinx()
ax2.plot(xb, sim, "-o", color="#f97316", lw=1.8, ms=5, zorder=4)
ax2.set_ylabel("Simulation accuracy (%)", color="#f97316")
ax2.tick_params(axis="y", colors="#f97316"); ax2.set_ylim(0, 105)
ax2.spines["top"].set_visible(False)

fig.tight_layout()
fig.savefig(OUT / "join_comparison.pdf", bbox_inches="tight", pad_inches=0.04)
plt.close(fig)
print("wrote join_comparison.pdf")

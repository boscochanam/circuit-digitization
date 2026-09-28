"""Graphical abstract for IEEE Access (660x295 px JPG, < 45 KB).

Top: pipeline strip. Bottom: component-pair micro-F1 on both real benchmarks
(31 human-verified images; 164 held-out CGHD photographs), ours vs baselines.
Numbers: docs/research/experiments/join_micro_n31.json, hough/cc micro JSONs,
docs/research/experiments/revision2/cghd_ref_benchmark.json.

  uv run --with matplotlib python paper/ieee-paper/generate_graphical_abstract.py
"""
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from PIL import Image

OUT = Path(__file__).resolve().parent / "figures" / "graphical_abstract.jpg"
W, H, DPI = 660, 295, 110

stages = [("Input image", "hand-drawn scan", "#e6e6e6"),
          ("Component\ndetection", "YOLO OBB", "#dbe8f7"),
          ("Component\nocclusion", "median fill", "#dcefe0"),
          ("Wire\nextraction", "Sauvola + PCA", "#f8e1cf"),
          ("Endpoint-graph\njoin", "+ degree-budget", "#dbe8f7"),
          ("Structural\nnetlist", "pin-to-node map", "#dcefe0")]

methods = ["Ours", "Rescue + compl.", "Hough + prox.", "Conn. comp.", "Radius u-f"]
human31 = [0.890, 0.829, 0.805, 0.624, 0.667]
held164 = [0.711, 0.659, 0.480, 0.594, 0.518]

fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
top = fig.add_axes([0.0, 0.66, 1.0, 0.34]); top.axis("off")
top.set_xlim(0, 6); top.set_ylim(0, 1)
for i, (name, sub, col) in enumerate(stages):
    x = i + 0.06
    ours = i in (2, 3, 4)
    top.add_patch(FancyBboxPatch((x, 0.12), 0.82, 0.78, boxstyle="round,pad=0.02,rounding_size=0.06",
                                 fc=col, ec="#c0392b" if ours else "#555", lw=1.4 if ours else 0.8))
    top.text(x + 0.41, 0.63, name, ha="center", va="center", fontsize=6.6, weight="bold", linespacing=0.95)
    top.text(x + 0.41, 0.25, sub, ha="center", va="center", fontsize=5.6, color="#444")
    if i < 5:
        top.annotate("", xy=(i + 1.06, 0.51), xytext=(x + 0.84, 0.51),
                     arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#444"))
top.text(3.5, 0.0, "contribution: occlusion-first extraction + endpoint-graph joining", ha="center",
         va="bottom", fontsize=5.8, color="#c0392b", style="italic")

ax = fig.add_axes([0.20, 0.13, 0.77, 0.47])
y = range(len(methods))
h = 0.38
b1 = ax.barh([v - h / 2 for v in y], human31, height=h, color="#2c6fb7", label="31 human-verified images")
b2 = ax.barh([v + h / 2 for v in y], held164, height=h, color="#e39a4c", label="164 held-out photographs, 24 drafters")
for bars in (b1, b2):
    for r in bars:
        ax.text(r.get_width() + 0.008, r.get_y() + r.get_height() / 2, f"{r.get_width():.3f}",
                va="center", fontsize=5.4)
ax.set_yticks(list(y)); ax.set_yticklabels(methods, fontsize=6.2)
ax.get_yticklabels()[0].set_weight("bold")
ax.invert_yaxis()
ax.set_xlim(0.4, 1.0)
ax.tick_params(axis="x", labelsize=5.6, length=2)
ax.set_xlabel("Connectivity micro-F1 (component pairs, annotated boxes)", fontsize=5.8, labelpad=1)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(fontsize=5.4, loc="lower right", frameon=False, handlelength=1.2)

buf = BytesIO()
fig.savefig(buf, format="png", dpi=DPI)
plt.close(fig)
im = Image.open(buf).convert("RGB").resize((W, H), Image.LANCZOS)
for q in range(92, 40, -4):
    im.save(OUT, "JPEG", quality=q, optimize=True)
    if OUT.stat().st_size < 45_000:
        break
print(OUT, im.size, OUT.stat().st_size, "bytes, quality", q)

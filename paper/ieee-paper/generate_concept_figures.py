#!/usr/bin/env python3
"""Reproducible generators for the paper's concept/benchmark figures, with one shared
sans-serif style so all figures match. Produces:
  - endpoint_graph_concept.pdf  (radius over-merge vs our 5-edge typed graph)
  - completion_concept.pdf      (degree-budget completion + self-loop guard)
  - pipeline_overview.pdf       (6-stage flow, our contribution highlighted)
  - wire_benchmark.pdf          (wire-detection F1 bar chart, sans-serif)
Run locally: uv run python paper/ieee-paper/generate_concept_figures.py
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, FancyArrowPatch

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# Shared style — sans-serif everywhere, matched sizes
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "legend.fontsize": 8.5,
    "figure.dpi": 300,
})

# Palette
C_COMP = "#cfe0f3"      # component fill
C_COMP_EDGE = "#1b1b1b"
C_PIN = "#2ca02c"       # component pin (green square)
C_END = "#1f77b4"       # wire endpoint (blue dot)
C_BODY = "#1f77b4"      # wire body (solid blue)
C_EP_PIN = "#2ca02c"    # endpoint-pin edge (green dashed)
C_EE = "#ff7f0e"        # endpoint-endpoint (orange dashed)
C_TJ = "#9467bd"        # T-junction endpoint->body (purple dashed)
C_RAIL = "#d62728"      # rail-tap pin->body (red dashed)
C_BAD = "#d62728"


def _comp(ax, x, y, w, h, label):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc=C_COMP, ec=C_COMP_EDGE, lw=1.4, zorder=2))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontweight="bold", zorder=3)


def _pin(ax, x, y):
    ax.add_patch(Rectangle((x - 0.05, y - 0.05), 0.10, 0.10, fc=C_PIN, ec="black", lw=0.6, zorder=5))


def _end(ax, x, y):
    ax.add_patch(Circle((x, y), 0.06, fc=C_END, ec="white", lw=0.8, zorder=5))


# ---------------------------------------------------------------- endpoint graph
def endpoint_graph():
    fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.0, 3.1))

    # (a) radius-based over-merge
    ax = axa
    ax.set_title("(a) Radius-based joining (production)")
    _comp(ax, 0.2, 1.0, 0.7, 0.9, "R1")
    _comp(ax, 1.9, 1.0, 0.7, 0.9, "C1")
    _comp(ax, 3.6, 1.0, 0.7, 0.9, "R2")
    # pins
    for px in (0.95, 1.85):
        ax.add_patch(Circle((px, 1.45), 0.06, fc=C_END, ec="white", lw=0.8, zorder=5))
    for px in (2.65, 3.55):
        ax.add_patch(Circle((px, 1.45), 0.06, fc=C_END, ec="white", lw=0.8, zorder=5))
    # over-grab radius circles
    for cx in (1.4, 3.1):
        ax.add_patch(Circle((cx, 1.45), 0.55, fc="none", ec=C_BAD, ls=(0, (4, 3)), lw=1.3, zorder=4))
    ax.annotate("", xy=(1.85, 1.45), xytext=(0.95, 1.45),
                arrowprops=dict(arrowstyle="-|>", color=C_BAD, lw=2.2), zorder=6)
    ax.annotate("", xy=(2.65, 1.45), xytext=(1.85, 1.45),
                arrowprops=dict(arrowstyle="-|>", color=C_BAD, lw=2.2), zorder=6)
    ax.text(2.25, 0.55, "radius grabs every pin in range\n→ R1, C1, R2 wrongly merged",
            ha="center", va="top", color=C_BAD, style="italic", fontsize=8.5)
    ax.set_xlim(0, 4.5); ax.set_ylim(0.2, 2.4); ax.axis("off")

    # (b) endpoint-graph with 5 typed edges
    ax = axb
    ax.set_title("(b) Endpoint-graph joining (ours): five typed edges")
    # rail wire across the top (a long wire body)
    rail_y = 2.05
    ax.plot([0.5, 3.9], [rail_y, rail_y], color=C_BODY, lw=2.4, zorder=3, solid_capstyle="round")
    _end(ax, 0.5, rail_y); _end(ax, 3.9, rail_y)
    # two collinear segments meeting end-to-end (endpoint-endpoint) on the rail's right
    ax.plot([2.2, 3.05], [rail_y, rail_y], color=C_BODY, lw=2.4, zorder=3)  # same rail; mark a join point
    # components
    _comp(ax, 0.25, 0.35, 0.6, 0.7, "R1")   # taps rail (rail-tap)
    _comp(ax, 1.55, 0.35, 0.6, 0.7, "C1")   # via vertical wire + endpoint-pin
    _comp(ax, 3.45, 0.35, 0.6, 0.7, "R2")   # endpoint-pin on the right rail end
    # R1 top pin taps directly into rail body (rail-tap, pin->body)
    p_r1 = (0.55, 1.05)
    _pin(ax, *p_r1)
    ax.plot([p_r1[0], p_r1[0]], [p_r1[1], rail_y], color=C_RAIL, ls=(0, (1, 1.4)), lw=1.8, zorder=4)
    ax.add_patch(Circle((p_r1[0], rail_y), 0.05, fc=C_RAIL, ec="white", lw=0.6, zorder=6))
    # vertical wire: top endpoint lands on rail mid (T-junction endpoint->body); bottom endpoint -> C1 pin
    vx = 1.85
    ax.plot([vx, vx], [1.15, rail_y], color=C_BODY, lw=2.4, zorder=3)
    _end(ax, vx, 1.15)                       # bottom endpoint
    ax.add_patch(Circle((vx, rail_y), 0.06, fc=C_TJ, ec="white", lw=0.8, zorder=6))  # T-junction hit
    p_c1 = (1.85, 1.05)
    _pin(ax, *p_c1)
    ax.plot([vx, p_c1[0]], [1.15, p_c1[1]], color=C_EP_PIN, ls=(0, (5, 3)), lw=1.6, zorder=4)
    # endpoint-endpoint: a short wire from the right whose endpoint meets the rail's right endpoint
    ax.plot([3.05, 3.9], [1.5, rail_y], color=C_BODY, lw=2.4, zorder=3)
    _end(ax, 3.05, 1.5)
    ax.add_patch(Circle((3.9, rail_y), 0.085, fc="none", ec=C_EE, lw=1.8, zorder=6))  # ee junction ring
    # R2 pin -> rail right end (endpoint-pin)
    p_r2 = (3.75, 1.05)
    _pin(ax, *p_r2)
    ax.plot([3.9, p_r2[0]], [rail_y, p_r2[1]], color=C_EP_PIN, ls=(0, (5, 3)), lw=1.6, zorder=4)

    ax.set_xlim(0, 4.5); ax.set_ylim(0.1, 2.5); ax.axis("off")

    # shared legend
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color=C_BODY, lw=2.4, label="Wire body"),
        Line2D([0], [0], color=C_EP_PIN, ls=(0, (5, 3)), lw=1.6, label="Endpoint–pin"),
        Line2D([0], [0], color=C_EE, marker="o", mfc="none", ls="none", ms=8, label="Endpoint–endpoint"),
        Line2D([0], [0], color=C_TJ, marker="o", ls="none", ms=7, label="T-junction (endpoint–body)"),
        Line2D([0], [0], color=C_RAIL, ls=(0, (1, 1.4)), lw=1.8, label="Rail-tap (pin–body)"),
        Line2D([0], [0], color=C_END, marker="o", ls="none", ms=7, mec="white", label="Wire endpoint"),
        Line2D([0], [0], color=C_PIN, marker="s", ls="none", ms=7, mec="black", label="Component pin"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(OUT / "endpoint_graph_concept.pdf", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print("wrote endpoint_graph_concept.pdf")


# ---------------------------------------------------------------- completion
def completion():
    fig, (axb, axa) = plt.subplots(1, 2, figsize=(7.0, 2.9))

    def scene(ax, after):
        _comp(ax, 0.2, 0.8, 0.7, 1.0, "R1")
        _comp(ax, 1.7, 0.8, 0.7, 1.0, "R2")
        _comp(ax, 3.2, 0.8, 0.7, 1.0, "R3")
        # Net A wire between R1.right and R2.left
        ax.add_patch(Rectangle((0.85, 1.25), 0.10, 0.10, fc=C_PIN, ec="black", lw=0.6, zorder=5))
        ax.add_patch(Rectangle((1.65, 1.25), 0.10, 0.10, fc=C_PIN, ec="black", lw=0.6, zorder=5))
        ax.plot([0.95, 1.65], [1.30, 1.30], color=C_BODY, lw=2.4, zorder=3)
        ax.text(1.30, 1.50, "Net A", color=C_BODY, ha="center", fontsize=9)
        # R2 right pin and R3 left pin
        ax.add_patch(Rectangle((2.35, 1.25), 0.10, 0.10, fc=C_PIN, ec="black", lw=0.6, zorder=5))
        r3_pin = (3.15, 1.30)
        if after:
            # completion edge R2.right -> R3.left, merged into Net A; R3 now connected (green)
            ax.add_patch(Rectangle((r3_pin[0] - 0.05, r3_pin[1] - 0.05), 0.10, 0.10,
                                   fc=C_PIN, ec="black", lw=0.6, zorder=5))
            arr = FancyArrowPatch((2.45, 1.30), (r3_pin[0], r3_pin[1]),
                                  connectionstyle="arc3,rad=-0.35", arrowstyle="-|>",
                                  color=C_EE, lw=2.0, mutation_scale=14, zorder=4)
            ax.add_patch(arr)
            ax.text(2.8, 1.92, "completion edge\n(min-cost b-matching)", color=C_EE,
                    ha="center", va="bottom", fontsize=8, style="italic")
            ax.text(2.95, 1.50, "Net A (merged)", color=C_BODY, ha="center", fontsize=9)
            ax.text(2.05, 0.45,
                    "self-loop guard: a pin's own two terminals\nare never matched to each other",
                    ha="center", va="top", fontsize=7.8, color="#2a7a2a")
        else:
            # R3 left pin floating (red), Net B label
            ax.add_patch(Circle(r3_pin, 0.07, fc=C_BAD, ec="white", lw=0.8, zorder=5))
            ax.text(r3_pin[0] + 0.05, 1.95, "floating pin", color=C_BAD, ha="center",
                    va="bottom", fontsize=8.5, style="italic")
        ax.set_xlim(0, 4.1); ax.set_ylim(0.2, 2.3); ax.axis("off")

    axb.set_title("Before completion")
    scene(axb, after=False)
    axa.set_title("After completion")
    scene(axa, after=True)
    fig.tight_layout()
    fig.savefig(OUT / "completion_concept.pdf", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print("wrote completion_concept.pdf")


# ---------------------------------------------------------------- pipeline overview
def pipeline_overview():
    fig, ax = plt.subplots(figsize=(7.2, 1.9))
    stages = [
        ("Input\nImage", "Scanned\nschematic", "#d9d9d9"),
        ("Component\nDetection", "YOLO OBB\n88.5% mAP", "#cfe0f3"),
        ("Component\nOcclusion", "Local median\nfill", "#cdeccd"),
        ("Binarization\n+ Line Extract", "Sauvola + CCL\n+ PCA", "#f7d9c4"),
        ("Wire\nJoining", "Endpoint-graph\n+ degree-budget", "#cfe0f3"),
        ("SPICE\nNetlist", "Pin discovery\n+ simulation", "#cdeccd"),
    ]
    n = len(stages)
    w, h, gap = 1.85, 1.25, 0.42
    x = 0.0
    for i, (title, sub, col) in enumerate(stages):
        ax.add_patch(FancyBboxPatch((x, 0), w, h, boxstyle="round,pad=0.02,rounding_size=0.10",
                                    fc=col, ec="#1b1b1b", lw=1.4, zorder=2))
        ax.text(x + w / 2, h * 0.66, title, ha="center", va="center", fontweight="bold", fontsize=8.5)
        ax.text(x + w / 2, h * 0.25, sub, ha="center", va="center", fontsize=6.8, color="#444")
        if i < n - 1:
            ax.annotate("", xy=(x + w + gap - 0.05, h / 2), xytext=(x + w + 0.05, h / 2),
                        arrowprops=dict(arrowstyle="-|>", color="black", lw=1.6), zorder=1)
        x += w + gap
    # "Our contribution" dashed box tightly around Wire Joining (index 4)
    cx = (w + gap) * 4
    ax.add_patch(FancyBboxPatch((cx - 0.09, -0.12), w + 0.18, h + 0.24,
                                boxstyle="round,pad=0.0,rounding_size=0.10",
                                fc="none", ec=C_BAD, ls=(0, (6, 3)), lw=2.2, zorder=4))
    ax.text(cx + w / 2, -0.40, "Our contribution", ha="center", va="top",
            color=C_BAD, style="italic", fontweight="bold", fontsize=9.0)
    ax.set_xlim(-0.2, x - gap + 0.2); ax.set_ylim(-0.85, h + 0.35); ax.axis("off")
    ax.set_aspect("equal")
    fig.savefig(OUT / "pipeline_overview.pdf", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print("wrote pipeline_overview.pdf")


# ---------------------------------------------------------------- wire benchmark
def wire_benchmark():
    # (label, F1, group) — values from the 134-image wire-detection benchmark
    rows = [
        ("a16 (ours)", 0.976, "ours"),
        ("v4 baseline", 0.973, "ours"),
        ("v2", 0.959, "ours"),
        ("v1", 0.950, "ours"),
        ("v3", 0.949, "ours"),
        ("adaptive Gaussian", 0.928, "alt"),
        ("OTSU", 0.789, "bad"),
        ("Triangle", 0.758, "bad"),
    ]
    rows = rows[::-1]  # worst at bottom, best at top
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    colors = {"ours": "#1f77b4", "alt": "#ff7f0e", "bad": "#d62728"}
    ys = range(len(rows))
    ax.barh(list(ys), [r[1] for r in rows],
            color=[colors[r[2]] for r in rows], edgecolor="black", lw=0.5, zorder=2)
    # highlight ours (top bar) green
    ax.barh([len(rows) - 1], [rows[-1][1]], color="#2ca02c", edgecolor="black", lw=0.5, zorder=3)
    for i, r in enumerate(rows):
        ax.text(r[1] + 0.004, i, f"{r[1]:.3f}", va="center", ha="left", fontsize=8.5)
    ax.axvline(0.976, color="#2ca02c", ls="--", lw=1.0, alpha=0.7, zorder=1)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([r[0] for r in rows], fontsize=8.5)
    ax.set_xlabel("Wire detection F1 (134 images)")
    ax.set_xlim(0.6, 1.02)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.grid(axis="x", ls=":", alpha=0.4, zorder=0)
    fig.tight_layout()
    fig.savefig(OUT / "wire_benchmark.pdf", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print("wrote wire_benchmark.pdf")


if __name__ == "__main__":
    endpoint_graph()
    completion()
    pipeline_overview()
    wire_benchmark()
    print(f"\nAll concept figures written to {OUT}/")

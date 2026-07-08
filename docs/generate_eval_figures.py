"""Generate evaluation figures for the paper.

Three figures:
1) F1 vs error severity plot (from synthgt evaluation across L0-L5)
2) Join strategy comparison plot (from join_eval_134 results)
3) Per-circuit performance table (from expanded benchmark)
"""
from __future__ import annotations

import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from wire_detection.paths import DOCS_DIR, REPO_ROOT, output_dir

# Paths
ROOT = REPO_ROOT
OUTPUT_DIR = output_dir()
FIG_DIR = DOCS_DIR  # Save figures to docs/ for paper

# Dark theme consistent with existing visualizations
plt.style.use('dark_background')
COLORS = {
    'primary': '#e94560',
    'green': '#22c55e',
    'yellow': '#facc15',
    'orange': '#f97316',
    'red': '#ef4444',
    'cyan': '#06b6d4',
    'gray': '#6b7280',
    'light_gray': '#9ca3af',
    'bg': '#111827',
    'panel_bg': '#1e293b',
    'panel_border': '#334155',
}

# Error levels from synthgt evaluation
ERROR_LEVELS = {
    0: "L0\nClean",
    1: "L1\nMild",
    2: "L2\nModerate",
    3: "L3\nHeavy",
    4: "L4\nSevere",
}


def load_benchmark_data():
    """Load per-config benchmark data from expanded_full_ranking."""
    ranking_path = OUTPUT_DIR / "benchmark_experiments" / "expanded_full_ranking" / "full_ranking.json"
    with open(ranking_path) as f:
        return json.load(f)


def load_join_eval_data():
    """Load join evaluation summary data."""
    summary_path = OUTPUT_DIR / "join_eval_134" / "summary.json"
    with open(summary_path) as f:
        return json.load(f)


def generate_f1_vs_severity():
    """Figure 1: F1 vs error severity across all synthetic circuits.
    
    Runs the synthgt evaluation to compute mean F1 at each error level.
    """
    print("Generating Figure 1: F1 vs Error Severity...")
    
    from wire_detection.synthgt.circuits import CATALOG
    from wire_detection.synthgt.synthesize import (
        inject_errors, intended_pairs, synthesize_clean, ERROR_LEVELS,
    )
    from wire_detection.core.join_strategies import run_strategy
    from wire_detection.synthgt.evaluate import _comp_pairs, _prf, _make_std_pins
    
    # Compute per-circuit F1 at each severity
    sevs = sorted(ERROR_LEVELS.keys())
    circuit_f1s = {}
    all_f1s_by_sev = {s: [] for s in sevs}
    
    for spec in CATALOG:
        components, clean_wires, pin_pos = synthesize_clean(spec)
        gt_pairs = intended_pairs(spec)
        std_pins = _make_std_pins(pin_pos, spec)
        
        circuit_f1s[spec.name] = []
        for sev in sevs:
            n = 1 if sev == 0 else 8
            acc = 0.0
            for seed in range(n):
                wires = inject_errors(clean_wires, sev, seed, 
                                      pin_pos=pin_pos, components=components)
                _, net = run_strategy("graph_rescue", wires, components,
                                      std_pins=std_pins)
                p, r, f = _prf(gt_pairs, _comp_pairs(net))
                acc += f
            mean_f1 = acc / n
            circuit_f1s[spec.name].append(mean_f1)
            all_f1s_by_sev[sev].append(mean_f1)
    
    # Aggregate statistics
    means = [np.mean(all_f1s_by_sev[s]) for s in sevs]
    medians = [np.median(all_f1s_by_sev[s]) for s in sevs]
    p10 = [np.percentile(all_f1s_by_sev[s], 10) for s in sevs]
    p90 = [np.percentile(all_f1s_by_sev[s], 90) for s in sevs]
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), 
                                    facecolor=COLORS['bg'])
    fig.suptitle('Synthetic Ground-Truth Evaluation: Join F1 vs Error Severity',
                 fontsize=16, color=COLORS['primary'], fontweight='bold', y=1.02)
    
    # Left panel: Aggregate statistics
    ax1.set_facecolor(COLORS['panel_bg'])
    x = np.arange(len(sevs))
    
    # Shaded region for P10-P90
    ax1.fill_between(x, p10, p90, alpha=0.3, color=COLORS['cyan'], 
                     label='P10–P90')
    
    # Mean and median lines
    ax1.plot(x, means, 'o-', color=COLORS['green'], linewidth=2.5, 
             markersize=8, label='Mean F1', zorder=5)
    ax1.plot(x, medians, 's--', color=COLORS['yellow'], linewidth=2, 
             markersize=7, label='Median F1', zorder=5)
    
    # Individual circuits (thin lines)
    for name, f1s in circuit_f1s.items():
        ax1.plot(x, f1s, '-', color=COLORS['light_gray'], alpha=0.3, 
                linewidth=1, zorder=1)
    
    # Perfect line
    ax1.axhline(y=1.0, color=COLORS['gray'], linestyle=':', alpha=0.5)
    ax1.axhline(y=0.9, color=COLORS['orange'], linestyle=':', alpha=0.3)
    
    ax1.set_xlabel('Error Severity', fontsize=12, color=COLORS['light_gray'])
    ax1.set_ylabel('Component-Connectivity F1', fontsize=12, 
                   color=COLORS['light_gray'])
    ax1.set_xticks(x)
    ax1.set_xticklabels(list(ERROR_LEVELS.values()), fontsize=9)
    ax1.set_ylim(0.5, 1.05)
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
    ax1.legend(loc='lower left', fontsize=10, framealpha=0.8)
    ax1.set_title('Aggregate Performance (15 circuits, 8 seeds)',
                  fontsize=12, color=COLORS['light_gray'])
    ax1.grid(True, alpha=0.2, color=COLORS['gray'])
    ax1.tick_params(colors=COLORS['light_gray'])
    for spine in ax1.spines.values():
        spine.set_color(COLORS['panel_border'])
    
    # Right panel: Per-circuit heatmap
    ax2.set_facecolor(COLORS['panel_bg'])
    
    circuit_names = list(circuit_f1s.keys())
    data = np.array([circuit_f1s[name] for name in circuit_names])
    
    # Sort by mean F1 (ascending = hardest first)
    sort_idx = np.argsort(data.mean(axis=1))
    data_sorted = data[sort_idx, :]
    names_sorted = [circuit_names[i] for i in sort_idx]
    
    im = ax2.imshow(data_sorted, cmap='RdYlGn', vmin=0.5, vmax=1.0, 
                    aspect='auto', interpolation='nearest')
    
    # Add text annotations
    for i in range(len(names_sorted)):
        for j in range(len(sevs)):
            val = data_sorted[i, j]
            color = 'white' if val < 0.75 else 'black'
            ax2.text(j, i, f'{val:.2f}', ha='center', va='center',
                    fontsize=8, color=color, fontweight='bold')
    
    ax2.set_xticks(range(len(sevs)))
    ax2.set_xticklabels([ERROR_LEVELS[s] for s in sevs], fontsize=9)
    ax2.set_yticks(range(len(names_sorted)))
    ax2.set_yticklabels(names_sorted, fontsize=9)
    ax2.set_title('Per-Circuit F1 Heatmap', fontsize=12, 
                  color=COLORS['light_gray'])
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax2, shrink=0.8, pad=0.02)
    cbar.set_label('F1 Score', color=COLORS['light_gray'])
    cbar.ax.tick_params(colors=COLORS['light_gray'])
    
    ax2.tick_params(colors=COLORS['light_gray'])
    for spine in ax2.spines.values():
        spine.set_color(COLORS['panel_border'])
    
    plt.tight_layout()
    
    out_path = FIG_DIR / "fig_f1_vs_severity.png"
    fig.savefig(out_path, dpi=200, bbox_inches='tight', 
                facecolor=COLORS['bg'], edgecolor='none')
    plt.close()
    print(f"  Saved: {out_path}")
    
    # Also save the raw data
    data_out = {
        'means': [float(m) for m in means],
        'medians': [float(m) for m in medians],
        'p10': [float(p) for p in p10],
        'p90': [float(p) for p in p90],
        'per_circuit': circuit_f1s,
        'error_levels': ERROR_LEVELS,
    }
    data_path = OUTPUT_DIR / "synthgt_f1_by_severity.json"
    with open(data_path, 'w') as f:
        json.dump(data_out, f, indent=2)
    print(f"  Data saved: {data_path}")
    
    return out_path


def generate_join_comparison():
    """Figure 2: Join strategy comparison from join_eval_134 data.
    
    Bar chart comparing top join strategies on balanced composite score.
    """
    print("\nGenerating Figure 2: Join Strategy Comparison...")
    
    summary = load_join_eval_data()
    
    # Select top strategies to show (best 8)
    strategy_names = [
        'degree_budget', 'graph_rescue', 'graph_full', 
        'graph_30', 'graph_scale', 'graph_dir_30',
        'nearest2_30', 'production'
    ]
    
    # Build comparison data
    balanced_scores = []
    composite_scores = []
    wire_usage = []
    self_loops = []
    
    for name in strategy_names:
        if name in summary:
            data = summary[name]
            balanced_scores.append(data['balanced'])
            composite_scores.append(data['composite'])
            wire_usage.append(data['wires_used_pct'])
            self_loops.append(data['self_loop'])
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), facecolor=COLORS['bg'])
    fig.suptitle('Join Strategy Comparison (134-image benchmark)',
                 fontsize=16, color=COLORS['primary'], fontweight='bold', y=1.02)
    
    short_names = ['degree\nbudget', 'graph\nrescue', 'graph\nfull', 
                   'graph\n30', 'graph\nscale', 'graph\ndir_30',
                   'nearest2\n30', 'production']
    
    colors = [COLORS['green'] if 'graph' in n else 
              COLORS['cyan'] if 'degree' in n else
              COLORS['yellow'] for n in strategy_names]
    
    # Panel 1: Balanced Score (primary metric - lower is better)
    ax = axes[0, 0]
    ax.set_facecolor(COLORS['panel_bg'])
    bars = ax.bar(range(len(balanced_scores)), balanced_scores, 
                  color=colors, edgecolor='white', linewidth=0.5, alpha=0.9)
    ax.set_xticks(range(len(short_names)))
    ax.set_xticklabels(short_names, fontsize=8)
    ax.set_ylabel('Balanced Score\n(lower = better)', fontsize=10, 
                  color=COLORS['light_gray'])
    ax.set_title('Balanced Composite Score', fontsize=12, 
                color=COLORS['light_gray'])
    ax.grid(True, alpha=0.2, axis='y', color=COLORS['gray'])
    ax.tick_params(colors=COLORS['light_gray'])
    for spine in ax.spines.values():
        spine.set_color(COLORS['panel_border'])
    
    # Add value labels on bars
    for bar, val in zip(bars, balanced_scores):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.005,
               f'{val:.3f}', ha='center', va='bottom', fontsize=8,
               color=COLORS['light_gray'])
    
    # Panel 2: Wire Usage
    ax = axes[0, 1]
    ax.set_facecolor(COLORS['panel_bg'])
    bars = ax.bar(range(len(wire_usage)), wire_usage, 
                  color=colors, edgecolor='white', linewidth=0.5, alpha=0.9)
    ax.set_xticks(range(len(short_names)))
    ax.set_xticklabels(short_names, fontsize=8)
    ax.set_ylabel('Wires Used (%)', fontsize=10, color=COLORS['light_gray'])
    ax.set_title('Wire Utilization', fontsize=12, color=COLORS['light_gray'])
    ax.set_ylim(0, 110)
    ax.grid(True, alpha=0.2, axis='y', color=COLORS['gray'])
    ax.tick_params(colors=COLORS['light_gray'])
    for spine in ax.spines.values():
        spine.set_color(COLORS['panel_border'])
    
    for bar, val in zip(bars, wire_usage):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
               f'{val:.1f}%', ha='center', va='bottom', fontsize=8,
               color=COLORS['light_gray'])
    
    # Panel 3: Self-loops (lower = fewer errors)
    ax = axes[1, 0]
    ax.set_facecolor(COLORS['panel_bg'])
    bars = ax.bar(range(len(self_loops)), self_loops, 
                  color=colors, edgecolor='white', linewidth=0.5, alpha=0.9)
    ax.set_xticks(range(len(short_names)))
    ax.set_xticklabels(short_names, fontsize=8)
    ax.set_ylabel('Self-Loop Count', fontsize=10, color=COLORS['light_gray'])
    ax.set_title('Self-Loop Errors', fontsize=12, color=COLORS['light_gray'])
    ax.grid(True, alpha=0.2, axis='y', color=COLORS['gray'])
    ax.tick_params(colors=COLORS['light_gray'])
    for spine in ax.spines.values():
        spine.set_color(COLORS['panel_border'])
    
    for bar, val in zip(bars, self_loops):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 5,
               str(val), ha='center', va='bottom', fontsize=8,
               color=COLORS['light_gray'])
    
    # Panel 4: Scatter plot - Balanced vs Wire Usage
    ax = axes[1, 1]
    ax.set_facecolor(COLORS['panel_bg'])
    
    scatter_colors = colors[:len(balanced_scores)]
    ax.scatter(wire_usage, balanced_scores, c=scatter_colors, s=120, 
              edgecolors='white', linewidth=1, zorder=5, alpha=0.9)
    
    # Label each point
    for i, name in enumerate(strategy_names[:len(balanced_scores)]):
        ax.annotate(name, (wire_usage[i], balanced_scores[i]),
                   textcoords="offset points", xytext=(8, 5),
                   fontsize=7, color=COLORS['light_gray'])
    
    ax.set_xlabel('Wire Utilization (%)', fontsize=10, color=COLORS['light_gray'])
    ax.set_ylabel('Balanced Score (lower = better)', fontsize=10, 
                  color=COLORS['light_gray'])
    ax.set_title('Efficiency vs Quality Tradeoff', fontsize=12, 
                color=COLORS['light_gray'])
    ax.grid(True, alpha=0.2, color=COLORS['gray'])
    ax.tick_params(colors=COLORS['light_gray'])
    for spine in ax.spines.values():
        spine.set_color(COLORS['panel_border'])
    
    plt.tight_layout()
    
    out_path = FIG_DIR / "fig_join_comparison.png"
    fig.savefig(out_path, dpi=200, bbox_inches='tight', 
                facecolor=COLORS['bg'], edgecolor='none')
    plt.close()
    print(f"  Saved: {out_path}")
    
    return out_path


def generate_per_circuit_table():
    """Figure 3: Per-circuit performance table from expanded benchmark.
    
    Shows top configs ranked by F1 with detailed metrics.
    """
    print("\nGenerating Figure 3: Per-Circuit Performance Table...")
    
    ranking = load_benchmark_data()
    
    # ranking is a list of dicts, each with name, global_f1, precision, recall, fp, fn
    configs = []
    for item in ranking:
        if isinstance(item, dict) and 'name' in item:
            configs.append({
                'name': item['name'],
                'f1': item.get('global_f1', 0),
                'precision': item.get('precision', 0),
                'recall': item.get('recall', 0),
                'fp': item.get('fp', 0),
                'fn': item.get('fn', 0),
            })
    
    # Sort by F1 descending
    configs.sort(key=lambda x: x['f1'], reverse=True)
    
    # Take top 12
    configs = configs[:12]
    
    fig, ax = plt.subplots(figsize=(14, 8), facecolor=COLORS['bg'])
    ax.set_facecolor(COLORS['bg'])
    ax.axis('off')
    
    ax.set_title('Expanded Benchmark: Top Configurations (134 images, 36 configs)',
                 fontsize=16, color=COLORS['primary'], fontweight='bold', 
                 pad=20)
    
    # Table data
    headers = ['Rank', 'Config', 'F1', 'Precision', 'Recall', 'FP', 'FN', 'Status']
    cell_data = []
    cell_colors = []
    
    for i, cfg in enumerate(configs):
        rank = i + 1
        name = cfg['name']
        f1 = cfg['f1']
        prec = cfg['precision']
        rec = cfg['recall']
        fp = cfg['fp']
        fn = cfg['fn']
        
        # Status indicator
        if f1 >= 0.97:
            status = '★ Best'
            row_color = '#1a3a1a'
        elif f1 >= 0.95:
            status = '● Strong'
            row_color = '#1a2a1a'
        elif f1 >= 0.90:
            status = '● Good'
            row_color = '#2a2a1a'
        else:
            status = '○ Fair'
            row_color = '#2a1a1a'
        
        cell_data.append([
            str(rank), name, f'{f1:.4f}', f'{prec:.4f}', f'{rec:.4f}',
            str(fp), str(fn), status
        ])
        cell_colors.append([row_color] * len(headers))
    
    # Create table
    table = ax.table(
        cellText=cell_data,
        colLabels=headers,
        cellColours=cell_colors,
        colColours=[COLORS['panel_bg']] * len(headers),
        cellLoc='center',
        loc='center',
        colWidths=[0.06, 0.22, 0.1, 0.1, 0.1, 0.08, 0.08, 0.12]
    )
    
    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.8)
    
    # Style header row
    for j, header in enumerate(headers):
        cell = table[0, j]
        cell.set_text_props(color='white', fontweight='bold', fontsize=11)
        cell.set_facecolor(COLORS['panel_bg'])
        cell.set_edgecolor(COLORS['panel_border'])
    
    # Style data rows
    for i in range(len(configs)):
        for j in range(len(headers)):
            cell = table[i + 1, j]
            cell.set_edgecolor(COLORS['panel_border'])
            
            # Color F1 cell based on value
            if j == 2:  # F1 column
                f1_val = configs[i]['f1']
                if f1_val >= 0.97:
                    cell.set_text_props(color=COLORS['green'], fontweight='bold')
                elif f1_val >= 0.95:
                    cell.set_text_props(color=COLORS['yellow'])
                else:
                    cell.set_text_props(color=COLORS['orange'])
    
    # Add annotation
    annotation_text = (
        "Winner: a16 (anchor_endpoint_dist=16) | F1=0.9755\n"
        "Pipeline: Sauvola + Component Extraction + PCA Endpoints\n"
        "117/134 images (87%) achieve F1 ≥ 0.90 | Median F1 = 1.000"
    )
    ax.text(0.5, -0.05, annotation_text, transform=ax.transAxes,
           fontsize=10, color=COLORS['light_gray'], ha='center', va='top',
           bbox=dict(boxstyle='round,pad=0.5', facecolor=COLORS['panel_bg'],
                    edgecolor=COLORS['panel_border']))
    
    out_path = FIG_DIR / "fig_per_circuit_table.png"
    fig.savefig(out_path, dpi=200, bbox_inches='tight', 
                facecolor=COLORS['bg'], edgecolor='none')
    plt.close()
    print(f"  Saved: {out_path}")
    
    return out_path


def main():
    """Generate all evaluation figures."""
    print("=" * 60)
    print("GENERATING EVALUATION FIGURES")
    print("=" * 60)
    
    # Create output directory if needed
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    fig1 = generate_f1_vs_severity()
    fig2 = generate_join_comparison()
    fig3 = generate_per_circuit_table()
    
    print("\n" + "=" * 60)
    print("ALL FIGURES GENERATED SUCCESSFULLY")
    print("=" * 60)
    print(f"\n1. F1 vs Error Severity: {fig1}")
    print(f"2. Join Strategy Comparison: {fig2}")
    print(f"3. Per-Circuit Performance Table: {fig3}")
    
    return [fig1, fig2, fig3]


if __name__ == "__main__":
    main()

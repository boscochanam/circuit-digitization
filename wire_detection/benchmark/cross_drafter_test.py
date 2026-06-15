#!/usr/bin/env python3
"""
Cross-Drafter Generalization Test
==================================
Split the 134-image benchmark into D1-only and D2-only subsets,
run the best config (v4 baseline with anchor_endpoint_dist=12) on each,
and compare F1 scores.
"""
from __future__ import annotations
import json, re, sys, time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, '/home/claw/circuit-digitization')
sys.path.insert(0, '/home/claw/workspace')

from wire_detection.benchmark.expanded_benchmark import (
    preload_all_images, run_config, _all_image_data
)
from wire_detection.benchmark.experiment_harness import ExperimentConfig

# ── Config: v4 baseline with anchor_endpoint_dist=12 ──
V4_CONFIG = ExperimentConfig(
    name="v4_baseline",
    sauvola_k=0.285, sauvola_window=67,
    close_kernel=3, ccl_min_area=28,
    dedup_angle=10.0, dedup_dist=18.0,
    crop_padding=10, occlusion_margin=0.15,
    normalize_mode="none", endpoint_mode="pca",
    dedup_mode="overlap",
    anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
)

def classify_drafter(image_name: str) -> str | None:
    """Extract drafter ID (D1, D2, ...) from image name like C100_D1_P4_jpg."""
    m = re.search(r'_D(\d+)_', image_name)
    if m:
        return f"D{m.group(1)}"
    return None

def split_by_drafter():
    """Load all images and split into per-drafter subsets."""
    data = preload_all_images()
    
    drafter_groups: dict[str, list] = {}
    for item in data:
        image_name = item[0]
        drafter = classify_drafter(image_name)
        if drafter:
            drafter_groups.setdefault(drafter, []).append(item)
    
    return drafter_groups

def run_subset(name: str, subset: list) -> dict:
    """Run V4 config on a subset of images, return results dict."""
    import wire_detection.benchmark.expanded_benchmark as eb
    # Temporarily replace the global data
    original = eb._all_image_data
    eb._all_image_data = subset
    
    t0 = time.time()
    summary = run_config(V4_CONFIG)
    elapsed = time.time() - t0
    
    # Restore
    eb._all_image_data = original
    
    return {
        "name": name,
        "n_images": len(subset),
        "f1": summary.global_f1,
        "precision": summary.precision,
        "recall": summary.recall,
        "tp": summary.tp,
        "fp": summary.fp,
        "fn": summary.fn,
        "red": summary.red,
        "elapsed_s": round(elapsed, 1),
        "per_image": [asdict(img) for img in summary.images],
    }

def print_report(results: list[dict]):
    """Print a formatted comparison report."""
    print("\n" + "=" * 90)
    print("CROSS-DRAFTER GENERALIZATION REPORT")
    print("Config: v4_baseline (anchor_endpoint_dist=12)")
    print("=" * 90)
    
    print(f"\n{'Subset':<15} {'Images':>7} {'F1':>8} {'Prec':>8} {'Rec':>8} {'TP':>6} {'FP':>6} {'FN':>6} {'Red':>6} {'Time':>7}")
    print("-" * 90)
    
    for r in results:
        print(f"{r['name']:<15} {r['n_images']:>7d} {r['f1']:>8.4f} {r['precision']:>8.4f} {r['recall']:>8.4f} "
              f"{r['tp']:>6d} {r['fp']:>6d} {r['fn']:>6d} {r['red']:>6d} {r['elapsed_s']:>6.1f}s")
    
    print("-" * 90)
    
    if len(results) >= 2:
        f1_d1 = next((r['f1'] for r in results if r['name'] == 'D1'), None)
        f1_d2 = next((r['f1'] for r in results if r['name'] == 'D2'), None)
        if f1_d1 is not None and f1_d2 is not None:
            diff = f1_d1 - f1_d2
            better = "D1" if diff > 0 else "D2"
            print(f"\nF1 difference: {abs(diff):.4f} (better: {better})")
            print(f"D1 F1: {f1_d1:.4f}  |  D2 F1: {f1_d2:.4f}")
    
    # Also show overall
    overall = next((r for r in results if r['name'] == 'ALL'), None)
    if overall:
        print(f"\nOverall (all images): F1={overall['f1']:.4f}, P={overall['precision']:.4f}, R={overall['recall']:.4f}")

def main():
    print("Preloading all images...")
    drafter_groups = split_by_drafter()
    
    print(f"\nDrafter distribution:")
    for d in sorted(drafter_groups.keys()):
        names = [item[0] for item in drafter_groups[d]]
        print(f"  {d}: {len(drafter_groups[d])} images")
    
    # Run on D1, D2, and ALL
    results = []
    
    for drafter in sorted(drafter_groups.keys()):
        subset = drafter_groups[drafter]
        print(f"\nRunning v4_baseline on {drafter} ({len(subset)} images)...", flush=True)
        r = run_subset(drafter, subset)
        results.append(r)
        print(f"  F1={r['f1']:.4f}  P={r['precision']:.4f}  R={r['recall']:.4f}  TP={r['tp']} FP={r['fp']} FN={r['fn']}")
    
    # Run on ALL
    print(f"\nRunning v4_baseline on ALL images...", flush=True)
    all_data = []
    for subset in drafter_groups.values():
        all_data.extend(subset)
    r_all = run_subset("ALL", all_data)
    results.append(r_all)
    print(f"  F1={r_all['f1']:.4f}  P={r_all['precision']:.4f}  R={r_all['recall']:.4f}  TP={r_all['tp']} FP={r_all['fp']} FN={r_all['fn']}")
    
    print_report(results)
    
    # ── Per-image breakdown for D1 vs D2 ──
    print("\n" + "=" * 90)
    print("PER-IMAGE BREAKDOWN: D1 vs D2")
    print("=" * 90)
    
    for r in results:
        if r['name'] in ('D1', 'D2'):
            print(f"\n── {r['name']} ({r['n_images']} images) ──")
            # Sort by F1 ascending to show worst first
            sorted_imgs = sorted(r['per_image'], key=lambda x: x['f1'])
            for img in sorted_imgs:
                tag_str = f"  [{','.join(img.get('tags', []))}]" if img.get('tags') else ""
                print(f"  {img['image']:<30s} F1={img['f1']:.4f}  P={img['p']:.4f}  R={img['r']:.4f}  "
                      f"GT={img['gt']:>3d}  Det={img['detected']:>3d}  "
                      f"TP={img['tp']:>3d} FP={img['fp']:>3d} FN={img['fn']:>3d}{tag_str}")
    
    # ── Save results ──
    out_dir = Path("output/benchmark_experiments/cross_drafter")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    save_data = []
    for r in results:
        save_r = {k: v for k, v in r.items() if k != 'per_image'}
        save_data.append(save_r)
    
    (out_dir / "cross_drafter_results.json").write_text(
        json.dumps(save_data, indent=2), encoding="utf-8"
    )
    
    # Save per-image breakdown too
    per_image_data = {}
    for r in results:
        if r['name'] in ('D1', 'D2', 'ALL'):
            per_image_data[r['name']] = r['per_image']
    (out_dir / "per_image_breakdown.json").write_text(
        json.dumps(per_image_data, indent=2), encoding="utf-8"
    )
    
    print(f"\nResults saved to: {out_dir}")

if __name__ == "__main__":
    main()

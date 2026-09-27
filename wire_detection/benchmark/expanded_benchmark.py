#!/usr/bin/env python3
"""EXPANDED BENCHMARK — run the 134-image wire study with committed identity labels.

Requires WIRE_GT_IMAGES to point to the original CGHD scans. Missing inputs fail closed;
no Roboflow prefix fallback can silently score augmented component labels.
"""
from __future__ import annotations
import json
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np

from wire_detection import paths
from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig, ImageResult, RunSummary,
    build_component_mask,
    crop_to_roi, shift_components, detect_wires_experiment, wave1_configs, wave2_configs, wave3_configs, wave4_configs,
)

# The committed label sets use matching `<stem>_jpg.txt` filenames. External source
# images must be supplied explicitly; see ground_truth/README.md.
GT_LABELS = paths.wire_labels_dir()
COMPONENT_LABELS = paths.component_labels_dir()


# Preload all image data
_all_image_data: list[tuple[str, np.ndarray, list, list]] | None = None

def preload_all_images():
    """Load all images and GT lines once."""
    global _all_image_data
    if _all_image_data is not None:
        return _all_image_data

    data = []
    image_root = paths.gt_images_dir()  # fail before computing any plausible partial result
    if not GT_LABELS.is_dir() or not COMPONENT_LABELS.is_dir():
        raise FileNotFoundError("Committed wire/component label directories are missing")
    all_images = sorted(GT_LABELS.glob("*_jpg.txt"))
    component_names = {p.name for p in COMPONENT_LABELS.glob("*_jpg.txt")}
    if len(all_images) != 134 or {p.name for p in all_images} != component_names:
        raise ValueError("Expected 134 matching wire and component identity-label files")
    for gt_file in all_images:
        image_name = gt_file.stem.removesuffix("_jpg")
        image_path = image_root / f"{image_name}_jpg.jpg"
        if not image_path.is_file():
            image_path = image_root / f"{image_name}.jpg"
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            raise FileNotFoundError(f"CGHD image missing or unreadable: {image_path}")
        h, w = gray.shape
        gt_lines = ref.load_ground_truth(gt_file, w, h)
        label_path = COMPONENT_LABELS / gt_file.name
        components = ref.parse_components(label_path, w, h)
        if not components:
            raise ValueError(f"No components in identity label file: {label_path}")
        data.append((image_name, gray, gt_lines, components))

    _all_image_data = data
    return data


def run_config(cfg: ExperimentConfig) -> RunSummary:
    """Run a single config across all preloaded images."""
    results: list[ImageResult] = []

    for image_name, gray, gt_lines, components in _all_image_data:
        h, w = gray.shape

        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_components = shift_components(components, ox, oy)

        lines_local = detect_wires_experiment(cropped, local_components, cfg)
        lines_global = [
            ((x1 + ox, y1 + oy), (x2 + ox, y2 + oy))
            for (x1, y1), (x2, y2) in lines_local
        ]

        tp, fp, fn, red = ref.evaluate(lines_global, gt_lines)
        precision = tp / max(tp + fp + red, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-8)

        img_result = ImageResult(
            image=image_name,
            gt=len(gt_lines),
            detected=len(lines_global),
            tp=tp, fp=fp, fn=fn, red=red,
            p=precision, r=recall, f1=f1,
            comps=len(components),
            has_hdc=True,
        )

        tags = []
        if f1 < 0.40: tags.append("hard")
        if fn >= max(4, len(gt_lines) // 3): tags.append("fn_heavy")
        if fp >= max(4, len(gt_lines) // 4): tags.append("fp_heavy")
        if red >= max(4, img_result.tp // 3) if img_result.tp else red >= 4: tags.append("redundant")
        if len(lines_global) == 0: tags.append("no_det")
        img_result.tags = tags
        results.append(img_result)

    tp_t = sum(r.tp for r in results)
    fp_t = sum(r.fp for r in results)
    fn_t = sum(r.fn for r in results)
    red_t = sum(r.red for r in results)
    precision_g = tp_t / max(tp_t + fp_t + red_t, 1)
    recall_g = tp_t / max(tp_t + fn_t, 1)
    global_f1 = 2 * precision_g * recall_g / max(precision_g + recall_g, 1e-8)

    return RunSummary(
        config=cfg,
        global_f1=global_f1,
        precision=precision_g,
        recall=recall_g,
        tp=tp_t, fp=fp_t, fn=fn_t, red=red_t,
        beat_reference=global_f1 > 0.7066,
        images=results,
    )


if __name__ == "__main__":
    # Gather all unique configs (wave1-4)
    all_configs = wave1_configs() + wave2_configs() + wave3_configs() + wave4_configs()
    # Remove duplicates by name
    seen: set[str] = set()
    unique_configs = []
    for cfg in all_configs:
        if cfg.name not in seen:
            seen.add(cfg.name)
            unique_configs.append(cfg)
    # Add the best_candidate_v4 manually
    unique_configs.append(ExperimentConfig(
        name="expanded_best_v4",
        sauvola_k=0.285, sauvola_window=67,
        close_kernel=3, ccl_min_area=28,
        dedup_angle=10.0, dedup_dist=18.0,
        crop_padding=10, occlusion_margin=0.15,
        normalize_mode="none", endpoint_mode="pca",
        dedup_mode="overlap",
        anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
    ))

    print(f"Preloading {len(preload_all_images())} images...\n")
    n_imgs = len(preload_all_images())

    t0 = time.time()
    summaries: list[RunSummary] = []
    for i, cfg in enumerate(unique_configs):
        tc = time.time()
        print(f"[{i+1}/{len(unique_configs)}] {cfg.name:30s} ... ", end="", flush=True)
        summary = run_config(cfg)
        elapsed = time.time() - tc
        print(f"F1={summary.global_f1:.4f}  P={summary.precision:.4f}  R={summary.recall:.4f}  "
              f"TP={summary.tp} FP={summary.fp} FN={summary.fn} Red={summary.red}  "
              f"({elapsed:.1f}s)")
        summaries.append(summary)

    total_time = time.time() - t0

    # ── Ranking ──
    ranking = sorted(summaries, key=lambda s: s.global_f1, reverse=True)

    print("\n" + "=" * 110)
    print("FULL RANKING — All configs on all 134 images")
    print("=" * 110)
    print(f"{'Rank':>4s} {'Name':30s} {'F1':>8s} {'Prec':>8s} {'Rec':>8s} {'TP':>5s} {'FP':>5s} {'FN':>5s} {'Red':>5s}  {'Imgs':>5s}")
    print("-" * 110)
    for rank, s in enumerate(ranking, 1):
        print(f"{rank:4d} {s.config.name:30s} {s.global_f1:.4f} {s.precision:.4f} {s.recall:.4f} "
              f"{s.tp:5d} {s.fp:5d} {s.fn:5d} {s.red:5d}  {len(s.images):4d}")
    print("-" * 110)

    # Show best vs worst spread
    best = ranking[0]
    worst = ranking[-1]
    print(f"\nBest:  {best.config.name:30s} F1={best.global_f1:.4f}")
    print(f"Worst: {worst.config.name:30s} F1={worst.global_f1:.4f}")
    print(f"Spread: {best.global_f1 - worst.global_f1:.4f}")

    # Compare to old reference baseline (which was on 23 images)
    print("\nOld reference baseline (23 images): F1=0.7066")
    ref23 = next((s for s in ranking if s.config.name == "baseline_control"), None)
    if ref23:
        print(f"Baseline on 134 images:              F1={ref23.global_f1:.4f}")

    print(f"\nTotal time: {total_time:.1f}s for {len(unique_configs)} configs x {n_imgs} images")

    # ── Save ──
    out_dir = Path("output/benchmark_experiments/expanded_full_ranking")
    out_dir.mkdir(parents=True, exist_ok=True)

    ranking_data = []
    for s in ranking:
        run_dir = out_dir / s.config.name
        run_dir.mkdir(exist_ok=True)
        (run_dir / "summary.json").write_text(
            json.dumps({
                "config": asdict(s.config),
                "global_f1": s.global_f1,
                "precision": s.precision,
                "recall": s.recall,
                "tp": s.tp, "fp": s.fp, "fn": s.fn, "red": s.red,
                "images": [asdict(img) for img in s.images],
            }, indent=2),
            encoding="utf-8",
        )
        ranking_data.append({
            "name": s.config.name,
            "global_f1": s.global_f1,
            "precision": s.precision,
            "recall": s.recall,
            "tp": s.tp, "fp": s.fp, "fn": s.fn, "red": s.red,
        })

    (out_dir / "full_ranking.json").write_text(
        json.dumps(ranking_data, indent=2), encoding="utf-8"
    )

    # ── Markdown table ──
    md = [
        "| Rank | Config | F1 | Precision | Recall | TP | FP | FN | Red |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, s in enumerate(ranking, 1):
        md.append(f"| {rank} | {s.config.name} | {s.global_f1:.4f} | {s.precision:.4f} | {s.recall:.4f} | "
                  f"{s.tp} | {s.fp} | {s.fn} | {s.red} |")
    (out_dir / "full_ranking.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\nResults saved to: {out_dir / 'full_ranking.json'}")

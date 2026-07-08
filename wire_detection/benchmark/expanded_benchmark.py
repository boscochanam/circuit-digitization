#!/usr/bin/env python3
"""
EXPANDED BENCHMARK — Run ALL experiment configs across all 134 images.
Uses filename prefix matching instead of pixel-diff.
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np

from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig, ImageResult, RunSummary,
    build_component_mask,
    crop_to_roi, shift_components, detect_wires_experiment, wave1_configs, wave2_configs, wave3_configs, wave4_configs,
)

_REPO = Path(__file__).resolve().parents[2]

# Data paths. Same env-var contract as build_net_gt.py; see ground_truth/README.md.
#
# The 134 ground-truth wire-polyline label files are committed (ground_truth/wire_labels/),
# so GT_LABELS needs no override. The CGHD source images are NOT redistributed here --
# point WIRE_GT_IMAGES at a directory of `<name>_jpg.jpg` files. Component labels come from
# the Roboflow export (roboflow_test2/), which is a local-only symlink.
GT_LABELS = Path(os.environ.get("WIRE_GT_WIRE_LABELS", _REPO / "ground_truth" / "wire_labels"))
# Committed CGHD component labels (identity copies, CC BY 4.0). When present these are
# used directly and no Roboflow export is needed for occlusion.
COMPONENT_LABELS = Path(
    os.environ.get("WIRE_COMPONENT_LABELS", _REPO / "ground_truth" / "component_labels")
)
# No default: ground_truth/local_eval/images holds the 31-image net-GT set, a DIFFERENT
# dataset. Defaulting there would silently score 31 of 134 and print a plausible F1.
_gt_images = os.environ.get("WIRE_GT_IMAGES")
GT_IMAGES = Path(_gt_images) if _gt_images else None
HDC_BASE = Path(os.environ.get("WIRE_HDC_BASE", _REPO / "roboflow_test2"))
ROB_IMAGES_BASE = HDC_BASE
HDC_SPLITS = os.environ.get("WIRE_HDC_SPLITS", "train,valid,test").split(",")


def find_hdc_label_by_prefix(image_name: str) -> Path | None:
    """Find HDC label by filename prefix matching (handles .rf.XXXX suffixes).

    .. warning::
       Returns the FIRST match — may be from an augmented version whose labels
       do NOT align with the original image.  Prefer :func:`find_exact_match`
       when loading labels for occlusion on original images.
    """
    for split in HDC_SPLITS:
        label_dir = HDC_BASE / split / "labels"
        matches = sorted(label_dir.glob(f"{image_name}_jpg.rf.*.txt"))
        if matches:
            return matches[0]
    for split in HDC_SPLITS:
        label_dir = HDC_BASE / split / "labels"
        matches = sorted(label_dir.glob(f"{image_name}_png.rf.*.txt"))
        if matches:
            return matches[0]
        matches = sorted(label_dir.glob(f"{image_name}_jpeg.rf.*.txt"))
        if matches:
            return matches[0]
    return None


def find_exact_match(image_name: str, orig_gray: np.ndarray) -> tuple[Path, Path] | None:
    """Find the Roboflow version pixel-identical to ``orig_gray`` and its label.

    CRITICAL (Jun 2026): Each Roboflow image has multiple ``.rf.<hash>`` versions —
    some augmented, some untouched.  ``find_rob_image()`` returns the first match
    (sorted by filename), which may be augmented.  Its labels are in a different
    coordinate space and will produce wrong occlusion polygons on the original.

    This function finds the version with pixel error < 0.01 (identical) and
    returns its label path.  Always prefer this over ``find_hdc_label_by_prefix``
    when the caller loads the original (non-augmented) image.
    """
    stem = f"{image_name}_jpg"
    for split in HDC_SPLITS:
        img_dir = ROB_IMAGES_BASE / split / "images"
        label_dir = ROB_IMAGES_BASE / split / "labels"
        if not img_dir.exists():
            continue
        for f in sorted(img_dir.glob(f"{stem}.rf.*.jpg")):
            rob = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
            if rob is not None and rob.shape == orig_gray.shape:
                err = np.mean(np.abs(orig_gray.astype(float) - rob.astype(float)))
                if err < 0.01:  # pixel-identical
                    label = label_dir / f"{f.stem}.txt"
                    if label.exists():
                        return (f, label)
    return None


# Cache: image_name -> components
_component_cache: dict[str, list] = {}
def load_components(image_name: str, w: int, h: int) -> list:
    """Load and cache HDC components for an image."""
    if image_name not in _component_cache:
        hdc_path = find_hdc_label_by_prefix(image_name)
        _component_cache[image_name] = ref.parse_components(hdc_path, w, h)
    return _component_cache[image_name]

def find_rob_image(image_name: str) -> Path | None:
    """Find the Roboflow augmented image (matches label orientation)."""
    for split in HDC_SPLITS:
        img_dir = ROB_IMAGES_BASE / split / "images"
        matches = sorted(img_dir.glob(f"{image_name}_jpg.rf.*.jpg"))
        if matches:
            return matches[0]
    return None


# Preload all image data
_all_image_data: list[tuple[str, np.ndarray, list, list]] | None = None

def preload_all_images():
    """Load all images and GT lines once."""
    global _all_image_data
    if _all_image_data is not None:
        return _all_image_data

    if not GT_LABELS.is_dir():
        raise SystemExit(f"GT_LABELS not found: {GT_LABELS}\nSet WIRE_GT_WIRE_LABELS.")
    if GT_IMAGES is None or not GT_IMAGES.is_dir():
        raise SystemExit(
            f"WIRE_GT_IMAGES is {'unset' if GT_IMAGES is None else f'not a directory: {GT_IMAGES}'}.\n"
            "The CGHD source images are not redistributed with this repo. Fetch CGHD-1152\n"
            "(https://doi.org/10.5281/zenodo.6385814) and point WIRE_GT_IMAGES at a directory of\n"
            "<name>_jpg.jpg files covering the 134 names in ground_truth/wire_labels/.\n"
            "Do NOT point it at ground_truth/local_eval/images -- that is the 31-image net-GT set.\n"
            "See ground_truth/README.md."
        )
    # The Roboflow export is only needed when the committed component labels are absent.
    if not COMPONENT_LABELS.is_dir() and not HDC_BASE.is_dir():
        raise SystemExit(
            f"Neither committed component labels ({COMPONENT_LABELS}) nor a Roboflow\n"
            f"export ({HDC_BASE}) is present. Set WIRE_COMPONENT_LABELS or WIRE_HDC_BASE."
        )

    data = []
    all_images = sorted(GT_LABELS.glob("*_jpg.txt"))
    for gt_file in all_images:
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = GT_IMAGES / f"{image_name}_jpg.jpg"

        # Load the ORIGINAL image (correct for evaluation)
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue

        h, w = gray.shape
        gt_lines = ref.load_ground_truth(gt_file, w, h)

        # CRITICAL: the occlusion labels must be in the ORIGINAL image's coordinate
        # space. Roboflow ships several `.rf.<hash>` copies per image and the name
        # gives no clue which is augmented; measured, 216/216 augmented copies carry
        # labels that differ from the identity copy's, and the identity copy is not
        # the sorted-first for 31 of 111 stems. Prefer the committed identity labels;
        # otherwise recover the identity copy by pixel comparison. Never fall back to
        # find_hdc_label_by_prefix() -- it returns an arbitrary copy and silently
        # produces a plausible, wrong F1 (otsu 0.5854 instead of 0.7894).
        committed = COMPONENT_LABELS / f"{image_name}_jpg.txt"
        if committed.exists():
            components = ref.parse_components(committed, w, h)
        else:
            exact = find_exact_match(image_name, gray)
            if not exact:
                raise SystemExit(
                    f"No pixel-identical Roboflow copy for {image_name}, and no committed\n"
                    f"label at {committed}. Augmented labels live in a different coordinate\n"
                    "space and would silently corrupt every metric. Refusing to guess.\n"
                    "See ground_truth/README.md, 'The Roboflow identity-copy trap'."
                )
            _, label_path = exact
            components = ref.parse_components(label_path, w, h)
        if not components:
            continue
        data.append((image_name, gray, gt_lines, components))

    # Never report metrics over a silently-truncated image set: an empty or partial run
    # still prints a plausible F1, and the published numbers assume all 134 images.
    if not data:
        raise SystemExit(
            f"Loaded 0 of {len(all_images)} images. Labels resolved ({GT_LABELS}) but no image\n"
            f"or component label matched. Check WIRE_GT_IMAGES ({GT_IMAGES}) and\n"
            f"WIRE_HDC_BASE ({HDC_BASE})."
        )
    if len(data) != len(all_images):
        print(
            f"WARNING: scored {len(data)} of {len(all_images)} labelled images — "
            f"{len(all_images) - len(data)} skipped (missing image or component label). "
            "The published results use all 134; these numbers are NOT comparable."
        )

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

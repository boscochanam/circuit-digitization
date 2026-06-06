#!/usr/bin/env python3
"""
Join evaluation on the 134-image GT set.

Runs every strategy in the registry, detects wires fresh with best_candidate_v4,
scores structural health, and outputs per-image results (JSONL) + summary.

Features:
  - Checkpoint/resume: skips images already in results.jsonl
  - Per-image JSONL: one line per image with per-strategy scores
  - Summary: aggregate table printed + saved as JSON + markdown

Run:
  python wire_detection/benchmark/join_eval_134.py
  python wire_detection/benchmark/join_eval_134.py --resume   # skip processed images
  python wire_detection/benchmark/join_eval_134.py --limit 10 # quick test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig,
    build_component_mask,
    crop_to_roi,
    detect_wires_experiment,
    shift_components,
)
from wire_detection.core.join_strategies import (
    STRATEGIES,
    make_pins,
    make_pins_junction_aware,
    run_strategy,
    score_netlist,
)

# ── Data paths (134-image GT set) ──
GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
GT_WIRE_LABELS = Path(
    "/home/claw/workspace/ground_truth/labels_few_annot/labels/train"
    "/manually_verified_no_background_data/images"
)
HDC_BASE = Path("/home/claw/circuit-digitization/roboflow_test2")
HDC_SPLITS = ["train", "valid", "test"]

# Output
OUT_DIR = Path(SCRIPT_DIR.parent.parent / "output" / "join_eval_134")

# ── Best candidate v4 config ──
CFG = ExperimentConfig(
    name="best_candidate_v4",
    sauvola_k=0.285,
    sauvola_window=67,
    close_kernel=3,
    ccl_min_area=28,
    fallback_ks=(),
    endpoint_mode="pca",
    dedup_mode="overlap",
    dedup_angle=12,
    dedup_dist=8,
    anchor_filter_enabled=True,
    anchor_endpoint_dist=12.0,
    anchor_link_dist=8.0,
)


# ── HDC label matching (prefix-based) ──
def find_hdc_label(image_name: str) -> Path | None:
    """Find HDC component label by filename prefix."""
    for split in HDC_SPLITS:
        label_dir = HDC_BASE / split / "labels"
        for ext in ["_jpg", "_png", "_jpeg"]:
            matches = sorted(label_dir.glob(f"{image_name}{ext}.rf.*.txt"))
            if matches:
                return matches[0]
    return None


def parse_components(text: str, w: int, h: int) -> list:
    """Parse YOLO-OBB component labels."""
    comps = []
    for line in text.splitlines():
        p = line.split()
        if len(p) != 9:
            continue
        try:
            cls = int(p[0])
            c = [float(x) for x in p[1:9]]
        except ValueError:
            continue
        xs = [int(c[i] * w) for i in range(0, 8, 2)]
        ys = [int(c[i] * h) for i in range(1, 8, 2)]
        comps.append(
            (cls, [(xs[i], ys[i]) for i in range(4)], (min(xs), min(ys), max(xs), max(ys)))
        )
    return comps


# ── Wire detection ──
def detect_wires(gray: np.ndarray, components: list) -> list:
    """Run best_candidate_v4 detection pipeline."""
    occ = build_component_mask(gray, components, CFG.occlusion_margin)
    if components:
        cropped, ox, oy = crop_to_roi(occ, components, CFG.crop_padding)
        local = shift_components(components, ox, oy)
    else:
        cropped, ox, oy, local = occ, 0, 0, []
    lines = detect_wires_experiment(cropped, local, CFG)
    return [((x1 + ox, y1 + oy), (x2 + ox, y2 + oy)) for (x1, y1), (x2, y2) in lines]


# ── Checkpoint management ──
def load_checkpoint(jsonl_path: Path) -> set[str]:
    """Load already-processed image names from JSONL."""
    done = set()
    if jsonl_path.exists():
        for line in jsonl_path.read_text().splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    done.add(rec["image"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


def append_result(jsonl_path: Path, record: dict) -> None:
    """Append a single result record to JSONL."""
    with open(jsonl_path, "a") as f:
        f.write(json.dumps(record) + "\n")


# ── Discover images ──
def discover_images() -> list[tuple[Path, Path | None]]:
    """Find all images with GT wire labels and their HDC component labels."""
    pairs = []
    for gt_file in sorted(GT_WIRE_LABELS.glob("*_jpg.txt")):
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = GT_IMAGES / f"{image_name}_jpg.jpg"
        if not image_path.exists():
            continue
        hdc = find_hdc_label(image_name)
        if hdc is None:
            continue
        pairs.append((image_path, hdc))
    return pairs


# ── Main ──
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resume", action="store_true", help="Skip images already in results.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="Max images to process (0=all)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUT_DIR / "results.jsonl"

    # Discover images
    all_pairs = discover_images()
    total = len(all_pairs)
    print(f"Found {total} images with GT wire labels + HDC component labels")

    # Load checkpoint
    done = set()
    if args.resume and jsonl_path.exists():
        done = load_checkpoint(jsonl_path)
        print(f"Resuming: {len(done)} images already processed")

    # Strategy names in expected performance order (best first)
    strategy_names = [s["name"] for s in STRATEGIES]
    # Reorder: graph_rescue first, then graph_*, then junction_*, then rest
    priority = [
        "graph_rescue", "graph_full", "graph_scale", "graph_dir_30", "graph_30",
        "junction_extend_n1", "junction_n1_30",
        "nearest2_30", "extend12_n1_30",
        "anchored2_30", "nearest1_30", "density_30",
        "all_18", "anchored1_30",
        "mutual_30", "nearest1_18",
        "production",
    ]
    strategy_names = [n for n in priority if n in strategy_names]

    # Run info
    run_info = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_images": total,
        "strategies": strategy_names,
        "config": CFG.name,
        "resumed_from": len(done),
    }
    (OUT_DIR / "run_info.json").write_text(json.dumps(run_info, indent=2))

    # Process images
    n_img = 0
    comp_tot = 0
    t0 = time.perf_counter()
    agg = {n: defaultdict(float) for n in strategy_names}

    # If resuming, re-aggregate from checkpoint
    if done:
        for line in jsonl_path.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            n = rec["image"]
            if n not in done:
                continue
            comp_tot += rec.get("components", 0)
            for s_name in strategy_names:
                if s_name in rec.get("strategies", {}):
                    sm = rec["strategies"][s_name]
                    for k in ("self_loop", "floating", "giant", "dangling", "unused"):
                        agg[s_name][k] += sm.get(k, 0)
                    agg[s_name]["ratio_sum"] += sm.get("nets_per_component", 0)
                    agg[s_name]["used_sum"] += sm.get("pct_wires_used", 0)
                    agg[s_name]["bal_sum"] += sm.get("balanced", 0)

    # Progress bar
    try:
        from tqdm import tqdm
        pbar = tqdm(total=total, desc="Join eval", unit="img", initial=len(done))
    except ImportError:
        pbar = None

    for image_path, hdc_path in all_pairs:
        image_name = image_path.stem  # e.g. C100_D1_P1_jpg
        if image_name in done:
            if pbar:
                pbar.update(1)
            continue
        if args.limit and n_img >= args.limit:
            break

        # Load image
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            if pbar:
                pbar.update(1)
            continue
        h, w = gray.shape

        # Load components
        assert hdc_path is not None  # filtered in discover_images
        hdc_text = hdc_path.read_text(encoding="utf-8")
        components = parse_components(hdc_text, w, h)
        if not components:
            if pbar:
                pbar.update(1)
            continue

        # Detect wires
        wires = detect_wires(gray, components)
        if not wires:
            if pbar:
                pbar.update(1)
            continue

        # Build pin sets (shared across strategies)
        std_pins = make_pins(wires, components)
        junc_pins = make_pins_junction_aware(wires, components)

        # Score every strategy
        strat_results = {}
        for s_name in strategy_names:
            pins, nl = run_strategy(s_name, wires, components, std_pins=std_pins, junc_pins=junc_pins)
            m = score_netlist(wires, components, pins, nl, 30.0)
            strat_results[s_name] = {
                "self_loop": m["self_loop_components"],
                "floating": m["floating_components"],
                "giant": m["giant_nets"],
                "dangling": m["dangling_wire_ends"],
                "unused": m["unused_wires"],
                "nets_per_component": m["nets_per_component"],
                "pct_wires_used": m["pct_wires_used"],
                "balanced": m["balanced"],
            }
            # Aggregate
            agg[s_name]["self_loop"] += m["self_loop_components"]
            agg[s_name]["floating"] += m["floating_components"]
            agg[s_name]["giant"] += m["giant_nets"]
            agg[s_name]["dangling"] += m["dangling_wire_ends"]
            agg[s_name]["unused"] += m["unused_wires"]
            agg[s_name]["ratio_sum"] += m["nets_per_component"]
            agg[s_name]["used_sum"] += m["pct_wires_used"]
            agg[s_name]["bal_sum"] += m["balanced"]

        # Record
        record = {
            "image": image_name,
            "components": len(components),
            "wires": len(wires),
            "strategies": strat_results,
        }
        append_result(jsonl_path, record)
        done.add(image_name)
        comp_tot += len(components)
        n_img += 1

        if pbar:
            pbar.update(1)
            pbar.set_postfix(img=n_img, wires=len(wires))
        elif n_img % 10 == 0:
            elapsed = time.perf_counter() - t0
            rate = n_img / elapsed if elapsed > 0 else 0
            eta = (total - len(done)) / rate if rate > 0 else 0
            print(f"  [{n_img}/{total}] {elapsed:.0f}s elapsed, ~{eta:.0f}s remaining", file=sys.stderr)

    if pbar:
        pbar.close()

    if n_img == 0 and not done:
        print("No images processed")
        return 1

    # Count actual processed
    total_processed = len(done)

    # ── Summary ──
    print("\n" + "=" * 120)
    print(f"JOIN EVALUATION — 134-image GT set  ({total_processed} images, {comp_tot} components, fresh best_candidate_v4 detection)")
    print("-" * 120)
    header = f"{'strategy':25s} {'self-loop':>9s} {'floating':>9s} {'giant':>7s} {'unused':>9s} {'w-used%':>8s} {'n/comp':>7s} {'composite':>10s} {'BALANCED':>9s}"
    print(header)
    print("-" * 120)

    rows = []
    for n in strategy_names:
        a = agg[n]
        count = total_processed if total_processed > 0 else 1
        composite = (a["self_loop"] + a["floating"] + a["giant"]) / max(1, comp_tot)
        balanced = a["bal_sum"] / count
        rows.append((n, a, composite, balanced, count))
    rows.sort(key=lambda r: r[3])  # sort by balanced

    for n, a, composite, balanced, count in rows:
        print(
            f"{n:25s} {int(a['self_loop']):9d} {int(a['floating']):9d} "
            f"{int(a['giant']):7d} {int(a['unused']):9d} {a['used_sum']/count:8.1f} "
            f"{a['ratio_sum']/count:7.3f} {composite:10.4f} {balanced:9.4f}"
        )
    print("=" * 120)
    print("Sorted by BALANCED (composite + under-connection penalty) — matches visual join quality.")
    print("composite = over-merge only; a strategy can game it by NOT connecting.")

    # ── Save summary ──
    summary = {}
    for n, a, composite, balanced, count in rows:
        summary[n] = {
            "self_loop": int(a["self_loop"]),
            "floating": int(a["floating"]),
            "giant": int(a["giant"]),
            "unused": int(a["unused"]),
            "wires_used_pct": round(a["used_sum"] / count, 1),
            "nets_per_component": round(a["ratio_sum"] / count, 3),
            "composite": round(composite, 4),
            "balanced": round(balanced, 4),
        }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    # ── Markdown table ──
    md_lines = [
        f"## Join Evaluation — 134-image GT set ({total_processed} images)",
        "",
        f"Timestamp: {run_info['timestamp']}",
        f"Config: {CFG.name}",
        "",
        "| Rank | Strategy | self-loop | floating | giant | unused | wires-used% | nets/comp | composite | balanced |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, (n, a, composite, balanced, count) in enumerate(rows, 1):
        md_lines.append(
            f"| {rank} | {n} | {int(a['self_loop'])} | {int(a['floating'])} | "
            f"{int(a['giant'])} | {int(a['unused'])} | {a['used_sum']/count:.1f} | "
            f"{a['ratio_sum']/count:.3f} | {composite:.4f} | {balanced:.4f} |"
        )
    (OUT_DIR / "summary.md").write_text("\n".join(md_lines))

    elapsed = time.perf_counter() - t0
    print(f"\nResults saved to: {OUT_DIR}")
    print(f"Total time: {elapsed:.1f}s for {total_processed} images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

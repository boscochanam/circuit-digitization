#!/usr/bin/env python3
"""
CONNECTIVITY EXPERIMENT — Test methods for connecting wire endpoints to components.

Methods tested:
  1. ray_cast       — extend endpoint along wire axis until hitting a component bbox
  2. nearest_edge   — project endpoint to closest point on any component bbox edge
  3. radial_search  — find component bboxes within radius R of endpoint
  4. axis_sweep     — extend H/V (Manhattan) from endpoint until hitting a bbox
  5. nearest_center — closest component center within radius (simple baseline)

Metrics:
  - connected_rate   : % of endpoints that reach a component
  - orphan_rate      : % of endpoints hitting nothing
  - both_connected   : % of wires where BOTH endpoints connect
  - avg_connections  : average components per endpoint (should be ~1)
  - wire_discard_rate: % of wires discarded (neither endpoint connects)
"""
from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "/home/claw/circuit-digitization")
sys.path.insert(0, "/home/claw/workspace")

from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig,
    build_component_mask,
    crop_to_roi,
    detect_wires_experiment,
    shift_components,
)

# ── Paths ──
GT_LABELS = Path("/home/claw/workspace/ground_truth/labels_few_annot/labels/train/manually_verified_no_background_data/images")
GT_IMAGES = Path("/home/claw/workspace/ground_truth/labels_few_annot/images")
HDC_BASE = Path("/home/claw/circuit-digitization/roboflow_test2")
HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = Path("/home/claw/circuit-digitization/output/connectivity_experiment")


# ── Component class names ──
COMPONENT_NAMES = {
    0: "and", 1: "antenna", 2: "capacitor-adjustable", 3: "capacitor-polarized",
    4: "capacitor-unpolarized", 5: "crossover", 6: "crystal", 7: "diac",
    8: "diode", 9: "diode-light_emitting", 10: "diode-thyrector", 11: "diode-zener",
    12: "fuse", 13: "gnd", 14: "inductor", 15: "inductor-ferrite",
    16: "integrated_circuit", 17: "integrated_circuit-ne555",
    18: "integrated_circuit-voltage_regulator", 19: "junction", 20: "lamp",
    21: "magnetic", 22: "mechanical", 23: "microphone", 24: "motor",
    25: "nand", 26: "not", 27: "operational_amplifier", 28: "optocoupler",
    29: "or", 30: "potentiometer", 31: "probe", 32: "relay",
    33: "resistor", 34: "resistor-adjustable", 35: "switch",
    36: "thermistor", 37: "transformer", 38: "transistor",
    39: "transistor-pnp", 40: "triac", 41: "varistor",
    42: "voltage_source", 43: "wire", 44: "terminal",
}


# ═══════════════════════════════════════════════
# DATA LOADING (shared with expanded_benchmark)
# ═══════════════════════════════════════════════

def find_hdc_label(image_name: str) -> Path | None:
    for split in HDC_SPLITS:
        label_dir = HDC_BASE / split / "labels"
        if not label_dir.exists():
            continue
        for suffix in ["_jpg", "_png", "_jpeg", ""]:
            pattern = f"{image_name}{suffix}.rf.*.txt" if suffix else f"{image_name}.rf.*.txt"
            matches = sorted(label_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def load_components(image_name: str, w: int, h: int) -> list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]]:
    """Load components as (class_id, vertices, bbox) tuples (harness-compatible)."""
    hdc_path = find_hdc_label(image_name)
    if hdc_path is None:
        return []
    return ref.parse_components(hdc_path, w, h)


def component_info(comp: tuple) -> dict:
    """Convert a component tuple to a display dict."""
    cls_id, vertices, bbox = comp
    return {
        "class_id": cls_id,
        "name": COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}"),
        "bbox": bbox,
        "vertices": vertices,
    }


# ═══════════════════════════════════════════════
# CONNECTIVITY METHODS
# ═══════════════════════════════════════════════

def _point_to_segment_dist(px, py, x1, y1, x2, y2):
    """Distance from point (px,py) to line segment (x1,y1)-(x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x, proj_y = x1 + t * dx, y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _line_intersects_rect(x1, y1, x2, y2, xmin, ymin, xmax, ymax):
    """Check if line segment intersects an axis-aligned rectangle."""
    # Check if either endpoint is inside
    if xmin <= x1 <= xmax and ymin <= y1 <= ymax:
        return True
    if xmin <= x2 <= xmax and ymin <= y2 <= ymax:
        return True
    # Check each edge of the rectangle
    edges = [
        (xmin, ymin, xmax, ymin), (xmax, ymin, xmax, ymax),
        (xmax, ymax, xmin, ymax), (xmin, ymax, xmin, ymin),
    ]
    for ex1, ey1, ex2, ey2 in edges:
        if _segments_intersect(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
            return True
    return False


def _segments_intersect(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    """Check if two line segments intersect."""
    def cross(ox, oy, ax, ay, bx, by):
        return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)
    d1 = cross(bx1, by1, bx2, by2, ax1, ay1)
    d2 = cross(bx1, by1, bx2, by2, ax2, ay2)
    d3 = cross(ax1, ay1, ax2, ay2, bx1, by1)
    d4 = cross(ax1, ay1, ax2, ay2, bx2, by2)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    if d1 == 0 and _on_segment(bx1, by1, bx2, by2, ax1, ay1): return True
    if d2 == 0 and _on_segment(bx1, by1, bx2, by2, ax2, ay2): return True
    if d3 == 0 and _on_segment(ax1, ay1, ax2, ay2, bx1, by1): return True
    if d4 == 0 and _on_segment(ax1, ay1, ax2, ay2, bx2, by2): return True
    return False


def _on_segment(px, py, qx, qy, rx, ry):
    return min(px, qx) <= rx <= max(px, qx) and min(py, qy) <= ry <= max(py, qy)


def _bbox_edge_nearest_point(px, py, bbox):
    """Find the nearest point on bbox edge to (px, py)."""
    xmin, ymin, xmax, ymax = bbox
    cx = max(xmin, min(px, xmax))
    cy = max(ymin, min(py, ymax))
    # If point is inside bbox, project to nearest edge
    if cx == px and cy == py:
        dists = [
            (abs(px - xmin), (xmin, py)),
            (abs(px - xmax), (xmax, py)),
            (abs(py - ymin), (px, ymin)),
            (abs(py - ymax), (px, ymax)),
        ]
        _, pt = min(dists)
        return pt
    return (cx, cy)


def connect_ray_cast(endpoint, wire_dir, components, max_dist=80):
    """Extend endpoint along wire direction until hitting a component bbox.
    Returns list of (component_index, hit_distance)."""
    ex, ey = endpoint
    dx, dy = wire_dir
    norm = math.hypot(dx, dy)
    if norm < 1e-6:
        return []
    dx, dy = dx / norm, dy / norm

    hits = []
    for ci, comp in enumerate(components):
        xmin, ymin, xmax, ymax = comp[2]
        # Step along ray and check bbox containment
        for step in range(1, int(max_dist) + 1, 2):
            rx, ry = int(ex + dx * step), int(ey + dy * step)
            if xmin <= rx <= xmax and ymin <= ry <= ymax:
                hits.append((ci, step))
                break
            # Also check reverse direction
            rx2, ry2 = int(ex - dx * step), int(ey - dy * step)
            if xmin <= rx2 <= xmax and ymin <= ry2 <= ymax:
                hits.append((ci, step))
                break
    # Sort by distance, return closest
    hits.sort(key=lambda x: x[1])
    return hits[:1] if hits else []


def connect_nearest_edge(endpoint, components, max_dist=50):
    """Find component whose bbox edge is nearest to endpoint."""
    ex, ey = endpoint
    best = None
    for ci, comp in enumerate(components):
        ne = _bbox_edge_nearest_point(ex, ey, comp[2])
        d = math.hypot(ex - ne[0], ey - ne[1])
        if d <= max_dist:
            if best is None or d < best[1]:
                best = (ci, d)
    return [best] if best else []


def connect_radial_search(endpoint, components, radius=40):
    """Find components whose bbox overlaps a circle around endpoint."""
    ex, ey = endpoint
    hits = []
    for ci, comp in enumerate(components):
        xmin, ymin, xmax, ymax = comp[2]
        # Closest point on bbox to circle center
        cx = max(xmin, min(ex, xmax))
        cy = max(ymin, min(ey, ymax))
        d = math.hypot(ex - cx, ey - cy)
        if d <= radius:
            hits.append((ci, d))
    hits.sort(key=lambda x: x[1])
    return hits[:1] if hits else []


def connect_axis_sweep(endpoint, components, max_dist=80):
    """Extend horizontally and vertically from endpoint until hitting a bbox.
    Manhattan routing assumption."""
    ex, ey = endpoint
    best = None
    for ci, comp in enumerate(components):
        xmin, ymin, xmax, ymax = comp[2]
        # Horizontal sweep right
        if ey >= ymin and ey <= ymax and ex <= xmax:
            d = xmax - ex
            if 0 < d <= max_dist:
                if best is None or d < best[1]:
                    best = (ci, d)
        # Horizontal sweep left
        if ey >= ymin and ey <= ymax and ex >= xmin:
            d = ex - xmin
            if 0 < d <= max_dist:
                if best is None or d < best[1]:
                    best = (ci, d)
        # Vertical sweep down
        if ex >= xmin and ex <= xmax and ey <= ymax:
            d = ymax - ey
            if 0 < d <= max_dist:
                if best is None or d < best[1]:
                    best = (ci, d)
        # Vertical sweep up
        if ex >= xmin and ex <= xmax and ey >= ymin:
            d = ey - ymin
            if 0 < d <= max_dist:
                if best is None or d < best[1]:
                    best = (ci, d)
    return [best] if best else []


def connect_nearest_center(endpoint, components, max_dist=60):
    """Simple baseline: closest component center within radius."""
    ex, ey = endpoint
    best = None
    for ci, comp in enumerate(components):
        xmin, ymin, xmax, ymax = comp[2]
        cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
        d = math.hypot(ex - cx, ey - cy)
        if d <= max_dist:
            if best is None or d < best[1]:
                best = (ci, d)
    return [best] if best else []


# Method registry
METHODS = {
    "ray_cast": connect_ray_cast,
    "nearest_edge": connect_nearest_edge,
    "radial_search": connect_radial_search,
    "axis_sweep": connect_axis_sweep,
    "nearest_center": connect_nearest_center,
}


# ═══════════════════════════════════════════════
# EXPERIMENT
# ═══════════════════════════════════════════════

@dataclass
class WireConnectivityResult:
    image: str
    n_components: int
    n_wires: int
    # Per-method results
    connected_endpoints: int = 0       # endpoints that hit a component
    orphan_endpoints: int = 0          # endpoints hitting nothing
    both_connected_wires: int = 0      # wires where both ends connect
    one_connected_wires: int = 0       # wires where one end connects
    zero_connected_wires: int = 0      # wires where neither end connects
    total_endpoints: int = 0
    multi_hit_endpoints: int = 0       # endpoints hitting >1 component
    connections: list = field(default_factory=list)  # list of (wire_idx, endpoint_idx, comp_idx, dist)


def run_connectivity_on_image(
    gray: np.ndarray,
    components: list[tuple],
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    method_name: str,
    method_fn,
    **kwargs,
) -> WireConnectivityResult:
    """Run a single connectivity method on one image's detected wires."""
    result = WireConnectivityResult(
        image="",
        n_components=len(components),
        n_wires=len(lines),
    )
    result.total_endpoints = len(lines) * 2

    for wi, (p1, p2) in enumerate(lines):
        # Get wire direction for ray_cast
        wire_dir = (p2[0] - p1[0], p2[1] - p1[1])

        ep1_hits = method_fn(p1, components, **kwargs) if method_name != "ray_cast" else method_fn(p1, wire_dir, components, **kwargs)
        ep2_hits = method_fn(p2, components, **kwargs) if method_name != "ray_cast" else method_fn(p2, wire_dir, components, **kwargs)

        ep1_connected = len(ep1_hits) > 0
        ep2_connected = len(ep2_hits) > 0

        if ep1_connected:
            result.connected_endpoints += 1
            if len(ep1_hits) > 1:
                result.multi_hit_endpoints += 1
            for ci, dist in ep1_hits:
                result.connections.append((wi, 0, ci, dist))
        else:
            result.orphan_endpoints += 1

        if ep2_connected:
            result.connected_endpoints += 1
            if len(ep2_hits) > 1:
                result.multi_hit_endpoints += 1
            for ci, dist in ep2_hits:
                result.connections.append((wi, 1, ci, dist))
        else:
            result.orphan_endpoints += 1

        if ep1_connected and ep2_connected:
            result.both_connected_wires += 1
        elif ep1_connected or ep2_connected:
            result.one_connected_wires += 1
        else:
            result.zero_connected_wires += 1

    return result


def run_experiment(
    method_name: str,
    method_fn,
    all_image_data: list[tuple[str, np.ndarray, list, list]] | None = None,
    **kwargs,
) -> dict:
    """Run a connectivity method across all images."""
    if all_image_data is None:
        all_image_data = preload_all_images()

    results: list[WireConnectivityResult] = []
    t0 = time.time()

    for image_name, gray, components, gt_lines in all_image_data:
        # Run best_v4 wire detection
        cfg = ExperimentConfig(
            name="best_v4",
            sauvola_k=0.285,
            sauvola_window=67,
            close_kernel=3,
            ccl_min_area=28,
            endpoint_mode="pca",
            dedup_mode="overlap",
            dedup_angle=10,
            dedup_dist=18,
            anchor_filter_enabled=True,
            anchor_endpoint_dist=12.0,
            anchor_link_dist=8.0,
        )
        h, w = gray.shape

        # Build component mask and crop
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_comps = shift_components(components, ox, oy)

        # Detect wires
        lines_local = detect_wires_experiment(cropped, local_comps, cfg)
        lines_global = [((x1 + ox, y1 + oy), (x2 + ox, y2 + oy)) for (x1, y1), (x2, y2) in lines_local]

        # Run connectivity
        r = run_connectivity_on_image(gray, components, lines_global, method_name, method_fn, **kwargs)
        r.image = image_name
        results.append(r)

    elapsed = time.time() - t0

    # Aggregate
    total_endpoints = sum(r.total_endpoints for r in results)
    total_connected = sum(r.connected_endpoints for r in results)
    total_orphan = sum(r.orphan_endpoints for r in results)
    total_both = sum(r.both_connected_wires for r in results)
    total_one = sum(r.one_connected_wires for r in results)
    total_zero = sum(r.zero_connected_wires for r in results)
    total_wires = sum(r.n_wires for r in results)
    total_multi = sum(r.multi_hit_endpoints for r in results)

    # Component hit distribution
    comp_hit_counts: dict[int, int] = {}
    for r in results:
        for wi, ei, ci, dist in r.connections:
            comp_hit_counts[ci] = comp_hit_counts.get(ci, 0) + 1

    summary = {
        "method": method_name,
        "kwargs": kwargs,
        "images": len(results),
        "total_wires": total_wires,
        "total_endpoints": total_endpoints,
        "connected_rate": round(total_connected / max(total_endpoints, 1), 4),
        "orphan_rate": round(total_orphan / max(total_endpoints, 1), 4),
        "both_connected_rate": round(total_both / max(total_wires, 1), 4),
        "one_connected_rate": round(total_one / max(total_wires, 1), 4),
        "zero_connected_rate": round(total_zero / max(total_wires, 1), 4),
        "wire_discard_rate": round(total_zero / max(total_wires, 1), 4),
        "multi_hit_rate": round(total_multi / max(total_endpoints, 1), 4),
        "elapsed_s": round(elapsed, 1),
    }

    return {"summary": summary, "results": results}


def preload_all_images():
    """Load all images, components, and GT lines."""
    data: list[tuple[str, np.ndarray, list, list]] = []
    all_gt = sorted(GT_LABELS.glob("*_jpg.txt"))
    print(f"Loading {len(all_gt)} images...")
    for gt_file in all_gt:
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = GT_IMAGES / f"{image_name}_jpg.jpg"
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape
        components = load_components(image_name, w, h)
        gt_lines = ref.load_ground_truth(gt_file, w, h)
        data.append((image_name, gray, components, gt_lines))
        if len(data) % 50 == 0:
            print(f"  loaded {len(data)}...")
    print(f"  done: {len(data)} images")
    return data


# ═══════════════════════════════════════════════
# VISUALIZATION
# ═══════════════════════════════════════════════

def visualize_connections(
    gray: np.ndarray,
    components: list[tuple],
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    result: WireConnectivityResult,
    method_name: str,
    output_path: Path,
):
    """Draw wire endpoints and their component connections on the image."""
    vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # Draw component bboxes
    for comp in components:
        xmin, ymin, xmax, ymax = comp[2]
        cv2.rectangle(vis, (xmin, ymin), (xmax, ymax), (0, 200, 0), 1)

    # Build connection lookup
    connected_eps = {}  # (wire_idx, endpoint_idx) -> (comp_idx, dist)
    for wi, ei, ci, dist in result.connections:
        connected_eps[(wi, ei)] = (ci, dist)

    # Draw wires
    for wi, (p1, p2) in enumerate(lines):
        cv2.line(vis, p1, p2, (0, 0, 255), 1)

        for ei, ep in enumerate([p1, p2]):
            if (wi, ei) in connected_eps:
                ci, dist = connected_eps[(wi, ei)]
                comp = components[ci]
                cx = (comp[2][0] + comp[2][2]) // 2
                cy = (comp[2][1] + comp[2][3]) // 2
                cv2.circle(vis, ep, 4, (0, 255, 0), -1)  # green = connected
                cv2.line(vis, ep, (cx, cy), (0, 255, 0), 1)
            else:
                cv2.circle(vis, ep, 4, (0, 0, 255), -1)  # red = orphan

    cv2.imwrite(str(output_path), vis)


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    vis_dir = OUTPUT_DIR / "visualizations"
    vis_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("CONNECTIVITY EXPERIMENT")
    print("=" * 60)

    # Preload all data
    all_data = preload_all_images()

    # Run all methods
    all_summaries = []

    for method_name, method_fn in METHODS.items():
        print(f"\n{'─' * 50}")
        print(f"Running: {method_name}")
        print(f"{'─' * 50}")

        # Set method-specific kwargs
        kwargs = {}
        if method_name == "ray_cast":
            kwargs = {"max_dist": 80}
        elif method_name == "nearest_edge":
            kwargs = {"max_dist": 50}
        elif method_name == "radial_search":
            kwargs = {"radius": 40}
        elif method_name == "axis_sweep":
            kwargs = {"max_dist": 80}
        elif method_name == "nearest_center":
            kwargs = {"max_dist": 60}

        result = run_experiment(method_name, method_fn, all_data, **kwargs)
        summary = result["summary"]
        all_summaries.append(summary)

        print(f"  Connected rate:     {summary['connected_rate']:.1%}")
        print(f"  Orphan rate:        {summary['orphan_rate']:.1%}")
        print(f"  Both-connected:     {summary['both_connected_rate']:.1%}")
        print(f"  One-connected:      {summary['one_connected_rate']:.1%}")
        print(f"  Zero-connected:     {summary['zero_connected_rate']:.1%}")
        print(f"  Wire discard rate:  {summary['wire_discard_rate']:.1%}")
        print(f"  Multi-hit rate:     {summary['multi_hit_rate']:.1%}")
        print(f"  Time: {summary['elapsed_s']:.1f}s")

        # Generate visualizations for first 3 images
        for i, r in enumerate(result["results"][:3]):
            image_name = r.image
            image_path = GT_IMAGES / f"{image_name}_jpg.jpg"
            gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if gray is None:
                continue
            h, w = gray.shape
            components = load_components(image_name, w, h)

            # Re-run detection to get lines (cached in practice)
            cfg = ExperimentConfig(
                name="best_v4", sauvola_k=0.285, sauvola_window=67,
                close_kernel=3, ccl_min_area=28, endpoint_mode="pca",
                dedup_mode="overlap", dedup_angle=10, dedup_dist=18,
                anchor_filter_enabled=True, anchor_endpoint_dist=12.0,
                anchor_link_dist=8.0,
            )
            occluded = build_component_mask(gray, components, cfg.occlusion_margin)
            cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
            local_comps = shift_components(components, ox, oy)
            lines_local = detect_wires_experiment(cropped, local_comps, cfg)
            lines_global = [((x1+ox, y1+oy), (x2+ox, y2+oy)) for (x1,y1),(x2,y2) in lines_local]

            out_path = vis_dir / f"{method_name}_{i}_{image_name}.jpg"
            visualize_connections(gray, components, lines_global, r, method_name, out_path)

    # Save results
    results_path = OUTPUT_DIR / "results.json"
    with open(results_path, "w") as f:
        json.dump(all_summaries, f, indent=2)
    print(f"\n✓ Results saved to {results_path}")

    # Print comparison table
    print(f"\n{'=' * 70}")
    print(f"{'METHOD':<18} {'CONN%':>7} {'ORPHAN%':>8} {'BOTH%':>7} {'DISCARD%':>9} {'MULTI%':>8}")
    print(f"{'─' * 70}")
    for s in all_summaries:
        print(f"{s['method']:<18} {s['connected_rate']:>6.1%} {s['orphan_rate']:>7.1%} "
              f"{s['both_connected_rate']:>6.1%} {s['wire_discard_rate']:>8.1%} "
              f"{s['multi_hit_rate']:>7.1%}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

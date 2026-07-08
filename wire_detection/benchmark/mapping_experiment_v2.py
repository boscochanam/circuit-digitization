#!/usr/bin/env python3
"""
WIRE-TO-COMPONENT MAPPING EXPERIMENT V2 — Exhaustive approach testing.

Goal: Find the best possible method for determining which wire connects to which component.
This is CRITICAL for SPICE netlist extraction.

Approaches:
  DISTANCE-BASED:
    1. nearest_bbox_edge — baseline (current 69%)
    2. nearest_bbox_center
    3. nearest_polygon_edge — actual OBB polygon distance
    4. nearest_polygon_vertex
    5. distance_inv_area — penalize large components

  DIRECTION-AWARE:
    6. ray_cast_forward — extend along wire direction
    7. ray_cast_both — extend both directions
    8. angle_weighted — cosine-weighted distance

  OBB PIN ESTIMATION:
    9. obb_pin_ends — 2-terminal pins at OBB long axis ends
    10. obb_all_corners — test all 4 corners
    11. component_type_pins — class-specific pin locations

  PIXEL/CONTOUR:
    12. pixel_trace — walk wire pixels to component boundary
    13. dilated_overlap — dilate wire mask, check component overlap
    14. edge_contour — edge detection near components

  GRAPH-BASED:
    15. hungarian — optimal global assignment
    16. junction_propagation — propagate through junctions
    17. topology_constraint — limit connections per component type

  ENSEMBLE:
    18. voting_top3 — majority vote of top 3
    19. weighted_ensemble — learned weights
    20. cascade — try methods in order of precision

Evaluation:
  - Use GT wire endpoints (not detected) to isolate mapping quality
  - Also test with detected wires (pipeline output)
  - Per-endpoint and per-wire accuracy
  - Per-component-type accuracy
  - Dense-area accuracy
  - Error analysis
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.benchmark.experiment_harness import (
    ExperimentConfig,
    build_component_mask,
    crop_to_roi,
    detect_wires_experiment,
    shift_components,
)
from wire_detection.benchmark.connectivity_experiment import COMPONENT_NAMES

from wire_detection.paths import gt_images_dir, gt_labels_dir, hdc_root, output_dir
# ── Paths ──
HDC_SPLITS = ["train", "valid", "test"]
OUTPUT_DIR = output_dir() / "mapping_experiment_v2"
LOG_FILE = OUTPUT_DIR / "status.log"


def log(msg: str):
    """Write to log file and stdout."""
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def find_hdc_label(image_name: str) -> Path | None:
    for split in HDC_SPLITS:
        label_dir = hdc_root() / split / "labels"
        if not label_dir.exists():
            continue
        for suffix in ["_jpg", "_png", "_jpeg", ""]:
            pattern = f"{image_name}{suffix}.rf.*.txt" if suffix else f"{image_name}.rf.*.txt"
            matches = sorted(label_dir.glob(pattern))
            if matches:
                return matches[0]
    return None


def load_components(image_name: str, w: int, h: int) -> list:
    hdc_path = find_hdc_label(image_name)
    if hdc_path is None:
        return []
    return ref.parse_components(hdc_path, w, h)


# ═══════════════════════════════════════════════════
# GEOMETRY HELPERS
# ═══════════════════════════════════════════════════

def point_to_bbox_dist(px: int, py: int, bbox: tuple) -> float:
    """Distance from point to nearest point on bbox edge."""
    xmin, ymin, xmax, ymax = bbox
    cx = max(xmin, min(px, xmax))
    cy = max(ymin, min(py, ymax))
    return math.hypot(px - cx, py - cy)


def point_to_segment_dist(px, py, ax, ay, bx, by) -> float:
    """Distance from point to line segment (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-10:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def point_to_polygon_dist(px: int, py: int, vertices: list) -> float:
    """Distance from point to nearest edge of polygon."""
    min_dist = float("inf")
    n = len(vertices)
    for i in range(n):
        ax, ay = vertices[i]
        bx, by = vertices[(i + 1) % n]
        d = point_to_segment_dist(px, py, ax, ay, bx, by)
        min_dist = min(min_dist, d)
    return min_dist


def point_to_polygon_vertex_dist(px: int, py: int, vertices: list) -> float:
    """Distance from point to nearest polygon vertex."""
    return min(math.hypot(px - vx, py - vy) for vx, vy in vertices)


def get_obb_pins(vertices: list) -> list[tuple[int, int]]:
    """Get pin locations from OBB vertices — ends of the long axis."""
    # vertices are 4 corners of oriented bounding box
    # Find the long axis by checking which pair of opposite corners has longer distance
    d02 = math.hypot(vertices[0][0] - vertices[2][0], vertices[0][1] - vertices[2][1])
    d13 = math.hypot(vertices[1][0] - vertices[3][0], vertices[1][1] - vertices[3][1])

    if d02 >= d13:
        # Long axis is 0-2
        mid1 = ((vertices[0][0] + vertices[1][0]) // 2, (vertices[0][1] + vertices[1][1]) // 2)
        mid2 = ((vertices[2][0] + vertices[3][0]) // 2, (vertices[2][1] + vertices[3][1]) // 2)
    else:
        # Long axis is 1-3
        mid1 = ((vertices[1][0] + vertices[2][0]) // 2, (vertices[1][1] + vertices[2][1]) // 2)
        mid2 = ((vertices[3][0] + vertices[0][0]) // 2, (vertices[3][1] + vertices[0][1]) // 2)

    return [mid1, mid2]


def get_component_pins(cls_id: int, vertices: list) -> list[tuple[int, int]]:
    """Estimate pin locations based on component type."""
    bbox_center = (
        sum(v[0] for v in vertices) // len(vertices),
        sum(v[1] for v in vertices) // len(vertices),
    )

    name = COMPONENT_NAMES.get(cls_id, "")

    # 2-terminal components
    two_terminal = {
        "resistor", "capacitor-unpolarized", "capacitor-polarized",
        "inductor", "diode", "diode-zener", "diode-light_emitting",
        "fuse", "led", "thermistor", "varistor", "crystal",
        "resistor-adjustable", "capacitor-adjustable", "inductor-ferrite",
    }

    if name in two_terminal or "diode" in name or "capacitor" in name or "resistor" in name:
        return get_obb_pins(vertices)

    # 3-terminal components
    three_terminal = {"transistor", "transistor-pnp", "operational_amplifier"}
    if name in three_terminal or "transistor" in name:
        pins = get_obb_pins(vertices)
        # Add third pin at center or opposite side
        pins.append(bbox_center)
        return pins

    # Multi-terminal (ICs, etc.)
    ic_types = {"integrated_circuit", "integrated_circuit-ne555", "integrated_circuit-voltage_regulator"}
    if name in ic_types or "integrated" in name:
        # Return all 4 corners + edge midpoints
        pins = list(vertices)
        for i in range(len(vertices)):
            mid = (
                (vertices[i][0] + vertices[(i + 1) % len(vertices)][0]) // 2,
                (vertices[i][1] + vertices[(i + 1) % len(vertices)][1]) // 2,
            )
            pins.append(mid)
        return pins

    # Default: use OBB pin ends
    return get_obb_pins(vertices)


def get_bbox_edge_nearest_point(px: int, py: int, bbox: tuple) -> tuple[int, int]:
    """Get the nearest point on bbox edge to (px, py)."""
    xmin, ymin, xmax, ymax = bbox
    cx = max(xmin, min(px, xmax))
    cy = max(ymin, min(py, ymax))
    return (cx, cy)


# ═══════════════════════════════════════════════════
# MAPPING METHODS
# ═══════════════════════════════════════════════════

def map_nearest_bbox_edge(ep, components, **kw) -> int:
    """1. Nearest component by bbox edge distance."""
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        d = point_to_bbox_dist(ep[0], ep[1], comp[2])
        if d < best_d:
            best_d = d
            best_ci = ci
    return best_ci


def map_nearest_bbox_center(ep, components, **kw) -> int:
    """2. Nearest component by bbox center distance."""
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        bbox = comp[2]
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        d = math.hypot(ep[0] - cx, ep[1] - cy)
        if d < best_d:
            best_d = d
            best_ci = ci
    return best_ci


def map_nearest_polygon_edge(ep, components, **kw) -> int:
    """3. Nearest component by actual polygon edge distance."""
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        d = point_to_polygon_dist(ep[0], ep[1], comp[1])
        if d < best_d:
            best_d = d
            best_ci = ci
    return best_ci


def map_nearest_polygon_vertex(ep, components, **kw) -> int:
    """4. Nearest component by polygon vertex distance."""
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        d = point_to_polygon_vertex_dist(ep[0], ep[1], comp[1])
        if d < best_d:
            best_d = d
            best_ci = ci
    return best_ci


def map_distance_inv_area(ep, components, **kw) -> int:
    """5. Distance weighted by inverse component area (prefer smaller components)."""
    best_ci, best_score = -1, float("inf")
    for ci, comp in enumerate(components):
        bbox = comp[2]
        area = max((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), 1)
        d = point_to_bbox_dist(ep[0], ep[1], bbox)
        # Score: distance * log(area) — penalize large components
        score = d * (1 + math.log10(area) * 0.3)
        if score < best_score:
            best_score = score
            best_ci = ci
    return best_ci


def map_ray_cast_forward(ep, components, wire_dir=None, **kw) -> int:
    """6. Cast ray from endpoint along wire direction."""
    if wire_dir is None:
        return map_nearest_bbox_edge(ep, components)

    dx, dy = wire_dir
    best_ci, best_d = -1, float("inf")

    for ci, comp in enumerate(components):
        bbox = comp[2]
        # Cast ray in wire direction
        for step in range(1, 80, 2):
            rx = int(ep[0] + dx * step)
            ry = int(ep[1] + dy * step)
            if bbox[0] <= rx <= bbox[2] and bbox[1] <= ry <= bbox[3]:
                if step < best_d:
                    best_d = step
                    best_ci = ci
                break
            # Also check reverse direction from ep (wire may approach from opposite side)
            rx2 = int(ep[0] - dx * step)
            ry2 = int(ep[1] - dy * step)
            if bbox[0] <= rx2 <= bbox[2] and bbox[1] <= ry2 <= bbox[3]:
                if step < best_d:
                    best_d = step
                    best_ci = ci
                break
    return best_ci


def map_ray_cast_both(ep, components, wire_dir=None, **kw) -> int:
    """7. Cast rays in both wire direction and perpendicular."""
    best_ci, best_d = -1, float("inf")

    directions = []
    if wire_dir is not None:
        dx, dy = wire_dir
        directions = [(dx, dy), (-dx, -dy), (-dy, dx), (dy, -dx)]  # forward, back, perp-left, perp-right
    else:
        # 8 cardinal directions
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            directions.append((math.cos(rad), math.sin(rad)))

    for ci, comp in enumerate(components):
        bbox = comp[2]
        for ddx, ddy in directions:
            for step in range(1, 60, 2):
                rx = int(ep[0] + ddx * step)
                ry = int(ep[1] + ddy * step)
                if bbox[0] <= rx <= bbox[2] and bbox[1] <= ry <= bbox[3]:
                    if step < best_d:
                        best_d = step
                        best_ci = ci
                    break
    return best_ci


def map_angle_weighted(ep, components, wire_dir=None, **kw) -> int:
    """8. Distance weighted by angle alignment with wire direction."""
    if wire_dir is None:
        return map_nearest_bbox_edge(ep, components)

    dx, dy = wire_dir
    best_ci, best_score = -1, float("inf")

    for ci, comp in enumerate(components):
        bbox = comp[2]
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2

        # Direction from endpoint to component center
        to_comp_x = cx - ep[0]
        to_comp_y = cy - ep[1]
        to_comp_len = math.hypot(to_comp_x, to_comp_y)

        if to_comp_len < 1e-6:
            return ci

        # Cosine similarity
        cos_sim = (to_comp_x * dx + to_comp_y * dy) / to_comp_len

        d = point_to_bbox_dist(ep[0], ep[1], bbox)
        # Penalize misalignment: score = distance / (1 + cosine_similarity)
        # Higher cosine similarity = lower score = better
        score = d / (1.0 + max(cos_sim, 0))

        if score < best_score:
            best_score = score
            best_ci = ci

    return best_ci


def map_obb_pin_ends(ep, components, **kw) -> int:
    """9. Distance to OBB pin endpoints (midpoints of short edges)."""
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        pins = get_obb_pins(comp[1])
        for px, py in pins:
            d = math.hypot(ep[0] - px, ep[1] - py)
            if d < best_d:
                best_d = d
                best_ci = ci
    return best_ci


def map_obb_all_corners(ep, components, **kw) -> int:
    """10. Distance to nearest OBB corner."""
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        for vx, vy in comp[1]:
            d = math.hypot(ep[0] - vx, ep[1] - vy)
            if d < best_d:
                best_d = d
                best_ci = ci
    return best_ci


def map_component_type_pins(ep, components, **kw) -> int:
    """11. Distance to component-type-specific pin locations."""
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        pins = get_component_pins(comp[0], comp[1])
        for px, py in pins:
            d = math.hypot(ep[0] - px, ep[1] - py)
            if d < best_d:
                best_d = d
                best_ci = ci
    return best_ci


def map_pixel_trace(ep, components, binary_image=None, **kw) -> int:
    """12. Walk pixels from endpoint along wire until hitting component region."""
    if binary_image is None:
        return map_nearest_bbox_edge(ep, components)

    best_ci, best_d = -1, float("inf")
    h, w = binary_image.shape

    # Create component masks
    comp_masks = []
    for ci, comp in enumerate(components):
        mask = np.zeros((h, w), dtype=np.uint8)
        pts = np.array(comp[1], dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
        comp_masks.append((ci, mask))

    # Walk in 8 directions from endpoint
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        dx, dy = math.cos(rad), math.sin(rad)

        for step in range(5, 80, 3):
            rx = int(ep[0] + dx * step)
            ry = int(ep[1] + dy * step)

            if 0 <= rx < w and 0 <= ry < h:
                for ci, mask in comp_masks:
                    if mask[ry, rx] > 0:
                        if step < best_d:
                            best_d = step
                            best_ci = ci
                        break
                else:
                    continue
                break  # Found a hit

    # If no hit, fall back to nearest bbox
    if best_ci < 0:
        return map_nearest_bbox_edge(ep, components)

    return best_ci


def map_dilated_overlap(ep, components, binary_image=None, **kw) -> int:
    """13. Create dilated point mask, check overlap with component polygons."""
    if binary_image is None:
        return map_nearest_bbox_edge(ep, components)

    h, w = binary_image.shape

    # Create a small circle mask around the endpoint
    point_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(point_mask, (int(ep[0]), int(ep[1])), 15, 255, -1)

    best_ci, best_overlap = -1, 0
    for ci, comp in enumerate(components):
        comp_mask = np.zeros((h, w), dtype=np.uint8)
        pts = np.array(comp[1], dtype=np.int32)
        cv2.fillPoly(comp_mask, [pts], 255)

        overlap = cv2.countNonZero(cv2.bitwise_and(point_mask, comp_mask))
        if overlap > best_overlap:
            best_overlap = overlap
            best_ci = ci

    if best_ci < 0:
        return map_nearest_bbox_edge(ep, components)

    return best_ci


def map_edge_contour(ep, components, gray_image=None, **kw) -> int:
    """14. Use edge detection to find component boundaries, map to nearest edge."""
    if gray_image is None:
        return map_nearest_bbox_edge(ep, components)

    edges = cv2.Canny(gray_image, 50, 150)

    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        bbox = comp[2]
        # Create mask for this component's region (expanded by margin)
        margin = 20
        x1 = max(0, bbox[0] - margin)
        y1 = max(0, bbox[1] - margin)
        x2 = min(gray_image.shape[1], bbox[2] + margin)
        y2 = min(gray_image.shape[0], bbox[3] + margin)

        # Count edge pixels in this region near the endpoint
        roi_edges = edges[y1:y2, x1:x2]
        edge_count = cv2.countNonZero(roi_edges)

        # Distance to component
        d = point_to_bbox_dist(ep[0], ep[1], bbox)

        # Score: distance (edge count is just a tiebreaker)
        if d < best_d:
            best_d = d
            best_ci = ci

    return best_ci


def map_bbox_with_margin(ep, components, margin=10, **kw) -> int:
    """15. Nearest component using expanded bboxes (margin in px)."""
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        bbox = comp[2]
        expanded = (bbox[0] - margin, bbox[1] - margin, bbox[2] + margin, bbox[3] + margin)
        d = point_to_bbox_dist(ep[0], ep[1], expanded)
        if d < best_d:
            best_d = d
            best_ci = ci
    return best_ci


def map_bbox_with_area_penalty(ep, components, **kw) -> int:
    """16. Nearest component, penalized by component area ratio."""
    best_ci, best_score = -1, float("inf")

    # Compute median area
    areas = []
    for comp in components:
        bbox = comp[2]
        areas.append((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
    median_area = sorted(areas)[len(areas) // 2] if areas else 1

    for ci, comp in enumerate(components):
        bbox = comp[2]
        area = max((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), 1)
        d = point_to_bbox_dist(ep[0], ep[1], bbox)
        # Penalize if component is much larger than median
        area_ratio = area / max(median_area, 1)
        score = d * (1 + 0.1 * max(area_ratio - 1, 0))
        if score < best_score:
            best_score = score
            best_ci = ci
    return best_ci


def map_nearest_polygon_edge_margin(ep, components, margin=10, **kw) -> int:
    """17. Nearest polygon edge with expanded margin."""
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        d = point_to_polygon_dist(ep[0], ep[1], comp[1])
        d = max(0, d - margin)
        if d < best_d:
            best_d = d
            best_ci = ci
    return best_ci


def map_nearest_with_exclude(ep, components, exclude_ci=-1, **kw) -> int:
    """18. Nearest component excluding a specific component (for disambiguation)."""
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        if ci == exclude_ci:
            continue
        d = point_to_bbox_dist(ep[0], ep[1], comp[2])
        if d < best_d:
            best_d = d
            best_ci = ci
    return best_ci


def map_closest_non_junction(ep, components, **kw) -> int:
    """19. Nearest non-junction, non-terminal component."""
    JUNCTION_IDS = {19, 44}  # junction, terminal
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        if comp[0] in JUNCTION_IDS:
            continue
        d = point_to_bbox_dist(ep[0], ep[1], comp[2])
        if d < best_d:
            best_d = d
            best_ci = ci

    # Fall back to any component if no non-junction found
    if best_ci < 0:
        return map_nearest_bbox_edge(ep, components)
    return best_ci


def map_closest_non_junction_polygon(ep, components, **kw) -> int:
    """20. Nearest non-junction component by polygon edge distance."""
    JUNCTION_IDS = {19, 44}
    best_ci, best_d = -1, float("inf")
    for ci, comp in enumerate(components):
        if comp[0] in JUNCTION_IDS:
            continue
        d = point_to_polygon_dist(ep[0], ep[1], comp[1])
        if d < best_d:
            best_d = d
            best_ci = ci

    if best_ci < 0:
        return map_nearest_polygon_edge(ep, components)
    return best_ci


def map_two_nearest_agreement(ep, components, other_ep=None, **kw) -> int:
    """21. For each endpoint, find 2 nearest; if both endpoints share a component, use it."""
    if other_ep is None:
        return map_nearest_bbox_edge(ep, components)

    # Find 3 nearest to this endpoint
    dists1 = [(ci, point_to_bbox_dist(ep[0], ep[1], comp[2])) for ci, comp in enumerate(components)]
    dists1.sort(key=lambda x: x[1])

    # Find 3 nearest to other endpoint
    dists2 = [(ci, point_to_bbox_dist(other_ep[0], other_ep[1], comp[2])) for ci, comp in enumerate(components)]
    dists2.sort(key=lambda x: x[1])

    # Check if this endpoint's nearest is the other endpoint's nearest
    # If so, prefer the second nearest (the wire connects two DIFFERENT components)
    if dists1 and dists2:
        if dists1[0][0] == dists2[0][0]:
            # Same component nearest to both endpoints — pick second nearest for this one
            if len(dists1) > 1:
                return dists1[1][0]

    return dists1[0][0] if dists1 else -1


# ═══════════════════════════════════════════════════
# EVALUATION FRAMEWORK
# ═══════════════════════════════════════════════════

class MappingEvaluator:
    """Evaluates wire-to-component mapping quality."""

    def __init__(self, name: str, method_fn, needs_binary=False, needs_gray=False, needs_dir=False):
        self.name = name
        self.method_fn = method_fn
        self.needs_binary = needs_binary
        self.needs_gray = needs_gray
        self.needs_dir = needs_dir

        # Stats
        self.total_endpoints = 0
        self.correct_endpoints = 0
        self.total_wires = 0
        self.correct_wires_both = 0  # Both endpoints correct
        self.correct_wires_either = 0  # At least one endpoint correct
        self.per_comp_type = defaultdict(lambda: {"total": 0, "correct": 0})
        self.per_distance = defaultdict(lambda: {"total": 0, "correct": 0})
        self.errors = []  # Track worst errors

    def evaluate_endpoint(self, ep, comp_idx, components, gt_comp_idx, **extra_kwargs):
        """Evaluate a single endpoint mapping."""
        self.total_endpoints += 1

        kwargs = {"components": components}
        if self.needs_binary and "binary_image" in extra_kwargs:
            kwargs["binary_image"] = extra_kwargs["binary_image"]
        if self.needs_gray and "gray_image" in extra_kwargs:
            kwargs["gray_image"] = extra_kwargs["gray_image"]
        if self.needs_dir and "wire_dir" in extra_kwargs:
            kwargs["wire_dir"] = extra_kwargs["wire_dir"]

        predicted_ci = self.method_fn(ep, **kwargs)

        is_correct = (predicted_ci == gt_comp_idx)
        if is_correct:
            self.correct_endpoints += 1

        # Track by component type
        if gt_comp_idx >= 0 and gt_comp_idx < len(components):
            cls_id = components[gt_comp_idx][0]
            comp_name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
            self.per_comp_type[comp_name]["total"] += 1
            if is_correct:
                self.per_comp_type[comp_name]["correct"] += 1

        # Track by distance
        if gt_comp_idx >= 0 and gt_comp_idx < len(components):
            d = point_to_bbox_dist(ep[0], ep[1], components[gt_comp_idx][2])
            dist_bucket = int(d // 20) * 20
            self.per_distance[dist_bucket]["total"] += 1
            if is_correct:
                self.per_distance[dist_bucket]["correct"] += 1

        # Track errors
        if not is_correct and gt_comp_idx >= 0:
            err_dist = -1
            if gt_comp_idx < len(components):
                err_dist = point_to_bbox_dist(ep[0], ep[1], components[gt_comp_idx][2])
            self.errors.append({
                "ep": ep,
                "predicted": predicted_ci,
                "actual": gt_comp_idx,
                "dist": err_dist,
            })

        return predicted_ci

    def summary(self) -> dict:
        ep_acc = self.correct_endpoints / max(self.total_endpoints, 1)
        wire_acc = self.correct_wires_both / max(self.total_wires, 1)
        return {
            "name": self.name,
            "endpoint_accuracy": ep_acc,
            "wire_accuracy_both": wire_acc,
            "wire_accuracy_either": self.correct_wires_either / max(self.total_wires, 1),
            "total_endpoints": self.total_endpoints,
            "correct_endpoints": self.correct_endpoints,
            "total_wires": self.total_wires,
            "correct_wires_both": self.correct_wires_both,
        }


# ═══════════════════════════════════════════════════
# GROUND TRUTH WIRE→COMPONENT MAPPING
# ═══════════════════════════════════════════════════

def compute_gt_mapping(
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list,
    max_dist: float = 50.0,
) -> list[tuple[int, int]]:
    """
    For each wire, compute pseudo-GT component mapping.
    Maps each endpoint to the nearest non-junction component within max_dist.
    Returns list of (comp_idx_ep1, comp_idx_ep2) for each wire.
    """
    JUNCTION_IDS = {19, 44}  # junction, terminal — these are connection points, not real components

    gt_mappings = []
    for ep1, ep2 in wires:
        # Map ep1 — prefer non-junction
        best1 = -1
        best_d1 = float("inf")
        for ci, comp in enumerate(components):
            d = point_to_bbox_dist(ep1[0], ep1[1], comp[2])
            # Prefer non-junction, but allow junction if nothing else is close
            penalty = 0 if comp[0] not in JUNCTION_IDS else 10
            score = d + penalty
            if score < best_d1:
                best_d1 = score
                best1 = ci

        # Map ep2 — prefer non-junction
        best2 = -1
        best_d2 = float("inf")
        for ci, comp in enumerate(components):
            d = point_to_bbox_dist(ep2[0], ep2[1], comp[2])
            penalty = 0 if comp[0] not in JUNCTION_IDS else 10
            score = d + penalty
            if score < best_d2:
                best_d2 = score
                best2 = ci

        gt_mappings.append((best1, best2))

    return gt_mappings


def compute_gt_mapping_with_disambiguation(
    wires: list[tuple[tuple[int, int], tuple[int, int]]],
    components: list,
    max_dist: float = 50.0,
) -> list[tuple[int, int]]:
    """
    Better pseudo-GT: for each wire, if both endpoints map to the same component,
    try to assign one endpoint to a different nearby component.
    """
    JUNCTION_IDS = {19, 44}

    gt_mappings = []
    for ep1, ep2 in wires:
        # Get ranked candidates for each endpoint
        candidates1 = []
        candidates2 = []
        for ci, comp in enumerate(components):
            d1 = point_to_bbox_dist(ep1[0], ep1[1], comp[2])
            d2 = point_to_bbox_dist(ep2[0], ep2[1], comp[2])
            penalty1 = 0 if comp[0] not in JUNCTION_IDS else 10
            penalty2 = 0 if comp[0] not in JUNCTION_IDS else 10
            candidates1.append((ci, d1 + penalty1))
            candidates2.append((ci, d2 + penalty2))

        candidates1.sort(key=lambda x: x[1])
        candidates2.sort(key=lambda x: x[1])

        best1 = candidates1[0][0] if candidates1 else -1
        best2 = candidates2[0][0] if candidates2 else -1

        # If both map to same component, try to disambiguate
        if best1 == best2 and best1 >= 0:
            # Check if ep2 is closer to a different component
            if len(candidates2) > 1:
                # Is the second candidate close enough?
                if candidates2[1][1] < candidates2[0][1] + 30:  # within 30px
                    best2 = candidates2[1][0]

        gt_mappings.append((best1, best2))

    return gt_mappings


# ═══════════════════════════════════════════════════
# MAIN EXPERIMENT
# ═══════════════════════════════════════════════════

def run_mapping_experiments():
    log("=" * 80)
    log("WIRE-TO-COMPONENT MAPPING EXPERIMENT V2")
    log("=" * 80)

    cfg = ExperimentConfig(
        name="best_candidate_v4",
        sauvola_k=0.285, sauvola_window=67,
        close_kernel=3, ccl_min_area=28,
        dedup_angle=10.0, dedup_dist=18.0,
        crop_padding=10, occlusion_margin=0.15,
        normalize_mode="none", endpoint_mode="pca",
        dedup_mode="overlap",
        anchor_filter_enabled=True, anchor_endpoint_dist=12.0, anchor_link_dist=8.0,
    )

    # ── Load all images ──
    log("Loading images...")
    all_data = []
    for gt_file in sorted(gt_labels_dir().glob("*_jpg.txt")):
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = gt_images_dir() / f"{image_name}_jpg.jpg"
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape
        gt_lines = ref.load_ground_truth(gt_file, w, h)
        components = load_components(image_name, w, h)
        if not components:
            continue
        all_data.append((image_name, gray, gt_lines, components))

    log(f"Loaded {len(all_data)} images")

    # ── Define methods ──
    methods = [
        # (name, function, needs_binary, needs_gray, needs_dir)
        ("01_nearest_bbox_edge", map_nearest_bbox_edge, False, False, False),
        ("02_nearest_bbox_center", map_nearest_bbox_center, False, False, False),
        ("03_nearest_polygon_edge", map_nearest_polygon_edge, False, False, False),
        ("04_nearest_polygon_vertex", map_nearest_polygon_vertex, False, False, False),
        ("05_distance_inv_area", map_distance_inv_area, False, False, False),
        ("06_ray_cast_forward", map_ray_cast_forward, False, False, True),
        ("07_ray_cast_both", map_ray_cast_both, False, False, True),
        ("08_angle_weighted", map_angle_weighted, False, False, True),
        ("09_obb_pin_ends", map_obb_pin_ends, False, False, False),
        ("10_obb_all_corners", map_obb_all_corners, False, False, False),
        ("11_component_type_pins", map_component_type_pins, False, False, False),
        ("12_pixel_trace", map_pixel_trace, True, False, False),
        ("13_dilated_overlap", map_dilated_overlap, True, False, False),
        ("14_edge_contour", map_edge_contour, False, True, False),
        ("15_bbox_margin_10", lambda ep, **kw: map_bbox_with_margin(ep, margin=10, **kw), False, False, False),
        ("16_bbox_margin_20", lambda ep, **kw: map_bbox_with_margin(ep, margin=20, **kw), False, False, False),
        ("17_bbox_area_penalty", map_bbox_with_area_penalty, False, False, False),
        ("18_polygon_margin_10", lambda ep, **kw: map_nearest_polygon_edge_margin(ep, margin=10, **kw), False, False, False),
        ("19_skip_junction_bbox", map_closest_non_junction, False, False, False),
        ("20_skip_junction_polygon", map_closest_non_junction_polygon, False, False, False),
    ]

    # ═══════════════════════════════════════════════════
    # PHASE 1: GT WIRE ENDPOINT EVALUATION
    # ═══════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log("PHASE 1: GT WIRE ENDPOINT MAPPING (using ground truth wires)")
    log("=" * 80)

    # First, compute pseudo-GT for all wires
    log("\nComputing pseudo-GT mappings...")
    all_gt_mappings = []
    all_gt_wires_flat = []  # (image_idx, wire_idx, endpoint_idx, ep, gt_comp_idx)

    for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
        gt_maps = compute_gt_mapping_with_disambiguation(gt_lines, components)
        all_gt_mappings.append(gt_maps)

        for wi, ((ep1, ep2), (gt1, gt2)) in enumerate(zip(gt_lines, gt_maps)):
            all_gt_wires_flat.append((img_idx, wi, 0, ep1, gt1))
            all_gt_wires_flat.append((img_idx, wi, 1, ep2, gt2))

    log(f"Total GT endpoints to evaluate: {len(all_gt_wires_flat)}")

    # Prepare binary images for methods that need them
    log("Pre-processing binary images...")
    binary_cache = {}
    gray_cache = {}
    for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
        h, w = gray.shape
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        binary_cache[img_idx] = (cropped, ox, oy)
        gray_cache[img_idx] = gray

    # Run each method
    results = {}

    for method_name, method_fn, needs_binary, needs_gray, needs_dir in methods:
        log(f"\nEvaluating: {method_name}")
        t0 = time.time()

        total_ep = 0
        correct_ep = 0
        total_wires = 0
        correct_both = 0
        correct_either = 0
        per_comp = defaultdict(lambda: {"total": 0, "correct": 0})
        per_dist = defaultdict(lambda: {"total": 0, "correct": 0})

        for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
            cropped, ox, oy = binary_cache[img_idx]
            local_components = shift_components(components, ox, oy)

            gt_maps = all_gt_mappings[img_idx]

            for wi, ((ep1, ep2), (gt1, gt2)) in enumerate(zip(gt_lines, gt_maps)):
                # Map to local coordinates
                ep1_local = (ep1[0] - ox, ep1[1] - oy)
                ep2_local = (ep2[0] - ox, ep2[1] - oy)

                # Wire direction
                dx = ep2[0] - ep1[0]
                dy = ep2[1] - ep1[1]
                norm = math.hypot(dx, dy)
                wire_dir = (dx / norm, dy / norm) if norm > 1e-6 else (1, 0)

                extra = {}
                if needs_binary:
                    extra["binary_image"] = cropped
                if needs_gray:
                    extra["gray_image"] = gray
                if needs_dir:
                    extra["wire_dir"] = wire_dir

                # Evaluate ep1
                pred1 = method_fn(ep1_local, components=local_components, **extra)
                total_ep += 1
                ep1_correct = (pred1 == gt1)
                if ep1_correct:
                    correct_ep += 1

                # Track per component type
                if gt1 >= 0 and gt1 < len(local_components):
                    cls_id = local_components[gt1][0]
                    cname = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
                    per_comp[cname]["total"] += 1
                    if ep1_correct:
                        per_comp[cname]["correct"] += 1

                    d = point_to_bbox_dist(ep1_local[0], ep1_local[1], local_components[gt1][2])
                    db = int(d // 20) * 20
                    per_dist[db]["total"] += 1
                    if ep1_correct:
                        per_dist[db]["correct"] += 1

                # Evaluate ep2
                pred2 = method_fn(ep2_local, components=local_components, **extra)
                total_ep += 1
                ep2_correct = (pred2 == gt2)
                if ep2_correct:
                    correct_ep += 1

                if gt2 >= 0 and gt2 < len(local_components):
                    cls_id = local_components[gt2][0]
                    cname = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
                    per_comp[cname]["total"] += 1
                    if ep2_correct:
                        per_comp[cname]["correct"] += 1

                    d = point_to_bbox_dist(ep2_local[0], ep2_local[1], local_components[gt2][2])
                    db = int(d // 20) * 20
                    per_dist[db]["total"] += 1
                    if ep2_correct:
                        per_dist[db]["correct"] += 1

                # Wire-level
                total_wires += 1
                if ep1_correct and ep2_correct:
                    correct_both += 1
                if ep1_correct or ep2_correct:
                    correct_either += 1

        elapsed = time.time() - t0
        ep_acc = correct_ep / max(total_ep, 1)
        wire_both = correct_both / max(total_wires, 1)
        wire_either = correct_either / max(total_wires, 1)

        results[method_name] = {
            "endpoint_accuracy": ep_acc,
            "wire_accuracy_both": wire_both,
            "wire_accuracy_either": wire_either,
            "total_endpoints": total_ep,
            "correct_endpoints": correct_ep,
            "total_wires": total_wires,
            "per_comp_type": dict(per_comp),
            "per_distance": dict(per_dist),
            "elapsed": elapsed,
        }

        log(f"  Endpoint accuracy: {ep_acc:.4f} ({correct_ep}/{total_ep})")
        log(f"  Wire accuracy (both): {wire_both:.4f} ({correct_both}/{total_wires})")
        log(f"  Wire accuracy (either): {wire_either:.4f}")
        log(f"  Time: {elapsed:.1f}s")

    # ═══════════════════════════════════════════════════
    # PHASE 2: COMBINED / ENSEMBLE METHODS
    # ═══════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log("PHASE 2: ENSEMBLE & ADVANCED METHODS")
    log("=" * 80)

    # Sort Phase 1 results
    sorted_methods = sorted(results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True)
    top3_names = [m[0] for m in sorted_methods[:3]]
    top5_names = [m[0] for m in sorted_methods[:5]]

    log(f"\nTop 3 methods: {top3_names}")
    log(f"Top 5 methods: {top5_names}")

    # Run ensemble methods on a sample to save time
    # ... will implement voting, weighted, cascade here

    # ═══════════════════════════════════════════════════
    # PHASE 3: DETECTED WIRE EVALUATION
    # ═══════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log("PHASE 3: DETECTED WIRE MAPPING (using pipeline output)")
    log("=" * 80)

    # Run top 5 methods on detected wires
    det_results = {}

    for method_name in top5_names:
        method_fn = None
        needs_binary = False
        needs_gray = False
        needs_dir = False
        for mn, mf, nb, ng, nd in methods:
            if mn == method_name:
                method_fn = mf
                needs_binary = nb
                needs_gray = ng
                needs_dir = nd
                break

        if method_fn is None:
            continue

        log(f"\nEvaluating detected wires: {method_name}")
        t0 = time.time()

        total_ep = 0
        correct_ep = 0
        total_wires = 0
        correct_both = 0

        for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
            h, w = gray.shape
            occluded = build_component_mask(gray, components, cfg.occlusion_margin)
            cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
            local_components = shift_components(components, ox, oy)

            lines_local = detect_wires_experiment(cropped, local_components, cfg)

            for wire in lines_local:
                ep1, ep2 = wire
                ep1_global = (ep1[0] + ox, ep1[1] + oy)
                ep2_global = (ep2[0] + ox, ep2[1] + oy)

                # GT mapping for detected wire endpoints
                gt1 = -1
                best_d1 = float("inf")
                for ci, comp in enumerate(components):
                    d = point_to_bbox_dist(ep1_global[0], ep1_global[1], comp[2])
                    penalty = 0 if comp[0] not in {19, 44} else 10
                    if d + penalty < best_d1:
                        best_d1 = d + penalty
                        gt1 = ci

                gt2 = -1
                best_d2 = float("inf")
                for ci, comp in enumerate(components):
                    d = point_to_bbox_dist(ep2_global[0], ep2_global[1], comp[2])
                    penalty = 0 if comp[0] not in {19, 44} else 10
                    if d + penalty < best_d2:
                        best_d2 = d + penalty
                        gt2 = ci

                # Wire direction
                dx = ep2[0] - ep1[0]
                dy = ep2[1] - ep1[1]
                norm = math.hypot(dx, dy)
                wire_dir = (dx / norm, dy / norm) if norm > 1e-6 else (1, 0)

                extra = {}
                if needs_binary:
                    extra["binary_image"] = cropped
                if needs_gray:
                    extra["gray_image"] = gray
                if needs_dir:
                    extra["wire_dir"] = wire_dir

                pred1 = method_fn(ep1, components=local_components, **extra)
                pred2 = method_fn(ep2, components=local_components, **extra)

                total_ep += 2
                if pred1 == gt1:
                    correct_ep += 1
                if pred2 == gt2:
                    correct_ep += 1

                total_wires += 1
                if pred1 == gt1 and pred2 == gt2:
                    correct_both += 1

        elapsed = time.time() - t0
        ep_acc = correct_ep / max(total_ep, 1)
        wire_both = correct_both / max(total_wires, 1)

        det_results[method_name] = {
            "endpoint_accuracy": ep_acc,
            "wire_accuracy_both": wire_both,
            "total_endpoints": total_ep,
            "correct_endpoints": correct_ep,
            "total_wires": total_wires,
            "elapsed": elapsed,
        }

        log(f"  Endpoint accuracy: {ep_acc:.4f} ({correct_ep}/{total_ep})")
        log(f"  Wire accuracy (both): {wire_both:.4f} ({correct_both}/{total_wires})")
        log(f"  Time: {elapsed:.1f}s")

    # ═══════════════════════════════════════════════════
    # PHASE 4: FAILURE ANALYSIS
    # ═══════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log("PHASE 4: FAILURE ANALYSIS")
    log("=" * 80)

    # Analyze WHERE the best method fails
    best_method_name = sorted_methods[0][0]
    best_method_fn = None
    best_needs_binary = False
    best_needs_dir = False
    for mn, mf, nb, ng, nd in methods:
        if mn == best_method_name:
            best_method_fn = mf
            best_needs_binary = nb
            best_needs_dir = nd
            break

    if best_method_fn:
        # Collect failure cases
        failures = {
            "same_component": 0,  # Both endpoints map to same (should be different)
            "off_by_one": 0,  # Predicted is within 1 rank of correct
            "junction_error": 0,  # Correct was junction/terminal
            "dense_area": 0,  # Many components nearby
            "far_from_any": 0,  # Endpoint far from all components
        }

        total_failures = 0

        for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
            cropped, ox, oy = binary_cache[img_idx]
            local_components = shift_components(components, ox, oy)
            gt_maps = all_gt_mappings[img_idx]

            for wi, ((ep1, ep2), (gt1, gt2)) in enumerate(zip(gt_lines, gt_maps)):
                ep1_local = (ep1[0] - ox, ep1[1] - oy)
                ep2_local = (ep2[0] - ox, ep2[1] - oy)

                dx = ep2[0] - ep1[0]
                dy = ep2[1] - ep1[1]
                norm = math.hypot(dx, dy)
                wire_dir = (dx / norm, dy / norm) if norm > 1e-6 else (1, 0)

                extra = {}
                if best_needs_binary:
                    extra["binary_image"] = cropped
                if best_needs_dir:
                    extra["wire_dir"] = wire_dir

                pred1 = best_method_fn(ep1_local, components=local_components, **extra)
                pred2 = best_method_fn(ep2_local, components=local_components, **extra)

                for pred, gt, ep_local in [(pred1, gt1, ep1_local), (pred2, gt2, ep2_local)]:
                    if pred != gt:
                        total_failures += 1

                        # Check failure mode
                        if pred == gt1 and gt == gt2:  # Mapped to the other endpoint's component
                            failures["same_component"] += 1

                        if gt >= 0 and gt < len(local_components):
                            if local_components[gt][0] in {19, 44}:
                                failures["junction_error"] += 1

                            # Count nearby components
                            nearby = sum(1 for c in local_components
                                        if point_to_bbox_dist(ep_local[0], ep_local[1], c[2]) < 50)
                            if nearby >= 3:
                                failures["dense_area"] += 1

                            d = point_to_bbox_dist(ep_local[0], ep_local[1], local_components[gt][2])
                            if d > 30:
                                failures["far_from_any"] += 1

        log(f"\nFailure analysis for best method: {best_method_name}")
        log(f"Total failures: {total_failures}")
        for mode, count in sorted(failures.items(), key=lambda x: x[1], reverse=True):
            pct = count / max(total_failures, 1) * 100
            log(f"  {mode}: {count} ({pct:.1f}%)")

    # ═══════════════════════════════════════════════════
    # PHASE 5: HYPERPARAMETER SWEEP
    # ═══════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log("PHASE 5: HYPERPARAMETER SWEEP (top method)")
    log("=" * 80)

    # Sweep margin parameters for the best method
    if best_method_name in ["01_nearest_bbox_edge", "15_bbox_margin_10", "16_bbox_margin_20"]:
        log("\nSweeping bbox margin...")
        for margin in [0, 5, 8, 10, 12, 15, 20, 25, 30, 40, 50]:
            total_ep = 0
            correct_ep = 0

            for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
                cropped, ox, oy = binary_cache[img_idx]
                local_components = shift_components(components, ox, oy)
                gt_maps = all_gt_mappings[img_idx]

                for wi, ((ep1, ep2), (gt1, gt2)) in enumerate(zip(gt_lines, gt_maps)):
                    ep1_local = (ep1[0] - ox, ep1[1] - oy)
                    ep2_local = (ep2[0] - ox, ep2[1] - oy)

                    pred1 = map_bbox_with_margin(ep1_local, local_components, margin=margin)
                    pred2 = map_bbox_with_margin(ep2_local, local_components, margin=margin)

                    total_ep += 2
                    if pred1 == gt1:
                        correct_ep += 1
                    if pred2 == gt2:
                        correct_ep += 1

            acc = correct_ep / max(total_ep, 1)
            log(f"  margin={margin:3d}: endpoint_acc={acc:.4f}")

    elif best_method_name in ["03_nearest_polygon_edge", "18_polygon_margin_10"]:
        log("\nSweeping polygon margin...")
        for margin in [0, 5, 8, 10, 12, 15, 20, 25, 30]:
            total_ep = 0
            correct_ep = 0

            for img_idx, (image_name, gray, gt_lines, components) in enumerate(all_data):
                cropped, ox, oy = binary_cache[img_idx]
                local_components = shift_components(components, ox, oy)
                gt_maps = all_gt_mappings[img_idx]

                for wi, ((ep1, ep2), (gt1, gt2)) in enumerate(zip(gt_lines, gt_maps)):
                    ep1_local = (ep1[0] - ox, ep1[1] - oy)
                    ep2_local = (ep2[0] - ox, ep2[1] - oy)

                    pred1 = map_nearest_polygon_edge_margin(ep1_local, local_components, margin=margin)
                    pred2 = map_nearest_polygon_edge_margin(ep2_local, local_components, margin=margin)

                    total_ep += 2
                    if pred1 == gt1:
                        correct_ep += 1
                    if pred2 == gt2:
                        correct_ep += 1

            acc = correct_ep / max(total_ep, 1)
            log(f"  margin={margin:3d}: endpoint_acc={acc:.4f}")

    # ═══════════════════════════════════════════════════
    # SYNTHESIS
    # ═══════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log("SYNTHESIS")
    log("=" * 80)

    log("\nPhase 1 Results (GT wires, endpoint accuracy):")
    log(f"{'Method':<40s} {'EP Acc':>8s} {'Wire Both':>10s} {'Wire Either':>12s}")
    log("-" * 75)
    for name, res in sorted(results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True):
        log(f"{name:<40s} {res['endpoint_accuracy']:8.4f} {res['wire_accuracy_both']:10.4f} {res['wire_accuracy_either']:12.4f}")

    if det_results:
        log("\nPhase 3 Results (detected wires, endpoint accuracy):")
        log(f"{'Method':<40s} {'EP Acc':>8s} {'Wire Both':>10s}")
        log("-" * 65)
        for name, res in sorted(det_results.items(), key=lambda x: x[1]["endpoint_accuracy"], reverse=True):
            log(f"{name:<40s} {res['endpoint_accuracy']:8.4f} {res['wire_accuracy_both']:10.4f}")

    # Per-component-type breakdown for best method
    if best_method_name in results:
        per_comp = results[best_method_name].get("per_comp_type", {})
        if per_comp:
            log(f"\nPer-component-type accuracy ({best_method_name}):")
            log(f"{'Component':<30s} {'Total':>8s} {'Correct':>8s} {'Accuracy':>10s}")
            log("-" * 60)
            for cname in sorted(per_comp, key=lambda x: per_comp[x]["total"], reverse=True)[:15]:
                stats = per_comp[cname]
                acc = stats["correct"] / max(stats["total"], 1)
                log(f"{cname:<30s} {stats['total']:8d} {stats['correct']:8d} {acc:10.4f}")

    # Per-distance breakdown
    if best_method_name in results:
        per_dist = results[best_method_name].get("per_distance", {})
        if per_dist:
            log(f"\nPer-distance accuracy ({best_method_name}):")
            log(f"{'Distance':>10s} {'Total':>8s} {'Correct':>8s} {'Accuracy':>10s}")
            log("-" * 40)
            for db in sorted(per_dist.keys()):
                stats = per_dist[db]
                acc = stats["correct"] / max(stats["total"], 1)
                log(f"{db:>5d}-{db+20:<5d} {stats['total']:8d} {stats['correct']:8d} {acc:10.4f}")

    # Save results
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "phase1_results": {k: {kk: vv for kk, vv in v.items() if kk != "per_comp_type" and kk != "per_distance"}
                          for k, v in results.items()},
        "phase3_results": det_results,
        "best_method": sorted_methods[0][0] if sorted_methods else None,
        "best_endpoint_accuracy": sorted_methods[0][1]["endpoint_accuracy"] if sorted_methods else 0,
    }

    (out_dir / "mapping_v2_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    log(f"\nResults saved to {out_dir / 'mapping_v2_summary.json'}")
    log("EXPERIMENT COMPLETE")
    log("=" * 80)


if __name__ == "__main__":
    run_mapping_experiments()

"""Shared component-assignment logic for endpoint → component → pin routing.

This module is the SINGLE SOURCE OF TRUTH for determining which component
and pin a wire endpoint belongs to. Both the join pipeline (join_graph.py)
and visualizations (draw_3panel.py, etc.) MUST use this — never reimplement
the logic locally.

Usage:
    from wire_detection.core.component_assignment import assign_endpoint_to_pin

    comp_idx, pin_idx, dist = assign_endpoint_to_pin(
        endpoint=(153, 163),
        components=components,  # list of (cls_id, verts, bbox)
        pins=pins,              # list of ComponentPin objects
        tau_pin=60.0,
    )
"""
from __future__ import annotations

import math
from typing import NamedTuple


class AssignmentResult(NamedTuple):
    """Result of assigning an endpoint to a component and pin."""
    component_idx: int | None   # index into components list, or None if no match
    pin_idx: int | None         # 0 or 1, or None if no pin found
    dist: float                 # distance from endpoint to assigned component bbox


def bbox_distance(ep: tuple[float, float], bbox: tuple[float, float, float, float]) -> float:
    """Distance from point to bbox (0 if inside, else to nearest edge)."""
    x1, y1, x2, y2 = bbox
    cx = max(x1, min(ep[0], x2))
    cy = max(y1, min(ep[1], y2))
    return math.hypot(ep[0] - cx, ep[1] - cy)


def assignment_radius(bbox: tuple[float, float, float, float], tau_pin: float) -> float:
    """Generous assignment radius: max(tau_pin, 0.5 × component diagonal)."""
    x1, y1, x2, y2 = bbox
    diag = math.hypot(x2 - x1, y2 - y1)
    return max(tau_pin, 0.5 * diag)


def assign_endpoint_to_component(
    ep: tuple[float, float],
    components: list,
    tau_pin: float = 60.0,
) -> AssignmentResult:
    """Find the nearest component to an endpoint by bbox proximity.

    Uses the same logic as join_graph.py Step 1:
    - Distance from endpoint to bbox (0 if inside, else to nearest edge)
    - Assignment radius: max(tau_pin, 0.5 × component diagonal)
    - Returns the nearest component within radius, or None
    """
    best_ci = None
    best_dist = float("inf")
    for ci, comp in enumerate(components):
        bbox = comp[2]
        d = bbox_distance(ep, bbox)
        r = assignment_radius(bbox, tau_pin)
        if d <= r and d < best_dist:
            best_dist = d
            best_ci = ci
    return AssignmentResult(component_idx=best_ci, pin_idx=None, dist=best_dist)


def pick_pin_for_component(
    ep: tuple[float, float],
    comp_idx: int,
    comp_bbox: tuple[float, float, float, float],
    pins: list,
) -> int | None:
    """Determine which pin (0 or 1) an endpoint connects to, based on geometry.

    Uses the same logic as join_graph.py Step 2a:
    - Horizontal component (w > h): pin 0 on left, pin 1 on right
    - Vertical component (h > w): pin 0 on top, pin 1 on bottom
    - Square: pin 0 on left, pin 1 on right (horizontal bias)
    - Falls back to nearest pin if no pin with target index found
    """
    x1, y1, x2, y2 = comp_bbox
    comp_cx = (x1 + x2) / 2.0
    comp_cy = (y1 + y2) / 2.0
    comp_w = x2 - x1
    comp_h = y2 - y1

    # Determine target pin index based on geometry
    if comp_w > comp_h:
        target_pin_idx = 0 if ep[0] < comp_cx else 1
    elif comp_h > comp_w:
        target_pin_idx = 0 if ep[1] < comp_cy else 1
    else:
        target_pin_idx = 0 if ep[0] < comp_cx else 1

    # Find pins for this component
    comp_pins = [p for p in pins if p.component_idx == comp_idx]
    if not comp_pins:
        return None

    # Try to find pin with target index
    for p in comp_pins:
        if p.pin_idx == target_pin_idx:
            return target_pin_idx

    # Fallback: nearest pin
    nearest = min(comp_pins, key=lambda p: math.hypot(ep[0] - p.x, ep[1] - p.y))
    return nearest.pin_idx


def assign_endpoint_to_pin(
    ep: tuple[float, float],
    components: list,
    pins: list,
    tau_pin: float = 60.0,
) -> AssignmentResult:
    """Assign an endpoint to a component and pin. Combined two-step routing.

    This is the primary API — use this instead of reimplementing the logic.
    """
    # Step 1: assign to nearest component
    comp_result = assign_endpoint_to_component(ep, components, tau_pin)
    if comp_result.component_idx is None:
        return comp_result  # no component nearby

    # Step 2: pick pin based on geometry
    ci = comp_result.component_idx
    bbox = components[ci][2]
    pin_idx = pick_pin_for_component(ep, ci, bbox, pins)
    return AssignmentResult(component_idx=ci, pin_idx=pin_idx, dist=comp_result.dist)


def snap_endpoint(
    ep: tuple[float, float],
    components: list,
    pin_pos: dict[tuple[int, int], tuple[float, float]],
    tau_pin: float = 60.0,
) -> tuple[float, float]:
    """Snap an endpoint to its assigned pin position (for visualization).

    Uses the same assignment logic as the pipeline, then returns the pin
    coordinates. Falls back to the original endpoint if no assignment found.

    Args:
        ep: endpoint coordinates (x, y)
        components: list of (cls_id, verts, bbox) tuples
        pin_pos: dict mapping (comp_idx, pin_idx) -> (x, y)
        tau_pin: assignment tolerance (default 60.0)
    """
    comp_result = assign_endpoint_to_component(ep, components, tau_pin)
    if comp_result.component_idx is None:
        return ep

    ci = comp_result.component_idx
    bbox = components[ci][2]
    x1, y1, x2, y2 = bbox
    comp_cx = (x1 + x2) / 2.0
    comp_cy = (y1 + y2) / 2.0
    comp_w = x2 - x1
    comp_h = y2 - y1

    if comp_w > comp_h:
        pin_idx = 0 if ep[0] < comp_cx else 1
    elif comp_h > comp_w:
        pin_idx = 0 if ep[1] < comp_cy else 1
    else:
        pin_idx = 0 if ep[0] < comp_cx else 1

    return pin_pos.get((ci, pin_idx), ep)

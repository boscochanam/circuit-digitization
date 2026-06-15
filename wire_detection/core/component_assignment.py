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


def _point_to_segment_dist(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Minimum distance from point (px,py) to segment (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    cx = ax + t * dx
    cy = ay + t * dy
    return math.hypot(px - cx, py - cy)


def obb_distance(ep: tuple[float, float], vertices: list[tuple[float, float]]) -> float:
    """Minimum distance from a point to a rotated rectangle defined by 4 vertices.

    If the point is inside the polygon the distance is 0.
    Otherwise returns the minimum distance to any of the 4 edges.
    """
    px, py = ep
    n = len(vertices)
    # ---- winding-number point-in-polygon test (convex rect) ----
    inside = False
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        if ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / (y2 - y1) + x1):
            inside = not inside
    if inside:
        return 0.0
    # ---- min distance to edges ----
    best = float("inf")
    for i in range(n):
        ax, ay = vertices[i]
        bx, by = vertices[(i + 1) % n]
        d = _point_to_segment_dist(px, py, ax, ay, bx, by)
        if d < best:
            best = d
    return best


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
        vertices = comp[1]
        if vertices is not None and len(vertices) == 4:
            d = obb_distance(ep, vertices)
        else:
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
    """Determine which pin (0 or 1) an endpoint connects to.

    Uses nearest-pin routing: the endpoint joins whichever pin of this
    component is closest in Euclidean distance.  This replaces the old
    left/right/top/bottom geometric heuristic which broke when wires
    approached from a direction the heuristic didn't expect (e.g. a
    vertically-wired capacitor classified as "horizontal" because w > h,
    causing both endpoints to route to the same pin).
    """
    comp_pins = [p for p in pins if p.component_idx == comp_idx]
    if not comp_pins:
        return None

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

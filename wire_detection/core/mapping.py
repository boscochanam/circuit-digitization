"""Wire-to-component mapping methods.

Extracted from benchmark/mapping_phase3.py — contains the production-ready
mapping algorithms without experiment/evaluation code.
"""
from __future__ import annotations

import math


# ═══════════════════════════════════════════════
# COMPONENT TYPE CLASSIFICATION
# ═══════════════════════════════════════════════

TWO_TERMINAL_TYPES = {
    "resistor", "capacitor-unpolarized", "capacitor-polarized",
    "inductor", "diode", "diode-zener", "diode-light_emitting",
    "diode-thyrector", "fuse", "thermistor", "varistor", "crystal",
    "resistor-adjustable", "capacitor-adjustable", "inductor-ferrite",
    "magnetic", "relay", "switch",
}
MULTI_TERMINAL_TYPES = {
    "integrated_circuit", "integrated_circuit-ne555",
    "integrated_circuit-voltage_regulator", "transistor", "transistor-pnp",
    "operational_amplifier", "optocoupler", "triac", "diac",
}


# ═══════════════════════════════════════════════
# GEOMETRY HELPERS
# ═══════════════════════════════════════════════

def point_to_bbox_dist(px: float, py: float, bbox: tuple[int, int, int, int]) -> float:
    """Distance from point to nearest edge of a bounding box."""
    xmin, ymin, xmax, ymax = bbox
    cx = max(xmin, min(px, xmax))
    cy = max(ymin, min(py, ymax))
    return math.hypot(px - cx, py - cy)


def point_in_polygon(px: float, py: float, vertices: list[tuple[int, int]]) -> bool:
    """Check if point is inside polygon using ray casting."""
    n = len(vertices)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = vertices[i]
        xj, yj = vertices[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_to_polygon_dist(px: float, py: float, vertices: list[tuple[int, int]]) -> float:
    """Distance from point to nearest edge of a polygon."""
    min_d = float("inf")
    n = len(vertices)
    for i in range(n):
        ax, ay = vertices[i]
        bx, by = vertices[(i + 1) % n]
        ldx, ldy = bx - ax, by - ay
        len_sq = ldx * ldx + ldy * ldy
        if len_sq < 1e-10:
            d = math.hypot(px - ax, py - ay)
        else:
            t = max(0, min(1, ((px - ax) * ldx + (py - ay) * ldy) / len_sq))
            d = math.hypot(px - (ax + t * ldx), py - (ay + t * ldy))
        min_d = min(min_d, d)
    return min_d


# ═══════════════════════════════════════════════
# COMPONENT TYPE CHECKS
# ═══════════════════════════════════════════════

def is_two_terminal(cls_id: int, component_names: dict[int, str]) -> bool:
    """Check if a component class is a 2-terminal type."""
    name = component_names.get(cls_id, "")
    return name in TWO_TERMINAL_TYPES or "resistor" in name or "capacitor" in name or "diode" in name


def is_multi_terminal(cls_id: int, component_names: dict[int, str]) -> bool:
    """Check if a component class is a multi-terminal type."""
    name = component_names.get(cls_id, "")
    return name in MULTI_TERMINAL_TYPES or "integrated" in name or "transistor" in name


# ═══════════════════════════════════════════════
# CANDIDATE SELECTION
# ═══════════════════════════════════════════════

def get_candidates(
    ep: tuple[int, int],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
) -> list[tuple[int, float]]:
    """Get sorted (component_idx, distance) candidates for an endpoint."""
    cands = []
    for ci, comp in enumerate(components):
        d = point_to_bbox_dist(ep[0], ep[1], comp[2])
        cands.append((ci, d))
    cands.sort(key=lambda x: x[1])
    return cands


# ═══════════════════════════════════════════════
# MAPPING METHODS
# ═══════════════════════════════════════════════

def map_baseline(
    wire: tuple[tuple[int, int], tuple[int, int]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
) -> tuple[int, int]:
    """Baseline mapping: nearest bbox edge, no disambiguation."""
    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    return (c1[0][0] if c1 else -1, c2[0][0] if c2 else -1)


def map_selective_disambiguate(
    wire: tuple[tuple[int, int], tuple[int, int]],
    components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
    component_names: dict[int, str] | None = None,
    confidence_threshold: float = 15,
) -> tuple[int, int]:
    """Baseline by default, disambiguate only when same-component AND confident alternative exists.

    This is the best-performing mapping method from the Phase 3 experiments.
    """
    if component_names is None:
        component_names = {}

    ep1, ep2 = wire
    c1 = get_candidates(ep1, components)
    c2 = get_candidates(ep2, components)
    best1 = c1[0][0] if c1 else -1
    best2 = c2[0][0] if c2 else -1

    if best1 != best2 or best1 < 0:
        return best1, best2

    comp = components[best1]
    cls_id = comp[0]

    if is_multi_terminal(cls_id, component_names):
        return best1, best2

    inside1 = point_in_polygon(ep1[0], ep1[1], comp[1])
    inside2 = point_in_polygon(ep2[0], ep2[1], comp[1])
    if inside1 and inside2:
        return best1, best2

    if is_two_terminal(cls_id, component_names):
        d1, d2 = c1[0][1], c2[0][1]
        if d2 >= d1:
            for ci, d in c2[1:]:
                if ci != best1:
                    best2 = ci
                    break
        else:
            for ci, d in c1[1:]:
                if ci != best2:
                    best1 = ci
                    break
        return best1, best2

    gap1 = c1[1][1] - c1[0][1] if len(c1) > 1 else float("inf")
    gap2 = c2[1][1] - c2[0][1] if len(c2) > 1 else float("inf")

    if gap2 < confidence_threshold:
        for ci, d in c2[1:]:
            if ci != best1:
                best2 = ci
                break
    elif gap1 < confidence_threshold:
        for ci, d in c1[1:]:
            if ci != best2:
                best1 = ci
                break

    return best1, best2

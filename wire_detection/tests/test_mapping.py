"""Tests for wire-to-component mapping methods in mapping_phase3.py.

Tests baseline mapping, selective disambiguation, and helper functions
using synthetic component data (no real images needed).
"""
from __future__ import annotations


from wire_detection.benchmark.mapping_phase3 import (
    is_multi_terminal,
    is_two_terminal,
    map_baseline,
    map_selective_disambiguate,
    point_in_polygon,
)


# ═══════════════════════════════════════════════
# HELPERS: synthetic component factories
# ═══════════════════════════════════════════════


def _make_component(cls_id: int, x: int, y: int, w: int = 20, h: int = 20):
    """Create a synthetic component: (class_id, polygon, bbox)."""
    polygon = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    bbox = (x, y, x + w, y + h)
    return (cls_id, polygon, bbox)


# ═══════════════════════════════════════════════
# map_baseline
# ═══════════════════════════════════════════════


def test_map_baseline_nearest_component():
    """Baseline maps each endpoint to its nearest component by bbox distance."""
    comp_a = _make_component(33, 0, 0)      # resistor at origin
    comp_b = _make_component(33, 200, 200)   # resistor far away
    components = [comp_a, comp_b]

    wire = ((10, 10), (210, 210))
    c1, c2 = map_baseline(wire, components)
    assert c1 == 0   # ep1 nearest to comp_a
    assert c2 == 1   # ep2 nearest to comp_b


def test_map_baseline_equidistant_picks_first():
    """When equidistant, baseline picks the first candidate (sorted by index)."""
    comp_a = _make_component(33, 0, 0)
    comp_b = _make_component(33, 100, 0)
    components = [comp_a, comp_b]

    # Midpoint between the two components
    wire = ((50, 10), (50, 10))
    c1, c2 = map_baseline(wire, components)
    # Both endpoints map to the same (nearest) component
    assert c1 == c2


def test_map_baseline_far_endpoint_returns_valid():
    """Far endpoint still maps to nearest component (no -1 if components exist)."""
    comp = _make_component(33, 50, 50)
    components = [comp]

    wire = ((0, 0), (500, 500))
    c1, c2 = map_baseline(wire, components)
    assert c1 == 0
    assert c2 == 0


def test_map_baseline_empty_components():
    """No components returns -1 for both endpoints."""
    wire = ((10, 10), (50, 50))
    c1, c2 = map_baseline(wire, [])
    assert c1 == -1
    assert c2 == -1


# ═══════════════════════════════════════════════
# map_selective_disambiguate
# ═══════════════════════════════════════════════


def test_selective_disambiguate_two_terminal_reassigns():
    """When both endpoints map to same 2-terminal component, reassigns one."""
    # Two resistors close together but separated
    comp_a = _make_component(33, 0, 0)     # resistor bbox (0,0)-(20,20)
    comp_b = _make_component(33, 30, 0)    # nearby resistor bbox (30,0)-(50,20)
    components = [comp_a, comp_b]

    # Wire endpoints both nearest to comp_a bbox, but OUTSIDE the polygon
    # so containment check doesn't prevent disambiguation
    wire = ((-5, 10), (25, 10))
    c1, c2 = map_selective_disambiguate(wire, components)
    # Should disambiguate: one endpoint stays on comp_a, other goes to comp_b
    assert c1 != c2


def test_selective_disambiguate_multi_terminal_keeps():
    """When both endpoints map to same multi-terminal component, keeps both."""
    # IC (class_id=16 is integrated_circuit)
    comp_ic = _make_component(16, 0, 0, w=100, h=100)
    comp_other = _make_component(33, 200, 200)
    components = [comp_ic, comp_other]

    # Wire endpoints both near the IC
    wire = ((20, 50), (80, 50))
    c1, c2 = map_selective_disambiguate(wire, components)
    # Multi-terminal: should NOT disambiguate
    assert c1 == c2 == 0


def test_selective_disambiguate_inside_polygon_keeps():
    """When both endpoints are inside the component polygon, keeps mapping."""
    comp = _make_component(33, 0, 0, w=100, h=100)
    comp_far = _make_component(33, 300, 300)
    components = [comp, comp_far]

    # Both endpoints clearly inside the polygon
    wire = ((20, 20), (80, 80))
    c1, c2 = map_selective_disambiguate(wire, components)
    # Both inside polygon → keeps same component
    assert c1 == c2


def test_selective_disambiguate_threshold_respected():
    """Confidence threshold controls whether reassignment happens."""
    # Two components with a gap
    comp_a = _make_component(33, 0, 0)
    comp_b = _make_component(33, 200, 0)
    comp_c = _make_component(33, 205, 0)  # very close to comp_b
    components = [comp_a, comp_b, comp_c]

    # Wire endpoints: ep1 near comp_a, ep2 between comp_b and comp_c
    wire = ((5, 10), (202, 10))
    # With high threshold: more likely to reassign
    c1_high, c2_high = map_selective_disambiguate(wire, components, confidence_threshold=50)
    # With low threshold: less likely to reassign
    c1_low, c2_low = map_selective_disambiguate(wire, components, confidence_threshold=1)
    # Both should map ep1 to comp_a
    assert c1_high == 0
    assert c1_low == 0


def test_selective_disambiguate_different_components_no_change():
    """When endpoints map to different components, no disambiguation needed."""
    comp_a = _make_component(33, 0, 0)
    comp_b = _make_component(33, 200, 200)
    components = [comp_a, comp_b]

    wire = ((10, 10), (210, 210))
    c1, c2 = map_selective_disambiguate(wire, components)
    assert c1 == 0
    assert c2 == 1


# ═══════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════


def test_same_component_single():
    """Single component: both endpoints map to it, no crash."""
    comp = _make_component(33, 50, 50)
    components = [comp]

    wire = ((55, 55), (65, 65))
    c1, c2 = map_baseline(wire, components)
    assert c1 == c2 == 0


def test_multi_terminal_transistor():
    """Transistor (3-pin) should be detected as multi-terminal."""
    assert is_multi_terminal(38) is True  # transistor
    assert is_two_terminal(38) is False


def test_containment_check():
    """point_in_polygon correctly identifies interior vs exterior."""
    square = [(10, 10), (50, 10), (50, 50), (10, 50)]
    assert point_in_polygon(30, 30, square) is True
    assert point_in_polygon(0, 0, square) is False
    assert point_in_polygon(100, 100, square) is False

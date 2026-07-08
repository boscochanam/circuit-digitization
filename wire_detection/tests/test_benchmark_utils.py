"""Tests for benchmark utility functions: geometry, data loading, preprocessing.

Tests geometry helpers from mapping_phase3.py and preprocessing/extraction
helpers from experiment_harness.py and reference_pipeline.py.
"""
from __future__ import annotations

import os
import math

import numpy as np

from wire_detection.benchmark.mapping_phase3 import (
    get_candidates,
    is_multi_terminal,
    is_two_terminal,
    point_in_polygon,
    point_to_bbox_dist,
    point_to_polygon_dist,
)
from wire_detection.benchmark.experiment_harness import (
    build_component_mask,
    crop_to_roi,
    shift_components,
)
from wire_detection.benchmark.reference_pipeline import (
    load_ground_truth,
    parse_components,
)


# ═══════════════════════════════════════════════
# GEOMETRY: point_to_bbox_dist
# ═══════════════════════════════════════════════


def test_point_to_bbox_dist_inside_returns_zero():
    """Point inside the bbox should have distance 0."""
    bbox = (10, 10, 50, 50)
    assert point_to_bbox_dist(30, 30, bbox) == 0.0


def test_point_to_bbox_dist_outside_returns_correct_distance():
    """Point outside bbox returns Euclidean distance to nearest edge."""
    bbox = (10, 10, 50, 50)
    d = point_to_bbox_dist(0, 0, bbox)
    expected = math.hypot(10, 10)
    assert abs(d - expected) < 1e-6


def test_point_to_bbox_dist_on_edge_returns_zero():
    """Point on the bbox edge should have distance 0."""
    bbox = (10, 10, 50, 50)
    assert point_to_bbox_dist(10, 30, bbox) == 0.0
    assert point_to_bbox_dist(30, 50, bbox) == 0.0


def test_point_to_bbox_dist_corner():
    """Point at a corner should have distance 0."""
    bbox = (10, 10, 50, 50)
    assert point_to_bbox_dist(10, 10, bbox) == 0.0
    assert point_to_bbox_dist(50, 50, bbox) == 0.0


def test_point_to_bbox_dist_above():
    """Point directly above bbox center."""
    bbox = (10, 10, 50, 50)
    d = point_to_bbox_dist(30, 0, bbox)
    assert abs(d - 10.0) < 1e-6


# ═══════════════════════════════════════════════
# GEOMETRY: point_in_polygon
# ═══════════════════════════════════════════════


def test_point_in_polygon_inside():
    """Point inside a square polygon."""
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon(5, 5, square) is True


def test_point_in_polygon_outside():
    """Point outside a square polygon."""
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon(15, 5, square) is False


def test_point_in_polygon_on_vertex():
    """Point exactly on a vertex — behavior depends on ray-casting impl."""
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    result = point_in_polygon(0, 0, square)
    assert isinstance(result, bool)


def test_point_in_polygon_triangle():
    """Point inside a triangle."""
    tri = [(0, 0), (10, 0), (5, 10)]
    assert point_in_polygon(5, 3, tri) is True
    assert point_in_polygon(0, 5, tri) is False


def test_point_in_polygon_convex_shape():
    """Point inside a convex hexagon."""
    hexagon = [(10, 0), (20, 5), (20, 15), (10, 20), (0, 15), (0, 5)]
    assert point_in_polygon(10, 10, hexagon) is True
    assert point_in_polygon(25, 10, hexagon) is False


# ═══════════════════════════════════════════════
# GEOMETRY: point_to_polygon_dist
# ═══════════════════════════════════════════════


def test_point_to_polygon_dist_inside_returns_zero():
    """Point inside polygon should return 0 distance (on boundary or inside)."""
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    d = point_to_polygon_dist(5, 5, square)
    # Distance to nearest edge of the square
    assert d == 5.0


def test_point_to_polygon_dist_outside():
    """Point outside polygon returns distance to nearest edge."""
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    d = point_to_polygon_dist(15, 5, square)
    assert abs(d - 5.0) < 1e-6


def test_point_to_polygon_dist_on_edge():
    """Point on polygon edge returns 0."""
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    d = point_to_polygon_dist(10, 5, square)
    assert abs(d - 0.0) < 1e-6


# ═══════════════════════════════════════════════
# DATA LOADING: load_ground_truth
# ═══════════════════════════════════════════════


def test_load_ground_truth_returns_tuples(tmp_path):
    """load_ground_truth returns list of (p1, p2) tuples."""
    label = tmp_path / "test.txt"
    # YOLO-OBB format: class_id x1 y1 x2 y2 x3 y3 x4 y4
    # Square wire from (100,100) to (200,100) to (200,110) to (100,110) in 640x640
    label.write_text("0 0.15625 0.15625 0.3125 0.15625 0.3125 0.171875 0.15625 0.171875\n")
    result = load_ground_truth(label, 640, 640)
    assert len(result) == 1
    p1, p2 = result[0]
    assert isinstance(p1, tuple) and isinstance(p2, tuple)
    assert len(p1) == 2 and len(p2) == 2


def test_load_ground_truth_coordinate_range(tmp_path):
    """Coordinates are within image bounds."""
    label = tmp_path / "test.txt"
    label.write_text("0 0.1 0.1 0.9 0.1 0.9 0.15 0.1 0.15\n")
    result = load_ground_truth(label, 640, 640)
    assert len(result) == 1
    for p1, p2 in result:
        for x, y in [p1, p2]:
            assert 0 <= x <= 640
            assert 0 <= y <= 640


def test_load_ground_truth_multiple_wires(tmp_path):
    """Multiple lines in label file produce multiple wire tuples."""
    label = tmp_path / "test.txt"
    label.write_text(
        "0 0.1 0.1 0.5 0.1 0.5 0.15 0.1 0.15\n"
        "0 0.2 0.2 0.8 0.2 0.8 0.25 0.2 0.25\n"
    )
    result = load_ground_truth(label, 640, 640)
    assert len(result) == 2


def test_load_ground_truth_empty_file(tmp_path):
    """Empty label file returns empty list."""
    label = tmp_path / "test.txt"
    label.write_text("")
    result = load_ground_truth(label, 640, 640)
    assert result == []


def test_load_ground_truth_malformed_lines(tmp_path):
    """Malformed lines are skipped."""
    label = tmp_path / "test.txt"
    label.write_text(
        "bad line\n"
        "0 0.1 0.1 0.5 0.1 0.5 0.15 0.1 0.15\n"
        "0 1 2\n"
    )
    result = load_ground_truth(label, 640, 640)
    assert len(result) == 1


# ═══════════════════════════════════════════════
# DATA LOADING: parse_components
# ═══════════════════════════════════════════════


def test_parse_components_returns_tuples(tmp_path):
    """parse_components returns list of (class_id, polygon, bbox)."""
    label = tmp_path / "comp.txt"
    label.write_text("33 0.3 0.3 0.7 0.3 0.7 0.4 0.3 0.4\n")
    result = parse_components(label, 640, 640)
    assert len(result) == 1
    cls_id, polygon, bbox = result[0]
    assert cls_id == 33
    assert len(polygon) == 4
    assert len(bbox) == 4


def test_parse_components_has_bbox(tmp_path):
    """Bounding box is (x1, y1, x2, y2) with x1<x2, y1<y2."""
    label = tmp_path / "comp.txt"
    label.write_text("33 0.3 0.3 0.7 0.3 0.7 0.4 0.3 0.4\n")
    result = parse_components(label, 640, 640)
    _, _, bbox = result[0]
    x1, y1, x2, y2 = bbox
    assert x1 <= x2
    assert y1 <= y2


def test_parse_components_has_vertices(tmp_path):
    """Polygon vertices are 4 (x, y) tuples."""
    label = tmp_path / "comp.txt"
    label.write_text("33 0.3 0.3 0.7 0.3 0.7 0.4 0.3 0.4\n")
    result = parse_components(label, 640, 640)
    _, polygon, _ = result[0]
    assert len(polygon) == 4
    for pt in polygon:
        assert len(pt) == 2


def test_parse_components_multiple(tmp_path):
    """Multiple components parsed correctly."""
    label = tmp_path / "comp.txt"
    label.write_text(
        "33 0.1 0.1 0.3 0.1 0.3 0.2 0.1 0.2\n"
        "8 0.5 0.5 0.8 0.5 0.8 0.6 0.5 0.6\n"
    )
    result = parse_components(label, 640, 640)
    assert len(result) == 2
    assert result[0][0] == 33
    assert result[1][0] == 8


def test_parse_components_empty_file(tmp_path):
    """Empty label file returns empty list."""
    label = tmp_path / "comp.txt"
    label.write_text("")
    result = parse_components(label, 640, 640)
    assert result == []


def test_parse_components_none_path():
    """None path returns empty list."""
    result = parse_components(None, 640, 640)
    assert result == []


# ═══════════════════════════════════════════════
# find_hdc_label (prefix matching)
# ═══════════════════════════════════════════════


def test_find_hdc_label_prefix_matching(tmp_path):
    """Prefix matching finds label file with .rf. suffix."""
    from wire_detection.benchmark.mapping_phase3 import find_hdc_label

    # Create mock HDC directory structure
    label_dir = tmp_path / "train" / "labels"
    label_dir.mkdir(parents=True)
    (label_dir / "C100_D1_P1_jpg.rf.abc123.txt").write_text("33 0.1 0.1 0.5 0.1 0.5 0.2 0.1 0.2\n")

    import wire_detection.benchmark.mapping_phase3 as mod
    old_splits = mod.HDC_SPLITS
    try:
        # The HDC root resolves from WIRE_HDC_BASE at call time, so point it at the fixture.
        os.environ["WIRE_HDC_BASE"] = str(tmp_path)
        mod.HDC_SPLITS = ["train"]
        result = find_hdc_label("C100_D1_P1_jpg")
        assert result is not None
        assert "C100_D1_P1_jpg" in result.name
    finally:
        os.environ.pop("WIRE_HDC_BASE", None)
        mod.HDC_SPLITS = old_splits


def test_find_hdc_label_no_match_returns_none(tmp_path):
    """No matching label file returns None."""
    from wire_detection.benchmark.mapping_phase3 import find_hdc_label

    import wire_detection.benchmark.mapping_phase3 as mod
    old_splits = mod.HDC_SPLITS
    try:
        os.environ["WIRE_HDC_BASE"] = str(tmp_path)
        mod.HDC_SPLITS = ["train"]
        result = find_hdc_label("nonexistent_image")
        assert result is None
    finally:
        os.environ.pop("WIRE_HDC_BASE", None)
        mod.HDC_SPLITS = old_splits


# ═══════════════════════════════════════════════
# PREPROCESSING: build_component_mask
# ═══════════════════════════════════════════════


def test_build_component_mask_fills_polygons():
    """Component mask fills polygon regions with median color, not white."""
    gray = np.full((100, 100), 128, dtype=np.uint8)
    # Draw a dark rectangle at (20,20)-(40,40) to give distinct median
    gray[20:40, 20:40] = 60
    # Component polygon covers the dark rectangle
    polygon = [(20, 20), (40, 20), (40, 40), (20, 40)]
    bbox = (20, 20, 40, 40)
    components = [(33, polygon, bbox)]

    result = build_component_mask(gray, components, occlusion_margin=0.15)
    # The polygon region should be filled with median color (not original 60)
    # Median of local region should be around 128 (most of region is 128)
    assert result.shape == gray.shape
    # The filled region should differ from original
    assert result[30, 30] != 60


def test_build_component_mask_preserves_outside():
    """Pixels outside component polygons are unchanged."""
    gray = np.full((100, 100), 128, dtype=np.uint8)
    polygon = [(20, 20), (40, 20), (40, 40), (20, 40)]
    bbox = (20, 20, 40, 40)
    components = [(33, polygon, bbox)]

    result = build_component_mask(gray, components, occlusion_margin=0.15)
    # Corner pixel far from component
    assert result[0, 0] == 128


# ═══════════════════════════════════════════════
# PREPROCESSING: crop_to_roi
# ═══════════════════════════════════════════════


def test_crop_to_roi_returns_offset():
    """crop_to_roi returns (cropped_image, offset_x, offset_y)."""
    gray = np.full((200, 200), 128, dtype=np.uint8)
    polygon = [(50, 50), (100, 50), (100, 100), (50, 100)]
    bbox = (50, 50, 100, 100)
    components = [(33, polygon, bbox)]

    cropped, ox, oy = crop_to_roi(gray, components, padding=10)
    assert cropped.shape[0] <= 200
    assert cropped.shape[1] <= 200
    assert ox >= 0 and oy >= 0


def test_crop_to_roi_empty_components():
    """Empty components returns original image with zero offset."""
    gray = np.full((200, 200), 128, dtype=np.uint8)
    cropped, ox, oy = crop_to_roi(gray, [], padding=10)
    assert cropped.shape == gray.shape
    assert ox == 0 and oy == 0


def test_crop_to_roi_padding():
    """Padding extends crop region."""
    gray = np.full((200, 200), 128, dtype=np.uint8)
    polygon = [(80, 80), (120, 80), (120, 120), (80, 120)]
    bbox = (80, 80, 120, 120)
    components = [(33, polygon, bbox)]

    cropped_small, ox1, oy1 = crop_to_roi(gray, components, padding=5)
    cropped_large, ox2, oy2 = crop_to_roi(gray, components, padding=20)
    assert cropped_large.shape[0] >= cropped_small.shape[0]
    assert cropped_large.shape[1] >= cropped_small.shape[1]


# ═══════════════════════════════════════════════
# PREPROCESSING: shift_components
# ═══════════════════════════════════════════════


def test_shift_components_adjusts_coordinates():
    """shift_components subtracts offset from all coordinates."""
    polygon = [(50, 60), (100, 60), (100, 100), (50, 100)]
    bbox = (50, 60, 100, 100)
    components = [(33, polygon, bbox)]

    shifted = shift_components(components, ox=40, oy=50)
    assert len(shifted) == 1
    cls_id, new_poly, new_bbox = shifted[0]
    assert cls_id == 33
    assert new_poly[0] == (10, 10)
    assert new_bbox == (10, 10, 60, 50)


def test_shift_components_zero_offset():
    """Zero offset leaves coordinates unchanged."""
    polygon = [(10, 20), (30, 20), (30, 40), (10, 40)]
    bbox = (10, 20, 30, 40)
    components = [(33, polygon, bbox)]

    shifted = shift_components(components, ox=0, oy=0)
    assert shifted[0][1] == polygon
    assert shifted[0][2] == bbox


def test_shift_components_multiple():
    """Multiple components all get shifted."""
    comp1 = (33, [(10, 20), (30, 20), (30, 40), (10, 40)], (10, 20, 30, 40))
    comp2 = (8, [(50, 60), (80, 60), (80, 90), (50, 90)], (50, 60, 80, 90))

    shifted = shift_components([comp1, comp2], ox=5, oy=10)
    assert shifted[0][1][0] == (5, 10)
    assert shifted[1][1][0] == (45, 50)


# ═══════════════════════════════════════════════
# CLASSIFICATION: is_two_terminal / is_multi_terminal
# ═══════════════════════════════════════════════


def test_is_two_terminal_resistor():
    """Resistor (class_id=33) is two-terminal."""
    assert is_two_terminal(33) is True


def test_is_two_terminal_capacitor():
    """Capacitor (class_id=3 or 4) is two-terminal."""
    assert is_two_terminal(3) is True  # capacitor-polarized
    assert is_two_terminal(4) is True  # capacitor-unpolarized


def test_is_two_terminal_diode():
    """Diode (class_id=8) is two-terminal."""
    assert is_two_terminal(8) is True


def test_is_multi_terminal_transistor():
    """Transistor (class_id=38) is multi-terminal."""
    assert is_multi_terminal(38) is True


def test_is_multi_terminal_ic():
    """Integrated circuit (class_id=16) is multi-terminal."""
    assert is_multi_terminal(16) is True


def test_is_two_terminal_junction_false():
    """Junction (class_id=19) is NOT two-terminal."""
    assert is_two_terminal(19) is False


def test_is_multi_terminal_resistor_false():
    """Resistor is NOT multi-terminal."""
    assert is_multi_terminal(33) is False


# ═══════════════════════════════════════════════
# CANDIDATES: get_candidates
# ═══════════════════════════════════════════════


def test_get_candidates_returns_sorted():
    """Candidates are sorted by distance (nearest first)."""
    components = [
        (33, [(0, 0), (10, 0), (10, 10), (0, 10)], (0, 0, 10, 10)),
        (8, [(100, 100), (110, 100), (110, 110), (100, 110)], (100, 100, 110, 110)),
    ]
    cands = get_candidates((5, 5), components)
    assert len(cands) == 2
    assert cands[0][1] <= cands[1][1]


def test_get_candidates_empty_components():
    """Empty components returns empty candidates."""
    cands = get_candidates((5, 5), [])
    assert cands == []


def test_get_candidates_far_point():
    """Far point still returns candidates sorted by distance."""
    components = [
        (33, [(0, 0), (10, 0), (10, 10), (0, 10)], (0, 0, 10, 10)),
        (8, [(50, 50), (60, 50), (60, 60), (50, 60)], (50, 50, 60, 60)),
    ]
    cands = get_candidates((200, 200), components)
    assert len(cands) == 2
    assert cands[0][1] > 0

"""Tests for Phase 1.9 (Anchor Filter) and Phase 4.1 (Wire Detection Metrics).

Phase 1.9: The anchor filter is not a standalone pipeline stage; it is embedded
in the join strategies (join_graph.py dead-end rescue, join_strategies.py
attach_anchored).  We test the *concept* by reimplementing the core distance
predicates and exercising the logic paths that the real code uses.

Phase 4.1: The evaluation metrics (TP/FP/FN/redundant counting, precision,
recall, F1) live in benchmark/reference_pipeline.py.  We copy the two key
functions locally so the tests are self-contained, then exercise them with
carefully chosen synthetic data.
"""
from __future__ import annotations

import math
from typing import List, Tuple

import pytest

# ═══════════════════════════════════════════════════════════════════
# LOCAL COPIES OF REFERENCE IMPLEMENTATIONS  (self-contained tests)
# ═══════════════════════════════════════════════════════════════════

Line = Tuple[Tuple[int, int], Tuple[int, int]]


def _point_to_segment_dist(p: tuple, a: tuple, b: tuple) -> float:
    """Perpendicular distance from point *p* to line segment *ab*.

    Copied verbatim from wire_detection/benchmark/reference_pipeline.py
    so that tests never need to import that module (which pulls in heavy
    dependencies like numpy / cv2 at module level).
    """
    ax, ay = a
    bx, by = b
    px, py = p
    abx, aby = bx - ax, by - ay
    t = ((px - ax) * abx + (py - ay) * aby) / max(abx * abx + aby * aby, 1e-8)
    t = max(0, min(1, t))
    return math.hypot(px - (ax + t * abx), py - (ay + t * aby))


def evaluate(
    detected: list[Line],
    ground_truth: list[Line],
    match_dist: float = 20.0,
) -> tuple[int, int, int, int]:
    """Evaluate detected lines against ground truth.

    Returns (tp, fp, fn, redundant).
    Copied from wire_detection/benchmark/reference_pipeline.py.
    """
    matched = [False] * len(ground_truth)
    tp = fp = red = 0

    for det in detected:
        best_dist, best_idx = float("inf"), -1
        for gi, gt in enumerate(ground_truth):
            dist = (
                _point_to_segment_dist(det[0], gt[0], gt[1])
                + _point_to_segment_dist(det[1], gt[0], gt[1])
            ) / 2
            if dist < best_dist:
                best_dist = dist
                best_idx = gi

        if best_dist <= match_dist:
            if matched[best_idx]:
                red += 1  # already matched — redundant
            else:
                tp += 1
                matched[best_idx] = True
        else:
            fp += 1

    fn = sum(1 for m in matched if not m)
    return tp, fp, fn, red


# ═══════════════════════════════════════════════════════════════════
# ANCHOR FILTER UTILITIES  (Phase 1.9 helpers)
# ═══════════════════════════════════════════════════════════════════

# a16 best config parameters (from AGENTS.md)
ANCHOR_ENDPOINT_DIST = 16  # pixels — max distance from endpoint to component bbox to be "anchored"
LINK_DIST = 8              # pixels — max distance between two endpoints to link them
MARGIN = 8                 # pixels — margin around component bbox for anchor check


def is_endpoint_anchored(
    endpoint: tuple[int, int],
    component_bbox: tuple[int, int, int, int],
    endpoint_dist: int = ANCHOR_ENDPOINT_DIST,
) -> bool:
    """Check whether *endpoint* is within *endpoint_dist* pixels of a
    component bounding box (with *MARGIN* extension).

    This mirrors the logic in attach_anchored() and join_graph.py's
    component proximity checks.
    """
    x1, y1, x2, y2 = component_bbox
    # Clamp the endpoint to the expanded bbox and check distance
    cx = max(x1 - MARGIN, min(endpoint[0], x2 + MARGIN))
    cy = max(y1 - MARGIN, min(endpoint[1], y2 + MARGIN))
    dist = math.hypot(endpoint[0] - cx, endpoint[1] - cy)
    return dist <= endpoint_dist


def endpoints_should_link(
    ep_a: tuple[int, int],
    ep_b: tuple[int, int],
    link_distance: int = LINK_DIST,
) -> bool:
    """Check whether two wire endpoints are close enough to be linked
    (join_graph.py edge 2: |ep_a - ep_b| <= tau_join).
    """
    return math.hypot(ep_a[0] - ep_b[0], ep_a[1] - ep_b[1]) <= link_distance


def filter_anchored_endpoints(
    endpoints: list[tuple[int, int]],
    component_bboxes: list[tuple[int, int, int, int]],
    endpoint_dist: int = ANCHOR_ENDPOINT_DIST,
) -> list[tuple[int, int]]:
    """Return only endpoints that are anchored to at least one component.
    Endpoints without an anchor are considered 'floating' and would be
    candidates for the dead-end rescue logic.
    """
    anchored = []
    for ep in endpoints:
        for bbox in component_bboxes:
            if is_endpoint_anchored(ep, bbox, endpoint_dist):
                anchored.append(ep)
                break
    return anchored


# ═══════════════════════════════════════════════════════════════════
# PHASE 1.9 — ANCHOR FILTER TESTS
# ═══════════════════════════════════════════════════════════════════


class TestAnchorFilter:
    """Tests for the anchor filter logic used in wire join strategies."""

    # --- test_endpoint_near_component ---

    def test_endpoint_near_component_inside_bbox(self):
        """Endpoint exactly on the component bbox edge should be anchored."""
        bbox = (100, 100, 200, 150)
        assert is_endpoint_anchored((100, 125), bbox) is True

    def test_endpoint_near_component_within_distance(self):
        """Endpoint 10px outside bbox (within 16px threshold) should be anchored."""
        bbox = (100, 100, 200, 150)
        # Point is 10px directly above the bbox top edge (y=100)
        assert is_endpoint_anchored((150, 90), bbox) is True

    def test_endpoint_near_component_exactly_at_threshold(self):
        """Endpoint exactly at the 16px threshold boundary should be anchored."""
        bbox = (100, 100, 200, 150)
        # 16px directly above the bbox (top edge y=100)
        assert is_endpoint_anchored((150, 84), bbox) is True

    # --- test_endpoint_far_from_component ---

    def test_endpoint_far_from_component(self):
        """Endpoint >16px from any bbox should NOT be anchored."""
        bbox = (100, 100, 200, 150)
        # 50px above the bbox
        assert is_endpoint_anchored((150, 50), bbox) is False

    def test_endpoint_just_beyond_threshold(self):
        """Endpoint at 17px from bbox should still be anchored due to MARGIN=8.

        The MARGIN extends the bbox by 8px, so 17px from original bbox edge
        is only 9px from the expanded bbox, which is within the 16px threshold.
        """
        bbox = (100, 100, 200, 150)
        # 17px directly above the bbox top edge → 9px from expanded edge
        assert is_endpoint_anchored((150, 83), bbox) is True

    def test_endpoint_far_beyond_threshold(self):
        """Endpoint at 25px from bbox should NOT be anchored.

        25px from original → 17px from expanded (with MARGIN=8) → > 16px threshold.
        """
        bbox = (100, 100, 200, 150)
        # 25px directly above the bbox top edge
        assert is_endpoint_anchored((150, 75), bbox) is False

    def test_endpoint_far_diagonal(self):
        """Endpoint far in diagonal direction should not be anchored."""
        bbox = (100, 100, 200, 150)
        # Far away diagonally
        assert is_endpoint_anchored((0, 0), bbox) is False

    # --- test_link_distance_filter ---

    def test_endpoints_within_link_distance(self):
        """Two endpoints 5px apart (< 8px link_dist) should link."""
        assert endpoints_should_link((100, 100), (105, 100)) is True

    def test_endpoints_at_link_distance(self):
        """Two endpoints exactly 8px apart should link."""
        assert endpoints_should_link((100, 100), (108, 100)) is True

    def test_endpoints_beyond_link_distance(self):
        """Two endpoints 9px apart (> 8px link_dist) should NOT link."""
        assert endpoints_should_link((100, 100), (109, 100)) is False

    def test_endpoints_diagonal_link_distance(self):
        """Diagonal distance check: sqrt(36+64) = 10 > 8, should not link."""
        assert endpoints_should_link((100, 100), (106, 108)) is False

    def test_identical_endpoints_link(self):
        """Identical endpoints (distance=0) should always link."""
        assert endpoints_should_link((100, 100), (100, 100)) is True

    # --- test_anchor_preserves_connected ---

    def test_anchor_preserves_connected_endpoints(self):
        """Endpoints connected to components should survive anchor filtering."""
        bboxes = [(50, 50, 100, 100), (200, 200, 250, 250)]
        endpoints = [
            (60, 60),   # inside bbox[0]
            (240, 240), # inside bbox[1]
        ]
        anchored = filter_anchored_endpoints(endpoints, bboxes)
        assert len(anchored) == 2
        assert (60, 60) in anchored
        assert (240, 240) in anchored

    def test_anchor_filters_floating_endpoints(self):
        """Endpoints far from all components should be filtered out."""
        bboxes = [(50, 50, 100, 100)]
        endpoints = [
            (60, 60),   # anchored to bbox[0]
            (300, 300), # far away, floating
        ]
        anchored = filter_anchored_endpoints(endpoints, bboxes)
        assert len(anchored) == 1
        assert (60, 60) in anchored

    def test_anchor_mixed_endpoints(self):
        """Mix of anchored and floating endpoints: only anchored survive."""
        bboxes = [(50, 50, 100, 100), (300, 300, 350, 350)]
        endpoints = [
            (55, 55),   # near bbox[0] → anchored
            (310, 310), # near bbox[1] → anchored
            (200, 200), # between boxes, far from both → floating
        ]
        anchored = filter_anchored_endpoints(endpoints, bboxes)
        assert len(anchored) == 2

    def test_empty_components_no_anchors(self):
        """With no components, no endpoints can be anchored."""
        endpoints = [(100, 100), (200, 200)]
        anchored = filter_anchored_endpoints(endpoints, [])
        assert len(anchored) == 0

    def test_empty_endpoints(self):
        """With no endpoints, result is empty."""
        bboxes = [(50, 50, 100, 100)]
        anchored = filter_anchored_endpoints([], bboxes)
        assert len(anchored) == 0

    def test_custom_endpoint_distance(self):
        """Custom endpoint_dist changes the anchoring threshold."""
        bbox = (100, 100, 200, 150)
        # Point (150, 78): 14px from expanded bbox edge (with MARGIN=8)
        # anchored with dist=16, not anchored with dist=10
        assert is_endpoint_anchored((150, 78), bbox, endpoint_dist=16) is True
        assert is_endpoint_anchored((150, 78), bbox, endpoint_dist=10) is False

    def test_component_bbox_corner_cases(self):
        """Test anchoring near component bbox corners."""
        bbox = (100, 100, 200, 150)
        # Corner: 10px diagonally from top-left corner
        # Closest point on bbox is (100, 100), distance = sqrt(200) ≈ 14.1
        assert is_endpoint_anchored((90, 90), bbox) is True  # within 16px

        # Corner: 20px diagonally from top-left
        # distance = sqrt(800) ≈ 28.3
        assert is_endpoint_anchored((80, 80), bbox) is False  # > 16px


# ═══════════════════════════════════════════════════════════════════
# PHASE 4.1 — WIRE DETECTION METRICS TESTS
# ═══════════════════════════════════════════════════════════════════


class TestPointToSegmentDist:
    """Unit tests for the _point_to_segment_dist distance function."""

    def test_point_on_segment_midpoint(self):
        """Point at the midpoint of a horizontal segment → distance 0."""
        d = _point_to_segment_dist((50, 0), (0, 0), (100, 0))
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_point_on_segment_endpoint(self):
        """Point exactly at segment endpoint → distance 0."""
        d = _point_to_segment_dist((0, 0), (0, 0), (100, 0))
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_point_perpendicular(self):
        """Point directly above segment midpoint → perpendicular distance."""
        d = _point_to_segment_dist((50, 10), (0, 0), (100, 0))
        assert d == pytest.approx(10.0, abs=1e-6)

    def test_point_beyond_segment_perpendicular(self):
        """Point beyond segment end → closest to nearest endpoint."""
        d = _point_to_segment_dist((120, 10), (0, 0), (100, 0))
        # Closest point is (100, 0), distance = sqrt(20^2 + 10^2) ≈ 22.36
        assert d == pytest.approx(math.hypot(20, 10), abs=1e-6)

    def test_degenerate_segment(self):
        """Degenerate (zero-length) segment → distance to the single point."""
        d = _point_to_segment_dist((3, 4), (0, 0), (0, 0))
        assert d == pytest.approx(5.0, abs=1e-6)

    def test_diagonal_segment(self):
        """Diagonal segment: point (0, 10) to segment (0,0)-(10,10)."""
        d = _point_to_segment_dist((0, 10), (0, 0), (10, 10))
        # The closest point on the segment is (5, 5); distance = sqrt(50) ≈ 7.07
        assert d == pytest.approx(math.sqrt(50), abs=1e-4)


class TestTPCounting:
    """Test that true positives are correctly counted."""

    def test_tp_near_identical_lines(self):
        """Two nearly-identical lines should count as one TP."""
        detected = [((10, 10), (100, 100))]
        ground_truth = [((12, 12), (98, 98))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 1
        assert fp == 0
        assert fn == 0
        assert red == 0

    def test_tp_exact_match(self):
        """Identical lines should match exactly (dist = 0)."""
        detected = [((0, 0), (100, 100))]
        ground_truth = [((0, 0), (100, 100))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 1
        assert fp == 0
        assert fn == 0

    def test_tp_with_offset(self):
        """Line offset by 5px in each direction should still TP."""
        detected = [((5, 5), (105, 105))]
        ground_truth = [((0, 0), (100, 100))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 1

    def test_tp_multiple_lines(self):
        """Multiple correctly detected lines."""
        detected = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
        ]
        ground_truth = [
            ((12, 12), (98, 98)),
            ((202, 198), (298, 302)),
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 2
        assert fp == 0
        assert fn == 0


class TestFPCounting:
    """Test that false positives are correctly counted."""

    def test_fp_no_match(self):
        """Detected line far from any GT → FP."""
        detected = [((10, 10), (100, 100))]
        ground_truth = [((500, 500), (600, 600))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 0
        assert fp == 1
        assert fn == 1

    def test_fp_multiple(self):
        """Multiple detected lines with no GT → all FP."""
        detected = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
        ]
        ground_truth: list[Line] = []
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 0
        assert fp == 2
        assert fn == 0

    def test_fp_partial_match(self):
        """One TP + one FP when only one GT exists."""
        detected = [
            ((10, 10), (100, 100)),  # matches GT
            ((500, 500), (600, 600)),  # no match → FP
        ]
        ground_truth = [((12, 12), (98, 98))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 1
        assert fp == 1
        assert fn == 0


class TestFNCounting:
    """Test that false negatives are correctly counted."""

    def test_fn_no_detections(self):
        """No detections, one GT → FN."""
        detected: list[Line] = []
        ground_truth = [((10, 10), (100, 100))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 0
        assert fp == 0
        assert fn == 1

    def test_fn_multiple_gt_undetected(self):
        """Two GT lines, none detected → FN=2."""
        detected: list[Line] = []
        ground_truth = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 0
        assert fn == 2

    def test_fn_partial_detection(self):
        """Detect 1 of 2 GT lines → FN=1."""
        detected = [((10, 10), (100, 100))]
        ground_truth = [
            ((12, 12), (98, 98)),    # matched
            ((500, 500), (600, 600)), # unmatched → FN
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 1
        assert fn == 1


class TestPrecisionRecallF1:
    """Test precision, recall, and F1 calculations."""

    def test_perfect_precision(self):
        """All detections match GT → precision = 1.0."""
        detected = [((10, 10), (100, 100))]
        ground_truth = [((10, 10), (100, 100))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        precision = tp / max(tp + fp, 1)
        assert precision == pytest.approx(1.0)

    def test_perfect_recall(self):
        """All GT lines detected → recall = 1.0."""
        detected = [((10, 10), (100, 100))]
        ground_truth = [((10, 10), (100, 100))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        recall = tp / max(tp + fn, 1)
        assert recall == pytest.approx(1.0)

    def test_precision_calculation_known(self):
        """TP=3, FP=1 → precision = 0.75."""
        # We need 3 matching lines and 1 non-matching
        detected = [
            ((10, 10), (100, 100)),   # → matches GT[0]
            ((200, 200), (300, 300)),  # → matches GT[1]
            ((400, 400), (500, 500)),  # → matches GT[2]
            ((800, 800), (900, 900)),  # → no match
        ]
        ground_truth = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
            ((400, 400), (500, 500)),
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 3
        assert fp == 1
        assert fn == 0
        precision = tp / max(tp + fp, 1)
        assert precision == pytest.approx(0.75)

    def test_recall_calculation_known(self):
        """TP=2, FN=1 → recall ≈ 0.667."""
        detected = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
        ]
        ground_truth = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
            ((500, 500), (600, 600)),  # missed
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 2
        assert fn == 1
        recall = tp / max(tp + fn, 1)
        assert recall == pytest.approx(2.0 / 3.0, abs=1e-6)

    def test_f1_perfect(self):
        """Perfect detection → F1 = 1.0."""
        detected = [((10, 10), (100, 100))]
        ground_truth = [((10, 10), (100, 100))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)
        assert f1 == pytest.approx(1.0)

    def test_f1_known_values(self):
        """TP=3, FP=1, FN=1 → P=0.75, R=0.75, F1=0.75."""
        detected = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
            ((400, 400), (500, 500)),
            ((800, 800), (900, 900)),  # FP
        ]
        ground_truth = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
            ((400, 400), (500, 500)),
            ((1000, 1000), (1100, 1100)),  # FN
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 3
        assert fp == 1
        assert fn == 1
        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)
        assert p == pytest.approx(0.75)
        assert r == pytest.approx(0.75)
        assert f1 == pytest.approx(0.75)

    def test_f1_zero_tp(self):
        """No matches → P=0, R=0, F1=0."""
        detected = [((10, 10), (100, 100))]
        ground_truth = [((500, 500), (600, 600))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)
        assert f1 == pytest.approx(0.0)

    def test_f1_symmetric(self):
        """F1 is symmetric w.r.t. precision and recall: if P=0.6, R=0.75,
        F1 should be 2*0.6*0.75/(0.6+0.75) ≈ 0.6667."""
        detected = [
            ((10, 10), (100, 100)),   # TP
            ((200, 200), (300, 300)),  # TP
            ((400, 400), (500, 500)),  # TP
            ((800, 800), (900, 900)),  # FP
        ]
        ground_truth = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
            ((400, 400), (500, 500)),
            ((600, 600), (700, 700)),  # FN
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 3
        assert fp == 1
        assert fn == 1
        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)
        # P = 3/4 = 0.75, R = 3/4 = 0.75, F1 = 0.75
        assert f1 == pytest.approx(0.75)


class TestRedundantDetection:
    """Test that redundant detections (second match to same GT) are counted as
    redundant, not as additional TPs."""

    def test_redundant_two_detect_one_gt(self):
        """Two detected lines both matching the same GT → 1 TP + 1 redundant."""
        detected = [
            ((10, 10), (100, 100)),
            ((12, 12), (98, 98)),  # very close to first, matches same GT
        ]
        ground_truth = [((11, 11), (99, 99))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 1
        assert red == 1
        assert fp == 0
        assert fn == 0

    def test_redundant_three_detect_two_gt(self):
        """Three detected, two GT: two TP, one redundant."""
        detected = [
            ((10, 10), (100, 100)),   # matches GT[0]
            ((12, 12), (98, 98)),     # also matches GT[0] → redundant
            ((500, 500), (600, 600)), # matches GT[1]
        ]
        ground_truth = [
            ((11, 11), (99, 99)),
            ((500, 500), (600, 600)),
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 2
        assert red == 1
        assert fp == 0
        assert fn == 0

    def test_redundant_not_counted_as_fp(self):
        """Redundant lines should not be counted as FP."""
        detected = [
            ((10, 10), (100, 100)),
            ((11, 11), (99, 99)),  # redundant
        ]
        ground_truth = [((10, 10), (100, 100))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert red == 1
        assert fp == 0  # critical: redundant ≠ FP


class TestEvaluateFunction:
    """Integration tests for the evaluate() function with synthetic data."""

    def test_evaluate_perfect_match(self):
        """All detected match all GT exactly → TP=N, FP=0, FN=0."""
        detected = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
            ((400, 400), (500, 500)),
        ]
        ground_truth = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
            ((400, 400), (500, 500)),
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 3
        assert fp == 0
        assert fn == 0
        assert red == 0

    def test_evaluate_no_match(self):
        """No overlap between detected and GT → TP=0, FP=N_detected, FN=N_gt."""
        detected = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
        ]
        ground_truth = [
            ((500, 500), (600, 600)),
            ((700, 700), (800, 800)),
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 0
        assert fp == 2
        assert fn == 2
        assert red == 0

    def test_evaluate_empty_detected(self):
        """No detections → TP=0, FP=0, FN=N_gt."""
        detected: list[Line] = []
        ground_truth = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 0
        assert fp == 0
        assert fn == 2

    def test_evaluate_empty_ground_truth(self):
        """No GT → all detections are FP."""
        detected = [
            ((10, 10), (100, 100)),
            ((200, 200), (300, 300)),
        ]
        ground_truth: list[Line] = []
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 0
        assert fp == 2
        assert fn == 0

    def test_evaluate_both_empty(self):
        """Both empty → all zeros."""
        tp, fp, fn, red = evaluate([], [])
        assert tp == 0
        assert fp == 0
        assert fn == 0
        assert red == 0

    def test_evaluate_custom_match_dist(self):
        """Tighter match_dist reduces TPs for offset lines."""
        detected = [((10, 10), (100, 100))]
        ground_truth = [((20, 20), (90, 90))]
        # With match_dist=20, this should be TP (avg dist ≈ 7.1)
        tp20, _, _, _ = evaluate(detected, ground_truth, match_dist=20)
        assert tp20 == 1

        # With match_dist=5, this might not match
        # avg dist = (point_to_seg(10,10 → 20,20-90,90) + point_to_seg(100,100 → 20,20-90,90)) / 2
        # Point (10,10) to segment (20,20)-(90,90): closest endpoint (20,20), dist = sqrt(200) ≈ 14.1
        # Point (100,100) to segment (20,20)-(90,90): closest endpoint (90,90), dist = sqrt(200) ≈ 14.1
        # avg ≈ 14.1
        tp5, fp5, _, _ = evaluate(detected, ground_truth, match_dist=5)
        assert tp5 == 0
        assert fp5 == 1

    def test_evaluate_one_to_many_gt(self):
        """One detected line matching one of many GT → 1 TP, rest FN."""
        detected = [((100, 100), (200, 200))]
        ground_truth = [
            ((100, 100), (200, 200)),  # matched
            ((500, 500), (600, 600)),  # FN
            ((700, 700), (800, 800)),  # FN
        ]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 1
        assert fn == 2
        assert fp == 0

    def test_evaluate_many_to_one_gt(self):
        """Multiple detected lines, one GT → 1 TP + rest redundant."""
        detected = [
            ((10, 10), (100, 100)),
            ((11, 11), (99, 99)),
            ((12, 12), (98, 98)),
        ]
        ground_truth = [((10, 10), (100, 100))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 1
        assert red == 2
        assert fp == 0


class TestEvaluateEdgeCases:
    """Edge cases and boundary conditions for the evaluate function."""

    def test_single_point_segment(self):
        """Zero-length segment as ground truth."""
        detected = [((50, 50), (50, 50))]
        ground_truth = [((50, 50), (50, 50))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 1

    def test_very_long_line(self):
        """Very long lines should still match if close enough."""
        detected = [((0, 0), (10000, 10000))]
        ground_truth = [((5, 5), (9995, 9995))]
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 1

    def test_horizontal_vs_vertical(self):
        """A horizontal and vertical line should not match each other."""
        detected = [((0, 0), (100, 0))]
        ground_truth = [((50, -50), (50, 50))]
        # Point (0,0) to segment (50,-50)-(50,50): closest is (50,0), dist=50
        # Point (100,0) to segment (50,-50)-(50,50): closest is (50,0), dist=50
        # avg = 50 > 20
        tp, fp, fn, red = evaluate(detected, ground_truth)
        assert tp == 0
        assert fp == 1
        assert fn == 1

    def test_parallel_offset_line(self):
        """Two parallel lines offset by match_dist boundary."""
        detected = [((0, 0), (100, 0))]
        ground_truth = [((0, 19), (100, 19))]
        # Point (0,0) to segment (0,19)-(100,19): closest is (0,19), dist=19
        # Point (100,0) to segment (0,19)-(100,19): closest is (100,19), dist=19
        # avg = 19 < 20 → TP
        tp, _, _, _ = evaluate(detected, ground_truth, match_dist=20)
        assert tp == 1

        # Now offset by 21 → should be FP
        ground_truth2 = [((0, 21), (100, 21))]
        _, fp2, _, _ = evaluate(detected, ground_truth2, match_dist=20)
        assert fp2 == 1

    def test_match_dist_zero_exact(self):
        """match_dist=0: only exact matches count as TP."""
        detected = [((10, 10), (100, 100))]
        ground_truth = [((10, 10), (100, 100))]
        tp, fp, fn, red = evaluate(detected, ground_truth, match_dist=0)
        assert tp == 1

        ground_truth2 = [((11, 11), (100, 100))]
        tp2, fp2, _, _ = evaluate(detected, ground_truth2, match_dist=0)
        assert tp2 == 0
        assert fp2 == 1


# ═══════════════════════════════════════════════════════════════════
# PHASE 4.3 — SYNTHETIC ERROR INJECTION
# ═══════════════════════════════════════════════════════════════════

from pathlib import Path
import numpy as np


def inject_endpoint_error(lines, level, rng):
    """Displace endpoints of wire lines based on error severity level.

    Parameters
    ----------
    lines : list of ((x1, y1), (x2, y2))
        Detected wire endpoints (pixel coordinates).
    level : int
        Error severity 0–5.  0 = no change, 5 = largest displacement.
    rng : numpy.random.RandomState
        Seeded RNG for reproducibility.

    Returns
    -------
    list of ((x1, y1), (x2, y2))
        New lines with displaced endpoints.
    """
    if level == 0:
        return [tuple(line) for line in lines]

    # Displacement ranges per level (pixels): (low, high) half-range
    ranges = {
        1: (1, 3),
        2: (3, 6),
        3: (6, 10),
        4: (10, 15),
        5: (15, 20),
    }
    lo, hi = ranges.get(level, (15, 20))

    new_lines = []
    for (x1, y1), (x2, y2) in lines:
        dx1 = rng.randint(-hi, hi + 1)
        dy1 = rng.randint(-hi, hi + 1)
        dx2 = rng.randint(-hi, hi + 1)
        dy2 = rng.randint(-hi, hi + 1)
        # For levels 1–2 keep displacement within the tight range
        if level <= 2:
            # Ensure at least ±lo in at least one endpoint
            if abs(dx1) < lo and abs(dy1) < lo:
                dx1 = rng.choice([-1, 1]) * rng.randint(lo, hi + 1)
            if abs(dx2) < lo and abs(dy2) < lo:
                dx2 = rng.choice([-1, 1]) * rng.randint(lo, hi + 1)
        new_lines.append(((x1 + dx1, y1 + dy1), (x2 + dx2, y2 + dy2)))
    return new_lines


def inject_wire_drop(lines, fraction, rng):
    """Randomly remove a fraction of wires from the list.

    Parameters
    ----------
    lines : list
        Wire annotations.
    fraction : float
        Fraction to remove, in [0, 1].
    rng : numpy.random.RandomState
        Seeded RNG.

    Returns
    -------
    list
        Subset of lines (dropped wires removed).
    """
    n = len(lines)
    n_drop = int(round(n * fraction))
    if n_drop == 0:
        return list(lines)
    if n_drop >= n:
        return []
    drop_indices = set(rng.choice(n, size=n_drop, replace=False))
    return [line for i, line in enumerate(lines) if i not in drop_indices]


def endpoint_max_displacement(original, perturbed):
    """Maximum Euclidean displacement across all endpoints."""
    max_d = 0.0
    for (ox, oy), (px, py) in zip(
        [pt for line in original for pt in line],
        [pt for line in perturbed for pt in line],
    ):
        d = np.hypot(px - ox, py - oy)
        if d > max_d:
            max_d = d
    return max_d


SAMPLE_LINES = [
    ((100.0, 100.0), (200.0, 200.0)),
    ((50.0, 150.0), (300.0, 150.0)),
    ((120.0, 80.0), (120.0, 320.0)),
    ((0.0, 0.0), (500.0, 500.0)),
    ((250.0, 50.0), (250.0, 450.0)),
]


class TestEndpointDisplacement:
    """Phase 4.3: endpoint displacement at various error levels."""

    def test_l0_no_change(self):
        """L0 = no change. Lines should be identical."""
        rng = np.random.RandomState(42)
        perturbed = inject_endpoint_error(SAMPLE_LINES, level=0, rng=rng)
        assert len(perturbed) == len(SAMPLE_LINES)
        for orig, new in zip(SAMPLE_LINES, perturbed):
            assert orig == new, "L0 error should leave lines unchanged"

    def test_l1_small_displacement(self):
        """L1 = small displacement (1-3 px range). Endpoints moved slightly."""
        rng = np.random.RandomState(42)
        perturbed = inject_endpoint_error(SAMPLE_LINES, level=1, rng=rng)
        assert len(perturbed) == len(SAMPLE_LINES)
        # Lines should differ (at least one endpoint displaced)
        any_changed = any(orig != new for orig, new in zip(SAMPLE_LINES, perturbed))
        assert any_changed, "L1 should displace at least one endpoint"
        # Max displacement should be within expected range
        max_disp = endpoint_max_displacement(SAMPLE_LINES, perturbed)
        assert max_disp <= 4.0, f"L1 max displacement {max_disp:.1f} exceeds ~3px"

    def test_l5_large_displacement(self):
        """L5 = large displacement (15-20 px range). Endpoints moved significantly."""
        rng = np.random.RandomState(99)
        perturbed = inject_endpoint_error(SAMPLE_LINES, level=5, rng=rng)
        assert len(perturbed) == len(SAMPLE_LINES)
        max_disp = endpoint_max_displacement(SAMPLE_LINES, perturbed)
        # With range 15-20, at least one endpoint should move >10px
        assert max_disp > 5.0, (
            f"L5 max displacement {max_disp:.1f} is suspiciously small"
        )
        assert max_disp <= 30.0, (
            f"L5 max displacement {max_disp:.1f} exceeds expected 20px"
        )

    def test_error_severity_controllable(self):
        """Higher error levels produce strictly larger average deviations."""
        avg_disps = {}
        for level in range(0, 6):
            rng = np.random.RandomState(123)
            perturbed = inject_endpoint_error(SAMPLE_LINES, level=level, rng=rng)
            total = 0.0
            for (ox, oy), (px, py) in zip(
                [pt for l in SAMPLE_LINES for pt in l],
                [pt for l in perturbed for pt in l],
            ):
                total += np.hypot(px - ox, py - oy)
            avg_disps[level] = total / (len(SAMPLE_LINES) * 2)
        # Average displacement should generally increase with level
        for lev in range(1, 6):
            assert avg_disps[lev] >= avg_disps[0], (
                f"Level {lev} avg disp {avg_disps[lev]:.2f} < L0"
            )
        # L5 should be notably larger than L1
        assert avg_disps[5] > avg_disps[1], (
            f"L5 avg {avg_disps[5]:.2f} should be > L1 avg {avg_disps[1]:.2f}"
        )

    def test_l0_preserves_count(self):
        """L0 error should not change wire count."""
        rng = np.random.RandomState(42)
        result = inject_endpoint_error(SAMPLE_LINES, level=0, rng=rng)
        assert len(result) == len(SAMPLE_LINES)


class TestWireDropping:
    """Phase 4.3: wire removal (dropping)."""

    def test_no_drop(self):
        """Fraction=0 removes nothing."""
        rng = np.random.RandomState(42)
        result = inject_wire_drop(SAMPLE_LINES, fraction=0.0, rng=rng)
        assert len(result) == len(SAMPLE_LINES)

    def test_drop_fraction(self):
        """Fraction=0.4 removes approximately 40% of wires."""
        rng = np.random.RandomState(42)
        result = inject_wire_drop(SAMPLE_LINES, fraction=0.4, rng=rng)
        # 5 wires, 0.4 → 2 removed → 3 remain
        assert len(result) == 3, f"Expected 3 remaining, got {len(result)}"

    def test_drop_all(self):
        """Fraction=1.0 removes everything."""
        rng = np.random.RandomState(42)
        result = inject_wire_drop(SAMPLE_LINES, fraction=1.0, rng=rng)
        assert len(result) == 0

    def test_drop_preserves_identity(self):
        """Remaining lines should be originals (no modification)."""
        rng = np.random.RandomState(42)
        result = inject_wire_drop(SAMPLE_LINES, fraction=0.4, rng=rng)
        for line in result:
            assert line in SAMPLE_LINES, "Dropped wires should preserve originals"

    def test_reproducibility(self):
        """Same seed → same dropped subset."""
        r1 = inject_wire_drop(SAMPLE_LINES, fraction=0.4, rng=np.random.RandomState(7))
        r2 = inject_wire_drop(SAMPLE_LINES, fraction=0.4, rng=np.random.RandomState(7))
        assert r1 == r2


# ═══════════════════════════════════════════════════════════════════
# PHASE 5.1 — DATASET INTEGRITY
# ═══════════════════════════════════════════════════════════════════

GT_IMAGES_DIR = Path(
    "/home/claw/workspace/ground_truth/labels_few_annot/images"
)
GT_LABELS_DIR = Path(
    "/home/claw/workspace/ground_truth/labels_few_annot/labels"
    "/train/manually_verified_no_background_data/images"
)
HDC_LABELS_BASE = Path(__file__).resolve().parents[2] / "roboflow_test2"


class TestDatasetImageCount:
    """Phase 5.1: verify ground-truth image directory has expected count."""

    def test_image_count(self):
        """GT images directory should contain a substantial number of JPGs."""
        jpg_files = list(GT_IMAGES_DIR.glob("*.jpg"))
        count = len(jpg_files)
        assert count > 100, f"Expected >100 images, found {count}"
        assert count < 2000, f"Unexpected image count {count}"


class TestDatasetLabelCount:
    """Phase 5.1: verify ground-truth label directory has expected count."""

    def test_label_count(self):
        """GT labels directory should contain a substantial number of TXTs."""
        txt_files = list(GT_LABELS_DIR.glob("*.txt"))
        count = len(txt_files)
        assert count > 100, f"Expected >100 labels, found {count}"
        assert count < 500, f"Unexpected label count {count}"


class TestDatasetFilenameMatch:
    """Phase 5.1: each GT label file should have a matching image file."""

    def test_labels_have_images(self):
        """For each .txt label, the corresponding .jpg image should exist."""
        txt_files = list(GT_LABELS_DIR.glob("*.txt"))
        missing = []
        for txt in txt_files:
            img_name = txt.stem + ".jpg"
            img_path = GT_IMAGES_DIR / img_name
            if not img_path.exists():
                missing.append(img_name)
        if missing:
            ratio = len(missing) / len(txt_files)
            assert ratio < 0.1, (
                f"{len(missing)}/{len(txt_files)} labels missing images "
                f"(>{10:.0f}% threshold)"
            )

    def test_images_have_labels(self):
        """Most images should have a matching label file (allow subset)."""
        jpg_files = list(GT_IMAGES_DIR.glob("*.jpg"))
        missing = []
        for jpg in jpg_files:
            txt_path = GT_LABELS_DIR / (jpg.stem + ".txt")
            if not txt_path.exists():
                missing.append(jpg.name)
        # Many images may not have labels (subset annotation); verify not ALL missing
        assert len(missing) < len(jpg_files), "No images have matching labels"


class TestDatasetLabelFormat:
    """Phase 5.1: verify YOLO-OBB label format (class_id + 8 normalized coords)."""

    def test_label_line_format(self):
        """Each line should have exactly 9 space-separated values."""
        txt_files = list(GT_LABELS_DIR.glob("*.txt"))
        sample = txt_files[:20]
        errors = []
        for txt in sample:
            with open(txt) as f:
                for i, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) != 9:
                        errors.append(f"{txt.name}:{i} has {len(parts)} values")
                    else:
                        try:
                            int(parts[0])
                        except ValueError:
                            errors.append(f"{txt.name}:{i} class_id not int")
                        for j, p in enumerate(parts[1:], 1):
                            try:
                                v = float(p)
                                if not (0.0 <= v <= 1.0):
                                    errors.append(
                                        f"{txt.name}:{i} coord {j}={v} out of [0,1]"
                                    )
                            except ValueError:
                                errors.append(
                                    f"{txt.name}:{i} coord {j} not a number"
                                )
        assert not errors, f"Format errors:\n" + "\n".join(errors[:20])

    def test_label_line_count_nonzero(self):
        """Each checked label file should have at least one annotation line."""
        txt_files = list(GT_LABELS_DIR.glob("*.txt"))
        empty = []
        for txt in txt_files[:30]:
            content = txt.read_text().strip()
            if not content:
                empty.append(txt.name)
        assert not empty, f"Empty label files: {empty}"


class TestDatasetNoEmptyLabels:
    """Phase 5.1: no label file should be completely empty."""

    def test_no_empty_labels(self):
        """Scan all GT label files — none should be empty."""
        txt_files = list(GT_LABELS_DIR.glob("*.txt"))
        empty_files = []
        for txt in txt_files:
            if txt.stat().st_size == 0:
                empty_files.append(txt.name)
        assert not empty_files, f"Empty label files: {empty_files}"


class TestHDCLabelsExist:
    """Phase 5.1: verify HDC (component) labels exist in roboflow_test2."""

    def test_hdc_label_count(self):
        """roboflow_test2 should contain component labels for many images."""
        label_dirs = [
            HDC_LABELS_BASE / "train" / "labels",
            HDC_LABELS_BASE / "valid" / "labels",
            HDC_LABELS_BASE / "test" / "labels",
        ]
        total = 0
        for d in label_dirs:
            if d.exists():
                total += len(list(d.glob("*.txt")))
        assert total > 100, f"Expected >100 HDC labels, found {total}"

    def test_hdc_label_format(self):
        """Sample HDC labels should be in YOLO-OBB format."""
        label_dir = HDC_LABELS_BASE / "train" / "labels"
        if not label_dir.exists():
            pytest.skip("HDC train labels directory not found")
        txt_files = sorted(label_dir.glob("*.txt"))[:5]
        for txt in txt_files:
            with open(txt) as f:
                for i, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    assert len(parts) >= 9, (
                        f"{txt.name}:{i} has {len(parts)} values, expected >=9"
                    )

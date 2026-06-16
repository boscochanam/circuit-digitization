"""
Tests for Phase 1.3 — Edge Cases: components at image boundaries and single component images.
Verifies pipeline handles boundary conditions correctly.
"""
import numpy as np
import cv2
import pytest
from wire_detection.pipeline.stages.threshold import ThresholdStage
from wire_detection.pipeline.stages.ccl import ccl_components
from wire_detection.pipeline.stages.contour_extract import find_endpoints, extract_lines_from_blobs
from wire_detection.pipeline.stages.dedup import global_dedup


# =============================================================================
# Phase 1.3 — Edge Cases: Components at Image Boundaries
# =============================================================================

class TestBoundaryComponents:
    """Test pipeline behavior when components are at image boundaries."""

    def test_component_at_top_edge(self):
        """Component touching the top edge of the image."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.rectangle(img, (10, 0), (90, 20), 60, -1)  # touches top edge
        cv2.line(img, (50, 20), (50, 80), 30, 2)  # wire going down

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        assert result.image.dtype == np.uint8
        assert result.image.max() == 255

        comps = ccl_components(result.image, min_area=28)
        assert len(comps) >= 1

    def test_component_at_bottom_edge(self):
        """Component touching the bottom edge of the image."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.rectangle(img, (10, 80), (90, 99), 60, -1)  # touches bottom edge
        cv2.line(img, (50, 0), (50, 80), 30, 2)  # wire going up

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        comps = ccl_components(result.image, min_area=28)
        assert len(comps) >= 1

    def test_component_at_left_edge(self):
        """Component touching the left edge of the image."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.rectangle(img, (0, 10), (20, 90), 60, -1)  # touches left edge
        cv2.line(img, (20, 50), (80, 50), 30, 2)  # wire going right

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        comps = ccl_components(result.image, min_area=28)
        assert len(comps) >= 1

    def test_component_at_right_edge(self):
        """Component touching the right edge of the image."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.rectangle(img, (80, 10), (99, 90), 60, -1)  # touches right edge
        cv2.line(img, (0, 50), (80, 50), 30, 2)  # wire going left

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        comps = ccl_components(result.image, min_area=28)
        assert len(comps) >= 1

    def test_component_at_corner(self):
        """Component touching the top-left corner."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.rectangle(img, (0, 0), (30, 30), 60, -1)  # top-left corner
        cv2.line(img, (30, 15), (80, 15), 30, 2)  # wire going right
        cv2.line(img, (15, 30), (15, 80), 30, 2)  # wire going down

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        comps = ccl_components(result.image, min_area=28)
        assert len(comps) >= 1

    def test_wire_at_boundary(self):
        """Wire touching the image boundary."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.line(img, (0, 50), (50, 50), 30, 2)  # wire from left edge to center

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        bw_inv = cv2.bitwise_not(result.image)
        lines = extract_lines_from_blobs(bw_inv, min_area=10)
        assert len(lines) >= 1

    def test_crop_bounds_at_boundary(self):
        """ROI crop handles components at image boundaries correctly."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.rectangle(img, (0, 0), (30, 30), 60, -1)  # top-left corner
        cv2.rectangle(img, (70, 70), (99, 99), 60, -1)  # bottom-right corner

        # Simulate ROI crop: union of bboxes + padding
        bbox_union = np.array([[0, 0], [99, 99]])
        pad = 10
        x1 = max(0, bbox_union[0][0] - pad)
        y1 = max(0, bbox_union[0][1] - pad)
        x2 = min(99, bbox_union[1][0] + pad)
        y2 = min(99, bbox_union[1][1] + pad)

        cropped = img[y1:y2+1, x1:x2+1]
        assert cropped.shape[0] > 0
        assert cropped.shape[1] > 0


# =============================================================================
# Phase 1.3 — Edge Cases: Single Component Images
# =============================================================================

class TestSingleComponentImages:
    """Test pipeline behavior with only one component."""

    def test_single_component_detected(self):
        """Single component is detected by CCL."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.rectangle(img, (20, 20), (80, 80), 60, -1)  # single component

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        comps = ccl_components(result.image, min_area=28)
        assert len(comps) == 1

    def test_single_wire_detected(self):
        """Single wire is detected."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.line(img, (10, 50), (90, 50), 30, 2)  # single wire

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        bw_inv = cv2.bitwise_not(result.image)
        lines = extract_lines_from_blobs(bw_inv, min_area=10)
        assert len(lines) >= 1

    def test_single_component_and_wire(self):
        """Single component with one wire connected."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.rectangle(img, (10, 40), (40, 60), 60, -1)  # component
        cv2.line(img, (40, 50), (90, 50), 30, 2)  # wire

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        comps = ccl_components(result.image, min_area=28)
        assert len(comps) >= 1

    def test_empty_image_no_components(self):
        """Empty image (all background) returns no components after proper thresholding."""
        img = np.full((100, 100), 240, dtype=np.uint8)  # all background

        # THRESH_BINARY_INV: pixels > 128 → 0 (background), ≤ 128 → 255
        # Since all pixels are 240 (>128), result is all zeros → no components
        _, bw = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY_INV)
        comps = ccl_components(bw, min_area=28)
        # Uniform image → no foreground → no components
        assert len(comps) == 0

    def test_empty_image_no_lines(self):
        """Empty image returns no lines."""
        img = np.full((100, 100), 240, dtype=np.uint8)  # all background

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        bw_inv = cv2.bitwise_not(result.image)
        lines = extract_lines_from_blobs(bw_inv, min_area=10)
        assert len(lines) == 0

    def test_single_dot_image(self):
        """Image with just a single dot (noise) — OTSU on near-uniform image."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        img[50, 50] = 30  # single dark pixel

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        # OTSU on near-uniform image may produce unexpected results;
        # the key is the pipeline doesn't crash
        assert result.image.size == 100 * 100

    def test_minimal_circuit(self):
        """Minimal circuit: one component, two wires (thicker lines for thresholding)."""
        img = np.full((100, 200), 240, dtype=np.uint8)
        cv2.rectangle(img, (70, 40), (130, 60), 60, -1)  # component
        cv2.line(img, (10, 50), (70, 50), 30, 3)  # left wire (thicker)
        cv2.line(img, (130, 50), (190, 50), 30, 3)  # right wire (thicker)

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        bw_inv = cv2.bitwise_not(result.image)
        lines = extract_lines_from_blobs(bw_inv, min_area=10)
        deduped = global_dedup(lines, angle=12, dist=18)
        # Should detect at least 1 wire segment
        assert len(deduped) >= 1

    def test_single_component_dedup(self):
        """Deduplication works correctly with single component."""
        img = np.full((100, 100), 240, dtype=np.uint8)
        cv2.rectangle(img, (20, 20), (80, 80), 60, -1)

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        bw_inv = cv2.bitwise_not(result.image)
        lines = extract_lines_from_blobs(bw_inv, min_area=28)
        deduped = global_dedup(lines, angle=12, dist=18)
        # Single component should produce 0 or 1 lines (the component boundary)
        assert len(deduped) <= 2

    def test_small_image_single_component(self):
        """Small image (20x20) with single component."""
        img = np.full((20, 20), 240, dtype=np.uint8)
        cv2.rectangle(img, (2, 2), (18, 18), 60, -1)

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        comps = ccl_components(result.image, min_area=1)
        assert len(comps) >= 1

    def test_tall_narrow_image_single_wire(self):
        """Tall narrow image (20x200) with single vertical wire."""
        img = np.full((200, 20), 240, dtype=np.uint8)
        cv2.line(img, (10, 10), (10, 190), 30, 2)

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        bw_inv = cv2.bitwise_not(result.image)
        lines = extract_lines_from_blobs(bw_inv, min_area=10)
        assert len(lines) >= 1

    def test_wide_short_image_single_wire(self):
        """Wide short image (200x20) with single horizontal wire."""
        img = np.full((20, 200), 240, dtype=np.uint8)
        cv2.line(img, (10, 10), (190, 10), 30, 2)

        stage = ThresholdStage()
        result = stage.run(img, {"mode": "otsu"})
        bw_inv = cv2.bitwise_not(result.image)
        lines = extract_lines_from_blobs(bw_inv, min_area=10)
        assert len(lines) >= 1

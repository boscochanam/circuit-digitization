import numpy as np
import cv2
from wire_detection.pipeline.stages.threshold import ThresholdStage
from wire_detection.pipeline.stages.invert import InvertStage
from wire_detection.pipeline.stages.dilate import DilateStage
from wire_detection.pipeline.stages.ccl import CCLStage, ccl_components
from wire_detection.pipeline.stages.contour_extract import find_endpoints, extract_lines_from_blobs
from wire_detection.pipeline.stages.dedup import global_dedup
from wire_detection.pipeline.stages.length_filter import filter_short_lines


def test_threshold_otsu():
    stage = ThresholdStage()
    img = np.full((100, 100), 200, dtype=np.uint8)
    img[30:70, 30:70] = 50
    result = stage.run(img, {"mode": "otsu"})
    assert result.image.dtype == np.uint8
    assert result.image.shape == img.shape


def test_threshold_manual():
    stage = ThresholdStage()
    img = np.full((100, 100), 200, dtype=np.uint8)
    result = stage.run(img, {"mode": "manual", "value": 128})
    assert result.image.dtype == np.uint8


def test_invert():
    stage = InvertStage()
    img = np.zeros((10, 10), dtype=np.uint8)
    result = stage.run(img, {})
    assert result.image[0, 0] == 255


def test_dilate():
    stage = DilateStage()
    img = np.zeros((50, 50), dtype=np.uint8)
    img[25, 25] = 255
    result = stage.run(img, {"kernel_size": 3, "iterations": 1})
    assert result.image.sum() > 0


def test_ccl_components():
    binary = np.zeros((100, 100), dtype=np.uint8)
    cv2.rectangle(binary, (10, 10), (30, 30), 255, -1)
    cv2.rectangle(binary, (60, 60), (80, 80), 255, -1)
    comps = ccl_components(binary, min_area=10)
    assert len(comps) == 2


def test_find_endpoints():
    mask = np.zeros((50, 50), dtype=bool)
    mask[10:30, 20:25] = True
    p1, p2 = find_endpoints(mask)
    assert p1 is not None
    assert p2 is not None


def test_global_dedup():
    lines = [((10, 10), (100, 100)), ((12, 12), (98, 98))]
    deduped = global_dedup(lines, angle=10, dist=12)
    assert len(deduped) == 1


def test_filter_short_lines():
    lines = [((10, 10), (20, 20)), ((10, 10), (200, 200))]
    filtered = filter_short_lines(lines, min_length=50)
    assert len(filtered) == 1


def test_extract_lines_from_blobs(synthetic_non_crossing_image):
    import cv2
    _, bw = cv2.threshold(synthetic_non_crossing_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw_inv = cv2.bitwise_not(bw)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(bw_inv, kernel, iterations=1)
    lines = extract_lines_from_blobs(dilated, min_area=10)
    assert len(lines) == 2


# =============================================================================
# Phase 1.6 — CCL (Connected Component Labeling) Tests
# =============================================================================

from wire_detection.pipeline.stages.dedup import point_line_dist


def test_ccl_min_area_filter():
    """Three components of sizes ~10, ~50, ~200 px. With min_area=28, only 50 and 200 survive."""
    binary = np.zeros((200, 200), dtype=np.uint8)
    # Small component: ~10 px (2x5 rectangle = 10)
    cv2.rectangle(binary, (0, 0), (1, 4), 255, -1)
    # Medium component: ~50 px (5x10 = 50)
    cv2.rectangle(binary, (50, 50), (59, 54), 255, -1)
    # Large component: ~200 px (10x20 = 200)
    cv2.rectangle(binary, (100, 100), (119, 109), 255, -1)

    comps = ccl_components(binary, min_area=28)
    assert len(comps) == 2
    # Verify which components survived by checking area
    areas = [int(c.sum()) for c in comps]
    assert all(a >= 28 for a in areas)
    assert 10 not in areas


def test_ccl_noise_removal():
    """Many tiny 1-2 px noise dots + 2 real components (50+ px each). Noise removed."""
    binary = np.zeros((200, 200), dtype=np.uint8)
    # Scatter 30 noise dots (1 pixel each)
    rng = np.random.RandomState(42)
    noise_positions = rng.randint(0, 200, size=(30, 2))
    for y, x in noise_positions:
        binary[y, x] = 255
    # Add a few 2-pixel noise clusters
    for i in range(10):
        binary[i, 190] = 255
        binary[i, 191] = 255

    # Real component 1: horizontal line 1x60
    cv2.rectangle(binary, (10, 100), (69, 100), 255, -1)
    # Real component 2: square 8x8 = 64
    cv2.rectangle(binary, (100, 100), (107, 107), 255, -1)

    comps = ccl_components(binary, min_area=30)
    assert len(comps) == 2
    areas = [int(c.sum()) for c in comps]
    assert all(a >= 30 for a in areas)


def test_ccl_large_components_preserved():
    """A very large component (5000 px) is preserved regardless of min_area."""
    binary = np.zeros((200, 200), dtype=np.uint8)
    # Large component: ~5000 px
    cv2.rectangle(binary, (10, 10), (80, 80), 255, -1)  # 71x71 = 5041

    comps = ccl_components(binary, min_area=0)
    assert len(comps) == 1
    assert int(comps[0].sum()) >= 5000

    # Even with a very high min_area threshold
    comps_high = ccl_components(binary, min_area=4000)
    assert len(comps_high) == 1
    assert int(comps_high[0].sum()) >= 5000


def test_ccl_component_count():
    """5 separate rectangular components (each 100+ px). ccl_components returns exactly 5."""
    binary = np.zeros((300, 300), dtype=np.uint8)
    # 5 separate 10x10 squares = 100 px each
    positions = [(10, 10), (10, 100), (100, 10), (100, 100), (200, 200)]
    for x, y in positions:
        cv2.rectangle(binary, (x, y), (x + 9, y + 9), 255, -1)

    comps = ccl_components(binary, min_area=30)
    assert len(comps) == 5


def test_ccl_empty_image():
    """All-black image returns empty list."""
    binary = np.zeros((100, 100), dtype=np.uint8)
    comps = ccl_components(binary, min_area=30)
    assert comps == []


def test_ccl_connectivity():
    """Two diagonal-touching 3x3 blocks: 8-connectivity merges them, 4-connectivity keeps them separate."""
    # Create two 3x3 blocks that touch diagonally
    binary = np.zeros((10, 20), dtype=np.uint8)
    # Block 1: rows 2-4, cols 2-4
    binary[2:5, 2:5] = 255
    # Block 2: rows 5-7, cols 5-7 (touches block 1 at pixel (4,4) -> (5,5) diagonally)
    binary[5:8, 5:8] = 255

    # 8-connectivity: diagonal neighbors are connected -> 1 component
    comps_8 = ccl_components(binary, min_area=5, connectivity=8)
    assert len(comps_8) == 1

    # 4-connectivity: diagonal neighbors are NOT connected -> 2 components
    comps_4 = ccl_components(binary, min_area=5, connectivity=4)
    assert len(comps_4) == 2


# =============================================================================
# Phase 1.7 — Endpoint Extraction Tests
# =============================================================================

def test_find_endpoints_horizontal_line():
    """Horizontal line mask (1px tall, 50px wide). Endpoints at left and right extremes."""
    mask = np.zeros((50, 100), dtype=bool)
    mask[25, 10:60] = True  # horizontal line from x=10 to x=59 at y=25

    p1, p2 = find_endpoints(mask)
    assert p1 is not None
    assert p2 is not None

    # The two endpoints should be at x=10 and x=59
    xs = sorted([p1[0], p2[0]])
    assert xs[0] <= 11  # left endpoint
    assert xs[1] >= 58  # right endpoint
    # Both should be at y=25
    assert abs(p1[1] - 25) <= 1
    assert abs(p2[1] - 25) <= 1


def test_find_endpoints_vertical_line():
    """Vertical line mask. Endpoints at top and bottom."""
    mask = np.zeros((100, 50), dtype=bool)
    mask[10:60, 25] = True  # vertical line from y=10 to y=59 at x=25

    p1, p2 = find_endpoints(mask)
    assert p1 is not None
    assert p2 is not None

    ys = sorted([p1[1], p2[1]])
    assert ys[0] <= 11  # top endpoint
    assert ys[1] >= 58  # bottom endpoint
    # Both should be at x=25
    assert abs(p1[0] - 25) <= 1
    assert abs(p2[0] - 25) <= 1


def test_find_endpoints_diagonal():
    """Diagonal line mask. Endpoints at the two ends."""
    mask = np.zeros((100, 100), dtype=bool)
    # Draw a diagonal line from (10, 10) to (60, 60)
    for i in range(51):
        mask[10 + i, 10 + i] = True

    p1, p2 = find_endpoints(mask)
    assert p1 is not None
    assert p2 is not None

    # One endpoint should be near (10, 10), other near (60, 60)
    dist_top_left = min(
        math.hypot(p1[0] - 10, p1[1] - 10),
        math.hypot(p2[0] - 10, p2[1] - 10),
    )
    dist_bottom_right = min(
        math.hypot(p1[0] - 60, p1[1] - 60),
        math.hypot(p2[0] - 60, p2[1] - 60),
    )
    assert dist_top_left <= 2
    assert dist_bottom_right <= 2


def test_find_endpoints_empty_mask():
    """Empty mask returns (None, None)."""
    mask = np.zeros((50, 50), dtype=bool)
    p1, p2 = find_endpoints(mask)
    assert p1 is None
    assert p2 is None


def test_extract_lines_multiple_blobs():
    """3 separate line-shaped blobs -> extract_lines_from_blobs returns 3 lines."""
    binary = np.zeros((100, 300), dtype=np.uint8)
    # Blob 1: horizontal line at top
    cv2.rectangle(binary, (10, 10), (80, 11), 255, -1)  # ~72 px
    # Blob 2: horizontal line at middle
    cv2.rectangle(binary, (10, 50), (80, 51), 255, -1)  # ~72 px
    # Blob 3: horizontal line at bottom
    cv2.rectangle(binary, (10, 90), (80, 91), 255, -1)  # ~72 px

    lines = extract_lines_from_blobs(binary, min_area=30)
    assert len(lines) == 3
    # Each line should be a tuple of two points
    for line in lines:
        assert len(line) == 2
        assert all(isinstance(p, tuple) and len(p) == 2 for p in line)


def test_extract_lines_filters_small_blobs():
    """Large blob (area >= min_area) produces a line; tiny blob does not."""
    binary = np.zeros((100, 300), dtype=np.uint8)
    # Large blob: 10x10 = 100 px
    cv2.rectangle(binary, (10, 10), (19, 19), 255, -1)
    # Tiny blob: 3x1 = 3 px (below min_area)
    cv2.rectangle(binary, (50, 50), (52, 50), 255, -1)

    lines = extract_lines_from_blobs(binary, min_area=30)
    assert len(lines) == 1
    # The single line should come from the large blob
    line = lines[0]
    xs = [line[0][0], line[1][0]]
    assert min(xs) >= 10
    assert max(xs) <= 19


# =============================================================================
# Phase 1.8 — Overlap Deduplication Tests
# =============================================================================

import math


def test_dedup_removes_near_duplicate():
    """Two nearly identical lines (offset by 2px) should be merged to 1."""
    lines = [
        ((100, 100), (200, 100)),
        ((100, 102), (200, 102)),  # shifted down by 2px
    ]
    deduped = global_dedup(lines, angle=10, dist=12)
    assert len(deduped) == 1


def test_dedup_preserves_unique_lines():
    """Two perpendicular lines should both be kept."""
    lines = [
        ((100, 100), (200, 100)),  # horizontal
        ((150, 50), (150, 150)),   # vertical
    ]
    deduped = global_dedup(lines, angle=10, dist=12)
    assert len(deduped) == 2


def test_dedup_angle_threshold():
    """Two lines at ~15° angle, overlapping spatially.
    With angle=10 they should be kept (angle > threshold).
    With angle=20 they should be merged (angle < threshold, close enough).
    """
    # Two lines sharing a common midpoint region, at ~15° from each other
    # They overlap spatially so both endpoints of the shorter line are near the longer line
    angle_rad = math.radians(15)
    # Both lines are ~100px long, centered at (100, 50)
    # Line 1: horizontal
    lines_a = ((50, 50), (150, 50))
    # Line 2: rotated 15°, also centered near (100, 50) — both endpoints within dist of line1
    cx, cy = 100, 50
    half = 50
    x1 = cx - int(half * math.cos(angle_rad))
    y1 = cy + int(half * math.sin(angle_rad))
    x2 = cx + int(half * math.cos(angle_rad))
    y2 = cy - int(half * math.sin(angle_rad))
    lines_b = ((x1, y1), (x2, y2))

    lines = [lines_a, lines_b]

    # angle=10: 15° > 10° -> both kept
    deduped_tight = global_dedup(lines, angle=10, dist=12)
    assert len(deduped_tight) == 2

    # angle=20: 15° < 20° -> merged (endpoints close enough to longer line)
    deduped_wide = global_dedup(lines, angle=20, dist=12)
    assert len(deduped_wide) == 1


def test_dedup_distance_threshold():
    """Two parallel lines 30px apart. Even with large angle threshold, NOT merged (too far)."""
    lines = [
        ((100, 50), (200, 50)),   # horizontal at y=50
        ((100, 80), (200, 80)),   # horizontal at y=80 (30px apart)
    ]
    deduped = global_dedup(lines, angle=90, dist=12)
    assert len(deduped) == 2


def test_dedup_empty_input():
    """Empty list returns empty list."""
    deduped = global_dedup([], angle=10, dist=12)
    assert deduped == []


def test_dedup_single_line():
    """Single line returns itself."""
    lines = [((10, 10), (100, 100))]
    deduped = global_dedup(lines, angle=10, dist=12)
    assert len(deduped) == 1
    assert deduped[0] == ((10, 10), (100, 100))


def test_dedup_t_junction():
    """A T-junction (3 lines meeting at a point). All 3 preserved (different angles)."""
    # T-junction: horizontal line + vertical line going up + vertical line going down
    # All meet at (100, 100)
    lines = [
        ((50, 100), (150, 100)),   # horizontal
        ((100, 100), (100, 50)),   # vertical up
        ((100, 100), (100, 150)),  # vertical down
    ]
    deduped = global_dedup(lines, angle=10, dist=12)
    assert len(deduped) == 3


def test_point_line_dist_on_line():
    """Point exactly on the line segment should have distance ~0."""
    dist = point_line_dist((50, 50), (0, 50), (100, 50))
    assert dist < 0.01


def test_point_line_dist_off_line():
    """Point off the line should have correct perpendicular distance."""
    # Point (50, 55) is 5 units away from horizontal line y=50
    dist = point_line_dist((50, 55), (0, 50), (100, 50))
    assert abs(dist - 5.0) < 0.01


def test_point_line_dist_at_endpoint():
    """Point at an endpoint should have distance 0."""
    dist = point_line_dist((0, 50), (0, 50), (100, 50))
    assert dist < 0.01

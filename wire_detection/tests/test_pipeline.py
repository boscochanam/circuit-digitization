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

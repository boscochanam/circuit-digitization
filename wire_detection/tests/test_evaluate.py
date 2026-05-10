from wire_detection.evaluate.metric import point_to_segment_dist, segment_dist
from wire_detection.evaluate.match import evaluate


def test_point_to_segment_dist_zero():
    dist = point_to_segment_dist((10, 10), (10, 10), (20, 20))
    assert dist == 0.0


def test_point_to_segment_dist_perpendicular():
    dist = point_to_segment_dist((5, 10), (0, 0), (10, 0))
    assert dist == 10.0


def test_segment_dist_identical():
    seg = ((0, 0), (10, 10))
    dist = segment_dist(seg, seg)
    assert dist == 0.0


def test_segment_dist_parallel():
    d = ((0, 0), (10, 10))
    g = ((0, 5), (10, 15))
    dist = segment_dist(d, g)
    assert dist > 0


def test_evaluate_perfect():
    detections = [((10, 10), (100, 100)), ((10, 100), (100, 10))]
    gt = [((10, 10), (100, 100)), ((10, 100), (100, 10))]
    result = evaluate(detections, gt, dist_thresh=20)
    assert result.tp == 2
    assert result.fp == 0
    assert result.fn == 0
    assert result.f1 == 1.0


def test_evaluate_no_matches():
    detections = [((0, 0), (5, 5))]
    gt = [((100, 100), (200, 200))]
    result = evaluate(detections, gt, dist_thresh=20)
    assert result.tp == 0
    assert result.fp == 1
    assert result.fn == 1


def test_evaluate_redundant():
    detections = [((10, 10), (100, 100)), ((12, 12), (98, 98))]
    gt = [((10, 10), (100, 100))]
    result = evaluate(detections, gt, dist_thresh=20)
    assert result.tp == 1
    assert result.redundant == 1

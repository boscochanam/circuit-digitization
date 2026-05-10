import numpy as np
from wire_detection.sdg.generator import SDG, SDGConfig
from wire_detection.sdg.primitives import get_bezier_curve, get_rect_edge_point
from wire_detection.sdg.backgrounds import generate_plain_background, generate_grid_background, generate_noise_background
from wire_detection.sdg.formats import export_yolov8_pose, export_lines
from pathlib import Path
import tempfile


def test_generate_one():
    cfg = SDGConfig(num_images=1, seed=42)
    sdg = SDG(cfg)
    rng = np.random.default_rng(42)
    img, lines = sdg.generate_one(rng)
    assert img is not None
    assert len(lines) >= 3
    assert img.shape[0] == 1024
    assert img.shape[1] == 1024


def test_get_bezier_curve():
    import random
    rng = random.Random(42)
    curve = get_bezier_curve((10, 10), (100, 100), rng=rng)
    assert curve.shape[0] == 50
    assert curve.shape[1] == 2
    assert tuple(curve[0]) == (10, 10) or tuple(curve[0]) == (10, 10)


def test_get_rect_edge_point():
    pt = get_rect_edge_point((50, 50), (100, 100), (0, 0, 100, 100))
    assert pt is not None
    assert len(pt) == 2


def test_background_plain():
    bg = generate_plain_background((100, 100))
    assert bg.shape == (100, 100)
    assert bg[0, 0] == 255


def test_background_grid():
    bg = generate_grid_background((100, 100), grid_size=50)
    assert bg.shape == (100, 100)


def test_background_noise():
    bg = generate_noise_background((100, 100), noise_type="gaussian")
    assert bg.shape == (100, 100)


def test_export_yolov8_pose():
    lines = [((10, 20), (100, 200))]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        export_yolov8_pose(lines, (640, 640), f.name)
        with open(f.name) as f2:
            content = f2.read()
        assert len(content) > 0
        Path(f.name).unlink()


def test_export_lines():
    lines = [((10, 20), (100, 200))]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        export_lines(lines, f.name)
        with open(f.name) as f2:
            content = f2.read()
        assert "10 20 100 200" in content
        Path(f.name).unlink()

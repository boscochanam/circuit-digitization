import json
from pathlib import Path

import cv2
import numpy as np
import pytest

pytest.importorskip("wire_detection.data.cghd_subset", reason="cghd_subset module not available")
from wire_detection.data.cghd_subset import (
    build_cghd_subset,
    load_cghd_class_map,
    normalize_cghd_label,
    polygon_to_yolo_obb,
    quality_filter,
)


def test_normalize_cghd_label():
    assert normalize_cghd_label("capacitor.unpolarized") == "capacitor-unpolarized"


def test_quality_filter_rejects_dark_image():
    image = np.zeros((128, 128), dtype=np.uint8)
    result = quality_filter(image, strictness="moderate")
    assert not result.keep
    assert "too_dark" in result.issues


def test_polygon_to_yolo_obb_returns_eight_coords():
    coords = polygon_to_yolo_obb([[10, 10], [30, 10], [30, 30], [10, 30]], 100, 100)
    assert len(coords) == 8
    assert all(0.0 <= value <= 1.0 for value in coords)


def test_build_cghd_subset_exports_labels(tmp_path):
    source = tmp_path / "cghd1152"
    drafter = source / "drafter_1"
    (drafter / "images").mkdir(parents=True)
    (drafter / "instances").mkdir(parents=True)

    classes = {
        "__background__": 0,
        "resistor": 1,
        "block": 2,
    }
    (source / "classes.json").write_text(json.dumps(classes), encoding="utf-8")

    image = np.full((256, 256, 3), 200, dtype=np.uint8)
    cv2.rectangle(image, (80, 110), (180, 150), (0, 0, 0), 2)
    image_path = drafter / "images" / "C1_D1_P1.jpg"
    cv2.imwrite(str(image_path), image)

    instance = {
        "imageHeight": 256,
        "imageWidth": 256,
        "shapes": [
            {
                "label": "resistor",
                "points": [[80, 110], [180, 110], [180, 150], [80, 150]],
                "shape_type": "polygon",
            },
            {
                "label": "block",
                "points": [[10, 10], [20, 10], [20, 20], [10, 20]],
                "shape_type": "polygon",
            },
        ],
    }
    (drafter / "instances" / "C1_D1_P1.json").write_text(json.dumps(instance), encoding="utf-8")

    output = tmp_path / "out"
    summary = build_cghd_subset(source, output, strictness="lenient", train_ratio=1.0, seed=1)

    assert summary["images_kept"] == 1
    assert (output / "train" / "images" / "C1_D1_P1.jpg").exists()
    label_path = output / "train" / "labels" / "C1_D1_P1.txt"
    assert label_path.exists()
    line = label_path.read_text(encoding="utf-8").strip().split()
    assert line[0] == "0"
    assert len(line) == 9
    classes_out = (output / "classes.txt").read_text(encoding="utf-8").splitlines()
    assert classes_out == ["resistor"]
    assert load_cghd_class_map(source) == {"resistor": 0}

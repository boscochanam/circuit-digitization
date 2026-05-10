import pytest
import numpy as np
import cv2
from pathlib import Path


@pytest.fixture
def synthetic_image():
    img = np.full((200, 200), 255, dtype=np.uint8)
    cv2.line(img, (30, 30), (170, 170), 0, 2)
    cv2.line(img, (30, 170), (170, 30), 0, 2)
    return img


@pytest.fixture
def synthetic_non_crossing_image():
    img = np.full((200, 200), 255, dtype=np.uint8)
    cv2.line(img, (30, 30), (170, 30), 0, 2)
    cv2.line(img, (30, 170), (170, 170), 0, 2)
    return img


@pytest.fixture
def synthetic_gt_lines():
    return [((30, 30), (170, 170)), ((30, 170), (170, 30))]


@pytest.fixture
def sample_pipeline_config():
    return {
        "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract", "dedup", "length_filter"],
        "stage_params": {
            "threshold": {"mode": "otsu"},
            "dilate": {"kernel_size": 3, "iterations": 1},
            "ccl": {"min_area": 10},
            "dedup": {"angle_thresh": 10, "dist_thresh": 12},
            "length_filter": {"min_length": 20},
        },
    }

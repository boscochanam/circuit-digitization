from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "baseline": {
        "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract", "dedup", "length_filter"],
        "stage_params": {
            "threshold": {"mode": "otsu"},
            "dilate": {"kernel_size": 5, "iterations": 1},
            "ccl": {"min_area": 30},
            "dedup": {"angle_thresh": 10, "dist_thresh": 12},
            "length_filter": {"min_length": 20},
        },
    },
    "aggressive": {
        "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract", "dedup", "length_filter"],
        "stage_params": {
            "threshold": {"mode": "otsu"},
            "dilate": {"kernel_size": 7, "iterations": 2},
            "ccl": {"min_area": 20},
            "dedup": {"angle_thresh": 5, "dist_thresh": 8},
            "length_filter": {"min_length": 10},
        },
    },
    "conservative": {
        "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract", "dedup", "length_filter"],
        "stage_params": {
            "threshold": {"mode": "manual", "value": 140},
            "dilate": {"kernel_size": 3, "iterations": 1},
            "ccl": {"min_area": 50},
            "dedup": {"angle_thresh": 15, "dist_thresh": 20},
            "length_filter": {"min_length": 50},
        },
    },
    "no_dedup": {
        "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract", "length_filter"],
        "stage_params": {
            "threshold": {"mode": "otsu"},
            "dilate": {"kernel_size": 5, "iterations": 1},
            "ccl": {"min_area": 30},
            "length_filter": {"min_length": 20},
        },
    },
    "heavy_dilate": {
        "stages": ["threshold", "invert", "dilate", "ccl", "contour_extract", "dedup", "length_filter"],
        "stage_params": {
            "threshold": {"mode": "otsu"},
            "dilate": {"kernel_size": 9, "iterations": 3},
            "ccl": {"min_area": 50},
            "dedup": {"angle_thresh": 10, "dist_thresh": 12},
            "length_filter": {"min_length": 30},
        },
    },
}

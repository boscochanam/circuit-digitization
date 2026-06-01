"""Presets API route."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

PRESETS: dict[str, dict[str, Any]] = {
    "best_candidate_v4": {
        "label": "Best v4 (Sauvola+Component, F1=0.833)",
        "description": "Sauvola k=0.285 w=67 | close 3×3 | CCL 28 | PCA endpoints | overlap dedup | anchor filter",
        "sauvola_k": 0.285,
        "sauvola_window": 67,
        "close_kernel": 3,
        "ccl_min_area": 28,
        "endpoint_mode": "pca",
        "dedup_mode": "overlap",
        "dedup_angle": 10,
        "dedup_dist": 18,
        "anchor_filter_enabled": True,
        "anchor_endpoint_dist": 12.0,
        "anchor_link_dist": 8.0,
    },
    "best_candidate_v2": {
        "label": "v2 (Sauvola+Component, F1=0.826)",
        "description": "Sauvola k=0.285 w=61 | CCL 24 | PCA | overlap dedup | anchor filter",
        "sauvola_k": 0.285,
        "sauvola_window": 61,
        "close_kernel": 3,
        "ccl_min_area": 24,
        "endpoint_mode": "pca",
        "dedup_mode": "overlap",
        "dedup_angle": 10,
        "dedup_dist": 18,
        "anchor_filter_enabled": True,
        "anchor_endpoint_dist": 12.0,
        "anchor_link_dist": 8.0,
    },
    "skeleton_graph_v1": {
        "label": "Skeleton Graph v1 (F1=0.819, best recall)",
        "description": "Sauvola k=0.285 w=67 | skeleton graph extraction | score_cluster dedup | anchor filter",
        "sauvola_k": 0.285,
        "sauvola_window": 67,
        "close_kernel": 3,
        "ccl_min_area": 28,
        "endpoint_mode": "pca",
        "dedup_mode": "score_cluster",
        "dedup_angle": 10,
        "dedup_dist": 18,
        "anchor_filter_enabled": True,
        "anchor_endpoint_dist": 14.0,
        "anchor_link_dist": 8.0,
        "extraction_mode": "skeleton",
    },
    "baseline_control": {
        "label": "Baseline (Sauvola+Component, F1=0.795)",
        "description": "Sauvola k=0.30 w=51 | CCL 20 | extremal endpoints | baseline dedup",
        "sauvola_k": 0.30,
        "sauvola_window": 51,
        "close_kernel": 3,
        "ccl_min_area": 20,
        "endpoint_mode": "extremal",
        "dedup_mode": "baseline",
        "dedup_angle": 10,
        "dedup_dist": 18,
        "anchor_filter_enabled": False,
    },
    "legacy_threshold": {
        "label": "Legacy (OTSU/Manual threshold, old UI)",
        "description": "Old stage-based pipeline with user-controlled threshold/dilate/CCL params",
        "legacy": True,
    },
}


@router.get("/api/presets")
def list_presets():
    """Return available pipeline presets for the UI dropdown."""
    result = {}
    for key, preset in PRESETS.items():
        entry = {
            "label": preset["label"],
            "description": preset["description"],
        }
        if not preset.get("legacy"):
            entry["params"] = {
                "sauvola_k": preset.get("sauvola_k", 0.285),
                "sauvola_window": preset.get("sauvola_window", 67),
                "close_kernel": preset.get("close_kernel", 3),
                "ccl_min_area": preset.get("ccl_min_area", 28),
                "dedup_angle": preset.get("dedup_angle", 10),
                "dedup_dist": preset.get("dedup_dist", 18),
                "anchor_endpoint_dist": preset.get("anchor_endpoint_dist", 12.0),
                "anchor_link_dist": preset.get("anchor_link_dist", 8.0),
            }
        result[key] = entry
    return JSONResponse(result)

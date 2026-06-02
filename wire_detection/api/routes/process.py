"""Pipeline processing API route."""
from __future__ import annotations

import base64
import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import wire_detection.api.deps as deps
from wire_detection.api.routes.presets import PRESETS
from wire_detection.pipeline.factory import PipelineFactory

router = APIRouter()

# ── Pipeline result cache ──
# Keys on (image_path, preset_name, canonical_params_json) so tab switches
# that reuse the same detection params return instantly.
_PIPELINE_CACHE: dict[str, dict] = {}
_PIPELINE_CACHE_MAX = 128
_PIPELINE_CACHE_ORDER: list[str] = []  # LRU eviction tracking


def _cache_key(image_path: str, preset_name: str, params: dict) -> str:
    canonical = json.dumps(params, sort_keys=True, default=str)
    raw = f"{image_path}|{preset_name}|{canonical}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str) -> dict | None:
    if key in _PIPELINE_CACHE:
        # move to end (most recently used)
        _PIPELINE_CACHE_ORDER.remove(key)
        _PIPELINE_CACHE_ORDER.append(key)
        return _PIPELINE_CACHE[key]
    return None


def _cache_put(key: str, value: dict) -> None:
    if key in _PIPELINE_CACHE:
        _PIPELINE_CACHE_ORDER.remove(key)
    elif len(_PIPELINE_CACHE) >= _PIPELINE_CACHE_MAX:
        # evict oldest
        oldest = _PIPELINE_CACHE_ORDER.pop(0)
        _PIPELINE_CACHE.pop(oldest)
    _PIPELINE_CACHE[key] = value
    _PIPELINE_CACHE_ORDER.append(key)


def _img_to_base64(image: np.ndarray) -> str:
    _, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode("utf-8")


def _build_legacy_config(params: dict) -> dict:
    """Build pipeline config from old-style UI params."""
    config = deps._load_default_config()
    stage_params = config.get("stage_params", {})
    if "k" in params:
        stage_params["threshold"]["k"] = float(params["k"])
    if "min_area" in params:
        stage_params["ccl"]["min_area"] = int(params["min_area"])
    if "dedup_angle" in params:
        stage_params["dedup"]["angle_thresh"] = int(params["dedup_angle"])
    if "dedup_dist" in params:
        stage_params["dedup"]["dist_thresh"] = int(params["dedup_dist"])
    if "close_ks" in params:
        stage_params["close"]["kernel_size"] = int(params["close_ks"])
    return config


def _run_preset_pipeline_cached(
    image: np.ndarray, image_path: str, preset_name: str, ui_params: dict
) -> dict:
    """Run pipeline with LRU caching by (image_path, preset_name, params)."""
    key = _cache_key(image_path, preset_name, ui_params)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    result = _run_preset_pipeline(image, preset_name, ui_params, image_path=image_path)
    _cache_put(key, result)
    return result


def _run_preset_pipeline(image: np.ndarray, preset_name: str, ui_params: dict, image_path: str = "") -> dict:
    """Run the preset pipeline on an image. Returns results dict."""
    from wire_detection.benchmark.experiment_harness import (
        ExperimentConfig, build_component_mask, crop_to_roi, shift_components,
        detect_wires_experiment, sauvola_binary, normalize_image,
    )

    preset = PRESETS[preset_name]

    cfg = ExperimentConfig(
        name=preset_name,
        sauvola_k=preset.get("sauvola_k", 0.285),
        sauvola_window=preset.get("sauvola_window", 67),
        close_kernel=preset.get("close_kernel", 3),
        ccl_min_area=preset.get("ccl_min_area", 28),
        endpoint_mode=preset.get("endpoint_mode", "pca"),
        dedup_mode=preset.get("dedup_mode", "overlap"),
        dedup_angle=preset.get("dedup_angle", 10),
        dedup_dist=preset.get("dedup_dist", 18),
        anchor_filter_enabled=preset.get("anchor_filter_enabled", True),
        anchor_endpoint_dist=preset.get("anchor_endpoint_dist", 12.0),
        anchor_link_dist=preset.get("anchor_link_dist", 8.0),
        extraction_mode=preset.get("extraction_mode", "component"),
    )

    if "sauvola_k" in ui_params:
        cfg.sauvola_k = float(ui_params["sauvola_k"])
    if "sauvola_window" in ui_params:
        cfg.sauvola_window = int(ui_params["sauvola_window"])
    if "close_kernel" in ui_params:
        cfg.close_kernel = int(ui_params["close_kernel"])
    if "ccl_min_area" in ui_params:
        cfg.ccl_min_area = int(ui_params["ccl_min_area"])
    if "endpoint_mode" in ui_params:
        cfg.endpoint_mode = str(ui_params["endpoint_mode"])
    if "dedup_mode" in ui_params:
        cfg.dedup_mode = str(ui_params["dedup_mode"])
    if "dedup_angle" in ui_params:
        cfg.dedup_angle = float(ui_params["dedup_angle"])
    if "dedup_dist" in ui_params:
        cfg.dedup_dist = float(ui_params["dedup_dist"])
    if "anchor_filter_enabled" in ui_params:
        cfg.anchor_filter_enabled = bool(ui_params["anchor_filter_enabled"])
    if "anchor_endpoint_dist" in ui_params:
        cfg.anchor_endpoint_dist = float(ui_params["anchor_endpoint_dist"])
    if "anchor_link_dist" in ui_params:
        cfg.anchor_link_dist = float(ui_params["anchor_link_dist"])

    gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    components = []
    if image_path:
        comp_labels = deps.registry.load_component_labels(Path(image_path))
        if comp_labels:
            components = comp_labels

    if components:
        occluded = build_component_mask(gray, components, cfg.occlusion_margin)
        cropped, ox, oy = crop_to_roi(occluded, components, cfg.crop_padding)
        local_components = shift_components(components, ox, oy)
    else:
        cropped, ox, oy = gray, 0, 0
        local_components = []

    t0 = time.time()
    lines_local = detect_wires_experiment(cropped, local_components, cfg)
    elapsed_ms = (time.time() - t0) * 1000
    lines_global = [((x1 + ox, y1 + oy), (x2 + ox, y2 + oy)) for (x1, y1), (x2, y2) in lines_local]

    overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for (x1, y1), (x2, y2) in lines_global:
        cv2.line(overlay, (x1, y1), (x2, y2), (0, 0, 255), 2)

    normalized = normalize_image(cropped, cfg.normalize_mode)
    bw = sauvola_binary(normalized, cfg.sauvola_k, cfg.sauvola_window)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.close_kernel, cfg.close_kernel))
    closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)

    return {
        "line_count": len(lines_global),
        "blob_count": len(lines_global),
        "elapsed_ms": elapsed_ms,
        "overlay": _img_to_base64(overlay),
        "threshold": _img_to_base64(bw),
        "dilated": _img_to_base64(closed),
        "preset": preset_name,
        "lines": lines_global,
        "params": {
            "sauvola_k": cfg.sauvola_k,
            "sauvola_window": cfg.sauvola_window,
            "ccl_min_area": cfg.ccl_min_area,
            "endpoint_mode": cfg.endpoint_mode,
            "dedup_mode": cfg.dedup_mode,
            "anchor_filter_enabled": cfg.anchor_filter_enabled,
        },
    }


@router.post("/api/process")
async def process_image(data: dict[str, Any]):
    import asyncio
    loop = asyncio.get_event_loop()

    def _sync():
        img_idx = data.get("img_idx", 0)
        ds = data.get("ds", "gt_labels")
        params = data.get("params", {})
        preset = data.get("preset", "legacy_threshold")

        images = deps.registry.list_images(ds)
        if img_idx < 0 or img_idx >= len(images):
            return JSONResponse({"error": "index out of range"}, status_code=404)

        try:
            image = deps.cache.load_image(str(images[img_idx]))
        except FileNotFoundError:
            return JSONResponse({"error": "image not found"}, status_code=404)
        image_path = str(images[img_idx])

        if preset == "legacy_threshold":
            config = _build_legacy_config(params)
            pipeline = PipelineFactory.from_config(config)
            result = pipeline.run(image)
            overlay = pipeline.visualize(image, result)
            return JSONResponse({
                "line_count": len(result.lines),
                "blob_count": result.blob_count,
                "elapsed_ms": result.elapsed_ms,
                "overlay": _img_to_base64(overlay),
                "threshold": _img_to_base64(result.stage_outputs.get("threshold", image)),
                "close": _img_to_base64(result.stage_outputs.get("close", image)),
                "preset": preset,
            })

        if preset not in PRESETS:
            return JSONResponse({"error": f"Unknown preset: {preset}"}, status_code=400)

        try:
            pipeline_result = _run_preset_pipeline_cached(image, image_path, preset, params)
            return JSONResponse(pipeline_result)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    return await loop.run_in_executor(None, _sync)

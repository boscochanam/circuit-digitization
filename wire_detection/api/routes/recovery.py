"""Detection-recovery route — step through cumulative fixes and SEE what each recovers.

Runs the ordered recovery iterations (wire_detection/core/recovery.py) on one image
and returns, for every iteration, proxy metrics (line count, join connectivity,
ink density) plus a diff-highlighted overlay for the SELECTED iteration:

  blue  = wire kept from the compare iteration
  green = wire ADDED by this iteration   (what the fix recovered)
  red   = wire REMOVED by this iteration  (what the fix cost)

There is no wire ground-truth for the 1680 HDC images, so metrics are proxies and
the visual diff is the decision aid. Compare against the previous iteration ("prev")
or against the baseline ("baseline").
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import wire_detection.api.deps as deps
from wire_detection.api.routes.presets import PRESETS
from wire_detection.core.join_strategies import run_strategy, score_netlist
from wire_detection.core.recovery import (
    DEFAULT_ITERATION, ITERATIONS, diff_lines, get_iteration, grid_suppress, list_iterations,
)
from wire_detection.core.spice import COMPONENT_NAMES

router = APIRouter()

C_KEPT = (255, 180, 40)     # blue  (carried over)
C_ADDED = (90, 255, 120)    # green (recovered by this iteration)
C_REMOVED = (40, 90, 255)   # red   (lost by this iteration)


def _b64(image: np.ndarray) -> str:
    _, buf = cv2.imencode(".png", image)
    return base64.b64encode(buf).decode("utf-8")


def _dim(gray: np.ndarray) -> np.ndarray:
    return (cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) * 0.55 + 32).astype(np.uint8)


def _put(canvas, text, org, color, scale=0.42):
    cv2.putText(canvas, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(canvas, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def _base_cfg(preset_name: str, ui_params: dict):
    """Build the same ExperimentConfig the UI pipeline uses for this preset."""
    from wire_detection.benchmark.experiment_harness import ExperimentConfig
    p = PRESETS[preset_name]
    cfg = ExperimentConfig(
        name=preset_name,
        sauvola_k=p.get("sauvola_k", 0.285), sauvola_window=p.get("sauvola_window", 67),
        close_kernel=p.get("close_kernel", 3), ccl_min_area=p.get("ccl_min_area", 28),
        endpoint_mode=p.get("endpoint_mode", "pca"), dedup_mode=p.get("dedup_mode", "overlap"),
        dedup_angle=p.get("dedup_angle", 10), dedup_dist=p.get("dedup_dist", 18),
        anchor_filter_enabled=p.get("anchor_filter_enabled", True),
        anchor_endpoint_dist=p.get("anchor_endpoint_dist", 12.0),
        anchor_link_dist=p.get("anchor_link_dist", 8.0),
        extraction_mode=p.get("extraction_mode", "component"),
    )
    # honour the user's detection-slider overrides (same keys as process.py)
    for k in ("sauvola_k", "sauvola_window", "close_kernel", "ccl_min_area",
              "anchor_endpoint_dist", "anchor_link_dist"):
        if k in ui_params:
            setattr(cfg, k, type(getattr(cfg, k))(ui_params[k]))
    return cfg


def _detect(cropped: np.ndarray, local_components, base_preset: str, ui_params: dict, it):
    """Run one iteration: apply overrides, optional grid-suppress, detect. Returns (lines_local, ink_pct)."""
    from dataclasses import replace
    from wire_detection.benchmark.experiment_harness import (
        detect_wires_experiment, normalize_image, build_binary_masks, fuse_masks,
    )
    cfg = _base_cfg(base_preset, ui_params)
    cfg = replace(cfg, **it.overrides) if it.overrides else cfg
    img = grid_suppress(cropped) if it.grid else cropped
    normalized = normalize_image(img, cfg.normalize_mode)
    masks = build_binary_masks(normalized, cfg)
    vote = cfg.threshold_vote if cfg.threshold_fusion_enabled else 1
    fused, _ = fuse_masks(masks, vote)
    ink = float((fused > 0).mean() * 100.0)
    lines = detect_wires_experiment(img, local_components, cfg)
    return lines, ink


def _join_metrics(wires, components):
    if not wires or not components:
        return {"used": 0.0, "floating": 0, "nets": 0}
    try:
        pins, netlist = run_strategy("production", wires, components)
        m = score_netlist(wires, components, pins, netlist, 30.0)
        return {"used": m["pct_wires_used"], "floating": m["floating_components"], "nets": m["n_nets"]}
    except Exception:
        return {"used": 0.0, "floating": 0, "nets": 0}


@router.post("/api/recovery_overlay")
def recovery_overlay(data: dict[str, Any]):
    from wire_detection.benchmark.experiment_harness import (
        build_component_mask, crop_to_roi, shift_components,
    )
    img_idx = int(data.get("img_idx", 0))
    ds = data.get("ds", "gt_labels")
    preset = data.get("preset", "best_candidate_v4")
    params = data.get("params", {}) or {}
    selected = data.get("iteration", DEFAULT_ITERATION)
    compare = data.get("compare", "prev")  # "prev" | "baseline"

    images = deps.registry.list_images(ds)
    if img_idx < 0 or img_idx >= len(images):
        return JSONResponse({"error": "index out of range"}, status_code=404)
    image_path = str(images[img_idx])
    try:
        image = deps.cache.load_image(image_path)
    except FileNotFoundError:
        return JSONResponse({"error": "image not found"}, status_code=404)
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    components = deps.registry.load_component_labels(Path(image_path)) or []

    if components:
        from dataclasses import replace  # noqa
        margin, pad = 0.15, 10
        occ = build_component_mask(gray, components, margin)
        cropped, ox, oy = crop_to_roi(occ, components, pad)
        local_components = shift_components(components, ox, oy)
    else:
        cropped, ox, oy, local_components = gray, 0, 0, []

    # run every iteration once; keep local + global lines
    runs = []
    base_n = None
    for it in ITERATIONS:
        try:
            lines_local, ink = _detect(cropped, local_components, preset, params, it)
        except Exception as e:
            lines_local, ink = [], 0.0
            _ = e
        g = [((int(x1 + ox), int(y1 + oy)), (int(x2 + ox), int(y2 + oy)))
             for (x1, y1), (x2, y2) in lines_local]
        jm = _join_metrics(g, components)
        if base_n is None:
            base_n = len(g)
        runs.append({"it": it, "local": lines_local, "global": g, "ink": ink, "join": jm})

    iter_rows = []
    for r in runs:
        n = len(r["global"])
        iter_rows.append({
            "key": r["it"].key, "label": r["it"].label, "desc": r["it"].desc,
            "lines": n, "delta_base": n - base_n,
            "ink": round(r["ink"], 2), "used": r["join"]["used"],
            "floating": r["join"]["floating"], "nets": r["join"]["nets"],
        })

    # selected + compare iterations -> diff overlay (rendered in cropped/local coords)
    sel_i = next((i for i, r in enumerate(runs) if r["it"].key == selected), 0)
    cmp_i = 0 if compare == "baseline" else max(0, sel_i - 1)
    sel, cmp = runs[sel_i], runs[cmp_i]
    added, kept, removed = diff_lines(sel["local"], cmp["local"], tol=14.0)

    canvas = _dim(cropped)
    for comp in local_components:
        x1, y1, x2, y2 = comp[2]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (70, 70, 55), 1)
    for ln in kept:
        cv2.line(canvas, ln[0], ln[1], C_KEPT, 1, cv2.LINE_AA)
    for ln in removed:
        cv2.line(canvas, ln[0], ln[1], C_REMOVED, 1, cv2.LINE_AA)
        for ep in ln:
            cv2.circle(canvas, ep, 3, C_REMOVED, 1, cv2.LINE_AA)
    for ln in added:
        cv2.line(canvas, ln[0], ln[1], C_ADDED, 2, cv2.LINE_AA)
    cmp_label = "baseline" if compare == "baseline" else runs[cmp_i]["it"].key
    title = f"{sel['it'].label}  vs {cmp_label}:  +{len(added)} added  -{len(removed)} removed  ({len(kept)} kept)"
    _put(canvas, title.encode("ascii", "replace").decode().replace("?", "-"), (8, 18), (235, 235, 235), 0.44)

    return JSONResponse({
        "overlay": _b64(canvas),
        "iterations": iter_rows,
        "selected": runs[sel_i]["it"].key,
        "compare": compare,
        "compare_key": cmp_label,
        "added": len(added), "removed": len(removed), "kept": len(kept),
        "n_components": len(components),
        "warnings": ([] if components else ["No component labels for this image"])
                    + ([] if sel["global"] else ["No wires detected at this iteration"]),
    })


@router.get("/api/recovery_iterations")
def recovery_iterations():
    return JSONResponse({"iterations": list_iterations(), "default": DEFAULT_ITERATION})

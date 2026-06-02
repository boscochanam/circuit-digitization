"""Join-overlay route — image-grounded view of the node-joining for verification.

Renders the SAME join the /api/netlist route builds (discover_pins + OBB pins +
build_netlist), but draws it ON the schematic image so a human can verify each
join against real copper:

  cyan   = detected wire (the real evidence)
  green  = wire-end -> its NEAREST pin (the intended join)
  orange = wire-end -> EXTRA pins it also grabbed within range (the over-joins)
  white  = pin locations

Pass `net` to isolate one net (highlight only its pins/wires); omit for all nets.
Returns base64 PNG so the UI can show it like any image panel.
"""
from __future__ import annotations

import base64
import math
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import wire_detection.api.deps as deps
from wire_detection.api.models import JoinOverlayRequest
from wire_detection.core.netlist import (
    derive_pins_from_obb,
    discover_pins,
)
from wire_detection.core.join_strategies import (
    DEFAULT_STRATEGY,
    list_strategies,
    run_strategy,
    score_netlist,
)
from wire_detection.core.spice import COMPONENT_NAMES

router = APIRouter()

MAX_PIN_DIST = 30.0
C_WIRE = (255, 180, 40)     # cyan-blue
C_PRIMARY = (90, 255, 120)  # green
C_EXTRA = (40, 150, 255)    # orange


def _img_to_base64(image: np.ndarray) -> str:
    _, buf = cv2.imencode(".png", image)
    return base64.b64encode(buf).decode("utf-8")


def _dim(gray: np.ndarray) -> np.ndarray:
    # dim less than before so the schematic stays readable under the overlay
    canvas = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    return (canvas * 0.55 + 32).astype(np.uint8)


def _pins_near(ep, pins, max_pin_dist):
    out = [(math.hypot(ep[0] - p.x, ep[1] - p.y), p) for p in pins]
    out = [(d, p) for d, p in out if d <= max_pin_dist]
    out.sort(key=lambda x: x[0])
    return out


def _make_pins(wires, components):
    all_pins = []
    for ci, comp in enumerate(components):
        tname = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        all_pins.extend(derive_pins_from_obb(ci, comp, tname))
    clustered = discover_pins(wires, components)
    if clustered:
        ov = {(cp.component_idx, cp.pin_idx): (cp.x, cp.y) for cp in clustered}
        for p in all_pins:
            k = (p.component_idx, p.pin_idx)
            if k in ov:
                p.x, p.y = ov[k]
    return all_pins


def _put(canvas, text, org, color, scale=0.40):
    cv2.putText(canvas, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(canvas, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def _render_all(gray, wires, components, pins, netlist, max_pin_dist):
    canvas = _dim(gray)
    for comp in components:
        x1, y1, x2, y2 = comp[2]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (70, 70, 55), 1)
    nets = [n for n in netlist.nodes if len(n.pins) >= 2]
    for node in nets:
        for wi in node.wires:
            if not (0 <= wi < len(wires)):
                continue
            ep1, ep2 = wires[wi]
            cv2.line(canvas, ep1, ep2, C_WIRE, 1, cv2.LINE_AA)
            for ep in (ep1, ep2):
                for j, (_d, p) in enumerate(_pins_near(ep, node.pins, max_pin_dist)):
                    cv2.line(canvas, ep, (p.x, p.y), C_PRIMARY if j == 0 else C_EXTRA, 1, cv2.LINE_AA)
        for p in node.pins:
            cv2.circle(canvas, (p.x, p.y), 2, (220, 220, 220), -1, cv2.LINE_AA)
    _put(canvas, f"{len(nets)} nets | cyan=wire green=nearest-pin orange=extra(over-join)", (8, 16), (230, 230, 230))
    return canvas


def _render_one(gray, wires, components, pins, netlist, node, max_pin_dist, rank, total):
    canvas = _dim(gray)
    for comp in components:
        x1, y1, x2, y2 = comp[2]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (70, 70, 55), 1)
    for ep1, ep2 in wires:
        cv2.line(canvas, ep1, ep2, (60, 60, 60), 1, cv2.LINE_AA)
    extra = 0
    for wi in node.wires:
        if not (0 <= wi < len(wires)):
            continue
        ep1, ep2 = wires[wi]
        cv2.line(canvas, ep1, ep2, C_WIRE, 2, cv2.LINE_AA)
        for ep in (ep1, ep2):
            cv2.circle(canvas, ep, 3, C_WIRE, -1, cv2.LINE_AA)
            for j, (_d, p) in enumerate(_pins_near(ep, node.pins, max_pin_dist)):
                cv2.line(canvas, ep, (p.x, p.y), C_PRIMARY if j == 0 else C_EXTRA, 2 if j == 0 else 1, cv2.LINE_AA)
                if j > 0:
                    extra += 1
    comp_types = {}
    for p in node.pins:
        comp = components[p.component_idx]
        tn = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        comp_types[tn] = comp_types.get(tn, 0) + 1
        x1, y1, x2, y2 = comp[2]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), C_PRIMARY, 2)
        cv2.circle(canvas, (p.x, p.y), 6, C_PRIMARY, -1, cv2.LINE_AA)
        cv2.circle(canvas, (p.x, p.y), 6, (20, 20, 20), 1, cv2.LINE_AA)
        _put(canvas, f"{tn[:8]}.{p.pin_name}", (p.x + 7, p.y), C_PRIMARY, 0.42)
    ncomp = len({p.component_idx for p in node.pins})
    types_str = ", ".join(f"{k}x{v}" for k, v in sorted(comp_types.items()))
    _put(canvas, f"net N{node.node_id} ({rank}/{total})  {len(node.pins)} pins on {ncomp} components  {len(node.wires)} wires",
         (8, 16), (90, 160, 255) if ncomp > 3 else (230, 230, 230), 0.38)
    _put(canvas, f"types: {types_str[:90]}", (8, 33), (210, 210, 210), 0.36)
    _put(canvas, f"orange over-joins: {extra}", (8, 50), C_EXTRA if extra else (210, 210, 210), 0.36)
    return canvas


def _net_summaries(netlist):
    nets = sorted((n for n in netlist.nodes if len(n.pins) >= 2),
                  key=lambda n: len({p.component_idx for p in n.pins}), reverse=True)
    return [
        {"net_id": n.node_id, "pins": len(n.pins),
         "components": len({p.component_idx for p in n.pins}), "wires": len(n.wires)}
        for n in nets
    ], nets


@router.post("/api/join_overlay")
async def join_overlay(data: JoinOverlayRequest):
    import asyncio
    def _sync():
        from wire_detection.api.routes.process import _run_preset_pipeline_cached

        images = deps.registry.list_images(data.ds)
        if data.img_idx < 0 or data.img_idx >= len(images):
            return JSONResponse({"error": "index out of range"}, status_code=404)
        image_path = str(images[data.img_idx])
        try:
            image = deps.cache.load_image(image_path)
        except FileNotFoundError:
            return JSONResponse({"error": "image not found"}, status_code=404)
        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        components = deps.registry.load_component_labels(Path(image_path)) or []
        result = _run_preset_pipeline_cached(gray, image_path, data.preset, data.params or {})
        wires = [((int(a[0]), int(a[1])), (int(b[0]), int(b[1]))) for a, b in result.get("lines", [])]

        warnings = []
        if not components:
            warnings.append("No component labels for this image")
        if not wires:
            warnings.append("No wires detected")

        max_pin_dist = float(data.max_pin_dist or MAX_PIN_DIST)
        strategy = data.strategy or DEFAULT_STRATEGY
        if not components or not wires:
            canvas = _dim(gray)
            _put(canvas, "  ".join(warnings) or "nothing to render", (8, 16), (90, 160, 255))
            return JSONResponse({"overlay": _img_to_base64(canvas), "nets": [],
                                 "metrics": None, "strategy": strategy, "warnings": warnings})

        pins, netlist = run_strategy(strategy, wires, components)
        metrics = score_netlist(wires, components, pins, netlist, max_pin_dist)
        summaries, nets = _net_summaries(netlist)

        if data.net is not None:
            match = next(((i, n) for i, n in enumerate(nets) if n.node_id == data.net), None)
            if match is None:
                return JSONResponse({"error": f"net {data.net} not found"}, status_code=404)
            rank, node = match
            canvas = _render_one(gray, wires, components, pins, netlist, node, max_pin_dist, rank + 1, len(nets))
        else:
            canvas = _render_all(gray, wires, components, pins, netlist, max_pin_dist)

        return JSONResponse({
            "overlay": _img_to_base64(canvas),
            "nets": summaries,
            "metrics": metrics,
            "strategy": strategy,
            "warnings": warnings,
        })

    return await asyncio.get_event_loop().run_in_executor(None, _sync)


@router.get("/api/join_strategies")
def join_strategies():
    return JSONResponse({"strategies": list_strategies(), "default": DEFAULT_STRATEGY})

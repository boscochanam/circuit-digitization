"""Topology route — structured JSON for interactive wire/component visualization.

Returns the same join data that /api/netlist and /api/join_overlay use, but as
structured JSON instead of SPICE text or a rendered PNG. The response contains:
  - wires:      detected wires with their node assignment
  - pins:       component pin locations with node assignment
  - components: component metadata with which nodes they touch
  - nodes:      aggregated node summaries (wire/pin/component counts)
  - warnings:   any pipeline or label issues

This lets the frontend render its own interactive topology graph.
"""
from __future__ import annotations

from pathlib import Path

import cv2
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import wire_detection.api.deps as deps
from wire_detection.api.models import JoinOverlayRequest
from wire_detection.core.join_strategies import DEFAULT_STRATEGY, run_strategy
from wire_detection.core.spice import COMPONENT_NAMES

router = APIRouter()


def _build_topology_data(
    img_idx: int,
    ds: str,
    preset: str,
    params_overrides: dict | None = None,
    strategy: str | None = None,
) -> dict:
    """Build topology data — wires, pins, components, nodes — using the same
    pipeline and join strategy as /api/netlist and /api/join_overlay."""
    images = deps.registry.list_images(ds)
    if img_idx < 0 or img_idx >= len(images):
        return {"error": "index out of range"}

    try:
        image = deps.cache.load_image(str(images[img_idx]))
    except FileNotFoundError:
        return {"error": "image not found"}

    image_path = str(images[img_idx])
    gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    components_raw = deps.registry.load_component_labels(
        Path(image_path), img_wh=(image.shape[1], image.shape[0])
    ) or []

    from wire_detection.api.routes.process import _run_preset_pipeline_cached

    pipeline_result = _run_preset_pipeline_cached(
        gray, image_path, preset, params_overrides or {}
    )

    warnings: list[str] = []
    if not components_raw:
        warnings.append("No component labels found for this image")
    if pipeline_result["line_count"] == 0:
        warnings.append("No wires detected in this image")

    wires = [((int(a[0]), int(a[1])), (int(b[0]), int(b[1])))
             for a, b in pipeline_result.get("lines", [])]

    if not components_raw or not wires:
        return {
            "wires": [],
            "pins": [],
            "components": [],
            "nodes": [],
            "warnings": warnings,
        }

    # Run the join strategy — same as /api/netlist and /api/join_overlay
    used_strategy = strategy or DEFAULT_STRATEGY
    all_pins, netlist = run_strategy(used_strategy, wires, components_raw)

    # ── Build wire→node lookup ──
    # For each wire index, find which node it belongs to.
    wire_to_node: dict[int, int] = {}
    for node in netlist.nodes:
        for wi in node.wires:
            wire_to_node[wi] = node.node_id

    topo_wires = []
    for wi, (ep1, ep2) in enumerate(wires):
        topo_wires.append({
            "idx": wi,
            "ep1": list(ep1),
            "ep2": list(ep2),
            "node_id": wire_to_node.get(wi),
        })

    # ── Build pin list ──
    topo_pins = []
    for p in all_pins:
        key = (p.component_idx, p.pin_name)
        node_id = netlist.pin_to_node.get(key)
        comp = components_raw[p.component_idx]
        comp_type = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        prefix = _get_prefix(comp_type) or "X"
        topo_pins.append({
            "x": p.x,
            "y": p.y,
            "component_idx": p.component_idx,
            "component_name": f"{prefix}{p.component_idx + 1}",
            "pin_name": p.pin_name,
            "node_id": node_id,
        })

    # ── Build component list with node_ids ──
    # Each component collects the unique node_ids from its pins.
    comp_node_ids: dict[int, set[int]] = {}
    for p in all_pins:
        key = (p.component_idx, p.pin_name)
        node_id = netlist.pin_to_node.get(key)
        if node_id is not None:
            comp_node_ids.setdefault(p.component_idx, set()).add(node_id)

    topo_components = []
    for ci, comp in enumerate(components_raw):
        cls_id = comp[0]
        type_name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
        prefix = _get_prefix(type_name) or "X"
        x1, y1, x2, y2 = comp[2]
        topo_components.append({
            "idx": ci,
            "name": f"{prefix}{ci + 1}",
            "type": type_name,
            "bbox": [x1, y1, x2, y2],
            "node_ids": sorted(comp_node_ids.get(ci, set())),
        })

    # ── Build node summaries ──
    topo_nodes = []
    for node in netlist.nodes:
        pin_component_idxs = {p.component_idx for p in node.pins}
        topo_nodes.append({
            "node_id": node.node_id,
            "wire_count": len(node.wires),
            "pin_count": len(node.pins),
            "component_count": len(pin_component_idxs),
        })

    return {
        "wires": topo_wires,
        "pins": topo_pins,
        "components": topo_components,
        "nodes": topo_nodes,
        "warnings": warnings,
    }


def _get_prefix(type_name: str) -> str | None:
    """Get SPICE prefix for a component type (e.g. 'R' for resistor)."""
    from wire_detection.core.component_classes import PREFIX_MAP
    return PREFIX_MAP.get(type_name)


@router.post("/api/topology")
async def topology(data: JoinOverlayRequest):
    import asyncio

    def _sync():
        result = _build_topology_data(
            img_idx=data.img_idx,
            ds=data.ds,
            preset=data.preset,
            params_overrides=data.params,
            strategy=data.strategy,
        )
        if "error" in result:
            return JSONResponse({"error": result["error"]}, status_code=404)
        return JSONResponse(result)

    return await asyncio.get_event_loop().run_in_executor(None, _sync)

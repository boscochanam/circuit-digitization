"""Netlist generation API route."""
from __future__ import annotations

from pathlib import Path

import cv2
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import wire_detection.api.deps as deps
from wire_detection.api.models import NetlistRequest
from wire_detection.api.routes.process import _run_preset_pipeline
from wire_detection.core.netlist import (
    build_netlist,
    derive_pins_from_obb,
)
from wire_detection.core.spice import COMPONENT_NAMES, SpiceGenerator

router = APIRouter()


def _build_netlist_response(
    img_idx: int,
    ds: str,
    preset: str,
) -> dict:
    images = deps.registry.list_images(ds)
    if img_idx < 0 or img_idx >= len(images):
        return {"error": "index out of range"}

    try:
        image = deps.cache.load_image(str(images[img_idx]))
    except FileNotFoundError:
        return {"error": "image not found"}

    image_path = str(images[img_idx])
    gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    components_raw = deps.registry.load_component_labels(Path(image_path)) or []

    pipeline_result = _run_preset_pipeline(
        gray, preset, {}, image_path=image_path
    )

    warnings: list[str] = []
    if not components_raw:
        warnings.append("No component labels found for this image")
    if pipeline_result["line_count"] == 0:
        warnings.append("No wires detected in this image")

    wires = pipeline_result.get("lines", [])

    if not components_raw:
        gen = SpiceGenerator()
        return {
            "nodes": [],
            "components": [],
            "connections": [],
            "spice_netlist": gen.generate([]),
            "warnings": warnings,
        }

    pins = []
    for ci, comp in enumerate(components_raw):
        cls_id = comp[0]
        type_name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
        comp_pins = derive_pins_from_obb(ci, comp, type_name)
        pins.extend(comp_pins)

    netlist = build_netlist(wires, components_raw, pins, max_pin_dist=30)

    gen = SpiceGenerator()
    spice_text = gen.generate(components_raw, netlist)

    response_nodes = []
    for node in netlist.nodes:
        pin_list = []
        for pin in node.pins:
            pin_list.append({
                "component": f"comp_{pin.component_idx}",
                "pin": pin.pin_name,
            })
        response_nodes.append({
            "id": node.node_id,
            "pins": pin_list,
        })

    response_components = []
    for ci, comp in enumerate(components_raw):
        cls_id = comp[0]
        type_name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
        prefix = gen._get_prefix(type_name) or "X"
        comp_pins = derive_pins_from_obb(ci, comp, type_name)
        response_components.append({
            "name": f"{prefix}{ci + 1}",
            "type": type_name,
            "pins": [p.pin_name for p in comp_pins],
        })

    connections = _build_connections(netlist, wires)

    return {
        "nodes": response_nodes,
        "components": response_components,
        "connections": connections,
        "spice_netlist": spice_text,
        "warnings": warnings,
    }


def _build_connections(netlist, wires):
    wire_to_comp_pins: dict[int, list[tuple[int, str]]] = {}
    for node in netlist.nodes:
        for wi in node.wires:
            if wi not in wire_to_comp_pins:
                wire_to_comp_pins[wi] = []
            for pin in node.pins:
                wire_to_comp_pins[wi].append((pin.component_idx, pin.pin_name))

    connections = []
    for wi, pins_list in wire_to_comp_pins.items():
        for i in range(len(pins_list)):
            for j in range(i + 1, len(pins_list)):
                connections.append({
                    "from": {"component": f"comp_{pins_list[i][0]}", "pin": pins_list[i][1]},
                    "to": {"component": f"comp_{pins_list[j][0]}", "pin": pins_list[j][1]},
                    "wire_idx": wi,
                })
    return connections


@router.post("/api/netlist")
def get_netlist(data: NetlistRequest):
    result = _build_netlist_response(
        img_idx=data.img_idx,
        ds=data.ds,
        preset=data.preset,
    )
    if "error" in result:
        return JSONResponse({"error": result["error"]}, status_code=404)
    return JSONResponse(result)

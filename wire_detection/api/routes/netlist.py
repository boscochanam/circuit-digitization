"""Netlist generation and simulation API routes."""
from __future__ import annotations

from pathlib import Path

import cv2
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import wire_detection.api.deps as deps
from wire_detection.api.models import NetlistRequest, SimulateRequest
from wire_detection.core.netlist import (
    build_netlist,
    derive_pins_from_obb,
    discover_pins,
)
from wire_detection.core.spice import COMPONENT_NAMES, SpiceGenerator
from wire_detection.core.simulator import SpiceSimulator

router = APIRouter()


def _run_preset_pipeline(gray, preset, params_overrides, image_path=None):
    """Run pipeline using cached preset config."""
    from wire_detection.api.routes.process import _run_preset_pipeline_cached
    return _run_preset_pipeline_cached(gray, image_path or "", preset, params_overrides or {})


def _build_netlist_data(
    img_idx: int,
    ds: str,
    preset: str,
    params_overrides: dict | None = None,
) -> dict:
    """Build netlist data using endpoint clustering pin discovery."""
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
        gray, preset, params_overrides or {}, image_path=image_path
    )

    warnings: list[str] = []
    if not components_raw:
        warnings.append("No component labels found for this image")
    if pipeline_result["line_count"] == 0:
        warnings.append("No wires detected in this image")

    wires = pipeline_result.get("lines", [])

    gen = SpiceGenerator()

    if not components_raw:
        return {
            "nodes": [],
            "components": [],
            "connections": [],
            "spice_netlist": gen.generate([]),
            "warnings": warnings,
        }

    # Step 1: Derive OBB pins for ALL components (junctions, terminals, transformer, etc.)
    all_pins = []
    for ci, comp in enumerate(components_raw):
        cls_id = comp[0]
        type_name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
        comp_pins = derive_pins_from_obb(ci, comp, type_name)
        all_pins.extend(comp_pins)

    # Step 2: Get wire-guided positions for SPICE-active components
    clustered_pins = discover_pins(wires, components_raw)

    # Step 3: Override OBB pin positions with wire-guided positions where available
    if clustered_pins:
        pin_overrides: dict[tuple[int, int], tuple[int, int]] = {}
        for cp in clustered_pins:
            pin_overrides[(cp.component_idx, cp.pin_idx)] = (cp.x, cp.y)
        for pin in all_pins:
            key = (pin.component_idx, pin.pin_idx)
            if key in pin_overrides:
                pin.x, pin.y = pin_overrides[key]

    # Step 4: Build netlist with ALL pins
    netlist = build_netlist(wires, components_raw, all_pins, max_pin_dist=30)
    spice_text = gen.generate(components_raw, netlist)

    # Step 5: Build response — one entry per component with node assignments
    response_nodes: dict[int, dict] = {}
    response_components = []

    for ci, comp in enumerate(components_raw):
        cls_id = comp[0]
        type_name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
        prefix = gen._get_prefix(type_name) or "X"
        comp_pins = [p for p in all_pins if p.component_idx == ci]
        if comp_pins:
            pin_info = []
            for p in comp_pins:
                key = (p.component_idx, p.pin_name)
                node_id = netlist.pin_to_node.get(key)
                if node_id is not None:
                    response_nodes.setdefault(node_id, {"id": node_id, "pins": []})
                    response_nodes[node_id]["pins"].append({
                        "component": f"{prefix}{ci + 1}",
                        "pin": p.pin_name,
                    })
                pin_info.append(f"pin{p.pin_idx} ({p.x},{p.y})")
            response_components.append({
                "name": f"{prefix}{ci + 1}",
                "type": type_name,
                "pins": pin_info,
                "position": {
                    "x": (comp[2][0] + comp[2][2]) // 2,
                    "y": (comp[2][1] + comp[2][3]) // 2,
                },
            })

    return {
        "nodes": list(response_nodes.values()),
        "components": response_components,
        "connections": [],
        "spice_netlist": spice_text,
        "warnings": warnings,
    }


@router.post("/api/netlist")
async def get_netlist(data: NetlistRequest):
    import asyncio
    def _sync():
        result = _build_netlist_data(
            img_idx=data.img_idx,
            ds=data.ds,
            preset=data.preset,
            params_overrides=data.params,
        )
        if "error" in result:
            return JSONResponse({"error": result["error"]}, status_code=404)
        return JSONResponse(result)
    return await asyncio.get_event_loop().run_in_executor(None, _sync)


@router.post("/api/simulate")
def run_simulation(data: SimulateRequest):
    """Run ngspice DC operating point simulation on provided SPICE netlist."""
    sim = SpiceSimulator()
    if not sim.is_available():
        return JSONResponse({
            "success": False,
            "error": "ngspice not installed on server",
        })

    result = sim.run_dc_analysis(data.spice_text)

    if "error" in result:
        return JSONResponse({
            "success": False,
            "error": result["error"],
            "raw_output": result.get("raw_output", ""),
        })

    voltages = [{"node": k, "voltage": v} for k, v in result.get("voltages", {}).items()]
    currents = [{"source": k, "current": v} for k, v in result.get("currents", {}).items()
                if "#branch" in k]

    return JSONResponse({
        "success": True,
        "node_voltages": voltages,
        "branch_currents": currents,
    })

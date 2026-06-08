"""Netlist generation and simulation API routes."""
from __future__ import annotations

from pathlib import Path

import cv2
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import wire_detection.api.deps as deps
from wire_detection.api.models import NetlistRequest, SimulateRequest
from wire_detection.core.join_strategies import run_strategy, DEFAULT_STRATEGY
from wire_detection.core.connection_overrides import load_overrides, apply_overrides_to_netlist, wires_with_removes
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
    component_values: dict[str, str] | None = None,
    strategy: str | None = None,
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

    components_raw = deps.registry.load_component_labels(
        Path(image_path), img_wh=(image.shape[1], image.shape[0])) or []

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

    # Build the netlist with the default join strategy (the endpoint-graph join —
    # see core/join_graph.py / docs/join-verification.md). run_strategy builds the
    # pins (derive_pins_from_obb for all components + discover_pins overrides, or
    # junction-aware pins) and applies wire extension EXACTLY as the Join Check /
    # Voltage Map routes do — so the netlist, topology graph and SPICE match those
    # views for ANY DEFAULT_STRATEGY, not only standard-pin ones.
    # Connection-editor overrides: disconnect (remove) is applied to the wires
    # BEFORE the join so the net actually splits; reassign/join are applied AFTER
    # as node merges. Together the netlist/voltage/current sims reflect manual
    # wire->component edits, not just the topology view.
    _overrides = load_overrides(ds, img_idx)
    wires = wires_with_removes(wires, _overrides)
    all_pins, netlist = run_strategy(strategy or DEFAULT_STRATEGY, wires, components_raw)
    netlist = apply_overrides_to_netlist(netlist, components_raw, _overrides)
    spice_text = gen.generate(components_raw, netlist, value_overrides=component_values)

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
            component_values=data.component_values,
            strategy=data.strategy,
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

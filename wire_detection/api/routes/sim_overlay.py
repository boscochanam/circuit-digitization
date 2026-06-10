"""Voltage-map route — visualize the SPICE nodal-analysis result ON the schematic.

Pipeline: chosen join strategy → netlist → SPICE → ngspice DC operating point.
Then each electrical net is coloured by its computed node voltage (jet heatmap)
and labelled on the image. Turns the simulation table into a picture.

Caveat: component values are generator defaults (R=1k, V=5V, …), so the voltages
are a valid DC solution of the *extracted topology*, not the real circuit's
numbers; and they're only as correct as the join.
"""
from __future__ import annotations

import base64
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import wire_detection.api.deps as deps
from wire_detection.api.models import SimOverlayRequest
from wire_detection.core.join_strategies import run_strategy
from wire_detection.core.connection_overrides import load_overrides, apply_overrides_to_netlist, wires_with_removes
from wire_detection.core.spice import SpiceGenerator
from wire_detection.core.simulator import SpiceSimulator

router = APIRouter()


def _b64(img):
    _, buf = cv2.imencode(".png", img)
    return base64.b64encode(buf).decode("utf-8")


def _dim(gray):
    return (cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) * 0.5 + 30).astype(np.uint8)


def _put(c, t, org, color, s=0.42):
    cv2.putText(c, t, org, cv2.FONT_HERSHEY_SIMPLEX, s, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(c, t, org, cv2.FONT_HERSHEY_SIMPLEX, s, color, 1, cv2.LINE_AA)


def _volt_color(v, vmin, vmax):
    t = 0.0 if vmax <= vmin else (v - vmin) / (vmax - vmin)
    t = max(0.0, min(1.0, t))
    bgr = cv2.applyColorMap(np.array([[int(t * 255)]], np.uint8), cv2.COLORMAP_JET)[0, 0]
    return (int(bgr[0]), int(bgr[1]), int(bgr[2]))


def _err_overlay(gray, msg, color=(90, 160, 255)):
    c = _dim(gray)
    _put(c, msg[:70], (8, 18), color)
    return c


@router.post("/api/sim_overlay")
async def sim_overlay(data: SimOverlayRequest):
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

        components = deps.registry.load_component_labels(
            Path(image_path), img_wh=(gray.shape[1], gray.shape[0])) or []
        res = _run_preset_pipeline_cached(gray, image_path, data.preset, data.params or {})
        wires = [((int(a[0]), int(a[1])), (int(b[0]), int(b[1]))) for a, b in res.get("lines", [])]

        warnings = []
        if not components:
            warnings.append("No component labels")
        if not wires:
            warnings.append("No wires detected")
        if not components or not wires:
            return JSONResponse({"overlay": _b64(_err_overlay(gray, "  ".join(warnings))),
                                 "available": False, "node_voltages": [], "warnings": warnings})

        strategy = data.strategy or "production"
        _overrides = load_overrides(data.ds, data.img_idx)
        wires = wires_with_removes(wires, _overrides)
        pins, netlist = run_strategy(strategy, wires, components)
        netlist = apply_overrides_to_netlist(netlist, components, _overrides)
        gen = SpiceGenerator()
        spice = gen.generate(components, netlist, value_overrides=data.component_values)
        gnd_id = gen._find_gnd_node(components, netlist)

        sim = SpiceSimulator()
        if not sim.is_available():
            return JSONResponse({"overlay": _b64(_err_overlay(gray, "ngspice not installed — cannot compute voltages")),
                                 "available": False, "node_voltages": [], "warnings": ["ngspice not installed"],
                                 "spice_netlist": spice})
        result = sim.run_dc_analysis(spice)
        if "error" in result or "voltages" not in result:
            return JSONResponse({"overlay": _b64(_err_overlay(gray, "simulation failed: " + str(result.get("error", "")), (255, 120, 120))),
                                 "available": False, "node_voltages": [],
                                 "warnings": [result.get("error", "sim failed")], "spice_netlist": spice})

        volts = {k.lower(): v for k, v in result["voltages"].items()}
        volts.setdefault("0", 0.0)

        # net node_id -> voltage (gnd net -> "0", others -> "n{id}")
        net_volt = {}
        for n in netlist.nodes:
            key = "0" if (gnd_id is not None and n.node_id == gnd_id) else f"n{n.node_id}"
            if key in volts:
                net_volt[n.node_id] = volts[key]
        vals = list(net_volt.values())
        vmin = min(vals) if vals else 0.0
        vmax = max(vals) if vals else 0.0

        canvas = _dim(gray)
        for comp in components:
            x1, y1, x2, y2 = comp[2]
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (70, 70, 55), 1)
        GREY = (120, 120, 120)
        for n in netlist.nodes:
            if not n.pins:
                continue
            v = net_volt.get(n.node_id)
            col = _volt_color(v, vmin, vmax) if v is not None else GREY
            for wi in n.wires:
                if 0 <= wi < len(wires):
                    cv2.line(canvas, wires[wi][0], wires[wi][1], col, 2, cv2.LINE_AA)
            for p in n.pins:
                cv2.circle(canvas, (p.x, p.y), 4, col, -1, cv2.LINE_AA)
                cv2.circle(canvas, (p.x, p.y), 4, (15, 15, 15), 1, cv2.LINE_AA)
            if v is not None and len(n.pins) >= 2:
                cx = int(sum(p.x for p in n.pins) / len(n.pins))
                cy = int(sum(p.y for p in n.pins) / len(n.pins))
                _put(canvas, f"{v:.2f}V", (cx + 4, cy - 4), col)

        # header + colorbar
        _put(canvas, f"DC node voltages  {vmin:.2f}V .. {vmax:.2f}V   [{strategy}]  grey = not solved",
             (8, 16), (235, 235, 235), 0.40)
        bx, by, bw = 8, 24, 140
        for i in range(bw):
            bgr = cv2.applyColorMap(np.array([[int(i / bw * 255)]], np.uint8), cv2.COLORMAP_JET)[0, 0]
            cv2.line(canvas, (bx + i, by), (bx + i, by + 8), (int(bgr[0]), int(bgr[1]), int(bgr[2])), 1)
        cv2.rectangle(canvas, (bx, by), (bx + bw, by + 8), (200, 200, 200), 1)

        node_voltages = [{"node": f"N{nid}", "voltage": round(v, 4)} for nid, v in sorted(net_volt.items())]
        currents = [{"source": k, "current": round(val, 6)}
                    for k, val in result.get("currents", {}).items() if "#branch" in k]
        return JSONResponse({
            "overlay": _b64(canvas), "available": True,
            "node_voltages": node_voltages, "branch_currents": currents,
            "vmin": round(vmin, 3), "vmax": round(vmax, 3),
            "n_solved": len(net_volt),
            "n_nets": sum(1 for n in netlist.nodes if len(n.pins) >= 2),
            "strategy": strategy, "warnings": warnings, "spice_netlist": spice,
        })

    return await asyncio.get_event_loop().run_in_executor(None, _sync)

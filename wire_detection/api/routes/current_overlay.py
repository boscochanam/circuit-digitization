"""Current-map route — visualize per-component currents ON the schematic.

Pipeline: same as sim_overlay (join → netlist → SPICE → ngspice DC op).
Then compute current through each component from node voltages + component
values using Ohm's law, and draw a HOT-colormap overlay where components and
wires are coloured by current magnitude (black → red → yellow → white).

Current computation:
- Resistors (R): I = |V_anode - V_cathode| / R
- Capacitors (C): DC steady state → I ≈ 0
- Inductors (L): DC steady state → I = |V_anode - V_cathode| / R_series
- Voltage sources (V): branch current from ngspice
- Diodes (D): branch current from ngspice if available
- Other: grey (no simple calculation)

Wires inherit the max current of the components they connect to.
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
from wire_detection.core.spice import SpiceGenerator
from wire_detection.core.simulator import SpiceSimulator
from wire_detection.core.component_classes import PREFIX_MAP, COMPONENT_TYPES

router = APIRouter()


def _b64(img):
    _, buf = cv2.imencode(".png", img)
    return base64.b64encode(buf).decode("utf-8")


def _dim(gray):
    return (cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) * 0.5 + 30).astype(np.uint8)


def _put(c, t, org, color, s=0.42):
    cv2.putText(c, t, org, cv2.FONT_HERSHEY_SIMPLEX, s, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(c, t, org, cv2.FONT_HERSHEY_SIMPLEX, s, color, 1, cv2.LINE_AA)


def _current_color(i, imin, imax):
    """Map current magnitude to HOT colormap (black→red→yellow→white)."""
    if imax <= imin:
        t = 0.0
    else:
        t = (i - imin) / (imax - imin)
    t = max(0.0, min(1.0, t))
    bgr = cv2.applyColorMap(
        np.array([[int(t * 255)]], np.uint8), cv2.COLORMAP_HOT
    )[0, 0]
    return (int(bgr[0]), int(bgr[1]), int(bgr[2]))


def _parse_spice_value(raw: str) -> float | None:
    """Parse a SPICE value string like '1000', '10k', '4.7u', '1e-6' to float."""
    s = raw.strip().lower()
    if not s:
        return None
    _SI = {"t": 1e12, "g": 1e9, "meg": 1e6, "m": 1e-3,
           "k": 1e3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
    for suffix, mult in sorted(_SI.items(), key=lambda x: -len(x[0])):
        if s.endswith(suffix):
            try:
                return float(s[: -len(suffix)]) * mult
            except ValueError:
                pass
    try:
        return float(s)
    except ValueError:
        return None


def _err_overlay(gray, msg, color=(90, 160, 255)):
    c = _dim(gray)
    _put(c, msg[:70], (8, 18), color)
    return c


def _build_component_names(components):
    """Build component index → SPICE name mapping (mirrors SpiceGenerator naming).

    Components are tuples: (class_id, polygon_vertices, bbox).
    Returns dict: component_index -> spice_name (e.g., {0: "R1", 1: "C1", ...}).
    """
    prefix_counters: dict[str, int] = {}
    names: dict[int, str] = {}
    for i, comp in enumerate(components):
        cls_id = comp[0]
        type_name = COMPONENT_TYPES.get(cls_id, f"cls_{cls_id}")
        prefix = PREFIX_MAP.get(type_name)
        if prefix is None:
            continue
        prefix_counters[prefix] = prefix_counters.get(prefix, 0) + 1
        names[i] = f"{prefix}{prefix_counters[prefix]}"
    return names


def _compute_component_currents(components, netlist, volts, spice_text, result):
    """Compute per-component current from node voltages and SPICE data.

    Returns dict: component_name -> current (amps).
    """
    import re

    comp_currents: dict[str, float] = {}

    # Build component index → SPICE name mapping
    comp_names = _build_component_names(components)
    # Reverse: spice_name → index
    name_to_idx = {v: k for k, v in comp_names.items()}

    # Build comp_name → net_ids mapping from netlist
    # pin.component_idx is the index into the components list;
    # comp_names maps index → SPICE name (e.g. "R3")
    comp_nets: dict[str, list[int]] = {}
    for node in netlist.nodes:
        for pin in node.pins:
            spice_name = comp_names.get(pin.component_idx)
            if spice_name:
                comp_nets.setdefault(spice_name, []).append(node.node_id)

    # Extract component values from SPICE netlist
    # Lines like: R1 n1 n2 1000  or  V1 n1 0 DC 5
    comp_values: dict[str, float] = {}
    for line in spice_text.split("\n"):
        line = line.strip()
        if not line or line.startswith(".") or line.startswith("*"):
            continue
        m = re.match(r"^([RCVL])(\d+)\s+\S+\s+\S+\s+([\d.eE+\-kmunpf]+)", line)
        if m:
            prefix, idx, val_str = m.group(1), m.group(2), m.group(3)
            name = f"{prefix}{idx}"
            val = _parse_spice_value(val_str)
            if val is not None:
                comp_values[name] = val

    # Also try to get branch currents from ngspice result
    branch_currents = result.get("currents", {})

    for i, comp in enumerate(components):
        cls_id = comp[0]
        comp_name = comp_names.get(i)
        if comp_name is None:
            continue
        prefix = comp_name[0]

        # Find which nets this component connects to
        net_ids = comp_nets.get(comp_name, [])
        if len(net_ids) < 2:
            # Need at least 2 pins to compute current
            comp_currents[comp_name] = 0.0
            continue

        # Get voltages at each pin's net
        node_voltages = []
        for nid in net_ids[:2]:  # Take first two pins (anode/cathode)
            key = f"n{nid}" if nid != 0 else "0"
            v = volts.get(key, volts.get(str(nid), 0.0))
            node_voltages.append(v)

        v_diff = abs(node_voltages[0] - node_voltages[1])

        if prefix == "R":
            # Resistor: I = V / R
            r_val = comp_values.get(comp_name, 1000.0)
            current = v_diff / r_val if r_val > 0 else 0.0
        elif prefix == "C":
            # Capacitor: DC steady state → I ≈ 0
            current = 0.0
        elif prefix == "L":
            # Inductor: DC steady state → I = V / R_series (small R)
            l_val = comp_values.get(comp_name, 0.001)
            r_series = 0.01  # Small series resistance
            current = v_diff / r_series if r_series > 0 else 0.0
        elif prefix == "V":
            # Voltage source: use branch current from ngspice
            branch_key = f"{comp_name.lower()}#branch"
            current = abs(branch_currents.get(branch_key, 0.0))
        elif prefix == "D":
            # Diode: try branch current, else estimate
            branch_key = f"{comp_name.lower()}#branch"
            current = abs(branch_currents.get(branch_key, 0.0))
        else:
            # Other components: grey (zero current)
            current = 0.0

        comp_currents[comp_name] = current

    return comp_currents


@router.post("/api/current_overlay")
async def current_overlay(data: SimOverlayRequest):
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
            Path(image_path), img_wh=(gray.shape[1], gray.shape[0])
        ) or []
        res = _run_preset_pipeline_cached(gray, image_path, data.preset, data.params or {})
        wires = [
            ((int(a[0]), int(a[1])), (int(b[0]), int(b[1])))
            for a, b in res.get("lines", [])
        ]

        warnings = []
        if not components:
            warnings.append("No component labels")
        if not wires:
            warnings.append("No wires detected")
        if not components or not wires:
            return JSONResponse(
                {
                    "overlay": _b64(_err_overlay(gray, "  ".join(warnings))),
                    "available": False,
                    "component_currents": [],
                    "warnings": warnings,
                }
            )

        strategy = data.strategy or "production"
        pins, netlist = run_strategy(strategy, wires, components)
        gen = SpiceGenerator()
        spice = gen.generate(components, netlist, value_overrides=data.component_values)

        sim = SpiceSimulator()
        if not sim.is_available():
            return JSONResponse(
                {
                    "overlay": _b64(_err_overlay(gray, "ngspice not installed — cannot compute currents")),
                    "available": False,
                    "component_currents": [],
                    "warnings": ["ngspice not installed"],
                    "spice_netlist": spice,
                }
            )
        result = sim.run_dc_analysis(spice)
        if "error" in result or "voltages" not in result:
            return JSONResponse(
                {
                    "overlay": _b64(
                        _err_overlay(
                            gray,
                            "simulation failed: " + str(result.get("error", "")),
                            (255, 120, 120),
                        )
                    ),
                    "available": False,
                    "component_currents": [],
                    "warnings": [result.get("error", "sim failed")],
                    "spice_netlist": spice,
                }
            )

        volts = {k.lower(): v for k, v in result["voltages"].items()}
        volts.setdefault("0", 0.0)

        # Compute per-component currents
        comp_currents = _compute_component_currents(
            components, netlist, volts, spice, result
        )

        # Find current range
        i_vals = [abs(v) for v in comp_currents.values() if v > 0]
        imin = 0.0
        imax = max(i_vals) if i_vals else 1.0

        # Build wire → current mapping (wire inherits max current of connected components)
        wire_currents: dict[int, float] = {}
        # Build component names for drawing + wire mapping
        comp_names = _build_component_names(components)
        for node in netlist.nodes:
            # Find components connected to this node (by SPICE name)
            connected_comps = [comp_names.get(p.component_idx) for p in node.pins]
            max_i = 0.0
            for cn in connected_comps:
                if cn:
                    max_i = max(max_i, abs(comp_currents.get(cn, 0.0)))
            for wi in node.wires:
                if 0 <= wi < len(wires):
                    wire_currents[wi] = max(wire_currents.get(wi, 0.0), max_i)

        # Draw overlay
        canvas = _dim(gray)

        # Draw components as filled rectangles colored by current
        GREY = (120, 120, 120)
        for i, comp in enumerate(components):
            x1, y1, x2, y2 = comp[2]
            comp_name = comp_names.get(i, "?")
            ci = abs(comp_currents.get(comp_name, 0.0))
            col = _current_color(ci, imin, imax) if ci > 0 else GREY
            cv2.rectangle(canvas, (x1, y1), (x2, y2), col, -1)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (40, 40, 40), 1)

            # Label significant currents (>1% of max)
            if ci > 0.01 * imax and imax > 0:
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                # Format current with SI prefix
                if ci >= 1.0:
                    label = f"{ci:.2f}A"
                elif ci >= 1e-3:
                    label = f"{ci * 1e3:.2f}mA"
                elif ci >= 1e-6:
                    label = f"{ci * 1e6:.2f}uA"
                else:
                    label = f"{ci * 1e9:.1f}nA"
                _put(canvas, label, (cx - 15, cy + 4), col, 0.35)

        # Draw wires colored by current
        for wi, col_i in wire_currents.items():
            if 0 <= wi < len(wires):
                col = _current_color(col_i, imin, imax) if col_i > 0 else GREY
                cv2.line(canvas, wires[wi][0], wires[wi][1], col, 2, cv2.LINE_AA)

        # Draw pins
        for node in netlist.nodes:
            ci = 0.0
            for p in node.pins:
                cn = comp_names.get(p.component_idx)
                if cn:
                    ci = max(ci, abs(comp_currents.get(cn, 0.0)))
            col = _current_color(ci, imin, imax) if ci > 0 else GREY
            for p in node.pins:
                cv2.circle(canvas, (p.x, p.y), 4, col, -1, cv2.LINE_AA)
                cv2.circle(canvas, (p.x, p.y), 4, (15, 15, 15), 1, cv2.LINE_AA)

        # Header + colorbar
        _put(
            canvas,
            f"DC currents  {_fmt_current(imin)} .. {_fmt_current(imax)}   [{strategy}]  grey = no current",
            (8, 16),
            (235, 235, 235),
            0.40,
        )
        bx, by, bw = 8, 24, 140
        for i in range(bw):
            bgr = cv2.applyColorMap(
                np.array([[int(i / bw * 255)]], np.uint8), cv2.COLORMAP_HOT
            )[0, 0]
            cv2.line(
                canvas,
                (bx + i, by),
                (bx + i, by + 8),
                (int(bgr[0]), int(bgr[1]), int(bgr[2])),
                1,
            )
        cv2.rectangle(canvas, (bx, by), (bx + bw, by + 8), (200, 200, 200), 1)

        # Build response
        component_currents_list = [
            {"name": name, "current": round(ival, 6)}
            for name, ival in sorted(comp_currents.items())
        ]

        return JSONResponse(
            {
                "overlay": _b64(canvas),
                "available": True,
                "component_currents": component_currents_list,
                "imin": round(imin, 6),
                "imax": round(imax, 6),
                "warnings": warnings,
                "spice_netlist": spice,
            }
        )

    return await asyncio.get_event_loop().run_in_executor(None, _sync)


def _fmt_current(i: float) -> str:
    """Format current with SI prefix."""
    if i >= 1.0:
        return f"{i:.2f}A"
    elif i >= 1e-3:
        return f"{i * 1e3:.2f}mA"
    elif i >= 1e-6:
        return f"{i * 1e6:.2f}uA"
    else:
        return f"{i * 1e9:.1f}nA"

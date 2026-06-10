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
from wire_detection.api.models import JoinOverlayRequest, PathRequest
from wire_detection.api.models import OverrideRequest
from wire_detection.core.connection_overrides import (
    load_overrides,
    save_overrides,
    validate_override_key,
    validate_reassign_target,
)
from wire_detection.core.join_strategies import DEFAULT_STRATEGY, run_strategy
from wire_detection.core.spice import COMPONENT_NAMES

router = APIRouter()

import re as _re
_ENDPOINT_RE = _re.compile(r"^wire_(\d+)_ep(1|2)$")


def apply_overrides(
    wires: list,
    components_raw: list,
    all_pins: list,
    netlist,
    overrides: dict,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Apply connection overrides (reassign → remove → join) to topology data.

    Returns updated (topo_wires, topo_pins, topo_nodes).

    Internally tracks per-endpoint node assignments so that operations work
    at the ``wire_<idx>_ep<1|2>`` granularity.
    """
    from wire_detection.core.netlist import NetNode, Netlist

    # ── Build per-endpoint → node_id lookup ──
    # Also build reverse: (wire_idx, ep_num) → node_id and wire_idx → [node_ids]
    ep_to_node: dict[str, int | None] = {}
    _ep_to_node_ids: dict[tuple[int, int], set[int]] = {}  # (wire_idx, ep_num) → {node_ids}
    for node in netlist.nodes:
        for wi in node.wires:
            # Each wire belongs to one node; both endpoints share that node
            # but we track per-endpoint for override flexibility
            for ep in (1, 2):
                key = f"wire_{wi}_ep{ep}"
                ep_to_node[key] = node.node_id
                _ep_to_node_ids.setdefault((wi, ep), set()).add(node.node_id)

    # ── Build per-endpoint → pin lookup ──
    # Map (component_idx, pin_name) → node_id for quick reference
    pin_node: dict[tuple[int, str], int | None] = dict(netlist.pin_to_node)

    # Also build a lookup: component_name → component_idx from all_pins
    # and node_id → set of pins in that node
    node_pins: dict[int, list] = {}
    node_wire_idxs: dict[int, list[int]] = {}
    for node in netlist.nodes:
        node_pins[node.node_id] = list(node.pins)
        node_wire_idxs[node.node_id] = list(node.wires)

    # ── Phase 1: Reassign ──
    reassign = overrides.get("reassign", {})
    for ep_key, target in reassign.items():
        m = _ENDPOINT_RE.match(ep_key)
        if m is None:
            continue
        wire_idx = int(m.group(1))
        ep_num = int(m.group(2))

        # Find target node via component name + pin name
        comp_name = target.get("component", "")
        pin_name = target.get("pin", "")
        target_node_id: int | None = None

        # Look up component_idx from the topo_pins list (component_name format "R2" etc.)
        # We need to find the matching component and its pin
        from wire_detection.core.component_classes import PREFIX_MAP
        for ci, comp in enumerate(components_raw):
            cls_id = comp[0]
            type_name = COMPONENT_NAMES.get(cls_id, f"cls_{cls_id}")
            prefix = PREFIX_MAP.get(type_name) or "X"
            cname = f"{prefix}{ci + 1}"
            if cname == comp_name:
                # Found the component — now find its pin
                key = (ci, pin_name)
                target_node_id = pin_node.get(key)
                break

        if target_node_id is None:
            continue  # can't resolve target, skip

        old_node_id = ep_to_node.get(ep_key)
        if old_node_id is None or old_node_id == target_node_id:
            # Already on target node or no old node — just update mapping
            ep_to_node[ep_key] = target_node_id
            continue

        # Merge old_node into target_node (same logic as the join phase).
        # This ensures the wire's old net and the target pin's net become one
        # electrical node, so the topology reflects the connection.
        src, dst = (old_node_id, target_node_id) if old_node_id < target_node_id else (target_node_id, old_node_id)

        for wi in node_wire_idxs.get(src, []):
            if wi not in node_wire_idxs.get(dst, []):
                node_wire_idxs.setdefault(dst, []).append(wi)
            for ep in (1, 2):
                k = f"wire_{wi}_ep{ep}"
                if ep_to_node.get(k) == src:
                    ep_to_node[k] = dst

        for pin in node_pins.get(src, []):
            node_pins.setdefault(dst, []).append(pin)
            pin_key = (pin.component_idx, pin.pin_name)
            if pin_node.get(pin_key) == src:
                pin_node[pin_key] = dst

        node_wire_idxs[src] = []
        node_pins[src] = []

        # Update endpoint → node mapping
        ep_to_node[ep_key] = dst

    # ── Phase 2: Remove ──
    remove_keys = overrides.get("remove", [])
    for ep_key in remove_keys:
        if ep_key in ep_to_node:
            # Remove endpoint from its current node's pin tracking
            old_node_id = ep_to_node[ep_key]
            ep_to_node[ep_key] = None  # disconnected

    # ── Phase 3: Join ──
    join_pairs = overrides.get("join", [])
    for pair in join_pairs:
        if len(pair) != 2:
            continue
        key_a, key_b = pair[0], pair[1]

        node_a = ep_to_node.get(key_a)
        node_b = ep_to_node.get(key_b)

        if node_a is None or node_b is None:
            continue  # can't join a disconnected endpoint
        if node_a == node_b:
            continue  # already same node

        # Merge: move everything from smaller node into larger node
        if node_a > node_b:
            node_a, node_b = node_b, node_a
            key_a, key_b = key_b, key_a

        # node_a is smaller (or equal), node_b is larger — merge node_a into node_b
        # Move all wires from node_a → node_b
        for wi in node_wire_idxs.get(node_a, []):
            if wi not in node_wire_idxs.get(node_b, []):
                node_wire_idxs.setdefault(node_b, []).append(wi)
            # Update all endpoint → node mappings for this wire
            for ep in (1, 2):
                k = f"wire_{wi}_ep{ep}"
                if ep_to_node.get(k) == node_a:
                    ep_to_node[k] = node_b

        # Move all pins from node_a → node_b
        for pin in node_pins.get(node_a, []):
            node_pins.setdefault(node_b, []).append(pin)
            # Update pin_node mapping
            pin_key = (pin.component_idx, pin.pin_name)
            if pin_node.get(pin_key) == node_a:
                pin_node[pin_key] = node_b

        # Clear node_a
        node_wire_idxs[node_a] = []
        node_pins[node_a] = []

    # ── Phase 4: Merge (pin <-> pin, no wire needed) ──
    # The manual fix for fragmented detections: connect two component pins
    # directly. Resolves each pin to its node and merges, same as the join phase.
    from wire_detection.core.component_classes import PREFIX_MAP as _PREFIX_MAP

    def _resolve_pin_node(ref):
        comp_name = (ref or {}).get("component", "")
        pin_name = (ref or {}).get("pin", "")
        for ci, comp in enumerate(components_raw):
            type_name = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
            prefix = _PREFIX_MAP.get(type_name) or "X"
            if f"{prefix}{ci + 1}" == comp_name:
                return pin_node.get((ci, pin_name))
        return None

    for pair in overrides.get("merge", []):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        node_a = _resolve_pin_node(pair[0])
        node_b = _resolve_pin_node(pair[1])
        if node_a is None or node_b is None or node_a == node_b:
            continue
        if node_a > node_b:
            node_a, node_b = node_b, node_a
        for wi in node_wire_idxs.get(node_a, []):
            if wi not in node_wire_idxs.get(node_b, []):
                node_wire_idxs.setdefault(node_b, []).append(wi)
            for ep in (1, 2):
                k = f"wire_{wi}_ep{ep}"
                if ep_to_node.get(k) == node_a:
                    ep_to_node[k] = node_b
        for pin in node_pins.get(node_a, []):
            node_pins.setdefault(node_b, []).append(pin)
            pin_key = (pin.component_idx, pin.pin_name)
            if pin_node.get(pin_key) == node_a:
                pin_node[pin_key] = node_b
        node_wire_idxs[node_a] = []
        node_pins[node_a] = []

    # ── Rebuild topo_wires ──
    topo_wires = []
    for wi, (ep1, ep2) in enumerate(wires):
        # Wire's primary node is determined by the endpoints
        # If both endpoints agree, use that node; if they differ, use the
        # endpoint with more associations (or ep1 as tiebreaker)
        n1 = ep_to_node.get(f"wire_{wi}_ep1")
        n2 = ep_to_node.get(f"wire_{wi}_ep2")
        if n1 == n2:
            wire_node = n1
        elif n1 is not None and n2 is None:
            wire_node = n1
        elif n2 is not None and n1 is None:
            wire_node = n2
        else:
            # Both different — pick ep1's node as primary
            wire_node = n1
        topo_wires.append({
            "idx": wi,
            "ep1": list(ep1),
            "ep2": list(ep2),
            "node_id": wire_node,
        })

    # ── Rebuild topo_pins ──
    topo_pins = []
    for p in all_pins:
        key = (p.component_idx, p.pin_name)
        node_id = pin_node.get(key)
        comp = components_raw[p.component_idx]
        comp_type = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        from wire_detection.core.component_classes import PREFIX_MAP
        prefix = PREFIX_MAP.get(comp_type) or "X"
        topo_pins.append({
            "x": p.x,
            "y": p.y,
            "component_idx": p.component_idx,
            "component_name": f"{prefix}{p.component_idx + 1}",
            "pin_name": p.pin_name,
            "node_id": node_id,
        })

    # ── Rebuild topo_nodes ──
    # Collect all non-empty nodes
    active_node_ids = set()
    for node_id, wires_list in node_wire_idxs.items():
        if wires_list:
            active_node_ids.add(node_id)
    for node_id, pins_list in node_pins.items():
        if pins_list:
            active_node_ids.add(node_id)

    topo_nodes = []
    for nid in sorted(active_node_ids):
        wires_list = node_wire_idxs.get(nid, [])
        pins_list = node_pins.get(nid, [])
        comp_idxs = {p.component_idx for p in pins_list}
        topo_nodes.append({
            "node_id": nid,
            "wire_count": len(wires_list),
            "pin_count": len(pins_list),
            "component_count": len(comp_idxs),
        })

    return topo_wires, topo_pins, topo_nodes


# Re-export for apply_overrides
import re as _re
_ENDPOINT_RE = _re.compile(r"^wire_(\d+)_ep(1|2)$")


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

    # ── Apply overrides if any ──
    overrides = load_overrides(ds, img_idx)
    if overrides.get("reassign") or overrides.get("join") or overrides.get("remove") or overrides.get("merge"):
        topo_wires, topo_pins, topo_nodes = apply_overrides(
            wires, components_raw, all_pins, netlist, overrides
        )
        # Rebuild component node_ids from overridden pins
        comp_node_ids2: dict[int, set[int]] = {}
        for p_info in topo_pins:
            if p_info["node_id"] is not None:
                comp_node_ids2.setdefault(p_info["component_idx"], set()).add(p_info["node_id"])
        for comp in topo_components:
            comp["node_ids"] = sorted(comp_node_ids2.get(comp["idx"], set()))

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


@router.get("/api/topology/overrides")
async def get_overrides(idx: int, ds: str = "gt_labels"):
    """Return the current overrides dict for a given image."""
    import asyncio

    def _sync():
        return JSONResponse(load_overrides(ds, idx))

    return await asyncio.get_event_loop().run_in_executor(None, _sync)


@router.post("/api/topology/overrides")
async def save_override(data: OverrideRequest):
    """Validate and save overrides, then return the updated topology."""
    import asyncio

    def _sync():
        # Build topology data to validate against
        topo = _build_topology_data(
            img_idx=data.img_idx,
            ds=data.dataset,
            preset=data.preset,
        )
        if "error" in topo:
            return JSONResponse({"error": topo["error"]}, status_code=404)

        overrides = data.overrides

        # Validate reassign keys
        reassign = overrides.get("reassign", {})
        for ep_key, target in reassign.items():
            err = validate_override_key(ep_key, topo["wires"], topo["components"])
            if err:
                return JSONResponse({"error": err}, status_code=400)
            err = validate_reassign_target(target, topo["components"])
            if err:
                return JSONResponse({"error": err}, status_code=400)

        # Validate join keys
        for i, pair in enumerate(overrides.get("join", [])):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                return JSONResponse(
                    {"error": f"join[{i}] must be a 2-element list"},
                    status_code=400,
                )
            for ep_key in pair:
                err = validate_override_key(ep_key, topo["wires"], topo["components"])
                if err:
                    return JSONResponse({"error": err}, status_code=400)

        # Validate remove keys
        for ep_key in overrides.get("remove", []):
            err = validate_override_key(ep_key, topo["wires"], topo["components"])
            if err:
                return JSONResponse({"error": err}, status_code=400)

        # Save to disk
        try:
            save_overrides(data.dataset, data.img_idx, overrides)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        # Rebuild topology with the saved overrides
        updated = _build_topology_data(
            img_idx=data.img_idx,
            ds=data.dataset,
            preset=data.preset,
        )
        if "error" in updated:
            return JSONResponse({"error": updated["error"]}, status_code=404)
        return JSONResponse(updated)

    return await asyncio.get_event_loop().run_in_executor(None, _sync)


@router.delete("/api/topology/overrides")
async def delete_overrides(idx: int, ds: str = "gt_labels"):
    """Clear overrides for an image (save empty overrides) and return updated topology."""
    import asyncio

    def _sync():
        empty = {"reassign": {}, "join": [], "remove": []}
        save_overrides(ds, idx, empty)

        topo = _build_topology_data(
            img_idx=idx,
            ds=ds,
            preset="best_candidate_v4",
        )
        if "error" in topo:
            return JSONResponse({"error": topo["error"]}, status_code=404)
        return JSONResponse(topo)

    return await asyncio.get_event_loop().run_in_executor(None, _sync)

@router.post("/api/path")
async def trace_path(data: PathRequest):
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
            return JSONResponse({"error": result["error"], "path": [], "warnings": [result["error"]]}, status_code=404)

        components = result.get("components", [])
        warnings: list[str] = []

        # Build adjacency: component name → node_ids
        comp_to_nodes: dict[str, list[int]] = {}
        for comp in components:
            comp_to_nodes[comp["name"]] = comp.get("node_ids", [])

        # Build adjacency: node_id → set of component names
        node_to_comps: dict[int, set[str]] = {}
        for comp in components:
            for nid in comp.get("node_ids", []):
                node_to_comps.setdefault(nid, set()).add(comp["name"])

        from_name = data.from_component
        to_name = data.to_component

        if from_name not in comp_to_nodes:
            warnings.append(f"Component '{from_name}' not found")
            return JSONResponse({"path": [], "warnings": warnings})
        if to_name not in comp_to_nodes:
            warnings.append(f"Component '{to_name}' not found")
            return JSONResponse({"path": [], "warnings": warnings})
        if from_name == to_name:
            warnings.append("Start and end components are the same")
            return JSONResponse({"path": [], "warnings": warnings})

        # BFS through bipartite graph: component ↔ node
        from collections import deque

        queue: deque[tuple[str, list[dict]]] = deque()
        queue.append((from_name, [{"type": "component", "name": from_name, "node_ids": sorted(comp_to_nodes[from_name])}]))
        visited_comps: set[str] = {from_name}
        visited_nodes: set[int] = set()

        while queue:
            current_name, path = queue.popleft()

            for nid in comp_to_nodes.get(current_name, []):
                if nid in visited_nodes:
                    continue
                visited_nodes.add(nid)

                node_step = {
                    "type": "node",
                    "node_id": nid,
                    "components": sorted(node_to_comps.get(nid, set())),
                }

                for neighbor_name in sorted(node_to_comps.get(nid, set())):
                    if neighbor_name in visited_comps:
                        continue
                    if neighbor_name == to_name:
                        full_path = path + [node_step, {
                            "type": "component",
                            "name": neighbor_name,
                            "node_ids": sorted(comp_to_nodes[neighbor_name]),
                        }]
                        return JSONResponse({"path": full_path, "warnings": warnings})
                    visited_comps.add(neighbor_name)
                    comp_step = {
                        "type": "component",
                        "name": neighbor_name,
                        "node_ids": sorted(comp_to_nodes[neighbor_name]),
                    }
                    queue.append((neighbor_name, path + [node_step, comp_step]))

        warnings.append(f"No path found between '{from_name}' and '{to_name}'")
        return JSONResponse({"path": [], "warnings": warnings})

    return await asyncio.get_event_loop().run_in_executor(None, _sync)

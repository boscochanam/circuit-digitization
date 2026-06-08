"""
Override storage layer for the connection editor feature.

Provides load/save/validate functions for per-image wire-connection overrides
stored as JSON files under wire_detection/overrides/{dataset}/{img_idx}.json.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OVERRIDES_ROOT = os.path.join(os.path.dirname(__file__), "..", "overrides")

_ENDPOINT_RE = re.compile(r"^wire_(\d+)_ep(1|2)$")


def _default_overrides() -> dict:
    return {"reassign": {}, "join": [], "remove": []}


def _overrides_path(dataset: str, img_idx: int) -> str:
    return os.path.join(OVERRIDES_ROOT, dataset, f"{img_idx}.json")


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------

def load_overrides(dataset: str, img_idx: int) -> dict:
    """Return the overrides dict for *dataset*/*img_idx*, or a blank slate."""
    path = _overrides_path(dataset, img_idx)
    if not os.path.isfile(path):
        return _default_overrides()
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    # Fill in any missing keys for backward-compat
    base = _default_overrides()
    for key in base:
        data.setdefault(key, base[key])
    return data


def _validate_structure(overrides: dict) -> None:
    """Raise ValueError if *overrides* does not match the expected schema."""
    if not isinstance(overrides, dict):
        raise ValueError("overrides must be a dict")

    reassign = overrides.get("reassign", {})
    join = overrides.get("join", [])
    remove = overrides.get("remove", [])

    if not isinstance(reassign, dict):
        raise ValueError("'reassign' must be a dict")

    if not isinstance(join, list):
        raise ValueError("'join' must be a list of 2-element lists/tuples")
    for i, pair in enumerate(join):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError(
                f"'join[{i}' must be a 2-element list/tuple, got {type(pair).__name__} len={len(pair) if isinstance(pair, (list, tuple)) else 'N/A'}"
            )

    if not isinstance(remove, list):
        raise ValueError("'remove' must be a list of strings")
    for i, item in enumerate(remove):
        if not isinstance(item, str):
            raise ValueError(f"'remove[{i}]' must be a string, got {type(item).__name__}")


def save_overrides(dataset: str, img_idx: int, overrides: dict) -> None:
    """Persist *overrides* to disk after validating its structure."""
    _validate_structure(overrides)
    path = _overrides_path(dataset, img_idx)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(overrides, fh, indent=2)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_override_key(key: str, wires: list, components: list) -> str | None:
    """Validate a wire-endpoint key like ``wire_3_ep2``.

    Returns an error message string if *key* is invalid, ``None`` if valid.
    """
    m = _ENDPOINT_RE.match(key)
    if m is None:
        return f"Invalid key format '{key}'; expected wire_<idx>_ep<1|2>"

    idx = int(m.group(1))
    valid_indices = {w["idx"] for w in wires}
    if idx not in valid_indices:
        return f"Wire index {idx} not found (valid: {sorted(valid_indices)})"

    # endpoint number (1 or 2) is already enforced by the regex
    return None


def validate_reassign_target(target: dict, components: list) -> str | None:
    """Validate a reassign target like ``{"component": "R2", "pin": "pin1"}``.

    Returns an error message string if *target* is invalid, ``None`` if valid.
    """
    if not isinstance(target, dict):
        return "Reassign target must be a dict"

    comp_name = target.get("component")
    pin_name = target.get("pin")

    if comp_name is None or pin_name is None:
        return "Reassign target must contain 'component' and 'pin' keys"

    comp_names = {c["name"] for c in components}
    if comp_name not in comp_names:
        return f"Component '{comp_name}' not found (available: {sorted(comp_names)})"

    # Find the matching component and check its pins
    comp = next(c for c in components if c["name"] == comp_name)
    # Components may have a 'pins' list, or we accept any pin name if no list
    known_pins = comp.get("pins")
    if known_pins is not None:
        pin_names = [p.get("pin_name", p.get("name", "")) for p in known_pins]
        if pin_name not in pin_names:
            return (
                f"Pin '{pin_name}' not found on component '{comp_name}' "
                f"(available: {pin_names})"
            )

    return None


# ---------------------------------------------------------------------------
# Disconnect (remove) — applied to the WIRES, before the join runs
# ---------------------------------------------------------------------------

# Far-off coordinate: a "removed" wire bridges nothing during the join, while its
# index stays valid (reassign/join keys reference wire indices).
_DEGENERATE_EP = (-100000, -100000)


def removed_wire_indices(overrides: dict) -> set:
    """Wire indices that have at least one removed endpoint."""
    out = set()
    for key in overrides.get("remove", []) or []:
        m = _ENDPOINT_RE.match(key) if isinstance(key, str) else None
        if m:
            out.add(int(m.group(1)))
    return out


def wires_with_removes(wires, overrides):
    """Return a copy of *wires* where any wire with a removed endpoint is replaced
    by a degenerate, off-canvas segment.

    A disconnect must take effect BEFORE the join runs (so the net actually
    splits), but simply dropping the wire would shift every later wire's index and
    break the ``wire_<idx>_ep<n>`` keys that reassign/join rely on. Substituting a
    degenerate segment keeps indices stable while making the wire join nothing.

    NOTE: a wire endpoint can also seed a discovered pin, so degenerating it can
    drop that pin. Acceptable for a manual, visible, undoable disconnect — but see
    the tracking issue for the topology-vs-sim consistency discussion.
    """
    idxs = removed_wire_indices(overrides)
    if not idxs:
        return wires
    out = list(wires)
    for wi in idxs:
        if 0 <= wi < len(out):
            out[wi] = (_DEGENERATE_EP, _DEGENERATE_EP)
    return out


# ---------------------------------------------------------------------------
# Apply overrides to the core netlist (so SPICE / voltage / current reflect them)
# ---------------------------------------------------------------------------

def apply_overrides_to_netlist(netlist, components_raw, overrides):
    """Bake connection overrides into the core ``Netlist`` so the generated SPICE
    — and therefore the netlist, voltage and current simulations — reflect manual
    wire→component assignments, not just the topology *view*.

    ``reassign`` and ``join`` are applied as node MERGES (union-find): exactly the
    "connect this wire's net to that component pin / to that other wire" intent.
    This covers the common "auto-join missed a connection" case (the stated goal:
    assign wire nodes to components).

    ``remove`` (splitting a node) is intentionally NOT propagated here — it needs
    the node's internal connectivity recomputed without the removed wire, which is
    a larger change. Reassign/join are the additive "assign/connect" operations.

    Returns a NEW ``Netlist`` (the input is left untouched). No-op if there are no
    reassign/join overrides.
    """
    from wire_detection.core.netlist import NetNode, Netlist
    from wire_detection.core.component_classes import PREFIX_MAP
    from wire_detection.core.spice import COMPONENT_NAMES

    reassign = overrides.get("reassign", {}) or {}
    join = overrides.get("join", []) or []
    if not reassign and not join:
        return netlist

    # wire index -> its node id (from the current join result)
    wire_to_node: dict[int, int] = {}
    for node in netlist.nodes:
        for wi in node.wires:
            wire_to_node[wi] = node.node_id

    pin_to_node = dict(netlist.pin_to_node)

    # SPICE component name ("R2") -> component index, matching spice.py naming.
    name_to_idx: dict[str, int] = {}
    for ci, comp in enumerate(components_raw):
        type_name = COMPONENT_NAMES.get(comp[0], f"cls_{comp[0]}")
        prefix = PREFIX_MAP.get(type_name) or "X"
        name_to_idx[f"{prefix}{ci + 1}"] = ci

    # ── union-find over node ids (smaller id stays root for stable node names) ──
    parent: dict[int, int] = {node.node_id: node.node_id for node in netlist.nodes}

    def find(x: int) -> int:
        root = x
        while parent.get(root, root) != root:
            root = parent[root]
        while parent.get(x, x) != root:  # path compression
            parent[x], x = root, parent[x]
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            lo, hi = (ra, rb) if ra < rb else (rb, ra)
            parent[hi] = lo

    def _ep_wire(key) -> int | None:
        m = _ENDPOINT_RE.match(key) if isinstance(key, str) else None
        return int(m.group(1)) if m else None

    # reassign: connect the wire's net to the target component pin's net
    for ep_key, target in reassign.items():
        wi = _ep_wire(ep_key)
        if wi is None:
            continue
        src = wire_to_node.get(wi)
        ci = name_to_idx.get((target or {}).get("component", ""))
        if ci is None:
            continue
        tgt = pin_to_node.get((ci, (target or {}).get("pin", "")))
        if src is not None and tgt is not None:
            union(src, tgt)

    # join: connect two wires' nets
    for pair in join:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        wa, wb = _ep_wire(pair[0]), _ep_wire(pair[1])
        if wa is None or wb is None:
            continue
        na, nb = wire_to_node.get(wa), wire_to_node.get(wb)
        if na is not None and nb is not None:
            union(na, nb)

    # ── rebuild the netlist with merged nodes ──
    merged: dict[int, NetNode] = {}
    for node in netlist.nodes:
        root = find(node.node_id)
        dst = merged.get(root)
        if dst is None:
            dst = merged[root] = NetNode(node_id=root, pins=[], wires=[])
        dst.pins.extend(node.pins)
        dst.wires.extend(node.wires)

    out = Netlist()
    out.nodes = list(merged.values())
    out.pin_to_node = {key: find(nid) for key, nid in pin_to_node.items()}
    return out

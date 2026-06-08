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

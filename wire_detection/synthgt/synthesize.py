"""Turn an authored `CircuitSpec` into a detector-style coordinate map.

`synthesize_clean` produces the components + wires that the *clean* join recovers
exactly. `inject_errors` then perturbs the wires the way a real detector might -
BUT the error model here is a first-pass PLACEHOLDER (uniform jitter, symmetric
cut-short, independent drops, uniform wrong-pin snaps). Real detection error is
structured and correlated with the image (breaks at faint strokes/crossings,
anchor over-deletion, etc.).
Until this is calibrated against the real detector's output (see
`docs/synthetic-eval-plan.md`), synthetic *join* scores are a robustness signal,
not a prediction of real-image performance.
"""
from __future__ import annotations

import math
import random
from itertools import combinations

from wire_detection.core.component_classes import COMPONENT_TYPES, PREFIX_MAP
from wire_detection.core.join_strategies import make_pins
from wire_detection.synthgt.circuits import CircuitSpec

NAME_TO_CLS = {v: k for k, v in COMPONENT_TYPES.items()}

Point = tuple[int, int]
Wire = tuple[Point, Point]


def build_components(spec: CircuitSpec, *, return_angle: bool = False):
    """spec -> list of (cls_id, vertices, bbox) in the pipeline's component format.

    When *return_angle* is True, also return the per-component angle (degrees)
    so callers can compute rotated pin positions.
    """
    comps = []
    angles = []
    for c in spec.comps:
        cls = NAME_TO_CLS[c.type]
        if c.orient == "H":
            w, h = c.size, 30
        else:
            w, h = 30, c.size
        angle = getattr(c, "angle", 0.0) or 0.0
        if angle:
            # Rotate the 4 corners, then compute the AABB that contains them
            rad = math.radians(angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            half_w, half_h = w / 2, h / 2
            corners = [(-half_w, -half_h), (half_w, -half_h),
                       (half_w, half_h), (-half_w, half_h)]
            rotated = [(int(cos_a * dx - sin_a * dy + c.cx),
                        int(sin_a * dx + cos_a * dy + c.cy))
                       for dx, dy in corners]
            xs = [p[0] for p in rotated]
            ys = [p[1] for p in rotated]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            comps.append((cls, rotated, bbox))
        else:
            bbox = (c.cx - w // 2, c.cy - h // 2, c.cx + w // 2, c.cy + h // 2)
            comps.append((cls, [], bbox))
        angles.append(angle)
    if return_angle:
        return comps, angles
    return comps


def pin_positions(components, spec: CircuitSpec | None = None) -> dict[tuple[int, int], Point]:
    """Pin coords keyed (comp_idx, pin_idx).

    If *spec* is provided and components have non-zero angles, computes pins
    directly from the rotation geometry (the pipeline's derive_pins_from_obb
    only handles axis-aligned bboxes).  Otherwise falls back to make_pins.
    """
    # Check if any component has rotation
    has_angle = any(getattr(c, "angle", 0.0) for c in spec.comps) if spec else False
    if has_angle and spec:
        pins: dict[tuple[int, int], Point] = {}
        for i, c in enumerate(spec.comps):
            angle = getattr(c, "angle", 0.0) or 0.0
            # Pins are along the LONG axis: Y for "V", X for "H"
            half_long = c.size / 2
            rad = math.radians(angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            if c.orient == "H":
                # Long axis is X before rotation
                base_angle = 0.0
            else:
                # Long axis is Y before rotation (90°)
                base_angle = 90.0
            total_rad = math.radians(angle + base_angle)
            ca, sa = math.cos(total_rad), math.sin(total_rad)
            for pi, sign in enumerate([-1, 1]):
                px = int(sign * half_long * ca + c.cx)
                py = int(sign * half_long * sa + c.cy)
                pins[(i, pi)] = (px, py)
        return pins
    return {(p.component_idx, p.pin_idx): (p.x, p.y) for p in make_pins([], components)}


def _route_net(members: list[tuple[int, int]], pin_pos) -> list[Wire]:
    """Chain a net's pins into wire segments. Sorting by (x, y) yields clean
    axis-aligned segments for collinear rails and direct links otherwise; each
    endpoint lands exactly on a pin so the join binds it (dist 0)."""
    pts = sorted({pin_pos[m] for m in members})
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def synthesize_clean(spec: CircuitSpec):
    """Return (components, wires, pin_pos). Wires reproduce the authored netlist."""
    components = build_components(spec)
    pin_pos = pin_positions(components, spec)
    wires: list[Wire] = []
    for net in spec.nets:
        wires.extend(_route_net(net, pin_pos))
    return components, wires, pin_pos


def value_overrides(spec: CircuitSpec) -> dict[str, str]:
    """SPICE value map keyed `f"{prefix}{comp_idx+1}"` (matches SpiceGenerator)."""
    out: dict[str, str] = {}
    for i, c in enumerate(spec.comps):
        prefix = PREFIX_MAP.get(c.type)
        if prefix:
            out[f"{prefix}{i + 1}"] = c.value
    return out


def intended_pairs(spec: CircuitSpec) -> set[tuple[int, int]]:
    """Ground-truth connected component pairs (the join target)."""
    pairs: set[tuple[int, int]] = set()
    for net in spec.nets:
        comps = sorted({ci for ci, _pin in net})
        pairs.update(combinations(comps, 2))
    return pairs


# ====================================================================
# ERROR MODEL  (PLACEHOLDER - see module docstring / docs)
# ====================================================================

# severity -> (jitter_sigma_px, cut_short_px, drop_prob, wrong_pin_prob).
# Level 0 is the clean control. Swap this table / the functions below when
# calibrating to the real detector's measured error statistics.
#
# wrong_pin_prob is the OVER-MERGE mode: an endpoint snaps onto a nearby pin it
# does not belong to (detector traced a stroke into the wrong lead). Without it
# the model can only break wires, never short them, and join precision would sit
# at a meaningless 1.00 across the whole sweep.
ERROR_LEVELS: dict[int, tuple[float, float, float, float]] = {
    0: (0.0, 0.0, 0.00, 0.00),   # clean control
    1: (3.0, 4.0, 0.00, 0.00),   # mild localization noise + slight cut-short
    2: (6.0, 9.0, 0.05, 0.02),   # moderate
    3: (10.0, 15.0, 0.12, 0.05),  # heavy
    4: (14.0, 22.0, 0.20, 0.10),  # severe
}

# wrong-pin snap: candidate pins live in this distance band from the endpoint
# (closer = its own pin, farther = not a plausible confusion).
_SNAP_MIN_PX = 25.0
_SNAP_MAX_PX = 120.0


def _cut_short(wire: Wire, px: float) -> Wire:
    """Pull both endpoints inward along the wire - mimics the detector stopping a
    stroke short of the component lead (the #21 anchor-deletion failure)."""
    (x1, y1), (x2, y2) = wire
    dx, dy = x2 - x1, y2 - y1
    ln = math.hypot(dx, dy)
    if ln < 1e-6 or px <= 0:
        return wire
    ux, uy = dx / ln, dy / ln
    k = min(px, (ln - 2) / 2)  # never collapse the wire past a 2px core
    return ((int(x1 + ux * k), int(y1 + uy * k)),
            (int(x2 - ux * k), int(y2 - uy * k)))


def inject_errors(
    wires: list[Wire],
    severity: int,
    seed: int,
    pin_pos: dict[tuple[int, int], Point] | None = None,
    params: tuple[float, float, float, float] | None = None,
) -> list[Wire]:
    """Apply the placeholder error model deterministically for (severity, seed).

    `pin_pos` enables the wrong-pin snap (over-merge) mode; without it that mode
    is skipped. `params` overrides the ERROR_LEVELS row - used by tests to force
    a single error mode in isolation.
    """
    sigma, cut, drop, wrong = (params if params is not None
                               else ERROR_LEVELS.get(severity, (0.0, 0.0, 0.0, 0.0)))
    if params is None and severity == 0:
        return list(wires)
    rng = random.Random((seed << 8) ^ (severity << 3) ^ 0x5EED)
    pins: list[Point] = sorted(pin_pos.values()) if pin_pos else []
    out: list[Wire] = []
    for w in wires:
        if drop and rng.random() < drop:
            continue                       # detector missed this wire entirely
        w = _cut_short(w, cut)
        (x1, y1), (x2, y2) = w
        if sigma:
            x1 += rng.gauss(0, sigma); y1 += rng.gauss(0, sigma)
            x2 += rng.gauss(0, sigma); y2 += rng.gauss(0, sigma)
        ends = [(int(x1), int(y1)), (int(x2), int(y2))]
        if wrong and pins:
            for k in (0, 1):
                if rng.random() >= wrong:
                    continue
                cands = [p for p in pins
                         if _SNAP_MIN_PX < math.hypot(p[0] - ends[k][0],
                                                      p[1] - ends[k][1]) <= _SNAP_MAX_PX]
                if cands:
                    # land EXACTLY on the wrong pin - the confident failure mode
                    ends[k] = cands[rng.randrange(len(cands))]
        out.append((ends[0], ends[1]))
    return out

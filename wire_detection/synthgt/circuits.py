"""Authored ground-truth circuits.

A `CircuitSpec` is a netlist we know is correct, plus a clean 2-D layout. Layouts
are designed so the members of each net are collinear (share a rail), which lets
the synthesizer route axis-aligned wires that don't graze other components - so
the *clean* join recovers the authored netlist exactly (the harness asserts this).

Conventions (match `derive_pins_from_obb`):
  * a vertical component (orient "V") has pin0 = TOP, pin1 = BOTTOM;
  * a horizontal component (orient "H") has pin0 = LEFT, pin1 = RIGHT;
  * pins sit at center +/- 0.25*long_size along the long axis.

DC note: only R / L / V are used (L is a short at DC). Capacitors are avoided in
these series loops because a cap blocks DC - its legitimate I=0 is indistinguishable
from a fragmented/dead join and would muddy the sim score.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Comp:
    type: str            # component-class name, e.g. "resistor", "voltage-DC"
    value: str           # SPICE value, e.g. "1k", "5"
    cx: int
    cy: int
    orient: str = "V"    # "V" -> pins top/bottom ; "H" -> pins left/right
    size: int = 160      # long-axis length; short axis fixed at 30
    angle: float = 0.0   # rotation in degrees (0 = axis-aligned per orient)


@dataclass
class CircuitSpec:
    name: str
    comps: list[Comp]
    nets: list[list[tuple[int, int]]]   # each net: [(comp_idx, pin_idx), ...]
    expect_mA: float | None = None      # authored source current (sanity / SPICE oracle)
    note: str = ""
    extra: dict = field(default_factory=dict)


# == helpers to keep the catalog readable ==
def _V(value, cx, cy, **kw):  # noqa: N802 - terse on purpose
    return Comp("voltage-DC", value, cx, cy, **kw)

def _R(value, cx, cy, **kw):  # noqa: N802
    return Comp("resistor", value, cx, cy, **kw)

def _L(value, cx, cy, **kw):  # noqa: N802
    return Comp("inductor", value, cx, cy, **kw)

def _D(value, cx, cy, **kw):  # noqa: N802
    return Comp("diode", value, cx, cy, **kw)

def _GND(value, cx, cy, **kw):  # noqa: N802
    return Comp("gnd", value, cx, cy, **kw)


# ====================================================================
# CATALOG
# ====================================================================

CATALOG: list[CircuitSpec] = [
    # V || R || R - three vertical components on two horizontal rails.
    CircuitSpec(
        name="parallel_rr",
        comps=[_V("5", 120, 220), _R("1k", 300, 220), _R("1k", 480, 220)],
        nets=[[(0, 0), (1, 0), (2, 0)],      # all tops
              [(0, 1), (1, 1), (2, 1)]],     # all bottoms
        expect_mA=10.0,                       # 5V / (1k||1k = 500R)
        note="Parallel R. Stresses multi-terminal nets.",
    ),

    # Voltage divider: V - R1 - R2 in a series loop (rectangle).
    CircuitSpec(
        name="divider_rr",
        comps=[_V("5", 120, 240, size=200),
               _R("1k", 300, 140, orient="H"),
               _R("1k", 480, 240, size=200)],
        nets=[[(0, 0), (1, 0)],   # V.top  - R1.left   (top-left rail, y=140)
              [(1, 1), (2, 0)],   # R1.right- R2.top    (top-right rail, y=140)
              [(2, 1), (0, 1)]],  # R2.bot - V.bot      (bottom rail,  y=340)
        expect_mA=2.5,            # 5V / 2k
        note="Series divider, rectangular loop.",
    ),

    # Four components around a square: V - R1 - R2 - R3.
    CircuitSpec(
        name="loop4_r",
        comps=[_V("5", 120, 260, size=240),
               _R("1k", 320, 140, orient="H", size=200),
               _R("1k", 520, 260, size=240),
               _R("1k", 320, 380, orient="H", size=200)],
        nets=[[(0, 0), (1, 0)],   # V.top   - R1.left   (y=140)
              [(1, 1), (2, 0)],   # R1.right - R2.top    (y=140)
              [(2, 1), (3, 1)],   # R2.bot  - R3.right   (y=380)
              [(3, 0), (0, 1)]],  # R3.left - V.bot      (y=380)
        expect_mA=5.0 / 3.0,      # 5V / 3k
        note="Square loop, 4 components / 4 nets.",
    ),

    # R-L series loop (L is a short at DC, so I = 5V / R).
    CircuitSpec(
        name="rl_series",
        comps=[_V("5", 120, 240, size=200),
               _R("2.2k", 300, 140, orient="H"),
               _L("10m", 480, 240, size=200)],
        nets=[[(0, 0), (1, 0)],
              [(1, 1), (2, 0)],
              [(2, 1), (0, 1)]],
        expect_mA=5.0 / 2200.0 * 1000.0,   # ~2.273 mA (L shorts at DC)
        note="R-L loop; checks L handled as DC short.",
    ),

    # Stress circuit: V + a 5-resistor series ring (6 components / 6 nets).
    # More components and wires => more chances for the error model to fragment.
    CircuitSpec(
        name="ring6_r",
        comps=[_V("5", 120, 300, size=300),
               _R("1k", 280, 140, orient="H", size=180),
               _R("1k", 500, 140, orient="H", size=180),
               _R("1k", 680, 300, size=300),
               _R("1k", 500, 460, orient="H", size=180),
               _R("1k", 280, 460, orient="H", size=180)],
        nets=[[(0, 0), (1, 0)],   # V.top   - R1.left   (y=140)
              [(1, 1), (2, 0)],   # R1.right - R2.left   (y=140)
              [(2, 1), (3, 0)],   # R2.right - R3.top    (y=140)
              [(3, 1), (4, 1)],   # R3.bot  - R4.right   (y=460)
              [(4, 0), (5, 1)],   # R4.left - R5.right   (y=460)
              [(5, 0), (0, 1)]],  # R5.left - V.bot      (y=460)
        expect_mA=1.0,            # 5V / 5k
        note="6-component ring; the join-under-error stress case.",
    ),

    # Forward-biased diode loop: V - R - D. Exercises the D/DMOD SPICE path.
    # I = (5 - V_D)/1k with V_D ~ 0.69V for DMOD (Is=1e-14, N=1) -> ~4.31 mA.
    CircuitSpec(
        name="diode_r",
        comps=[_V("5", 120, 240, size=200),
               _R("1k", 300, 140, orient="H"),
               _D("D_default", 480, 240, size=200)],
        nets=[[(0, 0), (1, 0)],   # V.top  - R.left
              [(1, 1), (2, 0)],   # R.right - D.anode (top)
              [(2, 1), (0, 1)]],  # D.cathode - V.bot
        expect_mA=4.31,
        note="Forward-biased diode loop; checks the D path + DMOD model.",
    ),

    # Divider with a ground symbol on the bottom net. Exercises the gnd
    # single-pin component and SpiceGenerator's node-0 remap.
    CircuitSpec(
        name="gnd_ref",
        comps=[_V("5", 120, 240, size=200),
               _R("1k", 300, 140, orient="H"),
               _R("1k", 480, 240, size=200),
               Comp("gnd", "0", 300, 400, size=40)],
        nets=[[(0, 0), (1, 0)],
              [(1, 1), (2, 0)],
              [(2, 1), (0, 1), (3, 0)]],   # bottom net carries the gnd symbol
        expect_mA=2.5,            # 5V / 2k (gnd only renames the node)
        note="Divider + gnd symbol; checks node-0 remap and 1-pin components.",
    ),

    # Two opposing sources in one loop: 5V and 3V (same vertical orientation,
    # so the second source opposes around the loop) over 2k -> 1 mA. Exercises
    # the multi-source sim check (ALL source currents must match the oracle).
    CircuitSpec(
        name="two_sources",
        comps=[_V("5", 120, 240, size=200),
               _R("1k", 300, 140, orient="H"),
               _V("3", 480, 240, size=200),
               _R("1k", 300, 340, orient="H")],
        nets=[[(0, 0), (1, 0)],   # V1.top - R1.left
              [(1, 1), (2, 0)],   # R1.right - V2.top
              [(2, 1), (3, 1)],   # V2.bot - R2.right
              [(3, 0), (0, 1)]],  # R2.left - V1.bot
        expect_mA=1.0,            # (5 - 3)V / 2k
        note="Opposing 5V/3V sources in one loop; multi-source oracle check.",
    ),

    # Two INDEPENDENT loops 100px apart - the over-merge bait. Ground truth has
    # NO cross-loop pairs, so any join that bridges the gap loses precision.
    # Note a single cross-short does NOT change DC currents (one wire is not a
    # return path), so this failure is invisible to sim_ok - precision is the
    # only metric that catches it. That asymmetry is the point of this circuit.
    CircuitSpec(
        name="dense_pair",
        comps=[_V("5", 120, 220, size=120), _R("1k", 220, 220, size=120),
               _V("5", 320, 220, size=120), _R("1k", 420, 220, size=120)],
        nets=[[(0, 0), (1, 0)], [(0, 1), (1, 1)],     # loop A
              [(2, 0), (3, 0)], [(2, 1), (3, 1)]],    # loop B
        expect_mA=5.0,            # each loop: 5V / 1k
        note="Two independent loops side by side; GT has no cross pairs.",
    ),

    # ── Angled circuits (rotation in degrees) ──────────────────────────
    # Tests that the harness correctly handles rotated OBBs and pin positions.
    # Pins are computed from angle + orient, not from the axis-aligned bbox.

    # V-shaped series: V1(vertical) + R1(30°) + R2(-30°) in a V loop.
    # Wires are diagonal — the join must handle non-axis-aligned segments.
    CircuitSpec(
        name="angled_v",
        comps=[_V("5", 200, 250, size=160),
               _R("1k", 380, 150, orient="H", size=160, angle=30),
               _R("1k", 380, 350, orient="H", size=160, angle=-30)],
        nets=[[(0, 0), (1, 0)],   # V1.top → R1.pin0
              [(1, 1), (2, 1)],   # R1.pin1 → R2.pin1
              [(2, 0), (0, 1)]],  # R2.pin0 → V1.bot
        expect_mA=2.5,            # 5V / 2k
        note="V-shaped series loop; components at ±30°.",
    ),

    # Diamond ring: V1 + 4×R at 0°, 45°, 0°, -45° — a non-rectangular ring.
    CircuitSpec(
        name="angled_ring4",
        comps=[_V("5", 200, 300, size=160),
               _R("1k", 400, 150, orient="H", size=160, angle=45),
               _R("1k", 600, 300, size=160),
               _R("1k", 400, 450, orient="H", size=160, angle=-45)],
        nets=[[(0, 0), (1, 0)],   # V1.top → R1.pin0
              [(1, 1), (2, 0)],   # R1.pin1 → R2.top
              [(2, 1), (3, 1)],   # R2.bot → R3.pin1
              [(3, 0), (0, 1)]],  # R3.pin0 → V1.bot
        expect_mA=1.667,           # 5V / 3k (V1 + 3 resistors in series)
        note="Diamond-shaped ring; 4 components at mixed angles.",
    ),

    # Parallel with angled resistors: V1 + R1(45°) + R2(-45°) sharing both nets.
    CircuitSpec(
        name="angled_parallel",
        comps=[_V("5", 150, 250, size=160),
               _R("1k", 400, 150, orient="H", size=160, angle=45),
               _R("1k", 400, 350, orient="H", size=160, angle=-45)],
        nets=[[(0, 0), (1, 0), (2, 0)],   # top rail
              [(0, 1), (1, 1), (2, 1)]],   # bottom rail
        expect_mA=5.0,            # 5V / 1k (SPICE sees series, not parallel — known issue)
        note="Parallel resistors at ±45°; multi-terminal angled nets.",
    ),
]

CATALOG_BY_NAME = {c.name: c for c in CATALOG}

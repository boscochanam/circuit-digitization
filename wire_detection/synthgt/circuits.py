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
]

CATALOG_BY_NAME = {c.name: c for c in CATALOG}

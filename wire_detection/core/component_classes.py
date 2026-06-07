"""Shared component class mappings.

Single source of truth for class-ID → type-name and type-name → SPICE-prefix
lookups.  Every module that needs these (process.py, spice.py, netlist.py,
join_strategies.py, benchmarks, …) should import from here instead of defining
its own copy.
"""
from __future__ import annotations

# Class-ID → type-name  (from Roboflow data.yaml — 58 classes)
COMPONENT_TYPES: dict[int, str] = {
    0: "and", 1: "antenna", 2: "capacitor-adjustable", 3: "capacitor-polarized",
    4: "capacitor-unpolarized", 5: "crossover", 6: "crystal", 7: "diac",
    8: "diode", 9: "diode-LED", 10: "diode-thyrector", 11: "diode-zener",
    12: "fuse", 13: "gnd", 14: "inductor", 15: "inductor-ferrite",
    16: "IC", 17: "IC-NE555", 18: "IC-voltage-reg", 19: "junction",
    20: "lamp", 21: "magnetic", 22: "mechanical", 23: "microphone",
    24: "motor", 25: "nand", 26: "nor", 27: "not",
    28: "opamp", 29: "opamp-schmitt", 30: "optical", 31: "optocoupler",
    32: "or", 33: "probe", 34: "probe-current", 35: "probe-voltage",
    36: "relay", 37: "resistor", 38: "resistor-adjustable", 39: "resistor-photo",
    40: "socket", 41: "speaker", 42: "switch", 43: "terminal",
    44: "text", 45: "thyristor", 46: "transformer", 47: "transistor-BJT",
    48: "transistor-FET", 49: "transistor-photo", 50: "triac", 51: "unknown",
    52: "varistor", 53: "voltage-AC", 54: "voltage-battery", 55: "voltage-DC",
    56: "vss", 57: "xor",
}

PREFIX_MAP: dict[str, str] = {
    "resistor": "R", "capacitor-unpolarized": "C", "capacitor-polarized": "C",
    "capacitor-adjustable": "C", "inductor": "L", "inductor-ferrite": "L",
    "diode": "D", "diode-LED": "D", "diode-zener": "D", "diode-thyrector": "D",
    "transistor-BJT": "Q", "transistor-FET": "Q", "transistor-pnp": "Q",
    "voltage-DC": "V", "voltage-AC": "V", "voltage-battery": "V",
    "gnd": "GND", "junction": "J", "terminal": "T", "text": "TXT",
    "IC": "U", "IC-NE555": "U", "IC-voltage-reg": "U",
    "opamp": "U", "opamp-schmitt": "U",
}

SIMULATABLE_PREFIXES: set[str] = {"R", "C", "L", "V", "D", "Q", "U"}

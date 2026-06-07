"""SPICE netlist generation from circuit netlist data."""
from __future__ import annotations

import re

from wire_detection.core.netlist import Netlist


COMPONENT_NAMES: dict[int, str] = {
    0: "and", 1: "antenna", 2: "capacitor-adjustable", 3: "capacitor-polarized",
    4: "capacitor-unpolarized", 5: "crossover", 6: "crystal", 7: "diac",
    8: "diode", 9: "diode-light_emitting", 10: "diode-thyrector", 11: "diode-zener",
    12: "fuse", 13: "gnd", 14: "inductor", 15: "inductor-ferrite",
    16: "integrated_circuit", 17: "integrated_circuit-ne555",
    18: "integrated_circuit-voltage_regulator", 19: "junction", 20: "lamp",
    21: "magnetic", 22: "mechanical", 23: "microphone", 24: "motor",
    25: "nand", 26: "not", 27: "operational_amplifier", 28: "optocoupler",
    29: "or", 30: "potentiometer", 31: "probe", 32: "relay",
    33: "resistor", 34: "resistor-adjustable", 35: "switch",
    36: "thermistor", 37: "transformer", 38: "transistor",
    39: "transistor-pnp", 40: "triac", 41: "varistor",
    42: "voltage_source", 43: "wire", 44: "terminal",
}

PREFIX_MAP: dict[str, str] = {
    "resistor": "R",
    "resistor-adjustable": "R",
    "capacitor-unpolarized": "C",
    "capacitor-polarized": "C",
    "capacitor-adjustable": "C",
    "inductor": "L",
    "inductor-ferrite": "L",
    "diode": "D",
    "diode-zener": "D",
    "diode-light_emitting": "D",
    "diode-thyrector": "D",
    "diac": "D",
    "voltage_source": "V",
    "transistor": "Q",
    "transistor-pnp": "Q",
    "integrated_circuit": "U",
    "integrated_circuit-ne555": "U",
    "integrated_circuit-voltage_regulator": "U",
    "operational_amplifier": "U",
    "and": "U",
    "nand": "U",
    "or": "U",
    "not": "U",
    "fuse": "F",
    "lamp": "L",
    "switch": "S",
    "relay": "S",
    "motor": "M",
    "crystal": "X",
    "microphone": "U",
    "optocoupler": "U",
    "triac": "T",
    "thermistor": "R",
    "varistor": "R",
    "potentiometer": "R",
    "transformer": "L",
    "crossover": "X",
    "antenna": "E",
    "magnetic": "L",
    "mechanical": "M",
    "junction": "J",
    "terminal": "T",
    "probe": "P",
}

DEFAULT_VALUES: dict[str, str] = {
    "resistor": "1000",
    "resistor-adjustable": "1000",
    "capacitor-unpolarized": "1e-6",
    "capacitor-polarized": "1e-6",
    "capacitor-adjustable": "1e-6",
    "inductor": "1e-3",
    "inductor-ferrite": "1e-3",
    "diode": "D_default",
    "diode-zener": "D_default",
    "diode-light_emitting": "D_default",
    "diode-thyrector": "D_default",
    "diac": "D_default",
    "voltage_source": "DC 5",
    "fuse": "1e-3",
    "lamp": "100",
    "crystal": "1e-6",
    "motor": "1",
    "switch": "1",
    "relay": "1",
    "probe": "1",
    "antenna": "1",
    "magnetic": "1e-3",
    "mechanical": "1",
    "microphone": "1",
    "transformer": "1",
    "potentiometer": "1000",
    "thermistor": "1000",
    "varistor": "1000",
    "crossover": "1",
    "transistor": "100",
    "transistor-pnp": "100",
    "integrated_circuit": "1",
    "integrated_circuit-ne555": "1",
    "integrated_circuit-voltage_regulator": "1",
    "operational_amplifier": "1",
    "and": "1",
    "nand": "1",
    "or": "1",
    "not": "1",
    "optocoupler": "1",
    "triac": "1",
    "junction": "1",
    "terminal": "1",
}

# SI prefix multipliers for value parsing
_SI_PREFIXES: dict[str, float] = {
    "t": 1e12, "g": 1e9, "meg": 1e6, "m": 1e-3,
    "k": 1e3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15,
}


def _parse_value(raw: str) -> str:
    """Parse a human-readable value like '10k', '4.7u', '100n', '5V' into a
    SPICE-compatible numeric string.

    Supports SI suffixes (T/G/Meg/k/m/u/n/p/f), bare numbers, voltage suffix,
    and already-numeric strings like '1e-6'.
    """
    s = raw.strip()
    if not s:
        return "1"

    s = re.sub(r"[Vv]$", "", s)

    try:
        float(s)
        return s
    except ValueError:
        pass

    m = re.match(r"^([0-9]*\.?[0-9]+)\s*([a-zA-Z]+)$", s)
    if m:
        num_str, suffix = m.group(1), m.group(2).lower()
        multiplier = _SI_PREFIXES.get(suffix)
        if multiplier is not None:
            try:
                val = float(num_str) * multiplier
                if abs(val) < 0.01 or abs(val) >= 1e6:
                    return f"{val:.6g}"
                return f"{val:.6f}".rstrip("0").rstrip(".")
            except (ValueError, OverflowError):
                pass

    return s


class SpiceGenerator:
    def __init__(self, component_names: dict[int, str] | None = None):
        self._component_names = component_names or COMPONENT_NAMES
        self._prefix_counters: dict[str, int] = {}

    def _get_next_name(self, prefix: str) -> str:
        self._prefix_counters[prefix] = self._prefix_counters.get(prefix, 0) + 1
        return f"{prefix}{self._prefix_counters[prefix]}"

    def _get_prefix(self, type_name: str) -> str | None:
        return PREFIX_MAP.get(type_name)

    def _get_default_value(self, type_name: str) -> str:
        return DEFAULT_VALUES.get(type_name, "1")

    def _get_type_name(self, cls_id: int) -> str:
        return self._component_names.get(cls_id, "resistor")

    def generate(
        self,
        components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]] | None = None,
        netlist: Netlist | None = None,
        value_overrides: dict[str, str] | None = None,
    ) -> str:
        if components is None:
            components = []
        if netlist is None:
            netlist = Netlist()

        self._prefix_counters = {}
        lines: list[str] = []
        lines.append("* SPICE netlist generated by Circuit Digitization")

        if not components or not netlist.nodes:
            lines.append(".end")
            return "\n".join(lines)

        gnd_node = self._find_gnd_node(components, netlist)
        node_remap: dict[int, str] = {}
        if gnd_node is not None:
            node_remap[gnd_node] = "0"
        for node in netlist.nodes:
            if node.node_id not in node_remap:
                node_remap[node.node_id] = f"N{node.node_id}"
        pin_map = self._build_pin_map(netlist)

        device_lines: list[str] = []
        model_lines: set[str] = set()
        skipped: dict[str, int] = {}
        has_vsrc = False

        for i, comp in enumerate(components):
            type_name = self._get_type_name(comp[0])
            if type_name == "gnd":
                continue
            prefix = self._get_prefix(type_name)
            if prefix is None:
                skipped[type_name] = skipped.get(type_name, 0) + 1
                continue

            pin_nodes: list[str] = []
            for pin_idx in range(50):
                key = (i, pin_idx)
                if key in pin_map:
                    pin_nodes.append(node_remap.get(pin_map[key], f"N{pin_map[key]}"))
                else:
                    break
            if not pin_nodes:
                continue

            # Emit only devices ngspice can simulate with a known model.
            if type_name.startswith("diode") or type_name == "diac":
                a = pin_nodes[0]
                k = pin_nodes[1] if len(pin_nodes) > 1 else "0"
                if a == k:  # self-loop short from over-merge — skip
                    skipped[type_name] = skipped.get(type_name, 0) + 1
                    continue
                model = "LEDMOD" if type_name == "diode-light_emitting" else "DMOD"
                device_lines.append(f"D{i + 1} {a} {k} {model}")
                model_lines.add(".model LEDMOD D(Is=1e-14 N=1.5)" if model == "LEDMOD"
                                else ".model DMOD D(Is=1e-14 N=1)")
            elif type_name in ("transistor", "transistor-pnp"):
                c = pin_nodes[0]
                b = pin_nodes[1] if len(pin_nodes) > 1 else "0"
                e = pin_nodes[2] if len(pin_nodes) > 2 else "0"
                if c == b == e:
                    skipped[type_name] = skipped.get(type_name, 0) + 1
                    continue
                mdl = "QPNP" if type_name == "transistor-pnp" else "QNPN"
                device_lines.append(f"Q{i + 1} {c} {b} {e} {mdl}")
                model_lines.add(".model QPNP PNP(Is=1e-14 Bf=100 Vaf=50)" if mdl == "QPNP"
                                else ".model QNPN NPN(Is=1e-14 Bf=100 Vaf=50)")
            elif type_name == "voltage_source":
                p = pin_nodes[0]
                n = pin_nodes[1] if len(pin_nodes) > 1 else "0"
                if p == n:
                    skipped[type_name] = skipped.get(type_name, 0) + 1
                    continue
                spice_name = f"V{i + 1}"
                if value_overrides and str(i) in value_overrides:
                    v_val = _parse_value(value_overrides[str(i)])
                else:
                    v_val = "5"
                device_lines.append(f"{spice_name} {p} {n} DC {v_val}")
                has_vsrc = True
            elif prefix in ("R", "C", "L"):
                spice_name = f"{prefix}{i + 1}"
                if value_overrides and str(i) in value_overrides:
                    value = _parse_value(value_overrides[str(i)])
                else:
                    value = self._get_default_value(type_name)
                if len(pin_nodes) >= 2 and pin_nodes[0] != pin_nodes[1]:
                    device_lines.append(f"{spice_name} {pin_nodes[0]} {pin_nodes[1]} {value}")
                else:
                    device_lines.append(f"{spice_name} {pin_nodes[0]} 0 {value}")
            else:
                # U (IC/opamp/logic), X (subckt), F (fuse), S (switch), M (motor), etc.
                # — no SPICE model available; skip so the netlist stays runnable.
                skipped[type_name] = skipped.get(type_name, 0) + 1

        if not device_lines:
            lines.append("* no simulatable primitives (R/C/L/V/D/Q) in this circuit")
            lines.append(".end")
            return "\n".join(lines)

        # Energize the circuit for the DC operating point. A hand-drawn extraction
        # usually fragments into several disconnected sub-circuits; a single source
        # would leave every island but one at 0V (the rest only tied to ground through
        # rshunt). So inject a 5V TEST source into each island that has none — a
        # correctly-connected circuit is one island and still gets exactly one source.
        # (Illustrative: these test sources are not the real supply.)
        import re as _re
        from collections import defaultdict as _dd
        _node_re = _re.compile(r"^(0|N\d+)$")
        _parent: dict[str, str] = {}

        def _find(x: str) -> str:
            _parent.setdefault(x, x)
            root = x
            while _parent[root] != root:
                root = _parent[root]
            while _parent[x] != root:
                _parent[x], x = root, _parent[x]
            return root

        def _union(a: str, b: str) -> None:
            ra, rb = _find(a), _find(b)
            if ra != rb:
                _parent[ra] = rb

        def _nodes_of(line: str) -> list[str]:
            return [t for t in line.split()[1:] if _node_re.match(t)]

        sourced_roots: set[str] = set()
        for ln in device_lines:
            if ln.startswith("*"):
                continue
            ns = _nodes_of(ln)
            for n in ns[1:]:
                _union(ns[0], n)
            if ln.split()[0].startswith("V"):  # an existing source marks its island
                for n in ns:
                    sourced_roots.add(_find(n))

        island_nodes: dict[str, list[str]] = _dd(list)
        for n in list(_parent.keys()):
            island_nodes[_find(n)].append(n)

        injected = 0
        for root, nodes_in in island_nodes.items():
            if root in sourced_roots:
                continue
            non0 = [n for n in nodes_in if n != "0"]
            if not non0:  # pure-ground island, nothing to drive
                continue
            injected += 1
            device_lines.append(f"VTEST{injected} {non0[0]} 0 DC 5")
            # If the island has no ground return, current can't flow (rshunt>>R) and
            # every node sits at ~5V. Tie a DIFFERENT node to ground so the source
            # drives current through the island's components -> a real voltage gradient.
            if "0" not in nodes_in and len(non0) >= 2:
                device_lines.append(f"VRET{injected} {non0[-1]} 0 DC 0")
        if injected:
            device_lines.append(
                f"* injected {injected} 5V test source(s) (+ground returns) to energize "
                f"{'the circuit' if injected == 1 and not has_vsrc else 'disconnected sub-circuits'} (illustrative)"
            )

        lines.extend(device_lines)
        lines.extend(sorted(model_lines))
        # rshunt ties every node to ground through a huge resistor so the DC
        # operating point stays solvable despite floating/degenerate nodes from
        # imperfect joins (avoids "singular matrix" / "no DC path to ground").
        lines.append(".options rshunt=1e12")
        if skipped:
            lines.append("* skipped (no SPICE model): "
                         + ", ".join(f"{t}x{c}" for t, c in sorted(skipped.items())))
        lines.append(".op")
        lines.append(".end")
        return "\n".join(lines)

    def _find_gnd_node(
        self,
        components: list[tuple[int, list[tuple[int, int]], tuple[int, int, int, int]]],
        netlist: Netlist,
    ) -> int | None:
        for i, comp in enumerate(components):
            cls_id = comp[0]
            type_name = self._get_type_name(cls_id)
            if type_name == "gnd":
                for node in netlist.nodes:
                    for pin in node.pins:
                        if pin.component_idx == i:
                            return node.node_id
        return None

    def _build_pin_map(self, netlist: Netlist) -> dict[tuple[int, int], int]:
        pin_map: dict[tuple[int, int], int] = {}
        for node in netlist.nodes:
            for pin in node.pins:
                pin_map[(pin.component_idx, pin.pin_idx)] = node.node_id
        return pin_map

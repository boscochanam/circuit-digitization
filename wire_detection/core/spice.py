"""SPICE netlist generation from circuit netlist data."""
from __future__ import annotations

import re

from wire_detection.core.component_classes import (
    COMPONENT_TYPES,
    PREFIX_MAP,
    SIMULATABLE_PREFIXES,
)
from wire_detection.core.netlist import Netlist

# Backward-compatible alias so existing ``from spice import COMPONENT_NAMES``
# keeps working.  New code should import COMPONENT_TYPES directly.
COMPONENT_NAMES = COMPONENT_TYPES

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
    "diode-LED": "D_default",
    "diode-thyrector": "D_default",
    "diac": "D_default",
    "voltage-DC": "DC 5",
    "voltage-AC": "AC 5",
    "voltage-battery": "DC 5",
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
    "varistor": "1000",
    "crossover": "1",
    "transistor-BJT": "100",
    "transistor-FET": "100",
    "IC": "1",
    "IC-NE555": "1",
    "IC-voltage-reg": "1",
    "opamp": "1",
    "opamp-schmitt": "1",
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
        """Generate a SPICE netlist from circuit component and netlist data.

        Builds a runnable ngspice netlist by mapping detected circuit components
        to SPICE device statements. The algorithm:

        1. **Node remapping**: Maps internal node IDs to SPICE node names (GND →
           "0", others → "N{id}"). Locates the ground node from any component
           typed "gnd".

        2. **Pin mapping**: Inverts the netlist structure into a
           (component_idx, pin_idx) → node_id lookup so each component's pins
           can be resolved to SPICE node names.

        3. **Device emission**: For each component, resolves the SPICE prefix
           (R/C/L for passives, V for sources, D for diodes, Q for transistors)
           and emits the appropriate device line. Components without SPICE models
           (ICs, motors, etc.) are skipped. Switches are modeled as tiny
           resistors (0.001Ω). Diodes get DMOD/LEDMOD subcircuit models;
           transistors get NPN/PNP models.

        4. **Island energisation**: Uses union-find to detect disconnected
           sub-circuits (islands). Injects 5V test sources (+ ground returns)
           into islands that lack a voltage source, so every island has a DC
           operating point solvable by ngspice.

        5. **Grounding**: Adds ``.options rshunt=1e12`` so floating/degenerate
           nodes from imperfect joins don't cause singular-matrix errors.

        Args:
            components: List of (cls_id, vertices, bbox) tuples from the
                component detector. Each bbox is (x1, y1, x2, y2).
            netlist: A Netlist object with .nodes (NetNode list) and
                .pin_to_node mapping. If None, an empty netlist is assumed.
            value_overrides: Optional dict mapping SPICE device names
                (e.g. "R1", "C3") to human-readable value strings
                (e.g. "10k", "4.7u") that override defaults.

        Returns:
            A complete SPICE netlist string (lines joined by newlines)
            ready to write to a .cir file and simulate with ngspice.
            Includes a header comment, device lines, .model statements,
            .options, .op, and .end directives.
        """
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
            if type_name == "switch":
                pin_nodes: list[str] = []
                for pin_idx in range(50):
                    key = (i, pin_idx)
                    if key in pin_map:
                        pin_nodes.append(node_remap.get(pin_map[key], f"N{pin_map[key]}"))
                    else:
                        break
                if len(pin_nodes) >= 2 and pin_nodes[0] != pin_nodes[1]:
                    device_lines.append(f"R{i + 1} {pin_nodes[0]} {pin_nodes[1]} 0.001")
                continue
            prefix = self._get_prefix(type_name)
            if prefix is None:
                skipped[type_name] = skipped.get(type_name, 0) + 1
                continue

            pin_nodes = []
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
                model = "LEDMOD" if type_name == "diode-LED" else "DMOD"
                device_lines.append(f"D{i + 1} {a} {k} {model}")
                model_lines.add(".model LEDMOD D(Is=1e-14 N=1.5)" if model == "LEDMOD"
                                else ".model DMOD D(Is=1e-14 N=1)")
            elif type_name in ("transistor-BJT", "transistor-FET"):
                c = pin_nodes[0]
                b = pin_nodes[1] if len(pin_nodes) > 1 else "0"
                e = pin_nodes[2] if len(pin_nodes) > 2 else "0"
                if c == b == e:
                    skipped[type_name] = skipped.get(type_name, 0) + 1
                    continue
                mdl = "QPNP" if type_name == "transistor-FET" else "QNPN"
                device_lines.append(f"Q{i + 1} {c} {b} {e} {mdl}")
                model_lines.add(".model QPNP PNP(Is=1e-14 Bf=100 Vaf=50)" if mdl == "QPNP"
                                else ".model QNPN NPN(Is=1e-14 Bf=100 Vaf=50)")
            elif type_name in ("voltage-DC", "voltage-AC", "voltage-battery"):
                p = pin_nodes[0]
                n = pin_nodes[1] if len(pin_nodes) > 1 else "0"
                if p == n:
                    skipped[type_name] = skipped.get(type_name, 0) + 1
                    continue
                spice_name = f"V{i + 1}"
                if value_overrides and spice_name in value_overrides:
                    v_val = _parse_value(value_overrides[spice_name])
                else:
                    v_val = "5"
                device_lines.append(f"{spice_name} {p} {n} DC {v_val}")
                has_vsrc = True
            elif prefix in ("R", "C", "L"):
                spice_name = f"{prefix}{i + 1}"
                if value_overrides and spice_name in value_overrides:
                    value = _parse_value(value_overrides[spice_name])
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

        # Re-resolve roots after all unions — earlier _find() calls may have
        # returned a root that later unions changed (union-find root mutation).
        sourced_roots = {_find(r) for r in sourced_roots}

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

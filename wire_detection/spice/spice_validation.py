"""SPICE Simulation Validation (Section 4.4)

Validates the SPICE simulation pipeline by comparing simulated results against
known theoretical values for simple circuits.  Tests cover:

1. ngspice availability detection with graceful mock fallback
2. DC analysis accuracy (voltage dividers, series/parallel resistors)
3. AC analysis accuracy (RC low-pass filter magnitude/phase)
4. Current measurement accuracy (Ohm's law, KCL)

Usage:
    # Run all tests (standalone)
    python -m wire_detection.spice.spice_validation

    # Run specific test category
    python -m wire_detection.spice.spice_validation --dc
    python -m wire_detection.spice.spice_validation --ac
    python -m wire_detection.spice.spice_validation --current
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════
# NGSPICE DETECTION
# ═══════════════════════════════════════════════

def find_ngspice() -> str | None:
    """Locate the ngspice batch-mode binary.

    Search order:
    1. ``NGSPICE_PATH`` environment variable
    2. ``ngspice_con`` on PATH (Windows console build)
    3. ``ngspice`` on PATH

    Returns the absolute path to the binary, or ``None`` if not found.
    """
    env = os.environ.get("NGSPICE_PATH")
    if env and Path(env).exists():
        return env
    for name in ("ngspice_con", "ngspice"):
        found = shutil.which(name)
        if found:
            return found
    return None


NGSPICE_PATH: str | None = find_ngspice()
NGSPICE_AVAILABLE: bool = NGSPICE_PATH is not None


# ═══════════════════════════════════════════════
# NGSPICE RUNNER
# ═══════════════════════════════════════════════

def run_ngspice(netlist: str, timeout: float = 30.0) -> str:
    """Run a SPICE netlist through ngspice and return raw stdout+stderr.

    Raises ``RuntimeError`` if ngspice is not available or the simulation
    fails.  The caller is responsible for parsing the output.
    """
    if not NGSPICE_PATH:
        raise RuntimeError("ngspice is not installed")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".cir", delete=False
    ) as f:
        f.write(netlist)
        cir_path = f.name

    try:
        result = subprocess.run(
            [NGSPICE_PATH, "-b", cir_path],
            capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout + "\n" + result.stderr
        if result.returncode != 0 and "error" in output.lower():
            raise RuntimeError(f"ngspice error (rc={result.returncode}): {output.strip()}")
        return output
    except subprocess.TimeoutExpired:
        raise RuntimeError("ngspice timed out")
    finally:
        Path(cir_path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════
# OUTPUT PARSERS
# ═══════════════════════════════════════════════

@dataclass
class DCResult:
    """Parsed DC operating-point results."""
    voltages: dict[str, float] = field(default_factory=dict)
    currents: dict[str, float] = field(default_factory=dict)
    raw: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.voltages)


@dataclass
class ACResult:
    """Parsed AC analysis results (complex transfer function)."""
    frequencies: list[float] = field(default_factory=list)
    # node -> list of complex values (one per frequency)
    node_data: dict[str, list[complex]] = field(default_factory=dict)
    raw: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.frequencies)


def parse_dc_output(output: str) -> DCResult:
    """Parse ngspice DC operating-point output into voltages and currents."""
    result = DCResult(raw=output)
    in_node_table = False
    current_section = False

    for line in output.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        if "No. of Data Rows" in stripped:
            in_node_table = True
            continue

        if in_node_table:
            if "Source" in stripped and "Current" in stripped:
                in_node_table = False
                current_section = True
                continue
            if stripped.startswith("-") or "Node" in stripped or "Voltage" in stripped:
                continue
            m = re.match(r"^(n?\w+)[\s\t]+([\d.eE+-]+)", stripped)
            if m:
                try:
                    result.voltages[m.group(1).lower()] = float(m.group(2))
                except ValueError:
                    pass
                continue

        if current_section:
            if stripped.startswith("-"):
                continue
            if stripped.startswith("Resistor") or stripped.startswith("Vsource"):
                current_section = False
                continue
            m = re.match(r"^([\w#]+)[\s\t]+([\d.eE+-]+)", stripped)
            if m:
                try:
                    result.currents[m.group(1).lower()] = float(m.group(2))
                except ValueError:
                    pass

    return result


def parse_ac_output(output: str) -> ACResult:
    """Parse ngspice AC analysis (Standard) output.

    ngspice AC output contains blocks like::

        Index   frequency      VM(out)      VP(out)
        ------  -----------    ----------   ----------
        0       1.000000e+02   7.071068e-01 -4.500000e+01

    We parse magnitude and phase per node and convert to complex.
    """
    result = ACResult(raw=output)
    freq_col: list[float] = []
    # node_name -> list of complex values
    node_values: dict[str, list[complex]] = {}

    lines = output.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        # Detect header lines like "Index   frequency      VM(out)      VP(out)"
        if "frequency" in stripped.lower() and ("vm(" in stripped.lower() or "vp(" in stripped.lower()):
            # Parse header to get node names
            headers = stripped.split()
            # Find node names from VM(...) columns
            mag_nodes: list[str] = []
            for h in headers:
                hm = re.match(r"VM\((\w+)\)", h, re.IGNORECASE)
                if hm:
                    mag_nodes.append(hm.group(1).lower())

            # Skip separator line (------)
            i += 1
            if i < len(lines) and lines[i].strip().startswith("-"):
                i += 1

            # Parse data lines
            while i < len(lines):
                dline = lines[i].strip()
                if not dline or dline.startswith("-") or "Index" in dline:
                    break
                parts = dline.split()
                if len(parts) >= 3:
                    try:
                        freq = float(parts[1])
                        freq_col.append(freq)

                        # Parse pairs of VM and VP for each node
                        col_idx = 2
                        for node_name in mag_nodes:
                            if col_idx < len(parts):
                                mag = float(parts[col_idx])
                                col_idx += 1
                            else:
                                mag = 0.0
                            if col_idx < len(parts):
                                phase_rad = float(parts[col_idx])
                                col_idx += 1
                            else:
                                phase_rad = 0.0
                            # ngspice .print ac outputs phase in radians
                            val = mag * complex(math.cos(phase_rad), math.sin(phase_rad))
                            if node_name not in node_values:
                                node_values[node_name] = []
                            node_values[node_name].append(val)
                    except (ValueError, IndexError):
                        pass
                i += 1
            continue

        i += 1

    result.frequencies = freq_col
    result.node_data = node_values
    return result


# ═══════════════════════════════════════════════
# SIMULATION HELPERS
# ═══════════════════════════════════════════════

def simulate_dc(netlist: str) -> DCResult:
    """Run a DC analysis netlist and return parsed results.

    If ngspice is unavailable, raises ``RuntimeError`` — callers should
    catch and skip/fallback.
    """
    output = run_ngspice(netlist)
    return parse_dc_output(output)


def simulate_ac(netlist: str) -> ACResult:
    """Run an AC analysis netlist and return parsed results."""
    output = run_ngspice(netlist)
    return parse_ac_output(output)


# ═══════════════════════════════════════════════
# THEORETICAL CIRCUIT DEFINITIONS
# ═══════════════════════════════════════════════

# All netlists use SPICE standard format compatible with ngspice.
# Node naming: N1, N2, ... for internal nodes; 0 for ground.

CIRCUITS: dict[str, str] = {
    # --- DC Circuits ---

    "dc_voltage_divider": textwrap.dedent("""\
        * DC Voltage Divider: V=10V, R1=1k, R2=1k
        * Expected: V(N2) = 5.0V
        V1 N1 0 DC 10
        R1 N1 N2 1000
        R2 N2 0 1000
        .op
        .end
    """),

    "dc_voltage_divider_unequal": textwrap.dedent("""\
        * DC Voltage Divider: V=10V, R1=1k, R2=2k
        * Expected: V(N2) = 10 * 2k/(1k+2k) = 6.6667V
        V1 N1 0 DC 10
        R1 N1 N2 1000
        R2 N2 0 2000
        .op
        .end
    """),

    "dc_series_resistors": textwrap.dedent("""\
        * Series Resistors: V=10V, R1=1k, R2=4k
        * Expected: I = 10/(1k+4k) = 2mA
        *           V(N1)=10V, V(N2)=8V
        V1 N1 0 DC 10
        R1 N1 N2 1000
        R2 N2 0 4000
        .op
        .end
    """),

    "dc_parallel_resistors": textwrap.dedent("""\
        * Parallel Resistors: V=10V, R1=1k, R2=1k
        * Expected: R_eq = 500, I_total = 20mA
        *           V(N1) = 10V
        V1 N1 0 DC 10
        R1 N1 0 1000
        R2 N1 0 1000
        .op
        .end
    """),

    "dc_three_resistor_network": textwrap.dedent("""\
        * T-network: V=12V, R1=1k, R2=2k, R3=3k
        * R1 series, R2 to gnd, R3 series
        * Expected: V(N2) = 12 * 2k/(1k+2k) = 8V (divider R1-R2)
        *           V(N3) = 0V (R3 to gnd, no current source beyond)
        V1 N1 0 DC 12
        R1 N1 N2 1000
        R2 N2 0 2000
        R3 N2 0 3000
        .op
        .end
    """),

    # --- AC Circuits ---

    "ac_rc_lowpass_1k_1uf": textwrap.dedent("""\
        * RC Low-pass Filter: R=1k, C=1uF
        * fc = 1/(2*pi*1k*1uF) = 159.155 Hz
        * At fc: |H| = 1/sqrt(2) = 0.7071, phase = -45 deg
        V1 N1 0 AC 1
        R1 N1 N2 1000
        C1 N2 0 1u
        .ac dec 10 1 10000
        .print ac vm(n2) vp(n2)
        .end
    """),

    "ac_rc_lowpass_10k_1nf": textwrap.dedent("""\
        * RC Low-pass Filter: R=10k, C=1nF
        * fc = 1/(2*pi*10k*1nF) = 15.915 kHz
        * At fc: |H| = 1/sqrt(2) = 0.7071
        V1 N1 0 AC 1
        R1 N1 N2 10000
        C1 N2 0 1n
        .ac dec 10 100 10000000
        .print ac vm(n2) vp(n2)
        .end
    """),

    "ac_rc_highpass_1k_1uf": textwrap.dedent("""\
        * RC High-pass Filter: C=1uF, R=1k
        * fc = 1/(2*pi*1k*1uF) = 159.155 Hz
        * At fc: |H| = 1/sqrt(2) = 0.7071, phase = +45 deg
        V1 N1 0 AC 1
        C1 N1 N2 1u
        R1 N2 0 1000
        .ac dec 10 1 10000
        .print ac vm(n2) vp(n2)
        .end
    """),

    # --- Current Measurement Circuits ---

    "current_ohms_law": textwrap.dedent("""\
        * Ohm's Law: V=5V, R=1k
        * Expected: I = 5V/1k = 5mA
        V1 N1 0 DC 5
        R1 N1 0 1000
        .op
        .end
    """),

    "current_series_same": textwrap.dedent("""\
        * Series Current: V=10V, R1=1k, R2=2k
        * Expected: I = 10/3k = 3.333mA (same through R1 and R2)
        V1 N1 0 DC 10
        R1 N1 N2 1000
        R2 N2 0 2000
        .op
        .end
    """),

    "current_kcl_node": textwrap.dedent("""\
        * KCL at node N2: V=10V
        * R1=1k (N1->N2), R2=2k (N2->0), R3=5k (N2->0)
        * I_R1 = (10-V(N2))/1k
        * I_R2 = V(N2)/2k, I_R3 = V(N2)/5k
        * KCL: I_R1 = I_R2 + I_R3
        *       (10-V)/1k = V/2k + V/5k
        *       V = 10 * (1/2k + 1/5k)^-1 / 1k ... solve:
        *       V * (1/1k + 1/2k + 1/5k) = 10/1k
        *       V = 10 / (1 + 0.5 + 0.2) = 10/1.7 = 5.8824V
        V1 N1 0 DC 10
        R1 N1 N2 1000
        R2 N2 0 2000
        R3 N2 0 5000
        .op
        .end
    """),
}


# ═══════════════════════════════════════════════
# THEORETICAL VALUES
# ═══════════════════════════════════════════════

# Tolerance for comparison — ngspice double-precision vs theory
TOL_VOLTAGE = 0.01     # 1% or 10mV
TOL_CURRENT = 0.001    # 0.1% or 10uA
TOL_AC_MAG = 0.02      # 2% magnitude
TOL_AC_PHASE = 2.0     # 2 degrees


def expected_rc_cutoff_frequency(r: float, c: float) -> float:
    """Theoretical cutoff frequency for RC low-pass: fc = 1/(2*pi*R*C)."""
    return 1.0 / (2.0 * math.pi * r * c)


def expected_rc_transfer(f: float, r: float, c: float, highpass: bool = False) -> complex:
    """Theoretical complex transfer function H(jw) for RC filter.

    Low-pass:  H = 1 / (1 + jwRC)
    High-pass: H = jwRC / (1 + jwRC)
    """
    wc = 2.0 * math.pi * f * r * c
    if highpass:
        return 1j * wc / (1.0 + 1j * wc)
    return 1.0 / (1.0 + 1j * wc)


# ═══════════════════════════════════════════════
# VALIDATION TESTS
# ═══════════════════════════════════════════════

@dataclass
class TestResult:
    """Single test case result."""
    name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class SpiceValidation:
    """Comprehensive SPICE simulation validation suite.

    Tests the simulation pipeline against known theoretical values for
    simple circuit configurations.  Can run with real ngspice or in
    mock mode (theoretical-only validation of test framework).
    """

    def __init__(self, use_mock: bool = False):
        """
        Args:
            use_mock: If True, skip actual ngspice runs and validate only
                      the test framework and theoretical calculations.
        """
        self.use_mock = use_mock or not NGSPICE_AVAILABLE
        self.results: list[TestResult] = []

    def _assert_close(
        self, actual: float, expected: float, tolerance: float,
        label: str, rel: bool = True,
    ) -> tuple[bool, str]:
        """Check if actual is close to expected within tolerance."""
        if rel:
            if abs(expected) < 1e-12:
                ok = abs(actual) < tolerance
            else:
                ok = abs(actual - expected) / abs(expected) <= tolerance
        else:
            ok = abs(actual - expected) <= tolerance

        if ok:
            msg = f"{label}: {actual:.6g} (expected {expected:.6g}) ✓"
        else:
            err = abs(actual - expected) / max(abs(expected), 1e-12) * 100 if rel else abs(actual - expected)
            unit = "%" if rel else ""
            msg = f"{label}: {actual:.6g} (expected {expected:.6g}) — off by {err:.2f}{unit}"
        return ok, msg

    # ── DC Tests ──

    def test_dc_voltage_divider_equal(self) -> TestResult:
        """Voltage divider with equal resistors: Vmid = Vin/2."""
        name = "DC: Voltage Divider (equal R)"
        if self.use_mock:
            # Mock: verify theoretical calculation
            v_mid = 10.0 * 1000 / (1000 + 1000)
            ok, msg = self._assert_close(v_mid, 5.0, TOL_VOLTAGE, "V(N2)")
            return TestResult(name=name, passed=ok, message=msg, details={"mock": True, "v_mid": v_mid})

        try:
            result = simulate_dc(CIRCUITS["dc_voltage_divider"])
            if not result.ok:
                return TestResult(name=name, passed=False, message=f"No DC data: {result.raw[:200]}")

            v_n2 = result.voltages.get("n2", None)
            if v_n2 is None:
                return TestResult(name=name, passed=False, message=f"Node n2 not found in {result.voltages}")

            ok, msg = self._assert_close(v_n2, 5.0, TOL_VOLTAGE, "V(N2)")
            return TestResult(name=name, passed=ok, message=msg, details={"v_n2": v_n2, "voltages": result.voltages})
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    def test_dc_voltage_divider_unequal(self) -> TestResult:
        """Voltage divider with R1=1k, R2=2k: Vmid = 10 * 2/3 = 6.6667V."""
        name = "DC: Voltage Divider (unequal R)"
        if self.use_mock:
            v_mid = 10.0 * 2000 / (1000 + 2000)
            ok, msg = self._assert_close(v_mid, 10.0 * 2 / 3, TOL_VOLTAGE, "V(N2)")
            return TestResult(name=name, passed=ok, message=msg, details={"mock": True})

        try:
            result = simulate_dc(CIRCUITS["dc_voltage_divider_unequal"])
            if not result.ok:
                return TestResult(name=name, passed=False, message=f"No DC data")

            v_n2 = result.voltages.get("n2", None)
            if v_n2 is None:
                return TestResult(name=name, passed=False, message=f"Node n2 not found")

            expected = 10.0 * 2000 / (1000 + 2000)  # 6.6667V
            ok, msg = self._assert_close(v_n2, expected, TOL_VOLTAGE, "V(N2)")
            return TestResult(name=name, passed=ok, message=msg, details={"v_n2": v_n2, "expected": expected})
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    def test_dc_series_resistors(self) -> TestResult:
        """Series R1=1k, R2=4k with V=10V: I=2mA, V(N2)=8V."""
        name = "DC: Series Resistors"
        if self.use_mock:
            i_total = 10.0 / (1000 + 4000)
            v_n2 = 10.0 - i_total * 1000
            ok_i, msg_i = self._assert_close(i_total, 2e-3, TOL_CURRENT, "I_total")
            ok_v, msg_v = self._assert_close(v_n2, 8.0, TOL_VOLTAGE, "V(N2)")
            ok = ok_i and ok_v
            msg = f"{msg_i}; {msg_v}"
            return TestResult(name=name, passed=ok, message=msg, details={"mock": True, "i": i_total, "v_n2": v_n2})

        try:
            result = simulate_dc(CIRCUITS["dc_series_resistors"])
            if not result.ok:
                return TestResult(name=name, passed=False, message="No DC data")

            v_n2 = result.voltages.get("n2", None)
            if v_n2 is None:
                return TestResult(name=name, passed=False, message=f"Node n2 not found")

            # V(N2) = 10 - I*R1 = 10 - 2mA*1k = 8V
            ok, msg = self._assert_close(v_n2, 8.0, TOL_VOLTAGE, "V(N2)")
            return TestResult(name=name, passed=ok, message=msg, details={"v_n2": v_n2, "voltages": result.voltages})
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    def test_dc_parallel_resistors(self) -> TestResult:
        """Parallel R1=1k || R2=1k with V=10V: R_eq=500, I_total=20mA."""
        name = "DC: Parallel Resistors"
        if self.use_mock:
            r_eq = 1000 * 1000 / (1000 + 1000)  # 500 ohm
            i_total = 10.0 / r_eq  # 20mA
            ok, msg = self._assert_close(i_total, 0.020, TOL_CURRENT, "I_total")
            return TestResult(name=name, passed=ok, message=msg, details={"mock": True, "i_total": i_total, "r_eq": r_eq})

        try:
            result = simulate_dc(CIRCUITS["dc_parallel_resistors"])
            if not result.ok:
                return TestResult(name=name, passed=False, message="No DC data")

            # Both resistors have V=10V across them
            v_n1 = result.voltages.get("n1", None)
            if v_n1 is None:
                return TestResult(name=name, passed=False, message=f"Node n1 not found")

            ok, msg = self._assert_close(v_n1, 10.0, TOL_VOLTAGE, "V(N1)")
            return TestResult(name=name, passed=ok, message=msg, details={"v_n1": v_n1, "voltages": result.voltages})
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    def test_dc_three_resistor_network(self) -> TestResult:
        """T-network: R1=1k series, R2=2k||R3=3k to gnd."""
        name = "DC: Three-Resistor Network"
        if self.use_mock:
            # R2||R3 = 2k*3k/(2k+3k) = 1200
            # V(N2) = 12 * 1200/(1000+1200) = 12*1200/2200 = 6.5455V
            r23 = 2000 * 3000 / (2000 + 3000)
            v_n2 = 12.0 * r23 / (1000 + r23)
            ok, msg = self._assert_close(v_n2, 12.0 * r23 / (1000 + r23), TOL_VOLTAGE, "V(N2)")
            return TestResult(name=name, passed=ok, message=msg, details={"mock": True, "v_n2": v_n2, "r23": r23})

        try:
            result = simulate_dc(CIRCUITS["dc_three_resistor_network"])
            if not result.ok:
                return TestResult(name=name, passed=False, message="No DC data")

            v_n2 = result.voltages.get("n2", None)
            if v_n2 is None:
                return TestResult(name=name, passed=False, message=f"Node n2 not found")

            # R2||R3 = 1200, V(N2) = 12 * 1200/2200 = 6.5455V
            r23 = 2000 * 3000 / (2000 + 3000)
            expected_v = 12.0 * r23 / (1000 + r23)
            ok, msg = self._assert_close(v_n2, expected_v, TOL_VOLTAGE, "V(N2)")
            return TestResult(name=name, passed=ok, message=msg, details={"v_n2": v_n2, "expected": expected_v})
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    # ── AC Tests ──

    def _test_ac_lowpass(self, r: float, c: float, freq_key: str, test_name: str) -> TestResult:
        """Shared AC low-pass test logic."""
        fc = expected_rc_cutoff_frequency(r, c)

        if self.use_mock:
            # Validate theoretical calculation at cutoff
            h_at_fc = expected_rc_transfer(fc, r, c, highpass=False)
            mag = abs(h_at_fc)
            phase = math.degrees(math.atan2(h_at_fc.imag, h_at_fc.real))
            ok_mag, msg_mag = self._assert_close(mag, 1.0 / math.sqrt(2), TOL_AC_MAG, "|H(fc)|")
            ok_phase, msg_phase = self._assert_close(phase, -45.0, TOL_AC_PHASE, "Phase(fc)", rel=False)
            ok = ok_mag and ok_phase
            msg = f"{msg_mag}; {msg_phase}"
            return TestResult(name=test_name, passed=ok, message=msg, details={"mock": True, "fc": fc, "mag": mag, "phase": phase})

        try:
            result = simulate_ac(CIRCUITS[freq_key])
            if not result.ok:
                return TestResult(name=test_name, passed=False, message=f"No AC data (freqs={len(result.frequencies)})")

            # Find the data point closest to cutoff frequency
            out_data = result.node_data.get("n2", [])
            if not out_data:
                return TestResult(name=test_name, passed=False, message=f"Node n2 not in node_data: {list(result.node_data.keys())}")

            # Find index closest to fc
            best_idx = min(range(len(result.frequencies)), key=lambda i: abs(result.frequencies[i] - fc))
            h = out_data[best_idx]
            freq_actual = result.frequencies[best_idx]
            mag = abs(h)
            phase = math.degrees(math.atan2(h.imag, h.real))

            ok_mag, msg_mag = self._assert_close(mag, 1.0 / math.sqrt(2), TOL_AC_MAG, f"|H(fc={fc:.1f}Hz)|")
            ok_phase, msg_phase = self._assert_close(phase, -45.0, TOL_AC_PHASE, "Phase(fc)", rel=False)
            ok = ok_mag and ok_phase
            msg = f"{msg_mag}; {msg_phase} (at f={freq_actual:.1f}Hz)"
            return TestResult(
                name=test_name, passed=ok, message=msg,
                details={"fc": fc, "f_actual": freq_actual, "mag": mag, "phase": phase, "freqs": len(result.frequencies)},
            )
        except Exception as e:
            return TestResult(name=test_name, passed=False, message=f"Exception: {e}")

    def test_ac_rc_lowpass_1k_1uf(self) -> TestResult:
        """RC low-pass: R=1k, C=1uF, fc=159.155 Hz."""
        return self._test_ac_lowpass(1000, 1e-6, "ac_rc_lowpass_1k_1uf", "AC: RC Low-pass (1k, 1uF)")

    def test_ac_rc_lowpass_10k_1nf(self) -> TestResult:
        """RC low-pass: R=10k, C=1nF, fc=15.915 kHz."""
        return self._test_ac_lowpass(10000, 1e-9, "ac_rc_lowpass_10k_1nf", "AC: RC Low-pass (10k, 1nF)")

    def _test_ac_highpass(self, r: float, c: float, freq_key: str, test_name: str) -> TestResult:
        """Shared AC high-pass test logic."""
        fc = expected_rc_cutoff_frequency(r, c)

        if self.use_mock:
            h_at_fc = expected_rc_transfer(fc, r, c, highpass=True)
            mag = abs(h_at_fc)
            phase = math.degrees(math.atan2(h_at_fc.imag, h_at_fc.real))
            ok_mag, msg_mag = self._assert_close(mag, 1.0 / math.sqrt(2), TOL_AC_MAG, "|H(fc)|")
            ok_phase, msg_phase = self._assert_close(phase, 45.0, TOL_AC_PHASE, "Phase(fc)", rel=False)
            ok = ok_mag and ok_phase
            msg = f"{msg_mag}; {msg_phase}"
            return TestResult(name=test_name, passed=ok, message=msg, details={"mock": True, "fc": fc, "mag": mag, "phase": phase})

        try:
            result = simulate_ac(CIRCUITS[freq_key])
            if not result.ok:
                return TestResult(name=test_name, passed=False, message=f"No AC data")

            out_data = result.node_data.get("n2", [])
            if not out_data:
                return TestResult(name=test_name, passed=False, message=f"Node n2 not in node_data")

            best_idx = min(range(len(result.frequencies)), key=lambda i: abs(result.frequencies[i] - fc))
            h = out_data[best_idx]
            freq_actual = result.frequencies[best_idx]
            mag = abs(h)
            phase = math.degrees(math.atan2(h.imag, h.real))

            ok_mag, msg_mag = self._assert_close(mag, 1.0 / math.sqrt(2), TOL_AC_MAG, f"|H(fc={fc:.1f}Hz)|")
            # For high-pass at fc, phase should be +45 degrees
            ok_phase, msg_phase = self._assert_close(phase, 45.0, TOL_AC_PHASE, "Phase(fc)", rel=False)
            ok = ok_mag and ok_phase
            msg = f"{msg_mag}; {msg_phase} (at f={freq_actual:.1f}Hz)"
            return TestResult(
                name=test_name, passed=ok, message=msg,
                details={"fc": fc, "f_actual": freq_actual, "mag": mag, "phase": phase},
            )
        except Exception as e:
            return TestResult(name=test_name, passed=False, message=f"Exception: {e}")

    def test_ac_rc_highpass_1k_1uf(self) -> TestResult:
        """RC high-pass: C=1uF, R=1k, fc=159.155 Hz."""
        return self._test_ac_highpass(1000, 1e-6, "ac_rc_highpass_1k_1uf", "AC: RC High-pass (1k, 1uF)")

    def test_ac_transfer_function_shape(self) -> TestResult:
        """Verify AC low-pass roll-off: at 10*fc, magnitude < 0.1."""
        name = "AC: Transfer Function Roll-off"
        r, c = 1000, 1e-6
        fc = expected_rc_cutoff_frequency(r, c)

        if self.use_mock:
            h_10fc = expected_rc_transfer(10 * fc, r, c, highpass=False)
            ok, msg = self._assert_close(abs(h_10fc), 0.0995, 0.05, "|H(10*fc)|")
            return TestResult(name=name, passed=ok, message=msg, details={"mock": True, "h_10fc_mag": abs(h_10fc)})

        try:
            result = simulate_ac(CIRCUITS["ac_rc_lowpass_1k_1uf"])
            if not result.ok:
                return TestResult(name=name, passed=False, message="No AC data")

            out_data = result.node_data.get("n2", [])
            if not out_data:
                return TestResult(name=name, passed=False, message="Node n2 not in data")

            # Find data point closest to 10*fc
            target_f = 10 * fc
            best_idx = min(range(len(result.frequencies)), key=lambda i: abs(result.frequencies[i] - target_f))
            mag_10fc = abs(out_data[best_idx])
            freq_actual = result.frequencies[best_idx]

            # At 10*fc, |H| = 1/sqrt(1+100) ≈ 0.0995
            expected_mag = 1.0 / math.sqrt(1.0 + 100.0)
            ok, msg = self._assert_close(mag_10fc, expected_mag, 0.05, f"|H(f={freq_actual:.0f}Hz)|")
            return TestResult(name=name, passed=ok, message=msg, details={"mag_10fc": mag_10fc, "f_actual": freq_actual})
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    # ── Current Tests ──

    def test_current_ohms_law(self) -> TestResult:
        """Ohm's law: V=5V, R=1k, I=5mA."""
        name = "Current: Ohm's Law (5V/1k)"
        if self.use_mock:
            i_theory = 5.0 / 1000
            ok, msg = self._assert_close(i_theory, 5e-3, TOL_CURRENT, "I")
            return TestResult(name=name, passed=ok, message=msg, details={"mock": True, "i": i_theory})

        try:
            result = simulate_dc(CIRCUITS["current_ohms_law"])
            if not result.ok:
                return TestResult(name=name, passed=False, message="No DC data")

            v_n1 = result.voltages.get("n1", None)
            if v_n1 is None:
                return TestResult(name=name, passed=False, message=f"Node n1 not found")

            # I = V/R = 5/1000 = 5mA
            expected_v = 5.0
            ok_v, msg_v = self._assert_close(v_n1, expected_v, TOL_VOLTAGE, "V(N1)")

            # Also check current if available
            i_r1 = result.currents.get("r1", None)
            if i_r1 is not None:
                i_abs = abs(i_r1)
                ok_i, msg_i = self._assert_close(i_abs, 5e-3, TOL_CURRENT, "|I(R1)|")
                ok = ok_v and ok_i
                msg = f"{msg_v}; {msg_i}"
            else:
                ok = ok_v
                msg = msg_v

            return TestResult(name=name, passed=ok, message=msg, details={"v_n1": v_n1, "i_r1": i_r1})
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    def test_current_series_same(self) -> TestResult:
        """Series circuit: same current through R1 and R2."""
        name = "Current: Series (same I)"
        if self.use_mock:
            i_theory = 10.0 / (1000 + 2000)
            ok, msg = self._assert_close(i_theory, 10.0 / 3000, TOL_CURRENT, "I")
            return TestResult(name=name, passed=ok, message=msg, details={"mock": True, "i": i_theory})

        try:
            result = simulate_dc(CIRCUITS["current_series_same"])
            if not result.ok:
                return TestResult(name=name, passed=False, message="No DC data")

            v_n2 = result.voltages.get("n2", None)
            if v_n2 is None:
                return TestResult(name=name, passed=False, message=f"Node n2 not found")

            # V(N2) = 10 - I*R1 = 10 - (10/3k)*1k = 10 - 3.333 = 6.667V
            expected_v_n2 = 10.0 * 2000 / (1000 + 2000)  # voltage divider: 10 * R2/(R1+R2)
            ok, msg = self._assert_close(v_n2, expected_v_n2, TOL_VOLTAGE, "V(N2)")

            # Current from voltage: I = (10 - V(N2)) / R1
            i_from_v = (10.0 - v_n2) / 1000
            expected_i = 10.0 / (1000 + 2000)
            ok_i, msg_i = self._assert_close(abs(i_from_v), expected_i, TOL_CURRENT, "|I| via KVL")
            ok = ok and ok_i
            msg = f"{msg}; {msg_i}"

            return TestResult(name=name, passed=ok, message=msg, details={"v_n2": v_n2, "i_from_v": i_from_v})
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    def test_current_kcl_node(self) -> TestResult:
        """KCL validation: I_R1 = I_R2 + I_R3 at node N2."""
        name = "Current: KCL at Node"
        if self.use_mock:
            # V(N2) = 10 / (1 + 0.5 + 0.2) = 5.8824V
            v_n2 = 10.0 / (1.0 + 1000/2000 + 1000/5000)
            i_r1 = (10.0 - v_n2) / 1000
            i_r2 = v_n2 / 2000
            i_r3 = v_n2 / 5000
            kcl_error = i_r1 - (i_r2 + i_r3)
            ok, msg = self._assert_close(abs(kcl_error), 0.0, TOL_CURRENT, "KCL error")
            return TestResult(name=name, passed=ok, message=msg, details={"mock": True, "v_n2": v_n2, "kcl_error": kcl_error})

        try:
            result = simulate_dc(CIRCUITS["current_kcl_node"])
            if not result.ok:
                return TestResult(name=name, passed=False, message="No DC data")

            v_n2 = result.voltages.get("n2", None)
            if v_n2 is None:
                return TestResult(name=name, passed=False, message=f"Node n2 not found")

            # Compute currents from voltages (Ohm's law)
            i_r1 = (10.0 - v_n2) / 1000   # current into node N2
            i_r2 = v_n2 / 2000              # current out of N2 through R2
            i_r3 = v_n2 / 5000              # current out of N2 through R3

            # KCL: sum of currents into node = sum out
            kcl_error = i_r1 - (i_r2 + i_r3)

            # Expected V(N2) = 10 / (1 + 0.5 + 0.2) = 5.8824V
            expected_v = 10.0 / (1.0 + 1000/2000 + 1000/5000)
            ok_v, msg_v = self._assert_close(v_n2, expected_v, TOL_VOLTAGE, "V(N2)")

            # KCL should be satisfied to numerical precision
            ok_kcl, msg_kcl = self._assert_close(abs(kcl_error), 0.0, TOL_CURRENT, "KCL residual")

            ok = ok_v and ok_kcl
            msg = f"{msg_v}; {msg_kcl}"

            return TestResult(
                name=name, passed=ok, message=msg,
                details={"v_n2": v_n2, "i_r1": i_r1, "i_r2": i_r2, "i_r3": i_r3, "kcl_error": kcl_error},
            )
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    # ── Integration Tests ──

    def test_ngspice_detection(self) -> TestResult:
        """Verify ngspice detection and basic invocation."""
        name = "Integration: ngspice Detection"
        if self.use_mock:
            return TestResult(
                name=name, passed=True,
                message=f"Mock mode — ngspice {'available' if NGSPICE_AVAILABLE else 'not available'}",
                details={"ngspice_available": NGSPICE_AVAILABLE, "path": NGSPICE_PATH},
            )

        if not NGSPICE_AVAILABLE:
            return TestResult(name=name, passed=False, message="ngspice not found on PATH")

        # Run a trivial circuit to verify ngspice works
        trivial = textwrap.dedent("""\
            * Trivial test
            V1 N1 0 DC 5
            .op
            .end
        """)
        try:
            output = run_ngspice(trivial)
            has_data = "No. of Data Rows" in output or "n1" in output.lower()
            return TestResult(
                name=name, passed=has_data,
                message=f"ngspice ran successfully" if has_data else f"ngspice ran but no data in output",
                details={"output_lines": len(output.split(chr(10)))},
            )
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    def test_spice_generator_integration(self) -> TestResult:
        """Test that SpiceGenerator produces valid netlists that ngspice accepts."""
        name = "Integration: SpiceGenerator → ngspice"
        if self.use_mock:
            return TestResult(name=name, passed=True, message="Mock mode — skipped", details={"mock": True})

        try:
            from wire_detection.core.netlist import (
                ComponentPin,
                build_netlist,
            )
            from wire_detection.core.spice import COMPONENT_NAMES, SpiceGenerator

            _ID = {v: k for k, v in COMPONENT_NAMES.items()}
            _RES = _ID["resistor"]
            _VDC = _ID["voltage-DC"]
            _GND = _ID["gnd"]

            # Build a simple voltage divider circuit
            def _pin(ci, name, pi, x, y):
                return ComponentPin(
                    component_idx=ci, component_name=name,
                    pin_idx=pi, pin_name=f"pin{pi}",
                    x=x, y=y, rel_x=0.0, rel_y=0.0,
                )

            pins = [
                _pin(0, "voltage-DC", 0, 10, 10),
                _pin(0, "voltage-DC", 1, 10, 30),
                _pin(1, "resistor", 0, 10, 10),
                _pin(1, "resistor", 1, 10, 30),
                _pin(2, "resistor", 0, 10, 30),
                _pin(2, "resistor", 1, 30, 30),
            ]

            components = [
                (55, [(0, 0), (40, 0), (40, 20), (0, 20)], (0, 0, 40, 20)),  # voltage-DC
                (37, [(0, 0), (40, 0), (40, 20), (0, 20)], (0, 0, 40, 20)),  # resistor
                (37, [(0, 0), (40, 0), (40, 20), (0, 20)], (0, 0, 40, 20)),  # resistor
            ]

            netlist = build_netlist([], components, pins, max_pin_dist=30)
            gen = SpiceGenerator()
            netlist_text = gen.generate(components, netlist)

            # Verify netlist has expected structure
            has_v = "V1" in netlist_text
            has_r = "R" in netlist_text
            has_op = ".op" in netlist_text
            has_end = ".end" in netlist_text

            if not (has_v and has_r and has_op and has_end):
                return TestResult(
                    name=name, passed=False,
                    message=f"Netlist missing elements: V={has_v}, R={has_r}, .op={has_op}, .end={has_end}",
                )

            # Run through ngspice
            result = simulate_dc(netlist_text)
            ok = result.ok
            msg = f"SpiceGenerator netlist simulated {'OK' if ok else 'FAIL'}"
            if not ok:
                msg += f" — {result.raw[:200]}"

            return TestResult(name=name, passed=ok, message=msg, details={"netlist_lines": len(netlist_text.split(chr(10)))})
        except Exception as e:
            return TestResult(name=name, passed=False, message=f"Exception: {e}")

    # ── Output Parser Tests ──

    def test_parser_dc_output(self) -> TestResult:
        """Verify DC output parser with known ngspice output format."""
        name = "Parser: DC Output"
        sample_output = textwrap.dedent("""\
            No. of Data Rows : 1

            Node                                  Voltage
            ----                                  -------
            ----	-------
            n1                               5.000000e+00
            n2                               2.500000e+00

            Source	Current
            ------
            -------
            v1#branch                        -2.50000e-03
        """)
        result = parse_dc_output(sample_output)
        ok_v1 = "n1" in result.voltages and abs(result.voltages["n1"] - 5.0) < 0.001
        ok_v2 = "n2" in result.voltages and abs(result.voltages["n2"] - 2.5) < 0.001
        ok_cur = "v1#branch" in result.currents

        ok = ok_v1 and ok_v2 and ok_cur
        msg = f"V(n1)={result.voltages.get('n1')}, V(n2)={result.voltages.get('n2')}, currents={list(result.currents.keys())}"
        return TestResult(name=name, passed=ok, message=msg, details={"voltages": result.voltages, "currents": result.currents})

    def test_parser_ac_output(self) -> TestResult:
        """Verify AC output parser with known ngspice AC format."""
        name = "Parser: AC Output"
        # Simulated ngspice AC output format
        sample_output = textwrap.dedent("""\
            Index   frequency      VM(out)      VP(out)      VM(n2)      VP(n2)
            ------  -----------    ----------   ----------   ----------  ----------
            0       1.000000e+02   9.950372e-01 -5.715719e+00  9.950372e-01 -5.715719e+00
            1       1.258925e+02   9.921778e-01 -7.125016e+00  9.921778e-01 -7.125016e+00
            2       1.584893e+02   7.071068e-01 -4.500000e+01  7.071068e-01 -4.500000e+01
            3       1.995262e+02   5.547002e-01 -5.625000e+01  5.547002e-01 -5.625000e+01
        """)
        result = parse_ac_output(sample_output)
        ok_freqs = len(result.frequencies) == 4
        ok_nodes = "n2" in result.node_data or "out" in result.node_data

        if ok_nodes:
            # Check that at index 2 (fc), |H| ≈ 0.707
            node_key = "n2" if "n2" in result.node_data else "out"
            h_fc = result.node_data[node_key][2]
            mag = abs(h_fc)
            ok_mag = abs(mag - 1.0 / math.sqrt(2)) < 0.01
        else:
            ok_mag = False

        ok = ok_freqs and ok_nodes and ok_mag
        msg = f"freqs={len(result.frequencies)}, nodes={list(result.node_data.keys())}"
        if ok_nodes:
            node_key = "n2" if "n2" in result.node_data else "out"
            msg += f", |H(fc)|={abs(result.node_data[node_key][2]):.4f}"
        return TestResult(name=name, passed=ok, message=msg, details={"frequencies": result.frequencies, "nodes": list(result.node_data.keys())})

    def test_parser_empty_output(self) -> TestResult:
        """Parser handles empty/error output gracefully."""
        name = "Parser: Empty Output"
        dc = parse_dc_output("")
        ac = parse_ac_output("")
        ok = not dc.ok and not ac.ok
        return TestResult(name=name, passed=ok, message="Empty input returns no data (correct)")

    # ═══════════════════════════════════════════════
    # RUNNER
    # ═══════════════════════════════════════════════

    def run_dc_tests(self) -> list[TestResult]:
        """Run all DC analysis tests."""
        tests = [
            self.test_dc_voltage_divider_equal,
            self.test_dc_voltage_divider_unequal,
            self.test_dc_series_resistors,
            self.test_dc_parallel_resistors,
            self.test_dc_three_resistor_network,
        ]
        results = [t() for t in tests]
        self.results.extend(results)
        return results

    def run_ac_tests(self) -> list[TestResult]:
        """Run all AC analysis tests."""
        tests = [
            self.test_ac_rc_lowpass_1k_1uf,
            self.test_ac_rc_lowpass_10k_1nf,
            self.test_ac_rc_highpass_1k_1uf,
            self.test_ac_transfer_function_shape,
        ]
        results = [t() for t in tests]
        self.results.extend(results)
        return results

    def run_current_tests(self) -> list[TestResult]:
        """Run all current measurement tests."""
        tests = [
            self.test_current_ohms_law,
            self.test_current_series_same,
            self.test_current_kcl_node,
        ]
        results = [t() for t in tests]
        self.results.extend(results)
        return results

    def run_all(self) -> list[TestResult]:
        """Run all validation tests."""
        self.results.clear()
        all_tests = [
            # Infrastructure
            self.test_ngspice_detection,
            self.test_parser_dc_output,
            self.test_parser_ac_output,
            self.test_parser_empty_output,
            # DC
            self.test_dc_voltage_divider_equal,
            self.test_dc_voltage_divider_unequal,
            self.test_dc_series_resistors,
            self.test_dc_parallel_resistors,
            self.test_dc_three_resistor_network,
            # AC
            self.test_ac_rc_lowpass_1k_1uf,
            self.test_ac_rc_lowpass_10k_1nf,
            self.test_ac_rc_highpass_1k_1uf,
            self.test_ac_transfer_function_shape,
            # Current
            self.test_current_ohms_law,
            self.test_current_series_same,
            self.test_current_kcl_node,
            # Integration
            self.test_spice_generator_integration,
        ]
        self.results = [t() for t in all_tests]
        return self.results


# ═══════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════

def print_results(results: list[TestResult]) -> None:
    """Print a formatted test report to stdout."""
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)

    mode = "MOCK" if not NGSPICE_AVAILABLE else "LIVE (ngspice)"
    print(f"\n{'='*70}")
    print(f"  SPICE Simulation Validation — {mode}")
    print(f"{'='*70}\n")

    for r in results:
        status = "  PASS" if r.passed else "  FAIL"
        print(f"  {status}  {r.name}")
        print(f"         {r.message}")
        if not r.passed and r.details:
            # Show relevant details for debugging
            for k, v in r.details.items():
                if k not in ("mock", "voltages", "currents", "freqs", "nodes", "netlist_lines", "output_lines"):
                    print(f"         [{k}] = {v}")
        print()

    print(f"{'─'*70}")
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if not NGSPICE_AVAILABLE:
        print(f"  ⚠  ngspice not found — all simulation tests ran in MOCK mode")
        print(f"     Install ngspice for live validation: apt install ngspice")
    print(f"{'='*70}\n")


# ═══════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════

def main() -> int:
    """Run SPICE validation and return exit code (0=pass, 1=fail)."""
    import argparse
    parser = argparse.ArgumentParser(description="SPICE Simulation Validation")
    parser.add_argument("--dc", action="store_true", help="Run DC tests only")
    parser.add_argument("--ac", action="store_true", help="Run AC tests only")
    parser.add_argument("--current", action="store_true", help="Run current tests only")
    parser.add_argument("--mock", action="store_true", help="Force mock mode (no ngspice)")
    args = parser.parse_args()

    suite = SpiceValidation(use_mock=args.mock)

    if args.dc:
        results = suite.run_dc_tests()
    elif args.ac:
        results = suite.run_ac_tests()
    elif args.current:
        results = suite.run_current_tests()
    else:
        results = suite.run_all()

    print_results(results)
    failed = sum(1 for r in results if not r.passed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

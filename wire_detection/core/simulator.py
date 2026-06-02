"""SPICE circuit simulator wrapper using ngspice."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def _resolve_ngspice() -> str | None:
    """Locate an ngspice batch binary.

    Order: NGSPICE_PATH env var (full path to the .exe) > `ngspice_con` on PATH
    > `ngspice` on PATH. On Windows the **console** build (`ngspice_con.exe`) is
    required for `-b` batch mode — the GUI `ngspice.exe` does not emit results to
    stdout, so prefer it.
    """
    env = os.environ.get("NGSPICE_PATH")
    if env and Path(env).exists():
        return env
    for name in ("ngspice_con", "ngspice"):
        found = shutil.which(name)
        if found:
            return found
    return None


class SpiceSimulator:
    def __init__(self, ngspice_path: str | None = None):
        self._ngspice_path = ngspice_path or _resolve_ngspice() or "ngspice"

    @staticmethod
    def is_available() -> bool:
        return _resolve_ngspice() is not None

    def run_dc_analysis(self, spice_text: str) -> dict:
        if not self.is_available():
            return {"error": "ngspice not found"}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".cir", delete=False
        ) as f:
            f.write(spice_text)
            cir_path = f.name

        try:
            result = subprocess.run(
                [self._ngspice_path, "-b", cir_path],
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout + "\n" + result.stderr

            if result.returncode != 0 and "error" in output.lower():
                return {"error": output.strip()}

            return self.parse_dc_output(output)

        except subprocess.TimeoutExpired:
            return {"error": "ngspice timed out"}
        except FileNotFoundError:
            return {"error": "ngspice not found"}
        finally:
            Path(cir_path).unlink(missing_ok=True)

    @staticmethod
    def parse_dc_output(output: str) -> dict:
        voltages: dict[str, float] = {}
        currents: dict[str, float] = {}

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
                    node = m.group(1).lower()
                    try:
                        voltages[node] = float(m.group(2))
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
                        currents[m.group(1)] = float(m.group(2))
                    except ValueError:
                        pass

        result: dict = {}
        if voltages:
            result["voltages"] = voltages
        if currents:
            result["currents"] = currents
        if not voltages and not currents:
            result["error"] = "no operating point data found"

        return result

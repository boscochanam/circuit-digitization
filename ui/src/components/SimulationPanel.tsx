"use client";

import { useState } from "react";

interface NodeVoltage {
  node: string;
  voltage: number;
}

interface BranchCurrent {
  source: string;
  current: number;
}

interface SimResult {
  success: boolean;
  node_voltages: NodeVoltage[];
  branch_currents: BranchCurrent[];
  error?: string;
}

export default function SimulationPanel({
  onRunSimulation,
}: {
  onRunSimulation: () => Promise<SimResult>;
}) {
  const [voltages, setVoltages] = useState<NodeVoltage[] | null>(null);
  const [currents, setCurrents] = useState<BranchCurrent[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSimulate = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await onRunSimulation();
      if (result.success === false) {
        throw new Error(result.error || "Simulation returned no result");
      }
      setVoltages(result.node_voltages ?? []);
      setCurrents(result.branch_currents ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
      setVoltages(null);
      setCurrents(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel-content">
      <div className="panel-content-inner">
        {/* Run button */}
        <div className="netlist-section">
          <button
            className="simulate-btn"
            onClick={handleSimulate}
            disabled={loading}
          >
            {loading ? (
              <span className="simulate-btn-content">
                <span className="loading-spinner" />
                Running…
              </span>
            ) : (
              "Run DC Simulation"
            )}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="netlist-section">
            <div className="netlist-section-title">Error</div>
            <div className="netlist-warning">{error}</div>
          </div>
        )}

        {/* Node Voltages */}
        {voltages && voltages.length > 0 && (
          <div className="netlist-section">
            <div className="netlist-section-title">DC Operating Point — Node Voltages</div>
            <table className="netlist-table">
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Voltage (V)</th>
                </tr>
              </thead>
              <tbody>
                {voltages.map((v, i) => (
                  <tr key={i}>
                    <td className="netlist-cell-mono">{v.node}</td>
                    <td className="netlist-cell-mono">{v.voltage.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Branch Currents */}
        {currents && currents.length > 0 && (
          <div className="netlist-section">
            <div className="netlist-section-title">Branch Currents</div>
            <table className="netlist-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Current (A)</th>
                </tr>
              </thead>
              <tbody>
                {currents.map((c, i) => (
                  <tr key={i}>
                    <td className="netlist-cell-mono">{c.source}</td>
                    <td className="netlist-cell-mono">{c.current.toFixed(6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* No results yet */}
        {!loading && !error && voltages === null && (
          <div className="netlist-section">
            <span className="viewport-empty">
              Click "Run DC Simulation" to analyze the circuit
            </span>
          </div>
        )}

        {/* Empty results */}
        {!loading && voltages !== null && voltages.length === 0 && (
          <div className="netlist-section">
            <span className="viewport-empty">No simulation results</span>
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchSimOverlayAction, fetchJoinStrategiesAction } from "@/app/actions";
import type { SimOverlayResult, JoinStrategy } from "@/lib/types";

/**
 * Voltage Map — visualizes the SPICE nodal-analysis result ON the schematic.
 * Each electrical net is coloured by its computed DC node voltage (blue=low,
 * red=high) with the value labelled. Turns the simulation table into a picture.
 */
export default function VoltageMapPanel({
  imageIdx,
  dataset,
  preset,
  params = {},
}: {
  imageIdx: number;
  dataset: string;
  preset: string;
  params?: Record<string, string | number>;
}) {
  const [data, setData] = useState<SimOverlayResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [strategies, setStrategies] = useState<JoinStrategy[]>([]);
  const [strategy, setStrategy] = useState<string>("nearest2_30");

  useEffect(() => {
    fetchJoinStrategiesAction()
      .then((r) => setStrategies(r.strategies))
      .catch(() => {});
  }, []);

  const doFetch = useCallback(async (strat: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchSimOverlayAction(imageIdx, dataset, preset, params, strat);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load voltage map");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [imageIdx, dataset, preset]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    doFetch(strategy);
  }, [imageIdx, dataset, preset, strategy]); // eslint-disable-line react-hooks/exhaustive-deps

  const cur = strategies.find((s) => s.name === strategy);

  return (
    <div className="panel-content">
      <div className="panel-content-inner" style={{ padding: 0, position: "relative" }}>
        {/* Strategy bar */}
        <div style={{
          display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
          padding: "6px 12px", borderBottom: "1px solid #27272a", fontSize: 11, color: "#a1a1aa",
        }}>
          <span style={{ color: "#71717a" }}>Join strategy:</span>
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            style={{
              background: "#0f1115", color: "#e6e6e6", border: "1px solid #2a2f3a",
              borderRadius: 4, padding: "3px 6px", fontSize: 11, minWidth: 220,
            }}
          >
            {strategies.map((s) => (
              <option key={s.name} value={s.name}>{s.label}</option>
            ))}
          </select>
          {data?.available && (
            <span style={{ marginLeft: "auto", color: "#a1a1aa" }}>
              {data.n_solved} nodes solved &middot; {data.vmin}V … {data.vmax}V
            </span>
          )}
        </div>

        {/* Caveat */}
        <div style={{
          padding: "4px 12px", fontSize: 10, color: "#71717a",
          borderBottom: "1px solid #27272a",
        }}>
          DC operating point on the extracted topology. Values use default component
          values (R=1k, V=5V…), so they're illustrative, not the real circuit's numbers —
          and only as correct as the join.
        </div>

        {/* Image */}
        <div style={{
          position: "relative", minHeight: 320, background: "#09090b",
          display: "flex", alignItems: "center", justifyContent: "center", padding: 8,
        }}>
          {loading && <div className="loading-overlay"><div className="loading-spinner" /></div>}
          {error && <div className="netlist-warning">{error}</div>}
          {!error && data?.overlay && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`data:image/png;base64,${data.overlay}`}
              alt="voltage map"
              style={{ maxWidth: "100%", maxHeight: "62vh", display: "block", borderRadius: 4 }}
            />
          )}
        </div>

        {data && !data.available && data.warnings.length > 0 && (
          <div style={{ padding: "6px 12px", fontSize: 11, color: "#fb923c" }}>
            {data.warnings.join("  ·  ")}
          </div>
        )}

        {/* Node voltage table */}
        {data?.available && data.node_voltages.length > 0 && (
          <div className="netlist-section" style={{ padding: "8px 12px" }}>
            <div className="netlist-section-title">Node voltages ({data.node_voltages.length})</div>
            <table className="netlist-table">
              <thead><tr><th>Node</th><th>Voltage (V)</th></tr></thead>
              <tbody>
                {data.node_voltages.map((v, i) => (
                  <tr key={i}>
                    <td className="netlist-cell-mono">{v.node}</td>
                    <td className="netlist-cell-mono">{v.voltage.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {cur && <div style={{ padding: "0 12px 10px", fontSize: 10, color: "#52525b" }}>{cur.desc}</div>}
      </div>
    </div>
  );
}

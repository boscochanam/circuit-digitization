"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchSimOverlayAction, fetchJoinStrategiesAction } from "@/app/actions";
import type { SimOverlayResult, JoinStrategy } from "@/lib/types";

/**
 * Voltage Map — visualizes the SPICE nodal-analysis result ON the schematic.
 * Each electrical net is coloured by its computed DC node voltage (blue=low,
 * red=high) with the value labelled. Turns the simulation table into a picture.
 *
 * Styled with the app's brutalist black-on-white tokens + netlist-* classes
 * (issue #11 #4/#7); params is in the deps so detection-slider changes re-run it.
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
  const [strategy, setStrategy] = useState<string>("graph_rescue");

  useEffect(() => {
    fetchJoinStrategiesAction()
      .then((r) => setStrategies(r.strategies))
      .catch(() => {});
  }, []);

  // params IS in the deps so changing detection sliders re-runs the map (issue #11 bug).
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
  }, [imageIdx, dataset, preset, params]);

  useEffect(() => {
    doFetch(strategy);
  }, [imageIdx, dataset, preset, strategy, params, doFetch]);

  const cur = strategies.find((s) => s.name === strategy);

  return (
    <div className="panel-content">
      <div className="panel-content-inner" style={{ padding: 0 }}>
        {/* Strategy bar */}
        <div style={BAR}>
          <span style={LABEL}>JOIN STRATEGY</span>
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)} style={SELECT}>
            {strategies.map((s) => (
              <option key={s.name} value={s.name}>{s.label}</option>
            ))}
          </select>
          {data?.available && (
            <span style={{ marginLeft: "auto", color: "var(--grey-dark)" }}>
              {data.n_solved} nodes solved &middot; {data.vmin}V … {data.vmax}V
            </span>
          )}
        </div>

        {/* Caveat */}
        <div style={CAVEAT}>
          DC operating point on the extracted topology. Default component values
          (R=1k, V=5V…); each disconnected sub-circuit is driven by a 5V test source +
          ground return so it isn&apos;t left at 0V. Illustrative — not the real
          circuit&apos;s numbers, and only as correct (and connected) as the join.
        </div>

        {/* Image */}
        <div style={STAGE}>
          {loading && <div className="loading-overlay"><div className="loading-spinner" /></div>}
          {error && <div className="netlist-warning">{error}</div>}
          {!error && data?.overlay && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`data:image/png;base64,${data.overlay}`}
              alt="voltage map"
              style={{ maxWidth: "100%", maxHeight: "62vh", display: "block" }}
            />
          )}
        </div>

        {data && !data.available && data.warnings.length > 0 && (
          <div className="netlist-warning" style={{ margin: "8px 12px" }}>{data.warnings.join("  ·  ")}</div>
        )}

        {data?.available && data.node_voltages.length > 0 && (
          <div className="netlist-section" style={{ margin: "10px 12px" }}>
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
        {cur && <div style={{ padding: "0 12px 12px", fontSize: 10, color: "var(--grey-dark)" }}>{cur.desc}</div>}
      </div>
    </div>
  );
}

// brutalist black-on-white styles (design tokens)
const BAR: React.CSSProperties = {
  display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
  padding: "8px 12px", borderBottom: "2px solid var(--black)", fontSize: 11,
  color: "var(--grey-dark)", background: "var(--white)",
};
const LABEL: React.CSSProperties = {
  fontSize: 9, letterSpacing: 2, textTransform: "uppercase", color: "var(--grey-dark)",
};
const SELECT: React.CSSProperties = {
  background: "var(--white)", color: "var(--black)", border: "1px solid var(--black)",
  borderRadius: 0, padding: "3px 6px", fontSize: 11, minWidth: 220,
};
const CAVEAT: React.CSSProperties = {
  padding: "6px 12px", fontSize: 10, color: "var(--grey-dark)",
  borderBottom: "1px solid var(--grey-mid)", background: "var(--grey-light)",
};
const STAGE: React.CSSProperties = {
  position: "relative", minHeight: 320, background: "var(--grey-light)",
  display: "flex", alignItems: "center", justifyContent: "center", padding: 10,
};

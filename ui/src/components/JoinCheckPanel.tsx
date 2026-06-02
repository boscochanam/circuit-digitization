"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchJoinOverlayAction, fetchJoinStrategiesAction } from "@/app/actions";
import type { JoinOverlayResult, JoinStrategy } from "@/lib/types";

/**
 * Image-grounded join verification. Renders the join overlay (server-rendered
 * on the schematic image): cyan = wire, green = nearest-pin join, orange =
 * extra over-joins. Lets you switch between "All nets" and one isolated net to
 * verify each join against real copper.
 */
export default function JoinCheckPanel({
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
  const [data, setData] = useState<JoinOverlayResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // null = all nets; otherwise a net_id
  const [selectedNet, setSelectedNet] = useState<number | null>(null);
  const [strategies, setStrategies] = useState<JoinStrategy[]>([]);
  const [strategy, setStrategy] = useState<string>("production");

  // Load the strategy registry once.
  useEffect(() => {
    fetchJoinStrategiesAction()
      .then((r) => { setStrategies(r.strategies); setStrategy(r.default); })
      .catch(() => {});
  }, []);

  const doFetch = useCallback(async (net: number | null, strat: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchJoinOverlayAction(imageIdx, dataset, preset, params, net, strat);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load join overlay");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [imageIdx, dataset, preset]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset to all-nets whenever the image or strategy changes, and fetch.
  useEffect(() => {
    setSelectedNet(null);
    doFetch(null, strategy);
  }, [imageIdx, dataset, preset, strategy]); // eslint-disable-line react-hooks/exhaustive-deps

  const currentStrategy = strategies.find((s) => s.name === strategy);

  const nets = data?.nets ?? [];
  // nets come back worst-over-merge first
  const selectNet = (net: number | null) => {
    setSelectedNet(net);
    doFetch(net, strategy);
  };
  const stepNet = (dir: number) => {
    if (nets.length === 0) return;
    const ids = nets.map((n) => n.net_id);
    if (selectedNet === null) {
      selectNet(ids[0]);
      return;
    }
    const idx = ids.indexOf(selectedNet);
    const next = (idx + dir + ids.length) % ids.length;
    selectNet(ids[next]);
  };

  const current = selectedNet !== null ? nets.find((n) => n.net_id === selectedNet) : null;

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
          {currentStrategy && (
            <span style={{ color: "#71717a", fontSize: 10, flex: "1 1 240px" }}>{currentStrategy.desc}</span>
          )}
        </div>

        {/* Metrics — grouped so the over-merge vs under-connect trade-off is readable */}
        {data?.metrics && (() => {
          const m = data.metrics;
          // verdict: a strategy can score a low over-merge composite by NOT connecting
          const overMerged = m.giant_nets >= 3 || m.self_loop_components >= 8;
          const underConnected = m.pct_wires_used < 60;
          const verdict = overMerged && !underConnected ? { t: "OVER-MERGED", c: "#fb923c" }
            : underConnected && !overMerged ? { t: "UNDER-CONNECTED", c: "#fbbf24" }
            : overMerged && underConnected ? { t: "BOTH WRONG", c: "#f87171" }
            : { t: "BALANCED", c: "#4ade80" };
          return (
            <div style={{
              display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap",
              padding: "8px 12px", borderBottom: "1px solid #27272a", fontSize: 11,
              fontVariantNumeric: "tabular-nums",
            }}>
              <Group title="over-merge">
                <Metric label="self-loops" value={m.self_loop_components} bad={m.self_loop_components >= 8} />
                <Metric label="giant nets" value={m.giant_nets} bad={m.giant_nets >= 3} />
              </Group>
              <Group title="under-connect">
                <Metric label="floating" value={m.floating_components} bad={m.floating_components > 5} />
                <Metric label="wires used" value={`${m.pct_wires_used}%`} bad={m.pct_wires_used < 60}
                  good={m.pct_wires_used >= 80} />
              </Group>
              <Group title="size">
                <Metric label="nets" value={m.n_nets} />
                <Metric label="/comp" value={m.nets_per_component} />
              </Group>
              <div style={{ marginLeft: "auto", display: "flex", gap: 12, alignItems: "center" }}>
                <span style={{ color: "#71717a" }}>
                  composite <strong style={{ color: "#a1a1aa" }}>{m.composite.toFixed(3)}</strong>
                </span>
                <span title="composite + under-connection penalty — matches what you see">
                  balanced <strong style={{ color: m.balanced < 0.18 ? "#4ade80" : m.balanced < 0.26 ? "#fbbf24" : "#fb923c", fontSize: 13 }}>
                    {m.balanced.toFixed(3)}
                  </strong>
                </span>
                <span style={{
                  padding: "2px 8px", borderRadius: 4, fontWeight: 700, fontSize: 10,
                  color: "#0b0b0b", background: verdict.c,
                }}>{verdict.t}</span>
              </div>
            </div>
          );
        })()}

        {/* Toolbar */}
        <div style={{
          display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
          padding: "6px 12px", borderBottom: "1px solid #27272a", fontSize: 11, color: "#a1a1aa",
        }}>
          <span style={{ color: "#71717a" }}>View:</span>
          <button
            onClick={() => selectNet(null)}
            style={tabStyle(selectedNet === null)}
          >All nets</button>
          <button onClick={() => stepNet(-1)} style={btnStyle} disabled={nets.length === 0}>‹ prev net</button>
          <button onClick={() => stepNet(1)} style={btnStyle} disabled={nets.length === 0}>next net ›</button>
          <select
            value={selectedNet === null ? "" : String(selectedNet)}
            onChange={(e) => selectNet(e.target.value === "" ? null : parseInt(e.target.value, 10))}
            style={{
              background: "#0f1115", color: "#e6e6e6", border: "1px solid #2a2f3a",
              borderRadius: 4, padding: "3px 6px", fontSize: 11,
            }}
          >
            <option value="">All nets ({nets.length})</option>
            {nets.map((n) => (
              <option key={n.net_id} value={n.net_id}>
                N{n.net_id} — {n.components} comps, {n.pins} pins{n.components > 3 ? "  ⚠ over-merge?" : ""}
              </option>
            ))}
          </select>
          {current && (
            <span style={{ marginLeft: "auto", color: current.components > 3 ? "#fb923c" : "#a1a1aa" }}>
              N{current.net_id}: {current.pins} pins on {current.components} components · {current.wires} wires
            </span>
          )}
        </div>

        {/* Legend */}
        <div style={{
          padding: "4px 12px", fontSize: 10, color: "#71717a",
          borderBottom: "1px solid #27272a", display: "flex", gap: 14, flexWrap: "wrap",
        }}>
          <Legend color="#28b4ff" label="detected wire" />
          <Legend color="#78ff5a" label="nearest-pin join (intended)" />
          <Legend color="#ff9628" label="extra over-join" />
          <span>— verify the green/orange links land on terminals a real wire reaches.</span>
        </div>

        {/* Image */}
        <div style={{ position: "relative", minHeight: 320, background: "#09090b",
          display: "flex", alignItems: "center", justifyContent: "center", padding: 8 }}>
          {loading && (
            <div className="loading-overlay"><div className="loading-spinner" /></div>
          )}
          {error && <div className="netlist-warning">{error}</div>}
          {!error && data?.overlay && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`data:image/png;base64,${data.overlay}`}
              alt="join overlay"
              style={{ maxWidth: "100%", maxHeight: "70vh", display: "block", borderRadius: 4 }}
            />
          )}
          {!error && !loading && !data?.overlay && (
            <span className="viewport-empty">No overlay</span>
          )}
        </div>

        {data?.warnings && data.warnings.length > 0 && (
          <div style={{ padding: "6px 12px", fontSize: 11, color: "#fb923c" }}>
            {data.warnings.join("  ·  ")}
          </div>
        )}
      </div>
    </div>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <span style={{ display: "inline-flex", gap: 10, alignItems: "center" }}>
      <span style={{ color: "#52525b", fontSize: 9, textTransform: "uppercase", letterSpacing: ".04em" }}>{title}</span>
      {children}
    </span>
  );
}

function Metric({ label, value, good, bad }: { label: string; value: number | string; good?: boolean; bad?: boolean }) {
  const color = bad ? "#fb923c" : good ? "#4ade80" : "#a1a1aa";
  return (
    <span style={{ color: "#71717a" }}>
      {label} <strong style={{ color }}>{value}</strong>
    </span>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <span style={{ width: 14, height: 3, background: color, display: "inline-block", borderRadius: 2 }} />
      {label}
    </span>
  );
}

const btnStyle: React.CSSProperties = {
  background: "#0f1115", color: "#e6e6e6", border: "1px solid #2a2f3a",
  borderRadius: 4, padding: "3px 8px", fontSize: 11, cursor: "pointer",
};
function tabStyle(active: boolean): React.CSSProperties {
  return {
    ...btnStyle,
    background: active ? "#1a2237" : "#0f1115",
    borderColor: active ? "#7aa2ff" : "#2a2f3a",
    color: active ? "#b3c7ff" : "#e6e6e6",
  };
}

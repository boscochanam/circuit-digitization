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
  }, [imageIdx, dataset, preset, params]); // params included so detection-slider changes re-run the overlay (issue #11)

  // Reset to all-nets whenever the image, strategy, or detection params change, and fetch.
  useEffect(() => {
    setSelectedNet(null);
    doFetch(null, strategy);
  }, [imageIdx, dataset, preset, strategy, params, doFetch]);

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
          padding: "6px 12px", borderBottom: "1px solid var(--grey-mid)", fontSize: 11, color: "var(--grey-dark)",
        }}>
          <span style={{ color: "var(--grey-dark)" }}>Join strategy:</span>
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            style={{
              background: "var(--white)", color: "var(--black)", border: "1px solid var(--black)",
              borderRadius: 0, padding: "3px 6px", fontSize: 11, minWidth: 220,
            }}
          >
            {strategies.map((s) => (
              <option key={s.name} value={s.name}>{s.label}</option>
            ))}
          </select>
          {currentStrategy && (
            <span style={{ color: "var(--grey-dark)", fontSize: 10, flex: "1 1 240px" }}>{currentStrategy.desc}</span>
          )}
        </div>

        {/* Metrics — grouped so the over-merge vs under-connect trade-off is readable.
            join_quality is the ROBUST headline (conn% + over-merge, not gameable by
            wire-to-wire chaining like `balanced` is). */}
        {data?.metrics && (() => {
          const m = data.metrics;
          const overMerged = m.giant_nets >= 3 || m.self_loop_components >= 8;
          const underConnected = m.pct_connected < 55;
          const verdict = overMerged && !underConnected ? { t: "OVER-MERGED", c: "var(--warning)" }
            : underConnected && !overMerged ? { t: "UNDER-CONNECTED", c: "var(--warning)" }
            : overMerged && underConnected ? { t: "BOTH WRONG", c: "var(--error)" }
            : { t: "BALANCED", c: "var(--success)" };
          const jq = m.join_quality ?? m.balanced;
          return (
            <div style={{
              display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap",
              padding: "8px 12px", borderBottom: "1px solid var(--grey-mid)", fontSize: 11,
              fontVariantNumeric: "tabular-nums",
            }}>
              <Group title="over-merge">
                <Metric label="self-loops" value={m.self_loop_components} bad={m.self_loop_components >= 8} />
                <Metric label="giant nets" value={m.giant_nets} bad={m.giant_nets >= 3} />
              </Group>
              <Group title="connectivity">
                <Metric label="comp conn" value={`${m.pct_connected}%`} bad={m.pct_connected < 55} good={m.pct_connected >= 75} />
                <Metric label="eff wires" value={`${m.pct_effective_wires ?? m.pct_wires_used}%`} good={(m.pct_effective_wires ?? 0) >= 85} />
                <Metric label="floating" value={m.floating_components} bad={m.floating_components > 5} />
              </Group>
              <Group title="size">
                <Metric label="nets" value={m.n_nets} />
              </Group>
              <div style={{ marginLeft: "auto", display: "flex", gap: 12, alignItems: "center" }}>
                <span title="composite over-merge + under-connection (by EFFECTIVE wires). Lower = better. Robust." style={{ color: "var(--grey-dark)" }}>
                  join_q <strong style={{ color: jq < 0.16 ? "var(--success)" : jq < 0.24 ? "var(--warning)" : "var(--error)", fontSize: 13 }}>
                    {jq.toFixed(3)}
                  </strong>
                </span>
                <span style={{
                  padding: "2px 8px", borderRadius: 0, fontWeight: 700, fontSize: 10,
                  color: "var(--black)", background: verdict.c,
                }}>{verdict.t}</span>
              </div>
            </div>
          );
        })()}

        {/* Toolbar */}
        <div style={{
          display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
          padding: "6px 12px", borderBottom: "1px solid var(--grey-mid)", fontSize: 11, color: "var(--grey-dark)",
        }}>
          <span style={{ color: "var(--grey-dark)" }}>View:</span>
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
              background: "var(--white)", color: "var(--black)", border: "1px solid var(--black)",
              borderRadius: 0, padding: "3px 6px", fontSize: 11,
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
            <span style={{ marginLeft: "auto", color: current.components > 3 ? "var(--warning)" : "var(--grey-dark)" }}>
              N{current.net_id}: {current.pins} pins on {current.components} components · {current.wires} wires
            </span>
          )}
        </div>

        {/* Legend */}
        <div style={{
          padding: "4px 12px", fontSize: 10, color: "var(--grey-dark)",
          borderBottom: "1px solid var(--grey-mid)", display: "flex", gap: 14, flexWrap: "wrap",
        }}>
          <Legend color="#28b4ff" label="detected wire" />
          <Legend color="#78ff5a" label="nearest-pin join (intended)" />
          <Legend color="#ff9628" label="extra over-join" />
          <span>— verify the green/orange links land on terminals a real wire reaches.</span>
        </div>

        {/* Image */}
        <div style={{ position: "relative", minHeight: 320, background: "var(--grey-light)",
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
              style={{ maxWidth: "100%", maxHeight: "70vh", display: "block", borderRadius: 0 }}
            />
          )}
          {!error && !loading && !data?.overlay && (
            <span className="viewport-empty">No overlay</span>
          )}
        </div>

        {data?.warnings && data.warnings.length > 0 && (
          <div style={{ padding: "6px 12px", fontSize: 11, color: "var(--warning)" }}>
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
      <span style={{ color: "var(--grey-dark)", fontSize: 9, textTransform: "uppercase", letterSpacing: ".04em" }}>{title}</span>
      {children}
    </span>
  );
}

function Metric({ label, value, good, bad }: { label: string; value: number | string; good?: boolean; bad?: boolean }) {
  const color = bad ? "var(--warning)" : good ? "var(--success)" : "var(--grey-dark)";
  return (
    <span style={{ color: "var(--grey-dark)" }}>
      {label} <strong style={{ color }}>{value}</strong>
    </span>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <span style={{ width: 14, height: 3, background: color, display: "inline-block", borderRadius: 0 }} />
      {label}
    </span>
  );
}

const btnStyle: React.CSSProperties = {
  background: "var(--white)", color: "var(--black)", border: "1px solid var(--black)",
  borderRadius: 0, padding: "3px 8px", fontSize: 11, cursor: "pointer",
};
function tabStyle(active: boolean): React.CSSProperties {
  return {
    ...btnStyle,
    background: active ? "var(--blue)" : "var(--white)",
    borderColor: active ? "var(--blue)" : "var(--black)",
    color: active ? "var(--white)" : "var(--black)",
  };
}

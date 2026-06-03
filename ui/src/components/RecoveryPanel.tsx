"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchRecoveryOverlayAction, fetchRecoveryIterationsAction } from "@/app/actions";
import type { RecoveryResult, RecoveryIteration } from "@/lib/types";

/**
 * Detection Recovery — step through cumulative fixes for "wires disappear on HDC"
 * (see docs/hdc-detection-failures.md) and SEE what each iteration changes:
 *   blue  = wire kept from the compare iteration
 *   green = wire ADDED by this iteration (recovered)
 *   red   = wire REMOVED by this iteration (cost)
 * The table shows every iteration's proxy metrics so you can choose one; the image
 * highlights the diff vs the previous iteration (or baseline).
 *
 * Brutalist black-on-white tokens + netlist-* classes; params in deps (issue #11).
 */
export default function RecoveryPanel({
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
  const [data, setData] = useState<RecoveryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [iterations, setIterations] = useState<RecoveryIteration[]>([]);
  const [iteration, setIteration] = useState<string>("anchor");
  const [compare, setCompare] = useState<"prev" | "baseline">("prev");

  useEffect(() => {
    fetchRecoveryIterationsAction()
      .then((r) => { setIterations(r.iterations); setIteration(r.default); })
      .catch(() => {});
  }, []);

  const doFetch = useCallback(async (iter: string, cmp: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchRecoveryOverlayAction(imageIdx, dataset, preset, params, iter, cmp);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recovery overlay");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [imageIdx, dataset, preset, params]);

  useEffect(() => {
    doFetch(iteration, compare);
  }, [imageIdx, dataset, preset, iteration, compare, params, doFetch]);

  const keys = iterations.map((i) => i.key);
  const stepIter = (dir: number) => {
    if (keys.length === 0) return;
    const idx = keys.indexOf(iteration);
    const next = (idx + dir + keys.length) % keys.length;
    setIteration(keys[next]);
  };
  const cur = iterations.find((i) => i.key === iteration);
  const rows = data?.iterations ?? [];

  return (
    <div className="panel-content">
      <div className="panel-content-inner" style={{ padding: 0 }}>
        {/* Iteration bar */}
        <div style={BAR}>
          <span style={LABEL}>ITERATION</span>
          <button onClick={() => stepIter(-1)} style={BTN} disabled={!keys.length}>‹</button>
          <select value={iteration} onChange={(e) => setIteration(e.target.value)} style={SELECT}>
            {iterations.map((i) => (<option key={i.key} value={i.key}>{i.label}</option>))}
          </select>
          <button onClick={() => stepIter(1)} style={BTN} disabled={!keys.length}>›</button>
          <span style={{ ...LABEL, marginLeft: 12 }}>HIGHLIGHT VS</span>
          <button onClick={() => setCompare("prev")} style={TAB(compare === "prev")}>previous</button>
          <button onClick={() => setCompare("baseline")} style={TAB(compare === "baseline")}>baseline</button>
          {data && (
            <span style={{ marginLeft: "auto", fontVariantNumeric: "tabular-nums" }}>
              <strong style={{ color: "var(--success)" }}>+{data.added}</strong> added&nbsp;&nbsp;
              <strong style={{ color: "var(--error)" }}>−{data.removed}</strong> removed&nbsp;&nbsp;
              <span style={{ color: "var(--grey-dark)" }}>{data.kept} kept</span>
            </span>
          )}
        </div>

        {/* Legend */}
        <div style={LEGEND}>
          <Sw color="#28b4ff" label="kept (carried from compare)" />
          <Sw color="#5aff78" label="added by this iteration" />
          <Sw color="#ff5a5a" label="removed by this iteration" />
          {cur && <span style={{ color: "var(--grey-dark)" }}>— {cur.desc}</span>}
        </div>

        {/* Image */}
        <div style={STAGE}>
          {loading && <div className="loading-overlay"><div className="loading-spinner" /></div>}
          {error && <div className="netlist-warning">{error}</div>}
          {!error && data?.overlay && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={`data:image/png;base64,${data.overlay}`} alt="recovery diff"
              style={{ maxWidth: "100%", maxHeight: "56vh", display: "block", border: "1px solid var(--black)" }} />
          )}
        </div>

        {data && data.warnings.length > 0 && (
          <div className="netlist-warning" style={{ margin: "6px 12px" }}>{data.warnings.join("  ·  ")}</div>
        )}

        {/* Metrics table — every iteration, click a row to view it */}
        {rows.length > 0 && (
          <div className="netlist-section" style={{ margin: "10px 12px" }}>
            <div className="netlist-section-title">
              Iterations — lines recovered &amp; the join trade-off (click a row to view)
            </div>
            <table className="netlist-table">
              <thead>
                <tr>
                  <th>Iteration</th><th title="detected wire lines">lines</th>
                  <th title="change vs baseline">Δ base</th>
                  <th title="foreground % after binarization (high = flooded/noisy)">ink%</th>
                  <th title="% of detected wires the join uses (production, 30px)">used%</th>
                  <th title="floating components (under-connected)">float</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const active = r.key === iteration;
                  return (
                    <tr key={r.key} onClick={() => setIteration(r.key)}
                      style={{ cursor: "pointer", background: active ? "var(--blue)" : undefined,
                               color: active ? "var(--white)" : undefined }}>
                      <td>{r.label}</td>
                      <td className="netlist-cell-mono">{r.lines}</td>
                      <td className="netlist-cell-mono" style={{ color: active ? "var(--white)" : r.delta_base > 0 ? "var(--success)" : r.delta_base < 0 ? "var(--error)" : undefined }}>
                        {r.delta_base > 0 ? "+" : ""}{r.delta_base}
                      </td>
                      <td className="netlist-cell-mono" style={{ color: active ? "var(--white)" : r.ink > 20 ? "var(--error)" : r.ink > 8 ? "var(--warning)" : undefined }}>{r.ink.toFixed(1)}</td>
                      <td className="netlist-cell-mono" style={{ color: active ? "var(--white)" : r.used >= 80 ? "var(--success)" : r.used < 60 ? "var(--warning)" : undefined }}>{r.used.toFixed(0)}</td>
                      <td className="netlist-cell-mono">{r.floating}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div style={{ fontSize: 10, color: "var(--grey-dark)", padding: "6px 2px 0" }}>
              Note: more recovered lines often <em>lowers</em> used% — detection recovery exposes the
              fixed-radius join (Mode C). High ink% (e.g. fusion) = flooded threshold, likely noise.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Sw({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <span style={{ width: 14, height: 4, background: color, display: "inline-block" }} />
      {label}
    </span>
  );
}

const BAR: React.CSSProperties = {
  display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap",
  padding: "8px 12px", borderBottom: "2px solid var(--black)", fontSize: 11,
  color: "var(--grey-dark)", background: "var(--white)",
};
const LABEL: React.CSSProperties = {
  fontSize: 9, letterSpacing: 2, textTransform: "uppercase", color: "var(--grey-dark)",
};
const SELECT: React.CSSProperties = {
  background: "var(--white)", color: "var(--black)", border: "1px solid var(--black)",
  borderRadius: 0, padding: "3px 6px", fontSize: 11, minWidth: 180,
};
const BTN: React.CSSProperties = {
  background: "var(--white)", color: "var(--black)", border: "1px solid var(--black)",
  borderRadius: 0, padding: "2px 8px", fontSize: 12, cursor: "pointer", lineHeight: 1,
};
function TAB(active: boolean): React.CSSProperties {
  return {
    background: active ? "var(--blue)" : "var(--white)", color: active ? "var(--white)" : "var(--black)",
    border: "1px solid var(--black)", borderColor: active ? "var(--blue)" : "var(--black)",
    borderRadius: 0, padding: "3px 8px", fontSize: 11, cursor: "pointer",
  };
}
const LEGEND: React.CSSProperties = {
  padding: "5px 12px", fontSize: 10, color: "var(--grey-dark)",
  borderBottom: "1px solid var(--grey-mid)", display: "flex", gap: 14, flexWrap: "wrap",
  background: "var(--grey-light)",
};
const STAGE: React.CSSProperties = {
  position: "relative", minHeight: 300, background: "var(--grey-light)",
  display: "flex", alignItems: "center", justifyContent: "center", padding: 10,
};

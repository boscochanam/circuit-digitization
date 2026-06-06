"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchNetlistAction } from "@/app/actions";
import type { NetlistResult } from "@/lib/types";

export default function NetlistPanel({
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
  const [data, setData] = useState<NetlistResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [netlistExpanded, setNetlistExpanded] = useState(true);

  const doFetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchNetlistAction(imageIdx, dataset, preset, params);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load netlist");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [imageIdx, dataset, preset, params]);

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  const handleCopy = async () => {
    if (!data?.spice_netlist) return;
    try {
      await navigator.clipboard.writeText(data.spice_netlist);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  if (loading) {
    return (
      <div className="panel-content">
        <div className="panel-content-inner">
          <div className="loading-overlay">
            <div className="loading-spinner" />
          </div>
          <span className="viewport-empty">Loading netlist…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel-content">
        <div className="panel-content-inner">
          <div className="netlist-error">{error}</div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="panel-content">
        <div className="panel-content-inner">
          <span className="viewport-empty">No netlist data</span>
        </div>
      </div>
    );
  }

  return (
    <div className="panel-content">
      <div className="panel-content-inner">
        {/* Warnings */}
        {data.warnings.length > 0 && (
          <div className="netlist-section">
            <div className="netlist-section-title">Warnings</div>
            {data.warnings.map((w, i) => (
              <div key={i} className="netlist-warning">{w}</div>
            ))}
          </div>
        )}

        {/* SPICE Netlist */}
        <div className="netlist-section">
          {/* role=button (not <button>) so the Copy <button> can nest legally —
              a <button> inside a <button> is invalid HTML / a hydration error. */}
          <div
            className="netlist-section-title netlist-collapsible"
            role="button"
            tabIndex={0}
            onClick={() => setNetlistExpanded((v) => !v)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setNetlistExpanded((v) => !v); } }}
          >
            {netlistExpanded ? "▾" : "▸"} SPICE Netlist
            <button
              className="netlist-copy-btn"
              onClick={(e) => { e.stopPropagation(); handleCopy(); }}
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
          {netlistExpanded && (
            <pre className="netlist-code">{data.spice_netlist}</pre>
          )}
        </div>

        {/* Components */}
        {data.components.length > 0 && (
          <div className="netlist-section">
            <div className="netlist-section-title">Components ({data.components.length})</div>
            <table className="netlist-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Pins</th>
                </tr>
              </thead>
              <tbody>
                {data.components.map((c, i) => (
                  <tr key={i}>
                    <td className="netlist-cell-mono">{c.name}</td>
                    <td>{c.type}</td>
                    <td className="netlist-cell-mono">{c.pins.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Nodes */}
        {data.nodes.length > 0 && (
          <div className="netlist-section">
            <div className="netlist-section-title">Nodes ({data.nodes.length})</div>
            <table className="netlist-table">
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Connected Pins</th>
                </tr>
              </thead>
              <tbody>
                {data.nodes.map((n) => (
                  <tr key={n.id}>
                    <td className="netlist-cell-mono">N{n.id}</td>
                    <td>
                      {n.pins.map((p, j) => (
                        <span key={j} className="netlist-pin-tag">
                          {p.component}.{p.pin}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Empty state */}
        {data.components.length === 0 && data.nodes.length === 0 && (
          <div className="netlist-section">
            <span className="viewport-empty">No components or nodes found</span>
          </div>
        )}
      </div>
    </div>
  );
}

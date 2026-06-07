"use client";

import { useState } from "react";
import type { NetlistResult } from "@/lib/types";

interface NetlistTabProps {
  netlist: NetlistResult | null;
  spiceNetlist: string | null;
  loading: boolean;
  error: string | null;
}

/**
 * Bottom-panel Netlist tab: SPICE code + component table + node connectivity table.
 * Self-contained — receives data as props, no internal fetching.
 */
export default function NetlistTab({ netlist, spiceNetlist, loading, error }: NetlistTabProps) {
  const [copied, setCopied] = useState(false);
  const [showSpice, setShowSpice] = useState(true);
  const [showComponents, setShowComponents] = useState(true);
  const [showNodes, setShowNodes] = useState(true);

  const handleCopy = async () => {
    const text = spiceNetlist ?? netlist?.spice_netlist ?? "";
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard not available */
    }
  };

  if (loading) {
    return (
      <div className="netlist-tab">
        <div className="loading-overlay">
          <div className="loading-spinner" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="netlist-tab">
        <div className="netlist-warning">{error}</div>
      </div>
    );
  }

  const spice = spiceNetlist ?? netlist?.spice_netlist;
  const components = netlist?.components ?? [];
  const nodes = netlist?.nodes ?? [];
  const warnings = netlist?.warnings ?? [];

  return (
    <div className="netlist-tab">
      {/* SPICE Netlist */}
      <div className="netlist-section">
        <div
          className="netlist-section-title netlist-collapsible"
          role="button"
          tabIndex={0}
          onClick={() => setShowSpice(!showSpice)}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setShowSpice(!showSpice); } }}
        >
          {showSpice ? "▾" : "▸"} SPICE Netlist
          <button
            className="netlist-copy-btn"
            onClick={(e) => { e.stopPropagation(); handleCopy(); }}
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
        {showSpice && spice && (
          <pre className="netlist-code">{spice}</pre>
        )}
        {showSpice && !spice && (
          <div className="viewport-empty">No SPICE netlist available</div>
        )}
      </div>

      {/* Component Table */}
      {components.length > 0 && (
        <div className="netlist-section">
          <div
            className="netlist-section-title netlist-collapsible"
            role="button"
            tabIndex={0}
            onClick={() => setShowComponents(!showComponents)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setShowComponents(!showComponents); } }}
          >
            {showComponents ? "▾" : "▸"} Components ({components.length})
          </div>
          {showComponents && (
            <table className="netlist-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Pins</th>
                </tr>
              </thead>
              <tbody>
                {components.map((c) => (
                  <tr key={c.name}>
                    <td className="netlist-cell-mono">{c.name}</td>
                    <td>{c.type}</td>
                    <td className="netlist-cell-mono">{c.pins.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Node Connectivity Table */}
      {nodes.length > 0 && (
        <div className="netlist-section">
          <div
            className="netlist-section-title netlist-collapsible"
            role="button"
            tabIndex={0}
            onClick={() => setShowNodes(!showNodes)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setShowNodes(!showNodes); } }}
          >
            {showNodes ? "▾" : "▸"} Nodes ({nodes.length})
          </div>
          {showNodes && (
            <table className="netlist-table">
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Connected Pins</th>
                </tr>
              </thead>
              <tbody>
                {nodes.map((n) => (
                  <tr key={n.id}>
                    <td className="netlist-cell-mono">net_{n.id}</td>
                    <td>
                      {n.pins.map((p) => (
                        <span key={`${p.component}-${p.pin}`} className="netlist-pin-tag">
                          {p.component}.{p.pin}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="netlist-section">
          <div className="netlist-section-title">Warnings</div>
          {warnings.map((w, i) => (
            <div key={i} className="netlist-warning">{w}</div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!spice && components.length === 0 && nodes.length === 0 && warnings.length === 0 && (
        <div className="netlist-section">
          <div className="viewport-empty">No netlist data available</div>
        </div>
      )}
    </div>
  );
}

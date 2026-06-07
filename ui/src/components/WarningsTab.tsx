"use client";

import type { NetlistResult } from "@/lib/types";

interface WarningsTabProps {
  netlist: NetlistResult | null;
  loading: boolean;
}

/**
 * Bottom-panel Warnings tab: structural errors + join quality analysis.
 * Detects self-loops, floating components, and giant nets.
 */
export default function WarningsTab({ netlist, loading }: WarningsTabProps) {
  if (loading) {
    return (
      <div className="warnings-tab">
        <div className="loading-overlay">
          <div className="loading-spinner" />
        </div>
      </div>
    );
  }

  if (!netlist) {
    return (
      <div className="warnings-tab">
        <div className="viewport-empty">No netlist data — run pipeline first</div>
      </div>
    );
  }

  const warnings = netlist.warnings ?? [];
  const components = netlist.components ?? [];
  const nodes = netlist.nodes ?? [];

  // Detect self-loops: components where all pins map to the same node
  const selfLoops = components.filter((c) => {
    if (c.pins.length < 2) return false;
    const nodeIds = new Set<number>();
    for (const node of nodes) {
      if (node.pins.some((p) => p.component === c.name)) {
        nodeIds.add(node.id);
      }
    }
    // All pins connect to exactly one node = self-loop
    return nodeIds.size === 1 && c.pins.length >= 2;
  });

  // Detect floating components: no pins in any node
  const floatingComponents = components.filter((c) => {
    return !nodes.some((n) => n.pins.some((p) => p.component === c.name));
  });

  // Detect giant nets: nodes with unusually many pins
  const giantNets = nodes.filter((n) => n.pins.length > 10);

  const hasIssues = warnings.length > 0 || selfLoops.length > 0 || floatingComponents.length > 0 || giantNets.length > 0;

  return (
    <div className="warnings-tab">
      {/* Structural Warnings from Backend */}
      {warnings.length > 0 && (
        <div className="netlist-section">
          <div className="netlist-section-title">Structural Warnings ({warnings.length})</div>
          {warnings.map((w, i) => (
            <div key={i} className="netlist-warning">{w}</div>
          ))}
        </div>
      )}

      {/* Self-Loops */}
      {selfLoops.length > 0 && (
        <div className="netlist-section">
          <div className="netlist-section-title">Self-Loops ({selfLoops.length})</div>
          <div className="active-params">
            {selfLoops.map((c) => (
              <span key={c.name} className="netlist-pin-tag">{c.name}</span>
            ))}
          </div>
        </div>
      )}

      {/* Floating Components */}
      {floatingComponents.length > 0 && (
        <div className="netlist-section">
          <div className="netlist-section-title">Floating Components ({floatingComponents.length})</div>
          <div className="active-params">
            {floatingComponents.map((c) => (
              <span key={c.name} className="netlist-pin-tag">{c.name}</span>
            ))}
          </div>
        </div>
      )}

      {/* Giant Nets */}
      {giantNets.length > 0 && (
        <div className="netlist-section">
          <div className="netlist-section-title">Giant Nets ({giantNets.length})</div>
          <div className="active-params">
            {giantNets.map((n) => (
              <span key={n.id} className="netlist-pin-tag">
                net_{n.id} ({n.pins.length} pins)
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Join Quality Summary */}
      <div className="netlist-section">
        <div className="netlist-section-title">Join Quality</div>
        <table className="netlist-table">
          <tbody>
            <tr>
              <td>Components</td>
              <td className="netlist-cell-mono">{components.length}</td>
            </tr>
            <tr>
              <td>Nets</td>
              <td className="netlist-cell-mono">{nodes.length}</td>
            </tr>
            <tr>
              <td>Self-Loops</td>
              <td className={`netlist-cell-mono ${selfLoops.length > 0 ? "netlist-warning-text" : ""}`}>
                {selfLoops.length}
              </td>
            </tr>
            <tr>
              <td>Floating</td>
              <td className={`netlist-cell-mono ${floatingComponents.length > 0 ? "netlist-warning-text" : ""}`}>
                {floatingComponents.length}
              </td>
            </tr>
            <tr>
              <td>Giant Nets</td>
              <td className={`netlist-cell-mono ${giantNets.length > 0 ? "netlist-warning-text" : ""}`}>
                {giantNets.length}
              </td>
            </tr>
            <tr>
              <td>Warnings</td>
              <td className={`netlist-cell-mono ${warnings.length > 0 ? "netlist-warning-text" : ""}`}>
                {warnings.length}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* No Issues */}
      {!hasIssues && (
        <div className="netlist-section">
          <div className="netlist-section-title">No Issues Found</div>
          <div className="viewport-empty">Circuit structure looks good</div>
        </div>
      )}
    </div>
  );
}

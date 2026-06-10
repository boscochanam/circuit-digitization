"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import type { TopologyResult, ConnectionOverrides, PinRef } from "@/lib/types";
import type { EditMode } from "./TopologyOverlay";

export interface TopoHighlight {
  component?: string;
  pin?: [number, number];
}

interface Props {
  topology: TopologyResult;
  selectedEndpoint: string | null;
  overrides: ConnectionOverrides;
  editMode: EditMode;
  joinSource: string | null;
  onSetEditMode: (m: EditMode) => void;
  onSetJoinSource: (k: string | null) => void;
  onReassign: (endpointKey: string, componentName: string, pinName: string) => void;
  onConnectPins: (a: PinRef, b: PinRef) => void;
  onDisconnect: (endpointKey: string) => void;
  onResetOverrides: () => void;
  onUpdateOverrides: (next: ConnectionOverrides) => void;
  onClearSelection: () => void;
  onHighlight: (h: TopoHighlight | null) => void;
  onSelectComponent: (name: string | null) => void;
  onQuickFix?: (endpointKey: string, componentName: string, pinName: string) => void;
}

const EP_RE = /^wire_(\d+)_ep(\d)$/;
const isElectrical = (type: string) => type !== "text";

function parseOverrides(text: string): { ok: true; data: ConnectionOverrides } | { ok: false; error: string } {
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed !== "object" || parsed === null) return { ok: false, error: "Expected a JSON object" };
    if (!("reassign" in parsed) || !("join" in parsed) || !("remove" in parsed))
      return { ok: false, error: "Missing required keys: reassign, join, remove" };
    if (typeof parsed.reassign !== "object") return { ok: false, error: "'reassign' must be an object" };
    if (!Array.isArray(parsed.join)) return { ok: false, error: "'join' must be an array" };
    if (!Array.isArray(parsed.remove)) return { ok: false, error: "'remove' must be an array" };
    return { ok: true, data: parsed as ConnectionOverrides };
  } catch (e) {
    return { ok: false, error: `Invalid JSON: ${e instanceof Error ? e.message : e}` };
  }
}

export default function ConnectionEditorPanel({
  topology,
  selectedEndpoint,
  overrides,
  editMode,
  joinSource,
  onSetEditMode,
  onSetJoinSource,
  onReassign,
  onConnectPins,
  onDisconnect,
  onResetOverrides,
  onUpdateOverrides,
  onClearSelection,
  onHighlight,
  onSelectComponent,
  onQuickFix,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const [legendOpen, setLegendOpen] = useState(false);

  useEffect(() => {
    if (selectedEndpoint) setCollapsed(false);
  }, [selectedEndpoint]);

  useEffect(() => {
    if (!copySuccess) return;
    const t = setTimeout(() => setCopySuccess(false), 2000);
    return () => clearTimeout(t);
  }, [copySuccess]);

  const handleCopy = useCallback(() => {
    const json = JSON.stringify(overrides, null, 2);
    navigator.clipboard.writeText(json).then(() => setCopySuccess(true));
  }, [overrides]);

  const handleImport = useCallback(() => {
    const result = parseOverrides(importText);
    if (!result.ok) {
      setImportError(result.error);
      return;
    }
    onUpdateOverrides(result.data);
    setImportOpen(false);
    setImportText("");
    setImportError(null);
  }, [importText, onUpdateOverrides]);

  const totalOverrides =
    Object.keys(overrides.reassign).length + overrides.join.length + overrides.remove.length +
    (overrides.merge?.length ?? 0);

  // All electrical pins, for the panel-based pin <-> pin connector.
  const electricalPins = useMemo(() => {
    const elec = new Set(topology.components.filter((c) => isElectrical(c.type)).map((c) => c.name));
    return topology.pins
      .filter((p) => elec.has(p.component_name))
      .map((p) => ({ component: p.component_name, pin: p.pin_name, node_id: p.node_id }));
  }, [topology.pins, topology.components]);

  const [pinA, setPinA] = useState("");
  const [pinB, setPinB] = useState("");
  const parsePinKey = (k: string): PinRef | null => {
    const i = k.lastIndexOf(".");
    return i < 0 ? null : { component: k.slice(0, i), pin: k.slice(i + 1) };
  };

  // node_id -> component names on that node (so we can show what each pin connects
  // to). Text labels are excluded — they aren't electrical connections, so listing
  // them as net members made unconnected pins look connected.
  const nodeMembers = useMemo(() => {
    const elec = new Set(
      topology.components.filter((c) => isElectrical(c.type)).map((c) => c.name),
    );
    const m = new Map<number, string[]>();
    for (const p of topology.pins) {
      if (p.node_id === null || !elec.has(p.component_name)) continue;
      const arr = m.get(p.node_id) ?? [];
      if (!arr.includes(p.component_name)) arr.push(p.component_name);
      m.set(p.node_id, arr);
    }
    return m;
  }, [topology.pins, topology.components]);

  // Selected endpoint -> its coords + current node/pin
  const sel = useMemo(() => {
    if (!selectedEndpoint) return null;
    const m = selectedEndpoint.match(EP_RE);
    if (!m) return null;
    const wire = topology.wires.find((w) => w.idx === parseInt(m[1], 10));
    if (!wire) return null;
    const [x, y] = m[2] === "1" ? wire.ep1 : wire.ep2;
    const pin = topology.pins.find((p) => Math.abs(p.x - x) <= 6 && Math.abs(p.y - y) <= 6) ?? null;
    const nodeId = pin?.node_id ?? wire.node_id;
    return { x, y, pin, nodeId };
  }, [selectedEndpoint, topology]);

  const reassigned = selectedEndpoint ? overrides.reassign[selectedEndpoint] : undefined;
  const targets = useMemo(
    () => topology.components.filter((c) => isElectrical(c.type)),
    [topology.components],
  );

  // "Island" terminals: component pins whose net touches only their own
  // component, i.e. not wired to anything else. The join leaves essentially no
  // truly floating wires, but it does leave these dead-ends — they're the real
  // "not connected" signal worth surfacing (ringed amber on the diagram).
  const floatingPins = useMemo(() => {
    const elec = new Set(
      topology.components.filter((c) => isElectrical(c.type)).map((c) => c.name),
    );
    const deadEnd = new Set(
      topology.nodes.filter((n) => n.component_count === 1).map((n) => n.node_id),
    );
    return topology.pins.filter(
      (p) => p.node_id !== null && deadEnd.has(p.node_id) && elec.has(p.component_name),
    );
  }, [topology.pins, topology.nodes, topology.components]);
  const unconnectedCount = floatingPins.length;

  // At-a-glance overview: how many real parts and how many distinct nets they
  // form (text-label pins excluded so the net count reflects the actual circuit).
  const stats = useMemo(() => {
    const elec = new Set(
      topology.components.filter((c) => isElectrical(c.type)).map((c) => c.name),
    );
    const nets = new Set<number>();
    for (const p of topology.pins) {
      if (p.node_id !== null && elec.has(p.component_name)) nets.add(p.node_id);
    }
    return { parts: elec.size, nets: nets.size };
  }, [topology.components, topology.pins]);

  const membersOf = (nodeId: number | null | undefined, exclude?: string) =>
    nodeId === null || nodeId === undefined
      ? []
      : (nodeMembers.get(nodeId) ?? []).filter((n) => n !== exclude);

  const findNearestPin = useCallback((endpointKey: string): { componentName: string; pinName: string } | null => {
    const m = endpointKey.match(EP_RE);
    if (!m) return null;
    const wire = topology.wires.find((w) => w.idx === parseInt(m[1], 10));
    if (!wire) return null;
    const [x, y] = m[2] === "1" ? wire.ep1 : wire.ep2;

    const deadEnd = new Set(
      topology.nodes.filter((n) => n.component_count === 1).map((n) => n.node_id),
    );

    let bestDist = Infinity;
    let bestPin: { componentName: string; pinName: string } | null = null;

    for (const pin of topology.pins) {
      if (pin.node_id !== null && deadEnd.has(pin.node_id)) continue;
      const w = topology.wires.find((ww) => ww.idx === parseInt(m[1], 10));
      if (w && pin.node_id === w.node_id) continue;

      const dist = Math.sqrt((pin.x - x) ** 2 + (pin.y - y) ** 2);
      if (dist < bestDist && dist < 50) {
        bestDist = dist;
        bestPin = { componentName: pin.component_name, pinName: pin.pin_name };
      }
    }
    return bestPin;
  }, [topology]);

  const nearestPin = selectedEndpoint ? findNearestPin(selectedEndpoint) : null;

  if (collapsed) {
    return (
      <button
        className="conn-collapsed"
        onClick={() => setCollapsed(false)}
        onMouseDown={(e) => e.stopPropagation()}
        title="Show connection editor"
      >
        ‹ Editor{totalOverrides > 0 ? ` · ${totalOverrides}` : ""}
      </button>
    );
  }

  return (
    <div className="conn-editor" onMouseLeave={() => onHighlight(null)} onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <div className="conn-editor-head">
        <span>Connection editor</span>
        <span style={{ display: "flex", gap: 6 }}>
          <button
            className="conn-reset"
            onClick={handleCopy}
            title="Copy overrides as JSON to clipboard"
          >
            {copySuccess ? "Copied!" : "Copy"}
          </button>
          <button
            className="conn-reset"
            onClick={() => { setImportOpen(!importOpen); setImportText(JSON.stringify(overrides, null, 2)); setImportError(null); }}
            title="Import overrides from JSON"
          >
            Import
          </button>
          {totalOverrides > 0 && (
            <button className="conn-reset" onClick={onResetOverrides} title="Clear all manual overrides">
              Reset {totalOverrides}
            </button>
          )}
          {selectedEndpoint && (
            <button className="conn-reset" onClick={onClearSelection} title="Deselect (Esc)">✕</button>
          )}
          <button className="conn-reset" onClick={() => setLegendOpen(!legendOpen)} title="What the colours, dots and rings mean">ⓘ</button>
          <button className="conn-reset" onClick={() => setCollapsed(true)} title="Collapse panel (free the diagram)">–</button>
        </span>
      </div>

      {legendOpen && (
        <div className="conn-legend">
          <div className="conn-sub">What you&apos;re looking at</div>
          <div className="conn-legend-row">
            <span className="conn-legend-swatch">
              <svg width="34" height="10" aria-hidden>
                <rect x="0" width="10" height="10" fill="#e6194b" /><rect x="12" width="10" height="10" fill="#3cb44b" /><rect x="24" width="10" height="10" fill="#4363d8" />
              </svg>
            </span>
            <span>Each <strong>colour</strong> is one electrical net — same colour = same node.</span>
          </div>
          <div className="conn-legend-row">
            <span className="conn-legend-swatch"><svg width="14" height="14" aria-hidden><circle cx="7" cy="7" r="4.5" fill="#22c55e" /></svg></span>
            <span><strong>Green</strong> wire-end dot — connected to a multi-component net.</span>
          </div>
          <div className="conn-legend-row">
            <span className="conn-legend-swatch"><svg width="14" height="14" aria-hidden><circle cx="7" cy="7" r="4.5" fill="#ef4444" /></svg></span>
            <span><strong>Red</strong> wire-end dot — dangling. Click it, then <strong>⚡ Quick Fix</strong> to auto-connect.</span>
          </div>
          <div className="conn-legend-row">
            <span className="conn-legend-swatch"><svg width="14" height="14" aria-hidden><circle cx="7" cy="7" r="5" fill="none" stroke="#f59e0b" strokeWidth="2" /></svg></span>
            <span><strong>Amber ring</strong> on a pin — a component terminal not wired to anything else (turn on the Pins layer).</span>
          </div>
          <p className="conn-hint" style={{ marginTop: 4 }}>
            Click a white endpoint dot to <strong>Connect / Join / Disconnect</strong>; hover any wire or pin to read its net.
          </p>
        </div>
      )}

      {importOpen && (
        <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--grey-mid)" }}>
          <div className="conn-sub">Import overrides (JSON)</div>
          <textarea
            value={importText}
            onChange={(e) => { setImportText(e.target.value); setImportError(null); }}
            style={{
              width: "100%", minHeight: 120, fontFamily: "monospace", fontSize: 11,
              background: "var(--white)", color: "var(--black)", border: "1px solid var(--black)",
              borderRadius: 0, padding: 6, resize: "vertical",
            }}
            placeholder='{"reassign": {}, "join": [], "remove": []}'
          />
          {importError && (
            <div style={{ color: "var(--error)", fontSize: 11, marginTop: 4 }}>{importError}</div>
          )}
          <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
            <button className="conn-btn" onClick={handleImport}>Apply</button>
            <button className="conn-btn conn-cancel" onClick={() => { setImportOpen(false); setImportError(null); }}>Cancel</button>
          </div>
        </div>
      )}

      {!selectedEndpoint || !sel ? (
        <div className="conn-body">
          <div className="conn-overview">
            <span><strong>{stats.parts}</strong> parts</span>
            <span><strong>{stats.nets}</strong> nets</span>
            {unconnectedCount > 0 && (
              <span className="conn-floating"><strong>{unconnectedCount}</strong> unconnected</span>
            )}
          </div>
          <p className="conn-hint">
            Each colour on the diagram is one electrical net. Click a wire endpoint (the white
            dots) to edit its connection, or hover any wire/pin to read its net.
          </p>

          <div className="conn-connect-pins">
            <div className="conn-sub">Connect two pins (no wire needed)</div>
            <select className="conn-pin-select" value={pinA} onChange={(e) => setPinA(e.target.value)}>
              <option value="">Pin A…</option>
              {electricalPins.map((p) => (
                <option key={`a-${p.component}.${p.pin}`} value={`${p.component}.${p.pin}`}>
                  {p.component}.{p.pin}{p.node_id !== null ? ` · Node ${p.node_id}` : ""}
                </option>
              ))}
            </select>
            <select className="conn-pin-select" value={pinB} onChange={(e) => setPinB(e.target.value)}>
              <option value="">Pin B…</option>
              {electricalPins.map((p) => (
                <option key={`b-${p.component}.${p.pin}`} value={`${p.component}.${p.pin}`}>
                  {p.component}.{p.pin}{p.node_id !== null ? ` · Node ${p.node_id}` : ""}
                </option>
              ))}
            </select>
            <button
              className="conn-btn"
              disabled={!pinA || !pinB || pinA === pinB}
              onClick={() => {
                const a = parsePinKey(pinA);
                const b = parsePinKey(pinB);
                if (a && b) { onConnectPins(a, b); setPinA(""); setPinB(""); }
              }}
            >
              Connect pins
            </button>
            <p className="conn-hint">Merges the two pins&apos; nets into one node — for parts the detector left unwired.</p>
          </div>

          {unconnectedCount > 0 && (
            <div className="conn-problems-section">
              <div className="conn-sub">Needs attention</div>
              <div className="conn-floating-note">
                <strong className="conn-floating">{unconnectedCount}</strong> component{" "}
                {unconnectedCount === 1 ? "pin isn't" : "pins aren't"} wired to anything else —
                ringed <span className="conn-floating">amber</span> on the diagram. Hover a row to
                find it, click to focus, then wire up the nearby endpoint.
              </div>
              <div className="conn-problem-group">
                <div className="conn-problem-label">
                  Unconnected terminals <span className="conn-problem-count">{unconnectedCount}</span>
                </div>
                <div className="conn-problems">
                  {floatingPins.map((p, i) => (
                    <button
                      key={`${p.component_name}-${p.pin_name}-${i}`}
                      className="conn-problem-row"
                      onMouseEnter={() => onHighlight({ component: p.component_name, pin: [p.x, p.y] })}
                      onClick={() => onSelectComponent(p.component_name)}
                    >
                      <span className="conn-problem-name">{p.component_name}.{p.pin_name}</span>
                      <span className="conn-problem-meta">Node {p.node_id}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
          {totalOverrides > 0 && (
            <div className="conn-overrides">
              <div className="conn-sub">Manual edits</div>
              {Object.entries(overrides.reassign).map(([k, v]) => (
                <div key={k} className="conn-ov-row">
                  <span>↪ {k} → {v.component}.{v.pin}</span>
                  <button
                    className="conn-ov-undo"
                    title="Undo this edit"
                    onClick={() => {
                      const reassign = { ...overrides.reassign };
                      delete reassign[k];
                      onUpdateOverrides({ ...overrides, reassign });
                    }}
                  >↺</button>
                </div>
              ))}
              {overrides.join.map((p, i) => (
                <div key={`j${i}`} className="conn-ov-row">
                  <span>⤬ {p[0]} ↔ {p[1]}</span>
                  <button
                    className="conn-ov-undo"
                    title="Undo this edit"
                    onClick={() => onUpdateOverrides({ ...overrides, join: overrides.join.filter((_, idx) => idx !== i) })}
                  >↺</button>
                </div>
              ))}
              {overrides.remove.map((k) => (
                <div key={k} className="conn-ov-row">
                  <span>✕ {k} disconnected</span>
                  <button
                    className="conn-ov-undo"
                    title="Undo this edit"
                    onClick={() => onUpdateOverrides({ ...overrides, remove: overrides.remove.filter((x) => x !== k) })}
                  >↺</button>
                </div>
              ))}
              {(overrides.merge ?? []).map((p, i) => (
                <div key={`m${i}`} className="conn-ov-row">
                  <span>⊕ {p[0].component}.{p[0].pin} ↔ {p[1].component}.{p[1].pin}</span>
                  <button
                    className="conn-ov-undo"
                    title="Undo this edit"
                    onClick={() => onUpdateOverrides({ ...overrides, merge: (overrides.merge ?? []).filter((_, idx) => idx !== i) })}
                  >↺</button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="conn-body">
          <div className="conn-sub">Selected endpoint</div>
          <div className="conn-cur">
            <strong>{selectedEndpoint}</strong>
            {sel.pin && <span className="conn-near"> · near {sel.pin.component_name}</span>}
            <div className="conn-cur-info">
              {sel.nodeId !== null && sel.nodeId !== undefined ? (
                <>
                  Node {sel.nodeId}
                  {membersOf(sel.nodeId).length > 0
                    ? <> · with {membersOf(sel.nodeId).join(", ")}</>
                    : <span className="conn-floating"> · floating</span>}
                </>
              ) : (
                <span className="conn-floating">floating / unconnected</span>
              )}
            </div>
            {reassigned && (
              <div className="conn-tag">manually → {reassigned.component}.{reassigned.pin}</div>
            )}
          </div>

          {editMode === null && (
            <div className="conn-actions">
              <button className="conn-btn" title="Attach this endpoint to a component pin — their nets merge into one node" onClick={() => onSetEditMode("reassign")}>Connect</button>
              <button className="conn-btn" title="Connect this endpoint to another wire endpoint — their nets merge into one node" onClick={() => { onSetEditMode("join"); onSetJoinSource(selectedEndpoint); }}>Join…</button>
              <button className="conn-btn conn-btn-danger" title="Detach this endpoint from its net" onClick={() => onDisconnect(selectedEndpoint)}>Disconnect</button>
              {nearestPin && onQuickFix && (
                <button
                  className="conn-btn conn-btn-quickfix"
                  title={`Auto-connect to nearest pin: ${nearestPin.componentName}.${nearestPin.pinName}`}
                  onClick={() => onQuickFix(selectedEndpoint, nearestPin.componentName, nearestPin.pinName)}
                  style={{ background: "rgba(34,197,94,0.2)", borderColor: "rgba(34,197,94,0.5)" }}
                >
                  ⚡ Quick Fix
                </button>
              )}
            </div>
          )}

          {editMode === "reassign" && (
            <>
              <div className="conn-sub">Connect to a component pin</div>
              <p className="conn-hint">
                Merges this endpoint&apos;s net with the pin&apos;s — they become one electrical node.
              </p>
              <div className="conn-targets">
                {targets.map((comp) => (
                  <div
                    key={comp.name}
                    className="conn-comp-group"
                    onMouseEnter={() => onHighlight({ component: comp.name })}
                  >
                    <div className="conn-comp">{comp.name} <span className="conn-type">{comp.type}</span></div>
                    {topology.pins
                      .filter((p) => p.component_name === comp.name)
                      .map((pin) => {
                        const members = membersOf(pin.node_id, comp.name);
                        const floating = pin.node_id === null || members.length === 0;
                        const isCur = sel.nodeId === pin.node_id && sel.pin?.component_name === comp.name;
                        return (
                          <button
                            key={pin.pin_name}
                            className={`conn-pin ${isCur ? "conn-pin-cur" : ""}`}
                            onMouseEnter={() => onHighlight({ component: comp.name, pin: [pin.x, pin.y] })}
                            onClick={() => { onReassign(selectedEndpoint, comp.name, pin.pin_name); onSetEditMode(null); }}
                          >
                            <span className="conn-pin-name">{pin.pin_name}</span>
                            <span className="conn-pin-meta">
                              {pin.node_id !== null ? `Node ${pin.node_id}` : "—"}
                              {floating
                                ? <span className="conn-floating"> · floating</span>
                                : <> · {members.join(", ")}</>}
                              {isCur && <span className="conn-cur-mark"> ● current</span>}
                            </span>
                          </button>
                        );
                      })}
                  </div>
                ))}
              </div>
              <button className="conn-btn conn-cancel" onClick={() => onSetEditMode(null)}>Cancel</button>
            </>
          )}

          {editMode === "join" && (
            <>
              <div className="conn-sub">Join</div>
              <p className="conn-hint">
                Click another endpoint on the diagram to connect it to <strong>{joinSource}</strong>.
              </p>
              <button className="conn-btn conn-cancel" onClick={() => { onSetJoinSource(null); onSetEditMode(null); }}>Cancel</button>
            </>
          )}

          {editMode === null && (
            <button className="conn-deselect" onClick={onClearSelection}>Deselect</button>
          )}
        </div>
      )}
    </div>
  );
}

"use client";

import { useMemo } from "react";
import type { TopologyResult, ConnectionOverrides } from "@/lib/types";
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
  onDisconnect: (endpointKey: string) => void;
  onResetOverrides: () => void;
  onUpdateOverrides: (next: ConnectionOverrides) => void;
  onClearSelection: () => void;
  onHighlight: (h: TopoHighlight | null) => void;
}

const EP_RE = /^wire_(\d+)_ep(\d)$/;
// Electrically meaningful reassign targets — drop text labels (you can't wire to a label).
const isElectrical = (type: string) => type !== "text";

export default function ConnectionEditorPanel({
  topology,
  selectedEndpoint,
  overrides,
  editMode,
  joinSource,
  onSetEditMode,
  onSetJoinSource,
  onReassign,
  onDisconnect,
  onResetOverrides,
  onUpdateOverrides,
  onClearSelection,
  onHighlight,
}: Props) {
  const totalOverrides =
    Object.keys(overrides.reassign).length + overrides.join.length + overrides.remove.length;

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
  const unconnectedCount = useMemo(() => {
    const elec = new Set(
      topology.components.filter((c) => isElectrical(c.type)).map((c) => c.name),
    );
    const deadEnd = new Set(
      topology.nodes.filter((n) => n.component_count === 1).map((n) => n.node_id),
    );
    return topology.pins.filter(
      (p) => p.node_id !== null && deadEnd.has(p.node_id) && elec.has(p.component_name),
    ).length;
  }, [topology.pins, topology.nodes, topology.components]);

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

  return (
    <div className="conn-editor" onMouseLeave={() => onHighlight(null)} onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <div className="conn-editor-head">
        <span>Connection editor</span>
        <span style={{ display: "flex", gap: 6 }}>
          {totalOverrides > 0 && (
            <button className="conn-reset" onClick={onResetOverrides} title="Clear all manual overrides">
              Reset {totalOverrides}
            </button>
          )}
          {selectedEndpoint && (
            <button className="conn-reset" onClick={onClearSelection} title="Deselect (Esc)">✕</button>
          )}
        </span>
      </div>

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
          {unconnectedCount > 0 && (
            <div className="conn-floating-note">
              <strong className="conn-floating">{unconnectedCount}</strong> component{" "}
              {unconnectedCount === 1 ? "pin isn't" : "pins aren't"} wired to anything else —
              ringed <span className="conn-floating">amber</span> on the diagram (turn on the Pins
              layer). Click a nearby endpoint to connect it.
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

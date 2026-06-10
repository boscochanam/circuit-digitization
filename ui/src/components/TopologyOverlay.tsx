"use client";

import { useMemo, useEffect, useCallback } from "react";
import type { TopologyResult, PathResult, PathStep, ConnectionOverrides } from "@/lib/types";
const NODE_COLORS = [
  "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
  "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9A6324",
];

export type EditMode = "reassign" | "join" | "disconnect" | null;

interface TopologyOverlayProps {
  topology: TopologyResult;
  imgWidth: number;
  imgHeight: number;
  scaleX: number;
  scaleY: number;
  selectedNode: number | null;
  selectedComponent: string | null;
  onWireClick: (nodeId: number) => void;
  onComponentClick: (name: string, shiftKey: boolean) => void;
  onBackgroundClick: () => void;
  showWires: boolean;
  showPins: boolean;
  showComponents: boolean;
  onToggleWires?: () => void;
  onTogglePins?: () => void;
  onToggleComponents?: () => void;
  // Path tracing
  pathStart?: string | null;
  pathEnd?: string | null;
  pathData?: PathResult | null;
  // Endpoint selection & edit mode
  selectedEndpoint?: string | null; // e.g. "wire_3_ep2"
  onEndpointClick?: (endpointKey: string, shiftKey: boolean) => void;
  editMode?: EditMode;
  onSetEditMode?: (mode: EditMode) => void;
  joinSource?: string | null;
  onSetJoinSource?: (key: string | null) => void;
  // Overrides actions
  overrides?: ConnectionOverrides;
  onReassign?: (endpointKey: string, componentName: string, pinName: string) => void;
  onJoin?: (sourceEndpoint: string, targetEndpoint: string) => void;
  onDisconnect?: (endpointKey: string) => void;
  onResetOverrides?: () => void;
  // Component/pin to flash when hovering a row in the Connection editor panel.
  highlight?: { component?: string; pin?: [number, number] } | null;
}

/**
 * SVG overlay that renders wires as colored lines, pins as dots,
 * and components as translucent rects on top of the schematic image.
 * Click to highlight a net (node) or component.
 */
export default function TopologyOverlay({
  topology,
  imgWidth,
  imgHeight,
  scaleX,
  scaleY,
  selectedNode,
  selectedComponent,
  onWireClick,
  onComponentClick,
  onBackgroundClick,
  showWires,
  showPins,
  showComponents,
  onToggleWires,
  onTogglePins,
  onToggleComponents,
  pathStart = null,
  pathEnd = null,
  pathData = null,
  selectedEndpoint = null,
  onEndpointClick,
  editMode = null,
  onSetEditMode,
  joinSource = null,
  onSetJoinSource,
  overrides = { reassign: {}, join: [], remove: [] },
  onReassign,
  onJoin,
  onDisconnect,
  onResetOverrides,
  highlight = null,
}: TopologyOverlayProps) {
  // The floating edit popovers are superseded by the docked Connection editor
  // panel (rendered by CircuitViewport); kept but disabled here.
  const showFloatingPanels: boolean = false;
  // Escape: back out of the flow — first exit edit mode, then deselect.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (editMode === "join") {
        onSetJoinSource?.(null);
        onSetEditMode?.(null);
      } else if (editMode) {
        onSetEditMode?.(null);
      } else if (selectedEndpoint) {
        onBackgroundClick();
      }
    };
    if (editMode || selectedEndpoint) {
      window.addEventListener("keydown", handler);
      return () => window.removeEventListener("keydown", handler);
    }
  }, [editMode, selectedEndpoint, onSetEditMode, onSetJoinSource, onBackgroundClick]);

  // Helper functions for override visual indicators
  const isReassigned = useCallback((key: string) => key in overrides.reassign, [overrides.reassign]);
  const isRemoved = useCallback((key: string) => overrides.remove.includes(key), [overrides.remove]);
  const isJoined = useCallback((key: string) => overrides.join.some(pair => pair.includes(key)), [overrides.join]);
  const totalOverrides = Object.keys(overrides.reassign).length + overrides.remove.length + overrides.join.length;

  // Generate a consistent color for join rings based on the pair
  const JOIN_RING_COLORS = ["#22c55e", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"];
  const getJoinColor = useCallback((endpointKey: string) => {
    for (let i = 0; i < overrides.join.length; i++) {
      if (overrides.join[i].includes(endpointKey)) {
        return JOIN_RING_COLORS[i % JOIN_RING_COLORS.length];
      }
    }
    return "#888";
  }, [overrides.join]);

  // Resolve a "wire_<idx>_ep<n>" key to its [x, y] image coordinate (for drawing
  // the join links between paired endpoints).
  const endpointCoord = useCallback((key: string): [number, number] | null => {
    const m = key.match(/^wire_(\d+)_ep(\d)$/);
    if (!m || !topology) return null;
    const w = topology.wires.find((w) => w.idx === parseInt(m[1], 10));
    if (!w) return null;
    return m[2] === "1" ? w.ep1 : w.ep2;
  }, [topology]);

  // Node ids that include at least one component pin. A wire NOT on one of these
  // is "floating" — not connected to any component (the thing the editor fixes).
  const connectedNodeIds = useMemo(
    () => new Set(topology.nodes.filter((n) => n.component_count > 0).map((n) => n.node_id)),
    [topology.nodes],
  );

  // Dead-end nets: a node that touches exactly one component. Every pin on it is
  // an "island" — a terminal not tied to any *other* component. These are the
  // connections that actually need fixing (the join leaves no truly floating
  // wires, but it does leave plenty of single-component dead-ends on messy
  // hand-drawn images). We ring those pins amber so they're easy to find.
  const deadEndNodeIds = useMemo(
    () => new Set(topology.nodes.filter((n) => n.component_count === 1).map((n) => n.node_id)),
    [topology.nodes],
  );
  // Only real, electrical terminals count — text labels carry their own isolated
  // pins (and would all read as "dead-ends"), so exclude them.
  const electricalNames = useMemo(
    () => new Set(topology.components.filter((c) => c.type !== "text").map((c) => c.name)),
    [topology.components],
  );

  // node_id -> the electrical components sharing that net, for hover tooltips.
  const nodeMembers = useMemo(() => {
    const m = new Map<number, string[]>();
    for (const p of topology.pins) {
      if (p.node_id === null || !electricalNames.has(p.component_name)) continue;
      const arr = m.get(p.node_id) ?? [];
      if (!arr.includes(p.component_name)) arr.push(p.component_name);
      m.set(p.node_id, arr);
    }
    return m;
  }, [topology.pins, electricalNames]);

  // Plain-language description of the net a wire/pin sits on (SVG <title> tooltip).
  const netLabel = useCallback(
    (nodeId: number | null | undefined): string => {
      if (nodeId === null || nodeId === undefined) return "unconnected (no net)";
      const members = nodeMembers.get(nodeId) ?? [];
      if (members.length === 0) return `Node ${nodeId} · reaches no component`;
      if (members.length === 1) return `Node ${nodeId} · only ${members[0]} (dead-end)`;
      return `Node ${nodeId} · ${members.join(", ")}`;
    },
    [nodeMembers],
  );

  // Build sets of components and nodes that are part of the path
  const pathComponentNames = new Set<string>();
  const pathNodeIds = new Set<number>();
  const pathActive = pathData && pathData.path.length > 0;

  if (pathActive && pathData) {
    for (const step of pathData.path) {
      if (step.type === "component" && step.name) {
        pathComponentNames.add(step.name);
      } else if (step.type === "node" && step.node_id !== undefined) {
        pathNodeIds.add(step.node_id);
      }
    }
  }

  // Button style for the edit panel
  const btnStyle = useMemo(
    () => ({
      background: "rgba(255,255,255,0.1)",
      border: "1px solid rgba(255,255,255,0.2)",
      borderRadius: 4,
      color: "#fff",
      padding: "3px 8px",
      fontSize: 11,
      cursor: "pointer" as const,
    }),
    [],
  );

  const cancelBtnStyle = useMemo(
    () => ({
      background: "rgba(255,255,255,0.05)",
      border: "1px solid rgba(255,255,255,0.15)",
      borderRadius: 4,
      color: "#aaa",
      padding: "3px 8px",
      fontSize: 11,
      cursor: "pointer" as const,
    }),
    [],
  );

  // Parse selected endpoint to get wire index and endpoint number
  const selectedWireIdx = useMemo(() => {
    if (!selectedEndpoint) return null;
    const m = selectedEndpoint.match(/^wire_(\d+)_ep(\d)$/);
    return m ? parseInt(m[1], 10) : null;
  }, [selectedEndpoint]);

  const selectedEpNum = useMemo(() => {
    if (!selectedEndpoint) return null;
    const m = selectedEndpoint.match(/^wire_(\d+)_ep(\d)$/);
    return m ? parseInt(m[2], 10) : null;
  }, [selectedEndpoint]);

  // Find the selected wire
  const selectedWire = useMemo(() => {
    if (selectedWireIdx === null || !topology) return null;
    return topology.wires.find((w) => w.idx === selectedWireIdx) ?? null;
  }, [topology, selectedWireIdx]);

  // Get endpoint coordinates for the selected endpoint
  const selectedEpCoords = useMemo(() => {
    if (!selectedWire || selectedEpNum === null) return null;
    return selectedEpNum === 1 ? selectedWire.ep1 : selectedWire.ep2;
  }, [selectedWire, selectedEpNum]);

  // Find which pin/node/component this endpoint connects to
  const endpointInfo = useMemo(() => {
    if (!selectedEpCoords || !topology || selectedWireIdx === null) {
      return {
        nodeId: null as number | null,
        pinName: null as string | null,
        componentName: null as string | null,
      };
    }
    const [epx, epy] = selectedEpCoords;
    const TOLERANCE = 5;

    // Check if any pin matches this endpoint
    for (const pin of topology.pins) {
      if (
        Math.abs(pin.x - epx) <= TOLERANCE &&
        Math.abs(pin.y - epy) <= TOLERANCE
      ) {
        // Find component that contains this pin (by bbox containment)
        for (const comp of topology.components) {
          const [x1, y1, x2, y2] = comp.bbox;
          if (epx >= x1 && epx <= x2 && epy >= y1 && epy <= y2) {
            return {
              nodeId: pin.node_id,
              pinName: `pin (${Math.round(pin.x)},${Math.round(pin.y)})`,
              componentName: comp.name,
            };
          }
        }
        return {
          nodeId: pin.node_id,
          pinName: `pin (${Math.round(pin.x)},${Math.round(pin.y)})`,
          componentName: null,
        };
      }
    }

    // Fall back to wire's node_id and find component containing endpoint
    const wire = topology.wires.find((w) => w.idx === selectedWireIdx);
    if (wire) {
      for (const comp of topology.components) {
        const [x1, y1, x2, y2] = comp.bbox;
        if (epx >= x1 && epx <= x2 && epy >= y1 && epy <= y2) {
          return {
            nodeId: wire.node_id,
            pinName: null,
            componentName: comp.name,
          };
        }
      }
      return { nodeId: wire.node_id, pinName: null, componentName: null };
    }
    return { nodeId: null, pinName: null, componentName: null };
  }, [topology, selectedEpCoords, selectedWireIdx]);

  // Use percentage sizing so the SVG fills its container div (which is already
  // sized to the displayed image dimensions). Coordinates are pre-scaled by
  // scaleX/scaleY so they map correctly regardless of SVG intrinsic size.
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        overflow: "hidden",
      }}
    >
      <svg
        width="100%"
        height="100%"
        style={{ pointerEvents: "none" }}
        onClick={onBackgroundClick}
      >
        {/* Background click target — first child so it doesn't intercept children */}
        <rect
          x={0}
          y={0}
          width="100%"
          height="100%"
          fill="transparent"
          style={{ pointerEvents: "all", cursor: "default" }}
          onClick={(e) => {
            e.stopPropagation();
            onBackgroundClick();
          }}
        />
        {/* Wires */}
        {showWires &&
          topology.wires.map((wire) => {
            const wireColor =
              NODE_COLORS[(wire.node_id ?? 0) % NODE_COLORS.length];
            const nodeInPath =
              wire.node_id !== null && pathNodeIds.has(wire.node_id);
            const dimmed = selectedNode !== null && wire.node_id !== selectedNode;
            // Floating wire: its net touches no component pin — flag it in red.
            const unconnected = wire.node_id === null || !connectedNodeIds.has(wire.node_id);

            let strokeColor = unconnected ? "#ef4444" : wireColor;
            let strokeW = unconnected ? 2.5 : 2;
            let opacity = dimmed ? 0.15 : 0.8;

            if (pathActive && nodeInPath) {
              strokeColor = "#FFD700";
              strokeW = 3;
              opacity = 1;
            } else if (pathActive && !nodeInPath) {
              opacity = 0.08;
            }

            // Highlight wire if its endpoint is selected — bright cyan so the
            // selected wire is unmistakable against the node-coloured ones.
            const isEndpointSelected = selectedWireIdx === wire.idx;
            if (isEndpointSelected) {
              strokeColor = "#22d3ee";
              strokeW = 3.5;
              opacity = 1;
            }

            return (
              <g key={`w-${wire.idx}`}>
                {(() => {
                  const ep1Key = `wire_${wire.idx}_ep1`;
                  const ep2Key = `wire_${wire.idx}_ep2`;
                  const wireDashed = isRemoved(ep1Key) || isRemoved(ep2Key) || unconnected;
                  return (
                    <line
                      x1={wire.ep1[0] * scaleX}
                      y1={wire.ep1[1] * scaleY}
                      x2={wire.ep2[0] * scaleX}
                      y2={wire.ep2[1] * scaleY}
                      stroke={strokeColor}
                      strokeWidth={strokeW}
                      opacity={opacity}
                      strokeDasharray={wireDashed ? "6 3" : undefined}
                      style={{ pointerEvents: "all", cursor: "pointer" }}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (wire.node_id !== null) onWireClick(wire.node_id);
                      }}
                    >
                      <title>{`Wire ${wire.idx} — ${netLabel(wire.node_id)}`}</title>
                    </line>
                  );
                })()}
                {/* Endpoint 1 — large invisible hit target + clear marker */}
                <circle
                  cx={wire.ep1[0] * scaleX}
                  cy={wire.ep1[1] * scaleY}
                  r={11}
                  fill="transparent"
                  style={{ pointerEvents: "all", cursor: "pointer" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (editMode === "join" && joinSource) {
                      const targetKey = `wire_${wire.idx}_ep1`;
                      if (targetKey !== joinSource) onJoin?.(joinSource, targetKey);
                    } else {
                      onEndpointClick?.(`wire_${wire.idx}_ep1`, e.shiftKey);
                    }
                  }}
                >
                  <title>{`Endpoint wire ${wire.idx} ep1 — ${netLabel(wire.node_id)} · click to edit`}</title>
                </circle>
                <circle
                  cx={wire.ep1[0] * scaleX}
                  cy={wire.ep1[1] * scaleY}
                  r={4.5}
                  fill={editMode === "join" && `wire_${wire.idx}_ep1` === joinSource ? "#FFD700" : "#ffffff"}
                  stroke={editMode === "join" && `wire_${wire.idx}_ep1` === joinSource ? "#FFD700" : "#15151f"}
                  strokeWidth={1.5}
                  opacity={0.92}
                  style={{ pointerEvents: "none" }}
                />
                      {/* Endpoint 1 — override indicators */}
                      {isReassigned(`wire_${wire.idx}_ep1`) && (
                      <text
                      x={wire.ep1[0] * scaleX + 6}
                      y={wire.ep1[1] * scaleY - 6}
                      fill="#FFD700"
                      fontSize={10}
                      style={{ pointerEvents: "none" }}
                      >♦</text>
                      )}
                      {isRemoved(`wire_${wire.idx}_ep1`) && (
                      <circle
                      cx={wire.ep1[0] * scaleX}
                      cy={wire.ep1[1] * scaleY}
                      r={4}
                      fill="#888"
                      stroke="#666"
                      strokeWidth={1}
                      style={{ pointerEvents: "none" }}
                      />
                      )}
                      {isJoined(`wire_${wire.idx}_ep1`) && (
                      <circle
                      cx={wire.ep1[0] * scaleX}
                      cy={wire.ep1[1] * scaleY}
                      r={8}
                      fill="none"
                      stroke={getJoinColor(`wire_${wire.idx}_ep1`)}
                      strokeWidth={2}
                      style={{ pointerEvents: "none" }}
                      />
                      )}
                {/* Endpoint 2 — large invisible hit target + clear marker */}
                <circle
                  cx={wire.ep2[0] * scaleX}
                  cy={wire.ep2[1] * scaleY}
                  r={11}
                  fill="transparent"
                  style={{ pointerEvents: "all", cursor: "pointer" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (editMode === "join" && joinSource) {
                      const targetKey = `wire_${wire.idx}_ep2`;
                      if (targetKey !== joinSource) onJoin?.(joinSource, targetKey);
                    } else {
                      onEndpointClick?.(`wire_${wire.idx}_ep2`, e.shiftKey);
                    }
                  }}
                >
                  <title>{`Endpoint wire ${wire.idx} ep2 — ${netLabel(wire.node_id)} · click to edit`}</title>
                </circle>
                <circle
                  cx={wire.ep2[0] * scaleX}
                  cy={wire.ep2[1] * scaleY}
                  r={4.5}
                  fill={editMode === "join" && `wire_${wire.idx}_ep2` === joinSource ? "#FFD700" : "#ffffff"}
                  stroke={editMode === "join" && `wire_${wire.idx}_ep2` === joinSource ? "#FFD700" : "#15151f"}
                  strokeWidth={1.5}
                  opacity={0.92}
                  style={{ pointerEvents: "none" }}
                />
                      {/* Endpoint 2 — override indicators */}
                      {isReassigned(`wire_${wire.idx}_ep2`) && (
                      <text
                      x={wire.ep2[0] * scaleX + 6}
                      y={wire.ep2[1] * scaleY - 6}
                      fill="#FFD700"
                      fontSize={10}
                      style={{ pointerEvents: "none" }}
                      >♦</text>
                      )}
                      {isRemoved(`wire_${wire.idx}_ep2`) && (
                      <circle
                      cx={wire.ep2[0] * scaleX}
                      cy={wire.ep2[1] * scaleY}
                      r={4}
                      fill="#888"
                      stroke="#666"
                      strokeWidth={1}
                      style={{ pointerEvents: "none" }}
                      />
                      )}
                      {isJoined(`wire_${wire.idx}_ep2`) && (
                      <circle
                      cx={wire.ep2[0] * scaleX}
                      cy={wire.ep2[1] * scaleY}
                      r={8}
                      fill="none"
                      stroke={getJoinColor(`wire_${wire.idx}_ep2`)}
                      strokeWidth={2}
                      style={{ pointerEvents: "none" }}
                      />
                      )}
              </g>
            );
          })}

        {/* Manual join links — a dashed line between joined endpoints, so a join
            reads as an actual connection across the image, not just two matching
            rings you have to hunt for. Colour matches the endpoints' join rings. */}
        {showWires &&
          overrides.join.map((pair, i) => {
            const a = endpointCoord(pair[0]);
            const b = endpointCoord(pair[1]);
            if (!a || !b) return null;
            const color = JOIN_RING_COLORS[i % JOIN_RING_COLORS.length];
            const mx = ((a[0] + b[0]) / 2) * scaleX;
            const my = ((a[1] + b[1]) / 2) * scaleY;
            return (
              <g key={`join-link-${i}`} style={{ pointerEvents: "none" }}>
                <line
                  x1={a[0] * scaleX}
                  y1={a[1] * scaleY}
                  x2={b[0] * scaleX}
                  y2={b[1] * scaleY}
                  stroke={color}
                  strokeWidth={2.5}
                  strokeDasharray="6 4"
                  opacity={0.95}
                />
                <circle cx={mx} cy={my} r={7} fill={color} opacity={0.9} />
                <text x={mx} y={my + 3} textAnchor="middle" fontSize={9} fontWeight={700}
                  fill="#000" style={{ pointerEvents: "none" }}>⤬</text>
              </g>
            );
          })}

        {/* Selected endpoint marker — bright cyan halo so it's unmistakable */}
        {showWires && selectedEpCoords && (
          <g style={{ pointerEvents: "none" }}>
            <circle cx={selectedEpCoords[0] * scaleX} cy={selectedEpCoords[1] * scaleY} r={13} fill="none" stroke="#22d3ee" strokeWidth={2.5} opacity={0.95} />
            <circle cx={selectedEpCoords[0] * scaleX} cy={selectedEpCoords[1] * scaleY} r={6} fill="#22d3ee" stroke="#ffffff" strokeWidth={2} />
          </g>
        )}

        {/* Pins */}
        {showPins &&
          topology.pins.map((pin, i) => {
            const color =
              NODE_COLORS[(pin.node_id ?? 0) % NODE_COLORS.length];
            const nodeInPath =
              pin.node_id !== null && pathNodeIds.has(pin.node_id);
            const dimmed =
              selectedNode !== null && pin.node_id !== selectedNode;

            let pinColor = color;
            let opacity = dimmed ? 0.15 : 1;

            if (pathActive && nodeInPath) {
              pinColor = "#FFD700";
              opacity = 1;
            } else if (pathActive && !nodeInPath) {
              opacity = 0.08;
            }

            // Island terminal: this pin's net touches only its own component
            // (and it's a real electrical part, not a text label).
            const floating =
              pin.node_id !== null &&
              deadEndNodeIds.has(pin.node_id) &&
              electricalNames.has(pin.component_name);

            return (
              <g key={`p-${i}`}>
                {floating && (
                  <circle
                    cx={pin.x * scaleX}
                    cy={pin.y * scaleY}
                    r={6.5}
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    opacity={Math.max(opacity, 0.55)}
                    style={{ pointerEvents: "none" }}
                  />
                )}
                <circle
                  cx={pin.x * scaleX}
                  cy={pin.y * scaleY}
                  r={3}
                  fill={pinColor}
                  opacity={opacity}
                  style={{ pointerEvents: "all", cursor: "pointer" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (pin.node_id !== null) onWireClick(pin.node_id);
                  }}
                >
                  <title>{`${pin.component_name}.${pin.pin_name} — ${netLabel(pin.node_id)}${floating ? " · unconnected terminal" : ""}`}</title>
                </circle>
              </g>
            );
          })}

        {/* Components */}
        {showComponents &&
          topology.components.map((comp) => {
            const color =
              NODE_COLORS[(comp.node_ids[0] ?? 0) % NODE_COLORS.length];
            const dimmed =
              selectedComponent !== null && comp.name !== selectedComponent;
            const [x1, y1, x2, y2] = comp.bbox;

            const inPath = pathComponentNames.has(comp.name);
            const isStart = comp.name === pathStart;
            const isEnd = comp.name === pathEnd;

            let rectColor = color;
            let rectFill = color;
            let fillOpacity = dimmed ? 0.03 : 0.15;
            let strokeOpacity = dimmed ? 0.1 : 1;
            let strokeWidth = 1.5;

            if (pathActive && inPath) {
              if (isStart) {
                rectColor = "#22c55e"; // green for start
                rectFill = "#22c55e";
              } else if (isEnd) {
                rectColor = "#ef4444"; // red for end
                rectFill = "#ef4444";
              } else {
                rectColor = "#FFD700"; // gold for intermediate
                rectFill = "#FFD700";
              }
              fillOpacity = 0.3;
              strokeOpacity = 1;
              strokeWidth = 3;
            } else if (pathActive && !inPath) {
              fillOpacity = 0.02;
              strokeOpacity = 0.08;
            }

            return (
              <rect
                key={`c-${comp.name}`}
                x={x1 * scaleX}
                y={y1 * scaleY}
                width={(x2 - x1) * scaleX}
                height={(y2 - y1) * scaleY}
                fill={rectFill}
                fillOpacity={fillOpacity}
                stroke={rectColor}
                strokeWidth={strokeWidth}
                strokeOpacity={strokeOpacity}
                style={{ pointerEvents: "all", cursor: "pointer" }}
                onClick={(e) => {
                  e.stopPropagation();
                  onComponentClick(comp.name, e.shiftKey);
                }}
              >
                <title>{`${comp.name} (${comp.type})${
                  comp.node_ids.filter((n) => n !== null).length
                    ? ` — Node ${comp.node_ids.filter((n) => n !== null).join(", ")}`
                    : ""
                }`}</title>
              </rect>
            );
          })}

        {/* Hover highlight driven by the Connection editor panel */}
        {highlight?.component && (() => {
          const comp = topology.components.find((c) => c.name === highlight.component);
          if (!comp) return null;
          const [x1, y1, x2, y2] = comp.bbox;
          return (
            <rect x={x1 * scaleX} y={y1 * scaleY} width={(x2 - x1) * scaleX} height={(y2 - y1) * scaleY}
              fill="#22d3ee" fillOpacity={0.18} stroke="#22d3ee" strokeWidth={3} rx={2}
              style={{ pointerEvents: "none" }} />
          );
        })()}
        {highlight?.pin && (
          <circle cx={highlight.pin[0] * scaleX} cy={highlight.pin[1] * scaleY} r={9}
            fill="none" stroke="#22d3ee" strokeWidth={3} style={{ pointerEvents: "none" }} />
        )}

      </svg>

      {/* Endpoint edit panel — main view (action buttons) */}
      {showFloatingPanels && selectedEndpoint && selectedEpCoords && !editMode && (
        <div
          style={{
            position: "absolute",
            left: selectedEpCoords[0] * scaleX + 10,
            top: selectedEpCoords[1] * scaleY - 60,
            background: "rgba(20, 20, 30, 0.95)",
            border: "1px solid rgba(255,255,255,0.2)",
            borderRadius: 8,
            padding: "8px 12px",
            color: "#fff",
            fontSize: 12,
            zIndex: 100,
            minWidth: 180,
            pointerEvents: "all",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            {selectedEndpoint}
          </div>
          <div style={{ color: "#aaa", marginBottom: 8 }}>
            {endpointInfo.nodeId !== null && `Node ${endpointInfo.nodeId}`}
            {endpointInfo.componentName &&
              ` — ${endpointInfo.componentName}`}
            {endpointInfo.pinName && `.${endpointInfo.pinName}`}
            {!endpointInfo.nodeId &&
              !endpointInfo.componentName &&
              !endpointInfo.pinName && (
                <span style={{ color: "#666" }}>Unconnected endpoint</span>
              )}
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              onClick={() => onSetEditMode?.("reassign")}
              style={btnStyle}
            >
              Reassign
            </button>
            <button
              onClick={() => {
                onSetEditMode?.("join");
                onSetJoinSource?.(selectedEndpoint);
              }}
              style={btnStyle}
            >
              Join…
            </button>
            <button
              onClick={() => onSetEditMode?.("disconnect")}
              style={btnStyle}
            >
              Disconnect
            </button>
          </div>
        </div>
      )}

      {/* Reassign panel — pin selector */}
      {showFloatingPanels && selectedEndpoint && selectedEpCoords && editMode === "reassign" && (
        <div
          style={{
            position: "absolute",
            left: selectedEpCoords[0] * scaleX + 10,
            top: selectedEpCoords[1] * scaleY - 60,
            background: "rgba(20, 20, 30, 0.95)",
            border: "1px solid rgba(255,255,255,0.2)",
            borderRadius: 8,
            padding: "8px 12px",
            color: "#fff",
            fontSize: 12,
            zIndex: 100,
            minWidth: 180,
            maxWidth: 260,
            pointerEvents: "all",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Reassign endpoint</div>
          <div style={{ maxHeight: 200, overflowY: "auto" }}>
            {topology.components.map((comp) => (
              <div key={comp.name}>
                <div style={{ color: "#888", fontSize: 10, marginTop: 4 }}>
                  {comp.name} ({comp.type})
                </div>
                {topology.pins
                  .filter((p) => p.component_name === comp.name)
                  .map((pin) => {
                    const isCurrent =
                      endpointInfo.componentName === comp.name &&
                      pin.node_id === endpointInfo.nodeId;
                    return (
                      <div
                        key={`${comp.name}.${pin.pin_name}`}
                        onClick={() => {
                          onReassign?.(selectedEndpoint, comp.name, pin.pin_name);
                          onSetEditMode?.(null);
                        }}
                        style={{
                          padding: "2px 8px",
                          cursor: "pointer",
                          borderRadius: 3,
                          background: isCurrent
                            ? "rgba(255,215,0,0.2)"
                            : "transparent",
                          fontSize: 11,
                        }}
                      >
                        {pin.pin_name} (Node {pin.node_id})
                        {isCurrent && (
                          <span style={{ color: "#FFD700", marginLeft: 4 }}>●</span>
                        )}
                      </div>
                    );
                  })}
              </div>
            ))}
          </div>
          <button
            onClick={() => onSetEditMode?.(null)}
            style={{ ...cancelBtnStyle, marginTop: 6 }}
          >
            Cancel
          </button>
        </div>
      )}

      {/* Join mode panel */}
      {showFloatingPanels && selectedEndpoint && selectedEpCoords && editMode === "join" && (
        <div
          style={{
            position: "absolute",
            left: selectedEpCoords[0] * scaleX + 10,
            top: selectedEpCoords[1] * scaleY - 60,
            background: "rgba(20, 20, 30, 0.95)",
            border: "1px solid rgba(255,215,0,0.3)",
            borderRadius: 8,
            padding: "8px 12px",
            color: "#fff",
            fontSize: 12,
            zIndex: 100,
            minWidth: 180,
            pointerEvents: "all",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Join mode</div>
          <div style={{ color: "#aaa", fontSize: 11, marginBottom: 8 }}>
            Click another endpoint to join with {joinSource}
          </div>
          <button
            onClick={() => {
              onSetJoinSource?.(null);
              onSetEditMode?.(null);
            }}
            style={cancelBtnStyle}
          >
            Cancel
          </button>
        </div>
      )}

      {/* Disconnect confirmation panel */}
      {showFloatingPanels && selectedEndpoint && selectedEpCoords && editMode === "disconnect" && (
        <div
          style={{
            position: "absolute",
            left: selectedEpCoords[0] * scaleX + 10,
            top: selectedEpCoords[1] * scaleY - 60,
            background: "rgba(20, 20, 30, 0.95)",
            border: "1px solid rgba(220,50,50,0.3)",
            borderRadius: 8,
            padding: "8px 12px",
            color: "#fff",
            fontSize: 12,
            zIndex: 100,
            minWidth: 180,
            pointerEvents: "all",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Disconnect endpoint</div>
          <div style={{ color: "#aaa", fontSize: 11, marginBottom: 8 }}>
            Remove {selectedEndpoint} from Node {endpointInfo.nodeId}?
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              onClick={() => {
                onDisconnect?.(selectedEndpoint);
                onSetEditMode?.(null);
              }}
              style={{
                ...btnStyle,
                background: "rgba(220,50,50,0.3)",
                border: "1px solid rgba(220,50,50,0.5)",
              }}
            >
              Disconnect
            </button>
            <button
              onClick={() => onSetEditMode?.(null)}
              style={cancelBtnStyle}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Control bar — top-right corner */}
      <div
        style={{
          position: "absolute",
          top: 8,
          right: 8,
          display: "flex",
          gap: 10,
          background: "rgba(0,0,0,0.7)",
          borderRadius: 6,
          padding: "4px 10px",
          fontSize: 12,
          color: "#fff",
          userSelect: "none",
        }}
      >
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={showWires}
            onChange={onToggleWires}
            style={{ pointerEvents: "all" }}
          />
          Wires
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={showPins}
            onChange={onTogglePins}
            style={{ pointerEvents: "all" }}
          />
          Pins
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={showComponents}
            onChange={onToggleComponents}
            style={{ pointerEvents: "all" }}
          />
          Components
        </label>
        {totalOverrides > 0 && (
          <span style={{
            background: "#FFD700",
            color: "#000",
            borderRadius: 10,
            padding: "1px 6px",
            fontSize: 10,
            fontWeight: 600,
            lineHeight: "16px",
          }}>
            {totalOverrides} override{totalOverrides !== 1 ? "s" : ""}
          </span>
        )}
        {totalOverrides > 0 && (
          <button
            onClick={onResetOverrides}
            style={{
              background: "rgba(220,50,50,0.3)",
              border: "1px solid rgba(220,50,50,0.5)",
              borderRadius: 4,
              color: "#fff",
              padding: "2px 8px",
              fontSize: 11,
              cursor: "pointer",
            }}
          >
            Reset
          </button>
        )}
      </div>

      {/* Path status indicator */}
      {pathActive && (
        <div
          style={{
            position: "absolute",
            top: 8,
            left: 8,
            display: "flex",
            gap: 6,
            alignItems: "center",
            background: "rgba(0,0,0,0.8)",
            borderRadius: 6,
            padding: "4px 10px",
            fontSize: 12,
            color: "#FFD700",
            userSelect: "none",
          }}
        >
          🔗 Path: {pathStart} → {pathEnd}
        </div>
      )}

      {pathStart && !pathEnd && (
        <div
          style={{
            position: "absolute",
            top: 8,
            left: 8,
            display: "flex",
            gap: 6,
            alignItems: "center",
            background: "rgba(0,0,0,0.8)",
            borderRadius: 6,
            padding: "4px 10px",
            fontSize: 12,
            color: "#22c55e",
            userSelect: "none",
          }}
        >
          📍 Start: {pathStart} — Shift+click an end component
        </div>
      )}
    </div>
  );
}

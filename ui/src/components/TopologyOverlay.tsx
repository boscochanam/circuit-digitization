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
}: TopologyOverlayProps) {
  // Escape key to exit edit mode / join mode
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (editMode === "join") {
          onSetJoinSource?.(null);
          onSetEditMode?.(null);
        } else if (editMode) {
          onSetEditMode?.(null);
        }
      }
    };
    if (editMode) {
      window.addEventListener("keydown", handler);
      return () => window.removeEventListener("keydown", handler);
    }
  }, [editMode, onSetEditMode, onSetJoinSource]);

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

            let strokeColor = wireColor;
            let strokeW = 2;
            let opacity = dimmed ? 0.15 : 0.8;

            if (pathActive && nodeInPath) {
              strokeColor = "#FFD700";
              strokeW = 3;
              opacity = 1;
            } else if (pathActive && !nodeInPath) {
              opacity = 0.08;
            }

            // Highlight wire if its endpoint is selected
            const isEndpointSelected = selectedWireIdx === wire.idx;
            if (isEndpointSelected) {
              strokeW = 3;
              opacity = 1;
            }

            return (
              <g key={`w-${wire.idx}`}>
                {(() => {
                  const ep1Key = `wire_${wire.idx}_ep1`;
                  const ep2Key = `wire_${wire.idx}_ep2`;
                  const wireDashed = isRemoved(ep1Key) || isRemoved(ep2Key);
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
                    />
                  );
                })()}
                      {/* Endpoint 1 — visible click target */}
                <circle
                  cx={wire.ep1[0] * scaleX}
                  cy={wire.ep1[1] * scaleY}
                  r={8}
                  fill={editMode === "join" && `wire_${wire.idx}_ep1` === joinSource ? "rgba(255,215,0,0.2)" : "rgba(255,255,255,0.35)"}
                  stroke={editMode === "join" ? `wire_${wire.idx}_ep1` === joinSource ? "#FFD700" : "rgba(255,255,255,0.6)" : "transparent"}
                  strokeWidth={editMode === "join" ? 1 : 0}
                  style={{
                    pointerEvents: "all",
                    cursor: editMode === "join" ? "pointer" : "pointer",
                    opacity: editMode === "join" && `wire_${wire.idx}_ep1` === joinSource ? 0.5 : 1,
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (editMode === "join" && joinSource) {
                      const targetKey = `wire_${wire.idx}_ep1`;
                      if (targetKey !== joinSource) onJoin?.(joinSource, targetKey);
                    } else {
                      onEndpointClick?.(`wire_${wire.idx}_ep1`, e.shiftKey);
                      }
                      }}
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
                      {/* Endpoint 2 — visible click target */}
                <circle
                  cx={wire.ep2[0] * scaleX}
                  cy={wire.ep2[1] * scaleY}
                  r={8}
                  fill={editMode === "join" && `wire_${wire.idx}_ep2` === joinSource ? "rgba(255,215,0,0.2)" : "rgba(255,255,255,0.35)"}
                  stroke={editMode === "join" ? `wire_${wire.idx}_ep2` === joinSource ? "#FFD700" : "rgba(255,255,255,0.6)" : "transparent"}
                  strokeWidth={editMode === "join" ? 1 : 0}
                  style={{
                    pointerEvents: "all",
                    cursor: editMode === "join" ? "pointer" : "pointer",
                    opacity: editMode === "join" && `wire_${wire.idx}_ep2` === joinSource ? 0.5 : 1,
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (editMode === "join" && joinSource) {
                      const targetKey = `wire_${wire.idx}_ep2`;
                      if (targetKey !== joinSource) onJoin?.(joinSource, targetKey);
                    } else {
                      onEndpointClick?.(`wire_${wire.idx}_ep2`, e.shiftKey);
                      }
                      }}
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

        {/* Selected endpoint marker */}
        {showWires && selectedEpCoords && (
          <circle
            cx={selectedEpCoords[0] * scaleX}
            cy={selectedEpCoords[1] * scaleY}
            r={5}
            fill={
              NODE_COLORS[((selectedWire?.node_id ?? 0) % NODE_COLORS.length)]
            }
            stroke="#fff"
            strokeWidth={2}
            style={{ pointerEvents: "none" }}
          />
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

            return (
              <circle
                key={`p-${i}`}
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
              />
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
              />
            );
          })}


      </svg>

      {/* Endpoint edit panel — main view (action buttons) */}
      {selectedEndpoint && selectedEpCoords && !editMode && (
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
      {selectedEndpoint && selectedEpCoords && editMode === "reassign" && (
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
      {selectedEndpoint && selectedEpCoords && editMode === "join" && (
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
      {selectedEndpoint && selectedEpCoords && editMode === "disconnect" && (
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

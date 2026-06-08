"use client";

import type { TopologyResult, PathResult, PathStep } from "@/lib/types";
const NODE_COLORS = [
  "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
  "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9A6324",
];

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
}: TopologyOverlayProps) {
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
        {/* Wires */}
        {showWires &&
          topology.wires.map((wire) => {
            const color = NODE_COLORS[(wire.node_id ?? 0) % NODE_COLORS.length];
            const nodeInPath = wire.node_id !== null && pathNodeIds.has(wire.node_id);
            const dimmed = selectedNode !== null && wire.node_id !== selectedNode;

            let strokeColor = color;
            let strokeW = 2;
            let opacity = dimmed ? 0.15 : 0.8;

            if (pathActive && nodeInPath) {
              strokeColor = "#FFD700";
              strokeW = 3;
              opacity = 1;
            } else if (pathActive && !nodeInPath) {
              opacity = 0.08;
            }

            return (
              <line
                key={`w-${wire.idx}`}
                x1={wire.ep1[0] * scaleX}
                y1={wire.ep1[1] * scaleY}
                x2={wire.ep2[0] * scaleX}
                y2={wire.ep2[1] * scaleY}
                stroke={strokeColor}
                strokeWidth={strokeW}
                opacity={opacity}
                style={{ pointerEvents: "all", cursor: "pointer" }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (wire.node_id !== null) onWireClick(wire.node_id);
                }}
              />
            );
          })}

        {/* Pins */}
        {showPins &&
          topology.pins.map((pin, i) => {
            const color = NODE_COLORS[(pin.node_id ?? 0) % NODE_COLORS.length];
            const nodeInPath = pin.node_id !== null && pathNodeIds.has(pin.node_id);
            const dimmed = selectedNode !== null && pin.node_id !== selectedNode;

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
            const color = NODE_COLORS[(comp.node_ids[0] ?? 0) % NODE_COLORS.length];
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

        {/* Background click target — must be last so it doesn't intercept children */}
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
      </svg>

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

"use client";

import type { TopologyResult } from "@/lib/types";

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
  onComponentClick: (name: string) => void;
  onBackgroundClick: () => void;
  showWires: boolean;
  showPins: boolean;
  showComponents: boolean;
  onToggleWires?: () => void;
  onTogglePins?: () => void;
  onToggleComponents?: () => void;
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
}: TopologyOverlayProps) {
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
            const dimmed = selectedNode !== null && wire.node_id !== selectedNode;
            return (
              <line
                key={`w-${wire.idx}`}
                x1={wire.ep1[0] * scaleX}
                y1={wire.ep1[1] * scaleY}
                x2={wire.ep2[0] * scaleX}
                y2={wire.ep2[1] * scaleY}
                stroke={color}
                strokeWidth={2}
                opacity={dimmed ? 0.15 : 0.8}
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
            const dimmed = selectedNode !== null && pin.node_id !== selectedNode;
            return (
              <circle
                key={`p-${i}`}
                cx={pin.x * scaleX}
                cy={pin.y * scaleY}
                r={3}
                fill={color}
                opacity={dimmed ? 0.15 : 1}
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
            return (
              <rect
                key={`c-${comp.name}`}
                x={x1 * scaleX}
                y={y1 * scaleY}
                width={(x2 - x1) * scaleX}
                height={(y2 - y1) * scaleY}
                fill={color}
                fillOpacity={dimmed ? 0.03 : 0.15}
                stroke={color}
                strokeWidth={1.5}
                strokeOpacity={dimmed ? 0.1 : 1}
                style={{ pointerEvents: "all", cursor: "pointer" }}
                onClick={(e) => {
                  e.stopPropagation();
                  onComponentClick(comp.name);
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
    </div>
  );
}

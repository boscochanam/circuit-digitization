"use client";

import { memo, useState, useCallback } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface CircuitNodeData {
  label: string;
  typeLabel: string;
  color: string;
  dimmed?: boolean;
  scale?: number;
  value?: string;
  onValueChange?: (name: string, value: string) => void;
  voltage?: number;
  showVoltage?: boolean;
}

function CircuitNode(props: NodeProps) {
  const { data: rawData, selected } = props;
  const {
    label,
    typeLabel,
    color,
    dimmed,
    scale = 1,
    value = "",
    onValueChange,
    voltage,
    showVoltage,
  } = rawData as unknown as CircuitNodeData;

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const baseSize = selected ? 28 : 24;
  const size = Math.round(baseSize * scale);
  const fontSize = Math.round((selected ? 9 : 7) * Math.min(scale, 1.5));
  const borderW = selected ? 2.5 : 1.5;

  const commitValue = useCallback(() => {
    setEditing(false);
    const trimmed = draft.trim();
    if (trimmed !== value && onValueChange) {
      onValueChange(label, trimmed);
    }
  }, [draft, value, label, onValueChange]);

  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setDraft(value);
      setEditing(true);
    },
    [value],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        commitValue();
      } else if (e.key === "Escape") {
        setDraft(value);
        setEditing(false);
      }
    },
    [commitValue, value],
  );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        height: "100%",
        position: "relative",
        transition: "opacity 0.2s ease",
        opacity: dimmed ? 0.25 : 1,
      }}
    >
      {/* Invisible handles for edge connections */}
      <Handle
        type="source"
        position={Position.Right}
        style={{
          opacity: 0,
          pointerEvents: "none",
          background: "transparent",
          border: "none",
        }}
      />
      <Handle
        type="target"
        position={Position.Left}
        style={{
          opacity: 0,
          pointerEvents: "none",
          background: "transparent",
          border: "none",
        }}
      />

      {/* Selection glow */}
      {selected && (
        <div
          style={{
            position: "absolute",
            width: size + 14 * scale,
            height: size + 14 * scale,
            borderRadius: "50%",
            border: `2px solid ${color}`,
            opacity: 0.3,
            pointerEvents: "none",
          }}
        >
          <style>{`
            @keyframes rf-pulse {
              0% { transform: scale(1); opacity: 0.4; }
              50% { transform: scale(1.15); opacity: 0.1; }
              100% { transform: scale(1); opacity: 0.4; }
            }
          `}</style>
          <div
            style={{
              width: "100%",
              height: "100%",
              borderRadius: "50%",
              animation: "rf-pulse 2s ease-in-out infinite",
            }}
          />
        </div>
      )}

      {/* Main circle */}
      <div
        title={`${label} (${typeLabel})`}
        style={{
          width: size,
          height: size,
          borderRadius: "50%",
          backgroundColor: color,
          opacity: selected ? 0.9 : 0.6,
          border: `${borderW}px solid ${color}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "all 0.15s ease",
          zIndex: 1,
        }}
      >
        <span
          style={{
            color: "#fff",
            fontSize,
            fontFamily: "monospace",
            fontWeight: selected ? "bold" : "normal",
            lineHeight: 1,
            userSelect: "none",
          }}
        >
          {label}
        </span>
      </div>

      {/* Type label on selection */}
      {selected && (
        <span
          style={{
            fontSize: Math.round(9 * scale),
            color: "#f4f4f5",
            fontFamily: "sans-serif",
            textAlign: "center",
            whiteSpace: "nowrap",
            pointerEvents: "none",
            zIndex: 1,
            marginTop: 2,
          }}
        >
          {typeLabel}
        </span>
      )}

      {/* Value display */}
      {editing ? (
        <input
          className="circuit-node-value-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={commitValue}
          autoFocus
          onClick={(e) => e.stopPropagation()}
          style={{ marginTop: 2 }}
        />
      ) : (
        <span
          className="circuit-node-value"
          onDoubleClick={handleDoubleClick}
          title={value ? `${label} = ${value}` : `Double-click to set value for ${label}`}
          style={{
            fontSize: Math.round(9 * scale),
          }}
        >
          {value || "\u00A0"}
        </span>
      )}

      {/* Voltage display when simOverlay is active */}
      {showVoltage && voltage !== undefined && (
        <span
          className={`circuit-node-voltage ${voltage > 2.5 ? "circuit-node-voltage-high" : "circuit-node-voltage-low"}`}
          style={{
            fontSize: Math.round(8 * scale),
          }}
        >
          {voltage.toFixed(2)}V
        </span>
      )}
    </div>
  );
}

export default memo(CircuitNode);

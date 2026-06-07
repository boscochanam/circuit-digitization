"use client";

import { useState } from "react";
import type { PipelineOverlay, CircuitOverlay, SimOverlay } from "@/stores/appStore";

interface OverlayControlsProps {
  pipelineOverlay: PipelineOverlay;
  onPipelineOverlayChange: (v: PipelineOverlay) => void;
  circuitOverlay: CircuitOverlay;
  onCircuitOverlayChange: (v: CircuitOverlay) => void;
  simOverlay: SimOverlay;
  onSimOverlayChange: (v: SimOverlay) => void;
  opacity: number;
  onOpacityChange: (v: number) => void;
}

const PIPELINE_OPTIONS: { value: PipelineOverlay; label: string }[] = [
  { value: "none", label: "Off" },
  { value: "source", label: "Source" },
  { value: "threshold", label: "Thresh" },
  { value: "detected", label: "Detect" },
  { value: "dilated", label: "Dilat" },
];

const CIRCUIT_OPTIONS: { value: CircuitOverlay; label: string }[] = [
  { value: "none", label: "Off" },
  { value: "components", label: "Comps" },
  { value: "connections", label: "Conn" },
  { value: "values", label: "Vals" },
  { value: "all", label: "All" },
];

const SIM_OPTIONS: { value: SimOverlay; label: string }[] = [
  { value: "none", label: "Off" },
  { value: "voltage", label: "Volt" },
  { value: "current", label: "Curr" },
];

export default function OverlayControls({
  pipelineOverlay,
  onPipelineOverlayChange,
  circuitOverlay,
  onCircuitOverlayChange,
  simOverlay,
  onSimOverlayChange,
  opacity,
  onOpacityChange,
}: OverlayControlsProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="overlay-controls">
      <button
        className="overlay-controls-header"
        onClick={() => setCollapsed(!collapsed)}
        type="button"
      >
        <span className="overlay-controls-title">Overlays</span>
        <span style={{ fontSize: 10, color: "#71717a" }}>
          {collapsed ? "▼" : "▲"}
        </span>
      </button>

      {!collapsed && (
        <>
          <div className="overlay-controls-label">Pipeline</div>
          <div className="overlay-toggle-group">
            {PIPELINE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                className={`overlay-toggle-btn${pipelineOverlay === opt.value ? " overlay-toggle-active" : ""}`}
                onClick={() => onPipelineOverlayChange(opt.value)}
                type="button"
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="overlay-controls-label">Circuit</div>
          <div className="overlay-toggle-group">
            {CIRCUIT_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                className={`overlay-toggle-btn${circuitOverlay === opt.value ? " overlay-toggle-active" : ""}`}
                onClick={() => onCircuitOverlayChange(opt.value)}
                type="button"
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="overlay-controls-label">Sim</div>
          <div className="overlay-toggle-group">
            {SIM_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                className={`overlay-toggle-btn${simOverlay === opt.value ? " overlay-toggle-active" : ""}`}
                onClick={() => onSimOverlayChange(opt.value)}
                type="button"
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="overlay-opacity-slider">
            <span className="overlay-opacity-label">α</span>
            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(opacity * 100)}
              onChange={(e) => onOpacityChange(parseInt(e.target.value, 10) / 100)}
            />
            <span className="overlay-opacity-value">
              {Math.round(opacity * 100)}%
            </span>
          </div>
        </>
      )}
    </div>
  );
}

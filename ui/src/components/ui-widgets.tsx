"use client";

import { useState, useEffect } from "react";

export function MetricsBar({ result, preset }: {
  result: { line_count: number; blob_count: number; elapsed_ms: number } | null;
  preset: string;
}) {
  return (
    <div className="metrics-bar">
      <div className="metric"><span className="metric-value">{result?.line_count ?? "—"}</span><span className="metric-label">Lines</span></div>
      <div className="metric"><span className="metric-value">{result?.blob_count ?? "—"}</span><span className="metric-label">Blobs</span></div>
      <div className="metric"><span className="metric-value">{result?.elapsed_ms?.toFixed(1) ?? "—"}</span><span className="metric-label">ms</span></div>
      <div className="metric-preset">{preset}</div>
    </div>
  );
}

export function ParamGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="param-group">
      <div className="param-group-title">{title}</div>
      {children}
    </div>
  );
}

export function ParamSlider({ label, value, min, max, step, unit, onChange }: {
  label: string; value: number; min: number; max: number; step: number; unit?: string;
  onChange: (v: number) => void;
}) {
  // One consistent control: label + a TYPEABLE numeric box on the top row, a
  // full-width slim slider below. Every param row has identical proportions
  // regardless of label length, and the numeric box matches the same
  // text-input interaction model used for component values — so dragging and
  // typing both work and nothing is squeezed.
  const [text, setText] = useState(String(value));
  useEffect(() => { setText(String(value)); }, [value]);

  const commit = (raw: string) => {
    const n = parseFloat(raw);
    if (Number.isNaN(n)) { setText(String(value)); return; }
    const clamped = Math.min(max, Math.max(min, n));
    setText(String(clamped));
    if (clamped !== value) onChange(clamped);
  };

  return (
    <div className="param-row">
      <div className="param-row-head">
        <span className="param-row-label">{label}</span>
        <span className="param-row-box">
          <input
            className="param-row-num"
            type="text"
            inputMode="decimal"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onBlur={(e) => commit(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
            aria-label={label}
          />
          {unit ? <span className="param-row-unit">{unit}</span> : null}
        </span>
      </div>
      <input
        className="param-range"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        aria-label={`${label} slider`}
      />
    </div>
  );
}

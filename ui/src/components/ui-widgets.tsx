"use client";

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
  return (
    <div className="param-slider">
      <span className="param-slider-label">{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="param-slider-input"
      />
      <span className="param-slider-value">{value}{unit ?? ""}</span>
    </div>
  );
}

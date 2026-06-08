"use client";

interface OverlayControlsProps {
  activeOverlay: string;
  onOverlayChange: (overlay: string) => void;
  overlayOpacity: number;
  onOpacityChange: (opacity: number) => void;
  hasPipelineResult: boolean;
  hasSimOverlay: boolean;
  onRunOCR?: () => void;
  ocrLoading?: boolean;
}

/**
 * View bar — a horizontal strip ABOVE the image (not a floating overlay, so it
 * never hides the schematic). Views are grouped by stage:
 *   Source  ·  Detection (Threshold / Detected / Dilated)  ·  Simulation (Voltage)
 * plus an opacity slider (when an overlay is shown) and the OCR action.
 */
export default function OverlayControls({
  activeOverlay,
  onOverlayChange,
  overlayOpacity,
  onOpacityChange,
  hasPipelineResult,
  hasSimOverlay,
  onRunOCR,
  ocrLoading = false,
}: OverlayControlsProps) {
  const groups: { label: string; items: { id: string; label: string; disabled?: boolean }[] }[] = [
    { label: "Source", items: [{ id: "none", label: "Source" }] },
    {
      label: "Detection",
      items: [
        { id: "threshold", label: "Threshold", disabled: !hasPipelineResult },
        { id: "detected", label: "Detected", disabled: !hasPipelineResult },
        { id: "dilated", label: "Dilated", disabled: !hasPipelineResult },
      ],
    },
    { label: "Simulation", items: [
      { id: "voltage", label: "Voltage", disabled: !hasPipelineResult },
      { id: "current", label: "Current", disabled: !hasPipelineResult },
    ] },
    { label: "Analysis", items: [
      { id: "join", label: "Join check", disabled: !hasPipelineResult },
      { id: "topology", label: "Topology", disabled: !hasPipelineResult },
    ] },
  ];

  return (
    <div className="view-bar">
      <span className="view-bar-label">VIEW</span>
      {groups.map((g, gi) => (
        <div key={g.label} className="view-group" data-group={g.label}>
          {g.items.map((o) => (
            <button
              key={o.id}
              className={`view-btn ${activeOverlay === o.id ? "active" : ""}`}
              disabled={o.disabled}
              onClick={() => onOverlayChange(o.id)}
              title={`${g.label}: ${o.label}`}
            >
              {o.label}
            </button>
          ))}
          {gi < groups.length - 1 && <span className="view-sep" aria-hidden />}
        </div>
      ))}

      {activeOverlay !== "none" && activeOverlay !== "join" && (
        <div className="view-opacity">
          <label>Opacity</label>
          <input
            type="range"
            min={0}
            max={100}
            value={overlayOpacity}
            onChange={(e) => onOpacityChange(Number(e.target.value))}
          />
          <span>{overlayOpacity}%</span>
        </div>
      )}

      {onRunOCR && (
        <button className="ocr-btn" onClick={onRunOCR} disabled={ocrLoading}>
          {ocrLoading ? "⏳ Reading…" : "🔍 Read values (OCR)"}
        </button>
      )}
    </div>
  );
}

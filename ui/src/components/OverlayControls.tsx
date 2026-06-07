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
    { label: "Simulation", items: [{ id: "voltage", label: "Voltage", disabled: !hasPipelineResult }] },
    { label: "Analysis", items: [{ id: "join", label: "Join check", disabled: !hasPipelineResult }] },
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

      <style jsx>{`
        .view-bar {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
          background: var(--white);
          border-bottom: 3px solid var(--black);
          padding: 7px 14px;
          flex-shrink: 0;
        }
        .view-bar-label {
          font-family: var(--font-mono), monospace;
          font-size: 9px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 1.5px;
          color: var(--grey-dark);
        }
        .view-group {
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .view-sep {
          width: 1px;
          height: 18px;
          background: var(--grey-mid);
          margin: 0 6px;
        }
        .view-btn {
          font-family: var(--font-mono), monospace;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.4px;
          padding: 6px 11px;
          background: var(--white);
          color: var(--black);
          border: 2px solid var(--black);
          cursor: pointer;
          line-height: 1;
        }
        .view-btn:hover:not(:disabled) { background: var(--grey-light); }
        .view-btn.active { background: var(--black); color: var(--white); }
        .view-btn:disabled { opacity: 0.35; cursor: not-allowed; }
        .view-opacity {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 10px;
          font-family: var(--font-mono), monospace;
        }
        .view-opacity label { font-weight: 700; text-transform: uppercase; color: var(--grey-dark); }
        .view-opacity input { width: 90px; }
        .view-opacity span { width: 34px; text-align: right; }
        .ocr-btn {
          margin-left: auto;
          font-family: var(--font-mono), monospace;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.4px;
          padding: 6px 11px;
          background: var(--white);
          color: var(--black);
          border: 2px solid var(--black);
          cursor: pointer;
        }
        .ocr-btn:hover:not(:disabled) { background: var(--grey-light); }
        .ocr-btn:disabled { opacity: 0.5; cursor: not-allowed; }
      `}</style>
    </div>
  );
}

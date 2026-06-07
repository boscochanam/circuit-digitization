"use client";

interface OverlayControlsProps {
  activeOverlay: string;
  onOverlayChange: (overlay: string) => void;
  overlayOpacity: number;
  onOpacityChange: (opacity: number) => void;
  hasPipelineResult: boolean;
}

/**
 * Overlay controls — floating panel in bottom-right of viewport.
 * Toggle between pipeline stages and adjust opacity.
 */
export default function OverlayControls({
  activeOverlay,
  onOverlayChange,
  overlayOpacity,
  onOpacityChange,
  hasPipelineResult,
}: OverlayControlsProps) {
  const overlays = [
    { id: "none", label: "None", disabled: false },
    { id: "threshold", label: "Threshold", disabled: !hasPipelineResult },
    { id: "detected", label: "Detected", disabled: !hasPipelineResult },
    { id: "dilated", label: "Dilated", disabled: !hasPipelineResult },
  ];

  return (
    <div className="overlay-controls">
      <div className="overlay-buttons">
        {overlays.map((o) => (
          <button
            key={o.id}
            className={`overlay-btn ${activeOverlay === o.id ? "active" : ""}`}
            disabled={o.disabled}
            onClick={() => onOverlayChange(o.id)}
          >
            {o.label}
          </button>
        ))}
      </div>
      {activeOverlay !== "none" && (
        <div className="overlay-opacity">
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

      <style jsx>{`
        .overlay-controls {
          position: absolute;
          bottom: 16px;
          right: 16px;
          display: flex;
          flex-direction: column;
          gap: 8px;
          background: var(--white);
          border: 3px solid var(--black);
          padding: 12px 16px;
          z-index: 10;
          box-shadow: 4px 4px 0 var(--black);
          min-width: 280px;
        }
        .overlay-buttons {
          display: flex;
          gap: 6px;
        }
        .overlay-btn {
          font-family: var(--font-mono), monospace;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          padding: 8px 12px;
          background: var(--white);
          color: var(--black);
          border: 2px solid var(--black);
          cursor: pointer;
        }
        .overlay-btn:hover:not(:disabled) {
          background: var(--grey-light);
        }
        .overlay-btn.active {
          background: var(--black);
          color: var(--white);
        }
        .overlay-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }
        .overlay-opacity {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 10px;
          font-family: var(--font-mono), monospace;
        }
        .overlay-opacity label {
          font-weight: 600;
          text-transform: uppercase;
        }
        .overlay-opacity input {
          flex: 1;
          width: 80px;
        }
        .overlay-opacity span {
          width: 30px;
          text-align: right;
        }
      `}</style>
    </div>
  );
}

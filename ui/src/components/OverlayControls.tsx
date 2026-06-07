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
          bottom: 12px;
          right: 12px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          background: rgba(255, 255, 255, 0.95);
          border: 2px solid var(--black);
          padding: 8px;
          z-index: 10;
        }
        .overlay-buttons {
          display: flex;
          gap: 4px;
        }
        .overlay-btn {
          font-family: var(--font-mono), monospace;
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          padding: 4px 8px;
          background: var(--white);
          color: var(--grey-dark);
          border: 1px solid var(--black);
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

"use client";

import CircuitGraph from "./CircuitGraph";
import ZoomableImage from "./ZoomableImage";

interface CircuitViewportProps {
  sourceImageUrl?: string;
  imageIdx?: number;
  dataset?: string;
  preset?: string;
  params?: Record<string, string | number>;
  showSourceOverlay?: boolean;
}

/**
 * Main viewport — circuit graph is the primary view.
 * Source image can be toggled as an overlay.
 */
export default function CircuitViewport({
  sourceImageUrl,
  imageIdx = 0,
  dataset = "gt_labels",
  preset = "best_candidate_v4",
  params = {},
  showSourceOverlay = false,
}: CircuitViewportProps) {
  return (
    <div className="circuit-viewport">
      {/* Circuit graph is always rendered */}
      <CircuitGraph
        imageIdx={imageIdx}
        dataset={dataset}
        preset={preset}
        params={params}
      />

      {/* Source image overlay (toggleable) */}
      {showSourceOverlay && sourceImageUrl && (
        <div className="viewport-overlay">
          <ZoomableImage
            src={sourceImageUrl}
            alt="Source overlay"
            maxHeight="100%"
          />
        </div>
      )}
    </div>
  );
}

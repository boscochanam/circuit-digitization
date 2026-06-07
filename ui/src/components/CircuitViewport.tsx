"use client";

import { useState } from "react";
import ZoomableImage from "./ZoomableImage";
import OverlayControls from "./OverlayControls";

interface CircuitViewportProps {
  sourceImageUrl?: string;
  pipelineResult?: any;
  imageIdx?: number;
  dataset?: string;
  preset?: string;
  params?: Record<string, string | number>;
}

/**
 * Main viewport — the actual image with toggleable overlays.
 * 
 * Layers (bottom to top):
 *   1. Source image (always visible)
 *   2. Pipeline overlay (threshold / detected / dilated) — semi-transparent
 *   3. Component labels (OCR results, bounding boxes)
 *   4. Voltage/current heatmap (simulation)
 */
export default function CircuitViewport({
  sourceImageUrl,
  pipelineResult,
  imageIdx = 0,
  dataset = "gt_labels",
  preset = "best_candidate_v4",
  params = {},
}: CircuitViewportProps) {
  const [activeOverlay, setActiveOverlay] = useState<string>("none");
  const [overlayOpacity, setOverlayOpacity] = useState(70);

  // Get overlay image based on selection
  const getOverlayUrl = (type: string): string | null => {
    if (!pipelineResult) return null;
    switch (type) {
      case "threshold":
        return pipelineResult.threshold ? `data:image/jpeg;base64,${pipelineResult.threshold}` : null;
      case "detected":
        return pipelineResult.overlay ? `data:image/jpeg;base64,${pipelineResult.overlay}` : null;
      case "dilated":
        return pipelineResult.dilated ? `data:image/jpeg;base64,${pipelineResult.dilated}` : null;
      default:
        return null;
    }
  };

  const overlayUrl = getOverlayUrl(activeOverlay);

  return (
    <div className="circuit-viewport">
      {/* Source image (base layer) */}
      {sourceImageUrl ? (
        <div className="viewport-base">
          <ZoomableImage
            src={sourceImageUrl}
            alt="Source"
            maxHeight="100%"
          />
        </div>
      ) : (
        <div className="viewport-empty">No image loaded</div>
      )}

      {/* Pipeline overlay (semi-transparent on top of source) */}
      {overlayUrl && (
        <div
          className="viewport-overlay"
          style={{ opacity: overlayOpacity / 100 }}
        >
          <img
            src={overlayUrl}
            alt={activeOverlay}
            style={{ width: "100%", height: "100%", objectFit: "contain" }}
          />
        </div>
      )}

      {/* Overlay controls (fixed position) */}
      <OverlayControls
        activeOverlay={activeOverlay}
        onOverlayChange={setActiveOverlay}
        overlayOpacity={overlayOpacity}
        onOpacityChange={setOverlayOpacity}
        hasPipelineResult={!!pipelineResult}
      />
    </div>
  );
}

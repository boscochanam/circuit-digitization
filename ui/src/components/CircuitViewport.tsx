"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import ZoomableImage from "./ZoomableImage";
import OverlayControls from "./OverlayControls";
import ComponentPopover from "./ComponentPopover";

interface CircuitViewportProps {
  sourceImageUrl?: string;
  pipelineResult?: any;
  simOverlayUrl?: string | null;
  ocrResults?: any;
  imageIdx?: number;
  dataset?: string;
  preset?: string;
  params?: Record<string, string | number>;
  onRunOCR?: () => void;
  ocrLoading?: boolean;
  onActiveOverlayChange?: (overlay: string) => void;
  componentValues?: Record<string, string>;
  onValueChange?: (name: string, value: string) => void;
}

/**
 * Main viewport — the actual image with toggleable overlays.
 * 
 * Layers (bottom to top):
 *   1. Source image (always visible)
 *   2. Pipeline overlay (threshold / detected / dilated) — semi-transparent
 *   3. Voltage/current heatmap overlay — semi-transparent
 *   4. Component labels (names + OCR values)
 */
export default function CircuitViewport({
  sourceImageUrl,
  pipelineResult,
  simOverlayUrl,
  ocrResults,
  imageIdx = 0,
  dataset = "gt_labels",
  preset = "best_candidate_v4",
  params = {},
  onRunOCR,
  ocrLoading = false,
  onActiveOverlayChange,
  componentValues = {},
  onValueChange,
}: CircuitViewportProps) {
  const [activeOverlay, setActiveOverlay] = useState<string>("none");
  const [overlayOpacity, setOverlayOpacity] = useState(70);
  const [editingComponent, setEditingComponent] = useState<{ name: string; type: string; x: number; y: number } | null>(null);

  const viewportRef = useRef<HTMLDivElement>(null);
  const imgElRef = useRef<HTMLImageElement | null>(null);
  const [imgRect, setImgRect] = useState<{ left: number; top: number; width: number; naturalWidth: number; naturalHeight: number } | null>(null);

  const recalcImgRect = useCallback(() => {
    const vp = viewportRef.current;
    const img = imgElRef.current;
    if (!vp || !img || !img.naturalWidth) return;
    const vpR = vp.getBoundingClientRect();
    const imgR = img.getBoundingClientRect();
    setImgRect({
      left: imgR.left - vpR.left,
      top: imgR.top - vpR.top,
      width: imgR.width,
      naturalWidth: img.naturalWidth,
      naturalHeight: img.naturalHeight,
    });
  }, []);

  const handleImageLoad = useCallback((img: HTMLImageElement) => {
    imgElRef.current = img;
    requestAnimationFrame(() => recalcImgRect());
  }, [recalcImgRect]);

  const handleViewChange = useCallback(() => {
    requestAnimationFrame(() => recalcImgRect());
  }, [recalcImgRect]);

  useEffect(() => {
    const vp = viewportRef.current;
    if (!vp) return;
    const ro = new ResizeObserver(() => recalcImgRect());
    ro.observe(vp);
    return () => ro.disconnect();
  }, [recalcImgRect]);

  const handleOverlayChange = (overlay: string) => {
    setActiveOverlay(overlay);
    onActiveOverlayChange?.(overlay);
  };

  // Get overlay image based on selection
  const getOverlayUrl = (type: string): string | null => {
    if (type === "voltage") return simOverlayUrl ?? null;
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

  const components = pipelineResult?.components ?? [];

  const imgScale = imgRect ? imgRect.width / imgRect.naturalWidth : 1;
  const imgOffsetX = imgRect?.left ?? 0;
  const imgOffsetY = imgRect?.top ?? 0;

  return (
    <div className="circuit-viewport" ref={viewportRef}>
      {/* Source image (base layer) — overlay passed inside ZoomableImage */}
      {sourceImageUrl ? (
        <div className="viewport-base">
          <ZoomableImage
            src={sourceImageUrl}
            alt="Source"
            maxHeight="100%"
            onImageLoad={handleImageLoad}
            onViewChange={handleViewChange}
            overlay={overlayUrl ? (
              <img
                src={overlayUrl}
                alt={activeOverlay}
                style={{ width: "100%", height: "100%", objectFit: "contain" }}
              />
            ) : undefined}
            overlayOpacity={overlayOpacity / 100}
          />
        </div>
      ) : (
        <div className="viewport-empty">No image loaded</div>
      )}

      {/* Component labels overlay */}
      {components.length > 0 && (
        <div className="viewport-labels">
          {components.slice(0, 50).map((c: any, i: number) => {
            if (!c.bbox) return null;
            const [x1, y1, x2, y2] = c.bbox;
            const cx = ((x1 + x2) / 2);
            const cy = ((y1 + y2) / 2);
            const renderX = cx * imgScale + imgOffsetX;
            const renderY = cy * imgScale + imgOffsetY;
            const ocrVal = ocrResults?.components?.find(
              (v: any) => v.type === "text" && Math.abs(v.index - i) < 5
            );
            const hasOcrValue = !!ocrVal?.value;
            const hasManualValue = !!componentValues[c.name];
            const dotColor = hasManualValue ? "var(--blue)" : hasOcrValue ? "var(--success)" : "var(--grey-mid)";

            const handleClick = (e: React.MouseEvent) => {
              e.stopPropagation();
              setEditingComponent({ name: c.name, type: c.type, x: cx, y: cy });
            };

            return (
              <div
                key={i}
                className="component-label component-label-clickable"
                style={{ left: `${renderX}px`, top: `${renderY}px` }}
                title={`${c.name} (${c.type})`}
                onClick={handleClick}
              >
                <span className="component-status-dot" style={{ background: dotColor }} />
                <span className="comp-name">{c.name}</span>
                {hasManualValue && (
                  <span className="comp-value">{componentValues[c.name]}</span>
                )}
                {!hasManualValue && hasOcrValue && (
                  <span className="comp-value">{ocrVal.value}</span>
                )}
              </div>
            );
          })}

          {/* Popover for editing component value */}
          {editingComponent && (() => {
            const popX = editingComponent.x * imgScale + imgOffsetX;
            const popY = editingComponent.y * imgScale + imgOffsetY;
            return (
            <div
              className="component-popover-anchor"
              style={{ left: `${popX}px`, top: `${popY - 40}px` }}
            >
              <ComponentPopover
                name={editingComponent.name}
                type={editingComponent.type}
                currentValue={componentValues[editingComponent.name] ?? ocrResults?.components?.find(
                  (v: any) => v.type === "text" && Math.abs(v.index - components.findIndex((c: any) => c.name === editingComponent.name)) < 5
                )?.value ?? ""}
                onSave={(value) => onValueChange?.(editingComponent.name, value)}
                onClose={() => setEditingComponent(null)}
              />
            </div>
            );
          })()}
        </div>
      )}

      {/* OCR + Overlay controls (fixed position) */}
      <OverlayControls
        activeOverlay={activeOverlay}
        onOverlayChange={handleOverlayChange}
        overlayOpacity={overlayOpacity}
        onOpacityChange={setOverlayOpacity}
        hasPipelineResult={!!pipelineResult}
        hasSimOverlay={!!simOverlayUrl}
        onRunOCR={onRunOCR}
        ocrLoading={ocrLoading}
      />
    </div>
  );
}

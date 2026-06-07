"use client";

import { useState, useCallback, useRef, useEffect } from "react";
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
 * Main viewport — renders a single image (overlay if active, else source)
 * with component labels on top.
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

  // Zoom/pan state
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({ x: 0, y: 0, offsetX: 0, offsetY: 0 });

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

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale(prev => Math.max(0.5, Math.min(5, prev * delta)));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (scale <= 1) return;
    setIsPanning(true);
    panStartRef.current = { x: e.clientX, y: e.clientY, offsetX: offset.x, offsetY: offset.y };
  }, [scale, offset]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return;
    const dx = e.clientX - panStartRef.current.x;
    const dy = e.clientY - panStartRef.current.y;
    setOffset({ x: panStartRef.current.offsetX + dx, y: panStartRef.current.offsetY + dy });
  }, [isPanning]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  const handleDoubleClick = useCallback(() => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  }, []);

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

  const displaySrc = overlayUrl ?? sourceImageUrl ?? null;

  const components = pipelineResult?.components ?? [];

  const imgScale = imgRect ? imgRect.width / imgRect.naturalWidth : 1;
  const imgOffsetX = imgRect?.left ?? 0;
  const imgOffsetY = imgRect?.top ?? 0;

  return (
    <div 
      className="circuit-viewport" 
      ref={viewportRef}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onDoubleClick={handleDoubleClick}
      style={{ cursor: scale > 1 ? (isPanning ? "grabbing" : "grab") : "default", overflow: "hidden" }}
    >
      {displaySrc ? (
        <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`, transformOrigin: "center center", transition: isPanning ? "none" : "transform 0.1s ease-out" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={imgElRef}
              src={displaySrc}
              alt={overlayUrl ? activeOverlay : "Source"}
              onLoad={() => requestAnimationFrame(() => recalcImgRect())}
              style={{
                display: "block",
                maxWidth: "100%",
                maxHeight: "100%",
                objectFit: "contain",
                opacity: overlayUrl ? overlayOpacity / 100 : 1,
              }}
            />
          </div>
          {scale !== 1 && (
            <div style={{ position: "absolute", bottom: 8, right: 8, background: "rgba(0,0,0,0.7)", color: "#fff", padding: "4px 8px", borderRadius: 4, fontSize: 12, fontFamily: "monospace" }}>
              {Math.round(scale * 100)}%
            </div>
          )}
        </div>
      ) : (
        <div className="viewport-empty">No image loaded</div>
      )}

      {/* Component labels overlay */}
      {components.length > 0 && activeOverlay !== "none" && (
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

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import OverlayControls from "./OverlayControls";
import ComponentPopover from "./ComponentPopover";
import JoinCheckPanel from "./JoinCheckPanel";
import TopologyOverlay from "./TopologyOverlay";
import type { TopologyResult, PathResult } from "@/lib/types";

interface CircuitViewportProps {
  sourceImageUrl?: string;
  pipelineResult?: any;
  simOverlayUrl?: string | null;
  currentOverlayUrl?: string | null;
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
  // Topology overlay
  topology?: TopologyResult | null;
  topologyLoading?: boolean;
  selectedNode?: number | null;
  selectedComponent?: string | null;
  onNodeSelect?: (nodeId: number | null) => void;
  onComponentSelect?: (name: string | null) => void;
  pathStart?: string | null;
  pathEnd?: string | null;
  pathData?: PathResult | null;
  onPathClick?: (name: string) => void;
  showWires?: boolean;
  showPins?: boolean;
  showComponents?: boolean;
  onToggleWires?: () => void;
  onTogglePins?: () => void;
  onToggleComponents?: () => void;
}

/**
 * Main viewport — renders a single image (overlay if active, else source)
 * with component labels on top.
 */
export default function CircuitViewport({
  sourceImageUrl,
  pipelineResult,
  simOverlayUrl,
  currentOverlayUrl,
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
  topology = null,
  topologyLoading = false,
  selectedNode = null,
  selectedComponent = null,
  onNodeSelect,
  onComponentSelect,
  pathStart = null,
  pathEnd = null,
  pathData = null,
  onPathClick,
  showWires = true,
  showPins = true,
  showComponents = true,
  onToggleWires,
  onTogglePins,
  onToggleComponents,
}: CircuitViewportProps) {
  const [activeOverlay, setActiveOverlay] = useState<string>("none");
  const [overlayOpacity, setOverlayOpacity] = useState(70);
  const [editingComponent, setEditingComponent] = useState<{ name: string; type: string; x: number; y: number } | null>(null);

  // Excalidraw-style view transform (view tabs only — the Join view owns its
  // own panel). Two-finger scroll pans; ctrl/cmd or trackpad pinch zooms toward
  // the cursor; click-drag grabs/pans; double-click resets.
  const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({ x: 0, y: 0, vx: 0, vy: 0 });
  const viewRef = useRef(view);
  viewRef.current = view;

  const viewportRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const imgElRef = useRef<HTMLImageElement | null>(null);
  // w/h = rendered (CSS) size, nw/nh = natural (original) image size. Component
  // bbox coords are in NATURAL pixels, so labels must be scaled by w/nw, h/nh —
  // otherwise they drift off the components whenever the image is shown scaled down.
  const [imgSize, setImgSize] = useState({ w: 0, h: 0, nw: 0, nh: 0 });

  const clampScale = (s: number) => Math.max(0.2, Math.min(8, s));

  const handleOverlayChange = (overlay: string) => {
    setActiveOverlay(overlay);
    onActiveOverlayChange?.(overlay);
  };

  // Bound as a NON-passive native listener so preventDefault actually stops the
  // page from scrolling (pan) or the browser from zooming (ctrl/pinch).
  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) {
      const rect = wrapperRef.current?.getBoundingClientRect();
      const dz = Math.max(-25, Math.min(25, e.deltaY));
      const factor = Math.exp(-dz * 0.01);
      setView((v) => {
        const scale = clampScale(v.scale * factor);
        const k = scale / v.scale;
        if (!rect) return { ...v, scale };
        const dx = e.clientX - rect.left;
        const dy = e.clientY - rect.top;
        return { scale, x: v.x - dx * (k - 1), y: v.y - dy * (k - 1) };
      });
    } else {
      setView((v) => ({ ...v, x: v.x - e.deltaX, y: v.y - e.deltaY }));
    }
  }, []);

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, [handleWheel, activeOverlay]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    // grab anywhere to pan; a click with no drag still reaches component labels
    setIsPanning(true);
    panStartRef.current = { x: e.clientX, y: e.clientY, vx: viewRef.current.x, vy: viewRef.current.y };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return;
    const dx = e.clientX - panStartRef.current.x;
    const dy = e.clientY - panStartRef.current.y;
    setView((v) => ({ ...v, x: panStartRef.current.vx + dx, y: panStartRef.current.vy + dy }));
  }, [isPanning]);

  const handleMouseUp = useCallback(() => setIsPanning(false), []);
  const handleDoubleClick = useCallback(() => setView({ scale: 1, x: 0, y: 0 }), []);

  const zoomToCenter = useCallback((factor: number) => {
    const vp = viewportRef.current?.getBoundingClientRect();
    const rect = wrapperRef.current?.getBoundingClientRect();
    setView((v) => {
      const scale = clampScale(v.scale * factor);
      const k = scale / v.scale;
      if (!vp || !rect) return { ...v, scale };
      const dx = vp.left + vp.width / 2 - rect.left;
      const dy = vp.top + vp.height / 2 - rect.top;
      return { scale, x: v.x - dx * (k - 1), y: v.y - dy * (k - 1) };
    });
  }, []);

  // Get overlay image based on selection
  const getOverlayUrl = (type: string): string | null => {
    if (type === "voltage") return simOverlayUrl ?? null;
    if (type === "current") return currentOverlayUrl ?? null;
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

  // natural→rendered scale so component labels land ON the components.
  // Coordinates are in original image space (704×704 etc.) but the displayed
  // image is a thumbnail (300×300). Use original dimensions from pipeline result.
  const origW = pipelineResult?.image_width ?? imgSize.nw;
  const origH = pipelineResult?.image_height ?? imgSize.nh;
  const sx = origW ? imgSize.w / origW : 1;
  const sy = origH ? imgSize.h / origH : 1;

  /** Only R, C, L, V have SPICE models — only these are value-editable */
  const isEditable = (name: string) => /^[RCLV]/.test(name);

  const measureImg = useCallback((img: HTMLImageElement | null) => {
    imgElRef.current = img;
    if (img) {
      setImgSize({ w: img.offsetWidth, h: img.offsetHeight, nw: img.naturalWidth, nh: img.naturalHeight });
    }
  }, []);

  return (
    <div className="viewport-col">
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
    {activeOverlay === "join" ? (
      <div className="join-view-host">
        <JoinCheckPanel imageIdx={imageIdx} dataset={dataset} preset={preset} params={params} />
      </div>
    ) : (
    <div
      className="circuit-viewport"
      ref={viewportRef}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onDoubleClick={handleDoubleClick}
      style={{ cursor: isPanning ? "grabbing" : "grab", overflow: "hidden", touchAction: "none" }}
    >
      {displaySrc ? (
        <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div ref={wrapperRef} style={{ position: "relative", maxWidth: "100%", maxHeight: "100%", transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`, transformOrigin: "0 0", transition: isPanning ? "none" : "transform 0.08s ease-out" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={measureImg}
              onLoad={(e) => measureImg(e.currentTarget)}
              src={displaySrc}
              alt={overlayUrl ? activeOverlay : "Source"}
              style={{
                display: "block",
                maxWidth: "100%",
                maxHeight: "100%",
                objectFit: "contain",
                opacity: overlayUrl ? overlayOpacity / 100 : 1,
              }}
            />
            {/* Labels inside transform wrapper — scale with image */}
            {components.length > 0 && activeOverlay !== "none" && imgSize.w > 0 && (
              <div className="viewport-labels" style={{ left: imgElRef.current?.offsetLeft ?? 0, top: imgElRef.current?.offsetTop ?? 0, width: imgSize.w, height: imgSize.h }}>
                {components.slice(0, 50).map((c: any, i: number) => {
                  if (!c.bbox) return null;
                  const [x1, y1, x2, y2] = c.bbox;
                  const cx = ((x1 + x2) / 2) * sx;
                  const cy = ((y1 + y2) / 2) * sy;
                  const ocrVal = ocrResults?.components?.find(
                    (v: any) => v.type === "text" && Math.abs(v.index - i) < 5
                  );
                  const hasOcrValue = !!ocrVal?.value;
                  const hasManualValue = !!componentValues[c.name];
                  const dotColor = hasManualValue ? "var(--blue)" : hasOcrValue ? "var(--success)" : "var(--grey-mid)";

                  const editable = isEditable(c.name);
                  const handleClick = (e: React.MouseEvent) => {
                    e.stopPropagation();
                    // pass the SPICE prefix letter (R/C/L/V) as type so the popover's
                    // placeholder/label resolve (c.type is the long name like "capacitor-unpolarized")
                    setEditingComponent({ name: c.name, type: c.name.charAt(0), x: cx, y: cy });
                  };

                  return (
                    <div
                      key={i}
                      className={`component-label${editable ? " component-label-clickable" : ""}`}
                      style={{ left: `${cx}px`, top: `${cy}px` }}
                      title={`${c.name} (${c.type})`}
                      onClick={editable ? handleClick : undefined}
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
                  return (
                  <div
                    className="component-popover-anchor"
                    style={{ left: `${editingComponent.x}px`, top: `${editingComponent.y - 40}px` }}
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
            {/* Topology overlay — replaces labels when active */}
            {activeOverlay === "topology" && topology && imgSize.w > 0 && (
              <div style={{
                position: "absolute",
                left: imgElRef.current?.offsetLeft ?? 0,
                top: imgElRef.current?.offsetTop ?? 0,
                width: imgSize.w,
                height: imgSize.h,
                overflow: "hidden",
              }}>
                <TopologyOverlay
                  topology={topology}
                  imgWidth={imgSize.nw}
                  imgHeight={imgSize.nh}
                  scaleX={sx}
                  scaleY={sy}
                  selectedNode={selectedNode ?? null}
                  selectedComponent={selectedComponent ?? null}
                  onWireClick={(nodeId) => onNodeSelect?.(nodeId)}
                  onComponentClick={(name, shiftKey) => {
                    if (shiftKey) {
                      onPathClick?.(name);
                    } else {
                      onComponentSelect?.(name);
                    }
                  }}
                  onBackgroundClick={() => {
                    onNodeSelect?.(null);
                    onComponentSelect?.(null);
                    if (onPathClick) {
                      onPathClick(""); // clear path
                    }
                  }}
                  pathStart={pathStart}
                  pathEnd={pathEnd}
                  pathData={pathData}
                  showWires={showWires}
                  showPins={showPins}
                  showComponents={showComponents}
                  onToggleWires={onToggleWires}
                  onTogglePins={onTogglePins}
                  onToggleComponents={onToggleComponents}
                />
              </div>
            )}
          </div>
          {/* Zoom controls — minus / reset% / plus. stopPropagation so the
              buttons don't start a pan or trigger the reset-on-doubleclick. */}
          <div className="zoom-ctl" onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
            <button className="zoom-ctl-btn" title="Zoom out" onClick={() => zoomToCenter(1 / 1.2)}>−</button>
            <button className="zoom-ctl-pct" title="Reset view (or double-click the image)" onClick={() => setView({ scale: 1, x: 0, y: 0 })}>{Math.round(view.scale * 100)}%</button>
            <button className="zoom-ctl-btn" title="Zoom in" onClick={() => zoomToCenter(1.2)}>+</button>
          </div>
        </div>
      ) : (
        <div className="viewport-empty">No image loaded</div>
      )}

    </div>
    )}
    </div>
  );
}

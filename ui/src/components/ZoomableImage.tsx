"use client";

import { useState, useRef, useCallback, useEffect } from "react";

interface ZoomableImageProps {
  src: string;
  alt: string;
  maxHeight?: string;
  className?: string;
  onImageLoad?: (img: HTMLImageElement) => void;
  onViewChange?: () => void;
  /** Overlay element rendered on top of the source image inside the zoom container. */
  overlay?: React.ReactNode;
  /** Opacity for the overlay (0–1). */
  overlayOpacity?: number;
}

/**
 * Image with mouse-wheel zoom and drag-to-pan.
 * Double-click resets to default view.
 */
export default function ZoomableImage({
  src,
  alt,
  maxHeight = "70vh",
  className = "",
  onImageLoad,
  onViewChange,
  overlay,
  overlayOpacity = 1,
}: ZoomableImageProps) {
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const offsetStart = useRef({ x: 0, y: 0 });

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale((s) => Math.min(Math.max(s * delta, 0.5), 5));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (scale <= 1) return;
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY };
    offsetStart.current = { ...offset };
  }, [scale, offset]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging) return;
    const dx = e.clientX - dragStart.current.x;
    const dy = e.clientY - dragStart.current.y;
    setOffset({
      x: offsetStart.current.x + dx,
      y: offsetStart.current.y + dy,
    });
  }, [dragging]);

  const handleMouseUp = useCallback(() => {
    setDragging(false);
  }, []);

  const handleDoubleClick = useCallback(() => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    onViewChange?.();
  }, [scale, offset, onViewChange]);

  return (
    <div
      className={`zoomable-container ${className}`}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onDoubleClick={handleDoubleClick}
      style={{
        overflow: "hidden",
        cursor: scale > 1 ? (dragging ? "grabbing" : "grab") : "default",
        position: "relative",
        borderRadius: 4,
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      <img
        src={src}
        alt={alt}
        draggable={false}
        onLoad={(e) => onImageLoad?.(e.currentTarget as HTMLImageElement)}
        style={{
          display: "block",
          maxWidth: "100%",
          maxHeight,
          transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
          transformOrigin: "center center",
          transition: dragging ? "none" : "transform 0.1s ease",
        }}
      />
      {overlay && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            opacity: overlayOpacity,
            pointerEvents: "none",
          }}
        >
          {overlay}
        </div>
      )}
      {scale !== 1 && (
        <div
          style={{
            position: "absolute",
            bottom: 6,
            right: 6,
            background: "rgba(0,0,0,0.7)",
            color: "#94a3b8",
            fontSize: 11,
            padding: "2px 6px",
            borderRadius: 4,
            pointerEvents: "none",
          }}
        >
          {Math.round(scale * 100)}% — double-click to reset
        </div>
      )}
    </div>
  );
}

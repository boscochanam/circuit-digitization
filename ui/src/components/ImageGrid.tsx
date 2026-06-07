"use client";

import { useRef, useEffect } from "react";

interface ImageGridProps {
  imageList: string[];
  imageIdx: number;
  dataset: string;
  gridCount: number;
  onSelect: (idx: number) => void;
  onScroll: (e: React.UIEvent<HTMLDivElement>) => void;
  onClose?: () => void;
}

/**
 * Thumbnail picker — a centered modal overlay. Scroll loads more thumbnails
 * (paginated), so large datasets (e.g. HDC 1680) are fully navigable.
 */
export default function ImageGrid({
  imageList,
  imageIdx,
  dataset,
  gridCount,
  onSelect,
  onScroll,
  onClose,
}: ImageGridProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const shown = Math.min(gridCount, imageList.length);

  useEffect(() => {
    const active = scrollRef.current?.querySelector(".grid-thumb-active");
    active?.scrollIntoView({ block: "nearest" });
  }, [imageIdx]);

  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose?.(); };
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [onClose]);

  return (
    <div className="image-grid-backdrop" onClick={onClose}>
      <div className="image-grid-modal" onClick={(e) => e.stopPropagation()}>
        <div className="image-grid-header">
          <span>{dataset} — {shown} of {imageList.length} shown</span>
          <button className="image-grid-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="image-grid-scroll" ref={scrollRef} onScroll={onScroll}>
          {imageList.slice(0, gridCount).map((name, i) => (
            <button
              key={name + i}
              className={`grid-thumb ${i === imageIdx ? "grid-thumb-active" : ""}`}
              onClick={() => onSelect(i)}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api/thumb?idx=${i}&ds=${dataset}`} alt="" loading="lazy" />
              <span className="grid-thumb-label">{i + 1}</span>
            </button>
          ))}
        </div>
      </div>

      <style jsx>{`
        .image-grid-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.6);
          z-index: 100;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
        }
        .image-grid-modal {
          background: var(--white);
          border: 3px solid var(--black);
          box-shadow: 6px 6px 0 var(--black);
          width: min(1100px, 92vw);
          height: min(80vh, 760px);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .image-grid-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          border-bottom: 3px solid var(--black);
          font-family: var(--font-mono), monospace;
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .image-grid-close {
          border: 2px solid var(--black);
          background: var(--white);
          font-weight: 700;
          padding: 2px 9px;
          cursor: pointer;
          line-height: 1;
        }
        .image-grid-close:hover { background: var(--black); color: var(--white); }
        .image-grid-scroll {
          flex: 1;
          min-height: 0;
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
          gap: 6px;
          padding: 12px;
          overflow-y: auto;
          background: var(--white);
        }
        .grid-thumb {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          padding: 4px;
          border: 2px solid transparent;
          background: transparent;
          cursor: pointer;
        }
        .grid-thumb:hover { border-color: var(--grey-mid); }
        .grid-thumb-active { border-color: var(--blue); background: var(--grey-light); }
        .grid-thumb img {
          width: 100%;
          aspect-ratio: 1;
          object-fit: cover;
          border: 1px solid var(--grey-light);
        }
        .grid-thumb-label {
          font-family: var(--font-mono), monospace;
          font-size: 9px;
          color: var(--grey-dark);
        }
      `}</style>
    </div>
  );
}
